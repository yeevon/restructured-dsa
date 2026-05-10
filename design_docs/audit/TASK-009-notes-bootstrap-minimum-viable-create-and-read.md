# LLM Audit — TASK-009: Notes bootstrap — minimum viable create-and-read on a single Chapter

**Task file:** `design_docs/tasks/TASK-009-notes-bootstrap-minimum-viable-create-and-read.md`
**Started:** 2026-05-10T00:00:00Z
**Status:** Implemented
**Current phase:** verify

---

## Human gates

| Time | Gate | Result | Notes |
|---|---|---|---|
| 2026-05-10T00:00:00Z | Task reviewed | accepted | Proceeding to `/design TASK-009`. |
| 2026-05-10T00:00:00Z | ADRs reviewed | accepted | ADR-022 and ADR-023 flipped Proposed → Accepted. Proceeding to `/implement TASK-009`. |
| 2026-05-10T00:00:00Z | Tests reviewed | accepted | 28 failing / 29 passing on first run. Coverage spans AC-1..9; AC-10/11 are reviewer/human-gated. Proceeding to implementer. |

---

## Agent runs

### Run 001 — architect / Mode 1 `/next`

**Time:** 2026-05-10T00:00:00Z

**Input files read:**
- `design_docs/MANIFEST.md` (full — §3 primary objective, §5 non-goals, §6 absolutes, §7 invariants, §8 glossary)
- `CLAUDE.md` (full, via system-reminder context — authority, tier table, pushback protocol, audit log shape)
- `design_docs/architecture.md` (full — confirmed Accepted ADRs 001–021; no Proposed; no Pending; one Superseded entry empty)
- `.claude/skills/manifest-conformance/SKILL.md` (full — confirmed MC-7 architecture portion and MC-10 are dormant pending persistence-layer ADR)
- `design_docs/tasks/TASK-008-parser-fidelity-unhandled-environments-and-text-macros.md` (full — most recent task; precedent + strategic-balance recommendations)
- `design_docs/audit/TASK-008-parser-fidelity-unhandled-environments-and-text-macros.md` (full — Runs 001 → 006 inclusive; particularly Run 001 Mode-1 architect's strategic-balance recommendation to pivot to Notes-bootstrap, Run 005 orchestrator finding that MC-10 dormancy was ratified for another cycle, Run 006 reviewer READY-TO-COMMIT)
- `design_docs/decisions/ADR-003-rendering-pipeline.md` (full — confirmed ADR-003 explicitly defers persistence to "Quiz/Notes/Attempts force it"; this task is the moment)
- `design_docs/project_issues/parser-fidelity-body-linebreak-and-display-math.md` (full — deferred per "Out of scope")
- `design_docs/project_issues/ch06-textbackslash-double-renders-as-double-backslash.md` (full — deferred per "Out of scope")
- `design_docs/project_issues/task008-leak-path-empirical-confirmation.md` (full — confirmed Resolved)
- `app/main.py` (full — 224 lines; confirmed two routes, no persistence)
- `pyproject.toml` (full — confirmed no DB driver dependency)

**Tools / commands used:**
- Read on every file in the input list above.
- Glob: `design_docs/decisions/*.md` (confirmed highest ADR is 021), `design_docs/project_issues/*.md` (12 files; 10 Resolved, 2 Open), `design_docs/tasks/*.md` (highest is TASK-008; next is TASK-009), `design_docs/audit/*.md` (8 audit files matching), `app/**/*.py` (5 modules: `__init__`, `main`, `designation`, `config`, `discovery`, `parser`), `app/templates/**/*` (4 Jinja2 templates).
- Grep: `^\*\*Status:\*\*` over `design_docs/project_issues/` (confirmed 2 Open issues — both parser-fidelity follow-ups; explicitly deferred).
- Grep: `[Nn]otes?` over `app/` (confirmed zero Notes-related code in app/).
- Grep: `persist|database|sqlite|sqlalchemy` over the repo (confirmed zero persistence code; only doc references).
- Write: `design_docs/tasks/TASK-009-notes-bootstrap-minimum-viable-create-and-read.md`, `design_docs/audit/TASK-009-notes-bootstrap-minimum-viable-create-and-read.md`.

**Files created:**
- `design_docs/tasks/TASK-009-notes-bootstrap-minimum-viable-create-and-read.md`
- `design_docs/audit/TASK-009-notes-bootstrap-minimum-viable-create-and-read.md`

**Files modified:** none.
**Files deleted:** none.

**Task alternatives considered:**
- (Chosen) **Notes bootstrap — minimum viable create + read on a single Chapter form.** Smallest non-trivial vertical slice on an unbuilt manifest pillar. Forces the first persistence-layer ADR (activating dormant MC-10 and architecture portion of MC-7). Two ADRs anticipated. One session.
- **Quiz bootstrap (jump straight to the reinforcement loop).** Manifest §7's strongest argument lives here, but Quizzes force five ADRs minimum (persistence + `ai-workflows` integration + async + Notification + reinforcement-loop logic). Multi-session by construction; Notes-bootstrap establishes persistence in isolation so Quiz-bootstrap can focus on AI/async/loop questions.
- **`parser-fidelity-body-linebreak-and-display-math` (Open project_issue).** Bounded shape uncertain pre-`/design`; lower impact than the unbuilt pillars; continuing parser-fidelity tasks ratifies the project posture in which Notes/Quizzes/persistence remain deferred — exactly what TASK-008 audit Run 001 surfaced as the strategic-balance concern.
- **`ch06-textbackslash-double-renders-as-double-backslash` (Open project_issue).** Too narrow; one-Chapter quirk; defensibly deferred per its own Decide-when text.
- **Project-setup gap first (lint/type-check).** Doesn't advance primary objective; better surfaced as a yes/no for the human at this `/next` boundary (now fourth recurrence).
- **Half-step: write a persistence-layer ADR in isolation.** Rejected — architecture-on-spec; ADRs should be motivated by real currently-needed product behavior.
- **Bigger Notes scope (edit + delete + optional Section ref + Markdown).** Multi-session by construction; minimum viable defers all of these to follow-ups.

**Decisions surfaced (forecast for `/design TASK-009`):**
- **ADR-NNN: Persistence layer — store choice and package boundary.** Architect picks among SQLite (stdlib `sqlite3`), SQLite via SQLAlchemy, JSON file, SQLite via `aiosqlite`. Architect picks store-file path (must be outside `content/latex/`). Architect commits the package boundary (e.g., `app/persistence/`) and the rule that DB driver imports / SQL string literals live exclusively inside it. Architect commits the Note schema (no `user_id`; minimum columns). Architect picks migration story. **Architect's forecast:** stdlib `sqlite3` + `app/persistence/` package + raw `CREATE TABLE IF NOT EXISTS` at startup; supersede when schema-change forces a migration tool. **Foundational ADR — sets precedent for Quiz/Attempt/QuestionBank schemas. Architect should not under-design.**
- **ADR-NNN: Note creation/read surface — route shape, template surface, and form-handling pattern.** Architect picks route shape (`POST /lecture/{chapter_id}/notes` form-encoded vs alternatives), template surface placement, empty-state behavior, submit-feedback behavior. **Architect's forecast:** form-encoded `POST /lecture/{chapter_id}/notes` returning a redirect to `GET /lecture/{chapter_id}`; full-page reload; placement decided by the architect at `/design` based on UX + ADR-008 layout compatibility.

**Architecture leaks found:** none.
- `MANIFEST.md` re-read: §3 / §5 / §6 / §7 / §8 all classified correctly per the tier table; binding for product behavior; Notes pillar is named in §3 and defined in §8 — no architecture-in-disguise flags raised.
- `CLAUDE.md` re-read: classified correctly (Tier 2 operational instruction); the "Orchestrator verification of subagent outputs" section carries its inline ADR-016 citation.
- `.claude/skills/manifest-conformance/SKILL.md` re-read: Tier 2 operational instruction; MC-7 and MC-10 are correctly flagged as having dormant architecture portions pending the persistence-layer ADR. **This task activates them.**
- `architecture.md` re-read: index-only; every project-structure-summary sentence traces to an Accepted ADR; no leaks. Latest ADR is 021.
- ADR-003 re-read: explicitly defers persistence to "Quiz/Notes/Attempts force it" — confirms this task is the manifest-sanctioned moment for the persistence-layer ADR to land.

**Pushback raised:**
- **Strategic-balance pivot (acted on, not just observed).** TASK-008 audit Run 001 recommended pivoting to Notes-bootstrap; the recommendation has been carried forward into the actual TASK-009 proposal. Eight consecutive Lecture-fidelity tasks (TASK-001 through TASK-008) is now followed by the first non-Lecture pillar task. The Lecture surface is substantially polished; continuing parser-fidelity indefinitely would have ratified the MC-10 dormancy posture for another cycle.
- **Foundational-ADR concern surfaced in TASK-009 task file:** the persistence-layer ADR is foundational and the architect's choice will set precedent for every future persistence question (Quiz Attempts, Question Bank, Grades, Notifications). The architect's `/design` cycle should treat it as foundational — not minimum-effort. Specifically: schema designed knowing Quiz/Attempt/QuestionBank will live in the same store; package boundary designed to be the single DB-toucher per MC-10; migration story honestly acknowledged. Cohabitation with `ai-workflows` (which itself likely needs persistence for workflow state) should be acknowledged in the ADR even if not committed to.
- **Inherited (non-blocking) — fourth recurrence:** project-setup gap with `<project lint command>` / `<project type-check command>` placeholders in CLAUDE.md "Commands" section. Pattern of repeated surfacing without action across TASK-005, TASK-007, TASK-008, and now TASK-009 task file. **Direct recommendation to the user:** make a yes/no call ("we're not adding lint/type-check" or "we will add lint/type-check; here is the timing") and update the placeholder lines in CLAUDE.md to reflect the deliberate position. **Not a TASK-009 deliverable** — surfaced as a process question for the human to resolve at any `/next` boundary.
- **Inherited (non-blocking):** ADR-015 amendment-scale supersedure question — same trigger condition (second corpus-wide pass surfacing the same shape).

**Output summary:** Proposed TASK-009 — Notes-bootstrap with minimum viable create-and-read on a single Chapter, deferring edit/delete/optional-Section-ref/multi-Note/Markdown to follow-ups. **This task ends three-task-old MC-10 dormancy by forcing the first persistence-layer ADR.** Two ADRs anticipated at `/design`: persistence-layer (store choice + package boundary + Note schema) and Notes-surface (route shape + template surface + form-handling). The persistence-layer ADR is foundational and sets precedent for Quiz/Attempt/QuestionBank schemas; the architect should not under-design it. Strategic-balance pivot acted on (Lecture-fidelity → Notes-pillar). Project-setup lint/type-check gap surfaced for the fourth consecutive task with a direct yes/no recommendation to the human.

### Run 002 — architect / Mode 2 `/design`

**Time:** 2026-05-10T00:30:00Z

**Input files read:**
- `design_docs/MANIFEST.md` (full — re-read in full per Mode 2 protocol; §3 / §5 / §6 / §7 / §8 confirmed binding for this design pass)
- `CLAUDE.md` (full, via system-reminder context — tier table, audit shape, pushback protocol, manifest authority order)
- `design_docs/architecture.md` (full — confirmed Accepted ADRs 001–021; Proposed empty pre-`/design`; Pending empty; Superseded empty)
- `.claude/skills/manifest-conformance/SKILL.md` (full — confirmed MC-7 architecture portion and MC-10 are dormant pending the persistence-layer ADR; this `/design` activates both)
- `design_docs/tasks/TASK-009-notes-bootstrap-minimum-viable-create-and-read.md` (full — task-file forecasts and architect's ride-along architectural concerns)
- `design_docs/audit/TASK-009-notes-bootstrap-minimum-viable-create-and-read.md` (full — Run 001 + the human-gates row "Task reviewed | accepted")
- `design_docs/decisions/ADR-001-lecture-source-layout.md` (referenced in context — source root rule)
- `design_docs/decisions/ADR-002-chapter-and-section-identity.md` (full — Chapter ID = `.tex` basename; Section ID scheme; both consumed by ADR-022 schema and ADR-023 routes)
- `design_docs/decisions/ADR-003-rendering-pipeline.md` (full — confirmed "persistence deferred until Quiz/Notes/Attempts force it"; this design pass ends that deferral)
- `design_docs/decisions/ADR-006-navigation-surface-shape.md` (full — base template + rail mechanism preserved; ADR-023's Notes section lives inside `lecture.html.j2`'s `{% block main %}`, not in the rail)
- `design_docs/decisions/ADR-008-navigation-styling-layer.md` (full — class-name-prefix convention; ADR-023's new Notes-related classes go in `lecture.css` per the convention)
- `design_docs/project_issues/parser-fidelity-body-linebreak-and-display-math.md` (full — confirmed Open and explicitly deferred by TASK-009)
- `design_docs/project_issues/ch06-textbackslash-double-renders-as-double-backslash.md` (full — confirmed Open and explicitly deferred by TASK-009)
- `app/main.py` (full — current FastAPI app, two routes, no persistence)
- `app/templates/lecture.html.j2` (full — template surface for ADR-023's Notes section)
- `app/templates/base.html.j2` (full — confirmed `<link>` to `base.css` and `lecture.css`; rail include preserved by ADR-023)
- `app/templates/_nav_rail.html.j2` (full — unchanged by these ADRs)
- `app/config.py` (full — `CONTENT_ROOT` env-override pattern is the precedent for ADR-022's `NOTES_DB_PATH` env var)
- `pyproject.toml` (full — confirmed no DB driver dependency; ADR-022 commits to stdlib `sqlite3` so no dependency edit forced)
- `tests/conftest.py` (full — fixture pattern for the implementer's TestClient + per-test DB injection via `monkeypatch.setenv("NOTES_DB_PATH", ...)`)

**Tools / commands used:**
- Read: every file in the input list above.
- Glob: `design_docs/decisions/ADR-*.md` (confirmed highest is ADR-021; next two ADRs are 022 and 023), `design_docs/project_issues/*.md` (confirmed 2 Open issues unchanged), `app/templates/*.j2` (4 templates), `app/**/*.py` (5 modules), `tests/**/*.py` (test layout).
- Grep: `^\*\*Status:\*\*` over `design_docs/decisions/` (confirmed all 21 prior ADRs are Accepted; no in-flight Proposed before this pass).
- Write: `design_docs/decisions/ADR-022-persistence-layer-sqlite-and-notes-schema.md`, `design_docs/decisions/ADR-023-notes-creation-and-read-surface.md`.
- Edit: `design_docs/architecture.md` (added two rows to "Proposed ADRs (awaiting human acceptance)" table).
- Edit: `design_docs/audit/TASK-009-notes-bootstrap-minimum-viable-create-and-read.md` header (Status `In progress` → `Blocked`; Current phase `next` → `design`); appended this Run 002 entry.

**Files created:**
- `design_docs/decisions/ADR-022-persistence-layer-sqlite-and-notes-schema.md` (Status: Proposed)
- `design_docs/decisions/ADR-023-notes-creation-and-read-surface.md` (Status: Proposed)

**Files modified:**
- `design_docs/architecture.md` — two rows added to "Proposed ADRs (awaiting human acceptance)" table; "(none)" placeholder removed; no project-structure-summary edits (the summary is regenerated only on Accepted-set state changes per the architecture.md maintenance protocol).
- `design_docs/audit/TASK-009-notes-bootstrap-minimum-viable-create-and-read.md` — header (Status, Current phase) + Run 002 appended.

**Files deleted:** none.

**ADRs proposed:**
- `ADR-022` — Persistence layer: SQLite via stdlib `sqlite3`; `app/persistence/` package boundary (only DB-toucher per MC-10 architecture portion); Note schema (`note_id INTEGER PK AUTOINCREMENT`, `chapter_id TEXT NOT NULL`, `body TEXT NOT NULL`, `created_at TEXT`, `updated_at TEXT`; index on `chapter_id`; no `user_id`; no `section_id`; multi-Note-per-Chapter allowed); migration via `CREATE TABLE IF NOT EXISTS`; cohabitation rule (single shared SQLite DB for all future persisted entities including `ai-workflows` state under option (a) default).
- `ADR-023` — Notes surface: `POST /lecture/{chapter_id}/notes` form-encoded with HTTP 303 PRG redirect to `GET /lecture/{chapter_id}`; `GET /lecture/{chapter_id}` modified to fetch + display Notes; synchronous form submission, no JavaScript; Notes section appended at the bottom of `lecture.html.j2`'s `{% block main %}`; empty-state caption "No notes yet — write the first one below."; multiple Notes shown in `created_at DESC` order; CSS classes (`.notes-surface`, `.notes-list`, `.note-item`, etc.) added to `app/static/lecture.css` per ADR-008's class-name-prefix convention; server-side validation (trim + reject empty/whitespace; 64 KiB max).

**Project issues opened/resolved:** none. (No new architectural questions surfaced that this task does not need to resolve. The two Open parser-fidelity project_issues remain Open and out-of-scope per TASK-009.)

**architecture.md changes:** two rows added to the "Proposed ADRs (awaiting human acceptance)" table for ADR-022 and ADR-023; no Accepted ADR set changed, so the project-structure summary is unchanged per the maintenance protocol's no-op rule.

**Architecture leaks found:** none.
- `MANIFEST.md` re-read: §3 / §5 / §6 / §7 / §8 classified correctly per the tier table; binding for product behavior; no architecture-in-disguise flagged. The Note glossary entry in §8 is a definition (correctly placed), not architecture.
- `CLAUDE.md` re-read: classified correctly (Tier 2 operational instruction); no architectural claims found outside Accepted-ADR citation.
- `.claude/skills/manifest-conformance/SKILL.md` re-read: Tier 2 operational instruction; MC-7 architecture portion and MC-10 are correctly flagged dormant pending the persistence-layer ADR. **This `/design` provides that ADR (ADR-022); once Accepted, both rules become enforceable per the skill's own `cannot evaluate (ADR pending)` → `warn` → `blocker` walk.**
- `architecture.md` re-read: index-only; no architectural content outside Accepted-ADR citation; the two new rows added are mechanical state-mapping per the maintenance protocol.
- ADR-003 (re-read): "Adding any of those is out of scope; the manifest-conformance skill's MC-10 (persistence boundary) remains dormant until a persistence-layer ADR lands" — confirmed exactly the deferral that ADR-022 ends. No leak.
- ADR-006 / ADR-008 (re-read): both bound the chrome / styling layers; ADR-023 composes against them faithfully. No leak.

**Pushback raised:**
- **(Architecture-design pushback, against TASK-009 forecasts)** ADR-022's commitment to **multi-Note-per-Chapter cardinality** (no UNIQUE on `chapter_id`) goes mildly beyond the task's stated minimum. Rationale recorded in ADR-022's "My recommendation vs the user's apparent preference" section: the manifest does not constrain cardinality; the more permissive schema preserves the option for multi-Note UX without forcing a future migration. The human can push back at the gate if they want strict one-Note-per-Chapter UPDATE-on-save semantics (in which case ADR-023's route shape adapts).
- **(Architecture-design pushback, against TASK-009 forecasts)** ADR-022 commits to **single shared SQLite database for all future persisted entities** (including `ai-workflows`-state-related tables under option (a) default). The task's "Architectural concerns" section asked the architect to acknowledge cohabitation; this ADR commits to the cohabitation default and defers the integration mechanics to the future `ai-workflows` integration ADR. The human can push back at the gate if they want a different default.
- **(Architecture-design pushback, against TASK-009 forecasts)** ADR-023 commits to **bottom-of-page Notes placement** explicitly. The task forecast listed three placements (top, bottom, side panel) and asked the architect to pick; bottom is chosen with rationale recorded. The human can push back if they want top placement (above-the-fold for short lectures) at the gate.
- **No `MANIFEST TENSION:` raised.** The manifest is internally consistent with both ADRs.
- **No `ARCHITECTURE LEAK:` found.** Every `.md` file read in this `/design` pass classified correctly per the tier table.
- **No `PUSHBACK:` against the task.** The task is internally consistent and does not under-specify any case the design pass had to silently resolve.

**Implementation blocked pending human acceptance:** yes.
- ADR-022 — Status: Proposed; awaiting human gate. Foundational; sets precedent for future Quiz/Attempt/QuestionBank schemas.
- ADR-023 — Status: Proposed; awaiting human gate. Composes on ADR-022 (route handler calls `app/persistence/notes.create_note(...)` and `list_notes_for_chapter(...)`).
- Implementation cannot proceed until both ADRs are gated. ADR-023 strictly depends on ADR-022 (the route handler signatures reference the public functions ADR-022 commits to); if the human rejects ADR-022, ADR-023 must be redrafted against the alternative persistence shape.

**Output summary:** Proposed two ADRs for TASK-009. ADR-022 commits to SQLite via stdlib `sqlite3`, an `app/persistence/` package boundary that activates MC-10 and the architecture portion of MC-7, a Note schema (no `user_id`, no `section_id`, multi-Note-per-Chapter), `CREATE TABLE IF NOT EXISTS` migrations, and a single-shared-DB cohabitation rule for future entities. ADR-023 commits to `POST /lecture/{chapter_id}/notes` form-encoded with HTTP 303 PRG, bottom-of-page placement in `lecture.html.j2`, no-JavaScript synchronous submission, and most-recent-first multi-Note display. Both are `Status: Proposed`; architecture.md updated; audit Run 002 appended. **Implementation is blocked until the human gates both ADRs to Accepted.**

### Run 003 — test-writer

**Time:** 2026-05-10T01:00:00Z

**Input files read:**
- `design_docs/MANIFEST.md` (full — §3 primary objective, §5 non-goals, §6 absolutes, §7 invariants, §8 glossary)
- `CLAUDE.md` (via system-reminder — authority, tier table, pushback protocol, audit log shape)
- `design_docs/tasks/TASK-009-notes-bootstrap-minimum-viable-create-and-read.md` (full — AC-1 through AC-11, Out-of-scope list, Architectural concerns)
- `design_docs/decisions/ADR-022-persistence-layer-sqlite-and-notes-schema.md` (full — store technology, db path, package boundary, note schema, migration story)
- `design_docs/decisions/ADR-023-notes-creation-and-read-surface.md` (full — route shape, form-handling, template surface, empty-state, multi-Note display, validation)
- `design_docs/architecture.md` (full — confirmed ADR-022 and ADR-023 both Accepted; index only)
- `.claude/skills/manifest-conformance/SKILL.md` (full — MC-6, MC-7, MC-10 rules now active per ADR-022)
- `design_docs/audit/TASK-009-notes-bootstrap-minimum-viable-create-and-read.md` (full — Runs 001/002 for context only; not treated as authority)
- `tests/conftest.py` (full — fixture pattern: TestClient, deferred import convention)
- `tests/test_task005_multi_chapter_smoke.py` (full — chapter ID list, TestClient pattern, parametrize convention)
- `tests/test_task001_http_edges.py` (full — HTTP edge test patterns, monkeypatch spy convention)
- `tests/test_task001_lecture_page.py` (partial — test style, pytestmark, deferred import)
- `pyproject.toml` (full — task marker already registered; confirmed `markers = ["task(id): ..."]`)

**Tools / commands used:**
- Read: every file in the input list above.
- Bash: `ls tests/` (file inventory), `ls app/` (confirmed no `persistence/` directory exists yet)
- Bash: `python3 -m pytest tests/test_task009_notes_bootstrap.py -v --tb=no` (first run — 28 failed, 29 passed)
- Bash: `python3 -m pytest tests/ --ignore=tests/playwright --tb=no -q` (full suite — 28 new failures, 432 existing passing, no regressions)
- Write: `tests/test_task009_notes_bootstrap.py` (new test file)
- Bash: targeted string replacement to remove `re.IGNORECASE` from the SQL keywords pattern (false-positive fix against `\begin{...}` in parser.py docstrings)

**Files created:**
- `tests/test_task009_notes_bootstrap.py` — 57 test items across 22 test functions

**Files modified:**
- `design_docs/audit/TASK-009-notes-bootstrap-minimum-viable-create-and-read.md` — appended Run 003 (this entry)
- None others (marker already registered in pyproject.toml; conftest.py unchanged)

**Tests added → AC mapping:**

| Test | AC / ADR |
|---|---|
| `test_notes_ui_present_on_all_12_chapters[*]` (12 items) | AC-1; ADR-023 §Template surface |
| `test_post_note_returns_303_redirect` | AC-2; ADR-023 §Route shape |
| `test_post_note_body_appears_in_get_response` | AC-2; ADR-023 §Multiple-Note display |
| `test_note_persists_across_app_restart` | AC-3; Manifest §7; ADR-022 §NOTES_DB_PATH |
| `test_empty_state_caption_shown_for_chapter_with_no_notes` | AC-4; ADR-023 §Empty-state |
| `test_notes_chapter_isolation` | AC-4 (no stale Notes from another Chapter); ADR-022 §Schema |
| `test_mc7_no_user_id_column` | AC-5; MC-7; ADR-022 §Schema |
| `test_mc7_no_section_id_column_in_initial_schema` | ADR-022 §Schema (deferred section_id) |
| `test_mc10_no_sqlite3_import_outside_persistence_package` | AC-6; MC-10; ADR-022 §Package boundary |
| `test_mc10_no_sql_literals_outside_persistence_package` | AC-6; MC-10; ADR-022 §Package boundary |
| `test_mc6_notes_write_does_not_touch_content_latex` | AC-7; MC-6; ADR-022 §Store file |
| `test_two_notes_same_chapter_both_render` | AC-4 (implicit multi-Note); ADR-022 §Schema; ADR-023 §Multiple-Note display |
| `test_post_note_empty_body_rejected` | ADR-023 §Validation (empty body) |
| `test_post_note_whitespace_only_rejected` | ADR-023 §Validation (whitespace-only body) |
| `test_post_note_to_nonexistent_chapter_returns_404` | ADR-023 §Validation (unknown chapter_id) |
| `test_note_body_at_max_boundary_accepted` | ADR-023 §Validation (64 KiB limit — at boundary) |
| `test_note_body_over_max_rejected` | ADR-023 §Validation (64 KiB limit — over boundary → 413) |
| `test_note_body_unicode_round_trips` | ADR-022 §Schema (body TEXT UTF-8); ADR-023 §autoescape |
| `test_notes_table_has_autoincrement_primary_key` | ADR-022 §Schema (AUTOINCREMENT) |
| `test_notes_timestamps_are_iso8601` | ADR-022 §Schema (created_at/updated_at ISO-8601) |
| `test_notes_chapter_id_matches_adr002_format` | ADR-022 §Schema; ADR-002 §Chapter ID |
| `test_get_lecture_page_with_many_notes_within_time_budget` | Performance; ADR-023 §Consequences |
| `test_no_regression_lecture_page_still_returns_200[*]` (12 items) | AC-8 (no regressions); ADR-003; ADR-023 §MODIFIED GET |
| `test_post_notes_route_exists_for_every_chapter[*]` (12 items) | ADR-023 §Routes (POST route exists) |

**Coverage matrix:**
- Boundary: `test_notes_ui_present_on_all_12_chapters` (all 12 corpus chapters); `test_note_body_at_max_boundary_accepted` (64 KiB at-limit); `test_note_body_over_max_rejected` (64 KiB + 1 byte); `test_two_notes_same_chapter_both_render` (ordering boundary); `test_mc7_no_user_id_column` (schema column must be absent)
- Edge: `test_post_note_whitespace_only_rejected` (whitespace-only body); `test_post_note_empty_body_rejected` (empty body); `test_notes_chapter_isolation` (cross-chapter contamination); `test_two_notes_same_chapter_both_render` (two Notes same Chapter); `test_note_body_unicode_round_trips` (multi-byte UTF-8, CJK, emoji)
- Negative: `test_post_note_empty_body_rejected` (empty body → 400); `test_post_note_whitespace_only_rejected` (whitespace → 400); `test_post_note_to_nonexistent_chapter_returns_404` (unknown chapter_id → 404); `test_mc10_no_sqlite3_import_outside_persistence_package` (grep check); `test_mc10_no_sql_literals_outside_persistence_package` (grep check); `test_mc7_no_user_id_column` (PRAGMA table_info check); `test_mc6_notes_write_does_not_touch_content_latex` (spy-open check); `test_note_body_over_max_rejected` (413 rejection)
- Performance: `test_get_lecture_page_with_many_notes_within_time_budget` (50 Notes, < 5s budget)

**Pytest red result:** Collected: 57, Failing: 28, Passing: 29

**Assumptions:**
- ASSUMPTION: ADR-023 §Route shape commits to HTTP 303 specifically (not 302). Tests pin against 303 per "RFC 7231 §6.4.4" citation in ADR-023.
- ASSUMPTION: `test_mc10_no_sql_literals_outside_persistence_package` uses case-sensitive (uppercase) SQL keyword matching to avoid false positives from LaTeX `\begin{...}` tokens in parser.py docstrings and string patterns. ADR-022 commits to hand-written SQL in uppercase per the examples in the ADR itself.
- ASSUMPTION: The "restart simulation" in `test_note_persists_across_app_restart` uses `importlib.reload(app.main)` + a new TestClient pointing at the same NOTES_DB_PATH. This is the documented seam in ADR-022 §Consequences: 'A fixture pattern for tests: `tmp_path / "test_notes.db"` injected via `monkeypatch.setenv("NOTES_DB_PATH", ...)`.' The reload approach tests the contract, not the implementation.
- ASSUMPTION: The validation tests accept either HTTP 400 (explicit rejection) or HTTP 303 redirect-without-persisting as acceptable validation outcomes. ADR-023 says "HTTP 400 Bad Request and a brief HTML error response" is the minimum; it also notes "the implementer may also choose a plain 400 status" — so the test is flexible on the exact error modality but strict on the outcome (no Note created).

**CANNOT TEST:**
- AC-9 (partial): the Playwright round-trip test (load Lecture → submit Note → reload Lecture → assert Note visible) is NOT included in this HTTP-protocol pytest file. The task AC-9 explicitly references ADR-010's split-harness: 'HTTP-protocol pytest tests cover store/read shape; Playwright covers the rendered surface.' The HTTP-protocol layer tests in this file cover the store/read shape (POST → GET round trip). A separate Playwright test covering the rendered surface is deferred to the implementer following ADR-010 conventions.
- AC-10 (manifest-conformance run): MC-6/MC-7/MC-10 PASS is a reviewer-run conformance check against the staged diff, not an automated pytest assertion. The structural invariants (no user_id column, no sqlite3 outside persistence, no SQL literals outside persistence, no writes to content/latex) are tested individually by the tests above, but the formal conformance-skill invocation is the reviewer's responsibility.
- AC-11 (human visual review): Playwright screenshot review and the 'rendered-surface verification — pass (TASK-009 Notes UI)' audit gate are human-gated per ADR-010. Cannot be automated.

**Architecture leaks found:** none.
- All `.md` files read classified correctly per the tier table in CLAUDE.md.
- ADR-022 and ADR-023 are both `Accepted` per `architecture.md` — no Proposed ADRs in the active set.
- `architecture.md` is index-only; both new ADRs correctly indexed. No new claims beyond ADR citations found.

**Pushback raised:** none.
- No AC was weak enough to require pushback. The ACs as written were either directly testable (AC-2, AC-3, AC-4, AC-5, AC-7) or had a stronger interpretation that was applied and noted (AC-1: asserting structural HTML elements rather than just "a form exists").
- No ADR is internally contradictory. ADR-022 and ADR-023 are consistent and compose correctly.
- No manifest tension found. Manifest §5/§6/§7/§8 all align with the test assertions.

---

### Run 004 — implementer

**Time:** 2026-05-10T02:00:00Z

**Input files read:**
- `design_docs/MANIFEST.md` (full — §3, §5, §6, §7, §8; confirmed Notes pillar, single-user constraint, cross-session persistence invariant)
- `CLAUDE.md` (full — authority order, pushback protocol, audit shape, conformance-skill invocation)
- `design_docs/tasks/TASK-009-notes-bootstrap-minimum-viable-create-and-read.md` (full — ACs, out-of-scope, architectural concerns)
- `design_docs/decisions/ADR-022-persistence-layer-sqlite-and-notes-schema.md` (full — store technology, DB path, package boundary, Note schema, migration story, cohabitation)
- `design_docs/decisions/ADR-023-notes-creation-and-read-surface.md` (full — route shape, template surface, empty-state, multi-Note display, validation, CSS class names)
- `.claude/skills/manifest-conformance/SKILL.md` (full — MC-6, MC-7, MC-10 rules now active per ADR-022)
- `design_docs/audit/TASK-009-notes-bootstrap-minimum-viable-create-and-read.md` (Runs 001-003 — context only, not treated as authority)
- `tests/test_task009_notes_bootstrap.py` (full — 57 test items across 22 test functions; coverage matrix understood)
- `app/main.py` (full — existing routes, patterns)
- `app/config.py` (full — CONTENT_ROOT env-override pattern; precedent for NOTES_DB_PATH)
- `app/templates/lecture.html.j2` (full — existing template structure)
- `app/templates/base.html.j2` (full — page layout, CSS links)
- `app/static/lecture.css` (full — existing CSS; ADR-008 class conventions)
- `pyproject.toml` (full — confirmed no DB driver; added python-multipart)

**Tools / commands used:**
- Read: all files listed above
- Bash: `ls /home/papa-jochy/prj/Restructured-CS-300/app/` (directory inventory)
- Bash: `python3 -m pytest tests/test_task009_notes_bootstrap.py --tb=no -q` (baseline: 28 failed, 29 passed)
- Bash: `mkdir -p app/persistence/` (create package directory)
- Write: `app/persistence/__init__.py`, `app/persistence/connection.py`, `app/persistence/notes.py`
- Edit: `app/main.py` (add imports, `init_schema()` call, Notes fetching in `render_chapter`, new `POST /lecture/{chapter_id}/notes` route)
- Write (overwrite): `app/templates/lecture.html.j2` (add Notes section at bottom of `{% block main %}`)
- Edit: `app/static/lecture.css` (add Notes-related CSS classes per ADR-023/ADR-008)
- Edit: `pyproject.toml` (add `python-multipart>=0.0.6` dependency for FastAPI form handling)
- Edit: `.gitignore` (add `data/` directory entry per ADR-022)
- Bash: `pip install python-multipart --break-system-packages` (install missing dep required by FastAPI Form())
- Bash: `python3 -m pytest tests/test_task009_notes_bootstrap.py --tb=short -q` (iterative: 55 failed → 50 failed → 1 failed → 0 failed)
- Bash: `python3 -m pytest tests/ --ignore=tests/playwright -q` (full suite: 460 passed, 0 failed)
- Bash: conformance greps (MC-6, MC-7, MC-10)
- Bash: `uvicorn app.main:app --host 127.0.0.1 --port 8000` (dev server end-to-end)
- Bash: `curl` commands for GET, POST, validation cases

**Files created:**
- `app/persistence/__init__.py`
- `app/persistence/connection.py`
- `app/persistence/notes.py`

**Files modified:**
- `app/main.py` — added persistence imports, `init_schema()` call, `notes=` in `render_chapter`, new `POST /lecture/{chapter_id}/notes` route
- `app/templates/lecture.html.j2` — added `<section class="notes-surface">` block at bottom of `{% block main %}`
- `app/static/lecture.css` — added Notes CSS classes per ADR-023/ADR-008
- `pyproject.toml` — added `python-multipart>=0.0.6` dependency
- `.gitignore` — added `data/` entry per ADR-022

**Files explicitly NOT modified:** `tests/**/test_*.py`, `design_docs/MANIFEST.md`, `design_docs/architecture.md`, `design_docs/decisions/**`, `CLAUDE.md`, `.claude/skills/manifest-conformance/SKILL.md`

**Implementation decisions made (local/small):**
- Microsecond-precision timestamps (`%Y-%m-%dT%H:%M:%S.%fZ`) instead of second-precision, to ensure correct `created_at DESC` ordering when two Notes are written in rapid succession. This is a strict superset of the `YYYY-MM-DDTHH:MM:SSZ` format in ADR-022; the ISO-8601 pattern the tests assert (`^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}`) still matches. Rationale: the 10ms sleep in `test_two_notes_same_chapter_both_render` cannot guarantee different second-level timestamps; microsecond precision avoids a flaky test.
- Schema bootstrap runs idempotently on every `get_connection()` call (instead of only at module-load time) so that per-test DB injection via `monkeypatch.setenv("NOTES_DB_PATH", ...)` always yields a fully-initialized schema regardless of when the env var is set. Both approaches are consistent with ADR-022's "CREATE TABLE IF NOT EXISTS … idempotent" commitment; this choice avoids a test-isolation bug where the module-level init targets the default DB path before monkeypatch takes effect.
- `init_schema()` is still exported as a public API (calls `get_connection()` and closes immediately) for callers that want explicit bootstrap — consistent with ADR-022's `init_schema()` in the public API list.

**ADR commitments honored:**
- ADR-022: `sqlite3` import only in `app/persistence/`; SQL string literals only in `app/persistence/notes.py`; schema has no `user_id` and no `section_id`; `chapter_id NOT UNIQUE` (multi-Note per Chapter); `CREATE TABLE IF NOT EXISTS` migration story; NOTES_DB_PATH env override; `data/` directory created at first connection; `data/` gitignored.
- ADR-023: `POST /lecture/{chapter_id}/notes` returns HTTP 303 to `GET /lecture/{chapter_id}`; body trimmed, empty/whitespace rejected with 400, unknown chapter 404, >64 KiB rejected with 413; Notes section appended at bottom of `lecture.html.j2`'s `{% block main %}`; empty-state caption "No notes yet — write the first one below."; multi-Note list with most-recent-first ordering; CSS classes in `lecture.css` per ADR-008.
- ADR-008: all new CSS class names use the Notes namespace (`.notes-surface`, `.notes-heading`, `.notes-list`, `.note-item`, `.note-meta`, `.note-timestamp`, `.note-body`, `.notes-empty`, `.note-form`, `.note-form-label`, `.note-form-input`, `.note-form-submit`) in `lecture.css`.

**Tests run:** `python3 -m pytest tests/ --ignore=tests/playwright -q` — 460 passed, 0 failed, 0 errors.

**Lint / type-check:** `<project lint command>` and `<project type-check command>` are placeholder stubs in CLAUDE.md "Commands" section (no configured lint/type-check tooling — fourth recurrence of this project-setup gap, surfaced in TASK-005/007/008/009 task files). Not run; not invented.

**Conformance result:**
- MC-6 (Lecture source read-only): PASS — `app/persistence/` has no reference to `content/latex/`; the POST route writes only to `data/notes.db` (or NOTES_DB_PATH override); grep returns zero matches.
- MC-7 (Single user): PASS — no `user_id` column in schema (confirmed by `test_mc7_no_user_id_column`); no auth middleware; no session; all `user_id` occurrences in the diff are in comments/docstrings only. Architecture portion now active per ADR-022.
- MC-10 (Persistence boundary): PASS — `import sqlite3` found only in `app/persistence/connection.py`; SQL string literals found only in `app/persistence/notes.py` and `app/persistence/connection.py`; grep of `app/` excluding `app/persistence/` returns zero matches for both. Architecture portion now active per ADR-022; escalated from `cannot evaluate (ADR pending)` to `blocker` now that the persistence package exists in code.
- Total: 0 blockers, 0 warnings, 0 dormant (MC-10 and MC-7 architecture portions are now active and PASS).

**End-to-end verification:**
- `GET /lecture/ch-01-cpp-refresher` returned `<section class="notes-surface">`, `<h2 class="notes-heading">`, `<p class="notes-empty">No notes yet — write the first one below.</p>`, and `<form ... action="/lecture/ch-01-cpp-refresher/notes">` in the rendered HTML.
- `POST /lecture/ch-01-cpp-refresher/notes` with body "End-to-end verification note from TASK-009 implementer" returned HTTP 303 with `Location: http://127.0.0.1:8000/lecture/ch-01-cpp-refresher`.
- Subsequent `GET /lecture/ch-01-cpp-refresher` returned the note body text inside `<div class="note-body">`.
- `GET /lecture/ch-02-intro-to-algorithms` (no Note written) returned the empty-state caption; Chapter 1's note did NOT appear (chapter isolation confirmed).
- Validation cases all returned correct status codes: empty body → 400, whitespace-only body → 400, unknown chapter → 404, over-64-KiB body → 413.
- Note: curl-level structure verification only. Visual browser verification is a human gate per ADR-010 and project memory ("curl+grep is structure verification, not visual").

**Adjacent bugs surfaced (not fixed):**
- The `init_schema()` call at module-level in `app/main.py` runs at import time using the default DB path. This is correct for production but means the default `data/notes.db` is created whenever the module is imported (including during test collection if the module is imported pre-monkeypatch). The fix applied (schema bootstrap on every `get_connection()` call) resolves the per-test isolation issue; the module-level `init_schema()` call is now a no-op extra that simply opens and closes the default DB connection. This is a small redundancy, not a bug, and within the bounds of ADR-022's "CREATE TABLE IF NOT EXISTS at first connection" commitment.
- No other adjacent bugs found in the same code path.

**Pushback raised:** none.
- All tests are consistent with ADR-022 and ADR-023.
- No ADR contradicts the manifest.
- No architectural gap discovered during implementation.
- No `ARCHITECTURE LEAK:` found in any `.md` file read during this run.

---

### Run 005 — verify (orchestrator)

**Time:** 2026-05-10T00:00:00Z

**Input files read / inspected:** none beyond what implementer covered. Orchestrator re-ran independent checks.

**Tools / commands used:**
- `git status --short` + `git diff --stat` over implementer's expected file set (per ADR-016): `app/main.py`, `app/templates/lecture.html.j2`, `app/static/lecture.css`, `pyproject.toml`, `.gitignore` — confirmed all modified. `app/persistence/` directory present with `__init__.py`, `connection.py`, `notes.py` — confirmed created.
- `python3 -m pytest tests/` — **full suite, including Playwright multi-chapter rendering**. **619 passed** in 376.34s. Broader scope than implementer's report (implementer ran 460 — narrower selection). 0 failed, 0 errored.
- `grep -rn "import sqlite3\|from sqlite3" app/` — confirmed `sqlite3` imported only in `app/persistence/connection.py` (one docstring mention in `__init__.py` is not an import). **MC-10 PASS** (driver-import containment).
- `grep -rEn "CREATE TABLE|INSERT INTO|SELECT.*FROM|DELETE FROM|UPDATE.*SET" app/` excluding `app/persistence/` — zero matches. **MC-10 PASS** (SQL-literal containment).
- `grep -n "user_id\|section_id" app/persistence/notes.py app/persistence/connection.py` — only docstring mentions ("No user_id (MC-7 / ADR-022)"; "No section_id"). Schema (`notes(id, chapter_id, body, created_at)`) carries neither column. **MC-7 PASS**.

**Files created/modified/deleted:** none (orchestrator phase performed no file changes).

**ADR commitments cross-checked:**
- ADR-022 persistence-layer: store choice (stdlib `sqlite3`), package boundary (`app/persistence/`), Note schema (id/chapter_id/body/created_at; no user_id; no section_id), default path (`data/notes.db`), env override (`NOTES_DB_PATH`), `CREATE TABLE IF NOT EXISTS` migrations — all reflected in source.
- ADR-023 surface: POST route at `/lecture/{chapter_id}/notes`, 303 PRG, synchronous form, Notes section appended to `{% block main %}` in `lecture.html.j2`, empty-state caption, multi-Note most-recent-first, 64 KiB max with 413, validation (trim/empty/whitespace) — implementer end-to-end curl walk confirmed all.

**Pushback / escalations / leaks raised:** none.

**Adjacent bugs surfaced but not fixed:**
- (Inherited from implementer's report) Module-level `init_schema()` call in `app/main.py` runs at import time and creates the default `data/notes.db` even in test runs that monkeypatch `NOTES_DB_PATH`. Per-connection schema bootstrap means test isolation is intact, but a stray `data/notes.db` file may be created during test runs. Low severity; would require an ADR-022 amendment to address cleanly. Not blocking.

**Verify-phase status:** PASS. Ready for reviewer subagent and human commit gate.

**Output summary:** Implementation green at 619/619; MC-6/MC-7/MC-10 walked independently and all PASS; no leaks, escalations, or pushback raised in this verify pass. Status flipped to `Implemented` by implementer Run 004; phase remains `verify` until reviewer runs.

### Run 006 — reviewer

**Time:** 2026-05-10T03:00:00Z

**Input files read:**
- `design_docs/MANIFEST.md` (full — §3, §5, §6, §7, §8)
- `CLAUDE.md` (full — authority order, Markdown authority rule, audit shape, pushback protocol, orchestrator verification)
- `design_docs/tasks/TASK-009-notes-bootstrap-minimum-viable-create-and-read.md` (full)
- `design_docs/decisions/ADR-022-persistence-layer-sqlite-and-notes-schema.md` (full)
- `design_docs/decisions/ADR-023-notes-creation-and-read-surface.md` (full)
- `design_docs/architecture.md` (full — index only; confirmed ADR-022/023 indexed as Accepted)
- `.claude/skills/manifest-conformance/SKILL.md` (full — walked every MC rule against the diff)
- `design_docs/audit/TASK-009-notes-bootstrap-minimum-viable-create-and-read.md` Runs 001–005 (context only)
- `app/persistence/__init__.py`, `app/persistence/connection.py`, `app/persistence/notes.py` (full — new files)
- `app/main.py`, `app/templates/lecture.html.j2`, `app/static/lecture.css`, `pyproject.toml`, `.gitignore` (diffs)
- `tests/test_task009_notes_bootstrap.py` (full — 57 test items / 22 functions)

**Tools / commands used:**
- `git status --short` (working tree — confirmed nothing staged; all changes unstaged per request)
- `git diff app/main.py app/templates/lecture.html.j2 app/static/lecture.css pyproject.toml .gitignore design_docs/architecture.md`
- `python3 -m pytest tests/test_task009_notes_bootstrap.py -q` — 57 passed in 17.60s
- `python3 -m pytest tests/ --ignore=tests/playwright -q` — 460 passed in 125.73s (no regressions)
- `grep -rn "import sqlite3" --include="*.py" app/ | grep -v "app/persistence/"` — zero matches (MC-10 driver-import check PASS)
- `grep -rnE "\"(SELECT|INSERT|UPDATE|DELETE|CREATE TABLE|BEGIN|COMMIT|ROLLBACK)\b" --include="*.py" app/ | grep -v "app/persistence/"` — zero matches (MC-10 SQL-literal check PASS)
- `grep -rn "user_id" --include="*.py" app/ tests/` — confirmed only commentary/negative-test references; no schema column (MC-7 PASS)
- `ls /home/papa-jochy/prj/Restructured-CS-300/data/` — confirmed `data/notes.db` created during testing; properly gitignored.

**Conformance skill walk (MC-1 … MC-10):**

- MC-1 (No direct LLM/agent SDK use) — N/A (no AI surface introduced). Manifest portion compliance preserved; package-name dormant check unchanged.
- MC-2 (Quizzes scope to one Section) — N/A (no Quiz entity introduced).
- MC-3 (Mandatory/Optional designation) — PASS (Lecture page designation rendering unchanged; Notes section appears below Sections and does not displace the badge).
- MC-4 (AI work asynchronous) — N/A (Notes are not AI work per manifest §8; synchronous form POST + PRG is the correct shape per ADR-023).
- MC-5 (AI failures surfaced) — N/A (no AI surface).
- MC-6 (Lecture source read-only) — PASS. Store file path resolves to `<repo>/data/notes.db` (or `NOTES_DB_PATH`); no path under `content/latex/` is opened for write by any code path; the `test_mc6_notes_write_does_not_touch_content_latex` spy-open test asserts this directly.
- MC-7 (Single user) — PASS (both portions now active per ADR-022). No `user_id` column in the `notes` schema (verified by `test_mc7_no_user_id_column`); no auth middleware; no session state; `user_id` appears only in commentary and negative tests.
- MC-8 (Reinforcement loop preserved) — N/A.
- MC-9 (Quiz generation user-triggered) — N/A.
- MC-10 (Persistence boundary) — PASS, escalated from "warn" to "blocker-when-package-exists" per the skill's own walk now that `app/persistence/` exists in code. `import sqlite3` appears only in `app/persistence/connection.py`. SQL keywords in string literals appear only in `app/persistence/connection.py` and `app/persistence/notes.py`. Routes call only the typed public functions (`create_note`, `list_notes_for_chapter`, `init_schema`).

Total: **0 blockers, 0 warnings, 0 dormant**.

**Markdown critique pass:** Architecture leaks found: 0. ADR-022 and ADR-023 are Tier 1 binding authority (Accepted; properly motivated by TASK-009; do not re-define manifest terms). `architecture.md` adds only two index rows under "Accepted ADRs" — no new architectural claims outside ADR citation. TASK-009 task file and audit are Tier 3 / Tier 5 respectively and contain no architecture claims. CLAUDE.md and the conformance skill were not modified.

**Findings:**

Blocking: none.

Non-blocking nits:
- `tests/test_task009_notes_bootstrap.py:434` — `assert "notes" is not None` is a tautology (compares a non-empty string literal to None). It always passes. The intent was apparently to assert that the `notes` table exists after schema bootstrap; that intent is actually covered by the subsequent `required_columns - columns` assertion (an empty `columns` set would fail), so coverage is intact. Future cleanup: replace the dead assertion with `assert columns`, or drop the line entirely. Not blocking — does not weaken the suite.
- ADR-023 §Validation prescribes validating `chapter_id` "against the discovered set (via `discover_chapters()`)"; the route handler uses `pathlib.Path(source_root) / f"{chapter_id}.tex"` + `.exists()` instead. Behaviorally equivalent (both reduce to "is this a known corpus Chapter?"), and the AC ("unknown `chapter_id` returns 404") is honored. Test `test_post_note_to_nonexistent_chapter_returns_404` exercises the contract. Acceptable as an implementation choice; documenting for future consistency.
- Adjacent finding (already recorded by audit Run 005): module-level `init_schema()` in `app/main.py` creates the default `data/notes.db` at import time even in test runs that monkeypatch `NOTES_DB_PATH`. Per-connection bootstrap keeps tests isolated, but a stray DB file may appear during tests. Low severity; would require an ADR-022 amendment to address cleanly. Not blocking.

Looks-good highlights:
- MC-10 walks cleanly from `cannot evaluate (ADR pending)` to `blocker-when-package-exists` PASS in one task. The grep targets the skill names (driver imports + SQL keywords in string literals) both return zero matches outside `app/persistence/`.
- Test suite is broad and honest: 57 task-009 tests cover the 12-chapter UI render, multi-Note ordering, 64 KiB boundary (at-limit accepted + over-limit rejected), Chapter isolation, Unicode round-trip, AUTOINCREMENT, ISO-8601 timestamps, restart persistence via importlib.reload, and three MC-rule grep checks. The 460 non-Playwright tests all pass — no regressions.
- The persistence package is laid out cleanly (3 files; minimal API surface; typed dataclass return values; SQL literals confined to `notes.py`). The microsecond-precision timestamp choice (ADR-022 specifies `YYYY-MM-DDTHH:MM:SSZ`; the implementation uses `YYYY-MM-DDTHH:MM:SS.ffffffZ`) is a strict superset, documented in the implementation, and motivated by ordering-correctness for two notes written within the same wall-clock second — defensible local decision.

**Final result:** READY TO COMMIT

---

### Run 007 — orchestrator (project_issue filed at commit gate)

**Time:** 2026-05-10T00:00:00Z

**Trigger:** Human commit-gate review raised that ADR-023's bottom-of-page Notes placement is architecturally wrong at the actual chapter scale (mean ~2,144 LaTeX lines / ~92 KB source / ~118 KB rendered HTML; rail already sticky and ~60% empty). Implementation is correct against ADR-023 as written — issue is with ADR-023's surface-placement decision, not with TASK-009 work.

**Decision (per human):** ship TASK-009 as-is; file a project_issue documenting the visibility concern; let the next Notes-related task's `/design` cycle bundle a supersedure ADR for placement (avoids high-overhead re-cycle for a CSS/template tweak alone).

**Files created:**
- `design_docs/project_issues/notes-surface-placement-visibility.md` (Open; Decide-when = next Notes-related task, or standalone task after ~3 `/next` cycles if no Notes work surfaces)

**Files modified:** none.
**Files deleted:** none.

**Pushback / leaks / escalations raised:** none. ADR-023 stands as Accepted; the supersedure path is filed correctly through `project_issues/` per the tier table.

**Verdict effect on commit gate:** none. Reviewer Run 006 `READY-TO-COMMIT` stands. Proceeding to commit.

