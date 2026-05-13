# Project issue: TASK-001 test collides with ADR-006 rail

**Status:** Resolved by Path 1 (test amendment) — 2026-05-08
**Opened:** 2026-05-08
**Opened by:** Human (parking decision during TASK-002 implementation)
**Source:** ESCALATION raised by implementer in Run 007 of `design_docs/audit/TASK-002-chapter-navigation-grouped-by-designation.md`

**Resolution:** `tests/test_task001_lecture_page.py::test_ac3_mandatory_not_optional` amended to scope its assertion to the `<header class="lecture-header">` block (the chapter's own badge area) instead of substring-searching the whole HTML. Intent preserved; rail's "Optional" section header no longer trips it. After amendment: `158 passed, 0 failed`. Trace updated to include ADR-006.

**Honest note:** This issue was over-categorized when first opened. A pre-existing test failing because an Accepted ADR shifted the architecture is routine test maintenance, not an open architectural question — the markdown-authority rule already settles it (Accepted ADRs > pre-existing test assumptions). The "three branches" framing inflated a one-line scope fix into a multi-option decision tree that briefly parked TASK-002. Kept as record of the resolution path; future similar collisions should route directly to a test amendment without opening a project_issue.

## Summary

`tests/test_task001_lecture_page.py:181` (`test_ac3_mandatory_not_optional`) asserts `"Optional" not in html` against the response body of `GET /lecture/ch-01-cpp-refresher`. ADR-006 (Accepted, TASK-002) introduces a left-hand navigation rail rendered via `base.html.j2` on every Lecture page, with sections labeled "Mandatory" and "Optional." The literal string "Optional" now appears in the rail markup of every Lecture response, including ch-01's. The assertion therefore fires.

## Why this is a real architectural question, not a bug

- The TASK-001 test's intent — "ch-01's badge does not say Optional" — remains correct under ADR-006.
- The TASK-001 test's *assertion shape* — substring search over whole HTML — was sound for the world before ADR-006 (no rail; no other place "Optional" could appear) and is overbroad for the world after.
- ADR-006 cannot satisfy the assertion as written without giving up the rail's section labels (which is the load-bearing affordance of the rail — manifest §7's "separable in every learner-facing surface" invariant).

## Decision tree (for whoever takes this up)

1. **Amend the TASK-001 test.** Scope the assertion to ch-01's specific badge element (the per-chapter Mandatory/Optional badge in the lecture body, not the rail). Preserves intent; removes overbreadth. Cheapest path. Forced by the fact that ADR-006 was Accepted by the human and therefore wins under the markdown-authority rule (Accepted ADRs > test assertions written before the ADR existed). This is the test-writer's lane to execute, not the implementer's.
2. **Revisit ADR-006.** Reopen the rail's labeling decision — either drop the literal "Optional" header, use a different word, or rely solely on visual grouping without text labels. Reverses an Accepted gate; only justifiable if the rail labels are being reconsidered on their own merits (not just to keep the TASK-001 test untouched). Note: dropping the labels likely violates manifest §7's "separable in every learner-facing surface" invariant; needs `MANIFEST TENSION:` analysis before considering this path.
3. **Drop ADR-006's rail-on-every-Lecture-page provision.** Keep `GET /` landing page; remove the rail include from `lecture.html.j2`. Reverses part of ADR-006's Decision section. Same gate-reversal concern. Leaves Lecture pages without the in-context cross-Chapter navigation that motivated the rail in the first place.

## Decide when

- Before `/implement TASK-002` resumes (work is currently parked with code in working tree, uncommitted).
- The collision blocks Phase 3 verify and any further TASK-002 progress; the parked working-tree state passes 25 new TASK-002 tests but fails 1 TASK-001 test.

## State of the working tree at parking time

- New app files (uncommitted): `app/discovery.py`, `app/templates/base.html.j2`, `app/templates/_nav_rail.html.j2`, `app/templates/index.html.j2`.
- Modified app files (uncommitted): `app/main.py`, `app/designation.py`, `app/templates/lecture.html.j2`.
- New test files (uncommitted): `tests/test_task002_navigation.py` and `tests/fixtures/latex_*/`.
- pytest at parking time: `1 failed, 157 passed` — the failure is `test_ac3_mandatory_not_optional` only.
- ADR-005, ADR-006, ADR-007 remain Accepted on disk (not reversed by this parking).
- `architecture.md` row moves from `/design TASK-002` remain in working tree, uncommitted.

## Recommendation (orchestrator's read; not binding)

Path 1 (amend the TASK-001 test) is the lowest-cost path that respects the markdown-authority rule. The test was correct for its world; it is overbroad for the world after ADR-006. The fix is a single targeted assertion change scoped to the per-chapter badge element. Path 2 and Path 3 reverse a human-Accepted ADR and would each need their own decision history.
