# ADR-046: The Question preamble persistence layer — a nullable `questions.preamble TEXT` column (additive `ALTER TABLE ADD COLUMN` via the `_apply_additive_migrations` check + the `CREATE TABLE questions` block for fresh DBs), the `Question` dataclass gains `preamble: str | None`, `add_questions_to_quiz`'s per-Question payload dict gains a `"preamble"` key (no signature change), the row→dataclass converter and the `Question`-returning accessors (`list_questions_for_quiz`, `get_question`) carry it through; no new accessor; no `user_id`; SQL stays under `app/persistence/`

**Status:** `Accepted`
Auto-accepted by /auto on 2026-05-13
**Date:** 2026-05-13
**Task:** TASK-018
**Resolves:** none — the companion **ADR-045** resolves `design_docs/project_issues/question-gen-prompt-emit-assertion-only-test-suites.md`; this ADR is the persistence-mechanics half of that resolution.
**Supersedes:** none — consumes **ADR-041** (the `questions.test_suite` column this mirrors — the new `preamble` column is added by the same `_apply_additive_migrations` `PRAGMA table_info` + guarded `ALTER TABLE ADD COLUMN` recipe, also declared in the `CREATE TABLE IF NOT EXISTS questions` block for fresh DBs; the `Question` dataclass's `test_suite: str | None` field shape this new field mirrors; the `add_questions_to_quiz` payload-dict pattern this extends; the `list_questions_for_quiz` `SELECT` carry-through this extends), **ADR-044** (the `get_question(question_id) -> Question | None` accessor added by the runner slice — its `SELECT` and the returned dataclass extend to carry `preamble`; ADR-044 consumed unchanged in all decisions but the dataclass's one additional attribute), **ADR-033** (the `questions` table this extends — the new `preamble` column is additive per ADR-022's migration story; the no-non-coding-column posture is preserved — the new column holds only source code, the shared struct/class shapes; the `'|'`-delimited `topics` column and all other existing columns are unchanged), **ADR-022** (the persistence boundary — `import sqlite3` + SQL literals stay under `app/persistence/`; the additive-migration story — `CREATE TABLE IF NOT EXISTS` / nullable `ALTER TABLE ADD COLUMN`; the per-entity-module pattern), **ADR-037** (the generation processor whose `add_questions_to_quiz` call now passes one more key in the per-Question dict — the lifecycle / failure-handling unchanged), and **ADR-039** (the `Question`-returning accessor `list_questions_for_quiz` whose returned dataclass gains the new field — consumed; no signature change). The companion **ADR-045** owns the prompt + schema + processor decisions (the `GeneratedQuestion.preamble` Pydantic field, the prompt's new STRICT REQUIREMENTs, the processor's `q.get("preamble", "")` defensive read, the asymmetric "preamble is NOT a `generation_failed` trigger" decision); the companion **ADR-047** owns the sandbox splice extension and the take-surface `preamble` block; this ADR owns *only* the storage mechanics. No prior ADR is re-decided.

## Context

ADR-045 decides that a Question carries a **preamble** — a string of shared struct/class/header source the test suite (and the learner's implementation) both depend on — represented as **an additive optional `GeneratedQuestion.preamble: str` Pydantic field** (`default=""`; empty-string-allowed; not embedded inside `prompt` or `test_suite`). This ADR decides how that string is *stored* in `data/notes.db` and *exposed* to callers — the small persistence-layer changes ADR-045 forecast as "owned by the companion ADR-046".

The established context:

- ADR-033's `questions` table: `question_id` PK AUTOINCREMENT, `section_id TEXT NOT NULL`, `prompt TEXT NOT NULL`, `topics TEXT NOT NULL DEFAULT ''` (`'|'`-delimited), `created_at TEXT NOT NULL`, plus (ADR-041) `test_suite TEXT` (nullable) — created via `CREATE TABLE IF NOT EXISTS` in `app/persistence/connection.py`'s `_SCHEMA_SQL` block (under ADR-022's migration story), with `test_suite` added to existing DBs via `_apply_additive_migrations`'s `PRAGMA table_info` + guarded `ALTER TABLE ADD COLUMN` recipe and also declared in the fresh-DB `CREATE TABLE` block. The `Question` dataclass in `app/persistence/quizzes.py` mirrors the columns (`topics` exposed as `list[str]`, split from the delimited column; `test_suite: str | None`).
- ADR-044 added `get_question(question_id) -> Question | None` (a single-Question accessor used by the "Run tests" route to fetch a Question's `test_suite` to feed the sandbox) and the four `attempt_questions` test-result columns (`test_passed`, `test_status`, `test_output`, `test_run_at`). The `AttemptQuestion` dataclass also gained `test_suite` + the four `test_*` fields.
- `add_questions_to_quiz(quiz_id, questions: list[dict])` (ADR-037) takes a list of `{"prompt": str, "topics": list[str], "test_suite": str}` dicts (ADR-041 extended the dict with `test_suite`) and INSERTs one `questions` row per dict (with `section_id` from the Quiz, `topics` `'|'`-joined) plus one `quiz_questions` row, all in one transaction. `list_questions_for_quiz(quiz_id) -> list[Question]` (ADR-039) is a `quiz_questions ⨝ questions` join returning `Question` dataclasses. `_row_to_question(row)` converts a `sqlite3.Row` to a `Question`. `app/persistence/__init__.py` re-exports `Question` and the public functions.
- ADR-022's migration story: `CREATE TABLE IF NOT EXISTS` / `CREATE INDEX IF NOT EXISTS` are additive (idempotent); a column that can't be expressed that way goes through `_apply_additive_migrations(conn)` — a `PRAGMA table_info(<table>)` check + a guarded `ALTER TABLE <table> ADD COLUMN <col> <type>` (nullable; no `NOT NULL` without a default SQLite accepts on `ALTER`). ADR-037 added `quizzes.generation_error TEXT` via this mechanic; ADR-041 added `questions.test_suite TEXT`; ADR-044 added the four `attempt_questions.test_*` columns. A non-additive change (rename / re-constrain / drop) forces a follow-up ADR. ADR-033 flagged a "when the n-tables threshold makes the monolithic `_SCHEMA_SQL` block awkward → per-module schema-fragment refactor" forecast — not triggered by adding a *column*.
- MC-7: no `user_id` on any Quiz-domain table. MC-10: `import sqlite3` and SQL literals only under `app/persistence/`; callers receive dataclasses, never raw rows or `sqlite3.Connection`.

The decision space is small (the pattern is well-established; mirrors ADR-041 exactly):

- **The storage form.** A nullable `questions.preamble TEXT` column — vs. a `question_preambles` table (no real motivation; the preamble is small text, one-to-one with a Question; a join buys nothing) — vs. a `NOT NULL DEFAULT ''` column (complicates "no recorded preamble" semantics for legacy rows; nullable is the honest model — see Alternative B for the parallel argument from ADR-041).
- **Whether the column is in `_SCHEMA_SQL` or in `_apply_additive_migrations`.** Both, mirroring ADR-041 / ADR-044 / ADR-037's pattern: in the `CREATE TABLE questions` block for fresh DBs, and in `_apply_additive_migrations` for existing DBs. Idempotent in both places.
- **The `Question` dataclass field type.** `preamble: str | None` (mirroring `test_suite: str | None`) — nullable for legacy rows (a pre-TASK-018 Question has `preamble IS NULL`), non-null for newly-persisted rows (ADR-045's processor's `q.get("preamble", "")` defensive default means a Question always carries *something* — an empty string or a real preamble; the persisted column may hold `""` (a real "no shared shapes" semantic for a TASK-018+ Question) or `NULL` (a legacy pre-TASK-018 Question)).
- **The `add_questions_to_quiz` payload-dict shape.** No signature change; the per-Question dict gains a `"preamble"` key. The function reads `q.get("preamble", "")` (defensive; matches ADR-045's processor's defensive default). The `INSERT` gains the new column.
- **Whether a new accessor is needed.** No — `list_questions_for_quiz` (ADR-039) returns `Question` dataclasses whose fields are read by templates / route code; the dataclass just gains one more attribute. `get_question` (ADR-044) similarly. The runner-slice's "Run tests" route (ADR-043) already calls `get_question` to fetch a Question's `test_suite`; after this task it reads the returned `Question`'s `preamble` too. No new public function name; no new symbol re-exported.

The manifest constrains the decision: §5 ("No multi-user features" — no `user_id` on the new column; "No non-coding Question formats" — the column holds only source code, the shared struct/class shapes, never a non-coding artifact, by the same logic ADR-033 / ADR-041 establish), §7 ("Every Quiz Attempt, Note, and completion mark persists across sessions" — the preamble persists with the Question, which is part of the Bank, "never deleted" per §8), §8 (**Question Bank** — "Never deleted" — the preamble column is additive nullable; legacy rows keep `preamble IS NULL` and the runner's default-`""` splice handles them — ADR-047).

## Decision

### The storage — a nullable `questions.preamble TEXT` column, added via `_apply_additive_migrations` (mirroring ADR-041's `test_suite` recipe) and declared in the `CREATE TABLE questions` block in `_SCHEMA_SQL` for fresh databases

The `questions` table gains a column **`preamble TEXT`** — nullable, no default. NULL means "this row predates TASK-018 (no recorded preamble)"; an empty string means "this Question has been generated under TASK-018+ and the LLM declared it needs no shared shapes" (a real and valid semantic per ADR-045); a non-empty string means "this Question's shared struct/class shapes". The column is added two ways, both idempotent:

1. **In `_apply_additive_migrations(conn)`** in `app/persistence/connection.py` — a `PRAGMA table_info(questions)` check + a guarded `ALTER TABLE questions ADD COLUMN preamble TEXT`, mirroring the `questions.test_suite` precedent ADR-041 set (and the `quizzes.generation_error` precedent ADR-037 set, and the `attempt_questions.test_*` columns ADR-044 added). This is what brings an *existing* `data/notes.db` (one created before TASK-018) up to date — no migration-trigger fires (ADR-022's migration story: a nullable `ALTER TABLE ADD COLUMN` is additive).
2. **In the `CREATE TABLE IF NOT EXISTS questions` block in `_SCHEMA_SQL`** — the column is added to the `CREATE TABLE` statement so a *fresh* database (one created from scratch — e.g. a test's `NOTES_DB_PATH` monkeypatch) gets the column directly without needing the `ALTER` round-trip. This mirrors the pattern ADR-041 set for `test_suite`: the column is in *both* `_SCHEMA_SQL`'s `CREATE TABLE` block and `_apply_additive_migrations`'s check; the `PRAGMA table_info` check makes the `ALTER` a silent no-op when the column already exists from the `CREATE TABLE` block.

**Why a nullable column, not `NOT NULL DEFAULT ''`:** mirrors ADR-041's argument — a `DEFAULT ''` means a legacy Question with no recorded preamble reads back as `preamble = ''`, which is **indistinguishable from** the "TASK-018+ Question that needs no shared shapes" case (which legitimately stores `""` via the ADR-045 schema's `default=""`). Nullable is the honest model: NULL = "no recorded preamble" (legacy rows only, pre-TASK-018); `""` = "TASK-018+ Question, LLM declared no shared shapes needed" (a real semantic); a non-empty string = "the preamble's shared shapes". Three semantically distinct cases, two of which the column needs to distinguish (legacy vs no-shared-shapes); a `DEFAULT ''` collapses them.

(Note: this is a slightly different argument than ADR-041's: ADR-041 noted that in practice every TASK-016+ Question always has a non-empty `test_suite` (because ADR-040's failure handling refuses to persist a Question without one), so the nullable column's "no recorded test suite" semantic only applied to legacy rows. Here, ADR-045 deliberately keeps the empty-string-allowed semantic for `preamble`, so the column genuinely holds both `""` (TASK-018+, no shared shapes) and a non-empty string (TASK-018+, shared shapes) for TASK-018+ rows, plus NULL for legacy rows. The nullable column carries the three-way distinction cleanly.)

**Why a column, not a `question_preambles` table:** ADR-045 picked the single source-code-string representation for `preamble` (mirroring ADR-040's `test_suite`); a string is one TEXT column on `questions`, mirroring `prompt`, `topics`, and `test_suite` being columns. A `question_preambles` table would only make sense if a Question could have multiple preambles or if preambles were shared across Questions (they aren't — each Question carries its own; sharing is not in scope and would be a different ADR). ADR-033's "n-tables threshold → per-module schema-fragment refactor" forecast is **not triggered** — this task adds a *column* to an existing table, not a table.

### The `Question` dataclass — gains `preamble: str | None`

The `Question` dataclass in `app/persistence/quizzes.py` gains a field **`preamble: str | None`** (placed near `test_suite` — implementer's call; not architecture). `_row_to_question(row)` carries it through: `preamble=row["preamble"]` (the `sqlite3.Row` yields `None` for a NULL column — exactly the `str | None` the field models). The dataclass continues to model the `questions` table columns; `preamble` is `str | None` because the column is nullable (a legacy row has `preamble IS NULL`; a newly-persisted row may have `""` or a non-empty string). No `user_id` (MC-7).

The dataclass's docstring notes "the preamble holds shared struct/class/header source code the test suite and the learner's implementation both depend on (ADR-045); NULL only for a Question that predates TASK-018; an empty string is a real and valid semantic (a Question that needs no shared shapes, per ADR-045's empty-`preamble`-allowed rule); a non-empty string is the shared-shapes source."

### `add_questions_to_quiz` — the per-Question payload dict gains a `"preamble"` key (no signature change)

`add_questions_to_quiz(quiz_id, questions: list[dict])` is **unchanged in signature**; each dict in `questions` now carries a `"preamble"` key. The function reads `q.get("preamble", "")` (defensive default of empty string, matching ADR-045's processor's defensive default for an artefact that omits the key entirely). The function's INSERT gains the column:

```
INSERT INTO questions (section_id, prompt, topics, test_suite, preamble, created_at)
VALUES (?, ?, ?, ?, ?, ?)
```

— `preamble` from `q.get("preamble", "")`. The `quiz_questions` INSERT and the one-transaction discipline are unchanged. The docstring's `[{"prompt": str, "topics": list[str], "test_suite": str}, ...]` becomes `[{"prompt": str, "topics": list[str], "test_suite": str, "preamble": str}, ...]`; the docstring's "the caller is responsible for sanity-checking that questions is non-empty and each prompt is non-empty (ADR-037), each test_suite is non-empty (ADR-040)" note gains "; preamble may be empty — an empty preamble is a real and valid semantic (ADR-045)". MC-2 unchanged (every Question carries the Quiz's `section_id`); MC-10 unchanged (SQL stays here); no `user_id` (MC-7).

### `list_questions_for_quiz` and `get_question` — the `SELECT` carries `q.preamble` through; no signature change

`list_questions_for_quiz`'s `SELECT q.question_id, q.section_id, q.prompt, q.topics, q.test_suite, q.created_at` (ADR-039 / ADR-041) gains `q.preamble` (so `_row_to_question` can read it via `row["preamble"]`); the function's signature and return type are unchanged (the returned `Question` dataclass just carries one more attribute).

`get_question(question_id) -> Question | None` (ADR-044)'s `SELECT` similarly gains `preamble`; its signature and return type are unchanged. The "Run tests" route (ADR-043) which already calls `get_question` to fetch a Question's `test_suite` for the sandbox now also reads the returned `Question`'s `preamble` and passes it to `run_test_suite(test_suite, response, preamble)` (ADR-047 owns the sandbox-side mechanics). The take-page render (ADR-038 / ADR-043 / ADR-047) reads the `preamble` field from the `AttemptQuestion` dataclass (which `list_attempt_questions` ADR-044 returns via the join with `questions`).

### `AttemptQuestion` — gains `preamble: str | None` carried through from the `questions ⨝ attempt_questions` join in `list_attempt_questions`

`list_attempt_questions(attempt_id) -> list[AttemptQuestion]` (ADR-039 / ADR-044) joins `attempt_questions` with `questions` to carry the Question's `prompt`, `test_suite`, and `quiz_questions.position` into the returned dataclass; the join's `SELECT` gains `q.preamble`. The `AttemptQuestion` dataclass gains a `preamble: str | None` attribute that the take template reads to decide whether to render the read-only `<pre class="quiz-take-preamble">` block (ADR-047) and what it contains. No signature change to `list_attempt_questions`.

### No new public function this task — the existing accessors carry the new field through

`app/persistence/__init__.py`'s re-exports are unchanged (`Question` and `AttemptQuestion` are already re-exported; they just carry one more attribute each). No new function name; no new symbol. The "Run tests" route uses `get_question` (already exists, ADR-044); the take template reads `aq.preamble` from `AttemptQuestion` (the dataclass that `list_attempt_questions` already returns); the processor passes `"preamble"` in the per-Question dict to `add_questions_to_quiz` (already exists, ADR-037).

### Scope of this ADR

This ADR fixes only:

1. **The storage:** a nullable `questions.preamble TEXT` column — added via `_apply_additive_migrations`'s `PRAGMA table_info(questions)` check + `ALTER TABLE questions ADD COLUMN preamble TEXT` (mirroring ADR-041's `test_suite` and ADR-037's `generation_error`), and declared in the `CREATE TABLE IF NOT EXISTS questions` block in `_SCHEMA_SQL` for fresh databases. Additive per ADR-022; no migration-trigger; ADR-033's n-tables-threshold refactor not triggered (a column, not a table).
2. **The `Question` dataclass:** gains `preamble: str | None`; `_row_to_question` carries it through; no `user_id`.
3. **`add_questions_to_quiz`:** signature unchanged; the per-Question payload dict gains a `"preamble"` key (defensive default `""`); the `INSERT` gains the column; the one-transaction discipline unchanged.
4. **`list_questions_for_quiz` and `get_question` `SELECT`:** add `q.preamble`; no signature changes; the returned `Question` dataclass carries the new attribute.
5. **`AttemptQuestion` dataclass:** gains `preamble: str | None` carried through from the `questions ⨝ attempt_questions` join in `list_attempt_questions`; no signature change.
6. **No new public function** this task (`app/persistence/__init__.py` re-exports unchanged); the existing `Question`-returning accessors carry the new field through.

This ADR does **not** decide:

- **The `question_gen` prompt + schema decisions** — owned by **ADR-045**.
- **The sandbox splice extension and the take-surface `preamble` block** — owned by **ADR-047**.
- Any **`questions`-delete path** (there isn't one — ADR-033's "never deleted; only superseded by content reorganization"; adding one is not in scope).
- Any **`questions` schema change beyond the additive `preamble` column** (no rename, no re-constrain, no new table; the relational Topic vocabulary stays deferred).
- Whether `preamble` should carry metadata (a declared language / `#include` list / entry-point name) alongside the source code — a future ADR adds those as additional nullable columns if a runner slice wants them; the `preamble` string stays the runnable source. Bounded.

## Alternatives considered

**A. A `question_preambles` table (one-to-one with `questions`, joined on `question_id`), instead of a `questions.preamble TEXT` column.**
Rejected. The preamble is one-to-one with a Question, the LLM emits it as a single string, and there is no use case for querying preambles independently of their Questions. A `question_preambles` table is more surface (a join, a row-per-Question that doesn't currently exist, ADR-033's "n-tables threshold" closer) for no benefit — a TEXT column on `questions` is the simplest fit, mirroring how `prompt`, `topics`, and `test_suite` are columns on the same table. (If a future slice wants to share preambles across Questions or version them — neither in scope — a future ADR can supersede this one and migrate the column to a table; the migration is additive (`CREATE TABLE IF NOT EXISTS`); bounded.)

**B. A `NOT NULL DEFAULT ''` column instead of a nullable one.**
Rejected. SQLite *can* `ALTER TABLE ADD COLUMN preamble TEXT NOT NULL DEFAULT ''` — but a `DEFAULT ''` collapses two semantically distinct cases that the column needs to distinguish:
- **Legacy row (pre-TASK-018):** no recorded preamble — the row predates the column.
- **TASK-018+ row with no shared shapes:** the Pydantic schema's `default=""` produced `""`, which the processor passes through; the Question genuinely needs no shared shapes (ADR-045's empty-`preamble`-allowed rule).
A `DEFAULT ''` would read both back as `preamble = ''`, with no way to tell them apart. Nullable is the honest model: NULL = legacy; `""` = TASK-018+, no shared shapes; non-empty = TASK-018+, shared shapes. This is the same shape as ADR-041's nullable-vs-`NOT NULL` argument, with a slight twist: ADR-041's `test_suite` couldn't *legitimately* be `""` for a TASK-016+ row (the `min_length=1` validator + the bad-`test_suite` whole-Quiz `generation_failed` path forbid it), so `test_suite = ''` was honestly only a "DB-default artefact" case; here `preamble = ''` is genuinely valid for TASK-018+, so the nullable column has to carry the three-way distinction.

**C. Add `preamble` only to `_SCHEMA_SQL`'s `CREATE TABLE questions` block, not to `_apply_additive_migrations`.**
Rejected — mirrors ADR-041's Alternative C: an existing `data/notes.db` (one created before TASK-018) already has a `questions` table; `CREATE TABLE IF NOT EXISTS` is a no-op on it, so the column would never get added to an existing DB. The `_apply_additive_migrations` `PRAGMA table_info` + `ALTER` path is what upgrades an existing DB.

**D. Add a new accessor (e.g. `get_preamble_for_question(question_id) -> str | None`) this task.**
Rejected — premature; the existing accessors carry the new field through (`get_question` returns the `Question` dataclass which now carries `preamble`; `list_attempt_questions` returns `AttemptQuestion` which now carries `preamble` via the join). The "Run tests" route already calls `get_question`; it reads one more attribute on the returned dataclass. The take template reads `aq.preamble` from the existing `AttemptQuestion` dataclass. Adding a dedicated single-field accessor would be an accessor with no caller — the architecture-on-spec anti-pattern that ADR-041 §No new accessor rejected. (If a future surface genuinely needs a single-field accessor for a unit test or a non-Question consumer, that's a small implementer addition; not architecture.)

**E. Fold this ADR into ADR-045 (one ADR, not two).**
Considered. Rejected for record-keeping: the ADR-040 / ADR-041 split established the precedent (representation/workflow/processor/failure/surface in ADR-040; persistence storage mechanics in ADR-041), and the precedent works well. Each ADR is independently citable, each focused on one concern, each smaller to read. The cost is one more ADR file; the gain is editorial clarity. Same call as ADR-041's Alternative E.

## My recommendation vs the user's apparent preference

Aligned with the user's apparent preference, captured in the TASK-018 task file's "Architectural decisions expected" section (which forecast this ADR as either a section of the prompt ADR or a small companion — `/design`'s call; the architect picked the split, mirroring ADR-040 / ADR-041). The task's specific forecasts — nullable additive `preamble TEXT` column; `Question.preamble: str | None`; `add_questions_to_quiz` no signature change, payload-dict gains a `"preamble"` key; `list_questions_for_quiz` / `get_question` carry the field through; no new accessor; SQL stays under `app/persistence/` (MC-10); no `user_id` (MC-7) — are all adopted exactly as forecast. No disagreement to surface; this is the obvious shape and follows the codebase's existing patterns (the `questions.topics` handling, the `questions.test_suite` recipe, the `_apply_additive_migrations` mechanic, the `Question`-returning accessor shape, the `AttemptQuestion` join carry-through).

The one architect's-judgement call recorded here (not a disagreement with the user, an architect's affirmation of the cleanest form): **the nullable column's three-way semantic distinction** (NULL = legacy / `""` = TASK-018+ no shared shapes / non-empty = TASK-018+ shared shapes). The task's forecast leaned `str = Field(default="")` at the Pydantic layer (which means TASK-018+ rows always have *something* in the column — either `""` or the LLM's output); this ADR pins the storage column as nullable to keep the legacy-vs-TASK-018+-no-shapes distinction tractable. This is the right shape and matches ADR-041's nullable-`test_suite` precedent; explicit here so the implementer doesn't accidentally write `NOT NULL DEFAULT ''` and quietly lose the distinction.

I am NOT pushing back on:

- ADR-041's `questions.test_suite` recipe — consumed unchanged (mirrored exactly for `preamble`).
- ADR-033's `questions` schema — consumed unchanged (the new column is additive; the no-non-coding-column posture is preserved).
- ADR-022's persistence boundary and additive-migration story — preserved.
- ADR-039's `Question`-returning accessor pattern — consumed unchanged (one more attribute on the returned dataclass).
- ADR-044's `get_question` accessor and `AttemptQuestion` extension — consumed unchanged (one more attribute on each returned dataclass).
- ADR-037's generation processor — consumed unchanged (one more key in the per-Question dict passed to `add_questions_to_quiz`; the lifecycle / failure-handling unchanged).
- MC-7 (single user) — preserved (no `user_id` on the new column or the new dataclass field).
- MC-10 (persistence boundary) — preserved (DDL in `connection.py`, dataclass / converter / accessors in `app/persistence/quizzes.py`; SQL literals stay there; no `sqlite3` import outside `app/persistence/`).

## Manifest reading

Read as binding for this decision:

- **§5 Non-Goals.** "No non-coding Question formats" — the `preamble` column holds only source code (the shared struct/class shapes), never a non-coding artifact; mirrors `test_suite` and `prompt`. "No multi-user features" — no `user_id` on the new column or the new dataclass field. "No in-app authoring of lecture content" — the preamble is generated by `question_gen` (read-only to `content/latex/`) and persisted to `data/notes.db`'s `questions.preamble`; nothing under `content/latex/` is opened for write.
- **§7 Invariants.** "Every Quiz Attempt, Note, and completion mark persists across sessions" — the preamble persists with the Question. "Single-user" — no `user_id`.
- **§8 Glossary.** **Question Bank** — "Never deleted" — the preamble column is additive nullable; legacy rows keep `preamble IS NULL` and the runner's default-`""` splice handles them (ADR-047); the Bank's no-delete posture is preserved.

No manifest entries flagged as architecture-in-disguise. The column-vs-table choice, the nullable-vs-`NOT NULL` decision, and the dataclass-field placement are operational architecture the manifest delegates to "the architecture document".

## Conformance check

- **MC-1 (No direct LLM/agent SDK use).** Vacuously preserved — `app/persistence/quizzes.py` and `app/persistence/connection.py` import no AI; the new column / field / payload key are all persistence-layer mechanics. **PASS.**
- **MC-2 (Quizzes scope to one Section).** Honored — the preamble is per Question; each Question carries the Quiz's `section_id` (unchanged); no cross-Section composition. **PASS.**
- **MC-3 (Mandatory/Optional designation).** Orthogonal — no designation column on the new field. **PASS.**
- **MC-4 (AI work asynchronous).** Vacuously preserved — persistence does no AI. **PASS.**
- **MC-5 (AI failures surfaced, never fabricated).** Honored — the persistence layer faithfully stores whatever ADR-045's processor passes (a non-empty string or `""`); no fabrication; the bad-`test_suite` whole-Quiz `generation_failed` path (ADR-040) is enforced upstream in the processor, not here; this ADR does not weaken that path. **PASS.**
- **MC-6 (Lecture source read-only).** Honored — the new column is in `data/notes.db`; nothing under `content/latex/` is touched. **PASS.**
- **MC-7 (Single user).** Honored — no `user_id` on the new `questions.preamble` column, the `Question.preamble` field, or the `AttemptQuestion.preamble` field. **PASS.**
- **MC-8 (Reinforcement loop preserved).** Orthogonal — persistence doesn't shape the loop; the loop is composition + generation + grading. **PASS.**
- **MC-9 (Quiz generation user-triggered).** Orthogonal — persistence doesn't trigger generation. **PASS.**
- **MC-10 (Persistence boundary).** Honored — `import sqlite3` and SQL literals stay under `app/persistence/`; the new `questions.preamble` column's DDL goes in `connection.py` (via the `PRAGMA table_info` additive-`ALTER` check + the `CREATE TABLE` block); the dataclass / converter / payload changes are in `app/persistence/quizzes.py`; the processor (`process_quiz_requests.py`), the route (`app/main.py`), and the templates call only the typed public functions from `app/persistence/__init__.py` — they never receive a `sqlite3.Connection` or a raw row tuple. **PASS.**

No previously-dormant rule is activated.

## Consequences

**Becomes possible:**

- A Question's preamble persists in `data/notes.db`'s `questions.preamble` column (and is round-trip through `add_questions_to_quiz` → `list_questions_for_quiz` / `get_question` / `list_attempt_questions`).
- The "Run tests" route (ADR-043 / ADR-047) reads a Question's preamble via `get_question` and passes it to the sandbox's splice.
- The take page (ADR-043 / ADR-047) reads the preamble via the `AttemptQuestion` dataclass and renders a read-only block when present.
- Pre-TASK-018 Questions in the Bank stay valid as-is with `preamble IS NULL`; the runner's default-`""` `preamble` path (ADR-047) handles them byte-equivalently to ADR-042's pre-task splice.

**Becomes more expensive:**

- `app/persistence/quizzes.py` grows the `Question` dataclass field, the `_row_to_question` line, the `add_questions_to_quiz` INSERT change, the `list_questions_for_quiz` / `get_question` `SELECT` change, the `AttemptQuestion` dataclass field, and the `list_attempt_questions` join `SELECT` change. Mitigation: ~6 small changes mirroring the `test_suite` pattern ADR-041 set; small.
- `app/persistence/connection.py` grows two `preamble TEXT` declarations (the `CREATE TABLE questions` block and the `_apply_additive_migrations` `ALTER`). Mitigation: ~2 lines.

**Becomes impossible (under this ADR):**

- A `questions` schema change that re-constrains or drops the column (any such change forces a follow-up ADR per ADR-022's migration story).
- The preamble being written under `content/latex/` (it goes to `data/notes.db`).
- A non-coding artifact in the preamble column (the schema's `extra="forbid"` upstream (ADR-045) and the column's TEXT-source-code-only contract enforce this — the persistence layer accepts whatever ADR-045's processor passes).

**Future surfaces this ADR pre-positions:**

- A future ADR adding metadata to `preamble` (a declared language / `#include` list / entry-point name) — additive (more nullable columns).
- A future ADR migrating `questions.preamble` to a shared / versioned `question_preambles` table — additive (`CREATE TABLE IF NOT EXISTS`); bounded.

**Supersedure path if this proves wrong:**

- If the column form proves wrong (a runner slice's `/design` wants metadata alongside the source) → a future ADR adds nullable columns; bounded.
- If the nullable-column three-way semantic distinction proves unnecessary (e.g. the grading slice doesn't care about legacy preambles) → a future ADR can collapse to `NOT NULL DEFAULT ''` with a one-time backfill; bounded.

The supersedure path runs through a new ADR. This ADR does not edit any prior ADR in place; it builds on ADR-041 (the recipe this mirrors), ADR-044 (the `get_question` accessor and `AttemptQuestion` extension this carries the new field through), ADR-033 (the schema this extends), ADR-022 (the migration story), ADR-039 (the existing accessor pattern), ADR-037 (the processor whose payload-dict gains one key).
