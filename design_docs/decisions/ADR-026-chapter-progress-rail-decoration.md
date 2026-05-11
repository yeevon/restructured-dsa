# ADR-026: Chapter-level derived progress display — rail-resident "X / Y" decoration + bulk persistence accessor

**Status:** `Accepted`
Auto-accepted by /auto on 2026-05-10
**Date:** 2026-05-10
**Task:** TASK-011
**Resolves:** none (no project_issue filed against this question; the surface decision is forced inline by TASK-011 as the activation of the manifest §7 second-half invariant "Chapter-level progress is derived from Section state")
**Supersedes:** none

## Context

TASK-010 shipped the first half of manifest §7's two-part invariant: **"Completion state lives at the Section level."** ADR-024 committed the schema (`section_completions` table; presence ≡ complete; `chapter_id` indexed); ADR-025 committed the per-Section UI surface (the toggle affordance now per ADR-025 §Template-placement, soon to be superseded by ADR-027). Both ADRs explicitly named "Chapter-level derived progress display" as their primary forecasted future consumer.

This ADR is the **second half** of the invariant: **"Chapter-level progress is derived from Section state."** The derivation must live somewhere in code; this ADR fixes where, what shape it takes, and how the rail consumes it.

The decision space has materially different alternatives:

- **Display surface placement:** inside each `<li class="nav-chapter-item">` in `_nav_rail.html.j2` (the existing per-Chapter row), or a separate per-Chapter mini-table elsewhere on the page, or a dedicated `/progress/{chapter_id}` page, or a header badge on the Lecture page itself.
- **Visual shape:** plain text "X / Y" suffix, a graphical progress bar, a percent ("60%"), a checkmark-only indicator for full + count for partial, or a combination.
- **Empty-state and full-state:** "0 / Y" verbatim vs hidden-when-zero; "Y / Y" verbatim vs a checkmark glyph vs a bolder weight.
- **Persistence accessor shape:** call the existing `list_complete_section_ids_for_chapter(chapter_id)` once per Chapter row in the rail-context-build loop (12 SQL calls per page render at the current corpus size); or introduce a new bulk accessor `count_complete_sections_per_chapter() -> dict[str, int]` (one SQL call: `SELECT chapter_id, COUNT(*) FROM section_completions GROUP BY chapter_id`).
- **Total-Sections denominator source:** call `extract_sections(chapter_id, latex_text)` per Chapter to count Sections at rail-build time (12 file reads + parses per render); or extend the existing `discover_chapters()` helper (or a sibling) to return a per-Chapter Section count alongside the existing `ChapterEntry` fields; or cache.
- **Chapter-progress derivation home:** route handler composes the rail context inline; or `app/discovery.py` grows a new helper; or `app/persistence/section_completions.py` exposes the bulk accessor and the route composes; or a new `app/progress.py` module owns the derivation.

The manifest constrains the decision through §3 (consumption-tracking primitive — supports retention by giving the learner a visible "this is how far I've gotten in this Chapter" affordance), §5 (no LMS — no progress export, no gradebook semantics; the display is internal-only), §6 (Mandatory and Optional honored everywhere — the rail's existing designation grouping must continue to honor the split, and the per-Chapter progress decoration must respect it), §7 (**"Completion state lives at the Section level. Chapter-level progress is derived from Section state."** — the derivation must be a function of Section state, never a separately-stored Chapter-level counter), §8 (Chapter is the parent of Sections; Sections are the atomic unit for completion).

## Decision

### Display surface placement — inside each `<li class="nav-chapter-item">` in `_nav_rail.html.j2`, after the chapter label

The per-Chapter progress decoration is rendered inside each existing `<li class="nav-chapter-item">` row in the rail partial, appended after the existing `<a>` link's display label. The rail iterates each `nav_groups["Mandatory"]` and `nav_groups["Optional"]` group exactly as today; this ADR adds **one additional rendered element per row** (a small `<span class="nav-chapter-progress">` containing the "X / Y" text), and nothing else changes in the rail's structure.

The decoration is **rail-resident** rather than displayed on a separate page or as a header badge because:

- The rail is the only surface that already iterates every Chapter (per ADR-006/ADR-007). Adding the progress decoration to the existing iteration is structurally cheap.
- The rail is `position: sticky` (per ADR-008's `.lecture-rail` styling) and visible from any scroll position. A learner partway through a Chapter sees both their progress on the current Chapter and on every other Chapter without scrolling.
- A separate `/progress/{chapter_id}` page would split the navigation surface from the progress surface, forcing a navigation round-trip; a header badge would be visible only at the top of each Lecture page (defeating the "visible from any scroll position" property the rail already provides).

The decoration is **per-Chapter "X / Y" text**, where:

- `X` is the count of complete Sections for that Chapter (from the persistence layer).
- `Y` is the total count of discovered Sections for that Chapter (from the parser).

The decoration appears **only when Y > 0** — Chapters with zero discovered Sections (none in the current corpus, but the rail's per-row degradation contract from ADR-007 already handles malformed chapters) suppress the decoration entirely. An error-row (`label_status != "ok"`) likewise suppresses the decoration, preserving ADR-007's per-row fail-loudly visual.

### Visual shape — plain "X / Y" text suffix, no progress bar, no percent

The decoration is rendered as plain text in the form `"X / Y"` (e.g., `"3 / 7"`) inside a `<span class="nav-chapter-progress">`. There is no progress bar, no percent, no checkmark glyph for the complete state. The empty-state ("0 / Y") and full-state ("Y / Y") are displayed using the same plain-text shape.

Rationale:

- A progress bar is a graphical element that competes for visual attention with the chapter label. The rail is narrow (`minmax(220px, 18rem)` per ADR-008); a bar would either be too small to read or push the chapter label horizontally. Plain text is unambiguous and fits within the existing line-height.
- A percent ("43%") obscures the underlying count — the learner cannot tell whether 43% means "3 of 7" or "43 of 100." For a study tool where the per-Chapter Section count varies from ~3 to ~10, the raw count is more informative than the ratio.
- A checkmark-only indicator for the full state ("✓") would inconsistent with the partial states and force a special-case in CSS for color treatment. Keeping the same shape across all states (zero, partial, full) is simpler and more honest about what the data means.
- The full-state ("Y / Y") gets a distinct visual weight via the `nav-chapter-progress--complete` modifier class (added when X == Y). The implementer may apply a bolder weight, a green tint matching the existing `--ok` palette, or both — implementer-tunable within the architectural commitment that the full-state read as "complete" without a glyph.
- The text is rendered with a separator (a CSS-controlled space and a slightly muted color via `.nav-chapter-progress`) so the chapter label remains visually dominant.

### Empty-state and full-state — same plain-text shape; full-state gets a CSS modifier class

- **Empty state ("0 / Y"):** rendered verbatim. A Chapter the learner has not started shows "0 / 7" (or whatever Y is). The decoration is present, not hidden — the learner sees the denominator from day one, which is itself useful information ("this Chapter has 7 Sections to read").
- **Partial state ("X / Y" with 0 < X < Y):** rendered verbatim. No special treatment.
- **Full state ("Y / Y"):** rendered verbatim with the `.nav-chapter-progress` element additionally carrying a `nav-chapter-progress--complete` modifier class, so CSS can apply a distinct visual treatment (bolder weight, green tint, or both — implementer-tunable). No glyph is added; no count is hidden.

The full-state CSS modifier class is the architectural commitment; the specific visual treatment is implementer-tunable.

### Persistence accessor shape — new bulk accessor `count_complete_sections_per_chapter() -> dict[str, int]`

A new function is added to `app/persistence/section_completions.py`:

```python
def count_complete_sections_per_chapter() -> dict[str, int]:
    """
    Return a mapping of {chapter_id: complete_section_count} for every
    Chapter that has at least one complete Section.

    Chapters with zero complete Sections are NOT in the returned dict —
    callers must default to 0 for missing keys.

    SQL lives here — not in the caller (ADR-022 / ADR-024 §Package boundary).
    """
```

The implementation is one SQL statement:

```sql
SELECT chapter_id, COUNT(*) AS complete_count
FROM section_completions
GROUP BY chapter_id
```

The function is re-exported from `app/persistence/__init__.py` alongside the existing `list_complete_section_ids_for_chapter` and the rest of the section-completions API.

Rationale (bulk accessor over per-Chapter call-in-loop):

- The rail iterates every Chapter on every page render (12 today; potentially ~20 if Optional chapters grow). Calling `list_complete_section_ids_for_chapter(chapter_id)` once per Chapter would be 12 SQL queries per page render, each fetching the full ID set just to discard it after taking `len()`. The bulk accessor is one query.
- The `chapter_id` column is already indexed (per ADR-024 §Schema). `GROUP BY chapter_id` uses that index directly.
- The bulk accessor is the **canonical "derive Chapter progress from Section state" code path** going forward. Future consumers (Mandatory-only filtered progress, "X% of Mandatory complete" header badges, completion-history surfacing, Quiz-bootstrap's per-Chapter Quiz status) consume the same accessor; the manifest §7 second-half invariant has a single source of truth in code.
- The single-result-set return shape (`dict[str, int]`) is small (~100 bytes for the current corpus); the cost of building the dict is negligible.
- The existing per-Chapter accessor `list_complete_section_ids_for_chapter(chapter_id)` is preserved unchanged — the Lecture page route consumes it (via ADR-025) for per-Section heading state, and removing it would force an unrelated change. The two accessors coexist.

The route handler (`/lecture/{chapter_id}` and `/`) calls `count_complete_sections_per_chapter()` once when building the rail context, then attaches the count to each `ChapterEntry` (or to a parallel structure the template iterates).

### Total-Sections denominator source — extend `discover_chapters()` to include per-Chapter Section count

The denominator (Y = total Sections in Chapter) is derived from `extract_sections(chapter_id, latex_text)`. To avoid invoking the parser 12 times per page render, the existing `discover_chapters(source_root)` helper (in `app/discovery.py`) is extended to **also** read each Chapter's `.tex` file and call `extract_sections()` to compute the Section count, attaching it to each returned `ChapterEntry` as a new field `section_count: int`.

Concretely, the `ChapterEntry` shape is extended to:

```python
class ChapterEntry:
    chapter_id: str
    chapter_number: int
    display_label: str
    link_target: str
    label_status: Literal["ok", "missing_title", "malformed_title"]
    section_count: int   # NEW — number of Sections discovered in this Chapter
```

Rationale:

- `discover_chapters()` already opens each `.tex` file to extract `\title{...}` (per ADR-007). Adding a single call to `extract_sections()` against the same already-read text is incrementally cheap (the file is in memory; the parser runs once more per Chapter).
- The Lecture page route already calls `extract_sections()` for the requested Chapter (in `render_chapter()`); no change there.
- The total-Sections count is a property of the Chapter (a function of the source `.tex` file), so it belongs alongside the other Chapter metadata in `ChapterEntry`. Putting it elsewhere (e.g., in a separate `chapter_section_counts: dict[str, int]` parallel to `nav_groups`) would force the template to consult two structures in lockstep.
- Failure mode: if `extract_sections()` raises `ValueError` for a Chapter (per ADR-002 fail-loudly), the `ChapterEntry` records `section_count = 0` and `label_status` is degraded to a new value (`"section_extraction_failed"`) so the row renders in the warning palette per ADR-008. The rail does not crash; the bad Chapter shows as broken just like ADR-007's per-row degradation for missing titles. **Architect's read:** this is a small, additive addition to ADR-007's per-row fail-loudly contract; it does not require a supersedure of ADR-007 because (a) ADR-007's spec already names `label_status` as `Literal["ok", "missing_title", "malformed_title"]` with the explicit caveat that "the row's link still points at `/lecture/{chapter_id}` (clicking it will then succeed or fail loudly under ADR-003's existing rendering contract)" — adding a fourth literal value is consistent with that contract; (b) the new failure mode is empirically rare (every Chapter currently parses cleanly).

### Chapter-progress derivation home — route handler composes from `discover_chapters()` (denominator) + `count_complete_sections_per_chapter()` (numerator)

The route handlers (`/`, `/lecture/{chapter_id}`) compose the rail context as follows:

1. `nav_groups = discover_chapters(source_root)` — already returns per-Chapter `section_count` after this ADR's extension.
2. `complete_counts = count_complete_sections_per_chapter()` — new bulk accessor.
3. For each Chapter in `nav_groups["Mandatory"]` and `nav_groups["Optional"]`, attach `complete_count = complete_counts.get(chapter_id, 0)` to the row's data — either by mutating the `ChapterEntry` or by passing a parallel dict to the template (implementer's call; the cleaner shape is mutation-via-attribute, but the architectural commitment is the data flow, not the structure).
4. The template reads `entry.section_count` (denominator) and `entry.complete_count` (numerator) and renders `<span class="nav-chapter-progress">{{ entry.complete_count }} / {{ entry.section_count }}</span>` (with the `--complete` modifier when equal).

The composition lives in the route handlers (or in a small helper they share). It does **not** live in `discover_chapters()` itself because that helper reads only the filesystem (per ADR-007); coupling it to the persistence layer would muddy its single responsibility.

### CSS class ownership — `.nav-chapter-progress` lives in `base.css`

Per ADR-008's class-name-prefix convention (`.nav-*` → `base.css`), the new `.nav-chapter-progress` and `.nav-chapter-progress--complete` classes belong in `app/static/base.css`. The implementer adds the rules under the existing `.nav-chapter-item` block.

The visual styling is implementer-tunable (font size, color, weight, modifier-state treatment) within the architectural commitment that:

- Plain text "X / Y" is the rendered shape.
- The decoration is visually subordinate to the chapter label (smaller, lighter, or both) so it does not compete for attention.
- The full-state modifier class produces a visually distinct "complete" treatment (bolder, green-tinted via the existing `--ok` family, or both).

### Chapter-level progress is the canonical derivation path (manifest §7 second-half anchor in code)

This ADR commits to the bulk accessor + extended `discover_chapters()` shape as the **single canonical "derive Chapter progress from Section state" code path** going forward. Future consumers consume this same shape:

- Mandatory-only filtered progress views (e.g., "you are 60% through Mandatory") consume the same `complete_counts` dict, summing across Mandatory chapters.
- Completion-history surfacing (e.g., "Sections completed this week") consumes the existing `completed_at` column (per ADR-024) via a new accessor; the bulk-count accessor remains the per-Chapter aggregation.
- Quiz-bootstrap's per-Chapter Quiz status (when it lands) consumes the bulk-count accessor for the "Sections complete vs Sections quizzed" comparison, without needing to re-derive completion counts.

Manifest §7's second-half invariant ("Chapter-level progress is derived from Section state") thus has a single, named code path: `count_complete_sections_per_chapter()` + `discover_chapters().section_count`. Future contributors who want per-Chapter progress in any new surface consume this path and do not invent parallel derivations.

### Known limitation — orphan/renumber problem deferred

The `section_completions` table stores Section IDs per ADR-024 (`{chapter_id}#section-{n-m}`). If a Chapter's source `.tex` is edited to remove a Section (e.g., 1-3 is deleted) or to renumber Sections (e.g., 1-3 becomes 1-2 because 1-2 was deleted), the persisted completion rows for the now-absent Section IDs become orphans:

- An orphan completion row's Section ID does not match any current Section. The row is invisible to the Lecture page (ADR-025's per-Section template loop iterates only currently-discovered Sections).
- The bulk accessor `count_complete_sections_per_chapter()` will still count the orphan row in the per-Chapter total, producing a numerator (X) that exceeds the parser-derived denominator (Y). The "X / Y" decoration could read "8 / 7" — visually wrong.
- The renumber case is worse: the persisted row points at (e.g.) `ch-01#section-1-3`, but the *new* `1-3` is a different Section than what the user originally completed. The decoration count is preserved but its semantic meaning has silently drifted.

**This ADR explicitly does NOT solve the orphan/renumber problem.** Reasons:

- The problem requires either (a) a content-change-detection mechanism that invalidates orphan completion rows when source Sections are removed/renumbered, (b) a UI surface for the user to manually reconcile orphan completions, or (c) a stricter Section-ID derivation that survives renumbering (e.g., a stable Section UUID embedded in the LaTeX source). Each is a substantial decision worthy of its own ADR.
- Quiz-bootstrap will hit the same problem at higher cost (Quiz Attempt rows reference Section IDs and Question IDs that derive from Section content; renumbering a Section invalidates Quiz history). The orphan/renumber question is best decided in the context of Quiz-bootstrap, where the cost is higher and the design space is broader.
- At the current single-user, content-author-aware-of-changes operating model, the orphan case is rare and self-correcting (the user notices "X / Y" reading 8/7 and either re-marks the Section or accepts the discrepancy as a known artifact).

The `count_complete_sections_per_chapter()` function clamps the displayed numerator to the denominator at the **template level** (CSS-only or inline Jinja `min(count, total)` — implementer's call), so the rail never visually shows "8 / 7." The underlying database row is preserved (no silent deletion); only the displayed value is clamped. This is a minimum-viable defensive measure, not an orphan-resolution mechanism.

**Recorded as a known limitation in this ADR's Consequences. A future task (likely Quiz-bootstrap or a dedicated content-change-reconciliation task) will address it.**

### Scope of this ADR

This ADR fixes only:

1. The display surface placement (inside each `nav-chapter-item` in `_nav_rail.html.j2`, appended after the chapter label).
2. The visual shape (plain text "X / Y"; no bar; no percent; no glyph).
3. The empty-state and full-state shapes (verbatim text; full-state gets a CSS modifier class).
4. The persistence accessor shape (new bulk accessor `count_complete_sections_per_chapter() -> dict[str, int]` in `app/persistence/section_completions.py`).
5. The total-Sections denominator source (extend `discover_chapters()` to compute and return per-Chapter `section_count`; new `label_status` value `"section_extraction_failed"` for parser failures).
6. The chapter-progress derivation home (route handler composes; this ADR's accessor + extended `discover_chapters()` is the canonical code path for manifest §7's second-half invariant).
7. The CSS class ownership (`.nav-chapter-progress` and `.nav-chapter-progress--complete` in `app/static/base.css`).
8. The orphan/renumber problem as an explicit known limitation deferred to a future task (with a template-level clamp as the minimum-viable defensive measure).

This ADR does **not** decide:

- Mandatory-only filtered progress view (e.g., "60% through Mandatory") — out of TASK-011 scope; future task consumes this ADR's accessor.
- Cross-Chapter aggregation surfaces ("you have completed N of M total Sections") — out of scope; future task.
- Completion timestamps surfaced in UI — `completed_at` is still persisted (ADR-024) but not displayed.
- Per-Chapter detail page (e.g., `/progress/{chapter_id}`) — out of scope; rail decoration is sufficient.
- Quiz-related progress integration — out of scope; manifest §7 separates completion from the reinforcement loop; Quiz-bootstrap will introduce its own surfaces.
- Orphan/renumber resolution mechanism — deferred to a future task (likely Quiz-bootstrap).
- Specific font-size, color, or weight values for the progress decoration — implementer-tunable.

## Alternatives considered

**A. Per-Chapter call-in-loop using the existing `list_complete_section_ids_for_chapter(chapter_id)` accessor.**

Rejected. The rail iterates every Chapter on every page render (12 today). Calling `list_complete_section_ids_for_chapter(chapter_id)` 12 times per page render is 12 SQL queries where 1 would suffice. Each call fetches the full ID set just to discard it after taking `len()`. The bulk accessor (`SELECT chapter_id, COUNT(*) FROM section_completions GROUP BY chapter_id`) is one indexed query and returns exactly the data the rail needs. At single-user, single-process scale the absolute cost difference is sub-millisecond, but the bulk accessor is also the **canonical derivation home** — future Mandatory-only progress, "X% complete" badges, and Quiz-bootstrap's per-Chapter Quiz integration all consume this same shape. Choosing the per-Chapter call-in-loop would force every future consumer to either repeat the inefficiency or add the bulk accessor later anyway.

**B. Persist Chapter-level counts in a separate `chapter_progress` table that is updated by the completion route handlers.**

Rejected. Manifest §7 is explicit: **"Chapter-level progress is derived from Section state."** Persisting a Chapter-level counter would be a separately-stored derived value — exactly the shape the manifest forbids. The bulk accessor derives at query time from the canonical Section-level state; no Chapter-level row ever exists. A schema-level Chapter counter would also force every `mark_section_complete` / `unmark_section_complete` call to update two rows transactionally — a complexity tier this ADR does not need (the derivation is sub-millisecond).

**C. Display surface: per-Chapter detail page at `/progress/{chapter_id}` showing per-Section status.**

Rejected. Forces a navigation round-trip (rail link → detail page → back to Lecture). The rail already iterates every Chapter; the per-Chapter "X / Y" decoration is the minimum-scope surface that satisfies manifest §7's derived-display invariant. A per-Chapter detail page is a future enhancement (and possibly the right home for orphan/renumber resolution UI) but not the minimum scope.

**D. Display surface: header badge on each Lecture page showing the current Chapter's progress.**

Rejected. A header badge is visible only at the top of the Lecture page; on a 30-screen Chapter (per the `notes-surface-placement-visibility` issue's empirical measurements), the badge is far above the reading position for most of the user's time on the page. The rail is sticky and visible from any scroll position; the rail decoration covers the use case the badge would address, plus shows progress for **all** Chapters at once (not just the current one).

**E. Visual shape: progress bar (e.g., a small `<progress>` element or a CSS-styled fill bar).**

Rejected. The rail is `minmax(220px, 18rem)` wide. A progress bar wide enough to be readable competes with the chapter label for horizontal space; a bar narrow enough to fit is too small to be useful. Plain text fits within the existing line-height and is unambiguous. A bar also requires deciding the bar's color across states (incomplete vs partial vs complete), forcing more CSS commitments than the plain-text shape needs.

**F. Visual shape: percent ("43%") instead of "X / Y."**

Rejected. The percent obscures the underlying count. For a study tool where Section counts vary from ~3 to ~10, "3 / 7" tells the learner more than "43%" — the denominator itself is meaningful information ("this Chapter has 7 Sections to read"). The percent shape also makes the empty-state ("0%") and the just-started state ("14%") visually similar; the integer-count shape distinguishes them clearly.

**G. Visual shape: checkmark glyph ("✓") for full state; "X / Y" for partial; nothing for empty.**

Considered. Hiding the empty-state decoration entirely would clean up the rail's visual density at the cost of removing useful denominator information. Substituting "✓" for "Y / Y" introduces special-case handling (the CSS / template knows about three states instead of one). Plain "X / Y" across all states is simpler, more honest, and the full-state CSS modifier class can carry whatever distinct treatment the implementer chooses (bolder weight, green tint) without a glyph. The minor refactor cost of moving to a glyph-based shape later is bounded.

**H. Empty-state: hide the decoration when X == 0 (Chapter not yet started).**

Considered. Hiding "0 / 7" would reduce visual clutter on day one when no Section is complete. Rejected because the denominator itself is useful information — a learner glancing at the rail learns "Chapter 3 has 7 Sections" without opening it. The rail's `.nav-chapter-progress` element is small and visually subordinate; the cost of always rendering it is negligible.

**I. Total-Sections denominator: re-invoke `extract_sections()` 12 times per page render at rail-build time, without caching or extending `discover_chapters()`.**

Rejected. Each `extract_sections()` call reads the `.tex` file from disk and runs the LaTeX parser. At 12 Chapters × ~100 KB per file × per-page-render frequency, this is wasted I/O. Extending `discover_chapters()` (which already opens each file once for `\title{...}` extraction) is the natural amortization — the file is read once per page render either way; the parser runs against the in-memory string.

**J. Total-Sections denominator: cache per-Chapter Section counts in module-level state, invalidated by file-mtime check.**

Considered. Caching would amortize the parser cost across page renders. Rejected as premature: the per-page-render cost of running `extract_sections()` 12 times against in-memory strings is sub-second at the current corpus size; caching adds a state-management story (when does the cache invalidate? what happens during dev `--reload`?) for a problem that isn't observed. ADR-007 already chose request-time scan over startup cache for the same reason; the principle holds here. If page-render latency ever becomes observable, a future ADR can add the cache.

**K. Chapter-progress derivation home: introduce a new `app/progress.py` module that owns both the bulk accessor and the denominator query.**

Considered. A dedicated module would isolate the derivation logic. Rejected because (a) the bulk accessor naturally belongs in `app/persistence/section_completions.py` (it's a SQL query on the `section_completions` table, and ADR-022 commits to per-entity persistence modules); (b) the denominator query naturally belongs in `app/discovery.py` (it's an extension of the existing per-Chapter file-walk); (c) introducing a third module solely to compose two existing modules' outputs is over-decomposition at this scope. The route handler is the natural composition point. If the derivation grows substantially (e.g., Mandatory-only filtering, time-range queries, cross-entity composition with Quiz-bootstrap), a dedicated module becomes warranted; that is a future ADR.

**L. Display: separate "Chapter progress" table on the landing page (`GET /`), in addition to or instead of the rail decoration.**

Rejected as redundant with the rail. The landing page already shows the rail; a separate table would duplicate the same information in a less-scannable shape. The rail decoration is sufficient for the minimum scope; if a richer per-Chapter overview is later wanted, a per-Chapter detail page is the right shape (Alternative C, deferred).

**M. Schema-level Chapter total: store the per-Chapter Section count in a new `chapters` table updated on file change.**

Rejected. Sections are filesystem-derived (ADR-001, ADR-002); persisting a derived count would create a second source of truth that drifts whenever the source `.tex` is edited (manifest §6: source is edited outside the application). The parser is the single source of truth for the Section count; the cost of running it is negligible. ADR-022 explicitly chose not to persist Chapter metadata for this exact reason ("Chapters are a filesystem-derived concept (ADR-001, ADR-007), not a persisted entity").

**N. Orphan-row UI: surface orphan completion rows in the rail or in a dedicated "stale completions" view, prompting the user to clean up.**

Rejected for this task. The orphan/renumber problem is a real architectural question but not the minimum scope of TASK-011. Surfacing it in the UI without a resolution mechanism would add a "broken state" affordance with no user remedy. The template-level clamp (cap displayed numerator at the denominator) is the minimum-viable defensive measure for now; the orphan-resolution UI is a future task (likely paired with Quiz-bootstrap, which has the same problem at higher cost).

## My recommendation vs the user's apparent preference

The TASK-011 task file forecasts the architect's choice for the persistence accessor as **"option (2): new bulk accessor `count_complete_sections_per_chapter() -> dict[str, int]` (one SQL call: `SELECT chapter_id, COUNT(*) FROM section_completions GROUP BY chapter_id`)"** with the explicit annotation **"Forecast: (2) for cleanliness."** This ADR aligns with that forecast and adopts the proposed function name verbatim.

For the **visual shape**, the task lists candidates ("X / Y" plain text; progress bar; percent; checkmark for full + count for partial) and says "Architect picks." This ADR commits to **plain "X / Y" text** with rationale (Alternatives E, F, G). If the human prefers a progress bar or a percent, this is the place to push back at the gate.

For the **total-Sections denominator source**, the task names the question and forecasts neither answer. This ADR commits to **extending `discover_chapters()`** with rationale (Alternative I, J rejection). If the human prefers a per-Chapter cache or a separate dedicated function, this is the place to push back.

For the **chapter-progress derivation home**, the task forecasts: **"yes — the new accessor (or the rail-context-build helper) is the canonical 'derive Chapter progress from Section state' code path going forward."** This ADR aligns and explicitly names the bulk accessor + extended `discover_chapters()` as the canonical code path that future consumers consume.

One area of mild push beyond the task's forecast: the task does not enumerate the **orphan/renumber problem** as a decision, but the task's "Architectural concerns" section does flag it as a known limitation to acknowledge. This ADR commits to a **template-level clamp** (cap displayed numerator at the denominator) as the minimum-viable defensive measure, with the broader resolution explicitly deferred to a future task. The architect's read is that the clamp is necessary to prevent visually-wrong "8 / 7" decorations after content changes; the clamp itself does not foreclose any future resolution mechanism. If the human prefers no clamp (let the wrong value surface as a "this needs attention" signal), this is the place to push back.

A second area of mild push: this ADR introduces **a new `label_status` value `"section_extraction_failed"`** for the per-Chapter row degradation case (Chapter parse fails entirely). The architect's read is that this is a small, additive extension to ADR-007's existing degradation contract, consistent with ADR-007's "fail-loudly per row" principle. It does not require a supersedure of ADR-007 because the existing literal type can be widened. If the reviewer or the human reads this as a substantive change to ADR-007 worthy of its own supersedure, that supersedure would be a 1-line change and bounded.

I am NOT pushing back on:

- The single-user posture (manifest §5 / §6 / §7) — honored: no `user_id` in the new accessor.
- The read-only Lecture source rule (manifest §6, MC-6) — honored: the accessor reads `data/notes.db`; the denominator reads `content/latex/` for read only.
- The persistence-boundary rule (MC-10, active per ADR-022) — honored: the new accessor's SQL lives only in `app/persistence/section_completions.py`.
- The Mandatory/Optional honored-everywhere absolute (manifest §6, MC-3) — preserved by construction: the rail's existing designation grouping is unchanged; the per-Chapter progress decoration appears within each row regardless of designation.
- ADR-006 (navigation surface) — preserved: the rail's structure is unchanged; the decoration is additive within the existing `nav-chapter-item` row.
- ADR-007 (Chapter discovery) — extended additively: `ChapterEntry` gains a `section_count` field; `label_status` literal gains one new value (`"section_extraction_failed"`).
- ADR-008 (CSS architecture) — extended faithfully: new `.nav-chapter-progress` classes go in `base.css` per the prefix convention.
- Manifest §7 second-half invariant — directly anchored in code by this ADR's bulk accessor + extended `discover_chapters()` shape.

## Manifest reading

Read as binding for this decision:

- **§3 Primary Objective.** Drive consumption + retention. Per-Chapter progress is a consumption-tracking primitive that gives the learner a visible "this is how far I have gotten" affordance, supporting retention by making un-completed Sections discoverable from any scroll position.
- **§5 Non-Goals.** "No LMS / no gradebook export" bounds the scope: progress is internal-only, not export. "No multi-user" bounds the schema and accessor (no `user_id`). "No mobile-first" bounds the responsive obligation (the rail decoration is desktop-tuned).
- **§6 Behaviors and Absolutes.** "Single-user" honored. "Lecture source read-only" honored (the bulk accessor reads `data/notes.db`; the denominator reads `content/latex/` for read only). "Mandatory and Optional honored everywhere" — the rail's existing designation grouping is unchanged; the decoration appears within each row regardless of designation, naturally inheriting the M/O split.
- **§7 Invariants.** **"Completion state lives at the Section level. Chapter-level progress is derived from Section state."** — directly motivates this ADR. The bulk accessor derives at query time from the canonical Section-level state; no Chapter-level row is persisted; the manifest's second-half invariant has a single named code path. **"Mandatory and Optional are separable in every learner-facing surface."** — preserved by construction; the rail already exposes the split structurally.
- **§8 Glossary.** Chapter is the parent of Sections; Sections are the atomic unit for completion. The decoration's denominator (Y) is the count of discovered Sections per Chapter; the numerator (X) is the count of complete Sections per Chapter. The decoration is per-Chapter (the rail's natural row granularity), derived from Section state (the manifest's commitment).

No manifest entries flagged as architecture-in-disguise.

## Conformance check

- **MC-1 (No direct LLM/agent SDK use).** Orthogonal — no AI in this surface.
- **MC-2 (Quizzes scope to exactly one Section).** Orthogonal — no Quiz entity. The accessor's per-Chapter aggregation does not violate per-Section Quiz scoping (Quiz-bootstrap will introduce its own per-Section accessors).
- **MC-3 (Mandatory/Optional designation respects the canonical mapping).** Preserved by construction. The rail's existing M/O grouping (per ADR-006/ADR-007) is unchanged; the decoration appears within each row regardless of designation. Future Mandatory-only progress views consume the same accessor + the existing `chapter_designation()` (ADR-004); no hardcoded chapter-number rules; no per-Chapter override.
- **MC-4 (AI work asynchronous).** Orthogonal — no AI in this surface.
- **MC-5 (AI failures surfaced).** Orthogonal — no AI.
- **MC-6 (Lecture source read-only).** Honored. The bulk accessor writes nothing; the denominator extension reads `content/latex/` for read only (the same files `discover_chapters()` already reads). No new write paths.
- **MC-7 (Single user).** Honored. The new accessor's SQL has no `user_id` predicate; the function signature has no per-user argument; the GROUP BY produces a global-per-Chapter aggregation.
- **MC-8 (Reinforcement loop preserved).** Orthogonal — no Quiz machinery.
- **MC-9 (Quiz generation user-triggered).** Orthogonal.
- **MC-10 (Persistence boundary).** Honored. The new accessor's SQL string literal lives in `app/persistence/section_completions.py`; route handlers and templates do not import `sqlite3` and do not contain SQL. The grep target ADR-022 committed to remains zero matches.
- **UI-1 / UI-2 / UI-3 (ui-task-scope).** UI-1 satisfied at the task level (TASK-011 declares the rail-decoration UI surface). UI-2 satisfied by this ADR (the styling target — `app/static/base.css` — is named; the class-name namespace `.nav-chapter-progress` is committed). UI-3 satisfied by the diff naming `app/static/base.css` (modified) and listing the rules added.
- **UI-4 (rendered-behavior verification gate).** Honored. ADR-010's Playwright harness covers the rail rendering and per-Chapter progress visibility.

Previously-dormant rule activated by this ADR: none new. (MC-7 architecture portion and MC-10 architecture portion are already active per ADR-022; this ADR consumes both.)

## Consequences

**Becomes possible:**

- A learner can see, at any scroll position on any Lecture page, how many Sections of every Chapter they have completed.
- The manifest §7 second-half invariant ("Chapter-level progress is derived from Section state") has a single named code path: `count_complete_sections_per_chapter()` + extended `discover_chapters()`. Future consumers consume this path.
- Future Mandatory-only filtered progress views consume the same accessor + the existing designation function — no new derivation needed.
- Future Quiz-bootstrap per-Chapter Quiz status consumes the same accessor for the "Sections complete vs Sections quizzed" comparison.
- Adding a new Section to a Chapter's source `.tex` is immediately reflected in the rail's denominator on the next page render (no schema change, no migration).
- Marking a Section complete is immediately reflected in the rail's numerator on the next page render (the persistence write is committed before the PRG redirect; the GET re-reads the bulk accessor).

**Becomes more expensive:**

- Every page render performs one additional SQL query (`count_complete_sections_per_chapter()`). Mitigation: the indexed `chapter_id` GROUP BY is sub-millisecond; the cost is below the noise floor of the existing per-render work.
- Every page render performs one additional `extract_sections()` call per Chapter (12 calls per page) inside `discover_chapters()`. Mitigation: each call runs against the in-memory `.tex` text already read for `\title{...}` extraction; total cost is small (~tens of milliseconds at current corpus size). If page-render latency becomes observable, a future ADR can add a per-mtime cache.
- `app/discovery.py` now has a dependency on `app/parser.py` (it must call `extract_sections()`). Mitigation: the import is one-way (`discovery` imports `parser`); no circular dependency.
- `app/persistence/__init__.py` now exports one additional name (`count_complete_sections_per_chapter`). Mitigation: the public API surface remains small; the alternative (deep imports) would compromise the single-import-surface convention.
- The `ChapterEntry` shape gains a `section_count: int` field. Mitigation: the field is additive; existing template code that does not reference it is unchanged.
- Existing tests that asserted the old `ChapterEntry` shape may need updates to accommodate the new field. Mitigation: per the user-memory entry "Test updates forced by Accepted ADRs are routine," the test-writer amends affected assertions as this ADR becomes Accepted.

**Becomes impossible (under this ADR):**

- A Chapter-level completion counter persisted as a separate row. Forbidden by manifest §7 ("derived from Section state").
- A rail decoration that does not respect the Mandatory/Optional grouping. The decoration appears within each row; the grouping is preserved by construction.
- A per-Chapter progress display that uses a derivation other than the named code path (`count_complete_sections_per_chapter()` + `discover_chapters().section_count`). Future consumers consume the canonical path.

**Future surfaces this ADR pre-positions:**

- Mandatory-only filtered progress view ("you are 60% through Mandatory") — consumes `count_complete_sections_per_chapter()` + `chapter_designation()` (ADR-004); aggregates across Mandatory chapters.
- Cross-Chapter aggregate ("N of M total Mandatory Sections complete") — same composition.
- Completion-history surfacing ("Sections completed this week") — consumes the existing `completed_at` column (ADR-024) via a new accessor; the bulk-count accessor remains the per-Chapter aggregation.
- Quiz-bootstrap per-Chapter Quiz status — consumes the bulk-count accessor for the "Sections complete vs Sections quizzed" comparison; no new derivation needed.
- Per-Chapter detail page (e.g., `/progress/{chapter_id}`) — natural home for orphan/renumber resolution UI; consumes the bulk-count accessor + the per-Section ID accessor.

**Known limitations (recorded explicitly):**

- **Orphan/renumber problem.** If a Chapter's source `.tex` removes or renumbers Sections, the persisted completion rows for the now-absent Section IDs become orphans. The bulk accessor will count them in the per-Chapter total, producing a numerator that exceeds the parser-derived denominator. Mitigation: template-level clamp (cap displayed numerator at the denominator). Resolution: deferred to a future task (likely Quiz-bootstrap or a dedicated content-change-reconciliation task), where Quiz Attempt rows have the same problem at higher cost.
- **No rail-resident "you are here" indicator.** The decoration shows progress for every Chapter, but does not visually distinguish the currently-rendered Chapter. This is intentional — manifest §3's primary-objective focus is consumption + retention, not navigation; the existing `<a>` link's hover state is sufficient for navigation. A future task may add a "current Chapter" highlight if a user-research signal warrants it.

**Supersedure path if this proves wrong:**

- If the rail decoration proves visually noisy or insufficient → a future ADR moves the surface (per-Chapter detail page, header badge, or both) or refines the visual shape (progress bar, percent, glyph). Cost: template + CSS edit; bounded.
- If the bulk accessor's GROUP BY proves slow at scale → a future ADR adds a covering index or moves to an in-memory cache. The accessor's signature is preserved; only the implementation changes.
- If the orphan/renumber problem becomes acute → a future ADR introduces a content-change-reconciliation mechanism. The bulk accessor is consumed unchanged; the new mechanism wraps it.
- If extending `discover_chapters()` with `section_count` proves to over-couple discovery to the parser → a future ADR introduces a separate `chapter_section_counts()` helper that the rail-context-build composes alongside `discover_chapters()`. The composition shape changes; the data flow does not.

## Test-writer pre-flag

Per the user-memory entry "Test updates forced by Accepted ADRs are routine," the following test changes are anticipated when this ADR becomes Accepted (the test-writer amends them as routine ADR-driven test evolution; not a PUSHBACK target):

- Tests that assert `ChapterEntry` has only the existing 5 fields will need updates to accommodate the new `section_count` field.
- Tests that assert the rail's HTML structure may need updates to accommodate the new `<span class="nav-chapter-progress">` element per row.
- New Playwright tests assert the per-Chapter progress decoration appears in the rail on both the landing page and Lecture pages, and that marking a Section complete updates the count after reload (per TASK-011's AC for the new surface).
