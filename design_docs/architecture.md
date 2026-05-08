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

Lecture source is a read-only LaTeX corpus under `content/latex/`, with one `.tex` file per Chapter (ADR-001); each Chapter ID is the file basename, and Section IDs are `{chapter_id}#section-{n-m}` derived from `\section{N.M ...}` numbering (ADR-002). A local FastAPI application parses one Chapter `.tex` at request time using `pylatexenc`, renders the structured intermediate representation through Jinja2, and serves it on `127.0.0.1` with no persistence layer (ADR-003). The Mandatory/Optional designation for any Chapter is computed by a single Python function whose threshold cites manifest §8, with no config file or sidecar (ADR-004). Navigation lives on a `GET /` landing page and on a left-hand rail included in every Lecture page via a shared base template, both surfaces rendering from one helper (ADR-006); that helper discovers Chapters by scanning `content/latex/` at request time, labels each row from the Chapter's `\title{...}` macro using the same extractor the Lecture page uses, and orders within each Mandatory/Optional group by parsed chapter number ascending (ADR-007).
