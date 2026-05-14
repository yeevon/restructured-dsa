"""
TASK-019: Quiz-grading slice — tests for AC-3 (persistence layer).

Tests derive from:
  ADR-050 — The Grade aggregate's persistence:
    - New `grades` table (PK attempt_id, FK → quiz_attempts)
    - New nullable `quiz_attempts.grading_error TEXT` column
    - attempt_questions.is_correct / .explanation now writeable
    - Grade dataclass (attempt_id, score, weak_topics, recommended_sections, graded_at)
    - QuizAttempt gains grading_error: str | None
    - AttemptQuestion gains is_correct: bool | None and explanation: str | None
    - New persistence functions: list_submitted_attempts, mark_attempt_grading,
      mark_attempt_graded, mark_attempt_grading_failed, save_attempt_grade,
      get_grade_for_attempt
    - test_passed → is_correct mapping: True→1, False→0, None/non-'ran'→0
    - weak_topics / recommended_sections as '|'-delimited TEXT
    - Score recomputed from SUM(is_correct), not from workflow output
    - No user_id anywhere
    - SQL stays under app/persistence/

Coverage matrix:
  Boundary:
    - test_grades_table_exists_on_fresh_db: grades table created by schema bootstrap.
    - test_grading_error_column_exists_on_fresh_db: grading_error column exists.
    - test_grading_error_column_additive_on_existing_db: additive migration adds it.
    - test_grades_table_additive_on_existing_db: additive migration creates grades table.
    - test_mark_attempt_grading_flips_status: submitted → grading.
    - test_mark_attempt_graded_flips_status: grading → graded, graded_at set.
    - test_mark_attempt_grading_failed_flips_status_and_records_error:
        grading → grading_failed, grading_error stored.
    - test_save_attempt_grade_creates_grades_row: grades row inserted with score.
    - test_save_attempt_grade_writes_is_correct_to_attempt_questions:
        attempt_questions.is_correct set from test_passed mapping.
    - test_save_attempt_grade_writes_explanation_to_attempt_questions:
        attempt_questions.explanation set from per_question_explanations.
    - test_save_attempt_grade_score_recomputed_from_is_correct:
        score in grades row is SUM(is_correct), not arbitrary input.
    - test_get_grade_for_attempt_returns_grade: Grade dataclass returned for graded Attempt.
    - test_get_grade_for_attempt_returns_none_for_ungraded: None for submitted Attempt.
    - test_list_submitted_attempts_returns_submitted_rows: only 'submitted' rows returned.
    - test_weak_topics_persisted_as_pipe_delimited_text: '|' round-trip.
    - test_recommended_sections_persisted_as_pipe_delimited_text: '|' round-trip.
    - test_empty_weak_topics_persisted_as_empty_string: [] → '' → [].
  Edge:
    - test_is_correct_mapping_true_to_1: test_passed=True → is_correct=1 (True).
    - test_is_correct_mapping_false_to_0: test_passed=False → is_correct=0 (False).
    - test_is_correct_mapping_none_to_0: test_passed=None (not run) → is_correct=0 (False).
    - test_is_correct_mapping_not_ran_status_to_0: test_status='timed_out' → is_correct=0.
    - test_list_attempt_questions_carries_is_correct_and_explanation:
        After grading, list_attempt_questions returns AttemptQuestion with both fields.
    - test_save_attempt_grade_atomicity_on_failure:
        If a per_question_explanations key doesn't match any attempt_questions row,
        the whole transaction rolls back — no partial Grade persists.
    - test_attempt_questions_is_correct_null_before_grading:
        Before grading, is_correct is None on all AttemptQuestion objects.
    - test_grade_persists_across_fresh_connection: Grade survives new sqlite3.connect().
    - test_list_submitted_attempts_excludes_other_statuses:
        graded / grading_failed / in_progress / requested attempts not in list.
    - test_multiple_questions_all_graded_in_one_save:
        save_attempt_grade with 3 questions writes all 3 is_correct values.
  Negative:
    - test_save_attempt_grade_no_partial_grade_on_question_id_mismatch:
        Passing an unknown question_id raises and leaves attempt_questions unchanged.
    - test_mark_attempt_grading_failed_writes_no_grades_row: no grades row on failure path.
    - test_mark_attempt_grading_failed_leaves_is_correct_null:
        After grading_failed, attempt_questions.is_correct stays NULL.
    - test_no_user_id_on_grades_table: grades table has no user_id column (MC-7).
    - test_no_user_id_on_grading_error_column: quiz_attempts has no user_id (MC-7).
    - test_get_grade_for_attempt_returns_none_for_grading_failed: None since no grades row.
    - test_mc10_persistence_functions_re_exported_from_init: all six new functions in __init__.
  Performance:
    - test_save_attempt_grade_many_questions_within_budget:
        Grading 10 questions via save_attempt_grade completes within 5 seconds.
        Catches O(n²) from per-question SELECT-then-UPDATE in separate transactions.

pytestmark registers all tests under task("TASK-019").

ASSUMPTIONS:
  ASSUMPTION: app.persistence exports the TASK-019 persistence functions:
    list_submitted_attempts, mark_attempt_grading, mark_attempt_graded,
    mark_attempt_grading_failed, save_attempt_grade, get_grade_for_attempt.
    If not exported, ImportError / AttributeError is the failing signal.

  ASSUMPTION: app.persistence exports the Grade dataclass.

  ASSUMPTION: The test scaffolding for creating a graded-ready Attempt (quiz +
    questions + attempt + attempt_questions with test results) reuses the
    existing persistence functions from earlier tasks (start_attempt,
    submit_attempt, save_attempt_test_result, etc.) via app.persistence.

  ASSUMPTION: The save_attempt_grade signature follows ADR-050:
    save_attempt_grade(attempt_id, *, per_question_explanations: dict[int, str],
    weak_topics: list[str], recommended_sections: list[str]) -> Grade
    — or a compatible signature as decided by the implementer; if the exact
    parameter names differ, the AttributeError / TypeError is the failing signal.
"""

from __future__ import annotations

import pathlib
import sqlite3
import tempfile
import time
from typing import Any

import pytest

pytestmark = pytest.mark.task("TASK-019")

REPO_ROOT = pathlib.Path(__file__).parent.parent

MANDATORY_CHAPTER_ID = "ch-01-cpp-refresher"
MANDATORY_FIRST_SECTION = "1-1"


# ---------------------------------------------------------------------------
# Helpers — database setup using the real application persistence layer
# ---------------------------------------------------------------------------


def _init_db(db_path: str, monkeypatch) -> None:
    """Bootstrap the schema for a fresh test DB."""
    monkeypatch.setenv("NOTES_DB_PATH", db_path)
    from app.persistence import init_schema  # noqa: PLC0415
    init_schema()


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


def _get_table_names(db_path: str) -> set[str]:
    conn = sqlite3.connect(db_path)
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    names = {row[0] for row in cur.fetchall()}
    conn.close()
    return names


def _bootstrap_and_create_quiz(db_path: str, monkeypatch) -> tuple[int, int]:
    """
    Set up a quiz with one question, return (quiz_id, question_id).
    Uses the real TestClient to trigger schema init and quiz creation.
    """
    monkeypatch.setenv("NOTES_DB_PATH", db_path)
    from fastapi.testclient import TestClient  # noqa: PLC0415
    from app.main import app  # noqa: PLC0415
    client = TestClient(app)

    # Bootstrap the schema by hitting a lecture page
    client.get(f"/lecture/{MANDATORY_CHAPTER_ID}")

    # Create a quiz via the POST route
    resp = client.post(
        f"/lecture/{MANDATORY_CHAPTER_ID}/sections/{MANDATORY_FIRST_SECTION}/quiz",
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303), f"Expected redirect, got {resp.status_code}"

    quizzes = _db_rows(db_path, "SELECT quiz_id, status FROM quizzes")
    assert quizzes, "No quiz row created"
    quiz_id = quizzes[0]["quiz_id"]

    # Insert a question and link it to the quiz
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO questions (section_id, prompt, topics, test_suite, preamble) "
        "VALUES (?, ?, ?, ?, ?)",
        (
            f"{MANDATORY_CHAPTER_ID}#section-{MANDATORY_FIRST_SECTION}",
            "Implement a stack.",
            "stacks|data-structures",
            "def test_stack():\n    s = Stack()\n    s.push(1)\n    assert s.pop() == 1\n",
            "",
        ),
    )
    conn.commit()
    question_id = conn.execute(
        "SELECT question_id FROM questions ORDER BY question_id DESC LIMIT 1"
    ).fetchone()[0]
    conn.execute(
        "INSERT INTO quiz_questions (quiz_id, question_id, position) VALUES (?, ?, ?)",
        (quiz_id, question_id, 1),
    )
    conn.execute("UPDATE quizzes SET status='ready' WHERE quiz_id=?", (quiz_id,))
    conn.commit()
    conn.close()

    return quiz_id, question_id


def _create_submitted_attempt(
    db_path: str, quiz_id: int, question_id: int, monkeypatch, *, test_passed: bool | None = True
) -> int:
    """
    Create a submitted Attempt with one AttemptQuestion with test results.
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
    save_attempt_responses(attempt.attempt_id, {question_id: "class Stack: pass"})

    if test_passed is not None:
        save_attempt_test_result(
            attempt.attempt_id,
            question_id,
            passed=test_passed,
            status="ran",
            output="ok" if test_passed else "AssertionError",
        )
    else:
        # Simulate a learner who never ran the tests
        # test_status stays NULL; test_passed stays NULL
        pass

    submit_attempt(attempt.attempt_id)
    return attempt.attempt_id


# ===========================================================================
# Boundary: schema / column existence
# ===========================================================================


def test_grades_table_exists_on_fresh_db(tmp_path, monkeypatch) -> None:
    """
    AC-3 / ADR-050: grades table is created on a fresh DB after schema bootstrap.
    Boundary: table existence check on a fresh DB.
    """
    db_path = str(tmp_path / "fresh.db")
    _init_db(db_path, monkeypatch)
    tables = _get_table_names(db_path)
    assert "grades" in tables, (
        "The 'grades' table must exist after schema bootstrap on a fresh DB. "
        "ADR-050: CREATE TABLE IF NOT EXISTS grades (attempt_id INTEGER PRIMARY KEY ...)"
    )


def test_grading_error_column_exists_on_fresh_db(tmp_path, monkeypatch) -> None:
    """
    AC-3 / ADR-050: quiz_attempts.grading_error column exists on a fresh DB.
    Boundary: column existence on fresh DB.
    """
    db_path = str(tmp_path / "fresh.db")
    _init_db(db_path, monkeypatch)
    cols = _get_table_columns(db_path, "quiz_attempts")
    assert "grading_error" in cols, (
        "quiz_attempts.grading_error column must exist after schema bootstrap. "
        "ADR-050: new nullable grading_error TEXT column (mirrors quizzes.generation_error)."
    )


def test_grading_error_column_additive_on_existing_db(tmp_path, monkeypatch) -> None:
    """
    AC-3 / ADR-050 / ADR-022: grading_error column is added by _apply_additive_migrations
    on a DB that was created WITHOUT the column (simulating a pre-TASK-019 DB).
    Boundary: additive migration; the pre-task DB must gain the column on init.
    """
    db_path = str(tmp_path / "existing.db")
    # Create a DB with the quiz_attempts table but WITHOUT grading_error
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE quiz_attempts ("
        "  attempt_id INTEGER PRIMARY KEY,"
        "  quiz_id INTEGER NOT NULL,"
        "  status TEXT NOT NULL DEFAULT 'in_progress',"
        "  created_at TEXT,"
        "  submitted_at TEXT,"
        "  graded_at TEXT"
        ")"
    )
    conn.commit()
    conn.close()

    _init_db(db_path, monkeypatch)
    cols = _get_table_columns(db_path, "quiz_attempts")
    assert "grading_error" in cols, (
        "grading_error column must be added by _apply_additive_migrations on a pre-task DB. "
        "ADR-050 / ADR-022: PRAGMA table_info check + ALTER TABLE ADD COLUMN."
    )


def test_grades_table_additive_on_existing_db(tmp_path, monkeypatch) -> None:
    """
    AC-3 / ADR-050 / ADR-022: grades table is created by _apply_additive_migrations
    on a DB that was created WITHOUT it (simulating a pre-TASK-019 DB).
    Boundary: additive creation; existing DB gains the table on init.
    """
    db_path = str(tmp_path / "existing_no_grades.db")
    # Create a minimal DB without grades table
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE quiz_attempts ("
        "  attempt_id INTEGER PRIMARY KEY,"
        "  quiz_id INTEGER NOT NULL,"
        "  status TEXT NOT NULL DEFAULT 'in_progress',"
        "  created_at TEXT,"
        "  submitted_at TEXT,"
        "  graded_at TEXT"
        ")"
    )
    conn.commit()
    conn.close()

    _init_db(db_path, monkeypatch)
    tables = _get_table_names(db_path)
    assert "grades" in tables, (
        "grades table must be created by _apply_additive_migrations on a pre-task DB. "
        "ADR-050 / ADR-022: CREATE TABLE IF NOT EXISTS grades in migrations."
    )


def test_mark_attempt_grading_flips_status(tmp_path, monkeypatch) -> None:
    """
    AC-3 / ADR-050: mark_attempt_grading(attempt_id) transitions status from
    'submitted' to 'grading'.
    Boundary: lifecycle transition submitted→grading.
    """
    db_path = str(tmp_path / "grading.db")
    quiz_id, question_id = _bootstrap_and_create_quiz(db_path, monkeypatch)
    attempt_id = _create_submitted_attempt(db_path, quiz_id, question_id, monkeypatch)

    monkeypatch.setenv("NOTES_DB_PATH", db_path)
    from app.persistence import mark_attempt_grading  # noqa: PLC0415
    mark_attempt_grading(attempt_id)

    rows = _db_rows(db_path, "SELECT status FROM quiz_attempts WHERE attempt_id=?", (attempt_id,))
    assert rows[0]["status"] == "grading", (
        f"Expected status='grading' after mark_attempt_grading, got {rows[0]['status']}. "
        "ADR-050 / ADR-049: the processor transitions submitted→grading before invoking the workflow."
    )


def test_mark_attempt_graded_flips_status(tmp_path, monkeypatch) -> None:
    """
    AC-3 / ADR-050: mark_attempt_graded(attempt_id) sets status='graded' and graded_at.
    Boundary: lifecycle transition grading→graded.
    """
    db_path = str(tmp_path / "graded.db")
    quiz_id, question_id = _bootstrap_and_create_quiz(db_path, monkeypatch)
    attempt_id = _create_submitted_attempt(db_path, quiz_id, question_id, monkeypatch)

    monkeypatch.setenv("NOTES_DB_PATH", db_path)
    from app.persistence import mark_attempt_grading, mark_attempt_graded  # noqa: PLC0415
    mark_attempt_grading(attempt_id)
    mark_attempt_graded(attempt_id)

    rows = _db_rows(db_path, "SELECT status, graded_at FROM quiz_attempts WHERE attempt_id=?", (attempt_id,))
    assert rows[0]["status"] == "graded", (
        f"Expected status='graded', got {rows[0]['status']}. ADR-050."
    )
    assert rows[0]["graded_at"] is not None, (
        "graded_at must be set when status transitions to 'graded'. ADR-050."
    )


def test_mark_attempt_grading_failed_flips_status_and_records_error(
    tmp_path, monkeypatch
) -> None:
    """
    AC-3 / ADR-050: mark_attempt_grading_failed(attempt_id, error=...) sets
    status='grading_failed' and records the error in grading_error.
    Boundary: failure lifecycle transition; error string persisted.
    """
    db_path = str(tmp_path / "failed.db")
    quiz_id, question_id = _bootstrap_and_create_quiz(db_path, monkeypatch)
    attempt_id = _create_submitted_attempt(db_path, quiz_id, question_id, monkeypatch)

    monkeypatch.setenv("NOTES_DB_PATH", db_path)
    from app.persistence import mark_attempt_grading, mark_attempt_grading_failed  # noqa: PLC0415
    mark_attempt_grading(attempt_id)
    mark_attempt_grading_failed(attempt_id, error="aiw run returned non-zero exit")

    rows = _db_rows(
        db_path,
        "SELECT status, grading_error FROM quiz_attempts WHERE attempt_id=?",
        (attempt_id,),
    )
    assert rows[0]["status"] == "grading_failed", (
        f"Expected status='grading_failed', got {rows[0]['status']}. ADR-050."
    )
    assert rows[0]["grading_error"] == "aiw run returned non-zero exit", (
        f"Expected grading_error to be set, got {rows[0]['grading_error']!r}. ADR-050."
    )


def test_save_attempt_grade_creates_grades_row(tmp_path, monkeypatch) -> None:
    """
    AC-3 / ADR-050: save_attempt_grade creates a row in the grades table.
    Boundary: grades table is populated after a successful grading call.
    """
    db_path = str(tmp_path / "save_grade.db")
    quiz_id, question_id = _bootstrap_and_create_quiz(db_path, monkeypatch)
    attempt_id = _create_submitted_attempt(db_path, quiz_id, question_id, monkeypatch, test_passed=True)

    monkeypatch.setenv("NOTES_DB_PATH", db_path)
    from app.persistence import mark_attempt_grading, save_attempt_grade  # noqa: PLC0415
    mark_attempt_grading(attempt_id)
    grade = save_attempt_grade(
        attempt_id,
        per_question_explanations={question_id: "The implementation is correct."},
        weak_topics=[],
        recommended_sections=[],
    )

    rows = _db_rows(db_path, "SELECT * FROM grades WHERE attempt_id=?", (attempt_id,))
    assert len(rows) == 1, f"Expected 1 grades row, got {len(rows)}"
    assert rows[0]["attempt_id"] == attempt_id


def test_save_attempt_grade_writes_is_correct_to_attempt_questions(
    tmp_path, monkeypatch
) -> None:
    """
    AC-3 / ADR-050: save_attempt_grade writes is_correct derived from test_passed
    to attempt_questions. test_passed=True → is_correct=1.
    Boundary: is_correct value after grading.
    """
    db_path = str(tmp_path / "is_correct.db")
    quiz_id, question_id = _bootstrap_and_create_quiz(db_path, monkeypatch)
    attempt_id = _create_submitted_attempt(db_path, quiz_id, question_id, monkeypatch, test_passed=True)

    monkeypatch.setenv("NOTES_DB_PATH", db_path)
    from app.persistence import mark_attempt_grading, save_attempt_grade  # noqa: PLC0415
    mark_attempt_grading(attempt_id)
    save_attempt_grade(
        attempt_id,
        per_question_explanations={question_id: "Correct implementation."},
        weak_topics=[],
        recommended_sections=[],
    )

    rows = _db_rows(
        db_path,
        "SELECT is_correct FROM attempt_questions WHERE attempt_id=? AND question_id=?",
        (attempt_id, question_id),
    )
    assert len(rows) == 1
    # is_correct = 1 in SQLite (True → 1 per ADR-050 mapping)
    assert rows[0]["is_correct"] == 1, (
        f"Expected is_correct=1 (test_passed=True → is_correct=1 per ADR-050 mapping), "
        f"got {rows[0]['is_correct']!r}"
    )


def test_save_attempt_grade_writes_explanation_to_attempt_questions(
    tmp_path, monkeypatch
) -> None:
    """
    AC-3 / ADR-050: save_attempt_grade writes the explanation string to
    attempt_questions.explanation.
    Boundary: explanation value after grading.
    """
    db_path = str(tmp_path / "explanation.db")
    quiz_id, question_id = _bootstrap_and_create_quiz(db_path, monkeypatch)
    attempt_id = _create_submitted_attempt(db_path, quiz_id, question_id, monkeypatch)

    monkeypatch.setenv("NOTES_DB_PATH", db_path)
    from app.persistence import mark_attempt_grading, save_attempt_grade  # noqa: PLC0415
    mark_attempt_grading(attempt_id)
    save_attempt_grade(
        attempt_id,
        per_question_explanations={question_id: "Your push/pop logic is correct."},
        weak_topics=[],
        recommended_sections=[],
    )

    rows = _db_rows(
        db_path,
        "SELECT explanation FROM attempt_questions WHERE attempt_id=? AND question_id=?",
        (attempt_id, question_id),
    )
    assert rows[0]["explanation"] == "Your push/pop logic is correct."


def test_save_attempt_grade_score_recomputed_from_is_correct(
    tmp_path, monkeypatch
) -> None:
    """
    AC-3 / ADR-050 / ADR-049 score cross-check: grades.score is recomputed from
    SUM(is_correct), NOT taken from the workflow's claimed score. The test verifies
    that the persisted score matches what SUM(is_correct) would yield (test_passed=True → 1).

    This is the architectural realization of ADR-048's commitment that the LLM does
    not re-judge correctness: even if save_attempt_grade receives a wrong 'score',
    the persisted value reflects the runner's truth.
    """
    db_path = str(tmp_path / "score_recompute.db")
    quiz_id, question_id = _bootstrap_and_create_quiz(db_path, monkeypatch)
    attempt_id = _create_submitted_attempt(db_path, quiz_id, question_id, monkeypatch, test_passed=True)

    monkeypatch.setenv("NOTES_DB_PATH", db_path)
    from app.persistence import mark_attempt_grading, save_attempt_grade  # noqa: PLC0415
    mark_attempt_grading(attempt_id)
    save_attempt_grade(
        attempt_id,
        per_question_explanations={question_id: "Correct."},
        weak_topics=[],
        recommended_sections=[],
    )

    rows = _db_rows(db_path, "SELECT score FROM grades WHERE attempt_id=?", (attempt_id,))
    assert rows[0]["score"] == 1, (
        f"Expected score=1 (one question, test_passed=True → is_correct=1 → SUM=1), "
        f"got {rows[0]['score']!r}. ADR-050: score is recomputed from SUM(is_correct)."
    )


def test_get_grade_for_attempt_returns_grade(tmp_path, monkeypatch) -> None:
    """
    AC-3 / ADR-050: get_grade_for_attempt returns a Grade dataclass for a graded Attempt.
    Boundary: successful Grade retrieval.
    """
    db_path = str(tmp_path / "get_grade.db")
    quiz_id, question_id = _bootstrap_and_create_quiz(db_path, monkeypatch)
    attempt_id = _create_submitted_attempt(db_path, quiz_id, question_id, monkeypatch)

    monkeypatch.setenv("NOTES_DB_PATH", db_path)
    from app.persistence import (  # noqa: PLC0415
        mark_attempt_grading,
        save_attempt_grade,
        get_grade_for_attempt,
    )
    mark_attempt_grading(attempt_id)
    save_attempt_grade(
        attempt_id,
        per_question_explanations={question_id: "Good work."},
        weak_topics=["stacks"],
        recommended_sections=["ch-01-cpp-refresher#section-1-1"],
    )

    grade = get_grade_for_attempt(attempt_id)
    assert grade is not None, (
        "get_grade_for_attempt must return a Grade dataclass for a graded Attempt. "
        "ADR-050."
    )
    assert grade.attempt_id == attempt_id
    assert isinstance(grade.score, int)
    assert isinstance(grade.weak_topics, list)
    assert isinstance(grade.recommended_sections, list)
    assert grade.graded_at is not None


def test_get_grade_for_attempt_returns_none_for_ungraded(tmp_path, monkeypatch) -> None:
    """
    AC-3 / ADR-050: get_grade_for_attempt returns None for a submitted (ungraded) Attempt.
    Boundary: no grades row → None returned.
    """
    db_path = str(tmp_path / "ungraded.db")
    quiz_id, question_id = _bootstrap_and_create_quiz(db_path, monkeypatch)
    attempt_id = _create_submitted_attempt(db_path, quiz_id, question_id, monkeypatch)

    monkeypatch.setenv("NOTES_DB_PATH", db_path)
    from app.persistence import get_grade_for_attempt  # noqa: PLC0415
    grade = get_grade_for_attempt(attempt_id)
    assert grade is None, (
        "get_grade_for_attempt must return None for an Attempt with no grades row. "
        "ADR-050."
    )


def test_list_submitted_attempts_returns_submitted_rows(tmp_path, monkeypatch) -> None:
    """
    AC-3 / ADR-050: list_submitted_attempts returns QuizAttempt objects with
    status='submitted'. Boundary: at least one submitted row present.
    """
    db_path = str(tmp_path / "submitted_list.db")
    quiz_id, question_id = _bootstrap_and_create_quiz(db_path, monkeypatch)
    attempt_id = _create_submitted_attempt(db_path, quiz_id, question_id, monkeypatch)

    monkeypatch.setenv("NOTES_DB_PATH", db_path)
    from app.persistence import list_submitted_attempts  # noqa: PLC0415
    attempts = list_submitted_attempts()
    assert any(a.attempt_id == attempt_id for a in attempts), (
        "list_submitted_attempts must include the submitted Attempt. ADR-050."
    )
    for a in attempts:
        assert a.status == "submitted", (
            f"list_submitted_attempts returned an Attempt with status={a.status!r}. "
            "Only 'submitted' rows should be returned. ADR-050."
        )


def test_weak_topics_persisted_as_pipe_delimited_text(tmp_path, monkeypatch) -> None:
    """
    AC-3 / ADR-050: weak_topics is persisted as '|'-delimited TEXT and
    round-trips correctly as list[str].
    Boundary: multi-item list round-trip through '|' delimiter.
    """
    db_path = str(tmp_path / "weak_topics.db")
    quiz_id, question_id = _bootstrap_and_create_quiz(db_path, monkeypatch)
    attempt_id = _create_submitted_attempt(db_path, quiz_id, question_id, monkeypatch, test_passed=False)

    monkeypatch.setenv("NOTES_DB_PATH", db_path)
    from app.persistence import mark_attempt_grading, save_attempt_grade, get_grade_for_attempt  # noqa: PLC0415
    mark_attempt_grading(attempt_id)
    save_attempt_grade(
        attempt_id,
        per_question_explanations={question_id: "You missed the edge case."},
        weak_topics=["stacks", "data-structures"],
        recommended_sections=[],
    )

    # Verify the raw TEXT form in the DB
    rows = _db_rows(db_path, "SELECT weak_topics FROM grades WHERE attempt_id=?", (attempt_id,))
    raw = rows[0]["weak_topics"]
    assert "|" in raw or raw in ("stacks|data-structures", "data-structures|stacks"), (
        f"weak_topics stored as {raw!r}; expected '|'-delimited TEXT (ADR-050)."
    )

    # Verify the dataclass round-trip
    grade = get_grade_for_attempt(attempt_id)
    assert set(grade.weak_topics) == {"stacks", "data-structures"}, (
        f"weak_topics round-trip failed: {grade.weak_topics!r}"
    )


def test_recommended_sections_persisted_as_pipe_delimited_text(
    tmp_path, monkeypatch
) -> None:
    """
    AC-3 / ADR-050: recommended_sections is persisted as '|'-delimited TEXT
    and round-trips as list[str].
    Boundary: multi-item recommended_sections round-trip.
    """
    db_path = str(tmp_path / "recommended.db")
    quiz_id, question_id = _bootstrap_and_create_quiz(db_path, monkeypatch)
    attempt_id = _create_submitted_attempt(db_path, quiz_id, question_id, monkeypatch, test_passed=False)

    monkeypatch.setenv("NOTES_DB_PATH", db_path)
    from app.persistence import mark_attempt_grading, save_attempt_grade, get_grade_for_attempt  # noqa: PLC0415
    mark_attempt_grading(attempt_id)
    save_attempt_grade(
        attempt_id,
        per_question_explanations={question_id: "Review the section on stacks."},
        weak_topics=["stacks"],
        recommended_sections=["ch-01-cpp-refresher#section-1-1", "ch-01-cpp-refresher#section-1-2"],
    )

    grade = get_grade_for_attempt(attempt_id)
    assert len(grade.recommended_sections) == 2, (
        f"Expected 2 recommended_sections, got {grade.recommended_sections!r}"
    )
    assert "ch-01-cpp-refresher#section-1-1" in grade.recommended_sections


def test_empty_weak_topics_persisted_as_empty_string(tmp_path, monkeypatch) -> None:
    """
    AC-3 / ADR-050: weak_topics=[] is persisted as '' in the TEXT column
    and round-trips back to [] (not ['']). Boundary: empty list handling.
    """
    db_path = str(tmp_path / "empty_topics.db")
    quiz_id, question_id = _bootstrap_and_create_quiz(db_path, monkeypatch)
    attempt_id = _create_submitted_attempt(db_path, quiz_id, question_id, monkeypatch, test_passed=True)

    monkeypatch.setenv("NOTES_DB_PATH", db_path)
    from app.persistence import mark_attempt_grading, save_attempt_grade, get_grade_for_attempt  # noqa: PLC0415
    mark_attempt_grading(attempt_id)
    save_attempt_grade(
        attempt_id,
        per_question_explanations={question_id: "Perfect solution!"},
        weak_topics=[],
        recommended_sections=[],
    )

    grade = get_grade_for_attempt(attempt_id)
    assert grade.weak_topics == [], (
        f"Empty weak_topics must round-trip as []. Got {grade.weak_topics!r}. ADR-050."
    )
    assert grade.recommended_sections == [], (
        f"Empty recommended_sections must round-trip as []. Got {grade.recommended_sections!r}."
    )


# ===========================================================================
# Edge: is_correct mapping variants, atomicity, across-connection persistence
# ===========================================================================


def test_is_correct_mapping_true_to_1(tmp_path, monkeypatch) -> None:
    """
    AC-3 / ADR-050 §The test_passed → is_correct mapping:
    test_passed=True → is_correct=1 (True in Python).
    Edge: the ran+True case.
    """
    db_path = str(tmp_path / "map_true.db")
    quiz_id, question_id = _bootstrap_and_create_quiz(db_path, monkeypatch)
    attempt_id = _create_submitted_attempt(db_path, quiz_id, question_id, monkeypatch, test_passed=True)

    monkeypatch.setenv("NOTES_DB_PATH", db_path)
    from app.persistence import (  # noqa: PLC0415
        mark_attempt_grading,
        save_attempt_grade,
        list_attempt_questions,
    )
    mark_attempt_grading(attempt_id)
    save_attempt_grade(
        attempt_id,
        per_question_explanations={question_id: "Correct."},
        weak_topics=[],
        recommended_sections=[],
    )
    aqs = list_attempt_questions(attempt_id)
    aq = next(a for a in aqs if a.question_id == question_id)
    assert aq.is_correct is True, (
        f"test_passed=True should map to is_correct=True, got {aq.is_correct!r}. ADR-050."
    )


def test_is_correct_mapping_false_to_0(tmp_path, monkeypatch) -> None:
    """
    AC-3 / ADR-050 §The test_passed → is_correct mapping:
    test_passed=False → is_correct=0 (False in Python).
    Edge: the ran+False case.
    """
    db_path = str(tmp_path / "map_false.db")
    quiz_id, question_id = _bootstrap_and_create_quiz(db_path, monkeypatch)
    attempt_id = _create_submitted_attempt(db_path, quiz_id, question_id, monkeypatch, test_passed=False)

    monkeypatch.setenv("NOTES_DB_PATH", db_path)
    from app.persistence import (  # noqa: PLC0415
        mark_attempt_grading,
        save_attempt_grade,
        list_attempt_questions,
    )
    mark_attempt_grading(attempt_id)
    save_attempt_grade(
        attempt_id,
        per_question_explanations={question_id: "The test failed — your pop() didn't return the right value."},
        weak_topics=["stacks"],
        recommended_sections=[],
    )
    aqs = list_attempt_questions(attempt_id)
    aq = next(a for a in aqs if a.question_id == question_id)
    assert aq.is_correct is False, (
        f"test_passed=False should map to is_correct=False, got {aq.is_correct!r}. ADR-050."
    )


def test_is_correct_mapping_none_to_0(tmp_path, monkeypatch) -> None:
    """
    AC-3 / ADR-050 §The test_passed → is_correct mapping:
    test_passed=None (learner never ran the tests) → is_correct=0 (False).
    Edge: the not-run case; failure-to-pass = not correct per §8.
    """
    db_path = str(tmp_path / "map_none.db")
    quiz_id, question_id = _bootstrap_and_create_quiz(db_path, monkeypatch)
    attempt_id = _create_submitted_attempt(db_path, quiz_id, question_id, monkeypatch, test_passed=None)

    monkeypatch.setenv("NOTES_DB_PATH", db_path)
    from app.persistence import (  # noqa: PLC0415
        mark_attempt_grading,
        save_attempt_grade,
        list_attempt_questions,
    )
    mark_attempt_grading(attempt_id)
    save_attempt_grade(
        attempt_id,
        per_question_explanations={question_id: "The test never ran — you submitted without clicking Run tests."},
        weak_topics=["stacks"],
        recommended_sections=[],
    )
    aqs = list_attempt_questions(attempt_id)
    aq = next(a for a in aqs if a.question_id == question_id)
    assert aq.is_correct is False, (
        f"test_passed=None should map to is_correct=False (not run = not correct per §8 + ADR-050 mapping). "
        f"Got {aq.is_correct!r}."
    )


def test_is_correct_mapping_not_ran_status_to_0(tmp_path, monkeypatch) -> None:
    """
    AC-3 / ADR-050 §The test_passed → is_correct mapping:
    test_status='timed_out' (test_passed=None) → is_correct=0.
    Edge: a timed-out test run.
    """
    db_path = str(tmp_path / "map_timed_out.db")
    quiz_id, question_id = _bootstrap_and_create_quiz(db_path, monkeypatch)

    # Create an attempt where the test timed out
    monkeypatch.setenv("NOTES_DB_PATH", db_path)
    from app.persistence import (  # noqa: PLC0415
        start_attempt,
        save_attempt_responses,
        submit_attempt,
        save_attempt_test_result,
        mark_attempt_grading,
        save_attempt_grade,
        list_attempt_questions,
    )
    attempt = start_attempt(quiz_id)
    save_attempt_responses(attempt.attempt_id, {question_id: "class Stack: pass"})
    save_attempt_test_result(
        attempt.attempt_id,
        question_id,
        passed=None,
        status="timed_out",
        output="Timed out after 5s",
    )
    submit_attempt(attempt.attempt_id)
    attempt_id = attempt.attempt_id

    mark_attempt_grading(attempt_id)
    save_attempt_grade(
        attempt_id,
        per_question_explanations={question_id: "The test timed out — your solution likely has an infinite loop."},
        weak_topics=["stacks"],
        recommended_sections=[],
    )
    aqs = list_attempt_questions(attempt_id)
    aq = next(a for a in aqs if a.question_id == question_id)
    assert aq.is_correct is False, (
        f"test_status='timed_out' (test_passed=None) should map to is_correct=False. "
        f"Got {aq.is_correct!r}. ADR-050 mapping table."
    )


def test_list_attempt_questions_carries_is_correct_and_explanation(
    tmp_path, monkeypatch
) -> None:
    """
    AC-3 / ADR-050: After grading, list_attempt_questions returns AttemptQuestion
    objects carrying both is_correct and explanation fields.
    Edge: the existing accessor is extended to carry the new fields.
    """
    db_path = str(tmp_path / "aq_fields.db")
    quiz_id, question_id = _bootstrap_and_create_quiz(db_path, monkeypatch)
    attempt_id = _create_submitted_attempt(db_path, quiz_id, question_id, monkeypatch)

    monkeypatch.setenv("NOTES_DB_PATH", db_path)
    from app.persistence import (  # noqa: PLC0415
        mark_attempt_grading,
        save_attempt_grade,
        list_attempt_questions,
    )
    mark_attempt_grading(attempt_id)
    save_attempt_grade(
        attempt_id,
        per_question_explanations={question_id: "Well done."},
        weak_topics=[],
        recommended_sections=[],
    )
    aqs = list_attempt_questions(attempt_id)
    aq = next(a for a in aqs if a.question_id == question_id)

    assert hasattr(aq, "is_correct"), (
        "AttemptQuestion must have an is_correct attribute after grading (ADR-050)."
    )
    assert hasattr(aq, "explanation"), (
        "AttemptQuestion must have an explanation attribute after grading (ADR-050)."
    )
    assert aq.explanation == "Well done."


def test_save_attempt_grade_atomicity_on_failure(tmp_path, monkeypatch) -> None:
    """
    AC-3 / ADR-050 / MC-5: If save_attempt_grade receives a question_id that
    doesn't match any attempt_questions row, the whole transaction rolls back.
    No partial Grade persists — the grades table stays empty.

    MC-5: the failure is honest; no partial Grade can persist.
    Edge: question_id mismatch triggers rollback.
    """
    db_path = str(tmp_path / "atomicity.db")
    quiz_id, question_id = _bootstrap_and_create_quiz(db_path, monkeypatch)
    attempt_id = _create_submitted_attempt(db_path, quiz_id, question_id, monkeypatch)

    monkeypatch.setenv("NOTES_DB_PATH", db_path)
    from app.persistence import mark_attempt_grading, save_attempt_grade  # noqa: PLC0415
    mark_attempt_grading(attempt_id)

    bogus_question_id = 99999
    with pytest.raises(Exception):
        # Passing a bogus question_id not in attempt_questions should raise
        save_attempt_grade(
            attempt_id,
            per_question_explanations={bogus_question_id: "This question doesn't exist."},
            weak_topics=[],
            recommended_sections=[],
        )

    # After the failure, no grades row must exist
    rows = _db_rows(db_path, "SELECT * FROM grades WHERE attempt_id=?", (attempt_id,))
    assert len(rows) == 0, (
        f"After save_attempt_grade failure, grades table must have no rows for this attempt. "
        f"Got {rows!r}. ADR-050 / MC-5: no partial Grade persists."
    )

    # attempt_questions.is_correct must still be NULL
    aq_rows = _db_rows(
        db_path,
        "SELECT is_correct FROM attempt_questions WHERE attempt_id=?",
        (attempt_id,),
    )
    for row in aq_rows:
        assert row["is_correct"] is None, (
            f"After rollback, is_correct must stay NULL. Got {row['is_correct']!r}."
        )


def test_attempt_questions_is_correct_null_before_grading(tmp_path, monkeypatch) -> None:
    """
    AC-3 / ADR-050 / ADR-033: Before grading, is_correct is None on all
    AttemptQuestion objects. The NULL-until-graded posture ADR-033 reserved.
    Edge: pre-grading state.
    """
    db_path = str(tmp_path / "null_before.db")
    quiz_id, question_id = _bootstrap_and_create_quiz(db_path, monkeypatch)
    attempt_id = _create_submitted_attempt(db_path, quiz_id, question_id, monkeypatch)

    monkeypatch.setenv("NOTES_DB_PATH", db_path)
    from app.persistence import list_attempt_questions  # noqa: PLC0415
    aqs = list_attempt_questions(attempt_id)
    for aq in aqs:
        assert aq.is_correct is None, (
            f"Before grading, is_correct must be None. Got {aq.is_correct!r} for "
            f"question_id={aq.question_id}. ADR-033 / ADR-050."
        )
        assert aq.explanation is None, (
            f"Before grading, explanation must be None. Got {aq.explanation!r}. ADR-033."
        )


def test_grade_persists_across_fresh_connection(tmp_path, monkeypatch) -> None:
    """
    AC-3 / ADR-050 / Manifest §7: Grade persists across sessions (a fresh
    sqlite3.connect() sees the Grade row after grading).
    Edge: persistence across connections.
    """
    db_path = str(tmp_path / "persist.db")
    quiz_id, question_id = _bootstrap_and_create_quiz(db_path, monkeypatch)
    attempt_id = _create_submitted_attempt(db_path, quiz_id, question_id, monkeypatch)

    monkeypatch.setenv("NOTES_DB_PATH", db_path)
    from app.persistence import mark_attempt_grading, save_attempt_grade  # noqa: PLC0415
    mark_attempt_grading(attempt_id)
    save_attempt_grade(
        attempt_id,
        per_question_explanations={question_id: "Correct answer."},
        weak_topics=["stacks"],
        recommended_sections=["ch-01-cpp-refresher#section-1-1"],
    )

    # Re-query with a new sqlite3.connect() — no app layer
    rows = _db_rows(db_path, "SELECT * FROM grades WHERE attempt_id=?", (attempt_id,))
    assert len(rows) == 1, (
        "Grade row must persist across a fresh connection. Manifest §7."
    )


def test_list_submitted_attempts_excludes_other_statuses(tmp_path, monkeypatch) -> None:
    """
    AC-3 / ADR-050: list_submitted_attempts excludes Attempts with status
    other than 'submitted' (graded, grading_failed, in_progress are not returned).
    Edge: only submitted rows in the result.
    """
    db_path = str(tmp_path / "exclude_others.db")
    quiz_id, question_id = _bootstrap_and_create_quiz(db_path, monkeypatch)

    # Create a submitted attempt (will be in list)
    submitted_id = _create_submitted_attempt(db_path, quiz_id, question_id, monkeypatch)

    # Create an in_progress attempt (not submitted)
    monkeypatch.setenv("NOTES_DB_PATH", db_path)
    from app.persistence import start_attempt, list_submitted_attempts  # noqa: PLC0415
    in_progress = start_attempt(quiz_id)

    attempts = list_submitted_attempts()
    ids = {a.attempt_id for a in attempts}
    assert submitted_id in ids, "Submitted Attempt must be in list_submitted_attempts."
    assert in_progress.attempt_id not in ids, (
        "in_progress Attempt must NOT be in list_submitted_attempts."
    )


def test_multiple_questions_all_graded_in_one_save(tmp_path, monkeypatch) -> None:
    """
    AC-3 / ADR-050: save_attempt_grade with 3 questions writes all 3 is_correct
    values in a single transaction.
    Edge: multiple questions graded atomically.
    """
    db_path = str(tmp_path / "multi_q.db")
    monkeypatch.setenv("NOTES_DB_PATH", db_path)
    from fastapi.testclient import TestClient  # noqa: PLC0415
    from app.main import app  # noqa: PLC0415
    client = TestClient(app)
    client.get(f"/lecture/{MANDATORY_CHAPTER_ID}")

    # Create quiz
    client.post(
        f"/lecture/{MANDATORY_CHAPTER_ID}/sections/{MANDATORY_FIRST_SECTION}/quiz",
        follow_redirects=False,
    )
    quizzes = _db_rows(db_path, "SELECT quiz_id FROM quizzes")
    quiz_id = quizzes[0]["quiz_id"]

    # Insert 3 questions
    conn = sqlite3.connect(db_path)
    q_ids = []
    for i in range(3):
        conn.execute(
            "INSERT INTO questions (section_id, prompt, topics, test_suite, preamble) VALUES (?, ?, ?, ?, ?)",
            (
                f"{MANDATORY_CHAPTER_ID}#section-{MANDATORY_FIRST_SECTION}",
                f"Question {i + 1}",
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
        mark_attempt_grading,
        save_attempt_grade,
        list_attempt_questions,
    )
    attempt = start_attempt(quiz_id)
    save_attempt_responses(attempt.attempt_id, {q: "class X: pass" for q in q_ids})
    for q in q_ids:
        save_attempt_test_result(attempt.attempt_id, q, passed=True, status="ran", output="ok")
    submit_attempt(attempt.attempt_id)

    mark_attempt_grading(attempt.attempt_id)
    save_attempt_grade(
        attempt.attempt_id,
        per_question_explanations={q: f"Explanation for question {q}." for q in q_ids},
        weak_topics=[],
        recommended_sections=[],
    )

    aqs = list_attempt_questions(attempt.attempt_id)
    for aq in aqs:
        assert aq.is_correct is True, (
            f"question_id={aq.question_id}: expected is_correct=True after grading, "
            f"got {aq.is_correct!r}."
        )
        assert aq.explanation is not None and len(aq.explanation) > 0, (
            f"question_id={aq.question_id}: expected non-empty explanation after grading."
        )


# ===========================================================================
# Negative: no partial grade, no user_id, failure path invariants
# ===========================================================================


def test_save_attempt_grade_no_partial_grade_on_question_id_mismatch(
    tmp_path, monkeypatch
) -> None:
    """
    AC-3 / ADR-050 / MC-5: Passing a question_id not in the Attempt's
    attempt_questions rows raises and leaves no partial Grade.
    This mirrors ADR-049's 'the question_id set must match' check.
    Negative: invalid question_id.
    """
    db_path = str(tmp_path / "no_partial.db")
    quiz_id, question_id = _bootstrap_and_create_quiz(db_path, monkeypatch)
    attempt_id = _create_submitted_attempt(db_path, quiz_id, question_id, monkeypatch)

    monkeypatch.setenv("NOTES_DB_PATH", db_path)
    from app.persistence import mark_attempt_grading, save_attempt_grade  # noqa: PLC0415
    mark_attempt_grading(attempt_id)

    with pytest.raises(Exception):
        save_attempt_grade(
            attempt_id,
            per_question_explanations={99999: "Mismatch."},
            weak_topics=[],
            recommended_sections=[],
        )

    rows = _db_rows(db_path, "SELECT * FROM grades WHERE attempt_id=?", (attempt_id,))
    assert len(rows) == 0, "No partial Grade row must exist after save_attempt_grade failure."


def test_mark_attempt_grading_failed_writes_no_grades_row(tmp_path, monkeypatch) -> None:
    """
    AC-3 / ADR-050 / MC-5: mark_attempt_grading_failed writes NO grades row.
    On the failure path, the grades table stays empty for this attempt_id.
    Negative: failure path produces no Grade artifact.
    """
    db_path = str(tmp_path / "no_grade_on_fail.db")
    quiz_id, question_id = _bootstrap_and_create_quiz(db_path, monkeypatch)
    attempt_id = _create_submitted_attempt(db_path, quiz_id, question_id, monkeypatch)

    monkeypatch.setenv("NOTES_DB_PATH", db_path)
    from app.persistence import mark_attempt_grading, mark_attempt_grading_failed  # noqa: PLC0415
    mark_attempt_grading(attempt_id)
    mark_attempt_grading_failed(attempt_id, error="workflow returned malformed output")

    rows = _db_rows(db_path, "SELECT * FROM grades WHERE attempt_id=?", (attempt_id,))
    assert len(rows) == 0, (
        "mark_attempt_grading_failed must NOT insert a grades row. "
        "ADR-050 / MC-5: no partial / fabricated Grade on the failure path."
    )


def test_mark_attempt_grading_failed_leaves_is_correct_null(tmp_path, monkeypatch) -> None:
    """
    AC-3 / ADR-050 / MC-5: After grading_failed, attempt_questions.is_correct stays NULL.
    The failure path must not write any is_correct value (no half-Grade).
    Negative: is_correct stays NULL on failure.
    """
    db_path = str(tmp_path / "is_correct_null_on_fail.db")
    quiz_id, question_id = _bootstrap_and_create_quiz(db_path, monkeypatch)
    attempt_id = _create_submitted_attempt(db_path, quiz_id, question_id, monkeypatch)

    monkeypatch.setenv("NOTES_DB_PATH", db_path)
    from app.persistence import mark_attempt_grading, mark_attempt_grading_failed  # noqa: PLC0415
    mark_attempt_grading(attempt_id)
    mark_attempt_grading_failed(attempt_id, error="workflow failed")

    rows = _db_rows(
        db_path,
        "SELECT is_correct, explanation FROM attempt_questions WHERE attempt_id=?",
        (attempt_id,),
    )
    for row in rows:
        assert row["is_correct"] is None, (
            f"After grading_failed, is_correct must stay NULL. Got {row['is_correct']!r}. "
            "ADR-050 / MC-5: the failure path must not write any is_correct value."
        )
        assert row["explanation"] is None, (
            f"After grading_failed, explanation must stay NULL. Got {row['explanation']!r}."
        )


def test_no_user_id_on_grades_table(tmp_path, monkeypatch) -> None:
    """
    AC-6 / MC-7 / ADR-050: The grades table must not have a user_id column.
    Single-user project; no user identity in any Grade-side table.
    Negative: column absence check.
    """
    db_path = str(tmp_path / "no_user_id.db")
    _init_db(db_path, monkeypatch)
    cols = _get_table_columns(db_path, "grades")
    assert "user_id" not in cols, (
        f"grades table must NOT have a user_id column. MC-7 (ADR-050). "
        f"Columns found: {cols!r}"
    )


def test_no_user_id_on_grading_error_column(tmp_path, monkeypatch) -> None:
    """
    AC-6 / MC-7 / ADR-050: The quiz_attempts table must not have a user_id column
    added by TASK-019 (the grading_error column is the only new addition).
    Negative: no user_id smuggled in alongside grading_error.
    """
    db_path = str(tmp_path / "no_user_id_attempts.db")
    _init_db(db_path, monkeypatch)
    cols = _get_table_columns(db_path, "quiz_attempts")
    assert "user_id" not in cols, (
        f"quiz_attempts table must NOT have a user_id column. MC-7 (ADR-050). "
        f"Columns found: {cols!r}"
    )


def test_get_grade_for_attempt_returns_none_for_grading_failed(
    tmp_path, monkeypatch
) -> None:
    """
    AC-3 / ADR-050: get_grade_for_attempt returns None for a grading_failed Attempt
    (no grades row was inserted on the failure path).
    Negative: no grade row on failure path → None returned.
    """
    db_path = str(tmp_path / "get_grade_failed.db")
    quiz_id, question_id = _bootstrap_and_create_quiz(db_path, monkeypatch)
    attempt_id = _create_submitted_attempt(db_path, quiz_id, question_id, monkeypatch)

    monkeypatch.setenv("NOTES_DB_PATH", db_path)
    from app.persistence import (  # noqa: PLC0415
        mark_attempt_grading,
        mark_attempt_grading_failed,
        get_grade_for_attempt,
    )
    mark_attempt_grading(attempt_id)
    mark_attempt_grading_failed(attempt_id, error="something went wrong")

    grade = get_grade_for_attempt(attempt_id)
    assert grade is None, (
        "get_grade_for_attempt must return None for a grading_failed Attempt "
        "(no grades row exists). ADR-050."
    )


def test_mc10_persistence_functions_re_exported_from_init(tmp_path, monkeypatch) -> None:
    """
    AC-3 / AC-6 / MC-10: all six new persistence functions are re-exported from
    app/persistence/__init__.py (the single-import surface per ADR-022).
    Negative: missing export would mean callers have to reach into quizzes.py directly
    (MC-10 violation).
    """
    _init_db(str(tmp_path / "init_check.db"), monkeypatch)
    import app.persistence as pers  # noqa: PLC0415

    required_exports = [
        "list_submitted_attempts",
        "mark_attempt_grading",
        "mark_attempt_graded",
        "mark_attempt_grading_failed",
        "save_attempt_grade",
        "get_grade_for_attempt",
    ]
    missing = [name for name in required_exports if not hasattr(pers, name)]
    assert not missing, (
        f"app.persistence must re-export: {missing}. "
        "ADR-050: all new functions re-exported from app/persistence/__init__.py (MC-10)."
    )


# ===========================================================================
# Performance: save_attempt_grade with many questions
# ===========================================================================


def test_save_attempt_grade_many_questions_within_budget(tmp_path, monkeypatch) -> None:
    """
    AC-3 / Performance: save_attempt_grade with 10 questions completes within 5s.

    Scale surface: the per-Question UPDATE loop; a naive implementation that
    does one SELECT+UPDATE per question in a separate transaction each time
    would be O(n) but with high constant; an O(n²) implementation (e.g.
    re-scanning attempt_questions per update) would be caught here.

    The budget of 5s is generous for a local SQLite round-trip — the goal is
    to catch runaway implementations, not to micro-benchmark.
    """
    db_path = str(tmp_path / "perf_grade.db")
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
    q_ids = []
    for i in range(10):
        conn.execute(
            "INSERT INTO questions (section_id, prompt, topics, test_suite, preamble) VALUES (?, ?, ?, ?, ?)",
            (
                f"{MANDATORY_CHAPTER_ID}#section-{MANDATORY_FIRST_SECTION}",
                f"Question {i + 1}",
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
        mark_attempt_grading,
        save_attempt_grade,
    )
    attempt = start_attempt(quiz_id)
    save_attempt_responses(attempt.attempt_id, {q: "class X: pass" for q in q_ids})
    for q in q_ids:
        save_attempt_test_result(attempt.attempt_id, q, passed=True, status="ran", output="ok")
    submit_attempt(attempt.attempt_id)
    mark_attempt_grading(attempt.attempt_id)

    start = time.monotonic()
    save_attempt_grade(
        attempt.attempt_id,
        per_question_explanations={q: f"Explanation {q}." for q in q_ids},
        weak_topics=[],
        recommended_sections=[],
    )
    elapsed = time.monotonic() - start

    assert elapsed < 5.0, (
        f"save_attempt_grade with 10 questions took {elapsed:.2f}s (budget: 5s). "
        "Possible O(n²) implementation or unbounded per-question round-trips."
    )
