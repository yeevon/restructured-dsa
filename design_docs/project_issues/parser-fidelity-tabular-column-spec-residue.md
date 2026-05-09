# Tabular column-spec residue leaks into first table cell (ADR-011 implementation gap)

**Status:** Open
**Surfaced:** 2026-05-09 (TASK-005 human screenshot review; orchestrator Run 008 corpus-wide categorization)
**Decide when:** as part of the focused parser-fidelity follow-up task (TASK-007 candidate). High visible-bug surface; affects every Chapter that uses `\begin{tabular}{@{}...@{}}` in source.

## Question

ADR-011 (Accepted) commits to: "strip column spec from rendered output entirely (only data rows render); log a structured warning per ADR-003's warn-per-node pattern for complex/uninterpreted spec features (vertical bars, `p{width}`, `@{...}`). Simple alignment letters (`l`, `c`, `r`) are stripped without warning."

The current implementation does not honor that commitment. For source `\begin{tabular}{@{}lccc@{}}`, the rendered first cell of the first row contains `lccc@\n\n<strong>Operation</strong>` — the column-spec textual content (`l`, `c`, `c`, `c`, `@`) leaks in front of the actual cell content. For `\begin{tabular}{@{}p{3.4cm}p{5cm}p{4.8cm}@{}}`, the rendered first cell starts with `p3.4cmp5cmp4.8cm@`. The `{}` characters are stripped but the rest survives.

**Corpus-wide count:** ~53 distinct visible instances across Chapters 02 (6), 03 (30), and 04 (17). All Chapters that use the `@{}...@{}` idiom are affected.

## Options known

- **Option 1: Make the column-spec strip greedy per ADR-011.** Walk the parser handler for `tabular`; ensure the entire spec argument (everything between the first `{` and its matching `}` after `\begin{tabular}`) is removed from the rendered cell text — including content that survives current stripping (`@`, alignment letters, `p{width}`). The `{}` empty groups inside the spec must be handled before the outer `{}` strip. Bounded fix; one parser handler change.
- **Option 2: Switch to pylatexenc's column-spec parser.** If pylatexenc exposes structured access to the tabular argument, use it instead of regex-stripping. Heavier; aligns with ADR-003's "use pylatexenc node-walker." May obviate Option 1 entirely.
- **Option 3: Pre-strip column-spec from source-text before pylatexenc runs.** Regex-replace `\\begin{tabular}{[^}]*}` with `\\begin{tabular}{}` before parsing. Brittle (nested braces in `p{width}` would break the regex); not recommended.

## Constraints

- ADR-011 is Accepted and binding. The implementation must align with the ADR; if Option 1 is insufficient, Option 2 is the supersedure path.
- ADR-003 commits to pylatexenc as the parser; any column-spec handling stays inside that strategy.
- Manifest §6 ("visible failures"): the rendered surface must not silently misrepresent source content. Tabular cells must contain only the data rows.
- The pre-existing project_issue `latex-tabular-column-spec-passthrough.md` is marked "Resolved by ADR-011 (Accepted)" — but the implementation does not satisfy the ADR. This issue is the implementation-gap follow-up.

## Why this is filed as a project_issue

ADR-015 amended bug-class partition routes class-1 LaTeX/parser content-fidelity bugs to in-scope fold-in under new Proposed ADRs. The TASK-005 validation pass surfaced this category at corpus scale (~53 instances across 3 Chapters); folding under TASK-005 would inflate the task far beyond its session boundary. Per the human's gate decision (orchestrator Run 008), the parser-fidelity categories ship as project_issues and a focused follow-up task (TASK-007 candidate) bundles them.

## Resolution

When resolved, mark this issue `Resolved by ADR-NNN`.
