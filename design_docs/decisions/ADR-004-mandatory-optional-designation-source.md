# ADR-004: Mandatory/Optional designation source — manifest-derived rule, encoded in a single Python module

**Status:** `Accepted`
**Date:** 2026-05-07
**Task:** TASK-001
**Resolves:** none (no project_issues filed against this question)

## Context

TASK-001 acceptance criterion 3 requires that the rendered Chapter 1 page label the Chapter as Mandatory, "visible and not buried." Manifest §6 fixes that "Mandatory and Optional content are honored everywhere," and §7 fixes that "Mandatory and Optional are separable in every learner-facing surface." Manifest §8 fixes the canonical Chapter mapping: **Chapters 1–6 are Mandatory, Chapter 7 onward is Optional.** Manifest-conformance rule MC-3 grounds out on whatever ADR names the data source for that mapping; the rule is currently dormant for the architecture portion.

The decision here is narrow but real: **where in the codebase does the Chapter ID → Mandatory|Optional rule live, and how does the renderer read it?** Multiple materially different alternatives exist (front-matter in the source files, a sidecar config file, a code constant, derive from chapter number at parse time). Each has different costs and different fragility properties.

This ADR has to commit to a *single* canonical source so that future tasks (the Mandatory-only filter view; the multi-Chapter index; per-Chapter Quiz dashboards) all read from the same place. Without this commitment, MC-3 cannot become evaluable and the invariant becomes per-surface convention rather than enforceable rule.

## Decision

### The mapping

The mapping from Chapter ID to Mandatory|Optional is encoded as a single function in a single Python module:

```
# pseudocode — implementation owned by the implementer agent
def chapter_designation(chapter_id: str) -> Literal["Mandatory", "Optional"]:
    chapter_number = parse_chapter_number(chapter_id)  # extract from kebab-case basename
    if 1 <= chapter_number <= 6:
        return "Mandatory"
    return "Optional"
```

The threshold (`<= 6`) is a single source of truth in the application code. It is declared in one place, with a docstring citing manifest §8 ("Currently Chapters 1–6 [Mandatory] … Currently Chapter 7 onward [Optional]"). No other code path encodes the threshold; every learner-facing surface that needs the designation calls this function.

### Chapter number parsing

The chapter number is parsed from the Chapter ID per ADR-002. For Chapter 1, the Chapter ID is `ch-01-cpp-refresher`, and the chapter number is `1`. For other Chapters whose IDs follow `ch{NN}...` or `ch{N}...` patterns, the parser extracts the leading numeric component. If the Chapter ID does not match the expected pattern, the function **fails loudly** rather than defaulting to either designation. (This honors the same "no fabrication" principle ADR-002 applied: the system never invents a designation for content whose ID does not unambiguously yield one.)

### Why not a config file

The mapping is *not* stored in a config file (YAML/TOML/JSON), *not* stored in the LaTeX source as front-matter, *not* stored in a database, *not* stored alongside the Chapter file as a sidecar `.meta` file. It is a Python module constant + function. Justification:

- The manifest itself states the rule textually (§8). Anything more elaborate than a code constant would be a less-typed restatement of a manifest fact.
- A config file would create a second source of truth (manifest text + config file) that could drift. With the rule in code, it can drift only via a code edit, which goes through review.
- Sidecar files would require the application to read them, creating a second `content/latex/`-adjacent path that ADR-001's read-only rule would have to extend to cover. Keeping the rule in code keeps the source-layout boundary clean.
- The cost of editing a Python module when the manifest changes the threshold is identical to the cost of editing a config file, with the bonus that the change goes through type-checking and the reviewer agent.

### How the renderer reads it

The renderer (ADR-003's pipeline) calls `chapter_designation(chapter_id)` and passes the result into the Jinja2 template as a variable. The template renders the badge based on that variable. Neither the parser nor the template hardcodes a chapter number.

### What this ADR does *not* decide

- **Section-level designation:** manifest §8 explicitly says Sections inherit from their parent Chapter and "do not carry their own designation independent of the Chapter." This ADR enforces that by having no Section-level designation function. Future ADRs cannot introduce per-Section overrides without superseding both this ADR and (effectively) re-reading manifest §8.
- **The Mandatory-only filter view:** TASK-001 only renders one Chapter's Lecture; no index page exists. The filter view is a future task. This ADR only ensures the data is *available* to be filtered later.
- **Display style of the badge:** the Jinja2 template owns visual treatment. ADR-004 only commits to "the data is exposed; the badge is visible and unambiguous."
- **Where Topics live** (manifest §8 says Topics form a project-wide vocabulary). Topics are not Mandatory/Optional and are unrelated to this ADR.

## Alternatives considered

**A. Encode designation as front-matter inside each `\.tex` file (e.g., a custom `\designation{Mandatory}` macro near the top).**
Rejected. This would require either (a) editing every existing `.tex` file to add the macro — content migration that competes with primary-objective scope — or (b) treating absence-of-macro as a default, which silently splits the source-of-truth between the file and the default rule. Both are worse than reading the manifest's stated rule once and encoding it. It would also tightly couple the source to the application: the manifest says the source is read-only and edited outside the application; designation is application-side metadata, not source-side metadata.

**B. Sidecar YAML/JSON file (e.g., `content/latex/chapters.yaml` listing every chapter and its designation).**
Rejected. Creates a second source of truth that can drift from the manifest. Reading it at startup adds a startup cost and a new "is the file present and well-formed?" failure mode. The threshold rule (1–6 Mandatory, 7+ Optional) is simpler than the data structure needed to express it.

**C. Database table populated from a migration.**
Rejected for TASK-001. There is no database, and manifest-conformance rule MC-10 (persistence boundary) is dormant. Introducing a database for one boolean-per-chapter is outsize. When persistence lands for Quizzes/Attempts, the M/O question can be revisited in a future ADR if that database becomes the natural home — but that is an upflow trigger, not an upstream commit.

**D. Hardcode the designation everywhere it is needed.**
Rejected outright. This is what MC-3 was written to forbid. Any code path that says `if chapter_id == "ch-01-cpp-refresher": badge = "Mandatory"` is a violation; the conformance skill will catch it. The `chapter_designation` function is the single allowed encoding.

**E. Derive from filesystem layout (`content/latex/mandatory/` vs `content/latex/optional/` directories).**
Rejected. This was implicitly considered and rejected in ADR-001 — the source layout deliberately does not encode M/O in directory structure to keep ADR-001 and ADR-004 independent. Adopting this alternative would have required a content-migration commit (move every existing `.tex` into one of two new subdirectories), would have made future re-classification of a chapter (manifest §8 says "Currently Chapters 1–6") a file-move operation rather than a code edit, and would have entangled MC-6 (path read-only) with MC-3 (designation source) in an unhelpful way.

## My recommendation vs the user's apparent preference

The task forecasts "where the Chapter → Mandatory|Optional mapping is recorded." It does not prescribe a mechanism. The user has not signaled a preference for config vs code vs source-embedded. This ADR picks code-as-source and argues it.

**Light pushback worth surfacing for the human:** the manifest says "Currently Chapters 1–6 [Mandatory]" and "Currently Chapter 7 onward [Optional]" with the word "Currently." That word reads as "this is the present mapping; it may shift." If the user expects to revise the threshold often, an editable config file may feel friendlier than a code constant. I am still recommending the code-constant approach because (a) "edit one file" is the same cost either way, (b) the code path goes through the reviewer agent which is precisely where MC-3 wants the change to go through, and (c) the manifest is the conceptual source — code merely mirrors it. If the human disagrees, this ADR is the right place to push back at gate time.

I am NOT pushing back on the manifest itself. The manifest's M/O split (§6, §7, §8) is product behavior and is binding.

## Manifest reading

Read as binding:
- §6: "Mandatory and Optional content are honored everywhere." — Bound the requirement that the designation be exposed on every learner-facing surface.
- §7: "Mandatory and Optional are separable in every learner-facing surface." — Bound the requirement that the data be filterable at the surface level.
- §8: Glossary entries for **Mandatory** ("Currently Chapters 1–6") and **Optional** ("Currently Chapter 7 onward"). — Bound the threshold rule encoded here. Glossary entries for **Chapter** ("Carries a Mandatory or Optional designation. … mutually exclusive at the Chapter level") and **Section** ("Inherits its Mandatory or Optional designation from its parent Chapter; Sections do not carry their own designation independent of the Chapter") — Bound the no-Section-level-designation rule.

No manifest entries flagged as architecture-in-disguise. The "Currently" hedge in §8 is product-level acknowledgment that the curriculum may grow; it does not require a rebuildable config — it requires that the encoding be cheap to update.

## Conformance check

- **MC-3 (Mandatory/Optional designation respects the canonical mapping).** This ADR provides the canonical mapping source MC-3's architecture portion has been waiting on. Once Accepted, MC-3 becomes evaluable end-to-end: the conformance skill can enforce that no code path outside the `chapter_designation` function encodes the chapter-number threshold. The manifest portion (designation visible on every learner-facing surface; learner can view Mandatory-only) remains active and is honored by ADR-003's badge rendering.
- **MC-7 (Single user).** No tension. The function is global, not user-scoped, which is correct.
- No other MC rules are affected.

Previously-dormant rule activated by this ADR (once Accepted): MC-3's mapping-source check.

## Consequences

**Becomes possible:**
- MC-3's architecture-portion check is evaluable: a grep for chapter-number literals (`1, 2, 3, 4, 5, 6` in M/O context, or `< 7`, `<= 6`, etc.) outside the `chapter_designation` function flags violations.
- A future Mandatory-only filter view filters Chapter IDs through `chapter_designation` rather than reimplementing the rule.
- A future per-Chapter dashboard can call the same function to badge Chapters consistently.

**Becomes more expensive:**
- If the user wants to ad-hoc reclassify a single Chapter outside the threshold rule (e.g., "Chapter 4 is now Optional even though it's in the 1–6 range"), the function has to grow from a threshold check to a per-Chapter override structure. That is a real future cost; the threshold encoding is correct *while the manifest's "1–6 Mandatory, 7+ Optional" rule holds*. If the manifest changes the rule, this ADR is superseded.

**Becomes impossible (under this ADR):**
- Per-Section designation overrides (manifest §8 forbids these anyway; this ADR enforces).
- Designation drift across surfaces (every surface calls one function; no surface invents its own rule).

**Future surfaces this ADR pre-positions:**
- The Mandatory-only filter view (a future task) reads from `chapter_designation`.
- Multi-Chapter index page badges every Chapter through the same function.
- Future per-Chapter Quiz aggregation surfaces (if they ever exist; manifest forbids cross-Section quizzes but not aggregated displays) would inherit designation from the Chapter via this function.
