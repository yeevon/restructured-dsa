# ADR-017: Tabular column-spec stripping — implementation contract for ADR-011 (balanced-brace consumption)

**Status:** `Accepted`
**Date:** 2026-05-09
**Task:** TASK-007
**Accepted:** 2026-05-09 (human gate; accepted as written — implements ADR-011's outcome contract via balanced-brace consumption; recorded in TASK-007 audit Run 003)
**Resolves:** `design_docs/project_issues/parser-fidelity-tabular-column-spec-residue.md`
**Supersedes:** none. **Implements** ADR-011 (Accepted) — does not change ADR-011's commitment; tightens the mechanism contract that the existing implementation does not satisfy.

## Context

ADR-011 (Accepted, TASK-004) commits the project to:

> "The parser's `_render_tabular` handler strips the column-specification argument from the rendered output entirely. Only data rows from the tabular body are rendered as HTML `<tr>` elements. The column spec does not appear as visible text in any rendered table."

The TASK-005 corpus-wide validation pass (orchestrator Run 008, recorded in `design_docs/audit/TASK-005-multi-chapter-rendering-validation.md`) surfaced **53 visible instances across Chapters 02 (6), 03 (30), and 04 (17)** where the column-spec textual content (`l`, `c`, `c`, `c`, `@`, `p3.4cm`, etc.) leaks into the first cell of the first rendered row of a `tabular`. Examples in the catalog: `lccc@\n\n<strong>Operation</strong>`, `p3.4cmp5cmp4.8cm@`. The `{}` empty groups inside the spec are stripped, but the surrounding spec characters survive.

Reading `app/parser.py:383`, the cause is mechanical:

```python
m = re.search(r'\\begin\{tabular\}\{([^}]*)\}(.*?)\\end\{tabular\}', raw, re.DOTALL)
```

The capture group `[^}]*` is non-greedy at the **first** `}` it encounters. For a tabular argument like `{@{}lccc@{}}`, the **first** `}` inside the argument terminates `[^}]*` after only `@{`, so the regex captures `col_spec="@{"` and the body match begins with `}lccc@{}}<actual rows>`. The handler then passes that string into the row splitter, which yields a first cell containing `lccc@` plus the actual content. The bug is a brace-balance bug, not a strategy bug — the regex assumes the argument has no nested `{}`, which is false for `@{}`, `p{width}`, `>{}`, `<{}`, and any future spec feature that brings braces.

ADR-011 itself does not specify the mechanism (regex vs. pylatexenc structured access vs. pre-parse). It commits to the outcome ("strip entirely") and to the warn-per-node pattern for complex features. The implementation gap is therefore an **implementation-contract gap inside ADR-011's outcome commitment** — not a conflict with ADR-011, and not a question the existing ADR resolved.

The TASK-007 task file ("Architectural concerns I want to raise") flagged this as a `/design`-time choice: codify the mechanism in a separate ADR (clearer audit trail, the precedent for per-fix-one-ADR), or append a Resolution-note clarification to ADR-011 (less paperwork). The architect at `/design` picks the separate-ADR shape — see "My recommendation vs the user's apparent preference."

This decision is forced now because TASK-007's acceptance criteria require zero column-spec residue across ch-02/03/04 first cells, and that requires either committing to a tighter mechanism (this ADR) or amending ADR-011 in place (rejected, see Alternatives).

## Decision

The tabular column-spec stripping uses a **balanced-brace consumption mechanism** that walks from the opening `{` immediately after `\begin{tabular}` and consumes characters until it finds the matching `}` at depth zero. Nested `{}` pairs inside the spec — `@{}`, `p{3.4cm}`, `>{\bfseries}`, `<{...}` — are consumed as part of the spec, not treated as the spec's terminator.

Concretely, `_render_tabular` in `app/parser.py` replaces the current single-regex extraction:

```python
# CURRENT (buggy):
m = re.search(r'\\begin\{tabular\}\{([^}]*)\}(.*?)\\end\{tabular\}', raw, re.DOTALL)
```

with a two-step extraction that:

1. Locates the first `\begin{tabular}{` literal in `raw`.
2. From the position immediately after the opening `{`, scans character-by-character keeping a brace-depth counter (start at 1; `+1` on `{`, `-1` on `}`; the spec terminates when the counter returns to 0).
3. Captures the spec substring (between the opening `{` and the matching `}`) and the body substring (between that matching `}` and the next `\end{tabular}`).
4. Passes the spec substring to `_warn_complex_col_spec` (existing helper, ADR-011's warn-per-node) and discards it from rendered output.
5. Passes the body substring to the existing row splitter.

The implementer is free to express the balanced-brace scan as a small Python loop, a regex with a recursive-pattern feature, or any other mechanism that produces the balanced-brace semantic. The architectural commitment is on the **semantic** ("the spec is the entire balanced-brace argument starting at `\begin{tabular}{`"), not on the syntactic shape of the matcher.

The **rendered output contract** matches ADR-011 exactly: zero column-spec characters (`l`, `c`, `r`, `p`, digits, units, `@`, `|`, `>`, `<`, braces) appear in any rendered cell. The body substring passed to the row splitter contains only the tabular's data rows.

The **warn-per-node contract** (ADR-011) is unchanged: the existing `_warn_complex_col_spec(col_spec, chapter_id)` helper continues to fire warnings for `|`, `p{`, `@{`, `>{`, `<{`. Because this ADR's mechanism captures the entire spec (including nested-brace content), the warnings now fire on the full spec text, not on the truncated `[^}]*` slice.

### What this ADR does *not* decide

- **Per-column alignment preservation.** ADR-011's Alternative B (preserve alignment as CSS classes per column) remains deferred. This ADR only commits to stripping the spec correctly; the spec is still discarded after the warn pass.
- **Switching to pylatexenc-structured argument parsing.** Considered as Alternative B below; deferred. The current corpus does not need it; if a future Chapter introduces a spec feature the balanced-brace scan cannot disambiguate, supersede.
- **Failure-mode behavior on truly malformed tabular** (e.g., `\begin{tabular}{lcc` with no closing brace). The architectural commitment is that the parser logs a structured warning per ADR-003 and either falls back to rendering the verbatim text inside a single-cell row (existing fallback at `_render_tabular` line 385) or skips the environment. Implementer chooses the fallback shape; no new ADR required if it stays inside ADR-003's "warn-per-node, do not crash, do not fabricate" envelope.

## Alternatives considered

**A. Append a clarifying Resolution-note to ADR-011 instead of writing a new ADR.**
The lighter-touch option. ADR-011's Decision section would gain a paragraph specifying the balanced-brace mechanism; no new ADR file. Rejected because:
- ADR-011 is **Accepted** and the project's discipline is to supersede or extend Accepted ADRs via new ADRs, not in-place edits. In-place edits to Accepted ADRs erase the audit trail of why the mechanism contract changed.
- The mechanism choice (balanced-brace scan vs. pylatexenc-structured-access vs. pre-strip regex) is itself a real decision with material alternatives — exactly the shape an ADR exists to record.
- The TASK-007 task file's "Architectural concerns" section recommends the separate-ADR shape with a weak preference; the architect concurs.
- The empirical evidence (53 visible defects across 3 Chapters) is itself the new context that justifies a fresh decision — ADR-011 was written without that evidence, and "ADR-011 plus a Resolution note" loses the chronology.

**B. Switch to pylatexenc-structured argument parsing for tabular.**
Register `tabular` as a known environment with a custom argspec (`{spec}{body}` — pylatexenc's `latex_context.add_context_category(...)`); pylatexenc would then parse the spec as a `LatexGroupNode` whose `nodelist` we can walk structurally. Rejected for TASK-007 because:
- Registering `tabular` under a custom context is a larger surface change than the bug warrants. The current implementation reads tabular content from `latex_verbatim()` and uses regex to slice it — this ADR fixes the slicing, not the strategy.
- pylatexenc's `tabular` parsing for the spec argument behaves the same as for any group node: the structural representation is "characters inside braces"; the **interpretation** of those characters as column-spec features is the project's responsibility either way. We still need a per-feature warn pass; switching to structured access does not get us free interpretation.
- ADR-003 commits to pylatexenc as the parser; structured-access for tabular is a refinement, not a strategy change. If a future Chapter forces the refinement (e.g., a tabular spec with content the balanced-brace scan can't handle), supersede this ADR with a structured-access ADR.
- Bounded mitigation: this ADR's balanced-brace scan handles every spec feature in the current corpus (`@{}`, `p{cm}`, `|`, `l`, `c`, `r`); empirically there is no observed case it would miss.

**C. Pre-strip the spec from `raw` source-text before pylatexenc walks the document.**
A regex pass like `re.sub(r'\\begin\{tabular\}\{[^}]*?\}', r'\\begin{tabular}{}', source)` applied before parsing. Rejected because:
- The `[^}]*` problem is exactly the bug we are fixing; the same naive regex breaks the same way at the pre-strip level (nested `@{}` still terminates the match early).
- A pre-strip pass with balanced-brace logic is functionally identical to doing the balanced-brace scan inside `_render_tabular` — but the pre-strip version corrupts the source-text that subsequent error reporting refers to (line numbers, verbatim quoting). The in-handler scan keeps all source-text fidelity.
- Pre-strip operates outside the parser pipeline (runs before pylatexenc), which contradicts ADR-003's "walk the LaTeX node tree in Python" commitment to keeping LaTeX understanding inside the node-walker layer.

**D. Strip the spec by post-processing the rendered HTML to remove leading-cell-residue patterns.**
Run a regex against the rendered HTML to remove patterns like `^lccc@`, `^p\d+\.\d+cm` from each first cell. Rejected because:
- It's a textual post-fix on output, not a fix at the parsing layer where the bug lives. The same residue would slip in via any future spec feature whose pattern wasn't anticipated by the post-fix regex.
- It conflates two unrelated cell contents (legitimate first-cell text starting with the same letters vs. spec residue) — false positives are possible.
- It violates the project's "fix at the layer where the bug lives" discipline.

## My recommendation vs the user's apparent preference

The user's explicit direction (TASK-007 task file, "Architectural concerns I want to raise" section) is a **weak preference** for the separate-ADR shape over the in-place Resolution-note edit, with the explicit note "the architect at `/design` can override." The architect concurs with the weak preference for the separate-ADR shape and writes ADR-017 here.

On the mechanism choice (Options 1/2/3 in `parser-fidelity-tabular-column-spec-residue.md`), the user has not signaled a preference among the three options. The project_issue identifies Option 1 (balanced-brace strip) as bounded; Option 2 (pylatexenc structured access) as heavier and ADR-003-aligned; Option 3 (pre-parse regex) as brittle. The architect picks **Option 1**, scoped tighter than the project_issue described it: the balanced-brace scan is the architectural commitment, not "any greedy regex."

If the human's reading of the task is that an in-place clarification of ADR-011 is preferable, the supersedure path is straightforward: this ADR is rejected at gate, and the human edits ADR-011 directly with the same mechanism contract. The architect's preference for separate-ADR is procedural, not substantive — the substantive decision (balanced-brace scan) is the same either way.

Aligned with user direction on substance (Option 1) and on the weakly-stated preference for separate-ADR shape.

## Consequences

**Becomes possible:**

- Every `\begin{tabular}{...}` in the corpus, including the dominant `@{}...@{}` and `p{width}` idioms, renders without spec-residue text in any cell. The 53 visible instances across ch-02/03/04 disappear.
- The warn-per-node pattern (ADR-011) operates on the full spec text rather than the truncated `[^}]*` slice — `|`, `p{`, `@{`, `>{`, `<{` warnings now fire reliably for every occurrence in the corpus.
- A Playwright assertion of the form "no rendered cell contains `lccc@` / `p3.4cm` / etc." is a stable regression test.
- Future tabular spec features that bring nested `{}` (e.g., `>{\bfseries}`, `<{\itshape}`, hypothetical `m{width}`) are stripped correctly without a new mechanism change — only the warn list extends.

**Becomes more expensive:**

- Adding **per-column alignment preservation** later (ADR-011 Alternative B) still requires a separate ADR and parser changes (column-index tracking, multicolumn awareness). This ADR does not foreclose that path; it only ensures the spec is consumed so alignment metadata could be extracted from it cleanly.
- If a future spec feature introduces escaped braces (`\{`, `\}`) inside the spec, the balanced-brace counter overcounts (treats `\{` as opening). Mitigation: extend the scan to skip backslash-escaped braces. No corpus instance currently exists.

**Becomes impossible (under this ADR):**

- A column-spec character appearing as visible text in a rendered cell. The balanced-brace scan removes the entire spec.
- Reverting to the `[^}]*` mechanism without a supersedure ADR.

**Supersedure path:**

- If the balanced-brace scan proves insufficient (a Chapter introduces a spec the scan can't disambiguate, or the project decides to preserve alignment as CSS), supersede with an ADR that adopts pylatexenc-structured argument parsing for `tabular` (Alternative B above). The supersedure changes the **mechanism**, not the **outcome contract** (zero spec residue) — that contract was set by ADR-011 and is preserved by the supersedure.
- If the project later refactors toward a fully structured IR (per the ADR-012 "supersedure path" language), this ADR's regex-on-verbatim approach is replaced by structural walks of the IR's table node. The outcome contract again survives.

## Manifest reading

Read as binding for this decision:

- **§3 Primary Objective ("drive consumption … via per-Chapter Lectures").** Bound the requirement: 53 visible spec-residue defects across 3 Chapters degrade consumption; this ADR closes them.
- **§5 Non-Goals: "No in-app authoring of lecture content."** Honored — the fix lives in `app/parser.py`, not in `content/latex/`. No source file is edited.
- **§6 Behaviors and Absolutes: "A Lecture has a single source"; "AI failures are visible" (read more broadly as the project's "visible failure, no fabrication" principle).** Bound the warn-per-node pattern: complex spec features continue to log structured warnings; the implementation does not silently misrepresent uninterpreted content.
- **§7 Invariants.** Not directly touched; tabular rendering does not interact with M/O separability or the reinforcement loop.

No manifest entries flagged as architecture-in-disguise.

## Conformance check

- **MC-1 (No direct LLM/agent SDK use).** Not touched. No AI surface.
- **MC-2 (Quizzes scope to one Section).** Not touched.
- **MC-3 (Mandatory/Optional designation).** Not touched. Tabular rendering does not interact with designation.
- **MC-4 (AI work asynchronous).** Not touched.
- **MC-5 (AI failures surfaced).** Not touched.
- **MC-6 (Lecture source read-only).** *Honored.* The fix edits `app/parser.py`'s `_render_tabular` handler in memory; no path under `content/latex/` is touched by code or by editorial intent.
- **MC-7 (Single user).** Not touched.
- **MC-8..MC-10.** Not touched.

ADR-relationship checks:

- **ADR-003 (rendering pipeline).** Honored. This ADR operates within ADR-003's "extend environment-specific handlers" clause. The `_render_tabular` handler is being corrected, not replaced. The warn-per-node pattern is unchanged.
- **ADR-011 (tabular column-spec handling).** Implements ADR-011's outcome contract ("strip entirely") with a tighter mechanism contract. ADR-011 stays Accepted; ADR-017 layers on top.
- **ADR-008 (CSS layering).** Not touched (no CSS changes for the tabular fix).
- **ADR-010 (Playwright verification).** TASK-007 acceptance criteria require Playwright tests verifying the fix. This ADR's decision is verified through the ADR-010 gate.
- **ADR-013 (split verification harness).** TASK-007 reuses the 12-Chapter parameterized screenshot harness from TASK-005 for cross-corpus re-verification.

## Project_issue resolution

`design_docs/project_issues/parser-fidelity-tabular-column-spec-residue.md` is updated in this `/design` cycle to `Status: Resolved by ADR-017 (Proposed; contingent on acceptance)` with a one-line resolution note. Per the project's resolution discipline (TASK-005's `/design` precedent for ADR-014), an issue resolved by a `Proposed` ADR carries the resolution pointer immediately; if ADR-017 is rejected at gate, the project_issue's status reverts to Open and is re-triaged in a follow-up `/design` cycle.
