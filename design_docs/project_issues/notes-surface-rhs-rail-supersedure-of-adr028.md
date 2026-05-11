# Notes surface — LHS rail was the wrong rail; RHS would match the reading-flow real estate

**Status:** Open
**Surfaced:** 2026-05-11 (TASK-011 human post-commit review)
**Decide when:** the next task that touches the page-layout grid or any rail-resident surface — likely the same `/design` cycle that supersedes the section-completion PRG-redirect scroll-disrupt issue (`section-completion-prg-redirect-disrupts-scroll-position.md`), since both are post-TASK-011 placement/UX corrections to ADR-027/028 and bundling them avoids a second template/CSS-only `/design` round.

## Question

ADR-028 (Accepted, 2026-05-10, auto-accepted by `/auto`) committed to placing the per-Chapter Notes panel as a **rail-resident section inside `_nav_rail.html.j2`** (the **left-hand** rail), below the chapter list, sharing the rail's `position: sticky` real estate. TASK-011's reviewer gave `READY-TO-COMMIT` against the ADR-028 contract.

At post-commit review the human raised that ADR-028's surface choice is **the wrong rail**:

> "i said put notes in in LHS rail when i mean RHS rail where there is alot of empty realestate, i take the blame for that"

The mismatch:

- The current page is a two-column CSS Grid: `.lecture-rail` (LHS, sticky, `minmax(220px, 18rem)`) + `.page-main` (centered, `max-width: 860px`). On any wide-viewport desktop the entire region **right of the 860px main column is empty**. The LHS rail is now stacked (chapter list + Mandatory/Optional headings + Notes panel) and visually crowded; the RHS is unused.
- A RHS notes rail would (a) put Notes adjacent to the reading column where the cognitive flow already sits (right-side annotation matches handwritten margin notes), (b) free the LHS rail from the stacking pressure ADR-028's flex-column wrapper had to introduce, (c) consume the empty real estate that exists today specifically because the manifest §5 non-goal of "no mobile-first" leaves us free to use horizontal space.
- The principle is the same one ADR-028 itself encoded — *visibility follows scroll-position-cost* — but applied with a corrected understanding of which rail has the real estate.

This is a re-decision, not an implementation bug: ADR-028 faithfully encoded the brief it was given. The brief was wrong (the human takes blame for the LHS/RHS mix-up at the original `notes-surface-placement-visibility` framing time).

## Options known

- **Option 1 — Three-column CSS Grid: LHS chapter rail | main | RHS notes rail.** Add a third grid column (e.g., `grid-template-columns: minmax(220px, 18rem) minmax(0, 860px) minmax(220px, 22rem);`). RHS rail is sticky like the LHS rail. Move `<section class="rail-notes">` out of `_nav_rail.html.j2` into a new `_notes_rail.html.j2` partial; the base template includes both. CSS classes can keep the `rail-notes-*` / `rail-note-*` prefix (they're still rail-resident; the prefix doesn't bind to LHS specifically) — or rename to `notes-rail-*` for clarity. Per ADR-008's CSS-file split, the new RHS rail styling lives in `base.css` (page chrome). Pros: directly uses the empty real estate; reading-adjacent; LHS rail un-crowds. Cons: third column constrains the centered max-width-860px main column more tightly on narrow desktops (testable; the page-main's existing `max-width: 860px` cap means it doesn't grow into the freed RHS space anyway, so the cost is small).
- **Option 2 — Keep Notes in LHS rail; reduce LHS crowding by collapsing chapter list under a heading or moving Mandatory/Optional headings into a more compact form.** Status quo on layout; reorganize LHS to make Notes feel less stacked. Pros: zero layout-architecture change; one-cycle CSS-only follow-up. Cons: doesn't solve the "empty RHS real estate" observation; LHS will always be cramped at `minmax(220px, 18rem)` for a textarea; defeats the stated principle.
- **Option 3 — Floating / absolutely-positioned RHS notes panel** (not a grid column; a fixed-position panel anchored to the right of `.page-main`). Pros: no grid restructure. Cons: positioning fragility on different viewport widths; loses sticky semantics that the existing rail gets for free.
- **Option 4 — Status quo; do nothing.** Notes stays in LHS per ADR-028. Pros: zero cost. Cons: human has explicitly identified this as wrong.

Option 1 is the strong forecast. Option 4 is the explicit non-choice the human ruled out.

## Decide when (priority context)

The next task that touches the page-layout grid or any rail-resident surface. Since the section-completion-PRG-redirect scroll-disrupt issue (`section-completion-prg-redirect-disrupts-scroll-position.md`) is already on the project_issues list and also a TASK-011 post-commit finding, both should likely bundle into one follow-up task and one `/design` cycle (two ADR supersedures: §Template-surface of ADR-028 → RHS rail; PRG-redirect-with-fragment from ADR-025 → no-fragment or async — see the other issue).

A standalone "just move Notes to the RHS rail" task is the wrong shape for the same reason TASK-009's and TASK-010's standalone-placement-tasks were rejected — re-running the test-writer + implementer cycle for a template/CSS tweak is high overhead for low delta. Bundle with the next surface-touching task.

## Cross-references

- ADR-028 §Template-surface and §Rail integration (placement decision being challenged)
- ADR-008 §CSS-file split (RHS rail styles will live in `base.css` alongside LHS rail styles)
- `app/templates/_nav_rail.html.j2`, `app/templates/base.html.j2`, `app/static/base.css` (current LHS-rail home of the Notes panel)
- `section-completion-prg-redirect-disrupts-scroll-position.md` (parallel TASK-011 post-commit finding; bundle target for the next `/design` cycle)
