---
description: Architect proposes the next task.
allowed-tools: Read, Write, Glob, Grep
---

Invoke the architect subagent in **Mode 1: Propose the next task**.

Architect reads (in order):
- `design_docs/MANIFEST.md` — binding for product behavior, scope, non-goals, invariants, and glossary. Classification protocol applies only for reporting/flagging architecture-in-disguise; it does not authorize routing around manifest entries.
- `CLAUDE.md` — authority pointers and pure conventions. Flag any architectural content that has leaked in.
- `design_docs/architecture.md` — current state of the project's architecture (architect-owned).
- `.claude/skills/manifest-conformance/SKILL.md` — drift-critical guardrails. A proposed task that would force a violation is wrong by construction.
- All of `design_docs/decisions/`, `design_docs/project_issues/`, and `design_docs/tasks/`.

Architect then writes the next TASK-NNN file at `design_docs/tasks/TASK-NNN-<slug>.md`.

The proposed task must include:
- An "Alternatives considered (task direction)" section with at least two materially different alternatives.
- An "Architectural concerns I want to raise" section that names any architecture-in-disguise inheritance, any flaws spotted in `architecture.md`, any leaks spotted in `CLAUDE.md`, or "None."

After it finishes, show me the path. Pause for me to review and edit before I run `/design TASK-NNN`.

If the architect outputs `MANIFEST TENSION:` or `PRIMARY OBJECTIVE COMPLETE:`, surface it and stop.
