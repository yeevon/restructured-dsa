# ADR-033: Quiz domain schema — `quizzes` / `questions` / `quiz_questions` / `quiz_attempts` / `attempt_questions` under `app/persistence/quizzes.py`, in the shared `data/notes.db`, with ADR-022's migration story; Topic tags as a delimited TEXT column (the `topics` table deferred to the generation task)

**Status:** `Accepted`
Auto-accepted by /auto on 2026-05-11
**Date:** 2026-05-11
**Task:** TASK-013
**Resolves:** none (no project_issue was filed against the Quiz schema question; it is forced inline by TASK-013, and ADR-022 §Future-cohabitation pre-positioned the package + the single-shared-DB rule and explicitly deferred "the Quiz/Attempt/QuestionBank/Notification schemas — owned by Quiz-bootstrap ADRs" — this ADR fills that in)
**Supersedes:** none — this ADR *adds* under ADR-022's umbrella; ADR-022 pre-positioned the `app/persistence/` package boundary, the cohabitation rule (single shared `data/notes.db`), and the migration story, but not the Quiz columns. No prior ADR is re-decided.
**Superseded by:** none

## Context

TASK-013 ships the first vertical slice of the Quiz pillar — the Quiz domain model + a per-Section Quiz read surface — with Quiz *generation* (the `ai-workflows` integration, async delivery, Notification, and the replay-+-fresh composition) explicitly deferred to the next task(s). Manifest §3 / §7 make the reinforcement loop the reason the project exists; this slice lays the schema the loop is built on. ADR-022 (Accepted, 2026-05-10) committed to one shared SQLite database under `data/notes.db`, each persisted entity owning its own module under `app/persistence/`, with `CREATE TABLE IF NOT EXISTS` schema bootstrap and a "first non-additive change forces a follow-up ADR" migration story; ADR-022 §Future-cohabitation forecast the module list `quizzes.py`, `attempts.py`, `question_bank.py`, `notifications.py`, `topics.py` and said the Quiz schemas are "owned by Quiz-bootstrap ADRs." ADR-024 (Accepted, 2026-05-10) is the first concrete validation of that cohabitation rule (the `section_completions` table + `app/persistence/section_completions.py`) — the per-entity-module pattern this ADR mirrors. ADR-002 fixes the Section ID string form (`{chapter_id}#section-{n-m}`), which is what the Quiz/Question `section_id` columns store; Sections are filesystem-derived (ADR-001), not a persisted entity, so `section_id` is TEXT validated at the route handler, not an FK (the same convention ADR-022 uses for Notes' `chapter_id` and ADR-024 uses for `section_completions.section_id`).

This ADR is forced now because: (a) TASK-013's read surface needs tables to read; (b) the schema-churn risk — the Question↔Topic relationship, the Grade entity, the per-Question correctness structure — has downstream cost if the wrong call forces a non-additive migration in the generation/grading task (ADR-022's migration story tolerates *additive* changes only), so the schema must be designed for additive extensibility; (c) the per-Section Quiz surface placement ADR (ADR-034) and the placeholder Quiz-trigger affordance need a table to write a `requested`-status Quiz row into.

The decision space has materially different alternatives:

- **Table set / how Question↔Quiz membership is modelled:** a `quiz_questions` join table (a Question may appear in multiple Quizzes for its Section over time — manifest §8) vs a `quiz_id` FK column on `questions` (which forecloses multi-Quiz membership) vs no `questions` table at all this task (defer the Question Bank entirely).
- **Where generation-status and grading-status live:** one combined `status` enum on one table; a `quizzes.status` (generation lifecycle) + a `quiz_attempts.status` (attempt/grading lifecycle) split; status as a separate `quiz_events` log.
- **Per-Question correctness / responses:** an `attempt_questions` join table now (one row per Question per Attempt, carrying response + correctness + explanation, the last two NULL until grading); a JSON/TEXT blob column on `quiz_attempts`; stub it entirely for the grading task.
- **Topic tags on Questions:** a delimited TEXT column on `questions` (`topics TEXT`, e.g. `"hashing|collision-resolution"`); a `question_topics` join table referencing a `topics` table; a `question_topics` join with free-text `topic` values and no `topics` table.
- **The Grade aggregate (score, Weak Topics, recommended Sections — manifest §8):** ship a `grades` table now; ship score/weak-topics columns on `quiz_attempts` now; defer the aggregate entirely (it has no consumer until grading exists).
- **The Notification entity (manifest §8):** ship a `notifications` table stub now (ADR-022 forecasts it); defer to the async-delivery task.
- **Migration mechanics:** extend `_SCHEMA_SQL` in `connection.py` (ADR-024's choice, validated at 2 tables) vs a per-module schema-fragment-registration pattern.
- **Foreign-key enforcement:** declare `REFERENCES` clauses and enable `PRAGMA foreign_keys = ON`; declare `REFERENCES` for documentation only (SQLite ignores them without the pragma); no `REFERENCES` clauses at all.

The manifest constrains the decision through §5 ("No cross-Section Quizzes. A Quiz scope is one Section" — `quizzes.section_id NOT NULL`, no Chapter-bound Quiz row, no aggregation-across-Sections row; "No non-coding Question formats … Every Question is a hands-on coding task" — the `questions` table carries a coding-task prompt and Topic tags, no `option_*` / `correct_choice` / `answer_text` / `describe_*` / `recall_*` columns; "No live / synchronous AI results … surfaced via Notification" — the lifecycle enums *name* the async states the generation/grading tasks will drive, but this task introduces no AI call; "No LMS gradebook export"; "No multi-user"), §6 ("Quizzes scope to Sections; Lectures and Notes scope to Chapters. Per-Chapter quiz aggregations, if ever surfaced, are computed from per-Section results. There is no Chapter-bound Quiz entity"; "AI work is asynchronous"; "AI failures are visible … never fabricates a result"; "Single-user"; "Lecture source read-only"), §7 ("A Quiz is bound to exactly one Section"; "Every Question is a hands-on coding task"; "Every post-first Quiz for a Section contains both replayed wrong-answer Questions and freshly-generated Questions … The first Quiz for a Section contains only fresh Questions" — the schema must leave room for both the replay portion (per-Question wrong-answer history) and the fresh portion (Weak-Topic-targeted generation) without a non-additive migration; "Quiz generation is always explicitly user-triggered"; "Every Quiz Attempt … persists across sessions"), §8 glossary (Quiz, Question, Question Bank, Quiz Attempt, Grade, Weak Topic, Notification — all consumed; "Topics form a project-wide vocabulary maintained alongside Chapter content" — bears on the Topic-tags decision).

## Decision

### Table set — `quizzes`, `questions`, `quiz_questions`, `quiz_attempts`, `attempt_questions`; the Grade aggregate and the `notifications` table deferred (additive later)

The Quiz domain gets five tables, all created via `CREATE TABLE IF NOT EXISTS` appended to `app/persistence/connection.py`'s `_SCHEMA_SQL` block (ADR-022's migration story; ADR-024's mechanic):

```sql
-- A Quiz: scoped to exactly one Section (manifest §5/§6/§7, MC-2).
-- A Quiz row exists from the moment the user requests one; its Questions are
-- populated (via quiz_questions) when generation completes and status reaches 'ready'.
CREATE TABLE IF NOT EXISTS quizzes (
    quiz_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    section_id TEXT    NOT NULL,            -- full ADR-002 composite ID, e.g. "ch-03-...#section-3-2"
    status     TEXT    NOT NULL DEFAULT 'requested',
                                            -- generation lifecycle, see §Lifecycle enums:
                                            -- 'requested' | 'generating' | 'ready' | 'generation_failed'
    created_at TEXT    NOT NULL             -- ISO-8601 UTC
);
CREATE INDEX IF NOT EXISTS idx_quizzes_section_id ON quizzes (section_id);

-- The Question Bank for a Section: every Question ever generated for that Section
-- (manifest §8 "never deleted; only superseded by content reorganization").
-- Every Question is a hands-on coding task (manifest §5/§7): a prompt and Topic tags;
-- NO choice/recall/describe columns.
CREATE TABLE IF NOT EXISTS questions (
    question_id INTEGER PRIMARY KEY AUTOINCREMENT,
    section_id  TEXT    NOT NULL,           -- the Section whose Question Bank this belongs to
    prompt      TEXT    NOT NULL,           -- the coding-task prompt (what to implement)
    topics      TEXT    NOT NULL DEFAULT '',-- '|'-delimited Topic-tag list, see §Topic tags
    created_at  TEXT    NOT NULL            -- ISO-8601 UTC
);
CREATE INDEX IF NOT EXISTS idx_questions_section_id ON questions (section_id);

-- Membership: which Questions a Quiz is composed of, and in what order.
-- A Question MAY appear in multiple Quizzes for its Section over time (manifest §8) —
-- this is a many-to-many join, NOT a quiz_id FK on questions.
CREATE TABLE IF NOT EXISTS quiz_questions (
    quiz_id     INTEGER NOT NULL REFERENCES quizzes (quiz_id),
    question_id INTEGER NOT NULL REFERENCES questions (question_id),
    position    INTEGER NOT NULL,           -- 1-based order of this Question within this Quiz
    PRIMARY KEY (quiz_id, question_id)
);
CREATE INDEX IF NOT EXISTS idx_quiz_questions_question_id ON quiz_questions (question_id);

-- A Quiz Attempt: one submission of a Quiz by the user (manifest §8).
-- Created when the learner starts taking a 'ready' Quiz (a later task).
-- 'status' names the async-grading lifecycle INCLUDING a failure state (MC-5).
CREATE TABLE IF NOT EXISTS quiz_attempts (
    attempt_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    quiz_id      INTEGER NOT NULL REFERENCES quizzes (quiz_id),
    status       TEXT    NOT NULL DEFAULT 'in_progress',
                                            -- attempt/grading lifecycle, see §Lifecycle enums:
                                            -- 'in_progress' | 'submitted' | 'grading' | 'graded' | 'grading_failed'
    created_at   TEXT    NOT NULL,          -- ISO-8601 UTC (Attempt started)
    submitted_at TEXT,                      -- ISO-8601 UTC, NULL until submitted
    graded_at    TEXT                       -- ISO-8601 UTC, NULL until graded
);
CREATE INDEX IF NOT EXISTS idx_quiz_attempts_quiz_id ON quiz_attempts (quiz_id);

-- Per-Question state within an Attempt: the learner's response and (once graded)
-- the per-Question correctness + explanation. This is the structure that makes
-- wrong-answer-replay history exist (MC-8): a Question with is_correct = 0 in any
-- Attempt is a replay candidate for the next Quiz of its Section.
CREATE TABLE IF NOT EXISTS attempt_questions (
    attempt_id  INTEGER NOT NULL REFERENCES quiz_attempts (attempt_id),
    question_id INTEGER NOT NULL REFERENCES questions (question_id),
    response    TEXT,                       -- the learner's code, NULL until they answer
    is_correct  INTEGER,                    -- 0 | 1, NULL until graded (manifest §8 "per-Question correctness")
    explanation TEXT,                       -- per-Question grading explanation, NULL until graded (manifest §8)
    PRIMARY KEY (attempt_id, question_id)
);
CREATE INDEX IF NOT EXISTS idx_attempt_questions_question_id ON attempt_questions (question_id);
```

**Why these five and not more/fewer:**

- **`quizzes` with `section_id NOT NULL`** is the MC-2 / §6 / §7 commitment in schema form: every Quiz references exactly one Section; there is no `chapter_id`-only Quiz row, no aggregation row. Per-Chapter quiz aggregations, "if ever surfaced, are computed from per-Section results" (§6) — they are a query (`GROUP BY` over `quizzes.section_id`'s Chapter prefix, or over the discovered Section list), never a stored entity.
- **`questions`** is the Question Bank (§8). It is per-Section (`section_id`), carries a coding-task `prompt` and `topics` tags, and is never deleted — there is **no delete path** for `questions` rows in `app/persistence/quizzes.py` this task or any forecasted task, mirroring ADR-024's "the Question Bank is never deleted; enforced by the absence of a delete path" posture. (If `PRAGMA foreign_keys = ON` is enabled — see below — the `REFERENCES` clauses on `quiz_questions` / `attempt_questions` additionally prevent a `questions` row from being deleted while it is referenced; but the primary guarantee is "no code deletes Questions.")
- **`quiz_questions`** is a many-to-many join (PK `(quiz_id, question_id)`, plus a `position` column for order). This is the §8 "May appear in multiple Quizzes for its Section over time" requirement. A `quiz_id` FK column on `questions` is *rejected* — it would make a Question belong to exactly one Quiz forever, foreclosing the loop's replay portion (a replayed Question is, by definition, in a later Quiz than the one it was first answered wrong in).
- **`quiz_attempts`** is the Quiz Attempt entity (§8) with a `status` enum that *names* a failure state (`grading_failed`) — so the future grading task surfaces an AI failure as a failure (MC-5 / §6) rather than fabricating a Grade. `submitted_at` / `graded_at` are NULL until those lifecycle events occur (the same nullable-timestamp pattern ADR-022 uses for `notes.updated_at`).
- **`attempt_questions`** carries the learner's `response` (NULL until answered) and the per-Question `is_correct` + `explanation` (NULL until graded). Shipping this *now* — rather than a JSON blob on `quiz_attempts` or a stub for the grading task — is the schema-churn mitigation the task asked for: the grading task `UPDATE`s these columns; the replay-composition task `SELECT`s `question_id` where `is_correct = 0`; neither has to re-decide the structure. The Grade's per-Question portion (correctness + explanation, §8) lives here.

**Deferred, additive later (architecture-on-spec test applied — these have no consumer until grading/async-delivery exists):**

- **The Grade *aggregate* — score, identified Weak Topics, recommended Sections to re-read (§8).** Deferred to the grading task. When it lands, it adds either a `grades` table (PK `attempt_id`, FK to `quiz_attempts`, plus `score`, `weak_topics TEXT`, `recommended_sections TEXT`) or nullable columns on `quiz_attempts` (`score`, `weak_topics`, `recommended_sections`) — both are `CREATE TABLE IF NOT EXISTS` / `ALTER TABLE ADD COLUMN` (nullable), i.e., additive, i.e., they do not fire ADR-022's migration trigger. Shipping it now would be a table nothing writes to.
- **The `notifications` table (§8).** Deferred to the async-delivery task. ADR-022 forecasts it; this ADR's lifecycle enums do *not* reference it (a `quizzes.status = 'ready'` row and a `quiz_attempts.status = 'graded'` row are the facts a future Notification scaffolding reads — the Notification entity is a *projection* of those facts, not a precondition for them). A `notifications` table stub now would be borderline architecture-on-spec; this ADR declines it.
- **The optional `notes.section_id` column** (ADR-022 §Schema deferred it) — unrelated to Quizzes; not touched here.

### Lifecycle enums — two separate enums, each naming a failure state

There are two distinct lifecycles, and conflating them into one column would be wrong:

- **`quizzes.status` — the *generation* lifecycle:** `requested` → `generating` → `ready` → `generation_failed`.
  - `requested` — the user clicked "Generate a Quiz for this Section"; the row is a recorded user request. **No AI call has been made.** (This is the status the TASK-013 placeholder Quiz-trigger affordance, per ADR-034, writes — see §The `requested` status below.)
  - `generating` — the `ai-workflows` generation workflow is running (a later task).
  - `ready` — generation succeeded; `quiz_questions` rows now exist; the learner can take this Quiz (a later task).
  - `generation_failed` — generation failed; surfaced as a failure (MC-5); no fabricated Questions.
- **`quiz_attempts.status` — the *attempt + grading* lifecycle:** `in_progress` → `submitted` → `grading` → `graded` → `grading_failed`.
  - `in_progress` — the learner is taking the Quiz (a later task creates this row).
  - `submitted` — the learner submitted their responses; `attempt_questions.response` is populated; grading not yet started.
  - `grading` — the `ai-workflows` grading workflow is running (a later task).
  - `graded` — grading succeeded; `attempt_questions.is_correct` / `.explanation` are populated; the Grade aggregate (deferred) is recorded.
  - `grading_failed` — grading failed; surfaced as a failure (MC-5); no fabricated Grade.

Both enums are stored as TEXT (no SQLite `CHECK` constraint enforcing the value set — adding a `CHECK` later, or changing the value set, would be a non-additive migration; ADR-022's posture is to keep the schema additive-extensible, and the persistence module's public functions are the practical enforcement point, the same way ADR-024's `action ∈ {mark, unmark}` is enforced at the route handler, not in the schema). Adding a new lifecycle state later (e.g., a `quizzes.status = 'queued'` if the generation task wants a queue) is purely additive — a new permitted string value, no DDL change. The exact spelling of the states is implementer-followable from this ADR; the generation/grading tasks may *add* states but may not *remove or rename* them without a superseding ADR.

### The `requested` status — how the TASK-013 placeholder Quiz-trigger affordance uses it

Per ADR-034 (the per-Section Quiz surface placement ADR), TASK-013 ships a **real** user-triggered route — `POST /lecture/{chapter_id}/sections/{section_number}/quiz` — that inserts one `quizzes` row with `status = 'requested'`, `section_id = {chapter_id}#section-{n-m}` (validated at the route handler against the parsed Section set, exactly as ADR-024 validates `section_completions.section_id`), `created_at = <now>`, and **no** `quiz_questions` rows and **no** `quiz_attempts` row. No AI call is made (MC-1); no background job is started (MC-9 — the route fires only on the explicit user click); nothing is fabricated (MC-5 — a `requested`-status row is honestly "we recorded your request to generate a Quiz," not a Grade or a Question or a finished Quiz). The downstream processing of `requested`-status Quizzes — the `ai-workflows` generation workflow that walks them to `generating` → `ready` — is explicitly the **next task's** job; this task creates the row and leaves it there.

The per-Section Quiz read surface (ADR-034) renders these rows honestly: with zero Quizzes for a Section, an empty-state caption; with one or more, a list of each Quiz's status in plain language (`requested` → "Requested — generation pending"; never "Quiz ready" or a takeable affordance until the row reaches `ready`, which no TASK-013 path produces). MC-5's "never fabricated" obligation is honored: the surface never presents a `requested` Quiz as a finished one.

### Topic tags — a `'|'`-delimited TEXT column on `questions` now; the `topics` table + `question_topics` join deferred to the generation task

`questions.topics` is a `'|'`-delimited string of Topic-tag names (`""` when empty; e.g. `"hashing|collision-resolution|load-factor"`). The persistence module exposes Topic tags to callers as a `list[str]` (split on `'|'`, empty list when the column is `''`) — callers never see the raw delimited string, the same way they never see a raw `sqlite3.Row`.

**Why the cheap form now, not a `topics` table + join:**

- The schema ADR has to decide *somewhere* for Question Topic tags to live anyway (TASK-013 ships the `questions` table). The question is whether the cheap delimited-TEXT form is *genuinely worse* than a `topics` table + `question_topics` join — and it is not, because the migration from the cheap form to the relational form is **additive (clean)**: when the generation task wants Topics as first-class entities (for Weak-Topic identification — §8: "Topics form a project-wide vocabulary maintained alongside Chapter content"), it does (1) `CREATE TABLE IF NOT EXISTS topics (...)`, (2) `CREATE TABLE IF NOT EXISTS question_topics (...)`, (3) backfill `question_topics` rows by splitting each `questions.topics` value — a *data* migration (read-transform-write inside the persistence package), **not** a schema change, so it does **not** fire ADR-022's "first non-additive change" trigger. Step 4 (dropping `questions.topics`) is optional and *the only* non-additive piece — and even that is avoidable (leave `questions.topics` as a denormalized cache, or simply stop reading it). Net: deferring Topics costs nothing in migration pain.
- §8 says Topics are "maintained alongside Chapter content" — i.e., a *curriculum* artifact, sourced like the LaTeX corpus, not a Quiz artifact. Shipping a `topics` table *now* (with no source, no curriculum-side maintenance path, and nothing reading it) would be exactly the architecture-on-spec anti-pattern the project's task discipline has rejected for Topics three times (TASK-009 → TASK-012). The right home for the Topic-vocabulary decision is the task that has a behavioral consumer — the generation task, whose `/design` decides the source shape (`content/`-derived? a Python module? a `topics` table seeded from a source?) and the read path, with the `questions.topics` column migrated into `question_topics` rows at that point.

So: **no separate Topic-vocabulary ADR is created by TASK-013.** This section *is* the Topic decision: ship `questions.topics TEXT` now; defer the `topics` table + `question_topics` join + the Topic-vocabulary-source decision to the generation task's `/design`. The generation task's `/design` may file a project_issue or just decide it inline; either is fine. (No `project_issue` is filed by this ADR — the question is squarely the generation task's to resolve and is not "unresolved and homeless"; it has a named home.)

### Module path and public API — `app/persistence/quizzes.py`, re-exported by `app/persistence/__init__.py`

A new module `app/persistence/quizzes.py` joins the persistence package alongside `notes.py`, `section_completions.py`, and `connection.py`. It owns all SQL string literals and parameter binding for the Quiz domain (all five tables); it does **not** consult the filesystem (Section validation is the route handler's job, per ADR-024's split). Initial public API (re-exported by `app/persistence/__init__.py`, single import surface per ADR-022; TASK-013 needs only a subset — the read accessor and the `requested`-row creator — the rest are forecast and may be added incrementally by later tasks rather than all stubbed now):

```python
@dataclass
class Quiz:
    quiz_id: int
    section_id: str
    status: str          # 'requested' | 'generating' | 'ready' | 'generation_failed'
    created_at: str

@dataclass
class Question:
    question_id: int
    section_id: str
    prompt: str
    topics: list[str]    # split from the '|'-delimited column; [] when empty
    created_at: str

# --- TASK-013 needs these ---
def request_quiz(section_id: str) -> Quiz: ...
    # INSERT a quizzes row with status='requested', created_at=<now>; return it.
def list_quizzes_for_section(section_id: str) -> list[Quiz]: ...
    # SELECT * FROM quizzes WHERE section_id = ? ORDER BY created_at DESC.
def list_quizzes_for_chapter(chapter_id: str) -> dict[str, list[Quiz]]: ...
    # bulk accessor: {section_id: [Quiz, ...]} for every Section of the Chapter
    # that has >=1 Quiz — mirrors count_complete_sections_per_chapter() (ADR-026)
    # / list_complete_section_ids_for_chapter() (ADR-024) so render_chapter does
    # one query per request, not one per Section. (Implementation may match on the
    # 'chapter_id#%' prefix of section_id, or take the parsed Section-id list from
    # the caller — implementer's choice; either keeps SQL in the persistence package.)

# --- forecast; later tasks add as needed (not all stubbed in TASK-013) ---
# def add_questions_to_quiz(quiz_id, questions) -> None      # generation task
# def list_questions_for_quiz(quiz_id) -> list[Question]     # quiz-taking task
# def list_question_bank_for_section(section_id) -> list[Question]  # replay-composition task
# def create_attempt(quiz_id) -> QuizAttempt                 # quiz-taking task
# def record_response(attempt_id, question_id, response) -> None    # quiz-taking task
# def record_grade(attempt_id, per_question, ...) -> None    # grading task
```

Module shape mirrors `notes.py` / `section_completions.py`: `from __future__ import annotations`; dataclasses per row; a private `_utc_now_iso()` helper duplicated from the sibling modules (ADR-024's "two implementations of a 2-line function is not a real DRY violation" stands — if a fourth entity module needs it, *that* is the moment to factor it out; this ADR does not introduce shared-helper infrastructure); all connections opened/used/closed within a `try ... finally` per the established pattern; no long-lived connection state. SQL string literals appear only in this file (MC-10).

### Schema bootstrap — extend `_SCHEMA_SQL` in `connection.py`; recommend `PRAGMA foreign_keys = ON`

The five tables' DDL is appended to the existing `_SCHEMA_SQL` string in `app/persistence/connection.py` (ADR-024's mechanic; ADR-022's migration story). This pushes `_SCHEMA_SQL` from ~17 lines to ~55 lines — still tractable as one string, but this is the n-tables threshold ADR-024 flagged ("if at three or four tables the centralized string becomes unwieldy, a future ADR can introduce a per-module schema-fragment-registration pattern"). This ADR does **not** introduce that pattern (it is still a readable string, and a refactor that adds module-import-order considerations and a "forgot to register" failure mode is not justified yet) — but it explicitly notes that the *next* persistence-touching task may legitimately propose it, and that doing so is a pure code reorganization that does **not** fire ADR-022's migration trigger (the DDL outputs are unchanged).

Because the Quiz domain has real inter-table references (unlike `notes` / `section_completions`, which FK nothing because Chapters/Sections are filesystem-derived), this ADR **recommends** the implementer enable SQLite foreign-key enforcement by adding `conn.execute("PRAGMA foreign_keys = ON")` in `get_connection()` (SQLite ignores `REFERENCES` clauses without it). This is a low-risk additive change: `notes` and `section_completions` have no `REFERENCES` clauses, so the pragma is a no-op for them; for the Quiz tables it makes the `REFERENCES` clauses actually prevent dangling `quiz_questions` / `attempt_questions` rows. If the implementer judges the pragma adds friction (e.g., a test that relied on inserting an orphan row), the `REFERENCES` clauses still serve as self-documentation and the "Question Bank never deleted" guarantee still holds via "no delete path exists" — so the pragma is a recommendation, not a hard requirement of this ADR. (A test for "a `quiz_questions` row cannot reference a nonexistent `quiz_id` when the pragma is on" is welcome but not required.)

### `ai-workflows` is NOT touched by this ADR

This ADR introduces no `ai-workflows` dependency, no workflow module path, no build/serve story for AI work, no AI call (not even stubbed). The lifecycle enums *name* the async-generation and async-grading states the future `ai-workflows` integration will drive — that is **schema design** (so the generation/grading tasks add behavior without a non-additive migration), **not** an AI-integration decision. MC-1's architecture portion (the forbidden-SDK list, the workflow module path) stays `cannot evaluate (ADR pending)` — the AI-engine ADR is the *next* task's job. The `requested`-status row the TASK-013 placeholder trigger creates is a recorded user request that *nothing in TASK-013 processes*; its processor is the next task.

### Scope of this ADR

This ADR fixes only:

1. The Quiz-domain table set (`quizzes`, `questions`, `quiz_questions`, `quiz_attempts`, `attempt_questions`) and the columns committed above — `quizzes.section_id NOT NULL`; no Chapter-bound Quiz row; no aggregation row; no `user_id` anywhere; no choice/recall/describe columns on `questions`; per-Question correctness recordable via `attempt_questions`; multi-Quiz Question membership via the `quiz_questions` join.
2. The two lifecycle enums (`quizzes.status` generation lifecycle; `quiz_attempts.status` attempt/grading lifecycle), each naming a failure state, stored as TEXT, additive-extensible.
3. The Topic-tags decision: `questions.topics` as a `'|'`-delimited TEXT column now; the `topics` table + `question_topics` join + the Topic-vocabulary-source decision deferred to the generation task's `/design` (no separate ADR, no project_issue — the question has a named home).
4. The `requested`-status row as the persistence shape behind the TASK-013 placeholder Quiz-trigger affordance (the route + template shape is ADR-034's; this ADR fixes only the row it writes and the no-AI / no-fabrication / honest-rendering posture).
5. The module path (`app/persistence/quizzes.py`), the initial public API surface (the read accessor + the `requested`-row creator are the TASK-013 must-ship; the rest are forecast), and the `__init__.py` re-export shape (single import surface).
6. The schema-bootstrap mechanic (extend `_SCHEMA_SQL` in `connection.py`; flag the n-tables threshold for the next task; recommend `PRAGMA foreign_keys = ON`).
7. The deferral of the Grade aggregate (score / Weak Topics / recommended Sections) and the `notifications` table to their consuming tasks — both additive when they land.
8. The migration story: ADR-022's `CREATE TABLE IF NOT EXISTS`; the schema is designed for additive extensibility (the generation/grading/composition tasks add columns/tables/lifecycle-states, never rename or re-constrain); the first non-additive change forces a follow-up ADR.

This ADR does **not** decide:

- The per-Section Quiz surface placement, the empty-state copy, the CSS namespace, or the route/template shape of the placeholder Quiz-trigger affordance — owned by ADR-034.
- The `ai-workflows` integration mechanics, the forbidden-SDK list, the workflow module path, the async-result-delivery mechanism, or the replay-+-fresh composition logic — owned by the next task(s)' `/design`. This ADR's lifecycle enums *name* the states those tasks will drive; they do not commit to *how*.
- The Topic-vocabulary source and read path — owned by the generation task's `/design` (the `questions.topics` column is migrated into a `question_topics` join at that point).
- The Grade aggregate's column shape — owned by the grading task's `/design`.
- The Notification entity's schema or surface — owned by the async-delivery task's `/design`.
- The Quiz-taking surface (where the learner writes code against a Question, response persistence, the "submit Attempt" route) — owned by a later task; the `attempt_questions.response` column is the slot it writes to.
- Whether `_SCHEMA_SQL` is refactored into per-module fragments — flagged for the next persistence-touching task; not decided here.
- Any change to the `notes` / `section_completions` schemas — untouched.

## Alternatives considered

**A. `quiz_id` FK column on `questions` instead of a `quiz_questions` join table.**
Rejected. A `quiz_id` FK on `questions` makes each Question belong to exactly one Quiz forever. Manifest §8 says a Question "May appear in multiple Quizzes for its Section over time" — and the reinforcement loop *requires* it: a replayed wrong-answer Question (manifest §7) is, by construction, in a *later* Quiz than the one it was first answered incorrectly in. The FK-on-`questions` shape would force the replay-composition task to either supersede this ADR with a non-trivial migration or to *copy* Questions (defeating "the persisted set of all Questions ever generated for a Section, each retaining its full Attempt history" — a copied Question has no history). The `quiz_questions` join is the only shape that satisfies §8 and §7 without churn. The `position` column on the join gives Question ordering within a Quiz at negligible cost.

**B. Defer the `questions` table entirely; ship only `quizzes` + `quiz_attempts` this task.**
Considered. TASK-013 produces no Questions (no generation). But the schema-churn argument cuts the other way: the *expensive* decisions are exactly the Question-shaped ones (the `quiz_questions` membership join; the `attempt_questions` per-Question-correctness structure; where Topic tags live) — deferring `questions` would mean the generation/grading/composition tasks each re-open those decisions mid-flight, which is *more* risk, not less. Shipping the full Question-side schema now, with no rows, is the same move the project made for `notes` (TASK-009 shipped the table; the edit/delete/Section-reference follow-ups just `ALTER`/`INSERT` against it). Rejected: ship `questions` (and `quiz_questions`, `attempt_questions`) now.

**C. One combined `status` enum on `quizzes` covering both generation and grading lifecycles.**
Rejected. Generation status is a property of the *Quiz* (a Quiz is generated once); grading status is a property of an *Attempt* (a Quiz can be attempted multiple times, each Attempt graded separately — §8: "A single submission of a Quiz by the user"). Conflating them onto one column forces awkward semantics ("the Quiz is `graded`" — which Attempt?) and breaks the moment a second Attempt exists. The two-enum split (`quizzes.status` for generation, `quiz_attempts.status` for attempt/grading) is the shape the entities actually have.

**D. Per-Question responses + correctness as a JSON/TEXT blob column on `quiz_attempts` instead of an `attempt_questions` table.**
Rejected. A JSON blob (`responses TEXT` containing `[{question_id, response, is_correct, explanation}, ...]`) makes the replay-composition query — "give me every `question_id` the user got wrong in any Attempt for this Section" — a full-table scan with JSON parsing in application code, instead of `SELECT DISTINCT question_id FROM attempt_questions WHERE is_correct = 0 AND attempt_id IN (...)`. It also makes per-Question grading an awkward read-modify-write of the whole blob. The relational `attempt_questions` table is the shape the loop's replay portion (MC-8 / §7) wants to query against; ADR-022 already rejected JSON storage for the persistence layer ("indexing … atomic writes … future query patterns … are all easier with SQL than with a JSON document") — the same reasoning applies here.

**E. Ship the Grade aggregate now — a `grades` table (or `score` / `weak_topics` columns on `quiz_attempts`).**
Rejected for this task. The Grade aggregate (score, identified Weak Topics, recommended Sections — §8) has *no consumer* until grading exists (the next-next task). Shipping it now is a table nothing writes to and nothing reads — the architecture-on-spec anti-pattern the project's task discipline rejects. And the cost of deferring is zero: when the grading task lands, it adds the `grades` table (`CREATE TABLE IF NOT EXISTS`) or the columns (`ALTER TABLE ADD COLUMN`, nullable) — both additive, neither fires ADR-022's migration trigger. The *per-Question* portion of the Grade (correctness + explanation) *is* shipped now, via `attempt_questions`, because that structure is load-bearing for MC-8 (the loop's replay portion needs per-Question wrong-answer history) and is the expensive-to-get-wrong shape — the aggregate is a cheap additive follow-on.

**F. Ship a `notifications` table stub now (ADR-022 forecasts it).**
Considered (the task names it a "borderline call"). Rejected. The lifecycle enums this ADR commits to do not *reference* a `notifications` table — a `quizzes.status = 'ready'` row and a `quiz_attempts.status = 'graded'` row are the *facts* a future Notification scaffolding reads; the Notification entity is a *projection* of those facts (manifest §8: "A learner-visible indication that an async AI result has become available"), not a precondition for them. A `notifications` table with no surface, no async-delivery path, and nothing reading it is architecture-on-spec. The async-delivery task — which has the consumer (the learner-visible "your Grade is ready" indication) — owns the Notification schema. Deferring costs nothing (`CREATE TABLE IF NOT EXISTS` is additive).

**G. Topic tags as a `question_topics` join table referencing a `topics` table, shipped now.**
Rejected for this task — see §Topic tags. The relational form is the *right* shape eventually (Weak-Topic identification in the generation task wants Topics as first-class entities; §8 says Topics are a "project-wide vocabulary maintained alongside Chapter content"), but shipping a `topics` table *now* — with no curriculum-side source, no maintenance path, and nothing reading it — is the architecture-on-spec anti-pattern the project has rejected for Topics three times. The migration from the cheap `questions.topics TEXT` form to the relational form is additive (new tables + a data backfill, no schema rename — does not fire ADR-022's trigger), so deferring is free. The generation task's `/design` owns the Topic-vocabulary-source decision; it migrates `questions.topics` into `question_topics` at that point.

**H. Topic tags as a `question_topics` join with free-text `topic` values and no `topics` table.**
Rejected. This is the relational shape's *cost* (a join table; a row per (question, topic)) without its *benefit* (a canonical Topic vocabulary — §8's "project-wide vocabulary"). Free-text topic values in a join table drift (`"hashing"` vs `"Hashing"` vs `"hash tables"`) exactly as much as a delimited TEXT column does, and are *harder* to clean up later. If we are going to defer the canonical vocabulary (which we are, correctly), the cheap delimited-TEXT column is the lower-cost interim shape.

**I. A separate database file for Quiz data (`data/quizzes.db`).**
Rejected — forbidden by ADR-022's single-shared-DB cohabitation commitment (and ADR-022 §Alternative E rejected exactly this). Cross-database transactions (a future Quiz Attempt referencing Notes-side data, or `ai-workflows` state referencing both) would require SQLite `ATTACH DATABASE` gymnastics for no offsetting benefit at single-user scale. The Quiz tables live in `data/notes.db`.

**J. An ORM (SQLAlchemy / SQLModel) for the Quiz domain because it has more inter-table relationships than Notes.**
Rejected — forbidden by ADR-022's stdlib-`sqlite3` commitment (and ADR-022 §Alternative A rejected it). Five tables with hand-written SQL in one ~250-line module is well within the "transparent, grep-able, no dependency" range ADR-022 chose; the `quiz_questions` / `attempt_questions` joins are simple `JOIN`s, not the relationship-traversal gnarliness an ORM earns its keep on. If the Quiz schema later becomes genuinely too gnarly to maintain by hand, supersede ADR-022 (the architecture-portion owner of the storage decision), not this ADR.

**K. A `quiz_events` append-only log for status transitions instead of a `status` column.**
Rejected — same reasoning as ADR-024 §Alternative B (the event-log shape for `section_completions`). No consumer of Quiz-status *history* exists; storing every transition as a row to answer "what is the current status" (one bit) is over-engineering. If a future task surfaces a real consumer (e.g., "show me when this Quiz's generation started/finished"), a `quiz_events` table can be added *alongside* the `status` column in a superseding ADR; the cost of starting with a `status` column and adding an event log later is not paying double. (The `created_at` / `submitted_at` / `graded_at` timestamps already capture the lifecycle-event *times* without a full event log.)

**L. No `REFERENCES` clauses at all (mirror ADR-024's "no FK because the referent is filesystem-derived").**
Rejected. ADR-024's rationale for no FK on `section_completions` is that Sections are *filesystem-derived* — there is no `sections` table to FK to. That does not apply to `quiz_questions` → `quizzes` / `questions` or `attempt_questions` → `quiz_attempts` / `questions`: those *are* persisted rows in tables that exist. Declaring the `REFERENCES` clauses (a) self-documents the relationships, (b) lets `PRAGMA foreign_keys = ON` actually prevent dangling rows. The cost is zero (SQLite ignores them without the pragma). Keeping them is the right default.

**M. Ship the full forecast public API (all the `add_questions_to_quiz` / `create_attempt` / `record_grade` / etc. functions) as stubs now.**
Rejected. Stubbing functions that no TASK-013 code path calls — and that the generation/grading/quiz-taking tasks will shape based on *their* `/design` — is speculative scaffolding. TASK-013 needs `request_quiz`, `list_quizzes_for_section`, and `list_quizzes_for_chapter` (the bulk read accessor for `render_chapter`); those are what this ADR commits to as the must-ship public API. The rest are *forecast* in the ADR (so later tasks know the shape that's coming) but added incrementally by the tasks that have a caller. This matches how `section_completions.py` grew (`count_complete_sections_per_chapter` was added by ADR-026/TASK-011, not stubbed by ADR-024/TASK-010).

## My recommendation vs the user's apparent preference

The TASK-013 task file forecasts: the `quizzes` / `questions` / `quiz_attempts` (+ join/history) tables under `app/persistence/quizzes.py` in `data/notes.db` with ADR-022's migration story; a `quiz_questions` join table for multi-Quiz Question membership (the task says explicitly "the task forecasts a `quiz_questions` join table for the multi-Quiz-membership requirement; if `/design` disagrees, argue it at the gate"); a status enum reserving the async-grading lifecycle including a failure state; no `user_id`; no choice/recall/describe columns; per-Question correctness recordable without a non-additive migration; and the Topic-vocabulary question folded into `/design` as a conditional decision ("ship a minimal Topic vocabulary now … iff the schema ADR concludes the alternative (a delimited TEXT column on `questions`, migrated later) is genuinely worse; otherwise defer Topics to the generation task and ship the cheap TEXT-column form now").

This ADR is **aligned with the task's forecast in full**, with these specifics the task left to `/design`:

- **`quiz_questions` join table — adopted as forecast** (with a `position` column the task didn't name; argued in §Decision and §Alternative A). No disagreement to surface here.
- **Five tables, not three.** The task forecasts "`quizzes` / `questions` / `quiz_attempts` (+ join/history)"; this ADR commits to `quizzes`, `questions`, `quiz_questions` (membership), `quiz_attempts`, `attempt_questions` (per-Question state). The "(+ join/history)" the task left open is realized as *two* tables — `quiz_questions` (Question↔Quiz membership) and `attempt_questions` (per-Question response + correctness within an Attempt). The architect's read is that `attempt_questions` is the right place for per-Question correctness (the task explicitly listed "a separate `attempt_questions`-style table now" as one of the `/design` options and asked the architect to pick) — it ships now because it is the expensive-to-get-wrong, MC-8-load-bearing shape, while the Grade *aggregate* (score/weak-topics/recommended-sections) ships later additively.
- **Two lifecycle enums, not one.** The task forecasts "a `status` enum reserving the async-grading lifecycle"; the architect splits it into `quizzes.status` (generation) + `quiz_attempts.status` (attempt/grading) because the two lifecycles belong to different entities. The task's enumerated example states (`requested` / `generating` / `awaiting_submission` / `submitted` / `grading` / `graded` / `failed`) are honored, redistributed across the two enums and with two distinct failure states (`generation_failed`, `grading_failed`) rather than one ambiguous `failed`. If the human prefers a single enum or a different state set, this is the place to push back at the gate — but the architect's read is that the two-enum split is the schema's natural shape and the task's "exact set is `/design`'s call" grants the authority.
- **Topic tags — deferred (the cheap TEXT column ships now).** The architect concludes the cheap `questions.topics TEXT` form is *not* genuinely worse than a `topics` table + join, because the migration to the relational form is additive (new tables + a data backfill, no schema rename — does not fire ADR-022's trigger). Per the task's framing, that means: ship the cheap form now, defer Topics to the generation task, and say so explicitly — which this ADR does (§Topic tags). **No separate Topic-vocabulary ADR is created by TASK-013.** This is aligned with the task's instruction; the task's prior-tasks-rejected-Topic-bootstrap-as-a-standalone-task history reinforces it.
- **The placeholder Quiz-trigger affordance — Option 1 (real `requested`-row route).** The schema side of this is here; the route/template side is ADR-034. The architect chose Option 1 (a real user-triggered `POST .../quiz` route that inserts a `status='requested'` Quiz row, no AI call, no background job, nothing fabricated) over Option 2 (disabled/caption) and Option 3 (nothing) — reasoning in ADR-034's "My recommendation vs the user's apparent preference"; the schema-side justification is here in §The `requested` status. The architect does **not** route this to `> NEEDS HUMAN` — the task's framing ("the task's framing gives the architect the authority to pick") and the bounded risk (the next task is scheduled; a `requested` row with no processor is honestly "we recorded your request," not a fabricated result; the surface renders it honestly) support deciding it.

I am NOT pushing back on:

- The single-user posture (manifest §5 / §6 / §7, MC-7) — honored: no `user_id` on any of the five tables, no auth, no per-user partitioning.
- The MC-2 / §6 / §7 Quiz-scope rule — honored by construction: `quizzes.section_id NOT NULL`; no Chapter-bound Quiz row; no aggregation-across-Sections row; no route or query composes a Quiz from Questions of more than one `section_id`.
- The "every Question is a hands-on coding task" rule (manifest §5 / §7) — honored: `questions` carries `prompt` (the coding-task prompt) and `topics` (tags); no `option_*` / `correct_choice` / `answer_text` / `describe_*` / `recall_*` columns; the schema does not admit a non-coding Question format.
- The "AI failures are visible, never fabricated" absolute (manifest §6, MC-5) — honored: both lifecycle enums name a failure state; the `requested`-status row is honestly a recorded request, not a fabricated Quiz/Grade/Question; the read surface (ADR-034) renders it honestly.
- The "reinforcement loop not foreclosed" rule (MC-8 / §7) — honored: `quiz_questions` permits a Question in multiple Quizzes for its Section; `attempt_questions.is_correct` makes per-Question wrong-answer history recordable; the replay portion (per-Question wrong-answer history) and the fresh portion (Weak-Topic-targeted generation, via the deferred Topic relational form) both have schema room without a non-additive migration.
- The "Quiz generation is user-triggered" rule (MC-9 / §7) — honored: the only path that creates a `quizzes` row in TASK-013 is the explicit user click on the placeholder trigger; no background job, no scheduled task.
- The "no direct LLM SDK use" rule (manifest §4, MC-1) — honored: this ADR adds no AI dependency; the lifecycle enums *name* states a future `ai-workflows` integration drives but commit to no integration mechanics; MC-1's architecture portion stays `cannot evaluate (ADR pending)`.
- The persistence-boundary rule (MC-10, active per ADR-022) — honored: SQL string literals for the Quiz domain live exclusively in `app/persistence/quizzes.py`; routes/templates call only the typed public functions; no `import sqlite3` outside `app/persistence/`.
- The read-only Lecture source rule (manifest §6, MC-6) — honored: the Quiz tables live in `data/notes.db`; nothing under `content/latex/` is opened for write.
- The Section ID scheme (ADR-002) — honored: `section_id` stores the full composite identifier; the route handler validates it against the parsed Section set (ADR-024's split); no re-derivation.
- The single-shared-DB cohabitation commitment (ADR-022) — honored: all five tables join `data/notes.db`; no new file.
- ADR-024's per-entity-module pattern — honored: `app/persistence/quizzes.py` is a new module under the same package, mirroring `section_completions.py`'s shape, validation-at-the-route-handler split, and `try ... finally` connection handling.
- The migration story (ADR-022) — honored: `CREATE TABLE IF NOT EXISTS`; the schema is additive-extensible; the first non-additive change forces a follow-up ADR.

## Manifest reading

Read as binding for this decision:

- **§3 Primary Objective.** Per-Section Quizzes are one of the three named consumption surfaces and the home of the reinforcement loop ("the reason this project exists" — §7); this schema is the foundation the loop is built on. The schema and the read accessor satisfy this.
- **§5 Non-Goals.** "No cross-Section Quizzes. A Quiz scope is one Section" — `quizzes.section_id NOT NULL`; no Chapter-bound Quiz row; no aggregation row. "No non-coding Question formats … Every Question is a hands-on coding task" — `questions` carries `prompt` + `topics`, no choice/recall/describe columns. "No live / synchronous AI results … surfaced via Notification" — the lifecycle enums name the async states; no AI call this task; no synchronous-AI path created. "No LMS gradebook export" — no completion/grade-export route; the Grade aggregate (deferred) carries no export semantics. "No multi-user" — no `user_id`. "No remote deployment" — single shared SQLite file (ADR-022).
- **§6 Behaviors and Absolutes.** "Quizzes scope to Sections; … Per-Chapter quiz aggregations, if ever surfaced, are computed from per-Section results. There is no Chapter-bound Quiz entity" — directly motivates `quizzes.section_id NOT NULL` and the absence of any aggregation table; per-Chapter aggregations are a query, not a stored entity. "AI work is asynchronous" — orthogonal to the schema (no AI in this task); the lifecycle enums are shaped so the async-delivery task adds states additively. "AI failures are visible … never fabricates a result" — both enums name a failure state; the `requested` row is honest. "Single-user" — no `user_id`. "Lecture source read-only" — Quiz tables in `data/notes.db`, never under `content/latex/`. "Mandatory and Optional honored everywhere" — orthogonal to the schema (the per-Section surface inherits the Chapter's designation via ADR-004's function — ADR-034's concern).
- **§7 Invariants.** **"A Quiz is bound to exactly one Section."** — `quizzes.section_id TEXT NOT NULL`; no nullable / multi-valued Section reference; no Chapter-bound Quiz row. **"Every Question is a hands-on coding task. … Questions never ask the learner to describe, explain, recall, or choose among options."** — `questions` has `prompt` (the coding task) and `topics`; no `option_*` / `correct_choice` / `answer_text` / `describe_*` / `recall_*` columns. **"Every post-first Quiz for a Section contains both replayed wrong-answer Questions and freshly-generated Questions … The first Quiz for a Section contains only fresh Questions (the bank is empty)."** — this task ships no composition logic, but the schema leaves room: `quiz_questions` permits a Question in multiple Quizzes; `attempt_questions.is_correct` makes wrong-answer-replay history recordable; the fresh portion (Weak-Topic-targeted generation) has schema room via the deferred Topic relational form (additive). **"Quiz generation is always explicitly user-triggered."** — the `requested`-status row is created only by the explicit user click (ADR-034's route); no background job. **"Every Quiz Attempt … persists across sessions"** — `quiz_attempts` rows live in SQLite outside the FastAPI process.
- **§8 Glossary.** **Quiz** ("scoped to exactly one Section, composed of one or more Questions. Generated by AI-driven processing on manual user trigger") — `quizzes` (`section_id NOT NULL`; `status` tracks the generation lifecycle; a `ready` Quiz has `quiz_questions` rows). **Question** ("a hands-on coding task … Has one or more Topic tags. Persists with full Attempt history … May appear in multiple Quizzes for its Section over time") — `questions` (`prompt`, `topics`); the `quiz_questions` join enables multi-Quiz membership; `attempt_questions` carries the per-Question history. **Question Bank** ("the persisted set of all Questions ever generated for a Section … Never deleted; only superseded by content reorganization") — `questions` per Section; no delete path. **Quiz Attempt** ("a single submission of a Quiz by the user. Carries the user's responses, a progress status through grading, and — once graded — a Grade") — `quiz_attempts` (`status` is the progress status; `attempt_questions.response` is the user's responses; the Grade aggregate is deferred, additive). **Grade** ("per-Question correctness, per-Question explanation, an aggregate score, identified Weak Topics, and recommended Sections to re-read") — the per-Question portion ships now (`attempt_questions.is_correct` / `.explanation`); the aggregate (score / Weak Topics / recommended Sections) is deferred to the grading task, additive. **Weak Topic** ("Topics form a project-wide vocabulary maintained alongside Chapter content") — bears on the Topic-tags decision: the canonical vocabulary is curriculum-side, so a `topics` table now (with no curriculum-side source) would be architecture-on-spec; `questions.topics` as a delimited TEXT column is the interim shape, migrated into a `question_topics` join by the generation task. **Notification** ("a learner-visible indication that an async AI result has become available") — a projection of `quizzes.status = 'ready'` / `quiz_attempts.status = 'graded'` facts; the `notifications` table is deferred to the async-delivery task. No new glossary terms are forced — every entity this ADR creates is already named in §8.

No manifest entries flagged as architecture-in-disguise for this decision. Manifest §4's `ai-workflows` commitment is *not* exercised by this ADR (deliberately — the AI-engine ADR is the next task's job); the lifecycle enums name async states but commit to no integration mechanics. (The standing flag from the project's MEMORY.md — "manifests describe desire, not architecture" — does not apply here: §5's "no non-coding Question formats" / "no cross-Section Quizzes" and §6's "no Chapter-bound Quiz entity" read as *product behavior* the schema honors by construction, not as tech-choice or mechanism entries; §4's `ai-workflows` commitment is the one explicit manifest-level architectural commitment, acknowledged and not over-reached.)

## Conformance check

- **MC-1 (No direct LLM/agent SDK use).** Honored. This ADR adds no AI dependency, no LLM SDK import, no AI call (not even stubbed); the persistence module depends only on stdlib `sqlite3`. The lifecycle enums *name* async-generation / async-grading states a future `ai-workflows` integration will drive — schema design, not an AI-integration decision. **Manifest portion: PASS.** **Architecture portion: stays `cannot evaluate (ADR pending)`** — the forbidden-SDK list and the workflow module path come from the AI-engine ADR, which is the *next* task's job, not this one's. Unchanged by this ADR.
- **MC-2 (Quizzes scope to exactly one Section).** Honored by construction. `quizzes.section_id TEXT NOT NULL`; no Chapter-bound Quiz row; no aggregation-across-Sections row; no route or query composes a Quiz from Questions of more than one `section_id` (the `request_quiz` route writes exactly one `section_id`; `add_questions_to_quiz` — forecast — will INSERT only Questions whose `section_id` matches the Quiz's). The reviewer re-verifies on the diff. **PASS.**
- **MC-3 (Mandatory/Optional designation respects the canonical mapping).** Orthogonal to the schema (no designation column; the per-Section surface inherits the Chapter's designation via ADR-004's function — ADR-034's concern, not this ADR's). No hardcoded chapter-number rule introduced. **PASS** (architecture portion of MC-3 — the canonical-mapping source — remains as ADR-004 defined; this ADR consumes it indirectly).
- **MC-4 (AI work asynchronous).** Honored — no code path in this task completes AI processing synchronously (there is no AI call). The lifecycle enums are shaped so the generation/grading tasks decouple submission, processing, and result delivery in time without a non-additive migration. The workflow-name enumeration stays `cannot evaluate (ADR pending)`. **PASS** (manifest principle).
- **MC-5 (AI failures surfaced, never fabricated).** Honored. Both lifecycle enums name a failure state (`generation_failed`, `grading_failed`) so the future generation/grading tasks surface failures as failures. The `requested`-status row the placeholder trigger creates is honestly "we recorded your request" — not a fabricated Quiz, Question, or Grade; the read surface (ADR-034) renders it honestly (never "Quiz ready" until `status = 'ready'`). No fallback path synthesizes a "looks like a grade" object — there is no AI surface to fail. **PASS.**
- **MC-6 (Lecture source read-only).** Honored. The five Quiz tables live in `data/notes.db` (ADR-022's store); nothing under `content/latex/` is opened for write by `app/persistence/quizzes.py`. The route handler still *reads* `content/latex/{chapter_id}.tex` (to validate the Section ID for `request_quiz`) — read-only, identical to what ADR-024's completion route already does. **PASS.**
- **MC-7 (Single user).** Honored. None of `quizzes`, `questions`, `quiz_questions`, `quiz_attempts`, `attempt_questions` has a `user_id` column, a `created_by` column, or any per-user partitioning; no auth, no session, no role check. Architecture portion (active per ADR-022): a future contributor cannot add a `user_id` to any Quiz table without superseding both ADR-022 and this ADR. **PASS.**
- **MC-8 (Reinforcement loop preserved).** Honored — the schema does not foreclose the loop. `quiz_questions` permits a Question to belong to multiple Quizzes for its Section over time (§8); `attempt_questions.is_correct` makes per-Question wrong-answer history recordable (the replay portion's input — MC-8 / §7); the fresh portion (Weak-Topic-targeted generation) has schema room via the deferred Topic relational form (additive — `questions.topics` migrates into `question_topics` in the generation task). No Quiz-composition code path exists in this task, so the "skip the replay query" / "skip fresh generation" forbidden paths are not yet exercisable — the reviewer confirms the schema leaves room for both portions without a non-additive migration. **PASS** (no composition code to evaluate yet; schema does not foreclose).
- **MC-9 (Quiz generation is user-triggered).** Honored. The only path that creates a `quizzes` row in TASK-013 is the explicit user click on the placeholder trigger (ADR-034's `POST .../quiz` route). No background job, no scheduled task, no auto-trigger creates a Quiz; nothing auto-generates anything (the `requested` row sits until the next task's generation workflow — itself user-context-bound — processes it). **PASS.**
- **MC-10 (Persistence boundary).** Honored. SQL string literals for the Quiz domain live exclusively in `app/persistence/quizzes.py`; the new `_SCHEMA_SQL` DDL lives in `app/persistence/connection.py`. Routes/templates call only the typed public functions from `app/persistence/__init__.py` (`request_quiz`, `list_quizzes_for_section`, `list_quizzes_for_chapter`) — they never receive a `sqlite3.Connection` or a raw row; they receive `Quiz` / `Question` dataclass instances. No `import sqlite3` outside `app/persistence/`; no SQL keyword in a string literal outside `app/persistence/`. MC-10 is `blocker` now (the persistence package exists per ADR-022); the new module respects the boundary. **PASS.**

Previously-dormant rule activated by this ADR: none new. (MC-1's architecture portion stays dormant — the AI-engine ADR doesn't exist yet. MC-7's and MC-10's architecture portions are already active per ADR-022; this ADR consumes both.)

## Consequences

**Becomes possible:**

- A persisted Quiz domain — Quizzes, the per-Section Question Bank, Quiz↔Question membership, Quiz Attempts, and per-Question Attempt state — that survives FastAPI restarts (manifest §7 satisfied for Quiz Attempts).
- A user-triggered "Generate a Quiz for this Section" affordance that records a `requested`-status Quiz row (manifest §7 / MC-9: user-triggered; MC-1: no AI call) — the first concrete piece of the Quiz pillar's write side.
- The generation task to focus purely on the `ai-workflows` integration + async delivery + Notification: it walks `requested` Quiz rows to `generating` → `ready` and `INSERT`s `quiz_questions` rows; it does not re-invent the schema or the surface.
- The grading task to `UPDATE` `attempt_questions.is_correct` / `.explanation` and add the Grade aggregate (a `grades` table or columns on `quiz_attempts`) additively — no re-decision of the per-Question structure.
- The replay-composition task (manifest §7) to query `SELECT DISTINCT question_id FROM attempt_questions WHERE is_correct = 0 AND attempt_id IN (...)` for the replay portion, and the discovered Section's Question Bank for the fresh portion's prior context — no schema change.
- A per-Section Quiz read surface (ADR-034) that does one `list_quizzes_for_chapter` query per Lecture-page render — the same shape as ADR-024's `complete_section_ids` and ADR-028's `rail_notes_context`.
- ADR-022's cohabitation pattern validated for a *multi-table* entity (five tables, one module) — the next entity inherits a proven shape.
- A clean test-fixture pattern: tests inject `NOTES_DB_PATH` (per ADR-022), all five Quiz tables are created in the test DB on first connection, per-test isolation continues to work.

**Becomes more expensive:**

- `connection.py`'s `_SCHEMA_SQL` is now ~55 lines instead of ~17. Mitigation: still a readable string; this ADR flags the n-tables threshold for the *next* persistence-touching task, which may legitimately propose a per-module schema-fragment-registration refactor (a pure code reorganization that does not fire ADR-022's migration trigger).
- Adding a Quiz-domain column requires editing `_SCHEMA_SQL` AND a `PRAGMA table_info`-guarded `ALTER TABLE` for existing installs (per ADR-022's migration story). Mitigation: same as ADR-022/ADR-024 — at single-user scale, "existing installs" is one machine.
- `app/persistence/__init__.py` grows by ~5 names (the must-ship Quiz API + the two dataclasses), more as later tasks add the forecast functions. Mitigation: still well below any reasonable API-surface threshold; the alternative (deep imports) would compromise the single-import-surface convention.
- `app/persistence/quizzes.py` will grow over the next several tasks (generation, grading, quiz-taking, composition each add functions). Mitigation: that growth is the entity module doing its job; the per-entity-module boundary keeps it contained, and if it grows past ~500 lines a future task may split it (e.g., `quizzes.py` + `attempts.py` per ADR-022's forecast module list) — a pure reorganization, not a re-decision.

**Becomes impossible (under this ADR):**

- A `user_id` column on any Quiz table. Forbidden by MC-7.
- A Chapter-bound Quiz row, or a Quiz row that aggregates across Sections. Forbidden by `quizzes.section_id NOT NULL` + MC-2 + §6.
- A `quizzes` row whose `section_id` is not the full ADR-002 composite ID. The route-handler validation (ADR-024's split) rejects it.
- A Question that belongs to exactly one Quiz forever. The `quiz_questions` join (not a `quiz_id` FK on `questions`) permits multi-Quiz membership; the `questions` table has no `quiz_id` column.
- A non-coding Question format. The `questions` schema has no `option_*` / `correct_choice` / `answer_text` / `describe_*` / `recall_*` column; adding one would require superseding this ADR.
- Deleting a Question from the Bank. No delete path for `questions` rows exists in `app/persistence/quizzes.py` (and with `PRAGMA foreign_keys = ON`, a referenced Question cannot be deleted).
- A fabricated Quiz/Grade/Question. The `requested` status is honest; both failure states exist; the read surface (ADR-034) renders status in plain language. (The grading/generation tasks' MC-5 obligation is to *use* the failure states, not invent results — this ADR gives them the states to use.)
- Storing Quiz data in a separate database file, or via an ORM, without superseding ADR-022.

**Future surfaces this ADR pre-positions:**

- `ai-workflows` generation workflow — walks `requested` Quiz rows to `generating` → `ready`, `INSERT`s `quiz_questions`. Next task. Same DB, same migration story.
- `ai-workflows` grading workflow — walks `submitted` Attempts to `grading` → `graded`, `UPDATE`s `attempt_questions.is_correct` / `.explanation`, adds the Grade aggregate (additive). Next-next task.
- The replay-+-fresh composition logic — `SELECT`s wrong-answer Questions (`attempt_questions.is_correct = 0`) + fresh Questions (Weak-Topic-targeted) for a post-first Quiz of a Section. A later task. No schema change.
- The Quiz-taking surface — creates a `quiz_attempts` row when the learner starts a `ready` Quiz; `UPDATE`s `attempt_questions.response`. A later task. The `attempt_questions.response` column is the slot.
- The Notification surface — a projection of `quizzes.status = 'ready'` / `quiz_attempts.status = 'graded'`; adds a `notifications` table (additive). The async-delivery task.
- The Topic relational form — a `topics` table + `question_topics` join, backfilled from `questions.topics`. The generation task. The data migration does not fire ADR-022's trigger; dropping `questions.topics` is optional.
- The Grade aggregate — a `grades` table or columns on `quiz_attempts` (`score`, `weak_topics`, `recommended_sections`). The grading task. Additive.
- Per-Chapter quiz aggregations (manifest §6: "computed from per-Section results, if ever surfaced") — a query (`GROUP BY` over `quizzes.section_id`), never a stored entity. A later task with a real consumer.

**Supersedure path if this proves wrong:**

- If `attempt_questions` proves the wrong shape for the Grade's per-Question portion (e.g., the grading task wants a different structure) → supersede with a new ADR; the `attempt_questions` table stays (it carries no rows until the quiz-taking task), or is migrated. Cost: bounded; nothing reads it until grading exists.
- If the two-enum split proves awkward (e.g., a unified workflow-state model emerges) → supersede; the enums are TEXT, so re-shaping them is a data migration plus possibly a column rename (the rename being the only non-additive piece). Caught early because no rows exist until the generation/quiz-taking tasks.
- If the `'|'`-delimited `questions.topics` form proves to leak (e.g., a Topic name contains `'|'`) → the persistence module's split/join logic is the fix (escape, or switch the delimiter); if that's insufficient, accelerate the `question_topics` migration (which the generation task does anyway). Cost: bounded.
- If `_SCHEMA_SQL` centralization becomes unwieldy at the next entity → the next persistence-touching task introduces per-module schema-fragment registration in a superseding ADR (a pure code reorganization; ADR-022's migration trigger does not fire). This ADR explicitly flags it.
- If the schema becomes too gnarly to maintain by hand across the generation/grading/composition tasks → supersede ADR-022 (the storage-decision owner) to introduce an ORM; this ADR's table shapes carry over as the ORM models.
- If the single-shared-DB commitment proves wrong (the DB grows multi-gigabyte) → supersede ADR-022 to split; this ADR's tables move as a unit.

The supersedure path for the Quiz schema, in every case, runs through a new ADR (and, where the storage *technology* or *file layout* is what's wrong, through superseding ADR-022 first). This ADR does not edit any prior ADR in place; it adds under ADR-022's umbrella.
