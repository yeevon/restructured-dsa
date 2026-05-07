---
description: Test-writer + implementer + verify for a task. Assumes ADRs already accepted.
argument-hint: [task ID, e.g. TASK-001]
allowed-tools: Read, Write, Edit, Glob, Grep, Bash
---

Implement task $ARGUMENTS.

**Precondition check:** all ADRs for this task in `design_docs/decisions/` must have `Status: Accepted`. If any are still `Proposed` or `Pending Resolution`, STOP and tell me which. Do not start tests until ADRs are accepted.

Plan:

1. **Tests first.**
   - Invoke the `test-writer` subagent with the task.
   - Run `pytest`. Identify the new tests by file path (those test-writer just created). Confirm at least one is failing.
   - Show me the test files. Pause for me to review.

2. **Implementation.**
   - Invoke the `implementer` subagent with the task + test file paths.
   - The implementer must NOT modify tests. If it produces ESCALATION or MANIFEST CONFLICT, surface and STOP.

3. **Verify.**
   - Run `pytest`. All tests pass.
   - Run `ruff check --fix && ruff format && mypy cs300/`.
   - Show me a summary: ADRs from this task, files changed, tests added, ACs satisfied.

Do NOT stage, commit, or push. I do that. After I commit, I'll run `/next`.

To review the staged diff before commit, invoke the reviewer subagent: `> Use the reviewer subagent on the staged changes`.
