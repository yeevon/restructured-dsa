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

Architect also appends a run entry to the task audit file at `design_docs/audit/TASK-NNN-<slug>.md` before stopping (per CLAUDE.md "LLM audit log"), recording: files read, tools/commands, ADRs created, project_issues opened/resolved, architecture.md rows added, leaks found, pushback raised, whether implementation is blocked pending human acceptance.

When it finishes, show me:
- Each new ADR file path and a one-line summary of what each decides.
- The `architecture.md` row(s) added (Proposed ADRs / Pending resolution).
- The audit file path with a pointer to the new run entry.
- Any pushback the architect raised against the apparent user preference.
- Any `ARCHITECTURE LEAK:` blocks the architect found while reading the inputs.

STOP. Do not run tests or implementation. I will:
1. Review each new ADR file.
2. Edit if needed.
3. Mark `Status: Accepted` in each ADR file (or reject — see below).
4. Update `architecture.md` to reflect the new ADR state. Either:
   - ask the architect to perform the mechanical state transition (move the row from "Proposed ADRs" to "Accepted ADRs," regenerate the project-structure summary from the current Accepted ADR set), **or**
   - perform the mechanical move myself.

   **No substantive architecture may be added to `architecture.md` during this move.** It only ever mirrors the current Accepted ADR set.

5. If I reject an ADR (do not mark Accepted): the architect removes the row from "Proposed ADRs" in `architecture.md` and regenerates the project-structure summary from the unchanged Accepted ADR set. The rejected ADR file remains on disk for history, with a note explaining why it was rejected.

6. Add a row to the audit file's "Human gates" table for each ADR I gate: `<timestamp> | ADR-NNN reviewed | accepted | <notes>` (or `rejected`). Update the audit header `Status` to `In progress` once all task ADRs are Accepted and architecture.md reflects them.

7. Run `/implement $ARGUMENTS` only after every ADR for this task is `Accepted` and `architecture.md` reflects that.

If architect outputs `MANIFEST TENSION:`, `> NEEDS HUMAN:`, or `ARCHITECTURE LEAK:`, surface to me and stop.
