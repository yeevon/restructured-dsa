"""
TASK-013: Quiz domain schema / persistence tests.

Tests derive from the Acceptance Criteria in
`design_docs/tasks/TASK-013-quiz-domain-model-and-per-section-quiz-surface.md`
and from the two Accepted ADRs:
  ADR-033 — Quiz domain schema: `quizzes`, `questions`, `quiz_questions`,
             `quiz_attempts`, `attempt_questions` under `app/persistence/quizzes.py`
             in `data/notes.db`. `quizzes.section_id TEXT NOT NULL`. No `user_id`
             on any table. `questions` has `prompt` + `topics` (pipe-delimited),
             NO choice/recall/describe columns. `quiz_questions` is many-to-many
             (a Question may appear in multiple Quizzes). `attempt_questions` carries
             `response`, `is_correct`, `explanation` (last two NULL until grading).
             Two TEXT status enums: `quizzes.status` ∈ {requested, generating, ready,
             generation_failed} and `quiz_attempts.status` ∈ {in_progress, submitted,
             grading, graded, grading_failed}. `CREATE TABLE IF NOT EXISTS` idempotent
             bootstrap. Public API: `request_quiz(section_id)`,
             `list_quizzes_for_chapter(chapter_id)`.
  ADR-034 — Per-Section Quiz surface placement: the route
             `POST /lecture/{chapter_id}/sections/{section_number}/quiz` validates
             the Section ID at the route handler (not in persistence).

Coverage matrix:
  Boundary:
    - test_quiz_schema_tables_exist_after_bootstrap: all five tables exist.
    - test_quiz_schema_bootstrap_idempotent: re-running bootstrap raises no error.
    - test_quizzes_status_enum_boundary_requested: status='requested' accepted.
    - test_quizzes_status_enum_boundary_generation_failed: failure state accepted.
    - test_quiz_attempts_status_enum_boundary_grading_failed: failure state accepted.
    - test_question_in_two_quizzes_same_section: a Question may belong to 2 Quizzes.
  Edge:
    - test_questions_table_has_no_choice_recall_describe_columns: zero non-coding cols.
    - test_no_user_id_on_any_quiz_domain_table: all five tables lack user_id.
    - test_quizzes_section_id_not_null_constraint: inserting NULL section_id fails.
    - test_attempt_questions_columns_include_response_is_correct_explanation: structure
      present and last two nullable.
    - test_questions_has_topics_column: topics column exists.
  Negative:
    - test_mc10_no_sqlite3_import_outside_persistence_package: grep boundary.
    - test_mc10_no_sql_literals_outside_persistence_package: grep boundary.
    - test_request_quiz_creates_requested_status_row: round-trip via public API.
    - test_list_quizzes_for_chapter_returns_dict: bulk accessor shape correct.
    - test_list_quizzes_for_chapter_empty_for_unknown_chapter: no rows → {}.
    - test_quizzes_section_id_is_not_null: verify NOT NULL DDL is enforced.
  Performance:
    - test_list_quizzes_for_chapter_many_rows_within_budget: 50 quiz rows query
      completes well within budget (catches O(n) → O(n²) regressions).

pytestmark registers all tests under task("TASK-013").
"""

from __future__ import annotations

import pathlib
import re
import sqlite3
import time

import pytest

pytestmark = pytest.mark.task("TASK-013")

REPO_ROOT = pathlib.Path(__file__).parent.parent

# ---------------------------------------------------------------------------
# Chapter / Section IDs from the corpus
# ---------------------------------------------------------------------------

MANDATORY_CHAPTER_ID = "ch-01-cpp-refresher"
OPTIONAL_CHAPTER_ID = "ch-07-heaps-and-treaps"

# A well-formed Section ID for ch-01-cpp-refresher section 1 (used in schema tests)
SECTION_ID_CH01_S1 = "ch-01-cpp-refresher#section-1-1"
SECTION_ID_CH01_S2 = "ch-01-cpp-refresher#section-1-2"

# ---------------------------------------------------------------------------
# Helpers — deferred imports so collection succeeds before implementation exists
# ---------------------------------------------------------------------------


def _make_client(monkeypatch, db_path: str):
    """
    Return a FastAPI TestClient pointing at an isolated test database.
    Deferred import so collection succeeds before the app exists.
    """
    monkeypatch.setenv("NOTES_DB_PATH", db_path)
    from fastapi.testclient import TestClient  # noqa: PLC0415
    from app.main import app  # noqa: PLC0415
    return TestClient(app)


def _bootstrap_db(db_path: str, monkeypatch) -> None:
    """
    Trigger schema bootstrap by creating a TestClient (which imports the app and
    runs init_schema at startup) and issuing one GET to ensure it is connected.
    """
    client = _make_client(monkeypatch, db_path)
    client.get(f"/lecture/{MANDATORY_CHAPTER_ID}")


def _get_table_columns(db_path: str, table: str) -> set[str]:
    """Return the set of column names for a table via PRAGMA table_info."""
    conn = sqlite3.connect(db_path)
    cur = conn.execute(f"PRAGMA table_info({table})")
    cols = {row[1] for row in cur.fetchall()}
    conn.close()
    return cols


def _get_all_tables(db_path: str) -> set[str]:
    """Return all table names in the database."""
    conn = sqlite3.connect(db_path)
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )
    tables = {row[0] for row in cur.fetchall()}
    conn.close()
    return tables


# ---------------------------------------------------------------------------
# AC-1 — Schema bootstrap: all five Quiz-domain tables exist and are idempotent
# Trace: TASK-013 AC-1; ADR-033 §Table set; ADR-022 §Migration story
# ---------------------------------------------------------------------------


def test_quiz_schema_tables_exist_after_bootstrap(tmp_path, monkeypatch) -> None:
    """
    AC-1 (TASK-013) / ADR-033: after schema bootstrap the five Quiz-domain tables
    must exist — `quizzes`, `questions`, `quiz_questions`, `quiz_attempts`,
    `attempt_questions`.

    ADR-033 §Table set names all five; ADR-022's migration story says they are
    created via CREATE TABLE IF NOT EXISTS appended to connection.py's _SCHEMA_SQL.

    Trace: AC-1; ADR-033 §Table set; ADR-022 §Migration story.
    """
    db_path = str(tmp_path / "quiz_schema.db")
    _bootstrap_db(db_path, monkeypatch)

    tables = _get_all_tables(db_path)

    required_tables = {
        "quizzes",
        "questions",
        "quiz_questions",
        "quiz_attempts",
        "attempt_questions",
    }
    missing = required_tables - tables
    assert not missing, (
        f"After schema bootstrap, the following Quiz-domain tables are missing: {missing!r}. "
        "AC-1/ADR-033 §Table set: all five tables must be created by bootstrap. "
        f"Tables found: {tables!r}."
    )


def test_quiz_schema_bootstrap_idempotent(tmp_path, monkeypatch) -> None:
    """
    AC-1 (TASK-013) / ADR-033 / ADR-022 §Migration story: re-running the schema
    bootstrap on the same database must not raise any error and must not create
    duplicate tables.

    ADR-022: 'CREATE TABLE IF NOT EXISTS … repeated calls are safe (idempotent).'
    This tests the 'no duplicate-table failure' requirement from AC-1.

    Trace: AC-1; ADR-022 §Migration story; ADR-033 §Schema bootstrap.
    """
    db_path = str(tmp_path / "idempotent.db")

    # First bootstrap
    _bootstrap_db(db_path, monkeypatch)

    # Directly invoke init_schema a second time — must not raise
    monkeypatch.setenv("NOTES_DB_PATH", db_path)
    try:
        from app.persistence import init_schema  # noqa: PLC0415
        init_schema()  # second call — idempotent
    except Exception as exc:
        pytest.fail(
            f"Re-running init_schema() on an already-bootstrapped database raised {exc!r}. "
            "AC-1/ADR-022: schema bootstrap must be idempotent (CREATE TABLE IF NOT EXISTS)."
        )

    # Table count must not have changed (no duplicate tables appear)
    tables = _get_all_tables(db_path)
    assert "quizzes" in tables, (
        "After second init_schema(), 'quizzes' table is gone — something went wrong."
    )


# ---------------------------------------------------------------------------
# AC-2 — `quizzes.section_id TEXT NOT NULL`, no Chapter-bound row
# Trace: TASK-013 AC-2; ADR-033 §Table set; MC-2; Manifest §6/§7
# ---------------------------------------------------------------------------


def test_quizzes_table_has_section_id_column(tmp_path, monkeypatch) -> None:
    """
    AC-2 (TASK-013) / ADR-033: the `quizzes` table must have a `section_id` column.

    ADR-033 §Table set: 'quizzes … section_id TEXT NOT NULL — full ADR-002 composite
    ID, e.g. "ch-03-...#section-3-2"'.

    Trace: AC-2; ADR-033 §Table set; MC-2 (Quiz scope to one Section).
    """
    db_path = str(tmp_path / "section_id.db")
    _bootstrap_db(db_path, monkeypatch)

    cols = _get_table_columns(db_path, "quizzes")
    assert "section_id" in cols, (
        f"The 'quizzes' table has no 'section_id' column. Columns: {cols!r}. "
        "AC-2/ADR-033: quizzes.section_id TEXT NOT NULL is the schema commitment "
        "that every Quiz references exactly one Section (MC-2 / Manifest §6/§7)."
    )


def test_quizzes_section_id_not_null_constraint(tmp_path, monkeypatch) -> None:
    """
    AC-2 (TASK-013) / ADR-033: `quizzes.section_id` must be declared NOT NULL.

    The constraint is verified by attempting a direct INSERT with section_id=NULL
    and asserting that SQLite raises an IntegrityError.

    Trace: AC-2; ADR-033 §Table set ('section_id TEXT NOT NULL'); MC-2.
    """
    db_path = str(tmp_path / "notnull.db")
    _bootstrap_db(db_path, monkeypatch)

    conn = sqlite3.connect(db_path)
    try:
        with pytest.raises(sqlite3.IntegrityError, match=r"(?i)NOT NULL"):
            conn.execute(
                "INSERT INTO quizzes (section_id, status, created_at) "
                "VALUES (NULL, 'requested', '2026-01-01T00:00:00Z')"
            )
            conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# AC-3 — No Quiz-domain table has a `user_id` column (MC-7)
# Trace: TASK-013 AC-3; ADR-033 §Decision ('No user_id anywhere'); MC-7
# ---------------------------------------------------------------------------


def test_no_user_id_on_any_quiz_domain_table(tmp_path, monkeypatch) -> None:
    """
    AC-3 (TASK-013) / MC-7 / ADR-033: no Quiz-domain table may have a `user_id`
    column.

    ADR-033: 'No `user_id` anywhere (manifest §5/§6 single-user posture).'
    MC-7 (architecture portion active per ADR-022): 'no user_id on any persisted
    entity'.

    Checks all five Quiz-domain tables.

    Trace: AC-3; ADR-033 §Decision; MC-7; Manifest §5 'No multi-user features'.
    """
    db_path = str(tmp_path / "no_user_id.db")
    _bootstrap_db(db_path, monkeypatch)

    quiz_tables = [
        "quizzes",
        "questions",
        "quiz_questions",
        "quiz_attempts",
        "attempt_questions",
    ]
    violations = []
    for table in quiz_tables:
        cols = _get_table_columns(db_path, table)
        if "user_id" in cols:
            violations.append(table)

    assert violations == [], (
        f"The following Quiz-domain tables have a 'user_id' column: {violations!r}. "
        "AC-3/MC-7: manifest §5/§6 (single user) and ADR-033 explicitly forbid "
        "a user_id column on any Quiz-domain table. No auth, no per-user partitioning."
    )


# ---------------------------------------------------------------------------
# AC-4 — `questions` table: coding-task prompt column + topics column, NO
#         choice/recall/describe columns
# Trace: TASK-013 AC-4; ADR-033 §Table set ('every Question is a coding task');
#         Manifest §5/§7
# ---------------------------------------------------------------------------


def test_questions_table_has_prompt_column(tmp_path, monkeypatch) -> None:
    """
    AC-4 (TASK-013) / ADR-033: the `questions` table must have a `prompt` column
    (the coding-task prompt).

    ADR-033: 'questions … prompt TEXT NOT NULL — the coding-task prompt
    (what to implement)'.

    Trace: AC-4; ADR-033 §Table set; Manifest §7 'Every Question is a
    hands-on coding task'.
    """
    db_path = str(tmp_path / "prompt_col.db")
    _bootstrap_db(db_path, monkeypatch)

    cols = _get_table_columns(db_path, "questions")
    assert "prompt" in cols, (
        f"The 'questions' table has no 'prompt' column. Columns: {cols!r}. "
        "AC-4/ADR-033: every Question is a hands-on coding task — the schema "
        "must carry a 'prompt' column for the coding-task description."
    )


def test_questions_has_topics_column(tmp_path, monkeypatch) -> None:
    """
    AC-4 (TASK-013) / ADR-033: the `questions` table must have a `topics` column.

    ADR-033 §Topic tags: 'questions.topics is a |-delimited string of Topic-tag
    names.' The column ships now; the relational form (question_topics join) is
    deferred to the generation task.

    Trace: AC-4; ADR-033 §Topic tags; Manifest §8 (Question has Topic tags).
    """
    db_path = str(tmp_path / "topics_col.db")
    _bootstrap_db(db_path, monkeypatch)

    cols = _get_table_columns(db_path, "questions")
    assert "topics" in cols, (
        f"The 'questions' table has no 'topics' column. Columns: {cols!r}. "
        "AC-4/ADR-033 §Topic tags: questions.topics TEXT (pipe-delimited tag list) "
        "must ship this task. The relational form is deferred to the generation task."
    )


def test_questions_table_has_no_choice_recall_describe_columns(
    tmp_path, monkeypatch
) -> None:
    """
    AC-4 (TASK-013) / ADR-033 / Manifest §5/§7: the `questions` table must NOT
    carry any choice / recall / describe column.

    ADR-033: 'NO choice/recall/describe columns' because 'every Question is a
    hands-on coding task' (Manifest §5/§7: 'No non-coding Question formats').

    Forbidden column name patterns (any column matching these substrings):
      option_, correct_choice, answer_text, describe_, recall_

    Trace: AC-4; ADR-033 §Table set ('no choice/recall/describe columns');
    Manifest §5 'No non-coding Question formats'; Manifest §7 'Every Question is
    a hands-on coding task'.
    """
    db_path = str(tmp_path / "no_choice_cols.db")
    _bootstrap_db(db_path, monkeypatch)

    cols = _get_table_columns(db_path, "questions")
    forbidden_patterns = [
        "option_",
        "correct_choice",
        "answer_text",
        "describe_",
        "recall_",
    ]
    violations = [
        col
        for col in cols
        if any(pat in col.lower() for pat in forbidden_patterns)
    ]

    assert violations == [], (
        f"The 'questions' table carries non-coding-task column(s): {violations!r}. "
        "AC-4/Manifest §5/§7: the schema must not admit non-coding Question formats. "
        "No option_*, correct_choice, answer_text, describe_*, or recall_* columns. "
        f"All columns found: {cols!r}."
    )


# ---------------------------------------------------------------------------
# AC-5 — A Question may appear in multiple Quizzes for its Section
#         (quiz_questions is a many-to-many join)
# Trace: TASK-013 AC-5; ADR-033 §Table set; Manifest §8 ('May appear in multiple
#         Quizzes for its Section over time')
# ---------------------------------------------------------------------------


def test_question_in_two_quizzes_same_section(tmp_path, monkeypatch) -> None:
    """
    AC-5 (TASK-013) / ADR-033: the `quiz_questions` join table must allow a single
    Question to appear in two distinct Quizzes for the same Section (many-to-many).

    ADR-033: 'quiz_questions … a Question MAY appear in multiple Quizzes for its
    Section over time (manifest §8) — this is a many-to-many join, NOT a quiz_id
    FK on questions.'

    Strategy: insert two Quiz rows and one Question row, then associate the Question
    with both Quizzes via quiz_questions — must not raise IntegrityError.

    Trace: AC-5; ADR-033 §Table set (quiz_questions join); Manifest §8 (Question
    'May appear in multiple Quizzes for its Section over time').
    """
    db_path = str(tmp_path / "multi_quiz.db")
    _bootstrap_db(db_path, monkeypatch)

    conn = sqlite3.connect(db_path)
    try:
        # Insert two Quiz rows for the same Section
        conn.execute(
            "INSERT INTO quizzes (section_id, status, created_at) "
            "VALUES (?, 'requested', '2026-01-01T00:00:00Z')",
            (SECTION_ID_CH01_S1,),
        )
        conn.execute(
            "INSERT INTO quizzes (section_id, status, created_at) "
            "VALUES (?, 'requested', '2026-01-01T00:00:01Z')",
            (SECTION_ID_CH01_S1,),
        )
        conn.commit()
        quiz_ids = [
            row[0] for row in conn.execute("SELECT quiz_id FROM quizzes").fetchall()
        ]
        assert len(quiz_ids) >= 2, "Expected at least two Quiz rows."

        # Insert one Question row for the same Section
        conn.execute(
            "INSERT INTO questions (section_id, prompt, topics, created_at) "
            "VALUES (?, 'Implement a hash table.', 'hashing', '2026-01-01T00:00:00Z')",
            (SECTION_ID_CH01_S1,),
        )
        conn.commit()
        question_id = conn.execute("SELECT question_id FROM questions").fetchone()[0]

        # Associate the Question with BOTH Quizzes — must not raise
        try:
            conn.execute(
                "INSERT INTO quiz_questions (quiz_id, question_id, position) "
                "VALUES (?, ?, 1)",
                (quiz_ids[0], question_id),
            )
            conn.execute(
                "INSERT INTO quiz_questions (quiz_id, question_id, position) "
                "VALUES (?, ?, 1)",
                (quiz_ids[1], question_id),
            )
            conn.commit()
        except sqlite3.IntegrityError as exc:
            pytest.fail(
                f"Inserting a Question into two Quizzes raised IntegrityError: {exc!r}. "
                "AC-5/ADR-033: quiz_questions is a many-to-many join (PK is "
                "(quiz_id, question_id)); a Question must be associable with multiple Quizzes."
            )

        # Verify both associations exist
        count = conn.execute(
            "SELECT COUNT(*) FROM quiz_questions WHERE question_id = ?",
            (question_id,),
        ).fetchone()[0]
        assert count == 2, (
            f"Expected 2 quiz_questions rows for question_id={question_id}, got {count}. "
            "AC-5: the many-to-many join must persist both associations."
        )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# AC-5 (continued) — `attempt_questions` structure: response / is_correct /
#                    explanation columns present, last two nullable until grading
# Trace: TASK-013 AC-5; ADR-033 §Table set (attempt_questions)
# ---------------------------------------------------------------------------


def test_attempt_questions_columns_include_response_is_correct_explanation(
    tmp_path, monkeypatch
) -> None:
    """
    AC-5 (TASK-013) / ADR-033: the `attempt_questions` table must carry columns
    `response`, `is_correct`, and `explanation`.

    ADR-033: 'attempt_questions carries … response … is_correct … explanation
    (per-Question grading explanation, NULL until graded).'

    This verifies the per-Question correctness structure ships now (rather than as
    a future alteration), so the loop's replay-composition can query it without a
    non-additive migration (MC-8).

    Trace: AC-5; ADR-033 §Table set (attempt_questions); MC-8 (loop not foreclosed).
    """
    db_path = str(tmp_path / "attempt_questions.db")
    _bootstrap_db(db_path, monkeypatch)

    cols = _get_table_columns(db_path, "attempt_questions")
    required = {"response", "is_correct", "explanation"}
    missing = required - cols
    assert not missing, (
        f"The 'attempt_questions' table is missing columns: {missing!r}. "
        f"All columns found: {cols!r}. "
        "AC-5/ADR-033: attempt_questions must carry response, is_correct, explanation "
        "so per-Question wrong-answer history exists for the replay loop (MC-8)."
    )


def test_attempt_questions_is_correct_and_explanation_nullable(
    tmp_path, monkeypatch
) -> None:
    """
    AC-5 (TASK-013) / ADR-033: `attempt_questions.is_correct` and `.explanation`
    must be nullable (NULL until grading completes).

    ADR-033: 'is_correct … NULL until graded … explanation … NULL until graded'.

    Strategy: insert a quiz_attempts row + an attempt_questions row with
    is_correct=NULL and explanation=NULL; must succeed without IntegrityError.

    Trace: AC-5; ADR-033 §Table set (attempt_questions columns).
    """
    db_path = str(tmp_path / "nullable_cols.db")
    _bootstrap_db(db_path, monkeypatch)

    conn = sqlite3.connect(db_path)
    try:
        # Seed: one Quiz + one Question
        conn.execute(
            "INSERT INTO quizzes (section_id, status, created_at) "
            "VALUES (?, 'ready', '2026-01-01T00:00:00Z')",
            (SECTION_ID_CH01_S1,),
        )
        conn.commit()
        quiz_id = conn.execute("SELECT quiz_id FROM quizzes").fetchone()[0]

        conn.execute(
            "INSERT INTO questions (section_id, prompt, topics, created_at) "
            "VALUES (?, 'Implement a stack.', '', '2026-01-01T00:00:00Z')",
            (SECTION_ID_CH01_S1,),
        )
        conn.commit()
        question_id = conn.execute("SELECT question_id FROM questions").fetchone()[0]

        # One attempt
        conn.execute(
            "INSERT INTO quiz_attempts (quiz_id, status, created_at) "
            "VALUES (?, 'in_progress', '2026-01-01T00:00:00Z')",
            (quiz_id,),
        )
        conn.commit()
        attempt_id = conn.execute("SELECT attempt_id FROM quiz_attempts").fetchone()[0]

        # Insert attempt_questions with NULL is_correct + NULL explanation
        try:
            conn.execute(
                "INSERT INTO attempt_questions "
                "(attempt_id, question_id, response, is_correct, explanation) "
                "VALUES (?, ?, NULL, NULL, NULL)",
                (attempt_id, question_id),
            )
            conn.commit()
        except sqlite3.IntegrityError as exc:
            pytest.fail(
                f"Inserting attempt_questions with NULL is_correct/explanation raised "
                f"IntegrityError: {exc!r}. "
                "AC-5/ADR-033: is_correct and explanation must be nullable until "
                "grading completes."
            )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# AC-5 — `quizzes.status` enum: accepts failure-state value 'generation_failed'
# AC-5 — `quiz_attempts.status` enum: accepts failure-state value 'grading_failed'
# Trace: TASK-013 AC-5; ADR-033 §Lifecycle enums; MC-5
# ---------------------------------------------------------------------------


def test_quizzes_status_enum_boundary_requested(tmp_path, monkeypatch) -> None:
    """
    ADR-033 §Lifecycle enums: `quizzes.status = 'requested'` must be accepted.

    Boundary: 'requested' is the initial state; the TASK-013 placeholder trigger
    creates rows in this state.

    Trace: AC-5; ADR-033 §Lifecycle enums ('requested' | 'generating' | 'ready' |
    'generation_failed').
    """
    db_path = str(tmp_path / "status_requested.db")
    _bootstrap_db(db_path, monkeypatch)

    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "INSERT INTO quizzes (section_id, status, created_at) "
            "VALUES (?, 'requested', '2026-01-01T00:00:00Z')",
            (SECTION_ID_CH01_S1,),
        )
        conn.commit()
        row = conn.execute("SELECT status FROM quizzes").fetchone()
        assert row is not None and row[0] == "requested", (
            "Inserted status='requested' into quizzes but could not read it back. "
            "ADR-033: 'requested' must be a valid status value for quizzes."
        )
    finally:
        conn.close()


def test_quizzes_status_enum_boundary_generation_failed(tmp_path, monkeypatch) -> None:
    """
    ADR-033 §Lifecycle enums: `quizzes.status = 'generation_failed'` must be
    accepted (the failure state that surfaces a generation failure to the learner).

    MC-5: 'AI failures are surfaced, never fabricated.' The schema must name the
    failure state so the generation task can write it rather than fabricating a Quiz.

    Trace: AC-5; ADR-033 §Lifecycle enums; MC-5.
    """
    db_path = str(tmp_path / "status_genfailed.db")
    _bootstrap_db(db_path, monkeypatch)

    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "INSERT INTO quizzes (section_id, status, created_at) "
            "VALUES (?, 'generation_failed', '2026-01-01T00:00:00Z')",
            (SECTION_ID_CH01_S1,),
        )
        conn.commit()
        row = conn.execute("SELECT status FROM quizzes").fetchone()
        assert row is not None and row[0] == "generation_failed", (
            "Inserted status='generation_failed' into quizzes but could not read it back. "
            "ADR-033/MC-5: 'generation_failed' must be a valid status — the schema must "
            "name the failure state so AI failures are surfaced, not fabricated."
        )
    finally:
        conn.close()


def test_quiz_attempts_status_enum_boundary_grading_failed(tmp_path, monkeypatch) -> None:
    """
    ADR-033 §Lifecycle enums: `quiz_attempts.status = 'grading_failed'` must be
    accepted (the failure state for the grading lifecycle).

    MC-5: grading failures must be surfaced as failures, not fabricated grades.

    Trace: AC-5; ADR-033 §Lifecycle enums ('grading_failed'); MC-5.
    """
    db_path = str(tmp_path / "status_gradefailed.db")
    _bootstrap_db(db_path, monkeypatch)

    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "INSERT INTO quizzes (section_id, status, created_at) "
            "VALUES (?, 'ready', '2026-01-01T00:00:00Z')",
            (SECTION_ID_CH01_S1,),
        )
        conn.commit()
        quiz_id = conn.execute("SELECT quiz_id FROM quizzes").fetchone()[0]

        conn.execute(
            "INSERT INTO quiz_attempts (quiz_id, status, created_at) "
            "VALUES (?, 'grading_failed', '2026-01-01T00:00:00Z')",
            (quiz_id,),
        )
        conn.commit()
        row = conn.execute("SELECT status FROM quiz_attempts").fetchone()
        assert row is not None and row[0] == "grading_failed", (
            "Inserted status='grading_failed' into quiz_attempts but could not read it back. "
            "ADR-033/MC-5: 'grading_failed' must be a valid quiz_attempts status — the "
            "schema must name the failure state so grading failures are surfaced."
        )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# AC-6 / MC-10 — `import sqlite3` and SQL literals only under app/persistence/
# Trace: TASK-013 AC-6; MC-10 (active per ADR-022); ADR-033 §Module path
# ---------------------------------------------------------------------------


def test_mc10_no_sqlite3_import_outside_persistence_package() -> None:
    """
    AC-6 (TASK-013) / MC-10: `import sqlite3` must appear ONLY in files under
    `app/persistence/`.

    ADR-022 §Package boundary: 'import sqlite3 may appear only in files under
    app/persistence/.' ADR-033 §Module path: the Quiz domain SQL lives in
    `app/persistence/quizzes.py`, which is inside the boundary.

    Grep strategy: scan all .py files under app/ OUTSIDE app/persistence/.
    Any match is a blocker-level MC-10 violation.

    Trace: AC-6; ADR-022 §Package boundary; ADR-033 §Module path; MC-10.
    """
    app_dir = REPO_ROOT / "app"
    persistence_dir = app_dir / "persistence"
    violations = []
    for py_file in app_dir.rglob("*.py"):
        try:
            py_file.relative_to(persistence_dir)
            continue  # inside app/persistence/ — allowed
        except ValueError:
            pass
        text = py_file.read_text(encoding="utf-8")
        if "import sqlite3" in text:
            violations.append(str(py_file))

    assert violations == [], (
        f"MC-10 BLOCKER: `import sqlite3` found outside `app/persistence/` "
        f"in: {violations!r}. "
        "ADR-022/ADR-033 §Package boundary: DB driver imports must be confined to "
        "app/persistence/. Routes, templates, quiz module consumers must never import "
        "sqlite3 directly."
    )


def test_mc10_no_sql_literals_outside_persistence_package() -> None:
    """
    AC-6 (TASK-013) / MC-10: SQL string literals must appear ONLY in files under
    `app/persistence/`.

    ADR-022/ADR-033 §Package boundary.

    Trace: AC-6; MC-10; ADR-022; ADR-033 §Module path.
    """
    app_dir = REPO_ROOT / "app"
    persistence_dir = app_dir / "persistence"

    sql_keywords_pattern = re.compile(
        r"""(?x)
        (?:"|')           # opening quote
        [^"']*            # any content
        (?:
            \bSELECT\b  |
            \bINSERT\b  |
            \bUPDATE\b  |
            \bDELETE\b  |
            \bCREATE\s+TABLE\b |
            \bBEGIN\b   |
            \bCOMMIT\b  |
            \bROLLBACK\b
        )
        [^"']*
        (?:"|')           # closing quote
        """,
    )

    violations = []
    for py_file in app_dir.rglob("*.py"):
        try:
            py_file.relative_to(persistence_dir)
            continue  # inside app/persistence/ — allowed
        except ValueError:
            pass
        text = py_file.read_text(encoding="utf-8")
        if sql_keywords_pattern.search(text):
            violations.append(str(py_file))

    assert violations == [], (
        f"MC-10 BLOCKER: SQL string literals found outside `app/persistence/` "
        f"in: {violations!r}. "
        "ADR-022/ADR-033 §Package boundary: SQL string literals must be confined to "
        "app/persistence/. Route handlers and templates must only call typed public "
        "functions (request_quiz, list_quizzes_for_chapter) — never embed SQL."
    )


# ---------------------------------------------------------------------------
# Public API round-trip — request_quiz() and list_quizzes_for_chapter()
# Trace: TASK-013 AC (request_quiz round-trip); ADR-033 §Module path §Public API
# ---------------------------------------------------------------------------


def test_request_quiz_creates_requested_status_row(tmp_path, monkeypatch) -> None:
    """
    ADR-033 §Public API: `request_quiz(section_id)` must insert one `quizzes` row
    with status='requested' and return it (as a Quiz dataclass/TypedDict).

    The returned object must have:
      - status == 'requested'
      - section_id == the value passed in
      - quiz_id is a positive integer

    This is the write path the TASK-013 placeholder trigger route calls.

    Trace: ADR-033 §Public API (`request_quiz`); ADR-034 §Quiz-trigger route.
    """
    db_path = str(tmp_path / "request_quiz.db")
    monkeypatch.setenv("NOTES_DB_PATH", db_path)

    # Trigger bootstrap first
    from fastapi.testclient import TestClient  # noqa: PLC0415
    from app.main import app  # noqa: PLC0415
    client = TestClient(app)
    client.get(f"/lecture/{MANDATORY_CHAPTER_ID}")

    from app.persistence import request_quiz  # noqa: PLC0415

    quiz = request_quiz(SECTION_ID_CH01_S1)

    assert quiz is not None, (
        "request_quiz() returned None. "
        "ADR-033 §Public API: must return a Quiz dataclass instance."
    )
    assert hasattr(quiz, "status"), (
        f"request_quiz() returned {quiz!r} with no 'status' attribute. "
        "ADR-033: must return a Quiz dataclass with a status field."
    )
    assert quiz.status == "requested", (
        f"request_quiz() created a row with status={quiz.status!r}; expected 'requested'. "
        "ADR-033 §Public API: request_quiz inserts a row with status='requested'."
    )
    assert hasattr(quiz, "section_id"), (
        f"request_quiz() returned {quiz!r} with no 'section_id' attribute."
    )
    assert quiz.section_id == SECTION_ID_CH01_S1, (
        f"request_quiz() stored section_id={quiz.section_id!r}; "
        f"expected {SECTION_ID_CH01_S1!r}. "
        "ADR-033: the section_id must be stored exactly as passed."
    )
    assert hasattr(quiz, "quiz_id") and isinstance(quiz.quiz_id, int) and quiz.quiz_id > 0, (
        f"request_quiz() returned a Quiz with quiz_id={getattr(quiz, 'quiz_id', None)!r}; "
        "expected a positive integer. "
        "ADR-033: quiz_id INTEGER PRIMARY KEY AUTOINCREMENT."
    )


def test_list_quizzes_for_chapter_returns_dict_with_section_id_key(
    tmp_path, monkeypatch
) -> None:
    """
    ADR-033 §Public API: `list_quizzes_for_chapter(chapter_id)` must return a
    dict keyed by section_id with lists of Quiz objects.

    After request_quiz(SECTION_ID_CH01_S1), the result must include that section_id.

    Trace: ADR-033 §Public API (`list_quizzes_for_chapter`); ADR-034 §render_chapter.
    """
    db_path = str(tmp_path / "list_chapter.db")
    monkeypatch.setenv("NOTES_DB_PATH", db_path)

    from fastapi.testclient import TestClient  # noqa: PLC0415
    from app.main import app  # noqa: PLC0415
    client = TestClient(app)
    client.get(f"/lecture/{MANDATORY_CHAPTER_ID}")

    from app.persistence import request_quiz, list_quizzes_for_chapter  # noqa: PLC0415

    request_quiz(SECTION_ID_CH01_S1)
    result = list_quizzes_for_chapter(MANDATORY_CHAPTER_ID)

    assert isinstance(result, dict), (
        f"list_quizzes_for_chapter() returned {type(result)!r}; expected dict. "
        "ADR-033 §Public API: returns {{section_id: [Quiz, ...]}} for each Section "
        "of the Chapter that has >=1 Quiz."
    )
    assert SECTION_ID_CH01_S1 in result, (
        f"list_quizzes_for_chapter({MANDATORY_CHAPTER_ID!r}) returned dict "
        f"without key {SECTION_ID_CH01_S1!r}. Keys: {list(result.keys())!r}. "
        "ADR-033: the bulk accessor must include sections that have >=1 Quiz."
    )
    quizzes = result[SECTION_ID_CH01_S1]
    assert isinstance(quizzes, list) and len(quizzes) >= 1, (
        f"list_quizzes_for_chapter()[SECTION_ID] = {quizzes!r}; expected list with "
        "at least one Quiz. "
        "ADR-033: each dict value is a list of Quiz objects."
    )
    assert quizzes[0].status == "requested", (
        f"The first Quiz in list_quizzes_for_chapter()[SECTION_ID] has "
        f"status={quizzes[0].status!r}; expected 'requested'. "
        "ADR-033: the Quiz created by request_quiz must be visible via the bulk accessor."
    )


def test_list_quizzes_for_chapter_empty_for_unknown_chapter(
    tmp_path, monkeypatch
) -> None:
    """
    ADR-033 §Public API: `list_quizzes_for_chapter(chapter_id)` must return an
    empty dict (or a dict with no entries) for a chapter_id with no Quiz rows.

    Negative: tests that the accessor handles the zero-Quizzes case cleanly
    (no crash, no leak of other chapters' quizzes).

    Trace: ADR-033 §Public API; ADR-034 §render_chapter (empty-state case).
    """
    db_path = str(tmp_path / "empty_chapter.db")
    monkeypatch.setenv("NOTES_DB_PATH", db_path)

    from fastapi.testclient import TestClient  # noqa: PLC0415
    from app.main import app  # noqa: PLC0415
    client = TestClient(app)
    client.get(f"/lecture/{MANDATORY_CHAPTER_ID}")

    from app.persistence import list_quizzes_for_chapter  # noqa: PLC0415

    result = list_quizzes_for_chapter("ch-99-does-not-exist")
    assert isinstance(result, dict), (
        f"list_quizzes_for_chapter() on unknown chapter returned {type(result)!r}; "
        "expected dict."
    )
    assert result == {}, (
        f"list_quizzes_for_chapter('ch-99-does-not-exist') returned {result!r}; "
        "expected {{}} (no Quiz rows for an unknown chapter). "
        "ADR-033: the bulk accessor must return an empty dict when no Quizzes exist "
        "for the chapter."
    )


def test_request_quiz_multiple_calls_create_multiple_rows(tmp_path, monkeypatch) -> None:
    """
    ADR-033: multiple calls to request_quiz(section_id) must create independent
    rows — the route can be called more than once (the user may click "Generate"
    again).

    Trace: ADR-033 §Public API; ADR-034 §Quiz-trigger route.
    """
    db_path = str(tmp_path / "multi_request.db")
    monkeypatch.setenv("NOTES_DB_PATH", db_path)

    from fastapi.testclient import TestClient  # noqa: PLC0415
    from app.main import app  # noqa: PLC0415
    client = TestClient(app)
    client.get(f"/lecture/{MANDATORY_CHAPTER_ID}")

    from app.persistence import request_quiz, list_quizzes_for_chapter  # noqa: PLC0415

    quiz1 = request_quiz(SECTION_ID_CH01_S1)
    quiz2 = request_quiz(SECTION_ID_CH01_S1)

    assert quiz1.quiz_id != quiz2.quiz_id, (
        f"Two calls to request_quiz() returned the same quiz_id={quiz1.quiz_id}. "
        "ADR-033: each call must insert a new row (AUTOINCREMENT primary key)."
    )

    result = list_quizzes_for_chapter(MANDATORY_CHAPTER_ID)
    section_quizzes = result.get(SECTION_ID_CH01_S1, [])
    assert len(section_quizzes) >= 2, (
        f"After two request_quiz() calls, list_quizzes_for_chapter returned "
        f"{len(section_quizzes)} Quiz(zes) for the Section; expected >=2. "
        "ADR-033: each call creates an independent Quiz row."
    )


# ---------------------------------------------------------------------------
# Performance — bulk accessor with many rows
# Trace: ADR-033 §Public API; ADR-034 §render_chapter (one query per request)
# ---------------------------------------------------------------------------


def test_list_quizzes_for_chapter_many_rows_within_budget(tmp_path, monkeypatch) -> None:
    """
    Performance: `list_quizzes_for_chapter(chapter_id)` with 50 Quiz rows across
    several Sections must complete within 5 seconds.

    ADR-034 §render_chapter: 'one bulk Quiz query per request, mirroring
    complete_section_ids / rail_notes_context.' The budget is generous (5 s) —
    the goal is to catch O(n²) regressions, not to micro-benchmark.

    Trace: ADR-033 §Public API; ADR-034 §render_chapter.
    """
    db_path = str(tmp_path / "perf.db")
    monkeypatch.setenv("NOTES_DB_PATH", db_path)

    from fastapi.testclient import TestClient  # noqa: PLC0415
    from app.main import app  # noqa: PLC0415
    client = TestClient(app)
    client.get(f"/lecture/{MANDATORY_CHAPTER_ID}")

    from app.persistence import request_quiz, list_quizzes_for_chapter  # noqa: PLC0415

    # Insert 50 Quiz rows spread across two section IDs
    for i in range(25):
        request_quiz(SECTION_ID_CH01_S1)
        request_quiz(SECTION_ID_CH01_S2)

    t0 = time.monotonic()
    result = list_quizzes_for_chapter(MANDATORY_CHAPTER_ID)
    elapsed = time.monotonic() - t0

    total_quizzes = sum(len(v) for v in result.values())
    assert total_quizzes >= 50, (
        f"After inserting 50 Quiz rows, list_quizzes_for_chapter returned only "
        f"{total_quizzes} rows. "
        "ADR-033: bulk accessor must return all rows for the chapter."
    )
    assert elapsed < 5.0, (
        f"list_quizzes_for_chapter with 50 rows took {elapsed:.2f}s (limit: 5s). "
        "ADR-034: the bulk accessor is a single query per render; 5s is generous. "
        "A slow result suggests O(n²) behavior."
    )
