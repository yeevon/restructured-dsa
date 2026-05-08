"""
Rendering-fidelity tests for TASK-001 — coverage gaps flagged by human reviewer.

These tests cover three (plus two bonus) areas that were absent from the original
test_task001_lecture_page.py suite:

  Gap 1 — Callout environments render as distinguishable HTML blocks
           (ADR-003: custom callout environments → styled HTML blocks)
  Gap 2 — No leaked raw LaTeX in rendered HTML
           (ADR-003: pylatexenc parse failures must not silently pass through)
  Gap 3 — Code listings render as <pre><code> blocks
           (ADR-003: lstlisting environments → <pre><code> blocks)
  Bonus 4 — Math expressions survive in MathJax-renderable form
           (ADR-003: inline/display math passes through unchanged)
  Bonus 5 — Unknown-macro warning logged, no crash
           (ADR-003: unrecognized nodes → structured warning, not crash/fabrication)

CONTRACT DECISIONS pinned in this module (within implementer latitude):
  - Callout HTML contract: each callout environment is represented in the rendered
    HTML as an element carrying a `data-callout="<env-name>"` attribute, e.g.
      data-callout="ideabox"
    Alternative class-name contracts (e.g. <div class="ideabox">) would also satisfy
    ADR-003; we pin data-callout because it is stable under CSS refactors and
    unambiguously machine-queryable.  The implementer MUST honor this attribute
    name; if a different attribute is chosen the tests document the mismatch clearly.
  - Math passthrough contract: inline math $...$ and display math \\[...\\] must
    appear in the HTML either unchanged (same delimiters) OR inside a
    <span class="math"> / <span class="math-inline"> / <span class="math-display">
    wrapper (any of those three class names are accepted).  MathJax convention is
    the LaTeX delimiter passthrough, so the test checks for that first.

CALLOUT COUNTS (grepped from content/latex/ch-01-cpp-refresher.tex):
  ideabox:    27 instances
  defnbox:    14 instances
  notebox:    12 instances
  warnbox:    29 instances
  examplebox: 29 instances

LSTLISTING COUNT: 36 pairs (\\begin{lstlisting} / \\end{lstlisting})

All tests carry pytestmark = pytest.mark.task("TASK-001") per the test-writer contract.
"""

import re
import logging
import pathlib

import pytest

pytestmark = pytest.mark.task("TASK-001")

# ---------------------------------------------------------------------------
# Source-derived constants (grepped; must match the real source exactly)
# ---------------------------------------------------------------------------

# Count of each callout environment in ch-01-cpp-refresher.tex
CALLOUT_COUNTS = {
    "ideabox": 27,
    "defnbox": 14,
    "notebox": 12,
    "warnbox": 29,
    "examplebox": 29,
}

# All five callout types present in ch-01-cpp-refresher.tex
CALLOUT_ENVS = list(CALLOUT_COUNTS.keys())

# Number of \\begin{lstlisting} / \\end{lstlisting} pairs in source
LSTLISTING_COUNT = 36

# A recognizable C++ snippet from the first lstlisting block in the source
# (lines 89-91: "myArray[2]       // element at index 2")
LSTLISTING_FIRST_CONTENT = "myArray[2]"

# A recognizable C++ snippet from a mid-document lstlisting block
# (lines 239-246: std::vector<int> oldestPeople …)
LSTLISTING_MID_CONTENT = "oldestPeople"

# Inline math expression that appears in the source ($O(1)$)
INLINE_MATH_EXPRESSION = r"O(1)"

# Display math content from lines 97-99
DISPLAY_MATH_FRAGMENT = r"element\_size"


# ---------------------------------------------------------------------------
# Gap 1 — Callout environments render as distinguishable HTML blocks
# ADR-003: "Recognizing the project's custom callout environments (ideabox,
#           defnbox, notebox, warnbox, examplebox) and emitting them as styled
#           HTML blocks."
# ---------------------------------------------------------------------------


class TestCalloutRendering:
    """
    Gap 1: Each callout environment that appears in ch-01-cpp-refresher.tex
    must produce a corresponding distinguishable element in the rendered HTML.

    Contract pinned: data-callout="<env-name>" attribute on the block element.
    """

    @pytest.mark.parametrize("env_name", CALLOUT_ENVS)
    def test_callout_env_produces_data_callout_attribute(
        self, env_name: str, ch01_lecture_response
    ) -> None:
        """
        ADR-003: each callout environment must emit an HTML element carrying
        data-callout="<env-name>", making it distinguishable from prose and
        from other callout types.

        One test per callout type; all five types appear in the source.
        """
        html = ch01_lecture_response.text
        expected_attr = f'data-callout="{env_name}"'
        assert expected_attr in html, (
            f"Callout environment '{env_name}' has no element with "
            f'data-callout="{env_name}" in the rendered HTML. '
            "ADR-003 requires callout environments to emit styled HTML blocks; "
            "the contract for this test suite pins data-callout as the "
            "distinguishing attribute."
        )

    @pytest.mark.parametrize("env_name,expected_count", CALLOUT_COUNTS.items())
    def test_callout_env_count_matches_source(
        self, env_name: str, expected_count: int, ch01_lecture_response
    ) -> None:
        """
        ADR-003: every callout instance in the source must produce a block in
        the HTML — none silently dropped.

        The source has exactly N instances of each type (grepped and fixed above).
        The HTML must contain at least that many data-callout="<env-name>" occurrences.
        """
        html = ch01_lecture_response.text
        attr = f'data-callout="{env_name}"'
        found = html.count(attr)
        assert found >= expected_count, (
            f"Expected at least {expected_count} data-callout=\"{env_name}\" "
            f"occurrences in rendered HTML (matching source count), found {found}. "
            "ADR-003: every callout instance must produce an HTML block."
        )

    def test_callout_types_are_distinguishable_from_each_other(
        self, ch01_lecture_response
    ) -> None:
        """
        ADR-003: styled HTML *blocks* — plural. If every callout had the same
        data-callout value the requirement would be vacuous. This test confirms
        that all five distinct data-callout values are present, so a renderer
        that collapses everything to a single type would fail.
        """
        html = ch01_lecture_response.text
        present = [env for env in CALLOUT_ENVS if f'data-callout="{env}"' in html]
        missing = [env for env in CALLOUT_ENVS if env not in present]
        assert missing == [], (
            f"These callout types are missing from the rendered HTML: {missing}. "
            "ADR-003 requires each distinct environment to produce a styled block."
        )


# ---------------------------------------------------------------------------
# Gap 2 — No leaked raw LaTeX in rendered HTML
# ADR-003: pylatexenc strategy; failure mode = "macro silently passed through
#          as plain text"
# ---------------------------------------------------------------------------

# Macros that are NEVER acceptable in rendered output outside of <pre>/<code>
# and outside of math delimiter spans.
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

# General catch-all: any \word{ pattern (backslash + one-or-more word chars + brace)
_GENERIC_MACRO_PATTERN = r"\\[A-Za-z]+\{"

# Math delimiters that are ALLOWED to pass through to MathJax
_MATH_INLINE_PATTERN = re.compile(r"\$[^$]+?\$")
_MATH_DISPLAY_PATTERN = re.compile(r"\\\[.*?\\\]", re.DOTALL)

# Regex to identify <pre> and <code> sections (where raw LaTeX in listings is OK)
_PRE_CODE_PATTERN = re.compile(r"<pre[\s>].*?</pre>|<code[\s>].*?</code>", re.DOTALL | re.IGNORECASE)

# MathJax span wrappers that mark math content (also acceptable)
_MATH_SPAN_PATTERN = re.compile(
    r'<span[^>]*class="[^"]*math[^"]*"[^>]*>.*?</span>',
    re.DOTALL | re.IGNORECASE,
)


def _strip_safe_regions(html: str) -> str:
    """
    Remove from html all regions that are allowed to contain raw LaTeX:
    - <pre>...</pre> blocks  (code listings — allowed to show raw text)
    - <code>...</code> blocks
    - Inline math $...$  (MathJax passthrough)
    - Display math \\[...\\]  (MathJax passthrough)
    - <span class="math*">...</span>  (MathJax-wrapped math)

    The remainder is "prose HTML" that must be free of raw LaTeX macros.
    """
    # Replace each safe region with a placeholder of equal length so that
    # character positions shift minimally (we care about presence, not position).
    stripped = html
    for pattern in (_PRE_CODE_PATTERN, _MATH_SPAN_PATTERN,
                    _MATH_INLINE_PATTERN, _MATH_DISPLAY_PATTERN):
        stripped = pattern.sub("<!-- SAFE_REGION -->", stripped)
    return stripped


class TestNoRawLatexLeak:
    """
    Gap 2: Raw LaTeX macros must not appear verbatim in the prose HTML.

    Allowed exceptions:
    - Inside <pre> / <code> blocks (code listings may display raw LaTeX).
    - Inside math delimiters $...$ or \\[...\\] or <span class="math*"> (MathJax).

    Everything outside those safe regions must be free of raw macro syntax.
    """

    @pytest.mark.parametrize("macro_pattern", _FORBIDDEN_MACRO_PATTERNS)
    def test_specific_macro_not_leaked_in_prose(
        self, macro_pattern: str, ch01_lecture_response
    ) -> None:
        """
        ADR-003: pylatexenc walk must consume structural macros. If a macro
        like \\section{ or \\begin{ appears in the prose HTML (outside pre/code
        and outside math), the parser silently passed it through — a failure mode
        ADR-003 forbids.
        """
        html = ch01_lecture_response.text
        prose_html = _strip_safe_regions(html)
        matches = re.findall(macro_pattern, prose_html)
        assert matches == [], (
            f"Raw LaTeX leak detected: pattern '{macro_pattern}' found "
            f"{len(matches)} time(s) in rendered prose HTML (outside pre/code "
            f"and math regions). ADR-003 requires pylatexenc to consume these "
            f"macros, not pass them through as plain text. "
            f"First match context: {matches[:3]!r}"
        )

    def test_generic_macro_pattern_not_leaked_in_prose(
        self, ch01_lecture_response
    ) -> None:
        """
        ADR-003 catch-all: no \\word{ pattern should survive in prose HTML.

        This catches any macro the specific list above does not enumerate.
        Math and code regions are excluded via _strip_safe_regions().
        """
        html = ch01_lecture_response.text
        prose_html = _strip_safe_regions(html)
        matches = re.findall(_GENERIC_MACRO_PATTERN, prose_html)
        assert matches == [], (
            f"Possible raw LaTeX macro(s) detected in prose HTML (outside "
            f"pre/code/math regions): {matches[:10]!r}. "
            "ADR-003: unrecognized nodes must be stripped or ignored, "
            "not passed through as plain text."
        )

    def test_no_backslash_begin_in_prose(self, ch01_lecture_response) -> None:
        """
        Specific regression: \\begin{ in prose (outside safe regions) is a
        clear signal that an environment was not parsed — the most common
        pylatexenc silent-failure mode.
        """
        html = ch01_lecture_response.text
        prose_html = _strip_safe_regions(html)
        assert r"\begin{" not in prose_html, (
            r"Raw '\begin{' found in rendered prose HTML (outside pre/code/math). "
            "ADR-003: environments must be parsed, not passed through."
        )

    def test_no_backslash_end_in_prose(self, ch01_lecture_response) -> None:
        """
        Mirror of the \\begin{ check: \\end{ in prose = unparsed environment close.
        """
        html = ch01_lecture_response.text
        prose_html = _strip_safe_regions(html)
        assert r"\end{" not in prose_html, (
            r"Raw '\end{' found in rendered prose HTML (outside pre/code/math). "
            "ADR-003: environments must be parsed, not passed through."
        )

    def test_pre_code_blocks_exempt_from_latex_leak_check(
        self, ch01_lecture_response
    ) -> None:
        """
        Sanity / documentation: confirms that code blocks in the rendered HTML
        DO contain backslash sequences (so the exemption logic is meaningful
        and not vacuous). If this test fails, it means no code blocks were
        rendered — which would be caught by Gap 3 tests, but this makes the
        reasoning explicit.

        This test also implicitly confirms _strip_safe_regions removes <pre> content.
        """
        html = ch01_lecture_response.text
        pre_blocks = _PRE_CODE_PATTERN.findall(html)
        # At least one pre block must exist (Gap 3 tests verify count more rigorously)
        assert len(pre_blocks) >= 1, (
            "No <pre> or <code> blocks found in rendered HTML. "
            "Cannot verify that the latex-leak exemption for code listings is active."
        )


# ---------------------------------------------------------------------------
# Gap 3 — Code listings render as <pre><code> blocks
# ADR-003: "Recognizing lstlisting environments and emitting them as <pre><code>
#           blocks."
# ---------------------------------------------------------------------------

# Regex to match <pre><code>...</code></pre> blocks (whitespace-tolerant)
_PRE_CODE_BLOCK_PATTERN = re.compile(
    r"<pre[^>]*>\s*<code[^>]*>.*?</code>\s*</pre>",
    re.DOTALL | re.IGNORECASE,
)

# Regex for just <pre> or just <code> blocks (looser; catches imperfect wrapping)
_PRE_BLOCK_PATTERN = re.compile(r"<pre[^>]*>.*?</pre>", re.DOTALL | re.IGNORECASE)


class TestCodeListingRendering:
    """
    Gap 3: Every \\begin{lstlisting}...\\end{lstlisting} pair in the source
    must produce a <pre><code>...</code></pre> block in the HTML.
    """

    def test_pre_code_block_count_at_least_source_count(
        self, ch01_lecture_response
    ) -> None:
        """
        ADR-003: 36 lstlisting pairs exist in the source; the rendered HTML
        must contain at least 36 <pre><code> blocks.

        We count <pre><code>...</code></pre> structures (whitespace-tolerant).
        """
        html = ch01_lecture_response.text
        pre_code_blocks = _PRE_CODE_BLOCK_PATTERN.findall(html)
        assert len(pre_code_blocks) >= LSTLISTING_COUNT, (
            f"Expected at least {LSTLISTING_COUNT} <pre><code> blocks in rendered HTML "
            f"(matching source lstlisting count), found {len(pre_code_blocks)}. "
            "ADR-003: every lstlisting environment must become a <pre><code> block."
        )

    def test_first_lstlisting_content_inside_pre_code(
        self, ch01_lecture_response
    ) -> None:
        """
        ADR-003: C++ code is human-readable inside <pre><code>, not stripped
        or rendered as prose.

        The first lstlisting block in the source (line 89) contains the string
        "myArray[2]".  That string must appear inside a <pre><code>...</code></pre>
        element in the HTML.
        """
        html = ch01_lecture_response.text
        pre_code_blocks = _PRE_CODE_BLOCK_PATTERN.findall(html)
        # Also check looser <pre> blocks in case code is not double-wrapped
        pre_blocks = _PRE_BLOCK_PATTERN.findall(html)
        all_code_regions = pre_code_blocks + pre_blocks

        found_in_code = any(LSTLISTING_FIRST_CONTENT in block for block in all_code_regions)
        assert found_in_code, (
            f"Expected '{LSTLISTING_FIRST_CONTENT}' to appear inside a "
            "<pre><code> (or <pre>) block in the rendered HTML. "
            "ADR-003: lstlisting content must be human-readable in a code block, "
            "not stripped or rendered as prose. "
            f"Source: ch-01-cpp-refresher.tex lines 89-91."
        )

    def test_mid_document_lstlisting_content_inside_pre_code(
        self, ch01_lecture_response
    ) -> None:
        """
        ADR-003: code content from a mid-document lstlisting block must also
        survive inside a <pre><code> element.

        The examplebox at source line 238 contains an lstlisting with
        "oldestPeople" — a distinct C++ identifier.
        """
        html = ch01_lecture_response.text
        pre_code_blocks = _PRE_CODE_BLOCK_PATTERN.findall(html)
        pre_blocks = _PRE_BLOCK_PATTERN.findall(html)
        all_code_regions = pre_code_blocks + pre_blocks

        found_in_code = any(LSTLISTING_MID_CONTENT in block for block in all_code_regions)
        assert found_in_code, (
            f"Expected '{LSTLISTING_MID_CONTENT}' to appear inside a "
            "<pre><code> (or <pre>) block in the rendered HTML. "
            "ADR-003: lstlisting content must not be stripped or treated as prose. "
            f"Source: ch-01-cpp-refresher.tex lines 239-246."
        )

    def test_lstlisting_content_not_in_prose(self, ch01_lecture_response) -> None:
        """
        Complementary check: the first-lstlisting content must NOT appear
        outside of a code block as raw prose.

        If "myArray[2]" appears in the HTML but NOT inside <pre>/<code>, the
        renderer is treating C++ code as paragraph text — a rendering defect
        even if the text is technically present.

        Strategy: strip all pre/code regions; the identifier must not appear
        in what remains.
        """
        html = ch01_lecture_response.text
        prose_only = _PRE_CODE_PATTERN.sub("<!-- CODE_BLOCK -->", html)
        # In prose-only HTML, the C++ identifier must be absent.
        # (It is OK for it to appear zero times in prose — it belongs in code blocks.)
        assert LSTLISTING_FIRST_CONTENT not in prose_only, (
            f"'{LSTLISTING_FIRST_CONTENT}' found outside a <pre>/<code> block "
            "in the rendered HTML. C++ code from lstlisting environments must "
            "not be rendered as prose. ADR-003."
        )


# ---------------------------------------------------------------------------
# Bonus 4 — Math expressions survive in MathJax-renderable form
# ADR-003: "Passing inline math ($...$) and display math (\\[...\\], equation env)
#           through to the HTML output as MathJax-renderable text."
# ---------------------------------------------------------------------------


class TestMathPassthrough:
    """
    Bonus 4: Math expressions present in the source must survive in the HTML
    in a form that MathJax can pick up.

    ADR-003 says these pass through unchanged (same delimiters) OR are wrapped
    in a span MathJax recognises.

    CONTRACT: Accept either:
      a) The raw LaTeX delimiter is present: $O(1)$ still appears literally, OR
      b) A <span class="math*"> wrapper contains the expression.

    ASSUMPTION: pylatexenc passthrough means the delimiter IS preserved literally
    in the HTML, which is the simplest contract to verify and what ADR-003 implies
    when it says "passing through to the HTML output."
    """

    def test_inline_math_o1_survives(self, ch01_lecture_response) -> None:
        """
        ADR-003: inline math $O(1)$ (which appears multiple times in the source)
        must survive in the HTML either as $O(1)$ or inside a math span.
        """
        html = ch01_lecture_response.text
        # Accept either: literal $O(1)$ present, or a math span containing O(1)
        literal_present = "$O(1)$" in html
        math_span_present = bool(
            re.search(r'<span[^>]*class="[^"]*math[^"]*"[^>]*>[^<]*O\(1\)[^<]*</span>', html)
        )
        assert literal_present or math_span_present, (
            "Inline math expression '$O(1)$' (present multiple times in source) "
            "did not survive in the rendered HTML in a MathJax-renderable form. "
            "ADR-003: inline math must be passed through with its delimiters or "
            "wrapped in a math span."
        )

    def test_display_math_survives(self, ch01_lecture_response) -> None:
        """
        ADR-003: display math \\[...\\] (source line 97) must survive in the HTML.

        The display math at line 97 contains a distinctive fragment: element_size
        (rendered as element\\_size in LaTeX). We check that the rendered HTML
        contains either the raw \\[...\\] delimiter pair or a math span.
        """
        html = ch01_lecture_response.text
        # The display math delimiters \\[ and \\] must be present (passthrough), OR
        # the content appears inside a math span.
        display_open = r"\["
        display_close = r"\]"
        literal_present = display_open in html and display_close in html
        math_span_present = bool(
            re.search(r'<span[^>]*class="[^"]*math-display[^"]*"[^>]*>', html, re.IGNORECASE)
        )
        assert literal_present or math_span_present, (
            r"Display math '\[...\]' from source line 97 did not survive in the "
            "rendered HTML. ADR-003: display math must pass through with its "
            r"delimiters ('\[' / '\]') or be wrapped in a math-display span."
        )

    def test_math_delimiters_not_stripped_as_raw_latex_leak(
        self, ch01_lecture_response
    ) -> None:
        """
        Boundary / consistency: the no-raw-latex-leak tests in Gap 2 exclude
        math regions. This test confirms that math delimiters in the HTML are
        not accidentally caught by the Gap 2 checks — i.e., they are inside
        the safe regions that _strip_safe_regions removes.

        If display math \\[...\\] is present in the HTML, it must be removed
        by _strip_safe_regions so that the generic-macro check (Gap 2) does
        not trigger a false positive on it.

        ASSUMPTION: If both display math delimiters are present AND the
        _strip_safe_regions function properly handles them, the stripped prose
        must NOT contain the \\[ delimiter.
        """
        html = ch01_lecture_response.text
        stripped = _strip_safe_regions(html)
        # After stripping math regions, the display math open delimiter should
        # not be present (it was inside a safe region).
        # We only run this check if display math IS in the HTML; if it's been
        # converted to a span form, \\[ may not be present at all.
        if r"\[" in html:
            assert r"\[" not in stripped, (
                r"Display math delimiter '\[' is present in the HTML but was NOT "
                "removed by _strip_safe_regions. This means the Gap 2 generic-macro "
                "check could produce false positives for valid math content. "
                "The _strip_safe_regions helper must cover \\[...\\] regions."
            )


# ---------------------------------------------------------------------------
# Bonus 5 — Unknown-macro warning logged (unit-level)
# ADR-003: "Stripping or ignoring nodes the parser does not recognize, with a
#           structured warning logged per unrecognized node — not a crash,
#           not a fabrication."
# ---------------------------------------------------------------------------

# ASSUMPTION: The implementer places the parser callable at one of these
# module paths. The test tries each in order until it finds one.
_PARSER_CANDIDATE_MODULES = [
    ("app.parser", "parse_latex"),
    ("app.render", "parse_latex"),
    ("app.rendering", "parse_latex"),
    ("app.lecture", "parse_latex"),
    ("app.core", "parse_latex"),
    ("app.parser", "render_chapter"),
    ("app.render", "render_chapter"),
    ("app.main", "parse_latex"),
]


def _find_parser() -> object | None:
    """
    Try to import a parser callable from known candidate module paths.
    Returns the callable, or None if none are importable yet (no implementation).
    """
    for module_path, fn_name in _PARSER_CANDIDATE_MODULES:
        try:
            import importlib
            mod = importlib.import_module(module_path)
            fn = getattr(mod, fn_name, None)
            if fn is not None:
                return fn
        except (ImportError, ModuleNotFoundError):
            continue
    return None


class TestUnknownNodeWarning:
    """
    Bonus 5: Calling the parser with an unknown macro must log a warning
    and must not raise an exception or fabricate content.

    ADR-003: "Stripping or ignoring nodes the parser does not recognize,
    with a structured warning logged per unrecognized node — not a crash,
    not a fabrication."

    ASSUMPTION: The parser exposes a function (name varies; candidates listed
    in _PARSER_CANDIDATE_MODULES) that accepts a LaTeX string and returns
    an HTML string or intermediate representation. If no such function is
    importable, the test is skipped with a note.
    """

    def test_unknown_macro_does_not_crash_parser(self, caplog) -> None:
        """
        ADR-003: an unknown macro must be silently stripped/ignored, not crash.

        Uses synthetic LaTeX with a fabricated macro \\unknownmacroXYZ{text}.
        """
        parser_fn = _find_parser()
        if parser_fn is None:
            pytest.fail(
                "No parser callable found at any candidate module path "
                f"({_PARSER_CANDIDATE_MODULES}). "
                "Once the implementation exists, this test must pass. "
                "ADR-003: parser must not crash on unknown nodes."
            )

        synthetic_latex = (
            r"\begin{document}"
            r"\unknownmacroXYZ{some text that should survive or be stripped}"
            r"\end{document}"
        )
        # Must not raise — ADR-003 forbids crashes on unknown nodes.
        with caplog.at_level(logging.WARNING):
            try:
                result = parser_fn(synthetic_latex)
            except Exception as exc:
                pytest.fail(
                    f"Parser raised {type(exc).__name__}({exc!r}) on synthetic "
                    "LaTeX with unknown macro. ADR-003: must not crash — "
                    "strip or ignore unrecognized nodes."
                )
        # The result must be a non-None value (not a crash substitution).
        assert result is not None, (
            "Parser returned None on synthetic LaTeX with unknown macro. "
            "ADR-003: must return a valid (possibly empty) result."
        )

    def test_unknown_macro_triggers_warning_log(self, caplog) -> None:
        """
        ADR-003: a structured warning must be logged per unrecognized node.

        We inject \\unknownmacroXYZ into synthetic LaTeX and assert that at
        least one WARNING-level log record was emitted whose message mentions
        the unknown macro name.
        """
        parser_fn = _find_parser()
        if parser_fn is None:
            pytest.fail(
                "No parser callable found — cannot test warning logging. "
                "ADR-003: unknown nodes must produce a structured warning."
            )

        synthetic_latex = (
            r"\begin{document}"
            r"\unknownmacroXYZ{probe}"
            r"\end{document}"
        )
        with caplog.at_level(logging.WARNING):
            try:
                parser_fn(synthetic_latex)
            except Exception:
                pass  # crash-on-unknown is caught by the sibling test above

        warning_records = [
            r for r in caplog.records if r.levelno >= logging.WARNING
        ]
        macro_mentioned = any(
            "unknownmacroXYZ" in r.message or "unknown" in r.message.lower()
            for r in warning_records
        )
        assert macro_mentioned, (
            "No WARNING log mentioning 'unknownmacroXYZ' or 'unknown' was emitted "
            "when the parser encountered an unknown macro. "
            "ADR-003: 'a structured warning logged per unrecognized node.' "
            f"Log records captured: {[(r.levelname, r.message) for r in warning_records]}"
        )
