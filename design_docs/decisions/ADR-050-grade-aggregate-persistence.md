# ADR-050: The Grade aggregate's persistence — a new `grades` table (PK `attempt_id` FK → `quiz_attempts`; `score INTEGER NOT NULL`, `weak_topics TEXT NOT NULL DEFAULT ''`, `recommended_sections TEXT NOT NULL DEFAULT ''`, `graded_at TEXT NOT NULL`); a new nullable `quiz_attempts.grading_error TEXT` column (additive, mirroring ADR-037's `generation_error`); both declared in `_SCHEMA_SQL` (fresh DBs) and added via `_apply_additive_migrations` (existing DBs); `attempt_questions.is_correct` / `.explanation` now writeable by the grading slice (the NULL-until-graded columns ADR-033 reserved); a new `Grade` dataclass; `AttemptQuestion` carries `is_correct: bool | None` and `explanation: str | None` through `list_attempt_questions`'s existing join; new persistence functions `list_submitted_attempts`, `mark_attempt_grading`, `save_attempt_grade` (one transactional save-or-fail; recomputes `score` from `is_correct`), `mark_attempt_grading_failed`, `mark_attempt_graded`, `get_grade_for_attempt`; the `test_passed` → `is_correct` mapping (`True`→1, `False`→0, `None`/`'not_run'`→0); `weak_topics` / `recommended_sections` persist as `'|'`-delimited TEXT (the relational `topics` table stays deferred to the composition slice); SQL stays under `app/persistence/`; no `user_id`

**Status:** `Accepted`
Auto-accepted by /auto on 2026-05-13
**Date:** 2026-05-13
**Task:** TASK-019
**Resolves:** part of `design_docs/project_issues/quiz-grading-slice-shape.md` (with ADR-048 + ADR-049 + ADR-051) — the "Grade aggregate's schema" question (a separate `grades` table) and the "Topic vocabulary handling" question (stays as `'|'`-delimited TEXT for now; the relational `topics` table deferred to the composition slice)
**Supersedes:** none — consumes **ADR-022** (the persistence boundary; `import sqlite3` and SQL literals stay under `app/persistence/`; the additive-migration story — `CREATE TABLE IF NOT EXISTS` for fresh DBs, `PRAGMA table_info`-guarded `ALTER TABLE ADD COLUMN` for existing DBs in `_apply_additive_migrations`), **ADR-033** (the `quiz_attempts.status` enum's `grading` / `graded` / `grading_failed` reserved states; the `attempt_questions.is_correct` / `.explanation` columns NULL-until-graded — this slice makes them writeable; the `'|'`-delimited Topics-column convention from `questions.topics` that `weak_topics` / `recommended_sections` mirror; the "Grade schema deferred to the grading task" forecast this ADR resolves), **ADR-037** (the `quizzes.generation_error TEXT` precedent the new `quiz_attempts.grading_error TEXT` column mirrors recipe-for-recipe), **ADR-039** (the Attempt-lifecycle persistence layer this extends — `start_attempt` / `submit_attempt` / `get_attempt` / `get_latest_attempt_for_quiz` / `list_questions_for_quiz` / `list_attempt_questions` / `save_attempt_responses` unchanged in signature; `list_attempt_questions` and `_row_to_attempt_question` extend to carry the now-writeable `is_correct` / `explanation` through the existing `attempt_questions ⨝ questions` join; `AttemptQuestion` dataclass gains two fields), **ADR-041 / ADR-044 / ADR-046** (the additive-column precedents — `questions.test_suite`, `attempt_questions.test_*`, `questions.preamble`; the `_apply_additive_migrations` `PRAGMA table_info` pattern this ADR's `grading_error` column reuses), **ADR-048** (the workflow's `GradeAttemptOutput` shape this persistence layer maps from — `per_question[i].explanation`, `score`, `weak_topics`, `recommended_sections`), **ADR-049** (the processor calls the new persistence functions; the score cross-check architecture is realized here via `SUM(is_correct)` recompute), **ADR-042/ADR-044** (the runner's `attempt_questions.test_passed` is the source of truth this ADR's `is_correct` mapping reads — `True`→1, `False`→0, `None`/`'not_run'`→0 — making `is_correct` a function of the test result per the §8 amendment), and **MC-7 / MC-10** (no `user_id`; SQL stays under `app/persistence/`). No prior ADR is re-decided.

## Context

The §8 amendment defined a Grade as a four-facet aggregate (per-Question correctness + per-Question explanation + an aggregate score + identified Weak Topics + recommended Sections to re-read). ADR-033 deferred the Grade's *home* to the grading task with the forecast "the schema is additive either as a separate `grades` table or as nullable columns on `quiz_attempts`"; ADR-033 made `attempt_questions.is_correct` and `.explanation` NULL until graded, the explicit forecast being "the grading slice writes them". ADR-037 set the precedent for additive failure-detail columns (`quizzes.generation_error TEXT`, nullable, `_apply_additive_migrations`-installed). ADR-048 decided the workflow's output shape — `GradeAttemptOutput.per_question: list[QuestionGrade]` (one `explanation` per Question), `score: int`, `weak_topics: list[str]`, `recommended_sections: list[str]`, with **no `is_correct` field** in `QuestionGrade` (the §8-honest commitment that correctness is the runner's verdict, not the LLM's judgment). ADR-049 decided the processor: it parses the workflow artefact, validates it, and calls one transactional persistence function that maps the runner's `test_passed` to `is_correct`, persists the per-Question explanations, INSERTs a `grades` row with the score *recomputed* from the persisted `is_correct` values, and flips `quiz_attempts.status` to `graded`. This ADR owns the persistence-layer half — the schema, the migration, the new dataclasses, the new functions, the existing-function carry-throughs, and the `test_passed` → `is_correct` mapping.

The decision space:

- **Where the Grade aggregate lives.** A separate `grades` table (PK `attempt_id`, FK to `quiz_attempts`) — vs nullable columns on `quiz_attempts` (`score INTEGER`, `weak_topics TEXT`, `recommended_sections TEXT`). ADR-033 records both as additive. The architect's call between the two; the rest of the slice is structurally orthogonal (the processor calls one persistence function either way; the take-page render reads the Grade either way; the dataclass shape differs but the consumer doesn't care).
- **Where the per-Question correctness + explanation live.** The existing `attempt_questions.is_correct INTEGER` and `attempt_questions.explanation TEXT` columns (ADR-033, NULL until graded) — vs new columns somewhere. ADR-033 already chose: `attempt_questions` carries them. This ADR just makes them *writeable* and surfaces them on the `AttemptQuestion` dataclass.
- **The `test_passed` → `is_correct` mapping.** A `test_passed = True` → `is_correct = 1` and `False` → `0` is mechanical. The non-trivial case is `None` (the learner submitted without running the tests, `test_status = NULL`) or `'not_run'` / `'timed_out'` / `'compile_error'` / `'setup_error'` (the run did not produce a verdict). Three options: (i) `is_correct = NULL` (no verdict yet — but then the Attempt is "graded" with NULL is_correct values, semantically incoherent — graded means everything was decided); (ii) `is_correct = 0` (treat any non-pass as incorrect — penalizes the learner for not running but is consistent with §8's "passed the test" framing — failing to run *is* failing to pass); (iii) `grading_failed` for any Attempt with a NULL `test_status` (refuse to grade an Attempt that wasn't fully test-run — but then a learner who skipped one Question's run for any reason can't ever get the Attempt graded, which is harsh). The architect picks (ii) — `None`/non-`'ran'` → `is_correct = 0` — with the *explanation* surfacing the failure mode honestly (the workflow prompt instructs the LLM to acknowledge `test_status = 'not_run'` / `compile_error` / etc.); this is MC-5's spirit (the failure is honest, not hidden) and §8's letter (the test didn't pass → not correct).
- **The Weak-Topics / recommended-Sections persisted form.** `list[str]` exposed publicly, persisted as `'|'`-delimited TEXT (mirroring `questions.topics` per ADR-033) — vs a relational `topics` table + `question_topics` + `attempt_weak_topics` join. The relational form's value is the cross-Section / cross-Attempt query (the composition slice's MC-8 read needs "all Questions tagged with Topic X in this Section's Bank"); for *this* slice (which only writes per-Attempt Weak Topics and reads them only on the take page), the delimited TEXT form is sufficient and the migration to the relational form is additive when the composition slice's `/design` triggers it.
- **The score cross-check.** ADR-049 records the architectural commitment ("the persisted `score` is recomputed from `is_correct`, not taken verbatim from the workflow"); this ADR owns the *implementation* — the `save_attempt_grade` function recomputes `score = SUM(is_correct)` in the same transaction as the per-Question writes, *after* the `is_correct` UPDATEs land. The transactional discipline guarantees the score is the truth of what was persisted.
- **The new persistence functions' shapes and signatures.** Five new functions (mirroring ADR-037's `mark_quiz_*` family for the lifecycle transitions, plus ADR-049's transactional save). One read accessor for the take-page render. `_row_to_grade` row→dataclass converter (mirroring `_row_to_quiz` / `_row_to_question`). All under `app/persistence/quizzes.py` (the Quiz-domain module), re-exported from `app/persistence/__init__.py`.
- **The migration story.** Additive — a new table `CREATE TABLE IF NOT EXISTS grades` in `_SCHEMA_SQL` (fresh DBs) plus a `sqlite_master`-existence check + `CREATE TABLE` in `_apply_additive_migrations` (existing DBs); a new nullable `quiz_attempts.grading_error TEXT` column added by the `PRAGMA table_info(quiz_attempts)` check + `ALTER TABLE … ADD COLUMN` (existing DBs) and in the `CREATE TABLE quiz_attempts` block (fresh DBs). No migration-trigger fires; ADR-033's "n-tables threshold → per-module schema-fragment refactor" forecast — re-evaluate: with `grades` this slice adds the *sixth* Quiz-domain table (`quizzes`, `questions`, `quiz_questions`, `quiz_attempts`, `attempt_questions`, now `grades`). The threshold has not been quantified ("when the n-tables threshold makes the monolithic `_SCHEMA_SQL` block awkward"); five tables of bootstrap-DDL plus the `_apply_additive_migrations` additions is *not yet* awkward (the `_SCHEMA_SQL` block is ~80 lines including comments; readable). The refactor is **not** triggered by this slice; the composition slice may trigger it if it adds a `topics` table + `question_topics` join + `notifications` table simultaneously.

The manifest constrains the decision through **§5** ("No multi-user features" — no `user_id` on the new `grades` table or the `grading_error` column; manifest-level constraint, not bypassable), **§6** ("AI failures are visible. If AI-driven processing fails, the failure is surfaced to the learner as a failure. The system never fabricates a result" — the transactional save-or-fail is the implementation of this commitment for the persistence layer; the `grading_error` column is the debugging-aid form), **§7** ("Every Quiz Attempt … persists across sessions" — the Grade persists with the Attempt; "Every Question is a hands-on coding task" — the per-Question `explanation` is *commentary on coding*, not a non-coding artifact; the column type is plain TEXT — no choice / option / recall fields), and **§8** (the Grade glossary's four facets; the Weak-Topic glossary's "drives the fresh-Question portion of subsequent Quizzes for the same Section" — the persisted Weak Topics list is what the composition slice reads).

## Decision

### The Grade aggregate's home — a separate `grades` table (PK `attempt_id`, FK to `quiz_attempts`)

`data/notes.db` gains a new table **`grades`** (declared in `_SCHEMA_SQL`'s `CREATE TABLE IF NOT EXISTS grades` block for fresh DBs; created in `_apply_additive_migrations` via a `SELECT name FROM sqlite_master WHERE type='table' AND name='grades'` existence check + a `CREATE TABLE IF NOT EXISTS grades …` for existing DBs — idempotent; mirrors how ADR-033's `CREATE TABLE IF NOT EXISTS` blocks landed but lifted into the migrations function for old DBs that were created before this ADR; alternatively, since `CREATE TABLE IF NOT EXISTS` is idempotent on any DB, the existence check is redundant and the same statement can live in just `_SCHEMA_SQL` — implementer's call between "one place" and "match the ALTER-column pattern's two-place declaration"; both are additive per ADR-022):

```sql
CREATE TABLE IF NOT EXISTS grades (
    attempt_id            INTEGER PRIMARY KEY REFERENCES quiz_attempts (attempt_id),
    score                 INTEGER NOT NULL,
    weak_topics           TEXT    NOT NULL DEFAULT '',
    recommended_sections  TEXT    NOT NULL DEFAULT '',
    graded_at             TEXT    NOT NULL
);
```

Why a separate table, not nullable columns on `quiz_attempts`:

- **Clean 1:1 to the Attempt with a PK on `attempt_id`.** A `graded` Attempt has exactly one `grades` row; a `submitted` / `grading` / `grading_failed` Attempt has zero. The presence of the `grades` row *is* the persisted Grade — no NULL-as-meaningful semantic to disambiguate ("`score = NULL` means ungraded" is ambiguous with "the LLM produced `score = NULL` as a real value", a class of confusion the separate table avoids).
- **Keeps `quiz_attempts` lean.** `quiz_attempts` already carries `attempt_id` / `quiz_id` / `status` / `created_at` / `submitted_at` / `graded_at` plus the new `grading_error` column (added below). Adding three more nullable aggregate columns (`score`, `weak_topics`, `recommended_sections`) on top of that pushes more lifecycle state and aggregate data into one wide row; the separate table keeps `quiz_attempts` focused on lifecycle and the Grade focused on aggregate.
- **Easier to extend.** A future "grader provenance" addition (`grader_model TEXT`, `grader_run_id TEXT`, `cost_usd REAL`) goes on `grades` without touching `quiz_attempts` — and `quiz_attempts` would otherwise grow more nullable provenance columns. A future "multiple graders per Attempt" extension (a `grades` row per grader) is a small refactor (`PRIMARY KEY (attempt_id, grader_run_id)`) on the `grades` table only; on the columns-on-`quiz_attempts` shape it'd be a much bigger refactor (split the Grade out into a new table; old code reads the deprecated columns).
- **The composition slice's read** (the next slice; reads the most recent `graded` Attempt's Weak Topics for the Section to drive the fresh portion of the next Quiz) — a join `grades ⨝ quiz_attempts ⨝ quizzes WHERE quizzes.section_id = ?` reads naturally; on the columns-on-`quiz_attempts` shape the join is shorter but the columns are mixed in with lifecycle columns.
- **`graded_at` already exists on `quiz_attempts`** (ADR-033) — it stays there, and `grades.graded_at` is a duplicate-or-cross-check column. The architect chooses to keep both: `quiz_attempts.graded_at` is the lifecycle timestamp (set when the status flips to `graded`); `grades.graded_at` is the Grade's birth timestamp (set when the `grades` row is INSERTed). In one transaction (ADR-049's `save_attempt_grade`) they are equal by construction; they could diverge under a future "re-grade in place" path (which would update `grades.graded_at` but not necessarily `quiz_attempts.graded_at`, since the Attempt was originally graded earlier). For *this* slice they are equal; the redundancy is cheap and forward-flexible.

The trade-offs of the columns-on-`quiz_attempts` alternative — fewer tables to learn; one less join; the natural NULL-as-ungraded read; ADR-033's "n-tables threshold" stays farther away — are real but minor; the architect picks the separate table for the cleanness arguments above.

### The `quiz_attempts.grading_error TEXT` column — new, nullable, additive (mirroring ADR-037's `generation_error`)

`quiz_attempts` gains a new column **`grading_error TEXT`** — nullable, no default. NULL for every non-failed Attempt; on failure, written by `mark_attempt_grading_failed(attempt_id, error=...)` with the failure detail string (mirroring ADR-037's `mark_quiz_generation_failed` exactly). Added two ways, both idempotent (the recipe ADR-037 / ADR-041 / ADR-044 / ADR-046 all established):

1. **In `_apply_additive_migrations(conn)`** — a `PRAGMA table_info(quiz_attempts)` check + a guarded `ALTER TABLE quiz_attempts ADD COLUMN grading_error TEXT`. The fifth row in the existing migration-block pattern; mirrors `quizzes.generation_error`.
2. **In the `CREATE TABLE IF NOT EXISTS quiz_attempts` block in `_SCHEMA_SQL`** — `grading_error TEXT` after `graded_at`. Fresh DBs get the column directly.

Why nullable and not `NOT NULL DEFAULT ''`: same argument as ADR-037 / ADR-041 / ADR-046 — `''` and NULL would collapse the "no recorded error" semantic with the "the error was the empty string" semantic; nullable is the honest model. (In practice the failure detail will never legitimately be the empty string — the processor writes a non-empty string on every failure path; but the column is for `grading_error IS NULL` semantically meaning "no failure recorded for this Attempt", which `IS NULL` distinguishes from "" cleanly.)

The learner-facing signal stays the honest "Grading failed" (ADR-051's render) — the `grading_error` column is a debugging aid for the author (mirroring how `generation_error` is used). ADR-051's call on whether to expose the detail to the learner; the architect forecasts "yes, in a small details expander" — the author *is* the learner here, and an honest failure-mode read is more useful than a generic message; but the architectural commitment is "the learner-facing primary signal is the honest failure"; the details expander is a render-side enhancement.

### The `attempt_questions.is_correct` and `.explanation` columns — writeable by the grading slice

ADR-033's `attempt_questions` already declares `is_correct INTEGER` and `explanation TEXT` (both NULL until graded). This ADR makes them *writeable*:

- `is_correct` is set by `save_attempt_grade` (the transactional persistence function) — `INTEGER` storing `1` for correct, `0` for incorrect. Derived from `attempt_questions.test_passed` per the mapping below.
- `explanation` is set by `save_attempt_grade` — `TEXT`, from `GradeAttemptOutput.per_question[i].explanation` matched by `question_id`.

No schema change to `attempt_questions` (the columns already exist); the dataclass and the accessor join just need to carry them through.

#### The `test_passed` → `is_correct` mapping

Reading `attempt_questions.test_passed` and `attempt_questions.test_status` (the runner's persisted columns — ADR-044):

| `test_status`        | `test_passed` | `is_correct` |
|---------------------|---------------|--------------|
| `'ran'`             | `1` (True)    | `1`          |
| `'ran'`             | `0` (False)   | `0`          |
| `'timed_out'`       | NULL          | `0`          |
| `'compile_error'`   | NULL          | `0`          |
| `'setup_error'`     | NULL          | `0`          |
| NULL (`test_run_at IS NULL` — never ran) | NULL | `0`     |

The "ran-and-passed" case → correct; every other case → not correct. The §8 amendment's "correctness determined by whether the learner's code passed the Question's tests" is satisfied: passed → correct; not-passed (for any reason) → not correct. The *explanation* (which the workflow produces) is what carries the nuance — "your code timed out", "didn't compile", "you didn't run the tests", "the assertion failed" — so the learner is not given a bare "incorrect" without context.

This mapping is implemented in the persistence layer (in `save_attempt_grade` or a small helper), not in the workflow — keeping the §8 commitment "correctness = runner's verdict" architecturally honest. The workflow does not get to override the mapping; it produces only the explanation.

(An alternative considered — treat `None` as `is_correct = NULL` so a `graded` Attempt can carry "no verdict yet" semantics — is rejected because a `graded` Attempt is semantically "all decided", and a NULL `is_correct` on a `graded` row is a contradiction. The MC-5-honest read is: failure to pass = not correct, with the explanation surfacing why.)

### The score cross-check — recomputed from `is_correct` in the same transaction, not taken verbatim from the workflow

ADR-049's architectural commitment ("the persisted `score` is recomputed from `SUM(is_correct)`, not taken verbatim") is implemented here. `save_attempt_grade` executes, in order, in one transaction:

1. **`UPDATE attempt_questions SET is_correct = ?, explanation = ? WHERE attempt_id = ? AND question_id = ?`** — one statement per Question in the Attempt; `is_correct` from the mapping above, `explanation` from `GradeAttemptOutput.per_question[i].explanation`.
2. **`SELECT COALESCE(SUM(is_correct), 0) FROM attempt_questions WHERE attempt_id = ?`** — read the just-persisted truth.
3. **`INSERT INTO grades (attempt_id, score, weak_topics, recommended_sections, graded_at) VALUES (?, ?, ?, ?, ?)`** — `score` from step 2 (not from the workflow's `score` field); `weak_topics` and `recommended_sections` from the workflow output, `'|'`-joined.
4. **`UPDATE quiz_attempts SET status='graded', graded_at=? WHERE attempt_id=?`** — flip the lifecycle.

All four steps in one `conn.execute(...) + conn.commit()` boundary (or the existing `with conn:` pattern under `app/persistence/quizzes.py`'s discipline; implementer's call). If any step raises, the transaction rolls back; the Attempt stays in `grading`; the processor's failure handler (ADR-049) then flips it to `grading_failed` and writes `grading_error`. No partial Grade can persist.

The workflow's `score` is **not** the persisted `score`. If it disagrees with `SUM(is_correct)`, the processor logs a warning to stderr (debugging aid) and proceeds with the recomputed value. The §8 truth is the runner's verdict; the LLM's `score` is a workflow output that exists because the LLM produces better explanations when it explicitly counts what passed.

### Weak Topics and recommended Sections — `'|'`-delimited TEXT (the relational `topics` table stays deferred)

`weak_topics` and `recommended_sections` are persisted as `'|'`-delimited TEXT columns on `grades` (`weak_topics TEXT NOT NULL DEFAULT ''`, `recommended_sections TEXT NOT NULL DEFAULT ''`), mirroring `questions.topics` (ADR-033). The empty-list case persists as `''` (rather than NULL); the round-trip is `'|'.join(weak_topics)` on write and `s.split('|') if s else []` on read (mirroring the existing `Question.topics` converter). Exposed publicly as `list[str]` on the `Grade` dataclass.

**The relational Topic vocabulary** (a `topics` table + `question_topics` join + `attempt_weak_topics` join, with the vocabulary sourced from a curriculum-side artifact) stays **deferred** — to the composition slice (the first thing that *queries* across Topics; MC-8's fresh-portion-driver needs "all Questions in this Section's Bank tagged with Topic X across all Attempts" — that's the cross-Attempt query the relational form enables). The migration from `'|'`-delimited TEXT to the relational form is additive per ADR-022 (`CREATE TABLE`s); the composition slice's `/design` triggers it. Deferred per ADR-035 — describing what's built here (the delimited TEXT form), not what won't be built (the relational vocabulary isn't forbidden, just not this slice's concern). ADR-033 / ADR-036 / ADR-037 all referenced this deferral; this ADR records that it remains in force through the grading slice.

### The new persistence functions

All under `app/persistence/quizzes.py`, re-exported from `app/persistence/__init__.py`:

- **`list_submitted_attempts() -> list[QuizAttempt]`** — `SELECT attempt_id, quiz_id, status, created_at, submitted_at, graded_at, grading_error FROM quiz_attempts WHERE status = 'submitted' ORDER BY submitted_at, attempt_id`. The read accessor the grading processor (ADR-049) polls. Returns `QuizAttempt` dataclasses (existing — gains `grading_error` field per below). Empty list for no `submitted` rows.
- **`mark_attempt_grading(attempt_id: int) -> None`** — `UPDATE quiz_attempts SET status = 'grading' WHERE attempt_id = ? AND status = 'submitted'`. Idempotent-ish: if the Attempt was not `submitted` (already `grading` from a prior crashed run, already `graded`, etc.), the UPDATE matches zero rows and is a silent no-op — the processor logs a warning and skips the Attempt (the row's status is honest, not overwritten). One transaction.
- **`mark_attempt_graded(attempt_id: int) -> None`** — `UPDATE quiz_attempts SET status = 'graded', graded_at = ? WHERE attempt_id = ?`. (Used by `save_attempt_grade` internally; exported for completeness but the processor calls `save_attempt_grade` for the full transition.) One transaction.
- **`mark_attempt_grading_failed(attempt_id: int, *, error: str | None = None) -> None`** — `UPDATE quiz_attempts SET status = 'grading_failed', grading_error = ? WHERE attempt_id = ?`. Mirrors `mark_quiz_generation_failed` from ADR-037. Touches no `attempt_questions` row; touches no `grades` row. One transaction.
- **`save_attempt_grade(attempt_id: int, *, per_question_explanations: dict[int, str], weak_topics: list[str], recommended_sections: list[str], graded_at: str | None = None) -> Grade`** — the transactional save-or-fail. In one transaction:
  1. For each `(question_id, explanation)` in `per_question_explanations.items()`, read the matching `attempt_questions` row (the Attempt was started by `start_attempt`, ADR-039, so the row exists), compute `is_correct` from the mapping (`test_passed`/`test_status` → 0/1) above, and `UPDATE attempt_questions SET is_correct = ?, explanation = ? WHERE attempt_id = ? AND question_id = ?`.
  2. `SELECT COALESCE(SUM(is_correct), 0) FROM attempt_questions WHERE attempt_id = ?` — the recomputed score.
  3. `INSERT INTO grades (attempt_id, score, weak_topics, recommended_sections, graded_at)` — `weak_topics` `'|'`-joined, `recommended_sections` `'|'`-joined, `graded_at` from the parameter (filled with `_utc_now_iso()` if `None`).
  4. `UPDATE quiz_attempts SET status = 'graded', graded_at = ? WHERE attempt_id = ?`.
  5. Return a `Grade` dataclass with the just-inserted values.
  Any exception raises; the transaction rolls back; the processor's catch (ADR-049) flips to `grading_failed`. A `question_id` in `per_question_explanations` that doesn't match any `attempt_questions` row for this Attempt is a defensive failure (the function raises `ValueError("question_id N not in attempt M")`; ADR-049's processor catches and flips to `grading_failed`). A `per_question_explanations` set that doesn't cover every Question in the Attempt is a defensive failure (the function raises; the processor catches; mirrors ADR-049's "the question_id set must match the input's" check — defense in depth).
- **`get_grade_for_attempt(attempt_id: int) -> Grade | None`** — `SELECT attempt_id, score, weak_topics, recommended_sections, graded_at FROM grades WHERE attempt_id = ?`. Returns a `Grade` dataclass (with `weak_topics` and `recommended_sections` split from `'|'`-delimited TEXT) or `None` if no `grades` row (the Attempt is not `graded`). The take-page render (ADR-051) calls this to fetch the Grade for a `graded` Attempt.

All six functions: no `user_id` (MC-7); SQL stays under `app/persistence/` (MC-10); `import sqlite3` stays in `app/persistence/connection.py` only. Re-exported from `app/persistence/__init__.py` under a TASK-019 / ADR-049–ADR-050 header (mirroring the TASK-017 grouping).

### The `Grade` dataclass

A new dataclass `Grade` in `app/persistence/quizzes.py` (alongside `Quiz` / `Question` / `QuizAttempt` / `AttemptQuestion`):

```python
@dataclass
class Grade:
    """
    A single grades row.

    ADR-050:
      attempt_id            INTEGER PRIMARY KEY (FK to quiz_attempts)
      score                 int      (0..len(attempt's questions); recomputed from
                                       attempt_questions.is_correct in save_attempt_grade)
      weak_topics           list[str]  (split from the '|'-delimited TEXT column;
                                        [] when empty — a perfect Attempt's Weak Topics)
      recommended_sections  list[str]  (split from '|'; [] valid)
      graded_at             str       (ISO-8601 UTC)

    No user_id (MC-7). The Weak Topics persisted form mirrors questions.topics
    (ADR-033 '|'-delimited TEXT); the relational topics-table migration is the
    composition slice's call. Exposed publicly as list[str].
    """
    attempt_id: int
    score: int
    weak_topics: list[str]
    recommended_sections: list[str]
    graded_at: str
```

A `_row_to_grade(row) -> Grade` converter mirrors `_row_to_quiz` / `_row_to_question` (splitting the delimited TEXT columns on read).

### The `QuizAttempt` dataclass — gains `grading_error: str | None`

The existing `QuizAttempt` dataclass (ADR-039 — `attempt_id` / `quiz_id` / `status` / `created_at` / `submitted_at` / `graded_at`) gains:

- `grading_error: str | None` — the failure detail when `status = 'grading_failed'`; NULL/None otherwise. Mirrors how `Quiz` would carry `generation_error: str | None` if it did (the current `Quiz` dataclass per ADR-033/ADR-037 does or should — the architect verifies during `/design` implementation whether the `Quiz` dataclass exposes `generation_error`; if not, that's an existing gap unrelated to this ADR and is fixed separately as a small accessor extension).

The `_row_to_attempt_question` converter and `_row_to_quiz_attempt` converters extend to carry the new fields (`bool(row["is_correct"]) if row["is_correct"] is not None else None` for the `INTEGER`→`bool|None` mapping on `attempt_questions.is_correct`; pass-through for `quiz_attempts.grading_error`).

The take-page render (ADR-051) reads `attempt.grading_error` for the `grading_failed` state branch.

### The `AttemptQuestion` dataclass — gains `is_correct: bool | None` and `explanation: str | None`

The existing `AttemptQuestion` dataclass (ADR-039 / ADR-044 / ADR-046 — `question_id` / `prompt` / `response` / `position` / `test_suite` / `test_passed` / `test_status` / `test_output` / `test_run_at` / `preamble`) gains:

- `is_correct: bool | None` — NULL/None for an ungraded Attempt's row; `True`/`False` after grading.
- `explanation: str | None` — NULL/None for an ungraded Attempt's row; the workflow's per-Question explanation after grading.

`list_attempt_questions(attempt_id)`'s `SELECT` already touches `attempt_questions ⨝ questions ⨝ quiz_questions` (ADR-039) and already returns the `attempt_questions.response` column; it extends to also `SELECT aq.is_correct, aq.explanation`. The `_row_to_attempt_question` converter carries them. No signature change to `list_attempt_questions`.

### The migration story — additive only, two-place declaration (mirroring ADR-041 / ADR-044 / ADR-046)

`_SCHEMA_SQL` gains:

- The new `CREATE TABLE IF NOT EXISTS grades (...)` block.
- The new `grading_error TEXT` column in the `CREATE TABLE IF NOT EXISTS quiz_attempts` block.

`_apply_additive_migrations(conn)` gains:

- A `PRAGMA table_info(quiz_attempts)` check + `ALTER TABLE quiz_attempts ADD COLUMN grading_error TEXT` (mirroring how `quizzes.generation_error` was added).
- A `SELECT name FROM sqlite_master WHERE type='table' AND name='grades'` existence check + `CREATE TABLE IF NOT EXISTS grades (...)` (the same DDL as `_SCHEMA_SQL` — idempotent in both places; the existence check is for clarity, not necessity). Alternatively, since the `CREATE TABLE IF NOT EXISTS` in `_SCHEMA_SQL` runs on every connection bootstrap (and is idempotent), the migration block can leave the table creation to `_SCHEMA_SQL` alone — implementer's call. The architectural commitment is "the `grades` table exists after `init_schema()` on both fresh and existing DBs"; the exact path is implementation.

Both changes are additive per ADR-022; no migration-trigger fires.

ADR-033's "n-tables threshold → per-module schema-fragment refactor" forecast is **not** triggered by this slice — six tables is not yet awkward. The composition slice (adding `topics` + `question_topics` + maybe `notifications` simultaneously) may trigger it; that slice's `/design` weighs.

### Scope of this ADR

This ADR fixes only:

1. **The `grades` table:** PK `attempt_id` (FK → `quiz_attempts`); `score INTEGER NOT NULL`, `weak_topics TEXT NOT NULL DEFAULT ''`, `recommended_sections TEXT NOT NULL DEFAULT ''`, `graded_at TEXT NOT NULL`. Declared in `_SCHEMA_SQL`'s `CREATE TABLE IF NOT EXISTS grades` block; created on existing DBs by `_apply_additive_migrations`. Additive per ADR-022.
2. **The `quiz_attempts.grading_error TEXT` column:** nullable; declared in the `CREATE TABLE quiz_attempts` block in `_SCHEMA_SQL` (fresh DBs); added on existing DBs by a `PRAGMA table_info(quiz_attempts)` check + `ALTER TABLE` in `_apply_additive_migrations`. Mirrors ADR-037's `quizzes.generation_error` recipe exactly.
3. **The `attempt_questions.is_correct` and `.explanation` columns:** unchanged schema (ADR-033 reserved them); this ADR makes them writeable by the grading slice. The `test_passed` → `is_correct` mapping (`True`→1, `False`→0, NULL/non-`'ran'`→0) is implemented here.
4. **The score cross-check:** `save_attempt_grade` recomputes `score = SUM(is_correct)` in the same transaction as the per-Question writes; the workflow's `score` is not the persisted truth.
5. **The new `Grade` dataclass:** `attempt_id` / `score` / `weak_topics: list[str]` / `recommended_sections: list[str]` / `graded_at`; `_row_to_grade` converter splits `'|'`-delimited TEXT.
6. **The `QuizAttempt` dataclass extension:** gains `grading_error: str | None`.
7. **The `AttemptQuestion` dataclass extension:** gains `is_correct: bool | None` and `explanation: str | None`; `list_attempt_questions` `SELECT` carries them through; converter maps `INTEGER` → `bool | None`.
8. **The new persistence functions:** `list_submitted_attempts`, `mark_attempt_grading`, `mark_attempt_graded`, `mark_attempt_grading_failed`, `save_attempt_grade` (transactional save-or-fail; raises on per-Question mismatch / incomplete coverage; ADR-049's processor catches and produces `grading_failed`), `get_grade_for_attempt`. All under `app/persistence/quizzes.py`; SQL stays here (MC-10); no `user_id` (MC-7); re-exported from `app/persistence/__init__.py`.
9. **The Weak-Topics / recommended-Sections persisted form:** `'|'`-delimited TEXT mirroring `questions.topics`; the relational `topics` table stays deferred to the composition slice.

This ADR does **not** decide:

- **The workflow's authoring surface** — owned by **ADR-048**.
- **The out-of-band processor's shape, lifecycle transitions, failure handling, `aiw run` CLI invocation, "notified" obligation, artefact parsing, CS-300 sanity check** — owned by **ADR-049**.
- **The graded-state and grading-failed-state rendering on the take page; what the failure render shows the learner; whether `grading_error` is exposed to the learner; the new CSS rules and namespace** — owned by **ADR-051**.
- **The active Notification entity** — deferred to a follow-on slice (ADR-049 records the deferral).
- **The relational Topic vocabulary** — deferred to the composition slice; this ADR persists `weak_topics` as `'|'`-delimited TEXT.
- **A "Try grading again" affordance on a `grading_failed` Attempt** — a future user-triggered surface; the persistence side natural shape would be a `reset_attempt_to_submitted(attempt_id)` function that flips `grading_failed` → `submitted` and clears `grading_error`. Out of scope.
- **The per-module schema-fragment refactor** (ADR-033's forecast) — not yet triggered; the composition slice may trigger it.

## Alternatives considered

**A. Nullable columns on `quiz_attempts` (`score INTEGER`, `weak_topics TEXT`, `recommended_sections TEXT`) instead of a separate `grades` table.**
Considered (the architect's forecast in the task file leaned `grades` table; the alternative was permitted as additive either way per ADR-033). Rejected for the reasons in §Decision §The Grade aggregate's home: the separate table gives a clean PK-on-`attempt_id` 1:1, keeps `quiz_attempts` focused on lifecycle, and is easier to extend with future provenance columns (`grader_model`, `cost_usd`, `grader_run_id`) without bloating `quiz_attempts`. The columns-on-`quiz_attempts` shape has marginal benefits (fewer joins, fewer tables to learn, NULL-as-ungraded reads naturally) but loses cleanness. The architect picks the table; the choice is defensible either way and the supersedure path is bounded (migrate to columns later via a backfill from `grades`).

**B. `is_correct = NULL` for `test_status != 'ran'` (a `graded` Attempt can carry NULL is_correct values).**
Rejected on coherence grounds: a `graded` Attempt means "all decisions are made". A NULL `is_correct` on a `graded` row is a contradiction (the §8 definition says correctness is part of the Grade). The composition slice's MC-8 read ("which Questions did the learner get wrong?") would have to choose how to interpret NULL — as wrong (the option this ADR picks, but pushed down to the schema where it doesn't belong) or as "doesn't count" (a weaker version of the wrong-answer-replay history). The cleaner shape is: failure-to-pass = not correct, by mapping; the *explanation* surfaces the failure mode honestly. MC-5's spirit: the failure is honest, not hidden as NULL.

**C. `grading_failed` for any Attempt with a NULL `test_status` (refuse to grade unrun Attempts).**
Rejected as too harsh: a learner who finished implementing Question 3 but didn't click "Run tests" on Question 5 before submitting still wants a Grade with what's known; the §8 amendment doesn't say the Attempt has to be fully test-run to be gradable. The "not run" case maps to `is_correct = 0` with the explanation noting "the test never ran" — honest and useful, not a refusal-to-grade.

**D. Score persisted from the LLM's `score` field verbatim (no cross-check).**
Rejected on §8 grounds: §8 makes correctness a function of the test result; the score is the count of correct Questions; therefore the score must be derived from the test result. The cross-check is cheap (it's already inside the transaction that wrote each `is_correct`) and architecturally clean. The LLM's `score` is a workflow output that exists because the LLM benefits from being prompted to count; the persisted truth is the recompute. The architectural commitment ADR-049 records is implemented here.

**E. Weak Topics / recommended Sections as a relational `topics` table + `attempt_weak_topics` join in this slice.**
Rejected, with the reasoning recorded in §Decision §Weak Topics and recommended Sections: the migration becomes load-bearing when the composition slice's MC-8 read needs cross-Section queries (which is one slice later); the delimited TEXT form is sufficient for this slice's writes-and-reads; the migration is additive per ADR-022 and can land in the composition slice's `/design`. Shipping it now would expand the slice's scope unnecessarily and force a Topic-vocabulary-source decision that's better made when the consumer's query needs are concrete. The deferral is conformant per ADR-035.

**F. Persist the workflow's full `GradeAttemptOutput` as a JSON blob on `grades` instead of normalizing per-Question explanations onto `attempt_questions.explanation`.**
Considered. Rejected: ADR-033 already provided `attempt_questions.explanation` for exactly this purpose; storing the LLM's per-Question explanations on the per-Question row is the normalized form, and the join `attempt_questions ⨝ questions ⨝ quiz_questions` (ADR-039 / ADR-044 / ADR-046) already returns everything the take-page render needs. A JSON blob would be an opaque second source of truth that the render would have to parse alongside the relational fields. The architecturally clean shape is: per-Question fields on `attempt_questions`; aggregate fields on `grades`.

**G. Add `grading_error` to `grades` instead of `quiz_attempts`.**
Rejected: the failure case has no `grades` row (the transactional save-or-fail leaves the Attempt with no Grade); `grading_error` must live on a row that exists even on failure. `quiz_attempts` is the natural home (it exists for every Attempt in any lifecycle state); `grades` is born on `graded`, so it can't carry the `grading_failed` detail. Mirrors how `quizzes.generation_error` is on `quizzes`, not on `questions`.

**H. A single denormalized `attempts_full` row carrying everything (lifecycle + responses + test results + correctness + explanations + aggregate).**
Rejected outright — denormalizing across `quiz_attempts` + `attempt_questions` + `grades` would make every read of the Attempt's data heavy and brittle; the existing normalized shape (one row per Attempt in `quiz_attempts`, one row per Question in `attempt_questions`, one row per graded Attempt in `grades`) is the right relational model. Mentioned to be rejected.

## My recommendation vs the user's apparent preference

Aligned with the user's apparent preference, captured in TASK-019's task file (the "Architectural decisions expected" section forecasts this ADR with the shape "a new `grades` table (PK `attempt_id`, FK to `quiz_attempts`, columns `score INTEGER NOT NULL`, `weak_topics TEXT NOT NULL`, `recommended_sections TEXT NOT NULL`, `graded_at TEXT NOT NULL`)" and "the additive migration … mirroring ADR-037 / ADR-041 / ADR-044 / ADR-046"), `quiz-grading-slice-shape.md` (which records both shapes as additive and forecasts the architect's lean toward the separate table), ADR-044 §`is_correct`'s source (which forecast "the grading slice sets `is_correct` (reading the persisted test result), not the runner"), ADR-049 §The score cross-check (which records the architectural commitment this ADR implements), and ADR-035 (deferrals are "what's built" descriptions, not project-wide postures).

The architect's call on the `is_correct` mapping ("not-`ran` → `is_correct = 0`, not `NULL`") is slightly more concrete than the task file's "(or `/design`'s call: treat a non-run test as `is_correct=0` with an explanation noting the test never ran — leans the second, since the learner having not clicked 'Run tests' before submitting should not block grading; the *explanation* surfaces it honestly)". Aligned — the architect picks option (ii) as forecast, with the reasoning recorded in §The `test_passed` → `is_correct` mapping.

I am NOT pushing back on:

- **ADR-022's additive-migration story** — consumed; the `grades` table, the `grading_error` column, and the `is_correct` / `.explanation` writes are all additive (no schema modification beyond `CREATE TABLE IF NOT EXISTS` and `ALTER TABLE ADD COLUMN`; the `attempt_questions.is_correct` writes flip NULLs to values, which is an UPDATE not a schema change).
- **ADR-033's `attempt_questions.is_correct` / `.explanation` NULL-until-graded posture** — consumed; this slice makes them writeable for the first time, exactly as ADR-033 forecast.
- **ADR-037 / ADR-041 / ADR-044 / ADR-046's additive-column recipe** — consumed; the `grading_error` column mirrors `generation_error` recipe-for-recipe.
- **ADR-048's `GradeAttemptOutput` shape** — consumed; the persistence maps `per_question[i].explanation` to `attempt_questions.explanation` and the aggregate to `grades` columns; the workflow's lack of an `is_correct` field is honored by the mapping.
- **ADR-049's transactional save-or-fail discipline** — consumed; `save_attempt_grade` is the transactional function; partial-Grade is physically impossible.
- **MC-7 / MC-10 / MC-5** — preserved by construction.

## Manifest reading

Read as binding for this decision:

- **§5 Non-Goals.** "No multi-user features" — no `user_id` on the `grades` table, the `grading_error` column, or any new dataclass; the `attempt_id` PK is the only identity on `grades` (single-user, single-Attempt).
- **§6 Behaviors and Absolutes.** "AI failures are visible … never fabricates a result" — the transactional save-or-fail in `save_attempt_grade` enforces this at the persistence layer: either every per-Question row + the `grades` row + the lifecycle flip commit together, or the transaction rolls back and the Attempt stays `grading` (the processor then flips to `grading_failed` and writes `grading_error`). No partial Grade can persist. "Single-user" — no `user_id` anywhere. "Code is written, run, and tested within the application" — orthogonal to persistence; the runner's `test_passed` is read by this layer as the input to the `is_correct` mapping.
- **§7 Invariants.** "Every Quiz Attempt … persists across sessions" — the new `grades` row persists with the Attempt; ADR-033's "never deleted" posture extends — there's no Grade-delete path. "Every Question is a hands-on coding task" — `attempt_questions.explanation` is *commentary on coding*, not a non-coding artifact; the column type is plain TEXT — no choice / option / recall fields exist or can be added (ADR-033 / ADR-040 / ADR-045's "schema makes non-coding inexpressible" posture extends transitively).
- **§8 Glossary.** **Grade** — the four-facet definition is realized: per-Question correctness (in `attempt_questions.is_correct`, derived from `test_passed` per the mapping), per-Question explanation (in `attempt_questions.explanation`, from the workflow), an aggregate score (in `grades.score`, recomputed from `SUM(is_correct)`), identified Weak Topics (in `grades.weak_topics`, `'|'`-delimited), and recommended Sections (in `grades.recommended_sections`, `'|'`-delimited). **Weak Topic** — "drives the fresh-Question portion of subsequent Quizzes for the same Section. The replay portion is driven separately by per-Question wrong-answer history" — both inputs are produced by this slice (Weak Topics in `grades.weak_topics`; the wrong-answer-replay history in `attempt_questions.is_correct = 0` rows). "Topics form a project-wide vocabulary maintained alongside Chapter content" — the relational form is deferred to the composition slice, where the cross-Section query need surfaces.

No manifest entries flagged as architecture-in-disguise for this decision. The table-vs-columns choice, the `is_correct` mapping, the score cross-check, the delimited-TEXT-vs-relational choice for Weak Topics, the migration recipe are all operational architecture the manifest delegates to the architecture document.

## Conformance check

- **MC-1 (No direct LLM/agent SDK use) — ACTIVE.** Honored — the persistence module imports stdlib (`sqlite3` in `connection.py` only; `datetime` in `quizzes.py`) + `dataclasses`; no LLM SDK; no AI call from `app/persistence/`. **PASS.**
- **MC-2 (Quizzes scope to exactly one Section).** Honored — `grades` is per-Attempt (PK `attempt_id`); the Attempt belongs to one Quiz which belongs to one Section; no cross-Section aggregation; `weak_topics` and `recommended_sections` are per-Attempt (the Section the Attempt is from is the natural recommendation target, per ADR-048's prompt). **PASS.**
- **MC-3 (Mandatory/Optional designation respects the canonical mapping).** Orthogonal; the Grade is for any Section's Attempt; the designation is not a Grade field. **PASS** (manifest portion); **`cannot evaluate (ADR pending)`** for the mapping-source architecture portion.
- **MC-4 (AI work asynchronous).** Honored — the persistence layer does no AI work; it is called from the out-of-band processor (ADR-049), never from a FastAPI request. **PASS.**
- **MC-5 (AI failures surfaced, never fabricated).** Honored — the transactional `save_attempt_grade` is the implementation: any failure (per-Question UPDATE raises, score recompute fails, `grades` INSERT raises, lifecycle UPDATE raises, a `question_id` mismatch / incomplete coverage validation raises) rolls back the whole transaction; no partial Grade ever persists; the processor's catch (ADR-049) flips the Attempt to `grading_failed` and writes the detail in `grading_error`. The score cross-check makes the persisted `score` the runner's truth, not the LLM's claim — a fabricated LLM `score` can't propagate. **PASS.**
- **MC-6 (Lecture source read-only).** Honored — persistence writes only to `data/notes.db`; never touches `content/latex/`. **PASS.**
- **MC-7 (Single user).** Honored — no `user_id` on `grades`, on the new `grading_error` column, on the `Grade` dataclass, on the extended `QuizAttempt` / `AttemptQuestion` dataclasses; `grades.attempt_id` is the only identity on the table. **PASS.**
- **MC-8 (Reinforcement loop preserved).** Honored — this slice writes the inputs the composition slice (next) consumes: `attempt_questions.is_correct` (the wrong-answer-replay history) and `grades.weak_topics` (the fresh-Question portion driver). The first-Quiz-only guard (ADR-037) is unchanged. **PASS.**
- **MC-9 (Quiz generation user-triggered).** Honored — this slice does **not** generate Quizzes; the `grades` writes are downstream of a user-submitted Attempt; the per-Section "Generate a Quiz" route is unchanged. **PASS.**
- **MC-10 (Persistence boundary) — ACTIVE.** Honored — all new SQL literals live in `app/persistence/quizzes.py` and `app/persistence/connection.py`; the new dataclasses are in `app/persistence/quizzes.py`; the new functions are re-exported from `app/persistence/__init__.py`; routes / workflow modules / templates call typed public functions only, receive dataclasses, never receive a `sqlite3.Connection` or a raw row tuple. **PASS.**

Previously-dormant rule activated by this ADR: none. The boundary grep / lint test for `app/persistence/` covers the new code without change.

## Consequences

**Becomes possible:**

- A `submitted` Attempt can be transitioned through `grading → graded` with a complete §8 Grade persisted (per-Question correctness from the runner; per-Question explanation from the workflow; aggregate score recomputed from `is_correct`; Weak Topics and recommended Sections from the workflow).
- The composition slice (next) can read both inputs MC-8 requires: `attempt_questions.is_correct = 0` rows (the wrong-answer-replay history; the replay portion's driver) and `grades.weak_topics` (the fresh-Question portion's driver).
- An honest failure state — `quiz_attempts.status = 'grading_failed'` with the detail in `grading_error`; no partial Grade; the take page (ADR-051) renders the honest failure without a fabricated Grade.
- §8 Grade-correctness is honored architecturally end-to-end: the workflow has no `is_correct` field (ADR-048), the mapping is in the persistence layer (here), the score is recomputed (here), the take page renders the runner's truth (ADR-051).
- A clean PK-on-`attempt_id` shape for the Grade — the presence of the `grades` row *is* the persisted Grade; no NULL-as-meaningful semantic on `quiz_attempts`.

**Becomes more expensive:**

- `app/persistence/quizzes.py` grows ~6 new functions + 1 new dataclass + 1 new converter + extensions to two existing dataclasses + extensions to `list_attempt_questions`'s SELECT. Mitigation: each function mirrors an existing pattern (`mark_quiz_*` / `start_attempt` / `save_attempt_responses` / `save_attempt_test_result`); the dataclass mirrors `Quiz` / `Question`; SQL stays tightly scoped.
- `app/persistence/connection.py`'s `_SCHEMA_SQL` grows by the `CREATE TABLE grades` block + the `grading_error TEXT` column on `quiz_attempts`; `_apply_additive_migrations` grows by one column-check + one table-create block. Mitigation: mirrors ADR-037's `generation_error` pattern + ADR-044's column-check pattern.
- `app/persistence/__init__.py` re-exports 6 new symbols. Mitigation: trivial; mirrors the TASK-014 / TASK-017 groupings.
- `data/notes.db` gains a sixth Quiz-domain table. The per-module schema-fragment refactor (ADR-033's forecast) is *closer* but not yet triggered; the composition slice may trigger it.

**Becomes impossible (under this ADR):**

- A `graded` Attempt without a `grades` row (the transactional save commits both or neither).
- A `graded` Attempt with NULL `is_correct` or NULL `explanation` on any `attempt_questions` row (the per-Question UPDATEs are part of the same transaction as the `grades` INSERT and the lifecycle flip).
- A partial Grade (the transaction's atomicity).
- An LLM-fabricated `score` propagating to the persisted truth (the recompute overrides).
- A `user_id` smuggled into any Grade-side row or dataclass (no such column anywhere; MC-7).
- A SQL literal outside `app/persistence/` (MC-10; the new functions are the only callers).

**Future surfaces this ADR pre-positions:**

- **The composition slice** — reads `attempt_questions WHERE is_correct = 0 AND attempt_id IN (...)` for wrong-answer-replay; reads `grades.weak_topics` for the fresh-Question portion; the relational `topics` table migration lands then.
- **A "Try grading again" affordance on a `grading_failed` Attempt** — needs `reset_attempt_to_submitted(attempt_id)` (flip `grading_failed` → `submitted`, clear `grading_error`); a small additive function the future slice adds. The persistence side is forward-compatible.
- **A "regrade in place" path** (recompute a Grade with a different LLM tier without creating a new Attempt) — needs `update_attempt_grade(attempt_id, ...)` and possibly a `grades.regraded_at` column; additive. Out of scope.
- **A `grades.grader_model TEXT`, `grades.grader_run_id TEXT`, `grades.cost_usd REAL` provenance triple** — for the author to know which LLM produced which Grade; nullable additive columns; out of scope this slice.
- **A `notifications` table referencing `attempt_id` for `grade_ready` kind** — the natural place to INSERT it is at the end of `save_attempt_grade`'s transaction (the same transaction; one more INSERT). Deferred to the follow-on Notification slice (ADR-049 records the deferral).
- **A `Grade.is_perfect` / `Grade.fraction_correct` computed-property on the dataclass** — derived from `score` and the Attempt's question count; trivial; out of scope.

**Supersedure path if this proves wrong:**

- If the `grades` table proves too separate (the take-page render always needs both `quiz_attempts` and `grades` joined, the joins get tiresome) → a future ADR could supersede this one and migrate the columns onto `quiz_attempts`; the migration is a backfill (`UPDATE quiz_attempts SET score = ..., weak_topics = ... FROM grades WHERE quiz_attempts.attempt_id = grades.attempt_id`) + drop the `grades` table. Cost: bounded; the backfill is mechanical.
- If the `is_correct` mapping proves too harsh (the `is_correct = 0` for `test_status = 'compile_error'` case feels punitive when the test suite itself is broken) → a future ADR refines the mapping (e.g. `test_status = 'compile_error' WITH workflow-flagged "test suite broken"` → `is_correct = NULL` and a dedicated "not graded" lifecycle state). The current mapping is the conservative call (penalize non-pass; let the explanation surface why); refining is additive.
- If the score cross-check proves too aggressive (some LLM `score` divergences are correct — e.g. the LLM correctly identifies a wrong test that the runner accepted) → a future ADR refines (a `grades.score_override INTEGER` column carrying the LLM's claim when it differs from the recompute, with a `grades.score_source TEXT` enum); additive. The architectural commitment "correctness = test result" stays as the default.
- If the `'|'`-delimited TEXT form for `weak_topics` / `recommended_sections` becomes a parsing burden (the composition slice's cross-Attempt query reads many `grades` rows and parses delimited strings repeatedly) → the composition slice's `/design` migrates to the relational `topics` table + an `attempt_weak_topics` join; additive per ADR-022.

The supersedure path runs through new ADRs. This ADR does not edit any prior ADR in place; it consumes ADR-022 / ADR-033 / ADR-037 / ADR-039 / ADR-041 / ADR-044 / ADR-046 / ADR-048 / ADR-049 unchanged.
