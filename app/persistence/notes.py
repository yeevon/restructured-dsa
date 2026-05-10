"""
app/persistence/notes — Note entity persistence.

ADR-022: SQL string literals for the Note entity live EXCLUSIVELY in this
module.  Routes call the typed public functions below; they never receive
a sqlite3.Connection or raw row tuples.

Public API:
  - Note       — dataclass describing a note row
  - create_note(chapter_id, body) -> Note
  - list_notes_for_chapter(chapter_id) -> list[Note]
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass

from app.persistence.connection import get_connection


@dataclass
class Note:
    """
    A single persisted Note row.

    ADR-022 §Schema:
      note_id    INTEGER PRIMARY KEY AUTOINCREMENT
      chapter_id TEXT NOT NULL
      body       TEXT NOT NULL
      created_at TEXT NOT NULL  (ISO-8601 UTC)
      updated_at TEXT NOT NULL  (ISO-8601 UTC)
    No user_id (MC-7 / ADR-022 §Schema).
    No section_id (deferred to follow-up task / ADR-022 §Schema).
    """

    note_id: int
    chapter_id: str
    body: str
    created_at: str
    updated_at: str


def _utc_now_iso() -> str:
    r"""
    Return the current UTC time as an ISO-8601 string with microsecond precision.

    ADR-022 specifies ISO-8601 UTC strings. The format YYYY-MM-DDTHH:MM:SSZ
    given in the ADR is the minimum shape; appending microseconds
    (YYYY-MM-DDTHH:MM:SS.ffffffZ) is a strict superset that still matches the
    ISO-8601 pattern asserted by the tests (\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}).

    Microsecond precision is needed so that two Notes written in rapid succession
    (e.g., within the same wall-clock second, separated by only a few milliseconds)
    receive distinct timestamps and sort correctly by created_at DESC.
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z"


def create_note(chapter_id: str, body: str) -> Note:
    """
    Insert a new Note row and return the resulting Note.

    ADR-022: the route handler passes a validated, trimmed body; this
    function sets created_at and updated_at to the current UTC time.

    SQL lives here — not in the caller (ADR-022 §Package boundary).
    """
    now = _utc_now_iso()
    conn = get_connection()
    try:
        cursor = conn.execute(
            "INSERT INTO notes (chapter_id, body, created_at, updated_at) "
            "VALUES (?, ?, ?, ?)",
            (chapter_id, body, now, now),
        )
        conn.commit()
        note_id = cursor.lastrowid
    finally:
        conn.close()

    return Note(
        note_id=note_id,
        chapter_id=chapter_id,
        body=body,
        created_at=now,
        updated_at=now,
    )


def list_notes_for_chapter(chapter_id: str) -> list[Note]:
    """
    Return all Notes for a Chapter, ordered most-recent-first.

    ADR-023 §Multiple-Note display: 'ORDER BY created_at DESC'.
    ADR-022 §Schema: chapter_id is NOT UNIQUE; multiple Notes per Chapter
    are supported.

    SQL lives here — not in the caller (ADR-022 §Package boundary).
    """
    conn = get_connection()
    try:
        cursor = conn.execute(
            "SELECT note_id, chapter_id, body, created_at, updated_at "
            "FROM notes "
            "WHERE chapter_id = ? "
            "ORDER BY created_at DESC",
            (chapter_id,),
        )
        rows = cursor.fetchall()
    finally:
        conn.close()

    return [
        Note(
            note_id=row["note_id"],
            chapter_id=row["chapter_id"],
            body=row["body"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
        for row in rows
    ]
