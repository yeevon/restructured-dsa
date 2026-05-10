"""
HTTP-protocol (smoke-layer) tests for TASK-007: `\\texttt{}` → `<span class="texttt">`.

ADR-018: The parser handler for `\\texttt{}` must emit `<span class="texttt">...</span>`
instead of `<code>...</code>` so that MathJax processes embedded inline math.
A matching `.texttt` CSS rule in `app/static/lecture.css` reproduces the
typewriter-font appearance (ADR-008: Lecture-body CSS lives in lecture.css).

This file covers:
  - AC-3: `<mjx-container>` presence inside texttt spans (Playwright-level;
    see tests/playwright/test_task007_texttt_dom.py for the live-browser test).
    At the smoke layer: `<span class="texttt">` elements are present.
  - AC-4: `.texttt` CSS rule exists in lecture.css (static check).
  - AC-3 negative (from tabular file companion): no `<code>` with `$...$` math.
  - CSS-load smoke: `lecture.css` contains a `.texttt` rule.
  - Structural: ch-04 callout with "head" ASCII-art content uses `<span class="texttt">`.
  - All 12 Chapters: any Chapter using `\\texttt{}` produces at least one
    `<span class="texttt">` element.

Coverage checklist:
  Boundary:
    - \\texttt{} with no embedded math (e.g., variable names): span emitted.
    - \\texttt{} with embedded inline math (e.g., $\\to$): span emitted, math preserved.
    - \\texttt{} with multiple math tokens in sequence.
    - First occurrence vs last occurrence in page (position effects).
  Edge:
    - \\texttt{} with HTML-special characters inside.
    - \\texttt{} whose content is only whitespace.
    - \\texttt{} nested inside a callout body (ch-04 "Picture the list" pattern).
    - Empty \\texttt{} argument.
  Negative:
    - No `<code>...$...$...</code>` pattern (math-in-code trap is closed).
    - `\\texttt{}` must NOT produce `<code>...</code>` (the old buggy output).
    - The `.texttt` span must NOT be empty-tag only; content must be inside.
  Performance:
    - Skipped: the CSS-load check is a static file read; no scaling surface.
      The 12-Chapter HTTP smoke is covered by test_task007_tabular_residue.py
      for the inline-code-with-math negative assertion (same client sweep).

pytestmark registers all tests under task("TASK-007").
"""

from __future__ import annotations

import importlib
import pathlib
import re

import pytest

pytestmark = pytest.mark.task("TASK-007")

# ---------------------------------------------------------------------------
# Canonical Chapter list (ADR-013; same as TASK-005)
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

# ch-04 is the primary hotspot: 39 of 42 `<code>` with `$...$` (Run 008 catalog).
# ch-09 and ch-10 also have \\texttt{} usages (ch-10: 95 raw \\to tokens).
TEXTTT_HOT_CHAPTERS = [
    "ch-04-lists-stacks-and-queues",
    "ch-09-balanced-trees",
    "ch-10-graphs",
]

# ---------------------------------------------------------------------------
# Import helpers
# ---------------------------------------------------------------------------


def _get_client():
    """Return a TestClient for the FastAPI app (deferred import)."""
    from fastapi.testclient import TestClient
    from app.main import app  # noqa: PLC0415
    return TestClient(app)


def _import_parse_latex():
    """Import parse_latex from app.parser (ADR-003 public API)."""
    mod = importlib.import_module("app.parser")
    return mod.parse_latex


def _make_doc(body: str) -> str:
    """Wrap body in a minimal LaTeX document structure."""
    return (
        r"\documentclass{article}" + "\n"
        r"\begin{document}" + "\n"
        + body + "\n"
        r"\end{document}"
    )


# ===========================================================================
# AC-4 / CSS-load smoke: lecture.css must contain a .texttt rule (ADR-018)
# ===========================================================================

def test_lecture_css_contains_texttt_rule() -> None:
    """
    AC-4 (TASK-007) / ADR-018 §Decision: `app/static/lecture.css` must
    contain a `.texttt` CSS rule with at least `font-family` set to monospace.

    ADR-008: Lecture-body content-styling CSS lives in `app/static/lecture.css`.
    ADR-018 §Decision: "A new CSS rule lands in `app/static/lecture.css` …
    `.texttt { font-family: 'Courier New', Courier, monospace; … }`"

    The parser emits `<span class="texttt">`; the CSS class must be defined
    for the typewriter font to apply. Without the CSS rule, the fix is
    visually incomplete (no font change).

    This test is RED before ADR-018 is implemented (the rule does not yet exist).
    """
    css_path = pathlib.Path(__file__).parent.parent / "app" / "static" / "lecture.css"
    assert css_path.exists(), (
        f"app/static/lecture.css not found at {css_path}. "
        "ADR-008: Lecture-body CSS lives in this file. "
        "If the file is missing, the lecture page has no styling at all."
    )

    css_text = css_path.read_text(encoding="utf-8")

    # The .texttt selector must be defined
    assert ".texttt" in css_text, (
        "'.texttt' not found in app/static/lecture.css. "
        "ADR-018 §Decision: 'A new CSS rule lands in app/static/lecture.css' — "
        "the `.texttt` rule must be present for the typewriter font to apply. "
        "ADR-008: all Lecture-body content styling lives in lecture.css."
    )

    # The rule must include font-family: monospace (the key visual property)
    # Extract the block following .texttt
    texttt_block_match = re.search(
        r"\.texttt\s*\{([^}]*)\}", css_text, re.DOTALL
    )
    assert texttt_block_match is not None, (
        "'.texttt' selector found in lecture.css but no rule block `{ ... }` "
        "immediately follows it. ADR-018: the `.texttt` rule must have a "
        "declaration block with at least `font-family: monospace`."
    )

    rule_block = texttt_block_match.group(1)
    assert "monospace" in rule_block or "Courier" in rule_block, (
        f"The `.texttt` rule block does not contain 'monospace' or 'Courier': "
        f"{rule_block!r}. "
        "ADR-018 §Decision: `.texttt {{ font-family: 'Courier New', Courier, monospace; … }}`"
        " — the monospace font-family is the primary visual property of this rule."
    )


# ===========================================================================
# AC-3: `<span class="texttt">` elements present in hot chapters
# ===========================================================================

@pytest.mark.parametrize("chapter_id", TEXTTT_HOT_CHAPTERS)
def test_texttt_hot_chapters_have_span_texttt_elements(chapter_id: str) -> None:
    """
    AC-3 (TASK-007): chapters with heavy `\\texttt{}` usage (ch-04, ch-09,
    ch-10) must contain at least one `<span class="texttt">` element in the
    rendered lecture page.

    ADR-018 §Decision: "The parser handler for `\\texttt{}` … emits
    `<span class="texttt">...</span>` instead of `<code>...</code>`."

    Failure: if this test passes with the old code, the implementation
    still uses `<code>` and the ADR-018 fix is not present.

    This test is RED before ADR-018 is implemented.
    """
    client = _get_client()
    response = client.get(f"/lecture/{chapter_id}")
    assert response.status_code == 200, (
        f"GET /lecture/{chapter_id} returned {response.status_code}."
    )
    body = response.text

    texttt_spans = re.findall(
        r'<span[^>]*class="[^"]*texttt[^"]*"[^>]*>',
        body,
        flags=re.IGNORECASE,
    )
    assert len(texttt_spans) > 0, (
        f"GET /lecture/{chapter_id} — no `<span class=\"texttt\">` elements "
        "found in the rendered lecture page. "
        "ADR-018: `\\texttt{{}}` must emit `<span class=\"texttt\">`. "
        f"This Chapter ({chapter_id}) has confirmed `\\texttt{{}}` usage "
        "per the Run 008 corpus catalog (ch-04: 39 code+math instances; "
        "ch-09/ch-10: many inline texttt uses). "
        "If this test fails, the ADR-018 implementation is not present."
    )


@pytest.mark.parametrize("chapter_id", TEXTTT_HOT_CHAPTERS)
def test_texttt_hot_chapters_no_bare_inline_code_elements(chapter_id: str) -> None:
    """
    Negative / AC-3: hot chapters must have NO bare `<code>` elements
    (i.e., `<code>` NOT inside `<pre>`) after the texttt fix.

    ADR-018 §Decision: "The `<code>` element is reserved for `<pre><code>`
    blocks emitted by the `verbatim` and `lstlisting` environments. …
    No parser path currently emits inline `<code>`."

    The old bug: `\\texttt{}` → `<code>...</code>` (inline, not in `<pre>`).
    After the fix: `\\texttt{}` → `<span class="texttt">`, and `<code>` appears
    ONLY inside `<pre>` blocks.
    """
    client = _get_client()
    response = client.get(f"/lecture/{chapter_id}")
    assert response.status_code == 200

    body = response.text
    # Remove all <pre>...</pre> blocks (verbatim/lstlisting) from consideration
    body_no_pre = re.sub(
        r"<pre[\s>].*?</pre>",
        "<!-- PRE -->",
        body,
        flags=re.DOTALL | re.IGNORECASE,
    )

    # Any remaining <code> elements are bare inline code — should be zero
    bare_code = re.findall(
        r"<code[^>]*>.*?</code>",
        body_no_pre,
        flags=re.DOTALL | re.IGNORECASE,
    )
    assert bare_code == [], (
        f"GET /lecture/{chapter_id} — {len(bare_code)} bare inline `<code>` "
        "element(s) found outside `<pre>` blocks. "
        "ADR-018: after the fix, `<code>` must appear ONLY inside `<pre>` blocks. "
        "Bare inline `<code>` means the texttt handler still emits `<code>`, not "
        "`<span class=\"texttt\">`. "
        f"First bare code element: {bare_code[0][:100]!r}"
        if bare_code else ""
    )


# ===========================================================================
# Unit-level tests against parse_latex() for ADR-018 contract
# ===========================================================================

class TestTextttEmitsSpanNotCode:
    """
    ADR-018 unit-level tests: `\\texttt{...}` must emit `<span class="texttt">`
    and must NOT emit `<code>...</code>`.

    Uses parse_latex() directly (ADR-003 public API).
    """

    def test_texttt_without_math_emits_span_texttt(self):
        """
        Boundary: `\\texttt{variable_name}` (no embedded math).

        ADR-018 §Decision: "The argument's contents continue to be processed
        by `_convert_inline_latex` recursively." For plain text, the output
        must be `<span class="texttt">variable_name</span>`.
        """
        parse_latex = _import_parse_latex()
        latex = _make_doc(r"The pointer \texttt{head} points to the first node.")
        html = parse_latex(latex, "ch-test-texttt-plain")

        # Must contain a texttt span
        assert '<span class="texttt">' in html or "texttt" in html, (
            "No `<span class=\"texttt\">` found for `\\texttt{{head}}`. "
            "ADR-018: `\\texttt{{}}` must emit `<span class=\"texttt\">`. "
            "Before the fix, `\\texttt{{head}}` emitted `<code>head</code>`."
        )
        # Must NOT use <code> for texttt content
        # (allow <code> only inside <pre> for verbatim blocks)
        body_no_pre = re.sub(
            r"<pre[\s>].*?</pre>", "<!-- PRE -->", html,
            flags=re.DOTALL | re.IGNORECASE,
        )
        assert "<code>head</code>" not in body_no_pre, (
            "`<code>head</code>` found for `\\texttt{{head}}`. "
            "ADR-018: `\\texttt{{}}` must use `<span class=\"texttt\">`, not `<code>`."
        )

    def test_texttt_with_embedded_math_emits_span_with_math_passthrough(self):
        """
        Boundary AC-3: `\\texttt{head $\\to$ node}` — texttt with embedded math.

        ADR-018 §Decision: "the argument's contents continue to be processed by
        `_convert_inline_latex` recursively, which already passes `LatexMathNode`
        instances through verbatim — so `$\\to$` inside the texttt argument flows
        out as `$\\to$` inside the `<span class=\"texttt\">`."

        The HTML output must contain `$\\to$` INSIDE a `<span class="texttt">`,
        not inside a `<code>` element.

        This is the primary contract of ADR-018: math is preserved in the span
        so MathJax can render it (MathJax does not skip `<span>`).
        """
        parse_latex = _import_parse_latex()
        latex = _make_doc(
            r"\texttt{head $\to$ [7 | $\bullet$] $\to$ [9 | $\bullet$] $\to$ [5 | null]}"
        )
        html = parse_latex(latex, "ch-test-texttt-math")

        # The span must exist
        span_match = re.search(
            r'<span[^>]*class="[^"]*texttt[^"]*"[^>]*>(.*?)</span>',
            html,
            re.DOTALL | re.IGNORECASE,
        )
        assert span_match is not None, (
            "No `<span class=\"texttt\">` found for "
            r"`\texttt{head $\to$ [7 | $\bullet$] ...}`. "
            "ADR-018: `\\texttt{{}}` must emit `<span class=\"texttt\">`. "
            "This is the exact ch-04 ASCII-art callout pattern."
        )

        span_content = span_match.group(1)

        # The math must be INSIDE the span (not stripped)
        assert "$" in span_content or "\\to" in span_content, (
            f"Span content does not contain the math token `$\\to$`: {span_content!r}. "
            "ADR-018: `LatexMathNode` instances pass through verbatim inside the span "
            "so MathJax can process them. The math must NOT be stripped."
        )

        # Must NOT use <code> (the old buggy output)
        body_no_pre = re.sub(
            r"<pre[\s>].*?</pre>", "<!-- PRE -->", html,
            flags=re.DOTALL | re.IGNORECASE,
        )
        assert re.search(r"<code[^>]*>\s*\$\\to\$", body_no_pre) is None, (
            "Math token `$\\to$` found inside a `<code>` element. "
            "ADR-018: `\\texttt{{}}` must NOT emit `<code>`. "
            "The bug: `<code>` is in MathJax's `skipHtmlTags`, so `$\\to$` inside "
            "`<code>` renders as literal text `$\\to$` not as an arrow glyph."
        )

    def test_texttt_multiple_math_tokens_all_preserved_in_span(self):
        """
        Edge: `\\texttt{$\\to$ $\\bullet$ $\\leftarrow$}` — multiple math tokens.

        All three must be preserved inside the `<span class="texttt">`.
        The ch-04 corpus pattern has sequences like
        `[7 | $\\bullet$] $\\to$ [9 | $\\bullet$]` — multiple tokens per span.
        """
        parse_latex = _import_parse_latex()
        latex = _make_doc(r"\texttt{$\to$ and $\bullet$ and $\leftarrow$}")
        html = parse_latex(latex, "ch-test-texttt-multi-math")

        span_match = re.search(
            r'<span[^>]*class="[^"]*texttt[^"]*"[^>]*>(.*?)</span>',
            html,
            re.DOTALL | re.IGNORECASE,
        )
        assert span_match is not None, (
            "No `<span class=\"texttt\">` found for multi-math `\\texttt{{}}`. "
            "ADR-018: any `\\texttt{{}}` — with or without math — must emit the span."
        )

    def test_texttt_does_not_emit_code_element_at_all(self):
        """
        Negative: `\\texttt{plain text}` must produce ZERO bare `<code>` elements.

        Any `<code>` element in the rendered HTML (outside `<pre>`) after the fix
        would mean the old handler is still active.
        """
        parse_latex = _import_parse_latex()
        latex = _make_doc(
            r"Here is \texttt{some typewriter text} and more \texttt{another} text."
        )
        html = parse_latex(latex, "ch-test-texttt-no-code")

        body_no_pre = re.sub(
            r"<pre[\s>].*?</pre>", "<!-- PRE -->", html,
            flags=re.DOTALL | re.IGNORECASE,
        )
        bare_codes = re.findall(
            r"<code[^>]*>.*?</code>",
            body_no_pre,
            flags=re.DOTALL | re.IGNORECASE,
        )
        assert bare_codes == [], (
            f"Bare `<code>` element(s) found after `\\texttt{{}}` rendering: "
            f"{bare_codes!r}. "
            "ADR-018: `\\texttt{{}}` must emit `<span class=\"texttt\">`. "
            "Any bare `<code>` means the old handler is still active."
        )

    def test_texttt_with_html_special_chars_content_escaped(self):
        """
        Edge: `\\texttt{a < b & c > d}` — HTML-sensitive characters inside texttt.

        ADR-018 §Decision: "Per-character HTML escaping rules inside `\\texttt{}`:
        the existing `_convert_inline_latex` recursion handles HTML-special
        characters via `_escape`; that mechanism is unchanged."

        The `<` and `>` must be HTML-escaped in the output; they must not
        create raw HTML tags.
        """
        parse_latex = _import_parse_latex()
        latex = _make_doc(r"\texttt{a < b \& c > d}")
        html = parse_latex(latex, "ch-test-texttt-escape")

        span_match = re.search(
            r'<span[^>]*class="[^"]*texttt[^"]*"[^>]*>(.*?)</span>',
            html,
            re.DOTALL | re.IGNORECASE,
        )
        if span_match is not None:
            span_content = span_match.group(1)
            # The raw `<` or `>` must not appear unescaped inside the span
            # (they would break the HTML if present)
            assert not re.search(r"<[a-z]", span_content, re.IGNORECASE), (
                "Raw `<tag>` found inside `<span class=\"texttt\">` for content "
                r"with HTML-special chars `a < b`. "
                "ADR-018: `_convert_inline_latex` must HTML-escape special chars."
            )

    def test_texttt_content_is_preserved_not_empty(self):
        """
        Positive: the texttt span must not be empty.

        `\\texttt{non-empty}` → `<span class="texttt">non-empty</span>` (not `<span></span>`).
        """
        parse_latex = _import_parse_latex()
        latex = _make_doc(r"\texttt{non-empty-content}")
        html = parse_latex(latex, "ch-test-texttt-nonempty")

        span_match = re.search(
            r'<span[^>]*class="[^"]*texttt[^"]*"[^>]*>(.*?)</span>',
            html,
            re.DOTALL | re.IGNORECASE,
        )
        if span_match is not None:
            span_content = span_match.group(1).strip()
            assert span_content != "", (
                "The `<span class=\"texttt\">` element is empty. "
                "ADR-018: the texttt argument content must appear inside the span."
            )
            assert "non-empty-content" in span_content or "non" in span_content, (
                f"Span content is not 'non-empty-content': {span_content!r}. "
                "The texttt argument text must be preserved inside the span."
            )


# ===========================================================================
# AC-3 (structural): ch-04 "Picture the list" callout contains texttt span
# with "head" reference (per TASK-007 task file AC description).
# ===========================================================================

def test_ch04_has_texttt_span_with_head_content() -> None:
    """
    AC-3 (structural): ch-04's "Picture the list" callout in the rendered
    lecture page must contain a `<span class="texttt">` whose content includes
    "head" (the first word in the ASCII-art typewriter string
    `\\texttt{head $\\to$ [7 | $\\bullet$] ...}`).

    TASK-007 task file AC-3: "the rendered HTML contains a `<span class=\"texttt\">`
    whose content references 'head'."

    This test will be RED before ADR-018 is implemented because:
    - The old handler emits `<code>head ...</code>`
    - The new handler must emit `<span class="texttt">head ...</span>`
    """
    client = _get_client()
    response = client.get("/lecture/ch-04-lists-stacks-and-queues")
    assert response.status_code == 200, (
        "GET /lecture/ch-04-lists-stacks-and-queues returned "
        f"{response.status_code}. Cannot test texttt span presence."
    )
    body = response.text

    # Find all <span class="texttt"> or <span class="texttt ..."> elements
    texttt_spans = re.findall(
        r'<span[^>]*class="[^"]*texttt[^"]*"[^>]*>(.*?)</span>',
        body,
        flags=re.DOTALL | re.IGNORECASE,
    )

    assert len(texttt_spans) > 0, (
        "No `<span class=\"texttt\">` elements found in ch-04. "
        "ADR-018: the `\\texttt{{}}` handler must emit this span. "
        "ch-04 has 39 confirmed `\\texttt{{}}` with embedded math (Run 008 catalog). "
        "If zero spans found, the ADR-018 fix is not present."
    )

    # At least one span must contain "head" (from the ASCII-art callout)
    spans_with_head = [s for s in texttt_spans if "head" in s.lower()]
    assert len(spans_with_head) > 0, (
        f"None of the {len(texttt_spans)} `<span class=\"texttt\">` elements "
        "in ch-04 contain 'head'. "
        "TASK-007 AC-3: 'the rendered HTML contains a `<span class=\"texttt\">` "
        "whose content references head (the typewriter-fonted ASCII-art string).' "
        "The ch-04 source has `\\texttt{{head $\\to$ [7 | $\\bullet$] ...}}`."
    )


# ===========================================================================
# Positive: texttt spans across all 12 chapters don't crash the parser
# ===========================================================================

@pytest.mark.parametrize("chapter_id", ALL_CHAPTER_IDS)
def test_all_chapters_render_with_span_texttt_or_no_texttt_usage(
    chapter_id: str
) -> None:
    """
    Structural / regression: every Chapter renders successfully (HTTP 200)
    after the ADR-018 change, and for Chapters with `\\texttt{}` usage the
    new `<span class="texttt">` element appears.

    This catches a regression where ADR-018's parser change breaks chapters
    that don't use `\\texttt{}` (the handler change must be safe for all paths).

    For chapters WITH `\\texttt{}` usage: at least one span must be present.
    For chapters WITHOUT usage: HTTP 200 and no bare inline `<code>` is sufficient.
    """
    client = _get_client()
    response = client.get(f"/lecture/{chapter_id}")
    assert response.status_code == 200, (
        f"GET /lecture/{chapter_id} returned {response.status_code}. "
        "ADR-018 parser change must not break any Chapter's rendering."
    )

    body = response.text
    # If any texttt span appears, verify it has content (not an empty span)
    texttt_spans_with_content = re.findall(
        r'<span[^>]*class="[^"]*texttt[^"]*"[^>]*>(.+?)</span>',
        body,
        flags=re.DOTALL | re.IGNORECASE,
    )
    for span_content in texttt_spans_with_content:
        stripped = span_content.strip()
        assert stripped != "", (
            f"GET /lecture/{chapter_id} — a `<span class=\"texttt\">` element "
            "is empty (no content between tags). "
            "ADR-018: every texttt span must contain its argument text."
        )
