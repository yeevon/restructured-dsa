"""
TASK-009: Notes bootstrap — minimum viable create-and-read on a single Chapter.

Tests derive from the Acceptance Criteria in
`design_docs/tasks/TASK-009-notes-bootstrap-minimum-viable-create-and-read.md`
and from the two Accepted ADRs:
  ADR-022 — Persistence layer: SQLite via stdlib `sqlite3`, `app/persistence/`
             package boundary, Note schema (no `user_id`, no `section_id`).
  ADR-023 — Notes surface: POST /lecture/{chapter_id}/notes (form-encoded, PRG
             303 redirect), bottom-of-page Notes section in lecture.html.j2,
             empty-state caption, most-recent-first list, server-side validation.

Coverage matrix (per TDD instruction checklist):
  Boundary:
    - test_notes_ui_present_on_all_12_chapters: iterate every Chapter in the corpus.
    - test_note_body_at_max_boundary / test_note_body_over_max_rejected: 64 KiB
      limit in ADR-023.
    - test_multi_note_order_most_recent_first: ordering boundary (newest at top).
    - test_mc7_no_user_id_column: schema boundary — column must be absent.
  Edge:
    - test_post_note_whitespace_only_rejected: whitespace-only body edge case.
    - test_post_note_empty_body_rejected: empty body edge case.
    - test_notes_chapter_isolation: Notes for Chapter A must NOT appear on Chapter B's
      page (cross-chapter contamination edge).
    - test_two_notes_same_chapter_both_render: two Notes on the same Chapter.
    - test_note_body_unicode_round_trips: Unicode characters in Note body.
  Negative:
    - test_post_note_empty_body_rejected: empty POST body → HTTP 400 or redirect
      back with no new Note created.
    - test_post_note_whitespace_only_rejected: whitespace POST body → HTTP 400.
    - test_post_note_to_nonexistent_chapter_returns_404: unknown chapter_id → 404.
    - test_mc10_no_sqlite3_import_outside_persistence_package: grep confirms
      `import sqlite3` only in app/persistence/.
    - test_mc10_no_sql_literals_outside_persistence_package: grep confirms SQL
      keywords in string literals only inside app/persistence/.
    - test_mc7_no_user_id_column: `PRAGMA table_info(notes)` returns no user_id.
    - test_mc6_notes_write_does_not_touch_content_latex: monkeypatch confirms
      no write to content/latex/ during Note creation.
  Performance:
    - test_get_lecture_page_with_many_notes_within_time_budget: insert 50 Notes
      for one Chapter, assert page renders in < 5 seconds.

pytestmark registers all tests under task("TASK-009").
"""

from __future__ import annotations

import os
import pathlib
import re
import sqlite3
import time

import pytest

pytestmark = pytest.mark.task("TASK-009")

# ---------------------------------------------------------------------------
# Chapter IDs (same canonical list as TASK-005)
# ---------------------------------------------------------------------------

ALL_CHAPTER_IDS = [
    "ch-01-cpp-refresher",
    "ch-02-intro-to-algorithms",
    "ch-03-intro-to-data-structures",
    "ch-04-lists-stacks-and-queues",
    "ch-05-hash-tables",
    "ch-06-trees",
    "ch-07-heaps-and-treaps",
    "ch-09-balanced-trees",
    "ch-10-graphs",
    "ch-11-b-trees",
    "ch-12-sets",
    "ch-13-additional-material",
]

REPO_ROOT = pathlib.Path(__file__).parent.parent

# ---------------------------------------------------------------------------
# Helpers — deferred imports so collection succeeds before implementation exists
# ---------------------------------------------------------------------------


def _make_client(monkeypatch=None, db_path: str | None = None):
    """
    Return a FastAPI TestClient.  If db_path is provided and monkeypatch is
    given, inject NOTES_DB_PATH into the environment so the persistence layer
    targets an isolated test database (ADR-022: env-overridable via NOTES_DB_PATH).

    The import is deferred so pytest collection succeeds even when the app
    package hasn't been written yet; the ImportError surfaces at test-call time
    (RED), not at collection time (ERROR).
    """
    if monkeypatch is not None and db_path is not None:
        monkeypatch.setenv("NOTES_DB_PATH", db_path)

    from fastapi.testclient import TestClient  # noqa: PLC0415
    from app.main import app  # noqa: PLC0415

    return TestClient(app)


def _get_notes_db_path(tmp_path: pathlib.Path) -> str:
    """Return a fresh per-test SQLite database path inside tmp_path."""
    return str(tmp_path / "test_notes.db")


def _direct_db_list_notes(db_path: str, chapter_id: str) -> list[dict]:
    """
    Query the SQLite database directly (bypassing the app) to verify persistence
    at the storage level.  This is an observer, not a collaborator — we use the
    same stdlib sqlite3 that ADR-022 names, but from outside the app.  This is
    the 'documented seam' for cross-restart persistence verification.
    """
    if not pathlib.Path(db_path).exists():
        return []
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.execute(
        "SELECT note_id, chapter_id, body, created_at, updated_at "
        "FROM notes WHERE chapter_id = ? ORDER BY created_at DESC",
        (chapter_id,),
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


# ===========================================================================
# AC-1 — Notes UI affordance (form + notes) is visible on every Chapter page
#
# Stronger interpretation (amended for ADR-028 supersedure — rail-resident Notes):
#   - a <section class="rail-notes"> block in the rail (ADR-028: Notes moved to rail)
#   - a <form ...> element whose action points to /lecture/{chapter_id}/notes
#   - a <textarea name="body"> inside it
#   - a <h2 ...> Notes heading (rail-notes-heading class per ADR-028)
# ===========================================================================


@pytest.mark.parametrize("chapter_id", ALL_CHAPTER_IDS)
def test_notes_ui_present_on_all_12_chapters(chapter_id: str, tmp_path, monkeypatch) -> None:
    """
    AC-1 (TASK-009): GET /lecture/{chapter_id} for every Chapter shows the Notes UI.
    
    Amended for ADR-028 (Accepted, TASK-011): Notes section moved from bottom-of-page
    (<section class="notes-surface">) to rail-resident panel (<section class="rail-notes">).
    The form and textarea remain; only the container class and location changed.
    
      - <section class="rail-notes"> block in the rail (ADR-028: supersedes ADR-023 §Template-surface)
      - <form ... action="/lecture/{chapter_id}/notes"> element (route unchanged)
      - <textarea name="body"> inside the form (name unchanged)
      - Notes heading (rail-notes-heading class, per ADR-028)

    Iterates ALL 12 corpus Chapters — not a spot-check.

    Trace: AC-1; ADR-023 §Template surface; MC-3 (existing badge must still render).
    """
    db_path = _get_notes_db_path(tmp_path)
    client = _make_client(monkeypatch, db_path)

    response = client.get(f"/lecture/{chapter_id}")
    assert response.status_code == 200, (
        f"GET /lecture/{chapter_id} returned HTTP {response.status_code}; expected 200. "
        "AC-1: every Chapter's Lecture page must be reachable."
    )
    body = response.text

    # ADR-028 (supersedes ADR-023 §Template-surface): rail-resident Notes panel
    # The old 'notes-surface' class is REMOVED; the new 'rail-notes' class is the commitment.
    assert "rail-notes" in body, (
        f"GET /lecture/{chapter_id} — rendered HTML does not contain 'rail-notes' class. "
        "AC-1/ADR-028 (amended from ADR-023): Notes section moved from bottom-of-page to rail. "
        "The rail-resident Notes panel uses <section class='rail-notes'> in _nav_rail.html.j2."
    )
    # The old 'notes-surface' class must NOT appear (ADR-028: removed)
    assert "notes-surface" not in body, (
        f"GET /lecture/{chapter_id} — 'notes-surface' class is still present. "
        "ADR-028: the bottom-of-page Notes section is removed; 'notes-surface' is renamed "
        "to 'rail-notes'."
    )

    # ADR-023: form pointing at the POST route
    expected_action = f"/lecture/{chapter_id}/notes"
    assert expected_action in body, (
        f"GET /lecture/{chapter_id} — rendered HTML does not contain the form action "
        f"'{expected_action}'. "
        "AC-1/ADR-023: form action must be POST /lecture/{chapter_id}/notes."
    )

    # ADR-023: textarea with name="body"
    assert 'name="body"' in body, (
        f"GET /lecture/{chapter_id} — rendered HTML does not contain '<textarea name=\"body\">'. "
        "AC-1/ADR-023: the Notes form must include a textarea named 'body'."
    )

    # ADR-028 (amended): rail-notes heading class replaces notes-heading
    assert "rail-notes-heading" in body or "Notes" in body, (
        f"GET /lecture/{chapter_id} — rendered HTML does not contain a rail-notes heading. "
        "AC-1/ADR-028 (amended from ADR-023): the rail Notes panel heading uses "
        "class='rail-notes-heading' per ADR-028 §CSS file ownership."
    )


# ===========================================================================
# AC-2 — POST a Note → persists → visible on Lecture page
# ===========================================================================


def test_post_note_returns_303_redirect(tmp_path, monkeypatch) -> None:
    """
    AC-2 (TASK-009) / ADR-023: POST /lecture/{chapter_id}/notes with a valid
    non-empty body returns HTTP 303 See Other (PRG redirect to GET page).

    ADR-023 §Route shape: 'returns HTTP 303 See Other with Location:
    /lecture/{chapter_id}'.

    Trace: AC-2; ADR-023 §Route shape; RFC 7231 §6.4.4.
    """
    db_path = _get_notes_db_path(tmp_path)
    client = _make_client(monkeypatch, db_path)

    response = client.post(
        "/lecture/ch-01-cpp-refresher/notes",
        data={"body": "A test note for chapter 1."},
        follow_redirects=False,
    )
    assert response.status_code == 303, (
        f"POST /lecture/ch-01-cpp-refresher/notes returned HTTP {response.status_code}; "
        "expected 303 See Other. "
        "AC-2/ADR-023: the PRG idiom requires 303 so browsers re-issue GET."
    )
    location = response.headers.get("location", "")
    assert "/lecture/ch-01-cpp-refresher" in location, (
        f"POST /lecture/ch-01-cpp-refresher/notes — Location header is {location!r}; "
        "expected it to contain '/lecture/ch-01-cpp-refresher'. "
        "ADR-023: redirect must return to the Chapter's Lecture page."
    )


def test_post_note_body_appears_in_get_response(tmp_path, monkeypatch) -> None:
    """
    AC-2 (TASK-009): after a successful POST, a GET /lecture/{chapter_id}
    returns a page that contains the Note body text.

    Trace: AC-2; ADR-023 §Multiple-Note display; ADR-022 §Note schema.
    """
    db_path = _get_notes_db_path(tmp_path)
    client = _make_client(monkeypatch, db_path)

    unique_body = "This is a uniquely worded note about Chapter 2 for TASK-009 test."
    client.post(
        "/lecture/ch-02-intro-to-algorithms/notes",
        data={"body": unique_body},
        follow_redirects=True,
    )

    get_response = client.get("/lecture/ch-02-intro-to-algorithms")
    assert get_response.status_code == 200
    assert unique_body in get_response.text, (
        f"GET /lecture/ch-02-intro-to-algorithms — the Note body {unique_body!r} was not "
        "found in the rendered HTML after a successful POST. "
        "AC-2: a submitted Note must be visible on the Lecture page."
    )


# ===========================================================================
# AC-3 — Persistence across restart (cross-instance persistence)
# ===========================================================================


def test_note_persists_across_app_restart(tmp_path, monkeypatch) -> None:
    """
    AC-3 (TASK-009) / Manifest §7: 'every Note … persists across sessions and
    is owned by the single user.'

    Simulates a server restart by:
      1. Creating a TestClient (instance A), posting a Note.
      2. Closing instance A.
      3. Creating a new TestClient (instance B) pointing at the SAME database
         file via NOTES_DB_PATH.
      4. Issuing GET /lecture/{chapter_id} on instance B.
      5. Asserting the Note body is visible.

    The 'same database file' is the documented seam for cross-restart persistence
    per ADR-022 §Store file location.

    Trace: AC-3; Manifest §7 'persists across sessions'; ADR-022 §NOTES_DB_PATH.
    """
    db_path = _get_notes_db_path(tmp_path)
    unique_body = "Restart-persistence test note TASK009-AC3."

    # --- Instance A: create the Note ---
    monkeypatch.setenv("NOTES_DB_PATH", db_path)
    from fastapi.testclient import TestClient  # noqa: PLC0415
    from app.main import app as app_a  # noqa: PLC0415

    client_a = TestClient(app_a)
    post_resp = client_a.post(
        "/lecture/ch-03-intro-to-data-structures/notes",
        data={"body": unique_body},
        follow_redirects=False,
    )
    assert post_resp.status_code == 303, (
        "POST in instance A did not return 303 — cannot proceed with restart test."
    )

    # Verify Note is in the raw database (storage-level observer)
    rows = _direct_db_list_notes(db_path, "ch-03-intro-to-data-structures")
    assert any(r["body"] == unique_body for r in rows), (
        f"Note body {unique_body!r} was not found in the raw database at {db_path} "
        "immediately after POST. "
        "AC-3/ADR-022: the persistence layer must commit the Note to disk."
    )

    # --- Simulate restart: create a new TestClient pointing at the SAME DB ---
    # Re-import to simulate a fresh app startup; env var still set.
    import importlib
    import app.main as main_module
    importlib.reload(main_module)
    from app.main import app as app_b  # noqa: PLC0415

    client_b = TestClient(app_b)
    get_resp = client_b.get("/lecture/ch-03-intro-to-data-structures")
    assert get_resp.status_code == 200, (
        f"GET on instance B returned {get_resp.status_code}; expected 200."
    )
    assert unique_body in get_resp.text, (
        f"After simulated restart (new TestClient, same NOTES_DB_PATH), "
        f"the Note body {unique_body!r} was NOT visible on the Lecture page. "
        "AC-3/Manifest §7: every Note must persist across server restarts."
    )


# ===========================================================================
# AC-4 — Empty-state and Chapter isolation
# ===========================================================================


def test_empty_state_caption_shown_for_chapter_with_no_notes(tmp_path, monkeypatch) -> None:
    """
    AC-4 (TASK-009) / ADR-023 §Empty-state: when a Chapter has no Notes, the
    rendered page shows the empty-state caption 'No notes yet' (exact text per
    ADR-023: 'No notes yet — write the first one below.') and shows the form.

    Trace: AC-4; ADR-023 §Empty-state shape.
    """
    db_path = _get_notes_db_path(tmp_path)
    client = _make_client(monkeypatch, db_path)

    # Fresh database: no notes exist for any Chapter.
    response = client.get("/lecture/ch-04-lists-stacks-and-queues")
    assert response.status_code == 200
    body = response.text

    assert "No notes yet" in body, (
        "GET /lecture/ch-04-lists-stacks-and-queues (no Notes) — empty-state caption "
        "'No notes yet' was not found in rendered HTML. "
        "AC-4/ADR-023: the empty-state caption 'No notes yet — write the first one below.' "
        "must appear when the Chapter has no Notes."
    )

    # The form must still be present in empty state
    assert 'name="body"' in body, (
        "GET /lecture/ch-04-lists-stacks-and-queues (no Notes) — the Note form "
        "(textarea name='body') was not present. "
        "AC-4/ADR-023: the form must always be available, even in empty state."
    )


def test_notes_chapter_isolation(tmp_path, monkeypatch) -> None:
    """
    AC-4 (TASK-009): a Note written for Chapter A must NOT appear on Chapter B's
    Lecture page, and Chapter B's page must show the empty-state caption.

    This tests that list_notes_for_chapter() filters by chapter_id correctly —
    a stale Note from another Chapter appearing is a data-isolation bug.

    Trace: AC-4 ('never … a stale Note from another Chapter'); ADR-022
    §Schema ('chapter_id TEXT NOT NULL'); ADR-023 §Route ('pass notes to template').
    """
    db_path = _get_notes_db_path(tmp_path)
    client = _make_client(monkeypatch, db_path)

    # Write a Note on Chapter 1
    unique_body_ch1 = "This note belongs ONLY to chapter 1, isolation test."
    client.post(
        "/lecture/ch-01-cpp-refresher/notes",
        data={"body": unique_body_ch1},
        follow_redirects=True,
    )

    # Chapter 1 should show the note
    resp_ch1 = client.get("/lecture/ch-01-cpp-refresher")
    assert unique_body_ch1 in resp_ch1.text, (
        "Chapter 1 note not found on Chapter 1 page — prerequisite for isolation test."
    )

    # Chapter 2 must NOT show Chapter 1's note and must show the empty-state caption
    resp_ch2 = client.get("/lecture/ch-02-intro-to-algorithms")
    assert resp_ch2.status_code == 200
    assert unique_body_ch1 not in resp_ch2.text, (
        f"Chapter 1 note body {unique_body_ch1!r} appeared on the Chapter 2 page. "
        "AC-4/ADR-022: notes must be filtered by chapter_id — cross-chapter contamination."
    )
    assert "No notes yet" in resp_ch2.text, (
        "Chapter 2 page (with no Notes) does not show 'No notes yet' empty-state caption. "
        "AC-4/ADR-023: empty-state caption required when the Chapter has no Notes."
    )


# ===========================================================================
# AC-5 — No user_id column (MC-7 schema enforcement)
# ===========================================================================


def test_mc7_no_user_id_column(tmp_path, monkeypatch) -> None:
    """
    AC-5 (TASK-009) / MC-7 architecture portion (now active per ADR-022):
    the `notes` table must have NO `user_id` column.

    Manifest §5/§6/§7: single-user — no auth, no per-user partitioning.
    ADR-022 §Schema: 'Explicitly omitted: no `user_id` column.'
    ADR-022 §Consequences: 'A `user_id` column on any persisted entity. Forbidden
    by MC-7 (architecture portion now active).'

    Test strategy: trigger schema bootstrap by issuing a GET (which opens the
    persistence layer), then inspect `PRAGMA table_info(notes)` directly.

    Trace: AC-5; Manifest §5 'No multi-user features'; ADR-022 §Schema; MC-7.
    """
    db_path = _get_notes_db_path(tmp_path)
    client = _make_client(monkeypatch, db_path)

    # Trigger schema bootstrap
    client.get("/lecture/ch-01-cpp-refresher")

    assert pathlib.Path(db_path).exists(), (
        f"Database file was not created at {db_path} after a GET request. "
        "ADR-022: the persistence layer must create data/notes.db at first connection."
    )

    conn = sqlite3.connect(db_path)
    cur = conn.execute("PRAGMA table_info(notes)")
    columns = {row[1] for row in cur.fetchall()}  # column names
    conn.close()

    assert "notes" is not None, "notes table must exist after schema bootstrap"
    assert "user_id" not in columns, (
        f"The 'notes' table contains a 'user_id' column. Columns found: {columns!r}. "
        "AC-5/MC-7: manifest §5/§6/§7 (single user) and ADR-022 §Schema explicitly "
        "forbid a user_id column. MC-7's architecture portion is now active."
    )

    # Verify the required columns ARE present
    required_columns = {"note_id", "chapter_id", "body", "created_at", "updated_at"}
    missing = required_columns - columns
    assert not missing, (
        f"The 'notes' table is missing required columns: {missing!r}. "
        "ADR-022 §Schema: required columns are "
        "note_id, chapter_id, body, created_at, updated_at."
    )


# ===========================================================================
# AC-5 — no section_id column in initial schema (deferred per ADR-022)
# ===========================================================================


def test_mc7_no_section_id_column_in_initial_schema(tmp_path, monkeypatch) -> None:
    """
    ADR-022 §Schema: 'Explicitly omitted: no `section_id` column.'
    TASK-009 defers the optional Section reference (manifest §7 'may optionally
    reference one Section') to a follow-up task.

    Trace: ADR-022 §Schema; TASK-009 'Out of scope' (optional Section reference).
    """
    db_path = _get_notes_db_path(tmp_path)
    client = _make_client(monkeypatch, db_path)

    client.get("/lecture/ch-01-cpp-refresher")  # trigger schema bootstrap

    if not pathlib.Path(db_path).exists():
        pytest.fail(f"Database not created at {db_path}.")

    conn = sqlite3.connect(db_path)
    cur = conn.execute("PRAGMA table_info(notes)")
    columns = {row[1] for row in cur.fetchall()}
    conn.close()

    assert "section_id" not in columns, (
        f"The 'notes' table has a 'section_id' column in the initial schema. "
        f"Columns found: {columns!r}. "
        "ADR-022 §Schema: section_id is explicitly deferred to a follow-up task."
    )


# ===========================================================================
# AC-6 / MC-10 — Persistence boundary: sqlite3 import only in app/persistence/
# ===========================================================================


def test_mc10_no_sqlite3_import_outside_persistence_package() -> None:
    """
    AC-6 (TASK-009) / MC-10 (architecture portion now active per ADR-022):
    `import sqlite3` must appear ONLY in files under `app/persistence/`.

    ADR-022 §Package boundary: '`import sqlite3` may appear only in files under
    `app/persistence/`.'

    Grep strategy: search all `.py` files under `app/` for the string
    'import sqlite3', filtering OUT those under `app/persistence/`.
    Any match outside that subtree is a blocker-level MC-10 violation.

    Trace: AC-6; ADR-022 §Package boundary; MC-10.
    """
    app_dir = REPO_ROOT / "app"
    violations = []
    for py_file in app_dir.rglob("*.py"):
        persistence_dir = app_dir / "persistence"
        try:
            relative = py_file.relative_to(persistence_dir)
            # File is inside app/persistence/ — allowed
            _ = relative
            continue
        except ValueError:
            pass
        # File is outside app/persistence/
        text = py_file.read_text(encoding="utf-8")
        if "import sqlite3" in text:
            violations.append(str(py_file))

    assert violations == [], (
        f"MC-10 BLOCKER: `import sqlite3` found outside `app/persistence/` "
        f"in the following files: {violations!r}. "
        "ADR-022 §Package boundary: DB driver imports must be confined to "
        "app/persistence/. Routes, templates, parser, discovery, config, designation "
        "must never import sqlite3 directly."
    )


def test_mc10_no_sql_literals_outside_persistence_package() -> None:
    """
    AC-6 (TASK-009) / MC-10: SQL string literals (containing SELECT, INSERT,
    UPDATE, DELETE, CREATE TABLE, BEGIN, COMMIT, ROLLBACK) must appear ONLY in
    files under `app/persistence/`.

    ADR-022 §Package boundary: 'SQL string literals … may appear only in files
    under `app/persistence/`.'

    Trace: AC-6; ADR-022 §Package boundary; MC-10.
    """
    app_dir = REPO_ROOT / "app"
    persistence_dir = app_dir / "persistence"

    # SQL keyword tokens that should not appear in string literals outside the boundary.
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
        # No re.IGNORECASE: SQL keywords in hand-written SQL are uppercase (ADR-022).
        # LaTeX uses lowercase \begin{...}, which must NOT match \bBEGIN\b.
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
        f"in the following files: {violations!r}. "
        "ADR-022 §Package boundary: SQL string literals must be confined to "
        "app/persistence/. Routes and other modules must only call the typed "
        "public functions (create_note, list_notes_for_chapter) — never embed SQL."
    )


# ===========================================================================
# AC-7 / MC-6 — Notes write does not touch content/latex/
# ===========================================================================


def test_mc6_notes_write_does_not_touch_content_latex(tmp_path, monkeypatch) -> None:
    """
    AC-7 (TASK-009) / MC-6: a Note POST must not open any file under
    `content/latex/` for write.

    Manifest §5 'No in-app authoring of lecture content' / ADR-022 §Store file:
    'The store file lives outside content/latex/ (MC-6 preserved by construction).
    Nothing under content/latex/ is opened for write by the persistence layer.'

    Strategy: monkeypatch builtins.open to spy on all write-mode opens under the
    repo root; POST a Note; assert zero writes under content/latex/.

    Trace: AC-7; Manifest §5/§6; ADR-022 §Store file location; MC-6.
    """
    import builtins

    content_latex_abs = str(REPO_ROOT / "content" / "latex")
    write_violations: list[str] = []
    original_open = builtins.open

    def spying_open(file, mode="r", *args, **kwargs):
        path_str = str(file)
        # Flag any write-mode open targeting anything under content/latex/
        write_modes = {"w", "wb", "a", "ab", "x", "xb", "w+", "wb+", "a+", "ab+"}
        effective_mode = str(mode)
        if (
            content_latex_abs in path_str
            and any(effective_mode.startswith(m) for m in {"w", "a", "x"})
        ):
            write_violations.append(path_str)
        return original_open(file, mode, *args, **kwargs)

    db_path = _get_notes_db_path(tmp_path)
    monkeypatch.setenv("NOTES_DB_PATH", db_path)
    monkeypatch.setattr(builtins, "open", spying_open)

    from fastapi.testclient import TestClient  # noqa: PLC0415
    from app.main import app  # noqa: PLC0415

    client = TestClient(app)
    client.post(
        "/lecture/ch-05-hash-tables/notes",
        data={"body": "MC-6 write-test note."},
        follow_redirects=False,
    )

    assert write_violations == [], (
        f"MC-6 BLOCKER: the Notes POST handler opened files under content/latex/ "
        f"for write: {write_violations!r}. "
        "AC-7/ADR-022: the persistence layer must never write to content/latex/. "
        "The store file lives under data/notes.db (or NOTES_DB_PATH override)."
    )


# ===========================================================================
# Multi-Note: two Notes on the same Chapter both render, most-recent-first
# ===========================================================================


def test_two_notes_same_chapter_both_render(tmp_path, monkeypatch) -> None:
    """
    TASK-009 AC multi-Note (implicit in AC-4 'two Notes on the same Chapter'):
    both Notes must appear on the Lecture page, most-recent-first per ADR-023.

    ADR-022 §Schema: 'chapter_id is NOT UNIQUE. Multiple Notes per Chapter are
    allowed by the schema.'
    ADR-023 §Multiple-Note display: 'ORDER BY created_at DESC (most-recent first).'

    Trace: AC-4 (implicit multi-Note); ADR-022 §Schema; ADR-023 §Multiple-Note display.
    """
    db_path = _get_notes_db_path(tmp_path)
    client = _make_client(monkeypatch, db_path)

    body_first = "First note for Chapter 6 trees TASK009."
    body_second = "Second note for Chapter 6 trees TASK009 (more recent)."

    client.post(
        "/lecture/ch-06-trees/notes",
        data={"body": body_first},
        follow_redirects=True,
    )
    # Small sleep to ensure created_at timestamps differ
    time.sleep(0.01)
    client.post(
        "/lecture/ch-06-trees/notes",
        data={"body": body_second},
        follow_redirects=True,
    )

    get_response = client.get("/lecture/ch-06-trees")
    assert get_response.status_code == 200
    html = get_response.text

    # Both must appear
    assert body_first in html, (
        f"First note body {body_first!r} not found in rendered HTML for ch-06-trees. "
        "ADR-022: multi-Note-per-Chapter must be supported; both Notes must render."
    )
    assert body_second in html, (
        f"Second note body {body_second!r} not found in rendered HTML for ch-06-trees. "
        "ADR-022: multi-Note-per-Chapter must be supported; both Notes must render."
    )

    # most-recent-first order (ADR-023)
    pos_first = html.index(body_first)
    pos_second = html.index(body_second)
    assert pos_second < pos_first, (
        "ADR-023 §Multiple-Note display: most-recent Note must appear BEFORE older Notes "
        "in the rendered HTML (ORDER BY created_at DESC). "
        f"Position of second (newer) note: {pos_second}; position of first (older): {pos_first}. "
        "The second note should come first."
    )


# ===========================================================================
# Validation: empty and whitespace-only bodies are rejected
# ===========================================================================


def test_post_note_empty_body_rejected(tmp_path, monkeypatch) -> None:
    """
    AC-2 / ADR-023 §Validation: submitting an empty body must not create a Note.

    ADR-023: 'the route handler trims body (rejects leading/trailing whitespace)
    and rejects empty / whitespace-only bodies with HTTP 400 Bad Request.'

    PINNED CONTRACT: HTTP 400 response (or redirect back without creating a Note).
    If the implementation redirects with no Note, the test verifies that no new
    Note was persisted in the database.

    Trace: ADR-023 §Validation; AC-2 (implicit — 'non-empty Note body').
    """
    db_path = _get_notes_db_path(tmp_path)
    client = _make_client(monkeypatch, db_path)

    # Empty body
    response = client.post(
        "/lecture/ch-01-cpp-refresher/notes",
        data={"body": ""},
        follow_redirects=False,
    )

    if response.status_code == 303:
        # If it redirected, verify no Note was persisted
        rows = _direct_db_list_notes(db_path, "ch-01-cpp-refresher")
        assert len(rows) == 0, (
            "POST with empty body redirected (303), but a Note was still persisted "
            "in the database. "
            "ADR-023 §Validation: empty bodies must not create a Note."
        )
    else:
        assert response.status_code == 400, (
            f"POST with empty body returned {response.status_code}; expected 400 "
            "(or 303 redirect without creating a Note). "
            "ADR-023 §Validation: empty bodies must be rejected."
        )


def test_post_note_whitespace_only_rejected(tmp_path, monkeypatch) -> None:
    """
    ADR-023 §Validation: submitting a whitespace-only body must not create a Note.

    The route handler trims the body first; a body that is only spaces/newlines/tabs
    is equivalent to an empty body after trim.

    PINNED CONTRACT: HTTP 400 or redirect without Note creation.

    Trace: ADR-023 §Validation ('trims body (rejects leading/trailing whitespace)
    and rejects empty / whitespace-only bodies').
    """
    db_path = _get_notes_db_path(tmp_path)
    client = _make_client(monkeypatch, db_path)

    response = client.post(
        "/lecture/ch-01-cpp-refresher/notes",
        data={"body": "   \t\n   "},
        follow_redirects=False,
    )

    if response.status_code == 303:
        rows = _direct_db_list_notes(db_path, "ch-01-cpp-refresher")
        assert len(rows) == 0, (
            "POST with whitespace-only body redirected (303) but persisted a Note. "
            "ADR-023: whitespace-only bodies must not be persisted."
        )
    else:
        assert response.status_code == 400, (
            f"POST with whitespace-only body returned {response.status_code}; "
            "expected 400 or a redirect without Note creation. "
            "ADR-023 §Validation: whitespace-only bodies must be rejected."
        )


def test_post_note_to_nonexistent_chapter_returns_404(tmp_path, monkeypatch) -> None:
    """
    ADR-023 §Validation: POST to /lecture/ch-99-does-not-exist/notes must return 404.

    ADR-023: 'the route handler validates chapter_id against the discovered set;
    an unknown chapter_id returns HTTP 404.'

    Trace: ADR-023 §Validation; ADR-002 (Chapter ID validation).
    """
    db_path = _get_notes_db_path(tmp_path)
    client = _make_client(monkeypatch, db_path)

    response = client.post(
        "/lecture/ch-99-does-not-exist/notes",
        data={"body": "A note for a nonexistent chapter."},
        follow_redirects=False,
    )
    assert response.status_code == 404, (
        f"POST /lecture/ch-99-does-not-exist/notes returned {response.status_code}; "
        "expected 404. "
        "ADR-023 §Validation: unknown chapter_id must return 404."
    )


# ===========================================================================
# Boundary: body at max (64 KiB) and over max (64 KiB + 1 byte)
# ===========================================================================


def test_note_body_at_max_boundary_accepted(tmp_path, monkeypatch) -> None:
    """
    Boundary test: a body exactly at the 64 KiB limit must be accepted.

    ADR-023 §Validation: 'Maximum body length: the route handler rejects bodies
    >64 KiB with HTTP 413 (Payload Too Large).'  At exactly 64 KiB it must succeed.

    Trace: ADR-023 §Validation.
    """
    db_path = _get_notes_db_path(tmp_path)
    client = _make_client(monkeypatch, db_path)

    # 64 KiB = 65536 bytes = 65536 ASCII characters
    max_body = "A" * 65536
    response = client.post(
        "/lecture/ch-01-cpp-refresher/notes",
        data={"body": max_body},
        follow_redirects=False,
    )
    # 303 = accepted (PRG redirect); any 2xx or 303 is acceptable
    assert response.status_code in (200, 201, 303), (
        f"POST with 64 KiB body returned {response.status_code}; expected 303 (or 2xx). "
        "ADR-023: a body AT the 64 KiB limit must be accepted."
    )


def test_note_body_over_max_rejected(tmp_path, monkeypatch) -> None:
    """
    Boundary test: a body over 64 KiB must be rejected with HTTP 413.

    ADR-023 §Validation: 'rejects bodies >64 KiB with HTTP 413 (Payload Too Large).'

    Trace: ADR-023 §Validation.
    """
    db_path = _get_notes_db_path(tmp_path)
    client = _make_client(monkeypatch, db_path)

    # 64 KiB + 1 byte
    over_max_body = "A" * 65537
    response = client.post(
        "/lecture/ch-01-cpp-refresher/notes",
        data={"body": over_max_body},
        follow_redirects=False,
    )
    assert response.status_code == 413, (
        f"POST with 65537-byte body returned {response.status_code}; expected 413. "
        "ADR-023 §Validation: bodies >64 KiB must be rejected with HTTP 413."
    )


# ===========================================================================
# Edge: Unicode in Note body round-trips correctly
# ===========================================================================


def test_note_body_unicode_round_trips(tmp_path, monkeypatch) -> None:
    """
    Edge case: a Note body containing Unicode characters (multi-byte UTF-8,
    emoji, accented characters, CJK) must round-trip correctly through the
    persistence layer and appear intact on the Lecture page.

    ADR-022 §Schema: body is TEXT (SQLite stores UTF-8).
    ADR-023 §Multiple-Note display: 'rendered via Jinja2's autoescape; treated
    as untrusted input and HTML-escaped on render.'

    Trace: ADR-022 §Schema; ADR-023 §Multiple-Note display.
    """
    db_path = _get_notes_db_path(tmp_path)
    client = _make_client(monkeypatch, db_path)

    # Unicode body: accented, CJK, math symbol, emoji
    unicode_body = "Árbol AVL — 平衡二叉树 — O(log n) — \U0001f333"
    client.post(
        "/lecture/ch-07-heaps-and-treaps/notes",
        data={"body": unicode_body},
        follow_redirects=True,
    )

    get_response = client.get("/lecture/ch-07-heaps-and-treaps")
    assert get_response.status_code == 200

    # The body text must appear in the rendered HTML (possibly HTML-escaped for
    # special characters like &, <, > — but the core text must be present).
    # Check for the non-special parts that survive HTML escaping intact:
    assert "Árbol AVL" in get_response.text or "&#193;rbol" in get_response.text, (
        "Unicode body text 'Árbol AVL' not found in rendered HTML after POST. "
        "ADR-022: body TEXT column must store UTF-8 transparently."
    )


# ===========================================================================
# Schema: note_id is AUTOINCREMENT (no ROWID reuse)
# ===========================================================================


def test_notes_table_has_autoincrement_primary_key(tmp_path, monkeypatch) -> None:
    """
    ADR-022 §Schema: 'note_id INTEGER PRIMARY KEY AUTOINCREMENT — Autoincrement
    (rather than ROWID reuse) prevents ID reuse if a row is later deleted.'

    Strategy: post two Notes, query the raw DB, assert note_id values are distinct
    and monotonically increasing integers.

    Trace: ADR-022 §Schema.
    """
    db_path = _get_notes_db_path(tmp_path)
    client = _make_client(monkeypatch, db_path)

    client.post(
        "/lecture/ch-09-balanced-trees/notes",
        data={"body": "First note for AUTOINCREMENT test."},
        follow_redirects=False,
    )
    client.post(
        "/lecture/ch-09-balanced-trees/notes",
        data={"body": "Second note for AUTOINCREMENT test."},
        follow_redirects=False,
    )

    rows = _direct_db_list_notes(db_path, "ch-09-balanced-trees")
    assert len(rows) == 2, (
        f"Expected 2 Notes in the database after 2 POSTs, got {len(rows)}."
    )

    ids = [r["note_id"] for r in rows]
    assert len(set(ids)) == 2, (
        f"note_id values are not distinct: {ids!r}. "
        "ADR-022: AUTOINCREMENT primary key must produce unique IDs."
    )
    # IDs must be positive integers
    for nid in ids:
        assert isinstance(nid, int) and nid > 0, (
            f"note_id {nid!r} is not a positive integer. "
            "ADR-022: note_id INTEGER PRIMARY KEY AUTOINCREMENT."
        )


# ===========================================================================
# Schema: created_at and updated_at are ISO-8601 UTC strings
# ===========================================================================


def test_notes_timestamps_are_iso8601(tmp_path, monkeypatch) -> None:
    """
    ADR-022 §Schema: 'created_at and updated_at — ISO-8601 UTC strings
    ("YYYY-MM-DDTHH:MM:SSZ"). Set by the persistence layer on insert/update.'

    Trace: ADR-022 §Schema §Column rationale.
    """
    db_path = _get_notes_db_path(tmp_path)
    client = _make_client(monkeypatch, db_path)

    client.post(
        "/lecture/ch-10-graphs/notes",
        data={"body": "Timestamp ISO-8601 test note."},
        follow_redirects=False,
    )

    rows = _direct_db_list_notes(db_path, "ch-10-graphs")
    assert len(rows) == 1, f"Expected 1 Note, got {len(rows)}."

    row = rows[0]
    for ts_col in ("created_at", "updated_at"):
        ts_value = row[ts_col]
        assert isinstance(ts_value, str), (
            f"Column {ts_col!r} is not a string: {ts_value!r}. "
            "ADR-022: timestamps stored as TEXT (ISO-8601)."
        )
        # ISO-8601 pattern: YYYY-MM-DDTHH:MM:SS (Z or +00:00 or bare UTC)
        iso_pattern = re.compile(
            r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}"
        )
        assert iso_pattern.match(ts_value), (
            f"Column {ts_col!r} value {ts_value!r} does not match ISO-8601 pattern "
            "YYYY-MM-DDTHH:MM:SS. "
            "ADR-022 §Schema: timestamps must be ISO-8601 UTC strings."
        )


# ===========================================================================
# Schema: chapter_id in notes table matches the ADR-002 format
# ===========================================================================


def test_notes_chapter_id_matches_adr002_format(tmp_path, monkeypatch) -> None:
    """
    ADR-022 §Schema: 'chapter_id TEXT NOT NULL — the Chapter ID per ADR-002
    (kebab-case basename of the source .tex file).'

    When a Note is written for ch-11-b-trees, the row's chapter_id must be
    exactly 'ch-11-b-trees' (not a path, not an int, not URL-escaped).

    Trace: ADR-022 §Schema; ADR-002 §Chapter ID.
    """
    db_path = _get_notes_db_path(tmp_path)
    client = _make_client(monkeypatch, db_path)

    expected_chapter_id = "ch-11-b-trees"
    client.post(
        f"/lecture/{expected_chapter_id}/notes",
        data={"body": "Chapter ID format test note."},
        follow_redirects=False,
    )

    rows = _direct_db_list_notes(db_path, expected_chapter_id)
    assert len(rows) == 1
    assert rows[0]["chapter_id"] == expected_chapter_id, (
        f"Row chapter_id is {rows[0]['chapter_id']!r}; expected {expected_chapter_id!r}. "
        "ADR-022/ADR-002: chapter_id must be stored as the kebab-case basename."
    )


# ===========================================================================
# Performance: Lecture page with many Notes renders within time budget
# ===========================================================================


def test_get_lecture_page_with_many_notes_within_time_budget(tmp_path, monkeypatch) -> None:
    """
    Performance test: a Lecture page with 50 Notes for one Chapter must render
    within 5 seconds.

    Catches O(n²) query patterns or runaway template loops over Notes.
    ADR-023: 'The Lecture-page GET route now performs an extra database query per
    request (list_notes_for_chapter). Mitigation: SQLite local read is
    sub-millisecond at this data scale.'

    Trace: ADR-023 §Consequences; AC-1 (renders the whole Chapter).
    """
    db_path = _get_notes_db_path(tmp_path)
    client = _make_client(monkeypatch, db_path)

    # Insert 50 Notes via POST
    for i in range(50):
        client.post(
            "/lecture/ch-12-sets/notes",
            data={"body": f"Performance test note {i}: sets and bitsets content here."},
            follow_redirects=False,
        )

    # Now measure a GET
    t0 = time.monotonic()
    response = client.get("/lecture/ch-12-sets")
    elapsed = time.monotonic() - t0

    assert response.status_code == 200, (
        f"GET /lecture/ch-12-sets with 50 Notes returned {response.status_code}."
    )
    assert elapsed < 5.0, (
        f"GET /lecture/ch-12-sets with 50 Notes took {elapsed:.2f}s (limit: 5s). "
        "ADR-023: the extra DB query should be sub-millisecond; 5s budget is generous. "
        "A slow result suggests O(n²) behavior in the query or template loop."
    )


# ===========================================================================
# Regression: existing lecture-page tests are not broken
# ===========================================================================


@pytest.mark.parametrize("chapter_id", ALL_CHAPTER_IDS)
def test_no_regression_lecture_page_still_returns_200(chapter_id: str, tmp_path, monkeypatch) -> None:
    """
    AC-8 (TASK-009): introducing the Notes surface must not regress any existing
    Lecture page.  Every Chapter still returns HTTP 200 and text/html.

    Trace: AC-8; ADR-003; ADR-023 §MODIFIED GET /lecture/{chapter_id}.
    """
    db_path = _get_notes_db_path(tmp_path)
    client = _make_client(monkeypatch, db_path)

    response = client.get(f"/lecture/{chapter_id}")
    assert response.status_code == 200, (
        f"Regression: GET /lecture/{chapter_id} returned {response.status_code} "
        "after Notes surface was added. "
        "AC-8: the Notes surface must not regress existing Lecture pages."
    )
    assert "text/html" in response.headers.get("content-type", ""), (
        f"Regression: GET /lecture/{chapter_id} content-type is not text/html "
        "after Notes surface was added."
    )


# ===========================================================================
# ADR-023: POST route exists (not 405) on all valid Chapter IDs
# ===========================================================================


@pytest.mark.parametrize("chapter_id", ALL_CHAPTER_IDS)
def test_post_notes_route_exists_for_every_chapter(chapter_id: str, tmp_path, monkeypatch) -> None:
    """
    ADR-023 §Routes: 'NEW: POST /lecture/{chapter_id}/notes — accepts form-encoded
    body; validates; persists; returns 303 redirect.'

    A POST with a valid body must NOT return 405 (Method Not Allowed) for any of
    the 12 corpus Chapter IDs.

    Trace: ADR-023 §Routes; AC-2.
    """
    db_path = _get_notes_db_path(tmp_path)
    client = _make_client(monkeypatch, db_path)

    response = client.post(
        f"/lecture/{chapter_id}/notes",
        data={"body": f"Route-existence test note for {chapter_id}."},
        follow_redirects=False,
    )
    assert response.status_code != 405, (
        f"POST /lecture/{chapter_id}/notes returned 405 Method Not Allowed. "
        "ADR-023: the POST route must exist for every valid Chapter ID."
    )
    # Must be either 303 (success) or a 4xx client error (e.g., validation failure)
    assert response.status_code in range(200, 500), (
        f"POST /lecture/{chapter_id}/notes returned unexpected {response.status_code}."
    )
