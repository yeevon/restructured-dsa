"""
Tests for the pure function `designation_for_chapter_id`.

Contract (locked in TASK-001 / MANIFEST §6 / ADR-001):
  - ch-01 through ch-06 → "mandatory"
  - ch-07 and above    → "optional"
  - The boundary is between ch-06 (mandatory) and ch-07 (optional).
  - The function lives in cs300.lecture.
"""

import pytest

pytestmark = pytest.mark.task("TASK-001")


@pytest.fixture
def designation_fn():
    from cs300.lecture import designation_for_chapter_id  # type: ignore[import]

    return designation_for_chapter_id


class TestDesignationForChapterId:
    """Unit tests for the designation pure function."""

    def test_ch01_is_mandatory(self, designation_fn):
        assert designation_fn("ch-01-intro") == "mandatory"

    def test_ch06_is_mandatory(self, designation_fn):
        """ch-06 is the last mandatory chapter — boundary case."""
        assert designation_fn("ch-06-trees") == "mandatory"

    def test_ch07_is_optional(self, designation_fn):
        """ch-07 is the first optional chapter — other side of the boundary."""
        assert designation_fn("ch-07-graphs") == "optional"

    def test_ch10_is_optional(self, designation_fn):
        """A higher chapter number well into optional range."""
        assert designation_fn("ch-10-advanced-sorting") == "optional"

    def test_ch03_is_mandatory(self, designation_fn):
        """A mid-range mandatory chapter."""
        assert designation_fn("ch-03-linked-lists") == "mandatory"

    def test_ch99_is_optional(self, designation_fn):
        """The maximum chapter number (per ADR-001 cap of 99) is optional."""
        assert designation_fn("ch-99-edge-case") == "optional"

    def test_return_type_is_literal(self, designation_fn):
        """Return value must be exactly the string 'mandatory' or 'optional', not a truthy value."""
        mandatory_result = designation_fn("ch-01-intro")
        optional_result = designation_fn("ch-07-graphs")
        assert mandatory_result == "mandatory"
        assert optional_result == "optional"
        # Not just truthy — must be the exact strings from the Literal type
        assert mandatory_result in ("mandatory", "optional")
        assert optional_result in ("mandatory", "optional")
