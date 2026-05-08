# ADR-003: Rendering pipeline for Chapter 1 — Python parser to static HTML, served by local FastAPI

**Status:** `Accepted`
**Date:** 2026-05-07
**Task:** TASK-001
**Resolves:** none (no project_issues filed against this question)

## Context

TASK-001 acceptance criterion 1 requires that "a Lecture page for Chapter 1 is reachable locally and renders the chapter's prose readably" when the human runs the project's documented dev command. Acceptance criterion 4 requires deterministic output across runs against fixed source. Acceptance criterion 5 requires that rendering touches no path under `content/latex/` for write. ADR-001 has fixed the input contract (one LaTeX article file per Chapter, body between `\begin{document}` and `\end{document}`). ADR-002 has fixed the identity scheme the renderer must produce (Chapter ID from basename; Section ID from leading section number).

This ADR has to commit to:

1. **A LaTeX-reading strategy** capable of recognizing `\section{...}` macros at the body level and producing readable HTML for the body prose, including the callout boxes (`ideabox`, `defnbox`, `notebox`, `warnbox`) and code listings (`lstlisting`) that `notes-style.tex` defines.
2. **An output format** for the Lecture page (HTML).
3. **A serving strategy** that lets the human "run the dev command" and reach the page locally without remote deployment (manifest §5 forbids remote deployment).
4. **A determinism rule** for the pipeline.

Manifest §4 names `ai-workflows` as the only AI engine commitment, but TASK-001 has zero AI work — the rendering pipeline is plain code, not an AI workflow. ADR-003 does not constrain how `ai-workflows` is integrated for future tasks; that is owned by a later ADR when the first AI-driven feature lands.

The decision space has multiple materially different alternatives (general-purpose LaTeX-to-HTML converters, custom parsers, TeX-to-PDF as an escape hatch). The choice has long-tail consequences for every future Lecture, Note, and Quiz-attachment surface, so the alternatives need to be considered carefully.

## Decision

### Pipeline shape

The rendering pipeline is a **Python program that parses one LaTeX `.tex` file into a structured intermediate representation, then renders that intermediate representation to HTML via a Jinja2 template.** The HTML is served by a small **FastAPI application** running locally on `127.0.0.1`. The dev command starts the FastAPI server; the human opens the Lecture URL in a local browser.

### LaTeX parsing strategy

The parser uses **`pylatexenc`** (specifically `pylatexenc.latexwalker` + `pylatexenc.latex2text` selectively) to walk the LaTeX node tree of the document body. The parser is responsible for:

- Locating the `document` environment (per ADR-001) and walking its children only.
- Recognizing `\section{...}` macros at the body level and emitting Section anchor nodes whose Section IDs follow ADR-002.
- Recognizing `\subsection{...}` macros and emitting subsection structure as plain HTML headings within a Section (no Section ID; subsections are not Sections per ADR-002).
- Recognizing the project's custom callout environments (`ideabox`, `defnbox`, `notebox`, `warnbox`, `examplebox`) and emitting them as styled HTML blocks.
- Recognizing `lstlisting` environments and emitting them as `<pre><code>` blocks (no syntax highlighting required for TASK-001; can be added later without superseding this ADR).
- Passing inline math (`$...$`) and display math (`\[...\]`, `equation` env) through to the HTML output as MathJax-renderable text. The Jinja2 template loads MathJax from a CDN-or-local script tag. (CDN vs local is an implementation detail, not architecture.)
- Stripping or ignoring nodes the parser does not recognize, with a structured warning logged per unrecognized node — not a crash, not a fabrication. Manifest §6 ("AI failures are visible") is about AI failures specifically; the broader principle (visible failures, no fabrication) is honored here for non-AI failures too.

The parser is a thin module; if `pylatexenc` proves insufficient for the corpus, the implementer may extend it with environment-specific handlers, but **the strategy is "walk the LaTeX node tree in Python," not "shell out to a LaTeX-to-HTML converter."** Switching to a different parsing library that preserves this strategy does not require superseding this ADR; switching to a different *strategy* does.

### Output format and template

The pipeline emits **one HTML page per Chapter**, rendered from a single Jinja2 template that takes:

- The Chapter ID and Chapter display title (from the LaTeX `\title{...}` macro in the preamble — the parser may peek at the preamble for this one piece of metadata; this is the only preamble-reading exception ADR-001 contemplates).
- The Chapter's Mandatory/Optional designation (resolved by ADR-004).
- An ordered list of Section blocks. Each Section block has: Section ID, Section heading text (the heading minus the leading number), and parsed body HTML.

The template emits a top-of-page Mandatory|Optional badge for the Chapter (satisfying TASK-001 acceptance criterion 3) and renders Sections as `<section id="{section_id}">` anchors so URL fragment navigation works.

### Serving strategy

A **FastAPI** application exposes a single route for TASK-001: `GET /lecture/{chapter_id}`. The route reads `content/latex/{chapter_id}.tex`, runs the parser, renders the Jinja2 template, and returns the HTML response. Static assets (CSS, MathJax loader if local) are served from a `static/` directory under the application package — never from `content/latex/`.

The dev command launches `uvicorn` against the FastAPI app on `127.0.0.1` at a documented port. (The port number is an operational choice the implementer makes; it is not architecture.) No reverse proxy, no production server, no remote binding — manifest §5 forbids remote deployment.

For TASK-001, the application has **no persistence layer**, no database, no session state, no auth. Adding any of those is out of scope; the manifest-conformance skill's MC-10 (persistence boundary) remains dormant until a persistence-layer ADR lands.

### Determinism

The pipeline is deterministic for a fixed input file. Two runs against the same `content/latex/{chapter_id}.tex`, with the same code, produce byte-identical HTML (modulo any timestamp the template might inject, which the template **must not** inject for TASK-001). No randomness; no clock-derived content. The implementer enforces this by writing a determinism test that renders Chapter 1 twice and diffs.

### Read-only enforcement

The parser, template renderer, and route handler open files under `content/latex/` for reading only (`open(..., "r")` or `pathlib.Path.read_text`). No code path under this ADR opens any file under `content/latex/` for writing. ADR-001's MC-6 grep target is `content/latex/`; this ADR's implementation will pass that grep cleanly.

## Alternatives considered

**A. Use `pandoc` (LaTeX → HTML) as a subprocess.**
Rejected. Pandoc handles a broad LaTeX dialect well but it is opaque about how it handles custom environments — `notes-style.tex` defines `ideabox`, `defnbox`, `notebox`, `warnbox`, and a custom `lstlisting` style. Pandoc would either drop them or render them in a way the project does not control without writing a Lua filter, which is a parser anyway, only in Lua and out-of-process. Adding a subprocess dependency for a tool whose extensibility story leads back to "write a parser" is a worse version of writing the parser in the project's own language. Pandoc would also force the project to ship and depend on a non-Python binary that has nothing else to do here.

**B. Use `plasTeX` instead of `pylatexenc`.**
Considered seriously. plasTeX is a LaTeX-to-HTML toolkit whose macro-extension model is designed for exactly this case (custom environments → custom HTML). However, plasTeX's output model is whole-document-rendering; the project needs structured node access (specifically: "walk the body, identify section boundaries, emit per-Section blocks for the Jinja2 template"). pylatexenc's node-walker API maps more directly onto that need, and a Jinja2 template is a more standard rendering layer for a FastAPI app than plasTeX's templating. plasTeX is not rejected on principle — if the implementer hits a ceiling with pylatexenc on a future Chapter and plasTeX clears it, a future ADR can supersede this one. For Chapter 1, pylatexenc + Jinja2 is the simpler fit.

**C. Compile LaTeX → PDF via `pdflatex` and serve the PDF.**
Rejected. The PDF route preserves the styling perfectly but loses Section addressability (TASK-001 acceptance criterion 2: each Section must be an addressable region of the page). It also loses the ability to emit a Mandatory badge as part of the page (the badge would have to be baked into the LaTeX preamble, which violates the "Lecture source is read-only" rule). Most importantly, future Quiz attachment requires an HTML surface where a "Quiz this Section" affordance can be rendered next to the Section content — a PDF cannot host that.

**D. Render the LaTeX with KaTeX/MathJax client-side and skip server parsing entirely.**
Rejected. KaTeX/MathJax handle math, not the document structure. They cannot parse `\section`, `ideabox`, etc. Client-side-only rendering does not produce Section IDs the server can use for URL routing. They are a *piece* of the chosen solution (math rendering inside HTML) but not a substitute for the parsing step.

**E. Hand-author HTML for Chapter 1 instead of parsing LaTeX.**
Rejected. This violates ADR-001's "single source" intent. Once HTML is hand-authored, the LaTeX file and the HTML file diverge silently. Manifest §6 ("A Lecture has a single source") tolerates *derived* HTML from LaTeX source but not *parallel-authored* HTML.

**F. Use Flask or another minimal web framework instead of FastAPI.**
Considered minor. Flask works equally well for a single-route, no-AI, no-persistence application. The choice of FastAPI over Flask is mildly preferential and does not foreclose future options either way: both run under uvicorn/wsgi locally; both integrate with Jinja2; both let an `ai-workflows`-driven route be added later. FastAPI is chosen because the manifest's secondary objective (§4) names `ai-workflows` as the AI engine, and `ai-workflows`-style async route signatures (`async def route(...)`) are first-class in FastAPI. This is forward-looking, not a TASK-001 constraint. If a future task surfaces a real reason to switch to Flask, supersede this ADR.

## My recommendation vs the user's apparent preference

The task file lists "rendering pipeline" as an expected ADR but does not prescribe technology. The user has not signaled a preference for pandoc, plasTeX, FastAPI, or anything else. This ADR makes specific technology choices (pylatexenc, Jinja2, FastAPI, MathJax) within the latitude the task and manifest leave the architect.

One area where I want to flag my own choice for human gating: **FastAPI over Flask is forward-looking, not strictly forced by TASK-001.** Either would satisfy TASK-001. I have stated my reasoning (alignment with `ai-workflows` async style for future tasks) and the cost of switching later (one ADR supersedure, a small refactor of route definitions). If the user wants to keep TASK-001's footprint maximally minimal and defer the framework choice, that is a legitimate alternative — replace FastAPI with "the implementer picks the smallest viable Python web server for serving one HTML page locally" and revisit when an actual AI-driven route is needed. I am leaving FastAPI in the proposed decision; the human can challenge it at the gate.

I am NOT pushing back on:
- The user's prohibition on remote deployment (manifest §5) — honored.
- The user's "ai-workflows is the only AI engine" commitment (manifest §4) — honored (TASK-001 has no AI; future ADRs handle the integration).
- The single-source rule (manifest §6) — honored by deriving HTML from LaTeX, never authoring HTML in parallel.

## Manifest reading

Read as binding:
- §3 Primary Objective ("drive consumption … via per-Chapter Lectures and Notes") — Bound the requirement that the pipeline produce a *readable* surface, not just a structurally-correct one.
- §5 Non-Goals ("No remote deployment / hosted product"; "No in-app authoring of lecture content"; "No mobile-first product") — Bound the local-only serving model and the "no parallel-authored HTML" rule. Mobile-first is a design constraint not specifically about this ADR.
- §6 Behaviors and Absolutes ("A Lecture has a single source"; "Mandatory and Optional content are honored everywhere"; "Consumption modes of a Lecture remain consistent") — Bound the derive-from-LaTeX rule and the requirement that the page surface the M/O designation.
- §7 Invariants ("Mandatory and Optional are separable in every learner-facing surface") — Bound the badge requirement on the rendered page.

No manifest entries flagged as architecture-in-disguise. Manifest §4's `ai-workflows` mention is explicitly owned by §4 itself.

## Conformance check

- **MC-1 (No direct LLM/agent SDK use).** TASK-001 has no AI surface; this ADR introduces no LLM SDK. The manifest portion remains dormant for this task; the rule stays clean.
- **MC-3 (Mandatory/Optional designation).** The Jinja2 template renders the M/O badge from data passed in by the route handler, not hardcoded. The data source is owned by ADR-004. ADR-003 commits to *displaying* M/O, not to *deciding* M/O — which is the correct separation.
- **MC-4 (AI work asynchronous).** TASK-001 has no AI; rule stays dormant. The choice of FastAPI plus async-friendly handlers does not violate MC-4 — there is no AI work to be synchronous about.
- **MC-6 (Lecture source read-only).** Honored: parser, route, template all read-only against `content/latex/`. The pre-commit hook can grep this implementation for any write target under `content/latex/` and find none.
- **MC-7 (Single user).** Honored: no auth, no user_id, no session partitioning.
- **MC-10 (Persistence boundary).** Dormant; TASK-001 has no DB. ADR-003 does not introduce one.

Previously-dormant rule activated: none new. (MC-6's path-specific check was activated by ADR-001; ADR-003 only consumes that.)

## Consequences

**Becomes possible:**
- A locally-runnable, deterministic Lecture page for Chapter 1.
- Section URL anchors that future tasks can deep-link to (e.g., a "go to the Quiz for this Section" affordance rendered next to each Section heading once Quizzes exist).
- A Jinja2 template that future Lecture tasks (other Chapters, Mandatory-only index, audio mode toggle UI) can extend without re-deciding the rendering layer.
- A FastAPI app that future routes can attach to without standing up a second server (Quiz routes, Notification routes, etc.).

**Becomes more expensive:**
- Adding a Chapter whose source uses LaTeX features pylatexenc cannot walk (esoteric macros, deeply-nested custom environments) requires either extending the parser or superseding this ADR with a different strategy. Acceptable: pylatexenc covers the corpus the project already has; the cost is bounded.
- Switching web frameworks later (FastAPI → something else) is a real cost (one ADR supersedure, route signature refactor). Mitigation: only one route exists today, so the cost is small now and will grow as routes accumulate. Revisit before adding the third or fourth route.

**Becomes impossible (under this ADR):**
- Rendering a Chapter without going through the LaTeX → IR → HTML pipeline. (Manifest §6's "single source" actually requires this; the ADR ratifies the manifest.)
- Serving the Lecture from a remote host (manifest §5).

**Out of scope for this ADR (deferred):**
- Audio consumption mode (manifest §7 contemplates it; no ADR until a task forces it).
- Multi-Chapter index page (deferred until a task forces it).
- Persistence layer (deferred until Quiz/Notes/Attempts force it).
- Exact port number, hot-reload behavior, log format — operational, not architectural.
- The specific dev command string. The implementer will produce a working command (e.g., `uvicorn app.main:app --reload`) and the human will record it in `CLAUDE.md`'s `Run:` field once it actually exists. The architect deliberately does not prescribe a placeholder command in this ADR; the command lands when there's a real one to record.
