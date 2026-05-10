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

## Proposed ADRs (awaiting human acceptance)

| # | Title | Task |
|---|---|---|

(none)

## Pending resolution (need human input)

(none)

## Superseded

| # | Title | Superseded by | Date |
|---|---|---|---|

(none)

## Project structure (high level)

Lecture source is a read-only LaTeX corpus under `content/latex/`, with one `.tex` file per Chapter (ADR-001); each Chapter ID is the file basename, and Section IDs are `{chapter_id}#section-{n-m}` derived from `\section{N.M ...}` numbering (ADR-002). A local FastAPI application parses one Chapter `.tex` at request time using `pylatexenc`, renders the structured intermediate representation through Jinja2, and serves it on `127.0.0.1` with no persistence layer (ADR-003). The Mandatory/Optional designation for any Chapter is computed by a single Python function whose threshold cites manifest §8, with no config file or sidecar (ADR-004). Navigation lives on a `GET /` landing page and on a left-hand rail included in every Lecture page via a shared base template, both surfaces rendering from one helper (ADR-006); that helper discovers Chapters by scanning `content/latex/` at request time, labels each row from the Chapter's `\title{...}` macro using the same extractor the Lecture page uses, and orders within each Mandatory/Optional group by parsed chapter number ascending (ADR-007). Page-chrome and rail styling live in a new `app/static/base.css`, while Lecture-body styling stays in the existing `app/static/lecture.css`; the two files are non-overlapping by class-name prefix, both are loaded flat from the base template (no preprocessor, no build step), the rail's Mandatory/Optional headings reuse the same `designation-mandatory`/`designation-optional` palette the Lecture badge already uses, and the page-level two-column layout is implemented with CSS Grid (ADR-008). Rendered-behavior verification for any UI surface uses Playwright through the `pytest-playwright` plugin so all tests run under the single `python3 -m pytest tests/` command; rendered-DOM-content tests live under `tests/playwright/` while HTTP-protocol, source-static, and runtime-side-effect tests stay in pytest under `tests/`; the default browser is Chromium driven by a session-scoped `live_server` fixture against the local FastAPI app; per-test screenshots and on-failure traces from the last run are written to a single artifact directory under `tests/` that is excluded from version control; the verification gate is satisfied when the pytest run is green and the human reviews the last-run screenshots, recorded as a `rendered-surface verification — pass` row in the audit Human-gates table (ADR-010).
