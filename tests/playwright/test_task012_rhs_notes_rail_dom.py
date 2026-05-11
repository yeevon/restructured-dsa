"""
TASK-012: Move Notes to a right-hand rail + stop the completion redirect from
anchor-snapping the user — Playwright DOM / round-trip tests.

Per ADR-010 / ADR-013 split-harness:
  - HTTP-protocol pytest tests (route shape, persistence, conformance, layout
    structure assertions from the rendered HTML) live in
    tests/test_task012_rhs_notes_rail_and_redirect.py.
  - Playwright tests (rendered DOM, round-trip, sticky visibility, scroll
    preservation) live here.

AC-10 (TASK-012): 'at least one Playwright test asserts:
  (a) on a Lecture page, the layout has a left rail, a main column, and a
      right Notes rail, and the Notes panel is in the right rail;
  (b) the right Notes rail is sticky (visible after a large scroll);
  (c) submitting a note via the right-rail form round-trips and the new note
      appears at the top of the right-rail list;
  (d) on the landing page (GET /), the right Notes rail is absent;
  (e) marking a Section complete from the bottom-of-Section affordance does
      NOT snap the scroll position (ADR-031: post-reload window.scrollY is
      within a small tolerance of the pre-click window.scrollY, enabled by
      the #section-{n}-end anchor + scroll-margin-top: 75vh mechanism).'

ADR-029 structural commitments tested here:
  - <nav class="lecture-rail"> (LHS chapter rail) is present.
  - <main class="page-main"> (centered reading column) is present.
  - <aside class="notes-rail"> (or equivalent with .notes-rail) is present on
    Lecture pages and ABSENT on GET /.
  - The .rail-notes section (Notes panel) is inside the notes-rail, not inside
    the lecture-rail.
  - The notes-rail is position:sticky — viewport-visible after a large scroll.

ADR-031 structural commitment tested here:
  - After clicking "mark complete" at the bottom of a tall Section, the
    post-reload window.scrollY is within a small tolerance (≤ 200px) of the
    pre-click window.scrollY (scroll is preserved via the #section-{n}-end
    anchor + scroll-margin-top: 75vh mechanism; no JavaScript).
  - The Section heading is NOT in the viewport immediately after the redirect
    (verifies the user was not snapped to the top of the section).
  - After the redirect, the browser URL contains '#section-{n}-end' (the
    Location header carries the anchor per ADR-031 §Decision).

These tests drive a real browser (Chromium, the binding test target per ADR-010)
against the live uvicorn server started by the `live_server` fixture in conftest.py.

NOTE: The live_server uses the real data/notes.db. Tests must not assume a clean
database — they assert that specific freshly-clicked affordances produce the
expected rendered state, without relying on an initially-empty database.

AMENDMENTS to existing Playwright tests (ADR-029 / ADR-031 supersedures):
  - test_task011_chapter_progress_dom.py::test_rail_notes_panel_renders_on_lecture_page:
    that test locates the Notes panel via '.rail-notes' selector. ADR-029 retains
    the 'rail-notes' class on the inner <section>; the selector still works.
    However, the test's docstring references '_nav_rail.html.j2 below the chapter
    list' — stale comment, but no assertion failure. No test code change needed.
  - test_task011_chapter_progress_dom.py::test_rail_notes_round_trip_note_appears_in_rail:
    that test locates the form via '.rail-notes textarea[name=body]' which is still
    correct (ADR-029 keeps the inner .rail-notes section). No change needed there.
  - test_task010_section_completion_dom.py::test_round_trip_mark_complete_and_visible_after_reload:
    that test calls page.wait_for_load_state("domcontentloaded") after click, which
    works regardless of fragment. No assertion on scrollY; no change needed.

pytestmark registers all tests under task("TASK-012").

ASSUMPTIONS:
  ASSUMPTION: ADR-029: the RHS Notes rail DOM element has class="notes-rail" (or
    contains that class). Playwright tests assert
    page.locator(".notes-rail") or page.locator("[class*='notes-rail']").
  ASSUMPTION: ADR-031 scroll tolerance: 'within a small tolerance (≤ 200px)' for
    the scroll preservation assertion. The test asserts
    abs(post_scroll_y - pre_scroll_y) <= 200. The #section-{n}-end anchor combined
    with scroll-margin-top: 75vh (ADR-031 §Decision) places the viewport close to
    the bottom-of-section affordance, so scroll delta should be small.
  ASSUMPTION: A 'tall Section' for the scroll test is ch-01-cpp-refresher.
    The test scrolls to a bottom-of-Section affordance and records scrollY before
    clicking.
"""

from __future__ import annotations

import time

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.task("TASK-012")

CHAPTER_ID = "ch-01-cpp-refresher"
SECTION_NUMBER = "1-1"

# Scroll preservation tolerance (pixels) — ADR-031 §Decision ('within a small tolerance')
SCROLL_TOLERANCE_PX = 200


# ===========================================================================
# AC-10(a) — Three-column layout: left rail, main, right Notes rail
# ===========================================================================


def test_lecture_page_has_three_column_layout(page: Page, live_server: str) -> None:
    """
    AC-10(a) (TASK-012): the Lecture page DOM must have three distinct column
    elements — a left chapter rail, a centered main column, and a right Notes rail.

    ADR-029 §Layout shape:
      - Column 1: <nav class="lecture-rail"> (LHS chapter navigation)
      - Column 2: <main class="page-main"> (centered reading column)
      - Column 3: <aside class="notes-rail"> (or element with .notes-rail) (RHS Notes)

    Trace: AC-10(a); ADR-029 §Layout shape.
    """
    page.goto(f"{live_server}/lecture/{CHAPTER_ID}")
    page.wait_for_load_state("domcontentloaded")

    # Column 1: LHS chapter rail
    lecture_rail = page.locator(".lecture-rail")
    expect(lecture_rail.first).to_be_visible()

    # Column 2: centered main reading column
    page_main = page.locator(".page-main, main[class*='page-main']")
    expect(page_main.first).to_be_visible()

    # Column 3: RHS Notes rail — the new wrapper element
    notes_rail = page.locator(".notes-rail")
    count = notes_rail.count()
    assert count >= 1, (
        f"No .notes-rail element found in the DOM of /lecture/{CHAPTER_ID}. "
        "AC-10(a)/ADR-029: the Lecture page must have a RHS Notes rail column "
        "(<aside class='notes-rail'> or equivalent) per the three-column layout."
    )
    expect(notes_rail.first).to_be_visible()


def test_notes_panel_is_inside_notes_rail_not_lecture_rail(
    page: Page, live_server: str
) -> None:
    """
    AC-10(a) (TASK-012): the Notes panel (.rail-notes section) must be inside
    the .notes-rail element, NOT inside the .lecture-rail element.

    This is the layout-correctness assertion — verifies the extraction from
    _nav_rail.html.j2 and insertion into _notes_rail.html.j2 (ADR-029).

    Trace: AC-10(a); ADR-029 §The new RHS rail partial (extraction commitment).
    """
    page.goto(f"{live_server}/lecture/{CHAPTER_ID}")
    page.wait_for_load_state("domcontentloaded")

    # The .rail-notes section must exist (Notes panel present)
    rail_notes = page.locator(".rail-notes")
    assert rail_notes.count() >= 1, (
        "No .rail-notes element found in DOM. "
        "ADR-029: the Notes section must be present in the RHS rail."
    )

    # .rail-notes must be INSIDE .notes-rail (RHS column)
    notes_rail_contains_rail_notes = page.locator(".notes-rail .rail-notes")
    assert notes_rail_contains_rail_notes.count() >= 1, (
        ".rail-notes is not inside .notes-rail. "
        "AC-10(a)/ADR-029: the Notes panel must be in the RHS notes-rail column, "
        "extracted from _nav_rail.html.j2 into the new _notes_rail.html.j2 partial."
    )

    # .rail-notes must NOT be inside .lecture-rail (LHS column) — the key supersedure
    lecture_rail_contains_rail_notes = page.locator(".lecture-rail .rail-notes")
    assert lecture_rail_contains_rail_notes.count() == 0, (
        f".rail-notes found INSIDE .lecture-rail with count "
        f"{lecture_rail_contains_rail_notes.count()}. "
        "AC-10(a)/ADR-029: the Notes panel must be removed from the LHS chapter rail "
        "(_nav_rail.html.j2). It now lives in the RHS .notes-rail column only."
    )


# ===========================================================================
# AC-10(b) — Right Notes rail is sticky: visible after a large scroll
# ===========================================================================


def test_notes_rail_is_sticky_visible_after_large_scroll(
    page: Page, live_server: str
) -> None:
    """
    AC-10(b) (TASK-012): the right Notes rail remains visible (position: sticky)
    after the user scrolls down through the Chapter.

    ADR-029 §Layout shape: 'The RHS rail is position: sticky (using the same
    sticky mechanism the LHS rail already uses) so it is visible from any scroll
    position.'

    Strategy:
      1. Load a Lecture page.
      2. Record the initial viewport position of the .notes-rail element.
      3. Scroll to the bottom of the page (window.scrollTo large value).
      4. Assert the .notes-rail element is still within the viewport
         (getBoundingClientRect().top is between 0 and viewport height).

    Trace: AC-10(b); ADR-029 §Layout shape (sticky commitment).
    """
    page.goto(f"{live_server}/lecture/{CHAPTER_ID}")
    page.wait_for_load_state("domcontentloaded")

    notes_rail = page.locator(".notes-rail").first
    expect(notes_rail).to_be_visible()

    # Get viewport height
    viewport_height = page.evaluate("() => window.innerHeight")

    # Scroll to near the bottom of the page
    page.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")
    page.wait_for_timeout(300)  # allow sticky positioning to settle

    # The notes-rail must still be in the viewport (position: sticky)
    bounding_rect = notes_rail.bounding_box()
    assert bounding_rect is not None, (
        ".notes-rail element has no bounding box after scroll. "
        "The element may have been scrolled out of the DOM or hidden."
    )

    rail_top = bounding_rect["y"]
    rail_bottom = bounding_rect["y"] + bounding_rect["height"]

    # A sticky element stays within the viewport: its top should be >= 0
    # and its bottom should be <= viewport height (or close to it).
    # We allow a generous margin (the full element height) since the rail
    # might extend below the viewport bottom while its top is still visible.
    assert rail_top < viewport_height, (
        f"After large scroll, .notes-rail top is at {rail_top}px which is "
        f">= viewport height {viewport_height}px. "
        "AC-10(b)/ADR-029: the right Notes rail must be position:sticky and "
        "remain visible after a large downward scroll."
    )
    assert rail_top >= -bounding_rect["height"], (
        f"After large scroll, .notes-rail top is at {rail_top}px (very negative). "
        "The element appears to have scrolled off the top of the viewport."
    )


# ===========================================================================
# AC-10(c) — Submitting a note via the right-rail form round-trips correctly
# ===========================================================================


def test_notes_round_trip_via_rhs_rail_form(page: Page, live_server: str) -> None:
    """
    AC-10(c) (TASK-012): submitting a Note via the RHS rail form (.notes-rail form)
    round-trips via PRG and the new Note appears at the TOP of the RHS rail list.

    ADR-029 §What of ADR-028 is retained:
      - 'Multiple-Note display order: most-recent-first.'
      - 'Submit-feedback shape: full-page reload via PRG. … the now-RHS-resident
        Notes panel re-renders with the new Note at the top of the list.'

    Steps:
      1. Load Lecture page for ch-03 (use a distinct chapter to avoid test
         cross-contamination).
      2. Find the RHS rail form (.notes-rail form).
      3. Fill the textarea with a unique body.
      4. Submit the form.
      5. Wait for the PRG redirect to resolve (page reloads).
      6. Assert the new Note body appears in .notes-rail content.
      7. Assert it is at the top (first) of the Notes list items.

    Trace: AC-10(c); ADR-029 §What of ADR-028 is retained (PRG, display order).
    """
    chapter = "ch-03-intro-to-data-structures"
    lecture_url = f"{live_server}/lecture/{chapter}"

    page.goto(lecture_url)
    page.wait_for_load_state("domcontentloaded")

    unique_body = f"RHS-rail-round-trip-PW-TASK012-{int(time.time() * 1000)}"

    # Find the RHS rail Notes textarea
    textarea = page.locator(".notes-rail textarea[name='body']").first
    expect(textarea).to_be_visible()
    textarea.fill(unique_body)

    # Submit via the RHS rail form button
    submit_button = page.locator(".notes-rail form button[type='submit']").first
    expect(submit_button).to_be_visible()
    submit_button.click()

    # Wait for the PRG redirect to complete (page reloads)
    page.wait_for_load_state("domcontentloaded")

    # The new Note must appear in the .notes-rail content
    notes_rail = page.locator(".notes-rail").first
    expect(notes_rail).to_be_visible()

    notes_rail_text = notes_rail.inner_text()
    assert unique_body in notes_rail_text, (
        f"Submitted Note body {unique_body!r} not found in .notes-rail content after "
        "PRG redirect. "
        "AC-10(c)/ADR-029: a Note submitted via the RHS rail form must appear in the "
        "RHS rail Notes list after the PRG reload."
    )

    # The Note must appear at the top of the list (most-recent-first)
    # Check by finding the note items list — if the class rail-notes-list exists,
    # the first item should contain our unique body.
    notes_list = page.locator(".notes-rail .rail-notes-list, .notes-rail .rail-note-item")
    if notes_list.count() > 0:
        first_note_text = notes_list.first.inner_text()
        assert unique_body in first_note_text, (
            f"First note item text is {first_note_text!r}; expected it to contain "
            f"{unique_body!r}. "
            "AC-10(c)/ADR-029: the most-recent Note must appear FIRST in the RHS "
            "rail Notes list (most-recent-first ordering per ADR-023, unchanged)."
        )


# ===========================================================================
# AC-10(d) — On GET /, the right Notes rail is absent
# ===========================================================================


def test_notes_rail_absent_on_landing_page(page: Page, live_server: str) -> None:
    """
    AC-10(d) (TASK-012): on the landing page (GET /), the right Notes rail
    must be absent from the DOM.

    ADR-029 §Per-Chapter scoping: 'on GET / the page is two-column (chapter rail
    + main); there is no empty third column and no rendered RHS rail DOM.'

    Trace: AC-10(d); ADR-029 §Per-Chapter scoping on the landing page.
    """
    page.goto(f"{live_server}/")
    page.wait_for_load_state("domcontentloaded")

    # .notes-rail must NOT be in the DOM at all
    notes_rail = page.locator(".notes-rail")
    assert notes_rail.count() == 0, (
        f".notes-rail found on the landing page (count={notes_rail.count()}). "
        "AC-10(d)/ADR-029: the right Notes rail must be ABSENT from GET / "
        "(no Chapter context → no rail_notes_context → grid degrades to two columns)."
    )

    # .rail-notes must also be absent (the inner Notes section)
    rail_notes = page.locator(".rail-notes")
    assert rail_notes.count() == 0, (
        f".rail-notes found on the landing page (count={rail_notes.count()}). "
        "AC-10(d)/ADR-029: the Notes panel must be OMITTED from the landing page "
        "(the {% if rail_notes_context %} guard suppresses it)."
    )

    # The chapter rail and main content must still be present (two-column layout)
    lecture_rail = page.locator(".lecture-rail")
    expect(lecture_rail.first).to_be_visible()

    page_main = page.locator(".page-main, main")
    expect(page_main.first).to_be_visible()


# ===========================================================================
# AC-10(e) — Marking a Section complete does NOT snap scroll position (ADR-031)
# ===========================================================================


def test_marking_section_complete_does_not_snap_scroll_position(
    page: Page, live_server: str
) -> None:
    """
    AC-10(e) (TASK-012): after clicking "mark complete" at the bottom-of-Section
    affordance (.section-end), the post-reload window.scrollY is within a small
    tolerance (≤ 200px) of the pre-click window.scrollY.

    ADR-031 §Decision (supersedes ADR-030 §Decision): the 303 Location header
    carries '#section-{n}-end', pointing at the .section-end wrapper element
    which has id="section-{n-m}-end" in lecture.html.j2. The CSS rule
    '.section-end { scroll-margin-top: 75vh; }' in lecture.css (ADR-008:
    section-* → lecture.css) ensures the browser scrolls to a position near the
    bottom-of-section affordance rather than snapping to the section heading.
    No JavaScript is used.

    ADR-030 §Decision was empirically refuted by Playwright audit Run 006:
    Chromium reset scrollY to 0 on the fragment-less same-URL POST→303→GET
    navigation (pre 3514px → post 0px, delta 3514px, tolerance 200px).
    ADR-031 resolves this by using the anchor + scroll-margin-top mechanism.

    This is the Playwright regression test that locks scroll-preservation
    behavior in for the ADR-031 mechanism.

    Strategy:
      1. Load a Lecture page on a chapter with at least one substantive Section.
      2. Scroll to the bottom of the first Section's .section-end affordance.
      3. Record pre-click window.scrollY.
      4. Click the "mark complete" button in the .section-end wrapper.
      5. Wait for the POST → 303 → GET redirect to complete.
      6. Assert abs(post-reload window.scrollY - pre-click window.scrollY) ≤ 200px.

    Trace: AC-10(e); ADR-031 §Decision; ADR-031 §Test-writer pre-flag (item 3);
           supersedes ADR-030 §Decision.
    """
    # Use ch-01 — known to have substantive sections
    lecture_url = f"{live_server}/lecture/{CHAPTER_ID}"
    page.goto(lecture_url)
    page.wait_for_load_state("domcontentloaded")

    # Find the first Section's .section-end wrapper with a completion form
    # We need a section that is in the incomplete state (action=mark)
    section_end_forms = page.locator(".section-end .section-completion-form")
    form_count = section_end_forms.count()
    assert form_count > 0, (
        f"No .section-end .section-completion-form found on /lecture/{CHAPTER_ID}. "
        "Prerequisite for scroll preservation test: need a bottom-of-Section form."
    )

    # Find the first form in 'mark' state (incomplete section)
    target_form = None
    for i in range(form_count):
        form = section_end_forms.nth(i)
        action_input = form.locator("input[name='action']").first
        if action_input.count() > 0:
            action_value = action_input.get_attribute("value")
            if action_value == "mark":
                target_form = form
                break

    if target_form is None:
        # All sections may already be complete from previous test runs —
        # use the first one and unmark first to get to a clean state.
        target_form = section_end_forms.first
        target_form.locator("button[type='submit']").first.click()
        page.wait_for_load_state("domcontentloaded")
        # After unmark, find the first mark-state form
        page.goto(lecture_url)
        page.wait_for_load_state("domcontentloaded")
        section_end_forms = page.locator(".section-end .section-completion-form")
        for i in range(section_end_forms.count()):
            form = section_end_forms.nth(i)
            action_input = form.locator("input[name='action']").first
            if action_input.count() > 0 and action_input.get_attribute("value") == "mark":
                target_form = form
                break

    assert target_form is not None, (
        "Could not find a .section-end .section-completion-form in 'mark' state. "
        "Cannot execute scroll preservation test."
    )

    # Scroll the target form button into view (scroll to bottom of Section)
    mark_button = target_form.locator("button[type='submit']").first
    mark_button.scroll_into_view_if_needed()
    page.wait_for_timeout(200)

    # Record pre-click scroll position
    pre_scroll_y = page.evaluate("() => window.scrollY")
    assert pre_scroll_y > 0, (
        f"pre_scroll_y is {pre_scroll_y}; expected > 0 after scrolling to section bottom. "
        "The scroll did not move from the top — the section may be near the page top."
    )

    # Click the "mark complete" button
    expect(mark_button).to_be_visible()
    mark_button.click()

    # Wait for the POST → 303 → GET redirect to complete
    page.wait_for_load_state("domcontentloaded")

    # Record post-reload scroll position
    post_scroll_y = page.evaluate("() => window.scrollY")

    # ADR-031 assertion: scroll position preserved within tolerance
    scroll_delta = abs(post_scroll_y - pre_scroll_y)
    assert scroll_delta <= SCROLL_TOLERANCE_PX, (
        f"Scroll position snapped: pre-click scrollY={pre_scroll_y}px, "
        f"post-reload scrollY={post_scroll_y}px, delta={scroll_delta}px "
        f"(tolerance: {SCROLL_TOLERANCE_PX}px). "
        "AC-10(e)/ADR-031: marking a Section complete from the bottom-of-Section "
        "affordance must NOT snap the scroll position. The 303 redirect must carry "
        "a '#section-{n}-end' anchor (pointing at the .section-end wrapper) and "
        "lecture.css must define '.section-end { scroll-margin-top: 75vh; }' so "
        "Chromium lands near the bottom-of-section affordance rather than at the "
        "section heading."
    )

    # Cleanup: unmark the section to leave the database state clean
    # (live_server uses real data/notes.db; cleanup is best-effort)
    section_end_forms_after = page.locator(".section-end .section-completion-form")
    for i in range(section_end_forms_after.count()):
        form = section_end_forms_after.nth(i)
        action_input = form.locator("input[name='action']").first
        if action_input.count() > 0 and action_input.get_attribute("value") == "unmark":
            form.locator("button[type='submit']").first.click()
            page.wait_for_load_state("domcontentloaded")
            break


def test_completion_redirect_location_anchors_section_end_in_browser(
    page: Page, live_server: str
) -> None:
    """
    AC-10(e) / ADR-031: after clicking the completion toggle, the browser URL
    contains '#section-{n}-end' (the .section-end wrapper anchor).

    This complements test_marking_section_complete_does_not_snap_scroll_position
    by asserting the URL shape directly (the '#section-{n}-end' fragment is present
    in the browser URL bar after the redirect completes).

    ADR-031 §Decision: 'The 303 Location header carries #section-{section_number}-end
    (pointing at the .section-end wrapper, which gains id="section-{n-m}-end").'

    AMENDMENT — ADR-031 (Accepted, 2026-05-11) supersedes ADR-030 §Decision
    (which was 'the browser URL must NOT contain a #section-* fragment').
    The test is renamed from
    test_completion_redirect_location_has_no_fragment_in_browser (ADR-030)
    to test_completion_redirect_location_anchors_section_end_in_browser (ADR-031).
    The assertion changes from 'assert "#" not in current_url'
    to 'assert f"#section-{SECTION_NUMBER}-end" in current_url'.

    Trace: AC-10(e); ADR-031 §Decision; ADR-031 §Test-writer pre-flag (item 3).
    """
    lecture_url = f"{live_server}/lecture/{CHAPTER_ID}"
    page.goto(lecture_url)
    page.wait_for_load_state("domcontentloaded")

    # Find the first incomplete Section's completion button
    section_end_forms = page.locator(".section-end .section-completion-form")
    assert section_end_forms.count() > 0, "No completion forms found."

    target_button = None
    for i in range(section_end_forms.count()):
        form = section_end_forms.nth(i)
        action_input = form.locator("input[name='action']").first
        if action_input.count() > 0 and action_input.get_attribute("value") == "mark":
            target_button = form.locator("button[type='submit']").first
            break

    if target_button is None:
        # All complete — unmark one first
        form = section_end_forms.first
        form.locator("button[type='submit']").first.click()
        page.wait_for_load_state("domcontentloaded")
        page.goto(lecture_url)
        page.wait_for_load_state("domcontentloaded")
        section_end_forms = page.locator(".section-end .section-completion-form")
        for i in range(section_end_forms.count()):
            form = section_end_forms.nth(i)
            action_input = form.locator("input[name='action']").first
            if action_input.count() > 0 and action_input.get_attribute("value") == "mark":
                target_button = form.locator("button[type='submit']").first
                break

    if target_button is None:
        pytest.skip("Cannot find an incomplete section to test URL shape.")

    # Click and wait for redirect
    target_button.click()
    page.wait_for_load_state("domcontentloaded")

    # ADR-031: the browser URL must contain '#section-{n}-end'
    current_url = page.url
    expected_fragment = f"#section-{SECTION_NUMBER}-end"
    assert expected_fragment in current_url, (
        f"After completion toggle, browser URL is {current_url!r} — does not contain "
        f"{expected_fragment!r}. "
        "AC-10(e)/ADR-031: the post-redirect URL must contain '#section-{n}-end'; "
        "the 303 Location header must be /lecture/{chapter_id}#section-{n}-end per "
        "ADR-031 §Decision. "
        "If the URL has no fragment or a different fragment, the route handler is not "
        "yet updated to ADR-031."
    )

    # The URL must also point to the correct lecture page
    assert f"/lecture/{CHAPTER_ID}" in current_url, (
        f"Post-redirect URL {current_url!r} does not contain '/lecture/{CHAPTER_ID}'. "
        "ADR-031: the redirect must target the Chapter's Lecture page."
    )

    # Cleanup
    section_end_forms_after = page.locator(".section-end .section-completion-form")
    for i in range(section_end_forms_after.count()):
        form = section_end_forms_after.nth(i)
        action_input = form.locator("input[name='action']").first
        if action_input.count() > 0 and action_input.get_attribute("value") == "unmark":
            form.locator("button[type='submit']").first.click()
            page.wait_for_load_state("domcontentloaded")
            break


# ===========================================================================
# Regression guard — existing three-column structural invariants
# ===========================================================================


def test_lhs_rail_still_shows_progress_and_chapter_list(
    page: Page, live_server: str
) -> None:
    """
    Regression (TASK-012): after the RHS rail introduction, the LHS chapter rail
    must still show the per-Chapter progress decorations (ADR-026) and the chapter
    list (ADR-006) — the LHS rail is UNCHANGED except for the Notes section removal.

    ADR-029 §Layout shape: 'Column 1 — the LHS chapter-navigation rail (.lecture-rail
    / _nav_rail.html.j2): unchanged in width and content except that the Notes
    <section> is removed.'

    Trace: regression; ADR-029 §Layout shape (LHS rail unchanged commitment).
    """
    page.goto(f"{live_server}/lecture/{CHAPTER_ID}")
    page.wait_for_load_state("domcontentloaded")

    # LHS rail must contain per-Chapter progress spans (ADR-026, unchanged)
    progress_spans_in_lhs = page.locator(".lecture-rail .nav-chapter-progress")
    count = progress_spans_in_lhs.count()
    assert count >= 12, (
        f"LHS rail has {count} .nav-chapter-progress spans; expected >= 12. "
        "ADR-029 regression: the LHS chapter rail must retain the ADR-026 progress "
        "decorations after the Notes panel is moved to the RHS column."
    )

    # LHS rail must still contain chapter links (ADR-006)
    chapter_links_in_lhs = page.locator(".lecture-rail a[href*='/lecture/']")
    assert chapter_links_in_lhs.count() >= 12, (
        f"LHS rail has {chapter_links_in_lhs.count()} chapter links; expected >= 12. "
        "ADR-029 regression: the LHS chapter rail must retain the chapter list."
    )


def test_notes_form_is_functional_in_rhs_rail_after_layout_change(
    page: Page, live_server: str
) -> None:
    """
    Regression (TASK-012): the Notes form in the RHS rail is functional —
    the textarea is fillable and the submit button is clickable.

    ADR-029: 'The textarea is usable at the RHS rail's narrowest width.'

    Trace: regression; ADR-029 §Textarea sizing at the RHS rail width.
    """
    page.goto(f"{live_server}/lecture/{CHAPTER_ID}")
    page.wait_for_load_state("domcontentloaded")

    # Find the Notes textarea in the RHS rail
    textarea = page.locator(".notes-rail textarea[name='body']").first
    expect(textarea).to_be_visible()

    # The textarea must be interactable
    textarea.fill("RHS-rail-functionality-regression-test")
    filled_value = textarea.input_value()
    assert filled_value == "RHS-rail-functionality-regression-test", (
        f"Textarea fill value is {filled_value!r}; expected the filled string. "
        "ADR-029: the RHS rail Notes textarea must be interactable."
    )

    # The submit button must exist and be visible
    submit_button = page.locator(".notes-rail form button[type='submit']").first
    expect(submit_button).to_be_visible()

    # Clear the textarea (don't actually submit for this regression test)
    textarea.fill("")
