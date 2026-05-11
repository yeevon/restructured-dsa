# ADR-027: Supersedure of ADR-025 §Template-placement — per-Section completion affordance moves from top-of-Section to bottom-of-Section

**Status:** `Accepted`
Auto-accepted by /auto on 2026-05-10
**Date:** 2026-05-10
**Task:** TASK-011
**Resolves:** `design_docs/project_issues/section-completion-affordance-placement.md`
**Supersedes:** `ADR-025` (§Template-placement only — the route shape, the form-handling pattern, the validation, the round-trip return point, and the styling-file ownership all remain Accepted as written by ADR-025)

## Context

ADR-025 (Accepted, 2026-05-10) committed to placing the per-Section completion affordance **inline next to `<h2 class="section-heading">`**, at the **top** of each Section in `lecture.html.j2`. The `/auto` cycle gated ADR-025 to Accepted; the implementer shipped the surface; the reviewer issued `READY-TO-COMMIT`; the human committed (`d2fec21`).

At post-commit review the human filed `design_docs/project_issues/section-completion-affordance-placement.md` (Open, surfaced 2026-05-10), with the following framing **(quoted verbatim from the issue file as the empirical evidence justifying this supersedure):**

> "It works and looks great but makes no practical sense to be displayed at the top of the section — better placement would be the bottom with clear line breaks before next section starts."

The issue file expanded the diagnosis:

> "The 'mark complete' affordance presupposes the learner has **finished reading** the Section. Encountering the affordance at the top of the Section asks the learner to commit to a completion claim *before* the act that earns it.
>
> The visual flow (heading → reading → completion) is broken by lifting the action to sit beside the heading. The current placement reads as 'this is a thing about the Section' rather than 'this is how you signal you're done.'
>
> A bottom-of-Section placement with a clear visual break (rule, padding, modified margin) before the next Section's heading would match the cognitive sequence: read → mark → move on."

The issue's Decide-when explicitly named this kind of task as the right home for the supersedure: *"the next Section-completion-related task (whether that's chapter-progress derived view, Mandatory-only filtered progress, completion-history surfacing, or — most likely — Quiz-bootstrap)."* TASK-011 is the chapter-progress derived view. This ADR is the supersedure the issue forecasted.

ADR-025's reasoning at the time was correct given what was known then: the architect chose top-of-Section placement on the basis that "the completion affordance is per-Section and the heading is the visual marker for 'this is a Section.' Co-locating the affordance with the heading keeps the user's eye at the same focal point when they decide to mark complete." This reasoning held in the abstract — it failed empirically once the surface shipped and the human encountered it in the actual reading flow on the actual Chapter lengths (the 30+ viewport-heights documented in `notes-surface-placement-visibility`). The architectural lesson the issue surfaces is that **placement of action affordances should be justified by *when in the reading flow* the user encounters the action, not by *which template scope* is structurally convenient.** This ADR encodes that lesson as the load-bearing principle.

The decision space (taken from the project_issue's enumerated options, plus consideration of what to retain from ADR-025):

- **Where to move the affordance:** bottom of the Section block (Option 1), or two-element split with a read-only status indicator at top + the action at bottom (Option 2), or keep status quo (Option 3, rejected by the human's framing), or floating affordance (Option 4, rejected because it requires JS, contradicting ADR-025's no-JS commitment).
- **Visual end-of-section break:** an `<hr>` element, a CSS bottom margin/padding rule on `<section>`, a dedicated `.section-end-break` class, a CSS-only border-bottom on `<section>`, or a combination.
- **Whether to retain a top-of-Section read-only status indicator** (Option 2 in the issue) — preserves the at-a-glance "is this Section complete" affordance the existing top-of-Section button doubles as for already-completed Sections.
- **CSS class renames and migrations:** what becomes of `.section-heading-row`, `.section-completion-form`, `.section-completion-button`, `.section-completion-button--complete`, `.section-completion-button--incomplete` once placement changes.

## Decision

### Move the entire completion form to the **bottom** of each `<section>` block (Option 1) — no read-only status indicator at top

The form moves from inside `<div class="section-heading-row">` (where it currently sits next to `<h2 class="section-heading">`) to a new container at the **end** of each `<section>` block, after `<div class="section-body">` and before the closing `</section>` tag. The new template structure becomes:

```html
{% for section in sections %}
<section id="{{ section.fragment }}"
         class="{% if section.id in complete_section_ids %}section-complete{% endif %}">
  <h2 class="section-heading">{{ section.heading | safe }}</h2>
  <div class="section-body">
    {{ section.body_html | safe }}
  </div>
  <div class="section-end">
    <form class="section-completion-form" method="post"
          action="/lecture/{{ chapter_id }}/sections/{{ section.section_number }}/complete">
      {% if section.id in complete_section_ids %}
        <input type="hidden" name="action" value="unmark">
        <button type="submit"
                class="section-completion-button section-completion-button--complete">
          &#10003; Complete
        </button>
      {% else %}
        <input type="hidden" name="action" value="mark">
        <button type="submit"
                class="section-completion-button section-completion-button--incomplete">
          Mark complete
        </button>
      {% endif %}
    </form>
  </div>
</section>
{% endfor %}
```

**Option 2 (top read-only status indicator + bottom action button) is rejected** for this supersedure. Rationale:

- ADR-025's existing `.section-complete` CSS class on the `<section>` element already provides at-a-glance state for already-completed Sections (it applies a Section-wide visual treatment — e.g., colored left-border, muted heading — per ADR-025 §State-indicator). The "is this Section complete" question is answerable from the heading's color and the Section-wide treatment without a separate top-of-Section indicator element.
- A separate read-only top-of-Section status indicator would be a second template surface to maintain (one for indicator, one for action). The CSS-class-on-`<section>` approach concentrates state visualization in one mechanism (the existing `.section-complete` class) while concentrating the action in one place (the bottom-of-Section form).
- The two-element-split shape doubles the per-Section template footprint for a marginal at-a-glance benefit. The Section-wide CSS treatment (already shipped) covers the same need.
- The two-element shape also forces a "split brain" template logic: the top element renders one thing when complete and nothing when incomplete; the bottom element renders the form. The single-bottom-only shape has one rendering path.

### Visual end-of-section break — new `.section-end` wrapper class with a CSS-controlled top border + padding; **no `<hr>` element**

The form lives inside a new `<div class="section-end">` wrapper. The CSS rule for `.section-end` provides:

- A **top border** (e.g., `border-top: 1px solid <neutral-gray>`) marking the end of the Section's reading content — visually distinct from the Section heading's own treatment so the learner reads it as "this is the end of this Section, not the start of a new one."
- **Top padding** (e.g., `padding-top: 1.5rem`) and **bottom margin** (e.g., `margin-bottom: 2rem` or larger) creating breathing room between the action affordance and the next Section's heading. The bottom margin is the primary visual break before the next `<section>`.
- A **flex/grid layout** that positions the form. The implementer chooses the alignment (right-aligned or centered) within the architectural commitment that the form is visually a footer-like element of the Section, not a body element.

`<hr>` is **rejected** as the visual break mechanism because:

- `<hr>` is a semantic HTML element ("thematic break in content") whose rendering is browser-default and harder to style consistently across browsers than a CSS border.
- The CSS border + padding shape lives entirely in `lecture.css` (per ADR-008's class-name-prefix convention); no template-level element addition beyond the `.section-end` wrapper.
- `<hr>` would require a CSS reset to remove its default styling before re-styling — net more CSS than the border-on-`.section-end` approach.

The `.section-end` wrapper is the architectural commitment; the specific border color, padding values, and form alignment are implementer-tunable within `lecture.css`.

### CSS class changes

The following classes from ADR-025 are affected:

- **`.section-heading-row`** — REMOVED. The top-of-Section heading is now plain `<h2 class="section-heading">`; no wrapper is needed (the form no longer co-resides with the heading). The `.section-heading-row` CSS rule in `lecture.css` is deleted.
- **`.section-completion-form`** — RETAINED. The form's class is unchanged; only its location moves. CSS rules that styled the form's inline placement (e.g., `display: flex` for heading-adjacent baseline alignment) are revised to fit the new wrapper-resident location (e.g., `margin-left: auto` for right-alignment within `.section-end`'s flex container).
- **`.section-completion-button`, `.section-completion-button--complete`, `.section-completion-button--incomplete`** — RETAINED. The button's classes are unchanged; the existing color treatments and label semantics remain.
- **`.section-complete`** (on `<section>`) — RETAINED. The Section-wide visual treatment (colored left-border, muted heading) remains the at-a-glance "is this complete" indicator; this is the load-bearing reason no separate top-of-Section status element is needed.
- **`.section-end`** — NEW. The bottom-of-Section wrapper. Lives in `lecture.css` per ADR-008.

### What is **NOT** changed by this supersedure (still per ADR-025)

ADR-025 made multiple decisions; this supersedure targets only §Template-placement. The following remain Accepted as written by ADR-025:

- **Route shape.** `POST /lecture/{chapter_id}/sections/{section_number}/complete` with form-encoded `action` field. Unchanged.
- **Form-handling pattern.** Synchronous PRG with no JavaScript. Unchanged.
- **Validation.** Route handler validates `chapter_id`, `section_number`, and `action`. Unchanged.
- **Round-trip return point.** PRG 303 redirect to `GET /lecture/{chapter_id}#section-{section_number}` with the URL fragment for scroll-restoration. Unchanged. Note that the URL fragment now scrolls to the *top* of the Section (the `<section id="...">` anchor); the user lands at the heading, scrolls down through the body, sees the now-flipped state at the bottom — the same scroll-restoration value, with the cognitive flow now correctly ordered.
- **Persistence integration.** Route handler calls `mark_section_complete` / `unmark_section_complete` from `app/persistence/`. Unchanged.
- **Styling file location.** `lecture.css` per ADR-008's class-name-prefix convention. Unchanged.
- **`.section-complete` class on `<section>`.** Unchanged — still applied for Section-wide visual treatment.
- **State-indicator design (button text + button color modifier + Section-wide CSS class).** Three layered indicators per ADR-025 §State-indicator. Unchanged in shape; only the affordance location moves.

The supersedure surface is narrow and surgical: §Template-placement only. The rest of ADR-025 stands.

### Load-bearing principle: action affordances follow the cognitive sequence, not the template scope

This supersedure encodes a project-wide principle for future placement decisions:

> **Action affordances are placed where the cognitive sequence puts them, not where the template scope makes them structurally convenient.**

Concretely: a "mark complete" action belongs at the moment the learner has earned the right to claim completion (after reading), not at the moment they first encounter the Section (the heading). A "submit a Note" action belongs where the learner's attention is when they decide to write (the rail, per ADR-028 — visible at any scroll position), not where the template's Section loop happens to end (the bottom of the page).

Future per-Section / per-Chapter affordances (Quiz-bootstrap's "Quiz this Section" surface; future Notes follow-up's per-Section reference; any future grading/feedback display) inherit this principle. Reviewers should reject any new affordance placement that is justified by template-scope convenience without naming the cognitive-sequence position the placement satisfies.

The principle is paired with ADR-028's load-bearing principle ("visibility follows scroll-position-cost"). Both arise from the same root cause (post-commit human review of placement quality) and together constitute the project's **placement-quality principles** for future surface decisions.

### Test-writer pre-flag — placement assertions in existing tests will fail by design

Per the user-memory entry **"Test updates forced by Accepted ADRs are routine"** and per the TASK-011 task file's "Architectural concerns" section, the following test updates are anticipated when this supersedure becomes Accepted:

- **Playwright tests** that asserted the completion form lives next to `<h2 class="section-heading">` (top-of-Section) will now fail. The test-writer amends them to assert the form lives inside `<div class="section-end">` at the bottom of each `<section>` block.
- **Pytest HTTP-protocol tests** that asserted the rendered HTML contains `<div class="section-heading-row">` will need updates: the wrapper is removed; the `<h2>` is now a direct child of `<section>`.
- **Any unit/integration test** that asserted the per-Section template structure with the form inline next to the heading will need amendment.

**The test-writer should NOT raise PUSHBACK for these failures.** They are the **routine ADR-driven test evolution** the user-memory entry describes. The test-writer's correct response is to amend the affected assertions to match the new placement, exactly as the user-memory entry prescribes:

> "When implementer ESCALATION is 'test fails because Accepted ADR-NNN changed the architecture,' amend the test directly; don't open project_issues or park the task."

The same routing applies preemptively to the test-writer phase: the supersedure ADR has named the placement change as the architecture change; tests that depend on the prior placement are amended at the test-writer phase, not flagged as bugs.

### Scope of this supersedure ADR

This ADR fixes only:

1. The relocation of the per-Section completion affordance from top-of-Section to bottom-of-Section.
2. The new `.section-end` wrapper and its visual-break treatment (CSS border + padding; no `<hr>`).
3. The removal of `.section-heading-row` (no longer needed once the form moves).
4. The retention of all other ADR-025 commitments (route shape, validation, PRG, state-indicator triad, styling file).
5. The encoding of the load-bearing placement-quality principle: action affordances follow the cognitive sequence, not the template scope.
6. The test-writer pre-flag for routine ADR-driven test amendment.

This ADR does **not** decide:

- The specific border color, padding values, or form alignment within `.section-end` — implementer-tunable within `lecture.css`.
- Any Quiz-related per-Section affordance placement — out of scope; Quiz-bootstrap's ADRs will inherit this ADR's placement-quality principle.
- A "sticky bottom-of-Section" affordance that follows the user's scroll within a long Section — out of scope; future ADR if a real workflow surfaces.
- Confirmation dialogs on unmark — none required (per ADR-025 §Decision); unmarking is reversible.
- Multi-Section batch completion — out of scope.

## Alternatives considered

**A. Option 2 from the project_issue: Two-element split — read-only status indicator at top + action at bottom.**

Considered carefully. The argument: preserve the at-a-glance "is this Section complete" affordance the existing top-of-Section button doubles as for already-completed Sections. **Rejected** because (a) ADR-025's `.section-complete` CSS class on `<section>` already provides Section-wide visual state via the heading color and the Section-wide treatment — the "at-a-glance is this complete" question is answered by the heading's color, not by a separate indicator element; (b) two template surfaces to maintain doubles the per-Section template footprint for marginal benefit; (c) the split-brain template logic ("top renders something only when complete; bottom always renders the form") is more complex than the single-bottom shape; (d) the issue's own framing names Option 1 as "the simplest delivery and a strong forecast" with Option 2 as "a refinement." This supersedure picks the simpler shape.

**B. Option 3 from the project_issue: Keep ADR-025's top-of-Section placement (status quo).**

Rejected by the human's framing. The project_issue file is the human's empirical evidence that the top-of-Section placement does not work in practice. The Decide-when text named "the next Section-completion-related task" as the home for the supersedure; TASK-011 is that task. Deferring again would extend the placement-debt.

**C. Option 4 from the project_issue: Floating "mark complete" affordance that follows scroll.**

Rejected. Requires JavaScript to determine the currently-in-viewport Section. Contradicts ADR-025's no-JS commitment (and ADR-023's project-wide no-JS posture). Adding JS here would force a project-wide ADR on JS/asset-build-step infrastructure — out of scope and unjustified for a placement refinement.

**D. Visual break: `<hr>` element instead of CSS border on `.section-end`.**

Rejected. `<hr>` has browser-default rendering that requires a CSS reset before re-styling. Net more CSS than the border-on-`.section-end` approach. Adds a semantic-HTML element (`<hr>` = "thematic break") whose semantics ("thematic break") are imprecise for the use case ("end of Section"). The wrapper-class approach is cleaner and lives entirely in `lecture.css` per ADR-008.

**E. Visual break: CSS bottom-border on `<section>` itself, no wrapper.**

Considered. Putting the border directly on `<section>` would avoid the wrapper element. **Rejected** because the wrapper provides a layout container for the form (e.g., flex alignment, padding around the form independent of the Section's overall margin). Without the wrapper, positioning the form requires either (a) absolute positioning (fragile), (b) modifying the Section's bottom-padding to accommodate the form's height (couples form size to Section padding), or (c) a JS measurement step (rejected). The wrapper is a small structural addition with significant layout flexibility.

**F. Visual break: increased bottom margin on `<section>` only, no border, no wrapper.**

Considered. The simplest possible change — no new element, no border, just whitespace. **Rejected** because the issue's text explicitly names "clear line breaks before next section starts" — pure whitespace does not visually communicate "this is the end of a Section" as forcefully as a horizontal rule (border or `<hr>`). A learner skimming a long Lecture page benefits from a visible end-of-Section signal that is more than just whitespace.

**G. Move the affordance to the bottom but retain `.section-heading-row` as a div wrapping `<h2>` only (for future use).**

Rejected as speculative. Retaining a wrapper class with no current consumer creates dead structure. If a future ADR needs a heading-row wrapper (e.g., for adding a per-Section quiz indicator next to the heading per Quiz-bootstrap), that ADR introduces the wrapper at the moment of need. Removing `.section-heading-row` cleanly is the right move.

**H. Add a top-of-Section minimal indicator: just a checkmark glyph (`✓`) inline next to the heading when complete, no form.**

Considered. Lighter than Option 2 (no read-only status element; just a glyph). **Rejected** because (a) the `.section-complete` class on `<section>` already provides at-a-glance state via the heading color; a glyph next to the heading is redundant; (b) adding a conditional glyph forces template logic in the heading area for marginal benefit; (c) the user's framing did not request a top-of-Section glyph — only a bottom-of-Section action with clear breaks. This ADR honors the user's framing exactly.

**I. Bundle this supersedure with ADR-028 (Notes placement supersedure) as a single "post-TASK-010 placement supersedure" ADR.**

Considered carefully. Both supersedures share the same root cause (post-commit human review of placement quality) and arise in the same TASK-011 design cycle. **Rejected** because (a) each supersedure cites a different prior ADR (ADR-025 vs ADR-023), and citation discipline is cleaner when each supersedure is its own document; (b) each encodes a different load-bearing principle (this ADR: action affordances follow the cognitive sequence; ADR-028: visibility follows scroll-position-cost) — bundling would force readers to mentally separate two principles in one document; (c) future readers searching for "why was the completion affordance moved?" or "why is Notes in the rail?" find a single dedicated ADR per question; (d) the architect-prompt note explicitly says "the architect may bundle...architect's call" — splitting is the cleaner shape for citation discipline at this scope. The architect's read is that the slight overhead of two documents is paid back by clearer citation and easier future supersedure (if either placement is later revisited, only one ADR moves).

## My recommendation vs the user's apparent preference

The TASK-011 task file forecasts this supersedure with explicit framing:

> "Supersedure of ADR-025 §Template-placement (per `section-completion-affordance-placement.md` Option 1 forecast) — relocate the per-Section completion form from inline-next-to-`<h2>` to the **end of each `<section>` block**, with a visual end-of-section break before the next Section's heading. The top-of-Section heading row may retain a *read-only status indicator* if `/design` finds it useful (Option 2 in the issue), but the *action* affordance moves to the bottom of the Section."

This ADR aligns with the forecast and additionally **rejects Option 2** (no read-only top-of-Section indicator), choosing the simplest viable shape (Option 1 only) with rationale (the existing `.section-complete` CSS class on `<section>` already provides at-a-glance state). The task file's "Architectural decisions expected" section names "Option 1 (clean move; less template surface to maintain)" as the architect's forecast; this ADR honors that forecast.

For the **visual end-of-section break**, the task names candidates ("`<hr>` element, increased bottom margin/padding via a new `.section-end` class, a CSS-only border-bottom rule") and says "Architect picks." This ADR commits to the **`.section-end` wrapper with CSS top-border + padding** with rationale (Alternatives D, E, F). If the human prefers the `<hr>` shape or the pure-whitespace shape, this is the place to push back at the gate.

For the **CSS class renames**, the task says "the supersedure ADR enumerates the class changes." This ADR explicitly enumerates: `.section-heading-row` removed; `.section-completion-form` retained; button classes retained; `.section-complete` retained; `.section-end` new.

For **citation discipline**, the task says "explicitly cite ADR-025 and explain that the empirical evidence … justifies the supersedure." This ADR cites ADR-025 in `Supersedes:`, quotes the human's review verbatim from the issue file, and names the empirical evidence (the post-commit review on the actual Chapter lengths) as the justification.

For **encoding the load-bearing principle**, the task says "the reading-flow lesson (action affordances follow the cognitive sequence) is the load-bearing architectural principle the supersedures encode — both ADRs should name it explicitly so future placement decisions inherit it." This ADR names the principle in §Decision and cross-references ADR-028's parallel principle.

For the **test-evolution pre-flag**, the task says "Architect should pre-flag this in the supersedure ADRs to make the routing explicit so the test-writer does not raise PUSHBACK on the routine ADR-driven test evolution." This ADR includes a dedicated "Test-writer pre-flag" section.

I am NOT pushing back on:

- The user's framing in the project_issue (verbatim quoted as the empirical evidence).
- ADR-025's other decisions (route shape, validation, PRG, state-indicator triad, styling file) — all retained as-is.
- The single-user posture (manifest §5 / §6 / §7) — preserved.
- The read-only Lecture source rule (manifest §6, MC-6) — preserved.
- The persistence-boundary rule (MC-10) — preserved (no DB code changes in this supersedure).
- The no-JS commitment (ADR-023 / ADR-025) — preserved (the supersedure is template + CSS only).
- ADR-008 (CSS architecture) — preserved (new `.section-end` class lives in `lecture.css` per the prefix convention).

## Manifest reading

Read as binding for this decision:

- **§3 Primary Objective.** Drive consumption + retention. The supersedure explicitly serves consumption: the action affordance now appears at the moment the learner has earned the right to claim completion (after reading), making the affordance read as "this is how you signal you're done" rather than "this is a thing about the Section."
- **§5 Non-Goals.** "No LMS / no gradebook" bounds the editorial scope (the supersedure does not introduce confirmation dialogs, completion ceremonies, or gamification). "No mobile-first" bounds the responsive obligation (the new `.section-end` wrapper is desktop-tuned).
- **§6 Behaviors and Absolutes.** "Single-user" honored. "Lecture source read-only" honored (template + CSS changes only; no source writes). "Mandatory and Optional honored everywhere" — preserved (the affordance placement is per-Section regardless of designation).
- **§7 Invariants.** **"Completion state lives at the Section level."** — directly preserved. The affordance remains per-Section; only its location within the Section moves. **"Mandatory and Optional are separable in every learner-facing surface."** — preserved (the rail's existing M/O grouping and the Lecture page's badge are untouched).
- **§8 Glossary.** Section is "the atomic unit for completion state." — the affordance remains per-Section. The supersedure does not change the Section's role; it changes only where in the Section's rendered HTML the action lives.

No manifest entries flagged as architecture-in-disguise. The supersedure is operational placement refinement, not a manifest-level change.

## Conformance check

- **MC-1 (No direct LLM/agent SDK use).** Orthogonal — completion has no AI surface.
- **MC-2 (Quizzes scope to exactly one Section).** Orthogonal — no Quiz entity.
- **MC-3 (Mandatory/Optional designation respects the canonical mapping).** Preserved by construction. The affordance placement is per-Section regardless of the parent Chapter's designation; no hardcoded chapter-number rule introduced.
- **MC-4 (AI work asynchronous).** Orthogonal.
- **MC-5 (AI failures surfaced).** Orthogonal.
- **MC-6 (Lecture source read-only).** Honored. The supersedure modifies only `app/templates/lecture.html.j2` and `app/static/lecture.css`; nothing under `content/latex/` is opened for write.
- **MC-7 (Single user).** Honored. The route handler and persistence layer (consumed unchanged from ADR-025) have no `user_id`; the template change has no per-user logic.
- **MC-8 (Reinforcement loop preserved).** Orthogonal — no Quiz machinery.
- **MC-9 (Quiz generation user-triggered).** Orthogonal.
- **MC-10 (Persistence boundary).** Honored. No DB code changes; the existing route handler and persistence calls are unchanged.
- **UI-1 / UI-2 / UI-3 (ui-task-scope).** UI-1 satisfied at the task level (TASK-011 declares the placement supersedure as part of its scope). UI-2 satisfied by this ADR (the styling target — `app/static/lecture.css` — is named; the new `.section-end` class is committed; the removed `.section-heading-row` is named). UI-3 satisfied by the diff naming the modified template and CSS files.
- **UI-4 (rendered-behavior verification gate).** Honored. ADR-010's Playwright harness covers the new placement; TASK-011 includes a per-supersedure rendered-surface verification gate.

Previously-dormant rule activated by this ADR: none.

## Consequences

**Becomes possible:**

- The cognitive sequence (heading → reading → completion) is restored: the learner reads the Section, then encounters the affordance at the moment they have earned the right to claim completion.
- The end-of-Section visual break (CSS border + padding on `.section-end`) provides a clear "this Section is over" signal before the next Section's heading.
- Future per-Section action affordances (Quiz-bootstrap's "Quiz this Section," any future grading/feedback surface) inherit the placement-quality principle: action affordances follow the cognitive sequence.

**Becomes more expensive:**

- The `lecture.html.j2` template's per-Section block restructures (heading-row wrapper removed; `.section-end` wrapper added). Mitigation: the change is localized to the per-Section loop; the existing Section-rendering content is untouched.
- `lecture.css` requires updates: `.section-heading-row` rule removed; `.section-end` rule added; `.section-completion-form` placement rules revised. Mitigation: the changes are contained within the existing `lecture.css`; no new file is introduced.
- Existing Playwright and pytest tests that asserted the prior placement will fail. Mitigation: per the test-writer pre-flag above, these are routine ADR-driven test amendments, not bugs.

**Becomes impossible (under this ADR):**

- The completion affordance at the top of the Section (next to `<h2 class="section-heading">`). The supersedure forces the move.
- The `.section-heading-row` wrapper class. Removed.
- An action affordance whose placement is justified by template-scope convenience without a cognitive-sequence rationale. The load-bearing principle now governs future placement decisions.

**Future surfaces this ADR pre-positions:**

- Quiz-bootstrap's "Quiz this Section" affordance — inherits this ADR's placement principle. The architect's forecast is that the Quiz affordance lives inside the same `.section-end` wrapper (alongside the completion form) so the bottom-of-Section becomes the standard per-Section action zone. Quiz-bootstrap's own ADR will commit to the precise shape.
- Future "completed on …" timestamp display — natural home is inside `.section-end` near the form, surfacing the existing `completed_at` column from ADR-024.
- Future "next incomplete Section" navigation cue — could read from the same Section-state data and surface a small affordance inside `.section-end`.

**Supersedure path if this proves wrong:**

- If the bottom-of-Section placement proves too easy to miss (the user finishes reading a Section and scrolls past the action affordance entirely) → a future ADR introduces a sticky-within-Section affordance, or restores the two-element split (Option 2). Cost: template + CSS edit; bounded.
- If the `.section-end` wrapper proves too noisy visually → a future ADR refines the visual break (smaller border, different alignment, fewer CSS rules). Bounded.
- If a sticky-bottom-of-page floating affordance becomes warranted (e.g., for a long Section) → a future ADR introduces it; the `.section-end` wrapper remains as the static fallback.

The supersedure is reversible (revert the template + CSS changes; restore ADR-025's placement) at low cost if the new placement also proves wrong. The empirical evidence from the human's post-commit review is the justification for this supersedure; future evidence is the justification for any subsequent supersedure.
