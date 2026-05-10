# LLM Audit — TASK-010: Section completion marking — per-Section "mark complete" toggle that persists

**Task file:** `design_docs/tasks/TASK-010-section-completion-marking.md`
**Started:** 2026-05-10T00:00:00Z
**Status:** Committed
**Current phase:** review

---

## Human gates

| Time | Gate | Result | Notes |
|---|---|---|---|
| 2026-05-10T21:50:21Z | Task reviewed | auto-accepted | /auto run |
| 2026-05-10T21:58:59Z | ADR-024 reviewed | auto-accepted | /auto run |
| 2026-05-10T21:58:59Z | ADR-025 reviewed | auto-accepted | /auto run |
| 2026-05-10T22:56:02Z | Tests reviewed | auto-accepted | /auto run (resumed; AC-9 moved out of ACs — see Run 005) |
| 2026-05-10T23:31:09Z | Commit review | auto-accepted | /auto run — commit d2fec21 |

---

## Agent runs

### Run 001 — architect / Mode 1 `/next`

**Time:** 2026-05-10T00:00:00Z

**Input files read:**
- `design_docs/MANIFEST.md` (full — §3 primary objective, §5 non-goals, §6 absolutes, §7 invariants, §8 glossary; focused on §7 "Completion state lives at the Section level" — the unbuilt invariant this task activates — and §8's Section glossary entry that names "completion state" as a Section property)
- `CLAUDE.md` (via system-reminder — authority, tier table, pushback protocol, audit log shape, markdown critique pass)
- `design_docs/architecture.md` (full — confirmed Accepted ADRs 001–023; no Proposed; no Pending; no Superseded entries)
- `.claude/skills/manifest-conformance/SKILL.md` (full — confirmed MC-7 architecture portion and MC-10 are NO LONGER dormant after ADR-022 / TASK-009 — both PASS-active; this task adds a second entity-table within the existing boundary)
- `design_docs/tasks/TASK-009-notes-bootstrap-minimum-viable-create-and-read.md` (full — most recent task; precedent for "minimum viable vertical slice on an unbuilt manifest pillar")
- `design_docs/audit/TASK-009-notes-bootstrap-minimum-viable-create-and-read.md` (full — Runs 001 → 007, including Run 007 orchestrator-filed Notes-placement issue; ADR-022/ADR-023 confirmation; reviewer READY-TO-COMMIT; final commit `06c067f`)
- `design_docs/decisions/ADR-022-persistence-layer-sqlite-and-notes-schema.md` (full — single-shared-DB cohabitation commitment explicitly anticipates this task's pattern; quote: "When Quiz-bootstrap lands, it adds (e.g.) `app/persistence/quizzes.py` … to the same package")
- `design_docs/decisions/ADR-023-notes-creation-and-read-surface.md` (full — precedent for form-encoded POST + 303 PRG + bottom-of-page template surface; the per-Section completion affordance follows the same shape scaled to per-Section)
- `design_docs/decisions/ADR-002-chapter-and-section-identity.md` (partial — confirmed Section ID scheme `{chapter_id}#section-{n-m}`; flagged in "Architectural concerns" that this scheme is URL-fragment-shaped and not directly path-segment-usable)
- `design_docs/project_issues/notes-surface-placement-visibility.md` (full — confirmed Open; Decide-when says "bundle with next Notes-related task"; this task is not Notes-related, so issue stays Open)
- `design_docs/project_issues/parser-fidelity-body-linebreak-and-display-math.md` (full — confirmed Open; explicitly deferred again)
- `design_docs/project_issues/ch06-textbackslash-double-renders-as-double-backslash.md` (full — confirmed Open; explicitly deferred again)
- `design_docs/project_issues/tooling-lint-and-type-check.md` (full — confirmed Open low priority; fifth-recurrence carried forward in "Architectural concerns")
- `app/main.py` (full — 304 lines; confirmed `render_chapter` passes `sections` to template; `lecture_page` returns rendered HTML; precedent for a per-Section POST route)
- `app/templates/lecture.html.j2` (full — confirmed `{% for section in sections %}` loop is the natural surface for per-Section affordance; precedent from ADR-023 Notes block at bottom of `{% block main %}`)
- `app/persistence/notes.py` (full — precedent shape for `app/persistence/section_completions.py` module: dataclass, public functions, SQL literals confined to module)

**Tools / commands used:**
- Read on every file in the input list above.
- Glob: `design_docs/decisions/*.md` (confirmed highest ADR is 023; next is 024), `design_docs/project_issues/*.md` (14 files total; confirmed 4 Open: Notes-placement, two parser-fidelity, tooling-lint-and-type-check), `design_docs/tasks/*.md` (highest is TASK-009; next is TASK-010), `design_docs/audit/*.md` (9 audit files matching).
- Grep: `complet` over `app/` (confirmed zero completion-related code in app/; the manifest §7 invariant is entirely unbuilt), `complet` over `design_docs/decisions/` (confirmed mentions in 12 ADRs are incidental wording, not architectural commitments — no completion ADR exists).
- Write: `design_docs/tasks/TASK-010-section-completion-marking.md`, `design_docs/audit/TASK-010-section-completion-marking.md`.

**Files created:**
- `design_docs/tasks/TASK-010-section-completion-marking.md`
- `design_docs/audit/TASK-010-section-completion-marking.md`

**Files modified:** none.
**Files deleted:** none.

**Task alternatives considered:**
- (Chosen) **Section completion marking — minimum viable per-Section toggle.** Smallest non-trivial vertical slice on an unbuilt manifest §7 invariant ("Completion state lives at the Section level"). Validates ADR-022's single-shared-DB cohabitation commitment with a second entity-table. Establishes the per-Section affordance surface pattern Quiz-bootstrap will reuse. One session, one or two ADRs. No AI/async machinery.
- **Quiz bootstrap (jump straight to the reinforcement-loop pillar).** Manifest §7's strongest argument lives here ("the reinforcement loop is the reason this project exists"). Forces five ADRs minimum (persistence schema extensions + `ai-workflows` integration + async + Notification + reinforcement-loop logic). Multi-session by construction. Completion-state is the smaller-prerequisite that exercises persistence-cohabitation in isolation before Quiz-bootstrap forces all five ADRs concurrently.
- **`ai-workflows` integration spike (pre-Quiz, no-Quiz).** Rejected — manifest §5 explicitly says Quiz is the only AI-driven learner surface; no non-Quiz AI feature exists to host a spike. `ai-workflows` integration must be motivated by Quiz-bootstrap directly.
- **Notes follow-up — edit/delete + surface placement supersedure.** Rejected as next task — Notes is bootstrapped; iterating on it ratifies the "Quizzes deferred" posture for another cycle. The Notes-placement issue's own Decide-when allows for ~3 `/next` cycles of deferral; this is the first one.
- **Parser-fidelity grab-bag (three Open project_issues).** Rejected — Lecture surface substantially polished; sixth task in a row of non-§7 work would be the wrong shape.
- **Lint/type-check tooling task.** Rejected — project-setup gap; doesn't advance primary objective. Fifth-recurrence carried forward as yes/no for the human.
- **Half-step: ship persistence schema for completion without UI affordance.** Rejected — architecture-on-spec; same anti-pattern as TASK-009's rejected "ADR-in-isolation" alternative.
- **Bigger scope: include Chapter-level derived progress display + Mandatory-only filtered view + rail-side progress indicators.** Rejected — multi-session by construction. The minimum scope is the primitive (per-Section state); derived views consume it without re-deciding the schema.

**Decisions surfaced (forecast for `/design TASK-010`):**
- **ADR-NNN: Section completion schema and persistence module.** Architect picks schema shape (one row per completed Section vs one row per ever-touched Section vs event log), whether `chapter_id` is a separate column or derivable, whether `section_id` is validated against the discovered set on write, the module path (forecast `app/persistence/section_completions.py`) and public API surface, and how this exercises ADR-022's cohabitation commitment. Architect's forecast: option (1) (one row per completed Section; unmarking deletes row; presence ≡ complete) for simplicity; module follows the `notes.py` precedent.
- **ADR-NNN (possibly separate): Section completion UI surface.** Architect picks route shape (forecast `POST /lecture/{chapter_id}/sections/{n-m}/complete` mirroring ADR-023's per-Chapter Notes shape, scaled per-Section), template placement within each `<section id="...">` block, state-indicator shape, and CSS class names. **Architect's forecast:** inline placement next to `<h2 class="section-heading">`; toggle via separate `mark`/`unmark` routes or a hidden form field; CSS class `.section-complete` adds visual styling on completed Sections.

**Note on ADR cardinality:** the architect should consider whether the schema and surface decisions are separable enough to warrant two ADRs (ADR-022/023 precedent) or whether they fold cleanly into one (the surface decision is small and tightly coupled to the schema's `section_id` shape). Architect's call.

**Note on ADR-002 path-segment friction:** Section IDs per ADR-002 are URL-fragment-shaped (`{chapter_id}#section-{n-m}`); the `#` is path-vs-fragment separator in URLs, so the full Section ID cannot be a path segment. The route handler must decompose Section ID into chapter_id (path) + section-number (path or query). Surfaced in "Architectural concerns" so the `/design` cycle explicitly commits to a translation step; this is not a defect in ADR-002 (which was designed for HTML anchor use), only a friction point the new route must account for.

**Architecture leaks found:** none.
- `MANIFEST.md` re-read: §3 / §5 / §6 / §7 / §8 all classified correctly per the tier table; binding for product behavior; §7 "Completion state lives at the Section level" is the load-bearing invariant this task activates — no architecture-in-disguise flag raised.
- `CLAUDE.md` re-read: classified correctly (Tier 2 operational instruction); the "Orchestrator verification of subagent outputs" section carries its inline ADR-016 citation; no leaks.
- `.claude/skills/manifest-conformance/SKILL.md` re-read: Tier 2 operational instruction; MC-7 and MC-10 are correctly recorded as no-longer-dormant per ADR-022 / TASK-009; this task tests the second-entity case of the same boundary.
- `architecture.md` re-read: index-only; every project-structure-summary sentence traces to an Accepted ADR (latest ADR-023); no leaks.
- ADR-022 re-read: single-shared-DB cohabitation commitment explicitly anticipates this task's pattern; not a leak — a pre-positioning the new ADR consumes.
- ADR-023 re-read: surface-shape precedent for per-Chapter Notes; the per-Section completion affordance follows the same shape scaled to per-Section. No leak.
- ADR-002 re-read: Section ID scheme is URL-fragment-shaped; flagged as friction point for the new route (not a leak; a translation step).

**Pushback raised:**
- **Strategic-balance pivot (continuing from TASK-009).** TASK-009 completed the Notes bootstrap and validated the persistence layer (ADR-022). Continuing to iterate on Notes or returning to parser-fidelity would ratify the project posture in which the manifest §7 completion-state invariant remains unbuilt for an eleventh consecutive task. **Direct recommendation:** the next vertical slice is on the §7 completion-state invariant, which this task takes. Quiz-bootstrap is the strategically correct task after this one (manifest §7's "reinforcement loop is the reason this project exists"), and Section-completion exercises the persistence-cohabitation pattern as a Quiz-bootstrap prerequisite without dragging `ai-workflows` / async / Notification into the same session.
- **Foundational-ADR validation:** ADR-022's single-shared-DB cohabitation commitment has not yet been tested in code (only Notes was added). This task validates the cohabitation pattern empirically — the architect's `/design` cycle should treat the experience as evidence for/against ADR-022's pattern. If friction surfaces (e.g., schema-bootstrap centralization in `connection.py` becomes awkward, or per-table test isolation breaks down), the architect should record it and consider whether a small amendment is warranted before Quiz-bootstrap forces multiple new modules at once.
- **Inherited (non-blocking) — fifth recurrence:** project-setup gap with `<project lint command>` / `<project type-check command>` placeholders in CLAUDE.md "Commands" section. Filed as Open project_issue during TASK-009 (`tooling-lint-and-type-check.md`); placeholders remain unfilled. **Direct recommendation to the user:** make the yes/no call ("we will add tooling; here is the timing" or "we are deferring; update the placeholders to reflect deliberate-deferral"). Not a TASK-010 deliverable.
- **Inherited (non-blocking):** ADR-015 amendment-scale supersedure question — unchanged trigger condition; no second corpus-wide pass surfaced; not raised this cycle.

**Output summary:** Proposed TASK-010 — Section completion marking with minimum viable per-Section toggle that persists. **This task activates the manifest §7 "Completion state lives at the Section level" invariant**, which has been unbuilt for the project's entire ten-task history. Forces one or two ADRs at `/design`: schema + persistence module (extends ADR-022's package boundary with a second entity-module; first concrete validation of ADR-022's single-shared-DB cohabitation commitment) and possibly a separate surface-shape ADR (per-Section affordance in `lecture.html.j2`). The task explicitly defers Chapter-level derived progress, Mandatory-only filtered views, Quiz integration, Notes follow-ups, and parser-fidelity Open issues. **The next task after this one should be Quiz-bootstrap** (manifest §7 reinforcement-loop pillar); this task is the prerequisite that exercises persistence cohabitation in isolation. Project-setup lint/type-check gap surfaced for the fifth consecutive `/next` cycle with a direct yes/no recommendation to the human.

### Run 002 — architect / Mode 2 `/design`

**Time:** 2026-05-10T22:00:00Z

**Input files read:**
- `design_docs/MANIFEST.md` (full re-read — §3 / §5 / §6 / §7 / §8 confirmed binding; §7 "Completion state lives at the Section level" is the load-bearing invariant the new ADRs activate; no entries flagged as architecture-in-disguise)
- `CLAUDE.md` (via system-reminder — tier table, pushback protocol, audit log shape, markdown critique pass, write-path check requirement)
- `design_docs/architecture.md` (full — confirmed Accepted ADRs 001–023; Proposed table empty before this run)
- `.claude/skills/manifest-conformance/SKILL.md` (full — MC-3, MC-6, MC-7, MC-8, MC-10 are the load-bearing rules for the two new ADRs; all preserved by construction)
- `design_docs/tasks/TASK-010-section-completion-marking.md` (full — task forecasts the two ADRs and decision space for both)
- `design_docs/audit/TASK-010-section-completion-marking.md` (Run 001 — architect's `/next` forecast and Architectural-concerns section)
- `design_docs/decisions/ADR-022-persistence-layer-sqlite-and-notes-schema.md` (full — single-shared-DB cohabitation commitment is the load-bearing precedent ADR-024 validates)
- `design_docs/decisions/ADR-023-notes-creation-and-read-surface.md` (full — PRG redirect + form-encoded POST + bottom-of-page template-surface precedent; ADR-025 mirrors the form-handling pattern, scaled per-Section)
- `design_docs/decisions/ADR-002-chapter-and-section-identity.md` (full — Section ID is `{chapter_id}#section-{n-m}`; ADR-025 commits to a route shape that decomposes this into path segments to avoid the `#` path/fragment-separator collision)
- `design_docs/decisions/ADR-008-navigation-styling-layer.md` (partial — confirmed `.section-*` class names belong in `app/static/lecture.css`)
- `design_docs/project_issues/notes-surface-placement-visibility.md` (full — confirmed Open and explicitly NOT addressed in this task per its own Decide-when)
- `app/main.py` (full — confirmed `render_chapter` shape; `lecture_page` returns rendered HTML; `create_note_route` PRG precedent for ADR-025)
- `app/persistence/__init__.py` (full — confirmed public-API export pattern that ADR-024 extends)
- `app/persistence/connection.py` (full — confirmed `_SCHEMA_SQL` shape; ADR-024 commits to extending the string in-place; centralized pattern validated for 2 tables)
- `app/persistence/notes.py` (full — confirmed module shape that `section_completions.py` mirrors per ADR-024)
- `app/templates/lecture.html.j2` (full — confirmed `{% for section in sections %}` loop; ADR-025 places the completion form inside each `<section>` block)
- `app/parser.py` (partial — confirmed `extract_sections` returns dicts with `id`, `fragment`, `heading`, `body_html`; ADR-025 commits to a small additive `section_number` field derivation)
- `app/static/lecture.css` (partial — confirmed existing color palette; ADR-025 commits to reusing it rather than introducing a new color family)
- `design_docs/decisions/` (Glob — confirmed highest ADR is 023; next is 024 → 025)

**Tools / commands used:**
- Read on every file in the input list above
- Glob: `design_docs/project_issues/*.md` (confirmed 14 issues; 4 Open; none resolved by these ADRs), `design_docs/decisions/*.md` (confirmed next ADR numbers 024/025)
- Grep: `section_id|section-1-1|fragment` over `app/` (confirmed `section.fragment` is the existing template field; `section.id` is the full composite ID per ADR-002 — the new `section_number` field is a clean addition)
- Write: `design_docs/decisions/ADR-024-section-completion-schema-and-persistence-module.md`, `design_docs/decisions/ADR-025-section-completion-ui-surface.md`
- Edit: `design_docs/architecture.md` (added two rows to Proposed ADRs table), `design_docs/audit/TASK-010-section-completion-marking.md` (header status update + this Run 002 entry)

**Files created:**
- `design_docs/decisions/ADR-024-section-completion-schema-and-persistence-module.md`
- `design_docs/decisions/ADR-025-section-completion-ui-surface.md`

**Files modified:**
- `design_docs/architecture.md` (added ADR-024 and ADR-025 rows to Proposed ADRs table; no other content changed; no architectural claims introduced)
- `design_docs/audit/TASK-010-section-completion-marking.md` (header: Status → Blocked, Current phase → design; appended this Run 002)

**Files deleted:** none.

**ADRs proposed:**
- `ADR-024` — Section completion schema and persistence module — `section_completions(section_id PK, chapter_id, completed_at)` with presence-as-complete semantics, new module `app/persistence/section_completions.py` mirroring `notes.py` shape, schema-bootstrap via extension of `_SCHEMA_SQL` in `connection.py`. First concrete validation of ADR-022's single-shared-DB cohabitation commitment; ADR explicitly records the validation finding (pattern holds; no supersedure forced).
- `ADR-025` — Section completion UI surface — `POST /lecture/{chapter_id}/sections/{section_number}/complete` with `action` form field (`mark`/`unmark`), inline affordance next to each `<h2 class="section-heading">` in `lecture.html.j2`, three-layered state indicator (button text + button-class modifier + section-level CSS class `.section-complete`), full-page PRG redirect with URL fragment to preserve scroll position. Small additive parser change: `section_number` field added to each Section dict in `extract_sections()`. New CSS classes added to `app/static/lecture.css` per ADR-008's prefix convention.

**Project issues opened/resolved:** none. (TASK-010 §Architectural-concerns explicitly directs the architect NOT to opportunistically address the `notes-surface-placement-visibility` Open issue here; this task is not a Notes-related task. No new architectural question surfaced during `/design` that needs a project_issue — all decisions are forced and resolvable in this cycle.)

**architecture.md changes:** two rows added to Proposed ADRs table (ADR-024 + ADR-025). No content added to project-structure summary or any other section (those are derived from Accepted ADRs only per the architecture.md maintenance protocol; Proposed ADRs do not yet contribute to the summary).

**Write-path check:** clean. All file changes are within `design_docs/{tasks,audit,decisions,project_issues}/**` — specifically: `design_docs/decisions/ADR-024-*.md` (created), `design_docs/decisions/ADR-025-*.md` (created), `design_docs/architecture.md` (modified — mechanical Proposed-ADRs row addition only), `design_docs/audit/TASK-010-*.md` (modified — header + Run 002). No edits to `app/`, `tests/`, `CLAUDE.md`, `MANIFEST.md`, or any skill file. No scratch files created.

**Architecture leaks found:** none.
- `architecture.md` re-read: project-structure summary remains derived from Accepted ADRs 001–023 (latest ADR-023); no new sentence introduced into the summary; the two new rows go in the Proposed table per the maintenance protocol. No leak.
- ADR-022 re-read: §Future-cohabitation explicitly pre-positions this task; not a leak — a pre-positioning ADR-024 consumes.
- ADR-023 re-read: form-handling-pattern precedent; not a leak — a shape ADR-025 mirrors.
- ADR-002 re-read: Section ID scheme is the natural FK target; ADR-025 explicitly commits to decomposing the composite ID into path segments to avoid the `#` separator collision (recorded as a constraint, not a leak).
- All other read ADRs: no leaks.

**Pushback raised:**
- **ADR-024 §My-recommendation-vs-user-preference (architect push beyond task forecast):** the architect commits to a **redundant `chapter_id` column** rather than deriving it from the prefix of `section_id` via `LIKE`. Task forecast leaves this open. Rationale (indexed B-tree lookup, query legibility, future Mandatory-only views) recorded in the ADR; if the human prefers the leaner schema, this is the gate to push back. **Not a blocker.**
- **ADR-024 §My-recommendation-vs-user-preference (architect API push):** `mark_section_complete` returns the persisted `SectionCompletion` dataclass rather than `None` (mirrors `create_note(...) -> Note` precedent from ADR-022; gives tests a return value to assert on). Task forecast does not prescribe. **Not a blocker.**
- **ADR-024 §My-recommendation-vs-user-preference (architect rename):** `list_complete_sections_for_chapter` (task forecast) → `list_complete_section_ids_for_chapter` (this ADR) — explicit that it returns IDs, not `SectionCompletion` objects. **Not a blocker.**
- **ADR-025 §My-recommendation-vs-user-preference (architect push beyond task forecast):** the PRG redirect carries a **URL fragment** (`#section-{section_number}`) to scroll the browser back to the just-toggled Section. Task forecast does not prescribe; the architect's rationale (otherwise the round-trip becomes "click, scroll back to find what you clicked, confirm" on a long Chapter) is recorded. **Not a blocker.**
- **ADR-025 §My-recommendation-vs-user-preference (architect push beyond task forecast):** the **three-layered state indicator** (button text + button-class modifier + section-level CSS class) rather than picking one of the task's enumerated options (a)–(d). Rationale (concurrent signals at three reading distances) recorded. **Not a blocker.**
- **ADR-025 §My-recommendation-vs-user-preference (architect rejection):** the **native `<input type="checkbox">` affordance is rejected** because submit-on-change requires JavaScript, which contradicts ADR-023's no-JS posture. If the human strongly prefers checkbox shape, alternative resolutions (CSS-styled button, SVG icon) are enumerated in the "My recommendation" section. **Not a blocker.**
- **ADR-025 §My-recommendation-vs-user-preference (architect push beyond task forecast):** the **small parser addition** (new `section_number` field in `extract_sections()` output dict) is a parser change in service of a UI surface. Architect rationale: parser is the source of Section metadata; one-line pure derivation. If the human prefers Jinja2-side derivation, that is also acceptable; the architectural commitment is the route URL containing the section number. **Not a blocker.**
- **ADR-024 §Cohabitation-validation finding:** the architect explicitly records that **ADR-022's single-shared-DB cohabitation pattern is validated by this task** — adding `section_completions.py` alongside `notes.py` requires no change to MC-10's grep target, the centralized `_SCHEMA_SQL` in `connection.py` is tractable at 2 tables, and the `NOTES_DB_PATH` test-fixture pattern works for multi-entity isolation. **No amendment of ADR-022 forced.** If Quiz-bootstrap (next task) surfaces friction with the centralized schema string, that ADR will revisit; this one does not.
- **Inherited (non-blocking) — fifth recurrence:** `tooling-lint-and-type-check.md` Open issue carried forward in TASK-010. Not in this ADR scope; no `/design` action.
- **Inherited (non-blocking):** `notes-surface-placement-visibility.md` Open issue — explicitly NOT addressed in this `/design` cycle per the issue's own Decide-when ("bundle with next Notes-related task"). This task is not Notes-related. Stays Open.
- **No MANIFEST TENSION raised.** No `ARCHITECTURE LEAK:` found.

**Implementation blocked pending human acceptance:** yes — ADR-024 and ADR-025 are `Status: Proposed`. The human needs to gate-accept both before `/implement TASK-010` can proceed. Once Accepted, the two rows move from "Proposed ADRs" to "Accepted ADRs" in `architecture.md` and the project-structure summary is regenerated from the new Accepted set (per the maintenance protocol).

**Output summary:** Proposed ADR-024 (Section completion schema + `app/persistence/section_completions.py` module; presence-as-complete semantics; first concrete validation of ADR-022's cohabitation commitment, which holds) and ADR-025 (per-Section UI surface; `POST /lecture/{chapter_id}/sections/{section_number}/complete` with `action` form field; inline heading-adjacent placement; three-layered state indicator; PRG with URL fragment). Both Proposed; awaiting human gate before implementation. Two rows added to `architecture.md` Proposed-ADRs table. Pushback raised on six architect-vs-forecast deltas (all non-blocker, recorded in the ADRs for human review). No project issues opened or resolved. No leaks. No MANIFEST TENSION. ADR-022's cohabitation pattern explicitly validated; no supersedure forced. Implementation blocked pending human acceptance of ADR-024 and ADR-025.

### Run 003 — test-writer

**Time:** 2026-05-10T22:30:00Z

**Input files read:**
- `design_docs/tasks/TASK-010-section-completion-marking.md` (full — all 11 ACs, architectural concerns, out-of-scope list, verify checklist)
- `design_docs/decisions/ADR-024-section-completion-schema-and-persistence-module.md` (full — schema shape, public API, module path, cohabitation validation, conformance check)
- `design_docs/decisions/ADR-025-section-completion-ui-surface.md` (full — route shape, form-handling pattern, template placement, state indicator, CSS classes, validation, conformance check)
- `design_docs/MANIFEST.md` (full — §3 primary objective, §5 non-goals, §6 absolutes, §7 invariants, §8 glossary)
- `.claude/skills/manifest-conformance/SKILL.md` (full — MC-6, MC-7, MC-10 rules that are active per ADR-022 and extended by ADR-024/ADR-025)
- `design_docs/audit/TASK-010-section-completion-marking.md` (Runs 001 + 002 — context only, not authority)
- `tests/conftest.py` (full — lecture_client, repo_root fixtures)
- `tests/playwright/conftest.py` (full — live_server fixture, uvicorn subprocess pattern)
- `tests/test_task009_notes_bootstrap.py` (full — precedent for persistence test patterns, _make_client, _direct_db_list_notes, monkeypatch NOTES_DB_PATH, storage-level observer pattern)
- `tests/playwright/test_task001_lecture_page_dom.py` (first 60 lines — Playwright test structure, pytestmark, expect() usage)
- `app/persistence/__init__.py` (full — current public API exports; confirms new exports not yet present)
- `app/parser.py` lines 679-708 (extract_sections public signature; confirmed section_number field not yet present)
- `pyproject.toml` (markers section — confirmed task marker already registered)

**Tools / commands used:**
- Read on every file in the input list above
- Bash: `find tests/ -type f | sort` (test layout discovery)
- Bash: `grep -n "markers\|task\|TASK" pyproject.toml` (marker registration check)
- Bash: `grep -n "section_number\|section_completions\|complete_section" app/parser.py` (confirm feature not yet implemented)
- Bash: `python3 -m pytest tests/test_task010_section_completion.py --tb=no -q` (RED verification)
- Bash: `python3 -m pytest tests/playwright/test_task010_section_completion_dom.py --collect-only -q` (Playwright collection check)

**Files created:**
- `tests/test_task010_section_completion.py`
- `tests/playwright/test_task010_section_completion_dom.py`

**Files modified:** none (task marker already registered in pyproject.toml; conftest.py unchanged).

**Tests added:**

HTTP / persistence tests (`tests/test_task010_section_completion.py`):

| Test name | AC mapping |
|---|---|
| `test_completion_affordance_on_all_12_chapters[*]` (×12) | AC-1 — affordance present on all corpus Chapters |
| `test_post_complete_returns_303_redirect` | AC-2 — PRG 303 on mark |
| `test_post_complete_redirect_location_contains_chapter` | AC-2 — Location header points to chapter + fragment |
| `test_post_mark_persists_to_database` | AC-2 — row written to section_completions |
| `test_marked_section_shown_as_complete_on_lecture_page` | AC-2 — rendered page shows complete state |
| `test_completion_persists_across_app_restart` | AC-3 — persistence across simulated restart |
| `test_completion_state_chapter_isolation` | AC-4 — no cross-Chapter state on rendered page |
| `test_completing_in_chapter_a_does_not_appear_in_raw_db_for_chapter_b` | AC-4 — DB-level isolation |
| `test_unmark_removes_completion` | AC-5 — unmark reverts visual state |
| `test_unmark_removes_db_row` | AC-5 — unmark deletes DB row (presence-as-complete) |
| `test_mark_complete_idempotent` | AC-5 edge — double-mark is no-op (INSERT OR IGNORE) |
| `test_unmark_complete_idempotent` | AC-5 edge — unmark on incomplete is no-op |
| `test_mark_unmark_mark_toggle_cycle` | AC-5 — full M→U→M toggle cycle at storage level |
| `test_mc10_no_sqlite3_import_outside_persistence_package` | AC-6 / MC-10 |
| `test_mc10_no_sql_literals_outside_persistence_package` | AC-6 / MC-10 |
| `test_mc7_no_user_id_column_in_section_completions` | AC-6 / MC-7 |
| `test_section_completions_required_columns_present` | AC-10 / ADR-024 schema shape |
| `test_mc6_completion_write_does_not_touch_content_latex` | AC-6 / MC-6 |
| `test_no_regression_lecture_page_still_returns_200[*]` (×12) | AC-7 — no regressions |
| `test_persistence_init_exports_completion_functions` | AC-10 — __init__.py re-exports |
| `test_mark_section_complete_returns_section_completion_dataclass` | AC-10 / ADR-024 API shape |
| `test_list_complete_section_ids_for_chapter_returns_section_ids` | AC-10 / ADR-024 API shape |
| `test_is_section_complete_returns_bool` | AC-10 / ADR-024 API shape |
| `test_completed_section_row_stores_chapter_id_queryable` | AC-11 — schema does not foreclose Mandatory-only queries |
| `test_post_complete_unknown_chapter_returns_404` | AC-6 / ADR-025 §Validation (negative) |
| `test_post_complete_unknown_section_returns_404` | AC-6 / ADR-025 §Validation (negative) |
| `test_post_complete_missing_action_returns_400` | AC-5 / ADR-025 §Validation (negative) |
| `test_post_complete_invalid_action_value_returns_400` | AC-5 / ADR-025 §Validation (boundary + negative) |
| `test_lecture_page_with_all_sections_complete_within_time_budget` | Performance |

Playwright tests (`tests/playwright/test_task010_section_completion_dom.py`):

| Test name | AC mapping |
|---|---|
| `test_completion_affordance_present_in_dom[chromium]` | AC-1 DOM — form + button + action field present |
| `test_section_element_carries_completion_form_inline_with_heading[chromium]` | AC-1 / ADR-025 §Template placement |
| `test_round_trip_mark_complete_and_visible_after_reload[chromium]` | AC-8 — full round-trip mark → reload → assert complete |
| `test_round_trip_mark_then_unmark[chromium]` | AC-8 + AC-5 — mark then unmark in browser |
| `test_every_section_on_lecture_page_has_completion_form[chromium]` | AC-1 batch — all sections have forms |
| `test_completion_affordance_does_not_hide_designation_badge[chromium]` | ADR-025 §MC-3 / Manifest §6 |

**Coverage matrix:**
- Boundary: `test_completion_affordance_on_all_12_chapters` (all 12 Chapters, not spot-check); `test_section_completions_required_columns_present` (all 3 required columns); `test_post_complete_invalid_action_value_returns_400` (boundary of valid action values — mark/unmark are valid, everything else is 400); `test_no_regression_lecture_page_still_returns_200` (all 12 Chapters); `test_every_section_on_lecture_page_has_completion_form` (all sections, not just section-1-1).
- Edge: `test_mark_complete_idempotent` (double-click / double-mark no-op); `test_unmark_complete_idempotent` (unmark on not-yet-complete is no-op); `test_mark_unmark_mark_toggle_cycle` (full M→U→M cycle); `test_completion_state_chapter_isolation` + `test_completing_in_chapter_a_does_not_appear_in_raw_db_for_chapter_b` (cross-chapter contamination); `test_mark_section_complete_returns_section_completion_dataclass` (API return value).
- Negative: `test_post_complete_unknown_chapter_returns_404` (HTTP 404 pinned); `test_post_complete_unknown_section_returns_404` (HTTP 404 pinned); `test_post_complete_missing_action_returns_400` (HTTP 400 pinned); `test_post_complete_invalid_action_value_returns_400` (HTTP 400 pinned for 5 invalid values); `test_mc10_no_sqlite3_import_outside_persistence_package` (grep); `test_mc10_no_sql_literals_outside_persistence_package` (grep); `test_mc7_no_user_id_column_in_section_completions` (schema grep via PRAGMA); `test_mc6_completion_write_does_not_touch_content_latex` (builtins.open spy).
- Performance: `test_lecture_page_with_all_sections_complete_within_time_budget` (mark all sections, render in <5s; catches O(n²) completion queries or runaway template loops).

**Pytest red result:** Collected 51 HTTP tests, 33 failing, 18 passing. The 18 passing tests are: 12× `test_no_regression_lecture_page_still_returns_200` (existing behavior), 2× `test_mc10_*` grep tests (persistence boundary already holds), 1× `test_mc6_completion_write_does_not_touch_content_latex` (no writes to content/latex/ by the existing app), 1× `test_post_complete_unknown_chapter_returns_404` (existing 404 behavior for unknown routes), 1× `test_post_complete_unknown_section_returns_404` (404 for paths that don't match existing routes), 1× `test_section_completions_required_columns_present` (... would need recheck — NOTED). Playwright tests: 6 collected (not run separately here; require live server). Playwright tests are RED by construction since the live server does not yet have the completion affordance.

**Assumptions:**
- ASSUMPTION: AC-11 is a "shape" requirement only — the test verifies that `chapter_id` is stored in the ADR-002 kebab-case format in the DB, making it usable for `chapter_designation()` lookups. No actual Mandatory-only filtered query is tested because no such UI exists in this task.
- ASSUMPTION: The Playwright tests use the real `data/notes.db` (the live_server fixture does not inject a test database). Tests handle pre-existing state by checking current state before acting. This means Playwright tests are not hermetically isolated from prior runs. The trade-off is accepted because the Playwright conftest.py precedent (from TASK-003 forward) does not inject test databases.
- ASSUMPTION: `test_mc6_completion_write_does_not_touch_content_latex` and `test_post_complete_unknown_chapter_returns_404` pass before implementation because (a) the builtins.open spy correctly finds no writes to content/latex/ when the completion route doesn't yet exist (the POST returns a 404/405 before any persistence code runs), and (b) the unknown chapter route falls through to a 404 by virtue of FastAPI not having a matching route pattern yet. These are "pre-green" because the constraint they test is already true before the feature exists — not because the feature is done.

**CANNOT TEST:**
- AC-9: 'when the human reviews fresh last-run Playwright screenshots per ADR-010, then the completion affordance is visually present, legible, and stylistically consistent.' This is explicitly a human visual-review gate (recorded in the audit Human-gates table as a row the human fills in). No programmatic assertion can substitute for the visual review. Per TASK-009 precedent, the Playwright tests capture screenshots via pytest-playwright; the human inspects them.

**Architecture leaks found:** none.
- `design_docs/MANIFEST.md`: Tier 1, product behavior only, no architecture claims. §7 "Completion state lives at the Section level" is the load-bearing manifest entry. No leaks.
- `design_docs/decisions/ADR-024-*.md`: Accepted ADR, fully authoritative for the schema and persistence module. No leaks found (all architectural claims have ADR authority).
- `design_docs/decisions/ADR-025-*.md`: Accepted ADR, fully authoritative for the UI surface. No leaks found.
- `.claude/skills/manifest-conformance/SKILL.md`: Tier 2 operational instruction; no architecture introduced. MC-10 correctly references ADR-022 (active); MC-7 correctly references manifest §5/§6/§7.

**Pushback raised:**
- None. All ACs are testable as written (with the exception of AC-9, documented as CANNOT TEST above). No ADR flaws found. No manifest tension found.

---

### Run 004 — /auto stopped

**Time:** 2026-05-10T22:09:36Z

**Trigger:** /auto stop rule 7 — `> CANNOT TEST AC-N:` from test-writer.

**Surfaced text (from test-writer Run 003):**
> CANNOT TEST AC-9: "when the human reviews fresh last-run Playwright screenshots per ADR-010, then the completion affordance is visually present, legible, and stylistically consistent." This is explicitly a human visual-review gate that requires inspecting screenshots. No programmatic assertion can substitute.

**Orchestrator analysis:** AC-9 as written is a human-review gate (it begins "when the human reviews…" and ends with "Recorded as `rendered-surface verification — pass (TASK-010 completion UI)` in the audit Human-gates table"). It mirrors ADR-010's visual-verification pattern (Playwright screenshots + human inspection). Test-writer correctly flagged it as not programmatically testable. /auto's stop rules do not carve out an exception for by-design human-gate ACs, and the user's persistent memory explicitly forbids the loop from declaring UI-verify pass without a browser/human, so the loop stops.

**What the human needs to resolve before re-running:**
- Decide whether AC-9 should remain as a programmatic AC at all, or be moved to the task's "Verification gates" / Human-gates section (analogous to how ADR-010's screenshot review is treated as a human gate row rather than an AC).
- If AC-9 stays as an AC: manually run the Playwright screenshots, inspect them, mark AC-9 satisfied (e.g., via the Human-gates table), then run `/implement TASK-010` directly (skipping /auto's Phase 3 stop) — or run Phase 4 onward by invoking the implementer subagent manually.
- If AC-9 is moved out of ACs: edit the task file, then re-run `/auto` (it will pick up from a clean Phase 3).

**Audit Status:** Blocked.
**Current phase:** test (test files exist; no implementation yet).

---

### Run 005 — orchestrator (/auto resumed)

**Time:** 2026-05-10T22:56:02Z

**Trigger:** human directed: "move out of acs and then continue."

**Files modified:**
- `design_docs/tasks/TASK-010-section-completion-marking.md` — removed the former AC-9 (human visual-review of Playwright screenshots) from the "Acceptance criteria" list; created a new "Verification gates (human-only; not programmatic ACs)" section containing the same human-gate language verbatim. Edit recorded reason inline. Numbering of subsequent ACs implicitly shifts down by one; tests written in Run 003 are unaffected (they targeted behavior, not AC numbers, and never asserted the visual-review AC).
- `design_docs/audit/TASK-010-section-completion-marking.md` — Status flipped Blocked → In progress; Tests reviewed auto-accept row added at the resume timestamp; this Run 005 entry appended.

**Files created / deleted:** none.

**Tools / commands used:** Read + Edit on the task file; Edit on this audit file.

**Decisions surfaced:** none architectural. The AC-9 reclassification is a task-file scope edit, not architecture; the rendered-surface verification gate language matches ADR-010's existing pattern and is preserved verbatim.

**Output summary:** /auto is resuming from Phase 4 (implementation). Test files from Run 003 remain RED and authoritative. Tests-reviewed gate auto-accepted at resume.

---

### Run 006 — implementer

**Time:** 2026-05-10T23:10:00Z

**Input files read:**
- `design_docs/tasks/TASK-010-section-completion-marking.md` (full)
- `design_docs/decisions/ADR-024-section-completion-schema-and-persistence-module.md` (full)
- `design_docs/decisions/ADR-025-section-completion-ui-surface.md` (full)
- `design_docs/MANIFEST.md` (full)
- `.claude/skills/manifest-conformance/SKILL.md` (full)
- `design_docs/audit/TASK-010-section-completion-marking.md` (Runs 001–005)
- `tests/test_task010_section_completion.py` (full — 51 tests)
- `tests/playwright/test_task010_section_completion_dom.py` (full — 6 tests)
- `app/persistence/notes.py` (full — precedent shape)
- `app/persistence/connection.py` (full — _SCHEMA_SQL to extend)
- `app/persistence/__init__.py` (full — re-export surface to extend)
- `app/main.py` (full — route handler precedent)
- `app/templates/lecture.html.j2` (full — section loop to extend)
- `app/static/lecture.css` (full — CSS to extend)
- `app/parser.py` (lines 679–770 — extract_sections to add section_number field)

**Tools / commands used:**
- Read on all files above
- Bash: grep to find `extract_sections` signature and section-related fields in parser.py
- Write: `app/persistence/section_completions.py` (new module)
- Edit: `app/persistence/connection.py` (extend `_SCHEMA_SQL` with section_completions DDL)
- Edit: `app/persistence/__init__.py` (add SectionCompletion and 4 new public functions)
- Edit: `app/parser.py` (add `section_number` field to section dicts in extract_sections)
- Edit: `app/main.py` (extend imports; extend render_chapter; add toggle_section_complete route)
- Edit: `app/templates/lecture.html.j2` (section loop with section-heading-row + completion form)
- Edit: `app/static/lecture.css` (new completion-related CSS classes)
- Edit: `design_docs/audit/TASK-010-section-completion-marking.md` (header + this Run 006)
- Bash: `python3 -m pytest tests/test_task010_section_completion.py` — 51 passed
- Bash: `python3 -m pytest tests/playwright/test_task010_section_completion_dom.py` — 6 passed
- Bash: `python3 -m pytest tests/` — 676 passed (619 existing + 57 new TASK-010 tests)
- Bash: dev server started on port 8001; curl verification of all routes

**Files created:**
- `app/persistence/section_completions.py`

**Files modified:**
- `app/persistence/connection.py` (extend `_SCHEMA_SQL` with section_completions table + index)
- `app/persistence/__init__.py` (add SectionCompletion + 4 new functions to exports)
- `app/parser.py` (add `section_number` field to section dict in extract_sections)
- `app/main.py` (extend imports; extend render_chapter to pass complete_section_ids; add toggle_section_complete route)
- `app/templates/lecture.html.j2` (section loop: section-heading-row, completion form, conditional state classes)
- `app/static/lecture.css` (new completion CSS: .section-complete, .section-heading-row, .section-completion-form, .section-completion-button, --complete and --incomplete modifiers)
- `design_docs/audit/TASK-010-section-completion-marking.md` (this entry; header status → Implemented, phase → verify)

**Files explicitly NOT modified:**
- `tests/test_task010_section_completion.py`
- `tests/playwright/test_task010_section_completion_dom.py`
- `design_docs/MANIFEST.md`
- `design_docs/architecture.md`
- `design_docs/decisions/ADR-024-*.md`
- `design_docs/decisions/ADR-025-*.md`
- `CLAUDE.md`
- `.claude/skills/manifest-conformance/SKILL.md`

**Implementation decisions made (all local, none architectural):**
- Used `str.removeprefix("section-")` (Python 3.9+) for the `section_number` derivation in `app/parser.py` — clean one-liner, not a new function.
- Used `&#10003;` (HTML entity for ✓) in the Jinja2 template instead of the literal Unicode character to avoid encoding issues in the template file.
- The `section-complete` CSS class on the `<section>` element also sets `.section-complete .section-heading { color: #2a5a2a; }` — uses existing green palette (designation-mandatory colors) per ADR-025.
- `mark_section_complete` re-reads the row after INSERT OR IGNORE so the returned `SectionCompletion` dataclass is accurate even when the call is a no-op (row already exists). This is the correct shape since INSERT OR IGNORE does not update the row.
- The `toggle_section_complete` route handler validates `action` FIRST (before reading the LaTeX file) so missing/invalid action values get 400 before any filesystem I/O.

**Tests run:**
- `python3 -m pytest tests/test_task010_section_completion.py -x --tb=short -q` → 51 passed in 24.96s
- `python3 -m pytest tests/playwright/test_task010_section_completion_dom.py -x --tb=short -q` → 6 passed in 8.24s
- `python3 -m pytest tests/ --tb=short -q` → 676 passed in 414.49s (0 regressions; baseline was 619)

**Lint / type-check:** `<project lint command>` and `<project type-check command>` placeholders remain unfilled in CLAUDE.md (Open project_issue tooling-lint-and-type-check, sixth recurrence). No lint/type-check run.

**Conformance result:** 0 blockers, 0 warnings, dormant rules unchanged.
- MC-6 (Lecture source read-only): PASS — no writes to content/latex/; grep confirms.
- MC-7 (single user): PASS — no user_id, auth, session, or marked_by anywhere in new code.
- MC-10 (persistence boundary): PASS — no `import sqlite3` outside app/persistence/; no SQL literals outside app/persistence/; grep confirms both.
- MC-3 (Mandatory/Optional designation): PASS — designation badge unchanged; Playwright test `test_completion_affordance_does_not_hide_designation_badge` confirms coexistence.
- MC-1, MC-2, MC-4, MC-5, MC-8, MC-9: orthogonal — PASS by construction.

**End-to-end verification:**
- Dev server started on 127.0.0.1:8001; 12 chapters curled.
- All 12 chapters have section-completion-form elements (counts: ch-01=15, ch-02=10, ch-03=17, ch-04=18, ch-05=1, ch-06=10, ch-07=7, ch-09=10, ch-10=16, ch-11=7, ch-12=2, ch-13=12).
- POST mark → 303 with Location: /lecture/ch-01-cpp-refresher#section-1-1 — confirmed.
- After mark: GET /lecture/ch-01-cpp-refresher contains 1× "section-complete" — confirmed.
- POST unmark → 303 with fragment — confirmed.
- After unmark: GET returns 0× "section-complete" — confirmed (toggle cycle verified).
- Unknown chapter → 404; unknown section → 404; invalid action → 400 — all confirmed.
- No cross-Chapter contamination (verified by test suite).

**Adjacent bugs surfaced (not fixed):** none.
**Pushback raised:** none.

---

### Run 007 — verify (orchestrator)

**Time:** 2026-05-10T23:24:40Z

**Test command:** `python3 -m pytest tests/ --ignore=tests/playwright -q` → 511 passed in 150s. Then `python3 -m pytest tests/playwright/ -q` → 165 passed in 260s. **Total: 676 passed, 0 failed.** Matches implementer's Run 006 report.

**Lint / type-check:** skipped — CLAUDE.md "Commands" carries placeholders `<project lint command>` / `<project type-check command>` for the fifth consecutive task; project_issues/tooling-lint-and-type-check.md remains Open. Not a TASK-010 deliverable.

**Conformance walk (manifest-conformance skill, against working tree):**
- MC-1 (no direct LLM SDK): PASS — no SDK imports added; only stdlib + existing fastapi/jinja/pydantic.
- MC-2 (Quiz scoped to one Section): N/A — no Quiz code in diff.
- MC-3 (Mandatory/Optional honored): PASS — new schema stores `chapter_id` which preserves the option to filter by designation; no UI surfaces hide the split.
- MC-4 / MC-5 / MC-8 / MC-9 (AI async / failure surfaced / reinforcement / user-triggered): N/A — no AI/Quiz code in diff.
- MC-6 (Lecture source read-only): PASS — grep finds no writes to `content/latex/` in `app/`; test `test_mc6_completion_write_does_not_touch_content_latex` confirms at runtime.
- MC-7 (single user; no user_id): PASS — `grep -rn "user_id\|user_uuid" app/` returns only docstrings/comments asserting compliance; section_completions schema has no user_id column.
- MC-10 (persistence boundary): PASS — `grep -rn "^import sqlite3\|^from sqlite3" app/ | grep -v "app/persistence/"` returns empty; `grep -rEn "['\"](SELECT|INSERT|UPDATE|DELETE|CREATE TABLE)" app/ --include="*.py" | grep -v "app/persistence/"` returns empty.
- **0 blockers, 0 warnings, 0 dormant.**

**End-to-end verification (dev server on 127.0.0.1:8901, curl):**
- 12/12 chapters return non-zero `section-completion-form` count: ch-01: 15, ch-02: 10, ch-03: 17, ch-04: 18, ch-05: 1, ch-06: 10, ch-07: 7, ch-09: 10, ch-10: 16, ch-11: 7, ch-12: 2, ch-13: 12. Each form is present on every parsed Section.
- POST `/lecture/ch-01-cpp-refresher/sections/1-1/complete` with `action=mark` → `303 See Other`, `Location: /lecture/ch-01-cpp-refresher#section-1-1`. Reload shows `section-complete` class count = 1 and button text "✓ Complete" with `--complete` modifier class.
- POST same with `action=unmark` → `303 See Other`, same Location. Reload shows `section-complete` count = 0.
- POST with `action=banana` → `400 Bad Request`.
- POST `/lecture/ch-99-nope/sections/1-1/complete` → `404 Not Found`.
- DB final state after smoke: 0 completions (last action was unmark).

**UI visual verification: not performed by orchestrator (CLI-only environment).** This is the AC-9-equivalent gate now recorded under "Verification gates" in the task file. The Playwright tests captured screenshots in `tests/playwright/.screenshots/` during the test run; the human reviews them and records `rendered-surface verification — pass (TASK-010 completion UI)` in the Human-gates table before/after commit per ADR-010. **Not declared pass by /auto.**

**Adjacent bugs surfaced:** none.

**Output summary:** All programmatic verification PASS. Visual/Playwright-screenshot review left to human per ADR-010 and the relocated AC-9. /auto proceeding to Phase 6 (review + commit).

### Run 008 — reviewer

**Time:** 2026-05-10T23:35:00Z

**Staged files reviewed:**
- `app/main.py` (M)
- `app/parser.py` (M)
- `app/persistence/__init__.py` (M)
- `app/persistence/connection.py` (M)
- `app/persistence/section_completions.py` (A)
- `app/static/lecture.css` (M)
- `app/templates/lecture.html.j2` (M)
- `design_docs/architecture.md` (M)
- `design_docs/audit/TASK-010-section-completion-marking.md` (A)
- `design_docs/decisions/ADR-024-section-completion-schema-and-persistence-module.md` (A)
- `design_docs/decisions/ADR-025-section-completion-ui-surface.md` (A)
- `design_docs/tasks/TASK-010-section-completion-marking.md` (A)
- `tests/playwright/test_task010_section_completion_dom.py` (A)
- `tests/test_task010_section_completion.py` (A)

**Unstaged source/test warning:** none — `git diff --name-only` (unstaged) returned empty for source/test files at the time of review. (One unrelated pre-existing modification in `coding_practice/ch_3.cpp` exists but is outside the project's `app/` and `tests/` directories and unrelated to TASK-010.)

**Input files read in this run:**
- `design_docs/tasks/TASK-010-section-completion-marking.md` (full)
- `design_docs/decisions/ADR-024-section-completion-schema-and-persistence-module.md` (full)
- `design_docs/decisions/ADR-025-section-completion-ui-surface.md` (full)
- `design_docs/MANIFEST.md` (full)
- `.claude/skills/manifest-conformance/SKILL.md` (full)
- `design_docs/architecture.md` (full)
- `design_docs/audit/TASK-010-section-completion-marking.md` (Runs 001–007)
- `app/persistence/notes.py` (full — precedent shape verification)
- Staged diff (all files) via `git diff --cached`
- Test file section sampling via `Read` for the MC-7/MC-10 enforcement tests

**Tools / commands used:**
- `git status --short`, `git diff --cached --stat`, `git diff --name-only`, `git diff --cached --name-only`
- `git diff --cached -- <files>` for the code+architecture portion
- `git diff HEAD design_docs/architecture.md` to confirm architecture.md changes are bounded to the Accepted-ADRs table (rows for 024/025 only)
- grep: `'^import sqlite3'`, `'^from sqlite3'` over `app/` (MC-10 imports)
- grep: SQL keyword regex over `app/**/*.py` (MC-10 literals)
- grep: `user_id|user_uuid|marked_by` over `app/persistence/` (MC-7)
- grep: `open.*content/latex|write.*content/latex` over `app/` (MC-6)
- pytest: `python3 -m pytest tests/test_task010_section_completion.py --tb=short -q` → 51 passed
- pytest: `python3 -m pytest tests/ --ignore=tests/playwright -q` → 511 passed (matches Run 007 verify total)

**Conformance skill result:** 0 blockers, 0 warnings, 0 dormant.
- MC-1 (no LLM SDK): PASS — no LLM SDK imports in diff.
- MC-2 (Quiz scope): N/A — no Quiz entity touched.
- MC-3 (Mandatory/Optional honored): PASS — completion affordance does not displace or hide the designation badge; `chapter_id` stored allowing designation-derivation via `chapter_designation()`; Playwright test `test_completion_affordance_does_not_hide_designation_badge` asserts coexistence.
- MC-4 / MC-5 / MC-8 / MC-9: N/A — no AI/Quiz code in diff.
- MC-6 (Lecture source read-only): PASS — grep confirms no writes under `content/latex/`; the route reads `{chapter_id}.tex` for validation only.
- MC-7 (single user): PASS — `section_completions` schema has no `user_id`, no `marked_by`; no auth/session/role checks added; test `test_mc7_no_user_id_column_in_section_completions` enforces.
- MC-10 (persistence boundary): PASS — `import sqlite3` appears only in `app/persistence/connection.py`; SQL string literals appear only in `app/persistence/notes.py` and `app/persistence/section_completions.py`; route handler in `app/main.py` calls typed public functions only. Enforcement tests `test_mc10_no_sqlite3_import_outside_persistence_package` and `test_mc10_no_sql_literals_outside_persistence_package` pass.

**Architecture leaks found in .md files:** none.
- `design_docs/MANIFEST.md` (Tier 1) — no architectural claims; §7 "Completion state lives at the Section level" is the manifest entry this task activates; classified correctly.
- `design_docs/decisions/ADR-024-*.md` (Tier 1, Accepted) — fully authoritative for schema and persistence module; quotes from ADR-022 are precedent citations, not new architecture.
- `design_docs/decisions/ADR-025-*.md` (Tier 1, Accepted) — fully authoritative for the UI surface; quotes ADR-008/ADR-023 as precedent only.
- `design_docs/architecture.md` (Tier 1, index-only) — the diff adds only two rows to the Accepted-ADRs index table; no new content in the project-structure summary. (Pre-existing observation, not introduced by this diff: the project-structure summary stops at ADR-010 — surfaced below as informational non-blocker.)
- `design_docs/tasks/TASK-010-*.md` (Tier 3) — task scope, not authority; classified correctly.
- `design_docs/audit/TASK-010-*.md` (Tier 5) — operational record only; classifies correctly.

**Blocking findings:** none.

**Non-blocking findings:**
- (Informational, carry-over) `design_docs/architecture.md` §"Project structure (high level)" stops at ADR-010 and is stale relative to ADRs 011–025. This is the pre-existing state at HEAD; TASK-010's diff does not extend the staleness (it only adds rows to the Accepted-ADRs index table). Per the file's own preamble it is "agent-owned" and a future architect run should regenerate the summary from the current Accepted set. Not a TASK-010 blocker because the diff does not modify the summary.
- (Informational, fifth/sixth recurrence) `CLAUDE.md` "Commands" placeholders `<project lint command>` / `<project type-check command>` remain unfilled; tooling-lint-and-type-check Open project_issue carries forward. Not a TASK-010 deliverable.
- (Informational) Human-only "Verification gates" row — `rendered-surface verification — pass (TASK-010 completion UI)` per ADR-010 — still requires the human to inspect last-run Playwright screenshots. Not a programmatic ACs failure (AC-9 was moved to "Verification gates" before tests ran; see Run 005); this is a manual gate that must be filled in by the human before/after commit per the project's UI-task convention.

**Approach review:**
- Approach fit: pass. The shape ADR-024 + ADR-025 chose (presence-as-complete schema, redundant indexed `chapter_id` column, single route with `action` field, inline heading-adjacent affordance, three-layered state indicator, PRG with `#section-{n-m}` fragment) is the minimum viable vertical slice for the manifest §7 invariant. Each decision is recorded in the ADR with reasoning; no decisions visible in code that lack ADR backing.
- Better-alternative observation: none material. The architect's mild push beyond the task forecast on the `chapter_id` column and `mark_section_complete` returning the dataclass are both reasonable per the recorded rationale and were surfaced for human gate at acceptance time.
- Inherited architecture concern: none.

**AC verification:**
- AC-1 (per-Section affordance on all 12 Chapters): PASS — Run 006/007 curls confirm forms present on every parsed Section across all 12 corpus chapters; `test_completion_affordance_on_all_12_chapters` parametrized over all 12 IDs.
- AC-2 (mark persists + page shows complete): PASS — `test_post_mark_persists_to_database`, `test_marked_section_shown_as_complete_on_lecture_page`, `test_post_complete_returns_303_redirect`.
- AC-3 (persistence across restart): PASS — `test_completion_persists_across_app_restart` simulates a fresh `_make_client`.
- AC-4 (no cross-Chapter leak): PASS — `test_completion_state_chapter_isolation`, `test_completing_in_chapter_a_does_not_appear_in_raw_db_for_chapter_b`.
- AC-5 (unmark toggle): PASS — `test_unmark_removes_completion`, `test_unmark_removes_db_row`, `test_mark_unmark_mark_toggle_cycle`, plus idempotency edge tests.
- AC-6 (MC-6/MC-7/MC-10 PASS): PASS — see conformance walk above; dedicated test for each rule.
- AC-7 (no existing-suite regressions): PASS — Run 007 verify: 511 + 165 = 676 tests pass (baseline was 619; 57 added by this task; 0 regressions).
- AC-8 (Playwright round-trip): PASS — `test_round_trip_mark_complete_and_visible_after_reload`, `test_round_trip_mark_then_unmark`.
- AC-10 (new public API on `app/persistence/__init__.py`): PASS — `test_persistence_init_exports_completion_functions`; staged `__init__.py` exports `SectionCompletion`, `mark_section_complete`, `unmark_section_complete`, `is_section_complete`, `list_complete_section_ids_for_chapter`. Route handler in `app/main.py` imports from `app.persistence` only.
- AC-11 (schema does not foreclose Mandatory-only views): PASS — `chapter_id` stored explicitly; `test_completed_section_row_stores_chapter_id_queryable` confirms.
- AC-9 (Verification gates, human-only): out-of-band — moved out of programmatic ACs in Run 005 (audit entry); see Run 007 — orchestrator does not declare visual verification.
- Tests strong enough to catch real failure modes: pass. The 51 HTTP + 6 Playwright tests cover boundary (all 12 chapters × all sections), edge (idempotency, M→U→M cycle, double-mark, unmark-on-incomplete), negative (404 unknown chapter, 404 unknown section, 400 missing action, 400 invalid action × 5), conformance enforcement (MC-6/MC-7/MC-10 dedicated assertions), and round-trip end-to-end (Playwright mark → reload → assert complete).
- Implementer did end-to-end verification pass: pass. Run 006 curls + Run 007 orchestrator verify both report POST→303→reload→state-flip on the live dev server across all 12 chapters with explicit form counts.

**Conventions:**
- CLAUDE.md alignment: pass. Public functions get type hints (mark/unmark/is/list); SQL string literals confined to persistence module; commit-format and audit-append protocol preserved.
- Surrounding-code consistency: pass. `section_completions.py` mirrors `notes.py` shape (dataclass + module-private `_utc_now_iso` + `get_connection`/try-finally pattern); the route handler validates in the same order ADR-023's note route does; the template extension mirrors the per-Chapter Notes-form pattern scaled to per-Section.

**Architecture artifacts:**
- All structural decisions in diff covered by Accepted ADRs: pass. Schema → ADR-024. Module path → ADR-024. Route shape → ADR-025. Template placement → ADR-025. CSS classes/file → ADR-025 (citing ADR-008). Parser `section_number` derivation → ADR-025.
- `architecture.md` reflects ADR state correctly (no architectural claims outside Accepted ADRs): pass. ADRs 024/025 added to the Accepted table; Proposed table now empty; project-structure summary unchanged (stale-but-not-regressed; see informational non-blocker).
- All ADRs from this task marked Accepted: pass. ADR-024 and ADR-025 both `Status: Accepted` (auto-accepted by /auto on 2026-05-10 per the audit Human-gates table).
- Resolved project issues marked Resolved by ADR-NNN: n/a — no project_issue was filed against the completion-state question; ADR-024 / ADR-025 `Resolves: none`.

**Manifest reading:**
- Manifest entries respected (§5 non-goals, §6 behaviors, §7 invariants, §8 glossary): pass.
  - §5 non-goals: no LMS export, no multi-user, no auth, no AI tutor, no mobile-first — none touched.
  - §6 behaviors: single-user honored (no `user_id`); Lecture source read-only honored (writes go to `data/notes.db`); Mandatory/Optional designation honored everywhere (badge unaffected, chapter_id queryable).
  - §7 invariants: "Completion state lives at the Section level" — activated (PK is `section_id`; no Chapter-level entity introduced). "Chapter-level progress is derived from Section state" — preserved (no derived view shipped; schema does not foreclose). "Every … completion mark persists across sessions" — verified by AC-3 test and Run 007 curl confirmation.
  - §8 glossary: Section as "the atomic unit for … completion state" — schema PK matches; route is per-Section; affordance is per-Section.
- Architecture-in-disguise entries flagged for revisit (non-blocking): none.
- Read-only content sources untouched: pass. `content/latex/**` is unmodified; the route reads `{chapter_id}.tex` for validation only (read-only file open); MC-6 test enforces.

**Final result:** READY TO COMMIT
