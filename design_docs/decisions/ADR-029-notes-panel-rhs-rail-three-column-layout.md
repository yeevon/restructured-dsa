# ADR-029: Supersedure of ADR-028 §Rail-integration / §Template-surface — Notes panel moves from the left-hand rail to a right-hand rail in a three-column layout

**Status:** `Accepted`
Auto-accepted by /auto on 2026-05-11
**Date:** 2026-05-11
**Task:** TASK-012
**Resolves:** `design_docs/project_issues/notes-surface-rhs-rail-supersedure-of-adr028.md`
**Supersedes:** `ADR-028` (§Rail-integration and the part of §Template-surface that placed `<section class="rail-notes">` inside `_nav_rail.html.j2` — see "What of ADR-028 is retained" below; ADR-028's route shape, validation, PRG, multiple-Note display order, submit-feedback shape, empty-state copy, no-edit/delete, no-Markdown, persistence integration, textarea-sizing *approach*, removal of the bottom-of-page Notes section in `lecture.html.j2`, the `notes` → `rail_notes_context` template-variable rename, and the load-bearing principle "visibility follows scroll-position-cost" all remain Accepted as written by ADR-028)

## Context

ADR-028 (Accepted, auto-accepted by `/auto` on 2026-05-10, committed in `3de9ab0`) committed to placing the per-Chapter Notes panel as a rail-resident `<section class="rail-notes">` inside `_nav_rail.html.j2` — the **left-hand** rail, below the chapter list, sharing the rail's `position: sticky` real estate. TASK-011's reviewer gave `READY-TO-COMMIT` against the ADR-028 contract; the human committed.

At post-commit review the human filed `design_docs/project_issues/notes-surface-rhs-rail-supersedure-of-adr028.md` (Open, surfaced 2026-05-11), with the following framing **(quoted verbatim from the issue file as the empirical evidence justifying this supersedure):**

> "i said put notes in in LHS rail when i mean RHS rail where there is alot of empty realestate, i take the blame for that"

The issue file expanded the diagnosis:

> - The current page is a two-column CSS Grid: `.lecture-rail` (LHS, sticky, `minmax(220px, 18rem)`) + `.page-main` (centered, `max-width: 860px`). On any wide-viewport desktop the entire region **right of the 860px main column is empty**. The LHS rail is now stacked (chapter list + Mandatory/Optional headings + per-Chapter progress + Notes panel) and visually crowded; the RHS is unused.
> - A RHS notes rail would (a) put Notes adjacent to the reading column where the cognitive flow already sits (right-side annotation matches handwritten margin notes), (b) free the LHS rail from the stacking pressure ADR-028's flex-column wrapper had to introduce, (c) consume the empty real estate that exists today specifically because the manifest §5 non-goal of "no mobile-first" leaves us free to use horizontal space.
> - The principle is the same one ADR-028 itself encoded — *visibility follows scroll-position-cost* — but applied with a corrected understanding of which rail has the real estate.

This is a re-decision, not an implementation bug. ADR-028 faithfully encoded the brief it was given (`notes-surface-placement-visibility.md` Option 1, which named "rail-resident below chapter list"); the brief had the LHS/RHS mix-up, and the human takes the blame. ADR-028's load-bearing principle (visibility follows scroll-position-cost) is **correct and retained**; what was wrong was the *application* of that principle to the LHS rail rather than to the RHS region where the real estate actually is.

The decision space (from the project_issue's enumerated options):

- **Layout shape:** three-column CSS Grid — LHS chapter rail | centered main | RHS Notes rail (Option 1); keep Notes in the LHS rail and just reorganize the LHS to reduce crowding (Option 2); a floating/absolutely-positioned RHS panel anchored to the right of `.page-main` (Option 3); status quo, do nothing (Option 4 — the human's explicit non-choice).
- **The new RHS rail partial:** filename and include structure for the extracted `<section class="rail-notes">` block.
- **Per-Chapter scoping on the landing page:** ADR-028's `{% if rail_notes_context %}` guard is retained — but now the *layout* must also degrade gracefully on `GET /`, where there is no RHS column.
- **CSS class names:** keep the `rail-notes-*` / `rail-note-*` prefix (still rail-resident) or rename to `notes-rail-*` for clarity.
- **Textarea sizing at the RHS rail width:** the RHS rail may be wider than the LHS rail; the `rows="3"` + `field-sizing: content` + `resize: vertical` fallback approach from ADR-028 is retained, with the RHS width as the new floor for "usable at the rail's narrowest width."

The manifest constrains this decision through §3 (Notes is one of three named consumption pillars; its visibility is value-load-bearing), §5 (**"No mobile-first product. A polished mobile experience is not a goal; usable layout in a desktop browser is sufficient"** — the entry that *licenses* consuming the empty horizontal real estate and also *bounds* the obligation: no mobile breakpoints are architecturally promised; also "no LMS / no AI tutor / no remote deployment / no multi-user"), §6 (single-user; Mandatory/Optional honored everywhere — the LHS chapter rail's M/O grouping is untouched; Lecture source read-only — template + CSS only), §7 (**"A Note is bound to exactly one Chapter and may optionally reference one Section within it"** — preserved: the RHS panel still shows the *current* Chapter's Notes and posts to `/lecture/{chapter_id}/notes`; "Every Note … persists across sessions" — preserved, no persistence change), §8 (Note, Section, Chapter, Mandatory, Optional — all stable; no new terms).

## Decision

### Layout shape — three-column CSS Grid: LHS chapter rail | centered main | RHS Notes rail (Option 1)

The page layout becomes a three-column CSS Grid on Lecture pages:

- **Column 1 — the LHS chapter-navigation rail** (`.lecture-rail` / `_nav_rail.html.j2`): unchanged in width and content except that the Notes `<section>` is *removed* (see below). It still carries the chapter list with the ADR-026 progress decoration and the Mandatory/Optional headings, and nothing else.
- **Column 2 — the centered main reading column** (`.page-main`): unchanged. Still capped at `max-width: 860px`. It does **not** grow into the freed RHS space — the cap means the cost of adding a third column on a narrower desktop is small (the main column does not shrink; the RHS rail takes space that was empty anyway).
- **Column 3 — the RHS Notes rail** (a new `<aside class="notes-rail">` wrapper, included via a new partial — see below): `position: sticky` exactly like the LHS rail, so it remains visible at any scroll position. This is where the Notes panel now lives.

The `.page-layout` grid in `base.css` changes from two columns to three. The forecast template (implementer-tunable within the architectural commitment):

```css
.page-layout {
  display: grid;
  grid-template-columns: minmax(220px, 18rem) minmax(0, 860px) minmax(220px, 22rem);
  min-height: 100vh;
}
```

The architectural commitments are:

- Three columns on Lecture pages, in the order: chapter rail, main, Notes rail.
- The RHS rail is `position: sticky` (using the same sticky mechanism the LHS rail already uses) so it is visible from any scroll position — this is the *load-bearing reason* the Notes panel is moved to a rail at all (ADR-028's "visibility follows scroll-position-cost" principle, retained).
- The centered main column keeps its `max-width: 860px` cap; the third column does not cause it to shrink below the cap at the widths the project targets ("usable layout in a desktop browser" per manifest §5).
- The exact `grid-template-columns` values, the RHS rail's width band, and any narrow-desktop fallback are implementer-tunable. The implementer should verify the three columns coexist without the main column being squeezed below its cap at a moderately narrow desktop width (e.g., 1280px). A minimal "stack on very narrow viewports" rule may be added if trivial, but a polished mobile experience is explicitly not a goal (manifest §5).

**Option 2 (keep Notes in the LHS rail; reorganize the LHS to reduce crowding) is rejected.** It does not use the empty RHS real estate the human explicitly identified; the LHS rail at `minmax(220px, 18rem)` is permanently cramped for a textarea regardless of how the chapter list is reorganized; and it defeats the stated principle (put the per-Chapter persistent affordance where the sticky real estate is — and the RHS is where the real estate is on a wide desktop).

**Option 3 (floating / absolutely-positioned RHS panel) is rejected.** Absolute positioning is fragile across viewport widths; it loses the `position: sticky` semantics the grid-column approach gets for free; and it would overlap content on narrower desktops. The grid-column approach reuses existing infrastructure (sticky rails already work).

**Option 4 (status quo) is rejected** — the human's explicit non-choice.

### The new RHS rail partial — extract `<section class="rail-notes">` into `_notes_rail.html.j2`; `base.html.j2` includes both rail partials

The `<section class="rail-notes">` block (currently inside `_nav_rail.html.j2`, conditional on `rail_notes_context`) is **extracted** into a new partial `app/templates/_notes_rail.html.j2`. `_nav_rail.html.j2` retains only the chapter list (with the ADR-026 progress decoration) and the Mandatory/Optional headings — the Notes `<section>` is no longer in its rendered output.

`base.html.j2`'s layout wrapper becomes (forecast structure; implementer-tunable):

```html
<div class="page-layout{% if not rail_notes_context %} page-layout--no-notes{% endif %}">
  <nav class="lecture-rail">
    {% include "_nav_rail.html.j2" %}
  </nav>
  <main class="page-main">
    {% block main %}{% endblock %}
  </main>
  {% if rail_notes_context %}
  <aside class="notes-rail" aria-labelledby="rail-notes-heading">
    {% include "_notes_rail.html.j2" %}
  </aside>
  {% endif %}
</div>
```

The architectural commitments are:

- A new partial holds the extracted Notes panel; `_nav_rail.html.j2` no longer renders it.
- `base.html.j2` includes both the LHS rail partial and the new RHS rail partial.
- The exact filename (`_notes_rail.html.j2` is the forecast), the wrapper element (`<aside>` is the forecast — it is semantically appropriate for a complementary content region; a `<nav>` or `<div>` is also acceptable), and the include structure are implementer-tunable. If the implementer keeps the `aria-labelledby` on the wrapper, the `id="rail-notes-heading"` on the heading inside the partial must match.

### Per-Chapter scoping on the landing page — the grid degrades to two columns on `GET /`

ADR-028's `{% if rail_notes_context %}` guard is **retained**: the Notes panel renders only when a Chapter context exists (i.e., on `GET /lecture/{chapter_id}`); on `GET /` (the landing page) it is omitted. With the move to a grid *column*, the layout must also degrade: on `/`, with no RHS column rendered, the grid is **two-column** (chapter rail + main), exactly as it was before ADR-028.

The forecast mechanism is a `page-layout` modifier class (`.page-layout--no-notes`) applied when `rail_notes_context` is falsy, which overrides `grid-template-columns` back to the two-column form:

```css
.page-layout--no-notes {
  grid-template-columns: minmax(220px, 18rem) minmax(0, 1fr);
}
```

The architectural commitments are:

- On `GET /` the page is two-column (chapter rail + main); there is no empty third column and no rendered RHS rail DOM.
- On `GET /lecture/{chapter_id}` the page is three-column with the Notes panel in the RHS rail.
- The exact mechanism (modifier class vs `{% if %}` around the grid-template declaration vs two named layout classes) is implementer-tunable; the commitment is the graceful degradation.

### CSS class names — keep the `rail-notes-*` / `rail-note-*` prefix; add `notes-rail` for the RHS wrapper

The Notes panel's existing classes (`rail-notes`, `rail-notes-heading`, `rail-notes-list`, `rail-note-item`, `rail-note-timestamp`, `rail-note-body`, `rail-notes-empty`, `rail-note-form`, `rail-note-form-label`, `rail-note-form-input`, `rail-note-form-submit`) are **kept as-is**. They are still rail-resident; the `rail-*` prefix does not bind to "the left rail specifically" — it binds to "a rail surface," and ADR-008's prefix convention maps `rail-*` to `base.css` regardless of which rail. Renaming all of them to `notes-rail-*` would be churn (CSS edits + template edits + test-assertion edits) for a cosmetic-clarity gain that the new `notes-rail` wrapper class already supplies (the wrapper names *where* the panel lives; the inner classes name *what* the panel contains).

A new wrapper class `.notes-rail` is added for the RHS column container (the `<aside>` element in `base.html.j2`). It is a `page-chrome / rail` class → it lives in `base.css` per ADR-008's prefix convention, alongside `.lecture-rail`. The new `.page-layout--no-notes` modifier (or whatever the implementer picks for the degradation) also lives in `base.css`.

The architectural commitments are:

- The Notes panel's inner classes keep their `rail-notes-*` / `rail-note-*` names; no rename.
- The new RHS column wrapper gets a `notes-rail`-prefixed class (`.notes-rail` is the forecast).
- All of these (kept and new) live in `base.css` per ADR-008. `lecture.css` is untouched by this ADR.
- The `.nav-rail-inner` flex-column wrapper in `base.css` (which ADR-028 introduced specifically to let the chapter list scroll while the Notes panel sat below it) may be simplified now that the Notes panel leaves the LHS rail — implementer-tunable; the commitment is only that the LHS rail still works (chapter list scrollable; M/O headings and progress decoration intact).

### Textarea sizing at the RHS rail width — `rows="3"` + `field-sizing: content` + `resize: vertical` fallback + no JavaScript (retained from ADR-028)

The textarea sizing approach from ADR-028 is **retained verbatim in shape**: default `rows="3"`, CSS `field-sizing: content` for browsers that support it (with a `min-height` matching the 3-row default and a `max-height` cap), `resize: vertical` as the universal fallback, `width: 100%`, the `Save` button full-width below the textarea, **no JavaScript**. The only change is that the new "narrowest rail width" floor is the RHS rail's narrowest width (forecast `220px` — the same `minmax(...)` floor as the LHS rail, so the floor is effectively unchanged). If the RHS rail's *maximum* width is set wider than the LHS rail's `18rem` (e.g., `22rem`), the implementer may tune the textarea's comfortable-at-default size upward within ADR-028's commitment that it be usable at the narrowest width and that no JS is introduced for resizing.

The architectural commitment is: the textarea is usable at the RHS rail's narrowest width; it grows on browsers that support `field-sizing: content`; it falls back gracefully (`resize: vertical`) on browsers that do not; **no JavaScript is introduced.** The no-JS posture (ADR-023 / ADR-025 / ADR-027 / ADR-028, and — pending the parallel ADR-030 — still in force for the completion toggle) is preserved by this ADR entirely.

### What of ADR-028 is retained

ADR-028 made many decisions; this supersedure targets only §Rail-integration and the part of §Template-surface that fixed *which rail* the panel sits in. The following remain Accepted as written by ADR-028:

- **Route shape.** `POST /lecture/{chapter_id}/notes` form-encoded; PRG 303 redirect to `GET /lecture/{chapter_id}`. Unchanged.
- **Form-handling pattern.** Synchronous PRG with no JavaScript. Unchanged.
- **Validation.** Route handler trims body; rejects empty/whitespace-only with 400; rejects unknown `chapter_id` with 404; rejects bodies > 64 KiB with 413. Unchanged.
- **Multiple-Note display order.** Most-recent-first (`ORDER BY created_at DESC`). Unchanged.
- **Submit-feedback shape.** Full-page reload via PRG; no flash, no toast, no URL fragment. Unchanged. (The PRG redirect re-renders the Lecture page; the now-RHS-resident Notes panel re-renders with the new Note at the top of the list — same feedback shape, in the new column.)
- **Empty-state copy.** "No notes yet — write the first one below." Unchanged; still in the `rail-notes-empty` class.
- **No edit/delete affordances.** Out of scope; remains out of scope.
- **No Markdown rendering.** Plain text via Jinja2 autoescape. Unchanged.
- **Persistence integration.** Route handler calls `create_note` / `list_notes_for_chapter` from `app/persistence/`. Unchanged.
- **Textarea-sizing approach.** `rows="3"` + `field-sizing: content` + `resize: vertical` + no JS. Unchanged (the narrowest-rail-width floor is now the RHS rail's floor; the approach is identical).
- **Removal of the bottom-of-page Notes section in `lecture.html.j2`.** Already done by ADR-028; not re-added. `lecture.html.j2` is untouched by this ADR (the bottom-of-Section completion affordance from ADR-027 also stays put).
- **The `notes` → `rail_notes_context` template-variable rename.** Unchanged — the route handler still builds `rail_notes_context` (a `{chapter_id, notes}` object on Lecture pages, `None` on the landing page). It is now consumed by `_notes_rail.html.j2` (and by `base.html.j2`'s `{% if %}` guards) rather than by `_nav_rail.html.j2`.
- **The `{% if rail_notes_context %}` guard.** Retained — now wrapping the RHS rail's inclusion in `base.html.j2` (and the new `page-layout--no-notes` modifier) rather than wrapping the `<section>` inside `_nav_rail.html.j2`.
- **The load-bearing principle "visibility follows scroll-position-cost."** Retained verbatim. This supersedure does **not** re-encode a new load-bearing principle — it *corrects the application* of ADR-028's existing principle to the rail that actually has the real estate on a wide desktop. (ADR-027's paired principle "action affordances follow the cognitive sequence" and — pending ADR-030 — the new "the response to a reading-flow action should not relocate the user" together remain the project's placement-quality principles.)

The supersedure surface is narrow: §Rail-integration (which rail; the new partial; the three-column grid that follows) and the part of §Template-surface that placed the panel inside `_nav_rail.html.j2`. Everything else in ADR-028 stands.

### Test-writer pre-flag — placement assertions in existing tests will fail by design

Per the user-memory entry **"Test updates forced by Accepted ADRs are routine"** and the TASK-012 task file's "Architectural concerns" section, the following test updates are anticipated when this supersedure becomes Accepted:

- **Pytest HTTP-protocol tests** that asserted the Notes panel (`<section class="rail-notes">`, the `rail-note-form`, the `rail-notes-list`, etc.) appears inside `_nav_rail.html.j2`'s rendered output, or asserted that `_nav_rail.html.j2`'s render contains the Notes panel, will now fail. The test-writer amends them to assert the Notes panel appears in the new partial / the RHS `notes-rail` region of the rendered Lecture page, and that `_nav_rail.html.j2`'s render no longer contains the Notes `<section>`.
- **Pytest tests** that asserted the `.page-layout` grid is two-column (e.g., asserting `grid-template-columns` has two tracks, or asserting the rendered HTML has exactly two grid children) will fail on Lecture pages. The test-writer amends them to assert three columns on Lecture pages and two columns on the landing page.
- **Playwright tests** for the Notes round-trip (load Lecture → submit Note → reload → assert Note visible) will need updated selectors to locate the form/list in the RHS rail rather than the LHS rail, and an assertion that the RHS rail is sticky (visible after a large scroll). A new Playwright assertion: on `GET /`, the RHS Notes rail is absent (two-column layout).
- **Any test** asserting the LHS rail's exact contents will need amendment to reflect that the Notes `<section>` is gone from it (chapter list + M/O headings + ADR-026 progress decoration only).

**The test-writer should NOT raise PUSHBACK for these failures.** They are the **routine ADR-driven test evolution** the user-memory entry describes:

> "When implementer ESCALATION is 'test fails because Accepted ADR-NNN changed the architecture,' amend the test directly; don't open project_issues or park the task."

The same routing applies preemptively to the test-writer phase: this supersedure ADR has named the surface change as the architecture change; tests that depend on the prior surface are amended at the test-writer phase, not flagged as bugs.

### Scope of this supersedure ADR

This ADR fixes only:

1. The relocation of the Notes UI from a `<section>` inside `_nav_rail.html.j2` (the LHS rail) to a new partial included by `base.html.j2` in a new RHS rail column.
2. The change of `.page-layout` from a two-column grid to a three-column grid on Lecture pages, with graceful degradation to two columns on the landing page.
3. The new `_notes_rail.html.j2` partial and the new `notes-rail` wrapper class (in `base.css`).
4. The retention of the Notes panel's existing `rail-notes-*` / `rail-note-*` class names (no rename), now consumed in the new partial.
5. The retention of all other ADR-028 commitments (route shape, validation, PRG, multiple-Note display order, submit-feedback shape, empty-state copy, no-edit/delete, no-Markdown, persistence integration, textarea-sizing approach, bottom-of-page-Notes-removal, the `notes`→`rail_notes_context` rename, the `{% if rail_notes_context %}` guard, the "visibility follows scroll-position-cost" principle).
6. The test-writer pre-flag for routine ADR-driven test amendment.

This ADR does **not** decide:

- Anything about the section-completion redirect — that is ADR-030's surface (the parallel supersedure of ADR-025 §round-trip-return-point).
- Edit / delete / Markdown / Section-reference Notes follow-ups — still deferred from ADR-023; future tasks.
- A "select a Chapter to take notes" placeholder for the landing-page RHS column — out of scope; ADR-028's omit-on-landing posture is retained; a future ADR + task if a placeholder is wanted.
- The exact `grid-template-columns` pixel/rem values, the RHS rail width band, the precise narrow-desktop fallback, or any CSS pixel/color values — implementer-tunable within the commitments above.
- Mobile responsiveness beyond "usable in a desktop browser" — manifest §5 bounds the obligation.
- Any change to the LHS chapter rail's contents, M/O grouping, or per-Chapter progress decoration — retained from ADR-006 / ADR-007 / ADR-026.
- Any Quiz-shaped scaffolding in either rail — explicitly out of scope; Quiz-bootstrap's own ADRs introduce its surfaces at the moment of need.

## Alternatives considered

**A. Option 2 from the project_issue: keep Notes in the LHS rail; reduce LHS crowding by reorganizing the chapter list or compacting the M/O headings.**

Rejected. It does not use the empty RHS real estate the human explicitly named as the point of the re-decision. The LHS rail at `minmax(220px, 18rem)` is permanently narrow for a textarea regardless of how the chapter list is reorganized; the crowding is a symptom of "two persistent surfaces stacked in one narrow column," and the cure is "give the second surface its own column," not "rearrange the first surface." Defeats the stated principle.

**B. Option 3 from the project_issue: floating / absolutely-positioned RHS Notes panel anchored to the right of `.page-main` (not a grid column).**

Rejected. Absolute positioning is fragile across viewport widths (the panel can overlap content on narrower desktops, or float off-screen on wider ones); it loses the `position: sticky` semantics the grid-column rails already get for free; and it adds a positioning surface that has to be re-derived on resize. The grid-column approach reuses the existing sticky-rail infrastructure with zero new positioning logic.

**C. Option 4 from the project_issue: status quo — Notes stays in the LHS rail per ADR-028.**

Rejected by the human's framing. The human explicitly identified this as wrong ("i said put notes in in LHS rail when i mean RHS rail"). The Decide-when text named "the next task that touches the page-layout grid or any rail-resident surface" as the home for the supersedure; TASK-012 is that task. Deferring again extends the placement/UX-debt by another cycle.

**D. Rename all `rail-notes-*` / `rail-note-*` classes to `notes-rail-*` for clarity.**

Considered. The argument: now that there are *two* rails, a `rail-*`-prefixed class is mildly ambiguous about which rail. **Rejected** because (a) the new `.notes-rail` wrapper class already disambiguates *where* the panel lives; the inner classes name *what* it contains, and "what" doesn't change with the column; (b) the rename is pure churn — CSS edits, template edits, *and* test-assertion edits — for a cosmetic gain; (c) ADR-008's prefix convention maps `rail-*` to `base.css` regardless of which rail, so the file-ownership boundary is not muddied by keeping the names. The architect's read is that the rename's cost outweighs the clarity gain; if the human disagrees, this is the place to push back at the gate (the rename is bounded and could be done in a later cleanup).

**E. Put the Notes panel in *both* rails, or make the column it lives in configurable.**

Rejected as over-engineering. There is one Notes panel; it lives in one place. The human's framing is unambiguous: the RHS rail. A configurable position is architecture-on-spec with no consumer.

**F. Use `float` or `position: fixed` on the existing `.page-layout` instead of a third grid track.**

Rejected. `float` interacts badly with the existing grid and would require clearing/sizing hacks; `position: fixed` removes the panel from the document flow and re-introduces all the fragility of Option 3. A third grid track is the idiomatic extension of the existing two-track grid.

**G. Bundle this supersedure with the section-completion-redirect supersedure (ADR-030) as a single ADR.**

Considered carefully. Both supersedures arise from the same TASK-011 post-commit human review and the same TASK-012 `/design` cycle, and the two project_issues each name the other as the bundle target for the *task*. **Rejected for the ADR documents** for the same reasons ADR-027 and ADR-028 were kept as separate documents (their parallel Alternative I/K): each supersedure cites a different prior ADR (ADR-028 vs ADR-025), each addresses a different concern (which rail the Notes panel lives in vs whether the completion redirect carries a scroll-anchor fragment), and citation discipline is cleaner with one supersedure per document — if either decision is later revisited, only one ADR moves. The task is one task / one `/design` cycle; the decisions are two ADRs. This matches the ADR-027/ADR-028 precedent exactly.

**H. Half-step: add the third grid column now but leave the Notes panel in the LHS rail (empty RHS column for a future task).**

Rejected as architecture-on-spec — a layout change with no consumer. The minimum viable shape is the complete vertical slice: three-column grid + Notes panel in the RHS column + the new partial + Playwright tests.

## My recommendation vs the user's apparent preference

The TASK-012 task file forecasts this supersedure with explicit framing:

> "Supersedure of ADR-028 §Template-surface / §Rail-integration — Notes panel moves from the left-hand rail to a right-hand rail in a three-column layout. … Forecast (per the issue's Option 1): three-column CSS Grid — `grid-template-columns: minmax(220px, 18rem) minmax(0, 860px) minmax(220px, 22rem)` or similar."

This ADR **aligns with the forecast** (Option 1 — three-column grid; Notes panel extracted to a new RHS partial; CSS in `base.css`; ADR-028's other decisions retained). For each architect-pick decision:

- **Layout shape:** three-column CSS Grid (Option 1), with explicit rejection of Options 2/3/4. Aligns with the task forecast and the issue's strong forecast.
- **The new RHS rail partial:** `_notes_rail.html.j2` (the forecast filename), included by `base.html.j2` alongside `_nav_rail.html.j2`; the RHS wrapper is `<aside class="notes-rail">` (forecast). Implementer-tunable filename/element.
- **Per-Chapter scoping / landing-page degradation:** the `{% if rail_notes_context %}` guard is retained; the grid degrades to two columns on `GET /` via a `page-layout` modifier class (the forecast mechanism). Aligns with the task's "the grid must degrade gracefully on the landing page" concern.
- **CSS class names:** **keep** the `rail-notes-*` / `rail-note-*` prefix (no rename); add `.notes-rail` for the new RHS wrapper. The task says "Architect picks; either way the classes stay in `base.css`." The architect picks "keep" — the rename's churn outweighs the clarity gain, and the new wrapper class supplies the disambiguation. If the human prefers the rename, push back at the gate.
- **Textarea sizing:** **retain ADR-028's approach verbatim** (`rows="3"` + `field-sizing: content` + `resize: vertical` + no JS), with the RHS rail's narrowest width as the new floor. The architect explicitly does **not** introduce JavaScript for the textarea; the no-JS posture is preserved by this ADR entirely.

For **citation discipline**, this ADR cites ADR-028 in `Supersedes:`, quotes the human's post-commit framing verbatim from the issue file ("i said put notes in in LHS rail when i mean RHS rail where there is alot of empty realestate, i take the blame for that"), and explains that ADR-028's reasoning was correct given the brief it was given but the brief had the LHS/RHS mix-up — and that this supersedure does *not* re-encode a new principle, it corrects the application of ADR-028's existing "visibility follows scroll-position-cost" principle.

For the **test-evolution pre-flag**, this ADR includes a dedicated "Test-writer pre-flag" section matching the ADR-027 / ADR-028 precedent.

I am NOT pushing back on:

- The human's framing in the project_issue (verbatim quoted as the empirical evidence).
- ADR-028's retained decisions (route shape, validation, PRG, multiple-Note display order, submit-feedback shape, empty-state copy, no-edit/delete, no-Markdown, persistence integration, textarea-sizing approach, bottom-of-page-Notes removal, the `notes`→`rail_notes_context` rename, the guard, the "visibility follows scroll-position-cost" principle) — all retained as-is.
- The single-user posture (manifest §5 / §6 / §7) — preserved.
- The read-only Lecture source rule (manifest §6, MC-6) — preserved (template + CSS only).
- The persistence-boundary rule (MC-10) — preserved (no DB code changes).
- The no-JS commitment (ADR-023 / ADR-025 / ADR-027 / ADR-028) — preserved (this supersedure is template + CSS only; the textarea growth is CSS-only on supporting browsers).
- ADR-006 / ADR-007 (navigation surface, chapter discovery/labelling/ordering) — preserved; the LHS rail's chapter list, M/O grouping, and ordering are untouched.
- ADR-008 (CSS architecture) — extended faithfully (new `notes-rail` and `page-layout--no-notes` classes go in `base.css` per the prefix convention; `lecture.css` untouched).
- ADR-026 (Chapter progress decoration) — preserved; the LHS rail still carries the `nav-chapter-progress` "X / Y" decoration on each chapter row.

## Manifest reading

Read as binding for this decision:

- **§3 Primary Objective.** Drive consumption + retention. Notes is one of three named consumption pillars; this supersedure restores Notes' visibility-and-usability by moving it to a surface that is both visible from any scroll position (the sticky RHS rail) *and* in real estate the user actually has (the empty horizontal space right of the 860px main column on a wide desktop). Reading-adjacent right-side annotation matches the cognitive model of margin notes.
- **§5 Non-Goals.** **"No mobile-first product. … usable layout in a desktop browser is sufficient."** — this is the entry that *licenses* the three-column desktop layout: consuming horizontal real estate is exactly what "usable layout in a desktop browser" frees us to do. It also *bounds* the obligation: no mobile breakpoints are architecturally promised; a minimal "stack on very narrow viewports" rule is optional, not required. "No LMS / no AI tutor / no remote deployment / no multi-user" — all orthogonal; nothing in this ADR touches them.
- **§6 Behaviors and Absolutes.** "Single-user" honored — no `user_id`; the Notes form and route are consumed unchanged. "Lecture source read-only" honored — template + CSS changes only; no writes to `content/latex/`. "Mandatory and Optional honored everywhere" — the LHS chapter rail's M/O grouping is untouched; the RHS Notes panel sits in a separate column and does not affect it.
- **§7 Invariants.** **"A Note is bound to exactly one Chapter and may optionally reference one Section within it."** — directly preserved. The RHS panel shows the *current* Chapter's Notes; the form posts to `/lecture/{chapter_id}/notes` (unchanged); the per-Chapter binding is encoded in the route URL. "Every Note … persists across sessions" — preserved (persistence layer per ADR-022 consumed unchanged). "Completion state lives at the Section level" — untouched by this ADR (that's ADR-030's surface). "Mandatory and Optional are separable in every learner-facing surface" — preserved (the LHS rail's grouping and the Lecture page's badge are untouched).
- **§8 Glossary.** Note, Section, Chapter, Mandatory, Optional — all stable. The supersedure changes only where in the rendered HTML the Notes UI lives; no entity definition changes; no new terms.

No manifest entries flagged as architecture-in-disguise. The supersedure is operational placement refinement, not a manifest-level change. The manifest is internally consistent with this decision.

## Conformance check

- **MC-1 (No direct LLM/agent SDK use).** Orthogonal — Notes have no AI surface. Note: this ADR introduces **no JavaScript at all**, so even the "is client JS an MC-1 matter?" question (it is not — MC-1 governs AI SDKs, not client JS) does not arise here.
- **MC-2 (Quizzes scope to exactly one Section).** Orthogonal — no Quiz entity, no Quiz route, no Quiz scaffolding.
- **MC-3 (Mandatory/Optional designation respects the canonical mapping).** Preserved by construction. The LHS rail's M/O grouping (per ADR-006 / ADR-007) is unchanged; the RHS Notes panel is a separate column and does not affect the grouping; no hardcoded chapter-number rule introduced.
- **MC-4 (AI work asynchronous).** Orthogonal.
- **MC-5 (AI failures surfaced).** Orthogonal.
- **MC-6 (Lecture source read-only).** Honored. Template + CSS changes only; nothing under `content/latex/` is opened for write.
- **MC-7 (Single user).** Honored. The Notes form has no `user_id`; the route handler (consumed unchanged from ADR-023/ADR-028) has no auth, no session, no per-user partitioning.
- **MC-8 (Reinforcement loop preserved).** Orthogonal — no Quiz machinery.
- **MC-9 (Quiz generation user-triggered).** Orthogonal.
- **MC-10 (Persistence boundary).** Honored. No DB code changes; the existing route handler and persistence calls (`create_note`, `list_notes_for_chapter`) are unchanged; no `sqlite3` import or SQL literal outside `app/persistence/` is introduced.
- **UI-1 / UI-2 / UI-3 (ui-task-scope).** UI-1 satisfied at the task level (TASK-012 declares the RHS rail as a UI surface change). UI-2 satisfied by this ADR (the styling target — `app/static/base.css` — is named; the new `.notes-rail` and `.page-layout--no-notes` classes are committed; the three-column `.page-layout` grid rule is committed; the retained `rail-notes-*` / `rail-note-*` classes are named). UI-3 satisfied by the diff naming the modified/created template and CSS files (`base.html.j2`, `_nav_rail.html.j2`, new `_notes_rail.html.j2`, `base.css`).
- **UI-4 / UI-5 / UI-6 (rendered-surface verification gate).** Honored. ADR-010's Playwright harness covers the new RHS-rail layout; TASK-012's "Verification gates (human-only)" section records the rendered-surface review (three-column layout, RHS Notes rail sticky, un-crowded LHS rail) as `rendered-surface verification — pass (TASK-012 RHS Notes rail + no-snap completion redirect)` in the audit Human-gates table.

Previously-dormant rule activated by this ADR: none.

## Consequences

**Becomes possible:**

- The Notes UI is visible from any scroll position on any Lecture page (the RHS rail is sticky) *and* sits in real estate the user actually has on a wide desktop — reading-adjacent, like margin notes.
- The LHS chapter rail is un-crowded: chapter list + M/O headings + ADR-026 progress decoration, nothing else. The `.nav-rail-inner` flex-column wrapper ADR-028 introduced to manage the stacking can be simplified.
- The page now has a **third persistent affordance surface** (the RHS rail). Future surfaces that follow ADR-028's "visibility follows scroll-position-cost" principle have two rails to choose between based on which has the room.
- The freed-by-construction RHS horizontal real estate (which exists because manifest §5 leaves the project free to use horizontal space) is now used rather than empty.

**Becomes more expensive:**

- The `base.css` grid is now three-column on Lecture pages and must degrade to two-column on the landing page — a small amount of conditional layout logic. Mitigation: a single modifier class (`page-layout--no-notes`); the degradation is one CSS rule.
- `base.html.j2` now includes two rail partials and has `{% if rail_notes_context %}` guards around the RHS rail's inclusion. Mitigation: the structure is small and localized; the prior two-column structure is recoverable by revert.
- A new partial file (`_notes_rail.html.j2`) is added; `_nav_rail.html.j2` shrinks correspondingly. Mitigation: net template-line count is roughly flat; the split improves separation of concerns.
- The three columns must coexist on a narrower desktop without squeezing the main column below its 860px cap. Mitigation: the cap means the main column does not grow into the freed space, so the third column's cost is "the space that was empty anyway"; the implementer verifies at ~1280px.
- Existing tests that asserted the Notes panel is in the LHS rail or the grid is two-column will fail. Mitigation: per the test-writer pre-flag, these are routine ADR-driven test amendments.

**Becomes impossible (under this ADR):**

- The Notes panel inside `_nav_rail.html.j2` (the LHS rail). The supersedure moves it out.
- A two-column layout on Lecture pages. Lecture pages are now three-column (the landing page stays two-column).
- A Notes UI on the landing page. The `{% if rail_notes_context %}` guard (retained) suppresses it.
- A Notes UI that requires JavaScript. The supersedure preserves the no-JS commitment entirely.
- An affordance placement that ignores which surface has the real estate. The corrected application of ADR-028's principle now governs.

**Future surfaces this ADR pre-positions:**

- **Edit / delete Notes.** When the next Notes-features task lands, the per-`<li class="rail-note-item">` template (now in `_notes_rail.html.j2`) extends to include action buttons; the route shape extends.
- **Optional Section reference on Notes.** The form (now in `_notes_rail.html.j2`) gains a `<select name="section_id">`; no architectural change to the RHS-rail panel.
- **Markdown rendering of Note bodies.** The `{{ note.body }}` variable is replaced with a sanitized-Markdown render once a library + sanitization story is committed.
- **A landing-page RHS column placeholder** ("select a Chapter to take notes") — if later wanted, a future ADR + small task; the `page-layout--no-notes` modifier is the natural integration point.
- **Quiz-bootstrap per-Chapter Quiz indicators.** If Quiz-bootstrap surfaces a per-Chapter status indicator at the page level, it now has two rails to choose between; its own ADR commits to where. (No slot is pre-allocated here — that would be architecture-on-spec.)
- **Notification surface (manifest §8).** Same — a future persistent affordance picks a rail per ADR-028's retained principle.

**Supersedure path if this proves wrong:**

- If the three-column layout proves too tight on common desktop widths → a future ADR widens the main column band or narrows the RHS rail, or makes the RHS rail collapsible (potentially with JS introduced by its own gated ADR). Cost: one `base.css` rule; bounded.
- If reading-adjacent (right) placement proves worse than left for some workflow → a future ADR moves the Notes panel back to the LHS column. Cost: swap two `{% include %}` lines + one grid rule; bounded.
- If the per-Chapter scoping (omit on landing) proves confusing once there are two rails → a future ADR introduces the "select a Chapter" placeholder for the landing-page RHS column. Bounded.
- If the no-JS commitment proves untenable for rail-Notes UX → a future ADR introduces JS infrastructure as a project-wide commitment (the same threshold ADR-030 weighs for the completion toggle). The rail-Notes shape consumes whatever JS infrastructure that ADR commits to.

The supersedure is reversible (swap the two rail includes, restore the two-column grid, move the `<section>` back into `_nav_rail.html.j2`) at low cost if the new placement also proves wrong. The empirical evidence from the human's post-commit review is the justification for this supersedure; future evidence is the justification for any subsequent supersedure.
