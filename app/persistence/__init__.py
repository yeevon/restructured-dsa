"""
app/persistence — the only DB-toucher in the application.

ADR-022: persistence boundary.  `import sqlite3` and all SQL string literals
live exclusively in this package.  Routes and other consumers call only the
typed public functions exported here.

Public API exported by this package:
  - init_schema()                               — bootstrap the schema (called at app startup)
  - create_note(...)                            — insert a new Note row
  - list_notes_for_chapter(...)                 — return Notes for a Chapter, most-recent-first
  - Note                                        — dataclass for a single Note row
  - SectionCompletion                           — dataclass for a single section_completions row
  - mark_section_complete(section_id, chapter_id) -> SectionCompletion
  - unmark_section_complete(section_id) -> None
  - is_section_complete(section_id) -> bool
  - list_complete_section_ids_for_chapter(chapter_id) -> list[str]
  - count_complete_sections_per_chapter() -> dict[str, int]
"""

from app.persistence.connection import init_schema
from app.persistence.notes import Note, create_note, list_notes_for_chapter
from app.persistence.section_completions import (
    SectionCompletion,
    mark_section_complete,
    unmark_section_complete,
    is_section_complete,
    list_complete_section_ids_for_chapter,
    count_complete_sections_per_chapter,
)

__all__ = [
    "init_schema",
    "Note",
    "create_note",
    "list_notes_for_chapter",
    "SectionCompletion",
    "mark_section_complete",
    "unmark_section_complete",
    "is_section_complete",
    "list_complete_section_ids_for_chapter",
    "count_complete_sections_per_chapter",
]
