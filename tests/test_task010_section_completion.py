"""
TASK-010: Section completion marking — per-Section "mark complete" toggle that persists.

Tests derive from the Acceptance Criteria in
`design_docs/tasks/TASK-010-section-completion-marking.md`
and from the two Accepted ADRs:
  ADR-024 — Section completion schema and persistence module:
             `section_completions(section_id PK, chapter_id, completed_at)`,
             presence-as-complete semantics, `app/persistence/section_completions.py`.
  ADR-025 — Section completion UI surface:
             `POST /lecture/{chapter_id}/sections/{section_number}/complete`
             with `action` form field, inline affordance next to `<h2>`, PRG redirect
             with URL fragment, three-layered state indicator.

Coverage matrix:
  Boundary:
    - test_completion_affordance_on_all_12_chapters: iterate all corpus Chapters (AC-1).
    - test_section_completions_table_no_user_id_column: schema boundary — user_id must be absent (AC-6/MC-7).
    - test_section_completions_required_columns_present: all three required columns present (AC-10/ADR-024).
    - test_post_complete_action_invalid_value_returns_400: boundary of valid action field values (AC-5/ADR-025).
  Edge:
    - test_mark_complete_idempotent: double-mark is a no-op (ADR-024: INSERT OR IGNORE) (AC-2/AC-5).
    - test_unmark_complete_idempotent: unmark an already-incomplete Section is no-op (AC-5).
    - test_completion_state_chapter_isolation: marking ch-A does not affect ch-B (AC-4).
    - test_mark_section_complete_returns_section_completion_dataclass: API shape (AC-10/ADR-024).
  Negative:
    - test_post_complete_unknown_chapter_returns_404: unknown chapter_id → 404 (ADR-025).
    - test_post_complete_unknown_section_returns_404: known chapter, bad section_number → 404 (ADR-025).
    - test_post_complete_missing_action_returns_400: missing action field → 400 (ADR-025).
    - test_post_complete_invalid_action_value_returns_400: bad action value → 400 (ADR-025).
    - test_mc10_no_sqlite3_import_outside_persistence_package: MC-10 grep (AC-6).
    - test_mc10_no_sql_literals_outside_persistence_package: MC-10 grep (AC-6).
    - test_mc6_completion_write_does_not_touch_content_latex: MC-6 (AC-6).
    - test_mc7_no_user_id_column: MC-7 (AC-6).
  Performance:
    - test_lecture_page_with_all_sections_complete_within_time_budget: marking all
      Sections of a Chapter complete and rendering the page is within 5s (AC-1/AC-2/ADR-025
      extra DB query per request).

pytestmark registers all tests under task("TASK-010").

CANNOT TEST AC-9: "when the human reviews fresh last-run Playwright screenshots per ADR-010,
then the completion affordance is visually present, legible, and stylistically consistent."
This is explicitly a human gate (visual review); it cannot be asserted programmatically.
See audit Run 003 for documentation.
"""

from __future__ import annotations

import pathlib
import re
import sqlite3
import time

import pytest

pytestmark = pytest.mark.task("TASK-010")

# ---------------------------------------------------------------------------
# Canonical Chapter IDs — same list as TASK-009
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

# Use ch-01 as the canonical test Chapter (has known sections 1-1 through 1-15)
TEST_CHAPTER_ID = "ch-01-cpp-refresher"
TEST_SECTION_NUMBER = "1-1"  # first section — boundary: first item in iteration
TEST_SECTION_ID = f"{TEST_CHAPTER_ID}#section-{TEST_SECTION_NUMBER}"

REPO_ROOT = pathlib.Path(__file__).parent.parent

# ---------------------------------------------------------------------------
# Helpers — deferred imports so collection succeeds before implementation
# ---------------------------------------------------------------------------


def _make_client(monkeypatch=None, db_path: str | None = None):
    """
    Return a FastAPI TestClient, optionally injecting NOTES_DB_PATH for test isolation.
    ADR-024: the same NOTES_DB_PATH env-var override (from ADR-022) controls both tables.
    """
    if monkeypatch is not None and db_path is not None:
        monkeypatch.setenv("NOTES_DB_PATH", db_path)

    from fastapi.testclient import TestClient  # noqa: PLC0415
    from app.main import app  # noqa: PLC0415

    return TestClient(app)


def _db_path(tmp_path: pathlib.Path) -> str:
    """Return a per-test isolated SQLite path."""
    return str(tmp_path / "test_completion.db")


def _direct_db_list_completions(db_path: str, chapter_id: str) -> list[dict]:
    """
    Query section_completions directly from SQLite (storage-level observer).
    Used for persistence-layer assertions without going through the app.
    """
    if not pathlib.Path(db_path).exists():
        return []
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.execute(
        "SELECT section_id, chapter_id, completed_at "
        "FROM section_completions WHERE chapter_id = ?",
        (chapter_id,),
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def _trigger_schema_bootstrap(client) -> None:
    """Issue a GET to any Lecture page to trigger persistence schema init."""
    client.get(f"/lecture/{TEST_CHAPTER_ID}")


# ===========================================================================
# AC-1 — Each Section has a visible per-Section completion affordance on
#         ALL 12 corpus Chapters
#
# Stronger AC: the rendered HTML must contain:
#   - a <form> targeting the per-Section completion route for at least one section
#   - a button labeled "Mark complete" (or "Mark incomplete" / "✓ Complete")
#   - the `section-completion-form` CSS class (ADR-025 architectural commitment)
# ===========================================================================


@pytest.mark.parametrize("chapter_id", ALL_CHAPTER_IDS)
def test_completion_affordance_on_all_12_chapters(
    chapter_id: str, tmp_path, monkeypatch
) -> None:
    """
    AC-1 (TASK-010): GET /lecture/{chapter_id} for every Chapter in the corpus
    renders a visible per-Section completion affordance on each Section.

    Stronger assertion (per test-writer AC critique): a trivially-passing test
    that only checks for 200 status would not catch a broken affordance. This
    test checks structural presence of the form + affordance class + button label
    per ADR-025's class-name commitments.

    Trace: AC-1; ADR-025 §Template placement; ADR-025 §Scope §Class names.
    """
    client = _make_client(monkeypatch, _db_path(tmp_path))

    response = client.get(f"/lecture/{chapter_id}")
    assert response.status_code == 200, (
        f"GET /lecture/{chapter_id} returned HTTP {response.status_code}; expected 200."
    )
    html = response.text

    # ADR-025: the completion form targets the per-Section route
    # At minimum one form action for this chapter's sections must appear.
    completion_route_pattern = re.compile(
        rf"/lecture/{re.escape(chapter_id)}/sections/[\d\-]+/complete"
    )
    assert completion_route_pattern.search(html), (
        f"GET /lecture/{chapter_id} — rendered HTML contains no form action matching "
        f"'/lecture/{chapter_id}/sections/*/complete'. "
        "AC-1/ADR-025: each Section must have a completion form targeting the "
        "POST /lecture/{chapter_id}/sections/{section_number}/complete route."
    )

    # ADR-025: the CSS class `section-completion-form` is the architectural commitment
    assert "section-completion-form" in html, (
        f"GET /lecture/{chapter_id} — rendered HTML does not contain the "
        "'section-completion-form' CSS class. "
        "AC-1/ADR-025: the completion form must carry the section-completion-form class."
    )

    # ADR-025: the button must be visible with the incomplete-state label
    assert "Mark complete" in html or "section-completion-button" in html, (
        f"GET /lecture/{chapter_id} — rendered HTML contains no 'Mark complete' button "
        "or 'section-completion-button' class. "
        "AC-1/ADR-025: each Section must have a button with the completion-button class."
    )

    # ADR-025: the action form field must be present
    assert 'name="action"' in html, (
        f"GET /lecture/{chapter_id} — rendered HTML contains no 'name=\"action\"' field. "
        "AC-1/ADR-025: each completion form must include a hidden action field "
        "(value='mark' or 'unmark')."
    )


# ===========================================================================
# AC-2 — Marking a Section complete: persists to DB and page shows it complete
# ===========================================================================


def test_post_complete_returns_303_redirect(tmp_path, monkeypatch) -> None:
    """
    AC-2 (TASK-010) / ADR-025: POST /lecture/{chapter_id}/sections/{n}/complete
    with action=mark returns HTTP 303 See Other (PRG idiom, mirroring ADR-023).

    Trace: AC-2; ADR-025 §Route shape ('HTTP 303 See Other').
    """
    client = _make_client(monkeypatch, _db_path(tmp_path))

    response = client.post(
        f"/lecture/{TEST_CHAPTER_ID}/sections/{TEST_SECTION_NUMBER}/complete",
        data={"action": "mark"},
        follow_redirects=False,
    )
    assert response.status_code == 303, (
        f"POST complete returned {response.status_code}; expected 303 See Other. "
        "AC-2/ADR-025: PRG redirect after successful mark must be 303."
    )


def test_post_complete_redirect_location_contains_chapter(tmp_path, monkeypatch) -> None:
    """
    AC-2 (TASK-010) / ADR-025 amended by ADR-031 (TASK-012 delta, supersedes ADR-030
    §Decision which superseded ADR-025 §Round-trip-return-point):

    AMENDMENT — ADR-031 (Accepted, 2026-05-11) supersedes ADR-030 §Decision.
    The 303 Location header now points to GET /lecture/{chapter_id}#section-{n}-end
    (a fragment anchored to the .section-end wrapper element which has
    id="section-{n-m}-end"). The ADR-030 assertion ('assert "#" not in location')
    is REMOVED; the Location must now carry a '#section-{n}-end' fragment.

    ADR-030 §Decision was empirically refuted by Playwright audit Run 006:
    Chromium reset scrollY to 0 on the fragment-less same-URL POST→303→GET navigation.
    ADR-031 picks the anchor + scroll-margin-top mechanism instead.

    Per CLAUDE.md / user-memory: "Test updates forced by Accepted ADRs are routine."

    Trace: AC-2; ADR-031 §Decision; ADR-031 §Test-writer pre-flag (item 2);
           supersedes ADR-030 §Decision (Run 004 amendment) which superseded
           ADR-025 §Round-trip return point.
    """
    client = _make_client(monkeypatch, _db_path(tmp_path))

    response = client.post(
        f"/lecture/{TEST_CHAPTER_ID}/sections/{TEST_SECTION_NUMBER}/complete",
        data={"action": "mark"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    location = response.headers.get("location", "")
    assert f"/lecture/{TEST_CHAPTER_ID}" in location, (
        f"303 Location is {location!r}; expected it to contain "
        f"'/lecture/{TEST_CHAPTER_ID}'. "
        "ADR-025/ADR-031: PRG must redirect to the Chapter's Lecture page."
    )
    # ADR-031 §Decision: the Location must carry '#section-{n}-end' fragment.
    # The .section-end wrapper gains id="section-{n-m}-end" in lecture.html.j2;
    # the CSS rule '.section-end { scroll-margin-top: 75vh; }' in lecture.css
    # (ADR-008: section-* → lecture.css) prevents the heading from snapping to the top.
    assert f"section-{TEST_SECTION_NUMBER}-end" in location, (
        f"303 Location {location!r} does not contain 'section-{TEST_SECTION_NUMBER}-end'. "
        "ADR-031 §Test-writer pre-flag (item 2): re-amended from "
        "'assert \"#\" not in location' (ADR-030 amendment, Run 004) to assert the "
        "#section-{n}-end fragment. The route handler must emit "
        f"url=f'/lecture/{{chapter_id}}#section-{{section_number}}-end' per "
        "ADR-031 §Decision. "
        "The new contract is tested comprehensively in "
        "test_task012_rhs_notes_rail_and_redirect.py."
    )


def test_post_mark_persists_to_database(tmp_path, monkeypatch) -> None:
    """
    AC-2 (TASK-010) / ADR-024: after POST action=mark, a row exists in the
    section_completions table in the SQLite database.

    This is the storage-level observer test (bypasses the app's render path)
    to verify the persistence layer actually wrote the row.

    ADR-024 §Presence-as-complete: presence of a row ≡ Section is complete.

    Trace: AC-2; ADR-024 §Schema; Manifest §7 'completion mark persists'.
    """
    db_path = _db_path(tmp_path)
    client = _make_client(monkeypatch, db_path)

    # Trigger schema creation
    _trigger_schema_bootstrap(client)

    # POST mark
    resp = client.post(
        f"/lecture/{TEST_CHAPTER_ID}/sections/{TEST_SECTION_NUMBER}/complete",
        data={"action": "mark"},
        follow_redirects=False,
    )
    assert resp.status_code == 303, (
        f"POST mark returned {resp.status_code}; prerequisite for storage check."
    )

    # Verify at the storage level
    rows = _direct_db_list_completions(db_path, TEST_CHAPTER_ID)
    matching = [r for r in rows if r["section_id"] == TEST_SECTION_ID]
    assert len(matching) == 1, (
        f"Expected 1 row in section_completions for section_id={TEST_SECTION_ID!r}, "
        f"found {len(matching)}. "
        "AC-2/ADR-024: mark_section_complete must insert a row (presence ≡ complete)."
    )
    assert matching[0]["chapter_id"] == TEST_CHAPTER_ID, (
        f"Row chapter_id is {matching[0]['chapter_id']!r}; expected {TEST_CHAPTER_ID!r}. "
        "ADR-024: the chapter_id column must be stored (redundant but indexed)."
    )
    # completed_at must be an ISO-8601 string
    iso_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")
    assert iso_pattern.match(matching[0]["completed_at"]), (
        f"completed_at value {matching[0]['completed_at']!r} is not ISO-8601. "
        "ADR-024: completed_at must be an ISO-8601 UTC timestamp."
    )


def test_marked_section_shown_as_complete_on_lecture_page(tmp_path, monkeypatch) -> None:
    """
    AC-2 (TASK-010): after marking Section as complete, a GET /lecture/{chapter_id}
    renders the Section with the 'complete' visual state indicators.

    ADR-025 §State indicator shape (three-layered):
      1. Button text '✓ Complete' (when complete)
      2. CSS modifier class `.section-completion-button--complete`
      3. CSS class `.section-complete` on the <section> element

    Trace: AC-2; ADR-025 §State indicator shape.
    """
    client = _make_client(monkeypatch, _db_path(tmp_path))

    # Mark the section
    client.post(
        f"/lecture/{TEST_CHAPTER_ID}/sections/{TEST_SECTION_NUMBER}/complete",
        data={"action": "mark"},
        follow_redirects=True,
    )

    # Reload the page
    response = client.get(f"/lecture/{TEST_CHAPTER_ID}")
    assert response.status_code == 200
    html = response.text

    # ADR-025: the section-complete CSS class must be present on the completed section
    assert "section-complete" in html, (
        "GET after mark — 'section-complete' CSS class not found in rendered HTML. "
        "AC-2/ADR-025: a marked-complete Section must carry the '.section-complete' class."
    )

    # ADR-025: the complete-state button modifier must be present
    assert "section-completion-button--complete" in html, (
        "GET after mark — 'section-completion-button--complete' not found in rendered HTML. "
        "AC-2/ADR-025: the complete-state button must carry the --complete modifier class."
    )

    # ADR-025: the action field must now say 'unmark' (so the user can toggle off)
    assert 'value="unmark"' in html, (
        "GET after mark — 'value=\"unmark\"' not found in rendered HTML. "
        "AC-2/ADR-025: after marking, the form must offer 'unmark' to toggle back."
    )


# ===========================================================================
# AC-3 — Persistence across server restart
# ===========================================================================


def test_completion_persists_across_app_restart(tmp_path, monkeypatch) -> None:
    """
    AC-3 (TASK-010) / Manifest §7: 'every … completion mark persists across sessions
    and is owned by the single user.'

    Simulates a server restart by:
      1. Creating TestClient A, marking a Section complete.
      2. Verifying the row exists in the raw DB (storage-level observer).
      3. Creating a NEW TestClient B pointing at the SAME database.
      4. Issuing GET /lecture/{chapter_id} on B.
      5. Asserting the Section is shown as complete.

    Trace: AC-3; Manifest §7 'persists across sessions'; ADR-024 §Cohabitation-validation;
    ADR-022 §NOTES_DB_PATH.
    """
    db_path = _db_path(tmp_path)
    monkeypatch.setenv("NOTES_DB_PATH", db_path)

    # --- Instance A: mark the Section ---
    from fastapi.testclient import TestClient  # noqa: PLC0415
    from app.main import app as app_a  # noqa: PLC0415

    client_a = TestClient(app_a)
    resp = client_a.post(
        f"/lecture/{TEST_CHAPTER_ID}/sections/{TEST_SECTION_NUMBER}/complete",
        data={"action": "mark"},
        follow_redirects=False,
    )
    assert resp.status_code == 303, (
        "Mark POST in instance A did not return 303 — prerequisite for restart test."
    )

    # Verify at storage level before restart
    rows = _direct_db_list_completions(db_path, TEST_CHAPTER_ID)
    assert any(r["section_id"] == TEST_SECTION_ID for r in rows), (
        f"Section {TEST_SECTION_ID!r} not found in DB after mark — "
        "prerequisite for restart persistence test. "
        "ADR-024: mark must insert a row immediately."
    )

    # --- Simulate restart: create a fresh TestClient B ---
    import importlib
    import app.main as main_module
    importlib.reload(main_module)
    from app.main import app as app_b  # noqa: PLC0415

    client_b = TestClient(app_b)
    response = client_b.get(f"/lecture/{TEST_CHAPTER_ID}")
    assert response.status_code == 200

    html = response.text
    assert "section-complete" in html, (
        "After simulated server restart (fresh TestClient, same DB), the 'section-complete' "
        "CSS class was NOT found in the rendered HTML. "
        "AC-3/Manifest §7: completion state must survive a server restart — it is read "
        "from the SQLite DB on every GET, not from in-process memory."
    )


# ===========================================================================
# AC-4 — Cross-Chapter isolation
# ===========================================================================


def test_completion_state_chapter_isolation(tmp_path, monkeypatch) -> None:
    """
    AC-4 (TASK-010): marking a Section in Chapter X does NOT cause any Section in
    Chapter Y to appear as complete.

    ADR-024: `chapter_id` is stored and used in `list_complete_section_ids_for_chapter`;
    the indexed per-Chapter query must filter exclusively by chapter_id.

    Trace: AC-4 ('no cross-Chapter leak, no stale "complete" state on Chapter Y');
    ADR-024 §list_complete_section_ids_for_chapter.
    """
    db_path = _db_path(tmp_path)
    client = _make_client(monkeypatch, db_path)

    chapter_x = "ch-01-cpp-refresher"
    section_x = "1-1"
    chapter_y = "ch-02-intro-to-algorithms"

    # Mark a Section in chapter_x
    resp = client.post(
        f"/lecture/{chapter_x}/sections/{section_x}/complete",
        data={"action": "mark"},
        follow_redirects=True,
    )
    assert resp.status_code == 200, "Mark + follow redirect must reach 200."

    # Visit chapter_y — no section there should show as complete
    response_y = client.get(f"/lecture/{chapter_y}")
    assert response_y.status_code == 200
    html_y = response_y.text

    assert "section-complete" not in html_y, (
        f"After marking a section in {chapter_x}, the rendered page for {chapter_y} "
        "contains the 'section-complete' CSS class. "
        "AC-4: completion state must be Chapter-scoped; no cross-Chapter contamination."
    )
    assert 'value="unmark"' not in html_y, (
        f"After marking a section in {chapter_x}, the page for {chapter_y} contains "
        "'value=\"unmark\"' — implying a Section in {chapter_y} is shown as complete. "
        "AC-4/ADR-024: chapter_id scoping must prevent cross-Chapter state leakage."
    )


def test_completing_in_chapter_a_does_not_appear_in_raw_db_for_chapter_b(
    tmp_path, monkeypatch
) -> None:
    """
    AC-4 (TASK-010) at the storage level: the section_completions rows written for
    Chapter A must have chapter_id = A, not chapter_id = B.

    Trace: AC-4; ADR-024 §chapter_id column ('enables per-chapter queries').
    """
    db_path = _db_path(tmp_path)
    client = _make_client(monkeypatch, db_path)
    _trigger_schema_bootstrap(client)

    client.post(
        "/lecture/ch-01-cpp-refresher/sections/1-1/complete",
        data={"action": "mark"},
        follow_redirects=False,
    )

    rows_for_ch2 = _direct_db_list_completions(db_path, "ch-02-intro-to-algorithms")
    assert rows_for_ch2 == [], (
        f"section_completions rows for ch-02-intro-to-algorithms after marking ch-01 "
        f"section: {rows_for_ch2!r}. "
        "AC-4/ADR-024: rows must be stored with the correct chapter_id."
    )


# ===========================================================================
# AC-5 — Toggle semantics (mark → unmark → mark cycle)
# ===========================================================================


def test_unmark_removes_completion(tmp_path, monkeypatch) -> None:
    """
    AC-5 (TASK-010): after marking a Section complete, POSTing action=unmark
    removes the completion — the page no longer shows the Section as complete.

    ADR-024 §Presence-as-complete: unmark deletes the row; its absence ≡ incomplete.
    ADR-025 §action field: 'unmark' is a valid value.

    Trace: AC-5 ('re-clicking the affordance unmarks the Section');
    ADR-024 §unmark_section_complete; ADR-025 §action form field.
    """
    client = _make_client(monkeypatch, _db_path(tmp_path))

    # Mark first
    client.post(
        f"/lecture/{TEST_CHAPTER_ID}/sections/{TEST_SECTION_NUMBER}/complete",
        data={"action": "mark"},
        follow_redirects=True,
    )

    html_after_mark = client.get(f"/lecture/{TEST_CHAPTER_ID}").text
    assert "section-complete" in html_after_mark, (
        "Prerequisite: Section must show as complete before unmark test."
    )

    # Now unmark
    resp_unmark = client.post(
        f"/lecture/{TEST_CHAPTER_ID}/sections/{TEST_SECTION_NUMBER}/complete",
        data={"action": "unmark"},
        follow_redirects=False,
    )
    assert resp_unmark.status_code == 303, (
        f"POST action=unmark returned {resp_unmark.status_code}; expected 303."
    )

    # Page should no longer show the section as complete
    html_after_unmark = client.get(f"/lecture/{TEST_CHAPTER_ID}").text
    assert "section-completion-button--complete" not in html_after_unmark, (
        "After unmark, 'section-completion-button--complete' is still in the HTML. "
        "AC-5: unmark must remove the complete-state visual indicator."
    )
    assert 'value="unmark"' not in html_after_unmark, (
        "After unmark, 'value=\"unmark\"' is still in the HTML. "
        "AC-5: after unmark, the form must revert to offering 'mark'."
    )


def test_unmark_removes_db_row(tmp_path, monkeypatch) -> None:
    """
    AC-5 (TASK-010) at the storage level: after unmark, the section_completions
    row must be deleted (presence-as-complete: absence ≡ incomplete).

    ADR-024 §Presence-as-complete: 'unmark_section_complete() deletes the row.'

    Trace: AC-5; ADR-024 §unmark_section_complete; ADR-024 §Consequences
    'Persisting completion history … is impossible. Unmarking deletes the row.'
    """
    db_path = _db_path(tmp_path)
    client = _make_client(monkeypatch, db_path)
    _trigger_schema_bootstrap(client)

    # Mark
    client.post(
        f"/lecture/{TEST_CHAPTER_ID}/sections/{TEST_SECTION_NUMBER}/complete",
        data={"action": "mark"},
        follow_redirects=False,
    )
    rows_after_mark = _direct_db_list_completions(db_path, TEST_CHAPTER_ID)
    assert any(r["section_id"] == TEST_SECTION_ID for r in rows_after_mark), (
        "Prerequisite: row must exist after mark."
    )

    # Unmark
    client.post(
        f"/lecture/{TEST_CHAPTER_ID}/sections/{TEST_SECTION_NUMBER}/complete",
        data={"action": "unmark"},
        follow_redirects=False,
    )
    rows_after_unmark = _direct_db_list_completions(db_path, TEST_CHAPTER_ID)
    matching = [r for r in rows_after_unmark if r["section_id"] == TEST_SECTION_ID]
    assert matching == [], (
        f"After unmark, the section_completions row for {TEST_SECTION_ID!r} still exists. "
        "AC-5/ADR-024: unmark_section_complete must delete the row (presence-as-complete: "
        "row absence ≡ incomplete)."
    )


def test_mark_complete_idempotent(tmp_path, monkeypatch) -> None:
    """
    AC-5 edge case: marking an already-complete Section twice (double-click) is a
    no-op — exactly one row exists, not two, and the page still shows complete.

    ADR-024: 'mark_section_complete is implemented as INSERT OR IGNORE so calling
    it on an already-complete Section is a no-op rather than an error.'

    Trace: AC-5; ADR-024 §INSERT-OR-IGNORE; ADR-025 §action-field-idempotent.
    """
    db_path = _db_path(tmp_path)
    client = _make_client(monkeypatch, db_path)
    _trigger_schema_bootstrap(client)

    # First mark
    client.post(
        f"/lecture/{TEST_CHAPTER_ID}/sections/{TEST_SECTION_NUMBER}/complete",
        data={"action": "mark"},
        follow_redirects=False,
    )
    # Second mark (double-click simulation)
    resp_second = client.post(
        f"/lecture/{TEST_CHAPTER_ID}/sections/{TEST_SECTION_NUMBER}/complete",
        data={"action": "mark"},
        follow_redirects=False,
    )
    # Must not error — 303 expected
    assert resp_second.status_code == 303, (
        f"Second mark returned {resp_second.status_code}; expected 303 (no-op, not error). "
        "ADR-024: INSERT OR IGNORE — double-mark must be a no-op, never an error."
    )

    # Exactly one row in the DB
    rows = _direct_db_list_completions(db_path, TEST_CHAPTER_ID)
    matching = [r for r in rows if r["section_id"] == TEST_SECTION_ID]
    assert len(matching) == 1, (
        f"Expected exactly 1 completion row after double-mark; got {len(matching)}. "
        "ADR-024: INSERT OR IGNORE prevents duplicate rows."
    )


def test_unmark_complete_idempotent(tmp_path, monkeypatch) -> None:
    """
    AC-5 edge case: unmarking a Section that is NOT complete is a no-op — no error.

    ADR-024: 'unmark_section_complete() is idempotent — unmarking an already-unmarked
    Section is a no-op (no error).'

    Trace: AC-5; ADR-024 §unmark_section_complete ('idempotent — no error').
    """
    client = _make_client(monkeypatch, _db_path(tmp_path))

    # Unmark without first marking — must not 500
    resp = client.post(
        f"/lecture/{TEST_CHAPTER_ID}/sections/{TEST_SECTION_NUMBER}/complete",
        data={"action": "unmark"},
        follow_redirects=False,
    )
    assert resp.status_code == 303, (
        f"Unmark on a not-complete Section returned {resp.status_code}; expected 303. "
        "ADR-024: unmark is idempotent — 'unmarking an already-unmarked Section is a "
        "no-op (no error).'  A 500 here is a bug."
    )


def test_mark_unmark_mark_toggle_cycle(tmp_path, monkeypatch) -> None:
    """
    AC-5 full toggle cycle: mark → unmark → mark, verify state at each step.

    Trace: AC-5 ('toggle, not append-only — incomplete is the default; complete is
    the toggle-on state; users can change their mind').
    """
    db_path = _db_path(tmp_path)
    client = _make_client(monkeypatch, db_path)
    _trigger_schema_bootstrap(client)

    def row_exists() -> bool:
        rows = _direct_db_list_completions(db_path, TEST_CHAPTER_ID)
        return any(r["section_id"] == TEST_SECTION_ID for r in rows)

    # Initial state: not complete
    assert not row_exists(), "Initial state must be incomplete."

    # Mark
    client.post(
        f"/lecture/{TEST_CHAPTER_ID}/sections/{TEST_SECTION_NUMBER}/complete",
        data={"action": "mark"},
        follow_redirects=False,
    )
    assert row_exists(), "After mark: row must exist."

    # Unmark
    client.post(
        f"/lecture/{TEST_CHAPTER_ID}/sections/{TEST_SECTION_NUMBER}/complete",
        data={"action": "unmark"},
        follow_redirects=False,
    )
    assert not row_exists(), "After unmark: row must not exist."

    # Mark again
    client.post(
        f"/lecture/{TEST_CHAPTER_ID}/sections/{TEST_SECTION_NUMBER}/complete",
        data={"action": "mark"},
        follow_redirects=False,
    )
    assert row_exists(), "After second mark: row must exist again."


# ===========================================================================
# AC-6 — Manifest-conformance: MC-6, MC-7, MC-10 PASS for the new module
# ===========================================================================


def test_mc10_no_sqlite3_import_outside_persistence_package() -> None:
    """
    AC-6 (TASK-010) / MC-10 (active per ADR-022, extended by ADR-024):
    `import sqlite3` must appear ONLY in files under `app/persistence/`.

    The new `section_completions.py` module joins the existing boundary; it must
    not trigger a new violation at `app/main.py` or any other route-layer file.

    Trace: AC-6; ADR-022 §Package boundary; ADR-024 §MC-10; MC-10.
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
        f"MC-10 BLOCKER: `import sqlite3` found outside `app/persistence/` in: "
        f"{violations!r}. "
        "AC-6/ADR-024: the new section_completions module must not cause a new "
        "sqlite3 import to leak into routes or other non-persistence modules."
    )


def test_mc10_no_sql_literals_outside_persistence_package() -> None:
    """
    AC-6 (TASK-010) / MC-10: SQL string literals must appear ONLY in
    files under `app/persistence/`.

    The completion route handler in app/main.py must call only the typed
    public functions (mark_section_complete, etc.) — never embed SQL.

    Trace: AC-6; ADR-024 §SQL literals confined to module; MC-10.
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
            continue
        except ValueError:
            pass
        text = py_file.read_text(encoding="utf-8")
        if sql_keywords_pattern.search(text):
            violations.append(str(py_file))

    assert violations == [], (
        f"MC-10 BLOCKER: SQL string literals found outside `app/persistence/` in: "
        f"{violations!r}. "
        "AC-6/ADR-024: route handlers must call only typed public functions, "
        "never embed SQL string literals."
    )


def test_mc7_no_user_id_column_in_section_completions(tmp_path, monkeypatch) -> None:
    """
    AC-6 (TASK-010) / MC-7 (single user, architecture portion active per ADR-022):
    the `section_completions` table must have NO `user_id` column.

    ADR-024 §Schema: 'Explicitly omitted: no `user_id` column. Manifest §5/§6/§7
    (single user). MC-7's architecture portion (active per ADR-022) is honored.'
    ADR-024 §Consequences: 'A `user_id` column on `section_completions`. Forbidden by MC-7.'

    Trace: AC-6; Manifest §5/§6/§7 'No multi-user features'; ADR-024 §Schema; MC-7.
    """
    db_path = _db_path(tmp_path)
    client = _make_client(monkeypatch, db_path)
    _trigger_schema_bootstrap(client)

    assert pathlib.Path(db_path).exists(), (
        f"Database not created at {db_path} after GET. "
        "ADR-022: the persistence layer must create data/notes.db on first connection."
    )

    conn = sqlite3.connect(db_path)
    cur = conn.execute("PRAGMA table_info(section_completions)")
    columns = {row[1] for row in cur.fetchall()}
    conn.close()

    assert columns, (
        "section_completions table has no columns — the table was not created. "
        "ADR-024: the schema bootstrap must create section_completions."
    )
    assert "user_id" not in columns, (
        f"The 'section_completions' table contains a 'user_id' column. "
        f"Columns found: {columns!r}. "
        "AC-6/MC-7: manifest §5/§6/§7 (single user) and ADR-024 §Schema explicitly "
        "forbid a user_id column."
    )
    # Also assert no marked_by column (equivalent per-user column)
    assert "marked_by" not in columns, (
        f"The 'section_completions' table contains a 'marked_by' column. "
        f"Columns found: {columns!r}. "
        "ADR-024: no per-user partitioning columns of any kind (MC-7)."
    )


def test_section_completions_required_columns_present(tmp_path, monkeypatch) -> None:
    """
    AC-10 (TASK-010): the `section_completions` table has exactly the columns
    committed to by ADR-024: section_id, chapter_id, completed_at.

    Trace: AC-10; ADR-024 §Schema.
    """
    db_path = _db_path(tmp_path)
    client = _make_client(monkeypatch, db_path)
    _trigger_schema_bootstrap(client)

    conn = sqlite3.connect(db_path)
    cur = conn.execute("PRAGMA table_info(section_completions)")
    columns = {row[1] for row in cur.fetchall()}
    conn.close()

    required = {"section_id", "chapter_id", "completed_at"}
    missing = required - columns
    assert not missing, (
        f"section_completions table is missing required columns: {missing!r}. "
        f"Columns found: {columns!r}. "
        "ADR-024 §Schema: required columns are section_id (PK), chapter_id, completed_at."
    )


def test_mc6_completion_write_does_not_touch_content_latex(
    tmp_path, monkeypatch
) -> None:
    """
    AC-6 (TASK-010) / MC-6: a completion POST must not open any file under
    `content/latex/` for write.

    Manifest §5 'No in-app authoring of lecture content'. ADR-024: completion
    writes go to `data/notes.db` (the NOTES_DB_PATH path), never to content/latex/.

    Strategy: spy on builtins.open for write-mode opens under content/latex/;
    POST action=mark; assert no write-mode opens happened there.

    Trace: AC-6; Manifest §5/§6; ADR-024 §Lecture-source-read-only; MC-6.
    """
    import builtins

    content_latex_abs = str(REPO_ROOT / "content" / "latex")
    write_violations: list[str] = []
    original_open = builtins.open

    def spying_open(file, mode="r", *args, **kwargs):
        path_str = str(file)
        if content_latex_abs in path_str and any(
            str(mode).startswith(m) for m in {"w", "a", "x"}
        ):
            write_violations.append(path_str)
        return original_open(file, mode, *args, **kwargs)

    db_path = _db_path(tmp_path)
    monkeypatch.setenv("NOTES_DB_PATH", db_path)
    monkeypatch.setattr(builtins, "open", spying_open)

    from fastapi.testclient import TestClient  # noqa: PLC0415
    from app.main import app  # noqa: PLC0415

    client = TestClient(app)
    client.post(
        f"/lecture/{TEST_CHAPTER_ID}/sections/{TEST_SECTION_NUMBER}/complete",
        data={"action": "mark"},
        follow_redirects=False,
    )

    assert write_violations == [], (
        f"MC-6 BLOCKER: completion POST opened files under content/latex/ for write: "
        f"{write_violations!r}. "
        "AC-6/ADR-024: writes must go only to data/notes.db — never to content/latex/."
    )


# ===========================================================================
# AC-7 — No regressions: existing lecture pages still return 200
# ===========================================================================


@pytest.mark.parametrize("chapter_id", ALL_CHAPTER_IDS)
def test_no_regression_lecture_page_still_returns_200(
    chapter_id: str, tmp_path, monkeypatch
) -> None:
    """
    AC-7 (TASK-010): adding the completion surface must not regress any existing
    Lecture page. Every Chapter still returns HTTP 200 and text/html.

    Trace: AC-7; ADR-003; ADR-025 §MODIFIED GET /lecture/{chapter_id}.
    """
    client = _make_client(monkeypatch, _db_path(tmp_path))

    response = client.get(f"/lecture/{chapter_id}")
    assert response.status_code == 200, (
        f"Regression: GET /lecture/{chapter_id} returned {response.status_code} "
        "after completion surface was added. "
        "AC-7: the completion surface must not regress existing Lecture pages."
    )
    assert "text/html" in response.headers.get("content-type", ""), (
        f"Regression: GET /lecture/{chapter_id} content-type is not text/html "
        "after completion surface was added."
    )


# ===========================================================================
# AC-10 — Persistence module exposes the ADR-024 public API from __init__.py
# ===========================================================================


def test_persistence_init_exports_completion_functions() -> None:
    """
    AC-10 (TASK-010) / ADR-024 §Module-level integration with __init__.py:
    `app/persistence/__init__.py` must export the four new completion functions
    and the SectionCompletion dataclass.

    ADR-024 exports: mark_section_complete, unmark_section_complete,
    is_section_complete, list_complete_section_ids_for_chapter, SectionCompletion.

    Route handlers import only from `app.persistence` (no deep imports).

    Trace: AC-10; ADR-024 §Module path and public API; ADR-024 §__init__.py re-export.
    """
    import app.persistence as persistence  # noqa: PLC0415

    required_exports = {
        "mark_section_complete",
        "unmark_section_complete",
        "is_section_complete",
        "list_complete_section_ids_for_chapter",
        "SectionCompletion",
    }
    for name in required_exports:
        assert hasattr(persistence, name), (
            f"app.persistence does not export '{name}'. "
            f"AC-10/ADR-024: __init__.py must re-export all completion public functions. "
            f"Missing: {name!r}"
        )


def test_mark_section_complete_returns_section_completion_dataclass(
    tmp_path, monkeypatch
) -> None:
    """
    AC-10 (TASK-010) / ADR-024 §API rationale:
    `mark_section_complete(section_id, chapter_id)` must return a SectionCompletion
    dataclass with section_id, chapter_id, and completed_at fields.

    ADR-024: 'mark_section_complete returns the dataclass so callers (and tests)
    can assert on the returned completed_at without a follow-up read.'

    Trace: AC-10; ADR-024 §mark_section_complete returns the dataclass.
    """
    db_path = _db_path(tmp_path)
    monkeypatch.setenv("NOTES_DB_PATH", db_path)

    # Trigger schema init
    from fastapi.testclient import TestClient  # noqa: PLC0415
    from app.main import app  # noqa: PLC0415

    TestClient(app).get(f"/lecture/{TEST_CHAPTER_ID}")

    import app.persistence as persistence  # noqa: PLC0415

    result = persistence.mark_section_complete(
        section_id=TEST_SECTION_ID,
        chapter_id=TEST_CHAPTER_ID,
    )
    assert result is not None, (
        "mark_section_complete returned None; expected a SectionCompletion dataclass. "
        "ADR-024: the function must return the persisted dataclass."
    )
    assert hasattr(result, "section_id"), (
        f"Return value {result!r} has no 'section_id' attribute. "
        "ADR-024: SectionCompletion dataclass must have section_id, chapter_id, completed_at."
    )
    assert result.section_id == TEST_SECTION_ID, (
        f"section_id mismatch: got {result.section_id!r}, expected {TEST_SECTION_ID!r}."
    )
    assert result.chapter_id == TEST_CHAPTER_ID, (
        f"chapter_id mismatch: got {result.chapter_id!r}, expected {TEST_CHAPTER_ID!r}."
    )
    assert hasattr(result, "completed_at") and result.completed_at, (
        f"SectionCompletion.completed_at is missing or empty: {result!r}. "
        "ADR-024: completed_at must be set at mark time."
    )


def test_list_complete_section_ids_for_chapter_returns_section_ids(
    tmp_path, monkeypatch
) -> None:
    """
    AC-10 (TASK-010): `list_complete_section_ids_for_chapter(chapter_id)` returns
    only the section IDs for the given chapter, as a list of strings.

    ADR-024: the function returns `list[str]` (Section IDs, not SectionCompletion objects).

    Trace: AC-10; ADR-024 §list_complete_section_ids_for_chapter.
    """
    db_path = _db_path(tmp_path)
    monkeypatch.setenv("NOTES_DB_PATH", db_path)

    from fastapi.testclient import TestClient  # noqa: PLC0415
    from app.main import app  # noqa: PLC0415

    TestClient(app).get(f"/lecture/{TEST_CHAPTER_ID}")

    import app.persistence as persistence  # noqa: PLC0415

    # Mark two sections
    persistence.mark_section_complete(
        section_id=f"{TEST_CHAPTER_ID}#section-1-1",
        chapter_id=TEST_CHAPTER_ID,
    )
    persistence.mark_section_complete(
        section_id=f"{TEST_CHAPTER_ID}#section-1-2",
        chapter_id=TEST_CHAPTER_ID,
    )

    result = persistence.list_complete_section_ids_for_chapter(TEST_CHAPTER_ID)
    assert isinstance(result, list), (
        f"list_complete_section_ids_for_chapter returned {type(result)!r}; expected list."
    )
    assert f"{TEST_CHAPTER_ID}#section-1-1" in result, (
        "section-1-1 not in list after marking."
    )
    assert f"{TEST_CHAPTER_ID}#section-1-2" in result, (
        "section-1-2 not in list after marking."
    )

    # Must be strings, not dataclass objects
    for item in result:
        assert isinstance(item, str), (
            f"list_complete_section_ids_for_chapter returned non-string item: {item!r}. "
            "ADR-024: the function returns list[str] (Section IDs), not SectionCompletion objects."
        )


def test_is_section_complete_returns_bool(tmp_path, monkeypatch) -> None:
    """
    AC-10 (TASK-010): `is_section_complete(section_id)` returns False before
    marking, True after marking, and False again after unmarking.

    ADR-024: the function returns bool.

    Trace: AC-10; ADR-024 §is_section_complete returns bool.
    """
    db_path = _db_path(tmp_path)
    monkeypatch.setenv("NOTES_DB_PATH", db_path)

    from fastapi.testclient import TestClient  # noqa: PLC0415
    from app.main import app  # noqa: PLC0415

    TestClient(app).get(f"/lecture/{TEST_CHAPTER_ID}")

    import app.persistence as persistence  # noqa: PLC0415

    # Before mark
    result_before = persistence.is_section_complete(TEST_SECTION_ID)
    assert result_before is False, (
        f"is_section_complete before marking returned {result_before!r}; expected False."
    )

    # After mark
    persistence.mark_section_complete(
        section_id=TEST_SECTION_ID, chapter_id=TEST_CHAPTER_ID
    )
    result_after_mark = persistence.is_section_complete(TEST_SECTION_ID)
    assert result_after_mark is True, (
        f"is_section_complete after marking returned {result_after_mark!r}; expected True."
    )

    # After unmark
    persistence.unmark_section_complete(TEST_SECTION_ID)
    result_after_unmark = persistence.is_section_complete(TEST_SECTION_ID)
    assert result_after_unmark is False, (
        f"is_section_complete after unmarking returned {result_after_unmark!r}; expected False."
    )


# ===========================================================================
# AC-11 — Schema does not foreclose Mandatory-only progress view
#
# ASSUMPTION: AC-11 is a "shape" requirement — the schema must store chapter_id
# so that Mandatory-only filtering is possible by joining with chapter_designation().
# The test verifies that chapter_id is stored and matches the ADR-002 format,
# making it usable for designation queries. No Mandatory-only UI is tested here.
# ===========================================================================


def test_completed_section_row_stores_chapter_id_queryable(
    tmp_path, monkeypatch
) -> None:
    """
    AC-11 (TASK-010): the section_completions schema stores `chapter_id` as a
    separate, indexed column, enabling future Mandatory-only progress queries
    without full-table LIKE scans.

    ADR-024 §chapter_id column rationale: 'enables per-chapter queries … and lets
    future queries use clean SQL without parsing the composite ID.'
    Manifest §6: 'Mandatory and Optional honored everywhere.'

    This test verifies the stored chapter_id matches the ADR-002 Chapter ID format
    (not a path, not an int, not URL-escaped) — making it joinable with
    `chapter_designation(chapter_id)` in a future filtered view.

    Trace: AC-11; ADR-024 §chapter_id column; Manifest §6 'Mandatory/Optional honored'.
    """
    db_path = _db_path(tmp_path)
    client = _make_client(monkeypatch, db_path)
    _trigger_schema_bootstrap(client)

    # Mark a section in a Mandatory Chapter (ch-01 through ch-06)
    mandatory_chapter = "ch-01-cpp-refresher"
    client.post(
        f"/lecture/{mandatory_chapter}/sections/1-1/complete",
        data={"action": "mark"},
        follow_redirects=False,
    )

    rows = _direct_db_list_completions(db_path, mandatory_chapter)
    assert rows, f"No completion rows for {mandatory_chapter!r} after mark."
    row = rows[0]

    # chapter_id must be a plain ADR-002 ID (not a path, not URL-encoded)
    stored_chapter_id = row["chapter_id"]
    assert stored_chapter_id == mandatory_chapter, (
        f"chapter_id stored as {stored_chapter_id!r}; expected {mandatory_chapter!r}. "
        "AC-11/ADR-024: chapter_id must be stored in ADR-002 format to be usable "
        "with chapter_designation() for Mandatory-only filtering."
    )
    # Must be kebab-case (no path separators, no URL encoding)
    assert "/" not in stored_chapter_id and "%" not in stored_chapter_id, (
        f"chapter_id {stored_chapter_id!r} contains path separators or URL encoding. "
        "ADR-024: chapter_id must be a plain kebab-case Chapter ID."
    )


# ===========================================================================
# Negative tests — route validation (ADR-025 §Validation)
# ===========================================================================


def test_post_complete_unknown_chapter_returns_404(tmp_path, monkeypatch) -> None:
    """
    ADR-025 §Validation: POST to an unknown chapter_id must return HTTP 404.

    'The route handler validates chapter_id against the discovered Chapter set
    (tex_path.exists() check). Unknown chapter_id returns HTTP 404.'

    PINNED CONTRACT: HTTP 404 (not 500, not 200).

    Trace: ADR-025 §Validation; ADR-023 §Validation (precedent).
    """
    client = _make_client(monkeypatch, _db_path(tmp_path))

    response = client.post(
        "/lecture/ch-99-does-not-exist/sections/1-1/complete",
        data={"action": "mark"},
        follow_redirects=False,
    )
    assert response.status_code == 404, (
        f"POST complete for unknown chapter returned {response.status_code}; expected 404. "
        "ADR-025: unknown chapter_id must return 404, not 500 or 200."
    )


def test_post_complete_unknown_section_returns_404(tmp_path, monkeypatch) -> None:
    """
    ADR-025 §Validation: POST with a valid chapter_id but an unknown section_number
    must return HTTP 404.

    'The route handler validates {chapter_id}#section-{section_number} against the
    parent Chapter's discovered Sections. Unknown Section returns HTTP 404.'

    PINNED CONTRACT: HTTP 404.

    Trace: ADR-025 §Validation; ADR-024 §Section-id-validation.
    """
    client = _make_client(monkeypatch, _db_path(tmp_path))

    # ch-01-cpp-refresher is valid; section 99-99 does not exist
    response = client.post(
        f"/lecture/{TEST_CHAPTER_ID}/sections/99-99/complete",
        data={"action": "mark"},
        follow_redirects=False,
    )
    assert response.status_code == 404, (
        f"POST complete for unknown section_number returned {response.status_code}; "
        "expected 404. "
        "ADR-025: unknown section number must return 404 to prevent orphan completion rows."
    )


def test_post_complete_missing_action_returns_400(tmp_path, monkeypatch) -> None:
    """
    ADR-025 §Validation: POST with no `action` field must return HTTP 400.

    'The route handler validates `action` is exactly "mark" or "unmark". Any other
    value (including missing) returns HTTP 400.'

    PINNED CONTRACT: HTTP 400.

    Trace: ADR-025 §Validation §action field.
    """
    client = _make_client(monkeypatch, _db_path(tmp_path))

    response = client.post(
        f"/lecture/{TEST_CHAPTER_ID}/sections/{TEST_SECTION_NUMBER}/complete",
        data={},  # no action field
        follow_redirects=False,
    )
    assert response.status_code == 400, (
        f"POST complete with missing action field returned {response.status_code}; "
        "expected 400. "
        "ADR-025: missing action field must be rejected with HTTP 400."
    )


def test_post_complete_invalid_action_value_returns_400(tmp_path, monkeypatch) -> None:
    """
    ADR-025 §Validation / boundary test for the action field:
    POST with action='delete' (not 'mark' or 'unmark') must return HTTP 400.

    'Any other value (including missing) returns HTTP 400.'

    PINNED CONTRACT: HTTP 400.

    Trace: ADR-025 §Validation; AC-5 (boundary of valid action values).
    """
    client = _make_client(monkeypatch, _db_path(tmp_path))

    for invalid_action in ("delete", "toggle", "yes", "", "MARK"):
        response = client.post(
            f"/lecture/{TEST_CHAPTER_ID}/sections/{TEST_SECTION_NUMBER}/complete",
            data={"action": invalid_action},
            follow_redirects=False,
        )
        assert response.status_code == 400, (
            f"POST complete with action={invalid_action!r} returned "
            f"{response.status_code}; expected 400. "
            "ADR-025: only 'mark' and 'unmark' are valid action values; anything "
            f"else must be rejected with HTTP 400. Got {response.status_code} for "
            f"action={invalid_action!r}."
        )


# ===========================================================================
# Performance — Lecture page with all Sections complete renders within budget
# ===========================================================================


def test_lecture_page_with_all_sections_complete_within_time_budget(
    tmp_path, monkeypatch
) -> None:
    """
    Performance test: after marking multiple sections complete, the Lecture page
    must render within 5 seconds.

    ADR-025 §Consequences: 'The Lecture-page GET route now performs an extra
    database query per request (list_complete_section_ids_for_chapter).
    Mitigation: SQLite local read is sub-millisecond at this data scale.'

    Catches O(n²) completion queries or runaway template loops over sections.

    Trace: AC-1 (renders all Sections); AC-2 (completion state reflected);
    ADR-025 §Consequences §Performance.
    """
    db_path = _db_path(tmp_path)
    monkeypatch.setenv("NOTES_DB_PATH", db_path)

    from fastapi.testclient import TestClient  # noqa: PLC0415
    from app.main import app  # noqa: PLC0415

    client = TestClient(app)
    _trigger_schema_bootstrap(client)

    import app.persistence as persistence  # noqa: PLC0415

    # Mark all 15 sections in ch-01 as complete
    for n in range(1, 16):
        section_id = f"{TEST_CHAPTER_ID}#section-1-{n}"
        try:
            persistence.mark_section_complete(
                section_id=section_id, chapter_id=TEST_CHAPTER_ID
            )
        except Exception:
            # Section may not exist (e.g. if the corpus uses a different numbering).
            # Skip non-existent sections rather than failing the performance test.
            pass

    t0 = time.monotonic()
    response = client.get(f"/lecture/{TEST_CHAPTER_ID}")
    elapsed = time.monotonic() - t0

    assert response.status_code == 200, (
        f"GET /lecture/{TEST_CHAPTER_ID} with completions returned {response.status_code}."
    )
    assert elapsed < 5.0, (
        f"GET /lecture/{TEST_CHAPTER_ID} with all Sections complete took {elapsed:.2f}s "
        "(limit: 5s). "
        "ADR-025: the extra completion DB query must be sub-millisecond; "
        "5s budget is generous. A slow result suggests O(n²) query pattern."
    )
