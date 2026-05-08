---
description: Architect proposes the next task.
allowed-tools: Read, Write, Glob, Grep
---

Invoke the architect subagent in **Mode 1: Propose the next task**.

Architect reads `design_docs/MANIFEST.md` (as input, not iron law — applying the desire/mechanism-as-desire/architecture-in-disguise classification protocol), `CLAUDE.md`, `design_docs/architecture.md`, all of `design_docs/decisions/`, all of `design_docs/project_issues/`, and all of `design_docs/tasks/`, then writes the next TASK-NNN file.

The proposed task must include an "Alternatives considered (task direction)" section and an "Architectural concerns I want to raise" section — the architect should not silently propose what looks obvious if there's a better-shaped task or if the obvious task quietly inherits architecture-in-disguise.

After it finishes, show me the path. Pause for me to review and edit before I run /design TASK-NNN.

If the architect outputs `MANIFEST TENSION:` or `PRIMARY OBJECTIVE COMPLETE:`, surface it and stop.
