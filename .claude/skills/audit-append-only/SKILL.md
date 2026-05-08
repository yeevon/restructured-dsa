---
name: audit-append-only
description: Enforces append-only discipline on task audit files at `design_docs/audit/TASK-NNN-*.md`. Catches in-place rewrites of existing run entries, retroactive column additions to the Human-gates table, run-number gaps or duplicates, and other violations of the audit-log lifecycle in `CLAUDE.md`. Use before any agent or orchestrator writes to an audit file, during `/review`, or when investigating audit integrity. Reports violations only; does not auto-fix.
---

# Audit append-only

`CLAUDE.md` defines audit files as **append-only operational records**: agents may append new run entries, but they must not rewrite earlier entries except to correct an obvious path/typo, and any such correction is itself an appended note (not an in-place rewrite). This skill enforces that rule mechanically.

The audit file structure (per the template in `CLAUDE.md`):

```
# LLM Audit — TASK-NNN: <title>

**Task file:** ...
**Started:** ...
**Status:** <mutable; current state>
**Current phase:** <mutable; current phase>

## Human gates

| Time | Gate | Result | Notes |
|---|---|---|---|
| <row 1> ...
| <row 2> ...

## Agent runs

### Run 001 — <agent> (<phase>)
...

### Run 002 — <agent> (<phase>)
...
```

The header fields `Status:` and `Current phase:` are mutable (they reflect current state). Everything else — Human-gates rows, Run NNN entries, table structure — is append-only.

**Authority of this skill:** operational instruction (Tier 2). It does not introduce architectural claims. Concrete file paths come from `CLAUDE.md`'s audit-log section. The skill is a write-time discipline check; it cannot intercept writes (skills are invoked, not hooks), so it runs against `git diff`, `git diff --cached`, or recent file modifications and reports violations after the fact.

**Boundary with `authority-state-check`:** complementary. `authority-state-check` AS-4 catches the *consequence* of an audit rewrite (audit claim diverges from disk). `audit-append-only` catches the *act* (the diff against the audit file shows in-place modification of an existing entry). Both should be available; the skills overlap intentionally because audit integrity is load-bearing for the rest of the workflow.

## When to invoke

- **Any agent or orchestrator before writing to `design_docs/audit/TASK-NNN-*.md`:** consult this skill's rules before producing the diff. The skill cannot stop the write, but it defines what counts as a clean append vs. a violation, so the agent can avoid producing a violating diff in the first place.
- **Reviewer at `/review` (Phase 4):** walk the staged diff for any audit file in scope. Flag violations as part of the verdict.
- **Orchestrator before pre-gating new tests or before commit:** if any audit file is in `git status` as modified, run this skill against its diff.
- **At human request:** "check audit integrity", "did the audit get rewritten?", "is the audit append-only?".

## Output format

For each audit file in scope (working-tree-modified or staged), inspect the diff. Produce a structured violations report:

```
RULE: <id>
WHERE: <audit_file:line(s) or hunk reference>
EVIDENCE: <quoted diff excerpt>
SEVERITY: blocker | warn
TRACE: skill convention + CLAUDE.md audit-log section
```

Lead the report with a count summary: `N blockers, M warnings`. If zero violations, say so explicitly.

The report names *what* was rewritten and *why* it violates the rule; it does not perform fixes. Restoration is the owner's job (architect or human, per `CLAUDE.md`'s ownership table for the audit file's shared lane).

## Rules

### AA-1 — Existing run entries are not modified

A `### Run NNN` block, once written, is not modified. New runs are appended at the end of the "Agent runs" section. Modifications to the body of an existing run entry — even minor wording tweaks — violate this rule.

**Detection:** for each audit file in the diff, identify hunks that modify lines inside an existing `### Run NNN` block (where `NNN` is not the highest-numbered run being added in this diff). Any such hunk is a violation.

- **Severity:** **blocker**.
- **Trace:** `CLAUDE.md` ("Agents may append new run entries; they must not rewrite earlier entries...").

### AA-2 — Human-gates table rows are append-only

The Human-gates table grows by appending new rows at the bottom. Existing rows — including the column count, the column headers, and the cell contents — are not modified after they are written.

**Detection:** for each audit file in the diff, inspect the Human-gates table:
- New rows appended at the end → OK.
- Modifications to existing rows (text, ordering, removal) → violation.
- Column additions or removals (e.g., the TASK-002 cycle's retroactive "Commited" column on TASK-001's audit) → violation.
- Header separator changes (e.g., `|---|---|---|---|` becoming `|---|---|---|---|---|`) → violation.

- **Severity:** **blocker** for column additions, header separator changes, or content modifications to existing rows; **warn** for whitespace-only normalization of existing rows (a sign of linter interference).
- **Trace:** `CLAUDE.md` audit-log "Append-only during a task" rule.

### AA-3 — Run numbering is monotonic and gap-free

New run entries use `Run N+1` where `N` is the highest existing run number in the file. No gaps (skipping from Run 005 to Run 007), no duplicates (two Run 006 entries), no out-of-order entries (Run 005 appearing after Run 006 in the file).

**Run-number assignment is the orchestrator's responsibility.** The orchestrator reads the audit file, computes `N+1`, and passes the run number to the agent it invokes. **Agents must not infer the next run number by reading the file themselves**, and must never renumber or rewrite existing entries to "make room" for a new one. Self-counting by agents is the brittle pattern this rule explicitly prevents.

**Detection:** parse all `### Run NNN` headers in the file (after the diff is applied). Verify the sequence is `1, 2, 3, ..., max` with no gaps and no duplicates, and that the entries appear in numerical order in the file.

- **Severity:** **blocker** for gaps, duplicates, or out-of-order entries.
- **Trace:** skill convention; reinforced by `CLAUDE.md`'s template structure (sequential `Run NNN` headers).

### AA-4 — Typo and path corrections are appended, not rewritten in place

Corrections to prior audit content are recorded as **new appended audit material**, never by editing the original run body. Prior run entries remain immutable; the original (incorrect) text stays visible where it was first written.

**Allowed correction shapes:**
- a new normal run entry, if the correction happens as part of a later agent or orchestrator run; **or**
- a dedicated `## Audit corrections` section at the end of the file, containing append-only correction entries.

Example correction-section entry:

```
## Audit corrections

### Correction 001 — 2026-05-08

**Corrects:** Run 003
**Original text:** `Commited`
**Correction:** `Committed`
**Reason:** typo in Human-gates note
```

The original text in Run 003 is **not** edited; the correction lives outside the run entry it describes.

**Detection:** an in-place modification of an earlier run entry that the diff or commit message describes as "fixing a typo" is still a violation of AA-1. The fix shape is to add a new run entry or append to the `## Audit corrections` section.

- **Severity:** **blocker** when an in-place rewrite is justified as a typo fix.
- **Trace:** `CLAUDE.md` ("...except to correct an obvious path/typo, and any such correction is itself an appended note (not an in-place rewrite)") — interpreted strictly so that AA-1 has no carve-out.

### AA-5 — Header field updates are exempt

The file's top-of-document fields are mutable and may be updated freely:

- `**Status:**` (e.g., `In progress` → `Blocked — parked` → `In progress` → `Implemented` → `Reviewed` → `Committed`)
- `**Current phase:**` (e.g., `next` → `design` → `test` → `implement` → `verify` → `review`)

The `**Started:**` and `**Task file:**` fields, once set, should not change. Modifications to those are flagged.

**Detection:** modifications above the `## Human gates` heading are inspected; only `Status:` and `Current phase:` lines may change.

- **Severity:** **blocker** for modifications to `Started:` or `Task file:`; **OK** for `Status:` and `Current phase:` updates.
- **Trace:** `CLAUDE.md` audit-log lifecycle ("Status: In progress | Blocked | Implemented | Reviewed | Committed", `Current phase: next | design | test | implement | verify | review`).

### AA-6 — Existing tables stay fixed once written; new tables in new run entries are allowed

**Existing tables** (Human-gates, any sub-table introduced by an earlier run) keep their column count, column headers, and header separator stable across the file's lifetime. Adding a column retroactively to record a state that didn't exist at write time is a violation; the right shape is to append a new row, a new run entry, or a new section that records the new state.

**Newly appended run entries may introduce new tables** (e.g., a per-phase metrics table) — but once written, those new tables become subject to the same append-only rule under AA-1: their structure is fixed and their rows are append-only.

**Detection:** for each table that already existed before the diff, compare the column count and header line before/after. Any change is a violation. Tables introduced by new run entries are exempt at creation time but immediately fall under AA-1 + AA-6 once the entry is written.

- **Severity:** **blocker** for modifications to pre-existing tables.
- **Trace:** skill convention; reinforced by the TASK-002 cycle's TASK-001-audit "Commited" column case.

## Notes

- The skill is a discipline check, not a hook. Agents must consult it before writing to maximize the chance of producing a clean append. After-the-fact detection during `/review` catches violations that slipped through.
- Linters that auto-normalize markdown can produce whitespace-only diffs that look like AA-2 violations. Treat as **warn** and let the human decide whether to keep the normalization or revert; if normalization is desired, the project should adopt a project-wide markdown formatter and run it once across all audits in a single dedicated commit, not interleaved with task work.
- The append-only rule applies to **task audit files** specifically. Other markdown files in `design_docs/` (architecture.md, ADRs, project_issues, task files) have their own lifecycle rules and are not in scope here. `authority-state-check` covers state coherence across those surfaces.
- This skill does not enforce the *content* of audit entries (whether a run entry is complete, whether the right files are listed, whether the output summary is accurate). Content-quality checks belong to the agent that writes the entry, the orchestrator that reads it, and the reviewer at `/review`.
