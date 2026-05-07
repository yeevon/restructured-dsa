---
description: Architect proposes the next task.
allowed-tools: Read, Write, Glob, Grep
---

Invoke the architect subagent in **Mode 1: Propose the next task**.

Architect reads design_docs/MANIFEST.md, CLAUDE.md, design_docs/architecture.md, all of design_docs/decisions/, all of design_docs/project_issues/, and all of tasks/, then writes the next TASK-NNN file.

After it finishes, show me the path. Pause for me to review and edit before I run /design TASK-NNN.

If the architect outputs `MANIFEST CONFLICT:` or `PRIMARY OBJECTIVE COMPLETE:`, surface it and stop.
