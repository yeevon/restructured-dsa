# ADR-022: Persistence layer — SQLite via stdlib `sqlite3`, `app/persistence/` package boundary, and the Note schema

**Status:** `Accepted` (2026-05-10)
**Date:** 2026-05-10
**Task:** TASK-009
**Resolves:** none (no project_issue filed against this question; the persistence-layer question is surfaced inline in the manifest-conformance skill's MC-10 dormancy and in ADR-003's "deferred until Quiz/Notes/Attempts force it" clause; this ADR ends both)
**Supersedes:** none

## Context

TASK-009 ships the minimum viable Note surface (create + read on a single Chapter). Manifest §7 makes "every Note … persists across sessions" a binding invariant; manifest §8 fixes Note as user-authored content bound to a Chapter. The application has no persistence layer today: ADR-003 explicitly deferred persistence "until Quiz/Notes/Attempts force it," and the manifest-conformance skill's MC-10 ("Persistence boundary") has been dormant ("`cannot evaluate (ADR pending)`") for the project's entire eight-task history.

This ADR is the manifest-sanctioned moment for the first persistence decision. The choice has long-tail consequences: the same persistence package will host the Quiz Bank, Quiz Attempts, Grades, and Notification entities once Quiz-bootstrap lands. The schema, the package boundary, and the migration story this ADR commits to set precedent for every later persistence question.

The decision space has materially different alternatives:

- **Store technology:** SQLite via stdlib `sqlite3`; SQLite via an ORM (SQLAlchemy / SQLModel); SQLite via the async driver `aiosqlite`; a flat JSON file under a project data directory.
- **Where the store file lives:** under the repository (`data/notes.db`); under `var/` or `state/`; under an XDG-style user path (`~/.local/share/restructured-cs300/...`); env-overridable.
- **Package boundary mechanics:** a Python package (`app/persistence/`) whose modules are the only code that imports the DB driver and the only code that contains SQL string literals; a single module (`app/persistence.py`); no boundary, scattered access.
- **Schema for Note:** minimal columns vs columns that anticipate future Note features (edit/delete, optional Section reference, soft-delete history).
- **Migration story:** raw `CREATE TABLE IF NOT EXISTS` at first connection; a migration tool (Alembic, yoyo); hand-edited DDL in version control without runtime application.

The manifest constrains the decision through §3 (Notes are a primary-objective pillar — persistence must support readable retrieval at request time), §5 (no remote deployment / no multi-user — bound the simplicity ceiling: no DB server, no connection pool, no migration framework justification yet), §6 (Lecture source is read-only — the persistence store must live outside `content/latex/`), §6 + §7 (single-user — no `user_id` column anywhere), and §7 (every Note persists across sessions — the store must outlive the FastAPI process).

## Decision

### Store technology — SQLite via stdlib `sqlite3`

The persistence store is a single SQLite database file accessed through Python's standard library `sqlite3` module. No third-party DB driver is added to `pyproject.toml`. No ORM is introduced.

Rationale: SQLite is single-writer-fine for a single-user local application (manifest §5 / §6 / §7), survives process restarts, supports the future Quiz/Attempt/QuestionBank tables in the same file without re-deciding the storage layer, and adds zero dependencies. The stdlib `sqlite3` module's API is small and stable; an ORM's value (cross-database portability, model-class ergonomics, change-management) is uncalled-for at this scale. `aiosqlite` (async driver) is rejected: FastAPI happily calls sync code from sync route handlers and there is no concurrency story (single user, single process, manifest §6); the async driver would add ceremony without payoff. A flat JSON file is rejected: indexing, atomic writes, and future query patterns (Quiz replay logic against the Question Bank — manifest §7) are all easier with SQL than with a JSON document the application has to serialize end-to-end on every change.

### Store file location — `data/notes.db` (repo-local), env-overridable via `NOTES_DB_PATH`

The default store file is `data/notes.db` under the repository root (i.e., `<repo>/data/notes.db`). The `data/` directory is created by the persistence layer at first connection if it does not already exist.

The path is overridable via the environment variable `NOTES_DB_PATH` (full filesystem path to the database file). Tests use this to inject a per-test `tmp_path` database without touching the dev database. The default lives at the repo root because the project is single-user, single-machine, no remote deployment (manifest §5); a more elaborate XDG path (`~/.local/share/...`) adds friction for the human operator without solving any real problem.

`data/notes.db` and the `data/` directory are added to `.gitignore`. The store is not version-controlled — Notes are user-generated and per-installation by definition (manifest §8: Notes are user-authored).

The store file lives outside `content/latex/` (MC-6 preserved by construction). Nothing under `content/latex/` is opened for write by the persistence layer.

### Package boundary — `app/persistence/` is the only DB-toucher

A new Python package `app/persistence/` is introduced. Its initial layout:

- `app/persistence/__init__.py` — exposes the public API (a small set of functions: `connect()`, `init_schema()`, plus per-entity modules' public functions).
- `app/persistence/connection.py` — owns the `sqlite3.connect(...)` call, the `sqlite3.Row` row-factory configuration, schema bootstrap (`CREATE TABLE IF NOT EXISTS ...` on first connection), and the path-resolution helper that consults `NOTES_DB_PATH`.
- `app/persistence/notes.py` — owns the SQL string literals and parameter-binding for the Note entity. Exposes `create_note(chapter_id, body) -> Note`, `list_notes_for_chapter(chapter_id) -> list[Note]`, and a small `Note` dataclass (or `TypedDict`) describing a row.

The architectural commitment is:

- **`import sqlite3` may appear only in files under `app/persistence/`.** Routes, templates, parser modules, designation, and discovery never `import sqlite3`.
- **SQL string literals (any string containing the tokens `SELECT`, `INSERT`, `UPDATE`, `DELETE`, `CREATE TABLE`, `BEGIN`, `COMMIT`, `ROLLBACK`) may appear only in files under `app/persistence/`.**
- **Routes and other consumers call only the typed public functions exposed by `app/persistence/`.** They never receive a `sqlite3.Connection` or a raw row tuple — they receive `Note` instances.

This is the architectural shape MC-10 ("Persistence boundary") activates against. The grep target for the manifest-conformance skill becomes "any `import sqlite3` outside `app/persistence/`" and "any SQL keyword in a string literal outside `app/persistence/`." Both should return zero matches.

### Schema for the Note entity — minimal columns; no `user_id`; no `section_id`

The `notes` table:

```sql
CREATE TABLE IF NOT EXISTS notes (
    note_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    chapter_id TEXT    NOT NULL,
    body       TEXT    NOT NULL,
    created_at TEXT    NOT NULL,  -- ISO-8601 UTC timestamp
    updated_at TEXT    NOT NULL   -- ISO-8601 UTC timestamp
);

CREATE INDEX IF NOT EXISTS idx_notes_chapter_id ON notes (chapter_id);
```

Column rationale:

- **`note_id INTEGER PRIMARY KEY AUTOINCREMENT`** — surrogate key. Autoincrement (rather than `ROWID` reuse) prevents ID reuse if a row is later deleted, which matters once `Resolved by ADR-NNN` references to a Note become possible (e.g., in audit trails, in future cross-Chapter views).
- **`chapter_id TEXT NOT NULL`** — the Chapter ID per ADR-002 (kebab-case basename of the source `.tex` file). Stored as TEXT, not as an FK to a `chapters` table — Chapters are a filesystem-derived concept (ADR-001, ADR-007), not a persisted entity. The application validates `chapter_id` against the discovered set at write time; an unknown `chapter_id` is rejected by the route handler before reaching the persistence layer.
- **`body TEXT NOT NULL`** — the user-authored Note text. No length limit at the schema level (SQLite's TEXT is effectively unbounded for this scale); the route handler may impose a sanity limit (e.g., 64 KiB) and return HTTP 400 above it.
- **`created_at` and `updated_at`** — ISO-8601 UTC strings (`"YYYY-MM-DDTHH:MM:SSZ"`). Set by the persistence layer on insert/update, not by the caller. `updated_at` equals `created_at` at row creation; reserved for the follow-up edit task. Stored as TEXT (rather than INTEGER epoch) because human-readable timestamps in the SQLite shell are useful when debugging and the storage cost is negligible.

**Explicitly omitted from the schema:**

- **No `user_id` column.** Manifest §5 / §6 / §7 (single user). MC-7's architecture portion is now active: any future contributor cannot add a `user_id` without superseding this ADR.
- **No `section_id` column.** Manifest §7 says Notes "may optionally reference one Section" — TASK-009 defers the optional Section reference to a follow-up. When that follow-up forces it, a future ADR commits to the column shape (likely `section_id TEXT NULL`) and the migration adds the column with `ALTER TABLE notes ADD COLUMN section_id TEXT`. Adding a nullable TEXT column is a low-risk SQLite migration.
- **No soft-delete column.** Edit/delete behavior is out of scope for TASK-009; the follow-up that adds DELETE will decide between hard delete and soft delete with its own ADR.
- **No tags, search-index, or full-text-search virtual table.** Out of scope.

**`chapter_id` is NOT UNIQUE.** Multiple Notes per Chapter are allowed by the schema. TASK-009's UI surfaces them in `created_at DESC` order ("most recent first"); the architect's read is that the manifest's "A Note is bound to exactly one Chapter" (§7) describes a Note's relationship to a Chapter, not a 1:1 cardinality between Chapters and Notes. Constraining UNIQUE here would force a "one Note per Chapter forever" invariant that the manifest does not require and that the follow-up Notes tasks would have to fight against.

### Migration story — `CREATE TABLE IF NOT EXISTS` at first connection; supersede when a real schema change forces a tool

Schema bootstrap is performed by `app/persistence/connection.py` on first connection: every `CREATE TABLE` and `CREATE INDEX` statement is wrapped in `IF NOT EXISTS` and run idempotently. There is no migration framework (Alembic, yoyo, raw migration scripts in version control).

Trigger condition for revisiting: the *first* schema change that cannot be expressed as an idempotent `IF NOT EXISTS` (e.g., a column rename, a NOT NULL constraint added to an existing column with rows in it, a foreign-key constraint added retroactively) forces a follow-up ADR. `ALTER TABLE ... ADD COLUMN` for a nullable column is *still* expressible idempotently via a `PRAGMA table_info(notes)` check inside `connection.py` — the trigger only fires for non-additive changes.

This is deliberately the simplest viable migration story. A migration framework's value (auditable history, reversible migrations, multi-environment coordination) is uncalled-for at single-user / single-machine / no-remote-deployment scale (manifest §5).

### Future cohabitation — Quiz/Attempt/Bank/Notification entities live in the same SQLite database

This ADR commits to **one shared SQLite database** for all current and future persisted entities, with multiple tables and multiple modules under `app/persistence/`. When Quiz-bootstrap lands, it adds (e.g.) `app/persistence/quizzes.py`, `app/persistence/attempts.py`, `app/persistence/question_bank.py`, `app/persistence/notifications.py` — each owning its own SQL — to the same package, sharing the same `connection.py`. All tables live in `data/notes.db` (the filename is preserved for compatibility with the env-var name `NOTES_DB_PATH`; renaming the file to `data/app.db` is a follow-up choice if the filename stops fitting).

This is a real architectural commitment, not a forecast. Splitting the Quiz data into a separate database would add cross-database transaction complexity (Quiz Attempts referencing Notes-side data, or vice versa, becomes impossible without cross-DB ATTACH gymnastics) for no offsetting benefit at single-user scale. Single shared DB is the right shape.

### `ai-workflows` cohabitation — acknowledged, not yet committed

Manifest §4 names `ai-workflows` as the only AI engine commitment. `ai-workflows` itself likely needs persistence for workflow-state tracking (run IDs, intermediate outputs, completion markers — exactly the kind of state Quiz-bootstrap will rely on for async result delivery per manifest §6). This ADR **acknowledges** that the persistence layer will host `ai-workflows`-state-related tables alongside the application's own entities; it does **not** commit to the schema, the table names, or the integration mechanics.

Concretely: when Quiz-bootstrap forces the `ai-workflows` integration ADR, that ADR may either (a) add tables to this same SQLite database under the `app/persistence/` package, (b) commit to a separate `ai-workflows`-owned store, or (c) consume `ai-workflows`'s own persistence configuration if the framework provides one. This ADR pre-positions option (a) as the default but does not foreclose (b) or (c); the choice belongs to the integration ADR.

### Scope of this ADR

This ADR fixes only:

1. The store technology (SQLite via stdlib `sqlite3`).
2. The store file location and override mechanism (`data/notes.db`, `NOTES_DB_PATH` env var).
3. The package boundary (`app/persistence/` is the only DB-toucher; MC-10 grep target).
4. The Note schema (the columns committed above; no `user_id`; no `section_id`; multi-Note-per-Chapter allowed).
5. The migration story (`CREATE TABLE IF NOT EXISTS`; trigger condition for revisiting).
6. The cohabitation rule (single shared SQLite DB for all future persisted entities).

This ADR does **not** decide:

- The route shape, template surface, or form-handling pattern for the Notes UI — those are owned by ADR-023.
- Edit / delete behavior on Notes — out of scope for TASK-009; future ADR.
- The `section_id` column shape — out of scope for TASK-009; future ADR.
- The Quiz/Attempt/QuestionBank/Notification schemas — owned by Quiz-bootstrap ADRs.
- The `ai-workflows` integration mechanics — owned by the integration ADR when Quiz-bootstrap forces it.
- A connection-pool, async-driver, or transactional-isolation policy — single-user, single-process, no concurrency story.
- Backup, export, or import of the store — out of scope.

## Alternatives considered

**A. SQLite via SQLAlchemy Core (or SQLModel / SQLAlchemy ORM).**
Rejected. SQLAlchemy's value (cross-DB portability, model-class ergonomics, migration tooling via Alembic) is uncalled-for at single-user / single-DB / no-portability-target scale. The cost is real: a new top-level dependency, a model-class layer that route handlers and templates would either consume directly (coupling templates to ORM objects) or shadow into plain dataclasses (defeating the model-class ergonomics). The stdlib `sqlite3` module's API is small enough that hand-written SQL is more transparent, easier to grep for boundary violations against MC-10, and adds zero dependency surface. If a future task surfaces a real reason to switch (e.g., the schema becomes too gnarly to maintain by hand, or a Quiz-bootstrap flow needs declarative relationship traversal), supersede this ADR.

**B. SQLite via `aiosqlite`.**
Rejected. FastAPI runs sync route handlers happily; the project has no concurrency story (single user, single process, manifest §6). `aiosqlite` would add a dependency and async-context-manager ceremony without payoff. The forward-looking argument from ADR-003 (FastAPI's `async def` route style aligns with `ai-workflows`-style async work) does not extend to the persistence layer: AI work is async because of network/long-running compute, not because SQLite is async. SQLite reads and writes are short, local, and CPU-bound; calling them synchronously from an `async def` route handler is the standard FastAPI pattern.

**C. Flat JSON file (`data/notes.json`) keyed by `chapter_id`.**
Rejected. JSON storage works for create + read on a single Chapter, but breaks down at every future shape change: indexing (the Question Bank's per-Section / per-Topic queries need real indexes), atomic writes (concurrent Quiz Attempt grading wants real transactions), and migrations (any schema change requires reading the entire file, transforming it, and writing it back atomically). The cost of "starting with JSON and switching to SQLite later" is paying for the migration twice. Starting with SQLite is the lower-total-cost path even though the minimum-viable Note surface could be served by JSON in isolation.

**D. Defer the persistence layer entirely; serialize Notes to a per-Chapter file under a Notes-source root.**
Rejected. The "one file per Note" / "one file per Chapter's Notes" approach has the same problems as Alternative C plus filesystem-level race conditions and a less obvious schema-change story. Manifest §6 ("Lecture source is read-only") is about Lecture source specifically, not about all filesystem-stored content; the rule does not authorize a parallel Notes-source root. Filesystem storage also fights the package-boundary rule (MC-10): the boundary becomes "files under `data/notes/` are the only Note storage" and route handlers either traverse the filesystem directly (boundary leak) or call a thin module that does (which is just a worse SQLite wrapper).

**E. Separate database file per entity family (`data/notes.db` for Notes, `data/quizzes.db` for Quizzes when they land, etc.).**
Rejected. Cross-database transactions require SQLite's `ATTACH DATABASE` mechanic and add real complexity for the inevitable Quiz Attempt → Note (or other) cross-references. At the project's scale (single user, ~12 Chapters today, projected hundreds of Quiz Attempts and thousands of Questions over the project's lifetime) one shared database file holds everything well within SQLite's comfortable operating range. If the database grows unmanageable (multi-gigabyte; query latency degrades), supersede this ADR and split.

**F. Schema with `chapter_id` UNIQUE (one Note per Chapter; UPDATE rather than INSERT on subsequent saves).**
Rejected. The manifest does not commit to one-Note-per-Chapter cardinality (§7 says "A Note is bound to exactly one Chapter," which is a Note→Chapter relationship statement, not a Chapter→Note cardinality statement). Constraining UNIQUE now would force the next Notes task (multi-Note support) to either supersede this ADR's schema with a non-trivial migration or to live with a one-Note-per-Chapter UX forever. The minimum-viable read path (display the most-recent Note for the Chapter at the top of the form) is independent of the cardinality and works under either schema; choosing the more permissive schema preserves the optionality.

**G. Schema with a `user_id` column defaulted to the literal string `"user"`.**
Rejected. Manifest §5 / §6 / §7 (single user). MC-7's architecture portion explicitly forbids per-user data partitioning at the data layer. A `user_id` column with a single sentinel value is not "future-proofing for multi-user" — it is a violation of MC-7 wearing a fig leaf. If the project ever becomes multi-user (which the manifest forbids), the move is to supersede the manifest first and the schema second; pre-emptively building the column accomplishes nothing while normalizing the multi-user shape.

**H. `created_at` / `updated_at` as INTEGER epoch seconds.**
Considered. INTEGER epoch is more compact and slightly faster to compare. Rejected mildly: ISO-8601 strings are human-readable in the SQLite shell during debugging and the storage difference is negligible at this scale. The choice is reversible (a future ADR can add an integer column or migrate the existing one); committing to ISO-8601 now is the lower-friction default.

**I. Migration via Alembic from day one.**
Rejected. Alembic's value (auditable migration history, reversible migrations, multi-environment coordination) is uncalled-for at single-user / single-machine scale. Setting it up adds a top-level dependency, a `migrations/` directory, and operational ceremony (the dev-startup story now includes "did you run `alembic upgrade head`"). The trigger condition committed above ("the first non-additive schema change") is the right moment to revisit; setting it up pre-emptively is over-engineering.

## My recommendation vs the user's apparent preference

The TASK-009 task file forecasts the architect's choice as "stdlib `sqlite3` + `app/persistence/` package + raw `CREATE TABLE IF NOT EXISTS` at startup; supersede when schema-change forces a migration tool." This ADR aligns with that forecast. The architect's read is that the user has signaled the right shape and this ADR confirms it with the schema and cohabitation details fleshed out.

One area of mild push beyond the task's forecast: the task proposes the schema columns "`note_id`, `chapter_id`, `body`, timestamps" as a *minimum*; this ADR additionally commits to **multi-Note-per-Chapter cardinality** (no UNIQUE on `chapter_id`), which the task does not explicitly address. The architect's read is that the manifest does not constrain this choice and the more permissive schema is the right default — preserving the option for multi-Note UX without requiring a schema migration when that follow-up lands. If the human wants the stricter cardinality (one Note per Chapter, UPDATE-on-save semantics), this is the place to push back at the gate; the route shape in ADR-023 will adapt.

A second area worth surfacing: the task's "Architectural concerns" section asks the architect to **explicitly check `ai-workflows` cohabitation**. This ADR's commitment is "single shared SQLite database for all future persisted entities, including `ai-workflows`-state-related tables under option (a)" but does not commit to the actual `ai-workflows` integration mechanics. The architect's read is that committing to the integration mechanics here is over-reach (no Quiz-bootstrap task exists yet to motivate it), but committing to the *cohabitation default* (one shared DB) is the right level — it lets the future integration ADR focus on AI mechanics rather than re-deciding the storage shape.

I am NOT pushing back on:

- The single-user posture (manifest §5 / §6 / §7) — honored: no `user_id`.
- The read-only Lecture source rule (manifest §6, MC-6) — honored: store lives at `<repo>/data/notes.db`, never under `content/latex/`.
- The "Notes are user-authored, never auto-generated" rule (manifest §8) — honored: this ADR fixes only the storage shape; AI-generation is foreclosed by the schema (no source-marker column) and by the surface ADR (no AI-driven write path).
- The asynchronous-AI absolute (manifest §6) — Notes are not AI work; the absolute does not constrain this ADR.
- The single-source rule for Lectures (manifest §6) — orthogonal: Notes are a separate entity from Lectures.

## Manifest reading

Read as binding for this decision:

- **§3 Primary Objective.** Notes are one of three named consumption pillars; persistence must support readable retrieval at request time across server restarts. The schema and the read path satisfy this.
- **§5 Non-Goals.** "No remote deployment / hosted product" bounds the storage discussion to a local file (not a database server). "No multi-user" bounds the schema (no `user_id`). "No mobile-first" is orthogonal to persistence.
- **§6 Behaviors and Absolutes.** "Single-user" bounds the schema. "Lecture source is read-only" (the application reads `content/latex/` only for read) bounds the store location: it lives at `<repo>/data/`, not under `content/latex/`. The "AI work asynchronous" absolute does not constrain Notes (Notes are not AI work).
- **§7 Invariants.** "Every Note … persists across sessions and is owned by the single user" — directly motivates this ADR. "A Note is bound to exactly one Chapter and may optionally reference one Section within it" — bounds the schema (`chapter_id NOT NULL`; `section_id` deferred to a follow-up).
- **§8 Glossary.** Note ("user-authored content bound to a Chapter, optionally referencing one Section. Editable by the user. Never auto-generated.") — bounds the schema (no source-marker / no auto-generation columns) and the architecture portion of the boundary rule (Notes are written through user-initiated routes, never through background jobs).

No manifest entries flagged as architecture-in-disguise. Manifest §4's `ai-workflows` mention is owned by §4 itself; this ADR acknowledges cohabitation and defers the integration mechanics to the future integration ADR.

## Conformance check

- **MC-1 (No direct LLM/agent SDK use).** This ADR introduces no LLM SDK; the persistence package depends only on stdlib `sqlite3`. Compliance preserved (and dormant for the SDK-name check until the AI-engine ADR lands — unchanged by this ADR).
- **MC-2 (Quizzes scope to exactly one Section).** Orthogonal — no Quiz table introduced. The future Quiz schema must respect MC-2; this ADR pre-positions the package boundary it will live within.
- **MC-3 (Mandatory/Optional designation respects the canonical mapping).** Orthogonal — no designation column. Notes inherit the Chapter's designation by virtue of being bound to a Chapter; the canonical mapping (ADR-004) is consulted at render time, not stored.
- **MC-4 (AI work asynchronous).** Orthogonal — Notes are not AI work.
- **MC-5 (AI failures are surfaced).** Orthogonal — Notes have no AI surface.
- **MC-6 (Lecture source read-only).** Honored. The store file lives at `<repo>/data/notes.db`, not under `content/latex/`. The persistence layer does not open any path under `content/latex/`. Compliance preserved.
- **MC-7 (Single user).** Honored. The schema has no `user_id` column; the connection layer has no auth check, no session management, no per-user partitioning. **Architecture portion now active:** future contributors cannot add a `user_id` without superseding this ADR.
- **MC-8 (Reinforcement loop preserved).** Orthogonal — no Quiz machinery in this ADR.
- **MC-9 (Quiz generation is user-triggered).** Orthogonal.
- **MC-10 (Persistence boundary).** **Activated by this ADR.** The architecture portion is now enforceable: `import sqlite3` and SQL string literals appear only under `app/persistence/`. The manifest-conformance skill's MC-10 entry walks from "`cannot evaluate (ADR pending)`" to "`warn` once the ADR is Accepted; escalate to `blocker` when the persistence package exists in code." Once the implementer creates `app/persistence/`, MC-10 escalates to `blocker` per the skill's own rule.

Previously-dormant rule activated by this ADR: **MC-10 (architecture portion) and MC-7 (architecture portion — "no per-user data partitioning at the data layer," now enforceable because a schema exists).**

## Consequences

**Becomes possible:**

- A persisted Note that survives FastAPI restarts (manifest §7 satisfied for Notes).
- A single SQL-grep target for MC-10 enforcement (`grep -r "import sqlite3" --include="*.py" app/ | grep -v "app/persistence/"` should return zero matches; same for SQL keywords in string literals).
- A package layout that future Quiz/Attempt/QuestionBank/Notification entities slot into without re-deciding the storage layer.
- A fixture pattern for tests: `tmp_path / "test_notes.db"` injected via `monkeypatch.setenv("NOTES_DB_PATH", ...)`, providing per-test isolation without a complex test-DB-rollback story.
- A clean supersedure path: any of these decisions (store technology, file location, schema, migration story) can be revisited independently when concrete evidence forces it.

**Becomes more expensive:**

- Adding a Note column requires editing both `app/persistence/connection.py`'s `CREATE TABLE` block AND adding a `PRAGMA table_info`-guarded `ALTER TABLE` for existing installs. Mitigation: at single-user scale, "existing installs" is one machine; the migration is a one-line addition.
- The SQL is hand-written. Readers of `app/persistence/notes.py` see the SQL directly, not an ORM model. Mitigation: this is a feature, not a cost — the SQL is grep-able for MC-10 and the schema is visible without needing to run an ORM introspector.
- Cross-DB queries are foreclosed by the single-database commitment. Mitigation: cross-DB queries are exactly the thing this commitment avoids the cost of (single shared DB has none of that complexity).
- Adding a new entity (e.g., Quiz) requires touching `connection.py`'s schema bootstrap. Mitigation: schema bootstrap is one function; new tables are appended to it.

**Becomes impossible (under this ADR):**

- A `user_id` column on any persisted entity. Forbidden by MC-7 (architecture portion now active).
- DB driver imports outside `app/persistence/`. Forbidden by MC-10 (architecture portion now active).
- SQL string literals outside `app/persistence/`. Forbidden by MC-10 (architecture portion now active).
- A separate database file per entity family without a superseding ADR. Forbidden by the single-shared-DB commitment.
- An ORM introduced incrementally without a superseding ADR. Forbidden by the stdlib-`sqlite3` commitment.

**Future surfaces this ADR pre-positions:**

- Quiz-bootstrap tables (`quizzes`, `attempts`, `questions`, `question_bank_membership`, `topics`, `notifications`) — added under `app/persistence/` as new modules, sharing `connection.py`. Same DB file. Same migration story (`CREATE TABLE IF NOT EXISTS` until non-additive change).
- `ai-workflows` cohabitation (option a above) — `ai-workflows`-state tables added under `app/persistence/` if the integration ADR chooses this path.
- An optional `section_id TEXT NULL` column on `notes` when the manifest §7 "may optionally reference one Section" follow-up lands. Migration: `ALTER TABLE notes ADD COLUMN section_id TEXT;` guarded by `PRAGMA table_info` check.
- Edit / delete behavior on Notes when those follow-ups land. The schema already carries `note_id` and `updated_at` in anticipation.

**Supersedure path if this proves wrong:**

- If the schema becomes too gnarly to maintain by hand → introduce SQLAlchemy Core (a future ADR; preserves stdlib-`sqlite3` as the underlying driver, adds the model layer on top).
- If the database file grows unmanageable → split entities across multiple files (a future ADR; the single-shared-DB commitment is the thing being superseded).
- If `CREATE TABLE IF NOT EXISTS` proves insufficient (first non-additive change) → introduce Alembic or a hand-written migration runner (a future ADR; the migration-story commitment is the thing being superseded).
- If `aiosqlite` becomes necessary (e.g., a real concurrency story emerges, contradicting manifest §6) — a manifest edit precedes the supersedure ADR.
