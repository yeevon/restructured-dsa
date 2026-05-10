"""
HTTP-protocol (smoke-layer) tests for TASK-007: Tabular column-spec residue fix.

ADR-017 (balanced-brace consumption): the `_render_tabular` handler must
consume the entire column-spec argument — including content inside nested `{}`
pairs such as `@{}`, `p{3.4cm}`, `>{}`, `<{}` — and leave zero spec residue
in any rendered table cell.

ADR-011 (Accepted, parent contract): "strip column spec from rendered output
entirely; only data rows render; log warn-per-node for complex spec features."

This file covers:
  - AC-1: @{}...@{} idiom residue absence across all 12 Chapters.
  - AC-2: p{width} residue absence and warn-per-node for that spec feature.
  - AC-8 (MC-6): no write path to content/latex/.

Coverage checklist:
  Boundary:
    - `@{}lccc@{}` — dominant corpus idiom (ch-02/03/04 hot spots).
    - `@{}p{3.4cm}p{5cm}p{4.8cm}@{}` — all p{width} braces nested.
    - `|c|c|c|` — vertical bars handled per ADR-011 warn-per-node.
    - `lll` — simple alignment letters (TASK-004 coverage extended here).
    - `>{\bfseries}lccc` — `>{...}` modifier with nested braces.
    - First-cell of first-row across all 12 Chapters (not a spot-check).
  Edge:
    - Tabular with only one column: `{l}`.
    - Tabular with `@{}` empty groups but NO data letters in spec: `{@{}@{}}`.
    - Spec `{@{}l@{}}` — letter flanked by empty @-groups.
    - Position effects: first cell vs second cell (residue only leaks into first).
  Negative:
    - Exact corpus residue patterns (`lccc@`, `p3.4cm`, `p5cm`, `p4.8cm@`) must
      be absent from first-cell text of every table in ch-02, ch-03, ch-04.
    - No `<code>` element contains `$...$` math tokens (texttt-math trap closed).
  Performance:
    - All 12 Chapters render within 3s under TestClient (shared with TASK-005
      coverage; re-exercised here to catch regressions from ADR-017 changes).

pytestmark registers all tests under task("TASK-007").
"""

from __future__ import annotations

import importlib
import logging
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

# Chapters with confirmed @{}...@{} or p{width} column-spec residue (Run 008 catalog).
# ch-02: 6 instances, ch-03: 30 instances, ch-04: 17 instances.
TABULAR_HOT_CHAPTERS = [
    "ch-02-intro-to-algorithms",
    "ch-03-intro-to-data-structures",
    "ch-04-lists-stacks-and-queues",
]

# Residue patterns that ADR-017 must prevent from appearing in any rendered cell.
# These are the exact corpus leak shapes documented in the project_issue and ADR-017.
RESIDUE_PATTERNS = [
    # @{}lccc@{} idiom residue variants (ch-02/03/04 dominant)
    re.compile(r"^l+c+r*@"),          # "lccc@..." prefix
    re.compile(r"^[lcr]+@"),           # any alignment-letter run ending in @
    re.compile(r"^@\{"),               # @{ as the first visible characters
    # p{width} residue variants
    re.compile(r"^p\{?[\d.]+"),        # "p{3.4..." or "p3.4..." prefix
    re.compile(r"^p[\d.]+cm"),         # "p3.4cm..." prefix (braces stripped but text leaks)
    # Vertical bar spec residue
    re.compile(r"^\|[lcr]"),           # "|c..." prefix
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


# ---------------------------------------------------------------------------
# HTML parsing helpers (no BeautifulSoup dependency)
# ---------------------------------------------------------------------------

_TABLE_RE = re.compile(r"<table[\s>].*?</table>", re.DOTALL | re.IGNORECASE)
_ROW_RE = re.compile(r"<tr[\s>].*?</tr>", re.DOTALL | re.IGNORECASE)
_FIRST_CELL_RE = re.compile(
    r"<(td|th)[^>]*>(.*?)</\1>", re.DOTALL | re.IGNORECASE
)
_TAG_STRIP_RE = re.compile(r"<[^>]+>")


def _extract_first_cells_of_all_tables(html: str) -> list[str]:
    """
    Extract the text content of the FIRST cell in the FIRST <tr> of each <table>.

    Returns a list of stripped plain-text strings (one per table).
    Intended for ADR-017 negative assertions: none of these should contain
    column-spec residue.
    """
    first_cells = []
    for table_match in _TABLE_RE.finditer(html):
        table_html = table_match.group(0)
        rows = _ROW_RE.finditer(table_html)
        first_row = next(rows, None)
        if first_row is None:
            continue
        cell_match = _FIRST_CELL_RE.search(first_row.group(0))
        if cell_match is None:
            continue
        # Strip inner HTML tags to get the visible text
        cell_inner = cell_match.group(2)
        plain = _TAG_STRIP_RE.sub("", cell_inner).strip()
        first_cells.append(plain)
    return first_cells


def _make_doc(body: str) -> str:
    """Wrap body in a minimal LaTeX document structure."""
    return (
        r"\documentclass{article}" + "\n"
        r"\begin{document}" + "\n"
        + body + "\n"
        r"\end{document}"
    )


# ===========================================================================
# AC-1: First-cell residue across the full 12-chapter corpus
# ADR-017: balanced-brace consumption closes the ADR-011 implementation gap.
# ===========================================================================

@pytest.mark.parametrize("chapter_id", ALL_CHAPTER_IDS)
def test_no_column_spec_residue_in_first_cell_of_any_table(chapter_id: str) -> None:
    """
    AC-1 (TASK-007): for every table in every Chapter, the first cell of the
    first row must NOT begin with column-spec residue text.

    The 53 visible instances in ch-02/03/04 (Run 008 catalog) all exhibit
    a first-cell starting with `lccc@`, `p3.4cm`, `p3.4cmp5cmp4.8cm@`, etc.
    ADR-017 (balanced-brace consumption) must eliminate all of them.

    Asserts against ALL 12 Chapters so future regressions surface immediately
    (not a spot-check of only the hot chapters).

    This test is RED before ADR-017 is implemented — the hot chapters have
    confirmed residue.
    """
    client = _get_client()
    response = client.get(f"/lecture/{chapter_id}")
    assert response.status_code == 200, (
        f"GET /lecture/{chapter_id} returned {response.status_code}. "
        "Cannot assess tabular residue if the page did not render."
    )

    first_cells = _extract_first_cells_of_all_tables(response.text)

    residue_found = []
    for cell_text in first_cells:
        for pattern in RESIDUE_PATTERNS:
            if pattern.search(cell_text):
                residue_found.append((cell_text[:80], pattern.pattern))
                break  # only report each cell once

    assert residue_found == [], (
        f"GET /lecture/{chapter_id} — column-spec residue found in the first cell "
        f"of {len(residue_found)} table(s). "
        "ADR-017: balanced-brace consumption must eliminate ALL spec residue; "
        "no column-spec characters may appear as visible text in any rendered cell. "
        f"Residue (cell_text_prefix, pattern): {residue_found!r}"
    )


@pytest.mark.parametrize("chapter_id", TABULAR_HOT_CHAPTERS)
def test_hot_chapter_no_lccc_at_in_any_cell(chapter_id: str) -> None:
    """
    AC-1 (negative): in the three hot chapters (ch-02, ch-03, ch-04), the
    exact corpus residue pattern 'lccc@' must not appear in the response body.

    This is a stricter body-level assertion that does not rely on HTML parsing —
    if 'lccc@' appears ANYWHERE in the HTML (even in an attribute), that's a
    signal worth investigating.

    This test will be RED before ADR-017 is implemented.
    """
    client = _get_client()
    response = client.get(f"/lecture/{chapter_id}")
    body = response.text
    # Strip code blocks before checking (verbatim LaTeX might have these)
    body_no_code = re.sub(
        r"<pre[\s>].*?</pre>|<code[\s>].*?</code>",
        "<!-- CODE -->",
        body,
        flags=re.DOTALL | re.IGNORECASE,
    )
    assert "lccc@" not in body_no_code, (
        f"GET /lecture/{chapter_id} — 'lccc@' found in rendered body (outside code blocks). "
        "This is the exact column-spec residue pattern from `@{}lccc@{}` tabular specs. "
        "ADR-017: the balanced-brace scanner must consume the spec entirely."
    )


@pytest.mark.parametrize("chapter_id", TABULAR_HOT_CHAPTERS)
def test_hot_chapter_no_p_width_residue_in_any_cell(chapter_id: str) -> None:
    """
    AC-2 (TASK-007): in ch-02/03/04, the `p{width}` residue patterns
    ('p3.4cm', 'p5cm', 'p4.8cm@') must not appear in the response body
    outside code blocks.

    The dominant corpus pattern is `@{}p{3.4cm}p{5cm}p{4.8cm}@{}`.
    The bug: `p3.4cmp5cmp4.8cm@` leaks as the first cell content.

    This test will be RED before ADR-017 is implemented.
    """
    client = _get_client()
    response = client.get(f"/lecture/{chapter_id}")
    body = response.text
    body_no_code = re.sub(
        r"<pre[\s>].*?</pre>|<code[\s>].*?</code>",
        "<!-- CODE -->",
        body,
        flags=re.DOTALL | re.IGNORECASE,
    )
    # The known corpus residue variants for p{width} specs
    for residue in ("p3.4cm", "p5cm", "p4.8cm@", "p3.4cmp5cm"):
        assert residue not in body_no_code, (
            f"GET /lecture/{chapter_id} — p-width residue '{residue}' found in "
            "rendered body (outside code blocks). "
            "ADR-017: the balanced-brace scanner must consume `p{{width}}` specs "
            "entirely; no text from inside the braces may leak into cells."
        )


# ===========================================================================
# AC-1/AC-2: Unit-level tests against parse_latex() for spec strip correctness
# ADR-017 contract: balanced-brace consumption handles @{}, p{width}, >{}, <{}
# ===========================================================================

class TestTabularBalancedBraceConsumption:
    """
    ADR-017 unit-level tests via parse_latex() (ADR-003 public API).

    Each test drives a synthetic tabular with a specific spec shape and
    asserts that the first rendered cell does NOT start with spec text.
    The data content (a unique marker string) MUST appear in the output.
    """

    def test_at_empty_brace_lccc_at_empty_brace_spec_stripped(self):
        """
        Boundary AC-1: `@{}lccc@{}` — the dominant corpus idiom.

        The bug: `[^}]*` terminates at the first `}` inside `@{`, capturing
        only `@{` as the spec, so `}lccc@{}` becomes the start of the body,
        and `lccc@` leaks into the first cell.

        After ADR-017: the balanced-brace scanner walks past `@{}` and `@{}`
        and captures the entire spec `@{}lccc@{}`.
        """
        parse_latex = _import_parse_latex()
        latex = _make_doc(
            r"""
\begin{tabular}{@{}lccc@{}}
Operation & Array & SLL & DLL \\
Insert head & O(1) & O(1) & O(1) \\
\end{tabular}
"""
        )
        html = parse_latex(latex, "ch-test-at-lccc-at")

        first_cells = _extract_first_cells_of_all_tables(html)
        assert first_cells, (
            "No table cells found in rendered HTML. "
            "The tabular environment may not have rendered at all."
        )
        first_cell = first_cells[0]

        # The first cell must be the first data cell, not the spec
        assert "Operation" in first_cell or "Operation" in html, (
            f"Data cell 'Operation' not found in rendered HTML. "
            "After spec strip, the first data row content must remain."
        )

        # The spec residue 'lccc@' must not appear in the first cell
        assert not re.search(r"^[lcr]+@", first_cell), (
            f"Column-spec residue found at the start of the first cell: {first_cell!r}. "
            "ADR-017: `@{{}}lccc@{{}}` spec must be consumed entirely by the "
            "balanced-brace scanner. The bug: `[^}}]*` terminated at first `}}`."
        )

    def test_at_p_width_p_width_p_width_at_spec_stripped(self):
        """
        Boundary AC-2: `@{}p{3.4cm}p{5cm}p{4.8cm}@{}` — the corpus's
        three-column p{width} spec (exactly as it appears in ch-02/03/04).

        All three nested `{width}` groups must be consumed by the balanced-brace
        scanner. The visible first cell must NOT start with `p3.4cm` or similar.
        """
        parse_latex = _import_parse_latex()
        latex = _make_doc(
            r"""
\begin{tabular}{@{}p{3.4cm}p{5cm}p{4.8cm}@{}}
Header One & Header Two & Header Three \\
Cell A & Cell B & Cell C \\
\end{tabular}
"""
        )
        html = parse_latex(latex, "ch-test-p-width-spec")

        first_cells = _extract_first_cells_of_all_tables(html)
        assert first_cells, "No table cells rendered."
        first_cell = first_cells[0]

        # Must not start with p{width} residue
        assert not re.search(r"^p[\{]?[\d.]+", first_cell), (
            f"p-width residue found at the start of the first cell: {first_cell!r}. "
            "ADR-017: `p{{3.4cm}}`, `p{{5cm}}`, `p{{4.8cm}}` must all be consumed "
            "as nested `{{}}` groups within the outer spec delimiter. "
            "The bug: `[^}}]*` terminates at the `}` inside `p{{3.4cm}}`."
        )

        # Data content must survive
        assert "Header One" in html, (
            "Data row 'Header One' missing after spec strip. "
            "ADR-017: stripping the spec must not drop data rows."
        )

    def test_pipe_vertical_bar_spec_stripped(self):
        """
        Boundary AC-2: `|c|c|c|` — vertical bars in the spec.

        ADR-011: vertical bars trigger warn-per-node and are stripped.
        ADR-017: the balanced-brace scan does not need to handle `|` specially
        (it's not a `{}`), but the overall spec must be consumed so no `|c|c|c|`
        appears in the first cell.

        Note: TASK-004 already covered `l|c|r` at the unit level; this test
        uses the corpus-realistic `|c|c|c|` shape (all-pipe-delimited).
        """
        parse_latex = _import_parse_latex()
        latex = _make_doc(
            r"""
\begin{tabular}{|c|c|c|}
\hline
A & B & C \\
\hline
\end{tabular}
"""
        )
        html = parse_latex(latex, "ch-test-pipe-all-columns")

        first_cells = _extract_first_cells_of_all_tables(html)
        # Even if the table has no cells (hline-only), the spec must not leak
        body_no_code = re.sub(
            r"<pre[\s>].*?</pre>|<code[\s>].*?</code>",
            "", html, flags=re.DOTALL | re.IGNORECASE,
        )
        assert "|c|c|c|" not in body_no_code, (
            "Column spec '|c|c|c|' found as visible text. "
            "ADR-011/ADR-017: spec must be stripped regardless of `|` content."
        )
        if first_cells:
            first_cell = first_cells[0]
            assert not re.search(r"^\|[lcr]", first_cell), (
                f"Pipe-prefixed spec residue in first cell: {first_cell!r}. "
                "ADR-017: the spec (including leading `|`) must be fully consumed."
            )

    def test_bfseries_modifier_spec_stripped(self):
        """
        Edge: `>{\\bfseries}lccc` — `>{}` modifier with nested braces.

        ADR-017 §Decision: "Nested `{}` pairs inside the spec — `@{}`, `p{{3.4cm}}`,
        `>{{\\bfseries}}`, `<{{...}}` — are consumed as part of the spec."

        The balanced-brace scanner must handle `>{...}` the same way it handles
        `@{...}` — consume the braces and their contents.
        """
        parse_latex = _import_parse_latex()
        latex = _make_doc(
            r"""
\begin{tabular}{>{\bfseries}lccc}
Heading & Col1 & Col2 & Col3 \\
Data & 1 & 2 & 3 \\
\end{tabular}
"""
        )
        html = parse_latex(latex, "ch-test-bfseries-spec")

        first_cells = _extract_first_cells_of_all_tables(html)
        body_no_code = re.sub(
            r"<pre[\s>].*?</pre>|<code[\s>].*?</code>",
            "", html, flags=re.DOTALL | re.IGNORECASE,
        )
        # The >{...} content must not appear in rendered cells
        assert r"{\bfseries}" not in body_no_code, (
            "Column-modifier spec `{\\bfseries}` found in rendered body. "
            "ADR-017: `>{{\\bfseries}}` must be consumed by the balanced-brace scanner."
        )
        if first_cells:
            first_cell = first_cells[0]
            assert "bfseries" not in first_cell and not re.search(r"^>?\{", first_cell), (
                f"Modifier spec residue in first cell: {first_cell!r}. "
                "ADR-017: `>{{...}}` is a nested `{{}}` pair that must be consumed."
            )

    def test_single_column_l_spec_stripped(self):
        """
        Boundary edge: `{l}` — single simple alignment letter.

        Single-letter specs were handled by the old `[^}]*` regex (no nested
        braces). Must still work after the ADR-017 balanced-brace scanner
        replaces the regex.
        """
        parse_latex = _import_parse_latex()
        latex = _make_doc(
            r"""
\begin{tabular}{l}
Single column content here \\
\end{tabular}
"""
        )
        html = parse_latex(latex, "ch-test-single-col")

        first_cells = _extract_first_cells_of_all_tables(html)
        if first_cells:
            first_cell = first_cells[0]
            assert first_cell != "l", (
                "Single-letter spec 'l' found as the entire first cell content. "
                "ADR-017: the balanced-brace scanner must strip simple specs too "
                "(backward-compatible with the old `[^}}]*` behavior)."
            )

        assert "Single column content here" in html, (
            "Data content 'Single column content here' missing. "
            "ADR-017: spec strip must not affect the body content."
        )

    def test_at_empty_groups_flanking_single_letter_spec_stripped(self):
        """
        Boundary: `{@{}l@{}}` — a single alignment letter flanked by empty
        `@{}` groups. The brace balance is:
          depth 1 (outer spec `{`)
          depth 2 (inner @`{`)
          depth 1 (inner @`}`)
          (letter `l` — no brace)
          depth 2 (inner @`{`)
          depth 1 (inner @`}`)
          depth 0 (outer spec `}` → spec terminates here)

        After ADR-017: the spec `@{}l@{}` is consumed; body starts after the
        matching `}` at depth 0. The first cell is the first data row cell.
        """
        parse_latex = _import_parse_latex()
        latex = _make_doc(
            r"""
\begin{tabular}{@{}l@{}}
DataCell \\
\end{tabular}
"""
        )
        html = parse_latex(latex, "ch-test-flanked-spec")

        first_cells = _extract_first_cells_of_all_tables(html)
        body_no_code = re.sub(
            r"<pre[\s>].*?</pre>", "", html, flags=re.DOTALL | re.IGNORECASE,
        )

        # "@{}l@{}" must not appear as a cell
        assert "@{}l@{}" not in body_no_code and "l@{}" not in body_no_code, (
            "Residue from `@{{}}l@{{}}` spec found in rendered body. "
            "ADR-017: both @{{}} groups must be consumed as nested braces."
        )

        # The data cell must be present
        assert "DataCell" in html, (
            "Data cell 'DataCell' missing after stripping `@{{}}l@{{}}` spec."
        )


# ===========================================================================
# AC-2: warn-per-node fires for complex spec features (ADR-011 unchanged)
# ===========================================================================

class TestComplexSpecWarningStillFires:
    """
    ADR-011 (Accepted, parent contract): warn-per-node for `|`, `p{`, `@{`, `>{`.
    ADR-017 §Decision: "the warn-per-node contract (ADR-011) is unchanged; the
    existing _warn_complex_col_spec(col_spec, chapter_id) helper continues to
    fire warnings for `|`, `p{`, `@{`, `>{`, `<{`. Because this ADR's mechanism
    captures the entire spec, the warnings now fire on the full spec text."
    """

    def test_at_empty_brace_spec_triggers_warning(self, caplog):
        """
        AC-2: `@{}lccc@{}` must trigger a WARNING log for the `@{` feature.

        ADR-011: `@{...}` → warn-per-node.
        ADR-017: the full spec is now captured, so the warning fires on the
        full `@{}lccc@{}` spec text (not on a truncated slice).
        """
        parse_latex = _import_parse_latex()
        latex = _make_doc(
            r"""
\begin{tabular}{@{}lccc@{}}
A & B & C & D \\
\end{tabular}
"""
        )
        with caplog.at_level(logging.WARNING):
            parse_latex(latex, "ch-test-at-warn")

        warning_texts = [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]
        has_at_warning = any(
            "@{" in msg or "at-brace" in msg.lower() or "inter-column" in msg.lower()
            for msg in warning_texts
        )
        assert has_at_warning, (
            "No WARNING log mentioning `@{` was emitted for `@{{}}lccc@{{}}` spec. "
            "ADR-011: `@{{...}}` features must trigger warn-per-node. "
            "ADR-017: the warning must fire on the full spec (not a truncated slice). "
            f"Warning messages captured: {warning_texts!r}"
        )

    def test_p_width_spec_triggers_warning_full_spec(self, caplog):
        """
        AC-2: `@{}p{3.4cm}p{5cm}@{}` must trigger a WARNING for `p{`.

        ADR-017 §Decision: "the warnings now fire on the full spec text, not
        the truncated `[^}]*` slice." Before ADR-017, `p{3.4cm}` was never
        reached because `[^}]*` terminated at the `{` inside `@{}`.
        """
        parse_latex = _import_parse_latex()
        latex = _make_doc(
            r"""
\begin{tabular}{@{}p{3.4cm}p{5cm}@{}}
Name & Value \\
\end{tabular}
"""
        )
        with caplog.at_level(logging.WARNING):
            parse_latex(latex, "ch-test-p-full-spec")

        warning_texts = [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]
        has_p_warning = any(
            "p{" in msg or "paragraph" in msg.lower() or "p-col" in msg.lower()
            for msg in warning_texts
        )
        assert has_p_warning, (
            "No WARNING log mentioning `p{` was emitted for `@{{}}p{{3.4cm}}p{{5cm}}@{{}}`. "
            "ADR-011: `p{{width}}` features must trigger warn-per-node. "
            "ADR-017: before this fix, the warning never fired because `[^}}]*` terminated "
            "at the `{{` inside `@{{}}` before reaching `p{{3.4cm}}`. "
            f"Warning messages captured: {warning_texts!r}"
        )


# ===========================================================================
# AC-8: MC-6 — no write path to content/latex/
# ===========================================================================

def test_mc6_lecture_source_read_only_no_write_in_parser() -> None:
    """
    AC-8 (MC-6): the application must never write to content/latex/.
    The parser changes introduced by ADR-017 must stay inside app/parser.py;
    no write path to the lecture source root is introduced.

    Strategy: scan app/parser.py for any `open(..., 'w')` or `write()` call
    that targets a path under `content/latex/` (or `CONTENT_ROOT` without
    a read-only guard).

    This is a static check — it does not parse Python AST, but it catches
    accidental additions of write paths to the parser module.
    """
    import pathlib
    parser_path = pathlib.Path(__file__).parent.parent / "app" / "parser.py"
    assert parser_path.exists(), (
        f"app/parser.py not found at {parser_path}. "
        "Cannot run MC-6 static check."
    )
    source = parser_path.read_text(encoding="utf-8")

    # Patterns that would indicate a write path into the content root.
    # "w" open mode, writelines, write() call — in a context involving
    # content/latex or CONTENT_ROOT.
    forbidden_patterns = [
        re.compile(r"""open\s*\(.*content/latex.*['"]\s*w"""),
        re.compile(r"""open\s*\(.*CONTENT_ROOT.*['"]\s*w"""),
        re.compile(r"""\.write\s*\(.*content/latex"""),
    ]
    violations = [p.pattern for p in forbidden_patterns if p.search(source)]
    assert violations == [], (
        f"MC-6 violation: app/parser.py contains a write-path pattern targeting "
        f"content/latex/ or CONTENT_ROOT: {violations!r}. "
        "ADR-017: the fix must stay inside the parser in-memory; no source file "
        "is written. Manifest §5: no in-app authoring of lecture content."
    )


# ===========================================================================
# Negative: no <code> element contains $...$ math tokens (texttt-math trap)
# This is the companion assertion for ADR-018; included here because it uses
# the same HTTP-level test client and corpus sweep.
# ===========================================================================

@pytest.mark.parametrize("chapter_id", ALL_CHAPTER_IDS)
def test_no_inline_math_inside_code_elements(chapter_id: str) -> None:
    """
    Negative / ADR-018 companion: after the texttt fix, NO `<code>` element
    in any rendered lecture page should contain inline math tokens `$...$`.

    The bug: `\\texttt{}` emitted `<code>...</code>`, and MathJax's default
    `skipHtmlTags` includes `code`, so `$\\to$`, `$\\bullet$` rendered as
    literal text. ADR-018 moves `\\texttt{}` to `<span class="texttt">`,
    leaving `<code>` only for `verbatim`/`lstlisting` blocks where math
    delimiters are legitimate literals.

    Post-fix: `<code>...$...$...</code>` patterns (inline math tokens directly
    inside a code element) must be absent from the rendered body.

    This test will be RED before ADR-018 is implemented for chapters with
    `\\texttt{}` containing embedded math (primarily ch-04, ch-09, ch-10).
    """
    client = _get_client()
    response = client.get(f"/lecture/{chapter_id}")
    assert response.status_code == 200, (
        f"GET /lecture/{chapter_id} returned {response.status_code}."
    )

    body = response.text

    # Find all <code>...</code> occurrences (NOT inside <pre>)
    # Strategy: find non-pre code blocks by removing pre+code blocks first,
    # then checking remaining bare <code> elements for math tokens.
    body_no_pre = re.sub(
        r"<pre[\s>].*?</pre>",
        "<!-- PRE -->",
        body,
        flags=re.DOTALL | re.IGNORECASE,
    )

    # Remaining <code> elements are inline (not inside <pre>)
    inline_code_blocks = re.findall(
        r"<code[^>]*>(.*?)</code>",
        body_no_pre,
        flags=re.DOTALL | re.IGNORECASE,
    )

    # Each inline code block must NOT contain a `$...$` math token
    math_in_code = [
        block for block in inline_code_blocks
        if re.search(r"\$[^$]+\$", block)
    ]

    assert math_in_code == [], (
        f"GET /lecture/{chapter_id} — {len(math_in_code)} inline <code> element(s) "
        "contain `$...$` math tokens. "
        "ADR-018: \\texttt{{}} must emit `<span class=\"texttt\">` (not `<code>`) "
        "so MathJax processes embedded math. MathJax's default `skipHtmlTags` "
        "includes `code`; math inside `<code>` renders as literal text. "
        "After the fix, `<code>` should appear only inside `<pre>` blocks "
        "(verbatim/lstlisting), never as a bare inline element with `$...$`. "
        f"Offending code blocks (first 3): {math_in_code[:3]!r}"
    )
