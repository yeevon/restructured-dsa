"""
app/persistence/section_completions — SectionCompletion entity persistence.

ADR-024: SQL string literals for the section_completions entity live EXCLUSIVELY
in this module. Routes call the typed public functions below; they never receive
a sqlite3.Connection or raw row tuples.

ADR-024 §Schema: section_completions(section_id PK, chapter_id, completed_at)
  - Presence ≡ complete: a row exists iff the Section is complete.
  - Unmarking deletes the row (INSERT OR IGNORE for mark; DELETE for unmark).
  - No user_id column (MC-7 / manifest §5/§6/§7 single-user).

Public API:
  - SectionCompletion         — dataclass describing a section_completions row
  - mark_section_complete(section_id, chapter_id) -> SectionCompletion
  - unmark_section_complete(section_id) -> None
  - is_section_complete(section_id) -> bool
  - list_complete_section_ids_for_chapter(chapter_id) -> list[str]
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass

from app.persistence.connection import get_connection


@dataclass
class SectionCompletion:
    """
    A single persisted section_completions row.

    ADR-024 §Schema:
      section_id   TEXT PRIMARY KEY  (full ADR-002 composite ID, e.g. "ch-01#section-1-1")
      chapter_id   TEXT NOT NULL     (redundant but indexed for per-chapter queries)
      completed_at TEXT NOT NULL     (ISO-8601 UTC timestamp)
    No user_id (MC-7 / ADR-024 §Schema).
    """

    section_id: str
    chapter_id: str
    completed_at: str


def _utc_now_iso() -> str:
    r"""
    Return the current UTC time as an ISO-8601 string with microsecond precision.

    ADR-024 §completed_at: 'ISO-8601 UTC timestamp string, written by the
    persistence layer at mark-complete time (not by the caller).'

    Duplicates notes.py's _utc_now_iso() deliberately — ADR-024 §Future-minor-refactor:
    'two implementations of a 2-line function is not a real DRY violation.'
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z"


def mark_section_complete(section_id: str, chapter_id: str) -> SectionCompletion:
    """
    Insert a section_completions row and return the resulting SectionCompletion.

    ADR-024: 'mark_section_complete is implemented as INSERT OR IGNORE so calling
    it on an already-complete Section is a no-op rather than an error.'

    ADR-024: 'mark_section_complete returns the dataclass so callers (and tests)
    can assert on the returned completed_at without a follow-up read.'

    SQL lives here — not in the caller (ADR-022 / ADR-024 §Package boundary).
    """
    now = _utc_now_iso()
    conn = get_connection()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO section_completions (section_id, chapter_id, completed_at) "
            "VALUES (?, ?, ?)",
            (section_id, chapter_id, now),
        )
        conn.commit()
        # If INSERT OR IGNORE was a no-op (row already exists), read back the
        # existing completed_at so the returned dataclass is accurate.
        cursor = conn.execute(
            "SELECT section_id, chapter_id, completed_at "
            "FROM section_completions WHERE section_id = ?",
            (section_id,),
        )
        row = cursor.fetchone()
    finally:
        conn.close()

    # row is always non-None here: either we just inserted or it already existed.
    return SectionCompletion(
        section_id=row["section_id"],
        chapter_id=row["chapter_id"],
        completed_at=row["completed_at"],
    )


def unmark_section_complete(section_id: str) -> None:
    """
    Delete the section_completions row for the given section_id.

    ADR-024: 'unmark_section_complete() deletes the row. Idempotent — unmarking
    an already-unmarked Section is a no-op (no error).'

    ADR-024 §Presence-as-complete: absence of a row ≡ Section is incomplete.

    SQL lives here — not in the caller (ADR-022 / ADR-024 §Package boundary).
    """
    conn = get_connection()
    try:
        conn.execute(
            "DELETE FROM section_completions WHERE section_id = ?",
            (section_id,),
        )
        conn.commit()
    finally:
        conn.close()


def is_section_complete(section_id: str) -> bool:
    """
    Return True iff a row exists in section_completions for the given section_id.

    ADR-024: 'is_section_complete returns bool for the per-Section template check.'

    SQL lives here — not in the caller (ADR-022 / ADR-024 §Package boundary).
    """
    conn = get_connection()
    try:
        cursor = conn.execute(
            "SELECT 1 FROM section_completions WHERE section_id = ? LIMIT 1",
            (section_id,),
        )
        row = cursor.fetchone()
    finally:
        conn.close()

    return row is not None


def list_complete_section_ids_for_chapter(chapter_id: str) -> list[str]:
    """
    Return a list of section_id strings for all complete Sections in a Chapter.

    ADR-024: 'list_complete_section_ids_for_chapter returns list[str] (a list of
    Section IDs, not full SectionCompletion objects) because the template only
    needs the set of completed IDs, not their timestamps.'

    The indexed chapter_id column makes this a B-tree seek rather than a full-table
    scan (ADR-024 §chapter_id column rationale).

    SQL lives here — not in the caller (ADR-022 / ADR-024 §Package boundary).
    """
    conn = get_connection()
    try:
        cursor = conn.execute(
            "SELECT section_id FROM section_completions WHERE chapter_id = ?",
            (chapter_id,),
        )
        rows = cursor.fetchall()
    finally:
        conn.close()

    return [row["section_id"] for row in rows]
