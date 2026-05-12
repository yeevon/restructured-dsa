"""
app/workflows/process_quiz_requests — out-of-band Quiz-request processor.

ADR-037 §Decision: the manual command `python -m app.workflows.process_quiz_requests`
polls quizzes rows with status='requested' and walks each through the generation
lifecycle: requested → generating → (aiw run subprocess) → ready or generation_failed.

Usage:
    python -m app.workflows.process_quiz_requests

What it does (each invocation):
  1. list_requested_quizzes() — find quizzes with status='requested'.
  2. For each Quiz:
     a. mark_quiz_generating(quiz_id)
     b. Read the Section's LaTeX content (read-only — MC-6) via app.parser.
     c. Invoke `aiw run question_gen --input section_content=... --input section_title=...
        --run-id quiz-{quiz_id}` as a subprocess (ADR-036 §How application code
        invokes the workflow) with AIW_EXTRA_WORKFLOW_MODULES=app.workflows.question_gen.
     d. On exit-0 and ≥1 non-empty-prompt question: add_questions_to_quiz + mark_quiz_ready.
     e. On non-zero exit / error / empty artefact: mark_quiz_generation_failed(error=...).
  3. Log a one-line summary per Quiz to stderr.

MC-1: no forbidden LLM/agent SDK import — all AI work goes through the `aiw` CLI subprocess.
MC-4: never called inside a request handler; runs in its own process.
MC-5: on failure, zero questions rows written; failure persisted in generation_error.
MC-6: reads content/latex/ read-only; never writes it.
MC-9: processes existing user-created 'requested' rows; never creates one.
MC-10: no DB driver imports; no SQL literals; DB access via app.persistence.* only.
"""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys

import app.config as _cfg
from app.parser import extract_sections
from app.persistence import (
    add_questions_to_quiz,
    list_requested_quizzes,
    mark_quiz_generation_failed,
    mark_quiz_generating,
    mark_quiz_ready,
)


def _get_section_content(section_id: str) -> tuple[str, str]:
    """
    Return (section_content, section_title) for the given section_id.

    The section_id is in ADR-002 composite form: "{chapter_id}#section-{n-m}".
    Reads the chapter's .tex file read-only (MC-6 — never writes content/latex/).

    Returns the Section's full parsed text and title.
    """
    # Extract chapter_id from the composite section_id
    # format: "{chapter_id}#section-{n-m}"
    chapter_id, section_fragment = section_id.split("#", 1)

    content_root = pathlib.Path(_cfg.CONTENT_ROOT)
    tex_path = content_root / f"{chapter_id}.tex"

    if not tex_path.exists():
        raise FileNotFoundError(f"LaTeX file not found: {tex_path}")

    latex_text = tex_path.read_text(encoding="utf-8")
    sections = extract_sections(chapter_id, latex_text)

    # Find the matching section
    for section in sections:
        if section["id"] == section_id:
            content = section.get("body_html", "")
            title = section.get("heading_text", section_id)
            return content, title

    # Fallback: return the whole latex body as content (section not found by ID)
    return latex_text, chapter_id


def _parse_artefact_from_stdout(stdout: str) -> dict:
    """
    Parse the terminal artefact from `aiw run` stdout.

    ADR-036 §The aiw run CLI's stdout contract:
      stdout = json.dumps(artifact, indent=2) + "\\ntotal cost: $X.XXXX\\n"
    Strip the trailing `total cost:` line(s), then json.loads the rest.
    Returns the parsed dict (e.g. {"questions": [...]}).
    Raises ValueError on parse failure.
    """
    lines = stdout.strip().splitlines()
    # Strip trailing "total cost: $..." lines
    while lines and lines[-1].strip().startswith("total cost:"):
        lines.pop()

    if not lines:
        raise ValueError("aiw run stdout was empty after stripping cost trailer")

    artefact_json = "\n".join(lines)
    return json.loads(artefact_json)


def _invoke_question_gen(
    *,
    section_content: str,
    section_title: str,
    run_id: str,
) -> dict:
    """
    Invoke the question_gen workflow via the documented `aiw run` CLI subprocess.

    ADR-036 §How application code invokes the workflow:
      subprocess.run(["aiw", "run", "question_gen", "--input", "section_content=...",
                      "--input", "section_title=...", "--run-id", "..."],
                     env={**os.environ, "AIW_EXTRA_WORKFLOW_MODULES": "app.workflows.question_gen"},
                     capture_output=True, text=True)

    Returns the terminal artefact dict on success.
    Raises ValueError with the error message on failure (non-zero exit or empty artefact).

    MC-1: no LLM SDK import; invocation goes through the `aiw` CLI subprocess.
    """
    env = {
        **os.environ,
        "AIW_EXTRA_WORKFLOW_MODULES": "app.workflows.question_gen",
    }

    # Use sys.executable-based form to be PATH-independent (ADR-036 note)
    result = subprocess.run(
        [
            "aiw", "run", "question_gen",
            "--input", f"section_content={section_content}",
            "--input", f"section_title={section_title}",
            "--run-id", run_id,
        ],
        env=env,
        capture_output=True,
        text=True,
        cwd=str(pathlib.Path(_cfg.CONTENT_ROOT).parent),
    )

    if result.returncode != 0:
        stderr_msg = result.stderr.strip() or f"aiw run exited {result.returncode}"
        raise ValueError(stderr_msg)

    try:
        artefact = _parse_artefact_from_stdout(result.stdout)
    except (json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"Failed to parse aiw run stdout: {exc}") from exc

    return artefact


def process_pending() -> None:
    """
    Main entry point: poll 'requested' Quiz rows and process each.

    ADR-037 §Decision:
      1. list_requested_quizzes() — find quizzes with status='requested'.
      2. For each: mark_quiz_generating → invoke workflow → persist or fail.
      3. Log a one-line summary per Quiz to stderr.

    The processor does NOT re-process generation_failed rows (ADR-037 / MC-5).
    It never creates a 'requested' row — only processes existing ones (MC-9).
    """
    requested_quizzes = list_requested_quizzes()

    if not requested_quizzes:
        print("No requested quizzes to process.", file=sys.stderr)
        return

    for quiz in requested_quizzes:
        quiz_id = quiz.quiz_id
        section_id = quiz.section_id
        run_id = f"quiz-{quiz_id}"

        print(f"Processing quiz_id={quiz_id} section_id={section_id!r} ...", file=sys.stderr)

        # Step a: transition to generating
        mark_quiz_generating(quiz_id)

        try:
            # Step b: read the Section's LaTeX content (read-only — MC-6)
            try:
                section_content, section_title = _get_section_content(section_id)
            except Exception as exc:
                error_msg = f"Failed to read section content: {exc}"
                mark_quiz_generation_failed(quiz_id, error=error_msg)
                print(f"  FAILED quiz_id={quiz_id}: {error_msg}", file=sys.stderr)
                continue

            # Step c: invoke the workflow via aiw run (ADR-036)
            try:
                artefact = _invoke_question_gen(
                    section_content=section_content,
                    section_title=section_title,
                    run_id=run_id,
                )
            except ValueError as exc:
                error_msg = str(exc)
                mark_quiz_generation_failed(quiz_id, error=error_msg)
                print(f"  FAILED quiz_id={quiz_id}: {error_msg}", file=sys.stderr)
                continue

            # Step d: validate the artefact (CS-300 sanity check — ADR-036)
            raw_questions = artefact.get("questions", [])

            # Filter to questions with non-empty prompt
            valid_questions = [
                q for q in raw_questions
                if isinstance(q, dict) and q.get("prompt", "").strip()
            ]

            if not valid_questions:
                # Empty artefact or no valid questions — treat as failure (ADR-036 / MC-5)
                error_msg = (
                    "Generation produced no valid coding-task Questions "
                    "(empty questions list or all prompts empty)"
                )
                mark_quiz_generation_failed(quiz_id, error=error_msg)
                print(f"  FAILED quiz_id={quiz_id}: {error_msg}", file=sys.stderr)
                continue

            # Step d (success): persist Questions + link to Quiz + mark ready
            add_questions_to_quiz(quiz_id, valid_questions)
            mark_quiz_ready(quiz_id)
            print(
                f"  OK quiz_id={quiz_id}: {len(valid_questions)} question(s) persisted, "
                "status=ready",
                file=sys.stderr,
            )

        except Exception as exc:
            # Catch-all for unexpected errors — never let the processor crash
            # without setting the Quiz to generation_failed (MC-5)
            error_msg = f"Unexpected error: {exc}"
            try:
                mark_quiz_generation_failed(quiz_id, error=error_msg)
            except Exception:
                pass
            print(f"  FAILED quiz_id={quiz_id}: {error_msg}", file=sys.stderr)


def main() -> None:
    """Alias for process_pending — callable entry point."""
    process_pending()


if __name__ == "__main__":
    process_pending()
