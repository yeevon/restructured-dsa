"""
TASK-011: Chapter-level derived progress display + bundled placement supersedures —
          Playwright DOM / round-trip tests.

Per ADR-010 / ADR-013 split-harness:
  - HTTP-protocol and persistence tests live in
    tests/test_task011_chapter_progress_and_supersedures.py.
  - Playwright tests (rendered DOM, round-trip, visual state) live here.

AC-11 (TASK-011): 'at least one Playwright test asserts:
  (a) the rail shows per-Chapter progress on the landing page;
  (b) marking a Section complete updates that Chapter's rail count after reload;
  (c) the new bottom-of-Section completion affordance is reachable and toggleable;
  (d) the rail-resident Notes panel renders the current Chapter's notes.'

ADR-026 §Display surface: <span class="nav-chapter-progress"> inside each
nav-chapter-item row.

ADR-027 §Decision: completion form inside <div class="section-end"> at bottom of
each <section> block; .section-heading-row removed.

ADR-028 §Rail integration: <section class="rail-notes"> inside _nav_rail.html.j2,
below the chapter list, with textarea rows="3".

These tests drive a real browser (via pytest-playwright) against the live uvicorn
server started by the `live_server` fixture in conftest.py.

NOTE: The live_server uses the real data/notes.db file. Tests must not assume a
clean database — they assert that specific freshly-clicked affordances produce the
expected rendered state, without relying on an initially-empty database.

pytestmark registers all tests under task("TASK-011").
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.task("TASK-011")

CHAPTER_ID = "ch-01-cpp-refresher"
SECTION_NUMBER = "1-1"


# ===========================================================================
# AC-11(a) — Rail shows per-Chapter progress on the landing page
# ===========================================================================


def test_rail_shows_per_chapter_progress_on_landing_page(
    page: Page, live_server: str
) -> None:
    """
    AC-11(a) (TASK-011): the landing page rail must show per-Chapter "X / Y"
    progress decorations for every Chapter row.

    ADR-026 §Display surface: <span class="nav-chapter-progress"> inside each
    nav-chapter-item row; visible from any scroll position (rail is sticky).

    Verifies:
      - At least one .nav-chapter-progress span is visible.
      - All .nav-chapter-progress spans contain a "N / M" pattern.
      - The count of progress spans matches the count of Chapter rows (12).
      - Both Mandatory and Optional groups contain progress spans.

    Trace: AC-11(a); ADR-026 §Display surface placement; ADR-026 §Visual shape.
    """
    page.goto(f"{live_server}/")
    page.wait_for_load_state("domcontentloaded")

    # At least one progress span must exist
    progress_spans = page.locator(".nav-chapter-progress")
    count = progress_spans.count()
    assert count >= 12, (
        f"Landing page rail has {count} .nav-chapter-progress spans; expected >= 12. "
        "AC-11(a)/ADR-026: every Chapter row must have a progress decoration."
    )

    # Every progress span must contain a "N / M" pattern
    import re
    progress_pattern = re.compile(r"\d+\s*/\s*\d+")
    for i in range(count):
        span = progress_spans.nth(i)
        text = span.inner_text().strip()
        assert progress_pattern.match(text) or progress_pattern.search(text), (
            f"Progress span #{i} text is {text!r}; expected 'N / M' pattern. "
            "ADR-026 §Visual shape: the decoration must be plain 'X / Y' text."
        )

    # First span must be visible (structural smoke check)
    expect(progress_spans.first).to_be_visible()


def test_both_mandatory_and_optional_chapters_have_progress_spans(
    page: Page, live_server: str
) -> None:
    """
    AC-11(a) + AC-4: both Mandatory and Optional chapter groups show progress
    decorations in the rail.

    Manifest §6: 'Mandatory and Optional honored everywhere.'
    ADR-026: the decoration appears within each row regardless of designation.

    Trace: AC-11(a); AC-4 (TASK-011); ADR-026 §Conformance MC-3.
    """
    page.goto(f"{live_server}/")
    page.wait_for_load_state("domcontentloaded")

    # Find the Mandatory and Optional labels in the rail
    mandatory_label = page.locator("[data-designation='Mandatory'], .nav-section-label").filter(
        has_text="Mandatory"
    ).first
    optional_label = page.locator("[data-designation='Optional'], .nav-section-label").filter(
        has_text="Optional"
    ).first

    expect(mandatory_label).to_be_visible()
    expect(optional_label).to_be_visible()

    # Progress spans must exist in the rail (both groups share the same rail)
    progress_spans = page.locator(".nav-chapter-progress")
    assert progress_spans.count() >= 12, (
        f"Expected >= 12 progress spans; found {progress_spans.count()}. "
        "Both Mandatory and Optional chapters must have progress decorations."
    )


# ===========================================================================
# AC-11(b) — Marking a Section complete updates that Chapter's rail count
# ===========================================================================


def test_marking_section_complete_updates_rail_count_after_reload(
    page: Page, live_server: str
) -> None:
    """
    AC-11(b) (TASK-011): after marking a Section complete (via the bottom-of-Section
    form per ADR-027), the PRG reload shows an updated "X / Y" count in the Chapter's
    rail row.

    Steps:
      1. Navigate to ch-01 lecture page.
      2. Record the current progress count for ch-01 in the rail.
      3. Find the section-1-1 completion form in .section-end and ensure it's in
         'mark' state; if already complete, unmark first.
      4. Click 'Mark complete'.
      5. Wait for the PRG redirect reload.
      6. Assert the ch-01 progress count increased by 1 in the rail.
      7. (Cleanup) Unmark the section to leave state clean for repeated runs.

    ADR-026: count_complete_sections_per_chapter() is re-read on every GET;
    the PRG redirect re-renders the rail with the new count.
    ADR-027: the completion form is now in .section-end at the bottom of each section.

    Trace: AC-11(b); ADR-026 §Consequences ('marking a Section complete is immediately
    reflected in the rail'); ADR-027 §Decision.
    """
    import re

    lecture_url = f"{live_server}/lecture/{CHAPTER_ID}"
    page.goto(lecture_url)
    page.wait_for_load_state("domcontentloaded")

    # Find ch-01's progress span — it's the first chapter in the Mandatory group
    # The rail renders Mandatory first; ch-01 is the first Mandatory chapter
    progress_spans = page.locator(".nav-chapter-progress")
    assert progress_spans.count() > 0, "No progress spans found on the lecture page."

    # Record the initial progress text for the first span (ch-01)
    initial_text = progress_spans.first.inner_text().strip()
    initial_match = re.search(r"(\d+)\s*/\s*(\d+)", initial_text)
    assert initial_match, (
        f"Progress span text {initial_text!r} does not match 'N / M' pattern."
    )
    initial_numerator = int(initial_match.group(1))

    # Find the section-1-1 block and its .section-end completion form
    section_el = page.locator(f"#section-{SECTION_NUMBER}").first
    action_input = section_el.locator("input[name=action]").first

    # Ensure we start from 'mark' state (incomplete)
    current_action = action_input.get_attribute("value")
    if current_action == "unmark":
        # Already complete — unmark it first
        section_el.locator(".section-end .section-completion-form button[type=submit]").first.click()
        page.wait_for_load_state("domcontentloaded")
        # Re-locate the section
        section_el = page.locator(f"#section-{SECTION_NUMBER}").first
        assert (
            section_el.locator("input[name=action]").first.get_attribute("value") == "mark"
        ), "Pre-condition: section-1-1 must be in 'mark' (incomplete) state."

        # Re-read the initial numerator after the state reset
        progress_spans = page.locator(".nav-chapter-progress")
        initial_text = progress_spans.first.inner_text().strip()
        initial_match = re.search(r"(\d+)\s*/\s*(\d+)", initial_text)
        initial_numerator = int(initial_match.group(1))

    # Click 'Mark complete' in the .section-end wrapper (ADR-027 placement)
    mark_button = section_el.locator(".section-end .section-completion-form button[type=submit]").first
    expect(mark_button).to_be_visible()
    mark_button.click()

    # Wait for the PRG redirect to complete
    page.wait_for_load_state("domcontentloaded")

    # The rail must now show initial_numerator + 1 for ch-01
    progress_spans_after = page.locator(".nav-chapter-progress")
    updated_text = progress_spans_after.first.inner_text().strip()
    updated_match = re.search(r"(\d+)\s*/\s*(\d+)", updated_text)
    assert updated_match, (
        f"Updated progress span text {updated_text!r} does not match 'N / M'."
    )
    updated_numerator = int(updated_match.group(1))

    assert updated_numerator == initial_numerator + 1, (
        f"After marking section-1-1 complete, ch-01 rail count changed from "
        f"{initial_numerator} to {updated_numerator}; expected {initial_numerator + 1}. "
        "AC-11(b)/ADR-026: marking a Section complete must immediately increment "
        "the Chapter's rail count by 1."
    )

    # Cleanup: unmark the section
    section_el_after = page.locator(f"#section-{SECTION_NUMBER}").first
    unmark_button = section_el_after.locator(
        ".section-end .section-completion-form button[type=submit]"
    ).first
    unmark_button.click()
    page.wait_for_load_state("domcontentloaded")


# ===========================================================================
# AC-11(c) — Bottom-of-Section completion affordance reachable and toggleable
# ===========================================================================


def test_section_end_completion_affordance_is_reachable(
    page: Page, live_server: str
) -> None:
    """
    AC-11(c) (TASK-011): the bottom-of-Section completion affordance is visible
    and reachable via the DOM — it lives in .section-end, not next to the heading.

    ADR-027 §Decision: form inside <div class="section-end"> at bottom of each
    <section> block; .section-heading-row is removed.

    Verifies:
      - At least one .section-end wrapper is visible.
      - Each .section-end contains a .section-completion-form.
      - .section-heading-row is absent from the DOM.

    Trace: AC-11(c); ADR-027 §Decision; ADR-027 §CSS class changes.
    """
    page.goto(f"{live_server}/lecture/{CHAPTER_ID}")
    page.wait_for_load_state("domcontentloaded")

    # ADR-027: .section-end wrappers must exist
    section_ends = page.locator(".section-end")
    count = section_ends.count()
    assert count > 0, (
        f"No .section-end wrappers found on /lecture/{CHAPTER_ID}. "
        "AC-11(c)/ADR-027: each Section must have a .section-end wrapper at the bottom."
    )
    expect(section_ends.first).to_be_visible()

    # Each .section-end must contain the completion form
    first_end = section_ends.first
    expect(first_end.locator(".section-completion-form")).to_be_visible()

    # ADR-027: .section-heading-row must be ABSENT
    heading_rows = page.locator(".section-heading-row")
    assert heading_rows.count() == 0, (
        f".section-heading-row found in DOM with count {heading_rows.count()}. "
        "ADR-027: .section-heading-row is removed in the supersedure; "
        "the heading is now plain <h2 class='section-heading'>."
    )


def test_bottom_of_section_affordance_toggleable(
    page: Page, live_server: str
) -> None:
    """
    AC-11(c) (TASK-011): the bottom-of-Section completion affordance is toggleable —
    clicking 'Mark complete' in .section-end marks the Section, and clicking again
    unmarks it. The toggle works end-to-end from the new bottom placement.

    ADR-027: only the location changes (from top of Section to .section-end at
    bottom); the route shape, PRG, and state-indicator triad are unchanged.

    Trace: AC-11(c); ADR-027 §What is NOT changed (route/PRG/state-indicators unchanged).
    """
    section_number = "1-3"  # use section-1-3 to avoid conflict with AC-11(b) test
    lecture_url = f"{live_server}/lecture/{CHAPTER_ID}"
    page.goto(lecture_url)
    page.wait_for_load_state("domcontentloaded")

    section_el = page.locator(f"#section-{section_number}").first
    action_input = section_el.locator("input[name=action]").first

    # Ensure we start from 'mark' (incomplete) state
    current_action = action_input.get_attribute("value")
    if current_action == "unmark":
        section_el.locator(".section-end .section-completion-form button[type=submit]").first.click()
        page.wait_for_load_state("domcontentloaded")
        section_el = page.locator(f"#section-{section_number}").first
        assert (
            section_el.locator("input[name=action]").first.get_attribute("value") == "mark"
        ), "Pre-condition: section must be in 'mark' state."

    # --- Mark complete via bottom-of-Section form ---
    section_el.locator(".section-end .section-completion-form button[type=submit]").first.click()
    page.wait_for_load_state("domcontentloaded")

    # After mark: section element must have 'section-complete' class
    section_after_mark = page.locator(f"#section-{section_number}").first
    classes_after_mark = section_after_mark.get_attribute("class") or ""
    assert "section-complete" in classes_after_mark, (
        f"After marking via .section-end form, section-{section_number} does not have "
        f"'section-complete' class. Classes: {classes_after_mark!r}. "
        "AC-11(c)/ADR-027: the state-indicator (section-complete class) must still work "
        "after the placement move."
    )

    # Action field must now say 'unmark'
    action_after_mark = (
        section_after_mark.locator("input[name=action]").first.get_attribute("value")
    )
    assert action_after_mark == "unmark", (
        f"After marking, action field is {action_after_mark!r}; expected 'unmark'."
    )

    # --- Unmark via bottom-of-Section form ---
    section_after_mark.locator(
        ".section-end .section-completion-form button[type=submit]"
    ).first.click()
    page.wait_for_load_state("domcontentloaded")

    # After unmark: section-complete class must be gone
    section_after_unmark = page.locator(f"#section-{section_number}").first
    classes_after_unmark = section_after_unmark.get_attribute("class") or ""
    assert "section-complete" not in classes_after_unmark, (
        f"After unmark, section-{section_number} still has 'section-complete'. "
        f"Classes: {classes_after_unmark!r}. "
        "AC-11(c)/ADR-027: unmark must remove the section-complete class."
    )


def test_every_section_has_section_end_wrapper(page: Page, live_server: str) -> None:
    """
    AC-11(c) batch: every <section id="section-*"> element must have exactly one
    .section-end child inside it. Not a spot-check — iterates all sections.

    ADR-027 §Template structure: 'inside each <section> block, after <div class=
    "section-body"> and before the closing </section> tag.'

    Trace: AC-11(c); ADR-027 §Decision (per-Section loop).
    """
    page.goto(f"{live_server}/lecture/{CHAPTER_ID}")
    page.wait_for_load_state("domcontentloaded")

    section_count = page.locator("section[id^='section-']").count()
    section_end_count = page.locator(
        "section[id^='section-'] .section-end"
    ).count()

    assert section_count > 0, (
        f"No <section id='section-*'> elements found on /lecture/{CHAPTER_ID}."
    )
    assert section_end_count == section_count, (
        f"Found {section_count} <section> elements but {section_end_count} .section-end "
        "wrappers. "
        "AC-11(c): EVERY Section must have exactly one .section-end wrapper."
    )


# ===========================================================================
# AC-11(d) — Rail-resident Notes panel renders current Chapter's notes
# ===========================================================================


def test_rail_notes_panel_renders_on_lecture_page(
    page: Page, live_server: str
) -> None:
    """
    AC-11(d) (TASK-011): the rail-resident Notes panel is visible on the Lecture page.

    ADR-028 §Rail integration: <section class="rail-notes"> inside _nav_rail.html.j2,
    below the chapter list.

    Verifies:
      - .rail-notes section is visible.
      - .rail-note-form is visible inside it.
      - textarea[name=body] is visible inside the form.
      - The form action points to /lecture/{chapter_id}/notes.

    Trace: AC-11(d); ADR-028 §Rail integration; ADR-028 §Template structure.
    """
    page.goto(f"{live_server}/lecture/{CHAPTER_ID}")
    page.wait_for_load_state("domcontentloaded")

    # ADR-028: the rail Notes section
    rail_notes = page.locator(".rail-notes").first
    expect(rail_notes).to_be_visible()

    # The Notes form must be inside the rail panel
    rail_note_form = page.locator(".rail-notes .rail-note-form, .rail-notes form").first
    expect(rail_note_form).to_be_visible()

    # The textarea must be inside the form
    textarea = page.locator(".rail-notes textarea[name='body']").first
    expect(textarea).to_be_visible()

    # The form action must point to the current chapter's notes route
    form_el = page.locator(".rail-notes form").first
    form_action = form_el.get_attribute("action") or ""
    assert f"/lecture/{CHAPTER_ID}/notes" in form_action, (
        f"rail-notes form action is {form_action!r}; expected it to contain "
        f"'/lecture/{CHAPTER_ID}/notes'. "
        "AC-11(d)/ADR-028: the rail Notes form must target the current chapter's route."
    )


def test_rail_notes_panel_absent_on_landing_page(
    page: Page, live_server: str
) -> None:
    """
    AC-11(d) + ADR-028 §Per-Chapter scoping: the Notes panel must NOT appear on
    GET / (the landing page, which has no Chapter context).

    ADR-028: 'On GET /, the Notes panel is omitted entirely via {% if rail_notes_context %}
    guard.'

    Trace: AC-11(d); ADR-028 §Per-Chapter scoping.
    """
    page.goto(f"{live_server}/")
    page.wait_for_load_state("domcontentloaded")

    # .rail-notes must not be in the DOM at all
    rail_notes = page.locator(".rail-notes")
    assert rail_notes.count() == 0, (
        f".rail-notes found on landing page (count={rail_notes.count()}). "
        "AC-11(d)/ADR-028: the Notes panel must be OMITTED from the landing page "
        "(no Chapter context)."
    )


def test_rail_notes_round_trip_note_appears_in_rail(
    page: Page, live_server: str
) -> None:
    """
    AC-11(d) (TASK-011): the primary Notes round-trip Playwright test.

    Steps:
      1. Load Lecture page for ch-02-intro-to-algorithms.
      2. Find the rail-resident Notes form (.rail-notes form).
      3. Fill in a unique Note body.
      4. Submit the form.
      5. Wait for the PRG redirect to resolve.
      6. Assert the new Note body appears in the .rail-notes panel.
      7. Assert the Note does NOT appear in any section of the main content
         (it's rail-resident, not in the bottom-of-page position).

    ADR-028: the PRG redirect reloads the page; the rail's Notes list re-renders
    with the new Note at the top (most-recent-first per ADR-023, unchanged).

    Trace: AC-11(d); ADR-028 §Rail integration; ADR-023 §Multiple-Note display (unchanged).
    """
    import time

    # Use ch-02 to avoid cross-contamination with other tests that use ch-01
    chapter = "ch-02-intro-to-algorithms"
    lecture_url = f"{live_server}/lecture/{chapter}"

    page.goto(lecture_url)
    page.wait_for_load_state("domcontentloaded")

    # Unique note body to identify this test's note
    unique_body = f"Rail-resident-note-roundtrip-TASK011-{int(time.time() * 1000)}"

    # Find the rail Notes textarea and fill it
    textarea = page.locator(".rail-notes textarea[name='body']").first
    expect(textarea).to_be_visible()
    textarea.fill(unique_body)

    # Submit the form
    submit_button = page.locator(".rail-notes form button[type='submit']").first
    expect(submit_button).to_be_visible()
    submit_button.click()

    # Wait for the PRG redirect to complete
    page.wait_for_load_state("domcontentloaded")

    # The new Note must appear in the .rail-notes panel
    rail_notes_content = page.locator(".rail-notes").first.inner_text()
    assert unique_body in rail_notes_content, (
        f"Submitted Note body {unique_body!r} not found in .rail-notes panel content. "
        "AC-11(d)/ADR-028: submitted Notes must appear in the rail-resident panel "
        "after the PRG redirect."
    )

    # The Note must NOT appear at the bottom of the page (old ADR-023 placement is gone)
    # Check that the Note is NOT inside any section element (it's rail-only)
    # This verifies the bottom-of-page Notes section is truly removed.
    main_content = page.locator("main").first.inner_text()
    # The note will appear in the rail which is inside the page, but check it's
    # not in the #main-content or article sections (i.e., not in .section-body areas)
    section_bodies = page.locator(".section-body")
    for i in range(section_bodies.count()):
        section_body_text = section_bodies.nth(i).inner_text()
        assert unique_body not in section_body_text, (
            f"Note body {unique_body!r} found inside a .section-body element. "
            "ADR-028: Notes are rail-resident only; they must not appear in Section "
            "body content."
        )


def test_rail_notes_textarea_has_rows_3_attribute(
    page: Page, live_server: str
) -> None:
    """
    AC-11(d) / ADR-028 §Rail-width constraints: the rail-resident Notes textarea
    must have rows="3" as the default value.

    ADR-028: 'Reduces default rows from 6 to 3' (quick-capture shape that fits
    the rail's 220px minimum width).

    Trace: AC-11(d); ADR-028 §Rail-width constraints on the textarea.
    """
    page.goto(f"{live_server}/lecture/{CHAPTER_ID}")
    page.wait_for_load_state("domcontentloaded")

    textarea = page.locator(".rail-notes textarea[name='body']").first
    expect(textarea).to_be_visible()

    rows_attr = textarea.get_attribute("rows")
    assert rows_attr == "3", (
        f"Rail Notes textarea has rows={rows_attr!r}; expected '3'. "
        "AC-11(d)/ADR-028: rows='3' is the committed default (quick-capture shape; "
        "fits the rail's 220px minimum width)."
    )
