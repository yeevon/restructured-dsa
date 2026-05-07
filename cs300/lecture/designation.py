"""
Pure function: derive Mandatory/Optional designation from a chapter ID.

Per TASK-001 (locked by author):
  ch-01 through ch-06 -> "mandatory"
  ch-07 and above     -> "optional"
"""

import re
from typing import Literal

_CHAPTER_ID_RE = re.compile(r"^ch-(\d{2})-")


def designation_for_chapter_id(chapter_id: str) -> Literal["mandatory", "optional"]:
    """Return 'mandatory' for ch-01..ch-06, 'optional' for ch-07+.

    If the chapter_id does not match the expected pattern the numeric prefix
    cannot be extracted; we return 'optional' as the safe default (no syllabus
    content should be silently promoted to mandatory).
    """
    match = _CHAPTER_ID_RE.match(chapter_id)
    if not match:
        return "optional"
    number = int(match.group(1))
    if 1 <= number <= 6:
        return "mandatory"
    return "optional"
