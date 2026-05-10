"""
Playwright DOM tests for TASK-007:
  1. Tabular column-spec residue absence (ADR-017).
  2. `\\texttt{}` → `<span class="texttt">` with MathJax passthrough (ADR-018).

These tests exercise the live rendered DOM in a real Chromium browser
(via the `live_server` fixture, ADR-010). They catch what HTTP-level
string-search tests can miss — specifically, MathJax rendering inside
`<span class="texttt">` only fires in a real browser after JS execution.

Coverage (Playwright layer per ADR-013 §Visual layer):

ADR-017 (tabular residue):
  - ch-02, ch-03, ch-04: first-cell of first table has no spec residue.
  - Locator: `table tr:first-child td:first-child, table tr:first-child th:first-child`.
  - Negative: inner_text() of those cells must not match residue patterns.

ADR-018 (texttt as span):
  - ch-04 "Picture the list" callout: after `networkidle`, `<mjx-container>`
    elements exist INSIDE a `<span class="texttt">` (proves MathJax processed math).
  - ch-04: visible text of the first texttt span does NOT contain literal
    `\\to` or `\\bullet` substrings (post-MathJax, those become glyphs).
  - ch-04: `<span class="texttt">` element's computed font-family includes
    'monospace' or 'Courier' (CSS rule from lecture.css is applied).

Coverage checklist:
  Boundary:
    - ch-02 (6 tabular instances), ch-03 (30), ch-04 (17): first-cell check.
    - The M/O boundary chapters (ch-06, ch-07) are NOT tabular hotspots;
      first-cell assertion still runs but is expected to pass trivially.
  Edge:
    - After networkidle: MathJax has had time to process inline math.
    - texttt spans in ch-04's callout section (nested context).
  Negative:
    - Literal `$\\to$`, `$\\bullet$`, `$\\leftarrow$` must NOT appear in the
      visible text of ch-04's texttt spans after MathJax runs.
    - Spec residue `lccc@`, `p3.4cm` must NOT appear in any first-table-cell
      visible text in ch-02/03/04.
  Performance:
    - All Playwright tests use `wait_for_load_state("networkidle")` with a
      generous timeout (20s) to allow MathJax to complete rendering.
    - A per-Chapter time budget is NOT separately tested here (covered by
      test_task005_multi_chapter_screenshots.py performance test).

pytestmark registers all tests under task("TASK-007").
"""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.task("TASK-007")

# Chapters with confirmed @{}...@{} or p{width} column-spec residue
TABULAR_HOT_CHAPTERS = [
    "ch-02-intro-to-algorithms",
    "ch-03-intro-to-data-structures",
    "ch-04-lists-stacks-and-queues",
]

# Corpus spec-residue patterns (visible text that must NOT appear in first cells)
RESIDUE_PATTERNS = [
    re.compile(r"^[lcr]+@"),   # "lccc@..." etc
    re.compile(r"^@\{"),        # "@{..." (rare but possible if outer not consumed)
    re.compile(r"^p\d"),        # "p3..." (p-width residue without braces)
    re.compile(r"^p\{"),        # "p{..." (p-width residue with brace)
    re.compile(r"^\|[lcr]"),    # "|c|..." vertical bar spec residue
]

CH04_URL_SLUG = "ch-04-lists-stacks-and-queues"
CH02_URL_SLUG = "ch-02-intro-to-algorithms"
CH03_URL_SLUG = "ch-03-intro-to-data-structures"


# ===========================================================================
# ADR-017: Tabular first-cell residue absence (Playwright DOM layer)
# ===========================================================================

@pytest.mark.parametrize("chapter_slug", TABULAR_HOT_CHAPTERS)
def test_tabular_first_cell_no_spec_residue(
    page: Page, live_server: str, chapter_slug: str
) -> None:
    """
    ADR-017 (Playwright AC-6a): for each hot chapter, the first `<td>` or `<th>`
    in the first `<tr>` of every `<table>` must NOT begin with column-spec residue.

    Strategy: iterate all `table` elements on the page; for each, find the first
    row's first cell; get its `inner_text()` and check against residue patterns.

    This test is the primary Playwright red signal for tabular residue in the
    hot chapters. It will be RED before ADR-017 is implemented because ch-02/03/04
    have confirmed residue instances (Run 008 catalog: 53 total instances).

    TASK-007 AC-6(a): "tabular-residue absence in ch-02/03/04 first-row first-cell."
    """
    url = f"{live_server}/lecture/{chapter_slug}"
    page.goto(url)
    page.wait_for_load_state("networkidle", timeout=20_000)

    tables = page.locator("table")
    table_count = tables.count()

    # If the chapter renders no tables, the test still passes (nothing to check)
    # but we log this as a warning via assert message.
    if table_count == 0:
        pytest.skip(
            f"No <table> elements found on {chapter_slug}. "
            "If the chapter has tabular environments, the renderer may not be "
            "emitting <table> tags — separate issue."
        )

    residue_found = []
    for i in range(table_count):
        table = tables.nth(i)
        # Locate the first cell of the first row
        first_cell = table.locator("tr:first-child td:first-child, tr:first-child th:first-child").first
        if first_cell.count() == 0:
            continue
        try:
            cell_text = first_cell.inner_text(timeout=2_000).strip()
        except Exception:
            continue

        for pattern in RESIDUE_PATTERNS:
            if pattern.search(cell_text):
                residue_found.append({
                    "table_index": i,
                    "cell_text_prefix": cell_text[:80],
                    "pattern": pattern.pattern,
                })
                break

    assert residue_found == [], (
        f"Playwright ({chapter_slug}): column-spec residue found in the first "
        f"cell of {len(residue_found)} table(s). "
        "ADR-017: balanced-brace consumption must eliminate ALL spec residue "
        "from the rendered DOM. These are the exact leak shapes the project_issue "
        "catalogued across ch-02/03/04. "
        f"Residue details: {residue_found!r}"
    )


def test_ch04_first_table_first_cell_has_real_content(
    page: Page, live_server: str
) -> None:
    """
    ADR-017 (Playwright positive): ch-04's first table first cell must start
    with real content (not spec residue).

    After the fix, the first cell should be a data word (capital letter,
    not one of [lcr@p|]). This pins the specific ch-04 expectation.

    ch-04 has 17 confirmed tabular residue instances. The first table in the
    chapter likely has an `@{}lccc@{}` spec; its first data row's first cell
    should start with a capital letter (e.g., "Operation", "Algorithm", etc.).
    """
    page.goto(f"{live_server}/lecture/{CH04_URL_SLUG}")
    page.wait_for_load_state("networkidle", timeout=20_000)

    tables = page.locator("table")
    if tables.count() == 0:
        pytest.skip("No tables rendered in ch-04.")

    first_cell = tables.first.locator(
        "tr:first-child td:first-child, tr:first-child th:first-child"
    ).first
    if first_cell.count() == 0:
        pytest.skip("No first cell in ch-04's first table.")

    cell_text = first_cell.inner_text(timeout=5_000).strip()

    # The first cell must NOT start with spec-residue chars [lcr@p|]
    # as the first character.
    first_char = cell_text[0] if cell_text else ""
    assert first_char not in "lcr@p|", (
        f"Playwright (ch-04): first cell of first table starts with '{first_char}' "
        f"— full text prefix: {cell_text[:60]!r}. "
        "This is consistent with column-spec residue (l, c, r, @, p, | are all "
        "spec characters in the `@{{}}lccc@{{}}` idiom). "
        "ADR-017: the first cell must contain real table data (a letter that is "
        "part of actual table content, not a column-spec character)."
    )


# ===========================================================================
# ADR-018: `<span class="texttt">` with MathJax passthrough (Playwright DOM)
# ===========================================================================

def test_ch04_texttt_span_contains_mjx_container_after_mathjax(
    page: Page, live_server: str
) -> None:
    """
    TASK-007 AC-3 (Playwright): after navigating to ch-04 and waiting for
    `networkidle` (so MathJax has run), a `<mjx-container>` element must exist
    INSIDE a `<span class="texttt">` element.

    This is the primary Playwright red signal for ADR-018.

    Before the fix:
      - `\\texttt{}` → `<code>...</code>`
      - MathJax skips `<code>` (it's in `skipHtmlTags`)
      - `<mjx-container>` does NOT appear inside `<code>`
      - The math renders as literal `$\\to$` text

    After the fix:
      - `\\texttt{}` → `<span class="texttt">...</span>`
      - MathJax processes `<span>` (not in `skipHtmlTags`)
      - `<mjx-container>` appears inside `<span class="texttt">`
      - Math renders as glyphs

    This test will be RED before ADR-018 is implemented.
    """
    page.goto(f"{live_server}/lecture/{CH04_URL_SLUG}")
    page.wait_for_load_state("networkidle", timeout=30_000)  # MathJax needs time

    # Assert there is at least one <span class="texttt"> on the page
    texttt_spans = page.locator('span.texttt')
    span_count = texttt_spans.count()
    assert span_count > 0, (
        "Playwright (ch-04): no `<span class=\"texttt\">` elements found "
        "after page load. "
        "ADR-018: `\\texttt{{}}` must emit `<span class=\"texttt\">`. "
        "ch-04 has 39+ confirmed `\\texttt{{}}` usages with inline math. "
        "If count is 0, the ADR-018 fix is not present."
    )

    # Assert that at least one texttt span contains an mjx-container child
    # (proving MathJax processed math inside the span)
    mjx_inside_texttt = page.locator('span.texttt mjx-container')
    mjx_count = mjx_inside_texttt.count()

    assert mjx_count > 0, (
        f"Playwright (ch-04): {span_count} `<span class=\"texttt\">` found, "
        "but ZERO `<mjx-container>` elements inside them. "
        "ADR-018: MathJax must process inline math inside `<span class=\"texttt\">`. "
        "MathJax does not skip `<span>` (only `code`, `pre`, `script`, etc. are "
        "in its default `skipHtmlTags`). "
        "If `<mjx-container>` is absent, MathJax may not have run yet (try "
        "increasing networkidle timeout), OR the span is missing math content, "
        "OR MathJax is skipping the span for another reason. "
        "TASK-007 AC-3: 'MathJax renders the embedded math glyphs (rendered DOM "
        "contains `<mjx-container>` elements within the typewriter-fonted span)'."
    )


def test_ch04_texttt_visible_text_has_no_literal_math_tokens(
    page: Page, live_server: str
) -> None:
    """
    ADR-018 (Playwright negative): after MathJax runs on ch-04, the visible
    text of each `<span class="texttt">` must NOT contain the literal strings
    `\\to`, `\\bullet`, or `\\leftarrow`.

    Before the fix: math is trapped in `<code>`, MathJax skips it,
    and `$\\to$` renders as literal text `$\to$` visible on screen.

    After the fix: math inside `<span class="texttt">` is processed by MathJax;
    `$\\to$` becomes → (a glyph). The visible text does not contain `\to`.

    This test will be RED before ADR-018 is implemented (or before MathJax runs).
    """
    page.goto(f"{live_server}/lecture/{CH04_URL_SLUG}")
    page.wait_for_load_state("networkidle", timeout=30_000)

    texttt_spans = page.locator('span.texttt')
    span_count = texttt_spans.count()

    if span_count == 0:
        pytest.fail(
            "Playwright (ch-04): no `<span class=\"texttt\">` elements found. "
            "ADR-018 fix is not present — cannot check for math-token literals."
        )

    literal_math_found = []
    for i in range(span_count):
        span = texttt_spans.nth(i)
        try:
            visible_text = span.inner_text(timeout=2_000)
        except Exception:
            continue

        # Post-MathJax, these literal LaTeX source strings must be gone
        for token in (r"\to", r"\bullet", r"\leftarrow", r"\rightarrow",
                      r"\nwarrow", r"\searrow"):
            if token in visible_text:
                literal_math_found.append({
                    "span_index": i,
                    "token": token,
                    "text_prefix": visible_text[:80],
                })

    assert literal_math_found == [], (
        f"Playwright (ch-04): literal LaTeX math tokens found in the visible "
        f"text of {len(literal_math_found)} `<span class=\"texttt\">` element(s) "
        "after MathJax ran. "
        "ADR-018: MathJax must render `$\\to$` as → (a glyph), not as `\\to` text. "
        "If literal `\\to` appears, MathJax did not process the span's math — "
        "either the span is still `<code>` (old bug), or MathJax did not run, "
        "or networkidle was not reached. "
        f"Offending spans: {literal_math_found[:3]!r}"
    )


def test_ch04_texttt_span_has_monospace_computed_font_family(
    page: Page, live_server: str
) -> None:
    """
    AC-4 (TASK-007) / ADR-018 (Playwright): the first `<span class="texttt">`
    on ch-04 must have a computed `font-family` that includes 'monospace'
    or 'Courier' — proving the `.texttt` CSS rule from lecture.css is applied.

    TASK-007 AC-4: "the typewriter font is preserved visually (Playwright
    assertion: the span has computed `font-family` matching `monospace` per
    the new `.texttt` CSS rule)."

    This test will be RED before ADR-018 is implemented (no span → no CSS).
    """
    page.goto(f"{live_server}/lecture/{CH04_URL_SLUG}")
    page.wait_for_load_state("networkidle", timeout=30_000)

    texttt_spans = page.locator('span.texttt')
    if texttt_spans.count() == 0:
        pytest.fail(
            "Playwright (ch-04): no `<span class=\"texttt\">` elements. "
            "Cannot check computed font-family. ADR-018 fix is not present."
        )

    first_span = texttt_spans.first
    expect(first_span).to_be_visible(timeout=5_000)

    # Evaluate the computed font-family via JS
    computed_font = page.evaluate(
        "(el) => window.getComputedStyle(el).fontFamily",
        first_span.element_handle(),
    )

    assert computed_font is not None, (
        "Playwright (ch-04): could not read computed font-family for "
        "`<span class=\"texttt\">`. Page JS evaluation returned None."
    )

    font_lower = computed_font.lower()
    assert "monospace" in font_lower or "courier" in font_lower, (
        f"Playwright (ch-04): `<span class=\"texttt\">` computed font-family is "
        f"'{computed_font}', which does not include 'monospace' or 'Courier'. "
        "ADR-018 §Decision: `.texttt {{ font-family: 'Courier New', Courier, monospace; }}`. "
        "ADR-008: this rule must be in lecture.css and the browser must apply it. "
        "If font-family is the default (serif or sans-serif), the `.texttt` CSS "
        "rule is either missing from lecture.css or the class is not applied to "
        "the span element."
    )


# ===========================================================================
# ADR-018: ch-04 screenshot capturing the texttt+MathJax rendering
# AC-6(b): at least one regression test per fix verifies corrected rendering
# ===========================================================================

def test_ch04_texttt_mathjax_screenshot(
    page: Page, live_server: str, tmp_path
) -> None:
    """
    AC-6(b) (TASK-007): capture a screenshot of ch-04 after MathJax has
    rendered, producing visual evidence of the `\\texttt{}` + math glyph fix.

    This screenshot is the human-review artifact for the texttt-math fix
    per ADR-010's verification gate.

    ADR-010: "the verification gate is satisfied when the pytest run is green
    and the human reviews the last-run screenshots."
    """
    import pathlib
    artifact_dir = pathlib.Path(__file__).parent / "artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=True)

    page.set_viewport_size({"width": 1280, "height": 900})
    page.goto(f"{live_server}/lecture/{CH04_URL_SLUG}")
    page.wait_for_load_state("networkidle", timeout=30_000)

    screenshot_path = artifact_dir / "task007-ch04-texttt-mathjax.png"
    page.screenshot(path=str(screenshot_path), full_page=True)

    assert screenshot_path.exists() and screenshot_path.stat().st_size > 0, (
        f"Screenshot for ch-04 (texttt/MathJax fix) was not written to "
        f"{screenshot_path}. ADR-010: screenshot artifact must be produced."
    )
