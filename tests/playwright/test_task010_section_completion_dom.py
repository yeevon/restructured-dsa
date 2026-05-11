"""
TASK-010: Section completion marking — Playwright DOM/round-trip tests.

Per ADR-010 / ADR-013 split-harness:
  - HTTP-protocol pytest tests (route shape, persistence, conformance) live in
    tests/test_task010_section_completion.py.
  - Playwright tests (rendered DOM, round-trip toggle, visual state) live here.

AC-8 (TASK-010): 'at least one Playwright test exercises the round-trip:
  load Lecture → mark a Section complete → reload Lecture → assert the Section
  is shown as complete.'

ADR-025 §State indicator shape (three-layered):
  1. Button text '✓ Complete' (when complete)
  2. CSS modifier class `.section-completion-button--complete`
  3. CSS class `.section-complete` on the <section> element

These tests drive a real browser (via pytest-playwright) against the live
uvicorn server started by the `live_server` fixture in conftest.py.

NOTE: The `live_server` fixture uses the real `data/notes.db` file (or whatever
NOTES_DB_PATH the server was started with). Tests must not assume a clean
database — they assert that specific freshly-clicked affordances produce the
expected rendered state, without relying on an initially-empty database.

CANNOT TEST AC-9: 'when the human reviews fresh last-run Playwright screenshots
per ADR-010, then the completion affordance is visually present, legible, and
stylistically consistent.' This is a human visual-review gate. The screenshots
are captured by pytest-playwright (--screenshot=on or via the page fixture) and
reviewed by the human in the audit Human-gates table. The test here captures the
DOM-structural assertions only.

pytestmark registers all tests under task("TASK-010").
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.task("TASK-010")

CHAPTER_ID = "ch-01-cpp-refresher"
SECTION_NUMBER = "1-1"  # first section — boundary: first item in the Lecture


# ===========================================================================
# AC-1 (DOM) — completion affordance is rendered in the DOM for every Section
# ===========================================================================


def test_completion_affordance_present_in_dom(page: Page, live_server: str) -> None:
    """
    AC-1 (TASK-010) / ADR-025 §Template placement: the Lecture page DOM must
    contain at least one element with the `section-completion-form` class for
    each `<section>` block.

    Verifies:
      - At least one `.section-completion-form` element exists (AC-1).
      - Each form contains a `[name=action]` hidden input.
      - Each form contains a `button[type=submit]` with the completion-button class.
      - The button label is either 'Mark complete' or '✓ Complete'.

    Trace: AC-1; ADR-025 §Template placement; ADR-025 §Class names.
    """
    page.goto(f"{live_server}/lecture/{CHAPTER_ID}")
    page.wait_for_load_state("domcontentloaded")

    # At least one completion form must exist
    completion_forms = page.locator(".section-completion-form")
    expect(completion_forms.first).to_be_visible()

    # Each form must contain a button
    first_button = page.locator(".section-completion-form .section-completion-button").first
    expect(first_button).to_be_visible()

    # Button label must be either 'Mark complete' or '✓ Complete'
    button_text = first_button.inner_text().strip()
    assert "Mark complete" in button_text or "Complete" in button_text, (
        f"Completion button text is {button_text!r}; expected 'Mark complete' or "
        "'✓ Complete'. "
        "ADR-025 §State indicator: button text must indicate the available action."
    )

    # The form must contain a hidden action field
    action_inputs = page.locator(".section-completion-form input[name=action]")
    count = action_inputs.count()
    assert count >= 1, (
        f"Found {count} action inputs in completion forms; expected at least 1. "
        "ADR-025: each completion form must contain a hidden action field."
    )


def test_section_element_carries_completion_form_in_section_end_wrapper(
    page: Page, live_server: str
) -> None:
    """
    AC-1 / ADR-027 §Decision (supersedes ADR-025 §Template-placement):
    the completion form must live inside a .section-end wrapper at the BOTTOM
    of each Section block — NOT inline next to the <h2> heading.

    ADR-027: 'The completion form moves from inside <div class="section-heading-row">
    (where it currently sits next to <h2 class="section-heading">) to a new container
    at the end of each <section> block, after <div class="section-body"> and before
    the closing </section> tag.'

    Verifies (amended for ADR-027 acceptance in TASK-011):
      - `.section-heading-row` wrapper is ABSENT (removed per ADR-027).
      - `.section-end` wrapper exists (the new bottom-of-Section container).
      - `.section-end` contains the `.section-completion-form`.
      - `.section-heading` is still present (plain <h2>, no wrapper).

    Trace: AC-6 TASK-011; ADR-027 §Decision; ADR-027 §CSS class changes.
    """
    page.goto(f"{live_server}/lecture/{CHAPTER_ID}")
    page.wait_for_load_state("domcontentloaded")

    # ADR-027: .section-heading-row wrapper is REMOVED
    heading_rows = page.locator(".section-heading-row")
    assert heading_rows.count() == 0, (
        f".section-heading-row found in DOM with count {heading_rows.count()}. "
        "ADR-027: .section-heading-row is removed; the heading is now a plain <h2>."
    )

    # ADR-027: .section-end wrapper must exist (new bottom-of-Section container)
    section_end_wrappers = page.locator(".section-end")
    expect(section_end_wrappers.first).to_be_visible()

    # The .section-end wrapper must contain the completion form
    first_end = section_end_wrappers.first
    expect(first_end.locator(".section-completion-form")).to_be_visible()

    # The heading must still exist as a plain <h2 class="section-heading">
    heading = page.locator(".section-heading").first
    expect(heading).to_be_visible()


# ===========================================================================
# AC-8 — Playwright round-trip: mark → reload → assert complete
# ===========================================================================


def test_round_trip_mark_complete_and_visible_after_reload(
    page: Page, live_server: str
) -> None:
    """
    AC-8 (TASK-010): the primary Playwright round-trip test.

    Steps:
      1. Load Lecture page for ch-01-cpp-refresher.
      2. Find the completion form for section-1-1 with action=mark.
      3. Click the 'Mark complete' button.
      4. Wait for the PRG redirect to resolve (page reloads to same chapter with fragment).
      5. Assert:
         - The <section id="section-1-1"> element carries the 'section-complete' class.
         - The completion button now shows '✓ Complete' (or the --complete modifier).
         - The action field for that section is now 'unmark'.

    ADR-025 §Round-trip return point: the 303 redirect resolves to
    GET /lecture/{chapter_id}#section-{section_number}; the browser navigates to
    the same page and scrolls to the section.

    Trace: AC-8; ADR-025 §Round-trip return point; ADR-025 §State indicator shape.
    """
    lecture_url = f"{live_server}/lecture/{CHAPTER_ID}"
    page.goto(lecture_url)
    page.wait_for_load_state("domcontentloaded")

    # Find the form for section-1-1 with action=mark (incomplete state)
    # We look for a form inside the <section id="section-1-1"> element.
    # If the page was previously marked complete by another test run, we first unmark.
    section_el = page.locator(f"#section-{SECTION_NUMBER}").first

    # Determine current state by looking at the action input value in this section
    action_input = section_el.locator("input[name=action]").first
    current_action = action_input.get_attribute("value")

    if current_action == "unmark":
        # Already complete — unmark it first to get to a clean 'mark' state
        section_el.locator(".section-completion-form").first.locator(
            "button[type=submit]"
        ).first.click()
        page.wait_for_load_state("domcontentloaded")
        # Verify we're back to the incomplete state
        section_el_fresh = page.locator(f"#section-{SECTION_NUMBER}").first
        action_input_fresh = section_el_fresh.locator("input[name=action]").first
        assert action_input_fresh.get_attribute("value") == "mark", (
            "After unmark step, action should be 'mark' but is not."
        )
        section_el = page.locator(f"#section-{SECTION_NUMBER}").first

    # Now mark the section as complete by clicking the button
    mark_button = section_el.locator(
        ".section-completion-form button[type=submit]"
    ).first
    expect(mark_button).to_be_visible()
    mark_button.click()

    # Wait for the PRG redirect to complete (page reload)
    page.wait_for_load_state("domcontentloaded")

    # After reload, the section must be shown as complete
    # 1. The <section> element must carry the section-complete class
    completed_section = page.locator(f"#section-{SECTION_NUMBER}").first
    section_classes = completed_section.get_attribute("class") or ""
    assert "section-complete" in section_classes, (
        f"After marking section-{SECTION_NUMBER} complete, the <section> element's "
        f"class attribute is {section_classes!r}; expected 'section-complete'. "
        "AC-8/ADR-025: the section-complete class must be applied to the <section> "
        "element when the Section is in the completed set."
    )

    # 2. The completion button must carry the --complete modifier class
    complete_button = completed_section.locator(".section-completion-button").first
    button_class = complete_button.get_attribute("class") or ""
    assert "section-completion-button--complete" in button_class, (
        f"After marking, button class is {button_class!r}; expected "
        "'section-completion-button--complete'. "
        "AC-8/ADR-025 §State indicator: the --complete modifier class signals the "
        "completed state on the button."
    )

    # 3. The action field must now say 'unmark' (toggle-ready)
    action_input_after = completed_section.locator("input[name=action]").first
    assert action_input_after.get_attribute("value") == "unmark", (
        "After marking, the action field still says 'mark' (expected 'unmark'). "
        "AC-8/ADR-025: after marking, the form must offer 'unmark' for the toggle."
    )


def test_round_trip_mark_then_unmark(page: Page, live_server: str) -> None:
    """
    AC-8 / AC-5 Playwright round-trip: mark a Section, then unmark it.

    Verifies the toggle goes all the way in both directions in the browser.

    Steps:
      1. Navigate to Lecture page.
      2. Mark section-1-2 (chosen distinct from section-1-1 above).
      3. Assert section-1-2 shows as complete.
      4. Click the unmark button.
      5. Assert section-1-2 returns to incomplete state.

    Trace: AC-5 (toggle); AC-8 (Playwright round-trip); ADR-025 §action form field.
    """
    section_number = "1-2"  # use section-1-2 to avoid conflict with round-trip test above
    lecture_url = f"{live_server}/lecture/{CHAPTER_ID}"
    page.goto(lecture_url)
    page.wait_for_load_state("domcontentloaded")

    section_el = page.locator(f"#section-{section_number}").first
    action_input = section_el.locator("input[name=action]").first
    current_action = action_input.get_attribute("value")

    # Ensure we start from the incomplete state
    if current_action == "unmark":
        section_el.locator(".section-completion-form button[type=submit]").first.click()
        page.wait_for_load_state("domcontentloaded")
        section_el = page.locator(f"#section-{section_number}").first
        assert (
            section_el.locator("input[name=action]").first.get_attribute("value")
            == "mark"
        ), "Pre-condition: section must be in incomplete state."

    # --- Mark ---
    section_el.locator(".section-completion-form button[type=submit]").first.click()
    page.wait_for_load_state("domcontentloaded")

    section_after_mark = page.locator(f"#section-{section_number}").first
    classes_after_mark = section_after_mark.get_attribute("class") or ""
    assert "section-complete" in classes_after_mark, (
        f"After mark, section-{section_number} does not have 'section-complete' class. "
        f"Classes: {classes_after_mark!r}"
    )

    # --- Unmark ---
    section_after_mark.locator(
        ".section-completion-form button[type=submit]"
    ).first.click()
    page.wait_for_load_state("domcontentloaded")

    section_after_unmark = page.locator(f"#section-{section_number}").first
    classes_after_unmark = section_after_unmark.get_attribute("class") or ""
    assert "section-complete" not in classes_after_unmark, (
        f"After unmark, section-{section_number} still has 'section-complete' class. "
        f"Classes: {classes_after_unmark!r}. "
        "AC-5/ADR-025: unmark must remove the section-complete class."
    )

    action_after_unmark = (
        section_after_unmark.locator("input[name=action]").first.get_attribute("value")
    )
    assert action_after_unmark == "mark", (
        f"After unmark, action field is {action_after_unmark!r}; expected 'mark'. "
        "ADR-025: after unmark, the form must revert to offering 'mark'."
    )


# ===========================================================================
# DOM structural completeness — all sections on the page have forms
# ===========================================================================


def test_every_section_on_lecture_page_has_completion_form(
    page: Page, live_server: str
) -> None:
    """
    AC-1 (DOM batch): every <section> element in the Lecture page must have exactly
    one `.section-completion-form` inside it.

    This is the batch-set assertion — not a spot-check of section-1-1 only.

    Trace: AC-1 ('each Section has a visible per-Section completion affordance');
    ADR-025 §Template placement ('inside each <section id=...> block').
    """
    page.goto(f"{live_server}/lecture/{CHAPTER_ID}")
    page.wait_for_load_state("domcontentloaded")

    # Count sections and forms
    section_count = page.locator("section[id^='section-']").count()
    form_count = page.locator("section[id^='section-'] .section-completion-form").count()

    assert section_count > 0, (
        f"No <section id='section-*'> elements found on /lecture/{CHAPTER_ID}. "
        "The lecture page must have at least one Section."
    )
    assert form_count == section_count, (
        f"Found {section_count} <section> elements but {form_count} completion forms. "
        "AC-1: EVERY Section must have exactly one completion form — not a spot-check."
    )


def test_completion_affordance_does_not_hide_designation_badge(
    page: Page, live_server: str
) -> None:
    """
    ADR-025 §Conformance MC-3: the completion affordance must not displace or hide
    the existing designation badge.

    Manifest §6: 'Mandatory and Optional honored everywhere.'
    ADR-025: 'the completion affordance does not obscure the existing designation badge.'

    Verifies: both `.designation-mandatory` (or `.designation-optional`) and
    `.section-completion-form` are visible on the page simultaneously.

    Trace: ADR-025 §Conformance MC-3; Manifest §6 'Mandatory/Optional honored everywhere'.
    """
    page.goto(f"{live_server}/lecture/{CHAPTER_ID}")
    page.wait_for_load_state("domcontentloaded")

    # ch-01 is Mandatory — its designation badge must still be present
    designation_el = page.locator(
        ".designation-mandatory, .designation-optional, [class*='designation']"
    ).first
    expect(designation_el).to_be_visible()

    # The completion form must also be present and visible
    completion_form_el = page.locator(".section-completion-form").first
    expect(completion_form_el).to_be_visible()
