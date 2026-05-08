"""
ADR-004: Mandatory/Optional designation source.

The mapping from Chapter ID to Mandatory|Optional is encoded as a single
function in this single Python module.

Manifest §8 defines:
  - Mandatory: Currently Chapters 1–6
  - Optional: Currently Chapter 7 onward

The threshold (1 <= chapter_number <= 6) is the single source of truth.
No other code path may encode this threshold; every learner-facing surface
calls chapter_designation().

MC-3 (manifest-conformance): this module is the canonical mapping source.
"""

from __future__ import annotations

import re
from typing import Literal


# Valid Chapter ID patterns per ADR-002:
#   (a) ch-NN-slug  — e.g. "ch-01-cpp-refresher", "ch-06-some-topic"
#   (b) chN / chNN  — e.g. "ch2", "ch7", "ch13"  (no hyphen, no slug)
#
# STRICTLY rejects:
#   - ch01-foo  (no initial hyphen, digits, then hyphen+slug) — neither canonical form
#   - ch-00-*   (chapter 0 is outside manifest §8 range)
#   - ch--1-*   (negative / double-hyphen)
#   - anything else

# Pattern (a): ch-{digits}-{slug} — digits come after the first hyphen
# The slug is one or more alphanumeric/hyphen characters after the second hyphen
_PATTERN_A = re.compile(r"^ch-(\d+)-[a-z0-9][a-z0-9-]*$")

# Pattern (b): ch{digits} with NO trailing hyphen+slug
_PATTERN_B = re.compile(r"^ch(\d+)$")


def parse_chapter_number(chapter_id: str) -> int:
    """
    Extract the chapter number from a Chapter ID.

    ADR-002: valid forms are:
      (a) ch-01-cpp-refresher  → 1
      (b) ch2, ch7, ch13       → 2, 7, 13

    Leading zeros are stripped: ch-01 → 1, ch-007 → 7.

    Raises ValueError for any ID that does not match a valid pattern or
    yields chapter number <= 0.

    ADR-004: the chapter_designation function calls this; failures here
    propagate as structured errors (no silent default).
    """
    m = _PATTERN_A.match(chapter_id)
    if m:
        num = int(m.group(1))  # int() strips leading zeros
        if num <= 0:
            raise ValueError(
                f"Chapter ID {chapter_id!r} yields chapter number {num}, "
                "which is outside the manifest's chapter range (>= 1). "
                "ADR-004: fail loudly for out-of-range chapter numbers."
            )
        return num

    m = _PATTERN_B.match(chapter_id)
    if m:
        num = int(m.group(1))  # int() strips leading zeros
        if num <= 0:
            raise ValueError(
                f"Chapter ID {chapter_id!r} yields chapter number {num}, "
                "which is outside the manifest's chapter range (>= 1). "
                "ADR-004: fail loudly for out-of-range chapter numbers."
            )
        return num

    raise ValueError(
        f"Chapter ID {chapter_id!r} does not match any recognized Chapter ID pattern. "
        "ADR-002 defines two valid forms: 'ch-NN-slug' and 'chN'. "
        "ADR-004: fail loudly for IDs that yield no unambiguous chapter number."
    )


def chapter_designation(chapter_id: str) -> Literal["Mandatory", "Optional"]:
    """
    Return the Mandatory|Optional designation for a Chapter.

    Manifest §8 (binding):
      Mandatory: Currently Chapters 1–6.
      Optional:  Currently Chapter 7 onward.

    The threshold (<= 6) is encoded here and nowhere else (MC-3).

    Raises ValueError if the chapter_id does not match the expected pattern
    (ADR-004: fail loudly; never default to either designation).

    Returns exactly the strings "Mandatory" or "Optional" (manifest §8 glossary).
    """
    chapter_number = parse_chapter_number(chapter_id)  # raises if malformed
    if 1 <= chapter_number <= 6:
        return "Mandatory"
    return "Optional"
