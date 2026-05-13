"""
app/workflows/question_gen — CS-300-owned question-generation WorkflowSpec.

ADR-036 §Where the CS-300 workflow module lives:
  This module defines and registers the `question_gen` ai-workflows workflow.
  It is loaded via AIW_EXTRA_WORKFLOW_MODULES=app.workflows.question_gen when
  the `aiw` CLI subprocess is invoked by the out-of-band processor
  (app/workflows/process_quiz_requests.py).

The workflow:
  - Input:  QuestionGenInput (section_content: str, section_title: str)
  - Output: QuestionGenOutput (questions: list[GeneratedQuestion])
             where GeneratedQuestion has prompt: str, topics: list[str], and
             test_suite: str (min_length=1 — ADR-040)
  - One LLMStep with prompt_fn (not prompt_template — the Section content is
    LaTeX and may contain { } characters; ADR-036).
  - response_format=QuestionGenOutput (required; KDR-004).
  - Tier: gemini/gemini-2.5-flash via LiteLLMRoute (ADR-036 default).

Schema constraints (ADR-036 / Manifest §5 / §7):
  - NO choice / correct_choice / answer_text / option_* / recall_* / describe_*
    field in GeneratedQuestion or QuestionGenOutput. Every Question is a
    hands-on coding task — the schema makes a non-coding Question inexpressible.

MC-1: only ai_workflows.* imported (no openai / anthropic / litellm / langgraph etc.).
MC-10: no DB driver imports; no SQL literals; no DB access.
"""

from __future__ import annotations

import os

from pydantic import BaseModel, ConfigDict, Field

from ai_workflows.primitives.tiers import LiteLLMRoute, TierConfig
from ai_workflows.workflows import LLMStep, WorkflowSpec, register_workflow


# ---------------------------------------------------------------------------
# Pydantic schemas — input and output
# ---------------------------------------------------------------------------


class QuestionGenInput(BaseModel):
    """
    Input to the question_gen workflow.

    ADR-036 §Workflow module: section_content is the Section's parsed LaTeX text
    (the prompt material); section_title is the Section's title for framing.
    No learner-controlled num_questions this slice (ADR-034's surface is a single
    submit button with no form fields).
    """
    model_config = ConfigDict(extra="forbid")

    section_content: str
    section_title: str


class GeneratedQuestion(BaseModel):
    """
    A single generated Question candidate.

    ADR-036 §Workflow module (extended by ADR-040):
      - prompt: str — the coding-task instruction (e.g. "Implement X in C++").
        The prompt must name the function/class signature the test suite tests,
        so the learner's implementation has a stable target.
      - topics: list[str] — Topic tags for Weak-Topic identification later.
      - test_suite: str — a runnable test-code string that verifies an
        implementation of the Question's coding task (ADR-040). min_length=1
        so a literally-empty test suite is rejected at the validator layer.
        Holds ONLY test source code — never an option list, a true/false key,
        a "describe" prompt, or a recall answer (manifest §5/§7; ADR-040).

    NO choice / correct_choice / answer_text / option_* / recall_* / describe_*
    field — the schema makes a non-coding Question inexpressible.
    Manifest §5: 'No non-coding Question formats.'
    Manifest §7: 'Every Question is a hands-on coding task.'
    """
    model_config = ConfigDict(extra="forbid")

    prompt: str
    topics: list[str]
    test_suite: str = Field(min_length=1)


class QuestionGenOutput(BaseModel):
    """
    Output (terminal artefact) of the question_gen workflow.

    ADR-036: the FIRST field is the terminal artefact per the framework's
    FINAL_STATE_KEY convention — `questions: list[GeneratedQuestion]`.
    The CLI prints json.dumps({"questions": [...]}, indent=2) on stdout.
    """
    model_config = ConfigDict(extra="forbid")

    questions: list[GeneratedQuestion]


# ---------------------------------------------------------------------------
# Tier registry
# ---------------------------------------------------------------------------


def _resolve_model() -> str:
    """
    Resolve the LLM model string for question generation at call time.

    Precedence (highest to lowest):
      1. QUESTION_GEN_MODEL env var — full litellm model string, used verbatim.
      2. OLLAMA_MODEL_QUESTION_GEN env var — Ollama model name; "ollama/" prefix
         is prepended if the value does not already start with it.
      3. Default: "gemini/gemini-2.5-flash".

    Reads os.environ at call time so monkeypatched env vars take effect in tests
    without a module reload.

    ADR-036 §Workflow module: "the specific provider/model is a tuning decision
    inside the tier registry, not an architectural commitment."
    """
    if qgm := os.environ.get("QUESTION_GEN_MODEL"):
        return qgm
    if ollama := os.environ.get("OLLAMA_MODEL_QUESTION_GEN"):
        return ollama if ollama.startswith("ollama/") else f"ollama/{ollama}"
    return "gemini/gemini-2.5-flash"


def question_gen_tier_registry() -> dict[str, TierConfig]:
    """
    Tier registry for the question_gen workflow.

    ADR-036 §Workflow module: one LLM tier — resolved via _resolve_model()
    (default: gemini/gemini-2.5-flash via LiteLLMRoute; needs GEMINI_API_KEY
    at runtime). The specific provider/model is a tuning decision, not an
    architectural commitment.
    """
    model = _resolve_model()
    return {
        "question-gen-llm": TierConfig(
            name="question-gen-llm",
            route=LiteLLMRoute(model=model),
        )
    }


# ---------------------------------------------------------------------------
# Prompt function
# ---------------------------------------------------------------------------


def _question_gen_prompt_fn(state: dict) -> tuple[str | None, list[dict]]:
    """
    Build the system + user prompt for the question_gen LLMStep.

    ADR-036: uses prompt_fn (not prompt_template) because the Section content is
    LaTeX and may contain { } characters which would collide with str.format
    placeholders.

    The prompt instructs the LLM to generate hands-on coding-task Questions
    about the Section's content — never describe/recall/choose items.
    """
    section_content: str = state.get("section_content", "")
    section_title: str = state.get("section_title", "")

    system_prompt = (
        "You are an expert computer science educator generating hands-on coding "
        "questions for a data structures and algorithms course.\n\n"
        "STRICT REQUIREMENTS:\n"
        "1. Every question MUST be a hands-on CODING TASK that asks the student to "
        "IMPLEMENT something in C++ (or C++/pseudocode as specified).\n"
        "2. NEVER generate: multiple-choice questions, true/false questions, "
        "short-answer/explain questions, describe-the-concept questions, "
        "recall/define questions, or any question that does not require writing code.\n"
        "3. Each question should target a specific implementable concept from the "
        "Section content below.\n"
        "4. Generate between 3 and 6 questions.\n"
        "5. Each question must include 1-3 topic tags relevant to the concept being tested.\n"
        "6. The 'prompt' field must be a clear, specific coding instruction that NAMES "
        "the function or class signature the student must implement "
        "(e.g. 'Implement a function `int* two_sum(const std::vector<int>& nums, int target)` "
        "that returns the indices of the two numbers that add up to target.').\n"
        "7. The 'test_suite' field MUST be a self-contained, runnable test file "
        "that verifies a correct implementation of the Question's prompt. "
        "The test suite MUST call the exact function/class named in the 'prompt' field. "
        "For C++ implementations, use assert-based cases in a main() function. "
        "For Python implementations, use unittest.TestCase or standalone assert statements. "
        "The test_suite field must contain ONLY test source code — never an option list, "
        "a true/false key, a description, or a recall answer. "
        "A non-empty test_suite is REQUIRED for every question without exception.\n"
    )

    user_message = (
        f"Section Title: {section_title}\n\n"
        f"Section Content:\n{section_content}\n\n"
        "Generate hands-on coding questions for this Section. Each question must ask "
        "the student to implement a concept from this Section in code."
    )

    return system_prompt, [{"role": "user", "content": user_message}]


# ---------------------------------------------------------------------------
# WorkflowSpec registration (fires at import time)
# ---------------------------------------------------------------------------

_spec = WorkflowSpec(
    name="question_gen",
    input_schema=QuestionGenInput,
    output_schema=QuestionGenOutput,
    tiers=question_gen_tier_registry(),
    steps=[
        LLMStep(
            tier="question-gen-llm",
            prompt_fn=_question_gen_prompt_fn,
            response_format=QuestionGenOutput,
        ),
    ],
)

register_workflow(_spec)
