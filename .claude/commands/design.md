---
description: Architect records architecture decisions for a task. Stops before tests.
argument-hint: [task ID, e.g. TASK-001]
allowed-tools: Read, Write, Edit, Glob, Grep
---

Invoke the architect subagent in **Mode 2** for task $ARGUMENTS.

Architect reads `design_docs/MANIFEST.md`, `CLAUDE.md`, `.claude/skills/manifest-conformance/SKILL.md`, `design_docs/architecture.md`, `design_docs/decisions/`, `design_docs/project_issues/`, the named TASK file, and any source code the task touches.

It identifies real architectural decisions (decisions where alternatives materially differ). For each decision:

- **Every architectural decision is recorded as an ADR** at `design_docs/decisions/ADR-NNN-<slug>.md` (with `Status: Proposed`). ADRs are the source of architectural truth.
- `design_docs/architecture.md` is updated mechanically: a row added to "Proposed ADRs" (or "Pending resolution" if the ADR is `Pending Resolution`). The architect does NOT introduce architectural content into `architecture.md` — it remains an index/summary of Accepted ADRs.
- If the decision resolves a known project issue, update the corresponding `design_docs/project_issues/<slug>.md` to `Status: Resolved by ADR-NNN`.

Each ADR (when written) must include:
- An "Alternatives considered" section with at least two real alternatives.
- A "My recommendation vs the user's apparent preference" section. If the architect disagrees with what the user appears to want (per the manifest, CLAUDE.md, the task, or recent conversation), it must say so and argue its case. Boundary: pushback targets architecture.md, ADRs, tasks, and CLAUDE.md framing — never manifest behavior, scope, non-goals, invariants, or glossary terms.
- A "Manifest reading" section that names which manifest entries it read as binding for this decision and which it flagged as architecture-in-disguise (for reporting only — flagging does not authorize routing around the manifest).
- A "Conformance check" section listing which drift-critical guardrails (from the conformance skill) the decision touches and how it stays compliant.

When it finishes, show me:
- Each new ADR file path and a one-line summary of what each decides.
- The `architecture.md` row(s) added (Proposed ADRs / Pending resolution).
- Any pushback the architect raised against the apparent user preference.
- Any `ARCHITECTURE LEAK:` blocks the architect found while reading the inputs.

STOP. Do not run tests or implementation. I will:
1. Review each new ADR file.
2. Edit if needed.
3. Mark `Status: Accepted` in each ADR file.
4. Move the row in `architecture.md` from "Proposed ADRs" to "Accepted ADRs" (and update the project-structure summary if the new ADR changes it). The architect can perform this mechanical move on a follow-up `/design` invocation, but never alters the ADR's substantive content.
5. Run `/implement $ARGUMENTS`.

If architect outputs `MANIFEST TENSION:`, `> NEEDS HUMAN:`, or `ARCHITECTURE LEAK:`, surface to me and stop.
