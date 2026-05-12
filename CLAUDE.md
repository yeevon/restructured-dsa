# Restructured CS 300

## Authority

Read in this order before any task:

1. **`design_docs/MANIFEST.md`** — locked source of truth for *what* the project is. Binding for product behavior, scope, non-goals, invariants, and glossary terms. If a request would violate a hard constraint, refuse and surface the conflict.
2. **`design_docs/decisions/` (Accepted ADRs)** — source of truth for *how* the project is built. Architecture decisions live here.
3. **`design_docs/architecture.md`** — index and summary of Accepted ADRs only. Does not introduce architectural claims; mirrors ADR state. If `architecture.md` and an ADR disagree, the ADR wins.
4. **`.claude/skills/manifest-conformance/SKILL.md`** — drift-critical guardrails. Each rule traces to the manifest or to an Accepted ADR. The reviewer invokes this skill rather than re-stating rules.
5. **`design_docs/project_issues/`** — open architectural questions awaiting `/design` resolution.
6. **`design_docs/tasks/`** — the active task file.

## Markdown authority rule

`.md` files are not automatically authoritative. Before treating a markdown statement as binding, classify the file:

| Tier | Files | Allowed to introduce architecture? | Authority |
|---|---|---|---|
| 1. Binding authority | `MANIFEST.md`, Accepted ADRs in `design_docs/decisions/`, `design_docs/architecture.md` (index only) | MANIFEST: only product behavior. ADRs: yes. architecture.md: **no** — must cite an Accepted ADR. | Yes |
| 2. Operational instruction | `CLAUDE.md`, `.claude/commands/*.md`, `.claude/agents/*.md`, `.claude/skills/*/SKILL.md` | No. Process and conventions only. | Process only |
| 3. Proposed work | task files, Proposed ADRs, files in `project_issues/` | No (issues raise questions; tasks request work; Proposed ADRs await human gate). | None until accepted |
| 4. Reference / context | notes, plans, scratch, conversation exports, drafts | No. | None |
| 5. Operational record / evidence | `design_docs/audit/TASK-NNN-<slug>.md` | No. May record decisions only as pointers to ADRs / tasks / reviewer findings. | None |

**No agent may treat a markdown statement as architecture unless it is backed by:**
- the manifest (for product behavior, scope, glossary, non-goals), or
- an Accepted ADR (for architecture), or
- `architecture.md` summarizing an Accepted ADR.

If a `.md` file contains an architectural claim without an Accepted-ADR reference, the reading agent must flag it as an **ARCHITECTURE LEAK** and not act on it. See "Markdown critique pass" below.

## Markdown critique pass

Before using any `.md` file as input, perform this critique pass:

- Is this file allowed (per the tier table above) to define what it is defining?
- Does it introduce architecture outside an Accepted ADR?
- Does it convert a user preference into a hard rule without decision history?
- Does it conflict with the manifest?
- Does it summarize an ADR accurately, or does it add new meaning?
- Is it stale relative to newer ADRs, tasks, or project issues?

If you find an architectural claim outside an Accepted ADR, output:

```
ARCHITECTURE LEAK:
File: <path>
Claim: <quoted text>
Why it is architecture: <reason — names a tool, fixes a schema, picks a pattern, etc.>
Missing authority: <which ADR would need to back this claim>
Recommended action: <flag for architect to draft an ADR | remove the claim | strip to neutral>
```

The reading agent does not edit the offending file. The owner does (architect for design docs; human for MANIFEST/CLAUDE.md/skills).

## Commands

Use the commands defined by the repository config when present. If no command is configured yet, surface that as a project setup gap. Do not invent tooling.

- Run: `uvicorn app.main:app --host 127.0.0.1 --port 8000`
- Test: `python3 -m pytest tests/`
- Process pending Quiz requests (out-of-band Quiz-generation processor, ADR-037): `python -m app.workflows.process_quiz_requests`
- Lint: `<project lint command>`
- Type check: `<project type-check command>`

## Conventions

These are workspace conventions, not architecture. Architectural patterns live in Accepted ADRs. `design_docs/architecture.md` may summarize them only when derived from Accepted ADRs. Do not infer patterns from examples in this file.

- Public functions get type hints; private helpers can skip them when types add no information.
- Commit format: `<type>(<scope>): <description>`. Scopes derive from the active task; do not invent scopes that aren't reflected in the codebase.
- **Task-file convention: programmatic ACs vs human-only Verification gates.** Acceptance criteria under `## Acceptance criteria` are programmatic — the test-writer translates each into one or more failing tests, and `/auto` rule 7 (`CANNOT TEST AC-N:`) stops the loop on any AC it cannot translate. Items whose only valid signal is a human eyeballing the artifact — rendered-surface visual review per `.claude/skills/ui-task-scope/SKILL.md` UI-5/UI-6, manual exploratory passes — go under a separate `## Verification gates (human-only; not programmatic ACs)` section. Test-writer does not write tests for them, `/auto` does not stop on them, and `/auto` Phase 5 files a `pending human` row in the audit Human-gates table for each so the human knows to fill it in post-commit. Misplacing a `"when the human reviews…"` item under Acceptance criteria is a process failure — the test-writer raises `PUSHBACK: AC-N is a human-only verification gate, not a programmatic AC.` and the task file must be corrected.

## LLM audit log

Every task gets an audit file at `design_docs/audit/TASK-NNN-<slug>.md`. The audit file is an **operational record, not architecture**. It does not create authority. It records what agents did, what files they touched, what decisions they surfaced, what tools/commands they ran, and what human gates occurred.

**Append-only during a task.** Agents may append new run entries; they must not rewrite earlier entries except to correct an obvious path/typo, and any such correction is itself an appended note (not an in-place rewrite).

**Lifecycle of the audit file:**

- `/next` (architect Mode 1) **creates** the file from the template below and appends Run 001.
- `/design` (architect Mode 2) **appends** Run NNN before stopping.
- `/implement` **appends** a run entry after each phase: test-writer, implementer, verify.
- The reviewer **appends** before its final output.
- The human (or whichever orchestrator advances the workflow) **updates the Human gates table** at gate transitions (task accepted, ADRs accepted, tests reviewed, commit reviewed).

**What the audit file may record:**

- Files read / created / modified / deleted.
- Tools and commands invoked.
- Decisions surfaced — only as pointers to ADR-NNN, project_issues/<slug>, or reviewer findings. Never as a place to record an architectural decision directly.
- Pushback / escalations / `ARCHITECTURE LEAK:` blocks raised.
- Test, conformance, and verification results.

**What the audit file may NOT do:** introduce architectural authority, record a new architectural decision as binding, or act as a rulebook.

The audit file may quote or reference architectural claims only as evidence:

- `ADR-NNN decided <short label>`
- `ARCHITECTURE LEAK raised against <file>`
- `Reviewer found decision in code without ADR`

Agents do not consult the audit log to decide what to do. They consult the manifest, Accepted ADRs, the task file, and the conformance skill. If the audit log and an authoritative artifact disagree, the authoritative artifact wins.

### Audit file template

```
# LLM Audit — TASK-NNN: <title>

**Task file:** `design_docs/tasks/TASK-NNN-<slug>.md`
**Started:** <ISO timestamp>
**Status:** In progress | Blocked | Implemented | Reviewed | Committed
**Current phase:** next | design | test | implement | verify | review

---

## Human gates

| Time | Gate | Result | Notes |
|---|---|---|---|

---

## Agent runs

(runs are appended in order; see per-agent prompts for the entry shape each agent appends)
```

Per-agent run-entry shapes are defined in each agent's prompt. The general shape is: timestamp; input files read; tools/commands used; files created/modified/deleted; decisions surfaced (as pointers); leaks/pushback raised; tests/conformance/verification results; output summary.

## Orchestrator verification of subagent outputs

*See `design_docs/decisions/ADR-016-orchestrator-verification-of-subagent-outputs.md` (Accepted, 2026-05-08). This section is the operational quick-reference; ADR-016 is authoritative. Amendments go through a supersedure ADR, not via edits to this section.*

The orchestrator (the top-level Claude session driving `/next`, `/design`, `/implement`, `/review`) is responsible for verifying that each subagent actually produced the file changes it was expected to produce. Subagent summaries describe *intent*, not *outcome* — trust but verify.

**After every subagent returns**, the orchestrator must:

1. **Identify the expected file changes** from the subagent's task (e.g., "architect creates ADR-011," "architect updates architecture.md," "test-writer creates test file," "implementer modifies app/parser.py").
2. **Run `git diff` on each expected file** to confirm the change exists and is substantively correct. A diff check is sufficient — do not pull full file context unless the diff reveals a problem.
3. **If a file was supposed to be created**, confirm it exists (e.g., `git diff --name-only` or a quick glob).
4. **If an expected change is missing or incomplete**, the orchestrator remedies the gap itself before proceeding to the next phase. Do not delegate to another subagent for a fix the orchestrator can make directly. **Exception:** test assertion files (`tests/**/test_*.py`, `tests/**/*_test.py`) are excluded from this remedy-directly authority — re-invoke the test-writer with a delta brief instead. See ADR-021.
5. **Append a note to the audit file** whenever a subagent fails to produce an expected update:

```
**Orchestrator remediation:** <agent type> (Run NNN) was expected to update <file path> with <description>. Change was missing/incomplete. Orchestrator applied the fix directly.
```

This verification step is mandatory at every phase transition: after `/next` (architect), after `/design` (architect), after each `/implement` phase (test-writer, implementer), and after `/review` (reviewer). The cost is one `git diff` per expected file — not a full re-read of the project.

## Pushback protocol (every agent, every layer)

The project flows: **MANIFEST → Accepted ADRs → tasks → tests → code**. Each layer is a contract for the next layer to satisfy. Each agent reads the upstream layers and produces the next layer.

Supporting records (not authority layers):

- `design_docs/architecture.md` summarizes Accepted ADRs.
- `design_docs/project_issues/` tracks unresolved architecture questions.
- `design_docs/audit/` records what happened.

The protocol is bidirectional. Every agent that reads an artifact also critiques it.

**Downflow (problems found in something you read):** if any upstream artifact (manifest, architecture.md, an ADR, a project_issue, a task, the tests) is internally contradictory, contradicts a higher layer, would force a conformance-skill violation, or is missing a case the layer below cannot resolve without making a silent decision — STOP and surface a `PUSHBACK:` (or `MANIFEST TENSION:` for manifest issues, `ARCHITECTURE FLAW:` for architecture.md issues). Do not route around the flaw. Do not make a silent compensating decision in your own layer.

**Upflow (problems discovered while you work):** if implementation reveals that an upstream artifact didn't anticipate a real case (the task is silent on a scenario the code must handle, the ADR didn't enumerate an alternative the implementer now sees is better, the architecture pattern doesn't fit a constraint that just surfaced) — STOP and surface upward as an `ESCALATION:` or `ADJACENT FINDING:`. Do not silently expand scope; do not silently leave the gap for the user to discover.

**Ownership of fixes:**

| Artifact | Owner who edits it |
|---|---|
| MANIFEST.md, CLAUDE.md, manifest-conformance skill | Human author |
| architecture.md, ADRs, project_issues, tasks | Architect agent (during `/next` and `/design`) |
| tests | test-writer agent (during `/implement`) |
| code | implementer agent |
| `design_docs/audit/TASK-NNN-<slug>.md` | Shared operational record: agents append their own run entries; human updates the Human gates table |

When an agent surfaces a flaw, the *owner* is the one who edits. The agent that found the flaw does not edit upstream artifacts itself.

**Critical engagement is mandatory, not optional.** Silent compliance with a flawed upstream artifact is a process failure, not a virtue. The boundary: pushback targets architecture, ADRs, tasks, tests, code, and CLAUDE.md framing — never manifest behavior, scope, non-goals, invariants, or glossary terms (those go to MANIFEST TENSION and stop).

## What this project is NOT

See `design_docs/MANIFEST.md` §5 (Non-Goals). Examples: no auth, no multi-user, no AI tutor chat, no mobile, no LMS features. If you find yourself sketching something that fits one of those, stop and surface the conflict.
