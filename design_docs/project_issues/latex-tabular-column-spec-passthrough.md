# LaTeX `tabular` column spec passes through to rendered table's first row

**Status:** Resolved by ADR-011 (Accepted)
**Surfaced:** 2026-05-08 (TASK-003 human screenshot review; orchestrator opened from rendering-fidelity finding during the ADR-010 verification gate)
**Decide when:** before the next task that introduces or restyles tables, OR before any task that adds a fixture/spec for table rendering, whichever comes first. Defensible to defer to a focused fidelity task at any time.

## Question

Every `\begin{tabular}{...}` environment in the corpus is rendered with its column-spec argument leaking into the first `<tr>` of the rendered HTML table. Concrete: `\begin{tabular}{lll}` produces a first row that visibly contains the literal text `lll` (the column-alignment spec); `\begin{tabular}{l|l@{}}` would produce `l|l@` etc. The column spec is LaTeX layout metadata — it tells `tabular` how many columns and how to align them — and it has no rendered-text meaning. The renderer is treating it as a data row.

The corpus contains many `tabular` environments (verified in Chapters 1, 5, 6, 7, 13 at minimum), with column specs ranging from simple (`ll`, `lll`) to more elaborate (vertical bars, `@{...}` separators, `p{...}` widths). Every one of them currently emits a broken first row.

What is the correct rendered behavior?

The question has multiple defensible answers and no single Accepted ADR resolves it:

- **Strip the column spec entirely; emit only data rows.** Column count is implicit from the data rows; alignment defaults to browser/CSS defaults (or to a global `<table>` rule in `lecture.css`). Loses LaTeX's left/center/right specifications at the rendered HTML layer.
- **Strip the column spec but preserve alignment via per-column CSS classes** (e.g., `<td class="col-l">`, `<td class="col-c">`). Preserves intent; adds a small CSS surface for column alignment. More work but visually closer to LaTeX.
- **Strip the column spec but preserve `|` separators as CSS `border-left` rules.** Captures the most-common LaTeX-table-with-vertical-rules pattern. Heavier; not all `|` specs are the same.

A related question: should the renderer also handle `@{...}` separators, `p{width}` columns, and `>{...}` row prefixes? The corpus uses primarily simple alignment specs, but the renderer needs a story for whatever shape it doesn't handle (warn-per-node? strip silently? fail loudly?). ADR-003's "warn-per-node and continue" pattern for the body parser is the natural floor; the column-spec failure is currently *not* warning, it is *passing through as text*, which is the wrong failure mode.

## Options known

1. **Strip the column spec inside the `tabular` parser; ignore alignment / separators / column widths.** Simplest. Rendered tables are correct (no spurious first row), with browser-default alignment. Implementer change: locate the `tabular` handler in `app/parser.py` and swallow the spec argument; emit only data rows. Loses some LaTeX visual fidelity at the rendered layer.

2. **Parse the column spec into a per-column descriptor, attach as data attributes or CSS classes on `<td>`/`<th>` elements; let `lecture.css` style alignment.** Preserves intent. Implementer change: parse `lll` / `l|c|r` / `p{1in}` etc. into column metadata; emit `<td class="align-left">` (or `data-align="left"`); add CSS rules. Larger change; more architectural surface. Closer to a renderer rewrite for tables than a fix.

3. **Run column specs through pylatexenc node-walker the same way the body parser walks math/code; emit warn-per-node for unhandled spec shapes; strip spec argument from the rendered output regardless.** Hybrid: visual outcome of option 1, but at least the parser logs unknown spec shapes for the human's review. Aligns with ADR-003's existing "warn-per-node and continue" failure-mode pattern.

4. **Defer indefinitely — accept the column-spec passthrough as a known cosmetic defect.** Not recommended; the bug is visible on every table in the corpus and undermines the manifest §3 ("drive consumption") objective.

## Constraints

- **ADR-003 ("Rendering pipeline")** commits to a `pylatexenc`-based parser that emits a structured intermediate representation through Jinja2. The current `tabular` handler is leaking the column-spec argument into the rendered output rather than treating it as parser metadata. Whatever resolves this issue must align with ADR-003's "warn-per-node, fail-loudly-on-unknown" semantics.
- **Manifest §3 ("drive consumption")** — broken first rows in every table degrade the consumption surface; the styling layer (ADR-008) cannot mask a parser bug that emits the wrong cells.
- **No new dependency** — `pylatexenc` already exposes the column spec to a node walker; the issue is what the handler does with it.
- The first-row passthrough is a content-fidelity bug, not a styling bug. CSS cannot fix it (the spec is in the DOM as text inside a `<td>`, not as a separate row CSS could hide). The fix lives in the parser/intermediate-representation layer.

## Why this is filed as a project_issue, not folded into a TASK-003 in-scope item

TASK-003 is the navigation styling task. Its scope (per ADR-008) is the rail, the landing page, and the page-level grid layout — explicitly not the body parser. Bundling a `tabular` parser fix into TASK-003 would (a) mix a content-fidelity decision into a styling decision, (b) require a follow-up ADR (parser change, not CSS), (c) delay TASK-003's primary deliverable for a parser-architecture discussion that is not yet ready.

The bug was surfaced during the human's screenshot-review portion of TASK-003's verification gate (ADR-010) — i.e., the styling task's verification mechanism caught a *pre-existing* parser bug, exactly the failure mode ADR-010's screenshot review is designed to surface. The right outcome is: TASK-003 commits as planned (styling work green), this issue gets triaged into the next task.

Defensible to revisit at any point; the issue is `Open` so the next architect run that touches body rendering or table fidelity can pick it up.

## Resolution

Resolved by ADR-011. The decision is: strip the column-spec argument from rendered output entirely (only data rows render); log a structured warning per ADR-003's warn-per-node pattern for complex/uninterpreted spec features (vertical bars, `p{width}`, `@{...}`). Simple alignment letters (`l`, `c`, `r`) are stripped without warning. This is a hybrid of Option 1 (strip-and-ignore for rendered output) and Option 3 (warn-per-node for uninterpreted features). ADR-011 is `Proposed` and awaits human acceptance before implementation proceeds.
