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

| Tier | Files | Allowed to introduce architecture? |
|---|---|---|
| 1. Binding authority | `MANIFEST.md`, Accepted ADRs in `design_docs/decisions/`, `design_docs/architecture.md` (index only) | MANIFEST: only product behavior. ADRs: yes. architecture.md: **no** — must cite an Accepted ADR. |
| 2. Operational instruction | `CLAUDE.md`, `.claude/commands/*.md`, `.claude/agents/*.md`, `.claude/skills/*/SKILL.md` | No. Process and conventions only. |
| 3. Proposed work | task files, Proposed ADRs, files in `project_issues/` | No (issues raise questions; tasks request work; Proposed ADRs await human gate). |
| 4. Reference / context | notes, plans, scratch, conversation exports, drafts | No. |

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

- Run: `<dev command>`
- Test: `pytest`
- Lint: `ruff check --fix && ruff format`
- Type check: `mypy cs300/`

## Conventions

These are workspace conventions, not architecture. Architectural patterns live in `design_docs/architecture.md`. Do not infer patterns from examples in this file.

- Public functions get type hints; private helpers can skip them when types add no information.
- Commit format: `<type>(<scope>): <description>`. Scopes derive from the active task; do not invent scopes that aren't reflected in the codebase.

## Pushback protocol (every agent, every layer)

The project flows: **MANIFEST → architecture.md → ADRs → project_issues → tasks → tests → code**. Each layer is a contract for the next layer to satisfy. Each agent reads the upstream layers and produces the next layer.

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

When an agent surfaces a flaw, the *owner* is the one who edits. The agent that found the flaw does not edit upstream artifacts itself.

**Critical engagement is mandatory, not optional.** Silent compliance with a flawed upstream artifact is a process failure, not a virtue. The boundary: pushback targets architecture, ADRs, tasks, tests, code, and CLAUDE.md framing — never manifest behavior, scope, non-goals, invariants, or glossary terms (those go to MANIFEST TENSION and stop).

## What this project is NOT

See `design_docs/MANIFEST.md` §5 (Non-Goals). Examples: no auth, no multi-user, no AI tutor chat, no mobile, no LMS features. If you find yourself sketching something that fits one of those, stop and surface the conflict.
