# Restructured CS 300 — Architecture

**Status:** Index and summary only. The source of architectural truth is the set of Accepted ADRs in `design_docs/decisions/`. This document does not introduce architectural claims; it is a derived view of `design_docs/decisions/` that mirrors ADR state and carries a project-structure summary regenerated from Accepted ADRs. If `architecture.md` and the ADR files disagree, **the ADR files win**.

**Authority order:** `MANIFEST.md` → Accepted ADRs → this document (mirror of ADR state) → tasks.

**Drift-critical guardrails** live in the `manifest-conformance` skill at `.claude/skills/manifest-conformance/SKILL.md`. The skill traces each rule to either the manifest (binding) or an Accepted ADR (binding while in force). Until a rule's backing ADR is Accepted, the architecture portion of the rule is dormant.

**Ownership:** the architect agent maintains this file, but only as a state-mapping function of `design_docs/decisions/`. No agent introduces a stack/schema/routing/persistence/source-layout/workflow/provider/algorithm decision here — those go in ADRs. Any architectural claim in this file without an ADR citation is an **ARCHITECTURE LEAK** and must be removed.

---

## Accepted ADRs

| # | Title | Task | Date |
|---|---|---|---|
| (none yet) | | | |

## Proposed ADRs (awaiting human acceptance)

| # | Title | Task |
|---|---|---|
| (none yet) | | |

## Pending resolution (need human input)

- (none yet)

## Superseded

| # | Title | Superseded by | Date |
|---|---|---|---|
| (none yet) | | | |

## Project structure (derived from Accepted ADRs)

(No Accepted ADRs yet. The architect regenerates this section from `design_docs/decisions/` each time the Accepted ADR set changes. No content may appear here that is not summarized from an Accepted ADR.)

## Maintenance protocol (state-change-driven only)

This file is a **derived view of `design_docs/decisions/`**. It updates only when an ADR's state changes — never as a place to record architecture.

- **ADR `Proposed` → `Accepted`:** move the row from "Proposed ADRs" to "Accepted ADRs"; regenerate the project-structure summary from the new Accepted ADR set.
- **ADR `Proposed` → rejected:** remove the row from "Proposed ADRs"; summary unchanged (the rejected ADR never entered Accepted).
- **ADR `Accepted` → `Superseded`:** move row to "Superseded"; add replacement to "Accepted"; regenerate summary.
- **ADR `Pending Resolution` → `Accepted`:** remove from "Pending resolution"; list under "Accepted"; regenerate summary.
- **ADR `Pending Resolution` → withdrawn:** remove from "Pending resolution"; summary unchanged.

**Regeneration rule:** the project-structure summary is recomputed from the current set of Accepted ADRs each time that set changes. It is a function of the Accepted ADR set; it never introduces an independent claim.

If `architecture.md` is edited in any other way — adding a sentence not derivable from an Accepted ADR — that is itself an ARCHITECTURE LEAK and the reviewer must flag it as blocking.
