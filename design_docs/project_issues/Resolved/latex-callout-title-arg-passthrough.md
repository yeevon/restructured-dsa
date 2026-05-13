# LaTeX callout `[Title]` optional argument renders as bracketed inline text instead of a callout title

**Status:** Resolved by ADR-012 (Accepted)
**Surfaced:** 2026-05-08 (TASK-003 human screenshot review; orchestrator opened from rendering-fidelity finding during the ADR-010 verification gate)
**Decide when:** before the next task that touches callout rendering or callout styling. Defensible to defer to a focused fidelity task at any time.

## Question

The corpus uses LaTeX callout environments with an optional argument that is conventionally a *title*: `\begin{ideabox}[Chapter map]`, `\begin{defnbox}[List]`, `\begin{notebox}[Stability of the gather step is essential]`, `\begin{warnbox}[...]`, `\begin{examplebox}[Three takes on "list" in C++]`. The optional bracketed argument is the callout's title — it should render as a header (bold, slightly larger, or wrapped in a heading element) at the top of the callout body. Today the renderer passes the brackets through literally, so the rendered DOM contains text like `[Stability of the gather step is essential]` inline, and the callout has no header treatment.

Five callout environments are affected (verified by grep against `content/latex/`): `ideabox`, `defnbox`, `notebox`, `warnbox`, `examplebox`. All five exist in `lecture.css` with palette/border treatment (`.callout-ideabox`, `.callout-defnbox`, `.callout-notebox`, `.callout-warnbox`, `.callout-examplebox`); none of them have a child rule for a title element because no title element is currently emitted into the DOM.

What is the correct rendered behavior?

- **Extract the optional argument as a callout title; emit it as a `<header>` or `<h*>` (or a `<div class="callout-title">`) inside the callout body; style with CSS.** Standard treatment for "boxed callout with header." Restores the editorial intent (each callout has a one-line description that orients the reader before the body begins).
- **Strip the optional argument entirely.** Loses the title text but removes the bug. Editorially worse — the human-author's title text is discarded.
- **Concatenate the title into the first paragraph as bold text.** Halfway between the two: title is not a separate header element, but it is visually distinguishable. Heavier intermediate-representation surface than option 1; easier than wholesale callout-template restructuring.

The CSS layer (`.callout-*` rules in `lecture.css`) is *prepared* to style a title element if one were emitted — the boxed-callout treatment already has the visual room. The fix is in the parser / intermediate representation, plus a tiny CSS rule (a few lines per callout type, or a single `.callout-title` rule used by all five).

## Options known

1. **Parse the optional argument in each callout environment's handler; emit a `<header class="callout-title">` (or `<div class="callout-title">`) as the first child of the callout body; add a CSS rule to `lecture.css` for `.callout-title` (bold, slightly larger, palette-matched border-bottom or margin-bottom).** Single architectural commitment: callouts have an optional title that is structurally distinct from the body. Editorially clean. Implementer change: parser adjustment for all five callout environments + a small CSS rule. Recommended starting point.

2. **Add the title argument to the callout's intermediate representation as a separate field; let the Jinja2 template emit the title element conditionally.** Same outcome as option 1 but routed through the IR rather than the parser hand-emitting HTML. Aligns with ADR-003's "structured intermediate representation through Jinja2." Slightly more refactoring; cleaner long-term.

3. **Strip the title entirely.** Easier; loses the title text. Not recommended (the corpus uses the title editorially: every callout starts with a one-line orientation that the human-author wrote on purpose).

4. **Render the title as concatenated bold text in the first paragraph.** Awkward; mixes title with body. Not recommended.

5. **Defer indefinitely — accept the bracketed-title passthrough.** Not recommended; the bug is visible on every callout in the corpus and is editorially load-bearing (the titles are not redundant with the body — they orient the reader).

## Constraints

- **ADR-003 ("Rendering pipeline")** owns the parser/IR/Jinja2 contract. Whatever resolves this issue must fit inside that pipeline shape.
- **`lecture.css` already has `.callout-ideabox` / `.callout-defnbox` / `.callout-notebox` / `.callout-warnbox` / `.callout-examplebox` palette rules.** Adding a `.callout-title` rule (or per-callout title rules) is a small CSS surface; the major work is parser-side.
- **Manifest §3 ("drive consumption")** — bracketed-title passthrough is visible on every callout and breaks the editorial flow of the chapters. The styling task (TASK-003) has already shipped the callout palette; the missing piece is the parser emitting a title element for the CSS to style.
- **No new dependency** — `pylatexenc` exposes optional environment arguments to the node walker; the parser handler just needs to consume them.
- The five affected environments share the same shape (optional `[title]` then body content). A single fix applies to all five.

## Why this is filed as a project_issue, not folded into a TASK-003 in-scope item

TASK-003 is the navigation styling task. Its scope (per ADR-008) is the rail, the landing page, and the page-level grid layout. The callout-title bug is in the body parser, not the rail/landing/page-grid surface. Bundling a callout-parser fix into TASK-003 would (a) mix a content-fidelity decision into a styling decision, (b) require parser changes to `app/parser.py` outside ADR-008's commitment, (c) delay TASK-003's primary deliverable.

The bug was surfaced during the human's screenshot-review portion of TASK-003's verification gate (ADR-010) — i.e., the styling task's verification mechanism caught a *pre-existing* parser bug, exactly what ADR-010's screenshot review is designed to surface.

Defensible to revisit at any point; the issue is `Open` so the next architect run that touches body rendering or callout styling can pick it up.

## Resolution

Resolved by ADR-012 (Accepted). The decision is: the parser handler extracts the optional `[Title]` argument and emits it as `<div class="callout-title">Title</div>` as the first child inside the callout div. The `.callout-title` CSS rule in `lecture.css` styles it (bold, uppercase, letter-spacing, bottom margin). Consistent across all five callout environments. Both rendering paths (`_nodes_to_html` and `_convert_inline_latex`) handle titles. No IR contract change -- the title is embedded HTML within `body_html`, consistent with ADR-003's existing pattern.
