# ADR-015: Multi-chapter validation pass triages latent bugs as project_issues; does not fix them in-scope

**Status:** `Accepted`
**Date:** 2026-05-08
**Task:** TASK-005
**Accepted:** 2026-05-08 (human gate; accepted with a substantive amendment to the Decision — see "Bug-class partition" sub-section below. Rationale recorded in TASK-005 audit Run 004: TASK-005 is testing the Lecture body, not the rail or general page chrome. LaTeX/parser bugs surfaced during validation are not Chapter-specific — fixing one usually fixes most — so they are folded in-scope under their own ADR. Rail/general-CSS bugs are also not Chapter-specific, but a fix would affect every page; those are escalated to their own task/ADR rather than filed as a project_issue.)
**Resolves:** none (this ADR codifies the in-scope/out-of-scope discipline TASK-005 commits to; no prior issue covers it)
**Supersedes:** none

## Context

TASK-005 walks all 12 Chapters through `GET /lecture/{chapter_id}` for the first time. The single previously-validated Chapter (Chapter 1) surfaced three latent parser bugs across three TASKs (TASK-002 surfaced `\\` linebreak passthrough; TASK-003's screenshot review surfaced tabular column-spec passthrough and callout-title passthrough; TASK-004 fixed the latter two via ADR-011 and ADR-012). The prior is overwhelming that Chapters 2–13 contain additional latent bugs not yet seen, because they have never been rendered through the validation gate.

The task's framing forces a discipline question: when the validation pass surfaces N latent bugs, **does this task fix them all or file them and exit?** Three options materially differ:

- **(a) Fix-everything:** every bug surfaced becomes an in-scope fix in TASK-005. The task's scope inflates to "12 screenshots + N parser fixes + M template fixes." Closes more bugs per cycle.
- **(b) File-and-exit (triage discipline):** every bug surfaced becomes a new `design_docs/project_issues/<slug>.md` file with `Status: Open`; TASK-005 ships the validation pass and the catalog of issues. Each issue is then triaged into a focused follow-up task. Keeps TASK-005 small.
- **(c) Hybrid with a per-bug architect call:** each surfaced bug is evaluated case-by-case during `/design TASK-005` (or the implementer's run); some are folded in, some are filed. Adds decision overhead per bug.

ADR-014 (this same `/design` cycle) folds the **pre-existing** `\\` linebreak project_issue into TASK-005, because (a) the issue pre-exists this validation pass, (b) the validation pass would re-surface the same bug across all 12 titles regardless, and (c) the fix is bounded to one regex line. ADR-014's decision is *not* a precedent for "fold in everything new found during the validation pass" — it is a one-off resolution of a pre-existing issue, motivated by the same screenshot-cleanliness argument that motivates this ADR's discipline.

The task is also structured under one of the architect's standing memory constraints: tasks should be vertical slices, small enough for one session. A fix-everything posture inflates TASK-005 to an unbounded session — the count of latent bugs is unknown, the difficulty per bug is unknown, and any one of them could itself force a parser-architecture decision (e.g., a bug that surfaces a constraint pylatexenc cannot meet).

The manifest constrains this decision through §3 (drive consumption — the cataloged issues advance prioritization for follow-up tasks; deferring fixes is fine if it accelerates the human's prioritization signal) and through the implicit "one task is one session" working-rhythm rule that emerges from the task-shape discipline (small vertical slices, manifest-aligned, one decision unit at a time).

## Decision

The multi-chapter validation pass adopts **Option (b): file-and-exit triage discipline.**

Concretely:

- **Every distinct latent bug surfaced during TASK-005's validation pass — by the smoke layer, by the Playwright layer, or by the human's screenshot review — is classified by bug class** (see "Bug-class partition" below) and routed to one of: in-scope fix (with its own ADR if architectural), escalation to a focused follow-up task/ADR, or filing as a `design_docs/project_issues/<slug>.md` with `Status: Open` per the existing template.
- **TASK-005 ships when:** (a) all 12 Chapters return HTTP 200, (b) all 12 screenshots exist and have been reviewed, (c) every bug surfaced has been routed per the bug-class partition (fixed-in-scope, escalated to its own task/ADR, or filed as Open project_issue).
- **A bug that prevents a Chapter from returning HTTP 200 (parser crash, template-render exception) is a smoke-layer test failure**, which is a TASK-005 acceptance-criterion failure, which is a blocker for TASK-005. Such a failure is fixed in TASK-005 because the AC requires it. The triage discipline applies to bugs that produce HTTP 200 but render incorrectly (passthrough text, missing structure, mis-rendered callouts) — those route per the bug-class partition. A crash on a Chapter is a different class (see "What 'blocker for TASK-005' means").
- **The triage discipline applies to TASK-005 only.** Future tasks set their own in-scope/out-of-scope discipline. This ADR does not generalize to "every task triages rather than fixes" — each task makes its own scope call. The pattern this ADR codifies is *"a corpus-wide validation/triage pass routes found bugs by bug class,"* and that pattern is reusable for future corpus-wide passes (e.g., a future "validate every Note renders" pass).

### Bug-class partition (added at human gate, 2026-05-08)

The original draft of this ADR committed to pure file-and-exit with one exception (ADR-014's pre-existing `\\` linebreak fix). The human's gate-time amendment refines this to a bug-class partition. The architectural rationale is that Chapters 2–13 are editorially uniform: the `.tex` source structure across all 12 Chapters is near-identical, so a parser/LaTeX bug surfaced on one Chapter almost always applies to most or all of the others; conversely, the surrounding features around the Chapters (rail, page chrome, general CSS) are not customized per Chapter, so a defect there is by construction not Chapter-specific either, and a fix touches every Lecture page at once. These two cases are not the same shape and warrant different routing.

The four bug classes and their routing:

1. **LaTeX/parser content-fidelity bugs (in the Lecture body).** Examples: an unhandled environment, an inline macro the parser does not recognize, a callout shape no prior Chapter exercised, a passthrough of LaTeX source that should have been stripped or rendered. **Routing: fix in-scope of TASK-005.** If the fix is bounded (similar in shape to ADR-011 / ADR-012 / ADR-014 — a single parser handler change, no architectural shift), it is folded into TASK-005's `/implement` phase under a new Proposed ADR drafted in the same task. If the fix is unbounded (forces a parser-architecture decision, requires superseding an Accepted ADR, surfaces a question the architect must answer), it follows the smoke-layer-crash escalation path (`ESCALATION:` → focused `/design` cycle → resolution). Rationale: LaTeX bugs are not Chapter-specific; one fix usually clears the same defect across multiple Chapters, and folding the fix in keeps the validation screenshots clean for human review on the same pass.

2. **Smoke-layer crashes (a Chapter returning non-200 because the parser or template raised).** Routing unchanged from the original Decision: AC-1 forces fix-or-escalate. Bounded fix → in-task. Unbounded → `ESCALATION:`. See "What 'blocker for TASK-005' means" below.

3. **Rail / page-chrome / general-CSS bugs (defects in the navigation rail, page header/footer, base layout, designation palette, or any styling that is not Lecture-body content).** **Routing: escalate to a focused follow-up task with its own ADR; do NOT file as a project_issue and do NOT fix in TASK-005.** Rationale: these defects are by construction not Chapter-specific, a fix would affect every Lecture page (not just the one being validated), and the architectural ownership belongs to the rail/styling tasks (ADR-006, ADR-008) — not to a content-fidelity validation pass. A project_issue is the wrong vehicle because the fix is large enough to deserve its own task framing; a single triage entry would underspecify the work. The human's `/next` cycle picks up the escalation and proposes the focused task.

4. **Anything else (truly latent rendering anomalies that don't fit classes 1–3).** Routing unchanged: file as `design_docs/project_issues/<slug>.md` with `Status: Open`. The architect's `/next` cycle after TASK-005 closes picks them up.

The implementer's discipline at task-execution time is to classify before routing. If the class is genuinely ambiguous (e.g., a defect that could be parser-side or template-side), the implementer surfaces an `ESCALATION:` and the architect decides at gate. The classification is binary per-bug — no "obviously trivial" carve-outs within a class.

The new pre-existing in-task fix (formerly the single ADR-014 exception) becomes the first instance of a class-1 fold-in: ADR-014's `\\` linebreak strip is folded under bug class 1 (LaTeX/parser content-fidelity). Subsequent class-1 bugs surfaced during validation get their own Proposed ADRs alongside ADR-014, all gated together at `/review TASK-005`.

### What "distinct latent bug" means

A distinct latent bug is a class of rendering defect, not an instance per Chapter. If 5 Chapters all have callouts with a new bracketed-arg shape that the current parser does not handle, **one project_issue captures the class**, naming the affected Chapters in its Question/Constraints sections. This keeps the project_issue directory comprehensible and matches the existing pattern (the tabular-column-spec issue named Chapters 1, 5, 6, 7, 13 as affected without filing five issues).

If a single Chapter has a Chapter-specific defect (e.g., `ch-09-balanced-trees` uses an environment no other Chapter uses), one project_issue is filed for that defect, naming `ch-09` specifically.

The architect's call at gate time, surfaced by the human's review, settles ambiguous "is this one bug or two" cases. The default heuristic: same root cause = same issue.

### What "blocker for TASK-005" means

The smoke layer (per ADR-013) asserts HTTP 200 + structural sanity (M/O badge, at least one Section anchor) on every Chapter. If a Chapter fails this layer, TASK-005's AC-1 ("every request returns HTTP 200") is unmet and the task cannot ship.

The implementer's response when the smoke layer fails:

1. **Diagnose the crash.** Read the parser traceback or template-render exception.
2. **If the fix is bounded** (similar in shape to ADR-011 / ADR-012 — a single parser handler, single environment, no architecture shift): fix it in-task. Add a regression test. Move on.
3. **If the fix is unbounded** (forces a parser-architecture decision, requires superseding an Accepted ADR, or surfaces a question the architect must answer): escalate via the task's `ESCALATION:` channel. The architect runs a focused `/design` cycle to resolve the architectural question. TASK-005 either (a) waits for that resolution and proceeds, or (b) is re-scoped to ship without the failing Chapter (with that Chapter's failure documented in the audit and a project_issue filed) — the architect picks at escalation time.

This boundary keeps TASK-005 small while honoring AC-1's "no Chapter crashes" requirement. It does NOT mean "every parser bug is unbounded" — bounded parser bugs (the ADR-011 / ADR-012 shape) are absorbed; the test author's discipline keeps the fix focused.

### What this ADR does *not* decide

- **The exact slug naming for new project_issue files.** Existing convention is descriptive kebab-case (`latex-tabular-column-spec-passthrough.md`); the architect or human picks per-issue.
- **Which follow-up tasks tackle which issues first.** That is the architect's `/next` call after TASK-005 closes.
- **Whether bugs can be fixed *between* TASK-005's `/design` and `/implement` phases.** No — the discipline applies through the entire task lifecycle. If the implementer encounters a bug, files it, and notices the fix is one regex line, the answer is still "file the issue, do not fix here." The single exception remains the `\\` linebreak fix codified by ADR-014.
- **A bound on how many project_issues TASK-005 may file.** The task closes when the validation pass is complete; the issue count is a side effect.

## Alternatives considered

**A. Fix-everything (Option (a) above).**
Rejected. TASK-005's scope explodes to "12 screenshots + N fixes + M test additions" with N unbounded. Each fix is itself a candidate for its own ADR (per the ADR-011/ADR-012 shape). A task that takes multiple sessions to ship is the wrong shape for the project's working rhythm. The fix-everything posture also delays the human's prioritization signal: the project would not see the catalog of issues until every one is fixed, and the human cannot redirect effort mid-stream.

**B. Hybrid with per-bug architect call (Option (c) above).**
Rejected. Adds decision overhead at every bug ("is this in-scope or out-of-scope this time?") that is not justified by the bounded fix-everything alternative. The triage discipline is binary by design: validation passes catalog, focused tasks fix. The single in-task exception (ADR-014) is well-scoped and motivated; broadening exceptions case-by-case dilutes the discipline.

**C. File-and-exit but allow the implementer to fold in any fix that is "obviously trivial."**
Rejected. "Obviously trivial" is a slippery-slope predicate that erodes the binary discipline. The implementer's discipline rule must be black-and-white at task-execution time: either fix or file, not "judge per case." Black-and-white rules are the right tool for the kind of triage pass TASK-005 is.

**D. Fix bugs found in Chapters 2–6 (Mandatory) and file bugs found in Chapters 7–13 (Optional).**
Rejected. The Mandatory/Optional split is a manifest invariant about content, not about implementation priority. Skewing in-task fixes toward Mandatory contradicts the task's framing as a *triage pass* and reintroduces the unbounded-scope problem for Mandatory while leaving Optional undertested. The cleaner framing is: triage everything; prioritize the resulting follow-up tasks however the architect/human chooses next cycle.

**E. Defer the entire question to the implementer (let `/implement TASK-005` decide per bug).**
Rejected. The discipline must be set at `/design` time so the implementer has a clear rule. Letting the implementer decide per bug introduces ambiguity at the wrong layer.

## My recommendation vs the user's apparent preference

**Aligned with the task's stated recommendation.** TASK-005's "Architectural decisions expected" section explicitly recommends "new latent bugs are filed as project_issues, not folded in." TASK-005's "Architectural concerns I want to raise" section reinforces: "this task is a triage pass, NOT a fix-everything-found pass. New latent bugs surfaced during the validation pass are filed as project_issues, not folded into this task. The single exception is the existing `\\` linebreak project_issue."

The architect agrees on the merits. This ADR codifies that recommendation as architectural commitment so the implementer (and any future similar pass) has a binding reference rather than relying on the task file alone.

The architect's only mild push: **the smoke-layer crash exception is real and should be explicit.** The task framing implies "every bug filed, none fixed," but a Chapter that returns 500 because the parser crashes does not produce a screenshot for the human to triage and does not produce a 200 response for the smoke layer to pass. The task AC-1 forces such crashes to be fixed (or the failing Chapter excluded from the validation set with the failure documented). This ADR makes the crash-fix exception explicit so the implementer is not stuck choosing between "ignore the AC" and "violate the discipline." See "What 'blocker for TASK-005' means" above.

## Consequences

**Becomes possible:**

- TASK-005 ships within one session. The task scope is bounded by the harness work (one HTTP test file + one Playwright test file), the one in-task fix codified by ADR-014, and the screenshot review. Bug count does not affect task duration.
- The human gets a catalog of every latent rendering defect in the corpus in one delivery. Prioritization signal arrives early. Follow-up tasks can be sequenced by impact.
- Future corpus-wide validation passes (e.g., "validate every Note renders," "validate every Quiz template renders") inherit the triage pattern by reference rather than re-deriving it.
- The architect's `/next` cycle after TASK-005 has concrete inputs (the catalog) for selecting the next focused fix task — exactly the pattern TASK-004 used (one task = one or two related parser fixes with their own ADRs).

**Becomes more expensive:**

- The corpus may carry visible rendering defects between TASK-005's close and the follow-up tasks that fix them. The screenshots will show the bugs; the human will know about them; consumption may be partially degraded. Acceptable cost: triage-without-fix is the trade for fast prioritization signal, and the bugs were already in the corpus before TASK-005 — TASK-005 makes them visible, not new.
- The project_issue directory grows. Existing convention handles this (one file per issue, descriptive slug); if the directory grows past ~10 active issues, the architect can introduce an index then per CLAUDE.md's standing rule.

**Becomes impossible (under this ADR, as amended at human gate):**

- A version of TASK-005 that fixes a rail / page-chrome / general-CSS defect in-scope. Class-3 bugs route to a focused follow-up task with its own ADR; the implementer does not absorb them.
- A version of TASK-005 that files a class-1 LaTeX/parser content-fidelity bug as a project_issue and exits. Class-1 bugs route to in-scope fix (with a new Proposed ADR if architectural). The amendment makes class-1 fold-in the rule, not the exception.
- A "we'll just slip this one in" deviation by the implementer that crosses bug-class boundaries. The bug-class partition is binary per bug; ambiguous classifications surface as `ESCALATION:` rather than as silent reclassifications.

**Supersedure path if this proves wrong:**

- If the file-and-exit posture leaves the project with too many open project_issues that the human cannot prioritize, supersede with a hybrid ADR that defines a "fix-bound" (e.g., "fix any bug that requires fewer than M lines of parser change in-task; file the rest"). The supersedure reintroduces the per-bug judgment but with a quantified bound rather than a slippery predicate.
- If a future corpus-wide pass surfaces zero latent bugs (rendering is mature), the discipline is moot and a future ADR can drop it. Until then, mature-rendering is the goal, not the assumption.
- If the project ever onboards a second author / second user (manifest §5 currently forbids this; if it changes, that is a manifest edit), the file-and-exit pattern likely still applies but the issue-handoff workflow gains an owner-assignment dimension this ADR does not anticipate.

## Manifest reading

Read as binding for this decision:

- **§3 Primary Objective ("drive consumption … via per-Chapter Lectures and Notes").** Bound the requirement that the task close in one session and the prioritization signal reach the human early. A fix-everything posture delays both.
- **§5 Non-Goals: "No remote deployment / hosted product."** Honored — the triage pattern is a local-development discipline; nothing about the issue-catalog implies any remote workflow.
- **§6 Behaviors and Absolutes.** Not directly touched; the triage discipline is process, not product behavior.
- **§7 Invariants.** Not directly touched.

No manifest entries flagged as architecture-in-disguise.

The architect notes: this ADR sits at the boundary between architecture and process. Its substance — "validation passes triage; focused tasks fix" — is a workflow rule. Per CLAUDE.md's tier table, workflow rules belong in `.claude/skills/*/SKILL.md` (Tier 2, human-owned) when they are project-wide guardrails, and in ADRs when they are decisions specific to a task or a class of task. This ADR captures the rule as an *architectural decision specific to TASK-005's class of task* (corpus-wide triage passes). If the human reads it as a project-wide rule and wants it lifted to a skill, that is a follow-up move; ADR-015 does not preclude it. The architect's reading is "task-class decision," not "project-wide rule."

## Conformance check

- **MC-1..MC-10.** Not directly touched. The triage discipline is workflow; no manifest invariant is implicated.

UI-skill rules (`ui-task-scope`):
- Not implicated. The discipline applies to bug-handling within a UI task, not to the UI surface itself.

Authority-state rules:
- **AS-1..AS-7.** Honored. ADR-015 is `Proposed`. Project_issues filed under this discipline carry `Status: Open` consistent with AS-5; their resolution will be `Resolved by ADR-NNN` where ADR-NNN is the focused follow-up's ADR.

No previously-dormant rule is activated by this ADR.
