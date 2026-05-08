# ADR-009: UI verification gate — manual desktop-browser inspection as a named acceptance gate; no UI test framework introduced

**Status:** `Rejected`
**Date:** 2026-05-08
**Task:** TASK-003
**Resolves:** none (no project_issues filed against this question; surfaced as an architectural decision the `ui-task-scope` skill UI-4 forces every UI task to make until a project-wide commitment lands)
**Supersedes:** none

**Human gate (2026-05-08):** Rejected. Human directed UI-4 option 1 (introduce a UI test framework) instead of option 2 (manual-browser gate). Direction was: "would like to implement playwrite now, we can get rid of grep html test and redo them with playwrite instead, we can save last test run for validation with screen shots, results should be in gitignore when i start pushing this to a repo." This file is preserved on disk for history per CLAUDE.md rejection-handling rule. The replacement decision is recorded in a new ADR drafted by the architect (see architecture.md "Proposed ADRs" table).

## Context

The `ui-task-scope` skill (`.claude/skills/ui-task-scope/SKILL.md`) rule UI-4 requires every task that ships HTML for a learner to choose one of three rendered-behavior verification gates:

1. **Introduce a UI test framework via ADR** (Playwright, Selenium, Cypress, or equivalent) before the task proceeds. Heavyweight architectural commitment that affects every future UI task.
2. **Add manual browser verification as a required acceptance gate** for this task — explicitly named in the task ACs and explicitly captured in the audit Human-gates table when verified.
3. **Defer rendered-behavior testing to a named follow-up task** — produces a `warn` finding, not a blocker, and must be justified.

UI-4 is the rule whose violation produced the TASK-002 silent-ship failure: the orchestrator declared verify-pass on `curl + grep` output, the rendered surface was a wall of unstyled text, and the rail never reached the human's eyes before the work was claimed done. The `audit-honesty` and `test-honesty-check` skills (TH-5) and orchestrator-memory note (`feedback_ui_tasks_need_browser_verify.md`) all reinforce: a UI task is not done until the rendered surface has been eyeballed in a real browser.

TASK-003's task file recommends option 2 (manual-browser gate) and explicitly rejects option 1 as a "heavyweight architectural commitment that should be commissioned by a task that needs it broadly, not sneaked in here." This ADR ratifies that recommendation, scopes it as a project-wide convention until a future ADR supersedes it, and names exactly what the manual-browser gate looks like (so the gate is a defined contract, not a vague "look at it in a browser").

The decision is genuinely architectural even though it does not introduce a tool, because:
- It commits the project to a verification *rhythm* (the human must open a browser, not the orchestrator) for every UI task going forward, until superseded.
- It defines the failure mode (orchestrator declares verify-pass without a browser-eyeball gate → blocker per UI-4 / UI-5 / UI-6).
- It positions a future supersedure path (a UI-test-framework ADR) explicitly, so the project knows what would justify the supersedure.

The manifest constrains this decision through §3 (consumption — verification has to confirm the surface is actually consumable, not merely returns 200), §5 (no remote deployment, no LMS — the project's deliverable surface is "what one human sees in one local browser," which makes manual gating cheap and sustainable), §7 (no learner-facing surface obligations beyond what the manifest's invariants require). No manifest entry directly forces a particular verification mechanism — UI-4 is operational, not a manifest invariant — but the manifest's primary objective indirectly motivates *some* gate that prevents shipping unconsumable surfaces.

## Decision

### The gate

For any task that ships a user-facing HTML surface, the verification gate is **manual desktop-browser inspection by the human**, recorded as a row in the task's audit Human-gates table.

The gate is satisfied when **all** of the following hold:

1. The human runs the project's run command (`uvicorn app.main:app --host 127.0.0.1 --port 8000` per CLAUDE.md) and the application starts without error.
2. The human opens `http://127.0.0.1:8000/` (the landing page; ADR-006) in a desktop browser and visually confirms each visual acceptance criterion in the task file is satisfied. "Desktop browser" means any of: a current Chromium-derived browser (Chrome, Edge, Brave), a current Gecko browser (Firefox), or a current WebKit browser (Safari) — running on the human's primary workstation.
3. The human opens at least one Lecture page (`http://127.0.0.1:8000/lecture/{chapter_id}` for some chapter the task touches; minimum one page) and visually confirms the same.
4. The human appends a row to the task's audit Human-gates table with `Gate: rendered-surface inspection` and `Result: pass` or `Result: fail — <one-line reason>`. A `fail` result blocks the commit and routes back to the implementer (or back to `/design` if the failure is architectural).

### What the gate is *not*

- **The gate is not satisfied by `curl` + `grep` output.** Structural HTML inspection (response code, class names present, hrefs resolve) is necessary but not sufficient. UI-5 makes this explicit; this ADR is the architectural backstop for UI-5.
- **The gate is not satisfied by the orchestrator alone.** Even if a future orchestrator is given browser-driving tools, the human must be the one whose eyes confirm the surface. (This is a manifest §5 / single-user constraint as much as an architectural one: there is no second human to delegate verification to.)
- **The gate is not a screenshot review.** A screenshot can be misleading (rendered at a different viewport, missing a hover state, hiding a CSS load failure that was masked by browser cache). The gate is a live browser interaction.
- **The gate does not require an automated test.** The project does not have a UI test framework, and this ADR does not introduce one (see Alternative B below).

### Who is obligated, and where

- **Architect (Mode 1, `/next`)** when proposing a task that ships HTML for a learner: name the manual-browser gate explicitly in the task's "Verify" section and as a checkbox-style AC. Do not propose a UI task without naming the gate.
- **Architect (Mode 2, `/design`)** when drafting an ADR whose Decision section introduces or modifies a user-facing HTML surface: do not silently default to "look at it in a browser." Either cite this ADR (the project's standing convention) or propose a different gate via a new ADR. Silence is a UI-4 blocker.
- **Implementer (`/implement`)** when producing the diff: do not declare run-complete. The implementer's run finishes when the diff is staged and the test suite is green; the gate happens *after* the implementer's run, gated by the human.
- **Orchestrator (`/implement` Phase 3 verify)** when verifying a UI task: do not declare verify-pass on CLI output. The verify-phase report must explicitly say "manual-browser gate required; routing to human" and name this ADR. The orchestrator's verify-phase report is *not* the gate; it is the routing of the gate to the human.
- **Reviewer (`/review` Phase 4)** when reviewing a UI task: confirm in the verdict that the audit Human-gates table contains the rendered-surface row marked `pass`. A staged commit on a UI task without that row is a review blocker.
- **Human:** is the gate. Their browser inspection is the verification. Their audit row is the record.

### Audit row format

The Human-gates table row added by the human is:

```
| <ISO timestamp> | rendered-surface inspection | pass | <free-text observations, ≤1 line>
```

Or, on failure:

```
| <ISO timestamp> | rendered-surface inspection | fail — <one-line reason> | <follow-up: route to implementer / route to /design>
```

The `Notes` cell in the `pass` case may be empty or carry a brief observation ("rail visible at 1440x900; M/O distinguishable; hover state visible on Chapter rows"). The `Notes` cell in the `fail` case must name the failure concretely enough that the next agent (implementer or architect) can act on it.

### Project-wide convention scope

This ADR's gate applies to **every task that ships a user-facing HTML surface**, not only TASK-003. Future UI tasks (e.g., Notes UI, Quiz UI, Notification chrome) honor this convention without re-deciding it; the architect's `/design` for those tasks may cite ADR-009 by reference rather than re-arguing the gate.

If a future UI task introduces enough surface area that the manual-browser gate becomes unsustainable for the human (e.g., a single change touches 30 pages and the human cannot reasonably eyeball all 30 each cycle), that pressure is the trigger for a UI-test-framework ADR (Alternative A below) to supersede this one. Until then, the manual gate is the project's commitment.

### Scope of this ADR

This ADR fixes only:

1. The verification mechanism (manual desktop-browser inspection by the human).
2. The audit row format that records the gate's outcome.
3. The list of agents/roles obligated to honor or route the gate.
4. The supersedure trigger (manual gate becomes unsustainable → propose a UI-test-framework ADR).

This ADR does **not** decide:

- Which specific browser the human uses. Any current desktop browser of the chromium/gecko/webkit families is acceptable.
- Whether screenshots are attached to the audit row. The architect leaves this as a human-discretion option; not required.
- The viewport size at which the gate is performed (manifest §5: no mobile-first; the human's natural desktop viewport is the floor).
- A specific UI test framework. That is a future ADR's commitment if and when this one is superseded.
- Whether the manual gate is sufficient for accessibility verification (WCAG, ARIA, color-contrast). It is not, but accessibility audit is out of scope for this ADR and for TASK-003 (per the task's "Out of scope" section).

## Alternatives considered

**A. Introduce a UI test framework via ADR — Playwright, Selenium, or Cypress — and make rendered-behavior tests automated.**
Rejected for now. A UI test framework is a substantial architectural commitment:
- Adds a new dependency (the framework + browser drivers).
- Adds a new test-run mode (browser-based tests typically run separately from unit tests, often slower).
- Requires CI / local-test orchestration (the human's `python3 -m pytest tests/` would need to invoke or be paired with a UI runner).
- Imposes a maintenance burden on every future UI change (the test must update with the surface).

The trigger for adopting a UI test framework is "the manual gate stops being sustainable." Today the project has 12 chapters, 1 user, 2 surfaces (`GET /` + Lecture pages). Manual eyeballing takes the human under a minute per cycle. The cost of the framework would dwarf the value at this scope. When the surface area grows (Notes UI, Quiz UI, Notification chrome, multi-page workflows), this ADR is superseded by a UI-test-framework ADR commissioned by the task that first hits the unsustainable threshold.

**B. Defer rendered-behavior testing entirely to a named follow-up task.**
Rejected. UI-4 option 3 is allowed for cases where the surface being shipped does not yet have visual stakes (e.g., a structural-only template change with no styling implications). TASK-003 does have visual stakes — visual stakes are the entire point of the task. Deferring would re-create the silent-ship failure mode TASK-002 fell into. UI-4 option 3 is rejected for any task whose ACs include visual outcomes.

**C. Make the orchestrator the verification gate (orchestrator opens a browser via tool, takes a screenshot, attaches to audit).**
Rejected. The orchestrator does not have reliable browser-driving tools available; even if it did, a screenshot is a static snapshot that cannot exercise hover state, focus order, click-to-navigate, or browser-resize behavior. The orchestrator's role is to *route* verification to the human, not to *perform* it. UI-5's "if the orchestrator cannot open a browser, it must say so explicitly and require the human to eyeball" is the operational version of this ADR's stricter "the orchestrator never performs the gate" rule.

**D. Make the gate a peer-review step (a second human reviews a screenshot or video).**
Rejected. Manifest §5 (single-user) and §3 (this is a personal project for one author) make a peer-review structure pointless. The human author is the only verifier the project has.

**E. Make the gate a CSS-snapshot-test (Stylelint + a snapshot of the rendered HTML).**
Rejected. Snapshot tests catch *changes*, not *correctness*. A snapshot of an unstyled wall of text would be locked in as the ground truth on the next commit, baking in the bug rather than catching it. Snapshots are a useful supplementary tool *after* a known-good rendered surface is committed; they are not a substitute for the initial eyeball that establishes the known-good state.

**F. Tie the gate to a CI check (rendered HTML compared against a reference image generated by the framework in Alternative A).**
Rejected. Strictly larger than Alternative A (CI infrastructure on top of a UI framework). The project has no CI today (no `.github/workflows/`, no equivalent); manifest §5 (no remote deployment) makes CI infrastructure low-priority. If the project later adopts CI for unit tests, a future ADR can fold UI snapshots in.

## My recommendation vs the user's apparent preference

The task file (TASK-003) explicitly recommended this gate: "the recommended choice for this task is option 2 (manual-browser gate) — option 1 is a heavyweight architectural commitment that should be commissioned by a task that needs it broadly, not sneaked in here." This ADR is aligned with the task's recommendation and with the human's apparent direction (no signal in the project history that the human wants automated UI testing now).

I am NOT pushing back on:
- The choice of option 2 over option 1 (aligned).
- The scope of "manual desktop-browser inspection" (matches the task's "Verify" section).
- The audit-row recording mechanism (matches the existing Human-gates table convention).
- The project-wide-convention scope of this ADR (extends beyond TASK-003 because every future UI task hits UI-4 the same way; this ADR makes that explicit so future architect runs cite this rather than re-decide).

The only mild push I want on the record: **the supersedure trigger should be a real signal, not "we got bored of eyeballing."** A future architect facing "the human is tired of looking at the page" is *not* the trigger for a UI-test-framework ADR; "the page count exceeds what the human can eyeball reliably in one session" is. This ADR records the trigger explicitly so the future supersedure has the right justification.

## Manifest reading

Read as binding for this decision:
- §3 Primary Objective ("drive consumption … via per-Chapter Lectures and Notes"). Bound the requirement that verification confirm the surface is *actually consumable*, not merely returns 200. The manual gate is the cheapest mechanism that produces that signal at the project's current scope.
- §5 Non-Goals: "No mobile-first product" bounds the gate to desktop-browser only. "No remote deployment" bounds the gate to the human's local workstation. "No LMS features" / "No multi-user features" bounds the verifier population to one (the human author); peer-review structures are pointless.
- §6 Behaviors and Absolutes: "AI failures are visible." Bound by analogy: rendering failures (not AI failures, but the same fail-loudly principle) must be visible to the human. The manual gate makes them visible.
- §7 Invariants: "Mandatory and Optional are separable in every learner-facing surface." Bound the gate's content (the human must confirm the M/O split is visually parseable); ADR-008 specifies the visual mechanism, this ADR specifies that the human verifies it.

No manifest entries flagged as architecture-in-disguise. This decision is genuinely operational-architectural (it commits the project to a verification *rhythm*); the manifest is silent on verification mechanisms by design.

## Conformance check

- **MC-1 / MC-2 / MC-4 / MC-5 / MC-7 / MC-8 / MC-9.** Not touched (no AI work, no Quiz, no auth, no DB).
- **MC-3 (Mandatory/Optional designation respects the canonical mapping).** Not touched directly, but the manual gate verifies that the M/O split is visually honored — the gate is a live check on MC-3 compliance at the rendered-surface level. Compliance preserved (the gate strengthens it).
- **MC-6 (Lecture source is read-only to the application).** Not touched (the gate does not write to `content/latex/`; running `uvicorn` against `content/latex/` is read-only).
- **MC-10 (Persistence boundary).** Not touched (no DB, no persistence).
- **UI-4 (rendered-behavior verification gate).** Satisfied by this ADR. UI-4 option 2 (named manual-browser gate) is the chosen mechanism; this ADR is the architectural backstop that names the gate as a project-wide convention.
- **UI-5 (verify-pass requires browser eyeballing).** Reinforced by this ADR. The orchestrator's `/implement` Phase 3 verify report routes to the human rather than declaring verify-pass; this ADR makes the routing the project's standing convention.
- **UI-6 (reviewer walks the rendered surface).** Reinforced by this ADR. The reviewer's verdict checks for the audit row that records the gate's outcome; absence of the row is a review blocker.
- **AS-1 / AS-2 / AS-3 / AS-4 / AS-5 / AS-6 / AS-7 (authority-state-check).** This ADR enters as `Proposed`; will be added as a row in `architecture.md`'s "Proposed ADRs" table on Write; moves to "Accepted ADRs" on the human gate. State-coherence preserved.
- **AA-1 through AA-6 (audit-append-only).** This ADR's audit-row format is consistent with the append-only Human-gates table convention; AA-2 (existing rows immutable) and AA-6 (existing tables fixed) are honored.
- **TH-1 through TH-5 (test-honesty-check).** Indirectly relevant: TH-5 ("tests pass on partial implementation") is the failure mode the manual gate exists to catch. This ADR is the architectural answer to TH-5 for UI work.

Previously-dormant rule activated by this ADR: none.

## Consequences

**Becomes possible:**
- Every future UI task has a defined verification gate; no architect need re-decide it. The architect's job in `/design` for a UI task is reduced from "choose between three UI-4 options and justify" to "cite ADR-009 and move on."
- The orchestrator's `/implement` Phase 3 verify report has a defined route: declare structural verification, name the manual-browser gate, route to the human. No more silent verify-pass on CLI output.
- The reviewer's protocol gains an audit-row check for UI tasks; absence of the rendered-surface row is a defined blocker, not a judgment call.
- The supersedure trigger (manual gate unsustainable) is named explicitly, so a future UI-test-framework ADR has a clear justification path.

**Becomes more expensive:**
- The human must open a browser on every UI task. Cost: under a minute per task at current scope. No new dependency, no new tooling.
- A UI task cannot be committed without the human's manual gate — adding a synchronous human step to the task lifecycle. Mitigation: the human is the project's single user; the gate is a natural moment of "look at what I just shipped" that the human would perform anyway.
- The orchestrator's `/implement` Phase 3 verify report becomes longer (must explicitly route to the human rather than declaring verify-pass).

**Becomes impossible (under this ADR):**
- A UI task that commits without an audit row marked `rendered-surface inspection — pass`. The reviewer is obligated to block.
- A UI task that defaults to `curl + grep` verification and calls itself done. UI-5 already prevents this; this ADR makes the prevention architectural.
- An orchestrator that declares verify-pass on a UI task without naming the manual gate. The orchestrator's verify-phase report is not the gate; the human's audit row is.

**Future surfaces this ADR pre-positions:**
- Notes UI (manifest §8) — verifies via this gate at task ship.
- Quiz UI surfaces — same.
- Notification surface (manifest §8) — same; the manual gate confirms that Notification arrival is *visible* (manifest §6: "AI failures are visible") in the human's browser.
- A future UI-test-framework ADR (whenever the manual gate stops being sustainable) — supersedes this one with a concrete tooling commitment.

**Supersedure path:**
- Trigger: "the human cannot reasonably eyeball every UI surface in one task cycle." Concretely: if a task touches more than ~5 distinct rendered surfaces, or if the project gains a CI loop that wants to gate UI changes automatically, that is the moment.
- A future ADR commits to a specific framework (Playwright, Selenium, etc.), defines the test-run mode, and either replaces the manual gate or makes it the secondary check (with the automated check primary).
- Until that ADR lands, this ADR is in force.
