# TASK-007: Parser fidelity — strip tabular column-spec residue from cells and stop `\texttt{}` from trapping inline math

**Inputs read:**
- Manifest: §3 (drive consumption — 600-800 visible LaTeX-bleed defects across the 12-chapter corpus directly degrade the consumption surface this project exists to deliver), §5 (Lecture source is read-only — no in-app authoring; parser fixes change rendering, not source), §6 (visible failures, single source — the rendered surface must not silently misrepresent source content), §8 (Chapter, Section, Lecture glossary — terms unchanged)
- architecture.md: Accepted ADRs 001–016. Directly touched: ADR-003 (rendering pipeline — pylatexenc node-walker, custom environment/macro handlers, warn-per-node), ADR-008 (CSS layering — Lecture-body styling lives in `app/static/lecture.css`), ADR-010 (Playwright verification gate — last-run screenshots gitignored). Implicitly touched: ADR-011 (already Accepted; this task closes the implementation gap against it).
- ADR-011 (Accepted, TASK-004): "strip column spec from rendered output entirely (only data rows render); log a structured warning per ADR-003's warn-per-node pattern for complex/uninterpreted spec features (vertical bars, `p{width}`, `@{...}`). Simple alignment letters (`l`, `c`, `r`) are stripped without warning." Implementation does not currently honor this commitment for the `@{}...@{}` idiom or for `p{width}` columns.
- ADR-012 (Accepted, TASK-004): pattern for adding new macro/environment handlers to `app/parser.py` and `lecture.css` together — the precedent this task follows.
- ADR-013 (Accepted, TASK-005): split-harness verification (smoke + Playwright). The 12-Chapter parameterized screenshot harness is already in place; this task reuses it.
- ADR-015 (Accepted with amendment, TASK-005): bug-class partition routes class-1 LaTeX/parser content-fidelity bugs to in-scope fold-in under new Proposed ADRs *at the typical-case scale* (1–3 instances). The corpus-wide validation pass surfaced the catalog at a different scale (5 categories × tens-to-hundreds each); the human's Run 008 gate decision was "ship TASK-005 with the catalog; pivot to a focused TASK-007." This task is that pivot. See "Architectural concerns I want to raise."
- Project issues this task progresses or resolves:
  - `design_docs/project_issues/parser-fidelity-tabular-column-spec-residue.md` (Open) — directly resolved.
  - `design_docs/project_issues/parser-fidelity-texttt-traps-inline-math.md` (Open) — directly resolved.
- Project issues this task explicitly defers (visible in "Out of scope"):
  - `design_docs/project_issues/parser-fidelity-unhandled-environments-and-text-macros.md` (Open)
  - `design_docs/project_issues/parser-fidelity-body-linebreak-and-display-math.md` (Open)
  - `design_docs/project_issues/ch06-textbackslash-double-renders-as-double-backslash.md` (Open)
- Conformance rules touched: MC-6 (Lecture source read-only — trivially preserved; this task only edits `app/parser.py`, `app/static/lecture.css`, and tests). MC-3 (Mandatory/Optional split — not touched). All other rules: not implicated.
- Code: `app/parser.py` (the parser surface to edit), `app/static/lecture.css` (CSS class for `.texttt`), `tests/playwright/` (where the new visual regression tests land), `tests/playwright/test_task005_multi_chapter_screenshots.py` (the harness this task reuses for re-verification across all 12 Chapters).

## What and why

The TASK-005 12-Chapter screenshot review surfaced ~600–800 visible LaTeX-bleed defects across 5 categories. This task fixes the two highest-impact bounded categories in one session, following the TASK-004 precedent (two related parser handlers, two ADRs, one cleanup pass):

1. **Tabular column-spec residue leaking into the first cell of every `@{}...@{}` and `p{...}` table** (~53 visible instances; ch-02/03/04). This is an ADR-011 implementation-gap — the ADR (Accepted) commits to stripping the spec entirely, but the implementation strips only the empty `{}` groups inside the spec, leaving `lccc@`, `p3.4cmp5cmp4.8cm@`, etc. in the rendered cell. Closing the gap honors an existing commitment.
2. **`\texttt{}` rendered as `<code>` traps inline math from MathJax** (~200+ visible defects; ch-04 ASCII-art callouts unreadable; ch-09/10 also affected). MathJax v3's default `skipHtmlTags` includes `code`, so `$\to$`, `$\bullet$`, `$\leftarrow$` render as literal source text instead of math glyphs. The fix is to render `\texttt{}` as `<span class="texttt">` (a tag MathJax does process) with a `monospace` CSS rule.

Together, these two fixes clear ~250+ of the ~600–800 catalogued defects in one session. The remaining three project_issues (~350–550 defects across unhandled environments/text-macros, body `\\`, ch-06 textbackslash) are deferred to follow-up tasks; their bounded shape is less certain and at least one (unhandled-environments) requires per-environment editorial decisions that would inflate this task.

This advances the primary objective (manifest §3) directly: every visible LaTeX-bleed in the rendered Lecture surface is an obstacle to consumption. The fixes are small (each is a single parser-handler change matching the ADR-011/ADR-012 shape) and re-use the TASK-005 verification harness for cross-corpus re-verification.

## Acceptance criteria

- [ ] Given a Chapter source containing `\begin{tabular}{@{}lccc@{}}` (the dominant idiom across ch-02/03/04), when the Lecture page renders, then no characters from the column-spec argument (`@`, `l`, `c`, `r`, `p`, digits, units like `cm`, braces) appear as visible text in any rendered table cell — only data rows from the tabular body are rendered. Assertion: rendered HTML for ch-02/03/04 contains zero substrings matching `lccc@`, `p3.4cm`, or other spec-argument residue patterns.
- [ ] Given a Chapter source containing `\begin{tabular}{@{}p{3.4cm}p{5cm}p{4.8cm}@{}}` or other `p{width}` columns, when the Lecture page renders, then the column-spec residue does not appear in any cell, and the parser logs a structured warning per ADR-003's warn-per-node pattern naming the unhandled spec feature (`p{width}`).
- [ ] Given a Chapter source containing `\texttt{head $\to$ [7 | $\bullet$] $\to$ [9 | $\bullet$] $\to$ [5 | null]}` (or similar `\texttt{}` with embedded inline math), when the Lecture page renders in a real browser (Playwright), then MathJax renders the embedded math glyphs (rendered DOM contains `<mjx-container>` elements within the typewriter-fonted span) — not literal `$\to$` source text.
- [ ] Given any `\texttt{}` macro in source (with or without embedded math), when the Lecture page renders, then the typewriter font is preserved visually (Playwright assertion: the span has computed `font-family` matching `monospace` per the new `.texttt` CSS rule).
- [ ] Given the existing TASK-001/003/004/005 Playwright tests, when the full test suite runs (`python3 -m pytest tests/`), then all existing tests pass — no regressions.
- [ ] Given the new fixes, when Playwright tests run, then at least one regression test per fix verifies the corrected rendering: (a) tabular-residue absence in ch-02/03/04 first-row first-cell, (b) `<mjx-container>` presence inside `\texttt{}` spans for at least one ch-04 ASCII-art callout.
- [ ] Given the TASK-005 12-Chapter parameterized screenshot harness (`tests/playwright/test_task005_multi_chapter_screenshots.py`), when this task ships, then a re-run of the harness produces a fresh set of last-run screenshots and the human re-reviews to confirm visible-defect reduction in the two target categories. Recorded as a `rendered-surface verification — pass (TASK-007 categories)` row in the audit Human-gates table per ADR-010.
- [ ] Given the staged diff, when manifest-conformance runs, then MC-6 (no writes to `content/latex/`) PASS.
- [ ] Both target project_issues are resolved: `parser-fidelity-tabular-column-spec-residue.md` resolved by ADR-NNN (the new tabular-residue ADR); `parser-fidelity-texttt-traps-inline-math.md` resolved by ADR-NNN (the new texttt-as-span ADR).

## Architectural decisions expected

- **ADR-NNN: Tabular column-spec stripping — implementation alignment with ADR-011.** The handler for `\begin{tabular}` must consume and discard the entire column-spec argument (everything between the first `{` and its matching `}` after `\begin{tabular}`), including content inside nested `{}` (e.g., `p{3.4cm}`). Per the project_issue, three options materially differ (handler-level greedy strip; pylatexenc structured access; pre-parse regex). Architect picks at `/design`. This ADR is a clarifying companion to ADR-011 (it does not supersede; it implements). The architect should decide whether this is a separate ADR or a Resolution-note clarification on ADR-011 — see "Architectural concerns I want to raise" below.
- **ADR-NNN: `\texttt{}` rendering — emit `<span class="texttt">` instead of `<code>` so MathJax processes embedded inline math.** Per the project_issue, options are (1) span-with-CSS, (2) pre-process math inside the texttt argument, (3) MathJax config change (forbidden — affects pure code blocks), (4) author-side workaround (forbidden — manifest §5). Option 1 is the bounded, ADR-008-aligned path. The new CSS rule (`.texttt { font-family: monospace; }`) belongs in `app/static/lecture.css` per ADR-008.

These become Proposed ADRs during `/design TASK-007`. Nothing substantive lands in `architecture.md` until the human gates them.

## Alternatives considered (task direction)

- **(Chosen) Bundle the two highest-impact bounded parser-fidelity fixes (tabular residue + texttt math) into one task.** Both fixes live in `app/parser.py` macro/environment handlers (same file, same pattern as TASK-004's ADR-011/ADR-012). Both are ADR-shape-equivalent to TASK-004. Together they clear ~250+ of the ~600–800 catalogued defects. One session, two ADRs, one re-verification pass against the TASK-005 12-chapter harness. Risk: if either fix is unexpectedly complex (e.g., pylatexenc does not expose what we need), descope to one fix. Mitigation: both fixes have well-enumerated bounded options (Option 1 in each project_issue) that match the ADR-011/ADR-012 shape.

- **Pick only one fix (the highest-impact one — `\texttt{}` math trap, ~200+ defects).** Narrower task; produces a single ADR; lowest risk of one-fix-blocking-the-other. Rejected because the TASK-004 precedent demonstrates that two related parser-handler fixes coexist comfortably in one task; splitting introduces a second `/design`/`/implement`/`/review` cycle for marginal scope reduction. If the architect determines during `/design` that one fix is materially harder, descoping is straightforward.

- **Tackle all 5 parser-fidelity project_issues at once.** Rejected — explicitly the wrong scale per the human's Run 008 ship-with-catalog gate decision and per the "one task = one session" rhythm. Unhandled-environments alone requires per-environment editorial decisions across ~28 instances spanning at least 4 distinct LaTeX environment names (`algorithm`, `algorithmic`, `proof`, `theorem`, etc.); body `\\` requires a triage sample-and-decide pass before any ADR is draftable; ch-06 textbackslash is its own one-Chapter quirk. Bundling the unbounded ones with the bounded ones would inflate the task to multi-session scope.

- **Supersede ADR-015 first; defer parser-fidelity work to a subsequent task.** Process work that ships zero visible-defect reduction. Rejected because the reviewer (Run 009) and the human (Run 008 gate) both already concluded that the amended ADR-015 was correct for the typical case and that this specific corpus-wide pass justified an "amendment-of-amendment" routing decision recorded in the audit. Re-encoding that into an ADR-015 supersedure ADR is real architectural cleanup — but it's better-evidenced *after* a second corpus-wide pass surfaces the same scale problem. Surfacing one anomaly does not yet justify a supersedure; surfacing the same shape twice does. See "Architectural concerns I want to raise."

- **Tackle the unhandled-environments project_issue first (28 instances, ch-09 dominant).** Rejected — even though it's smaller in raw count than the texttt-math category, it requires per-environment editorial decisions (is `algorithm` a `<pre>`? a `<figure>`? a `<div class="algorithm">`? what about `proof` and `theorem`?). Each decision is its own micro-ADR. The bounded shape is uncertain at task-proposal time. The two fixes chosen here have enumerated, ADR-shape-equivalent options at task-proposal time — they are ready for `/design` without per-environment editorial discovery work.

- **Tackle the project-setup gap (lint/type-check placeholders in `CLAUDE.md`) first.** Rejected as a primary direction — the placeholders are surfaced via the `feedback_dont_prescribe_predecisions` memory rule (don't prescribe actions before the prerequisite ADR exists), and there is no ADR backing a tooling choice. Surface as a project-setup observation in "Architectural concerns" below; let the human decide whether to commission a tooling-choice `/design` cycle.

## Architectural concerns I want to raise

- **ADR-015 amendment scale problem (inherited from TASK-005 Run 008/Run 009).** The amended "fold class-1 in-scope under new Proposed ADRs" rule was sized for the ADR-011/ADR-012/ADR-014 typical-case shape (~1–3 instances per category). At TASK-005's empirical scale (5 categories × tens-to-hundreds each), the rule was the wrong tool, and the human's Run 008 gate decision was an "amendment-of-amendment" routing. **My recommendation: do not propose an ADR-015 supersedure as a separate next task yet.** Reasons: (a) one corpus-wide pass is one data point; the supersedure should be evidence-driven from at least two passes; (b) the reviewer (Run 009) and the human concurred non-blocking; (c) the existing audit-trail recorded the amendment-of-amendment, which is a defensible documentation route for a one-off scale anomaly. **However:** if a second corpus-wide pass (e.g., a future "validate every Note renders" pass under ADR-013's split-harness pattern) surfaces the same scale problem, that is the trigger for a `Supersedes ADR-015` cycle. I am surfacing the recommendation here so the next architect cycle (after this one) inherits the trigger condition and does not have to re-derive it. This task is not the right place to propose the supersedure.

- **ADR-011 implementation gap is an ADR-fidelity defect, not a new architectural decision.** ADR-011 (Accepted, TASK-004) commits to "strip column spec from rendered output entirely." The implementation does not honor that. The `/design TASK-007` architect should decide whether the new tabular-residue ADR is (a) a separate ADR that *implements* ADR-011's commitment (clearer audit trail; consistent with the per-fix-one-ADR pattern), or (b) a Resolution-note clarification appended to ADR-011 itself plus a code change with no new ADR (less paperwork; consistent with "ADRs are decisions, not implementation trackers"). My weak preference is (a): the gap is empirical evidence that ADR-011's commitment was not load-bearing in the implementer's read of the parser handler, and a separate ADR makes the implementation contract explicit. The architect at `/design` can override.

- **Project-setup gap: `CLAUDE.md` "Commands" section has placeholders for `<project lint command>` and `<project type-check command>`** (CLAUDE.md lines 63–64). The project has no lint/type-check tooling configured. This was surfaced in TASK-005 audit Run 007 (verify phase) as a non-blocking observation. **This is a tooling-choice question (ruff vs. flake8 vs. pylint; mypy vs. pyright vs. none) that requires its own `/design` cycle if the human wants tooling at all.** I am not proposing it as the next task because (a) it does not advance the primary objective directly, (b) the project has shipped 6 tasks without it, and (c) surfacing actions to the human before the prerequisite ADR exists violates the `feedback_dont_prescribe_predecisions` memory rule. I am surfacing it here so the human can commission a tooling-choice task whenever they choose to.

- **No `ARCHITECTURE LEAK:` found in this `/next` cycle.** Every `.md` file I read in the prerequisite set classified correctly per the tier table. CLAUDE.md §"Orchestrator verification of subagent outputs" now has its inline ADR-016 citation; the previously-recurring leak is closed. `architecture.md` is index-only and every project-structure-summary sentence traces to an Accepted ADR.

- **No `MANIFEST TENSION:` raised.** The manifest is internally consistent with this task. §3 (consumption) motivates; §5 (read-only source) is trivially preserved (parser-only changes); §6 (visible failures) is honored by the warn-per-node pattern for unhandled spec features; §7/§8 invariants and glossary unchanged.

- **Conformance-skill compliance.** MC-6 (read-only source) is the only directly touched rule and is preserved by construction (this task edits `app/parser.py`, `app/static/lecture.css`, and tests; not `content/latex/`). MC-3 (M/O split) is not touched. All other MC rules are not implicated.

## Out of scope (this task)

- The remaining three parser-fidelity project_issues:
  - `parser-fidelity-unhandled-environments-and-text-macros.md` — defer to a follow-up parser-fidelity task; requires per-environment editorial decisions.
  - `parser-fidelity-body-linebreak-and-display-math.md` — defer; requires triage sample-and-decide before an ADR is draftable.
  - `ch06-textbackslash-double-renders-as-double-backslash.md` — defer; one-Chapter quirk, low priority relative to the corpus-wide categories.
- An ADR-015 supersedure (see "Architectural concerns" — defer pending a second corpus-wide pass).
- A clarifying Resolution-note edit to ADR-011 (the `/design` architect decides whether the new ADR or a clarifying note is the right shape; this task's scope encompasses either path).
- Lint / type-check tooling choice (project-setup gap — separate `/design` cycle if commissioned).
- Notes, Quizzes, persistence, AI integration. Manifest §8 entities deferred until a task forces them.
- Generic table-alignment styling (no current project_issue requests it).
- A new `<table>`-level CSS class (the existing tabular rendering is sufficient once the residue is stripped; new CSS is only the `.texttt` rule).
- Configuration changes to MathJax (forbidden direction per the texttt project_issue's Option 3).
- Author-side LaTeX rewrites (forbidden direction per manifest §5 and the project_issue's Option 4).

## Verify

- The human runs `python3 -m pytest tests/` and confirms exit code 0 (existing 387 tests + the new regression tests pass).
- The human re-runs the TASK-005 12-Chapter Playwright screenshot harness (`tests/playwright/test_task005_multi_chapter_screenshots.py`) and reviews the fresh last-run screenshots in `tests/playwright/artifacts/`.
- Visual confirmation against the TASK-005 catalog:
  - **ch-02, ch-03, ch-04 tables:** no `lccc@`, `p3.4cm`, or similar column-spec residue in any rendered cell.
  - **ch-04 "Picture the list" / "Picture of the interior splice" callouts:** ASCII-art node diagrams render with arrows/bullets as math glyphs (via MathJax), not as raw `$\to$` / `$\bullet$` source.
  - **Sample one ch-09 or ch-10 `\texttt{}` block** to confirm typewriter font is preserved (the `<span class="texttt">` rule has the same visual effect as the prior `<code>` element).
- Rendered-surface verification per ADR-010: Playwright tests green + screenshots reviewed, recorded as a `rendered-surface verification — pass (TASK-007 categories)` row in the audit Human-gates table.
- The reviewer runs manifest-conformance against the staged diff: MC-6 PASS, no new blockers.
- Both target project_issues are resolved (Status flipped from `Open` to `Resolved by ADR-NNN`).
- The remaining three parser-fidelity project_issues are visibly cited in this task's audit as deferred (no Status change required — they remain `Open` for the next architect cycle).
- The orchestrator confirms (per ADR-016) that every expected file change is present via `git diff` before passing each phase boundary.
