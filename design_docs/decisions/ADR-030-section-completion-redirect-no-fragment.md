# ADR-030: Supersedure of ADR-025 §Round-trip-return-point — the section-completion 303 redirect drops the `#section-{n}` fragment so the toggle does not relocate the user

**Status:** `Superseded by ADR-031` (§Decision only — the "drop the `#section-{n}` fragment from the `303 Location` header; rely on Chromium preserving scroll on the fragment-less same-URL navigation" mechanism. **ADR-030's load-bearing principle — "the response to a reading-flow action should not relocate the user; completion is an annotation on what was just read, not a navigation event" — is RETAINED in full and is better honored by ADR-031's mechanism**, which ADR-031 cites rather than re-invents. ADR-030's "what of ADR-025 is retained" bookkeeping, its scoping of ADR-025 §Round-trip-return-point as superseded, its test-writer pre-flag's *intent*, and its no-JS commitment all remain accurate. See ADR-031 for the working mechanism: a `#section-{section_number}-end` anchor on the `.section-end` wrapper + a large `scroll-margin-top` on `.section-end` so fragment navigation lands the wrapper ≈ where the user clicked, no JavaScript.)
Original Acceptance: Auto-accepted by /auto on 2026-05-11
**Date:** 2026-05-11
**Task:** TASK-012
**Resolves:** `design_docs/project_issues/section-completion-prg-redirect-disrupts-scroll-position.md` (the *principle* portion — ADR-030 supplied "the response to a reading-flow action should not relocate the user"; the *mechanism* that delivers it is ADR-031's, after ADR-030's Option-1 mechanism was empirically refuted by the Playwright regression test ADR-030 itself mandated)
**Supersedes:** `ADR-025` (§Round-trip-return-point only — the `#section-{section_number}` URL fragment in the `303 Location` header; the route shape `POST /lecture/{chapter_id}/sections/{section_number}/complete` with form-encoded `action`, the form-handling pattern, the validation rules, the persistence integration, the state-indicator triad, and the styling-file ownership all remain Accepted as written by ADR-025 and as carried by ADR-027. **Note on the supersedure ledger:** ADR-025 was already `Superseded by ADR-027` for its §Template-placement portion; this ADR added a second, *narrower* supersedure pointer for its §Round-trip-return-point portion. The cleanest way to express this in `architecture.md`'s Superseded table is one row per superseding ADR: "ADR-025 §Template-placement → ADR-027" and "ADR-025 §Round-trip-return-point → ADR-030"; ADR-030's §Decision *mechanism* is in turn superseded by ADR-031, but ADR-025 §Round-trip-return-point remains `Superseded by ADR-030` — the decision *that the round-trip return point is no longer the heading anchor* stands; ADR-031 only changes *what the new return point is*.)
**Superseded by:** `ADR-031` (§Decision only — the no-fragment redirect mechanism. ADR-030's load-bearing principle, its ADR-025 bookkeeping, and its no-JS commitment are retained by ADR-031.)

> **Status note (2026-05-11, TASK-012):** ADR-030's §Decision chose "Option 1 — drop the `#section-{n}` fragment from the `303 Location` header" on the hypothesis that modern Chromium preserves the document's scroll position on a POST→303→GET navigation that lands on the same URL. ADR-030 mandated a Playwright regression test to lock that behavior in, and documented the contingency: if the test demonstrates Chromium does *not* preserve scroll, the fallback is Option 2 (client-side JS) via a human-gated JS-posture ADR. **The implementation phase ran that test and it failed** — Chromium resets `scrollY` to 0 (the top of the page) on the fragment-less same-URL navigation (`pre-click scrollY=3514px → post-reload scrollY=0px`). The `/auto` loop stopped and surfaced the failure to the human (audit Run 006). The human chose **neither** Option 1 (empirically the worst — snaps to page top) **nor** Option 2 (client-side JS — "a bunch of unneeded javascript for what we're building" for a single-user local reader); instead the human chose a no-JS mechanism: anchor the 303 redirect to `#section-{section_number}-end` (an `id` on the `.section-end` wrapper) + a large `scroll-margin-top` on `.section-end` so fragment navigation lands the wrapper ≈ where the user clicked (audit Run 007). That mechanism is recorded in **ADR-031**, which supersedes ADR-030 §Decision while retaining ADR-030's load-bearing principle (the principle is *better* honored by ADR-031's mechanism — the user ends up at the bottom of the Section they just finished, not at the top of the page).

## Context

ADR-025 (Accepted, auto-accepted by `/auto` on 2026-05-10) committed the section-completion toggle to a **POST → 303 → GET** PRG round-trip whose `303 Location` header included a `#section-{section_number}` URL fragment, intended to land the browser back at the just-toggled Section's heading via standard HTML anchor behavior. ADR-027 (Accepted, 2026-05-10) moved the completion *affordance* from inline-next-to-`<h2 class="section-heading">` (top of Section) to a `.section-end` wrapper at the **bottom** of each Section — and explicitly **did not revisit the redirect-target fragment** (ADR-027 §"What is NOT changed by this supersedure": "Round-trip return point. PRG 303 redirect to `GET /lecture/{chapter_id}#section-{section_number}` with the URL fragment for scroll-restoration. Unchanged. Note that the URL fragment now scrolls to the *top* of the Section…"). Both ADRs were committed in `3de9ab0` via TASK-011.

At post-commit review the human filed `design_docs/project_issues/section-completion-prg-redirect-disrupts-scroll-position.md` (Open, surfaced 2026-05-11), with the following framing **(quoted verbatim from the issue file as the empirical evidence justifying this supersedure):**

> "there is a bug with the completion bug didn't notice it where the button was placed before, it anchors you to the top of the section when you click complete which is a jarring experience"

— and on framing the fix:

> "or just no anchor, radical idea i know but we put it on the bottom of the section cause it was a natural flow while reading so don't mess with the users experience"

The mismatch the issue documents:

- The fragment-anchor behavior was *correct* under ADR-025: the affordance was at the **top** of the Section, the user clicked from the top, the redirect landed them at the top — ~zero scroll motion. The bug was masked by the placement.
- ADR-027 moved the affordance to the **bottom** of the Section but left the fragment unchanged. Now the user reads to the bottom of a tall Section (the corpus's longest Chapter renders to ~30+ viewport heights, per ADR-028's cited measurements), clicks "mark complete" at the `.section-end` wrapper, and the 303 redirect snaps them all the way *back up* to the Section heading — a ~30-viewport scroll jump to a position they did not ask for.
- The human's principle is binding regardless of mechanism: **the click at the bottom-of-Section affordance is a natural-flow reading-flow act; the response should not move the user.** Completion is an annotation on what the user just read, not a navigation event.

The issue file ruled out Options 4 (anchor to the `.section-end` wrapper instead of the heading) and 5 (anchor to the next Section's heading) by the human's principle ("don't mess with the users experience" — *any* anchoring is "messing with"). It named Option 1 (drop the fragment entirely) as "the smallest fix consistent with the principle, contingent on browser behavior," and Option 2 (introduce client-side JavaScript for an async no-navigation toggle) as "the cleanest UX but a real architectural commitment." The human's framing ("radical idea i know but … don't mess with the users experience") "strongly suggests Option 1 first — try the smallest change that respects the principle, fall back to JS only if browser behavior doesn't cooperate."

The decision space:

- **The mechanism:** Option 1 (drop the `#section-{n}` fragment from the 303 `Location`; rely on Chromium preserving scroll on POST→303→GET-same-URL); Option 2 (intercept the form with client-side `fetch()`, update the DOM in place, retain the no-JS PRG path as a fallback); Option 3 (JS-required, no fallback — rejected by the issue for the no-JS-fallback regression); Options 4/5 (anchor variants — ruled out by the human's principle).
- **If Option 2 is chosen:** a separate ADR committing to the client-side-JavaScript posture (where the JS lives, how it's loaded, how it's tested, whether the no-JS PRG fallback is retained), marked `Status: Proposed`, with `/design` ending on `> NEEDS HUMAN`.

The manifest constrains this decision through §3 (the completion toggle is a consumption-tracking primitive whose UX should not fight the reading flow), §5 ("no mobile-first" — Chromium is the binding test target per ADR-010; other browsers' scroll-preservation behavior is out of scope; "no LMS / no AI tutor / no remote deployment / no multi-user"), §6 (single-user; Lecture source read-only — one route-handler line changes, or — under Option 2 — one route-handler line plus a small static JS file), §7 (**"Completion state lives at the Section level"** — preserved: the redirect-target change does not touch where completion state lives, only where the browser scrolls to after the POST; "Every … completion mark persists across sessions" — preserved, no persistence change).

## Decision

### The mechanism — Option 1: drop the `#section-{n}` fragment from the `303 Location` header; rely on Chromium preserving scroll on the same-URL navigation; lock the behavior in with a Playwright regression test

The `POST /lecture/{chapter_id}/sections/{section_number}/complete` route handler stops emitting the `#section-{section_number}` fragment in its `303 See Other` `Location` header. The redirect target becomes simply:

```python
return RedirectResponse(url=f"/lecture/{chapter_id}", status_code=303)
```

— i.e., the same shape the Notes route already uses (`POST /lecture/{chapter_id}/notes` → `303 → GET /lecture/{chapter_id}`, no fragment, per ADR-023). Modern Chromium preserves the document's scroll position when a POST→303→GET navigation lands on the *same URL* the form was submitted from (the GET re-renders the page with the now-updated completion state; the browser keeps the user where they were). Because Chromium is the binding UI test target per ADR-010, this behavior is **testable**: the implementer's Playwright suite adds a regression test that (a) loads a Lecture page, (b) scrolls to the bottom of a tall Section, (c) records `window.scrollY`, (d) clicks the bottom-of-Section "mark complete" button, (e) waits for the navigation/re-render to settle, (f) asserts the post-reload `window.scrollY` is within a small tolerance of the pre-click value.

The architectural commitments are:

- The `303 Location` header for the completion toggle carries **no `#section-{n}` fragment** — just `/lecture/{chapter_id}`.
- A Playwright regression test asserts the post-toggle scroll position is preserved (within a small tolerance) for a click at the bottom-of-Section affordance on a tall Section.
- The no-JavaScript posture (ADR-023 / ADR-025 / ADR-027 / ADR-028) is **preserved** — Option 1 introduces no client-side code; it is a one-line route-handler change.
- Everything else about the route (shape, validation, persistence integration, the `action=mark|unmark` dispatch, the 303 status, the state-indicator triad) is unchanged.

**Why Option 1 is the design and not Option 2:**

- The human's framing — *"or just no anchor, radical idea i know"* — reads as an explicit preference for the *smallest* change that respects the principle. Option 1 *is* that change: one route-handler line, zero new code surface, the no-JS posture intact.
- Option 1 mirrors a pattern the project already runs: the Notes route has used a fragment-less `303 → GET /lecture/{chapter_id}` since ADR-023 with no scroll-disruption complaint. The completion route was the outlier in carrying a fragment; this ADR removes the outlier.
- The behavior is verifiable under the project's binding test target (Chromium / ADR-010), so "browser-dependent" is not an open risk here — it is a Playwright assertion.
- Option 2 would be the **first JavaScript in the project** — a permanent architectural commitment far larger than the immediate feature, deliberately avoided by ADR-023 / ADR-025 / ADR-027 / ADR-028. Crossing that threshold for a problem Option 1 solves would be disproportionate.

**The Option 2 contingency (NOT exercised by this ADR as written).** This `/design` cycle cannot run Playwright; the Playwright scroll-preservation assertion is produced and run in the test-writer / implementer phase, and the TASK-012 acceptance criteria already cover the case where Option 1's assertion fails. **If — and only if — the test-writer/implementer phase demonstrates via Playwright that Chromium does *not* reliably preserve scroll on the fragment-less same-URL navigation, the fallback is Option 2:** intercept the completion form with a small client-side `fetch()` handler that POSTs the form and updates the DOM in place (toggle the button label and `action` field; toggle the `section-complete` class on the `<section>`; update the LHS-rail `nav-chapter-progress` "X / Y" count per ADR-026), with the fragment-less no-JS PRG path (this ADR's Option 1) retained as the progressive-enhancement fallback for the JS-off case. **Option 2 requires a *separate, dedicated* `Status: Proposed` ADR committing to the client-side-JavaScript posture** — where the JS lives (`app/static/`), how it's loaded (a `<script>` tag in `base.html.j2`? a module?), how it's tested (Playwright with both JS-on and JS-off variants), and whether the no-JS PRG fallback is retained (forecast: yes — progressive enhancement, not JS-required; and the Notes form is explicitly *not* given the async treatment in that ADR — the Notes form's PRG round-trip does not have the snap problem because the form is in the rail, not at the bottom of a 30-viewport Section). That JS-posture ADR is gated by the human via `> NEEDS HUMAN`; the orchestrator must not cross the no-JS threshold on its own. Because this `/design` cycle defaults to Option 1, that JS-posture ADR is **not written here** and `/design` does **not** end on `> NEEDS HUMAN`. If the implementation phase forces the fallback, a new `/design` round (or a delta `/design`) writes the JS-posture ADR and the human gates it before implementation proceeds — exactly the routing the task file and the project_issue prescribe.

**Options 4 and 5 are rejected** by the human's principle ("don't mess with the users experience" — any anchoring, whether to the heading, the `.section-end` wrapper, or the next Section, is "messing with" the user's scroll position). **Option 3 (JS-required, no fallback) is rejected** for the no-JS-fallback regression (it removes the no-JS path entirely without the progressive-enhancement excuse, and makes the no-JS case untestable because it stops existing).

### What of ADR-025 is retained

ADR-025 made many decisions; this supersedure targets only §Round-trip-return-point — specifically the `#section-{section_number}` fragment in the 303 `Location` header. The following remain Accepted as written by ADR-025 (and as carried by ADR-027):

- **Route shape.** `POST /lecture/{chapter_id}/sections/{section_number}/complete` with a form-encoded `action` field (`"mark"` | `"unmark"`); `{section_number}` in the URL path; the route handler composes the full Section ID internally. Unchanged.
- **Form-handling pattern.** Synchronous PRG with no JavaScript; `303 See Other` on success; idempotent mark/unmark semantics (`mark` against an already-complete Section is a no-op; `unmark` against an already-incomplete Section is a no-op). Unchanged — only the redirect *target* drops the fragment.
- **Validation.** Route handler validates `chapter_id` against the discovered Chapter set (404 if unknown); validates `{chapter_id}#section-{section_number}` against the parent Chapter's discovered Sections (404 if unknown); validates `action` is exactly `"mark"` or `"unmark"` (400 otherwise). Unchanged.
- **Persistence integration.** Route handler calls `mark_section_complete` / `unmark_section_complete` from `app/persistence/`. Unchanged (ADR-024 schema unchanged).
- **State-indicator triad.** Button text (`✓ Complete` / `Mark complete`) + button color modifier + the `.section-complete` CSS class on `<section>`. Unchanged.
- **Template placement.** Bottom-of-Section, inside the `.section-end` wrapper — that is ADR-027's decision, *retained*. This ADR does **not** move the affordance again; it fixes the redirect side-effect ADR-027's relocation made jarring.
- **Styling file location.** `lecture.css` per ADR-008's prefix convention. Unchanged — this ADR is a one-line route-handler change; no CSS change.
- **The `complete_section_ids` template variable** passed to `lecture.html.j2` by the `GET /lecture/{chapter_id}` route. Unchanged.

The supersedure surface is narrow and surgical: the URL fragment in the 303 `Location` header. Everything else in ADR-025 (and ADR-027) stands.

### Load-bearing principle: the response to a reading-flow action should not relocate the user

This supersedure encodes a project-wide placement-quality principle, pairing with ADR-027's "action affordances follow the cognitive sequence" and ADR-028's "visibility follows scroll-position-cost":

> **The response to a reading-flow action should not relocate the user. An affordance placed at the natural reading position (per ADR-027) earns a response that leaves the user at that position — completion is an annotation on what was just read, not a navigation event. A page-reload (PRG) response keeps the user where they were; it does not snap them to an anchor.**

Concretely: ADR-027 correctly moved the completion affordance to the moment the learner has earned the right to claim completion (after reading, at the bottom of the Section). The *response* to that click must honor the same cognitive sequence — the learner has just finished reading, clicked, and is now done with this Section; the correct response is "the state flipped where you were," not "you have been teleported back to the heading." A scroll-anchor in the redirect contradicts the placement decision it was paired with. Future per-Section / per-Chapter action affordances (Quiz-bootstrap's "Quiz this Section" surface; any future grading/feedback display) inherit this principle: a reading-flow action's response leaves the user in place unless the action's *meaning* is navigation (e.g., "go to the next Section" — which the human explicitly ruled out for completion).

Reviewers should reject any new reading-flow-action response that relocates the user without naming why relocation is the *meaning* of the action.

### Test-writer pre-flag — the 303-Location-fragment assertion will fail by design

Per the user-memory entry **"Test updates forced by Accepted ADRs are routine"** and the TASK-012 task file's "Architectural concerns" section, the following test updates are anticipated when this supersedure becomes Accepted:

- **A pytest HTTP-protocol test** that asserted the `303 Location` header from `POST /lecture/{chapter_id}/sections/{section_number}/complete` includes `#section-{section_number}` will now fail. The test-writer amends it to assert the `Location` header is exactly `/lecture/{chapter_id}` (no fragment) — the same shape the Notes-route 303 test already asserts.
- **A Playwright completion-toggle test** will need a *new* assertion: after a "mark complete" click at the bottom-of-Section affordance on a tall Section, the post-reload `window.scrollY` is within a small tolerance of the pre-click `window.scrollY`. (This is the regression test that locks Chromium's scroll-preservation behavior in, per ADR-010's binding test target.)
- **Any existing Playwright completion-toggle test** that implicitly relied on the page scrolling to the Section heading after the toggle (e.g., asserting the Section heading is in the viewport post-toggle) will need amendment to the new behavior (the user stays where they were).

**The test-writer should NOT raise PUSHBACK for these failures.** They are the **routine ADR-driven test evolution** the user-memory entry describes:

> "When implementer ESCALATION is 'test fails because Accepted ADR-NNN changed the architecture,' amend the test directly; don't open project_issues or park the task."

The same routing applies preemptively to the test-writer phase: this supersedure ADR has named the redirect-target change as the architecture change; tests that depend on the prior fragment-carrying redirect are amended at the test-writer phase, not flagged as bugs. **The one exception is the Playwright scroll-preservation assertion itself:** if that assertion *fails* (i.e., Chromium does not reliably preserve scroll on the fragment-less same-URL navigation), that is the documented trigger for the Option 2 fallback — at which point the implementer escalates (`ESCALATION:` per CLAUDE.md) so a new `/design` round writes the JS-posture ADR and the human gates it. The test-writer does not silently switch to Option 2; the implementer does not silently introduce JS; the threshold is crossed only via a gated ADR.

### Scope of this supersedure ADR

This ADR fixes only:

1. The removal of the `#section-{section_number}` fragment from the `303 Location` header in the section-completion route handler — the redirect target becomes `/lecture/{chapter_id}`.
2. The requirement of a Playwright regression test that the post-toggle scroll position is preserved (within a small tolerance) for a bottom-of-Section click on a tall Section.
3. The retention of all other ADR-025 / ADR-027 commitments (route shape, validation, persistence integration, state-indicator triad, bottom-of-Section placement, styling file, the `complete_section_ids` template variable).
4. The encoding of the load-bearing placement-quality principle: the response to a reading-flow action should not relocate the user.
5. The test-writer pre-flag for routine ADR-driven test amendment, with the explicit Option-2-fallback trigger documented.

This ADR does **not** decide:

- Anything about the Notes panel's column placement — that is ADR-029's surface (the parallel supersedure of ADR-028 §Rail-integration).
- The adoption of client-side JavaScript. This ADR defaults to Option 1 (no JS). The Option 2 fallback (and its required separate, gated JS-posture ADR) is exercised *only if* the test-writer/implementer phase demonstrates Chromium does not preserve scroll on the fragment-less same-URL navigation — and even then, only via a new `/design` round and a human gate, not silently.
- Moving the completion affordance again. ADR-027 placed it at the bottom of each `<section>`; that is correct and retained.
- Any change to the `section_completions` schema (ADR-024) or the route-handler's mark/unmark logic. Only the redirect target changes.
- Async (JS) treatment of the Notes form. Out of scope here — the Notes form's PRG round-trip does not have the snap problem. (Under Option 2, the JS-posture ADR would explicitly keep the Notes form out of scope too.)
- Confirmation dialogs on unmark — none required (per ADR-025); unmarking is reversible.
- Mobile responsiveness — manifest §5 bounds the obligation; Chromium is the binding test target per ADR-010.

## Alternatives considered

**A. Option 4 from the project_issue: anchor to the `.section-end` wrapper (`#section-{n}-end`) instead of the heading.**

Rejected by the human's principle. Keeping the PRG-with-fragment pattern but pointing the fragment at the bottom of the Section (where the user clicked) would *usually* land the user near where they were — but the page still flickers (reload → browser scrolls back to the wrapper), and the human's framing rules out *any* anchoring ("don't mess with the users experience"). Option 4 makes the manipulation smaller, not absent; the principle wants it absent. Also requires adding an `id` to the `.section-end` wrapper, a template change Option 1 does not need.

**B. Option 5 from the project_issue: anchor to the next Section's heading (`#section-{N+1}`).**

Rejected. Reframes completion as "advance reading," which is a navigation semantics the human explicitly did not ask for ("don't mess with the users experience" — and the affordance's *meaning* is "I have read this," not "take me to the next one"). Contradicts the principle. Also breaks down at the last Section of a Chapter (no next Section to anchor to).

**C. Option 2 from the project_issue: async `fetch()` toggle with no navigation (introduces client-side JavaScript).**

Considered as the *fallback*, not the design. The cleanest UX (zero scroll motion, no flicker, no round-trip; the rail count updates instantly) — but it would be the **first JavaScript in the project**, a permanent architectural commitment far larger than the immediate feature, deliberately avoided by ADR-023 / ADR-025 / ADR-027 / ADR-028. **Rejected as the design** because Option 1 solves the problem with one route-handler line and a Playwright assertion, the no-JS posture intact, and matches the human's "smallest change that respects the principle" framing. **Retained as the contingency** only if the test-writer/implementer phase demonstrates Chromium does not preserve scroll on the fragment-less same-URL navigation — and even then, only via a separate, human-gated JS-posture ADR, never silently. (Per the task file's "Architectural concerns": "try Option 1 first … only fall back to Option 2 if Option 1 demonstrably fails the Playwright scroll-preservation assertion; if Option 2, write a separate, dedicated ADR for the JS posture, mark it `Status: Proposed`, and end `/design` with `> NEEDS HUMAN`." This `/design` cycle picks Option 1, so the JS-posture ADR is not written and `> NEEDS HUMAN` is not raised.)

**D. Option 3 from the project_issue: JS-required async, no PRG fallback.**

Rejected. Same JS commitment as Option 2, plus a regression on the no-JS posture without the progressive-enhancement excuse: the `<form>` becomes a `<button type="button">` that only works via JS, the no-JS case stops existing (and stops being testable), and the project's "trust the simplest mechanism" preference is rejected without strong reason. Even if the project ever adopts client-side JS, it should be progressive enhancement (Option 2), not JS-required (Option 3).

**E. Keep the fragment but add a `scroll-behavior: smooth` CSS rule so the snap is animated rather than instant.**

Rejected. An animated 30-viewport scroll is still a 30-viewport relocation the user did not ask for — it makes the manipulation prettier, not absent. The principle wants the user left in place.

**F. Bundle this supersedure with ADR-029 (the Notes-panel RHS-rail supersedure) as a single ADR.**

Considered carefully. Both supersedures arise from the same TASK-011 post-commit human review and the same TASK-012 `/design` cycle, and the two project_issues each name the other as the bundle target for the *task*. **Rejected for the ADR documents** for the same reasons ADR-027 and ADR-028 were kept as separate documents (their parallel Alternative I/K): each supersedure cites a different prior ADR (ADR-025 vs ADR-028), each addresses a different concern (whether the completion redirect carries a scroll-anchor fragment vs which rail the Notes panel lives in), each encodes a different load-bearing principle (this ADR: the response to a reading-flow action should not relocate the user; ADR-029: the corrected application of "visibility follows scroll-position-cost"), and citation discipline is cleaner with one supersedure per document — if either decision is later revisited, only one ADR moves. The task is one task / one `/design` cycle; the decisions are two ADRs. This matches the ADR-027/ADR-028 precedent exactly.

## My recommendation vs the user's apparent preference

The TASK-012 task file forecasts this supersedure with explicit framing:

> "Supersedure of ADR-025 §round-trip-return-point — the section-completion 303 redirect drops the `#section-{n}` fragment (Option 1). **Try Option 1 first.** Only if you have concrete reason to believe Chromium won't preserve scroll on POST→303→GET-same-URL should you fall back to Option 2 … Default to Option 1."

And the project_issue's framing:

> "The human's framing ('radical idea i know but … don't mess with the users experience') strongly suggests Option 1 first — try the smallest change that respects the principle, fall back to JS only if browser behavior doesn't cooperate."

This ADR **aligns with the forecast and the human's framing**: Option 1 (drop the fragment) is the design; Option 2 (client-side JS) is the documented contingency, exercised only on Playwright evidence and only via a separate human-gated ADR. The architect has **no concrete reason to believe Chromium won't preserve scroll** on the fragment-less same-URL navigation — the Notes route has used exactly this pattern since ADR-023 with no scroll-disruption complaint — so the architect picks Option 1 as the design and lets the test-writer/implementer phase produce the Playwright evidence. This `/design` cycle cannot run Playwright, so per the task file's instruction ("if you can't verify the browser behavior here, pick Option 1 as the design and let the test-writer/implementer phase produce the Playwright evidence — the task AC already covers the case where Option 1's assertion fails"), Option 1 is the design.

For each architect-pick decision:

- **The mechanism:** Option 1 — drop the `#section-{n}` fragment; redirect to `/lecture/{chapter_id}`; lock the scroll-preservation behavior in with a Playwright regression test. Aligns with the task forecast.
- **The Option 2 contingency:** documented but not exercised here. If the implementation phase forces it, a separate `Status: Proposed` JS-posture ADR is written in a new `/design` round and the human gates it. **`/design TASK-012` does not end on `> NEEDS HUMAN`** because Option 1 is the design.
- **The load-bearing principle:** "the response to a reading-flow action should not relocate the user," paired with ADR-027's and ADR-028's principles.
- **Citation discipline:** cite ADR-025 in `Supersedes:` (and note ADR-027's relationship — ADR-027 moved the affordance to the bottom and "did not revisit the redirect-target fragment"); quote the human's post-commit framing verbatim; explain that ADR-025's fragment was correct when the affordance was at the top (zero scroll motion) but became wrong when ADR-027 moved the affordance to the bottom.

For the **test-evolution pre-flag**, this ADR includes a dedicated "Test-writer pre-flag" section with the explicit Option-2-fallback trigger, matching the ADR-027 / ADR-028 precedent.

I am NOT pushing back on:

- The human's framing in the project_issue (verbatim quoted as the empirical evidence).
- ADR-025's / ADR-027's retained decisions (route shape, validation, persistence integration, state-indicator triad, bottom-of-Section placement, styling file, the `complete_section_ids` variable) — all retained as-is.
- The single-user posture (manifest §5 / §6 / §7) — preserved.
- The read-only Lecture source rule (manifest §6, MC-6) — preserved (one route-handler line; no source writes).
- The persistence-boundary rule (MC-10) — preserved (no DB code changes; the `mark_section_complete` / `unmark_section_complete` calls and the route handler's persistence interaction are unchanged).
- The no-JS commitment (ADR-023 / ADR-025 / ADR-027 / ADR-028) — **preserved by this ADR**: Option 1 introduces no client-side code. (The no-JS posture would be superseded *only* under the Option 2 contingency, *only* via a separate human-gated JS-posture ADR — which this `/design` cycle does not write.)
- ADR-008 (CSS architecture) — untouched; this is a route-handler change, not a CSS change.
- ADR-010 (Playwright UI verification) — extended faithfully: a new Playwright regression test for scroll preservation, against the binding Chromium target.
- ADR-024 (section-completion schema) — preserved; no schema change.
- ADR-026 (Chapter progress decoration) — preserved; the LHS rail's "X / Y" count is unchanged by the redirect-target change. (Under the Option 2 contingency, the JS handler would update it in place — but that's not this ADR.)
- ADR-027's load-bearing principle ("action affordances follow the cognitive sequence") — this ADR's principle is its natural completion: the *response* to the cognitively-sequenced action must also honor the sequence.

## Manifest reading

Read as binding for this decision:

- **§3 Primary Objective.** Drive consumption + retention. The completion toggle is a consumption-tracking primitive; a toggle whose response snaps the user 30 viewports away fights the reading flow and degrades the consumption experience. Dropping the fragment leaves the user where they were — the toggle becomes a frictionless annotation on what was just read.
- **§5 Non-Goals.** "No mobile-first" — Chromium is the binding UI test target per ADR-010; other browsers' scroll-preservation behavior is out of scope; the Playwright regression test locks the binding-target behavior in. "No LMS / no AI tutor / no remote deployment / no multi-user" — all orthogonal.
- **§6 Behaviors and Absolutes.** "Single-user" honored — no `user_id`; the route handler (consumed unchanged from ADR-025/ADR-027) has no auth. "AI work asynchronous" — orthogonal; completion is not AI work; the synchronous PRG (now fragment-less) is the correct shape for non-AI work. "Lecture source read-only" honored — one route-handler line changes; nothing under `content/latex/` is written. "Mandatory and Optional honored everywhere" — preserved; the completion toggle is per-Section regardless of designation.
- **§7 Invariants.** **"Completion state lives at the Section level."** — directly preserved. The redirect-target change does not touch where completion state lives or what it's bound to — only where the browser scrolls after the POST. "Chapter-level progress is derived from Section state" — preserved (ADR-026's derived "X / Y" decoration reads from the same Section-state data after the redirect). "Every … completion mark persists across sessions" — preserved (the PRG redirect's GET path reads completion state from persistence per ADR-024). "Mandatory and Optional are separable in every learner-facing surface" — preserved (the rail's M/O grouping and the Lecture page's badge are untouched).
- **§8 Glossary.** Section is "the atomic unit for … completion state. The unit of in-lecture navigation." — the affordance and the route remain per-Section; the supersedure changes only the redirect target's fragment, not the Section's role. No new terms.

No manifest entries flagged as architecture-in-disguise. The supersedure is operational UX refinement, not a manifest-level change. The manifest is internally consistent with this decision.

## Conformance check

- **MC-1 (No direct LLM/agent SDK use).** Orthogonal — completion has no AI surface. Note: this ADR introduces **no JavaScript at all** (Option 1); even the "is client JS an MC-1 matter?" question (it is not — MC-1 governs AI SDKs, not client JS) does not arise here. Under the Option 2 contingency, MC-1 would still be irrelevant — that would be a no-JS-posture supersedure, not an MC-1 matter.
- **MC-2 (Quizzes scope to exactly one Section).** Orthogonal — no Quiz entity, no Quiz route.
- **MC-3 (Mandatory/Optional designation respects the canonical mapping).** Preserved by construction. The completion toggle is per-Section regardless of the parent Chapter's designation; no hardcoded chapter-number rule introduced; the LHS rail's M/O grouping is untouched.
- **MC-4 (AI work asynchronous).** Orthogonal — completion is not AI work; the synchronous PRG (fragment-less) is the correct shape for non-AI work; treating it as a violation would misread MC-4's scope.
- **MC-5 (AI failures surfaced).** Orthogonal — no AI in this surface.
- **MC-6 (Lecture source read-only).** Honored. The supersedure modifies only `app/main.py`'s redirect line (and adds a Playwright test); nothing under `content/latex/` is opened for write. The route handler still *reads* `content/latex/{chapter_id}.tex` (to validate the Section ID) — read-only, identical to what ADR-003 / ADR-023 / ADR-025 already do.
- **MC-7 (Single user).** Honored. The route handler and persistence layer (consumed unchanged from ADR-025/ADR-027) have no `user_id`, no auth, no session, no per-user partitioning.
- **MC-8 (Reinforcement loop preserved).** Orthogonal — no Quiz machinery; marking a Section complete does not trigger Quiz generation.
- **MC-9 (Quiz generation user-triggered).** Orthogonal.
- **MC-10 (Persistence boundary).** Honored. No DB code changes; the route handler calls only the typed public functions from `app/persistence/` (`mark_section_complete`, `unmark_section_complete`, `list_complete_section_ids_for_chapter`); no `sqlite3` import or SQL literal outside `app/persistence/` is introduced.
- **UI-1 / UI-2 / UI-3 (ui-task-scope).** UI-1 satisfied at the task level (TASK-012 declares the per-Section UI behavior change in scope). UI-2: this ADR is a route-handler behavior change, not a CSS change — no new CSS to scope (ADR-029 scopes the CSS for the parallel layout change). UI-3 satisfied by the diff naming the modified file (`app/main.py`) and the new/amended Playwright test.
- **UI-4 / UI-5 / UI-6 (rendered-surface verification gate).** Honored. ADR-010's Playwright harness covers the new no-snap behavior (the scroll-preservation regression test); TASK-012's "Verification gates (human-only)" section records the rendered-surface review (clicking "mark complete" at the bottom of a tall Section does not produce a jarring scroll jump) as part of `rendered-surface verification — pass (TASK-012 RHS Notes rail + no-snap completion redirect)` in the audit Human-gates table.

Previously-dormant rule activated by this ADR: none.

## Consequences

**Becomes possible:**

- Marking (or unmarking) a Section complete from the bottom-of-Section affordance leaves the user where they were — the toggle is a frictionless annotation, not a navigation event.
- The completion route's redirect shape now matches the Notes route's redirect shape (`303 → GET /lecture/{chapter_id}`, no fragment) — one consistent PRG idiom across the project's two form-posting surfaces.
- The Playwright regression test locks Chromium's scroll-preservation behavior in, so a future change that re-introduces a scroll jump is caught.
- Future per-Section / per-Chapter action affordances inherit the new placement-quality principle ("the response to a reading-flow action should not relocate the user").

**Becomes more expensive:**

- (Almost nothing.) The route-handler change is one line. The new Playwright assertion is a small addition to the existing completion-toggle test.
- Existing tests that asserted the `303 Location` includes `#section-{n}`, or that the page scrolls to the Section heading post-toggle, will fail. Mitigation: per the test-writer pre-flag, these are routine ADR-driven test amendments.

**Becomes impossible (under this ADR):**

- A completion toggle whose 303 redirect carries a scroll-anchor fragment. The supersedure removes it.
- A reading-flow-action response that relocates the user without naming why relocation is the action's meaning. The load-bearing principle now governs.

**Future surfaces this ADR pre-positions:**

- Quiz-bootstrap's "Quiz this Section" affordance — its response (whatever it is) inherits this ADR's principle: a reading-flow action's response leaves the user in place unless the action's meaning is navigation.
- A future "completed on …" timestamp display inside `.section-end` (surfacing the existing `completed_at` column from ADR-024) — its rendering is unaffected; the fragment-less redirect re-renders the page in place, so the timestamp appears where the user is.
- If the project ever does adopt client-side JS (the Option 2 contingency, or any future ADR), the completion toggle is a natural first candidate for progressive enhancement — but the no-JS PRG path (this ADR's Option 1) remains the baseline.

**Supersedure path if this proves wrong:**

- If Chromium does *not* reliably preserve scroll on the fragment-less same-URL navigation (caught by the Playwright regression test in the implementation phase) → the Option 2 contingency: a separate, human-gated JS-posture ADR is written, and the completion form gets a progressive-enhancement `fetch()` handler with this ADR's Option 1 retained as the no-JS fallback. The threshold is crossed only via that gated ADR, never silently.
- If the no-fragment redirect proves to have some other unforeseen UX cost → a future ADR revisits the round-trip shape (e.g., the Option 2 contingency, or some other no-JS mechanism). Cost: bounded; the route-handler change is one line.
- If the load-bearing principle proves too broad (some reading-flow action genuinely *should* relocate the user) → a future ADR carves the exception, naming why relocation is that action's meaning. The principle's burden is "name the reason," not "never relocate."

The supersedure is reversible (re-add the `#section-{n}` fragment to the redirect line) at one-line cost if the no-fragment redirect also proves wrong. The empirical evidence from the human's post-commit review is the justification for this supersedure; future evidence (including the Playwright scroll-preservation assertion's result) is the justification for any subsequent supersedure.
