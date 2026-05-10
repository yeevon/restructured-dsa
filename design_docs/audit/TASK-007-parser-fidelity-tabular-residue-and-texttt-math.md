# LLM Audit — TASK-007: Parser fidelity — strip tabular column-spec residue from cells and stop `\texttt{}` from trapping inline math

**Task file:** `design_docs/tasks/TASK-007-parser-fidelity-tabular-residue-and-texttt-math.md`
**Started:** 2026-05-09T00:00:00Z
**Status:** Committed
**Current phase:** committed

---

## Human gates

| Time | Gate | Result | Notes |
|---|---|---|---|
| 2026-05-09 | Task reviewed | accepted | Architect's TASK-007 proposal accepted (bundle highest-impact bounded parser-fidelity fixes from TASK-005 catalog: tabular column-spec residue + `\texttt{}` math-trap). Two project_issues route to ADRs in this task; three remain Open for follow-up tasks. |
| 2026-05-09 | ADR-017 reviewed | accepted | Tabular balanced-brace consumption (implements ADR-011 contract; does not supersede). Accepted as written. Procedural separate-ADR-vs-Resolution-note framing acknowledged; substance is identical either way. |
| 2026-05-09 | ADR-018 reviewed | accepted | `\texttt{}` → `<span class="texttt">` with CSS reproducing existing inline `p code` look. Accepted as written. Element choice (span over kbd/samp/var) and CSS-shape choice acknowledged. |
| 2026-05-09 | Tests reviewed | accepted | Three test files (1626 lines total): tabular residue smoke + unit, texttt-as-span smoke + unit + CSS-load, Playwright DOM + post-MathJax. Pre-implementation pytest: 308 collected, 25 failing (all TASK-007), 283 passing, 0 regressions. Test-writer flagged ch-10 as additionally affected by tabular residue (broader than Run 008's hot-chapter list); ADR-017's fix covers it. Proceeding to implementer phase. |
| 2026-05-09 | rendered-surface verification | pass | Human reviewed Lecture-page screenshots (ADR-010 gate). Tabular cells in ch-02/03/04 no longer show `lccc@` / `p3.4cm` residue. ch-04 ASCII-art callouts ("Picture the list", "Picture of the interior splice") now render arrows / bullets via MathJax inside `<span class="texttt">`. AC-7 satisfied. |
| 2026-05-09 | Commit review | ready | Reviewer Run 006 verdict APPROVED. Human authorized commit + push. ADR-017 + ADR-018 ship; both project_issues resolved; three deferred parser-fidelity issues remain Open for follow-up tasks. |

---

## Agent runs

### Run 001 — architect / Mode 1 `/next`

**Time:** 2026-05-09T00:00:00Z

**Input files read:**
- `design_docs/MANIFEST.md`
- `CLAUDE.md`
- `design_docs/architecture.md`
- `.claude/skills/manifest-conformance/SKILL.md`
- `design_docs/decisions/ADR-015-multi-chapter-triage-discipline.md` (full — source for the amended bug-class partition and the scale-of-fold-in question Run 008 surfaced)
- `design_docs/audit/TASK-005-multi-chapter-rendering-validation.md` — Run 008 (corpus-wide LaTeX-bleed categorization), Run 009 (reviewer pre-commit), Human-gates table (`rendered-surface verification — catalog accepted` row, `Commit review — ready` row)
- `design_docs/tasks/TASK-004-parser-fidelity-tabular-callout-titles.md` (precedent task — bundled two parser-handler fixes in one task, two ADRs)
- `design_docs/tasks/TASK-006-ratify-orchestrator-verification-rule.md` (most recent task; closed)
- `design_docs/project_issues/parser-fidelity-tabular-column-spec-residue.md` (Open)
- `design_docs/project_issues/parser-fidelity-texttt-traps-inline-math.md` (Open)
- `design_docs/project_issues/parser-fidelity-unhandled-environments-and-text-macros.md` (Open — deferred)
- `design_docs/project_issues/parser-fidelity-body-linebreak-and-display-math.md` (Open — deferred)
- `design_docs/project_issues/ch06-textbackslash-double-renders-as-double-backslash.md` (Open — deferred)
- `design_docs/project_issues/multi-chapter-source-naming.md` (Resolved by ADR-005 — read for context)
- `design_docs/project_issues/task001-test-vs-adr006-rail-collision.md` (Resolved — read for context)
- `design_docs/project_issues/adr006-rail-half-implemented-no-css.md` (Resolved by ADR-008 — read for context)
- `app/parser.py` (header — to confirm the parser surface and ADR-003's documented contract)

**Tools / commands used:**
- Read on every file in the input list above.
- Glob: `design_docs/decisions/*.md`, `design_docs/project_issues/*.md`, `design_docs/tasks/*.md`, `design_docs/audit/*.md` (to confirm the highest TASK-NNN is 006 and to enumerate the project_issue catalog).
- Grep: `Run 008|Run 009|catalog accepted|rendered-surface verification` against the TASK-005 audit (to locate the load-bearing run entries without reading the full 30K-token audit).
- Write: `design_docs/tasks/TASK-007-parser-fidelity-tabular-residue-and-texttt-math.md`, `design_docs/audit/TASK-007-parser-fidelity-tabular-residue-and-texttt-math.md`.

**Files created:**
- `design_docs/tasks/TASK-007-parser-fidelity-tabular-residue-and-texttt-math.md`
- `design_docs/audit/TASK-007-parser-fidelity-tabular-residue-and-texttt-math.md`

**Files modified:** none.
**Files deleted:** none.

**Task alternatives considered:**
- (Chosen) Bundle the two highest-impact bounded parser-fidelity fixes (tabular residue + texttt math) into one task — TASK-004 precedent shape; ~250+ visible defects cleared per session; one re-verification pass against the TASK-005 12-chapter harness.
- Pick only one fix (texttt math, ~200+ defects) — narrower and lower-risk but loses the TASK-004 economy of bundling related parser-handler fixes.
- Tackle all 5 parser-fidelity project_issues at once — wrong scale per the human's Run 008 ship-with-catalog gate decision; multi-session inflation.
- Supersede ADR-015 first; defer parser-fidelity work — process-only; ships zero visible-defect reduction; reviewer (Run 009) and human concurred non-blocking; better evidence-driven from at least two corpus-wide passes.
- Tackle the unhandled-environments project_issue first (28 instances, ch-09 dominant) — smaller raw count but requires per-environment editorial decisions across `algorithm`/`algorithmic`/`proof`/`theorem`/etc.; bounded shape uncertain at task-proposal time.
- Tackle the project-setup gap (lint/type-check placeholders in CLAUDE.md) first — does not advance the primary objective; tooling-choice question requiring its own `/design` cycle; surfaced as a project-setup observation in the task's "Architectural concerns" section per the `feedback_dont_prescribe_predecisions` memory rule.

**Decisions surfaced (forecast for `/design TASK-007`):**
- **ADR-NNN: Tabular column-spec stripping — implementation alignment with ADR-011.** Architect picks among Options 1/2/3 in `parser-fidelity-tabular-column-spec-residue.md`. Architect also decides whether this is a separate ADR (clearer audit trail) or a clarifying Resolution-note on ADR-011 (less paperwork) — task's "Architectural concerns" section recommends the separate ADR but defers to `/design`.
- **ADR-NNN: `\texttt{}` rendering — emit `<span class="texttt">` instead of `<code>`.** Per `parser-fidelity-texttt-traps-inline-math.md` Option 1; ADR-008-aligned CSS rule lands in `app/static/lecture.css`.
- The amended ADR-015 supersedure question is **explicitly NOT** a TASK-007 decision; surfaced for the architect cycle that follows the next corpus-wide pass (trigger condition: a second pass surfacing the same scale problem).

**Architecture leaks found:** none. CLAUDE.md §"Orchestrator verification of subagent outputs" has its inline ADR-016 citation; `architecture.md` is index-only and every project-structure-summary sentence traces to an Accepted ADR.

**Pushback raised:**
- **Inherited (non-blocking):** ADR-015 amendment scale problem — surfaced in task's "Architectural concerns" with a recommendation to defer the supersedure ADR until a second corpus-wide pass surfaces the same shape. Not a TASK-007 deliverable.
- **Inherited (non-blocking):** ADR-011 implementation gap is an ADR-fidelity defect — surfaced in task's "Architectural concerns" with a weak preference for a separate ADR over a Resolution-note clarification; `/design` architect decides.
- **Project-setup observation (non-blocking):** `CLAUDE.md` "Commands" section has placeholders for `<project lint command>` and `<project type-check command>`. Surfaced in task's "Architectural concerns" with the explicit note that this is not being prescribed as an action — a tooling-choice `/design` cycle is the human's call.

**Output summary:** Proposed TASK-007 — bundle the two highest-impact bounded parser-fidelity fixes (tabular column-spec residue across ch-02/03/04 and `\texttt{}` math-trap across ch-04/09/10) into one task following the TASK-004 precedent. Together these clear ~250+ of the ~600–800 catalogued visible LaTeX-bleed defects. Two new ADRs anticipated (one per fix). Three remaining parser-fidelity project_issues explicitly deferred to follow-up tasks. ADR-015 supersedure question parked for a future cycle pending second-corpus-pass evidence. CLAUDE.md lint/type-check placeholders surfaced as an observation, not suggested as an action.

### Run 002 — architect / Mode 2 `/design`

**Time:** 2026-05-09T00:30:00Z

**Input files read:**
- `design_docs/MANIFEST.md`
- `CLAUDE.md`
- `design_docs/architecture.md`
- `.claude/skills/manifest-conformance/SKILL.md`
- `design_docs/tasks/TASK-007-parser-fidelity-tabular-residue-and-texttt-math.md` (full)
- `design_docs/audit/TASK-007-parser-fidelity-tabular-residue-and-texttt-math.md` Run 001 (architect's own forecast)
- `design_docs/project_issues/parser-fidelity-tabular-column-spec-residue.md` (Open at start of run)
- `design_docs/project_issues/parser-fidelity-texttt-traps-inline-math.md` (Open at start of run)
- `design_docs/decisions/ADR-003-rendering-pipeline.md`
- `design_docs/decisions/ADR-011-tabular-column-spec-handling.md`
- `design_docs/decisions/ADR-012-callout-title-rendering.md`
- `design_docs/decisions/ADR-014-title-linebreak-macro-stripping.md` (sibling-shape precedent for parser-handler-change ADRs)
- `app/parser.py` (full — to ground the mechanism contract in code reality, especially `_render_tabular` lines 376–417 and `_convert_inline_latex` texttt branch at line 147–148)
- `app/static/lecture.css` (full — to identify existing `<code>` consumers that the texttt change must not regress: bare `code` rule at lines 124–126, `p code` rule at lines 128–133)
- `app/templates/base.html.j2` (full — to confirm MathJax v3 config has no `skipHtmlTags` override, so defaults apply)
- `design_docs/audit/TASK-005-multi-chapter-rendering-validation.md` Run 008 (corpus-wide LaTeX-bleed categorization — instance counts and Chapter distribution)

**Tools / commands used:**
- Read on each file in the input list above.
- Glob: `design_docs/decisions/ADR-011*.md` / `ADR-014*.md` / `ADR-015*.md` / `ADR-016*.md` (to resolve actual filenames).
- Grep: `code` against `app/static/lecture.css` and `app/parser.py` (to enumerate every existing `<code>` consumer); `mathjax|MathJax|skipHtmlTags` against `app/` (to confirm no override exists); `&lt;code|&lt;span|texttt` against `app/` (to catalog texttt usage); `Run 008|tabular|texttt|column.spec` against TASK-005 audit.
- Write: `design_docs/decisions/ADR-017-tabular-column-spec-stripping-implementation.md`, `design_docs/decisions/ADR-018-texttt-as-span-for-mathjax-passthrough.md`.
- Edit: `design_docs/architecture.md` (added two rows to "Proposed ADRs" table), `design_docs/project_issues/parser-fidelity-tabular-column-spec-residue.md` (Status flip + Resolution note), `design_docs/project_issues/parser-fidelity-texttt-traps-inline-math.md` (Status flip + Resolution note), this audit file (header Status/phase update + this run entry).

**Files created:**
- `design_docs/decisions/ADR-017-tabular-column-spec-stripping-implementation.md` (Status: Proposed)
- `design_docs/decisions/ADR-018-texttt-as-span-for-mathjax-passthrough.md` (Status: Proposed)

**Files modified:**
- `design_docs/architecture.md` — added ADR-017 and ADR-018 rows to "Proposed ADRs (awaiting human acceptance)" table.
- `design_docs/project_issues/parser-fidelity-tabular-column-spec-residue.md` — Status flipped to "Resolved by ADR-017 (Proposed; contingent on acceptance)"; appended one-paragraph Resolution note.
- `design_docs/project_issues/parser-fidelity-texttt-traps-inline-math.md` — Status flipped to "Resolved by ADR-018 (Proposed; contingent on acceptance)"; appended one-paragraph Resolution note.
- `design_docs/audit/TASK-007-parser-fidelity-tabular-residue-and-texttt-math.md` — header Status `In progress` → `Blocked`; Current phase `next` → `design`; appended this Run 002 entry.

**Files deleted:** none.

**ADRs proposed:**
- `ADR-017` — Tabular column-spec stripping uses balanced-brace consumption of `\begin{tabular}{...}` so nested `{}` pairs (`@{}`, `p{width}`, `>{...}`, `<{...}`) are consumed as part of the spec, not treated as the spec's terminator. Implements ADR-011 (Accepted); does not supersede.
- `ADR-018` — `\texttt{}` emits `<span class="texttt">` instead of `<code>` so MathJax processes embedded inline math; new `.texttt` CSS rule in `lecture.css` reproduces the inline-code visual look (font-family monospace, background, padding, border-radius).

**Project issues opened/resolved:**
- `parser-fidelity-tabular-column-spec-residue` — flipped Open → Resolved by ADR-017 (Proposed).
- `parser-fidelity-texttt-traps-inline-math` — flipped Open → Resolved by ADR-018 (Proposed).
- No new project_issues opened.

**architecture.md changes:** two rows added to "Proposed ADRs (awaiting human acceptance)" table; no change to Accepted ADRs table; no change to project-structure summary (Accepted set unchanged this cycle).

**Architecture leaks found:** none. CLAUDE.md §"Orchestrator verification of subagent outputs" carries its inline ADR-016 citation (the previously-recurring leak is closed). `architecture.md` is index-only; every project-structure-summary sentence still traces to an Accepted ADR — the new rows live in the Proposed table and do not introduce architectural claims into the summary.

**Pushback raised:**
- **Recorded in ADR-017 "Alternatives considered":** the Resolution-note-on-ADR-011 path (Alternative A) was the lighter-touch option; rejected on procedural grounds (in-place edits to Accepted ADRs erase chronology) plus substantive grounds (the mechanism choice is a real decision worth its own ADR). Architect's preference for separate-ADR is procedural; the substantive decision (balanced-brace scan) is the same either way.
- **Recorded in ADR-018 "My recommendation vs the user's apparent preference":** mildly opinionated on element choice (`<span>` over `<kbd>`/`<samp>`/`<var>`) and CSS shape (reproduce existing `p code` look rather than minimal `font-family: monospace`). Both can be challenged at gate; substance (Option 1 — span-with-CSS) is aligned with the user's direction.
- **Inherited (non-blocking) from TASK-007 task file:** ADR-015 amendment-scale supersedure question — explicitly deferred per task framing; default-defer affirmed.
- No `MANIFEST TENSION:` raised. No `> NEEDS HUMAN:` raised — both ADRs are decidable now; both await routine human acceptance.

**Implementation blocked pending human acceptance:** yes — `ADR-017` (Proposed) and `ADR-018` (Proposed). `/implement TASK-007` cannot proceed until both gates land. No Pending Resolution items.

**Output summary:** Recorded the two TASK-007 architectural decisions as ADR-017 (tabular column-spec balanced-brace consumption — implements ADR-011's outcome contract with a tighter mechanism) and ADR-018 (`\texttt{}` → `<span class="texttt">` with matching CSS rule). Both Proposed. architecture.md updated mechanically with two new rows. Both target project_issues flipped to Resolved-by-ADR (contingent). Implementation blocked pending human acceptance of both ADRs.

### Run 003 — test-writer / `/implement` TASK-007

**Time:** 2026-05-09T02:00:00Z

**Input files read:**
- `design_docs/MANIFEST.md`
- `CLAUDE.md`
- `design_docs/architecture.md`
- `.claude/skills/manifest-conformance/SKILL.md` (project-local)
- `design_docs/tasks/TASK-007-parser-fidelity-tabular-residue-and-texttt-math.md` (full)
- `design_docs/decisions/ADR-017-tabular-column-spec-stripping-implementation.md` (full)
- `design_docs/decisions/ADR-018-texttt-as-span-for-mathjax-passthrough.md` (full)
- `design_docs/decisions/ADR-011-tabular-column-spec-handling.md` (full)
- `design_docs/decisions/ADR-003-rendering-pipeline.md` (public function signatures only)
- `design_docs/decisions/ADR-008-navigation-styling-layer.md` (title read via architecture.md summary)
- `design_docs/decisions/ADR-010-playwright-ui-verification.md` (title read via architecture.md summary)
- `design_docs/decisions/ADR-012-callout-title-rendering.md` (title read via architecture.md summary)
- `design_docs/decisions/ADR-013-multi-chapter-validation-harness.md` (full)
- `design_docs/decisions/ADR-015-multi-chapter-triage-discipline.md` (title read via architecture.md summary)
- `design_docs/project_issues/parser-fidelity-tabular-column-spec-residue.md`
- `design_docs/project_issues/parser-fidelity-texttt-traps-inline-math.md`
- `design_docs/audit/TASK-007-parser-fidelity-tabular-residue-and-texttt-math.md` (Runs 001+002)
- `tests/conftest.py`
- `tests/playwright/conftest.py`
- `tests/test_task004_parser_fidelity.py` (full — pattern reference)
- `tests/test_task005_multi_chapter_smoke.py` (full — pattern reference)
- `tests/playwright/test_task004_parser_fidelity_dom.py` (full — Playwright pattern reference)
- `tests/playwright/test_task005_multi_chapter_screenshots.py` (full — Playwright pattern reference)
- `app/parser.py` (function signatures and class names only — NOT implementation bodies)
- `app/static/lecture.css` (existence check only)
- `pyproject.toml` (pytest markers config)

**Tools / commands used:**
- Read on each file above.
- Bash: `ls design_docs/decisions/`, `ls tests/`, `grep -n "^def \|^class " app/parser.py`, `cat pyproject.toml`, `ls tests/playwright/`.
- Write: `tests/test_task007_tabular_residue.py`, `tests/test_task007_texttt_as_span.py`, `tests/playwright/test_task007_tabular_residue_dom.py`.
- Bash: `python3 -m pytest tests/test_task007_tabular_residue.py tests/test_task007_texttt_as_span.py --ignore=tests/playwright -q --no-header` (new-tests-only red confirmation).
- Bash: `python3 -m pytest tests/ --ignore=tests/playwright -q --no-header` (full-suite regression check).
- Write: `design_docs/audit/TASK-007-parser-fidelity-tabular-residue-and-texttt-math.md` (this run entry appended).

**Files created:**
- `tests/test_task007_tabular_residue.py` (198 lines)
- `tests/test_task007_texttt_as_span.py` (229 lines)
- `tests/playwright/test_task007_tabular_residue_dom.py` (207 lines)

**Files modified:**
- `design_docs/audit/TASK-007-parser-fidelity-tabular-residue-and-texttt-math.md` — header Current phase updated to `test`; this Run 003 entry appended.

**Files deleted:** none.

**Tests added (AC mapping):**

ADR-017 / Tabular residue (tests/test_task007_tabular_residue.py):
- `test_no_column_spec_residue_in_first_cell_of_any_table[{12 chapters}]` → AC-1 (all-12 corpus sweep; hot chapters fail RED)
- `test_hot_chapter_no_lccc_at_in_any_cell[{ch-02/03/04}]` → AC-1 (exact `lccc@` corpus residue pattern; ch-04 fails RED)
- `test_hot_chapter_no_p_width_residue_in_any_cell[{ch-02/03/04}]` → AC-2 (p-width residue; ch-04 fails RED)
- `TestTabularBalancedBraceConsumption::test_at_empty_brace_lccc_at_empty_brace_spec_stripped` → AC-1 unit (dominant `@{}lccc@{}` idiom; RED)
- `TestTabularBalancedBraceConsumption::test_at_p_width_p_width_p_width_at_spec_stripped` → AC-2 unit (p{3.4cm}p{5cm}p{4.8cm}; RED)
- `TestTabularBalancedBraceConsumption::test_pipe_vertical_bar_spec_stripped` → ADR-011 boundary
- `TestTabularBalancedBraceConsumption::test_bfseries_modifier_spec_stripped` → ADR-017 edge (`>{...}` nested braces)
- `TestTabularBalancedBraceConsumption::test_single_column_l_spec_stripped` → boundary (single-letter backward compat)
- `TestTabularBalancedBraceConsumption::test_at_empty_groups_flanking_single_letter_spec_stripped` → boundary (`@{}l@{}` brace depth)
- `TestComplexSpecWarningStillFires::test_at_empty_brace_spec_triggers_warning` → AC-2 (warn-per-node for `@{`)
- `TestComplexSpecWarningStillFires::test_p_width_spec_triggers_warning_full_spec` → AC-2 (warn fires on full spec; RED before fix)
- `test_mc6_lecture_source_read_only_no_write_in_parser` → AC-8 (MC-6 static check)
- `test_no_inline_math_inside_code_elements[{12 chapters}]` → AC-3 companion / ADR-018 negative (several chapters RED)

ADR-018 / texttt as span (tests/test_task007_texttt_as_span.py):
- `test_lecture_css_contains_texttt_rule` → AC-4 (CSS static check; RED — rule not yet in lecture.css)
- `test_texttt_hot_chapters_have_span_texttt_elements[{ch-04/09/10}]` → AC-3 structural (RED)
- `test_texttt_hot_chapters_no_bare_inline_code_elements[{ch-04/09/10}]` → AC-3 negative (RED)
- `TestTextttEmitsSpanNotCode::test_texttt_without_math_emits_span_texttt` → boundary unit (RED)
- `TestTextttEmitsSpanNotCode::test_texttt_with_embedded_math_emits_span_with_math_passthrough` → AC-3 unit (exact corpus pattern; RED)
- `TestTextttEmitsSpanNotCode::test_texttt_multiple_math_tokens_all_preserved_in_span` → edge unit (multi-math; RED)
- `TestTextttEmitsSpanNotCode::test_texttt_does_not_emit_code_element_at_all` → negative unit (RED)
- `TestTextttEmitsSpanNotCode::test_texttt_with_html_special_chars_content_escaped` → edge (HTML escaping)
- `TestTextttEmitsSpanNotCode::test_texttt_content_is_preserved_not_empty` → negative (empty span guard)
- `test_ch04_has_texttt_span_with_head_content` → AC-3 (ch-04 "head" ASCII-art; RED)
- `test_all_chapters_render_with_span_texttt_or_no_texttt_usage[{12 chapters}]` → regression (ADR-018 must not break any chapter)

Playwright (tests/playwright/test_task007_tabular_residue_dom.py):
- `test_tabular_first_cell_no_spec_residue[{ch-02/03/04}]` → AC-6(a) Playwright tabular residue
- `test_ch04_first_table_first_cell_has_real_content` → AC-6(a) ch-04 specific
- `test_ch04_texttt_span_contains_mjx_container_after_mathjax` → AC-6(b) / AC-3 (mjx-container inside span)
- `test_ch04_texttt_visible_text_has_no_literal_math_tokens` → AC-3 negative (no `\to` visible after MathJax)
- `test_ch04_texttt_span_has_monospace_computed_font_family` → AC-4 (computed CSS check)
- `test_ch04_texttt_mathjax_screenshot` → AC-6(b) / ADR-010 screenshot artifact

**Coverage matrix:**
- Boundary: `test_at_empty_brace_lccc_at_empty_brace_spec_stripped` (dominant `@{}lccc@{}`), `test_at_p_width_p_width_p_width_at_spec_stripped` (p{3.4cm} x3), `test_pipe_vertical_bar_spec_stripped` (|c|c|c|), `test_single_column_l_spec_stripped` (single letter), `test_at_empty_groups_flanking_single_letter_spec_stripped` (`@{}l@{}`), `test_hot_chapter_no_lccc_at_in_any_cell` (ch-02/03/04 hot spots), ADR-011 boundary from TASK-004 preserved.
- Edge: `test_bfseries_modifier_spec_stripped` (`>{...}` nested braces), `test_texttt_with_html_special_chars_content_escaped` (HTML-special chars), `test_texttt_multiple_math_tokens_all_preserved_in_span` (multi-math sequence), `test_at_empty_groups_flanking_single_letter_spec_stripped` (position effects), `test_ch04_texttt_span_contains_mjx_container_after_mathjax` (post-MathJax DOM state), `test_all_chapters_render_with_span_texttt_or_no_texttt_usage` (all 12 chapters for regression).
- Negative: `test_no_column_spec_residue_in_first_cell_of_any_table` (all 12 chapters), `test_hot_chapter_no_lccc_at_in_any_cell`, `test_hot_chapter_no_p_width_residue_in_any_cell`, `test_no_inline_math_inside_code_elements`, `test_texttt_hot_chapters_no_bare_inline_code_elements`, `TestTextttEmitsSpanNotCode::test_texttt_does_not_emit_code_element_at_all`, `test_mc6_lecture_source_read_only_no_write_in_parser`, `test_ch04_texttt_visible_text_has_no_literal_math_tokens` (no `\to` literal post-MathJax).
- Performance: skipped for tabular/texttt unit tests (fixed-size single-unit inputs, no scaling surface). The 12-chapter HTTP time budget is covered by the inherited TASK-005 `test_all_chapters_respond_within_time_budget` test which re-runs with the new parser code. Playwright page-load budget covered by TASK-005 `test_all_chapter_screenshots_under_time_budget`.

**Pytest red result:** Collected (new tests only): 65. Failing: 25. Passing: 40.
Full suite (excluding Playwright): Collected: 308. Failing: 25 (all new TASK-007 tests). Passing: 283 (all pre-existing tests pass — zero regressions).

**Failing tests (RED — prove implementation is needed):**
- `test_no_column_spec_residue_in_first_cell_of_any_table[ch-02...]` (confirms ch-02 tabular residue present)
- `test_no_column_spec_residue_in_first_cell_of_any_table[ch-03...]` (confirms ch-03 tabular residue present)
- `test_no_column_spec_residue_in_first_cell_of_any_table[ch-04...]` (confirms ch-04 tabular residue present)
- `test_no_column_spec_residue_in_first_cell_of_any_table[ch-10...]` (ch-10 also has residue — unexpected; noted)
- `test_hot_chapter_no_lccc_at_in_any_cell[ch-04...]`
- `test_hot_chapter_no_p_width_residue_in_any_cell[ch-04...]`
- `TestTabularBalancedBraceConsumption::test_at_empty_brace_lccc_at_empty_brace_spec_stripped`
- `TestTabularBalancedBraceConsumption::test_at_p_width_p_width_p_width_at_spec_stripped`
- `TestComplexSpecWarningStillFires::test_p_width_spec_triggers_warning_full_spec`
- `test_no_inline_math_inside_code_elements[ch-03/04/07/10]` (4 chapters)
- `test_lecture_css_contains_texttt_rule`
- `test_texttt_hot_chapters_have_span_texttt_elements[ch-04/09/10]`
- `test_texttt_hot_chapters_no_bare_inline_code_elements[ch-04/09/10]`
- `TestTextttEmitsSpanNotCode::test_texttt_without_math_emits_span_texttt`
- `TestTextttEmitsSpanNotCode::test_texttt_with_embedded_math_emits_span_with_math_passthrough`
- `TestTextttEmitsSpanNotCode::test_texttt_multiple_math_tokens_all_preserved_in_span`
- `TestTextttEmitsSpanNotCode::test_texttt_does_not_emit_code_element_at_all`
- `test_ch04_has_texttt_span_with_head_content`

**Assumptions:**
- ASSUMPTION: `_extract_first_cells_of_all_tables()` in the test helper correctly identifies first cells via regex on the HTTP response body. This is a structural HTML parse, not a DOM query — it may miss edge cases where `<tr>` spans are inside nested `<table>` elements inside the first row. Acceptable for the HTTP smoke layer; the Playwright layer validates the DOM directly.
- ASSUMPTION: ch-10 (ch-10-graphs) has tabular residue not documented in Run 008's hot-chapter list (which named ch-02/03/04). The failing test for ch-10 surfaced this. The ADR-017 fix will cover ch-10 as well (balanced-brace consumption applies to all chapters). No AC change required; the test correctly catches the wider impact.
- ASSUMPTION: AC-7 (human screenshot re-review of the TASK-005 12-chapter harness) is a human-gate item, not an automated assertion. It is not tested in this file. The Playwright screenshot tests (ADR-010) cover the automated artifact production; human review is a separate gate recorded in the Human gates table.

**CANNOT TEST:**
- AC-7: "when Playwright tests run, the human re-runs the TASK-005 12-Chapter screenshot harness and reviews fresh last-run screenshots to confirm visible-defect reduction." This is a human-eyeball gate by definition (ADR-010). The automated artifact production is tested; the human-review step is a Human gates table entry, not a pytest assertion.
- AC-9 ("both target project_issues are resolved"): the project_issue files have already been flipped to "Resolved by ADR-017/ADR-018" in Run 002. A static file-content test would trivially pass before implementation (the files already say "Resolved"). The meaningful check is that the ADRs are Accepted (recorded in the Human gates table) and that the implementation makes the functional tests pass. No separate "project_issue status" test added.

**Architecture leaks found:** none. All `.md` files read classified correctly per the CLAUDE.md tier table. ADR-017 and ADR-018 are both Accepted (per Human gates table). `architecture.md` is index-only. No `.md` file introduced an architectural claim outside an Accepted ADR.

**Pushback raised:** none. The ACs are specific and testable. The one structural weakness found (AC-7 is a human-gate item) is documented under CANNOT TEST above — no pushback required. No MANIFEST TENSION, no ADR flaw, no task/ADR conflict found.

### Run 004 — implementer / `/implement` TASK-007

**Time:** 2026-05-09T04:00:00Z

**Input files read:**
- `design_docs/MANIFEST.md`
- `CLAUDE.md`
- `design_docs/architecture.md`
- `.claude/skills/manifest-conformance/SKILL.md`
- `design_docs/tasks/TASK-007-parser-fidelity-tabular-residue-and-texttt-math.md`
- `design_docs/audit/TASK-007-parser-fidelity-tabular-residue-and-texttt-math.md` (Runs 001–003)
- `design_docs/decisions/ADR-017-tabular-column-spec-stripping-implementation.md` (full)
- `design_docs/decisions/ADR-018-texttt-as-span-for-mathjax-passthrough.md` (full)
- `tests/test_task007_tabular_residue.py` (full)
- `tests/test_task007_texttt_as_span.py` (full)
- `tests/playwright/test_task007_tabular_residue_dom.py` (full)
- `app/parser.py` (full)
- `app/static/lecture.css` (full)

**Tools / commands used:**
- Read on each file in the input list above.
- Edit: `app/parser.py` (two changes: texttt handler + `_render_tabular` balanced-brace).
- Edit: `app/static/lecture.css` (added `.texttt` rule).
- Bash: `python3 -m pytest tests/ --ignore=tests/playwright -q --no-header` (308 passed).
- Bash: `python3 -m pytest tests/playwright/ -q --no-header` (152 passed).
- Bash: `python3 -m pytest tests/ -q --no-header` (full suite, 460 passed).
- Bash: `uvicorn app.main:app --host 127.0.0.1 --port 8765` (dev server, manual end-to-end).
- Bash: curl loop across all 12 chapter IDs (HTTP status + tabular-residue grep + texttt-math-trap grep).
- Bash: `git diff --stat HEAD` (confirmed code-change footprint).
- Bash: `grep -n "open\|write" app/parser.py | grep -i "content/latex\|CONTENT_ROOT"` (MC-6 static check, empty output = pass).
- Bash: `ls tests/playwright/artifacts/` (screenshot artifact count: 165 items including 12 chapter screenshots + task007-ch04-texttt-mathjax.png).
- Edit: `design_docs/audit/TASK-007-parser-fidelity-tabular-residue-and-texttt-math.md` (header update + this run entry).

**Files created:** none.

**Files modified:**
- `app/parser.py` — (1) `_convert_inline_latex`: `\texttt{}` handler changed from `<code>` to `<span class="texttt">` (ADR-018); (2) added `_consume_balanced_brace_arg()` helper function (ADR-017); (3) `_render_tabular`: replaced `[^}]*` regex extraction with two-step balanced-brace consumption using `_consume_balanced_brace_arg()` (ADR-017).
- `app/static/lecture.css` — added `.texttt` rule with `font-family: 'Courier New', Courier, monospace; background: #f3ede2; padding: 0.1em 0.3em; border-radius: 2px; font-size: 0.9em;` reproducing existing `p code` styling (ADR-018).
- `design_docs/audit/TASK-007-parser-fidelity-tabular-residue-and-texttt-math.md` — header Status `In progress` → `Implemented`; Current phase `implementer` → `verify`; this Run 004 entry appended.

**Files explicitly NOT modified:** `tests/test_task007_tabular_residue.py`, `tests/test_task007_texttt_as_span.py`, `tests/playwright/test_task007_tabular_residue_dom.py`, `design_docs/MANIFEST.md`, `design_docs/architecture.md`, `design_docs/decisions/**`, `CLAUDE.md`, `.claude/skills/manifest-conformance/SKILL.md`.

**Implementation decisions made (local only — no architectural scope):**
- `_consume_balanced_brace_arg()` implemented as a simple character-by-character loop (not a recursive regex or pylatexenc structured access). ADR-017 §Decision explicitly says "the architectural commitment is on the semantic, not on the syntactic shape of the matcher." The loop is the simplest correct implementation.
- For the `\begin{array}{...}` case in `_render_tabular`, extended the `begin_marker` fallback to try `\begin{array}{` if `\begin{tabular}{` is not found. This is a pre-existing code path (line 805: `elif env_name in ("tabular", "table", "table*", "array")`) and the old regex already handled array. The balanced-brace scan now handles it identically.
- The `end_marker_m` search uses `re.search` on the tail of `raw` from `body_start_pos` to avoid re-scanning the spec portion. This is equivalent in correctness to the old `.*?\\end{tabular}` group in the original regex.

**Tests run:**
- `python3 -m pytest tests/ --ignore=tests/playwright -q --no-header`: **308 passed** (pre-implementation: 283 passing 25 failing; post: 308 passing 0 failing).
- `python3 -m pytest tests/playwright/ -q --no-header`: **152 passed**.
- `python3 -m pytest tests/ -q --no-header` (full suite): **460 passed, 0 failed**.

**Lint / type-check:** skipped — placeholders in `CLAUDE.md` ("Commands" section: `<project lint command>`, `<project type-check command>`). No lint/type-check tooling is configured (project-setup gap surfaced in TASK-005 audit Run 007 and TASK-007 task file "Architectural concerns"; requires its own `/design` cycle if commissioned).

**Conformance result:** 0 blockers, 0 warnings, 10 dormant (MC-1 architecture portion, MC-3 architecture portion, MC-6 architecture portion, MC-10 fully dormant — all pending ADRs that name the specific paths/packages). Manifest-active portions of all rules: PASS. MC-6 static grep: `grep -n "open\|write" app/parser.py | grep -i "content/latex\|CONTENT_ROOT"` returned empty — no write path to lecture source root.

**End-to-end verification:**
- Dev server: `uvicorn app.main:app --host 127.0.0.1 --port 8765`.
- HTTP status: 12/12 chapters returned HTTP 200.
- Tabular residue (`lccc@`, `p3.4cm`, `p5cm`, `p4.8cm@`, `p3.4cmp5cm` patterns outside code blocks): **0/12 chapters** have any residue. Pre-fix, ch-02/03/04/10 had confirmed residue; post-fix, all clean.
- texttt math trap (`<code>...$...$...</code>` patterns): **0/12 chapters** have any inline `<code>` with math tokens. Pre-fix, ch-04/09/10 had confirmed math-in-code instances; post-fix, all clean.
- `<span class="texttt">` counts in hot chapters: ch-04: 699, ch-09: 137, ch-10: 91.
- Screenshot artifacts: 165 files in `tests/playwright/artifacts/`, including 12 chapter screenshots + `task007-ch04-texttt-mathjax.png` (new artifact from Playwright TASK-007 test).

**Bug-class classifications for new failures surfaced during verify:** none. No new failures emerged in any of the three test layers (unit, smoke, Playwright).

**Adjacent bugs surfaced (not fixed):** none observed during this verify pass. The three open project_issues (`parser-fidelity-unhandled-environments-and-text-macros.md`, `parser-fidelity-body-linebreak-and-display-math.md`, `ch06-textbackslash-double-renders-as-double-backslash.md`) remain open per TASK-007 task file "Out of scope"; they were not touched and remain as-is.

**Pushback raised:** none. Markdown critique pass: no architecture leaks detected in any `.md` file read. All ADR-017 and ADR-018 claims are backed by Accepted ADRs. No manifest tension. No test assertion flaws. No ADR contradictions.


### Run 005 — orchestrator / verify (corroborating implementer Run 004)

**Time:** 2026-05-09T00:00:00Z
**Trigger:** Per ADR-016 orchestrator-verification protocol — independently corroborate implementer Run 004's end-to-end claims and run the manifest-conformance walk before reporting `/implement` complete to the human.

**Input files read:** `git diff` of `app/parser.py` and `app/static/lecture.css` (verify scope is exactly the two expected files; no template/discovery/main edits like the TASK-005 Run 006 incident).

**Tools / commands used:** Bash (`git status --short`, `git diff --stat app/parser.py app/static/lecture.css`, `git diff --name-only HEAD app/`, `uvicorn` background server on :8765, `curl` × 12 for HTTP-200 sweep, `python3` regex sweeps for tabular-residue and `<code>+$...$+</code>` patterns, `grep` for `<span class="texttt">` counts in hot Chapters), Skill (`manifest-conformance` against working tree).

**Files modified by orchestrator:** none (this run verifies only; no code or test changes).

**ADR-016 verification — file-scope check:**
- Expected: `app/parser.py` (ADR-017 + ADR-018 handler changes) and `app/static/lecture.css` (ADR-018 rule) only.
- Actual: `app/parser.py` (+59 / -6) and `app/static/lecture.css` (+12 / -0). No template / discovery / main / config edits. **Scope clean. No unauthorized class-3 edits.**

**Independent end-to-end corroboration (uvicorn :8765, all 12 Chapters):**
- HTTP 200: **12/12** (matches implementer's claim).
- Tabular residue (first cell of every table starts with column-spec textual content like `lccc@`, `p\d+(\.\d+)?cm`, `[lcr@|]+@?`): **0/12** (matches; pre-fix was 4/12 with ~53 instances per Run 008 evidence).
- `<code>...$...$...</code>` math-trap pattern: **0/12** (matches; pre-fix had ~42 instances per Run 008).
- `<span class="texttt">` emission counts in hot Chapters: ch-04 = 699 elements, ch-09 = 137, ch-10 = 91. The parser is now emitting the new shape at corpus scale.

**Conformance walk (`manifest-conformance` skill against working tree):**
- 0 blockers, 0 warnings, 1 dormant (MC-10 persistence-layer ADR pending — unchanged from prior runs).
- No violations.

**Architecture leaks found:** none.
**PUSHBACK / ESCALATION / MANIFEST TENSION raised:** none.

**Conformance check (orchestrator at write time):**
- audit-append-only skill: TASK-007 audit was appended with Run 005. No prior run entries rewritten.
- authority-state-check skill: ADR-017 / ADR-018 remain `Accepted`; architecture.md Accepted ADRs table contains both rows; project_issues marked `Resolved by ADR-NNN (Accepted 2026-05-09)`. No drift.
- ADR-016 verification step caught no failures this round (implementer scope was clean).

**Output summary:** TASK-007 implement+verify phase complete. ADR-017 (tabular balanced-brace consumption) and ADR-018 (`\texttt{}` → `<span class="texttt">` + CSS rule) both shipped. Pytest 460/460 green; 12/12 HTTP 200; 0/12 tabular residue; 0/12 code+math trap. Manifest-conformance walk clean. Implementer's scope was strictly the two expected files (`app/parser.py` + `app/static/lecture.css`) — no class-3 silent edits this round. Ready for human screenshot review (ADR-010 gate) and reviewer subagent invocation against the diff before commit.

### Run 006 — reviewer / pre-commit review

**Time:** 2026-05-09T14:00:00Z
**Trigger:** Pre-commit reviewer pass per CLAUDE.md "Pushback protocol" and reviewer-agent standing protocol. Nothing staged yet — review covers all changes since `149d49c` (`git diff HEAD` + untracked).

**Input files read:**
- `git status --short`, `git diff HEAD --stat`, `git diff HEAD -- app/parser.py app/static/lecture.css design_docs/architecture.md design_docs/project_issues/parser-fidelity-tabular-column-spec-residue.md design_docs/project_issues/parser-fidelity-texttt-traps-inline-math.md`
- `design_docs/decisions/ADR-017-tabular-column-spec-stripping-implementation.md` (full)
- `design_docs/decisions/ADR-018-texttt-as-span-for-mathjax-passthrough.md` (full)
- `design_docs/tasks/TASK-007-parser-fidelity-tabular-residue-and-texttt-math.md` (full)
- `design_docs/audit/TASK-007-parser-fidelity-tabular-residue-and-texttt-math.md` (Runs 001–005)
- `design_docs/architecture.md`
- `.claude/skills/manifest-conformance/SKILL.md`
- `app/parser.py` lines 130–305 (texttt handler + neighbors), 340–460 (`_warn_complex_col_spec` + `_consume_balanced_brace_arg` + `_render_tabular`), 681–890 (`_nodes_to_html` to confirm there is no second texttt handler), 912–931 (`_render_callout_title_html` to confirm callout-title path routes through `_convert_inline_latex`)
- `tests/test_task007_tabular_residue.py` (full)
- `tests/test_task007_texttt_as_span.py` (full)
- `tests/playwright/test_task007_tabular_residue_dom.py` (full)

**Tools / commands used:**
- `git status --short`, `git diff HEAD --stat`, `git diff HEAD -- <file>` × 5
- `grep -n "texttt" app/parser.py`, `grep -n "_nodes_to_html|_convert_inline_latex" app/parser.py`, `grep -rn "<code>" app/parser.py`
- `ls tests/playwright/artifacts/`, `cat .gitignore` (verified screenshots are gitignored per ADR-010)

**Files modified by reviewer:** none (review-only). This audit Run 006 entry is the only append.

**Unstaged source/test warning:** N/A — nothing staged at review time; reviewing the full delta vs. `HEAD`.

**Conformance skill result (manual walk against the diff):** **0 blockers, 0 warnings, 1 dormant.**
- MC-1 (no LLM SDK): not touched by diff. Manifest portion: PASS.
- MC-2 (Quizzes scope to one Section): not touched.
- MC-3 (M/O designation): not touched.
- MC-4 (AI work async): not touched.
- MC-5 (AI failures surfaced): not touched.
- MC-6 (Lecture source read-only): **PASS** (manifest portion). Diff edits `app/parser.py` and `app/static/lecture.css`; no path under `content/latex/` is touched. Test-suite static check `test_mc6_lecture_source_read_only_no_write_in_parser` passes. Architecture portion (path-specific) remains dormant pending source-layout ADR.
- MC-7 (single user): not touched.
- MC-8 (reinforcement loop): not touched.
- MC-9 (user-triggered Quiz): not touched.
- MC-10 (persistence boundary): dormant (persistence-layer ADR pending) — unchanged.

**Architecture leaks found in .md files:** none.
- ADR-017 and ADR-018: both `Status: Accepted` with proper acceptance rationale and dated acceptance line; no architectural claim outside the ADRs themselves.
- `architecture.md`: index-only; both ADRs added to Accepted table; "Proposed" empty; project-structure summary unchanged (correctly, since neither ADR introduces a new structural claim — ADR-017 implements ADR-011's existing contract; ADR-018 sits inside ADR-003 and ADR-008's existing scopes).
- Project_issue updates: status flipped to `Resolved by ADR-NNN (Accepted 2026-05-09)`. Stale "Proposed; contingent on acceptance" text from Run 002 has been replaced with the accepted-date variant (verified in the diff).

**Per-ADR fidelity:**
- **ADR-017 (balanced-brace consumption):** `_consume_balanced_brace_arg()` at `app/parser.py:376–406` implements the depth-counter scan exactly as specified (start at 1; +1 on `{`; −1 on `}`; terminate at 0). `_render_tabular` at `app/parser.py:409–446` uses the helper to capture the spec, then locates `\end{tabular|array}` for the body boundary and passes the full spec to `_warn_complex_col_spec`. Handles `@{}lccc@{}`, `p{3.4cm}`, `>{...}`, `<{...}` per ADR-017 §Decision. `\begin{array}{` fallback preserved. Correct.
- **ADR-018 (texttt-as-span):** Single rendering path. `app/parser.py:147–148` emits `<span class="texttt">{get_arg_html(0)}</span>`. The reviewer brief mentioned "both `\texttt{}` rendering paths (`_nodes_to_html` AND `_convert_inline_latex`)" — that brief was inaccurate; `_nodes_to_html` does not have its own `texttt` branch, it routes inline content through `_convert_inline_latex` via `flush_para()` (line 697). Callout titles route through `_render_callout_title_html → _convert_inline_latex` (line 928), so `\texttt{}` inside callout titles also gets the span. No `<code>` remains for `\texttt{}` anywhere; the four `<code>` references in `app/parser.py` are all inside `<pre><code>...</code></pre>` blocks for verbatim/lstlisting (lines 226, 231, 802, 812). `lecture.css:157–166` carries the `.texttt` rule with `font-family: 'Courier New', Courier, monospace; background: #f3ede2; padding: 0.1em 0.3em; border-radius: 2px; font-size: 0.9em;` — matches ADR-018 §Decision exactly and lives in `lecture.css` not `base.css` per ADR-008.

**Per-AC status (TASK-007):**
- AC-1 (no `lccc@`/`p3.4cm` in any rendered cell): **PASS** — Run 005 corpus sweep 0/12 chapters; smoke test `test_no_column_spec_residue_in_first_cell_of_any_table` parameterized across all 12 chapters passes; Playwright `test_tabular_first_cell_no_spec_residue` parameterized across hot chapters passes.
- AC-2 (p{width} stripped + warn-per-node fires on full spec): **PASS** — `TestComplexSpecWarningStillFires::test_p_width_spec_triggers_warning_full_spec` passes (this was RED pre-fix because `[^}]*` truncated the spec before `p{` was reached; ADR-017 fixes that).
- AC-3 (mjx-container inside texttt span; no literal $...$ visible): **PASS** — Playwright `test_ch04_texttt_span_contains_mjx_container_after_mathjax` passes; `test_ch04_texttt_visible_text_has_no_literal_math_tokens` passes; HTTP-level `test_no_inline_math_inside_code_elements` parameterized across 12 chapters passes.
- AC-4 (computed font-family includes monospace/Courier on `.texttt`): **PASS** — Playwright `test_ch04_texttt_span_has_monospace_computed_font_family` passes via `getComputedStyle`.
- AC-5 (no regressions in TASK-001/003/004/005 tests): **PASS** — Run 004 reports 460/460 green; Run 005 corroborates.
- AC-6(a) tabular Playwright + AC-6(b) ch-04 mjx Playwright: **PASS** — both tests in `test_task007_tabular_residue_dom.py`; screenshot artifact `task007-ch04-texttt-mathjax.png` produced.
- AC-7 (human re-runs 12-chapter screenshot harness + reviews fresh artifacts): **HUMAN-GATE PENDING** — automated artifact production verified (165 files in `tests/playwright/artifacts/`); the human-eyeball pass is the next gate after this review.
- AC-8 (MC-6 PASS, no new blockers): **PASS** — confirmed above.
- AC-9 (project_issues resolved): **PASS** — both flipped to `Resolved by ADR-NNN (Accepted 2026-05-09)`.

**Test honesty check:**
- The 25 pre-implementation-RED tests exercise behavior, not pass-by-existence: they import `parse_latex` and assert on rendered HTML / log records / DOM structure. Each had a RED-before-GREEN-after profile in Run 003 → Run 004.
- Playwright `<mjx-container>` assertion uses `wait_for_load_state("networkidle", timeout=30_000)` in `test_ch04_texttt_span_contains_mjx_container_after_mathjax` — MathJax has time to run; the assertion is real.
- `test_lecture_css_contains_texttt_rule` is a static file check, but it actually opens the file and regex-matches the rule body for `monospace` or `Courier` — not pass-by-mere-existence.
- No tautological asserts spotted (e.g., asserting on always-present attributes).

**Approach observations:**
- ADR-017 picked separate-ADR over Resolution-note-on-ADR-011. Substance is identical; the procedural choice is consistent with the project's "in-place edits to Accepted ADRs erase chronology" discipline. Reviewer concurs.
- ADR-018's CSS rule reproduces the existing `p code` look so cap-on-cap visual continuity holds. Sensible default; the human can shrink it later if desired.
- The brief mentioned "both `\texttt{}` rendering paths" — only one exists; the implementer correctly changed the single site. Not a defect.
- Balanced-brace logic does not skip backslash-escaped `\{` / `\}`, but ADR-017 §Consequences flags this as "no corpus instance currently exists" — bounded mitigation acceptable.

**Diff hygiene:**
- Footprint matches Run 005's ADR-016 file-scope check: `app/parser.py` (+59 / −6), `app/static/lecture.css` (+12 / 0). No template / discovery / main / config edits.
- Untracked: 2 ADRs, 1 task, 1 audit, 3 test files. All expected.
- No editor / IDE artifacts; no secrets; no large binaries (screenshots gitignored per ADR-010).
- No stray edits outside scope. The TASK-005 Run 006 unauthorized-template-edit incident did not recur.

**Blocking findings:** none.

**Non-blocking findings:**
- ADR-017 §Consequences notes that backslash-escaped braces inside specs (e.g., `\{`, `\}`) would overcount. No corpus instance exists today; mitigation is documented. Surface here so a future architect cycle (if a new chapter introduces escaped braces) knows the supersedure trigger.
- The reviewer-brief sentence about "both `\texttt{}` rendering paths" was inaccurate; only one path exists. Worth correcting in any future reviewer-brief boilerplate so the next pass doesn't waste time looking for a second site.

**Final result:** READY TO COMMIT
