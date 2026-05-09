# ADR-011: Tabular column spec handling — strip from rendered output, warn-per-node for complex spec features

**Status:** `Accepted`
**Date:** 2026-05-08
**Task:** TASK-004
**Resolves:** `design_docs/project_issues/latex-tabular-column-spec-passthrough.md`
**Supersedes:** none

## Context

The LaTeX parser's `_render_tabular` handler in `app/parser.py` currently leaks the column-specification argument from `\begin{tabular}{lll}` into the first rendered table row as visible text. Every `tabular` environment in the corpus (verified in Chapters 1, 5, 6, 7, 13 at minimum) produces a broken first row containing the literal column-spec string (e.g., `lll`, `l|c|r`). The column spec is LaTeX layout metadata that controls column count, alignment, and separators -- it has no rendered-text meaning.

This bug was surfaced during TASK-003's Playwright screenshot review (ADR-010 verification gate) and filed as `design_docs/project_issues/latex-tabular-column-spec-passthrough.md`. The project issue enumerates three options: strip-and-ignore, strip-and-preserve-alignment-as-CSS, and strip-with-warn-per-node.

ADR-003 (Accepted) commits the project to a pylatexenc-based parser that emits structured intermediate representation through Jinja2. ADR-003 establishes the "warn-per-node and continue" pattern for unrecognized or uninterpretable nodes. The current `_render_tabular` implementation already uses a regex to extract the tabular body content from the raw LaTeX verbatim, but the regex correctly skips the column spec -- the bug is that the column spec was previously not being stripped. The existing code on disk (as of TASK-004's design phase) already has the fix in place via the regex pattern `\\begin\{tabular\}\{[^}]*\}(.*?)\\end\{tabular\}` which skips the column spec group. However, the architectural decision about *how* to handle column spec features the parser does not interpret (vertical bars, `p{width}`, `@{...}`) has not been recorded.

This decision is forced by TASK-004, which requires the parser to handle tabular environments correctly. The human pushed back on resolving this "within ADR-003's latitude" without a formal ADR, requesting that the decision go through the human gate for consistency with the project's ADR discipline.

## Decision

The parser's `_render_tabular` handler strips the column-specification argument from the rendered output entirely. Only data rows from the tabular body are rendered as HTML `<tr>` elements. The column spec does not appear as visible text in any rendered table.

For column-spec features that the parser does not interpret -- specifically vertical bars (`|`), paragraph columns (`p{width}`), inter-column spacing (`@{...}`), and column-type modifiers (`>{...}`, `<{...}`) -- the parser logs a structured warning per ADR-003's warn-per-node pattern. The warning identifies the specific spec feature encountered and the chapter context. This preserves the "visible failure, no fabrication" principle from ADR-003 and manifest section 6: uninterpreted features are logged so the human can review them, but the table still renders with its data rows intact.

Simple alignment letters (`l`, `c`, `r`) are stripped without warning -- they are understood but not preserved in the HTML output. Browser/CSS defaults handle table cell alignment; the existing `lecture.css` table rules (border-collapse, padding) apply uniformly.

## Alternatives considered

**A. Strip-and-ignore (no warnings for any spec feature).**
The simplest option. Strip the column spec entirely; emit only data rows; log nothing about uninterpreted features. Rejected because it silently discards information about complex spec features that *might* affect rendered appearance (e.g., `p{3in}` specifying a column width, `|` specifying vertical rules). ADR-003's "warn-per-node" pattern exists precisely to surface such cases for human review without crashing. Ignoring silently when the parser has the information to warn is inconsistent with that pattern.

**B. Strip column spec but preserve alignment as per-column CSS classes.**
Parse the column spec into per-column descriptors (`l` -> `text-align: left`, `c` -> `text-align: center`, `r` -> `text-align: right`); emit `<td class="align-left">` (or `data-align="left"`) on each cell; add CSS rules to `lecture.css`. More faithful to the LaTeX source. Rejected because: (1) the corpus primarily uses simple `l` specs where left-alignment is already the browser default; (2) parsing column specs into per-column metadata and mapping them onto the correct `<td>` elements requires tracking column indices across `&`-split cells, including handling `\multicolumn` spans -- a substantially larger implementation surface than the current regex-based approach; (3) the architectural cost (new CSS classes, column-index tracking, multicolumn awareness) is disproportionate to the visual benefit for this corpus; (4) a future ADR can add alignment preservation if the corpus demands it, without superseding this one -- the warn-per-node output from this ADR would surface exactly the cases where alignment matters.

**C. Strip-with-warn-per-node for ALL spec characters (including simple `l`, `c`, `r`).**
Would warn on every column spec in every table. Rejected because simple alignment letters are well-understood (even though not preserved as CSS); warning on them would flood the log with non-actionable noise. The warn-per-node pattern is most valuable when it surfaces features the parser genuinely does not interpret.

## My recommendation vs the user's apparent preference

The user's direction (via the human pushback on Run 002) is to create formal ADRs for both TASK-004 decisions rather than resolving them within ADR-003's latitude. This ADR satisfies that direction. The substantive decision (strip + warn for complex features) aligns with what was described in Run 002's output and the project issue's Option 1 + Option 3 hybrid. The user has not signaled a preference for a specific alternative among the three options in the project issue. Aligned with user direction on process; the substantive choice is the architect's recommendation.

## Consequences

**Becomes possible:**
- Every table in the corpus renders without a spurious first row containing the column spec.
- Complex spec features (`|`, `p{width}`, `@{...}`) are logged as structured warnings, surfacing them for human review during multi-chapter validation passes.
- A future ADR can add alignment preservation (Alternative B) without superseding this one -- the decision to strip is compatible with a later decision to also preserve alignment metadata.

**Becomes more expensive:**
- Adding column-alignment preservation later requires a new ADR and parser changes (tracking column indices, emitting CSS classes). This cost is bounded and deferred deliberately.
- Vertical-rule rendering (`|` in column specs) is not supported; tables that rely on vertical rules for readability will render without them. The corpus primarily uses horizontal rules (`\hline`, `\midrule`) which the parser already strips.

**Becomes impossible (under this ADR):**
- Preserving LaTeX column alignment in the rendered HTML without a superseding or extending ADR.

**Supersedure path:**
If a future chapter's tables require column alignment or vertical rules for readability, a new ADR extends the tabular handler to parse and emit alignment metadata. This ADR's strip-and-warn behavior is the floor; the extension adds preservation on top.

## Manifest reading

Read as binding:
- section 3 Primary Objective ("drive consumption") -- broken first rows in every table degrade the consumption surface; this decision fixes that.
- section 5 Non-Goals ("no in-app authoring") -- the parser reads source; this decision does not write to it.
- section 6 Behaviors and Absolutes ("A Lecture has a single source"; visible failures) -- the warn-per-node pattern honors the visible-failure principle for uninterpreted features.

No manifest entries flagged as architecture-in-disguise.

## Conformance check

- **MC-6 (Lecture source is read-only).** Preserved. The parser reads `content/latex/` files; this decision changes how the column spec is processed in memory, not how files are accessed. No write path introduced.
- **MC-3 (Mandatory/Optional designation).** Not touched. Table rendering does not affect M/O designation.
- **MC-7 (Single user).** Not touched.
- **MC-1 through MC-5, MC-8 through MC-10.** Not touched (no AI work, no Quiz, no persistence changes).
- **ADR-003 (rendering pipeline).** This decision operates within ADR-003's "extend environment-specific handlers" clause. The `_render_tabular` handler is being corrected, not replaced. The warn-per-node pattern is ADR-003's own error-handling contract.
- **ADR-010 (Playwright verification).** TASK-004 acceptance criteria require Playwright tests verifying the fix. This ADR's decision is verified through the ADR-010 gate.
