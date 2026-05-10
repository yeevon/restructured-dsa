# Unhandled `\begin{...}` environments and text-formatting macros bleed through

**Status:** Resolved by ADR-019 (Gap A) and ADR-020 (Gap B) (both Accepted 2026-05-10)
**Resolution note (2026-05-10, TASK-008 architect Mode 2):** Architect's `/design`-time corpus walk found zero source-level unhandled `\begin{...}` envs in the corpus (the TASK-005 catalog's "28 unhandled, ch-09 (22)" framing did not survive inspection). ADR-019 commits to a generic `<div class="unrecognized-env" data-env="X">` wrapper for the unknown-env dispatch (Gap A); ADR-020 commits to a defensive macro-stripping pass at every `_escape(raw)` parse-failure fallback site (Gap B — the most likely actual leak site for the 99 catalogued macro-token leaks). The empirical confirmation work the architect could not complete in `/design` (running a diagnostic test) is captured in the new project_issue `task008-leak-path-empirical-confirmation.md` and is the first step of `/implement TASK-008`.
**Surfaced:** 2026-05-09 (TASK-005 human screenshot review; orchestrator Run 008 corpus-wide categorization)
**Decide when:** as part of TASK-007 candidate. Medium-to-high visible-bug surface; concentrated in specific Chapters but covers two related parser-handler gaps.

## Question

Two related parser-fidelity gaps surfaced at corpus scale during TASK-005's validation pass:

**Gap A — `\begin{...}` / `\end{...}` of unhandled environments leak through as literal text.** The parser has handlers for the five callout environments (per ADR-012) and for `tabular`, `lstlisting`, `itemize`, `enumerate`, etc. (per ADR-003). Other LaTeX environments — apparently `algorithm`, `algorithmic`, `proof`, `theorem`, `figure`, or similar — are not handled, and the literal `\begin{<env>}` and `\end{<env>}` tokens render in the page body.

**Corpus-wide count:** ~28 instances. ch-09 (22) is the dominant Chapter; ch-02 (2), ch-03 (2), ch-13 (2) also affected.

**Gap B — text-formatting macros `\textbf` / `\textit` / `\emph` / `\textsc` / `\texttt` (the no-arg form) leak through as `\textbf{`, `\textit{`, etc.** Either the parser has no handler for these macros, or the handlers do not strip the macro wrapper before emitting the inner content. Either way, the rendered HTML contains the literal macro tokens.

**Corpus-wide count:** ~99 instances. ch-10 (60) is the dominant Chapter; ch-13 (23), ch-04 (13), ch-02 (2), ch-12 (1) also affected.

These two gaps are filed under one project_issue because (a) both are parser-handler gaps in the same component, (b) both are class-1 LaTeX/parser content-fidelity bugs per ADR-015's partition, and (c) the architect is likely to address them with related parser-handler additions. The follow-up TASK-007 architect can split into separate ADRs or address with one umbrella decision.

## Options known

- **Option 1: Add explicit handlers for each leaked environment / macro.** Walk the corpus; identify every leaked `\begin{X}` and `\<macro>{...}`; add a parser-handler per node type. Bounded but requires per-environment editorial decisions (e.g., should `algorithm` render as `<pre>` or `<div class="algorithm">`?).
- **Option 2: Add a generic "unknown-environment / unknown-macro" fallback handler.** Any unrecognized environment renders its body content as a `<div class="unrecognized-env" data-env="X">...</div>`; any unrecognized text-formatting macro emits its inner text without the macro wrapper. Pylatexenc's warn-per-node pattern (per ADR-003) logs the encounter for follow-up. Less editorial precision but immediately silences the visible-LaTeX bleed.
- **Option 3: Hybrid — specific handlers for high-frequency cases, generic fallback for the rest.** Most pragmatic. The TASK-007 architect picks the per-Chapter editorial intent for the top-3 most-frequent leaks and falls back generically for the rest.

## Constraints

- ADR-003 (Accepted) commits to pylatexenc + warn-per-node. New handlers must stay inside that strategy.
- Manifest §3 (drive consumption): unhandled LaTeX in body text degrades the consumption surface.
- ADR-008 (CSS layering): any new CSS classes belong in `lecture.css` (Lecture-body styling).
- For each environment / macro, the architect must decide editorial intent (e.g., is `algorithm` a `<pre>`? a `<figure>`? a `<div>`?).

## Why this is filed as a project_issue

Same reason as the related TASK-005 parser-fidelity issues: ADR-015 amended fold-in is the wrong scale tool for this volume. Per the human's gate decision (orchestrator Run 008), the category ships as a project_issue and the follow-up parser-fidelity task addresses it.

## Resolution

When resolved, mark this issue `Resolved by ADR-NNN` (or by multiple ADRs if the TASK-007 architect splits the two gaps).
