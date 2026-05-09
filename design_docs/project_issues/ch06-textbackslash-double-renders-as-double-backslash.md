# `\textbackslash\textbackslash` in ch-06 renders as `\\` instead of `\ \`

**Status:** Open
**Surfaced:** 2026-05-09 (TASK-005 implementer Run 006 adjacent finding; orchestrator Run 007 verify-first routing per amended ADR-015)
**Decide when:** before the next focused parser-fidelity task, or before any task that adds new `\textbackslash` usage to the corpus, whichever comes first. Defensible to defer to a focused fidelity task at any time.

## Question

In `content/latex/ch-06-trees.tex`, two adjacent `\textbackslash` macros in a `texttt`/code context render in the Lecture page's HTML body as the two-character substring `\\` instead of `\ \` (one backslash, one space, one backslash, or any visually-separated pair). The rendered surface conflates the two backslash glyphs into what reads as a single LaTeX-style `\\` linebreak token, which is editorially distinct from "two backslash characters."

This was first observed by the TASK-005 implementer (Run 006) during the multi-chapter Playwright validation pass. It was originally framed by the implementer as "Relevant only to PUSHBACK-1 resolution" — i.e., the bug was masking inside a whole-body `\\` check that was overconstrained vs ADR-014's actual title-only commitment. After the orchestrator scoped that test to title surfaces only (Run 007 PUSHBACK-1 resolution), the ch-06 body-content defect is no longer caught by any test. It remains a real rendering defect that is currently invisible to the test suite.

## Options known

- **Option 1: Insert a zero-width or actual space between adjacent `\textbackslash` outputs in the parser.** Simplest. The parser handler for `\textbackslash` can emit `\&#x200B;` (zero-width space) or `\ ` (regular space + backslash) when the next sibling node is also a `\textbackslash`, so the rendered HTML preserves visual separation. Trade-off: the zero-width approach preserves character count for code-block widths; the visible-space approach is simpler but adds a visible character.

- **Option 2: Render `\textbackslash` in a `<span>` wrapper** (e.g., `<span class="latex-backslash">\</span>`). Two adjacent spans naturally render with their own glyph boxes; CSS controls separation. More DOM weight per backslash; but per-character control is the cleanest path if `\textbackslash` is used heavily.

- **Option 3: Use a different LaTeX source representation in ch-06.** Replace adjacent `\textbackslash` with `\textbackslash{}\textbackslash` or `\textbackslash{}~\textbackslash`. Trade-off: editing source contradicts manifest §5 ("no in-app authoring") and shifts the fix burden to the corpus author, not the parser. Forbidden direction unless the source itself is wrong (it isn't — `\textbackslash\textbackslash` is valid LaTeX that the parser should handle).

- **Option 4: Defer until a Chapter introduces a third occurrence or the human surfaces it during a screenshot review.** Acceptable if the visible-bug surface area stays low. Currently affects one Chapter (ch-06).

## Constraints

- Manifest §6 ("visible failures"): the rendered surface should not silently misrepresent source content. Adjacent `\textbackslash` in source = adjacent backslash glyphs in render.
- ADR-003 (rendering pipeline, Accepted): the parser uses pylatexenc and may extend with environment-specific or macro-specific handlers. A `\textbackslash` handler change is well within ADR-003's strategy.
- ADR-015 (multi-chapter validation pass triage discipline, Accepted with amendment): class-1 LaTeX/parser content-fidelity bugs surfaced during a validation pass route to in-scope fold-in. This bug surfaced AFTER TASK-005's verify gate was met (human chose verify-first routing per the bug-class partition's amendment process), so it is filed for follow-up rather than blocking TASK-005 ship.
- No current test catches this defect. A regression test added with the fix should assert that rendering `ch-06`'s relevant `texttt` block produces visually-separated backslash glyphs (or, equivalently, that the rendered HTML for adjacent `\textbackslash` source contains a separator character or wrapping element between the two `\` glyphs).

## Why this is filed as a project_issue

This is a class-1 LaTeX/parser content-fidelity bug per ADR-015's amended bug-class partition. ADR-015's default routing is "fold in-scope of the validation pass under a new Proposed ADR." The orchestrator's Run 007 verify-first routing exception applies only because the defect surfaced after TASK-005's verify gate was met and the human explicitly authorized verify-first routing for it. The architect's `/next` cycle should pick this up as a focused follow-up task; the resolution will be a Proposed ADR (likely Option 1 or Option 2 above) and a small parser-handler change with a regression test.

## Resolution

When resolved, mark this issue `Resolved by ADR-NNN`.
