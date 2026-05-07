# Restructured CS 300 — Architecture

This file is agent-owned (architect agent). Updates happen during task work. Humans review changes via PR/diff but do not edit by hand. To change a decision, supersede it via a new ADR.

## Accepted ADRs

| # | Title | Task | Date |
|---|---|---|---|
| 000 | Baseline: import "Decisions already made" from CLAUDE.md | bootstrap | 2026-05-07 |

## Proposed ADRs (awaiting human acceptance)

| # | Title | Task |
|---|---|---|
| 001 | Chapter ID is derived from the LaTeX filename | TASK-001 |
| 002 | Section IDs are slugged from `\section{...}` headings, scoped within a Chapter, with deterministic collision suffixes | TASK-001 |
| 003 | Lecture parser produces an intermediate Chapter / Section model that both the HTML renderer and the future Script extractor consume | TASK-001 |
| 004 | Unrecognized LaTeX environments and commands render as visible passthrough blocks, never as silent drops | TASK-001 |
| 005 | Lecture Page route is `/chapters/{chapter_id}/lecture` with Section anchors as URL fragments | TASK-001 |

## Pending resolution (need human input)

(none)

## Superseded

(none)

## Project structure (high level)

The Lecture pipeline is a pure read-only chain: LaTeX source under `content/latex/` → `cs300.lecture.parse_chapter` (plasTeX-backed, returns a `Chapter` Pydantic model with structured `Section` / `Block` / `Inline` variants) → `cs300.lecture.render_html` (consumes the model, emits HTML via a Jinja2 template) → FastAPI route at `/chapters/{chapter_id}/lecture`. The intermediate `Chapter` model is the contract that lets the future Lecture Script extractor be a sibling renderer rather than a re-parse, satisfying the manifest's "Lecture Scripts are extracted from LaTeX, never from rendered HTML" constraint. Chapter id comes from the `.tex` filename; Section id comes from `\section{...}` heading slugs scoped per-Chapter. Mandatory/Optional designation is per-Chapter, derived from the numeric prefix of the Chapter id by a small pure function. No DB writes, no AI calls, no async work in this pipeline.
