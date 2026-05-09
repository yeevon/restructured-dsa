# ADR-013: Multi-chapter validation harness — split Playwright (visual) and HTTP-protocol pytest (smoke)

**Status:** `Accepted`
**Date:** 2026-05-08
**Task:** TASK-005
**Accepted:** 2026-05-08 (human gate; rationale recorded in TASK-005 audit Run 004 — content is dense but file-type structure across all 12 Chapters is near-identical, so a parser issue found in one Chapter applies to most others; the surrounding features around the Chapters are not customized per Chapter, which makes a split harness with a fast HTTP smoke gate plus a parameterized Playwright visual layer the right shape for triage)
**Resolves:** none (no existing project_issue covers this question; it is forced by TASK-005 framing)
**Supersedes:** none

## Context

TASK-005 is the first triage pass across all 12 Chapters. Eleven of twelve Chapters have never been rendered through `GET /lecture/{chapter_id}` and confirmed via the ADR-010 verification gate. The task forces a decision about the *shape* of the validation harness — i.e., how the test suite asserts on (a) "every Chapter returns HTTP 200, no parser crash, no template-render exception" and (b) "every Chapter produces a Playwright screenshot for the human's per-Chapter visual review."

Three options materially differ:

- **(a) Pure Playwright batch test.** One parameterized Playwright test that walks all 12 Chapter IDs, asserts HTTP 200 (via Playwright's `page.goto()` response), takes a screenshot of each, and lets the human review the artifact set.
- **(b) Playwright batch + HTTP-protocol pytest layer.** A parameterized HTTP-only pytest using `TestClient` that asserts 200 + minimal structural sanity (heading present, at least one section anchor) on every `GET /lecture/{chapter_id}`; plus a parameterized Playwright pass that captures the 12 screenshots for visual review.
- **(c) CLI render-all tool.** A separate `python -m app.render_all` command that writes 12 HTML files to a tmp dir for offline human review, in addition to or instead of the in-test workflow.

ADR-010 commits the project to Playwright as the rendered-DOM verification mechanism, with last-run screenshots gitignored as the human's validation evidence. ADR-010 also explicitly draws the boundary "rendered-DOM-content tests live under `tests/playwright/`; HTTP-protocol, source-static, and runtime-side-effect tests stay in pytest under `tests/`." That boundary is the architectural input that constrains this decision.

The corpus is 12 files. Each Lecture page exercises the body parser end-to-end (sections, callouts, tabular, code listings, math, lists, custom envs) and the navigation rail (which renders all 12 rows on every page). The single previously-validated Chapter (Chapter 1) revealed three latent parser bugs (tabular column spec, callout title, `\\` linebreak); the prior is overwhelming that the other 11 contain additional latent bugs.

The manifest constrains this decision through §3 (drive consumption — the validation surface must be exercised), §5 (no remote deployment, no CI; the harness runs locally), §6 ("Mandatory and Optional content are honored everywhere" — the M/O badge renders on every page), and §7 (M/O separable in every learner-facing surface).

## Decision

The validation harness is **split** — Option (b) above:

### HTTP-protocol layer (pytest, `TestClient`-based)

A new parameterized pytest at `tests/test_task005_multi_chapter_smoke.py` walks **all 12 Chapter IDs** (the same list TASK-005's AC enumerates: `ch-01-cpp-refresher`, `ch-02-intro-to-algorithms`, `ch-03-intro-to-data-structures`, `ch-04-lists-stacks-and-queues`, `ch-05-hash-tables`, `ch-06-trees`, `ch-07-heaps-and-treaps`, `ch-09-balanced-trees`, `ch-10-graphs`, `ch-11-b-trees`, `ch-12-sets`, `ch-13-additional-material`). For each Chapter, the test asserts:

- `response.status_code == 200` — the parser/template did not raise an unhandled exception.
- `"text/html" in response.headers["content-type"]` — basic content-type sanity.
- The response body contains the Chapter's expected M/O badge text per the canonical mapping (Chapters 1–6 Mandatory; Chapters 7, 9, 10, 11, 12, 13 Optional). This is the **structural smoke check**, deliberately light — not a rendered-DOM assertion. The badge presence as a substring confirms `chapter_designation()` ran and the template rendered, which is the smallest structural witness that the page is meaningful.
- The response body contains at least one `<section id="` substring — confirms `extract_sections()` produced at least one Section anchor (TASK-005 AC-3.iii).

This layer is **fast** (TestClient runs in-process; ~12 tests at ~10ms each). Its job is to fail loudly the instant a Chapter's parse path crashes or the template raises — long before Playwright is launched. It is the project's first repeatable smoke gate against the corpus as a whole.

### Visual layer (Playwright, parameterized)

A new parameterized Playwright test at `tests/playwright/test_task005_multi_chapter_screenshots.py` walks the same 12 Chapter IDs against the `live_server` fixture (per ADR-010). For each Chapter:

- `page.goto(f"http://127.0.0.1:{port}/lecture/{chapter_id}")` — drives a real Chromium against the live FastAPI app.
- Asserts the page heading is visible (`expect(page.locator("h1, .lecture-header")).to_be_visible()` or the implementer's locator-of-choice for the existing Lecture-header element) — confirms the page rendered structurally beyond HTTP 200.
- Captures a full-page screenshot to `tests/playwright/artifacts/lecture-{chapter_id}.png` (or whatever artifact path the implementer adopts consistent with ADR-010's "last run only, single artifact directory" rule). Same viewport for all 12 to enable cross-Chapter visual comparison.

This layer is the **human-review surface**. After `pytest` exits 0, the human opens the artifact directory and reviews the 12 screenshots per the ADR-010 verification gate.

### Why split, not pure Playwright

Three reasons drive the split, not a "do both because you can" argument:

1. **Failure mode separation.** A parser crash and a styling regression are different kinds of bugs and benefit from different signals. The HTTP-protocol test fails fast and unambiguously: "Chapter X's parser exploded, see the traceback." The Playwright test asserts on rendered DOM/visual structure. Crashing the harness at the protocol layer when a Chapter blows up the parser keeps the Playwright run focused on the Chapters that actually produced HTML to look at.

2. **Speed of feedback.** TestClient tests run in milliseconds; Playwright tests run in seconds (browser startup, page navigation, screenshot capture). When a parser bug surfaces, the implementer wants the protocol-level red lights immediately. Putting the HTTP-200 gate behind Playwright's browser launch slows iteration unnecessarily.

3. **Boundary fidelity to ADR-010.** ADR-010 explicitly draws the boundary: "HTTP-protocol shape checks: `assert response.status_code == 200`, `assert 'text/html' in content-type`, body-length sanity … remain `TestClient`-based." A pure-Playwright harness would route HTTP-200 assertions through a browser session for no architectural benefit and against ADR-010's commitment.

### Why not the CLI render-all tool

Adding `python -m app.render_all` would introduce a new code surface (a CLI module under `app/`) for which no current task forces a use case. ADR-010 already commits the project to in-test artifact production; the "render all 12 to tmp" workflow is satisfied by the Playwright artifact directory. A separate CLI also splits the verification path: the harness would either duplicate effort with the in-test artifacts or replace them, and the latter contradicts ADR-010's gate. Out of scope.

### What this ADR does *not* decide

- **The exact pytest parametrize fixture shape.** `pytest.mark.parametrize("chapter_id", [...])` vs a fixture-driven sweep is implementer choice; the architect commits to "all 12 Chapter IDs are walked," not to the parametrize syntax.
- **Whether the HTTP smoke test asserts on per-Chapter content beyond the M/O badge and at least one Section anchor.** Heavier per-Chapter content assertions belong to the Playwright layer (rendered DOM) or to focused follow-up tasks targeting a specific bug class (the latent-bug triage that ADR-015 commits to). The smoke layer stays light.
- **Per-test screenshot viewport size.** Falls back to ADR-010's default (Playwright default 1280x720) unless the implementer pins a different value in `pytest.ini`.
- **Whether the existing Chapter-1-only tests are deleted.** They stay; this ADR adds the multi-chapter pass alongside the existing per-Chapter coverage. Chapter 1 appears in the new 12-Chapter set as a regression check.

## Alternatives considered

**A. Pure Playwright batch test (Option (a) above).**
Rejected. Routes HTTP-protocol assertions through a browser session for no architectural benefit (ADR-010's boundary explicitly puts protocol checks in pytest). Also, when a parser bug crashes a Chapter, the Playwright layer's failure signal is "page navigation produced a non-2xx response" — the same information the TestClient would surface in 100x less time. The split is strictly better at no extra architectural cost.

**B. CLI render-all tool (Option (c) above).**
Rejected. Introduces a new code surface (`app/render_all.py`) and a second verification workflow (offline file review) competing with ADR-010's in-test artifact directory. No current task forces a CLI use case, and the verification gate is already satisfied by the Playwright artifact directory the human reviews. Adds maintenance for no current consumer.

**C. Single parameterized test mixing TestClient HTTP-200 and Playwright screenshots in one body.**
Rejected. Couples the two failure modes — a TestClient HTTP-200 failure and a Playwright screenshot-capture failure now share one test ID. Pytest's parametrize-then-collect model handles "12 chapters × 2 modes" as 24 separate test IDs cleanly; folding them into one test loses the per-mode signal in CI/output and complicates per-mode `xfail`/skip logic.

**D. HTTP-protocol smoke test only; defer Playwright screenshots to a later task.**
Rejected. TASK-005 AC-2 explicitly requires 12 screenshots for the human's per-Chapter visual review. Deferring the Playwright layer would leave AC-2 unmet and would defer the actual point of the validation pass (human eyeballs on every Chapter). The HTTP-200 layer alone confirms "no crash" but not "consumable surface" — the manifest §3 motivation requires the latter.

**E. Playwright-only (drop the HTTP-protocol layer entirely).**
Considered. Saves a few minutes of test-writing. Rejected because the HTTP-protocol layer is the smallest unit that catches the most-likely failure mode (parser crash on an unvisited Chapter) and produces the fastest feedback. A multi-second-per-Chapter Playwright pass that fails with a page-navigation error on Chapter 7 leaves the implementer slower to diagnose than a sub-second TestClient parametrize that surfaces the same crash with a Python traceback.

## My recommendation vs the user's apparent preference

**Aligned with the task's stated recommendation.** TASK-005's "Architectural decisions expected" section explicitly recommends Option (b), "for separation of concerns + speed of feedback." The architect agrees on the merits — the boundary is a direct consumption of ADR-010's existing protocol-vs-DOM split, and the speed-of-feedback argument is real. No pushback.

The architect's only mild push: **the HTTP smoke layer should stay deliberately light.** Heavier rendered-content assertions belong in Playwright (where the assertions exercise the live DOM) or in focused follow-up tasks (where a specific bug class drives a targeted test). Letting the smoke layer grow to "assert on every callout, every table, every Section heading" pulls it back toward the grep-HTML failure pattern ADR-010 was drafted to eliminate. The two checks committed above (M/O badge text + at least one `<section id="` substring) are the floor and the ceiling for the smoke layer in this ADR.

## Consequences

**Becomes possible:**

- A repeatable, fast (ms-scale) smoke gate against the entire Chapter corpus that catches parser-crash regressions before they reach the browser. Future TASK-NN can extend the parametrize list with one line per new Chapter.
- A repeatable visual-validation pass producing 12 last-run screenshots per ADR-010, reviewable by the human in one sitting.
- A clean signal during the validation pass for which Chapters crash (HTTP-protocol failures) vs which Chapters render but look wrong (Playwright failures or human-review findings).
- Future Chapter additions (e.g., a recovered Chapter 8 source, or new Optional MIT OCW additions) get covered by extending one parametrize list in each layer — no architectural change.

**Becomes more expensive:**

- Two new test files (one per layer). Bounded scope; both are parametrize-driven, ~60–120 lines combined.
- Test-suite runtime grows by 12 Playwright-driven page loads (~5–10 seconds per typical Playwright workstation). Within the budget ADR-010 already committed to.
- Maintenance: when a new Chapter is added or a Chapter ID changes (ADR-005 rename event), both parametrize lists update. Acceptable; one point of duplication per layer.

**Becomes impossible (under this ADR):**

- A multi-chapter validation pass that ships without a fast HTTP-200 smoke gate (TestClient layer).
- A multi-chapter validation pass that ships without 12 screenshots for the human's per-Chapter review (Playwright layer).
- Routing HTTP-protocol assertions through a browser session — ADR-010's boundary is reaffirmed.

**Supersedure path if this proves wrong:**

- If the HTTP-protocol smoke layer is consistently green while Playwright catches all the bugs anyway, a future ADR can drop the smoke layer (and the architect would learn that the speed-of-feedback argument was less load-bearing than the architectural-boundary argument). The smoke layer is cheap to remove.
- If the visual-screenshot review surfaces a need for finer per-Chapter rendered-DOM assertions, a future ADR can add a third layer (per-Chapter Playwright assertions targeting specific elements) without restructuring the existing two layers.
- If the project ever adopts CI, the parametrize lists carry over identically; CI's only new commitment is `playwright install chromium` per runner, which is already ADR-010's per-workstation rule.

## Manifest reading

Read as binding for this decision:

- **§3 Primary Objective ("drive consumption … via per-Chapter Lectures and Notes").** Bound the requirement that all 12 Chapters be exercised, not just sampled.
- **§5 Non-Goals:** "No remote deployment" — bounds the harness to local execution. "No mobile-first" — bounds the screenshot viewport to desktop default. "No LMS features" — irrelevant to harness shape.
- **§6 Behaviors and Absolutes:** "Mandatory and Optional content are honored everywhere" — the smoke layer's per-Chapter M/O badge assertion is a direct enforcement of this invariant on every Chapter (not just Chapter 1).
- **§7 Invariants:** "Mandatory and Optional are separable in every learner-facing surface" — the M/O badge assertion confirms separability at every Chapter's rendered output.

No manifest entries flagged as architecture-in-disguise. The manifest is silent on test-harness shape by design; the silence is correct.

## Conformance check

- **MC-1 (No direct LLM/agent SDK use).** Not touched. The harness is browser/HTTP only; no AI surface.
- **MC-2 (Quizzes scope to exactly one Section).** Not touched (no Quiz code).
- **MC-3 (Mandatory/Optional designation respects the canonical mapping).** *Strengthened.* The smoke-layer per-Chapter M/O badge assertion enforces the canonical mapping at the rendered-output boundary on every Chapter, not just Chapter 1. The Playwright layer's screenshots give the human a 12-row visual confirmation surface.
- **MC-4 (AI work asynchronous).** Not touched.
- **MC-5 (AI failures surfaced).** Not touched.
- **MC-6 (Lecture source read-only).** *Honored.* The smoke layer reads `content/latex/` via the existing `render_chapter()` path (read-only); the Playwright layer reads via the live FastAPI app (same path). No write paths added.
- **MC-7 (Single user).** *Honored.* One `live_server` fixture instance per session; no per-user state.
- **MC-8 (Reinforcement loop).** Not touched (no Quiz code).
- **MC-9 (Quiz generation user-triggered).** Not touched.
- **MC-10 (Persistence boundary).** Dormant; no DB introduced.

UI-skill rules (`ui-task-scope`):
- **UI-4 (UI surfaces must have rendered-behavior tests).** *Honored* — both layers add tests for the multi-chapter Lecture surface.
- **UI-5 (Verify pass requires browser eyeballing).** *Honored* via ADR-010's screenshot-review portion of the gate.
- **UI-6 (Reviewer walks rendered surface).** *Honored* via the audit Human-gates row format ADR-010 commits to.

Authority-state rules (`authority-state-check`):
- **AS-1..AS-7.** Honored. ADR-013 is `Proposed`. ADR-010 is consumed without modification. No ADR is silently superseded.

No previously-dormant rule is activated by this ADR.
