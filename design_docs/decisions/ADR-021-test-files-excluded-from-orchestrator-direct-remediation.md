# ADR-021: Test assertion files are excluded from the orchestrator's direct-remediation authority

**Status:** `Accepted`
**Date:** 2026-05-10
**Task:** (workflow refinement, no `/next` cycle — surfaced by the TASK-008 retrospective audit-log analysis)
**Resolves:** none
**Supersedes:** none (constrains ADR-016 step 4 without replacing it; ADR-016 remains in force)

## Context

ADR-016 mandates that the orchestrator verify every subagent's expected file outputs after the subagent returns, and either remedy gaps directly (when mechanical) or escalate back to the responsible subagent (when role authority is required). Step 4 of ADR-016 draws the boundary between "remedy directly" and "escalate" but does not enumerate which file classes fall on which side.

Empirical record across the audit logs shows the boundary has been interpreted too broadly when test assertion files are involved:

- **TASK-003 audit Run 008.** After the orchestrator removed an unauthorized `.nav-chapter-id` CSS class from `app/static/base.css`, six Playwright test assertions in `tests/playwright/test_task002_navigation_dom.py` were left referencing the removed class. The orchestrator rewrote all six tests in place under the "remedy directly" clause rather than re-invoking the test-writer with a delta brief. The audit log records this as an `**This is an orchestrator scope override**` flag.
- **TASK-005 audit Run 007.** Four test assertions across the multi-chapter validation harness were amended in place by the orchestrator (case-insensitivity adjustments, scope narrowing from whole-body to title-only). The audit log records each amendment as an orchestrator-direct edit. The test-writer was not re-invoked.

In both cases the per-edit work was small, but the cumulative effect is silent test-design drift: the test-writer's authority over assertion design (which test exists, what it asserts, what scope, what selector pattern) is bypassed without a Run entry capturing the design rationale. Subsequent test-honesty audits cannot trace why a given assertion has its current shape because the only record is an orchestrator-edit diff. The agent-ownership table in CLAUDE.md "Pushback protocol" already lists `tests` as test-writer-owned; ADR-016's "remedy directly if mechanical" clause should respect that ownership boundary, but it does not say so explicitly.

This ADR closes the ambiguity by excluding test assertion files from the orchestrator's direct-remediation authority. The orchestrator may still verify them via `git diff` per ADR-016 steps 1–3 and may still detect that an amendment is required, but the amendment itself must be performed by the test-writer in a re-invocation.

## Decision

Test assertion files are **excluded** from the orchestrator's "remedy directly if mechanical" authority granted by ADR-016 step 4. Specifically:

- Files matching `tests/**/test_*.py` and `tests/**/*_test.py` MAY be read by the orchestrator and MAY be diffed against expected changes per ADR-016 steps 1–3, but MUST NOT be modified by the orchestrator under the direct-remediation clause.
- When an amendment is required (because the orchestrator overrode subagent scope, because the human gate course-corrected, because mid-implementation discovery surfaced a missing or wrong assertion, or for any other reason), the orchestrator MUST re-invoke the test-writer with a delta brief that names: (a) the test files affected, (b) the change required, (c) the rationale.
- The test-writer's re-invocation Run is appended to the audit file as a normal test-writer Run entry (not as an `Orchestrator remediation:` note).
- Test infrastructure files (`tests/conftest.py`, `tests/fixtures/**`, shared utilities) remain test-writer-owned but are also addable by the implementer per existing implementer.md "Hard rules" (test infrastructure is extendable). The orchestrator's exclusion under this ADR applies only to the assertion-file glob above.

The exclusion does NOT apply to:
- Test artifacts that are not assertion files (e.g., snapshot directories, `tests/playwright/artifacts/**`).
- Untracked test scratch files an agent leaks outside its lane (the orchestrator may still delete those under ADR-016's general gap-remediation authority, since the remediation is *deletion*, not assertion-design editing).
- Mechanical syntax-only fixes the orchestrator detects in non-test files (those remain governed by ADR-016 step 4 unchanged).

## Alternatives considered

**A. Wholesale supersedure of ADR-016 with the test-file exclusion baked into a restated rule.**
Rejected. ADR-016's Context, Alternatives, Consequences, and Manifest reading sections are still correct as written; only step 4's boundary needs narrowing. Wholesale supersedure would force a future reader to ignore ADR-016 and read ADR-021 instead, losing the framing in ADR-016 that does not need to change. The narrower constraint-on-an-existing-rule shape is honest about what's actually being changed.

**B. Leave the rule as orchestrator convention without an ADR.**
Rejected. The TASK-003 and TASK-005 incidents both happened *after* the agent-ownership table was in CLAUDE.md and the implicit interpretation ("tests are test-writer's") was theoretically available. The convention did not bite. Codifying the boundary as an Accepted ADR with a one-sentence CLAUDE.md citation is what makes it enforced rather than aspirational.

**C. Move the rule to a `.claude/skills/<name>/SKILL.md`.**
Rejected for the same reason ADR-016 §Alternatives D rejected the skill-only approach: skill files are Tier 2 under the Markdown authority rule, and a skill encoding a workflow constraint without an Accepted ADR backing is leak-shaped. The skill+ADR pairing would work, but for a one-paragraph constraint a skill file is overhead.

**D. Add the exclusion as a literal step in `CLAUDE.md` §"Orchestrator verification of subagent outputs" without an ADR.**
Rejected. CLAUDE.md is Tier 2; introducing a workflow-mechanism constraint inline would re-trigger the same `ARCHITECTURE LEAK:` pattern that ADR-016 was ratified to close. The CLAUDE.md citation is allowed as a one-sentence pointer to this ADR (citation surface, not authority surface).

## Consequences

**Becomes possible:**
- Test-writer Run entries in the audit log capture the design rationale for every assertion change. Test-honesty audits can trace assertion shape back to a Run entry instead of to an opaque orchestrator-edit diff.
- The agent-ownership table in CLAUDE.md "Pushback protocol" gains a checkable enforcement point at the orchestrator's verification step, not just at subagent invocation.

**Becomes more expensive:**
- Test amendments that the orchestrator previously hand-edited (small case adjustments, scope narrowing, selector swaps) now require a test-writer re-invocation, which is a heavier process step than an inline edit. This is the intended cost of preserving test-writer authority. Estimated frequency from the audit-log analysis: ~10 test-edit events across the first 8 tasks, so ~1 extra test-writer re-invocation per task on average.

**Becomes impossible (under this ADR):**
- Orchestrator hand-editing of `tests/**/test_*.py` or `tests/**/*_test.py` files under any rationale. Detection of an amendment requirement is allowed; the amendment itself is not.

**Supersedure path:**
A future ADR may relax this exclusion (e.g., if a hard-coded class of trivial textual fixes is identified that test-writer re-invocation is genuinely overkill for) by superseding this ADR. The supersedure would either narrow the file-glob exclusion or enumerate the trivial-fix class. Until then, the exclusion is binding.

## Manifest reading

Read as binding:
- §6 Behaviors and Absolutes (visible failures) — re-invoking the test-writer surfaces test-design changes as proper Run entries instead of burying them in orchestrator-edits commits, which serves the visible-failures principle one layer up.
- §5 Non-Goals — none of the non-goals constrain orchestrator process.

No manifest entries flagged as architecture-in-disguise.

## Conformance check

- **Markdown authority rule (CLAUDE.md tier table).** This ADR exists at Tier 1 (Accepted ADR). The CLAUDE.md citation in §"Orchestrator verification of subagent outputs" is a Tier 2 citation surface only — it points at this ADR and does not introduce content this ADR does not commit to.
- **ADR-016.** This ADR constrains step 4 of ADR-016 without superseding it. ADR-016 remains Accepted; its other steps and its remedy/escalate framing are unchanged.
- **MC-1 through MC-10 (manifest-conformance rules).** Not touched. The exclusion is workflow process; it does not affect product behavior, content layout, M/O designation, persistence, or any rendering surface.
- **CLAUDE.md "Pushback protocol" agent-ownership table.** This ADR makes the agent-ownership table's "tests = test-writer" entry checkable at the orchestrator's verification step. Consistent, not conflicting.
