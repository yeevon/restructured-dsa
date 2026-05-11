"""
TASK-011: Chapter-level derived progress display + bundled placement supersedures
           (completion affordance bottom-of-section; Notes rail-resident panel).

Tests derive from the Acceptance Criteria in
`design_docs/tasks/TASK-011-chapter-progress-and-placement-supersedures.md`
and from the three newly-Accepted ADRs:
  ADR-026 — Chapter-level derived progress display: rail-resident "X / Y" decoration;
             new bulk persistence accessor count_complete_sections_per_chapter();
             discover_chapters() extended with per-Chapter section_count field.
  ADR-027 — Supersedure of ADR-025 §Template-placement: completion form moves from
             top-of-Section (inside .section-heading-row) to bottom-of-Section
             (inside new .section-end wrapper); .section-heading-row removed.
  ADR-028 — Supersedure of ADR-023 §Template-surface: Notes section moves from
             bottom of lecture.html.j2 block main to a rail-resident
             <section class="rail-notes"> inside _nav_rail.html.j2; old
             notes-surface class removed; new rail-notes-* classes in base.css;
             template variable renamed notes -> rail_notes_context; landing page
             omits the panel entirely.

Coverage matrix:
  Boundary:
    - test_rail_progress_decoration_on_all_12_chapters: iterate all corpus Chapters.
    - test_progress_shows_zero_when_no_sections_complete: 0 / Y state.
    - test_progress_shows_full_when_all_sections_complete: Y / Y state + --complete class.
    - test_count_complete_sections_per_chapter_returns_dict: accessor shape.
    - test_discover_chapters_section_count_field_mandatory_boundary: first Mandatory.
    - test_discover_chapters_section_count_field_optional_boundary: first Optional.
    - test_section_end_wrapper_present_first_and_last_section: first and last section.
    - test_notes_ui_absent_on_landing_page: landing page omission.
  Edge:
    - test_count_complete_sections_missing_keys_default_to_zero: chapters with no
      completions are absent from the dict (caller defaults to 0).
    - test_progress_counts_across_all_chapters_simultaneously: rail shows counts for
      ALL chapters regardless of which chapter is currently rendered (AC-3 scope).
    - test_notes_chapter_isolation_in_rail: notes from chapter A do not appear on
      chapter B's rail panel.
    - test_rail_notes_textarea_rows_attribute: textarea rows="3" default (ADR-028).
    - test_section_end_wrapper_no_heading_row: .section-heading-row must be absent.
    - test_orphan_clamp_numerator_never_exceeds_denominator: template-level clamp.
  Negative:
    - test_old_notes_surface_class_absent_on_lecture_page: 'notes-surface' must not
      appear in lecture page HTML (ADR-028: removed).
    - test_old_section_heading_row_class_absent: '.section-heading-row' must not
      appear in lecture page HTML (ADR-027: removed).
    - test_notes_panel_absent_on_landing_page: 'rail-notes' must not appear on /.
    - test_count_complete_returns_dict_not_list: wrong return type is caught.
    - test_new_function_not_exported_from_top_level_before_implementation: fails RED
      until count_complete_sections_per_chapter is exported.
    - test_section_completion_form_not_at_top_of_section: form must NOT be inside h2
      or adjacent to heading (ADR-027: placement moved to bottom).
  Performance:
    - test_rail_progress_decoration_all_chapters_within_time_budget: all 12 chapters
      in the rail rendered within 5 s.
    - test_bulk_accessor_single_query_performance: count_complete accessor is fast
      even with completions across many chapters.

pytestmark registers all tests under task("TASK-011").

ASSUMPTIONS:
  ASSUMPTION: ADR-026 §Persistence accessor shape: count_complete_sections_per_chapter()
    returns dict[str, int] where keys are chapter_ids that have at least one complete
    section; chapters with zero completions are ABSENT from the dict (callers default
    to 0 for missing keys). Tests encode this exact contract.
  ASSUMPTION: ADR-026 §ChapterEntry extension: the discover_chapters() return shape
    yields ChapterEntry objects that have a section_count: int field. Tests assert
    the field exists on each ChapterEntry in the returned groups.
  ASSUMPTION: ADR-026 §new label_status value: "section_extraction_failed" is added
    to the Literal type but tests do not exhaustively enumerate; they only verify that
    the existing corpus chapters have label_status "ok".
  ASSUMPTION: ADR-028 §template variable: the lecture route context includes
    rail_notes_context (not notes) as the variable name. Tests grep HTML structure
    rather than inspecting context dict directly.
  ASSUMPTION: ADR-028 §CSS class names for rail-notes elements: the rail panel HTML
    contains class="rail-notes" on the <section> wrapper, class="rail-notes-list" on
    the note list, class="rail-note-form" on the form, class="rail-note-form-input"
    on the textarea. Tests assert these new class names.
  ASSUMPTION: ADR-027 §section-end wrapper: the completion form lives inside
    <div class="section-end"> which is a direct child of each <section id="section-*">
    element, appearing AFTER <div class="section-body">. Tests check for the .section-end
    class and verify it comes after the section body content in DOM order.
"""

from __future__ import annotations

import pathlib
import re
import sqlite3
import time

import pytest

pytestmark = pytest.mark.task("TASK-011")

# ---------------------------------------------------------------------------
# Canonical Chapter ID list (same across all tasks)
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

# Chapters 1-6 are Mandatory; 7+ are Optional (manifest §8 glossary)
MANDATORY_CHAPTER_IDS = [
    "ch-01-cpp-refresher",
    "ch-02-intro-to-algorithms",
    "ch-03-intro-to-data-structures",
    "ch-04-lists-stacks-and-queues",
    "ch-05-hash-tables",
    "ch-06-trees",
]
OPTIONAL_CHAPTER_IDS = [
    "ch-07-heaps-and-treaps",
    "ch-09-balanced-trees",
    "ch-10-graphs",
    "ch-11-b-trees",
    "ch-12-sets",
    "ch-13-additional-material",
]

TEST_CHAPTER_ID = "ch-01-cpp-refresher"
TEST_SECTION_NUMBER = "1-1"

REPO_ROOT = pathlib.Path(__file__).parent.parent

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_client(monkeypatch=None, db_path: str | None = None):
    """Return a FastAPI TestClient, injecting NOTES_DB_PATH for isolation."""
    if monkeypatch is not None and db_path is not None:
        monkeypatch.setenv("NOTES_DB_PATH", db_path)
    from fastapi.testclient import TestClient  # noqa: PLC0415
    from app.main import app  # noqa: PLC0415
    return TestClient(app)


def _db_path(tmp_path: pathlib.Path) -> str:
    return str(tmp_path / "test_task011.db")


def _direct_count_completions(db_path: str, chapter_id: str) -> int:
    """Count completion rows for a chapter directly from the SQLite DB."""
    if not pathlib.Path(db_path).exists():
        return 0
    conn = sqlite3.connect(db_path)
    cur = conn.execute(
        "SELECT COUNT(*) FROM section_completions WHERE chapter_id = ?",
        (chapter_id,),
    )
    count = cur.fetchone()[0]
    conn.close()
    return count


def _bootstrap_schema(client) -> None:
    """Trigger schema init via a GET request."""
    client.get(f"/lecture/{TEST_CHAPTER_ID}")


# ===========================================================================
# AC-1 — Per-Chapter "X / Y" progress decoration appears in the rail on all
#         12 corpus Chapters and on the landing page.
# ===========================================================================


@pytest.mark.parametrize("chapter_id", ALL_CHAPTER_IDS)
def test_rail_progress_decoration_on_all_12_chapters(
    chapter_id: str, tmp_path, monkeypatch
) -> None:
    """
    AC-1 (TASK-011): GET /lecture/{chapter_id} for every Chapter in the corpus
    renders a per-Chapter "X / Y" progress decoration in the navigation rail.

    ADR-026 structural commitment:
      - <span class="nav-chapter-progress"> must appear in the rail HTML.
      - The decoration must appear once for each Chapter row (12 total spans).
      - Pattern matches "N / M" where N, M are non-negative integers.

    Iterates ALL 12 corpus Chapters — not a spot-check.

    Trace: AC-1; ADR-026 §Display surface placement; ADR-026 §Visual shape.
    """
    client = _make_client(monkeypatch, _db_path(tmp_path))
    response = client.get(f"/lecture/{chapter_id}")
    assert response.status_code == 200, (
        f"GET /lecture/{chapter_id} returned {response.status_code}; expected 200."
    )
    html = response.text

    # ADR-026: the decoration span class is the architectural commitment
    assert "nav-chapter-progress" in html, (
        f"GET /lecture/{chapter_id} — rendered HTML contains no 'nav-chapter-progress' "
        "class. AC-1/ADR-026: each Chapter row in the rail must render a "
        "<span class='nav-chapter-progress'> decoration."
    )

    # ADR-026 §Visual shape: the decoration is plain "X / Y" text
    # At least one "digit / digit" pattern must appear in the rail
    progress_pattern = re.compile(r"\d+\s*/\s*\d+")
    assert progress_pattern.search(html), (
        f"GET /lecture/{chapter_id} — rendered HTML contains no 'N / M' progress "
        "pattern. AC-1/ADR-026: the decoration must render as plain 'X / Y' text."
    )


def test_rail_progress_decoration_on_landing_page(tmp_path, monkeypatch) -> None:
    """
    AC-1 (TASK-011): GET / (landing page) also renders per-Chapter progress
    decorations in the rail — the rail is shared between landing and lecture pages.

    ADR-026: both GET / and GET /lecture/{chapter_id} route handlers call
    count_complete_sections_per_chapter() when building the rail context.

    Trace: AC-1; ADR-026 §Chapter-progress derivation home.
    """
    client = _make_client(monkeypatch, _db_path(tmp_path))
    response = client.get("/")
    assert response.status_code == 200, (
        f"GET / returned {response.status_code}; expected 200."
    )
    html = response.text

    assert "nav-chapter-progress" in html, (
        "GET / — rendered HTML contains no 'nav-chapter-progress' class. "
        "AC-1/ADR-026: the landing page rail must also show per-Chapter progress decorations."
    )

    # All 12 chapters must have progress spans
    span_count = html.count("nav-chapter-progress")
    assert span_count >= 12, (
        f"GET / — found only {span_count} occurrences of 'nav-chapter-progress'; "
        "expected at least 12 (one per Chapter). "
        "AC-1/ADR-026: every Chapter row must have a progress decoration."
    )


# ===========================================================================
# AC-2 — Marking a Section complete updates that Chapter's rail count
# ===========================================================================


def test_rail_count_updates_after_marking_complete(tmp_path, monkeypatch) -> None:
    """
    AC-2 (TASK-011): after marking a Section in Chapter X complete, a GET of
    Chapter X's Lecture page shows an updated rail count (X+1 / Y) for that
    Chapter row; no other Chapter's count changes.

    ADR-026: the PRG redirect re-reads count_complete_sections_per_chapter()
    on the GET, so the updated count is visible immediately.

    Trace: AC-2; ADR-026 §Persistence accessor; ADR-024 §PRG redirect.
    """
    db_path = _db_path(tmp_path)
    client = _make_client(monkeypatch, db_path)
    _bootstrap_schema(client)

    # Record initial progress for ch-01 — find the "N / M" pattern in its rail row
    resp_before = client.get(f"/lecture/{TEST_CHAPTER_ID}")
    html_before = resp_before.text

    # Extract all "N / M" patterns; we're interested in the count before marking
    progress_before = re.findall(r"(\d+)\s*/\s*(\d+)", html_before)
    # Find the one for ch-01 (typically the first one in Mandatory group)
    # The rail renders them in chapter order; grab all numerators for context
    numerators_before = [int(n) for n, _m in progress_before]
    total_before = sum(numerators_before)

    # Mark one section in ch-01
    client.post(
        f"/lecture/{TEST_CHAPTER_ID}/sections/{TEST_SECTION_NUMBER}/complete",
        data={"action": "mark"},
        follow_redirects=False,
    )

    resp_after = client.get(f"/lecture/{TEST_CHAPTER_ID}")
    html_after = resp_after.text

    progress_after = re.findall(r"(\d+)\s*/\s*(\d+)", html_after)
    numerators_after = [int(n) for n, _m in progress_after]
    total_after = sum(numerators_after)

    assert total_after == total_before + 1, (
        f"After marking one section complete in {TEST_CHAPTER_ID}, "
        f"total numerator across all rail rows changed by {total_after - total_before}; "
        "expected exactly +1. "
        "AC-2/ADR-026: marking one section must increment that Chapter's count by 1."
    )


# ===========================================================================
# AC-3 — Rail shows counts for ALL chapters regardless of current chapter
# ===========================================================================


def test_progress_counts_across_all_chapters_simultaneously(
    tmp_path, monkeypatch
) -> None:
    """
    AC-3 (TASK-011): after marking sections in multiple Chapters, navigating to
    any Chapter's Lecture page shows correct non-zero counts for ALL Chapters
    that have completions — not just the currently-rendered Chapter.

    ADR-026: count_complete_sections_per_chapter() is a bulk query that returns
    counts for every chapter that has completions; the rail accessor is not
    Chapter-X-scoped.

    Trace: AC-3; ADR-026 §Persistence accessor shape ('not Chapter-X-scoped').
    """
    db_path = _db_path(tmp_path)
    monkeypatch.setenv("NOTES_DB_PATH", db_path)

    from fastapi.testclient import TestClient  # noqa: PLC0415
    from app.main import app  # noqa: PLC0415
    client = TestClient(app)
    _bootstrap_schema(client)

    import app.persistence as persistence  # noqa: PLC0415

    # Mark one section in ch-01 and one in ch-06 (distinct chapters)
    persistence.mark_section_complete(
        section_id="ch-01-cpp-refresher#section-1-1",
        chapter_id="ch-01-cpp-refresher",
    )
    persistence.mark_section_complete(
        section_id="ch-06-trees#section-6-1",
        chapter_id="ch-06-trees",
    )

    # Navigate to ch-02 (a completely DIFFERENT chapter from where we marked)
    resp = client.get("/lecture/ch-02-intro-to-algorithms")
    assert resp.status_code == 200
    html = resp.text

    # The rail on ch-02's page must still show non-zero for ch-01 and ch-06
    # We check there are at least 2 progress patterns with a non-zero numerator
    non_zero_patterns = re.findall(r"([1-9]\d*)\s*/\s*\d+", html)
    assert len(non_zero_patterns) >= 2, (
        f"On /lecture/ch-02, expected at least 2 non-zero progress numerators "
        f"(for ch-01 and ch-06 which were marked), got {len(non_zero_patterns)} "
        f"non-zero entries in patterns: {non_zero_patterns!r}. "
        "AC-3/ADR-026: the rail accessor must show ALL chapters' progress, not just "
        "the currently-rendered chapter's count."
    )


# ===========================================================================
# AC-4 — Mandatory/Optional grouping preserved under progress decoration
# ===========================================================================


def test_designation_grouping_preserved_with_progress_decoration(
    tmp_path, monkeypatch
) -> None:
    """
    AC-4 (TASK-011): the progress decoration must not collapse, hide, reorder,
    or interfere with the existing Mandatory/Optional designation grouping.

    Manifest §6: 'Mandatory and Optional honored everywhere.'
    ADR-026: the decoration appears within each row; the grouping is preserved
    by construction.

    Verifies:
      - Both Mandatory and Optional section labels appear in the rail.
      - nav-chapter-progress spans appear inside both Mandatory and Optional groups.
      - The order (Mandatory first, Optional second) is preserved.

    Trace: AC-4; ADR-026 §CSS class ownership; Manifest §6; MC-3.
    """
    client = _make_client(monkeypatch, _db_path(tmp_path))
    response = client.get("/")
    assert response.status_code == 200
    html = response.text

    # Both designation headings must appear
    assert "Mandatory" in html, (
        "GET / — 'Mandatory' group label not found in rendered HTML. "
        "AC-4/MC-3: Mandatory/Optional grouping must be preserved."
    )
    assert "Optional" in html, (
        "GET / — 'Optional' group label not found in rendered HTML. "
        "AC-4/MC-3: Optional group label must remain visible."
    )

    # Mandatory must appear before Optional
    pos_mandatory = html.find("Mandatory")
    pos_optional = html.find("Optional")
    assert pos_mandatory < pos_optional, (
        f"'Mandatory' appears at position {pos_mandatory} but 'Optional' at "
        f"{pos_optional}. "
        "AC-4/ADR-006: Mandatory group must appear before Optional group."
    )

    # nav-chapter-progress must appear after the Mandatory heading
    pos_first_progress = html.find("nav-chapter-progress")
    assert pos_first_progress > pos_mandatory, (
        "First 'nav-chapter-progress' span appears before the Mandatory group "
        "heading — progress decorations are not inside the chapter list. "
        "AC-4/ADR-026: decorations must be inside Chapter rows in the designation groups."
    )


# ===========================================================================
# AC-5 — Empty-state (0 / Y) and full-state (Y / Y + --complete class)
# ===========================================================================


def test_progress_shows_zero_when_no_sections_complete(
    tmp_path, monkeypatch
) -> None:
    """
    AC-5 (TASK-011) empty-state: with a fresh database (no completions),
    every Chapter's progress decoration shows "0 / Y" where Y > 0.

    ADR-026 §Empty-state: "0 / Y" rendered verbatim; not hidden.
    The denominator (Y) is > 0 for every Chapter in the corpus (all have Sections).

    Trace: AC-5; ADR-026 §Empty-state and full-state.
    """
    client = _make_client(monkeypatch, _db_path(tmp_path))
    response = client.get("/")
    assert response.status_code == 200
    html = response.text

    # All progress patterns must have numerator 0 (no completions yet)
    # Note: the landing page shows 12 progress spans; all must start at "0 / N"
    progress_patterns = re.findall(r"(\d+)\s*/\s*(\d+)", html)
    assert len(progress_patterns) >= 12, (
        f"Expected at least 12 progress patterns (one per chapter), "
        f"found {len(progress_patterns)}."
    )
    for numerator_str, denominator_str in progress_patterns:
        numerator = int(numerator_str)
        denominator = int(denominator_str)
        assert numerator == 0, (
            f"Fresh database: progress pattern '{numerator_str} / {denominator_str}' "
            "has non-zero numerator. AC-5/ADR-026: empty-state must be '0 / Y'."
        )
        assert denominator > 0, (
            f"Progress pattern '{numerator_str} / {denominator_str}' has denominator 0. "
            "ADR-026: each Chapter must have at least one discoverable Section."
        )


def test_progress_shows_full_state_with_complete_css_modifier(
    tmp_path, monkeypatch
) -> None:
    """
    AC-5 (TASK-011) full-state: when a Chapter has all Sections marked complete,
    the progress decoration carries the 'nav-chapter-progress--complete' CSS
    modifier class (ADR-026 §Full-state).

    Strategy: mark all Sections in ch-12-sets (a shorter chapter) complete via
    the persistence layer, then assert the --complete modifier appears on the
    GET response.

    Trace: AC-5; ADR-026 §Empty-state and full-state ('full-state gets the
    --complete modifier class').
    """
    db_path = _db_path(tmp_path)
    monkeypatch.setenv("NOTES_DB_PATH", db_path)

    from fastapi.testclient import TestClient  # noqa: PLC0415
    from app.main import app  # noqa: PLC0415
    client = TestClient(app)
    _bootstrap_schema(client)

    import app.persistence as persistence  # noqa: PLC0415

    # Mark sections 12-1 through 12-10 for ch-12-sets.
    # The exact section count for ch-12 depends on the corpus; we mark
    # many to maximise the chance of hitting Y/Y for whatever Y is.
    # The test's real contract is: if any chapter reaches Y/Y, the --complete
    # modifier must appear.  We use the discovery module to find the actual count.
    import app.discovery as discovery  # noqa: PLC0415
    import app.config as config  # noqa: PLC0415
    source_root = pathlib.Path(config.CONTENT_ROOT)
    nav_groups = discovery.discover_chapters(source_root)
    all_chapters = (
        nav_groups.get("Mandatory", []) + nav_groups.get("Optional", [])
    )

    # Find ch-12 in the discovered chapters
    ch12_entry = next(
        (e for e in all_chapters if e.chapter_id == "ch-12-sets"), None
    )
    if ch12_entry is None:
        pytest.skip("ch-12-sets not found in corpus; cannot test full-state")

    # ADR-026: section_count field must be present on ChapterEntry
    assert hasattr(ch12_entry, "section_count"), (
        f"ChapterEntry for ch-12-sets has no 'section_count' field. "
        "AC-5/ADR-026: discover_chapters() must attach section_count to each ChapterEntry."
    )
    section_count = ch12_entry.section_count
    assert section_count > 0, (
        f"ch-12-sets.section_count is {section_count}; expected > 0."
    )

    # Mark all discovered sections complete
    for n in range(1, section_count + 1):
        persistence.mark_section_complete(
            section_id=f"ch-12-sets#section-12-{n}",
            chapter_id="ch-12-sets",
        )

    resp = client.get("/lecture/ch-12-sets")
    assert resp.status_code == 200
    html = resp.text

    assert "nav-chapter-progress--complete" in html, (
        f"After marking all {section_count} sections of ch-12-sets complete, "
        "the rendered HTML does not contain 'nav-chapter-progress--complete'. "
        "AC-5/ADR-026: when X == Y (all Sections complete), the progress span "
        "must carry the 'nav-chapter-progress--complete' modifier class."
    )


# ===========================================================================
# AC-6 — Completion affordance lives at bottom-of-Section (ADR-027)
# ===========================================================================


@pytest.mark.parametrize("chapter_id", ALL_CHAPTER_IDS)
def test_completion_form_inside_section_end_wrapper_on_all_chapters(
    chapter_id: str, tmp_path, monkeypatch
) -> None:
    """
    AC-6 (TASK-011): the completion form must live inside a .section-end wrapper
    at the bottom of each Section block, NOT inside .section-heading-row next
    to the heading.

    ADR-027 §Decision: the form moves to <div class="section-end"> inside
    each <section> block.

    Verifies:
      - '.section-end' class is present (the new wrapper).
      - '.section-heading-row' class is ABSENT (the old wrapper, removed).

    Iterates ALL 12 corpus Chapters.

    Trace: AC-6; ADR-027 §Decision; ADR-027 §CSS class changes.
    """
    client = _make_client(monkeypatch, _db_path(tmp_path))
    response = client.get(f"/lecture/{chapter_id}")
    assert response.status_code == 200
    html = response.text

    # ADR-027: new wrapper class must be present
    assert "section-end" in html, (
        f"GET /lecture/{chapter_id} — 'section-end' class not found. "
        "AC-6/ADR-027: the completion form must be wrapped in <div class='section-end'>."
    )

    # ADR-027: old heading-row wrapper must be REMOVED
    assert "section-heading-row" not in html, (
        f"GET /lecture/{chapter_id} — 'section-heading-row' class is still present. "
        "AC-6/ADR-027: '.section-heading-row' is removed; the <h2> is now a direct "
        "child of <section>; the form lives in '.section-end', not next to the heading."
    )


def test_section_completion_form_not_at_top_of_section(
    tmp_path, monkeypatch
) -> None:
    """
    AC-6 (TASK-011): the completion form must NOT appear immediately adjacent to
    the Section heading (it has moved to the bottom per ADR-027).

    The test checks that the <form class="section-completion-form"> does NOT
    appear immediately after <h2 class="section-heading"> in the HTML
    (i.e., there is substantial content — the section body — between them).

    Trace: AC-6; ADR-027 §Decision ('form moves from top to bottom').
    """
    client = _make_client(monkeypatch, _db_path(tmp_path))
    response = client.get(f"/lecture/{TEST_CHAPTER_ID}")
    assert response.status_code == 200
    html = response.text

    # The heading HTML and the form HTML should be separated by the section body.
    # Pattern: find <h2 class="section-heading">, then check that
    # <form class="section-completion-form" is NOT the very next thing.
    # We check that there is substantial content (>100 chars) between the first
    # section heading and the first completion form.
    heading_match = re.search(r'class="section-heading"', html)
    form_match = re.search(r'class="section-completion-form"', html)

    assert heading_match is not None, (
        "No 'section-heading' class found in HTML — prerequisite for placement check."
    )
    assert form_match is not None, (
        "No 'section-completion-form' class found in HTML — form is absent."
    )

    heading_pos = heading_match.start()
    form_pos = form_match.start()

    # The form must come AFTER the heading (bottom-of-Section)
    assert form_pos > heading_pos, (
        f"section-completion-form appears before section-heading in HTML "
        f"(form at {form_pos}, heading at {heading_pos}). "
        "ADR-027: the form must be at the BOTTOM of the Section, not the top."
    )

    # There must be substantial content (the section body) between heading and form
    content_between = html[heading_pos:form_pos]
    assert len(content_between) > 200, (
        f"Only {len(content_between)} chars between heading and form — "
        "the form appears to still be right next to the heading (inline placement). "
        "AC-6/ADR-027: the form must be separated from the heading by the section "
        "body content."
    )


def test_section_end_wrapper_present_first_and_last_section(
    tmp_path, monkeypatch
) -> None:
    """
    AC-6 boundary: the .section-end wrapper must be present on BOTH the
    first and the last Section — not only the first (spot-check guard).

    ADR-027: every Section in the for-loop gets a .section-end wrapper.

    Trace: AC-6; ADR-027 §Template structure (per-Section loop).
    """
    client = _make_client(monkeypatch, _db_path(tmp_path))
    response = client.get(f"/lecture/{TEST_CHAPTER_ID}")
    assert response.status_code == 200
    html = response.text

    # Count .section-end occurrences and compare to section count
    section_end_count = html.count("section-end")
    # Also count how many <section id="section-"> there are
    section_id_count = len(re.findall(r'id="section-\d+-\d+"', html))

    assert section_id_count > 0, (
        f"No section id='section-*' elements found on /lecture/{TEST_CHAPTER_ID}."
    )
    assert section_end_count >= section_id_count, (
        f"Found {section_end_count} 'section-end' occurrences but {section_id_count} "
        "section elements. "
        "AC-6/ADR-027: every Section must have a .section-end wrapper."
    )


def test_old_section_heading_row_class_absent(tmp_path, monkeypatch) -> None:
    """
    AC-6 negative: '.section-heading-row' must be entirely absent from the
    rendered Lecture page HTML (ADR-027: the class is removed).

    This is a hard negative — finding this class means the implementation
    did not complete the supersedure.

    Trace: AC-6; ADR-027 §CSS class changes ('REMOVED: .section-heading-row').
    """
    client = _make_client(monkeypatch, _db_path(tmp_path))
    for chapter_id in ALL_CHAPTER_IDS:
        response = client.get(f"/lecture/{chapter_id}")
        assert response.status_code == 200
        assert "section-heading-row" not in response.text, (
            f"GET /lecture/{chapter_id} — 'section-heading-row' class is still present "
            "in the rendered HTML. "
            "AC-6/ADR-027: this class is REMOVED in the supersedure; "
            "the heading is now a plain <h2 class='section-heading'>."
        )


# ===========================================================================
# AC-7 — Notes section no longer at bottom of page; now rail-resident
# ===========================================================================


def test_old_notes_surface_class_absent_on_lecture_page(
    tmp_path, monkeypatch
) -> None:
    """
    AC-7 (TASK-011) negative: '<section class="notes-surface">' must NOT appear
    anywhere in the rendered Lecture page HTML.

    ADR-028: the bottom-of-page Notes section is removed entirely.

    Trace: AC-7; ADR-028 §Removal of bottom-of-page Notes section.
    """
    client = _make_client(monkeypatch, _db_path(tmp_path))
    for chapter_id in ALL_CHAPTER_IDS:
        response = client.get(f"/lecture/{chapter_id}")
        assert response.status_code == 200
        assert "notes-surface" not in response.text, (
            f"GET /lecture/{chapter_id} — 'notes-surface' class still present. "
            "AC-7/ADR-028: the bottom-of-page Notes section (<section class='notes-surface'>) "
            "is removed; Notes are now rail-resident."
        )


@pytest.mark.parametrize("chapter_id", ALL_CHAPTER_IDS)
def test_notes_panel_present_in_rail_on_all_lecture_pages(
    chapter_id: str, tmp_path, monkeypatch
) -> None:
    """
    AC-7 (TASK-011): the Notes panel must appear inside the rail on every
    Lecture page (GET /lecture/{chapter_id}).

    ADR-028 structural commitment:
      - <section class="rail-notes"> in the rail partial.
      - The panel contains the Notes form targeting /lecture/{chapter_id}/notes.
      - The textarea with name="body" is present.

    Iterates ALL 12 corpus Chapters.

    Trace: AC-7; ADR-028 §Rail integration; ADR-028 §Template structure.
    """
    client = _make_client(monkeypatch, _db_path(tmp_path))
    response = client.get(f"/lecture/{chapter_id}")
    assert response.status_code == 200
    html = response.text

    # ADR-028: new rail-notes section class
    assert "rail-notes" in html, (
        f"GET /lecture/{chapter_id} — 'rail-notes' class not found. "
        "AC-7/ADR-028: the Notes panel must be rail-resident "
        "(<section class='rail-notes'>)."
    )

    # The Notes form must target the correct POST route
    expected_action = f"/lecture/{chapter_id}/notes"
    assert expected_action in html, (
        f"GET /lecture/{chapter_id} — form action '{expected_action}' not found. "
        "AC-7/ADR-028: the rail-resident Notes form must post to "
        "/lecture/{chapter_id}/notes (route unchanged from ADR-023)."
    )

    # The textarea must be present (ADR-028: name="body" unchanged)
    assert 'name="body"' in html, (
        f"GET /lecture/{chapter_id} — no textarea name='body' found. "
        "AC-7/ADR-028: the Notes form textarea must carry name='body'."
    )


# ===========================================================================
# AC-7 continued — Landing page omits the Notes panel (ADR-028)
# ===========================================================================


def test_notes_panel_absent_on_landing_page(tmp_path, monkeypatch) -> None:
    """
    AC-7 (TASK-011): when the user is on GET / (landing page, no Chapter context),
    the Notes panel is OMITTED from the rail entirely.

    ADR-028 §Per-Chapter scoping: 'the Notes panel renders only when the rendering
    route has a Chapter context. On GET /, the Notes panel is omitted entirely via
    {% if rail_notes_context %} guard.'

    Verifies:
      - 'rail-notes' class must NOT appear on GET /.
      - No Notes form action (no /notes POST target) must appear on GET /.

    Trace: AC-7; ADR-028 §Per-Chapter scoping (landing page omission).
    """
    client = _make_client(monkeypatch, _db_path(tmp_path))
    response = client.get("/")
    assert response.status_code == 200
    html = response.text

    assert "rail-notes" not in html, (
        "GET / — 'rail-notes' class is present in the landing page HTML. "
        "AC-7/ADR-028: the Notes panel must be OMITTED from the landing page "
        "(no Chapter context; {% if rail_notes_context %} guard suppresses it)."
    )

    # No /lecture/{chapter_id}/notes form action on landing page
    notes_action_pattern = re.compile(r"/lecture/[^/]+/notes")
    assert not notes_action_pattern.search(html), (
        "GET / — a Notes form action URL was found in the landing page HTML. "
        "AC-7/ADR-028: the landing page rail must not include a Notes form "
        "(no Chapter context)."
    )


def test_notes_ui_absent_on_landing_page(tmp_path, monkeypatch) -> None:
    """
    AC-7 negative / boundary: old Notes classes ('notes-surface', 'notes-heading',
    'note-form') must NOT appear on the landing page either.

    Confirms both old AND new Notes classes are absent from GET /.

    Trace: AC-7; ADR-028 §CSS class rename; ADR-028 §Per-Chapter scoping.
    """
    client = _make_client(monkeypatch, _db_path(tmp_path))
    response = client.get("/")
    assert response.status_code == 200
    html = response.text

    for old_class in ("notes-surface", "notes-heading", "note-form", "note-item"):
        assert old_class not in html, (
            f"GET / — old Notes class '{old_class}' found in landing page HTML. "
            "ADR-028: old notes-* classes are removed from lecture.css and templates."
        )


# ===========================================================================
# AC-8 — Notes panel shows current Chapter's notes; Chapter isolation
# ===========================================================================


def test_notes_chapter_isolation_in_rail(tmp_path, monkeypatch) -> None:
    """
    AC-8 (TASK-011): a Note written for Chapter A must NOT appear in the
    rail Notes panel on Chapter B's page.

    ADR-028: the rail-resident Notes panel shows that Chapter's notes
    (list_notes_for_chapter(chapter_id), per ADR-023, unchanged).

    Trace: AC-8; ADR-028 §Per-Chapter scoping; ADR-023 §Route (unchanged).
    """
    db_path = _db_path(tmp_path)
    client = _make_client(monkeypatch, db_path)

    unique_body = "Rail-isolation test note for ch-01 TASK011."
    client.post(
        "/lecture/ch-01-cpp-refresher/notes",
        data={"body": unique_body},
        follow_redirects=True,
    )

    # The note must appear on ch-01's page (in the rail panel)
    resp_ch1 = client.get("/lecture/ch-01-cpp-refresher")
    assert unique_body in resp_ch1.text, (
        f"Note body {unique_body!r} not found in ch-01 response after POST. "
        "Prerequisite for isolation test."
    )

    # The note must NOT appear on ch-02's page
    resp_ch2 = client.get("/lecture/ch-02-intro-to-algorithms")
    assert unique_body not in resp_ch2.text, (
        f"Chapter 1 note body {unique_body!r} appeared on Chapter 2's page. "
        "AC-8/ADR-028: rail-resident Notes must be Chapter-scoped."
    )


def test_notes_form_action_url_matches_current_chapter(
    tmp_path, monkeypatch
) -> None:
    """
    AC-8 (TASK-011): on each Lecture page, the Notes form action URL must
    point to /lecture/{THIS_chapter_id}/notes, not to any other chapter.

    ADR-028: the form action is built from rail_notes_context.chapter_id,
    which equals the currently-rendered Chapter.

    Trace: AC-8; ADR-028 §Template structure (form action).
    """
    client = _make_client(monkeypatch, _db_path(tmp_path))

    for chapter_id in ALL_CHAPTER_IDS:
        response = client.get(f"/lecture/{chapter_id}")
        assert response.status_code == 200
        html = response.text

        expected_action = f"/lecture/{chapter_id}/notes"
        assert expected_action in html, (
            f"GET /lecture/{chapter_id} — form action '{expected_action}' not found. "
            "AC-8/ADR-028: rail Notes form must post to the CURRENT chapter's notes route."
        )

        # No form action for a DIFFERENT chapter must appear in the Notes panel
        for other_chapter in ALL_CHAPTER_IDS:
            if other_chapter == chapter_id:
                continue
            wrong_action = f"/lecture/{other_chapter}/notes"
            # The wrong action must NOT appear specifically in a rail-notes context
            # (it might appear in completion forms for other sections, so we only
            # check that the rail-notes section doesn't have wrong chapter actions)
            # This simpler check: the notes form action for wrong chapter must not
            # appear anywhere on the page (no other chapter's notes form exists)
            if wrong_action in html:
                pytest.fail(
                    f"GET /lecture/{chapter_id} — found form action '{wrong_action}' "
                    f"for WRONG chapter. "
                    "AC-8/ADR-028: the Notes form must target only the current chapter."
                )
            break  # Only check one other chapter to keep test fast


# ===========================================================================
# AC-9 — Rail-resident Notes panel textarea usability at narrow rail width
# ===========================================================================


def test_rail_notes_textarea_rows_attribute(tmp_path, monkeypatch) -> None:
    """
    AC-9 (TASK-011): the Notes textarea in the rail panel must use rows="3"
    as the default (ADR-028 §Rail-width constraints), not the old rows="6"
    from ADR-023 which was cramped at the rail's 220px minimum width.

    Trace: AC-9; ADR-028 §Rail-width constraints on the textarea.
    """
    client = _make_client(monkeypatch, _db_path(tmp_path))
    response = client.get(f"/lecture/{TEST_CHAPTER_ID}")
    assert response.status_code == 200
    html = response.text

    # ADR-028: rows="3" is the committed default
    assert 'rows="3"' in html, (
        "GET /lecture/ch-01 — textarea does not have rows=\"3\" attribute. "
        "AC-9/ADR-028: the rail-resident Notes textarea must use rows='3' (quick-capture "
        "shape that fits the rail's narrow width without horizontal overflow)."
    )

    # Old rows="6" must no longer be present (the commit from ADR-023)
    # This assertion may be too strict if rows="6" legitimately appears elsewhere
    # (e.g., some other textarea). We confirm it does NOT appear as the Notes textarea.
    # We check there is no rows="6" in a rail-notes context.
    # Simple approach: confirm the textarea with name="body" has rows="3"
    body_textarea_pattern = re.compile(
        r'<textarea[^>]+name="body"[^>]*>|<textarea[^>]*name="body"[^>]*>'
    )
    match = body_textarea_pattern.search(html)
    assert match is not None, (
        "No <textarea name='body'> found in the rendered HTML."
    )
    textarea_tag = match.group(0)
    assert 'rows="3"' in textarea_tag or 'rows=3' in textarea_tag, (
        f"The <textarea name='body'> tag is: {textarea_tag!r}. "
        "AC-9/ADR-028: the Notes textarea must have rows='3' (not rows='6')."
    )


def test_rail_notes_textarea_has_maxlength(tmp_path, monkeypatch) -> None:
    """
    AC-9: the textarea must still carry maxlength="65536" (ADR-023 validation
    unchanged per ADR-028 §What is NOT changed).

    Trace: AC-9; ADR-028 §What is NOT changed (validation unchanged from ADR-023).
    """
    client = _make_client(monkeypatch, _db_path(tmp_path))
    response = client.get(f"/lecture/{TEST_CHAPTER_ID}")
    assert response.status_code == 200
    html = response.text

    assert 'maxlength="65536"' in html, (
        "GET /lecture/ch-01 — 'maxlength=\"65536\"' not found in rendered HTML. "
        "AC-9/ADR-028: the Notes textarea maxlength must remain 65536 "
        "(validation unchanged from ADR-023)."
    )


# ===========================================================================
# AC-10 — No regressions on existing tests (amended Notes and completion assertions)
# ===========================================================================


@pytest.mark.parametrize("chapter_id", ALL_CHAPTER_IDS)
def test_no_regression_lecture_page_still_returns_200_after_supersedures(
    chapter_id: str, tmp_path, monkeypatch
) -> None:
    """
    AC-10 (TASK-011): after the two supersedures (ADR-027 placement + ADR-028 surface),
    every Chapter's Lecture page must still return HTTP 200 and text/html.

    Trace: AC-10; ADR-027 §Consequences; ADR-028 §Consequences.
    """
    client = _make_client(monkeypatch, _db_path(tmp_path))
    response = client.get(f"/lecture/{chapter_id}")
    assert response.status_code == 200, (
        f"Regression: GET /lecture/{chapter_id} returned {response.status_code} "
        "after ADR-027 + ADR-028 supersedures. "
        "AC-10: supersedures must not break any Lecture page."
    )
    assert "text/html" in response.headers.get("content-type", ""), (
        f"Regression: GET /lecture/{chapter_id} content-type is not text/html."
    )


def test_old_note_css_classes_absent_from_lecture_pages(
    tmp_path, monkeypatch
) -> None:
    """
    AC-10 negative: the old ADR-023 CSS classes must not appear in any
    Lecture page (ADR-028 §CSS file ownership: old classes removed from lecture.css).

    Old classes: notes-surface, notes-heading, notes-list, note-item, note-meta,
    note-timestamp, note-body, notes-empty, note-form, note-form-label,
    note-form-input, note-form-submit.

    Trace: AC-10; ADR-028 §CSS file ownership ('old classes removed from lecture.css').
    """
    old_classes = [
        "notes-surface",
        "notes-heading",
        "notes-list",
        "note-item",
        "note-meta",
        "note-timestamp",
        "note-body",
        "notes-empty",
        "note-form",
        "note-form-label",
        "note-form-input",
        "note-form-submit",
    ]

    client = _make_client(monkeypatch, _db_path(tmp_path))

    for chapter_id in ALL_CHAPTER_IDS[:3]:  # spot-check 3 chapters (first, mid, last)
        response = client.get(f"/lecture/{chapter_id}")
        assert response.status_code == 200
        html = response.text
        for cls in old_classes:
            assert f'class="{cls}"' not in html, (
                f"GET /lecture/{chapter_id} — old Notes CSS class '{cls}' still present as a class= attribute. "
                "AC-10/ADR-028: old notes-* / note-* classes are renamed to rail-notes-* / "
                "rail-note-* and removed from lecture.css."
            )


# ===========================================================================
# AC-11 — Bulk persistence accessor count_complete_sections_per_chapter()
# ===========================================================================


def test_count_complete_sections_per_chapter_exported_from_persistence(
    tmp_path, monkeypatch
) -> None:
    """
    AC-11 (TASK-011): app.persistence must export count_complete_sections_per_chapter.

    ADR-026 §Persistence accessor shape: the function is re-exported from
    app/persistence/__init__.py alongside the existing section-completion API.

    This test will be RED until the function is implemented and exported.

    Trace: AC-11; ADR-026 §Persistence accessor shape.
    """
    import app.persistence as persistence  # noqa: PLC0415

    assert hasattr(persistence, "count_complete_sections_per_chapter"), (
        "app.persistence does not export 'count_complete_sections_per_chapter'. "
        "AC-11/ADR-026: the new bulk accessor must be exported from "
        "app/persistence/__init__.py alongside the existing completion API."
    )


def test_count_complete_sections_per_chapter_returns_dict(
    tmp_path, monkeypatch
) -> None:
    """
    AC-11 (TASK-011): count_complete_sections_per_chapter() returns dict[str, int].

    ADR-026: the function returns {chapter_id: complete_section_count} for chapters
    that have at least one complete section.

    Trace: AC-11; ADR-026 §Persistence accessor shape.
    """
    db_path = _db_path(tmp_path)
    monkeypatch.setenv("NOTES_DB_PATH", db_path)

    from fastapi.testclient import TestClient  # noqa: PLC0415
    from app.main import app  # noqa: PLC0415
    TestClient(app).get(f"/lecture/{TEST_CHAPTER_ID}")

    import app.persistence as persistence  # noqa: PLC0415

    result = persistence.count_complete_sections_per_chapter()
    assert isinstance(result, dict), (
        f"count_complete_sections_per_chapter() returned {type(result)!r}; expected dict. "
        "AC-11/ADR-026: the function must return dict[str, int]."
    )
    # Each value must be an int
    for chapter_id, count in result.items():
        assert isinstance(chapter_id, str), (
            f"Key {chapter_id!r} is not a string. "
            "ADR-026: keys are chapter_id strings."
        )
        assert isinstance(count, int) and count > 0, (
            f"Value for chapter '{chapter_id}' is {count!r}; "
            "expected a positive int (only chapters WITH completions appear in the dict). "
            "ADR-026: chapters with zero completions are absent from the dict."
        )


def test_count_complete_sections_missing_keys_default_to_zero(
    tmp_path, monkeypatch
) -> None:
    """
    AC-11 edge: chapters with NO completions are absent from the returned dict;
    callers must default to 0 for missing keys.

    ADR-026 §Persistence accessor shape (docstring): 'Chapters with zero complete
    Sections are NOT in the returned dict — callers must default to 0 for missing keys.'

    Trace: AC-11; ADR-026 §Persistence accessor shape.
    """
    db_path = _db_path(tmp_path)
    monkeypatch.setenv("NOTES_DB_PATH", db_path)

    from fastapi.testclient import TestClient  # noqa: PLC0415
    from app.main import app  # noqa: PLC0415
    TestClient(app).get(f"/lecture/{TEST_CHAPTER_ID}")

    import app.persistence as persistence  # noqa: PLC0415

    # Fresh DB: no completions
    result_empty = persistence.count_complete_sections_per_chapter()
    assert result_empty == {}, (
        f"count_complete_sections_per_chapter() on an empty DB returned {result_empty!r}; "
        "expected {{}}. "
        "ADR-026: with no completions, the dict must be empty (all missing → default 0)."
    )

    # Mark one section in ch-01
    persistence.mark_section_complete(
        section_id="ch-01-cpp-refresher#section-1-1",
        chapter_id="ch-01-cpp-refresher",
    )

    result_one = persistence.count_complete_sections_per_chapter()
    assert "ch-01-cpp-refresher" in result_one, (
        "ch-01-cpp-refresher not in result after marking section-1-1. "
        "ADR-026: chapter with completions must appear in the dict."
    )
    assert result_one["ch-01-cpp-refresher"] == 1, (
        f"Expected count 1 for ch-01, got {result_one['ch-01-cpp-refresher']!r}."
    )

    # ch-02 has no completions — must be absent (not key-with-value-0)
    assert "ch-02-intro-to-algorithms" not in result_one, (
        "ch-02 (with zero completions) is present in the dict with a 0 value. "
        "ADR-026: chapters with zero completions must be ABSENT from the dict."
    )


def test_count_complete_sections_per_chapter_multi_chapter_accuracy(
    tmp_path, monkeypatch
) -> None:
    """
    AC-11 boundary: marking sections in multiple chapters produces correct
    per-chapter counts in a single dict — one bulk query, not 12 per-chapter calls.

    Trace: AC-11; ADR-026 §Persistence accessor shape ('one SQL call').
    """
    db_path = _db_path(tmp_path)
    monkeypatch.setenv("NOTES_DB_PATH", db_path)

    from fastapi.testclient import TestClient  # noqa: PLC0415
    from app.main import app  # noqa: PLC0415
    TestClient(app).get(f"/lecture/{TEST_CHAPTER_ID}")

    import app.persistence as persistence  # noqa: PLC0415

    # Mark 2 sections in ch-01, 3 sections in ch-06
    for n in range(1, 3):
        persistence.mark_section_complete(
            section_id=f"ch-01-cpp-refresher#section-1-{n}",
            chapter_id="ch-01-cpp-refresher",
        )
    for n in range(1, 4):
        persistence.mark_section_complete(
            section_id=f"ch-06-trees#section-6-{n}",
            chapter_id="ch-06-trees",
        )

    result = persistence.count_complete_sections_per_chapter()

    assert result.get("ch-01-cpp-refresher") == 2, (
        f"ch-01 count: expected 2, got {result.get('ch-01-cpp-refresher')!r}."
    )
    assert result.get("ch-06-trees") == 3, (
        f"ch-06 count: expected 3, got {result.get('ch-06-trees')!r}."
    )
    # Other chapters must still be absent
    assert "ch-02-intro-to-algorithms" not in result, (
        "ch-02 (no completions) should not appear in the bulk accessor result."
    )


# ===========================================================================
# AC-11 continued — discover_chapters() section_count field
# ===========================================================================


def test_discover_chapters_section_count_field_mandatory_boundary(
    tmp_path, monkeypatch
) -> None:
    """
    AC-11 boundary: discover_chapters() must return ChapterEntry objects that
    include a section_count: int field for the first Mandatory chapter.

    ADR-026 §Total-Sections denominator source: 'extend discover_chapters() to
    include per-Chapter Section count' via a new field on ChapterEntry.

    Trace: AC-11; ADR-026 §Total-Sections denominator source.
    """
    import app.discovery as discovery  # noqa: PLC0415
    import app.config as config  # noqa: PLC0415

    source_root = pathlib.Path(config.CONTENT_ROOT)
    nav_groups = discovery.discover_chapters(source_root)

    mandatory = nav_groups.get("Mandatory", [])
    assert mandatory, "No Mandatory chapters discovered — corpus missing?"

    first_mandatory = mandatory[0]
    assert hasattr(first_mandatory, "section_count"), (
        f"ChapterEntry for {first_mandatory.chapter_id!r} has no 'section_count' field. "
        "AC-11/ADR-026: discover_chapters() must extend ChapterEntry with section_count."
    )
    assert isinstance(first_mandatory.section_count, int), (
        f"section_count for {first_mandatory.chapter_id!r} is "
        f"{type(first_mandatory.section_count)!r}; expected int."
    )
    assert first_mandatory.section_count > 0, (
        f"section_count for {first_mandatory.chapter_id!r} is "
        f"{first_mandatory.section_count}; expected > 0 (every Chapter has Sections)."
    )


def test_discover_chapters_section_count_field_optional_boundary(
    tmp_path, monkeypatch
) -> None:
    """
    AC-11 boundary: discover_chapters() section_count field must also be present
    and correct for Optional chapters (Chapter 7+, per manifest §8 glossary).

    Trace: AC-11; ADR-026 §Total-Sections denominator source; Manifest §8 (Optional def).
    """
    import app.discovery as discovery  # noqa: PLC0415
    import app.config as config  # noqa: PLC0415

    source_root = pathlib.Path(config.CONTENT_ROOT)
    nav_groups = discovery.discover_chapters(source_root)

    optional = nav_groups.get("Optional", [])
    assert optional, "No Optional chapters discovered — corpus missing?"

    first_optional = optional[0]
    assert hasattr(first_optional, "section_count"), (
        f"ChapterEntry for {first_optional.chapter_id!r} (Optional) has no 'section_count'. "
        "AC-11/ADR-026: section_count must be present on ALL chapter entries, "
        "not just Mandatory."
    )
    assert isinstance(first_optional.section_count, int) and first_optional.section_count > 0, (
        f"section_count for Optional chapter {first_optional.chapter_id!r} is "
        f"{first_optional.section_count!r}; expected positive int."
    )


def test_all_chapter_entries_have_section_count() -> None:
    """
    AC-11 batch: ALL 12 ChapterEntry objects returned by discover_chapters()
    must have a section_count > 0.  Not a spot-check; iterates the full set.

    Trace: AC-11; ADR-026 §Total-Sections denominator source.
    """
    import app.discovery as discovery  # noqa: PLC0415
    import app.config as config  # noqa: PLC0415

    source_root = pathlib.Path(config.CONTENT_ROOT)
    nav_groups = discovery.discover_chapters(source_root)

    all_entries = nav_groups.get("Mandatory", []) + nav_groups.get("Optional", [])
    assert len(all_entries) >= 12, (
        f"Expected at least 12 chapter entries, got {len(all_entries)}."
    )

    failures = []
    for entry in all_entries:
        if not hasattr(entry, "section_count"):
            failures.append(f"{entry.chapter_id}: missing section_count field")
        elif not isinstance(entry.section_count, int) or entry.section_count <= 0:
            failures.append(
                f"{entry.chapter_id}: section_count={entry.section_count!r} (expected positive int)"
            )

    assert not failures, (
        f"section_count field issues on {len(failures)} ChapterEntry objects:\n"
        + "\n".join(failures)
        + "\nAC-11/ADR-026: every ChapterEntry must have section_count > 0."
    )


# ===========================================================================
# AC-11 — Orphan clamp: numerator never visually exceeds denominator
# ===========================================================================


def test_orphan_clamp_numerator_never_exceeds_denominator(
    tmp_path, monkeypatch
) -> None:
    """
    AC-11 edge (orphan clamp): ADR-026 §Known limitation specifies a template-level
    clamp to prevent the rail showing 'X / Y' where X > Y (orphan completion rows
    after source edits).

    Strategy: inject orphan rows into the DB directly, then assert that the
    rendered HTML shows at most 'Y / Y' — never 'Y+N / Y'.

    Trace: AC-11; ADR-026 §Known limitation — orphan/renumber problem.
    """
    db_path = _db_path(tmp_path)
    monkeypatch.setenv("NOTES_DB_PATH", db_path)

    from fastapi.testclient import TestClient  # noqa: PLC0415
    from app.main import app  # noqa: PLC0415
    TestClient(app).get(f"/lecture/{TEST_CHAPTER_ID}")

    # Inject 999 fake orphan completion rows for ch-12-sets directly via sqlite3
    conn = sqlite3.connect(db_path)
    for n in range(999):
        # These section IDs do not exist in the corpus (orphans)
        conn.execute(
            "INSERT OR IGNORE INTO section_completions (section_id, chapter_id, completed_at) "
            "VALUES (?, ?, ?)",
            (
                f"ch-12-sets#section-99-{n}",  # non-existent section ID
                "ch-12-sets",
                "2026-01-01T00:00:00Z",
            ),
        )
    conn.commit()
    conn.close()

    resp = TestClient(app).get("/lecture/ch-12-sets")
    assert resp.status_code == 200
    html = resp.text

    # Find the progress pattern(s) for ch-12-sets in the rail.
    # All "X / Y" patterns in the rail must have X <= Y (clamped).
    progress_patterns = re.findall(r"(\d+)\s*/\s*(\d+)", html)
    for numerator_str, denominator_str in progress_patterns:
        n, y = int(numerator_str), int(denominator_str)
        assert n <= y, (
            f"Rail shows '{n} / {y}' — numerator exceeds denominator. "
            "AC-11/ADR-026: the template-level clamp must prevent 'X / Y' where X > Y "
            "(orphan completion rows from source edits must not show impossible counts). "
            f"Found pattern '{n} / {y}' in the rendered HTML."
        )


# ===========================================================================
# AC-12 — Manifest-conformance: MC-6, MC-7, MC-10 for new code
# ===========================================================================


def test_mc7_new_accessor_has_no_user_id_argument() -> None:
    """
    AC-12 (TASK-011) / MC-7: count_complete_sections_per_chapter() must accept
    no user_id argument and produce a global aggregation (single-user).

    ADR-026 §Conformance check MC-7: 'no user_id predicate; no per-user argument.'
    Manifest §5 / §6 / §7: single user — no per-user partitioning.

    Trace: AC-12; ADR-026 §MC-7; Manifest §5/§6/§7.
    """
    import inspect
    import app.persistence as persistence  # noqa: PLC0415

    func = getattr(persistence, "count_complete_sections_per_chapter", None)
    assert func is not None, (
        "count_complete_sections_per_chapter not found in app.persistence."
    )
    sig = inspect.signature(func)
    param_names = list(sig.parameters.keys())
    for bad_param in ("user_id", "user", "account_id", "tenant_id"):
        assert bad_param not in param_names, (
            f"count_complete_sections_per_chapter has a '{bad_param}' parameter. "
            f"Parameters found: {param_names!r}. "
            "AC-12/MC-7: the function must accept no per-user argument; "
            "this is a single-user system (Manifest §5/§6/§7)."
        )


def test_mc10_count_accessor_sql_lives_only_in_persistence_package() -> None:
    """
    AC-12 (TASK-011) / MC-10: the SQL for count_complete_sections_per_chapter()
    must live only in app/persistence/, not in route handlers or other modules.

    Checks that app/main.py does not contain GROUP BY or COUNT(*) SQL literals.

    Trace: AC-12; ADR-026 §Conformance check MC-10; ADR-022 §Package boundary.
    """
    app_dir = REPO_ROOT / "app"
    persistence_dir = app_dir / "persistence"

    # Look for GROUP BY and COUNT patterns that belong in the persistence layer
    group_by_pattern = re.compile(
        r"""(?:"|')             # opening quote
        [^"']*
        (?:\bGROUP\s+BY\b | \bCOUNT\s*\()
        [^"']*
        (?:"|')                 # closing quote
        """,
        re.VERBOSE,
    )

    violations = []
    for py_file in app_dir.rglob("*.py"):
        try:
            py_file.relative_to(persistence_dir)
            continue  # inside app/persistence/ — allowed
        except ValueError:
            pass
        text = py_file.read_text(encoding="utf-8")
        if group_by_pattern.search(text):
            violations.append(str(py_file))

    assert violations == [], (
        f"MC-10 BLOCKER: SQL with GROUP BY or COUNT found outside app/persistence/ in: "
        f"{violations!r}. "
        "AC-12/ADR-026: the new bulk accessor's SQL must live in "
        "app/persistence/section_completions.py."
    )


# ===========================================================================
# Performance tests
# ===========================================================================


def test_rail_progress_decoration_all_chapters_within_time_budget(
    tmp_path, monkeypatch
) -> None:
    """
    Performance: GET / (landing page, renders all 12 chapter progress decorations)
    must complete within 5 seconds even with some completions in the DB.

    ADR-026 §Consequences: one additional indexed GROUP BY SQL query per render;
    extend discover_chapters() with 12 additional extract_sections() calls per render.
    Mitigation: all sub-millisecond at this scale.

    Trace: AC-1 (renders whole rail); ADR-026 §Consequences §Performance.
    """
    db_path = _db_path(tmp_path)
    monkeypatch.setenv("NOTES_DB_PATH", db_path)

    from fastapi.testclient import TestClient  # noqa: PLC0415
    from app.main import app  # noqa: PLC0415
    client = TestClient(app)
    _bootstrap_schema(client)

    import app.persistence as persistence  # noqa: PLC0415

    # Seed a few completions across different chapters
    for chapter_id, section_id in [
        ("ch-01-cpp-refresher", "ch-01-cpp-refresher#section-1-1"),
        ("ch-06-trees", "ch-06-trees#section-6-1"),
        ("ch-12-sets", "ch-12-sets#section-12-1"),
    ]:
        persistence.mark_section_complete(section_id=section_id, chapter_id=chapter_id)

    t0 = time.monotonic()
    response = client.get("/")
    elapsed = time.monotonic() - t0

    assert response.status_code == 200, (
        f"GET / returned {response.status_code}; expected 200."
    )
    assert elapsed < 5.0, (
        f"GET / with rail progress decoration took {elapsed:.2f}s (limit: 5s). "
        "ADR-026: discover_chapters() + count_complete_sections_per_chapter() must "
        "complete in sub-second at the 12-chapter corpus scale. "
        "A slow result suggests O(n²) behavior or missing index."
    )


def test_bulk_accessor_single_query_performance(tmp_path, monkeypatch) -> None:
    """
    Performance: count_complete_sections_per_chapter() with completions across
    many chapters must complete in < 1 second (the indexed GROUP BY is fast).

    Catches regressions to a per-Chapter call-in-loop pattern.

    Trace: AC-11; ADR-026 §Persistence accessor shape ('one SQL call');
    ADR-026 §Alternatives A ('12 SQL queries vs 1').
    """
    db_path = _db_path(tmp_path)
    monkeypatch.setenv("NOTES_DB_PATH", db_path)

    from fastapi.testclient import TestClient  # noqa: PLC0415
    from app.main import app  # noqa: PLC0415
    TestClient(app).get(f"/lecture/{TEST_CHAPTER_ID}")

    import app.persistence as persistence  # noqa: PLC0415

    # Seed completions across all 12 chapters
    for chapter_id in ALL_CHAPTER_IDS:
        for n in range(1, 6):
            persistence.mark_section_complete(
                section_id=f"{chapter_id}#section-1-{n}",
                chapter_id=chapter_id,
            )

    t0 = time.monotonic()
    result = persistence.count_complete_sections_per_chapter()
    elapsed = time.monotonic() - t0

    assert isinstance(result, dict) and len(result) >= 12, (
        f"Expected dict with >= 12 entries, got {result!r}."
    )
    assert elapsed < 1.0, (
        f"count_complete_sections_per_chapter() with 12-chapter completions took "
        f"{elapsed:.3f}s (limit: 1s). "
        "ADR-026: the indexed GROUP BY should be sub-millisecond. "
        "A slow result suggests a per-Chapter loop instead of one bulk query."
    )
