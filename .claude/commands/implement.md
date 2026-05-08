---
description: Test-writer + implementer + verify for a task. Assumes architecture.md edits + ADRs are already accepted.
argument-hint: [task ID, e.g. TASK-001]
allowed-tools: Read, Write, Edit, Glob, Grep, Bash
---

Implement task $ARGUMENTS.

**Precondition checks:**
- Every ADR for this task in `design_docs/decisions/` must have `Status: Accepted`. Any `Proposed` or `Pending Resolution` is blocking — stop and tell me which.
- The `design_docs/architecture.md` edits from `/design` must be committed-or-staged-and-reviewed by me. If `git diff design_docs/architecture.md` shows unreviewed edits, surface them and stop until I confirm.
- The task audit file must exist at `design_docs/audit/TASK-NNN-<slug>.md` (created by `/next`). If it does not, stop and surface the missing-audit error.

Plan:

Each phase appends a run entry to the task audit file at `design_docs/audit/TASK-NNN-<slug>.md` before transitioning to the next phase (per CLAUDE.md "LLM audit log"). The audit file is append-only; do not rewrite earlier entries.

1. **Tests first.**
   - Invoke the `test-writer` subagent with the task. Test-writer appends its run entry before returning.
   - Run the project's test command. Identify the new tests by file path (those test-writer just created). Confirm at least one is failing.
   - If test-writer outputs `PUSHBACK:` (weak ACs, manifest conflict, or ADR flaw) or `ARCHITECTURE LEAK:`, surface to me and STOP. Do not proceed to implementation until I resolve.
   - Show me the test files and the audit file's new run entry. Pause for me to review. When I accept, I add a row to the audit "Human gates" table (`Tests reviewed | accepted | ...`).

2. **Implementation.**
   - Invoke the `implementer` subagent with the task + test file paths. Implementer appends its run entry before returning.
   - The implementer must NOT modify tests, `design_docs/architecture.md`, ADRs, the manifest, CLAUDE.md, or the conformance skill.
   - If implementer outputs `PUSHBACK:` (test/ADR/manifest flaw) or `ARCHITECTURE LEAK:`, surface and STOP.

3. **Verify.**
   - Run the project's test command. All tests pass.
   - Run the project's lint and type-check commands.
   - **Conformance walk.** Walk `.claude/skills/manifest-conformance/SKILL.md` against the working tree (or staged diff). Any blocker is an escalation; surface and stop before reporting done.
   - **End-to-end verification.** Run the actual user-visible artifact the task delivers (start the dev server and hit the route, run the CLI, render the page, generate the file). Look at the result. If the task touched a rendering/parsing/batch pipeline, audit the WHOLE affected set, not one example. Lead with counts.
   - The implementer's run entry already records the verify-phase results (test/lint/type-check/conformance/end-to-end). If you (the orchestrator) ran additional verify steps after implementer returned, append a small `### Run NNN — verify (orchestrator)` entry recording what you ran and what you saw.
   - Show me a summary: ADRs from this task, files changed, tests added, ACs satisfied, conformance result, end-to-end verification result, any adjacent bugs surfaced but not fixed, and the audit file path.

Do NOT stage, commit, or push. I do that. After I commit, I'll run `/next`.

To review the staged diff before commit, invoke the reviewer subagent: `> Use the reviewer subagent on the staged changes`. The reviewer will invoke the conformance skill explicitly as part of its protocol and will append its run entry to the task audit file before returning. After commit, I add a `Commit review | ready` row to the audit "Human gates" table and update the audit `Status` to `Committed`.
