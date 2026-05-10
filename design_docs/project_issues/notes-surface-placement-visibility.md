# Notes surface placement — bottom-of-page is practically invisible at chapter scale

**Status:** Open
**Surfaced:** 2026-05-10 (TASK-009 human commit-gate review)
**Decide when:** when Notes feature work next surfaces (e.g. edit/delete/Markdown/Section-ref follow-up) — relocation can ride alongside that ADR rather than re-cycling Notes alone. Not a blocker for shipping TASK-009.

## Question

ADR-023 (Accepted, 2026-05-10) committed to placing the Notes section at the bottom of `lecture.html.j2`'s `{% block main %}`, after all rendered Sections. TASK-009's reviewer gave `READY-TO-COMMIT` against the ADR-023 contract.

At commit-gate review the human raised that ADR-023's placement is **architecturally wrong for the actual content scale**:

**Empirical chapter lengths (LaTeX source, 12 chapters):**

| Stat | LaTeX lines | LaTeX bytes |
|---|---|---|
| Shortest (`ch-12-sets`) | 1,588 | 67 KB |
| Longest (`ch-03-intro-to-data-structures`) | 3,437 | 143 KB |
| Mean | ~2,144 | ~92 KB |
| Total (corpus) | 25,727 | 1,103 KB |

Rendered HTML for `ch-01-cpp-refresher` is **118 KB** — order of 30+ viewport heights of scroll on a typical laptop. The Notes surface, appended after all Sections, is therefore many screens below the reading flow. A learner finishes reading and must scroll past the entire chapter to reach a Notes affordance that ADR-023 commits is visible "on every Chapter page."

**The rail (`_nav_rail.html.j2` + ADR-008 `base.css`) is already `position: sticky; top: 0; max-height: 100vh`** — visible the whole way down. With 12 chapter entries (Mandatory + Optional groups), it occupies roughly 30–40% of viewport height; the remaining 60–70% is empty real estate that scrolls with the page.

The mismatch: a sticky-and-mostly-empty rail is the natural home for a per-chapter persistent affordance; the bottom of a 30-screen page is not.

## Options known

- **Option 1 — Rail-resident Notes panel.** Add a Notes section to `_nav_rail.html.j2` below the chapter list, sharing the sticky rail's `position: sticky` real estate. Pros: per-chapter Notes always visible regardless of scroll position; uses currently-wasted real estate; matches the chapter-scoped lifetime of a Note. Cons: rail is `minmax(220px, 18rem)` wide — body field may feel cramped on narrower viewports; needs a CSS decision on overflow/scrollbars inside the rail; touches ADR-008's CSS-file split (`base.css` owns rail).
- **Option 2 — Split rail (top = chapter list, bottom = Notes).** Same as Option 1 but with explicit 50/50 (or other ratio) vertical partition inside the rail. Pros: predictable layout; clear visual hierarchy. Cons: less flexible than scroll-based stacking; ratio is a design call that needs justification.
- **Option 3 — Floating/anchored Notes panel.** A fixed-position panel pinned to a viewport corner with show/hide affordance. Pros: doesn't compete with rail width. Cons: more JS surface (manifest §6 currently allows none here, and ADR-023 deliberately committed to synchronous no-JS); may conflict with `select_autoescape` Note-rendering assumptions; visual interference with chapter content.
- **Option 4 — Keep ADR-023's bottom-of-page placement.** Status quo. Pros: zero change cost; works correctly for short chapters and as a "submit and forget" feature. Cons: defeats the value-proposition for the actual corpus.

Option 1 is the architect's current forecast; Option 2 is a structural variant; Option 3 is technically possible but contradicts ADR-023's synchronous-no-JS stance and the manifest's no-AI-on-this-surface posture.

## Decide when (priority context)

The human's commit-gate guidance (recorded here as the framing for whichever architect picks this up):

> "It def. needs to be moved. Does it need to be moved now? Not really — we're still in build mode adding other features. The rest of the Notes features [edit / delete / Markdown / Section-ref / multi-Note polish] probably has higher priority. As long as moving its location isn't a sticky point, it should be prioritized accordingly."

Practical implication: the next Notes-related task (whether that's TASK-NNN-notes-edit-and-delete, TASK-NNN-notes-markdown-rendering, TASK-NNN-notes-section-reference, or similar) should bundle the placement supersedure into its `/design` cycle. A standalone "just move the Notes section" task is the wrong shape — re-running the test-writer + implementer cycle for a CSS/template tweak is high overhead for low delta. The supersedure ADR (likely `ADR-NNN supersedes ADR-023 §Template-surface`) rides alongside whatever ADR the next Notes task needs.

If no Notes task surfaces within ~3 `/next` cycles, the architect should propose a standalone surface-relocation task to prevent the visibility issue from becoming permanent.

## Cross-references

- ADR-023 §Template-surface (placement decision being challenged)
- ADR-008 (`base.css` owns the rail; rail is sticky)
- `_nav_rail.html.j2` (current rail contents)
- TASK-009 audit Run 006 (reviewer `READY-TO-COMMIT` against ADR-023 as written; this issue does not re-open the commit gate)
- Manifest §3 (Notes as a primary pillar — visibility is value-load-bearing)
