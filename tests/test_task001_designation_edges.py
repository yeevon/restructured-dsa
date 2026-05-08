"""
Designation edge cases for TASK-001 (Category C).

These tests extend the ADR-004 / ADR-002 unit tests in test_task001_identity.py
with boundary and error-path cases that the earlier suite did not cover.

COVERED IN THIS FILE:

  C15 — Chapter 0 → raises (manifest §8 begins at Chapter 1)
  C16 — Negative chapter number → raises
  C17 — Very large chapter number (ch-99-future) → 'Optional'
  C18 — Boundary: ch6 → 'Mandatory', ch7 → 'Optional'
         (parametric check added here; skip note if already covered)
  C19 — Chapter ID with leading zeros → parse_chapter_number normalizes correctly
         (ch-01-x → 1; ch-007-x → 7)
  C20 — Chapter ID without separator after number (ch01-foo)
         PINNED CONTRACT: strict regex required → raises (see docstring)

PINNED CONTRACTS:

  C15 / C16 — chapter_designation for chapter 0 or negative:
    Manifest §8 defines Mandatory as 'Currently Chapters 1–6' and Optional as
    'Currently Chapter 7 onward.'  Chapter 0 and negative chapter numbers are
    outside the manifest's defined range.  ADR-004 states the function 'fails
    loudly rather than defaulting to either designation' for IDs that do not
    match the expected pattern.  PINNED: raises ValueError or RuntimeError.

  C20 — 'ch01-foo' (no hyphen between digit block and slug):
    ADR-002 shows both 'ch-01-cpp-refresher' and 'ch2' styles are in the
    corpus.  'ch01-foo' is an intermediate form not explicitly mentioned.
    ADR-002 does not enumerate it as valid.  PINNED as STRICT: the function
    must raise for this form, because:
      (a) 'ch-01-...' uses a hyphen after 'ch'; 'ch2' has no slug at all.
          'ch01-foo' is neither form.
      (b) A permissive regex that accepts 'ch01-foo' could silently accept
          malformed IDs that are one typo away from valid ones, violating the
          'fail loudly' principle.
      (c) Keeping the parser strict forces callers to use unambiguous IDs.
    If the implementer finds a strong reason to be permissive (accepting
    'ch01-foo' as chapter 1), they must update this test and document the
    decision here.

pytestmark registers all tests under task("TASK-001").
"""

import importlib

import pytest

pytestmark = pytest.mark.task("TASK-001")


# ---------------------------------------------------------------------------
# Deferred-import helpers (same pattern as test_task001_identity.py)
# ---------------------------------------------------------------------------


def _get_chapter_designation():
    """
    Import chapter_designation from wherever ADR-004 places it.

    ASSUMPTION: placed in a module under app.* (same as test_task001_identity).
    """
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


def _get_parse_chapter_number():
    """
    Import parse_chapter_number from wherever ADR-002/ADR-004 places it.

    ASSUMPTION: placed in a module under app.* (same as test_task001_identity).
    """
    candidates = [
        ("app.identity", "parse_chapter_number"),
        ("app.parser", "parse_chapter_number"),
        ("app.lecture", "parse_chapter_number"),
        ("app.core", "parse_chapter_number"),
        ("app.designation", "parse_chapter_number"),
        ("app.chapter", "parse_chapter_number"),
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
        "Cannot import 'parse_chapter_number' from any expected module. "
        "ADR-002 and ADR-004 require a function that extracts chapter number "
        "from a chapter_id string."
    )


# ---------------------------------------------------------------------------
# C15 — Chapter 0 → raises
# ---------------------------------------------------------------------------


def test_c15_chapter_zero_raises():
    """
    C15: chapter_designation for a chapter-0 ID must raise, not return a
    designation.

    Manifest §8: 'Currently Chapters 1–6 [Mandatory] … Currently Chapter 7
    onward [Optional].'  Chapter 0 is outside the manifest's defined chapter
    space — the manifest begins at Chapter 1.

    ADR-004: 'If the Chapter ID does not match the expected pattern, the
    function fails loudly rather than defaulting to either designation.'

    PINNED CONTRACT: raises ValueError or RuntimeError.

    Trace: ADR-004; manifest §8.
    """
    chapter_designation = _get_chapter_designation()
    with pytest.raises((ValueError, RuntimeError), match=""):
        chapter_designation("ch-00-intro")


def test_c15_chapter_zero_via_parse_raises():
    """
    C15 at the parse_chapter_number layer: chapter number 0 must not be
    returned as a valid chapter number.

    ADR-004 derives the designation via parse_chapter_number; if that function
    returns 0, the designation function would have to handle it explicitly.
    It's cleaner for parse_chapter_number itself to reject 'ch-00-*' as
    yielding an invalid chapter number.

    PINNED CONTRACT: either parse_chapter_number raises, OR
    chapter_designation raises when receiving 0.

    Trace: ADR-004; manifest §8.
    """
    parse = _get_parse_chapter_number()
    chapter_designation = _get_chapter_designation()

    # Attempt to parse 'ch-00-intro'
    try:
        num = parse("ch-00-intro")
    except (ValueError, RuntimeError):
        # Raised at parse level — contract satisfied.
        return

    # If parse returned 0, chapter_designation must reject it.
    if num == 0:
        with pytest.raises((ValueError, RuntimeError)):
            chapter_designation("ch-00-intro")
    else:
        # Unexpected numeric result — parse should have yielded 0 or raised.
        pytest.fail(
            f"parse_chapter_number('ch-00-intro') returned {num!r}. "
            "Expected either 0 (triggering designation failure) or a raised error. "
            "ADR-002/ADR-004: chapter 0 is outside the manifest's chapter range."
        )


# ---------------------------------------------------------------------------
# C16 — Negative chapter number → raises
# ---------------------------------------------------------------------------


def test_c16_negative_chapter_number_raises_via_designation():
    """
    C16: chapter_designation for a negative-chapter ID must raise.

    A chapter ID of 'ch--1-x' encodes a chapter number of -1 under a naive
    parser.  ADR-004's fail-loudly rule requires a raised exception — returning
    'Mandatory' or 'Optional' for a negative chapter would be fabrication.

    PINNED CONTRACT: raises ValueError or RuntimeError.

    Trace: ADR-004; ADR-002 fail-loudly rule.
    """
    chapter_designation = _get_chapter_designation()
    with pytest.raises((ValueError, RuntimeError), match=""):
        chapter_designation("ch--1-x")


def test_c16_negative_chapter_number_raises_via_parse():
    """
    C16 at the parse_chapter_number layer.

    'ch--1-x' has a double-hyphen which is not a valid chapter ID format per
    ADR-002. parse_chapter_number should reject it.

    Trace: ADR-002; ADR-004.
    """
    parse = _get_parse_chapter_number()
    with pytest.raises((ValueError, RuntimeError), match=""):
        parse("ch--1-x")


# ---------------------------------------------------------------------------
# C17 — Very large chapter number → 'Optional'
# ---------------------------------------------------------------------------


def test_c17_large_chapter_number_is_optional():
    """
    C17: chapter_designation('ch-99-future') → 'Optional'.

    ADR-004 threshold: chapters 1–6 are Mandatory, 7+ are Optional.
    Chapter 99 is well within the Optional range.

    Trace: ADR-004; manifest §8.
    """
    chapter_designation = _get_chapter_designation()
    result = chapter_designation("ch-99-future")
    assert result == "Optional", (
        f"chapter_designation('ch-99-future') returned {result!r}, expected 'Optional'. "
        "ADR-004: all chapters >= 7 are Optional."
    )


def test_c17_large_chapter_parse_number_is_99():
    """
    C17: parse_chapter_number('ch-99-future') must return 99.

    Trace: ADR-002 chapter number extraction; ADR-004.
    """
    parse = _get_parse_chapter_number()
    result = parse("ch-99-future")
    assert result == 99, (
        f"parse_chapter_number('ch-99-future') returned {result!r}, expected 99."
    )


# ---------------------------------------------------------------------------
# C18 — Boundary at the threshold: ch6 → Mandatory, ch7 → Optional
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "chapter_id,expected",
    [
        ("ch6", "Mandatory"),
        ("ch-06-some-topic", "Mandatory"),
        ("ch7", "Optional"),
        ("ch-07-some-topic", "Optional"),
    ],
)
def test_c18_boundary_chapters(chapter_id: str, expected: str):
    """
    C18: Explicit boundary tests at the Mandatory/Optional threshold.

    ADR-004: 'if 1 <= chapter_number <= 6: return "Mandatory"; return "Optional"'
    The boundary values are 6 (last Mandatory) and 7 (first Optional).

    Manifest §8: 'Currently Chapters 1–6 [Mandatory] … Chapter 7 onward [Optional].'

    Note: The parametric test in test_task001_identity.py covers ch6 ('ch6')
    and ch7 ('ch7') under test_adr004_chapters_1_through_6_are_mandatory and
    test_adr004_chapter_7_and_beyond_are_optional.  We add the zero-padded
    two-digit variants ('ch-06-...', 'ch-07-...') here as new boundary cases.

    Trace: ADR-004; manifest §8.
    """
    chapter_designation = _get_chapter_designation()
    result = chapter_designation(chapter_id)
    assert result == expected, (
        f"chapter_designation({chapter_id!r}) returned {result!r}, expected {expected!r}. "
        "ADR-004 boundary: ch6/ch-06 → Mandatory; ch7/ch-07 → Optional."
    )


# ---------------------------------------------------------------------------
# C19 — Chapter IDs with leading zeros
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "chapter_id,expected_number",
    [
        ("ch-01-x", 1),
        ("ch-06-x", 6),
        ("ch-07-x", 7),
        ("ch-007-x", 7),
        ("ch-013-x", 13),
    ],
)
def test_c19_leading_zeros_parse_correctly(chapter_id: str, expected_number: int):
    """
    C19: parse_chapter_number must strip leading zeros when extracting the
    chapter number from a zero-padded Chapter ID.

    ADR-002: 'ch-01-cpp-refresher → chapter number 1' (zero-padded two-digit).
    ADR-004 pseudocode: 'chapter_number = parse_chapter_number(chapter_id)'.
    If parse_chapter_number returns '01' (a string) or fails to strip the
    leading zero, subsequent 1 <= chapter_number <= 6 arithmetic fails.

    'ch-007-x' → 7 (three-digit padding must also be handled).

    Trace: ADR-002; ADR-004.
    """
    parse = _get_parse_chapter_number()
    result = parse(chapter_id)
    assert result == expected_number, (
        f"parse_chapter_number({chapter_id!r}) returned {result!r}, "
        f"expected {expected_number}. Leading zeros must be normalized to an int."
    )


@pytest.mark.parametrize(
    "chapter_id,expected_designation",
    [
        ("ch-01-x", "Mandatory"),
        ("ch-06-x", "Mandatory"),
        ("ch-07-x", "Optional"),
        ("ch-007-x", "Optional"),
    ],
)
def test_c19_leading_zeros_designation_correct(chapter_id: str, expected_designation: str):
    """
    C19 end-to-end: zero-padded IDs feed correctly through chapter_designation.

    ADR-004: designation derived from parsed chapter number.  If leading-zero
    parsing fails, a chapter ID like 'ch-06-x' might yield int('06')=6 (Python
    handles this) but 'ch-007-x' parsing edge must be verified.

    Trace: ADR-002; ADR-004.
    """
    chapter_designation = _get_chapter_designation()
    result = chapter_designation(chapter_id)
    assert result == expected_designation, (
        f"chapter_designation({chapter_id!r}) returned {result!r}, "
        f"expected {expected_designation!r}. "
        "ADR-004: leading-zero-padded Chapter IDs must resolve correctly."
    )


# ---------------------------------------------------------------------------
# C20 — Chapter ID without separator after number (ch01-foo)
# ---------------------------------------------------------------------------


def test_c20_chapter_id_without_separator_after_number_strict():
    """
    C20: 'ch01-foo' (no hyphen between 'ch' and the digit block) must be
    rejected by parse_chapter_number.

    PINNED CONTRACT: strict regex required → raises ValueError or RuntimeError.

    Rationale (documented per task instructions):
      ADR-002 defines two valid forms:
        (a) 'ch-01-cpp-refresher' — hyphen after 'ch', then two-digit block,
            then hyphen, then slug.
        (b) 'ch2', 'ch7', 'ch13' — 'ch' directly followed by digits, NO slug.
      'ch01-foo' is a hybrid: 'ch' directly followed by digits AND THEN a hyphen
      and slug.  It matches neither canonical form.  Accepting it silently would
      mean the parser is more permissive than the defined corpus, creating a gap
      between what IDs are valid and what files exist on disk.

    ADR-004: 'If the Chapter ID does not match the expected pattern, the function
    fails loudly.'

    If the implementer finds strong corpus evidence for 'ch01-...' form and wants
    to accept it, they must update this test with a documented rationale and a
    new pinned contract of PERMISSIVE.

    Trace: ADR-002; ADR-004.
    """
    parse = _get_parse_chapter_number()
    with pytest.raises((ValueError, RuntimeError), match=""):
        parse("ch01-foo")


def test_c20_chapter_designation_rejects_no_separator():
    """
    C20 end-to-end: chapter_designation('ch01-foo') must raise.

    This is the designation-layer check of the same contract above.  Whether
    the raise originates in parse_chapter_number or in chapter_designation
    itself, the external behavior must be a structured exception.

    Trace: ADR-004; ADR-002.
    """
    chapter_designation = _get_chapter_designation()
    with pytest.raises((ValueError, RuntimeError), match=""):
        chapter_designation("ch01-foo")
