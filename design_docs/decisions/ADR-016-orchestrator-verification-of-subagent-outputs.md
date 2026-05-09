# ADR-016: Orchestrator verifies subagent file outputs after every phase via `git diff`

**Status:** `Accepted`
**Date:** 2026-05-08
**Task:** TASK-006
**Resolves:** (none — ratifies a pre-existing operational rule that had been living unbacked in `CLAUDE.md`)
**Supersedes:** none

## Context

The project's workflow is a chain of subagent handoffs: `/next` runs the architect, `/design` runs the architect, `/implement` runs test-writer then implementer, `/review` runs the reviewer. Each subagent returns a *summary message* describing what it did, and the orchestrator (the top-level Claude session) is the only party that can act on that summary in the next phase.

Subagent summaries describe **intent**, not **outcome**. Empirical history in this project includes at least one case where a subagent's summary claimed an update was made and the file on disk was unchanged (TASK-002 / TASK-003 reviewer findings; TASK-004 audit Run 003 explicitly required orchestrator remediation when an architect run skipped a row in `architecture.md`). The cost of trusting a subagent summary at face value is silent drift: a phase advances, downstream agents read stale state, and the divergence is discovered later — during `/review` at the earliest, during `/implement` at the worst — at which point the audit log is already polluted and the next phase has compounded the gap.

The cheap, reliable defense is for the orchestrator to run `git diff` (or `git status`) on each file the subagent was *expected* to create or modify, immediately after the subagent returns. A diff check is one shell call per expected file; it does not require re-reading the project, and it does not require a second subagent. When a gap is found, the orchestrator either fixes it directly (for mechanical gaps the orchestrator has full context for) or escalates back to the responsible subagent.

This rule was previously stated inline in `CLAUDE.md` §"Orchestrator verification of subagent outputs". Multiple architect and reviewer runs flagged that section as an `ARCHITECTURE LEAK:` because `CLAUDE.md` is Tier 2 ("operational instruction; process and conventions only") under the Markdown authority rule and the section introduced a workflow mechanism (mandated steps, an authority grant for the orchestrator to remediate, a fixed audit-format string) without an Accepted ADR backing. The leak flag was correct under the rule as written; the rule itself was not wrong, only unbacked. This ADR ratifies the rule so that the `CLAUDE.md` section (which remains as the operational quick-reference) cites this ADR instead of standing alone.

## Decision

The orchestrator (the top-level Claude session driving `/next`, `/design`, `/implement`, `/review`) MUST verify every subagent's expected file outputs immediately after the subagent returns and before advancing to the next phase. Verification is mechanical:

1. Identify the expected file changes from the subagent's task brief (e.g., "architect creates ADR-013," "test-writer creates `tests/playwright/test_chapters_render.py`," "implementer modifies `app/parser.py`").
2. Run `git diff <path>` on each expected file (and `git status` / a quick glob for newly-created files) to confirm the change exists and is substantively correct. A diff check is sufficient — full re-read of the file is not required unless the diff reveals a problem.
3. If a file was supposed to be created, confirm it exists.
4. If an expected change is missing or incomplete, the orchestrator either:
   - **remedies the gap directly** when the gap is mechanical and the orchestrator has full context (e.g., a single missing row in `architecture.md`, a missing audit-row append, a one-line stale text), or
   - **escalates back to the subagent** when the gap requires the subagent's role-specific authority (e.g., a missing ADR; a missing test file; an architectural decision the orchestrator does not own).
5. Append a remediation note to the task audit file whenever the orchestrator applies a fix that a subagent failed to produce:

   ```
   **Orchestrator remediation:** <agent type> (Run NNN) was expected to update <file path> with <description>. Change was missing/incomplete. Orchestrator applied the fix directly.
   ```

Verification is mandatory at every phase transition: after `/next` (architect Run 001), after `/design` (architect Run 002), after each `/implement` phase (test-writer, implementer, verify), and after `/review` (reviewer).

The cost target is one `git diff` per expected file, not a full re-read. Re-reads are reserved for diffs that reveal a problem.

The operational quick-reference for this rule lives in `CLAUDE.md` §"Orchestrator verification of subagent outputs"; that section cites this ADR and does not introduce content that this ADR does not already commit to.

## Alternatives considered

**A. Trust subagent summaries; investigate only when a downstream agent finds a gap.**
Cheaper per phase. Rejected because the empirical record shows silent drift compounds: if `/design` skipped a row in `architecture.md`, the next reader (test-writer or implementer) reads stale state and may produce work that compounds the gap. Catching the drift one phase later means the audit log already records a phase-transition that did not actually happen as described, and the remediation cost grows. The `git diff` check is one cheap call; the cost of *not* doing it is unbounded.

**B. Make verification a subagent (a second-pass "verifier" agent invoked after every phase).**
Architecturally clean (separation of concerns) but introduces a second subagent invocation per phase. Rejected because (1) the verification work is *mechanical* — a `git diff` and a comparison to the expected change list — which is exactly the work the orchestrator is best positioned to do given that the orchestrator just briefed the first subagent and knows what was asked; (2) a verifier subagent itself would need *its* outputs verified, regressing the problem; (3) the cost (a full subagent invocation per phase) is wildly disproportionate to the cost of one `git diff` per expected file.

**C. Keep the rule purely in `CLAUDE.md` without an ADR.**
The original state. Rejected because the Markdown authority rule places `CLAUDE.md` in Tier 2 ("process and conventions only; no architecture") and the rule as written introduces a workflow mechanism (mandated steps + remediation authority + a fixed audit-format string) that the architect's critique pass correctly classifies as architecture-in-disguise. Leaving it unbacked means every `/next`, `/design`, `/implement`, and `/review` cycle re-flags it, which costs human attention each time and frames a correct operational rule as a process violation. Ratifying it via ADR converts the flag into a citation.

**D. Move the rule to a `.claude/skills/orchestrator-verification/SKILL.md`.**
Skill files are also Tier 2 under the Markdown authority rule. The leak relocates rather than disappears unless the skill cites an Accepted ADR. The conventional pattern in this project (see `manifest-conformance/SKILL.md` line 10) is for skills to encode process *only* when every concrete rule traces to an Accepted ADR or the manifest. So a skill-only solution is not actually leak-free — it requires an ADR to back it. Given the rule is operationally short (one section), a skill file is overhead; the inline `CLAUDE.md` section + ADR citation is sufficient.

## Consequences

**Becomes possible:**
- The architect's and reviewer's Markdown critique pass against `CLAUDE.md` §"Orchestrator verification of subagent outputs" passes by citation, not by interpretation. The recurring `ARCHITECTURE LEAK:` flag (TASK-004 reviewer Run 006; TASK-005 architect Run 001 and Run 002) stops firing on this section.
- New orchestrator agents (or a future replacement of the workflow harness) inherit the rule with an ADR-backed authority trail rather than as a free-standing mandate in operational instructions.
- Future amendments to the rule (e.g., a different remediation boundary, a different audit-format string) go through a normal supersedure ADR rather than a `CLAUDE.md` edit, preserving decision history.

**Becomes more expensive:**
- Changes to the orchestrator-verification rule (any of the five steps, the remediation boundary, the audit-format string) require a supersedure ADR. This is the intended cost of ratifying a workflow mechanism as architecture.

**Becomes impossible (under this ADR):**
- Skipping the `git diff` verification step at a phase transition without amending or superseding this ADR. The rule is binding while this ADR is in force.
- Stating a different version of the orchestrator-verification rule in `CLAUDE.md` or a skill file. Citation surfaces (`CLAUDE.md`, skills) cannot diverge from this ADR's text.

**Supersedure path:**
A future ADR may supersede this one if the workflow harness changes (e.g., a different orchestrator surface, a different verification mechanism). The supersedure ADR replaces the rule wholesale; the `CLAUDE.md` citation is updated mechanically in the same commit.

## Manifest reading

Read as binding:
- section 6 Behaviors and Absolutes ("visible failures") — the orchestrator-verification rule directly serves this principle by catching subagent failures at the phase boundary instead of letting them surface later as silent drift.
- section 5 Non-Goals — none of the non-goals (no auth, no AI tutor, no LMS, no mobile) constrain orchestrator process.

No manifest entries flagged as architecture-in-disguise.

## Conformance check

- **Markdown authority rule (CLAUDE.md tier table).** This ADR exists at Tier 1 (Accepted ADR). The `CLAUDE.md` §"Orchestrator verification of subagent outputs" section becomes a Tier 2 citation surface with an explicit pointer to this ADR. The leak is closed.
- **MC-1 through MC-10 (manifest-conformance rules).** Not touched. The orchestrator-verification rule is workflow process; it does not affect product behavior, content layout, M/O designation, persistence, or any rendering surface.
- **ADR-003 (rendering pipeline), ADR-007 (chapter discovery), ADR-010 (Playwright verification).** Not touched. This ADR's scope is the *workflow* between subagents, not the rendered surface or the test framework.
- **CLAUDE.md "LLM audit log" template.** This ADR commits the orchestrator to appending a `**Orchestrator remediation:**` note to the task audit file when remediation occurs. That format is consistent with the audit file template's Run-entry shape and the audit-append-only skill's append-only discipline.
