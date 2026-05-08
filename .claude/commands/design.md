---
description: Architect records ADRs for a task. Stops before tests.
argument-hint: [task ID, e.g. TASK-001]
allowed-tools: Read, Write, Edit, Glob, Grep
---

Invoke the architect subagent in **Mode 2** for task $ARGUMENTS.

Architect reads `design_docs/MANIFEST.md`, `CLAUDE.md`, `design_docs/architecture.md`, `design_docs/decisions/`, `design_docs/project_issues/`, the named TASK file, and any source code the task touches. It identifies real architectural decisions (decisions where alternatives materially differ), writes each as `design_docs/decisions/ADR-NNN-<slug>.md` with `Status: Proposed`, and updates `design_docs/architecture.md` (Proposed ADRs section). If an ADR resolves a known project issue, the corresponding `design_docs/project_issues/<slug>.md` is updated to `Status: Resolved by ADR-NNN`.

Each ADR must include:
- An "Alternatives considered" section with at least two real alternatives.
- A "My recommendation vs the user's apparent preference" section. If the architect disagrees with what the user appears to want (per the manifest, CLAUDE.md, the task, or recent conversation), it must say so and argue its case.
- A "Manifest reading" section that classifies the manifest entries it read as binding, as architecture-in-disguise, or flagged for revisit.

When it finishes, show me:
- Each new ADR file path
- A summary of what each decides
- Any pushback the architect raised against the apparent user preference (if any)

STOP. Do not run tests or implementation. I will:
1. Read each new ADR
2. Edit if needed
3. Mark `Status: Accepted` in the ADR file
4. Move the entry from Proposed to Accepted in `design_docs/architecture.md`
5. Run `/implement $ARGUMENTS`

If architect outputs `MANIFEST TENSION:` or `> NEEDS HUMAN:`, surface to me and stop.
