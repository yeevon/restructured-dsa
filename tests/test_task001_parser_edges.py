"""
Parser robustness edge cases for TASK-001 (Category B).

These tests exercise the parser/renderer with synthetic LaTeX strings — NOT
the real ch-01-cpp-refresher.tex source.  Each synthetic fixture is small
and self-contained.  The tests call the parser function directly (unit-style)
wherever possible; they fall back to a tempdir-as-source approach when the
renderer is hardwired to read from a file path.

TEMPDIR FALLBACK RATIONALE: ADR-003 fixes the route as
  GET /lecture/{chapter_id} → read content/latex/{chapter_id}.tex
If the renderer's internal pipeline is exposed as a callable that takes a
LaTeX string, the unit-style approach is used directly.  If the renderer only
operates on disk paths (common in pylatexenc-based implementations), the tests
write a minimal .tex file to a temporary directory and monkeypatch the renderer's
source root to point there.  Both approaches test the same contract.

PINNED CONTRACTS (recorded here and in each test docstring):

  B7 — Empty document body:
    Renders without crashing; the returned HTML contains a Mandatory or Optional
    badge (designation is chapter-level, not section-derived); zero section
    anchors are emitted.

  B8 — No \\section macros:
    Renders without crashing; zero <section id="section-..."> anchors emitted.

  B9 — Section without leading number:
    ADR-002: 'renderer fails loudly.'
    PINNED: the parser raises ValueError or RuntimeError (structured error).
    The route MAY translate this to a 4xx; the unit test checks the raise.
    Must NOT silently emit a Section with a fabricated ID.

  B10 — Special characters in section headings:
    HTML output escapes &, <, > properly (no raw HTML injection).

  B11 — Inline math in section heading:
    Math survives in the heading as MathJax-renderable text (either literal
    delimiter or span wrapper, same contract as Bonus 4 in rendering fidelity).

  B12 — Empty callout:
    \\begin{ideabox}\\end{ideabox} emits a data-callout="ideabox" block
    (possibly empty body) without crashing.

  B13 — Empty lstlisting:
    \\begin{lstlisting}\\end{lstlisting} emits a <pre><code> block
    (possibly empty body) without crashing.

  B14 — Unclosed environment:
    PINNED: the parser does NOT crash; it either:
      (a) logs a structured WARNING per ADR-003 and recovers (returning HTML),
       OR
      (b) raises a structured ValueError/RuntimeError that the route translates
          to a 4xx.
    Fabricating content to fill the gap is forbidden (ADR-002/ADR-003
    no-fabrication principle).

pytestmark registers all tests under task("TASK-001").
"""

import importlib
import logging
import os
import pathlib
import textwrap
import tempfile

import pytest

pytestmark = pytest.mark.task("TASK-001")


# ---------------------------------------------------------------------------
# Helpers: find the parser callable and the source-root injectable render fn
# ---------------------------------------------------------------------------

_PARSER_CANDIDATES = [
    ("app.parser", "parse_latex"),
    ("app.render", "parse_latex"),
    ("app.rendering", "parse_latex"),
    ("app.lecture", "parse_latex"),
    ("app.core", "parse_latex"),
]

_RENDER_CHAPTER_CANDIDATES = [
    ("app.parser", "render_chapter"),
    ("app.render", "render_chapter"),
    ("app.rendering", "render_chapter"),
    ("app.lecture", "render_chapter"),
    ("app.core", "render_chapter"),
    ("app.main", "render_chapter"),
]

_EXTRACT_SECTIONS_CANDIDATES = [
    ("app.parser", "extract_sections"),
    ("app.render", "extract_sections"),
    ("app.rendering", "extract_sections"),
    ("app.lecture", "extract_sections"),
    ("app.core", "extract_sections"),
    ("app.identity", "extract_sections"),
]


def _find_callable(candidate_list: list[tuple[str, str]]) -> object | None:
    """Try each (module, fn_name) pair; return the first callable found."""
    for module_path, fn_name in candidate_list:
        try:
            mod = importlib.import_module(module_path)
            fn = getattr(mod, fn_name, None)
            if fn is not None:
                return fn
        except (ImportError, ModuleNotFoundError):
            continue
    return None


def _get_parser():
    """
    Return the parser callable that accepts a LaTeX string and returns HTML (or IR).

    ASSUMPTION: the implementer exposes a callable at one of the candidate paths
    that takes at minimum a LaTeX body string.  If none is found, tests that need
    this callable will FAIL with an informative message (not silently pass).
    """
    fn = _find_callable(_PARSER_CANDIDATES)
    if fn is None:
        raise ImportError(
            "Cannot import a parser callable from any of: "
            + str([m for m, _ in _PARSER_CANDIDATES])
            + ". ADR-003: the pipeline must expose a callable for these unit tests."
        )
    return fn


def _get_extract_sections():
    """
    Return extract_sections(chapter_id, latex_body) -> list[Section].

    ASSUMPTION: the implementer exposes extract_sections per the ADR-002 contract.
    """
    fn = _find_callable(_EXTRACT_SECTIONS_CANDIDATES)
    if fn is None:
        raise ImportError(
            "Cannot import 'extract_sections' from any expected module. "
            "ADR-002 requires a function that parses section macros from a LaTeX body."
        )
    return fn


def _get_render_chapter():
    """
    Return a render_chapter(chapter_id, source_root=...) callable, used as the
    tempdir-based fallback when the parser is hardwired to disk paths.

    ASSUMPTION: the implementer exposes render_chapter with a signature that
    accepts at least a chapter_id; optionally a source_root or content_dir kwarg.
    """
    return _find_callable(_RENDER_CHAPTER_CANDIDATES)


# ---------------------------------------------------------------------------
# B7 — Empty document body
# ---------------------------------------------------------------------------


def test_b7_empty_document_body_does_not_crash():
    """
    B7: \\begin{document}\\end{document} must not raise an exception.

    Trace: ADR-003 robustness — the parser must not crash on edge-case bodies.
    """
    parser = _get_parser()
    minimal_latex = r"\begin{document}\end{document}"
    try:
        result = parser(minimal_latex)
    except Exception as exc:
        pytest.fail(
            f"Parser raised {type(exc).__name__}({exc!r}) on empty document body. "
            "ADR-003: the pipeline must not crash — it should produce an empty "
            "but valid HTML page."
        )
    assert result is not None, (
        "Parser returned None for an empty document body. "
        "ADR-003: must return a valid (possibly empty) result."
    )


def test_b7_empty_document_body_has_zero_section_anchors():
    """
    B7: An empty document body must produce zero Section anchors.

    ADR-002: Section anchors are derived from \\section macros.  No \\section
    macros → no anchors.  The designation badge may still appear (it is per-
    chapter, not per-section).

    Trace: ADR-002; ADR-003.
    """
    import re as _re

    parser = _get_parser()
    minimal_latex = r"\begin{document}\end{document}"
    try:
        result = parser(minimal_latex)
    except Exception:
        pytest.fail("Parser crashed on empty document body — see B7 no-crash test.")

    html = str(result) if result is not None else ""
    section_ids = _re.findall(r'id="section-\d+-\d+"', html)
    assert section_ids == [], (
        f"Empty document body produced {len(section_ids)} section anchor(s): "
        f"{section_ids}. ADR-002: section anchors derive from \\section macros only."
    )


# ---------------------------------------------------------------------------
# B8 — Document with prose but no \\section macros
# ---------------------------------------------------------------------------


def test_b8_no_section_macros_does_not_crash():
    """
    B8: A document body with prose but no \\section macros must not crash.

    Trace: ADR-003 robustness; ADR-002 (zero sections is a valid document state).
    """
    parser = _get_parser()
    latex_body = (
        r"\begin{document}"
        "\nSome introductory text here.\n"
        r"This paragraph has no section."
        r"\end{document}"
    )
    try:
        result = parser(latex_body)
    except Exception as exc:
        pytest.fail(
            f"Parser raised {type(exc).__name__}({exc!r}) on a document with no "
            "\\section macros. ADR-003: must not crash on edge-case content."
        )
    assert result is not None


def test_b8_no_section_macros_yields_zero_section_anchors():
    """
    B8: prose-only body → zero <section id="section-*"> anchors.

    Trace: ADR-002; ADR-003.
    """
    import re as _re

    parser = _get_parser()
    latex_body = (
        r"\begin{document}"
        "\nSome introductory text here.\n"
        r"\end{document}"
    )
    try:
        result = parser(latex_body)
    except Exception:
        pytest.fail("Parser crashed on prose-only body — see B8 no-crash test.")

    html = str(result) if result is not None else ""
    section_ids = _re.findall(r'id="section-\d+-\d+"', html)
    assert section_ids == [], (
        f"Prose-only body produced {len(section_ids)} section anchor(s): {section_ids}. "
        "ADR-002: \\section macros are the only source of section anchors."
    )


# ---------------------------------------------------------------------------
# B9 — Section without leading number → fail loudly
# ---------------------------------------------------------------------------


def test_b9_section_without_leading_number_raises():
    """
    B9: A \\section macro without a leading numeric pattern must cause the
    parser/extract_sections to raise a structured error, not fabricate an ID.

    PINNED CONTRACT: ValueError or RuntimeError is raised.
    Rationale: ADR-002 states 'the renderer fails loudly rather than fabricating
    a Section ID.'  'Fails loudly' = raises a structured Python exception at
    the boundary the unit tests can observe.  At the HTTP layer, the route
    MAY translate this to a 4xx (HTTP 422 is reasonable); see test_b9_http below.

    Trace: ADR-002 'fail loudly'; manifest §6 no-fabrication principle.
    """
    extract_sections = _get_extract_sections()
    latex_body = r"\section{Introduction}  % no leading number pattern"
    with pytest.raises((ValueError, RuntimeError), match=""):
        extract_sections("ch-01-cpp-refresher", latex_body)


def test_b9_section_without_leading_number_does_not_emit_fabricated_id():
    """
    B9 complementary: even if the parser does NOT raise (e.g., it returns an
    error sentinel instead of raising), the returned data must not include a
    Section with a fabricated ID.

    ADR-002: 'the renderer fails loudly rather than fabricating a Section ID.'

    Two possible behaviors are acceptable:
      1. A Python exception is raised (tested above).
      2. An empty list is returned (no sections fabricated).

    Returning a section with id="section-introduction" or any fabricated slug
    is NOT acceptable.

    Trace: ADR-002; manifest §6.
    """
    extract_sections = _get_extract_sections()
    latex_body = r"\section{Introduction}"

    try:
        sections = extract_sections("ch-01-cpp-refresher", latex_body)
    except (ValueError, RuntimeError):
        # Raising is acceptable — this is the primary pinned contract.
        return

    # If we reach here, no exception was raised.  Assert no fabricated ID.
    ids = [s.get("id") if isinstance(s, dict) else getattr(s, "id", None)
           for s in (sections or [])]
    fabricated = [
        sid for sid in ids
        if sid is not None and "section-" in str(sid).lower()
        and not any(
            str(sid).lower().endswith(f"section-{n}")
            for n in [str(i) for i in range(100)]
        )
    ]
    # More direct check: none of the returned IDs should exist
    # (no fabricated numeric section ID can be derived from unnumbered heading)
    assert (sections is None or len(sections) == 0), (
        f"extract_sections did not raise for unnumbered \\section{{Introduction}}, "
        f"and returned non-empty sections: {sections}. "
        "ADR-002: must fail loudly, not fabricate. Either raise or return empty."
    )


def test_b9_section_without_leading_number_via_http_returns_4xx():
    """
    B9 at the HTTP layer: if a chapter file contains a \\section without a
    leading number, the route must return a 4xx, not a 200 with fabricated IDs.

    PINNED CONTRACT: HTTP 4xx (404 or 422 or 500 are all 'fail loudly';
    200 with fabricated content is NOT acceptable).

    Strategy: write a synthetic .tex file to a tempdir, monkeypatch the
    renderer's source root to that tempdir, then GET the chapter.

    ASSUMPTION: the renderer accepts a 'content_root' or 'source_root'
    configuration injectable at app startup or via a dependency. If it does
    not, this test falls back to a skip with a documented rationale.

    Trace: ADR-002; ADR-003.
    """
    from fastapi.testclient import TestClient  # noqa: PLC0415
    try:
        from app.main import app  # noqa: PLC0415
    except ImportError:
        pytest.fail("app.main is not importable — implementation does not exist yet.")

    # Attempt to find a source-root injectable config
    source_root_injectable = False
    try:
        import app.config as _cfg  # noqa: PLC0415
        if hasattr(_cfg, "CONTENT_ROOT") or hasattr(_cfg, "SOURCE_ROOT"):
            source_root_injectable = True
    except ImportError:
        pass

    if not source_root_injectable:
        pytest.skip(
            "Cannot inject a synthetic source root — the renderer does not expose "
            "a testable source_root configuration.  "
            "RATIONALE: this test requires the renderer to accept a source_root "
            "kwarg or environment variable so that a synthetic .tex file can be "
            "substituted for the real content.  Once the implementer adds that "
            "configuration seam (recommended for full test isolation), remove this "
            "skip and activate the full test."
        )

    with tempfile.TemporaryDirectory() as tmpdir:
        # Write a .tex file with an unnumbered section
        fake_tex = pathlib.Path(tmpdir) / "ch-synthetic-bad-section.tex"
        fake_tex.write_text(
            textwrap.dedent(r"""
                \documentclass{article}
                \begin{document}
                \section{Introduction}
                Some prose.
                \end{document}
            """),
            encoding="utf-8",
        )
        # Monkeypatch the source root
        try:
            import app.config as _cfg  # noqa: PLC0415
            original = getattr(_cfg, "CONTENT_ROOT", getattr(_cfg, "SOURCE_ROOT", None))
            attr_name = "CONTENT_ROOT" if hasattr(_cfg, "CONTENT_ROOT") else "SOURCE_ROOT"
            setattr(_cfg, attr_name, tmpdir)
            client = TestClient(app)
            response = client.get("/lecture/ch-synthetic-bad-section")
            setattr(_cfg, attr_name, original)
        except Exception as exc:
            pytest.skip(
                f"Monkeypatching source root raised {type(exc).__name__}: {exc}. "
                "Skipping HTTP-layer B9 check."
            )

        assert response.status_code != 200, (
            f"GET /lecture/ch-synthetic-bad-section returned 200 for a chapter "
            f"with an unnumbered \\section. ADR-002: must fail loudly. "
            f"Response body fragment: {response.text[:300]!r}"
        )


# ---------------------------------------------------------------------------
# B10 — Special characters in section headings (HTML escaping)
# ---------------------------------------------------------------------------


def test_b10_special_chars_in_heading_are_html_escaped():
    """
    B10: Section heading text containing &, <, > must be HTML-escaped in output.

    Input: \\section{1.1 Code & data <stuff>}
    Expected: the heading in the HTML contains &amp; for &, &lt; for <,
              &gt; for > — no raw ampersands or angle brackets that could
              break the HTML structure or create XSS-shaped output.

    PINNED CONTRACT: standard HTML entity escaping is required.  This is not
    an explicit ADR-003 statement but is implied by 'renders the chapter's
    prose readably' (TASK-001 AC1) and by any correct HTML output.

    Trace: ADR-003 output format ('one HTML page'); TASK-001 AC1.
    """
    import html as _html
    import re as _re

    extract_sections = _get_extract_sections()
    latex_body = r"\section{1.1 Code & data <stuff>}"

    try:
        sections = extract_sections("ch-01-cpp-refresher", latex_body)
    except (ValueError, RuntimeError) as exc:
        # If the parser rejects this as malformed, that is fine too —
        # the key contract is no XSS-shaped raw output.
        pytest.skip(
            f"extract_sections raised {type(exc).__name__} on heading with "
            "special characters — the fail-loudly path was taken, which satisfies "
            "the no-fabrication contract. HTML-escape test not applicable."
        )

    if not sections:
        return  # No sections emitted; no escaping issue possible.

    # Get the heading text from the first section
    first = sections[0]
    heading = (
        first.get("heading") or first.get("title") or first.get("text")
        if isinstance(first, dict)
        else (
            getattr(first, "heading", None)
            or getattr(first, "title", None)
            or getattr(first, "text", None)
        )
    )
    if heading is None:
        # Can't introspect heading; fall through gracefully
        return

    heading_str = str(heading)
    # Must not contain raw & < > in a context that would break HTML
    assert "&amp;" in heading_str or "&" not in heading_str, (
        f"Heading contains raw '&' instead of '&amp;': {heading_str!r}. "
        "HTML escaping is required for all text inserted into HTML output."
    )
    assert "&lt;" in heading_str or "<" not in heading_str, (
        f"Heading contains raw '<' instead of '&lt;': {heading_str!r}. "
        "HTML escaping is required; raw '<' can break HTML structure."
    )
    assert "&gt;" in heading_str or ">" not in heading_str, (
        f"Heading contains raw '>' instead of '&gt;': {heading_str!r}. "
        "HTML escaping is required."
    )


def test_b10_special_chars_not_present_raw_in_html_output():
    """
    B10 integration variant: render a synthetic document with special chars
    in the section heading via the full parser and assert the HTML output is
    well-formed (no raw & < > in the heading region).

    Trace: ADR-003; TASK-001 AC1.
    """
    import re as _re

    parser = _get_parser()
    latex_body = (
        r"\begin{document}" + "\n"
        r"\section{1.1 Code & data <stuff>}" + "\n"
        r"Some content." + "\n"
        r"\end{document}"
    )

    try:
        result = parser(latex_body)
    except (ValueError, RuntimeError):
        # Fail-loud path is acceptable; the test goal is to prevent silent XSS.
        return
    except Exception as exc:
        pytest.fail(
            f"Parser raised unexpected {type(exc).__name__}({exc!r}) on heading "
            "with special characters."
        )

    html = str(result) if result is not None else ""
    # In the heading region we must not find raw & < > — they must be escaped.
    # We look for patterns like ">Code & data<" which indicates raw ampersand in HTML.
    raw_ampersand_in_content = _re.search(r">[^<]*&[^<]*<", html)
    assert not raw_ampersand_in_content, (
        "Raw '&' found between HTML tags — possible unescaped content from "
        "section heading '1.1 Code & data <stuff>'. "
        "All text inserted into HTML must be escaped. "
        f"Context: {raw_ampersand_in_content.group()!r}"
    )


# ---------------------------------------------------------------------------
# B11 — Inline math in section heading
# ---------------------------------------------------------------------------


def test_b11_inline_math_in_section_heading_survives():
    """
    B11: \\section{1.1 Big-O of $O(n^2)$} — math in the heading must survive
    in the rendered HTML in a MathJax-renderable form.

    ADR-003: 'passing inline math ($...$) … through to the HTML output as
    MathJax-renderable text.' The same contract applies to math that appears
    inside a section heading, not just in body prose.

    PINNED CONTRACT: the rendered HTML must contain either:
      (a) the literal string $O(n^2)$ (or $O(n^{2})$ — brace-preserved form), OR
      (b) a <span class="math*"> wrapping the expression.

    Trace: ADR-003 math passthrough; TASK-001 AC2 (section as addressable region).
    """
    import re as _re

    parser = _get_parser()
    latex_body = (
        r"\begin{document}" + "\n"
        r"\section{1.1 Big-O of $O(n^2)$}" + "\n"
        r"Some content." + "\n"
        r"\end{document}"
    )

    try:
        result = parser(latex_body)
    except (ValueError, RuntimeError) as exc:
        pytest.skip(
            f"Parser raised structured error ({type(exc).__name__}) on heading "
            "with inline math — fail-loud path, math test not applicable here."
        )
    except Exception as exc:
        pytest.fail(
            f"Parser raised unexpected {type(exc).__name__}({exc!r}) on heading "
            "with inline math. ADR-003: must not crash."
        )

    html = str(result) if result is not None else ""
    # Accept literal math delimiter OR a span wrapper
    literal_math_present = "O(n^2)" in html or "O(n^{2})" in html
    span_math_present = bool(
        _re.search(r'<span[^>]*class="[^"]*math[^"]*"[^>]*>', html, _re.IGNORECASE)
    )
    assert literal_math_present or span_math_present, (
        "Inline math '$O(n^2)$' in section heading did not survive in the "
        "rendered HTML in a MathJax-renderable form. "
        "ADR-003: inline math must pass through with its delimiters or be "
        "wrapped in a math span — even when the math appears inside a heading."
    )


# ---------------------------------------------------------------------------
# B12 — Empty callout environment
# ---------------------------------------------------------------------------


def test_b12_empty_ideabox_does_not_crash():
    """
    B12: \\begin{ideabox}\\end{ideabox} (empty body) must not crash the parser.

    ADR-003: 'Recognizing the project's custom callout environments … and
    emitting them as styled HTML blocks.'  An empty environment is still a
    valid environment.

    Trace: ADR-003; TASK-001 AC1 (renders readably — empty callout is allowed).
    """
    parser = _get_parser()
    latex_body = (
        r"\begin{document}" + "\n"
        r"\begin{ideabox}\end{ideabox}" + "\n"
        r"\end{document}"
    )
    try:
        result = parser(latex_body)
    except Exception as exc:
        pytest.fail(
            f"Parser raised {type(exc).__name__}({exc!r}) on empty ideabox. "
            "ADR-003: must not crash on empty callout environments."
        )
    assert result is not None


def test_b12_empty_ideabox_emits_data_callout_attribute():
    """
    B12: An empty ideabox must emit an element with data-callout="ideabox".

    CONTRACT pinned: data-callout="ideabox" attribute (same contract as Gap 1
    in test_task001_rendering_fidelity.py).

    Trace: ADR-003; Run 004 pinned contract.
    """
    parser = _get_parser()
    latex_body = (
        r"\begin{document}" + "\n"
        r"\begin{ideabox}\end{ideabox}" + "\n"
        r"\end{document}"
    )
    try:
        result = parser(latex_body)
    except Exception:
        pytest.fail("Parser crashed on empty ideabox — see B12 no-crash test.")

    html = str(result) if result is not None else ""
    assert 'data-callout="ideabox"' in html, (
        "Empty \\begin{ideabox}\\end{ideabox} did not produce an element with "
        'data-callout="ideabox" in the HTML. '
        "ADR-003: every callout environment, even empty, must emit a styled block."
    )


# ---------------------------------------------------------------------------
# B13 — Empty lstlisting
# ---------------------------------------------------------------------------


def test_b13_empty_lstlisting_does_not_crash():
    """
    B13: \\begin{lstlisting}\\end{lstlisting} (empty body) must not crash.

    ADR-003: 'Recognizing lstlisting environments and emitting them as
    <pre><code> blocks.'  An empty listing is a valid edge case.

    Trace: ADR-003.
    """
    parser = _get_parser()
    latex_body = (
        r"\begin{document}" + "\n"
        r"\begin{lstlisting}" + "\n"
        r"\end{lstlisting}" + "\n"
        r"\end{document}"
    )
    try:
        result = parser(latex_body)
    except Exception as exc:
        pytest.fail(
            f"Parser raised {type(exc).__name__}({exc!r}) on empty lstlisting. "
            "ADR-003: must not crash on empty code listing environments."
        )
    assert result is not None


def test_b13_empty_lstlisting_emits_pre_code_block():
    """
    B13: An empty lstlisting must emit a <pre> or <pre><code> block.

    ADR-003: 'lstlisting environments … emitting them as <pre><code> blocks.'

    Trace: ADR-003.
    """
    import re as _re

    parser = _get_parser()
    latex_body = (
        r"\begin{document}" + "\n"
        r"\begin{lstlisting}" + "\n"
        r"\end{lstlisting}" + "\n"
        r"\end{document}"
    )
    try:
        result = parser(latex_body)
    except Exception:
        pytest.fail("Parser crashed on empty lstlisting — see B13 no-crash test.")

    html = str(result) if result is not None else ""
    # Accept either <pre><code>...</code></pre> or <pre>...</pre>
    has_pre = bool(_re.search(r"<pre[^>]*>", html, _re.IGNORECASE))
    assert has_pre, (
        "Empty \\begin{lstlisting}\\end{lstlisting} did not produce a <pre> block. "
        "ADR-003: lstlisting environments must emit <pre><code> blocks."
    )


# ---------------------------------------------------------------------------
# B14 — Unclosed environment
# ---------------------------------------------------------------------------


def test_b14_unclosed_environment_does_not_crash():
    """
    B14: An unclosed lstlisting (no matching \\end{lstlisting}) must not crash.

    PINNED CONTRACT:
      The parser must NOT raise an unhandled exception that propagates as a 500.
      Acceptable outcomes:
        (a) The parser recovers and returns HTML (possibly with a warning logged).
        (b) The parser raises a *structured* ValueError / RuntimeError that the
            route translates to a 4xx.
      Fabricating content to 'complete' the unclosed environment is forbidden.

    ADR-003: 'Stripping or ignoring nodes the parser does not recognize, with
    a structured warning logged per unrecognized node — not a crash, not a
    fabrication.'  An unclosed environment is a structural error; the same
    no-crash + no-fabrication principle applies.

    Trace: ADR-003 robustness and structured-warning commitment.
    """
    parser = _get_parser()
    latex_body = (
        r"\begin{document}" + "\n"
        r"\begin{lstlisting}" + "\n"
        "int x = 1;" + "\n"
        # deliberately NO \end{lstlisting}
        r"\end{document}"
    )
    # Neither an unhandled crash nor a fabrication is acceptable.
    # A structured ValueError/RuntimeError is the 'fail loudly' form.
    # We catch everything else as a test failure.
    try:
        result = parser(latex_body)
        # If we get here without an exception: result must be non-None (not silent crash)
        # and must not contain a raw \begin{ leak (fabrication check).
        if result is not None:
            html_str = str(result)
            # The unclosed environment must not leave \begin{lstlisting} in the prose.
            import re as _re
            raw_begin_in_prose = r"\begin{lstlisting}" in html_str
            if raw_begin_in_prose:
                # Strip <pre> regions first — raw LaTeX inside <pre> is OK
                stripped = _re.sub(r"<pre[^>]*>.*?</pre>", "", html_str, flags=_re.DOTALL | _re.IGNORECASE)
                assert r"\begin{lstlisting}" not in stripped, (
                    r"Unclosed \begin{lstlisting} leaked into prose HTML. "
                    "ADR-003: unclosed environments must not produce raw LaTeX in output."
                )
    except (ValueError, RuntimeError):
        # Structured raise is the pinned contract alternative — acceptable.
        pass
    except Exception as exc:
        pytest.fail(
            f"Parser raised unhandled {type(exc).__name__}({exc!r}) on unclosed "
            r"lstlisting environment. "
            "ADR-003: must not crash. Either recover with a warning or raise a "
            "structured ValueError/RuntimeError."
        )


def test_b14_unclosed_environment_logs_warning_or_raises_structured(caplog):
    """
    B14 structured-warning variant: if the parser recovers from an unclosed
    environment rather than raising, it MUST log at WARNING level.

    ADR-003: 'a structured warning logged per unrecognized node — not a crash,
    not a fabrication.'  An unclosed environment is a worse-than-unrecognized
    structural error; a WARNING (at minimum) is required.

    If the parser raises a structured exception instead, this test passes
    (raising IS failing loudly — no warning needed when an exception propagates).

    Trace: ADR-003 structured-warning commitment.
    """
    parser = _get_parser()
    latex_body = (
        r"\begin{document}" + "\n"
        r"\begin{lstlisting}" + "\n"
        "int x = 1;\n"
        r"\end{document}"
    )

    raised_structured = False
    with caplog.at_level(logging.WARNING):
        try:
            parser(latex_body)
        except (ValueError, RuntimeError):
            raised_structured = True
        except Exception as exc:
            pytest.fail(
                f"Unhandled {type(exc).__name__} from parser on unclosed lstlisting."
            )

    if raised_structured:
        # Raised a structured error — loud failure, no warning needed.
        return

    # If no exception: a WARNING must have been logged.
    warning_records = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert len(warning_records) >= 1, (
        "Parser recovered from unclosed lstlisting without raising AND without "
        "logging a WARNING. ADR-003: structured warning required for every "
        "unrecognized / malformed node — silent recovery is not acceptable."
    )
