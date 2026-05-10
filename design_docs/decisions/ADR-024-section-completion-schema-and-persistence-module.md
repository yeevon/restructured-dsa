# ADR-024: Section completion schema and persistence module — `section_completions` table (presence ≡ complete) under `app/persistence/section_completions.py`

**Status:** `Accepted`
Auto-accepted by /auto on 2026-05-10
**Date:** 2026-05-10
**Task:** TASK-010
**Resolves:** none (no project_issue filed against this question; the schema decision is forced inline by TASK-010, and ADR-022 §Future-cohabitation pre-positioned this as the first concrete validation of the single-shared-DB rule)
**Supersedes:** none

## Context

TASK-010 ships the minimum viable per-Section completion toggle, activating the manifest §7 invariant **"Completion state lives at the Section level. Chapter-level progress is derived from Section state."** ADR-022 (Accepted, 2026-05-10) committed to one shared SQLite database under `data/notes.db`, with each persisted entity owning its own module under `app/persistence/`. ADR-022 §Future-cohabitation explicitly anticipated this case: *"When Quiz-bootstrap lands, it adds (e.g.) `app/persistence/quizzes.py`, `app/persistence/attempts.py` … to the same package, sharing the same `connection.py`."*

This ADR is the **first concrete validation of ADR-022's cohabitation commitment**. Section completion is the first non-Notes entity to enter `app/persistence/`. The schema, the module path, and the `connection.py` integration set precedent for every future entity (Quiz Bank, Quiz Attempts, Grades, Notifications, `ai-workflows` state) that ADR-022 reserved space for.

The decision space has materially different alternatives:

- **Schema shape:** presence-as-complete (one row per completed Section, delete on unmark) vs boolean-state (one row per ever-touched Section, flip a flag on toggle) vs event-log (one row per `mark`/`unmark` action, derive state from the latest event).
- **`chapter_id` storage:** redundant column (`chapter_id TEXT NOT NULL`) vs derive at query time via string-split on the `#` separator.
- **`section_id` validation:** write-time validation against the discovered Section set vs trust the caller vs validate only against the parent Chapter's discovered Sections.
- **Module path and public API surface:** `app/persistence/section_completions.py` mirroring `notes.py` shape vs co-locating completion functions inside `notes.py` (rejected on principle — different entities; ADR-022's per-entity-module rule).
- **Schema bootstrap mechanics:** extend the existing `_SCHEMA_SQL` string in `connection.py` vs introduce a per-module schema-fragment-registration pattern.
- **`completed_at` timestamp:** stored and returned, never displayed in this task vs omit entirely vs add an explicit `marked_by` audit column (rejected — MC-7 forbids any user-partitioning column).

The manifest constrains the decision through §3 (Notes/Lectures/Quizzes consumption pillars — Section completion is an internal-progress primitive that informs all three), §5 (no LMS — no gradebook export semantics; no multi-user — no `user_id`), §6 (Mandatory/Optional honored everywhere — completion state must be queryable per the parent Chapter's designation; Lecture source read-only — completion writes go to `data/notes.db`), §7 ("Completion state lives at the Section level. Chapter-level progress is derived from Section state." — directly motivates this ADR; "every … completion mark persists across sessions" — fixes persistence as a hard requirement), §8 (Section is "the atomic unit for Quizzes and completion state" — completion is a Section property, never a Chapter or Quiz property).

## Decision

### Schema shape — `section_completions(section_id PK, chapter_id, completed_at)` with **presence ≡ complete**

```sql
CREATE TABLE IF NOT EXISTS section_completions (
    section_id   TEXT PRIMARY KEY,
    chapter_id   TEXT NOT NULL,
    completed_at TEXT NOT NULL  -- ISO-8601 UTC timestamp
);

CREATE INDEX IF NOT EXISTS idx_section_completions_chapter_id
    ON section_completions (chapter_id);
```

Column rationale:

- **`section_id TEXT PRIMARY KEY`** — the full Section ID per ADR-002 (e.g., `ch-01-cpp-refresher#section-1-1`). Primary key because each Section has at most one completion record under the presence-as-complete semantics. Stored as TEXT (the natural representation of ADR-002's composite identifier); no surrogate integer key. The `#` separator is part of the value; SQLite treats it as an opaque byte sequence.
- **`chapter_id TEXT NOT NULL`** — redundant with the prefix of `section_id` but stored explicitly. Rationale: the per-Chapter query (`list_complete_sections_for_chapter(chapter_id)`) is the dominant read pattern (every Lecture-page GET runs it once); an indexed `chapter_id` column makes the lookup a B-tree seek rather than a full-table scan with a `LIKE '{chapter_id}#%'` predicate. At single-user scale the performance difference is imperceptible today, but the redundant column also makes the schema self-documenting and lets future queries (e.g., "complete count per Chapter," "Mandatory-only complete count") use clean SQL without parsing the composite ID.
- **`completed_at TEXT NOT NULL`** — ISO-8601 UTC timestamp string, written by the persistence layer at mark-complete time (not by the caller). Same format as `notes.created_at` (ADR-022). Not displayed in UI in this task; stored for future audit / sort / "last completed Section" queries. Removing it later requires only a column drop; including it now costs nothing.

**Presence ≡ complete semantics:** a Section is complete iff a row exists for its `section_id`. `mark_section_complete()` inserts a row (or no-ops if one already exists). `unmark_section_complete()` deletes the row. There is no boolean column; there is no history. The schema is the simplest viable shape that satisfies the toggle behavior, the persistence-across-restart requirement, and the per-Chapter query pattern.

**Explicitly omitted from the schema:**

- **No `user_id` column.** Manifest §5 / §6 / §7 (single user). MC-7's architecture portion (active per ADR-022) is honored.
- **No `marked_by` column.** Same rationale; would be a user-partitioning column with one sentinel value.
- **No `is_complete` boolean.** The presence-as-complete shape makes the column redundant: a row's existence is the boolean. Adding it would force two-step toggle logic (UPDATE rather than DELETE on unmark) and would require a separate "row exists but `is_complete=0`" semantics that has no consumer.
- **No event log / history table.** Manifest §5 forbids LMS-style audit semantics; no current consumer of completion history exists. If a future task surfaces a real reason (e.g., "show me Sections I marked complete then later unmarked"), a separate `section_completion_events` table can be added in a superseding ADR; the cost of starting with presence-as-complete and adding an event log later is not paying double — the event log is purely additive.
- **No FK constraint on `section_id` to a `sections` table.** Sections are filesystem-derived (ADR-001, ADR-002), not persisted entities. The schema cannot foreign-key on something that does not have a rows-in-a-table existence. Write-time validation (below) supplies the missing referential check.

### `section_id` validation — write-time against the discovered Section set

`mark_section_complete()` and `unmark_section_complete()` accept a `section_id` and a `chapter_id`. The route handler is responsible for:

1. Validating `chapter_id` against the discovered Chapter set (already established by ADR-023's Notes route — `tex_path.exists()` check).
2. Decomposing the route's path parameters into a full Section ID of the form `{chapter_id}#section-{n-m}`.
3. Validating the resulting Section ID against the parent Chapter's discovered Sections (`extract_sections(chapter_id, latex_text)` already returns the canonical list with `id` and `fragment` fields).

The persistence layer itself does not consult the filesystem. The persistence functions accept the already-validated arguments and persist them. This preserves ADR-022's package-boundary rule: `app/persistence/` does not know about LaTeX, parser output, or Chapter discovery — it only knows about SQL.

Write-time validation rejects orphan rows from typos, stale URLs, or future content-reorganization events. An unknown Section ID returns HTTP 404 at the route layer, never reaching the persistence layer. This follows ADR-023's precedent ("the route handler validates `chapter_id` from form input rather than from a typed FastAPI path parameter").

### Module path and public API — `app/persistence/section_completions.py`

A new module `app/persistence/section_completions.py` joins the persistence package alongside `notes.py` and `connection.py`. The module exposes the following public API, re-exported by `app/persistence/__init__.py`:

```python
def mark_section_complete(section_id: str, chapter_id: str) -> SectionCompletion: ...
def unmark_section_complete(section_id: str) -> None: ...
def is_section_complete(section_id: str) -> bool: ...
def list_complete_section_ids_for_chapter(chapter_id: str) -> list[str]: ...
```

Where `SectionCompletion` is a dataclass mirroring the `notes.Note` shape:

```python
@dataclass
class SectionCompletion:
    section_id: str
    chapter_id: str
    completed_at: str
```

API rationale:

- **`mark_section_complete` returns the dataclass** so callers (and tests) can assert on the returned `completed_at` without a follow-up read.
- **`unmark_section_complete` returns `None`** because the caller has no use for the (now-deleted) row; idempotent — unmarking an already-unmarked Section is a no-op (no error).
- **`is_section_complete` returns `bool`** for the per-Section template check (the template needs a fast yes/no per Section heading). The Lecture page calls `list_complete_section_ids_for_chapter` once at the top of `render_chapter` and the template checks against the returned set; individual `is_section_complete` calls per Section would be N+1 queries.
- **`list_complete_section_ids_for_chapter` returns `list[str]`** (a list of Section IDs, not full `SectionCompletion` objects) because the template only needs the set of completed IDs, not their timestamps. Templates do not consume `completed_at` in this task.

`mark_section_complete` is implemented as `INSERT OR IGNORE` so calling it on an already-complete Section is a no-op rather than an error. This matches the user-visible semantics (clicking "mark complete" twice should not error) and means the route handler does not need to read-before-write.

**Module shape mirrors `notes.py` precedent:**

- SQL string literals live exclusively inside `section_completions.py`. Route handlers and templates never import `sqlite3` and never see raw rows (MC-10, active per ADR-022).
- A small `_utc_now_iso()` helper (or shared one — see "Future minor refactor" below) generates the timestamp.
- All connections are opened, used, and closed within a `try ... finally` block per `notes.py`'s pattern; no long-lived connection state.

### Schema bootstrap — extend `_SCHEMA_SQL` in `connection.py`

The new table's DDL is appended to the existing `_SCHEMA_SQL` string in `app/persistence/connection.py`. Concretely:

```python
_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS notes (
    note_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    chapter_id TEXT    NOT NULL,
    body       TEXT    NOT NULL,
    created_at TEXT    NOT NULL,
    updated_at TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_notes_chapter_id ON notes (chapter_id);

CREATE TABLE IF NOT EXISTS section_completions (
    section_id   TEXT PRIMARY KEY,
    chapter_id   TEXT NOT NULL,
    completed_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_section_completions_chapter_id
    ON section_completions (chapter_id);
"""
```

ADR-022's "trigger condition for revisiting" is **not** fired by this change — adding a new table whose DDL is fully expressible as `CREATE TABLE IF NOT EXISTS` is precisely the additive change ADR-022 anticipated. `init_schema()` continues to be called once at app startup; the second table is created idempotently on the first connection.

**A small architectural note for ADR-022's cohabitation validation:** the centralized `_SCHEMA_SQL` string in `connection.py` is the pattern ADR-022 chose. With two tables it remains tractable. The architect's read is that the pattern is **validated** by this task: nothing about adding a second entity's DDL to `_SCHEMA_SQL` is friction. If at three or four tables (Quiz-bootstrap will likely add several) the centralized string becomes unwieldy, a future ADR can introduce a per-module schema-fragment-registration pattern (each entity module exposes a `SCHEMA_SQL` constant that `connection.py` concatenates). This ADR does **not** preemptively introduce that pattern — over-engineering for an unobserved future cost.

### Module-level integration with `__init__.py`

`app/persistence/__init__.py` re-exports the new public functions:

```python
from app.persistence.connection import init_schema
from app.persistence.notes import Note, create_note, list_notes_for_chapter
from app.persistence.section_completions import (
    SectionCompletion,
    mark_section_complete,
    unmark_section_complete,
    is_section_complete,
    list_complete_section_ids_for_chapter,
)

__all__ = [
    "init_schema",
    "Note",
    "create_note",
    "list_notes_for_chapter",
    "SectionCompletion",
    "mark_section_complete",
    "unmark_section_complete",
    "is_section_complete",
    "list_complete_section_ids_for_chapter",
]
```

Route handlers in `app/main.py` import only from `app.persistence` (no deep imports into `app.persistence.section_completions`); this preserves the boundary as a single import surface and makes MC-10's grep target unchanged.

### Future minor refactor (NOT done in this task)

`notes.py` has a private `_utc_now_iso()` helper. `section_completions.py` will need the same function. The architect's read is that **duplicating the helper for this task** is the right call — two implementations of a 2-line function is not a real DRY violation, and lifting it to a shared `app/persistence/_clock.py` (or similar) is a refactor that adds a new module solely to share two lines. If Quiz-bootstrap adds three more entity modules that each need the helper, **that** is the right moment to factor it out. ADR-022's cohabitation rule does not require helper-sharing infrastructure; this ADR consciously defers.

If the implementer prefers to share the helper now (one-line `from app.persistence.notes import _utc_now_iso` import in `section_completions.py`), that is also acceptable — the helper is module-private by Python convention but cross-module imports of `_`-prefixed names within a single package are not a real boundary violation. The architect mildly prefers duplication for clarity (each entity module is self-contained); the implementer may choose either.

### Cohabitation validation — ADR-022's pattern holds

This ADR is the empirical test TASK-010 §Architectural-concerns asked the architect to run. The architect's read after designing the schema, module, and `__init__.py` extension:

- **The package-boundary rule holds without friction.** Adding `section_completions.py` alongside `notes.py` requires no change to ADR-022's MC-10 grep target. The boundary is "import `sqlite3` and SQL string literals only under `app/persistence/`" — that statement is unchanged by adding another module under that same root.
- **The centralized `_SCHEMA_SQL` in `connection.py` is tractable at two tables.** No supersedure of ADR-022 is forced. (See above note for the n-tables tipping point.)
- **The single-shared-DB commitment is honored without ceremony.** Both tables live in `data/notes.db`; the file is unchanged in location or naming; the `NOTES_DB_PATH` env-var override continues to work uniformly for both.
- **The per-test fixture pattern (`monkeypatch.setenv("NOTES_DB_PATH", str(tmp_path / "test.db"))`) provides per-test isolation for both tables.** Tests do not need a per-table override or a more elaborate test-DB-rollback mechanism. ADR-022's fixture pattern works for the multi-entity case by construction.

The architect explicitly records: **ADR-022's cohabitation commitment is validated by this task; no amendment is warranted.** If Quiz-bootstrap (the next forecasted task) surfaces friction with the centralized `_SCHEMA_SQL` or the helper-sharing question becomes acute, that ADR will revisit; this one does not.

### Scope of this ADR

This ADR fixes only:

1. The `section_completions` table schema and the presence-as-complete semantics.
2. The module path (`app/persistence/section_completions.py`) and public API surface.
3. The schema-bootstrap mechanics (extend `_SCHEMA_SQL` in `connection.py`; no per-module fragment registration).
4. The validation responsibility split (route handler validates; persistence layer trusts).
5. The `__init__.py` re-export shape (single import surface for `app.persistence` consumers).
6. The cohabitation-validation finding (ADR-022 holds; no supersedure forced).

This ADR does **not** decide:

- The route shape, template surface, or form-handling pattern for the completion UI — owned by ADR-025.
- Chapter-level derived progress display — out of TASK-010 scope; future ADR + task.
- Mandatory-only progress views — out of TASK-010 scope; the schema does not foreclose them (Mandatory designation is derivable from `chapter_id` via `chapter_designation()`).
- Completion history / audit semantics — out of scope; if needed, supersede with an event-log table.
- Quiz integration — manifest §7 separates the reinforcement loop from completion state; no coupling introduced.
- `ai-workflows` cohabitation mechanics — owned by the future integration ADR.

## Alternatives considered

**A. Schema: boolean-state column (`section_id PK, is_complete BOOLEAN, completed_at`) — one row per ever-touched Section; toggle flips `is_complete`.**

Rejected. The boolean-state schema persists a "this Section was touched but is no longer complete" state that has no consumer. Under presence-as-complete, an unmarked Section is *exactly* the same as a never-marked Section — there is no semantic difference the application surfaces. Carrying a boolean adds a column with no consumer and forces every read to filter on `is_complete = 1` (or remember to). The `INSERT OR IGNORE` + `DELETE` pattern under presence-as-complete is simpler and produces a smaller database. If a future task surfaces a real reason to distinguish "never marked" from "marked then unmarked" (e.g., a "Sections you've engaged with" view), that is the moment to add an event log; the boolean shape is the awkward middle ground that neither saves history nor stays minimal.

**B. Schema: event-log table (`event_id PK, section_id, action, at`) — append-only; complete = latest event is `mark`.**

Rejected. Manifest §5 forbids LMS-style audit semantics, and no current consumer of completion-action history exists. The event-log shape is the right primitive *if* the application later needs "show me a timeline of Sections I marked/unmarked." Until that consumer exists, the schema carries every action as a row even though only the latest one is queried — the application stores N rows per Section to answer a question that needs at most one bit of state. The `ORDER BY at DESC LIMIT 1` per Section becomes the dominant read pattern, with all the indexing costs that implies. **Reversibility:** if the event log is ever needed, a superseding ADR can add a `section_completion_events` table *alongside* `section_completions` (the current state stays where it is, and the event log captures new actions going forward); the cost of starting with presence-as-complete and adding an event log later is not paying double — only the historical events before the migration are missing, which is acceptable for a single-user personal tool.

**C. Schema: omit `chapter_id` — derive at query time via `LIKE '{chapter_id}#%'`.**

Considered. The `chapter_id` is fully recoverable from the prefix of `section_id` (everything before the `#`). Storing it redundantly is a denormalization. **Rejected mildly:** the per-Chapter query is the dominant read pattern (every Lecture-page GET runs `list_complete_section_ids_for_chapter`), and SQLite's `LIKE` with a non-anchored pattern (`'ch-01-cpp-refresher#%'`) can use an index if the index is on `section_id` and the pattern is a prefix, but the query plan is more fragile than an indexed equality lookup on a dedicated column. At single-user scale the difference is imperceptible today, but the indexed `chapter_id` lookup is the more legible query and the schema self-documents which column is the "Chapter handle." The storage cost is negligible (single-user, ~12 Chapters × ~5 Sections each = ~60 rows even when every Section is complete). Future queries ("complete count per Chapter," "Mandatory-only completion ratio") become clean SQL without a `SUBSTR(section_id, 1, INSTR(section_id, '#') - 1)` expression.

**D. Schema: composite primary key (`(chapter_id, section_id)`) instead of `section_id` alone.**

Rejected. `section_id` is already globally unique per ADR-002 (the Chapter prefix is part of the value). Adding `chapter_id` to the PK is redundant and forces every insert/update/delete to specify both. The dedicated `chapter_id` column (above) gives the per-Chapter query path without compromising the PK shape.

**E. Module: co-locate completion functions inside `notes.py`.**

Rejected. ADR-022's package-boundary rule is per-entity-module: *"`app/persistence/quizzes.py`, `app/persistence/attempts.py`, `app/persistence/question_bank.py`, `app/persistence/notifications.py` — each owning its own SQL"*. Notes and Section completions are different entities (different manifest §8 glossary entries; different lifecycle; different query patterns). Co-locating them would violate the rule ADR-022 set as the project's persistence-cohabitation pattern. Even though the modules will be small, the boundary-by-entity rule is the load-bearing convention; bending it for the first non-Notes entity would normalize the wrong shape.

**F. Module: per-module schema-fragment-registration pattern.**

Considered. Each entity module exposes a `SCHEMA_SQL` constant; `connection.py` imports each module's constant and concatenates them at bootstrap. **Rejected as premature** at two tables. The centralized `_SCHEMA_SQL` string in `connection.py` is one Python string of ~10 lines after this change. The registration pattern adds module-import-order considerations, a new convention for downstream modules to follow, and a place where forgetting to register a new module produces a silent test-failure. If `_SCHEMA_SQL` becomes unwieldy at four or five tables, **that** is the right moment to refactor. (See "Future minor refactor" above; ADR-022's centralized pattern is validated at two tables.)

**G. Validation: trust the caller — persistence layer accepts any `section_id` and `chapter_id` without validation.**

Considered. The persistence layer is by definition not the right boundary for "is this Section ID known to the LaTeX corpus" — that's a parser/discovery concern. **Decision:** the persistence layer trusts the caller (rejecting nothing); the route handler is responsible for validation against the discovered Section set. The ADR records this split explicitly so future entities can follow the same convention.

**H. Validation: validate only `chapter_id` exists; trust `section_id` (no per-Section parse).**

Rejected. A typo'd `section-1-99` Section ID for a Chapter that only has 1-1 through 1-7 would silently persist an orphan completion row. ADR-023's precedent ("validate `chapter_id` against the discovered set") at minimum requires the same level here. Section-level validation also rejects stale URLs from old browser tabs or external links to renumbered Sections; the cost is one additional `extract_sections()` call (which the route handler is already making for the Lecture render) — effectively free.

**I. Schema: omit `completed_at`.**

Rejected. The column is one extra TEXT field per row at ~30 bytes; storage cost is negligible. The benefit is that future audit / "last completed Section" / "Sections completed this week" queries become possible without a schema migration. The UI does not display the timestamp in this task; that does not justify omitting it. Following the `notes.created_at` precedent (ADR-022) is the consistent choice.

**J. Schema: `marked_at` and `unmarked_at` to track both state transitions.**

Rejected. Under presence-as-complete, "unmarked" means "row does not exist," so an `unmarked_at` column is meaningless (the row that would carry it has been deleted). Tracking both transitions requires the event-log shape (Alternative B); both are rejected for the same reason — no consumer.

**K. Toggle semantics: append-only event log even though only the latest event is queried (Alternative B's schema with the read pattern of presence-as-complete).**

Same as Alternative B; rejected for the same reasons. Storing history that no consumer reads is over-engineering.

**L. Validation: enforce a foreign-key constraint via `FOREIGN KEY (chapter_id) REFERENCES chapters(chapter_id)`.**

Rejected. There is no `chapters` table — Chapters are filesystem-derived (ADR-001, ADR-002, ADR-007), not persisted entities. A FK to a non-existent table is impossible. The route-handler-level discovery check (ADR-023 precedent, extended here) is the equivalent referential check.

## My recommendation vs the user's apparent preference

The TASK-010 task file forecasts the architect's choice as "option (1) (one row per completed Section; unmarking deletes row; presence ≡ complete) for simplicity unless audit-history is a real requirement (manifest §5 forbids LMS features; audit history of completion has no current consumer)." This ADR **aligns with that forecast**. The TASK-010 task additionally forecasts `app/persistence/section_completions.py` with the function set `mark_section_complete`, `unmark_section_complete`, `is_section_complete`, `list_complete_sections_for_chapter` — this ADR commits to those names with a minor rename: `list_complete_sections_for_chapter` → `list_complete_section_ids_for_chapter` to be explicit that it returns IDs, not `SectionCompletion` objects.

One area of mild push beyond the task's forecast: the task asks "**whether `chapter_id` is a separate column or derivable from `section_id`**" without prescribing. This ADR commits to **separate column** with rationale (Alternative C). The architect's read is that the manifest is silent here and the more legible schema (with the dedicated `chapter_id` column) is the right default; if the human wants the leaner schema (`section_id` only, derive `chapter_id` at read time), this is the place to push back at the gate.

A second area: the task forecasts "**whether the `section_id` is validated against the discovered Section set on write. Architect picks; precedent (ADR-023 §Validation) suggests yes — write-time validation prevents orphan rows from typos or stale URLs.**" This ADR commits to **yes, validated at the route handler** (not at the persistence layer), and the persistence layer trusts the caller. This is the clean boundary split — discovery is not a persistence concern. ADR-023's "validate at the route handler" precedent is honored.

A third area where this ADR pushes beyond the forecast: the **`mark_section_complete` returns the `SectionCompletion` dataclass**, not `None`. The task does not prescribe. The architect's read is that returning the freshly-persisted object is the more useful API (callers and tests can assert on the returned `completed_at` without an extra read) and matches the `create_note(chapter_id, body) -> Note` precedent in ADR-022.

I am NOT pushing back on:

- The single-user posture (manifest §5 / §6 / §7) — honored: no `user_id`, no `marked_by`.
- The read-only Lecture source rule (manifest §6, MC-6) — honored: writes go to `data/notes.db`.
- The persistence-boundary rule (MC-10, active per ADR-022) — honored: SQL lives only under `app/persistence/`.
- The Section ID scheme (ADR-002) — honored: `section_id` stores the full composite identifier; no re-derivation.
- The single-shared-DB cohabitation commitment (ADR-022) — honored: new table joins `data/notes.db`; no new file.
- The Mandatory/Optional honored-everywhere absolute (manifest §6, MC-3) — preserved: the schema does not store designation, but `chapter_id` is recoverable per row, and `chapter_designation()` is callable from the route layer or template layer for any future filtered view. The schema does not foreclose Mandatory-only progress.

## Manifest reading

Read as binding for this decision:

- **§3 Primary Objective.** Section completion is a consumption-tracking primitive that supports retention by giving the learner a visible "I have absorbed this Section" affordance. The schema and read path satisfy this.
- **§5 Non-Goals.** "No LMS / no gradebook export" bounds the schema scope (no audit log, no per-action history, no completion-export route). "No multi-user" bounds the schema (no `user_id`, no `marked_by`). "No remote deployment" preserves single-machine simplicity (one shared SQLite file).
- **§6 Behaviors and Absolutes.** "Single-user" honored. "Lecture source read-only" honored (writes go to `data/notes.db`). "Mandatory and Optional honored everywhere" — the schema does not foreclose Mandatory-only completion queries; `chapter_id` is stored and `chapter_designation(chapter_id)` is callable. "AI work asynchronous" orthogonal (completion is not AI work).
- **§7 Invariants.** **"Completion state lives at the Section level."** — directly motivates this ADR. The schema's PK is `section_id`; there is no Chapter-level completion entity. **"Chapter-level progress is derived from Section state."** — preserved: any future Chapter-level progress view consumes `list_complete_section_ids_for_chapter(chapter_id)` and computes its derivation; the schema does not store derived state. "Every … completion mark persists across sessions and is owned by the single user." — honored: rows live in SQLite outside the FastAPI process; no `user_id` because of single-user.
- **§8 Glossary.** Section is "the atomic unit for Quizzes and **completion state**." — the schema's PK is `section_id`. Chapter is the parent unit and inherits its Mandatory/Optional designation — the schema's redundant `chapter_id` column enables that derivation. Note (orthogonal) — Notes and completions are separate entities under ADR-022's per-entity-module rule.

No manifest entries flagged as architecture-in-disguise. Manifest §4's `ai-workflows` mention is consumed by ADR-022's cohabitation acknowledgment; this ADR does not commit to integration mechanics.

## Conformance check

- **MC-1 (No direct LLM/agent SDK use).** Orthogonal — this ADR introduces no LLM dependency. Compliance preserved.
- **MC-2 (Quizzes scope to exactly one Section).** Orthogonal — no Quiz entity introduced. The Section ID precedent the schema honors is the same one MC-2 will require Quiz tables to reference.
- **MC-3 (Mandatory/Optional designation respects the canonical mapping).** Preserved by construction. The schema stores `chapter_id` but not designation; `chapter_designation(chapter_id)` (ADR-004) is consulted at read time. No hardcoded chapter-number rules; no per-Section designation override. Future Mandatory-only progress views consume the existing canonical mapping unchanged.
- **MC-4 (AI work asynchronous).** Orthogonal — completion is not AI work.
- **MC-5 (AI failures surfaced).** Orthogonal — no AI in this surface.
- **MC-6 (Lecture source read-only).** Honored. The persistence layer writes to `data/notes.db` only. No file under `content/latex/` is opened for write. Compliance preserved.
- **MC-7 (Single user).** Honored. The schema has no `user_id`, no `marked_by`, no per-user partitioning. Architecture portion (active per ADR-022) is preserved by this ADR: future contributors cannot add a `user_id` to `section_completions` without superseding both ADR-022 and this ADR.
- **MC-8 (Reinforcement loop preserved).** Orthogonal — no Quiz machinery. Manifest §7 explicitly separates completion from the reinforcement loop; this ADR honors that separation (no coupling between `section_completions` and any future Quiz table).
- **MC-9 (Quiz generation user-triggered).** Orthogonal.
- **MC-10 (Persistence boundary).** Honored. SQL string literals for `section_completions` live exclusively in `app/persistence/section_completions.py`. The new module joins the existing boundary; no new `import sqlite3` outside `app/persistence/`; no SQL string literals outside `app/persistence/`. The grep target ADR-022 committed to is unchanged. Compliance preserved (and reinforced — this ADR is the second cohabitating module under MC-10's active boundary).

Previously-dormant rule activated by this ADR: none new. (MC-7 architecture portion and MC-10 architecture portion are already active per ADR-022; this ADR consumes both.)

## Consequences

**Becomes possible:**

- A learner can mark and unmark Sections as complete; state persists across server restarts (manifest §7 satisfied for completion state).
- Every Lecture-page render can show which of the Chapter's Sections are complete via a single indexed query (`list_complete_section_ids_for_chapter`).
- Future Chapter-level progress derivation (manifest §7) consumes this primitive without re-deciding the schema.
- Future Mandatory-only progress filtering (manifest §6) consumes `chapter_id` + `chapter_designation()` without re-deciding the schema.
- ADR-022's cohabitation pattern is validated in code — the next entity (Quiz-bootstrap) inherits a proven shape.
- A clean test-fixture pattern: tests inject `NOTES_DB_PATH` (per ADR-022), both `notes` and `section_completions` are created in the test DB on first connection, and per-test isolation continues to work.

**Becomes more expensive:**

- `connection.py`'s `_SCHEMA_SQL` is now ~17 lines instead of ~10. Mitigation: still trivially readable; if Quiz-bootstrap pushes it past ~50 lines, that is the moment to revisit (per-module fragment-registration; a future ADR).
- Adding a Section completion column requires editing `_SCHEMA_SQL` AND adding a `PRAGMA table_info`-guarded `ALTER TABLE` for existing installs (per ADR-022's migration story). Mitigation: same as ADR-022 — at single-user scale, "existing installs" is one machine.
- `app/persistence/__init__.py` now exports 9 names instead of 4. Mitigation: still well below any reasonable API-surface threshold; the alternative (deep imports) would compromise the single-import-surface convention.

**Becomes impossible (under this ADR):**

- A `user_id` column on `section_completions`. Forbidden by MC-7.
- A Section completion row whose `section_id` is not the full composite ID per ADR-002. The PK shape forces it.
- Persisting completion history (mark/unmark events as rows). The presence-as-complete schema does not record it. Unmarking deletes the row.
- Coupling completion to a Quiz entity at the schema level. The schema has no FK or column referencing any Quiz concept.

**Future surfaces this ADR pre-positions:**

- Chapter-level derived progress (e.g., "5 of 7 Sections complete in Chapter 3") — consumes `list_complete_section_ids_for_chapter` and the Chapter's discovered Section list from `extract_sections`. No schema change.
- Mandatory-only progress view — consumes `chapter_designation(chapter_id)` per Chapter; filters Chapters before counting. No schema change.
- "Last completed Section" / "Sections completed this week" queries — consume `completed_at`. No schema change.
- An event log for completion history (if a future task surfaces a real consumer) — supersede with a `section_completion_events` table alongside `section_completions`. The current table stays as the canonical state.
- Quiz-bootstrap reading completion state for Quiz suggestions ("re-quiz an incomplete Section first") — consumes the existing read API. No coupling at the schema level (Quiz tables do not FK to completion).

**Supersedure path if this proves wrong:**

- If presence-as-complete proves insufficient (a real consumer of completion history emerges) → introduce a `section_completion_events` table in a new ADR; presence-as-complete stays as the canonical current state, the event log captures new actions.
- If the `chapter_id` redundant column proves unjustified (e.g., it becomes inconsistent with the prefix of `section_id` due to a bug) → introduce a CHECK constraint or remove the column in a superseding ADR. The migration is trivial.
- If `_SCHEMA_SQL` centralization becomes unwieldy at N tables → introduce per-module schema-fragment registration in a superseding ADR. ADR-022's migration-story trigger condition does **not** fire for this kind of refactor (it's a pure code reorganization; the DDL outputs are unchanged).
- If `INSERT OR IGNORE` semantics confuse a future implementer (e.g., they expect an error on double-mark) → switch to explicit read-before-write in a superseding ADR; both shapes produce the same user-visible behavior.
