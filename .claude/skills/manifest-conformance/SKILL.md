---
name: manifest-conformance
description: Drift-critical guardrails that keep code aligned with `design_docs/MANIFEST.md` invariants and Accepted ADRs in `design_docs/decisions/`. Use when reviewing pending changes, before commits, when the reviewer agent runs, or when the user asks to "check conformance" / "audit for drift" / "verify manifest invariants". Reports violations only — does not auto-fix.
---

# Manifest conformance

This skill enforces the small set of rules whose violation would cause the codebase to drift away from manifest invariants or Accepted ADRs. Each rule traces to a manifest section (§) or to an Accepted ADR.

**Authority of this skill:** rules that trace to the manifest (§5 Non-Goals, §6 Behaviors and Absolutes, §7 Invariants) are non-negotiable product behavior. Rules that trace to an Accepted ADR are binding while that ADR is in force; if an ADR is superseded, this skill is updated in the same commit. **This skill is operational instruction (Tier 2) and never introduces architectural claims.** Concrete names (file paths, package names, library names, workflow identifiers) come from the ADRs the rules cite, not from this file.

If a rule's backing ADR is not yet Accepted, the rule notes "ADR pending" and:
- the manifest portion is enforced as written,
- the architecture portion (specific paths, package names) is **dormant** — the skill returns `cannot evaluate (ADR pending)` for those checks until the ADR lands.

When invoked, walk the rules below against the pending diff (or the working tree, if asked broadly) and produce a structured violation report:

```
RULE: <id>
WHERE: <file:line or path>
EVIDENCE: <code excerpt or shell finding>
SEVERITY: blocker | warn | cannot evaluate (ADR pending)
TRACE: <manifest § or ADR-NNN>
```

Lead the report with a count summary (`N blockers, M warnings, K dormant`). If zero violations, say so explicitly with the count.

## Rules

### MC-1 — No direct LLM/agent SDK use
- **Trace:** manifest §4 (secondary objective: `ai-workflows` is the only AI engine the project commits to) + **ADR-036** (the `ai-workflows` integration — Accepted 2026-05-12; enumerates the forbidden-SDK set and names the workflow module path).
- **Manifest portion (active):** application code does not call any LLM SDK directly. All AI work goes through `ai-workflows` (the engine the manifest names).
- **Architecture portion (active per ADR-036):** application code under `app/` (including `app/workflows/`) must not `import` any of: `openai`, `anthropic`, `google.generativeai`, `google.genai`, `cohere`, `mistralai`, `groq`, `together`, `replicate` (or any other LLM-provider SDK); `litellm` (the unified adapter `ai-workflows` wraps); `langchain`, `langchain_*`, `langgraph`, `langgraph_*` (the orchestration layer `ai-workflows` wraps — CS-300 authors a `WorkflowSpec`, never a `StateGraph`); or a raw `httpx` / `requests` / `urllib` call to a provider's chat-completions / messages / generate endpoint (CS-300's existing `httpx`/`requests` use for `TestClient` and Playwright fixtures is fine — what is forbidden is a *direct LLM-API HTTP call* from `app/` code). The only AI dependency `app/` code imports is `ai_workflows.*` (the `WorkflowSpec` authoring API: `WorkflowSpec`, `LLMStep`, `ValidateStep`, `RetryPolicy`, `register_workflow`, plus `TierConfig` + a route type from `ai_workflows.primitives.tiers`); AI *invocation* goes through the `aiw` CLI subprocess (ADR-036). The CS-300 workflow module lives under `app/workflows/` (the question-generation workflow at `app/workflows/question_gen.py`).
- Severity: **blocker** for the manifest portion **and** for the package-name / module-path check (ADR-036 Accepted).

### MC-2 — Quizzes scope to exactly one Section
- **Trace:** manifest §6, §7.
- Every Quiz entity, route, query, and AI prompt references exactly one Section. There is no cross-Section Quiz, no Chapter-bound Quiz, no aggregated-across-Sections Quiz.
- Forbidden: `quiz_id` without an associated `section_id`; queries that select Questions from multiple `section_id` values into a single Quiz; routes that accept multiple Section IDs for one Quiz.
- Severity: **blocker**.

### MC-3 — Mandatory/Optional designation respects the canonical mapping
- **Trace:** manifest §6, §8 (Mandatory/Optional must be honored, exposed, and learner-viewable as Mandatory-only). The canonical Chapter → Mandatory|Optional mapping source is defined by an ADR (pending `/design`).
- **Manifest portion (active):** every learner-facing surface honors and exposes the split; learners can view Mandatory-only.
- **Architecture portion (dormant until ADR lands):** the specific mapping (which Chapters are Mandatory vs Optional, and where the data lives) comes from the relevant Accepted ADR.
- Forbidden once ADR lands: hardcoded chapter-number rules anywhere in code; per-Section overrides that contradict the Chapter; UI surfaces that hide the split.
- Severity: **blocker** for the manifest portion; `cannot evaluate (ADR pending)` for the mapping-source check.

### MC-4 — AI work is asynchronous from the learner's perspective
- **Trace:** manifest §6, §7.
- No code path completes AI processing synchronously inside the request that submits it. Submission, processing, and result delivery are decoupled in time. The learner is notified when results are ready (Notification entity, manifest §8).
- The full set of AI-driven workflows (and therefore which routes must not block on them) is defined by the AI-engine and tier-routing ADRs (pending `/design`).
- Severity: **blocker** for the manifest principle; specific workflow-name enumeration is `cannot evaluate (ADR pending)`.

### MC-5 — AI failures are surfaced, never fabricated
- **Trace:** manifest §6.
- When AI-driven processing fails, the failure is delivered to the learner as a failure. The system never substitutes a placeholder grade, fabricated Question, or stand-in Notification.
- Forbidden: fallback paths that synthesize a "looks like a grade" object on workflow exception; silent retries that mask permanent failure.
- Severity: **blocker**.

### MC-6 — Lecture source is read-only to the application
- **Trace:** manifest §5 (no in-app authoring), §6 (single source). The lecture source root path is defined by the source-layout ADR (pending `/design`).
- **Manifest portion (active):** the application reads lecture source and never writes to it. No code path writes to whatever the source-layout ADR designates as the lecture source root.
- **Architecture portion (dormant until ADR lands):** the specific path under which lecture source lives.
- The pre-commit guard separately ensures the lecture source root is never staged in the same commit that touches application code.
- Severity: **blocker** for the manifest principle; `cannot evaluate (ADR pending)` for the path-specific grep until an ADR names the root.

### MC-7 — Single user
- **Trace:** manifest §5, §6.
- No code path assumes multi-tenant capability: no `user_id` columns, no auth middleware, no per-user data partitioning, no role checks.
- Severity: **blocker**.

### MC-8 — Reinforcement loop is preserved
- **Trace:** manifest §7.
- Every post-first Quiz for a Section contains both replayed wrong-answer Questions and freshly-generated Questions. Replay-only or fresh-only Quizzes (after the first) are a bug.
- The first Quiz for a Section contains only fresh Questions (the bank is empty).
- Forbidden: composition code paths that skip the replay query when prior wrong answers exist; paths that skip fresh generation when the replay set is non-empty.
- Severity: **blocker**.

### MC-9 — Quiz generation is user-triggered
- **Trace:** manifest §7.
- No background job, scheduled task, or auto-trigger generates a Quiz. Every Quiz is generated in response to an explicit user action.
- Severity: **blocker**.

### MC-10 — Persistence boundary
- **Trace:** persistence-layer ADR (pending `/design`).
- Only the persistence package defined by the persistence-layer ADR talks to the database it owns. Routes, workflows, and templates do not embed SQL or open DB connections.
- Forbidden once ADR lands: DB driver imports outside the persistence package; raw SQL string literals outside the persistence package.
- Severity: `cannot evaluate (ADR pending)` until the persistence-layer ADR is Accepted; **warn** once the ADR is Accepted; escalate to **blocker** when the persistence package exists in code.

## How to invoke

- Manually: by asking "check manifest conformance on the staged diff" (or the slash-command shim once one exists).
- From the reviewer agent: invoke this skill against the staged diff. Any blocker in this skill's report is a review blocker. `cannot evaluate (ADR pending)` results are reported but do not block — they tell the human "this rule will become enforceable once the named ADR is Accepted."
- From a pre-commit hook: shell out to the grep checks for syntactic rules; for semantic rules (MC-2, MC-4, MC-5, MC-8, MC-9), require human review.

## Out of scope for this skill

- Code style, lint, type-check — handled by `ruff` and `mypy`.
- Architecture conformance that is not drift-critical — handled by the reviewer agent against Accepted ADRs.
- Manifest content edits — handled by the human author per manifest §9 Change Protocol.
- ADR drafting and acceptance — handled by the architect agent (drafts) and the human (gates `Accepted`).
