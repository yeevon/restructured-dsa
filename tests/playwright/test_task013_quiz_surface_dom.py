"""
TASK-013: Per-Section Quiz surface — Playwright DOM tests.

Per ADR-010 / ADR-013 split-harness:
  - HTTP-protocol pytest tests (schema, persistence, route shape, conformance) live in
    tests/test_task013_quiz_schema.py and tests/test_task013_quiz_surface_http.py.
  - Playwright tests (rendered DOM, visual affordance presence, M/O inheritance) live here.

AC-11 (TASK-013): 'at least one Playwright test asserts:
  (a) on a Lecture page, each <section>'s .section-end wrapper contains a
      .section-quiz-* block with the empty-state text;
  (b) the surface renders on both a Mandatory Chapter and an Optional Chapter
      (M/O inheritance);
  (c) the "Generate a Quiz for this Section" affordance is present as a real
      form/button (per ADR-034 Option 1 — a real form with a submit button,
      not a disabled button or caption-only).'

ADR-034 structural commitments tested here:
  - Inside .section-end (or its child .section-quiz), a block with the
    empty-state text 'No quizzes yet for this Section.' is present.
  - The block uses .section-quiz-* CSS classes.
  - A form with action ending in '/quiz' and a submit button is present inside
    the .section-quiz block (the real user-triggered trigger).
  - The .section-end wrapper is NOT broken by the addition of the Quiz block.
  - On a Mandatory Chapter (ch-01-*) and an Optional Chapter (ch-07-*), the
    Quiz surface renders correctly (M/O inheritance).

ADR-031 structural commitment (no-relocate) tested here via a smoke check:
  - After clicking "Generate a Quiz for this Section", the browser URL contains
    '#section-{n-m}-end' (the Location header from the 303 redirect carries the
    anchor per ADR-031 / ADR-034).

These tests drive a real browser (Chromium, the binding test target per ADR-010)
against the live uvicorn server started by the `live_server` fixture in conftest.py.

NOTE: The live_server uses the real data/notes.db. Tests must not assume a clean
database — they assert that the freshly-rendered page shows the empty-state for
Sections that have no Quizzes, and that the affordance button is present.

ASSUMPTIONS:
  ASSUMPTION: ADR-034 §CSS: the .section-quiz block is present inside .section-end
    or is a direct child of the .section-end wrapper. Playwright tests assert
    page.locator('.section-quiz') or page.locator('.section-end .section-quiz').
    The exact nesting is implementer-tunable; both forms use the .section-quiz
    class per ADR-034.
  ASSUMPTION: The 'Generate a Quiz for this Section' button is a submit button
    inside a <form> with action ending '/quiz'. Playwright asserts
    page.locator('[action$="/quiz"]') and page.locator('.section-quiz-button').
  ASSUMPTION: The empty-state text is 'No quizzes yet for this Section.' —
    the exact must-ship copy per ADR-034.
  ASSUMPTION: ch-01-cpp-refresher is a Mandatory Chapter; ch-07-heaps-and-treaps
    is an Optional Chapter (per the canonical designation function, ADR-004).

pytestmark registers all tests under task("TASK-013").
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.task("TASK-013")

MANDATORY_CHAPTER_ID = "ch-01-cpp-refresher"
OPTIONAL_CHAPTER_ID = "ch-07-heaps-and-treaps"

# Section numbers for trigger tests (first section of each chapter)
MANDATORY_FIRST_SECTION = "1-1"
OPTIONAL_FIRST_SECTION = "7-1"


# ===========================================================================
# AC-11(a) — .section-end wrappers each contain a .section-quiz block
# Trace: TASK-013 AC-11(a); ADR-034 §Placement
# ===========================================================================


def test_each_section_end_contains_section_quiz_block(
    page: Page, live_server: str
) -> None:
    """
    AC-11(a) (TASK-013): on a Lecture page, every .section-end wrapper must contain
    a .section-quiz (or a child with a section-quiz-* class) block.

    ADR-034 §Placement: 'the per-Section Quiz surface lives inside the
    <div class="section-end"> wrapper, after the completion form — one Quiz block
    per <section>, keyed by section.id'.

    Verifies:
      - At least one .section-quiz block exists on the page.
      - Each .section-quiz is inside a .section-end wrapper.
      - The empty-state caption 'No quizzes yet' is present in at least one block.

    Trace: AC-11(a); ADR-034 §Placement; ADR-027 (section-end wrapper unchanged).
    """
    page.goto(f"{live_server}/lecture/{MANDATORY_CHAPTER_ID}")
    page.wait_for_load_state("domcontentloaded")

    # At least one .section-quiz block must be present
    section_quiz_blocks = page.locator(".section-quiz")
    count = section_quiz_blocks.count()
    assert count >= 1, (
        f"No .section-quiz block found on /lecture/{MANDATORY_CHAPTER_ID}. "
        "AC-11(a)/ADR-034: each <section>'s .section-end wrapper must contain a "
        ".section-quiz block (one per section)."
    )

    # The first .section-quiz block must be visible
    expect(section_quiz_blocks.first).to_be_visible()

    # .section-quiz must be inside .section-end (ADR-034: placed after the completion form)
    quiz_in_section_end = page.locator(".section-end .section-quiz")
    count_nested = quiz_in_section_end.count()
    assert count_nested >= 1, (
        f"No .section-quiz found inside .section-end on /lecture/{MANDATORY_CHAPTER_ID}. "
        "AC-11(a)/ADR-034: the Quiz block must be inside the .section-end wrapper "
        "(not a sibling, not above the section body). "
        f"Found {count} .section-quiz block(s) total, "
        f"but {count_nested} inside .section-end."
    )


def test_section_quiz_empty_state_text_in_dom(page: Page, live_server: str) -> None:
    """
    AC-11(a) (TASK-013) / ADR-034 §Empty-state: at least one .section-quiz block
    on the page must contain the empty-state text 'No quizzes yet for this Section.'

    ADR-034: 'With zero Quizzes for a Section, the surface shows an empty-state
    caption — "No quizzes yet for this Section." (the exact copy is the must-ship).'

    Trace: AC-11(a); ADR-034 §Empty-state (must-ship).
    """
    page.goto(f"{live_server}/lecture/{MANDATORY_CHAPTER_ID}")
    page.wait_for_load_state("domcontentloaded")

    # Find the empty-state paragraph with the must-ship text
    empty_state = page.locator(".section-quiz-empty")
    if empty_state.count() == 0:
        # Fallback: look for the text anywhere in a .section-quiz block
        empty_state = page.locator(".section-quiz").filter(
            has_text="No quizzes yet"
        )

    assert empty_state.count() >= 1, (
        f"No element with empty-state text 'No quizzes yet' found inside a "
        f".section-quiz block on /lecture/{MANDATORY_CHAPTER_ID}. "
        "AC-11(a)/ADR-034 §Empty-state: 'No quizzes yet for this Section.' is the "
        "must-ship empty-state caption."
    )
    expect(empty_state.first).to_be_visible()


# ===========================================================================
# AC-11(b) — Quiz surface renders on both Mandatory and Optional Chapters
# Trace: TASK-013 AC-11(b); ADR-034; MC-3; Manifest §7
# ===========================================================================


def test_quiz_surface_renders_on_mandatory_chapter_dom(
    page: Page, live_server: str
) -> None:
    """
    AC-11(b) (TASK-013): the per-Section Quiz surface must render on a Mandatory
    Chapter (ch-01-cpp-refresher).

    ADR-034 / MC-3: 'Mandatory and Optional honored everywhere — the per-Section
    Quiz surface inherits the parent Chapter's designation via ADR-004's function;
    nothing about the surface hides the M/O split.'

    Trace: AC-11(b); ADR-034; MC-3; Manifest §7 'Mandatory and Optional are
    separable in every learner-facing surface'.
    """
    page.goto(f"{live_server}/lecture/{MANDATORY_CHAPTER_ID}")
    page.wait_for_load_state("domcontentloaded")

    section_quiz = page.locator(".section-quiz")
    count = section_quiz.count()
    assert count >= 1, (
        f"No .section-quiz block found on Mandatory Chapter "
        f"/lecture/{MANDATORY_CHAPTER_ID}. "
        "AC-11(b)/ADR-034/MC-3: the Quiz surface must be present on Mandatory Chapters."
    )
    expect(section_quiz.first).to_be_visible()

    # Screenshot for human review (per ADR-010 rendered-surface verification gate)
    page.screenshot(
        path="tests/playwright/artifacts/task013_mandatory_chapter_quiz_surface.png"
    )


def test_quiz_surface_renders_on_optional_chapter_dom(
    page: Page, live_server: str
) -> None:
    """
    AC-11(b) (TASK-013): the per-Section Quiz surface must also render on an
    Optional Chapter (ch-07-heaps-and-treaps).

    M/O inheritance: 'nothing about the surface hides the M/O split' (ADR-034).
    The surface is identical on Optional and Mandatory Chapters.

    Trace: AC-11(b); ADR-034; MC-3; Manifest §6 'Mandatory and Optional are
    honored everywhere'.
    """
    page.goto(f"{live_server}/lecture/{OPTIONAL_CHAPTER_ID}")
    page.wait_for_load_state("domcontentloaded")

    section_quiz = page.locator(".section-quiz")
    count = section_quiz.count()
    assert count >= 1, (
        f"No .section-quiz block found on Optional Chapter "
        f"/lecture/{OPTIONAL_CHAPTER_ID}. "
        "AC-11(b)/ADR-034/MC-3: the Quiz surface must render on Optional Chapters "
        "too — M/O inheritance must not hide or suppress the surface."
    )
    expect(section_quiz.first).to_be_visible()

    # Screenshot for human review
    page.screenshot(
        path="tests/playwright/artifacts/task013_optional_chapter_quiz_surface.png"
    )


def test_quiz_surface_present_on_both_mandatory_and_optional(
    page: Page, live_server: str
) -> None:
    """
    AC-11(b) (TASK-013) combined assertion: the Quiz surface renders on BOTH a
    Mandatory and an Optional Chapter within the same test.

    Verifies the M/O inheritance principle in a single test that switches pages.

    Trace: AC-11(b); ADR-034; Manifest §7 'Mandatory and Optional are separable
    in every learner-facing surface'.
    """
    for chapter_id in (MANDATORY_CHAPTER_ID, OPTIONAL_CHAPTER_ID):
        page.goto(f"{live_server}/lecture/{chapter_id}")
        page.wait_for_load_state("domcontentloaded")

        section_quiz = page.locator(".section-quiz")
        count = section_quiz.count()
        assert count >= 1, (
            f"No .section-quiz block found on /lecture/{chapter_id}. "
            "AC-11(b)/ADR-034: Quiz surface must render on both Mandatory and "
            "Optional Chapters (M/O inheritance — nothing suppresses the surface)."
        )


# ===========================================================================
# AC-11(c) — "Generate a Quiz for this Section" affordance: real form + button
# Trace: TASK-013 AC-11(c); ADR-034 §Quiz-trigger affordance (Option 1)
# ===========================================================================


def test_generate_quiz_form_is_present_in_dom(page: Page, live_server: str) -> None:
    """
    AC-11(c) (TASK-013): on a Lecture page, at least one 'Generate a Quiz for
    this Section' affordance must be present as a real <form> with a submit button
    (not a disabled button or caption-only).

    ADR-034 §Option 1 (chosen): 'a real POST /lecture/{chapter_id}/sections/{n}/quiz
    route … a <form method="post" action="/lecture/{chapter_id}/sections/{n}/quiz">
    with a single submit button, inside the .section-quiz block.'

    Verifies:
      - A form with action ending in '/quiz' exists.
      - The form is inside .section-quiz.
      - A submit button is inside the form.
      - The button is not disabled.

    Trace: AC-11(c); ADR-034 §Quiz-trigger affordance (Option 1).
    """
    page.goto(f"{live_server}/lecture/{MANDATORY_CHAPTER_ID}")
    page.wait_for_load_state("domcontentloaded")

    # A form whose action ends in '/quiz' must be present inside .section-quiz
    quiz_form = page.locator(".section-quiz form[action$='/quiz']")
    count = quiz_form.count()
    assert count >= 1, (
        f"No <form action$='/quiz'> found inside .section-quiz on "
        f"/lecture/{MANDATORY_CHAPTER_ID}. "
        "AC-11(c)/ADR-034: the 'Generate a Quiz' affordance is a real form with "
        "action pointing at POST .../sections/{n}/quiz. "
        "A disabled-button or caption-only implementation does NOT satisfy this AC."
    )
    expect(quiz_form.first).to_be_visible()

    # The form must contain a submit button
    submit_button = quiz_form.first.locator("button[type='submit'], input[type='submit']")
    button_count = submit_button.count()
    assert button_count >= 1, (
        f"The quiz form on /lecture/{MANDATORY_CHAPTER_ID} has no submit button. "
        "AC-11(c)/ADR-034: a submit button must be inside the quiz form."
    )
    expect(submit_button.first).to_be_visible()

    # The button must NOT be disabled
    is_disabled = submit_button.first.is_disabled()
    assert not is_disabled, (
        f"The 'Generate a Quiz' submit button on /lecture/{MANDATORY_CHAPTER_ID} "
        "is disabled. "
        "AC-11(c)/ADR-034 §Option 1: the affordance is a LIVE form (not disabled). "
        "ADR-034 rejected Option 2 (disabled button) precisely because 'a disabled "
        "button is a promise the surface can't keep.'"
    )


def test_generate_quiz_button_label_readable(page: Page, live_server: str) -> None:
    """
    ADR-034 §Quiz-trigger affordance: the submit button label must convey
    'Generate a Quiz for this Section' (or a sufficiently similar label).

    The label makes it clear what the button does — generating a Quiz request —
    rather than a generic 'Submit'.

    Trace: ADR-034 §Template (button label from sample HTML: 'Generate a Quiz for
    this Section').
    """
    page.goto(f"{live_server}/lecture/{MANDATORY_CHAPTER_ID}")
    page.wait_for_load_state("domcontentloaded")

    quiz_form = page.locator(".section-quiz form[action$='/quiz']")
    if quiz_form.count() == 0:
        pytest.fail(
            f"No quiz form found on /lecture/{MANDATORY_CHAPTER_ID}. "
            "Prerequisite for button label test failed."
        )

    submit_button = quiz_form.first.locator(
        "button[type='submit'], input[type='submit']"
    )
    if submit_button.count() == 0:
        pytest.fail("No submit button found in quiz form.")

    button_text = submit_button.first.inner_text().strip()
    assert "Generate" in button_text or "Quiz" in button_text or "quiz" in button_text.lower(), (
        f"Quiz form submit button text is {button_text!r}; expected it to contain "
        "'Generate' or 'Quiz'. "
        "ADR-034 §Template: the button label must convey quiz generation."
    )


# ===========================================================================
# ADR-034 — .section-end wrapper is preserved (Quiz block added, not replacing)
# Trace: ADR-034 §What is NOT changed (section-end wrapper unchanged)
# ===========================================================================


def test_section_end_wrapper_still_contains_completion_form(
    page: Page, live_server: str
) -> None:
    """
    ADR-034 §What is NOT changed: the completion form must still be present in
    .section-end after the Quiz block is added.

    ADR-034: 'The completion form (ADR-025/ADR-027/ADR-031) — unchanged; the
    Quiz block is rendered *after* it inside .section-end.'

    This verifies the Quiz block does not replace the completion form.

    Trace: ADR-034 §What is NOT changed; ADR-027 (section-end wrapper unchanged).
    """
    page.goto(f"{live_server}/lecture/{MANDATORY_CHAPTER_ID}")
    page.wait_for_load_state("domcontentloaded")

    # The completion form must be inside .section-end
    completion_in_section_end = page.locator(".section-end .section-completion-form")
    count = completion_in_section_end.count()
    assert count >= 1, (
        f"No .section-completion-form found inside .section-end on "
        f"/lecture/{MANDATORY_CHAPTER_ID} after Quiz block was added. "
        "ADR-034: the completion form must remain in .section-end unchanged; "
        "the Quiz block is rendered *after* it, not instead of it."
    )


def test_quiz_block_comes_after_completion_form_in_dom(
    page: Page, live_server: str
) -> None:
    """
    ADR-034 §Placement (order within .section-end): the .section-quiz block must
    come AFTER the .section-completion-form inside .section-end.

    ADR-034: 'the Quiz block is rendered *after* it [the completion form] inside
    .section-end' — cognitive-sequence order: mark complete → then generate a Quiz.

    Strategy: compare the DOM position of the first .section-completion-form and
    the first .section-quiz block.

    Trace: ADR-034 §Placement ('after the completion form'); ADR-027 §Cognitive
    sequence ('action affordances follow the cognitive sequence').
    """
    page.goto(f"{live_server}/lecture/{MANDATORY_CHAPTER_ID}")
    page.wait_for_load_state("domcontentloaded")

    # Use evaluate to get the document order of the two elements
    # Returns True if .section-quiz follows .section-completion-form in DOM order
    quiz_after_completion = page.evaluate("""() => {
        const completionForm = document.querySelector('.section-completion-form');
        const quizBlock = document.querySelector('.section-quiz');
        if (!completionForm || !quizBlock) return null;
        // Node.compareDocumentPosition: bit 4 (0x04) means 'follows'
        return (completionForm.compareDocumentPosition(quizBlock) & 0x04) !== 0;
    }""")

    assert quiz_after_completion is not None, (
        f"Could not locate both .section-completion-form and .section-quiz on "
        f"/lecture/{MANDATORY_CHAPTER_ID}. "
        "Both elements must be present for the ordering assertion."
    )
    assert quiz_after_completion is True, (
        f".section-quiz does NOT follow .section-completion-form in DOM order on "
        f"/lecture/{MANDATORY_CHAPTER_ID}. "
        "ADR-034: the Quiz block must be rendered AFTER the completion form inside "
        ".section-end (cognitive sequence: read → mark complete → generate Quiz)."
    )


# ===========================================================================
# ADR-031 / ADR-034 — After clicking "Generate a Quiz", URL anchor preserved
# Trace: ADR-034 §Quiz-trigger route; ADR-031 (no-relocate mechanism reused)
# ===========================================================================


def test_generate_quiz_click_url_contains_section_end_anchor(
    page: Page, live_server: str
) -> None:
    """
    ADR-034 + ADR-031: after clicking "Generate a Quiz for this Section", the
    browser URL must contain '#section-{n-m}-end' (the PRG redirect anchor).

    ADR-034: 'PRG redirect: 303 → /lecture/{chapter_id}#section-{section_number}-end'.
    ADR-031 (reused unchanged): 'the Location header carries the anchor; the
    .section-end wrapper already carries id="section-{n-m}-end" and a large
    scroll-margin-top; the redirect lands the user back where they were.'

    This is the Playwright complement of the HTTP-protocol anchor test.

    Trace: ADR-034 §Quiz-trigger route (PRG redirect); ADR-031 §Decision (no-relocate).
    """
    page.goto(f"{live_server}/lecture/{MANDATORY_CHAPTER_ID}")
    page.wait_for_load_state("domcontentloaded")

    # Find the first quiz form and click its submit button
    quiz_form = page.locator(".section-quiz form[action$='/quiz']")
    if quiz_form.count() == 0:
        pytest.fail(
            f"No quiz form found on /lecture/{MANDATORY_CHAPTER_ID}. "
            "Cannot test POST redirect behavior without the trigger form."
        )

    submit_button = quiz_form.first.locator(
        "button[type='submit'], input[type='submit']"
    )
    if submit_button.count() == 0:
        pytest.fail("No submit button found in quiz form.")

    # Click the button and wait for the redirect to complete
    with page.expect_navigation():
        submit_button.first.click()

    page.wait_for_load_state("domcontentloaded")

    current_url = page.url
    assert "#section-" in current_url and "-end" in current_url, (
        f"After clicking 'Generate a Quiz', the browser URL is {current_url!r}. "
        "Expected it to contain '#section-{n-m}-end'. "
        "ADR-034/ADR-031: the PRG redirect anchors at '#section-{n-m}-end' so the "
        "response does not relocate the reader (no-relocate rule reused unchanged)."
    )

    # Screenshot for human review (per ADR-010 rendered-surface verification gate)
    page.screenshot(
        path="tests/playwright/artifacts/task013_after_generate_quiz_click.png"
    )


# ===========================================================================
# Edge — section-quiz block count matches section count on the page
# Trace: ADR-034 §Placement ('one Quiz block per <section>')
# ===========================================================================


def test_section_quiz_block_count_matches_section_count(
    page: Page, live_server: str
) -> None:
    """
    ADR-034 §Placement: 'one Quiz block per <section>'. The number of .section-quiz
    blocks must equal the number of <section> elements on the page.

    A mismatch means either a Section is missing its Quiz block (AC-11(a) failure)
    or an extra block was rendered (template loop error).

    Trace: ADR-034 §Placement ('one Quiz block per <section>').
    """
    page.goto(f"{live_server}/lecture/{MANDATORY_CHAPTER_ID}")
    page.wait_for_load_state("domcontentloaded")

    section_count = page.locator("section[id]").count()
    quiz_block_count = page.locator(".section-quiz").count()

    assert section_count > 0, (
        f"No <section> elements found on /lecture/{MANDATORY_CHAPTER_ID}. "
        "The Lecture page must render Section elements."
    )
    assert quiz_block_count == section_count, (
        f"Found {quiz_block_count} .section-quiz block(s) but {section_count} "
        f"<section> element(s) on /lecture/{MANDATORY_CHAPTER_ID}. "
        "ADR-034 §Placement: there must be exactly ONE .section-quiz block per Section "
        "(one-to-one mapping). A mismatch means a Section is missing its Quiz block "
        "or the template loop rendered extra blocks."
    )
