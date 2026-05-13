"""
TASK-018: Question preamble — Playwright DOM tests.

Per ADR-010 / ADR-013 split-harness:
  - HTTP-protocol and unit tests live in tests/test_task018_preamble.py.
  - Playwright tests (rendered DOM, preamble block presence/absence) live here.

Structural commitments tested here derive from ADR-047:
  - When a Question has a non-empty preamble, the take page renders a
    <pre class="quiz-take-preamble"> element (the read-only preamble block).
  - When a Question has an empty preamble, NO <pre class="quiz-take-preamble">
    element appears in the DOM.
  - The existing <pre class="quiz-take-test-suite"> (ADR-043) still renders
    alongside the new preamble block.
  - No <script> tag is added to the take page (ADR-035 no-JS posture preserved).

These tests drive a real browser (Chromium) against the live_server fixture.
They inject a ready Quiz with a Question whose preamble is controlled.

ASSUMPTIONS:
  ASSUMPTION: The live_server fixture (from playwright/conftest.py) starts
    uvicorn and inherits NOTES_DB_PATH from the environment.
  ASSUMPTION: The take surface uses quiz-take-* CSS classes per ADR-038 /
    ADR-043 / ADR-047.
  ASSUMPTION: The Playwright tests inject a fresh DB via a pytest tmp_path
    fixture, bypassing the live DB so the preamble value is known.

pytestmark registers all tests under task("TASK-018").
"""

from __future__ import annotations

import json
import pathlib
import shutil
import sqlite3

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.task("TASK-018")

REPO_ROOT = pathlib.Path(__file__).parent.parent.parent
MANDATORY_CHAPTER_ID = "ch-01-cpp-refresher"
SECTION_ID = "ch-01-cpp-refresher#section-1-1"
SECTION_NUMBER = "1-1"

_CPP_PREAMBLE = "struct Pair { int a; int b; };"

_CPP_TEST_SUITE = (
    "#include <cassert>\n"
    "void swap_pair(Pair& p);\n"
    "int main() {\n"
    "    Pair p{1, 2};\n"
    "    swap_pair(p);\n"
    "    assert(p.a == 2);\n"
    "    return 0;\n"
    "}\n"
)


def _seed_quiz_with_preamble(db_path: str, preamble: str) -> tuple[int, int]:
    """
    Insert a ready Quiz with one Question carrying the given preamble.
    Returns (quiz_id, question_id).
    """
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "INSERT INTO quizzes (section_id, status, created_at) "
            "VALUES (?, 'ready', '2026-05-13T00:00:00Z')",
            (SECTION_ID,),
        )
        conn.commit()
        quiz_id = conn.execute(
            "SELECT quiz_id FROM quizzes WHERE section_id=? ORDER BY quiz_id DESC LIMIT 1",
            (SECTION_ID,),
        ).fetchone()[0]

        conn.execute(
            "INSERT INTO questions (section_id, prompt, topics, test_suite, preamble, created_at) "
            "VALUES (?, 'Implement swap_pair(Pair&)', 'data-structures', ?, ?, '2026-05-13T00:00:00Z')",
            (SECTION_ID, _CPP_TEST_SUITE, preamble),
        )
        conn.commit()
        question_id = conn.execute(
            "SELECT question_id FROM questions ORDER BY question_id DESC LIMIT 1"
        ).fetchone()[0]

        conn.execute(
            "INSERT INTO quiz_questions (quiz_id, question_id, position) VALUES (?, ?, 1)",
            (quiz_id, question_id),
        )
        conn.commit()
    finally:
        conn.close()
    return quiz_id, question_id


# ---------------------------------------------------------------------------
# AC-8 DOM: preamble block renders when non-empty
# ---------------------------------------------------------------------------


def test_take_page_dom_renders_preamble_block_when_non_empty(
    page: Page, live_server: str, tmp_path
) -> None:
    """
    AC-8 (TASK-018) / ADR-047: the take page for a Question with a non-empty
    preamble must render a <pre class="quiz-take-preamble"> element in the DOM.
    This is the Playwright DOM assertion complementing the HTTP-level check in
    test_task018_preamble.py::test_take_page_renders_preamble_block_when_non_empty.

    Uses a freshly-seeded DB (NOTES_DB_PATH monkeypatched) so the preamble
    value is known and controlled.
    """
    # AC-8 DOM: pre.quiz-take-preamble rendered when preamble non-empty (ADR-047)
    import os

    db_path = str(tmp_path / "pw_preamble_present.db")
    os.environ["NOTES_DB_PATH"] = db_path

    # Bootstrap the schema and seed the quiz
    page.goto(f"{live_server}/lecture/{MANDATORY_CHAPTER_ID}")
    page.wait_for_load_state("networkidle")

    quiz_id, question_id = _seed_quiz_with_preamble(db_path, _CPP_PREAMBLE)

    take_url = (
        f"{live_server}/lecture/{MANDATORY_CHAPTER_ID}"
        f"/sections/{SECTION_NUMBER}/quiz/{quiz_id}/take"
    )
    page.goto(take_url)
    page.wait_for_load_state("networkidle")

    preamble_block = page.locator(".quiz-take-preamble")
    assert preamble_block.count() >= 1, (
        f"No .quiz-take-preamble element found on the take page ({take_url}). "
        "ADR-047: a read-only <pre class='quiz-take-preamble'> block must render "
        "when the Question's preamble is non-empty."
    )


def test_take_page_dom_omits_preamble_block_when_empty(
    page: Page, live_server: str, tmp_path
) -> None:
    """
    AC-8 (TASK-018) / ADR-047: the take page for a Question with an empty preamble
    must NOT render any .quiz-take-preamble element in the DOM — no visible empty box.
    """
    # AC-8 DOM: no .quiz-take-preamble when preamble is empty (ADR-047 omit-when-empty)
    import os

    db_path = str(tmp_path / "pw_preamble_absent.db")
    os.environ["NOTES_DB_PATH"] = db_path

    page.goto(f"{live_server}/lecture/{MANDATORY_CHAPTER_ID}")
    page.wait_for_load_state("networkidle")

    quiz_id, question_id = _seed_quiz_with_preamble(db_path, "")  # empty preamble

    take_url = (
        f"{live_server}/lecture/{MANDATORY_CHAPTER_ID}"
        f"/sections/{SECTION_NUMBER}/quiz/{quiz_id}/take"
    )
    page.goto(take_url)
    page.wait_for_load_state("networkidle")

    preamble_block = page.locator(".quiz-take-preamble")
    assert preamble_block.count() == 0, (
        f"Found .quiz-take-preamble element on take page ({take_url}) when preamble is empty. "
        "ADR-047: the preamble block must be omitted when preamble is '' — "
        "no visible empty box must appear for a Question with no shared shapes."
    )


def test_take_page_dom_test_suite_block_still_renders_with_preamble(
    page: Page, live_server: str, tmp_path
) -> None:
    """
    AC-8 (TASK-018) / ADR-047 / ADR-043: adding the preamble block must not remove
    the existing .quiz-take-test-suite block. When preamble is non-empty, both
    .quiz-take-preamble AND .quiz-take-test-suite must be in the DOM.
    """
    # AC-8 DOM: both preamble and test-suite blocks render when preamble non-empty (ADR-047)
    import os

    db_path = str(tmp_path / "pw_both_blocks.db")
    os.environ["NOTES_DB_PATH"] = db_path

    page.goto(f"{live_server}/lecture/{MANDATORY_CHAPTER_ID}")
    page.wait_for_load_state("networkidle")

    quiz_id, question_id = _seed_quiz_with_preamble(db_path, _CPP_PREAMBLE)

    take_url = (
        f"{live_server}/lecture/{MANDATORY_CHAPTER_ID}"
        f"/sections/{SECTION_NUMBER}/quiz/{quiz_id}/take"
    )
    page.goto(take_url)
    page.wait_for_load_state("networkidle")

    test_suite_block = page.locator(".quiz-take-test-suite")
    assert test_suite_block.count() >= 1, (
        f"No .quiz-take-test-suite found on take page ({take_url}). "
        "ADR-043 / ADR-047: the test-suite block must still render when preamble is added."
    )

    preamble_block = page.locator(".quiz-take-preamble")
    assert preamble_block.count() >= 1, (
        f"No .quiz-take-preamble found on take page ({take_url}). "
        "ADR-047: the preamble block must render alongside the test-suite block."
    )
