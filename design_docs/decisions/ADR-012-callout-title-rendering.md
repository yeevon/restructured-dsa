# ADR-012: Callout title rendering — extract optional `[Title]` argument and emit as `<div class="callout-title">` inside callout div

**Status:** `Accepted`
**Date:** 2026-05-08
**Task:** TASK-004
**Resolves:** `design_docs/project_issues/latex-callout-title-arg-passthrough.md`
**Supersedes:** none

## Context

The corpus uses five callout environments (`ideabox`, `defnbox`, `notebox`, `warnbox`, `examplebox`) with an optional bracket argument that conventionally serves as a title: `\begin{ideabox}[Chapter map]`, `\begin{defnbox}[List]`, etc. The optional argument is the callout's title -- it orients the reader before the body begins.

The parser currently passes the brackets through literally, so the rendered DOM contains text like `[Stability of the gather step is essential]` inline within the callout body, without any header treatment. This was surfaced during TASK-003's Playwright screenshot review (ADR-010 verification gate) and filed as `design_docs/project_issues/latex-callout-title-arg-passthrough.md`.

ADR-003 (Accepted) commits the project to a pylatexenc-based parser with environment-specific handlers for all five callout environments. ADR-003 explicitly permits extending handlers: "the implementer may extend [the parser] with environment-specific handlers." The `_nodes_to_html` function in `app/parser.py` already contains a callout handler that emits `<div data-callout="..." class="callout callout-...">` wrappers. ADR-008 (Accepted) scoped `lecture.css` for Lecture-body content styling, including `.callout-*` palette rules. A `.callout-title` CSS rule already exists in `lecture.css` (added during prior implementation work).

The existing code already has a `_get_optional_arg` helper and the `_nodes_to_html` callout handler already emits `<div class="callout-title">` when a title is extracted. However, the `_convert_inline_latex` path (which handles callout environments nested inside inline content) does not extract the optional argument. The architectural question is: what is the correct structural representation of a callout title in the rendered HTML, and should this be consistent across both rendering paths?

The human pushed back on resolving this "within ADR-003's latitude" without a formal ADR, requesting that the decision go through the human gate for consistency with the project's ADR discipline.

## Decision

The parser handler for all five callout environments extracts the optional `[Title]` argument (when present) and emits it as `<div class="callout-title">Title</div>` as the first child element inside the callout's wrapper `<div>`. The title div precedes the callout body content. When no optional argument is supplied, no title element is emitted -- the callout body renders as before.

The rendering is consistent across all five callout environments: `ideabox`, `defnbox`, `notebox`, `warnbox`, and `examplebox`. Each uses the same `.callout-title` CSS class, the same structural position (first child of the callout div), and the same extraction logic.

Both rendering paths handle titles:
- **`_nodes_to_html`** (the primary body-level renderer): uses `_get_optional_arg` to extract the title from the environment node's argument list, then emits the `<div class="callout-title">` before the body HTML.
- **`_convert_inline_latex`** (the inline content renderer, which handles callout environments nested inside other content): also extracts and emits the title when present, maintaining structural consistency.

The title text is HTML-escaped (via `_escape`) before insertion into the `<div class="callout-title">`. The title is treated as plain text, not as LaTeX content that requires further parsing -- this is a simplification that works for the corpus's current titles (which are short descriptive phrases without math or macros). If a future title contains math or macros, the existing `_convert_inline_latex` approach for the title text would be the natural extension, but that is not committed to by this ADR.

The CSS rule in `lecture.css` for `.callout-title` styles the title as bold, slightly smaller than body text, uppercase with letter-spacing, and with a bottom margin separating it from the callout body. This rule is already present in `lecture.css` and applies uniformly across all five callout types -- the callout-type-specific palette (background, border color) comes from the parent `.callout-*` class, not from the title.

The title is embedded directly in the `body_html` string, not as a separate IR field. This is consistent with ADR-003's existing pattern where callout HTML (including the wrapper div, data-callout attribute, and body content) is assembled by the parser handler and passed to Jinja2 as a single HTML string within the section's `body_html`. No IR contract change is required.

## Alternatives considered

**A. Route the title through the IR as a separate field for Jinja2 to render conditionally.**
Each callout in the IR would carry `{"type": "callout", "env": "ideabox", "title": "Chapter map", "body_html": "..."}`, and the Jinja2 template would conditionally emit the title div. More aligned with a strict reading of ADR-003's "structured intermediate representation through Jinja2" pattern. Rejected because: (1) the current IR does not have per-node typed objects -- the body_html is assembled as a flat HTML string by the parser, and callouts are already emitted as HTML divs within that string; (2) introducing a per-node IR type system for callouts alone would be an inconsistent half-measure unless all environment types were refactored simultaneously; (3) the Jinja2 template (`lecture.html.j2`) currently receives `body_html` as a pre-rendered string and outputs it with `| safe` -- it does not iterate over structured content nodes; (4) the refactoring cost is disproportionate to the benefit for a title element that is structurally simple. If the project later refactors toward a fully structured IR (where the template renders each node type), a future ADR can move callout titles into that structure.

**B. Strip the title entirely.**
Simpler than either option. Rejected because the corpus uses the title editorially: every callout starts with a one-line orientation that the human-author wrote on purpose. Stripping it discards authored content and degrades the reading surface, contrary to manifest section 3 (drive consumption).

**C. Concatenate the title into the first paragraph as bold text (no separate element).**
The title would appear as `<p><strong>Chapter map.</strong> Body text continues...` inside the callout. Rejected because: (1) it conflates title and body semantically -- a future CSS redesign or accessibility audit would not be able to target the title separately; (2) it requires the parser to identify and merge into the first paragraph node, which is more fragile than emitting a separate div; (3) the `.callout-title` CSS rule already exists and provides the correct visual treatment; using it is simpler.

## My recommendation vs the user's apparent preference

The user's direction (via the human pushback on Run 002) is to create formal ADRs for both TASK-004 decisions rather than resolving them within ADR-003's latitude. This ADR satisfies that direction. The substantive decision (emit title as `<div class="callout-title">` directly in the parser handler) aligns with what was described in Run 002's output and the project issue's Option 1. The user has not signaled a preference for a specific alternative among the options in the project issue. Aligned with user direction on process.

On the question of Option 1 (direct HTML emission) vs Option 2 (route through IR): the architect recommends Option 1 because it matches the existing code pattern and avoids a disproportionate refactoring cost. If the user prefers Option 2's stronger IR separation, the architect would accept that direction but notes the implementation cost is larger and the benefit materializes only if the project later adopts a fully structured IR -- which is not currently planned.

## Consequences

**Becomes possible:**
- Every callout environment with a `[Title]` argument renders the title as a visually distinct header at the top of the callout body, restoring the editorial intent of the corpus's titles.
- Callouts without titles render exactly as before (no regression).
- The `.callout-title` CSS rule applies uniformly, giving the human a single styling point for all callout titles across all five environment types.
- Future callout environments (if any are added to the corpus) can follow the same pattern: optional `[Title]` argument -> `<div class="callout-title">`.

**Becomes more expensive:**
- Adding math or macro support inside callout titles requires changing the title extraction from `_escape(text)` to `_convert_inline_latex(nodes)`. This is a bounded extension, not a supersedure.
- Migrating to a fully structured IR (Alternative A) would require reworking this title emission to move from parser-assembled HTML to template-rendered conditional. The cost is bounded to the five callout handlers plus a template change.

**Becomes impossible (under this ADR):**
- Rendering a callout title with a different structural element (e.g., `<h4>` instead of `<div class="callout-title">`) without updating both rendering paths and the CSS rule. The `.callout-title` class is the committed interface.

**Supersedure path:**
If the project adopts a fully structured IR where the Jinja2 template renders each content node type, a future ADR supersedes this one by moving callout title rendering from the parser into the template. The `.callout-title` CSS class and the visual treatment survive the supersedure; only the emission point changes.

## Manifest reading

Read as binding:
- section 3 Primary Objective ("drive consumption") -- missing callout titles degrade the reading surface; every callout in the corpus loses its orienting header. This decision restores that.
- section 5 Non-Goals ("no in-app authoring") -- the parser reads source; this decision does not write to it.
- section 6 Behaviors and Absolutes ("A Lecture has a single source") -- the title is derived from the LaTeX source's optional argument, not authored in parallel.

No manifest entries flagged as architecture-in-disguise.

## Conformance check

- **MC-6 (Lecture source is read-only).** Preserved. The parser reads the optional argument from the LaTeX source in memory; no file writes.
- **MC-3 (Mandatory/Optional designation).** Not touched. Callout titles do not affect M/O designation.
- **MC-7 (Single user).** Not touched.
- **MC-1 through MC-5, MC-8 through MC-10.** Not touched (no AI work, no Quiz, no persistence changes).
- **ADR-003 (rendering pipeline).** This decision uses ADR-003's "extend environment-specific handlers" clause. The callout handlers are being corrected to handle an argument they were previously passing through. The `_get_optional_arg` helper and `.callout-title` emission are extensions within ADR-003's strategy, not a change to the strategy itself.
- **ADR-008 (navigation styling layer).** ADR-008 scoped `lecture.css` for Lecture-body content styling including `.callout-*` rules. The `.callout-title` rule is a small addition within that scope -- content-body styling, not page chrome. No new CSS file needed.
- **ADR-010 (Playwright verification).** TASK-004 acceptance criteria require Playwright tests verifying callout title rendering. This ADR's decision is verified through the ADR-010 gate.
