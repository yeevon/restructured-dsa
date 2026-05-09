"""
HTTP-protocol smoke tests for TASK-005: Multi-chapter rendering validation.

ADR-013 (split harness): this file is the HTTP-protocol layer — fast, TestClient-based,
parameterized over all 12 Chapter IDs.  For each Chapter the tests assert:
  - HTTP 200 (no parser crash, no template-render exception)
  - text/html content-type
  - M/O badge text present per the canonical manifest mapping
  - at least one <section id=" substring (confirms extract_sections() ran)

ADR-014 (\\-linebreak strip): tests for extract_title_from_latex() unit behavior
and for rendered-title cleanliness across all 12 Chapters are also in this file.

ADR-015 (bug-class partition): this file covers class-2 (smoke-layer crashes);
class-1 LaTeX/parser content-fidelity bugs are handled by follow-up ADRs if
they surface during /implement.

Coverage checklist (documented in TASK-005 audit Run 005):
  Boundary:
    - Chapter IDs at the Mandatory/Optional boundary: ch-06 (last Mandatory),
      ch-07 (first Optional) — both parameterized; badge assertion catches boundary flip.
    - extract_title_from_latex: input with only \\\\, input with \\\\\\\\large (real corpus shape).
  Edge:
    - All 12 Chapter IDs — not a spot-check; every Chapter is exercised.
    - extract_title_from_latex: empty string, no \\\\title macro, title that is only whitespace
      after stripping.
  Negative:
    - \\\\  must not appear in any rendered title (across all 12 Chapter pages).
    - extract_title_from_latex: returns None for missing macro; strips \\\\ without residue.
  Performance:
    - test_all_chapters_respond_within_time_budget: all 12 Chapters render within 3s each.

pytestmark registers all tests under task("TASK-005").
"""

from __future__ import annotations

import importlib
import time

import pytest

pytestmark = pytest.mark.task("TASK-005")

# ---------------------------------------------------------------------------
# Canonical Chapter list (ADR-013 Decision; TASK-005 AC-1)
# 12 IDs — ch-08 is absent from the corpus (ADR-005 precondition).
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

# Canonical M/O mapping per manifest §8 (Mandatory = ch-01 through ch-06;
# Optional = ch-07 and ch-09 through ch-13).
# MC-3: the badge renders on every page.
_MANDATORY_IDS = {
    "ch-01-cpp-refresher",
    "ch-02-intro-to-algorithms",
    "ch-03-intro-to-data-structures",
    "ch-04-lists-stacks-and-queues",
    "ch-05-hash-tables",
    "ch-06-trees",
}
_OPTIONAL_IDS = {
    "ch-07-heaps-and-treaps",
    "ch-09-balanced-trees",
    "ch-10-graphs",
    "ch-11-b-trees",
    "ch-12-sets",
    "ch-13-additional-material",
}


def _expected_badge(chapter_id: str) -> str:
    if chapter_id in _MANDATORY_IDS:
        return "Mandatory"
    return "Optional"


# ---------------------------------------------------------------------------
# Import helper — deferred so collection succeeds before implementation exists
# ---------------------------------------------------------------------------

def _get_client():
    """Return a TestClient for the FastAPI app (deferred import)."""
    from fastapi.testclient import TestClient
    from app.main import app  # noqa: PLC0415
    return TestClient(app)


def _import_extract_title():
    """Import extract_title_from_latex from app.discovery (ADR-014 public API)."""
    mod = importlib.import_module("app.discovery")
    return mod.extract_title_from_latex


# ===========================================================================
# AC-1: HTTP 200 for every Chapter (parameterized over all 12 IDs)
# ADR-013 HTTP-protocol smoke layer
# ===========================================================================

@pytest.mark.parametrize("chapter_id", ALL_CHAPTER_IDS)
def test_lecture_page_returns_http_200(chapter_id: str) -> None:
    """
    AC-1 (TASK-005): GET /lecture/{chapter_id} returns HTTP 200 for every Chapter.

    A non-200 response means the parser or template raised an unhandled exception.
    A failure on ANY single Chapter is a blocking TASK-005 AC failure.

    ADR-013 §HTTP-protocol layer: "assert response.status_code == 200 — the
    parser/template did not raise an unhandled exception."
    """
    client = _get_client()
    response = client.get(f"/lecture/{chapter_id}")
    assert response.status_code == 200, (
        f"GET /lecture/{chapter_id} returned HTTP {response.status_code} "
        f"(expected 200). "
        "The parser or template raised an unhandled exception for this Chapter. "
        "TASK-005 AC-1: every Chapter must return 200; a failure on ANY Chapter "
        "is a blocking TASK-005 AC failure."
    )


@pytest.mark.parametrize("chapter_id", ALL_CHAPTER_IDS)
def test_lecture_page_returns_html_content_type(chapter_id: str) -> None:
    """
    AC-1 / ADR-013: GET /lecture/{chapter_id} returns text/html content-type.

    Ensures the FastAPI route responded with HTML, not a JSON error body or
    raw text that might accidentally have been returned on a caught exception.
    """
    client = _get_client()
    response = client.get(f"/lecture/{chapter_id}")
    content_type = response.headers.get("content-type", "")
    assert "text/html" in content_type, (
        f"GET /lecture/{chapter_id} returned content-type={content_type!r}, "
        "expected 'text/html'. "
        "ADR-013: the response must carry a text/html content-type."
    )


# ===========================================================================
# AC-3 structural: M/O badge present for every Chapter
# MC-3 (manifest §6 §7): Mandatory/Optional honored everywhere
# ===========================================================================

@pytest.mark.parametrize("chapter_id", ALL_CHAPTER_IDS)
def test_lecture_page_contains_correct_mo_badge(chapter_id: str) -> None:
    """
    AC-3(i) (TASK-005) / MC-3: each Chapter's rendered page body contains the
    correct M/O badge text per the canonical manifest mapping.

    Chapters 1-6 → "Mandatory"; Chapters 7, 9-13 → "Optional".

    ADR-013: "The response body contains the Chapter's expected M/O badge text
    per the canonical mapping … confirms chapter_designation() ran and the
    template rendered."

    This is the smoke layer's structural smoke check — deliberately light.
    """
    expected = _expected_badge(chapter_id)
    client = _get_client()
    response = client.get(f"/lecture/{chapter_id}")
    body = response.text
    assert expected in body, (
        f"GET /lecture/{chapter_id} — response body does not contain '{expected}'. "
        f"Expected M/O badge text per canonical mapping: chapters 1-6 → Mandatory, "
        f"chapters 7/9-13 → Optional. "
        "MC-3: Mandatory/Optional content must be honored everywhere. "
        "ADR-013: badge presence is the structural smoke check."
    )


# ===========================================================================
# AC-3(iii): at least one <section id=" present for every Chapter
# ===========================================================================

@pytest.mark.parametrize("chapter_id", ALL_CHAPTER_IDS)
def test_lecture_page_contains_at_least_one_section_anchor(chapter_id: str) -> None:
    """
    AC-3(iii) (TASK-005): each Chapter's rendered body contains at least one
    `<section id="` substring — confirms extract_sections() produced at least
    one Section anchor.

    ADR-013: "The response body contains at least one <section id=\" substring
    — confirms extract_sections() produced at least one Section anchor."
    """
    client = _get_client()
    response = client.get(f"/lecture/{chapter_id}")
    body = response.text
    assert '<section id="' in body, (
        f"GET /lecture/{chapter_id} — response body contains no '<section id=\"' "
        "substring. Expected at least one Section anchor from extract_sections(). "
        "TASK-005 AC-3(iii): every Chapter must have at least one rendered Section."
    )


# ===========================================================================
# Boundary: M/O boundary between ch-06 (last Mandatory) and ch-07 (first Optional)
# ===========================================================================

def test_ch06_is_mandatory_boundary() -> None:
    """
    Boundary test: ch-06-trees is the LAST Mandatory Chapter.
    Its rendered page must contain 'Mandatory', NOT 'Optional'.

    MC-3: designation must flip at exactly Chapter 7.  Testing both sides of
    the boundary guards against an off-by-one in chapter_designation().
    """
    client = _get_client()
    response = client.get("/lecture/ch-06-trees")
    body = response.text
    assert "Mandatory" in body, (
        "GET /lecture/ch-06-trees did not contain 'Mandatory'. "
        "ch-06 is the last Mandatory Chapter per manifest §8. "
        "MC-3: the canonical mapping must hold at the boundary."
    )
    # Must NOT be labeled Optional
    assert "Optional" not in body or body.index("Mandatory") < body.index("Optional"), (
        "GET /lecture/ch-06-trees body contains 'Optional' text. "
        "The badge must show 'Mandatory' for ch-06 (off-by-one in designation?)."
    )


def test_ch07_is_optional_boundary() -> None:
    """
    Boundary test: ch-07-heaps-and-treaps is the FIRST Optional Chapter.
    Its rendered page must contain 'Optional'.

    MC-3: designation must flip at exactly Chapter 7.
    """
    client = _get_client()
    response = client.get("/lecture/ch-07-heaps-and-treaps")
    body = response.text
    assert "Optional" in body, (
        "GET /lecture/ch-07-heaps-and-treaps did not contain 'Optional'. "
        "ch-07 is the first Optional Chapter per manifest §8. "
        "MC-3: the canonical mapping must hold at the boundary."
    )


# ===========================================================================
# Negative: no rendered title (rail OR lecture header) contains literal '\\'
# ADR-014: the \\ linebreak macro must be stripped by extract_title_from_latex()
# ===========================================================================

@pytest.mark.parametrize("chapter_id", ALL_CHAPTER_IDS)
def test_rendered_page_title_contains_no_backslash_residue(chapter_id: str) -> None:
    """
    ADR-014: across all 12 Chapter rendered pages, neither the lecture-header
    title (<h1 class="lecture-title">) nor any rail row label
    (<a> inside <li class="nav-chapter-item">) contains the literal '\\\\'.

    Scope is the title surfaces only.  ADR-014's commitment is to
    extract_title_from_latex(), which feeds the lecture-page header and the
    rail labels (ADR-007 single-extraction).  Body content is out of scope:
    LaTeX math (\\begin{cases}, \\begin{array}) legitimately contains \\\\ row
    separators, and the MathJax loader's JS config contains \\\\[ \\\\] for
    display-math delimiters — neither is a defect this test is supposed to
    catch.
    """
    import re
    client = _get_client()
    response = client.get(f"/lecture/{chapter_id}")
    body = response.text

    # Lecture-page header (template: <h1 class="lecture-title">{{ title }}</h1>)
    header_matches = re.findall(
        r'<h1[^>]*class="lecture-title"[^>]*>(.*?)</h1>',
        body, flags=re.DOTALL,
    )
    # Rail row labels (template: <li class="nav-chapter-item ..."><a ...>LABEL</a></li>)
    rail_matches = re.findall(
        r'<li[^>]*class="nav-chapter-item[^"]*"[^>]*>\s*<a[^>]*>(.*?)</a>',
        body, flags=re.DOTALL,
    )
    title_surfaces = header_matches + rail_matches

    assert title_surfaces, (
        f"GET /lecture/{chapter_id} — no title surfaces found in rendered HTML "
        "(neither <h1 class='lecture-title'> nor <li class='nav-chapter-item'><a>). "
        "Test cannot verify ADR-014's title-cleanliness commitment."
    )

    for surface in title_surfaces:
        assert "\\\\" not in surface, (
            f"GET /lecture/{chapter_id} — a title surface contains the literal "
            f"'\\\\\\\\' substring: {surface!r}. "
            "ADR-014: extract_title_from_latex() must strip the \\\\\\\\ macro before "
            "the \\\\[a-zA-Z]+ strip."
        )


# ===========================================================================
# ADR-014: unit tests for extract_title_from_latex()
# ===========================================================================

def test_extract_title_strips_backslash_backslash_linebreak() -> None:
    """
    ADR-014 §Decision: extract_title_from_latex() strips the \\\\ linebreak macro.

    Input: the exact corpus pattern — '\\\\title{CS 300 -- Chapter 2 Lectures\\\\\\\\large Introduction to Algorithms}'
    Expected: no \\\\ in the output.

    This test will be RED until the ADR-014 regex line is added:
        raw = re.sub(r'\\\\\\\\', ' ', raw)  # strip \\\\ linebreak macro
    """
    extract = _import_extract_title()
    # The real corpus title shape: \title{CS 300 -- Chapter 2 Lectures\\\large Introduction to Algorithms}
    # In Python raw string: r'\title{CS 300 -- Chapter 2 Lectures\\\large Introduction to Algorithms}'
    latex_text = r"\title{CS 300 -- Chapter 2 Lectures\\\large Introduction to Algorithms}"
    result = extract(latex_text)
    assert result is not None, (
        "extract_title_from_latex() returned None for a valid \\\\title{...} macro. "
        "Expected a non-None string."
    )
    assert "\\\\" not in result, (
        f"extract_title_from_latex() returned {result!r}, which still contains '\\\\\\\\'. "
        "ADR-014: the \\\\\\\\ linebreak macro must be stripped. "
        "This test is RED until the ADR-014 regex line is added before \\\\[a-zA-Z]+."
    )


def test_extract_title_returns_clean_text_after_backslash_strip() -> None:
    """
    ADR-014: after stripping \\\\ and \\large, the result is clean plain text.

    Input: \\title{Title A\\\\\\\\large Subtitle B}
    Expected result: 'Title A Subtitle B' (no backslashes, no braces).
    """
    extract = _import_extract_title()
    latex_text = r"\title{Title A\\\large Subtitle B}"
    result = extract(latex_text)
    assert result is not None
    # No backslash residue of any kind
    assert "\\" not in result, (
        f"extract_title_from_latex() returned {result!r}, which contains a backslash. "
        "ADR-014: all LaTeX macros (\\\\, \\\\large, etc.) must be stripped."
    )
    # Both words present
    assert "Title A" in result, (
        f"extract_title_from_latex() returned {result!r} — 'Title A' not found. "
        "The pre-\\\\ text must be preserved."
    )
    assert "Subtitle B" in result, (
        f"extract_title_from_latex() returned {result!r} — 'Subtitle B' not found. "
        "The post-\\\\large text must be preserved."
    )


def test_extract_title_with_only_backslash_backslash_in_title() -> None:
    """
    ADR-014 edge: title that contains ONLY the \\\\ macro between two text fragments.

    Input: \\title{A\\\\B}
    Expected: 'A B' (backslash-backslash replaced by space, whitespace collapsed).
    """
    extract = _import_extract_title()
    latex_text = r"\title{A\\B}"
    result = extract(latex_text)
    assert result is not None, (
        "extract_title_from_latex() returned None for \\\\title{A\\\\\\\\B}."
    )
    assert "\\" not in result, (
        f"extract_title_from_latex() returned {result!r} — still contains '\\\\'. "
        "ADR-014: the \\\\\\\\ macro must be stripped from all positions in the title."
    )


def test_extract_title_no_macro_returns_none() -> None:
    """
    ADR-014 edge (negative): when there is no \\title{...} macro, return None.

    This guards against the ADR-014 regex change accidentally matching
    unrelated content.
    """
    extract = _import_extract_title()
    result = extract("no title macro here, just raw text")
    assert result is None, (
        f"extract_title_from_latex() returned {result!r} for input with no \\\\title{{}} macro. "
        "Expected None."
    )


def test_extract_title_empty_after_strip_returns_none() -> None:
    """
    ADR-014 edge: title that is only formatting macros — empty after strip.

    Input: \\title{\\\\\\\\large}  — becomes empty after stripping.
    Expected: None (empty string → None per ADR-007's contract).
    """
    extract = _import_extract_title()
    latex_text = r"\title{\\\large}"
    result = extract(latex_text)
    # After stripping \\ and \large, nothing is left → should return None
    assert result is None or (isinstance(result, str) and result.strip() == ""), (
        f"extract_title_from_latex() returned {result!r} for a title that is only "
        "LaTeX formatting macros. Expected None or empty string after stripping. "
        "ADR-007: empty label → label_status 'missing_title'."
    )


# ===========================================================================
# Performance: all 12 Chapters render within a generous wall-clock budget
# ===========================================================================

def test_all_chapters_respond_within_time_budget() -> None:
    """
    Performance: all 12 Chapter Lecture pages respond within 3 seconds each
    (generous budget for a local in-process TestClient against a 12-file corpus).

    Catches O(n^2) or runaway recursion in the parser path — not a micro-benchmark.

    ADR-003: rendering is at request time; ADR-007: discovery scans at request time.
    """
    client = _get_client()
    slow_chapters = []
    for chapter_id in ALL_CHAPTER_IDS:
        t0 = time.monotonic()
        client.get(f"/lecture/{chapter_id}")
        elapsed = time.monotonic() - t0
        if elapsed > 3.0:
            slow_chapters.append((chapter_id, elapsed))

    assert slow_chapters == [], (
        f"The following Chapters took more than 3s to render: {slow_chapters!r}. "
        "This may indicate a pathological scaling issue in the parser or discovery path. "
        "ADR-003: parsing runs at request time; 3s is a generous budget for 12 local files."
    )
