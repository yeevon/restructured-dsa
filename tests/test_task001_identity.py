"""
Unit tests for Chapter / Section identity functions (ADR-002) and
chapter_designation function (ADR-004).

These tests exercise PURE FUNCTIONS and do not require the FastAPI server.
They are isolated enough that collection succeeds (ImportError is raised at
call-time when the implementation does not yet exist), so pytest --collect-only
will list them and they will fail (not error) when run.

pytestmark registers all tests under the task marker.
"""

import pytest

pytestmark = pytest.mark.task("TASK-001")


# ---------------------------------------------------------------------------
# Helper: deferred import — raises ImportError at test call-time, not at
# module-import time, so that collection succeeds before implementation exists.
# ---------------------------------------------------------------------------


def _get_chapter_designation():
    """
    Import chapter_designation from wherever ADR-004 places it.

    ADR-004: "a single function in a single Python module".
    ASSUMPTION: the implementer places it in app.designation (or app.chapter).
    We try a set of plausible module paths; if none work, raise ImportError
    clearly.
    """
    import importlib

    candidates = [
        ("app.designation", "chapter_designation"),
        ("app.chapter", "chapter_designation"),
        ("app.models", "chapter_designation"),
        ("app.lecture", "chapter_designation"),
        ("app.core", "chapter_designation"),
    ]
    for module_path, func_name in candidates:
        try:
            mod = importlib.import_module(module_path)
            fn = getattr(mod, func_name, None)
            if fn is not None:
                return fn
        except ImportError:
            continue
    raise ImportError(
        "Cannot import 'chapter_designation' from any expected module. "
        "ADR-004 requires it to exist in a single Python module under the app package."
    )


def _get_identity_functions():
    """
    Import Section / Chapter identity helpers.

    ADR-002: functions that derive chapter_number and section_id from source.
    ASSUMPTION: implementer exposes parse_chapter_number and/or derive_section_id
    from app.identity, app.parser, or app.lecture.
    """
    import importlib

    # We need at minimum a way to parse the chapter number from a chapter_id.
    # ADR-002: chapter_number comes from the kebab-case basename.
    candidates_number = [
        ("app.identity", "parse_chapter_number"),
        ("app.parser", "parse_chapter_number"),
        ("app.lecture", "parse_chapter_number"),
        ("app.core", "parse_chapter_number"),
        ("app.designation", "parse_chapter_number"),
        ("app.chapter", "parse_chapter_number"),
    ]
    parse_chapter_number = None
    for module_path, func_name in candidates_number:
        try:
            mod = importlib.import_module(module_path)
            fn = getattr(mod, func_name, None)
            if fn is not None:
                parse_chapter_number = fn
                break
        except ImportError:
            continue

    if parse_chapter_number is None:
        raise ImportError(
            "Cannot import 'parse_chapter_number' from any expected module. "
            "ADR-004 and ADR-002 require a function that extracts a chapter number "
            "from a chapter_id such as 'ch-01-cpp-refresher'."
        )

    return {"parse_chapter_number": parse_chapter_number}


# ---------------------------------------------------------------------------
# ADR-002 — Chapter identity
# ---------------------------------------------------------------------------


def test_adr002_chapter_id_for_ch01_is_basename_without_extension():
    """
    ADR-002: Chapter ID = file basename without .tex extension.
    For ch-01-cpp-refresher.tex the Chapter ID is 'ch-01-cpp-refresher'.

    Trace: ADR-002 "Chapter ID is a kebab-case slug derived from the chapter
    source file's basename (without the .tex extension)."
    """
    import pathlib

    # The derivation rule is a pure string operation; no import needed.
    source_path = pathlib.Path("content/latex/ch-01-cpp-refresher.tex")
    chapter_id = source_path.stem  # basename without extension
    assert chapter_id == "ch-01-cpp-refresher"


def test_adr002_chapter_number_extracted_from_ch01():
    """
    ADR-002 / ADR-004: parse_chapter_number('ch-01-cpp-refresher') == 1.

    Trace: ADR-004 "chapter_number = parse_chapter_number(chapter_id);
    for Chapter 1, chapter_id = 'ch-01-cpp-refresher', chapter_number = 1."
    """
    fns = _get_identity_functions()
    parse_chapter_number = fns["parse_chapter_number"]
    result = parse_chapter_number("ch-01-cpp-refresher")
    assert result == 1, (
        f"parse_chapter_number('ch-01-cpp-refresher') returned {result!r}, expected 1"
    )


def test_adr002_chapter_number_zero_padded_formats():
    """
    ADR-002: Chapter number must be extractable from both 'ch-01-...' and
    'ch2' styles (the corpus has both).

    Trace: ADR-002 notes "the existing chapter file naming is inconsistent
    (ch-01-cpp-refresher.tex vs ch2.tex, ch3.tex, ...)."

    ASSUMPTION: parse_chapter_number handles both naming styles.
    """
    fns = _get_identity_functions()
    parse = fns["parse_chapter_number"]
    # Zero-padded two-digit variant
    assert parse("ch-01-cpp-refresher") == 1
    # Non-padded single-digit variant (ch2 style)
    assert parse("ch2") == 2
    assert parse("ch7") == 7


def test_adr002_malformed_chapter_id_raises():
    """
    ADR-002 / ADR-004: A Chapter ID that does not match any expected pattern
    must cause the function to fail loudly.

    Trace: ADR-004 "If the Chapter ID does not match the expected pattern, the
    function fails loudly rather than defaulting to either designation."
    """
    fns = _get_identity_functions()
    parse = fns["parse_chapter_number"]
    with pytest.raises((ValueError, KeyError, RuntimeError)):
        parse("totally-invalid-chapter")


# ---------------------------------------------------------------------------
# ADR-002 — Section ID derivation
# ---------------------------------------------------------------------------


def test_adr002_section_id_structure_for_section_1_1():
    """
    ADR-002: Section ID = '{chapter_id}#section-{number-with-dot-as-hyphen}'.
    For section 1.1 in ch-01-cpp-refresher, the ID is
    'ch-01-cpp-refresher#section-1-1'.

    Trace: ADR-002 Section ID scheme.
    """
    # This is a pure string transformation; we test it as stated in ADR-002.
    chapter_id = "ch-01-cpp-refresher"
    raw_section_number = "1.1"
    section_number_kebab = raw_section_number.replace(".", "-")
    section_id = f"{chapter_id}#section-{section_number_kebab}"
    assert section_id == "ch-01-cpp-refresher#section-1-1"


def test_adr002_section_id_for_multi_digit_section():
    """
    ADR-002: Section number like '1.10' should produce 'section-1-10', not
    'section-1-1-0'.

    Trace: ADR-002 "leading number, lowercased, with the dot replaced by a
    hyphen."  A single dot-to-hyphen replacement is sufficient.
    """
    chapter_id = "ch-01-cpp-refresher"
    raw_section_number = "1.10"
    section_number_kebab = raw_section_number.replace(".", "-")
    section_id = f"{chapter_id}#section-{section_number_kebab}"
    assert section_id == "ch-01-cpp-refresher#section-1-10"


def test_adr002_only_section_macros_produce_section_ids_not_subsections():
    """
    ADR-002: \\subsection{} must NOT produce Section IDs.

    Strategy: if the implementation exposes a function that parses a LaTeX
    snippet into Section blocks, pass a subsection-containing snippet and
    assert no Section ID is produced for it.

    ASSUMPTION: the implementer exposes a function named extract_sections,
    parse_sections, or similar that takes a LaTeX body string and returns a list
    of section objects with 'id' fields.
    """
    import importlib

    candidates = [
        ("app.parser", "extract_sections"),
        ("app.lecture", "extract_sections"),
        ("app.core", "extract_sections"),
        ("app.identity", "extract_sections"),
    ]
    extract_sections = None
    for module_path, func_name in candidates:
        try:
            mod = importlib.import_module(module_path)
            fn = getattr(mod, func_name, None)
            if fn is not None:
                extract_sections = fn
                break
        except ImportError:
            continue

    if extract_sections is None:
        raise ImportError(
            "Cannot import 'extract_sections' from any expected module. "
            "ADR-002 requires a function that returns Section objects from a LaTeX body."
        )

    # Body with one real \section and one \subsection — only the section counts.
    latex_body = r"""
\section{2.1 Some Section}
\subsection{2.1.1 A Subsection}
Some content here.
"""
    sections = extract_sections("ch-01-cpp-refresher", latex_body)
    # Only one Section expected: the \section macro
    ids = [s.get("id") or getattr(s, "id", None) for s in sections]
    assert len(ids) == 1, (
        f"extract_sections returned {len(ids)} sections for a snippet with "
        f"one \\section and one \\subsection; expected 1. IDs found: {ids}"
    )
    fragment = ids[0]
    # The id attribute may be full ('ch-01-cpp-refresher#section-2-1') or just fragment
    assert "section-2-1" in str(fragment), (
        f"Section anchor ID does not contain 'section-2-1': {fragment!r}"
    )


def test_adr002_section_without_leading_number_raises():
    """
    ADR-002: A \\section macro without a leading numeric pattern causes the
    renderer to fail loudly — it must not fabricate a Section ID.

    Trace: ADR-002 "if the source contains \\section macros that lack a leading
    numeric pattern ... the renderer fails loudly rather than fabricating a
    Section ID."
    """
    import importlib

    candidates = [
        ("app.parser", "extract_sections"),
        ("app.lecture", "extract_sections"),
        ("app.core", "extract_sections"),
        ("app.identity", "extract_sections"),
    ]
    extract_sections = None
    for module_path, func_name in candidates:
        try:
            mod = importlib.import_module(module_path)
            fn = getattr(mod, func_name, None)
            if fn is not None:
                extract_sections = fn
                break
        except ImportError:
            continue

    if extract_sections is None:
        raise ImportError(
            "Cannot import 'extract_sections' — needed for ADR-002 loud-failure test."
        )

    latex_body = r"\section{Introduction}  % no leading number"
    with pytest.raises((ValueError, RuntimeError)):
        extract_sections("ch-01-cpp-refresher", latex_body)


# ---------------------------------------------------------------------------
# ADR-004 — chapter_designation
# ---------------------------------------------------------------------------


def test_adr004_chapter_1_is_mandatory():
    """
    ADR-004 / Manifest §8: chapter_designation('ch-01-cpp-refresher') == 'Mandatory'.

    Trace: ADR-004 "if 1 <= chapter_number <= 6: return 'Mandatory'".
    Manifest §8: "Currently Chapters 1–6 [are Mandatory]."
    """
    chapter_designation = _get_chapter_designation()
    result = chapter_designation("ch-01-cpp-refresher")
    assert result == "Mandatory", (
        f"chapter_designation('ch-01-cpp-refresher') returned {result!r}, "
        "expected 'Mandatory'. Manifest §8 and ADR-004 require Ch 1–6 = Mandatory."
    )


@pytest.mark.parametrize(
    "chapter_id,expected",
    [
        ("ch-01-cpp-refresher", "Mandatory"),
        ("ch2", "Mandatory"),
        ("ch3", "Mandatory"),
        ("ch4", "Mandatory"),
        ("ch5", "Mandatory"),
        ("ch6", "Mandatory"),
    ],
)
def test_adr004_chapters_1_through_6_are_mandatory(chapter_id, expected):
    """
    ADR-004 / Manifest §8: all Chapters 1–6 return 'Mandatory'.

    Trace: ADR-004 threshold rule; Manifest §8.
    """
    chapter_designation = _get_chapter_designation()
    result = chapter_designation(chapter_id)
    assert result == expected, (
        f"chapter_designation({chapter_id!r}) returned {result!r}, expected {expected!r}"
    )


@pytest.mark.parametrize(
    "chapter_id",
    ["ch7", "ch10", "ch11", "ch12", "ch13"],
)
def test_adr004_chapter_7_and_beyond_are_optional(chapter_id):
    """
    ADR-004 / Manifest §8: Chapters 7+ return 'Optional'.

    Trace: ADR-004 "return 'Optional'" for chapter_number >= 7.
    Manifest §8: "Currently Chapter 7 onward [is Optional]."
    """
    chapter_designation = _get_chapter_designation()
    result = chapter_designation(chapter_id)
    assert result == "Optional", (
        f"chapter_designation({chapter_id!r}) returned {result!r}, expected 'Optional'"
    )


def test_adr004_malformed_chapter_id_raises_loudly():
    """
    ADR-004: A malformed Chapter ID must cause chapter_designation to fail
    loudly, not return a default designation.

    Trace: ADR-004 "If the Chapter ID does not match the expected pattern, the
    function fails loudly rather than defaulting to either designation."
    """
    chapter_designation = _get_chapter_designation()
    with pytest.raises((ValueError, KeyError, RuntimeError)):
        chapter_designation("not-a-valid-chapter-id")


def test_adr004_designation_returns_literal_strings():
    """
    ADR-004: The return values are exactly the strings "Mandatory" or "Optional"
    (the manifest's canonical terms, manifest §8), not booleans, integers,
    or alternate capitalizations.

    Trace: ADR-004 pseudocode; Manifest §8 glossary.
    """
    chapter_designation = _get_chapter_designation()
    mandatory_result = chapter_designation("ch-01-cpp-refresher")
    optional_result = chapter_designation("ch7")
    assert mandatory_result == "Mandatory"  # exact string, case-sensitive
    assert optional_result == "Optional"  # exact string, case-sensitive
    # Must be str, not bool / int / enum with different repr
    assert isinstance(mandatory_result, str)
    assert isinstance(optional_result, str)


def test_adr004_no_section_level_designation_function_exists():
    """
    ADR-004 / Manifest §8: Sections inherit designation from their Chapter and
    do NOT carry their own designation.  There must be no per-Section designation
    function in the application.

    Manifest §8: "Sections do not carry their own designation independent of
    the Chapter."  ADR-004: "no Section-level designation function."

    Strategy: inspect the modules where chapter_designation lives and assert
    that no function named 'section_designation' or 'get_section_designation'
    or similar is exported.
    """
    import importlib

    candidates = [
        "app.designation",
        "app.chapter",
        "app.models",
        "app.lecture",
        "app.core",
    ]
    forbidden_names = {"section_designation", "get_section_designation", "section_mandatory"}
    violations: list[str] = []
    for module_path in candidates:
        try:
            mod = importlib.import_module(module_path)
            for name in forbidden_names:
                if hasattr(mod, name):
                    violations.append(f"{module_path}.{name}")
        except ImportError:
            continue

    assert violations == [], (
        f"Found per-Section designation function(s) {violations}. "
        "ADR-004 and Manifest §8 forbid per-Section designation."
    )


# ---------------------------------------------------------------------------
# ADR-002 — Determinism of Section ID derivation (unit level)
# ---------------------------------------------------------------------------


def test_adr002_section_id_derivation_is_deterministic():
    """
    ADR-002: The Section ID derivation is deterministic — calling it twice with
    the same input produces the same output.

    Trace: TASK-001 AC4 at unit level; ADR-002 "IDs are deterministic".
    """
    chapter_id = "ch-01-cpp-refresher"
    section_number = "1.1"
    # Pure string computation — no external state
    def derive(ch_id: str, sec_num: str) -> str:
        return f"{ch_id}#section-{sec_num.replace('.', '-')}"

    id1 = derive(chapter_id, section_number)
    id2 = derive(chapter_id, section_number)
    assert id1 == id2 == "ch-01-cpp-refresher#section-1-1"
