---
name: authority-state-check
description: Verifies coherence across the project's authority surfaces — ADR files on disk, `architecture.md`, task audit Human-gates tables, project_issues, and task files. Use before `/implement`, before `/review`, and whenever an ADR's `Status` changes. Catches drift such as Accepted ADRs being edited, architecture.md missing a row for a gated ADR, audit gates that disagree with on-disk ADR states, project_issues claiming resolution by a still-Proposed ADR, or `/implement` starting while a task ADR is still Proposed. Reports drift only; does not auto-fix.
---

# Authority state check

This skill enforces *state coherence* across the project's authority surfaces. It is complementary to `manifest-conformance` (which enforces *content* drift — chapter-number literals, AI-SDK use, etc.). The two skills operate on different axes: content versus state.

The authority surfaces this skill watches:

1. **ADR files** at `design_docs/decisions/ADR-NNN-*.md` (the source of architectural truth).
2. **`design_docs/architecture.md`** (the index — mirrors Accepted-ADR set only; never introduces architecture).
3. **Task audit Human-gates tables** at `design_docs/audit/TASK-NNN-*.md` (the operational record of what the human gated).
4. **Project_issues files** at `design_docs/project_issues/*.md` (open architectural questions and their `Resolved by ADR-NNN` closures).
5. **Task files** at `design_docs/tasks/TASK-NNN-*.md` (where ADRs are referenced as dependencies).

**Authority of this skill:** operational instruction (Tier 2). It does not introduce architectural claims. It does not decide *what* an ADR should say or whether an ADR should be Accepted; it only verifies that the disk state is internally consistent across surfaces. The markdown-authority rule from `CLAUDE.md` is the load-bearing reference: ADRs are the source of architectural truth; everything else mirrors them.

## When to invoke

- **Orchestrator before `/implement`:** as part of the precondition check. Drift here is the most common cause of mid-implementation surprises (e.g., implementer reads an Accepted ADR that has unrecorded content edits, or architecture.md is missing a row for an ADR the task depends on).
- **Reviewer at `/review` (Phase 4):** before the conformance walk. State drift discovered after staged code is wasted review time; catching it first lets the reviewer either flag for fix-before-commit or proceed knowing the diff sits on coherent authority.
- **Architect or orchestrator on ADR `Status` change:** best-effort — invoked immediately after any agent or human flips `Status: Proposed → Accepted`, `Accepted → Superseded`, or `Proposed → Rejected`. Catches missed mechanical state transitions (the architecture.md row move, the audit Human-gates row addition).
- **Architect Mode 2 (`/design`) at end of run:** after drafting Proposed ADRs, before stopping. Verifies the new ADRs are properly registered in architecture.md's Proposed table and no upstream coherence broke.
- **At human request:** "check authority state", "audit drift across docs", "are the ADRs and architecture.md in sync".

## Output format

Walk the rules below against the on-disk state. Produce a structured drift report:

```
RULE: <id>
WHERE: <file:line or surface name>
EVIDENCE: <quoted excerpt or finding>
SEVERITY: blocker | warn | dormant
TRACE: <authority surface or skill convention>
```

Lead the report with a count summary: `N blockers, M warnings, K dormant`. If zero drift, say so explicitly. The report names *what* is drifted; it does not perform fixes. The owner-of-fix per `CLAUDE.md`'s ownership table executes the correction.

## Rules

### AS-1 — Accepted ADR content immutability

An ADR file with `Status: Accepted` is not edited substantively after the gate. Substantive means: changes to the Decision section, the Alternatives, the Consequences, the Manifest reading, or the Conformance check. Mechanical corrections (typos, dead links, formatting normalization) are allowed and should be recorded as the only diff in their commit.

To change a substantive part of an Accepted ADR, choose one of:
- **Supersede:** draft a new ADR (`Status: Proposed`) that supersedes the old one. The old ADR's `Status` becomes `Superseded` once the new one is Accepted.
- **Revert to Proposed:** flip the ADR's `Status` back to `Proposed`, edit, then re-gate. The architecture.md row moves with it.

**Detection (minimum viable):**
- For each ADR file appearing in `git diff --name-only` or `git diff --cached --name-only`, read its `Status` field.
- If `Status: Accepted`, inspect the diff:
  - If the diff changes the Decision, Alternatives, Consequences, Manifest reading, or Conformance check sections → report AS-1 blocker.
  - If the diff only changes typos, formatting, dead links, or table placement → no blocker; report it as a mechanical edit so the human can confirm.

**Detection (stronger, optional):**
- If verifying that a currently-Accepted ADR has remained pristine since its acceptance, walk `git log -- design_docs/decisions/ADR-NNN-*.md` to find the commit where `Status` first became `Accepted`, then diff against the current file. Use only when the lightweight check is insufficient (e.g., during a periodic audit or when investigating a specific drift report); not required on every skill invocation.

- **Severity:** **blocker** for substantive diffs against an Accepted ADR.
- **Trace:** `CLAUDE.md` markdown-authority rule (Accepted ADRs are binding) + this skill's operational definition of "substantive."

### AS-2 — ADR Status values are coherent

Every ADR file's `Status` field is one of: `Proposed`, `Pending Resolution`, `Accepted`, `Superseded`, `Rejected`. No other value. The status is parseable from a single line near the ADR header.

- **Severity:** **blocker** for unrecognized status values; **warn** for missing or malformed status fields.
- **Trace:** convention surfaced by this skill; reinforced by `architecture.md`'s table headings (Accepted, Proposed, Pending resolution, Superseded).

### AS-3 — `architecture.md` mirrors ADR-disk states

`architecture.md` is a mirror, not a source. Cross-check:

- Every ADR with `Status: Accepted` on disk has exactly one row in `architecture.md`'s "Accepted ADRs" table.
- Every ADR with `Status: Proposed` on disk has exactly one row in "Proposed ADRs (awaiting human acceptance)".
- Every ADR with `Status: Pending Resolution` on disk has exactly one row in "Pending resolution (need human input)".
- Every ADR with `Status: Superseded` on disk has exactly one row in "Superseded" with the superseding ADR named.
- Every row in any `architecture.md` table corresponds to an ADR on disk with the matching `Status`.
- ADRs with `Status: Rejected` do not appear in any `architecture.md` table.
- Each row's **title** matches the ADR's title; the row's **task** and **date** fields match the ADR header. If `architecture.md` includes a summary column, the summary must be directly derived from the ADR's Decision section and must not add new meaning. `architecture.md` introduces no architectural content beyond the mirror.

- **Severity:** **blocker** when a row is missing for a gated ADR, when a row contains an ADR not on disk, or when a Rejected ADR appears in a Proposed/Accepted table.
- **Trace:** `architecture.md` opening line ("This file is an index of Accepted ADRs only. It does not introduce architectural claims; if it disagrees with an Accepted ADR, the ADR wins.") + `CLAUDE.md` Tier-1 authority table.

### AS-4 — Audit Human-gates table matches disk

For every task audit file at `design_docs/audit/TASK-NNN-*.md`, the Human-gates table's `ADR-NNN reviewed | accepted` rows match the on-disk ADR's `Status`. Specifically:

- Every audit row claiming `ADR-NNN reviewed | accepted` corresponds to an ADR file with `Status: Accepted`.
- Every audit row claiming `ADR-NNN reviewed | rejected` corresponds to an ADR file with `Status: Rejected`.
- Conversely, every ADR listed in the audit's `/design` run as proposed for that task and later marked `Accepted` or `Rejected` on disk has a corresponding Human-gates row.
- An audit's claimed-ADR-content quotation does not disagree with the on-disk ADR's content (no audit row may misrepresent an ADR's Decision or status).

- **Severity:** **blocker** when an audit gate disagrees with the on-disk ADR; **warn** when a gate is missing for an ADR that is Accepted but the audit pre-dates the gate (allow grandfathered cases with a one-line note).
- **Trace:** `CLAUDE.md` audit-log section ("audit file may quote or reference architectural claims only as evidence... if the audit log and an authoritative artifact disagree, the authoritative artifact wins").

### AS-5 — Project_issue ↔ ADR coherence

A `Status: Resolved by ADR-NNN` line in any project_issue requires ADR-NNN to be `Accepted` on disk. An `Open` project_issue whose resolving ADR is `Accepted` is also incoherent (one of them is stale). Specifically:

- `Resolved by ADR-NNN` ⇒ ADR-NNN exists with `Status: Accepted`.
- `Resolved by ADR-NNN` ⇒ ADR-NNN's content actually addresses the issue (a quick textual check; the ADR's Decision section references the project_issue's slug or restates its question).
- An `Open` project_issue whose subject is now decided by an Accepted ADR ⇒ flag as drift; either the issue is not actually resolved (and the ADR is incomplete), or the issue should be marked resolved and was not.

- **Severity:** **blocker** when the resolved-by claim points to a non-Accepted or missing ADR; **warn** when an Open issue overlaps with an Accepted ADR's subject.
- **Trace:** `CLAUDE.md` ("if the decision resolves a known project issue, update the corresponding `design_docs/project_issues/<slug>.md` to `Status: Resolved by ADR-NNN`").

### AS-6 — Task ↔ ADR coherence

A task file's references to ADR statuses match disk. Task files commonly include sections like "Architecture state assumed" or "Accepted ADRs this task depends on." Each cited ADR's status in the task file matches the ADR file's `Status`.

- A task that says "depends on ADR-NNN (Accepted)" while ADR-NNN is `Proposed` is drift.
- A task that lists an ADR as a `/design` deliverable while the ADR file already has `Status: Accepted` from a prior task is also drift (the task's `/design` work is already done and should be recorded as such or the dependency rephrased).

- **Severity:** **warn** by default; **blocker** if `/implement` is about to run on a task whose ADR-status claims diverge from disk.
- **Trace:** convention; reinforced by the markdown-authority rule.

### AS-7 — `/implement` does not start with Proposed/Pending ADRs

No `/implement` phase begins while any ADR named as a task dependency or as a `/design` deliverable is in `Status: Proposed` or `Status: Pending Resolution`. This is a hard precondition; soft overrides ("the user re-invoked `/implement`, treating it as implicit confirmation") are not acceptable.

The orchestrator (or whoever advances the workflow) must verify on-disk ADR statuses, not memory of recent gates. State on disk is the contract.

- **Severity:** **blocker**.
- **Trace:** `/implement` precondition (per the project's slash-command definition) + this skill's operational rule against soft overrides of state preconditions.

## Notes

- This skill verifies *state coherence*, not *content correctness*. An ADR that is internally consistent across all surfaces but contains a flawed Decision is out of scope here — `manifest-conformance` and the architect's own critical engagement are the surfaces for that.
- Mechanical fixes for drift this skill detects are owned per `CLAUDE.md`: architect for ADR/architecture.md/project_issues/tasks; human for `MANIFEST.md`/`CLAUDE.md`/skills; shared for audit Human-gates rows.
- Run cost is small — most checks are status-line greps and table-row matches across a bounded set of files. The skill should run quickly enough to be a routine precondition rather than an occasional audit.
- This skill does not enforce *write-time* discipline (it cannot intercept an agent's edit of an Accepted ADR). It catches the drift at the next boundary (`/implement`, `/review`, or status change). Pair with append-only-style write-time skills for narrower coverage where appropriate.
