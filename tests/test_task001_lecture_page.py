"""
Integration tests for TASK-001: Render Chapter 1 as a viewable Lecture page.

Each test traces to a specific acceptance criterion (AC) or ADR commitment.
All tests are expected to FAIL until the implementation exists.

pytestmark registers all tests in this file under the task marker so they can
be targeted with:  pytest -m 'task("TASK-001")'
"""

import pathlib
import re
import unittest.mock
from typing import Generator

import pytest

pytestmark = pytest.mark.task("TASK-001")

# ---------------------------------------------------------------------------
# Expected section-anchor IDs derived directly from the real source file.
# grep -n '\\section{' content/latex/ch-01-cpp-refresher.tex revealed 15
# sections numbered 1.1 through 1.15.
# ADR-002: section anchor ID fragment = "section-{number-with-dot-as-hyphen}"
# ---------------------------------------------------------------------------
EXPECTED_SECTION_FRAGMENTS = [
    "section-1-1",
    "section-1-2",
    "section-1-3",
    "section-1-4",
    "section-1-5",
    "section-1-6",
    "section-1-7",
    "section-1-8",
    "section-1-9",
    "section-1-10",
    "section-1-11",
    "section-1-12",
    "section-1-13",
    "section-1-14",
    "section-1-15",
]

CHAPTER_ID = "ch-01-cpp-refresher"

# ---------------------------------------------------------------------------
# AC1 — Lecture page reachable
# ---------------------------------------------------------------------------


def test_ac1_lecture_page_returns_200(ch01_lecture_response):
    """
    AC1: GET /lecture/ch-01-cpp-refresher returns HTTP 200.

    Trace: TASK-001 AC1 — "a Lecture page for Chapter 1 is reachable locally".
    ADR-003: FastAPI exposes GET /lecture/{chapter_id}.
    """
    assert ch01_lecture_response.status_code == 200


def test_ac1_lecture_page_content_type_is_html(ch01_lecture_response):
    """
    AC1: The response content-type indicates HTML.

    Trace: TASK-001 AC1 — "renders the chapter's prose readably";
    ADR-003 — pipeline emits one HTML page per Chapter.
    """
    content_type = ch01_lecture_response.headers.get("content-type", "")
    assert "text/html" in content_type


def test_ac1_response_body_is_non_empty(ch01_lecture_response):
    """
    AC1: The HTML body is non-trivially populated (more than a blank page).

    Trace: TASK-001 AC1 — "renders the chapter's prose readably".
    """
    html = ch01_lecture_response.text
    assert len(html) > 200, "Response body is suspiciously short — expected rendered prose"


# ---------------------------------------------------------------------------
# AC2 — Section addressability
# ---------------------------------------------------------------------------


def test_ac2_all_expected_section_anchors_present(ch01_lecture_response):
    """
    AC2: HTML contains an <section> or element with id matching every expected
    Section fragment derived from the real source file.

    ADR-002: HTML anchor ID for a Section is the fragment part of the Section ID
    (the part after '#' in 'ch-01-cpp-refresher#section-1-1' is 'section-1-1').
    ADR-003: template emits <section id="{section_id}"> anchors.
    Trace: TASK-001 AC2 — "each Section in the LaTeX source appears as an
    addressable region of the page".
    """
    html = ch01_lecture_response.text
    for fragment in EXPECTED_SECTION_FRAGMENTS:
        # id attribute can appear on any element; we check the string is present.
        assert f'id="{fragment}"' in html, (
            f"Missing section anchor id=\"{fragment}\" in rendered HTML"
        )


def test_ac2_section_count_matches_source(ch01_lecture_response):
    """
    AC2: The number of Section anchors in the HTML matches the number of
    \\section macros in the source (15 for ch-01-cpp-refresher.tex).

    Trace: TASK-001 AC2.  ADR-002: only \\section produces Section IDs.
    """
    html = ch01_lecture_response.text
    # Count id="section-1-NNN" attributes — the pattern ADR-002 mandates.
    found_ids = re.findall(r'id="(section-\d+-\d+)"', html)
    assert len(found_ids) == len(EXPECTED_SECTION_FRAGMENTS), (
        f"Expected {len(EXPECTED_SECTION_FRAGMENTS)} section anchors, "
        f"found {len(found_ids)}: {found_ids}"
    )


def test_ac2_subsections_do_not_get_section_ids(ch01_lecture_response):
    """
    AC2 / ADR-002: \\subsection macros must NOT produce Section-ID anchors.

    ADR-002: "Only LaTeX \\section{...} macros at the document body level
    produce a Section anchor. \\subsection{...} and deeper ... are not
    manifest Sections."

    Strategy: the rendered HTML must not contain anchor IDs that look like
    section IDs beyond the 15 expected ones.  Any extra id="section-*"
    attributes would indicate subsections were incorrectly promoted.
    """
    html = ch01_lecture_response.text
    found_ids = re.findall(r'id="(section-[\d-]+)"', html)
    unexpected = [sid for sid in found_ids if sid not in EXPECTED_SECTION_FRAGMENTS]
    assert unexpected == [], (
        f"Found unexpected section-like anchor IDs (subsections promoted?): {unexpected}"
    )


# ---------------------------------------------------------------------------
# AC3 — Mandatory badge visible
# ---------------------------------------------------------------------------


def test_ac3_mandatory_badge_present(ch01_lecture_response):
    """
    AC3: The rendered HTML contains an unambiguous 'Mandatory' indicator.

    Manifest §8: Chapters 1–6 are Mandatory.
    ADR-004: chapter_designation('ch-01-cpp-refresher') → 'Mandatory'.
    ADR-003: Jinja2 template renders a top-of-page badge.
    Trace: TASK-001 AC3 — "the Chapter is unambiguously labeled as Mandatory ...
    the designation is visible and not buried."
    """
    html = ch01_lecture_response.text
    assert "Mandatory" in html, (
        "HTML does not contain the text 'Mandatory'; Chapter 1 badge is missing."
    )


def test_ac3_mandatory_not_optional(ch01_lecture_response):
    """
    AC3: Chapter 1's own designation badge says 'Mandatory', not 'Optional'.

    Scope: the `<header class="lecture-header">` block of the lecture body —
    i.e. the chapter's own badge + title. NOT the page-wide HTML. ADR-006
    introduced a navigation rail with a labeled "Optional" section that
    legitimately appears on every Lecture page (including Mandatory chapters);
    the original whole-HTML substring assertion is overbroad after ADR-006.

    Trace: TASK-001 AC3.  ADR-004.  ADR-006.  Manifest §8.
    """
    html = ch01_lecture_response.text

    header_match = re.search(
        r'<header class="lecture-header">.*?</header>',
        html,
        re.DOTALL,
    )
    assert header_match, "lecture-header block missing from rendered page"
    lecture_header = header_match.group(0)

    assert "Mandatory" in lecture_header, (
        "Chapter 1's lecture-header block does not contain 'Mandatory'."
    )
    assert "Optional" not in lecture_header, (
        "Chapter 1's lecture-header block contains 'Optional' — its own "
        "badge should be Mandatory."
    )


# ---------------------------------------------------------------------------
# AC4 — Determinism
# ---------------------------------------------------------------------------


def test_ac4_two_renders_are_byte_identical(lecture_client):
    """
    AC4: Two GET /lecture/ch-01-cpp-refresher responses (same process, same
    source, sequential) are byte-identical.

    ADR-003 Determinism: "Two runs against the same content/latex/{chapter_id}.tex
    ... produce byte-identical HTML. No randomness; no clock-derived content."
    Trace: TASK-001 AC4.
    """
    r1 = lecture_client.get("/lecture/ch-01-cpp-refresher")
    r2 = lecture_client.get("/lecture/ch-01-cpp-refresher")

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.text == r2.text, (
        "Two sequential renders of Chapter 1 produced different HTML. "
        "Pipeline is non-deterministic."
    )


def test_ac4_no_timestamp_in_rendered_html(ch01_lecture_response):
    """
    AC4 / ADR-003: Template must NOT inject a timestamp into the output.

    ADR-003: "the template must not inject [a timestamp] for TASK-001."
    A timestamp would make every render byte-different and violate determinism.

    Strategy: look for common timestamp patterns (ISO 8601, HTTP date format,
    year-only) in the HTML.  This is a heuristic; the core determinism test
    above is the authoritative check.
    """
    html = ch01_lecture_response.text
    # ISO-8601 date fragment: YYYY-MM-DD
    iso_dates = re.findall(r"\b\d{4}-\d{2}-\d{2}\b", html)
    assert iso_dates == [], (
        f"Possible timestamps found in rendered HTML: {iso_dates}. "
        "ADR-003 forbids injecting timestamps."
    )


# ---------------------------------------------------------------------------
# AC5 — Read-only source (integration-level check via monkeypatching)
# ---------------------------------------------------------------------------


def test_ac5_no_write_to_content_latex_during_render(repo_root, monkeypatch):
    """
    AC5: No path under content/latex/ is opened for writing during a render.

    Manifest §5 / §6: "The application does not modify the source."
    ADR-001 §3: "No path under content/latex/ is ever opened for writing,
    created, deleted, or moved by application code."
    Trace: TASK-001 AC5.

    Strategy: monkeypatch pathlib.Path.open and builtins.open to intercept
    every file-open call; assert that zero calls target content/latex/ with a
    write mode.
    """
    import builtins

    content_latex_str = str(repo_root / "content" / "latex")
    write_modes = {"w", "wb", "a", "ab", "x", "xb", "w+", "wb+", "a+", "ab+"}
    write_calls_detected: list[str] = []

    original_builtin_open = builtins.open
    original_path_open = pathlib.Path.open

    def guarded_builtin_open(file, mode="r", *args, **kwargs):
        mode_str = str(mode)
        if any(m in mode_str for m in write_modes):
            file_str = str(file)
            if content_latex_str in file_str:
                write_calls_detected.append(f"builtins.open({file_str!r}, {mode!r})")
        return original_builtin_open(file, mode, *args, **kwargs)

    def guarded_path_open(self, mode="r", *args, **kwargs):
        mode_str = str(mode)
        if any(m in mode_str for m in write_modes):
            path_str = str(self)
            if content_latex_str in path_str:
                write_calls_detected.append(f"Path.open({path_str!r}, {mode!r})")
        return original_path_open(self, mode, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", guarded_builtin_open)
    monkeypatch.setattr(pathlib.Path, "open", guarded_path_open)

    # Trigger a full render via the FastAPI app.
    from fastapi.testclient import TestClient
    from app.main import app  # noqa: PLC0415

    client = TestClient(app)
    response = client.get("/lecture/ch-01-cpp-refresher")
    assert response.status_code == 200  # render actually ran

    assert write_calls_detected == [], (
        f"Write operations detected against content/latex/ during render: "
        f"{write_calls_detected}"
    )


# ---------------------------------------------------------------------------
# ADR-001 — input contract
# ---------------------------------------------------------------------------


def test_adr001_renderer_reads_from_correct_path(repo_root, monkeypatch):
    """
    ADR-001 §1, §2: The renderer reads from content/latex/{chapter_id}.tex and
    treats the content of \\begin{document}...\\end{document} as the Lecture body.

    Strategy: monkeypatch builtins.open / pathlib.Path.read_text / .open to
    record which files are opened for reading during a render.  Assert that
    content/latex/ch-01-cpp-refresher.tex is among the files read.

    ASSUMPTION: The renderer will use either pathlib.Path.read_text,
    pathlib.Path.open, or builtins.open to read the source file.
    """
    import builtins

    expected_source = str(repo_root / "content" / "latex" / "ch-01-cpp-refresher.tex")
    files_read: list[str] = []

    original_builtin_open = builtins.open
    original_read_text = pathlib.Path.read_text

    def spy_builtin_open(file, mode="r", *args, **kwargs):
        if "r" in str(mode) or mode == "r":
            files_read.append(str(file))
        return original_builtin_open(file, mode, *args, **kwargs)

    def spy_read_text(self, *args, **kwargs):
        files_read.append(str(self))
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", spy_builtin_open)
    monkeypatch.setattr(pathlib.Path, "read_text", spy_read_text)

    from fastapi.testclient import TestClient
    from app.main import app  # noqa: PLC0415

    client = TestClient(app)
    response = client.get("/lecture/ch-01-cpp-refresher")
    assert response.status_code == 200

    assert any(expected_source in f for f in files_read), (
        f"Expected the renderer to read '{expected_source}', "
        f"but observed reads were: {files_read}"
    )


def test_adr001_preamble_content_not_treated_as_lecture_body(ch01_lecture_response):
    """
    ADR-001 §2: Everything before \\begin{document} is preamble; the renderer
    must not treat preamble macros as Lecture content.

    Strategy: the \\documentclass, \\input, \\title, \\author, \\date macros
    that appear in the preamble must NOT appear verbatim in the rendered HTML
    body as raw LaTeX commands.  Their text may appear in processed form (e.g.
    the title string), but the raw macro names must not leak through.
    """
    html = ch01_lecture_response.text
    # Raw LaTeX preamble macros that must not appear verbatim in the output
    preamble_macro_leaks = [
        r"\documentclass",
        r"\input{",
        r"\author{",
        r"\date{",
    ]
    for macro in preamble_macro_leaks:
        assert macro not in html, (
            f"Preamble macro '{macro}' leaked into rendered HTML body. "
            "ADR-001: preamble is not Lecture content."
        )
