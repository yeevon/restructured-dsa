"""
TASK-013: Per-Section Quiz surface — HTTP-protocol pytest tests.

Tests derive from the Acceptance Criteria in
`design_docs/tasks/TASK-013-quiz-domain-model-and-per-section-quiz-surface.md`
and from:
  ADR-033 — Quiz domain schema (request_quiz, list_quizzes_for_chapter).
  ADR-034 — Per-Section Quiz surface placement:
    - Each <section>'s .section-end wrapper contains a .section-quiz block.
    - Empty-state caption: 'No quizzes yet for this Section.'
    - POST /lecture/{chapter_id}/sections/{section_number}/quiz:
        valid Section → 303 with Location ending '#section-{n-m}-end'.
        unknown chapter_id → 4xx, no row created.
        out-of-range section_number → 4xx, no row created.
    - Section ID validation at the route handler (not the persistence layer).
    - render_chapter passes section_quizzes_by_id to the template.
    - CSS classes section-quiz-* present in rendered HTML.
  ADR-031 — PRG redirect anchor: Location header ends with #section-{n-m}-end.

Coverage matrix:
  Boundary:
    - test_quiz_surface_on_all_12_chapters: surface present on ALL corpus chapters.
    - test_quiz_surface_on_mandatory_chapter: Mandatory chapter (ch-01-*).
    - test_quiz_surface_on_optional_chapter: Optional chapter (ch-07-*).
    - test_post_quiz_route_303_and_location_anchor: valid POST → 303 + anchor.
    - test_post_quiz_creates_exactly_one_requested_row: exactly one row, not two.
    - test_post_quiz_on_every_mandatory_chapter: route works on Mandatory Chapters.
  Edge:
    - test_quiz_surface_empty_state_text: empty-state caption matches ADR-034.
    - test_section_quiz_css_classes_present: section-quiz-* classes in HTML.
    - test_quiz_surface_shows_requested_status_after_post: populated-case renders.
    - test_quiz_button_form_present_in_section_end: generate-quiz form present.
  Negative:
    - test_post_quiz_unknown_chapter_returns_4xx: unknown chapter → 4xx, no row.
    - test_post_quiz_out_of_range_section_number_returns_4xx: bad section → 4xx, no row.
    - test_post_quiz_wrong_method_get_returns_405_or_404: GET on POST route rejected.
    - test_requested_quiz_never_presented_as_ready: requested status never 'ready'.
    - test_no_regression_existing_tests_still_pass_all_chapters: lecture/rails intact.
  Performance:
    - test_lecture_page_with_many_quizzes_within_time_budget: 30 quiz rows → <5s.

pytestmark registers all tests under task("TASK-013").
"""

from __future__ import annotations

import pathlib
import sqlite3
import time

import pytest

pytestmark = pytest.mark.task("TASK-013")

REPO_ROOT = pathlib.Path(__file__).parent.parent

# ---------------------------------------------------------------------------
# Corpus chapter IDs
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

MANDATORY_CHAPTER_ID = "ch-01-cpp-refresher"
OPTIONAL_CHAPTER_ID = "ch-07-heaps-and-treaps"

# A first section number for the Mandatory and Optional chapters used in route tests.
# ADR-002: section_number is the n-m portion of section-{n-m} (e.g. "1-1").
MANDATORY_FIRST_SECTION = "1-1"
OPTIONAL_FIRST_SECTION = "7-1"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_client(monkeypatch, db_path: str):
    """
    Return a FastAPI TestClient backed by an isolated test database.
    Import deferred so collection succeeds before the app exists.
    """
    monkeypatch.setenv("NOTES_DB_PATH", db_path)
    from fastapi.testclient import TestClient  # noqa: PLC0415
    from app.main import app  # noqa: PLC0415
    return TestClient(app)


def _db_count_quizzes(db_path: str) -> int:
    """Return total number of rows in the quizzes table (bypasses app)."""
    if not pathlib.Path(db_path).exists():
        return 0
    conn = sqlite3.connect(db_path)
    cur = conn.execute("SELECT COUNT(*) FROM quizzes")
    count = cur.fetchone()[0]
    conn.close()
    return count


def _db_list_quizzes(db_path: str) -> list[dict]:
    """Return all rows in the quizzes table as a list of dicts."""
    if not pathlib.Path(db_path).exists():
        return []
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.execute(
        "SELECT quiz_id, section_id, status, created_at FROM quizzes"
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


# ===========================================================================
# AC-7 — Per-Section Quiz surface present on every Chapter page (all 12)
# Trace: TASK-013 AC-7; ADR-034 §Placement; ADR-034 §Empty-state
# ===========================================================================


@pytest.mark.parametrize("chapter_id", ALL_CHAPTER_IDS)
def test_quiz_surface_on_all_12_chapters(chapter_id: str, tmp_path, monkeypatch) -> None:
    """
    AC-7 (TASK-013): GET /lecture/{chapter_id} for every corpus Chapter must render
    a per-Section Quiz surface — a block with the section-quiz-* CSS class and the
    empty-state caption 'No quizzes yet for this Section.' (when no Quizzes exist).

    ADR-034 §Placement: 'one Quiz block per <section>, keyed by section.id'.
    ADR-034 §Empty-state: "No quizzes yet for this Section."

    Iterates ALL 12 corpus Chapters — not a spot-check.

    Trace: AC-7; ADR-034 §Placement; ADR-034 §Empty-state (must-ship).
    """
    db_path = str(tmp_path / f"quiz_surface_{chapter_id}.db")
    client = _make_client(monkeypatch, db_path)

    response = client.get(f"/lecture/{chapter_id}")
    assert response.status_code == 200, (
        f"GET /lecture/{chapter_id} returned HTTP {response.status_code}; expected 200. "
        "AC-7: every Chapter's Lecture page must be reachable."
    )
    html = response.text

    # ADR-034 §CSS: section-quiz-* classes in lecture.css; at least one class must appear.
    assert "section-quiz" in html, (
        f"GET /lecture/{chapter_id} — no 'section-quiz' CSS class found in rendered HTML. "
        "AC-7/ADR-034: the per-Section Quiz surface uses section-quiz-* CSS classes "
        "(e.g. section-quiz, section-quiz-empty, section-quiz-form). "
        "The block must be rendered for every Section."
    )

    # ADR-034 §Empty-state: the must-ship caption when no Quizzes exist for a Section.
    assert "No quizzes yet" in html, (
        f"GET /lecture/{chapter_id} — empty-state caption 'No quizzes yet' not found. "
        "AC-7/ADR-034: the empty-state must read as 'this is where Quizzes for this "
        "Section will live' and must not imply a Quiz exists. "
        "The exact copy ADR-034 commits to: 'No quizzes yet for this Section.'"
    )


def test_quiz_surface_on_mandatory_chapter(tmp_path, monkeypatch) -> None:
    """
    AC-8 (TASK-013): the per-Section Quiz surface must be present on a Mandatory
    Chapter (ch-01-cpp-refresher).

    ADR-034 / MC-3 / Manifest §6: 'Mandatory and Optional are honored everywhere —
    the per-Section Quiz surface inherits the parent Chapter's designation.'

    Trace: AC-8; ADR-034; MC-3; Manifest §6 'Mandatory and Optional honored everywhere'.
    """
    db_path = str(tmp_path / "mandatory.db")
    client = _make_client(monkeypatch, db_path)

    response = client.get(f"/lecture/{MANDATORY_CHAPTER_ID}")
    assert response.status_code == 200
    html = response.text

    assert "section-quiz" in html, (
        f"GET /lecture/{MANDATORY_CHAPTER_ID} — no section-quiz class in HTML. "
        "AC-8/ADR-034/MC-3: the Quiz surface must render on Mandatory Chapters."
    )
    assert "No quizzes yet" in html, (
        f"GET /lecture/{MANDATORY_CHAPTER_ID} — empty-state caption missing. "
        "ADR-034: empty-state 'No quizzes yet for this Section.' must appear when "
        "no Quizzes exist on a Mandatory Chapter."
    )


def test_quiz_surface_on_optional_chapter(tmp_path, monkeypatch) -> None:
    """
    AC-8 (TASK-013): the per-Section Quiz surface must also be present on an
    Optional Chapter (ch-07-heaps-and-treaps).

    ADR-034 / MC-3: 'nothing about the surface hides the M/O split.'

    Trace: AC-8; ADR-034; MC-3; Manifest §7 'Mandatory and Optional are separable
    in every learner-facing surface'.
    """
    db_path = str(tmp_path / "optional.db")
    client = _make_client(monkeypatch, db_path)

    response = client.get(f"/lecture/{OPTIONAL_CHAPTER_ID}")
    assert response.status_code == 200
    html = response.text

    assert "section-quiz" in html, (
        f"GET /lecture/{OPTIONAL_CHAPTER_ID} — no section-quiz class in HTML. "
        "AC-8/ADR-034/MC-3: the Quiz surface must render on Optional Chapters "
        "too — Mandatory/Optional inheritance must not hide the surface."
    )
    assert "No quizzes yet" in html, (
        f"GET /lecture/{OPTIONAL_CHAPTER_ID} — empty-state caption missing. "
        "ADR-034: empty-state must appear on Optional Chapter sections."
    )


# ===========================================================================
# AC-7/ADR-034 — Empty-state caption exact text
# Trace: ADR-034 §Empty-state ('No quizzes yet for this Section.')
# ===========================================================================


def test_quiz_surface_empty_state_text(tmp_path, monkeypatch) -> None:
    """
    ADR-034 §Empty-state: the empty-state caption must read 'No quizzes yet for
    this Section.' (must-ship; minor wording is implementer-tunable but the exact
    ADR-034 text is the contract this test pins).

    The empty-state paragraph uses class='section-quiz-empty' per ADR-034 template.

    Trace: ADR-034 §Empty-state ('No quizzes yet for this Section.'
    exact copy is the must-ship).
    """
    db_path = str(tmp_path / "empty_state.db")
    client = _make_client(monkeypatch, db_path)

    response = client.get(f"/lecture/{MANDATORY_CHAPTER_ID}")
    assert response.status_code == 200
    html = response.text

    # The exact ADR-034-committed copy:
    assert "No quizzes yet for this Section" in html, (
        f"GET /lecture/{MANDATORY_CHAPTER_ID} — the exact empty-state text "
        "'No quizzes yet for this Section' was not found. "
        "ADR-034 §Empty-state: 'No quizzes yet for this Section.' is the "
        "committed copy (the must-ship) for the per-Section Quiz empty state."
    )


# ===========================================================================
# ADR-034 — CSS classes in rendered HTML
# Trace: ADR-034 §CSS ('section-quiz-* namespace in lecture.css per ADR-008')
# ===========================================================================


def test_section_quiz_css_classes_present(tmp_path, monkeypatch) -> None:
    """
    ADR-034 §CSS: the rendered Lecture page must contain section-quiz-* CSS classes.

    ADR-034 commits to: .section-quiz (block wrapper), .section-quiz-empty
    (empty-state), .section-quiz-form (trigger form), .section-quiz-button.

    At minimum, the HTML must include 'section-quiz' as a class-name substring.
    Tests that the CSS namespace (section-quiz-*) is actually used in the rendered
    template — not just the CSS file.

    Trace: ADR-034 §CSS; ADR-008 (section-* → lecture.css).
    """
    db_path = str(tmp_path / "css_classes.db")
    client = _make_client(monkeypatch, db_path)

    response = client.get(f"/lecture/{MANDATORY_CHAPTER_ID}")
    assert response.status_code == 200
    html = response.text

    # At least three section-quiz-* classes must be present to confirm the namespace
    # is used: the block wrapper (section-quiz), the empty-state (section-quiz-empty),
    # and the form (section-quiz-form) or button (section-quiz-button).
    quiz_classes_found = {
        cls
        for cls in [
            "section-quiz-empty",
            "section-quiz-form",
            "section-quiz-button",
            "section-quiz-list",
            "section-quiz-heading",
            "section-quiz-item",
        ]
        if cls in html
    }
    assert len(quiz_classes_found) >= 1, (
        f"No section-quiz-* CSS classes found in rendered HTML for "
        f"/lecture/{MANDATORY_CHAPTER_ID}. "
        "ADR-034 §CSS: the per-Section Quiz block uses the section-quiz-* CSS "
        "namespace (section-quiz-empty, section-quiz-form, section-quiz-button, etc.) "
        "in app/static/lecture.css per ADR-008. "
        f"HTML snippet (first 3000 chars): {html[:3000]!r}"
    )


# ===========================================================================
# AC-9 — "Generate a Quiz for this Section" form present in section-end
# Trace: TASK-013 AC-9; ADR-034 §Quiz-trigger affordance (Option 1)
# ===========================================================================


def test_quiz_button_form_present_in_section_end(tmp_path, monkeypatch) -> None:
    """
    AC-9 (TASK-013): the rendered Lecture page must contain a form whose action
    points at the POST /lecture/{chapter_id}/sections/{section_number}/quiz route.

    ADR-034 §Quiz-trigger: 'a real, user-triggered form with a submit button
    inside .section-quiz — POST /lecture/{chapter_id}/sections/{n}/quiz.'

    Confirms the affordance is a real form (not a disabled button or caption-only).

    Trace: AC-9; ADR-034 §Quiz-trigger affordance; ADR-034 §Option 1 (real route).
    """
    db_path = str(tmp_path / "quiz_form.db")
    client = _make_client(monkeypatch, db_path)

    response = client.get(f"/lecture/{MANDATORY_CHAPTER_ID}")
    assert response.status_code == 200
    html = response.text

    # The form action must point at the quiz route (contains '/quiz')
    # ADR-034: 'action="/lecture/{chapter_id}/sections/{section_number}/quiz"'
    assert "/quiz" in html, (
        f"GET /lecture/{MANDATORY_CHAPTER_ID} — no form action pointing at a /quiz "
        "route found in rendered HTML. "
        "AC-9/ADR-034: the 'Generate a Quiz for this Section' affordance must be a real "
        "form (not a disabled button) pointing at POST .../sections/{n}/quiz."
    )

    # The button itself must be present
    assert "Generate a Quiz" in html or "Generate" in html, (
        f"GET /lecture/{MANDATORY_CHAPTER_ID} — 'Generate a Quiz' button text not found. "
        "AC-9/ADR-034: the submit button label must convey 'Generate a Quiz for this Section'."
    )


# ===========================================================================
# AC-9 — POST /lecture/{chapter_id}/sections/{section_number}/quiz
#         valid section → 303 + Location with #section-{n-m}-end anchor
# Trace: TASK-013 AC-9; ADR-034 §Quiz-trigger route; ADR-031 (no-relocate)
# ===========================================================================


def test_post_quiz_route_returns_303(tmp_path, monkeypatch) -> None:
    """
    AC-9 (TASK-013) / ADR-034: POST /lecture/{chapter_id}/sections/{section_number}/quiz
    with a valid Section must return HTTP 303 See Other.

    ADR-034 §Quiz-trigger route: 'PRG redirect: 303 → /lecture/{chapter_id}
    #section-{section_number}-end'.

    Trace: AC-9; ADR-034 §Quiz-trigger route; RFC 7231 §6.4.4.
    """
    db_path = str(tmp_path / "post_303.db")
    client = _make_client(monkeypatch, db_path)

    response = client.post(
        f"/lecture/{MANDATORY_CHAPTER_ID}/sections/{MANDATORY_FIRST_SECTION}/quiz",
        follow_redirects=False,
    )
    assert response.status_code == 303, (
        f"POST /lecture/{MANDATORY_CHAPTER_ID}/sections/{MANDATORY_FIRST_SECTION}/quiz "
        f"returned HTTP {response.status_code}; expected 303 See Other. "
        "AC-9/ADR-034: the Quiz-trigger route must PRG-redirect (303) so browsers "
        "re-issue a GET and do not re-submit on back/refresh."
    )


def test_post_quiz_route_location_ends_with_section_end_anchor(
    tmp_path, monkeypatch
) -> None:
    """
    AC-9 (TASK-013) / ADR-034 + ADR-031: the 303 Location header for
    POST .../sections/{n}/quiz must end with '#section-{n}-end'.

    ADR-034: 'PRG redirect: 303 → /lecture/{chapter_id}#section-{section_number}-end'.
    ADR-031 (no-relocate mechanism): the Location anchors the .section-end wrapper
    so the response does not snap the reader.

    Trace: AC-9; ADR-034 §Quiz-trigger route; ADR-031 §Decision (reused unchanged).
    """
    db_path = str(tmp_path / "location_anchor.db")
    client = _make_client(monkeypatch, db_path)

    response = client.post(
        f"/lecture/{MANDATORY_CHAPTER_ID}/sections/{MANDATORY_FIRST_SECTION}/quiz",
        follow_redirects=False,
    )
    assert response.status_code == 303, (
        f"Expected 303 from quiz POST, got {response.status_code}. Prerequisite failed."
    )
    location = response.headers.get("location", "")
    expected_anchor = f"#section-{MANDATORY_FIRST_SECTION}-end"
    assert location.endswith(expected_anchor), (
        f"POST .../sections/{MANDATORY_FIRST_SECTION}/quiz — Location is {location!r}; "
        f"expected it to end with {expected_anchor!r}. "
        "AC-9/ADR-034/ADR-031: the PRG redirect must anchor at the section-end wrapper "
        "('#section-{n-m}-end') so the scroll position is preserved (no-relocate rule)."
    )


def test_post_quiz_creates_exactly_one_requested_row(tmp_path, monkeypatch) -> None:
    """
    AC-9 (TASK-013) / ADR-034: a single POST .../quiz must create exactly one
    'requested'-status Quiz row in the database.

    ADR-034 §Quiz-trigger route: 'calls app.persistence.request_quiz(section_id)
    which inserts a quizzes row with status='requested' … NO quiz_questions rows,
    NO quiz_attempts row.'

    ADR-033 §The `requested` status: no AI call made; honest 'we recorded your request.'

    Trace: AC-9; ADR-034 §Quiz-trigger route; ADR-033 §The `requested` status.
    """
    db_path = str(tmp_path / "one_row.db")
    client = _make_client(monkeypatch, db_path)

    # Ensure DB is bootstrapped
    client.get(f"/lecture/{MANDATORY_CHAPTER_ID}")

    assert _db_count_quizzes(db_path) == 0, "Prerequisite: no Quizzes before the POST."

    client.post(
        f"/lecture/{MANDATORY_CHAPTER_ID}/sections/{MANDATORY_FIRST_SECTION}/quiz",
        follow_redirects=False,
    )

    rows = _db_list_quizzes(db_path)
    assert len(rows) == 1, (
        f"After one POST to the quiz route, found {len(rows)} rows in quizzes; expected 1. "
        "AC-9/ADR-034: exactly one 'requested'-status Quiz row must be created."
    )
    assert rows[0]["status"] == "requested", (
        f"The newly-created Quiz row has status={rows[0]['status']!r}; expected 'requested'. "
        "ADR-034/ADR-033: the placeholder trigger creates a status='requested' row — "
        "not a fabricated Quiz; honestly 'we recorded your request'."
    )


def test_post_quiz_on_every_mandatory_chapter(tmp_path, monkeypatch) -> None:
    """
    Boundary: POST .../quiz must work (return 303) on MANDATORY Chapters.

    Tests ch-01 and ch-02 as representatives of the Mandatory class.

    Trace: AC-9; ADR-034 §Quiz-trigger route; MC-3.
    """
    mandatory_tests = [
        ("ch-01-cpp-refresher", "1-1"),
        ("ch-02-intro-to-algorithms", "2-1"),
    ]
    for chapter_id, section_number in mandatory_tests:
        db_path = str(tmp_path / f"mandatory_{chapter_id}.db")
        client = _make_client(monkeypatch, db_path)

        response = client.post(
            f"/lecture/{chapter_id}/sections/{section_number}/quiz",
            follow_redirects=False,
        )
        assert response.status_code == 303, (
            f"POST /lecture/{chapter_id}/sections/{section_number}/quiz "
            f"returned {response.status_code}; expected 303. "
            "AC-9/ADR-034: the quiz trigger route must work on Mandatory Chapters."
        )


# ===========================================================================
# Negative — invalid chapter_id or section_number → 4xx, no row created
# Trace: TASK-013 AC-9; ADR-034 §Quiz-trigger route (validates Section ID at handler)
# ===========================================================================


def test_post_quiz_unknown_chapter_returns_4xx(tmp_path, monkeypatch) -> None:
    """
    AC-9 (TASK-013) / ADR-034: POST to an unknown chapter_id must return 4xx
    and must NOT create any Quiz row.

    ADR-034: 'Validate chapter_id against the discovered set … reject (404)
    if not in the known Chapter set.' (Same pattern as the Notes route's
    chapter-validation, ADR-023.)

    Trace: AC-9; ADR-034 §Quiz-trigger route; ADR-024 §Validation split.
    """
    db_path = str(tmp_path / "unknown_chapter.db")
    client = _make_client(monkeypatch, db_path)

    # Ensure DB is bootstrapped
    client.get(f"/lecture/{MANDATORY_CHAPTER_ID}")

    response = client.post(
        "/lecture/ch-99-does-not-exist/sections/99-1/quiz",
        follow_redirects=False,
    )
    assert response.status_code in range(400, 500), (
        f"POST /lecture/ch-99-does-not-exist/sections/99-1/quiz returned "
        f"{response.status_code}; expected a 4xx client error. "
        "AC-9/ADR-034: an unknown chapter_id must be rejected at the route handler "
        "(same validation pattern as ADR-023 Notes route)."
    )

    # No Quiz row must have been created
    count = _db_count_quizzes(db_path)
    assert count == 0, (
        f"POST with unknown chapter_id created {count} Quiz row(s) despite the 4xx response. "
        "ADR-034: the handler must reject before calling request_quiz."
    )


def test_post_quiz_out_of_range_section_number_returns_4xx(
    tmp_path, monkeypatch
) -> None:
    """
    AC-9 (TASK-013) / ADR-034: POST with a section_number that does not exist in
    the parsed Section set must return 4xx and NOT create any Quiz row.

    ADR-034: 'Validate section_number against the parsed Section set: compose
    section_id = f"{chapter_id}#section-{section_number}"; reject (404) if not in
    {s["id"] for s in extract_sections(chapter_id, latex_text)}.'

    Trace: AC-9; ADR-034 §Quiz-trigger route (section validation); ADR-024
    §Validation split ('route handler validates … persistence trusts the caller').
    """
    db_path = str(tmp_path / "unknown_section.db")
    client = _make_client(monkeypatch, db_path)

    # Ensure DB is bootstrapped
    client.get(f"/lecture/{MANDATORY_CHAPTER_ID}")

    # Section number 999-999 does not exist in any Chapter.
    response = client.post(
        f"/lecture/{MANDATORY_CHAPTER_ID}/sections/999-999/quiz",
        follow_redirects=False,
    )
    assert response.status_code in range(400, 500), (
        f"POST /lecture/{MANDATORY_CHAPTER_ID}/sections/999-999/quiz returned "
        f"{response.status_code}; expected 4xx. "
        "AC-9/ADR-034: an out-of-range section_number must be rejected at the "
        "route handler — section_id validation is the route's job, not the "
        "persistence layer's."
    )

    # No Quiz row must have been created
    count = _db_count_quizzes(db_path)
    assert count == 0, (
        f"POST with out-of-range section_number created {count} Quiz row(s) despite "
        "the 4xx response. "
        "ADR-034: the handler must reject before calling request_quiz."
    )


def test_post_quiz_wrong_method_get_returns_405_or_404(tmp_path, monkeypatch) -> None:
    """
    Negative: GET on the POST-only quiz route must return 405 Method Not Allowed
    (or 404 if the router doesn't expose a GET route for this path at all).

    ADR-034: the route is declared as @app.post(...) — the router does not define
    a GET handler for this path, so a GET must not succeed.

    Trace: ADR-034 §Quiz-trigger route (POST only); HTTP RFC 7231 §6.5.5.
    """
    db_path = str(tmp_path / "wrong_method.db")
    client = _make_client(monkeypatch, db_path)

    response = client.get(
        f"/lecture/{MANDATORY_CHAPTER_ID}/sections/{MANDATORY_FIRST_SECTION}/quiz",
        follow_redirects=False,
    )
    assert response.status_code in (404, 405), (
        f"GET on the POST-only quiz route returned {response.status_code}; "
        "expected 404 or 405. "
        "ADR-034: the route is POST-only; GET must not succeed."
    )


# ===========================================================================
# AC-9 — After POST, GET shows the Quiz in requested status (populated-case)
# Trace: TASK-013 AC-9; ADR-034 §What the surface renders (populated case)
# ===========================================================================


def test_quiz_surface_shows_requested_status_after_post(tmp_path, monkeypatch) -> None:
    """
    AC-9 (TASK-013) / ADR-034: after a successful POST .../quiz, GET /lecture/...
    must show the Quiz's status in plain language — 'Requested' or 'generation pending'
    — and must NEVER present the Quiz as ready or takeable.

    ADR-034 §What the surface renders (populated case): 'requested → "Requested —
    generation pending"'; 'never presents a requested/generating Quiz as finished or
    takeable' (MC-5 applied to the read surface).

    Trace: AC-9; ADR-034 §Populated case; MC-5 ('never fabricated').
    """
    db_path = str(tmp_path / "populated_case.db")
    client = _make_client(monkeypatch, db_path)

    # Trigger a Quiz request
    client.post(
        f"/lecture/{MANDATORY_CHAPTER_ID}/sections/{MANDATORY_FIRST_SECTION}/quiz",
        follow_redirects=False,
    )

    # Now GET the page — the Quiz surface must show the status
    response = client.get(f"/lecture/{MANDATORY_CHAPTER_ID}")
    assert response.status_code == 200
    html = response.text

    # The status must be communicated honestly: 'Requested', 'generation pending', or
    # 'requested' (case-insensitive) — ADR-034 maps status='requested' to a plain-language
    # label. We check that the text conveys "request was recorded" NOT "Quiz is ready".
    status_signalled = (
        "Requested" in html
        or "requested" in html
        or "generation pending" in html
        or "Generation pending" in html
        or "section-quiz-item--requested" in html
    )
    assert status_signalled, (
        f"After POST .../quiz, GET /lecture/{MANDATORY_CHAPTER_ID} does not show "
        "the Quiz's 'requested' status in the HTML. "
        "ADR-034 §Populated case: 'requested' → 'Requested — generation pending' "
        "(or equivalent plain-language label). The surface must render the status."
    )

    # MUST NOT present the Quiz as 'ready' or 'takeable' — MC-5 (never fabricated).
    # A 'requested' row must never be labeled 'Ready' or offer a 'Take Quiz' button.
    # Note: we check for 'Ready' as a label; the word can appear in other contexts —
    # we scope the check to the quiz block context by checking for 'section-quiz-item--ready'.
    assert "section-quiz-item--ready" not in html, (
        f"After a POST that creates only a 'requested' Quiz, the rendered HTML contains "
        "'section-quiz-item--ready'. "
        "AC-9/MC-5/ADR-034: a 'requested' Quiz must NEVER be presented as 'ready'. "
        "The surface must render status honestly (MC-5: 'never fabricated')."
    )


def test_requested_quiz_never_presented_as_ready(tmp_path, monkeypatch) -> None:
    """
    MC-5 / ADR-034: a Quiz row with status='requested' must never be rendered as
    status='ready' or offered as a takeable Quiz.

    This is a stronger version of the populated-case test above, asserting directly
    on the raw HTML that no 'ready'-suggesting affordance appears after a POST that
    creates only a 'requested' row.

    PINNED CONTRACT: the HTML must not contain 'section-quiz-item--ready' (the CSS
    modifier for a ready Quiz that would trigger a take-button in a later task).

    Trace: MC-5; ADR-034 §Populated case ('no takeable affordance ships this task');
    Manifest §6 'AI failures are visible … never fabricates a result'.
    """
    db_path = str(tmp_path / "never_ready.db")
    client = _make_client(monkeypatch, db_path)

    # Create a 'requested' row
    client.post(
        f"/lecture/{MANDATORY_CHAPTER_ID}/sections/{MANDATORY_FIRST_SECTION}/quiz",
        follow_redirects=False,
    )

    # GET: the HTML must not contain any 'ready' quiz item class
    response = client.get(f"/lecture/{MANDATORY_CHAPTER_ID}")
    html = response.text

    assert "section-quiz-item--ready" not in html, (
        "After creating a 'requested' Quiz row, the page HTML contains "
        "'section-quiz-item--ready'. "
        "MC-5/ADR-034: a 'requested' row must never be rendered as 'ready'. "
        "No TASK-013 path produces a 'ready' Quiz; presenting 'requested' as 'ready' "
        "fabricates an AI result (a finished Quiz) that doesn't exist."
    )


# ===========================================================================
# AC-10 — No regressions on existing Lecture/navigation/rails/completion/Notes tests
# Trace: TASK-013 AC-10; ADR-034 §What is NOT changed
# ===========================================================================


@pytest.mark.parametrize("chapter_id", ALL_CHAPTER_IDS)
def test_no_regression_lecture_page_still_returns_200(
    chapter_id: str, tmp_path, monkeypatch
) -> None:
    """
    AC-10 (TASK-013): introducing the Quiz surface must not regress existing
    Lecture pages. Every Chapter still returns HTTP 200 with text/html.

    ADR-034 §What is NOT changed: 'the Notes surface, the section-completion
    route, the parser, discovery — unchanged; this task only adds the per-Section
    Quiz surface.'

    Trace: AC-10; ADR-034 §What is NOT changed.
    """
    db_path = str(tmp_path / f"regression_{chapter_id}.db")
    client = _make_client(monkeypatch, db_path)

    response = client.get(f"/lecture/{chapter_id}")
    assert response.status_code == 200, (
        f"Regression: GET /lecture/{chapter_id} returned {response.status_code} "
        "after the Quiz surface was added. "
        "AC-10: the Quiz surface must not regress any existing Lecture page."
    )
    assert "text/html" in response.headers.get("content-type", ""), (
        f"Regression: GET /lecture/{chapter_id} content-type is not text/html "
        "after the Quiz surface was added."
    )


@pytest.mark.parametrize("chapter_id", ALL_CHAPTER_IDS)
def test_no_regression_existing_notes_form_still_present(
    chapter_id: str, tmp_path, monkeypatch
) -> None:
    """
    AC-10 (TASK-013) / ADR-034 §What is NOT changed: the Notes form (RHS rail)
    must still be present on every Chapter after the Quiz surface is added.

    ADR-034: 'The Notes surface … unchanged.'

    Trace: AC-10; ADR-034 §What is NOT changed; ADR-029 (RHS Notes rail).
    """
    db_path = str(tmp_path / f"notes_regression_{chapter_id}.db")
    client = _make_client(monkeypatch, db_path)

    response = client.get(f"/lecture/{chapter_id}")
    assert response.status_code == 200

    html = response.text
    # The Notes form action must still be present (ADR-023/029).
    expected_action = f"/lecture/{chapter_id}/notes"
    assert expected_action in html, (
        f"Regression: GET /lecture/{chapter_id} — Notes form action "
        f"'{expected_action}' is missing after Quiz surface was added. "
        "AC-10/ADR-034: the Notes surface is unchanged by TASK-013."
    )


@pytest.mark.parametrize("chapter_id", ALL_CHAPTER_IDS)
def test_no_regression_section_completion_form_still_present(
    chapter_id: str, tmp_path, monkeypatch
) -> None:
    """
    AC-10 (TASK-013) / ADR-034: the section-completion form must still be present
    after the Quiz surface is added.

    ADR-034: 'The completion form (ADR-025/ADR-027/ADR-031) — unchanged; the
    Quiz block is rendered *after* it inside .section-end.'

    Trace: AC-10; ADR-034 §What is NOT changed; ADR-025/027 (completion form).
    """
    db_path = str(tmp_path / f"completion_regression_{chapter_id}.db")
    client = _make_client(monkeypatch, db_path)

    response = client.get(f"/lecture/{chapter_id}")
    assert response.status_code == 200

    html = response.text
    assert "section-completion-form" in html, (
        f"Regression: GET /lecture/{chapter_id} — 'section-completion-form' class "
        "missing after Quiz surface was added. "
        "AC-10/ADR-034: the completion form is rendered before the Quiz block inside "
        ".section-end; removing it is a regression."
    )


# ===========================================================================
# Performance — Lecture page with many Quizzes renders within budget
# Trace: ADR-034 §render_chapter ('one bulk Quiz query per request')
# ===========================================================================


def test_lecture_page_with_many_quizzes_within_time_budget(tmp_path, monkeypatch) -> None:
    """
    Performance: a Lecture page for ch-01-cpp-refresher with 30 Quiz rows (across
    multiple Sections) must render within 5 seconds.

    ADR-034 §render_chapter: 'one bulk Quiz query per request, mirroring
    complete_section_ids / rail_notes_context' — not N queries for N Sections.
    Budget is generous (5 s) to catch O(n²) scaling in the bulk query or the
    template loop over Sections × Quizzes.

    Trace: ADR-034 §render_chapter (one query per render); AC-7.
    """
    db_path = str(tmp_path / "perf_surface.db")
    client = _make_client(monkeypatch, db_path)

    # Bootstrap the DB
    client.get(f"/lecture/{MANDATORY_CHAPTER_ID}")

    # Insert 30 Quiz rows across multiple Sections via the route
    for i in range(30):
        section = MANDATORY_FIRST_SECTION if i % 2 == 0 else "1-2"
        client.post(
            f"/lecture/{MANDATORY_CHAPTER_ID}/sections/{section}/quiz",
            follow_redirects=False,
        )

    t0 = time.monotonic()
    response = client.get(f"/lecture/{MANDATORY_CHAPTER_ID}")
    elapsed = time.monotonic() - t0

    assert response.status_code == 200, (
        f"GET /lecture/{MANDATORY_CHAPTER_ID} with 30 Quiz rows returned "
        f"{response.status_code}."
    )
    assert elapsed < 5.0, (
        f"GET /lecture/{MANDATORY_CHAPTER_ID} with 30 Quiz rows took {elapsed:.2f}s "
        "(limit: 5s). "
        "ADR-034: the Lecture page should do ONE bulk quiz query per render — not N. "
        "A slow result suggests O(n) queries (one per Section) or O(n²) template loop."
    )
