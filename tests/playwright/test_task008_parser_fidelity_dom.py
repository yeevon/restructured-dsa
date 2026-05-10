"""
Playwright DOM-assertion tests for TASK-008: Parser fidelity — unhandled
environments and bleeding text-formatting macros.

ADR-013 (split harness — visual layer): this file contains the Playwright DOM
assertions that confirm raw LaTeX tokens do NOT appear as visible text in the
rendered Lecture body.

ADR-010: Playwright tests run against the `live_server` fixture (a real uvicorn
process). The DOM assertions operate on the parsed DOM after Chromium renders
the page — this catches cases where the token appears in the HTTP response body
but is hidden from the user (e.g., inside a comment or display:none element),
and vice versa.

AC-6 (task spec): "at least one Playwright regression test per gap."
  - Gap A: one Playwright assertion on ch-09 that no begin-brace / end-brace literal
    token appears in visible body text.
  - Gap B: one Playwright assertion on ch-10 that no textbf-brace / textit-brace /
    emph-brace literal token appears in visible body text. An additional assertion
    on ch-13 is included because the HTTP-layer tests confirmed ch-13 is the actual
    dominant Gap B chapter (not ch-10), so at least one Playwright test is RED before
    the fix lands.

Rationale for Playwright vs. HTTP-protocol split (per task spec and ADR-013):
  The HTTP-protocol tests (test_task008_parser_fidelity.py) assert on the raw
  response body text (HTML string). The Playwright tests assert on what the
  browser renders as visible DOM text — complementary, different failure modes.
  The HTTP-layer catches "the token is in the HTML source."
  The Playwright layer catches "the token is visible in the rendered page."

ACs targeted:
  AC-6: One Playwright assertion per gap.

Coverage checklist:
  Boundary:
    - ch-09 (per catalog dominant for Gap A) and ch-10 (per catalog dominant
      for Gap B) are the focal chapters. ch-13 is added because empirical
      pre-fix testing confirmed ch-13 has the actual leak (both Gap A and Gap B).
  Edge:
    - end-brace checked independently from begin-brace in the Gap A Playwright test.
    - Both textit-brace and emph-brace checked alongside textbf-brace in Gap B test.
  Negative:
    - Each assertion is a hard "must not contain" on visible body text.
  Performance:
    - skipped: Playwright tests are session-scoped browser loads; the
      TASK-005 harness already has a 15s/page time-budget assertion that
      covers the full corpus including these chapters.

pytestmark registers all tests under task("TASK-008").
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.task("TASK-008")

# Focus chapters for the two gaps.
CH_09 = "ch-09-balanced-trees"   # Gap A dominant per catalog
CH_10 = "ch-10-graphs"            # Gap B dominant per catalog
CH_13 = "ch-13-additional-material"  # Empirically confirmed: actual dominant leak chapter

# Raw macro tokens to check (using separate string constants to avoid SyntaxWarning
# from backslash sequences in docstrings).
BEGIN_TOKEN = r"\begin{"
END_TOKEN = r"\end{"
TEXTBF_TOKEN = r"\textbf{"
TEXTIT_TOKEN = r"\textit{"
EMPH_TOKEN = r"\emph{"


def _get_body_text(page: "Page") -> str:
    """
    Get visible inner text from the lecture body element or main/body fallback.
    ADR-013: Playwright assertions operate on rendered DOM text, not HTML source.
    """
    body_count = page.locator(".lecture-body, main").count()
    if body_count > 0:
        return page.locator(".lecture-body, main").first.inner_text()
    return page.locator("body").inner_text()


# ===========================================================================
# AC-6 Gap A: no begin-brace / end-brace literal token visible in ch-09 body DOM.
#
# ADR-019: the unknown-env fallback wraps inner content in
#   <div class="unrecognized-env" data-env="X">{inner_html}</div>
# ADR-020: at _escape(raw) fallback sites, the wrapper tokens are consumed (Decision 4).
# ===========================================================================


def test_ch09_no_begin_token_visible_in_dom(page: Page, live_server: str) -> None:
    """
    AC-6 (Gap A, Playwright): navigate to ch-09 Lecture page and assert
    that the literal begin-brace substring does not appear in visible body text.

    Strategy: page inner_text() returns text content after browser parsing —
    HTML tags are stripped, only visible text nodes are included. A literal
    begin-brace token in inner_text() means the token leaked through the parser
    and the browser rendered it as visible text.

    ADR-019 + ADR-020: both the env-level wrapper and the raw-text fallback
    must be fixed. The Playwright layer checks the user-visible outcome.
    """
    url = f"{live_server}/lecture/{CH_09}"
    page.goto(url)
    page.wait_for_load_state("networkidle")

    visible_text = _get_body_text(page)

    assert BEGIN_TOKEN not in visible_text, (
        "AC-6 Gap A FAIL: the literal begin-brace token appears in visible text of "
        "ch-09-balanced-trees as rendered by Chromium. "
        "ADR-019: the unknown-env fallback must not leak begin-brace tokens to "
        "the rendered DOM. ADR-020: the defensive macro-stripping helper must "
        "consume begin-brace tokens at _escape(raw) fallback sites. "
        "This test is a regression check; it is RED when the fix is absent for ch-09."
    )


def test_ch09_no_end_token_visible_in_dom(page: Page, live_server: str) -> None:
    """
    AC-6 (Gap A, Playwright, close token): assert that the end-brace token does
    not appear as visible text in the ch-09 DOM.

    The close token may leak independently from the open token if only one side
    of an environment boundary triggers a parse failure.
    """
    url = f"{live_server}/lecture/{CH_09}"
    page.goto(url)
    page.wait_for_load_state("networkidle")

    visible_text = _get_body_text(page)

    assert END_TOKEN not in visible_text, (
        "AC-6 Gap A FAIL: the literal end-brace token appears in visible text of "
        "ch-09-balanced-trees. "
        "ADR-019 + ADR-020: both open and close env tokens must be consumed."
    )


def test_ch13_no_begin_token_visible_in_dom(page: Page, live_server: str) -> None:
    """
    AC-6 (Gap A, Playwright, ch-13): the HTTP-layer pre-fix tests confirmed that
    ch-13-additional-material has actual Gap A leaks in the current parser.
    This Playwright test is RED before the fix lands (unlike ch-09, which
    was already clean before the fix).

    ADR-013: the Playwright layer provides the user-visible-DOM confirmation
    that the HTTP-layer body-string assertion also catches.

    This test MUST FAIL before the implementer touches app/parser.py.
    """
    url = f"{live_server}/lecture/{CH_13}"
    page.goto(url)
    page.wait_for_load_state("networkidle")

    visible_text = _get_body_text(page)

    assert BEGIN_TOKEN not in visible_text, (
        "AC-6 Gap A FAIL (ch-13): the literal begin-brace token appears in "
        "visible text of ch-13-additional-material as rendered by Chromium. "
        "ADR-019 + ADR-020: begin-brace tokens must not reach visible DOM text "
        "for any chapter. This test is RED until the TASK-008 fix lands."
    )


# ===========================================================================
# AC-6 Gap B: no textbf-brace / textit-brace / emph-brace literal token visible.
#
# ADR-020: textbf{X} becomes <strong>X</strong>, textit{X}/emph{X} become
# <em>X</em> at every _escape(raw) fallback site. The browser strips these tags
# from inner_text() — the literal macro wrapper token must not be visible.
# ===========================================================================


def test_ch10_no_textbf_token_visible_in_dom(page: Page, live_server: str) -> None:
    """
    AC-6 (Gap B, Playwright, textbf, ch-10): navigate to ch-10 Lecture page and
    assert that the literal textbf-brace substring does not appear in visible text.

    ch-10 is the catalog-dominant chapter for Gap B. The most likely leak site
    is the tabular cell-walker fallback (ADR-020 Site A) for cells containing
    textbf mixed with inline math.
    """
    url = f"{live_server}/lecture/{CH_10}"
    page.goto(url)
    page.wait_for_load_state("networkidle")

    visible_text = _get_body_text(page)

    assert TEXTBF_TOKEN not in visible_text, (
        "AC-6 Gap B FAIL: the literal textbf-brace token appears in visible text "
        "of ch-10-graphs as rendered by Chromium. "
        "ADR-020: textbf{X} must be converted to <strong>X</strong> at every "
        "_escape(raw) fallback site (Sites A/B/C/D)."
    )


def test_ch10_no_textit_token_visible_in_dom(page: Page, live_server: str) -> None:
    """
    AC-6 (Gap B, Playwright, textit, ch-10): assert that the textit-brace token
    does not appear in visible body text in ch-10.

    ADR-020 maps textit{X} to <em>X</em>. Separate from textbf because they
    may activate different fallback-path sites.
    """
    url = f"{live_server}/lecture/{CH_10}"
    page.goto(url)
    page.wait_for_load_state("networkidle")

    visible_text = _get_body_text(page)

    assert TEXTIT_TOKEN not in visible_text, (
        "AC-6 Gap B FAIL: the literal textit-brace token appears in visible text "
        "of ch-10-graphs. "
        "ADR-020: textit{X} must become <em>X</em> at fallback sites."
    )


def test_ch10_no_emph_token_visible_in_dom(page: Page, live_server: str) -> None:
    """
    AC-6 (Gap B, Playwright, emph, ch-10): assert that the emph-brace token
    does not appear as visible text in the ch-10 DOM.

    ADR-020 maps emph{X} to <em>X</em>. Distinct from textit{} in LaTeX semantics
    but same HTML output in this project.
    """
    url = f"{live_server}/lecture/{CH_10}"
    page.goto(url)
    page.wait_for_load_state("networkidle")

    visible_text = _get_body_text(page)

    assert EMPH_TOKEN not in visible_text, (
        "AC-6 Gap B FAIL: the literal emph-brace token appears in visible text "
        "of ch-10-graphs. "
        "ADR-020: emph{X} must become <em>X</em> at fallback sites."
    )


def test_ch13_no_textbf_token_visible_in_dom(page: Page, live_server: str) -> None:
    """
    AC-6 (Gap B, Playwright, textbf, ch-13): the HTTP-layer pre-fix tests confirmed
    that ch-13-additional-material has actual Gap B leaks (textbf-brace visible in
    rendered HTML). This Playwright test confirms the DOM-visible outcome.

    This test MUST FAIL before the implementer touches app/parser.py.
    """
    url = f"{live_server}/lecture/{CH_13}"
    page.goto(url)
    page.wait_for_load_state("networkidle")

    visible_text = _get_body_text(page)

    assert TEXTBF_TOKEN not in visible_text, (
        "AC-6 Gap B FAIL (ch-13): the literal textbf-brace token appears in "
        "visible text of ch-13-additional-material as rendered by Chromium. "
        "ADR-020: the defensive _strip_text_formatting_macros helper must convert "
        "textbf{X} to <strong>X</strong> at every _escape(raw) fallback site. "
        "This test is RED until the TASK-008 fix lands."
    )
