# LLM Audit — TASK-004: Fix parser fidelity — strip tabular column specs and render callout titles

**Task file:** `design_docs/tasks/TASK-004-parser-fidelity-tabular-callout-titles.md`
**Started:** 2026-05-08T00:00:00Z
**Status:** Implemented
**Current phase:** verify

---

## Human gates

| Time | Gate | Result | Notes |
|---|---|---|---|
| 2026-05-08 | Task reviewed | accepted | TASK-004 accepted as proposed; proceed to /design |
| 2026-05-08 | ADR-011 reviewed | accepted | Tabular column spec handling — strip + warn |
| 2026-05-08 | ADR-012 reviewed | accepted | Callout title rendering — emit as div.callout-title |

---

## Agent runs

### Run 001 — architect / Mode 1 `/next`

**Time:** 2026-05-08T00:00:00Z
**Input files read:**
- `design_docs/MANIFEST.md`
- `CLAUDE.md`
- `design_docs/architecture.md`
- `.claude/skills/manifest-conformance/SKILL.md`
- `design_docs/decisions/ADR-001-lecture-source-layout.md`
- `design_docs/decisions/ADR-002-chapter-and-section-identity.md`
- `design_docs/decisions/ADR-003-rendering-pipeline.md`
- `design_docs/decisions/ADR-004-mandatory-optional-designation-source.md`
- `design_docs/decisions/ADR-005-chapter-source-file-naming.md`
- `design_docs/decisions/ADR-008-navigation-styling-layer.md`
- `design_docs/decisions/ADR-010-playwright-ui-verification.md`
- `design_docs/tasks/TASK-003-style-navigation-surface.md`
- `design_docs/project_issues/multi-chapter-source-naming.md`
- `design_docs/project_issues/adr006-rail-half-implemented-no-css.md`
- `design_docs/project_issues/latex-tabular-column-spec-passthrough.md`
- `design_docs/project_issues/latex-callout-title-arg-passthrough.md`
- `design_docs/audit/TASK-003-style-navigation-surface.md` (header only)
- `app/main.py`
- `app/config.py`
- `app/discovery.py` (header only)

**Tools / commands used:** Read (all files above), Glob (design_docs/decisions, tasks, project_issues — ripgrep ENOENT, fell back to direct file reads)
**Files created:** `design_docs/tasks/TASK-004-parser-fidelity-tabular-callout-titles.md`, `design_docs/audit/TASK-004-parser-fidelity-tabular-callout-titles.md`
**Files modified:** none
**Task alternatives considered:**
- (Chosen) Fix both parser fidelity bugs (tabular + callout titles) in one task
- Fix only tabular bug; defer callout titles — rejected (same file, same pattern, marginal scope savings)
- Skip fidelity fixes; go to multi-chapter validation — rejected (validates with known bugs, degrades review quality)
- Jump to Notes/Quiz features — rejected (builds on cracked rendering foundation)
**Decisions surfaced:** Possible ADR for callout-title IR shape (depends on `/design` assessment); possible ADR for tabular handling strategy; both may stay within ADR-003's latitude
**Architecture leaks found:** none
**Pushback raised:** none
**Output summary:** Proposed TASK-004 to fix two parser fidelity bugs (tabular column spec passthrough, callout title passthrough) surfaced during TASK-003 screenshot review; resolves both open project issues.

### Run 002 — architect / Mode 2 `/design`

**Time:** 2026-05-08T12:00:00Z
**Input files read:**
- `design_docs/MANIFEST.md`
- `CLAUDE.md`
- `design_docs/architecture.md`
- `.claude/skills/manifest-conformance/SKILL.md`
- `design_docs/decisions/ADR-001-lecture-source-layout.md` (header)
- `design_docs/decisions/ADR-003-rendering-pipeline.md`
- `design_docs/decisions/ADR-008-navigation-styling-layer.md`
- `design_docs/decisions/ADR-010-playwright-ui-verification.md`
- `design_docs/tasks/TASK-004-parser-fidelity-tabular-callout-titles.md`
- `design_docs/project_issues/latex-tabular-column-spec-passthrough.md`
- `design_docs/project_issues/latex-callout-title-arg-passthrough.md`
- `app/parser.py`
- `app/templates/lecture.html.j2`
- `app/static/lecture.css`
- `design_docs/audit/TASK-004-parser-fidelity-tabular-callout-titles.md`

**Tools / commands used:** Read (all files above)
**Files created:** none
**Files modified:**
- `design_docs/project_issues/latex-tabular-column-spec-passthrough.md` — Status changed from Open to Resolved by TASK-004; Resolution section filled
- `design_docs/project_issues/latex-callout-title-arg-passthrough.md` — Status changed from Open to Resolved by TASK-004; Resolution section filled
- `design_docs/audit/TASK-004-parser-fidelity-tabular-callout-titles.md` — header updated (phase: design), Run 002 appended
**ADRs proposed:** none — both decisions are within ADR-003's existing latitude
**Project issues opened/resolved:**
- `latex-tabular-column-spec-passthrough` — resolved (within ADR-003 latitude)
- `latex-callout-title-arg-passthrough` — resolved (within ADR-003 latitude)
**architecture.md changes:** none (no new ADRs)
**Architecture leaks found:** none
**Pushback raised:** none
**Implementation blocked pending human acceptance:** no — no new ADRs; both fixes operate within ADR-003's Accepted latitude
**Output summary:** Both decisions (tabular column spec handling, callout title rendering) fall within ADR-003's "extend environment-specific handlers" latitude. No new ADRs needed. Tabular: strip-and-ignore with warn-per-node for complex spec features. Callout titles: parser handler emits title as `<div class="callout-title">` directly in HTML (existing pattern in `_nodes_to_html` + existing CSS rule); fix the extraction logic and ensure inline path also handles titles. Both project issues marked resolved.

### Run 003 — architect / Mode 2 `/design` (ADR creation per human pushback)

**Time:** 2026-05-08T18:00:00Z
**Input files read:**
- `design_docs/MANIFEST.md`
- `CLAUDE.md`
- `design_docs/architecture.md`
- `.claude/skills/manifest-conformance/SKILL.md`
- `design_docs/decisions/ADR-003-rendering-pipeline.md`
- `design_docs/decisions/ADR-008-navigation-styling-layer.md`
- `design_docs/decisions/ADR-010-playwright-ui-verification.md`
- `design_docs/tasks/TASK-004-parser-fidelity-tabular-callout-titles.md`
- `design_docs/project_issues/latex-tabular-column-spec-passthrough.md`
- `design_docs/project_issues/latex-callout-title-arg-passthrough.md`
- `app/parser.py`
- `app/static/lecture.css`
- `design_docs/audit/TASK-004-parser-fidelity-tabular-callout-titles.md`

**Tools / commands used:** Read (all files above), Write (ADR-011, ADR-012), Edit (architecture.md, both project issue files, task file, audit file)
**Files created:**
- `design_docs/decisions/ADR-011-tabular-column-spec-handling.md`
- `design_docs/decisions/ADR-012-callout-title-rendering.md`
**Files modified:**
- `design_docs/architecture.md` — added ADR-011 and ADR-012 rows to Proposed ADRs table
- `design_docs/project_issues/latex-tabular-column-spec-passthrough.md` — Status changed from "Resolved by TASK-004 (within ADR-003 latitude)" to "Resolved by ADR-011 (pending acceptance)"; Resolution section updated to reference ADR-011
- `design_docs/project_issues/latex-callout-title-arg-passthrough.md` — Status changed from "Resolved by TASK-004 (within ADR-003 latitude)" to "Resolved by ADR-012 (pending acceptance)"; Resolution section updated to reference ADR-012
- `design_docs/tasks/TASK-004-parser-fidelity-tabular-callout-titles.md` — "Architectural decisions expected" section updated to reference ADR-011 and ADR-012; "Verify" section updated to reference specific ADR numbers
- `design_docs/audit/TASK-004-parser-fidelity-tabular-callout-titles.md` — header Status changed to Blocked; Run 003 appended
**ADRs proposed:**
- `ADR-011` — Strip tabular column spec from rendered output; warn-per-node for complex spec features
- `ADR-012` — Extract callout `[Title]` optional argument and emit as `<div class="callout-title">` inside callout div
**Project issues opened/resolved:**
- `latex-tabular-column-spec-passthrough` — resolved by ADR-011 (pending acceptance)
- `latex-callout-title-arg-passthrough` — resolved by ADR-012 (pending acceptance)
**architecture.md changes:** Two rows added to Proposed ADRs table (ADR-011, ADR-012)
**Architecture leaks found:** none
**Pushback raised:** none — this run responds to the human's pushback on Run 002 (decisions should be formal ADRs, not resolved within ADR-003's latitude)
**Implementation blocked pending human acceptance:** yes — ADR-011 and ADR-012 are both `Proposed`; `/implement` cannot proceed until the human accepts both
**Output summary:** Created ADR-011 (tabular column spec handling) and ADR-012 (callout title rendering) as formal Proposed ADRs per human pushback. Updated project issues, architecture.md, task file, and audit file to reference the new ADRs. Implementation is blocked pending human acceptance of both ADRs.

### Run 004 — test-writer

**Time:** 2026-05-08T00:00:00Z
**Input files read:**
- `design_docs/MANIFEST.md`
- `CLAUDE.md`
- `design_docs/architecture.md`
- `design_docs/decisions/ADR-011-tabular-column-spec-handling.md`
- `design_docs/decisions/ADR-012-callout-title-rendering.md`
- `tests/conftest.py`
- `tests/playwright/conftest.py`
- `tests/test_task001_rendering_fidelity.py`
- `tests/playwright/test_task001_rendering_fidelity_dom.py`
- `tests/playwright/test_task003_navigation_styling.py`
- `tests/test_task002_navigation.py` (header)
- `tests/fixtures/latex_minimal/ch-01-arrays.tex`
- `app/parser.py` (public function signatures only — offset 0, limit 60 and grep of `^def|^class`)
- `pyproject.toml`
- `design_docs/audit/TASK-004-parser-fidelity-tabular-callout-titles.md`
- `content/latex/ch-01-cpp-refresher.tex` (grep for tabular specs and titled callouts)

**Tools / commands used:** Read, Bash (ls, grep for tabular/callout lines), Write (two new test files), Bash (pytest runs)
**Files created:**
- `tests/test_task004_parser_fidelity.py`
- `tests/playwright/test_task004_parser_fidelity_dom.py`
**Files modified:** none (marker `task(id)` was already registered in `pyproject.toml`)
**Tests added:**
- `TestTabularColumnSpecStripped::test_simple_lll_spec_not_in_rendered_html` → AC-1
- `TestTabularColumnSpecStripped::test_data_rows_still_rendered_after_spec_strip` → AC-1 (data not dropped)
- `TestTabularColumnSpecStripped::test_simple_ll_spec_not_in_rendered_html` → AC-1 boundary
- `TestTabularColumnSpecStripped::test_lcr_mixed_simple_spec_not_in_rendered_html` → AC-1 boundary
- `TestTabularColumnSpecStripped::test_ch01_tabular_lll_not_in_rendered_html` → AC-1 end-to-end
- `TestTabularColumnSpecStripped::test_tabular_inside_callout_spec_not_in_rendered_html` → AC-1 edge (nesting)
- `TestTabularComplexSpecWarning::test_pipe_spec_not_visible_in_output` → AC-2 (no text)
- `TestTabularComplexSpecWarning::test_pipe_spec_triggers_warning_log` → AC-2 (warning log)
- `TestTabularComplexSpecWarning::test_p_width_spec_not_visible_in_output` → AC-2 boundary
- `TestTabularComplexSpecWarning::test_p_width_spec_triggers_warning_log` → AC-2 boundary (warning log)
- `TestTabularComplexSpecWarning::test_at_spec_not_visible_in_output` → AC-2 boundary (@{})
- `TestTabularComplexSpecWarning::test_simple_lrc_does_not_trigger_warning` → AC-2 negative (no spurious warn)
- `TestCalloutTitleRendering::test_ideabox_title_in_callout_title_div` → AC-3
- `TestCalloutTitleRendering::test_ideabox_title_not_as_raw_bracketed_text` → AC-3 negative
- `TestCalloutTitleRendering::test_ch01_first_callout_title_in_callout_title_div` → AC-3 end-to-end
- `TestCalloutTitleRendering::test_ch01_bracketed_title_text_not_in_rendered_html` → AC-3 negative end-to-end
- `TestCalloutNoTitle::test_ideabox_without_title_has_no_callout_title_div` → AC-4
- `TestCalloutNoTitle::test_defnbox_without_title_has_no_callout_title_div` → AC-4 boundary
- `TestAllCalloutEnvsHaveConsistentTitleRendering::test_callout_env_with_title_emits_callout_title_div[*]` → AC-5 (5 params)
- `TestAllCalloutEnvsHaveConsistentTitleRendering::test_callout_env_title_not_as_raw_bracketed_text[*]` → AC-5 negative (5 params)
- `TestAllCalloutEnvsHaveConsistentTitleRendering::test_all_five_envs_use_same_callout_title_class` → AC-5 structural consistency
- `TestAllCalloutEnvsHaveConsistentTitleRendering::test_all_callout_titles_in_ch01_are_structural` → AC-5 batch (all 111)
- `TestCalloutTitleEdgeCases::test_title_with_html_sensitive_chars_is_escaped` → ADR-012 HTML-escape edge
- `TestCalloutTitleEdgeCases::test_multi_word_title_is_fully_captured` → edge (multi-word title)
- `TestCalloutTitleEdgeCases::test_callout_body_content_is_preserved_alongside_title` → regression (body not dropped)
- `test_tabular_column_spec_lll_not_in_any_table_cell` (Playwright) → AC-1 + ADR-010 Playwright requirement
- `test_tabular_data_rows_are_present_in_dom` (Playwright) → AC-1 data-not-dropped (Playwright)
- `test_callout_title_chapter_map_in_callout_title_div` (Playwright) → AC-3 + ADR-010 Playwright requirement
- `test_callout_title_count_matches_titled_callouts` (Playwright) → AC-5 batch (Playwright)
- `test_raw_bracketed_title_not_visible_in_dom` (Playwright) → AC-3 negative (Playwright)
- `test_callout_title_is_first_child_of_callout_div` (Playwright) → ADR-012 structural position

**Coverage matrix:**
- Boundary: `test_simple_ll_spec_not_in_rendered_html` (2-col spec), `test_lcr_mixed_simple_spec_not_in_rendered_html` (mixed simple), `test_p_width_spec_*` (p{width}), `test_at_spec_not_visible_in_output` (@{...}), `test_defnbox_without_title_has_no_callout_title_div` (2nd no-title env). All spec variants from ADR-011 (l/c/r, |, p{w}, @{...}) covered. `test_simple_lrc_does_not_trigger_warning` covers the "no warn for simple" threshold flip.
- Edge: `test_tabular_inside_callout_spec_not_in_rendered_html` (nesting), `test_title_with_html_sensitive_chars_is_escaped` (HTML-sensitive chars in title), `test_multi_word_title_is_fully_captured` (multi-word title), `test_callout_body_content_is_preserved_alongside_title` (body not consumed by title extraction), `test_all_callout_titles_in_ch01_are_structural` (whole real corpus batch).
- Negative: `test_ideabox_title_not_as_raw_bracketed_text`, `test_ch01_bracketed_title_text_not_in_rendered_html`, `test_callout_env_title_not_as_raw_bracketed_text[*]` (all 5 envs), `test_ideabox_without_title_has_no_callout_title_div`, `test_defnbox_without_title_has_no_callout_title_div`, `test_simple_lrc_does_not_trigger_warning`, `test_raw_bracketed_title_not_visible_in_dom` (Playwright).
- Performance: skipped — inputs are single fixed-size tabular/callout fragments; no scaling surface for unit tests. The batch corpus test (`test_all_callout_titles_in_ch01_are_structural` + Playwright `test_callout_title_count_matches_titled_callouts`) provides a scale signal but not a time budget assertion, which is appropriate for DOM count assertions.

**Pytest red result:** Collected: 33, Failing: 20, Passing: 13 (unit tests). Playwright: 6 errors (browser not installed — same infrastructure state as TASK-003 Playwright tests).
**Assumptions:**
- ASSUMPTION: ADR-011's tabular spec text-strip is already implemented on disk (grep confirmed the existing regex skips the spec). The tabular strip tests pass; the warning-for-complex-spec tests fail (warning logic not yet implemented). This matches ADR-011's context note about the existing regex fix.
- ASSUMPTION: The warning message for `|` in a tabular spec will contain either the literal character `|`, the word "pipe", or the word "vertical". Tests accept any of these.
- ASSUMPTION: The warning message for `p{width}` will contain either `p{`, the word "paragraph", or `p-col`. Tests accept any of these.
**CANNOT TEST:** none
**Architecture leaks found:** none
**Pushback raised:** none

### Run 005 — implementer

**Time:** 2026-05-08T20:00:00Z
**Input files read:**
- `design_docs/MANIFEST.md`
- `design_docs/architecture.md`
- `.claude/skills/manifest-conformance/SKILL.md`
- `CLAUDE.md`
- `design_docs/decisions/ADR-011-tabular-column-spec-handling.md`
- `design_docs/decisions/ADR-012-callout-title-rendering.md`
- `design_docs/decisions/ADR-003-rendering-pipeline.md`
- `tests/test_task004_parser_fidelity.py`
- `tests/conftest.py`
- `app/parser.py`

**Tools / commands used:** Read, Glob, Grep, Bash (pytest runs, git stash/pop, python debug scripts), Write (debug scripts, later deleted), Edit (app/parser.py, audit file)
**Files created:** none (debug scripts created and deleted during investigation)
**Files modified:**
- `app/parser.py` — Bug 1: added `_warn_complex_col_spec()` helper and updated `_render_tabular()` to extract and check col spec; Bug 2: updated `_get_optional_arg()` to use raw verbatim regex, added `_render_callout_title_html()` helper, updated callout handlers in both `_convert_inline_latex` and `_nodes_to_html` to extract title and re-parse body
- `design_docs/audit/TASK-004-parser-fidelity-tabular-callout-titles.md` — header updated, Run 005 appended

**Files explicitly NOT modified:** `tests/**/test_*.py`, `design_docs/MANIFEST.md`, `design_docs/architecture.md`, `design_docs/decisions/**`, `CLAUDE.md`, `.claude/skills/manifest-conformance/SKILL.md`

**Implementation decisions made:**
- Bug 1 (tabular warning): `_warn_complex_col_spec(col_spec, chapter_id)` checks for `|`, `p{`, `@{`, `>{`, `<{` in the column spec string and logs a structured WARNING per ADR-003 warn-per-node pattern. Simple `l/c/r` do not trigger warnings. The chapter_id is passed as `getattr(env_node, '_chapter_id', 'unknown')` since the node has no chapter context.
- Bug 2 (callout title): Root cause was that pylatexenc does not parse the optional bracket argument for unknown environments — `nodeargd.argnlist` is always empty. The `[Title]` text appears embedded in the first chars/macro node of the body nodelist. Fix: `_get_optional_arg()` now uses regex on `node.latex_verbatim()` to extract the title; body is re-parsed from raw verbatim with the `[Title]` prefix stripped using `(?:\[[^\]]*\])?`. Title is rendered through `_render_callout_title_html()` which calls `_convert_inline_latex` on the parsed title LaTeX (handles macros like `\texttt{...}` in titles).
- A pre-existing regression was discovered and fixed: `test_generic_macro_pattern_not_leaked_in_prose` failed after initial fix because titles containing LaTeX macros (e.g., `\texttt{using namespace std;}`) were passed to `_escape()` unchanged, leaving `\texttt{` in prose HTML. The `_render_callout_title_html()` helper re-parses the title LaTeX through `_convert_inline_latex`, handling macros inside titles per the "natural extension" path mentioned in ADR-012.

**Tests run:** `python -m pytest tests/ --ignore=tests/playwright -v` → 173 passed, 2 skipped, 6 warnings. `python -m pytest tests/test_task004_parser_fidelity.py -v` → 33/33 passed.
**Lint / type-check:** not configured (no `ruff` or `mypy` command in CLAUDE.md)
**Conformance result:** 0 blockers, 0 warnings, 4 dormant (MC-1 package names, MC-3 mapping source, MC-10 persistence boundary, MC-6 source root path — all ADR-pending per the skill)
**End-to-end verification:** FastAPI TestClient GET /lecture/ch-01-cpp-refresher → 200; callout-title divs found: 111/111 (all titled callouts structural); `[Chapter map]` not in HTML; `\texttt{` not in prose HTML; `<td>lll</td>` not in HTML. All 4 verification checks pass.
**Adjacent bugs surfaced (not fixed):** The `_warn_complex_col_spec` receives `getattr(env_node, '_chapter_id', 'unknown')` because the environment node has no chapter context — warnings always log `unknown` as the chapter ID. This is a pre-existing limitation of the warn-per-node pattern in this codebase (ADR-003 does not require the chapter_id in warnings). Not fixed as it is out of scope for TASK-004 and does not affect any failing test.
**Pushback raised:** none

### Run 006 — reviewer

**Time:** 2026-05-08T22:00:00Z
**Staged files reviewed:** none (nothing staged; reviewed unstaged working-tree diff per user instruction)
**Unstaged source/test warning:** All source and test files are unstaged. The staged diff is empty — this review was conducted against the working-tree diff at the user's explicit request.
**Conformance skill result:** 0 blockers, 0 warnings, 4 dormant (MC-1 package names, MC-3 mapping source, MC-6 source root path, MC-10 persistence boundary — all ADR-pending)
**Architecture leaks found in .md files:** 1 (CLAUDE.md — see blocking findings)
**Blocking findings:**
- ARCHITECTURE LEAK in CLAUDE.md: "Orchestrator verification of subagent outputs" section introduces a new process/architecture pattern (mandatory post-subagent verification with remediation authority) without an Accepted ADR. See review output for details.
- Project issue resolution text says "ADR-011 is Proposed and awaits human acceptance" but ADR-011 Status is Accepted. Stale text — non-blocking inconsistency but noted.
- Project issue resolution text says "ADR-012 is Proposed and awaits human acceptance" but ADR-012 Status is Accepted. Same stale text issue.
**Non-blocking findings:**
- `_warn_complex_col_spec` always receives `'unknown'` as chapter_id — warnings lack chapter context. Pre-existing limitation acknowledged in Run 005.
- `_render_tabular` has no type hint on its parameter; `_warn_complex_col_spec` has type hints (good). `_get_optional_arg` has no return type hint. Minor convention concern.
- Broad `except Exception` in callout body re-parse — swallows all errors silently. Acceptable per ADR-003 warn-per-node intent but worth noting.
- Test `test_simple_lll_spec_not_in_rendered_html` checks `"lll" not in prose_html` which could false-positive if body content happens to contain "lll" (unlikely but brittle). The more targeted `<td>lll</td>` check used in other tests is stronger.
**Final result:** CHANGES REQUESTED
