# ADR-005: Lecture Page route is `/chapters/{chapter_id}/lecture` with Section anchors as URL fragments

**Status:** Proposed
**Date:** 2026-05-07
**Task:** TASK-001

## Context
The manifest fixes the stable Section identity at `ch-NN-slug#section-slug` (§8 Glossary "Section"). The URL pattern for the Lecture Page is the first user-facing surface that anchors off this identity, and every later content surface (Notes, Quiz routes, the eventual Chapter index) will hang off the same `chapter_id` path key. The decision now sets the URL grammar for the rest of the project.

A Quiz is bound to exactly one Section (manifest §6, §7). A Note is bound to a Chapter and may optionally reference a Section (§7, §8). The URL grammar should accommodate these without forcing a later renaming of the Lecture Page route.

## Decision

The Lecture Page is served at `GET /chapters/{chapter_id}/lecture` where `{chapter_id}` is the `ch-NN-<slug>` form (ADR-001). The response is a single full HTML page rendering the entire Chapter, with each Section emitted as `<section id="section-{slug}" data-designation="{designation}">…</section>`. Within-page navigation is via URL fragment: `/chapters/ch-01-<slug>/lecture#section-bst-insertion`. The fragment slug matches the Section id's fragment portion exactly (the part after `#` in `ch-NN-slug#section-slug`).

The full page is rendered via a single Jinja2 template `cs300/templates/lecture.html` that takes a `Chapter` model (per ADR-003) and walks its Sections and Blocks. There is no per-Section URL (`/chapters/.../sections/.../lecture`) in TASK-001 — Sections are addressed by fragment within the Chapter's page.

Reserved URL grammar (not implemented in TASK-001 but reserved by this ADR so later ADRs honor it):

- `/chapters/` — Chapter index (later task)
- `/chapters/{chapter_id}/lecture` — Lecture Page (this ADR)
- `/chapters/{chapter_id}/notes` — Notes for the Chapter (later task)
- `/chapters/{chapter_id}/sections/{section_slug}/quizzes/...` — Quiz routes (later task; the `section_slug` here is the fragment portion of the Section id)
- `/chapters/{chapter_id}/lecture/audio` — Lecture Audio asset (later task)

These are reserved, not committed; later ADRs may refine the post-`chapter_id` portion. What this ADR commits to is `/chapters/{chapter_id}/...` as the prefix for all per-Chapter surfaces and `{section_slug}` as the path component for per-Section surfaces.

If a request arrives for an unknown `chapter_id`, the response is a plain 404 (FastAPI default). No fuzzy matching, no redirect.

## Alternatives considered
- **Per-Section URL (`/chapters/{chapter_id}/sections/{section_slug}/lecture`).** Rejected for v1: the Lecture Page is "a Chapter's content prepared for consumption" (§8 Glossary "Lecture Page"). A Section is not a stand-alone reading unit; the Quiz is the per-Section atomic unit, not the Lecture. URL fragments handle within-page navigation cleanly.
- **One-page-per-Chapter at `/{chapter_id}` (no `/chapters/` prefix).** Rejected: pollutes the root namespace and prevents adding non-chapter top-level routes (e.g., `/notifications`, `/settings`) without collision risk.
- **`{chapter_id}` is the numeric prefix only (`/chapters/01/lecture`).** Rejected: loses the human-readable slug, makes URLs unintuitive, and creates a second id-source for the Chapter (numeric in URL, slugged in filename). ADR-001 has a single id source.
- **Render Section bodies as HTMX-swappable fragments lazily fetched as the user scrolls.** Rejected: TASK-001 is functional, not performance-tuned; a single full-page render is the simplest thing that works. A future ADR can revisit if Chapters get long enough to make full-page rendering slow.

## Consequences
- The URL `chapter_id` path parameter is validated against the same regex as the filename (ADR-001) at the route layer. A malformed `chapter_id` returns 404, never reaches the parser.
- Anchored deep links work: `/chapters/ch-01-bst/lecture#section-bst-insertion` scrolls to the Section, which is everything in-page navigation needs.
- The route handler reads the corresponding `.tex` file (no DB), parses it (ADR-003), and renders it. Caching, ETags, and reload-on-source-change are out of scope for TASK-001 but are easy to bolt on later given the pure-function parser.
- Reserving the URL grammar above means later tasks won't have to debate `/chapters/` vs `/chapter/` vs something else — that bikeshed is closed.
- The URL fragment is HTML semantics, not a server route; the server returns the same HTML regardless of fragment. Standard browser behavior handles the scroll.

## Manifest conformance
- §8 Glossary "Section" stable id `ch-NN-slug#section-slug`: the URL `/chapters/ch-NN-slug/lecture#section-slug` materializes the stable id directly.
- §6 "Atomic units differ by surface" (Chapter for Lectures, Section for Quizzes): the URL grammar reflects this — `/chapters/{chapter_id}/lecture` is Chapter-scoped, the reserved Quiz route is Section-scoped.
- §3 Primary Objective: the URL is human-readable and bookmarkable, supporting the consumption objective directly.
