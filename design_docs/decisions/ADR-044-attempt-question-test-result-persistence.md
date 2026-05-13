# ADR-044: The `attempt_questions` test-result persistence layer — four nullable additive columns (`test_passed`, `test_status`, `test_output`, `test_run_at`) via the `_apply_additive_migrations` `PRAGMA table_info` check; a `save_attempt_test_result(attempt_id, question_id, *, passed, status, output, run_at=None)` writer; a `get_question(question_id) -> Question | None` accessor (the runner-slice accessor ADR-041 forecast); the `AttemptQuestion` dataclass gains the four fields; `list_attempt_questions` carries them through; `is_correct` stays set by the grading slice

**Status:** `Accepted`
**Auto-accepted by /auto on 2026-05-12**
**Date:** 2026-05-12
**Task:** TASK-017
**Resolves:** part of `design_docs/project_issues/in-app-test-runner-slice-shape.md` (with ADR-042 + ADR-043) — the `attempt_questions` test-result-columns sub-question, `is_correct`'s source, and the runner-slice accessor
**Supersedes:** none — consumes ADR-033 (the `attempt_questions` schema), ADR-022 (the persistence boundary + additive-migration story), ADR-039 (the Attempt-lifecycle persistence layer this extends), ADR-041 (the `questions.test_suite` column this reads; ADR-041 §No new accessor said "the runner slice adds one" — this is it), ADR-042 (the `RunResult` shape the writer maps from), unchanged

## Context

§8 Quiz Attempt now says it carries "the learner's code response for each Question, **the in-app test results for each response**, a progress status through grading, and — once graded — a Grade." Today (ADR-033 / ADR-039) `attempt_questions` carries `response` (the learner's code), `is_correct` (NULL until graded), `explanation` (NULL until graded) — but **no test results**. ADR-042 builds the sandbox (`run_test_suite(test_suite, response) -> RunResult` with `status`/`passed`/`output`); ADR-043 builds the "Run tests" route + take-surface affordance. This ADR owns the **persistence layer** the route writes to and reads from: the new `attempt_questions` columns, the writer function, the runner-slice accessor (the one ADR-041 deferred — "the runner slice adds one"), the `AttemptQuestion` dataclass extension, and the `list_attempt_questions` carry-through. It also makes the call on `is_correct`'s source.

Constraints:

- **ADR-022's migration story** — additive changes are `CREATE TABLE IF NOT EXISTS` (for fresh DBs) plus, where a column can't be expressed that way, a `PRAGMA table_info`-guarded `ALTER TABLE ADD COLUMN` in `_apply_additive_migrations` (idempotent — a no-op on a DB that already has the column). Precedents: ADR-037's `quizzes.generation_error`, ADR-041's `questions.test_suite`. No migration-trigger fires.
- **ADR-033's `attempt_questions` shape** — `(attempt_id, question_id, response, is_correct, explanation)`, PK on the pair, one row per Question per Attempt, created at Attempt start by `start_attempt` (ADR-039). The new test-result columns are siblings of `is_correct`/`explanation` — NULL until a run happens, then set by `save_attempt_test_result`. ADR-033 flagged an "n-tables threshold → per-module schema-fragment refactor" — adding columns to an existing table does not approach it.
- **ADR-039's persistence-layer pattern** — typed public functions in `app/persistence/quizzes.py`, dataclasses returned to callers, `import sqlite3` + SQL literals only here (MC-10), no `user_id` (MC-7), re-exported via `app/persistence/__init__.py`.
- **ADR-041 §No new accessor** — TASK-016 deliberately did *not* add an accessor that *reads* `questions.test_suite` at runtime ("nothing reads the test suite at runtime yet — the runner slice adds one"). This ADR adds it.
- **§8 Grade** — "per-Question correctness (determined by whether the learner's code passed the Question's tests)" — so `is_correct` becomes a *function of* the test result. Who sets it: the runner ("tests passed ≡ correct") or the grading slice (reading the persisted test result and adding the per-Question explanation alongside)? This ADR decides.
- **MC-6 / MC-5 / MC-7 / MC-10** — orthogonal-but-relevant: the persistence layer doesn't touch `content/latex/` (MC-6 is the sandbox's concern, ADR-042); a sandbox failure is persisted honestly via `test_status` (MC-5's spirit — the column shape is chosen so failure modes aren't conflated with pass/fail); no `user_id` (MC-7); SQL stays under `app/persistence/` (MC-10).

## Decision

### The column shape — four nullable additive columns on `attempt_questions`

`attempt_questions` gains four nullable columns (declared in the `CREATE TABLE attempt_questions` block in `connection.py`'s `_SCHEMA_SQL` for fresh DBs, **and** added for existing DBs by a `PRAGMA table_info(attempt_questions)`-guarded `ALTER TABLE attempt_questions ADD COLUMN ...` block in `_apply_additive_migrations`, mirroring ADR-037's `generation_error` and ADR-041's `test_suite`):

- `test_passed INTEGER` — `1` if the test suite ran to completion and passed, `0` if it ran and failed, **NULL** if no run has happened *or* the run did not complete (timed out / didn't compile / setup error). Meaningful **only when `test_status = 'ran'`**.
- `test_status TEXT` — the structured run status: `'ran'` | `'timed_out'` | `'compile_error'` | `'setup_error'` (mirroring `RunResult.status` — ADR-042); **NULL** until a run has happened. This column is load-bearing for honesty: `test_passed` alone (a bare `INTEGER`) cannot distinguish "the tests ran and failed" from "the tests timed out" from "the test suite didn't compile" — and conflating those is the MC-5-spirit violation. `test_status` carries the truth; the take page (ADR-043) renders the honest failure messages from it.
- `test_output TEXT` — the run's combined stdout+stderr, or the compiler diagnostic (`compile_error`), or the setup-failure message (`setup_error`); truncated to a sane cap by the sandbox (ADR-042's `RunResult.output` is already truncated — e.g. 16 KiB — to bound the DB size). NULL until a run.
- `test_run_at TEXT` — the ISO-8601 UTC timestamp of the latest run (set by the writer; the take page uses "is `test_run_at` NULL?" to decide "show 'not run yet'" vs "show the result"). NULL until a run.

**Denormalized "latest run" onto `attempt_questions`, not a new `attempt_question_runs` table.** The take surface (ADR-043) and the grading slice (next) need the *latest* run result, not the history of every run; `attempt_questions` already has exactly one row per Question per Attempt, so the latest result is naturally a few columns on it. A separate `attempt_question_runs` table (a row per run) would add a join, a row-per-run, and inch ADR-033's "n-tables threshold" closer — for a run-history that no manifest entry requires and that the surface and the grading slice don't read. (If a future need for run-history surfaces — e.g. "show me how my code evolved across runs" — that's a later, additive ADR; the columns here are the "latest" snapshot, which is forward-compatible with adding a history table later.)

`is_correct` and `explanation` are **untouched** by this ADR (still NULL until grading — ADR-039) — see "`is_correct`'s source" below.

### `is_correct`'s source — the grading slice sets it (reading the persisted test result), not the runner

The "Run tests" route (ADR-043) writes `test_passed` / `test_status` / `test_output` / `test_run_at` and **does not touch `is_correct`**. `is_correct` stays NULL until the (later) grading slice's out-of-band processor runs, at which point that processor reads the persisted test result and sets `is_correct` (and `explanation` alongside, and the Grade aggregate). §8 Grade's "correctness determined by whether the learner's code passed the Question's tests" is satisfied either way (whoever sets `is_correct`, it's a function of the test result) — but having the grading slice set it keeps that slice's job coherent: the grading slice computes the *whole* Grade (per-Question correctness *and* the per-Question explanation *and* the aggregate score *and* the Weak Topics), and the per-Question correctness is `test_passed` carried forward. If the runner set `is_correct`, the grading slice would have a partial-Grade state to reconcile (correctness already set, explanation not), and a learner could end up with `is_correct` set but the Attempt never graded (no aggregate, no explanation, no Notification) — a confusing half-state. The runner produces the raw signal; the grading slice consumes it. (This also matches the manifest's framing: "the in-app test results" (a runner output) and "a Grade" (a graded output) are separate things in §8.)

### The writer — `save_attempt_test_result(attempt_id, question_id, *, passed, status, output, run_at=None) -> None`

A new public function in `app/persistence/quizzes.py`:

- `passed: bool | None`, `status: str`, `output: str`, `run_at: str | None` (when `None`, the function fills `_utc_now_iso()` — same pattern as `start_attempt` / `submit_attempt`).
- `UPDATE attempt_questions SET test_passed = ?, test_status = ?, test_output = ?, test_run_at = ? WHERE attempt_id = ? AND question_id = ?` — updates the existing row (created at Attempt start by `start_attempt` — ADR-039). A `(attempt_id, question_id)` pair with no matching row is a silent no-op (defensive — the route built the call from the Attempt's own rows; mirrors `save_attempt_responses`'s ignore-unknown-`question_id` posture). One transaction.
- Does **not** touch `response`, `is_correct`, `explanation`, or `quiz_attempts.status` — running tests is a within-`in_progress` action; it changes only the four test-result columns.
- `passed` is stored as `1`/`0`/`NULL` (Python `True`/`False`/`None` → SQLite `INTEGER`/`NULL` — `sqlite3` does this natively for `bool`; the row→dataclass converter maps it back). No `user_id` (MC-7). SQL stays here (MC-10).

### The runner-slice accessor — `get_question(question_id) -> Question | None`

A new public function in `app/persistence/quizzes.py`: `SELECT question_id, section_id, prompt, topics, test_suite, created_at FROM questions WHERE question_id = ?` → a `Question` dataclass (the existing one — ADR-033/ADR-041; it already carries `test_suite: str | None`, `topics` split to `list[str]` via `_row_to_question`), or `None` if not found. The "Run tests" route (ADR-043) calls this to fetch the target Question's `test_suite` to feed the sandbox. `get_question` (returns the whole Question) is chosen over a narrower `get_test_suite_for_question(question_id) -> str | None` because the whole-Question accessor is more reusable (the grading slice and future surfaces will want a Question by id) and the `Question` dataclass already exists with the right shape — no new dataclass, no new converter. (ADR-041 §No new accessor: "the runner slice adds one" — this is it; the choice between `get_question` and a narrower accessor was the runner slice's call, and the reusable form wins.) SQL stays here (MC-10). No `user_id` (MC-7).

### The `AttemptQuestion` dataclass — gains the four test-result fields

`AttemptQuestion` (ADR-039 — currently `question_id` / `prompt` / `response` / `position`) gains:

- `test_suite: str | None` — the Question's test suite (so the take page can show the read-only test-suite block per ADR-043; `list_attempt_questions`'s join already touches `questions`, so this is one more `SELECT`ed column);
- `test_passed: bool | None`,
- `test_status: str | None`,
- `test_output: str | None`,
- `test_run_at: str | None`.

The `_row_to_attempt_question` converter carries them through (`bool(row["test_passed"]) if row["test_passed"] is not None else None` for the `INTEGER`→`bool|None` mapping; the rest are passthrough). No new dataclass — extending the existing `AttemptQuestion` keeps the take template's iteration unchanged in shape (it already iterates `attempt_questions`; each `aq` now also has `.test_suite` and `.test_*`). (An `AttemptQuestionRun` separate dataclass was considered and rejected — it'd only make sense paired with an `attempt_question_runs` table, which this ADR rejects; the "latest result" belongs on `AttemptQuestion`.)

### `list_attempt_questions` — carries the test-result fields through

`list_attempt_questions(attempt_id)`'s `SELECT` gains `q.test_suite`, `aq.test_passed`, `aq.test_status`, `aq.test_output`, `aq.test_run_at` (it already joins `attempt_questions aq` ⨝ `questions q` ⨝ `quiz_questions qq` ⨝ `quiz_attempts qa` and orders by `qq.position`); the converter populates the new `AttemptQuestion` fields. The take page (ADR-043) re-renders each Question's test suite + latest test result from this after a reload / in the `submitted` state. Order, filtering, and return-`[]`-for-unknown-attempt behavior are unchanged (ADR-039).

### `app/persistence/__init__.py` — re-exports `save_attempt_test_result` and `get_question`

Added to the imports and `__all__` (and the module docstring's public-API list), under a TASK-017 / ADR-042-ADR-044 header — mirroring how TASK-014's and TASK-015's additions were grouped.

## Alternatives considered

**A. A new `attempt_question_runs` table — a row per run (`run_id`, `attempt_id`, `question_id`, `passed`, `status`, `output`, `run_at`), so the full run-history is recorded.** More data; lets a future surface show "your code across runs". Rejected: no manifest entry requires run-history; the take surface (ADR-043) and the grading slice (next) read only the *latest* run; `attempt_questions` already has exactly one row per Question per Attempt, so the latest result is naturally a few columns on it; a separate table adds a join, a row-per-run, and inches ADR-033's n-tables threshold closer for no current consumer. If run-history is ever wanted, that's an additive ADR then — and the "latest" columns here are forward-compatible with adding a history table later (the columns become a denormalized cache of the latest `attempt_question_runs` row, or stay as-is). (It would have made run-history a free byproduct and made the schema heavier for no current need.)

**B. Three columns (`test_passed`, `test_output`, `test_run_at`) — no `test_status` — encoding the failure mode into `test_output` (a prefix like `[TIMEOUT]` / `[COMPILE ERROR]`) and treating `test_passed = NULL` as "didn't complete".** Closer to the task's literal forecast (`test_passed`/`test_output`/`test_run_at`). Rejected: a structured `test_status` column is genuinely needed — the grading slice (next) reads the test result to set `is_correct`, and it needs to distinguish "ran and failed" (→ `is_correct = 0`) from "timed out / didn't compile / setup error" (→ what? probably also `is_correct = 0`, but the *explanation* differs, and a string-prefix in `test_output` is a fragile thing to parse); the take page (ADR-043) renders the honest failure messages from a structured status, not from parsing `test_output`; and MC-5's spirit — not conflating failure modes with pass/fail — is best served by a dedicated column, not by overloading `test_output`. The task's forecast was "`test_passed`/`test_output`/`test_run_at` or `/design`'s equivalent" — `/design`'s equivalent adds `test_status`. (It would have made the column set match the forecast verbatim and made the failure-mode-vs-pass/fail distinction fragile — a bad trade.)

**C. `is_correct` set by the runner ("tests passed ≡ correct").** Simpler in one sense — the moment the tests pass, correctness is known. Rejected (see "`is_correct`'s source"): it splits the Grade across two slices (correctness from the runner, explanation + aggregate + Weak Topics from the grading slice), creating a half-graded state (a learner with `is_correct` set but the Attempt never graded — no aggregate, no explanation, no Notification), and the grading slice would have to reconcile a partially-set Grade rather than compute the whole thing from the raw test results. §8 Grade's "correctness determined by whether the code passed the tests" is satisfied either way; the grading-slice-sets-it shape keeps the Grade coherent and matches §8's framing of "the in-app test results" and "a Grade" as separate. The task's forecast leaned "by the grading slice" — aligned. (It would have made correctness available a step earlier and made the Grade a two-slice patchwork.)

**D. A narrower accessor — `get_test_suite_for_question(question_id) -> str | None` instead of `get_question(question_id) -> Question | None`.** Minimal — returns exactly what the route needs (the test suite). Rejected: `get_question` returns the whole `Question` (which already exists as a dataclass with the right shape — `test_suite`, `topics`, `prompt`, `section_id`, `created_at`), is more reusable (the grading slice and future surfaces will want a Question by id), and costs nothing extra (one `SELECT` of the existing columns + the existing `_row_to_question` converter). A narrow accessor would just be re-derived later. (It would have been one fewer dataclass field on the wire and made the next slice add `get_question` anyway.)

**E. A new `AttemptQuestionRun` dataclass for the run result, separate from `AttemptQuestion`.** Rejected — it only makes sense paired with an `attempt_question_runs` table (Alternative A, rejected); the "latest result" belongs on `AttemptQuestion` (the take template already iterates `AttemptQuestion`s; adding fields is shape-preserving). (No real alternative — recorded for completeness.)

## My recommendation vs the user's apparent preference

**Aligned with the task's forecast**, with the open calls made:

- **The column shape — four columns, adding `test_status` to the forecast's three.** The task forecast was "`test_passed INTEGER` + `test_output TEXT` + `test_run_at TEXT` (additive nullable `ALTER`s) … or `/design`'s equivalent" — `/design`'s equivalent adds `test_status` because the grading slice (next) and the take page (ADR-043) both need the structured run status, and MC-5's spirit is best served by not overloading `test_output`. A small, defensible deviation in the forecast's direction.
- **Denormalized columns, not a new table.** Exactly the forecast ("denormalized columns on `attempt_questions` … run-history is not a manifest requirement"). The n-tables-threshold refactor ADR-033 forecast is not triggered (no new table).
- **`is_correct` set by the grading slice.** Exactly the forecast ("by the grading slice — keeps the grading slice's 'compute the Grade' job coherent"). This ADR's "`is_correct`'s source" section is the forecast's rationale fleshed out (the half-graded-state argument).
- **The accessor — `get_question(question_id)`.** The task left it open ("`get_question` / `get_test_suite_for_question` — `/design`'s call"); the architect picked the reusable whole-Question form (the `Question` dataclass already exists; the grading slice will want it). ADR-041 §No new accessor explicitly handed this call to the runner slice — done.
- **`AttemptQuestion` extended, not replaced.** Exactly the forecast ("the `AttemptQuestion` (or new) dataclass change" — the existing one, extended).

No tension with the manifest. No tension with the user's apparent direction. Re-flag (not actioned): `tooling-lint-and-type-check.md` (Open, 11th+ recurrence) — not this task.

## Consequences

**Becomes possible / easier:**

- §8's "the in-app test results for each response" becomes a real persisted thing — `attempt_questions` carries the latest run's `test_passed` / `test_status` / `test_output` / `test_run_at`, which the take page (ADR-043) renders and the grading slice (next) reads.
- The grading slice (next) has a clean input — it reads `attempt_questions.test_passed` (and `test_status`/`test_output` for context) and sets `is_correct` + `explanation` + the aggregate; no half-graded state to reconcile.
- The take page can re-render each Question's test suite + latest result after a reload / in the `submitted` state from one `list_attempt_questions` call.
- A future run-history feature, if ever wanted, is an additive ADR (a new `attempt_question_runs` table; the columns here become the "latest" cache or stay as-is).

**Becomes more expensive:**

- Four new nullable columns on `attempt_questions` + the `CREATE TABLE` declaration + the `_apply_additive_migrations` `PRAGMA table_info`-guarded `ALTER` block. Mitigation: additive (no migration-trigger; idempotent on an existing DB); mirrors ADR-037's `generation_error` and ADR-041's `test_suite` precedents exactly.
- Two new public functions (`save_attempt_test_result`, `get_question`) in `app/persistence/quizzes.py` + the `__init__.py` re-exports. Mitigation: small (one `UPDATE`, one `SELECT`); pinned by pytest (the round-trip: write the result via `save_attempt_test_result`, re-query via `list_attempt_questions` after a fresh connection, get it intact).
- The `AttemptQuestion` dataclass grows five fields (`test_suite` + the four `test_*`); `_row_to_attempt_question` and `list_attempt_questions`'s `SELECT` grow to match. Mitigation: passthrough fields (one `bool`-mapping for `test_passed`); the take template's iteration is shape-preserving.

**Becomes impossible (under this ADR):**

- The take page or the grading slice not being able to distinguish "tests ran and failed" from "tests timed out / didn't compile" (`test_status` is a dedicated column; MC-5's spirit).
- A half-graded Attempt (`is_correct` is set only by the grading slice, which sets the whole Grade at once; the runner only writes the test-result columns).
- A `user_id` creeping in (none on the new columns, the new functions, or the `AttemptQuestion` extension; MC-7).
- SQL leaking out of `app/persistence/` (the new columns' DDL is in `connection.py`; the new functions' SQL is in `quizzes.py`; the route receives dataclasses; MC-10).

**Supersedure path if it proves wrong:** if run-history turns out to be wanted, a new additive ADR adds an `attempt_question_runs` table (the columns here stay as the "latest" snapshot or become a cache). If `test_status`'s enum needs more states (e.g. a distinct `crashed` vs `compile_error`), that's a value addition to the `RunResult.status` set (ADR-042) and a passthrough here — no schema change (it's a TEXT column). If the grading slice's design wants `is_correct` set earlier, a new ADR revisits — but the half-graded-state argument should hold.

## Manifest reading

- **§8 Quiz Attempt "the learner's code response for each Question, the in-app test results for each response, a progress status through grading, and — once graded — a Grade"** — read as **binding glossary/behavior**; this ADR adds "the in-app test results for each response" to the persisted Attempt. Its framing of "the in-app test results" and "a Grade" as *separate* things informs the `is_correct`-set-by-the-grading-slice call. Not architecture-in-disguise — *what* the Attempt carries, not *how* it's stored.
- **§8 Grade "per-Question correctness (determined by whether the learner's code passed the Question's tests)"** — read as **binding**; it makes `is_correct` a function of the test result, which this ADR's column shape supports (the grading slice reads `test_passed`). Not architecture-in-disguise.
- **§7 "Every Quiz Attempt … persists across sessions"** — read as **binding**; the test result persists on the `attempt_questions` row (which has no delete path — ADR-039's no-delete posture preserved), so it survives a reload and a new session. Not architecture-in-disguise.
- **§5 "No multi-user features"** — read as **binding**; no `user_id` on the new columns or functions. Not architecture-in-disguise.
- **§7 "Every Question is a hands-on coding task"** — read as **binding**; the test-result columns store test-execution outcomes, not a choice/recall/describe artifact — there is no field anywhere that could hold a non-coding result. Not architecture-in-disguise.
- No manifest entry read as architecture-in-disguise for this decision. No manifest entry flagged. No manifest tension.

## Conformance check

- **MC-7 (Single user).** No `user_id` on the four new `attempt_questions` columns, `save_attempt_test_result`, `get_question`, or the `AttemptQuestion` extension; no auth, no session, no per-user partitioning. **PASS.**
- **MC-10 (Persistence boundary).** The new columns' DDL lives in `connection.py` (`_SCHEMA_SQL`'s `CREATE TABLE attempt_questions` block + `_apply_additive_migrations`'s `PRAGMA table_info`-guarded `ALTER`); `save_attempt_test_result` and `get_question`'s SQL lives in `quizzes.py`; `import sqlite3` stays under `app/persistence/`; the route (ADR-043) calls only the typed public functions and receives `Question` / `AttemptQuestion` dataclasses — never a `sqlite3.Connection` or a raw row. **PASS** (warn-level rule per the skill — Accepted ADR-022 + the persistence package exists; this ADR keeps it clean).
- **MC-5 (AI failures surfaced, never fabricated).** Orthogonal in the letter (no AI in the persistence layer); binding in spirit — the `test_status` column exists precisely so a sandbox failure (`timed_out` / `compile_error` / `setup_error`) is persisted as that, never conflated with `test_passed`; the take page renders the honest message from it (ADR-043). **PASS** (spirit honored).
- **MC-6 (Lecture source read-only).** Orthogonal — the persistence layer touches `data/notes.db` only, never `content/latex/`; the corpus-write guard is the sandbox's concern (ADR-042). **PASS.**
- **MC-8 (Reinforcement loop preserved).** The `test_passed` column is the raw correctness signal the grading slice reads to set `is_correct` (the wrong-answer-replay history the composition slice will read) and identify Weak Topics; no loop logic is changed here; the first-Quiz-only guard (ADR-037) is untouched. **PASS.**
- **MC-1 / MC-2 / MC-3 / MC-4 / MC-9** — orthogonal (no AI, no Quiz-scope, no designation, no AI-async, no generation logic in the persistence layer). **PASS.**

## Test-writer pre-flag

New pytest (persistence + migration tests under `tests/`):

- `save_attempt_test_result` round-trip — `start_attempt` creates the `attempt_questions` rows; `save_attempt_test_result(attempt_id, question_id, passed=True, status="ran", output="...")` UPDATEs the row; `list_attempt_questions(attempt_id)` (after a fresh DB connection) returns an `AttemptQuestion` with `test_passed=True`, `test_status="ran"`, `test_output="..."`, `test_run_at` non-NULL, and `is_correct`/`explanation` still `None` (untouched — the grading slice sets those).
- `save_attempt_test_result` with `passed=None, status="timed_out"` → the row has `test_passed=None`, `test_status="timed_out"` — the failure mode is persisted distinctly, not conflated with pass/fail (MC-5's spirit).
- `save_attempt_test_result` with a `(attempt_id, question_id)` pair that has no row → silent no-op (mirrors `save_attempt_responses`).
- `get_question(question_id)` → the `Question` carrying its `test_suite` (and `topics` split to `list[str]`); `get_question(<unknown id>)` → `None`.
- `list_attempt_questions` carries `test_suite` + the four `test_*` fields through (they're `None` before any run; populated after a `save_attempt_test_result`); order/filtering unchanged (ADR-039's existing assertions still hold).
- The additive migration — on a DB that predates these columns, `_apply_additive_migrations` (via `get_connection`) adds `test_passed` / `test_status` / `test_output` / `test_run_at` to `attempt_questions` (a `PRAGMA table_info(attempt_questions)` after a connection shows them); on a fresh DB, the `CREATE TABLE attempt_questions` block already declares them; running it twice is a no-op (idempotent — no migration-trigger, ADR-022).
- A boundary grep: `import sqlite3` and SQL literals only under `app/persistence/`; `save_attempt_test_result` / `get_question` are re-exported from `app/persistence/__init__.py`'s `__all__`; no `user_id` anywhere in the new code.

(The sandbox pytest pre-flag is in ADR-042; the route + take-surface pytest/Playwright pre-flag is in ADR-043.)
