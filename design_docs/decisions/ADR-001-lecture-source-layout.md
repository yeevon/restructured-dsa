# ADR-001: Lecture source layout — LaTeX article files under `content/latex/`

**Status:** `Accepted`
**Date:** 2026-05-07
**Task:** TASK-001
**Resolves:** none (no project_issues filed against this question)

## Context

TASK-001 requires rendering Chapter 1 as a Lecture page from real curated content. The source for Chapter 1 already exists on disk at `content/latex/ch-01-cpp-refresher.tex`. Other chapter files (`ch2.tex` through `ch13.tex`, with `ch8.tex` absent) sit alongside it in the same directory. Manifest §6 establishes that "A Lecture has a single source" and that the application "does not modify the source." Manifest §5 forbids in-app authoring of lecture content. Manifest-conformance rule MC-6 grounds out on whatever path the source-layout ADR designates as the lecture source root; today that rule is dormant for path-specific checks because no ADR has named the root.

This ADR has to answer two coupled questions that TASK-001 cannot proceed without:

1. **Where on disk does Lecture source live?** (so MC-6's path-specific grep becomes evaluable, and so the renderer knows where to read from).
2. **What file format does the renderer read?** (so the rendering-pipeline ADR has a defined input).

Format-of-each-file matters because the existing Chapter 1 file is a complete `\documentclass{article}` LaTeX document that `\input{../../notes-style.tex}`s a styling preamble that is not lecture content (page colors, callout boxes, fonts). Treating the whole file as content would render styling commands as if they were prose; treating only the document body as content requires the renderer to know where the body begins. The ADR has to commit to one reading model so downstream agents do not silently invent one.

This ADR does *not* decide how the LaTeX is parsed, normalized, or transformed — that is ADR-003 (rendering pipeline). It only fixes the input contract.

## Decision

1. **The lecture source root is `content/latex/`** (path relative to the repository root). All Chapter source files live directly in this directory; no nested chapter subdirectories at this time.

2. **Each Chapter is a single self-contained LaTeX file** using `\documentclass{article}` and `\input`-ing the shared `notes-style.tex` preamble that lives at the repository root. The renderer treats the contents of `\begin{document} ... \end{document}` as the Lecture body for that Chapter; everything before `\begin{document}` is preamble that the renderer is free to ignore for content extraction (preamble-defined macros that *are* used in the body still need handling, but that is a parser concern, not a layout concern, and is owned by ADR-003).

3. **The lecture source root is read-only to the application.** Application code and rendering pipelines under this ADR's contract may open files under `content/latex/` for reading only. No path under `content/latex/` is ever opened for writing, created, deleted, or moved by application code.

4. **TASK-001 reads exactly one file: `content/latex/ch-01-cpp-refresher.tex`.** The presence of other chapter files in `content/latex/` is acknowledged but is out of scope for TASK-001. ADR-001 does not commit to how those other files are named, structured, or eventually rendered; that question is filed as a project issue (`design_docs/project_issues/multi-chapter-source-naming.md`).

5. **`notes-style.tex` is preamble, not content.** The renderer must not attempt to extract Lecture content from `notes-style.tex`. Whether the renderer parses the preamble at all is a parser-strategy question owned by ADR-003.

## Alternatives considered

**A. Convert LaTeX source to Markdown (or another lighter format) as the source of record.**
Rejected. The author has already invested in a LaTeX corpus with a custom styling preamble (callout boxes, code listings, math). Converting up-front would (a) be a content-migration project that competes with the manifest's primary objective for scope, and (b) violate the "single source" invariant the moment the LaTeX and Markdown disagree. Converting *as a derivation step* is fine — but that is what the rendering pipeline does (ADR-003), not what the source layout is.

**B. Keep LaTeX as the source but split each Chapter into per-Section files (e.g., `content/latex/ch-01/section-1.1.tex`).**
Rejected for TASK-001. The existing source is monolithic per Chapter, and the manifest's atomic unit for Lectures is the Chapter (manifest §8). Splitting at the Section level would force a content-reorganization commit before any rendering work happens — that is a content-management decision the user has not signaled, and TASK-001 can ship without it. Section addressability (acceptance criterion 2) is solved at the parser level by ADR-002, not by file-system layout.

**C. Move source out of the repo entirely (separate content repo, Git submodule, external store).**
Rejected. The source already lives in the repo and TASK-001 explicitly assumes its current location. Splitting it out introduces deployment and synchronization concerns that the manifest's "no remote deployment" non-goal (§5) makes pointless. If a future task surfaces a real need to decouple content from code, it can be raised as its own ADR.

## My recommendation vs the user's apparent preference

The task file (TASK-001) and the existing on-disk layout both point at "LaTeX files under `content/latex/`." There is no apparent user preference to override here; this ADR ratifies the existing state and writes down the contract that until now was implicit. No pushback raised.

## Manifest reading

Read as binding for this decision:
- §5 Non-Goals: "No in-app authoring of lecture content. Lecture source is edited outside the application; the application reads it, never writes it." — Bound the read-only rule.
- §6 Behaviors and Absolutes: "A Lecture has a single source." — Bound the "one Chapter, one source file" shape; ADR-001 honors it by treating one `.tex` file as the canonical source for one Chapter.
- §8 Glossary: "Chapter — A top-level unit of curriculum content. The atomic unit for Lectures and Notes." — Bound the per-Chapter file granularity.

No manifest entries flagged as architecture-in-disguise.

## Conformance check

- **MC-6 (Lecture source is read-only to the application).** The manifest portion is already active. Once this ADR is Accepted, the architecture portion (path-specific grep) becomes evaluable: the path is `content/latex/`. The pre-commit hook can grep for write operations against that prefix. Compliance: this ADR forbids any write to `content/latex/` from application code; tests and the conformance skill enforce.
- **MC-3 (Mandatory/Optional designation respects the canonical mapping).** The path layout deliberately does *not* encode Mandatory/Optional in directory structure (no `mandatory/` vs `optional/` subdirectories). That keeps MC-3's data-source decision orthogonal — owned by ADR-004 — instead of leaking into the filesystem. ADR-001 does not constrain ADR-004.
- No other MC rules are touched by this decision.

Previously dormant rule activated by this ADR (once Accepted): MC-6's path-specific grep against `content/latex/`.

## Consequences

**Becomes possible:**
- A grep-able conformance check against `content/latex/` for write operations.
- Downstream ADR-003 (rendering pipeline) has a fixed input contract: read one `.tex` file from `content/latex/` and produce a Lecture surface.
- Adding a new Chapter is a single-file operation outside the application — consistent with manifest §5.

**Becomes more expensive:**
- A future move to per-Section source files requires a new ADR that supersedes this one and a content-migration step. That cost is accepted as the price of *not* doing it speculatively now.
- Renaming the source root requires a coordinated supersedure of this ADR plus an update to the conformance skill's MC-6 grep target. (Acceptable; the manifest is stable, the path is not.)

**Becomes impossible (under this ADR):**
- Application-code write paths to `content/latex/`. Any code that needs to "regenerate" lecture source has to do so outside the application boundary, in a tool the user runs by hand.

**Out of scope for this ADR (deferred):**
- How LaTeX is parsed (ADR-003).
- How Sections within a Chapter are identified (ADR-002).
- Where the Chapter → Mandatory|Optional mapping lives (ADR-004).
- Naming convention for chapter files beyond Chapter 1 (filed as project issue).
