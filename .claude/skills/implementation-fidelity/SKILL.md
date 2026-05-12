---
name: implementation-fidelity
description: Verifies the implementation faithfully realizes the positive design commitments of the Accepted ADRs a task cites — route contracts, named mechanisms, named symbols, status machines — and that no HTTP route, module, class, or public function exists that no cited ADR or test introduced. Complementary to manifest-conformance (which enforces prohibitions) and authority-state-check (which enforces doc-state coherence). Use before the implementer declares a run done, during /review, and at /auto Phase 5 verification. Reports findings only; does not auto-fix.
---

# Implementation fidelity

`manifest-conformance` enforces *prohibitions* — the things the code must not do (no LLM SDK outside the boundary, no cross-Section Quiz, no `user_id`). `authority-state-check` enforces *doc-state coherence* — ADRs vs `architecture.md` vs audit gates. This skill enforces the third axis: **did the code build the thing the decision decided?** When an Accepted ADR's *Decision* section commits to a route contract, a mechanism, a module/function name, or a state machine, the implementation must realize *that* — not a different design that happens to pass the same tests.

The failure mode this skill exists to catch: an implementer hits a tension between a test assertion and an ADR's named design, and — instead of raising `PUSHBACK:` so the test-writer or architect resolves it — engineers a workaround (a substitute redirect mechanism, an extra route the ADR didn't name, a different dispatch primitive wrapped to resemble the named one). The test suite goes green; the architecture has silently drifted. A green suite obtained that way is a process failure, not a success.

**Authority of this skill:** operational instruction (Tier 2). It does not introduce architectural claims and does not decide *what* an ADR should say. Concrete names — route paths, mechanisms, symbol names, state names — come from the Accepted ADRs the rules cite, never from this file. If a task cites no ADR that makes a positive design commitment, this skill's *behavioral* rules (AF-1, AF-2, AF-4) are dormant for that task; AF-3 (the unbacked-surface check) and AF-5 (the workaround-smell check) still apply — they need no cited ADR.

**Boundary with the implementer agent's self-checks:** `implementer.md` carries a "new public-surface check" and an "ADR fidelity is non-negotiable" hard rule that an implementer is expected to apply *while it works*. This skill is the same checklist run *independently* — at `/review` and at `/auto` Phase 5 — so an implementer that skipped its own check doesn't slip through. The rules below are written so a reviewer can apply them without trusting the implementer's run entry.

## When to invoke

- **Implementer at end of `/implement` Phase 2:** before declaring the run done. Walk the diff against every Accepted ADR the task cites. Any `blocker` is a self-detected escalation — surface it as `PUSHBACK:`; do not ship the diff with the deviation and a footnote.
- **Reviewer during `/review` (Phase 4):** as a first-class check alongside `manifest-conformance` and `test-honesty-check`. A staged diff that deviates from a cited ADR's named design is a blocking finding regardless of test status.
- **Orchestrator at `/auto` Phase 5 (verify):** walk it against the working tree before staging. A `blocker` stops the loop — the implementer's output is not substantively correct against the ADRs (see `CLAUDE.md` "Orchestrator verification of subagent outputs"; ADR-016).
- **Architect during `/design`:** optional sanity pass — if an ADR's *Decision* section is so vague that AF-1/AF-2/AF-4 cannot be evaluated against a future diff, that is a sign the ADR needs a sharper Decision section before it ships.
- **At human request:** "did the implementation follow the ADRs?", "check implementation fidelity", "did anything drift from what we decided?".

## How to walk it

1. Enumerate the Accepted ADRs the task cites — the task file's dependency/citation list, plus any ADR the diff's own code comments reference.
2. For each, read its *Decision* section and extract every **positive design commitment**:
   - **Route definitions** — method, path, status code, redirect target (if any), request body shape, response body shape.
   - **Mechanism choices** — the named concurrency/dispatch primitive ("FastAPI `BackgroundTasks`"), storage approach ("stdlib `sqlite3`, no ORM"), redirect pattern ("PRG via a single `303`"), parsing approach, etc., *and* any mechanism the ADR explicitly *rejected*.
   - **Named symbols** — module paths, function/class names, parameter names, signatures the ADR commits to.
   - **State machines** — the named states and the allowed transitions between them.
3. For each commitment, find where the diff realizes it and confirm it matches. A mismatch — including a *substitute* that achieves a similar effect by different means — is a finding.
4. Independently of any ADR, scan the diff for new HTTP routes, new modules, new classes, and new public functions; check each against the cited ADRs and the test files (AF-3).
5. Scan the diff for comments/structure that exist to satisfy a specific test assertion rather than the feature (AF-5), and re-check AF-1/AF-2/AF-3 at each such site.

## Output format

```
RULE: <id>
WHERE: <file:line | route | symbol>
EVIDENCE: <code excerpt or finding — and the ADR clause it collides with>
SEVERITY: blocker | warn | dormant (no cited ADR makes this commitment)
TRACE: <ADR-NNN §Decision clause, test file:line, or "skill convention">
```

Lead the report with a count summary: `N blockers, M warnings, K dormant`. If zero findings, say so explicitly with the count.

The report names *what* drifted and *which ADR clause* it collides with; it does not perform fixes. Per `CLAUDE.md`'s ownership table, the fix is the implementer's lane (for code), the architect's (if the ADR itself should change — via a supersedure ADR, never a silent edit), or the test-writer's (if a test assertion is what forced the drift). The human gates which.

## Rules

### AF-1 — Route contract matches the ADR

For every HTTP route an Accepted ADR's *Decision* section specifies, the code implements that route with that method, that path, that status code, that redirect target (if any), and that request/response body shape — nothing substituted, nothing inserted.

Forbidden:
- extra redirect hops the ADR did not name (a `POST → 303 → GET → 303` chain where the ADR specified `POST → 303 → GET`);
- a substitute redirect mechanism — a `Refresh` header, a `Location`-less `303`, `<meta http-equiv="refresh">`, a JavaScript redirect — where the ADR named a specific one (a single `303` with a `Location`);
- a different status code, a different path, a different body shape.

If a *test* assertion appears to require a contract the ADR did not specify, that is an AF-1 finding **and** a `PUSHBACK:` candidate for the test-writer — it is not a license to deviate from the ADR. The mismatch between the test and the ADR is the bug to surface, not the gap to engineer across.

- Severity: **blocker** on mismatch; **dormant** if no cited ADR specifies a route contract for the diff's routes.

### AF-2 — Mechanism matches the ADR

Where an ADR's *Decision* section picks a specific mechanism — a concurrency/dispatch primitive ("FastAPI `BackgroundTasks`"), a storage library ("stdlib `sqlite3`, no ORM, no migration framework"), a redirect pattern ("PRG via `303`"), a parsing approach — the code uses *that* mechanism.

A different mechanism is a **blocker** even when it is wrapped to resemble the named one. Examples of the wrap-to-resemble anti-pattern:
- a `BackgroundTasks.add_task(...)` registration whose target spawns a `threading.Thread(daemon=True)` running its own event loop — that is *not* "using `BackgroundTasks`" in the ADR's sense; the work runs in a detached thread the ADR never contemplated;
- an `asyncio.create_task(...)` that an ADR explicitly *rejected*, reached via a sync wrapper so the call site "looks like" the approved path;
- raw `sqlite3` cursor work moved behind a thin function whose name implies the ADR's persistence-package API but whose body bypasses it.

Mechanisms an ADR explicitly *rejected* are forbidden outright — listing the rejected mechanism in a comment ("ADR-NNN rejected this, but…") does not unreject it.

- Severity: **blocker** on mismatch or on use of an ADR-rejected mechanism; **dormant** if no cited ADR pins a mechanism for the surface in question.

### AF-3 — No unbacked public surface

No HTTP route or endpoint, no module, no class, and no public function/method exists in the diff that is not named in (a) a cited ADR, (b) a test file for this task, or (c) pre-existing code. A new public surface is an architectural change; the architect owns it. **This rule needs no cited ADR — it always applies.**

NOT triggers: renames; parameter additions to existing callables; inline (private, non-exported, single-module) helpers introduced by a refactor; new private functions whose names start with `_` and that are not re-exported.

Triggers: a new route on the app; a new top-level module; a new class; a new function exported via `__all__` or imported across module boundaries; a new public method on an existing class that the cited ADRs/tests do not name.

- Severity: **blocker** for a new route, module, or class; **blocker** for a new exported/cross-module public function; **warn** for a borderline case (a module-private function that is nonetheless load-bearing across files, or a new public method whose absence/presence the tests are silent on).

### AF-4 — Named symbols exist as named

Function names, class names, module paths, parameter names, and state-machine state names that an Accepted ADR commits to **verbatim** are present **verbatim** in the code. Drift to catch:
- an ADR that says `generate_quiz_question(quiz_id)` against code that ships `dispatch_quiz_generation(quiz_id)`;
- an ADR naming states `requested → generating → ready → generation_failed` against code that uses `pending` / `done` / `error`;
- an ADR fixing a module path `app/workflows/quiz_generation.py` against code that puts it at `app/ai/quizgen.py`.

If the ADR's name is genuinely worse than the one the code wants, that is a supersedure-ADR conversation with the architect — not a silent rename in the implementation.

- Severity: **blocker** when the ADR is verbatim about the name/path; **warn** when the ADR describes the symbol but does not pin its exact spelling; **dormant** if no cited ADR names symbols for the diff.

### AF-5 — Test-shaped workaround smell

Code whose structure or comments exist to satisfy a *specific test assertion* rather than the feature is flagged for a second look. Tells:
- comments like "so httpx stops the chain at 303", "so the TestClient assertion passes", "to satisfy TASK-NNN's `…` check", "the test releases the event after the response is observed so we need …";
- branches that are dead in production and live only under the test harness;
- data shapes contorted to match an assertion (an extra field, a renamed key, a status string padded with text) with no product reason.

This is a `warn`, not a `blocker` — but it is a directed prompt to re-check AF-1 / AF-2 / AF-3 at that site, because a test-shaped workaround is the usual vehicle for an AF-1/AF-2/AF-3 violation. If the workaround turns out to be the only way to pass the test, the test is the bug: `PUSHBACK:` to the test-writer; the implementation does not absorb the contortion.

- Severity: **warn**, with a directed re-check of AF-1/AF-2/AF-3 at the flagged site.
