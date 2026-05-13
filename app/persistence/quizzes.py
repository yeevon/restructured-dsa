"""
app/persistence/quizzes — Quiz domain persistence.

ADR-033: SQL string literals for the Quiz domain live EXCLUSIVELY in this module.
Routes call the typed public functions below; they never receive a sqlite3.Connection
or raw row tuples.

ADR-033 §Table set:
  quizzes(quiz_id PK AUTOINCREMENT, section_id TEXT NOT NULL, status TEXT NOT NULL,
          created_at TEXT NOT NULL, generation_error TEXT nullable)
  questions(question_id PK AUTOINCREMENT, section_id TEXT NOT NULL, prompt TEXT NOT NULL,
            topics TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL)
  quiz_questions(quiz_id, question_id, position — many-to-many join; PK on pair)
  quiz_attempts(attempt_id PK AUTOINCREMENT, quiz_id FK, status TEXT NOT NULL,
                created_at TEXT NOT NULL, submitted_at TEXT nullable,
                graded_at TEXT nullable)
  attempt_questions(attempt_id, question_id, response TEXT nullable,
                    is_correct INTEGER nullable, explanation TEXT nullable;
                    PK on pair)

ADR-033 §Lifecycle enums:
  quizzes.status:        'requested' | 'generating' | 'ready' | 'generation_failed'
  quiz_attempts.status:  'in_progress' | 'submitted' | 'grading' | 'graded' | 'grading_failed'

ADR-033 §Topic tags:
  questions.topics is a '|'-delimited string; exposed as list[str] to callers.

ADR-033 §Public API (TASK-013 must-ship subset):
  - Quiz          — dataclass for a single quizzes row
  - Question      — dataclass for a single questions row
  - request_quiz(section_id) -> Quiz
  - list_quizzes_for_section(section_id) -> list[Quiz]
  - list_quizzes_for_chapter(chapter_id) -> dict[str, list[Quiz]]

ADR-036 / ADR-037 §Public API additions (TASK-014):
  - mark_quiz_generating(quiz_id) -> None
  - mark_quiz_ready(quiz_id) -> None
  - mark_quiz_generation_failed(quiz_id, error=None) -> None
  - add_questions_to_quiz(quiz_id, questions) -> None
  - list_requested_quizzes() -> list[Quiz]
  - get_quiz(quiz_id) -> Quiz | None
  - section_has_nonfailed_quiz(section_id) -> bool

MC-7: No user_id on any Quiz-domain table.
MC-10: import sqlite3 and all SQL literals live ONLY in this module (and connection.py).
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass

from app.persistence.connection import get_connection


# ---------------------------------------------------------------------------
# Dataclasses — one per row type exposed in the public API
# ---------------------------------------------------------------------------


@dataclass
class Quiz:
    """
    A single quizzes row.

    ADR-033 §Table set:
      quiz_id    INTEGER PRIMARY KEY AUTOINCREMENT
      section_id TEXT NOT NULL  (full ADR-002 composite ID, e.g. "ch-03#section-3-2")
      status     TEXT NOT NULL  ('requested' | 'generating' | 'ready' | 'generation_failed')
      created_at TEXT NOT NULL  (ISO-8601 UTC)

    No user_id (ADR-033 / MC-7 / manifest §5/§6 single-user).
    """

    quiz_id: int
    section_id: str
    status: str
    created_at: str


@dataclass
class Question:
    """
    A single questions row (Question Bank entry for a Section).

    ADR-033 §Table set (extended by ADR-041, further extended by ADR-046):
      question_id INTEGER PRIMARY KEY AUTOINCREMENT
      section_id  TEXT NOT NULL  (the Section whose Question Bank this belongs to)
      prompt      TEXT NOT NULL  (the coding-task prompt)
      topics      list[str]     (split from the '|'-delimited column; [] when empty)
      test_suite  str | None    (runnable test source code — ADR-040/ADR-041;
                                 NULL only for a Question that predates TASK-016;
                                 every Question persisted from TASK-016 forward
                                 always has a non-empty test_suite)
      preamble    str | None    (shared struct/class/header shapes — ADR-045/ADR-046;
                                 NULL only for a Question that predates TASK-018;
                                 "" = TASK-018+ Question that needs no shared shapes
                                 (a real and valid semantic per ADR-045);
                                 non-empty = the shared-shapes source)
      created_at  TEXT NOT NULL  (ISO-8601 UTC)

    No choice/recall/describe columns (manifest §5/§7: every Question is a
    hands-on coding task). No user_id (MC-7).
    """

    question_id: int
    section_id: str
    prompt: str
    topics: list[str]
    test_suite: str | None
    preamble: str | None
    created_at: str


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _utc_now_iso() -> str:
    """
    Return the current UTC time as an ISO-8601 string with microsecond precision.

    Duplicates notes.py / section_completions.py's _utc_now_iso() deliberately —
    ADR-033 §Module path: 'two implementations of a 2-line function is not a real
    DRY violation.'
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z"


def _row_to_quiz(row: object) -> Quiz:
    """Convert a sqlite3.Row (or dict-like) to a Quiz dataclass."""
    return Quiz(
        quiz_id=row["quiz_id"],
        section_id=row["section_id"],
        status=row["status"],
        created_at=row["created_at"],
    )


def _row_to_question(row: object) -> Question:
    """Convert a sqlite3.Row to a Question dataclass, splitting topics.

    ADR-041: the row→dataclass converter carries test_suite through.
    ADR-046: the converter also carries preamble through.
    row["test_suite"] yields None for a NULL column (a legacy row) — matching
    the str | None type on the Question dataclass.
    row["preamble"] yields None for a NULL column (a pre-TASK-018 row) — matching
    the str | None type on the Question dataclass.
    """
    raw_topics = row["topics"] or ""
    topics = [t for t in raw_topics.split("|") if t]
    return Question(
        question_id=row["question_id"],
        section_id=row["section_id"],
        prompt=row["prompt"],
        topics=topics,
        test_suite=row["test_suite"],
        preamble=row["preamble"],
        created_at=row["created_at"],
    )


# ---------------------------------------------------------------------------
# Public API — TASK-013 must-ship subset (ADR-033 §Public API)
# ---------------------------------------------------------------------------


def request_quiz(section_id: str) -> Quiz:
    """
    Insert a quizzes row with status='requested' and return it as a Quiz.

    ADR-033 §The `requested` status:
      - Inserts one quizzes row, status='requested', created_at=<now>.
      - NO quiz_questions rows (no Questions yet — generation is the next task).
      - NO quiz_attempts row.
      - No AI call (MC-1); no background job (MC-9); nothing fabricated (MC-5).
      - section_id validation is the route handler's job (ADR-034 / ADR-024
        validation split); this function trusts the caller.

    SQL lives here — not in the caller (ADR-022 / ADR-033 §Package boundary / MC-10).
    """
    now = _utc_now_iso()
    conn = get_connection()
    try:
        cursor = conn.execute(
            "INSERT INTO quizzes (section_id, status, created_at) "
            "VALUES (?, 'requested', ?)",
            (section_id, now),
        )
        conn.commit()
        quiz_id = cursor.lastrowid
        row = conn.execute(
            "SELECT quiz_id, section_id, status, created_at "
            "FROM quizzes WHERE quiz_id = ?",
            (quiz_id,),
        ).fetchone()
    finally:
        conn.close()

    return _row_to_quiz(row)


def list_quizzes_for_section(section_id: str) -> list[Quiz]:
    """
    Return all Quiz rows for a Section, most-recent-first.

    ADR-033 §Public API: 'SELECT * FROM quizzes WHERE section_id = ?
    ORDER BY created_at DESC.'

    SQL lives here — not in the caller (ADR-022 / ADR-033 §Package boundary / MC-10).
    """
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT quiz_id, section_id, status, created_at "
            "FROM quizzes WHERE section_id = ? "
            "ORDER BY created_at DESC",
            (section_id,),
        ).fetchall()
    finally:
        conn.close()

    return [_row_to_quiz(row) for row in rows]


def list_quizzes_for_chapter(chapter_id: str) -> dict[str, list[Quiz]]:
    """
    Bulk accessor: return {section_id: [Quiz, ...]} for every Section of the
    Chapter that has >=1 Quiz.

    ADR-033 §Public API: 'mirrors count_complete_sections_per_chapter() /
    list_complete_section_ids_for_chapter() so render_chapter does one query
    per request, not one per Section.'

    Implementation: matches on the 'chapter_id#%' prefix of section_id (the
    ADR-002 composite ID form). Sections with no Quizzes are not in the returned
    dict — callers default missing keys to [] (empty-state).

    SQL lives here — not in the caller (ADR-022 / ADR-033 §Package boundary / MC-10).
    """
    prefix = f"{chapter_id}#%"
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT quiz_id, section_id, status, created_at "
            "FROM quizzes WHERE section_id LIKE ? "
            "ORDER BY section_id, created_at DESC",
            (prefix,),
        ).fetchall()
    finally:
        conn.close()

    result: dict[str, list[Quiz]] = {}
    for row in rows:
        quiz = _row_to_quiz(row)
        result.setdefault(quiz.section_id, []).append(quiz)
    return result


# ---------------------------------------------------------------------------
# Public API — TASK-014 additions (ADR-036 / ADR-037)
# ---------------------------------------------------------------------------


def mark_quiz_generating(quiz_id: int) -> None:
    """
    Transition a Quiz from 'requested' to 'generating'.

    ADR-037 §Decision: the processor calls this before invoking the workflow.
    SQL lives here (MC-10).
    """
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE quizzes SET status = 'generating' WHERE quiz_id = ?",
            (quiz_id,),
        )
        conn.commit()
    finally:
        conn.close()


def mark_quiz_ready(quiz_id: int) -> None:
    """
    Transition a Quiz to 'ready' after successful generation.

    ADR-037 §Decision: the processor calls this after add_questions_to_quiz succeeds.
    SQL lives here (MC-10).
    """
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE quizzes SET status = 'ready' WHERE quiz_id = ?",
            (quiz_id,),
        )
        conn.commit()
    finally:
        conn.close()


def mark_quiz_generation_failed(quiz_id: int, error: str | None = None) -> None:
    """
    Transition a Quiz to 'generation_failed' and persist the optional error detail.

    ADR-037 §Failure-handling discipline: the error string (from aiw run's stderr)
    is written to the nullable quizzes.generation_error column (additive column per
    ADR-022 migration story; ADR-037). The learner-facing signal is "Generation failed"
    (ADR-034); the error column is a debugging aid only.

    MC-5: no fabricated Questions; the failure is persisted honestly.
    SQL lives here (MC-10).
    """
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE quizzes SET status = 'generation_failed', generation_error = ? "
            "WHERE quiz_id = ?",
            (error, quiz_id),
        )
        conn.commit()
    finally:
        conn.close()


def add_questions_to_quiz(
    quiz_id: int,
    questions: list[dict],
) -> None:
    """
    Persist generated Questions to the Section's Question Bank and link them to
    the Quiz via quiz_questions rows.

    ADR-036 §The orchestration boundary (extended by ADR-041): for each item in
    `questions` (dicts with 'prompt', 'topics', and 'test_suite' keys, drawn from
    the workflow's GeneratedQuestion output — ADR-040/ADR-041):
      - INSERT INTO questions (section_id, prompt, topics, test_suite, created_at)
        with section_id from the Quiz's section_id (MC-2 — exactly one Section),
        topics '|'-joined (ADR-033 §Topic tags), and test_suite from q["test_suite"].
      - INSERT INTO quiz_questions (quiz_id, question_id, position) 1-based.
    All within one transaction.

    `questions` is a list of dicts:
      [{"prompt": str, "topics": list[str], "test_suite": str}, ...].
    The caller is responsible for sanity-checking that questions is non-empty,
    each prompt is non-empty (ADR-037 §Decision), and each test_suite is
    non-empty (ADR-040 §Bad-test-suite failure handling — the processor performs
    a whole-Quiz check before calling this function).

    MC-2: every Question carries the same section_id as the Quiz.
    MC-10: SQL stays here.
    No user_id (MC-7).
    """
    # Fetch the Quiz's section_id (MC-2: Questions must carry the Quiz's section_id)
    conn = get_connection()
    try:
        quiz_row = conn.execute(
            "SELECT section_id FROM quizzes WHERE quiz_id = ?",
            (quiz_id,),
        ).fetchone()
        if quiz_row is None:
            raise ValueError(f"Quiz {quiz_id} not found")

        section_id = quiz_row["section_id"]
        now = _utc_now_iso()

        for position, q in enumerate(questions, start=1):
            prompt = q["prompt"]
            topics_list = q.get("topics", [])
            topics_str = "|".join(topics_list) if topics_list else ""
            test_suite = q["test_suite"]
            preamble = q.get("preamble", "")

            cursor = conn.execute(
                "INSERT INTO questions (section_id, prompt, topics, test_suite, preamble, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (section_id, prompt, topics_str, test_suite, preamble, now),
            )
            question_id = cursor.lastrowid

            conn.execute(
                "INSERT INTO quiz_questions (quiz_id, question_id, position) "
                "VALUES (?, ?, ?)",
                (quiz_id, question_id, position),
            )

        conn.commit()
    finally:
        conn.close()


def list_requested_quizzes() -> list[Quiz]:
    """
    Return all Quiz rows with status='requested', ordered by created_at ASC
    (oldest first — FIFO processing order).

    ADR-037 §Decision: the processor queries this to find work to do.
    SQL lives here (MC-10).
    """
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT quiz_id, section_id, status, created_at "
            "FROM quizzes WHERE status = 'requested' "
            "ORDER BY created_at ASC",
        ).fetchall()
    finally:
        conn.close()

    return [_row_to_quiz(row) for row in rows]


def get_quiz(quiz_id: int) -> Quiz | None:
    """
    Return a single Quiz by quiz_id, or None if not found.

    ADR-036 §The orchestration boundary: the processor reads the Quiz's section_id
    and current status. SQL lives here (MC-10).
    """
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT quiz_id, section_id, status, created_at "
            "FROM quizzes WHERE quiz_id = ?",
            (quiz_id,),
        ).fetchone()
    finally:
        conn.close()

    return _row_to_quiz(row) if row is not None else None


# ---------------------------------------------------------------------------
# Public API — TASK-015 additions (ADR-038 / ADR-039)
# ---------------------------------------------------------------------------


@dataclass
class QuizAttempt:
    """
    A single quiz_attempts row (a Quiz Attempt, manifest §8).

    ADR-039 §The QuizAttempt dataclass:
      attempt_id   INTEGER PRIMARY KEY AUTOINCREMENT
      quiz_id      INTEGER NOT NULL (FK → quizzes)
      status       TEXT NOT NULL  ('in_progress' | 'submitted' | 'grading' |
                                   'graded' | 'grading_failed' — ADR-033)
      created_at   TEXT NOT NULL  (ISO-8601 UTC)
      submitted_at TEXT nullable  (NULL until submitted)
      graded_at    TEXT nullable  (NULL until graded — Grade aggregate ships
                                   with the grading slice)

    No user_id (ADR-033 / MC-7 / manifest §5/§6 single-user).
    """

    attempt_id: int
    quiz_id: int
    status: str
    created_at: str
    submitted_at: str | None
    graded_at: str | None


@dataclass
class AttemptQuestion:
    """
    One Question's state within an Attempt — a convenience join of
    attempt_questions + the Question's prompt + quiz_questions.position.

    ADR-039 §The AttemptQuestion dataclass (extended by ADR-044, further by ADR-046):
      question_id  INTEGER  (FK → questions)
      prompt       TEXT     (the Question's coding-task prompt, from questions)
      response     TEXT | None  (the learner's code; NULL until submitted)
      position     INTEGER  (1-based order within the Quiz, from quiz_questions)
      test_suite   str | None  (the Question's runnable test source — ADR-041/ADR-044;
                               NULL for legacy rows predating TASK-016)
      preamble     str | None  (shared struct/class/header shapes — ADR-045/ADR-046;
                               NULL for legacy rows predating TASK-018;
                               "" = TASK-018+ Question that needs no shared shapes;
                               non-empty = shared-shapes source)

    ADR-044 §The AttemptQuestion dataclass: four test-result fields added:
      test_passed   bool | None  (True/False/None; None until first run or on failure)
      test_status   str | None   ('ran'|'timed_out'|'compile_error'|'setup_error'; None until run)
      test_output   str | None   (combined output / diagnostic; None until run)
      test_run_at   str | None   (ISO-8601 UTC timestamp of latest run; None until run)

    The take template iterates these in position order to render each
    Question's prompt + a code field + test suite + results panel.
    No is_correct / explanation this slice (NULL until grading — ADR-039).
    No user_id (MC-7).
    """

    question_id: int
    prompt: str
    response: str | None
    position: int
    test_suite: str | None = None
    preamble: str | None = None
    test_passed: bool | None = None
    test_status: str | None = None
    test_output: str | None = None
    test_run_at: str | None = None


def _row_to_quiz_attempt(row: object) -> QuizAttempt:
    """Convert a sqlite3.Row to a QuizAttempt dataclass."""
    return QuizAttempt(
        attempt_id=row["attempt_id"],
        quiz_id=row["quiz_id"],
        status=row["status"],
        created_at=row["created_at"],
        submitted_at=row["submitted_at"],
        graded_at=row["graded_at"],
    )


def _row_to_attempt_question(row: object) -> AttemptQuestion:
    """Convert a sqlite3.Row to an AttemptQuestion dataclass.

    ADR-044 §AttemptQuestion: carries test_suite + four test_* fields through.
    ADR-046: also carries preamble through via the questions join.
    test_passed: INTEGER 1/0/NULL → bool True/False/None (sqlite3 maps int→int;
    we convert explicitly to bool|None).
    """
    raw_passed = row["test_passed"]
    if raw_passed is None:
        test_passed = None
    else:
        test_passed = bool(raw_passed)

    return AttemptQuestion(
        question_id=row["question_id"],
        prompt=row["prompt"],
        response=row["response"],
        position=row["position"],
        test_suite=row["test_suite"],
        preamble=row["preamble"],
        test_passed=test_passed,
        test_status=row["test_status"],
        test_output=row["test_output"],
        test_run_at=row["test_run_at"],
    )


def start_attempt(quiz_id: int) -> QuizAttempt:
    """
    Start (or resume) a Quiz Attempt for a `ready` Quiz.

    ADR-039 §start_attempt:
    - If the Quiz already has an `in_progress` Attempt, reuse the latest one
      (by attempt_id DESC) — no second quiz_attempts row from an idle reload.
    - Otherwise INSERT a quiz_attempts row (status='in_progress', created_at=<now>,
      submitted_at/graded_at NULL), then INSERT one attempt_questions row per
      Question in the Quiz (response/is_correct/explanation all NULL), ordered by
      quiz_questions.position. All in one transaction.
    - Trusts the caller: quiz_id is a real `ready` Quiz (the route validated it
      via get_quiz). Does not re-validate the Quiz's status.
    - No user_id (MC-7). SQL stays here (MC-10).

    Returns the QuizAttempt (the reused or newly-created one).
    """
    conn = get_connection()
    try:
        # Check for an existing in_progress Attempt for this Quiz (ADR-039 §reuse)
        existing = conn.execute(
            "SELECT attempt_id, quiz_id, status, created_at, submitted_at, graded_at "
            "FROM quiz_attempts "
            "WHERE quiz_id = ? AND status = 'in_progress' "
            "ORDER BY attempt_id DESC LIMIT 1",
            (quiz_id,),
        ).fetchone()

        if existing is not None:
            return _row_to_quiz_attempt(existing)

        # No in_progress Attempt — create one. All in one transaction.
        now = _utc_now_iso()
        cursor = conn.execute(
            "INSERT INTO quiz_attempts (quiz_id, status, created_at) "
            "VALUES (?, 'in_progress', ?)",
            (quiz_id, now),
        )
        attempt_id = cursor.lastrowid

        # INSERT one attempt_questions row per Question in the Quiz (ADR-039
        # §attempt_questions rows at start; response/is_correct/explanation NULL).
        question_rows = conn.execute(
            "SELECT question_id FROM quiz_questions "
            "WHERE quiz_id = ? ORDER BY position",
            (quiz_id,),
        ).fetchall()

        for qrow in question_rows:
            conn.execute(
                "INSERT INTO attempt_questions (attempt_id, question_id) "
                "VALUES (?, ?)",
                (attempt_id, qrow["question_id"]),
            )

        conn.commit()

        # Re-fetch the freshly-inserted row to return a clean dataclass
        row = conn.execute(
            "SELECT attempt_id, quiz_id, status, created_at, submitted_at, graded_at "
            "FROM quiz_attempts WHERE attempt_id = ?",
            (attempt_id,),
        ).fetchone()
    finally:
        conn.close()

    return _row_to_quiz_attempt(row)


def get_attempt(attempt_id: int) -> QuizAttempt | None:
    """
    Return a single Attempt by attempt_id, or None if not found.

    ADR-039 §get_attempt.
    SQL stays here (MC-10).
    """
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT attempt_id, quiz_id, status, created_at, submitted_at, graded_at "
            "FROM quiz_attempts WHERE attempt_id = ?",
            (attempt_id,),
        ).fetchone()
    finally:
        conn.close()

    return _row_to_quiz_attempt(row) if row is not None else None


def get_latest_attempt_for_quiz(quiz_id: int) -> QuizAttempt | None:
    """
    Return the most recent Quiz Attempt for a Quiz (any status), or None if none exist.

    ADR-038 §GET .../take: after the PRG redirect, the GET handler uses this to find
    a `submitted` Attempt (so it can render the "Submitted — grading not yet available"
    state without calling `start_attempt`, which would create a new `in_progress` row).

    Returns the Attempt with the highest attempt_id for quiz_id, regardless of status.
    Returns None if no Attempts exist for the Quiz.

    SQL stays here (MC-10). No user_id (MC-7).
    """
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT attempt_id, quiz_id, status, created_at, submitted_at, graded_at "
            "FROM quiz_attempts WHERE quiz_id = ? "
            "ORDER BY attempt_id DESC LIMIT 1",
            (quiz_id,),
        ).fetchone()
    finally:
        conn.close()

    return _row_to_quiz_attempt(row) if row is not None else None


def list_questions_for_quiz(quiz_id: int) -> list[Question]:
    """
    Return the Questions composing a Quiz, ordered by quiz_questions.position.

    ADR-039 §list_questions_for_quiz: a join of quiz_questions ⨝ questions;
    returns Question dataclasses (topics split to list[str], per ADR-033).
    SQL stays here (MC-10).
    """
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT q.question_id, q.section_id, q.prompt, q.topics, "
            "q.test_suite, q.preamble, q.created_at "
            "FROM quiz_questions qq "
            "JOIN questions q ON qq.question_id = q.question_id "
            "WHERE qq.quiz_id = ? "
            "ORDER BY qq.position",
            (quiz_id,),
        ).fetchall()
    finally:
        conn.close()

    return [_row_to_question(row) for row in rows]


def list_attempt_questions(attempt_id: int) -> list[AttemptQuestion]:
    """
    Return the per-Question state of an Attempt — one AttemptQuestion per
    attempt_questions row, joined with the Question's prompt and
    quiz_questions.position, ordered by position.

    ADR-039 §list_attempt_questions: this is what the take template iterates.
    ADR-044: also SELECTs q.test_suite + the four aq.test_* columns so the
    take template can show the read-only test-suite block and results panel.
    Returns [] for an unknown attempt_id or an Attempt with no rows.
    SQL stays here (MC-10).
    """
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT aq.question_id, q.prompt, aq.response, qq.position, "
            "q.test_suite, q.preamble, aq.test_passed, aq.test_status, aq.test_output, aq.test_run_at "
            "FROM attempt_questions aq "
            "JOIN questions q ON aq.question_id = q.question_id "
            "JOIN quiz_questions qq ON aq.question_id = qq.question_id "
            "JOIN quiz_attempts qa ON aq.attempt_id = qa.attempt_id "
            "WHERE aq.attempt_id = ? AND qq.quiz_id = qa.quiz_id "
            "ORDER BY qq.position",
            (attempt_id,),
        ).fetchall()
    finally:
        conn.close()

    return [_row_to_attempt_question(row) for row in rows]


def save_attempt_responses(attempt_id: int, responses: dict[int, str]) -> None:
    """
    Write the learner's code for each Question in an Attempt.

    ADR-039 §save_attempt_responses:
    `responses` maps question_id → code-string. For each (question_id, code)
    in responses: UPDATE attempt_questions SET response = ? WHERE attempt_id = ?
    AND question_id = ?  — i.e. updates existing rows (created at Attempt start).
    A question_id not present in the Attempt's rows is ignored (no stray INSERT —
    defensive, since the route built `responses` from the Attempt's own rows).
    Stored response is the code verbatim (no transformation).
    Does NOT change the Attempt's status — submit_attempt does that.
    All in one transaction.
    No user_id (MC-7). SQL stays here (MC-10).
    """
    if not responses:
        return

    conn = get_connection()
    try:
        for question_id, code in responses.items():
            conn.execute(
                "UPDATE attempt_questions SET response = ? "
                "WHERE attempt_id = ? AND question_id = ?",
                (code, attempt_id, question_id),
            )
        conn.commit()
    finally:
        conn.close()


def submit_attempt(attempt_id: int) -> None:
    """
    Submit an Attempt: flip quiz_attempts.status → 'submitted', set submitted_at.

    ADR-039 §submit_attempt:
    Does NOT touch attempt_questions, does NOT touch is_correct/explanation,
    does NOT invoke grading (MC-4 — grading is a later out-of-band slice).
    Idempotent-ish: submitting an already-submitted Attempt is a harmless
    UPDATE (the route resolves the latest in_progress Attempt before calling).
    No user_id (MC-7). SQL stays here (MC-10).
    """
    now = _utc_now_iso()
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE quiz_attempts SET status = 'submitted', submitted_at = ? "
            "WHERE attempt_id = ?",
            (now, attempt_id),
        )
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Public API — TASK-017 additions (ADR-042 / ADR-043 / ADR-044)
# ---------------------------------------------------------------------------


def get_question(question_id: int) -> "Question | None":
    """
    Return a single Question by question_id, or None if not found.

    ADR-044 §The runner-slice accessor: the "Run tests" route (ADR-043) calls
    this to fetch the target Question's test_suite to feed the sandbox
    (ADR-042).  The whole Question is returned (not a narrower accessor) because
    the Question dataclass already exists with the right shape and the grading
    slice will also want a Question by id — ADR-041 §No new accessor:
    "the runner slice adds one."

    SELECT question_id, section_id, prompt, topics, test_suite, created_at
    FROM questions WHERE question_id = ?

    Returns None for an unknown question_id.
    SQL stays here (MC-10).  No user_id (MC-7).
    """
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT question_id, section_id, prompt, topics, test_suite, preamble, created_at "
            "FROM questions WHERE question_id = ?",
            (question_id,),
        ).fetchone()
    finally:
        conn.close()

    return _row_to_question(row) if row is not None else None


def save_attempt_test_result(
    attempt_id: int,
    question_id: int,
    *,
    passed: "bool | None",
    status: str,
    output: str,
    run_at: "str | None" = None,
) -> None:
    """
    Write the test-run result for one Question in an Attempt.

    ADR-044 §The writer:
    UPDATE attempt_questions SET test_passed=?, test_status=?, test_output=?,
    test_run_at=? WHERE attempt_id=? AND question_id=?

    A (attempt_id, question_id) pair with no matching row is a silent no-op
    (defensive — mirrors save_attempt_responses's ignore-unknown-question_id
    posture; the route built the call from the Attempt's own rows).

    Does NOT touch response, is_correct, explanation, or quiz_attempts.status —
    running tests is a within-in_progress action (ADR-043 / ADR-044).

    passed:  Python True/False/None → SQLite INTEGER 1/0/NULL
             (sqlite3 converts bool→int natively; None → NULL natively)
    run_at:  when None, filled by _utc_now_iso() (same pattern as start_attempt)

    SQL stays here (MC-10).  No user_id (MC-7).
    """
    now = run_at if run_at is not None else _utc_now_iso()
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE attempt_questions "
            "SET test_passed = ?, test_status = ?, test_output = ?, test_run_at = ? "
            "WHERE attempt_id = ? AND question_id = ?",
            (passed, status, output, now, attempt_id, question_id),
        )
        conn.commit()
    finally:
        conn.close()


def section_has_nonfailed_quiz(section_id: str) -> bool:
    """
    Return True if the Section already has a Quiz with status in
    {'requested', 'generating', 'ready'} (i.e. a non-failed Quiz).

    ADR-037 §The first-Quiz-only guard: the POST .../quiz route checks this
    before inserting a new requested row. A generation_failed Quiz does NOT
    count — the author can re-click Generate after a failure (ADR-037).

    MC-8: this guard prevents a fresh-only post-first Quiz from being produced.
    SQL lives here (MC-10).
    """
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM quizzes "
            "WHERE section_id = ? AND status IN ('requested', 'generating', 'ready')",
            (section_id,),
        ).fetchone()
    finally:
        conn.close()

    return row[0] > 0
