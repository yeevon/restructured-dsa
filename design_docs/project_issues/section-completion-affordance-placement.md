# Section-completion affordance placement — top-of-section is the wrong moment in the reading flow

**Status:** Open
**Surfaced:** 2026-05-10 (TASK-010 human post-commit review)
**Decide when:** when Section-completion or related per-Section UI work next surfaces (e.g. completion-history surfacing, Mandatory-only progress view, derived chapter-progress display, Quiz-bootstrap). Not a blocker for shipping TASK-010.

## Question

ADR-025 (Accepted, 2026-05-10) committed to placing the per-Section completion form **inline next to `<h2 class="section-heading">`**, at the **top** of each Section in `lecture.html.j2`. TASK-010's reviewer gave `READY-TO-COMMIT` against the ADR-025 contract.

At post-commit review the human raised that ADR-025's placement is **practically wrong for the reading flow**:

> "It works and looks great but makes no practical sense to be displayed at the top of the section — better placement would be the bottom with clear line breaks before next section starts."

The mismatch:

- The "mark complete" affordance presupposes the learner has **finished reading** the Section. Encountering the affordance at the top of the Section asks the learner to commit to a completion claim *before* the act that earns it.
- The visual flow (heading → reading → completion) is broken by lifting the action to sit beside the heading. The current placement reads as "this is a thing about the Section" rather than "this is how you signal you're done."
- A bottom-of-Section placement with a clear visual break (rule, padding, modified margin) before the next Section's heading would match the cognitive sequence: read → mark → move on.

This is the same **category** of issue as `notes-surface-placement-visibility.md` — placement of an interaction affordance relative to the content it relates to. Different specific problem (Notes was *too far from* its content; completion is *too far before* its content), same lesson for the architect: placement of action affordances should be justified by **when in the reading flow** the user encounters the action, not by **which template scope** is convenient.

## Options known

- **Option 1 — Move the completion form to the end of each `<section>` block, before the closing tag.** Render the affordance after the Section body content, followed by a visual break (`<hr>`, increased bottom margin, or a separator class) before the next `<section>`. Pros: matches the cognitive sequence (read → mark); clear visual end-of-Section signal; minimal CSS change (existing `.section-completion-form` class moves; new `.section-end-separator` or similar). Cons: harder to find for a learner who already completed the Section and wants to *un-mark* without re-scrolling; mitigation: the existing checked-state visual on the `<h2>` row (currently the affordance itself) needs to be preserved as a status indicator-only element at the top — splitting "indicator" from "action."
- **Option 2 — Two-element split: status indicator at top (read-only `<span class="section-complete-indicator">`), action button at bottom.** Top of Section shows "✓ Complete" or empty depending on state; bottom of Section shows the toggle form. Pros: preserves the at-a-glance "is this Section complete" affordance the current placement provides for already-completed Sections; bottom action matches reading flow. Cons: two surfaces to maintain in template + CSS; possibly redundant.
- **Option 3 — Keep ADR-025's top-of-Section placement.** Status quo. Pros: zero change cost; at-a-glance indicator and toggle co-located; works correctly for short Sections where the heading and the end of the body are in the same viewport. Cons: defeats the cognitive flow for typical Section lengths.
- **Option 4 — Floating "mark complete" affordance that follows scroll.** A fixed-position button (per-Section, anchored to whichever Section is currently in viewport) that lets the user mark any Section complete from any scroll position. Pros: maximally available. Cons: needs JS to determine current-in-viewport Section (contradicts ADR-025's no-JS posture and ADR-023's synchronous-no-JS precedent); visual interference with content; not how the current per-Section model is structured (one form per Section, statically rendered).

Option 1 is the simplest delivery and a strong forecast; Option 2 is a refinement that preserves the existing top-of-Section visual feedback for already-complete Sections. Option 3 is status quo. Option 4 contradicts the no-JS commitment.

## Decide when (priority context)

The human's post-commit guidance (recorded as framing for whichever architect picks this up):

> "It works and looks great" — i.e. shipping was the right call. The placement question is a follow-up refinement, not a regression to be hot-fixed.

Practical implication: the next Section-completion-related task (whether that's chapter-progress derived view, Mandatory-only filtered progress, completion-history surfacing, or — most likely — Quiz-bootstrap, since Quiz UI introduces another per-Section affordance whose placement must be jointly designed with completion's placement) should bundle the placement supersedure into its `/design` cycle. A standalone "just move the completion form" task is the wrong shape for the same reason TASK-009's Notes-placement supersedure was deferred — re-running the test-writer + implementer cycle for a template tweak is high overhead for low delta.

The supersedure ADR (likely `ADR-NNN supersedes ADR-025 §Template-placement`) rides alongside whatever ADR the next per-Section UI task needs.

If no per-Section UI task surfaces within ~3 `/next` cycles, the architect should propose a standalone surface-relocation task to prevent the placement issue from becoming permanent.

## Cross-references

- ADR-025 §Template-placement (placement decision being challenged)
- `notes-surface-placement-visibility.md` (parallel placement issue from TASK-009 — same category, different specifics)
- `app/templates/lecture.html.j2` (current section block)
- `app/static/lecture.css` (existing `.section-completion-form`, `.section-heading-row` classes)
- TASK-010 audit Run 008 (reviewer `READY-TO-COMMIT` against ADR-025 as written; this issue does not re-open the commit gate)
- Manifest §7 (Completion state lives at the Section level — placement of the *act* of completing is operational, not a manifest commitment)
