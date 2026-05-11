# ADR-025: Section completion UI surface — `POST /lecture/{chapter_id}/sections/{section_number}/complete` with `action` form field, inline affordance next to each `<h2 class="section-heading">`, full-page PRG redirect

**Status:** `Superseded by ADR-027` (§Template-placement only — see ADR-027 for the bottom-of-Section replacement; the route shape, form-handling pattern, validation, round-trip return point, and styling-file ownership from this ADR remain in force)
Original Acceptance: Auto-accepted by /auto on 2026-05-10
**Date:** 2026-05-10
**Task:** TASK-010
**Resolves:** none (no project_issue filed against this question; the surface decision is forced inline by TASK-010)
**Supersedes:** none
**Superseded by:** `ADR-027` (Auto-accepted by /auto on 2026-05-10)

## Context

TASK-010 ships the minimum viable per-Section completion toggle. ADR-024 (Proposed in the same `/design TASK-010` cycle) commits to the persistence shape: a `section_completions` table under `app/persistence/section_completions.py` with presence-as-complete semantics, write-time validation at the route handler. This ADR fixes the **HTTP/template/CSS surface** that consumes that persistence: which route the application exposes for marking and unmarking Sections, where in `lecture.html.j2` the completion affordance lives, what visual state indicator a completed Section carries, and how form submission is handled.

The decision space has materially different alternatives:

- **Route shape:** separate `mark`/`unmark` routes vs single toggle route vs single route with `action` form field; section number in URL path vs URL query vs form body.
- **Form pattern:** synchronous PRG (mirroring ADR-023) vs HTMX partial update vs client-side `fetch()`.
- **Template placement:** inline next to `<h2 class="section-heading">` vs at the end of each section's body vs floating in the right margin vs in a per-Chapter aggregated bar at the top of the page.
- **State indicator shape:** checkbox-shaped affordance vs heading suffix (e.g., "✓ Complete") vs section-level CSS class adding visual treatment vs combinations.
- **Round-trip return point:** PRG to `GET /lecture/{chapter_id}` (top of page) vs PRG to `GET /lecture/{chapter_id}#section-{n-m}` (scroll-anchored to the Section).
- **Validation:** route handler validates Section ID against the parent Chapter's discovered Sections vs trust the URL.

The manifest constrains the decision through §3 (consumption-first — the affordance must be direct, not buried), §5 (no LMS — no progress-export semantics; no mobile-first — desktop browser layout is sufficient; no AI tutor — completion is a manual toggle, not an AI suggestion), §6 (single user — no auth on the route; AI work async — orthogonal here; Mandatory/Optional honored — the affordance must not obscure the existing designation badge; Lecture source read-only — writes go to `data/notes.db`), §7 ("Completion state lives at the Section level" — the affordance is per-Section, not per-Chapter; every completion mark persists — the form actually persists, no client-only state), §8 (Section is "the atomic unit for Quizzes and completion state" — completion is a Section property).

## Decision

### Route shape — `POST /lecture/{chapter_id}/sections/{section_number}/complete` with `action` form field (`mark` or `unmark`)

A single new FastAPI route is introduced:

```
POST /lecture/{chapter_id}/sections/{section_number}/complete
```

Where:

- `{chapter_id}` is the Chapter ID per ADR-002 (e.g., `ch-01-cpp-refresher`) — already a route-typed path parameter in ADR-003/ADR-023's existing `GET /lecture/{chapter_id}` and `POST /lecture/{chapter_id}/notes`.
- `{section_number}` is the Section's number in kebab form (`1-1`, `2-3`, etc.) — **the part after `section-` in the Section ID's fragment per ADR-002**.

The route accepts a form-encoded body with a single field `action` whose value is the literal string `"mark"` or `"unmark"`. On success, the route returns **HTTP 303 See Other** with `Location: /lecture/{chapter_id}#section-{section_number}` — the PRG idiom from ADR-023, with the URL fragment added so the browser scrolls back to the Section the user was just looking at.

**Why this route shape rather than the alternatives:**

- **The Section ID per ADR-002 (`{chapter_id}#section-{n-m}`) is URL-fragment-shaped — the `#` is the path/fragment separator and cannot be a path segment.** Decomposing the Section ID into `{chapter_id}` (path) + `{section_number}` (path) is mandatory, not optional. The route handler composes the full Section ID internally (`section_id = f"{chapter_id}#section-{section_number}"`).
- **A single route with an `action` form field, rather than separate `/mark` and `/unmark` routes**, because the user-visible behavior is a toggle: the same affordance moves a Section in either direction. The form's hidden `action` field carries the intent. Separate routes would force the template to choose which form to render per Section based on current completion state, doubling the form rendering logic. A single route reads the action and dispatches.
- **A single toggle route that flips based on current state** (no `action` field at all) is rejected because the user-visible feedback is then "did my click do what I expected?" — if two clicks happen in fast succession (e.g., a double-click) the resulting state is non-deterministic. Carrying the intent explicitly in the form makes the action idempotent (a `mark` against an already-complete Section is a no-op; an `unmark` against an already-incomplete Section is a no-op) and removes the toggle-race ambiguity.
- **The section number in the URL path (rather than the form body)** mirrors ADR-023's per-Chapter Notes shape, which puts the Chapter in the path. Putting the section number in the path makes the URL self-documenting (`/lecture/ch-01-cpp-refresher/sections/1-1/complete`) and lets the route handler use a typed FastAPI path parameter for validation.

**Routes introduced or modified:**

- **NEW** `POST /lecture/{chapter_id}/sections/{section_number}/complete` — accepts form-encoded `action` (`"mark"` | `"unmark"`); validates `chapter_id` exists and `{chapter_id}#section-{section_number}` is a known Section of that Chapter; persists via the persistence package; returns 303 redirect to `GET /lecture/{chapter_id}#section-{section_number}`.
- **MODIFIED** `GET /lecture/{chapter_id}` (the existing Lecture-page route) — additionally fetches the completed-Section set for the Chapter via `app/persistence.list_complete_section_ids_for_chapter(chapter_id)` and passes it to the `lecture.html.j2` template under a new `complete_section_ids` template variable (a `set[str]` of full Section IDs). No change to the route's contract from the caller's perspective.

**Routes NOT introduced:**

- No `GET /lecture/{chapter_id}/sections/{section_number}` partial route. The completion state lives inline in the Lecture page; there is no addressable URL for "just the completion affordance."
- No `DELETE /lecture/{chapter_id}/sections/{section_number}/complete` REST-style route. The form-encoded `action=unmark` POST is the unmark mechanism; a separate DELETE method would require JS to issue (HTML forms cannot natively send DELETE).
- No JSON API. The route serves form-encoded HTML; no `application/json` content negotiation.
- No batch `POST /lecture/{chapter_id}/sections/complete` route for marking multiple Sections at once. Out of scope; manifest §5 / §7 do not require it.

### Form-handling pattern — synchronous form POST + PRG redirect with URL fragment; no JavaScript

The completion form submits synchronously via the browser's native form handling:

```html
<form class="section-completion-form" method="post"
      action="/lecture/{{ chapter_id }}/sections/{{ section_number }}/complete">
  <input type="hidden" name="action" value="mark">
  <button type="submit" class="section-completion-button">Mark complete</button>
</form>
```

When the Section is already complete, the form renders with `action="unmark"` and the button label `"Mark incomplete"` (or equivalent).

**Why synchronous PRG, not AJAX/HTMX:**

- ADR-023 already commits to the no-JavaScript posture for Notes; mirroring it for completion preserves the project's single form-handling style. Adding HTMX or AJAX for completion would create two form-handling patterns in one template — one with JS, one without — for no offsetting benefit at local-dev scale.
- The user's wait between click and re-rendered page is <100ms locally — well below the threshold where partial reloads would be perceptible.
- Synchronous PRG works without JavaScript. If the human disables JS, the affordance still works.
- Manifest §6's "AI work asynchronous" is about *AI* work specifically; completion is not AI work; synchronous form submission is the correct shape.

**The URL fragment in the redirect (`#section-{section_number}`) restores the user's scroll position** to the Section they just toggled. Without the fragment, the page reloads at the top and the user has to scroll back to find the Section. With the fragment, the browser scrolls the Section back into view automatically. (This is standard HTML anchor behavior — no JS required.)

**Validation:**

- The route handler validates `chapter_id` against the discovered Chapter set (`tex_path.exists()` check, mirroring ADR-023). Unknown `chapter_id` returns **HTTP 404**.
- The route handler validates `{chapter_id}#section-{section_number}` against the parent Chapter's discovered Sections (via `extract_sections(chapter_id, latex_text)`). Unknown Section returns **HTTP 404**.
- The route handler validates `action` is exactly `"mark"` or `"unmark"`. Any other value (including missing) returns **HTTP 400**.
- The form additionally carries a hidden `action` field with the exact required value; user-supplied corruption requires bypassing the form (e.g., `curl`).

### Template placement — inline next to the `<h2 class="section-heading">` of each Section

The completion form is rendered inside each `<section id="{{ section.fragment }}">` block, immediately following the `<h2 class="section-heading">`. Concretely, the Section structure becomes:

```html
{% for section in sections %}
<section id="{{ section.fragment }}"
         class="{% if section.id in complete_section_ids %}section-complete{% endif %}">
  <div class="section-heading-row">
    <h2 class="section-heading">{{ section.heading | safe }}</h2>
    <form class="section-completion-form" method="post"
          action="/lecture/{{ chapter_id }}/sections/{{ section.section_number }}/complete">
      {% if section.id in complete_section_ids %}
        <input type="hidden" name="action" value="unmark">
        <button type="submit" class="section-completion-button section-completion-button--complete">
          ✓ Complete
        </button>
      {% else %}
        <input type="hidden" name="action" value="mark">
        <button type="submit" class="section-completion-button section-completion-button--incomplete">
          Mark complete
        </button>
      {% endif %}
    </form>
  </div>
  <div class="section-body">
    {{ section.body_html | safe }}
  </div>
</section>
{% endfor %}
```

The template requires that each `section` dict carry a `section_number` field (e.g., `"1-1"`) in addition to the existing `fragment` field (e.g., `"section-1-1"`) and `id` field (e.g., `"ch-01-cpp-refresher#section-1-1"`). The implementer adds the new `section_number` field to the dict returned by `extract_sections()` in `app/parser.py`; the derivation is a single line (strip the `section-` prefix from the existing `fragment` field). This is a small, additive parser change — no schema/IR-shape change, just one more derived key per Section.

**Why inline next to the heading rather than the alternatives:**

- **Placement (a) — inline next to the heading.** The completion affordance is per-Section and the heading is the visual marker for "this is a Section." Co-locating the affordance with the heading keeps the user's eye at the same focal point when they decide to mark complete. The affordance is visible without scrolling past the Section's body. **(chosen)**
- **Placement (b) — at the end of each Section's body.** Considered. The argument: "complete after reading" matches the natural flow (mark complete when you finish reading). Rejected: long Sections push the affordance far below the Section's heading, and a user who wants to unmark a previously-marked Section has to scroll through the Section's body to find the button. Heading-adjacent placement covers both "I want to mark this" and "I want to see what's already marked" without requiring body scroll.
- **Placement (c) — floating in the right margin.** Rejected. Forces a third column or absolute positioning. The page layout per ADR-008 is a two-column CSS Grid (rail + main); adding floating per-Section affordances would either (a) require JavaScript to position them, (b) overlap with the main column content on narrow viewports, or (c) require a layout redesign. Inline placement avoids all three.
- **Placement (d) — per-Chapter aggregated bar at the top of the page.** Rejected. Aggregates all Sections into one control surface that the user has to read top-to-bottom to know which Sections are complete. The per-Section heading-adjacent affordance is the same information surface but co-located with each Section's identity.

**The `section-complete` CSS class is applied to the entire `<section>` element** when the Section is in the complete-section-ids set. This lets the CSS apply visual treatment to the whole Section block (e.g., a colored left-border, a muted heading color, a checkmark background) via a single class without per-element styling.

### State indicator shape — three layered indicators (checkmark in button + section-level CSS class + button text)

A complete Section is visually marked by **all three of**:

1. **The button's text:** `"✓ Complete"` (with a leading checkmark glyph) when complete; `"Mark complete"` when incomplete.
2. **The button's CSS modifier class:** `.section-completion-button--complete` adds a "completed" visual treatment (e.g., green background, white text); `.section-completion-button--incomplete` adds the default "action available" treatment (e.g., a neutral outlined button).
3. **The `<section>` element's CSS class:** `.section-complete` is added to the `<section>` element when complete, enabling Section-wide visual treatment (left border, heading color, or both — implementer-tunable within the architectural commitment that the treatment be visually distinct from incomplete Sections without obscuring the Section's content).

**Why all three rather than just one:**

- The button text alone is the minimum readable indicator but is small and easy to miss when skimming a long Lecture page.
- The Section-wide CSS class alone makes complete Sections scannable when the user scrolls through the page looking for "where did I leave off."
- The button color reinforces the state at the point of interaction, so the user does not accidentally unmark when they meant to confirm.

Together, the three indicators give the user direct, unambiguous, and scannable feedback at three different reading-flow distances (button-text on click; button-color on hover; Section-wide treatment on scroll).

**The checkmark glyph (`✓`, U+2713) is rendered as a literal Unicode character in the template,** not as an image or icon font. No new static asset is introduced. The character renders in any browser font that supports the basic Unicode plane.

### Round-trip return point — PRG redirect to `GET /lecture/{chapter_id}#section-{section_number}`

After successful POST, the route returns `303 See Other` with `Location: /lecture/{chapter_id}#section-{section_number}`. The browser:

1. Issues a fresh `GET /lecture/{chapter_id}` (the fragment is client-side; the server sees only the path).
2. Renders the full Lecture page with the now-updated completion state.
3. Scrolls the `<section id="section-{section_number}">` element into view automatically via HTML anchor behavior.

The user-visible feedback is: the Section they just toggled is in view, with the now-flipped state indicator and the now-flipped button text. The new visual state at the same scroll position is the confirmation that the toggle succeeded.

**Why the fragment in the redirect:**

- Without the fragment, the page reloads at the top. On a 30-screen Chapter (per the Notes-placement project_issue's empirical chapter-length measurements), the user has to scroll back to find the Section they were just looking at. This is a real UX cost — the completion action becomes "mark, scroll to find what you just marked, confirm."
- With the fragment, the browser restores the user's scroll position to the Section that was just toggled. The cost is one extra string-format in the route handler.
- The fragment is a standard HTML anchor behavior — no JS required. It works on every browser the project's no-JS posture (ADR-023) supports.

### Styling — new classes added to `app/static/lecture.css`

Per ADR-008's class-name-prefix convention (`.lecture-*`, `.section-*`, `.callout-*` → `lecture.css`; `.page-*`, `.nav-*`, `.index-*` → `base.css`), the new completion-related classes belong in `lecture.css` because they style content within the Lecture body's `<main>` region:

- `.section-complete` — applied to `<section>` when the Section is complete; adds visual treatment (e.g., left border in `--ok` color, slightly muted heading).
- `.section-heading-row` — the flex container for the heading and the completion form.
- `.section-completion-form` — the inline form's container (e.g., no margin, no border, baseline-aligned with the heading).
- `.section-completion-button` — the base button styling (font, padding, hover state).
- `.section-completion-button--complete` — modifier for the "complete" state (e.g., green fill, white text).
- `.section-completion-button--incomplete` — modifier for the "incomplete" state (e.g., outlined neutral).

The CSS itself is implementer-tunable within reason; the architectural commitment is **the class names**, **the file location** (`lecture.css`), and **the rule that complete and incomplete states be visually distinct without obscuring the Section's content or the existing designation badge / section heading hierarchy**.

The implementer should use the same color palette the existing `lecture.css` already establishes (the `designation-mandatory` / `designation-optional` greens and blues from ADR-008; the section-heading teal `#3d6a6b`). Introducing a new color family for completion is unjustified — the existing palette is sufficient.

### Scope of this ADR

This ADR fixes only:

1. The route shape (`POST /lecture/{chapter_id}/sections/{section_number}/complete` with `action` form field; PRG 303 to `GET /lecture/{chapter_id}#section-{section_number}`).
2. The form-handling pattern (synchronous, no-JS, server-side validation, idempotent mark/unmark semantics).
3. The template placement (inline next to `<h2 class="section-heading">` within each `<section>` block in `lecture.html.j2`).
4. The state-indicator shape (three layered indicators: button text + button color + section-level CSS class).
5. The round-trip return point (PRG with URL fragment to scroll back to the toggled Section).
6. The styling location (`app/static/lecture.css`) and class-name namespace.
7. The minor parser addition (`section_number` field added to each Section dict in `extract_sections()`).

This ADR does **not** decide:

- Chapter-level derived progress display (e.g., "5 of 7 Sections complete" badge) — out of TASK-010 scope; future ADR + task.
- Mandatory-only filtered progress views — out of TASK-010 scope.
- Completion timestamps surfaced in UI — `completed_at` is persisted (ADR-024) but not displayed.
- Rail-side completion indicators (per-Chapter "Sections complete: 5/7" in the nav rail) — out of scope; the rail (ADR-006/ADR-008) is unchanged.
- Completion-driven navigation cues (e.g., "next incomplete Section" jumps) — out of scope.
- Quiz integration — manifest §7 separates completion from the reinforcement loop.
- Specific CSS pixel values, hover/focus animations, or color hex codes — implementer-tunable.
- Confirmation dialogs on unmark — none required; toggling is direct.

## Alternatives considered

**A. Route shape: separate `POST /.../mark` and `POST /.../unmark` routes (no `action` form field).**
Rejected. Two routes with near-identical handler bodies duplicates code. The template would also need to render the right `action` URL per Section based on current state — doubling the form-rendering logic. The single-route-with-`action` shape consolidates both directions into one handler with a `if action == 'mark': ... elif action == 'unmark': ...` dispatch.

**B. Route shape: single toggle route that flips state based on current value (no `action` field).**
Rejected. A double-click or a stale browser tab can produce non-deterministic outcomes (two POSTs in fast succession could mark-then-unmark, or unmark-then-mark, depending on timing). Carrying the intent explicitly makes the action idempotent: `mark` always means "set to complete"; `unmark` always means "set to incomplete." A second `mark` against an already-complete Section is a no-op, not a flip.

**C. Route shape: section number in URL query (`POST /lecture/{chapter_id}/sections/complete?section=1-1`) instead of in the path.**
Rejected. Query parameters are less self-documenting than path parameters; FastAPI's typed path parameter validation is more idiomatic and produces a cleaner OpenAPI surface. The path-parameter shape mirrors ADR-023's `/lecture/{chapter_id}/notes` precedent.

**D. Route shape: section number in form body (`POST /lecture/{chapter_id}/sections/complete` with `section_number` in the body).**
Rejected. Same drawback as C — the parent resource (the Section) belongs in the URL path. The `action` field is metadata about *what to do*; the section identity is metadata about *which resource* — those belong in different parts of the request.

**E. Form pattern: HTMX-style partial reload (POST returns an HTML fragment that swaps into the page).**
Rejected. Same drawback as ADR-023's HTMX rejection: HTMX adds a top-level static asset and a partial-rendering surface; the project has no JS today; tests would have to cover both the no-JS form path and the HTMX swap path. The full-page reload with fragment-anchored scroll is the lower-cost shape that meets the user need.

**F. Form pattern: client-side `fetch()` returning JSON, with manual DOM update.**
Rejected. Same as E plus duplicate rendering logic (server-side template + client-side JS rendering).

**G. Form pattern: form submits with a `_method=DELETE` field for unmark (REST-method-overloading via hidden form field).**
Rejected. The REST-purity argument (DELETE is the verb for "remove this resource") does not pay off because there is no semantic distinction in this surface — mark and unmark are both state-changes on the same resource. The `action=mark|unmark` shape is more legible than `_method=POST|DELETE` and does not require the route handler to special-case the method dispatch.

**H. Template placement: at the end of each Section's body (button below the lecture content).**
Considered. "Mark complete after you read" matches the natural reading flow. Rejected: long Sections push the affordance far below the heading, and the unmark-from-skimming case requires scrolling through the body to find the button. Heading-adjacent placement is the more robust shape for both directions of the toggle.

**I. Template placement: floating in the right margin (absolute-positioned per Section).**
Rejected. Requires either JavaScript or a layout redesign of ADR-008's two-column CSS Grid. The viewport-relative pinned-corner alternative competes with future affordances for the same real estate.

**J. Template placement: per-Chapter aggregated control bar at the top of the page (a row of section pills, each clickable to toggle).**
Rejected. Aggregates Sections into a single control surface separate from the Sections themselves. The user has to read the pill labels and match them mentally to the Section content they refer to. Per-Section heading-adjacent affordances are co-located with the content they refer to.

**K. State indicator: button text only (no Section-level CSS class, no button color modifier).**
Rejected as the minimum acceptable indicator. The button text is easy to miss when skimming. Adding the Section-level class and the button color modifier gives the user three concurrent signals at three different reading distances; the marginal cost is two small CSS rules.

**L. State indicator: native HTML `<input type="checkbox">` as the affordance.**
Considered. A checkbox is the universal "toggle state" affordance and would convey the intent at a glance. Rejected: a checkbox needs a wrapping `<form>` to submit on change, and HTML checkboxes do not natively submit on change without JavaScript (the `change` event needs a JS handler to call `form.submit()`). A `<button type="submit">` inside a form submits synchronously without JS. The checkmark glyph in the button text gives the same visual cue without the JS-or-extra-button compromise.

**M. Round-trip return: PRG to `/lecture/{chapter_id}` (top of page) without URL fragment.**
Rejected. The user's scroll position is lost on every toggle; on a 30-screen Chapter, every mark-complete forces a scroll-back. The fragment-anchored redirect costs one string-format and preserves scroll position via standard HTML anchor behavior.

**N. Round-trip return: HTTP 204 No Content with a `Location` header (no body, no redirect, no page reload).**
Rejected. 204 No Content is for AJAX/fetch responses; a synchronous form POST that returns 204 leaves the browser on the form page with no visual update. The state has changed in the database but the user sees nothing. PRG with a full page reload is the synchronous-form-correct response.

**O. Validation: route handler validates `chapter_id` but trusts the section number from the URL.**
Rejected. A typo'd `/sections/1-99/complete` for a Chapter that only has 1-1 through 1-7 would silently persist an orphan completion row. ADR-024 §Validation already commits to "route handler validates the Section ID against the parent Chapter's discovered Sections." This ADR honors that commitment.

**P. Confirmation dialog on unmark (JS `confirm()` or an in-template confirmation step).**
Rejected. Confirmation friction on a reversible action (unmark just re-toggles) adds cost without payoff. The user can re-toggle if they err. Manifest does not require it.

## My recommendation vs the user's apparent preference

The TASK-010 task file forecasts the architect's choice as "**(1)** `POST /lecture/{chapter_id}/sections/{n-m}/complete` form-encoded + PRG redirect (mirrors ADR-023's per-Chapter Notes shape, scaled down to per-Section). [...] with explicit `mark` vs `unmark` distinction (e.g., separate routes or a hidden form field `action=mark|unmark`)." This ADR **aligns with that forecast** — single route + `action` form field rather than separate routes (the architect picks the single-route shape with the explicit dispatch).

For **template placement**, the task forecasts "**(a) inline in the Section heading (next to `<h2 class="section-heading">`), (b) as a button at the end of each Section's body, (c) floating in the right margin. Architect's forecast: (a) for visibility.**" This ADR aligns — (a) chosen with explicit rationale.

For **state indicator shape**, the task forecasts "**(a) checkbox checked, (b) heading suffix "✓ Complete", (c) section-level CSS class (`.section-complete` adds a green left-border or muted heading color), (d) all of the above. Architect picks.**" This ADR commits to **three of the four** — button text with checkmark glyph (variant of b), section-level CSS class (c), and a button-color modifier (an additional layered indicator the task did not explicitly enumerate). The architect rejects (a) — native `<input type="checkbox">` — because the no-JS submit-on-change requirement is not satisfiable with a native checkbox without JS (see Alternative L). If the human wants a literal checkbox visual style, the implementer can shape the `.section-completion-button` CSS to look checkbox-like (the architectural commitment is the class names, not the precise visual rendering); this is the place to push back at the gate if the literal-checkbox-shape matters more than the no-JS posture.

One area of mild push beyond the task's forecast: this ADR introduces the **URL fragment in the PRG redirect** (`#section-{section_number}`) so the browser scrolls back to the just-toggled Section. The task does not prescribe; the architect's read is that without the fragment the round-trip becomes "click, scroll back to find what you clicked, confirm" on a long Chapter — a real UX cost that the fragment fixes for one extra string-format. If the human prefers the simpler top-of-page redirect, this is the place to push back.

A second area of mild push: this ADR requires a **small parser addition** — adding a `section_number` field (e.g., `"1-1"`) to each Section dict returned by `extract_sections()`. The derivation is one line (strip `"section-"` from the existing `fragment`); the implementer adds it inside `app/parser.py`. This is technically a parser change in service of a UI surface. The architect's read is that this is acceptable because (a) the parser is the source of Section metadata and the new field is a pure derivation from existing data, (b) the alternative (deriving `section_number` in the template via Jinja2 string-manipulation) is less testable and uses Jinja2 as a string-processing engine for data the parser should already be returning. If the human prefers the template-derivation shape, that is also acceptable — the architectural commitment is that the route URL contain the section number; the source of the value is implementer-tunable.

A third area: this ADR rejects the **literal checkbox affordance** (`<input type="checkbox">`) because it would require JavaScript for submit-on-change behavior, which the project's no-JS posture (ADR-023) forecloses. If the human strongly prefers the checkbox visual, the alternatives are (i) shape the button CSS to look checkbox-like (still a button under the hood; preserves no-JS), or (ii) introduce a `<button>` with a `<svg>` checkmark icon (no new dependency; preserves no-JS). Neither requires JavaScript.

I am NOT pushing back on:

- The single-user posture (manifest §5 / §6 / §7) — honored: no auth, no `user_id` in route or template.
- The asynchronous-AI absolute (manifest §6) — orthogonal: completion is not AI work.
- The Lecture-source-read-only rule (manifest §6, MC-6) — honored: the completion route writes only via `app/persistence/` (ADR-024).
- The ADR-006 navigation surface — preserved: the rail is unchanged.
- The ADR-008 CSS architecture — extended faithfully: new classes go in `lecture.css` per the prefix convention.
- The ADR-023 form-handling precedent — extended faithfully: synchronous PRG, no-JS, server-side validation.
- TASK-010's "Out of scope" enumeration (Chapter-level progress, Mandatory-only views, rail indicators, Quiz integration, timestamps in UI, confirmation dialogs) — honored.
- The Notes-placement Open project_issue — explicitly NOT addressed here per the issue's own Decide-when ("bundle with next Notes-related task"). This task is not Notes-related.

## Manifest reading

Read as binding for this decision:

- **§3 Primary Objective.** Section completion is a consumption-tracking primitive that supports retention by giving the learner a visible "I have absorbed this Section" affordance. The heading-adjacent placement and fragment-anchored PRG satisfy this — the affordance is direct, visible, and does not displace the lecture content.
- **§5 Non-Goals.** "No LMS" bounds the editorial scope (no progress-export route; no tutorial / onboarding around completion). "No mobile-first" bounds the responsive obligation (heading-adjacent layout works on desktop; mobile-tunable in CSS but not architecturally promised). "No AI tutor" bounds the form behavior (no AI suggestion of "this Section seems complete; mark it?"). "No multi-user" bounds the route layer (no auth, no `user_id`).
- **§6 Behaviors and Absolutes.** "Single-user" honored — no auth on the POST route; the completion's owner is implicit. "AI work asynchronous" orthogonal — completion is not AI work. "Mandatory and Optional honored everywhere" — the Lecture page's designation badge is unchanged; the completion affordance does not displace or hide the designation. "A Lecture has a single source" preserved — completion is a separate entity from Lecture; Lecture source remains read-only.
- **§7 Invariants.** **"Completion state lives at the Section level."** — the route shape (`/sections/{section_number}/complete`) and the affordance placement (per-Section, inline with each heading) directly honor this. **"Chapter-level progress is derived from Section state."** — the architecture does not foreclose Chapter-level aggregation (the `complete_section_ids` template variable is queryable per Chapter; future tasks can aggregate without re-deciding this surface). "Every … completion mark persists across sessions" — the PRG redirect's GET path reads completion state from persistence (ADR-024); the state is visible after a server restart by virtue of being read from disk on every Lecture-page GET. "Mandatory and Optional are separable in every learner-facing surface" — preserved by virtue of the existing designation badge being unchanged; future Mandatory-only progress views consume the same persistence accessors.
- **§8 Glossary.** Section is "the atomic unit for Quizzes and **completion state**. The unit of in-lecture navigation." — the route shape and template placement both honor this: the completion affordance is per-Section, the route binds per-Section, the in-page anchor URL fragment binds per-Section. Chapter is the parent unit and inherits its designation — unchanged by this ADR.

No manifest entries flagged as architecture-in-disguise.

## Conformance check

- **MC-1 (No direct LLM/agent SDK use).** Orthogonal — completion has no AI surface.
- **MC-2 (Quizzes scope to exactly one Section).** Orthogonal — no Quiz route introduced.
- **MC-3 (Mandatory/Optional designation respects the canonical mapping).** Preserved by construction. The Lecture page's designation badge (per ADR-008) is unchanged; the completion affordance lives below the badge in the header and inline with each Section, never displacing or hiding the designation. Compliance preserved.
- **MC-4 (AI work asynchronous).** Orthogonal — completion is not AI work. The synchronous POST + PRG redirect is the correct shape for non-AI work; treating it as a violation would be a misread of MC-4's scope.
- **MC-5 (AI failures surfaced).** Orthogonal — no AI in this surface.
- **MC-6 (Lecture source read-only).** Honored. The completion route writes only via `app/persistence/` (ADR-024), which targets `data/notes.db`. The route does not open any path under `content/latex/`. The route handler does read `content/latex/{chapter_id}.tex` (to validate the Section ID against `extract_sections`), but the read is read-only and identical to what ADR-003/ADR-023 already do. Compliance preserved.
- **MC-7 (Single user).** Honored. The POST route accepts no auth, has no `user_id` in path or body, has no per-user partitioning. The route handler does not check session state, does not consult a user store, does not partition completion state by any per-user key. Compliance preserved (architecture portion active per ADR-022).
- **MC-8 (Reinforcement loop preserved).** Orthogonal — no Quiz machinery in this ADR. The architect explicitly preserves the manifest §7 separation between completion and the reinforcement loop: marking a Section complete does NOT trigger Quiz generation, does NOT replay any Question, and does NOT alter Quiz-readiness in any way. Quiz-bootstrap (the next task) will introduce the reinforcement-loop machinery; this ADR commits to no coupling.
- **MC-9 (Quiz generation user-triggered).** Orthogonal — no Quiz generation in this surface.
- **MC-10 (Persistence boundary).** Honored. The route handler in `app/main.py` calls only the typed public functions exposed by `app/persistence/` (`mark_section_complete`, `unmark_section_complete`, `list_complete_section_ids_for_chapter`); it does not import `sqlite3`, does not contain SQL string literals, and does not receive raw database rows. Compliance preserved (architecture portion active per ADR-022).
- **UI-1 / UI-2 / UI-3 (ui-task-scope).** UI-1 satisfied at the task level (TASK-010 declares the completion UI surface). UI-2 satisfied by this ADR (the styling target is named — `app/static/lecture.css` — and the class-name namespace is committed). UI-3 satisfied by the diff naming `app/static/lecture.css` (modified) and listing the rules added.
- **UI-4 (rendered-behavior verification gate).** Honored. ADR-010's Playwright harness covers the round-trip verification; TASK-010's acceptance criterion ("at least one Playwright test exercises the round-trip: load Lecture → mark a Section complete → reload Lecture → assert the Section is shown as complete") binds the implementer to add the Playwright test, and ADR-010's last-run-screenshot review is the human gate for the visual surface.

Previously-dormant rule activated by this ADR: none new. (MC-7 architecture portion and MC-10 architecture portion are active per ADR-022; ADR-024 reinforces both; this ADR consumes them.)

## Consequences

**Becomes possible:**

- A user can mark or unmark any Section as complete via an inline per-Section button; state persists across server restarts (manifest §7 satisfied for the completion-state pillar).
- The Lecture page becomes a one-stop surface for "consume + capture + track" — read the lecture, write a Note, mark Sections complete — without navigating away.
- The PRG redirect's URL fragment restores the user's scroll position, so the toggle action does not disrupt reading flow.
- The completion-affordance pattern (per-Section form inline with the heading, idempotent `action`-based POST, PRG with anchored return) is the shape Quiz-bootstrap can reuse for the "Quiz this Section" affordance.
- The `complete_section_ids` template variable is a clean integration point for any future surface that needs to display completion state (e.g., a future Chapter-level progress display in the rail).
- The form works without JavaScript, on any browser the FastAPI app supports.

**Becomes more expensive:**

- The `lecture.html.j2` template is now longer per Section (the `<div class="section-heading-row">` wrapper, the `<form>`, the conditional `action` field, the conditional button class). Mitigation: the additions are localized to within each `<section>` block; the existing Section-rendering content is untouched.
- The Lecture-page GET route now performs an extra database query per request (`list_complete_section_ids_for_chapter`). Mitigation: SQLite local read is sub-millisecond at this data scale; the single-user / single-process operating model has no contention.
- `extract_sections()` in `app/parser.py` now derives one additional field (`section_number`). Mitigation: one line of code; pure derivation from existing data.
- Adding Chapter-level derived progress or Mandatory-only views requires extending the route's template-variable surface and the template's conditional rendering. Mitigation: those are exactly the follow-ups TASK-010 defers; the cost is in the right place.

**Becomes impossible (under this ADR):**

- A completion toggle that does not persist to the database. The synchronous PRG + persistence-call shape forces the persistence step.
- A completion affordance outside a Section's `<section>` block. The template structure forces per-Section co-location.
- A completion route that operates on multiple Sections at once. The route shape forces per-Section.
- A completion toggle that requires JavaScript. The form works without JS by construction.
- Auth-gated completion. Manifest §5/§6 forbids; this ADR codifies the no-auth posture at the route layer.
- A completion record whose author is recorded. No `user_id` is ever sent or stored.

**Future surfaces this ADR pre-positions:**

- Chapter-level derived progress display (e.g., "5 of 7 Sections complete" badge on the Lecture-page header or in the rail) — consumes `complete_section_ids` (already in template scope) and the Chapter's discovered Section count.
- Mandatory-only filtered progress view — consumes the same data + `chapter_designation()` (ADR-004).
- A "next incomplete Section" navigation cue — derivable from the same data; one helper function.
- Quiz integration — Quiz-bootstrap can read completion state via `list_complete_section_ids_for_chapter` to bias Quiz suggestions toward incomplete Sections (or, equivalently, to surface "you haven't completed this Section yet; want to Quiz before marking complete?" affordances). **Important: no coupling at the schema level (ADR-024); coupling is purely at the UI suggestion layer if a future task introduces it.**
- Completion-aware rendering of the rail — replace each rail Chapter row with `Ch N — Title (M/K complete)` once a follow-up task surfaces the derived view.
- Markdown / rich-text formatting on the lecture body is unaffected — completion is a metadata layer that does not interact with lecture rendering.

**Supersedure path if this proves wrong:**

- If the heading-adjacent placement proves too visually noisy (e.g., the inline button competes with the heading for attention) → a future ADR moves the affordance to a small icon at the end of the heading line, or to a per-Section right-margin placement. Cost: template + CSS edit; bounded.
- If synchronous PRG with fragment scroll proves friction-heavy (the page-reload flicker is jarring for rapid mark-complete actions) → a future ADR introduces HTMX or a small JS swap. Cost: new dependency; bounded.
- If the `action` form field shape conflicts with a future need (e.g., a batch-complete affordance) → a future ADR adds a parallel route. The per-Section route stays.
- If the URL fragment redirect breaks for any browser configuration → a future ADR removes the fragment and accepts top-of-page reload. Cost: one line of code; bounded.
- If the layered three-indicator state shape proves too busy → a future ADR reduces to one or two indicators. Cost: CSS edit + template edit; bounded.
