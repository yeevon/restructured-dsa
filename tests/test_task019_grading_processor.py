"""
TASK-019: Quiz-grading slice — tests for AC-1 (the `process_quiz_attempts` processor).

Tests derive from:
  ADR-049 — The `process_quiz_attempts` out-of-band grading processor:
    - Manual command: python -m app.workflows.process_quiz_attempts
    - Polls submitted Attempts; sets 'grading'; invokes 'aiw run grade_attempt'
    - subprocess env carries AIW_EXTRA_WORKFLOW_MODULES=app.workflows.question_gen,app.workflows.grade_attempt
    - Parses the artefact from stdout (json.dumps + "total cost: $X" trailer)
    - CS-300 sanity check: question_id set match, explanation non-empty, score bounds
    - Persists Grade transactionally via save_attempt_grade
    - On failure → grading_failed + grading_error, zero grades row, zero is_correct writes
    - Does NOT re-process grading_failed Attempts
    - Does NOT touch non-submitted Attempts (in_progress, graded, grading_failed, etc.)
    - Score cross-check: persisted score recomputed from is_correct, not from workflow's score

Coverage matrix:
  Boundary:
    - test_processor_happy_path_submitted_to_graded:
        Given a submitted Attempt, when processor runs with mocked aiw run success,
        then Attempt transitions submitted→grading→graded, grades row inserted, is_correct set.
    - test_processor_happy_path_grade_score_recomputed:
        Even if the mocked artefact claims score=0, the persisted score is computed
        from SUM(is_correct) (the ADR-049 cross-check commitment).
    - test_processor_does_not_process_non_submitted_rows:
        An in_progress / graded / grading_failed Attempt is not touched by the processor.
    - test_processor_does_not_reprocess_grading_failed:
        A grading_failed Attempt stays grading_failed on a subsequent processor run.
  Edge:
    - test_processor_multiple_submitted_attempts_all_processed:
        Two submitted Attempts are both processed in one processor run.
    - test_processor_happy_path_weak_topics_and_recommended_sections:
        weak_topics and recommended_sections from the artefact persist correctly.
    - test_processor_artefact_question_id_mismatch_triggers_grading_failed:
        If the artefact's per_question question_id set doesn't match the input,
        the processor sets grading_failed and persists no Grade.
    - test_processor_empty_per_question_in_artefact_triggers_grading_failed:
        per_question=[] when the Attempt has questions → grading_failed.
  Negative:
    - test_processor_failure_path_nonzero_exit_sets_grading_failed:
        aiw run returns non-zero → grading_failed, grading_error set.
    - test_processor_failure_path_zero_grades_row_on_failure:
        On failure, no grades row inserted (MC-5 — no partial Grade).
    - test_processor_failure_path_is_correct_stays_null_on_failure:
        On failure, attempt_questions.is_correct stays NULL (no partial Grade).
    - test_processor_failure_path_grading_error_persisted:
        grading_error column is populated on failure.
    - test_processor_malformed_artefact_json_triggers_grading_failed:
        aiw run returns non-JSON stdout → grading_failed (JSON parse error).
    - test_processor_missing_required_artefact_key_triggers_grading_failed:
        artefact missing 'per_question' key → grading_failed.
    - test_processor_mc4_submit_route_unchanged:
        The submit route (POST .../take) does NOT invoke the grading processor;
        after POST, the Attempt is still 'submitted' (MC-4).
    - test_processor_mc5_no_fabricated_grade_on_failure:
        On any failure, no Grade artifact persists (MC-5).
  Performance:
    - test_processor_happy_path_multiple_questions_within_budget:
        Processing a 5-question Attempt with a mocked aiw run subprocess completes
        within 5 seconds. Catches O(n²) in the artefact-parsing or persistence loop.

pytestmark registers all tests under task("TASK-019").

ASSUMPTIONS:
  ASSUMPTION: app.workflows.process_quiz_attempts has a callable entry point
    (process_pending() or main()) that can be called in tests with the subprocess
    seam mocked. Mirrors ADR-037 / test_task014_quiz_generation.py's pattern.

  ASSUMPTION: The processor uses subprocess.run (or a thin wrapper) to invoke aiw run.
    Tests mock at subprocess.run in the app.workflows namespace (the same seam as
    test_task014_quiz_generation.py). If the processor uses a thin helper like
    _invoke_grade_attempt, mocking subprocess.run in app.workflows still catches it
    because the helper eventually calls subprocess.run.

  ASSUMPTION: The artefact stdout contract mirrors ADR-036:
    json.dumps(artifact, indent=2) + "\\ntotal cost: $X.XXXX\\n"
    where artifact = {"per_question": [...], "score": int, "weak_topics": [...],
                      "recommended_sections": [...]}.

  ASSUMPTION: The MANDATORY_CHAPTER_ID and MANDATORY_FIRST_SECTION constants are
    valid in the current corpus (ch-01-cpp-refresher / 1-1).
"""

from __future__ import annotations

import json
import pathlib
import sqlite3
import subprocess
import time
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.task("TASK-019")

REPO_ROOT = pathlib.Path(__file__).parent.parent
MANDATORY_CHAPTER_ID = "ch-01-cpp-refresher"
MANDATORY_FIRST_SECTION = "1-1"


# ---------------------------------------------------------------------------
# artefact stdout contract (mirrors ADR-036 / ADR-049 shape for grade_attempt)
# ---------------------------------------------------------------------------


def _make_grade_success_stdout(
    per_question: list[dict],
    score: int | None = None,
    weak_topics: list[str] | None = None,
    recommended_sections: list[str] | None = None,
) -> str:
    """
    Build stdout for a successful `aiw run grade_attempt` invocation.
    Mirrors the `aiw run` documented contract: json.dumps(artifact, indent=2)
    followed by "total cost: $X.XXXX".
    """
    if score is None:
        score = sum(1 for q in per_question if q.get("explanation"))
    artefact = {
        "per_question": per_question,
        "score": score,
        "weak_topics": weak_topics if weak_topics is not None else [],
        "recommended_sections": recommended_sections if recommended_sections is not None else [],
    }
    return json.dumps(artefact, indent=2) + "\ntotal cost: $0.0034\n"


def _make_completed_process(
    stdout: str = "",
    stderr: str = "",
    returncode: int = 0,
) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(
        args=["aiw", "run", "grade_attempt"],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


# ---------------------------------------------------------------------------
# Helpers — database setup
# ---------------------------------------------------------------------------


def _get_table_columns(db_path: str, table: str) -> set[str]:
    conn = sqlite3.connect(db_path)
    cur = conn.execute(f"PRAGMA table_info({table})")
    cols = {row[1] for row in cur.fetchall()}
    conn.close()
    return cols


def _db_rows(db_path: str, sql: str, params=()) -> list[dict]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.execute(sql, params)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def _bootstrap_and_create_ready_quiz(db_path: str, monkeypatch) -> tuple[int, list[int]]:
    """
    Bootstrap DB, create a ready quiz with one question.
    Returns (quiz_id, [question_id]).
    """
    monkeypatch.setenv("NOTES_DB_PATH", db_path)
    from fastapi.testclient import TestClient  # noqa: PLC0415
    from app.main import app  # noqa: PLC0415
    client = TestClient(app)
    client.get(f"/lecture/{MANDATORY_CHAPTER_ID}")

    client.post(
        f"/lecture/{MANDATORY_CHAPTER_ID}/sections/{MANDATORY_FIRST_SECTION}/quiz",
        follow_redirects=False,
    )
    quizzes = _db_rows(db_path, "SELECT quiz_id FROM quizzes")
    quiz_id = quizzes[0]["quiz_id"]

    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO questions (section_id, prompt, topics, test_suite, preamble) VALUES (?, ?, ?, ?, ?)",
        (
            f"{MANDATORY_CHAPTER_ID}#section-{MANDATORY_FIRST_SECTION}",
            "Implement a stack.",
            "stacks|data-structures",
            "def test_stack():\n    s = Stack()\n    s.push(1)\n    assert s.pop() == 1\n",
            "",
        ),
    )
    conn.commit()
    qid = conn.execute(
        "SELECT question_id FROM questions ORDER BY question_id DESC LIMIT 1"
    ).fetchone()[0]
    conn.execute(
        "INSERT INTO quiz_questions (quiz_id, question_id, position) VALUES (?, ?, ?)",
        (quiz_id, qid, 1),
    )
    conn.execute("UPDATE quizzes SET status='ready' WHERE quiz_id=?", (quiz_id,))
    conn.commit()
    conn.close()
    return quiz_id, [qid]


def _create_submitted_attempt_with_results(
    db_path: str,
    quiz_id: int,
    question_ids: list[int],
    monkeypatch,
    *,
    test_passed_values: dict[int, bool | None] | None = None,
) -> int:
    """
    Create a submitted Attempt with test results for all question_ids.
    Returns attempt_id.
    """
    monkeypatch.setenv("NOTES_DB_PATH", db_path)
    from app.persistence import (  # noqa: PLC0415
        start_attempt,
        save_attempt_responses,
        submit_attempt,
        save_attempt_test_result,
    )
    attempt = start_attempt(quiz_id)
    save_attempt_responses(attempt.attempt_id, {q: "class Stack: pass" for q in question_ids})
    if test_passed_values is None:
        test_passed_values = {q: True for q in question_ids}
    for qid, passed in test_passed_values.items():
        if passed is not None:
            save_attempt_test_result(
                attempt.attempt_id, qid,
                passed=passed,
                status="ran",
                output="ok" if passed else "AssertionError: expected 1, got 0",
            )
    submit_attempt(attempt.attempt_id)
    return attempt.attempt_id


def _run_processor(monkeypatch, db_path: str, mock_return):
    """
    Import the grading processor and invoke it with the subprocess call mocked.
    Mirrors the pattern from test_task014_quiz_generation.py.
    """
    monkeypatch.setenv("NOTES_DB_PATH", db_path)

    if isinstance(mock_return, type) and issubclass(mock_return, Exception):
        side_effect = mock_return("mocked failure")
        mock_rv = None
    else:
        side_effect = None
        mock_rv = mock_return

    with patch("subprocess.run", return_value=mock_rv, side_effect=side_effect):
        import app.workflows.process_quiz_attempts as proc_module  # noqa: PLC0415
        if hasattr(proc_module, "process_pending"):
            proc_module.process_pending()
        elif hasattr(proc_module, "main"):
            proc_module.main()
        elif hasattr(proc_module, "run"):
            proc_module.run()
        else:
            pytest.fail(
                "app.workflows.process_quiz_attempts has no callable entry point "
                "(process_pending / main / run). ADR-049: the processor module is "
                "a __main__ module with an entry point callable."
            )


# ===========================================================================
# Boundary: happy path lifecycle
# ===========================================================================


def test_processor_happy_path_submitted_to_graded(tmp_path, monkeypatch) -> None:
    """
    AC-1 / ADR-049: given a submitted Attempt, when the processor runs with a
    successful mocked aiw run, then the Attempt transitions submitted→grading→graded,
    a grades row is inserted, and is_correct is set on attempt_questions.

    The core lifecycle test for the grading processor.
    Boundary: the full happy-path lifecycle.
    """
    db_path = str(tmp_path / "happy.db")
    quiz_id, question_ids = _bootstrap_and_create_ready_quiz(db_path, monkeypatch)
    q_id = question_ids[0]
    attempt_id = _create_submitted_attempt_with_results(db_path, quiz_id, question_ids, monkeypatch)

    success_stdout = _make_grade_success_stdout(
        per_question=[{"question_id": q_id, "explanation": "Correct implementation."}],
        score=1,
        weak_topics=[],
        recommended_sections=[],
    )
    mock_proc = _make_completed_process(stdout=success_stdout)
    _run_processor(monkeypatch, db_path, mock_proc)

    # Attempt status must be 'graded'
    rows = _db_rows(db_path, "SELECT status, graded_at FROM quiz_attempts WHERE attempt_id=?", (attempt_id,))
    assert rows[0]["status"] == "graded", (
        f"Expected status='graded' after processor run, got {rows[0]['status']!r}. "
        "ADR-049: submitted→grading→graded lifecycle."
    )
    assert rows[0]["graded_at"] is not None, "graded_at must be set after grading."

    # grades row must exist
    grade_rows = _db_rows(db_path, "SELECT * FROM grades WHERE attempt_id=?", (attempt_id,))
    assert len(grade_rows) == 1, f"Expected 1 grades row, got {len(grade_rows)}."

    # is_correct must be set on attempt_questions
    aq_rows = _db_rows(
        db_path,
        "SELECT is_correct FROM attempt_questions WHERE attempt_id=?",
        (attempt_id,),
    )
    assert len(aq_rows) >= 1
    for row in aq_rows:
        assert row["is_correct"] is not None, (
            "is_correct must be set after grading (not NULL). ADR-050 mapping."
        )


def test_processor_happy_path_grade_score_recomputed(tmp_path, monkeypatch) -> None:
    """
    AC-1 / ADR-049 §The score cross-check: even if the artefact claims score=0,
    the persisted grades.score is recomputed from SUM(is_correct).

    When test_passed=True, is_correct=1, SUM=1. The artefact's score=0 claim
    must be ignored; the persisted score must be 1.

    This is the architectural commitment that the score is the runner's truth.
    Boundary: score cross-check (workflow score vs recomputed).
    """
    db_path = str(tmp_path / "score_cross.db")
    quiz_id, question_ids = _bootstrap_and_create_ready_quiz(db_path, monkeypatch)
    q_id = question_ids[0]
    attempt_id = _create_submitted_attempt_with_results(
        db_path, quiz_id, question_ids, monkeypatch,
        test_passed_values={q_id: True},  # test_passed=True → is_correct=1
    )

    # Artefact claims score=0 (wrong — the LLM miscounted)
    success_stdout = _make_grade_success_stdout(
        per_question=[{"question_id": q_id, "explanation": "Correct."}],
        score=0,  # deliberately wrong
    )
    mock_proc = _make_completed_process(stdout=success_stdout)
    _run_processor(monkeypatch, db_path, mock_proc)

    grade_rows = _db_rows(db_path, "SELECT score FROM grades WHERE attempt_id=?", (attempt_id,))
    assert len(grade_rows) == 1, "Expected a grades row after successful grading."
    # The persisted score must be 1 (recomputed from is_correct=1), not 0
    assert grade_rows[0]["score"] == 1, (
        f"Persisted score must be recomputed from SUM(is_correct)=1, not from the workflow's "
        f"claimed score=0. Got {grade_rows[0]['score']!r}. ADR-049 / ADR-050 score cross-check."
    )


def test_processor_does_not_process_non_submitted_rows(tmp_path, monkeypatch) -> None:
    """
    AC-1 / ADR-049: the processor only processes 'submitted' Attempts.
    An in_progress Attempt is not touched.
    Boundary: status filter (only submitted rows processed).
    """
    db_path = str(tmp_path / "skip_non_submitted.db")
    quiz_id, question_ids = _bootstrap_and_create_ready_quiz(db_path, monkeypatch)

    monkeypatch.setenv("NOTES_DB_PATH", db_path)
    from app.persistence import start_attempt  # noqa: PLC0415
    in_progress_attempt = start_attempt(quiz_id)

    # Run the processor (it should find no submitted rows and do nothing)
    mock_proc = _make_completed_process(stdout="{}", returncode=0)
    _run_processor(monkeypatch, db_path, mock_proc)

    # The in_progress attempt must still be in_progress
    rows = _db_rows(
        db_path,
        "SELECT status FROM quiz_attempts WHERE attempt_id=?",
        (in_progress_attempt.attempt_id,),
    )
    assert rows[0]["status"] == "in_progress", (
        f"Processor must not touch in_progress Attempts. "
        f"Status is {rows[0]['status']!r}. ADR-049."
    )


def test_processor_does_not_reprocess_grading_failed(tmp_path, monkeypatch) -> None:
    """
    AC-1 / ADR-049 / MC-5: the processor does NOT re-process grading_failed Attempts.
    No silent unbounded retry of permanent failures.
    Boundary: grading_failed rows skipped on subsequent runs.
    """
    db_path = str(tmp_path / "no_reprocess.db")
    quiz_id, question_ids = _bootstrap_and_create_ready_quiz(db_path, monkeypatch)
    q_id = question_ids[0]
    attempt_id = _create_submitted_attempt_with_results(db_path, quiz_id, question_ids, monkeypatch)

    # First run: fail → grading_failed
    fail_proc = _make_completed_process(returncode=1, stderr="error: LLM call failed")
    _run_processor(monkeypatch, db_path, fail_proc)

    rows = _db_rows(db_path, "SELECT status FROM quiz_attempts WHERE attempt_id=?", (attempt_id,))
    assert rows[0]["status"] == "grading_failed", (
        "Expected grading_failed after first failed processor run."
    )

    # Second run: now with a successful mocked response
    success_stdout = _make_grade_success_stdout(
        per_question=[{"question_id": q_id, "explanation": "Correct."}],
        score=1,
    )
    success_proc = _make_completed_process(stdout=success_stdout)
    _run_processor(monkeypatch, db_path, success_proc)

    # The Attempt must still be grading_failed (not re-processed)
    rows = _db_rows(db_path, "SELECT status FROM quiz_attempts WHERE attempt_id=?", (attempt_id,))
    assert rows[0]["status"] == "grading_failed", (
        f"Processor must NOT re-process grading_failed Attempts. "
        f"Status changed to {rows[0]['status']!r}. ADR-049 / MC-5: no silent unbounded retry."
    )


# ===========================================================================
# Edge: multiple attempts, artefact validation
# ===========================================================================


def test_processor_multiple_submitted_attempts_all_processed(tmp_path, monkeypatch) -> None:
    """
    AC-1 / ADR-049: two submitted Attempts are both processed in one processor run.
    The processor iterates all submitted rows.
    Edge: multiple submitted Attempts in one run.
    """
    db_path = str(tmp_path / "multi_attempts.db")
    quiz_id, question_ids = _bootstrap_and_create_ready_quiz(db_path, monkeypatch)
    q_id = question_ids[0]

    attempt_id_1 = _create_submitted_attempt_with_results(db_path, quiz_id, question_ids, monkeypatch)
    attempt_id_2 = _create_submitted_attempt_with_results(db_path, quiz_id, question_ids, monkeypatch)

    success_stdout = _make_grade_success_stdout(
        per_question=[{"question_id": q_id, "explanation": "Well implemented."}],
        score=1,
    )
    mock_proc = _make_completed_process(stdout=success_stdout)
    _run_processor(monkeypatch, db_path, mock_proc)

    for attempt_id in (attempt_id_1, attempt_id_2):
        rows = _db_rows(
            db_path,
            "SELECT status FROM quiz_attempts WHERE attempt_id=?",
            (attempt_id,),
        )
        assert rows[0]["status"] == "graded", (
            f"Attempt {attempt_id} must be 'graded' after processor run. "
            f"Got {rows[0]['status']!r}. ADR-049."
        )


def test_processor_happy_path_weak_topics_and_recommended_sections(
    tmp_path, monkeypatch
) -> None:
    """
    AC-1 / ADR-049: weak_topics and recommended_sections from the artefact are
    persisted correctly in the grades table.
    Edge: non-empty weak_topics and recommended_sections in the artefact.
    """
    db_path = str(tmp_path / "topics.db")
    quiz_id, question_ids = _bootstrap_and_create_ready_quiz(db_path, monkeypatch)
    q_id = question_ids[0]
    attempt_id = _create_submitted_attempt_with_results(
        db_path, quiz_id, question_ids, monkeypatch,
        test_passed_values={q_id: False},
    )

    success_stdout = _make_grade_success_stdout(
        per_question=[{"question_id": q_id, "explanation": "You didn't handle the empty case."}],
        score=0,
        weak_topics=["stacks", "edge-cases"],
        recommended_sections=["ch-01-cpp-refresher#section-1-1"],
    )
    mock_proc = _make_completed_process(stdout=success_stdout)
    _run_processor(monkeypatch, db_path, mock_proc)

    grade_rows = _db_rows(db_path, "SELECT weak_topics, recommended_sections FROM grades WHERE attempt_id=?", (attempt_id,))
    assert len(grade_rows) == 1
    # weak_topics should contain both topics (pipe-delimited)
    raw_wt = grade_rows[0]["weak_topics"]
    assert "stacks" in raw_wt, f"Expected 'stacks' in weak_topics, got {raw_wt!r}."
    raw_rs = grade_rows[0]["recommended_sections"]
    assert "ch-01-cpp-refresher" in raw_rs, (
        f"Expected recommended section in grades, got {raw_rs!r}."
    )


def test_processor_artefact_question_id_mismatch_triggers_grading_failed(
    tmp_path, monkeypatch
) -> None:
    """
    AC-1 / ADR-049 §CS-300 sanity check: if the artefact's per_question
    question_id set doesn't match the input's question_id set, the processor
    sets grading_failed and persists no Grade.

    This is the CS-300 defense-in-depth check (ADR-049 §Artefact parsing +
    CS-300 sanity check).
    Edge: question_id mismatch in artefact.
    """
    db_path = str(tmp_path / "qid_mismatch.db")
    quiz_id, question_ids = _bootstrap_and_create_ready_quiz(db_path, monkeypatch)
    q_id = question_ids[0]
    attempt_id = _create_submitted_attempt_with_results(db_path, quiz_id, question_ids, monkeypatch)

    # Artefact uses wrong question_id
    wrong_qid = q_id + 9999
    success_stdout = _make_grade_success_stdout(
        per_question=[{"question_id": wrong_qid, "explanation": "Mismatch explanation."}],
        score=1,
    )
    mock_proc = _make_completed_process(stdout=success_stdout)
    _run_processor(monkeypatch, db_path, mock_proc)

    rows = _db_rows(db_path, "SELECT status FROM quiz_attempts WHERE attempt_id=?", (attempt_id,))
    assert rows[0]["status"] == "grading_failed", (
        f"question_id mismatch in artefact must trigger grading_failed. "
        f"Got status={rows[0]['status']!r}. ADR-049 §CS-300 sanity check."
    )

    grade_rows = _db_rows(db_path, "SELECT * FROM grades WHERE attempt_id=?", (attempt_id,))
    assert len(grade_rows) == 0, (
        "No grades row must exist after question_id mismatch. MC-5 / ADR-049."
    )


def test_processor_empty_per_question_in_artefact_triggers_grading_failed(
    tmp_path, monkeypatch
) -> None:
    """
    AC-1 / ADR-049: per_question=[] in the artefact when the Attempt has
    questions → grading_failed (the question_id set doesn't match).
    Edge: empty per_question when questions exist.
    """
    db_path = str(tmp_path / "empty_per_q.db")
    quiz_id, question_ids = _bootstrap_and_create_ready_quiz(db_path, monkeypatch)
    attempt_id = _create_submitted_attempt_with_results(db_path, quiz_id, question_ids, monkeypatch)

    success_stdout = _make_grade_success_stdout(
        per_question=[],  # empty — mismatch with the Attempt's question_ids
        score=0,
    )
    mock_proc = _make_completed_process(stdout=success_stdout)
    _run_processor(monkeypatch, db_path, mock_proc)

    rows = _db_rows(db_path, "SELECT status FROM quiz_attempts WHERE attempt_id=?", (attempt_id,))
    assert rows[0]["status"] == "grading_failed", (
        f"Empty per_question (when questions exist) must trigger grading_failed. "
        f"Got {rows[0]['status']!r}. ADR-049."
    )


# ===========================================================================
# Negative: failure paths, MC-4, MC-5
# ===========================================================================


def test_processor_failure_path_nonzero_exit_sets_grading_failed(
    tmp_path, monkeypatch
) -> None:
    """
    AC-1 / ADR-049 / MC-5: aiw run returns non-zero exit code → grading_failed.
    Negative: non-zero subprocess exit → failure lifecycle.
    """
    db_path = str(tmp_path / "fail_nonzero.db")
    quiz_id, question_ids = _bootstrap_and_create_ready_quiz(db_path, monkeypatch)
    attempt_id = _create_submitted_attempt_with_results(db_path, quiz_id, question_ids, monkeypatch)

    fail_proc = _make_completed_process(
        returncode=1,
        stderr="error: LLM provider rate limit exceeded",
    )
    _run_processor(monkeypatch, db_path, fail_proc)

    rows = _db_rows(db_path, "SELECT status FROM quiz_attempts WHERE attempt_id=?", (attempt_id,))
    assert rows[0]["status"] == "grading_failed", (
        f"Non-zero aiw run exit must produce grading_failed. Got {rows[0]['status']!r}. "
        "ADR-049 / MC-5."
    )


def test_processor_failure_path_zero_grades_row_on_failure(tmp_path, monkeypatch) -> None:
    """
    AC-1 / ADR-049 / MC-5: on failure, no grades row is inserted.
    Zero fabricated Grade on any failure path.
    Negative: absence of grades row on failure.
    """
    db_path = str(tmp_path / "no_grade_fail.db")
    quiz_id, question_ids = _bootstrap_and_create_ready_quiz(db_path, monkeypatch)
    attempt_id = _create_submitted_attempt_with_results(db_path, quiz_id, question_ids, monkeypatch)

    fail_proc = _make_completed_process(returncode=1, stderr="error: timeout")
    _run_processor(monkeypatch, db_path, fail_proc)

    grade_rows = _db_rows(db_path, "SELECT * FROM grades WHERE attempt_id=?", (attempt_id,))
    assert len(grade_rows) == 0, (
        f"On failure, no grades row must be inserted. Got {len(grade_rows)} rows. "
        "ADR-049 / MC-5: no partial Grade."
    )


def test_processor_failure_path_is_correct_stays_null_on_failure(
    tmp_path, monkeypatch
) -> None:
    """
    AC-1 / ADR-049 / MC-5: on failure, attempt_questions.is_correct stays NULL.
    No half-Grade; the per-Question is_correct writes must not persist.
    Negative: is_correct NULL after failure.
    """
    db_path = str(tmp_path / "is_correct_null_fail.db")
    quiz_id, question_ids = _bootstrap_and_create_ready_quiz(db_path, monkeypatch)
    attempt_id = _create_submitted_attempt_with_results(db_path, quiz_id, question_ids, monkeypatch)

    fail_proc = _make_completed_process(returncode=1, stderr="error: malformed response")
    _run_processor(monkeypatch, db_path, fail_proc)

    aq_rows = _db_rows(
        db_path,
        "SELECT is_correct FROM attempt_questions WHERE attempt_id=?",
        (attempt_id,),
    )
    for row in aq_rows:
        assert row["is_correct"] is None, (
            f"After grading_failed, is_correct must stay NULL. Got {row['is_correct']!r}. "
            "ADR-049 / MC-5: no is_correct writes on the failure path."
        )


def test_processor_failure_path_grading_error_persisted(tmp_path, monkeypatch) -> None:
    """
    AC-1 / ADR-049: on failure, grading_error column is populated with the failure detail.
    Negative: grading_error non-null after failure.
    """
    db_path = str(tmp_path / "grading_error.db")
    quiz_id, question_ids = _bootstrap_and_create_ready_quiz(db_path, monkeypatch)
    attempt_id = _create_submitted_attempt_with_results(db_path, quiz_id, question_ids, monkeypatch)

    fail_proc = _make_completed_process(
        returncode=1,
        stderr="error: LLM call timed out after 60s",
    )
    _run_processor(monkeypatch, db_path, fail_proc)

    rows = _db_rows(
        db_path,
        "SELECT grading_error FROM quiz_attempts WHERE attempt_id=?",
        (attempt_id,),
    )
    assert rows[0]["grading_error"] is not None, (
        "grading_error must be set after a grading failure. ADR-049 / ADR-050."
    )
    assert len(rows[0]["grading_error"]) > 0, (
        "grading_error must be a non-empty string. ADR-049."
    )


def test_processor_malformed_artefact_json_triggers_grading_failed(
    tmp_path, monkeypatch
) -> None:
    """
    AC-1 / ADR-049: aiw run returns non-JSON stdout → JSON parse error → grading_failed.
    Negative: malformed artefact (not valid JSON).
    """
    db_path = str(tmp_path / "malformed_json.db")
    quiz_id, question_ids = _bootstrap_and_create_ready_quiz(db_path, monkeypatch)
    attempt_id = _create_submitted_attempt_with_results(db_path, quiz_id, question_ids, monkeypatch)

    bad_proc = _make_completed_process(
        returncode=0,
        stdout="this is not json at all\ntotal cost: $0.0000\n",
    )
    _run_processor(monkeypatch, db_path, bad_proc)

    rows = _db_rows(db_path, "SELECT status FROM quiz_attempts WHERE attempt_id=?", (attempt_id,))
    assert rows[0]["status"] == "grading_failed", (
        f"Malformed JSON artefact must trigger grading_failed. Got {rows[0]['status']!r}. "
        "ADR-049 §Artefact parsing."
    )


def test_processor_missing_required_artefact_key_triggers_grading_failed(
    tmp_path, monkeypatch
) -> None:
    """
    AC-1 / ADR-049 §CS-300 sanity check: artefact missing 'per_question' key → grading_failed.
    The processor validates all four required keys.
    Negative: missing required key in artefact.
    """
    db_path = str(tmp_path / "missing_key.db")
    quiz_id, question_ids = _bootstrap_and_create_ready_quiz(db_path, monkeypatch)
    attempt_id = _create_submitted_attempt_with_results(db_path, quiz_id, question_ids, monkeypatch)

    # Artefact missing 'per_question' key
    incomplete_artefact = {"score": 1, "weak_topics": [], "recommended_sections": []}
    bad_stdout = json.dumps(incomplete_artefact, indent=2) + "\ntotal cost: $0.0010\n"
    bad_proc = _make_completed_process(returncode=0, stdout=bad_stdout)
    _run_processor(monkeypatch, db_path, bad_proc)

    rows = _db_rows(db_path, "SELECT status FROM quiz_attempts WHERE attempt_id=?", (attempt_id,))
    assert rows[0]["status"] == "grading_failed", (
        f"Missing 'per_question' key must trigger grading_failed. Got {rows[0]['status']!r}. "
        "ADR-049 §CS-300 sanity check."
    )


def test_processor_mc4_submit_route_unchanged(tmp_path, monkeypatch) -> None:
    """
    AC-1 / MC-4: The submit route (POST .../take) does NOT invoke the grading processor.
    After submit POST, the Attempt is still 'submitted' (grading happens out-of-band).
    Negative: MC-4 — AI work is asynchronous from the learner's perspective.
    """
    db_path = str(tmp_path / "mc4.db")
    quiz_id, question_ids = _bootstrap_and_create_ready_quiz(db_path, monkeypatch)
    q_id = question_ids[0]

    monkeypatch.setenv("NOTES_DB_PATH", db_path)
    from app.persistence import start_attempt, save_attempt_responses  # noqa: PLC0415
    from fastapi.testclient import TestClient  # noqa: PLC0415
    from app.main import app  # noqa: PLC0415
    client = TestClient(app)
    attempt = start_attempt(quiz_id)
    save_attempt_responses(attempt.attempt_id, {q_id: "class Stack: pass"})

    # Submit via the HTTP route
    section_number = MANDATORY_FIRST_SECTION
    resp = client.post(
        f"/lecture/{MANDATORY_CHAPTER_ID}/sections/{section_number}/quiz/{quiz_id}/take",
        data={f"response_{q_id}": "class Stack: pass"},
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303), f"Expected redirect after submit, got {resp.status_code}"

    # The Attempt must be 'submitted', NOT 'graded' or 'grading'
    rows = _db_rows(
        db_path,
        "SELECT status FROM quiz_attempts WHERE quiz_id=? ORDER BY created_at DESC",
        (quiz_id,),
    )
    # Find the most recently submitted attempt
    statuses = [r["status"] for r in rows]
    # At least one attempt must be 'submitted'; none should be 'graded' or 'grading'
    assert "submitted" in statuses, (
        f"After POST submit, Attempt must be 'submitted'. Statuses: {statuses!r}. MC-4."
    )
    assert "graded" not in statuses, (
        f"After POST submit, no Attempt must be 'graded' (grading is out-of-band). "
        f"Statuses: {statuses!r}. MC-4."
    )
    assert "grading" not in statuses, (
        f"After POST submit, no Attempt must be 'grading'. Statuses: {statuses!r}. MC-4."
    )


def test_processor_mc5_no_fabricated_grade_on_failure(tmp_path, monkeypatch) -> None:
    """
    AC-1 / AC-6 / MC-5: on any failure, no Grade artifact persists.
    The system never fabricates a result to cover for a failure.
    Negative: absence of any partial-Grade artifact on failure.
    """
    db_path = str(tmp_path / "mc5.db")
    quiz_id, question_ids = _bootstrap_and_create_ready_quiz(db_path, monkeypatch)
    attempt_id = _create_submitted_attempt_with_results(db_path, quiz_id, question_ids, monkeypatch)

    fail_proc = _make_completed_process(returncode=1, stderr="error: permanent failure")
    _run_processor(monkeypatch, db_path, fail_proc)

    # No grades row
    grade_rows = _db_rows(db_path, "SELECT * FROM grades WHERE attempt_id=?", (attempt_id,))
    assert len(grade_rows) == 0, "MC-5: no grades row must exist on failure."

    # No is_correct / explanation set on attempt_questions
    aq_rows = _db_rows(
        db_path,
        "SELECT is_correct, explanation FROM attempt_questions WHERE attempt_id=?",
        (attempt_id,),
    )
    for row in aq_rows:
        assert row["is_correct"] is None, (
            f"MC-5: is_correct must stay NULL on failure. Got {row['is_correct']!r}."
        )
        assert row["explanation"] is None, (
            f"MC-5: explanation must stay NULL on failure. Got {row['explanation']!r}."
        )


# ===========================================================================
# Performance: processor with multiple questions
# ===========================================================================


def test_processor_happy_path_multiple_questions_within_budget(
    tmp_path, monkeypatch
) -> None:
    """
    AC-1 / Performance: processing a 5-question Attempt with a mocked aiw run
    subprocess completes within 5 seconds.

    Scale surface: the artefact-parsing loop, the per-question is_correct mapping,
    and the transactional save. Catches O(n²) if the implementer does separate
    transactions per question, or naively rescans attempt_questions on each update.

    The 5s budget is generous for SQLite — the goal is catching runaway scaling.
    """
    db_path = str(tmp_path / "perf.db")
    monkeypatch.setenv("NOTES_DB_PATH", db_path)
    from fastapi.testclient import TestClient  # noqa: PLC0415
    from app.main import app  # noqa: PLC0415
    client = TestClient(app)
    client.get(f"/lecture/{MANDATORY_CHAPTER_ID}")

    client.post(
        f"/lecture/{MANDATORY_CHAPTER_ID}/sections/{MANDATORY_FIRST_SECTION}/quiz",
        follow_redirects=False,
    )
    quizzes_rows = _db_rows(db_path, "SELECT quiz_id FROM quizzes")
    quiz_id = quizzes_rows[0]["quiz_id"]

    # Insert 5 questions
    conn = sqlite3.connect(db_path)
    q_ids = []
    for i in range(5):
        conn.execute(
            "INSERT INTO questions (section_id, prompt, topics, test_suite, preamble) VALUES (?, ?, ?, ?, ?)",
            (
                f"{MANDATORY_CHAPTER_ID}#section-{MANDATORY_FIRST_SECTION}",
                f"Question {i + 1}: implement a stack variant.",
                "stacks",
                f"def test_q{i}(): assert True\n",
                "",
            ),
        )
        conn.commit()
        qid = conn.execute(
            "SELECT question_id FROM questions ORDER BY question_id DESC LIMIT 1"
        ).fetchone()[0]
        q_ids.append(qid)
        conn.execute(
            "INSERT INTO quiz_questions (quiz_id, question_id, position) VALUES (?, ?, ?)",
            (quiz_id, qid, i + 1),
        )
        conn.commit()
    conn.execute("UPDATE quizzes SET status='ready' WHERE quiz_id=?", (quiz_id,))
    conn.commit()
    conn.close()

    from app.persistence import (  # noqa: PLC0415
        start_attempt,
        save_attempt_responses,
        submit_attempt,
        save_attempt_test_result,
    )
    attempt = start_attempt(quiz_id)
    save_attempt_responses(attempt.attempt_id, {q: "class Stack: pass" for q in q_ids})
    for q in q_ids:
        save_attempt_test_result(attempt.attempt_id, q, passed=True, status="ran", output="ok")
    submit_attempt(attempt.attempt_id)

    # Build a success artefact with 5 per_question entries
    per_q = [
        {"question_id": q, "explanation": f"Explanation for question {q}."}
        for q in q_ids
    ]
    success_stdout = _make_grade_success_stdout(per_question=per_q, score=5)
    mock_proc = _make_completed_process(stdout=success_stdout)

    start = time.monotonic()
    _run_processor(monkeypatch, db_path, mock_proc)
    elapsed = time.monotonic() - start

    rows = _db_rows(db_path, "SELECT status FROM quiz_attempts WHERE attempt_id=?", (attempt.attempt_id,))
    assert rows[0]["status"] == "graded", (
        f"Processor must grade the 5-question Attempt. Got {rows[0]['status']!r}."
    )

    assert elapsed < 5.0, (
        f"Processing a 5-question Attempt took {elapsed:.2f}s (budget: 5s). "
        "Possible O(n²) scaling in the processor's artefact-parsing or persistence loop."
    )
