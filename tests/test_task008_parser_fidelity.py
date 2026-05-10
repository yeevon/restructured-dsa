"""
HTTP-protocol smoke tests for TASK-008: Parser fidelity — unhandled environments
and bleeding text-formatting macros.

ADR-013 (split harness — HTTP-protocol layer): this file contains the substring-
based body assertions that confirm LaTeX macro tokens do NOT appear in rendered
HTML body text outside safe zones (pre/code blocks and MathJax delimiters).

ADR-019 (unhandled-environment strategy): the unknown-env fallback must emit
  <div class="unrecognized-env" data-env="X">{inner_html}</div>
instead of leaking literal \begin{X} / \end{X} tokens. Because the corpus walk
found zero source-level unhandled environments, this assertion is conditional —
it only fires if a `data-env=` attribute actually appears in the rendered HTML.

ADR-020 (defensive macro-stripping): the four `_escape(raw)` fallback sites must
emit `<strong>`, `<em>`, `<span class="texttt">`, `<span ...small-caps>` for
the recognized macros, never the literal `\textbf{`, `\textit{`, `\emph{`,
`\textsc{` wrapper tokens.

ACs targeted by this file:
  AC-1: No literal \begin{X} / \end{X} in prose HTML for any chapter.
         Concentrated on ch-09 (tikzpicture source dominant; most likely leak site).
  AC-2: No literal \textbf{ / \textit{ / \emph{ / \textsc{ in prose HTML for
         any chapter. Concentrated on ch-10 (60 Gap-B instances per catalog).
  AC-3/AC-4: If any `data-env=` attribute appears, the wrapper element has the
              correct shape (class="unrecognized-env", a data-env attribute,
              and inner HTML content).

Coverage checklist:
  Boundary:
    - AC-1: ch-09 (22-instance dominant from catalog) AND all 12 chapters.
    - AC-2: ch-10 (60-instance dominant), ch-13 (23), ch-04 (13) checked individually
            AND all 12 chapters via parametrize.
    - Safe-zone exemption boundary: the _strip_safe_regions helper is exercised
      via its own sanity test to confirm it covers \begin{} inside math.
  Edge:
    - All 12 Chapter IDs iterated, not a spot-check.
    - \textsc{ tested specifically (ADR-020 maps it to small-caps span) — it is
      less common than \textbf but still in the leaked set.
    - \end{ checked independently from \begin{ (asymmetric leak is possible).
  Negative:
    - Each macro checked as a specific negative assertion (zero matches required).
    - The safe-zone stripping is validated not to strip non-math backslash content.
  Performance:
    - All 12 chapters rendered and substring-checked within a 5s wall-clock budget
      per chapter (catches O(n^2) regressions; generous for in-process TestClient).

pytestmark registers all tests under task("TASK-008").
"""

from __future__ import annotations

import re
import time

import pytest

pytestmark = pytest.mark.task("TASK-008")

# ---------------------------------------------------------------------------
# Canonical Chapter list — matches TASK-005 smoke test exactly (ADR-013).
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

# Chapters from the TASK-005 catalog that dominate each gap.
CH_09 = "ch-09-balanced-trees"   # Gap A dominant: 22 tikzpicture/env instances
CH_10 = "ch-10-graphs"            # Gap B dominant: 60 macro-leak instances
CH_13 = "ch-13-additional-material"  # Gap B: 23 instances
CH_04 = "ch-04-lists-stacks-and-queues"  # Gap B: 13 instances


# ---------------------------------------------------------------------------
# Import helper — deferred so collection succeeds before implementation exists.
# ---------------------------------------------------------------------------

def _get_client():
    """Return a TestClient for the FastAPI app (deferred import)."""
    from fastapi.testclient import TestClient
    from app.main import app  # noqa: PLC0415
    return TestClient(app)


# ---------------------------------------------------------------------------
# Safe-zone stripping — imported from test_task001 to avoid duplication.
# Per task spec: "import it or duplicate the pattern; do NOT modify the source".
#
# We reproduce the pattern here (not importing from another test module, which
# would create a cross-test-module dependency that pytest doesn't manage) so
# this file remains independently runnable.
# ---------------------------------------------------------------------------

_PRE_CODE_PATTERN = re.compile(
    r"<pre[\s>].*?</pre>|<code[\s>].*?</code>",
    re.DOTALL | re.IGNORECASE,
)
_MATH_INLINE_PATTERN = re.compile(r"\$[^$]+?\$")
_MATH_DISPLAY_PATTERN = re.compile(r"\\\[.*?\\\]", re.DOTALL)
_MATH_SPAN_PATTERN = re.compile(
    r'<span[^>]*class="[^"]*math[^"]*"[^>]*>.*?</span>',
    re.DOTALL | re.IGNORECASE,
)
# Also cover \(...\) inline math delimiters (MathJax standard)
_MATH_PAREN_PATTERN = re.compile(r"\\\(.*?\\\)", re.DOTALL)


def _strip_safe_regions(html: str) -> str:
    """
    Remove from html all regions that are allowed to contain raw LaTeX:
    - <pre>...</pre> and <code>...</code> blocks
    - Inline math $...$
    - Display math \[...\]
    - MathJax inline math \(...\)
    - <span class="math*">...</span>

    The remainder is "prose HTML" that must be free of raw LaTeX macros.

    This is a local copy of the same pattern from test_task001_rendering_fidelity.py
    extended with \(...\) to cover ADR-020's "math delimiters are preserved in
    fallback paths" commitment (ADR-020 §Decision §5: "math delimiters inside
    fallback raw text are not escaped by this helper").
    """
    stripped = html
    for pattern in (
        _PRE_CODE_PATTERN,
        _MATH_SPAN_PATTERN,
        _MATH_INLINE_PATTERN,
        _MATH_DISPLAY_PATTERN,
        _MATH_PAREN_PATTERN,
    ):
        stripped = pattern.sub("<!-- SAFE_REGION -->", stripped)
    return stripped


# ===========================================================================
# AC-1: Gap A — no literal \begin{X} / \end{X} in prose HTML for any chapter.
#
# ADR-019: the unknown-env fallback emits
#   <div class="unrecognized-env" data-env="X">{inner_html}</div>
# and MUST NOT pass literal \begin{X} or \end{X} tokens to the rendered HTML.
# ADR-020: when pylatexenc fails to register an env and emits \begin/\end as
# raw chars, the _strip_text_formatting_macros helper consumes them (Decision §4).
# ===========================================================================


def test_ch09_no_backslash_begin_in_prose() -> None:
    """
    AC-1 (concentrated): ch-09-balanced-trees is the dominant chapter for Gap A.
    Its rendered HTML prose body must contain zero '\begin{' substrings outside
    pre/code blocks and MathJax delimiters.

    The TASK-005 catalog recorded 22 instances of env-bleed in ch-09, which the
    /design corpus walk traced to tikzpicture (29 occurrences; already skip-handled)
    and to pylatexenc parse failures on nested-brace optional args. Either way,
    the rendered HTML must be clean after the ADR-019 + ADR-020 fix.

    This test MUST FAIL before the implementer touches app/parser.py.
    """
    client = _get_client()
    response = client.get(f"/lecture/{CH_09}")
    assert response.status_code == 200, (
        f"GET /lecture/{CH_09} returned {response.status_code}; "
        "cannot assert prose content without a 200 response."
    )
    prose = _strip_safe_regions(response.text)
    assert r"\begin{" not in prose, (
        r"AC-1 FAIL: literal '\begin{' found in rendered prose of ch-09-balanced-trees "
        "(outside pre/code blocks and MathJax delimiters). "
        "ADR-019: the unknown-env fallback must wrap inner content in "
        "<div class=\"unrecognized-env\"> — not leak \\begin{} tokens. "
        "ADR-020: the defensive macro-stripping helper must consume \\begin{X} "
        "at raw-text fallback sites. This test is RED until the fix lands."
    )


def test_ch09_no_backslash_end_in_prose() -> None:
    """
    AC-1 (concentrated, asymmetric): the \end{X} token may leak independently
    from \begin{X} if only one side of the environment boundary triggers a
    parse failure.

    ch-09 is the dominant chapter for this gap.
    """
    client = _get_client()
    response = client.get(f"/lecture/{CH_09}")
    assert response.status_code == 200
    prose = _strip_safe_regions(response.text)
    assert r"\end{" not in prose, (
        r"AC-1 FAIL: literal '\end{' found in rendered prose of ch-09-balanced-trees "
        "(outside safe regions). "
        "ADR-019 + ADR-020: both the wrapper token and the close token must be consumed."
    )


@pytest.mark.parametrize("chapter_id", ALL_CHAPTER_IDS)
def test_no_backslash_begin_in_prose_all_chapters(chapter_id: str) -> None:
    """
    AC-1 (corpus-wide): for every chapter, rendered prose HTML contains zero
    '\begin{' substrings outside pre/code and MathJax zones.

    ADR-019: the generic unknown-env fallback must not leak \begin{} tokens for
    any chapter in the 12-chapter corpus.

    A failure on ANY chapter is a blocking AC-1 failure. The concentrated test
    on ch-09 above provides first-signal focus; this parametrized test proves
    the fix is corpus-wide.
    """
    client = _get_client()
    response = client.get(f"/lecture/{chapter_id}")
    assert response.status_code == 200, (
        f"GET /lecture/{chapter_id} returned {response.status_code}."
    )
    prose = _strip_safe_regions(response.text)
    assert r"\begin{" not in prose, (
        f"AC-1 FAIL: literal '\\begin{{' found in prose HTML for {chapter_id} "
        "(outside pre/code blocks and MathJax delimiters). "
        "ADR-019 + ADR-020: the unknown-env fallback and defensive macro-stripping "
        "must eliminate all \\begin{{}} tokens from rendered prose across all chapters."
    )


@pytest.mark.parametrize("chapter_id", ALL_CHAPTER_IDS)
def test_no_backslash_end_in_prose_all_chapters(chapter_id: str) -> None:
    """
    AC-1 (corpus-wide, close token): for every chapter, rendered prose HTML
    contains zero '\end{' substrings outside safe zones.

    Mirrors the \begin{ check. Asymmetric leak (only \end{ visible) is possible
    if the parser consumes the open token but not the close.
    """
    client = _get_client()
    response = client.get(f"/lecture/{chapter_id}")
    assert response.status_code == 200
    prose = _strip_safe_regions(response.text)
    assert r"\end{" not in prose, (
        f"AC-1 FAIL: literal '\\end{{' found in prose HTML for {chapter_id} "
        "(outside safe regions). "
        "ADR-019 + ADR-020: close tokens must also be consumed."
    )


# ===========================================================================
# AC-2: Gap B — no literal text-formatting macro tokens in prose HTML.
#
# ADR-020: \textbf{X} → <strong>X</strong>, \textit{X} → <em>X</em>,
#          \emph{X} → <em>X</em>, \texttt{X} → <span class="texttt">X</span>,
#          \textsc{X} → <span style="font-variant:small-caps">X</span>
# at every _escape(raw) fallback site. The literal wrapper tokens must NOT
# appear in the rendered HTML body outside safe zones.
# ===========================================================================

# The macro wrapper tokens that must never appear in prose HTML (AC-2).
# Note: \textsc{ is included even though it is not listed in AC-2 explicitly;
# it is in ADR-020's mapping and appears in the corpus — included for completeness.
_GAP_B_MACRO_TOKENS = [
    r"\textbf{",
    r"\textit{",
    r"\emph{",
    r"\textsc{",
]


def test_ch10_no_gap_b_macro_tokens_in_prose() -> None:
    """
    AC-2 (concentrated): ch-10-graphs is the dominant chapter for Gap B with
    ~60 catalogued instances. Its rendered HTML prose body must contain zero
    '\textbf{', '\textit{', '\emph{', '\textsc{' substrings outside safe zones.

    ADR-020: the defensive macro-stripping helper is applied at every _escape(raw)
    fallback site; the most likely site for ch-10 is the tabular cell-walker
    fallback (Site A in ADR-020) — cells like '\textbf{Problem $\downarrow$}'.

    This test MUST FAIL before the implementer touches app/parser.py.
    """
    client = _get_client()
    response = client.get(f"/lecture/{CH_10}")
    assert response.status_code == 200, (
        f"GET /lecture/{CH_10} returned {response.status_code}."
    )
    prose = _strip_safe_regions(response.text)
    failures = [token for token in _GAP_B_MACRO_TOKENS if token in prose]
    assert failures == [], (
        f"AC-2 FAIL: the following raw macro tokens were found in ch-10-graphs "
        f"rendered prose (outside pre/code/math): {failures!r}. "
        "ADR-020: the defensive _strip_text_formatting_macros helper must convert "
        "these tokens to their HTML equivalents at every _escape(raw) fallback site. "
        "This test is RED until the ADR-020 fix is applied."
    )


def test_ch13_no_gap_b_macro_tokens_in_prose() -> None:
    """
    AC-2 (secondary dominant): ch-13-additional-material had ~23 catalogued
    Gap B instances. Must also be clean after the ADR-020 fix.
    """
    client = _get_client()
    response = client.get(f"/lecture/{CH_13}")
    assert response.status_code == 200
    prose = _strip_safe_regions(response.text)
    failures = [token for token in _GAP_B_MACRO_TOKENS if token in prose]
    assert failures == [], (
        f"AC-2 FAIL: raw macro tokens {failures!r} found in ch-13 prose HTML. "
        "ADR-020: defensive macro-stripping must cover all affected chapters."
    )


def test_ch04_no_gap_b_macro_tokens_in_prose() -> None:
    """
    AC-2 (tertiary): ch-04-lists-stacks-and-queues had ~13 catalogued Gap B
    instances. Must also be clean after the ADR-020 fix.
    """
    client = _get_client()
    response = client.get(f"/lecture/{CH_04}")
    assert response.status_code == 200
    prose = _strip_safe_regions(response.text)
    failures = [token for token in _GAP_B_MACRO_TOKENS if token in prose]
    assert failures == [], (
        f"AC-2 FAIL: raw macro tokens {failures!r} found in ch-04 prose HTML. "
        "ADR-020: defensive macro-stripping must cover all affected chapters."
    )


@pytest.mark.parametrize("chapter_id", ALL_CHAPTER_IDS)
def test_no_textbf_in_prose_all_chapters(chapter_id: str) -> None:
    """
    AC-2 (corpus-wide, \\textbf{): across all 12 chapters, the literal '\\textbf{'
    substring must not appear in prose HTML outside safe zones.

    \\textbf{ is the most common Gap B token in the corpus. A corpus-wide pass
    ensures the ADR-020 fix (Sites A/B/C/D) covers every affected chapter,
    not just ch-10.
    """
    client = _get_client()
    response = client.get(f"/lecture/{chapter_id}")
    assert response.status_code == 200
    prose = _strip_safe_regions(response.text)
    assert r"\textbf{" not in prose, (
        f"AC-2 FAIL: literal '\\textbf{{' found in prose HTML for {chapter_id} "
        "(outside pre/code blocks and MathJax delimiters). "
        "ADR-020: '\\textbf{{X}}' must be converted to '<strong>X</strong>' "
        "at every _escape(raw) fallback site."
    )


@pytest.mark.parametrize("chapter_id", ALL_CHAPTER_IDS)
def test_no_textit_in_prose_all_chapters(chapter_id: str) -> None:
    """
    AC-2 (corpus-wide, \\textit{): literal '\\textit{' must not appear in prose
    HTML for any chapter.
    """
    client = _get_client()
    response = client.get(f"/lecture/{chapter_id}")
    assert response.status_code == 200
    prose = _strip_safe_regions(response.text)
    assert r"\textit{" not in prose, (
        f"AC-2 FAIL: literal '\\textit{{' found in prose HTML for {chapter_id}. "
        "ADR-020: '\\textit{{X}}' must become '<em>X</em>' at fallback sites."
    )


@pytest.mark.parametrize("chapter_id", ALL_CHAPTER_IDS)
def test_no_emph_in_prose_all_chapters(chapter_id: str) -> None:
    """
    AC-2 (corpus-wide, \\emph{): literal '\\emph{' must not appear in prose
    HTML for any chapter.
    """
    client = _get_client()
    response = client.get(f"/lecture/{chapter_id}")
    assert response.status_code == 200
    prose = _strip_safe_regions(response.text)
    assert r"\emph{" not in prose, (
        f"AC-2 FAIL: literal '\\emph{{' found in prose HTML for {chapter_id}. "
        "ADR-020: '\\emph{{X}}' must become '<em>X</em>' at fallback sites."
    )


@pytest.mark.parametrize("chapter_id", ALL_CHAPTER_IDS)
def test_no_textsc_in_prose_all_chapters(chapter_id: str) -> None:
    """
    AC-2 (corpus-wide, \\textsc{): literal '\\textsc{' must not appear in prose
    HTML for any chapter.

    ADR-020: \\textsc{X} → <span style="font-variant:small-caps">X</span>.
    """
    client = _get_client()
    response = client.get(f"/lecture/{chapter_id}")
    assert response.status_code == 200
    prose = _strip_safe_regions(response.text)
    assert r"\textsc{" not in prose, (
        f"AC-2 FAIL: literal '\\textsc{{' found in prose HTML for {chapter_id}. "
        "ADR-020: '\\textsc{{X}}' must become "
        "'<span style=\"font-variant:small-caps\">X</span>' at fallback sites."
    )


# ===========================================================================
# AC-2 positive contract: when the fix is present, the macro argument content
# appears as rendered HTML, not as invisible dropped text.
#
# ADR-020 Decision §1: the argument content X is preserved and HTML-escaped.
# "Visible failure, no fabrication" (manifest §6 broadly read).
# ===========================================================================


def test_ch10_textbf_argument_content_survives_as_strong_or_plain_text() -> None:
    """
    AC-2 positive: after the ADR-020 fix, the argument content of a \\textbf{}
    call must survive in the rendered HTML as either a <strong> element or as
    plain visible text — the macro wrapper is consumed, the content is not dropped.

    This guards against the "strip macro AND content" failure mode (ADR-019's
    rejected Alternative C applied to macro tokens).

    We use a heuristic: the rendered ch-10 HTML must contain at least ONE
    <strong> element in its body, because the corpus has many \textbf{} calls.
    If the helper strips \textbf{X} to nothing (drops X), this assertion fails.

    Note: this test may PASS if the implementer already converts \textbf{}
    correctly. That is acceptable — it exists to catch regressions where a
    "fix" drops content silently.
    """
    client = _get_client()
    response = client.get(f"/lecture/{CH_10}")
    assert response.status_code == 200
    html = response.text
    # ch-10 has many \textbf{} — at least one must survive as <strong>
    assert "<strong>" in html, (
        "AC-2 positive contract: ch-10 has many \\textbf{} occurrences; the rendered "
        "HTML contains no <strong> element. The ADR-020 helper must convert "
        "\\textbf{X} to <strong>X</strong>, not silently drop the content."
    )


# ===========================================================================
# AC-3 / AC-4 (ADR-019 wrapper): if any `data-env=` attribute appears in a
# rendered chapter, the element must have class="unrecognized-env".
#
# Per the architect's /design note: the corpus walk found ZERO source-level
# unhandled envs, so this assertion may be vacuously satisfied. The test is
# conditional — it only fires if data-env= is actually present.
# ===========================================================================

@pytest.mark.parametrize("chapter_id", ALL_CHAPTER_IDS)
def test_unrecognized_env_wrapper_shape_if_present(chapter_id: str) -> None:
    """
    AC-3/AC-4: IF the rendered HTML for a chapter contains any element with a
    `data-env=` attribute, that element MUST carry class="unrecognized-env".

    ADR-019 Decision §1: the unknown-env fallback emits exactly
      <div class="unrecognized-env" data-env="X">{inner_html}</div>

    The conditional structure is correct per the task spec: "the architect's
    /design-time corpus walk found ZERO source-level unhandled envs in the
    corpus, so this assertion may be vacuously satisfied." We write the test
    such that it only asserts the wrapper shape IF data-env= appears at all.

    If this test fires (is non-vacuous), a failure would indicate that the
    parser emits data-env= without the required class — a contract violation.
    """
    client = _get_client()
    response = client.get(f"/lecture/{chapter_id}")
    assert response.status_code == 200
    html = response.text

    # Find all occurrences of data-env= in the HTML
    data_env_pattern = re.compile(r'data-env="([^"]*)"', re.IGNORECASE)
    env_occurrences = data_env_pattern.findall(html)

    if not env_occurrences:
        # No unrecognized envs in rendered output — vacuously satisfied.
        return

    # If data-env= IS present, every occurrence must be inside an element with
    # class="unrecognized-env". We check by looking for the required class
    # alongside each data-env= attribute.
    # Strategy: the canonical form is 'class="unrecognized-env" data-env="X"'
    # or 'data-env="X" ... class="unrecognized-env"' — look for both orderings
    # OR look for the full pattern.
    unrecognized_class_with_env = re.compile(
        r'class="[^"]*unrecognized-env[^"]*"[^>]*data-env=|'
        r'data-env=[^>]*class="[^"]*unrecognized-env[^"]*"',
        re.IGNORECASE,
    )
    matched_pairs = unrecognized_class_with_env.findall(html)

    assert len(matched_pairs) >= len(env_occurrences), (
        f"AC-3/AC-4 FAIL for {chapter_id}: found {len(env_occurrences)} "
        f"data-env= occurrences (env names: {env_occurrences!r}) but only "
        f"{len(matched_pairs)} of them are inside an element with "
        'class="unrecognized-env". '
        "ADR-019 Decision §1: the unknown-env fallback MUST emit "
        '<div class="unrecognized-env" data-env="X">. '
        "A data-env= attribute on any other element shape violates the contract."
    )


def test_unrecognized_env_inner_html_not_empty_when_present() -> None:
    """
    AC-4 (ADR-019 Decision §1): when the unknown-env wrapper IS emitted, the
    inner_html must not be empty — the body content is preserved (recursively
    rendered via the same walker).

    ADR-019 rejected Alternative C ("drop inner content silently") and committed
    to "recurse through inner content" for manifest §6 ("visible failure,
    no fabrication") compliance.

    This test is vacuously true if no chapter has any unrecognized-env element.
    It fires only if an element with class="unrecognized-env" is present.
    """
    client = _get_client()
    empty_wrappers = []

    for chapter_id in ALL_CHAPTER_IDS:
        response = client.get(f"/lecture/{chapter_id}")
        if response.status_code != 200:
            continue
        html = response.text

        # Find all <div class="unrecognized-env" data-env="X">...</div> blocks
        wrapper_pattern = re.compile(
            r'<div[^>]*class="[^"]*unrecognized-env[^"]*"[^>]*>(.*?)</div>',
            re.DOTALL | re.IGNORECASE,
        )
        for match in wrapper_pattern.finditer(html):
            inner = match.group(1).strip()
            if not inner:
                env_match = re.search(r'data-env="([^"]*)"', match.group(0))
                env_name = env_match.group(1) if env_match else "unknown"
                empty_wrappers.append((chapter_id, env_name))

    assert empty_wrappers == [], (
        f"AC-4 FAIL: the following unrecognized-env wrappers have empty inner HTML: "
        f"{empty_wrappers!r}. "
        "ADR-019 Decision §1: the inner_html path must recurse through inner content "
        "and preserve body content — not drop it silently. "
        "(ADR-019 rejected Alternative C: 'Drop the unknown env entirely'.)"
    )


# ===========================================================================
# Edge: safe-zone stripping sanity — \begin{ inside math must be stripped.
#
# The _strip_safe_regions helper must cover \begin{cases}, \begin{array} etc.
# that legitimately appear inside \[...\] math. If it doesn't, the AC-1 tests
# would produce false positives on valid math content.
# ===========================================================================

def test_strip_safe_regions_removes_begin_inside_display_math() -> None:
    """
    Edge test: the _strip_safe_regions helper must remove \begin{cases} etc.
    that appear inside \[...\] display-math zones.

    If this fails, the AC-1 corpus-wide tests would incorrectly flag math
    content as LaTeX bleed (false positive), making them unreliable.

    ADR-020 §Decision §5: "math delimiters inside fallback raw text are not
    escaped by this helper" — the math-safe-region stripping must be consistent
    between the production code and the test helper.
    """
    sample_html = r"<p>Some prose</p> \[\begin{cases} a \\ b \end{cases}\] <p>more</p>"
    stripped = _strip_safe_regions(sample_html)
    assert r"\begin{" not in stripped, (
        r"Edge FAIL: _strip_safe_regions did NOT remove '\begin{' inside a \[...\] "
        "math zone. This means the AC-1 corpus-wide tests would false-positive on "
        "chapters containing display-math with \begin{cases}/\begin{array} etc. "
        "The _MATH_DISPLAY_PATTERN in _strip_safe_regions must cover this case."
    )


def test_strip_safe_regions_removes_begin_inside_pre_code() -> None:
    """
    Edge test: the _strip_safe_regions helper must remove \begin{lstlisting}
    etc. that appear inside <pre><code> blocks.

    Code listings legitimately show raw LaTeX source — the safe-zone stripping
    must exempt them so the AC-1 tests don't false-positive on lstlisting content.
    """
    sample_html = (
        "<p>prose</p>"
        "<pre><code>\\begin{tabular}{ll} A & B \\end{tabular}</code></pre>"
        "<p>more prose</p>"
    )
    stripped = _strip_safe_regions(sample_html)
    assert r"\begin{" not in stripped, (
        r"Edge FAIL: _strip_safe_regions did NOT remove '\begin{' inside a "
        "<pre><code> block. The AC-1 tests would false-positive on chapters with "
        "lstlisting content that shows raw LaTeX."
    )


def test_strip_safe_regions_preserves_prose_backslash_begin() -> None:
    """
    Negative edge: a literal \begin{ in prose HTML (NOT inside a safe zone) must
    NOT be stripped by _strip_safe_regions.

    This confirms the helper is zone-specific, not a global regex replacement of
    all \begin{ occurrences.
    """
    sample_html = "<p>This has a literal \\begin{foo} in prose</p>"
    stripped = _strip_safe_regions(sample_html)
    assert r"\begin{" in stripped, (
        r"Negative edge FAIL: _strip_safe_regions removed '\begin{' from prose "
        "(outside any safe zone). The helper must only strip safe regions, not "
        "all occurrences of \\begin{ globally. This would cause AC-1 tests to "
        "silently pass even when the parser leaks \\begin{ to prose."
    )


# ===========================================================================
# Performance: all 12 chapters render + prose-check within a generous budget.
#
# AC-1 + AC-2 combined: if the defensive macro-stripping helper has pathological
# scaling (e.g., re.sub on a 200kB HTML string, run 4 times with complex regexes),
# this catches it. 5s per chapter is generous for in-process TestClient.
# ===========================================================================

def test_all_chapters_ac1_ac2_checks_within_time_budget() -> None:
    """
    Performance: all 12 chapter responses can be fetched AND the safe-zone
    stripping + substring checks can be run within 5s per chapter.

    This catches runaway regex behavior in _strip_safe_regions or pathological
    parser output that makes the regex extremely slow. Not a micro-benchmark.

    ADR-003: rendering runs at request time; 5s is extremely generous for a
    local in-process TestClient + a few re.sub passes over HTML.
    """
    client = _get_client()
    slow_chapters = []

    for chapter_id in ALL_CHAPTER_IDS:
        t0 = time.monotonic()
        response = client.get(f"/lecture/{chapter_id}")
        if response.status_code == 200:
            prose = _strip_safe_regions(response.text)
            # Run all the checks to measure combined cost
            _ = r"\begin{" in prose
            _ = r"\end{" in prose
            for token in _GAP_B_MACRO_TOKENS:
                _ = token in prose
        elapsed = time.monotonic() - t0
        if elapsed > 5.0:
            slow_chapters.append((chapter_id, round(elapsed, 2)))

    assert slow_chapters == [], (
        f"Performance FAIL: the following chapters took >5s for fetch + prose "
        f"substring checks: {slow_chapters!r}. "
        "This may indicate a pathological regex or O(n^2) parser behavior. "
        "ADR-003: parsing at request time must not exhibit runaway scaling."
    )
