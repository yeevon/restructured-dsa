"""
Tests for MANIFEST §6 / §7 hard constraint: "The site never modifies LaTeX source."

We verify this by:
  1. Recording a content hash of every .tex fixture file BEFORE running parse/render.
  2. Running parse_chapter and render_html on it.
  3. Asserting the content hash is IDENTICAL after.

This is a pure file-integrity check. It does not depend on the content of the file.
We test against:
  - The fixture .tex files (always present)
  - The seeded Chapter 1 .tex under content/latex/ (skipped if not yet seeded)
"""

import hashlib
from pathlib import Path

import pytest

pytestmark = pytest.mark.task("TASK-001")

FIXTURE_TEX = Path(__file__).parent / "fixtures" / "latex" / "ch-99-test-chapter.tex"
PASSTHROUGH_FIXTURE = (
    Path(__file__).parent / "fixtures" / "latex" / "ch-98-passthrough-fixture.tex"
)
CONTENT_LATEX_DIR = Path(__file__).parent.parent / "content" / "latex"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _find_seeded_chapter_one() -> Path | None:
    import re

    pattern = re.compile(r"^ch-(\d{2})-([a-z0-9]+(?:-[a-z0-9]+)*)$")
    if not CONTENT_LATEX_DIR.exists():
        return None
    for tex_file in CONTENT_LATEX_DIR.glob("ch-01-*.tex"):
        if pattern.match(tex_file.stem):
            return tex_file
    return None


SEEDED_CH01 = _find_seeded_chapter_one()
SEED_MISSING_REASON = (
    "seed Chapter 1 LaTeX missing — implementer must seed content/latex/ch-01-<slug>.tex "
    "before this passes"
)


@pytest.fixture
def parse_chapter():
    from cs300.lecture import parse_chapter as _parse_chapter  # type: ignore[import]

    return _parse_chapter


@pytest.fixture
def render_html():
    from cs300.lecture import render_html as _render_html  # type: ignore[import]

    return _render_html


class TestFixtureFilesAreReadOnly:
    """After parsing and rendering a fixture .tex file, it must be byte-for-byte identical."""

    def test_ch99_fixture_unchanged_after_parse(self, parse_chapter):
        """Parsing ch-99-test-chapter.tex must not modify it."""
        hash_before = _sha256(FIXTURE_TEX)
        parse_chapter(FIXTURE_TEX)
        hash_after = _sha256(FIXTURE_TEX)
        assert hash_before == hash_after, (
            f"Fixture file {FIXTURE_TEX.name} was modified during parse_chapter()! "
            f"Hash before: {hash_before}, hash after: {hash_after}"
        )

    def test_ch99_fixture_unchanged_after_parse_and_render(
        self, parse_chapter, render_html
    ):
        """Parsing and rendering ch-99-test-chapter.tex must not modify it."""
        hash_before = _sha256(FIXTURE_TEX)
        chapter = parse_chapter(FIXTURE_TEX)
        render_html(chapter)
        hash_after = _sha256(FIXTURE_TEX)
        assert hash_before == hash_after, (
            f"Fixture file {FIXTURE_TEX.name} was modified during parse/render! "
            f"Hash before: {hash_before}, hash after: {hash_after}"
        )

    def test_ch98_passthrough_fixture_unchanged_after_parse(self, parse_chapter):
        """Parsing ch-98-passthrough-fixture.tex must not modify it."""
        hash_before = _sha256(PASSTHROUGH_FIXTURE)
        parse_chapter(PASSTHROUGH_FIXTURE)
        hash_after = _sha256(PASSTHROUGH_FIXTURE)
        assert hash_before == hash_after, (
            f"Passthrough fixture {PASSTHROUGH_FIXTURE.name} was modified during parse_chapter()!"
        )


@pytest.mark.skipif(SEEDED_CH01 is None, reason=SEED_MISSING_REASON)
class TestSeededChapterIsReadOnly:
    """The seeded Chapter 1 .tex under content/latex/ must not be modified by the pipeline."""

    def test_seeded_ch01_unchanged_after_parse(self, parse_chapter):
        """MANIFEST §6: parse_chapter must not write to the LaTeX source file."""
        hash_before = _sha256(SEEDED_CH01)  # type: ignore[arg-type]
        parse_chapter(SEEDED_CH01)
        hash_after = _sha256(SEEDED_CH01)  # type: ignore[arg-type]
        assert hash_before == hash_after, (
            f"Seeded file {SEEDED_CH01.name} was modified by parse_chapter()! "  # type: ignore[union-attr]
            "The site must NEVER modify LaTeX source (MANIFEST §6)."
        )

    def test_seeded_ch01_unchanged_after_full_render(self, parse_chapter, render_html):
        """MANIFEST §6: the full parse + render pipeline must not write to the LaTeX source file."""
        hash_before = _sha256(SEEDED_CH01)  # type: ignore[arg-type]
        chapter = parse_chapter(SEEDED_CH01)
        render_html(chapter)
        hash_after = _sha256(SEEDED_CH01)  # type: ignore[arg-type]
        assert hash_before == hash_after, (
            f"Seeded file {SEEDED_CH01.name} was modified by the parse+render pipeline! "  # type: ignore[union-attr]
            "The site must NEVER modify LaTeX source (MANIFEST §6)."
        )
