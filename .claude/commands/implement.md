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
   - Run the project's test command. Identify the new tests by file path (those test-writer just created). Confirm at least one is failing.
   - If test-writer outputs `PUSHBACK:`, surface to me and STOP. Do not proceed to implementation until I resolve.
   - Show me the test files. Pause for me to review.

2. **Implementation.**
   - Invoke the `implementer` subagent with the task + test file paths.
   - The implementer must NOT modify tests.
   - If implementer outputs `PUSHBACK:` or `MANIFEST CONFLICT:` or `ESCALATION:`, surface and STOP.

3. **Verify.**
   - Run the project's test command. All tests pass.
   - Run the project's lint and type-check commands (whatever the project uses — see CLAUDE.md or pyproject.toml/package.json for the configured tooling).
   - **End-to-end verification.** Run the actual user-visible artifact the task delivers (start the dev server and hit the route, run the CLI, render the page, generate the file). Look at the result. If the task touched a rendering/parsing/batch pipeline, audit the WHOLE affected set, not one example. Lead with counts.
   - Show me a summary: ADRs from this task, files changed, tests added, ACs satisfied, end-to-end verification result, any adjacent bugs surfaced but not fixed.

Do NOT stage, commit, or push. I do that. After I commit, I'll run `/next`.

To review the staged diff before commit, invoke the reviewer subagent: `> Use the reviewer subagent on the staged changes`.
