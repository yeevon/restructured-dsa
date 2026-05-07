"""
Tests for the LaTeX parser pure function `parse_chapter`.

Contract (ADR-001, ADR-002, ADR-003):
  - parse_chapter(tex_path: Path) -> Chapter
  - Chapter has: id (from filename), title (str), designation (Literal["mandatory","optional"]),
    sections (list[Section])
  - Section has: id (str of form "<chapter_id>#<section-slug>"), title (str), blocks (list[Block])
  - Section IDs are stable: parsing the same file twice yields identical ordered id lists.
  - Only \\section{...} produces a Section (not \\subsection).
  - If no \\section{...} exists, a single implicit Section with id "<chapter_id>#main" is produced.
  - The Chapter id equals the basename of the .tex file without extension.
  - Filenames not matching ^ch-(\\d{2})-([a-z0-9]+(?:-[a-z0-9]+)*)$ are rejected by the parser.
"""

from pathlib import Path

import pytest

pytestmark = pytest.mark.task("TASK-001")

FIXTURE_TEX = Path(__file__).parent / "fixtures" / "latex" / "ch-99-test-chapter.tex"


@pytest.fixture
def parse_chapter():
    from cs300.lecture import parse_chapter as _parse_chapter  # type: ignore[import]

    return _parse_chapter


@pytest.fixture
def parsed_chapter(parse_chapter):
    return parse_chapter(FIXTURE_TEX)


class TestChapterModel:
    """The parser returns a valid Chapter Pydantic model with expected fields."""

    def test_chapter_id_matches_filename(self, parsed_chapter):
        """ADR-001: chapter id is the basename of the .tex file without extension."""
        assert parsed_chapter.id == "ch-99-test-chapter"

    def test_chapter_has_title(self, parsed_chapter):
        """Chapter title must be a non-empty string."""
        assert isinstance(parsed_chapter.title, str)
        assert len(parsed_chapter.title) > 0

    def test_chapter_designation_is_optional_for_ch99(self, parsed_chapter):
        """ch-99 is above ch-06 boundary, so designation must be 'optional'."""
        assert parsed_chapter.designation == "optional"

    def test_chapter_designation_is_literal_string(self, parsed_chapter):
        """Designation must be exactly 'mandatory' or 'optional'."""
        assert parsed_chapter.designation in ("mandatory", "optional")

    def test_chapter_has_sections_list(self, parsed_chapter):
        """Chapter.sections must be a non-empty list (fixture has 3 \\section commands)."""
        assert isinstance(parsed_chapter.sections, list)
        assert len(parsed_chapter.sections) >= 1

    def test_chapter_sections_count_matches_fixture(self, parsed_chapter):
        """The fixture has 3 \\section{...} entries — parser must produce exactly 3 Sections."""
        # ch-99-test-chapter.tex has \section{Introduction to Arrays},
        # \section{Introduction to Linked Lists}, \section{Stacks and Queues}
        assert len(parsed_chapter.sections) == 3


class TestSectionModel:
    """Sections within a parsed Chapter have correct shape per ADR-002/ADR-003."""

    def test_section_id_scoped_to_chapter(self, parsed_chapter):
        """ADR-002: Section id is '<chapter_id>#<section-slug>'."""
        for section in parsed_chapter.sections:
            assert section.id.startswith("ch-99-test-chapter#"), (
                f"Section id {section.id!r} does not start with chapter id prefix"
            )

    def test_section_id_contains_hash_separator(self, parsed_chapter):
        """ADR-002: Section id uses '#' as separator between chapter id and section slug."""
        for section in parsed_chapter.sections:
            parts = section.id.split("#")
            assert len(parts) == 2, (
                f"Section id {section.id!r} must have exactly one '#'"
            )
            assert len(parts[0]) > 0, "Chapter id portion must be non-empty"
            assert len(parts[1]) > 0, "Section slug portion must be non-empty"

    def test_section_has_title(self, parsed_chapter):
        """Each Section has a non-empty title string."""
        for section in parsed_chapter.sections:
            assert isinstance(section.title, str)
            assert len(section.title) > 0, f"Section {section.id!r} has empty title"

    def test_section_has_blocks_list(self, parsed_chapter):
        """Each Section has a blocks attribute (list, possibly empty)."""
        for section in parsed_chapter.sections:
            assert isinstance(section.blocks, list)

    def test_subsection_does_not_produce_section(self, parsed_chapter):
        """ADR-002: \\subsection{...} must NOT appear as a top-level Section.
        The fixture has one \\subsection — verify the section count is still 3, not 4."""
        assert len(parsed_chapter.sections) == 3

    def test_first_section_slug_derived_from_heading(self, parsed_chapter):
        """ADR-002: The section slug is derived from the heading text.
        '\\section{Introduction to Arrays}' should slug to 'introduction-to-arrays'."""
        first_section = parsed_chapter.sections[0]
        slug = first_section.id.split("#")[1]
        # The slugify rule: lowercase, non-[a-z0-9] runs become single hyphens, strip edges
        assert slug == "introduction-to-arrays", (
            f"Expected slug 'introduction-to-arrays', got {slug!r}"
        )


class TestSectionIdStability:
    """ADR-002 / TASK-001 AC: Parsing the same file twice yields identical Section id lists."""

    def test_section_ids_are_stable_across_two_parses(self, parse_chapter):
        """The parser is a pure function: same input → same output, always."""
        chapter_a = parse_chapter(FIXTURE_TEX)
        chapter_b = parse_chapter(FIXTURE_TEX)
        ids_a = [s.id for s in chapter_a.sections]
        ids_b = [s.id for s in chapter_b.sections]
        assert ids_a == ids_b, (
            f"Section ids differ across two parses of the same file:\n"
            f"  First:  {ids_a}\n"
            f"  Second: {ids_b}"
        )

    def test_section_id_order_is_stable(self, parse_chapter):
        """The order of Sections matches document order and is reproducible."""
        chapter_a = parse_chapter(FIXTURE_TEX)
        chapter_b = parse_chapter(FIXTURE_TEX)
        assert [s.id for s in chapter_a.sections] == [s.id for s in chapter_b.sections]


class TestFilenameValidation:
    """ADR-001: The parser rejects files with non-conforming filenames."""

    def test_malformed_filename_raises_error(self, parse_chapter, tmp_path):
        """A .tex file not matching ^ch-(\\d{2})-([a-z0-9]+(?:-[a-z0-9]+)*)$ must be rejected."""
        bad_file = tmp_path / "Chapter1.tex"
        bad_file.write_text(
            r"\documentclass{article}\begin{document}Hello\end{document}"
        )
        with pytest.raises(Exception):
            parse_chapter(bad_file)

    def test_single_digit_prefix_filename_raises_error(self, parse_chapter, tmp_path):
        """'ch-1-bst.tex' (single digit) must be rejected — regex requires two digits."""
        bad_file = tmp_path / "ch-1-bst.tex"
        bad_file.write_text(
            r"\documentclass{article}\begin{document}Hello\end{document}"
        )
        with pytest.raises(Exception):
            parse_chapter(bad_file)

    def test_underscore_slug_filename_raises_error(self, parse_chapter, tmp_path):
        """'ch-01_bst.tex' (underscore instead of hyphen) must be rejected."""
        bad_file = tmp_path / "ch-01_bst.tex"
        bad_file.write_text(
            r"\documentclass{article}\begin{document}Hello\end{document}"
        )
        with pytest.raises(Exception):
            parse_chapter(bad_file)

    def test_valid_filename_does_not_raise(self, parse_chapter):
        """The fixture file has a valid conforming filename — it must not raise."""
        # This should not raise; we already use it in other tests but make it explicit
        chapter = parse_chapter(FIXTURE_TEX)
        assert chapter is not None


class TestImplicitSectionFallback:
    """ADR-002: A .tex with no \\section{} produces a single implicit Section with id '#main'."""

    def test_no_section_produces_implicit_main_section(self, parse_chapter, tmp_path):
        """A chapter with no \\section{} headings gets one Section with slug 'main'."""
        no_section_tex = tmp_path / "ch-50-no-sections.tex"
        no_section_tex.write_text(
            r"\documentclass{article}"
            r"\title{No Sections Chapter}"
            r"\begin{document}"
            r"\maketitle"
            r"This chapter has body text but no section headings."
            r"\end{document}"
        )
        chapter = parse_chapter(no_section_tex)
        assert len(chapter.sections) == 1
        assert chapter.sections[0].id == "ch-50-no-sections#main"
