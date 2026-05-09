# Body `\\` linebreak passthrough and `\[...\]` display-math handling

**Status:** Open
**Surfaced:** 2026-05-09 (TASK-005 human screenshot review; orchestrator Run 008 corpus-wide categorization)
**Decide when:** as part of TASK-007 candidate. Medium visible-bug surface; bundles two related "delimiter-passthrough" gaps.

## Question

Two delimiter-related parser-fidelity gaps surfaced during TASK-005's validation pass:

**Gap A — `\\` linebreak passes through in BODY text.** ADR-014 (Accepted) commits to stripping `\\` only in `extract_title_from_latex()` (i.e., the title-extraction path). It does not commit to stripping `\\` in the rendered Lecture body. The validation pass surfaced literal `\\` substrings in body content of every Chapter — particularly inside callouts and tabular cells where the source uses `\\` as a row separator or line break. Whether this is a bug depends on context:

- Inside `tabular`: `\\` is the row separator and the parser should consume it (split rows). Whether the parser is doing this correctly needs verification.
- Inside `cases`, `array`, `matrix` math environments: `\\` is the row separator inside math; MathJax handles it correctly. Not a bug.
- Inside `\texttt{}` ASCII-art callouts: `\\` may be a literal author intent (`\\ ` = backslash + space) or an editorial linebreak. Needs case-by-case decision.
- Inside ordinary paragraph text: `\\` is almost certainly editorial linebreak; should render as `<br>` or be stripped.

**Corpus-wide count:** ~611 raw matches via the broad regex (high false-positive rate from `//` in URLs and from `\\` inside math environments where MathJax handles correctly). Real body-context defects are an unknown subset; the TASK-007 architect should sample and triage.

**Gap B — `\[...\]` display-math literal in HTML body.** The MathJax v3 config in `app/templates/base.html.j2` declares `displayMath: [['\\[', '\\]']]`, which means MathJax v3 should process `\[...\]` as display math. The corpus contains ~55 `\[...\]` blocks (ch-09: 24 dominant). They appear literally in the raw HTML response (expected, pre-MathJax); whether MathJax actually renders them on the loaded page needs browser-side verification. If MathJax is failing on display math, this is a real defect; if MathJax is rendering, this is a false alarm.

These two gaps are filed under one project_issue because both are delimiter-handling questions and the TASK-007 architect is likely to address them in a single audit pass.

## Options known

**For Gap A:**
- **Option A1: Strip `\\` from body text uniformly outside of math environments.** Aligns with the rail/header treatment (ADR-014). Risk: may discard editorially-meaningful linebreaks.
- **Option A2: Render `\\` in body paragraphs as `<br>`; strip elsewhere.** More editorially faithful. Requires per-context detection.
- **Option A3: Investigate sample sites and decide per category.** TASK-007 architect drives.

**For Gap B:**
- **Option B1: Verify MathJax actually renders `\[...\]` in a live browser session against the validation harness; if yes, close as not-a-bug.** Required first step.
- **Option B2: If MathJax does not render, change the displayMath delimiters or the parser output.** Architectural decision deferred until B1's verification result is known.

## Constraints

- ADR-014 is binding for title extraction; this issue does not contradict ADR-014, only extends the strip question to body context.
- ADR-003 commits to pylatexenc + warn-per-node; both gaps stay inside that strategy.
- Manifest §3 (drive consumption): editorially-faithful rendering matters; both gaps degrade reading quality if real.

## Why this is filed as a project_issue

Same reason as the other TASK-005 parser-fidelity issues. Per the human's gate decision (orchestrator Run 008), filed for follow-up TASK-007.

## Resolution

When resolved, mark this issue `Resolved by ADR-NNN`. Likely two separate ADRs — one per gap — if the architect chooses to split.
