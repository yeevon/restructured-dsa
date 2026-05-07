# TASK-001: Render one Chapter's Lecture Page from LaTeX source

**Manifest sections this touches:** §3 Primary Objective, §6 Hard Constraints (Atomic units differ by surface; LaTeX is the source of truth; site never modifies LaTeX), §7 Invariants (Mandatory/Optional separable in every UI surface; Completion state per-Section; Read path only), §8 Glossary (Chapter, Section, Lecture, Lecture Page, Mandatory, Optional)
**Architecture state assumed:** ADR-000 (baseline: FastAPI + Jinja2 + HTMX, plasTeX, SQLite reserved for later, `cs300/` package layout)
**Project issues this forces:** none (TTS, topic vocabulary, notification mechanism, and HTMX testing strategy are all explicitly deferred until later tasks; this task is pure read-only HTML rendering)

## What and why
Use **Chapter 1** of the curated curriculum: drop its LaTeX into `content/latex/` and render it as the Lecture Page at a URL like `/chapters/ch-01-<slug>/lecture`. Sections within the Chapter are anchored (e.g., `#section-<slug>`) and each Section's DOM wrapper carries the Chapter's Mandatory/Optional designation as a data attribute, so the future Chapter index page can filter by designation. This is the smallest vertical slice that proves the LaTeX -> HTML pipeline, establishes the Chapter/Section identity scheme that every later task depends on, and produces something the human can open in a browser and read. No AI, no DB writes, no async — read path only.

**Curriculum decision (locked by author, 2026-05-07):** Mandatory/Optional designation is per-Chapter, not per-Section. Chapters `ch-01` through `ch-06` are **Mandatory** (SNHU CS-300 syllabus). Chapters `ch-07` and later are **Optional** (MIT OCW augmentation). Sections inherit their Chapter's designation; no within-Chapter split exists.

## Acceptance criteria
- [ ] Chapter 1's `.tex` file lives under `content/latex/` (committed; the manifest treats LaTeX source as read-only from the app, not from the repo).
- [ ] `cs300/` Python package exists with at minimum: `cs300/__init__.py`, `cs300/app.py` (FastAPI app), `cs300/lecture/` (LaTeX parsing + page rendering), `cs300/templates/` (Jinja2 templates).
- [ ] Given the seeded Chapter, when the user navigates to `GET /chapters/ch-01-<slug>/lecture`, the response is a full HTML page (status 200) containing the Chapter title, every Section's title, every Section's body content rendered to HTML, and stable per-Section anchor ids.
- [ ] The Chapter's wrapper element carries `data-designation="mandatory"` (since `ch-01` is Mandatory). Each Section's wrapper element carries the same `data-designation` value, inherited from the Chapter. A unit test asserts the attribute is present on both the Chapter and every Section in the rendered DOM.
- [ ] Section IDs are stable: re-running the parser on the same `.tex` file produces the same IDs in the same order. (Tested: a unit test parses the seeded Chapter twice and asserts identical Section ID lists.)
- [ ] LaTeX environments that don't yet have a render rule (e.g., a `lstlisting` block or an unfamiliar custom command) render as a clearly-marked passthrough or a visible TODO block — not a silent drop and not a 500. Author lists in the task notes which environments are mapped vs. passthrough.
- [ ] `pytest` passes; `ruff check` passes; `mypy cs300/` passes.
- [ ] `README` or a short note in the task close-out documents how to run the dev server and which URL to visit.

## Mandatory / Optional impact
YES — this task creates the very first curriculum-content surface, and it locks in the per-Chapter designation rule.

- The parsed `Chapter` model carries a single `designation: "mandatory" | "optional"` field, derived from the Chapter's numeric prefix (`ch-01` through `ch-06` → mandatory; `ch-07+` → optional). No per-Section designation field exists.
- The Lecture Page DOM exposes the designation as a `data-designation` attribute on the Chapter wrapper and on each Section wrapper (Sections inherit). This shape is what a future Chapter index page will use to render Mandatory-only filtering.
- **No within-page "Mandatory only" toggle in v1.** Chapter 1 is fully Mandatory, so a within-page toggle would do nothing visible; the manifest invariant ("user must always be able to view Mandatory-only") is satisfied because Chapter 1's Lecture Page IS Mandatory-only by construction. Filtering at the Chapter level is a Chapter-index concern and is a later task.
- The designation rule itself (chapter-number-based) lives in code as a small pure function (`designation_for_chapter_id(chapter_id) -> Literal["mandatory", "optional"]`). It is unit-tested. If the author later wants to override it for a specific Chapter, the override mechanism is not in scope for this task — surface as an issue if/when it comes up.

## Async / run contract
NO AI-service work is involved in this task. The Lecture Page is a pure deterministic transformation of LaTeX source to HTML. No `ai-workflows` Run is created, no `run_id` is stored, no Notification is surfaced. Lecture Audio (which IS async) is a later task.

## Architectural decisions expected
- **Section ID scheme.** How does the LaTeX walker normalize Section IDs to the manifest's `ch-NN-slug#section-slug` shape? What anchors a Section — `\section{...}`, `\subsection{...}`, both? What's the slug source — heading text? An explicit LaTeX label? How are ID collisions handled within a Chapter?
- **Chapter ID source.** The Chapter ID drives both the URL and the Mandatory/Optional designation lookup. Where does it come from — file name (`content/latex/ch-01-<slug>.tex`), a directory layout, or an explicit `\chapterid{ch-01-<slug>}` command in the source? The architect records the choice in an ADR.
- **plasTeX walker shape.** What's the in-memory data structure produced by parsing? (Likely `Chapter(id, title, designation, sections=[Section(id, title, body_html)])`, but record it.) Where do unrecognized LaTeX environments go — passthrough, drop, or TODO marker?
- **Routing surface.** URL pattern for Lecture Page. The manifest's stable Section ID is `ch-NN-slug#section-slug`; the URL likely echoes that (`/chapters/ch-NN-slug/lecture` with `#section-slug` anchors).
- **Test seam for the LaTeX pipeline.** Stable Section IDs must be unit-testable without spinning up FastAPI. Implies the parser is callable as a pure function from `.tex` path -> `Chapter` model.

**Already decided by the author (do not re-deliberate):**
- Mandatory/Optional designation is per-Chapter, derived from the numeric prefix (`ch-01..ch-06` Mandatory; `ch-07+` Optional). Sections inherit. No within-Chapter split, no LaTeX-level designation marker, no sidecar metadata file. Encoded as a small pure function in `cs300/lecture/`.
- Seeded Chapter is Chapter 1.
- No within-page Mandatory-only toggle in v1.

## Out of scope (this task)
- Notes (Chapter-bound user markdown). Later task.
- Quiz generation, Quiz taking, grading, async runs of any kind. Later task.
- Lecture Script extraction (the TTS-ready text representation). Later task — though the architect should not paint into a corner that prevents the script extraction from being a sibling output of the same source.
- Lecture Audio. Later task.
- SQLite schema, repositories, persistence layer. The Lecture Page is a pure read-only transformation; no DB write happens in this task.
- Topic vocabulary. The `project_issues/topic-vocabulary-representation.md` issue stays open; topics matter for Quiz generation, not for the Lecture Page.
- Notification mechanism. The `project_issues/notification-mechanism.md` issue stays open; nothing in this task is async.
- Multi-Chapter navigation, a Chapter index page, breadcrumbs. The deliverable is one Chapter rendered correctly. A bare hardcoded "go to /chapters/<seeded-id>/lecture" instruction in the README is sufficient.
- `tooling`/`pre-commit`/CI scaffolding beyond what's required to run `pytest`, `ruff`, and `mypy` locally.
- Styling beyond functional. Manifest non-goal: this is functional, not pretty.

## Verify
- `pytest` passes (includes a test that parsing the seeded `.tex` twice yields identical Section ID lists; a unit test that `designation_for_chapter_id` returns `"mandatory"` for `ch-01..ch-06` and `"optional"` for `ch-07+`; and a route test that `GET /chapters/ch-01-<slug>/lecture` returns 200 with the expected Section titles, anchors, and `data-designation="mandatory"` on the Chapter and Section wrappers).
- `ruff check` passes; `mypy cs300/` passes.
- The human runs the dev server, opens `http://localhost:<port>/chapters/ch-01-<slug>/lecture`, and sees the Chapter title and all Sections rendered with their content.
- The seeded LaTeX file under `content/latex/` is unchanged after the test run (read-only constraint preserved).
