"""
TASK-019: Quiz-grading slice — tests for AC-2 (the `grade_attempt` workflow module)
and conformance checks (AC-6 MC-1 / MC-7 / MC-10 boundary).

Tests derive from:
  ADR-048 — The `grade_attempt` `ai-workflows` workflow:
    - WorkflowSpec at app/workflows/grade_attempt.py
    - One LLMStep with prompt_fn, response_format=GradeAttemptOutput
    - RetryPolicy(max_attempts=3, exponential)
    - GradeAttemptInput / QuestionForGrading / QuestionGrade / GradeAttemptOutput schemas
    - model_config = ConfigDict(extra="forbid") on every model
    - min_length=1 on QuestionGrade.explanation
    - score: int = Field(ge=0) on GradeAttemptOutput
    - No is_correct field on QuestionGrade
    - MC-1: imports only ai_workflows.* + pydantic + stdlib

Coverage matrix:
  Boundary:
    - test_grade_attempt_output_valid_empty_lists: weak_topics=[], recommended_sections=[]
        valid for a perfect Attempt (boundary: empty lists).
    - test_grade_attempt_output_score_zero_valid: score=0 is valid (ge=0 boundary, at zero).
    - test_grade_attempt_output_score_positive_valid: score=3 persists correctly.
    - test_question_grade_explanation_min_length_one: explanation="" raises (min_length=1).
    - test_question_grade_explanation_single_char_valid: explanation="x" (length 1) is valid.
    - test_question_for_grading_test_passed_none_valid: test_passed=None is valid (not-run case).
    - test_question_for_grading_test_passed_bool_valid: test_passed=True / False round-trip.
    - test_workflow_spec_is_registered: workflow named "grade_attempt" is importable and registerable.
  Edge:
    - test_grade_attempt_input_extra_field_forbidden: GradeAttemptInput with extra field raises.
    - test_question_for_grading_extra_field_forbidden: QuestionForGrading with extra field raises.
    - test_question_grade_extra_field_forbidden: QuestionGrade with extra field raises.
    - test_grade_attempt_output_extra_field_forbidden: GradeAttemptOutput with extra field raises.
    - test_grade_attempt_output_no_is_correct_field: QuestionGrade has NO is_correct field
        (the schema makes LLM correctness override impossible — ADR-048 core commitment).
    - test_question_for_grading_unicode_response_round_trips: Unicode in response survives.
    - test_grade_attempt_output_many_questions: a list of 5 QuestionGrade items is valid.
    - test_grade_attempt_output_per_question_empty_list_valid: per_question=[] is valid schema.
  Negative:
    - test_grade_attempt_output_score_negative_raises: score=-1 raises (ge=0).
    - test_grade_attempt_output_missing_per_question_raises: missing required field raises.
    - test_grade_attempt_input_missing_questions_raises: missing required field raises.
    - test_question_grade_missing_question_id_raises: missing question_id raises.
    - test_mc1_no_forbidden_lm_sdk_import_in_grade_attempt_workflow: grep check — MC-1.
    - test_mc1_no_forbidden_sdk_in_process_quiz_attempts: grep check — MC-1 on processor.
    - test_mc7_no_user_id_in_workflow_schemas: no user_id field anywhere in schemas.
    - test_mc10_no_sqlite3_in_grade_attempt_workflow: no sqlite3 import in workflow — MC-10.
    - test_mc10_no_sqlite3_in_process_quiz_attempts: no sqlite3 import in processor — MC-10.
    - test_mc10_no_sql_literals_in_grade_attempt_workflow: no SQL string in workflow — MC-10.
    - test_mc10_no_sql_literals_in_process_quiz_attempts: no SQL string in processor — MC-10.
  Performance:
    - skipped: the workflow module is a schema/declaration-only file; no scaling surface
      in the schema definitions. The processor's performance is covered in
      test_task019_grading_processor.py which exercises transactional save across N questions.

pytestmark registers all tests under task("TASK-019").

ASSUMPTIONS:
  ASSUMPTION: app.workflows.grade_attempt exports (or makes importable):
    GradeAttemptInput, QuestionForGrading, QuestionGrade, GradeAttemptOutput —
    Pydantic models with ConfigDict(extra="forbid"); if not exported or the
    module does not exist, ImportError is the expected failing signal.

  ASSUMPTION: The WorkflowSpec is registered at module-level via register_workflow
    and the workflow name is "grade_attempt". The module is at app/workflows/grade_attempt.py.

  ASSUMPTION: The forbidden-SDK list from ADR-036 / MC-1:
    openai, anthropic, google.generativeai, google.genai, cohere, mistralai,
    groq, together, replicate, litellm, langchain, langgraph.
"""

from __future__ import annotations

import pathlib
import re

import pytest

pytestmark = pytest.mark.task("TASK-019")

REPO_ROOT = pathlib.Path(__file__).parent.parent
WORKFLOW_MODULE_PATH = REPO_ROOT / "app" / "workflows" / "grade_attempt.py"
PROCESSOR_MODULE_PATH = REPO_ROOT / "app" / "workflows" / "process_quiz_attempts.py"

# Forbidden SDK names per ADR-036 / MC-1
FORBIDDEN_SDK_NAMES = [
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


# ---------------------------------------------------------------------------
# Helpers — deferred imports so collection succeeds before implementation
# ---------------------------------------------------------------------------


def _import_workflow_schemas():
    """Import schema classes from app.workflows.grade_attempt."""
    import app.workflows.grade_attempt as mod  # noqa: PLC0415
    return (
        mod.GradeAttemptInput,
        mod.QuestionForGrading,
        mod.QuestionGrade,
        mod.GradeAttemptOutput,
    )


def _make_minimal_question_for_grading(question_id: int = 1) -> dict:
    return {
        "question_id": question_id,
        "prompt": "Implement a stack using an array.",
        "preamble": "",
        "test_suite": "def test_stack():\n    s = Stack()\n    s.push(1)\n    assert s.pop() == 1\n",
        "response": "class Stack:\n    def __init__(self): self.data=[]\n    def push(self,v): self.data.append(v)\n    def pop(self): return self.data.pop()\n",
        "test_passed": True,
        "test_status": "ran",
        "test_output": "passed",
    }


def _make_minimal_grade_attempt_input() -> dict:
    return {
        "section_title": "Arrays and Dynamic Arrays",
        "section_content": "This section covers arrays.",
        "questions": [_make_minimal_question_for_grading(1)],
    }


def _make_minimal_question_grade(question_id: int = 1) -> dict:
    return {
        "question_id": question_id,
        "explanation": "The implementation correctly pushes and pops from the data list.",
    }


def _make_minimal_grade_attempt_output(n_questions: int = 1) -> dict:
    return {
        "per_question": [_make_minimal_question_grade(i + 1) for i in range(n_questions)],
        "score": n_questions,
        "weak_topics": [],
        "recommended_sections": [],
    }


# ===========================================================================
# Boundary: valid schema round-trips
# ===========================================================================


def test_grade_attempt_output_valid_empty_lists() -> None:
    """
    AC-2 / ADR-048: GradeAttemptOutput with empty weak_topics and
    recommended_sections is valid — a perfect Attempt has no Weak Topics.
    Boundary: empty lists are the minimum valid state.
    """
    GradeAttemptInput, QuestionForGrading, QuestionGrade, GradeAttemptOutput = (
        _import_workflow_schemas()
    )
    data = _make_minimal_grade_attempt_output()
    data["weak_topics"] = []
    data["recommended_sections"] = []
    obj = GradeAttemptOutput(**data)
    assert obj.weak_topics == []
    assert obj.recommended_sections == []


def test_grade_attempt_output_score_zero_valid() -> None:
    """
    AC-2 / ADR-048: score=0 is valid (ge=0 boundary, at zero).
    An Attempt where every Question failed → score=0.
    """
    GradeAttemptInput, QuestionForGrading, QuestionGrade, GradeAttemptOutput = (
        _import_workflow_schemas()
    )
    data = _make_minimal_grade_attempt_output()
    data["score"] = 0
    obj = GradeAttemptOutput(**data)
    assert obj.score == 0


def test_grade_attempt_output_score_positive_valid() -> None:
    """
    AC-2 / ADR-048: score=3 round-trips correctly.
    """
    GradeAttemptInput, QuestionForGrading, QuestionGrade, GradeAttemptOutput = (
        _import_workflow_schemas()
    )
    data = _make_minimal_grade_attempt_output(3)
    data["score"] = 3
    obj = GradeAttemptOutput(**data)
    assert obj.score == 3


def test_question_grade_explanation_min_length_one() -> None:
    """
    AC-2 / ADR-048: QuestionGrade with explanation="" raises ValidationError.
    min_length=1 on explanation prevents an empty-string placeholder from
    satisfying the schema (MC-5 — no fabricated grade).
    Boundary: length 0 vs 1.
    """
    from pydantic import ValidationError  # noqa: PLC0415
    GradeAttemptInput, QuestionForGrading, QuestionGrade, GradeAttemptOutput = (
        _import_workflow_schemas()
    )
    with pytest.raises(ValidationError):
        QuestionGrade(question_id=1, explanation="")


def test_question_grade_explanation_single_char_valid() -> None:
    """
    AC-2 / ADR-048: explanation with length=1 is valid (boundary: exactly min_length).
    """
    GradeAttemptInput, QuestionForGrading, QuestionGrade, GradeAttemptOutput = (
        _import_workflow_schemas()
    )
    obj = QuestionGrade(question_id=1, explanation="x")
    assert obj.explanation == "x"


def test_question_for_grading_test_passed_none_valid() -> None:
    """
    AC-2 / ADR-048: test_passed=None is valid in QuestionForGrading.
    Represents a Question the learner submitted without running the tests
    (test_status='not_run'). Boundary: None is a valid value.
    """
    GradeAttemptInput, QuestionForGrading, QuestionGrade, GradeAttemptOutput = (
        _import_workflow_schemas()
    )
    data = _make_minimal_question_for_grading()
    data["test_passed"] = None
    data["test_status"] = "not_run"
    data["test_output"] = ""
    obj = QuestionForGrading(**data)
    assert obj.test_passed is None


def test_question_for_grading_test_passed_bool_valid() -> None:
    """
    AC-2 / ADR-048: test_passed=True and test_passed=False both round-trip.
    """
    GradeAttemptInput, QuestionForGrading, QuestionGrade, GradeAttemptOutput = (
        _import_workflow_schemas()
    )
    true_data = _make_minimal_question_for_grading()
    true_data["test_passed"] = True
    obj_true = QuestionForGrading(**true_data)
    assert obj_true.test_passed is True

    false_data = _make_minimal_question_for_grading()
    false_data["test_passed"] = False
    false_data["test_status"] = "ran"
    obj_false = QuestionForGrading(**false_data)
    assert obj_false.test_passed is False


def test_workflow_spec_is_registered() -> None:
    """
    AC-2 / ADR-048: the grade_attempt workflow module can be imported and
    defines a WorkflowSpec (or registers a workflow named 'grade_attempt').
    The module must define a GradeAttemptOutput as the response_format.
    """
    import app.workflows.grade_attempt as mod  # noqa: PLC0415
    # The module must be importable (i.e. no syntax errors, no forbidden imports)
    assert mod is not None
    # There must be a GradeAttemptOutput class
    assert hasattr(mod, "GradeAttemptOutput"), (
        "app.workflows.grade_attempt must export GradeAttemptOutput "
        "(ADR-048 §The Pydantic schemas)"
    )
    # There must be a WorkflowSpec or _spec registered at module level
    # The module should have the workflow name reflected somewhere
    module_src = WORKFLOW_MODULE_PATH.read_text()
    assert "grade_attempt" in module_src, (
        "The workflow module must register a workflow named 'grade_attempt' "
        "(ADR-048 §Registration)"
    )


# ===========================================================================
# Edge: extra fields forbidden, unicode, multi-question
# ===========================================================================


def test_grade_attempt_input_extra_field_forbidden() -> None:
    """
    AC-2 / ADR-048: GradeAttemptInput with an extra field raises ValidationError.
    ConfigDict(extra='forbid') on every model — no non-coding / chat / tutor field
    can sneak in (manifest §5 / §7).
    """
    from pydantic import ValidationError  # noqa: PLC0415
    GradeAttemptInput, QuestionForGrading, QuestionGrade, GradeAttemptOutput = (
        _import_workflow_schemas()
    )
    data = _make_minimal_grade_attempt_input()
    data["extra_chat_field"] = "hello"
    with pytest.raises(ValidationError):
        GradeAttemptInput(**data)


def test_question_for_grading_extra_field_forbidden() -> None:
    """
    AC-2 / ADR-048: QuestionForGrading with an extra field raises ValidationError.
    """
    from pydantic import ValidationError  # noqa: PLC0415
    GradeAttemptInput, QuestionForGrading, QuestionGrade, GradeAttemptOutput = (
        _import_workflow_schemas()
    )
    data = _make_minimal_question_for_grading()
    data["correct_choice"] = "A"
    with pytest.raises(ValidationError):
        QuestionForGrading(**data)


def test_question_grade_extra_field_forbidden() -> None:
    """
    AC-2 / ADR-048: QuestionGrade with an extra field raises ValidationError.
    Specifically ensures 'is_correct' cannot be added (the schema commits to
    not re-judging correctness — ADR-048 core commitment).
    """
    from pydantic import ValidationError  # noqa: PLC0415
    GradeAttemptInput, QuestionForGrading, QuestionGrade, GradeAttemptOutput = (
        _import_workflow_schemas()
    )
    with pytest.raises(ValidationError):
        QuestionGrade(question_id=1, explanation="Good work.", is_correct=True)


def test_grade_attempt_output_extra_field_forbidden() -> None:
    """
    AC-2 / ADR-048: GradeAttemptOutput with an extra field raises ValidationError.
    """
    from pydantic import ValidationError  # noqa: PLC0415
    GradeAttemptInput, QuestionForGrading, QuestionGrade, GradeAttemptOutput = (
        _import_workflow_schemas()
    )
    data = _make_minimal_grade_attempt_output()
    data["chat_turn"] = "What do you think?"
    with pytest.raises(ValidationError):
        GradeAttemptOutput(**data)


def test_grade_attempt_output_no_is_correct_field() -> None:
    """
    AC-2 / ADR-048 CORE: QuestionGrade has NO is_correct field.

    This is the architecturally load-bearing commitment: the LLM cannot
    disagree with the runner's correctness verdict because the schema
    provides no field through which to disagree. The persistence layer
    (ADR-050) derives is_correct from test_passed, not from the workflow.

    This test ensures the schema does not define an is_correct field
    (even as Optional or with a default).
    """
    GradeAttemptInput, QuestionForGrading, QuestionGrade, GradeAttemptOutput = (
        _import_workflow_schemas()
    )
    obj = QuestionGrade(question_id=1, explanation="The code correctly implements the target.")
    assert not hasattr(obj, "is_correct"), (
        "QuestionGrade must NOT have an is_correct field. "
        "ADR-048: the LLM cannot re-judge correctness; the schema makes "
        "that disagreement unexpressible. The persistence layer (ADR-050) "
        "derives is_correct from attempt_questions.test_passed."
    )
    # Also check the model_fields / schema
    assert "is_correct" not in QuestionGrade.model_fields, (
        "QuestionGrade.model_fields must not contain 'is_correct' "
        "(ADR-048 §is_correct is the runner's verdict, not the LLM's)"
    )


def test_question_for_grading_unicode_response_round_trips() -> None:
    """
    AC-2 / ADR-048: QuestionForGrading with Unicode content in response
    survives Pydantic validation unchanged. LaTeX-derived content and
    learner responses can contain Unicode characters.
    Edge: Unicode input.
    """
    GradeAttemptInput, QuestionForGrading, QuestionGrade, GradeAttemptOutput = (
        _import_workflow_schemas()
    )
    data = _make_minimal_question_for_grading()
    data["response"] = "// Solution using O(n) space\ndef solve(): return '你好'\n"
    obj = QuestionForGrading(**data)
    assert "你好" in obj.response


def test_grade_attempt_output_many_questions() -> None:
    """
    AC-2 / ADR-048: GradeAttemptOutput with 5 QuestionGrade items is valid.
    Edge: a Quiz with multiple Questions.
    """
    GradeAttemptInput, QuestionForGrading, QuestionGrade, GradeAttemptOutput = (
        _import_workflow_schemas()
    )
    data = _make_minimal_grade_attempt_output(5)
    data["score"] = 5
    data["weak_topics"] = []
    obj = GradeAttemptOutput(**data)
    assert len(obj.per_question) == 5


def test_grade_attempt_output_per_question_empty_list_valid() -> None:
    """
    AC-2 / ADR-048: per_question=[] is valid at the schema level.
    The processor validates the question_id match separately (ADR-049).
    Edge: empty per_question list in schema.
    """
    GradeAttemptInput, QuestionForGrading, QuestionGrade, GradeAttemptOutput = (
        _import_workflow_schemas()
    )
    obj = GradeAttemptOutput(per_question=[], score=0, weak_topics=[], recommended_sections=[])
    assert obj.per_question == []
    assert obj.score == 0


# ===========================================================================
# Negative: invalid inputs raise, forbidden fields/patterns absent
# ===========================================================================


def test_grade_attempt_output_score_negative_raises() -> None:
    """
    AC-2 / ADR-048: score=-1 raises ValidationError.
    Field(ge=0) enforces non-negative score — a negative score is nonsensical
    (the count of Questions whose test_passed=True cannot be negative).
    Negative: out-of-bounds score.
    """
    from pydantic import ValidationError  # noqa: PLC0415
    GradeAttemptInput, QuestionForGrading, QuestionGrade, GradeAttemptOutput = (
        _import_workflow_schemas()
    )
    data = _make_minimal_grade_attempt_output()
    data["score"] = -1
    with pytest.raises(ValidationError):
        GradeAttemptOutput(**data)


def test_grade_attempt_output_missing_per_question_raises() -> None:
    """
    AC-2 / ADR-048: GradeAttemptOutput missing the required 'per_question' field raises.
    Negative: missing required field.
    """
    from pydantic import ValidationError  # noqa: PLC0415
    GradeAttemptInput, QuestionForGrading, QuestionGrade, GradeAttemptOutput = (
        _import_workflow_schemas()
    )
    with pytest.raises(ValidationError):
        GradeAttemptOutput(score=0, weak_topics=[], recommended_sections=[])


def test_grade_attempt_input_missing_questions_raises() -> None:
    """
    AC-2 / ADR-048: GradeAttemptInput missing the required 'questions' field raises.
    Negative: missing required field.
    """
    from pydantic import ValidationError  # noqa: PLC0415
    GradeAttemptInput, QuestionForGrading, QuestionGrade, GradeAttemptOutput = (
        _import_workflow_schemas()
    )
    with pytest.raises(ValidationError):
        GradeAttemptInput(section_title="Arrays", section_content="Content here.")


def test_question_grade_missing_question_id_raises() -> None:
    """
    AC-2 / ADR-048: QuestionGrade missing question_id raises ValidationError.
    Negative: missing required field; question_id is needed for matching.
    """
    from pydantic import ValidationError  # noqa: PLC0415
    GradeAttemptInput, QuestionForGrading, QuestionGrade, GradeAttemptOutput = (
        _import_workflow_schemas()
    )
    with pytest.raises(ValidationError):
        QuestionGrade(explanation="Good implementation.")


def test_mc1_no_forbidden_lm_sdk_import_in_grade_attempt_workflow() -> None:
    """
    AC-6 / MC-1 / ADR-048: app/workflows/grade_attempt.py must not import
    any forbidden LLM/agent SDK. The boundary grep enforces this.

    Forbidden names: openai, anthropic, google.generativeai, google.genai,
    cohere, mistralai, groq, together, replicate, litellm, langchain, langgraph.

    The module may import ai_workflows.*, pydantic, and stdlib only.
    """
    assert WORKFLOW_MODULE_PATH.exists(), (
        f"app/workflows/grade_attempt.py does not exist at {WORKFLOW_MODULE_PATH}. "
        "It must be created by the implementer."
    )
    source = WORKFLOW_MODULE_PATH.read_text()
    for sdk in FORBIDDEN_SDK_NAMES:
        # Match `import sdk`, `from sdk`, `import sdk.something`
        pattern = rf"(?:^|\n)\s*(?:import|from)\s+{re.escape(sdk)}"
        assert not re.search(pattern, source), (
            f"FORBIDDEN SDK IMPORT: app/workflows/grade_attempt.py imports '{sdk}'. "
            f"MC-1 (ADR-036): app/workflows/ must import only ai_workflows.* + pydantic + stdlib."
        )


def test_mc1_no_forbidden_sdk_in_process_quiz_attempts() -> None:
    """
    AC-6 / MC-1 / ADR-049: app/workflows/process_quiz_attempts.py must not
    import any forbidden LLM/agent SDK. The processor imports stdlib + app.* only.
    """
    assert PROCESSOR_MODULE_PATH.exists(), (
        f"app/workflows/process_quiz_attempts.py does not exist at {PROCESSOR_MODULE_PATH}. "
        "It must be created by the implementer."
    )
    source = PROCESSOR_MODULE_PATH.read_text()
    for sdk in FORBIDDEN_SDK_NAMES:
        pattern = rf"(?:^|\n)\s*(?:import|from)\s+{re.escape(sdk)}"
        assert not re.search(pattern, source), (
            f"FORBIDDEN SDK IMPORT in process_quiz_attempts.py: '{sdk}'. MC-1."
        )


def test_mc7_no_user_id_in_workflow_schemas() -> None:
    """
    AC-6 / MC-7: no user_id field on any schema in app/workflows/grade_attempt.py.
    Single-user project; no user identity in the Grade pipeline.
    """
    assert WORKFLOW_MODULE_PATH.exists(), (
        f"app/workflows/grade_attempt.py not found at {WORKFLOW_MODULE_PATH}"
    )
    source = WORKFLOW_MODULE_PATH.read_text()
    # Search for user_id field definitions in Pydantic models
    assert "user_id" not in source, (
        "app/workflows/grade_attempt.py must NOT define a user_id field. "
        "MC-7: single-user; no user identity in any schema (ADR-048)."
    )


def test_mc10_no_sqlite3_in_grade_attempt_workflow() -> None:
    """
    AC-6 / MC-10: app/workflows/grade_attempt.py must not import sqlite3.
    SQL stays under app/persistence/ (ADR-022 / ADR-048).
    """
    assert WORKFLOW_MODULE_PATH.exists(), (
        f"app/workflows/grade_attempt.py not found at {WORKFLOW_MODULE_PATH}"
    )
    source = WORKFLOW_MODULE_PATH.read_text()
    assert "import sqlite3" not in source, (
        "app/workflows/grade_attempt.py must NOT import sqlite3. "
        "MC-10 (ADR-022): import sqlite3 stays under app/persistence/ only."
    )


def test_mc10_no_sqlite3_in_process_quiz_attempts() -> None:
    """
    AC-6 / MC-10: app/workflows/process_quiz_attempts.py must not import sqlite3.
    The processor calls typed public functions from app/persistence/__init__.py;
    it never imports sqlite3 directly (ADR-049 / ADR-022 / MC-10).
    """
    assert PROCESSOR_MODULE_PATH.exists(), (
        f"app/workflows/process_quiz_attempts.py not found at {PROCESSOR_MODULE_PATH}"
    )
    source = PROCESSOR_MODULE_PATH.read_text()
    assert "import sqlite3" not in source, (
        "app/workflows/process_quiz_attempts.py must NOT import sqlite3. "
        "MC-10: SQL stays under app/persistence/ only (ADR-049 / ADR-022)."
    )


def test_mc10_no_sql_literals_in_grade_attempt_workflow() -> None:
    """
    AC-6 / MC-10: app/workflows/grade_attempt.py must not contain SQL string literals.
    The workflow has no persistence responsibility; it only produces GradeAttemptOutput.
    """
    assert WORKFLOW_MODULE_PATH.exists(), (
        f"app/workflows/grade_attempt.py not found at {WORKFLOW_MODULE_PATH}"
    )
    source = WORKFLOW_MODULE_PATH.read_text()
    # Detect SQL literals by looking for common SQL keywords in string literals
    sql_pattern = r'["\'](?:SELECT|INSERT|UPDATE|DELETE|CREATE|ALTER|DROP|PRAGMA)\b'
    matches = re.findall(sql_pattern, source, re.IGNORECASE)
    assert not matches, (
        f"app/workflows/grade_attempt.py contains SQL string literals: {matches}. "
        "MC-10: SQL literals stay under app/persistence/ only."
    )


def test_mc10_no_sql_literals_in_process_quiz_attempts() -> None:
    """
    AC-6 / MC-10: app/workflows/process_quiz_attempts.py must not contain
    SQL string literals. The processor calls typed persistence functions.
    """
    assert PROCESSOR_MODULE_PATH.exists(), (
        f"app/workflows/process_quiz_attempts.py not found at {PROCESSOR_MODULE_PATH}"
    )
    source = PROCESSOR_MODULE_PATH.read_text()
    sql_pattern = r'["\'](?:SELECT|INSERT|UPDATE|DELETE|CREATE|ALTER|DROP|PRAGMA)\b'
    matches = re.findall(sql_pattern, source, re.IGNORECASE)
    assert not matches, (
        f"app/workflows/process_quiz_attempts.py contains SQL string literals: {matches}. "
        "MC-10: SQL literals stay under app/persistence/ only."
    )
