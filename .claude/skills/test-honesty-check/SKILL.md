---
name: test-honesty-check
description: Catches specific test-honesty failure modes — assertions that pass without exercising the property under test, fixtures that don't actually create the divergence the test claims to verify, mocks that mask the unit under test, and test assertions not backed by an Acceptance Criterion or Accepted ADR. Use after the test-writer finishes a run, during `/review`, or when verifying that a green test suite actually proves the feature works. Reports findings only; does not rewrite tests.
---

# Test honesty check

A test is **honest** if its pass/fail signal correlates with the implementation actually doing the right thing. A test is **dishonest** if it can pass while the implementation is broken or absent. This skill detects common dishonesty patterns at narrow, agent-triggered boundaries (post-test-write, pre-gate, review).

**Scope distinction:** this skill is narrow and project-scoped. If a broader unit-test evaluation skill exists in the environment, it remains user-triggered and separate. `test-honesty-check` is the fast precondition gate that fires automatically during `/implement` and `/review`.

**Authority of this skill:** operational instruction (Tier 2). It does not introduce architectural claims and does not decide *what* a test must assert; it only verifies that the assertions a test makes are not vacuous, are backed by authority (an AC or an Accepted ADR), and that fixtures actually create the conditions the test claims to exercise.

## When to invoke

- **Test-writer at end of `/implement` Phase 1:** before returning to the orchestrator. Walk the newly-created test files for the patterns below.
- **Orchestrator before pre-gating new tests to the human:** if any rule fires `blocker`, surface to the human; do not present the tests as ready-to-accept until addressed.
- **Reviewer during `/review` (Phase 4):** as part of the test-honesty walk on staged test files (new and modified).
- **At human request:** "are these tests honest?", "do these tests actually verify the feature?", "check test honesty before commit".

## Output format

Walk the rules below against the staged or working-tree test files in scope. Produce a structured findings report:

```
RULE: <id>
WHERE: <test_file:line(s)>
EVIDENCE: <quoted excerpt or finding>
SEVERITY: blocker | warn | dormant
TRACE: <skill convention or specific cited authority>
```

Lead the report with a count summary: `N blockers, M warnings, K dormant`. If zero findings, say so explicitly.

The report names *what* is dishonest and *why* the test could pass on a broken implementation; it does not rewrite tests. Test fixes are the test-writer's lane; the human gates whether the fix happens before commit.

## Rules

### TH-1 — Assertions on tokens unconditionally present

A substring assertion (`assert "X" in response.text`, `assert "X" in html`, `assert "X" in body`) is dishonest if `"X"` is unconditionally present in any reasonable response. Common offenders for HTML responses include `"title"`, `"head"`, `"body"`, `"html"`, `"meta"`, `"link"`, `"script"`, `"<"`, `">"`, `"/"`, `"!"`, single ASCII punctuation, and short CSS-class fragments that recur across the project's templates.

**Detection (minimum viable):**
- For each `assert "<token>" in <response_or_html>` pattern in a new or modified test, extract `<token>`.
- If `<token>` is shorter than 3 characters, or is a known HTML/CSS structural keyword, or appears in every fixture-rendered response without being feature-specific, flag.
- If the assertion is **negative** (`assert "<token>" not in <html>`), apply the same check and additionally check whether the rail/header/page-level template *legitimately* contains `<token>`. The TASK-002 case where `assert "Optional" not in html` fired against a Lecture page that legitimately rendered "Optional" in the rail is the canonical example.

**Action:** the test should narrow its scope (assert against a specific element, e.g., a regex-extracted `<header class="lecture-header">` block), or assert against a more specific token that only appears when the property under test holds.

- **Severity:** **blocker** when the asserted token is unconditionally present in any response from any fixture; **warn** when the token is present in a substantial subset of fixtures.
- **Trace:** skill convention; reinforced by the TASK-002 cycle's `test_ac3_mandatory_not_optional` and `test_ac_missing_title_does_not_fabricate` failures.

### TH-2 — Fixtures don't exercise the divergence the test claims

A test that claims to verify "A differs from B" must use fixtures where A and B actually differ. Common pattern: a test claims to verify "ordering is numeric, not lexical" but its fixture set doesn't contain a case where numeric and lexical orderings produce different results.

**Detection (signal-based):**
- If the test docstring or comments contain phrases like *"ASSUMPTION:"*, *"fixture doesn't actually exercise"*, *"happens to coincide with"*, *"would also pass under the wrong implementation"*, the test-writer has self-flagged. Treat as a definite finding.
- If the test name claims "X-vs-Y" semantics and the fixture file does not contain an example pair where X and Y diverge, flag. (Detection here is heuristic; a careful reader of the test + fixture is the floor.)

**Action:** strengthen the fixture so the divergence is exercised, or rename the test to reflect what it actually verifies.

- **Severity:** **blocker** when the test name or docstring promises a divergence the fixture cannot produce; **warn** when the test-writer has self-flagged but the AC is still partially satisfied.
- **Trace:** skill convention; reinforced by the TASK-002 cycle's `test_ac_order_1_numeric_vs_lexical_ordering` admission.

### TH-3 — Mocks mask the unit under test

A test mocks something it is supposed to verify. Common examples: a test of `render_chapter()` that mocks `render_chapter`; a test of "discovery rejects bad names" that mocks the discovery function; a test of "the route returns 200 for valid IDs" that mocks the route handler.

**Detection (minimum viable):**
- For each `mock`, `patch`, or `monkeypatch` in a new or modified test, identify the target.
- Cross-reference the target with the test's stated intent (test name, docstring, or AC trace).
- If the target IS the unit under test (or a function whose behavior the test claims to verify), flag.

**Action:** unmock the unit under test; mock only the boundaries (filesystem, external services, time, randomness).

- **Severity:** **blocker**.
- **Trace:** skill convention; reinforced by the broader testing principle that mocks belong at boundaries, not at the unit under test.

### TH-4 — Test assertions must trace to an AC or Accepted ADR

Every test assertion enforces a contract. Contracts must be backed by authority — either an Acceptance Criterion in the active task file or an Accepted ADR. A test that enforces an assumption neither in the task ACs nor in any Accepted ADR has elevated test-writer judgment to authority status without a gate.

**Detection (signal-based):**
- For each new test, walk its **nearest** `Trace:` line: test docstring first, then class docstring, then module-level trace block. The first one found applies.
- Verify the cited AC or ADR exists and contains the asserted contract.
- If no `Trace:` line is reachable from the test, the class, or the module, flag it.
- If a test asserts behavior X but the nearest `Trace:` cites an AC or ADR that does not require X, flag it.
- The TASK-002 cycle's two test-writer assumptions (Mandatory-before-Optional ordering and `app.config.CONTENT_ROOT` test seam) are the canonical examples — both became test-only contracts without ADR backing.

**Action:** either find the AC/ADR that backs the assertion (and add it to `Trace:`), or escalate to the architect to add an ADR amendment / task-AC update *before* the test is gated. Silently shipping a test with no authority backing is the failure this rule prevents.

- **Severity:** **blocker** when an assertion has no traceable AC or ADR backing; **warn** when the trace exists but is weak (cites a manifest invariant rather than a specific AC/ADR).
- **Trace:** `CLAUDE.md` markdown-authority rule + this skill's operational rule against test-only contracts.

### TH-5 — Tests pass on partial implementation

A green test suite that does not exercise the feature is not evidence the feature works. The TASK-002 cycle shipped a passing 158-test suite while the rail had no CSS rules; every test asserted against HTML structure (class names present, response 200, hrefs computed) but no test asserted against rendered visual behavior. The implementation was half-done; the suite did not catch it.

**Detection (heuristic):**
- For the kinds of features the task introduces, identify the depth of property the suite verifies.
- For UI surfaces: if the suite's tests all assert against `TestClient` HTML strings and none test rendered behavior, the suite is shallow against the feature. (See `ui-task-scope` rule UI-4 for the gate forcing rendered-behavior tests for UI tasks.)
- For data-pipeline surfaces: if the suite verifies happy paths only and no test exercises the documented error cases, flag.
- For surfaces with multiple specified failure modes (per the task ACs or ADRs): each named failure mode should have at least one corresponding test.

**Action:** add tests that exercise the depth the feature requires; do not declare green-equals-done on a shallow suite.

- **Severity:** **warn** by default; **blocker** when the task explicitly names a failure mode and no test exercises it.
- **Trace:** skill convention; reinforced by `ui-task-scope` (UI-4) for UI tasks.

## Notes

- The skill does not name a specific testing framework, mocking pattern, or coverage threshold. Those decisions are architectural and live in ADRs; the skill catches dishonesty *given* whatever framework the project uses.
- TH-2 and TH-5 are the hardest to automate fully; they rely on a careful reader cross-referencing test intent with fixture content and feature scope. Run them as a pass even if the heuristic detection is incomplete — a human or agent with context is the floor.
- TH-4's `Trace:` convention assumes the project's tests cite their backing in docstrings (TASK-001 established this pattern). If a project does not follow this convention, the skill cannot enforce TH-4 mechanically; the architect should adopt a `Trace:` convention or flag the gap.
- This skill complements `ui-task-scope` (UI-specific test obligations) and any broader unit-test evaluation skill that may exist in the environment. When a finding spans multiple skills (e.g., a UI task whose tests are also dishonest), each skill reports its rule independently; the most severe wins.
