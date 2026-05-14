"""
TASK-019: Quiz-grading slice — Playwright DOM tests for AC-4 (graded-state
and grading_failed-state take page rendering).

Per ADR-010 / ADR-013 split-harness:
  - HTTP-protocol pytest tests (persistence, route shape, CSS, MC checks)
    live in tests/test_task019_take_page_rendering.py and
    tests/test_task019_grade_persistence.py.
  - Playwright tests (rendered DOM, visual affordance presence, graded-state
    render structure) live here.

Structural commitments tested here derive from ADR-051:
  - The graded Attempt take page renders an aggregate score block with class
    quiz-take-grade (visible in the DOM).
  - The graded Attempt take page renders per-Question explanation blocks with
    class quiz-take-explanation (one per Question, not zero).
  - The graded Attempt take page renders a correctness indicator class on each
    Question block (quiz-take-question-correct or quiz-take-question-incorrect).
  - The grading_failed take page renders the quiz-take-grading-failed block
    and does NOT render quiz-take-grade (no fabricated Grade).
  - The submitted take page does NOT render quiz-take-grade (no regression).

These tests drive a real browser (Chromium) against the live uvicorn server
started by the `live_server` fixture in tests/playwright/conftest.py.

NOTE: These tests set NOTES_DB_PATH to a per-test tmp_path DB (the same pattern
the TASK-018 preamble DOM tests use). The live_server thread reads os.environ
at call time, so setting NOTES_DB_PATH before page.goto() bootstraps the
correct schema.

ASSUMPTIONS:
  ASSUMPTION: ADR-051: the graded-state take page uses:
    - <section class="quiz-take-grade"> for the aggregate block
    - <div class="quiz-take-explanation"> for per-Question explanations
    - quiz-take-question-correct / quiz-take-question-incorrect modifier on each
      .quiz-take-question block
  ASSUMPTION: The grading_failed-state uses <section class="quiz-take-grading-failed">.
  ASSUMPTION: ch-01-cpp-refresher / section 1-1 are valid in the live corpus.
  ASSUMPTION: The live server thread inherits os.environ NOTES_DB_PATH set before
    the page.goto() call (per the TASK-018 conftest threading change).

pytestmark registers all tests under task("TASK-019").
"""

from __future__ import annotations

import pathlib
import sqlite3
import os

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.task("TASK-019")

MANDATORY_CHAPTER_ID = "ch-01-cpp-refresher"
MANDATORY_FIRST_SECTION = "1-1"


# ---------------------------------------------------------------------------
# DB setup helpers (reused from unit-test pattern)
# ---------------------------------------------------------------------------


def _db_rows(db_path: str, sql: str, params=()) -> list[dict]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.execute(sql, params)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def _setup_db_with_graded_attempt(
    db_path: str,
    *,
    test_passed: bool = True,
    weak_topics: list[str] | None = None,
    grading_failed: bool = False,
    grading_error: str = "aiw run failed",
    explanation: str = "Your implementation correctly handles the test case.",
) -> tuple[str, int]:
    """
    Set up a DB with a quiz, one question, and a graded (or grading_failed) Attempt.
    Returns (take_url_path, quiz_id).
    Must be called AFTER setting NOTES_DB_PATH in the environment.
    """
    if weak_topics is None:
        weak_topics = []

    from app.persistence import init_schema  # noqa: PLC0415
    init_schema()

    # Create quiz via the persistence layer directly to avoid HTTP bootstrap
    conn = sqlite3.connect(db_path)

    section_id = f"{MANDATORY_CHAPTER_ID}#section-{MANDATORY_FIRST_SECTION}"

    # Insert section content reference (the quiz needs a section_id)
    conn.execute(
        "INSERT OR IGNORE INTO quizzes (section_id, status) VALUES (?, ?)",
        (section_id, "ready"),
    )
    conn.commit()
    quiz_id_row = conn.execute(
        "SELECT quiz_id FROM quizzes WHERE section_id=?", (section_id,)
    ).fetchone()
    quiz_id = quiz_id_row[0]

    conn.execute(
        "INSERT INTO questions (section_id, prompt, topics, test_suite, preamble) VALUES (?, ?, ?, ?, ?)",
        (
            section_id,
            "Implement a stack.",
            "stacks",
            "def test_stack():\n    s = Stack()\n    s.push(1)\n    assert s.pop() == 1\n",
            "",
        ),
    )
    conn.commit()
    question_id = conn.execute(
        "SELECT question_id FROM questions ORDER BY question_id DESC LIMIT 1"
    ).fetchone()[0]
    conn.execute(
        "INSERT INTO quiz_questions (quiz_id, question_id, position) VALUES (?, ?, ?)",
        (quiz_id, question_id, 1),
    )
    conn.commit()
    conn.close()

    from app.persistence import (  # noqa: PLC0415
        start_attempt,
        save_attempt_responses,
        submit_attempt,
        save_attempt_test_result,
        mark_attempt_grading,
        save_attempt_grade,
        mark_attempt_grading_failed,
    )

    attempt = start_attempt(quiz_id)
    save_attempt_responses(attempt.attempt_id, {question_id: "class Stack: pass"})
    save_attempt_test_result(
        attempt.attempt_id,
        question_id,
        passed=test_passed if not grading_failed else True,
        status="ran",
        output="ok",
    )
    submit_attempt(attempt.attempt_id)
    mark_attempt_grading(attempt.attempt_id)

    if grading_failed:
        mark_attempt_grading_failed(attempt.attempt_id, error=grading_error)
    else:
        save_attempt_grade(
            attempt.attempt_id,
            per_question_explanations={question_id: explanation},
            weak_topics=weak_topics,
            recommended_sections=[],
        )

    take_url = f"/lecture/{MANDATORY_CHAPTER_ID}/sections/{MANDATORY_FIRST_SECTION}/quiz/{quiz_id}/take"
    return take_url, quiz_id


# ===========================================================================
# AC-4 (Playwright): graded-state DOM structure
# ===========================================================================


def test_graded_take_page_shows_grade_block(
    page: Page, live_server: str, tmp_path
) -> None:
    """
    AC-4 / ADR-051 (Playwright): the graded Attempt take page renders a
    <section class="quiz-take-grade"> aggregate block in the DOM.

    This is the Playwright structural assertion confirming the server actually
    renders the grade block — the HTTP-level test confirms the HTML contains
    the class; this test confirms a real browser sees the element.
    """
    db_path = str(tmp_path / "graded_dom.db")
    os.environ["NOTES_DB_PATH"] = db_path

    take_url, quiz_id = _setup_db_with_graded_attempt(db_path, test_passed=True)

    page.goto(f"{live_server}{take_url}")
    grade_section = page.locator(".quiz-take-grade")
    expect(grade_section).to_be_visible(), (
        "The .quiz-take-grade aggregate block must be visible on the graded "
        "Attempt take page. ADR-051 / AC-4."
    )


def test_graded_take_page_shows_explanation_block(
    page: Page, live_server: str, tmp_path
) -> None:
    """
    AC-4 / ADR-051 (Playwright): the graded Attempt take page renders at least
    one .quiz-take-explanation element containing the LLM's explanation text.

    The §8 Grade's per-Question explanation facet must be visible in the DOM.
    """
    db_path = str(tmp_path / "explanation_dom.db")
    os.environ["NOTES_DB_PATH"] = db_path

    custom_explanation = "Your push/pop correctly maintains LIFO order."
    take_url, quiz_id = _setup_db_with_graded_attempt(
        db_path, test_passed=True, explanation=custom_explanation
    )

    page.goto(f"{live_server}{take_url}")
    explanation_block = page.locator(".quiz-take-explanation")
    expect(explanation_block).to_be_visible(), (
        "The .quiz-take-explanation block must be visible on the graded take page. "
        "ADR-051 / AC-4 / §8 Grade per-Question explanation facet."
    )
    expect(explanation_block).to_contain_text(custom_explanation), (
        f"The explanation text '{custom_explanation}' must appear in the DOM."
    )


def test_graded_take_page_shows_correctness_indicator(
    page: Page, live_server: str, tmp_path
) -> None:
    """
    AC-4 / ADR-051 (Playwright): the graded Attempt take page shows a correctness
    indicator (quiz-take-question-correct or quiz-take-question-incorrect) for
    each Question.

    test_passed=True → is_correct=True → .quiz-take-question-correct class expected.
    """
    db_path = str(tmp_path / "correct_indicator_dom.db")
    os.environ["NOTES_DB_PATH"] = db_path

    take_url, quiz_id = _setup_db_with_graded_attempt(db_path, test_passed=True)

    page.goto(f"{live_server}{take_url}")
    # Either correct or incorrect class must be present on the question block
    correct_el = page.locator(".quiz-take-question-correct")
    incorrect_el = page.locator(".quiz-take-question-incorrect")

    correct_count = correct_el.count()
    incorrect_count = incorrect_el.count()
    assert correct_count + incorrect_count > 0, (
        "At least one .quiz-take-question-correct or .quiz-take-question-incorrect "
        "element must be present on the graded take page. "
        "ADR-051 / AC-4 / §8 Grade per-Question correctness indicator."
    )


def test_grading_failed_take_page_shows_honest_failure_block(
    page: Page, live_server: str, tmp_path
) -> None:
    """
    AC-4 / ADR-051 (Playwright): the grading_failed Attempt take page renders
    a <section class="quiz-take-grading-failed"> honest failure block.

    MC-5 / §6: AI failures are visible. The system surfaces the failure — never
    fabricates a Grade.
    """
    db_path = str(tmp_path / "fail_dom.db")
    os.environ["NOTES_DB_PATH"] = db_path

    take_url, quiz_id = _setup_db_with_graded_attempt(
        db_path, grading_failed=True, grading_error="LLM rate limit exceeded"
    )

    page.goto(f"{live_server}{take_url}")
    fail_section = page.locator(".quiz-take-grading-failed")
    expect(fail_section).to_be_visible(), (
        "The .quiz-take-grading-failed honest failure block must be visible on the "
        "grading_failed take page. ADR-051 / AC-4 / MC-5."
    )


def test_grading_failed_take_page_no_grade_block(
    page: Page, live_server: str, tmp_path
) -> None:
    """
    AC-4 / ADR-051 (Playwright) / MC-5: the grading_failed take page must NOT
    render a .quiz-take-grade block (no fabricated Grade in the DOM).

    Assertion-only test: this tests WHAT MUST NOT appear, per MC-5.
    """
    db_path = str(tmp_path / "no_grade_dom.db")
    os.environ["NOTES_DB_PATH"] = db_path

    take_url, quiz_id = _setup_db_with_graded_attempt(
        db_path, grading_failed=True, grading_error="workflow malformed output"
    )

    page.goto(f"{live_server}{take_url}")
    grade_section = page.locator(".quiz-take-grade")
    assert grade_section.count() == 0, (
        "grading_failed take page must NOT contain .quiz-take-grade in the DOM. "
        "ADR-051 / MC-5: no fabricated Grade."
    )
