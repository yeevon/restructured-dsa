# Restructured CS 300

## Authority
The manifest at `design_docs/MANIFEST.md` is the locked source of truth. Read it before any task. If a request would violate a hard constraint, non-goal, or invariant, refuse and surface the conflict — do not interpret around it.

## Stack
- Backend: Python 3.12, FastAPI, SQLite, Pydantic
- AI engine: `ai-workflows` framework (only AI engine; never call models directly)
- LaTeX parsing: plasTeX (Python-native; keeps the stack uniform)
- Frontend: HTMX + Jinja2 server templates. Functional over pretty. No SPA framework, no React, no client-side state. Server returns HTML fragments; HTMX swaps them.
- Tests: pytest (backend), pytest + httpx for HTMX route tests (rendered HTML assertions)

## Tier routing (justified multi-tier per manifest §6)

The `ai-workflows` framework supports tier routing. This project uses it:

- **Local tier** — small model running locally (Ollama or an OpenAI-compatible local server). Used for: MCQ generation, MCQ grading, weak-topic extraction from MCQ-only attempts. Fast enough that async still feels nearly live.
- **Hosted tier** — larger hosted model (Claude or GPT). Used for: coding-question generation, coding-answer grading (which involves running tests), and any rubric-style grading of free-form responses. Local hardware can't do this within reasonable latency.
- **TTS tier** — separate provider (decided per-Chapter; see §Decided below). Lecture audio generation only.

Tier selection is by *workflow*, not by per-request routing. `cs300.workflows.grade_mcq` is local-tier; `cs300.workflows.grade_coding` is hosted-tier. Don't try to be cleverer than that.

## Question persistence (decided)

Questions are persisted in SQLite the moment they're generated. Schema sketch (architect refines on first quiz-generation task):

| Column | Notes |
|---|---|
| `id` | Stable, e.g. `q-ch01-bst-insertion-001` |
| `section_id` | Section binding (the manifest invariant — Section, not Chapter) |
| `topic_tags` | Many-to-many to the Topic vocabulary |
| `type` | `mcq` / `coding` / `short_answer` / etc. |
| `body` | Question prompt |
| `expected_answer_or_rubric` | Schema depends on type |
| `generated_by_run_id` | The `ai-workflows` run that produced it |
| `generated_at` | Timestamp |

Plus a separate `question_attempts` table tracking every time a Question appeared in a Quiz Attempt and whether the user got it right. The "replay incorrect Questions" logic queries this table:

```sql
SELECT q.* FROM questions q
JOIN question_attempts qa ON qa.question_id = q.id
WHERE q.section_id = ?
  AND qa.was_correct = false
  AND qa.attempt_id IN (SELECT id FROM quiz_attempts WHERE section_id = ? ORDER BY created_at DESC)
GROUP BY q.id
```

(That's roughly the shape; architect will refine.)

A Quiz is a snapshot — `quiz_questions` joins Quiz to Question with an order index. The same Question can appear in many Quizzes (that's the whole point of replay). Default Quiz size: **10 Questions** (tunable via config; not a manifest invariant).

## Quiz composition (decided — implements manifest §7 mixed-bank invariant)

The Quiz-generation workflow composes a 10-Question Quiz for a Section as follows:

1. **First Quiz for the Section**: 10 fresh Questions, generated targeting the Section's Topics broadly.
2. **Every subsequent Quiz for the Section**:
   - Pull Questions the user previously answered incorrectly for this Section (the replay set).
   - Generate fresh Questions targeting Weak Topics from the most recent Attempt.
   - Mix to reach 10 total. Default ratio: 40% replay, 60% fresh, capped by what's available in the replay set. (If the user only has 2 wrong-answer Questions for this Section, the Quiz is 2 replay + 8 fresh, not 4 replay + 6 fresh.)
3. The mix ratio lives in code (not the manifest) so it can be tuned without a manifest edit.
4. Quiz generation is always **manually triggered** by the user. The user clicks "Generate Quiz for Section X," waits for the run to complete, gets a Notification, then takes the Quiz.

## Deferred (don't build yet)

- **Topic weighting based on per-question wrong-answer history.** Author may revisit once 30+ Attempts of bank data exist. Premature now — no signal to calibrate against.

## Commands
- Run: `<dev command>`
- Test: `pytest`
- Lint: `ruff check --fix && ruff format`
- Type check: `mypy cs300/`

## Conventions
- Workflows live in `cs300/workflows/<workflow_name>.py`, register via `AIW_EXTRA_WORKFLOW_MODULES`
- Workflow naming reflects tier: `grade_mcq` (local), `grade_coding` (hosted), `generate_mcq` (local), `generate_coding` (hosted), `synth_audio` (TTS). The tier is set in the WorkflowSpec, not chosen at call time.
- Workflows are minimal: single tier per workflow; validators, retries, gates added in response to real failure modes
- No `await some_llm.generate(...)` outside `cs300/workflows/`. AI calls go through workflow runs only.
- Persistence layer is the only place that talks to SQLite. Routes use repository functions.
- HTMX routes return HTML fragments by default; full-page renders only on direct navigation
- Public functions get type hints; private helpers can skip them when types add no information.
- Commit format: `<type>(<scope>): <description>` where scope is e.g. `lecture`, `quiz`, `workflow`, `notes`
- LaTeX source under `content/latex/` is read-only from the application's perspective. Never staged in any commit that also touches application code.

## Manifest conformance
The reviewer agent (and the pre-commit hook) check for these specifically:
- No imports from `langchain`, `llamaindex`, `openai` (direct), `anthropic` (direct), or any LLM library outside `ai-workflows`
- No `cross-section` quiz logic — Quiz IDs always reference exactly one Section
- Mandatory/Optional split preserved in any new UI surface
- No code path that grades a Quiz Attempt synchronously
- No code that writes to LaTeX source files

## What this project is NOT
See MANIFEST §5 (Non-Goals). Examples: no auth, no multi-user, no AI tutor chat, no mobile, no LMS features. If you find yourself sketching something that fits one of those, stop and surface the conflict.
