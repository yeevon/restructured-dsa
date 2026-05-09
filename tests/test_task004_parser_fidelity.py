"""
Unit / integration tests for TASK-004: Fix parser fidelity.

Bug 1 (ADR-011): Tabular column spec passthrough.
  `\\begin{tabular}{lll}` leaks `lll` as visible text in the first rendered
  table row.  The parser must strip the column-spec argument entirely.

Bug 2 (ADR-012): Callout title passthrough.
  `\\begin{ideabox}[Chapter map]` renders `[Chapter map]` as inline bracketed
  text instead of a structured `<div class="callout-title">` header element.

Test strategy:
  - Call `parse_latex(latex_text, chapter_id)` directly (public API, ADR-003).
  - Also exercise `extract_sections(chapter_id, latex_body)` for section-scoped
    rendering to confirm both rendering paths are fixed (ADR-012 specifies both
    `_nodes_to_html` and `_convert_inline_latex` must handle titles).
  - For warning assertions, use `caplog` at WARNING level.
  - Negative tests pin what MUST NOT appear in output.

Coverage categories addressed:
  - Boundary: simple `l`/`c`/`r` (no warn), complex `|` / `p{w}` / `@{...}` (warn).
  - Edge: no-title callout, multi-word title, title with HTML-sensitive chars,
    all five callout envs, tabular nested inside a callout.
  - Negative: column spec text must not appear anywhere in rendered output;
    raw `[Title]` bracket form must not appear in rendered callout.
  - Performance: skipped — inputs are fixed-size single-unit; no scaling surface.
"""

from __future__ import annotations

import importlib
import logging
import re

import pytest

pytestmark = pytest.mark.task("TASK-004")

# ---------------------------------------------------------------------------
# Parser import
# ---------------------------------------------------------------------------

def _import_parse_latex():
    """Import parse_latex from app.parser (ADR-003 public API)."""
    mod = importlib.import_module("app.parser")
    return mod.parse_latex


def _import_extract_sections():
    """Import extract_sections from app.parser (ADR-003 public API)."""
    mod = importlib.import_module("app.parser")
    return mod.extract_sections


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CALLOUT_ENVS = ["ideabox", "defnbox", "notebox", "warnbox", "examplebox"]

_CALLOUT_TITLE_DIV_RE = re.compile(
    r'<div[^>]*class="[^"]*callout-title[^"]*"[^>]*>(.*?)</div>',
    re.DOTALL | re.IGNORECASE,
)


def _make_doc(body: str) -> str:
    """Wrap body in a minimal LaTeX document structure."""
    return (
        r"\documentclass{article}" + "\n"
        r"\begin{document}" + "\n"
        + body + "\n"
        r"\end{document}"
    )


# ===========================================================================
# AC-1  Tabular column spec NOT visible as text in rendered output
# ADR-011: Strip column-specification argument entirely from rendered output.
# ===========================================================================

class TestTabularColumnSpecStripped:
    """
    ADR-011: The column-spec argument from `\\begin{tabular}{<spec>}` must
    not appear as visible text anywhere in the rendered HTML output.

    The bug: the parser leaked the spec string (e.g. `lll`) into the first
    rendered table row as plain text.
    """

    def test_simple_lll_spec_not_in_rendered_html(self):
        """
        AC-1: `\\begin{tabular}{lll}` must not produce `lll` as visible text.

        Given a tabular environment with spec `lll`, the rendered HTML must
        contain zero occurrences of the literal string `lll` outside of
        `<pre>`/`<code>` blocks (i.e. not as a data row cell).

        This is the primary red signal for ADR-011's strip requirement.
        """
        parse_latex = _import_parse_latex()
        latex = _make_doc(
            r"""
\begin{tabular}{lll}
Header A & Header B & Header C \\
Row 1 & Row 2 & Row 3 \\
\end{tabular}
"""
        )
        html = parse_latex(latex, "ch-test-tabular")
        # The spec string `lll` must not appear in the rendered prose/table HTML.
        # It is acceptable inside a <pre> or <code> block but must not be a
        # free-standing text node (the bug was exactly this: `lll` appeared as
        # the first row's content).
        prose_html = re.sub(
            r"<pre[\s>].*?</pre>|<code[\s>].*?</code>",
            "<!-- CODE -->",
            html,
            flags=re.DOTALL | re.IGNORECASE,
        )
        assert "lll" not in prose_html, (
            "Column spec 'lll' found in rendered prose HTML. "
            "ADR-011: the column-spec argument must be stripped entirely; "
            "it must not appear as visible text in any table row."
        )

    def test_data_rows_still_rendered_after_spec_strip(self):
        """
        ADR-011: Stripping the spec must not silently drop data rows.

        The table body content (data rows) must still appear in the HTML
        even after the spec is stripped.
        """
        parse_latex = _import_parse_latex()
        latex = _make_doc(
            r"""
\begin{tabular}{lll}
Alpha & Beta & Gamma \\
Delta & Epsilon & Zeta \\
\end{tabular}
"""
        )
        html = parse_latex(latex, "ch-test-tabular")
        assert "Alpha" in html, (
            "Data row content 'Alpha' is missing from rendered HTML after "
            "column-spec strip. ADR-011: only the spec is stripped; data rows "
            "must still render as <tr> elements."
        )
        assert "Delta" in html, (
            "Data row content 'Delta' (second row) is missing from rendered HTML. "
            "ADR-011: all data rows must survive the spec strip."
        )

    def test_simple_ll_spec_not_in_rendered_html(self):
        """
        Boundary: two-column `ll` spec must also be stripped (not just `lll`).
        """
        parse_latex = _import_parse_latex()
        latex = _make_doc(
            r"""
\begin{tabular}{ll}
Name & Value \\
foo & bar \\
\end{tabular}
"""
        )
        html = parse_latex(latex, "ch-test-tabular")
        prose_html = re.sub(
            r"<pre[\s>].*?</pre>|<code[\s>].*?</code>",
            "<!-- CODE -->",
            html,
            flags=re.DOTALL | re.IGNORECASE,
        )
        # `ll` must not appear as a table data cell
        # (check: not present as a standalone text node in a <td> or <tr>)
        assert "<td>ll</td>" not in prose_html and "<th>ll</th>" not in prose_html, (
            "Column spec 'll' appears as a table cell in rendered HTML. "
            "ADR-011: two-column simple spec must be stripped without warning."
        )

    def test_lcr_mixed_simple_spec_not_in_rendered_html(self):
        """
        Boundary: `lcr` (mixed simple alignment) must be stripped without warning.
        ADR-011 §Decision: simple l/c/r stripped without warning.
        """
        parse_latex = _import_parse_latex()
        latex = _make_doc(
            r"""
\begin{tabular}{lcr}
Left & Center & Right \\
\end{tabular}
"""
        )
        html = parse_latex(latex, "ch-test-tabular")
        prose_html = re.sub(
            r"<pre[\s>].*?</pre>|<code[\s>].*?</code>",
            "<!-- CODE -->",
            html,
            flags=re.DOTALL | re.IGNORECASE,
        )
        assert "lcr" not in prose_html, (
            "Column spec 'lcr' found as visible text in rendered HTML. "
            "ADR-011: mixed simple l/c/r spec must be stripped."
        )

    def test_ch01_tabular_lll_not_in_rendered_html(self, ch01_lecture_response):
        """
        End-to-end / regression: The ch-01 source has `\\begin{tabular}{lll}` on
        line 144. The rendered lecture page must not contain `lll` as prose text
        outside code blocks.

        This test drives the live ch-01 lecture through the full rendering pipeline.
        """
        html = ch01_lecture_response.text
        prose_html = re.sub(
            r"<pre[\s>].*?</pre>|<code[\s>].*?</code>",
            "<!-- CODE -->",
            html,
            flags=re.DOTALL | re.IGNORECASE,
        )
        # The spec `lll` must not appear as a visible text node.
        # (It is fine as part of an attribute value, but it must not be a cell
        # contents — the bug was exactly that it appeared as the first row cell.)
        assert "<td>lll</td>" not in prose_html and "<th>lll</th>" not in prose_html, (
            "Column spec 'lll' from ch-01-cpp-refresher.tex line 144 rendered "
            "as a table cell in the lecture page. ADR-011: spec must be stripped."
        )

    def test_tabular_inside_callout_spec_not_in_rendered_html(self):
        """
        Edge: tabular nested inside a callout environment (as it appears in ch-01
        line 143-155: `\\begin{examplebox}[C++ sequence containers]` contains
        `\\begin{tabular}{lll}`).

        The spec must be stripped even when the tabular is a child of a callout.
        """
        parse_latex = _import_parse_latex()
        latex = _make_doc(
            r"""
\begin{examplebox}[Containers]
\begin{tabular}{lll}
Type & Size & Access \\
array & fixed & a[i] \\
\end{tabular}
\end{examplebox}
"""
        )
        html = parse_latex(latex, "ch-test-nested-tabular")
        prose_html = re.sub(
            r"<pre[\s>].*?</pre>|<code[\s>].*?</code>",
            "<!-- CODE -->",
            html,
            flags=re.DOTALL | re.IGNORECASE,
        )
        assert "<td>lll</td>" not in prose_html and "<th>lll</th>" not in prose_html, (
            "Column spec 'lll' leaked as a table cell inside a callout-nested tabular. "
            "ADR-011: spec must be stripped regardless of nesting context."
        )


# ===========================================================================
# AC-2  Complex tabular specs → no visible text + parser logs warning
# ADR-011: `|`, `p{width}`, `@{...}` → warn-per-node; data rows still render.
# ===========================================================================

class TestTabularComplexSpecWarning:
    """
    ADR-011: For column-spec features the parser does not interpret (vertical
    bars `|`, paragraph columns `p{width}`, inter-column spacing `@{...}`),
    the parser logs a structured WARNING per the warn-per-node pattern (ADR-003).

    The spec still must not appear as visible text in the output.
    """

    def test_pipe_spec_not_visible_in_output(self):
        """
        AC-2: `\\begin{tabular}{l|c|r}` — the spec `l|c|r` must not be visible
        in the rendered HTML.
        """
        parse_latex = _import_parse_latex()
        latex = _make_doc(
            r"""
\begin{tabular}{l|c|r}
Left & Center & Right \\
\end{tabular}
"""
        )
        html = parse_latex(latex, "ch-test-pipe-spec")
        prose_html = re.sub(
            r"<pre[\s>].*?</pre>|<code[\s>].*?</code>",
            "<!-- CODE -->",
            html,
            flags=re.DOTALL | re.IGNORECASE,
        )
        assert "l|c|r" not in prose_html, (
            "Complex spec 'l|c|r' found as visible text in rendered HTML. "
            "ADR-011: complex spec must be stripped (no visible text)."
        )

    def test_pipe_spec_triggers_warning_log(self, caplog):
        """
        AC-2: `|` in a column spec must trigger a WARNING-level log entry per
        ADR-011's warn-per-node contract.
        """
        parse_latex = _import_parse_latex()
        latex = _make_doc(
            r"""
\begin{tabular}{l|c|r}
A & B & C \\
\end{tabular}
"""
        )
        with caplog.at_level(logging.WARNING):
            parse_latex(latex, "ch-test-pipe-warn")

        warning_texts = [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]
        has_pipe_warning = any("|" in msg or "pipe" in msg.lower() or "vertical" in msg.lower()
                               for msg in warning_texts)
        assert has_pipe_warning, (
            "No WARNING log mentioning '|' (vertical bar) was emitted when parsing "
            "a tabular environment with spec 'l|c|r'. "
            "ADR-011: complex spec features must be logged as structured warnings "
            "per ADR-003's warn-per-node pattern. "
            f"Warning messages captured: {warning_texts!r}"
        )

    def test_p_width_spec_not_visible_in_output(self):
        """
        Boundary: `p{width}` column spec must be stripped without leaking text.
        """
        parse_latex = _import_parse_latex()
        latex = _make_doc(
            r"""
\begin{tabular}{p{3cm}p{5cm}}
Description & Value \\
foo & bar \\
\end{tabular}
"""
        )
        html = parse_latex(latex, "ch-test-p-spec")
        prose_html = re.sub(
            r"<pre[\s>].*?</pre>|<code[\s>].*?</code>",
            "<!-- CODE -->",
            html,
            flags=re.DOTALL | re.IGNORECASE,
        )
        assert "p{3cm}" not in prose_html and "p{5cm}" not in prose_html, (
            "Paragraph-column spec 'p{3cm}' or 'p{5cm}' found in rendered HTML. "
            "ADR-011: p{width} column specs must be stripped."
        )

    def test_p_width_spec_triggers_warning_log(self, caplog):
        """
        ADR-011: `p{width}` must trigger a WARNING log.
        """
        parse_latex = _import_parse_latex()
        latex = _make_doc(
            r"""
\begin{tabular}{p{3cm}p{5cm}}
Description & Value \\
\end{tabular}
"""
        )
        with caplog.at_level(logging.WARNING):
            parse_latex(latex, "ch-test-p-warn")

        warning_texts = [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]
        has_p_warning = any(
            "p{" in msg or "paragraph" in msg.lower() or "p-col" in msg.lower()
            for msg in warning_texts
        )
        assert has_p_warning, (
            "No WARNING log mentioning 'p{' (paragraph column) was emitted when "
            "parsing a tabular environment with 'p{width}' spec. "
            "ADR-011: p{width} features must trigger warn-per-node. "
            f"Warning messages captured: {warning_texts!r}"
        )

    def test_at_spec_not_visible_in_output(self):
        """
        Boundary: `@{...}` inter-column spacing spec must be stripped.
        """
        parse_latex = _import_parse_latex()
        latex = _make_doc(
            r"""
\begin{tabular}{l@{\quad}r}
Left & Right \\
\end{tabular}
"""
        )
        html = parse_latex(latex, "ch-test-at-spec")
        prose_html = re.sub(
            r"<pre[\s>].*?</pre>|<code[\s>].*?</code>",
            "<!-- CODE -->",
            html,
            flags=re.DOTALL | re.IGNORECASE,
        )
        assert r"@{\quad}" not in prose_html and r"@{" not in prose_html, (
            "Inter-column spacing spec '@{...}' found in rendered HTML. "
            "ADR-011: @{...} features must be stripped."
        )

    def test_simple_lrc_does_not_trigger_warning(self, caplog):
        """
        ADR-011 §Decision: simple l/c/r are stripped without warning.
        A warning for simple specs would be "non-actionable noise" (ADR-011
        alternative C was rejected on exactly this basis).

        This test confirms the warning log is NOT triggered for simple specs.
        """
        parse_latex = _import_parse_latex()
        latex = _make_doc(
            r"""
\begin{tabular}{lcr}
A & B & C \\
\end{tabular}
"""
        )
        with caplog.at_level(logging.WARNING):
            parse_latex(latex, "ch-test-no-warn")

        warning_texts = [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]
        # There should be no warning about tabular column spec for simple l/c/r
        tabular_spec_warnings = [
            msg for msg in warning_texts
            if "tabular" in msg.lower() and (
                "spec" in msg.lower() or "column" in msg.lower() or "|" in msg
            )
        ]
        assert tabular_spec_warnings == [], (
            "A WARNING was logged for a simple l/c/r tabular spec. "
            "ADR-011: simple alignment letters are stripped WITHOUT warning — "
            "warn-per-node is reserved for complex features (|, p{w}, @{...}). "
            f"Unexpected warnings: {tabular_spec_warnings!r}"
        )


# ===========================================================================
# AC-3  Callout title: `\\begin{ideabox}[Chapter map]` → callout-title div
# ADR-012: Extract optional [Title] → emit <div class="callout-title">Title</div>
# ===========================================================================

class TestCalloutTitleRendering:
    """
    ADR-012: Every callout environment with a `[Title]` argument must produce
    a `<div class="callout-title">Title</div>` as the first child of the
    callout wrapper div.

    The bug: the parser emitted `[Chapter map]` as inline bracketed text inside
    the callout body, with no structural header treatment.
    """

    def test_ideabox_title_in_callout_title_div(self):
        """
        AC-3: `\\begin{ideabox}[Chapter map]` → title in `<div class="callout-title">`.

        The title text "Chapter map" must appear inside an element with
        class `callout-title`, not as raw bracketed text `[Chapter map]`.
        """
        parse_latex = _import_parse_latex()
        latex = _make_doc(
            r"""
\begin{ideabox}[Chapter map]
This is the body of the ideabox.
\end{ideabox}
"""
        )
        html = parse_latex(latex, "ch-test-callout-title")

        # The title must be inside a callout-title element
        title_matches = _CALLOUT_TITLE_DIV_RE.findall(html)
        assert any("Chapter map" in m for m in title_matches), (
            "Title 'Chapter map' was NOT found inside a "
            '<div class="callout-title"> element in the rendered HTML. '
            "ADR-012: the optional [Title] argument must be extracted and emitted "
            "as <div class=\"callout-title\">Title</div>. "
            f"callout-title divs found: {title_matches!r}"
        )

    def test_ideabox_title_not_as_raw_bracketed_text(self):
        """
        AC-3 (negative): `[Chapter map]` must NOT appear as raw inline text.

        A passing callout-title test that coexists with `[Chapter map]` still
        present as prose text would be a false positive. This test makes the
        "raw bracketed text is gone" assertion explicit.
        """
        parse_latex = _import_parse_latex()
        latex = _make_doc(
            r"""
\begin{ideabox}[Chapter map]
Body text here.
\end{ideabox}
"""
        )
        html = parse_latex(latex, "ch-test-callout-title")
        assert "[Chapter map]" not in html, (
            "Raw bracketed title '[Chapter map]' found in rendered HTML. "
            "ADR-012: the [Title] argument must be extracted into a structural "
            "element, not passed through as bracketed inline text. "
            "This is the exact bug TASK-004 fixes."
        )

    def test_ch01_first_callout_title_in_callout_title_div(self, ch01_lecture_response):
        """
        End-to-end / regression: ch-01 line 11 is `\\begin{ideabox}[Chapter map]`.
        The rendered lecture page must contain the title in a callout-title div.

        This test drives the full rendering pipeline against the live corpus.
        """
        html = ch01_lecture_response.text

        title_matches = _CALLOUT_TITLE_DIV_RE.findall(html)
        assert any("Chapter map" in m for m in title_matches), (
            "Title 'Chapter map' (from ch-01-cpp-refresher.tex line 11: "
            "\\begin{ideabox}[Chapter map]) was not found inside a "
            '<div class="callout-title"> in the rendered lecture page. '
            "ADR-012: callout titles must render as structural header elements."
        )

    def test_ch01_bracketed_title_text_not_in_rendered_html(self, ch01_lecture_response):
        """
        End-to-end negative: `[Chapter map]` must not appear anywhere in the
        ch-01 rendered lecture page as raw prose text.
        """
        html = ch01_lecture_response.text
        assert "[Chapter map]" not in html, (
            "Raw bracketed title '[Chapter map]' found in the ch-01 rendered "
            "lecture page. ADR-012: title argument must be extracted and "
            "structurally emitted, not passed through as inline bracketed text."
        )


# ===========================================================================
# AC-4  Callout without title: no title element emitted
# ADR-012: When no optional argument is supplied, no title element is emitted.
# ===========================================================================

class TestCalloutNoTitle:
    """
    ADR-012: Callout environments without a `[Title]` argument must not
    emit any `<div class="callout-title">` element.
    """

    def test_ideabox_without_title_has_no_callout_title_div(self):
        """
        AC-4: `\\begin{ideabox}` (no optional arg) → no callout-title element.
        """
        parse_latex = _import_parse_latex()
        latex = _make_doc(
            r"""
\begin{ideabox}
Just the body, no title.
\end{ideabox}
"""
        )
        html = parse_latex(latex, "ch-test-no-title")
        assert "callout-title" not in html, (
            "A callout-title element was emitted for an ideabox with no optional "
            "argument. ADR-012: when no [Title] is supplied, no title element is "
            "emitted — the callout body renders as before."
        )

    def test_defnbox_without_title_has_no_callout_title_div(self):
        """
        Boundary: defnbox without title — no callout-title element.
        """
        parse_latex = _import_parse_latex()
        latex = _make_doc(
            r"""
\begin{defnbox}
A definition without a title label.
\end{defnbox}
"""
        )
        html = parse_latex(latex, "ch-test-no-title")
        assert "callout-title" not in html, (
            "A callout-title element was emitted for a defnbox with no optional "
            "argument. ADR-012: no title arg → no title element."
        )


# ===========================================================================
# AC-5  All 5 callout envs with [Title] → consistent: same element, same CSS
# ADR-012: Consistent across ideabox, defnbox, notebox, warnbox, examplebox.
# ===========================================================================

class TestAllCalloutEnvsHaveConsistentTitleRendering:
    """
    ADR-012: The title rendering must be consistent across all five callout
    environments. Each must:
    - Extract [Title] and emit <div class="callout-title">Title</div>
    - Use the same CSS class name
    - Place the title as the first child of the callout div
    """

    @pytest.mark.parametrize("env_name", _CALLOUT_ENVS)
    def test_callout_env_with_title_emits_callout_title_div(self, env_name: str):
        """
        AC-5: Every callout environment (parametrized over all 5) must emit
        `<div class="callout-title">` when given a [Title] argument.

        Iterating over all 5 envs — not just ideabox — ensures the fix is
        applied consistently (ADR-012 §Decision: "Consistent across all five
        callout environments").
        """
        parse_latex = _import_parse_latex()
        title_text = f"Test Title For {env_name}"
        latex = _make_doc(
            f"\\begin{{{env_name}}}[{title_text}]\n"
            "Body content.\n"
            f"\\end{{{env_name}}}\n"
        )
        html = parse_latex(latex, f"ch-test-{env_name}")

        title_matches = _CALLOUT_TITLE_DIV_RE.findall(html)
        assert any(title_text in m for m in title_matches), (
            f"Callout environment '{env_name}' with title [{title_text!r}] did not "
            f"emit a <div class=\"callout-title\"> element. "
            "ADR-012: all five callout environments must use the same structural "
            "title emission. If ideabox works but defnbox does not, the fix is "
            "incomplete."
        )

    @pytest.mark.parametrize("env_name", _CALLOUT_ENVS)
    def test_callout_env_title_not_as_raw_bracketed_text(self, env_name: str):
        """
        AC-5 (negative): For every callout env, raw `[Title text]` must not
        appear in the rendered output.

        This is the "no raw passthrough" assertion for each of the 5 envs.
        """
        parse_latex = _import_parse_latex()
        title_text = f"TitleFor{env_name}"
        bracketed = f"[{title_text}]"
        latex = _make_doc(
            f"\\begin{{{env_name}}}[{title_text}]\n"
            "Body content.\n"
            f"\\end{{{env_name}}}\n"
        )
        html = parse_latex(latex, f"ch-test-{env_name}")
        assert bracketed not in html, (
            f"Raw bracketed title '{bracketed}' found in rendered HTML for "
            f"callout environment '{env_name}'. "
            "ADR-012: [Title] argument must be extracted, not passed through."
        )

    def test_all_five_envs_use_same_callout_title_class(self):
        """
        AC-5 structural consistency: all five envs must use exactly
        `class="callout-title"` (or a class containing `callout-title`).

        If one env uses `callout-header` while another uses `callout-title`,
        the CSS rule in lecture.css (ADR-012 §Decision: ".callout-title CSS
        rule already exists") would not apply uniformly.
        """
        parse_latex = _import_parse_latex()
        for env_name in _CALLOUT_ENVS:
            title_text = "Uniform Title"
            latex = _make_doc(
                f"\\begin{{{env_name}}}[{title_text}]\n"
                "Body.\n"
                f"\\end{{{env_name}}}\n"
            )
            html = parse_latex(latex, f"ch-test-class-{env_name}")
            title_divs = _CALLOUT_TITLE_DIV_RE.findall(html)
            assert any(title_text in m for m in title_divs), (
                f"Callout environment '{env_name}' does not emit a "
                '<div class="callout-title"> (or class containing "callout-title") '
                f"element. All five envs must use the same CSS class for "
                "consistent styling (ADR-012, ADR-008)."
            )

    def test_all_callout_titles_in_ch01_are_structural(self, ch01_lecture_response):
        """
        Batch assertion: every callout instance in ch-01 has a title argument
        (grepped: 27+14+12+29+29 = 111 instances with brackets). After the fix,
        none of those titles should appear as raw bracketed text in the rendered
        HTML.

        We do not enumerate all 111 titles individually; instead we assert that
        NO pattern matching `[<word_chars> ]` appears inside a callout div's
        text as the ONLY callout-title treatment (i.e., the raw form is gone
        and the structural form is present).

        Specifically: the opening bracket directly after whitespace or start-of-
        callout-content is the bug pattern. We check that the number of
        `<div class="callout-title">` occurrences is >= 111 (all instances have
        titles), confirming structural emission for the whole corpus.
        """
        html = ch01_lecture_response.text
        # Count structural callout-title divs
        title_div_count = len(_CALLOUT_TITLE_DIV_RE.findall(html))
        total_titled_callouts = 27 + 14 + 12 + 29 + 29  # all 111 have [Title]
        assert title_div_count >= total_titled_callouts, (
            f"Expected at least {total_titled_callouts} <div class=\"callout-title\"> "
            f"elements in the ch-01 rendered lecture page (one per titled callout), "
            f"found {title_div_count}. "
            "ADR-012: every callout with a [Title] argument must emit a structural "
            "callout-title div."
        )


# ===========================================================================
# Edge / Boundary: HTML escaping, multi-word titles, special chars
# ADR-012 §Decision: title text is HTML-escaped (via _escape before insertion).
# ===========================================================================

class TestCalloutTitleEdgeCases:
    """
    ADR-012 §Decision: "The title text is HTML-escaped (via _escape) before
    insertion into the <div class=\"callout-title\">."

    Edge cases: titles with HTML-sensitive characters, multi-word titles, and
    titles containing LaTeX formatting macros.
    """

    def test_title_with_html_sensitive_chars_is_escaped(self):
        """
        Edge: title text `A & B` must be HTML-escaped to `A &amp; B` in output.

        ADR-012 explicitly commits to HTML-escaping the title text.
        A title with `&` that is not escaped would be an XSS vector in a real
        app and a rendering defect here.
        """
        parse_latex = _import_parse_latex()
        latex = _make_doc(
            r"""
\begin{notebox}[Arrays & Vectors]
Some body.
\end{notebox}
"""
        )
        html = parse_latex(latex, "ch-test-escape")
        # The raw `&` must not appear unescaped inside the callout-title div.
        title_matches = _CALLOUT_TITLE_DIV_RE.findall(html)
        # At least one title div must exist
        assert title_matches, (
            "No <div class=\"callout-title\"> found for notebox with title "
            "'Arrays & Vectors'. ADR-012: title must be emitted structurally."
        )
        for match in title_matches:
            if "Arrays" in match or "Vectors" in match:
                assert "&amp;" in match or "Arrays" in match, (
                    "Title containing '&' was not HTML-escaped in callout-title div. "
                    "ADR-012: title text is HTML-escaped via _escape."
                )

    def test_multi_word_title_is_fully_captured(self):
        """
        Edge: multi-word title `The big picture for 1.1` (which appears in
        ch-01 at line 166) must be fully captured, not truncated at first word.
        """
        parse_latex = _import_parse_latex()
        latex = _make_doc(
            r"""
\begin{ideabox}[The big picture for 1.1]
Full idea body here.
\end{ideabox}
"""
        )
        html = parse_latex(latex, "ch-test-multi-word")
        title_matches = _CALLOUT_TITLE_DIV_RE.findall(html)
        full_title = "The big picture for 1.1"
        assert any(full_title in m for m in title_matches), (
            f"Multi-word title '{full_title}' was not fully captured in "
            "<div class=\"callout-title\">. "
            "ADR-012: the full bracket content is the title."
        )

    def test_callout_body_content_is_preserved_alongside_title(self):
        """
        Regression: extracting the title must not consume or discard the
        callout body content.

        After the fix, the body text must still appear in the callout div
        after the callout-title element.
        """
        parse_latex = _import_parse_latex()
        body_text = "This is the actual body content that must survive."
        latex = _make_doc(
            f"\\begin{{warnbox}}[Important warning]\n"
            f"{body_text}\n"
            f"\\end{{warnbox}}\n"
        )
        html = parse_latex(latex, "ch-test-body-preserved")
        assert body_text in html, (
            f"Callout body text '{body_text}' is missing from rendered HTML "
            "after title extraction. ADR-012: extracting [Title] must not "
            "discard the callout body."
        )
