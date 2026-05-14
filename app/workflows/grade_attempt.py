"""
app/workflows/grade_attempt — CS-300-owned quiz-grading WorkflowSpec.

ADR-048 §Where the CS-300 workflow module lives:
  This module defines and registers the `grade_attempt` ai-workflows workflow.
  It is loaded via AIW_EXTRA_WORKFLOW_MODULES=...,app.workflows.grade_attempt when
  the `aiw` CLI subprocess is invoked by the out-of-band grading processor
  (app/workflows/process_quiz_attempts.py).

The workflow:
  - Input:  GradeAttemptInput (section_title, section_content,
                                questions: list[QuestionForGrading])
  - Output: GradeAttemptOutput (per_question: list[QuestionGrade],
                                 score: int, weak_topics: list[str],
                                 recommended_sections: list[str])
  - One LLMStep with prompt_fn (not prompt_template — LaTeX content may
    contain { } characters; ADR-048).
  - response_format=GradeAttemptOutput.
  - RetryPolicy(max_attempts=3, exponential backoff — ADR-048).
  - Tier: gemini/gemini-2.5-flash via LiteLLMRoute (ADR-048 default).

Schema constraints (ADR-048 / manifest §5 / §7):
  - NO is_correct field on QuestionGrade — the LLM cannot re-judge runner
    correctness.  The persistence layer (ADR-050) derives is_correct from
    attempt_questions.test_passed, never from the workflow's output.
  - ConfigDict(extra='forbid') on every model.
  - min_length=1 on QuestionGrade.explanation (empty explanations are
    inexpressible — MC-5).
  - score: int = Field(ge=0) on GradeAttemptOutput.

MC-1: only ai_workflows.* + pydantic + stdlib imported (no openai / anthropic /
      google.generativeai / litellm / langchain / langgraph etc.).
MC-7: single-user project; no identity field on any schema.
MC-10: no DB driver imports; no SQL literals; no DB access.
"""

from __future__ import annotations

import os

from pydantic import BaseModel, ConfigDict, Field

from ai_workflows.primitives.tiers import LiteLLMRoute, TierConfig
from ai_workflows.workflows import LLMStep, RetryPolicy, WorkflowSpec, register_workflow


# ---------------------------------------------------------------------------
# Pydantic schemas — input and output
# ---------------------------------------------------------------------------


class QuestionForGrading(BaseModel):
    """
    A single Question's data supplied to the grading LLM.

    ADR-048 §The Pydantic schemas:
      question_id  int      — identifies the Question for matching in the output
      prompt       str      — the coding-task prompt (so the LLM has context)
      preamble     str      — shared struct/class/header shapes (may be empty)
      test_suite   str      — the assertion-only test source code
      response     str      — the learner's submitted code
      test_passed  bool | None — runner verdict (True/False) or None (not run)
      test_status  str      — 'ran' | 'timed_out' | 'compile_error' | 'setup_error'
                              | 'not_run'
      test_output  str      — combined output / diagnostic (may be empty)

    ConfigDict(extra='forbid'): no non-coding / chat / tutor field can sneak in.
    MC-7: single-user; no identity field on any schema.
    No is_correct field (the LLM sees test_passed from the runner — it cannot
    invent a different verdict).
    """
    model_config = ConfigDict(extra="forbid")

    question_id: int
    prompt: str
    preamble: str
    test_suite: str
    response: str
    test_passed: bool | None
    test_status: str
    test_output: str


class GradeAttemptInput(BaseModel):
    """
    Input to the grade_attempt workflow.

    ADR-048 §The Pydantic schemas:
      section_title   str                        — Section title for context
      section_content str                        — Section body for context
      questions       list[QuestionForGrading]   — Questions with runner results

    ConfigDict(extra='forbid'). MC-7: single-user; no identity field.
    """
    model_config = ConfigDict(extra="forbid")

    section_title: str
    section_content: str
    questions: list[QuestionForGrading]


class QuestionGrade(BaseModel):
    """
    The LLM's per-Question grade output.

    ADR-048 §The Pydantic schemas (CORE COMMITMENT):
      question_id  int — identifies which Question this grade is for
      explanation  str — the LLM's explanation of the learner's work;
                         min_length=1 so an empty-string placeholder is
                         inexpressible (MC-5 — no fabricated grade detail).

    NO is_correct field: the schema commits to NOT re-judging the runner's
    correctness verdict. The persistence layer (ADR-050) always derives
    is_correct from attempt_questions.test_passed, not from the LLM.
    ConfigDict(extra='forbid') prevents any field from being added at runtime.
    """
    model_config = ConfigDict(extra="forbid")

    question_id: int
    explanation: str = Field(min_length=1)


class GradeAttemptOutput(BaseModel):
    """
    Output (terminal artefact) of the grade_attempt workflow.

    ADR-048 §The Pydantic schemas:
      per_question          list[QuestionGrade]  — one entry per Question
      score                 int                  — the LLM's claimed score
                                                   (ge=0; the processor cross-
                                                   checks and recomputes from
                                                   SUM(is_correct) — ADR-049)
      weak_topics           list[str]            — Topic tags the learner
                                                   struggled with
      recommended_sections  list[str]            — Section IDs recommended for
                                                   review

    ConfigDict(extra='forbid'). MC-7: single-user; no identity field.
    """
    model_config = ConfigDict(extra="forbid")

    per_question: list[QuestionGrade]
    score: int = Field(ge=0)
    weak_topics: list[str]
    recommended_sections: list[str]


# ---------------------------------------------------------------------------
# Tier registry
# ---------------------------------------------------------------------------


def _resolve_model() -> str:
    """
    Resolve the LLM model string for grade attempt at call time.

    Precedence (highest to lowest):
      1. GRADE_ATTEMPT_MODEL env var — full litellm model string, used verbatim.
      2. OLLAMA_MODEL_GRADE_ATTEMPT env var — Ollama model name; "ollama/" prefix
         is prepended if the value does not already start with it.
      3. Default: "gemini/gemini-2.5-flash".

    Reads os.environ at call time so monkeypatched env vars take effect in tests
    without a module reload.

    ADR-048 §Tier registry: "the specific provider/model is a tuning decision
    inside the tier registry, not an architectural commitment."
    """
    if gam := os.environ.get("GRADE_ATTEMPT_MODEL"):
        return gam
    if ollama := os.environ.get("OLLAMA_MODEL_GRADE_ATTEMPT"):
        return ollama if ollama.startswith("ollama/") else f"ollama/{ollama}"
    return "gemini/gemini-2.5-flash"


def grade_attempt_tier_registry() -> dict[str, TierConfig]:
    """
    Tier registry for the grade_attempt workflow.

    ADR-048 §Tier registry: one LLM tier — resolved via _resolve_model()
    (default: gemini/gemini-2.5-flash via LiteLLMRoute; needs GEMINI_API_KEY
    at runtime). The specific provider/model is a tuning decision, not an
    architectural commitment.
    """
    model = _resolve_model()
    return {
        "grade-attempt-llm": TierConfig(
            name="grade-attempt-llm",
            route=LiteLLMRoute(model=model),
        )
    }


# ---------------------------------------------------------------------------
# Prompt function
# ---------------------------------------------------------------------------


def _grade_attempt_prompt_fn(state: dict) -> tuple[str | None, list[dict]]:
    """
    Build the system + user prompt for the grade_attempt LLMStep.

    ADR-048: uses prompt_fn (not prompt_template) because the Section content is
    LaTeX and may contain { } characters which would collide with str.format
    placeholders.

    The prompt instructs the LLM to:
    - Provide per-question explanations (not correctness verdicts — the runner
      already determined pass/fail; the LLM's role is explanation only).
    - Identify weak topics from the learner's answers.
    - Recommend sections for review.
    - Report a score (the processor cross-checks this independently).
    """
    section_title: str = state.get("section_title", "")
    section_content: str = state.get("section_content", "")
    questions: list[dict] = state.get("questions", [])

    questions_text = ""
    for i, q in enumerate(questions, start=1):
        test_passed = q.get("test_passed")
        test_status = q.get("test_status", "")
        test_output = q.get("test_output", "")
        verdict = "PASSED" if test_passed else ("NOT RUN" if test_passed is None else "FAILED")

        questions_text += (
            f"\n--- Question {i} (ID: {q.get('question_id')}) ---\n"
            f"Prompt: {q.get('prompt', '')}\n"
            f"Test Suite:\n{q.get('test_suite', '')}\n"
            f"Learner Response:\n{q.get('response', '')}\n"
            f"Test Result: {verdict} (status={test_status})\n"
            f"Test Output: {test_output}\n"
        )
        if q.get("preamble"):
            questions_text += f"Shared Code (Preamble):\n{q['preamble']}\n"

    system_prompt = (
        "You are an expert computer science educator grading hands-on coding "
        "quiz submissions for a data structures and algorithms course.\n\n"
        "STRICT REQUIREMENTS:\n"
        "1. For each Question, provide a clear, educational EXPLANATION of the "
        "learner's work. The explanation should describe what the learner did "
        "well or poorly, and what the correct approach is. Minimum 1 character — "
        "never leave an explanation empty.\n"
        "2. Do NOT re-judge whether a test passed or failed — the automated test "
        "runner already determined pass/fail. Your explanation provides educational "
        "context, not a new correctness verdict.\n"
        "3. Identify 'weak_topics': a list of topic tags the learner appeared to "
        "struggle with based on their responses. Use the same topic format as "
        "the Question topics (e.g. 'stacks', 'linked lists', 'recursion'). "
        "Return an empty list if no topics were problematic.\n"
        "4. Identify 'recommended_sections': a list of section IDs the learner "
        "should review (e.g. 'ch-01-cpp-refresher#section-1-2'). Return an empty "
        "list if no additional review is needed.\n"
        "5. Report a 'score': count of Questions whose tests PASSED (test_passed=True). "
        "Questions with test_passed=False or None count as 0. The score must be "
        "between 0 and the total number of Questions (inclusive).\n"
        "6. The 'per_question' list must contain exactly one entry per Question, "
        "in any order, identified by 'question_id'. Each entry has only: "
        "'question_id' (int) and 'explanation' (non-empty string).\n"
    )

    user_message = (
        f"Section Title: {section_title}\n\n"
        f"Section Content (for context):\n{section_content}\n\n"
        f"Quiz Questions and Learner Submissions:\n{questions_text}\n\n"
        "Please grade the submissions following the strict requirements above."
    )

    return system_prompt, [{"role": "user", "content": user_message}]


# ---------------------------------------------------------------------------
# WorkflowSpec registration (fires at import time)
# ---------------------------------------------------------------------------

_spec = WorkflowSpec(
    name="grade_attempt",
    input_schema=GradeAttemptInput,
    output_schema=GradeAttemptOutput,
    tiers=grade_attempt_tier_registry(),
    steps=[
        LLMStep(
            tier="grade-attempt-llm",
            prompt_fn=_grade_attempt_prompt_fn,
            response_format=GradeAttemptOutput,
            retry=RetryPolicy(max_transient_attempts=3),
        ),
    ],
)

register_workflow(_spec)
