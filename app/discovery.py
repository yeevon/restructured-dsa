"""
ADR-007: Chapter discovery, display label, and within-group ordering.

Single shared helper that enumerates Chapter .tex files under a source root
at request time, groups them by Mandatory/Optional designation, and orders
each group by parsed chapter number ascending.

ADR-006 contract: both GET / and GET /lecture/{chapter_id} call discover_chapters()
so the rail and the landing page are always in sync (one source of truth).

MC-3: no chapter-number threshold literals here — all designation work
      goes through chapter_designation() in app/designation.py.
MC-6: files under the source root are opened read-only only.
"""

from __future__ import annotations

import logging
import pathlib
import re
from dataclasses import dataclass
from typing import Literal

from app.designation import chapter_designation, parse_chapter_number, _PATTERN_A
from app.parser import extract_sections

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Performance: per-process mtime-keyed section-count cache (ADR-026 §denominator).
#
# discover_chapters() is called on every page render.  Each call previously
# invoked extract_sections() (a full pylatexenc parse) for all 12 Chapter files,
# making each render O(N_chapters) in parser work regardless of which Chapter was
# requested.  This caused test_all_chapters_respond_within_time_budget to exceed
# the 3-second-per-Chapter budget (~3.5s measured; test TASK-005 regression).
#
# The fix: cache section counts by (absolute_path_str, mtime_ns).  The source
# .tex files are read-only to the application (MC-6 / manifest §5).  If they
# change (during development), the mtime changes and the cache misses cleanly.
# The cache is module-level and lives for the process lifetime — safe for a
# single-process uvicorn server.  A uvicorn --reload restart clears it.
#
# The cached value is an int (section count) or None (extract_sections raised).
# None is cached too so the expensive parse is not retried within the same process.
# ---------------------------------------------------------------------------
_section_count_cache: dict[tuple[str, int], int | None] = {}


def _get_cached_section_count(
    tex_file: pathlib.Path,
    chapter_id: str,
    latex_text: str,
) -> int | None:
    """Return cached section count for tex_file, or parse and cache it.

    Cache key: (absolute_path_str, mtime_ns).  Returns None if extract_sections()
    raises (the None is cached so the parse is not retried within the same process).
    """
    try:
        mtime_ns = tex_file.stat().st_mtime_ns
    except OSError:
        mtime_ns = 0
    key = (str(tex_file), mtime_ns)
    if key in _section_count_cache:
        return _section_count_cache[key]
    try:
        discovered = extract_sections(chapter_id, latex_text)
        count: int | None = len(discovered)
    except Exception as exc:
        logger.warning(
            "Discovery: extract_sections failed for %r — %s; "
            "degrading label_status to 'section_extraction_failed'.",
            chapter_id,
            exc,
        )
        count = None
    _section_count_cache[key] = count
    return count


# ADR-007 §display-label: extract \title{...} from each Chapter's preamble.
# Shared function — reused by both the navigation helper and (via main.py) the
# Lecture route handler so the rail label and the Lecture header agree by construction.
_TITLE_RE = re.compile(r'\\title\{([^}]+)\}')


def extract_title_from_latex(latex_text: str) -> str | None:
    """
    Extract the plain-text title from the LaTeX \\title{...} macro.

    Returns the normalized title string, or None if the macro is absent or
    extracts to an empty string.

    ADR-003 (preamble peek) / ADR-007 (single shared extraction).
    """
    m = _TITLE_RE.search(latex_text)
    if not m:
        return None
    raw = m.group(1)
    # Strip LaTeX formatting: \\ (line break), \large, \small, etc.
    raw = re.sub(r'\\\\', ' ', raw)            # strip the \\ linebreak macro (ADR-014)
    raw = re.sub(r'\\[a-zA-Z]+', ' ', raw)
    raw = re.sub(r'[{}]', '', raw)
    normalized = re.sub(r'\s+', ' ', raw).strip()
    return normalized if normalized else None


@dataclass
class ChapterEntry:
    """Per-row data for the navigation surface (ADR-007 helper return shape).

    ADR-026: section_count is the number of Sections discovered in this Chapter.
    Used as the denominator (Y) in the rail's "X / Y" progress decoration.
    Zero if section extraction failed (label_status == "section_extraction_failed").
    """
    chapter_id: str
    chapter_number: int
    display_label: str
    link_target: str
    label_status: Literal["ok", "missing_title", "malformed_title", "section_extraction_failed"]
    section_count: int = 0   # ADR-026: total Sections discovered; 0 if not yet set
    complete_count: int = 0  # ADR-026: complete Sections (attached by route handler; not from DB)


class DuplicateChapterNumber(ValueError):
    """Raised when two Chapter files share the same chapter number (ADR-007)."""
    pass


class InvalidChapterBasename(ValueError):
    """Raised when a .tex file in the source root has a basename that does not
    match ADR-005 Form A. Fail-loudly per the TASK-002 acceptance criterion."""
    pass


def discover_chapters(
    source_root: pathlib.Path,
) -> dict[Literal["Mandatory", "Optional"], list[ChapterEntry]]:
    """
    Enumerate Chapter .tex files under source_root at request time.

    ADR-007 contract:
    - Scans source_root for *.tex files at the moment of the call (no startup cache).
    - Validates each basename against ADR-005's Form A regex; invalid basenames raise
      InvalidChapterBasename (fail-loudly per TASK-002 AC — not silently omitted).
    - Extracts \\title{...} from each valid Chapter's preamble using
      extract_title_from_latex(). Missing or empty title → label_status "missing_title",
      display_label carries an explicit error marker.
    - Groups by chapter_designation() (ADR-004). No chapter-number literals here.
    - Orders each group by parsed chapter number ascending.
    - Raises DuplicateChapterNumber if two valid files share the same chapter number.

    Returns a dict with exactly two keys: "Mandatory" and "Optional". Each value is
    a list (possibly empty) of ChapterEntry objects in canonical order.
    """
    mandatory: list[ChapterEntry] = []
    optional: list[ChapterEntry] = []

    # Track chapter numbers to detect duplicates.
    # Maps chapter_number → first chapter_id that claimed it.
    seen_numbers: dict[int, str] = {}

    for tex_file in sorted(source_root.glob("*.tex")):
        basename = tex_file.stem  # filename without .tex

        if not _PATTERN_A.match(basename):
            raise InvalidChapterBasename(
                f"File {basename!r} does not match the ADR-005 Form A naming pattern "
                "(ch-NN-slug with exactly two zero-padded digits and a kebab-case slug). "
                "Invalid basenames are rejected fail-loudly (TASK-002 AC / ADR-005). "
                "Rename the file to Form A before adding it to the corpus."
            )

        try:
            chapter_number = parse_chapter_number(basename)
        except ValueError as exc:
            logger.warning("Discovery: skipping %r — %s", basename, exc)
            continue

        if chapter_number in seen_numbers:
            first = seen_numbers[chapter_number]
            raise DuplicateChapterNumber(
                f"Chapter number {chapter_number} is claimed by two files: "
                f"{first!r} and {basename!r}. "
                "ADR-007: two files sharing the same chapter number is an "
                "unrecoverable ambiguity. Resolve by deleting or renaming one file."
            )
        seen_numbers[chapter_number] = basename

        # ADR-007: extract \title{...} read-only; do not parse the full body here.
        try:
            latex_text = tex_file.read_text(encoding="utf-8")
        except OSError as exc:
            logger.warning("Discovery: cannot read %r — %s", str(tex_file), exc)
            continue

        raw_title = extract_title_from_latex(latex_text)

        if raw_title is None:
            label_status: Literal["ok", "missing_title", "malformed_title"] = "missing_title"
            display_label = f"[Chapter {basename} — title unavailable]"
            logger.warning(
                "Discovery: %r has no \\title{} macro. "
                "Row will display with error marker.",
                basename,
            )
        else:
            label_status = "ok"
            display_label = raw_title

        # ADR-026: compute per-Chapter section count (denominator for "X / Y" decoration).
        # Use the mtime-keyed cache to avoid re-parsing on every page render.
        section_count = 0
        if label_status == "ok":
            cached = _get_cached_section_count(tex_file, basename, latex_text)
            if cached is None:
                label_status = "section_extraction_failed"
                section_count = 0
            else:
                section_count = cached

        designation = chapter_designation(basename)
        entry = ChapterEntry(
            chapter_id=basename,
            chapter_number=chapter_number,
            display_label=display_label,
            link_target=f"/lecture/{basename}",
            label_status=label_status,
            section_count=section_count,
        )

        if designation == "Mandatory":
            mandatory.append(entry)
        else:
            optional.append(entry)

    mandatory.sort(key=lambda e: e.chapter_number)
    optional.sort(key=lambda e: e.chapter_number)

    return {"Mandatory": mandatory, "Optional": optional}
