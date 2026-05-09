"""
Playwright DOM-content tests migrated from tests/test_task001_rendering_fidelity.py.

Per ADR-010 "Migration scope":
  All callout-assertion, math-passthrough, and lstlisting-content tests
  migrate to Playwright (all interrogate rendered HTML for content fidelity).

The original tests assert against `ch01_lecture_response.text` (TestClient).
These Playwright tests assert against the live-rendered DOM.

Tests migrated:
  TestCalloutRendering:
  - test_callout_env_produces_data_callout_attribute (parametrized per env)
  - test_callout_env_count_matches_source (parametrized per env)
  - test_callout_types_are_distinguishable_from_each_other

  TestNoRawLatexLeak:
  - test_specific_macro_not_leaked_in_prose (parametrized)
  - test_generic_macro_pattern_not_leaked_in_prose
  - test_no_backslash_begin_in_prose
  - test_no_backslash_end_in_prose
  - test_pre_code_blocks_exempt_from_latex_leak_check

  TestCodeListingRendering:
  - test_pre_code_block_count_at_least_source_count
  - test_first_lstlisting_content_inside_pre_code
  - test_mid_document_lstlisting_content_inside_pre_code
  - test_lstlisting_content_not_in_prose

  TestMathPassthrough:
  - test_inline_math_o1_survives
  - test_display_math_survives
  - test_math_delimiters_not_stripped_as_raw_latex_leak

  TestUnknownNodeWarning — these are UNIT tests (call the parser function
  directly); they do NOT assert against rendered DOM.  Per ADR-010 they stay
  in pytest because they are not DOM-content assertions — they test a Python
  callable, not a rendered page.  They remain in test_task001_rendering_fidelity.py.

pytestmark registers all tests under task("TASK-001").
"""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.task("TASK-001")

LECTURE_URL_PATH = "/lecture/ch-01-cpp-refresher"

# Source-derived constants (same as original file)
CALLOUT_COUNTS = {
    "ideabox": 27,
    "defnbox": 14,
    "notebox": 12,
    "warnbox": 29,
    "examplebox": 29,
}
CALLOUT_ENVS = list(CALLOUT_COUNTS.keys())
LSTLISTING_COUNT = 36
LSTLISTING_FIRST_CONTENT = "myArray[2]"
LSTLISTING_MID_CONTENT = "oldestPeople"

_FORBIDDEN_MACRO_PATTERNS = [
    r"\\section\{",
    r"\\subsection\{",
    r"\\textbf\{",
    r"\\textit\{",
    r"\\emph\{",
    r"\\begin\{",
    r"\\end\{",
    r"\\input\{",
    r"\\label\{",
    r"\\ref\{",
    r"\\cite\{",
]

_GENERIC_MACRO_PATTERN = r"\\[A-Za-z]+\{"


# ---------------------------------------------------------------------------
# Gap 1 — Callout environments render as distinguishable HTML blocks
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("env_name", CALLOUT_ENVS)
def test_callout_env_produces_data_callout_attribute(
    page: Page, live_server: str, env_name: str
) -> None:
    """
    ADR-003: each callout environment must emit an element with
    data-callout="{env_name}" in the rendered DOM.

    Trace: TASK-001 rendering fidelity Gap 1; ADR-003; ADR-010 migration.
    """
    page.goto(live_server + LECTURE_URL_PATH)
    page.wait_for_load_state("networkidle")

    callout_elements = page.locator(f'[data-callout="{env_name}"]')
    count = callout_elements.count()
    assert count >= 1, (
        f"No element with data-callout='{env_name}' found in rendered DOM. "
        "ADR-003: every callout environment must emit a styled block element."
    )


@pytest.mark.parametrize("env_name,expected_count", CALLOUT_COUNTS.items())
def test_callout_env_count_matches_source(
    page: Page, live_server: str, env_name: str, expected_count: int
) -> None:
    """
    ADR-003: every callout instance in the source must produce a block — none
    silently dropped.

    Trace: TASK-001 rendering fidelity Gap 1; ADR-003; ADR-010 migration.
    """
    page.goto(live_server + LECTURE_URL_PATH)
    page.wait_for_load_state("networkidle")

    count = page.locator(f'[data-callout="{env_name}"]').count()
    assert count >= expected_count, (
        f"Expected at least {expected_count} data-callout='{env_name}' elements "
        f"in rendered DOM, found {count}. "
        "ADR-003: every callout instance must produce an HTML block."
    )


def test_callout_types_are_distinguishable_from_each_other(
    page: Page, live_server: str
) -> None:
    """
    ADR-003: all five distinct callout types must be present in the DOM.

    Trace: TASK-001 rendering fidelity Gap 1; ADR-003; ADR-010 migration.
    """
    page.goto(live_server + LECTURE_URL_PATH)
    page.wait_for_load_state("networkidle")

    missing = []
    for env_name in CALLOUT_ENVS:
        if page.locator(f'[data-callout="{env_name}"]').count() == 0:
            missing.append(env_name)

    assert missing == [], (
        f"These callout types are missing from the rendered DOM: {missing}. "
        "ADR-003 requires each distinct environment to produce a styled block."
    )


# ---------------------------------------------------------------------------
# Gap 2 — No leaked raw LaTeX in rendered HTML
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("macro_pattern", _FORBIDDEN_MACRO_PATTERNS)
def test_specific_macro_not_leaked_in_prose(
    page: Page, live_server: str, macro_pattern: str
) -> None:
    """
    ADR-003: structural LaTeX macros must not appear in the rendered DOM prose
    (outside <pre>/<code> and math regions).

    Trace: TASK-001 rendering fidelity Gap 2; ADR-003; ADR-010 migration.
    """
    page.goto(live_server + LECTURE_URL_PATH)
    page.wait_for_load_state("networkidle")

    html = page.content()

    # Remove <pre>/<code> blocks and math spans from the HTML before checking
    safe_removed = re.sub(
        r"<pre[\s>].*?</pre>|<code[\s>].*?</code>",
        "<!-- SAFE -->",
        html,
        flags=re.DOTALL | re.IGNORECASE,
    )
    safe_removed = re.sub(
        r'<span[^>]*class="[^"]*math[^"]*"[^>]*>.*?</span>',
        "<!-- SAFE -->",
        safe_removed,
        flags=re.DOTALL | re.IGNORECASE,
    )
    # Remove inline and display math delimiters
    safe_removed = re.sub(r"\$[^$]+?\$", "<!-- SAFE -->", safe_removed)
    safe_removed = re.sub(r"\\\[.*?\\\]", "<!-- SAFE -->", safe_removed, flags=re.DOTALL)

    matches = re.findall(macro_pattern, safe_removed)
    assert matches == [], (
        f"Raw LaTeX pattern '{macro_pattern}' found {len(matches)} time(s) in "
        "rendered prose HTML (outside pre/code and math regions). "
        "ADR-003: pylatexenc must consume structural macros, not pass them through."
    )


def test_generic_macro_pattern_not_leaked_in_prose(
    page: Page, live_server: str
) -> None:
    """
    ADR-003 catch-all: no \\word{ pattern should survive in prose HTML.

    Trace: TASK-001 rendering fidelity Gap 2; ADR-003; ADR-010 migration.
    """
    page.goto(live_server + LECTURE_URL_PATH)
    page.wait_for_load_state("networkidle")

    html = page.content()
    # Strip safe regions
    safe_removed = re.sub(
        r"<pre[\s>].*?</pre>|<code[\s>].*?</code>",
        "<!-- SAFE -->",
        html,
        flags=re.DOTALL | re.IGNORECASE,
    )
    safe_removed = re.sub(
        r'<span[^>]*class="[^"]*math[^"]*"[^>]*>.*?</span>',
        "<!-- SAFE -->",
        safe_removed,
        flags=re.DOTALL | re.IGNORECASE,
    )
    safe_removed = re.sub(r"\$[^$]+?\$", "<!-- SAFE -->", safe_removed)
    safe_removed = re.sub(r"\\\[.*?\\\]", "<!-- SAFE -->", safe_removed, flags=re.DOTALL)

    matches = re.findall(_GENERIC_MACRO_PATTERN, safe_removed)
    assert matches == [], (
        f"Possible raw LaTeX macro(s) in prose HTML: {matches[:10]!r}. "
        "ADR-003: unrecognized nodes must not pass through as plain text."
    )


def test_no_backslash_begin_in_prose(page: Page, live_server: str) -> None:
    """
    Specific regression: \\begin{ in prose = unparsed environment.

    Trace: TASK-001 rendering fidelity Gap 2; ADR-003; ADR-010 migration.
    """
    page.goto(live_server + LECTURE_URL_PATH)
    page.wait_for_load_state("networkidle")

    html = page.content()
    safe_removed = re.sub(
        r"<pre[\s>].*?</pre>|<code[\s>].*?</code>",
        "<!-- SAFE -->",
        html,
        flags=re.DOTALL | re.IGNORECASE,
    )
    safe_removed = re.sub(r"\$[^$]+?\$", "<!-- SAFE -->", safe_removed)
    safe_removed = re.sub(r"\\\[.*?\\\]", "<!-- SAFE -->", safe_removed, flags=re.DOTALL)

    assert r"\begin{" not in safe_removed, (
        r"Raw '\begin{' in rendered prose HTML (outside pre/code/math). "
        "ADR-003: environments must be parsed, not passed through."
    )


def test_no_backslash_end_in_prose(page: Page, live_server: str) -> None:
    """
    Mirror: \\end{ in prose = unparsed environment close.

    Trace: TASK-001 rendering fidelity Gap 2; ADR-003; ADR-010 migration.
    """
    page.goto(live_server + LECTURE_URL_PATH)
    page.wait_for_load_state("networkidle")

    html = page.content()
    safe_removed = re.sub(
        r"<pre[\s>].*?</pre>|<code[\s>].*?</code>",
        "<!-- SAFE -->",
        html,
        flags=re.DOTALL | re.IGNORECASE,
    )
    safe_removed = re.sub(r"\$[^$]+?\$", "<!-- SAFE -->", safe_removed)
    safe_removed = re.sub(r"\\\[.*?\\\]", "<!-- SAFE -->", safe_removed, flags=re.DOTALL)

    assert r"\end{" not in safe_removed, (
        r"Raw '\end{' in rendered prose HTML (outside pre/code/math). "
        "ADR-003: environments must be parsed, not passed through."
    )


def test_pre_code_blocks_exempt_from_latex_leak_check(
    page: Page, live_server: str
) -> None:
    """
    Sanity: confirms code blocks exist in rendered HTML (the exemption logic is
    meaningful and not vacuous).

    Trace: TASK-001 rendering fidelity Gap 2; ADR-003; ADR-010 migration.
    """
    page.goto(live_server + LECTURE_URL_PATH)
    page.wait_for_load_state("networkidle")

    pre_blocks = page.locator("pre")
    assert pre_blocks.count() >= 1, (
        "No <pre> blocks found in rendered HTML. "
        "Cannot verify that the latex-leak exemption for code listings is active."
    )


# ---------------------------------------------------------------------------
# Gap 3 — Code listings render as <pre><code> blocks
# ---------------------------------------------------------------------------


def test_pre_code_block_count_at_least_source_count(
    page: Page, live_server: str
) -> None:
    """
    ADR-003: 36 lstlisting pairs in the source → at least 36 <pre><code> blocks.

    Trace: TASK-001 rendering fidelity Gap 3; ADR-003; ADR-010 migration.
    """
    page.goto(live_server + LECTURE_URL_PATH)
    page.wait_for_load_state("networkidle")

    html = page.content()
    pre_code_blocks = re.findall(
        r"<pre[^>]*>\s*<code[^>]*>.*?</code>\s*</pre>",
        html,
        flags=re.DOTALL | re.IGNORECASE,
    )
    assert len(pre_code_blocks) >= LSTLISTING_COUNT, (
        f"Expected at least {LSTLISTING_COUNT} <pre><code> blocks, "
        f"found {len(pre_code_blocks)}. "
        "ADR-003: every lstlisting environment must become a <pre><code> block."
    )


def test_first_lstlisting_content_inside_pre_code(
    page: Page, live_server: str
) -> None:
    """
    ADR-003: the first lstlisting block's content must appear inside <pre>/<code>.

    Trace: TASK-001 rendering fidelity Gap 3; ADR-003; ADR-010 migration.
    """
    page.goto(live_server + LECTURE_URL_PATH)
    page.wait_for_load_state("networkidle")

    # Find all pre/code blocks and check if any contain the expected content
    html = page.content()
    pre_blocks = re.findall(
        r"<pre[^>]*>.*?</pre>",
        html,
        flags=re.DOTALL | re.IGNORECASE,
    )
    found_in_code = any(LSTLISTING_FIRST_CONTENT in block for block in pre_blocks)
    assert found_in_code, (
        f"Expected '{LSTLISTING_FIRST_CONTENT}' to appear inside a <pre> block. "
        "ADR-003: lstlisting content must be human-readable in a code block."
    )


def test_mid_document_lstlisting_content_inside_pre_code(
    page: Page, live_server: str
) -> None:
    """
    ADR-003: mid-document lstlisting content must appear inside <pre>/<code>.

    Trace: TASK-001 rendering fidelity Gap 3; ADR-003; ADR-010 migration.
    """
    page.goto(live_server + LECTURE_URL_PATH)
    page.wait_for_load_state("networkidle")

    html = page.content()
    pre_blocks = re.findall(
        r"<pre[^>]*>.*?</pre>",
        html,
        flags=re.DOTALL | re.IGNORECASE,
    )
    found_in_code = any(LSTLISTING_MID_CONTENT in block for block in pre_blocks)
    assert found_in_code, (
        f"Expected '{LSTLISTING_MID_CONTENT}' to appear inside a <pre> block. "
        "ADR-003: lstlisting content must not be stripped or treated as prose."
    )


def test_lstlisting_content_not_in_prose(page: Page, live_server: str) -> None:
    """
    Complementary: the first lstlisting content must NOT appear outside <pre>/<code>.

    Trace: TASK-001 rendering fidelity Gap 3; ADR-003; ADR-010 migration.
    """
    page.goto(live_server + LECTURE_URL_PATH)
    page.wait_for_load_state("networkidle")

    html = page.content()
    # Strip all pre/code regions
    prose_only = re.sub(
        r"<pre[^>]*>.*?</pre>|<code[^>]*>.*?</code>",
        "<!-- CODE_BLOCK -->",
        html,
        flags=re.DOTALL | re.IGNORECASE,
    )
    assert LSTLISTING_FIRST_CONTENT not in prose_only, (
        f"'{LSTLISTING_FIRST_CONTENT}' found outside a <pre>/<code> block. "
        "C++ code from lstlisting must not be rendered as prose. ADR-003."
    )


# ---------------------------------------------------------------------------
# Bonus 4 — Math expressions survive in MathJax-renderable form
# ---------------------------------------------------------------------------


def test_inline_math_o1_survives(page: Page, live_server: str) -> None:
    """
    ADR-003: inline math $O(1)$ must survive in the HTML in MathJax-renderable form.

    Trace: TASK-001 rendering fidelity Bonus 4; ADR-003; ADR-010 migration.

    By the time `page.content()` is captured (after `networkidle`), MathJax v3
    has typically replaced the literal `$O(1)$` with an `<mjx-container>` element
    containing rendered math.  This test now accepts any of the three valid
    states the parser+MathJax pipeline can produce: (a) the literal `$O(1)$`
    delimiters survived (MathJax not yet run), (b) MathJax produced an
    `<mjx-container>` whose data-attributes or descendant text references O(1),
    or (c) the legacy `<span class="math">…O(1)…</span>` shape from an earlier
    rendering convention.  The assertion's intent is "the parser did not eat
    the inline math" — all three states satisfy that intent.
    """
    page.goto(live_server + LECTURE_URL_PATH)
    page.wait_for_load_state("networkidle")

    html = page.content()
    literal_present = "$O(1)$" in html
    math_span_present = bool(
        re.search(r'<span[^>]*class="[^"]*math[^"]*"[^>]*>[^<]*O\(1\)[^<]*</span>', html)
    )
    # MathJax v3 chtml output: <mjx-container ...> ... O(1) text in nested
    # <mjx-mi>/<mjx-mn>/<mjx-mo> nodes.  Grep for an mjx-container that has
    # the literal O(1) tokens in its rendered character stream.
    mjx_container_present = bool(
        re.search(
            r"<mjx-container[^>]*>.*?O.*?\(.*?1.*?\).*?</mjx-container>",
            html,
            flags=re.DOTALL,
        )
    )
    assert literal_present or math_span_present or mjx_container_present, (
        "Inline math '$O(1)$' did not survive in the rendered HTML in a "
        "MathJax-renderable form. "
        "ADR-003: inline math must pass through with delimiters, in a math span, "
        "or as an mjx-container with the math characters present."
    )


def test_display_math_survives(page: Page, live_server: str) -> None:
    """
    ADR-003: display math \\[...\\] from source line 97 must survive in the HTML.

    Trace: TASK-001 rendering fidelity Bonus 4; ADR-003; ADR-010 migration.
    """
    page.goto(live_server + LECTURE_URL_PATH)
    page.wait_for_load_state("networkidle")

    html = page.content()
    literal_present = r"\[" in html and r"\]" in html
    math_span_present = bool(
        re.search(r'<span[^>]*class="[^"]*math-display[^"]*"[^>]*>', html, re.IGNORECASE)
    )
    assert literal_present or math_span_present, (
        r"Display math '\[...\]' did not survive in the rendered HTML. "
        r"ADR-003: display math must pass through as '\['/'\]' or in a math-display span."
    )


def test_math_delimiters_not_stripped_as_raw_latex_leak(
    page: Page, live_server: str
) -> None:
    """
    Consistency: math delimiters in the HTML must be removed by safe-region
    stripping so the generic-macro check doesn't produce false positives.

    Trace: TASK-001 rendering fidelity Bonus 4; ADR-003; ADR-010 migration.
    """
    page.goto(live_server + LECTURE_URL_PATH)
    page.wait_for_load_state("networkidle")

    html = page.content()
    if r"\[" not in html:
        return  # Display math was converted to a span form — no issue

    stripped = re.sub(r"\\\[.*?\\\]", "<!-- SAFE -->", html, flags=re.DOTALL)
    assert r"\[" not in stripped, (
        r"Display math delimiter '\[' is present in HTML but was NOT removed "
        "by safe-region stripping. The generic-macro check may produce false positives."
    )
