"""
Playwright tests for TASK-003: Style the navigation surface.

These tests verify the *visual* ACs from TASK-003 — properties a learner
actually depends on that the prior TestClient/string-search tests could not
catch (the "silent ship" failure mode ADR-010 is designed to prevent).

Each test uses Playwright's rendered-DOM assertions: bounding-box positions,
computed styles, role/name reachability, and navigability.  A test that
asserts a CSS class is present in the HTML is NOT a substitute for these tests;
passing CSS-class-present assertions was exactly how TASK-002 shipped a wall
of unstyled text.

Acceptance criteria tested (references to TASK-003 task file + ADR-008):

  AC-1  The LHS navigation rail visibly occupies a left-hand region of the
        viewport — not a stacked-on-top block.  (bounding-box assertion)

  AC-2  The "Mandatory" section heading is visually distinguishable from the
        "Optional" section heading via the designation palette.  ADR-008:
        "reuse the established designation-mandatory / designation-optional
        palette."  (computed-style color assertion)

  AC-3  Chapter rows render as clickable links with visible hover/focus
        affordance — links are reachable by role and navigation works.

  AC-4  On a Lecture page (GET /lecture/{id}), the same rail appears in the
        same left-hand position AND the Lecture body's existing styling
        (designation badge, section headings) is preserved.

  AC-5  A `.nav-chapter-error` row is visually distinct from healthy rows —
        ADR-008 commits to the warnbox palette for error rows.

  AC-6  The `.nav-chapter-empty` "(none)" row is muted/de-emphasized (lower
        contrast or italicized) compared to healthy rows.

  AC-7  The page-layout is a two-column grid, not stacked vertically — the
        `.page-layout` container uses CSS Grid as committed by ADR-008.

  CSS-ASSET  The `base.css` stylesheet (committed by ADR-008) is loaded and
             returns HTTP 200 (not 404).

pytestmark registers all tests under task("TASK-003").
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.task("TASK-003")

# ---------------------------------------------------------------------------
# CSS-ASSET — base.css must be loaded (ADR-008 commits to a new file)
# ---------------------------------------------------------------------------


def test_base_css_is_loaded_and_returns_200(page: Page, live_server: str) -> None:
    """
    ADR-008: introduces `app/static/base.css` as a new CSS asset.
    `base.html.j2` must load it.  A 404 on base.css means the implementer
    has not yet created the file — this test is the primary "is CSS present?"
    red signal for the TDD phase.

    Strategy: navigate to GET / and intercept the base.css resource response.

    Trace: TASK-003 AC-7; ADR-008 (CSS file split — base.css introduced).
    """
    css_responses: dict[str, int] = {}

    def capture_response(response):
        if "base.css" in response.url:
            css_responses["base.css"] = response.status

    page.on("response", capture_response)
    page.goto(live_server + "/")
    page.wait_for_load_state("networkidle")

    assert "base.css" in css_responses, (
        "GET / did not request base.css at all. "
        "ADR-008: base.html.j2 must load /static/base.css. "
        "Either the <link rel='stylesheet' href='/static/base.css'> tag is "
        "missing from base.html.j2 or the implementer has not yet added it."
    )
    assert css_responses["base.css"] == 200, (
        f"base.css was requested but returned HTTP {css_responses['base.css']} "
        "(expected 200). ADR-008: app/static/base.css must exist and be served. "
        "The implementer has not yet created this file."
    )


# ---------------------------------------------------------------------------
# AC-1 — Rail is on the LEFT (bounding-box positional assertion)
# ---------------------------------------------------------------------------


def test_rail_occupies_left_side_of_viewport(page: Page, live_server: str) -> None:
    """
    AC-1: The LHS navigation rail visibly occupies a left-hand region of the
    viewport — not stacked above the main content.

    Strategy: compare the bounding boxes of `.lecture-rail` (the nav element)
    and `.page-main` (the main content area).  On a two-column layout the rail's
    right edge must be to the LEFT of the main column's left edge.

    ADR-008: "The two-column layout (`.page-layout` containing `.lecture-rail`
    and `.page-main`) is implemented with CSS Grid."  The grid makes the rail
    the first track and the main content the second track.

    This is the core test that TASK-002's structural tests could NOT catch —
    they checked class names but not rendered positions.

    Trace: TASK-003 AC-1 "LHS navigation rail visibly occupies a left-hand
    region of the viewport (not a stacked-on-top block)"; ADR-008.
    """
    page.goto(live_server + "/")
    page.wait_for_load_state("networkidle")

    rail = page.locator("nav.lecture-rail")
    main = page.locator("main.page-main")

    expect(rail).to_be_visible()
    expect(main).to_be_visible()

    rail_box = rail.bounding_box()
    main_box = main.bounding_box()

    assert rail_box is not None, "nav.lecture-rail has no bounding box (not visible?)."
    assert main_box is not None, "main.page-main has no bounding box (not visible?)."

    # In a two-column side-by-side layout:
    # rail's right edge (rail_x + rail_width) should be at or left of main's left edge.
    rail_right = rail_box["x"] + rail_box["width"]
    main_left = main_box["x"]

    assert rail_right <= main_left + 10, (  # 10px tolerance for border/gap
        f"Rail right edge ({rail_right:.0f}px) is to the RIGHT of or overlapping "
        f"the main column's left edge ({main_left:.0f}px). "
        "This indicates the rail is NOT rendered as a left-column — it may be "
        "stacked above the main content (no CSS Grid applied yet). "
        "ADR-008: the page-layout must use CSS Grid so the rail occupies a "
        "left-hand column and the main content is to its right."
    )


def test_rail_is_in_left_third_of_viewport(page: Page, live_server: str) -> None:
    """
    AC-1 (boundary variant): the rail must start at the left edge of the page
    and occupy at most the left 40% of viewport width.

    Rationale: ADR-008 fixes the rail track at `minmax(220px, 18rem)` — that's
    roughly 16-20% of a 1280px viewport.  Accepting up to 40% leaves room for
    unusual font sizes without a false failure.

    Trace: TASK-003 AC-1; ADR-008 CSS Grid track definition.
    """
    page.set_viewport_size({"width": 1280, "height": 900})
    page.goto(live_server + "/")
    page.wait_for_load_state("networkidle")

    rail = page.locator("nav.lecture-rail")
    box = rail.bounding_box()

    assert box is not None, "nav.lecture-rail has no bounding box."

    viewport_width = 1280
    rail_right = box["x"] + box["width"]

    # Rail must start near the left edge (x < 50px — only page margin)
    assert box["x"] < 50, (
        f"Rail starts at x={box['x']:.0f}px, expected near the left edge (<50px). "
        "ADR-008: the rail is the first track in the page grid."
    )
    # Rail must not take up more than 40% of the viewport
    assert rail_right < viewport_width * 0.40, (
        f"Rail extends to x={rail_right:.0f}px, which is "
        f"{100 * rail_right / viewport_width:.0f}% of the viewport width. "
        "Expected the rail to occupy at most 40% of a 1280px viewport. "
        "ADR-008 fixes the rail track at minmax(220px, 18rem)."
    )


# ---------------------------------------------------------------------------
# AC-2 — Mandatory / Optional headings use the designation palette
# ---------------------------------------------------------------------------


def test_mandatory_heading_uses_designation_palette(page: Page, live_server: str) -> None:
    """
    AC-2: The "Mandatory" section heading must use the designation-mandatory
    color palette (greenish: #d4ecd4 background or #2a5a2a text per ADR-008),
    NOT the same styling as the "Optional" heading.

    ADR-008: "The first .nav-section-label (rendered with text 'Mandatory')
    gets a green left-border or text accent matching the designation-mandatory
    palette."

    Strategy: get the computed style of the Mandatory heading and the Optional
    heading.  At minimum they must differ in color or border-color — the M/O
    distinction must be visually encoded, not just textually present.

    NOTE: This test will FAIL until base.css provides the palette rules.
    With no CSS, both headings render with identical default browser styling.

    Trace: TASK-003 AC-1 "Mandatory section is visually distinguishable from
    Optional section"; ADR-008 M/O palette commitment.
    """
    page.goto(live_server + "/")
    page.wait_for_load_state("networkidle")

    # Both headings share the class .nav-section-label
    mandatory_heading = page.locator(".nav-section-label", has_text="Mandatory").first
    optional_heading = page.locator(".nav-section-label", has_text="Optional").first

    expect(mandatory_heading).to_be_visible()
    expect(optional_heading).to_be_visible()

    # Get computed border-left-color for each heading (ADR-008 commits to a
    # left-border or text-color accent for the distinction)
    mandatory_border = mandatory_heading.evaluate(
        "el => window.getComputedStyle(el).getPropertyValue('border-left-color')"
    )
    optional_border = optional_heading.evaluate(
        "el => window.getComputedStyle(el).getPropertyValue('border-left-color')"
    )
    mandatory_color = mandatory_heading.evaluate(
        "el => window.getComputedStyle(el).getPropertyValue('color')"
    )
    optional_color = optional_heading.evaluate(
        "el => window.getComputedStyle(el).getPropertyValue('color')"
    )
    mandatory_bg = mandatory_heading.evaluate(
        "el => window.getComputedStyle(el).getPropertyValue('background-color')"
    )
    optional_bg = optional_heading.evaluate(
        "el => window.getComputedStyle(el).getPropertyValue('background-color')"
    )

    # At least one visual property must differ between Mandatory and Optional.
    # If no CSS rules are applied (the pre-implementation state), all computed
    # styles will be identical browser defaults — this assertion will FAIL.
    colors_differ = (
        mandatory_border != optional_border
        or mandatory_color != optional_color
        or mandatory_bg != optional_bg
    )

    assert colors_differ, (
        "The 'Mandatory' and 'Optional' rail headings have identical computed styles: "
        f"border-left-color: mandatory={mandatory_border!r}, optional={optional_border!r}; "
        f"color: mandatory={mandatory_color!r}, optional={optional_color!r}; "
        f"background-color: mandatory={mandatory_bg!r}, optional={optional_bg!r}. "
        "ADR-008: the rail headings must use the designation palette to make "
        "M/O visually distinguishable. Without base.css, both headings render "
        "identically (browser defaults) — this test is red until CSS is in place."
    )


def test_mandatory_heading_is_semantically_a_heading(page: Page, live_server: str) -> None:
    """
    AC-2 structural variant: the "Mandatory" label must be an h2 element
    (as committed by the template _nav_rail.html.j2) so it renders with
    heading semantics, not as a styled div.

    Trace: TASK-003 AC-1; ADR-006 (rail template commits to h2 for labels).
    """
    page.goto(live_server + "/")
    page.wait_for_load_state("networkidle")

    # role="heading" is the ARIA role for h2 elements
    mandatory_heading = page.get_by_role("heading", name="Mandatory")
    optional_heading = page.get_by_role("heading", name="Optional")

    expect(mandatory_heading).to_be_visible()
    expect(optional_heading).to_be_visible()


# ---------------------------------------------------------------------------
# AC-3 — Chapter rows are clickable links that navigate correctly
# ---------------------------------------------------------------------------


def test_chapter_links_are_visible_and_clickable(page: Page, live_server: str) -> None:
    """
    AC-3: Chapter rows render as clickable links with visible affordance.

    Strategy: find all anchor elements inside .nav-chapter-item, assert each
    is visible. Click one and assert navigation to /lecture/{id} occurs.

    Trace: TASK-003 AC-1 "Chapter rows render as clickable links with visible
    hover/focus affordance"; ADR-006 (each row links to /lecture/{id}).
    """
    page.goto(live_server + "/")
    page.wait_for_load_state("networkidle")

    # Collect all nav chapter links (healthy rows)
    chapter_links = page.locator(".nav-chapter-item a")
    count = chapter_links.count()
    assert count >= 1, (
        f"Found {count} chapter links in .nav-chapter-item elements. "
        "Expected at least 1 from the live content corpus. "
        "ADR-006: every chapter in the corpus must have a navigation row."
    )

    # Every link must be visible
    for i in range(count):
        link = chapter_links.nth(i)
        expect(link).to_be_visible()

    # Click the first link and assert navigation to /lecture/
    first_href = chapter_links.first.get_attribute("href")
    assert first_href is not None, "First chapter link has no href attribute."
    assert "/lecture/" in first_href, (
        f"First chapter link href={first_href!r} does not contain '/lecture/'. "
        "ADR-006: chapter links must target GET /lecture/{chapter_id}."
    )

    chapter_links.first.click()
    page.wait_for_url("**/lecture/**")
    # We successfully navigated to a lecture page
    assert "/lecture/" in page.url, (
        f"After clicking a chapter link, URL is {page.url!r}. "
        "Expected navigation to /lecture/{chapter_id}."
    )


def test_nav_rail_links_have_hover_style(page: Page, live_server: str) -> None:
    """
    AC-3 (hover affordance): chapter links must have a different computed style
    when hovered compared to resting state — this confirms a hover rule exists
    in base.css.

    ADR-008 commits that the implementer "may add a small number of utility /
    pseudo-state classes if needed (e.g., .nav-chapter-item:hover)."

    Strategy: compare background-color before and after hover on the first
    nav chapter link.

    NOTE: This tests :hover state. Without base.css, the before/after will be
    identical (browser default — no hover style). This assertion will FAIL
    until base.css provides a :hover rule for .nav-chapter-item a (or similar).

    Trace: TASK-003 AC-1 "visible hover/focus affordance"; ADR-008.
    """
    page.goto(live_server + "/")
    page.wait_for_load_state("networkidle")

    first_link = page.locator(".nav-chapter-item a").first
    expect(first_link).to_be_visible()

    # Capture resting style
    resting_bg = first_link.evaluate(
        "el => window.getComputedStyle(el).getPropertyValue('background-color')"
    )
    resting_color = first_link.evaluate(
        "el => window.getComputedStyle(el).getPropertyValue('color')"
    )

    # Hover
    first_link.hover()
    # Small wait for CSS transition
    page.wait_for_timeout(150)

    hovered_bg = first_link.evaluate(
        "el => window.getComputedStyle(el).getPropertyValue('background-color')"
    )
    hovered_color = first_link.evaluate(
        "el => window.getComputedStyle(el).getPropertyValue('color')"
    )

    # At least one property must change on hover
    hover_changes_something = (
        resting_bg != hovered_bg or resting_color != hovered_color
    )
    assert hover_changes_something, (
        "Nav chapter link has identical computed styles before and after hover: "
        f"background-color: resting={resting_bg!r}, hovered={hovered_bg!r}; "
        f"color: resting={resting_color!r}, hovered={hovered_color!r}. "
        "ADR-008: chapter links must have a hover affordance (.nav-chapter-item:hover "
        "or similar CSS rule). This test is red until base.css provides a hover rule."
    )


# ---------------------------------------------------------------------------
# AC-4 — Lecture page has same rail in same left-hand position
# ---------------------------------------------------------------------------


def test_lecture_page_rail_is_on_left(page: Page, live_server: str) -> None:
    """
    AC-4: On a Lecture page the same rail appears in the same left-hand
    position as on GET /.

    Strategy: GET /lecture/ch-01-cpp-refresher, assert the rail bounding box
    has the same left-column position as on the landing page.

    Trace: TASK-003 AC-2 "the same rail appears in the same left-hand position
    with the same styling as on GET /".
    """
    page.set_viewport_size({"width": 1280, "height": 900})

    # Landing page rail position
    page.goto(live_server + "/")
    page.wait_for_load_state("networkidle")
    landing_rail = page.locator("nav.lecture-rail")
    expect(landing_rail).to_be_visible()
    landing_box = landing_rail.bounding_box()

    # Lecture page rail position
    page.goto(live_server + "/lecture/ch-01-cpp-refresher")
    page.wait_for_load_state("networkidle")
    lecture_rail = page.locator("nav.lecture-rail")
    expect(lecture_rail).to_be_visible()
    lecture_box = lecture_rail.bounding_box()

    assert landing_box is not None, "Landing page rail has no bounding box."
    assert lecture_box is not None, "Lecture page rail has no bounding box."

    # Rail left edge must be in the same position on both pages (within 5px)
    assert abs(landing_box["x"] - lecture_box["x"]) < 5, (
        f"Rail x-position differs: landing={landing_box['x']:.0f}px, "
        f"lecture={lecture_box['x']:.0f}px. "
        "ADR-008: the same base.css layout rules apply on both surfaces; "
        "the rail must be in the same position on every page."
    )


def test_lecture_page_body_designation_badge_preserved(page: Page, live_server: str) -> None:
    """
    AC-4 regression: adding the rail must NOT regress the Lecture body's
    existing styling — specifically the designation badge.

    The `.designation-badge` element (Mandatory/Optional) must be visible
    within the `.lecture-header` block, not hidden by the new layout.

    Trace: TASK-003 AC-2 "Lecture body's existing styling … is preserved";
    ADR-008 "TASK-001's visual treatments must be preserved."
    """
    page.goto(live_server + "/lecture/ch-01-cpp-refresher")
    page.wait_for_load_state("networkidle")

    badge = page.locator(".lecture-header .designation-badge")
    expect(badge).to_be_visible()

    # The badge must be to the RIGHT of the rail (inside the main column, not
    # inside the rail itself)
    badge_box = badge.bounding_box()
    rail_box = page.locator("nav.lecture-rail").bounding_box()

    assert badge_box is not None, ".designation-badge has no bounding box."
    assert rail_box is not None, "nav.lecture-rail has no bounding box."

    rail_right = rail_box["x"] + rail_box["width"]
    assert badge_box["x"] > rail_right - 10, (
        f"Designation badge x={badge_box['x']:.0f}px is not to the right of "
        f"the rail's right edge ({rail_right:.0f}px). "
        "The badge should be inside the main content column, not inside the rail. "
        "ADR-008: TASK-001's visual treatments must be preserved."
    )


# ---------------------------------------------------------------------------
# AC-5 — .nav-chapter-error rows are visually distinct
# ---------------------------------------------------------------------------


def test_error_row_is_visually_distinct_from_healthy_rows(
    page: Page, live_server: str
) -> None:
    """
    AC-5: A `.nav-chapter-error` row must be visually distinct from healthy
    `.nav-chapter-item` rows (without the error class).

    ADR-008: "The CSS rule for .nav-chapter-error makes the row visually
    distinct from healthy rows via a warning-colored left-border (matching
    .callout-warnbox palette: #cfae87 border, #f5eddf background tint)."

    Strategy: this test requires a fixture corpus with a missing-title chapter.
    It navigates to GET / with the FIXTURE_MISSING_TITLE corpus (via the live
    server).  BUT since the live server uses the real content/latex/ root, not
    a fixture, this test inspects whether the error class produces a visually
    different computed style.

    Alternative strategy used here: if an error row exists on the live page,
    compare its styles to a healthy row.  If no error row exists (clean corpus),
    we use a different assertion: verify that the CSS rule for .nav-chapter-error
    exists and produces a different background than a default .nav-chapter-item.

    Trace: TASK-003 AC-3; ADR-007 per-row fail-loudly; ADR-008 error treatment.
    """
    page.goto(live_server + "/")
    page.wait_for_load_state("networkidle")

    # Check if there are any error rows in the live corpus
    error_rows = page.locator(".nav-chapter-error")
    error_count = error_rows.count()

    # Check if there are any healthy nav-chapter-item rows (without error class)
    healthy_rows = page.locator(".nav-chapter-item:not(.nav-chapter-error)")
    healthy_count = healthy_rows.count()

    if error_count > 0 and healthy_count > 0:
        # Both exist: compare their background or border styles directly
        error_bg = error_rows.first.evaluate(
            "el => window.getComputedStyle(el).getPropertyValue('background-color')"
        )
        healthy_bg = healthy_rows.first.evaluate(
            "el => window.getComputedStyle(el).getPropertyValue('background-color')"
        )
        error_border = error_rows.first.evaluate(
            "el => window.getComputedStyle(el).getPropertyValue('border-left-color')"
        )
        healthy_border = healthy_rows.first.evaluate(
            "el => window.getComputedStyle(el).getPropertyValue('border-left-color')"
        )

        visually_distinct = (
            error_bg != healthy_bg or error_border != healthy_border
        )
        assert visually_distinct, (
            "A .nav-chapter-error row has identical computed styles to a healthy "
            f".nav-chapter-item row: "
            f"background-color: error={error_bg!r}, healthy={healthy_bg!r}; "
            f"border-left-color: error={error_border!r}, healthy={healthy_border!r}. "
            "ADR-008: error rows must use the warning-palette (warnbox colors) "
            "to visually signal the failure. This test is red until base.css "
            "provides the .nav-chapter-error rule."
        )
    else:
        # No error rows in live corpus — test that the CSS rule exists by
        # injecting a temporary .nav-chapter-error element and checking its style
        page.evaluate("""() => {
            const li = document.createElement('li');
            li.className = 'nav-chapter-item nav-chapter-error';
            li.id = '_test_error_row';
            li.innerHTML = '<a href="#">Test Error Row</a>';
            const list = document.querySelector('.nav-chapter-list');
            if (list) list.appendChild(li);
        }""")

        injected = page.locator("#_test_error_row")
        if injected.count() > 0:
            error_bg = injected.evaluate(
                "el => window.getComputedStyle(el).getPropertyValue('background-color')"
            )
            # The injected error row's background must differ from the transparent default
            # if base.css provides the .nav-chapter-error rule.
            # Default browser background is "rgba(0, 0, 0, 0)" or "transparent".
            # ADR-008 commits to #f5eddf background tint.
            default_transparent = (
                error_bg in ("rgba(0, 0, 0, 0)", "transparent")
            )
            assert not default_transparent, (
                f"Injected .nav-chapter-error element has background-color={error_bg!r}, "
                "which is the browser default (transparent). "
                "ADR-008: .nav-chapter-error must have a non-default background "
                "(warning-palette tint: #f5eddf or similar). "
                "This test is red until base.css provides the .nav-chapter-error rule."
            )
        else:
            pytest.fail(
                "Could not inject a test .nav-chapter-error element — no "
                ".nav-chapter-list found on the page. Cannot verify error-row styling."
            )


# ---------------------------------------------------------------------------
# AC-6 — .nav-chapter-empty rows are muted / de-emphasized
# ---------------------------------------------------------------------------


def test_empty_state_row_is_muted(page: Page, live_server: str) -> None:
    """
    AC-6: The `.nav-chapter-empty` "(none)" row must be styled as muted /
    de-emphasized (lower contrast or italicized) compared to healthy rows.

    ADR-008: "The .nav-chapter-empty '(none)' row is rendered in a muted
    color (lower contrast than healthy rows) and italicized."

    Strategy: if a .nav-chapter-empty row exists in the live corpus, compare
    its computed color and font-style to a healthy .nav-chapter-item.  If not
    present in live corpus, inject one and check its computed styles.

    Trace: TASK-003 AC-4; ADR-008 empty-state treatment.
    """
    page.goto(live_server + "/")
    page.wait_for_load_state("networkidle")

    empty_rows = page.locator(".nav-chapter-empty")
    empty_count = empty_rows.count()

    if empty_count > 0:
        empty_color = empty_rows.first.evaluate(
            "el => window.getComputedStyle(el).getPropertyValue('color')"
        )
        empty_font_style = empty_rows.first.evaluate(
            "el => window.getComputedStyle(el).getPropertyValue('font-style')"
        )

        # The row must be italic (ADR-008 commits to italicized empty state)
        assert empty_font_style == "italic", (
            f"The .nav-chapter-empty row has font-style={empty_font_style!r}, "
            "expected 'italic'. ADR-008: empty-state rows must be italicized "
            "to signal structural emptiness without competing for visual attention. "
            "This test is red until base.css provides the .nav-chapter-empty rule."
        )
    else:
        # Inject a test empty row
        page.evaluate("""() => {
            const li = document.createElement('li');
            li.className = 'nav-chapter-empty';
            li.id = '_test_empty_row';
            li.textContent = '(none)';
            const list = document.querySelector('.nav-chapter-list');
            if (list) list.appendChild(li);
        }""")

        injected = page.locator("#_test_empty_row")
        if injected.count() > 0:
            font_style = injected.evaluate(
                "el => window.getComputedStyle(el).getPropertyValue('font-style')"
            )
            assert font_style == "italic", (
                f"Injected .nav-chapter-empty element has font-style={font_style!r}, "
                "expected 'italic'. ADR-008: empty-state rows must be italicized. "
                "This test is red until base.css provides the .nav-chapter-empty rule."
            )
        else:
            pytest.fail(
                "Could not inject a .nav-chapter-empty test element — no "
                ".nav-chapter-list found. Cannot verify empty-state styling."
            )


# ---------------------------------------------------------------------------
# AC-7 — Page layout uses CSS Grid (layout mechanism assertion)
# ---------------------------------------------------------------------------


def test_page_layout_uses_css_grid(page: Page, live_server: str) -> None:
    """
    AC-7: The `.page-layout` container must use `display: grid` to produce
    the two-column layout.

    ADR-008: "The two-column layout … is implemented with CSS Grid:
    .page-layout { display: grid; grid-template-columns: minmax(220px, 18rem)
    minmax(0, 1fr); min-height: 100vh; }"

    Without base.css, `.page-layout` has the browser default `display: block`,
    which stacks the children vertically (the rail on top, main content below).
    This test is red until base.css sets `display: grid` on `.page-layout`.

    Trace: TASK-003 AC-1; ADR-008 "Page layout mechanism — CSS Grid."
    """
    page.goto(live_server + "/")
    page.wait_for_load_state("networkidle")

    layout_display = page.locator(".page-layout").evaluate(
        "el => window.getComputedStyle(el).getPropertyValue('display')"
    )

    assert layout_display == "grid", (
        f".page-layout has display={layout_display!r}, expected 'grid'. "
        "ADR-008: the page layout mechanism is CSS Grid. "
        "Without base.css, .page-layout defaults to display:block (stacked layout). "
        "This test is red until base.css is in place."
    )


def test_page_layout_grid_has_two_column_tracks(page: Page, live_server: str) -> None:
    """
    AC-7 (deeper): the CSS Grid must have two column tracks, not one.

    Strategy: get `grid-template-columns` from the computed style.
    A single-column or no-grid layout produces a single track value.
    A two-column layout produces two space-separated values.

    ADR-008 commits to `grid-template-columns: minmax(220px, 18rem) minmax(0, 1fr)`.

    Trace: TASK-003 AC-1; ADR-008.
    """
    page.goto(live_server + "/")
    page.wait_for_load_state("networkidle")

    grid_cols = page.locator(".page-layout").evaluate(
        "el => window.getComputedStyle(el).getPropertyValue('grid-template-columns')"
    )

    # grid-template-columns for a 2-column layout resolves to two pixel values
    # (e.g., "288px 992px" on a 1280px viewport minus scrollbar).
    # For a 1-column or no-grid layout it resolves to "none" or a single value.
    parts = grid_cols.split()
    assert len(parts) >= 2, (
        f".page-layout grid-template-columns resolves to {grid_cols!r}, "
        f"which has {len(parts)} token(s). Expected 2 (one per column). "
        "ADR-008: grid-template-columns must be 'minmax(220px, 18rem) minmax(0, 1fr)' "
        "(resolves to 2 pixel values at runtime). "
        "This test is red until base.css sets the grid-template-columns property."
    )


# ---------------------------------------------------------------------------
# Boundary / edge: both designation sections are present and correctly labeled
# ---------------------------------------------------------------------------


def test_both_designation_groups_present_on_landing_page(
    page: Page, live_server: str
) -> None:
    """
    Manifest §7 / ADR-006: Both "Mandatory" and "Optional" h2 headings must
    appear in the rail on GET /.

    Trace: Manifest §7 "Mandatory and Optional are separable in every
    learner-facing surface"; ADR-006; TASK-003 AC-1.
    """
    page.goto(live_server + "/")
    page.wait_for_load_state("networkidle")

    expect(page.get_by_role("heading", name="Mandatory")).to_be_visible()
    expect(page.get_by_role("heading", name="Optional")).to_be_visible()


def test_mandatory_heading_appears_before_optional_heading(
    page: Page, live_server: str
) -> None:
    """
    Boundary: Mandatory heading must appear before Optional heading in document
    order (Mandatory section is rendered first in _nav_rail.html.j2).

    Trace: ADR-006 template order; manifest §7.
    """
    page.goto(live_server + "/")
    page.wait_for_load_state("networkidle")

    headings = page.locator(".nav-section-label")
    count = headings.count()
    assert count == 2, (
        f"Expected exactly 2 .nav-section-label headings, found {count}. "
        "ADR-006: the rail always renders exactly two groups (Mandatory and Optional)."
    )

    first_text = headings.nth(0).text_content()
    second_text = headings.nth(1).text_content()

    assert "Mandatory" in (first_text or ""), (
        f"First .nav-section-label is '{first_text}', expected 'Mandatory'. "
        "The Mandatory section must appear before Optional in document order."
    )
    assert "Optional" in (second_text or ""), (
        f"Second .nav-section-label is '{second_text}', expected 'Optional'. "
        "The Optional section must appear after Mandatory."
    )


# ---------------------------------------------------------------------------
# Performance: the whole-page load completes within a generous budget
# ---------------------------------------------------------------------------


def test_landing_page_loads_within_time_budget(page: Page, live_server: str) -> None:
    """
    Performance: GET / must complete (DOM content loaded) within 5 seconds.

    This is a generous budget for a local server with a small corpus — it
    catches pathological regressions (infinite loop in discovery, O(n^2) in
    nav-group rendering) rather than micro-benchmarking.

    Trace: TASK-003 AC (usability — an unstyled wall of text is bad; a page
    that takes 30 seconds to load is worse); ADR-007 request-time scan.
    """
    import time

    start = time.monotonic()
    page.goto(live_server + "/", wait_until="domcontentloaded")
    elapsed = time.monotonic() - start

    assert elapsed < 5.0, (
        f"GET / took {elapsed:.2f}s to reach DOMContentLoaded. "
        "Expected under 5s for a local server with a small corpus. "
        "This may indicate a pathological scaling issue in chapter discovery."
    )
