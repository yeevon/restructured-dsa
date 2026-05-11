# Restructured CS 300 — Architecture

This file is agent-owned (architect agent). Updates happen during task work. Humans review changes via PR/diff but do not edit by hand. To change a decision, supersede it via a new ADR.

This file is an index of Accepted ADRs only. It does not introduce architectural claims; if it disagrees with an Accepted ADR, the ADR wins.

## Accepted ADRs

| # | Title | Task | Date |
|---|---|---|---|
| 001 | Lecture source layout — LaTeX article files under `content/latex/` | TASK-001 | 2026-05-07 |
| 002 | Chapter and Section identity | TASK-001 | 2026-05-07 |
| 003 | Rendering pipeline for Chapter 1 — Python parser to static HTML, served by local FastAPI | TASK-001 | 2026-05-07 |
| 004 | Mandatory/Optional designation source — manifest-derived rule, encoded in a single Python module | TASK-001 | 2026-05-07 |
| 005 | Chapter source file naming — single canonical form `ch-{NN}-{slug}` (Form A only) | TASK-002 | 2026-05-08 |
| 006 | Navigation surface — `GET /` landing page that also serves as a left-hand rail include in every Lecture page | TASK-002 | 2026-05-08 |
| 007 | Chapter discovery, display label, and within-group ordering | TASK-002 | 2026-05-08 |
| 008 | Navigation styling layer — split into `app/static/base.css` (page chrome + rail) and reuse the existing `app/static/lecture.css` (Lecture body), with M/O reusing the established designation palette and CSS Grid for the page layout | TASK-003 | 2026-05-08 |
| 010 | UI verification mechanism — Playwright (via `pytest-playwright`) as the project's UI test framework, with last-run screenshot artifacts gitignored | TASK-003 | 2026-05-08 |
| 011 | Tabular column spec handling — strip from rendered output, warn-per-node for complex spec features | TASK-004 | 2026-05-08 |
| 012 | Callout title rendering — extract optional `[Title]` argument and emit as `<div class="callout-title">` inside callout div | TASK-004 | 2026-05-08 |
| 013 | Multi-chapter validation harness — split Playwright (visual) and HTTP-protocol pytest (smoke) | TASK-005 | 2026-05-08 |
| 014 | Strip the `\\` linebreak macro from title extraction (resolves linebreak-passthrough project_issue) | TASK-005 | 2026-05-08 |
| 015 | Multi-chapter validation pass routes bugs by class — LaTeX/parser fold-in; rail/CSS escalate to own task; else file as project_issue | TASK-005 | 2026-05-08 |
| 016 | Orchestrator verifies subagent file outputs after every phase via `git diff`; remediates mechanical gaps directly | TASK-006 | 2026-05-08 |
| 017 | Tabular column-spec stripping — implementation contract for ADR-011 (balanced-brace consumption) | TASK-007 | 2026-05-09 |
| 018 | Render `\texttt{}` as `<span class="texttt">` so MathJax processes embedded inline math | TASK-007 | 2026-05-09 |
| 019 | Unhandled-environment rendering strategy — generic consume-and-skip fallback (no per-env editorial commitments) | TASK-008 | 2026-05-10 |
| 020 | Defensive macro-stripping pass in raw-text fallback paths — text-formatting macros do not leak from `_escape(raw)` sites | TASK-008 | 2026-05-10 |
| 021 | Test assertion files are excluded from the orchestrator's direct-remediation authority granted by ADR-016 — test amendments require a test-writer re-invocation | (workflow refinement) | 2026-05-10 |
| 022 | Persistence layer — SQLite via stdlib `sqlite3`, `app/persistence/` package boundary, and the Note schema | TASK-009 | 2026-05-10 |
| 024 | Section completion schema and persistence module — `section_completions` table (presence ≡ complete) under `app/persistence/section_completions.py` | TASK-010 | 2026-05-10 |
| 026 | Chapter-level derived progress display — rail-resident "X / Y" decoration + bulk persistence accessor | TASK-011 | 2026-05-10 |
| 027 | Supersedure of ADR-025 §Template-placement — per-Section completion affordance moves to bottom-of-Section | TASK-011 | 2026-05-10 |
| 028 | Supersedure of ADR-023 §Template-surface — Notes section moves from bottom-of-page to rail-resident panel (§Rail-integration / §Template-surface portion since superseded by ADR-029; remaining decisions still in force) | TASK-011 | 2026-05-10 |
| 029 | Supersedure of ADR-028 §Rail-integration / §Template-surface — Notes panel moves from the left-hand rail to a right-hand rail in a three-column layout | TASK-012 | 2026-05-11 |
| 030 | Supersedure of ADR-025 §Round-trip-return-point — the section-completion 303 redirect drops the `#section-{n}` fragment so the toggle does not relocate the user (§Decision/no-fragment-mechanism portion since superseded by ADR-031; the load-bearing principle "the response to a reading-flow action should not relocate the user" and the ADR-025 bookkeeping remain in force) | TASK-012 | 2026-05-11 |
| 031 | Supersedure of ADR-030 §Decision — the section-completion 303 redirect anchors to a `#section-{n}-end` fragment on the `.section-end` wrapper, paired with a large `scroll-margin-top`, so the toggle lands the user ≈ where they clicked with no JavaScript | TASK-012 | 2026-05-11 |

## Proposed ADRs (awaiting human acceptance)

(none)

## Pending resolution (need human input)

(none)

## Superseded

| # | Title | Superseded by | Date |
|---|---|---|---|
| 023 | Notes creation/read surface — `POST /lecture/{chapter_id}/notes` form-encoded with PRG redirect, Notes section appended to `lecture.html.j2`, multi-Note list with empty-state caption | ADR-028 (§Template-surface only) | 2026-05-10 |
| 025 | Section completion UI surface — inline affordance next to each `<h2 class="section-heading">` | ADR-027 (§Template-placement only) | 2026-05-10 |
| 025 | Section completion UI surface — full-page PRG redirect with `#section-{n}` URL fragment | ADR-030 (§Round-trip-return-point only) | 2026-05-11 |
| 028 | Notes rail-resident panel — `<section class="rail-notes">` inside `_nav_rail.html.j2` (the left-hand rail) | ADR-029 (§Rail-integration / §Template-surface portion only) | 2026-05-11 |
| 030 | Section completion 303 redirect — drop the `#section-{n}` fragment / rely on Chromium preserving scroll on the fragment-less same-URL navigation (empirically refuted) | ADR-031 (§Decision / no-fragment mechanism only; ADR-030's principle retained) | 2026-05-11 |

## Project structure (high level)

*Derived from the current Accepted-ADR set (001–008, 010–022, 024, 026, 027, 028, 029, 030, 031; ADR-009 was never assigned; ADR-023 and ADR-025 are Superseded — ADR-023 §Template-surface by ADR-028, ADR-025 §Template-placement by ADR-027 and §Round-trip-return-point by ADR-030; ADR-028's §Rail-integration / §Template-surface portion is superseded by ADR-029, its remaining decisions still in force; ADR-030's §Decision / no-fragment mechanism is superseded by ADR-031, but ADR-030's load-bearing principle remains in force).*

**Source corpus and rendering pipeline.** Lecture source is a read-only LaTeX corpus under `content/latex/`, one `.tex` file per Chapter, basenames in the canonical form `ch-{NN}-{slug}` (ADR-001, ADR-005); each Chapter ID is the file basename, and Section IDs are `{chapter_id}#section-{n-m}` derived from `\section{N.M ...}` numbering (ADR-002). A local FastAPI application parses one Chapter `.tex` at request time using `pylatexenc`, renders the structured intermediate representation through Jinja2, and serves it on `127.0.0.1` (ADR-003); each Section dict carries a derived `section_number` field (the part after `section-` in the fragment) for route-URL composition (ADR-025). The Mandatory/Optional designation for any Chapter is computed by a single Python function whose threshold cites manifest §8, with no config file or sidecar (ADR-004).

**Parser fidelity rules.** Tabular column-spec arguments are stripped from rendered output via balanced-brace consumption, with warn-per-node for complex spec features (ADR-011, ADR-017); callout `[Title]` arguments are extracted and emitted as `<div class="callout-title">` inside the callout div (ADR-012); the `\\` linebreak macro is stripped from title extraction (ADR-014); `\texttt{}` renders as `<span class="texttt">` so MathJax processes embedded inline math (ADR-018); unhandled LaTeX environments use a generic consume-and-skip fallback with no per-environment editorial commitment (ADR-019); raw-text fallback paths run a defensive macro-stripping pass so text-formatting macros do not leak (ADR-020). Multi-chapter validation splits Playwright (visual) and HTTP-protocol pytest (smoke) (ADR-013); validation-pass bugs are routed by class — LaTeX/parser folded in, rail/CSS escalated to its own task, else filed as a project_issue (ADR-015).

**Navigation and page layout.** Navigation lives on a `GET /` landing page and on a left-hand rail included in every Lecture page via a shared `base.html.j2`, both surfaces rendering from one `discover_chapters()` helper (ADR-006); that helper discovers Chapters by scanning `content/latex/` at request time, labels each row from the Chapter's `\title{...}` macro using the same extractor the Lecture page uses, and orders within each Mandatory/Optional group by parsed chapter number ascending (ADR-007). Page-chrome and rail styling live in `app/static/base.css`, while Lecture-body styling stays in `app/static/lecture.css`; the two files are non-overlapping by class-name prefix (`page-*`, `nav-*`, `index-*`, `rail-*`, `lecture-rail` → `base.css`; `lecture-*`, `section-*`, `callout-*`, `designation-*` → `lecture.css`), both loaded flat from the base template (no preprocessor, no build step), the rail's Mandatory/Optional headings reuse the `designation-mandatory`/`designation-optional` palette the Lecture badge uses, and the page-level layout is a CSS Grid (ADR-008). The left rail carries a per-Chapter derived "X / Y" progress decoration on each chapter row, fed by a single bulk persistence accessor and clamped so X never exceeds Y (ADR-026).

**Persistence.** SQLite via the stdlib `sqlite3` module is the persistence layer; `app/persistence/` is the only package that talks to the database; the Note schema and the section-completion schema live there (ADR-022, ADR-024). Notes are bound to a Chapter and stored most-recent-first; section completion uses presence-as-complete semantics in a `section_completions` table under `app/persistence/section_completions.py` with write-time validation at the route handler (ADR-022, ADR-024).

**Notes surface.** Notes are created via `POST /lecture/{chapter_id}/notes` (form-encoded body, PRG 303 redirect to `GET /lecture/{chapter_id}`, no fragment), with route-handler validation (trim; reject empty/whitespace-only; reject unknown Chapter; reject bodies > 64 KiB); the Notes panel is rail-resident in a right-hand rail — `<section class="rail-notes">` lives in `_notes_rail.html.j2`, included by `base.html.j2` in the right-hand column of a three-column CSS Grid layout (LHS chapter rail | centered main | RHS Notes rail), `position: sticky`, with the grid degrading to two columns on `GET /` where no Chapter context exists; the panel is rendered only when a Chapter context exists (omitted from `GET /`), with a `rows="3"` textarea using CSS `field-sizing: content` plus `resize: vertical` fallback and no JavaScript; multiple Notes display most-recent-first; submit feedback is a full-page PRG reload; no edit/delete, no Markdown (ADR-023 §non-template-surface decisions, ADR-028, ADR-029). The bottom-of-page Notes section that ADR-023 originally placed in `lecture.html.j2` was removed by ADR-028; ADR-028 originally placed the rail-resident panel in `_nav_rail.html.j2` (the left-hand rail), which ADR-029 superseded.

**Section completion surface.** A per-Section completion toggle posts to `POST /lecture/{chapter_id}/sections/{section_number}/complete` with a form-encoded `action` field (`mark` | `unmark`), idempotent, with route-handler validation of `chapter_id`, `section_number`, and `action`, returning a `303 See Other` PRG redirect to `GET /lecture/{chapter_id}#section-{section_number}-end` — the fragment points at the `.section-end` wrapper (which carries `id="section-{n-m}-end"`), and `.section-end` carries a large viewport-relative `scroll-margin-top` in `lecture.css` so fragment navigation lands the wrapper near the bottom of the viewport ≈ where the user clicked, leaving the user where they were rather than relocating them (ADR-031, superseding ADR-030 §Decision; ADR-030 superseded ADR-025 §Round-trip-return-point's `#section-{n}` heading anchor; a Playwright regression test locks the post-toggle scroll-delta within ≤ 200px of the pre-click position); the affordance is a `<form>` inside that `<div class="section-end">` wrapper at the bottom of each `<section>` (ADR-027, superseding ADR-025 §Template-placement); a complete Section carries three layered indicators — button text, button-color modifier, and a `.section-complete` class on the `<section>` element; `GET /lecture/{chapter_id}` passes a `complete_section_ids` set to the template (ADR-024, ADR-025, ADR-027, ADR-030, ADR-031). No JavaScript; synchronous form posting throughout.

**Placement-quality principles** (encoded by the post-TASK-010/011/012 supersedures, binding on future surface placement): action affordances follow the cognitive sequence, not the template scope (ADR-027); visibility follows scroll-position-cost — a surface a user must scroll past the entire content to reach is, at scale, invisible (ADR-028; ADR-029 retains this principle and corrects its application to the rail with the real estate); and the response to a reading-flow action should not relocate the user — completion is an annotation on what was just read, not a navigation event (ADR-030's principle, implemented by ADR-031's `#section-{n}-end` anchor + `scroll-margin-top` mechanism after ADR-030's no-fragment mechanism was empirically refuted in Chromium).

**UI verification.** Rendered-behavior verification for any UI surface uses Playwright through the `pytest-playwright` plugin so all tests run under the single `python3 -m pytest tests/` command; rendered-DOM-content tests live under `tests/playwright/` while HTTP-protocol, source-static, and runtime-side-effect tests stay in pytest under `tests/`; the default browser is Chromium driven by a session-scoped `live_server` fixture against the local FastAPI app; per-test screenshots and on-failure traces from the last run are written to a single artifact directory under `tests/` that is excluded from version control; the verification gate is satisfied when the pytest run is green and the human reviews the last-run screenshots, recorded as a `rendered-surface verification — pass` row in the audit Human-gates table (ADR-010).

**Workflow infrastructure.** The orchestrator verifies each subagent's expected file outputs via `git diff` after every phase and remediates mechanical gaps directly, except test-assertion files which require a test-writer re-invocation (ADR-016, ADR-021).
