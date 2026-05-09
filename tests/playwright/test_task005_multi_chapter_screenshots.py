"""
Playwright visual tests for TASK-005: Multi-chapter rendering validation.

ADR-013 (split harness — visual layer): this file walks all 12 Chapter IDs
against the `live_server` fixture (ADR-010), asserts the page heading is
visible, and captures a full-page screenshot to `tests/playwright/artifacts/`
(last-run-only, gitignored per ADR-010).

The screenshots are the human's 12-Chapter visual review surface per TASK-005
AC-2 and AC-3 and the ADR-010 screenshot-review gate.

Coverage checklist (documented in TASK-005 audit Run 005):
  Boundary:
    - ch-06-trees (last Mandatory) and ch-07-heaps-and-treaps (first Optional)
      are exercised by the full parametrize sweep; their badge locators are
      both asserted in test_lecture_page_mo_badge_is_visible.
  Edge:
    - All 12 Chapter IDs — not a spot-check; every Chapter is exercised.
    - ch-09-balanced-trees: the gap at ch-08 means ch-09 is the first number
      after a gap; it is included in the full parametrize.
  Negative:
    - test_lecture_page_title_has_no_backslash_residue: asserts '\\\\'
      does not appear in the visible text of the page heading element.
  Performance:
    - test_all_chapter_screenshots_under_time_budget: all 12 browser-driven
      page loads complete within 15s each (generous Playwright budget).

pytestmark registers all tests under task("TASK-005").
"""

from __future__ import annotations

import pathlib
import time

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.task("TASK-005")

# ---------------------------------------------------------------------------
# Canonical Chapter list — matches test_task005_multi_chapter_smoke.py exactly.
# ADR-013: "parameterized over the same 12 Chapter IDs."
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

# ADR-010: artifact directory — last run only, gitignored.
# Path matches the convention established by TASK-003 and TASK-004 Playwright tests.
_ARTIFACT_DIR = pathlib.Path(__file__).parent / "artifacts"

# Canonical M/O mapping (manifest §8)
_MANDATORY_IDS = {
    "ch-01-cpp-refresher",
    "ch-02-intro-to-algorithms",
    "ch-03-intro-to-data-structures",
    "ch-04-lists-stacks-and-queues",
    "ch-05-hash-tables",
    "ch-06-trees",
}


def _expected_badge(chapter_id: str) -> str:
    return "Mandatory" if chapter_id in _MANDATORY_IDS else "Optional"


# ===========================================================================
# AC-2 + AC-3: page heading is visible AND screenshot captured for each Chapter
# ADR-013 §Visual layer
# ===========================================================================

@pytest.mark.parametrize("chapter_id", ALL_CHAPTER_IDS)
def test_lecture_page_heading_is_visible(
    page: Page, live_server: str, chapter_id: str
) -> None:
    """
    TASK-005 AC-3(ii) + ADR-013 §Visual layer:
    For each Chapter, navigate to GET /lecture/{chapter_id} and assert the
    page heading element is visible in the rendered DOM.

    Locator strategy: the lecture header uses `h1` or `.lecture-header`
    (consistent with what TASK-003 tests use for the Lecture-header element).
    A visible heading confirms the page rendered structurally beyond HTTP 200.

    ADR-013 Decision: "Asserts the page heading is visible (use a locator
    consistent with what TASK-003's tests already use for the Lecture-header
    element)."
    """
    url = f"{live_server}/lecture/{chapter_id}"
    page.goto(url)
    page.wait_for_load_state("networkidle")

    # The Lecture-header element — consistent with TASK-003 Playwright convention.
    # If .lecture-header is absent from the DOM, the implementer has not yet
    # rendered the Lecture template; this test is the primary red signal for that.
    heading = page.locator("h1, .lecture-header")
    expect(heading.first).to_be_visible(
        timeout=10_000,
    )


@pytest.mark.parametrize("chapter_id", ALL_CHAPTER_IDS)
def test_lecture_page_full_page_screenshot(
    page: Page, live_server: str, chapter_id: str
) -> None:
    """
    TASK-005 AC-2 + ADR-013 §Visual layer:
    For each Chapter, capture a full-page screenshot to the artifact directory.

    ADR-010 "last run only" rule: each run overwrites; the artifact directory
    is a single named tree under tests/ (gitignored).  Viewport is pinned at
    1280x720 for cross-Chapter visual comparison consistency.

    The screenshot artifact is the human-review surface for:
      - AC-3(i): M/O badge correct
      - AC-3(ii): chapter title renders as header
      - AC-3(iii): at least one Section anchor visible
      - AC-3(iv): callouts render with palette borders + titles (ADR-012)
      - AC-3(v): tables without spurious column-spec first row (ADR-011)
      - AC-3(vi): code listings in <pre><code> blocks
    The human reviews these via the ADR-010 screenshot-review gate.
    """
    page.set_viewport_size({"width": 1280, "height": 720})
    url = f"{live_server}/lecture/{chapter_id}"
    page.goto(url)
    page.wait_for_load_state("networkidle")

    # Ensure artifact directory exists (ADR-010 implementer's responsibility)
    _ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

    screenshot_path = _ARTIFACT_DIR / f"lecture-{chapter_id}.png"
    page.screenshot(path=str(screenshot_path), full_page=True)

    # Assert the screenshot file was actually written — a missing file means
    # the Playwright screenshot call failed silently.
    assert screenshot_path.exists(), (
        f"Screenshot for {chapter_id} was not written to {screenshot_path}. "
        "ADR-010: each Chapter must produce a screenshot artifact for the human "
        "screenshot-review gate."
    )
    assert screenshot_path.stat().st_size > 0, (
        f"Screenshot for {chapter_id} at {screenshot_path} is empty. "
        "ADR-010: screenshot artifacts must be non-empty."
    )


# ===========================================================================
# MC-3 structural: M/O badge is visible in rendered DOM for every Chapter
# ADR-013 §Visual layer
# ===========================================================================

@pytest.mark.parametrize("chapter_id", ALL_CHAPTER_IDS)
def test_lecture_page_mo_badge_is_visible(
    page: Page, live_server: str, chapter_id: str
) -> None:
    """
    TASK-005 AC-3(i) / MC-3 (Playwright layer):
    The M/O badge (`.designation-badge` or the badge text) is visible in the
    rendered DOM for every Chapter, with the correct badge text.

    This is stronger than the smoke layer's body-text check — it requires the
    badge element to exist AND be visible (not display:none, not occluded).

    ADR-013: the Playwright layer's screenshot gives the human a 12-row visual
    confirmation surface; this assertion confirms the badge ELEMENT is present.
    """
    expected = _expected_badge(chapter_id)
    page.goto(f"{live_server}/lecture/{chapter_id}")
    page.wait_for_load_state("networkidle")

    # Strategy 1: use the .designation-badge class established by TASK-001/003
    badge = page.locator(".designation-badge")
    # Strategy 2: fall back to text matching if class not present
    badge_count = badge.count()

    # Case-insensitive compare: the .designation-badge CSS uses
    # `text-transform: uppercase` (TASK-003 / ADR-008 styling palette), so
    # Playwright's inner_text() returns the CSS-rendered uppercase form.
    # The HTML source is title-case ("Mandatory" / "Optional"); the visible
    # surface is uppercase.  Either form satisfies MC-3.
    if badge_count > 0:
        expect(badge.first).to_be_visible(timeout=5_000)
        badge_text = badge.first.inner_text().strip()
        assert expected.lower() in badge_text.lower(), (
            f"GET /lecture/{chapter_id} — .designation-badge text is {badge_text!r}, "
            f"expected to contain '{expected}' (case-insensitive). "
            "MC-3: every learner-facing surface must honor the M/O designation."
        )
    else:
        # If no .designation-badge, look for the text in the lecture header area
        header_text = page.locator(".lecture-header").inner_text()
        assert expected.lower() in header_text.lower(), (
            f"GET /lecture/{chapter_id} — neither a .designation-badge element nor "
            f"'{expected}' (case-insensitive) text in .lecture-header was found. "
            "MC-3: the M/O designation must be visible on every Chapter Lecture page."
        )


# ===========================================================================
# AC-3(iii): at least one section anchor is visible in rendered DOM
# ===========================================================================

@pytest.mark.parametrize("chapter_id", ALL_CHAPTER_IDS)
def test_lecture_page_has_at_least_one_section_anchor(
    page: Page, live_server: str, chapter_id: str
) -> None:
    """
    TASK-005 AC-3(iii) (Playwright layer): at least one `section[id]` element
    is present in the rendered DOM for every Chapter.

    Stronger than the smoke layer's substring check — Playwright queries the
    actual DOM rather than grepping the HTML text.
    """
    page.goto(f"{live_server}/lecture/{chapter_id}")
    page.wait_for_load_state("networkidle")

    section_anchors = page.locator("section[id]")
    count = section_anchors.count()

    assert count >= 1, (
        f"GET /lecture/{chapter_id} — no `section[id]` elements found in the "
        f"rendered DOM (found {count}). "
        "TASK-005 AC-3(iii): every Chapter must have at least one Section anchor. "
        "This may mean extract_sections() produced no sections or the template "
        "did not render the section elements."
    )


# ===========================================================================
# ADR-014 (Playwright): title text contains no backslash residue
# ===========================================================================

@pytest.mark.parametrize("chapter_id", ALL_CHAPTER_IDS)
def test_lecture_page_title_has_no_backslash_residue(
    page: Page, live_server: str, chapter_id: str
) -> None:
    """
    ADR-014 (Playwright layer): the visible title text in the Lecture-header
    element must not contain the literal '\\\\' substring.

    Every Chapter in the corpus has a title of the form:
        \\title{CS 300 -- Chapter N Lectures\\\\\\\\large <subtitle>}
    The current extract_title_from_latex() strips \\\\large but NOT \\\\, so
    the literal '\\\\' appears in the rendered title.

    This test will be RED until the ADR-014 regex fix is applied.

    Scope: this tests the Playwright (rendered-DOM) layer; the unit-level test
    is in test_task005_multi_chapter_smoke.py.
    """
    page.goto(f"{live_server}/lecture/{chapter_id}")
    page.wait_for_load_state("networkidle")

    # Get the visible text of the lecture header / h1
    header = page.locator("h1, .lecture-header")
    header_count = header.count()

    if header_count > 0:
        header_text = header.first.inner_text()
        assert "\\\\" not in header_text, (
            f"GET /lecture/{chapter_id} — the page heading contains '\\\\\\\\': "
            f"{header_text!r}. "
            "ADR-014: extract_title_from_latex() must strip the \\\\\\\\ LaTeX "
            "linebreak macro. This test is RED until the ADR-014 fix is applied."
        )
    else:
        pytest.fail(
            f"GET /lecture/{chapter_id} — no h1 or .lecture-header element found. "
            "Cannot verify title backslash-residue for this Chapter."
        )


# ===========================================================================
# Performance: all 12 Chapter pages load within a generous wall-clock budget
# ===========================================================================

def test_all_chapter_screenshots_under_time_budget(
    page: Page, live_server: str
) -> None:
    """
    Performance: all 12 Chapter Lecture pages reach DOMContentLoaded within
    15 seconds each in a Playwright session (generous budget that catches
    pathological regressions — runaway recursion, O(n^2) parser paths —
    not a micro-benchmark).

    ADR-003: rendering is at request time; 15s/page is extremely generous for
    a local uvicorn server driving a pylatexenc parser on a 12-file corpus.
    """
    slow_chapters = []
    for chapter_id in ALL_CHAPTER_IDS:
        t0 = time.monotonic()
        page.goto(
            f"{live_server}/lecture/{chapter_id}",
            wait_until="domcontentloaded",
        )
        elapsed = time.monotonic() - t0
        if elapsed > 15.0:
            slow_chapters.append((chapter_id, elapsed))

    assert slow_chapters == [], (
        f"Playwright: the following Chapters took >15s to reach DOMContentLoaded: "
        f"{slow_chapters!r}. "
        "This may indicate pathological scaling in the parser or template render. "
        "ADR-003: the pipeline must not exhibit O(n^2) or runaway recursion."
    )
