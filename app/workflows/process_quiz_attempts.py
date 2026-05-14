"""
app/workflows/process_quiz_attempts — out-of-band Quiz-attempt grading processor.

ADR-049 §Decision: the manual command `python -m app.workflows.process_quiz_attempts`
polls quiz_attempts rows with status='submitted' and walks each through the grading
lifecycle: submitted → grading → (aiw run subprocess) → graded or grading_failed.

Usage:
    python -m app.workflows.process_quiz_attempts

What it does (each invocation):
  1. list_submitted_attempts() — find quiz_attempts with status='submitted'.
  2. For each Attempt:
     a. mark_attempt_grading(attempt_id)
     b. Fetch the Quiz's Section content (read-only — MC-6).
     c. Fetch attempt_questions to build GradeAttemptInput.
     d. Invoke `aiw run grade_attempt --input ... --run-id attempt-{attempt_id}`
        as a subprocess with AIW_EXTRA_WORKFLOW_MODULES including grade_attempt.
     e. Validate the artefact:
          - Required keys: per_question, score, weak_topics, recommended_sections.
          - question_id set must exactly match the input question set.
          - All explanations non-empty.
          - score in [0, len(per_question)].
     f. On success: save_attempt_grade (transactional — ADR-050).
     g. On any failure: mark_attempt_grading_failed(attempt_id, error=...) — MC-5.
  3. Log a one-line summary per Attempt to stderr.

MC-1: no forbidden LLM/agent SDK import — all AI work goes through the `aiw` CLI subprocess.
MC-4: never called inside a request handler; runs in its own process.
MC-5: on failure, zero grades rows written; failure persisted in grading_error.
MC-6: reads content/latex/ read-only; never writes it.
MC-9: processes existing user-submitted 'submitted' rows; never creates one.
MC-10: no DB driver imports; no SQL literals; DB access via app.persistence.* only.
"""

from __future__ import annotations

import json
import logging
import os
import pathlib
import subprocess
import sys

import app.config as _cfg
from app.parser import extract_sections
from app.persistence import (
    list_submitted_attempts,
    mark_attempt_grading,
    mark_attempt_grading_failed,
    save_attempt_grade,
    list_attempt_questions,
    get_quiz,
    get_attempt,
)

# The directory that *contains* the `app` package — i.e. the CS-300 repo root.
# app/workflows/process_quiz_attempts.py → parents[0]=app/workflows, [1]=app, [2]=repo root.
# Used as both cwd= and the prepended PYTHONPATH entry for the aiw subprocess so that
# `aiw run grade_attempt` can `import app.workflows.grade_attempt` regardless of where
# the `aiw` console script is installed.
_REPO_ROOT = str(pathlib.Path(__file__).resolve().parents[2])


def _get_section_content(section_id: str) -> tuple[str, str]:
    """
    Return (section_content, section_title) for the given section_id.

    The section_id is in ADR-002 composite form: "{chapter_id}#section-{n-m}".
    Reads the chapter's .tex file read-only (MC-6 — never writes content/latex/).
    Returns (latex_body, section_id) as fallback if the section is not found.
    """
    chapter_id, _section_fragment = section_id.split("#", 1)

    content_root = pathlib.Path(_cfg.CONTENT_ROOT)
    tex_path = content_root / f"{chapter_id}.tex"

    if not tex_path.exists():
        raise FileNotFoundError(f"LaTeX file not found: {tex_path}")

    latex_text = tex_path.read_text(encoding="utf-8")
    sections = extract_sections(chapter_id, latex_text)

    for section in sections:
        if section["id"] == section_id:
            content = section.get("body_html", "")
            title = section.get("heading_text", section_id)
            return content, title

    # Fallback: return the whole latex body as content
    return latex_text, chapter_id


def _parse_artefact_from_stdout(stdout: str) -> dict:
    """
    Parse the terminal artefact from `aiw run` stdout.

    ADR-036 §The aiw run CLI's stdout contract:
      stdout = json.dumps(artifact, indent=2) + "\\ntotal cost: $X.XXXX\\n"
    Strip the trailing `total cost:` line(s), then json.loads the rest.
    Returns the parsed dict.
    Raises ValueError on parse failure.
    """
    lines = stdout.strip().splitlines()
    while lines and lines[-1].strip().startswith("total cost:"):
        lines.pop()

    if not lines:
        raise ValueError("aiw run stdout was empty after stripping cost trailer")

    artefact_json = "\n".join(lines)
    return json.loads(artefact_json)


def _invoke_grade_attempt(
    *,
    section_content: str,
    section_title: str,
    questions_json: str,
    run_id: str,
) -> dict:
    """
    Invoke the grade_attempt workflow via the documented `aiw run` CLI subprocess.

    ADR-049 §Decision: subprocess.run with AIW_EXTRA_WORKFLOW_MODULES set to
    include both question_gen and grade_attempt (in case the same python env
    has both loaded; grade_attempt is the one actually used here).

    Returns the terminal artefact dict on success.
    Raises ValueError with the error message on failure.

    MC-1: no LLM SDK import; invocation goes through the `aiw` CLI subprocess.
    """
    inherited_pythonpath = os.environ.get("PYTHONPATH", "")
    pythonpath = os.pathsep.join(p for p in (_REPO_ROOT, inherited_pythonpath) if p)

    env = {
        **os.environ,
        "AIW_EXTRA_WORKFLOW_MODULES": "app.workflows.question_gen,app.workflows.grade_attempt",
        "PYTHONPATH": pythonpath,
    }

    result = subprocess.run(
        [
            "aiw", "run", "grade_attempt",
            "--input", f"section_content={section_content}",
            "--input", f"section_title={section_title}",
            "--input", f"questions={questions_json}",
            "--run-id", run_id,
        ],
        env=env,
        capture_output=True,
        text=True,
        cwd=_REPO_ROOT,
    )

    if result.returncode != 0:
        stderr_msg = result.stderr.strip() or f"aiw run exited {result.returncode}"
        raise ValueError(stderr_msg)

    try:
        artefact = _parse_artefact_from_stdout(result.stdout)
    except (json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"Failed to parse aiw run stdout: {exc}") from exc

    return artefact


def _validate_artefact(artefact: dict, expected_question_ids: set[int]) -> None:
    """
    Validate the grade_attempt artefact from the workflow subprocess.

    ADR-049 §Decision (artefact validation):
      - Required keys: per_question, score, weak_topics, recommended_sections.
      - question_id set must exactly match expected_question_ids.
      - All explanations non-empty (min_length=1 per ADR-048 schema).
      - score in [0, len(per_question)].

    Raises ValueError with a descriptive message on any validation failure.
    """
    # Required keys check
    required_keys = {"per_question", "score", "weak_topics", "recommended_sections"}
    missing_keys = required_keys - set(artefact.keys())
    if missing_keys:
        raise ValueError(f"Artefact missing required keys: {missing_keys!r}")

    per_question = artefact["per_question"]
    score = artefact["score"]

    if not isinstance(per_question, list):
        raise ValueError(f"per_question must be a list, got {type(per_question).__name__!r}")

    # question_id set must match exactly
    artefact_ids = {q.get("question_id") for q in per_question if isinstance(q, dict)}
    if artefact_ids != expected_question_ids:
        missing = expected_question_ids - artefact_ids
        extra = artefact_ids - expected_question_ids
        raise ValueError(
            f"Artefact question_id mismatch: missing={missing!r}, extra={extra!r}"
        )

    # All explanations non-empty
    for q in per_question:
        if not isinstance(q, dict):
            raise ValueError(f"per_question entry is not a dict: {q!r}")
        explanation = q.get("explanation", "")
        if not explanation or not str(explanation).strip():
            raise ValueError(
                f"Artefact per_question entry for question_id={q.get('question_id')!r} "
                "has an empty explanation."
            )

    # Score bounds [0, len(per_question)]
    n = len(per_question)
    if not isinstance(score, int) or score < 0 or score > n:
        raise ValueError(
            f"Artefact score={score!r} is out of bounds [0, {n}]."
        )


def process_pending() -> None:
    """
    Main entry point: poll 'submitted' Attempt rows and grade each.

    ADR-049 §Decision:
      1. list_submitted_attempts() — find Attempts with status='submitted'.
      2. For each: mark_attempt_grading → fetch context → invoke workflow
         → validate → save_attempt_grade (transactional) or grading_failed.
      3. Log a one-line summary per Attempt to stderr.

    The processor does NOT re-process grading_failed Attempts (ADR-049 / MC-5).
    It never creates a 'submitted' row — only processes existing ones (MC-9).
    """
    submitted_attempts = list_submitted_attempts()

    if not submitted_attempts:
        print("No submitted attempts to process.", file=sys.stderr)
        return

    for attempt in submitted_attempts:
        attempt_id = attempt.attempt_id
        quiz_id = attempt.quiz_id
        run_id = f"attempt-{attempt_id}"

        print(
            f"Processing attempt_id={attempt_id} quiz_id={quiz_id} ...",
            file=sys.stderr,
        )

        # Step a: transition to grading
        mark_attempt_grading(attempt_id)

        try:
            # Step b: fetch the Quiz's Section content (read-only — MC-6)
            quiz = get_quiz(quiz_id)
            if quiz is None:
                error_msg = f"Quiz {quiz_id} not found"
                mark_attempt_grading_failed(attempt_id, error=error_msg)
                print(f"  FAILED attempt_id={attempt_id}: {error_msg}", file=sys.stderr)
                continue

            try:
                section_content, section_title = _get_section_content(quiz.section_id)
            except Exception as exc:
                error_msg = f"Failed to read section content: {exc}"
                mark_attempt_grading_failed(attempt_id, error=error_msg)
                print(f"  FAILED attempt_id={attempt_id}: {error_msg}", file=sys.stderr)
                continue

            # Step c: fetch attempt_questions to build workflow input
            aq_list = list_attempt_questions(attempt_id)
            if not aq_list:
                error_msg = f"No attempt_questions found for attempt_id={attempt_id}"
                mark_attempt_grading_failed(attempt_id, error=error_msg)
                print(f"  FAILED attempt_id={attempt_id}: {error_msg}", file=sys.stderr)
                continue

            # Build the questions JSON for the workflow input
            questions_payload = []
            for aq in aq_list:
                questions_payload.append({
                    "question_id": aq.question_id,
                    "prompt": aq.prompt or "",
                    "preamble": aq.preamble or "",
                    "test_suite": aq.test_suite or "",
                    "response": aq.response or "",
                    "test_passed": aq.test_passed,
                    "test_status": aq.test_status or "not_run",
                    "test_output": aq.test_output or "",
                })

            expected_question_ids = {aq.question_id for aq in aq_list}
            questions_json = json.dumps(questions_payload)

            # Step d: invoke the workflow via aiw run (ADR-049)
            try:
                artefact = _invoke_grade_attempt(
                    section_content=section_content,
                    section_title=section_title,
                    questions_json=questions_json,
                    run_id=run_id,
                )
            except ValueError as exc:
                error_msg = str(exc)
                mark_attempt_grading_failed(attempt_id, error=error_msg)
                print(f"  FAILED attempt_id={attempt_id}: {error_msg}", file=sys.stderr)
                continue

            # Step e: validate the artefact (ADR-049 §artefact validation)
            try:
                _validate_artefact(artefact, expected_question_ids)
            except ValueError as exc:
                error_msg = f"Artefact validation failed: {exc}"
                mark_attempt_grading_failed(attempt_id, error=error_msg)
                print(f"  FAILED attempt_id={attempt_id}: {error_msg}", file=sys.stderr)
                continue

            # Step f: persist — transactional save_attempt_grade (ADR-050)
            per_question = artefact["per_question"]
            per_question_explanations: dict[int, str] = {
                int(q["question_id"]): str(q["explanation"])
                for q in per_question
            }
            weak_topics: list[str] = [
                str(t) for t in artefact.get("weak_topics", [])
            ]
            recommended_sections: list[str] = [
                str(s) for s in artefact.get("recommended_sections", [])
            ]

            try:
                grade = save_attempt_grade(
                    attempt_id,
                    per_question_explanations=per_question_explanations,
                    weak_topics=weak_topics,
                    recommended_sections=recommended_sections,
                )
            except Exception as exc:
                error_msg = f"Failed to persist grade: {exc}"
                mark_attempt_grading_failed(attempt_id, error=error_msg)
                print(f"  FAILED attempt_id={attempt_id}: {error_msg}", file=sys.stderr)
                continue

            print(
                f"  OK attempt_id={attempt_id}: score={grade.score}/{len(aq_list)} "
                f"status=graded",
                file=sys.stderr,
            )

        except Exception as exc:
            # Catch-all for unexpected errors — never let the processor crash
            # without setting the Attempt to grading_failed (MC-5)
            error_msg = f"Unexpected error: {exc}"
            try:
                mark_attempt_grading_failed(attempt_id, error=error_msg)
            except Exception:
                pass
            print(f"  FAILED attempt_id={attempt_id}: {error_msg}", file=sys.stderr)


def main() -> None:
    """CLI entry point: configure logging, then run the processor.

    Scoped to the CLI path only — process_pending() itself does not touch global
    logging state, so a pytest run that calls process_pending() directly leaves
    app.parser's log level alone.
    """
    logging.getLogger("app.parser").setLevel(logging.ERROR)
    process_pending()


if __name__ == "__main__":
    main()
