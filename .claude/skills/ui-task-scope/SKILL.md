---
name: ui-task-scope
description: Guardrails for tasks that ship user-facing HTML — navigable surfaces, layout-bearing templates, multi-page consistency. Use when proposing or designing a task that introduces DOM, when implementing template changes, when writing or reviewing tests for a route that returns HTML, or when verifying a UI task. Reports gaps only; does not auto-fix.
---

# UI task scope

This skill is invoked when a task ships an actual user-facing HTML surface — a page, a layout, a navigation control, a multi-page consistency mechanism. It does not apply to internal API responses, content-transformation pipelines whose output is consumed by other code, or tasks that touch templates only to fix non-visual bugs.

**Authority of this skill:** operational instruction (Tier 2). It does not introduce architectural claims. Concrete names — which CSS file, which class names, which test framework — come from the ADRs the rules cite, never from this file. If a rule's backing ADR does not yet exist, the rule notes "ADR pending" and the architecture portion is **dormant**.

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

### UI-4 — UI surfaces must have rendered-behavior tests

Tests for a route that returns HTML for a user must include rendered-behavior verification, not just `TestClient` HTML-string assertions. A `TestClient` test confirming `"Mandatory"` appears in the response body verifies markup, not behavior. Rendered-behavior tests verify properties a user actually depends on: link reachability, focus order, visible layout integrity, navigability across pages.

- **Action when no UI test framework exists in the project:** test-writer raises `PUSHBACK:` and stops **unless** the task already includes one of the following explicit gates. The architect (or human) must choose one:
  1. add a UI test framework via ADR before the task proceeds (Playwright, Selenium, or equivalent — the choice is architectural and lives in an ADR);
  2. add **manual browser verification** as a required acceptance gate for this task — explicitly named in the task ACs, and explicitly captured in the Human-gates table when verified;
  3. defer rendered-behavior testing to a named follow-up task — produces a **warning**, not a blocker, and must be justified in the task file.
- **Severity:** **blocker** when the task is a UI task and none of (1)/(2)/(3) is present; **warn** when option (3) is chosen and justified.
- **Trace:** convention surfaced by this skill. Don't silently ship UI without rendered verification.

### UI-5 — Verify pass requires browser eyeballing

The /implement verify phase for a UI task is not satisfied by `curl` + `grep` + structural HTML assertions. The orchestrator (or human) must open the rendered page in a browser and confirm the surface is usable: the layout renders, controls are clickable, navigation works, the styling makes the affordance visible. If the orchestrator cannot open a browser, it must say so explicitly and require the human to eyeball before reporting verify-pass.

- **Severity:** **blocker** when the verify-phase report claims success on a UI task without naming a browser inspection step.
- **Trace:** operational verification rule for UI work; may be mirrored in `CLAUDE.md` or in reviewer/orchestrator prompts.

### UI-6 — Reviewer of a UI task must walk the rendered surface

The reviewer's protocol for a UI task includes opening the rendered page (or describing the rendered surface from a screenshot the human supplies) and confirming the staged diff produces a usable result, not just a structurally-correct HTML response. ADR fidelity for a UI ADR includes "does the implementation produce the affordance the ADR's Decision section describes," not only "does the diff add the right files."

- **Severity:** **blocker** in the reviewer's verdict when the staged diff is a UI task and no rendered-surface check is present in the review.
- **Trace:** UI-5 by analogy (rendered verification is the load-bearing observation; reviewer is one of the roles obligated to make it).

## Notes

- This skill does not name a specific UI test framework, CSS architecture, or styling pattern. Those decisions are architectural and live in ADRs. The skill enforces *that* such decisions are made and recorded; it does not make them.
- If the project has not yet adopted a UI test framework, UI-4 lets early UI work proceed via the manual-browser-verification gate or a named-follow-up deferral, while still preventing silent ship. The framework decision is not forced on the first UI task; it is forced as soon as the manual gate stops being sustainable.
- Half-implementation patterns this skill specifically catches: class names with no CSS rules; templates with no rendered verification; verify reports based on `curl` output alone; reviewers who walk AC compliance without walking the rendered surface.
