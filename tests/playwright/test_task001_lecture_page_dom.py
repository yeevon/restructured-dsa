"""
Playwright DOM-content tests migrated from tests/test_task001_lecture_page.py.

Per ADR-010 "Migration scope":
  Migrates to Playwright (DOM-content assertions):
  - test_ac2_all_expected_section_anchors_present
  - test_ac2_section_count_matches_source
  - test_ac2_subsections_do_not_get_section_ids
  - test_ac3_mandatory_badge_present
  - test_ac3_mandatory_not_optional
  - test_ac4_no_timestamp_in_rendered_html
  - test_adr001_preamble_content_not_treated_as_lecture_body

  Stays in pytest (non-DOM-content assertions):
  - test_ac1_lecture_page_returns_200        (HTTP status)
  - test_ac1_lecture_page_content_type_is_html  (HTTP header)
  - test_ac1_response_body_is_non_empty      (HTTP body-length sanity)
  - test_ac4_two_renders_are_byte_identical  (byte-equality of two responses)
  - test_ac5_no_write_to_content_latex_during_render  (monkeypatch side-effect)
  - test_adr001_renderer_reads_from_correct_path      (monkeypatch read spy)

These tests target the live corpus (ch-01-cpp-refresher.tex must exist in
content/latex/ for these tests to pass).  They use the `live_server` fixture
from tests/playwright/conftest.py.

pytestmark registers all tests under task("TASK-001") to preserve task association.
"""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.task("TASK-001")

CHAPTER_ID = "ch-01-cpp-refresher"
LECTURE_URL_PATH = f"/lecture/{CHAPTER_ID}"

# Section fragments expected in the rendered HTML (from source grep)
EXPECTED_SECTION_FRAGMENTS = [
    "section-1-1",  "section-1-2",  "section-1-3",  "section-1-4",  "section-1-5",
    "section-1-6",  "section-1-7",  "section-1-8",  "section-1-9",  "section-1-10",
    "section-1-11", "section-1-12", "section-1-13", "section-1-14", "section-1-15",
]


# ---------------------------------------------------------------------------
# AC2 — Section addressability
# ---------------------------------------------------------------------------


def test_ac2_all_expected_section_anchors_present(page: Page, live_server: str) -> None:
    """
    AC2: Every expected Section fragment appears as an id on an element in the
    rendered page (navigable anchor).

    ADR-002: HTML anchor ID for a Section is the fragment part of the Section ID.
    ADR-003: template emits <section id="{section_id}"> anchors.
    Trace: TASK-001 AC2; ADR-010 migration.
    """
    page.goto(live_server + LECTURE_URL_PATH)
    page.wait_for_load_state("networkidle")

    for fragment in EXPECTED_SECTION_FRAGMENTS:
        element = page.locator(f"[id='{fragment}']")
        assert element.count() >= 1, (
            f"Section anchor id='{fragment}' is not present in the rendered DOM. "
            "ADR-002: every \\section macro must produce an id-bearing element."
        )


def test_ac2_section_count_matches_source(page: Page, live_server: str) -> None:
    """
    AC2: The number of section anchor elements matches the source (15 for ch-01).

    ADR-002: only \\section produces Section IDs.
    Trace: TASK-001 AC2; ADR-010 migration.
    """
    page.goto(live_server + LECTURE_URL_PATH)
    page.wait_for_load_state("networkidle")

    # Count elements with id matching "section-1-N"
    html = page.content()
    found_ids = re.findall(r'id="(section-\d+-\d+)"', html)

    assert len(found_ids) == len(EXPECTED_SECTION_FRAGMENTS), (
        f"Expected {len(EXPECTED_SECTION_FRAGMENTS)} section anchor IDs, "
        f"found {len(found_ids)}: {found_ids}. "
        "ADR-002: section anchor count must match source \\section macro count."
    )


def test_ac2_subsections_do_not_get_section_ids(page: Page, live_server: str) -> None:
    """
    AC2 / ADR-002: \\subsection macros must NOT produce Section-ID anchors.

    Trace: TASK-001 AC2; ADR-002; ADR-010 migration.
    """
    page.goto(live_server + LECTURE_URL_PATH)
    page.wait_for_load_state("networkidle")

    html = page.content()
    found_ids = re.findall(r'id="(section-[\d-]+)"', html)
    unexpected = [sid for sid in found_ids if sid not in EXPECTED_SECTION_FRAGMENTS]

    assert unexpected == [], (
        f"Unexpected section-like anchor IDs in rendered DOM (subsections promoted?): "
        f"{unexpected}. ADR-002: only \\section macros produce Section anchors."
    )


# ---------------------------------------------------------------------------
# AC3 — Mandatory badge visible
# ---------------------------------------------------------------------------


def test_ac3_mandatory_badge_present(page: Page, live_server: str) -> None:
    """
    AC3: The rendered Lecture page for Chapter 1 contains an unambiguous
    'Mandatory' indicator (the designation badge in the lecture header).

    Manifest §8: Chapters 1–6 are Mandatory.
    ADR-004: chapter_designation('ch-01-cpp-refresher') → 'Mandatory'.
    ADR-003: Jinja2 template renders a top-of-page badge.
    Trace: TASK-001 AC3; ADR-010 migration.
    """
    page.goto(live_server + LECTURE_URL_PATH)
    page.wait_for_load_state("networkidle")

    # The badge is .designation-badge inside .lecture-header
    badge = page.locator(".lecture-header .designation-badge")
    expect(badge).to_be_visible()
    badge_text = badge.text_content() or ""
    assert "Mandatory" in badge_text, (
        f"Designation badge text is '{badge_text}', expected to contain 'Mandatory'. "
        "ADR-004: Chapter 1 must be labeled Mandatory."
    )


def test_ac3_mandatory_not_optional(page: Page, live_server: str) -> None:
    """
    AC3: Chapter 1's own designation badge says 'Mandatory', not 'Optional'.

    This is scoped to the lecture-header block — the rail legitimately shows
    an "Optional" heading but the lecture body's OWN badge must be Mandatory.

    ADR-006 introduced a navigation rail with an "Optional" section that
    appears on every Lecture page; the assertion is scoped to the lecture-header.

    Trace: TASK-001 AC3; ADR-004; ADR-006; manifest §8; ADR-010 migration.
    """
    page.goto(live_server + LECTURE_URL_PATH)
    page.wait_for_load_state("networkidle")

    header = page.locator(".lecture-header")
    expect(header).to_be_visible()

    # Badge within the lecture-header
    badge = header.locator(".designation-badge")
    expect(badge).to_be_visible()

    badge_text = badge.text_content() or ""
    assert "Mandatory" in badge_text, (
        "lecture-header badge does not contain 'Mandatory'."
    )
    assert "Optional" not in badge_text, (
        f"lecture-header badge contains 'Optional' (badge text: {badge_text!r}). "
        "Chapter 1's own badge must be Mandatory, not Optional."
    )


# ---------------------------------------------------------------------------
# AC4 — No timestamp in rendered HTML
# ---------------------------------------------------------------------------


def test_ac4_no_timestamp_in_rendered_html(page: Page, live_server: str) -> None:
    """
    AC4 / ADR-003: Template must NOT inject a timestamp into the output.

    ADR-003 Determinism: "no randomness; no clock-derived content."
    Trace: TASK-001 AC4; ADR-010 migration.
    """
    page.goto(live_server + LECTURE_URL_PATH)
    page.wait_for_load_state("networkidle")

    html = page.content()
    # ISO-8601 date fragment: YYYY-MM-DD
    iso_dates = re.findall(r"\b\d{4}-\d{2}-\d{2}\b", html)

    assert iso_dates == [], (
        f"Possible timestamps found in rendered HTML: {iso_dates}. "
        "ADR-003 forbids injecting timestamps."
    )


# ---------------------------------------------------------------------------
# ADR-001 — Preamble content not treated as Lecture body
# ---------------------------------------------------------------------------


def test_adr001_preamble_content_not_treated_as_lecture_body(
    page: Page, live_server: str
) -> None:
    """
    ADR-001 §2: preamble macros must NOT appear verbatim in the rendered HTML.

    Strategy: the \\documentclass, \\input, \\title, \\author, \\date macros
    must not appear as raw text in the rendered DOM.

    Trace: TASK-001 ADR-001 §2; ADR-010 migration.
    """
    page.goto(live_server + LECTURE_URL_PATH)
    page.wait_for_load_state("networkidle")

    html = page.content()
    preamble_macro_leaks = [
        r"\documentclass",
        r"\input{",
        r"\author{",
        r"\date{",
    ]
    for macro in preamble_macro_leaks:
        assert macro not in html, (
            f"Preamble macro '{macro}' leaked into rendered HTML. "
            "ADR-001: preamble is not Lecture content."
        )
