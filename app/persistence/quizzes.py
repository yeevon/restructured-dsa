"""
app/persistence/quizzes — Quiz domain persistence.

ADR-033: SQL string literals for the Quiz domain live EXCLUSIVELY in this module.
Routes call the typed public functions below; they never receive a sqlite3.Connection
or raw row tuples.

ADR-033 §Table set:
  quizzes(quiz_id PK AUTOINCREMENT, section_id TEXT NOT NULL, status TEXT NOT NULL,
          created_at TEXT NOT NULL)
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
