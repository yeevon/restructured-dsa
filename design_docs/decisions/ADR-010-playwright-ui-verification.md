# ADR-010: UI verification mechanism — Playwright (via `pytest-playwright`) as the project's UI test framework, with last-run screenshot artifacts gitignored

**Status:** `Accepted`
**Date:** 2026-05-08
**Task:** TASK-003
**Resolves:** none (UI-4 was previously surfaced under ADR-009 which the human Rejected; this ADR is the first commitment to a UI verification mechanism for the project — see "Relationship to ADR-009" below)
**Supersedes:** none

**Human gate (2026-05-08):** Accepted. Human ratified after the orchestrator transcribed the load-bearing density-vs-count justification into the ADR record. Human authorized a follow-up update to `.claude/skills/ui-task-scope/SKILL.md` to align UI-5 (and any related rule that implicitly assumes the manual-browser model) with this ADR before `/implement TASK-003` runs.

## Context

The `ui-task-scope` skill rule UI-4 requires every task that ships HTML for a learner to choose one of three rendered-behavior verification gates: (1) introduce a UI test framework via ADR, (2) add manual desktop-browser inspection as a named acceptance gate, or (3) defer with a justified follow-up. ADR-009 (drafted in the same `/design TASK-003` pass as ADR-008) chose option 2 — a manual desktop-browser gate — on the rationale that the project is small, single-user, has no CI, and that a UI test framework is heavyweight for the current surface area.

The human Rejected ADR-009 at gate time and directed UI-4 option 1 instead. The directive on the record:

> "would like to implement playwrite now, we can get rid of grep html test and redo them with playwrite instead, we can save last test run for validation with screen shots, results should be in gitignore when i start pushing this to a repo"

This is a clear directive to introduce Playwright now, migrate the existing rendered-DOM-string-search tests to Playwright assertions, capture per-run screenshots as the human's validation evidence, and ensure the artifact directory is excluded from version control. The directive supersedes the architect's prior recommendation; the architect's job here is to settle UI-4 option 1 in concrete terms, not to re-litigate option 2.

The human added a follow-up justification at gate time:

> "justification for not manual testing is that even though this is a simple ui it is context dense and relying on human validation to check 100 hundreds of pages worth of content will miss alot of issues"

This justification refines the cost-benefit reasoning the architect used in ADR-009. ADR-009 weighed the project's surface area by chapter count (12 chapters, 1 user, 2 surface types) and concluded the manual gate was sustainable at that scope. The human's argument reframes the binding constraint: it is content *density per surface*, not surface count. Each rendered Lecture page carries enough internal content (section structure, designation badge, callouts, math passthrough, code blocks, cross-Chapter rail entries, per-row error degradation under ADR-007) that a single human gate cycle does not reliably surface a regression in any one of those concerns. Across 12+ Chapters the probability that a manual gate misses some regression on some page is high enough that the human judges it unacceptable. This validates the Playwright direction on architectural merit, not just by human authority. The supersedure trigger ADR-009 named — "the page count exceeds what the human can eyeball reliably in one session" — is met under this reading, because the binding constraint is density per page, not raw page count.

The relevant existing assets and constraints:

- **Test runner:** `python3 -m pytest tests/` per `CLAUDE.md`. The current test suite has 158 tests across `tests/test_task001_*.py` and `tests/test_task002_navigation.py`, all using `fastapi.testclient.TestClient` against an in-process app instance. No browser is launched.
- **Run command:** `uvicorn app.main:app --host 127.0.0.1 --port 8000` per `CLAUDE.md`. The application is local-only (manifest §5: no remote deployment).
- **Existing tests that assert against rendered DOM-string content** (the "grep-HTML" pattern the directive targets):
  - `tests/test_task002_navigation.py` — `"Mandatory" in body`, `"Optional" in body`, `body.find("ch-01-arrays")`, ordering assertions via `body.find()`, `/lecture/{id}` substring checks, error-indicator substring checks for fail-loudly cases.
  - `tests/test_task001_lecture_page.py` — `id="section-1-N"` substring searches, `"Mandatory" in html`, `lecture-header` regex, preamble-macro absence checks.
  - `tests/test_task001_rendering_fidelity.py` — callout `data-callout` attribute searches, math-passthrough substring/regex, lstlisting `<pre><code>` checks.
  - `tests/test_task001_parser_edges.py` and `tests/test_task001_http_edges.py` — also assert against `response.text` content for parse-edge / HTTP-edge behavior.
- **Tests that do NOT match the "grep-HTML" pattern and stay in pytest:**
  - `tests/test_task001_conformance.py` — source-tree greps for write-mode opens (no HTML, no app invocation; pure static analysis of `app/` Python files).
  - `tests/test_task001_designation_edges.py` — unit tests against `chapter_designation()`; no HTML.
  - `tests/test_task001_readonly_edges.py` — filesystem-write detection via `monkeypatch`; no HTML assertions.
  - `tests/test_task001_identity.py` — Section ID computation unit tests; no HTML.
  - `tests/test_task002_navigation.py::test_mc3_*` and `::test_mc6_*` — source-tree greps and runtime write-detection via monkeypatch; no DOM assertions.
  - The HTTP-shape checks within otherwise-grep-HTML test files — `assert response.status_code == 200`, `assert "text/html" in content-type`, response-length sanity. These are HTTP-protocol assertions, not DOM assertions; they stay in pytest.

The boundary the directive draws ("get rid of grep html test and redo them with playwrite instead") is best read as: *assertions about rendered-DOM content* migrate to Playwright; *assertions about HTTP-protocol shape, source-code static properties, runtime side effects (writes), and pure-function unit behavior* stay in pytest. Conflating the two would either leave Playwright re-implementing protocol-level checks the existing TestClient does perfectly well, or strip pytest of its non-HTML coverage that has nothing to do with the directive. The ADR commits to the boundary explicitly so the implementer does not have to re-derive it.

The manifest constrains this decision through §3 (consumption — verification must confirm the surface is consumable, not merely returns 200; Playwright drives a real browser, which is the verification mechanism the consumption objective wants), §5 (no remote deployment, no LMS, no mobile-first — Playwright runs locally against the local FastAPI server, no CI infrastructure introduced; tests target a single desktop viewport), §6 ("Mandatory and Optional content are honored everywhere" — Playwright assertions pin the visible distinction at the rendered-DOM level), §7 ("Mandatory and Optional are separable in every learner-facing surface" — same), and §8 (single user — no per-user test isolation needed; Playwright sessions are one-at-a-time).

## Decision

### Framework — `pytest-playwright` (Playwright Python via the official pytest plugin)

The project adopts **Playwright** as its UI test framework, integrated through **`pytest-playwright`** (the official `playwright`-team-maintained pytest plugin). Concretely:

- `playwright` and `pytest-playwright` are added as Python dev dependencies. `playwright install chromium` is run once per workstation to install the browser binary.
- Playwright tests are written as `pytest` test functions that take the `page` fixture (`pytest-playwright`'s built-in fixture). Example shape:
  ```python
  def test_landing_page_shows_mandatory_and_optional_groups(page, live_server):
      page.goto("http://127.0.0.1:8000/")
      expect(page.get_by_role("heading", name="Mandatory")).to_be_visible()
      expect(page.get_by_role("heading", name="Optional")).to_be_visible()
  ```
- **Single test runner.** All tests — both the existing pytest tests and the new Playwright tests — run under one command: `python3 -m pytest tests/`. The Playwright tests are discovered as ordinary pytest test functions; `pytest-playwright` provides the browser fixtures. `CLAUDE.md`'s `Test:` line does not need to change. **This is a load-bearing reason to choose `pytest-playwright` over Playwright Node.js**: it preserves the project's single-runner discipline and avoids forcing CLAUDE.md to grow a second test command.
- **Default browser is Chromium.** Manifest §5 (no mobile-first) and the human's "desktop browser" framing make a single-browser default the right floor. The `--browser firefox` and `--browser webkit` flags remain available for ad-hoc cross-browser checks; this ADR does not commit to running them in the default test pass.
- **A `live_server` fixture starts `uvicorn app.main:app` on a free port for the duration of the test session.** The Playwright tests `page.goto()` against that local URL. The fixture is a thin wrapper around `uvicorn` (or `subprocess.Popen` if simpler) and lives in `tests/conftest.py` or a new `tests/playwright/conftest.py`. The implementer chooses; this ADR commits to the fixture existing, not to its file location.

### Test organization — Playwright tests live under `tests/playwright/`

A new directory `tests/playwright/` holds the Playwright test files. Files under `tests/` that do not import `pytest-playwright` fixtures remain ordinary pytest tests. The split is by directory, not by file naming convention, so future file additions are unambiguous.

The migrated test files are named to mirror the originals they replace — e.g., `tests/playwright/test_task002_navigation_dom.py` mirrors the DOM-assertion subset of `tests/test_task002_navigation.py`. The originals are not deleted en masse; instead, the DOM-assertion portions are *moved* to the Playwright file and the pytest file retains the HTTP-protocol / source-static / runtime-side-effect assertions. See "Migration scope" below.

### Migration scope — what moves to Playwright, what stays in pytest

The directive says "get rid of grep html test and redo them with playwrite." The architect reads this as *assertions about rendered-DOM content* migrate to Playwright; *non-DOM assertions stay in pytest*. The boundary:

**Migrates to Playwright (DOM-content assertions):**
- `test_task002_navigation.py`:
  - `test_ac_index_2_mandatory_label_present` / `_optional_label_present`
  - `test_ac_index_3_mandatory_chapters_in_mandatory_section` / `_optional_chapters_in_optional_section` / `_each_chapter_in_exactly_one_section`
  - `test_ac_index_4_chapter_links_target_lecture_route` / `_links_are_computed_not_hardcoded`
  - `test_ac_rail_1_lecture_page_includes_mandatory_label` / `_optional_label`
  - `test_ac_rail_2_lecture_page_rail_contains_cross_chapter_links`
  - `test_ac_order_1_numeric_order_mandatory_section` / `_numeric_vs_lexical_ordering`
  - `test_ac_bad_name_fails_loudly` / `_does_not_silently_omit` (the response-body content portions; the status-code check stays in pytest as a separate test)
  - `test_ac_missing_title_fails_loudly` / `_does_not_fabricate`
  - `test_ac_dup_number_whole_surface_fails_loudly` / `_does_not_silently_drop_one`
  - `test_ac_index_1_all_fixture_chapters_listed` (asserts against body content)
- `test_task001_lecture_page.py`:
  - `test_ac2_all_expected_section_anchors_present` / `_section_count_matches_source` / `_subsections_do_not_get_section_ids`
  - `test_ac3_mandatory_badge_present` / `_mandatory_not_optional`
  - `test_ac4_no_timestamp_in_rendered_html`
  - `test_adr001_preamble_content_not_treated_as_lecture_body`
- `test_task001_rendering_fidelity.py` — all callout-assertion, math-passthrough, lstlisting-content tests (these all interrogate rendered HTML for content fidelity).
- `test_task001_parser_edges.py` and `test_task001_http_edges.py` — the subsets that assert against `response.text` body content; the implementer reads each test and classifies (status-code/header tests stay in pytest, body-content tests move).

**Stays in pytest (non-DOM-content assertions):**
- All of `test_task001_conformance.py` (source-tree greps for write modes, no HTML).
- All of `test_task001_designation_edges.py` (unit tests against `chapter_designation()`).
- All of `test_task001_readonly_edges.py` (filesystem-write detection via `monkeypatch`).
- All of `test_task001_identity.py` (Section ID computation unit tests).
- `test_mc3_no_chapter_number_literals_outside_designation` and `test_mc6_no_write_open_against_content_latex_in_navigation_code` and `test_mc6_root_route_does_not_write_to_content_latex` from `test_task002_navigation.py` (source-tree greps and runtime write-detection).
- HTTP-protocol shape checks: `assert response.status_code == 200`, `assert "text/html" in content_type`, body-length sanity, response-determinism (`r1.text == r2.text` for byte-equality checks where the assertion is *equality of two responses* not *content correctness*). These remain `TestClient`-based.
- `test_ac4_two_renders_are_byte_identical` — byte-equality of two TestClient responses; no DOM walk needed. Stays in pytest.

**Total expected migration scope:** roughly 35-50 of the existing 158 tests move to Playwright (the architect is not exhaustively counting from this ADR — the implementer does the count during migration); the rest remain in pytest. The directive's target is the "grep HTML" *pattern*, not the *count* — every test that asserts against rendered-DOM content moves.

### Test artifacts — last run only, screenshots + traces, gitignored

The project saves the **last Playwright run** as artifacts for the human's validation review. The artifacts:

- **Screenshots per test** — Playwright captures one screenshot per test (the final viewport state) on success, and full-page screenshot + browser trace on failure. Configured via `pytest-playwright`'s `--screenshot=on` and `--video=retain-on-failure` and `--tracing=retain-on-failure` flags (or equivalent `pytest.ini` / `conftest.py` configuration; the implementer chooses the surface).
- **Browser traces on failure** — Playwright `trace.zip` files are saved on test failure; the human can open these in `playwright show-trace` to step through the failed run.
- **No videos by default** — videos are large and screenshots + traces are sufficient for the validation use case the human described. `--video=on` remains available for ad-hoc deep dives but is not the default.

The artifacts live at `tests/playwright/artifacts/` (or `test-results/` if the implementer prefers Playwright's default — the directory name is implementer's choice, but it MUST be a single named directory tree under `tests/` so the `.gitignore` rule and the cleanup rule both have one path to reference).

**Retention rule: last run only.** Each `pytest tests/playwright/` invocation overwrites the artifact directory's contents. Older runs are not preserved. This matches the human's stated intent ("save last test run for validation with screen shots") and avoids the artifact directory growing without bound. The `pytest-playwright` plugin and Playwright itself default to overwriting; the ADR commits to *not* configuring retention beyond the last run.

The architect explicitly does *not* commit to a "diff against previous run" or "screenshot regression" mechanism in this ADR. Such a mechanism (visual regression testing) would be a separable architectural decision and is out of scope here. The artifacts are for human review, not automated comparison.

### Gitignore commitment

The artifact directory MUST be excluded from version control. The `.gitignore` rule the project will carry once the implementer creates the artifact directory:

```
# Playwright test artifacts (last-run screenshots, traces, videos)
tests/playwright/artifacts/
```

(Or whatever directory path the implementer picks per the previous section; the architect's commitment is "the directory is gitignored," not the literal string above.)

The project already has a `.gitignore` file at the repo root (verified — the file exists and currently covers Python caches, virtual environments, SQLite runtime state, editor/OS files, and Claude local settings). The implementer adds the Playwright artifact line during the migration; this ADR does *not* prescribe that the human must edit `.gitignore` before any other work happens. The gitignore commitment is the binding architectural statement; the actual file edit is implementer scope at the moment the artifact directory is first created.

The `playwright/` browser binary cache (typically `~/.cache/ms-playwright/` on Linux) lives outside the repo and does not need a `.gitignore` rule.

### Verification gate — Playwright tests pass + human reviews last-run screenshots

The verification gate for any UI task replaces ADR-009's manual-browser inspection with:

1. **`python3 -m pytest tests/` passes** — including the Playwright tests under `tests/playwright/`. This is the automated portion.
2. **Human reviews the last-run screenshots** at `tests/playwright/artifacts/` (or chosen path) before declaring the task verified. This is the human-in-the-loop portion the human's directive explicitly preserves ("we can save last test run for validation with screen shots").
3. **Audit row format:** the Human-gates table row added by the human is:
   ```
   | <ISO timestamp> | rendered-surface verification | pass | playwright tests green; screenshots reviewed
   ```
   Or, on failure:
   ```
   | <ISO timestamp> | rendered-surface verification | fail — <one-line reason> | <follow-up>
   ```

The gate is **not** satisfied by Playwright tests passing alone — the screenshots must be reviewed. This preserves the load-bearing UI-5 / UI-6 / TH-5 invariant (humans actually look at the surface) while removing the requirement that the human manually open `uvicorn` + a browser for every cycle. The screenshot review is a faster, repeatable version of the same visual confirmation.

### Roles and obligations

- **Architect (Mode 1, `/next`):** when proposing a UI task, name "rendered-surface verification per ADR-010" in the task's "Verify" section.
- **Architect (Mode 2, `/design`):** when drafting an ADR that introduces or modifies a user-facing HTML surface, cite ADR-010 as the verification mechanism. Do not silently default to manual-browser inspection — that gate was rejected.
- **Test-writer (`/implement` Phase 1):** for any UI task, write at least one Playwright test under `tests/playwright/` covering each visual AC. Pytest-only DOM-string assertions are forbidden for new UI work.
- **Implementer (`/implement` Phase 2):** before declaring run-complete, run `python3 -m pytest tests/` and confirm both the existing pytest tests and the new Playwright tests pass. The implementer does not perform the screenshot review (the human does); the implementer's job is "tests green, artifacts produced."
- **Orchestrator (`/implement` Phase 3 verify):** confirms `pytest` exit code 0, confirms the `tests/playwright/artifacts/` directory contains screenshots from the last run, and routes to the human for the screenshot-review portion of the gate.
- **Reviewer (`/review` Phase 4):** confirms the audit Human-gates row marked `rendered-surface verification — pass` exists. Absence is a review blocker.
- **Human:** runs `python3 -m pytest tests/`, opens the screenshot directory, confirms the surface looks right, appends the audit row.

### What this ADR does *not* decide

- **A specific viewport size** beyond Playwright's default (1280x720). Manifest §5 (no mobile-first) means the desktop default is sufficient; the implementer may pin a different default in `pytest.ini` if desired.
- **A specific Playwright assertion style.** Playwright Python supports both `expect(locator).to_have_text(...)` and `assert locator.text_content() == ...` shapes; the implementer chooses per-test.
- **A CI invocation.** The project has no CI today; introducing one is a future ADR's call. The Playwright tests run locally on the human's workstation; that is the entire verification surface.
- **Visual regression testing** (screenshot-diff against a baseline). Out of scope; would be a separable future ADR.
- **Browser-binary management beyond the one-time `playwright install chromium`.** No automatic browser updates, no version pinning beyond what `requirements.txt` (or equivalent) carries for `playwright` itself.
- **Whether the existing pytest TestClient HTTP-protocol checks are reformulated as Playwright `request` API checks.** They are not — those checks belong to the layer that exercises FastAPI's HTTP surface directly; Playwright's strength is the rendered DOM, not the protocol layer. The boundary above ("Migration scope") is the binding rule.

## Alternatives considered

**A. Selenium (with `selenium-py`).**
The most mature browser-automation framework. Rejected because:
- Heavier setup: requires installing a separate WebDriver per browser (geckodriver, chromedriver) outside `pip`. `pytest-playwright`'s `playwright install chromium` is a single command that downloads a known-version browser; Selenium delegates browser version management to the user.
- Slower in practice than Playwright (Playwright's CDP-based architecture avoids the WebDriver round-trip overhead).
- Less ergonomic API for modern web app patterns (waiting strategies, network interception, isolated browser contexts). Playwright was designed after Selenium's pain points were well understood and addresses most of them.
- Smaller pytest integration ecosystem (Selenium has `pytest-selenium`, but the maintenance velocity has lagged relative to `pytest-playwright`).
- The human's directive explicitly named Playwright; Selenium would be choosing against the directive without strong architectural reason. Playwright is the better default for new projects in 2026, and "no remote deployment / no CI today" doesn't change that.

**B. Cypress (Node.js, browser-only).**
Rejected because:
- Cypress is Node.js — adopting it introduces a JavaScript/Node toolchain into a Python-only project. The project's `app/` is Python; the test suite is Python; CLAUDE.md `Test:` is `python3 -m pytest tests/`. Adding Node.js for tests alone is a substantial second-toolchain commitment that doesn't pay back at this scope.
- Cypress runs only in the browser (no headless mode prior to v10, and the Electron-based runner is heavier than Playwright's headless Chromium).
- Cypress's iframe model and same-origin restrictions are awkward for some testing patterns Playwright handles cleanly.
- Splitting the test runner (pytest for Python tests, Cypress for UI tests) creates the exact "two test commands" problem the `pytest-playwright` choice avoids. CLAUDE.md would need a second `Test:` line, and the orchestrator would need to invoke both.
- The human's directive named Playwright, not Cypress.

**C. Playwright via Node.js (raw `@playwright/test`).**
The non-`pytest-playwright` path. Rejected because:
- Same two-toolchain objection as Cypress: introduces Node.js into a Python project.
- Same two-runner objection: `pytest tests/` + `npx playwright test` becomes the test command; CLAUDE.md must grow.
- Loses the `pytest`-fixture composability — test fixtures (the `live_server` fixture, the fixture-corpus seam used by `test_task002_navigation.py`'s `_make_client_with_root` helper) would need to be re-implemented in JavaScript, doubling the maintenance surface.
- The Node.js Playwright is more featureful in some ways (better trace viewer integration, slightly faster startup), but those advantages don't overcome the toolchain cost at this project's scope.

**D. Keep the manual-browser gate (revive ADR-009's spirit).**
This was the architect's prior recommendation. Rejected because the human Rejected ADR-009 and explicitly directed Playwright. Re-proposing the manual gate would be reading-against-the-directive; the architect's pushback channel is "raise it explicitly in My recommendation vs the user's apparent preference," not "draft a contradicting ADR." See that section below.

**E. Use Playwright for end-to-end testing only and keep all DOM-string assertions in pytest.**
A "Playwright is for journeys; pytest is for content" split. Rejected because:
- It ignores the directive's explicit "we can get rid of grep html test and redo them with playwrite instead." The directive targets the grep-HTML pattern, which is exactly what this alternative would preserve.
- The grep-HTML pattern is what produced the TASK-002 silent-ship: tests passed by string-matching against unstyled HTML. Migrating these assertions to Playwright (where they exercise the actual rendered DOM via locators, role queries, and visibility checks) is the architectural fix for that failure mode. Keeping them as `string in body` assertions perpetuates the failure pattern.
- A Playwright `expect(page.get_by_role("heading", name="Mandatory")).to_be_visible()` is a strictly stronger assertion than `assert "Mandatory" in body`: the former requires the heading to exist as a heading semantic role *and* to be visible (not `display: none`, not occluded); the latter passes if "Mandatory" appears anywhere in the response, including in a CSS comment or a hidden meta tag.

**F. Skip a UI test framework entirely and rely on a CI-driven screenshot diff (e.g., `applitools`, `chromatic`).**
Strictly larger than option A or this ADR. Rejected because the project has no CI and manifest §5 (no remote deployment) makes a hosted SaaS visual-regression service inappropriate.

## My recommendation vs the user's apparent preference

**Aligned with the user's direction on the framework choice and the migration scope.** The human directed Playwright explicitly; the architect agrees Playwright is the right framework if any UI test framework is being introduced now (option A above), and the `pytest-playwright` integration is the right way to bring it in (preserves single-runner discipline, preserves CLAUDE.md `Test:` line, lowest-friction adoption path). The migration of grep-HTML tests to Playwright assertions is also the right architectural move on the merits — it addresses the TASK-002 silent-ship failure pattern at its root.

**Mild push the architect wants on the record:**

1. **The boundary between "grep HTML" tests and "structural HTTP" tests must be drawn deliberately, not by sweeping every existing test into Playwright.** The directive says "get rid of grep html test and redo them with playwrite instead." Read literally as "delete every existing test and rewrite all 158 in Playwright" this would (a) re-test things Playwright is poor at (file-write detection via monkeypatch, source-code static analysis), (b) couple every single behavior to a browser session, (c) inflate the test runtime by an order of magnitude. The Migration scope section above draws the boundary explicitly. The architect's read is that the human's intent is "the rendered-DOM-content tests" (the ones that produced the silent-ship failure), not "every test that touches `response.text`." If the human's intent is broader, the implementer revises the boundary at migration time and notes it; for now this ADR commits to the rendered-DOM-content reading.

2. **"Last run only" is the right retention rule, but it means a failing screenshot is overwritten on the next run.** The human asked for "last test run for validation." This ADR honors that literally: each run overwrites. If a screenshot from a failed run is needed for debugging, the human captures it from the artifacts directory before re-running, or the implementer commits it to the audit file as evidence. The ADR explicitly does not introduce a "keep failing-run screenshots" mechanism because that would either require a more elaborate retention policy (which the directive did not ask for) or grow the artifacts directory unbounded over time.

3. **Screenshots are validation evidence, not the primary verification.** Playwright tests passing is the primary verification (automated, repeatable, blocks `pytest` if broken). Screenshots are the human's eyeball check that the *automated assertions are checking the right thing* — i.e., that the surface looks correct, not just that the assertions pass. If a future Playwright test is wrong (asserts against a CSS class name that no longer corresponds to the visible surface), the screenshot review catches it where the assertion alone does not. The audit-row format above makes both portions explicit.

4. **The architect's prior preference for the manual-browser gate (ADR-009) is retracted on the merits — not merely overridden by directive.** The human's stated justification (recorded in Context above) reframes the binding constraint correctly: content *density per surface* dominates surface count for verification reliability. ADR-009's cost-benefit reasoning weighed surface count and underweighted density; that reasoning is wrong on reflection. ADR-010 is the architecturally correct call. The more durable parts of ADR-009 (the supersedure-trigger discipline, the role-obligation structure, the audit-row format pattern) are carried forward by ADR-010 in modified form; the rejected portion is the cost-benefit conclusion, not the framing apparatus.

## Manifest reading

Read as binding for this decision:

- **§3 Primary Objective ("drive consumption … via per-Chapter Lectures and Notes").** Bound the requirement that verification confirm the surface is *actually consumable*, not merely returns 200. Playwright drives a real browser and exercises the rendered DOM; this is a strictly stronger consumption-verification mechanism than `curl + grep`.
- **§5 Non-Goals:**
  - "No mobile-first product" — bounds the test viewport floor (desktop default).
  - "No remote deployment" — bounds the test runner to local; no CI infrastructure is introduced by this ADR.
  - "No multi-user features" — bounds the verifier to one (the human); no shared CI dashboard, no test-result distribution.
  - "No LMS features" — irrelevant to verification mechanism; not implicated.
- **§6 Behaviors and Absolutes:**
  - "Mandatory and Optional content are honored everywhere" — Playwright assertions verify the visible distinction at the DOM level (e.g., `expect(page.get_by_role("heading", name="Mandatory")).to_be_visible()`), strengthening MC-3 enforcement at the rendered-surface boundary.
  - "AI failures are visible" — not directly touched; verification mechanism does not change failure-visibility semantics.
- **§7 Invariants:**
  - "Mandatory and Optional are separable in every learner-facing surface" — Playwright verifies separability at the rendered layer.
- **§8 Glossary** — no new terms introduced; existing terms (Chapter, Mandatory, Optional, Section, Lecture) are consumed without modification.

No manifest entries flagged as architecture-in-disguise.

**Manifest entries the architect would want the human to revisit (low priority, surfaced for completeness):** none. The manifest is silent on verification mechanisms by design, and that silence is correct — the manifest is product behavior, not test infrastructure.

## Conformance check

- **MC-1 (No direct LLM/agent SDK use).** Not touched. Playwright is a browser-automation library, not an LLM SDK.
- **MC-2 (Quizzes scope to exactly one Section).** Not touched (no Quiz code introduced).
- **MC-3 (Mandatory/Optional designation respects the canonical mapping).** *Strengthened* by Playwright migration: the migrated rendered-DOM assertions verify the M/O split at the visible-surface level (`expect(...).to_be_visible()` queries the live DOM, not the response string). No CSS or layout rule encodes a chapter-number threshold.
- **MC-4 (AI work is asynchronous from the learner's perspective).** Not touched.
- **MC-5 (AI failures are surfaced, never fabricated).** Not touched.
- **MC-6 (Lecture source is read-only to the application).** Not touched. Playwright tests do not write to `content/latex/`; the existing source-tree-grep test (`test_task001_conformance.py`) and runtime monkeypatch test (`test_mc6_root_route_does_not_write_to_content_latex`) remain in pytest and continue to enforce.
- **MC-7 (Single user).** *Honored.* Playwright runs locally on the human's workstation. No remote test infrastructure, no shared dashboard, no multi-user test-result coordination. The `live_server` fixture starts one `uvicorn` instance per test session; one user, one browser, one verification surface.
- **MC-8 (Reinforcement loop is preserved).** Not touched (no Quiz code).
- **MC-9 (Quiz generation is user-triggered).** Not touched.
- **MC-10 (Persistence boundary).** Not touched. ADR pending; no DB introduced.

UI-skill rules (`ui-task-scope`):
- **UI-1 (Task scope must declare styling responsibility).** Not directly touched by this ADR; the rule applies to task files, not ADRs introducing test frameworks.
- **UI-2 (ADR Decision section must scope CSS).** Not applicable — this ADR introduces a test framework, not a UI surface.
- **UI-3 (Implementer must edit CSS for new layout-bearing templates).** Not applicable.
- **UI-4 (UI surfaces must have rendered-behavior tests).** *Satisfied.* This ADR settles UI-4 option 1 (introduce a UI test framework via ADR). Future UI tasks cite ADR-010 by reference rather than re-decide between the three UI-4 options.
- **UI-5 (Verify pass requires browser eyeballing).** *Satisfied with adjustment.* The human's screenshot review portion of the gate (audit-row step 2 in "Verification gate" above) preserves the load-bearing intent of UI-5 (a human looks at the rendered surface). The Playwright test pass alone does not satisfy UI-5; the screenshot review does. UI-5 may be updated in a follow-up to reflect that "browser eyeballing" can now be satisfied by reviewing Playwright screenshots from the last run, not only by opening `uvicorn` + a browser. The architect flags this for the human (UI-5 lives in `.claude/skills/ui-task-scope/SKILL.md`, which is human-owned per CLAUDE.md tier table).
- **UI-6 (Reviewer walks the rendered surface).** *Satisfied.* The reviewer confirms the audit row exists; the row records that the screenshots were reviewed.

Test-honesty rules (`test-honesty-check`):
- **TH-1..TH-4.** Not directly implicated.
- **TH-5 (tests pass on partial implementation).** *Strengthened.* TH-5 is the failure mode the directive exists to prevent. Playwright's rendered-DOM assertions (visibility, role queries, viewport interactions) are categorically harder to satisfy with a partial implementation than `string in body` assertions. A Playwright `expect(locator).to_be_visible()` requires the element to exist *and* render in the viewport; an `assert "Mandatory" in body` passes if the string appears anywhere in the response, including in HTML comments or hidden CSS-display-none elements. The migration is the architectural answer to TH-5 for UI work.

Authority-state rules (`authority-state-check`):
- **AS-1 (Accepted ADR content immutability).** ADR-010 is `Proposed`. ADR-008 (Accepted) is not edited by this ADR; ADR-006 (Accepted) is not edited; ADR-009 (Rejected) is not edited.
- **AS-2 (ADR Status values are coherent).** ADR-010 carries `Status: Proposed`, recognized by AS-2.
- **AS-3 (`architecture.md` mirrors ADR-disk states).** ADR-010 is added to `architecture.md`'s "Proposed ADRs" table; ADR-008 moves from "Proposed" to "Accepted"; ADR-009's row is removed (Rejected ADRs do not appear in any architecture.md table per AS-3).
- **AS-4 (Audit Human-gates table matches disk).** The audit's existing rows for ADR-008 (accepted) and ADR-009 (rejected) match disk. A new audit row will be added when ADR-010 is gated by the human.
- **AS-5 (Project_issue ↔ ADR coherence).** ADR-010 does not directly resolve a project_issue. `adr006-rail-half-implemented-no-css.md` is updated to drop the "(pending acceptance)" qualifier on its `Resolved by ADR-008` line, since ADR-008 is now Accepted.
- **AS-6 (Task ↔ ADR coherence).** TASK-003's references to ADR-009 are updated to ADR-010 (mechanical reference swap; see Part 3 of this `/design` cycle).
- **AS-7 (`/implement` does not start with Proposed/Pending ADRs).** ADR-010 is `Proposed` → `/implement TASK-003` is blocked until the human gates ADR-010.

Audit-append-only rules (`audit-append-only`):
- **AA-1..AA-6.** Honored. The new Run 003 entry is appended; existing Runs 001 and 002 and existing Human-gates rows are preserved verbatim.

**Previously-dormant rule activated by this ADR:** none. UI-4 was already operational; this ADR settles which option is chosen, not whether the rule applies.

## Relationship to ADR-009

ADR-009 was drafted in the same `/design TASK-003` pass and proposed manual desktop-browser inspection as the verification gate. The human Rejected ADR-009 at gate time and directed UI-4 option 1 (introduce a UI test framework) instead.

**ADR-009 is `Rejected`, not `Superseded`.** The distinction matters per AS-2 / AS-3:

- A Rejected ADR is one that was never Accepted by the human and therefore never entered the project's binding architecture. ADR-010 is *not* a successor to a prior commitment; it is the *first* commitment to a UI verification mechanism for the project.
- A Superseded ADR was previously Accepted, in force, and binding for some period of work; a successor ADR replaces it. That sequence did not occur here — ADR-009 was drafted, gated, and Rejected without ever entering force.
- ADR-009's file is preserved on disk (per CLAUDE.md's rejection-handling rule) as a historical record of the option-2 path the project considered and chose not to take. The file's `Status: Rejected` is the on-disk evidence of that path being closed.

ADR-010 cites ADR-009 in this section (and in the `Supersedes:` header field, where it is `none`) so a future reader can trace the decision history without confusion. ADR-010 does not depend on ADR-009 for its substance.

## Consequences

**Becomes possible:**

- A repeatable, automated verification of rendered-DOM content for every UI task. The Playwright test suite catches the silent-ship failure pattern (TASK-002's "structural class names present, but page renders unstyled") because Playwright assertions exercise the live DOM, not the response string.
- A single test command (`python3 -m pytest tests/`) that covers both the Python unit/integration tests and the browser-driven UI tests. CLAUDE.md `Test:` line is preserved.
- Screenshots from the last run as human-reviewable validation evidence. The human's gate cycle becomes "run pytest; open the screenshots directory; confirm the surface looks right; append the audit row" — faster than "start uvicorn; open browser; navigate; visually inspect; close browser; append audit row" while preserving the load-bearing visual confirmation.
- A defined upgrade path for future UI work: future UI tasks add Playwright tests under `tests/playwright/`, no new architectural decision required.
- A defined boundary between "rendered-DOM tests" (Playwright) and "HTTP-protocol / source-static / runtime-side-effect tests" (pytest). The boundary is enumerated in this ADR's Migration scope section; future test additions follow the same rule.

**Becomes more expensive:**

- Two new dev dependencies (`playwright`, `pytest-playwright`) and a one-time `playwright install chromium` per workstation (~150MB of browser binary).
- Test runtime grows. Browser-based tests are slower than `TestClient` tests by an order of magnitude (typically 100ms-1s per test versus 1-10ms). For a project at 158 tests today migrating ~30-50 to Playwright, expected total test-suite runtime grows from a few seconds to tens of seconds. At the project's scope this is acceptable; if it becomes a friction point, parallelization (`pytest-xdist`) is a future ADR's call.
- The implementer takes on a one-time migration cost: classify each existing test (DOM-content vs not), move the DOM-content portions to `tests/playwright/`, rewrite assertions in Playwright idiom. Estimated implementer scope: a few hours, bounded.
- A new test artifact directory exists in the working tree (`tests/playwright/artifacts/`) whose contents change on every test run. The `.gitignore` rule prevents accidental commits; the human verifies once that the rule is in place after the implementer creates the directory.
- The `live_server` fixture introduces an in-test process management surface (starting and stopping `uvicorn`). Failure modes (port collision, process leak) are bounded by `pytest`'s session-scope teardown, but the implementer must implement the fixture correctly.

**Becomes impossible (under this ADR):**

- A UI task that ships with `string in body` DOM assertions as its only rendered-behavior verification. The test-writer is obligated to add Playwright tests for any new UI work; pytest-only DOM assertions for new UI work are forbidden by the verification gate.
- A UI task that commits without an audit row marked `rendered-surface verification — pass`. The reviewer is obligated to block.
- A test runner split across Python and JavaScript toolchains. The `pytest-playwright` choice rules out raw Node.js Playwright and Cypress at the architectural level; future supersedure would require an ADR.
- An automatic upload of test artifacts to a remote CI / dashboard. The artifacts are local-only; manifest §5 (no remote deployment) is honored.

**Future surfaces this ADR pre-positions:**

- **Notes UI** (manifest §8) — Playwright tests under `tests/playwright/test_notes_*.py` verify the Note-editor surface; no new framework decision required.
- **Quiz UI surfaces** — Playwright tests cover the per-Section "Quiz this Section" affordances and the in-Quiz interaction (radio buttons, submit, navigate to next Question). The asynchronous AI portion (manifest §6: AI work is async) is verified via Playwright's wait mechanisms (`expect(...).to_be_visible(timeout=...)`) for the Notification's appearance.
- **Notification surface** (manifest §8) — Playwright verifies that a Notification appears in the chrome and is dismissible.
- **Visual regression testing** (future) — if the project ever wants screenshot-diff against a baseline, the artifact directory created by this ADR is the natural source-of-truth for that mechanism. Visual regression is a separable future ADR.
- **CI integration** (future) — if the project ever adopts CI, `python3 -m pytest tests/` is the single command CI invokes. Browser binaries are installed via the CI's Playwright install step. The current local-only model degrades gracefully into a CI-extended model without an architectural break.

**Supersedure path if this proves wrong:**

- **If `pytest-playwright` proves a maintenance burden** (e.g., browser-version drift breaks tests on workstation updates), a future ADR can pin `playwright` to a specific minor version or move to raw `playwright` Python without the pytest plugin (loses single-runner discipline; the cost is recorded here so the supersedure has a clear cost-benefit).
- **If the test runtime grows unsustainable** (e.g., the project reaches 500+ Playwright tests and a full run takes minutes), parallelization via `pytest-xdist` is an additive change (no ADR needed) or `playwright`'s sharding (`--shard=...`) becomes the path (ADR).
- **If the project gains CI** and Playwright artifacts are wanted as CI-uploaded artifacts (separate from the local `tests/playwright/artifacts/` last-run directory), a CI-integration ADR commits to the artifact-upload path; this ADR's local-only commitment becomes the local subset of a hybrid local+CI model.
- **If a future Playwright assertion turns out to be a bad fit for a particular surface** (e.g., a heavily-canvas-based or WebAssembly surface), the test-writer falls back to pytest+TestClient for that surface, with a one-line note in the test file explaining why. The boundary in Migration scope above is the rule; exceptions are case-by-case and recorded inline, not an ADR amendment.

---

## Follow-up flagged for the human (not in scope to fix here)

1. **`.claude/skills/ui-task-scope/SKILL.md` UI-5 wording** currently reads "browser eyeballing" with the implicit assumption that the human opens a browser directly. With ADR-010, "browser eyeballing" can be satisfied by reviewing Playwright screenshots from the last run. UI-5 may benefit from a clarifying edit; the architect cannot edit the skill file (human-owned per CLAUDE.md tier table). Recommended edit: append "or by reviewing Playwright screenshots from the last test run, per ADR-010" to UI-5's description.

2. **`CLAUDE.md`'s `Test:` line** is `python3 -m pytest tests/` and remains correct under this ADR — no edit needed. Flagging here for completeness so a future reader does not assume the test command must change.

3. **The `.gitignore` file** at the repo root currently does not include the Playwright artifact directory. The implementer adds the line during the migration (when the directory is first created); this ADR does not require a pre-implementation edit.
