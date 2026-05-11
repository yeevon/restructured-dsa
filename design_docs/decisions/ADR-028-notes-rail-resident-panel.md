# ADR-028: Supersedure of ADR-023 §Template-surface — Notes section moves from bottom-of-page to rail-resident panel

**Status:** `Superseded by ADR-029` (§Rail-integration and the part of §Template-surface that placed `<section class="rail-notes">` inside `_nav_rail.html.j2` only — see ADR-029 for the move to a right-hand rail in a three-column layout. The route shape, form-handling pattern, validation, multiple-Note display order, submit-feedback shape, empty-state copy, no-edit/delete, no-Markdown, persistence integration, the textarea-sizing *approach* (`rows="3"` + `field-sizing: content` + `resize: vertical` + no JS), the removal of the bottom-of-page Notes section in `lecture.html.j2`, the `notes` → `rail_notes_context` template-variable rename, the `{% if rail_notes_context %}` guard, and the load-bearing principle "visibility follows scroll-position-cost" all remain Accepted as written by this ADR.)
Original Acceptance: Auto-accepted by /auto on 2026-05-10
**Date:** 2026-05-10
**Task:** TASK-011
**Resolves:** `design_docs/project_issues/notes-surface-placement-visibility.md`
**Supersedes:** `ADR-023` (§Template-surface only — the route shape, the form-handling pattern, the empty-state shape, the multiple-Note display order, the submit-feedback shape, and the validation rules all remain Accepted as written by ADR-023; the styling-file ownership shifts per ADR-008's prefix convention because the surface moves from `lecture.html.j2`'s body to `_nav_rail.html.j2`)
**Superseded by:** `ADR-029` (§Rail-integration / §Template-surface portion only — Auto-accepted by /auto on 2026-05-11, TASK-012)

## Context

ADR-023 (Accepted, 2026-05-10) committed to placing the Notes section at the **bottom** of `lecture.html.j2`'s `{% block main %}`, after all rendered Sections. The `/auto` cycle gated ADR-023 to Accepted; the implementer shipped the surface; the reviewer issued `READY-TO-COMMIT`; the human committed.

At commit-gate review the human filed `design_docs/project_issues/notes-surface-placement-visibility.md` (Open, surfaced 2026-05-10), with the following framing **(quoted verbatim from the issue file as the empirical evidence justifying this supersedure):**

> "It def. needs to be moved. Does it need to be moved now? Not really — we're still in build mode adding other features. The rest of the Notes features [edit / delete / Markdown / Section-ref / multi-Note polish] probably has higher priority. As long as moving its location isn't a sticky point, it should be prioritized accordingly."

The issue file expanded the diagnosis with empirical chapter-length measurements:

> **Empirical chapter lengths (LaTeX source, 12 chapters):**
>
> | Stat | LaTeX lines | LaTeX bytes |
> |---|---|---|
> | Shortest (`ch-12-sets`) | 1,588 | 67 KB |
> | Longest (`ch-03-intro-to-data-structures`) | 3,437 | 143 KB |
> | Mean | ~2,144 | ~92 KB |
> | Total (corpus) | 25,727 | 1,103 KB |
>
> Rendered HTML for `ch-01-cpp-refresher` is **118 KB** — order of 30+ viewport heights of scroll on a typical laptop. The Notes surface, appended after all Sections, is therefore many screens below the reading flow. A learner finishes reading and must scroll past the entire chapter to reach a Notes affordance that ADR-023 commits is visible "on every Chapter page."
>
> **The rail (`_nav_rail.html.j2` + ADR-008 `base.css`) is already `position: sticky; top: 0; max-height: 100vh`** — visible the whole way down. With 12 chapter entries (Mandatory + Optional groups), it occupies roughly 30–40% of viewport height; the remaining 60–70% is empty real estate that scrolls with the page.
>
> **The mismatch:** a sticky-and-mostly-empty rail is the natural home for a per-chapter persistent affordance; the bottom of a 30-screen page is not.

The issue's Decide-when explicitly named "the next Notes-related task" as the home for the supersedure. TASK-011 is partly Notes-related (the rail-resident Notes panel is the issue's Option 1 forecast) and is the natural composition point with the chapter-progress derived display (which also lives in the rail). This ADR is the supersedure the issue forecasted.

ADR-023's reasoning at the time was correct given what was known then: the architect chose bottom-of-page placement on the basis that "the Lecture's primary content (the lecture itself) should be the visual focus when the page loads. Putting Notes at the top of `<main>` would push the lecture below the fold and contradict manifest §3 (consumption-first)." This reasoning held in the abstract. **It failed empirically once the surface shipped and the human encountered it on the actual Chapter lengths.** The architectural lesson the issue surfaces is that **affordance visibility must be designed against the actual content scale, not the abstract layout model.** A "bottom-of-page" surface at 1-screen scale is reachable; at 30-screen scale it is invisible. This ADR encodes that lesson as the load-bearing principle: **visibility follows scroll-position-cost.**

The decision space (taken from the project_issue's enumerated options):

- **Rail integration shape:** Notes panel inside `_nav_rail.html.j2` below the chapter list with natural flow stacking (Option 1), or explicit 50/50 vertical partition inside the rail (Option 2), or floating/anchored panel (Option 3 — rejected because it requires JS), or keep status quo (Option 4 — rejected by the human's framing).
- **Per-Chapter scoping on the landing page:** when the user is on `GET /` (no Chapter context), the rail still renders. Three options for the Notes panel: hide it, show a "select a Chapter" empty-state, or omit it from the landing page's rail entirely.
- **Rail-width constraints on the textarea:** the rail is `minmax(220px, 18rem)`. The current `<textarea rows="6">` becomes cramped. Options: reduce default `rows`, allow vertical growth via `min-height` + `field-sizing: content` (limited browser support), or accept the cramped default and treat rail-Notes as quick-capture.
- **What replaces the bottom-of-page Notes section in `lecture.html.j2`:** remove entirely, keep an empty placeholder, or keep a "see rail" pointer.
- **CSS file ownership:** all rail-resident Notes CSS in `base.css` (Notes is now rail-resident → rail-styling-file), or split between `base.css` and `lecture.css`.

## Decision

### Rail integration — Notes panel inside `_nav_rail.html.j2`, below the chapter list, natural flow stacking (Option 1)

The Notes UI is rendered as a new `<section class="rail-notes">` inside `_nav_rail.html.j2`, **after** the existing `<div class="nav-rail-inner">` block (which contains the Mandatory/Optional chapter lists). Concretely, the rail partial structure becomes:

```html
<div class="nav-rail-inner">
  <h2 class="nav-section-label" data-designation="Mandatory">Mandatory</h2>
  <ul class="nav-chapter-list">
    {# existing per-Chapter rows with the new ADR-026 progress decoration #}
  </ul>

  <h2 class="nav-section-label" data-designation="Optional">Optional</h2>
  <ul class="nav-chapter-list">
    {# existing per-Chapter rows with the new ADR-026 progress decoration #}
  </ul>
</div>

{% if rail_notes_context %}
<section class="rail-notes" aria-labelledby="rail-notes-heading">
  <h2 id="rail-notes-heading" class="rail-notes-heading">Notes</h2>
  {% if rail_notes_context.notes %}
    <ul class="rail-notes-list">
      {% for note in rail_notes_context.notes %}
        <li class="rail-note-item">
          <time class="rail-note-timestamp"
                datetime="{{ note.created_at }}">{{ note.created_at }}</time>
          <div class="rail-note-body">{{ note.body }}</div>
        </li>
      {% endfor %}
    </ul>
  {% else %}
    <p class="rail-notes-empty">No notes yet — write the first one below.</p>
  {% endif %}

  <form class="rail-note-form" method="post"
        action="/lecture/{{ rail_notes_context.chapter_id }}/notes">
    <label for="rail-note-body" class="rail-note-form-label">New note</label>
    <textarea id="rail-note-body" name="body" class="rail-note-form-input"
              rows="3" required maxlength="65536"
              placeholder="Quick note for this chapter..."></textarea>
    <button type="submit" class="rail-note-form-submit">Save</button>
  </form>
</section>
{% endif %}
```

**Option 2 (explicit 50/50 vertical partition) is rejected.** Rationale:

- A 50/50 partition forces a layout commitment that varies with the rail's actual content (12 chapters today; potentially ~20 if Optional grows). A natural-flow stacking adapts to whatever the chapter list size is.
- The chapter list is the rail's primary navigation function; Notes is a secondary write-surface. A 50/50 partition over-weights Notes relative to its navigation role.
- Natural stacking with a max-height + overflow-y on the rail (the existing `max-height: 100vh` per ADR-008's `.lecture-rail`) lets the chapter list and Notes panel co-exist without prescriptive ratios. If the rail content exceeds the viewport, the rail itself scrolls — the existing `position: sticky` behavior handles that.

The `<section class="rail-notes">` lives outside `<div class="nav-rail-inner">` so the existing rail-inner styling (which currently establishes the chapter-list visual rhythm) is unchanged. The Notes section is its own stacked block under `.lecture-rail` (the parent `<nav>` element).

### Per-Chapter scoping — show Notes panel only when a Chapter context exists; omit from landing page

The Notes panel renders **only** when the rendering route has a Chapter context (i.e., on `GET /lecture/{chapter_id}`). On `GET /` (the landing page), the Notes panel is **omitted** from the rail entirely. The template uses a `{% if rail_notes_context %}` guard around the entire `<section class="rail-notes">` block.

The `rail_notes_context` template variable is a structured object (or `None` on the landing page) populated by the route handler:

```python
class RailNotesContext:
    chapter_id: str
    notes: list[Note]   # ordered most-recent-first per ADR-023 §Multiple-Note display
```

The Lecture-page route (`GET /lecture/{chapter_id}`) populates `rail_notes_context` with the current Chapter's `chapter_id` and the result of `list_notes_for_chapter(chapter_id)` (consumed unchanged from ADR-023). The landing-page route (`GET /`) sets `rail_notes_context = None`.

**Three options were considered for the landing-page case:**

- **Hide the panel** (CSS `display: none`). Rejected — adds a CSS rule that hides DOM the template still renders; wasteful and confusing.
- **Show a "select a Chapter to take notes" empty-state.** Rejected — the landing page's primary purpose is chapter selection; an "empty Notes" placeholder competes for visual attention with the chapter list itself. The user is already being told "select a Chapter" by the rail's chapter-list itself; a duplicate hint adds noise.
- **Omit the panel entirely (chosen).** Cleanest shape: the landing page's rail is the chapter-list-only rail (the original ADR-006 surface); the Lecture page's rail adds the Notes panel below. The `{% if rail_notes_context %}` guard makes the conditional explicit in the template.

The bottom-of-page Notes section in `lecture.html.j2` (per ADR-023) is **removed entirely** — see "Removal of bottom-of-page Notes section" below.

### Rail-width constraints on the textarea — reduce default `rows` to 3; CSS `field-sizing: content` for browsers that support it; no JavaScript needed

The rail is `minmax(220px, 18rem)` (per ADR-008). The current Notes textarea is `<textarea rows="6">` from ADR-023, which is cramped at the rail's narrow width. This supersedure:

- **Reduces default `rows` from 6 to 3.** Three rows is a "quick-capture" shape that fits comfortably in the rail without overwhelming the chapter-list above it. Manual experimentation by the implementer may settle on a different value within the architectural commitment that the textarea fit comfortably at the rail's narrowest width (`220px`) without horizontal overflow or button clipping.
- **Adds CSS `field-sizing: content` (CSS Working Draft, supported by recent Chrome/Edge/Safari)** to allow the textarea to grow vertically as the user types, with a `min-height` matching the 3-row default and a `max-height` capping growth at ~12 rows (or `40vh`, implementer's call). On browsers that do not support `field-sizing: content`, the textarea remains at the 3-row default; the user can still drag-resize via the standard browser-native resize handle (`resize: vertical`). **No JavaScript.**
- **`width: 100%` (or equivalent flex/grid sizing)** on the textarea so it fills the rail's content width.
- **The submit button** (`Save`, shortened from `Save note` per ADR-023's text to fit the narrower rail) is full-width below the textarea, not inline next to it.

The architectural commitment is:

- The textarea is usable at `220px` rail width.
- The textarea grows on browsers that support `field-sizing: content`; falls back gracefully on browsers that do not.
- No JavaScript is introduced — `field-sizing: content` + `resize: vertical` is a clean CSS-only solution here, so none is needed. (Following the no-JS form-handling shape ADR-023 / ADR-025 / ADR-027 used because it was clean there too — not a project rule; see ADR-035.)

The specific CSS values (border, padding, exact `rows`, max-height) are implementer-tunable.

The maximum body length (64 KiB per ADR-023 §Validation) is unchanged; the `maxlength="65536"` HTML attribute remains.

### Removal of the bottom-of-page Notes section in `lecture.html.j2`

The existing `<section class="notes-surface">` block in `lecture.html.j2`'s `{% block main %}` is **removed entirely** (Option (a) from the task file's enumeration). The Notes section is now rail-resident only; keeping a duplicate or a "see rail" pointer at the bottom of the page would (a) duplicate UI for no benefit, (b) leave dead code in the template, (c) confuse the user about which surface is canonical.

The `notes` template variable passed to `lecture.html.j2` (per ADR-023) is **renamed** in the route handler to `rail_notes_context` (a structured object containing both the `notes` list and the `chapter_id` needed by the rail's form action URL). Templates that referenced `notes` directly are updated. The template variable is consumed by `_nav_rail.html.j2` (which is included via `base.html.j2`'s extends-chain), not by `lecture.html.j2` itself.

### CSS file ownership — rail-resident Notes CSS lives in `base.css`

Per ADR-008's class-name-prefix convention, classes prefixed with `nav-*`, `index-*`, `page-*`, and `lecture-rail` live in `base.css`. The new rail-resident Notes classes (`rail-notes`, `rail-notes-heading`, `rail-notes-list`, `rail-note-item`, `rail-note-timestamp`, `rail-note-body`, `rail-notes-empty`, `rail-note-form`, `rail-note-form-label`, `rail-note-form-input`, `rail-note-form-submit`) all use the **`rail-*` prefix** — a new prefix that explicitly maps to `base.css` because the surface they style is rail-resident.

The **old `notes-*` and `note-*` classes** (from ADR-023 — `.notes-surface`, `.notes-heading`, `.notes-list`, `.note-item`, `.note-meta`, `.note-timestamp`, `.note-body`, `.notes-empty`, `.note-form`, `.note-form-label`, `.note-form-input`, `.note-form-submit`) are **removed from `lecture.css`** along with the `<section class="notes-surface">` block they styled. This is the cleanup half of the supersedure: ADR-023 placed the Notes classes in `lecture.css` because the surface lived in the Lecture body; this supersedure moves the surface to the rail and the classes follow.

ADR-008's class-name-prefix rule is honored: `lecture.css` retains all `lecture-*`, `section-*`, `callout-*`, `designation-*` rules; `base.css` gains the new `rail-*` Notes rules. No file-ownership boundary is muddied.

### What is **NOT** changed by this supersedure (still per ADR-023)

ADR-023 made multiple decisions; this supersedure targets only §Template-surface (and the related styling-file ownership shift forced by the surface move). The following remain Accepted as written by ADR-023:

- **Route shape.** `POST /lecture/{chapter_id}/notes` form-encoded; PRG 303 redirect to `GET /lecture/{chapter_id}`. Unchanged.
- **Form-handling pattern.** Synchronous PRG; no JavaScript needed for this surface. Unchanged.
- **Validation.** Route handler trims body; rejects empty/whitespace-only with 400; rejects unknown `chapter_id` with 404; rejects bodies > 64 KiB with 413. Unchanged.
- **Multiple-Note display order.** Most-recent-first (`ORDER BY created_at DESC`). Unchanged.
- **Submit-feedback shape.** Full-page reload via PRG; no flash, no toast, no URL fragment. Unchanged. (The PRG redirect now causes the rail-resident Notes panel to re-render with the new Note at the top of the list — the same feedback shape, in the new surface.)
- **Empty-state copy.** "No notes yet — write the first one below." Unchanged in shape; lives in the new `rail-notes-empty` class instead of the old `notes-empty` class.
- **No edit/delete affordances.** Out of scope per ADR-023; remains out of scope.
- **No Markdown rendering.** Plain text via Jinja2 autoescape. Unchanged.
- **Persistence integration.** Route handler calls `create_note` / `list_notes_for_chapter` from `app/persistence/`. Unchanged.

The supersedure surface is narrow: §Template-surface and the CSS-file ownership that follows from it. The route shape, form-handling, validation, persistence integration, and editorial copy all stand.

### Load-bearing principle: visibility follows scroll-position-cost

This supersedure encodes a project-wide principle for future placement decisions:

> **Affordance visibility must be designed against the actual content scale; visibility on a long surface follows scroll-position-cost. A surface placed where the user has to scroll past the entire content to reach it is, at scale, invisible.**

Concretely: at 1-screen Chapter scale (a hypothetical short Chapter), the bottom-of-page Notes section is reachable in one or zero scrolls. At 30-screen Chapter scale (the actual corpus per the issue's measurements), the bottom-of-page Notes section is invisible — the learner finishes reading and the surface is many screens below their reading position. The rail's `position: sticky` real estate is the only surface in the project that is reachable from any scroll position; persistent per-Chapter affordances that need to be visible at any time belong there.

Future surfaces (Notification badges per manifest §8; Quiz-status indicators if Quiz-bootstrap surfaces them at the page level; any future "your progress so far" affordance) inherit this principle. Reviewers should reject any new affordance placement that is justified by abstract layout reasoning without naming the actual scroll-position-cost the placement imposes.

The principle is paired with ADR-027's load-bearing principle ("action affordances follow the cognitive sequence"). Both arise from the same root cause (post-commit human review of placement quality at 12-Chapter, ~30-screen-per-Chapter scale) and together constitute the project's **placement-quality principles** for future surface decisions.

### Test-writer pre-flag — placement assertions in existing tests will fail by design

Per the user-memory entry **"Test updates forced by Accepted ADRs are routine"** and per the TASK-011 task file's "Architectural concerns" section, the following test updates are anticipated when this supersedure becomes Accepted:

- **Pytest tests** that asserted the rendered Lecture HTML contains `<section class="notes-surface">` after the last Section will now fail. The test-writer amends them to assert the Notes section appears in the rail's HTML (specifically inside `_nav_rail.html.j2`, conditional on `rail_notes_context` being non-`None`), not in the Lecture body's `{% block main %}`.
- **Pytest tests** that asserted classes named `.notes-surface`, `.notes-heading`, `.notes-list`, `.note-item`, `.note-form`, etc., will fail. The test-writer amends them to assert the new `rail-*` classes (`rail-notes`, `rail-notes-heading`, `rail-notes-list`, `rail-note-item`, `rail-note-form`, etc.).
- **Playwright tests** for the Notes round-trip (load Lecture → submit Note → reload Lecture → assert Note visible) will need updates to locate the form by the new selector and to assert the rendered Note appears in the rail-resident list, not in the bottom-of-page list.
- **Tests asserting the landing page (`GET /`)** does not render the Notes panel: this is a new test the test-writer adds (or amends an existing landing-page test) to assert the rail on `/` does not contain the `rail-notes` section.

**The test-writer should NOT raise PUSHBACK for these failures.** They are the **routine ADR-driven test evolution** the user-memory entry describes. The test-writer's correct response is to amend the affected assertions to match the new surface, exactly as the user-memory entry prescribes:

> "When implementer ESCALATION is 'test fails because Accepted ADR-NNN changed the architecture,' amend the test directly; don't open project_issues or park the task."

The same routing applies preemptively to the test-writer phase: the supersedure ADR has named the surface change as the architecture change; tests that depend on the prior surface are amended at the test-writer phase, not flagged as bugs.

### Scope of this supersedure ADR

This ADR fixes only:

1. The relocation of the Notes UI from the bottom of `lecture.html.j2`'s `{% block main %}` to a new rail-resident section in `_nav_rail.html.j2`.
2. The per-Chapter scoping rule (panel renders only when a Chapter context exists; omitted from the landing page).
3. The textarea sizing approach (default `rows="3"`; `field-sizing: content` for browsers that support it; `resize: vertical` fallback; no JavaScript).
4. The complete removal of the bottom-of-page `<section class="notes-surface">` block in `lecture.html.j2` and its corresponding CSS in `lecture.css`.
5. The CSS class rename from `.notes-*` / `.note-*` to `.rail-notes-*` / `.rail-note-*`, with the new classes living in `base.css` per ADR-008's prefix convention.
6. The template-variable rename from `notes` to `rail_notes_context` (a structured `{chapter_id, notes}` object on the Lecture page; `None` on the landing page).
7. The encoding of the load-bearing placement-quality principle: visibility follows scroll-position-cost.
8. The test-writer pre-flag for routine ADR-driven test amendment.

This ADR does **not** decide:

- Edit / delete / Markdown / Section-reference Notes follow-ups — still deferred from ADR-023's "Out of scope"; future tasks.
- The exact CSS pixel values, border colors, or `max-height` for the rail-resident textarea — implementer-tunable within the architectural commitments above.
- A "expand to full-page Notes" affordance for longer-form Notes — out of scope; if rail-Notes proves too cramped for some workflows, a future ADR introduces a "compose in full surface" overlay.
- Mobile responsiveness for the rail-Notes panel — manifest §5 (no mobile-first) bounds the obligation.
- Any change to the Notes route, validation, persistence, or response shape — all retained from ADR-023.

## Alternatives considered

**A. Option 2 from the project_issue: Split rail with explicit 50/50 (or other ratio) partition.**

Rejected. A fixed ratio over-prescribes the layout for content that varies (12 chapters today; potentially ~20). Natural-flow stacking adapts to whatever the chapter list size is, with the rail's existing `max-height: 100vh` and overflow-y handling rail-content-exceeds-viewport cases. The chapter list is the rail's primary navigation function; Notes is secondary; a 50/50 partition over-weights Notes.

**B. Option 3 from the project_issue: Floating/anchored Notes panel pinned to a viewport corner.**

Rejected. Requires either (a) JavaScript to handle show/hide and positioning, (b) a fixed-position element that competes with content for screen real estate, or (c) absolute positioning that interferes with the existing two-column grid (ADR-008). The rail-resident shape uses existing infrastructure (the rail is already sticky) without new behavior surfaces, so this option's overhead buys nothing here. (Rejected on cost-vs-benefit, not because client-side code is forbidden — see ADR-035.)

**C. Option 4 from the project_issue: Keep ADR-023's bottom-of-page placement (status quo).**

Rejected by the human's framing. The empirical evidence (118 KB rendered HTML, 30+ viewport heights of scroll) demonstrates the bottom-of-page surface is invisible at the actual content scale. The Decide-when text named "the next Notes-related task" as the home for the supersedure; TASK-011 is partly Notes-related (rail-resident panel is Option 1 of the issue's enumerated forecasts).

**D. Per-Chapter scoping: show a "select a Chapter to take notes" empty-state on the landing page.**

Rejected. The landing page's primary purpose is chapter selection; the rail's chapter-list itself is the "select a Chapter" affordance. A duplicate hint inside an empty Notes panel adds noise without informational value. Omitting the Notes panel from the landing page entirely is the cleaner shape.

**E. Per-Chapter scoping: hide the Notes panel on the landing page via CSS (`display: none`) but render the DOM.**

Rejected. Renders DOM the user never sees, wastes bytes, and adds a CSS rule that hides what the template still produces. The `{% if rail_notes_context %}` template guard is the cleaner shape.

**F. Textarea: keep `rows="6"` and accept horizontal scroll inside the textarea on narrow rails.**

Rejected. The textarea would be cramped in a way that defeats the purpose of moving Notes to the rail (visibility + usability). A `rows="3"` default with `field-sizing: content` for vertical growth is the right shape: comfortable at default, adaptive as the user types.

**G. Textarea: introduce JavaScript for auto-resize (e.g., `auto-resize` library or a tiny inline script).**

Rejected. CSS `field-sizing: content` (with `resize: vertical` as the fallback) is a clean CSS-only solution for textarea auto-resize, so the JS-and-asset-build-machinery this would pull in is unwarranted *here*. (Rejected because the CSS solution is clean and sufficient, not because client-side code is off the table — see ADR-035; a future surface with a real need for JS introduces the infrastructure via its own ADR.)

**H. Replace bottom-of-page Notes section in `lecture.html.j2` with a "see rail" pointer instead of removing entirely.**

Rejected. The pointer would be dead weight: it tells the user the Notes are in the rail (which the user can see), and it occupies the bottom-of-page space that should be reclaimed for the new bottom-of-Section completion affordance per ADR-027 (which lives at the end of each Section, not at the page level — but the page-level real estate is freed regardless). Removing entirely is the clean shape.

**I. Keep the `notes-*` class names; just move the surface and re-style.**

Rejected. ADR-008's class-name-prefix convention maps `lecture-*`, `section-*`, etc. to `lecture.css` and `nav-*`, `index-*`, etc. to `base.css`. The `notes-*` prefix was chosen by ADR-023 because the surface lived in the Lecture body. Now that the surface lives in the rail, the class names should reflect that home (`rail-notes-*`). Keeping the old prefix would muddy the file-ownership rule and confuse future readers. The cost of renaming is bounded (CSS file edit + template file edit); the benefit (clean prefix-to-file mapping) is permanent.

**J. CSS file ownership: split — Notes-panel layout in `base.css`, individual note-item styling in `lecture.css`.**

Considered. The split would minimize churn in `lecture.css` (some `.note-item`, `.note-body` rules could stay). **Rejected** because (a) it muddies the prefix rule (rail-resident things in the rail-styling file is the cleaner principle), (b) the per-note item styling is small enough to move cleanly, (c) future readers searching for "where do rail-resident styles live?" should find one answer.

**K. Bundle this supersedure with ADR-027 (completion-placement supersedure) as a single "post-TASK-010 placement supersedure" ADR.**

Considered carefully. Both supersedures share the same root cause (post-commit human review of placement quality) and arise in the same TASK-011 design cycle. **Rejected** for the same reasons enumerated in ADR-027's parallel Alternative I: each supersedure cites a different prior ADR (ADR-023 vs ADR-025), each encodes a different load-bearing principle (this ADR: visibility follows scroll-position-cost; ADR-027: action affordances follow the cognitive sequence), and citation discipline is cleaner with one ADR per supersedure. The architect's read is that the slight overhead of two documents is paid back by clearer citation, easier future supersedure, and easier reader navigation.

**L. Add a JavaScript-based "scroll to top of Notes" floating button on the bottom-of-page placement instead of moving the surface.**

Rejected. The user's framing explicitly identifies the placement (not the navigation between top and bottom of page) as the issue. A "scroll to Notes" affordance treats the symptom (it's far away) without addressing the cause (the surface is in the wrong place). Also requires JS, which is forbidden. Also requires a UI element on every Lecture page (yet another affordance competing for visual attention).

## My recommendation vs the user's apparent preference

The TASK-011 task file forecasts this supersedure with explicit framing:

> "Supersedure of ADR-023 §Template-surface (per `notes-surface-placement-visibility.md` Option 1 forecast) — relocate the Notes section from bottom-of-page to a **rail-resident Notes panel** below the chapter list, sharing the rail's `position: sticky` real estate. Per-Chapter Notes become visible from any scroll position."

This ADR aligns with the forecast (Option 1 — rail-resident below chapter list). For each architect-pick decision, this ADR commits as follows:

- **Rail integration:** natural-flow stacking (Option 1 in the issue's enumeration, with explicit rejection of Option 2's 50/50 partition). Aligns with the task forecast.
- **Per-Chapter scoping on landing page:** **omit the panel entirely** (architect's pick from the three landing-page candidates in the task file). The architect's read is that the landing page's chapter-list is itself the "select a Chapter" affordance; an empty Notes panel duplicates that hint. If the human prefers the placeholder-with-hint shape, this is the place to push back.
- **Rail-width constraints on the textarea:** **default `rows="3"` + `field-sizing: content` for vertical growth + `resize: vertical` fallback + no JS needed**. The architect's pick from the task file's three options ((a) reduce default `rows`, (b) `field-sizing: content` with JS resize fallback, (c) accept cramped default). The architect **rejects** the JS-fallback option because the CSS-only path (`field-sizing: content` where supported + `resize: vertical` universally + the default-3-rows commitment) is clean and sufficient — not because JS is forbidden (see ADR-035). If the human wants a richer auto-grow behavior at the cost of introducing JS, this is the place to push back.
- **What replaces the bottom-of-page Notes section:** **remove entirely** (Option (a) from the task file; architect's pick). Rationale: keeping a placeholder or a "see rail" pointer is dead weight. If the human prefers a brief "Notes are in the rail →" pointer for one cycle to ease the transition, this is the place to push back at the gate (cost is small).
- **CSS file ownership:** **all rail-resident Notes CSS in `base.css`** (Option (i) from the task file; architect's pick). The new `rail-*` prefix maps to `base.css` per ADR-008's prefix convention. If the human prefers the split (Option (ii)), this is the place to push back.

For **citation discipline**, this ADR cites ADR-023 in `Supersedes:`, quotes the human's review verbatim from the issue file, and names the empirical evidence (the 118 KB rendered HTML; 30+ viewport heights; the issue's tabulated chapter-length data) as the justification.

For **encoding the load-bearing principle**, this ADR names "visibility follows scroll-position-cost" as the project-wide principle and cross-references ADR-027's parallel "action affordances follow the cognitive sequence."

For the **test-evolution pre-flag**, this ADR includes a dedicated "Test-writer pre-flag" section.

I am NOT pushing back on:

- The user's framing in the project_issue (verbatim quoted as the empirical evidence).
- ADR-023's other decisions (route shape, validation, PRG, multiple-Note display order, the no-JS form-handling shape, no edit/delete in this iteration) — all retained as-is.
- The single-user posture (manifest §5 / §6 / §7) — preserved.
- The read-only Lecture source rule (manifest §6, MC-6) — preserved.
- The persistence-boundary rule (MC-10) — preserved (no DB code changes; existing route handler and persistence calls are unchanged).
- The no-JS form-handling shape (ADR-023 / ADR-025 / ADR-027) — followed here too; the supersedure is template + CSS only, the textarea growth is CSS-only on supporting browsers, and no client-side code is needed. (Not a project invariant — see ADR-035.)
- ADR-006 (navigation surface) — preserved; the rail's structure is extended additively below the chapter list.
- ADR-008 (CSS architecture) — preserved (new `rail-*` classes go in `base.css` per the prefix convention; old `note-*` classes are removed from `lecture.css`).
- ADR-026 (Chapter progress decoration) — composes cleanly: the rail now has chapter-list-with-progress (above) and Notes-panel (below) as two stacked rail-content sections.

## Manifest reading

Read as binding for this decision:

- **§3 Primary Objective.** Drive consumption + retention. Notes is one of three named consumption pillars; the supersedure restores Notes' visibility (and therefore its value) by moving it to a surface that is visible from any scroll position. Bottom-of-page placement at 30-screen scale is invisible; rail-resident placement is reachable.
- **§5 Non-Goals.** "No mobile-first" bounds the responsive obligation (rail-Notes is desktop-tuned). "No LMS / no AI tutor" bounds the editorial scope (no rich-text Notes, no AI suggestions during composition).
- **§6 Behaviors and Absolutes.** "Single-user" honored. "Lecture source read-only" honored (template + CSS changes only). "Mandatory and Optional honored everywhere" — preserved (the rail's existing M/O grouping is unchanged; the Notes panel sits below the entire chapter list).
- **§7 Invariants.** **"A Note is bound to exactly one Chapter."** — directly preserved. The rail-resident panel shows the *current* Chapter's Notes; the form posts to `/lecture/{chapter_id}/notes` (per ADR-023, unchanged); the per-Chapter binding is encoded in the route URL. **"Every Note … persists across sessions."** — preserved (the persistence layer per ADR-022 is consumed unchanged).
- **§8 Glossary.** Note is "user-authored content bound to a Chapter, optionally referencing one Section. Editable by the user. Never auto-generated." — preserved. The supersedure changes only where in the rendered HTML the Notes UI lives; the entity definition is unchanged.

No manifest entries flagged as architecture-in-disguise.

## Conformance check

- **MC-1 (No direct LLM/agent SDK use).** Orthogonal — Notes have no AI surface.
- **MC-2 (Quizzes scope to exactly one Section).** Orthogonal.
- **MC-3 (Mandatory/Optional designation respects the canonical mapping).** Preserved by construction. The rail's existing M/O grouping (per ADR-006/ADR-007) is unchanged; the Notes panel sits below it without affecting the grouping.
- **MC-4 (AI work asynchronous).** Orthogonal.
- **MC-5 (AI failures surfaced).** Orthogonal.
- **MC-6 (Lecture source read-only).** Honored. Template + CSS changes only; no source writes.
- **MC-7 (Single user).** Honored. The form has no `user_id`; the route handler (consumed unchanged from ADR-023) has no auth.
- **MC-8 (Reinforcement loop preserved).** Orthogonal.
- **MC-9 (Quiz generation user-triggered).** Orthogonal.
- **MC-10 (Persistence boundary).** Honored. No DB code changes; existing route handler and persistence calls are unchanged.
- **UI-1 / UI-2 / UI-3 (ui-task-scope).** UI-1 satisfied at the task level (TASK-011 declares the placement supersedure as part of its scope). UI-2 satisfied by this ADR (the styling target — `app/static/base.css` — is named; the new `rail-*` class namespace is committed; the removed `notes-*` / `note-*` classes are named). UI-3 satisfied by the diff naming the modified template and CSS files.
- **UI-4 (rendered-behavior verification gate).** Honored. ADR-010's Playwright harness covers the new rail-resident Notes round-trip; TASK-011 includes a per-supersedure rendered-surface verification gate.

Previously-dormant rule activated by this ADR: none.

## Consequences

**Becomes possible:**

- The Notes UI is visible from any scroll position on any Lecture page (the rail is sticky per ADR-008).
- Future per-Chapter affordances (Notification badges per manifest §8, future "you are here" indicators) inherit the placement-quality principle (visibility follows scroll-position-cost) and consider the rail as a natural home.
- The rail becomes a **multi-purpose persistent affordance surface**: chapter list (per ADR-006), per-Chapter progress (per ADR-026), per-Chapter Notes (this ADR). Future stacking extends naturally.
- The bottom-of-page real estate in `lecture.html.j2` is reclaimed (no Notes section there); the new bottom-of-Section completion affordance (per ADR-027) sits cleanly at the end of each Section without a Notes-shaped competitor below.
- The user can write a Note while reading any part of the Chapter without scrolling 30 viewports first.

**Becomes more expensive:**

- The rail partial (`_nav_rail.html.j2`) grows substantially: it now contains the chapter list (with new ADR-026 progress decorations), and the new Notes section (with form + list). Mitigation: the structure is conditional (`{% if rail_notes_context %}` for Notes); the additions are localized; the prior simple structure is recoverable if the supersedure proves wrong.
- `base.css` grows substantially: new rail-resident Notes classes; potentially new layout rules for the rail's vertical stacking. Mitigation: the additions follow the existing class-name-prefix convention; `lecture.css` shrinks correspondingly (old `note-*` rules removed).
- The route handler must populate `rail_notes_context` for Lecture pages and explicitly set it to `None` for the landing page. Mitigation: a small helper or two lines per route; the structural change is bounded.
- Existing tests that asserted the bottom-of-page placement or the old class names will fail. Mitigation: per the test-writer pre-flag, these are routine ADR-driven test amendments.
- The rail at the rail's narrowest viewport width (`220px`) is now denser (chapter list with progress + Notes panel with form). Implementer-tunable spacing; mitigation per the architectural commitment that the textarea remain usable at `220px`.

**Becomes impossible (under this ADR):**

- The Notes section at the bottom of the Lecture page. The supersedure removes it.
- The `notes-*` / `note-*` class names. Renamed to `rail-*` per the prefix convention.
- A Notes UI on the landing page. The `{% if rail_notes_context %}` guard suppresses it.
- A Notes UI that *requires* JavaScript to function. The supersedure keeps the working no-JS form as the baseline (a later ADR could layer progressive-enhancement JS on top). (Not a ban on client-side code — see ADR-035.)
- An affordance placement that ignores the actual content scale. The load-bearing principle now governs.

**Future surfaces this ADR pre-positions:**

- **Edit / delete Notes.** When the next Notes-features task lands, the per-`<li class="rail-note-item">` template extends to include action buttons; the route shape extends to support the new methods.
- **Optional Section reference on Notes.** The form gains a `<select name="section_id">` populated from the current Chapter's Section list (the parser already returns it); no architectural change to the rail-resident panel.
- **Markdown rendering of Note bodies.** The `{{ note.body }}` template variable is replaced with `{{ note.body | markdown_safe }}` once a Markdown library and sanitization story are committed.
- **Multi-Chapter "all Notes" view.** A separate `/notes` route + template; reuses the existing persistence accessors.
- **Notification surface (manifest §8).** The rail's growing role as a persistent affordance surface naturally extends to a Notification panel; this ADR's principle ("visibility follows scroll-position-cost") motivates rail placement for any new persistent affordance.
- **Quiz-bootstrap per-Chapter Quiz indicators.** If Quiz-bootstrap surfaces a per-Chapter status indicator in the rail, it stacks naturally below or above the Notes panel; the rail is the new shared real estate.

**Supersedure path if this proves wrong:**

- If the rail-Notes textarea proves too cramped for typical Note lengths → a future ADR introduces an "expand to overlay" affordance, or restores a (now-redesigned) per-page-Notes surface, or enables `field-sizing: content` more aggressively. Cost: template + CSS edit; bounded.
- If the rail's vertical density (chapter list + progress + Notes) proves overwhelming → a future ADR introduces collapse/expand affordances for one or both sections (CSS-only if clean, JS if the interaction needs it — its own ADR decides).
- If the per-Chapter scoping (omit on landing) proves confusing → a future ADR introduces the "select a Chapter" placeholder. Bounded.
- If the no-JS Notes shape proves limiting for some workflow (e.g., the user wants real-time autosave for half-written drafts) → a future ADR adds the client-side JavaScript that workflow needs, with whatever asset infrastructure it requires. The rail-Notes shape consumes whatever that ADR commits to. (See ADR-032, which already forecasts the project's first client-side JS for a related Notes-save concern, and ADR-035, which makes JavaScript part of the available toolkit.)

The supersedure is reversible (revert template + CSS changes; restore ADR-023's bottom-of-page placement) at low cost if the new placement also proves wrong. The empirical evidence from the human's commit-gate review is the justification for this supersedure; future evidence is the justification for any subsequent supersedure.
