# ADR-005: Chapter source file naming — single canonical form `ch-{NN}-{slug}` (Form A only)

**Status:** `Accepted`
**Date:** 2026-05-08
**Task:** TASK-002
**Resolves:** `design_docs/project_issues/multi-chapter-source-naming.md` and the TASK-001 Run 005 ESCALATION against ADR-002 (silent on `ch01-foo` form).

## Context

ADR-002 fixed the rule "Chapter ID = file basename without extension" but did not commit to which basename form is valid. The corpus on disk today contains two distinct conventions:

- `ch-01-cpp-refresher.tex` (lowercase `ch`, hyphen, zero-padded number, hyphen, kebab slug). One file uses this form.
- `ch2.tex`, `ch3.tex`, `ch4.tex`, `ch5.tex`, `ch6.tex`, `ch7.tex`, `ch9.tex`, `ch10.tex`, `ch11.tex`, `ch12.tex`, `ch13.tex` (lowercase `ch`, unpadded number, no slug, no hyphen). Eleven files use this form. `ch8.tex` is absent.

`design_docs/project_issues/multi-chapter-source-naming.md` (Open since 2026-05-07) raised this issue and named two main routes (standardize-and-rename vs tolerate-both-conventions) plus one transitional variant. Its "Decide when:" condition fires for TASK-002 because the navigation surface enumerates Chapters across the whole corpus.

A second, related question is on record from TASK-001 Run 005: the test-writer ESCALATION that ADR-002 is silent on the `ch01-foo` form (lowercase `ch`, padded digits, hyphen, slug — no leading hyphen between `ch` and the digits, and no slug-after-hyphen separator before the digits). The test-writer pinned strict rejection of `ch01-foo` in tests and asked the architect to either ratify or override that strictness in an ADR. Both questions concern the canonical form of Chapter file basenames; this ADR resolves them together rather than punting one of them again.

Persistence does not exist yet, so no Quiz Attempt, Note, or completion-mark row currently foreign-keys on a Chapter ID. **This is the cheapest moment to commit to a naming rule:** every option below is reachable without a data migration. Once persistence lands, a rename becomes a foreign-key migration (manifest §7 requires Quiz Attempts, Notes, and completion marks to persist across sessions).

The manifest's relevant clauses are §5 ("Lecture source is edited outside the application") — any rename is a content-management commit the human performs, never an application action — and §6 ("A Lecture has a single source") — no parallel-source state may exist mid-migration.

## Precondition: content-management rename (human-performed, outside this ADR)

This ADR cannot be honored by the codebase until the eleven Form-B files in `content/latex/` are renamed to Form A. The application performs no rename (ADR-001, MC-6); the human performs the rename as a separate content-management commit, outside the application, **prior to `/implement TASK-002`**.

The exact renames required, given today's filesystem state (`ls content/latex/`):

| Current basename | New basename (Form A) |
|---|---|
| `ch2.tex` | `ch-02-<slug>.tex` |
| `ch3.tex` | `ch-03-<slug>.tex` |
| `ch4.tex` | `ch-04-<slug>.tex` |
| `ch5.tex` | `ch-05-<slug>.tex` |
| `ch6.tex` | `ch-06-<slug>.tex` |
| `ch7.tex` | `ch-07-<slug>.tex` |
| `ch9.tex` | `ch-09-<slug>.tex` |
| `ch10.tex` | `ch-10-<slug>.tex` |
| `ch11.tex` | `ch-11-<slug>.tex` |
| `ch12.tex` | `ch-12-<slug>.tex` |
| `ch13.tex` | `ch-13-<slug>.tex` |

`ch-01-cpp-refresher.tex` already matches Form A and is unchanged. `ch8.tex` is absent on disk and produces no row.

The `<slug>` for each file is the human's editorial choice — kebab-case lowercase ASCII, derived from the chapter's `\title{...}` content (e.g., `ch-07-heaps-and-priority-queues.tex` for the chapter the human currently titles "Heaps and Priority Queues"). The slug does not need to mirror the title verbatim; it should be short, descriptive, and stable. Once chosen, it becomes the Chapter ID and the URL slug.

This rename list is **documentation only**. No agent performs the rename. The architect agent did not edit any file under `content/latex/` to produce this ADR.

## Decision

### One canonical form

A Chapter file basename (and therefore a Chapter ID) is valid if and only if it matches this regular expression:

- **Form A — kebab+slug:** `^ch-(\d{2})-[a-z0-9][a-z0-9-]*$`
  - `\d{2}` is exactly two digits, zero-padded. Single-digit numbers MUST be written as `01`…`09`. Three-or-more digit numbers (Chapter 100+) are not contemplated by today's corpus and would require a future ADR to widen the regex; for now, exactly two digits is the rule.
  - The slug after the second hyphen is kebab-case lowercase ASCII: `[a-z0-9][a-z0-9-]*`. The slug must start with a letter or digit (no leading hyphen) and contain only lowercase ASCII letters, digits, and hyphens thereafter. Empty slug is rejected.
  - Examples (valid): `ch-01-cpp-refresher`, `ch-02-arrays`, `ch-07-heaps-and-priority-queues`, `ch-13-graphs-advanced`.

Any basename matching neither form is rejected by `parse_chapter_number()` (ADR-004) with a structured `ValueError`. In particular, the following forms are **rejected**:

- `ch1`, `ch2`, …, `ch13` (Form B — compact, no slug). These are the legacy basenames the human renames as a precondition above.
- `ch01-foo` (no leading hyphen between `ch` and digits, but a hyphen+slug after) — closes the TASK-001 Run 005 ESCALATION explicitly.
- `Ch-01-foo`, `CH-01-foo` (uppercase `Ch`/`CH`).
- `ch-1-foo`, `ch-7-foo` (single-digit, not zero-padded).
- `ch-001-foo`, `ch-0001-foo` (more than two digits).
- `ch-00-foo` (chapter 0, outside manifest §8 range — also rejected by the `chapter_number >= 1` check in `parse_chapter_number()`).
- `ch-01-`, `ch-01--foo`, `ch-01-FOO` (empty slug, leading-hyphen slug, uppercase slug).
- `ch--01-foo`, `ch-` (empty digits, double leading hyphen).
- Any chapter number that resolves to ≤ 0 (manifest §8 starts at Chapter 1).

The application code `app/designation.py` currently implements **two** patterns (`_PATTERN_A` and `_PATTERN_B`); under this ADR, `_PATTERN_B` is removed and `_PATTERN_A` is tightened to require exactly two digits. That code change lands in `/implement TASK-002`.

### Why one form (Form A only)

The author has signaled directly that the project standardizes on Form A. The corpus is small (twelve files, one already in Form A), the rename is a one-shot content-management commit, and a single-form parser is materially simpler than a dual-form parser:

- Discovery code uses one regex, not two.
- The conformance skill (or a future MC rule) can grep for any code that introduces a second pattern with a single literal check.
- URLs are uniform (`/lecture/ch-NN-slug`); no permanent `/lecture/ch2` next to `/lecture/ch-01-cpp-refresher` inconsistency.
- Editorial slugs are mandatory, which preserves the topical metadata the author has in `\title{...}` and surfaces it in URLs as well.

The cost — eleven renames the human performs once — is bounded and paid before persistence makes Chapter IDs foreign keys. This is the cheapest moment to standardize.

### Migration of existing files is out of scope for this ADR

This ADR documents **what** the renames are; it does **not** perform them. The application does not write to `content/latex/` (ADR-001, MC-6). The rename is a human-owned content-management commit performed before `/implement TASK-002` runs. If the rename has not been performed by the time discovery runs, the eleven Form-B files will be rejected by `parse_chapter_number()` with structured `ValueError`s, surfaced as discovery WARNINGs (per ADR-007), and not appear in the navigation rail — fail loudly, never fabricated.

### Scope of this ADR

This ADR fixes only:

1. The single valid Chapter file basename form (Form A) and the regex that defines it.
2. The list of files the human must rename as a precondition.
3. Closure of the TASK-001 Run 005 ESCALATION on the `ch01-foo` form (rejected).

This ADR does **not** decide:

- Where Chapter discovery lives (ADR-007).
- The order Chapters appear in the navigation (ADR-007).
- The display label for each Chapter row (ADR-007).
- The route taxonomy of the navigation surface (ADR-006).
- The exact slug each Form-B file gets (the human's editorial choice).

## Alternatives considered

**A. Standardize on Form A everywhere (rename `ch{N}.tex` → `ch-{NN}-{slug}.tex`).** **CHOSEN.** The human has signaled directly. Costs: requires the human to (i) choose a slug for each of 11 files; (ii) perform 11 renames in a single content-management commit; (iii) update any external bookmarks, notes, or scratch files that reference the old basenames. Benefit: uniform URLs, uniform Chapter IDs, single-pattern parser, no permanent inconsistency cost. The rename is a one-shot human action that is cheap because no Chapter ID is yet a foreign key.

**B. Standardize on Form B everywhere (rename `ch-01-cpp-refresher.tex` → `ch1.tex`).**
Rejected. One rename, but lossy: the descriptive slug `cpp-refresher` is human-meaningful metadata in the filename and the URL. Manifest §3 (consumption / discoverability) is better served by URLs that carry topic information. Form B uniformity would also discourage future Chapter authors from including descriptive slugs, which is a small but real degradation.

**C. Tolerate both forms (Form A and Form B both valid); recommend Form A for new files.**
Rejected per human direction. The architect's prior recommendation in this ADR (before the human override) was tolerate-both for migration-cost reasons: tolerate-both was reversible, required no rename, and was already implemented as fact in `app/designation.py`. The human override prevails for two defensible reasons: (i) the corpus is small and the rename is a one-shot commit the human can perform now; (ii) a single-form parser is materially simpler going forward (one regex, uniform URLs, no per-form branching in discovery code or tests). The "permanent URL inconsistency" cost the architect's prior recommendation accepted is now eliminated. This rejected alternative is recorded for future supersedure context: if the project ever needs to re-introduce a second form (e.g., a third source layout under a future ADR-001 supersedure), the historical reasoning for tolerate-both is preserved here.

**D. Tolerate both forms with a deprecation schedule (accept both today, schedule renaming for a later task).**
Rejected. A deprecation schedule is a tolerate-both decision in disguise — it pays the dual-form parser cost up front and the rename cost later, where the human's preference is to pay the rename cost up front (now, while the corpus is small and persistence does not yet exist) and skip the dual-form parser entirely.

**E. Resolve `ch01-foo` by accepting it as a third valid form.**
Rejected. The TASK-001 Run 005 ESCALATION raised this for explicit decision. Accepting it would (i) introduce a second regex with no corpus member to motivate it; (ii) make the parser ambiguous on near-by typos (is `ch01foo` the same chapter? the same as `ch01-foo`? the same as `ch1-foo` once leading zeros strip?). Strict rejection keeps the parser unambiguous and pins the test-writer's strict contract as architecture.

## My recommendation vs the user's apparent preference

The architect's prior recommendation in this ADR was **tolerate-both** (alternative C) for migration-cost reasons: at the time, the user had not signaled a preference and the cheapest path was the one already implemented in code. The human has now signaled directly — *"update adr-005 we're going with form A kebab+slug"* — and overridden that recommendation in favor of **Form A only** (alternative A).

The architect accepts the override and considers it defensible without further argument:

- The corpus is currently twelve files, only one of which is already in Form A. The eleven renames are a one-shot human-performed content-management commit; they do not compound.
- A single-form parser is materially simpler than a dual-form parser: one regex, no branching in discovery, no per-form logic in tests, uniform URLs.
- No persistence currently references Chapter IDs as foreign keys. The rename is paid at the cheapest moment per manifest §7's persistence-and-migration logic.
- The override is reversible by a future supersedure ADR if the cost-benefit ever shifts (e.g., if a corpus the human does not control needs to be ingested later); supersedure is the correct tool for that.

The architect does not argue against an override the human has already made. The override prevails.

No `MANIFEST TENSION:` raised. No `ARCHITECTURE LEAK:` raised by this ADR.

## Manifest reading

Read as binding for this decision:
- §5 Non-Goals: "Lecture source is edited outside the application." Bound the rule that this ADR does not, itself, perform any rename — file naming changes are outside-the-application content-management actions the human performs.
- §6 Behaviors and Absolutes: "A Lecture has a single source." Bound the rule that mid-rename parallel-source states are forbidden; the rename precondition is a single-step rename per file, not a "both files exist" intermediate state.
- §7 Invariants: "Every Quiz Attempt, Note, and completion mark persists across sessions." Bound the timing argument: standardizing now is cheap because no foreign-key migration is needed; standardizing later (post-persistence) is expensive. This ADR exploits the cheap window by committing to a single form before persistence lands.
- §8 Glossary: "Mandatory — Currently Chapters 1–6"; "Optional — Currently Chapter 7 onward." Bound the chapter-number ≥ 1 constraint enforced by `parse_chapter_number()`.

No manifest entries flagged as architecture-in-disguise.

## Conformance check

- **MC-3 (Mandatory/Optional designation respects the canonical mapping).** This ADR does not encode any chapter-number threshold. The threshold remains in `app/designation.py`'s `chapter_designation()` function (ADR-004). The regex pattern in `app/designation.py` is now backed by an Accepted ADR (this one), and the implementer's `/implement TASK-002` work will reduce two patterns to one. MC-3 architecture-portion compliance is unchanged.
- **MC-6 (Lecture source is read-only to the application).** Honored. This ADR forbids any application-side rename of files in `content/latex/`. The rename precondition is a human-performed content-management commit, outside the application code path. No application code writes to `content/latex/`.
- **MC-7 (Single user).** Not touched.
- No other MC rules are affected.

Previously-dormant rule activated by this ADR: none new. (MC-3 and MC-6 were activated by ADR-004 and ADR-001 respectively.)

## Consequences

**Becomes possible:**
- The Chapter discovery code (ADR-007) enumerates `*.tex` files under `content/latex/` and validates each basename against exactly one regex, with a single rejection path for everything else. Discovery is materially simpler than under a tolerate-both rule: no per-form branching, no two-pattern union.
- URLs are uniform: every Chapter is reachable at `/lecture/ch-NN-slug`. No `/lecture/ch2` next to `/lecture/ch-01-cpp-refresher` inconsistency.
- The conformance skill (or a future MC rule) can grep for any code that introduces a second pattern with a single literal check.
- The TASK-001 Run 005 ESCALATION is closed; tests already pinning `ch01-foo` as rejected are now backed by an Accepted ADR.
- The naming-issue file is closed. Future questions about Chapter ID form become supersedure questions for this ADR.

**Becomes more expensive:**
- The eleven Form-B files in `content/latex/` must be renamed to Form A by the human as a content-management commit *before* `/implement TASK-002` runs. The human chooses a kebab-case slug for each. Mitigation: this is a one-shot cost paid once, against a small corpus, at the cheapest moment (no foreign keys yet). The rename list is documented in this ADR for the human's reference.
- External bookmarks, notes, or scratch references to `ch2.tex` … `ch13.tex` (if any) become stale after the rename. Mitigation: this is a single-user project; the human controls all such references.
- `app/designation.py`'s `_PATTERN_B` and the dual-pattern branch in `parse_chapter_number()` must be removed during `/implement TASK-002`, and the existing tests for Form-B IDs must be updated. Mitigation: the implementer agent and test-writer agent handle this; the architect's job is to document the rule.

**Becomes impossible (under this ADR):**
- Application code that silently accepts a second pattern (e.g., `ch2`, `ch01-foo`, `Chapter1`, `01-cpp-refresher`). Parser must reject these with a structured error.
- Application code that writes to `content/latex/` to rename a file. (Already forbidden by ADR-001 / MC-6; this ADR ratifies that the *naming question* does not motivate breaking the read-only rule.)

**Future surfaces this ADR pre-positions:**
- A future ADR introducing a third Chapter source layout (e.g., per-Section files, ADR-001 alternative B revisited) will need to supersede this ADR.
- A future ADR widening the digit count (Chapters 100+) is straightforward: relax `\d{2}` to `\d{2,}` and supersede.
