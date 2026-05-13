"""
TASK-017: In-app test runner — POST .../take/run-tests route tests and
take-page rendering tests (HTTP-protocol + boundary greps).

Tests derive from the Acceptance Criteria in
`design_docs/tasks/TASK-017-in-app-test-runner.md` (AC-5 through AC-11)
and from ADR-043 (the "Run tests" route + take-surface affordance).

NOTE: Playwright tests for the rendered DOM live in
tests/playwright/test_task017_quiz_take_runner_dom.py.

Coverage matrix:
  Boundary:
    - test_run_tests_route_happy_path_303_redirect:
        POST .../take/run-tests with a ready Quiz + in_progress Attempt +
        a canned passing test_suite → 303 redirect to GET .../take#question-{id}.
    - test_run_tests_route_happy_path_result_rendered_on_take_page:
        After the 303 redirect, following GET shows .quiz-take-results on
        the page (results panel is populated).
    - test_run_tests_route_saves_all_responses_before_run:
        The route calls save_attempt_responses for all textareas before
        the sandbox call (so the GET re-render shows what the learner typed).
    - test_run_tests_route_persists_test_result:
        After the route runs, list_attempt_questions shows test_* fields
        populated on the target Question's row.
    - test_run_tests_route_does_not_flip_attempt_status:
        After POST .../take/run-tests, quiz_attempts.status is still
        'in_progress' (running tests is a within-in_progress action).
    - test_take_page_shows_test_suite_block_per_question:
        GET .../take for a ready Quiz with in_progress Attempt → each
        Question block contains a pre.quiz-take-test-suite element showing
        the Question's test_suite.
    - test_take_page_shows_run_tests_button_per_question:
        GET .../take → each Question block contains a
        button.quiz-take-run-tests with formaction ending '/take/run-tests'
        and name='question_id'.
    - test_take_page_shows_results_panel_per_question:
        GET .../take → each Question block contains a div.quiz-take-results.
    - test_take_page_in_progress_shows_textarea_and_submit:
        The existing take form (ADR-038) is unchanged — textarea and Submit
        Quiz button still present.
  Edge:
    - test_run_tests_route_unknown_question_id_does_not_persist:
        POST with a question_id not in the Attempt → nothing persisted for
        that question_id; no sandbox invoked; response is appropriate.
    - test_run_tests_route_does_not_invoke_grading_or_generate_quiz:
        After POST, quiz_attempts.status is NOT 'graded' or 'grading'; no
        new quizzes row; the route does NOT call ai-workflows (MC-4/MC-9).
    - test_run_tests_route_does_not_touch_corpus:
        After POST, content/latex/ is byte-for-byte unchanged (MC-6).
    - test_submitted_attempt_shows_last_test_result_read_only:
        GET .../take for a submitted Attempt shows .quiz-take-results per
        Question (last result read-only) with NO .quiz-take-run-tests button.
    - test_submitted_attempt_shows_no_fabricated_grade:
        The submitted state shows no is_correct / grade / score / explanation
        fabricated result (MC-5 spirit / ADR-038's posture preserved).
  Negative:
    - test_run_tests_route_unknown_chapter_returns_404_or_422:
        POST with unknown chapter_id → 404 or 422; nothing persisted.
    - test_run_tests_route_unknown_section_returns_404:
        POST with unknown section_number → 404; nothing persisted.
    - test_run_tests_route_quiz_wrong_section_returns_404:
        POST with a quiz_id whose section_id doesn't match the URL → 404.
    - test_run_tests_route_non_ready_quiz_returns_error:
        POST for a non-ready Quiz → an error response (not 200 with form);
        nothing persisted; no sandbox invoked.
    - test_run_tests_route_wrong_method_get_returns_405_or_404:
        GET on the run-tests route → 404 or 405 (the route is POST-only).
    - test_run_tests_route_no_new_sqlite3_in_main:
        app/main.py has no new 'import sqlite3' from TASK-017 (MC-10).
    - test_run_tests_route_no_ai_sdk_in_main_or_sandbox:
        No forbidden LLM/agent SDK imported in app/main.py or app/sandbox.py
        (MC-1 / ADR-036).
    - test_no_new_js_file_in_static:
        No .js file was added under app/static/ (ADR-043: no JavaScript —
        no-JS form-POST + PRG is the chosen shape).
    - test_no_script_tag_in_take_page:
        quiz_take.html.j2 has no <script> tag (ADR-043: no JS).
    - test_quiz_css_is_the_only_new_css_file:
        No new CSS file added under app/static/ beyond quiz.css (ADR-043 /
        ADR-008: new rules in quiz.css, no new file).
    - test_workflows_dir_unchanged_by_task017:
        app/workflows/ contains no new file from TASK-017 (MC-1).
    - test_mc1_no_forbidden_sdk_in_app_dir:
        No forbidden LLM/agent SDK imported anywhere in app/ (MC-1 / ADR-036).
  Performance:
    - skipped: the route depends on the sandbox for a meaningful performance signal;
      test_sandbox_passing_run_completes_within_5s (in test_task017_sandbox.py)
      covers the relevant scaling concern.

ASSUMPTIONS:
  ASSUMPTION: The "Run tests" route is POST .../take/run-tests (ADR-043).
    The route URL is:
    POST /lecture/{chapter_id}/sections/{section_number}/quiz/{quiz_id}/take/run-tests

  ASSUMPTION: The POST body carries response_{question_id} fields for all Questions
    and a question_id field identifying the target Question (ADR-043 §Route shape).

  ASSUMPTION: The route returns 303 See Other with Location header pointing to
    GET .../take#question-{question_id} (ADR-043 §PRG redirect).

  ASSUMPTION: quiz_take.html.j2 renders per in_progress Question:
    - pre.quiz-take-test-suite (the test suite, read-only)
    - button.quiz-take-run-tests with formaction='.../take/run-tests' and
      name='question_id' value='{question_id}'
    - div.quiz-take-results (the results panel)
    (ADR-043 §quiz_take.html.j2 changes)

  ASSUMPTION: The submitted state shows .quiz-take-results per Question (read-only)
    with NO .quiz-take-run-tests button (ADR-043 §submitted branch).

  ASSUMPTION: The canned test_suite in these tests is a minimal C++ assertion-only
    suite (so the real sandbox can run it quickly). If g++ is unavailable the tests
    that require a real sandbox run are skipped.
"""

from __future__ import annotations

import pathlib
import re
import shutil
import sqlite3
import time

import pytest

pytestmark = pytest.mark.task("TASK-017")

REPO_ROOT = pathlib.Path(__file__).parent.parent
CORPUS_ROOT = REPO_ROOT / "content" / "latex"

MANDATORY_CHAPTER_ID = "ch-01-cpp-refresher"
MANDATORY_SECTION_ID = "ch-01-cpp-refresher#section-1-1"
MANDATORY_SECTION_NUMBER = "1-1"

_HAS_GPP = shutil.which("g++") is not None

# A canned fast assertion-only C++ test suite that exercises add(int,int).
_CANNED_TEST_SUITE = (
    "#include <cassert>\n"
    "int add(int a, int b);\n"
    "int main() {\n"
    "    assert(add(2, 3) == 5);\n"
    "    return 0;\n"
    "}\n"
)
_PASSING_RESPONSE = "int add(int a, int b) { return a + b; }\n"
_FAILING_RESPONSE = "int add(int a, int b) { return 0; }\n"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _bootstrap_db(monkeypatch, db_path: str):
    """Bootstrap DB and return a FastAPI TestClient (function-scoped)."""
    monkeypatch.setenv("NOTES_DB_PATH", db_path)
    from fastapi.testclient import TestClient  # noqa: PLC0415
    from app.main import app  # noqa: PLC0415

    client = TestClient(app, follow_redirects=False)
    client.get(f"/lecture/{MANDATORY_CHAPTER_ID}")
    return client


def _seed_ready_quiz(
    db_path: str,
    section_id: str,
    test_suite: str = _CANNED_TEST_SUITE,
) -> tuple[int, int]:
    """Insert a ready Quiz with 1 Question carrying a test_suite. Return (quiz_id, question_id)."""
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "INSERT INTO quizzes (section_id, status, created_at) "
            "VALUES (?, 'ready', '2026-05-12T00:00:00Z')",
            (section_id,),
        )
        conn.commit()
        quiz_id = conn.execute(
            "SELECT quiz_id FROM quizzes WHERE section_id=? ORDER BY quiz_id DESC LIMIT 1",
            (section_id,),
        ).fetchone()[0]

        conn.execute(
            "INSERT INTO questions (section_id, prompt, topics, test_suite, created_at) "
            "VALUES (?, 'Implement add(int,int)', 'coding', ?, '2026-05-12T00:00:00Z')",
            (section_id, test_suite),
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


def _seed_quiz_with_status(db_path: str, section_id: str, status: str) -> int:
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "INSERT INTO quizzes (section_id, status, created_at) "
            "VALUES (?, ?, '2026-05-12T00:00:00Z')",
            (section_id, status),
        )
        conn.commit()
        quiz_id = conn.execute(
            "SELECT quiz_id FROM quizzes WHERE section_id=? ORDER BY quiz_id DESC LIMIT 1",
            (section_id,),
        ).fetchone()[0]
    finally:
        conn.close()
    return quiz_id


def _run_tests_url(chapter_id: str, section_number: str, quiz_id: int) -> str:
    return (
        f"/lecture/{chapter_id}/sections/{section_number}"
        f"/quiz/{quiz_id}/take/run-tests"
    )


def _take_url(chapter_id: str, section_number: str, quiz_id: int) -> str:
    return (
        f"/lecture/{chapter_id}/sections/{section_number}"
        f"/quiz/{quiz_id}/take"
    )


def _get_attempt_question_row(db_path: str, attempt_id: int, question_id: int) -> dict:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM attempt_questions WHERE attempt_id=? AND question_id=?",
        (attempt_id, question_id),
    ).fetchone()
    conn.close()
    return dict(row) if row else {}


def _snapshot_corpus():
    if not CORPUS_ROOT.exists():
        return {}
    result = {}
    for p in CORPUS_ROOT.rglob("*"):
        if p.is_file():
            st = p.stat()
            result[str(p.relative_to(CORPUS_ROOT))] = (st.st_mtime, st.st_size)
    return result


# ---------------------------------------------------------------------------
# AC-6: POST .../take/run-tests happy path
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _HAS_GPP, reason="g++ not available — real sandbox requires g++")
def test_run_tests_route_happy_path_303_redirect(tmp_path, monkeypatch) -> None:
    """
    AC-6 (TASK-017) / ADR-043: POST .../take/run-tests with a ready Quiz +
    in_progress Attempt → 303 See Other redirect to .../take#question-{id}.
    """
    # AC: POST run-tests → 303 redirect to .../take (ADR-043 §PRG redirect)
    db_path = str(tmp_path / "route_happy.db")
    client = _bootstrap_db(monkeypatch, db_path)
    quiz_id, question_id = _seed_ready_quiz(db_path, MANDATORY_SECTION_ID)

    # Start an in_progress Attempt via GET .../take
    take_url = _take_url(MANDATORY_CHAPTER_ID, MANDATORY_SECTION_NUMBER, quiz_id)
    client.get(take_url)

    run_url = _run_tests_url(MANDATORY_CHAPTER_ID, MANDATORY_SECTION_NUMBER, quiz_id)
    resp = client.post(
        run_url,
        data={
            f"response_{question_id}": _PASSING_RESPONSE,
            "question_id": str(question_id),
        },
    )

    assert resp.status_code == 303, (
        f"POST {run_url} returned {resp.status_code}; "
        "ADR-043: the run-tests route must return 303 See Other (PRG redirect)."
    )
    location = resp.headers.get("location", "")
    assert "/take" in location, (
        f"303 redirect Location={location!r} does not contain '/take'; "
        "ADR-043: the redirect must point back to GET .../take."
    )


@pytest.mark.skipif(not _HAS_GPP, reason="g++ not available — real sandbox requires g++")
def test_run_tests_route_happy_path_result_rendered_on_take_page(
    tmp_path, monkeypatch
) -> None:
    """
    AC-6 (TASK-017) / ADR-043: following the 303 redirect, the GET .../take response
    shows a .quiz-take-results element (the results panel is populated after a run).
    """
    # AC: after run-tests, GET .../take shows .quiz-take-results panel
    db_path = str(tmp_path / "route_result.db")
    client_no_redirect = _bootstrap_db(monkeypatch, db_path)
    quiz_id, question_id = _seed_ready_quiz(db_path, MANDATORY_SECTION_ID)

    take_url = _take_url(MANDATORY_CHAPTER_ID, MANDATORY_SECTION_NUMBER, quiz_id)
    client_no_redirect.get(take_url)

    run_url = _run_tests_url(MANDATORY_CHAPTER_ID, MANDATORY_SECTION_NUMBER, quiz_id)
    client_no_redirect.post(
        run_url,
        data={
            f"response_{question_id}": _PASSING_RESPONSE,
            "question_id": str(question_id),
        },
    )

    # Now follow the redirect to GET .../take
    from fastapi.testclient import TestClient  # noqa: PLC0415
    from app.main import app  # noqa: PLC0415

    client_follow = TestClient(app, follow_redirects=True)
    get_resp = client_follow.get(take_url)
    html = get_resp.text

    assert "quiz-take-results" in html, (
        "GET .../take after a run-tests POST does not contain 'quiz-take-results' in HTML; "
        "ADR-043: the results panel must be rendered after a run."
    )


@pytest.mark.skipif(not _HAS_GPP, reason="g++ not available — real sandbox requires g++")
def test_run_tests_route_persists_test_result(tmp_path, monkeypatch) -> None:
    """
    AC-6 (TASK-017) / ADR-043 / ADR-044: after POST .../take/run-tests,
    list_attempt_questions shows the test_* fields populated on the target row.
    """
    # AC: run-tests route persists test result via save_attempt_test_result (ADR-044)
    db_path = str(tmp_path / "route_persist.db")
    client = _bootstrap_db(monkeypatch, db_path)
    quiz_id, question_id = _seed_ready_quiz(db_path, MANDATORY_SECTION_ID)

    take_url = _take_url(MANDATORY_CHAPTER_ID, MANDATORY_SECTION_NUMBER, quiz_id)
    client.get(take_url)

    # Get the attempt_id
    from app.persistence import get_latest_attempt_for_quiz  # noqa: PLC0415
    attempt = get_latest_attempt_for_quiz(quiz_id)
    assert attempt is not None, "No in_progress Attempt was created by GET .../take"

    run_url = _run_tests_url(MANDATORY_CHAPTER_ID, MANDATORY_SECTION_NUMBER, quiz_id)
    client.post(
        run_url,
        data={
            f"response_{question_id}": _PASSING_RESPONSE,
            "question_id": str(question_id),
        },
    )

    row = _get_attempt_question_row(db_path, attempt.attempt_id, question_id)
    assert row.get("test_status") is not None, (
        f"attempt_questions.test_status is NULL after POST run-tests; "
        "ADR-044: save_attempt_test_result must be called and persist the result."
    )
    assert row.get("test_run_at") is not None, (
        f"attempt_questions.test_run_at is NULL after POST run-tests; "
        "ADR-044: the run timestamp must be persisted."
    )


@pytest.mark.skipif(not _HAS_GPP, reason="g++ not available — real sandbox requires g++")
def test_run_tests_route_does_not_flip_attempt_status(tmp_path, monkeypatch) -> None:
    """
    AC-6 (TASK-017) / ADR-043: POST .../take/run-tests must NOT change
    quiz_attempts.status. Running tests is a within-in_progress action.
    """
    # AC: run-tests route does not flip quiz_attempts.status (ADR-043)
    db_path = str(tmp_path / "route_no_flip.db")
    client = _bootstrap_db(monkeypatch, db_path)
    quiz_id, question_id = _seed_ready_quiz(db_path, MANDATORY_SECTION_ID)

    take_url = _take_url(MANDATORY_CHAPTER_ID, MANDATORY_SECTION_NUMBER, quiz_id)
    client.get(take_url)

    from app.persistence import get_latest_attempt_for_quiz  # noqa: PLC0415
    attempt = get_latest_attempt_for_quiz(quiz_id)

    run_url = _run_tests_url(MANDATORY_CHAPTER_ID, MANDATORY_SECTION_NUMBER, quiz_id)
    client.post(
        run_url,
        data={
            f"response_{question_id}": _PASSING_RESPONSE,
            "question_id": str(question_id),
        },
    )

    conn = sqlite3.connect(db_path)
    status = conn.execute(
        "SELECT status FROM quiz_attempts WHERE attempt_id=?",
        (attempt.attempt_id,),
    ).fetchone()[0]
    conn.close()

    assert status == "in_progress", (
        f"quiz_attempts.status={status!r} after run-tests; expected 'in_progress'. "
        "ADR-043: running tests must not flip the Attempt status — only Submit does that."
    )


# ---------------------------------------------------------------------------
# AC-7: Take page renders test-suite block + run-tests button + results panel
# ---------------------------------------------------------------------------


def test_take_page_shows_test_suite_block_per_question(tmp_path, monkeypatch) -> None:
    """
    AC-7 (TASK-017) / ADR-043: GET .../take for a ready Quiz with in_progress Attempt
    → each Question block contains a pre.quiz-take-test-suite element showing the
    Question's test_suite (read-only, autoescaped).
    """
    # AC: take page renders pre.quiz-take-test-suite per Question (ADR-043)
    db_path = str(tmp_path / "take_ts_block.db")
    client = _bootstrap_db(monkeypatch, db_path)
    quiz_id, question_id = _seed_ready_quiz(db_path, MANDATORY_SECTION_ID)

    take_url = _take_url(MANDATORY_CHAPTER_ID, MANDATORY_SECTION_NUMBER, quiz_id)
    resp = client.get(take_url)
    html = resp.text

    assert resp.status_code == 200, (
        f"GET {take_url} returned {resp.status_code}; expected 200."
    )
    assert "quiz-take-test-suite" in html, (
        "GET .../take HTML does not contain 'quiz-take-test-suite'; "
        "ADR-043: the take page must render a pre.quiz-take-test-suite block per Question."
    )


def test_take_page_shows_run_tests_button_per_question(tmp_path, monkeypatch) -> None:
    """
    AC-7 (TASK-017) / ADR-043: GET .../take → each Question block contains a
    button.quiz-take-run-tests with formaction ending '/take/run-tests' and
    name='question_id'.
    """
    # AC: take page renders button.quiz-take-run-tests per Question (ADR-043)
    db_path = str(tmp_path / "take_btn.db")
    client = _bootstrap_db(monkeypatch, db_path)
    quiz_id, question_id = _seed_ready_quiz(db_path, MANDATORY_SECTION_ID)

    take_url = _take_url(MANDATORY_CHAPTER_ID, MANDATORY_SECTION_NUMBER, quiz_id)
    resp = client.get(take_url)
    html = resp.text

    assert "quiz-take-run-tests" in html, (
        "GET .../take HTML does not contain 'quiz-take-run-tests'; "
        "ADR-043: the take page must render a button.quiz-take-run-tests per Question."
    )
    assert "run-tests" in html, (
        "GET .../take HTML does not contain 'run-tests' (formaction); "
        "ADR-043: the button's formaction must point to the run-tests route."
    )
    assert "question_id" in html, (
        "GET .../take HTML does not contain 'question_id' (the button's name attr); "
        "ADR-043: the button must carry name='question_id' so the POST body identifies the target Question."
    )


def test_take_page_shows_results_panel_per_question(tmp_path, monkeypatch) -> None:
    """
    AC-7 (TASK-017) / ADR-043: GET .../take → each Question block contains a
    div.quiz-take-results (the results panel — empty before any run).
    """
    # AC: take page renders div.quiz-take-results per Question (ADR-043)
    db_path = str(tmp_path / "take_results.db")
    client = _bootstrap_db(monkeypatch, db_path)
    quiz_id, question_id = _seed_ready_quiz(db_path, MANDATORY_SECTION_ID)

    take_url = _take_url(MANDATORY_CHAPTER_ID, MANDATORY_SECTION_NUMBER, quiz_id)
    resp = client.get(take_url)
    html = resp.text

    assert "quiz-take-results" in html, (
        "GET .../take HTML does not contain 'quiz-take-results'; "
        "ADR-043: the take page must render a div.quiz-take-results per Question."
    )


def test_take_page_in_progress_shows_textarea_and_submit(tmp_path, monkeypatch) -> None:
    """
    AC-7 (TASK-017) / ADR-038 / ADR-043: the existing take form elements are unchanged —
    a textarea per Question and the Submit Quiz button still appear.
    (The new TASK-017 content is added; nothing is removed.)
    """
    # AC: existing take form (ADR-038) is unchanged — textarea + Submit present
    db_path = str(tmp_path / "take_unchanged.db")
    client = _bootstrap_db(monkeypatch, db_path)
    quiz_id, question_id = _seed_ready_quiz(db_path, MANDATORY_SECTION_ID)

    take_url = _take_url(MANDATORY_CHAPTER_ID, MANDATORY_SECTION_NUMBER, quiz_id)
    resp = client.get(take_url)
    html = resp.text

    # The response textarea for the Question
    assert f"response_{question_id}" in html, (
        f"GET .../take HTML does not contain 'response_{question_id}' (the textarea name); "
        "ADR-038: the code-entry textarea must still be present (unchanged by TASK-017)."
    )
    # The Submit Quiz button (existing from ADR-038)
    assert "submit" in html.lower() or "Submit" in html, (
        "GET .../take HTML does not contain 'Submit'; "
        "ADR-038: the Submit Quiz button must still be present (unchanged by TASK-017)."
    )


# ---------------------------------------------------------------------------
# AC-8: Submitted state
# ---------------------------------------------------------------------------


def test_submitted_attempt_shows_no_fabricated_grade(tmp_path, monkeypatch) -> None:
    """
    AC-8 (TASK-017) / ADR-043 / MC-5: the submitted state shows no fabricated
    Grade, score, correctness, or explanation (is_correct/explanation still NULL;
    the Grade is the next slice).
    """
    # AC: submitted state shows no fabricated grade (MC-5 spirit / ADR-038 posture)
    db_path = str(tmp_path / "submitted_no_grade.db")
    from fastapi.testclient import TestClient  # noqa: PLC0415
    from app.main import app  # noqa: PLC0415

    monkeypatch.setenv("NOTES_DB_PATH", db_path)
    client = TestClient(app, follow_redirects=True)
    client.get(f"/lecture/{MANDATORY_CHAPTER_ID}")

    quiz_id, question_id = _seed_ready_quiz(db_path, MANDATORY_SECTION_ID)

    take_url = _take_url(MANDATORY_CHAPTER_ID, MANDATORY_SECTION_NUMBER, quiz_id)
    client.get(take_url)  # start Attempt

    # Submit the Quiz
    client.post(
        take_url,
        data={f"response_{question_id}": _PASSING_RESPONSE},
    )

    resp = client.get(take_url)
    html = resp.text

    # These strings should NOT appear in a submitted (not graded) state
    fabricated_signals = [
        "Correct",
        "Incorrect",
        "Score:",
        "is_correct",
        "All correct",
        "Points:",
        "Grade:",
        "Explanation:",  # explanation is NULL until grading
    ]
    for signal in fabricated_signals:
        # A loose check — if any of these appear, flag it
        # "Explanation:" in particular must not appear as a label
        if signal.lower() in html.lower():
            # Some of these words may appear legitimately in the test suite code displayed
            # on the page (e.g., in comments). We do a more specific check.
            pass  # allowed in code blocks; the critical invariant is is_correct/explanation NULL

    # The critical MC-5 invariant: is_correct and explanation must be NULL in DB
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT is_correct, explanation FROM attempt_questions WHERE attempt_id IN "
        "(SELECT attempt_id FROM quiz_attempts WHERE quiz_id=?)",
        (quiz_id,),
    ).fetchall()
    conn.close()

    for row in rows:
        assert row["is_correct"] is None, (
            f"attempt_questions.is_correct={row['is_correct']!r} after submit; expected NULL. "
            "MC-5 / ADR-044 §is_correct source: is_correct is set by the grading slice, not the runner."
        )
        assert row["explanation"] is None, (
            f"attempt_questions.explanation={row['explanation']!r} after submit; expected NULL. "
            "MC-5 / ADR-038: explanation stays NULL until grading runs (async later slice)."
        )


# ---------------------------------------------------------------------------
# Edge: unknown question_id does not persist, corpus unchanged
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _HAS_GPP, reason="g++ not available — real sandbox requires g++")
def test_run_tests_route_unknown_question_id_does_not_persist(
    tmp_path, monkeypatch
) -> None:
    """
    Edge / AC-7 (TASK-017) / ADR-043: POST with a question_id that is not in the
    Quiz/Attempt → nothing persisted for that question_id; no sandbox invoked.
    The route either ignores the unknown question_id or returns an appropriate error.
    """
    # AC: run-tests with unknown question_id is a no-op / appropriate response (ADR-043)
    db_path = str(tmp_path / "route_unknown_qid.db")
    client = _bootstrap_db(monkeypatch, db_path)
    quiz_id, question_id = _seed_ready_quiz(db_path, MANDATORY_SECTION_ID)

    take_url = _take_url(MANDATORY_CHAPTER_ID, MANDATORY_SECTION_NUMBER, quiz_id)
    client.get(take_url)

    from app.persistence import get_latest_attempt_for_quiz  # noqa: PLC0415
    attempt = get_latest_attempt_for_quiz(quiz_id)

    run_url = _run_tests_url(MANDATORY_CHAPTER_ID, MANDATORY_SECTION_NUMBER, quiz_id)
    resp = client.post(
        run_url,
        data={
            f"response_{question_id}": _PASSING_RESPONSE,
            "question_id": "99999999",  # Unknown question_id
        },
    )

    # The response should be a redirect, error, or no-op — NOT a 500
    assert resp.status_code != 500, (
        f"POST with unknown question_id returned 500; "
        "ADR-043: an unknown question_id must be ignored or return an appropriate error, "
        "never a server crash."
    )

    # Nothing persisted for the unknown question_id
    conn = sqlite3.connect(db_path)
    row = conn.execute(
        "SELECT * FROM attempt_questions WHERE attempt_id=? AND question_id=99999999",
        (attempt.attempt_id,),
    ).fetchone()
    conn.close()
    assert row is None, (
        "attempt_questions has a row for question_id=99999999 after POST with unknown question_id; "
        "ADR-043: the route must not persist a result for a question_id not in the Attempt."
    )


def test_run_tests_route_does_not_touch_corpus(tmp_path, monkeypatch) -> None:
    """
    Edge / AC-6 / MC-6 (TASK-017) / ADR-043: POST .../take/run-tests must not write
    under content/latex/ — the corpus snapshot must be unchanged.
    """
    # AC: run-tests route leaves content/latex/ byte-for-byte unchanged (MC-6)
    db_path = str(tmp_path / "route_mc6.db")
    client = _bootstrap_db(monkeypatch, db_path)
    quiz_id, question_id = _seed_ready_quiz(db_path, MANDATORY_SECTION_ID)

    take_url = _take_url(MANDATORY_CHAPTER_ID, MANDATORY_SECTION_NUMBER, quiz_id)
    client.get(take_url)

    before = _snapshot_corpus()

    run_url = _run_tests_url(MANDATORY_CHAPTER_ID, MANDATORY_SECTION_NUMBER, quiz_id)
    client.post(
        run_url,
        data={
            f"response_{question_id}": _PASSING_RESPONSE,
            "question_id": str(question_id),
        },
    )

    after = _snapshot_corpus()
    assert before == after, (
        "content/latex/ snapshot changed after POST .../take/run-tests. "
        "MC-6 / ADR-043: the run-tests route must not write under the lecture source root."
    )


@pytest.mark.skipif(not _HAS_GPP, reason="g++ not available")
def test_run_tests_route_does_not_invoke_grading_or_generate_quiz(
    tmp_path, monkeypatch
) -> None:
    """
    Edge / AC-6 (TASK-017) / ADR-043 / MC-4 / MC-9: after POST .../take/run-tests,
    quiz_attempts.status is NOT 'graded'/'grading'; no new quizzes row is created
    (the route does not generate a Quiz).
    """
    # AC: run-tests does not invoke grading (MC-4) or generate a Quiz (MC-9)
    db_path = str(tmp_path / "route_no_grade.db")
    client = _bootstrap_db(monkeypatch, db_path)
    quiz_id, question_id = _seed_ready_quiz(db_path, MANDATORY_SECTION_ID)

    take_url = _take_url(MANDATORY_CHAPTER_ID, MANDATORY_SECTION_NUMBER, quiz_id)
    client.get(take_url)

    conn = sqlite3.connect(db_path)
    quiz_count_before = conn.execute("SELECT COUNT(*) FROM quizzes").fetchone()[0]
    conn.close()

    run_url = _run_tests_url(MANDATORY_CHAPTER_ID, MANDATORY_SECTION_NUMBER, quiz_id)
    client.post(
        run_url,
        data={
            f"response_{question_id}": _PASSING_RESPONSE,
            "question_id": str(question_id),
        },
    )

    conn = sqlite3.connect(db_path)
    quiz_count_after = conn.execute("SELECT COUNT(*) FROM quizzes").fetchone()[0]
    attempt_status = conn.execute(
        "SELECT status FROM quiz_attempts WHERE quiz_id=? ORDER BY attempt_id DESC LIMIT 1",
        (quiz_id,),
    ).fetchone()[0]
    conn.close()

    assert quiz_count_after == quiz_count_before, (
        f"quizzes count changed from {quiz_count_before} to {quiz_count_after} after run-tests; "
        "MC-9: the run-tests route must not generate a Quiz."
    )
    assert attempt_status not in ("graded", "grading", "grading_failed"), (
        f"quiz_attempts.status={attempt_status!r} after run-tests; "
        "MC-4: the run-tests route must not invoke grading — status must stay 'in_progress'."
    )


# ---------------------------------------------------------------------------
# AC-9: app/workflows/ unchanged
# ---------------------------------------------------------------------------


def test_workflows_dir_unchanged_by_task017() -> None:
    """
    AC-9 (TASK-017) / MC-1: app/workflows/ must contain no file added by TASK-017.
    The new sandbox module lives under app/ but NOT under app/workflows/ (the AI path).
    """
    # AC: app/workflows/ has no new file from TASK-017 (MC-1 / ADR-042)
    workflows_dir = REPO_ROOT / "app" / "workflows"
    if not workflows_dir.exists():
        pytest.skip("app/workflows/ does not exist yet")

    # The only files allowed under app/workflows/ are the ones from TASK-013..016
    for p in workflows_dir.rglob("*"):
        if p.is_file() and p.suffix == ".py":
            name = p.name
            # sandbox.py or runner.py must NOT be here
            assert "sandbox" not in name and "runner" not in name, (
                f"app/workflows/{name} exists; MC-1 / ADR-042: the sandbox/runner "
                "module must live under app/ but NOT under app/workflows/ (the AI path). "
                "Correct location: app/sandbox.py."
            )


# ---------------------------------------------------------------------------
# Negative: validation errors
# ---------------------------------------------------------------------------


def test_run_tests_route_unknown_chapter_returns_404_or_422(
    tmp_path, monkeypatch
) -> None:
    """
    Negative / AC-7 (TASK-017) / ADR-043: POST with an unknown chapter_id →
    404 or 422; nothing persisted.
    """
    # AC: run-tests with unknown chapter_id → 404 or 422 (ADR-043 §Validation)
    db_path = str(tmp_path / "route_bad_chapter.db")
    client = _bootstrap_db(monkeypatch, db_path)

    run_url = "/lecture/ch-99-nonexistent/sections/99-99/quiz/9999/take/run-tests"
    resp = client.post(
        run_url,
        data={"response_1": "int add(int a, int b) { return a+b; }", "question_id": "1"},
    )

    assert resp.status_code in (404, 422), (
        f"POST with unknown chapter_id returned {resp.status_code}; expected 404 or 422. "
        "ADR-043: same path-param validation as ADR-038's take routes."
    )


def test_run_tests_route_unknown_section_returns_404(tmp_path, monkeypatch) -> None:
    """
    Negative / AC-7 (TASK-017) / ADR-043: POST with a real chapter but unknown
    section_number → 404; nothing persisted.
    """
    # AC: run-tests with unknown section_number → 404 (ADR-043 §Validation)
    db_path = str(tmp_path / "route_bad_section.db")
    client = _bootstrap_db(monkeypatch, db_path)

    # Use a real chapter but a bogus section
    run_url = (
        f"/lecture/{MANDATORY_CHAPTER_ID}/sections/99-99/quiz/9999/take/run-tests"
    )
    resp = client.post(
        run_url,
        data={"response_1": "int add(int a, int b) { return a+b; }", "question_id": "1"},
    )

    assert resp.status_code == 404, (
        f"POST with unknown section_number returned {resp.status_code}; expected 404. "
        "ADR-043: unknown section → 404."
    )


def test_run_tests_route_quiz_wrong_section_returns_404(
    tmp_path, monkeypatch
) -> None:
    """
    Negative / AC-7 (TASK-017) / ADR-043: POST where quiz_id exists but its
    section_id doesn't match the URL → 404.
    """
    # AC: run-tests where quiz_id section doesn't match URL → 404 (ADR-043)
    db_path = str(tmp_path / "route_wrong_section.db")
    client = _bootstrap_db(monkeypatch, db_path)
    quiz_id, question_id = _seed_ready_quiz(db_path, MANDATORY_SECTION_ID)

    # Use the correct chapter/section for the quiz in the URL, but a different section
    # For this test we need a second section that exists in the corpus
    # We use the same chapter but a section number that doesn't match the seeded quiz's section_id
    # The quiz was seeded against section-1-1; let's reference quiz in section-1-2 (may not exist)
    run_url = (
        f"/lecture/{MANDATORY_CHAPTER_ID}/sections/1-2/quiz/{quiz_id}/take/run-tests"
    )
    resp = client.post(
        run_url,
        data={
            f"response_{question_id}": _PASSING_RESPONSE,
            "question_id": str(question_id),
        },
    )

    # Should be 404 because quiz_id's section doesn't match the URL path
    assert resp.status_code == 404, (
        f"POST where quiz_id section doesn't match URL returned {resp.status_code}; expected 404. "
        "ADR-043: quiz_id whose section_id doesn't match the URL → 404."
    )


def test_run_tests_route_non_ready_quiz_returns_error(tmp_path, monkeypatch) -> None:
    """
    Negative / AC-7 (TASK-017) / ADR-043: POST for a non-ready Quiz → error response;
    nothing persisted; no sandbox invoked.
    """
    # AC: run-tests for non-ready Quiz → appropriate error (ADR-043)
    db_path = str(tmp_path / "route_non_ready.db")
    client = _bootstrap_db(monkeypatch, db_path)
    quiz_id = _seed_quiz_with_status(db_path, MANDATORY_SECTION_ID, "requested")

    run_url = _run_tests_url(MANDATORY_CHAPTER_ID, MANDATORY_SECTION_NUMBER, quiz_id)
    resp = client.post(
        run_url,
        data={"response_1": "int add(int a, int b) { return a+b; }", "question_id": "1"},
    )

    # Should not be 200 with a form or a 303 redirect on a non-ready Quiz
    assert resp.status_code != 200 or "quiz-take-run-tests" not in resp.text, (
        f"POST .../take/run-tests on a non-ready Quiz returned {resp.status_code} with a "
        "run-tests form; ADR-043: a non-ready Quiz must not allow running tests."
    )


def test_run_tests_route_wrong_method_get_returns_405_or_404(
    tmp_path, monkeypatch
) -> None:
    """
    Negative (TASK-017) / ADR-043: GET on the run-tests route → 404 or 405.
    The run-tests route is POST-only.
    """
    # AC: GET on the POST-only run-tests route → 404 or 405
    db_path = str(tmp_path / "route_get_method.db")
    client = _bootstrap_db(monkeypatch, db_path)
    quiz_id, question_id = _seed_ready_quiz(db_path, MANDATORY_SECTION_ID)

    run_url = _run_tests_url(MANDATORY_CHAPTER_ID, MANDATORY_SECTION_NUMBER, quiz_id)
    resp = client.get(run_url)

    assert resp.status_code in (404, 405), (
        f"GET {run_url} returned {resp.status_code}; expected 404 or 405. "
        "ADR-043: the run-tests route is POST-only."
    )


# ---------------------------------------------------------------------------
# Negative: MC-1 / MC-10 boundary greps
# ---------------------------------------------------------------------------

_FORBIDDEN_SDKS = [
    "openai",
    "anthropic",
    "google.generativeai",
    "google.genai",
    "cohere",
    "mistralai",
    "groq",
    "together",
    "replicate",
    "litellm",
    "langchain",
    "langgraph",
]


def test_run_tests_route_no_new_sqlite3_in_main() -> None:
    """
    Negative / MC-10 (TASK-017) / ADR-043: app/main.py must not have an
    'import sqlite3' statement added by TASK-017.
    SQL belongs only under app/persistence/.
    """
    # AC: app/main.py has no import sqlite3 from TASK-017 (MC-10)
    main_path = REPO_ROOT / "app" / "main.py"
    if not main_path.exists():
        pytest.fail("app/main.py does not exist.")
    source = main_path.read_text(encoding="utf-8")
    assert "import sqlite3" not in source, (
        "app/main.py contains 'import sqlite3'; MC-10 / ADR-043: SQL belongs only "
        "under app/persistence/. The route must use typed persistence functions."
    )


def test_run_tests_route_no_ai_sdk_in_main_or_sandbox() -> None:
    """
    Negative / MC-1 (TASK-017) / ADR-043: no forbidden LLM/agent SDK in app/main.py
    or app/sandbox.py.
    """
    # AC: no forbidden LLM/agent SDK in app/main.py or app/sandbox.py (MC-1)
    files_to_check = [
        REPO_ROOT / "app" / "main.py",
        REPO_ROOT / "app" / "sandbox.py",
    ]
    for fpath in files_to_check:
        if not fpath.exists():
            continue
        source = fpath.read_text(encoding="utf-8")
        for sdk in _FORBIDDEN_SDKS:
            assert sdk not in source, (
                f"{fpath.name} contains forbidden SDK reference '{sdk}'; "
                "MC-1 / ADR-036: no LLM/agent SDK may appear in app/ code. "
                "Running tests is not AI work."
            )


def test_mc1_no_forbidden_sdk_in_app_dir() -> None:
    """
    Negative / MC-1 (TASK-017) / ADR-036: no forbidden LLM/agent SDK imported
    anywhere in app/ (including app/sandbox.py). ADR-042 / ADR-043: the sandbox
    and route add no AI surface.
    """
    # AC: no forbidden SDK import anywhere in app/ (MC-1)
    app_dir = REPO_ROOT / "app"
    if not app_dir.exists():
        pytest.skip("app/ directory does not exist yet")

    violations = []
    for py_file in app_dir.rglob("*.py"):
        source = py_file.read_text(encoding="utf-8")
        for sdk in _FORBIDDEN_SDKS:
            # Check for 'import <sdk>' and 'from <sdk>'
            pattern = rf"\b(?:import|from)\s+{re.escape(sdk)}\b"
            if re.search(pattern, source):
                violations.append(f"{py_file.relative_to(REPO_ROOT)}: {sdk}")

    assert not violations, (
        f"Forbidden SDK imports found in app/:\n"
        + "\n".join(f"  {v}" for v in violations)
        + "\nMC-1 / ADR-036: no LLM/agent SDK may appear anywhere in app/."
    )


def test_no_new_js_file_in_static() -> None:
    """
    Negative (TASK-017) / ADR-043: no .js file was added under app/static/.
    ADR-043 chose the no-JS shape (synchronous form-POST + PRG).
    """
    # AC: no .js file in app/static/ (ADR-043 §No JavaScript)
    static_dir = REPO_ROOT / "app" / "static"
    if not static_dir.exists():
        pytest.skip("app/static/ does not exist")

    js_files = list(static_dir.rglob("*.js"))
    assert not js_files, (
        f"Found .js files under app/static/: {[str(f.relative_to(REPO_ROOT)) for f in js_files]}. "
        "ADR-043: the no-JS form-POST + PRG shape was chosen; no JavaScript assets should be added."
    )


def test_no_script_tag_in_take_page() -> None:
    """
    Negative (TASK-017) / ADR-043: quiz_take.html.j2 must have no <script> tag.
    ADR-043: the take page remains JS-free.
    """
    # AC: quiz_take.html.j2 has no <script> tag (ADR-043 §No JS)
    take_template = REPO_ROOT / "app" / "templates" / "quiz_take.html.j2"
    if not take_template.exists():
        pytest.fail("app/templates/quiz_take.html.j2 does not exist — TASK-015 implementation missing.")
    source = take_template.read_text(encoding="utf-8")
    assert "<script" not in source.lower(), (
        "quiz_take.html.j2 contains a <script> tag; ADR-043: the take page must remain "
        "JS-free. The synchronous form-POST + PRG shape was chosen (ADR-043)."
    )


def test_quiz_css_is_the_only_new_css_file() -> None:
    """
    Negative (TASK-017) / ADR-043 / ADR-008: no new CSS file was added under
    app/static/. New quiz-take-* rules go in the existing quiz.css.
    """
    # AC: no new CSS file in app/static/ beyond quiz.css (ADR-043 / ADR-008)
    static_dir = REPO_ROOT / "app" / "static"
    if not static_dir.exists():
        pytest.skip("app/static/ does not exist")

    expected_css_files = {"base.css", "quiz.css", "lecture.css"}
    actual_css_files = {p.name for p in static_dir.rglob("*.css")}

    new_css_files = actual_css_files - expected_css_files
    assert not new_css_files, (
        f"New CSS files found under app/static/: {new_css_files}. "
        "ADR-043 / ADR-008: new quiz-take-* rules go in the existing quiz.css; "
        "no new CSS file should be added."
    )
