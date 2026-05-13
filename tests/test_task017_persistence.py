"""
TASK-017: In-app test runner — persistence round-trip tests.

Tests derive from the Acceptance Criteria in
`design_docs/tasks/TASK-017-in-app-test-runner.md` (AC-5, AC-10)
and from ADR-044 (attempt_questions test-result persistence layer).

Coverage matrix:
  Boundary:
    - test_save_attempt_test_result_writes_all_four_columns:
        save_attempt_test_result(attempt_id, question_id, passed=True,
        status='ran', output='ok') → re-query via list_attempt_questions
        returns test_passed=True, test_status='ran', test_output='ok',
        test_run_at non-None.
    - test_save_attempt_test_result_passed_false:
        passed=False stored and retrieved correctly (INTEGER 0 → bool False).
    - test_save_attempt_test_result_passed_none_for_timed_out:
        passed=None, status='timed_out' stored and retrieved → test_passed
        is None, test_status='timed_out' (MC-5 — failure mode persisted
        distinctly, not conflated with pass/fail).
    - test_save_attempt_test_result_does_not_touch_is_correct_or_explanation:
        After save_attempt_test_result, is_correct and explanation on the
        attempt_questions row remain NULL (the grading slice sets those —
        ADR-044 §is_correct's source).
    - test_save_attempt_test_result_does_not_change_quiz_attempts_status:
        After save_attempt_test_result, quiz_attempts.status is still
        'in_progress' (running tests is a within-in_progress action).
    - test_get_question_returns_question_with_test_suite:
        get_question(question_id) returns the Question carrying its
        test_suite (ADR-044 §get_question / ADR-041's accessor deferral).
    - test_get_question_returns_none_for_unknown_id:
        get_question(<unknown id>) returns None.
    - test_list_attempt_questions_carries_test_suite_field:
        list_attempt_questions returns AttemptQuestion objects that each
        have a .test_suite attribute (may be None for legacy rows).
    - test_list_attempt_questions_carries_all_four_test_result_fields:
        After save_attempt_test_result, list_attempt_questions returns
        AttemptQuestion with all four test_* fields populated correctly.
    - test_attempt_question_fields_none_before_any_run:
        Before any save_attempt_test_result call, test_passed / test_status
        / test_output / test_run_at are all None.
  Edge:
    - test_save_attempt_test_result_no_op_for_unknown_pair:
        A (attempt_id, question_id) pair with no matching row → silent no-op
        (no exception, no row inserted — mirrors save_attempt_responses posture,
        ADR-044 §save_attempt_test_result).
    - test_save_attempt_test_result_overwrites_previous_result:
        Calling save_attempt_test_result twice on the same row → the second
        call wins (latest run semantics — ADR-044 §Denormalized columns).
    - test_save_attempt_test_result_persists_across_fresh_connection:
        After save_attempt_test_result, opening a new sqlite3.connect() and
        re-querying attempt_questions shows the persisted test_* values
        (manifest §7 — persists across sessions).
    - test_four_columns_exist_on_fresh_db:
        On a fresh DB (after bootstrap), PRAGMA table_info(attempt_questions)
        includes test_passed, test_status, test_output, test_run_at columns.
    - test_four_columns_added_on_existing_db_missing_them:
        On a DB that was created with the attempt_questions table but WITHOUT
        the four test_* columns, calling init_schema() (which runs
        _apply_additive_migrations) adds the columns (ADR-022 / ADR-044
        §Additive migration).
  Negative:
    - test_no_user_id_on_attempt_questions:
        attempt_questions has no user_id column (MC-7).
    - test_save_attempt_test_result_importable_from_persistence_init:
        save_attempt_test_result is re-exported from app.persistence.__init__
        (via __all__) — ADR-044 §Re-exports.
    - test_get_question_importable_from_persistence_init:
        get_question is re-exported from app.persistence.__init__ (via
        __all__) — ADR-044 §Re-exports.
    - test_mc10_no_sqlite3_outside_persistence_after_task017:
        No new import sqlite3 in app/main.py or app/sandbox.py (MC-10).
    - test_mc7_no_user_id_in_new_persistence_functions:
        The source of save_attempt_test_result and get_question (in
        app/persistence/quizzes.py) contains no 'user_id' string (MC-7).
  Performance:
    - test_save_attempt_test_result_for_many_questions_within_budget:
        Calling save_attempt_test_result for 20 questions in one Attempt
        completes within 5 s (catches O(n) regression on the UPDATE path).

ASSUMPTIONS:
  ASSUMPTION: `save_attempt_test_result(attempt_id, question_id, *, passed,
    status, output, run_at=None) -> None` is the new persistence function
    (ADR-044 §save_attempt_test_result). Keyword-only passed/status/output.

  ASSUMPTION: `get_question(question_id: int) -> Question | None` is the new
    accessor (ADR-044 §get_question).

  ASSUMPTION: The `AttemptQuestion` dataclass gains .test_suite, .test_passed,
    .test_status, .test_output, .test_run_at attributes (ADR-044 §AttemptQuestion).

  ASSUMPTION: The four new columns are added for existing DBs via
    _apply_additive_migrations via a PRAGMA table_info check, mirroring
    ADR-037's generation_error and ADR-041's test_suite precedents.

  ASSUMPTION: list_attempt_questions(attempt_id) carries the four test_*
    fields through in the returned AttemptQuestion objects.
"""

from __future__ import annotations

import pathlib
import re
import sqlite3
import time

import pytest

pytestmark = pytest.mark.task("TASK-017")

REPO_ROOT = pathlib.Path(__file__).parent.parent

# ---------------------------------------------------------------------------
# Corpus / section constants (reuse from TASK-015 patterns)
# ---------------------------------------------------------------------------

MANDATORY_CHAPTER_ID = "ch-01-cpp-refresher"
MANDATORY_SECTION_ID = "ch-01-cpp-refresher#section-1-1"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _bootstrap_db(monkeypatch, db_path: str):
    """Bootstrap the DB schema and return a FastAPI TestClient."""
    monkeypatch.setenv("NOTES_DB_PATH", db_path)
    from fastapi.testclient import TestClient  # noqa: PLC0415
    from app.main import app  # noqa: PLC0415

    client = TestClient(app)
    client.get(f"/lecture/{MANDATORY_CHAPTER_ID}")
    return client


def _seed_ready_quiz_with_test_suite(
    db_path: str,
    section_id: str,
    test_suite: str = "#include <cassert>\nint add(int,int);\nint main(){assert(add(2,3)==5);return 0;}\n",
) -> tuple[int, int]:
    """
    Insert a ready Quiz + 1 Question with a test_suite. Returns (quiz_id, question_id).
    """
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "INSERT INTO quizzes (section_id, status, created_at) "
            "VALUES (?, 'ready', '2026-05-12T00:00:00Z')",
            (section_id,),
        )
        conn.commit()
        quiz_id = conn.execute(
            "SELECT quiz_id FROM quizzes WHERE section_id=? ORDER BY quiz_id DESC LIMIT 1",
            (section_id,),
        ).fetchone()[0]

        conn.execute(
            "INSERT INTO questions (section_id, prompt, topics, test_suite, created_at) "
            "VALUES (?, 'Implement add(int,int)', 'coding', ?, '2026-05-12T00:00:00Z')",
            (section_id, test_suite),
        )
        conn.commit()
        question_id = conn.execute(
            "SELECT question_id FROM questions ORDER BY question_id DESC LIMIT 1"
        ).fetchone()[0]

        conn.execute(
            "INSERT INTO quiz_questions (quiz_id, question_id, position) VALUES (?, ?, 1)",
            (quiz_id, question_id),
        )
        conn.commit()
    finally:
        conn.close()
    return quiz_id, question_id


def _get_columns(db_path: str, table: str) -> set[str]:
    conn = sqlite3.connect(db_path)
    cur = conn.execute(f"PRAGMA table_info({table})")
    cols = {row[1] for row in cur.fetchall()}
    conn.close()
    return cols


def _raw_attempt_question_row(db_path: str, attempt_id: int, question_id: int) -> dict:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM attempt_questions WHERE attempt_id=? AND question_id=?",
        (attempt_id, question_id),
    ).fetchone()
    conn.close()
    return dict(row) if row else {}


def _raw_attempt_row(db_path: str, attempt_id: int) -> dict:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM quiz_attempts WHERE attempt_id=?", (attempt_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else {}


# ---------------------------------------------------------------------------
# AC-5 / ADR-044: save_attempt_test_result round-trips
# ---------------------------------------------------------------------------


def test_save_attempt_test_result_writes_all_four_columns(
    tmp_path, monkeypatch
) -> None:
    """
    AC-5 (TASK-017) / ADR-044: save_attempt_test_result writes test_passed,
    test_status, test_output, test_run_at on the attempt_questions row;
    list_attempt_questions after a fresh call returns them intact.
    """
    # AC: save_attempt_test_result persists all four test-result columns
    db_path = str(tmp_path / "test017_persist.db")
    _bootstrap_db(monkeypatch, db_path)
    quiz_id, question_id = _seed_ready_quiz_with_test_suite(db_path, MANDATORY_SECTION_ID)

    from app.persistence import start_attempt, save_attempt_test_result, list_attempt_questions  # noqa: PLC0415

    attempt = start_attempt(quiz_id)
    save_attempt_test_result(
        attempt.attempt_id,
        question_id,
        passed=True,
        status="ran",
        output="all assertions passed",
    )

    aq_list = list_attempt_questions(attempt.attempt_id)
    assert aq_list, "list_attempt_questions returned empty list after save_attempt_test_result."

    aq = aq_list[0]
    assert hasattr(aq, "test_passed"), (
        "AttemptQuestion has no .test_passed attribute; ADR-044: the dataclass must be extended."
    )
    assert aq.test_passed is True, (
        f"AttemptQuestion.test_passed={aq.test_passed!r}; expected True. "
        "ADR-044: passed=True stored as INTEGER 1, retrieved as bool True."
    )
    assert hasattr(aq, "test_status") and aq.test_status == "ran", (
        f"AttemptQuestion.test_status={getattr(aq, 'test_status', 'MISSING')!r}; expected 'ran'."
    )
    assert hasattr(aq, "test_output") and aq.test_output == "all assertions passed", (
        f"AttemptQuestion.test_output={getattr(aq, 'test_output', 'MISSING')!r}; "
        "expected 'all assertions passed'."
    )
    assert hasattr(aq, "test_run_at") and aq.test_run_at is not None, (
        f"AttemptQuestion.test_run_at={getattr(aq, 'test_run_at', 'MISSING')!r}; "
        "expected a non-None ISO timestamp."
    )


def test_save_attempt_test_result_passed_false(tmp_path, monkeypatch) -> None:
    """
    AC-5 (TASK-017) / ADR-044: passed=False is stored as INTEGER 0 and
    retrieved as bool False (not None, not 0).
    """
    # AC: passed=False stored and retrieved as bool False
    db_path = str(tmp_path / "test017_false.db")
    _bootstrap_db(monkeypatch, db_path)
    quiz_id, question_id = _seed_ready_quiz_with_test_suite(db_path, MANDATORY_SECTION_ID)

    from app.persistence import start_attempt, save_attempt_test_result, list_attempt_questions  # noqa: PLC0415

    attempt = start_attempt(quiz_id)
    save_attempt_test_result(
        attempt.attempt_id,
        question_id,
        passed=False,
        status="ran",
        output="assertion failed at line 5",
    )

    aq = list_attempt_questions(attempt.attempt_id)[0]
    assert aq.test_passed is False, (
        f"AttemptQuestion.test_passed={aq.test_passed!r}; expected False. "
        "ADR-044: passed=False stored as INTEGER 0, retrieved as bool False (not None, not 0)."
    )
    assert aq.test_status == "ran"


def test_save_attempt_test_result_passed_none_for_timed_out(
    tmp_path, monkeypatch
) -> None:
    """
    AC-5 (TASK-017) / ADR-044 / MC-5: passed=None with status='timed_out' →
    test_passed is None and test_status is 'timed_out' (the failure mode is
    persisted distinctly, not conflated with pass/fail).
    """
    # AC: save_attempt_test_result with passed=None, status='timed_out' → MC-5 spirit
    db_path = str(tmp_path / "test017_timeout.db")
    _bootstrap_db(monkeypatch, db_path)
    quiz_id, question_id = _seed_ready_quiz_with_test_suite(db_path, MANDATORY_SECTION_ID)

    from app.persistence import start_attempt, save_attempt_test_result, list_attempt_questions  # noqa: PLC0415

    attempt = start_attempt(quiz_id)
    save_attempt_test_result(
        attempt.attempt_id,
        question_id,
        passed=None,
        status="timed_out",
        output="the test run timed out",
    )

    aq = list_attempt_questions(attempt.attempt_id)[0]
    assert aq.test_passed is None, (
        f"AttemptQuestion.test_passed={aq.test_passed!r}; expected None for a timed-out run. "
        "ADR-044 / MC-5: the failure mode must be persisted distinctly from pass/fail."
    )
    assert aq.test_status == "timed_out", (
        f"AttemptQuestion.test_status={getattr(aq, 'test_status', 'MISSING')!r}; "
        "expected 'timed_out'. ADR-044: test_status carries the structured run status."
    )


def test_save_attempt_test_result_does_not_touch_is_correct_or_explanation(
    tmp_path, monkeypatch
) -> None:
    """
    AC-5 (TASK-017) / ADR-044 §is_correct's source: save_attempt_test_result must
    leave is_correct and explanation NULL. The grading slice sets those.
    """
    # AC: save_attempt_test_result does not set is_correct or explanation (ADR-044)
    db_path = str(tmp_path / "test017_iscorrect.db")
    _bootstrap_db(monkeypatch, db_path)
    quiz_id, question_id = _seed_ready_quiz_with_test_suite(db_path, MANDATORY_SECTION_ID)

    from app.persistence import start_attempt, save_attempt_test_result  # noqa: PLC0415

    attempt = start_attempt(quiz_id)
    save_attempt_test_result(
        attempt.attempt_id,
        question_id,
        passed=True,
        status="ran",
        output="ok",
    )

    row = _raw_attempt_question_row(db_path, attempt.attempt_id, question_id)
    assert row.get("is_correct") is None, (
        f"attempt_questions.is_correct={row.get('is_correct')!r} after save_attempt_test_result; "
        "expected NULL. ADR-044: is_correct is set by the grading slice, not the runner."
    )
    assert row.get("explanation") is None, (
        f"attempt_questions.explanation={row.get('explanation')!r} after save_attempt_test_result; "
        "expected NULL. ADR-044: explanation is set by the grading slice, not the runner."
    )


def test_save_attempt_test_result_does_not_change_quiz_attempts_status(
    tmp_path, monkeypatch
) -> None:
    """
    AC-5 (TASK-017) / ADR-044: save_attempt_test_result must not change
    quiz_attempts.status — running tests is a within-in_progress action.
    """
    # AC: save_attempt_test_result leaves quiz_attempts.status='in_progress' (ADR-043)
    db_path = str(tmp_path / "test017_status.db")
    _bootstrap_db(monkeypatch, db_path)
    quiz_id, question_id = _seed_ready_quiz_with_test_suite(db_path, MANDATORY_SECTION_ID)

    from app.persistence import start_attempt, save_attempt_test_result  # noqa: PLC0415

    attempt = start_attempt(quiz_id)
    save_attempt_test_result(
        attempt.attempt_id,
        question_id,
        passed=True,
        status="ran",
        output="ok",
    )

    row = _raw_attempt_row(db_path, attempt.attempt_id)
    assert row.get("status") == "in_progress", (
        f"quiz_attempts.status={row.get('status')!r} after save_attempt_test_result; "
        "expected 'in_progress'. ADR-043/ADR-044: running tests must not flip Attempt status."
    )


# ---------------------------------------------------------------------------
# AC-5 / ADR-044: get_question accessor
# ---------------------------------------------------------------------------


def test_get_question_returns_question_with_test_suite(tmp_path, monkeypatch) -> None:
    """
    AC-5 (TASK-017) / ADR-044 §get_question: get_question(question_id) returns the
    Question dataclass carrying its test_suite (ADR-041 §No new accessor: 'the runner
    slice adds one').
    """
    # AC: get_question returns Question with test_suite (ADR-044 §get_question)
    db_path = str(tmp_path / "test017_get_q.db")
    _bootstrap_db(monkeypatch, db_path)
    test_suite_val = "#include <cassert>\nint add(int,int);\nint main(){assert(add(1,2)==3);return 0;}\n"
    quiz_id, question_id = _seed_ready_quiz_with_test_suite(
        db_path, MANDATORY_SECTION_ID, test_suite=test_suite_val
    )

    from app.persistence import get_question  # noqa: PLC0415

    q = get_question(question_id)
    assert q is not None, (
        f"get_question({question_id}) returned None; expected a Question dataclass. "
        "ADR-044: get_question must return the Question for a known question_id."
    )
    assert hasattr(q, "test_suite"), (
        "Question dataclass has no .test_suite attribute; ADR-041: the Question carries test_suite."
    )
    assert q.test_suite == test_suite_val, (
        f"get_question returned test_suite={q.test_suite!r}; "
        f"expected {test_suite_val!r}. ADR-044: the accessor must return the stored test_suite."
    )
    assert hasattr(q, "question_id") and q.question_id == question_id, (
        "get_question returned Question with wrong question_id."
    )


def test_get_question_returns_none_for_unknown_id(tmp_path, monkeypatch) -> None:
    """
    AC-5 (TASK-017) / ADR-044: get_question(<unknown id>) returns None.
    """
    # AC: get_question returns None for unknown question_id
    db_path = str(tmp_path / "test017_get_q_none.db")
    _bootstrap_db(monkeypatch, db_path)

    from app.persistence import get_question  # noqa: PLC0415

    result = get_question(99999999)
    assert result is None, (
        f"get_question(99999999) returned {result!r}; expected None. "
        "ADR-044: get_question must return None for an unknown question_id."
    )


# ---------------------------------------------------------------------------
# AC-5 / ADR-044: list_attempt_questions carries test_suite + test_* fields
# ---------------------------------------------------------------------------


def test_list_attempt_questions_carries_test_suite_field(tmp_path, monkeypatch) -> None:
    """
    AC-5 (TASK-017) / ADR-044: list_attempt_questions returns AttemptQuestion objects
    with a .test_suite attribute (may be None for legacy rows — ADR-044 §AttemptQuestion).
    """
    # AC: list_attempt_questions carries .test_suite field on AttemptQuestion
    db_path = str(tmp_path / "test017_ats.db")
    _bootstrap_db(monkeypatch, db_path)
    quiz_id, question_id = _seed_ready_quiz_with_test_suite(db_path, MANDATORY_SECTION_ID)

    from app.persistence import start_attempt, list_attempt_questions  # noqa: PLC0415

    attempt = start_attempt(quiz_id)
    aq_list = list_attempt_questions(attempt.attempt_id)
    assert aq_list, "list_attempt_questions returned empty list."

    for aq in aq_list:
        assert hasattr(aq, "test_suite"), (
            f"AttemptQuestion {aq!r} has no .test_suite attribute; "
            "ADR-044: AttemptQuestion must be extended with .test_suite."
        )


def test_list_attempt_questions_carries_all_four_test_result_fields(
    tmp_path, monkeypatch
) -> None:
    """
    AC-5 (TASK-017) / ADR-044: after save_attempt_test_result, list_attempt_questions
    returns AttemptQuestion with all four test_* fields populated correctly.
    """
    # AC: list_attempt_questions carries all four test_* fields after a result is saved
    db_path = str(tmp_path / "test017_ats_full.db")
    _bootstrap_db(monkeypatch, db_path)
    quiz_id, question_id = _seed_ready_quiz_with_test_suite(db_path, MANDATORY_SECTION_ID)

    from app.persistence import start_attempt, save_attempt_test_result, list_attempt_questions  # noqa: PLC0415

    attempt = start_attempt(quiz_id)
    save_attempt_test_result(
        attempt.attempt_id,
        question_id,
        passed=True,
        status="ran",
        output="test output text",
    )

    aq_list = list_attempt_questions(attempt.attempt_id)
    aq = aq_list[0]

    for field in ("test_passed", "test_status", "test_output", "test_run_at"):
        assert hasattr(aq, field), (
            f"AttemptQuestion has no .{field} attribute; "
            f"ADR-044: the AttemptQuestion extension must include all four test_* fields."
        )

    assert aq.test_passed is True
    assert aq.test_status == "ran"
    assert aq.test_output == "test output text"
    assert aq.test_run_at is not None


def test_attempt_question_fields_none_before_any_run(tmp_path, monkeypatch) -> None:
    """
    AC-5 (TASK-017) / ADR-044: before any save_attempt_test_result call, the four
    test_* fields on AttemptQuestion are all None.
    """
    # AC: test_* fields are None before any run (NULL until first save_attempt_test_result)
    db_path = str(tmp_path / "test017_none_before.db")
    _bootstrap_db(monkeypatch, db_path)
    quiz_id, question_id = _seed_ready_quiz_with_test_suite(db_path, MANDATORY_SECTION_ID)

    from app.persistence import start_attempt, list_attempt_questions  # noqa: PLC0415

    attempt = start_attempt(quiz_id)
    aq_list = list_attempt_questions(attempt.attempt_id)
    aq = aq_list[0]

    for field in ("test_passed", "test_status", "test_output", "test_run_at"):
        val = getattr(aq, field, "MISSING")
        assert val is None, (
            f"AttemptQuestion.{field}={val!r} before any run; expected None. "
            "ADR-044: all four test_* columns are NULL until a run happens."
        )


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_save_attempt_test_result_no_op_for_unknown_pair(
    tmp_path, monkeypatch
) -> None:
    """
    Edge (TASK-017) / ADR-044: calling save_attempt_test_result with a
    (attempt_id, question_id) pair that has no matching row → silent no-op.
    No exception raised, no row inserted.
    """
    # AC: save_attempt_test_result is a silent no-op for an unknown (attempt_id, question_id)
    db_path = str(tmp_path / "test017_noop.db")
    _bootstrap_db(monkeypatch, db_path)

    from app.persistence import save_attempt_test_result  # noqa: PLC0415

    # Should not raise
    save_attempt_test_result(
        99999,
        88888,
        passed=True,
        status="ran",
        output="irrelevant",
    )
    # Verify no row was inserted
    conn = sqlite3.connect(db_path)
    count = conn.execute(
        "SELECT COUNT(*) FROM attempt_questions WHERE attempt_id=99999"
    ).fetchone()[0]
    conn.close()
    assert count == 0, (
        f"save_attempt_test_result with a non-existent (attempt_id, question_id) inserted "
        f"{count} row(s); expected 0. ADR-044: must be a silent no-op."
    )


def test_save_attempt_test_result_overwrites_previous_result(
    tmp_path, monkeypatch
) -> None:
    """
    Edge (TASK-017) / ADR-044: calling save_attempt_test_result twice on the same row
    → the second call wins (latest-run semantics — denormalized columns, not history).
    """
    # AC: second save_attempt_test_result overwrites the first (latest-run semantics)
    db_path = str(tmp_path / "test017_overwrite.db")
    _bootstrap_db(monkeypatch, db_path)
    quiz_id, question_id = _seed_ready_quiz_with_test_suite(db_path, MANDATORY_SECTION_ID)

    from app.persistence import start_attempt, save_attempt_test_result, list_attempt_questions  # noqa: PLC0415

    attempt = start_attempt(quiz_id)
    save_attempt_test_result(
        attempt.attempt_id, question_id, passed=False, status="ran", output="first run"
    )
    save_attempt_test_result(
        attempt.attempt_id, question_id, passed=True, status="ran", output="second run"
    )

    aq = list_attempt_questions(attempt.attempt_id)[0]
    assert aq.test_passed is True, (
        f"AttemptQuestion.test_passed={aq.test_passed!r} after two saves; expected True (second call wins). "
        "ADR-044 §Denormalized columns: the UPDATE overwrites; no history stored."
    )
    assert aq.test_output == "second run", (
        f"AttemptQuestion.test_output={aq.test_output!r}; expected 'second run' (second call wins)."
    )


def test_save_attempt_test_result_persists_across_fresh_connection(
    tmp_path, monkeypatch
) -> None:
    """
    Edge (TASK-017) / ADR-044 / manifest §7: after save_attempt_test_result, opening
    a new sqlite3.connect() and re-querying attempt_questions shows the persisted
    values (persists across sessions — manifest §7).
    """
    # AC: test result persists across a fresh DB connection (manifest §7)
    db_path = str(tmp_path / "test017_persist_cross.db")
    _bootstrap_db(monkeypatch, db_path)
    quiz_id, question_id = _seed_ready_quiz_with_test_suite(db_path, MANDATORY_SECTION_ID)

    from app.persistence import start_attempt, save_attempt_test_result  # noqa: PLC0415

    attempt = start_attempt(quiz_id)
    save_attempt_test_result(
        attempt.attempt_id,
        question_id,
        passed=True,
        status="ran",
        output="cross-connection check",
    )

    # Re-query via raw sqlite3 (a fresh connection — not the app's connection)
    row = _raw_attempt_question_row(db_path, attempt.attempt_id, question_id)
    assert row.get("test_passed") == 1, (
        f"Raw test_passed={row.get('test_passed')!r} after a fresh connection; expected 1. "
        "Manifest §7: the test result must persist across sessions."
    )
    assert row.get("test_status") == "ran"
    assert row.get("test_output") == "cross-connection check"
    assert row.get("test_run_at") is not None


# ---------------------------------------------------------------------------
# Additive migration tests
# ---------------------------------------------------------------------------


def test_four_columns_exist_on_fresh_db(tmp_path, monkeypatch) -> None:
    """
    AC-5 (TASK-017) / ADR-044 §Additive migration: on a fresh DB (after bootstrap),
    PRAGMA table_info(attempt_questions) includes the four new test_* columns.
    """
    # AC: four test_* columns exist on a fresh DB after schema bootstrap
    db_path = str(tmp_path / "test017_fresh.db")
    _bootstrap_db(monkeypatch, db_path)

    cols = _get_columns(db_path, "attempt_questions")
    for col in ("test_passed", "test_status", "test_output", "test_run_at"):
        assert col in cols, (
            f"attempt_questions is missing column '{col}' on a fresh DB. "
            "ADR-044 / ADR-022: the CREATE TABLE block must declare all four columns."
        )


def test_four_columns_added_on_existing_db_missing_them(tmp_path, monkeypatch) -> None:
    """
    AC-5 (TASK-017) / ADR-044 §Additive migration / ADR-022: on a DB that was created
    with attempt_questions but WITHOUT the four test_* columns, init_schema (which
    runs _apply_additive_migrations) adds them — additive, no data loss.
    """
    # AC: additive migration adds four columns to an existing DB that lacks them (ADR-022)
    db_path = str(tmp_path / "test017_migration.db")

    # Simulate a pre-TASK-017 DB: create tables manually with the OLD schema
    # (no test_* columns on attempt_questions).
    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS quizzes (
            quiz_id INTEGER PRIMARY KEY AUTOINCREMENT,
            section_id TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'requested',
            created_at TEXT NOT NULL,
            generation_error TEXT
        );
        CREATE TABLE IF NOT EXISTS questions (
            question_id INTEGER PRIMARY KEY AUTOINCREMENT,
            section_id TEXT NOT NULL,
            prompt TEXT NOT NULL,
            topics TEXT NOT NULL DEFAULT '',
            test_suite TEXT,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS quiz_questions (
            quiz_id INTEGER NOT NULL,
            question_id INTEGER NOT NULL,
            position INTEGER NOT NULL,
            PRIMARY KEY (quiz_id, question_id)
        );
        CREATE TABLE IF NOT EXISTS quiz_attempts (
            attempt_id INTEGER PRIMARY KEY AUTOINCREMENT,
            quiz_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'in_progress',
            created_at TEXT NOT NULL,
            submitted_at TEXT,
            graded_at TEXT
        );
        CREATE TABLE IF NOT EXISTS attempt_questions (
            attempt_id INTEGER NOT NULL,
            question_id INTEGER NOT NULL,
            response TEXT,
            is_correct INTEGER,
            explanation TEXT,
            PRIMARY KEY (attempt_id, question_id)
        );
    """)
    conn.close()

    # Confirm old columns before migration
    cols_before = _get_columns(db_path, "attempt_questions")
    for col in ("test_passed", "test_status", "test_output", "test_run_at"):
        assert col not in cols_before, (
            f"Pre-migration DB unexpectedly already has column '{col}' — test setup is wrong."
        )

    # Now bootstrap via the app — this should run _apply_additive_migrations
    monkeypatch.setenv("NOTES_DB_PATH", db_path)
    from app.persistence.connection import init_schema  # noqa: PLC0415
    init_schema()

    cols_after = _get_columns(db_path, "attempt_questions")
    for col in ("test_passed", "test_status", "test_output", "test_run_at"):
        assert col in cols_after, (
            f"attempt_questions is missing column '{col}' after additive migration. "
            "ADR-044 / ADR-022: _apply_additive_migrations must add the four test_* columns "
            "to an existing DB that lacks them."
        )


# ---------------------------------------------------------------------------
# Negative / MC-7 / MC-10 boundary
# ---------------------------------------------------------------------------


def test_no_user_id_on_attempt_questions(tmp_path, monkeypatch) -> None:
    """
    Negative / MC-7 (TASK-017) / ADR-044: attempt_questions must have no user_id
    column. The single-user invariant must not be violated.
    """
    # AC: attempt_questions has no user_id column (MC-7)
    db_path = str(tmp_path / "test017_no_userid.db")
    _bootstrap_db(monkeypatch, db_path)

    cols = _get_columns(db_path, "attempt_questions")
    assert "user_id" not in cols, (
        "attempt_questions has a 'user_id' column; MC-7 / ADR-044: the single-user "
        "invariant forbids user_id on any new column."
    )


def test_save_attempt_test_result_importable_from_persistence_init() -> None:
    """
    Negative (TASK-017) / ADR-044 §Re-exports: save_attempt_test_result must be
    importable from app.persistence (re-exported via __init__.py).
    """
    # AC: save_attempt_test_result is exported from app.persistence (ADR-044)
    from app import persistence  # noqa: PLC0415

    assert hasattr(persistence, "save_attempt_test_result"), (
        "app.persistence has no 'save_attempt_test_result' attribute; "
        "ADR-044: the function must be re-exported from app/persistence/__init__.py."
    )
    assert "save_attempt_test_result" in getattr(persistence, "__all__", []), (
        "'save_attempt_test_result' not in app.persistence.__all__; "
        "ADR-044: the function must be listed in __all__ for the MC-10 import contract."
    )


def test_get_question_importable_from_persistence_init() -> None:
    """
    Negative (TASK-017) / ADR-044 §Re-exports: get_question must be importable
    from app.persistence (re-exported via __init__.py).
    """
    # AC: get_question is exported from app.persistence (ADR-044)
    from app import persistence  # noqa: PLC0415

    assert hasattr(persistence, "get_question"), (
        "app.persistence has no 'get_question' attribute; "
        "ADR-044: get_question must be re-exported from app/persistence/__init__.py."
    )
    assert "get_question" in getattr(persistence, "__all__", []), (
        "'get_question' not in app.persistence.__all__; "
        "ADR-044: get_question must be in __all__ for the MC-10 import contract."
    )


def test_mc10_no_sqlite3_outside_persistence_after_task017() -> None:
    """
    Negative / MC-10 (TASK-017) / ADR-044 / ADR-042: app/sandbox.py and any
    new route code in app/main.py must not import sqlite3 (SQL belongs only
    under app/persistence/).
    """
    # AC: no new import sqlite3 in app/sandbox.py (MC-10)
    sandbox_path = REPO_ROOT / "app" / "sandbox.py"
    if sandbox_path.exists():
        source = sandbox_path.read_text(encoding="utf-8")
        assert "import sqlite3" not in source, (
            "app/sandbox.py contains 'import sqlite3'; MC-10: SQL/DB access belongs only "
            "under app/persistence/."
        )


def test_mc7_no_user_id_in_new_persistence_functions() -> None:
    """
    Negative / MC-7 (TASK-017) / ADR-044: app/persistence/quizzes.py must not
    have 'user_id' as an SQL column or Python field name added by TASK-017.
    Existing comment text 'No user_id (MC-7)' in docstrings is acceptable.
    The schema-level check (test_no_user_id_on_attempt_questions) is the primary
    guard; this grep catches any accidental code-level introduction.
    """
    # AC: no user_id SQL column or Python field introduced by TASK-017 (MC-7)
    quizzes_path = REPO_ROOT / "app" / "persistence" / "quizzes.py"
    if not quizzes_path.exists():
        pytest.fail("app/persistence/quizzes.py does not exist.")
    source = quizzes_path.read_text(encoding="utf-8")
    # Check for user_id appearing as a code token (e.g. in a dataclass field,
    # SQL column, or function parameter) on non-comment lines.
    # Lines whose first non-whitespace chars are '#' are comments and are OK
    # (the existing quizzes.py already has "No user_id (MC-7)" in comments).
    code_lines_with_user_id = []
    for line in source.splitlines():
        stripped = line.lstrip()
        if "user_id" not in stripped:
            continue
        if stripped.startswith("#"):
            continue  # comment line — OK
        # Also skip docstring lines (content between triple-quote blocks)
        # A simple heuristic: if the only occurrence is inside a quoted string
        # that mentions it negatively, skip. But for safety just flag it.
        code_lines_with_user_id.append(line)
    # Filter further: we only care about lines that introduce user_id as a
    # column/field name in SQL or Python code (not in string literals that
    # document its absence).
    real_violations = [
        ln for ln in code_lines_with_user_id
        if re.search(r"user_id\s*=|user_id\s*,|user_id\s*\)|user_id\s*TEXT|user_id\s*INTEGER", ln)
    ]
    assert not real_violations, (
        "app/persistence/quizzes.py introduces 'user_id' as a column/field:\n"
        + "\n".join(f"  {ln!r}" for ln in real_violations)
        + "\nMC-7 / ADR-044: no user_id column, field, or parameter is allowed."
    )


# ---------------------------------------------------------------------------
# Performance
# ---------------------------------------------------------------------------


def test_save_attempt_test_result_for_many_questions_within_budget(
    tmp_path, monkeypatch
) -> None:
    """
    Performance (TASK-017) / ADR-044: calling save_attempt_test_result for 20
    Questions in one Attempt must complete within 5 s (catches O(n) regression
    on the UPDATE path).
    """
    # Performance: save_attempt_test_result for 20 questions within 5 s
    N = 20
    db_path = str(tmp_path / "test017_perf.db")
    _bootstrap_db(monkeypatch, db_path)

    # Seed a Quiz with N questions, each with a test_suite
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "INSERT INTO quizzes (section_id, status, created_at) "
            "VALUES (?, 'ready', '2026-05-12T00:00:00Z')",
            (MANDATORY_SECTION_ID,),
        )
        conn.commit()
        quiz_id = conn.execute(
            "SELECT quiz_id FROM quizzes WHERE section_id=? ORDER BY quiz_id DESC LIMIT 1",
            (MANDATORY_SECTION_ID,),
        ).fetchone()[0]

        question_ids = []
        for pos in range(1, N + 1):
            conn.execute(
                "INSERT INTO questions (section_id, prompt, topics, test_suite, created_at) "
                "VALUES (?, ?, 'coding', '#include <cassert>', '2026-05-12T00:00:00Z')",
                (MANDATORY_SECTION_ID, f"Implement function #{pos}"),
            )
            conn.commit()
            qid = conn.execute(
                "SELECT question_id FROM questions ORDER BY question_id DESC LIMIT 1"
            ).fetchone()[0]
            conn.execute(
                "INSERT INTO quiz_questions (quiz_id, question_id, position) VALUES (?, ?, ?)",
                (quiz_id, qid, pos),
            )
            conn.commit()
            question_ids.append(qid)
    finally:
        conn.close()

    from app.persistence import start_attempt, save_attempt_test_result  # noqa: PLC0415

    attempt = start_attempt(quiz_id)

    t0 = time.monotonic()
    for qid in question_ids:
        save_attempt_test_result(
            attempt.attempt_id,
            qid,
            passed=True,
            status="ran",
            output=f"output for question {qid}",
        )
    elapsed = time.monotonic() - t0

    assert elapsed <= 5.0, (
        f"save_attempt_test_result for {N} questions took {elapsed:.2f}s; "
        f"expected ≤ 5 s. This catches O(n²) or per-call-connection regressions."
    )
