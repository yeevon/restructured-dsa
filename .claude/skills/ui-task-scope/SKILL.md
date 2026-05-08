---
name: ui-task-scope
description: Guardrails for tasks that ship user-facing HTML — navigable surfaces, layout-bearing templates, multi-page consistency. Use when proposing or designing a task that introduces DOM, when implementing template changes, when writing or reviewing tests for a route that returns HTML, or when verifying a UI task. Reports gaps only; does not auto-fix.
---

# UI task scope

This skill is invoked when a task ships an actual user-facing HTML surface — a page, a layout, a navigation control, a multi-page consistency mechanism. It does not apply to internal API responses, content-transformation pipelines whose output is consumed by other code, or tasks that touch templates only to fix non-visual bugs.

**Authority of this skill:** operational instruction (Tier 2). It does not introduce architectural claims. Concrete names — which CSS file, which class names, which test framework — come from the ADRs the rules cite, never from this file. If a rule's backing ADR does not yet exist, the rule notes "ADR pending" and the architecture portion is **dormant**. The UI test framework question (UI-4) is settled at the project level by ADR-010 (Playwright via `pytest-playwright` with last-run screenshot artifacts); UI-5 and UI-6's "rendered-surface verification" is satisfied through that mechanism.

## When to invoke

- **Architect (Mode 1, /next):** when proposing a task whose Goal or ACs include rendering, navigating, displaying, or laying out HTML for a learner.
- **Architect (Mode 2, /design):** when drafting an ADR whose Decision section names a route that returns HTML, a template, a layout pattern, or a class-name convention.
- **Implementer (/implement):** before declaring run-complete on any task that modifies files under `app/templates/` or any CSS file, or that adds new HTML-returning routes.
- **Test-writer (/implement Phase 1):** when writing tests against a route that returns HTML.
- **Reviewer (/review):** when the staged diff includes any template, CSS, JS, or HTML-returning route change.
- **Orchestrator (/implement Phase 3 verify):** when the task being verified is a UI task (per the Goal / ACs).

## Output format

Walk the rules below against the artifact in question (task file, ADR, code diff, test file, rendered page). Produce a structured gap report:

```
RULE: <id>
WHERE: <task file | ADR-NNN | file:line | rendered surface>
EVIDENCE: <quoted excerpt or finding>
SEVERITY: blocker | warn | dormant (ADR pending)
TRACE: <ADR-NNN, manifest §, or "convention not yet ADR-backed">
```

Lead the report with a count summary: `N blockers, M warnings, K dormant`. If zero gaps, say so explicitly.

## Rules

### UI-1 — Task scope must declare styling responsibility

A task that introduces a user-facing HTML surface must explicitly state that styling and layout are part of the deliverable, unless styling is deliberately deferred to a named follow-up task.

The task does **not** need to name the exact CSS file or class names unless those are already defined by an Accepted ADR. If the styling target is not yet ADR-backed, the task must list "styling scope" as an expected architecture decision for `/design`, ensuring the question is not silently dropped between phases.

Silence on styling is not acceptable. A task that ships layout-bearing DOM without declaring whether styling is in scope is half-implementation by construction.

- **Severity:** **blocker** when the task ACs introduce navigable layout but say nothing about styling scope (neither in-scope, nor deferred to a named follow-up, nor surfaced as a `/design`-time decision).
- **Trace:** UI task completeness convention surfaced by this skill. If an Accepted ADR fixes the CSS file or styling convention, cite it; otherwise this rule is operational, not architectural — it forces the styling question to be answered, not what the answer must be.

### UI-2 — ADR Decision section must scope CSS

An ADR whose Decision section introduces or modifies a user-facing HTML surface (route, template, layout) must specify the styling scope: which CSS file is edited, which class-name namespace the new templates use, and whether existing CSS rules are sufficient. An ADR that describes a rail / panel / page / layout without naming where its CSS rules live is incomplete.

- **Severity:** **blocker** when the ADR's Decision section introduces UI mechanism without scoping its styling.
- **Trace:** convention not yet ADR-backed; may be reinforced by a task AC or Accepted ADR that explicitly requires visible distinction or specific styling. Cite that source if it exists; otherwise this skill is the operational evidence, not product authority. Do not infer styling requirements from broad manifest invariants.

### UI-3 — Implementer must edit CSS for new layout-bearing templates

The implementer's run summary for a UI task must name which CSS file was edited and which new class rules were added. Adding class names to templates without corresponding CSS rules is half-implementation; the page renders as unstyled markup. If the ADR named the CSS file as the styling target, the implementer's diff must touch that file.

- **Severity:** **blocker** when the staged diff adds template classes (`.foo-bar`, `.baz-quux`) for which no rule exists in any project CSS file.
- **Trace:** the CSS file named by UI-1 / UI-2.

### UI-4 — UI surfaces must have rendered-behavior tests per ADR-010

Tests for a route that returns HTML for a user must include rendered-behavior verification, not just `TestClient` HTML-string assertions. A `TestClient` test confirming `"Mandatory"` appears in the response body verifies markup, not behavior. Rendered-behavior tests verify properties a user actually depends on: link reachability, visible layout integrity, role-and-name reachability, navigability across pages.

The project-wide answer to *how* rendered-behavior verification happens is **ADR-010**: Playwright via `pytest-playwright`, with rendered-DOM-content assertions written under `tests/playwright/` and run as part of `python3 -m pytest tests/`. UI tasks do not re-decide between framework options on a per-task basis — they cite ADR-010 and add Playwright tests for the new surface. New `string in body` assertions are not an acceptable substitute for new UI work.

- **Action for any UI task:** the test-writer adds at least one Playwright test under `tests/playwright/` covering each visual AC. If a task ships UI without Playwright coverage of its rendered-behavior ACs, the test-writer raises `PUSHBACK:` and stops.
- **Action if a UI task has a strong reason to defer rendered-behavior testing to a named follow-up:** the deferral must be justified in the task file and explicitly accepted by the human; this produces a **warning**, not a blocker. Silent deferral is not allowed.
- **Severity:** **blocker** when a UI task ships without Playwright coverage of its rendered-behavior ACs and no justified deferral is recorded; **warn** when a justified deferral is on record.
- **Trace:** ADR-010 (UI verification mechanism — Playwright via `pytest-playwright`). Don't silently ship UI without rendered verification.

### UI-5 — Verify pass requires human visual confirmation of the rendered surface

The /implement verify phase for a UI task is not satisfied by `curl` + `grep` + structural HTML assertions, and is not satisfied by Playwright tests passing alone. A human must visually confirm that the rendered surface is usable: the layout renders, controls are reachable, navigation works, the styling makes the affordance visible. The default mechanism under ADR-010 is **the human reviews the last-run Playwright screenshots** under the artifact directory ADR-010 names; opening the rendered page directly in a browser remains an available substitute when the human prefers it. The load-bearing requirement is that a human eyeballs the surface — not which channel they eyeball it through. If the orchestrator cannot trigger either path, it must say so explicitly and require the human to perform the visual check before reporting verify-pass.

- **Severity:** **blocker** when the verify-phase report claims success on a UI task without naming either screenshot review or direct browser inspection by the human.
- **Trace:** ADR-010 (verification gate — Playwright tests pass + human reviews last-run screenshots); operational verification rule for UI work; may be mirrored in `CLAUDE.md` or in reviewer/orchestrator prompts.

### UI-6 — Reviewer of a UI task must confirm rendered-surface verification

The reviewer's protocol for a UI task includes confirming that the rendered surface has been visually checked, not just that the staged diff is structurally correct. Under ADR-010 this confirmation is satisfied by an audit Human-gates row of the form `rendered-surface verification — pass` (Playwright tests green; screenshots reviewed by the human). Equivalent direct browser inspection by the human, recorded in the same row format, is also acceptable. ADR fidelity for a UI ADR includes "does the implementation produce the affordance the ADR's Decision section describes," not only "does the diff add the right files."

- **Severity:** **blocker** in the reviewer's verdict when the staged diff is a UI task and no audit row marked `rendered-surface verification — pass` is present, or when no equivalent record of human visual confirmation exists.
- **Trace:** ADR-010 (verification gate and audit-row format); UI-5 by analogy (rendered verification is the load-bearing observation; reviewer is one of the roles obligated to confirm it occurred).

## Notes

- This skill does not name a specific CSS architecture or styling pattern; those decisions are architectural and live in ADRs. The skill enforces *that* such decisions are made and recorded.
- The UI test framework question (UI-4) is settled at the project level by ADR-010 (Playwright via `pytest-playwright`, with last-run screenshots saved to a gitignored artifact directory). UI tasks cite ADR-010 by reference; they do not re-decide the framework. If a future UI task surfaces evidence that ADR-010 is unfit for some surface, the architect proposes a supersedure ADR — the skill does not route around the accepted decision.
- Half-implementation patterns this skill specifically catches: class names with no CSS rules; UI tasks shipped with `string in body` assertions in place of Playwright rendered-DOM assertions; verify reports based on `curl` output or pytest-only test output without human visual confirmation; reviewers who walk AC compliance without confirming a `rendered-surface verification — pass` audit row.
