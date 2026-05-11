# Section-completion PRG redirect disrupts scroll position — clicking "mark complete" snaps the user away from where they clicked

**Status:** Open
**Surfaced:** 2026-05-11 (TASK-011 human post-commit review)
**Decide when:** the next task that touches per-Section UI behavior or the section-completion route — likely the same `/design` cycle that supersedes the LHS-vs-RHS Notes rail issue (`notes-surface-rhs-rail-supersedure-of-adr028.md`), since both are post-TASK-011 placement/UX corrections to ADR-027/028 and bundling avoids a second template/route-only `/design` round.

## Question

ADR-025 (now Superseded by ADR-027 §Template-placement only) committed to a **POST → 303 → GET** PRG (Post-Redirect-Get) round-trip for the section-completion toggle, with the redirect target including a URL fragment (`#section-N`) intended to land the user back at the heading of the just-toggled Section. ADR-027 moved the action affordance from inline-with-heading to a `.section-end` wrapper at the **bottom** of each Section but did not revisit the redirect-target fragment.

At post-commit review the human raised that the PRG redirect is **practically wrong for the user's experience**:

> "there is a bug with the completion bug didn't notice it where the button was placed before, it anchors you to the top of the section when you click complete which is a jarring experience" — and on framing the fix: "or just no anchor, radical idea i know but we put it on the bottom of the section cause it was a natural flow while reading so don't mess with the users experience"

The mismatch:

- The bug existed under ADR-025 (form was at the top of the Section, so the `#section-N` anchor mostly held position) but was **masked by the placement** — clicking from the top, landing at the top, ~zero scroll motion.
- ADR-027 moved the action to the bottom of the Section. The user now clicks at the bottom of, e.g., a 30-viewport-tall Section; the PRG redirect lands them at `#section-N` (the heading) at the top of the same Section. **Result: a 30-viewport scroll snap upward** to a position they did not ask for.
- The human's principle is binding regardless of mechanism: **the click at the bottom-of-Section affordance was a natural-flow reading-flow act; the response should not move the user.** The completion toggle is an annotation on what the user just read, not a navigation event.

This is a real bug that ADR-025's PRG-with-fragment design introduced and ADR-027 made dramatically more visible. ADR-027 should arguably have anticipated it; it did not.

## Options known

- **Option 1 — Drop the URL fragment from the PRG redirect.** Server returns `303 See Other` with `Location: /lecture/{chapter_id}` (no `#section-N`). Browser navigates to the same URL. Modern Chromium typically preserves scroll position on POST→303→GET-same-URL navigation, but **behavior is browser-dependent** — testable, not guaranteed. Pros: smallest possible change (one route handler edit); zero JS commitment; preserves the existing no-JS posture (ADR-023 / ADR-025 pattern). Cons: scroll-preservation is browser-dependent; Playwright would need a regression test that locks Chromium's behavior in (and the test target is Chromium per ADR-010, so this is testable); other browsers' behavior is out-of-scope per manifest §5 (no mobile-first; Chromium is the binding test target).
- **Option 2 — Async fetch with no navigation (introduces client-side JavaScript for the first time).** The form submit is intercepted by a small JS handler that POSTs via `fetch()` and updates the DOM in place: toggle the button label, update the rail's `nav-chapter-progress` "X / Y" count, toggle the `<section class="section-complete">` class. Progressive enhancement — the form still works without JS via the existing PRG fallback (Option 1's no-fragment redirect serves the no-JS case). Pros: cleanest UX (zero scroll motion, no flicker, no round-trip); the rail count update is also instant. Cons: introduces the **first JavaScript in the project** — a real architectural threshold the project has deliberately avoided (ADR-023 §Synchronous form posture; ADR-025 inherited the no-JS pattern). Requires a new ADR committing to JS (or to progressive enhancement), to where the JS lives (`app/static/`), to how it's loaded (one `<script>` tag in `base.html.j2`?), and to how it's tested (Playwright has both no-JS and JS-on test variants). Surface is small (one fetch + two DOM updates) but the *commitment* is permanent.
- **Option 3 — JS-required async (no PRG fallback).** Same as Option 2 but the no-JS form fallback is removed; `<form>` is replaced by a `<button type="button">` that only works via JS. Pros: smaller code surface (one path, not two). Cons: same JS commitment as Option 2 plus a regression on the no-JS posture without the progressive-enhancement excuse; harder to test the no-JS case (it stops existing); rejects the user-memory principle of "trust the simplest mechanism" without strong reason.
- **Option 4 — Anchor to the `.section-end` wrapper (`#section-N-end`) instead of the heading.** Keep the PRG-with-fragment pattern; just change the fragment target to land at the bottom of the same Section (where the user clicked). Pros: smallest change to ADR-025/027's mechanism; Chromium scroll-to-fragment is reliable. Cons: still does a small visible scroll motion on tall Sections (the user clicked while looking at the `.section-end` wrapper, the page reloads, the browser scrolls back to the same wrapper — usually correct but the page *flickers*). Doesn't solve the "don't manipulate the user" principle, just makes the manipulation smaller.
- **Option 5 — Anchor to the next Section's heading (`#section-{N+1}`).** Reframes completion as "advance reading." Pros: the user finished a Section, here's the next one. Cons: the human explicitly ruled out anchoring of any kind ("don't mess with the users experience"); contradicts the principle.

The human's principle ("don't mess with the user's experience") rules out Options 4 and 5. Option 1 is the smallest fix consistent with the principle, contingent on browser behavior. Option 2 is the cleanest UX but a real architectural commitment. Option 3 is rejected for the no-JS-fallback regression.

## Decide when (priority context)

The next task that touches per-Section UI behavior or the section-completion route. Since the LHS-vs-RHS Notes rail issue (`notes-surface-rhs-rail-supersedure-of-adr028.md`) is already on the project_issues list and also a TASK-011 post-commit finding, both should likely bundle into one follow-up task and one `/design` cycle.

A standalone "just delete the fragment" task is the wrong shape unless the architect picks Option 1 — in which case the follow-up is a one-line route handler change + a Playwright regression test. If the architect picks Option 2, a standalone "introduce JS posture + async completion" task is right-sized (one ADR for the JS commitment, one ADR for the completion-async behavior, one for Notes-async if we want symmetry).

The human's framing ("radical idea i know but … don't mess with the users experience") strongly suggests Option 1 first — try the smallest change that respects the principle, fall back to JS only if browser behavior doesn't cooperate.

## Cross-references

- ADR-025 §PRG-redirect-with-fragment (origin of the fragment behavior)
- ADR-027 §Template-placement (moved the affordance to the bottom, exposing the bug)
- ADR-023 §Synchronous form posture (the no-JS commitment Option 2/3 would supersede)
- `app/main.py` (the section-completion route handler that returns the 303)
- `tests/playwright/` (the natural home for the regression test that locks Chromium scroll-preservation behavior)
- `notes-surface-rhs-rail-supersedure-of-adr028.md` (parallel TASK-011 post-commit finding; bundle target for the next `/design` cycle)
