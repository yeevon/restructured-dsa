# TASK-006: Ratify the orchestrator-verification rule via ADR-016

**Status:** Closed (2026-05-08) — ratification-only task; no code, no tests.

**Inputs read:**
- Manifest: ss5 (non-goals do not touch workflow process), ss6 ("visible failures" — the rule serves this principle by catching subagent drift at the phase boundary)
- CLAUDE.md: §"Orchestrator verification of subagent outputs" (lines 131-148) and §"Markdown authority rule" (the tier table that classifies `CLAUDE.md` as Tier 2 "process and conventions only")
- architecture.md: Accepted ADRs 001-012 (none touch workflow process); Proposed ADRs 013-015 (TASK-005, blocked by this leak)
- ADR-016 (newly Accepted in this task)
- Audit history of the leak flag: TASK-004 reviewer Run 006 (`CHANGES REQUESTED` state, not addressed before commit); TASK-005 architect Run 001 (re-flagged); TASK-005 architect Run 002 (re-flagged again).

## What and why

The orchestrator-verification rule (orchestrator runs `git diff` on every expected subagent output before advancing phases, and remediates mechanical gaps directly) has been in force since TASK-002 and is operationally correct. It has, however, been living unbacked in `CLAUDE.md` — a Tier 2 file that the Markdown authority rule restricts to "process and conventions only; no architecture introduced outside an Accepted ADR." Because the rule introduces a workflow mechanism (mandated steps + an authority grant for the orchestrator to remediate + a fixed audit-format string), every architect and reviewer run that reads `CLAUDE.md` correctly flags it as `ARCHITECTURE LEAK:` per the Markdown critique pass.

The rule itself is not wrong. The framing is: the rule is architecture, and architecture must live in an ADR. Ratifying the rule via a new ADR (ADR-016) converts the recurring leak flag into a one-line citation in `CLAUDE.md`, unblocking `/design TASK-005` (which had to re-flag the leak in both Run 001 and Run 002) and every future task that reads `CLAUDE.md`.

This task is mechanical: write ADR-016, add the row to `architecture.md`, add a citation header to the `CLAUDE.md` section, close the task. No tests, no code, no implementation phase.

## Acceptance criteria

- [x] ADR-016 exists at `design_docs/decisions/ADR-016-orchestrator-verification-of-subagent-outputs.md` with `Status: Accepted` and a complete Decision section that captures the rule from `CLAUDE.md` §"Orchestrator verification of subagent outputs" verbatim or stronger.
- [x] `design_docs/architecture.md` Accepted ADRs table contains a row for ADR-016 with `TASK-006` and `2026-05-08`.
- [x] `CLAUDE.md` §"Orchestrator verification of subagent outputs" includes a citation header pointing to ADR-016 (e.g., "_See ADR-016 (Accepted) — this section is the operational quick-reference; ADR-016 is authoritative._"). The body content is not changed; only a citation pointer is added.
- [x] Task audit file at `design_docs/audit/TASK-006-ratify-orchestrator-verification-rule.md` exists with the Human gates table closed (Task accepted, ADR-016 accepted, Task closed).
- [x] TASK-005 audit file has a Run 003 entry recording that the leak has been ratified by ADR-016 and is no longer a blocker for TASK-005.
- [x] No `app/` code is modified by this task.
- [x] No new tests are required — the rule operates on the workflow harness, not on rendered output. The orchestrator's compliance with ADR-016 is observable in audit-file run entries (each `/next`, `/design`, `/implement`, `/review` phase transition has the verification step recorded).

## Architectural decisions expected

- **ADR-016: Orchestrator verifies subagent file outputs after every phase via `git diff`.** Captures the rule from `CLAUDE.md` §"Orchestrator verification of subagent outputs" with full context, alternatives considered, consequences, and supersedure path. Status: Accepted (ratification of an in-force rule, not a new commitment).

## Alternatives considered (task direction)

- **(Chosen) Single ratification task — ADR-016 + citation header + audit closure, no implementation phase.** The rule is already in force; no behavior change is required. The minimum work to close the leak is the ADR + the citation. Bundling the ratification into one task avoids splitting trivial work across phases and gets `/design TASK-005` unblocked in the same session.

- **Move the rule to a new `.claude/skills/orchestrator-verification/SKILL.md`.** Rejected because skills are also Tier 2 under the Markdown authority rule. Without an Accepted ADR backing, the leak relocates from `CLAUDE.md` to the skill file. The conventional pattern (see `manifest-conformance/SKILL.md` line 10) is for skills to *cite* ADRs, not to *introduce* rules. So a skill-first path still requires this ADR; the only question is whether to *also* create a skill. Given the rule is short (one section in `CLAUDE.md`), a skill file is overhead; deferred until the rule grows enough to justify the indirection.

- **Edit `CLAUDE.md` §"Markdown authority rule" to carve out "orchestrator workflow process" from the architecture-leak definition, and leave the orchestrator-verification section unbacked.** Rejected because the carve-out is a *change to the leak rule itself* and would require its own ADR to be a defensible authority change. It is also broader than necessary: the issue is one specific section, not the whole class of orchestrator-process content. Targeting one section with one ADR is the minimum-blast-radius fix.

- **Defer ratification; rely on the architect's recommendation in TASK-005 audit and let the human carry the leak forward indefinitely.** Rejected because every future task's `/next` and `/design` phases will re-flag the leak, which costs human attention each time and frames a correct rule as a violation. The ratification work is small (one ADR + one citation + one audit file) and pays for itself on the next architect run.

## Architectural concerns I want to raise

- **None new.** This task closes the recurring `ARCHITECTURE LEAK:` flag against `CLAUDE.md` §"Orchestrator verification of subagent outputs" that was raised by:
  - TASK-004 reviewer Run 006 (`CHANGES REQUESTED` state, not addressed before commit `ad52ab2`)
  - TASK-005 architect Run 001 (re-flagged)
  - TASK-005 architect Run 002 (re-flagged again)
- The CLAUDE.md citation header preserves the operational quick-reference (humans and orchestrators can still read the rule in `CLAUDE.md`) while making clear that ADR-016 is the authoritative source. Future amendments to the rule go through a supersedure ADR, not a `CLAUDE.md` edit.

## Implementation note

This task does not invoke `/implement`. It is closed by the orchestrator (the human's session) directly, because the work is mechanical (writing one ADR, one citation header, one audit file) and the human is the gate-keeper for `CLAUDE.md` edits and for ADR acceptance. The audit file records the work in a single run entry plus the closure gate.
