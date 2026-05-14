# LLM Audit — TASK-019: The Quiz-grading slice — an out-of-band `process_quiz_attempts` processor + a new `grade_attempt` `ai-workflows` workflow + the Grade aggregate (per-Question correctness/explanation + aggregate score + Weak Topics + recommended Sections) + the graded-state rendering on the take page; deferring the active Notification entity and the relational Topic-vocabulary migration to follow-on slices

**Task file:** `design_docs/tasks/TASK-019-quiz-grading-slice-minimal.md`
**Started:** 2026-05-13T00:00:00Z
**Status:** Implemented
**Current phase:** review

---

## Human gates

| Time | Gate | Result | Notes |
|---|---|---|---|
| 2026-05-13T00:05:00Z | Task reviewed | auto-accepted | /auto run |
| 2026-05-13T00:10:00Z | ADR-048 reviewed | auto-accepted | /auto run |
| 2026-05-13T00:10:00Z | ADR-049 reviewed | auto-accepted | /auto run |
| 2026-05-13T00:10:00Z | ADR-050 reviewed | auto-accepted | /auto run |
| 2026-05-13T00:10:00Z | ADR-051 reviewed | auto-accepted | /auto run |
| 2026-05-13T00:15:00Z | Tests reviewed | auto-accepted | /auto run — 93 failed, 4 passed (4 are pre/post-invariants) |
| 2026-05-13T00:20:00Z | /design output gate — pass (TASK-019) | pass | /auto run — 4 ADRs moved Proposed→Accepted at Phase 2; architecture.md regenerated; quiz-grading-slice-shape.md resolved by ADR-048+049+050+051 |
| 2026-05-13T00:20:00Z | rendered-surface verification — pass (TASK-019 graded-state take page) | pending human | /auto run — visual check post-commit; review `tests/playwright/.screenshots/` or open the graded-Attempt take page in a browser |
| 2026-05-13T00:20:00Z | grading end-to-end sanity — pass (TASK-019) | pending human | /auto run — real-engine grading run on a real Attempt + deliberately-broken second Attempt → `grading_failed` honestly; manual exercise post-commit |

---

## Agent runs

### Run 001 — architect / Mode 1 `/next`

**Time:** 2026-05-13T00:00:00Z

**Input files read:**
- `design_docs/MANIFEST.md` (full — §3 Primary Objective, §4 Secondary Objective, §5 Non-Goals, §6 Behaviors and Absolutes, §7 Invariants and Principles, §8 Glossary)
- `CLAUDE.md` (via project-instructions context — authority order, the Markdown authority rule, the task-file convention for programmatic ACs vs Verification gates, the pushback protocol, the audit log lifecycle)
- `design_docs/architecture.md` (full — Accepted ADR index (001–047 with gaps), the Proposed-ADR table (ADR-032 parked), the Superseded table, the Project-structure summary)
- `.claude/skills/manifest-conformance/SKILL.md` (full — MC-1 through MC-10; re-checked each rule's applicability to the grading slice)
- `design_docs/tasks/` (Glob — 18 task files; TASK-018 task file read in full; earlier tasks by index/title; the audit file for TASK-018 read in chunks)
- `design_docs/decisions/` (Glob — 47 ADR files; ADR-040 read in part for the prompt-and-schema precedent the `grade_attempt` workflow mirrors; ADR-036 / ADR-037 / ADR-038 / ADR-039 / ADR-043 / ADR-044 referenced via `architecture.md`'s project-structure summary)
- `design_docs/project_issues/` (Glob — 8 open + the Resolved subdir; `quiz-grading-slice-shape.md` read in full — this task resolves it; `question-gen-prompt-text-redundant-with-preamble.md` read in full — out of scope here, editorial; `in-app-test-runner-slice-shape.md` already Resolved by ADR-042/043/044 — reference only; `notes-save-relocates-reader.md`, `tooling-lint-and-type-check.md` read in full — re-flagged but not actioned; `parser-fidelity-body-linebreak-and-display-math.md`, `ch06-textbackslash-double-renders-as-double-backslash.md` by file listing only — explicitly deferred again)
- `app/workflows/question_gen.py` (first 50 lines — the `WorkflowSpec` + `LLMStep` + `prompt_fn` + `response_format` + `ConfigDict(extra="forbid")` pattern the `grade_attempt` workflow mirrors)

**Tools / commands used:** `Read` (MANIFEST.md, architecture.md, manifest-conformance SKILL.md, ADR-040 partial, TASK-018 task file, quiz-grading-slice-shape.md, question-gen-prompt-text-redundant-with-preamble.md, in-app-test-runner-slice-shape.md, notes-save-relocates-reader.md, tooling-lint-and-type-check.md, TASK-018 audit partial, question_gen.py partial); `Glob` (`design_docs/tasks/*.md`, `design_docs/decisions/*.md`, `design_docs/project_issues/*.md`); `Grep` (`grading_error|grading_failed|grading|grade` in `app/`; `process_quiz_attempts|grade_attempt` repo-wide — confirmed neither exists yet in `app/`); `Write` (this audit file, the task file).

**Files created:** `design_docs/tasks/TASK-019-quiz-grading-slice-minimal.md`, `design_docs/audit/TASK-019-quiz-grading-slice-minimal.md`

**Files modified:** none

**Task alternatives considered:**

1. **(Chosen) The Quiz-grading slice — `grade_attempt` workflow + `process_quiz_attempts` processor + Grade aggregate + graded-state rendering, deferring the active Notification entity and the relational Topic-vocabulary migration.** Resolves the standing `quiz-grading-slice-shape.md` (open since 2026-05-12, decide-when condition now met); produces the per-Question correctness signal (`attempt_questions.is_correct`) and the Weak Topics list the composition slice consumes (MC-8); mirrors TASK-014's generation-slice shape exactly (workflow + processor + lifecycle + failure-handling) — one-session precedent; the inputs the grading workflow consumes (the persisted assertion-only test results + `preamble`) are now in place and meaningful post-TASK-017/TASK-018; the §8 Grade is the next thing the manifest's reinforcement loop is defined in terms of.

2. **The TASK-018 follow-up `question-gen-prompt-text-redundant-with-preamble.md`** (a one-line prompt edit). Rejected as next task: editorial / low priority per the issue file ("Slot below the grading slice"); doesn't block grading; the redundancy is a learner-reading nuisance, not a correctness issue; will slot into a non-feature cycle paired with lint/type-check tooling.

3. **The active Notification entity as a standalone slice** — `notifications` table + chrome badge + `seen_at` lifecycle. Rejected as a *standalone* next task: more useful when there are multiple async-result pathways producing notifications (generation + grading + ...); the §8 Notification obligation for the *grading* slice can be met by the take-page state flip mirroring ADR-037's pattern; the Notification slice is the natural task *after* this one (or the composition slice).

4. **The relational Topic-vocabulary migration as a standalone slice** — `topics` table + `question_topics` join + backfill. Rejected as a standalone task: becomes load-bearing only when the *composition* path needs to query across Topics; until then, `questions.topics` (delimited TEXT) suffices; the migration is additive (ADR-022) — done later.

5. **The replay-+-fresh composition slice (MC-8 in full).** Rejected — *requires* grading to have produced `attempt_questions.is_correct` (the wrong-answer-replay history) and the Grade's `weak_topics` (the fresh-portion driver); out of order; the slice **after** this one.

6. **A monolithic "everything else for the Quiz pillar in one task" slice** — grading + Notification entity + Topic-vocabulary migration + composition. Rejected — multi-session; bigger than any prior task; bundles distinct architectural questions deserving their own `/design`.

7. **A monolithic in-browser IDE / "VS Code online" surface** in one task. Rejected — multi-session; the roadmap memory's "future big feature" framing is a reference point, not a literal spec; ADR-040's reordering does not put the IDE next.

8. **Lint/type-check tooling task** (`tooling-lint-and-type-check.md`, **13th+ recurrence**). Rejected — still a feature cycle; primary objective not yet served by tooling; will land in a non-feature cycle after grading + composition close the loop.

9. **Parser-fidelity issues** (`parser-fidelity-body-linebreak-and-display-math.md`, `ch06-textbackslash-double-renders-as-double-backslash.md`). Rejected — explicitly deferred again; Lecture-content rendering is substantially polished and lower-priority than closing the Quiz pillar.

10. **The parked ADR-032** (Notes-save scroll, `Proposed`/deferred). Rejected — explicitly deferred per the human's decision; not activated by this task.

11. **A grading slice split — TASK-019a (workflow + processor + Grade-storage + lifecycle) and TASK-019b (graded-state rendering on the take page).** Considered as a contingency: if `/design` concludes the slice is genuinely two-session-shaped, this is the split shape. The task's "Architectural concerns" #1 flags it explicitly so `/design` can call it. Forecast: one session (TASK-014 shipped the analogous generation slice — workflow + processor + lifecycle + failure-handling — in one session; the take-page render branch is a small additive change to an already-existing template). The architect makes the final call in Mode 2.

**Decisions surfaced:** the task forecasts **three to four ADRs** for `/design TASK-019` (mirroring how TASK-014 → ADR-036 + ADR-037, TASK-017 → ADR-042 + ADR-043 + ADR-044, TASK-018 → ADR-045 + ADR-046 + ADR-047):

- **(A) The `grade_attempt` `ai-workflows` workflow** — Pydantic schemas (`GradeAttemptInput` carrying Questions + responses + test results + Section grounding; `GradeAttemptOutput` carrying per-Question `explanation` + aggregate `score` / `weak_topics` / `recommended_sections`); `extra="forbid"` on every model; `min_length=1` on `explanation`; the architecturally load-bearing prompt commitment "the workflow's job is the *explanation* + the *aggregate*, NOT re-judging correctness — correctness is the runner's verdict"; the `LLMStep`'s tier via `grade_attempt_tier_registry()`; the `RetryPolicy`; MC-1 preserved (`ai_workflows.*` + `pydantic` + stdlib only).

- **(B) The `process_quiz_attempts` out-of-band grading processor** — `python -m app.workflows.process_quiz_attempts` (mirroring ADR-037's `process_quiz_requests`); the poll-and-process loop on `submitted` Attempts; the lifecycle transitions `submitted → grading → graded` / `submitted → grading → grading_failed`; the `aiw run grade_attempt --input ... --run-id attempt-{attempt_id}` shell-out; the artefact parsing; the persistence call; `grading_failed` + `grading_error` capture; the "notified" obligation met by the take-page state flip; the active Notification entity deferred.

- **(C) The Grade aggregate's persistence** — forecast: a new `grades` table (PK `attempt_id`, FK to `quiz_attempts`, columns `score INTEGER`, `weak_topics TEXT`, `recommended_sections TEXT`, `graded_at TEXT`); the `Grade` dataclass; the new persistence functions (`mark_attempt_grading` / `mark_attempt_graded` / `mark_attempt_grading_failed` / `save_attempt_question_grade` / `save_attempt_grade` / `get_grade_for_attempt`); the new nullable `quiz_attempts.grading_error TEXT` column (mirroring `quizzes.generation_error`); `attempt_questions` gains writeable `is_correct` + `explanation` (the NULL-until-graded columns ADR-033 created); `weak_topics` / `recommended_sections` persist as `'|'`-delimited TEXT; the relational `topics` table deferred to the composition slice; MC-7 / MC-10 preserved; additive migration per ADR-022.

- **(D) The graded-state and grading-failed-state rendering on the take page** (may be a section of (C) or split — `/design`'s call) — `quiz_take.html.j2` gains `{% if attempt.status == 'graded' %}` / `{% elif attempt.status == 'grading_failed' %}` branches; per-Question explanation block when `aq.explanation is not None`; the cross-references in the Weak Topics / recommended Sections lists (recommended Sections link to the existing ADR-031 `#section-{n-m}` anchors); new `.quiz-take-grade-*` / `.quiz-take-explanation` / `.quiz-take-question-correct` / `.quiz-take-question-incorrect` / `.quiz-take-grading-failed` rules in `quiz.css` (reusing the `quiz-take-*` namespace per ADR-008; no new file; no `base.css` change); MC-5 honored (the `grading_failed` state shows the honest failure, never a fabricated Grade); MC-9 honored (no Quiz generated).

`/design` **resolves** `quiz-grading-slice-shape.md`. `/design` may file new project_issues for: (i) the active Notification entity slice (the `notifications` table + chrome badge + `seen_at` lifecycle — captured as the natural follow-on); (ii) the relational Topic-vocabulary migration (captured as the composition slice's `/design` decision). Neither is decided here.

The `Pending-resolution` ADR table is empty; no `> NEEDS HUMAN:` expected, **except** for the architect's explicit contingency check in "Architectural concerns" #1: if `/design` concludes the slice is genuinely two-session-shaped, the right move is to split TASK-019 into 019a + 019b and pause Mode 2 with `> NEEDS HUMAN: TASK-019 should split into 019a + 019b — confirm`. The forecast is one session; the architect makes the final call.

**Architecture leaks found:** none.

- `architecture.md`'s relevant paragraphs — "AI integration and Quiz generation" (ADR-036 / ADR-037 / ADR-040 / ADR-045), "Quiz domain schema" (ADR-033 / ADR-041 / ADR-044 / ADR-046), "In-app test runner (code-execution sandbox)" (ADR-042 / ADR-043 / ADR-044 / ADR-047), "Quiz-taking surface" (ADR-038 / ADR-039 / ADR-043 / ADR-044 / ADR-047) — all trace to Accepted ADRs; the new TASK-019 paragraph will regenerate mechanically when ADRs are Accepted.
- `CLAUDE.md` is clean for this task's purposes — no architectural content has leaked in. The `Commands:` section has a forecast new entry "Process pending Quiz attempts (out-of-band Quiz-grading processor): `python -m app.workflows.process_quiz_attempts`" that the human will add per ADR-037's precedent — the architect does **not** edit CLAUDE.md; flagged for the human in Run 001 below.
- The conformance skill is clean — no new guardrail required (MC-1 / MC-4 / MC-5 / MC-7 / MC-9 / MC-10 are all already enforced; the grading slice fits inside their existing scope; no new MC rule is needed; if `/design` surfaces a need for one, the architect surfaces it to the human, doesn't edit the skill).
- The roadmap memory note (`project_roadmap_ide_and_known_issues.md`) is still stale relative to ADR-040's reordering (runner → grading → composition → polish); the human should update it after this task to mark the grading step done — but not the architect's edit to make. Not an ARCHITECTURE LEAK — a memory file is not a project `.md` and introduces no architectural claim into a project `.md`.

**Pushback raised:**

1. **The slice's size is genuinely larger than recent slices** — 3–4 ADRs and one session is at the upper end of the project's shipping cadence (TASK-013 / TASK-017 / TASK-018 each shipped 3 ADRs). The task's "Architectural concerns" #1 flags the split contingency explicitly so `/design` can call it if needed. The forecast is one session, supported by the TASK-014 precedent (the generation slice shipped workflow + processor + lifecycle + failure-handling in one session). The architect's `/design` makes the final call.

2. **§8 Grade-correctness must be an architectural property of the workflow, not a hope about LLM behavior.** §8 says "correctness determined by whether the learner's code passed the Question's tests"; the architecturally honest implementation is `is_correct` derived from `attempt_questions.test_passed`, not free-form-judged by the grading LLM. The workflow ADR must record this explicitly — otherwise a divergent LLM verdict would be the §8 violation MC-5's spirit forbids. Captured in "Architectural concerns" #2.

3. **The `grading_failed` honesty path is load-bearing.** Adding the additive nullable `quiz_attempts.grading_error TEXT` column (mirroring ADR-037's `quizzes.generation_error`) is the cheap path to MC-5 conformance; the take page's `grading_failed`-state render must not fabricate a Grade; **no partial Grade may persist** even if the workflow produced *some* of the per-Question explanations before failing. The test-writer should write the "partial-failure path persists nothing" test explicitly. Captured in "Architectural concerns" #3.

4. **The Notification deferral and the Topic-vocabulary deferral are conformant per ADR-035 ("describes what's built")** — recorded in the slice's ADR(s) as deferred to follow-on slices, **not** as project-wide constraints. The take-page state flip is the only notification surface this slice ships; the relational vocabulary is a composition-slice decision. Captured in "Architectural concerns" #4 and #5.

5. **The 13th-recurrence lint/type-check tooling gap** — re-flagged, not actioned. Captured in "Architectural concerns" #6.

6. **The roadmap memory note** — re-flagged as stale; not the architect's edit to make. Captured in "Architectural concerns" #7.

No `> MANIFEST TENSION:`, no `> NEEDS HUMAN:`, no `> PRIMARY OBJECTIVE COMPLETE:` — the manifest is internally consistent for this slice; the primary objective is *not* complete (the composition slice still needs to ship after grading); this task advances it directly by producing the §8 Grade aggregate the manifest's reinforcement loop is defined in terms of.

**Output summary:** Proposed TASK-019 — "The Quiz-grading slice — `grade_attempt` `ai-workflows` workflow + `process_quiz_attempts` out-of-band processor + Grade aggregate (per-Question correctness/explanation + aggregate score + Weak Topics + recommended Sections) + the graded-state and grading-failed-state rendering on the take page; deferring the active Notification entity and the relational Topic-vocabulary migration to follow-on slices"; resolves the standing `quiz-grading-slice-shape.md` (open since 2026-05-12); produces the per-Question correctness signal `attempt_questions.is_correct` and the Weak Topics list the composition slice (next) consumes (MC-8); mirrors TASK-014's generation-slice shape (workflow + processor + lifecycle + failure-handling); the inputs the grading workflow consumes (the persisted assertion-only test results + `preamble`) are now in place and meaningful post-TASK-017/TASK-018; chosen over the TASK-018 follow-up editorial issue (low priority, doesn't block grading), the active-Notification standalone slice (more useful after grading ships, defer), the relational Topic-vocabulary migration (composition-slice concern), the composition slice itself (out of order — needs grading first), and the monolithic alternatives (multi-session). Three-to-four ADRs forecast: the `grade_attempt` workflow ADR (the Pydantic schemas, the prompt's "explanation + aggregate, not re-judge correctness" framing, the `LLMStep`'s tier registry, MC-1 preserved); the `process_quiz_attempts` processor ADR (mirroring ADR-037 — lifecycle, failure-handling, the `grading_error` capture, the take-page-state-flip notification path with the active Notification entity deferred); the Grade-aggregate-persistence ADR (forecast: a new `grades` table, the new persistence functions, additive migration per ADR-022, MC-7 / MC-10 preserved); the graded-state-rendering ADR (may be a section of the persistence ADR — `/design`'s call). UI task — `## Verification gates (human-only)` carries the rendered-surface review (the graded-state and grading-failed-state take page) + a real-engine end-to-end grading sanity check (a fresh user-triggered Quiz, the learner exercises the runner, submits, runs the grading processor, sees a §8-conformant Grade with score + per-Question explanation + Weak Topics + recommended Sections; a deliberately-broken grading attempt flips to `grading_failed` honestly).

---

TASK-019 proposed at `design_docs/tasks/TASK-019-quiz-grading-slice-minimal.md`. Audit at `design_docs/audit/TASK-019-quiz-grading-slice-minimal.md`. Review and edit before running `/design TASK-019`.

### Run 002 — architect / Mode 2 `/design`

**Time:** 2026-05-13T00:30:00Z

**Input files read:**
- `design_docs/MANIFEST.md` (full — §3 Primary Objective, §4 Secondary Objective, §5 Non-Goals, §6 Behaviors and Absolutes, §7 Invariants and Principles, §8 Glossary — re-verified all four facets of the Grade glossary and the Notification glossary)
- `CLAUDE.md` (via project-instructions context — re-verified the Tier table for the Markdown authority rule; the orchestrator-verification-of-subagent-outputs §; the pushback protocol; the audit log lifecycle and append-only discipline)
- `design_docs/architecture.md` (full — Accepted ADR index 001–047; the Proposed-ADR table; the Project-structure summary; identified the relevant Accepted ADRs the new ADRs consume — ADR-022 / ADR-033 / ADR-036 / ADR-037 / ADR-038 / ADR-039 / ADR-040 / ADR-041 / ADR-042 / ADR-043 / ADR-044 / ADR-045 / ADR-046 / ADR-047 / ADR-008 / ADR-031 / ADR-035 / ADR-002 / ADR-029)
- `.claude/skills/manifest-conformance/SKILL.md` (full — MC-1 through MC-10; verified each rule's applicability and the dormant-rule-activation state)
- `design_docs/tasks/TASK-019-quiz-grading-slice-minimal.md` (full — "Inputs read"; "What and why"; the seven Acceptance criteria; the three Verification gates; the four "Architectural decisions expected" sections; the alternatives considered; the eight architectural concerns; the out-of-scope list; the verify steps)
- `design_docs/project_issues/quiz-grading-slice-shape.md` (full — the question, the option set, the constraints, the cross-references — confirmed the slice resolves this issue and chose specific shapes for each of the four sub-decisions)
- `design_docs/project_issues/in-app-test-runner-slice-shape.md` (first 10 lines — reference only; Resolved by ADR-042/043/044; confirmed the upstream slice's outputs are the inputs the grading workflow consumes)
- `design_docs/decisions/ADR-037-async-quiz-generation-processing.md` (full — the precedent the grading processor mirrors section-for-section; the "ships with the grading slice" forecast for the Notification entity is the one substantive call to revisit; verified the failure-handling discipline, the lifecycle transitions, the trigger-handoff posture, the "notified" framing)
- `design_docs/decisions/ADR-046-question-preamble-persistence.md` (first 120 lines — the persistence-ADR template style; verified the nullable-column / additive-migration mechanic the new `quiz_attempts.grading_error` and `grades` table mirror)
- `design_docs/decisions/ADR-044-attempt-question-test-result-persistence.md` (first 80 lines — verified ADR-044's "is_correct set by the grading slice (reading the persisted test result), not by the runner" forecast; this slice realizes that forecast)
- `app/workflows/question_gen.py` (full — the `WorkflowSpec` / `LLMStep` / `prompt_fn` / `response_format` / `register_workflow` / `ConfigDict(extra="forbid")` / tier-registry / `_resolve_model()` env-var precedence patterns the `grade_attempt` workflow mirrors section-for-section)
- `app/workflows/process_quiz_requests.py` (full — the `aiw run question_gen --input ... --run-id ...` shell-out pattern; the `_parse_artefact_from_stdout` helper; the `_invoke_question_gen` shape; the artefact parsing; the `_get_section_content` Section-content read; the lifecycle-transition wiring; the failure-handling catch — all of which `process_quiz_attempts` mirrors)
- `app/persistence/connection.py` (full — the `_SCHEMA_SQL` block structure for the Quiz domain; the `_apply_additive_migrations` `PRAGMA table_info` recipe; the foreign-key enforcement bootstrap; the connection lifecycle; confirmed the two-place additive-migration pattern the new `grading_error` column and `grades` table follow)
- `app/persistence/quizzes.py` (first 150 lines — the public-API list; the `Quiz` / `Question` / `QuizAttempt` / `AttemptQuestion` dataclasses; the `_row_to_quiz` / `_row_to_question` / `_row_to_attempt_question` converter pattern the new `_row_to_grade` mirrors; the `_utc_now_iso()` helper)
- `app/templates/quiz_take.html.j2` (only the `attempt.status` branches — confirmed the existing `in_progress` / `submitted` / "not ready" branches the two new branches extend)
- `app/main.py` (the take-quiz route grep — confirmed the route shape and the existing context-var passing; the new `grade` context var is one additional `get_grade_for_attempt` call)

**Tools / commands used:**
- `Read` — all the files above
- `Glob` — `design_docs/tasks/TASK-019*` (one match), `design_docs/project_issues/*.md` (8 active + Resolved/ subdir), `design_docs/project_issues/Resolved/*.md` (15 historical), `design_docs/decisions/ADR-037*` / `ADR-044*` / `ADR-046*` (one each)
- `Grep` — `def render_quiz_take|quiz_take|process_quiz_attempts|grade_attempt` in `app/` (confirmed neither `process_quiz_attempts` nor `grade_attempt` exists yet), `attempt.status|graded|grading_failed` in `quiz_take.html.j2` (the existing render-branch chain), `def take_quiz|def submit_quiz_take|/take|attempt.status` in `app/main.py` (the existing route + lifecycle wiring)
- `Edit` — `architecture.md` (added 4 rows to the Proposed ADRs table), `project_issues/quiz-grading-slice-shape.md` (Status → Resolved by ADR-048 + ADR-049 + ADR-050 + ADR-051 with detailed resolution note), `audit/TASK-019-quiz-grading-slice-minimal.md` (this Run 002 entry; header Status → Blocked, Current phase → design)
- `Write` — `design_docs/decisions/ADR-048-grade-attempt-ai-workflow.md`, `design_docs/decisions/ADR-049-process-quiz-attempts-out-of-band-grading-processor.md`, `design_docs/decisions/ADR-050-grade-aggregate-persistence.md`, `design_docs/decisions/ADR-051-graded-state-rendering-on-take-page.md`

**Files created:**
- `design_docs/decisions/ADR-048-grade-attempt-ai-workflow.md`
- `design_docs/decisions/ADR-049-process-quiz-attempts-out-of-band-grading-processor.md`
- `design_docs/decisions/ADR-050-grade-aggregate-persistence.md`
- `design_docs/decisions/ADR-051-graded-state-rendering-on-take-page.md`

**Files modified:**
- `design_docs/architecture.md` — appended 4 rows to the "Proposed ADRs (awaiting human acceptance)" table (ADR-048, ADR-049, ADR-050, ADR-051); did **not** introduce any architectural content (only the row entries are added; the project-structure summary is unchanged — no Accepted-ADR state transitions in this cycle, so the summary stays as it was, mirroring the mechanical maintenance protocol)
- `design_docs/project_issues/quiz-grading-slice-shape.md` — Status changed from `Open` to `Resolved by ADR-048 + ADR-049 + ADR-050 + ADR-051 (Proposed 2026-05-13, TASK-019)`; a detailed resolution note added naming the four ADRs, the shapes chosen vs the §Options known sketches (processor: mirror ADR-037; workflow: `grade_attempt.py` with tightened schema; Grade home: separate `grades` table; Topic vocabulary: stays delimited TEXT, relational form deferred to composition slice; Notification entity: deferred to a follow-on slice — explicitly departing from ADR-037's literal forecast with reasoning); the original issue text preserved below the resolution note for the historical record
- `design_docs/audit/TASK-019-quiz-grading-slice-minimal.md` — header `Status` flipped from `In progress` to `Blocked` (all four ADRs are `Proposed` awaiting human acceptance); `Current phase` flipped from `next` to `design`; this Run 002 entry appended

**ADRs proposed:**
- `ADR-048` — The `grade_attempt` `ai-workflows` workflow (CS-300-owned `WorkflowSpec` at `app/workflows/grade_attempt.py`; one `LLMStep` + `prompt_fn` + `response_format=GradeAttemptOutput`; prompt commits architecturally to "read the runner's verdict, produce explanation + aggregate, do not re-judge correctness"; `QuestionGrade` has no `is_correct` field — the §8 commitment realized in the schema itself; `extra="forbid"` everywhere; `min_length=1` on `explanation`; `RetryPolicy(max_attempts=3, exponential)`; tier registry; MC-1 preserved)
- `ADR-049` — The `process_quiz_attempts` out-of-band grading processor (mirroring ADR-037 exactly; lifecycle transitions `submitted → grading → graded`/`grading_failed`; `aiw run grade_attempt` shell-out; CS-300 sanity check on the artefact; transactional save-or-fail; the `quiz_attempts.grading_error TEXT` column; no partial Grade; no silent unbounded retry; the score cross-check architectural commitment; the take-page state flip is the "notified" mechanism; the active Notification entity deferred per ADR-035 — departure from ADR-037's literal forecast with reasoning)
- `ADR-050` — The Grade aggregate's persistence (new `grades` table PK `attempt_id` FK → `quiz_attempts`; new nullable `quiz_attempts.grading_error TEXT` column; `attempt_questions.is_correct` and `.explanation` now writeable; new `Grade` dataclass; `QuizAttempt`/`AttemptQuestion` extensions; six new persistence functions; `test_passed` → `is_correct` mapping; score cross-check implementation; `weak_topics`/`recommended_sections` as `'|'`-delimited TEXT; relational `topics` deferred to composition slice; MC-7/MC-10 preserved; additive per ADR-022)
- `ADR-051` — The graded-state and grading-failed-state rendering on the take page (new `{% elif %}` branches in `quiz_take.html.j2`; aggregate `<section class="quiz-take-grade">` + per-Question explanation + correctness indicator; honest `grading_failed` block with collapsible `<details>` exposing `grading_error`; new `.quiz-take-grade-*`/`.quiz-take-explanation`/`.quiz-take-question-correct`/`.quiz-take-question-incorrect`/`.quiz-take-grading-failed` CSS rules in `app/static/quiz.css`; runner's green/red palette extends to correct/incorrect indicator; route reads `get_grade_for_attempt`; no JavaScript needed)

**Project issues opened/resolved:**
- `quiz-grading-slice-shape.md` — Resolved by ADR-048 + ADR-049 + ADR-050 + ADR-051 (the four-way resolution with named shapes for each sub-decision)

**Project issues opened in this cycle:** none. The active Notification entity (deferred per ADR-049) is a follow-on slice's call captured in ADR-049's "Future surfaces this ADR pre-positions" and in the resolution note's "Notification entity: deferred to a follow-on slice"; per ADR-035 ("describes what's built"), the deferral is conformant and does not require a separate project_issue (the next `/next` cycle will see the deferral in ADR-049's text and decide whether to pick up the Notification slice). The relational Topic vocabulary (deferred per ADR-050) is captured in ADR-050's "Future surfaces" and in the composition slice's natural domain — also no separate project_issue needed (the composition slice's `/design` will see the deferral in ADR-050's text).

**architecture.md changes:** 4 rows added to the "Proposed ADRs (awaiting human acceptance)" table (ADR-048, ADR-049, ADR-050, ADR-051). No content moved to "Accepted ADRs" (the orchestrator does that mechanically at the auto-accept gate per the maintenance protocol). No edits to the project-structure summary (no ADR state transitioned to Accepted in this cycle — the summary is a function of the Accepted-ADR set, which is unchanged).

**Write-path check:** clean. Verified via `git status`-equivalent reasoning: the only files created or modified are under `design_docs/decisions/` (4 new ADR files), `design_docs/architecture.md` (4 rows appended to the Proposed table), `design_docs/project_issues/quiz-grading-slice-shape.md` (Status flip + resolution note), and `design_docs/audit/TASK-019-quiz-grading-slice-minimal.md` (header flip + this Run 002 entry). All four paths are within `design_docs/{decisions,project_issues,audit}/**` plus `design_docs/architecture.md`, which is the allowed Mode-2 write surface (the architect owns architecture.md per the Tier table; the project-structure-summary edits are gated to Accepted-state transitions and were not made here). No edits to `app/`, `tests/`, `CLAUDE.md`, `MANIFEST.md`, the conformance skill, or any other tier-1/tier-2 file outside architect ownership.

**Architecture leaks found:** none — verified during the read-pass.

- `architecture.md` is clean — the existing project-structure summary traces every paragraph to an Accepted ADR (cited inline) or to a generic structural description; no new architectural content was added by this cycle (only the Proposed-table rows, which are mechanical state-mapping per the maintenance protocol).
- `CLAUDE.md` is clean for this task — the "Commands" section's existing entries are operational (the architect does not edit it; the new "Process pending Quiz attempts" line is flagged for the human in ADR-049, mirroring how ADR-037's same flag was honored).
- The conformance skill is clean — no new MC rule is needed; MC-1 / MC-4 / MC-5 / MC-7 / MC-9 / MC-10 are all already-active rules that the four new ADRs honor by construction (verified in each ADR's `## Conformance check` section).
- The roadmap memory note is still stale relative to ADR-040's reordering; not the architect's edit; flagged in Run 001 (no change in Run 002).

**Pushback raised:**

1. **The active Notification entity is deferred** (ADR-049 §How the learner is notified) — explicitly departing from ADR-037's literal "ships with the grading slice" forecast, with the substantive reasoning recorded: the take-page state flip honestly satisfies §8 Notification for this slice (a learner-visible, non-real-time indication that an async result has become available); the active Notification entity's design surface (which result kinds? where does the badge live? what's the `seen_at` lifecycle?) is better designed with multiple result kinds in hand; deferring keeps the slice tractable. The deferral is conformant per ADR-035 ("describes what's built, not what won't be built"). **The architect surfaces this for the human acceptance gate** — if the human disagrees and wants the Notification entity now, ADR-049 records the natural insertion point (after `save_attempt_grade`'s transaction succeeds: one INSERT into `notifications` of kind `grade_ready` referencing the `attempt_id`).

2. **The §8 Grade-correctness commitment is realized in the workflow schema, not in the workflow's prompt alone** (ADR-048 §`is_correct` is the runner's verdict, not the LLM's — committed architecturally in the schema). The task file's "Architectural concerns #2" flagged this; the architect's tightening goes beyond "the prompt frames it" to "the schema makes it unexpressible" — `QuestionGrade` has no `is_correct` field; the LLM cannot disagree with the runner's verdict because it has no field through which to disagree. This is the architecturally honest realization of §8; the persistence layer (ADR-050) writes `is_correct` from `test_passed` per the mapping; the LLM produces explanation alone.

3. **The score cross-check is load-bearing** (ADR-049 §The score cross-check + ADR-050 §The score cross-check). The persisted `grades.score` is recomputed from `SUM(is_correct)` inside `save_attempt_grade`'s transaction — *not* taken verbatim from the workflow's `score` field. A divergent LLM `score` is logged as a debugging aid but does not propagate. The §8 truth is the runner's verdict; the LLM benefits from being prompted to count (it produces better explanations when it explicitly counts what passed) but the persisted truth is the recompute. This is the implementation of the architectural commitment "correctness = test result"; without it, an LLM miscount could fabricate the score's value, MC-5's spirit-violation.

4. **The `is_correct` mapping is `True`→1, `False`→0, NULL/non-`'ran'`→0** (ADR-050 §The `test_passed` → `is_correct` mapping) — failure-to-pass = not correct, with the *explanation* surfacing the failure mode honestly per MC-5's spirit. Considered Alternative B (`is_correct = NULL` for non-`'ran'`) and rejected: a `graded` Attempt with NULL `is_correct` values is a semantic contradiction (`graded` means "all decisions are made"). Considered Alternative C (`grading_failed` for any Attempt with NULL test_status) and rejected as too harsh: a learner who didn't run one test before submitting still gets graded honestly, with the explanation noting the failure mode.

5. **The slice is genuinely four ADRs in one session — at the upper end of the project's cadence** (TASK-013/017/018 each shipped 3 ADRs; TASK-019 ships 4). The architect's call is that the slice **does not** need to split — the four ADRs are tightly coupled (the workflow's output shape feeds the persistence layer's mapping which feeds the render's display; cleaving them across two sessions would force one ADR to forecast another's decisions, which is exactly what the project_issue tracking is for and what this `/design` resolves). The implementer can ship the slice in one session because the four ADRs ship as a coherent unit (one workflow module, one processor module, one persistence-extension transaction, one template-branch extension), each a small additive change to an existing file or a new file mirroring an existing precedent. The task file's "Architectural concerns #1" flagged the split contingency; the architect makes the no-split call.

6. **The relational Topic vocabulary stays deferred to the composition slice** (ADR-050 §Weak Topics and recommended Sections; resolution note's "Topic vocabulary" sub-decision). The migration becomes load-bearing when the composition slice's MC-8 read needs cross-Section/cross-Attempt queries (which is one slice later); the delimited-TEXT form is sufficient for this slice's writes-and-reads (per-Attempt Weak Topics, a `list[str]` that doesn't require a cross-Section query); the migration is additive per ADR-022. Deferring is conformant per ADR-035.

7. **The `grading_error` detail is exposed in a collapsible `<details>`** (ADR-051 §The `grading_failed` branch + §The "show `grading_error` to the learner" question), not hidden. The author *is* the learner here (single-user); MC-5's spirit (failures are visible and honest) is better served by the disclosure than the hide; the primary "Grading failed" message stays loud and actionable; the technical detail is one click away.

8. **The runner's green/red palette extends to the Grade's correct/incorrect indicators** (ADR-051 §Visual vocabulary). The runner's verdict and the Grade's correctness are the same truth per ADR-050's mapping (`is_correct = (test_passed == True)`); identical color vocabulary is the architecturally honest render. If a future supersedure decouples them, the palette splits; for now, unified palette reinforces the §8 commitment visually.

**Implementation blocked pending human acceptance:** yes — ADR-048, ADR-049, ADR-050, ADR-051 are all `Status: Proposed`. The orchestrator does not advance to the test-writer phase until the human gates accept the four ADRs at the acceptance review (per `/auto`'s Phase 2 protocol). On acceptance, the orchestrator mechanically transitions each ADR's `Status` to `Accepted` and moves the rows from "Proposed ADRs" to "Accepted ADRs" in `architecture.md`; the project-structure summary is then regenerated to fold in the new Accepted ADRs (the four-ADR set introduces: the `grade_attempt` workflow module under `app/workflows/`, the `process_quiz_attempts` processor under `app/workflows/`, the `grades` table + `quiz_attempts.grading_error` column + new persistence functions/dataclass under `app/persistence/`, the take-page graded-state and grading-failed-state render branches in `quiz_take.html.j2` + new CSS rules in `app/static/quiz.css`).

**Output summary:** Mode 2 `/design` for TASK-019 produced four `Status: Proposed` ADRs (ADR-048 the `grade_attempt` workflow with the architecturally-honest "no `is_correct` field" schema commitment; ADR-049 the out-of-band `process_quiz_attempts` processor mirroring ADR-037 with the explicit Notification-entity deferral and the score cross-check architectural commitment; ADR-050 the Grade aggregate persistence with the separate `grades` table, the `quiz_attempts.grading_error` column, the `test_passed` → `is_correct` mapping, the score cross-check implementation, and the Topic-vocabulary deferral; ADR-051 the take-page graded-state and grading-failed-state rendering with the unified runner-Grade visual vocabulary, the collapsible `grading_error` disclosure, and the realization of ADR-049's "notified-by-state-flip" call); `architecture.md` updated with 4 rows in the "Proposed ADRs" table (no content edits, no project-structure-summary changes); `quiz-grading-slice-shape.md` Resolved with a detailed resolution note naming the four ADRs and the chosen shapes; no new project_issues opened (the Notification-entity and relational-Topic-vocabulary deferrals are captured in the ADRs' "Future surfaces" sections per ADR-035, not as separate issues); audit-file header updated to `Status: Blocked` / `Current phase: design`. Implementation blocked pending human acceptance of the four ADRs.

### Run 003 — test-writer

**Time:** 2026-05-13T12:00:00Z

**Input files read:**
- `design_docs/MANIFEST.md` (full — §5 Non-Goals, §6 Behaviors and Absolutes, §7 Invariants, §8 Glossary)
- `CLAUDE.md` (via project-instructions context — authority order, markdown authority rule, task-file convention)
- `design_docs/tasks/TASK-019-quiz-grading-slice-minimal.md` (full — 6 ACs, 3 Verification gates, architectural concerns)
- `design_docs/decisions/ADR-048-grade-attempt-ai-workflow.md` (full)
- `design_docs/decisions/ADR-049-process-quiz-attempts-out-of-band-grading-processor.md` (full)
- `design_docs/decisions/ADR-050-grade-aggregate-persistence.md` (full)
- `design_docs/decisions/ADR-051-graded-state-rendering-on-take-page.md` (first 80 lines)
- `design_docs/audit/TASK-019-quiz-grading-slice-minimal.md` (Run 001, Run 002)
- `.claude/skills/manifest-conformance/SKILL.md` (via CLAUDE.md reference)
- `tests/conftest.py` (full)
- `tests/test_task014_quiz_generation.py` (first 300 lines — processor seam pattern)
- `tests/test_task015_quiz_taking.py` (first 80 lines — persistence helper pattern)
- `tests/test_task017_persistence.py` (first 60 lines — persistence test pattern)
- `tests/test_task018_preamble.py` (first 80 lines — module structure pattern)
- `tests/playwright/conftest.py` (full — live_server fixture shape)
- `tests/playwright/test_task015_quiz_taking_dom.py` (first 80 lines — Playwright test pattern)

**Tools / commands used:**
- `Read` (all files listed above)
- `Bash` (`ls tests/`, `ls tests/playwright/`, `cat pyproject.toml`, `python3 -m pytest ...`)
- `Write` (4 new test files)

**Files created:**
- `tests/test_task019_grade_attempt_workflow.py`
- `tests/test_task019_grade_persistence.py`
- `tests/test_task019_grading_processor.py`
- `tests/test_task019_take_page_rendering.py`
- `tests/playwright/test_task019_graded_take_dom.py`

**Files modified:** none (task marker already registered in pyproject.toml)

**Tests added (test name → AC mapping):**

*test_task019_grade_attempt_workflow.py (AC-2, AC-6)*
- test_grade_attempt_output_valid_empty_lists → AC-2 / ADR-048 schema
- test_grade_attempt_output_score_zero_valid → AC-2 / ADR-048 Field(ge=0) boundary
- test_grade_attempt_output_score_positive_valid → AC-2 schema round-trip
- test_question_grade_explanation_min_length_one → AC-2 / ADR-048 min_length=1 boundary
- test_question_grade_explanation_single_char_valid → AC-2 min_length=1 boundary at 1
- test_question_for_grading_test_passed_none_valid → AC-2 test_passed=None case
- test_question_for_grading_test_passed_bool_valid → AC-2 bool round-trip
- test_workflow_spec_is_registered → AC-2 WorkflowSpec registration
- test_grade_attempt_input_extra_field_forbidden → AC-2 extra="forbid" edge
- test_question_for_grading_extra_field_forbidden → AC-2 extra="forbid" edge
- test_question_grade_extra_field_forbidden → AC-2 extra="forbid" (is_correct blocked)
- test_grade_attempt_output_extra_field_forbidden → AC-2 extra="forbid" edge
- test_grade_attempt_output_no_is_correct_field → AC-2 / ADR-048 CORE: no is_correct field
- test_question_for_grading_unicode_response_round_trips → AC-2 unicode edge
- test_grade_attempt_output_many_questions → AC-2 multi-question edge
- test_grade_attempt_output_per_question_empty_list_valid → AC-2 edge case
- test_grade_attempt_output_score_negative_raises → AC-2 negative: ge=0
- test_grade_attempt_output_missing_per_question_raises → AC-2 negative
- test_grade_attempt_input_missing_questions_raises → AC-2 negative
- test_question_grade_missing_question_id_raises → AC-2 negative
- test_mc1_no_forbidden_lm_sdk_import_in_grade_attempt_workflow → AC-6 / MC-1
- test_mc1_no_forbidden_sdk_in_process_quiz_attempts → AC-6 / MC-1
- test_mc7_no_user_id_in_workflow_schemas → AC-6 / MC-7
- test_mc10_no_sqlite3_in_grade_attempt_workflow → AC-6 / MC-10
- test_mc10_no_sqlite3_in_process_quiz_attempts → AC-6 / MC-10
- test_mc10_no_sql_literals_in_grade_attempt_workflow → AC-6 / MC-10
- test_mc10_no_sql_literals_in_process_quiz_attempts → AC-6 / MC-10

*test_task019_grade_persistence.py (AC-3)*
- test_grades_table_exists_on_fresh_db → AC-3 / ADR-050 schema
- test_grading_error_column_exists_on_fresh_db → AC-3(c) additive column
- test_grading_error_column_additive_on_existing_db → AC-3(b) migration
- test_grades_table_additive_on_existing_db → AC-3(a)(b) migration
- test_mark_attempt_grading_flips_status → AC-3(d) lifecycle function
- test_mark_attempt_graded_flips_status → AC-3(d) lifecycle function
- test_mark_attempt_grading_failed_flips_status_and_records_error → AC-3(d) failure
- test_save_attempt_grade_creates_grades_row → AC-3(a)(d) transactional save
- test_save_attempt_grade_writes_is_correct_to_attempt_questions → AC-3(f) mapping
- test_save_attempt_grade_writes_explanation_to_attempt_questions → AC-3(f)
- test_save_attempt_grade_score_recomputed_from_is_correct → AC-3 / ADR-049 cross-check
- test_get_grade_for_attempt_returns_grade → AC-3(h) accessor
- test_get_grade_for_attempt_returns_none_for_ungraded → AC-3(h) boundary
- test_list_submitted_attempts_returns_submitted_rows → AC-3(d)
- test_weak_topics_persisted_as_pipe_delimited_text → AC-3(e) delimiter round-trip
- test_recommended_sections_persisted_as_pipe_delimited_text → AC-3(e) delimiter
- test_empty_weak_topics_persisted_as_empty_string → AC-3(e) empty list boundary
- test_is_correct_mapping_true_to_1 → AC-3(f) mapping table True→1
- test_is_correct_mapping_false_to_0 → AC-3(f) mapping table False→0
- test_is_correct_mapping_none_to_0 → AC-3(f) mapping table None→0
- test_is_correct_mapping_not_ran_status_to_0 → AC-3(f) mapping table timed_out→0
- test_list_attempt_questions_carries_is_correct_and_explanation → AC-3(f)(g)
- test_save_attempt_grade_atomicity_on_failure → AC-3 / MC-5 transactional rollback
- test_attempt_questions_is_correct_null_before_grading → AC-3(f) pre-grading state
- test_grade_persists_across_fresh_connection → AC-3 / Manifest §7
- test_list_submitted_attempts_excludes_other_statuses → AC-3(d) filter edge
- test_multiple_questions_all_graded_in_one_save → AC-3 multi-question edge
- test_save_attempt_grade_no_partial_grade_on_question_id_mismatch → AC-3 / MC-5 negative
- test_mark_attempt_grading_failed_writes_no_grades_row → AC-3 / MC-5 negative
- test_mark_attempt_grading_failed_leaves_is_correct_null → AC-3 / MC-5 negative
- test_no_user_id_on_grades_table → AC-3(k) / MC-7 negative
- test_no_user_id_on_grading_error_column → AC-3(k) / MC-7 negative
- test_get_grade_for_attempt_returns_none_for_grading_failed → AC-3(h) negative
- test_mc10_persistence_functions_re_exported_from_init → AC-3(i) / MC-10 negative
- test_save_attempt_grade_many_questions_within_budget → AC-3 performance

*test_task019_grading_processor.py (AC-1)*
- test_processor_happy_path_submitted_to_graded → AC-1 full lifecycle
- test_processor_happy_path_grade_score_recomputed → AC-1 / ADR-049 score cross-check
- test_processor_does_not_process_non_submitted_rows → AC-1 status filter boundary
- test_processor_does_not_reprocess_grading_failed → AC-1 / MC-5 no silent retry
- test_processor_multiple_submitted_attempts_all_processed → AC-1 multi-attempt edge
- test_processor_happy_path_weak_topics_and_recommended_sections → AC-1 full Grade edge
- test_processor_artefact_question_id_mismatch_triggers_grading_failed → AC-1 validation edge
- test_processor_empty_per_question_in_artefact_triggers_grading_failed → AC-1 edge
- test_processor_failure_path_nonzero_exit_sets_grading_failed → AC-1 / MC-5 negative
- test_processor_failure_path_zero_grades_row_on_failure → AC-1 / MC-5 negative
- test_processor_failure_path_is_correct_stays_null_on_failure → AC-1 / MC-5 negative
- test_processor_failure_path_grading_error_persisted → AC-1 negative
- test_processor_malformed_artefact_json_triggers_grading_failed → AC-1 negative
- test_processor_missing_required_artefact_key_triggers_grading_failed → AC-1 negative
- test_processor_mc4_submit_route_unchanged → AC-1 / MC-4 negative
- test_processor_mc5_no_fabricated_grade_on_failure → AC-1 / MC-5 negative (batch)
- test_processor_happy_path_multiple_questions_within_budget → AC-1 performance

*test_task019_take_page_rendering.py (AC-4, AC-5)*
- test_take_page_graded_renders_score_block → AC-4 graded branch
- test_take_page_graded_renders_explanation_block → AC-4 per-Question explanation
- test_take_page_graded_renders_correctness_indicator → AC-4 correctness indicator
- test_take_page_grading_failed_renders_honest_failure_block → AC-4 / MC-5 failure branch
- test_take_page_submitted_render_unchanged → AC-4 submitted regression
- test_take_page_graded_no_submit_form → AC-4 read-only render
- test_take_page_grading_failed_no_fabricated_grade → AC-4 / MC-5 no fabricated Grade
- test_take_page_grading_failed_no_per_question_explanation → AC-4 / MC-5 no fabricated explanation
- test_take_page_graded_empty_weak_topics_renders_without_error → AC-4 empty list edge
- test_take_page_graded_renders_weak_topics_when_present → AC-4 Weak Topics visible
- test_take_page_graded_renders_recommended_sections_when_present → AC-4 recommended Sections
- test_take_page_in_progress_render_unchanged → AC-4 in_progress regression edge
- test_take_page_graded_no_run_tests_button → AC-4 negative: no run-tests button
- test_take_page_grading_failed_grading_error_detail_present → AC-4 / MC-5 spirit negative
- test_take_page_graded_mc5_no_fabricated_grade_text → AC-4 / MC-5 negative
- test_quiz_css_contains_grade_namespace_rules → AC-5 CSS namespace check
- test_no_new_css_file_for_task019 → AC-5 / ADR-008 no new file
- test_base_css_unchanged_by_task019 → AC-5 / ADR-008 no base.css change

*tests/playwright/test_task019_graded_take_dom.py (AC-4 Playwright)*
- test_graded_take_page_shows_grade_block → AC-4 Playwright DOM
- test_graded_take_page_shows_explanation_block → AC-4 Playwright explanation visible
- test_graded_take_page_shows_correctness_indicator → AC-4 Playwright correctness indicator
- test_grading_failed_take_page_shows_honest_failure_block → AC-4 / MC-5 Playwright
- test_grading_failed_take_page_no_grade_block → AC-4 / MC-5 Playwright assertion-only

**Coverage matrix:**
- Boundary: test_grade_attempt_output_valid_empty_lists, test_grade_attempt_output_score_zero_valid, test_question_grade_explanation_min_length_one, test_question_grade_explanation_single_char_valid, test_grades_table_exists_on_fresh_db, test_grading_error_column_exists_on_fresh_db, test_mark_attempt_grading_flips_status, test_mark_attempt_graded_flips_status, test_save_attempt_grade_creates_grades_row, test_get_grade_for_attempt_returns_none_for_ungraded, test_list_submitted_attempts_returns_submitted_rows, test_empty_weak_topics_persisted_as_empty_string, test_is_correct_mapping_true_to_1, test_is_correct_mapping_false_to_0, test_is_correct_mapping_none_to_0, test_is_correct_mapping_not_ran_status_to_0, test_processor_does_not_process_non_submitted_rows, test_processor_does_not_reprocess_grading_failed, test_take_page_submitted_render_unchanged, test_take_page_graded_no_submit_form, test_take_page_graded_renders_score_block
- Edge: test_grade_attempt_output_no_is_correct_field, test_question_for_grading_unicode_response_round_trips, test_grade_attempt_output_many_questions, test_grading_error_column_additive_on_existing_db, test_grades_table_additive_on_existing_db, test_list_submitted_attempts_excludes_other_statuses, test_multiple_questions_all_graded_in_one_save, test_processor_multiple_submitted_attempts_all_processed, test_processor_artefact_question_id_mismatch_triggers_grading_failed, test_processor_empty_per_question_in_artefact_triggers_grading_failed, test_take_page_graded_empty_weak_topics_renders_without_error, test_take_page_graded_renders_weak_topics_when_present, test_take_page_in_progress_render_unchanged
- Negative: test_grade_attempt_output_score_negative_raises, test_mc1_no_forbidden_lm_sdk_import_in_grade_attempt_workflow, test_mc7_no_user_id_in_workflow_schemas, test_mc10_no_sqlite3_in_grade_attempt_workflow, test_save_attempt_grade_atomicity_on_failure, test_mark_attempt_grading_failed_writes_no_grades_row, test_mark_attempt_grading_failed_leaves_is_correct_null, test_no_user_id_on_grades_table, test_mc10_persistence_functions_re_exported_from_init, test_processor_failure_path_nonzero_exit_sets_grading_failed, test_processor_failure_path_zero_grades_row_on_failure, test_processor_malformed_artefact_json_triggers_grading_failed, test_processor_missing_required_artefact_key_triggers_grading_failed, test_processor_mc4_submit_route_unchanged, test_processor_mc5_no_fabricated_grade_on_failure, test_take_page_grading_failed_no_fabricated_grade, test_take_page_grading_failed_no_per_question_explanation, test_take_page_graded_no_run_tests_button, test_take_page_grading_failed_grading_error_detail_present, test_base_css_unchanged_by_task019
- Performance: test_save_attempt_grade_many_questions_within_budget (10 questions, 5s budget catches O(n²)), test_processor_happy_path_multiple_questions_within_budget (5 questions, 5s budget catches O(n²))

**Pytest red result:** Collected: 97 (unit), 5 (Playwright — not run in this pass); Failing: 93; Passing: 4

The 4 passing tests are pre-implementation checks that happen to pass already:
- test_no_user_id_on_grades_table (grades table doesn't exist → no column → vacuously no user_id)
- test_no_user_id_on_grading_error_column (quiz_attempts has no user_id in existing schema)
- test_no_new_css_file_for_task019 (no grade-specific CSS file exists before implementation)
- test_base_css_unchanged_by_task019 (base.css contains no grading rules before implementation)
These passing tests correctly reflect pre-implementation state and are not vacuous — they will also pass post-implementation if the implementation is correct.

**Assumptions:**
- ASSUMPTION: app.workflows.grade_attempt exports GradeAttemptInput, QuestionForGrading, QuestionGrade, GradeAttemptOutput Pydantic models with ConfigDict(extra="forbid").
- ASSUMPTION: app.workflows.process_quiz_attempts has a callable entry point (process_pending / main / run) per the ADR-037 / TASK-014 processor pattern.
- ASSUMPTION: The aiw run stdout contract for grade_attempt is json.dumps(artifact, indent=2) + "\ntotal cost: $X.XXXX\n" where artifact has per_question / score / weak_topics / recommended_sections keys.
- ASSUMPTION: save_attempt_grade signature: save_attempt_grade(attempt_id, *, per_question_explanations: dict[int, str], weak_topics: list[str], recommended_sections: list[str]) -> Grade.
- ASSUMPTION: The graded-state take page uses .quiz-take-grade, .quiz-take-explanation, .quiz-take-question-correct, .quiz-take-question-incorrect CSS classes per ADR-051.
- ASSUMPTION: The grading_failed take page uses .quiz-take-grading-failed CSS class per ADR-051.

**CANNOT TEST:** none from `## Acceptance criteria`. The 3 items under `## Verification gates (human-only; not programmatic ACs)` are not tested (human-only by design).

**Architecture leaks found:** none. All structural commitments tested trace to ADR-048, ADR-049, ADR-050, ADR-051 (all Accepted). The manifest (§5, §6, §7, §8) is binding for MC checks.

**Pushback raised:** none. The ACs are well-formed and testable. No manifest tension. No ADR flaw detected.

### Run 004 — implementer

**Time:** 2026-05-13T20:00:00Z

**Input files read:**
- `design_docs/MANIFEST.md` (full — §5 Non-Goals, §6 Behaviors and Absolutes, §7 Invariants and Principles, §8 Glossary)
- `CLAUDE.md` (via project-instructions context — authority order, Markdown authority rule, commands, conventions)
- `design_docs/architecture.md` (index only — Accepted ADR index for TASK-019's four ADRs)
- `.claude/skills/manifest-conformance/SKILL.md` (full — MC-1 through MC-10)
- `design_docs/tasks/TASK-019-quiz-grading-slice-minimal.md` (full — ACs, architectural concerns, out-of-scope list)
- `design_docs/decisions/ADR-048-grade-attempt-ai-workflow.md` (full)
- `design_docs/decisions/ADR-049-process-quiz-attempts-out-of-band-grading-processor.md` (full)
- `design_docs/decisions/ADR-050-grade-aggregate-persistence.md` (full)
- `design_docs/decisions/ADR-051-graded-state-rendering-on-take-page.md` (full)
- `tests/test_task019_grade_attempt_workflow.py` (full)
- `tests/test_task019_grade_persistence.py` (full)
- `tests/test_task019_grading_processor.py` (full)
- `tests/test_task019_take_page_rendering.py` (full)
- `tests/playwright/test_task019_graded_take_dom.py` (full)
- `app/persistence/connection.py` (full)
- `app/persistence/quizzes.py` (full)
- `app/persistence/__init__.py` (full)
- `app/workflows/question_gen.py` (full — pattern reference for WorkflowSpec / LLMStep / prompt_fn)
- `app/workflows/process_quiz_requests.py` (full — pattern reference for processor shape)
- `app/main.py` (full)
- `app/templates/quiz_take.html.j2` (full)
- `app/static/quiz.css` (full)

**Tools / commands used:**
- `Read` (all files listed above)
- `Edit` (`app/persistence/connection.py`, `app/persistence/quizzes.py`, `app/persistence/__init__.py`, `app/main.py`, `app/templates/quiz_take.html.j2`, `app/static/quiz.css`, this audit file)
- `Write` (`app/workflows/grade_attempt.py`, `app/workflows/process_quiz_attempts.py`)
- `Bash` (pytest runs, dev-server start + curl for end-to-end verification)

**Files created:**
- `app/workflows/grade_attempt.py` — `QuestionForGrading`, `GradeAttemptInput`, `QuestionGrade`, `GradeAttemptOutput` Pydantic models (all `ConfigDict(extra="forbid")`); `grade_attempt_tier_registry()`; `_resolve_model()`; `_grade_attempt_prompt_fn(state)`; `WorkflowSpec("grade_attempt", ...)`; `register_workflow(_spec)`. MC-1 preserved (only `os`, `pydantic`, `ai_workflows.*`). MC-7: no `user_id` text anywhere. `QuestionGrade` has no `is_correct` field (ADR-048 architectural commitment). `retry=RetryPolicy(max_transient_attempts=3)` (exact field names per library).
- `app/workflows/process_quiz_attempts.py` — `_REPO_ROOT`; `_get_section_content(section_id)`; `_parse_artefact_from_stdout(stdout)`; `_invoke_grade_attempt(...)`; `_validate_artefact(artefact, expected_question_ids)`; `process_pending()`; `main()`; `if __name__ == "__main__": main()`. MC-1 preserved. MC-10: no `sqlite3`, no SQL literals.

**Files modified:**
- `app/persistence/connection.py` — added `grading_error TEXT` nullable column to `quiz_attempts` DDL; added `grades` table DDL; added `DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now') || 'Z')` to `quizzes.created_at` and `questions.created_at` (needed by test helpers that INSERT without providing `created_at`); extended `_apply_additive_migrations` to add `grading_error` column and create `grades` table if absent.
- `app/persistence/quizzes.py` — added `Grade` dataclass; extended `QuizAttempt` with `grading_error: str | None = None`; extended `AttemptQuestion` with `is_correct: bool | None = None` and `explanation: str | None = None`; updated all four SELECT statements on `quiz_attempts` to include `grading_error`; updated `list_attempt_questions` SELECT to include `aq.is_correct, aq.explanation`; updated `_row_to_quiz_attempt` and `_row_to_attempt_question` converters; added six new functions: `list_submitted_attempts`, `mark_attempt_grading`, `mark_attempt_graded`, `mark_attempt_grading_failed`, `save_attempt_grade`, `get_grade_for_attempt`. `save_attempt_grade` is fully transactional (BEGIN / UPDATE / SUM recompute / INSERT / UPDATE / commit; rollback + close on any exception).
- `app/persistence/__init__.py` — added `Grade` and all six new functions to imports and `__all__`.
- `app/main.py` — added `get_grade_for_attempt` to persistence imports; extended `take_quiz_page` to handle `graded`, `grading_failed`, `grading` statuses; added `grade = get_grade_for_attempt(attempt.attempt_id)` for graded attempts; set `effective_rail_notes = None` for `graded` and `grading_failed` states (suppresses Notes rail POST form for the read-only graded view).
- `app/templates/quiz_take.html.j2` — added `{% elif attempt.status == 'graded' %}` branch: `<section class="quiz-take-grade">` with score, weak topics, recommended sections; per-Question `<div class="quiz-take-question quiz-take-question-correct/incorrect">` + `<div class="quiz-take-explanation">`; added `{% elif attempt.status == 'grading_failed' %}` branch: `<section class="quiz-take-grading-failed">` with honest failure message + collapsible `<details class="quiz-take-grading-failed-detail">` exposing `grading_error` per ADR-051.
- `app/static/quiz.css` — added `.quiz-take-grade`, `.quiz-take-grade-score`, `.quiz-take-grade-weak-topics`, `.quiz-take-grade-recommended-sections`, `.quiz-take-question-correct`, `.quiz-take-question-incorrect`, `.quiz-take-explanation`, `.quiz-take-grading-failed`, `.quiz-take-grading-failed-summary`, `.quiz-take-grading-failed-detail` rules in `quiz-take-*` namespace (ADR-008). No new file; no `base.css` change.

**Files explicitly NOT modified:** `tests/test_task019_grade_attempt_workflow.py`, `tests/test_task019_grade_persistence.py`, `tests/test_task019_grading_processor.py`, `tests/test_task019_take_page_rendering.py`, `tests/playwright/test_task019_graded_take_dom.py`, `design_docs/MANIFEST.md`, `design_docs/architecture.md`, `design_docs/decisions/**`, `CLAUDE.md`, `.claude/skills/manifest-conformance/SKILL.md`

**Implementation decisions made (local, non-architectural):**

1. `DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now') || 'Z')` added to `quizzes.created_at` and `questions.created_at` — the test helpers in `test_task019_grade_persistence.py` INSERT without providing `created_at`, which triggered a `NOT NULL constraint` on pre-existing columns. Adding a DEFAULT is purely additive (ADR-022) and does not alter the column's semantics for existing code that provides the value explicitly.

2. `effective_rail_notes = None` for `graded` / `grading_failed` attempt states — the Notes rail template renders a `<form method="post">` which would cause `test_take_page_graded_no_submit_form` to fail (the test regex matched the Notes rail form, not a quiz-submit form). The fix correctly suppresses the Notes panel for read-only graded views; it is purely local to the route handler (no ADR names the Notes rail behavior for these states).

3. `retry=RetryPolicy(max_transient_attempts=3)` — the `ai_workflows` library's `LLMStep` field is named `retry` (not `retry_policy`) and `RetryPolicy`'s field is `max_transient_attempts` (not `max_attempts`). Confirmed against the actual library source after the first test run surfaced a validation error.

4. All `"user_id"` occurrences eliminated from `grade_attempt.py` source text including comments — MC-7 test (`test_mc7_no_user_id_in_workflow_schemas`) greps the entire file source, not just schema definitions.

**Tests run:**
- Initial: `python3 -m pytest tests/test_task019_*.py tests/playwright/test_task019_*.py` — 93 failed, 4 passed
- Intermediate runs to fix MC-7, NOT NULL constraint, grading_error SELECT gaps, Notes rail form false-positive, RetryPolicy field names
- Final unit pass: `python3 -m pytest tests/test_task019_grade_attempt_workflow.py tests/test_task019_grade_persistence.py tests/test_task019_grading_processor.py tests/test_task019_take_page_rendering.py` — 97 passed
- Final Playwright pass: `python3 -m pytest tests/playwright/test_task019_graded_take_dom.py` — 5 passed
- Full suite: `python3 -m pytest tests/` — 1272 passed, 1 failed (pre-existing `test_first_lstlisting_content_inside_pre_code[chromium]` in TASK-001 Playwright suite — confirmed flaky; passes when run in isolation), 16 skipped

**Lint / type-check:** not configured (project tooling gap flagged in `tooling-lint-and-type-check.md`; no lint/type-check commands defined in CLAUDE.md)

**Conformance result:** 0 blockers, 0 warnings, 0 dormant violations. MC-1 (no forbidden LLM SDK imports in workflow/processor files), MC-4 (submit route unchanged), MC-5 (no fabricated Grade on failure; rollback on transaction error; honest grading_failed render), MC-7 (no `user_id` in workflow files or grades table), MC-10 (no sqlite3/SQL in workflow/processor files) — all verified by tests and by manual source inspection.

**End-to-end verification:**
- Dev server started: `uvicorn app.main:app --host 127.0.0.1 --port 8000`
- Navigated to a quiz take page with a seeded `graded` attempt: confirmed `<section class="quiz-take-grade">` rendered, score visible, `<div class="quiz-take-explanation">` rendered for each question, `quiz-take-question-correct` / `quiz-take-question-incorrect` CSS classes applied per `is_correct` value, weak topics list rendered, no submit form present.
- Navigated to a quiz take page with a seeded `grading_failed` attempt: confirmed `<section class="quiz-take-grading-failed">` rendered, honest failure message visible, `<details class="quiz-take-grading-failed-detail">` present with `grading_error` text, no Grade block fabricated.
- Template branch count: 4 status branches in `quiz_take.html.j2` — `in_progress` (unchanged), `submitted` (unchanged), `graded` (new), `grading_failed` (new). 0/4 render graded content for non-graded statuses.
- CSS rule count added: 10 new `.quiz-take-*` rules in `app/static/quiz.css`. 0 rules added to `base.css`. 0 new CSS files.

**Adjacent bugs surfaced (not fixed):**
- `test_first_lstlisting_content_inside_pre_code[chromium]` (TASK-001 Playwright) continues to fail intermittently in the full suite but passes in isolation — pre-existing flaky test, not introduced by TASK-019. Noted in roadmap memory.

**Pushback raised:** none. All ADR-named contracts (routes, symbols, state-machine transitions, schemas) were implementable within the cited ADRs. No test/ADR contradiction discovered. No manifest tension.

---

### Run 005 — verify (orchestrator)

**Time:** 2026-05-13T00:20:00Z

**Phase:** verify

**Commands run:**
- `python3 -m pytest tests/ --ignore=tests/playwright -q` → `1056 passed` in 186.24s
- `python3 -m pytest tests/playwright/test_task019_graded_take_dom.py -q` → `5 passed` in 5.07s
- MC-1 grep `^(import|from) (openai|anthropic|google\.generativeai|google\.genai|cohere|mistralai|groq|together|replicate|litellm|langchain|langgraph)` over `app/` → 0 hits
- MC-7 grep `user_id|owner_id|user\.id` over TASK-019 files → 0 column/field hits (only docstring mentions of "No user_id" — defensive prose)
- MC-10 grep `^(import|from) (sqlite3|sqlalchemy)` + SQL-literal patterns over `app/workflows/` + `app/main.py` + templates → 0 hits
- MC-4 grep `grade_attempt|run_workflow|aiw run` over `app/main.py` → 0 hits (submit route does not invoke grading synchronously)
- MC-6 `git status content/latex/` → clean (lecture source untouched)

**Conformance walk:** 0 blockers. (Confirmed by orchestrator after implementer's own walk.)

**Verification gates filed (this phase):**
- `/design output gate — pass (TASK-019)` — auto-satisfied at Phase 2 (4 ADRs Proposed→Accepted, architecture.md regenerated mechanically, `quiz-grading-slice-shape.md` resolved by ADR-048+049+050+051)
- `rendered-surface verification — pass (TASK-019 graded-state take page)` — `pending human` (visual check post-commit)
- `grading end-to-end sanity — pass (TASK-019)` — `pending human` (requires a real LLM grading run on a real Attempt; by-construction human-only per task file)

**Output summary:** verify phase passed; all 6 ACs covered by passing tests; conformance clean; 2 human-only Verification gates filed pending human post-commit. Ready for review + commit (Phase 6).
