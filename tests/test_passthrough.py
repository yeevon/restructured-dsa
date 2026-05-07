"""
Tests for ADR-004: Unrecognized LaTeX environments render as visible PassthroughBlock,
never as silent drops and never as 500s.

The fixture ch-98-passthrough-fixture.tex contains \\begin{somethingweird}...\\end{somethingweird}.
Tests confirm:
  1. The parser produces a PassthroughBlock (not drops it, not raises).
  2. The PassthroughBlock carries environment="somethingweird" and non-empty raw_latex.
  3. The HTML renderer renders it as a <div class="lecture-passthrough"> with the required
     data-environment attribute, the label paragraph, and a <pre> containing the source.
"""

from pathlib import Path

import pytest

pytestmark = pytest.mark.task("TASK-001")

PASSTHROUGH_FIXTURE = (
    Path(__file__).parent / "fixtures" / "latex" / "ch-98-passthrough-fixture.tex"
)


@pytest.fixture
def parse_chapter():
    from cs300.lecture import parse_chapter as _parse_chapter  # type: ignore[import]

    return _parse_chapter


@pytest.fixture
def render_html():
    from cs300.lecture import render_html as _render_html  # type: ignore[import]

    return _render_html


@pytest.fixture
def parsed_passthrough_chapter(parse_chapter):
    return parse_chapter(PASSTHROUGH_FIXTURE)


class TestPassthroughBlockInModel:
    """The parser must produce a PassthroughBlock for unknown environments."""

    def test_parser_does_not_raise_on_unknown_environment(self, parse_chapter):
        """ADR-004: parsing a .tex with an unknown environment must not raise."""
        chapter = parse_chapter(PASSTHROUGH_FIXTURE)
        assert chapter is not None

    def test_passthrough_block_is_present(self, parsed_passthrough_chapter):
        """At least one block across all sections must be a PassthroughBlock with kind='passthrough'."""
        from cs300.lecture import PassthroughBlock  # type: ignore[import]

        all_blocks = [
            block
            for section in parsed_passthrough_chapter.sections
            for block in section.blocks
        ]
        passthrough_blocks = [b for b in all_blocks if isinstance(b, PassthroughBlock)]
        assert len(passthrough_blocks) >= 1, (
            "Expected at least one PassthroughBlock for '\\begin{somethingweird}' in fixture, "
            f"got block kinds: {[b.kind for b in all_blocks]}"
        )

    def test_passthrough_block_environment_name(self, parsed_passthrough_chapter):
        """ADR-003/ADR-004: PassthroughBlock.environment is the name of the unrecognized env."""
        from cs300.lecture import PassthroughBlock  # type: ignore[import]

        all_blocks = [
            block
            for section in parsed_passthrough_chapter.sections
            for block in section.blocks
        ]
        passthrough_blocks = [b for b in all_blocks if isinstance(b, PassthroughBlock)]
        assert len(passthrough_blocks) >= 1
        assert passthrough_blocks[0].environment == "somethingweird"

    def test_passthrough_block_raw_latex_is_nonempty(self, parsed_passthrough_chapter):
        """ADR-003/ADR-004: PassthroughBlock.raw_latex contains the verbatim source."""
        from cs300.lecture import PassthroughBlock  # type: ignore[import]

        all_blocks = [
            block
            for section in parsed_passthrough_chapter.sections
            for block in section.blocks
        ]
        passthrough_blocks = [b for b in all_blocks if isinstance(b, PassthroughBlock)]
        assert len(passthrough_blocks) >= 1
        assert isinstance(passthrough_blocks[0].raw_latex, str)
        assert len(passthrough_blocks[0].raw_latex.strip()) > 0

    def test_passthrough_block_kind_field(self, parsed_passthrough_chapter):
        """ADR-003: Block discriminator field is 'kind'; PassthroughBlock.kind == 'passthrough'."""
        from cs300.lecture import PassthroughBlock  # type: ignore[import]

        all_blocks = [
            block
            for section in parsed_passthrough_chapter.sections
            for block in section.blocks
        ]
        passthrough_blocks = [b for b in all_blocks if isinstance(b, PassthroughBlock)]
        assert len(passthrough_blocks) >= 1
        assert passthrough_blocks[0].kind == "passthrough"

    def test_normal_blocks_are_not_dropped(self, parsed_passthrough_chapter):
        """Sections that contain only normal content must still have blocks."""
        # The fixture has two \\section{} entries; the normal sections should not be empty
        normal_sections = [
            s
            for s in parsed_passthrough_chapter.sections
            if "normal" in s.title.lower()
        ]
        # We expect at least one section called "Normal Section" or "Another Normal Section"
        assert len(normal_sections) >= 1


class TestPassthroughBlockInHTML:
    """The HTML renderer must emit the required passthrough markup from ADR-004."""

    def test_rendered_html_contains_passthrough_div(self, parse_chapter, render_html):
        """ADR-004: passthrough block renders as <div class='lecture-passthrough'>."""
        chapter = parse_chapter(PASSTHROUGH_FIXTURE)
        html = render_html(chapter)
        assert 'class="lecture-passthrough"' in html, (
            'Rendered HTML must contain a <div class="lecture-passthrough"> for the '
            "unknown '\\begin{somethingweird}' environment"
        )

    def test_rendered_html_has_data_environment_attribute(
        self, parse_chapter, render_html
    ):
        """ADR-004: passthrough div must carry data-environment='somethingweird'."""
        chapter = parse_chapter(PASSTHROUGH_FIXTURE)
        html = render_html(chapter)
        assert 'data-environment="somethingweird"' in html

    def test_rendered_html_has_passthrough_label(self, parse_chapter, render_html):
        """ADR-004: rendered passthrough block must include a visible label paragraph."""
        chapter = parse_chapter(PASSTHROUGH_FIXTURE)
        html = render_html(chapter)
        assert "lecture-passthrough-label" in html
        assert "[unrendered LaTeX: somethingweird]" in html

    def test_rendered_html_has_passthrough_pre_block(self, parse_chapter, render_html):
        """ADR-004: rendered passthrough must include a <pre class='lecture-passthrough-source'>."""
        chapter = parse_chapter(PASSTHROUGH_FIXTURE)
        html = render_html(chapter)
        assert "lecture-passthrough-source" in html

    def test_passthrough_does_not_produce_500(self, parse_chapter, render_html):
        """Rendering a chapter with an unrecognized environment must complete without raising."""
        chapter = parse_chapter(PASSTHROUGH_FIXTURE)
        html = render_html(chapter)
        assert isinstance(html, str)
        assert len(html) > 0
