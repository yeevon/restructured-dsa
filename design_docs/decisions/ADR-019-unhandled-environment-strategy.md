# ADR-019: Unhandled-environment rendering strategy — generic consume-and-skip fallback (no per-env editorial commitments)

**Status:** `Accepted`
**Date:** 2026-05-10
**Task:** TASK-008
**Resolves:** `design_docs/project_issues/parser-fidelity-unhandled-environments-and-text-macros.md` (Gap A portion)
**Supersedes:** none

## Context

The TASK-005 corpus-wide validation pass (orchestrator Run 008) catalogued ~28 instances of "Unhandled `\begin{...}` / `\end{...}` bleed-through" with ch-09 as the dominant Chapter (22 instances). The TASK-008 task file inherited this framing and forecast Option 3 (hybrid: explicit handlers for the top-frequency unhandled envs `algorithm`, `algorithmic`, `proof`, `theorem`, `figure`; generic fallback for the long tail).

The TASK-008 architect's `/design`-time corpus walk (mandated by the task file as a hard prerequisite) produced a different finding:

**Corpus walk results (Glob over `content/latex/*.tex`, all 12 Chapter files, every `\begin{[a-zA-Z*]+}` substring):**

| Env name | Total occurrences across corpus | Parser status |
|---|---|---|
| `document` | 12 | handled (extracted as body) |
| `ideabox`, `defnbox`, `notebox`, `warnbox`, `examplebox` | ~111 (TASK-001 audit count) | handled (callout dispatch, ADR-012) |
| `itemize`, `enumerate` | dozens | handled (`_render_list`) |
| `verbatim`, `lstlisting` | many | handled (`<pre><code>`) |
| `center`, `flushleft`, `flushright`, `minipage` | many | handled (passthrough as `<div class="X">`) |
| `tabular`, `array` (display-context) | many | handled (`_render_tabular`, ADR-011/017) |
| `array`, `cases`, `aligned`, `matrix`, `pmatrix`, `bmatrix`, `smallmatrix`, `split` | 13 (`array` only) | inside `\[...\]` math; passed through as `LatexMathNode.latex_verbatim()` for MathJax |
| `equation`, `equation*`, `align`, `align*`, `gather`, `gather*`, `eqnarray`, `eqnarray*` | many | handled (display-math passthrough as `\[...\]`) |
| `tikzpicture` | 69 (ch-09: 29; ch-10: 10; ch-11: 5; ch-07: 9; ch-13: 4; ch-12: 3; ch-06: 9) | handled (explicitly skipped, line 866-868) |
| `figure`, `figure*`, `wrapfigure`, `subfigure` | 0 | n/a (none in corpus) |
| `algorithm`, `algorithmic`, `proof`, `theorem`, `lemma`, `definition`, `corollary`, `proposition` | 0 | n/a (none in corpus) |
| `quote`, `quotation`, `abstract` | 0 | n/a |
| `description` | 2 (ch-06) | handled by generic fallback at parser line 874-883 (recurses on inner_nodelist) |
| `table`, `wraptable`, `minipage` | 2 (ch-06) | `table` in env-handler dispatch (line 858-860); `minipage` at line 861 |

**Key finding: there are zero source-level unhandled `\begin{...}` environments in the corpus that aren't already explicitly handled or explicitly skipped.** The TASK-005 catalog's "28 unhandled instances, ch-09 (22)" framing does not survive the corpus walk; the most plausible explanation for the 22-in-ch-09 figure is that it counted source-line occurrences of `\begin{tikzpicture}` (29 in ch-09; rough underestimate) which the parser already silently skips. The "leaks" the human saw in the screenshots are not from source-level unhandled envs.

The architect therefore could NOT confirm the existence of source-level unhandled-env bleed-through via static analysis. Whatever leaks the human observed in screenshots most plausibly originate from one of three other paths:

1. pylatexenc parsing failures inside complex contexts (e.g., `\begin{tikzpicture}[level distance=10mm, every node/.style={...}]` has nested braces inside the optional argument; pylatexenc may misparse this and emit `\begin/\end` as raw chars). On parse failure, the parser's catch-all fallbacks (`_render_tabular` line 466, callout body re-walker line 254-255 / 834-835, `parse_latex` outermost catch at line 957-963) emit raw escaped text that preserves `\begin{...}` and `\textbf{...}` literally.
2. The unknown-environment fallback at parser lines 285-295 (`_convert_inline_latex`) and 874-883 (`_nodes_to_html`) currently emits `inner_nodelist` recursively but does NOT consume the `\begin{X}` or `\end{X}` wrapper tokens — if pylatexenc registered the env at all, the wrapper tokens are consumed by the env-node abstraction, but if pylatexenc did NOT register them (parse failure), they appear as `LatexCharsNode` content inside the surrounding parent's nodelist and reach `_escape()` directly.
3. The `\renewcommand{\arraystretch}{1.2}`, `\noindent\resizebox{\textwidth}{!}{...}`, `\multicolumn{N}{c}{...}`, `\footnotesize` etc. macros that surround tables in the corpus (e.g., ch-10 line 1890-1894) — these may cause pylatexenc to drop content or misroute it through the unknown-macro branch (parser line 203-212), which emits `get_arg_html(0)` and discards the rest. The discarded "rest" may contain content that subsequently gets re-encountered as raw chars.

The architectural decision this ADR makes is therefore not the one TASK-008's task file forecast (per-env editorial commitments under Option 3 hybrid). The decision is: commit to a **generic consume-and-skip fallback shape** that is robust to all three possible leak paths, defer per-env editorial commitments until evidence justifies them, and pair this ADR with ADR-020 (defensive macro-stripping in raw-text fallback paths) which addresses Gap B at the actual leak site.

This decision is forced now because TASK-008's acceptance criteria require visible-leak elimination across the affected Chapters, and that requires committing to a fallback posture that does not leak wrapper tokens regardless of parse path.

## Decision

The parser's unknown-environment fallback (the `else` branch at `app/parser.py:874-883` in `_nodes_to_html` and at `app/parser.py:285-295` in `_convert_inline_latex`) is strengthened to a **generic consume-and-skip with structured-warning emission**. Concretely:

1. The fallback emits `<div class="unrecognized-env" data-env="X">{inner_html}</div>` (where `X` is the env name and `inner_html` is the recursive render of `node.nodelist.nodelist`). The wrapping `<div>` exists so that:
   - The inner content (paragraphs, math, inline formatting) renders normally — no editorial loss for content that is otherwise safe.
   - A single CSS rule in `app/static/lecture.css` (`.unrecognized-env { /* identity */ }`) gives the human a single styling and verification surface.
   - The `data-env` attribute makes the unhandled env type visible in a Playwright DOM assertion or in a future console-side log scraper.
2. The existing structured warning (parser line 286-290 / 876-880) is preserved, and the warning message is unchanged: `"Unknown LaTeX environment: %s — passing through content. ADR-003: unknown nodes are silently ignored with a warning."` The warn-per-node pattern (ADR-003) continues.
3. The `inner_html` path goes through the SAME walker (`_nodes_to_html` for body context, `_convert_inline_latex` for inline context). Recursion guarantees that any `\textbf{X}` inside an unknown env's body is processed by the existing inline handlers — the unknown-env wrapper does not bypass inline macro handling.
4. **No literal `\begin{X}` or `\end{X}` substring appears in the rendered HTML** for any env that pylatexenc registers as a `LatexEnvironmentNode`. (The corollary case where pylatexenc fails to register the env at all — emitting `\begin/\end` as raw chars — is addressed by ADR-020's defensive macro-stripping pass at the raw-text fallback sites.)

The default CSS rule in `app/static/lecture.css`:

```css
.unrecognized-env {
  /* identity wrapper — no visual treatment by default; reserved for
     future per-env editorial decisions if any unhandled env's content
     warrants distinguishing styling */
}
```

The empty rule is intentional. It exists as a hook for future per-env CSS without committing to any editorial intent now. Browsers render `<div class="unrecognized-env">` exactly like `<div>`.

### What this ADR explicitly does NOT decide

- **Per-environment editorial intent.** No env is promoted to an explicit handler in this ADR. The corpus walk found zero unhandled envs with non-zero corpus instances, so no editorial commitment is forced. If a future Chapter introduces a new env type whose content warrants distinguishing CSS or structural HTML (e.g., a future `\begin{algorithm}` block where a `<pre class="algorithm">` is more readable than a generic `<div>`), supersede this ADR's "no per-env handlers" stance with a focused per-env ADR.
- **The fix for the Gap B text-formatting-macro leak (`\textbf{`, `\textit{`, `\emph{`, `\textsc{` appearing as visible text).** Gap B's leak path is not from the unknown-env fallback; it is from the raw-text fallback paths (`_escape(raw)` calls at parser lines 254-255, 466, 834-835). ADR-020 governs that fix.
- **Reconfiguration of pylatexenc to register more envs as known with explicit argspecs.** Considered as Alternative B; deferred. The current corpus does not need it; the supersedure path is bounded.
- **Removal of the existing `figure`/`figure*`/`tikzpicture` skip branch (parser line 866-868).** Those are explicit-skip decisions; this ADR's generic fallback applies only to envs not in any explicit branch. The skip branch stays.

## Alternatives considered

**A. Option 3 hybrid — explicit handlers for top-frequency unhandled envs + generic fallback for the rest.**
The TASK-008 task file's forecast. Rejected because the corpus walk found zero unhandled envs with non-zero corpus instances. The candidate envs the task file named (`algorithm`, `algorithmic`, `proof`, `theorem`, `figure`) do not appear in the corpus at all. Adding explicit handlers for envs that have zero corpus uses would be speculative architecture — exactly the kind of decision the manifest's "drive consumption" framing argues against (architecture should serve the actual content, not anticipated content). If a future Chapter introduces one of these envs with editorial significance, supersede this ADR's "no per-env handlers" stance with a focused per-env ADR at that point.

**B. Reconfigure pylatexenc to register every corpus env (callouts, tikzpicture, etc.) with explicit argspecs in a custom `LatexContextDb`.**
Stronger structural guarantee — pylatexenc would consume optional args (`[Title]`, `[level distance=...]`) into `nodeargd` rather than leaking them into the body nodelist. Rejected for TASK-008 because:
- The current parser already works around this via raw-verbatim regex (callout title extraction, tabular spec extraction). The bug is not "pylatexenc didn't parse the env" — it is "the parse-failure fallback emits raw text."
- A custom context DB is a substantial surface change that touches every env handler, not just the unhandled-env fallback. ADR-003's commitment is to "extend pylatexenc with environment-specific handlers," not "rewrite the context DB."
- The supersedure path is intact: if a future failure mode actually requires structured-arg parsing for a custom env, supersede with a context-DB ADR at that point. Not forced now.

**C. Strip the unknown env entirely (drop both wrapper AND inner content).**
The simplest "no-leak" option. Reject the unknown env's content silently; emit nothing; log a warning. Rejected because:
- The corpus contains content that is structurally surrounded by macros pylatexenc may not parse fully (e.g., `\noindent\resizebox{...}{...}{ \begin{tabular}{...} ... \end{tabular} }`). If the outer `\resizebox{...}` causes pylatexenc to wrap the entire tabular in an "unknown" group, dropping the inner content would drop the whole table — a worse outcome than the current bug.
- "Visible failure, no fabrication" (manifest §6, broadly read) argues for surfacing what we DO know (the inner content) rather than discarding it silently. The chosen decision (recurse through inner content) honors this.

**D. Emit `<details><summary>Unrecognized environment: X</summary>{inner_html}</details>` instead of `<div>`.**
Surfaces the unhandled-env warning in the rendered page itself. Rejected because:
- The reader sees an unhelpful "Unrecognized environment" disclosure widget on every unhandled env — for content that may render perfectly well inside the wrapper, the disclosure adds noise without adding signal. The structured-warning log (existing ADR-003 pattern) is the correct surface for "here's what the parser couldn't fully classify."
- Manifest §3 (drive consumption) argues against in-page debugging artifacts that don't help the reader understand the content.

**E. In-place edit to ADR-003 to clarify the unknown-env fallback shape (no new ADR).**
The lighter-touch option. Rejected because:
- ADR-003's "warn-per-node, do not crash, do not fabricate" is a strategic commitment; this ADR's "wrap in `<div class="unrecognized-env" data-env="X">`" is a specific implementation contract within that strategy. The shape is large enough to warrant its own decision record.
- ADR-018 / ADR-017 / ADR-014 / ADR-012 / ADR-011 all follow the precedent of "specific implementation contract within ADR-003 → its own ADR." Maintaining that precedent.
- Supersedure chronology stays clean: future evidence that the wrapper element should change (`<div>` → `<section>` → `<aside>`) supersedes this ADR specifically rather than amending ADR-003.

## My recommendation vs the user's apparent preference

The user's apparent direction (TASK-008 task file, "Architectural decisions expected" section) is **Option 3 hybrid** with explicit handlers for `algorithm`, `algorithmic`, `proof`, `theorem`, `figure`. The architect disagrees with this direction based on the `/design`-time corpus walk and recommends **Option 2 (generic fallback only)**.

**The disagreement is substantive, not procedural.** The user's framing assumed the catalog's "28 unhandled instances, ch-09 (22)" identified a real list of unhandled envs to write per-env handlers for. The corpus walk shows that list is empty: every `\begin{X}` in the corpus is either explicitly handled or explicitly skipped. There is no env to promote to an explicit handler. Writing handlers for envs that don't exist in the corpus is speculative architecture and contradicts the manifest's "drive consumption" framing (architecture should serve actual content).

The architect respects the user's directional preference for Option 3 in that the supersedure path remains open: if a future Chapter introduces `\begin{algorithm}` (or any other env) and its content warrants distinguishing CSS, a focused per-env ADR can promote it to an explicit handler at that time. The architect's preference for Option 2 NOW is bounded to NOW.

If the human prefers to ratify Option 3 as the project's standing posture (so that future Chapters introducing new envs are auto-promoted to explicit handlers without a discussion), this ADR can be rejected and a different ADR can ratify Option 3 directly. The architect's argument against pre-committing to Option 3 is that it generates per-env editorial obligations the project has no evidence-based basis to make (the architect has never seen any of these envs and cannot anticipate the editorial intent).

**Architect also pushes back on the task file's framing of the leak source.** The TASK-008 task file says "Gap A — unhandled `\begin{<env>}` / `\end{<env>}` tokens leak through as literal text" and lists `algorithm`, `algorithmic`, `proof`, `theorem`, `figure` as candidates. The corpus walk does not support that leak source. The architect could not run the diagnostic test (no shell access in `/design` mode) but states clearly here: the leak the human observed in the TASK-005 screenshots is most plausibly from one of the three other paths enumerated in Context (pylatexenc parse failure on TikZ-style nested-brace optional args; unknown-env fallback content escapes; surrounding macros causing parse drift). ADR-020 addresses the most likely actual site (raw-text fallback paths emit `\textbf{...}` as escaped text). The combination of ADR-019 + ADR-020 should clear visible leaks regardless of which path was actually responsible. The `/implement` cycle's first step must be a diagnostic test that confirms the actual leak path before the implementer commits to the fix surface — see the new project_issue `design_docs/project_issues/task008-leak-path-empirical-confirmation.md`.

## Consequences

**Becomes possible:**

- Any future Chapter that introduces a new `\begin{X}` env (whether currently in the corpus or not) renders without leaking `\begin{X}` or `\end{X}` literal substrings, regardless of pylatexenc's argspec handling for X.
- A Playwright assertion of the form "no rendered chapter contains `\begin{` outside `<pre>/<code>` and outside `\[...\]` math zones" is a stable cross-corpus regression test.
- The structured warnings (`logger.warning("Unknown LaTeX environment: ...")`) continue to flag unhandled envs, giving the human a single log surface to triage future per-env editorial decisions from.
- The `<div class="unrecognized-env" data-env="X">` wrapper provides a single CSS hook for any future per-env styling without further parser changes.

**Becomes more expensive:**

- Adding per-env editorial intent later (the deferred Option 3 hybrid) requires a focused ADR per env — small cost (one ADR + one parser branch + one CSS rule each), but each is its own decision rather than batched.
- If a future Chapter introduces an env whose generic-fallback rendering is visually wrong (e.g., a `\begin{theorem}` body that looks confusingly similar to surrounding prose), the supersedure cost is one focused ADR.

**Becomes impossible (under this ADR):**

- A literal `\begin{X}` substring in the rendered HTML for any env that pylatexenc registers as a `LatexEnvironmentNode`. (For envs pylatexenc fails to parse as envs — emitting `\begin/\end` as raw chars — ADR-020 governs the defensive-stripping pass.)
- Adding a per-env explicit handler without a focused ADR. The "blanket Option 3 ratification" path is closed by this ADR; future per-env handlers each get their own ADR.

**Supersedure path:**

- If empirical evidence (post-`/implement` diagnostic, future Chapter content) shows that a specific env's generic fallback rendering is editorially wrong, supersede with a focused per-env ADR that adds an explicit handler. The `.unrecognized-env` CSS hook stays; only that env's parser branch diverges.
- If pylatexenc's behavior changes in a future major version (e.g., it starts registering more envs by default), the generic fallback's coverage shrinks naturally without requiring an ADR change.
- If the project later refactors toward a fully structured IR (per ADR-012 / ADR-017's "supersedure path" language), the unknown-env handling moves into the IR layer; the `data-env="X"` attribute survives as the IR's "uninterpreted env" marker.

## Manifest reading

Read as binding for this decision:

- **§3 Primary Objective ("drive consumption … via per-Chapter Lectures").** Bound the requirement: visible LaTeX-bleed in the rendered surface is an obstacle to consumption; the generic fallback eliminates the wrapper-token leak across all Chapters at once. Also bound the rejection of Option 3 hybrid: writing per-env handlers for envs that do not exist in the corpus does not advance consumption.
- **§5 Non-Goals: "No in-app authoring of lecture content."** Honored — the fix lives in `app/parser.py` and `app/static/lecture.css`. No source file is edited.
- **§6 Behaviors and Absolutes: "A Lecture has a single source"; "AI failures are visible" (broadly read as "visible failure, no fabrication").** Bound the warn-per-node continuation (the structured warning surfaces the unhandled env type for human triage) and the recursive-inner-content rendering (preserves what the parser DOES know rather than discarding it).
- **§7 Invariants.** Not directly touched; unhandled-env handling does not interact with M/O separability or the reinforcement loop.

No manifest entries flagged as architecture-in-disguise.

## Conformance check

- **MC-1 (No direct LLM/agent SDK use).** Not touched. No AI surface.
- **MC-2 (Quizzes scope to one Section).** Not touched.
- **MC-3 (Mandatory/Optional designation).** Not touched. Unhandled-env wrapping does not interact with designation.
- **MC-4 (AI work asynchronous).** Not touched.
- **MC-5 (AI failures surfaced).** Not touched.
- **MC-6 (Lecture source read-only).** *Honored.* The fix edits `app/parser.py` and `app/static/lecture.css`. No path under `content/latex/` is touched.
- **MC-7 (Single user).** Not touched.
- **MC-8..MC-10.** Not touched.

ADR-relationship checks:

- **ADR-003 (rendering pipeline).** Honored. This ADR operates within ADR-003's "warn-per-node, do not crash, do not fabricate" envelope. The structured warning continues; the recursion through inner content continues; only the wrapper element changes (was: emit `inner` directly into the parent flow; now: wrap `inner` in `<div class="unrecognized-env" data-env="X">`).
- **ADR-008 (CSS layering).** Honored. The new `.unrecognized-env` CSS rule lives in `app/static/lecture.css` (Lecture-body content styling).
- **ADR-010 (Playwright verification).** TASK-008 acceptance criteria require Playwright cross-corpus assertions; this ADR's decision is verified through the ADR-010 gate.
- **ADR-012 / ADR-018 (precedent: parser handler change + matching CSS rule).** Same shape; no conflict.
- **ADR-013 (split verification harness).** TASK-008 reuses the 12-Chapter parameterized screenshot harness from TASK-005 for cross-corpus re-verification.
- **ADR-015 (bug-class partition).** This ADR resolves a class-1 (LaTeX/parser content-fidelity) bug routed via the deferred-project_issue path — exactly the routing the human's gate-time amendment of ADR-015 envisioned for high-volume class-1 categories.
- **ADR-019 ↔ ADR-020 relationship.** ADR-019 governs the unknown-env fallback (env-level wrapper). ADR-020 governs the raw-text fallback (when pylatexenc fails to register the env at all and the raw verbatim is emitted via `_escape`). They are sibling ADRs in TASK-008 and are gated together.

## Project_issue resolution

`design_docs/project_issues/parser-fidelity-unhandled-environments-and-text-macros.md` is updated in this `/design` cycle to `Status: Resolved by ADR-019 (Gap A) and ADR-020 (Gap B) (Proposed; contingent on acceptance)` with a one-line resolution note. Per the project's resolution discipline, an issue resolved by Proposed ADRs carries the resolution pointer immediately; if either ADR is rejected at gate, the issue's status reverts to Open and is re-triaged in a follow-up `/design` cycle.

A new project_issue is opened: `design_docs/project_issues/task008-leak-path-empirical-confirmation.md` — captures the work the architect could not complete in `/design` (running the diagnostic test to confirm the actual leak path), to be performed as the first step of TASK-008's `/implement` cycle.
