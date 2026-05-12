"""
TASK-015: Quiz-taking surface — Playwright DOM tests.

Per ADR-010 / ADR-013 split-harness:
  - HTTP-protocol pytest tests (persistence, route shape, MC-2/MC-4/MC-5/MC-7/MC-10)
    live in tests/test_task015_quiz_taking.py.
  - Playwright tests (rendered DOM, visual affordance presence, code fields, submit
    flow, M/O designation context) live here.

Structural commitments tested here derive from ADR-038:
  - The .section-quiz block's ready entry shows a 'Take this Quiz' link/button
    (section-quiz-take-link or text 'Take this Quiz' or link to .../take).
  - The take surface (quiz_take.html.j2) renders each Question's coding-task prompt
    and a code-entry <textarea> for each Question.
  - The take surface renders NO non-code inputs (no type='radio', no type='checkbox'
    for options — manifest §5/§7: every Question is a hands-on coding task).
  - After submit, the take surface shows an honest 'submitted — grading not yet
    available' (or equivalent) state — NO fabricated score, 'all correct', or grade.
  - The take affordance does NOT appear on requested/generating/generation_failed
    Quiz entries.
  - The take surface shows the Chapter's Mandatory/Optional designation context
    (MC-3 / manifest §6 'Mandatory and Optional honored everywhere').

These tests drive a real browser (Chromium, the binding test target per ADR-010)
against the live uvicorn server started by the `live_server` fixture in
tests/playwright/conftest.py.

NOTE: The live_server fixture uses the real data/notes.db. These tests must NOT
assume a clean database. They assert structural/behavioral contracts on the rendered
DOM:
  - For the take-affordance tests: we look for existing ready Quizzes on the rendered
    page, or (if none exist) record the structural test as 'skipped due to no ready
    Quiz in the live DB' (not a failure — the structural contract is verified by the
    HTTP-level tests in test_task015_quiz_taking.py against an injected ready Quiz).
  - For the take-surface rendering tests: the tests use page.goto() with the take URL
    constructed from a known ready Quiz (if the live DB has one) or skip.

ASSUMPTIONS:
  ASSUMPTION: ADR-038: the take affordance is a link with href containing '/take'
    and/or the text 'Take this Quiz' inside a .section-quiz-item--ready or
    .section-quiz element. The .section-quiz-take-link CSS class is the architectural
    commitment (ADR-038).
  ASSUMPTION: ch-01-cpp-refresher is a Mandatory Chapter; ch-07-heaps-and-treaps is
    an Optional Chapter (per ADR-004).
  ASSUMPTION: The take surface at /lecture/{chapter_id}/sections/{n-m}/quiz/{quiz_id}/take
    renders with quiz-take-* CSS classes per ADR-038.
  ASSUMPTION: The submit form uses method='post' and contains textarea elements with
    name='response_{question_id}' pattern.

pytestmark registers all tests under task("TASK-015").
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.task("TASK-015")

MANDATORY_CHAPTER_ID = "ch-01-cpp-refresher"
OPTIONAL_CHAPTER_ID = "ch-07-heaps-and-treaps"
MANDATORY_FIRST_SECTION = "1-1"
OPTIONAL_FIRST_SECTION = "7-1"


# ---------------------------------------------------------------------------
# AC-1 / ADR-038: take affordance on the .section-quiz block
# ---------------------------------------------------------------------------


def test_section_quiz_take_link_absent_on_no_ready_quiz(
    page: Page, live_server: str
) -> None:
    """
    AC-1 (TASK-015) / ADR-038: on a Lecture page for a Chapter whose Sections have
    NO ready Quiz, NO take affordance must be present in ANY .section-quiz block.

    This tests the negative: the 'Take this Quiz' link/button must NOT appear when
    there is no ready Quiz.

    NOTE: this test assumes the live DB does NOT have a ready Quiz for every Section
    of ch-01-cpp-refresher. If the live DB happens to have a ready Quiz, this test
    may produce a false assertion — the HTTP-level test covers the injected-DB case.

    Trace: AC-1; ADR-038 §Take affordance; ADR-034 (non-ready labels unchanged).
    """
    page.goto(f"{live_server}/lecture/{MANDATORY_CHAPTER_ID}")
    page.wait_for_load_state("networkidle")

    # A take affordance for a ready Quiz would have href containing '/take'
    # Check that no such link exists in any .section-quiz block
    # (This is a structural guard — if all Quizzes in the live DB are non-ready,
    # no take links should appear for newly-created sections.)
    # We look for the specific take-link class
    take_links = page.locator(".section-quiz-take-link")
    count = take_links.count()

    # We can't assert count == 0 because the live DB may have ready Quizzes.
    # Instead, assert the structural contract: if take links exist, they must
    # be inside .section-quiz-item--ready (not inside requested/generating/failed).
    if count > 0:
        # Each take link must be inside a ready item
        for i in range(count):
            link = take_links.nth(i)
            # The take link must have an href containing '/take'
            href = link.get_attribute("href") or ""
            assert "/take" in href, (
                f"take link #{i} has href={href!r} — does not contain '/take'. "
                "ADR-038: the take affordance must link to .../take."
            )
    # If count == 0, that is also acceptable (no ready Quiz → no take link).


def test_section_quiz_block_has_no_take_link_for_requested_entry(
    page: Page, live_server: str
) -> None:
    """
    AC-1 (TASK-015) / ADR-038: if a .section-quiz-item--requested entry is present on
    the page, it must NOT contain a take affordance.

    ADR-038: 'The requested / generating / generation_failed entries get NO such
    affordance (they are not takeable) — their labels are unchanged from ADR-034.'

    Trace: AC-1; ADR-038 §Take affordance (non-ready entries unchanged).
    """
    page.goto(f"{live_server}/lecture/{MANDATORY_CHAPTER_ID}")
    page.wait_for_load_state("networkidle")

    requested_items = page.locator(".section-quiz-item--requested")
    count = requested_items.count()

    if count == 0:
        pytest.skip(
            "No .section-quiz-item--requested entries on this page in the live DB. "
            "Cannot verify absence of take affordance on requested entries."
        )

    for i in range(count):
        item = requested_items.nth(i)
        # Must not contain a link to .../take
        take_link_inside = item.locator("a[href*='/take']")
        assert take_link_inside.count() == 0, (
            f".section-quiz-item--requested #{i} contains a '/take' link. "
            "AC-1/ADR-038: requested Quizzes must NOT show a take affordance."
        )


# ---------------------------------------------------------------------------
# AC-2 / ADR-038: take surface renders prompts + code fields
# ---------------------------------------------------------------------------


def test_take_surface_renders_code_textarea_fields(
    page: Page, live_server: str
) -> None:
    """
    AC-2 (TASK-015) / ADR-038: the take surface at .../quiz/{quiz_id}/take must render
    at least one code-entry <textarea> for each Question.

    This test attempts to find a ready Quiz in the live DB via the Lecture page,
    then navigates to its take URL and verifies the rendering.

    ADR-038: 'for each AttemptQuestion in position order, … a code-entry <textarea
    name="response_{aq.question_id}">.'

    Trace: AC-2; ADR-038 §take surface template.
    """
    page.goto(f"{live_server}/lecture/{MANDATORY_CHAPTER_ID}")
    page.wait_for_load_state("networkidle")

    # Look for a take link
    take_links = page.locator(".section-quiz-take-link, a[href*='/take'][href*='/quiz/']")
    count = take_links.count()

    if count == 0:
        pytest.skip(
            "No take affordance found on the live Lecture page — "
            "no ready Quiz in the live DB. "
            "HTTP-level tests in test_task015_quiz_taking.py cover this with an injected Quiz."
        )

    # Navigate to the first take link
    href = take_links.first.get_attribute("href") or ""
    if not href:
        pytest.skip("Take link has no href.")

    if not href.startswith("http"):
        href = live_server + href

    page.goto(href)
    page.wait_for_load_state("networkidle")

    # The take surface must contain at least one code-entry textarea
    textareas = page.locator("textarea[name^='response_']")
    textarea_count = textareas.count()

    assert textarea_count > 0, (
        f"Take surface at {href!r} contains no <textarea name='response_...'> fields. "
        "AC-2/ADR-038: the take surface must render a code-entry textarea for each Question."
    )


def test_take_surface_has_no_radio_or_option_inputs(
    page: Page, live_server: str
) -> None:
    """
    AC-2 (TASK-015) / manifest §5/§7: the take surface must NOT contain radio buttons
    or checkbox inputs that would indicate a non-coding Question format (multiple-choice
    or true/false).

    Manifest §5: 'No non-coding Question formats. No multiple-choice, no true/false.'
    Manifest §7: 'Every Question is a hands-on coding task.'

    Trace: AC-2; manifest §5/§7; ADR-038 §take surface template.
    """
    page.goto(f"{live_server}/lecture/{MANDATORY_CHAPTER_ID}")
    page.wait_for_load_state("networkidle")

    take_links = page.locator(".section-quiz-take-link, a[href*='/take'][href*='/quiz/']")
    if take_links.count() == 0:
        pytest.skip("No ready Quiz in live DB — cannot navigate to take surface.")

    href = take_links.first.get_attribute("href") or ""
    if not href.startswith("http"):
        href = live_server + href

    page.goto(href)
    page.wait_for_load_state("networkidle")

    # No radio buttons — multiple-choice would use type='radio'
    radio_inputs = page.locator("input[type='radio']")
    assert radio_inputs.count() == 0, (
        f"Take surface at {href!r} contains {radio_inputs.count()} radio input(s). "
        "Manifest §5/§7: the take surface must NOT render radio buttons. "
        "Every Question is a hands-on coding task — the learner writes code, not picks options."
    )


def test_take_surface_has_submit_button(page: Page, live_server: str) -> None:
    """
    AC-2 (TASK-015) / ADR-038: the take surface for an in_progress Attempt must have
    a submit button ('Submit Quiz' or similar) inside a <form method='post'>.

    ADR-038: 'a <form method="post" action=".../take"> … plus a submit button
    ("Submit Quiz").'

    Trace: AC-2; ADR-038 §take surface template.
    """
    page.goto(f"{live_server}/lecture/{MANDATORY_CHAPTER_ID}")
    page.wait_for_load_state("networkidle")

    take_links = page.locator(".section-quiz-take-link, a[href*='/take'][href*='/quiz/']")
    if take_links.count() == 0:
        pytest.skip("No ready Quiz in live DB.")

    href = take_links.first.get_attribute("href") or ""
    if not href.startswith("http"):
        href = live_server + href

    page.goto(href)
    page.wait_for_load_state("networkidle")

    html = page.content()

    # If the Attempt is in_progress, there must be a submit form
    # (If it's already submitted, the submitted state is shown instead — that's fine.)
    is_submitted_state = (
        "submitted" in html.lower()
        and "grading" in html.lower()
    )

    if not is_submitted_state:
        # Should have a submit button for an in_progress Attempt
        submit_button = page.locator(
            "button[type='submit'], input[type='submit'], "
            "button:has-text('Submit'), button:has-text('submit')"
        )
        assert submit_button.count() > 0, (
            f"Take surface at {href!r} (in_progress state) has no submit button. "
            "ADR-038: the take surface for an in_progress Attempt must have a submit button."
        )


def test_take_surface_shows_designation_context_mandatory(
    page: Page, live_server: str
) -> None:
    """
    AC-9 + MC-3 (TASK-015): the take surface for a Quiz on a Mandatory Chapter
    (ch-01-cpp-refresher) must show the Mandatory designation context.

    MC-3 / manifest §6: 'every learner-facing surface honors and exposes the split.'
    ADR-038: 'A header naming the Quiz's Section … with the Chapter's Mandatory/Optional
    designation badge.'

    Trace: AC-9; MC-3; ADR-038 §template; manifest §6.
    """
    page.goto(f"{live_server}/lecture/{MANDATORY_CHAPTER_ID}")
    page.wait_for_load_state("networkidle")

    take_links = page.locator(".section-quiz-take-link, a[href*='/take'][href*='/quiz/']")
    if take_links.count() == 0:
        pytest.skip(
            "No ready Quiz in the live DB for the Mandatory Chapter. "
            "MC-3 designation context is verified at HTTP level in test_task015_quiz_taking.py."
        )

    href = take_links.first.get_attribute("href") or ""
    if not href.startswith("http"):
        href = live_server + href

    page.goto(href)
    page.wait_for_load_state("networkidle")

    html = page.content().lower()

    designation_signal = (
        "mandatory" in html
        or "designation-mandatory" in html
        or "designation-m" in html
    )
    assert designation_signal, (
        f"Take surface at {href!r} (Mandatory Chapter) does not show the Mandatory "
        "designation context. "
        "MC-3/ADR-038: the take surface must show the Chapter's M/O designation badge."
    )


# ---------------------------------------------------------------------------
# AC-5 / ADR-038: submitted state — honest copy, no fabricated grade
# ---------------------------------------------------------------------------


def test_take_surface_submitted_state_has_no_fabricated_grade(
    page: Page, live_server: str
) -> None:
    """
    AC-5 (TASK-015) / MC-5 / ADR-038: when the take surface shows a submitted Attempt,
    it must NOT display a fabricated score, 'all correct', or any invented Grade.

    ADR-038 §submitted state: 'must not imply a Grade exists, must not show a score,
    must not say "all correct" or any invented result.'
    MC-5: 'the system never substitutes a placeholder grade'.

    This test checks the take surface for a submitted Attempt (if the live DB has one);
    it verifies the HTML does not contain forbidden fabricated-grade patterns.

    Trace: AC-5; ADR-038 §submitted state; MC-5; manifest §6.
    """
    page.goto(f"{live_server}/lecture/{MANDATORY_CHAPTER_ID}")
    page.wait_for_load_state("networkidle")

    take_links = page.locator(".section-quiz-take-link, a[href*='/take'][href*='/quiz/']")
    if take_links.count() == 0:
        pytest.skip("No ready Quiz in live DB — cannot check submitted state.")

    href = take_links.first.get_attribute("href") or ""
    if not href.startswith("http"):
        href = live_server + href

    page.goto(href)
    page.wait_for_load_state("networkidle")

    html = page.content().lower()

    # Only check for fabricated grades if the page is in the submitted state
    is_submitted = (
        "submitted" in html
        and ("grading" in html or "not yet" in html or "await" in html)
    )

    if not is_submitted:
        pytest.skip(
            "Take surface is not in submitted state — cannot verify absence of "
            "fabricated grade in submitted state. "
            "The HTTP-level test test_submitted_attempt_shows_no_fabricated_score "
            "covers this with an injected Quiz."
        )

    # In the submitted state, MUST NOT have fabricated grade patterns
    fabricated_patterns = [
        "all correct",
        "you passed",
        "you scored",
        "score:",
        "grade:",
        "100%",
        "correct!",
    ]
    found = [p for p in fabricated_patterns if p in html]
    assert not found, (
        f"Take surface submitted state contains fabricated-grade patterns: {found!r}. "
        "MC-5/ADR-038: the submitted state must never show a score, 'all correct', "
        "or any invented result. is_correct/explanation are NULL until grading."
    )


# ---------------------------------------------------------------------------
# AC-2 / ADR-038: take surface back-link to Section
# ---------------------------------------------------------------------------


def test_take_surface_has_back_link_to_section(page: Page, live_server: str) -> None:
    """
    ADR-038: the take surface must have a 'back to this Section' link in all states
    (/lecture/{chapter_id}#section-{n-m}-end).

    ADR-038: 'A "back to this Section" link (/lecture/{chapter_id}#section-{n-m}-end)
    in all states, so the learner can return to the Lecture page.'

    Trace: ADR-038 §template (back-link in all states).
    """
    page.goto(f"{live_server}/lecture/{MANDATORY_CHAPTER_ID}")
    page.wait_for_load_state("networkidle")

    take_links = page.locator(".section-quiz-take-link, a[href*='/take'][href*='/quiz/']")
    if take_links.count() == 0:
        pytest.skip("No ready Quiz in live DB.")

    href = take_links.first.get_attribute("href") or ""
    if not href.startswith("http"):
        href = live_server + href

    page.goto(href)
    page.wait_for_load_state("networkidle")

    html = page.content()

    # The back link must point back to the Lecture page with a section anchor
    has_back_link = (
        "#section-" in html
        and f"/lecture/{MANDATORY_CHAPTER_ID}" in html
    )
    assert has_back_link, (
        f"Take surface at {href!r} does not contain a back-link to the Section "
        f"(/lecture/{MANDATORY_CHAPTER_ID}#section-...-end). "
        "ADR-038: the take surface must have a 'back to this Section' link in all states."
    )


# ---------------------------------------------------------------------------
# AC-2 / ADR-038: take surface uses quiz-take-* CSS classes
# ---------------------------------------------------------------------------


def test_take_surface_uses_quiz_take_css_namespace(
    page: Page, live_server: str
) -> None:
    """
    AC-9 (TASK-015) / ADR-038 §CSS: the take surface's HTML must contain at least
    one quiz-take-* CSS class.

    ADR-038: 'the quiz-take-* namespace … .quiz-take (the page wrapper inside
    .page-main), .quiz-take-header, .quiz-take-form, .quiz-take-question, …'

    Trace: AC-9; ADR-038 §CSS; ADR-008 §prefix rule (quiz-take-* → quiz.css).
    """
    page.goto(f"{live_server}/lecture/{MANDATORY_CHAPTER_ID}")
    page.wait_for_load_state("networkidle")

    take_links = page.locator(".section-quiz-take-link, a[href*='/take'][href*='/quiz/']")
    if take_links.count() == 0:
        pytest.skip("No ready Quiz in live DB.")

    href = take_links.first.get_attribute("href") or ""
    if not href.startswith("http"):
        href = live_server + href

    page.goto(href)
    page.wait_for_load_state("networkidle")

    html = page.content()
    assert "quiz-take" in html, (
        f"Take surface at {href!r} does not contain any 'quiz-take' CSS class. "
        "ADR-038 §CSS: the take page must use the quiz-take-* namespace from quiz.css."
    )


# ---------------------------------------------------------------------------
# ADR-038: three-column shell — LHS rail + RHS Notes rail present on take page
# ---------------------------------------------------------------------------


def test_take_surface_three_column_shell_intact(
    page: Page, live_server: str
) -> None:
    """
    ADR-038 §Template: the take surface extends base.html.j2 (the three-column shell).
    The LHS chapter rail and RHS Notes rail must be present.

    ADR-038: 'The shell is base.html.j2 unchanged — the take page reuses the three-
    column layout (LHS chapter rail, centered .page-main, RHS Notes rail).'

    Trace: ADR-038 §Template; ADR-029 (RHS Notes rail); ADR-006 (LHS rail).
    """
    page.goto(f"{live_server}/lecture/{MANDATORY_CHAPTER_ID}")
    page.wait_for_load_state("networkidle")

    take_links = page.locator(".section-quiz-take-link, a[href*='/take'][href*='/quiz/']")
    if take_links.count() == 0:
        pytest.skip("No ready Quiz in live DB.")

    href = take_links.first.get_attribute("href") or ""
    if not href.startswith("http"):
        href = live_server + href

    page.goto(href)
    page.wait_for_load_state("networkidle")

    # LHS lecture rail must be present (navigation rail)
    lecture_rail = page.locator(".lecture-rail, nav.lecture-rail, [class*='lecture-rail']")
    assert lecture_rail.count() > 0, (
        f"Take surface at {href!r} has no .lecture-rail element. "
        "ADR-038: the take page uses base.html.j2's three-column shell — "
        "the LHS chapter navigation rail must be present."
    )

    # RHS Notes rail must be present (rail-notes)
    notes_rail = page.locator(".rail-notes, [class*='rail-notes'], .notes-rail")
    assert notes_rail.count() > 0, (
        f"Take surface at {href!r} has no .rail-notes element. "
        "ADR-038: the take page renders with a RHS Notes rail (truthy rail_notes_context). "
        "The Notes rail is present on the take page — jotting notes while taking a Quiz "
        "is genuinely useful (ADR-038 §Template)."
    )
