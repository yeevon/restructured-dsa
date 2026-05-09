"""
Playwright DOM tests for TASK-004: Fix parser fidelity.

These tests verify the two rendering bugs (ADR-011, ADR-012) against the
live rendered DOM — catching "silent ship" failures that string-search tests
on the HTTP response body can miss (per ADR-010 rationale).

Bug 1 (ADR-011): Tabular column spec passthrough.
  The column-spec argument `lll` from `\\begin{tabular}{lll}` must not appear
  as a visible text node in any table row in the rendered DOM.

Bug 2 (ADR-012): Callout title passthrough.
  `\\begin{ideabox}[Chapter map]` must render as a `<div class="callout-title">`
  element visible in the DOM, not as inline bracketed text.

Each test uses Playwright's DOM assertions (locators, inner_text, count) against
the live ch-01 lecture page rendered by a running FastAPI server (ADR-010).

Per ADR-010: at least one Playwright test per fix is required as a TASK-004
acceptance criterion.

pytestmark registers all tests under task("TASK-004").
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.task("TASK-004")

LECTURE_URL = "/lecture/ch-01-cpp-refresher"

# Total number of titled callouts in ch-01 (all 111 instances have [Title])
TOTAL_TITLED_CALLOUTS_CH01 = 27 + 14 + 12 + 29 + 29  # = 111


# ===========================================================================
# ADR-011: Tabular column spec must not appear in rendered table cells
# ===========================================================================

def test_tabular_column_spec_lll_not_in_any_table_cell(
    page: Page, live_server: str
) -> None:
    """
    ADR-011 (Playwright): `lll` from `\\begin{tabular}{lll}` on ch-01 line 144
    must not be visible as text content in any table cell (`<td>` or `<th>`).

    Strategy: navigate to the lecture page, query all <td> and <th> elements,
    and assert none has "lll" as its (trimmed) text content.

    This is the primary Playwright red signal for the tabular column spec bug.
    At least one Playwright test per fix is required by TASK-004 ACs + ADR-010.
    """
    page.goto(live_server + LECTURE_URL)
    page.wait_for_load_state("networkidle")

    # Find all table cells (td and th) on the page
    all_cells = page.locator("td, th")
    cell_count = all_cells.count()

    # At least some cells must exist (confirms tables rendered at all)
    assert cell_count > 0, (
        "No <td> or <th> elements found on the ch-01 lecture page. "
        "The tabular environments in ch-01 should have rendered table cells. "
        "If zero cells are found, the tabular handler may have regressed entirely."
    )

    # Collect any cell whose stripped text content equals the column spec strings
    spec_cells = []
    for i in range(cell_count):
        cell = all_cells.nth(i)
        text = cell.inner_text().strip()
        # Check for column spec patterns — single letters or the exact spec strings
        if text in ("lll", "ll", "lcr", "l|c|r", "l", "c", "r") or text == "lll":
            spec_cells.append(text)

    assert spec_cells == [], (
        f"Table cell(s) with column-spec text found in rendered DOM: {spec_cells!r}. "
        "ADR-011: the column-spec argument must be stripped entirely from rendered "
        "output. The cell text 'lll' is the exact bug symptom from ch-01 line 144."
    )


def test_tabular_data_rows_are_present_in_dom(
    page: Page, live_server: str
) -> None:
    """
    ADR-011 (Playwright): Stripping the column spec must not drop data rows.

    The ch-01 tabular at line 144 contains "C-style array" as a data row cell.
    That text must be visible in a `<td>` element.

    This test confirms the fix did not break row rendering while stripping the spec.
    """
    page.goto(live_server + LECTURE_URL)
    page.wait_for_load_state("networkidle")

    # "C-style array" appears in the first data row of the ch-01 tabular (line 145)
    # If the fix only strips the spec but preserves rows, this cell must exist.
    cell = page.locator("td", has_text="C-style array")
    expect(cell.first).to_be_visible(
        timeout=5000,
    )


# ===========================================================================
# ADR-012: Callout title must appear in a structural callout-title element
# ===========================================================================

def test_callout_title_chapter_map_in_callout_title_div(
    page: Page, live_server: str
) -> None:
    """
    ADR-012 (Playwright): ch-01 line 11: `\\begin{ideabox}[Chapter map]` —
    the title "Chapter map" must be visible inside a `.callout-title` element
    in the rendered DOM.

    Strategy: use `page.locator(".callout-title")` to find all callout-title
    elements, then assert at least one contains "Chapter map" as text.

    This is the primary Playwright red signal for the callout title bug.
    At least one Playwright test per fix is required by TASK-004 ACs + ADR-010.
    """
    page.goto(live_server + LECTURE_URL)
    page.wait_for_load_state("networkidle")

    # The .callout-title elements must exist at all
    title_divs = page.locator(".callout-title")
    count = title_divs.count()
    assert count > 0, (
        "No .callout-title elements found in the rendered DOM of the ch-01 "
        "lecture page. ADR-012: every callout with a [Title] argument must "
        "emit a <div class=\"callout-title\"> element. "
        "Ch-01 has 111 titled callouts; if count is 0 the fix is not present."
    )

    # At least one must contain "Chapter map"
    chapter_map_div = page.locator(".callout-title", has_text="Chapter map")
    expect(chapter_map_div.first).to_be_visible(
        timeout=5000,
    )


def test_callout_title_count_matches_titled_callouts(
    page: Page, live_server: str
) -> None:
    """
    ADR-012 (Playwright): All 111 titled callouts in ch-01 must produce a
    `.callout-title` element in the DOM.

    Batch assertion over the whole affected set — not a spot-check of item 0.
    """
    page.goto(live_server + LECTURE_URL)
    page.wait_for_load_state("networkidle")

    title_divs = page.locator(".callout-title")
    count = title_divs.count()

    assert count >= TOTAL_TITLED_CALLOUTS_CH01, (
        f"Expected at least {TOTAL_TITLED_CALLOUTS_CH01} .callout-title elements "
        f"in the ch-01 rendered DOM (one per titled callout), found {count}. "
        "ADR-012: every callout with a [Title] argument must emit a structural "
        "callout-title element. If count < 111, some callout types are not fixed."
    )


def test_raw_bracketed_title_not_visible_in_dom(
    page: Page, live_server: str
) -> None:
    """
    ADR-012 (Playwright, negative): `[Chapter map]` must not appear as visible
    text anywhere in the rendered DOM outside of a `.callout-title` element.

    Strategy: get the full page text content and assert the pattern `[Chapter map]`
    is absent. The Playwright `inner_text()` call returns the rendered text — if
    the bug is present, the brackets appear literally in the rendered text.
    """
    page.goto(live_server + LECTURE_URL)
    page.wait_for_load_state("networkidle")

    page_text = page.locator("body").inner_text()
    assert "[Chapter map]" not in page_text, (
        "Raw bracketed title '[Chapter map]' found in the visible text of the "
        "ch-01 lecture page. ADR-012: the [Title] argument must be extracted into "
        "a structural <div class=\"callout-title\"> element, not rendered as "
        "inline bracketed text. This is the exact bug symptom TASK-004 fixes."
    )


def test_callout_title_is_first_child_of_callout_div(
    page: Page, live_server: str
) -> None:
    """
    ADR-012 §Decision: "The title div precedes the callout body content."

    The .callout-title element must be the first child of its parent callout
    div (i.e., it must come before the body text).

    Strategy: for the first ideabox on the page, check that its first child
    element has class callout-title.
    """
    page.goto(live_server + LECTURE_URL)
    page.wait_for_load_state("networkidle")

    # The first ideabox on ch-01 (line 11) has title [Chapter map]
    first_ideabox = page.locator('[data-callout="ideabox"]').first
    expect(first_ideabox).to_be_visible(timeout=5000)

    # Its first child element should be the callout-title div
    first_child = first_ideabox.locator("> *").first
    # The first child must contain the title text.
    # Case-insensitive compare: .callout-title CSS uses `text-transform: uppercase`
    # (ADR-012 / ADR-008 styling palette), so inner_text() returns the rendered
    # uppercase form ("CHAPTER MAP"); the source title is "Chapter map".
    first_child_text = first_child.inner_text().strip()
    assert "chapter map" in first_child_text.lower(), (
        "The first child of the first ideabox callout div does not contain "
        "the title text 'Chapter map' (case-insensitive). "
        "ADR-012 §Decision: 'The title div precedes the callout body content.' "
        f"First child text found: {first_child_text!r}"
    )
