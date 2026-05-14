"""
TASK-019: Quiz-grading slice — tests for AC-4 (graded/grading_failed take-page render)
and AC-5 (CSS namespace in quiz.css).

Tests derive from:
  ADR-051 — Graded-state and grading-failed-state rendering on the take page:
    - quiz_take.html.j2 gains {% elif attempt.status == 'graded' %} branch
    - quiz_take.html.j2 gains {% elif attempt.status == 'grading_failed' %} branch
    - graded branch renders <section class="quiz-take-grade"> aggregate block
    - per-Question .quiz-take-explanation block (aq.explanation rendered)
    - per-Question .quiz-take-question-correct / .quiz-take-question-incorrect modifier
    - grading_failed branch renders <section class="quiz-take-grading-failed"> honest block
    - NO fabricated Grade in grading_failed render (MC-5)
    - NO submit form / NO "Run tests" button on graded/grading_failed Attempt
    - submitted render unchanged (no regression)
    - route reads Grade via get_grade_for_attempt and passes 'grade' context var
  ADR-050 — Grade dataclass; get_grade_for_attempt; QuizAttempt.grading_error

  ADR-008 (CSS namespace rule):
    - New rules use quiz-take-* namespace
    - No new CSS file; no base.css change

Coverage matrix:
  Boundary:
    - test_take_page_graded_renders_score_block:
        GET .../take for graded Attempt → HTML contains quiz-take-grade class.
    - test_take_page_graded_renders_explanation_block:
        GET .../take for graded Attempt → HTML contains quiz-take-explanation class
        with non-empty text.
    - test_take_page_graded_renders_correctness_indicator:
        GET .../take for graded Attempt → HTML contains quiz-take-question-correct
        or quiz-take-question-incorrect class (not absent — correctness is indicated).
    - test_take_page_grading_failed_renders_honest_failure_block:
        GET .../take for grading_failed Attempt → HTML contains quiz-take-grading-failed class.
    - test_take_page_submitted_render_unchanged:
        GET .../take for submitted Attempt → still renders "submitted" state (no regression);
        does NOT show quiz-take-grade.
    - test_take_page_graded_no_submit_form:
        graded Attempt → no <form method="post"> / no submit button in HTML (read-only).
    - test_take_page_grading_failed_no_fabricated_grade:
        grading_failed Attempt → quiz-take-grade NOT in the HTML (MC-5).
    - test_take_page_grading_failed_no_per_question_explanation:
        grading_failed Attempt → quiz-take-explanation NOT in the HTML (no fabricated
        per-Question explanation; is_correct is NULL on failure path).
  Edge:
    - test_take_page_graded_empty_weak_topics_renders_without_error:
        graded Attempt with weak_topics=[] → page renders without error (no crash
        on empty list rendering).
    - test_take_page_graded_renders_weak_topics_when_present:
        graded Attempt with weak_topics=['stacks'] → HTML contains the topic text.
    - test_take_page_graded_renders_recommended_sections_when_present:
        graded Attempt with recommended_sections=['ch-01-cpp-refresher#section-1-1'] →
        HTML contains the section reference.
    - test_take_page_in_progress_render_unchanged:
        in_progress Attempt → still renders the in_progress state (no regression).
  Negative:
    - test_take_page_graded_no_run_tests_button:
        graded Attempt → no "Run tests" button in HTML (in_progress-only action).
    - test_take_page_grading_failed_grading_error_detail_present:
        grading_failed Attempt → HTML contains the grading_error detail text
        (ADR-051: the collapsible <details> exposing grading_error — honest failure
        per MC-5's spirit: the author is the learner; honesty over hiding).
    - test_take_page_graded_mc5_no_fabricated_grade_text:
        graded Attempt → no "Grading not yet available" or "submitted" fallback text
        alongside the Grade (the page must show the actual Grade, not the fallback).
  Performance:
    - skipped: the route renders a single Attempt; the scale surface is the
      per-Question loop which is O(n) trivially. No scaling signal in the ACs for
      the take-page render path.

pytestmark registers all tests under task("TASK-019").

ASSUMPTIONS:
  ASSUMPTION: The take route URL is
    /lecture/{chapter_id}/sections/{section_number}/quiz/{quiz_id}/take
    (ADR-038 — unchanged).

  ASSUMPTION: The graded Attempt render uses CSS classes quiz-take-grade,
    quiz-take-explanation, quiz-take-question-correct, quiz-take-question-incorrect
    per ADR-051. If the implementer uses different class names, the assertions will
    fail as expected (the test-writer's stronger AC interpretation per AC-4's
    structural commitment).

  ASSUMPTION: The grading_failed Attempt render uses CSS class quiz-take-grading-failed
    per ADR-051.

  ASSUMPTION: MANDATORY_CHAPTER_ID = "ch-01-cpp-refresher", MANDATORY_FIRST_SECTION = "1-1".
"""

from __future__ import annotations

import pathlib
import sqlite3

import pytest

pytestmark = pytest.mark.task("TASK-019")

REPO_ROOT = pathlib.Path(__file__).parent.parent
MANDATORY_CHAPTER_ID = "ch-01-cpp-refresher"
MANDATORY_FIRST_SECTION = "1-1"


# ---------------------------------------------------------------------------
# Helpers — DB rows and test scaffolding
# ---------------------------------------------------------------------------


def _db_rows(db_path: str, sql: str, params=()) -> list[dict]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.execute(sql, params)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def _setup_quiz_with_question(db_path: str, monkeypatch) -> tuple[int, int]:
    """
    Bootstrap DB, create a ready quiz with one question.
    Returns (quiz_id, question_id).
    """
    monkeypatch.setenv("NOTES_DB_PATH", db_path)
    from fastapi.testclient import TestClient  # noqa: PLC0415
    from app.main import app  # noqa: PLC0415
    client = TestClient(app)
    client.get(f"/lecture/{MANDATORY_CHAPTER_ID}")

    client.post(
        f"/lecture/{MANDATORY_CHAPTER_ID}/sections/{MANDATORY_FIRST_SECTION}/quiz",
        follow_redirects=False,
    )
    quizzes = _db_rows(db_path, "SELECT quiz_id FROM quizzes")
    quiz_id = quizzes[0]["quiz_id"]

    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO questions (section_id, prompt, topics, test_suite, preamble) VALUES (?, ?, ?, ?, ?)",
        (
            f"{MANDATORY_CHAPTER_ID}#section-{MANDATORY_FIRST_SECTION}",
            "Implement a stack.",
            "stacks",
            "def test_stack():\n    s = Stack()\n    s.push(1)\n    assert s.pop() == 1\n",
            "",
        ),
    )
    conn.commit()
    qid = conn.execute(
        "SELECT question_id FROM questions ORDER BY question_id DESC LIMIT 1"
    ).fetchone()[0]
    conn.execute(
        "INSERT INTO quiz_questions (quiz_id, question_id, position) VALUES (?, ?, ?)",
        (quiz_id, qid, 1),
    )
    conn.execute("UPDATE quizzes SET status='ready' WHERE quiz_id=?", (quiz_id,))
    conn.commit()
    conn.close()
    return quiz_id, qid


def _create_graded_attempt(
    db_path: str,
    quiz_id: int,
    question_id: int,
    monkeypatch,
    *,
    test_passed: bool = True,
    weak_topics: list[str] | None = None,
    recommended_sections: list[str] | None = None,
    explanation: str = "Correct implementation.",
) -> int:
    """Create a graded Attempt and return attempt_id."""
    if weak_topics is None:
        weak_topics = []
    if recommended_sections is None:
        recommended_sections = []

    monkeypatch.setenv("NOTES_DB_PATH", db_path)
    from app.persistence import (  # noqa: PLC0415
        start_attempt,
        save_attempt_responses,
        submit_attempt,
        save_attempt_test_result,
        mark_attempt_grading,
        save_attempt_grade,
    )
    attempt = start_attempt(quiz_id)
    save_attempt_responses(attempt.attempt_id, {question_id: "class Stack: pass"})
    save_attempt_test_result(
        attempt.attempt_id,
        question_id,
        passed=test_passed,
        status="ran",
        output="ok" if test_passed else "AssertionError",
    )
    submit_attempt(attempt.attempt_id)
    mark_attempt_grading(attempt.attempt_id)
    save_attempt_grade(
        attempt.attempt_id,
        per_question_explanations={question_id: explanation},
        weak_topics=weak_topics,
        recommended_sections=recommended_sections,
    )
    return attempt.attempt_id


def _create_grading_failed_attempt(
    db_path: str,
    quiz_id: int,
    question_id: int,
    monkeypatch,
    *,
    error: str = "aiw run timed out",
) -> int:
    """Create a grading_failed Attempt and return attempt_id."""
    monkeypatch.setenv("NOTES_DB_PATH", db_path)
    from app.persistence import (  # noqa: PLC0415
        start_attempt,
        save_attempt_responses,
        submit_attempt,
        save_attempt_test_result,
        mark_attempt_grading,
        mark_attempt_grading_failed,
    )
    attempt = start_attempt(quiz_id)
    save_attempt_responses(attempt.attempt_id, {question_id: "class Stack: pass"})
    save_attempt_test_result(
        attempt.attempt_id,
        question_id,
        passed=True,
        status="ran",
        output="ok",
    )
    submit_attempt(attempt.attempt_id)
    mark_attempt_grading(attempt.attempt_id)
    mark_attempt_grading_failed(attempt.attempt_id, error=error)
    return attempt.attempt_id


def _get_take_page_html(db_path: str, quiz_id: int, monkeypatch) -> str:
    """GET the take page and return the response HTML text."""
    monkeypatch.setenv("NOTES_DB_PATH", db_path)
    from fastapi.testclient import TestClient  # noqa: PLC0415
    from app.main import app  # noqa: PLC0415
    client = TestClient(app)
    resp = client.get(
        f"/lecture/{MANDATORY_CHAPTER_ID}/sections/{MANDATORY_FIRST_SECTION}/quiz/{quiz_id}/take"
    )
    assert resp.status_code == 200, (
        f"Take page must return 200. Got {resp.status_code}."
    )
    return resp.text


# ===========================================================================
# Boundary: graded and grading_failed render branches present
# ===========================================================================


def test_take_page_graded_renders_score_block(tmp_path, monkeypatch) -> None:
    """
    AC-4 / ADR-051: GET .../take for a graded Attempt renders a .quiz-take-grade
    aggregate block containing the score.

    This is the structural commitment of the graded branch: the score is visible
    in a quiz-take-grade section. Without this block, the learner has no way to
    see their score — the §8 Grade's "aggregate score" facet is not rendered.
    Boundary: graded Attempt renders the aggregate block.
    """
    db_path = str(tmp_path / "score_block.db")
    quiz_id, question_id = _setup_quiz_with_question(db_path, monkeypatch)
    _create_graded_attempt(db_path, quiz_id, question_id, monkeypatch)

    html = _get_take_page_html(db_path, quiz_id, monkeypatch)
    assert "quiz-take-grade" in html, (
        "graded Attempt take page must contain the 'quiz-take-grade' CSS class "
        "for the aggregate score block. ADR-051 / AC-4."
    )


def test_take_page_graded_renders_explanation_block(tmp_path, monkeypatch) -> None:
    """
    AC-4 / ADR-051: GET .../take for a graded Attempt renders the per-Question
    .quiz-take-explanation block with the LLM's explanation text.

    This is the §8 Grade's "per-Question explanation" facet rendered on the page.
    Boundary: explanation is visible in the rendered HTML.
    """
    db_path = str(tmp_path / "explanation_block.db")
    quiz_id, question_id = _setup_quiz_with_question(db_path, monkeypatch)
    _create_graded_attempt(
        db_path, quiz_id, question_id, monkeypatch,
        explanation="Your push/pop implementation handles the edge case correctly.",
    )

    html = _get_take_page_html(db_path, quiz_id, monkeypatch)
    assert "quiz-take-explanation" in html, (
        "graded Attempt take page must contain the 'quiz-take-explanation' CSS class. "
        "ADR-051 / AC-4: per-Question explanation block."
    )
    assert "Your push/pop implementation handles the edge case correctly." in html, (
        "The explanation text must appear in the rendered HTML. ADR-051 / §8 Grade facets."
    )


def test_take_page_graded_renders_correctness_indicator(tmp_path, monkeypatch) -> None:
    """
    AC-4 / ADR-051: GET .../take for a graded Attempt renders a per-Question
    correctness indicator via .quiz-take-question-correct or
    .quiz-take-question-incorrect modifier class.

    The §8 Grade's "per-Question correctness" facet must be visually indicated.
    A test_passed=True → is_correct=True → .quiz-take-question-correct class.
    Boundary: correctness indicator is present in the rendered HTML.
    """
    db_path = str(tmp_path / "correct_indicator.db")
    quiz_id, question_id = _setup_quiz_with_question(db_path, monkeypatch)
    _create_graded_attempt(db_path, quiz_id, question_id, monkeypatch, test_passed=True)

    html = _get_take_page_html(db_path, quiz_id, monkeypatch)
    has_correct = "quiz-take-question-correct" in html
    has_incorrect = "quiz-take-question-incorrect" in html
    assert has_correct or has_incorrect, (
        "graded Attempt take page must render a correctness indicator class "
        "(quiz-take-question-correct or quiz-take-question-incorrect). "
        "ADR-051 / AC-4 / §8 Grade: per-Question correctness facet."
    )


def test_take_page_grading_failed_renders_honest_failure_block(
    tmp_path, monkeypatch
) -> None:
    """
    AC-4 / ADR-051: GET .../take for a grading_failed Attempt renders an honest
    failure block with the .quiz-take-grading-failed class.

    MC-5 / §6: AI failures are visible. The system must surface the failure,
    never fabricate a Grade to cover for it.
    Boundary: grading_failed state renders the honest failure section.
    """
    db_path = str(tmp_path / "fail_block.db")
    quiz_id, question_id = _setup_quiz_with_question(db_path, monkeypatch)
    _create_grading_failed_attempt(db_path, quiz_id, question_id, monkeypatch)

    html = _get_take_page_html(db_path, quiz_id, monkeypatch)
    assert "quiz-take-grading-failed" in html, (
        "grading_failed Attempt take page must contain the 'quiz-take-grading-failed' "
        "CSS class for the honest failure block. ADR-051 / AC-4 / MC-5."
    )


def test_take_page_submitted_render_unchanged(tmp_path, monkeypatch) -> None:
    """
    AC-4 / ADR-051 / ADR-038: GET .../take for a submitted Attempt still renders
    the existing 'submitted' state (no regression). The new graded/grading_failed
    branches must not break the existing submitted-state render.
    Boundary: submitted state regression check.
    """
    db_path = str(tmp_path / "submitted_unchanged.db")
    quiz_id, question_id = _setup_quiz_with_question(db_path, monkeypatch)

    monkeypatch.setenv("NOTES_DB_PATH", db_path)
    from app.persistence import start_attempt, save_attempt_responses, submit_attempt  # noqa: PLC0415
    attempt = start_attempt(quiz_id)
    save_attempt_responses(attempt.attempt_id, {question_id: "class Stack: pass"})
    submit_attempt(attempt.attempt_id)

    html = _get_take_page_html(db_path, quiz_id, monkeypatch)
    # The submitted state should not render the graded block
    assert "quiz-take-grade" not in html, (
        "submitted Attempt must NOT render the quiz-take-grade block. ADR-051 / AC-4."
    )
    # The submitted state should indicate grading is pending
    # (the exact wording is "grading not yet available" per ADR-038, or similar)
    # We test that the key CSS class is absent, not the exact copy (copy is implementation)
    assert "quiz-take-grading-failed" not in html, (
        "submitted Attempt must NOT render the quiz-take-grading-failed block."
    )


def test_take_page_graded_no_submit_form(tmp_path, monkeypatch) -> None:
    """
    AC-4 / ADR-051: graded Attempt take page must NOT contain a submit form.
    A graded Attempt is read-only — no submit button, no <form method='post'>.
    Running tests and submitting are in_progress-only actions (ADR-038, ADR-043).
    Boundary: absence of submit form on graded render.
    """
    db_path = str(tmp_path / "no_form.db")
    quiz_id, question_id = _setup_quiz_with_question(db_path, monkeypatch)
    _create_graded_attempt(db_path, quiz_id, question_id, monkeypatch)

    html = _get_take_page_html(db_path, quiz_id, monkeypatch)
    # The submit form uses method='post' per ADR-038
    # A graded page should not have it
    # We look for a submit button or POST form targeting the take URL
    import re  # noqa: PLC0415
    post_form = re.search(r'<form[^>]+method=["\']post["\']', html, re.IGNORECASE)
    assert not post_form, (
        "graded Attempt take page must NOT have a POST form (submit is in_progress-only). "
        "ADR-051 / AC-4: read-only render for graded Attempts."
    )


def test_take_page_grading_failed_no_fabricated_grade(tmp_path, monkeypatch) -> None:
    """
    AC-4 / ADR-051 / MC-5: grading_failed Attempt take page must NOT contain
    the quiz-take-grade block (no fabricated Grade rendered).

    The system never fabricates a result to cover for a failure (§6 / MC-5).
    Boundary: absence of quiz-take-grade on grading_failed render.
    """
    db_path = str(tmp_path / "no_fabricated.db")
    quiz_id, question_id = _setup_quiz_with_question(db_path, monkeypatch)
    _create_grading_failed_attempt(db_path, quiz_id, question_id, monkeypatch)

    html = _get_take_page_html(db_path, quiz_id, monkeypatch)
    assert "quiz-take-grade" not in html, (
        "grading_failed Attempt take page must NOT contain 'quiz-take-grade'. "
        "ADR-051 / MC-5: no fabricated Grade rendered on grading_failed."
    )


def test_take_page_grading_failed_no_per_question_explanation(
    tmp_path, monkeypatch
) -> None:
    """
    AC-4 / ADR-051 / MC-5: grading_failed Attempt take page must NOT contain
    the .quiz-take-explanation block (no fabricated per-Question explanation).

    On the failure path, attempt_questions.explanation is NULL (ADR-049 / ADR-050
    transactional rollback). The template must not render a fabricated explanation.
    Boundary: absence of explanation block on grading_failed render.
    """
    db_path = str(tmp_path / "no_expl_on_fail.db")
    quiz_id, question_id = _setup_quiz_with_question(db_path, monkeypatch)
    _create_grading_failed_attempt(db_path, quiz_id, question_id, monkeypatch)

    html = _get_take_page_html(db_path, quiz_id, monkeypatch)
    assert "quiz-take-explanation" not in html, (
        "grading_failed Attempt take page must NOT contain 'quiz-take-explanation'. "
        "ADR-051 / MC-5: no per-Question explanation block on grading_failed render."
    )


# ===========================================================================
# Edge: empty lists, weak topics and recommended sections visible
# ===========================================================================


def test_take_page_graded_empty_weak_topics_renders_without_error(
    tmp_path, monkeypatch
) -> None:
    """
    AC-4 / ADR-051: graded Attempt with weak_topics=[] renders without error.
    A perfect Attempt has no Weak Topics — the template must handle an empty list.
    Edge: empty weak_topics list.
    """
    db_path = str(tmp_path / "no_weak_topics.db")
    quiz_id, question_id = _setup_quiz_with_question(db_path, monkeypatch)
    _create_graded_attempt(db_path, quiz_id, question_id, monkeypatch, weak_topics=[])

    html = _get_take_page_html(db_path, quiz_id, monkeypatch)
    # The page must render without error (status 200 is checked inside _get_take_page_html)
    # And must have the grade block
    assert "quiz-take-grade" in html, (
        "graded Attempt with empty weak_topics must still render the quiz-take-grade block."
    )


def test_take_page_graded_renders_weak_topics_when_present(
    tmp_path, monkeypatch
) -> None:
    """
    AC-4 / ADR-051: graded Attempt with weak_topics=['stacks'] renders the
    Weak Topics list in the HTML.
    Edge: non-empty weak_topics visible in the rendered page.
    """
    db_path = str(tmp_path / "weak_topics_visible.db")
    quiz_id, question_id = _setup_quiz_with_question(db_path, monkeypatch)
    _create_graded_attempt(
        db_path, quiz_id, question_id, monkeypatch,
        test_passed=False,
        weak_topics=["stacks"],
        explanation="Your pop() didn't return the last element.",
    )

    html = _get_take_page_html(db_path, quiz_id, monkeypatch)
    assert "stacks" in html, (
        "Weak topic 'stacks' must appear in the rendered HTML for a graded Attempt. "
        "ADR-051 / §8 Grade: Weak Topics facet."
    )


def test_take_page_graded_renders_recommended_sections_when_present(
    tmp_path, monkeypatch
) -> None:
    """
    AC-4 / ADR-051: graded Attempt with recommended_sections renders the Section
    references in the HTML. The links cross-reference Sections via ADR-031's recipe.
    Edge: non-empty recommended_sections visible in the rendered page.
    """
    db_path = str(tmp_path / "recommended_visible.db")
    quiz_id, question_id = _setup_quiz_with_question(db_path, monkeypatch)
    _create_graded_attempt(
        db_path, quiz_id, question_id, monkeypatch,
        test_passed=False,
        weak_topics=["stacks"],
        recommended_sections=["ch-01-cpp-refresher#section-1-1"],
        explanation="Review the stack implementation section.",
    )

    html = _get_take_page_html(db_path, quiz_id, monkeypatch)
    assert "ch-01-cpp-refresher" in html, (
        "Recommended section 'ch-01-cpp-refresher' must appear in the rendered HTML. "
        "ADR-051 / §8 Grade: recommended Sections facet."
    )


def test_take_page_in_progress_render_unchanged(tmp_path, monkeypatch) -> None:
    """
    AC-4 / ADR-051: GET .../take for an in_progress Attempt still renders
    the existing in_progress state (no regression). The new graded/grading_failed
    branches must not break the in_progress render.
    Edge: in_progress state regression check.
    """
    db_path = str(tmp_path / "in_progress_unchanged.db")
    quiz_id, question_id = _setup_quiz_with_question(db_path, monkeypatch)

    monkeypatch.setenv("NOTES_DB_PATH", db_path)
    from app.persistence import start_attempt  # noqa: PLC0415
    attempt = start_attempt(quiz_id)

    html = _get_take_page_html(db_path, quiz_id, monkeypatch)
    # in_progress should not render the grade block
    assert "quiz-take-grade" not in html, (
        "in_progress Attempt must NOT render the quiz-take-grade block. ADR-051."
    )
    assert "quiz-take-grading-failed" not in html, (
        "in_progress Attempt must NOT render the quiz-take-grading-failed block."
    )


# ===========================================================================
# Negative: absence of run-tests button, grading_error detail present
# ===========================================================================


def test_take_page_graded_no_run_tests_button(tmp_path, monkeypatch) -> None:
    """
    AC-4 / ADR-051 / ADR-043: graded Attempt take page must NOT contain a
    "Run tests" button. Running tests is an in_progress-only action.
    Negative: absence of "Run tests" affordance on graded render.
    """
    db_path = str(tmp_path / "no_run_tests.db")
    quiz_id, question_id = _setup_quiz_with_question(db_path, monkeypatch)
    _create_graded_attempt(db_path, quiz_id, question_id, monkeypatch)

    html = _get_take_page_html(db_path, quiz_id, monkeypatch)
    # "Run tests" is the button text per ADR-043 / TASK-017 take-page
    assert "Run tests" not in html, (
        "graded Attempt take page must NOT contain 'Run tests' button. "
        "ADR-051: running tests is in_progress-only."
    )


def test_take_page_grading_failed_grading_error_detail_present(
    tmp_path, monkeypatch
) -> None:
    """
    AC-4 / ADR-051: grading_failed Attempt take page contains the grading_error
    detail text. ADR-051 commits to a collapsible <details> exposing grading_error
    (the author is the learner; honesty over hiding; MC-5's spirit).
    Negative: absence would mean the failure detail is hidden (MC-5 spirit violated).
    """
    db_path = str(tmp_path / "grading_error_detail.db")
    quiz_id, question_id = _setup_quiz_with_question(db_path, monkeypatch)
    error_text = "aiw run returned non-zero: rate limit exceeded"
    _create_grading_failed_attempt(
        db_path, quiz_id, question_id, monkeypatch, error=error_text
    )

    html = _get_take_page_html(db_path, quiz_id, monkeypatch)
    assert error_text in html, (
        f"grading_failed take page must expose the grading_error detail '{error_text}'. "
        "ADR-051: collapsible <details> element exposes grading_error for the author "
        "(honesty over hiding; MC-5's spirit; the author is the learner, single-user)."
    )


def test_take_page_graded_mc5_no_fabricated_grade_text(tmp_path, monkeypatch) -> None:
    """
    AC-4 / ADR-051 / MC-5: graded Attempt take page must not show the 'submitted'
    fallback copy alongside the Grade (the page shows the actual Grade, not the
    'grading not yet available' fallback).

    This tests that the graded branch is actually rendered — the fallback text must
    not appear alongside the Grade block (it would indicate the template branching
    is broken and the submitted-state fallback is leaking into the graded render).
    Negative: submitted-state fallback text absent on graded render.
    """
    db_path = str(tmp_path / "no_fallback.db")
    quiz_id, question_id = _setup_quiz_with_question(db_path, monkeypatch)
    _create_graded_attempt(db_path, quiz_id, question_id, monkeypatch)

    html = _get_take_page_html(db_path, quiz_id, monkeypatch)
    # The submitted-state fallback text (ADR-038 / existing render) must not appear
    # alongside the grade block (it would indicate broken template branching)
    # We check that the grade block IS present (structural) and the fallback is NOT
    assert "quiz-take-grade" in html, (
        "graded Attempt take page must show the quiz-take-grade block."
    )
    # The submitted-state render says "grading not yet available" or equivalent
    # It must be absent from the graded render
    assert "grading not yet available" not in html.lower(), (
        "graded Attempt take page must NOT show the 'grading not yet available' fallback. "
        "MC-5: the system shows the actual Grade, not a placeholder."
    )


# ===========================================================================
# AC-5: CSS namespace in quiz.css
# ===========================================================================


def test_quiz_css_contains_grade_namespace_rules(tmp_path, monkeypatch) -> None:
    """
    AC-5 / ADR-051 / ADR-008: app/static/quiz.css carries the new CSS rules
    under the quiz-take-* namespace:
      .quiz-take-grade, .quiz-take-grade-score, .quiz-take-explanation,
      .quiz-take-question-correct, .quiz-take-question-incorrect,
      .quiz-take-grading-failed

    No new CSS file (ADR-008's per-surface flat file posture).
    No base.css change.
    """
    quiz_css_path = REPO_ROOT / "app" / "static" / "quiz.css"
    assert quiz_css_path.exists(), (
        f"app/static/quiz.css must exist at {quiz_css_path}. "
        "ADR-008 / ADR-051: the grading CSS rules land in this existing file."
    )
    css = quiz_css_path.read_text()

    required_classes = [
        "quiz-take-grade",
        "quiz-take-explanation",
        "quiz-take-question-correct",
        "quiz-take-question-incorrect",
        "quiz-take-grading-failed",
    ]
    missing = [cls for cls in required_classes if cls not in css]
    assert not missing, (
        f"app/static/quiz.css is missing these TASK-019 CSS rules: {missing}. "
        "ADR-051 / AC-5: the grading rules reuse the quiz-take-* namespace (ADR-008); "
        "no new CSS file; no base.css change."
    )


def test_no_new_css_file_for_task019(tmp_path, monkeypatch) -> None:
    """
    AC-5 / ADR-051 / ADR-008: TASK-019 must NOT introduce a new CSS file.
    All grading CSS rules land in app/static/quiz.css per ADR-008's per-surface
    flat file posture.
    Negative: absence of a new grade-specific CSS file.
    """
    static_dir = REPO_ROOT / "app" / "static"
    if not static_dir.exists():
        pytest.skip("app/static/ directory does not exist yet.")

    css_files = list(static_dir.glob("*.css"))
    css_names = [f.name for f in css_files]
    grade_specific_files = [
        name for name in css_names
        if "grade" in name.lower() and name != "quiz.css"
    ]
    assert not grade_specific_files, (
        f"TASK-019 must NOT introduce a new grade-specific CSS file. "
        f"Found: {grade_specific_files!r}. "
        "ADR-051 / ADR-008: all grading CSS rules go in app/static/quiz.css."
    )


def test_base_css_unchanged_by_task019() -> None:
    """
    AC-5 / ADR-051 / ADR-008: app/static/base.css must not contain any
    TASK-019-specific rules (quiz-take-grade / quiz-take-explanation / etc.).
    The grading CSS rules stay in quiz.css, not in base.css.
    Negative: TASK-019 rules absent from base.css.
    """
    base_css_path = REPO_ROOT / "app" / "static" / "base.css"
    if not base_css_path.exists():
        pytest.skip("app/static/base.css does not exist.")

    css = base_css_path.read_text()
    task019_classes = [
        "quiz-take-grade",
        "quiz-take-explanation",
        "quiz-take-question-correct",
        "quiz-take-question-incorrect",
        "quiz-take-grading-failed",
    ]
    leaked = [cls for cls in task019_classes if cls in css]
    assert not leaked, (
        f"base.css must NOT contain TASK-019 grading CSS rules: {leaked!r}. "
        "ADR-051 / ADR-008: grading rules stay in quiz.css."
    )
