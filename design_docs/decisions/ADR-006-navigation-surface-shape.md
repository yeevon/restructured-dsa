# ADR-006: Navigation surface — `GET /` landing page that also serves as a left-hand rail include in every Lecture page

**Status:** `Accepted`
**Date:** 2026-05-08
**Task:** TASK-002
**Resolves:** none (no project_issues filed against this question; surfaced and addressed during TASK-002 design)

## Context

TASK-002 requires a learner-facing surface that exposes every Chapter present in `content/latex/`, grouped into Mandatory and Optional, with each Chapter linked to its existing Lecture page. The task explicitly leaves the *shape* of that surface to this design ADR, and the human's pushback on the original TASK-002 used "LHS rail" as shorthand while reserving rail-vs-page-vs-both for the architect.

Two architectural questions are coupled here:

1. **Where does the surface live?** Options include `GET /` (a dedicated landing page), `GET /chapters/` (an explicit index path), a sidebar fragment included in every page (no addressable URL of its own), or some combination.
2. **What HTML mechanism implements it?** Options include a standalone Jinja2 template, a partial template that the existing `lecture.html.j2` includes, or template inheritance via a base layout.

These are coupled because choosing "rail on every page" without a landing page leaves the bare URL `http://127.0.0.1:8000/` returning a FastAPI 404 — which is friction the human bookmarks against. Choosing "landing page only, no rail" leaves Lecture pages as dead ends — explicitly forbidden by TASK-002's acceptance criterion: "Lecture page is no longer a navigation dead end."

The existing FastAPI app exposes one route (`GET /lecture/{chapter_id}`) and one Jinja2 template (`app/templates/lecture.html.j2`) with no template inheritance. This ADR is the first place navigation chrome is introduced; whatever shape this ADR fixes, every future learner-facing surface (Notes UI, Quiz attachment, completion indicators) will compose against it.

The manifest constrains this decision through §3 (consumption / discoverability), §6 (Mandatory/Optional honored everywhere), §7 (Mandatory/Optional separable in every learner-facing surface), and §5 (no LMS, no remote deployment, no mobile-first — bound the simplicity ceiling).

## Decision

### Two surfaces, one source of truth

The navigation lives in **two places**, both reading from a single shared rendering helper:

1. **`GET /` — dedicated landing page.** A new FastAPI route returns an HTML page whose primary content is the navigation surface itself: two visibly-labeled sections ("Mandatory" and "Optional"), each containing a list of Chapter rows linking to `GET /lecture/{chapter_id}`. This page is the bookmark target ("home of this project") and the answer to "where do I go to find a chapter."
2. **Left-hand rail on every Lecture page.** The existing `lecture.html.j2` template is extended (via template inheritance from a new base layout, see below) to include a left-hand rail rendering the same two grouped lists. The rail is included in every Lecture page so Lecture pages are never dead ends (TASK-002 acceptance criterion).

Both surfaces render from the **same Python helper** (a single function returning the same data structure). The rail and the landing page are two views of one source of truth — there is no possibility of the rail and landing page disagreeing on which Chapters exist or how they are grouped.

### Template architecture

A new Jinja2 base template `app/templates/base.html.j2` owns the page-level chrome (`<html>`, `<head>`, MathJax script tag, the left-hand rail block, the `<main>` content region). Two child templates extend the base:

- `app/templates/lecture.html.j2` — refactored to extend `base.html.j2`, populating only the `{% block main %}` region with Lecture content. The header, MathJax setup, and rail come from `base.html.j2`.
- `app/templates/index.html.j2` — new template for `GET /`. Extends `base.html.j2`. Its `{% block main %}` is empty *or* contains a brief "Welcome — pick a Chapter from the navigation rail" header. The rail itself is the page; the `<main>` region is intentionally minimal.

The rail itself is a partial template `app/templates/_nav_rail.html.j2`, included by `base.html.j2` in a `<nav class="lecture-rail">` region. This is the only template that knows how to render the grouped Chapter list. Both the landing page and every Lecture page render the rail by virtue of extending `base.html.j2`.

### Data flow

The route handlers (`GET /` and `GET /lecture/{chapter_id}`) both call a single helper that returns a `dict[Literal["Mandatory", "Optional"], list[ChapterEntry]]` (where `ChapterEntry` is the per-row data structure: chapter_id, display_label, link target). The helper composes Chapter discovery (ADR-007) with the designation function (ADR-004). Both routes pass that dict into their template render call; the `_nav_rail.html.j2` partial reads the dict from a Jinja variable named `nav_groups` regardless of which route rendered it.

The Lecture page's existing `chapter_id`, `title`, `designation`, `sections`, `pre_section_html` template variables are unchanged — the rail is additive, not a refactor of the Lecture's existing data model.

### Routing

- `GET /` → returns the landing page. Status 200 unless Chapter discovery itself fails (per ADR-007's fail-loudly rule, which propagates as 500-class with a structured error in the page body). The route is documented in the FastAPI app's docstring and called out in `CLAUDE.md`'s "Run:" line indirectly — the human starts the server and visits `http://127.0.0.1:8000/`.
- `GET /lecture/{chapter_id}` — unchanged contract from ADR-003. Now renders with the rail by virtue of extending `base.html.j2`.
- `GET /chapters/` — **not introduced.** Adding a third route surface for the same content would create a third URL the human has to remember. `GET /` is the canonical home.

### Scope of this ADR

This ADR fixes only:

1. The set of routes that render navigation (`GET /` plus the rail-included-in-every-Lecture-page mechanism).
2. The template architecture (one base, two children, one rail partial).
3. The principle that the rail and the landing page render from a single helper (no two-source-of-truth risk).

This ADR does **not** decide:

- How Chapters are discovered (ADR-007).
- How Chapter display labels are sourced (ADR-007).
- Within-group ordering (ADR-007).
- CSS / visual treatment of the rail and the landing page (implementation choice; not architecture).
- Whether the rail collapses on narrow viewports (manifest §5: no mobile-first; whatever the implementer ships is acceptable as long as the rail does not become unreachable on a desktop browser).

## Alternatives considered

**A. Landing page only (`GET /`); no rail; Lecture pages have a "← Back to Chapters" link.**
Rejected. Satisfies TASK-002's acceptance criteria literally (Lecture page is no longer a dead end — there's a back link), but every Chapter-to-Chapter navigation requires two clicks (Lecture → home → other Lecture). At the current corpus size (12 chapters), a rail is reachable in one click and has no real cost — it's one partial template included by a base template the project will need anyway as soon as the second learner-facing surface (Notes UI, Quiz panel) lands. The rail is amortized infrastructure, not surface bloat.

**B. Rail only; no landing page; `GET /` redirects to `/lecture/{first-mandatory-chapter}`.**
Rejected. The "first Mandatory chapter" rule is itself a hidden architectural decision that this ADR would have to make and document. It also assumes the human always wants to land in Chapter 1 — but the project's primary objective (consumption) is served just as well by landing on a navigation surface and choosing where to go next. A redirect also denies the human a stable bookmark URL for "the home of this project."

**C. Sidebar rendered on every page including `GET /`, where `GET /` returns just the sidebar with no `<main>` content.**
Considered. Functionally equivalent to the chosen decision but makes the landing page feel anemic ("the home page is just a navigation panel and nothing else"). The chosen decision treats the landing page's `<main>` region as available for future welcome / what's-new / start-here content; that flexibility is cheap to preserve and would cost a refactor to add later if the landing page is initially defined as "rail with no main."

**D. `GET /chapters/` as the navigation surface; `GET /` returns 404 or a static "navigate to /chapters/" message.**
Rejected. Two URLs for the same idea (the project's home + the navigation surface) is friction the human pays every time. `GET /` is the natural bookmark target. There is no reason to introduce a `/chapters/` path unless and until the project later adds a second top-level taxonomy (e.g., `/topics/`), at which point a future ADR can split.

**E. Rail rendered server-side as a Jinja `include` in `lecture.html.j2` directly, without introducing a base template.**
Rejected. This works for TASK-002 in isolation but does not scale: when the second learner-facing surface (e.g., a Notes editor at `GET /notes/...`) lands, the rail will need to be included there too, and every new template will repeat the head/script/styles/rail boilerplate. Introducing the base template now is a small cost paid once; refactoring three or four templates later to share a base is a larger cost paid against task pressure. The architect's job here is to spend a small certain cost now to avoid a larger uncertain cost later.

**F. Single-page application (client-side rail rendered from a JSON endpoint).**
Rejected. Adds a JavaScript build/serve story the project does not currently have, plus a client-side rendering layer for content the server already has in hand. Manifest §5 (no mobile-first, no remote deployment) and the project's overall "small local FastAPI app" shape do not call for a SPA. ADR-003's pipeline is server-side rendered HTML; the rail is the same. (This rejects a SPA *architecture* on cost-vs-benefit, not "JavaScript" — JavaScript is part of the available toolkit; see ADR-035.)

## My recommendation vs the user's apparent preference

The human's pushback on the original TASK-002 used "LHS rail" as shorthand: "we can just have a LHS rail with Mandatory then links to chapters 1-6, and Options and links to chapters 7+ and that will cover this and gives easy chapter navigation." The reframed TASK-002 explicitly leaves rail-vs-page-vs-both to this ADR.

I am recommending **both** rather than rail-only. The disagreement with the user's apparent preference is mild and worth surfacing:

- **The user's framing implies a rail is sufficient.** A rail satisfies TASK-002's "Lecture page is no longer a dead end" criterion and exposes the Mandatory/Optional split structurally on every page.
- **My recommendation adds a `GET /` landing page on top of the rail.** Rationale: (i) the bare URL `http://127.0.0.1:8000/` is the human's first navigation in any session and currently returns 404 — that's avoidable friction; (ii) the rail-only design forces the human to first guess any Chapter URL to *get to* a page that hosts the rail, which is exactly the "URL guessing" the task aimed to eliminate; (iii) introducing the base template now is the right cost to absorb at the same moment the rail is built.
- **The cost of disagreeing with the user here is small.** If the human wants to defer the landing page, this ADR can be amended at the gate to "rail only; `GET /` returns 404" with no impact on the rail design. The base template is the meaningful architectural commitment; the existence of a `GET /` route is an additive deletion candidate.

I am NOT pushing back on:
- The rail itself — chosen.
- Grouping by Mandatory/Optional — required by manifest §7 and TASK-002.
- Rendering both via server-side templates — consistent with ADR-003.

## Manifest reading

Read as binding:
- §3 Primary Objective ("drive consumption … via per-Chapter Lectures") — Bound the requirement that the landing page actually leads the human into Chapters with as little friction as possible.
- §5 Non-Goals — "No LMS features" bounds the rail to "links to Lectures," not progress dashboards or assignment trackers; "No mobile-first product" bounds the rail's responsive obligations to "usable on a desktop browser." "No remote deployment" bounds the entire navigation to local-served HTML.
- §6 Behaviors and Absolutes — "Mandatory and Optional content are honored everywhere" bounds the requirement that both surfaces (rail and landing page) render the M/O grouping; the rail cannot show a flat list.
- §7 Invariants — "Mandatory and Optional are separable in every learner-facing surface" bounds the structural-grouping rule on both surfaces.
- §8 Glossary — Chapter, Lecture, Mandatory, Optional. Bound the per-row data model: each row is a Chapter (not a Section, not a Topic), labeled with its designation by virtue of the section it appears under.

No manifest entries flagged as architecture-in-disguise.

## Conformance check

- **MC-3 (Mandatory/Optional designation respects the canonical mapping).** Both surfaces render groupings derived at request time from `chapter_designation()` (ADR-004). Neither template hardcodes Chapter numbers; neither route hardcodes a static list of Mandatory or Optional chapter IDs. Compliance preserved.
- **MC-6 (Lecture source is read-only to the application).** Neither route writes to `content/latex/`. The rail rendering performs filesystem enumeration only (delegated to ADR-007); no write. Compliance preserved.
- **MC-7 (Single user).** Both routes are global; no per-user state, no user_id, no auth. Compliance preserved.
- **MC-1 / MC-2 / MC-4 / MC-5 / MC-8 / MC-9 / MC-10.** Not touched (no AI work, no Quiz, no persistence, no DB).

Previously-dormant rule activated by this ADR: none.

## Consequences

**Becomes possible:**
- A bookmarkable home (`http://127.0.0.1:8000/`) for the project.
- One-click Chapter-to-Chapter navigation from any Lecture page (via the rail).
- A base-template inheritance mechanism the project's future learner-facing surfaces (Notes, Quizzes, Notifications) will compose against without re-deciding chrome architecture each time.
- A single rail partial (`_nav_rail.html.j2`) that future surfaces include automatically by extending `base.html.j2`. Adding a Notes editor route, for example, gets the rail for free.

**Becomes more expensive:**
- The Lecture template is refactored to extend a base — a one-time cost paid against TASK-002. Mitigation: TASK-001's tests pin Lecture rendering behavior (133 tests on file); the refactor is mechanical and constrained.
- Adding a new top-level route now requires deciding whether it extends `base.html.j2` (gets the rail) or stands alone (no rail). The default — extend the base — is the right one for any learner-facing surface; non-learner surfaces (e.g., a future health-check endpoint, debug routes) skip the base. This is a small ongoing decision burden, not a structural cost.

**Becomes impossible (under this ADR):**
- A second navigation surface that derives groupings from a different mechanism than `chapter_designation()`. The single helper enforces a single source of truth for the grouped Chapter list.
- A Lecture page without the rail, unless a future ADR supersedes this one (in which case "Lecture page is a dead end again" must be addressed by that ADR).

**Future surfaces this ADR pre-positions:**
- Notes UI (manifest §8) — extends `base.html.j2`, gets the rail automatically.
- Quiz attachment surfaces (per-Section "Quiz this Section" affordances rendered inside Lecture pages) — already inside `lecture.html.j2`'s `{% block main %}`, no additional routing decision needed.
- Notification surface (manifest §8) — most natural shape is a header/badge inside `base.html.j2`'s chrome region, reachable from every page.
- Future Mandatory-only "view" affordance (if ever introduced — currently rejected by TASK-002 in favor of structural grouping) would naturally be a query parameter on `GET /` (e.g., `GET /?show=mandatory`), not a separate route.
