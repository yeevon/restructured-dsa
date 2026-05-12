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

    ADR-033 §Table set:
      question_id INTEGER PRIMARY KEY AUTOINCREMENT
      section_id  TEXT NOT NULL  (the Section whose Question Bank this belongs to)
      prompt      TEXT NOT NULL  (the coding-task prompt)
      topics      list[str]     (split from the '|'-delimited column; [] when empty)
      created_at  TEXT NOT NULL  (ISO-8601 UTC)

    No choice/recall/describe columns (manifest §5/§7: every Question is a
    hands-on coding task). No user_id (MC-7).
    """

    question_id: int
    section_id: str
    prompt: str
    topics: list[str]
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
    """Convert a sqlite3.Row to a Question dataclass, splitting topics."""
    raw_topics = row["topics"] or ""
    topics = [t for t in raw_topics.split("|") if t]
    return Question(
        question_id=row["question_id"],
        section_id=row["section_id"],
        prompt=row["prompt"],
        topics=topics,
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

    ADR-036 §The orchestration boundary: for each item in `questions` (dicts with
    'prompt' and 'topics' keys, drawn from the workflow's GeneratedQuestion output):
      - INSERT INTO questions (section_id, prompt, topics, created_at)
        with section_id from the Quiz's section_id (MC-2 — exactly one Section)
        and topics '|'-joined (ADR-033 §Topic tags).
      - INSERT INTO quiz_questions (quiz_id, question_id, position) 1-based.
    All within one transaction.

    `questions` is a list of dicts: [{"prompt": str, "topics": list[str]}, ...].
    The caller is responsible for sanity-checking that questions is non-empty
    and each prompt is non-empty (ADR-037 §Decision).

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

            cursor = conn.execute(
                "INSERT INTO questions (section_id, prompt, topics, created_at) "
                "VALUES (?, ?, ?, ?)",
                (section_id, prompt, topics_str, now),
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
