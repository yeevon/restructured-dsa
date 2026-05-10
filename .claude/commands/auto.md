---
description: One full /next→/design→/implement→/review→commit cycle with routine human gates auto-accepted. Stops on manifest tension, conformance blockers, NEEDS HUMAN, and leaks in human-owned files.
allowed-tools: Read, Write, Edit, Glob, Grep, Bash
---

Run a full task cycle autonomously. Routine gates (task review, ADR acceptance, test review, post-commit review) are auto-accepted by the loop and recorded in the audit file as `auto-accepted` rows. Non-routine signals stop and surface to the human.

This command does not change architectural authority for ADRs created outside `/auto`. ADRs flipped `Proposed → Accepted` *by /auto* are marked as such in the ADR file and the audit gates table so drift is visible.

---

## Stop conditions (escalate to human)

Stop and surface immediately — do **not** continue to the next phase — if any of these appear in any subagent run, in any file the loop reads, or in any verify step:

1. `> MANIFEST TENSION:` from any agent.
2. `> NEEDS HUMAN:` from architect (i.e., an ADR with `Status: Pending Resolution`).
3. `ARCHITECTURE LEAK:` flagged against any human-owned file: `design_docs/MANIFEST.md`, `CLAUDE.md`, or `.claude/skills/manifest-conformance/SKILL.md`. (Leaks in `architecture.md` are auto-resolvable — architect fixes mechanically.)
4. A `manifest-conformance` skill blocker raised by reviewer (any rule MC-N marked blocking).
5. A `manifest-conformance` skill blocker raised in the implementer's verify-phase walk that survives one implementer retry.
6. `PUSHBACK:` from any agent (test-writer, implementer, reviewer). Pushback by definition means the agent thinks something upstream is wrong; the loop does not get to interpret which target is "auto-fixable." Escalate.
7. `> CANNOT TEST AC-N:` from test-writer for any AC.
8. Reviewer reports any blocking finding other than auto-remediable cases listed below.
9. Architect outputs `> PRIMARY OBJECTIVE COMPLETE:` (success — stop, not a failure).
10. Implementer test failures persist after 2 implementer retries.

When stopping, append a final `### Run NNN — /auto stopped` entry to the task audit file naming the trigger and the surfaced text, set the audit `Status` to `Blocked`, and report the trigger to the user.

## Auto-remediation (loop continues)

The loop is allowed to remediate without human intervention only in these cases:

- `ARCHITECTURE LEAK:` flagged against `design_docs/architecture.md` only — re-invoke architect to mechanically regenerate the file from the current Accepted-ADR set.
- Implementer test failure on first or second attempt — re-invoke implementer with the failing test output. Bound: 2 retries total. Third failure → stop (rule 10 above).
- Architect Mode 2 produced zero ADRs (no architectural decision in the task) — skip the ADR-acceptance gate and proceed.

Anything else escalates. The audit file is the human's drift-detection surface; do not silently route around findings.

---

## Preflight

- `git status --porcelain` must be clean. If anything is uncommitted/untracked except files the loop will create, stop with `Working tree not clean — /auto requires a clean tree to start.`
- `design_docs/audit/` exists.
- Current branch is not `main` only if user policy requires that — otherwise no branch check.

## Phase 1 — Architect Mode 1 (task proposal)

Invoke the `architect` subagent with the same brief as `/next` (see `.claude/commands/next.md`). Architect creates the task file at `design_docs/tasks/TASK-NNN-<slug>.md`, the audit file at `design_docs/audit/TASK-NNN-<slug>.md`, and appends Run 001.

Verify the task file and audit file exist (per CLAUDE.md "Orchestrator verification"). If missing, remediate directly.

**Auto-gate: Task review.** If no stop condition triggered, append a row to the audit file's "Human gates" table:

```
<ISO timestamp> | Task reviewed | auto-accepted | /auto run
```

## Phase 2 — Architect Mode 2 (ADRs)

Invoke the `architect` subagent with the same brief as `/design TASK-NNN`. Architect produces ADRs at `design_docs/decisions/ADR-NNN-<slug>.md` (with `Status: Proposed`), updates `design_docs/architecture.md` mechanically, and appends Run 002 to the audit file.

Verify each expected ADR file exists and `architecture.md` rows were added (per CLAUDE.md "Orchestrator verification"). If missing or incomplete, remediate directly — except for content the architect alone may write; for those, re-invoke architect with a delta brief.

**Auto-gate: ADR acceptance.** For each ADR this run produced with `Status: Proposed` and no stop condition triggered:

1. Edit the ADR file: change `Status: Proposed` to `Status: Accepted` and add a single line under the status: `Auto-accepted by /auto on <ISO date>`.
2. Edit `design_docs/architecture.md`: move the ADR row from "Proposed ADRs" to "Accepted ADRs"; regenerate the project-structure summary from the new Accepted set (mechanical only — no new architectural claims).
3. Append a row to the audit file's "Human gates" table:

```
<ISO timestamp> | ADR-NNN reviewed | auto-accepted | /auto run
```

Set the audit header `Status` to `In progress` once all task ADRs are Accepted.

If the architect produced zero ADRs this run, skip this gate and proceed.

## Phase 3 — Tests

Invoke the `test-writer` subagent with the same brief as `/implement` Phase 1. Test-writer appends its run entry before returning.

Run the project's test command (`python3 -m pytest tests/`). Confirm at least one test created in this run is failing.

**Auto-gate: Test review.** If no stop condition triggered, append a row to the audit file's "Human gates" table:

```
<ISO timestamp> | Tests reviewed | auto-accepted | /auto run
```

## Phase 4 — Implementation

Invoke the `implementer` subagent with the task + test file paths. Implementer appends its run entry before returning.

Run the project's test command. If any task-relevant test fails:
- Retry up to 2 times: re-invoke implementer with the failing test output. Each retry appends its own run entry to the audit file.
- After 2 failed retries, stop (rule 9).

## Phase 5 — Verify

Run the project's test, lint, and type-check commands.

Walk `.claude/skills/manifest-conformance/SKILL.md` against the working tree. Any blocker → stop (rule 4 / rule 5 — apply the one-retry rule for implementer-resolvable violations first).

Run end-to-end verification per `/implement` Phase 3 (start the dev server and hit the route, run the CLI, render the page, etc.). For UI-touching work without a browser available, surface explicitly per CLAUDE.md memory rather than declaring success from CLI output alone.

Append a `### Run NNN — verify (orchestrator)` entry to the audit file recording test/lint/type-check/conformance/end-to-end results.

## Phase 6 — Review + commit

Stage all changes (`git add` named files; do not use `git add -A` to avoid sweeping in unrelated files).

Invoke the `reviewer` subagent on the staged changes. Reviewer appends its run entry to the audit file before returning.

If reviewer reports any blocking finding that is not auto-remediable per the rules above, stop. Otherwise proceed to commit.

Commit with conventional format: `<type>(<scope>): <description>` per CLAUDE.md. Message body cites the task and the ADRs accepted. Trailer: `Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>`.

**Auto-gate: Commit review.** Append a row to the audit file's "Human gates" table:

```
<ISO timestamp> | Commit review | auto-accepted | /auto run
```

Update the audit header `Status` to `Committed`.

---

## Final report

Output to the user:
- Task created (path).
- ADRs accepted this run (paths and one-line summaries).
- Files changed in the commit.
- Tests added; pass count.
- Conformance walk result.
- End-to-end verification result.
- Audit file path.
- The commit SHA.

Do **not** push. The human reviews the audit file and decides whether to push.

If the loop stopped at any phase, output instead:
- Trigger condition (rule number above) and surfaced text.
- Audit file path with the `Run NNN — /auto stopped` entry.
- What the human needs to resolve before re-running `/auto` or running the per-phase commands manually.
