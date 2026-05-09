# TASK-004: Fix parser fidelity — strip tabular column specs and render callout titles

**Inputs read:**
- Manifest: ss3 (drive consumption — broken tables and missing callout titles degrade every chapter's reading surface), ss5 (no in-app authoring; read-only source), ss6 (visible failures, single source, M/O honored), ss8 (Chapter, Section, Lecture glossary)
- architecture.md: Accepted ADRs 001-008, 010. ADR-003 (rendering pipeline) is the directly touched ADR — it owns the pylatexenc parser strategy, the IR, and the Jinja2 template contract
- ADR-003: parser uses pylatexenc node-walker; custom environment handlers for callout environments and lstlisting; warn-per-node on unrecognized nodes; no fabrication
- ADR-010: Playwright verification mechanism — new Playwright tests required for visual ACs; existing test boundary (DOM-content in Playwright, non-DOM in pytest)
- ADR-008: lecture.css already has `.callout-*` palette rules; callout-title CSS would be a small addition to lecture.css (content-body styling, not page chrome)
- Project issues forced: `latex-tabular-column-spec-passthrough.md` (Open), `latex-callout-title-arg-passthrough.md` (Open)
- Conformance rules touched: MC-6 (read-only — trivially preserved; parser changes don't write to source), MC-3 (M/O — not touched), ADR-010 verification gate

## What and why

The LaTeX parser currently has two fidelity bugs that affect every chapter in the corpus: (1) `\begin{tabular}{lll}` leaks the column-specification argument (`lll`) into the first rendered table row as visible text, and (2) callout environments like `\begin{ideabox}[Chapter map]` pass the optional `[Title]` argument through as bracketed inline text instead of rendering it as a callout header. Both bugs were surfaced during TASK-003's Playwright screenshot review and filed as open project issues. Fixing them advances the primary objective (manifest ss3) by making every table and every titled callout in the corpus render correctly — a prerequisite for the multi-chapter validation pass that follows.

## Acceptance criteria

- [ ] Given a Chapter source containing `\begin{tabular}{lll}`, when the Lecture page renders, then the column-specification string (`lll`) does not appear as visible text in any table row — only data rows from the tabular body are rendered.
- [ ] Given a Chapter source containing `\begin{tabular}{l|c|r}` or other complex column specs (`@{...}`, `p{...}`), when the Lecture page renders, then the column spec does not appear as visible text; the parser logs a structured warning per ADR-003's warn-per-node pattern for any spec feature it does not interpret (e.g., `|` separators, `p{width}`).
- [ ] Given a callout environment with an optional title argument (e.g., `\begin{ideabox}[Chapter map]`), when the Lecture page renders, then the title text ("Chapter map") appears as a visually distinct header element at the top of the callout body — not as bracketed inline text.
- [ ] Given a callout environment with no optional title argument (e.g., `\begin{ideabox}`), when the Lecture page renders, then no title element is emitted — the callout body renders as before.
- [ ] Given all five callout environments (`ideabox`, `defnbox`, `notebox`, `warnbox`, `examplebox`), when any of them carries an optional `[Title]` argument, then the title rendering is consistent across all five — same structural element, same CSS class.
- [ ] Given the existing TASK-001 and TASK-003 Playwright tests, when the full test suite runs (`python3 -m pytest tests/`), then all existing tests pass — no regressions.
- [ ] Given the new fidelity fixes, when Playwright tests run, then at least one test per fix verifies the correct rendering (tabular: no column spec in rendered rows; callout: title element present and visible when `[Title]` supplied).
- [ ] Given the staged diff, when manifest-conformance runs, then MC-6 (no writes to `content/latex/`) PASS.

## Architectural decisions expected

- **ADR-011: Tabular column spec handling.** Strip column spec from rendered output; log structured warning per ADR-003's warn-per-node pattern for complex/uninterpreted spec features (vertical bars, `p{width}`, `@{...}`). Simple alignment letters (`l`, `c`, `r`) stripped without warning. Resolves `latex-tabular-column-spec-passthrough.md`. Status: Proposed (awaiting human acceptance).
- **ADR-012: Callout title rendering.** Parser handler extracts optional `[Title]` argument and emits `<div class="callout-title">Title</div>` as first child inside callout div; `.callout-title` CSS rule in `lecture.css` styles it; consistent across all five callout environments; both rendering paths handle titles. Resolves `latex-callout-title-arg-passthrough.md`. Status: Proposed (awaiting human acceptance).

## Alternatives considered (task direction)

- **(Chosen) Fix both parser fidelity bugs in a single task.** Both bugs are in `app/parser.py`, both were surfaced in the same TASK-003 review cycle, both affect the same rendering pipeline (ADR-003), and both are small fixes. Bundling them avoids two task-proposal/design/implement cycles for work that shares a codebase surface. Risk: if one fix is unexpectedly complex, it delays the other. Mitigation: both bugs have well-enumerated options in their project issue files; the simplest option for each is a few lines of parser code.

- **Fix only the tabular bug; defer callout titles to TASK-005.** Would produce a narrower task. Rejected because: (a) both fixes are in the same file (`app/parser.py`), touching the same environment-handler pattern; (b) the callout-title fix is at least as small as the tabular fix; (c) splitting introduces a second test/design/implement/review cycle for marginal scope reduction. If the architect determines during `/design` that the callout-title fix requires a significant IR refactor, it can be descoped at that point.

- **Skip fidelity fixes; proceed directly to multi-chapter validation.** Would validate Chapters 2-13 with known bugs, then fix the bugs afterward and re-validate. Rejected because: (a) validating with known bugs means every screenshot review shows junk table rows and missing callout titles — the human would have to mentally filter known bugs from new bugs, which is exactly the kind of cognitive overhead that degrades review quality; (b) fixing the bugs first means the validation pass tests the real rendering quality; (c) the bugs are small and the validation pass is the obvious follow-up.

- **Jump to Notes or Quiz features.** Would advance the manifest's persistence and reinforcement-loop goals. Rejected because: (a) consumption of the full curriculum via readable Lectures is the foundation for Notes and Quizzes — building Notes on top of a rendering surface with broken tables and missing callout titles is building on a cracked foundation; (b) the fidelity fixes are small (one session) and clear the path for multi-chapter validation, which in turn clears the path for Notes/Quiz work.

## Architectural concerns I want to raise

- **ADR-003's "warn-per-node and continue" pattern is the natural error-handling model for both fixes.** The tabular column spec is currently passing through as text — the wrong failure mode. It should either be stripped (option 1) or warned-and-stripped (option 3). The callout title is currently passing through as bracketed text — the wrong failure mode. Both fixes align the parser's behavior with ADR-003's existing contract.

- **The callout-title fix may touch the Jinja2 template contract (ADR-003 boundary).** If the title is routed through the IR as a separate field (project issue option 2), that is a change to the IR shape that ADR-003 implicitly defined. The architect should determine during `/design` whether this warrants a lightweight ADR or is within ADR-003's latitude ("the implementer may extend [the parser] with environment-specific handlers").

- **CSS changes for callout titles belong in `lecture.css` (ADR-008 boundary).** ADR-008 scoped `lecture.css` for Lecture-body content styling, including `.callout-*` rules. A new `.callout-title` rule is a small addition within that scope — no new CSS file needed.

- **No `MANIFEST TENSION:` raised.** The manifest is internally consistent with this task. ss3 (consumption) motivates; ss5 (read-only source) is trivially preserved; ss6 (visible failures) is honored by the warn-per-node pattern.

- **No `ARCHITECTURE LEAK:` found.** `architecture.md` correctly indexes Accepted ADRs; no stale or fabricated content.

## Out of scope (this task)

- Multi-chapter rendering validation (Chapters 2-13). That is the follow-up task after fidelity is fixed.
- Table alignment preservation via CSS classes (project issue option 2 for tabular). If the architect picks strip-and-ignore (option 1 or 3), alignment-as-CSS is deferred.
- Notes, Quizzes, persistence, AI integration. Manifest ss8 entities deferred until a task forces them.
- The `\\` linebreak rendering issue (surfaced in TASK-002 Run 009). Separate parser bug, separate scope.
- CSS preprocessor, dark mode, responsive layout. Out of scope per manifest ss5 and prior tasks.

## Verify

- The human runs `python3 -m pytest tests/` and confirms exit code 0 (all existing tests plus new Playwright tests pass).
- The human reviews last-run Playwright screenshots at `tests/playwright/artifacts/` and confirms: (1) tables in Chapter 1 no longer show column-spec text in their first row; (2) callout environments with `[Title]` arguments display the title as a visually distinct header element; (3) callout environments without titles render as before (no regression).
- Rendered-surface verification per ADR-010: Playwright tests green + screenshots reviewed, recorded as a `rendered-surface verification -- pass` row in the audit Human-gates table.
- The reviewer runs manifest-conformance against the staged diff: MC-6 PASS, no new blockers.
- Both project issues are resolved: `latex-tabular-column-spec-passthrough.md` resolved by ADR-011; `latex-callout-title-arg-passthrough.md` resolved by ADR-012.
