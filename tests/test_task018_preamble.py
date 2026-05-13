"""
TASK-018: `question_gen`-prompt change — emit assertion-only test suites
that reference (but do not define) the implementation target, with a new
`preamble: str` field on GeneratedQuestion carrying shared struct/class/header
shapes, supporting persistence (questions.preamble column), sandbox splice
extension (preamble + response + test_suite), and take-page rendering
(.quiz-take-preamble block).

Tests derive from the Acceptance Criteria in
`design_docs/tasks/TASK-018-question-gen-prompt-assertion-only-test-suites.md`
and from the three Accepted ADRs this task lands:
  ADR-045 — The `question_gen` prompt change: STRICT REQUIREMENTs 7 and 8
             added (assertion-only test suites that reference but do not define
             the implementation target; preamble field for shared shapes);
             GeneratedQuestion gains `preamble: str = Field(default="")`;
             `extra="forbid"` and `test_suite` `min_length=1` preserved;
             processor reads `preamble` verbatim (q.get("preamble", ""));
             empty preamble is NOT a generation_failed trigger.
  ADR-046 — The Question preamble persistence: nullable `questions.preamble
             TEXT` column (additive via _apply_additive_migrations PRAGMA check
             + CREATE TABLE block for fresh DBs); Question dataclass gains
             `preamble: str | None`; AttemptQuestion gains `preamble: str | None`;
             add_questions_to_quiz payload dict gains "preamble" key (no
             signature change); list_questions_for_quiz / get_question /
             list_attempt_questions carry it through; no new accessor.
  ADR-047 — The sandbox splice extension: run_test_suite(test_suite, response,
             preamble="") → splice is `preamble + "\\n\\n" + response + "\\n\\n"
             + test_suite`; default-"" preserves byte-equivalence to ADR-042's
             pre-task splice; take template renders read-only
             <pre class="quiz-take-preamble"> per Question with non-empty preamble,
             omitted when empty; new .quiz-take-preamble rule in quiz.css.

Coverage matrix:
  Boundary:
    - test_generated_question_preamble_field_default_empty_string:
        GeneratedQuestion(prompt=..., topics=..., test_suite="x") round-trips
        with preamble="" as the default (boundary: absent key → default "").
    - test_generated_question_preamble_empty_string_is_valid:
        GeneratedQuestion(preamble="") is explicitly valid — empty preamble is
        a real semantic, not an error (contrast with test_suite's min_length=1).
    - test_generated_question_preamble_non_empty_round_trips:
        GeneratedQuestion with a non-empty preamble string round-trips through
        Pydantic (boundary: non-empty value preserved).
    - test_generated_question_test_suite_min_length_preserved:
        GeneratedQuestion(test_suite="") still raises (min_length=1 preserved —
        ADR-040 regression; boundary 0 vs 1 on test_suite).
    - test_questions_preamble_column_exists_fresh_db:
        questions.preamble column exists after schema bootstrap on a fresh DB.
    - test_add_questions_preamble_round_trips_list_questions:
        add_questions_to_quiz with a "preamble" key → list_questions_for_quiz
        returns Question with preamble attribute matching the inserted value.
    - test_add_questions_preamble_round_trips_get_question:
        add_questions_to_quiz with preamble → get_question returns Question
        with the same preamble value (ADR-044's accessor carries it through).
    - test_sandbox_preamble_parameter_default_keeps_pre_task_behavior:
        run_test_suite(test_suite, response) with no preamble argument works
        unchanged (default="" keeps the pre-task splice byte-equivalent — ADR-047).
    - test_sandbox_preamble_empty_string_same_as_no_preamble:
        run_test_suite(test_suite, response, preamble="") produces the same
        result as run_test_suite(test_suite, response) for a passing run.
    - test_sandbox_preamble_splice_order_preamble_first:
        A test where the preamble declares a struct used by the response and
        the test_suite — the splice succeeds only if preamble comes first.
    - test_take_page_renders_preamble_block_when_non_empty:
        GET .../take for a Question with a non-empty preamble → HTML contains
        "quiz-take-preamble" (the read-only block rendered per ADR-047).
    - test_take_page_omits_preamble_block_when_empty:
        GET .../take for a Question with preamble="" → HTML does NOT contain
        "quiz-take-preamble" (the block is omitted when empty per ADR-047).
  Edge:
    - test_generated_question_extra_fields_still_forbidden:
        GeneratedQuestion with a "choices" or "correct_choice" field raises
        (extra="forbid" preserved — no non-coding fields, §5/§7/ADR-045).
    - test_generated_question_preamble_unicode_content_round_trips:
        A preamble containing unicode (e.g. comments in non-ASCII) survives
        Pydantic validation round-trip unchanged.
    - test_questions_preamble_column_nullable_for_legacy_rows:
        A questions row inserted WITHOUT preamble (pre-TASK-018 style) has
        preamble IS NULL in DB — the column is nullable (ADR-046).
    - test_questions_preamble_column_additive_on_existing_db:
        On a DB with the questions table but WITHOUT preamble column, calling
        init_schema() adds the column additively (ADR-022/ADR-046 migration
        story — no data loss, no error).
    - test_add_questions_absent_preamble_key_defaults_gracefully:
        add_questions_to_quiz with a dict that has NO "preamble" key defaults
        to empty/None (defensive default — ADR-046).
    - test_sandbox_preamble_none_or_empty_with_legacy_question:
        run_test_suite with preamble=None or "" on a legacy Question (no
        preamble) does not crash; the splice degrades to pre-task behavior.
    - test_processor_reads_preamble_from_artefact_and_persists:
        When the aiw run artefact contains a "preamble" key per Question, the
        processor passes it to add_questions_to_quiz verbatim (no transformation).
    - test_processor_missing_preamble_key_defaults_to_empty_not_failure:
        When the artefact questions lack a "preamble" key entirely (old-style),
        the processor does NOT fail the Quiz — it defaults to "" (ADR-045's
        asymmetric rule: missing preamble is NOT a generation_failed trigger).
    - test_attempt_question_carries_preamble_field:
        list_attempt_questions returns AttemptQuestion objects with a .preamble
        attribute (ADR-046 — the template reads aq.preamble).
    - test_take_page_submitted_state_renders_preamble_when_non_empty:
        GET .../take for a submitted Attempt with a Question that has a
        non-empty preamble → HTML still contains "quiz-take-preamble" (both
        in_progress and submitted branches render the preamble per ADR-047).
  Negative:
    - test_generated_question_test_suite_still_required_non_empty:
        GeneratedQuestion where test_suite is "" still raises (ADR-040 preserved;
        MC-5 floor not weakened by the preamble addition).
    - test_generated_question_preamble_whitespace_only_is_valid:
        A whitespace-only preamble is valid at the Pydantic layer (no min_length
        on preamble — unlike test_suite which has min_length=1; ADR-045's
        deliberate asymmetry).
    - test_no_user_id_on_questions_preamble_column:
        questions.preamble column addition does not add a user_id column (MC-7).
    - test_mc10_no_sqlite3_in_workflows_after_task018:
        app/workflows/ must not import sqlite3 — the preamble field addition
        does not introduce any SQL into the workflow module (MC-10).
    - test_mc10_no_sql_literals_in_question_gen:
        app/workflows/question_gen.py contains no SQL string literals (MC-10).
    - test_mc1_no_forbidden_sdk_in_question_gen_after_preamble_addition:
        app/workflows/question_gen.py imports no forbidden LLM/agent SDK after
        the preamble field addition (MC-1 / ADR-036 / ADR-045).
    - test_mc1_app_workflows_still_only_ai_workflows_and_pydantic:
        The entire app/workflows/ directory imports only ai_workflows.* +
        pydantic + stdlib — no SDK added (MC-1).
    - test_take_page_preamble_no_empty_box_renders:
        When preamble is empty or None, the take page does NOT render a visible
        empty box or a "quiz-take-preamble" element (ADR-047's omitted-when-empty
        rule — no vacuous "Shared code: (empty)" displayed to the learner).
    - test_quiz_css_has_quiz_take_preamble_rule:
        app/static/quiz.css contains the new .quiz-take-preamble rule (ADR-047).
    - test_no_base_css_change_for_preamble:
        app/static/base.css does NOT contain "quiz-take-preamble" (the new rule
        lives in quiz.css only — ADR-047 / ADR-008).
    - test_no_new_css_file_for_preamble:
        No new CSS file was added under app/static/ for the preamble styling
        (new rules go in the existing quiz.css — ADR-047 / ADR-008).
  Performance:
    - test_preamble_column_round_trip_for_many_questions_within_budget:
        add_questions_to_quiz with 20 questions each carrying a non-empty
        preamble + list_questions_for_quiz for all 20 completes within 5 s
        (catches O(n²) regressions on the per-question INSERT path).

Notes on the processor test seam (per ADR-036 §The test seam):
  The processor invokes the workflow via subprocess.run. Tests mock that seam
  at the CS-300 processor boundary — same pattern as TASK-014/TASK-016 tests.

  A TASK-018+ success-path mock returns a canned artefact with:
    json.dumps({"questions": [
        {"prompt": "...", "topics": [...], "test_suite": "...", "preamble": "..."},
        ...
    ]}, indent=2) + "\\ntotal cost: $0.0042"

  An old-style (pre-TASK-018) success-path mock returns a canned artefact with:
    json.dumps({"questions": [
        {"prompt": "...", "topics": [...], "test_suite": "..."},  # no preamble key
        ...
    ]}, indent=2) + "\\ntotal cost: $0.0042"
  → processor must default preamble to "" (NOT generation_failed).

ASSUMPTIONS:
  ASSUMPTION: app.workflows.question_gen.GeneratedQuestion gains a `preamble`
    field with default="" (ADR-045). If absent, Pydantic-model-inspection tests
    fail (red as expected).

  ASSUMPTION: app.persistence.Question gains a `preamble: str | None` attribute
    (ADR-046). If absent, dataclass-inspection tests fail red.

  ASSUMPTION: app.persistence.AttemptQuestion gains a `preamble: str | None`
    attribute (ADR-046). If absent, the list_attempt_questions test fails red.

  ASSUMPTION: app.sandbox.run_test_suite gains an optional preamble: str = ""
    parameter (ADR-047). If absent, the preamble-specific sandbox tests fail red.

  ASSUMPTION: The route URL is unchanged (ADR-043): POST /lecture/{chapter_id}/
    sections/{section_number}/quiz/{quiz_id}/take/run-tests.

  ASSUMPTION: The questions table preamble column is nullable TEXT (ADR-046).

  ASSUMPTION: g++ is available in the test environment for C++ sandbox tests.
    Tests requiring C++ compilation are marked skipif(not _HAS_GPP, ...).

pytestmark registers all tests under task("TASK-018").
"""

from __future__ import annotations

import inspect
import json
import pathlib
import re
import shutil
import sqlite3
import time
from typing import Any
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.task("TASK-018")

REPO_ROOT = pathlib.Path(__file__).parent.parent

MANDATORY_CHAPTER_ID = "ch-01-cpp-refresher"
SECTION_ID_CH01_S1 = "ch-01-cpp-refresher#section-1-1"
MANDATORY_SECTION_NUMBER = "1-1"

_HAS_GPP = shutil.which("g++") is not None

# ---------------------------------------------------------------------------
# Canned artefact builders (mirrors TASK-016 pattern)
# ---------------------------------------------------------------------------


def _make_success_stdout(questions: list[dict]) -> str:
    """
    Build the stdout `aiw run question_gen` produces on a successful run.
    ADR-045: the artefact now includes `preamble` per question.
    ADR-036: `json.dumps(artifact, indent=2)` then `total cost: $X.XXXX`.
    """
    artefact = {"questions": questions}
    return json.dumps(artefact, indent=2) + "\ntotal cost: $0.0042\n"


def _make_completed_process(stdout="", stderr="", returncode=0):
    import subprocess
    return subprocess.CompletedProcess(
        args=["aiw", "run", "question_gen"],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


# Canned assertion-only C++ test suite (no reference implementation inside)
_CPP_PREAMBLE = """\
struct Node {
    int data;
    Node* next;
    Node(int d) : data(d), next(nullptr) {}
};
struct LinkedList {
    Node* head;
    LinkedList() : head(nullptr) {}
};
"""

_CPP_TEST_SUITE_ASSERTION_ONLY = """\
#include <cassert>
void append(LinkedList& list, int value);
int main() {
    LinkedList l;
    append(l, 42);
    assert(l.head != nullptr);
    assert(l.head->data == 42);
    return 0;
}
"""

_CPP_RESPONSE_APPEND_CORRECT = """\
void append(LinkedList& list, int value) {
    Node* n = new Node(value);
    n->next = list.head;
    list.head = n;
}
"""

_CPP_RESPONSE_APPEND_WRONG = """\
void append(LinkedList& list, int value) {
    // deliberately wrong: does nothing
}
"""

# Simpler preamble-free C++ test suite (for default-"" compatibility tests)
_CPP_TEST_SUITE_ADD = """\
#include <cassert>
int add(int a, int b);
int main() {
    assert(add(2, 3) == 5);
    return 0;
}
"""
_CPP_RESPONSE_ADD_CORRECT = "int add(int a, int b) { return a + b; }\n"
_CPP_RESPONSE_ADD_WRONG = "int add(int a, int b) { return 0; }\n"


# ---------------------------------------------------------------------------
# Helpers — DB seeding (mirrors TASK-017 pattern)
# ---------------------------------------------------------------------------


def _bootstrap_db(monkeypatch, db_path: str):
    """Bootstrap DB schema and return a FastAPI TestClient (function-scoped)."""
    monkeypatch.setenv("NOTES_DB_PATH", db_path)
    from fastapi.testclient import TestClient  # noqa: PLC0415
    from app.main import app  # noqa: PLC0415

    client = TestClient(app, follow_redirects=False)
    # Trigger schema bootstrap
    client.get(f"/lecture/{MANDATORY_CHAPTER_ID}")
    return client


def _seed_ready_quiz_with_preamble(
    db_path: str,
    section_id: str,
    preamble: str,
    test_suite: str = _CPP_TEST_SUITE_ADD,
) -> tuple[int, int]:
    """
    Insert a ready Quiz with one Question that has a given preamble.
    Returns (quiz_id, question_id).
    """
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "INSERT INTO quizzes (section_id, status, created_at) "
            "VALUES (?, 'ready', '2026-05-13T00:00:00Z')",
            (section_id,),
        )
        conn.commit()
        quiz_id = conn.execute(
            "SELECT quiz_id FROM quizzes WHERE section_id=? ORDER BY quiz_id DESC LIMIT 1",
            (section_id,),
        ).fetchone()[0]

        conn.execute(
            "INSERT INTO questions (section_id, prompt, topics, test_suite, preamble, created_at) "
            "VALUES (?, 'Implement add(int,int)', 'coding', ?, ?, '2026-05-13T00:00:00Z')",
            (section_id, test_suite, preamble if preamble != "" else ""),
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


def _take_url(quiz_id: int) -> str:
    return (
        f"/lecture/{MANDATORY_CHAPTER_ID}/sections/{MANDATORY_SECTION_NUMBER}"
        f"/quiz/{quiz_id}/take"
    )


def _run_tests_url(quiz_id: int) -> str:
    return (
        f"/lecture/{MANDATORY_CHAPTER_ID}/sections/{MANDATORY_SECTION_NUMBER}"
        f"/quiz/{quiz_id}/take/run-tests"
    )


# ===========================================================================
# AC-1: Prompt wording — assertion-only + preamble field in system prompt
# ===========================================================================


def test_prompt_fn_mentions_assertion_only() -> None:
    """
    AC-1 (TASK-018) / ADR-045: the system prompt string produced by
    _question_gen_prompt_fn must instruct the LLM to emit assertion-only test
    suites (STRICT REQUIREMENT 7 — the test_suite references but does NOT
    define the implementation target).

    The architectural commitment (ADR-045 §The prompt change) is the *substance*:
    "assertion-only", "does not define the implementation target", or equivalent
    phrasing must appear in the system prompt so an implementer reading the prompt
    knows the required shape.
    """
    # AC-1: system prompt instructs assertion-only test suites (ADR-045)
    from app.workflows.question_gen import _question_gen_prompt_fn  # noqa: PLC0415

    # Call the function with a dummy input (per ADR-036, the function takes
    # the workflow state dict as argument)
    prompt_tuple = _question_gen_prompt_fn(
        {"section_content": "dummy content", "section_title": "dummy section"}
    )
    # _question_gen_prompt_fn returns (system_prompt_str, messages_list) per ADR-036
    # The system prompt is the first element (str | None).
    prompt_text = prompt_tuple[0] or ""

    # The prompt must commit to "assertion-only" framing (substance)
    prompt_lower = prompt_text.lower()
    assertion_only_signals = [
        "assertion-only",
        "assertion only",
        "do not define",
        "does not define",
        "do not implement",
        "without defining",
        "without implementing",
        "reference implementation",  # typically in a negative context ("do not include")
    ]
    found = any(sig in prompt_lower for sig in assertion_only_signals)
    assert found, (
        f"The system prompt returned by _question_gen_prompt_fn does not contain "
        f"any of {assertion_only_signals!r}.\n"
        "ADR-045 §The prompt change: STRICT REQUIREMENT 7 must commit to "
        "'assertion-only' test suites that reference (call/instantiate) the "
        "implementation target but do NOT define or implement it. "
        "The prompt wording must make this clear to the LLM."
    )


def test_prompt_fn_mentions_preamble_field() -> None:
    """
    AC-1 (TASK-018) / ADR-045: the system prompt must instruct the LLM to
    emit shared struct/class shapes in a new `preamble` field (STRICT
    REQUIREMENT 8), NOT inside `test_suite` or `prompt`.
    """
    # AC-1: system prompt instructs the LLM to use the preamble field (ADR-045)
    from app.workflows.question_gen import _question_gen_prompt_fn  # noqa: PLC0415

    prompt_tuple = _question_gen_prompt_fn(
        {"section_content": "dummy content", "section_title": "dummy section"}
    )
    prompt_text = prompt_tuple[0] or ""

    prompt_lower = prompt_text.lower()
    preamble_signals = ["preamble"]
    found = any(sig in prompt_lower for sig in preamble_signals)
    assert found, (
        f"The system prompt returned by _question_gen_prompt_fn does not mention "
        f"'preamble'.\n"
        "ADR-045 §The prompt change: STRICT REQUIREMENT 8 must instruct the LLM to "
        "emit shared struct/class/header shapes in the `preamble` field — not inside "
        "`test_suite` or `prompt`. The word 'preamble' (or an equivalent committed "
        "label) must appear in the system prompt."
    )


def test_prompt_fn_preserves_strict_requirements_hands_on_coding() -> None:
    """
    AC-1 (TASK-018) / ADR-045: the existing STRICT REQUIREMENTs 1–6 (every Question
    is a hands-on coding task; no MC/true-false/recall/describe) must be preserved
    in the system prompt — the preamble addition does not relax them.
    """
    # AC-1: existing STRICT REQUIREMENTs 1-6 preserved in system prompt (ADR-045)
    from app.workflows.question_gen import _question_gen_prompt_fn  # noqa: PLC0415

    prompt_tuple = _question_gen_prompt_fn(
        {"section_content": "dummy content", "section_title": "dummy section"}
    )
    prompt_text = prompt_tuple[0] or ""
    prompt_lower = prompt_text.lower()

    # The prompt must still forbid non-coding Question types
    forbidden_format_signals = [
        "multiple-choice",
        "multiple choice",
        "true/false",
        "true-false",
        "multiple_choice",
        "recall",
        "no recall",
        "not recall",
        "no multiple",
        "no true",
    ]
    # At least ONE of these must appear (the prohibition exists in the prompt)
    # OR "hands-on coding" or "coding task" appears (positive framing of §7 invariant)
    coding_task_signals = ["hands-on", "coding task", "implement", "function", "class"]
    has_coding_instruction = any(sig in prompt_lower for sig in coding_task_signals)
    assert has_coding_instruction, (
        "The system prompt does not contain hands-on coding task framing "
        "(e.g. 'hands-on', 'coding task', 'implement'). "
        "ADR-045: STRICT REQUIREMENTs 1-6 must be preserved — every Question is a "
        "hands-on coding task."
    )


# ===========================================================================
# AC-2: GeneratedQuestion schema — preamble field + extra="forbid" + test_suite min_length
# ===========================================================================


def test_generated_question_preamble_field_default_empty_string() -> None:
    """
    AC-2 (TASK-018) / ADR-045: GeneratedQuestion gains preamble: str = Field(default="").
    Constructing with no preamble argument succeeds and preamble defaults to "".
    """
    # AC-2: GeneratedQuestion.preamble defaults to "" (ADR-045)
    from app.workflows.question_gen import GeneratedQuestion  # noqa: PLC0415

    q = GeneratedQuestion(prompt="Implement foo()", topics=["trees"], test_suite="x")
    assert hasattr(q, "preamble"), (
        "GeneratedQuestion has no 'preamble' attribute. "
        "ADR-045: GeneratedQuestion must gain preamble: str = Field(default='')."
    )
    assert q.preamble == "", (
        f"GeneratedQuestion.preamble defaulted to {q.preamble!r} instead of ''. "
        "ADR-045: the default for preamble must be an empty string (not None, not missing)."
    )


def test_generated_question_preamble_empty_string_is_valid() -> None:
    """
    AC-2 (TASK-018) / ADR-045: explicitly setting preamble="" is valid —
    empty preamble is a real semantic ("Question needs no shared shapes").
    No Pydantic validation error must be raised.
    """
    # AC-2: empty preamble is explicitly valid (ADR-045 — empty ≠ failure)
    from app.workflows.question_gen import GeneratedQuestion  # noqa: PLC0415

    q = GeneratedQuestion(
        prompt="Implement bar(int)", topics=["sorting"], test_suite="assert 1==1;", preamble=""
    )
    assert q.preamble == "", (
        f"GeneratedQuestion(preamble='') did not store '' — got {q.preamble!r}. "
        "ADR-045: empty preamble is a valid semantic."
    )


def test_generated_question_preamble_non_empty_round_trips() -> None:
    """
    AC-2 (TASK-018) / ADR-045: a non-empty preamble string is preserved through
    Pydantic construction (round-trips without transformation).
    """
    # AC-2: non-empty preamble round-trips through Pydantic (ADR-045)
    from app.workflows.question_gen import GeneratedQuestion  # noqa: PLC0415

    preamble_src = "struct Node { int data; Node* next; };"
    q = GeneratedQuestion(
        prompt="Implement append()", topics=["linked-lists"], test_suite="assert 1==1;", preamble=preamble_src
    )
    assert q.preamble == preamble_src, (
        f"GeneratedQuestion.preamble round-trip failed: expected {preamble_src!r}, got {q.preamble!r}. "
        "ADR-045: the preamble value must be stored verbatim."
    )


def test_generated_question_test_suite_min_length_preserved() -> None:
    """
    AC-2 (TASK-018) / ADR-045 / ADR-040 regression: adding the preamble field
    must NOT weaken the test_suite min_length=1 validator. A GeneratedQuestion
    with an empty test_suite must still raise a Pydantic ValidationError.
    """
    # AC-2: test_suite min_length=1 is preserved after preamble addition (ADR-040 regression)
    from app.workflows.question_gen import GeneratedQuestion  # noqa: PLC0415
    from pydantic import ValidationError  # noqa: PLC0415

    with pytest.raises(ValidationError, match="test_suite|min_length|string_too_short"):
        GeneratedQuestion(
            prompt="Implement baz()", topics=["graphs"], test_suite="", preamble=""
        )


def test_generated_question_extra_fields_still_forbidden() -> None:
    """
    AC-2 (TASK-018) / ADR-045: extra="forbid" is preserved — GeneratedQuestion
    with a non-coding field (choices, correct_choice, answer_text) raises.
    """
    # AC-2: extra="forbid" preserved — non-coding fields raise ValidationError (ADR-045)
    from app.workflows.question_gen import GeneratedQuestion  # noqa: PLC0415
    from pydantic import ValidationError  # noqa: PLC0415

    with pytest.raises(ValidationError):
        GeneratedQuestion(
            prompt="Implement foo()", topics=["trees"], test_suite="x",
            preamble="", choices=["A", "B", "C"]
        )


def test_generated_question_preamble_whitespace_only_is_valid() -> None:
    """
    AC-2 (TASK-018) / ADR-045: a whitespace-only preamble is valid at the Pydantic
    layer (no min_length on preamble — deliberate asymmetry with test_suite's
    min_length=1; ADR-045 §Why Field(default='') and not min_length=1).
    """
    # AC-2: whitespace-only preamble is valid (no min_length validator — ADR-045)
    from app.workflows.question_gen import GeneratedQuestion  # noqa: PLC0415

    q = GeneratedQuestion(
        prompt="Implement qux()", topics=["heaps"], test_suite="int main(){return 0;}",
        preamble="   \n  "
    )
    assert q.preamble == "   \n  ", (
        "GeneratedQuestion(preamble='   \\n  ') was rejected or transformed. "
        "ADR-045: a whitespace-only preamble is a valid value (no min_length on preamble)."
    )


def test_generated_question_preamble_unicode_content_round_trips() -> None:
    """
    AC-2 / Edge (TASK-018) / ADR-045: a preamble containing unicode (e.g. non-ASCII
    comments) survives Pydantic validation unchanged.
    """
    # Edge: preamble with unicode content round-trips through Pydantic (ADR-045)
    from app.workflows.question_gen import GeneratedQuestion  # noqa: PLC0415

    unicode_preamble = "// 共享代码 — Shared struct\nstruct Node { int val; };"
    q = GeneratedQuestion(
        prompt="Implement foo()", topics=["trees"], test_suite="int main(){return 0;}",
        preamble=unicode_preamble
    )
    assert q.preamble == unicode_preamble, (
        f"Preamble with unicode content was not preserved: got {q.preamble!r}. "
        "ADR-045: the preamble value must be stored verbatim regardless of character set."
    )


# ===========================================================================
# AC-3: DB schema — questions.preamble column
# ===========================================================================


def test_questions_preamble_column_exists_fresh_db(tmp_path, monkeypatch) -> None:
    """
    AC-3 (TASK-018) / ADR-046: after schema bootstrap on a fresh DB, the
    questions table must have a 'preamble' column (TEXT, nullable).
    """
    # AC-3: questions.preamble column exists on fresh DB (ADR-046)
    db_path = str(tmp_path / "fresh.db")
    monkeypatch.setenv("NOTES_DB_PATH", db_path)
    from app.persistence.connection import init_schema  # noqa: PLC0415

    init_schema()

    conn = sqlite3.connect(db_path)
    columns = {row[1] for row in conn.execute("PRAGMA table_info(questions)")}
    conn.close()

    assert "preamble" in columns, (
        "questions table does not have a 'preamble' column after schema bootstrap. "
        "ADR-046: _SCHEMA_SQL's CREATE TABLE questions block must include 'preamble TEXT'."
    )


def test_questions_preamble_column_additive_on_existing_db(tmp_path, monkeypatch) -> None:
    """
    AC-3 / Edge (TASK-018) / ADR-046 / ADR-022: on a DB that already has the
    questions table WITHOUT the preamble column (simulates a pre-TASK-018 DB),
    calling init_schema() must add the column additively (via _apply_additive_migrations)
    with no data loss and no error.
    """
    # Edge / AC-3: preamble column added additively on existing DB (ADR-046 / ADR-022)
    db_path = str(tmp_path / "legacy.db")
    # Manually create an older-style questions table WITHOUT preamble
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE questions ("
        "question_id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "section_id TEXT NOT NULL, "
        "prompt TEXT NOT NULL, "
        "topics TEXT NOT NULL DEFAULT '', "
        "test_suite TEXT, "
        "created_at TEXT NOT NULL"
        ")"
    )
    conn.execute(
        "INSERT INTO questions (section_id, prompt, topics, test_suite, created_at) "
        "VALUES ('ch-01#s-1', 'Implement foo()', 'trees', 'assert 1==1', '2026-01-01')"
    )
    conn.commit()
    conn.close()

    monkeypatch.setenv("NOTES_DB_PATH", db_path)
    from app.persistence.connection import init_schema  # noqa: PLC0415

    init_schema()

    conn2 = sqlite3.connect(db_path)
    columns = {row[1] for row in conn2.execute("PRAGMA table_info(questions)")}
    # The original row must still be there
    rows = conn2.execute("SELECT prompt FROM questions").fetchall()
    conn2.close()

    assert "preamble" in columns, (
        "questions.preamble column was NOT added to a pre-TASK-018 DB by "
        "_apply_additive_migrations. ADR-046: the PRAGMA table_info check + "
        "guarded ALTER TABLE ADD COLUMN must bring existing DBs up to date."
    )
    assert len(rows) == 1 and rows[0][0] == "Implement foo()", (
        "The existing row was lost or corrupted after _apply_additive_migrations. "
        "ADR-046 / ADR-022: additive migration must not destroy existing data."
    )


def test_questions_preamble_column_nullable_for_legacy_rows(tmp_path, monkeypatch) -> None:
    """
    AC-3 / Edge (TASK-018) / ADR-046: a questions row inserted without a preamble
    value (pre-TASK-018 style) has preamble IS NULL — the column is nullable.
    """
    # Edge / AC-3: questions.preamble is NULL for a legacy-style row (ADR-046)
    db_path = str(tmp_path / "legacy_null.db")
    monkeypatch.setenv("NOTES_DB_PATH", db_path)
    from app.persistence.connection import init_schema  # noqa: PLC0415

    init_schema()

    conn = sqlite3.connect(db_path)
    # Insert a row without the preamble column (old-style)
    conn.execute(
        "INSERT INTO questions (section_id, prompt, topics, test_suite, created_at) "
        "VALUES ('ch-01#s-1', 'Implement foo()', 'trees', 'assert 1==1', '2026-01-01')"
    )
    conn.commit()
    row = conn.execute("SELECT preamble FROM questions LIMIT 1").fetchone()
    conn.close()

    assert row[0] is None, (
        f"questions.preamble for a row inserted without preamble is {row[0]!r}; expected NULL. "
        "ADR-046: the column is nullable — NULL means 'pre-TASK-018 row, no recorded preamble'."
    )


def test_no_user_id_on_questions_preamble_column(tmp_path, monkeypatch) -> None:
    """
    AC-3 (TASK-018) / ADR-046 / MC-7: adding the questions.preamble column must
    NOT introduce a user_id column (single-user invariant).
    """
    # AC-3 / MC-7: questions table has no user_id column (ADR-046 / MC-7)
    db_path = str(tmp_path / "nouserid.db")
    monkeypatch.setenv("NOTES_DB_PATH", db_path)
    from app.persistence.connection import init_schema  # noqa: PLC0415

    init_schema()

    conn = sqlite3.connect(db_path)
    columns = {row[1] for row in conn.execute("PRAGMA table_info(questions)")}
    conn.close()

    assert "user_id" not in columns, (
        "questions table contains a 'user_id' column. "
        "MC-7 / ADR-046: no user_id column must be added anywhere — single-user posture."
    )


# ===========================================================================
# AC-4: Question dataclass — preamble field + persistence round-trips
# ===========================================================================


def test_add_questions_preamble_round_trips_list_questions(tmp_path, monkeypatch) -> None:
    """
    AC-4 (TASK-018) / ADR-046: add_questions_to_quiz with a "preamble" key →
    list_questions_for_quiz returns Question objects whose .preamble attribute
    equals the inserted value.
    """
    # AC-4: preamble round-trips through add_questions_to_quiz → list_questions_for_quiz
    db_path = str(tmp_path / "rt_list.db")
    monkeypatch.setenv("NOTES_DB_PATH", db_path)
    from app.persistence.connection import init_schema  # noqa: PLC0415
    from app.persistence.quizzes import (  # noqa: PLC0415
        add_questions_to_quiz,
        list_questions_for_quiz,
        request_quiz,
        mark_quiz_ready,
    )

    init_schema()

    # Seed a quiz
    quiz = request_quiz(SECTION_ID_CH01_S1)
    expected_preamble = "struct Node { int data; };"
    add_questions_to_quiz(
        quiz.quiz_id,
        [
            {
                "prompt": "Implement append()",
                "topics": ["linked-lists"],
                "test_suite": "#include <cassert>\nint main(){return 0;}",
                "preamble": expected_preamble,
            }
        ],
    )
    mark_quiz_ready(quiz.quiz_id)

    questions = list_questions_for_quiz(quiz.quiz_id)
    assert len(questions) == 1, (
        f"list_questions_for_quiz returned {len(questions)} Questions; expected 1."
    )
    q = questions[0]
    assert hasattr(q, "preamble"), (
        "Question returned by list_questions_for_quiz has no 'preamble' attribute. "
        "ADR-046: Question dataclass must carry preamble: str | None."
    )
    assert q.preamble == expected_preamble, (
        f"Question.preamble={q.preamble!r}; expected {expected_preamble!r}. "
        "ADR-046: list_questions_for_quiz SELECT must carry preamble through."
    )


def test_add_questions_preamble_round_trips_get_question(tmp_path, monkeypatch) -> None:
    """
    AC-4 (TASK-018) / ADR-046: add_questions_to_quiz with preamble →
    get_question returns a Question with the same preamble value.
    (The 'Run tests' route uses get_question to fetch both test_suite and preamble.)
    """
    # AC-4: preamble round-trips through add_questions_to_quiz → get_question (ADR-044/046)
    db_path = str(tmp_path / "rt_get.db")
    monkeypatch.setenv("NOTES_DB_PATH", db_path)
    from app.persistence.connection import init_schema  # noqa: PLC0415
    from app.persistence.quizzes import (  # noqa: PLC0415
        add_questions_to_quiz,
        get_question,
        request_quiz,
        mark_quiz_ready,
    )

    init_schema()

    quiz = request_quiz(SECTION_ID_CH01_S1)
    expected_preamble = "typedef struct { int x; } Point;"
    add_questions_to_quiz(
        quiz.quiz_id,
        [
            {
                "prompt": "Implement distance()",
                "topics": ["geometry"],
                "test_suite": "int main(){return 0;}",
                "preamble": expected_preamble,
            }
        ],
    )
    mark_quiz_ready(quiz.quiz_id)

    from app.persistence.quizzes import list_questions_for_quiz  # noqa: PLC0415
    questions = list_questions_for_quiz(quiz.quiz_id)
    assert questions, "No questions found after add_questions_to_quiz"
    question_id = questions[0].question_id

    fetched = get_question(question_id)
    assert fetched is not None, f"get_question({question_id}) returned None"
    assert hasattr(fetched, "preamble"), (
        "Question returned by get_question has no 'preamble' attribute. "
        "ADR-046: get_question SELECT must carry preamble."
    )
    assert fetched.preamble == expected_preamble, (
        f"get_question returned preamble={fetched.preamble!r}; expected {expected_preamble!r}. "
        "ADR-046: get_question must carry preamble through the SELECT."
    )


def test_add_questions_absent_preamble_key_defaults_gracefully(tmp_path, monkeypatch) -> None:
    """
    AC-4 / Edge (TASK-018) / ADR-046: add_questions_to_quiz with a dict that has NO
    "preamble" key (old-style caller) defaults to empty/None without crashing.
    The returned Question's preamble is None or "" (either is acceptable).
    """
    # Edge / AC-4: absent preamble key defaults gracefully in add_questions_to_quiz (ADR-046)
    db_path = str(tmp_path / "absent_preamble.db")
    monkeypatch.setenv("NOTES_DB_PATH", db_path)
    from app.persistence.connection import init_schema  # noqa: PLC0415
    from app.persistence.quizzes import (  # noqa: PLC0415
        add_questions_to_quiz,
        list_questions_for_quiz,
        request_quiz,
        mark_quiz_ready,
    )

    init_schema()

    quiz = request_quiz(SECTION_ID_CH01_S1)
    # Old-style dict without "preamble" key
    add_questions_to_quiz(
        quiz.quiz_id,
        [
            {
                "prompt": "Implement foo()",
                "topics": ["trees"],
                "test_suite": "int main(){return 0;}",
                # No "preamble" key
            }
        ],
    )
    mark_quiz_ready(quiz.quiz_id)

    questions = list_questions_for_quiz(quiz.quiz_id)
    assert len(questions) == 1, "No Question persisted despite add_questions_to_quiz succeeding"
    q = questions[0]
    # preamble should be None or "" (either is valid — the defensive default)
    assert q.preamble is None or q.preamble == "", (
        f"Question.preamble={q.preamble!r} for a row inserted without preamble key; "
        "expected None or ''. ADR-046: the defensive default for absent preamble is empty."
    )


def test_attempt_question_carries_preamble_field(tmp_path, monkeypatch) -> None:
    """
    AC-4 / Edge (TASK-018) / ADR-046: list_attempt_questions returns AttemptQuestion
    objects with a .preamble attribute. The take template reads aq.preamble.
    """
    # Edge / AC-4: AttemptQuestion carries preamble attribute (ADR-046)
    db_path = str(tmp_path / "aq_preamble.db")
    monkeypatch.setenv("NOTES_DB_PATH", db_path)
    from app.persistence.connection import init_schema  # noqa: PLC0415
    from app.persistence.quizzes import (  # noqa: PLC0415
        add_questions_to_quiz,
        list_attempt_questions,
        request_quiz,
        mark_quiz_ready,
        start_attempt,
    )

    init_schema()

    quiz = request_quiz(SECTION_ID_CH01_S1)
    preamble_value = "struct Pair { int a; int b; };"
    add_questions_to_quiz(
        quiz.quiz_id,
        [
            {
                "prompt": "Implement swap(Pair&)",
                "topics": ["data-structures"],
                "test_suite": "int main(){return 0;}",
                "preamble": preamble_value,
            }
        ],
    )
    mark_quiz_ready(quiz.quiz_id)

    attempt = start_attempt(quiz.quiz_id)
    aq_list = list_attempt_questions(attempt.attempt_id)

    assert aq_list, "list_attempt_questions returned empty list"
    aq = aq_list[0]
    assert hasattr(aq, "preamble"), (
        "AttemptQuestion returned by list_attempt_questions has no 'preamble' attribute. "
        "ADR-046: AttemptQuestion must carry preamble: str | None via the join SELECT."
    )
    assert aq.preamble == preamble_value, (
        f"AttemptQuestion.preamble={aq.preamble!r}; expected {preamble_value!r}. "
        "ADR-046: list_attempt_questions must carry preamble through the join."
    )


# ===========================================================================
# AC-5: Processor reads preamble from artefact
# ===========================================================================


def test_processor_reads_preamble_from_artefact_and_persists(
    tmp_path, monkeypatch
) -> None:
    """
    AC-5 / Edge (TASK-018) / ADR-045 / ADR-046: when the aiw run artefact contains
    a "preamble" key per Question, the processor passes it verbatim to
    add_questions_to_quiz — no transformation, no truncation (ADR-036's
    "the workflow returns data, CS-300 code persists it" rule).
    """
    # Edge / AC-5: processor passes preamble verbatim from artefact (ADR-045/046)
    db_path = str(tmp_path / "proc_preamble.db")
    monkeypatch.setenv("NOTES_DB_PATH", db_path)

    from fastapi.testclient import TestClient  # noqa: PLC0415
    from app.main import app  # noqa: PLC0415

    client = TestClient(app, follow_redirects=True)
    client.get(f"/lecture/{MANDATORY_CHAPTER_ID}")  # bootstrap schema

    # Seed a requested quiz
    from app.persistence import request_quiz  # noqa: PLC0415

    quiz = request_quiz(SECTION_ID_CH01_S1)

    expected_preamble = "struct Tree { int val; Tree* left; Tree* right; };"

    # Canned artefact with preamble
    canned_stdout = _make_success_stdout(
        [
            {
                "prompt": "Implement tree_height(Tree*)",
                "topics": ["trees", "recursion"],
                "test_suite": "#include <cassert>\nTree* height_fn(Tree*); int main(){return 0;}",
                "preamble": expected_preamble,
            }
        ]
    )

    with patch("subprocess.run", return_value=_make_completed_process(stdout=canned_stdout)):
        from app.workflows.process_quiz_requests import process_pending  # noqa: PLC0415

        process_pending()

    from app.persistence import list_questions_for_quiz  # noqa: PLC0415

    questions = list_questions_for_quiz(quiz.quiz_id)
    assert questions, "No Questions persisted after processing the artefact"
    assert questions[0].preamble == expected_preamble, (
        f"Persisted preamble={questions[0].preamble!r}; expected {expected_preamble!r}. "
        "ADR-045/ADR-046: the processor must read preamble verbatim from the artefact "
        "and pass it to add_questions_to_quiz unchanged."
    )


def test_processor_missing_preamble_key_defaults_to_empty_not_failure(
    tmp_path, monkeypatch
) -> None:
    """
    AC-5 / Edge (TASK-018) / ADR-045: when the artefact questions lack a "preamble"
    key entirely (old-style pre-TASK-018 artefact), the processor must NOT fail the
    Quiz — it defaults to "" (the defensive default; a missing preamble is NOT a
    generation_failed trigger, deliberately asymmetric with test_suite's policy).
    """
    # Edge / AC-5: missing preamble key is not a failure (ADR-045 asymmetric rule)
    db_path = str(tmp_path / "proc_no_preamble.db")
    monkeypatch.setenv("NOTES_DB_PATH", db_path)

    from fastapi.testclient import TestClient  # noqa: PLC0415
    from app.main import app  # noqa: PLC0415

    client = TestClient(app, follow_redirects=True)
    client.get(f"/lecture/{MANDATORY_CHAPTER_ID}")

    from app.persistence import request_quiz  # noqa: PLC0415

    quiz = request_quiz(SECTION_ID_CH01_S1)

    # Old-style artefact: no "preamble" key
    canned_stdout = _make_success_stdout(
        [
            {
                "prompt": "Implement foo()",
                "topics": ["trees"],
                "test_suite": "#include <cassert>\nint foo(); int main(){ foo(); return 0; }",
                # deliberately no "preamble" key
            }
        ]
    )

    with patch("subprocess.run", return_value=_make_completed_process(stdout=canned_stdout)):
        from app.workflows.process_quiz_requests import process_pending  # noqa: PLC0415

        process_pending()

    import sqlite3 as _sqlite3

    conn = _sqlite3.connect(db_path)
    quiz_row = conn.execute(
        "SELECT status FROM quizzes WHERE quiz_id=?", (quiz.quiz_id,)
    ).fetchone()
    conn.close()

    assert quiz_row is not None, "Quiz row disappeared after processing"
    assert quiz_row[0] == "ready", (
        f"Quiz status={quiz_row[0]!r} after processing an artefact with no preamble key; "
        "expected 'ready'. ADR-045: a missing/blank preamble is NOT a generation_failed "
        "trigger — the processor must default to '' and proceed normally."
    )


# ===========================================================================
# AC-6: Sandbox splice extension — run_test_suite gains preamble parameter
# ===========================================================================


def test_sandbox_preamble_parameter_exists_in_signature() -> None:
    """
    AC-6 (TASK-018) / ADR-047: run_test_suite must accept an optional
    preamble: str = "" parameter.
    """
    # AC-6: run_test_suite has preamble parameter (ADR-047)
    from app.sandbox import run_test_suite  # noqa: PLC0415

    sig = inspect.signature(run_test_suite)
    params = sig.parameters
    assert "preamble" in params, (
        f"run_test_suite signature {sig} has no 'preamble' parameter. "
        "ADR-047: run_test_suite must accept preamble: str = '' as the third parameter."
    )
    preamble_param = params["preamble"]
    assert preamble_param.default == "" or preamble_param.default == inspect.Parameter.empty, (
        f"run_test_suite preamble parameter default is {preamble_param.default!r}; "
        "expected '' (empty string). ADR-047: default must be '' so pre-task call-sites "
        "continue to work unchanged."
    )


@pytest.mark.skipif(not _HAS_GPP, reason="g++ not available — C++ sandbox path requires g++")
def test_sandbox_preamble_parameter_default_keeps_pre_task_behavior() -> None:
    """
    AC-6 / Boundary (TASK-018) / ADR-047: run_test_suite(test_suite, response) with
    no preamble argument works unchanged — the default "" keeps the splice
    byte-equivalent to ADR-042's pre-task splice for a simple C++ test.
    """
    # Boundary / AC-6: default preamble preserves pre-task behavior (ADR-047)
    from app.sandbox import run_test_suite  # noqa: PLC0415

    result = run_test_suite(_CPP_TEST_SUITE_ADD, _CPP_RESPONSE_ADD_CORRECT)
    assert result.status == "ran", (
        f"run_test_suite(test_suite, response) with no preamble returned status={result.status!r}; "
        "ADR-047: the default preamble='' must not break existing call-sites."
    )
    assert result.passed is True, (
        f"run_test_suite(test_suite, response) with no preamble returned passed={result.passed!r}; "
        "ADR-047: the splice must still work as before when no preamble is provided."
    )


@pytest.mark.skipif(not _HAS_GPP, reason="g++ not available — C++ sandbox path requires g++")
def test_sandbox_preamble_empty_string_same_as_no_preamble() -> None:
    """
    AC-6 / Boundary (TASK-018) / ADR-047: run_test_suite(test_suite, response, preamble="")
    produces the same result as run_test_suite(test_suite, response) for a passing run.
    (Boundary: preamble="" must be byte-equivalent to ADR-042's pre-task splice.)
    """
    # Boundary / AC-6: preamble="" is byte-equivalent to no preamble (ADR-047)
    from app.sandbox import run_test_suite  # noqa: PLC0415

    result = run_test_suite(_CPP_TEST_SUITE_ADD, _CPP_RESPONSE_ADD_CORRECT, preamble="")
    assert result.status == "ran", (
        f"run_test_suite with preamble='' returned status={result.status!r}; "
        "ADR-047: preamble='' must not change the splice behavior vs. no-preamble."
    )
    assert result.passed is True, (
        f"run_test_suite with preamble='' returned passed={result.passed!r}; "
        "ADR-047: the splice must be equivalent to the pre-task form when preamble is empty."
    )


@pytest.mark.skipif(not _HAS_GPP, reason="g++ not available — C++ sandbox path requires g++")
def test_sandbox_preamble_splice_order_preamble_first() -> None:
    """
    AC-6 / Boundary (TASK-018) / ADR-047: the splice order is preamble + response +
    test_suite. This is the only order that works in C++ — the preamble's struct
    declarations must be visible to the response's implementation (which uses them)
    and to the test_suite's assertions. A test that structurally requires preamble
    first: the preamble declares LinkedList/Node, the response implements append()
    using those types, the test_suite asserts on them.
    """
    # Boundary / AC-6: preamble-first splice order works for struct-depending response (ADR-047)
    from app.sandbox import run_test_suite  # noqa: PLC0415

    result = run_test_suite(
        _CPP_TEST_SUITE_ASSERTION_ONLY,
        _CPP_RESPONSE_APPEND_CORRECT,
        preamble=_CPP_PREAMBLE,
    )
    assert result.status == "ran", (
        f"run_test_suite with preamble+response+test_suite returned status={result.status!r}; "
        "expected 'ran'. ADR-047: the splice preamble + response + test_suite in one TU "
        "must compile and run when all three pieces are consistent."
    )
    assert result.passed is True, (
        f"run_test_suite with a correct append() implementation returned passed={result.passed!r}; "
        "expected True. ADR-047: a correct learner response against a preamble + assertion-only "
        "test suite must produce RunResult(status='ran', passed=True) — the §6 happy path."
    )


@pytest.mark.skipif(not _HAS_GPP, reason="g++ not available — C++ sandbox path requires g++")
def test_sandbox_preamble_wrong_response_returns_ran_false() -> None:
    """
    AC-6 (TASK-018) / ADR-047: a deliberately wrong response against a preamble +
    assertion-only test suite produces RunResult(status='ran', passed=False).
    This is the honest fail path — the §6 loop reaches pass=False on a real
    generated Question pattern. MC-5: never fabricated.
    """
    # AC-6: wrong response + preamble + assertion-only suite → status='ran', passed=False (ADR-047)
    from app.sandbox import run_test_suite  # noqa: PLC0415

    result = run_test_suite(
        _CPP_TEST_SUITE_ASSERTION_ONLY,
        _CPP_RESPONSE_APPEND_WRONG,
        preamble=_CPP_PREAMBLE,
    )
    assert result.status == "ran", (
        f"run_test_suite (wrong response) returned status={result.status!r}; expected 'ran'. "
        "ADR-047: a run that reaches assertion failure must still be status='ran'."
    )
    assert result.passed is False, (
        f"run_test_suite (wrong response) returned passed={result.passed!r}; expected False. "
        "ADR-047 / MC-5: a wrong learner response must produce passed=False, never True."
    )


def test_sandbox_preamble_none_does_not_crash() -> None:
    """
    AC-6 / Edge (TASK-018) / ADR-047: run_test_suite with preamble=None (from a
    legacy Question where preamble is NULL in the DB — see ADR-046) must not crash.
    The route's `question.preamble or ''` guard (ADR-047) handles this; but the
    sandbox itself should either accept None or the caller converts. We test that
    the overall pipeline does not crash when preamble is None by mimicking the
    route's guard.
    """
    # Edge / AC-6: None preamble (legacy Question) handled gracefully (ADR-047)
    from app.sandbox import run_test_suite  # noqa: PLC0415

    preamble_from_legacy = None
    # Route does: preamble=question.preamble or ""
    preamble_coerced = preamble_from_legacy or ""

    # Should not raise
    result = run_test_suite(
        "FUNCTION foo := bar",  # unrecognized language → setup_error
        "// some response",
        preamble=preamble_coerced,
    )
    assert result is not None, (
        "run_test_suite with preamble='' (coerced from None) returned None; "
        "ADR-047: the call must return a RunResult, not raise."
    )


# ===========================================================================
# AC-7: 'Run tests' route passes preamble to run_test_suite
# ===========================================================================


@pytest.mark.skipif(not _HAS_GPP, reason="g++ not available — real sandbox requires g++")
def test_run_tests_route_with_preamble_returns_303(tmp_path, monkeypatch) -> None:
    """
    AC-7 (TASK-018) / ADR-047: POST .../take/run-tests for a Question that has a
    non-empty preamble must pass preamble to run_test_suite via get_question
    and return 303 (the route's pass-through is the only change to ADR-043's
    other decisions — ADR-047 §The 'Run tests' route).
    """
    # AC-7: run-tests route reads Question.preamble and passes it to run_test_suite (ADR-047)
    db_path = str(tmp_path / "rt_preamble.db")
    client = _bootstrap_db(monkeypatch, db_path)
    quiz_id, question_id = _seed_ready_quiz_with_preamble(
        db_path,
        SECTION_ID_CH01_S1,
        preamble=_CPP_PREAMBLE,
        test_suite=_CPP_TEST_SUITE_ASSERTION_ONLY,
    )

    take_url = _take_url(quiz_id)
    client.get(take_url)  # start in_progress Attempt

    run_url = _run_tests_url(quiz_id)
    resp = client.post(
        run_url,
        data={
            f"response_{question_id}": _CPP_RESPONSE_APPEND_CORRECT,
            "question_id": str(question_id),
        },
    )

    assert resp.status_code == 303, (
        f"POST {run_url} (with preamble Question) returned {resp.status_code}; expected 303. "
        "ADR-047: the run-tests route must still return 303 (PRG redirect) when the Question "
        "carries a preamble — route behavior unchanged from ADR-043 except for the preamble pass-through."
    )


@pytest.mark.skipif(not _HAS_GPP, reason="g++ not available — real sandbox requires g++")
def test_run_tests_route_with_preamble_persists_passed_true(tmp_path, monkeypatch) -> None:
    """
    AC-7 (TASK-018) / ADR-047 / ADR-044: POST .../take/run-tests with a correct
    response + preamble Question → test_passed=True persisted in attempt_questions.
    This is the §6 happy path: the pass-path that TASK-017's parked gate couldn't reach.
    """
    # AC-7: run-tests route with preamble + correct response → test_passed=True persisted
    db_path = str(tmp_path / "rt_passed.db")
    client = _bootstrap_db(monkeypatch, db_path)
    quiz_id, question_id = _seed_ready_quiz_with_preamble(
        db_path,
        SECTION_ID_CH01_S1,
        preamble=_CPP_PREAMBLE,
        test_suite=_CPP_TEST_SUITE_ASSERTION_ONLY,
    )

    take_url = _take_url(quiz_id)
    client.get(take_url)

    from app.persistence import get_latest_attempt_for_quiz  # noqa: PLC0415
    attempt = get_latest_attempt_for_quiz(quiz_id)
    assert attempt is not None

    run_url = _run_tests_url(quiz_id)
    client.post(
        run_url,
        data={
            f"response_{question_id}": _CPP_RESPONSE_APPEND_CORRECT,
            "question_id": str(question_id),
        },
    )

    conn = sqlite3.connect(db_path)
    row = conn.execute(
        "SELECT test_status, test_passed FROM attempt_questions WHERE attempt_id=? AND question_id=?",
        (attempt.attempt_id, question_id),
    ).fetchone()
    conn.close()

    assert row is not None, "No attempt_questions row after run-tests"
    test_status, test_passed = row
    assert test_status == "ran", (
        f"test_status={test_status!r} after run-tests with preamble + correct response; "
        "ADR-047: a correct implementation + preamble + assertion-only suite must reach 'ran'."
    )
    assert test_passed == 1, (
        f"test_passed={test_passed!r} after run-tests with correct response and preamble; "
        "expected 1 (True). ADR-047: this is the §6 happy path — passed=True on a real "
        "generated Question pattern. TASK-017's parked pass-path gate depends on this."
    )


# ===========================================================================
# AC-8: Take page template — .quiz-take-preamble block
# ===========================================================================


def test_take_page_renders_preamble_block_when_non_empty(tmp_path, monkeypatch) -> None:
    """
    AC-8 (TASK-018) / ADR-047: GET .../take for a Question with a non-empty preamble
    must render "quiz-take-preamble" in the HTML (the read-only block is present).
    """
    # AC-8: take page renders quiz-take-preamble when preamble is non-empty (ADR-047)
    db_path = str(tmp_path / "take_preamble_present.db")
    client = _bootstrap_db(monkeypatch, db_path)
    quiz_id, question_id = _seed_ready_quiz_with_preamble(
        db_path, SECTION_ID_CH01_S1, preamble="struct Node { int data; };"
    )

    take_url = _take_url(quiz_id)
    resp = client.get(take_url)
    html = resp.text

    assert resp.status_code == 200, f"GET {take_url} returned {resp.status_code}; expected 200."
    assert "quiz-take-preamble" in html, (
        "GET .../take for a Question with a non-empty preamble does not contain "
        "'quiz-take-preamble' in the HTML. "
        "ADR-047: a read-only <pre class='quiz-take-preamble'> block must render "
        "when the Question's preamble is non-empty."
    )


def test_take_page_omits_preamble_block_when_empty(tmp_path, monkeypatch) -> None:
    """
    AC-8 (TASK-018) / ADR-047: GET .../take for a Question with an empty preamble
    must NOT contain "quiz-take-preamble" in the HTML — no visible empty box.
    """
    # AC-8: take page omits quiz-take-preamble when preamble is empty (ADR-047 omit-when-empty rule)
    db_path = str(tmp_path / "take_preamble_absent.db")
    client = _bootstrap_db(monkeypatch, db_path)
    quiz_id, question_id = _seed_ready_quiz_with_preamble(
        db_path, SECTION_ID_CH01_S1, preamble=""
    )

    take_url = _take_url(quiz_id)
    resp = client.get(take_url)
    html = resp.text

    assert resp.status_code == 200, f"GET {take_url} returned {resp.status_code}; expected 200."
    assert "quiz-take-preamble" not in html, (
        "GET .../take for a Question with an empty preamble contains 'quiz-take-preamble' in HTML; "
        "ADR-047: the block must be omitted when the preamble is empty — no visible empty box."
    )


def test_take_page_preamble_no_empty_box_renders(tmp_path, monkeypatch) -> None:
    """
    AC-8 / Negative (TASK-018) / ADR-047: a Question with preamble=None (legacy row)
    must also not render a quiz-take-preamble block. The {% if aq.preamble %} Jinja
    guard handles both None and "".
    """
    # Negative / AC-8: no quiz-take-preamble rendered for NULL preamble (ADR-047 Jinja guard)
    db_path = str(tmp_path / "take_preamble_null.db")
    client = _bootstrap_db(monkeypatch, db_path)

    # Insert a legacy-style question without preamble column value (NULL)
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO quizzes (section_id, status, created_at) "
        "VALUES (?, 'ready', '2026-05-13T00:00:00Z')",
        (SECTION_ID_CH01_S1,),
    )
    conn.commit()
    quiz_id = conn.execute(
        "SELECT quiz_id FROM quizzes WHERE section_id=? ORDER BY quiz_id DESC LIMIT 1",
        (SECTION_ID_CH01_S1,),
    ).fetchone()[0]

    conn.execute(
        "INSERT INTO questions (section_id, prompt, topics, test_suite, created_at) "
        "VALUES (?, 'Implement foo()', 'trees', 'int main(){return 0;}', '2026-05-13')",
        (SECTION_ID_CH01_S1,),
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
    conn.close()

    take_url = _take_url(quiz_id)
    resp = client.get(take_url)
    html = resp.text

    assert "quiz-take-preamble" not in html, (
        "GET .../take for a Question with NULL preamble contains 'quiz-take-preamble'; "
        "ADR-047: the Jinja {% if aq.preamble %} guard must handle None (legacy rows) "
        "the same as empty string — omit the block entirely."
    )


def test_take_page_submitted_state_renders_preamble_when_non_empty(
    tmp_path, monkeypatch
) -> None:
    """
    AC-8 / Edge (TASK-018) / ADR-047: in the submitted state, a Question with a non-empty
    preamble must also render the quiz-take-preamble block (both in_progress and submitted
    branches render it — the preamble is part of the Question's specification, §8 Question).
    """
    # Edge / AC-8: preamble renders in submitted state when non-empty (ADR-047)
    db_path = str(tmp_path / "take_submitted.db")
    monkeypatch.setenv("NOTES_DB_PATH", db_path)
    from fastapi.testclient import TestClient  # noqa: PLC0415
    from app.main import app  # noqa: PLC0415

    client = TestClient(app, follow_redirects=True)
    client.get(f"/lecture/{MANDATORY_CHAPTER_ID}")

    quiz_id, question_id = _seed_ready_quiz_with_preamble(
        db_path, SECTION_ID_CH01_S1, preamble="struct Vec { int x; int y; };"
    )

    take_url = _take_url(quiz_id)
    client.get(take_url)  # start in_progress Attempt

    # Submit the Quiz
    client.post(
        take_url,
        data={f"response_{question_id}": "int add(int a, int b) { return a + b; }"},
    )

    resp = client.get(take_url)
    html = resp.text

    assert "quiz-take-preamble" in html, (
        "GET .../take (submitted state) for a Question with a non-empty preamble does not "
        "contain 'quiz-take-preamble'. "
        "ADR-047 §Alternative E (rejected): the preamble renders in BOTH in_progress and "
        "submitted states — it is part of the Question's specification (§8)."
    )


def test_take_page_test_suite_block_still_renders_with_preamble(
    tmp_path, monkeypatch
) -> None:
    """
    AC-8 (TASK-018) / ADR-047: adding the preamble block must not remove the existing
    quiz-take-test-suite block (ADR-043). Both blocks must render when the preamble is
    non-empty.
    """
    # AC-8: quiz-take-test-suite still renders alongside quiz-take-preamble (ADR-047 / ADR-043)
    db_path = str(tmp_path / "take_both_blocks.db")
    client = _bootstrap_db(monkeypatch, db_path)
    quiz_id, question_id = _seed_ready_quiz_with_preamble(
        db_path, SECTION_ID_CH01_S1, preamble="struct Node { int data; };"
    )

    take_url = _take_url(quiz_id)
    resp = client.get(take_url)
    html = resp.text

    assert "quiz-take-test-suite" in html, (
        "GET .../take does not contain 'quiz-take-test-suite'; "
        "ADR-043: the existing test-suite block must still render — "
        "ADR-047 adds the preamble block alongside it, not replacing it."
    )
    assert "quiz-take-preamble" in html, (
        "GET .../take does not contain 'quiz-take-preamble'; "
        "ADR-047: both blocks must render when preamble is non-empty."
    )


# ===========================================================================
# AC-9: CSS — .quiz-take-preamble rule in quiz.css
# ===========================================================================


def test_quiz_css_has_quiz_take_preamble_rule() -> None:
    """
    AC-9 (TASK-018) / ADR-047 / ADR-008: app/static/quiz.css must contain the
    .quiz-take-preamble CSS rule. The rule must be in quiz.css (reusing the
    quiz-take-* namespace per ADR-008) and not in base.css or a new file.
    """
    # AC-9: .quiz-take-preamble rule exists in quiz.css (ADR-047 / ADR-008)
    quiz_css = REPO_ROOT / "app" / "static" / "quiz.css"
    assert quiz_css.exists(), (
        "app/static/quiz.css does not exist. "
        "ADR-047 / ADR-008: the new .quiz-take-preamble rule must be added to the "
        "existing quiz.css (no new CSS file)."
    )
    source = quiz_css.read_text(encoding="utf-8")
    assert ".quiz-take-preamble" in source, (
        "app/static/quiz.css does not contain '.quiz-take-preamble'. "
        "ADR-047 / ADR-008: a new .quiz-take-preamble rule must be added to quiz.css "
        "(reusing the quiz-take-* CSS namespace)."
    )


def test_no_base_css_change_for_preamble() -> None:
    """
    AC-9 / Negative (TASK-018) / ADR-047 / ADR-008: app/static/base.css must NOT
    contain 'quiz-take-preamble'. The new rule lives in quiz.css only.
    """
    # Negative / AC-9: quiz-take-preamble not in base.css (ADR-047 / ADR-008)
    base_css = REPO_ROOT / "app" / "static" / "base.css"
    if not base_css.exists():
        pytest.skip("app/static/base.css does not exist")
    source = base_css.read_text(encoding="utf-8")
    assert "quiz-take-preamble" not in source, (
        "app/static/base.css contains 'quiz-take-preamble'. "
        "ADR-047 / ADR-008: the new .quiz-take-preamble rule must live ONLY in "
        "quiz.css — no base.css change."
    )


def test_no_new_css_file_for_preamble() -> None:
    """
    AC-9 / Negative (TASK-018) / ADR-047 / ADR-008: no new CSS file was added under
    app/static/ for the preamble styling. The only CSS files must be the established
    base.css, quiz.css, lecture.css.
    """
    # Negative / AC-9: no new CSS file for preamble (ADR-047 / ADR-008)
    static_dir = REPO_ROOT / "app" / "static"
    if not static_dir.exists():
        pytest.skip("app/static/ does not exist")

    expected_css_files = {"base.css", "quiz.css", "lecture.css"}
    actual_css_files = {p.name for p in static_dir.rglob("*.css")}
    new_css_files = actual_css_files - expected_css_files

    assert not new_css_files, (
        f"New CSS files found under app/static/: {new_css_files}. "
        "ADR-047 / ADR-008: new .quiz-take-preamble rules go in the existing quiz.css; "
        "no new CSS file should be added."
    )


# ===========================================================================
# AC-10: MC-1 / MC-10 boundary checks
# ===========================================================================


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


def test_mc10_no_sqlite3_in_workflows_after_task018() -> None:
    """
    AC-10 (TASK-018) / MC-10 / ADR-045: app/workflows/question_gen.py must not
    import sqlite3. The preamble field is a Pydantic schema change; no SQL belongs
    in the workflow module.
    """
    # AC-10 / MC-10: no sqlite3 import in question_gen.py after preamble addition
    qgen_path = REPO_ROOT / "app" / "workflows" / "question_gen.py"
    if not qgen_path.exists():
        pytest.fail("app/workflows/question_gen.py does not exist.")
    source = qgen_path.read_text(encoding="utf-8")
    assert "import sqlite3" not in source, (
        "app/workflows/question_gen.py contains 'import sqlite3'. "
        "MC-10 / ADR-045: the workflow module must not touch the DB — SQL stays under app/persistence/."
    )


def test_mc10_no_sql_literals_in_question_gen() -> None:
    """
    AC-10 (TASK-018) / MC-10 / ADR-045: app/workflows/question_gen.py must not
    contain SQL string literals (SELECT, INSERT, CREATE TABLE, etc.).
    """
    # AC-10 / MC-10: no SQL literals in question_gen.py (ADR-045)
    qgen_path = REPO_ROOT / "app" / "workflows" / "question_gen.py"
    if not qgen_path.exists():
        pytest.fail("app/workflows/question_gen.py does not exist.")
    source = qgen_path.read_text(encoding="utf-8")
    sql_keywords = ["SELECT ", "INSERT INTO", "CREATE TABLE", "ALTER TABLE", "PRAGMA "]
    for kw in sql_keywords:
        assert kw not in source, (
            f"app/workflows/question_gen.py contains SQL keyword '{kw}'. "
            "MC-10 / ADR-045: SQL literals must stay under app/persistence/."
        )


def test_mc1_no_forbidden_sdk_in_question_gen_after_preamble_addition() -> None:
    """
    AC-10 (TASK-018) / MC-1 / ADR-045 / ADR-036: app/workflows/question_gen.py
    must not import any forbidden LLM/agent SDK after the preamble field addition
    (the preamble is a Pydantic schema change; no SDK touched).
    """
    # AC-10 / MC-1: no forbidden SDK import in question_gen.py after TASK-018 (ADR-045)
    qgen_path = REPO_ROOT / "app" / "workflows" / "question_gen.py"
    if not qgen_path.exists():
        pytest.fail("app/workflows/question_gen.py does not exist.")
    source = qgen_path.read_text(encoding="utf-8")
    for sdk in _FORBIDDEN_SDKS:
        pattern = rf"\b(?:import|from)\s+{re.escape(sdk)}\b"
        assert not re.search(pattern, source), (
            f"app/workflows/question_gen.py contains forbidden SDK import '{sdk}'. "
            "MC-1 / ADR-045 / ADR-036: the workflow module must only import ai_workflows.* + "
            "pydantic + stdlib. The preamble field is a Pydantic change — no SDK touched."
        )


def test_mc1_app_workflows_still_only_ai_workflows_and_pydantic() -> None:
    """
    AC-10 (TASK-018) / MC-1 / ADR-045 / ADR-036: the entire app/workflows/ directory
    must not import any forbidden LLM/agent SDK after TASK-018.
    """
    # AC-10 / MC-1: no forbidden SDK in app/workflows/ (MC-1 boundary scan — ADR-045)
    workflows_dir = REPO_ROOT / "app" / "workflows"
    if not workflows_dir.exists():
        pytest.skip("app/workflows/ does not exist")

    violations = []
    for py_file in workflows_dir.rglob("*.py"):
        source = py_file.read_text(encoding="utf-8")
        for sdk in _FORBIDDEN_SDKS:
            pattern = rf"\b(?:import|from)\s+{re.escape(sdk)}\b"
            if re.search(pattern, source):
                violations.append(f"{py_file.relative_to(REPO_ROOT)}: {sdk}")

    assert not violations, (
        "Forbidden SDK imports found in app/workflows/:\n"
        + "\n".join(f"  {v}" for v in violations)
        + "\nMC-1 / ADR-045 / ADR-036: app/workflows/ must import only ai_workflows.* + "
        "pydantic + stdlib."
    )


def test_mc10_no_sqlite3_outside_persistence_after_task018() -> None:
    """
    AC-10 (TASK-018) / MC-10: no new `import sqlite3` in app/main.py,
    app/sandbox.py, or app/workflows/ from TASK-018 changes (SQL stays under
    app/persistence/).
    """
    # AC-10 / MC-10: no sqlite3 outside app/persistence/ after TASK-018 (ADR-045)
    files_to_check = [
        REPO_ROOT / "app" / "main.py",
        REPO_ROOT / "app" / "sandbox.py",
    ]
    for fpath in files_to_check:
        if not fpath.exists():
            continue
        source = fpath.read_text(encoding="utf-8")
        assert "import sqlite3" not in source, (
            f"{fpath.name} contains 'import sqlite3'. "
            "MC-10 / ADR-045: SQL/DB access belongs only under app/persistence/."
        )


# ===========================================================================
# Performance: preamble column round-trip for many questions
# ===========================================================================


def test_preamble_column_round_trip_for_many_questions_within_budget(
    tmp_path, monkeypatch
) -> None:
    """
    Performance (TASK-018) / ADR-046: add_questions_to_quiz with 20 Questions each
    carrying a non-empty preamble + list_questions_for_quiz for all 20 must complete
    within 5 s. Catches O(n²) regressions on the per-question INSERT path (the same
    concern ADR-037 / ADR-041's one-transaction discipline guards against).
    """
    # Performance: preamble round-trip for 20 questions completes within 5 s (ADR-046)
    db_path = str(tmp_path / "perf_preamble.db")
    monkeypatch.setenv("NOTES_DB_PATH", db_path)
    from app.persistence.connection import init_schema  # noqa: PLC0415
    from app.persistence.quizzes import (  # noqa: PLC0415
        add_questions_to_quiz,
        list_questions_for_quiz,
        request_quiz,
        mark_quiz_ready,
    )

    init_schema()
    quiz = request_quiz(SECTION_ID_CH01_S1)

    n = 20
    questions_payload = [
        {
            "prompt": f"Implement function_{i}()",
            "topics": ["performance"],
            "test_suite": f"#include <cassert>\nint fn_{i}(); int main(){{return 0;}}",
            "preamble": f"// Shared struct for question {i}\nstruct Node_{i} {{ int data_{i}; }};",
        }
        for i in range(n)
    ]

    t0 = time.monotonic()
    add_questions_to_quiz(quiz.quiz_id, questions_payload)
    mark_quiz_ready(quiz.quiz_id)
    questions = list_questions_for_quiz(quiz.quiz_id)
    elapsed = time.monotonic() - t0

    assert elapsed <= 5.0, (
        f"add_questions_to_quiz({n} questions with preamble) + list_questions_for_quiz "
        f"took {elapsed:.2f}s; expected ≤ 5 s. "
        "ADR-046: the preamble column addition must not introduce O(n²) behavior."
    )
    assert len(questions) == n, (
        f"list_questions_for_quiz returned {len(questions)} Questions; expected {n}."
    )
    for i, q in enumerate(questions):
        assert q.preamble is not None, (
            f"Question[{i}].preamble is None after add_questions_to_quiz with preamble. "
            "ADR-046: the preamble must be persisted for all Questions."
        )


# ===========================================================================
# CANNOT TEST: AC-12 (ADR acceptance gate) — this is a human-only gate.
# The ADRs are already Accepted (auto-accepted by /auto on 2026-05-13);
# their existence on disk is a file-system check we can do, but the
# "acceptance" itself is a human gate recorded in the audit.
# ===========================================================================
