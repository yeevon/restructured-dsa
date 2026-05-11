# ADR-031: Supersedure of ADR-030 §Decision — the section-completion 303 redirect anchors to a `#section-{n}-end` fragment on the `.section-end` wrapper, paired with a large `scroll-margin-top`, so the toggle lands the user ≈ where they clicked with no JavaScript

**Status:** `Accepted`
Auto-accepted by /auto on 2026-05-11
**Date:** 2026-05-11
**Task:** TASK-012
**Resolves:** `design_docs/project_issues/section-completion-prg-redirect-disrupts-scroll-position.md` (jointly: ADR-030 supplied the load-bearing principle, this ADR supplies the working mechanism)
**Supersedes:** `ADR-030` (§Decision only — the "drop the `#section-{n}` fragment from the `303 Location` header; rely on Chromium preserving scroll on the fragment-less same-URL navigation" mechanism. ADR-030's **load-bearing principle** — "the response to a reading-flow action should not relocate the user; completion is an annotation on what was just read, not a navigation event" — is **retained in full and better honored by this ADR's mechanism**; ADR-030's "what of ADR-025 is retained" bookkeeping, its scoping of ADR-025 §Round-trip-return-point as superseded, and its placement in the supersedure ledger remain accurate. The cleanest way to express this in `architecture.md`'s Superseded table is to add one row: "ADR-030 §Decision (no-fragment redirect mechanism) → ADR-031", leaving ADR-030's principle and bookkeeping in force. ADR-025 §Round-trip-return-point remains `Superseded by ADR-030` — the *principle* under which the round-trip return point is decided is ADR-030's; ADR-031 only changes the *mechanism* ADR-030 chose to implement that principle.)
**Superseded by:** none

## Context

ADR-030 (Accepted, auto-accepted by `/auto` on 2026-05-11, TASK-012) superseded ADR-025 §Round-trip-return-point and committed to **Option 1**: the `POST /lecture/{chapter_id}/sections/{section_number}/complete` route handler stops emitting the `#section-{section_number}` fragment in its `303 Location` header (redirect target becomes `/lecture/{chapter_id}`), relying on modern Chromium preserving the document's scroll position on a POST→303→GET navigation that lands on the *same URL* the form was submitted from. ADR-030 explicitly documented the contingency: *"If — and only if — the test-writer/implementer phase demonstrates via Playwright that Chromium does not reliably preserve scroll on the fragment-less same-URL navigation, the fallback is Option 2 [client-side `fetch()` async toggle] ... requires a separate, dedicated `Status: Proposed` ADR committing to the client-side-JavaScript posture ... gated by the human via `> NEEDS HUMAN`; the orchestrator must not cross the no-JS threshold on its own."*

The implementation phase ran that Playwright regression test against Chromium and it **failed**:

> `tests/playwright/test_task012_rhs_notes_rail_dom.py::test_marking_section_complete_does_not_snap_scroll_position[chromium]` — `AssertionError: Scroll position snapped: pre-click scrollY=3514px, post-reload scrollY=0px, delta=3514px (tolerance: 200px)`

Chromium does **not** preserve scroll on the `POST → 303 → GET /lecture/{chapter_id}` (fragment-less, same-URL) navigation — it resets `scrollY` to **0** (the top of the document). This is the exact "Option 2 fallback trigger" ADR-030 documented: the `/auto` loop stopped (per `/auto` rule 2 / rule 6 — the only path to a green scroll-preservation test is introducing JavaScript, which ADR-030 forbids without a gated ADR), surfaced the failure to the human, and did **not** re-invoke the implementer or silently route around it. Recorded in `design_docs/audit/TASK-012-...md` Run 006.

The human resolved the stop (Run 007) by choosing **neither** of ADR-030's two documented paths:

- **Not Option 1** ("no fragment"). It is empirically the worst of the candidates — Chromium snaps the user to the top of the *whole page*, a far worse relocation than the original `#section-{n}` anchor's "snap to the Section heading."
- **Not Option 2** (client-side JavaScript async toggle). The human's framing at the stop: *"a bunch of unneeded javascript for what we're building"* — for a single-user, local-only lecture reader, a `fetch()` handler + DOM-update path + a client-side asset + Playwright JS-on/JS-off test variants is disproportionate to the problem. ADR-030 itself notes the no-JS PRG path would have to be retained as the JS-off fallback anyway, so Option 2 is *more* code, not less. (The objection is "this doesn't need JavaScript here," not "JavaScript is off-limits" — see ADR-035.)

Instead the human picked a **no-JavaScript variant of the previously-ruled-out "anchor to the bottom of the Section" family** (the project_issue's Option 4), softened with a CSS trick that removes the ~1-viewport jump that made plain Option 4 "a bit jarring":

> Anchor the 303 redirect to a new `#section-{n}-end` fragment — an `id` on the `.section-end` wrapper (the bottom-of-Section affordance container per ADR-027) — **AND** give `.section-end` a large `scroll-margin-top` in `lecture.css`. Fragment navigation normally yanks the target element to the *top* of the viewport; `scroll-margin-top: <large value>` makes the browser leave that much space above the target, so `.section-end` lands near the *bottom* of the viewport — approximately where the "mark complete" button was when the user clicked it. Net: ~zero perceived scroll motion, no JavaScript, a ~3-line diff. On short Sections (< 1 viewport tall) it degrades gracefully — the browser can't scroll that far, so it lands near the top, which is fine because a short Section has no jarring jump in the first place.

The project_issue's earlier ruling that Options 4 and 5 are "ruled out by the human's principle" is **relaxed by the human's own re-decision**: the `scroll-margin-top` polish is exactly what was missing from plain Option 4. The human's principle ("don't mess with the user's experience" / "the response should not relocate the user") is *not* relaxed — it is the binding constraint, and this mechanism honors it more faithfully than either ADR-030 Option 1 (snaps to page top) or the original ADR-025 fragment (snaps to Section heading): the user clicks at the bottom of the Section and stays at the bottom of the Section.

The decision space:

- **The mechanism:** (a) ADR-030 Option 1 — no fragment; **rejected empirically** (Chromium snaps to page top, Playwright-proven); (b) ADR-030 Option 2 — client-side JS; **rejected by the human** (disproportionate for a single-user local reader; more code, not less; crosses a permanent architectural threshold); (c) plain Option 4 — `#section-{n}-end` anchor with no `scroll-margin-top`; **rejected** (a ~1-viewport jump remains, called "a bit jarring" in the project_issue); (d) Option 5 — anchor to the *next* Section's heading; **rejected** (wrong semantics — completion's meaning is "I have read this," not "take me to the next one"; breaks at the last Section of a Chapter); (e) **this ADR's choice** — `#section-{n}-end` anchor on `.section-end` + a large `scroll-margin-top` on `.section-end`, no JavaScript.
- **The `scroll-margin-top` value:** large enough that `.section-end` lands near the bottom of the viewport; viewport-relative (`vh`) so it adapts to window height; implementer-tunable so the Playwright scroll-delta-≤-200px assertion passes with margin. ADR-030's Playwright regression test (the `abs(post − pre) ≤ 200px` assertion) is **retained** and now becomes the acceptance signal for this mechanism — it should now PASS.

The manifest constrains this decision through §3 (the completion toggle is a consumption-tracking primitive whose UX should not fight the reading flow — this mechanism makes the toggle a frictionless annotation), §5 ("no mobile-first" — Chromium is the binding test target per ADR-010; other browsers' fragment-scroll behavior is out of scope; "no LMS / no AI tutor / no remote deployment / no multi-user"), §6 (single-user; Lecture source read-only — one route-handler line + one template `id` attribute + one CSS rule; no source writes), §7 (**"Completion state lives at the Section level"** — preserved: the redirect-target change does not touch where completion state lives, only where the browser scrolls to after the POST; "Every … completion mark persists across sessions" — preserved, no persistence change).

## Decision

### The mechanism — anchor the 303 redirect to `#section-{section_number}-end` (an `id` on the `.section-end` wrapper) and give `.section-end` a large `scroll-margin-top` so fragment navigation lands the wrapper near the bottom of the viewport; no JavaScript

Three coordinated changes:

1. **`app/main.py` — `toggle_section_complete` route handler.** The `303 See Other` `Location` header carries a fragment again, but pointing at the `.section-end` wrapper (where the user clicked), not the Section heading:

   ```python
   return RedirectResponse(
       url=f"/lecture/{chapter_id}#section-{section_number}-end",
       status_code=303,
   )
   ```

   (The route already composes `section_id = f"{chapter_id}#section-{section_number}"` internally for validation; `section_number` is already a path parameter — no new derivation is needed.)

2. **`app/templates/lecture.html.j2` — the `<div class="section-end">` wrapper.** Gains an `id` so the fragment has a target:

   ```html
   <div class="section-end" id="{{ section.fragment }}-end">
   ```

   `section.fragment` is already `section-{n-m}` (e.g., `section-1-1`), so this renders as `id="section-1-1-end"` — matching the redirect's `#section-{section_number}-end` (e.g., `#section-1-1-end`). The `<section id="{{ section.fragment }}">` anchor on the Section element is **unchanged** (still `id="section-1-1"`); the `.section-end` wrapper just adds the `-end`-suffixed id alongside it.

3. **`app/static/lecture.css` — the `.section-end` rule.** Gains a large viewport-relative `scroll-margin-top`:

   ```css
   .section-end {
     /* ... existing rules (margin-top, padding-top, margin-bottom, border-top,
        display: flex, justify-content: flex-end) unchanged ... */
     scroll-margin-top: 75vh; /* implementer-tunable; large enough that fragment
                                 navigation lands .section-end near the bottom of
                                 the viewport ≈ where the user clicked, and the
                                 ADR-030 Playwright scroll-delta-≤-200px assertion
                                 passes with margin */
   }
   ```

   Per ADR-008's class-name-prefix convention (`section-*` → `lecture.css`), this rule belongs in `lecture.css` — the same file `.section-end` already lives in.

The architectural commitments are:

- The `303 Location` header for the completion toggle carries the `#section-{section_number}-end` fragment — pointing at the bottom-of-Section affordance container, not the Section heading.
- The `.section-end` wrapper renders with `id="section-{n-m}-end"` so the fragment has a target.
- `.section-end` carries a large viewport-relative `scroll-margin-top` so fragment navigation lands the wrapper near the bottom of the viewport. The exact value is implementer-tunable within the constraint that the ADR-030 Playwright assertion (`abs(post_scrollY − pre_scrollY) ≤ 200px` after a bottom-of-Section "mark complete" click on a tall Section) passes.
- The no-JS form-handling shape the Notes and completion surfaces share (ADR-023 / ADR-025 / ADR-027 / ADR-028 / ADR-030) is **followed** — this mechanism introduces no client-side code; it is a one-line route-handler change, a one-attribute template change, and a one-property CSS change. (Following a clean recipe, not honoring a project rule — see ADR-035; the human's choice here was a deliberate "this doesn't need JavaScript," not the discharge of an invariant.)
- Everything else about the route (shape, validation, persistence integration, the `action=mark|unmark` dispatch, the 303 status, the state-indicator triad) is unchanged.
- Everything else about ADR-027's bottom-of-Section placement (the `.section-end` wrapper, its visual-break treatment, the form alignment) is unchanged — this ADR adds an `id` and a `scroll-margin-top` to that wrapper; it does not move or re-style it.

**Why this mechanism and not the alternatives:**

- **Option 1 (no fragment) is empirically refuted.** ADR-030 chose it on the hypothesis that Chromium preserves scroll on the fragment-less same-URL navigation. The Playwright regression test ADR-030 itself mandated falsified that hypothesis: Chromium resets `scrollY` to 0. ADR-030's contingency is triggered.
- **Option 2 (client-side JS) is rejected by the human and is disproportionate.** It would be the first JavaScript in the project — a permanent architectural commitment — for a single-user, local-only reader, when a 3-line no-JS diff solves the problem. ADR-030 already notes the no-JS PRG path would have to be retained as the JS-off fallback under Option 2, so Option 2 is strictly *more* code surface, not less. The human's framing ("a bunch of unneeded javascript for what we're building") is the binding signal.
- **Plain Option 4 (anchor to `.section-end`, no `scroll-margin-top`) leaves a residual jump.** Without `scroll-margin-top`, fragment navigation yanks `.section-end` to the *top* of the viewport — so the user clicks at the bottom of the Section (the `.section-end` wrapper near the bottom of their viewport), the page reloads, and the browser scrolls so that `.section-end` is at the *top* of the viewport — a roughly-one-viewport upward jump. The project_issue called this "a bit jarring." The `scroll-margin-top` polish is exactly what removes that jump: with `scroll-margin-top: 75vh`, the browser leaves 75vh of space above `.section-end`, so `.section-end` lands ~75vh down the viewport — i.e., near the bottom, ≈ where it was when the user clicked. Net: ~zero perceived motion.
- **Option 5 (anchor to the next Section) has the wrong semantics.** "Mark complete" means "I have read this Section," not "take me to the next one." Anchoring to the next Section's heading reframes completion as a navigation act the human explicitly did not ask for, and it breaks at the last Section of a Chapter (there is no next Section to anchor to).
- **This mechanism honors ADR-030's load-bearing principle more faithfully than ADR-030's own chosen mechanism.** ADR-030's principle: "the response to a reading-flow action should not relocate the user; completion is an annotation on what was just read, not a navigation event." ADR-030 Option 1 *relocates the user to the top of the whole page*. The original ADR-025 fragment *relocates the user to the Section heading*. This mechanism leaves the user at the bottom of the Section — where they were. The principle is retained; the mechanism is replaced with one that actually delivers it.

### What of ADR-030 is retained

ADR-030 made one decision (§Decision: the no-fragment redirect mechanism) and encoded one load-bearing principle. This supersedure targets only §Decision. The following remain in force from ADR-030:

- **The load-bearing principle** — "the response to a reading-flow action should not relocate the user. An affordance placed at the natural reading position (per ADR-027) earns a response that leaves the user at that position — completion is an annotation on what was just read, not a navigation event." Retained verbatim; this ADR's mechanism is its faithful implementation. (ADR-030 Option 1 was an *attempt* at implementing this principle; the attempt failed empirically; this ADR's mechanism succeeds.)
- **The Playwright regression test requirement** — a Playwright test asserting that, after a "mark complete" click at the bottom-of-Section affordance on a tall Section, the post-reload `window.scrollY` is within a small tolerance (≤ 200px) of the pre-click `window.scrollY`. ADR-030 mandated it as the lock on Chromium's (non-existent) scroll-preservation behavior; under this ADR it becomes the lock on the `scroll-margin-top` value being large enough. The assertion is unchanged; only its docstring/comments need updating (it was failing under ADR-030's mechanism; it should now pass under this ADR's mechanism).
- **ADR-030's scoping of ADR-025 §Round-trip-return-point as superseded.** ADR-025 §Round-trip-return-point remains `Superseded by ADR-030` — the decision *that the round-trip return point is no longer the `#section-{n}` heading anchor* stands; this ADR only changes *what the new round-trip return point is* (the `.section-end` wrapper with a `scroll-margin-top` offset, rather than "nowhere — no fragment").
- **ADR-030's "what of ADR-025 is retained" bookkeeping.** The route shape, form-handling pattern, validation, persistence integration, state-indicator triad, bottom-of-Section placement (ADR-027), styling file location, and the `complete_section_ids` template variable all remain Accepted as written by ADR-025 / ADR-027 — ADR-030 enumerated them, ADR-031 does not disturb them.
- **ADR-030's no-JS form-handling shape.** ADR-030 stayed within it; this ADR also stays within it. (The Option 2 / JS-posture-ADR contingency in ADR-030 is now *moot* — the empirical failure that would have triggered it is instead resolved by this no-JS mechanism, per the human's explicit choice. The completion toggle no longer has any pressure pushing it toward client-side JS — but client-side JS was never forbidden; see ADR-035.)

The supersedure surface is narrow and surgical: the **mechanism** by which the completion route's response leaves the user where they clicked. Everything else in ADR-030 (and ADR-025 / ADR-027) stands.

### Load-bearing principle — unchanged; this ADR is its working implementation

This ADR does **not** re-encode a new principle. It retains ADR-030's:

> **The response to a reading-flow action should not relocate the user. An affordance placed at the natural reading position (per ADR-027) earns a response that leaves the user at that position — completion is an annotation on what was just read, not a navigation event. A reading-flow-action response keeps the user where they were; it does not snap them to an anchor that relocates them.**

The refinement this ADR adds is purely mechanical: *a same-URL PRG navigation does not, by itself, preserve scroll in Chromium (empirically false); to keep the user where they were after a PRG round-trip, anchor the redirect at the element the user was looking at and offset that element's scroll-snap position so it lands back where it was.* The principle's burden on future reading-flow affordances is unchanged: a reading-flow action's response leaves the user in place unless the action's *meaning* is navigation; if a PRG round-trip is the mechanism, the redirect anchors at the affordance the user interacted with.

Reviewers should reject any new reading-flow-action response that relocates the user without naming why relocation is the *meaning* of the action — and should reject any new PRG-based reading-flow affordance that omits the redirect anchor + `scroll-margin-top` offset (or an equivalent no-JS mechanism) and thereby leaves the user snapped to the top of the page.

### Test-writer pre-flag — the new TASK-012 "no fragment" assertions must be re-amended; the Playwright scroll-delta assertion stays and should now pass

Per the user-memory entry **"Test updates forced by Accepted ADRs are routine"** (`feedback_test_evolution_is_routine.md`) and the TASK-012 task file's "Architectural concerns" section, the following test updates are anticipated when this supersedure becomes Accepted. **The test-writer should NOT raise PUSHBACK for these** — they are the routine ADR-driven test evolution the user-memory entry describes: *"When implementer ESCALATION is 'test fails because Accepted ADR-NNN changed the architecture,' amend the test directly; don't open project_issues or park the task."* The same routing applies preemptively at the test-writer phase: ADR-031 has named the redirect-target change as the architecture change; tests that depend on ADR-030's "no fragment" redirect are amended at the test-writer phase, not flagged as bugs.

1. **New TASK-012 pytest tests in `tests/test_task012_rhs_notes_rail_and_redirect.py`** that assert the `303 Location` header has **no** fragment must be re-amended to assert the `Location` ends with `#section-{section_number}-end`. Specifically:
   - `test_completion_redirect_location_no_fragment_mark` — re-amend to assert the `Location` for an `action=mark` POST ends with `#section-{section_number}-end` (e.g., for section `1-1`: `/lecture/{chapter_id}#section-1-1-end`). Rename if the test name now misdescribes (e.g., `test_completion_redirect_location_anchors_section_end_mark`).
   - `test_completion_redirect_location_no_fragment_unmark` — same, for `action=unmark`.
   - `test_completion_redirect_location_no_fragment_all_chapters` (×12 parametrized) — re-amend to assert the `Location` ends with `#section-{section_number}-end` for the tested Section on each of the 12 corpus Chapters.
   - `test_completion_redirect_still_returns_303` — unchanged (the 303 status is unchanged).
2. **`tests/test_task010_section_completion.py::test_post_complete_redirect_location_contains_chapter`** — the test-writer amended this in TASK-012 Run 004 from `assert f"section-{TEST_SECTION_NUMBER}" in location` to `assert "#" not in location` (per ADR-030). It must be **re-amended** to assert `f"section-{TEST_SECTION_NUMBER}-end" in location` (and that the chapter path is still present). Update the docstring to cite ADR-031 §Test-writer pre-flag.
3. **`tests/playwright/test_task012_rhs_notes_rail_dom.py::test_marking_section_complete_does_not_snap_scroll_position`** — keep the `abs(post_scrollY − pre_scrollY) <= 200` assertion exactly as written; it was *failing* under ADR-030's mechanism and should now *pass* under ADR-031's. Only the docstring/comments need updating (drop the "Chromium preserves scroll on the fragment-less same-URL navigation" framing; replace with "the `#section-{n}-end` anchor + `.section-end { scroll-margin-top }` lands the wrapper ≈ where the user clicked"). If the assertion still fails after the implementer applies the mechanism, the implementer **escalates** (`ESCALATION:` per CLAUDE.md) so the `scroll-margin-top` value can be tuned — that is a value-tuning loop, *not* a re-trigger of the no-JS-threshold escalation (the mechanism is fixed; only the magnitude of `scroll-margin-top` is in play).
4. **`tests/playwright/test_task012_rhs_notes_rail_dom.py::test_completion_redirect_location_has_no_fragment_in_browser`** (and any sibling like `test_rhs_notes_rail_scroll_preservation_across_12_chapters` that asserts the post-toggle browser URL has no `#`) — re-amend to assert the browser URL after the toggle ends with `#section-{n}-end`. Rename if the name now misdescribes.
5. **A new small assertion (welcome, not required):** that `.section-end` in the rendered `lecture.html.j2` carries `id="section-{n-m}-end"`, and that `app/static/lecture.css` sets `scroll-margin-top` on `.section-end`. A source-static test (grep `lecture.css` for `scroll-margin-top`) and a rendered-HTML test (parse the lecture page, assert each `.section-end` has the `-end`-suffixed id matching its parent `<section>`) are both in keeping with the project's existing test style.

### Scope of this supersedure ADR

This ADR fixes only:

1. The change of the `303 Location` header's fragment from `#section-{section_number}` (ADR-025) / no fragment (ADR-030) to `#section-{section_number}-end` (pointing at the `.section-end` wrapper).
2. The addition of `id="{{ section.fragment }}-end"` to the `<div class="section-end">` wrapper in `lecture.html.j2`.
3. The addition of a large viewport-relative `scroll-margin-top` to the `.section-end` rule in `lecture.css` (per ADR-008's `section-*` → `lecture.css` convention), implementer-tunable so the ADR-030 Playwright scroll-delta-≤-200px assertion passes.
4. The retention of ADR-030's load-bearing principle (unchanged), its Playwright regression test requirement (unchanged assertion, updated docstring), its scoping of ADR-025 §Round-trip-return-point as superseded, its "what of ADR-025 is retained" bookkeeping, and the no-JS form-handling shape it stayed within (which this ADR also stays within — not a project rule; see ADR-035).
5. The test-writer pre-flag for routine ADR-driven test amendment (re-amending the TASK-012 "no fragment" assertions to assert the `#section-{n}-end` fragment; keeping the Playwright scroll-delta assertion).

This ADR does **not** decide:

- Anything about the Notes panel's column placement — that is ADR-029's surface.
- The adoption of client-side JavaScript *for the completion toggle*. This ADR's mechanism needs none; the ADR-030 Option-2 / JS-posture-ADR contingency is rendered moot (the empirical failure that would have triggered it is resolved here, per the human's explicit choice). A future ADR could still add it for some other reason — that's a normal step, not a forbidden one; see ADR-035.
- Moving the completion affordance again. ADR-027 placed it at the bottom of each `<section>` inside the `.section-end` wrapper; that is correct and retained. This ADR adds an `id` and a `scroll-margin-top` to that wrapper; it does not move or re-style it.
- The exact `scroll-margin-top` value — implementer-tunable within the constraint that the ADR-030 Playwright assertion passes.
- Any change to the `section_completions` schema (ADR-024) or the route-handler's mark/unmark logic. Only the redirect target's fragment changes (plus a template `id` and a CSS property).
- Async (JS) treatment of the Notes form. Out of scope here — the Notes form's PRG round-trip does not have the snap problem (the form is in the rail, not at the bottom of a tall Section).
- Confirmation dialogs on unmark — none required (per ADR-025); unmarking is reversible.
- Mobile responsiveness — manifest §5 bounds the obligation; Chromium is the binding test target per ADR-010. (`scroll-margin-top: 75vh` is viewport-relative and adapts to window height, so it degrades reasonably on a short viewport — but a "polished mobile experience" is not promised.)
- Browsers other than Chromium — out of scope per ADR-010 (Chromium is the binding test target). `scroll-margin-top` is widely supported in modern browsers, but the project's verification target is Chromium and the Playwright assertion locks Chromium's behavior in.

## Alternatives considered

**A. ADR-030 Option 1 — no fragment; rely on Chromium preserving scroll on the fragment-less same-URL navigation.**

Rejected — empirically refuted by the Playwright regression test ADR-030 itself mandated. Chromium does not preserve scroll on `POST → 303 → GET /lecture/{chapter_id}` (it resets `scrollY` to 0, the top of the page). This is ADR-030's documented Option-2 fallback trigger; the human resolved the stop in favor of this ADR's no-JS mechanism rather than Option 2. (The Notes route uses the same fragment-less `303 → GET /lecture/{chapter_id}` pattern and "has no scroll-disruption complaint" — but that is because the Notes form is in the rail near the top, not at the bottom of a 30-viewport Section; the Notes form's *post-reload* scroll-to-top is not noticed because the form was near the top to begin with. The completion form at the bottom of a tall Section makes the scroll-to-top dramatically visible. ADR-030's "the Notes route already does this" reasoning held for the *redirect shape* but not for the *user-perceived effect* on a bottom-of-Section affordance — which is exactly why ADR-030 mandated the Playwright test, and exactly why that test failing triggers this ADR.)

**B. ADR-030 Option 2 — client-side JavaScript async toggle (`fetch()` + DOM update in place).**

Considered as ADR-030's documented fallback; **rejected by the human** at the surfaced stop: *"a bunch of unneeded javascript for what we're building."* Rationale: (a) it would be the first JavaScript in the project — a permanent architectural commitment (script-tag wiring in `base.html.j2`, a static JS file, Playwright JS-on/JS-off test variants, a no-JS PRG fallback retained anyway) — disproportionate for a single-user, local-only lecture reader; (b) ADR-030 itself notes the no-JS PRG path would have to be retained as the JS-off fallback under Option 2, so Option 2 is strictly *more* code surface than this ADR's 3-line no-JS diff, not less; (c) the human's whole framing of this issue ("radical idea i know but … don't mess with the users experience" / "a bunch of unneeded javascript") reads as a preference for the *smallest* change that respects the principle. This ADR's mechanism is that change. (Note: ADR-030 routed Option 2 through a `> NEEDS HUMAN`-gated JS-posture ADR; the human's choice of this ADR's mechanism instead means that gate is never reached — there is no longer any path by which the completion toggle forces client-side JS.)

**C. Plain Option 4 — anchor the 303 redirect to `#section-{n}-end` on the `.section-end` wrapper, *without* a `scroll-margin-top` on `.section-end`.**

Rejected. Without `scroll-margin-top`, fragment navigation yanks `.section-end` to the *top* of the viewport. The user clicks "mark complete" at the bottom of the Section (the `.section-end` wrapper near the bottom of their viewport), the page reloads, and the browser scrolls so `.section-end` is at the *top* — a roughly-one-viewport upward jump. The project_issue called this "a bit jarring." Better than ADR-025's "snap to Section heading" (~30 viewports) or ADR-030 Option 1's "snap to page top," but still a visible relocation. The `scroll-margin-top` polish is precisely what eliminates the residual jump: with a large `scroll-margin-top`, the browser leaves that much space above `.section-end`, so the wrapper lands near the *bottom* of the viewport ≈ where the user clicked. The `scroll-margin-top` is not optional cosmetic polish — it is the difference between "a bit jarring" and "~zero perceived motion," which is the difference between violating and honoring the human's principle.

**D. Option 5 — anchor the 303 redirect to the *next* Section's heading (`#section-{N+1-1}`).**

Rejected. "Mark complete" means "I have read this Section," not "take me to the next one." Anchoring to the next Section's heading reframes completion as a navigation act — a semantics the human explicitly did not ask for ("don't mess with the users experience"). It also breaks down at the last Section of a Chapter: there is no next Section to anchor to, so the route handler would need a special case (anchor to where? the bottom of the current Section? the top of the page?), reintroducing the complexity this ADR's uniform `#section-{n}-end` mechanism avoids.

**E. Keep ADR-030's no-fragment redirect but add a JavaScript `scrollIntoView()` on page load to restore the pre-click position.**

Rejected. Same JavaScript commitment as Option 2 (it's *more* JS than Option 2's `fetch()` handler in some respects — it needs to *remember* the pre-click position across the navigation, e.g., via `sessionStorage`, and restore it on load), with the same disproportionality the human flagged. The pure-CSS `scroll-margin-top` mechanism achieves the same effect with no client-side code.

**F. Bundle this supersedure into a re-edit of ADR-030 (amend ADR-030's §Decision in place rather than writing a new ADR).**

Rejected — `AS-1` (Accepted-ADR content immutability; the conformance skill / CLAUDE.md authority rules) forbids editing an Accepted ADR's decision body in place. ADR-030 is Accepted (auto-accepted 2026-05-11). The correct mechanism is a new ADR (this one) that cites ADR-030, retains ADR-030's principle and bookkeeping, and supersedes only ADR-030's §Decision mechanism. This also matches the project's established pattern (ADR-027 superseding ADR-025 §Template-placement; ADR-029 superseding ADR-028 §Rail-integration; ADR-030 superseding ADR-025 §Round-trip-return-point — each a new document with a narrow supersedure scope).

**G. Anchor to `.section-end` and reduce the `border-top` / padding so the wrapper is shorter, instead of adding `scroll-margin-top`.**

Rejected — doesn't solve the problem. The issue is *where in the viewport the wrapper lands after fragment navigation*, not *how tall the wrapper is*. A shorter `.section-end` still gets yanked to the top of the viewport by fragment navigation; the user is still relocated by ~one viewport. `scroll-margin-top` is the property that controls scroll-snap landing position; that is the right tool.

## My recommendation vs the user's apparent preference

This ADR **implements the human's explicit choice**, made at the `/auto` stop the empirical Playwright failure surfaced (audit Run 007). The human chose, in their own words, *neither* ADR-030 Option 1 (*"empirically the worst — snaps to page top"*) *nor* ADR-030 Option 2 (*"a bunch of unneeded javascript for what we're building"*), and instead specified: *"anchor the 303 redirect to a new `#section-{n}-end` fragment (an `id` on the `.section-end` wrapper) AND give `.section-end` a large `scroll-margin-top` in `lecture.css` so that fragment navigation … leaves ~that much space above it and lands `.section-end` near the bottom of the viewport — i.e., approximately where the button was when the user clicked it. Net: ~zero perceived scroll motion, no JavaScript, ~3-line diff."*

This ADR is the routine `Proposed` supersedure that records that decision. **It is aligned with the user's direction in full** — there is no disagreement to surface. The architect's only choices within the decision are mechanical:

- **`scroll-margin-top: 75vh`** as the *starting* value (implementer-tunable). Rationale: large enough that `.section-end` lands in roughly the bottom quarter of the viewport ≈ where a bottom-of-Section affordance sits when the user clicks it, while leaving the affordance fully visible (not pushed below the fold). If the Playwright scroll-delta-≤-200px assertion fails at 75vh, the implementer tunes (75–90vh is the plausible band; the assertion is the binding test, not the literal value). This is a value-tuning loop, not an architectural one.
- **`id="{{ section.fragment }}-end"`** as the id form (rather than, e.g., a separate `data-section-end` attribute the route handler would have to know a different name for). Rationale: `section.fragment` is already `section-{n-m}`, so `{{ section.fragment }}-end` renders as `section-{n-m}-end`, which matches `#section-{section_number}-end` in the redirect with zero extra derivation — the route's `section_number` path parameter and the template's `section.fragment` already agree on the `{n-m}` form. Using the existing fragment as the base keeps the redirect target and the template id trivially in sync.

I am NOT pushing back on:

- The human's explicit choice at the stop (this ADR records it faithfully).
- ADR-030's load-bearing principle ("the response to a reading-flow action should not relocate the user") — **retained in full**; this ADR's mechanism is its faithful implementation (more faithful than ADR-030 Option 1 or the original ADR-025 fragment).
- ADR-030's Playwright regression test requirement — retained; the assertion is unchanged and should now pass.
- ADR-030's scoping of ADR-025 §Round-trip-return-point as superseded, and ADR-030's "what of ADR-025 is retained" bookkeeping — retained.
- ADR-025's / ADR-027's retained decisions (route shape, validation, persistence integration, state-indicator triad, bottom-of-Section placement, the `complete_section_ids` variable) — all retained as-is.
- ADR-027's `.section-end` wrapper and its visual-break treatment — retained; this ADR adds an `id` and a `scroll-margin-top` to it, nothing else.
- The single-user posture (manifest §5 / §6 / §7) — preserved.
- The read-only Lecture source rule (manifest §6, MC-6) — preserved (one route-handler line, one template attribute, one CSS property; no source writes).
- The persistence-boundary rule (MC-10) — preserved (no DB code changes).
- The no-JS form-handling shape (ADR-023 / ADR-025 / ADR-027 / ADR-028 / ADR-030) — **followed by this ADR**: the mechanism is route-handler + template + CSS only, no client-side code. (Following a clean recipe, not honoring a project rule — see ADR-035; the ADR-030 Option-2 / JS-posture-ADR contingency is now moot.)
- ADR-008 (CSS architecture) — followed faithfully: the `scroll-margin-top` rule goes on `.section-end` in `lecture.css` per the `section-*` → `lecture.css` prefix convention.
- ADR-010 (Playwright UI verification) — the binding Chromium target and the existing scroll-delta assertion are honored.
- ADR-024 (section-completion schema) — preserved; no schema change.
- ADR-026 (Chapter progress decoration) — preserved; the LHS rail's "X / Y" count is unchanged by the redirect-target change.
- AS-1 (Accepted-ADR content immutability) — honored: ADR-030 is not edited in place; this is a new superseding ADR.

## Manifest reading

Read as binding for this decision:

- **§3 Primary Objective.** Drive consumption + retention. The completion toggle is a consumption-tracking primitive; a toggle whose response snaps the user 30 viewports (ADR-025) or to the page top (ADR-030 Option 1) fights the reading flow. This mechanism leaves the user at the bottom of the Section they just finished — the toggle becomes a frictionless annotation on what was just read.
- **§5 Non-Goals.** "No mobile-first" — Chromium is the binding UI test target per ADR-010; `scroll-margin-top` is viewport-relative and degrades reasonably on short viewports, but a polished mobile experience is not promised; other browsers' fragment-scroll behavior is out of scope. "No LMS / no AI tutor / no remote deployment / no multi-user" — all orthogonal.
- **§6 Behaviors and Absolutes.** "Single-user" honored — no `user_id`; the route handler (consumed unchanged from ADR-025/ADR-027/ADR-030) has no auth. "AI work asynchronous" — orthogonal; completion is not AI work; the synchronous PRG (now with a `#section-{n}-end` anchor) is the correct shape for non-AI work. "Lecture source read-only" honored — one route-handler line, one template attribute, one CSS property; nothing under `content/latex/` is written. "Mandatory and Optional honored everywhere" — preserved; the completion toggle is per-Section regardless of designation; the LHS rail's M/O grouping is untouched.
- **§7 Invariants.** **"Completion state lives at the Section level."** — directly preserved. The redirect-target change does not touch where completion state lives or what it's bound to — only where the browser scrolls after the POST. "Chapter-level progress is derived from Section state" — preserved (ADR-026's derived "X / Y" decoration reads from the same Section-state data after the redirect). "Every … completion mark persists across sessions" — preserved (the PRG redirect's GET path reads completion state from persistence per ADR-024). "Mandatory and Optional are separable in every learner-facing surface" — preserved (the rail's M/O grouping and the Lecture page's badge are untouched).
- **§8 Glossary.** Section is "the atomic unit for … completion state. The unit of in-lecture navigation." — the affordance and the route remain per-Section; the supersedure changes only the redirect target's fragment (and a template id + a CSS property), not the Section's role. No new terms.

No manifest entries flagged as architecture-in-disguise. The supersedure is operational UX refinement, not a manifest-level change. The manifest is internally consistent with this decision.

## Conformance check

- **MC-1 (No direct LLM/agent SDK use).** Orthogonal — completion has no AI surface. This ADR introduces **no JavaScript at all**; the "is client JS an MC-1 matter?" question (it is not — MC-1 governs AI SDKs, not client JS) does not arise here. The ADR-030 Option-2 contingency is moot.
- **MC-2 (Quizzes scope to exactly one Section).** Orthogonal — no Quiz entity, no Quiz route.
- **MC-3 (Mandatory/Optional designation respects the canonical mapping).** Preserved by construction. The completion toggle is per-Section regardless of the parent Chapter's designation; no hardcoded chapter-number rule introduced; the LHS rail's M/O grouping is untouched.
- **MC-4 (AI work asynchronous).** Orthogonal — completion is not AI work; the synchronous PRG (with a `#section-{n}-end` anchor) is the correct shape for non-AI work; treating it as a violation would misread MC-4's scope.
- **MC-5 (AI failures surfaced).** Orthogonal — no AI in this surface.
- **MC-6 (Lecture source read-only).** Honored. The supersedure modifies `app/main.py`'s redirect line, `app/templates/lecture.html.j2`'s `.section-end` wrapper (adds an `id`), and `app/static/lecture.css`'s `.section-end` rule (adds `scroll-margin-top`), and updates Playwright/pytest test docstrings + assertions; nothing under `content/latex/` is opened for write. The route handler still *reads* `content/latex/{chapter_id}.tex` (to validate the Section ID) — read-only, identical to what ADR-003 / ADR-023 / ADR-025 / ADR-030 already do.
- **MC-7 (Single user).** Honored. The route handler and persistence layer (consumed unchanged from ADR-025/ADR-027/ADR-030) have no `user_id`, no auth, no session, no per-user partitioning.
- **MC-8 (Reinforcement loop preserved).** Orthogonal — no Quiz machinery; marking a Section complete does not trigger Quiz generation.
- **MC-9 (Quiz generation user-triggered).** Orthogonal.
- **MC-10 (Persistence boundary).** Honored. No DB code changes; the route handler calls only the typed public functions from `app/persistence/` (`mark_section_complete`, `unmark_section_complete`, `list_complete_section_ids_for_chapter`); no `sqlite3` import or SQL literal outside `app/persistence/` is introduced.
- **UI-1 / UI-2 / UI-3 (ui-task-scope).** UI-1 satisfied at the task level (TASK-012 declares the per-Section UI behavior change in scope). UI-2: this ADR touches CSS (a `scroll-margin-top` property on the existing `.section-end` class in the existing `lecture.css` file — no new class, no new file) and the template (one `id` attribute) and the route handler (one line) — all named here. UI-3 satisfied by the diff naming the modified files (`app/main.py`, `app/templates/lecture.html.j2`, `app/static/lecture.css`) and the amended Playwright/pytest tests.
- **UI-4 / UI-5 / UI-6 (rendered-surface verification gate).** Honored. ADR-010's Playwright harness covers the no-snap behavior (the scroll-delta-≤-200px regression test, retained from ADR-030 — now expected to pass); TASK-012's "Verification gates (human-only)" section records the rendered-surface review (clicking "mark complete" at the bottom of a tall Section does not produce a jarring scroll jump) as part of `rendered-surface verification — pass (TASK-012 RHS Notes rail + no-snap completion redirect)` in the audit Human-gates table.

Previously-dormant rule activated by this ADR: none.

## Consequences

**Becomes possible:**

- Marking (or unmarking) a Section complete from the bottom-of-Section affordance leaves the user ≈ where they clicked — the toggle is a frictionless annotation, not a navigation event. The ADR-030 Playwright scroll-delta assertion (which was failing) now passes.
- The completion route's redirect carries a self-documenting `#section-{n}-end` fragment that names the affordance the user interacted with — the redirect target is now legible.
- Future per-Section / per-Chapter PRG-based reading-flow affordances inherit the pattern: anchor the redirect at the affordance the user touched, and offset that element's scroll-snap position (`scroll-margin-top` or equivalent) so it lands back where it was — a no-JS recipe for "the response doesn't relocate the user."
- This mechanism adds no client-side JavaScript — but that is a fact about this surface, not a project-wide ban (see ADR-035; ADR-032 already forecasts the project's first client-side JS for a related Notes-save concern).

**Becomes more expensive:**

- (Almost nothing.) The route-handler change is one line; the template change is one attribute; the CSS change is one property. The Playwright assertion is unchanged (only its docstring updates). The TASK-012 "no fragment" pytest assertions are re-amended (routine ADR-driven test evolution per the test-writer pre-flag).
- A `scroll-margin-top` value that's too small leaves a residual jump; too large pushes `.section-end` below the fold on a short viewport. Mitigation: implementer-tunable, with the Playwright scroll-delta-≤-200px assertion as the lock, and the constraint that the affordance stays visible.

**Becomes impossible (under this ADR):**

- A completion toggle whose 303 redirect carries the `#section-{n}` *heading* anchor (ADR-025) — superseded by ADR-027 §placement + ADR-030 §principle + ADR-031 §mechanism.
- A completion toggle whose 303 redirect carries *no* fragment and relies on browser scroll-preservation (ADR-030 Option 1) — empirically refuted; replaced.
- A reading-flow-action response that relocates the user without naming why relocation is the action's meaning — ADR-030's load-bearing principle (retained here) governs.
- A *pressure forcing* client-side JavaScript onto the completion toggle (the ADR-030 Option-2 contingency) — moot; the no-relocate behavior is delivered by this no-JS mechanism per the human's explicit choice. (A future ADR could still add progressive-enhancement JS on top if a real need arises — that's allowed, just not needed; see ADR-035.)

**Future surfaces this ADR pre-positions:**

- Quiz-bootstrap's "Quiz this Section" affordance — its response (whatever it is) inherits ADR-030's principle: a reading-flow action's response leaves the user in place unless the action's meaning is navigation; if a PRG round-trip is the mechanism, the redirect anchors at the affordance the user touched (with a `scroll-margin-top` offset) per this ADR's recipe. ADR-027 already forecasts the Quiz affordance living in the same `.section-end` wrapper — which already carries the `id="section-{n}-end"` anchor, so a Quiz affordance there gets the same no-relocate behavior for free.
- A future "completed on …" timestamp display inside `.section-end` (surfacing the existing `completed_at` column from ADR-024) — its rendering is unaffected; the page re-renders with the user at the bottom of the Section, so the timestamp appears where the user is.
- If the project adds client-side JS for some other reason (e.g., the ADR-032 Notes-save concern), the completion toggle is a natural candidate for progressive enhancement on top — but the no-JS PRG path (this ADR's mechanism) remains the baseline, and there is no longer any pressure forcing the JS adoption here.

**Supersedure path if this proves wrong:**

- If `scroll-margin-top` proves unreliable in Chromium for the bottom-of-Section landing (caught by the Playwright scroll-delta assertion still failing after value-tuning) → a future ADR revisits the mechanism. The most likely next candidate would be the ADR-030 Option-2 client-side-JS path (its own ADR, deciding where the JS lives and how it's tested and tested-without), or some other no-JS approach. Cost: bounded; the diff is 3 lines.
- If the `#section-{n}-end` anchor proves to have some other unforeseen UX cost → a future ADR revisits the round-trip shape. Cost: bounded.
- If ADR-030's load-bearing principle proves too broad (some reading-flow action genuinely *should* relocate the user) → a future ADR carves the exception, naming why relocation is that action's meaning. The principle's burden is "name the reason," not "never relocate."

The supersedure is reversible (revert the redirect line, the template `id`, and the CSS property) at ~3-line cost if the mechanism also proves wrong. The empirical evidence — the Playwright failure proving Chromium does not preserve scroll on the fragment-less navigation, plus the human's explicit choice at the resolved stop — is the justification for this supersedure; future evidence (including the now-passing Playwright scroll-delta assertion's continued result) is the justification for any subsequent supersedure.
