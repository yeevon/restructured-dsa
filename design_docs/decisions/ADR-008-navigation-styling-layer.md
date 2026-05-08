# ADR-008: Navigation styling layer — split into `app/static/base.css` (page chrome + rail) and reuse the existing `app/static/lecture.css` (Lecture body), with M/O reusing the established designation palette and CSS Grid for the page layout

**Status:** `Accepted`
**Date:** 2026-05-08
**Task:** TASK-003
**Resolves:** `design_docs/project_issues/adr006-rail-half-implemented-no-css.md`
**Supersedes:** none

**Human gate (2026-05-08):** Accepted. Human ratified Path 2 ("we can go with path 2 its reasonable"). The architect's mild push against the orchestrator-read Path 1 recommendation stands.

## Context

ADR-006 fixed the navigation surface mechanism (`GET /` landing page + a left-hand rail included in every Lecture page via a shared `base.html.j2`, both surfaces fed by a single `discover_chapters()` helper). ADR-006 explicitly excluded "CSS / visual treatment of the rail and the landing page" from its Decision section, classifying styling as "implementation choice; not architecture." `/implement TASK-002` then added the structural class names to the templates (`.lecture-rail`, `.nav-rail-inner`, `.nav-section-label`, `.nav-chapter-list`, `.nav-chapter-item`, `.nav-chapter-error`, `.nav-chapter-empty`, `.page-layout`, `.page-main`) but added no corresponding CSS rules. The 158-test suite passed (every test asserts against HTML structure), but in a real desktop browser the page renders as an unstyled wall of text.

`design_docs/project_issues/adr006-rail-half-implemented-no-css.md` (Open since 2026-05-08) re-classifies the styling decision: in retrospect it was *not* a pure implementation choice because (a) the choice of which CSS file holds the rules, (b) the class-name namespace, and (c) whether existing CSS is sufficient are all decisions an implementer cannot make consistently without an architectural anchor — and the absence of that anchor is exactly what shipped a half-implementation. The `ui-task-scope` skill (UI-2) now requires an ADR to scope CSS for any UI surface; this ADR is the first instance under that rule.

The project_issue enumerates three resolution paths: (1) amend ADR-006 to scope CSS via the `authority-state-check` AS-1 amendment cycle (Accepted → Proposed → re-Accept), (2) draft a new ADR (this one) dedicated to the styling layer, citing ADR-006 as the mechanism it styles, (3) ship unstyled (rejected by TASK-003's framing per manifest §3 / UI-1 / UI-3). The project_issue's orchestrator-read recommendation favored Path 1; this ADR takes Path 2 and explains the disagreement under "My recommendation vs the user's apparent preference" below.

The relevant existing assets:
- `app/static/lecture.css` — present, ~175 lines, owns Lecture-body styling: typography, designation badge (`.designation-mandatory` and `.designation-optional` palette), section headings, callouts (`.callout-ideabox`, `.callout-defnbox`, `.callout-notebox`, `.callout-warnbox`, `.callout-examplebox`), `<pre>` code blocks, lists, tables, math. Contains zero rules for any rail / landing-page / page-layout class name.
- `app/templates/base.html.j2` — owns page chrome: `<html>`, `<head>`, MathJax script, the `<nav class="lecture-rail">` region, the `<main class="page-main">` region wrapped in `<div class="page-layout">`. Loads `/static/lecture.css` via a single `<link rel="stylesheet">`.
- `app/templates/_nav_rail.html.j2` — the rail partial. Renders two `.nav-section-label` headings ("Mandatory" and "Optional"), each followed by a `.nav-chapter-list` `<ul>` containing `.nav-chapter-item` `<li>` rows or a `.nav-chapter-empty` `<li>` "(none)" row. Per-row degradation under ADR-007 adds the `.nav-chapter-error` class to `<li>` for any Chapter with `label_status != "ok"`.
- `app/templates/index.html.j2` — extends `base.html.j2`. Adds an `.index-header` / `.index-title` / `.index-subtitle` block. None of these three class names have CSS rules either; they are part of the same half-implementation.
- `app/templates/lecture.html.j2` — extends `base.html.j2`. Existing class names (`.lecture-header`, `.lecture-title`, `.designation-badge`, `.designation-mandatory`, `.designation-optional`, `.section-heading`) are styled by `lecture.css` and must remain styled by it (TASK-003 must not regress TASK-001's visual treatment).

The manifest constrains this decision through §3 (consumption — an unstyled wall of text is a worse consumption surface than the curl-style Lecture page TASK-001 shipped), §6 ("Mandatory and Optional content are honored everywhere" — visible distinction matters when both designations are surfaced), §7 ("Mandatory and Optional are separable in every learner-facing surface" — the rail's split must be visually parseable, not just present in the DOM), and §5 (no mobile-first, no remote deployment, no LMS — bounds the styling ceiling to "usable on a desktop browser").

## Decision

### CSS file split — `base.css` for page chrome + rail; `lecture.css` for Lecture body content

A new file `app/static/base.css` is introduced. It owns CSS for everything `base.html.j2` and `_nav_rail.html.j2` and `index.html.j2` introduce: the page-level layout (`.page-layout`, `.page-main`), the rail (`.lecture-rail`, `.nav-rail-inner`, `.nav-section-label`, `.nav-chapter-list`, `.nav-chapter-item`, `.nav-chapter-error`, `.nav-chapter-empty`), and the landing page chrome (`.index-header`, `.index-title`, `.index-subtitle`). It also owns the `body`-level reset/baseline that needs to live higher in the cascade than the Lecture-specific styling (because `lecture.css` currently sets `body { max-width: 860px; margin: 0 auto; padding: 0 1rem 2rem }` — a constraint that no longer holds once the page is a two-column layout).

The existing `app/static/lecture.css` file is preserved but **scoped down**: rules that pertain to the Lecture body (`.lecture-header`, `.lecture-title`, `.designation-badge` and its `-mandatory`/`-optional` variants, `.section-heading`, `h3`, `h4`, callouts, `<pre>`, `code`, lists, tables, math classes) stay where they are. The `body { ... }` block in `lecture.css` is removed; its baseline typography and color rules move to `base.css`'s `body { ... }` block. The `body { max-width: 860px; ... }` page-width constraint is removed entirely (the two-column layout in `base.css` replaces it), but the same effective max-width on the Lecture body content is reasserted via `.page-main` in `base.css` so TASK-001's reading-width discipline is preserved.

`base.html.j2` loads both stylesheets in order:

```html
<link rel="stylesheet" href="/static/base.css">
<link rel="stylesheet" href="/static/lecture.css">
```

`base.css` first (sets up the page-level layout and the rail). `lecture.css` second (specifies the Lecture body content within `.page-main`). Neither file uses `@import`; both are flat CSS files served as static assets per ADR-003.

The two files are intentionally **non-overlapping** by class-name prefix:

- `base.css` owns: `.page-layout`, `.page-main`, `.lecture-rail`, `.nav-*`, `.index-*`, plus the `body`-level baseline.
- `lecture.css` owns: `.lecture-header`, `.lecture-title`, `.designation-badge`, `.designation-*`, `.section-heading`, `.callout`, `.callout-*`, plus element selectors that affect Lecture-body content (`pre`, `code`, `p code`, `ul`, `ol`, `li`, `table`, `td`, `th`, `.math*`, `h3`, `h4`).

The `.lecture-rail` class — currently used as the `<nav>` wrapper — moves conceptually into the "page chrome" namespace under `base.css`. Its name is preserved (no template rename) because TASK-002's tests assert against it; renaming would force a test churn unrelated to this task.

### Class-name namespace — preserve every name TASK-002 shipped; do not rename

The class names already in the templates (`.page-layout`, `.page-main`, `.lecture-rail`, `.nav-rail-inner`, `.nav-section-label`, `.nav-chapter-list`, `.nav-chapter-item`, `.nav-chapter-error`, `.nav-chapter-empty`, `.index-header`, `.index-title`, `.index-subtitle`) are the namespace this ADR commits to. No template renames; no class additions beyond what is structurally needed. Adding rules for these existing classes is the entire CSS deliverable.

The implementer may add a small number of utility / pseudo-state classes if needed (e.g., `.nav-chapter-item:hover`, `.nav-chapter-item a:focus`) — those are CSS pseudo-class selectors on existing classes, not new template classes.

### Mandatory / Optional visual treatment — reuse the established designation palette from `lecture.css`

The Lecture page already encodes the M/O distinction via the `.designation-mandatory` (greenish: `#d4ecd4` background, `#2a5a2a` text, `#9db89b` border) and `.designation-optional` (bluish: `#e8eef5` background, `#2a3a5a` text, `#9fb4cd` border) palette. The rail's "Mandatory" and "Optional" `<h2 class="nav-section-label">` headings reuse the same hues so the human's mental association ("green = Mandatory, blue = Optional") is consistent across surfaces.

Concretely:

- The first `.nav-section-label` (rendered with text "Mandatory") gets a green left-border or text accent matching the `designation-mandatory` palette.
- The second `.nav-section-label` (rendered with text "Optional") gets a blue left-border or text accent matching the `designation-optional` palette.
- Implementation note for the implementer: because the template renders both labels with the same class name, the distinction is achieved by either (i) a `.nav-section-label:nth-of-type(1)` / `:nth-of-type(2)` selector, or (ii) addition of a `data-designation="Mandatory"` / `data-designation="Optional"` attribute to each label (an attribute, not a class name — preserves the "no template renames" promise above) and an attribute selector in CSS. Either is acceptable; the implementer chooses. The architectural commitment is to the palette reuse, not to the selector mechanism.

This commitment is binding: a new rail-specific palette is **rejected** because it would force the human to maintain two color systems for the same M/O distinction, and divergence is the predictable failure mode (one surface revises a hue, the other does not, and the M/O association degrades).

### Per-row error treatment — visually distinct via `.nav-chapter-error` rule

The `.nav-chapter-error` class is added to any rail row whose `label_status != "ok"` (per ADR-007's per-row fail-loudly rule). The CSS rule for `.nav-chapter-error` makes the row visually distinct from healthy rows via:

- A warning-colored left-border (matching `lecture.css`'s `.callout-warnbox` palette: `#cfae87` border, `#f5eddf` background tint applied to the row) so the visual language is consistent with the existing project warning treatment.
- The link inside the row remains clickable (per ADR-007: clicking surfaces the rendering failure under ADR-003's existing contract — fail-loudly all the way down). The row is *visually degraded*, not disabled.

### Empty-state treatment — `.nav-chapter-empty` styled as muted

The `.nav-chapter-empty` "(none)" row is rendered in a muted color (lower contrast than healthy rows) and italicized so the structural emptiness is communicated without competing for visual attention. This is a stylistic commitment, not a content commitment — the rendered text "(none)" is set by the template (ADR-006's data flow), not by this ADR.

### Page layout mechanism — CSS Grid

The two-column layout (`.page-layout` containing `.lecture-rail` and `.page-main`) is implemented with CSS Grid:

```css
.page-layout {
  display: grid;
  grid-template-columns: minmax(220px, 18rem) minmax(0, 1fr);
  min-height: 100vh;
}
```

Rationale (as opposed to flexbox or floats):

- Grid expresses "fixed-ish sidebar + flexible main column" more directly than flexbox (`flex: 0 0 18rem` / `flex: 1`); the constraint is on the *track*, not on the *children*.
- `minmax(0, 1fr)` for the main column prevents a wide `<pre>` block in the Lecture body from forcing the rail to overflow — a known flexbox failure mode.
- The Lecture body's existing `max-width: 860px` is preserved by setting it on `.page-main`'s inner content (or by repositioning that constraint into `lecture.css` under a `.page-main .lecture { max-width: ... }` selector).
- Grid has no responsive obligation under this ADR (manifest §5 — no mobile-first). On a narrow desktop viewport the rail simply scrolls horizontally with the page; future widening to "rail collapses below a breakpoint" is a follow-up that this ADR does not commit to.

### Scope of this ADR

This ADR fixes only:

1. The CSS file architecture (`base.css` + `lecture.css`, non-overlapping by class-name prefix).
2. The class-name namespace (preserved as-shipped by TASK-002; no template renames).
3. The M/O visual treatment principle (reuse the designation palette; no rail-specific palette).
4. The error and empty-state visual principles (warning-palette degradation; muted empty state).
5. The page-layout mechanism (CSS Grid).

This ADR does **not** decide:

- Specific pixel values for the rail width beyond the `minmax(220px, 18rem)` track. The implementer may tune within reason.
- Hover/focus animation timing / easing — pure visual tuning, not architecture.
- Whether the rail collapses on narrow viewports (manifest §5: no mobile-first).
- A CSS preprocessor, build step, or bundler. The project's "small local FastAPI + flat static CSS" shape (ADR-003) is preserved.
- A CSS linter (Stylelint, etc.). The project has no lint commitment for any language yet (CLAUDE.md `Lint:` is a placeholder); this ADR does not introduce one.

## Alternatives considered

**A. Path 1 from the project_issue: amend ADR-006 to scope CSS via the AS-1 cycle (Accepted → Proposed → re-Accept).**
Considered. The project_issue's orchestrator-read recommendation favored this path on the rationale that ADR-006 should be a complete record of the navigation Decision. Rejected because:
- The styling layer is genuinely separable from the navigation mechanism. The rail's mechanism (one helper, one base template, two surfaces, no two-source-of-truth risk) is unchanged by any decision this ADR makes. Bundling the styling decision into ADR-006 would imply they are coupled when they are not, and would set the precedent that every future rendering ADR must include its styling — which the project does not want (Notes UI styling, Quiz UI styling, Notification chrome styling each have their own visual concerns and may want their own ADRs that compose against ADR-008 rather than amending ADR-006 again and again).
- The AS-1 amendment cycle creates an interim window where ADR-006 reads as `Status: Proposed` while its underlying mechanism decision is settled and shipped. That state is misleading: a reader during the window would correctly conclude "the navigation mechanism is currently un-Accepted" when in fact only the styling addendum is awaiting gate. Path 2 keeps ADR-006 untouched (its mechanism decision is correct and Accepted; its silence on styling is not a defect in *that* decision, it's the absence of a *separate* decision).
- The `architecture.md` row mechanics under Path 1 are awkward (the project_issue's own "Architectural concerns" section calls this out: does the row stay in Accepted or move to Proposed during the amendment? Either answer creates a false drift signal). Under Path 2, the mechanics are clean: ADR-006 stays in Accepted, ADR-008 enters Proposed, ADR-008 moves to Accepted on the human gate.
- Path 2 mirrors how the project has already separated decisions that *could* have been bundled. ADR-001 (source layout) + ADR-003 (rendering pipeline) are separable for the same reason: source layout is not the rendering pipeline, even though no rendering is possible without source. ADR-006 (navigation mechanism) + ADR-008 (navigation styling) follow the same pattern.

**B. Extend the existing `app/static/lecture.css` with rail and landing-page rules; do not introduce a new CSS file.**
Rejected. The project_issue named "(a) extend `lecture.css`" as one of the three CSS-file options. It would minimize file count but conflate two namespaces (Lecture-body content vs. page chrome) in one file, making it harder to reason about which rules affect which surface. As soon as the project adds a third surface (Notes UI, for example), `lecture.css` becomes a misnomer for "the file that styles things that are not lectures." Splitting now is the cheapest moment to do it.

**C. Introduce a new file (`nav.css` or `rail.css`) loaded alongside `lecture.css` from `base.html.j2`, scoped narrowly to the rail.**
Rejected. The class names that need rules include `.page-layout` and `.page-main` (the page-level grid) which are not "navigation" — they are page chrome. A `nav.css` named for the rail would either need to also own page-layout rules (in which case the name lies) or leave page-layout rules in `lecture.css` (in which case `lecture.css` ends up owning chrome that is not Lecture-specific). Better to name the file for the layer it owns: `base.css` for everything `base.html.j2` and its includes need, regardless of whether a particular rule pertains specifically to the rail or to the page-level grid.

**D. Split into three files: `base.css` (page chrome), `nav.css` (rail only), `lecture.css` (Lecture body).**
Rejected as over-decomposition. Rail and page chrome are tightly coupled (the rail *is* page chrome); splitting them into two files imposes ordering-of-load discipline on the implementer for no compositional benefit. Two files is the right granularity at this scope. A future ADR can split if a third surface (e.g., Notes UI) wants its own page-chrome variation.

**E. Use Flexbox for the page layout instead of Grid.**
Considered as the closest competitor to Grid. Flexbox would express the layout as `<div class="page-layout" style="display: flex">` with `.lecture-rail { flex: 0 0 18rem }` and `.page-main { flex: 1; min-width: 0 }`. Functionally equivalent for the chosen layout. Rejected because Grid expresses the constraint ("first track is sidebar-sized, second track is everything else") on the *container's* track definition rather than on each child's flex parameters — a cleaner separation of concerns when the children semantically are not "items in a row" but "regions of a page." The `min-width: 0` flexbox idiom for preventing main-column overflow is also less obvious than Grid's `minmax(0, 1fr)`; the latter signals intent more directly. Both work; the preference is mild but recorded so the implementer doesn't pick silently.

**F. Use a new rail-specific color palette unrelated to the existing `.designation-mandatory` / `.designation-optional` palette.**
Rejected. Two color systems for the same M/O distinction is a maintenance trap: every future palette refresh must touch both, and divergence is the predictable failure mode. Manifest §6 ("Mandatory and Optional content are honored everywhere") is best honored when the *visual encoding* of the distinction is consistent across surfaces, not just the structural distinction. The existing palette is the single source of M/O visual identity; the rail consumes it.

**G. Make the per-row error treatment a strikethrough on the link text.**
Rejected. Strikethrough communicates "this thing is dead / removed / no longer applicable" — but ADR-007's per-row fail-loudly intent is that the row is *broken* (its label couldn't be extracted), not *removed*. A warning-palette treatment (matching `.callout-warnbox`) more accurately communicates "this is in trouble; click to see what's wrong" while keeping the row visibly active.

**H. Hide the `.nav-chapter-empty` "(none)" row entirely via `display: none`.**
Rejected. The empty-state row is structural information from ADR-006 / ADR-007: a designation group is empty. Hiding it makes the rail's structure context-dependent ("Mandatory has no entries → rail looks shorter") in a way that confuses the human's sense of the rail's stable shape. Muted styling preserves the structural commitment while signaling the emptiness without demanding attention.

## My recommendation vs the user's apparent preference

The project_issue's "Recommendation" section (orchestrator's read; explicitly marked "not binding") favored **Path 1** (amend ADR-006). I am recommending **Path 2** (this ADR). The disagreement is architecturally substantive and worth surfacing:

- **The orchestrator's argument for Path 1:** "It makes ADR-006 a complete record of the navigation Decision and forces the styling target to be named in the same place the mechanism is."
- **My argument for Path 2:** ADR-006's Decision is the navigation *mechanism*, and that decision is correct, complete, and accepted. The styling layer is a separable concern — the same way ADR-001 (source layout) is separable from ADR-003 (rendering pipeline) even though one consumes the other. Bundling styling into ADR-006 would (i) misrepresent the AS-1 amendment cycle's interim state (ADR-006 marked `Proposed` while its core decision is settled and shipped), (ii) set the precedent that every future rendering ADR must own its styling, which is wrong if the project ever wants a styling ADR to compose across surfaces, (iii) produce awkward `architecture.md` row mechanics during the amendment window. ADR-008 leaves ADR-006 untouched and adds a clean new decision in the right granularity.
- **Cost of disagreeing with the orchestrator's read here is small.** The orchestrator's read explicitly says "Path 2 is acceptable if the architect judges that styling will be a recurring separate concern (i.e., a styling-ADR pattern is forming)." I judge that yes — Notes UI, Quiz UI, and Notification chrome will each plausibly want their own visual decisions, and either each amends ADR-006 (and ADR-006 grows into a chrome-ADR-of-everything) or the project develops a styling-ADR pattern starting now. Starting now is cheaper.

The human did not signal a direct preference between Path 1 and Path 2; the project_issue is the only signal, and it explicitly defers to the architect's judgment on this question. So this is a "mild disagreement with an orchestrator-read recommendation," not a pushback against the human's stated direction.

I am NOT pushing back on:
- The need to resolve the project_issue (chosen — this ADR resolves it).
- The rejection of Path 3 (ship unstyled) by TASK-003's framing (chosen — manifest §3 motivates).
- The class names already shipped by TASK-002 (preserved as-is).
- The existing `lecture.css` palette for `.designation-mandatory` / `.designation-optional` (reused, not replaced).
- ADR-006's core navigation mechanism (untouched).

## Manifest reading

Read as binding for this decision:
- §3 Primary Objective ("drive consumption … via per-Chapter Lectures and Notes"). Bound the requirement that the navigation surface is *usable*, not just structurally present. An unstyled wall of text is a worse consumption surface than the curl-style Lecture page TASK-001 shipped; this decision answers that.
- §5 Non-Goals: "No mobile-first product" bounds the responsive obligation to "usable on a desktop browser." "No remote deployment" bounds the entire styling discussion to local-served HTML and flat static CSS (no CDN, no build step, no preprocessor). "No LMS features" bounds the rail to "links to Lectures," not progress dashboards or assignment trackers — the styling reflects this floor.
- §6 Behaviors and Absolutes: "Mandatory and Optional content are honored everywhere." Bound the requirement that *both* surfaces (rail and landing page) render the M/O grouping with a *visible* distinction, not just a structural one. The reused designation palette honors this at the visual layer.
- §7 Invariants: "Mandatory and Optional are separable in every learner-facing surface." Bound the visible-distinction floor; the palette reuse satisfies it.
- §8 Glossary entries for Chapter, Mandatory, Optional. Bound the per-row data model; consumed without modification from ADR-007.

No manifest entries flagged as architecture-in-disguise.

## Conformance check

- **MC-3 (Mandatory/Optional designation respects the canonical mapping).** This ADR consumes the designation classification produced by `chapter_designation()` (ADR-004). No CSS rule encodes a chapter-number threshold or a hardcoded chapter-ID list. The visual M/O distinction is driven entirely by the `nav_groups["Mandatory"]` vs `nav_groups["Optional"]` partition the helper produces. Compliance preserved.
- **MC-6 (Lecture source is read-only to the application).** This ADR adds CSS rules under `app/static/`. No path under `content/latex/` is read or written by CSS work. Compliance preserved.
- **MC-7 (Single user).** No per-user state introduced; CSS is global. Compliance preserved.
- **MC-1 / MC-2 / MC-4 / MC-5 / MC-8 / MC-9 / MC-10.** Not touched (no AI work, no Quiz, no persistence, no DB).
- **UI-1 / UI-2 / UI-3 (ui-task-scope).** UI-1 satisfied at the task level (TASK-003 declares styling responsibility). UI-2 satisfied by this ADR (CSS is scoped: which files, which classes, which palette). UI-3 will be satisfied by the implementer's diff naming `app/static/base.css` (new) and `app/static/lecture.css` (modified) and listing the rules added.
- **UI-4 (rendered-behavior verification gate).** This ADR does not set the verification gate; ADR-009 (proposed in the same `/design TASK-003` pass) sets it. This ADR's compliance with UI-4 is conditional on ADR-009 being Accepted alongside.
- **AS-1 (Accepted ADR content immutability).** ADR-006 is *not* edited by this ADR (Path 2). ADR-006 remains `Accepted`, untouched. AS-1 compliance: trivial.
- **AS-3 (architecture.md mirrors ADR states).** ADR-008 enters the "Proposed ADRs" table on Write; moves to "Accepted ADRs" on the human gate. ADR-006's row is not moved.
- **AS-5 (Project_issue ↔ ADR coherence).** `adr006-rail-half-implemented-no-css.md` is updated to `Status: Resolved by ADR-008` when this ADR is Accepted. Per AS-5, the Open → Resolved-by transition requires ADR-008 to be `Accepted` on disk; until the human gate, the issue stays `Open` and the resolution is `Resolved by ADR-008 (pending acceptance)`. The issue file's edit happens at the same moment as this ADR is written (architect Mode 2 contract); the human gate completes the resolution.

Previously-dormant rule activated by this ADR: none. UI-1/UI-2/UI-3 were already in force (ui-task-scope skill is operational, not architectural — its rules force decisions, they do not become "active" the way MC-6's path grep does).

## Consequences

**Becomes possible:**
- A usable browser experience on `GET /` and on every Lecture page: rail occupies the left, main content occupies the right, Mandatory and Optional are visually distinguishable, links are clickable affordances with hover/focus state.
- TASK-002's parked working tree commits as a complete deliverable.
- Future learner-facing surfaces (Notes UI, Quiz UI, Notification chrome) that extend `base.html.j2` get the page-layout grid and the rail styling for free, plus a clean naming convention (`base.css` for chrome shared across surfaces, per-surface CSS for surface-specific content).
- The rail and the Lecture badge agree on the M/O visual encoding; the human's mental color-association is consistent across surfaces.
- A precedent for future styling decisions: each surface that introduces page chrome lives in `base.css`; each surface that owns content has its own per-surface CSS file.

**Becomes more expensive:**
- One additional static asset to load on every page (`base.css` in addition to `lecture.css`). At local-dev / single-user scope this is trivial; manifest §5 (no remote deployment) means there is no CDN concern. The two files are flat CSS; no build step.
- A small edit to `lecture.css` to remove the `body { ... }` block that conflicts with the new two-column layout. Mitigation: TASK-001's tests pin Lecture-body rendering behavior; the edit is mechanical and the affected rules are isolated.
- Two-file CSS means the implementer has to think about which file a new rule belongs in. Mitigation: the prefix rule (`page-*`, `lecture-rail`, `nav-*`, `index-*` → `base.css`; `.lecture-*`, `.designation-*`, `.callout-*`, `.section-*` → `lecture.css`) is unambiguous for every class name currently in the project.

**Becomes impossible (under this ADR):**
- A rail-specific M/O color palette divorced from the Lecture-page badge palette. Future drift between the two would now require a superseding ADR, which is the right friction.
- A page-layout mechanism that hides the rail on narrow viewports without an ADR amendment. The current rule is "no responsive collapse"; a future "collapse below 720px" would be a future ADR's call.

**Future surfaces this ADR pre-positions:**
- Notes UI (manifest §8) — extends `base.html.j2`, gets the rail and the page grid for free; introduces its own `notes.css` for Note-editor-specific content following the same pattern.
- Quiz UI surfaces (per-Section "Quiz this Section" affordances rendered inside Lecture pages) — already inside `lecture.html.j2`'s `{% block main %}`, styled via additions to `lecture.css` (or a future `quiz.css` if the surface grows enough to warrant its own file).
- Notification surface (manifest §8) — most natural shape is a header/badge inside `base.html.j2`'s chrome region; styling lives in `base.css` because it is page chrome.
- A future Mandatory-only filter view — would adjust `_nav_rail.html.j2` to omit the Optional group; CSS untouched (the rule is on `.nav-section-label` regardless of how many sections render).

**Supersedure path if this proves wrong:**
- If the two-file split proves over-engineered (e.g., rules end up duplicated across both files), a future ADR can collapse them back to one. The cost is bounded (concatenate, reload, re-test).
- If a CSS preprocessor is later introduced (e.g., Sass for variables / nesting), a future ADR commits to it; this ADR's flat-CSS commitment becomes the input to the preprocessor.
- If a UI test framework is later introduced (per UI-4's option 1), a future ADR commits to it; this ADR's CSS architecture is consumed without change.
