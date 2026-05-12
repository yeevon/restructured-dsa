"""
TASK-014: Quiz generation — the first Quiz for a Section, fresh-only, via
`ai-workflows`, async, walking a `requested` Quiz to `ready`.

Tests derive from the Acceptance Criteria in
`design_docs/tasks/TASK-014-quiz-generation-first-quiz-fresh-via-ai-workflows.md`
and from the two Accepted ADRs this task lands:
  ADR-036 — `ai-workflows` integration: the project depends on
             `jmdl-ai-workflows` (PyPI); the question-gen workflow is a CS-300-
             owned `WorkflowSpec` at `app/workflows/question_gen.py`; the out-of-
             band processor invokes it by shelling out to `aiw run question_gen …`
             as a subprocess, reading the terminal artefact from stdout; the test
             seam is CS-300's own processor boundary (mock the subprocess call);
             no forbidden LLM/agent SDK import in `app/`; MC-1.
  ADR-037 — Async Quiz-generation processing: an out-of-band `python -m
             app.workflows.process_quiz_requests` command polls `requested`-status
             Quiz rows; `POST .../quiz` route is unchanged (no enqueue) and returns
             303 immediately; failure → `generation_failed` + nullable
             `quizzes.generation_error TEXT` column; the first-Quiz-only guard
             rejects (HTTP 409) a second `requested` request for a Section that
             already has a non-failed Quiz; a `generation_failed` Quiz does NOT
             count against the guard; the "notified" obligation met for this slice
             by the per-Section status-flip to "Ready" (no Notification entity
             ships this task); the processor does NOT re-process `generation_failed`
             rows.

Coverage matrix:
  Boundary:
    - test_processor_happy_path_requested_to_ready:
        The full requested→generating→ready lifecycle; ≥1 questions row persisted.
    - test_processor_happy_path_questions_have_nonempty_prompt:
        Every persisted question has a non-empty prompt (boundary = ≥1 item).
    - test_processor_happy_path_quiz_questions_position_set:
        quiz_questions rows link the Questions to the Quiz with position set ≥1.
    - test_first_quiz_guard_boundary_ready_blocks_second:
        Section with a 'ready' Quiz → POST returns 409 (boundary: exact guard flip).
    - test_first_quiz_guard_boundary_generating_blocks_second:
        Section with a 'generating' Quiz → POST returns 409.
    - test_first_quiz_guard_boundary_generation_failed_allows_retry:
        Section whose only Quiz is 'generation_failed' → POST is allowed (boundary:
        guard does NOT count failed Quizzes).
    - test_first_quiz_guard_requested_blocks_second:
        Section with an existing 'requested' Quiz → POST returns 409.
  Edge:
    - test_processor_failure_empty_artefact_treated_as_failure:
        Empty questions list treated as failure (no questions persisted,
        Quiz → generation_failed).
    - test_processor_does_not_reprocess_generation_failed_rows:
        A 'generation_failed' Quiz is NOT re-processed on a subsequent processor run.
    - test_generation_error_column_is_nullable_for_nonfailed_quizzes:
        generation_error column is NULL for a 'ready' Quiz.
    - test_no_user_id_on_generation_error_column:
        The new quizzes.generation_error column has no accompanying user_id column.
    - test_schema_generation_error_column_exists:
        The quizzes.generation_error column is additive (exists after bootstrap).
    - test_question_gen_output_schema_has_prompt_and_topics_no_choices:
        QuestionGenOutput / GeneratedQuestion schema: prompt + topics fields exist;
        no choice/recall/describe field.
  Negative:
    - test_processor_failure_path_zero_questions_persisted:
        On subprocess failure, zero questions rows are inserted (MC-5 — no
        fabricated Question).
    - test_processor_failure_path_quiz_status_generation_failed:
        On subprocess failure, Quiz status → 'generation_failed' (MC-5).
    - test_processor_failure_path_generation_error_persisted:
        On subprocess failure, quizzes.generation_error is populated.
    - test_route_returns_303_immediately_quiz_still_requested:
        POST .../quiz returns 303 immediately; the Quiz is still 'requested' at
        return time (the processor has NOT run — MC-4 / manifest §6).
    - test_mc1_no_forbidden_lm_sdk_import_in_app:
        Grep `app/` for forbidden LLM/agent SDK imports — assert none (MC-1).
    - test_mc10_no_sqlite3_import_in_workflows:
        Grep `app/workflows/` for `import sqlite3` — assert none (MC-10 extended).
    - test_mc10_no_sql_literals_in_workflows:
        Grep `app/workflows/` for SQL string literals — assert none (MC-10).
    - test_no_user_id_on_new_persistence_functions:
        New persistence functions / the processor never introduce a user_id concept.
  Performance:
    - test_processor_happy_path_with_multiple_questions_within_budget:
        Processing a Quiz with 5 generated questions persists them all within 5s.
        (Scale surface: the processor iterates the questions list; catches O(n²)
        if the implementer does one INSERT per question in a per-question transaction
        with an extra SELECT each time.)

Notes on the test seam (per ADR-036 §The test seam):
  The processor invokes the workflow via `subprocess.run` (or a thin wrapper such
  as `_invoke_question_gen`). Tests mock that seam at the CS-300 processor boundary —
  NOT the framework's in-process `StubLLMAdapter`, which cannot reach a subprocess.

  A success-path mock returns a canned artefact whose stdout matches the `aiw run`
  documented contract:
    json.dumps({"questions": [{"prompt": "...", "topics": ["..."]}]}, indent=2)
    + "\\ntotal cost: $0.0012"
  A failure-path mock returns a CompletedProcess with returncode=1 and
  stderr="error: LLM call timed out" (or raises subprocess.SubprocessError).

pytestmark registers all tests under task("TASK-014").

ASSUMPTIONS:
  ASSUMPTION: The processor module lives at `app.workflows.process_quiz_requests`
    (ADR-037 §Decision) with a callable entry point (e.g. `process_pending()` or
    `main()`) that can be called directly in tests with the subprocess seam mocked.
    If the module's entry point is named differently, the ImportError will be the
    failing signal (the test is still red for the right reason).

  ASSUMPTION: The thin helper the processor uses to invoke the workflow is named
    `_invoke_question_gen` (ADR-036 §How application code invokes the workflow,
    pseudocode) and lives in a module importable as `app.workflows.process_quiz_requests`
    or a sibling module. Tests mock at `subprocess.run` in the `app.workflows`
    package namespace as a fallback if `_invoke_question_gen` is not directly importable.

  ASSUMPTION: `app.persistence` exports the TASK-014 persistence functions
    (mark_quiz_generating, mark_quiz_ready, mark_quiz_generation_failed,
    add_questions_to_quiz, list_requested_quizzes) — the test imports them from
    `app.persistence` (the single-import surface per ADR-022). If they are not yet
    exported, the ImportError / AttributeError is the failing signal.

  ASSUMPTION: `app.workflows.question_gen` exports (or makes importable):
    `QuestionGenOutput` — a pydantic model whose first field is `questions:
    list[GeneratedQuestion]`; `GeneratedQuestion` has `prompt: str` and
    `topics: list[str]`, no `choices`/`correct_choice`/`answer_text`/`recall_*`/
    `describe_*` field.
"""

from __future__ import annotations

import json
import pathlib
import re
import sqlite3
import subprocess
import time
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.task("TASK-014")

REPO_ROOT = pathlib.Path(__file__).parent.parent

# ---------------------------------------------------------------------------
# Chapter / Section IDs from the corpus
# ---------------------------------------------------------------------------

MANDATORY_CHAPTER_ID = "ch-01-cpp-refresher"
OPTIONAL_CHAPTER_ID = "ch-07-heaps-and-treaps"

SECTION_ID_CH01_S1 = "ch-01-cpp-refresher#section-1-1"
SECTION_ID_CH01_S2 = "ch-01-cpp-refresher#section-1-2"

MANDATORY_FIRST_SECTION = "1-1"

# ---------------------------------------------------------------------------
# aiw run stdout contract (ADR-036 §The aiw run CLI's stdout contract)
# The artefact is json.dumps(artifact, indent=2) followed by a `total cost: $X`
# line; structured logs go to stderr (not stdout).
# ---------------------------------------------------------------------------


def _make_success_stdout(questions: list[dict]) -> str:
    """
    Build the stdout that `aiw run question_gen` would produce on a successful run.
    ADR-036: `json.dumps(artifact, indent=2)` then `total cost: $X.XXXX`.
    The artefact is `{"questions": [{"prompt": "...", "topics": [...]}, ...]}`.
    """
    artefact = {"questions": questions}
    return json.dumps(artefact, indent=2) + "\ntotal cost: $0.0012\n"


def _make_completed_process(
    stdout: str = "",
    stderr: str = "",
    returncode: int = 0,
) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(
        args=["aiw", "run", "question_gen"],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


# ---------------------------------------------------------------------------
# Helpers — deferred imports so collection succeeds before implementation exists
# ---------------------------------------------------------------------------


def _bootstrap_and_make_client(monkeypatch, db_path: str):
    """Bootstrap the DB and return a FastAPI TestClient."""
    monkeypatch.setenv("NOTES_DB_PATH", db_path)
    from fastapi.testclient import TestClient  # noqa: PLC0415
    from app.main import app  # noqa: PLC0415
    client = TestClient(app)
    client.get(f"/lecture/{MANDATORY_CHAPTER_ID}")
    return client


def _get_table_columns(db_path: str, table: str) -> set[str]:
    conn = sqlite3.connect(db_path)
    cur = conn.execute(f"PRAGMA table_info({table})")
    cols = {row[1] for row in cur.fetchall()}
    conn.close()
    return cols


def _db_rows(db_path: str, sql: str, params=()) -> list[dict]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.execute(sql, params)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def _run_processor(monkeypatch, db_path: str, mock_return):
    """
    Import the processor module and invoke it with the subprocess call mocked.

    The processor is `app.workflows.process_quiz_requests`.  Its entry point is
    assumed to be a `process_pending()` or `main()` callable (ASSUMPTION above).
    The subprocess seam is `subprocess.run` inside `app.workflows` (or a thin
    `_invoke_question_gen` wrapper).

    `mock_return` is either a `subprocess.CompletedProcess` (for success / failure
    paths) or an exception class to raise.
    """
    monkeypatch.setenv("NOTES_DB_PATH", db_path)

    # Determine how to mock: the processor may use subprocess.run directly or via
    # a thin helper.  We mock subprocess.run in the app.workflows namespace.
    # If the processor uses a named wrapper, it will still import subprocess.run.
    if isinstance(mock_return, type) and issubclass(mock_return, Exception):
        side_effect = mock_return("mocked failure")
        mock_rv = None
    else:
        side_effect = None
        mock_rv = mock_return

    with patch("subprocess.run", return_value=mock_rv, side_effect=side_effect):
        import app.workflows.process_quiz_requests as proc_module  # noqa: PLC0415
        # Try common entry-point names:
        if hasattr(proc_module, "process_pending"):
            proc_module.process_pending()
        elif hasattr(proc_module, "main"):
            proc_module.main()
        elif hasattr(proc_module, "run"):
            proc_module.run()
        else:
            pytest.fail(
                "app.workflows.process_quiz_requests has no callable entry point "
                "(process_pending / main / run). ADR-037: the processor module is "
                "a `__main__` module with an entry point callable for testing."
            )


# ===========================================================================
# AC-1 — Happy-path: requested → generating → ready, Questions persisted,
#         quiz_questions rows created, surface shows "Ready"
# Trace: TASK-014 AC-1; ADR-036 §Decision; ADR-037 §Decision
# ===========================================================================


def test_processor_happy_path_requested_to_ready(tmp_path, monkeypatch) -> None:
    """
    AC-1 (TASK-014): given a Section with a `requested`-status Quiz and an empty
    Question Bank, when the processor runs (with the subprocess mocked to return a
    successful artefact), then the Quiz transitions requested→generating→ready,
    ≥1 questions row is persisted, and quiz_questions rows link them to the Quiz.

    ADR-036 §The test seam: mock subprocess.run to return the canned artefact.
    ADR-037 §Decision: the processor walks the lifecycle.

    Trace: AC-1; ADR-036; ADR-037 §Decision.
    """
    db_path = str(tmp_path / "happy.db")
    client = _bootstrap_and_make_client(monkeypatch, db_path)

    # Create a requested Quiz via the existing route
    client.post(
        f"/lecture/{MANDATORY_CHAPTER_ID}/sections/{MANDATORY_FIRST_SECTION}/quiz",
        follow_redirects=False,
    )

    # Verify there is a requested Quiz row
    rows = _db_rows(db_path, "SELECT quiz_id, status FROM quizzes")
    assert len(rows) == 1 and rows[0]["status"] == "requested", (
        "Prerequisite: expected exactly one 'requested' Quiz before running the processor."
    )
    quiz_id = rows[0]["quiz_id"]

    # Mock the subprocess to return a successful artefact
    success_stdout = _make_success_stdout([
        {"prompt": "Implement a hash table with open addressing.", "topics": ["hashing", "arrays"]},
        {"prompt": "Write a binary search function.", "topics": ["search", "binary-search"]},
    ])
    mock_proc = _make_completed_process(stdout=success_stdout)
    _run_processor(monkeypatch, db_path, mock_proc)

    # Assert: Quiz is now 'ready'
    quiz_rows = _db_rows(db_path, "SELECT status FROM quizzes WHERE quiz_id = ?", (quiz_id,))
    assert quiz_rows and quiz_rows[0]["status"] == "ready", (
        f"After processor ran with a successful artefact, the Quiz (quiz_id={quiz_id}) "
        f"has status={(repr(quiz_rows[0]['status']) if quiz_rows else 'NOT FOUND')}; "
        "expected 'ready'. "
        "AC-1/ADR-037: the lifecycle must walk requested→generating→ready."
    )

    # Assert: ≥1 questions row persisted
    question_rows = _db_rows(db_path, "SELECT question_id, prompt, section_id FROM questions")
    assert len(question_rows) >= 1, (
        f"After processor ran successfully, found {len(question_rows)} questions rows; "
        "expected ≥1. "
        "AC-1: at least one Question must be persisted to the Section's Question Bank."
    )

    # Assert: quiz_questions rows exist
    qq_rows = _db_rows(
        db_path,
        "SELECT quiz_id, question_id, position FROM quiz_questions WHERE quiz_id = ?",
        (quiz_id,),
    )
    assert len(qq_rows) >= 1, (
        f"After processor ran successfully, found {len(qq_rows)} quiz_questions rows "
        f"for quiz_id={quiz_id}; expected ≥1. "
        "AC-1/ADR-036: quiz_questions rows must link Questions to the Quiz."
    )


def test_processor_happy_path_questions_have_nonempty_prompt(tmp_path, monkeypatch) -> None:
    """
    AC-1 (TASK-014): every persisted Question must have a non-empty prompt.

    ADR-036: the processor validates that ≥1 item with a non-empty `prompt` came back;
    an empty `questions` list or a prompt-less item is treated as failure.

    Trace: AC-1; ADR-036 §The orchestration boundary.
    """
    db_path = str(tmp_path / "nonempty_prompt.db")
    client = _bootstrap_and_make_client(monkeypatch, db_path)

    client.post(
        f"/lecture/{MANDATORY_CHAPTER_ID}/sections/{MANDATORY_FIRST_SECTION}/quiz",
        follow_redirects=False,
    )

    success_stdout = _make_success_stdout([
        {"prompt": "Implement a stack using an array.", "topics": ["stack", "arrays"]},
    ])
    mock_proc = _make_completed_process(stdout=success_stdout)
    _run_processor(monkeypatch, db_path, mock_proc)

    question_rows = _db_rows(db_path, "SELECT prompt FROM questions")
    assert len(question_rows) >= 1, (
        "No questions persisted; cannot check prompt content."
    )
    for row in question_rows:
        assert row["prompt"] and row["prompt"].strip(), (
            f"A persisted Question has an empty prompt: {row['prompt']!r}. "
            "AC-1/ADR-036: every persisted Question must have a non-empty prompt — "
            "the processor must validate the artefact before writing."
        )


def test_processor_happy_path_quiz_questions_position_set(tmp_path, monkeypatch) -> None:
    """
    AC-1 (TASK-014): quiz_questions rows must have position set (≥1).

    ADR-036: `add_questions_to_quiz` uses 1-based position.

    Trace: AC-1; ADR-036 §The orchestration boundary ('position set').
    """
    db_path = str(tmp_path / "position.db")
    client = _bootstrap_and_make_client(monkeypatch, db_path)

    client.post(
        f"/lecture/{MANDATORY_CHAPTER_ID}/sections/{MANDATORY_FIRST_SECTION}/quiz",
        follow_redirects=False,
    )

    success_stdout = _make_success_stdout([
        {"prompt": "Implement a queue using two stacks.", "topics": ["queue", "stacks"]},
        {"prompt": "Implement a linked list with O(1) prepend.", "topics": ["linked-list"]},
    ])
    mock_proc = _make_completed_process(stdout=success_stdout)
    _run_processor(monkeypatch, db_path, mock_proc)

    qq_rows = _db_rows(db_path, "SELECT position FROM quiz_questions")
    assert len(qq_rows) >= 1, "No quiz_questions rows found."
    for row in qq_rows:
        assert row["position"] is not None and row["position"] >= 1, (
            f"quiz_questions row has position={row['position']!r}; expected ≥1. "
            "AC-1/ADR-036: quiz_questions.position must be set (1-based)."
        )


def test_processor_happy_path_questions_section_id_matches(tmp_path, monkeypatch) -> None:
    """
    AC-1 / AC-6 (TASK-014): every persisted Question must have section_id equal
    to the Section the Quiz belongs to (MC-2 — exactly one Section).

    ADR-036: `add_questions_to_quiz` takes `section_id` from the Quiz's section_id.

    Trace: AC-1; AC-6; ADR-036 §The orchestration boundary; MC-2.
    """
    db_path = str(tmp_path / "section_id_match.db")
    client = _bootstrap_and_make_client(monkeypatch, db_path)

    client.post(
        f"/lecture/{MANDATORY_CHAPTER_ID}/sections/{MANDATORY_FIRST_SECTION}/quiz",
        follow_redirects=False,
    )

    success_stdout = _make_success_stdout([
        {"prompt": "Implement a binary search tree insert.", "topics": ["BST"]},
    ])
    mock_proc = _make_completed_process(stdout=success_stdout)
    _run_processor(monkeypatch, db_path, mock_proc)

    # The expected section_id from ADR-002: chapter_id#section-n-m
    expected_section_id = SECTION_ID_CH01_S1
    question_rows = _db_rows(db_path, "SELECT section_id FROM questions")
    assert len(question_rows) >= 1, "No questions persisted."
    for row in question_rows:
        assert row["section_id"] == expected_section_id, (
            f"Question has section_id={row['section_id']!r}; "
            f"expected {expected_section_id!r}. "
            "AC-1/AC-6/MC-2: every Question generated for a Section must carry "
            "that Section's section_id — no cross-Section composition."
        )


# ===========================================================================
# AC-1 — Surface shows "Ready" after processor walk
# Trace: AC-1; ADR-034 §What the surface renders (populated case)
# ===========================================================================


def test_processor_happy_path_surface_shows_ready(tmp_path, monkeypatch) -> None:
    """
    AC-1 (TASK-014): after the processor walks a Quiz to 'ready', the per-Section
    Quiz surface on GET /lecture/{chapter_id} must show the Quiz's status as "Ready".

    ADR-034 §Populated case: `ready` → "Ready" (with no takeable affordance — the
    Quiz-taking surface is a later slice).

    Trace: AC-1; ADR-034 §Populated case; MC-5 (surface never fabricates).
    """
    db_path = str(tmp_path / "surface_ready.db")
    client = _bootstrap_and_make_client(monkeypatch, db_path)

    client.post(
        f"/lecture/{MANDATORY_CHAPTER_ID}/sections/{MANDATORY_FIRST_SECTION}/quiz",
        follow_redirects=False,
    )

    success_stdout = _make_success_stdout([
        {"prompt": "Implement a min-heap.", "topics": ["heaps"]},
    ])
    mock_proc = _make_completed_process(stdout=success_stdout)
    _run_processor(monkeypatch, db_path, mock_proc)

    response = client.get(f"/lecture/{MANDATORY_CHAPTER_ID}")
    assert response.status_code == 200
    html = response.text

    # The surface must show the "Ready" state
    ready_signalled = (
        "section-quiz-item--ready" in html
        or "Ready" in html
    )
    assert ready_signalled, (
        f"After the processor walked the Quiz to 'ready', GET /lecture/{MANDATORY_CHAPTER_ID} "
        "does not show the 'Ready' status in the HTML. "
        "AC-1/ADR-034: when a Quiz reaches 'ready', the per-Section surface must render "
        "'Ready' (no takeable affordance — the take-button is a later slice)."
    )

    # MUST NOT show a take-button (ADR-034 commitment: no takeable affordance this task)
    assert "take-quiz" not in html.lower() and "take quiz" not in html.lower(), (
        "The rendered page contains 'take quiz' text after a Quiz reaches 'ready'. "
        "ADR-034: 'no takeable affordance ships … even for a `ready` Quiz' — "
        "the Quiz-taking surface is a later slice (TASK-014 must not add a take-button)."
    )


# ===========================================================================
# AC-2 — MC-1: no forbidden LLM/agent SDK import in app/
# Trace: TASK-014 AC-2; ADR-036 §The forbidden-SDK list; MC-1 (active per ADR-036)
# ===========================================================================


# The forbidden SDK package names enumerated in ADR-036 §The forbidden-SDK list
# and reflected into SKILL.md MC-1 (active per ADR-036, Accepted 2026-05-12).
_FORBIDDEN_SDK_PATTERNS = [
    r"\bimport openai\b",
    r"\bfrom openai\b",
    r"\bimport anthropic\b",
    r"\bfrom anthropic\b",
    r"\bimport google\.generativeai\b",
    r"\bfrom google\.generativeai\b",
    r"\bimport google\.genai\b",
    r"\bfrom google\.genai\b",
    r"\bimport cohere\b",
    r"\bfrom cohere\b",
    r"\bimport mistralai\b",
    r"\bfrom mistralai\b",
    r"\bimport groq\b",
    r"\bfrom groq\b",
    r"\bimport together\b",
    r"\bfrom together\b",
    r"\bimport replicate\b",
    r"\bfrom replicate\b",
    r"\bimport litellm\b",
    r"\bfrom litellm\b",
    r"\bimport langchain\b",
    r"\bfrom langchain\b",
    r"\bimport langgraph\b",
    r"\bfrom langgraph\b",
]


def test_mc1_no_forbidden_lm_sdk_import_in_app() -> None:
    """
    AC-2 (TASK-014) / MC-1 (architecture portion now ACTIVE per ADR-036 Accepted
    2026-05-12): application code under `app/` must NOT import any forbidden
    LLM/agent SDK.

    ADR-036 §The forbidden-SDK list: `openai`, `anthropic`, `google.generativeai`,
    `google.genai`, `cohere`, `mistralai`, `groq`, `together`, `replicate`,
    `litellm`, `langchain*`, `langgraph*`. The only AI import in `app/` is
    `ai_workflows.*`; AI invocation goes through the `aiw` CLI subprocess.

    Grepping all .py files under `app/`.

    Trace: AC-2; ADR-036 §The forbidden-SDK list; MC-1 (blocker, architecture
    portion active); Manifest §4 (ai-workflows is the only AI engine commitment).
    """
    app_dir = REPO_ROOT / "app"
    compiled = [re.compile(p) for p in _FORBIDDEN_SDK_PATTERNS]
    violations: list[str] = []

    for py_file in sorted(app_dir.rglob("*.py")):
        text = py_file.read_text(encoding="utf-8")
        for pattern in compiled:
            if pattern.search(text):
                violations.append(f"{py_file}: matched {pattern.pattern!r}")

    assert violations == [], (
        f"MC-1 BLOCKER: forbidden LLM/agent SDK import(s) found in `app/`:\n"
        + "\n".join(f"  {v}" for v in violations)
        + "\n\nADR-036 §The forbidden-SDK list / MC-1 (active per ADR-036, Accepted "
        "2026-05-12): application code must not import these SDKs directly. "
        "All AI work goes through `ai_workflows.*`; invocation via `aiw run` subprocess."
    )


# ===========================================================================
# AC-3 — Out-of-band-ness: POST route returns 303 immediately; Quiz still 'requested'
# Trace: TASK-014 AC-3; ADR-037 §The trigger handoff; MC-4; Manifest §6
# ===========================================================================


def test_route_returns_303_immediately_quiz_still_requested(tmp_path, monkeypatch) -> None:
    """
    AC-3 (TASK-014) / MC-4 / Manifest §6: when `POST .../quiz` is hit, the
    response is the existing 303 PRG redirect returned immediately — the AI
    generation call has NOT run inside the request handler; the Quiz is still
    'requested' at the moment the route returns.

    ADR-037 §The trigger handoff: the route does no enqueue, no signal, no
    fire-and-forget. It records the `requested` row and returns 303. Period.

    This test also verifies no AI subprocess was launched during the request:
    we patch subprocess.run to raise if called, then assert the POST succeeds.

    Trace: AC-3; ADR-037 §The trigger handoff; MC-4; Manifest §6 'AI work is
    asynchronous from the learner's perspective'.
    """
    db_path = str(tmp_path / "out_of_band.db")
    monkeypatch.setenv("NOTES_DB_PATH", db_path)

    # Patch subprocess.run to raise if any subprocess is spawned during the POST
    subprocess_was_called = []

    def _raise_if_called(*args, **kwargs):
        subprocess_was_called.append(args)
        raise AssertionError(
            "subprocess.run was called during the POST /lecture/.../quiz request. "
            "AC-3/MC-4: no AI processing must happen inside the request handler. "
            "The processor runs out-of-band (a separate manual command, ADR-037)."
        )

    with patch("subprocess.run", side_effect=_raise_if_called):
        from fastapi.testclient import TestClient  # noqa: PLC0415
        from app.main import app  # noqa: PLC0415
        client = TestClient(app)
        client.get(f"/lecture/{MANDATORY_CHAPTER_ID}")

        response = client.post(
            f"/lecture/{MANDATORY_CHAPTER_ID}/sections/{MANDATORY_FIRST_SECTION}/quiz",
            follow_redirects=False,
        )

    # Route must return 303 (unchanged per ADR-037)
    assert response.status_code == 303, (
        f"POST .../quiz returned {response.status_code}; expected 303. "
        "AC-3/ADR-034/ADR-037: the route is unchanged — it still returns a 303 PRG redirect."
    )

    # Quiz must still be 'requested' (the processor has not run)
    rows = _db_rows(db_path, "SELECT status FROM quizzes")
    assert rows and rows[0]["status"] == "requested", (
        f"After POST, the Quiz has status={(repr(rows[0]['status']) if rows else 'NOT FOUND')}; "
        "expected 'requested'. "
        "AC-3/MC-4: the Quiz must remain 'requested' until the out-of-band processor runs."
    )

    # Confirm subprocess was NOT called during the request
    assert subprocess_was_called == [], (
        "subprocess.run was called during the POST request, violating MC-4. "
        "The out-of-band processor must run in a separate process, not inside the request."
    )


# ===========================================================================
# AC-4 — Failure path: generation_failed, no questions synthesized, surface shows
#         "Generation failed", processor does not re-process generation_failed rows
# Trace: TASK-014 AC-4; ADR-036 §Failure is a non-zero exit; ADR-037 §Failure;
#        MC-5; Manifest §6 'AI failures are visible'
# ===========================================================================


def test_processor_failure_path_quiz_status_generation_failed(tmp_path, monkeypatch) -> None:
    """
    AC-4 (TASK-014) / MC-5: when the subprocess returns a non-zero exit, the Quiz
    transitions to `generation_failed`.

    ADR-037 §Failure: 'on a non-zero aiw run exit / an error: ... on stderr (or
    the artefact is empty / fails CS-300's sanity check): mark_quiz_generation_failed(quiz_id, error=...)'

    Trace: AC-4; ADR-037 §Failure; MC-5.
    """
    db_path = str(tmp_path / "failure_status.db")
    client = _bootstrap_and_make_client(monkeypatch, db_path)

    client.post(
        f"/lecture/{MANDATORY_CHAPTER_ID}/sections/{MANDATORY_FIRST_SECTION}/quiz",
        follow_redirects=False,
    )

    rows = _db_rows(db_path, "SELECT quiz_id FROM quizzes")
    quiz_id = rows[0]["quiz_id"]

    # Mock: subprocess returns non-zero exit with error on stderr
    failure_proc = _make_completed_process(
        stdout="",
        stderr="error: LLM call timed out after 30s",
        returncode=1,
    )
    _run_processor(monkeypatch, db_path, failure_proc)

    quiz_rows = _db_rows(db_path, "SELECT status FROM quizzes WHERE quiz_id = ?", (quiz_id,))
    assert quiz_rows and quiz_rows[0]["status"] == "generation_failed", (
        f"After subprocess failure, Quiz status={(repr(quiz_rows[0]['status']) if quiz_rows else 'NOT FOUND')}; "
        "expected 'generation_failed'. "
        "AC-4/MC-5/ADR-037: a non-zero aiw run exit must walk the Quiz to 'generation_failed'."
    )


def test_processor_failure_path_zero_questions_persisted(tmp_path, monkeypatch) -> None:
    """
    AC-4 (TASK-014) / MC-5: when the subprocess fails, zero questions rows must be
    persisted for that Quiz (no fabricated / placeholder Question).

    ADR-037: 'No fabricated Questions'. MC-5: 'The system never substitutes a
    placeholder grade, fabricated Question, or stand-in Notification.'

    Trace: AC-4; ADR-037 §Failure; MC-5; Manifest §6 'AI failures are visible …
    never fabricates a result'.
    """
    db_path = str(tmp_path / "failure_no_questions.db")
    client = _bootstrap_and_make_client(monkeypatch, db_path)

    client.post(
        f"/lecture/{MANDATORY_CHAPTER_ID}/sections/{MANDATORY_FIRST_SECTION}/quiz",
        follow_redirects=False,
    )

    failure_proc = _make_completed_process(
        stdout="",
        stderr="error: provider rate-limit exceeded",
        returncode=1,
    )
    _run_processor(monkeypatch, db_path, failure_proc)

    question_rows = _db_rows(db_path, "SELECT question_id FROM questions")
    assert question_rows == [], (
        f"After subprocess failure, {len(question_rows)} questions row(s) were persisted; "
        "expected 0. "
        "AC-4/MC-5/ADR-037: on a failed generation, NO Questions must be written to the "
        "Question Bank. Fabricating a placeholder Question is a hard violation of MC-5."
    )


def test_processor_failure_path_generation_error_persisted(tmp_path, monkeypatch) -> None:
    """
    AC-4 (TASK-014) / ADR-037 §Failure: when the subprocess fails, the
    `quizzes.generation_error` column must be populated with the error detail.

    ADR-037: 'the detail persisted in a new nullable `quizzes.generation_error TEXT`
    column … mark_quiz_generation_failed(quiz_id, error=<the stderr error: message>)'.

    Trace: AC-4; ADR-037 §Failure-handling discipline; MC-5.
    """
    db_path = str(tmp_path / "failure_error_column.db")
    client = _bootstrap_and_make_client(monkeypatch, db_path)

    client.post(
        f"/lecture/{MANDATORY_CHAPTER_ID}/sections/{MANDATORY_FIRST_SECTION}/quiz",
        follow_redirects=False,
    )

    error_text = "error: schema validation failed: 'prompt' field missing"
    failure_proc = _make_completed_process(
        stdout="",
        stderr=error_text,
        returncode=1,
    )
    _run_processor(monkeypatch, db_path, failure_proc)

    quiz_rows = _db_rows(db_path, "SELECT status, generation_error FROM quizzes")
    assert quiz_rows, "No Quiz row found."
    row = quiz_rows[0]

    assert row["status"] == "generation_failed", (
        f"Quiz status={row['status']!r}; expected 'generation_failed'."
    )
    # The generation_error column must be populated (non-empty)
    assert row["generation_error"] is not None and row["generation_error"].strip(), (
        f"quizzes.generation_error={row['generation_error']!r}; expected a non-empty "
        "error string (the error detail from stderr). "
        "AC-4/ADR-037: the failure detail must be persisted in generation_error for "
        "the author to read (it is a debugging aid, not the learner-facing message)."
    )


def test_processor_failure_path_surface_shows_generation_failed(tmp_path, monkeypatch) -> None:
    """
    AC-4 (TASK-014) / MC-5: after a failed generation, the per-Section Quiz surface
    must show "Generation failed".

    ADR-034 §Populated case: `generation_failed` → "Generation failed".
    MC-5: 'the failure is delivered to the learner as a failure.'

    Trace: AC-4; ADR-034 §Populated case; MC-5.
    """
    db_path = str(tmp_path / "failure_surface.db")
    client = _bootstrap_and_make_client(monkeypatch, db_path)

    client.post(
        f"/lecture/{MANDATORY_CHAPTER_ID}/sections/{MANDATORY_FIRST_SECTION}/quiz",
        follow_redirects=False,
    )

    failure_proc = _make_completed_process(
        stdout="",
        stderr="error: LLM provider returned 503",
        returncode=1,
    )
    _run_processor(monkeypatch, db_path, failure_proc)

    response = client.get(f"/lecture/{MANDATORY_CHAPTER_ID}")
    assert response.status_code == 200
    html = response.text

    failed_signalled = (
        "section-quiz-item--generation_failed" in html
        or "Generation failed" in html
        or "generation_failed" in html
    )
    assert failed_signalled, (
        f"After a failed generation, GET /lecture/{MANDATORY_CHAPTER_ID} does not show "
        "the 'Generation failed' status. "
        "AC-4/MC-5/ADR-034: when a Quiz reaches 'generation_failed', the per-Section "
        "surface must render 'Generation failed' (honest signal — never fabricated)."
    )


def test_processor_does_not_reprocess_generation_failed_rows(tmp_path, monkeypatch) -> None:
    """
    AC-4 (TASK-014) / MC-5: the processor must NOT re-process `generation_failed`
    rows on a subsequent run — a `generation_failed` Quiz stays `generation_failed`.

    ADR-037: 'The CS-300 command does not re-process generation_failed rows on a
    later run (a generation_failed row stays generation_failed).'
    MC-5: 'silent retries that mask permanent failure' are forbidden.

    Boundary note: ADR-037 explicitly says re-processing is 'the bug to avoid'. A
    second run with a now-success mock must leave the generation_failed row unchanged.

    Trace: AC-4 (no unbounded silent retry); ADR-037 §Decision; MC-5.
    """
    db_path = str(tmp_path / "no_reprocess.db")
    client = _bootstrap_and_make_client(monkeypatch, db_path)

    client.post(
        f"/lecture/{MANDATORY_CHAPTER_ID}/sections/{MANDATORY_FIRST_SECTION}/quiz",
        follow_redirects=False,
    )
    quiz_id_row = _db_rows(db_path, "SELECT quiz_id FROM quizzes")[0]
    quiz_id = quiz_id_row["quiz_id"]

    # First run: fail → generation_failed
    failure_proc = _make_completed_process(
        stdout="", stderr="error: timeout", returncode=1
    )
    _run_processor(monkeypatch, db_path, failure_proc)

    # Confirm failure
    after_first = _db_rows(
        db_path, "SELECT status FROM quizzes WHERE quiz_id = ?", (quiz_id,)
    )
    assert after_first and after_first[0]["status"] == "generation_failed", (
        "Prerequisite: expected 'generation_failed' after first (failing) processor run."
    )

    # Second run: mock returns success — but the processor must NOT re-process the
    # generation_failed row.
    success_stdout = _make_success_stdout([
        {"prompt": "Implement a deque.", "topics": ["deque"]},
    ])
    success_proc = _make_completed_process(stdout=success_stdout)
    _run_processor(monkeypatch, db_path, success_proc)

    after_second = _db_rows(
        db_path, "SELECT status FROM quizzes WHERE quiz_id = ?", (quiz_id,)
    )
    assert after_second and after_second[0]["status"] == "generation_failed", (
        f"After a second processor run, the 'generation_failed' Quiz has "
        f"status={after_second[0]['status']!r}; expected it to remain 'generation_failed'. "
        "AC-4/MC-5/ADR-037: the processor must NOT re-process generation_failed rows — "
        "a silent re-attempt on a permanently-failed row masks the failure (MC-5 violation)."
    )

    # Also confirm no questions were written in the second run
    question_rows = _db_rows(db_path, "SELECT question_id FROM questions")
    assert question_rows == [], (
        f"After the second (would-be-successful) processor run, {len(question_rows)} "
        "questions row(s) were found; expected 0. "
        "The processor must not write questions for a generation_failed Quiz."
    )


# ===========================================================================
# AC-5 — Every generated Question is a hands-on coding task (no non-coding format)
# Trace: TASK-014 AC-5; ADR-036 §Where the CS-300 workflow module lives (GeneratedQuestion);
#        Manifest §5 'No non-coding Question formats'; §7 'Every Question is a coding task'
# ===========================================================================


def test_question_gen_output_schema_has_prompt_and_topics_no_choices() -> None:
    """
    AC-5 (TASK-014): the `QuestionGenOutput` / `GeneratedQuestion` schema in
    `app/workflows/question_gen.py` must have a `prompt` field and a `topics`
    field and NO field named `choices`/`correct_choice`/`answer_text` or matching
    `*choice*`/`*recall*`/`*describe*`.

    ADR-036 §Where the CS-300 workflow module lives: 'No option_* / correct_choice /
    answer_text / describe_* / recall_* / `choices` field anywhere in QuestionGenOutput
    or GeneratedQuestion — the schema makes a non-coding Question impossible to express.'

    Manifest §5: 'No non-coding Question formats. No multiple-choice, no true/false,
    no short-answer, no describe-the-concept.' §7: 'Every Question is a hands-on
    coding task.'

    Trace: AC-5; ADR-036 §Workflow module; Manifest §5 Non-Goals; §7 Invariants.
    """
    from app.workflows.question_gen import QuestionGenOutput, GeneratedQuestion  # noqa: PLC0415

    # Check QuestionGenOutput has 'questions' as its first field (framework's
    # FINAL_STATE_KEY convention — ADR-036)
    output_fields = list(QuestionGenOutput.model_fields.keys())
    assert "questions" in output_fields, (
        f"QuestionGenOutput has fields {output_fields!r}; expected 'questions' as the "
        "first field. ADR-036: the first field of output_schema is the terminal artefact "
        "(the framework's FINAL_STATE_KEY convention)."
    )
    assert output_fields[0] == "questions", (
        f"QuestionGenOutput's first field is {output_fields[0]!r}; expected 'questions'. "
        "ADR-036: the first field of output_schema becomes the terminal artefact."
    )

    # Check GeneratedQuestion has prompt and topics
    question_fields = set(GeneratedQuestion.model_fields.keys())
    assert "prompt" in question_fields, (
        f"GeneratedQuestion fields: {question_fields!r}. "
        "AC-5/ADR-036: GeneratedQuestion must have a 'prompt' field (the coding-task instruction)."
    )
    assert "topics" in question_fields, (
        f"GeneratedQuestion fields: {question_fields!r}. "
        "AC-5/ADR-036: GeneratedQuestion must have a 'topics' field (Topic-tag list)."
    )

    # Check for forbidden non-coding-task fields
    forbidden_substrings = ["choice", "recall", "describe", "answer_text", "option_"]
    violations = [
        field
        for field in question_fields
        if any(pat in field.lower() for pat in forbidden_substrings)
    ]
    assert violations == [], (
        f"GeneratedQuestion has forbidden non-coding-task field(s): {violations!r}. "
        "AC-5/ADR-036/Manifest §5/§7: the schema must NOT admit non-coding Question "
        "formats. No choices, no correct_choice, no answer_text, no recall_*, no describe_*. "
        "A non-coding Question must be unexpressible in the schema."
    )


def test_question_gen_output_schema_on_quizzes_table(tmp_path, monkeypatch) -> None:
    """
    AC-5 (TASK-014): the `questions` table (ADR-033) must have no choice/recall/
    describe column (confirming the schema from TASK-013 is unchanged on this point).

    ADR-036 §Workflow module: 'mirroring how ADR-033's questions table has no such
    column (manifest §5/§7).'

    Trace: AC-5; ADR-033 §Table set; ADR-036; Manifest §5/§7.
    """
    db_path = str(tmp_path / "schema_unchanged.db")
    _bootstrap_and_make_client(monkeypatch, db_path)

    cols = _get_table_columns(db_path, "questions")
    forbidden_patterns = ["option_", "correct_choice", "answer_text", "describe_", "recall_", "choices"]
    violations = [
        col for col in cols
        if any(pat in col.lower() for pat in forbidden_patterns)
    ]
    assert violations == [], (
        f"The `questions` table carries non-coding-task column(s): {violations!r}. "
        "AC-5/ADR-033/ADR-036/Manifest §5/§7: the schema must not admit non-coding "
        "Question formats. No option_*, correct_choice, answer_text, choices, "
        "describe_*, or recall_* columns."
    )


# ===========================================================================
# AC-6 — MC-2: every Question linked to the Quiz references exactly one Section
# Trace: TASK-014 AC-6; ADR-036 §The orchestration boundary; MC-2; Manifest §6/§7
# ===========================================================================


def test_no_cross_section_questions_in_quiz(tmp_path, monkeypatch) -> None:
    """
    AC-6 (TASK-014) / MC-2: every Question linked to a Quiz must have the same
    section_id as the Quiz.  No cross-Section composition is allowed.

    ADR-036: 'add_questions_to_quiz … section_id taken from the Quiz's section_id
    (so the Question lands in the Section's Bank — MC-2: exactly one Section).'

    Trace: AC-6; ADR-036 §The orchestration boundary; MC-2; Manifest §6 'Quizzes
    scope to Sections; …'; §7 'A Quiz is bound to exactly one Section.'
    """
    db_path = str(tmp_path / "no_cross_section.db")
    client = _bootstrap_and_make_client(monkeypatch, db_path)

    client.post(
        f"/lecture/{MANDATORY_CHAPTER_ID}/sections/{MANDATORY_FIRST_SECTION}/quiz",
        follow_redirects=False,
    )

    success_stdout = _make_success_stdout([
        {"prompt": "Implement a trie.", "topics": ["trie", "strings"]},
        {"prompt": "Implement a segment tree.", "topics": ["segment-tree"]},
    ])
    mock_proc = _make_completed_process(stdout=success_stdout)
    _run_processor(monkeypatch, db_path, mock_proc)

    # Get quiz section_id
    quiz_rows = _db_rows(db_path, "SELECT quiz_id, section_id FROM quizzes WHERE status = 'ready'")
    assert quiz_rows, "No ready Quiz found."
    quiz_section_id = quiz_rows[0]["section_id"]
    quiz_id = quiz_rows[0]["quiz_id"]

    # Get all linked questions' section_ids
    linked = _db_rows(
        db_path,
        """SELECT q.section_id FROM questions q
           JOIN quiz_questions qq ON q.question_id = qq.question_id
           WHERE qq.quiz_id = ?""",
        (quiz_id,),
    )
    assert len(linked) >= 1, "No questions linked to the ready Quiz."
    cross_section = [r for r in linked if r["section_id"] != quiz_section_id]
    assert cross_section == [], (
        f"Questions from a DIFFERENT section are linked to quiz_id={quiz_id}: "
        f"{cross_section!r}. Quiz's section_id={quiz_section_id!r}. "
        "AC-6/MC-2/Manifest §6/§7: no cross-Section composition; every Question in "
        "a Quiz must reference exactly the same Section as the Quiz."
    )


# ===========================================================================
# AC-7 — First-Quiz-only guard (MC-8): POST returns 409 if a non-failed Quiz exists
# Trace: TASK-014 AC-7; ADR-037 §The first-Quiz-only guard; MC-8; Manifest §7
# ===========================================================================


def test_first_quiz_guard_boundary_ready_blocks_second(tmp_path, monkeypatch) -> None:
    """
    AC-7 (TASK-014) / MC-8: when a Section already has a 'ready' Quiz, a second
    POST .../quiz must return HTTP 409 and must NOT create a new Quiz row.

    ADR-037 §The first-Quiz-only guard: 'the route gains a guard: before inserting
    a new requested row, check whether the Section already has a non-failed Quiz
    (status ∈ {requested, generating, ready}). If it does, return HTTP 409.'

    Boundary: 'ready' is the exact boundary value that triggers the guard.

    Trace: AC-7; ADR-037 §The first-Quiz-only guard; MC-8; Manifest §7 'Every post-
    first Quiz … must not be fresh-only.'
    """
    db_path = str(tmp_path / "guard_ready.db")
    client = _bootstrap_and_make_client(monkeypatch, db_path)

    # Create a Quiz and walk it to 'ready'
    client.post(
        f"/lecture/{MANDATORY_CHAPTER_ID}/sections/{MANDATORY_FIRST_SECTION}/quiz",
        follow_redirects=False,
    )
    success_stdout = _make_success_stdout([
        {"prompt": "Implement a red-black tree rotation.", "topics": ["red-black-tree"]},
    ])
    mock_proc = _make_completed_process(stdout=success_stdout)
    _run_processor(monkeypatch, db_path, mock_proc)

    # Verify the Quiz is 'ready'
    rows = _db_rows(db_path, "SELECT status FROM quizzes WHERE section_id = ?", (SECTION_ID_CH01_S1,))
    assert rows and rows[0]["status"] == "ready", "Prerequisite: Quiz must be 'ready'."

    # Second POST: must return 409
    second_response = client.post(
        f"/lecture/{MANDATORY_CHAPTER_ID}/sections/{MANDATORY_FIRST_SECTION}/quiz",
        follow_redirects=False,
    )
    assert second_response.status_code == 409, (
        f"Second POST for a Section with a 'ready' Quiz returned "
        f"{second_response.status_code}; expected 409 Conflict. "
        "AC-7/ADR-037/MC-8: the first-Quiz-only guard must reject a second request "
        "when the Section already has a non-failed Quiz."
    )

    # No new Quiz row must have been created
    all_rows = _db_rows(db_path, "SELECT quiz_id FROM quizzes WHERE section_id = ?", (SECTION_ID_CH01_S1,))
    assert len(all_rows) == 1, (
        f"After the 409 rejection, there are {len(all_rows)} Quiz rows for the Section; "
        "expected exactly 1 (the original 'ready' Quiz). "
        "AC-7/ADR-037: HTTP 409 must not create any new Quiz row."
    )


def test_first_quiz_guard_boundary_generating_blocks_second(tmp_path, monkeypatch) -> None:
    """
    AC-7 (TASK-014) / MC-8: when a Section already has a 'generating' Quiz, a
    second POST must return HTTP 409.

    Boundary: 'generating' is one of the three non-failed statuses that trigger the
    guard (ADR-037: status ∈ {requested, generating, ready}).

    Trace: AC-7; ADR-037 §The first-Quiz-only guard; MC-8.
    """
    db_path = str(tmp_path / "guard_generating.db")
    client = _bootstrap_and_make_client(monkeypatch, db_path)

    # Insert a Quiz in 'generating' status directly (bypassing the route)
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO quizzes (section_id, status, created_at) "
        "VALUES (?, 'generating', '2026-05-12T00:00:00Z')",
        (SECTION_ID_CH01_S1,),
    )
    conn.commit()
    conn.close()

    # Second POST (which would be the first via the route, but the guard must see
    # the 'generating' row and reject)
    response = client.post(
        f"/lecture/{MANDATORY_CHAPTER_ID}/sections/{MANDATORY_FIRST_SECTION}/quiz",
        follow_redirects=False,
    )
    assert response.status_code == 409, (
        f"POST for a Section with a 'generating' Quiz returned {response.status_code}; "
        "expected 409. "
        "AC-7/ADR-037/MC-8: the guard triggers on status ∈ {requested, generating, ready}."
    )

    rows = _db_rows(db_path, "SELECT quiz_id FROM quizzes WHERE section_id = ?", (SECTION_ID_CH01_S1,))
    assert len(rows) == 1, (
        f"After the 409, there are {len(rows)} rows; expected 1. No new row must be created."
    )


def test_first_quiz_guard_requested_blocks_second(tmp_path, monkeypatch) -> None:
    """
    AC-7 (TASK-014) / MC-8: when a Section already has a 'requested' Quiz, a
    second POST must return HTTP 409.

    Boundary: 'requested' is the third non-failed status that triggers the guard.
    This is the same-status boundary (two clicks without running the processor).

    Trace: AC-7; ADR-037 §The first-Quiz-only guard; MC-8.
    """
    db_path = str(tmp_path / "guard_requested.db")
    client = _bootstrap_and_make_client(monkeypatch, db_path)

    # First POST: succeeds (creates 'requested' row)
    first_response = client.post(
        f"/lecture/{MANDATORY_CHAPTER_ID}/sections/{MANDATORY_FIRST_SECTION}/quiz",
        follow_redirects=False,
    )
    assert first_response.status_code == 303, "Prerequisite: first POST must return 303."

    # Second POST: must return 409
    second_response = client.post(
        f"/lecture/{MANDATORY_CHAPTER_ID}/sections/{MANDATORY_FIRST_SECTION}/quiz",
        follow_redirects=False,
    )
    assert second_response.status_code == 409, (
        f"Second POST (Section already has 'requested' Quiz) returned "
        f"{second_response.status_code}; expected 409. "
        "AC-7/ADR-037/MC-8: a 'requested' Quiz is a non-failed Quiz — the guard "
        "must reject a second request to prevent a fresh-only post-first Quiz."
    )

    all_rows = _db_rows(db_path, "SELECT quiz_id FROM quizzes WHERE section_id = ?", (SECTION_ID_CH01_S1,))
    assert len(all_rows) == 1, (
        f"After the 409, there are {len(all_rows)} rows; expected 1."
    )


def test_first_quiz_guard_boundary_generation_failed_allows_retry(tmp_path, monkeypatch) -> None:
    """
    AC-7 (TASK-014) / MC-8: a Section whose ONLY Quiz is 'generation_failed' must
    ALLOW a new POST (HTTP 303 + a new 'requested' row is created).

    ADR-037: 'A generation_failed Quiz does NOT count against the guard — the author
    can re-click "Generate a Quiz for this Section" after a failure.'

    Boundary: this is the boundary flip — 'generation_failed' is the one status that
    does NOT trigger the guard (generation_failed ∉ {requested, generating, ready}).

    Trace: AC-7; ADR-037 §The first-Quiz-only guard ('a generation_failed Quiz does
    not count'); MC-8.
    """
    db_path = str(tmp_path / "guard_failed_allows.db")
    client = _bootstrap_and_make_client(monkeypatch, db_path)

    # Create a Quiz and walk it to 'generation_failed'
    client.post(
        f"/lecture/{MANDATORY_CHAPTER_ID}/sections/{MANDATORY_FIRST_SECTION}/quiz",
        follow_redirects=False,
    )
    failure_proc = _make_completed_process(
        stdout="", stderr="error: timeout", returncode=1
    )
    _run_processor(monkeypatch, db_path, failure_proc)

    rows = _db_rows(db_path, "SELECT status FROM quizzes WHERE section_id = ?", (SECTION_ID_CH01_S1,))
    assert rows and rows[0]["status"] == "generation_failed", (
        "Prerequisite: Quiz must be 'generation_failed' before retry."
    )

    # Retry POST: must succeed with 303 (the guard must NOT block)
    retry_response = client.post(
        f"/lecture/{MANDATORY_CHAPTER_ID}/sections/{MANDATORY_FIRST_SECTION}/quiz",
        follow_redirects=False,
    )
    assert retry_response.status_code == 303, (
        f"Retry POST for a Section with a 'generation_failed' Quiz returned "
        f"{retry_response.status_code}; expected 303. "
        "AC-7/ADR-037: a 'generation_failed' Quiz does NOT count against the first-Quiz-"
        "only guard — the author must be able to retry after a failure."
    )

    # A new 'requested' row must have been created
    all_rows = _db_rows(db_path, "SELECT status FROM quizzes WHERE section_id = ?", (SECTION_ID_CH01_S1,))
    statuses = [r["status"] for r in all_rows]
    assert "requested" in statuses, (
        f"After the retry POST, no 'requested' row exists for the Section. "
        f"Statuses found: {statuses!r}. "
        "ADR-037: the retry must create a new 'requested' row alongside the historical "
        "'generation_failed' row (the failed row is never deleted — ADR-033 posture)."
    )


# ===========================================================================
# AC-8 — MC-9: processor processes existing rows; never creates one
# Trace: TASK-014 AC-8; ADR-037 §The trigger handoff; MC-9; Manifest §7
# ===========================================================================


def test_processor_module_exists_as_main_module() -> None:
    """
    AC-8 (TASK-014) / MC-9: the out-of-band processor must exist as a module
    under `app/workflows/process_quiz_requests.py` (ADR-037 §Decision).

    This is the structural contract: `python -m app.workflows.process_quiz_requests`
    must be a valid command (i.e., the module must be importable as a package module).

    Trace: AC-8; ADR-037 §Decision ('a manual command: python -m
    app.workflows.process_quiz_requests'); MC-9.
    """
    processor_module_path = REPO_ROOT / "app" / "workflows" / "process_quiz_requests.py"
    assert processor_module_path.exists(), (
        f"The processor module does not exist at {processor_module_path}. "
        "AC-8/ADR-037: the out-of-band processor must be `python -m "
        "app.workflows.process_quiz_requests` — a __main__ module under app/workflows/."
    )

    # The __init__.py for app/workflows/ must also exist
    init_path = REPO_ROOT / "app" / "workflows" / "__init__.py"
    assert init_path.exists(), (
        f"The app/workflows/__init__.py does not exist at {init_path}. "
        "ADR-036/ADR-037: app/workflows/ must be a proper Python package."
    )


# ===========================================================================
# AC-9 — MC-7: no user_id on new tables/columns; additive DDL (ADR-022)
# Trace: TASK-014 AC-9; ADR-037 §Failure-handling; MC-7; ADR-022
# ===========================================================================


def test_schema_generation_error_column_exists(tmp_path, monkeypatch) -> None:
    """
    AC-9 (TASK-014) / ADR-037: the new nullable `quizzes.generation_error TEXT`
    column must exist after schema bootstrap.

    ADR-037 §Failure-handling: 'ALTER TABLE quizzes ADD COLUMN generation_error TEXT'
    — additive, nullable, created via ADR-022's migration story.

    Trace: AC-9; ADR-037 §Failure-handling discipline; ADR-022 §Migration story.
    """
    db_path = str(tmp_path / "gen_error_col.db")
    _bootstrap_and_make_client(monkeypatch, db_path)

    cols = _get_table_columns(db_path, "quizzes")
    assert "generation_error" in cols, (
        f"The `quizzes` table has no `generation_error` column. Columns: {cols!r}. "
        "AC-9/ADR-037: a nullable `generation_error TEXT` column must be added to "
        "`quizzes` via additive `ALTER TABLE ADD COLUMN` per ADR-022."
    )


def test_no_user_id_on_generation_error_column(tmp_path, monkeypatch) -> None:
    """
    AC-9 (TASK-014) / MC-7: the `quizzes` table must have no `user_id` column
    (including after the new `generation_error` column is added).

    MC-7: 'No code path assumes multi-tenant capability: no user_id columns.'

    Trace: AC-9; MC-7; ADR-033 §No user_id; Manifest §5 'No multi-user features'.
    """
    db_path = str(tmp_path / "no_user_id.db")
    _bootstrap_and_make_client(monkeypatch, db_path)

    cols = _get_table_columns(db_path, "quizzes")
    assert "user_id" not in cols, (
        f"The `quizzes` table has a `user_id` column after TASK-014 schema additions. "
        f"Columns: {cols!r}. "
        "AC-9/MC-7: no user_id column must appear on any Quiz-domain table — "
        "single-user posture (Manifest §5 / ADR-033 / MC-7)."
    )


def test_generation_error_column_is_nullable_for_nonfailed_quizzes(tmp_path, monkeypatch) -> None:
    """
    AC-9 (TASK-014) / ADR-037: `quizzes.generation_error` must be NULL for a
    non-failed Quiz (nullable — not a NOT NULL column).

    ADR-037: 'nullable column … NULL for every non-failed Quiz.'

    Trace: AC-9; ADR-037 §Failure-handling; ADR-022 §Migration story (additive /
    nullable ALTER TABLE ADD COLUMN).
    """
    db_path = str(tmp_path / "nullable_gen_error.db")
    client = _bootstrap_and_make_client(monkeypatch, db_path)

    client.post(
        f"/lecture/{MANDATORY_CHAPTER_ID}/sections/{MANDATORY_FIRST_SECTION}/quiz",
        follow_redirects=False,
    )

    success_stdout = _make_success_stdout([
        {"prompt": "Implement DFS on an adjacency list graph.", "topics": ["graphs", "DFS"]},
    ])
    mock_proc = _make_completed_process(stdout=success_stdout)
    _run_processor(monkeypatch, db_path, mock_proc)

    quiz_rows = _db_rows(db_path, "SELECT status, generation_error FROM quizzes")
    assert quiz_rows and quiz_rows[0]["status"] == "ready", (
        "Prerequisite: expected a 'ready' Quiz."
    )
    assert quiz_rows[0]["generation_error"] is None, (
        f"A 'ready' Quiz has generation_error={quiz_rows[0]['generation_error']!r}; "
        "expected NULL. "
        "AC-9/ADR-037: generation_error must be NULL for non-failed Quizzes — it is "
        "only populated on the failure path."
    )


# ===========================================================================
# AC-10 — MC-10: import sqlite3 and SQL literals only under app/persistence/
#          (extended to app/workflows/)
# Trace: TASK-014 AC-10; MC-10; ADR-022; ADR-036
# ===========================================================================


def test_mc10_no_sqlite3_import_in_workflows() -> None:
    """
    AC-10 (TASK-014) / MC-10: `import sqlite3` must NOT appear in any file under
    `app/workflows/` (or anywhere under `app/` outside `app/persistence/`).

    ADR-036 §The orchestration boundary: 'the workflow module does not touch CS-300's
    database (MC-10 — the workflow module imports no sqlite3, opens no connection).'
    ADR-022 §Package boundary: `import sqlite3` confined to `app/persistence/`.

    Trace: AC-10; ADR-036 §The orchestration boundary; ADR-022 §Package boundary;
    MC-10; Manifest (single-user posture, persistence boundary).
    """
    app_dir = REPO_ROOT / "app"
    persistence_dir = app_dir / "persistence"
    violations = []
    for py_file in sorted(app_dir.rglob("*.py")):
        try:
            py_file.relative_to(persistence_dir)
            continue  # inside app/persistence/ — allowed
        except ValueError:
            pass
        text = py_file.read_text(encoding="utf-8")
        if "import sqlite3" in text:
            violations.append(str(py_file))

    assert violations == [], (
        f"MC-10 BLOCKER: `import sqlite3` found outside `app/persistence/` in: "
        f"{violations!r}. "
        "AC-10/ADR-022/ADR-036: DB driver imports must be confined to app/persistence/. "
        "The workflow module and processor must not import sqlite3 directly — they call "
        "only the typed public functions from app.persistence.*."
    )


def test_mc10_no_sql_literals_in_workflows() -> None:
    """
    AC-10 (TASK-014) / MC-10: SQL string literals (SELECT / INSERT / UPDATE / DELETE /
    CREATE TABLE / BEGIN / COMMIT / ROLLBACK) must NOT appear under `app/workflows/`
    (or anywhere outside `app/persistence/`).

    ADR-036 §The orchestration boundary (MC-10). ADR-022 §Package boundary.

    Trace: AC-10; ADR-022 §Package boundary; ADR-036; MC-10.
    """
    app_dir = REPO_ROOT / "app"
    persistence_dir = app_dir / "persistence"

    sql_keywords_pattern = re.compile(
        r"""(?x)
        (?:"|')               # opening quote
        [^"']*                # any content
        (?:
            \bSELECT\b  |
            \bINSERT\b  |
            \bUPDATE\b  |
            \bDELETE\b  |
            \bCREATE\s+TABLE\b |
            \bBEGIN\b   |
            \bCOMMIT\b  |
            \bROLLBACK\b
        )
        [^"']*
        (?:"|')               # closing quote
        """,
    )

    violations = []
    for py_file in sorted(app_dir.rglob("*.py")):
        try:
            py_file.relative_to(persistence_dir)
            continue  # inside app/persistence/ — allowed
        except ValueError:
            pass
        text = py_file.read_text(encoding="utf-8")
        if sql_keywords_pattern.search(text):
            violations.append(str(py_file))

    assert violations == [], (
        f"MC-10 BLOCKER: SQL string literals found outside `app/persistence/` in: "
        f"{violations!r}. "
        "AC-10/ADR-022/ADR-036: SQL literals must be confined to app/persistence/. "
        "The workflow module and processor must call only typed public functions "
        "(mark_quiz_generating, mark_quiz_ready, mark_quiz_generation_failed, "
        "add_questions_to_quiz, list_requested_quizzes, get_quiz) — no raw SQL."
    )


# ===========================================================================
# AC-11 — Per-Section surface: generating / ready / generation_failed states
#          are now actually exercised; no takeable affordance for 'ready'
# Trace: TASK-014 AC-11; ADR-034 §What the surface renders; MC-5; MC-3
# ===========================================================================


def test_surface_shows_generating_status(tmp_path, monkeypatch) -> None:
    """
    AC-11 (TASK-014): when a Section has a Quiz in 'generating' status, the
    per-Section surface must show "Generating…".

    ADR-034 §What the surface renders: `generating` → "Generating…".
    This test exercises the 'generating' state by directly inserting a row
    (bypassing the processor — just tests the render path).

    Trace: AC-11; ADR-034 §Populated case; MC-5 (never presents generating as ready).
    """
    db_path = str(tmp_path / "surface_generating.db")
    client = _bootstrap_and_make_client(monkeypatch, db_path)

    # Insert a 'generating' row directly
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO quizzes (section_id, status, created_at) "
        "VALUES (?, 'generating', '2026-05-12T00:00:00Z')",
        (SECTION_ID_CH01_S1,),
    )
    conn.commit()
    conn.close()

    response = client.get(f"/lecture/{MANDATORY_CHAPTER_ID}")
    assert response.status_code == 200
    html = response.text

    generating_signalled = (
        "section-quiz-item--generating" in html
        or "Generating" in html
    )
    assert generating_signalled, (
        f"A 'generating' Quiz does not show 'Generating…' on the surface. "
        "AC-11/ADR-034: `generating` status must render as 'Generating…'. "
        f"HTML snippet (first 5000 chars): {html[:5000]!r}"
    )


def test_surface_ready_has_no_takeable_affordance(tmp_path, monkeypatch) -> None:
    """
    AC-11 (TASK-014) / ADR-034: a 'ready' Quiz must show "Ready" but must NOT
    offer a takeable affordance (no take-button — the Quiz-taking surface is a
    later slice).

    ADR-034 §What the surface renders: 'ready → "Ready" (with no takeable affordance
    — the Quiz-taking surface is a later task)'; 'no takeable affordance ships …
    even for a ready Quiz'.

    Trace: AC-11; ADR-034 §Populated case; ADR-034 §What is NOT changed.
    """
    db_path = str(tmp_path / "no_take_button.db")
    client = _bootstrap_and_make_client(monkeypatch, db_path)

    # Insert a 'ready' row directly
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO quizzes (section_id, status, created_at) "
        "VALUES (?, 'ready', '2026-05-12T00:00:00Z')",
        (SECTION_ID_CH01_S1,),
    )
    conn.commit()
    conn.close()

    response = client.get(f"/lecture/{MANDATORY_CHAPTER_ID}")
    assert response.status_code == 200
    html = response.text

    # Must show "Ready"
    ready_signalled = (
        "section-quiz-item--ready" in html
        or "Ready" in html
    )
    assert ready_signalled, (
        "A 'ready' Quiz does not show 'Ready' on the surface. "
        "AC-11/ADR-034: `ready` status must render as 'Ready'."
    )

    # Must NOT show a take-button (ADR-034 commitment — later task).
    # Check for specific take-quiz affordance CSS class or URL patterns only.
    # A broad AND of individual words ("take", "quiz", "button") produces false
    # positives because those words appear individually in the lecture body text.
    take_quiz_patterns = [
        "take-quiz",
        "take quiz",
        'class="take-quiz',
        "/quiz/take",
    ]
    violations = [p for p in take_quiz_patterns if p in html.lower()]
    assert violations == [], (
        f"The rendered page shows a take-quiz affordance pattern {violations!r} "
        "for a 'ready' Quiz. "
        "AC-11/ADR-034: 'no takeable affordance ships even for a ready Quiz' — "
        "the Quiz-taking surface is a later slice (not TASK-014)."
    )


def test_surface_mandatory_and_optional_both_render_statuses(tmp_path, monkeypatch) -> None:
    """
    AC-11 (TASK-014) / MC-3: the per-Section Quiz surface (including the new
    'ready' / 'generation_failed' status labels) must render on BOTH Mandatory
    and Optional Chapters (M/O inheritance).

    ADR-034 / MC-3 / Manifest §6: 'Mandatory and Optional are honored everywhere.'
    The surface inherits the parent Chapter's designation; the status labels render
    regardless of designation.

    Trace: AC-11; MC-3; ADR-034 §What the surface renders; Manifest §6/§7.
    """
    db_path_m = str(tmp_path / "mandatory_ready.db")
    client_m = _bootstrap_and_make_client(monkeypatch, db_path_m)

    # Insert a 'ready' row for the Mandatory chapter
    conn = sqlite3.connect(db_path_m)
    conn.execute(
        "INSERT INTO quizzes (section_id, status, created_at) "
        "VALUES (?, 'ready', '2026-05-12T00:00:00Z')",
        (SECTION_ID_CH01_S1,),
    )
    conn.commit()
    conn.close()

    response_m = client_m.get(f"/lecture/{MANDATORY_CHAPTER_ID}")
    assert response_m.status_code == 200
    assert "section-quiz-item--ready" in response_m.text or "Ready" in response_m.text, (
        f"Mandatory Chapter /lecture/{MANDATORY_CHAPTER_ID} does not show 'Ready' "
        "for a 'ready' Quiz. AC-11/MC-3: status labels must render on Mandatory Chapters."
    )

    # Optional chapter
    db_path_o = str(tmp_path / "optional_ready.db")
    monkeypatch.setenv("NOTES_DB_PATH", db_path_o)
    from fastapi.testclient import TestClient  # noqa: PLC0415
    from app.main import app  # noqa: PLC0415
    client_o = TestClient(app)
    client_o.get(f"/lecture/{OPTIONAL_CHAPTER_ID}")

    optional_section_id = f"{OPTIONAL_CHAPTER_ID}#section-7-1"
    conn_o = sqlite3.connect(db_path_o)
    conn_o.execute(
        "INSERT INTO quizzes (section_id, status, created_at) "
        "VALUES (?, 'ready', '2026-05-12T00:00:00Z')",
        (optional_section_id,),
    )
    conn_o.commit()
    conn_o.close()

    response_o = client_o.get(f"/lecture/{OPTIONAL_CHAPTER_ID}")
    assert response_o.status_code == 200
    assert "section-quiz-item--ready" in response_o.text or "Ready" in response_o.text, (
        f"Optional Chapter /lecture/{OPTIONAL_CHAPTER_ID} does not show 'Ready' "
        "for a 'ready' Quiz. AC-11/MC-3: status labels must render on Optional Chapters too."
    )


# ===========================================================================
# AC-12 — No Notification entity ships this task; no stand-in fabricated
# Trace: TASK-014 AC-12; ADR-037 §How the learner is notified; MC-5
# ===========================================================================


def test_no_notifications_table_in_schema(tmp_path, monkeypatch) -> None:
    """
    AC-12 (TASK-014) / ADR-037: no Notification entity ships this task. The
    `notifications` table must NOT exist in the database after bootstrap.

    ADR-037 §How the learner is notified: 'no Notification entity ships this task.
    The active Notification entity … ships with the grading slice.'

    Trace: AC-12; ADR-037 §How the learner is notified; MC-5 (no stand-in
    Notification when generation has not actually succeeded).
    """
    db_path = str(tmp_path / "no_notifications.db")
    _bootstrap_and_make_client(monkeypatch, db_path)

    conn = sqlite3.connect(db_path)
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='notifications'"
    )
    table_exists = cur.fetchone() is not None
    conn.close()

    assert not table_exists, (
        "A 'notifications' table was found in the database after TASK-014 bootstrap. "
        "AC-12/ADR-037: the Notification entity (the 'notifications' table + learner-"
        "visible surface) does NOT ship this task — it ships with the grading slice "
        "(where there's a Grade to notify about too)."
    )


def test_no_fabricated_notification_on_non_ready_quiz(tmp_path, monkeypatch) -> None:
    """
    AC-12 (TASK-014) / MC-5: the surface must NOT present any 'notification' or
    'ready' signal for a Quiz that is still 'requested' (no AI processing done).

    ADR-037: 'In no case is a stand-in Notification fabricated.'
    MC-5: 'The system never substitutes a … stand-in Notification.'

    Trace: AC-12; ADR-037 §How the learner is notified; MC-5.
    """
    db_path = str(tmp_path / "no_fabricated_notif.db")
    client = _bootstrap_and_make_client(monkeypatch, db_path)

    client.post(
        f"/lecture/{MANDATORY_CHAPTER_ID}/sections/{MANDATORY_FIRST_SECTION}/quiz",
        follow_redirects=False,
    )

    response = client.get(f"/lecture/{MANDATORY_CHAPTER_ID}")
    assert response.status_code == 200
    html = response.text

    # Must NOT show "Ready" for a 'requested' Quiz
    assert "section-quiz-item--ready" not in html, (
        "The surface shows 'section-quiz-item--ready' for a Quiz that is still 'requested'. "
        "AC-12/MC-5: a stand-in 'Ready' Notification is fabrication — the Quiz has not "
        "been processed and is not ready."
    )


# ===========================================================================
# AC-14 — The ai-workflows integration ADR exists and is Accepted
# Trace: TASK-014 AC-14; ADR-036; ADR-037
# ===========================================================================


def test_adr036_exists_and_is_accepted() -> None:
    """
    AC-14 (TASK-014): ADR-036 (the `ai-workflows` integration ADR) must exist in
    `design_docs/decisions/` and have `Status: Accepted`.

    AC-14: 'when /design completes, then the ai-workflows integration is a new ADR.'

    Trace: AC-14; ADR-036.
    """
    adr_path = REPO_ROOT / "design_docs" / "decisions" / "ADR-036-ai-workflows-integration.md"
    assert adr_path.exists(), (
        f"ADR-036 does not exist at {adr_path}. "
        "AC-14: the ai-workflows integration must be backed by an Accepted ADR."
    )
    text = adr_path.read_text(encoding="utf-8")
    assert "Status:** `Accepted`" in text or "**Status:** `Accepted`" in text, (
        f"ADR-036 at {adr_path} does not have Status: Accepted. "
        "AC-14: ADR-036 must be Accepted before implementation proceeds."
    )


def test_adr037_exists_and_is_accepted() -> None:
    """
    AC-14 (TASK-014): ADR-037 (the async Quiz-generation processing ADR) must exist
    in `design_docs/decisions/` and have `Status: Accepted`.

    AC-14: 'the async-delivery / out-of-band-processing mechanism is a new ADR.'

    Trace: AC-14; ADR-037.
    """
    adr_path = REPO_ROOT / "design_docs" / "decisions" / "ADR-037-async-quiz-generation-processing.md"
    assert adr_path.exists(), (
        f"ADR-037 does not exist at {adr_path}. "
        "AC-14: the async processing mechanism must be backed by an Accepted ADR."
    )
    text = adr_path.read_text(encoding="utf-8")
    assert "Status:** `Accepted`" in text or "**Status:** `Accepted`" in text, (
        f"ADR-037 at {adr_path} does not have Status: Accepted. "
        "AC-14: ADR-037 must be Accepted before implementation proceeds."
    )


# ===========================================================================
# Edge — empty artefact treated as failure
# Trace: ADR-036 §The orchestration boundary ('an empty questions list … treated as a failure')
# ===========================================================================


def test_processor_failure_empty_artefact_treated_as_failure(tmp_path, monkeypatch) -> None:
    """
    Edge: an artefact with an empty questions list (stdout parses correctly but
    `{"questions": []}` has zero items) must be treated as a failure — the Quiz
    transitions to 'generation_failed', no questions persisted.

    ADR-036 §The orchestration boundary: 'on success and the artefact non-empty
    (≥1 item with a non-empty prompt)'; 'on a non-zero aiw run exit / an error: on
    stderr — OR an empty/invalid artefact / a questions list that fails CS-300's own
    sanity check that ≥1 coding-task Question came back: mark_quiz_generation_failed.'

    Trace: ADR-036 §The orchestration boundary; ADR-037 §Failure; MC-5.
    """
    db_path = str(tmp_path / "empty_artefact.db")
    client = _bootstrap_and_make_client(monkeypatch, db_path)

    client.post(
        f"/lecture/{MANDATORY_CHAPTER_ID}/sections/{MANDATORY_FIRST_SECTION}/quiz",
        follow_redirects=False,
    )
    quiz_id = _db_rows(db_path, "SELECT quiz_id FROM quizzes")[0]["quiz_id"]

    # Empty artefact — exit 0 but no questions
    empty_stdout = _make_success_stdout([])  # {"questions": []}
    empty_proc = _make_completed_process(stdout=empty_stdout, returncode=0)
    _run_processor(monkeypatch, db_path, empty_proc)

    quiz_rows = _db_rows(db_path, "SELECT status FROM quizzes WHERE quiz_id = ?", (quiz_id,))
    # The processor must treat an empty questions list as a failure
    status = quiz_rows[0]["status"] if quiz_rows else "NOT FOUND"
    assert status == "generation_failed", (
        f"After an empty-artefact artefact (zero questions), Quiz status={status!r}; "
        "expected 'generation_failed'. "
        "ADR-036/ADR-037: an empty questions list is a sanity-check failure — the "
        "Quiz must not become 'ready' with no Questions."
    )

    question_rows = _db_rows(db_path, "SELECT question_id FROM questions")
    assert question_rows == [], (
        f"After an empty artefact, {len(question_rows)} question rows found; expected 0."
    )


# ===========================================================================
# Performance — processor with multiple questions within budget
# Trace: AC-1; ADR-036 §The orchestration boundary
# ===========================================================================


def test_processor_happy_path_with_multiple_questions_within_budget(tmp_path, monkeypatch) -> None:
    """
    Performance (AC-1): processing a Quiz with 5 generated questions must complete
    within 5 seconds.

    Scale surface: `add_questions_to_quiz` iterates the questions list and performs
    one INSERT INTO questions + one INSERT INTO quiz_questions per question. A naive
    implementation that opens/closes a connection per question would be O(n) — still
    fine. An implementation that runs an extra SELECT per question would be O(n)
    with a larger constant — also fine. An O(n²) retry loop per question would show
    up here.

    The 5-second budget is generous (the real operation should be <100ms for 5 rows).

    Trace: AC-1 performance; ADR-036 §The orchestration boundary.
    """
    db_path = str(tmp_path / "perf.db")
    client = _bootstrap_and_make_client(monkeypatch, db_path)

    client.post(
        f"/lecture/{MANDATORY_CHAPTER_ID}/sections/{MANDATORY_FIRST_SECTION}/quiz",
        follow_redirects=False,
    )

    questions = [
        {"prompt": f"Implement data structure #{i}: a self-balancing BST.", "topics": [f"ds-{i}", "BST"]}
        for i in range(5)
    ]
    success_stdout = _make_success_stdout(questions)
    mock_proc = _make_completed_process(stdout=success_stdout)

    t0 = time.monotonic()
    _run_processor(monkeypatch, db_path, mock_proc)
    elapsed = time.monotonic() - t0

    # Verify questions were persisted
    question_rows = _db_rows(db_path, "SELECT question_id FROM questions")
    assert len(question_rows) >= 5, (
        f"Expected ≥5 questions rows after processing 5-question artefact; "
        f"got {len(question_rows)}."
    )

    assert elapsed < 5.0, (
        f"Processing a 5-question artefact took {elapsed:.2f}s (limit: 5s). "
        "AC-1/ADR-036: question persistence should be fast — catching O(n²) patterns "
        "(e.g. one DB connection per question, or a SELECT-then-INSERT per question "
        "with an N×M retry loop)."
    )


# ===========================================================================
# Delta (Run 010) — subprocess invocation shape:
# `aiw run question_gen` receives the correct --input values
# (the Section's actual body_html / heading_text, not empty strings or the
# composite section_id).
#
# Trace: ADR-036 §How application code invokes the workflow; ADR-036 §The test seam;
# reviewer Run 009 blocking finding #1.
# ===========================================================================


def test_subprocess_invocation_shape_section_content_and_title(tmp_path, monkeypatch) -> None:
    """
    Delta (Run 010): the processor must invoke `aiw run question_gen` with
    `--input section_content=<actual Section body_html>` (non-empty, matching
    what `app.parser.extract_sections` returns under the `body_html` key) and
    `--input section_title=<heading_text>` (the Section's plain-text heading,
    NOT the composite section_id).

    This test fails against the current `app/workflows/process_quiz_requests.py`
    because `_get_section_content` reads `section.get("html", "")` /
    `section.get("content", "")` / `section.get("title", section_id)` — none of
    which are keys that `extract_sections` returns (`body_html` / `heading_text`).
    The result is `section_content=""` and `section_title=<composite section_id>`,
    so the LLM never receives the Section's text.

    Contracts asserted (ADR-036 §How application code invokes the workflow):
      1. The subprocess command starts with ["aiw", "run", "question_gen"].
      2. The --input section_content=VALUE pair is present and VALUE is non-empty
         AND matches the body_html that `extract_sections` produces for the Section.
      3. The --input section_title=VALUE pair is present and VALUE is the Section's
         heading_text (NOT the composite section_id).
      4. A --run-id VALUE is present and VALUE contains the quiz_id (the format
         "quiz-{quiz_id}" per the implementer; the test asserts containment, not
         an exact format).
      5. The env kwarg has AIW_EXTRA_WORKFLOW_MODULES=app.workflows.question_gen.

    Trace: ADR-036 §How application code invokes the workflow; ADR-036 §The test seam
    (the CS-300 processor boundary is the test seam — mock subprocess.run and inspect
    call_args); reviewer Run 009 blocking finding #1.
    """
    import pathlib as _pathlib  # noqa: PLC0415 — deferred to avoid collection-time ImportError

    db_path = str(tmp_path / "invocation_shape.db")
    monkeypatch.setenv("NOTES_DB_PATH", db_path)

    # --- Step 1: Bootstrap the DB and create a 'requested' Quiz ---
    from fastapi.testclient import TestClient  # noqa: PLC0415
    from app.main import app as _app  # noqa: PLC0415
    client = TestClient(_app)
    # Bootstrap the DB by hitting the lecture page (creates all tables)
    client.get(f"/lecture/{MANDATORY_CHAPTER_ID}")
    # Submit the Quiz request — creates a 'requested' row
    client.post(
        f"/lecture/{MANDATORY_CHAPTER_ID}/sections/{MANDATORY_FIRST_SECTION}/quiz",
        follow_redirects=False,
    )

    # Verify the Quiz row and capture quiz_id
    quiz_rows = _db_rows(db_path, "SELECT quiz_id, section_id, status FROM quizzes")
    assert len(quiz_rows) == 1 and quiz_rows[0]["status"] == "requested", (
        "Prerequisite: expected exactly one 'requested' Quiz before running the processor."
    )
    quiz_id = quiz_rows[0]["quiz_id"]
    assert quiz_rows[0]["section_id"] == SECTION_ID_CH01_S1, (
        f"Prerequisite: section_id mismatch: expected {SECTION_ID_CH01_S1!r}, "
        f"got {quiz_rows[0]['section_id']!r}."
    )

    # --- Step 2: Compute the expected section content from extract_sections ---
    # This is the ground truth the processor must pass to `aiw run question_gen`.
    import app.config as _app_config  # noqa: PLC0415
    from app.parser import extract_sections as _extract_sections  # noqa: PLC0415

    chapter_id = MANDATORY_CHAPTER_ID
    tex_path = _pathlib.Path(_app_config.CONTENT_ROOT) / f"{chapter_id}.tex"
    assert tex_path.exists(), (
        f"Prerequisite: .tex file not found at {tex_path}. "
        "The test needs the real corpus to derive the expected section_content."
    )
    latex_text = tex_path.read_text(encoding="utf-8")
    sections = _extract_sections(chapter_id, latex_text)

    target_section = next(
        (s for s in sections if s["id"] == SECTION_ID_CH01_S1),
        None,
    )
    assert target_section is not None, (
        f"Prerequisite: section {SECTION_ID_CH01_S1!r} not found in extract_sections output. "
        f"IDs found: {[s['id'] for s in sections]!r}"
    )

    expected_body_html: str = target_section.get("body_html", "")
    expected_heading_text: str = target_section.get("heading_text", "")

    assert expected_body_html.strip(), (
        f"Prerequisite: extract_sections returned an empty body_html for {SECTION_ID_CH01_S1!r}. "
        "The test is designed for a Section with non-empty content."
    )
    assert expected_heading_text.strip(), (
        f"Prerequisite: extract_sections returned an empty heading_text for {SECTION_ID_CH01_S1!r}."
    )

    # --- Step 3: Run the processor with subprocess.run mocked ---
    # The mock must return a valid CompletedProcess so the processor's artefact-
    # parsing path is exercised (though the assertions below are on call_args, not
    # the lifecycle outcome).
    success_stdout = _make_success_stdout([
        {"prompt": "Implement a vector class.", "topics": ["vectors"]},
    ])
    mock_completed = _make_completed_process(stdout=success_stdout, returncode=0)

    captured_mock = MagicMock(return_value=mock_completed)

    with patch("subprocess.run", captured_mock):
        import app.workflows.process_quiz_requests as _proc  # noqa: PLC0415
        if hasattr(_proc, "process_pending"):
            _proc.process_pending()
        elif hasattr(_proc, "main"):
            _proc.main()
        else:
            pytest.fail(
                "app.workflows.process_quiz_requests has no callable entry point. "
                "ADR-037: the processor must expose process_pending() or main()."
            )

    # --- Step 4: Assert subprocess.run was called (at all) ---
    assert captured_mock.called, (
        "subprocess.run was never called during the processor run. "
        "ADR-036: the processor must invoke `aiw run question_gen` via subprocess.run."
    )

    # Extract the call arguments from the first (and only) subprocess.run call.
    call = captured_mock.call_args
    # call.args[0] is the command list; call.kwargs may hold env=, capture_output=, etc.
    # Support both positional and keyword first arg.
    if call.args:
        cmd = call.args[0]
    else:
        cmd = call.kwargs.get("args") or call.kwargs.get("cmd", [])

    # --- Step 5: Assert the command prefix is ["aiw", "run", "question_gen", ...] ---
    assert isinstance(cmd, list) and len(cmd) >= 3, (
        f"subprocess.run was called with a non-list or too-short command: {cmd!r}. "
        "ADR-036: the command must be a list starting with ['aiw', 'run', 'question_gen', ...]."
    )
    assert cmd[0] == "aiw" and cmd[1] == "run" and cmd[2] == "question_gen", (
        f"subprocess.run command does not start with ['aiw', 'run', 'question_gen']. "
        f"Got: {cmd[:4]!r}. "
        "ADR-036 §How application code invokes the workflow: the command must be "
        "['aiw', 'run', 'question_gen', ...]."
    )

    # --- Step 6: Extract --input KEY=VALUE pairs from the command list ---
    # The command has pairs: --input KEY=VALUE, --input KEY=VALUE, --run-id RUN_ID.
    input_values: dict[str, str] = {}
    run_id_value: str | None = None
    i = 3  # skip ["aiw", "run", "question_gen"]
    while i < len(cmd):
        token = cmd[i]
        if token == "--input" and i + 1 < len(cmd):
            kv = cmd[i + 1]
            # kv is "KEY=VALUE"; split on the first "="
            if "=" in kv:
                k, _, v = kv.partition("=")
                input_values[k] = v
            i += 2
        elif token == "--run-id" and i + 1 < len(cmd):
            run_id_value = cmd[i + 1]
            i += 2
        else:
            i += 1

    # --- Step 7: Assert section_content is present, non-empty, and matches body_html ---
    assert "section_content" in input_values, (
        f"The processor did not pass --input section_content=... to `aiw run question_gen`. "
        f"Input pairs found: {list(input_values.keys())!r}. "
        "ADR-036: the command must include --input section_content=<Section body_html>. "
        "This likely means _get_section_content reads the wrong dict key "
        "(uses 'html'/'content' instead of 'body_html')."
    )

    actual_section_content = input_values["section_content"]

    assert actual_section_content.strip(), (
        f"The processor passed --input section_content= with an EMPTY value to `aiw run question_gen`. "
        f"Expected the Section's body_html (first 80 chars): {expected_body_html[:80]!r}. "
        "ADR-036 §How application code invokes the workflow: section_content must be the "
        "Section's rendered body (body_html key from extract_sections). "
        "Current bug: _get_section_content reads section.get('html', '') / "
        "section.get('content', '') — both keys are absent from extract_sections output; "
        "the correct key is 'body_html'."
    )

    assert actual_section_content == expected_body_html, (
        f"The processor passed a section_content value that does not match the Section's "
        f"body_html from extract_sections.\n"
        f"  Passed (first 120 chars): {actual_section_content[:120]!r}\n"
        f"  Expected (first 120 chars): {expected_body_html[:120]!r}\n"
        "ADR-036: section_content must be the value of the 'body_html' key returned by "
        "extract_sections for the matched Section."
    )

    # --- Step 8: Assert section_title is present and is heading_text, not section_id ---
    assert "section_title" in input_values, (
        f"The processor did not pass --input section_title=... to `aiw run question_gen`. "
        f"Input pairs found: {list(input_values.keys())!r}. "
        "ADR-036: the command must include --input section_title=<heading_text>."
    )

    actual_section_title = input_values["section_title"]

    # The title must NOT be the raw composite section_id (the current bug's fallback).
    assert actual_section_title != SECTION_ID_CH01_S1, (
        f"The processor passed the composite section_id {SECTION_ID_CH01_S1!r} as the "
        f"section_title, instead of the Section's heading_text {expected_heading_text!r}. "
        "ADR-036: section_title must be the Section's plain-text heading (heading_text key "
        "from extract_sections). "
        "Current bug: _get_section_content reads section.get('title', section_id) — "
        "the 'title' key is absent; the fallback is the composite section_id; "
        "the correct key is 'heading_text'."
    )

    assert actual_section_title == expected_heading_text, (
        f"The processor passed section_title={actual_section_title!r} but the Section's "
        f"heading_text is {expected_heading_text!r}.\n"
        "ADR-036: section_title must match the 'heading_text' key from extract_sections."
    )

    # --- Step 9: Assert --run-id is present and contains the quiz_id ---
    assert run_id_value is not None, (
        f"The processor did not pass --run-id to `aiw run question_gen`. "
        f"Full command: {cmd!r}. "
        "ADR-036: --run-id must be passed to identify the run (e.g. 'quiz-{quiz_id}')."
    )

    assert str(quiz_id) in run_id_value, (
        f"The --run-id value {run_id_value!r} does not contain the quiz_id {quiz_id!r}. "
        "ADR-036: the run-id must identify the Quiz (the implementer uses 'quiz-{quiz_id}')."
    )

    # --- Step 10: Assert AIW_EXTRA_WORKFLOW_MODULES is set in the subprocess env ---
    env_kwarg = call.kwargs.get("env")
    assert env_kwarg is not None, (
        "subprocess.run was called without an `env=` kwarg. "
        "ADR-036: the subprocess env must include "
        "AIW_EXTRA_WORKFLOW_MODULES=app.workflows.question_gen so the `aiw` CLI can "
        "discover the CS-300 workflow module."
    )
    assert env_kwarg.get("AIW_EXTRA_WORKFLOW_MODULES") == "app.workflows.question_gen", (
        f"AIW_EXTRA_WORKFLOW_MODULES in the subprocess env is "
        f"{env_kwarg.get('AIW_EXTRA_WORKFLOW_MODULES')!r}; "
        "expected 'app.workflows.question_gen'. "
        "ADR-036: AIW_EXTRA_WORKFLOW_MODULES must be set so `aiw run` imports the "
        "CS-300-owned question_gen WorkflowSpec before dispatching."
    )
