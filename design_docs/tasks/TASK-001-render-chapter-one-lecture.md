# TASK-001: Render Chapter 1 as a viewable Lecture page

**Manifest sections this touches:** §3 Primary Objective (drives consumption of curated curriculum), §5 Non-Goals (no in-app authoring, no remote deployment), §6 Behaviors and Absolutes ("A Lecture has a single source"; Mandatory/Optional honored everywhere), §7 Invariants (Lectures scope to Chapters; Mandatory/Optional separable in every learner-facing surface), §8 Glossary (Chapter, Section, Lecture, Mandatory).
**Architecture state assumed:** None. This is TASK-001; no ADRs exist. Every architectural decision this task requires must be drafted during `/design`.
**Project issues this forces:** none currently filed (the project_issues directory is empty). New project_issues files will be created in Mode 2 if questions surface that this task does NOT need to resolve.

## What and why

Build a single, viewable Lecture page for Chapter 1 (the "C++ Refresher" content already on disk at `content/latex/ch-01-cpp-refresher.tex`) so the human can open a browser (or equivalent local viewer) and read Chapter 1 as a structured Lecture, with its Sections navigable and the Chapter's Mandatory designation clearly indicated.

This is the smallest vertical slice that advances the manifest's primary objective: it produces a real learner-facing surface — a Lecture for a Chapter — from real curated content. It establishes the spine on which Sections (and therefore Quiz attachment points), Notes, and consumption modes are later hung, without committing to any of those yet.

The task deliberately stops short of: any Quiz mechanics, any Notes mechanics, any AI work, any persistence beyond what's needed to render, any second consumption mode (audio), any second Chapter, and any Mandatory-only filter UI. Those are later tasks.

## Acceptance criteria

- [ ] Given the Chapter 1 source file is present at its current location on disk, when the human runs the project's documented dev command, then a Lecture page for Chapter 1 is reachable locally and renders the chapter's prose readably.
- [ ] Given the rendered page, when the human inspects it, then each Section in the LaTeX source appears as an addressable region of the page (with a stable per-Section identifier sufficient for future deep-linking and future per-Section Quiz attachment).
- [ ] Given the rendered page, when the human inspects it, then the Chapter is unambiguously labeled as Mandatory (per manifest §8: Chapters 1–6 are Mandatory). The visual treatment may be minimal, but the designation is visible and not buried.
- [ ] Given the documented dev command, when the human runs it twice in a row without editing source, then both runs produce equivalent rendered output (the rendering pipeline is deterministic with respect to a fixed source file).
- [ ] Given the LaTeX source file is opened read-only by the application, when the rendering pipeline runs, then no path under `content/latex/` is written to. (Manifest §5 / §6: Lecture source is read-only.)
- [ ] Given the project has no documented commands today (CLAUDE.md "Commands" section has placeholder values), when this task ships, then the dev command at minimum is recorded in CLAUDE.md by the human at the appropriate gate. (Architect/implementer surface this; the human owns CLAUDE.md.)

## Mandatory / Optional impact

This task **does** touch a curriculum-content surface (the Lecture page). The split applies.

For this task, the rule is: the Chapter's designation (Mandatory) is visibly displayed on the Lecture page itself. A Mandatory-only filter view across the whole curriculum is **not** built here (there's only one Chapter being rendered, and no index page exists yet). The architecture established in this task must not foreclose adding a Mandatory-only view later — specifically, the rendered Chapter must carry its Mandatory designation as data the page exposes, not as hardcoded copy that would have to be unwound when more Chapters land.

The manifest invariant "Mandatory and Optional are separable in every learner-facing surface" is honored at the per-page level by labeling the Chapter; it will be honored at the index level when an index exists (a later task).

## Async / run contract

This task involves **no AI-service work**. No grading, no question generation, no TTS, no weak-topic extraction. The Async / run contract checks do not apply to this task. The manifest's async invariant (§6) becomes relevant the first time an AI-driven feature is introduced; this task does not introduce one.

## Architectural decisions expected

The architect should expect to draft (in `/design TASK-001`) ADRs for, at minimum:

- **ADR: Lecture source layout.** Where lecture source lives on disk and what file format(s) the Lecture pipeline reads. This grounds manifest-conformance rule MC-6 (currently dormant) and §6's "single source" invariant.
- **ADR: Chapter and Section identity.** The stable identifier scheme for a Chapter and for Sections within it (the latter is the future attachment point for Quizzes per manifest §6 and §7 — Quizzes scope to one Section). The rendering pipeline must produce these IDs from source deterministically.
- **ADR: Rendering pipeline for Chapter 1.** What transforms the source into a viewable Lecture page (parser strategy, output format, how/where the page is served or opened). Decide minimally — only what TASK-001 needs. Do not preemptively decide audio, multi-Chapter aggregation, TOC, search, or styling beyond what makes the page readable.
- **ADR: Mandatory/Optional designation source.** Where the Chapter → Mandatory|Optional mapping is recorded and how the Lecture page reads it. Grounds manifest-conformance rule MC-3 (currently dormant). Manifest §8 names Chapters 1–6 Mandatory and 7+ Optional; the ADR must respect that mapping but is free to choose how it is encoded.

Any further questions surfaced (persistence boundary, web framework choice for non-Lecture surfaces, audio pipeline, etc.) that are NOT forced by TASK-001 should be filed as `design_docs/project_issues/<slug>.md` rather than decided here. Per manifest principle: decide what TASK-001 needs and no more.

## Out of scope (this task)

- Any Chapter other than Chapter 1.
- A multi-Chapter index / table of contents.
- A Mandatory-only filter UI.
- Notes (entity, UI, storage).
- Quizzes (entity, UI, generation, attachment).
- AI integration of any kind.
- Audio / listening consumption mode (manifest §7 contemplates multi-mode Lectures; this task ships the reading mode for one Chapter only).
- Persistent storage of completion state, Attempts, Question Banks, etc.
- Search, full-text indexing, or cross-Chapter linking.
- Styling beyond what makes the prose readable (typography polish, dark mode, mobile layout — manifest §5 explicitly says no mobile-first).
- Any deployment beyond local-only.

## Alternatives considered (task direction)

Three materially different directions for what TASK-001 should be were considered:

1. **(Chosen) Render Chapter 1 as a viewable Lecture page.** End-to-end vertical slice: real source → real Lecture surface a learner can read. Forces only the ADRs needed *now* (source layout, identity, rendering, M/O designation). Produces something the human can react to. Establishes the Section addressability that future Quiz attachment depends on, without committing to Quiz design yet.

2. **Skeleton app + "Hello" page + Mandatory/Optional toggle stub backed by a hardcoded Chapter list.** Smaller and gets a web stack standing up, but the page contains no curriculum content. It would force a web-framework ADR and an M/O-mapping ADR up front but defer everything about lecture source. Rejected because the manifest's primary objective is consumption of curated content; a stub page consumes nothing. A first task that doesn't move the primary objective is the wrong first task.

3. **CLI that parses one Chapter's LaTeX into a structured JSON dump (no UI).** Cleanly testable, isolates the parser, defers all UI questions. Rejected because it is a horizontal layer, not a vertical slice. The architect-prompt rule is "vertical slices, not horizontal layers." A parsed JSON the human cannot read as a Lecture does not advance consumption; it just builds infrastructure speculatively. The parser will get exercised as a *consequence* of direction 1, not as the deliverable.

A fourth idea — define the full Pydantic + table schema for Chapter / Section / Quiz / Question / Attempt before anything else — was also considered and rejected: it commits to schema decisions for entities (Quiz, Question, Attempt) that no current task needs, against the principle of deciding only what is forced now.

## Architectural concerns I want to raise

**Project setup gap (not an architecture leak):** `CLAUDE.md` "Commands" section (lines 60–64) contains placeholder values:

```
- Run: `<dev command>`
- Test: `<project test command>`
- Lint: `<project lint command>`
- Type check: `<project type-check command>`
```

CLAUDE.md itself instructs: "Use the commands defined by the repository config when present. If no command is configured yet, surface that as a project setup gap. Do not invent tooling." TASK-001 will produce at least one runnable command (the dev command that opens the Chapter 1 Lecture page). The human owns `CLAUDE.md` and should fill in at least the `Run:` line as part of accepting this task's outcome. The architect / implementer agents must not silently invent and document tooling on the human's behalf. This is operational, not architectural — flagged here so it does not get lost.

**Manifest:** No `MANIFEST TENSION:`. No `ARCHITECTURE LEAK:`. Manifest §4 names `ai-workflows` as a tech, but explicitly owns that as the single allowed manifest-level architectural commitment, so it is not a leak.

**architecture.md:** The file does not exist yet. That is correct for an empty-decisions state — the architect will create it during `/design TASK-001` once at least one ADR is drafted. Not an `ARCHITECTURE FLAW:`.

**CLAUDE.md leak check:** Tier 2 file. Conventions section (type hints, commit format) are workspace-level, not architectural. Pushback protocol and audit-log shape are process. No claims about file paths, frameworks, schemas, or patterns. Clean.

## Verify

- The human runs the documented dev command and a browser (or equivalent local viewer) shows Chapter 1's Lecture, with Sections visible as distinct, addressable regions, and the Chapter labeled Mandatory.
- The reviewer agent runs the manifest-conformance skill against the staged diff. MC-6 (Lecture source read-only) is enforced for the manifest portion; the architecture portion becomes evaluable once the source-layout ADR lands. MC-3 (Mandatory/Optional designation) is similarly partially evaluable. No blockers raised.
- A grep across the implementation code for any write operation targeting the lecture source root returns nothing. (The exact path becomes greppable once the source-layout ADR names it.)
- TASK-001's audit file at `design_docs/audit/TASK-001-render-chapter-one-lecture.md` ends with a `Status: Committed` and the human-gates table records: task accepted, ADRs accepted, tests reviewed, commit reviewed.
