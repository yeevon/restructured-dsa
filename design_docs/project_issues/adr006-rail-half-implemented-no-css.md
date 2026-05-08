# Project issue: ADR-006 navigation rail is half-implemented — no CSS rules exist

**Status:** Resolved by ADR-008
**Opened:** 2026-05-08
**Opened by:** Human (during TASK-002 post-review re-read)
**Source:** Human inspection of the rendered page after `/review` returned `READY WITH NOTES`. None of the agents (architect, implementer, reviewer) caught it; orchestrator declared verify-pass on `curl` output.

**Resolution note (2026-05-08, `/design TASK-003`):** Resolved by **ADR-008** (Path 2 from the decision tree below — draft a new ADR dedicated to navigation styling, leaving ADR-006 untouched). Architect chose Path 2 over the orchestrator's recommended Path 1 (amend ADR-006 via the AS-1 cycle); rationale recorded in ADR-008's "My recommendation vs the user's apparent preference" section. ADR-008 scopes: a new `app/static/base.css` for page chrome and rail (with `app/static/lecture.css` retained for Lecture-body content); class names preserved as TASK-002 shipped them; M/O visual treatment reuses the existing `designation-mandatory` / `designation-optional` palette; per-row error rows use the existing `.callout-warnbox` palette; empty-state rows are muted; page layout is CSS Grid. **Human accepted ADR-008 on 2026-05-08** (Path 2 ratified — "we can go with path 2 its reasonable").

The verification gate for the rendered surface is settled separately. ADR-009 (manual desktop-browser inspection) was drafted in the same `/design TASK-003` cycle but **Rejected** by the human, who directed UI-4 option 1 (introduce a UI test framework) instead. **ADR-010** (Playwright via `pytest-playwright`, last-run screenshots gitignored) is the replacement, drafted in a follow-up `/design TASK-003` cycle; ADR-010 is `Proposed` and awaits human acceptance. ADR-010 does not resolve this project_issue (the issue is about CSS scoping, which ADR-008 settles); ADR-010 is referenced here only because it is the verification mechanism the implementer will use to confirm this issue's underlying half-implementation is fixed.

## Summary

ADR-006 introduces a left-hand navigation rail rendered via shared `base.html.j2` on `GET /` and on every Lecture page. The implementer added class names to the templates (`.lecture-rail`, `.nav-rail-inner`, `.nav-section-label`, `.nav-chapter-list`, `.nav-chapter-item`, `.nav-chapter-error`, `.nav-chapter-empty`, `.page-layout`, `.page-main`) but never added corresponding rules to any CSS file. The page renders as an unstyled wall of text in a real browser. The 158-test suite passes because every test asserts against HTML structure (class names present, `href` values, response 200) and never against rendered visual behavior.

## Why this is a real architectural question, not a one-line code fix

ADR-006's Decision section names the **mechanism** of the rail (shared `base.html.j2`, included on every Lecture page, both surfaces fed by one helper) but does not scope the **styling responsibility**: which CSS file is edited, what class-name namespace is used, whether existing CSS is sufficient. Adding a CSS file in a follow-up commit without amending ADR-006 leaves the architecture documentation incomplete (`ui-task-scope` rule UI-2 makes this explicit going forward).

## How this slipped through (so the next cycle does better)

- **Architect (Mode 2 / `/design`):** drafted ADR-006 without scoping CSS. Was not yet a known failure pattern.
- **Implementer:** added class names without rules. No skill or rule flagged "templates with classes need rules in some CSS file."
- **Reviewer (`/review` Phase 4):** walked AC compliance, ADR fidelity, conformance — never opened the rendered page.
- **Orchestrator (Phase 3 verify):** ran `uvicorn` + `curl`, grepped for class names, declared "both surfaces render correctly." Confused structure verification with visual verification. Direct `CLAUDE.md` rule violation.

Process artifacts created in response (so this fails differently next time):

- New skill `ui-task-scope` — UI-1..UI-6 cover task scope, ADR scope, implementer CSS edits, rendered-behavior tests, browser verify, reviewer rendered-surface walk.
- New skill `test-honesty-check` — TH-5 (tests pass on partial implementation) catches the suite-passes-while-feature-broken pattern.
- New skill `authority-state-check` — orthogonal to this issue, but tightens the surrounding workflow.
- New skill `audit-append-only` — orthogonal to this issue.
- Updated orchestrator memory: don't claim verify-pass on UI tasks from CLI output alone.

## Decision tree (for whoever takes this up)

1. **Amend ADR-006 to scope CSS.** Revert ADR-006 from `Accepted` to `Proposed` (per `authority-state-check` AS-1's allowed path), add a styling-scope subsection to the Decision section (which CSS file, what class-name namespace), re-gate. Then close this issue by adding the actual CSS rules in a follow-up commit (or as part of TASK-002 closure). Cleanest from "ADR-006 is the complete record" perspective. Forces the gate-paperwork (architecture.md row stays in Accepted? Or moves to Proposed during the amendment? `authority-state-check` AS-3 will catch whichever way is wrong).

2. **Draft ADR-008 specifically for navigation/landing styling.** Leave ADR-006 silent on CSS; ADR-008 covers the styling layer, citing ADR-006 as the mechanism it styles. Less paperwork but readers must combine two ADRs to understand the full navigation surface. Defensible if the project expects future styling-only ADRs as a pattern.

3. **Defer styling to TASK-003 with no ADR change.** Split: TASK-002 ships an unstyled rail, TASK-003 adds CSS. Visibly broken UI in the meantime; loses information about what the navigation surface is supposed to look like. **Not recommended** — the surface is half-deliverable and the project would commit it as "complete."

## Decide when

- Before TASK-002's staged diff is committed. Committing the current staged diff as "TASK-002 complete" would record an unstyled half-implementation as the project's idea of done. The audit's `Status` is now `Blocked — half-implemented` to surface this until resolved.
- Decision can be deferred only if the human explicitly accepts shipping unstyled (Path 3 above) and amends the TASK-002 audit + commit message accordingly.

## State of the working tree at issue-open time

- 42 files staged for TASK-002 (per `git diff --staged --stat`). 158 tests pass. End-to-end `curl`-based verify recorded `200` on `GET /` and Lecture pages.
- Rail is in the DOM on all responses; no CSS rules exist for any rail class name.
- ADR-006 status on disk: `Accepted`.
- `architecture.md`: ADR-006 in "Accepted ADRs" table.
- TASK-002 audit: `Status: Blocked — half-implemented` (flipped on issue open).

## Recommendation (orchestrator's read; not binding)

Path 1 (amend ADR-006) is cleanest: it makes ADR-006 a complete record of the navigation Decision and forces the styling target to be named in the same place the mechanism is. The amendment cycle (revert to Proposed, edit, re-Accept) is bounded and well-defined. Path 2 is acceptable if the architect judges that styling will be a recurring separate concern (i.e., a styling-ADR pattern is forming). Path 3 is not recommended unless the project deliberately accepts shipping unstyled UI as a TASK-002 outcome.
