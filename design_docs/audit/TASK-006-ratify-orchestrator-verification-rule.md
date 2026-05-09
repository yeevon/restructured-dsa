# LLM Audit — TASK-006: Ratify the orchestrator-verification rule via ADR-016

**Task file:** `design_docs/tasks/TASK-006-ratify-orchestrator-verification-rule.md`
**Started:** 2026-05-08T00:00:00Z
**Status:** Closed
**Current phase:** done

---

## Human gates

| Time | Gate | Result | Notes |
|---|---|---|---|
| 2026-05-08 | Task reviewed | accepted | Human directly authorized: ratify the orchestrator-verification rule via ADR + ratification task so TASK-005 can proceed without re-flagging the leak. Mechanical-only; no test/implement phase. |
| 2026-05-08 | ADR-016 reviewed | accepted | Captures the rule from `CLAUDE.md` §"Orchestrator verification of subagent outputs" with full Context / Decision / Alternatives / Consequences. Recurring leak flag is now backed. |
| 2026-05-08 | Task closed | closed | All ACs satisfied: ADR-016 (Accepted) on disk; `architecture.md` Accepted-ADRs row added; `CLAUDE.md` citation header added; TASK-005 audit Run 003 records the unblock. |

---

## Agent runs

### Run 001 — orchestrator (human session) / direct ratification

**Time:** 2026-05-08T00:00:00Z
**Input files read:**
- `design_docs/MANIFEST.md` (ss5, ss6 — workflow process is not a manifest concern; "visible failures" backs the rule's intent)
- `CLAUDE.md` (lines 125-148: §"Orchestrator verification of subagent outputs" target section; §"Markdown authority rule" tier table)
- `design_docs/architecture.md` (current Accepted ADR set, Proposed ADR set, project-structure prose)
- `design_docs/decisions/ADR-012-callout-title-rendering.md` (template reference for ADR format)
- `design_docs/tasks/TASK-004-parser-fidelity-tabular-callout-titles.md` (task-file shape reference)
- `design_docs/audit/TASK-005-multi-chapter-rendering-validation.md` (Run 001 + Run 002 records of the leak flag)
- `.claude/agents/architect.md`, `.claude/agents/reviewer.md`, `.claude/agents/test-writer.md`, `.claude/agents/implementer.md` (located the Markdown-critique-pass instructions that fire the flag)
- `.claude/skills/manifest-conformance/SKILL.md` (line 10 — convention that skills cite ADRs rather than introduce rules)
- `.claude/skills/authority-state-check/SKILL.md` (header — confirms Tier 2 status of skills)

**Tools / commands used:** Read (all files above), Bash (`git status --short`, `ls .claude/agents/ .claude/commands/ .claude/skills/`, `grep -n -i "orchestrator|markdown.*critique|leak|tier.2|architecture leak"` across agents and commands and skills), Write (`design_docs/decisions/ADR-016-orchestrator-verification-of-subagent-outputs.md`, `design_docs/tasks/TASK-006-ratify-orchestrator-verification-rule.md`, `design_docs/audit/TASK-006-ratify-orchestrator-verification-rule.md`), Edit (`design_docs/architecture.md` Accepted ADRs row; `CLAUDE.md` §"Orchestrator verification..." citation header; `design_docs/audit/TASK-005-multi-chapter-rendering-validation.md` Run 003 append)

**Files created:**
- `design_docs/decisions/ADR-016-orchestrator-verification-of-subagent-outputs.md` (Status: Accepted)
- `design_docs/tasks/TASK-006-ratify-orchestrator-verification-rule.md` (Status: Closed)
- `design_docs/audit/TASK-006-ratify-orchestrator-verification-rule.md` (this file)

**Files modified:**
- `design_docs/architecture.md` — appended ADR-016 row to the Accepted ADRs table.
- `CLAUDE.md` — added a one-line citation header to §"Orchestrator verification of subagent outputs" pointing to ADR-016. Body content of the section is unchanged; only the header is added so the architect's Markdown critique pass sees the ADR backing.
- `design_docs/audit/TASK-005-multi-chapter-rendering-validation.md` — appended Run 003 (orchestrator note) recording that the recurring `ARCHITECTURE LEAK:` flag against `CLAUDE.md` §"Orchestrator verification of subagent outputs" has been ratified by ADR-016 and is no longer a blocker for `/implement TASK-005`.

**Files deleted:** none

**Task alternatives considered:** documented in the task file under "Alternatives considered (task direction)" — single ratification task chosen over skill-first, leak-rule-carve-out, or indefinite deferral. No new alternatives surfaced during execution.

**Decisions surfaced (as pointers):**
- ADR-016 (Accepted) — orchestrator verifies subagent file outputs after every phase via `git diff`; remediates mechanical gaps directly; appends `**Orchestrator remediation:**` notes to the task audit file.

**Architecture leaks found:**
- The pre-existing `ARCHITECTURE LEAK:` flag against `CLAUDE.md` §"Orchestrator verification of subagent outputs" (TASK-004 reviewer Run 006; TASK-005 architect Run 001 and Run 002) is closed by this task. ADR-016 is now the authoritative source; `CLAUDE.md`'s section is a citation surface.
- No new leaks found.

**Pushback raised:** none. The user's directive (ratify via ADR + task; close both; update audit; goal: unblock TASK-005) is internally consistent with the Markdown authority rule and with the existing project conventions. Skill-vs-ADR consideration documented in the ADR's Alternative D and in the task's Alternatives section.

**Conformance check (run by orchestrator at write time, not by a separate verifier):**
- Markdown authority rule: ADR-016 is at Tier 1 (Accepted ADR). `CLAUDE.md` citation is at Tier 2. No leak introduced.
- audit-append-only skill: TASK-005 audit was appended (Run 003), not rewritten. TASK-006 audit is freshly created.
- authority-state-check skill: ADR-016 `Status: Accepted` is consistent with the `architecture.md` Accepted ADRs table row added in the same task. No state drift.

**Output summary:** Ratified the orchestrator-verification rule that had been living unbacked in `CLAUDE.md` §"Orchestrator verification of subagent outputs" since TASK-002. Created ADR-016 (Accepted) capturing the rule with full Context / Decision / Alternatives / Consequences / Manifest reading / Conformance check. Added the row to `architecture.md` Accepted ADRs table. Added a citation header to the `CLAUDE.md` section so the architect's and reviewer's Markdown critique pass sees the ADR backing instead of re-flagging the section. Appended Run 003 to TASK-005 audit recording the unblock. TASK-005 now has no blocking flags from prior phases; `/implement TASK-005` is gated only by human acceptance of the still-`Proposed` ADRs 013, 014, 015.
