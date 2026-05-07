"""
Tests for the Lecture Page FastAPI route: GET /chapters/{chapter_id}/lecture

Contract (ADR-005, ADR-001, ADR-002, ADR-003, TASK-001 ACs):
  - GET /chapters/{chapter_id}/lecture returns 200 with a full HTML page.
  - Response contains the Chapter title.
  - Response contains every Section's title.
  - Every Section has a stable anchor: <section id="section-{slug}" ...>
  - The Chapter wrapper element carries data-designation="mandatory" for ch-01..ch-06.
  - Every Section wrapper carries the same data-designation as the Chapter.
  - Unknown chapter_id returns 404 (FastAPI default per ADR-005).
  - Content-Type is text/html.

The route test uses the seeded Chapter 1 .tex under content/latex/.
If the seed file is absent, the test is skipped with a clear message.

The designation and parser-stability tests in this file do NOT skip; they require
the implementation to exist.
"""

import re
from pathlib import Path

import pytest
from starlette.testclient import TestClient

pytestmark = pytest.mark.task("TASK-001")

CONTENT_LATEX_DIR = Path(__file__).parent.parent / "content" / "latex"
CHAPTER_ID_PATTERN = re.compile(r"^ch-(\d{2})-([a-z0-9]+(?:-[a-z0-9]+)*)$")


def _find_seeded_chapter_one() -> Path | None:
    """Return the path to the seeded Chapter 1 .tex file, or None if not present."""
    if not CONTENT_LATEX_DIR.exists():
        return None
    for tex_file in CONTENT_LATEX_DIR.glob("ch-01-*.tex"):
        if CHAPTER_ID_PATTERN.match(tex_file.stem):
            return tex_file
    return None


SEEDED_CH01 = _find_seeded_chapter_one()
SEED_MISSING_REASON = (
    "seed Chapter 1 LaTeX missing — implementer must seed content/latex/ch-01-<slug>.tex "
    "before this passes"
)


@pytest.fixture
def app():
    from cs300.app import app as _app  # type: ignore[import]

    return _app


@pytest.fixture
def client(app):
    return TestClient(app)


class TestContentLatexDirectory:
    """ADR-001 / TASK-001 AC: whatever .tex lives under content/latex/ matches the filename regex."""

    def test_content_latex_dir_exists(self):
        """The content/latex/ directory must exist once the implementer seeds Chapter 1."""
        assert CONTENT_LATEX_DIR.exists(), (
            "content/latex/ directory does not exist. "
            "The implementer must create this directory and seed at least one chapter .tex file."
        )

    def test_all_tex_files_match_chapter_id_regex(self):
        """Every .tex file under content/latex/ must match ^ch-(\\d{2})-([a-z0-9]+(?:-[a-z0-9]+)*)$."""
        if not CONTENT_LATEX_DIR.exists():
            pytest.fail("content/latex/ directory does not exist")
        tex_files = list(CONTENT_LATEX_DIR.glob("*.tex"))
        assert len(tex_files) >= 1, (
            "At least one .tex file must exist under content/latex/"
        )
        for tex_file in tex_files:
            assert CHAPTER_ID_PATTERN.match(tex_file.stem), (
                f"File {tex_file.name!r} does not match the required filename regex "
                r"'^ch-(\d{2})-([a-z0-9]+(?:-[a-z0-9]+)*)$'"
            )


@pytest.mark.skipif(SEEDED_CH01 is None, reason=SEED_MISSING_REASON)
class TestLectureRouteWithSeededChapter:
    """Route tests that require the seeded Chapter 1 .tex to be present."""

    @pytest.fixture
    def chapter_id(self):
        return SEEDED_CH01.stem  # type: ignore[union-attr]

    @pytest.fixture
    def parsed_chapter(self, chapter_id):
        from cs300.lecture import parse_chapter  # type: ignore[import]

        return parse_chapter(SEEDED_CH01)

    def test_lecture_route_returns_200(self, client, chapter_id):
        """ADR-005: GET /chapters/{chapter_id}/lecture returns HTTP 200."""
        response = client.get(f"/chapters/{chapter_id}/lecture")
        assert response.status_code == 200

    def test_response_is_html(self, client, chapter_id):
        """The response Content-Type must be text/html."""
        response = client.get(f"/chapters/{chapter_id}/lecture")
        assert "text/html" in response.headers.get("content-type", "")

    def test_response_contains_chapter_title(self, client, chapter_id, parsed_chapter):
        """The rendered page contains the Chapter title."""
        response = client.get(f"/chapters/{chapter_id}/lecture")
        assert parsed_chapter.title in response.text, (
            f"Chapter title {parsed_chapter.title!r} not found in rendered page"
        )

    def test_response_contains_all_section_titles(
        self, client, chapter_id, parsed_chapter
    ):
        """The rendered page contains every Section's title text."""
        response = client.get(f"/chapters/{chapter_id}/lecture")
        for section in parsed_chapter.sections:
            assert section.title in response.text, (
                f"Section title {section.title!r} not found in rendered page"
            )

    def test_section_anchors_are_present(self, client, chapter_id, parsed_chapter):
        """ADR-005: Each Section is rendered with id='section-{slug}' anchor."""
        response = client.get(f"/chapters/{chapter_id}/lecture")
        for section in parsed_chapter.sections:
            slug = section.id.split("#")[1]
            expected_anchor = f'id="section-{slug}"'
            assert expected_anchor in response.text, (
                f"Section anchor {expected_anchor!r} not found in rendered page"
            )

    def test_chapter_wrapper_has_mandatory_designation(self, client, chapter_id):
        """TASK-001 AC: ch-01 is Mandatory; the Chapter wrapper must carry data-designation='mandatory'."""
        response = client.get(f"/chapters/{chapter_id}/lecture")
        assert 'data-designation="mandatory"' in response.text, (
            'Chapter wrapper element missing data-designation="mandatory" attribute'
        )

    def test_every_section_wrapper_has_designation(
        self, client, chapter_id, parsed_chapter
    ):
        """TASK-001 AC: Every Section wrapper carries data-designation matching the Chapter's designation."""
        response = client.get(f"/chapters/{chapter_id}/lecture")
        html = response.text
        # ch-01 → all sections should be mandatory
        # Count occurrences of data-designation="mandatory" — must be >= 1 (chapter) + N sections
        designation_count = html.count('data-designation="mandatory"')
        # At minimum: 1 chapter wrapper + 1 per section
        min_expected = 1 + len(parsed_chapter.sections)
        assert designation_count >= min_expected, (
            f"Expected at least {min_expected} data-designation='mandatory' attributes "
            f"(1 chapter wrapper + {len(parsed_chapter.sections)} section wrappers), "
            f"found {designation_count}"
        )

    def test_unknown_chapter_returns_404(self, client):
        """ADR-005: A request for an unknown chapter_id returns 404."""
        response = client.get("/chapters/ch-99-does-not-exist/lecture")
        assert response.status_code == 404

    def test_malformed_chapter_id_returns_404(self, client):
        """ADR-005 / ADR-001: A malformed chapter_id (doesn't match regex) returns 404."""
        response = client.get("/chapters/not-a-valid-chapter-id/lecture")
        assert response.status_code == 404


class TestLectureRouteImport:
    """The cs300 package must be importable with app and lecture submodules."""

    def test_cs300_package_is_importable(self):
        import cs300  # type: ignore[import]  # noqa: F401

        assert cs300 is not None

    def test_cs300_app_is_importable(self):
        import cs300.app  # type: ignore[import]  # noqa: F401
        from cs300.app import app  # type: ignore[import]

        assert app is not None

    def test_cs300_lecture_is_importable(self):
        import cs300.lecture  # type: ignore[import]  # noqa: F401

    def test_cs300_lecture_parse_chapter_is_exported(self):
        from cs300.lecture import parse_chapter  # type: ignore[import]

        assert callable(parse_chapter)

    def test_cs300_lecture_render_html_is_exported(self):
        from cs300.lecture import render_html  # type: ignore[import]

        assert callable(render_html)

    def test_cs300_lecture_designation_fn_is_exported(self):
        from cs300.lecture import designation_for_chapter_id  # type: ignore[import]

        assert callable(designation_for_chapter_id)
