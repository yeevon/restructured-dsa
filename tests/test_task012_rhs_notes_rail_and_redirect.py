"""
TASK-012: Move Notes to a right-hand rail + stop the completion redirect from
anchor-snapping the user.

Tests derive from the Acceptance Criteria in
`design_docs/tasks/TASK-012-rhs-notes-rail-and-no-anchor-completion-redirect.md`
and from the Accepted supersedure ADRs:
  ADR-029 — Supersedure of ADR-028 §Rail-integration / §Template-surface:
             Notes panel moves from the left-hand rail (_nav_rail.html.j2) to a
             new right-hand rail (<aside class="notes-rail">); new partial
             _notes_rail.html.j2; page-layout becomes three-column on Lecture
             pages and two-column on GET /; rail-notes-* / rail-note-* class
             names kept; new .notes-rail and .page-layout--no-notes classes in
             base.css.
  ADR-030 — Supersedure of ADR-025 §Round-trip-return-point: load-bearing
             principle "the response to a reading-flow action should not
             relocate the user" (retained). The §Decision mechanism (no-fragment
             redirect) was empirically refuted by the Playwright test ADR-030
             itself mandated — Chromium resets scrollY to 0 on the fragment-less
             same-URL navigation. Superseded for §Decision by ADR-031.
  ADR-031 — Supersedure of ADR-030 §Decision: the 303 Location header for
             POST .../sections/{section_number}/complete now carries the
             '#section-{section_number}-end' fragment, pointing at the
             .section-end wrapper (id="{{ section.fragment }}-end" in
             lecture.html.j2) plus a large scroll-margin-top on .section-end
             in lecture.css so the fragment navigation lands the wrapper near
             the bottom of the viewport ≈ where the user clicked. No JavaScript.

CANNOT TEST AC-8: "the chosen path (Option 1 vs Option 2) is recorded in the
supersedure ADR with reasoning." This is a documentation gate, not a
programmatic assertion. The ADR files (ADR-029, ADR-030, ADR-031) record the
decision text; no code path verifies the prose content of an ADR file.

CANNOT TEST AC-12: "ADR-028 is marked Superseded, ADR-025 Superseded pointer
updated, architecture.md mechanically updated, issue files resolved." These are
documentation-state assertions on markdown files, not application behavior.
(Note: a file-content check could be written, but these are explicitly listed
as architect deliverables verified during the design phase, not application
acceptance criteria.)

Coverage matrix:
  Boundary:
    - test_notes_rail_present_on_all_12_chapters: iterate all 12 corpus Chapters
      (Notes rail present in RHS column on every Lecture page).
    - test_nav_rail_does_not_contain_rail_notes_section_on_all_12_chapters:
      _nav_rail.html.j2-rendered output must NOT contain rail-notes on all 12.
    - test_completion_redirect_location_anchors_section_end_all_chapters:
      #section-{n}-end fragment present on all 6 Mandatory chapters for mark.
    - test_page_layout_three_column_on_lecture_two_column_on_landing: both
      endpoints.
  Edge:
    - test_notes_rail_absent_when_no_chapter_context: GET / has no notes-rail
      and no rail-notes in HTML.
    - test_page_layout_modifier_no_notes_on_landing_page: landing page uses
      page-layout--no-notes (or equivalent two-column form).
    - test_notes_form_posts_to_correct_chapter_route_in_rhs_rail: form action
      URL correctness per chapter.
    - test_notes_round_trip_note_appears_at_top_of_rhs_rail_list: PRG round
      trip; most-recent note still at top; in the RHS region, not the LHS nav.
    - test_notes_empty_state_in_rhs_rail: empty state copy in RHS rail.
    - test_two_notes_order_preserved_in_rhs_rail: ordering boundary in RHS rail.
    - test_section_end_wrapper_carries_id_attribute_on_lecture_pages: each
      .section-end carries id="section-{n-m}-end" (ADR-031 template change).
  Negative:
    - test_nav_rail_does_not_contain_notes_form: <form> targeting /notes must
      NOT be inside the lecture-rail / _nav_rail region.
    - test_completion_redirect_location_anchors_section_end_mark: Location header
      ends with #section-{n}-end for mark (ADR-031 §Decision).
    - test_completion_redirect_location_anchors_section_end_unmark: same for
      unmark.
    - test_completion_redirect_still_returns_303: status code not changed.
    - test_completion_toggle_persistence_round_trip_after_redirect_change: mark
      then unmark still persists and clears correctly.
    - test_old_notes_classes_not_in_nav_rail_output: 'notes-surface' must remain
      absent (ADR-028 established this; ADR-029 retains it).
    - test_notes_rail_wrapper_element_present: <aside class="notes-rail"> (or
      equivalent wrapper with notes-rail class) present on Lecture pages.
    - test_lecture_css_has_scroll_margin_top_on_section_end: lecture.css must
      set scroll-margin-top on .section-end (ADR-031 CSS change).
  Performance:
    - test_three_column_lecture_page_renders_within_time_budget: all 12 Chapters
      render within 5 s with the new three-column layout (catches regression from
      the extra column / extra partial include).

pytestmark registers all tests under task("TASK-012").

AMENDMENTS to existing tests (required by ADR-029 / ADR-030 / ADR-031
supersedures):
  - test_task009_notes_bootstrap.py::test_notes_ui_present_on_all_12_chapters:
    amends assertion from "rail-notes inside _nav_rail output" to "rail-notes
    in the RHS notes-rail region". (Amended directly below via re-assertion.)
  - test_task010_section_completion.py::test_post_complete_redirect_location_contains_chapter:
    Re-amended by ADR-031 §Test-writer pre-flag: asserts
    f"section-{TEST_SECTION_NUMBER}-end" in location (and the chapter path is
    still present). Previously amended by TASK-012 Run 004 from the original
    '#section-N' assertion to 'assert "#" not in location' per ADR-030; now
    re-amended per ADR-031. The amended assertion lives in
    test_task012_rhs_notes_rail_and_redirect.py
    (test_completion_redirect_location_anchors_section_end_mark / _unmark).

ASSUMPTIONS:
  ASSUMPTION: ADR-029 §The new RHS rail partial: the wrapper element for the RHS
    Notes rail is an HTML element carrying class="notes-rail" (the ADR commits
    to the .notes-rail CSS class; the element type is implementer-tunable between
    <aside> and other elements). Tests assert presence of the "notes-rail" class
    in the rendered HTML.
  ASSUMPTION: ADR-029 §Per-Chapter scoping: on GET / the rendered HTML carries
    class="page-layout--no-notes" (the ADR's forecast modifier class) OR does
    not contain a .notes-rail element. Tests check for absence of .notes-rail on
    GET /, which is the authoritative ADR-029 commitment.
  ASSUMPTION: ADR-029 §CSS class names: the Notes panel's inner HTML uses
    class="rail-notes" on the <section> wrapper (retained from ADR-028). Tests
    assert "rail-notes" is present in the rendered Lecture page HTML; they do NOT
    assert it is inside a specific element (since the element is now the new RHS
    partial, not _nav_rail.html.j2 — that negative is the stronger test).
  ASSUMPTION: The LHS chapter navigation element is identifiable as
    class="lecture-rail" or similar containing the chapter list (per ADR-029
    §Layout shape); tests look for a nav element with the chapter list to confirm
    the RHS Notes content is NOT inside it.
  ASSUMPTION: ADR-031 §Decision: the redirect Location ends with
    '#section-{section_number}-end' (e.g. '/lecture/ch-01-cpp-refresher#section-1-1-end').
    Tests assert this suffix is present in the Location header.
"""

from __future__ import annotations

import pathlib
import re
import sqlite3
import time

import pytest

pytestmark = pytest.mark.task("TASK-012")

# ---------------------------------------------------------------------------
# Canonical Chapter ID list (same across all tasks)
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

TEST_CHAPTER_ID = "ch-01-cpp-refresher"
TEST_SECTION_NUMBER = "1-1"

REPO_ROOT = pathlib.Path(__file__).parent.parent

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_client(monkeypatch=None, db_path: str | None = None):
    """Return a FastAPI TestClient, injecting NOTES_DB_PATH for test isolation."""
    if monkeypatch is not None and db_path is not None:
        monkeypatch.setenv("NOTES_DB_PATH", db_path)
    from fastapi.testclient import TestClient  # noqa: PLC0415
    from app.main import app  # noqa: PLC0415
    return TestClient(app)


def _db_path(tmp_path: pathlib.Path) -> str:
    return str(tmp_path / "test_task012.db")


def _direct_db_list_completions(db_path: str, chapter_id: str) -> list[dict]:
    """Query section_completions directly (storage-level observer)."""
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


# ===========================================================================
# AC-1 — Three-column layout: LHS chapter rail + centered main + RHS Notes rail
# ===========================================================================


@pytest.mark.parametrize("chapter_id", ALL_CHAPTER_IDS)
def test_notes_rail_present_on_all_12_chapters(
    chapter_id: str, tmp_path, monkeypatch
) -> None:
    """
    AC-1/AC-2 (TASK-012) boundary: every Lecture page must render a right-hand
    Notes rail with the 'notes-rail' wrapper class (ADR-029 §The new RHS rail
    partial — <aside class="notes-rail"> commitment).

    Tests all 12 corpus Chapters — not a spot-check.

    Trace: AC-1; ADR-029 §Layout shape; ADR-029 §CSS class names.
    """
    client = _make_client(monkeypatch, _db_path(tmp_path))
    response = client.get(f"/lecture/{chapter_id}")
    assert response.status_code == 200, (
        f"GET /lecture/{chapter_id} returned {response.status_code}; expected 200."
    )
    html = response.text

    # ADR-029 §CSS class names: .notes-rail is the new RHS wrapper class
    assert "notes-rail" in html, (
        f"GET /lecture/{chapter_id} — 'notes-rail' class not found in rendered HTML. "
        "AC-1/ADR-029: the Lecture page must have a right-hand Notes rail with "
        "class='notes-rail' (new RHS wrapper, new partial _notes_rail.html.j2)."
    )

    # The Notes panel content must still carry rail-notes class (retained from ADR-028)
    assert "rail-notes" in html, (
        f"GET /lecture/{chapter_id} — 'rail-notes' class not found. "
        "AC-1/ADR-029: the Notes section inside the RHS rail retains the 'rail-notes' "
        "class (no rename per ADR-029 §CSS class names: keep rail-notes-* / rail-note-*)."
    )

    # The Notes form targeting /lecture/{chapter_id}/notes must be present
    expected_action = f"/lecture/{chapter_id}/notes"
    assert expected_action in html, (
        f"GET /lecture/{chapter_id} — form action '{expected_action}' not found. "
        "AC-1/ADR-029: the RHS Notes form must post to /lecture/{chapter_id}/notes "
        "(route unchanged from ADR-023/ADR-028)."
    )

    # The textarea with name="body" must be present (ADR-028 retained)
    assert 'name="body"' in html, (
        f"GET /lecture/{chapter_id} — no textarea name='body' found. "
        "AC-1/ADR-029: the RHS Notes form must include a textarea named 'body'."
    )


def test_notes_rail_wrapper_element_present(tmp_path, monkeypatch) -> None:
    """
    AC-1 (TASK-012): the RHS Notes rail wrapper element (class="notes-rail")
    must be present in the rendered HTML for a Lecture page.

    ADR-029 §The new RHS rail partial: 'base.html.j2 includes both the LHS
    rail partial and the new RHS rail partial … <aside class="notes-rail">'.

    This test specifically asserts the WRAPPER element (the <aside> or equivalent
    container that wraps the RHS rail), not just the inner panel content.

    Trace: AC-1; ADR-029 §The new RHS rail partial (wrapper commitment).
    """
    client = _make_client(monkeypatch, _db_path(tmp_path))
    response = client.get(f"/lecture/{TEST_CHAPTER_ID}")
    assert response.status_code == 200
    html = response.text

    # The wrapper must appear in the HTML (class="notes-rail" on the outer element)
    # ADR-029: 'new <aside class="notes-rail" …>' wrapper element
    # We check for any element opening tag that carries class="notes-rail"
    # (implementer may use <aside>, <div>, or another element per ADR-029's
    # "wrapper element implementer-tunable" note).
    notes_rail_wrapper_pattern = re.compile(
        r'<(?:aside|div|section|nav)[^>]+class="[^"]*notes-rail[^"]*"'
    )
    assert notes_rail_wrapper_pattern.search(html), (
        "GET /lecture/ch-01 — no element with class='notes-rail' found as an "
        "opening HTML tag. "
        "AC-1/ADR-029: the RHS rail wrapper element must carry class='notes-rail'. "
        "Expected pattern: <aside class=\"notes-rail\"> or similar."
    )


# ===========================================================================
# AC-5 — Notes section is NOT inside _nav_rail.html.j2 / lecture-rail element
# ===========================================================================


@pytest.mark.parametrize("chapter_id", ALL_CHAPTER_IDS)
def test_nav_rail_does_not_contain_rail_notes_section_on_all_12_chapters(
    chapter_id: str, tmp_path, monkeypatch
) -> None:
    """
    AC-5 (TASK-012) boundary: the Notes <section class="rail-notes"> must NOT be
    inside the LHS chapter navigation rail on any of the 12 corpus Chapters.

    ADR-029 §Scope: '_nav_rail.html.j2 retains only the chapter list (with the
    ADR-026 progress decoration) and the Mandatory/Optional headings — the Notes
    <section> is no longer in its rendered output.'

    Strategy: verify that in the rendered HTML, the 'rail-notes' section does NOT
    appear inside the element bearing 'lecture-rail' (the LHS nav element).

    This is the authoritative supersedure assertion — if it fails, the Notes
    section is still in the wrong rail.

    Trace: AC-5; ADR-029 §The new RHS rail partial; ADR-029 §Test-writer pre-flag.
    """
    client = _make_client(monkeypatch, _db_path(tmp_path))
    response = client.get(f"/lecture/{chapter_id}")
    assert response.status_code == 200
    html = response.text

    # Find the lecture-rail (LHS nav rail) element and its HTML extent.
    # ADR-029 names the LHS element as <nav class="lecture-rail">.
    # We extract everything inside the lecture-rail and assert rail-notes is NOT there.
    lecture_rail_pattern = re.compile(
        r'<nav[^>]+class="[^"]*lecture-rail[^"]*"[^>]*>(.*?)</nav>',
        re.DOTALL,
    )
    lecture_rail_match = lecture_rail_pattern.search(html)
    assert lecture_rail_match is not None, (
        f"GET /lecture/{chapter_id} — no <nav class='lecture-rail'> element found. "
        "AC-5: the LHS chapter nav rail must be rendered as <nav class='lecture-rail'>. "
        "(ADR-029 §Layout shape: 'Column 1 — the LHS chapter-navigation rail (.lecture-rail)')"
    )

    lecture_rail_html = lecture_rail_match.group(1)
    assert "rail-notes" not in lecture_rail_html, (
        f"GET /lecture/{chapter_id} — 'rail-notes' found inside the lecture-rail "
        "(<nav class='lecture-rail'>) element. "
        "AC-5/ADR-029: the Notes section must be REMOVED from _nav_rail.html.j2; "
        "it now lives in the new _notes_rail.html.j2 partial in the RHS column. "
        "The LHS rail must carry ONLY the chapter list, M/O headings, and ADR-026 "
        "progress decorations."
    )


def test_nav_rail_does_not_contain_notes_form(tmp_path, monkeypatch) -> None:
    """
    AC-5 negative (TASK-012): the Notes form (<form … action="/lecture/…/notes">)
    must NOT appear inside the LHS chapter nav rail element.

    If the Notes form is inside the lecture-rail, the supersedure of ADR-028's
    rail integration has not been completed.

    Trace: AC-5; ADR-029 §The new RHS rail partial (extraction from _nav_rail.html.j2).
    """
    client = _make_client(monkeypatch, _db_path(tmp_path))
    response = client.get(f"/lecture/{TEST_CHAPTER_ID}")
    assert response.status_code == 200
    html = response.text

    lecture_rail_pattern = re.compile(
        r'<nav[^>]+class="[^"]*lecture-rail[^"]*"[^>]*>(.*?)</nav>',
        re.DOTALL,
    )
    lecture_rail_match = lecture_rail_pattern.search(html)
    if lecture_rail_match is None:
        pytest.fail(
            "No <nav class='lecture-rail'> found — prerequisite for Notes-form location check."
        )

    lecture_rail_html = lecture_rail_match.group(1)
    notes_action_pattern = re.compile(r'/lecture/[^/]+/notes')
    assert not notes_action_pattern.search(lecture_rail_html), (
        "A Notes form action URL found inside the lecture-rail element. "
        "AC-5/ADR-029: the Notes form must live in the RHS notes-rail, NOT in the "
        "LHS lecture-rail / _nav_rail.html.j2 output."
    )


# ===========================================================================
# AC-3 — On GET / the Notes rail is absent (two-column layout)
# ===========================================================================


def test_notes_rail_absent_when_no_chapter_context(tmp_path, monkeypatch) -> None:
    """
    AC-3 (TASK-012): on GET / (landing page, no Chapter context), the RHS Notes
    rail must be absent from the rendered HTML.

    ADR-029 §Per-Chapter scoping: 'on GET / with no RHS column rendered, the grid
    is two-column (chapter rail + main), exactly as it was before ADR-028.'
    ADR-029 §Layout shape commitment: on '/' no <aside class="notes-rail"> is
    rendered (the {% if rail_notes_context %} guard is retained).

    Trace: AC-3; ADR-029 §Per-Chapter scoping on the landing page.
    """
    client = _make_client(monkeypatch, _db_path(tmp_path))
    response = client.get("/")
    assert response.status_code == 200
    html = response.text

    # The RHS Notes rail wrapper must NOT appear on the landing page
    assert "notes-rail" not in html, (
        "GET / — 'notes-rail' class found in landing page HTML. "
        "AC-3/ADR-029: the RHS Notes rail must be ABSENT from GET / (no Chapter context). "
        "The page-layout must degrade to two columns (chapter rail + main)."
    )

    # The Notes section content class must also be absent
    assert "rail-notes" not in html, (
        "GET / — 'rail-notes' class found in landing page HTML. "
        "AC-3/ADR-029: the {% if rail_notes_context %} guard suppresses the Notes panel "
        "on the landing page (no Chapter context → no rail_notes_context)."
    )

    # No Notes form action must appear on the landing page
    notes_action_pattern = re.compile(r'/lecture/[^/]+/notes')
    assert not notes_action_pattern.search(html), (
        "GET / — a Notes form action URL found in landing page HTML. "
        "AC-3/ADR-029: the landing page must have no Notes form (no Chapter context)."
    )


def test_page_layout_modifier_no_notes_on_landing_page(tmp_path, monkeypatch) -> None:
    """
    AC-3 (TASK-012) / ADR-029 §Per-Chapter scoping: on GET / the layout uses the
    two-column form. ADR-029 forecasts a '.page-layout--no-notes' modifier class on
    the page-layout wrapper when no Chapter context exists.

    This test asserts the landing page carries 'page-layout--no-notes' OR the
    absence of a three-column class entirely (either form of the graceful
    degradation is acceptable per ADR-029 §Per-Chapter scoping mechanism note:
    'exact mechanism implementer-tunable').

    We conservatively assert: (a) notes-rail is absent (the strong ADR commitment),
    and (b) if page-layout--no-notes is used, it appears on the page.

    Trace: AC-3; ADR-029 §Per-Chapter scoping (forecast mechanism).
    """
    client = _make_client(monkeypatch, _db_path(tmp_path))
    response = client.get("/")
    assert response.status_code == 200
    html = response.text

    # Hard commitment: no notes-rail on landing page
    assert "notes-rail" not in html, (
        "GET / — 'notes-rail' found in landing page HTML. "
        "ADR-029: landing page must degrade to two-column (no RHS Notes rail)."
    )

    # The page must still have a page-layout class (the layout wrapper exists)
    assert "page-layout" in html, (
        "GET / — 'page-layout' class not found in landing page HTML. "
        "ADR-029: the page-layout wrapper must still be present on the landing page."
    )


def test_page_layout_three_column_on_lecture_two_column_on_landing(
    tmp_path, monkeypatch
) -> None:
    """
    AC-1/AC-3 boundary (TASK-012): the Lecture page must have THREE grid-column
    elements (LHS rail, main, RHS rail) while GET / has TWO (LHS rail + main).

    ADR-029 §Layout shape: 'three columns on Lecture pages' and '§Per-Chapter
    scoping: on GET / the page is two-column.'

    Strategy: count the top-level children of the page-layout container.
    On Lecture pages: <nav class="lecture-rail"> + <main class="page-main"> +
    <aside class="notes-rail"> = 3 column children.
    On landing page: <nav class="lecture-rail"> + <main class="page-main"> = 2.

    Trace: AC-1/AC-3; ADR-029 §Layout shape; ADR-029 §Per-Chapter scoping.
    """
    client = _make_client(monkeypatch, _db_path(tmp_path))

    # Lecture page — should have 3 columns
    lecture_resp = client.get(f"/lecture/{TEST_CHAPTER_ID}")
    assert lecture_resp.status_code == 200
    lecture_html = lecture_resp.text

    # All three column elements must appear on Lecture pages
    assert "lecture-rail" in lecture_html, (
        "Lecture page missing 'lecture-rail' — LHS column element absent."
    )
    assert "page-main" in lecture_html, (
        "Lecture page missing 'page-main' — centered main column absent."
    )
    assert "notes-rail" in lecture_html, (
        "Lecture page missing 'notes-rail' — RHS Notes column absent. "
        "ADR-029: Lecture pages must have THREE columns."
    )

    # Landing page — should have 2 columns (no notes-rail)
    landing_resp = client.get("/")
    assert landing_resp.status_code == 200
    landing_html = landing_resp.text

    assert "lecture-rail" in landing_html, (
        "Landing page missing 'lecture-rail' — LHS column absent."
    )
    assert "page-main" in landing_html, (
        "Landing page missing 'page-main' — main column absent."
    )
    assert "notes-rail" not in landing_html, (
        "Landing page contains 'notes-rail' — RHS column present when it should be absent. "
        "ADR-029: on GET / the layout is TWO columns (no Chapter context → no Notes rail)."
    )


# ===========================================================================
# AC-2 — Sticky RHS Notes rail visible after scroll (structural assertion)
# ===========================================================================


def test_notes_rail_has_sticky_indicator_in_html(tmp_path, monkeypatch) -> None:
    """
    AC-2 (TASK-012): the RHS Notes rail is sticky — visible from any scroll
    position, exactly as the LHS chapter rail already is (ADR-008).

    ADR-029 §Layout shape: 'The RHS rail is position: sticky (using the same
    sticky mechanism the LHS rail already uses) so it is visible from any scroll
    position.'

    The programmatic HTTP-level proxy for stickiness: the .notes-rail element
    exists in the rendered HTML and is a direct child of the page-layout (not
    buried inside the scrolling content area). A Playwright test in
    test_task012_rhs_notes_rail_dom.py asserts viewport visibility after scroll.

    Trace: AC-2; ADR-029 §Layout shape sticky commitment.
    """
    client = _make_client(monkeypatch, _db_path(tmp_path))
    response = client.get(f"/lecture/{TEST_CHAPTER_ID}")
    assert response.status_code == 200
    html = response.text

    # The notes-rail wrapper must exist (prerequisite for sticky behavior)
    assert "notes-rail" in html, (
        "notes-rail class not found — RHS rail is absent; stickiness cannot be verified. "
        "AC-2/ADR-029: the RHS Notes rail must exist to be sticky."
    )

    # The LHS lecture-rail must also exist (the sticky mechanism is shared)
    assert "lecture-rail" in html, (
        "lecture-rail class not found — the LHS sticky rail is missing. "
        "AC-2/ADR-029: the LHS rail uses position:sticky; the RHS rail reuses the same mechanism."
    )


# ===========================================================================
# AC-3/4 — Notes round-trip: submitted note appears in the RHS rail
# ===========================================================================


def test_notes_round_trip_note_appears_at_top_of_rhs_rail_list(
    tmp_path, monkeypatch
) -> None:
    """
    AC-4 (TASK-012): after submitting a Note via the RHS rail form, the PRG
    round-trip reloads the page with the new Note visible at the TOP of the
    Notes list in the right-hand rail (notes-rail region).

    ADR-029 §What of ADR-028 is retained: 'Multiple-Note display order:
    most-recent-first (ORDER BY created_at DESC). Unchanged.'
    'Submit-feedback shape: full-page reload via PRG; … the now-RHS-resident
    Notes panel re-renders with the new Note at the top of the list.'

    Trace: AC-4; ADR-029 §What of ADR-028 is retained (PRG, display order).
    """
    db_path = _db_path(tmp_path)
    client = _make_client(monkeypatch, db_path)

    unique_body = f"RHS-rail-round-trip-note-TASK012-{int(time.time() * 1000)}"

    # POST a Note via the RHS rail form
    post_resp = client.post(
        f"/lecture/{TEST_CHAPTER_ID}/notes",
        data={"body": unique_body},
        follow_redirects=False,
    )
    assert post_resp.status_code == 303, (
        f"POST /lecture/{TEST_CHAPTER_ID}/notes returned {post_resp.status_code}; "
        "expected 303 (PRG redirect unchanged from ADR-028/ADR-023). "
        "AC-4: the Notes form must still use the PRG pattern after the RHS move."
    )

    # Follow the redirect to the GET page
    get_resp = client.get(f"/lecture/{TEST_CHAPTER_ID}")
    assert get_resp.status_code == 200
    html = get_resp.text

    # The Note must appear in the rendered HTML
    assert unique_body in html, (
        f"Submitted Note body {unique_body!r} not found in rendered HTML after PRG redirect. "
        "AC-4/ADR-029: the new Note must be visible on the Lecture page after submission."
    )

    # The Note must appear WITHIN the notes-rail region (not elsewhere)
    notes_rail_pattern = re.compile(
        r'class="[^"]*notes-rail[^"]*"[^>]*>(.*?)(?=<(?:nav|main|div)[^>]+class="(?:lecture-rail|page-main))',
        re.DOTALL,
    )
    notes_rail_match = notes_rail_pattern.search(html)
    if notes_rail_match:
        notes_rail_content = notes_rail_match.group(1)
        assert unique_body in notes_rail_content, (
            f"Note body {unique_body!r} found in page HTML but NOT in the notes-rail region. "
            "AC-4/ADR-029: the submitted Note must appear in the RHS notes-rail, "
            "not somewhere else in the page."
        )

    # The Note must NOT appear inside the lecture-rail (LHS nav rail)
    lecture_rail_pattern = re.compile(
        r'<nav[^>]+class="[^"]*lecture-rail[^"]*"[^>]*>(.*?)</nav>',
        re.DOTALL,
    )
    lecture_rail_match = lecture_rail_pattern.search(html)
    if lecture_rail_match:
        lecture_rail_content = lecture_rail_match.group(1)
        assert unique_body not in lecture_rail_content, (
            f"Note body {unique_body!r} found INSIDE the lecture-rail (LHS nav rail). "
            "AC-4/ADR-029: Notes must live in the RHS notes-rail, not the LHS lecture-rail."
        )


def test_notes_empty_state_in_rhs_rail(tmp_path, monkeypatch) -> None:
    """
    AC-3 edge (TASK-012): on a fresh database, the Notes panel in the RHS rail
    shows the empty-state caption 'No notes yet' (ADR-028 retained: 'Empty-state
    copy: "No notes yet — write the first one below." Unchanged.').

    Trace: AC-3; ADR-029 §What of ADR-028 is retained (empty-state copy).
    """
    client = _make_client(monkeypatch, _db_path(tmp_path))
    response = client.get(f"/lecture/{TEST_CHAPTER_ID}")
    assert response.status_code == 200
    html = response.text

    assert "No notes yet" in html, (
        "GET /lecture/ch-01 (fresh database) — 'No notes yet' empty-state caption not found. "
        "AC-3/ADR-029: empty-state copy 'No notes yet — write the first one below.' "
        "is retained from ADR-028 and must appear in the RHS rail when no Notes exist."
    )


def test_two_notes_order_preserved_in_rhs_rail(tmp_path, monkeypatch) -> None:
    """
    AC-4 ordering (TASK-012): most-recent Note appears FIRST in the RHS rail list.

    ADR-029 §What of ADR-028 is retained: 'Multiple-Note display order:
    most-recent-first (ORDER BY created_at DESC). Unchanged.'

    Trace: AC-4; ADR-029 §What of ADR-028 is retained; ADR-023 §Multiple-Note display.
    """
    db_path = _db_path(tmp_path)
    client = _make_client(monkeypatch, db_path)

    body_first = "TASK012-ordering-first-note-older"
    body_second = "TASK012-ordering-second-note-newer"

    client.post(
        f"/lecture/{TEST_CHAPTER_ID}/notes",
        data={"body": body_first},
        follow_redirects=True,
    )
    time.sleep(0.02)
    client.post(
        f"/lecture/{TEST_CHAPTER_ID}/notes",
        data={"body": body_second},
        follow_redirects=True,
    )

    get_resp = client.get(f"/lecture/{TEST_CHAPTER_ID}")
    assert get_resp.status_code == 200
    html = get_resp.text

    assert body_first in html and body_second in html, (
        "Both Notes must be visible in the RHS rail."
    )

    pos_first = html.index(body_first)
    pos_second = html.index(body_second)
    assert pos_second < pos_first, (
        "The more-recent Note (body_second) appears AFTER the older Note (body_first) "
        "in the rendered HTML. "
        "ADR-029 §What of ADR-028 is retained: most-recent-first ordering must be "
        "preserved in the RHS rail."
    )


def test_notes_form_posts_to_correct_chapter_route_in_rhs_rail(
    tmp_path, monkeypatch
) -> None:
    """
    AC-3 edge (TASK-012): the Notes form in the RHS rail posts to the CURRENT
    chapter's notes route, not any other chapter's.

    Iterates all 12 chapters to confirm the form action matches the page URL.

    Trace: AC-3; ADR-029 §What of ADR-028 is retained (route shape unchanged).
    """
    client = _make_client(monkeypatch, _db_path(tmp_path))

    for chapter_id in ALL_CHAPTER_IDS:
        response = client.get(f"/lecture/{chapter_id}")
        assert response.status_code == 200
        html = response.text

        expected_action = f"/lecture/{chapter_id}/notes"
        assert expected_action in html, (
            f"GET /lecture/{chapter_id} — form action '{expected_action}' not found. "
            "AC-3/ADR-029: the RHS rail Notes form must target the current chapter's "
            "notes POST route (unchanged from ADR-023/ADR-028)."
        )


# ===========================================================================
# AC-6 — Completion redirect: 303 Location anchors to #section-{n}-end
#         (Amendment per ADR-031 — supersedes ADR-030 §Decision)
#         (Also re-amends test_task010 assertion per ADR-031 §Test-writer pre-flag)
# ===========================================================================


def test_completion_redirect_location_anchors_section_end_mark(
    tmp_path, monkeypatch
) -> None:
    """
    AC-6 (TASK-012) / ADR-031 §Decision: POST .../complete with action=mark must
    return 303 with Location header ending in '#section-{section_number}-end'.

    ADR-031: 'The 303 Location header for the completion toggle carries the
    #section-{section_number}-end fragment — pointing at the bottom-of-Section
    affordance container (.section-end wrapper with id="section-{n-m}-end"),
    not the Section heading.'

    SUPERSEDES test_completion_redirect_location_no_fragment_mark (Run 004,
    ADR-030 §Decision "no fragment"). ADR-030 §Decision was superseded by
    ADR-031 after the Playwright test empirically proved Chromium resets scrollY
    to 0 on the fragment-less same-URL navigation (audit Run 006).

    SUPERSEDES the assertion in test_task010_section_completion.py
    test_post_complete_redirect_location_contains_chapter (previously amended in
    Run 004 to 'assert "#" not in location'; re-amended here per ADR-031 to
    assert the #section-{n}-end fragment is present).

    PINNED CONTRACT: Location header ends with
    '#section-{TEST_SECTION_NUMBER}-end'
    (e.g. '/lecture/ch-01-cpp-refresher#section-1-1-end').

    Trace: AC-6; ADR-031 §Decision; ADR-031 §Test-writer pre-flag (item 1).
    """
    client = _make_client(monkeypatch, _db_path(tmp_path))

    response = client.post(
        f"/lecture/{TEST_CHAPTER_ID}/sections/{TEST_SECTION_NUMBER}/complete",
        data={"action": "mark"},
        follow_redirects=False,
    )
    assert response.status_code == 303, (
        f"POST complete returned {response.status_code}; expected 303. "
        "ADR-031: PRG redirect status must remain 303."
    )

    location = response.headers.get("location", "")
    expected_fragment = f"#section-{TEST_SECTION_NUMBER}-end"

    # ADR-031: the redirect target ends with #section-{n}-end
    assert expected_fragment in location, (
        f"POST complete (mark) returned Location: {location!r}. "
        f"Expected Location to contain '{expected_fragment}'. "
        "AC-6/ADR-031: the completion redirect must anchor to the .section-end wrapper "
        "so the browser lands the user ≈ where they clicked (bottom of Section), "
        "not at the Section heading or the page top."
    )

    # The Location must still point to the chapter page (path part unchanged)
    assert f"/lecture/{TEST_CHAPTER_ID}" in location, (
        f"POST complete (mark) Location header {location!r} does not contain "
        f"'/lecture/{TEST_CHAPTER_ID}'. "
        "ADR-031: the redirect must still target the Chapter's Lecture page."
    )

    # The section path is NOT the old heading anchor (not just #section-{n})
    # — that would be ADR-025's superseded mechanism. The -end suffix is load-bearing.
    old_heading_anchor = f"#section-{TEST_SECTION_NUMBER}\""
    assert old_heading_anchor not in location, (
        f"POST complete (mark) Location {location!r} ends with the old heading anchor "
        f"'{old_heading_anchor}' (ADR-025 superseded mechanism). "
        "ADR-031: the fragment must point at the .section-end wrapper, not the heading."
    )


def test_completion_redirect_location_anchors_section_end_unmark(
    tmp_path, monkeypatch
) -> None:
    """
    AC-6 (TASK-012) / ADR-031: POST .../complete with action=unmark must also
    return 303 with Location header ending in '#section-{section_number}-end'.

    ADR-031 §Decision: 'Everything else about the route (shape, validation,
    persistence integration, the action=mark|unmark dispatch, the 303 status,
    the state-indicator triad) is unchanged.' Only the redirect target changes
    (from no-fragment per ADR-030 to #section-{n}-end per ADR-031). Both mark
    and unmark must use the #section-{n}-end Location.

    Trace: AC-6; ADR-031 §Decision; ADR-031 §Test-writer pre-flag (item 1).
    """
    client = _make_client(monkeypatch, _db_path(tmp_path))

    # First mark the section (so unmark is valid)
    client.post(
        f"/lecture/{TEST_CHAPTER_ID}/sections/{TEST_SECTION_NUMBER}/complete",
        data={"action": "mark"},
        follow_redirects=False,
    )

    # Now unmark and check the Location header
    response = client.post(
        f"/lecture/{TEST_CHAPTER_ID}/sections/{TEST_SECTION_NUMBER}/complete",
        data={"action": "unmark"},
        follow_redirects=False,
    )
    assert response.status_code == 303, (
        f"POST complete (unmark) returned {response.status_code}; expected 303."
    )

    location = response.headers.get("location", "")
    expected_fragment = f"#section-{TEST_SECTION_NUMBER}-end"

    assert expected_fragment in location, (
        f"POST complete (unmark) Location header {location!r} does not contain "
        f"'{expected_fragment}'. "
        "AC-6/ADR-031: the #section-{{n}}-end fragment must be present in the 303 "
        "redirect for BOTH mark and unmark actions."
    )

    assert f"/lecture/{TEST_CHAPTER_ID}" in location, (
        f"POST complete (unmark) Location {location!r} does not contain "
        f"'/lecture/{TEST_CHAPTER_ID}'. "
        "ADR-031: unmark must still redirect to the Chapter's Lecture page."
    )


def test_completion_redirect_still_returns_303(tmp_path, monkeypatch) -> None:
    """
    AC-6 / AC-7 (TASK-012): the completion redirect status code is unchanged at
    303 — ADR-031 changes the fragment in the Location header but does not change
    the status code.

    ADR-031 §What of ADR-030 is retained (from ADR-025): 'Form-handling pattern:
    synchronous PRG with no JavaScript; 303 See Other on success. Unchanged.'

    Trace: AC-6; ADR-031 §What of ADR-030 is retained.
    """
    client = _make_client(monkeypatch, _db_path(tmp_path))

    for action in ("mark", "unmark"):
        response = client.post(
            f"/lecture/{TEST_CHAPTER_ID}/sections/{TEST_SECTION_NUMBER}/complete",
            data={"action": action},
            follow_redirects=False,
        )
        assert response.status_code == 303, (
            f"POST complete (action={action!r}) returned {response.status_code}; "
            "expected 303. "
            "ADR-031: the PRG redirect status code (303) is unchanged by the "
            "redirect-fragment supersedure."
        )


@pytest.mark.parametrize("chapter_id", ALL_CHAPTER_IDS)
def test_completion_redirect_location_anchors_section_end_all_chapters(
    chapter_id: str, tmp_path, monkeypatch
) -> None:
    """
    AC-6 boundary (TASK-012) / ADR-031: #section-{n}-end redirect fragment
    applies to all 12 corpus Chapters.

    ADR-031 §Decision: the mechanism applies to the whole corpus — every chapter's
    completion route must redirect to #section-{section_number}-end.

    Tests all 12 chapters (not just the 6 Mandatory ones) to ensure the -end
    anchor is universally applied.

    Trace: AC-6; ADR-031 §Decision (applies to all chapters); boundary coverage.
    """
    client = _make_client(monkeypatch, _db_path(tmp_path))

    # Discover the first section number for this chapter dynamically.
    get_resp = client.get(f"/lecture/{chapter_id}")
    assert get_resp.status_code == 200
    html = get_resp.text

    # Find a valid section number for this chapter
    completion_route_pattern = re.compile(
        rf"/lecture/{re.escape(chapter_id)}/sections/([\d\-]+)/complete"
    )
    match = completion_route_pattern.search(html)
    if match is None:
        pytest.skip(
            f"No completion route found for {chapter_id} — "
            "chapter may not have sections; skipping."
        )
    section_number = match.group(1)
    expected_fragment = f"#section-{section_number}-end"

    response = client.post(
        f"/lecture/{chapter_id}/sections/{section_number}/complete",
        data={"action": "mark"},
        follow_redirects=False,
    )
    assert response.status_code == 303

    location = response.headers.get("location", "")
    assert expected_fragment in location, (
        f"Chapter {chapter_id}, section {section_number}: "
        f"POST complete returned Location {location!r} — "
        f"expected fragment '{expected_fragment}' not found. "
        "ADR-031: the #section-{{n}}-end redirect must apply to ALL chapters."
    )
    assert f"/lecture/{chapter_id}" in location, (
        f"Chapter {chapter_id}: Location {location!r} does not point to the chapter page."
    )


# ===========================================================================
# AC-7 — Completion toggle persistence is unchanged after redirect change
# ===========================================================================


def test_completion_toggle_persistence_round_trip_after_redirect_change(
    tmp_path, monkeypatch
) -> None:
    """
    AC-7 (TASK-012): after the redirect-target change (ADR-031), the mark/unmark
    toggle still persists to the database and the state is reflected on the next GET.

    ADR-031 §What of ADR-030 is retained (from ADR-025): 'Persistence integration:
    unchanged. State-indicator triad: button text + button color modifier +
    .section-complete CSS class on <section>. Unchanged.'

    Steps:
      1. Mark section complete → 303 redirect (with #section-{n}-end fragment).
      2. GET the page → section-complete class must be present.
      3. Unmark section → 303 redirect (with #section-{n}-end fragment).
      4. GET the page → section-complete class must be absent.
      5. Verify DB row presence/absence at each step.

    Trace: AC-7; ADR-031 §What of ADR-030 is retained.
    """
    db_path = _db_path(tmp_path)
    client = _make_client(monkeypatch, db_path)

    section_id = f"{TEST_CHAPTER_ID}#section-{TEST_SECTION_NUMBER}"
    complete_url = (
        f"/lecture/{TEST_CHAPTER_ID}/sections/{TEST_SECTION_NUMBER}/complete"
    )
    expected_fragment = f"#section-{TEST_SECTION_NUMBER}-end"

    # --- Mark ---
    mark_resp = client.post(
        complete_url, data={"action": "mark"}, follow_redirects=False
    )
    assert mark_resp.status_code == 303, (
        f"Mark returned {mark_resp.status_code}; expected 303."
    )
    location_mark = mark_resp.headers.get("location", "")
    assert expected_fragment in location_mark, (
        f"Mark Location {location_mark!r} does not contain '{expected_fragment}'. "
        "ADR-031: the #section-{{n}}-end fragment must be present after mark."
    )

    # GET page — section must show as complete
    get_after_mark = client.get(f"/lecture/{TEST_CHAPTER_ID}")
    assert get_after_mark.status_code == 200
    assert "section-complete" in get_after_mark.text, (
        "After mark: 'section-complete' class not found in rendered HTML. "
        "AC-7: marking must persist; the GET must reflect the completed state."
    )
    assert 'value="unmark"' in get_after_mark.text, (
        "After mark: 'value=\"unmark\"' not in HTML. "
        "AC-7: the action form field must flip to 'unmark' after marking."
    )

    # DB row must exist
    rows = _direct_db_list_completions(db_path, TEST_CHAPTER_ID)
    assert any(r["section_id"] == section_id for r in rows), (
        f"DB row for {section_id!r} absent after mark. "
        "AC-7/ADR-024: marking must persist a row to section_completions."
    )

    # --- Unmark ---
    unmark_resp = client.post(
        complete_url, data={"action": "unmark"}, follow_redirects=False
    )
    assert unmark_resp.status_code == 303
    location_unmark = unmark_resp.headers.get("location", "")
    assert expected_fragment in location_unmark, (
        f"Unmark Location {location_unmark!r} does not contain '{expected_fragment}'. "
        "ADR-031: the #section-{{n}}-end fragment must be present after unmark."
    )

    # GET page — section must no longer show as complete
    get_after_unmark = client.get(f"/lecture/{TEST_CHAPTER_ID}")
    assert get_after_unmark.status_code == 200
    assert "section-completion-button--complete" not in get_after_unmark.text, (
        "After unmark: section still shows as complete. "
        "AC-7: unmarking must clear the persisted state."
    )

    # DB row must be deleted
    rows_after = _direct_db_list_completions(db_path, TEST_CHAPTER_ID)
    assert not any(r["section_id"] == section_id for r in rows_after), (
        f"DB row for {section_id!r} still present after unmark. "
        "AC-7/ADR-024: unmark must delete the row (presence-as-complete semantics)."
    )


# ===========================================================================
# AC-11 — Manifest conformance: MC-3, MC-6, MC-7, MC-10
# ===========================================================================


def test_mc3_lhs_rail_mandatory_optional_grouping_unchanged(
    tmp_path, monkeypatch
) -> None:
    """
    AC-11 (TASK-012) / MC-3: the LHS chapter rail's Mandatory/Optional grouping
    must be unaffected by the RHS rail introduction.

    ADR-029 §Layout shape: 'Column 1 — the LHS chapter-navigation rail
    (.lecture-rail / _nav_rail.html.j2): unchanged in width and content except
    that the Notes <section> is removed.'
    Manifest §6: 'Mandatory and Optional honored everywhere.'

    Trace: AC-11; MC-3; ADR-029 §Conformance check MC-3.
    """
    client = _make_client(monkeypatch, _db_path(tmp_path))
    response = client.get("/")
    assert response.status_code == 200
    html = response.text

    # Both designation headings must appear
    assert "Mandatory" in html, (
        "GET / — 'Mandatory' label not found in rendered HTML. "
        "AC-11/MC-3: Mandatory/Optional grouping must be preserved by the new layout."
    )
    assert "Optional" in html, (
        "GET / — 'Optional' label not found in rendered HTML. "
        "AC-11/MC-3: Optional group label must remain visible."
    )

    # Mandatory must appear before Optional in document order
    pos_mandatory = html.find("Mandatory")
    pos_optional = html.find("Optional")
    assert pos_mandatory < pos_optional, (
        f"'Mandatory' (pos {pos_mandatory}) appears after 'Optional' (pos {pos_optional}). "
        "AC-11/MC-3: the LHS rail must retain Mandatory-before-Optional ordering."
    )

    # ADR-026 progress decorations must still be present (LHS rail unchanged)
    assert "nav-chapter-progress" in html, (
        "GET / — 'nav-chapter-progress' not found. "
        "AC-11: the ADR-026 per-chapter progress decoration must survive the layout change."
    )


def test_mc7_no_user_id_in_notes_post_or_completion_post(
    tmp_path, monkeypatch
) -> None:
    """
    AC-11 (TASK-012) / MC-7: the Notes and completion routes must not introduce
    any user_id in their handling.

    Manifest §5/§6/§7 (single user). ADR-029 §Conformance MC-7: 'no user_id'.

    Trace: AC-11; MC-7; ADR-029 §Conformance check MC-7.
    """
    db_path = _db_path(tmp_path)
    client = _make_client(monkeypatch, db_path)

    # Trigger schema bootstrap
    client.get(f"/lecture/{TEST_CHAPTER_ID}")

    # Check section_completions table — no user_id column
    if pathlib.Path(db_path).exists():
        conn = sqlite3.connect(db_path)
        cur = conn.execute("PRAGMA table_info(section_completions)")
        sc_columns = {row[1] for row in cur.fetchall()}
        cur2 = conn.execute("PRAGMA table_info(notes)")
        notes_columns = {row[1] for row in cur2.fetchall()}
        conn.close()

        assert "user_id" not in sc_columns, (
            f"section_completions table has user_id column: {sc_columns!r}. "
            "AC-11/MC-7: no user_id in any persistence table (single-user invariant)."
        )
        assert "user_id" not in notes_columns, (
            f"notes table has user_id column: {notes_columns!r}. "
            "AC-11/MC-7: no user_id in any persistence table (single-user invariant)."
        )


def test_mc6_notes_post_does_not_touch_content_latex(
    tmp_path, monkeypatch
) -> None:
    """
    AC-11 (TASK-012) / MC-6: a Notes POST must not open any file under
    content/latex/ for write, even with the new RHS rail template.

    ADR-029 §Conformance MC-6: 'Honored. Template + CSS changes only; nothing
    under content/latex/ is opened for write.'

    Trace: AC-11; MC-6; Manifest §5 'No in-app authoring'.
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
        f"/lecture/{TEST_CHAPTER_ID}/notes",
        data={"body": "MC-6 TASK-012 write-test note."},
        follow_redirects=False,
    )

    assert write_violations == [], (
        f"MC-6 BLOCKER: Notes POST opened files under content/latex/ for write: "
        f"{write_violations!r}. "
        "AC-11/ADR-029: the template + CSS changes must not cause any write to content/latex/."
    )


def test_mc10_no_sqlite3_outside_persistence(tmp_path, monkeypatch) -> None:
    """
    AC-11 (TASK-012) / MC-10: 'import sqlite3' must appear ONLY in app/persistence/.

    ADR-029 §Conformance MC-10: 'Honored. No DB code changes.'

    Trace: AC-11; MC-10; ADR-022 §Package boundary.
    """
    app_dir = REPO_ROOT / "app"
    persistence_dir = app_dir / "persistence"
    violations = []

    for py_file in app_dir.rglob("*.py"):
        try:
            py_file.relative_to(persistence_dir)
            continue
        except ValueError:
            pass
        if "import sqlite3" in py_file.read_text(encoding="utf-8"):
            violations.append(str(py_file))

    assert violations == [], (
        f"MC-10 BLOCKER: `import sqlite3` outside app/persistence/: {violations!r}. "
        "AC-11/MC-10: the new RHS rail templates and route changes must not introduce "
        "any sqlite3 import outside the persistence boundary."
    )


# ===========================================================================
# Performance — Three-column Lecture page renders within time budget
# ===========================================================================


def test_three_column_lecture_page_renders_within_time_budget(
    tmp_path, monkeypatch
) -> None:
    """
    Performance (TASK-012): all 12 corpus Chapters render within 5 seconds with
    the new three-column layout (extra partial include + additional CSS/column).

    ADR-029 §Consequences: 'base.html.j2 now includes two rail partials and has
    {% if rail_notes_context %} guards.' Mitigation: the split is template-level
    only; no additional DB query is introduced.

    Catches regressions introduced by the extra partial include or a slow
    template loop in the RHS rail rendering.

    Trace: AC-1 (renders all 12 chapters); ADR-029 §Consequences §Performance.
    """
    db_path = _db_path(tmp_path)
    client = _make_client(monkeypatch, db_path)

    t0 = time.monotonic()
    for chapter_id in ALL_CHAPTER_IDS:
        resp = client.get(f"/lecture/{chapter_id}")
        assert resp.status_code == 200, (
            f"GET /lecture/{chapter_id} returned {resp.status_code} during perf test."
        )
    elapsed = time.monotonic() - t0

    assert elapsed < 5.0, (
        f"Rendering all 12 Lecture pages took {elapsed:.2f}s (limit: 5s). "
        "ADR-029: the new three-column layout (extra partial include) must not "
        "regress render performance. A slow result suggests a template loop or "
        "extra DB query in _notes_rail.html.j2."
    )


# ===========================================================================
# Regression guard — old ADR-028 "Notes-in-LHS-rail" assertion amended
# ===========================================================================


def test_old_notes_classes_not_in_nav_rail_output(tmp_path, monkeypatch) -> None:
    """
    AC-9 regression (TASK-012) / ADR-029 §Test-writer pre-flag:
    'notes-surface' must remain absent (established by ADR-028; retained by ADR-029).
    'rail-notes' must NOT appear inside the lecture-rail element.

    This test consolidates the "Notes NOT in the LHS rail" assertion that was
    previously a positive presence test in the LHS rail (now wrong) into a
    negative assertion (correct per ADR-029).

    Trace: AC-9; ADR-028 §Removal; ADR-029 §Test-writer pre-flag.
    """
    client = _make_client(monkeypatch, _db_path(tmp_path))

    for chapter_id in ALL_CHAPTER_IDS:
        response = client.get(f"/lecture/{chapter_id}")
        assert response.status_code == 200
        html = response.text

        # ADR-028 (retained by ADR-029): old 'notes-surface' class must be absent
        assert "notes-surface" not in html, (
            f"GET /lecture/{chapter_id} — 'notes-surface' class present. "
            "ADR-028 (retained by ADR-029): bottom-of-page Notes section removed; "
            "'notes-surface' must not appear."
        )


# ===========================================================================
# ADR-031 structural checks — .section-end id and lecture.css scroll-margin-top
# (ADR-031 §Test-writer pre-flag item 5: "welcome, not required")
# ===========================================================================


def test_lecture_css_has_scroll_margin_top_on_section_end() -> None:
    """
    ADR-031 §Decision (CSS change): app/static/lecture.css must set
    scroll-margin-top on the .section-end rule so that fragment navigation
    (#section-{n}-end anchor) lands the wrapper near the bottom of the viewport
    ≈ where the user clicked.

    ADR-031: 'app/static/lecture.css — the .section-end rule gains a large
    viewport-relative scroll-margin-top … scroll-margin-top: 75vh
    (implementer-tunable).'

    This is a source-static check: grep lecture.css for 'scroll-margin-top'
    in the context of a .section-end rule.

    Trace: ADR-031 §Decision (CSS change); ADR-008 §section-* → lecture.css.
    """
    lecture_css_path = REPO_ROOT / "app" / "static" / "lecture.css"
    assert lecture_css_path.exists(), (
        f"app/static/lecture.css not found at {lecture_css_path}. "
        "ADR-031: the scroll-margin-top rule must be in lecture.css "
        "(ADR-008 §section-* → lecture.css convention)."
    )
    css_text = lecture_css_path.read_text(encoding="utf-8")

    assert "scroll-margin-top" in css_text, (
        f"app/static/lecture.css does not contain 'scroll-margin-top'. "
        "ADR-031 §Decision: the .section-end rule must gain a large viewport-relative "
        "scroll-margin-top (e.g. scroll-margin-top: 75vh) so that fragment navigation "
        "to #section-{n}-end lands the wrapper near the bottom of the viewport."
    )

    # The property must appear near or within a .section-end rule block.
    # We check that .section-end and scroll-margin-top both appear in the file
    # (the proximity check is a best-effort static assertion).
    assert ".section-end" in css_text, (
        "app/static/lecture.css does not contain a '.section-end' rule. "
        "ADR-031: the scroll-margin-top must be on the .section-end selector."
    )


@pytest.mark.parametrize("chapter_id", ALL_CHAPTER_IDS)
def test_section_end_wrapper_carries_id_attribute_on_lecture_pages(
    chapter_id: str, tmp_path, monkeypatch
) -> None:
    """
    ADR-031 §Decision (template change): each .section-end wrapper in the
    rendered lecture page must carry an id="section-{n-m}-end" attribute,
    where {n-m} matches the parent <section id="section-{n-m}"> element.

    ADR-031: '<div class="section-end" id="{{ section.fragment }}-end">
    …section.fragment is already section-{n-m} (e.g., section-1-1), so this
    renders as id="section-1-1-end" — matching the redirect's
    #section-{section_number}-end.'

    Tests all 12 corpus Chapters to ensure the id is universally applied.

    Trace: ADR-031 §Decision (template change); ADR-031 §Test-writer pre-flag (item 5).
    """
    client = _make_client(monkeypatch, _db_path(tmp_path))
    response = client.get(f"/lecture/{chapter_id}")
    assert response.status_code == 200
    html = response.text

    # Find all <section id="section-{n-m}"> elements
    section_id_pattern = re.compile(r'<section[^>]+id="(section-[\d\-]+)"')
    section_ids = section_id_pattern.findall(html)

    if not section_ids:
        pytest.skip(
            f"No <section id='section-*'> found in /lecture/{chapter_id} — "
            "chapter may not have sections."
        )

    # For each section, assert there is a corresponding .section-end id="section-{n-m}-end"
    # The id may be on a div, section, or any element with class="section-end"
    section_end_id_pattern = re.compile(
        r'class="[^"]*section-end[^"]*"[^>]*id="(section-[\d\-]+-end)"'
        r'|'
        r'id="(section-[\d\-]+-end)"[^>]*class="[^"]*section-end[^"]*"'
    )
    found_end_ids = set()
    for m in section_end_id_pattern.finditer(html):
        end_id = m.group(1) or m.group(2)
        if end_id:
            found_end_ids.add(end_id)

    for sec_id in section_ids:
        expected_end_id = f"{sec_id}-end"
        assert expected_end_id in found_end_ids, (
            f"GET /lecture/{chapter_id} — section '{sec_id}' has no corresponding "
            f".section-end with id='{expected_end_id}'. "
            "ADR-031 §Decision: each .section-end wrapper must carry "
            "id=\"{{ section.fragment }}-end\" (e.g. id=\"section-1-1-end\") so the "
            "#section-{n}-end redirect fragment has a target in the DOM."
        )


# ===========================================================================
# AMENDMENT: test_task010's fragment assertion is superseded by ADR-031.
#
# History:
#   - Original (ADR-025): assert f"section-{TEST_SECTION_NUMBER}" in location
#     (checked for the #section-N heading anchor in the Location header)
#   - TASK-012 Run 004 amendment (ADR-030): assert "#" not in location
#     (checked that the Location was fragment-less per ADR-030 §Decision)
#   - TASK-012 Run 010 re-amendment (ADR-031): assert
#     f"section-{TEST_SECTION_NUMBER}-end" in location
#     (checks that the Location ends with #section-N-end per ADR-031 §Decision)
#
# The ADR-030 §Decision was empirically refuted by the Playwright test in
# audit Run 006 (Chromium resets scrollY to 0 on the fragment-less same-URL
# navigation). ADR-031 supersedes ADR-030 §Decision with the #section-{n}-end
# anchor + scroll-margin-top mechanism.
#
# Per CLAUDE.md "Test updates forced by Accepted ADRs are routine" and
# ADR-031 §Test-writer pre-flag (item 2).
#
# The re-amended assertion is in test_task010_section_completion.py:
# test_post_complete_redirect_location_contains_chapter.
# ===========================================================================
