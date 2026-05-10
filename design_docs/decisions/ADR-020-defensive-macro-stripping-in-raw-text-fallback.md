# ADR-020: Defensive macro-stripping pass in raw-text fallback paths — text-formatting macros do not leak from `_escape(raw)` sites

**Status:** `Accepted`
**Date:** 2026-05-10
**Task:** TASK-008
**Resolves:** `design_docs/project_issues/parser-fidelity-unhandled-environments-and-text-macros.md` (Gap B portion; sibling to ADR-019 which governs Gap A)
**Supersedes:** none

## Context

The TASK-005 corpus-wide validation pass (orchestrator Run 008) catalogued ~99 instances of "Raw `\textbf` / `\textit` / `\emph` / `\textsc` / `\texttt{`" leaking through to the rendered HTML body. ch-10 dominates with 60 instances; ch-13 (23), ch-04 (13), ch-02 (2), ch-12 (1) also affected.

The TASK-008 task file noted that inline handlers for these macros already exist (`app/parser.py:143-150`):

```python
if name == "textbf":
    result_parts.append(f"<strong>{get_arg_html(0)}</strong>")
elif name == "textit" or name == "emph":
    result_parts.append(f"<em>{get_arg_html(0)}</em>")
elif name == "texttt":
    result_parts.append(f'<span class="texttt">{get_arg_html(0)}</span>')
elif name == "textsc":
    result_parts.append(f"<span style=\"font-variant:small-caps\">{get_arg_html(0)}</span>")
```

The bleed therefore happens at code paths that bypass `_convert_inline_latex` — i.e., paths that emit raw escaped text via `_escape(...)`. The TASK-008 task file flagged Gap B's leak path as "not yet confirmed" and required the `/design` architect to reproduce the leak in a test before designing the fix.

The architect could not run the diagnostic test in `/design` mode (no shell access). However, static analysis of `app/parser.py` identifies **three sites** where `_escape(raw_text)` is called as a parse-failure fallback, and all three would emit `\textbf{X}` etc. as visible escaped text if pylatexenc fails to register the env / failed to parse the cell content:

1. **Tabular cell-walker fallback (line 462-466):**
   ```python
   try:
       walker = LatexWalker(cell)
       cell_nodelist, _, _ = walker.get_latex_nodes(pos=0)
       cell_html = _convert_inline_latex(cell_nodelist or [])
   except Exception:
       cell_html = _escape(cell)
   ```
   If `LatexWalker(cell)` throws on a complex cell content (e.g., ch-10 line 1894 `\begin{tabular}{p{3.2cm}|p{2.9cm}|...}` where the cell content is `\textbf{Problem $\downarrow$\ /\ Graph $\rightarrow$}`), the cell falls back to escaped text containing literal `\textbf{...}`.

2. **Callout body re-walker fallback in `_nodes_to_html` (line 829-835):**
   ```python
   try:
       _walker2 = _LW2(body_latex)
       body_nodelist2, _, _ = _walker2.get_latex_nodes(pos=0)
       body_html = _nodes_to_html(body_nodelist2 or [])
   except Exception:
       body_html = _escape(body_latex)
   ```
   Same shape: parse failure → escaped raw text → `\textbf{...}` leaks.

3. **Callout body re-walker fallback in `_convert_inline_latex` (line 249-255):**
   ```python
   try:
       _walker = _LW(body_latex)
       body_nodelist, _, _ = _walker.get_latex_nodes(pos=0)
       body_html = _convert_inline_latex(body_nodelist or [], context)
   except Exception:
       body_html = _escape(body_latex)
   ```
   Same shape.

There is also a fourth site: `_render_callout_title_html` (line 924-931) has the same pattern. And the outermost `parse_latex` (line 957-963) returns `""` on exception — that doesn't leak, but it silently drops the chapter, which is a different failure mode not addressed by this ADR.

The corpus shapes most likely to trigger the parse-failure path in the cell walker (site 1):
- ch-10 line 1894: `\begin{tabular}{p{3.2cm}|p{2.9cm}|p{3.2cm}|p{3.6cm}|p{2.6cm}}` with cells containing `\textbf{X $\rightarrow$ Y}` (math-mixed inline formatting).
- ch-10 line 510: `\begin{tabular}{rp{6.5cm}|l|l}` with cells containing `\texttt{...}` and inline math.
- Multiple corpus tables wrap their tabular in `\renewcommand{\arraystretch}{1.2}`, `\noindent\resizebox{\textwidth}{!}{...}`, `\multicolumn{N}{l}{...}` — any of these may cause pylatexenc to mis-segment the tabular's body, leading to cell content that contains nested env / macro tokens the cell walker can't reparse.

The corpus shapes most likely to trigger callout body re-walker failure (sites 2-3):
- Any callout containing a `[Title]` that itself contains a macro (e.g., `\begin{ideabox}[\textbf{Recap of the algorithm}]`) — the title-extraction regex stops at the first `]`, so a `]` inside `\textbf{[..]}` would mismatch.
- Any callout body that contains a TikZ block, an unknown env, or content pylatexenc parses inconsistently.

This decision is forced now because TASK-008's acceptance criteria require that text-formatting macro tokens do not appear as visible HTML body text outside `<pre>/<code>` — and that cannot be guaranteed without addressing the raw-text fallback paths.

The **architect was unable to confirm via empirical reproduction** which of the three sites (or some combination) is the actual leak source for the 99 catalogued instances. The first action of `/implement` must be to run the diagnostic test (see `design_docs/project_issues/task008-leak-path-empirical-confirmation.md`) and pinpoint the responsible site(s). The decision recorded here is robust to all three: the defensive-stripping pass is applied at every `_escape(raw)` fallback site, so the actual responsible site does not change the fix shape.

## Decision

A new helper `_strip_text_formatting_macros(raw: str) -> str` is added to `app/parser.py`. It is applied at every site where the parser falls back to emitting `_escape(raw_latex_text)` as the result of a pylatexenc parse failure. The helper transforms the following patterns inside the raw text *before* HTML-escaping:

1. **Recognized text-formatting macros become inline HTML:**
   - `\textbf{X}` → `<strong>{escaped X}</strong>`
   - `\textit{X}` → `<em>{escaped X}</em>`
   - `\emph{X}` → `<em>{escaped X}</em>`
   - `\texttt{X}` → `<span class="texttt">{escaped X}</span>` (per ADR-018)
   - `\textsc{X}` → `<span style="font-variant:small-caps">{escaped X}</span>`
2. **Unrecognized `\macroname{X}` patterns are stripped to their argument content** (not the macro wrapper). The macro name is consumed and discarded; the inner content is HTML-escaped and emitted in place. This matches the existing unknown-macro behavior in `_convert_inline_latex` (line 211-212).
3. **Unrecognized `\macroname` (no argument) is stripped silently** (consumed and emitted as nothing).
4. **Wrapper `\begin{X}` and `\end{X}` substrings are consumed** (emitted as nothing). The body content between them is preserved (and recursively run through the same defensive pass).
5. **All remaining text** is HTML-escaped via the existing `_escape` helper.

The transformation uses balanced-brace consumption (the same mechanism ADR-017 introduced for tabular column-spec stripping) to walk `\macroname{...}` arguments without breaking on nested `{...}` or unbalanced bracket content. The implementer is free to express the walk as a small loop, a regex-with-recursive-pattern, or any equivalent mechanism; the architectural commitment is on the **semantic** ("the argument is a balanced-brace span starting after the macro name"), not on the syntactic shape.

The helper is applied at four sites in `app/parser.py`:

- **Site A** — `_render_tabular`, line 466 (cell-walker fallback): `cell_html = _strip_text_formatting_macros(cell)` (replaces `_escape(cell)`).
- **Site B** — `_convert_inline_latex` callout body fallback, line 255: `body_html = _strip_text_formatting_macros(body_latex)` (replaces `_escape(body_latex)`).
- **Site C** — `_nodes_to_html` callout body fallback, line 835: `body_html = _strip_text_formatting_macros(body_latex)` (replaces `_escape(body_latex)`).
- **Site D** — `_render_callout_title_html` fallback, line 930: `title_html = _strip_text_formatting_macros(title_latex)` (replaces `_escape(title_latex)`).

The successful (non-fallback) walker paths are unchanged. When pylatexenc parses the content correctly, the existing `_convert_inline_latex` / `_nodes_to_html` recursion handles the macros; the defensive helper is dead code on those paths. Only the parse-failure branches activate it.

### What this ADR explicitly does NOT decide

- **Replacing pylatexenc with a custom LaTeX parser.** The defensive helper is a fallback-path strengthening, not a parser strategy change. ADR-003 still governs.
- **Handling every text macro in `_strip_text_formatting_macros`.** Only the four corpus-impacting macros (`textbf`, `textit`, `emph`, `texttt`, `textsc`) are explicitly mapped; other unknown macros are stripped to their argument content (Decision §2-3). If a future corpus introduces a macro that needs distinguishing rendering inside a fallback path, supersede this ADR with one that adds the macro.
- **Per-Chapter parse-failure logging.** The structured `logger.warning` already fires at the original `try/except` site; the helper does not need to re-warn. The four sites' existing exception handling stays; only the fallback emission changes.
- **Fixing the underlying pylatexenc parse failures.** This ADR is defensive: when the parser fails, the visible damage is contained. Fixing the root cause (e.g., registering custom envs in a pylatexenc context DB so they parse correctly) is out of scope and deferred. If a future Chapter's parse-failure rate rises high enough to justify it, supersede with a context-DB ADR.
- **Math content inside fallback paths.** Inline math `$...$` and display math `\[...\]` in fallback raw text are passed through verbatim (the helper does NOT escape `$` or `\[` characters that would break MathJax). The helper preserves math delimiters as-is so MathJax can still render them.

## Alternatives considered

**A. Replace `_escape(raw)` fallbacks with `<pre>{escaped raw}</pre>` blocks.**
The simplest "make the leak invisible" option — wrap the raw text in a `<pre>` so it renders monospaced (and the test suite's `_PRE_CODE_PATTERN` correctly classifies it as a "safe region" where LaTeX may appear). Rejected because:
- Visible regression: a tabular cell that previously rendered `\textbf{X}` as inline italics on a parse failure would suddenly render as a monospaced code block. The reader sees a structurally-broken table cell instead of a visually-correct (if formatted-imperfectly) cell.
- Doesn't actually preserve the editorial intent of the original LaTeX; just hides the leak by reclassifying it.
- Would fool the regression tests but not the human reader.

**B. Drop the `try/except` entirely and let pylatexenc parse failures crash the request.**
"Visible failure, no fabrication" interpreted maximally — if the parser can't handle a Chapter, the Chapter returns 500. Rejected because:
- The existing 12 Chapters all return HTTP 200 today; reverting to crash-on-failure would regress AC-1 from TASK-005.
- The failures we're working around are pylatexenc's, not the project's. The project's "do not crash" commitment (ADR-003) was made precisely because pylatexenc's failure modes are non-deterministic across content.
- "Visible failure" is honored by the structured `logger.warning` at the original site; the user-visible failure is the structured log entry, not a 500.

**C. Apply the defensive-stripping pass globally (including in successful walker paths).**
Instead of activating only on parse failure, run the helper as a final pass on every emitted HTML chunk. Rejected because:
- The successful path's `_convert_inline_latex` correctly maps `\textbf{}` to `<strong>` already; the global pass would have no effect on correctly-walked content.
- Risk of double-substitution on edge cases (`<strong>\textbf{X}</strong>` — already-emitted HTML being misinterpreted). The fallback-only scoping eliminates this risk by construction.
- Adds an unnecessary regex pass to every render of every Chapter. Cost is small but the architectural complexity is real.

**D. Write a custom pylatexenc context DB that registers every corpus env and macro with explicit argspecs (so parse failures don't happen).**
The "fix the root cause" option. Rejected for TASK-008 because:
- A custom context DB is a substantial refactor of `app/parser.py` (every env handler needs to know about the new context); ADR-003's "extend with environment-specific handlers" clause covers per-env additions but not a wholesale context-DB rewrite.
- The architect has not confirmed via empirical test which envs/macros are causing the parse failures; designing a context DB without that data is speculative.
- The defensive-stripping approach (this ADR) is a safety net that lets the project keep ADR-003's strategy intact while addressing the user-visible damage. If post-implementation evidence shows that parse failures continue at high rate, a future ADR can add the context DB on top of this defensive pass — they are complementary, not exclusive.

**E. Strip text-formatting macros via a regex pre-pass on the LaTeX source-text before pylatexenc walks it.**
A single regex pass at the top of `parse_latex`. Rejected because:
- ADR-003 commits to "walking the LaTeX node tree in Python," not "regexing the source." A pre-pass that rewrites the source before parsing contradicts that strategy.
- The macros that should be stripped depend on context — `\textbf{X}` inside a `<pre>` (lstlisting) listing is legitimate visible content; pre-stripping would corrupt code listings.
- The fallback-path scoping in this ADR avoids both objections by restricting the strip to the (small, parse-failed) fallback branches.

## My recommendation vs the user's apparent preference

The user's apparent direction (TASK-008 task file) was **trace the leak first, then design**. The architect agrees with this direction in principle but could not execute it (no shell access in `/design` mode to run the diagnostic). The architect's recorded decision is a static-analysis-driven design that is **robust to whichever of the three identified leak sites turns out to be responsible**, with an explicit project_issue (`task008-leak-path-empirical-confirmation`) capturing the diagnostic work as the first step of `/implement`.

If the diagnostic test (run during `/implement`) reveals that the actual leak path is something other than the four identified `_escape(raw)` fallback sites, the implementer must `ESCALATION:` back to the architect and `/design` cycles a supersedure. The architect's commitment is to the **decision shape** (defensive-stripping pass at parse-failure fallback sites), not to "this fix definitely closes the bug" — that confirmation requires the empirical test the architect could not run.

The architect mildly disagrees with the task file's framing of Gap B as a separate decision from Gap A. The task file said: "the architect commits to: (a) reproduce the leak in a test, (b) trace the call site, (c) decide whether one ADR covers both gaps or two ADRs separate them." The architect chose **two ADRs** because the architectural sites differ:

- **ADR-019** governs the env-level wrapper (the unknown-environment dispatch in `_nodes_to_html` and `_convert_inline_latex` — the place where pylatexenc DID register an env but the parser doesn't have a handler).
- **ADR-020** (this ADR) governs the raw-text fallback (the place where pylatexenc FAILED to parse and the parser dropped to `_escape(raw)`).

These are different code sites with different supersedure paths. Combining them into one ADR would obscure the chronology when one is later superseded but the other is not.

If the user prefers a single combined ADR, this can be folded into ADR-019 at gate-time without substantive change.

Aligned with user direction on substance (defensive fix); pushback on the user's framing of "Option 3 hybrid for Gap A" (see ADR-019); pushback on the framing of "one shared root cause" (split into two ADRs because two architectural sites).

## Consequences

**Becomes possible:**

- Every `_escape(raw)` fallback site emits HTML in which `\textbf{X}` etc. become `<strong>X</strong>` etc., not literal escaped text. The 99 catalogued visible-leak instances should clear (modulo the empirical-confirmation work in `/implement`).
- A Playwright cross-corpus assertion of the form "no rendered chapter contains `\textbf{` outside `<pre>/<code>` zones" is a stable regression test.
- Future raw-text fallback sites (any new `_escape(raw)` added to the parser) get the defensive pass for free if the implementer uses `_strip_text_formatting_macros` instead of `_escape` at those sites. The naming convention (`_strip_*` vs. `_escape`) signals the right default.
- Math content (`$...$`, `\[...\]`) inside fallback paths is preserved correctly so MathJax still renders.

**Becomes more expensive:**

- Adding a new text-formatting macro that needs distinguishing rendering inside a fallback path requires extending `_strip_text_formatting_macros`. Bounded — one branch per macro.
- The defensive-stripping helper is a second copy of macro→HTML mapping logic (the first being in `_convert_inline_latex`). If the mapping needs to change (e.g., `\textbf{}` should emit something other than `<strong>`), both copies need updating. Mitigation: extract a shared mapping table that both use.

**Becomes impossible (under this ADR):**

- A `\textbf{X}` literal substring in the rendered HTML body for any Chapter, regardless of whether pylatexenc parsed the surrounding context successfully or fell back. (Same for the other four mapped macros.)
- Reverting to `_escape(raw)` at any of the four sites without a supersedure ADR.

**Supersedure path:**

- If empirical evidence (post-`/implement` diagnostic) shows that the actual leak path is somewhere other than the four identified fallback sites, supersede with an ADR that targets the actual site. The defensive-stripping helper survives; only the call sites diverge.
- If the project later implements a custom pylatexenc context DB so parse failures stop happening, the defensive helper becomes dead code; supersede with an ADR that removes the helper. Cost is bounded.
- If the project refactors toward a fully structured IR, the helper moves into the IR-emission layer; the parse-failure-path concept survives but in a different shape.

## Manifest reading

Read as binding for this decision:

- **§3 Primary Objective ("drive consumption … via per-Chapter Lectures").** Bound the requirement: 99 visible macro-leak instances degrade consumption; this ADR closes them.
- **§5 Non-Goals: "No in-app authoring of lecture content."** Honored — the fix lives in `app/parser.py`. No source file is edited.
- **§6 Behaviors and Absolutes: "A Lecture has a single source"; "AI failures are visible" (broadly read as "visible failure, no fabrication").** Bound the structured-warning continuation (the existing `logger.warning` at each fallback site stays); the visible damage of the parse failure is contained, but the failure is still surfaced via the log.
- **§7 Invariants.** Not directly touched.

No manifest entries flagged as architecture-in-disguise.

## Conformance check

- **MC-1 (No direct LLM/agent SDK use).** Not touched. No AI surface.
- **MC-2 (Quizzes scope to one Section).** Not touched.
- **MC-3 (Mandatory/Optional designation).** Not touched.
- **MC-4 (AI work asynchronous).** Not touched.
- **MC-5 (AI failures surfaced).** Not touched.
- **MC-6 (Lecture source read-only).** *Honored.* The fix edits `app/parser.py`. No path under `content/latex/` is touched.
- **MC-7 (Single user).** Not touched.
- **MC-8..MC-10.** Not touched.

ADR-relationship checks:

- **ADR-003 (rendering pipeline).** Honored. The defensive-stripping helper operates strictly within ADR-003's "warn-per-node, do not crash, do not fabricate" envelope. The structured warning at each fallback site continues; the helper just changes what gets emitted on the failure branch from `_escape(raw)` to a stripped/processed equivalent.
- **ADR-008 (CSS layering).** Honored. No new CSS rules are introduced by this ADR (the emitted `<strong>`, `<em>`, `<span class="texttt">`, `<span style="font-variant:small-caps">` already have CSS rules from prior ADRs — `lecture.css` for `.texttt` per ADR-018, browser defaults for `<strong>` and `<em>`).
- **ADR-010 (Playwright verification).** TASK-008 acceptance criteria require Playwright cross-corpus assertions; this ADR's decision is verified through the ADR-010 gate.
- **ADR-011 / ADR-017 (tabular spec handling).** Site A (the cell-walker fallback) is in `_render_tabular`, the same handler ADR-011/017 govern. This ADR strengthens the cell fallback without changing the spec-stripping behavior. No conflict.
- **ADR-012 (callout title rendering).** Sites B/C/D are inside the callout-body and callout-title rendering paths ADR-012 governs. This ADR strengthens those paths' parse-failure fallbacks. No conflict — the successful-parse path is unchanged.
- **ADR-018 (texttt as `<span class="texttt">`).** The defensive helper maps `\texttt{X}` to `<span class="texttt">{X}</span>` — same emission as ADR-018. The MathJax math-passthrough commitment from ADR-018 is preserved (math delimiters inside fallback raw text are not escaped by this helper).
- **ADR-019 (unhandled-environment strategy).** Sibling ADR for TASK-008. ADR-019 governs the env-level wrapper at the unknown-env dispatch sites; ADR-020 governs the raw-text fallback. They are complementary; together they close visible-LaTeX-bleed across the corpus.

## Project_issue resolution

`design_docs/project_issues/parser-fidelity-unhandled-environments-and-text-macros.md` is updated in this `/design` cycle to `Status: Resolved by ADR-019 (Gap A) and ADR-020 (Gap B) (Proposed; contingent on acceptance)` with a one-line resolution note (handled in the ADR-019 update; this ADR shares the resolution pointer).

A new project_issue is opened: `design_docs/project_issues/task008-leak-path-empirical-confirmation.md` — captures the diagnostic work the architect could not perform in `/design` (running a test that exercises every Chapter's GET /lecture/{id} response and reports literal `\begin{...}`, `\end{...}`, `\textbf{`, `\textit{`, `\emph{`, `\textsc{` substrings outside `<pre>/<code>` and math zones). The implementer must run this diagnostic as the first step of `/implement TASK-008` and confirm the actual leak site(s) before applying the fix. If the diagnostic reveals a site not covered by ADR-019/020, the implementer escalates and the architect designs a supersedure.
