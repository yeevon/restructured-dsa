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

ADR-005: the canonical Chapter file basename form is Form A only:
  ch-{NN}-{slug}  where NN is exactly two zero-padded digits.
The _PATTERN_A regex below encodes Form A. Discovery code uses _PATTERN_A
directly to filter basenames before routing to parse_chapter_number.
"""

from __future__ import annotations

import re
from typing import Literal


# ADR-005: canonical form — Form A (ch-NN-slug, exactly two padded digits).
# Used by discovery.py to validate basenames before processing.
_PATTERN_A = re.compile(r"^ch-(\d{2})-[a-z0-9][a-z0-9-]*$")

# Internal broad pattern for parse_chapter_number to remain backward-compatible
# with any callers that use non-canonical IDs (e.g., ch-007-x used in TASK-001
# edge-case tests). Discovery validates via _PATTERN_A first; this function only
# extracts the number from whatever matches either pattern.
_PATTERN_A_BROAD = re.compile(r"^ch-(\d+)-[a-z0-9][a-z0-9-]*$")
_PATTERN_B = re.compile(r"^ch(\d+)$")


def parse_chapter_number(chapter_id: str) -> int:
    """
    Extract the chapter number from a Chapter ID.

    ADR-002: valid forms in the broader corpus are:
      (a) ch-01-cpp-refresher → 1  (Form A, canonical per ADR-005)
      (b) ch2, ch7, ch13 → 2, 7, 13  (Form B, legacy)
      Additionally handles over-padded digits (ch-007-x → 7) for
      backward-compatibility with TASK-001 edge-case tests.

    ADR-005: discovery code uses _PATTERN_A to pre-validate basenames;
    this function is the arithmetic layer, not the naming-policy layer.

    Raises ValueError for any ID that matches neither pattern or yields
    chapter number <= 0.

    ADR-004: failures propagate as structured errors (no silent default).
    """
    m = _PATTERN_A_BROAD.match(chapter_id)
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
        num = int(m.group(1))
        if num <= 0:
            raise ValueError(
                f"Chapter ID {chapter_id!r} yields chapter number {num}, "
                "which is outside the manifest's chapter range (>= 1). "
                "ADR-004: fail loudly for out-of-range chapter numbers."
            )
        return num

    raise ValueError(
        f"Chapter ID {chapter_id!r} does not match any recognized Chapter ID pattern. "
        "ADR-005 canonical form is 'ch-NN-slug'; ADR-004 fail loudly for "
        "IDs that yield no unambiguous chapter number."
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
