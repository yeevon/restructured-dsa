"""
TASK-015: Quiz-taking surface — pytest tests (HTTP-protocol + persistence).

Tests derive from the Acceptance Criteria in
`design_docs/tasks/TASK-015-quiz-taking-surface-write-code-and-submit-attempt.md`
and from the two Accepted ADRs this task lands:
  ADR-038 — The Quiz-taking surface: a GET/POST
             /lecture/{chapter_id}/sections/{section_number}/quiz/{quiz_id}/take
             route pair rendering its own quiz_take.html.j2 page; an Attempt
             started on GET (latest in_progress reused); attempt_questions rows
             created at Attempt start; "Take this Quiz" button-styled link on the
             .section-quiz block's ready entry; the submit route PRG-redirecting
             back to GET .../take in a "Submitted — grading not yet available"
             state; take-page CSS in a new app/static/quiz.css; the submit route
             does NOT invoke grading (MC-4).
  ADR-039 — The Quiz Attempt persistence layer: start_attempt / get_attempt /
             list_questions_for_quiz / list_attempt_questions /
             save_attempt_responses / submit_attempt; QuizAttempt and
             AttemptQuestion dataclasses; attempt_questions rows created at
             Attempt start; additive idx_attempt_questions_attempt_id index;
             no user_id (MC-7); SQL stays under app/persistence/ (MC-10);
             submit_attempt does not invoke grading (MC-4).

Coverage matrix:
  Boundary:
    - test_start_attempt_creates_in_progress_row: Attempt row with status='in_progress'
    - test_start_attempt_creates_one_attempt_questions_row_per_question: one row per Q
    - test_start_attempt_reuses_in_progress_attempt: no second quiz_attempts row
    - test_get_attempt_returns_quiz_attempt: get_attempt round-trip
    - test_get_attempt_returns_none_for_unknown_id: unknown id → None
    - test_list_questions_for_quiz_returns_questions_in_position_order: positional order
    - test_list_attempt_questions_returns_one_per_question: one AttemptQuestion per Q
    - test_list_attempt_questions_empty_for_unknown_attempt: [] for unknown id
    - test_save_attempt_responses_writes_code_verbatim: exact code string stored
    - test_submit_attempt_flips_status_to_submitted: status='submitted', submitted_at set
    - test_submit_attempt_leaves_is_correct_and_explanation_null: no Grade fabricated
    - test_take_route_get_200_for_ready_quiz: happy path GET 200
    - test_take_route_post_303_to_take_url: POST returns 303 to GET .../take
    - test_take_route_get_mandatory_chapter_200: Mandatory Chapter take route works
    - test_take_route_get_optional_chapter_200: Optional Chapter take route works
    - test_take_affordance_present_on_ready_quiz: .section-quiz block shows take link
  Edge:
    - test_attempt_persists_across_connections: re-query after new connection sees Attempt
    - test_save_attempt_responses_ignores_unknown_question_id: stray question_id → no row
    - test_list_attempt_questions_returns_empty_for_fresh_quiz_unknown_attempt: edge case
    - test_quiz_take_renders_all_questions_in_order: all Q prompts + textareas rendered
    - test_take_route_submitted_state_shows_honest_copy: submitted→ no fabricated grade
    - test_submitted_attempt_shows_no_fabricated_score: no invented grade text in HTML
  Negative:
    - test_take_route_get_404_unknown_chapter: unknown chapter → 404
    - test_take_route_get_404_unknown_section: unknown section → 404
    - test_take_route_get_404_unknown_quiz_id: unknown quiz_id → 404
    - test_take_route_get_non_ready_quiz_no_takeable_form: non-ready Quiz → no form
    - test_take_route_get_malformed_chapter_id_422: malformed chapter_id → 422
    - test_take_route_get_quiz_wrong_section_404: quiz_id for wrong section → 404
    - test_take_affordance_absent_on_requested_quiz: no take link on requested Quiz
    - test_take_affordance_absent_on_generating_quiz: no take link on generating Quiz
    - test_take_affordance_absent_on_generation_failed_quiz: no take link on failed Quiz
    - test_submit_route_attempt_is_submitted_not_graded: status=submitted not graded
    - test_no_user_id_on_quiz_attempts_or_attempt_questions: MC-7
    - test_mc10_no_sqlite3_outside_persistence: sqlite3 boundary still intact
    - test_mc10_no_sql_literals_outside_persistence: SQL literals boundary intact
    - test_mc2_attempt_traces_to_exactly_one_section: attempt → one section
    - test_mc4_submit_route_attempt_status_is_submitted: no grading after POST
    - test_mc5_no_fabricated_grade_in_attempt_questions: is_correct/explanation NULL
  Performance:
    - test_start_attempt_with_many_questions_within_budget: 50 questions, start < 5s
    - test_list_attempt_questions_many_questions_within_budget: 50 questions list < 5s

pytestmark registers all tests under task("TASK-015").
"""

from __future__ import annotations

import pathlib
import re
import sqlite3
import time

import pytest

pytestmark = pytest.mark.task("TASK-015")

REPO_ROOT = pathlib.Path(__file__).parent.parent

# ---------------------------------------------------------------------------
# Corpus constants
# ---------------------------------------------------------------------------

MANDATORY_CHAPTER_ID = "ch-01-cpp-refresher"
OPTIONAL_CHAPTER_ID = "ch-07-heaps-and-treaps"

# These section IDs and numbers must match what exists in the corpus .tex files.
# ADR-002: section_id = "{chapter_id}#section-{n-m}"; route uses section_number = "n-m".
MANDATORY_SECTION_ID = "ch-01-cpp-refresher#section-1-1"
MANDATORY_SECTION_NUMBER = "1-1"

OPTIONAL_SECTION_ID = "ch-07-heaps-and-treaps#section-7-1"
OPTIONAL_SECTION_NUMBER = "7-1"


# ---------------------------------------------------------------------------
# Helpers — deferred imports so collection succeeds before implementation exists
# ---------------------------------------------------------------------------


def _make_client(monkeypatch, db_path: str):
    """Return a FastAPI TestClient backed by an isolated test database."""
    monkeypatch.setenv("NOTES_DB_PATH", db_path)
    from fastapi.testclient import TestClient  # noqa: PLC0415
    from app.main import app  # noqa: PLC0415
    return TestClient(app)


def _bootstrap(monkeypatch, db_path: str):
    """Bootstrap the DB schema and return a TestClient."""
    client = _make_client(monkeypatch, db_path)
    # Trigger schema init by hitting a known-good route
    client.get(f"/lecture/{MANDATORY_CHAPTER_ID}")
    return client


def _seed_ready_quiz_with_questions(db_path: str, section_id: str, n_questions: int = 2):
    """
    Insert a ready Quiz + n_questions Questions linked via quiz_questions.
    Returns (quiz_id, list[question_id], list[prompt]).
    Uses raw sqlite3 to bypass the (not-yet-implemented) persistence functions.
    """
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

        question_ids = []
        prompts = []
        for pos in range(1, n_questions + 1):
            prompt = f"Implement function #{pos} for {section_id}"
            conn.execute(
                "INSERT INTO questions (section_id, prompt, topics, created_at) "
                "VALUES (?, ?, 'coding', '2026-05-12T00:00:00Z')",
                (section_id, prompt),
            )
            conn.commit()
            question_id = conn.execute(
                "SELECT question_id FROM questions ORDER BY question_id DESC LIMIT 1"
            ).fetchone()[0]
            conn.execute(
                "INSERT INTO quiz_questions (quiz_id, question_id, position) "
                "VALUES (?, ?, ?)",
                (quiz_id, question_id, pos),
            )
            conn.commit()
            question_ids.append(question_id)
            prompts.append(prompt)
    finally:
        conn.close()
    return quiz_id, question_ids, prompts


def _seed_quiz_with_status(db_path: str, section_id: str, status: str):
    """
    Insert a Quiz with the given status (no questions needed for status-label tests).
    Returns quiz_id.
    """
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


# ---------------------------------------------------------------------------
# AC-3 / ADR-039: start_attempt — creates quiz_attempts row + attempt_questions rows
# ---------------------------------------------------------------------------


def test_start_attempt_creates_in_progress_row(tmp_path, monkeypatch) -> None:
    """
    AC-3 (TASK-015) / ADR-039: start_attempt(quiz_id) must insert a quiz_attempts row
    with status='in_progress', the correct quiz_id, created_at set, and
    submitted_at/graded_at NULL.

    Trace: AC-3; ADR-039 §start_attempt; manifest §7 'Every Quiz Attempt … persists
    across sessions'.
    """
    db_path = str(tmp_path / "start_attempt.db")
    _bootstrap(monkeypatch, db_path)
    quiz_id, _, _ = _seed_ready_quiz_with_questions(db_path, MANDATORY_SECTION_ID)

    from app.persistence import start_attempt  # noqa: PLC0415

    attempt = start_attempt(quiz_id)

    assert attempt is not None, (
        "start_attempt() returned None. ADR-039: must return a QuizAttempt."
    )
    assert hasattr(attempt, "attempt_id") and isinstance(attempt.attempt_id, int) and attempt.attempt_id > 0, (
        f"start_attempt() returned {attempt!r} with invalid attempt_id. "
        "ADR-039: attempt_id must be a positive integer (AUTOINCREMENT PK)."
    )
    assert hasattr(attempt, "quiz_id") and attempt.quiz_id == quiz_id, (
        f"start_attempt() returned attempt.quiz_id={getattr(attempt, 'quiz_id', None)!r}; "
        f"expected {quiz_id!r}. ADR-039: the Attempt must reference the Quiz it was started for."
    )
    assert hasattr(attempt, "status") and attempt.status == "in_progress", (
        f"start_attempt() returned status={getattr(attempt, 'status', None)!r}; "
        "expected 'in_progress'. ADR-039: a new Attempt starts in_progress."
    )
    assert hasattr(attempt, "created_at") and attempt.created_at, (
        f"start_attempt() returned attempt without created_at: {attempt!r}. "
        "ADR-039: created_at must be set."
    )
    assert hasattr(attempt, "submitted_at") and attempt.submitted_at is None, (
        f"start_attempt() returned attempt.submitted_at={getattr(attempt, 'submitted_at', 'MISSING')!r}; "
        "expected None. ADR-039: submitted_at is NULL until the Attempt is submitted."
    )
    assert hasattr(attempt, "graded_at") and attempt.graded_at is None, (
        f"start_attempt() returned attempt.graded_at={getattr(attempt, 'graded_at', 'MISSING')!r}; "
        "expected None. ADR-039 / MC-4: graded_at is NULL until grading runs (async, not now)."
    )


def test_start_attempt_creates_one_attempt_questions_row_per_question(
    tmp_path, monkeypatch
) -> None:
    """
    AC-3 (TASK-015) / ADR-039: after start_attempt(quiz_id) with a Quiz having
    N Questions, there must be exactly N attempt_questions rows for the Attempt,
    one per Question, with response/is_correct/explanation all NULL.

    ADR-039: 'start_attempt … INSERT one attempt_questions row per Question in the
    Quiz (response/is_correct/explanation all NULL), ordered by quiz_questions.position.
    All in one transaction.'

    Trace: AC-3; ADR-039 §attempt_questions rows at Attempt start; MC-4 (no Grade
    fabricated — is_correct NULL); MC-5 (explanation NULL).
    """
    N = 3
    db_path = str(tmp_path / "aq_rows.db")
    _bootstrap(monkeypatch, db_path)
    quiz_id, question_ids, _ = _seed_ready_quiz_with_questions(
        db_path, MANDATORY_SECTION_ID, n_questions=N
    )

    from app.persistence import start_attempt  # noqa: PLC0415

    attempt = start_attempt(quiz_id)

    conn = sqlite3.connect(db_path)
    try:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM attempt_questions WHERE attempt_id = ?",
            (attempt.attempt_id,),
        ).fetchall()
    finally:
        conn.close()

    assert len(rows) == N, (
        f"After start_attempt() for a Quiz with {N} Questions, found {len(rows)} "
        f"attempt_questions rows; expected exactly {N}. "
        "ADR-039: one attempt_questions row per Question in the Quiz, created at Attempt start."
    )

    # Verify all rows have NULL response / is_correct / explanation
    for row in rows:
        assert row["response"] is None, (
            f"attempt_questions row for attempt_id={attempt.attempt_id}, "
            f"question_id={row['question_id']!r} has response={row['response']!r}; "
            "expected NULL. ADR-039: response is NULL until the learner submits code."
        )
        assert row["is_correct"] is None, (
            f"attempt_questions.is_correct is not NULL for a fresh Attempt. "
            "MC-4/MC-5: is_correct stays NULL until grading runs (async later slice)."
        )
        assert row["explanation"] is None, (
            f"attempt_questions.explanation is not NULL for a fresh Attempt. "
            "MC-5: explanation stays NULL until grading runs."
        )

    # All question_ids in the rows must be from this Quiz
    row_question_ids = {row["question_id"] for row in rows}
    assert row_question_ids == set(question_ids), (
        f"attempt_questions rows reference question_ids {row_question_ids!r}; "
        f"expected {set(question_ids)!r}. "
        "ADR-039: exactly the Quiz's Questions must be in the Attempt (MC-2)."
    )


def test_start_attempt_reuses_in_progress_attempt(tmp_path, monkeypatch) -> None:
    """
    ADR-039: calling start_attempt(quiz_id) twice for the same Quiz must return the
    SAME Attempt (no second quiz_attempts row). The 'reuse-the-latest-in_progress' semantics.

    ADR-039 §start_attempt: 'If the Quiz already has an in_progress Attempt, reuse
    the latest one (by created_at / attempt_id) — no second quiz_attempts row from
    an idle take-surface reload.'

    Boundary: the second call returns the same attempt_id.

    Trace: AC-3; ADR-039 §start_attempt; ADR-038 §GET creates-but-reuses.
    """
    db_path = str(tmp_path / "reuse.db")
    _bootstrap(monkeypatch, db_path)
    quiz_id, _, _ = _seed_ready_quiz_with_questions(db_path, MANDATORY_SECTION_ID)

    from app.persistence import start_attempt  # noqa: PLC0415

    attempt1 = start_attempt(quiz_id)
    attempt2 = start_attempt(quiz_id)

    assert attempt1.attempt_id == attempt2.attempt_id, (
        f"start_attempt() called twice for the same Quiz returned different attempt_ids: "
        f"{attempt1.attempt_id!r} vs {attempt2.attempt_id!r}. "
        "ADR-039: if an in_progress Attempt already exists for the Quiz, reuse it — "
        "do NOT create a second quiz_attempts row."
    )

    # Confirm exactly one quiz_attempts row for this quiz
    conn = sqlite3.connect(db_path)
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM quiz_attempts WHERE quiz_id = ?", (quiz_id,)
        ).fetchone()[0]
    finally:
        conn.close()

    assert count == 1, (
        f"After two start_attempt() calls, found {count} quiz_attempts rows for quiz_id="
        f"{quiz_id!r}; expected exactly 1. "
        "ADR-039: idle reloads must not spawn orphan in_progress rows."
    )


# ---------------------------------------------------------------------------
# AC-3 / ADR-039: get_attempt
# ---------------------------------------------------------------------------


def test_get_attempt_returns_quiz_attempt(tmp_path, monkeypatch) -> None:
    """
    ADR-039: get_attempt(attempt_id) must return a QuizAttempt for a known attempt_id.

    Trace: AC-3; ADR-039 §get_attempt; manifest §7 'persists across sessions'.
    """
    db_path = str(tmp_path / "get_attempt.db")
    _bootstrap(monkeypatch, db_path)
    quiz_id, _, _ = _seed_ready_quiz_with_questions(db_path, MANDATORY_SECTION_ID)

    from app.persistence import start_attempt, get_attempt  # noqa: PLC0415

    attempt = start_attempt(quiz_id)
    fetched = get_attempt(attempt.attempt_id)

    assert fetched is not None, (
        f"get_attempt({attempt.attempt_id!r}) returned None; expected a QuizAttempt. "
        "ADR-039: get_attempt must return the Attempt for a known attempt_id."
    )
    assert fetched.attempt_id == attempt.attempt_id, (
        f"get_attempt returned attempt_id={fetched.attempt_id!r}; "
        f"expected {attempt.attempt_id!r}."
    )
    assert fetched.quiz_id == quiz_id, (
        f"get_attempt returned quiz_id={fetched.quiz_id!r}; expected {quiz_id!r}."
    )
    assert fetched.status == "in_progress", (
        f"get_attempt returned status={fetched.status!r}; expected 'in_progress'."
    )


def test_get_attempt_returns_none_for_unknown_id(tmp_path, monkeypatch) -> None:
    """
    ADR-039: get_attempt(attempt_id) must return None for an unknown attempt_id.

    Negative: the standard single-row accessor's not-found contract.

    Trace: ADR-039 §get_attempt.
    """
    db_path = str(tmp_path / "get_attempt_none.db")
    _bootstrap(monkeypatch, db_path)

    from app.persistence import get_attempt  # noqa: PLC0415

    result = get_attempt(999_999)

    assert result is None, (
        f"get_attempt(999_999) returned {result!r}; expected None. "
        "ADR-039: get_attempt must return None for an unknown attempt_id."
    )


# ---------------------------------------------------------------------------
# ADR-039: list_questions_for_quiz
# ---------------------------------------------------------------------------


def test_list_questions_for_quiz_returns_questions_in_position_order(
    tmp_path, monkeypatch
) -> None:
    """
    ADR-039: list_questions_for_quiz(quiz_id) must return the Quiz's Questions
    ordered by quiz_questions.position (ascending).

    Boundary: positions 1, 2, 3 — the first and last items in the list.

    Trace: AC-3; ADR-039 §list_questions_for_quiz.
    """
    db_path = str(tmp_path / "list_q.db")
    _bootstrap(monkeypatch, db_path)
    quiz_id, question_ids, prompts = _seed_ready_quiz_with_questions(
        db_path, MANDATORY_SECTION_ID, n_questions=3
    )

    from app.persistence import list_questions_for_quiz  # noqa: PLC0415

    questions = list_questions_for_quiz(quiz_id)

    assert isinstance(questions, list), (
        f"list_questions_for_quiz returned {type(questions)!r}; expected list. "
        "ADR-039: returns list[Question]."
    )
    assert len(questions) == 3, (
        f"list_questions_for_quiz returned {len(questions)} Questions; expected 3. "
        "ADR-039: must return exactly the Questions in the Quiz."
    )
    # Verify order: prompts in seeded position order (1, 2, 3)
    returned_prompts = [q.prompt for q in questions]
    assert returned_prompts == prompts, (
        f"list_questions_for_quiz returned prompts in order {returned_prompts!r}; "
        f"expected {prompts!r} (position order). "
        "ADR-039: Questions must be ordered by quiz_questions.position."
    )
    # Each returned item must be a Question (has question_id, prompt, topics, section_id)
    for q in questions:
        assert hasattr(q, "question_id"), f"Question has no question_id: {q!r}"
        assert hasattr(q, "prompt"), f"Question has no prompt: {q!r}"
        assert hasattr(q, "topics") and isinstance(q.topics, list), (
            f"Question.topics is not a list: {q!r}. "
            "ADR-033/ADR-039: topics must be a list[str] split from the pipe-delimited column."
        )
        # MC-7 and non-coding-column: no option_*, correct_choice, answer_text
        assert not hasattr(q, "option_a"), (
            "Question dataclass has option_a — violates manifest §5/§7 non-coding format."
        )


# ---------------------------------------------------------------------------
# ADR-039: list_attempt_questions
# ---------------------------------------------------------------------------


def test_list_attempt_questions_returns_one_per_question(
    tmp_path, monkeypatch
) -> None:
    """
    ADR-039: list_attempt_questions(attempt_id) must return one AttemptQuestion per
    attempt_questions row, joined with the Question's prompt and quiz_questions.position,
    ordered by position.

    Trace: AC-3; ADR-039 §list_attempt_questions.
    """
    N = 3
    db_path = str(tmp_path / "list_aq.db")
    _bootstrap(monkeypatch, db_path)
    quiz_id, question_ids, prompts = _seed_ready_quiz_with_questions(
        db_path, MANDATORY_SECTION_ID, n_questions=N
    )

    from app.persistence import start_attempt, list_attempt_questions  # noqa: PLC0415

    attempt = start_attempt(quiz_id)
    aq_list = list_attempt_questions(attempt.attempt_id)

    assert isinstance(aq_list, list), (
        f"list_attempt_questions returned {type(aq_list)!r}; expected list. "
        "ADR-039: returns list[AttemptQuestion]."
    )
    assert len(aq_list) == N, (
        f"list_attempt_questions returned {len(aq_list)} items; expected {N}. "
        "ADR-039: one AttemptQuestion per attempt_questions row."
    )

    for i, aq in enumerate(aq_list):
        assert hasattr(aq, "question_id"), f"AttemptQuestion has no question_id: {aq!r}"
        assert hasattr(aq, "prompt") and aq.prompt == prompts[i], (
            f"AttemptQuestion[{i}].prompt={getattr(aq, 'prompt', None)!r}; "
            f"expected {prompts[i]!r}. "
            "ADR-039: prompt comes from the Question join."
        )
        assert hasattr(aq, "response") and aq.response is None, (
            f"AttemptQuestion[{i}].response={getattr(aq, 'response', None)!r}; "
            "expected None on a fresh Attempt."
        )
        assert hasattr(aq, "position") and aq.position == i + 1, (
            f"AttemptQuestion[{i}].position={getattr(aq, 'position', None)!r}; "
            f"expected {i + 1}. ADR-039: position from quiz_questions.position."
        )


def test_list_attempt_questions_empty_for_unknown_attempt(
    tmp_path, monkeypatch
) -> None:
    """
    ADR-039: list_attempt_questions(attempt_id) must return [] for an unknown attempt_id.

    Trace: ADR-039 §list_attempt_questions.
    """
    db_path = str(tmp_path / "list_aq_empty.db")
    _bootstrap(monkeypatch, db_path)

    from app.persistence import list_attempt_questions  # noqa: PLC0415

    result = list_attempt_questions(999_999)

    assert result == [], (
        f"list_attempt_questions(999_999) returned {result!r}; expected []. "
        "ADR-039: returns [] for an unknown attempt_id."
    )


# ---------------------------------------------------------------------------
# AC-4 / ADR-039: save_attempt_responses + submit_attempt
# ---------------------------------------------------------------------------


def test_save_attempt_responses_writes_code_verbatim(tmp_path, monkeypatch) -> None:
    """
    AC-4 (TASK-015) / ADR-039: save_attempt_responses(attempt_id, {qid: code}) must
    UPDATE attempt_questions.response to the exact code string for each question_id.

    ADR-039: 'Stored response is the code verbatim (no transformation).'

    Trace: AC-4; ADR-039 §save_attempt_responses.
    """
    db_path = str(tmp_path / "save_responses.db")
    _bootstrap(monkeypatch, db_path)
    quiz_id, question_ids, _ = _seed_ready_quiz_with_questions(
        db_path, MANDATORY_SECTION_ID, n_questions=2
    )

    from app.persistence import (  # noqa: PLC0415
        start_attempt, save_attempt_responses, list_attempt_questions
    )

    attempt = start_attempt(quiz_id)
    code_map = {
        question_ids[0]: "def my_func():\n    return 42",
        question_ids[1]: "class MyStack:\n    def __init__(self): self.data = []",
    }
    save_attempt_responses(attempt.attempt_id, code_map)

    aq_list = list_attempt_questions(attempt.attempt_id)
    aq_by_qid = {aq.question_id: aq for aq in aq_list}

    for qid, code in code_map.items():
        assert qid in aq_by_qid, (
            f"question_id={qid!r} not found in list_attempt_questions after "
            f"save_attempt_responses."
        )
        assert aq_by_qid[qid].response == code, (
            f"After save_attempt_responses, question_id={qid!r} has response="
            f"{aq_by_qid[qid].response!r}; expected {code!r}. "
            "ADR-039: the stored response is the code verbatim."
        )


def test_save_attempt_responses_ignores_unknown_question_id(
    tmp_path, monkeypatch
) -> None:
    """
    ADR-039: save_attempt_responses must silently ignore a question_id not in the
    Attempt's attempt_questions rows (no stray INSERT, no exception).

    ADR-039: 'a question_id not present in the Attempt's rows is ignored (no stray
    INSERT — defensive, since the route built responses from the Attempt's own rows).'

    Edge: the route might receive a crafted POST with an extra field.

    Trace: ADR-039 §save_attempt_responses; ADR-024 §Validation split.
    """
    db_path = str(tmp_path / "ignore_unknown.db")
    _bootstrap(monkeypatch, db_path)
    quiz_id, question_ids, _ = _seed_ready_quiz_with_questions(
        db_path, MANDATORY_SECTION_ID, n_questions=1
    )

    from app.persistence import (  # noqa: PLC0415
        start_attempt, save_attempt_responses
    )

    attempt = start_attempt(quiz_id)
    unknown_qid = 999_999
    responses = {
        question_ids[0]: "correct code",
        unknown_qid: "stray code — not in this Quiz",
    }

    # Must not raise; must not insert a row for unknown_qid
    try:
        save_attempt_responses(attempt.attempt_id, responses)
    except Exception as exc:
        pytest.fail(
            f"save_attempt_responses with an unknown question_id raised {exc!r}. "
            "ADR-039: unknown question_ids must be silently ignored, not raise."
        )

    conn = sqlite3.connect(db_path)
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM attempt_questions WHERE attempt_id = ? AND question_id = ?",
            (attempt.attempt_id, unknown_qid),
        ).fetchone()[0]
    finally:
        conn.close()

    assert count == 0, (
        f"save_attempt_responses created {count} attempt_questions rows for unknown "
        f"question_id={unknown_qid!r}; expected 0. "
        "ADR-039: no stray INSERT for a question_id not in the Attempt."
    )


def test_submit_attempt_flips_status_to_submitted(tmp_path, monkeypatch) -> None:
    """
    AC-4 (TASK-015) / ADR-039: submit_attempt(attempt_id) must flip quiz_attempts.status
    to 'submitted' and set submitted_at.

    Trace: AC-4; ADR-039 §submit_attempt.
    """
    db_path = str(tmp_path / "submit_attempt.db")
    _bootstrap(monkeypatch, db_path)
    quiz_id, question_ids, _ = _seed_ready_quiz_with_questions(
        db_path, MANDATORY_SECTION_ID, n_questions=2
    )

    from app.persistence import (  # noqa: PLC0415
        start_attempt, save_attempt_responses, submit_attempt, get_attempt
    )

    attempt = start_attempt(quiz_id)
    save_attempt_responses(
        attempt.attempt_id,
        {question_ids[0]: "print('hello')", question_ids[1]: "return None"},
    )
    submit_attempt(attempt.attempt_id)

    fetched = get_attempt(attempt.attempt_id)
    assert fetched is not None, "get_attempt() returned None after submit."
    assert fetched.status == "submitted", (
        f"After submit_attempt(), quiz_attempts.status={fetched.status!r}; "
        "expected 'submitted'. ADR-039 §submit_attempt."
    )
    assert fetched.submitted_at is not None, (
        f"After submit_attempt(), submitted_at is None. "
        "ADR-039: submitted_at must be set when the Attempt is submitted."
    )


def test_submit_attempt_leaves_is_correct_and_explanation_null(
    tmp_path, monkeypatch
) -> None:
    """
    AC-4 + AC-5 (TASK-015) / MC-4 / MC-5 / ADR-039: after submit_attempt(), each
    attempt_questions row must still have is_correct=NULL and explanation=NULL.

    ADR-039: 'Does NOT touch is_correct/explanation, does NOT invoke grading (MC-4).'
    MC-5: the system never fabricates a Grade.

    Trace: AC-4; AC-5; ADR-039 §submit_attempt; MC-4; MC-5.
    """
    db_path = str(tmp_path / "submit_null.db")
    _bootstrap(monkeypatch, db_path)
    quiz_id, question_ids, _ = _seed_ready_quiz_with_questions(
        db_path, MANDATORY_SECTION_ID, n_questions=2
    )

    from app.persistence import (  # noqa: PLC0415
        start_attempt, save_attempt_responses, submit_attempt
    )

    attempt = start_attempt(quiz_id)
    save_attempt_responses(
        attempt.attempt_id,
        {qid: "some code" for qid in question_ids},
    )
    submit_attempt(attempt.attempt_id)

    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            "SELECT is_correct, explanation FROM attempt_questions WHERE attempt_id = ?",
            (attempt.attempt_id,),
        ).fetchall()
    finally:
        conn.close()

    assert len(rows) > 0, "No attempt_questions rows found after submit."
    for row in rows:
        assert row[0] is None, (
            f"attempt_questions.is_correct={row[0]!r} after submit_attempt(); "
            "expected NULL. MC-4/MC-5: is_correct is NULL until the (async) grading "
            "slice runs — submit_attempt must never fabricate a correctness value."
        )
        assert row[1] is None, (
            f"attempt_questions.explanation={row[1]!r} after submit_attempt(); "
            "expected NULL. MC-5: explanation is NULL until grading; never fabricated."
        )


# ---------------------------------------------------------------------------
# AC-4 / Manifest §7: Attempt persists across connections (sessions)
# ---------------------------------------------------------------------------


def test_attempt_persists_across_connections(tmp_path, monkeypatch) -> None:
    """
    AC-4 (TASK-015) / Manifest §7: 'Every Quiz Attempt … persists across sessions'.

    After start_attempt + save_attempt_responses + submit_attempt, opening a NEW
    connection and re-querying via get_attempt / list_attempt_questions must return
    the submitted Attempt with the learner's responses.

    This is the central invariant: persistence across sessions.

    Trace: AC-4; ADR-039 §get_attempt / §list_attempt_questions; manifest §7.
    """
    db_path = str(tmp_path / "persist.db")
    _bootstrap(monkeypatch, db_path)
    quiz_id, question_ids, _ = _seed_ready_quiz_with_questions(
        db_path, MANDATORY_SECTION_ID, n_questions=2
    )

    code = {question_ids[0]: "def f(): pass", question_ids[1]: "class C: pass"}

    from app.persistence import (  # noqa: PLC0415
        start_attempt, save_attempt_responses, submit_attempt
    )

    attempt = start_attempt(quiz_id)
    save_attempt_responses(attempt.attempt_id, code)
    submit_attempt(attempt.attempt_id)

    # Simulate a new session by re-importing with the same DB path but new import
    # (the env var is already set; just call again — this exercises re-querying)
    from app.persistence import get_attempt, list_attempt_questions  # noqa: PLC0415

    fetched = get_attempt(attempt.attempt_id)
    assert fetched is not None and fetched.status == "submitted", (
        f"After a re-query, get_attempt returned {fetched!r}; expected submitted Attempt. "
        "Manifest §7: the Attempt must persist across sessions."
    )

    aq_list = list_attempt_questions(attempt.attempt_id)
    aq_by_qid = {aq.question_id: aq for aq in aq_list}
    for qid, expected_code in code.items():
        assert qid in aq_by_qid, f"question_id={qid!r} missing from re-queried Attempt."
        assert aq_by_qid[qid].response == expected_code, (
            f"After re-query, question_id={qid!r} has response="
            f"{aq_by_qid[qid].response!r}; expected {expected_code!r}. "
            "Manifest §7: the learner's submitted code must persist across sessions."
        )


# ---------------------------------------------------------------------------
# AC-5 / ADR-038: POST submit → Attempt is submitted, not graded (MC-4)
# ---------------------------------------------------------------------------


def test_submit_route_attempt_is_submitted_not_graded(tmp_path, monkeypatch) -> None:
    """
    AC-5 (TASK-015) / MC-4: the POST .../take route must return with the Attempt in
    'submitted' status — NOT 'graded' — and no AI/grading call must have run inside
    the request handler.

    Verified by: after the POST, the Attempt status from get_attempt() is 'submitted';
    no grading columns are set (is_correct stays NULL on all attempt_questions).

    MC-4: 'No code path completes AI processing synchronously inside the request that
    submits it.'

    Trace: AC-5; ADR-038 §POST .../take; ADR-039 §submit_attempt (does not invoke
    grading); MC-4; manifest §6.
    """
    db_path = str(tmp_path / "submit_mc4.db")
    client = _bootstrap(monkeypatch, db_path)
    quiz_id, question_ids, _ = _seed_ready_quiz_with_questions(
        db_path, MANDATORY_SECTION_ID, n_questions=2
    )

    # Load the take surface (starts an Attempt)
    take_url = (
        f"/lecture/{MANDATORY_CHAPTER_ID}"
        f"/sections/{MANDATORY_SECTION_NUMBER}"
        f"/quiz/{quiz_id}/take"
    )
    get_resp = client.get(take_url)
    assert get_resp.status_code == 200, (
        f"GET {take_url} returned {get_resp.status_code}; expected 200. "
        "Prerequisite: the take surface must load before we POST."
    )

    # Build the submit form — one field per question
    form_data = {f"response_{qid}": f"code for {qid}" for qid in question_ids}
    post_resp = client.post(take_url, data=form_data, follow_redirects=False)

    assert post_resp.status_code == 303, (
        f"POST {take_url} returned {post_resp.status_code}; expected 303 (PRG redirect). "
        "ADR-038 §POST .../take: the submit route must PRG-redirect."
    )

    # The redirect target must be back to the take URL (not the lecture page)
    location = post_resp.headers.get("location", "")
    assert "/take" in location, (
        f"POST {take_url} — Location={location!r} does not contain '/take'. "
        "ADR-038 §Submit-route behavior: redirect back to GET .../take."
    )

    # The Attempt must be 'submitted', not 'graded'
    from app.persistence import get_attempt  # noqa: PLC0415

    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT attempt_id, status FROM quiz_attempts WHERE quiz_id = ? "
            "ORDER BY attempt_id DESC LIMIT 1",
            (quiz_id,),
        ).fetchone()
    finally:
        conn.close()

    assert row is not None, "No quiz_attempts row found after POST."
    attempt_id, status = row
    assert status == "submitted", (
        f"After the POST submit route, quiz_attempts.status={status!r}; "
        "expected 'submitted'. "
        "MC-4: the submit route must not invoke grading — the Attempt stays 'submitted' "
        "(not 'grading' or 'graded') until the async grading processor runs later."
    )

    # Verify no is_correct has been set (no fabricated Grade — MC-4 / MC-5)
    conn = sqlite3.connect(db_path)
    try:
        bad_rows = conn.execute(
            "SELECT COUNT(*) FROM attempt_questions WHERE attempt_id = ? "
            "AND is_correct IS NOT NULL",
            (attempt_id,),
        ).fetchone()[0]
    finally:
        conn.close()

    assert bad_rows == 0, (
        f"{bad_rows} attempt_questions rows have is_correct != NULL after the submit POST. "
        "MC-4/MC-5: is_correct must stay NULL until the (async) grading slice runs; "
        "the submit route must never fabricate correctness values."
    )


def test_take_route_post_303_to_take_url(tmp_path, monkeypatch) -> None:
    """
    ADR-038: POST /lecture/{chapter_id}/sections/{section_number}/quiz/{quiz_id}/take
    must return HTTP 303 See Other with a Location header pointing back to the
    take URL (GET .../take).

    ADR-038 §Submit-route behavior: PRG-redirect back to GET .../take.

    Trace: AC-5; ADR-038 §Submit-route behavior.
    """
    db_path = str(tmp_path / "post_303.db")
    client = _bootstrap(monkeypatch, db_path)
    quiz_id, question_ids, _ = _seed_ready_quiz_with_questions(
        db_path, MANDATORY_SECTION_ID, n_questions=1
    )

    take_url = (
        f"/lecture/{MANDATORY_CHAPTER_ID}"
        f"/sections/{MANDATORY_SECTION_NUMBER}"
        f"/quiz/{quiz_id}/take"
    )
    # GET first to start an Attempt
    client.get(take_url)

    form_data = {f"response_{question_ids[0]}": "my solution"}
    resp = client.post(take_url, data=form_data, follow_redirects=False)

    assert resp.status_code == 303, (
        f"POST {take_url} returned {resp.status_code}; expected 303. "
        "ADR-038: the submit route must use PRG (303 See Other)."
    )
    location = resp.headers.get("location", "")
    assert location, (
        f"POST {take_url} returned 303 but no Location header. "
        "ADR-038: a 303 must carry a Location header pointing to the take URL."
    )
    assert "/take" in location, (
        f"POST {take_url} — Location={location!r} does not contain '/take'. "
        "ADR-038: redirect back to GET .../take (the take surface confirms submission)."
    )


# ---------------------------------------------------------------------------
# AC-5 (submitted state) / MC-5: no fabricated Grade in rendered HTML
# ---------------------------------------------------------------------------


def test_take_route_submitted_state_shows_honest_copy(tmp_path, monkeypatch) -> None:
    """
    AC-5 + AC-6 (TASK-015) / MC-5 / ADR-038: after submitting an Attempt, re-GET of
    the take URL must render the 'Submitted — grading not yet available' (or similar
    honest) state without a fabricated score, grade, or 'all correct' text.

    ADR-038 §The honest 'submitted — not yet graded' copy: 'must not imply a Grade
    exists, must not show a score, must not say "all correct" or any invented result.'

    Trace: AC-5; ADR-038 §submitted state; MC-5 (AI failures surfaced, never fabricated).
    """
    db_path = str(tmp_path / "submitted_state.db")
    client = _bootstrap(monkeypatch, db_path)
    quiz_id, question_ids, _ = _seed_ready_quiz_with_questions(
        db_path, MANDATORY_SECTION_ID, n_questions=1
    )

    take_url = (
        f"/lecture/{MANDATORY_CHAPTER_ID}"
        f"/sections/{MANDATORY_SECTION_NUMBER}"
        f"/quiz/{quiz_id}/take"
    )
    client.get(take_url)
    client.post(
        take_url,
        data={f"response_{question_ids[0]}": "my code"},
        follow_redirects=True,
    )

    # After submission (follow_redirects=True lands on the GET take page)
    re_get = client.get(take_url)
    assert re_get.status_code == 200, (
        f"GET {take_url} after submission returned {re_get.status_code}; expected 200. "
        "ADR-038: the take surface must remain accessible after submission."
    )
    html = re_get.text

    # Must show some form of honest 'submitted' status copy
    submitted_signal = (
        "Submitted" in html
        or "submitted" in html
        or "grading not yet" in html
        or "not yet graded" in html
        or "awaiting grading" in html
    )
    assert submitted_signal, (
        f"After submission, the re-GET of the take surface does not show a 'submitted' "
        "status indicator. "
        "ADR-038: the 'Submitted — grading not yet available' state must be shown."
    )


def test_submitted_attempt_shows_no_fabricated_score(tmp_path, monkeypatch) -> None:
    """
    AC-5 (TASK-015) / MC-5: the take surface after submission must NOT contain
    fabricated score/correctness text.

    Forbidden: 'score', 'all correct', 'you passed', '%', 'grade:' (case-insensitive)
    in a grade-implying context.

    MC-5: 'the system never substitutes a placeholder grade'.
    ADR-038: 'must not imply a Grade exists … must not show a score … must not say
    "all correct" or any invented result'.

    Trace: AC-5; ADR-038 §submitted state; MC-5; manifest §6.
    """
    db_path = str(tmp_path / "no_fake_grade.db")
    client = _bootstrap(monkeypatch, db_path)
    quiz_id, question_ids, _ = _seed_ready_quiz_with_questions(
        db_path, MANDATORY_SECTION_ID, n_questions=2
    )

    take_url = (
        f"/lecture/{MANDATORY_CHAPTER_ID}"
        f"/sections/{MANDATORY_SECTION_NUMBER}"
        f"/quiz/{quiz_id}/take"
    )
    client.get(take_url)
    client.post(
        take_url,
        data={f"response_{qid}": "code" for qid in question_ids},
        follow_redirects=True,
    )

    html = client.get(take_url).text.lower()

    # Fabricated-grade patterns that must NOT appear in the submitted state
    fabricated_patterns = [
        "all correct",
        "you passed",
        "you scored",
        "score: ",
        "grade: ",
        "100%",
        "correct!",
        "is_correct",  # raw column name must not leak
    ]
    found = [p for p in fabricated_patterns if p in html]
    assert not found, (
        f"After submission, the take surface HTML contains fabricated-grade patterns: "
        f"{found!r}. "
        "MC-5/ADR-038: the submitted state must never show a score, 'all correct', "
        "or any invented result. is_correct/explanation stay NULL until grading."
    )


# ---------------------------------------------------------------------------
# AC-7 / ADR-038: GET take route — 404 / 422 cases
# ---------------------------------------------------------------------------


def test_take_route_get_200_for_ready_quiz(tmp_path, monkeypatch) -> None:
    """
    AC-2 + AC-7 (TASK-015) / ADR-038: GET /lecture/{chapter_id}/sections/{section_number}
    /quiz/{quiz_id}/take for a valid ready Quiz with ≥1 Question must return 200.

    Happy path — the foundational GET.

    Trace: AC-2; AC-7; ADR-038 §GET .../take.
    """
    db_path = str(tmp_path / "take_200.db")
    client = _bootstrap(monkeypatch, db_path)
    quiz_id, _, _ = _seed_ready_quiz_with_questions(
        db_path, MANDATORY_SECTION_ID, n_questions=2
    )

    resp = client.get(
        f"/lecture/{MANDATORY_CHAPTER_ID}"
        f"/sections/{MANDATORY_SECTION_NUMBER}"
        f"/quiz/{quiz_id}/take"
    )
    assert resp.status_code == 200, (
        f"GET .../quiz/{quiz_id}/take returned {resp.status_code}; expected 200. "
        "AC-2/ADR-038: a valid ready Quiz must return 200."
    )
    assert "text/html" in resp.headers.get("content-type", ""), (
        "GET take route did not return text/html."
    )


def test_take_route_get_mandatory_chapter_200(tmp_path, monkeypatch) -> None:
    """
    AC-9 + MC-3 (TASK-015): the take surface must work for a Quiz on a Mandatory
    Chapter (ch-01-cpp-refresher).

    MC-3: 'every learner-facing surface honors and exposes the [Mandatory/Optional] split.'

    Trace: AC-9; MC-3; ADR-038; manifest §6 'Mandatory and Optional honored everywhere'.
    """
    db_path = str(tmp_path / "mandatory_take.db")
    client = _bootstrap(monkeypatch, db_path)
    quiz_id, _, _ = _seed_ready_quiz_with_questions(
        db_path, MANDATORY_SECTION_ID, n_questions=1
    )

    resp = client.get(
        f"/lecture/{MANDATORY_CHAPTER_ID}"
        f"/sections/{MANDATORY_SECTION_NUMBER}"
        f"/quiz/{quiz_id}/take"
    )
    assert resp.status_code == 200, (
        f"Take route for Mandatory Chapter returned {resp.status_code}; expected 200. "
        "MC-3: the take surface must be reachable for Mandatory Chapter Quizzes."
    )
    html = resp.text
    # M/O designation context must be visible (MC-3)
    # The designation badge uses 'Mandatory' or 'mandatory' or 'designation-mandatory'
    designation_signal = (
        "mandatory" in html.lower()
        or "designation-" in html.lower()
    )
    assert designation_signal, (
        f"Take route for Mandatory Chapter does not show M/O designation context. "
        "MC-3/ADR-038: the take surface must surface the parent Chapter's "
        "Mandatory/Optional context (designation badge per ADR-004/ADR-008)."
    )


def test_take_route_get_optional_chapter_200(tmp_path, monkeypatch) -> None:
    """
    AC-9 + MC-3 (TASK-015): the take surface must work for a Quiz on an Optional
    Chapter (ch-07-heaps-and-treaps).

    Trace: AC-9; MC-3; ADR-038; manifest §6 'Mandatory and Optional honored everywhere'.
    """
    db_path = str(tmp_path / "optional_take.db")
    client = _bootstrap(monkeypatch, db_path)
    quiz_id, _, _ = _seed_ready_quiz_with_questions(
        db_path, OPTIONAL_SECTION_ID, n_questions=1
    )

    resp = client.get(
        f"/lecture/{OPTIONAL_CHAPTER_ID}"
        f"/sections/{OPTIONAL_SECTION_NUMBER}"
        f"/quiz/{quiz_id}/take"
    )
    assert resp.status_code == 200, (
        f"Take route for Optional Chapter returned {resp.status_code}; expected 200. "
        "MC-3: the take surface must be reachable for Optional Chapter Quizzes."
    )
    html = resp.text
    # Optional designation context must be visible
    designation_signal = (
        "optional" in html.lower()
        or "designation-" in html.lower()
    )
    assert designation_signal, (
        f"Take route for Optional Chapter does not show M/O designation context. "
        "MC-3/ADR-038: the take surface must surface the Optional designation context."
    )


def test_take_route_get_404_unknown_chapter(tmp_path, monkeypatch) -> None:
    """
    AC-7 (TASK-015) / ADR-038: GET with an unknown chapter_id must return 404.

    ADR-038: 'chapter_id valid (the corpus .tex exists) — else 404.'

    Trace: AC-7; ADR-038 §GET validation; ADR-024 §Validation split.
    """
    db_path = str(tmp_path / "take_404_ch.db")
    client = _bootstrap(monkeypatch, db_path)

    resp = client.get(
        "/lecture/ch-99-does-not-exist/sections/99-1/quiz/1/take"
    )
    assert resp.status_code == 404, (
        f"GET with unknown chapter_id returned {resp.status_code}; expected 404. "
        "AC-7/ADR-038: an unknown chapter_id must return 404."
    )


def test_take_route_get_404_unknown_section(tmp_path, monkeypatch) -> None:
    """
    AC-7 (TASK-015) / ADR-038: GET with an unknown section_number must return 404.

    ADR-038: 'section_number corresponds to a known Section … else 404.'

    Trace: AC-7; ADR-038 §GET validation; ADR-024 §Validation split.
    """
    db_path = str(tmp_path / "take_404_sec.db")
    client = _bootstrap(monkeypatch, db_path)
    quiz_id, _, _ = _seed_ready_quiz_with_questions(
        db_path, MANDATORY_SECTION_ID, n_questions=1
    )

    resp = client.get(
        f"/lecture/{MANDATORY_CHAPTER_ID}/sections/999-999/quiz/{quiz_id}/take"
    )
    assert resp.status_code == 404, (
        f"GET with unknown section_number returned {resp.status_code}; expected 404. "
        "AC-7/ADR-038: an unknown section_number must return 404."
    )


def test_take_route_get_404_unknown_quiz_id(tmp_path, monkeypatch) -> None:
    """
    AC-7 (TASK-015) / ADR-038: GET with a quiz_id that does not exist must return 404.

    ADR-038: 'quiz_id exists (get_quiz(quiz_id) is not None) — else 404.'

    Trace: AC-7; ADR-038 §GET validation.
    """
    db_path = str(tmp_path / "take_404_qid.db")
    client = _bootstrap(monkeypatch, db_path)

    resp = client.get(
        f"/lecture/{MANDATORY_CHAPTER_ID}"
        f"/sections/{MANDATORY_SECTION_NUMBER}"
        "/quiz/999999/take"
    )
    assert resp.status_code == 404, (
        f"GET with unknown quiz_id returned {resp.status_code}; expected 404. "
        "AC-7/ADR-038: a quiz_id that does not exist must return 404."
    )


def test_take_route_get_malformed_chapter_id_422(tmp_path, monkeypatch) -> None:
    """
    AC-7 (TASK-015) / ADR-038: GET with a malformed chapter_id must return 422.

    ADR-038: 'chapter_id malformed (no valid chapter number per chapter_designation())
    — else 422 (mirroring render_chapter).'

    Trace: AC-7; ADR-038 §GET validation; ADR-024.
    """
    db_path = str(tmp_path / "take_422.db")
    client = _bootstrap(monkeypatch, db_path)

    # A string that cannot be a valid chapter_id (no numeric chapter prefix)
    resp = client.get(
        "/lecture/not-a-real-chapter-id/sections/1-1/quiz/1/take"
    )
    assert resp.status_code in (404, 422), (
        f"GET with malformed chapter_id returned {resp.status_code}; expected 422 (or 404). "
        "AC-7/ADR-038: a malformed chapter_id must return 422 (mirroring render_chapter)."
    )


def test_take_route_get_quiz_wrong_section_404(tmp_path, monkeypatch) -> None:
    """
    AC-7 (TASK-015) / ADR-038: GET with a quiz_id that exists but belongs to a
    DIFFERENT Section than the URL's section_number must return 404.

    ADR-038: 'the Quiz's section_id matches the composed section_id (the Quiz
    belongs to the Section in the URL) — else 404.'

    This prevents navigating to a Quiz that doesn't belong to the Section in the URL.

    Trace: AC-7; ADR-038 §GET validation; MC-2.
    """
    db_path = str(tmp_path / "take_wrong_section.db")
    client = _bootstrap(monkeypatch, db_path)

    # Create a Quiz for section 1-1
    quiz_id, _, _ = _seed_ready_quiz_with_questions(
        db_path, MANDATORY_SECTION_ID, n_questions=1
    )

    # Try to access this Quiz via section 1-2 (wrong section)
    resp = client.get(
        f"/lecture/{MANDATORY_CHAPTER_ID}/sections/1-2/quiz/{quiz_id}/take"
    )
    assert resp.status_code == 404, (
        f"GET with quiz_id belonging to a different Section returned {resp.status_code}; "
        "expected 404. "
        "AC-7/ADR-038: a Quiz accessed via the wrong Section URL must return 404 "
        "(MC-2: the take surface must trace to exactly one Section)."
    )


def test_take_route_get_non_ready_quiz_no_takeable_form(tmp_path, monkeypatch) -> None:
    """
    AC-7 (TASK-015) / ADR-038: a non-ready Quiz accessed via the take URL must NOT
    present a takeable form (no <form> with response fields and a submit button for
    code submission).

    ADR-038: 'The Quiz's status is ready — if it is requested/generating/
    generation_failed, the surface does NOT present a takeable form.'

    Negative: the status code may be 200 (rendered honest state) or 4xx — both
    acceptable; the key assertion is NO takeable form.

    Trace: AC-7; ADR-038 §GET validation (non-ready case).
    """
    db_path = str(tmp_path / "take_not_ready.db")
    client = _bootstrap(monkeypatch, db_path)
    quiz_id = _seed_quiz_with_status(db_path, MANDATORY_SECTION_ID, "requested")

    resp = client.get(
        f"/lecture/{MANDATORY_CHAPTER_ID}"
        f"/sections/{MANDATORY_SECTION_NUMBER}"
        f"/quiz/{quiz_id}/take"
    )

    if resp.status_code == 200:
        html = resp.text
        # Must NOT contain a form with code-response fields
        has_response_field = bool(re.search(r'name=["\']response_\d+["\']', html))
        assert not has_response_field, (
            "GET take route for a 'requested' Quiz returned 200 with a response_ form "
            "field in the HTML. "
            "ADR-038: a non-ready Quiz must NOT present a takeable form — no response_ "
            "fields, no submit button for code submission."
        )
        # Must NOT have a submit button that implies code submission
        # (a "back" link or an honest status page is fine; a "Submit Quiz" button is not)
        has_submit_quiz = "Submit Quiz" in html or "submit quiz" in html.lower()
        assert not has_submit_quiz, (
            "GET take route for a 'requested' Quiz contains a 'Submit Quiz' button. "
            "ADR-038: a non-ready Quiz must not present a takeable form."
        )
    else:
        # 4xx is also acceptable per ADR-038 ('HTTP error or a rendered honest state')
        assert resp.status_code in range(400, 500), (
            f"GET take route for a 'requested' Quiz returned unexpected status "
            f"{resp.status_code}; expected 200 with no-takeable-form, or 4xx."
        )


# ---------------------------------------------------------------------------
# AC-1 / ADR-038: take affordance on .section-quiz block
# ---------------------------------------------------------------------------


def test_take_affordance_present_on_ready_quiz(tmp_path, monkeypatch) -> None:
    """
    AC-1 (TASK-015) / ADR-038: when a Section has a ready Quiz, the rendered Lecture
    page must show a take affordance (a 'Take this Quiz' link or button-styled link)
    on that Quiz's list entry.

    ADR-038 §Take affordance: 'section-quiz-take-link' in lecture.css; the link is
    keyed by quiz_id and points to GET .../take.

    Trace: AC-1; ADR-038 §Take affordance on .section-quiz block.
    """
    db_path = str(tmp_path / "take_affordance.db")
    client = _bootstrap(monkeypatch, db_path)
    quiz_id, _, _ = _seed_ready_quiz_with_questions(
        db_path, MANDATORY_SECTION_ID, n_questions=1
    )

    resp = client.get(f"/lecture/{MANDATORY_CHAPTER_ID}")
    assert resp.status_code == 200
    html = resp.text

    # Must contain a take affordance — either the CSS class or a link with /take
    take_signal = (
        "section-quiz-take-link" in html
        or "/take" in html
        or "Take this Quiz" in html
        or "Take Quiz" in html
    )
    assert take_signal, (
        f"GET /lecture/{MANDATORY_CHAPTER_ID} with a ready Quiz (id={quiz_id!r}) "
        "shows no take affordance in the .section-quiz block. "
        "AC-1/ADR-038: a ready Quiz must have a 'Take this Quiz' link/button "
        "('section-quiz-take-link' class or a link to .../take)."
    )

    # The take link must reference this quiz's quiz_id
    assert f"/quiz/{quiz_id}/take" in html or f"quiz/{quiz_id}" in html, (
        f"GET /lecture/{MANDATORY_CHAPTER_ID} — take affordance does not contain "
        f"/quiz/{quiz_id}/take. "
        "ADR-038: the take link must be keyed by quiz_id."
    )


def test_take_affordance_absent_on_requested_quiz(tmp_path, monkeypatch) -> None:
    """
    AC-1 (TASK-015) / ADR-038: a 'requested' Quiz's list entry must NOT show a take
    affordance. The 'Requested' label is unchanged from ADR-034.

    ADR-038: 'The requested / generating / generation_failed entries get NO such
    affordance (they are not takeable) — their labels are unchanged from ADR-034.'

    Trace: AC-1; ADR-038 §Take affordance; ADR-034 (non-ready labels unchanged).
    """
    db_path = str(tmp_path / "no_affordance_requested.db")
    client = _bootstrap(monkeypatch, db_path)
    quiz_id = _seed_quiz_with_status(db_path, MANDATORY_SECTION_ID, "requested")

    resp = client.get(f"/lecture/{MANDATORY_CHAPTER_ID}")
    assert resp.status_code == 200
    html = resp.text

    # Must NOT contain a take link for this quiz_id
    assert f"/quiz/{quiz_id}/take" not in html, (
        f"GET /lecture/{MANDATORY_CHAPTER_ID} contains /quiz/{quiz_id}/take for a "
        "'requested' Quiz. "
        "AC-1/ADR-038: a requested Quiz must NOT show a take affordance."
    )


def test_take_affordance_absent_on_generating_quiz(tmp_path, monkeypatch) -> None:
    """
    AC-1 / ADR-038: a 'generating' Quiz must NOT show a take affordance.

    Trace: AC-1; ADR-038 §Take affordance; ADR-034 (generating label unchanged).
    """
    db_path = str(tmp_path / "no_affordance_generating.db")
    client = _bootstrap(monkeypatch, db_path)
    quiz_id = _seed_quiz_with_status(db_path, MANDATORY_SECTION_ID, "generating")

    resp = client.get(f"/lecture/{MANDATORY_CHAPTER_ID}")
    assert resp.status_code == 200
    html = resp.text

    assert f"/quiz/{quiz_id}/take" not in html, (
        f"GET /lecture/{MANDATORY_CHAPTER_ID} contains /quiz/{quiz_id}/take for a "
        "'generating' Quiz. ADR-038: generating Quizzes must not show a take affordance."
    )


def test_take_affordance_absent_on_generation_failed_quiz(tmp_path, monkeypatch) -> None:
    """
    AC-1 / ADR-038: a 'generation_failed' Quiz must NOT show a take affordance.

    Trace: AC-1; ADR-038 §Take affordance; ADR-034 (generation_failed label unchanged).
    """
    db_path = str(tmp_path / "no_affordance_failed.db")
    client = _bootstrap(monkeypatch, db_path)
    quiz_id = _seed_quiz_with_status(db_path, MANDATORY_SECTION_ID, "generation_failed")

    resp = client.get(f"/lecture/{MANDATORY_CHAPTER_ID}")
    assert resp.status_code == 200
    html = resp.text

    assert f"/quiz/{quiz_id}/take" not in html, (
        f"GET /lecture/{MANDATORY_CHAPTER_ID} contains /quiz/{quiz_id}/take for a "
        "'generation_failed' Quiz. ADR-038: failed Quizzes must not show a take affordance."
    )


# ---------------------------------------------------------------------------
# AC-2 / ADR-038: take surface renders all Questions with code fields
# ---------------------------------------------------------------------------


def test_quiz_take_renders_all_questions_in_order(tmp_path, monkeypatch) -> None:
    """
    AC-2 (TASK-015) / ADR-038: the take surface must render ALL Questions in the
    Quiz (in quiz_questions.position order), each with its coding-task prompt text
    and a code-entry <textarea>.

    ADR-038: 'for each AttemptQuestion in position order, a block with the Question's
    coding-task prompt (rendered as text) and a code-entry <textarea name="response_{aq.question_id}">.'

    ADR-038 (manifest §5/§7 enforced): the surface must NOT render non-code inputs
    (no option radios, no true/false toggle, no 'describe in a sentence' field).

    Trace: AC-2; ADR-038 §take surface template; manifest §5/§7.
    """
    N = 3
    db_path = str(tmp_path / "take_renders.db")
    client = _bootstrap(monkeypatch, db_path)
    quiz_id, question_ids, prompts = _seed_ready_quiz_with_questions(
        db_path, MANDATORY_SECTION_ID, n_questions=N
    )

    take_url = (
        f"/lecture/{MANDATORY_CHAPTER_ID}"
        f"/sections/{MANDATORY_SECTION_NUMBER}"
        f"/quiz/{quiz_id}/take"
    )
    resp = client.get(take_url)
    assert resp.status_code == 200
    html = resp.text

    # All prompts must appear in the HTML
    for prompt in prompts:
        assert prompt in html, (
            f"Take surface does not contain Question prompt {prompt!r}. "
            "AC-2/ADR-038: all Questions' coding-task prompts must be rendered."
        )

    # Each Question must have a code-entry textarea
    for qid in question_ids:
        # ADR-038: <textarea name="response_{aq.question_id}">
        assert f"response_{qid}" in html, (
            f"Take surface does not contain a response field for question_id={qid!r}. "
            "AC-2/ADR-038: every Question must have a code-entry <textarea name='response_{qid}'>."
        )

    # Must NOT contain non-code input types (no option radios, no true/false toggle)
    # Manifest §5/§7: 'No non-coding Question formats.'
    # 'type="radio"' in html would indicate a multiple-choice question
    assert 'type="radio"' not in html, (
        "Take surface contains type='radio' — this violates manifest §5/§7. "
        "Every Question is a hands-on coding task; the take surface must NOT render "
        "option radios or any non-code input."
    )
    assert 'type="checkbox"' not in html or "response_" in html, (
        "Take surface contains checkbox inputs without code-response fields. "
        "Manifest §5: no non-coding Question formats."
    )


# ---------------------------------------------------------------------------
# AC-8 / ADR-039: additive index + no user_id (MC-7, MC-8)
# ---------------------------------------------------------------------------


def test_no_user_id_on_quiz_attempts_or_attempt_questions(
    tmp_path, monkeypatch
) -> None:
    """
    AC-8 (TASK-015) / MC-7 / ADR-039: no user_id column must appear on quiz_attempts
    or attempt_questions after TASK-015's additions.

    ADR-039: 'No user_id column … manifest §5/§6 single-user posture.'
    MC-7: 'no user_id columns, no auth middleware, no per-user data partitioning.'

    Trace: AC-8; MC-7; ADR-039 §No user_id; manifest §5/§6.
    """
    db_path = str(tmp_path / "no_user_id.db")
    _bootstrap(monkeypatch, db_path)

    conn = sqlite3.connect(db_path)
    try:
        for table in ("quiz_attempts", "attempt_questions"):
            cols = {
                row[1]
                for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
            }
            assert "user_id" not in cols, (
                f"Table '{table}' has a 'user_id' column. "
                "AC-8/MC-7/ADR-039: no user_id is allowed on any Quiz-domain table. "
                "The project is single-user (manifest §5/§6)."
            )
    finally:
        conn.close()


def test_attempt_questions_index_is_additive(tmp_path, monkeypatch) -> None:
    """
    AC-8 (TASK-015) / ADR-039: the idx_attempt_questions_attempt_id index must exist
    after schema bootstrap, created via CREATE INDEX IF NOT EXISTS (additive, no
    migration trigger per ADR-022).

    ADR-039: 'connection.py's _SCHEMA_SQL gains one line:
    CREATE INDEX IF NOT EXISTS idx_attempt_questions_attempt_id ON attempt_questions (attempt_id).'

    Trace: AC-8; ADR-039 §additive index; ADR-022 §Migration story.
    """
    db_path = str(tmp_path / "index.db")
    _bootstrap(monkeypatch, db_path)

    conn = sqlite3.connect(db_path)
    try:
        indexes = {
            row[1]
            for row in conn.execute("PRAGMA index_list(attempt_questions)").fetchall()
        }
    finally:
        conn.close()

    assert "idx_attempt_questions_attempt_id" in indexes, (
        f"Index 'idx_attempt_questions_attempt_id' not found on attempt_questions. "
        f"Indexes found: {indexes!r}. "
        "AC-8/ADR-039: the additive index must be created by connection.py's "
        "_SCHEMA_SQL via CREATE INDEX IF NOT EXISTS."
    )


# ---------------------------------------------------------------------------
# AC-6 / MC-2: Attempt traces to exactly one Section
# ---------------------------------------------------------------------------


def test_mc2_attempt_traces_to_exactly_one_section(tmp_path, monkeypatch) -> None:
    """
    AC-6 (TASK-015) / MC-2: the Quiz's section_id, the Attempt's quiz_id, and every
    attempt_questions row's question_id must all trace to exactly ONE Section.

    MC-2: 'Every Quiz entity, route, query, and AI prompt references exactly one Section.'

    Trace: AC-6; ADR-038 §MC-2; ADR-039 §MC-2; MC-2; manifest §6/§7.
    """
    db_path = str(tmp_path / "mc2.db")
    _bootstrap(monkeypatch, db_path)
    quiz_id, question_ids, _ = _seed_ready_quiz_with_questions(
        db_path, MANDATORY_SECTION_ID, n_questions=3
    )

    from app.persistence import start_attempt  # noqa: PLC0415

    attempt = start_attempt(quiz_id)

    conn = sqlite3.connect(db_path)
    try:
        # The Quiz references one section_id
        quiz_row = conn.execute(
            "SELECT section_id FROM quizzes WHERE quiz_id = ?", (quiz_id,)
        ).fetchone()
        assert quiz_row is not None, f"Quiz {quiz_id!r} not found."
        quiz_section_id = quiz_row[0]
        assert quiz_section_id == MANDATORY_SECTION_ID, (
            f"Quiz section_id={quiz_section_id!r}; expected {MANDATORY_SECTION_ID!r}."
        )

        # All attempt_questions must reference Questions whose section_id == the Quiz's
        aq_rows = conn.execute(
            "SELECT q.section_id FROM attempt_questions aq "
            "JOIN questions q ON aq.question_id = q.question_id "
            "WHERE aq.attempt_id = ?",
            (attempt.attempt_id,),
        ).fetchall()
        section_ids_in_attempt = {row[0] for row in aq_rows}
    finally:
        conn.close()

    assert section_ids_in_attempt == {MANDATORY_SECTION_ID}, (
        f"The Attempt's attempt_questions rows reference section_ids "
        f"{section_ids_in_attempt!r}; expected only {{{MANDATORY_SECTION_ID!r}}}. "
        "MC-2: every Question in the Attempt must trace to the one Section the Quiz "
        "is scoped to. No cross-Section Attempt composition is allowed."
    )


# ---------------------------------------------------------------------------
# AC-8 / MC-4 assertion: submit_attempt does not invoke grading
# ---------------------------------------------------------------------------


def test_mc4_submit_route_attempt_status_is_submitted(tmp_path, monkeypatch) -> None:
    """
    AC-8 + MC-4 (TASK-015): after submit_attempt(), the Attempt's status must be
    'submitted' — not 'grading', 'graded', or 'grading_failed'. The persistence
    function itself must not invoke grading.

    MC-4: 'No code path completes AI processing synchronously inside the request
    that submits it.'
    ADR-039 §submit_attempt: 'Does NOT invoke grading (MC-4).'

    Trace: AC-8; MC-4; ADR-039 §submit_attempt.
    """
    db_path = str(tmp_path / "mc4.db")
    _bootstrap(monkeypatch, db_path)
    quiz_id, question_ids, _ = _seed_ready_quiz_with_questions(
        db_path, MANDATORY_SECTION_ID, n_questions=1
    )

    from app.persistence import (  # noqa: PLC0415
        start_attempt, save_attempt_responses, submit_attempt, get_attempt
    )

    attempt = start_attempt(quiz_id)
    save_attempt_responses(attempt.attempt_id, {question_ids[0]: "code"})
    submit_attempt(attempt.attempt_id)

    fetched = get_attempt(attempt.attempt_id)
    assert fetched is not None

    # Status MUST be 'submitted', not any grading-related state
    grading_states = {"grading", "graded", "grading_failed"}
    assert fetched.status not in grading_states, (
        f"After submit_attempt(), Attempt status is {fetched.status!r}. "
        "MC-4/ADR-039: submit_attempt must NOT invoke grading synchronously. "
        "The Attempt stays 'submitted' until the async grading processor runs later."
    )
    assert fetched.status == "submitted", (
        f"After submit_attempt(), Attempt status is {fetched.status!r}; expected 'submitted'."
    )


def test_mc5_no_fabricated_grade_in_attempt_questions(tmp_path, monkeypatch) -> None:
    """
    AC-8 + MC-5 (TASK-015): after the full start → save_responses → submit lifecycle,
    every attempt_questions.is_correct and .explanation must remain NULL.

    MC-5: 'the system never substitutes a placeholder grade'.
    ADR-039: 'does NOT touch is_correct/explanation'.

    Trace: AC-8; MC-5; ADR-039 §submit_attempt; manifest §6.
    """
    db_path = str(tmp_path / "mc5.db")
    _bootstrap(monkeypatch, db_path)
    quiz_id, question_ids, _ = _seed_ready_quiz_with_questions(
        db_path, MANDATORY_SECTION_ID, n_questions=3
    )

    from app.persistence import (  # noqa: PLC0415
        start_attempt, save_attempt_responses, submit_attempt
    )

    attempt = start_attempt(quiz_id)
    save_attempt_responses(
        attempt.attempt_id, {qid: "some code" for qid in question_ids}
    )
    submit_attempt(attempt.attempt_id)

    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            "SELECT question_id, is_correct, explanation FROM attempt_questions "
            "WHERE attempt_id = ?",
            (attempt.attempt_id,),
        ).fetchall()
    finally:
        conn.close()

    assert len(rows) == len(question_ids), (
        f"Expected {len(question_ids)} attempt_questions rows, got {len(rows)}."
    )
    for qid, is_correct, explanation in rows:
        assert is_correct is None, (
            f"attempt_questions.is_correct={is_correct!r} for question_id={qid!r} "
            "after the full submit lifecycle. "
            "MC-5: is_correct must be NULL — the grading slice (async, later) fills it. "
            "The submit path must never fabricate a correctness value."
        )
        assert explanation is None, (
            f"attempt_questions.explanation={explanation!r} for question_id={qid!r}. "
            "MC-5: explanation must be NULL until grading runs. Never fabricated."
        )


# ---------------------------------------------------------------------------
# AC-9 / MC-10: persistence boundary grepping
# ---------------------------------------------------------------------------


def test_mc10_no_sqlite3_outside_persistence() -> None:
    """
    AC-9 (TASK-015) / MC-10 / ADR-022: after TASK-015's additions (the new take
    route, the quiz_take.html.j2 template), `import sqlite3` must still appear ONLY
    in files under app/persistence/.

    MC-10: 'Only the persistence package … talks to the database. Routes, workflows,
    and templates do not embed SQL or open DB connections.'

    Trace: AC-9; MC-10; ADR-022 §Package boundary; ADR-038 §MC-10 (take route +
    template call only typed public functions).
    """
    app_dir = REPO_ROOT / "app"
    persistence_dir = app_dir / "persistence"
    violations = []
    for py_file in app_dir.rglob("*.py"):
        try:
            py_file.relative_to(persistence_dir)
            continue  # inside app/persistence/ — allowed
        except ValueError:
            pass
        text = py_file.read_text(encoding="utf-8")
        if "import sqlite3" in text:
            violations.append(str(py_file.relative_to(REPO_ROOT)))

    assert violations == [], (
        f"MC-10 BLOCKER: `import sqlite3` found outside `app/persistence/` in: "
        f"{violations!r}. "
        "ADR-022/ADR-038/ADR-039: the take route, the submit route, and quiz_take.html.j2 "
        "must call only typed public functions from app/persistence/__init__.py — "
        "they must never import sqlite3."
    )


def test_mc10_no_sql_literals_outside_persistence() -> None:
    """
    AC-9 (TASK-015) / MC-10: SQL string literals must appear ONLY under app/persistence/.

    Trace: AC-9; MC-10; ADR-022 §Package boundary; ADR-039 §SQL stays here.
    """
    app_dir = REPO_ROOT / "app"
    persistence_dir = app_dir / "persistence"

    sql_pattern = re.compile(
        r"""(?x)
        (?:"|')           # opening quote
        [^"']*            # any content
        (?:
            \bSELECT\b  |
            \bINSERT\b  |
            \bUPDATE\b  |
            \bDELETE\b  |
            \bCREATE\s+TABLE\b |
            \bCREATE\s+INDEX\b |
            \bBEGIN\b   |
            \bCOMMIT\b  |
            \bROLLBACK\b
        )
        [^"']*
        (?:"|')
        """,
    )

    violations = []
    for py_file in app_dir.rglob("*.py"):
        try:
            py_file.relative_to(persistence_dir)
            continue  # allowed
        except ValueError:
            pass
        text = py_file.read_text(encoding="utf-8")
        if sql_pattern.search(text):
            violations.append(str(py_file.relative_to(REPO_ROOT)))

    assert violations == [], (
        f"MC-10 BLOCKER: SQL string literals found outside `app/persistence/` in: "
        f"{violations!r}. "
        "ADR-022/ADR-039 §SQL stays here: all SQL literals for Attempt functions "
        "live in app/persistence/quizzes.py. Routes and templates must not embed SQL."
    )


# ---------------------------------------------------------------------------
# Performance
# ---------------------------------------------------------------------------


def test_start_attempt_with_many_questions_within_budget(
    tmp_path, monkeypatch
) -> None:
    """
    Performance: start_attempt(quiz_id) for a Quiz with 50 Questions must complete
    within 5 seconds.

    This catches O(n²) regressions in the INSERT-all-attempt_questions-rows path.
    Budget is generous (5s) — the goal is to catch pathological scaling, not to
    micro-benchmark.

    ADR-039: 'INSERT one attempt_questions row per Question … All in one transaction.'
    The single-transaction path should be fast even with 50 Questions.

    Trace: ADR-039 §start_attempt (one transaction); ADR-022 §single-user scale.
    """
    db_path = str(tmp_path / "perf_start.db")
    _bootstrap(monkeypatch, db_path)
    quiz_id, _, _ = _seed_ready_quiz_with_questions(
        db_path, MANDATORY_SECTION_ID, n_questions=50
    )

    from app.persistence import start_attempt  # noqa: PLC0415

    t0 = time.monotonic()
    attempt = start_attempt(quiz_id)
    elapsed = time.monotonic() - t0

    assert attempt is not None, "start_attempt returned None for 50-question Quiz."

    conn = sqlite3.connect(db_path)
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM attempt_questions WHERE attempt_id = ?",
            (attempt.attempt_id,),
        ).fetchone()[0]
    finally:
        conn.close()

    assert count == 50, (
        f"start_attempt with 50 Questions created {count} attempt_questions rows; expected 50."
    )
    assert elapsed < 5.0, (
        f"start_attempt with 50 Questions took {elapsed:.2f}s (limit: 5s). "
        "ADR-039: creating attempt_questions rows at start must be a single transaction. "
        "A slow result suggests O(n²) behavior or N separate transactions."
    )


def test_list_attempt_questions_many_questions_within_budget(
    tmp_path, monkeypatch
) -> None:
    """
    Performance: list_attempt_questions(attempt_id) for an Attempt with 50 Questions
    must complete within 5 seconds.

    This catches O(n²) scaling in the JOIN (attempt_questions ⨝ questions ⨝
    quiz_questions, ordered by position).

    Trace: ADR-039 §list_attempt_questions; ADR-034 §render_chapter (same scale posture).
    """
    db_path = str(tmp_path / "perf_list.db")
    _bootstrap(monkeypatch, db_path)
    quiz_id, _, _ = _seed_ready_quiz_with_questions(
        db_path, MANDATORY_SECTION_ID, n_questions=50
    )

    from app.persistence import start_attempt, list_attempt_questions  # noqa: PLC0415

    attempt = start_attempt(quiz_id)

    t0 = time.monotonic()
    aq_list = list_attempt_questions(attempt.attempt_id)
    elapsed = time.monotonic() - t0

    assert len(aq_list) == 50, (
        f"list_attempt_questions returned {len(aq_list)} items for 50-question Attempt; "
        "expected 50."
    )
    assert elapsed < 5.0, (
        f"list_attempt_questions with 50 Questions took {elapsed:.2f}s (limit: 5s). "
        "ADR-039: the JOIN query must scale linearly, not quadratically."
    )


# ---------------------------------------------------------------------------
# CSS / AC-9 (styling): quiz.css file exists + section-quiz-take-link rule in lecture.css
# ---------------------------------------------------------------------------


def test_quiz_css_file_exists() -> None:
    """
    AC-9 (TASK-015) / ADR-038 §CSS / UI-2: app/static/quiz.css must exist.

    ADR-038: 'A new file app/static/quiz.css owns the take-page's classes — the
    quiz-take-* namespace.'
    ADR-008 §Future-surfaces: 'a future quiz.css if the surface grows enough to
    warrant its own file' — this is that file.

    Trace: AC-9; ADR-038 §CSS; ADR-008.
    """
    quiz_css = REPO_ROOT / "app" / "static" / "quiz.css"
    assert quiz_css.exists(), (
        f"app/static/quiz.css does not exist at {quiz_css!r}. "
        "AC-9/ADR-038: a new app/static/quiz.css must be created for the take-page "
        "quiz-take-* CSS classes."
    )


def test_quiz_css_contains_quiz_take_namespace() -> None:
    """
    AC-9 (TASK-015) / ADR-038 §CSS: app/static/quiz.css must contain at least one
    quiz-take-* class rule.

    ADR-038: 'the quiz-take-* namespace: .quiz-take, .quiz-take-header,
    .quiz-take-form, .quiz-take-question, …'

    Trace: AC-9; ADR-038 §CSS; ADR-008 §prefix rule.
    """
    quiz_css = REPO_ROOT / "app" / "static" / "quiz.css"
    if not quiz_css.exists():
        pytest.fail(
            "app/static/quiz.css does not exist — cannot check quiz-take-* namespace."
        )
    text = quiz_css.read_text(encoding="utf-8")
    assert "quiz-take" in text, (
        f"app/static/quiz.css does not contain any 'quiz-take' rule. "
        "ADR-038 §CSS: the file must define the quiz-take-* CSS namespace."
    )


def test_lecture_css_contains_section_quiz_take_link_rule() -> None:
    """
    AC-9 (TASK-015) / ADR-038 §CSS: app/static/lecture.css must contain a
    .section-quiz-take-link rule.

    ADR-038: 'the take affordance on the .section-quiz block … reuses the
    section-quiz-* namespace in lecture.css — a new .section-quiz-take-link rule
    in lecture.css.'

    Trace: AC-9; ADR-038 §CSS; ADR-008 (section-* → lecture.css).
    """
    lecture_css = REPO_ROOT / "app" / "static" / "lecture.css"
    assert lecture_css.exists(), (
        f"app/static/lecture.css not found at {lecture_css!r}."
    )
    text = lecture_css.read_text(encoding="utf-8")
    assert "section-quiz-take-link" in text, (
        f"app/static/lecture.css does not contain 'section-quiz-take-link'. "
        "ADR-038: the take-affordance link uses the section-quiz-* namespace in "
        "lecture.css (ADR-008: section-* → lecture.css). A .section-quiz-take-link "
        "rule must be present."
    )


def test_base_html_loads_quiz_css() -> None:
    """
    AC-9 (TASK-015) / ADR-038 §CSS: app/templates/base.html.j2 must load quiz.css.

    ADR-038: 'base.html.j2 loads /static/quiz.css alongside /static/base.css and
    /static/lecture.css (a third <link rel="stylesheet">).'

    Trace: AC-9; ADR-038 §CSS.
    """
    base_template = REPO_ROOT / "app" / "templates" / "base.html.j2"
    assert base_template.exists(), f"base.html.j2 not found at {base_template!r}."
    text = base_template.read_text(encoding="utf-8")
    assert "quiz.css" in text, (
        f"base.html.j2 does not load quiz.css. "
        "ADR-038: base.html.j2 must include a third <link rel='stylesheet'> for "
        "/static/quiz.css so quiz-take-* classes are available on the take page."
    )


def test_quiz_take_template_exists() -> None:
    """
    AC-2 (TASK-015) / ADR-038 §Template: app/templates/quiz_take.html.j2 must exist.

    ADR-038: 'A new template app/templates/quiz_take.html.j2 extending base.html.j2.'

    Trace: AC-2; ADR-038 §Template.
    """
    template = REPO_ROOT / "app" / "templates" / "quiz_take.html.j2"
    assert template.exists(), (
        f"app/templates/quiz_take.html.j2 not found at {template!r}. "
        "ADR-038: the Quiz-taking surface is its own template."
    )
