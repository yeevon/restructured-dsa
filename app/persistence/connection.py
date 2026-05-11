"""
app/persistence/connection — SQLite connection management.

ADR-022:
  - Store technology: SQLite via stdlib sqlite3 (no third-party DB driver).
  - Default path: data/notes.db relative to repository root.
  - Override: NOTES_DB_PATH environment variable (full path to the db file).
  - Schema bootstrap: CREATE TABLE IF NOT EXISTS at first connection (idempotent).
  - Package boundary: sqlite3 import lives ONLY in this package.

The data/ directory is created if it does not exist (ADR-022 §Store file location).
"""

from __future__ import annotations

import os
import pathlib
import sqlite3

# ---- Path resolution (ADR-022 §Store file location) ----

_APP_DIR = pathlib.Path(__file__).parent.parent   # app/
_REPO_ROOT = _APP_DIR.parent                       # repo root

_DEFAULT_DB_PATH = str(_REPO_ROOT / "data" / "notes.db")


def _get_db_path() -> str:
    """
    Return the filesystem path to the SQLite database file.
    Honors the NOTES_DB_PATH environment variable (ADR-022).
    """
    return os.environ.get("NOTES_DB_PATH", _DEFAULT_DB_PATH)


def _ensure_data_dir(db_path: str) -> None:
    """
    Create the parent directory of the database file if it does not exist.
    ADR-022: 'The data/ directory is created by the persistence layer at first
    connection if it does not already exist.'
    """
    parent = pathlib.Path(db_path).parent
    parent.mkdir(parents=True, exist_ok=True)


# ---- Schema DDL (ADR-022 §Migration story) ----

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS notes (
    note_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    chapter_id TEXT    NOT NULL,
    body       TEXT    NOT NULL,
    created_at TEXT    NOT NULL,
    updated_at TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_notes_chapter_id ON notes (chapter_id);

CREATE TABLE IF NOT EXISTS section_completions (
    section_id   TEXT PRIMARY KEY,
    chapter_id   TEXT NOT NULL,
    completed_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_section_completions_chapter_id
    ON section_completions (chapter_id);

-- ---------------------------------------------------------------------------
-- Quiz domain tables (ADR-033 §Table set + §Schema bootstrap)
-- All five tables; CREATE TABLE IF NOT EXISTS = idempotent (ADR-022 migration
-- story).  Foreign-key enforcement is enabled below via PRAGMA foreign_keys.
-- ---------------------------------------------------------------------------

-- A Quiz: scoped to exactly one Section (manifest §5/§6/§7, MC-2).
CREATE TABLE IF NOT EXISTS quizzes (
    quiz_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    section_id TEXT    NOT NULL,
    status     TEXT    NOT NULL DEFAULT 'requested',
    created_at TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_quizzes_section_id ON quizzes (section_id);

-- The Question Bank for a Section (manifest §8 "never deleted").
-- Every Question is a hands-on coding task (manifest §5/§7):
--   prompt = coding-task description; topics = '|'-delimited tag list.
-- NO choice/recall/describe columns.
CREATE TABLE IF NOT EXISTS questions (
    question_id INTEGER PRIMARY KEY AUTOINCREMENT,
    section_id  TEXT    NOT NULL,
    prompt      TEXT    NOT NULL,
    topics      TEXT    NOT NULL DEFAULT '',
    created_at  TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_questions_section_id ON questions (section_id);

-- Membership: which Questions a Quiz is composed of (many-to-many).
-- A Question MAY appear in multiple Quizzes for its Section (manifest §8).
CREATE TABLE IF NOT EXISTS quiz_questions (
    quiz_id     INTEGER NOT NULL REFERENCES quizzes (quiz_id),
    question_id INTEGER NOT NULL REFERENCES questions (question_id),
    position    INTEGER NOT NULL,
    PRIMARY KEY (quiz_id, question_id)
);
CREATE INDEX IF NOT EXISTS idx_quiz_questions_question_id ON quiz_questions (question_id);

-- A Quiz Attempt (manifest §8).
-- status enum names a failure state (MC-5): 'grading_failed'.
CREATE TABLE IF NOT EXISTS quiz_attempts (
    attempt_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    quiz_id      INTEGER NOT NULL REFERENCES quizzes (quiz_id),
    status       TEXT    NOT NULL DEFAULT 'in_progress',
    created_at   TEXT    NOT NULL,
    submitted_at TEXT,
    graded_at    TEXT
);
CREATE INDEX IF NOT EXISTS idx_quiz_attempts_quiz_id ON quiz_attempts (quiz_id);

-- Per-Question state within an Attempt (MC-8: wrong-answer-replay history).
-- is_correct and explanation are NULL until graded.
CREATE TABLE IF NOT EXISTS attempt_questions (
    attempt_id  INTEGER NOT NULL REFERENCES quiz_attempts (attempt_id),
    question_id INTEGER NOT NULL REFERENCES questions (question_id),
    response    TEXT,
    is_correct  INTEGER,
    explanation TEXT,
    PRIMARY KEY (attempt_id, question_id)
);
CREATE INDEX IF NOT EXISTS idx_attempt_questions_question_id ON attempt_questions (question_id);
"""


def get_connection() -> sqlite3.Connection:
    """
    Open a new SQLite connection to the database file and bootstrap the schema.

    Callers are responsible for closing the connection (or using it as a
    context manager).  Row factory is sqlite3.Row so callers receive named
    columns.

    ADR-022: sqlite3.Row row-factory; no connection pool (single-user,
    single-process, no concurrency story).

    Schema bootstrap is performed on every connection so that:
    - Tests that inject a fresh NOTES_DB_PATH via monkeypatch always get a
      fully-initialized schema without requiring a separate startup call.
    - All statements are idempotent (CREATE TABLE IF NOT EXISTS / CREATE INDEX
      IF NOT EXISTS), so repeated calls are safe (ADR-022 §Migration story).
    """
    db_path = _get_db_path()
    _ensure_data_dir(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    # ADR-033 §Schema bootstrap: enable foreign-key enforcement so REFERENCES
    # clauses on quiz_questions / attempt_questions / quiz_attempts are enforced.
    # notes and section_completions have no REFERENCES clauses so this is a no-op
    # for them. (ADR-033 §Schema bootstrap: 'recommended, not a hard requirement'.)
    conn.execute("PRAGMA foreign_keys = ON")
    # Idempotent schema bootstrap on every fresh connection
    conn.executescript(_SCHEMA_SQL)
    conn.commit()
    return conn


def init_schema() -> None:
    """
    Explicit schema bootstrap — opens a connection (which bootstraps the schema
    idempotently) and closes it immediately.

    Called at app startup so the database file and table exist before any
    request arrives.  Also called by tests to verify the schema was created.

    ADR-022: 'Schema bootstrap is performed by app/persistence/connection.py
    on first connection: every CREATE TABLE and CREATE INDEX statement is
    wrapped in IF NOT EXISTS and run idempotently.'
    """
    conn = get_connection()
    conn.close()
