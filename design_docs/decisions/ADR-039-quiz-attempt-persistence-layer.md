# ADR-039: The Quiz Attempt persistence layer — `app/persistence/quizzes.py` gains `start_attempt` / `get_attempt` / `get_latest_attempt_for_quiz` / `list_questions_for_quiz` / `list_attempt_questions` / `save_attempt_responses` / `submit_attempt`, the `QuizAttempt` and `AttemptQuestion` dataclasses, `attempt_questions` rows created at Attempt start, and an additive `idx_attempt_questions_attempt_id` index

**Status:** `Accepted`
Auto-accepted by /auto on 2026-05-12
**Date:** 2026-05-12
**Task:** TASK-015
**Resolves:** none (no project_issue was filed against the Attempt-persistence layer; ADR-033 §Module-path-and-public-API forecast the Attempt-lifecycle functions and said "the rest are forecast and may be added incrementally by later tasks rather than all stubbed now" — this ADR fills that in for the TASK-015 slice)
**Supersedes:** none — this ADR *adds* under ADR-022's umbrella and ADR-033's schema; it consumes the `quiz_attempts` / `attempt_questions` tables (already in `connection.py`'s `_SCHEMA_SQL`) unchanged and adds one additive index. The Quiz-taking surface that calls these functions is decided in ADR-038 (proposed in the same `/design` cycle). No prior ADR is re-decided.
**Superseded by:** none

## Context

ADR-033 (Accepted, TASK-013) shipped the Quiz domain schema — five tables, all created via `CREATE TABLE IF NOT EXISTS` in `connection.py`'s `_SCHEMA_SQL`, under ADR-022's persistence boundary (`import sqlite3` and SQL literals only under `app/persistence/`; routes call typed public functions; callers receive dataclasses, not `sqlite3.Row` tuples). Two of those tables — `quiz_attempts` (`attempt_id` PK, `quiz_id` FK, `status` TEXT default `'in_progress'`, `created_at`, `submitted_at` nullable, `graded_at` nullable; index `idx_quiz_attempts_quiz_id`) and `attempt_questions` (`attempt_id` FK, `question_id` FK, `response` TEXT nullable, `is_correct` INTEGER nullable, `explanation` TEXT nullable; PK `(attempt_id, question_id)`; index `idx_attempt_questions_question_id`) — have *no* public-API functions yet: TASK-013 shipped only the read accessor (`list_quizzes_for_chapter`) and the `requested`-row creator (`request_quiz`); TASK-014 added the generation functions (`mark_quiz_generating` / `mark_quiz_ready` / `mark_quiz_generation_failed` / `add_questions_to_quiz` / `list_requested_quizzes` / `get_quiz` / `section_has_nonfailed_quiz`). ADR-033 §Module-path-and-public-API forecast the Attempt-lifecycle functions ("`start_attempt` / `get_attempt` / `list_questions_for_quiz` / `save_attempt_responses` / `submit_attempt`") and said the forecast functions "may be added incrementally by later tasks rather than all stubbed now."

TASK-015 (the Quiz-taking surface — ADR-038) is the first thing that *writes* `quiz_attempts` / `attempt_questions`: the learner opens a `ready` Quiz, an Attempt starts, the learner writes code against each Question, submits, and the submission persists as a `quiz_attempts` row (`in_progress` → `submitted`) + one `attempt_questions` row per Question carrying the learner's `response`. No grading happens this slice — `attempt_questions.is_correct` / `.explanation` stay NULL; no Grade aggregate; the submit route does not invoke grading (MC-4). The take route + template + submit route (ADR-038) need typed public functions in `app/persistence/quizzes.py` to: start (or resume) an Attempt for a `ready` Quiz; fetch an Attempt by id; list the Questions in a Quiz in order; list the per-Question state of an Attempt (for the take template's render); save the learner's responses; flip the Attempt to `submitted`. The exact function set/names, the dataclasses, when `attempt_questions` rows are created (at Attempt start vs at submit — ADR-038 §Decision commits to at-start; this ADR encodes it), and any new index are this ADR's to decide.

The established patterns this ADR mirrors:

- **ADR-033's dataclass-returning convention** — `Quiz` (for a `quizzes` row), `Question` (for a `questions` row, with `topics` split to `list[str]`); a `_row_to_quiz` / `_row_to_question` helper converting `sqlite3.Row` → dataclass; callers never see a raw row.
- **ADR-022's "no delete path is the guarantee"** — `questions` has no delete path in `app/persistence/quizzes.py` (the Question Bank is never deleted, manifest §8); this ADR adds no delete path for `quiz_attempts` or `attempt_questions` either (an Attempt persists across sessions, §7 — there is no "delete Attempt" function this slice or any forecast slice; if one is ever wanted, a future ADR decides it).
- **ADR-024's validation split** — the route handler validates path parameters against the corpus; the persistence layer trusts the caller (`request_quiz(section_id)` does not validate `section_id`; the route does). This ADR's functions follow the same posture — `start_attempt(quiz_id)` trusts that `quiz_id` is a real Quiz (the route validated it via `get_quiz`); `save_attempt_responses(attempt_id, responses)` trusts that `attempt_id` is a real Attempt and that the `question_id`s in `responses` belong to the Attempt's Quiz (the route built `responses` from the take form, whose fields were rendered from the Attempt's `attempt_questions` rows) — though the function may defensively ignore a `question_id` not in the Attempt rather than insert a stray row.
- **ADR-022's migration story** — additive changes only (`CREATE TABLE IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS`, nullable `ALTER TABLE ADD COLUMN`); a non-additive change forces a follow-up ADR. The new index this ADR adds is `CREATE INDEX IF NOT EXISTS`, i.e. additive — no migration trigger.
- **ADR-033's "two implementations of a 2-line function is not a real DRY violation"** — `quizzes.py` has its own `_utc_now_iso()` (a duplicate of `notes.py` / `section_completions.py`); this ADR reuses `quizzes.py`'s existing `_utc_now_iso()`.

The decision space has materially different alternatives:

- **The function set / names:** the forecast `start_attempt` / `get_attempt` / `list_questions_for_quiz` / `save_attempt_responses` / `submit_attempt` (plus a per-Question-state accessor the take template needs); a thinner set; a fatter set with mid-edit-autosave functions now.
- **Whether `attempt_questions` rows are created at Attempt start or at submit:** at start (one row per Question, `response` NULL — `save_attempt_responses` is an `UPDATE`); at submit (the rows are created with the responses in one `INSERT` pass).
- **`start_attempt`'s semantics when an `in_progress` Attempt for the Quiz already exists:** reuse the latest `in_progress` Attempt (no orphan rows from idle reloads); always create a new Attempt (a fresh Attempt each take-surface-load); raise (the caller must explicitly resume).
- **The dataclasses:** a `QuizAttempt` mirroring the `quiz_attempts` columns + an `AttemptQuestion` carrying `question_id` / `prompt` / `response` / `position` (a convenience for the take template); only `QuizAttempt` + the template takes `Question`s + a `{question_id: response}` dict separately; a fatter `QuizAttempt` carrying its `attempt_questions` rows inline.
- **The `responses` parameter shape for `save_attempt_responses`:** a `dict[int, str]` (`question_id` → code); a `list[tuple[int, str]]`; a `list[AttemptQuestion]` with updated `response`s.
- **The new index:** `idx_attempt_questions_attempt_id` on `attempt_questions (attempt_id)`; no new index (the existing `idx_attempt_questions_question_id` + the PK `(attempt_id, question_id)` may suffice — SQLite can use the PK's leading column for `WHERE attempt_id = ?`); a composite index.

The manifest constrains the decision through §5 ("No non-coding Question formats … Every Question is a hands-on coding task" — `attempt_questions.response` holds the learner's *code*; no choice/recall/describe field; "No multi-user features" — no `user_id` on `quiz_attempts` / `attempt_questions` / any dataclass; "No live / synchronous AI results" — the functions perform no AI work; `submit_attempt` flips the status to `submitted`, not `graded`), §6 ("AI work is asynchronous" — the persistence functions are the durable record the async grading slice will later `UPDATE`; "AI failures are visible … never fabricates a result" — `is_correct`/`explanation` stay NULL until grading; the functions never fabricate a Grade; "Single-user"; "Lecture source read-only" — the persistence layer does not touch `content/latex/`), §7 ("A Quiz is bound to exactly one Section" — `start_attempt(quiz_id)` produces an Attempt referencing one Quiz, whose `quiz_questions` rows are all of one Section, MC-2; "Every Question is a hands-on coding task. The learner writes code" — `attempt_questions.response` is the code; "Every post-first Quiz … contains both replayed wrong-answer Questions and freshly-generated Questions" — the `attempt_questions.is_correct` column the grading slice fills is the wrong-answer-replay history the composition slice reads; this slice records the `response`, leaving room for both; "Quiz generation is always explicitly user-triggered" — the persistence functions generate nothing; "Every Quiz Attempt … persists across sessions and is owned by the single user" — the central invariant: a `quiz_attempts` row + its `attempt_questions` rows persists; no `user_id`), §8 (Quiz Attempt — "A single submission of a Quiz by the user. Carries the user's responses, a progress status through grading, and — once graded — a Grade" — `QuizAttempt` mirrors the `quiz_attempts` row up to `submitted`; the `graded_at` column is present but NULL this slice; the Grade aggregate is deferred; Question / Question Bank — `list_questions_for_quiz` reads them, never adds or deletes; Grade / Weak Topic / Notification — out of scope this slice).

## Decision

### The function set — `start_attempt`, `get_attempt`, `get_latest_attempt_for_quiz`, `list_questions_for_quiz`, `list_attempt_questions`, `save_attempt_responses`, `submit_attempt`

Seven new public functions in `app/persistence/quizzes.py`, re-exported by `app/persistence/__init__.py` (single import surface per ADR-022). All SQL literals and parameter binding for these stay in `quizzes.py` (MC-10); none consults the filesystem (Section/Chapter validation is the route handler's job, ADR-024's split). (`get_latest_attempt_for_quiz` was added to this set in-flight during TASK-015 implementation — see the §Amendment note at the end; the rest were in the ADR as originally written.)

```python
@dataclass
class QuizAttempt:
    """A single quiz_attempts row (a Quiz Attempt, manifest §8). No user_id (MC-7)."""
    attempt_id: int
    quiz_id: int
    status: str            # 'in_progress' | 'submitted' | 'grading' | 'graded' | 'grading_failed' (ADR-033)
    created_at: str        # ISO-8601 UTC
    submitted_at: str | None  # NULL until submitted
    graded_at: str | None     # NULL until graded (deferred — Grade aggregate ships with the grading slice)


@dataclass
class AttemptQuestion:
    """One Question's state within an Attempt — a convenience join of attempt_questions + the Question's prompt.
    The take template iterates these (in `position` order) to render each Question's prompt + a code field.
    No is_correct / explanation here this slice (they are NULL until grading; the grading slice's accessor adds them)."""
    question_id: int
    prompt: str            # the Question's coding-task prompt (from questions.prompt)
    response: str | None   # the learner's code for this Question in this Attempt; NULL until they submit
    position: int          # 1-based order within the Quiz (from quiz_questions.position)


def start_attempt(quiz_id: int) -> QuizAttempt:
    """Start (or resume) a Quiz Attempt for a `ready` Quiz.

    - If the Quiz already has an `in_progress` Attempt, reuse the latest one (by created_at / attempt_id) —
      no second quiz_attempts row from an idle take-surface reload.
    - Otherwise INSERT a quiz_attempts row (status='in_progress', created_at=<now>, submitted_at/graded_at NULL),
      then INSERT one attempt_questions row per Question in the Quiz (response/is_correct/explanation all NULL),
      ordered by quiz_questions.position. All in one transaction.
    - Trusts the caller: quiz_id is a real `ready` Quiz (the route validated via get_quiz). This function does not
      re-validate the Quiz's status — but a Quiz with no quiz_questions rows (not yet generated) yields an Attempt
      with no attempt_questions rows, which the take surface would render as an empty Quiz (the route's `ready`-check
      prevents reaching here for a non-`ready` Quiz in practice).
    - No user_id (MC-7). SQL stays here (MC-10).
    Returns the QuizAttempt (the reused or newly-created one)."""


def get_attempt(attempt_id: int) -> QuizAttempt | None:
    """Return a single Attempt by attempt_id, or None if not found. SQL stays here (MC-10)."""


def get_latest_attempt_for_quiz(quiz_id: int) -> QuizAttempt | None:
    """Return the most recent Attempt (any status) for a Quiz — ordered by created_at / attempt_id descending —
    or None if the Quiz has no Attempts. Used by GET .../take to detect a `submitted` latest Attempt and render
    the submitted state, instead of calling start_attempt (which only ever returns/creates an `in_progress`
    Attempt and would therefore spawn a fresh blank Attempt after the submit PRG-redirect). Read-only; no INSERT.
    No user_id (MC-7). SQL stays here (MC-10)."""


def list_questions_for_quiz(quiz_id: int) -> list[Question]:
    """Return the Questions composing a Quiz, ordered by quiz_questions.position.
    A join of quiz_questions ⨝ questions; returns Question dataclasses (topics split to list[str], per ADR-033).
    (Used wherever the Quiz's Questions are needed without an Attempt context; the take template uses
    list_attempt_questions, which carries the learner's response too.) SQL stays here (MC-10)."""


def list_attempt_questions(attempt_id: int) -> list[AttemptQuestion]:
    """Return the per-Question state of an Attempt — one AttemptQuestion per attempt_questions row, joined with the
    Question's prompt and the quiz_questions.position, ordered by position. This is what the take template iterates.
    Returns [] for an unknown attempt_id or an Attempt with no attempt_questions rows. SQL stays here (MC-10)."""


def save_attempt_responses(attempt_id: int, responses: dict[int, str]) -> None:
    """Write the learner's code for each Question in an Attempt. `responses` maps question_id -> code-string.
    For each (question_id, code) in responses: UPDATE attempt_questions SET response = ? WHERE attempt_id = ?
    AND question_id = ? — i.e. updates existing rows (created at Attempt start); a question_id not present in the
    Attempt's rows is ignored (no stray INSERT — defensive, since the route built `responses` from the Attempt's
    own rows). Stored response is the code verbatim (no transformation). Does NOT change the Attempt's status —
    submit_attempt does that. All in one transaction. No user_id (MC-7). SQL stays here (MC-10)."""


def submit_attempt(attempt_id: int) -> None:
    """Submit an Attempt: UPDATE quiz_attempts SET status = 'submitted', submitted_at = <now> WHERE attempt_id = ?.
    Does NOT touch attempt_questions, does NOT touch is_correct/explanation, does NOT invoke grading (MC-4 —
    grading is a later out-of-band slice). Idempotent-ish: submitting an already-submitted Attempt is a harmless
    no-op-ish UPDATE (the route resolves the latest `in_progress` Attempt before calling, so a double-POST is
    handled at the route, not here). No user_id (MC-7). SQL stays here (MC-10)."""
```

(Exact SQL phrasing, the `_row_to_quiz_attempt` / `_row_to_attempt_question` helper shapes, and whether `start_attempt` builds the `attempt_questions` rows from `list_questions_for_quiz`'s result or from an inline join are implementer-tunable; the function signatures, the dataclass field sets, the at-start `attempt_questions`-creation, the reuse-the-latest-`in_progress` semantics for `start_attempt`, the no-grading discipline, and the no-`user_id` / SQL-stays-here boundary are the architectural commitments.)

**Why this set and not more/fewer:**

- **`start_attempt(quiz_id)` reusing the latest `in_progress` Attempt** is the simplest "the Attempt persists" (§7) shape that does not spawn orphan `in_progress` rows from idle take-surface reloads — the take route calls it on every `GET .../take`, and reusing the existing `in_progress` Attempt (rather than always creating a new one) means a reload lands the learner back on the same Attempt. A "resume an `in_progress` Attempt across sessions" affordance beyond this — explicitly listing past Attempts, choosing which to resume — is not required this slice (TASK-015 §Out-of-scope); a future task with a real reason owns it. ("Always a new Attempt" was the alternative — rejected: a fresh Attempt each reload is wasteful and confusing for the single user; "raise — caller must explicitly resume" was rejected as pushing complexity onto the route for no benefit.)
- **`attempt_questions` rows created at Attempt start** (ADR-038 §Decision commits to this; this ADR encodes it): `start_attempt` INSERTs one row per Question (`response`/`is_correct`/`explanation` NULL); `save_attempt_responses` is therefore an `UPDATE` keyed on `(attempt_id, question_id)` against existing rows. This makes the per-Question-state structure (`response` now; `is_correct`/`explanation` later, filled by the grading slice's `UPDATE`; `question_id` read by the composition slice's `SELECT ... WHERE is_correct = 0`) exist from the moment the Attempt exists — the grading slice and the composition slice never have to handle "the row might not exist yet" — and keeps the take template's render path uniform (it always iterates `AttemptQuestion`s). Creating-at-submit (the rows INSERTed with the responses in one pass) is workable and the AC permits it, but it leaves an `in_progress` Attempt with no `attempt_questions` rows — a less uniform structure for no offsetting benefit at this scope.
- **`list_attempt_questions(attempt_id) -> list[AttemptQuestion]`** is the convenience the take template needs — for each Question in the Attempt, in order: the `question_id`, the coding-task `prompt`, the current `response` (NULL on a fresh Attempt; the submitted code in the "submitted" state). Returning `Question`s + a separate `{question_id: response}` dict was the alternative — rejected as making the template stitch two structures together for every render. A fatter `QuizAttempt` carrying its `attempt_questions` rows inline was rejected — it conflates "the Attempt row" with "the Attempt's per-Question state", which are queried at different times (the route fetches the Attempt to check its status, then fetches the per-Question rows to render).
- **`list_questions_for_quiz(quiz_id) -> list[Question]`** is shipped (even though the take template uses `list_attempt_questions`) because (a) ADR-033 forecast it, (b) it is the natural "what Questions does this Quiz contain, in order" accessor that future surfaces (a Grade display, a "review this Quiz's Questions" view) will want, and (c) `start_attempt` may use it internally to build the `attempt_questions` rows. It is a thin join (`quiz_questions ⨝ questions`, ordered by `position`); no cost to ship.
- **`get_attempt(attempt_id) -> QuizAttempt | None`** is the standard single-row accessor (mirroring `get_quiz`); the take/submit routes use it to check an Attempt's status.
- **`get_latest_attempt_for_quiz(quiz_id) -> QuizAttempt | None`** closes the gap between ADR-038 §GET's described submitted-state behavior ("if the Attempt is already `submitted` … render the submitted state instead of a takeable form") and the rest of this function set: `start_attempt` only ever returns/creates an `in_progress` Attempt, and `get_attempt` needs the `attempt_id`, so without a "latest Attempt for this Quiz, any status" accessor a re-`GET` after the submit PRG-redirect would spawn a fresh blank `in_progress` Attempt instead of showing the submitted state. It is a thin read accessor (`SELECT … WHERE quiz_id = ? ORDER BY created_at DESC, attempt_id DESC LIMIT 1`); no cost to ship. (Added in-flight during TASK-015 implementation — the implementer surfaced the gap, the human gated the addition; see the §Amendment note.)
- **`save_attempt_responses` takes a `dict[int, str]`** (`question_id` → code) — the natural shape for "the route built a map from the take form's fields, each keyed by `question_id`"; a `list[tuple[int, str]]` was the alternative (no real difference; a dict is the more idiomatic "keyed by `question_id`" shape).
- **No mid-edit-autosave function this slice** — the take surface has no mid-edit save (ADR-038 §Decision: `save_attempt_responses` is called once, by the submit route); an autosave-on-each-keystroke / autosave-on-blur function (which would need a JS caller and a per-Question save endpoint) is a future task's addition.
- **No `delete_attempt` / `delete_attempt_questions` function** — an Attempt persists across sessions (§7); there is no delete path this slice or any forecast slice. (If a "discard this Attempt" affordance is ever wanted — e.g. to clean up orphan `in_progress` Attempts — a future ADR decides it; the absence of a delete path is the guarantee, mirroring `questions`'s no-delete-path posture.)

### `attempt_questions` rows are created at Attempt start — encoded here

`start_attempt`, when it creates a new Attempt (not when it reuses an `in_progress` one), INSERTs one `attempt_questions` row per Question in the Quiz, with `response` / `is_correct` / `explanation` all NULL, ordered by `quiz_questions.position` (the `position` column on `quiz_questions` is not stored on `attempt_questions` — the order is recovered by joining back to `quiz_questions` in `list_attempt_questions` / `list_questions_for_quiz`). All in one transaction with the `quiz_attempts` INSERT. ADR-038 §Decision and §Alternative D explain the choice (clean `UPDATE` for `save_attempt_responses`; uniform per-Question structure from the moment the Attempt exists; the grading and composition slices never face "the row might not exist yet"); this section is the persistence-layer encoding of it.

### The new index — `idx_attempt_questions_attempt_id` on `attempt_questions (attempt_id)`, additive

`connection.py`'s `_SCHEMA_SQL` gains one line:

```sql
CREATE INDEX IF NOT EXISTS idx_attempt_questions_attempt_id ON attempt_questions (attempt_id);
```

The `attempt_questions` table currently has `idx_attempt_questions_question_id` (added by ADR-033, for the grading/composition slices' `WHERE question_id = ?` / `is_correct = 0` queries) and the PK `(attempt_id, question_id)`. The TASK-015 paths query `attempt_questions` by `attempt_id` (`list_attempt_questions(attempt_id)`, `save_attempt_responses(attempt_id, ...)`'s per-row `UPDATE ... WHERE attempt_id = ? AND question_id = ?`); SQLite *can* use the PK's leading column (`attempt_id`) for those, so a dedicated `attempt_id` index is not strictly required for correctness — but adding it is cheap, additive (`CREATE INDEX IF NOT EXISTS`, no migration trigger per ADR-022), consistent with the project's "index the FK columns surfaces query by" pattern (`idx_quiz_attempts_quiz_id`, `idx_quiz_questions_question_id`, `idx_questions_section_id`, `idx_quizzes_section_id`, `idx_notes_chapter_id`, `idx_section_completions_chapter_id`), and makes the "list this Attempt's per-Question rows" path explicit. It is added to `_SCHEMA_SQL` (ADR-024's mechanic — extend the `_SCHEMA_SQL` block; the per-module schema-fragment refactor ADR-033 flagged "when the n-tables threshold makes the monolithic block awkward" is *not* triggered by this task — no new table, just one index line). No new `ALTER TABLE` is needed (no new column this task).

### No `user_id`; SQL stays under `app/persistence/`

No `user_id` column on `quiz_attempts` / `attempt_questions` / `QuizAttempt` / `AttemptQuestion` / any new structure (ADR-033 already omits it from the tables; this ADR omits it from the dataclasses and adds no auth/session/per-user-partitioning anywhere) — manifest §5/§6/§7, MC-7. `import sqlite3` and all SQL string literals for the Quiz domain stay in `app/persistence/quizzes.py` (and `connection.py` for the schema/index DDL) — MC-10; the take route, the submit route, and `quiz_take.html.j2` (ADR-038) call only the typed public functions re-exported by `app/persistence/__init__.py`, receiving dataclass instances, never a `sqlite3.Connection` or a raw row tuple.

### What is NOT changed or decided by this ADR

- **The `quiz_attempts` / `attempt_questions` table schemas** (ADR-033) — consumed unchanged; this ADR adds access functions + dataclasses + one additive index, not a schema change.
- **The `quizzes` / `questions` / `quiz_questions` tables and their existing public functions** (ADR-033, ADR-036, ADR-037) — unchanged; this ADR adds Attempt-lifecycle functions alongside them.
- **The `quiz_attempts.status` enum** (`in_progress` → `submitted` → `grading` → `graded` → `grading_failed`, ADR-033) — consumed unchanged; this slice exercises `in_progress` and `submitted`; the `grading` / `graded` / `grading_failed` states and the functions that drive them (the grading slice's `mark_attempt_grading` / `mark_attempt_graded` / `mark_attempt_grading_failed` / `save_attempt_grades` or similar) are the grading slice's job.
- **The Grade aggregate's schema** (score / weak-topics / recommended-sections — ADR-033 deferred it "to the grading task") — still deferred; this slice ships no `grades` table, no `score` / `weak_topics` / `recommended_sections` columns, no functions for them. **Not smuggled in.**
- **The `attempt_questions.is_correct` / `.explanation` columns** — present (ADR-033), NULL until grading; this slice's functions never write them; the grading slice's `UPDATE` does. **Not fabricated.**
- **The `notifications` table** (ADR-022 / ADR-037 — ships with the grading slice) — still deferred. **Not smuggled in.**
- **The relational Topic vocabulary** (`topics` table + `question_topics` join — ADR-033 deferred it "to the generation task", ADR-036 re-deferred it "to the Weak-Topic-identification slice") — still deferred; `list_questions_for_quiz` returns `Question`s with `topics` split from the existing `questions.topics` `'|'`-delimited column (ADR-033), unchanged. **Not smuggled in.**
- **Mid-edit autosave functions / a per-Question save endpoint / a `delete_attempt` function / a "list all Attempts for a Quiz/Section" accessor** — future tasks; not this slice.
- **The Quiz-taking surface itself** (the take route pair, the template, the layout, the take affordance, the submit-route redirect, the CSS) — owned by ADR-038 (proposed in the same `/design` cycle); this ADR supplies the persistence functions ADR-038 calls.
- **The per-module schema-fragment refactor** ADR-033 flagged for "when the n-tables threshold makes the monolithic `_SCHEMA_SQL` block awkward" — not triggered (no new table; one index line); the architect notes it again only as a standing flag, not a TASK-015 deliverable.

### Test-writer pre-flag — new persistence tests; no existing test broken

- **No existing test breaks by design** — this ADR *adds* functions/dataclasses/an index; it changes no existing function or schema. If an existing test fails, that is a regression to fix.
- **New pytest** (under `tests/`): `start_attempt(quiz_id)` on a `ready` Quiz with ≥1 Question creates a `quiz_attempts` row with `status='in_progress'`, the right `quiz_id`, `created_at` set, `submitted_at`/`graded_at` NULL, and one `attempt_questions` row per Question with `response`/`is_correct`/`explanation` all NULL; calling `start_attempt` again for the same Quiz reuses the latest `in_progress` Attempt (no second `quiz_attempts` row); `get_attempt(attempt_id)` returns the `QuizAttempt` (and `None` for an unknown id); `list_questions_for_quiz(quiz_id)` returns the Quiz's Questions in `quiz_questions.position` order; `list_attempt_questions(attempt_id)` returns one `AttemptQuestion` per attempt row (`question_id` / `prompt` / `response` / `position`) in order, and `[]` for an unknown id; `save_attempt_responses(attempt_id, {qid: code})` writes each `response` verbatim (and ignores a `question_id` not in the Attempt — no stray row); `submit_attempt(attempt_id)` flips `status` → `submitted`, sets `submitted_at`, leaves `attempt_questions.is_correct`/`.explanation` NULL, leaves `attempt_questions.response` as saved; the Attempt persists across sessions (re-querying via `get_attempt` / `list_attempt_questions` after a new connection returns the `submitted` Attempt with the learner's responses); no `user_id` on any new row or dataclass (MC-7); `idx_attempt_questions_attempt_id` is created via `CREATE INDEX IF NOT EXISTS` (additive — no migration trigger; assert via `PRAGMA index_list(attempt_questions)` or a schema-introspection check); the MC-10 boundary grep extended to confirm `import sqlite3` / SQL literals for the Attempt functions stay under `app/persistence/`. (The route-level and rendered-surface tests — the take route, the submit route's MC-4 no-grading-in-the-request check, the rendered take surface — are ADR-038's test-writer pre-flag.)
- The test-writer should **not** raise `CANNOT TEST AC-N` on the human-only verification gates — they are correctly placed under TASK-015's "Verification gates (human-only; not programmatic ACs)" section.

### Scope of this ADR

This ADR fixes only:

1. The Attempt-lifecycle public functions in `app/persistence/quizzes.py`: `start_attempt(quiz_id) -> QuizAttempt` (reuse-the-latest-`in_progress` semantics; creates `attempt_questions` rows at Attempt start), `get_attempt(attempt_id) -> QuizAttempt | None`, `get_latest_attempt_for_quiz(quiz_id) -> QuizAttempt | None` (the most recent Attempt for a Quiz, any status — added in-flight during TASK-015 implementation; see §Amendment), `list_questions_for_quiz(quiz_id) -> list[Question]`, `list_attempt_questions(attempt_id) -> list[AttemptQuestion]`, `save_attempt_responses(attempt_id, responses: dict[int, str]) -> None`, `submit_attempt(attempt_id) -> None` — all re-exported by `app/persistence/__init__.py`; SQL stays under `app/persistence/` (MC-10); no `user_id` (MC-7); `submit_attempt` does not invoke grading (MC-4).
2. The `QuizAttempt` dataclass (`attempt_id` / `quiz_id` / `status` / `created_at` / `submitted_at` / `graded_at`) and the `AttemptQuestion` dataclass (`question_id` / `prompt` / `response` / `position`).
3. `attempt_questions` rows created at Attempt start (one per Question, `response`/`is_correct`/`explanation` NULL) — `save_attempt_responses` is an `UPDATE`.
4. The additive `idx_attempt_questions_attempt_id` index, added to `connection.py`'s `_SCHEMA_SQL` via `CREATE INDEX IF NOT EXISTS`.
5. The test-writer pre-flag (new persistence tests; no existing test broken by design).

This ADR does **not** decide:

- The Quiz-taking surface (the take route pair, the template, the layout, the take affordance on the `.section-quiz` block, the submit-route redirect, the CSS) — owned by ADR-038.
- The grading-slice functions (`mark_attempt_grading` etc.), the Grade aggregate's schema, the `notifications` table, the relational Topic vocabulary, mid-edit-autosave functions, a `delete_attempt` function, a "list all Attempts" accessor — all later slices / future tasks; **not smuggled in here**.
- The per-module schema-fragment refactor ADR-033 flagged — not triggered by this task; a standing flag only.
- The exact SQL phrasing, the `_row_to_*` helper shapes, whether `start_attempt` builds `attempt_questions` from `list_questions_for_quiz` or an inline join, the `responses` parameter's exact element shape (a dict vs a list of tuples) — implementer-tunable within the signatures above.

## Alternatives considered

**A. Create `attempt_questions` rows at submit (one `INSERT` pass), not at Attempt start.**
Considered — the AC permits it; it would mean `start_attempt` only creates the `quiz_attempts` row, and `submit_attempt` (or `save_attempt_responses`, called once at submit) INSERTs the `attempt_questions` rows with the responses. **Rejected** in favor of at-start: creating the rows at start makes `save_attempt_responses` a clean `UPDATE` keyed on `(attempt_id, question_id)`, makes the per-Question-state structure exist from the moment the Attempt exists (the grading slice's `UPDATE is_correct/explanation` and the composition slice's `SELECT ... WHERE is_correct = 0` both operate on these rows and never face "the row might not exist yet"), and keeps the take template's render path uniform (always iterate `AttemptQuestion`s). At-submit is workable but less uniform for no offsetting benefit. (ADR-038 §Decision and §Alternative D make the same call from the surface side.)

**B. `start_attempt` always creates a new Attempt (a fresh Attempt each take-surface-load), not reusing the latest `in_progress` one.**
Considered. **Rejected** — a fresh Attempt each `GET .../take` reload is wasteful (orphan `in_progress` rows pile up) and confusing for the single user (which Attempt's responses are "current"?); reusing the latest `in_progress` Attempt is the simplest "the Attempt persists" (§7) shape with no extra click and no orphan-row spawning. A richer "see all my Attempts / start a fresh one" UX is a future task; this slice keeps it simple.

**C. `start_attempt` raises if an `in_progress` Attempt for the Quiz already exists (the caller must explicitly call a separate `resume_attempt`).**
Considered. **Rejected** — pushes complexity onto the route (it would have to catch the raise and call `resume_attempt`) for no benefit; "reuse the latest `in_progress`" inside `start_attempt` is simpler and is exactly what the take route wants on every `GET .../take`.

**D. Only `QuizAttempt` (no `AttemptQuestion`); the take template takes `Question`s + a `{question_id: response}` dict separately.**
Considered. **Rejected** — makes the take template stitch two structures together for every render (for each `Question`, look up its `response` in the dict, find its `position`). An `AttemptQuestion` dataclass carrying `question_id` / `prompt` / `response` / `position` is the convenience; the take template iterates one ordered list. (A fatter `QuizAttempt` carrying its `attempt_questions` rows inline was also rejected — it conflates "the Attempt row" (queried to check status) with "the Attempt's per-Question state" (queried to render), which are fetched at different times.)

**E. No new index — rely on the PK `(attempt_id, question_id)`'s leading column for `WHERE attempt_id = ?`.**
Considered — SQLite can use the PK's leading column, so `idx_attempt_questions_attempt_id` is not strictly required for correctness. **Rejected** in favor of adding it: it is cheap, additive (`CREATE INDEX IF NOT EXISTS` — no migration trigger), consistent with the project's "index the FK columns surfaces query by" pattern (every other FK/scan column has an index), and makes the "list this Attempt's per-Question rows" path explicit rather than implicit-in-the-PK. The marginal cost (one index line, a tiny write-time overhead) is negligible at single-user scale.

**F. A composite index `(attempt_id, question_id)` (separate from the PK).**
Rejected — redundant with the PK, which already provides that exact index. A plain `(attempt_id)` index is the right addition (the PK covers `(attempt_id, question_id)` lookups; a `(attempt_id)`-only index is what helps the "all rows for this Attempt" scan without the PK's second-column overhead — though in practice the PK suffices; the `(attempt_id)` index is the consistent-with-the-pattern choice).

**G. Ship the grading-slice functions now (stub `mark_attempt_grading` etc.) since the grading slice is next.**
Rejected — architecture-on-spec. The grading-slice functions have no consumer until the grading slice exists (which has its own out-of-band processor, Grade-aggregate schema, Weak-Topic-identification path, and `notifications` table — TASK-014-sized on its own); stubbing them now would be functions nothing calls. ADR-033 §Module-path-and-public-API explicitly said the forecast functions "may be added incrementally by later tasks rather than all stubbed now" — this ADR ships the TASK-015 subset; the grading slice ships its subset.

**H. Fold these persistence decisions into ADR-038 (the Quiz-taking-surface ADR) — one ADR, not two.**
Considered — the surface decisions and the persistence decisions are tightly coupled (ADR-038 §Decision references "the functions ADR-039 decides" throughout). **Rejected** in favor of two ADRs: the persistence decisions are substantial enough (six functions, two dataclasses, a new index, the at-start `attempt_questions`-creation, the reuse-the-latest-`in_progress` semantics, the no-`user_id` / SQL-stays-here / no-grading boundary discipline MC-10/MC-7/MC-4 trace to) that a dedicated ADR keeps each focused — mirroring the project's ADR-033 (Quiz schema) → ADR-034 (per-Section Quiz surface) split, which separated the persistence shape from the surface that consumes it for the same reason. (TASK-015 §Architectural-decisions-expected names the persistence ADR as "(optional, may be folded into the take-surface ADR)" and leaves "one ADR or two" to `/design`'s call — the architect picks two.)

## My recommendation vs the user's apparent preference

The TASK-015 task file forecasts this ADR as "(optional, may be folded into the take-surface ADR) The Quiz Attempt persistence layer — the `app/persistence/quizzes.py` Attempt-lifecycle functions, the `QuizAttempt` (and maybe `AttemptQuestion`) dataclass(es), the create-at-start-vs-create-at-submit call for `attempt_questions`, and any new index", with the forecast function set ("`start_attempt(quiz_id) -> QuizAttempt`, `get_attempt(attempt_id) -> QuizAttempt | None`, `list_questions_for_quiz(quiz_id) -> list[Question]`, `save_attempt_responses(attempt_id, responses: dict[int, str])`, `submit_attempt(attempt_id) -> None`") and the instruction "One ADR or two is `/design`'s call".

This ADR is **aligned with the task's forecast**, with these `/design` calls made:

- **Two ADRs, not one** — the persistence decisions are substantial enough to warrant their own ADR, mirroring ADR-033 → ADR-034. (The task left "one or two" to `/design`; the architect picked two.) No disagreement to surface.
- **The function set** — the forecast `start_attempt` / `get_attempt` / `list_questions_for_quiz` / `save_attempt_responses` / `submit_attempt`, **plus `list_attempt_questions`** (the per-Question-state accessor the take template needs — the task's forecast mentioned "maybe an `AttemptQuestion` carrying `question_id` / `prompt` / `response`", which implies an accessor returning them; this ADR makes that accessor explicit). Aligned and slightly expanded for the template's needs.
- **`attempt_questions` rows created at Attempt start** — the task said "the AC permits either"; the architect picked at-start (clean `UPDATE` for `save_attempt_responses`; uniform per-Question structure; the grading and composition slices never face a missing row). Aligned with ADR-038's matching call.
- **`start_attempt` reuses the latest `in_progress` Attempt** — the task said "`/design` may keep it simple: one Attempt per take-surface-load, or one per Quiz with the latest `in_progress` reused; `/design`'s call". The architect picked reuse-the-latest-`in_progress` (no orphan rows, no extra click). Aligned.
- **`QuizAttempt` + `AttemptQuestion` dataclasses** — the task's forecast was "`QuizAttempt`, and maybe an `AttemptQuestion` carrying `question_id` / `prompt` / `response`"; the architect ships both (`AttemptQuestion` also carries `position`). Aligned.
- **`idx_attempt_questions_attempt_id`** — the task's forecast was "an index on `attempt_questions.attempt_id` if not already present"; the architect ships it (additive). Aligned.
- **`responses: dict[int, str]`** — the task's forecast signature exactly. Aligned.

I am NOT pushing back on:

- ADR-033's `quiz_attempts` / `attempt_questions` schema, the `quiz_attempts.status` enum, the no-`user_id` posture, the `'|'`-delimited `questions.topics` column — all consumed unchanged; this ADR adds access functions, two dataclasses, and one additive index, not a schema change.
- ADR-022's persistence boundary (`import sqlite3` + SQL literals only under `app/persistence/`; routes call typed public functions; callers receive dataclasses), the migration story (additive only — the new index is `CREATE INDEX IF NOT EXISTS`), the single-shared-`data/notes.db` rule, the `_SCHEMA_SQL`-extension mechanic (ADR-024's) — all followed.
- ADR-024's validation split (route handler validates; persistence trusts the caller) — followed: `start_attempt` / `save_attempt_responses` / `submit_attempt` trust the caller (the route validated `quiz_id` via `get_quiz` and built `responses` from the Attempt's own rows); `save_attempt_responses` defensively ignores a `question_id` not in the Attempt rather than insert a stray row.
- ADR-038's Quiz-taking surface — this ADR supplies the functions it calls; the surface decisions (route shape, template, layout, take affordance, submit redirect, CSS) are ADR-038's, not re-decided here.
- The single-user posture (manifest §5/§6/§7, MC-7) — preserved: no `user_id` on `quiz_attempts` / `attempt_questions` / `QuizAttempt` / `AttemptQuestion` / any new structure; no auth, no session, no per-user partitioning.
- The "AI work asynchronous" rule (MC-4 / §6) — preserved: `submit_attempt` flips the status to `submitted`, not `graded`; no AI call; the (later) out-of-band grading slice will `UPDATE` the `grading`/`graded`/`grading_failed` states and fill `is_correct`/`explanation`.
- The "AI failures surfaced, never fabricated" rule (MC-5) — preserved: `is_correct`/`explanation` stay NULL until grading; the functions never fabricate a Grade; the Grade aggregate is deferred.
- The "Quizzes scope to Sections" rule (MC-2 / §6 / §7) — preserved: `start_attempt(quiz_id)` produces an Attempt referencing one Quiz, whose `quiz_questions` rows are all of one Section; `list_questions_for_quiz` / `list_attempt_questions` query within one `quiz_id`; no function composes an Attempt or a Question list across Sections.
- The "reinforcement loop preserved" rule (MC-8 / §7) — preserved: the `attempt_questions.is_correct` column the grading slice fills (on the rows this slice creates) is the wrong-answer-replay history the composition slice reads; this slice records the `response`, leaving room for both loop portions without a non-additive migration; no fresh-only-post-first-Quiz path is created.
- The read-only Lecture source rule (manifest §6, MC-6) — preserved: the persistence layer does not touch `content/latex/`; the Attempt rows live in `data/notes.db`.
- The "Every Question is a hands-on coding task" rule (manifest §5/§7) — preserved: `attempt_questions.response` (and `AttemptQuestion.response`) holds the learner's *code*; no choice/recall/describe field anywhere; `list_questions_for_quiz` returns `Question`s whose `prompt` is the coding-task instruction (ADR-033).
- ADR-035 (ADRs describe the architecture *used*) — followed: this ADR records the functions the persistence layer *uses* for the take/submit slice; it does not prohibit a future mid-edit-autosave function or a `delete_attempt` function — those are decided on their merits in their own ADRs when a task needs them.

## Manifest reading

Read as binding for this decision:

- **§5 Non-Goals.** "No non-coding Question formats … Every Question is a hands-on coding task" — `attempt_questions.response` / `AttemptQuestion.response` hold the learner's *code*; no `option_*` / `correct_choice` / `answer_text` / `describe_*` / `recall_*` field on any dataclass or in any function signature. "No multi-user features. No accounts, no auth, no sharing, no social, no roles" — no `user_id` on `quiz_attempts` / `attempt_questions` / `QuizAttempt` / `AttemptQuestion`; no auth, no session, no per-user partitioning in any function. "No live / synchronous AI results" — the functions perform no AI work; `submit_attempt` flips the status to `submitted`, not `graded`; the async grading slice will later `UPDATE` the grading states. "No LMS features / No remote deployment" — none crossed (the persistence layer is local SQLite, ADR-022).
- **§6 Behaviors and Absolutes.** "AI work is asynchronous from the learner's perspective. Submission, processing, and result delivery are decoupled in time" — these functions are the *durable record* of the submission (`quiz_attempts` row `submitted`, `attempt_questions.response` populated); the *processing* (the grading slice's `UPDATE is_correct/explanation`, the Grade aggregate) is decoupled in time; `submit_attempt` does not invoke it. "AI failures are visible … never fabricates a result" — `is_correct`/`explanation` stay NULL until grading; the functions never fabricate a Grade; the absence of a Grade is honest, not papered over. "Single-user" — no multi-tenant data path. "Lecture source read-only" — the persistence layer does not touch `content/latex/`.
- **§7 Invariants.** **"A Quiz is bound to exactly one Section."** — `start_attempt(quiz_id)` produces an Attempt referencing one Quiz, whose `quiz_questions` rows are all of one Section (the generation processor, ADR-037, links only Questions of the Quiz's Section); no function composes an Attempt across Sections (MC-2). **"Every Question is a hands-on coding task. The learner writes code that implements a concept from the Section under study."** — `attempt_questions.response` is the code; `list_questions_for_quiz` returns `Question`s whose `prompt` is the coding-task instruction. **"Every post-first Quiz for a Section contains both replayed wrong-answer Questions and freshly-generated Questions."** — the `attempt_questions.is_correct` column the grading slice fills (on the rows `start_attempt` creates) is the wrong-answer-replay history the composition slice reads; this slice records the `response`, leaving room for both loop portions; no fresh-only-post-first-Quiz path is created here. **"Quiz generation is always explicitly user-triggered."** — the persistence functions generate nothing. **"Every Quiz Attempt, Note, and completion mark persists across sessions and is owned by the single user."** — the central invariant this ADR's functions implement: a `quiz_attempts` row + its `attempt_questions` rows is created by `start_attempt`, updated by `save_attempt_responses` / `submit_attempt`, and persists across sessions (`get_attempt` / `list_attempt_questions` re-query it after a new connection); owned by the single user (no `user_id` — there is one). There is no delete path — an Attempt persists.
- **§8 Glossary.** **Quiz Attempt** — "A single submission of a Quiz by the user. Carries the user's responses, a progress status through grading, and — once graded — a Grade" — `QuizAttempt` mirrors the `quiz_attempts` row (`status` is the progress-through-grading enum; `submitted_at` / `graded_at` the lifecycle timestamps); this slice ships the Attempt up to `submitted`; the `graded_at` column is present but NULL; the Grade aggregate is deferred. **Question** — "A single graded item … a hands-on coding task … Persists with full Attempt history (which Attempts it appeared in, correctness in each)" — `list_questions_for_quiz` reads `Question`s; the `attempt_questions` rows `start_attempt` creates are this Question's "appearance in this Attempt"; the "correctness in each" (`is_correct`) is filled by the grading slice. **Question Bank** — `list_questions_for_quiz` reads from it (via `quiz_questions ⨝ questions`); it never adds or deletes a Question. **Grade / Weak Topic / Notification** — out of scope this slice; no function or dataclass for them. No new glossary terms forced.

No manifest entries flagged as architecture-in-disguise for this decision. The persistence-layer additions are operational data-access design applying the project's encoded patterns (ADR-022's boundary, ADR-024's validation split, ADR-033's dataclass-returning convention, ADR-022's additive-migration story); no manifest-level change.

## Conformance check

- **MC-1 (No direct LLM/agent SDK use).** Honored trivially. The Attempt-persistence functions perform no AI work — they execute SQL via the existing `get_connection()` and return dataclasses; no LLM SDK import, no `ai-workflows` invocation; this task adds no `app/workflows/` code. **Manifest portion: PASS.** **Architecture portion (ADR-036 Accepted): PASS** — stays satisfied (no AI import added anywhere).
- **MC-2 (Quizzes scope to exactly one Section).** Honored by construction. `start_attempt(quiz_id)` produces an Attempt referencing one Quiz; its `attempt_questions` rows are one per Question in that Quiz's `quiz_questions` rows, which the generation processor (ADR-037) populated only with Questions of the Quiz's Section; `list_questions_for_quiz` / `list_attempt_questions` query within one `quiz_id` / `attempt_id`; no function takes multiple `section_id`s or composes an Attempt/Question-list across Sections. **PASS.**
- **MC-3 (Mandatory/Optional designation respects the canonical mapping).** Not directly implicated — the persistence layer has no designation logic (the take route, ADR-038, renders the designation via ADR-004's `chapter_designation()`); no hardcoded chapter-number rule introduced. **PASS** (by non-involvement; the architecture portion remains as ADR-004 defined).
- **MC-4 (AI work asynchronous).** Honored. `submit_attempt` flips `quiz_attempts.status` → `submitted` and sets `submitted_at`; it does **not** transition to `grading`/`graded`, does **not** invoke any AI workflow, does **not** start a background job; the Attempt sits in `submitted` until the (later) out-of-band grading slice's processor picks it up — exactly as ADR-037's generation processor picks up `requested` Quizzes. **PASS** (manifest principle; the grading-workflow-name enumeration stays `cannot evaluate (ADR pending)`).
- **MC-5 (AI failures surfaced, never fabricated).** Honored. `attempt_questions.is_correct` / `.explanation` are NULL after `start_attempt` and stay NULL after `save_attempt_responses` / `submit_attempt` — the functions never write a fabricated correctness value or explanation; no function synthesizes a Grade aggregate (the aggregate is deferred); the absence of a Grade is represented honestly (NULL columns), not papered over. **PASS.**
- **MC-6 (Lecture source is read-only to the application).** Honored. The persistence layer does not open anything under `content/latex/` (the take route validates the Section ID via the existing `extract_sections` read path — ADR-038 — not the persistence layer); the Attempt rows live in `data/notes.db`. **PASS** (the lecture source root remains as ADR-001 defined).
- **MC-7 (Single user).** Honored. No `user_id` column on `quiz_attempts` / `attempt_questions` (ADR-033 already omits it; this ADR adds no column); no `user_id` field on `QuizAttempt` / `AttemptQuestion`; no auth, no session, no per-user partitioning, no role check in any function. **PASS.**
- **MC-8 (Reinforcement loop preserved).** Honored — the functions do not foreclose the loop. `start_attempt` composes the Attempt's `attempt_questions` strictly from one Quiz's `quiz_questions` rows (one Section), so no fresh-only-post-first-Quiz path is created; the `attempt_questions.is_correct` column the grading slice will `UPDATE` (on the rows `start_attempt` creates) is the wrong-answer-replay history the composition slice reads via `SELECT ... WHERE is_correct = 0`; this slice records the `response` (`save_attempt_responses`), the grading slice records the `is_correct`, the composition slice reads both; the schema (ADR-033) already supports both loop portions without a non-additive migration. No composition code is exercisable yet; the functions do not foreclose. **PASS.**
- **MC-9 (Quiz generation is user-triggered).** Honored. The Attempt-persistence functions generate nothing — no background job, no auto-trigger; this rule stays clean by construction. **PASS.**
- **MC-10 (Persistence boundary).** Honored, and the rule's enforcement strengthened (more public functions in the persistence package; the take route + template, ADR-038, call only typed public functions). `import sqlite3` and all SQL literals for the new functions stay in `app/persistence/quizzes.py`; the new index DDL is in `connection.py`'s `_SCHEMA_SQL`; the functions are re-exported by `app/persistence/__init__.py`; callers receive `QuizAttempt` / `AttemptQuestion` / `Question` dataclass instances, never a `sqlite3.Connection` or a raw row tuple; no SQL string literal or `sqlite3` import is added outside `app/persistence/`. **PASS** (architecture portion active per ADR-022; this ADR consumes and strengthens it).
- **UI-1 / UI-2 / UI-3 (ui-task-scope).** Not directly implicated — this ADR is a persistence-layer decision, not a UI surface; the UI scoping is ADR-038's (a new `app/static/quiz.css` for the `quiz-take-*` take-page classes; the `.section-quiz-take-link` rule in `lecture.css`). This ADR's diff (the persistence functions + dataclasses + the index line in `connection.py`) is named under §Scope. **N/A** (covered by ADR-038 for the UI portion).
- **UI-4 / UI-5 / UI-6 (rendered-surface verification gate).** Not directly implicated — the rendered-surface gate is ADR-038's / ADR-010's; this ADR's tests are HTTP-protocol / persistence pytest under `tests/` (the Attempt-lifecycle functions), not rendered-surface tests. **N/A** (covered by ADR-038).

Previously-dormant rule activated by this ADR: none. (MC-10's architecture portion is already active per ADR-022; this ADR consumes and strengthens it. MC-1's architecture portion is already active per ADR-036 and stays satisfied — no AI import added.)

## Consequences

**Becomes possible:**

- The Quiz-taking surface (ADR-038) can start an Attempt for a `ready` Quiz, list the Quiz's Questions in order with the learner's current responses, save the learner's submitted code, and flip the Attempt to `submitted` — all via typed public functions, no SQL in the route or template.
- A Quiz Attempt (a `quiz_attempts` row + its `attempt_questions` rows carrying the learner's `response` for each Question) persists across sessions (§7) — `get_attempt` / `list_attempt_questions` re-query it after a new connection.
- The grading slice can build directly on these rows: it `UPDATE`s `attempt_questions.is_correct` / `.explanation` (the rows already exist, created at Attempt start), transitions `quiz_attempts.status` `submitted` → `grading` → `graded`/`grading_failed`, sets `graded_at`, and adds the Grade aggregate (additively) — without re-deciding the per-Question structure.
- The composition slice (post-first Quizzes) can read `attempt_questions.question_id WHERE is_correct = 0` (the wrong-answer-replay history this slice starts recording the `response` for, and the grading slice fills the `is_correct` for) — without a non-additive migration.
- The persistence package's public API is the single import surface (`app/persistence/__init__.py`) for the Attempt lifecycle, consistent with the Note / section-completion / Quiz-domain functions.

**Becomes more expensive:**

- Six new functions + two dataclasses + one `_row_to_*`-style helper-or-two in `app/persistence/quizzes.py`, one index line in `connection.py`, and the `__init__.py` re-export list grows. Mitigation: each mirrors an established pattern (the dataclass-returning convention, the `get_connection()` open/use/close idiom, the FK-column-index pattern); the persistence package was built to grow this way (ADR-022 / ADR-033).
- One more index on `attempt_questions` (a tiny write-time overhead per row inserted). Mitigation: negligible at single-user scale; consistent with the project's "index the FK columns surfaces query by" pattern.
- An idle `start_attempt` (a `GET .../take` that is never submitted) leaves an `in_progress` Attempt (reused on a subsequent reload, but not garbage-collected). Mitigation: harmless in a single-user dev database; a future "discard this Attempt" function / affordance can clean it up if `in_progress` Attempts ever pile up.

**Becomes impossible (under this ADR):**

- A `user_id` on `quiz_attempts` / `attempt_questions` / `QuizAttempt` / `AttemptQuestion`. MC-7 + the no-`user_id` commitment forbid it.
- `submit_attempt` (or any function this slice ships) transitioning an Attempt to `grading`/`graded` or invoking grading. MC-4 + the no-grading-discipline commitment forbid it (the grading slice's functions do that).
- A function this slice ships fabricating an `is_correct` / `explanation` value or a Grade aggregate. MC-5 + the "leave them NULL until grading" commitment forbid it.
- `start_attempt` composing an Attempt from Questions of more than one Section. MC-2 + the "compose strictly from one Quiz's `quiz_questions` rows" commitment forbid it.
- SQL literals or a `sqlite3` import for the Attempt functions outside `app/persistence/`. MC-10 + the "SQL stays here" commitment forbid it.
- A delete path for `quiz_attempts` / `attempt_questions` this slice. The absence of a delete path is the guarantee (§7: an Attempt persists); a future ADR would have to add one explicitly.

**Future surfaces this ADR pre-positions:**

- The grading slice's persistence functions — `mark_attempt_grading(attempt_id)` / `mark_attempt_graded(attempt_id)` / `mark_attempt_grading_failed(attempt_id, error=None)` (mirroring ADR-037's `mark_quiz_*` functions), `save_attempt_grades(attempt_id, per_question: list[...])` (UPDATE `is_correct`/`explanation` on the rows this slice created), and the Grade-aggregate functions (against the deferred `grades` table or columns). The next slice.
- A "list all Attempts for a Quiz / Section" accessor — a future "see all my Attempts" / "retake this Quiz" surface; additive.
- A `delete_attempt` / "discard this Attempt" function — if orphan `in_progress` Attempts ever need cleanup; a future ADR decides it.
- Mid-edit autosave functions / a per-Question save endpoint — if a future task adds mid-edit save (with a JS caller); additive.
- The relational Topic vocabulary (`topics` table + `question_topics` join) — ADR-033/ADR-036 deferred it "to the Weak-Topic-identification slice"; `list_questions_for_quiz` returns `Question`s with `topics` split from the existing `questions.topics` column unchanged; the migration to the relational form is additive.

**Supersedure path if this proves wrong:**

- If creating `attempt_questions` rows at Attempt start proves wrong (e.g. a Quiz with many Questions makes the start-of-take INSERT batch noticeable — unlikely at this scale) → a future ADR (and an ADR-038 supersedure) switches to create-at-submit; bounded cost (the persistence functions + the take template's render path).
- If `start_attempt`'s "reuse the latest `in_progress` Attempt" proves wrong (e.g. the learner wants a fresh Attempt each take-surface-load, or orphan `in_progress` Attempts become a real problem) → a future ADR switches to "always a new Attempt" + adds an Attempt-history surface and/or a `delete_attempt` function; bounded cost.
- If the function set proves too thin (the take surface or a future surface needs a function not shipped here) → a future task adds it incrementally (ADR-033's "may be added incrementally by later tasks" posture); no supersedure needed for an addition.
- If the `idx_attempt_questions_attempt_id` index proves redundant (the PK suffices in practice) → it can be dropped (a `DROP INDEX` — technically non-additive, so a future ADR would note it); negligible cost; or it is simply left as harmless.
- If the `QuizAttempt` / `AttemptQuestion` dataclass shapes prove insufficient (e.g. the grading slice wants `is_correct`/`explanation` on `AttemptQuestion`) → the grading slice's ADR adds a richer accessor (e.g. `list_graded_attempt_questions`) or extends `AttemptQuestion` (adding optional fields is additive); bounded cost.

The supersedure path, in every case, runs through a new ADR (or, for a pure addition, just a later task). This ADR does not edit any prior ADR in place; it adds the Attempt-persistence layer under ADR-022's umbrella and ADR-033's schema, consuming both unchanged, and supplies the functions ADR-038's Quiz-taking surface calls.

---

## Amendment (2026-05-12, during TASK-015 implementation)

`get_latest_attempt_for_quiz(quiz_id) -> QuizAttempt | None` was added to this ADR's function set in-flight, during the implementation of TASK-015.

**Why it was added:** ADR-038 §GET .../take describes the behaviour "if the Attempt is already `submitted` (including via the submit route's PRG redirect), render the surface in the submitted state instead of a takeable form." This ADR's original function set did not provide a way for the route to obtain *the latest Attempt for a Quiz, any status* — `start_attempt(quiz_id)` only ever returns/creates an `in_progress` Attempt, and `get_attempt(attempt_id)` requires the `attempt_id`. So after the submit PRG-redirect a re-`GET` of the take surface would have spawned a fresh blank `in_progress` Attempt instead of showing the submitted state. `get_latest_attempt_for_quiz` is the minimal accessor that closes that gap; it is a read-only single-row `SELECT … WHERE quiz_id = ? ORDER BY created_at DESC, attempt_id DESC LIMIT 1`, with no `user_id` and SQL kept under `app/persistence/` like the rest.

**Process note:** the implementer surfaced this as a gap (an `ADJACENT FINDING:` in the TASK-015 audit, Run 004) — a new public callable that no cited ADR named. Per CLAUDE.md's pushback protocol the implementer should have stopped and surfaced it *before* implementing; `/auto` caught the new public surface, stopped (Run 005), and escalated. The human reviewed and gated the addition; the architect/orchestrator then folded it into this ADR's function set (this note) and into `architecture.md`'s ADR-039 row + Quiz-taking-surface paragraph. This ADR was still uncommitted and auto-accepted-today, so this is an amendment to the ADR's function set, not a supersedure; the supersedure path described above is unchanged.
