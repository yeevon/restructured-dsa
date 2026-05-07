---
description: Architect records ADRs for a task. Stops before tests.
argument-hint: [task ID, e.g. TASK-001]
allowed-tools: Read, Write, Edit, Glob, Grep
---

Invoke the architect subagent in **Mode 2** for task $ARGUMENTS.

Architect reads design_docs/MANIFEST.md, CLAUDE.md, design_docs/architecture.md, design_docs/decisions/, design_docs/project_issues/, the named TASK file, and any source code the task touches. It identifies real architectural decisions, writes each as `design_docs/decisions/ADR-NNN-<slug>.md` with `Status: Proposed`, and updates `design_docs/architecture.md` (Proposed ADRs section). If an ADR resolves a known project issue, the corresponding `design_docs/project_issues/<slug>.md` is updated to `Status: Resolved by ADR-NNN`.

When it finishes, show me:
- Each new ADR file path
- A summary of what each decides

STOP. Do not run tests or implementation. I will:
1. Read each new ADR
2. Edit if needed
3. Mark `Status: Accepted` in the ADR file
4. Move the entry from Proposed to Accepted in design_docs/architecture.md
5. Run `/implement $ARGUMENTS`

If architect outputs `MANIFEST CONFLICT:` or `> NEEDS HUMAN:`, surface to me and stop.
