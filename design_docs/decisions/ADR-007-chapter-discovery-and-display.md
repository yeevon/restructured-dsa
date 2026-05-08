# ADR-007: Chapter discovery, display label, and within-group ordering

**Status:** `Accepted`
**Date:** 2026-05-08
**Task:** TASK-002
**Resolves:** none (no project_issues filed against this question; surfaced and addressed during TASK-002 design)

## Context

ADR-006 fixes that the navigation surface (`GET /` landing page + per-Lecture-page rail) renders from a single Python helper that returns the grouped Chapter list. This ADR fixes what that helper does: how Chapters are *enumerated*, what *label* each row shows, and what *order* the rows appear in within each Mandatory/Optional group.

Three coupled questions:

1. **Discovery mechanism.** Three options have material differences: (a) filesystem scan of `content/latex/*.tex` at request time; (b) filesystem scan once at startup, cached for the process lifetime; (c) explicit registry (a Python list of Chapter IDs maintained in code).
2. **Display label source.** Two options: (a) extract `\title{...}` from each Chapter's LaTeX preamble (the Lecture page's title-rendering already does this for the page being rendered, per ADR-003); (b) derive a label from the Chapter ID itself (e.g., `ch-01-cpp-refresher` → "Chapter 1 — Cpp Refresher").
3. **Within-group ordering.** With chapter numbers 1–7 and 9–13 (assuming the human has performed the ADR-005 rename precondition), a documented ordering rule is required by TASK-002's determinism acceptance criterion. Lexical ordering on basenames would be wrong for any future widening that introduced a non-padded digit; chapter-number-ascending sidesteps that risk regardless.

ADR-001 fixes `content/latex/` as the lecture source root and forbids application writes to it (MC-6). ADR-002 fixes "Chapter ID = file basename without extension." ADR-005 (proposed in this same design pass) fixes the single valid Chapter ID form (`ch-{NN}-{slug}`, two-digit zero-padded number, kebab-case lowercase ASCII slug) and rejects everything else, including the legacy `ch{N}` basenames currently on disk for chapters 2–13. ADR-003 fixes that Chapter rendering must be deterministic (byte-identical HTML across two runs against the same source).

The manifest constrains this decision through §6 ("A Lecture has a single source" — the label cannot drift from the source's `\title{...}`), §7 ("Mandatory and Optional are separable in every learner-facing surface" — discovery must classify every discovered Chapter into exactly one group), and §5 ("No in-app authoring" — the application reads, never writes, source).

## Decision

### Discovery mechanism — filesystem scan at request time

The Chapter list is enumerated by scanning `content/latex/` for `*.tex` files **at the moment a navigation route is rendered.** No startup cache, no explicit registry.

The scan returns the set of basenames (without `.tex` extension). Each basename is validated against ADR-005's single regex (`_PATTERN_A` in `app/designation.py`, tightened by `/implement TASK-002` to require exactly two padded digits and a kebab slug); invalid basenames are skipped with a structured WARNING log entry, never silently coerced into the canonical form. Once the human's ADR-005 rename precondition has been performed, every `*.tex` file under `content/latex/` matches the regex and produces a row; before the rename, the eleven legacy `ch{N}.tex` files are rejected by the regex and surfaced as discovery WARNINGs.

Rationale for request-time scan over startup cache:
- TASK-002 has zero performance pressure. The corpus is 12 files; scanning takes microseconds. The `uvicorn --reload` dev workflow already re-imports modules on file change, but does not necessarily re-trigger startup hooks — a request-time scan removes that subtlety.
- Determinism (ADR-003) is preserved trivially: a deterministic source on disk yields a deterministic scan result regardless of when it runs.
- A startup cache would introduce a subtle staleness bug if the human adds a new Chapter file mid-session — the navigation would not show it until restart. The request-time scan picks up new files immediately, which is the right behavior for a single-user, single-session-at-a-time, content-edited-outside-the-application project.
- The MC-6 read-only rule applies identically to scan-at-request and scan-at-startup; no conformance difference.

Rationale for scan over explicit registry:
- An explicit registry (a Python list of Chapter IDs maintained alongside the Chapter files) is a second source of truth that can drift from the filesystem. Manifest §6's "single source" principle for Lecture content extends naturally to "the filesystem is the registry of which Chapters exist."
- A registry would impose a process step on the human ("add the Chapter, then update the registry") that adds friction for no gain. Manifest §5's "Lecture source is edited outside the application" implies the source-of-truth-for-which-Chapters-exist is the source directory itself.
- The conformance benefit of a registry (detecting "is this Chapter file expected?") is hypothetical at this scope.

### Display label source — extract `\title{...}` from each Chapter's preamble; fall back to a structured error row if missing

For each discovered Chapter, the navigation helper extracts the `\title{...}` macro contents from the Chapter's `.tex` file using the same simple regex-based extraction the existing route handler uses (`_extract_title` in `app/main.py`, established by ADR-003). The result is normalized to plain text (stripping LaTeX formatting macros within the title) and used as the row's display label.

If `\title{...}` is missing, malformed, or extracts to an empty string, the Chapter row **fails loudly per row**: the navigation surface renders that row with a structured error label (e.g., a visually-distinct "[Chapter `{chapter_id}` — title unavailable]" row), and a structured WARNING is logged. The row's link still points at `/lecture/{chapter_id}` (clicking it will then succeed or fail loudly under ADR-003's existing rendering contract). The navigation surface does **not** silently fabricate a label, and does **not** hide the row from the navigation — both behaviors would violate the "AI failures are visible" principle (manifest §6) extended to non-AI failures (the principle ADR-002 and ADR-004 already extended to fail-loudly behavior).

The navigation surface as a whole still renders. One bad Chapter does not crash the navigation; only its own row is degraded. This is consistent with TASK-002's acceptance criterion: "that Chapter row fails loudly … but never silently fabricates a title or designation."

Rationale for `\title{...}` over Chapter-ID-derived labels:
- The author has invested editorial effort in the `\title{...}` strings (`"CS 300 -- Chapter 7 Lectures\\\large Heaps and Priority Queues"`). That effort is the project's only signal of what each Chapter is *about*. Deriving a label from `ch-07-heaps-and-priority-queues` would duplicate the topical information from the slug, and the duplication would silently diverge the moment the author revises a `\title{...}` without renaming the file.
- Manifest §6 ("A Lecture has a single source") is honored: the title shown in the rail is the same title shown in the Lecture page's header. There is no second source of label information.
- The `\title{...}` extraction code already exists in `app/main.py` (`_extract_title`) and is exercised by TASK-001's tests. Reusing it ensures the rail label and the Lecture page header agree by construction.

The extraction helper is moved out of `app/main.py` into a shared module (the architect leaves the exact module location to the implementer; one natural choice is `app/parser.py` since the parser already extracts other LaTeX content, or a new `app/discovery.py` if the implementer prefers separation). Wherever it lives, both `app/main.py`'s Lecture route and the new navigation helper call the same function — no two implementations of title extraction.

### Within-group ordering — by parsed chapter number ascending

Within each Mandatory/Optional group, Chapters are ordered by their parsed chapter number (the integer returned by `parse_chapter_number()`, ADR-004) **ascending**. Examples (post-rename, the corpus state assumed by `/implement TASK-002`):

- Mandatory group: `ch-01-cpp-refresher` (1), `ch-02-<slug>` (2), `ch-03-<slug>` (3), `ch-04-<slug>` (4), `ch-05-<slug>` (5), `ch-06-<slug>` (6).
- Optional group: `ch-07-<slug>` (7), `ch-09-<slug>` (9), `ch-10-<slug>` (10), `ch-11-<slug>` (11), `ch-12-<slug>` (12), `ch-13-<slug>` (13). (`ch08` is absent from disk; the gap is rendered as a gap — no placeholder, no error.)

Rationale:
- The chapter number is the project's existing identity handle (ADR-002, ADR-004). Sorting by it produces an order that matches both the syllabus reading order and the user's mental model. Under Form A only, the chapter number is captured directly by the regex's `\d{2}` group — a single, unambiguous parse per basename.
- Lexical ordering on basenames is rejected. Even though the Form-A canonical form pads to two digits (so `ch-02-...` and `ch-10-...` lexically sort correctly today), the ordering rule is anchored on the parsed integer rather than the basename string so a future widening (Chapters 100+, requiring a regex relaxation per ADR-005's "Future surfaces") does not silently invalidate the sort.
- Chapter-number ascending is deterministic for any fixed corpus, satisfying TASK-002's determinism criterion.
- The gap (no `ch08`-prefixed file) is handled by simply not emitting a row for the missing Chapter. The navigation surface shows the present Chapters in the canonical order; absence is silent absence (the human knows Chapter 8 is missing because they curated the corpus, and the navigation accurately reflects what is on disk).

Under Form A only, two discovered files cannot share the same chapter number unless their slugs differ — e.g., `ch-07-heaps.tex` and `ch-07-priority-queues.tex` both present. If that occurs, the navigation helper **fails loudly** for the entire surface, not just the conflicting rows. Rationale: two source files claiming the same Chapter ID number is an unrecoverable ambiguity — the rail cannot pick one without silently choosing, and silent choice is forbidden by ADR-005 / ADR-002 fail-loudly principles. A noisy crash here is the right behavior; the human resolves by deleting or renaming one of the two files.

### Helper signature and return shape

The navigation helper has a deterministic, type-hinted signature. The architect specifies the contract; the implementer chooses the exact module location.

```
# pseudocode — implementation owned by the implementer agent
def discover_chapters(source_root: pathlib.Path) -> dict[
    Literal["Mandatory", "Optional"],
    list[ChapterEntry]
]:
    """
    Enumerate Chapter files under source_root, group by designation,
    sort each group by chapter number ascending. Returns a dict with
    exactly two keys: "Mandatory" and "Optional". Each value is a list
    (possibly empty) of ChapterEntry objects in canonical order.
    """

class ChapterEntry:
    chapter_id: str       # canonical Chapter ID per ADR-005
    chapter_number: int   # parsed from the ID per ADR-004
    display_label: str    # extracted from \title{...} per this ADR
    link_target: str      # e.g. f"/lecture/{chapter_id}"
    label_status: Literal["ok", "missing_title", "malformed_title"]
```

The exact shape of `ChapterEntry` (dataclass, NamedTuple, TypedDict, Pydantic model) is an implementation choice. The architect commits to: a stable record per Chapter with the named fields above, deterministic ordering within each group, and structured `label_status` for fail-loudly rendering of degraded rows.

### Scope of this ADR

This ADR fixes only:

1. The discovery mechanism (filesystem scan at request time).
2. The display-label source (`\title{...}` extraction with fail-loudly fallback per row).
3. The within-group ordering rule (chapter number ascending).
4. The required helper return shape and the per-row degradation contract.

This ADR does **not** decide:

- Where the helper lives (which module). Implementer choice.
- The exact data class / type used for `ChapterEntry`. Implementer choice.
- CSS / visual treatment of degraded rows. Implementer choice (must be visually distinct; not architecture).
- Whether subsequent caching is added if performance pressure ever surfaces. A future ADR can add a cache.

## Alternatives considered

**A. Discovery via filesystem scan at startup, cached in module state for the process lifetime.**
Rejected. The cache invalidates incorrectly when the human adds a new Chapter file mid-session, and the staleness bug surfaces silently. Performance is not a concern at this scope. Caching is a future-ADR concern when there's a real cost to amortize.

**B. Discovery via explicit registry (a Python list `CHAPTERS = ["ch-01-cpp-refresher", "ch-02-arrays", ...]`).**
Rejected. Two sources of truth (filesystem + list); the list will drift. Manifest §6's "single source" principle and §5's "source edited outside the application" jointly motivate "filesystem is the registry."

**C. Display label from `\title{...}` (chosen) vs from the Chapter ID's slug.**
ID-derived labels considered and rejected:
- Form A IDs carry topical metadata in the slug (e.g., `ch-01-cpp-refresher`), but rendering "Cpp Refresher" loses the editorial polish the author put into `\title{...}` ("CS 300 — Chapter 1 Lectures: C++ Refresher" or similar).
- Slug-derived labels would silently diverge from the `\title{...}` content the moment the author revises a `\title{...}` without renaming the file (and renaming requires also renaming any persisted Chapter-ID references, which is exactly the cost ADR-005 commits to paying once now and never again).
- Manifest §6 ("A Lecture has a single source") motivates: the title shown in the rail is the same title shown in the Lecture page header. There is no second source of label information.

**D. Display label from `\title{...}` with the route-specific Lecture title regex *duplicated* in the navigation helper (rather than extracted into a shared function).**
Rejected. Two implementations of title extraction will drift. Manifest §6 ("A Lecture has a single source") motivates a single extraction. The architect's directive: extract once, reuse twice.

**E. Within-group order by display label alphabetically.**
Rejected. Labels are editorial; sorting on them introduces ordering instability when titles are revised, and produces a non-syllabus order. Chapter number is the natural pedagogical order.

**F. Within-group order by basename lexically.**
Rejected. Under Form A only, lexical order on the post-rename corpus happens to coincide with chapter-number order (because the digits are zero-padded to two), but the rule is anchored on the parsed integer rather than the basename string so a future widening (Chapters 100+, requiring a regex relaxation per ADR-005's "Future surfaces") does not silently invalidate the sort. Parsing the chapter number out is the chosen approach.

**G. Hide degraded rows (Chapter with missing `\title{...}`) entirely from the navigation.**
Rejected. Hiding silently violates the fail-loudly principle ADR-002 and ADR-004 established for non-AI failures. The human's expectation, when they put a `.tex` file in `content/latex/`, is that it appears in the navigation. Silently dropping it because of a malformed preamble would surface as "where did Chapter 7 go?" — a debugging problem the noisy-degraded-row design avoids.

**H. Crash the entire navigation surface if any Chapter has a missing/malformed `\title{...}`.**
Rejected. One bad Chapter should not deny the human access to the other 11. Per-row degradation preserves the navigation's primary value (discoverability of working Chapters) while still surfacing the failure (the bad row is visibly broken). This is the same design principle ADR-003 applies to unknown LaTeX nodes (warn per node, don't crash the page).

## My recommendation vs the user's apparent preference

The human did not signal a preference between filesystem scan and explicit registry, between `\title{...}` and ID-derived labels, or between chapter-number ordering and label ordering. The reframed TASK-002 listed all three as architectural decisions the design ADR would make.

I am recommending the lowest-friction options consistent with the project's existing architecture:
- Filesystem scan at request time (matches ADR-001's "source edited outside the application" rhythm).
- `\title{...}` extraction (matches ADR-003's existing Lecture title behavior; preserves manifest §6's single-source rule).
- Chapter-number ordering (matches ADR-002/ADR-004's existing identity model).

The only place I would surface mild pushback is on the `ch7.tex` / `ch-07-foo.tex` collision case: the architect chooses **fail loudly for the whole surface** rather than fail loudly per row, because two files claiming the same chapter number is a corpus-level invariant violation, not a row-level data quality issue. If the human prefers per-row degradation here too (pick one arbitrarily, log a warning), this ADR can be amended at the gate. The architect's recommendation stays at "the corpus must not contain Chapter-number duplicates; the system surfaces the duplicate clearly so the human can resolve."

I am NOT pushing back on:
- The manifest's invariants (§6, §7) — honored.
- ADR-005's single-canonical-form (Form A only) naming rule — consumed correctly here.
- ADR-006's two-surface architecture — consumed correctly here.

## Manifest reading

Read as binding:
- §5 Non-Goals: "No in-app authoring of lecture content. Lecture source is edited outside the application; the application reads it, never writes it." Bound the read-only rule for filesystem scan.
- §6 Behaviors and Absolutes: "A Lecture has a single source." Bound the single-extraction rule for `\title{...}`. The label in the rail and the title in the Lecture page header come from the same source-extraction function.
- §6: "Mandatory and Optional content are honored everywhere." Bound the requirement that *every* discovered Chapter is classified into exactly one group.
- §7 Invariants: "Mandatory and Optional are separable in every learner-facing surface." Bound the discovery contract: the helper returns a dict with exactly the two keys "Mandatory" and "Optional," and every Chapter belongs to exactly one.
- §8 Glossary entries for Chapter, Mandatory, Optional. Bound the per-row data model.

No manifest entries flagged as architecture-in-disguise.

## Conformance check

- **MC-3 (Mandatory/Optional designation respects the canonical mapping).** Every discovered Chapter is routed through `chapter_designation()` (ADR-004) to determine its group. The navigation helper does not encode any chapter-number threshold. Compliance preserved.
- **MC-6 (Lecture source is read-only to the application).** The filesystem scan opens files only for reading (the `\title{...}` extraction reads the preamble; the rest of the file is not opened until the Lecture route is hit). No write paths against `content/latex/`. Compliance preserved.
- **MC-7 (Single user).** Discovery is global; no per-user state. Compliance preserved.
- **MC-1 / MC-2 / MC-4 / MC-5 / MC-8 / MC-9 / MC-10.** Not touched.

Previously-dormant rule activated by this ADR: none.

## Consequences

**Becomes possible:**
- The navigation surface (ADR-006) has a deterministic, type-hinted helper to consume.
- New Chapter files are discoverable immediately upon being placed in `content/latex/` — no code change, no registry update, no restart required (under the request-time-scan rule).
- Bad Chapter files (missing `\title{...}`, malformed preamble) are surfaced as visibly-degraded navigation rows rather than disappearing or crashing the surface.

**Becomes more expensive:**
- Every navigation render performs N filesystem reads (one per Chapter, just to extract the `\title{...}`). At 12 chapters this is trivial; at hundreds of chapters it would matter. **Mitigation in this ADR:** implementer extracts only the `\title{...}` from each file (read enough to find the macro; do not read the entire file). At scale, a future ADR can add a cache invalidated by mtime.
- A future move to per-Section files (ADR-001 alternative B, currently rejected) would require this ADR to be superseded — discovery semantics change when the file is no longer the unit of a Chapter.

**Becomes impossible (under this ADR):**
- A navigation surface that silently hides a Chapter from view because of a malformed preamble. Per-row degradation is the only allowed failure mode short of a corpus-level Chapter-number collision.
- A navigation surface that orders Chapters lexically. Order is by chapter number, full stop.
- A second source of truth for the Chapter list (the filesystem is canonical). A future ADR introducing a registry would have to argue against this one.

**Future surfaces this ADR pre-positions:**
- Per-Chapter completion indicators (manifest §7: completion lives at the Section level; Chapter-level progress is derived) — fit naturally into `ChapterEntry` as an additional field once persistence lands.
- Per-Chapter "has Notes" indicator (manifest §8) — same shape, additional field.
- Future "show chapter description" hover/tooltip — natural extension reading additional preamble metadata.
- A future Mandatory-only filter view (currently rejected by TASK-002) could simply pass `nav_groups["Mandatory"]` to the template and omit the Optional group, with no change to the discovery helper.
