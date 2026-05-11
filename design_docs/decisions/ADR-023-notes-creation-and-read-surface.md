# ADR-023: Notes creation/read surface — `POST /lecture/{chapter_id}/notes` form-encoded with PRG redirect, Notes section appended to `lecture.html.j2`, multi-Note list with empty-state caption

**Status:** `Superseded by ADR-028` (§Template-surface only — see ADR-028 for the rail-resident replacement; the route shape, form-handling, empty-state, multiple-Note display order, submit-feedback shape, and validation rules from this ADR remain in force)
Original Acceptance: 2026-05-10
**Date:** 2026-05-10
**Task:** TASK-009
**Resolves:** none (no project_issue filed against this question; the surface question is forced inline by TASK-009)
**Supersedes:** none
**Superseded by:** `ADR-028` (Auto-accepted by /auto on 2026-05-10)

## Context

TASK-009 ships the minimum viable Note surface. ADR-022 (Proposed in the same `/design TASK-009` cycle) commits to the persistence shape: SQLite via stdlib `sqlite3` under `app/persistence/`, with a `notes` table keyed on `(note_id, chapter_id, body, created_at, updated_at)`. This ADR fixes the **HTTP/template surface** that consumes that persistence: which routes the application exposes for Note creation and read, where in `lecture.html.j2` the Notes UI lives, what the empty-state and submit-feedback shapes are, and how form input is validated.

The decision space has materially different alternatives:

- **Route shape:** `POST /lecture/{chapter_id}/notes` form-encoded; `POST /notes` with `chapter_id` in the body; HTMX-style partial-reload; client-side fetch returning JSON; full-page form submission with PRG (Post-Redirect-Get).
- **Where Notes live in the Lecture template:** appended at the bottom of `{% block main %}` after Sections; injected near the Mandatory/Optional badge at the top; in a collapsible side panel; on a separate `/lecture/{chapter_id}/notes` page.
- **Empty-state shape:** form alone with placeholder text; form + "No notes yet" caption; form + onboarding hint with examples.
- **Submit-feedback shape:** PRG (full-page reload); inline AJAX with status indicator; flash message in URL fragment; toast / notification banner.
- **Validation:** server-side rejection of empty/whitespace-only body with HTTP 400 + redirect; client-side `required` attribute only; both.
- **Multiple-Note display:** list ordered most-recent-first; list ordered oldest-first; collapsible per-Note panels; only the most-recent Note shown.

The manifest constrains the decision through §3 (Notes are a primary-objective consumption pillar — the surface must be readable and direct), §5 (no mobile-first bounds the responsive obligation; no LMS bounds the editorial scope to "user can write a Note and read it"), §6 (single user — no auth, no per-user partitioning at the route layer; AI work async — Notes are not AI work, so synchronous form submission is the right shape, not a violation of the AI-async absolute), §7 (every Note persists; bound to one Chapter).

## Decision

### Route shape — `POST /lecture/{chapter_id}/notes` form-encoded body, PRG redirect to `GET /lecture/{chapter_id}`

A new FastAPI route is introduced: `POST /lecture/{chapter_id}/notes`. The route accepts a form-encoded body with a single field `body` (the Note text). On success, the route returns **HTTP 303 See Other** with `Location: /lecture/{chapter_id}` — the standard PRG (Post-Redirect-Get) idiom. The browser issues a fresh `GET /lecture/{chapter_id}` and the new Note appears via the read path.

**Why 303 specifically:** RFC 7231 §6.4.4 specifies 303 for "the response to the request can be found at another URI and SHOULD be retrieved using a GET method on that resource." 302 is the older, more ambiguous redirect; some HTTP clients historically preserve the POST method on 302 (counter to the spec), so 303 is the safer choice for PRG.

The Lecture page route (`GET /lecture/{chapter_id}`, owned by ADR-003 and ADR-006) is extended to fetch the Notes for the Chapter via `app/persistence/notes.list_notes_for_chapter(chapter_id)` and pass them to the `lecture.html.j2` template under a `notes` template variable. The route signature and existing template variables (`chapter_id`, `title`, `designation`, `sections`, `pre_section_html`, `nav_groups`) are unchanged; `notes` is additive.

**Routes introduced or modified:**

- **NEW** `POST /lecture/{chapter_id}/notes` — accepts form-encoded `body`; validates; persists; returns 303 redirect to `GET /lecture/{chapter_id}`.
- **MODIFIED** `GET /lecture/{chapter_id}` — additionally fetches Notes for the Chapter and passes them to the template. No change to the route's contract from the caller's perspective (still returns `200` on success, `404` on missing Chapter, `422` on malformed `chapter_id`).

**Routes NOT introduced:**

- No `GET /notes` index route. Cross-Chapter Notes views are out of TASK-009 scope.
- No `GET /lecture/{chapter_id}/notes` partial route. The Notes UI lives inside the Lecture page; there is no addressable URL for "just the Notes section."
- No `PUT/PATCH/DELETE /notes/{note_id}` routes. Edit / delete are out of TASK-009 scope.
- No JSON API. The route serves form-encoded HTML; no `application/json` content negotiation.

### Form-handling pattern — synchronous form POST + PRG redirect; no JavaScript

The form submits synchronously via the browser's native form handling: `<form method="post" action="/lecture/{chapter_id}/notes">`. There is no `fetch()`, no `XMLHttpRequest`, no HTMX, no client-side framework. On submit the browser issues the POST, follows the 303 redirect, and renders the resulting GET response — a full page reload.

**Why synchronous PRG, not AJAX/HTMX:**

- The project has no JavaScript build/serve story (manifest §5 bounds the operational simplicity ceiling; ADR-003 commits to flat static assets, no preprocessor / no build step). Adding HTMX would add a top-level static asset and a behavioral surface; adding AJAX would require either a JSON API (rejected above) or an HTML-fragment endpoint plus the swap logic.
- Notes are not latency-sensitive. The user writes a Note, submits, and the page reloads in <100ms locally — well below the threshold where partial reloads would be perceptible.
- Synchronous PRG works without JavaScript at all. If the human turns off JS in their browser, the Notes UI still works. This is the lowest-friction baseline; layering AJAX on top later is a small ADR if a real reason emerges.
- Manifest §6's "AI work is asynchronous from the learner's perspective" is about *AI* work specifically. Notes are not AI work (manifest §8: "Never auto-generated"). Synchronous form submission is the correct shape for Notes; treating it as a violation of the AI-async absolute would be a misread.

**Validation:**

- The route handler trims `body` (rejects leading/trailing whitespace) and rejects empty / whitespace-only bodies with **HTTP 400 Bad Request** and a brief HTML error response. (Architect's note: the simplest acceptable error response is a re-render of the Lecture page with an error caption; the implementer may also choose a plain 400 status with a small error page. Either is acceptable as long as the rejection is visible to the user, not silent.)
- The route handler validates `chapter_id` against the discovered set (via `discover_chapters()`); an unknown `chapter_id` returns **HTTP 404**.
- Maximum body length: the route handler rejects bodies >64 KiB with HTTP 413 (Payload Too Large). 64 KiB is generous for a personal study Note and prevents accidental denial-of-service via very large form posts.
- The HTML form additionally carries `required` and `maxlength="65536"` attributes on the `<textarea>` so most user errors are caught client-side without round-tripping; the server-side validation is the authority.

### Template surface — Notes section appended at the bottom of `lecture.html.j2`'s `{% block main %}`

The Notes UI is rendered as a new `<section class="notes-surface">` block inside `lecture.html.j2`'s `{% block main %}`, **after** the existing per-Section content loop. Concretely, the structure becomes:

```html
<article class="lecture">
  <header class="lecture-header">...</header>
  {% if pre_section_html %}<div class="lecture-intro">...</div>{% endif %}
  {% for section in sections %}<section id="...">...</section>{% endfor %}

  <section class="notes-surface">
    <h2 class="notes-heading">Notes</h2>
    {% if notes %}
      <ul class="notes-list">
        {% for note in notes %}
          <li class="note-item">
            <div class="note-meta">
              <time class="note-timestamp" datetime="{{ note.created_at }}">{{ note.created_at }}</time>
            </div>
            <div class="note-body">{{ note.body }}</div>
          </li>
        {% endfor %}
      </ul>
    {% else %}
      <p class="notes-empty">No notes yet — write the first one below.</p>
    {% endif %}

    <form class="note-form" method="post" action="/lecture/{{ chapter_id }}/notes">
      <label for="note-body" class="note-form-label">New note</label>
      <textarea id="note-body" name="body" class="note-form-input"
                rows="6" required maxlength="65536"
                placeholder="Write a note about this chapter..."></textarea>
      <button type="submit" class="note-form-submit">Save note</button>
    </form>
  </section>
</article>
```

**Why "appended at the bottom" rather than top or side panel:**

- The Lecture's primary content (the lecture itself) should be the visual focus when the page loads. Putting Notes at the top of `<main>` would push the lecture below the fold and contradict manifest §3 (consumption-first).
- A collapsible side panel competes with the existing left-hand rail (ADR-006) for the page's left-side real estate; CSS Grid (ADR-008) sets up two columns (rail + main), and a third column for Notes would force a layout redesign.
- Bottom-of-page placement matches the natural reading flow: the user reads the lecture top-to-bottom; the Notes surface appears where the user's attention is at the *end* of the lecture, which is exactly when they have something to write down.
- A separate `/lecture/{chapter_id}/notes` page is rejected because it forces a navigation away from the lecture content the Note is *about* — round-tripping between two pages every time the user wants to write a Note while reading is friction the in-page placement avoids.

### Empty-state shape — form + "No notes yet — write the first one below." caption

When `list_notes_for_chapter(chapter_id)` returns an empty list, the template renders:

- The `<h2 class="notes-heading">Notes</h2>` heading (always present).
- A `<p class="notes-empty">` caption with the text "No notes yet — write the first one below."
- The form (always present, regardless of empty state).

The empty-state caption is editorial-grade plain English. It does not include onboarding examples, tutorials, or feature explanations — manifest §5 (no mobile-first, no LMS) bounds the editorial scope; this is a personal study tool, not a consumer onboarding surface.

### Multiple-Note display — list ordered `created_at DESC` (most-recent first)

When multiple Notes exist for a Chapter, the template renders them as a `<ul class="notes-list">` with each Note as a `<li class="note-item">`. The order is **most-recent first** (`ORDER BY created_at DESC` in the persistence query). Each Note item shows:

- A timestamp (`<time>` element with `datetime` attribute set to ISO-8601 from `created_at`).
- The Note body (plain text, escaped — no Markdown rendering, no rich-text formatting; manifest scope is plain text per TASK-009 "Out of scope").

The body is rendered via Jinja2's autoescape (already enabled in `app/main.py`'s Jinja2 environment); user-authored Note text is treated as untrusted input and HTML-escaped on render.

The list does **not** include per-Note edit/delete affordances — those are out of TASK-009 scope. Adding them is a follow-up ADR + task.

### Submit-feedback shape — full-page reload via 303 PRG

After successful `POST /lecture/{chapter_id}/notes`, the user sees:

1. The browser's native loading indicator briefly during the redirect.
2. The fully re-rendered Lecture page with the new Note now at the top of `notes-list`.

There is no flash message, no toast, no inline status indicator, no URL fragment. The new Note's appearance at the top of the list is the user-visible feedback that the submission succeeded.

**Why no flash message:** flash messaging requires either (a) a session/cookie store to round-trip the message, which contradicts manifest §6 (no session) and adds a session-handling complexity tier; or (b) a URL fragment (`#note-saved`) that JavaScript reads on load, which contradicts the no-JS commitment above. The new-Note-appears-at-top feedback is direct and sufficient.

### Styling — new classes added to `app/static/lecture.css`

Per ADR-008's class-name-prefix convention (`.lecture-*`, `.section-*`, `.callout-*` → `lecture.css`; `.page-*`, `.nav-*`, `.index-*` → `base.css`), the new Notes-related classes belong in `lecture.css` because they style content within the Lecture body's `<main>` region:

- `.notes-surface` — container for the Notes section.
- `.notes-heading` — the "Notes" `<h2>`.
- `.notes-list` — the `<ul>` of existing Notes.
- `.note-item`, `.note-meta`, `.note-timestamp`, `.note-body` — per-Note display elements.
- `.notes-empty` — the empty-state caption.
- `.note-form`, `.note-form-label`, `.note-form-input`, `.note-form-submit` — the form and its parts.

The CSS itself is implementer-tunable within reason; the architectural commitment is the class names, the file location, and the rule that the form be visually distinct from the lecture body without competing for visual attention.

### Scope of this ADR

This ADR fixes only:

1. The route shape (`POST /lecture/{chapter_id}/notes` form-encoded; PRG 303 redirect; modified `GET /lecture/{chapter_id}` to fetch Notes).
2. The form-handling pattern (synchronous, no-JS, server-side validation).
3. The template surface placement (appended at the bottom of `lecture.html.j2`'s `{% block main %}`).
4. The empty-state shape and copy.
5. The multiple-Note display order (most-recent first) and per-item shape (timestamp + body, no edit/delete affordances).
6. The submit-feedback shape (full-page reload via PRG; no flash).
7. The styling location (CSS in `app/static/lecture.css`; class-name namespace).

This ADR does **not** decide:

- Edit / delete UX or routes — out of TASK-009 scope; future ADR.
- Optional Section reference UX — out of TASK-009 scope; future ADR.
- Cross-Chapter Notes views or `GET /notes` — out of scope.
- Markdown / rich-text rendering — out of scope.
- Search / filter / tagging — out of scope.
- Pagination of the Notes list — out of scope (single user, expected Note count per Chapter is small).
- A REST/JSON API for programmatic access — out of scope.
- Specific CSS pixel values, hover/focus states, or animations — implementer-tunable.

## Alternatives considered

**A. Route shape: `POST /notes` with `chapter_id` in the form body (instead of in the URL path).**
Rejected. RESTful convention places the parent resource in the URL path: a Note belongs to a Chapter, so `POST /lecture/{chapter_id}/notes` reads correctly as "create a Note under this Chapter." Putting `chapter_id` in the body works but loses the URL's self-documentation. It would also force the route to validate `chapter_id` from form input rather than from a typed FastAPI path parameter, and would foreclose the future shape `GET /lecture/{chapter_id}/notes/{note_id}` for an individual-Note URL (which a future task may want).

**B. Route shape: HTMX-style partial-reload (`POST` returns an HTML fragment that swaps into the page).**
Rejected. HTMX adds a top-level static-asset dependency and a partial-rendering surface. The latency benefit (avoid a full page reload) is imperceptible at local-dev scale (<100ms full reload). The cost is a new behavioral surface for which the project has no testing infrastructure; Playwright tests would have to cover both the no-JS form-submission path and the HTMX swap path. Synchronous PRG is the lower-cost, lower-friction default. If a future Notes follow-up surfaces a real reason (e.g., the user wants to write multiple Notes rapidly without losing scroll position), HTMX or a small targeted JS bit can be introduced under its own ADR.

**C. Route shape: client-side `fetch()` returning JSON, with manual DOM update.**
Rejected. Same drawback as HTMX (new behavioral surface, new testing infrastructure) plus duplicate rendering logic (server-side template + client-side JS rendering). The project's "small local FastAPI + flat static assets" shape (ADR-003) does not call for a JSON API.

**D. Template surface: Notes panel injected near the Mandatory/Optional badge at the top of the Lecture page.**
Rejected. Pushes the lecture content below the fold; contradicts manifest §3's consumption-first prioritization. The badge area is editorial chrome (Chapter title, designation); mixing it with a user-input surface conflates two different roles.

**E. Template surface: collapsible side panel (third column to the right of the lecture body).**
Rejected. Forces a layout redesign of ADR-008's two-column CSS Grid (`grid-template-columns: minmax(220px, 18rem) minmax(0, 1fr)`). Three-column layouts are real architectural commitments; introducing one for a single new surface is over-investment. Bottom-of-page placement satisfies the same UX intent (Notes are a separate region from the lecture body) without redesigning the page layout.

**F. Template surface: separate page at `/lecture/{chapter_id}/notes`.**
Rejected. Forces a navigation round-trip every time the user wants to write a Note while reading. The user's mental model is "I'm reading Chapter X and I want to write a Note about Chapter X" — those two intents are co-located on one page, not split across two URLs. A separate page also fights manifest §3 (consumption + retention work in the same surface).

**G. Form-handling pattern: store form state in `localStorage` so half-written Notes survive an accidental reload.**
Rejected. Adds a JavaScript surface (the project has no JS today) and a state-management story (when does `localStorage` get cleared?). For minimum-viable, the user accepts that a half-written Note is lost if they navigate away. Adding draft-recovery is a follow-up if a real workflow surfaces.

**H. Empty-state: only the form, with `placeholder` text inside the textarea conveying the empty state.**
Considered. The textarea's `placeholder="Write a note about this chapter..."` already conveys "this is where Notes go." Rejected mildly: an explicit caption (`<p class="notes-empty">No notes yet...</p>`) above the form is more informative than relying on placeholder text alone, and placeholder text disappears when the user starts typing — which removes the only signal that the empty state is the empty state. A separate caption is the cleaner shape.

**I. Empty-state: onboarding hint with examples ("Try jotting down a question to revisit, a definition to memorize, or a code snippet you want to remember").**
Rejected. Editorial-grade onboarding contradicts manifest §5 (no LMS features; this is a personal tool). The author already knows what Notes are for.

**J. Multiple-Note display: oldest-first (chronological order, like a journal).**
Considered. Most-recent-first is chosen because the most-recently-written Note is the one the user is most likely to want to verify (just-saved feedback) and the one they're most likely to want to reference next. An older Note that is still relevant won't be missed (it's still on the page); a just-saved Note appearing far below the fold would be invisible feedback.

**K. Multiple-Note display: only the most-recent Note shown, with a "show all" expander.**
Rejected. Hides the multi-Note nature of the surface from the user; contradicts the architecture of ADR-022 (which permits multi-Note-per-Chapter explicitly). If the surface eventually grows to dozens of Notes per Chapter, pagination or scroll-fading is a follow-up; for now a flat list is the right shape.

**L. Submit-feedback: redirect with URL fragment `#note-saved` and a JS `onload` handler that highlights the new Note.**
Rejected. Adds a JS surface for visual feedback that the natural new-Note-at-top placement already provides. Failure mode: if JS fails to load, the URL fragment confuses the browser's scroll-into-view behavior. Synchronous PRG without a fragment is the cleaner shape.

**M. Submit-feedback: a flash message in a session/cookie store ("Note saved").**
Rejected. Forces a session/cookie story (manifest §6 single-user; no sessions). The new-Note-at-top placement is sufficient feedback.

**N. Validation: client-side only (`required` attribute on the `<textarea>`), no server-side rejection.**
Rejected. A malicious or accidental empty POST (e.g., from `curl` or a browser-extension auto-form-filler) would write an empty Note. Server-side validation is the authority; client-side validation is an ergonomic shortcut for the common path.

## My recommendation vs the user's apparent preference

The TASK-009 task file forecasts the architect's choice as "form-encoded `POST /lecture/{chapter_id}/notes` returning a redirect to `GET /lecture/{chapter_id}`. Simple, no JS dependency, preserves the FastAPI route/template shape established by ADR-003." This ADR aligns with that forecast, with the additional commitments above (PRG via 303 specifically, bottom-of-page placement, most-recent-first list order, plain-text body with autoescape, no edit/delete in this iteration).

One area where this ADR pushes mildly beyond the task's forecast: the task lists template-surface placement as "(a) bottom of the page below all Sections, (b) top of the page near the Mandatory/Optional badge, (c) collapsible side panel" and asks the architect to pick. This ADR commits to (a) — bottom — and explains why above. If the human reads the page differently (e.g., wants the Notes form near the top so it is always above-the-fold and doesn't require scrolling past a long lecture), this is the place to push back at the gate.

A second area: the task forecasts "submit-feedback: full-page reload (simplest; works without JS)" and this ADR commits to that. The architect's read is that this is a fully aligned forecast — no push beyond the user's apparent direction. The third area: this ADR commits to **no Markdown rendering** even though Note bodies are plain text by default. The TASK-009 file's "Out of scope" section explicitly lists "Markdown / rich-text formatting / code-block support inside Notes" — so the architect is consuming the user's stated direction here, not pushing beyond it.

I am NOT pushing back on:

- The single-user posture (manifest §5 / §6 / §7) — honored: no auth, no `user_id` in route handlers.
- The asynchronous-AI absolute (manifest §6) — orthogonal: Notes are not AI work.
- The Lecture-source-read-only rule (manifest §6, MC-6) — honored: the Notes route writes to `data/notes.db`, never to `content/latex/`.
- The ADR-006 navigation surface — preserved: the rail is unchanged.
- The ADR-008 CSS architecture — extended faithfully: new classes go in `lecture.css` per the prefix convention.
- TASK-009's "Out of scope" enumeration (edit, delete, optional Section, multi-Chapter view, Markdown, search/filter/tags) — honored.

## Manifest reading

Read as binding for this decision:

- **§3 Primary Objective.** Notes are one of three named consumption pillars; the surface must be readable and direct. The bottom-of-page placement and PRG redirect satisfy this.
- **§5 Non-Goals.** "No mobile-first" bounds the responsive obligation (the form works on a desktop browser). "No LMS" bounds the editorial scope (no onboarding tutorials, no per-Note metadata beyond timestamp). "No AI tutor / chat" bounds the form behavior (no AI assistance during Note authoring). "No multi-user" bounds the route layer (no auth, no `user_id` in URL or body). "No remote deployment" bounds the local-only POST handling.
- **§6 Behaviors and Absolutes.** "Single-user" is honored — no auth check on the POST route; the Note's owner is implicit. "AI work asynchronous" is **orthogonal** — Notes are not AI work; synchronous form submission is correct. "Mandatory and Optional content honored" is preserved (the Lecture page already displays the badge; Notes do not displace or hide the designation). "A Lecture has a single source" is preserved (Notes are a separate entity from the Lecture; the Lecture's source remains read-only).
- **§7 Invariants.** "Every Note … persists across sessions" — the PRG redirect's GET path reads the Note from persistence (ADR-022); the Note is visible after a server restart by virtue of being read from disk on every GET. "A Note is bound to exactly one Chapter" — the route shape encodes this in the URL path (`/lecture/{chapter_id}/notes`). "May optionally reference one Section" — deferred to a follow-up; this ADR does not foreclose adding a `section_id` field to the form later.
- **§8 Glossary.** Note ("user-authored content bound to a Chapter, optionally referencing one Section. Editable by the user. Never auto-generated.") — bound the route's input validation (the body is user-authored, not auto-generated; no AI-generation entry point exists). "Editable by the user" is the architect's read on why edit/delete will eventually need to land — but a follow-up, not this task.

No manifest entries flagged as architecture-in-disguise.

## Conformance check

- **MC-1 (No direct LLM/agent SDK use).** Orthogonal — Notes have no AI surface. Compliance preserved.
- **MC-2 (Quizzes scope to exactly one Section).** Orthogonal — no Quiz route introduced.
- **MC-3 (Mandatory/Optional designation).** Orthogonal — the Lecture page's designation badge is unchanged by this ADR. The Notes section appears below the Sections; it does not affect or hide the designation. Compliance preserved.
- **MC-4 (AI work asynchronous).** Orthogonal — Notes are not AI work. The synchronous POST + PRG redirect is the correct shape; treating it as a violation would be a misread of MC-4's scope.
- **MC-5 (AI failures are surfaced, never fabricated).** Orthogonal — no AI in this surface.
- **MC-6 (Lecture source read-only).** Honored. The Notes route writes only via `app/persistence/` (ADR-022) which targets `data/notes.db`. The route does not open any file under `content/latex/`. The Lecture-page GET still reads `content/latex/{chapter_id}.tex` for read only. Compliance preserved.
- **MC-7 (Single user).** Honored. The POST route accepts no auth, has no `user_id` in path or body, has no per-user partitioning. The route handler does not check session state, does not consult a user store, does not partition Notes by any per-user key. Compliance preserved (architecture portion now active per ADR-022 and reinforced here).
- **MC-8 (Reinforcement loop preserved).** Orthogonal — no Quiz machinery.
- **MC-9 (Quiz generation user-triggered).** Orthogonal.
- **MC-10 (Persistence boundary).** Honored. The route handler in `app/main.py` calls only the typed public functions exposed by `app/persistence/notes` (`create_note`, `list_notes_for_chapter`); it does not import `sqlite3`, does not contain SQL string literals, and does not receive raw database rows. Compliance preserved (architecture portion now active per ADR-022 and reinforced here).
- **UI-1 / UI-2 / UI-3 (ui-task-scope).** UI-1 satisfied at the task level (TASK-009 declares the Notes UI surface). UI-2 satisfied by this ADR (the styling target is named — `app/static/lecture.css` — and the class-name namespace is committed). UI-3 satisfied by the diff naming `app/static/lecture.css` (modified) and listing the rules added.
- **UI-4 (rendered-behavior verification gate).** Honored. ADR-010's Playwright harness covers the round-trip verification; TASK-009's acceptance criterion 9 ("at least one Playwright test exercises the round-trip: load Lecture → submit Note → reload Lecture → assert Note visible") binds the implementer to add the Playwright test, and ADR-010's last-run-screenshot review is the human gate for the visual surface.

Previously-dormant rule activated by this ADR: none new. (ADR-022 activates MC-10's architecture portion and MC-7's architecture portion; this ADR consumes both.)

## Consequences

**Becomes possible:**

- A user can write a Note bound to a Chapter, the Note persists across server restarts, and the Note is visible on subsequent visits to that Chapter's Lecture page.
- The Lecture page becomes a one-stop surface for "consume + capture" — read the lecture, write a Note, read it back later — without navigating away.
- Multiple Notes per Chapter accumulate over time, with the most-recent Note at the top of the list.
- The form works without JavaScript, on any browser the FastAPI app supports.
- Future Notes follow-ups (edit, delete, optional Section reference, multi-Chapter view) extend this surface incrementally without re-deciding the route shape or the template placement.
- The `notes` template variable is a clean integration point for any future surface that needs to display Notes (e.g., a future Mandatory-only view that includes Notes).

**Becomes more expensive:**

- The `lecture.html.j2` template is now ~30 lines longer, with both the empty-state and populated-state branches plus the form. Mitigation: the additions are localized to one new `<section class="notes-surface">` block; the existing Lecture-rendering content is untouched.
- The Lecture-page GET route now performs an extra database query per request (`list_notes_for_chapter`). Mitigation: SQLite local read is sub-millisecond at this data scale; the single-user / single-process operating model has no contention.
- Adding edit/delete affordances requires extending the per-Note item template, the route shape, and the persistence module. Mitigation: those are exactly the follow-ups TASK-009 defers; the cost is in the right place.

**Becomes impossible (under this ADR):**

- A Note created without an associated Chapter ID. The route shape forces the binding.
- A JavaScript-required form submission. The form works without JS by construction; adding a JS-required surface would be a superseding ADR.
- Auth-gated Note creation. Manifest §5/6 forbids; this ADR codifies the no-auth posture at the route layer.
- A Note whose author is recorded. No `user_id` is ever sent or stored.

**Future surfaces this ADR pre-positions:**

- Edit/delete: extends per-`<li class="note-item">` to include action buttons; adds `POST /lecture/{chapter_id}/notes/{note_id}/edit` (or PUT/DELETE if a future ADR commits to method-overloading); reuses the form pattern.
- Optional Section reference: adds a `<select name="section_id">` to the form populated from the Chapter's Section list; route handler validates `section_id` against that Chapter's Sections.
- Cross-Chapter Notes view: adds a `GET /notes` route + template; reuses `list_notes_for_chapter` factored to `list_notes(filter)` or similar.
- Markdown rendering: replaces `{{ note.body }}` with `{{ note.body | markdown_safe }}` once a Markdown library and a sanitization story are committed under their own ADR.
- Quiz integration: the same template-extension pattern (a `<section class="quiz-surface">` block in `lecture.html.j2`) hosts the per-Section "Quiz this Section" affordance when Quiz-bootstrap lands. The pattern is established by this ADR.

**Supersedure path if this proves wrong:**

- If the bottom-of-page placement proves un-discoverable (the user keeps missing the Notes section because lectures are too long) → a future ADR moves the surface or adds a "go to Notes" affordance near the top. Cost: template edit + CSS edit; bounded.
- If synchronous PRG proves too friction-heavy (e.g., a user-research signal that the full-page reload is jarring) → a future ADR introduces HTMX or a small JS swap. Cost: new dependency; bounded.
- If the form-encoded route shape conflicts with a future need for programmatic Note creation (e.g., a future tooling integration) → a future ADR adds a parallel `POST /api/notes` JSON route. The HTML form route remains. Cost: route addition; non-blocking.
