# ADR-051: The graded-state and grading-failed-state rendering on the take page — `quiz_take.html.j2` gains `{% elif attempt.status == 'graded' %}` and `{% elif attempt.status == 'grading_failed' %}` branches; the `graded` branch renders an aggregate `<section class="quiz-take-grade">` block (score, Weak Topics list, recommended Sections list with anchor links to `{chapter_id}#section-{n-m}` per ADR-031), per-Question the existing read-only `response` / `preamble` / `test_suite` / `.quiz-take-results` blocks unchanged plus a new read-only `<div class="quiz-take-explanation">` block, and a per-Question correctness indicator (`.quiz-take-question-correct` / `.quiz-take-question-incorrect` modifier class); the `grading_failed` branch renders an honest `<section class="quiz-take-grading-failed">` block with the failure message + a small read-only `<details>` exposing the `grading_error` detail (the author *is* the learner; honesty over hiding); per-Question read-only blocks render unchanged; no fabricated Grade (MC-5); no submit form / no "Run tests" button (graded/failed Attempts are not `in_progress`); new `.quiz-take-grade-*` / `.quiz-take-explanation` / `.quiz-take-question-correct` / `.quiz-take-question-incorrect` / `.quiz-take-grading-failed` rules in `app/static/quiz.css` (reusing the `quiz-take-*` namespace per ADR-008; no new CSS file; no `base.css` change); the existing `in_progress` and `submitted` renders unchanged; the take-page route (ADR-038) reads the Grade via `get_grade_for_attempt` (ADR-050) and passes it to the template alongside the existing `attempt` / `attempt_questions` context

**Status:** `Accepted`
Auto-accepted by /auto on 2026-05-13
**Date:** 2026-05-13
**Task:** TASK-019
**Resolves:** part of `design_docs/project_issues/quiz-grading-slice-shape.md` (with ADR-048 + ADR-049 + ADR-050) — the "graded-state and grading-failed-state rendering" question, which ADR-049's "notified" obligation is realized through
**Supersedes:** none — consumes **ADR-038** (the take-page route pair and the three-column shell; this ADR adds a fourth render branch to the existing `in_progress` / `submitted` / "not ready" set, but does not change the route's path-param validation, the `start_attempt` / `submit_attempt` semantics, or the existing renders; the route gains one new persistence call to read the Grade for a `graded` Attempt), **ADR-039** (the `AttemptQuestion` carry-through this extends with the `is_correct` / `.explanation` fields ADR-050 added), **ADR-031** (the no-relocate `#section-{n-m}` anchor recipe — the recommended-Sections links cross-reference Sections via this anchor; the take page itself is reached via the existing `GET .../take` route, no new anchor on the take page), **ADR-008** (the `quiz-take-*` namespace posture and the per-surface CSS-file convention — this ADR adds new rules to the existing `app/static/quiz.css`, no new file, no `base.css` change; the surface "may add a third per-surface file" was triggered by ADR-038 for `quiz.css` and this slice's additions stay within that file), **ADR-035** (the "ADRs describe the architecture *used*, not a restriction of the toolkit" posture — this ADR does not introduce a "no JavaScript" or "always use no-JS" framing; the no-JS rendering choice here is "the no-JS shape was clean and sufficient", as is the existing pattern on every other surface), **ADR-049** (the "notified" obligation — this take-page state flip *is* the "notified" mechanism for this slice; ADR-049 makes the call to defer the active Notification entity, and this ADR is the surface that realizes it), and **ADR-050** (the `Grade` dataclass, the `get_grade_for_attempt(attempt_id) -> Grade | None` accessor, the `QuizAttempt.grading_error: str | None` field, the `AttemptQuestion.is_correct: bool | None` and `.explanation: str | None` fields the template reads). No prior ADR is re-decided.

## Context

ADR-049's processor walks a `submitted` Attempt through `grading → graded` (with a complete Grade persisted via ADR-050's `save_attempt_grade`) or `grading → grading_failed` (with the detail in `quiz_attempts.grading_error`). The take page is the surface where the learner sees the result — ADR-049's call ("the take-page state flip is the 'notified' mechanism for this slice; the active Notification entity is deferred") makes this surface load-bearing for §8 Notification. The take page already renders three Attempt states (`in_progress` / `submitted` / "not ready"); this ADR adds two more (`graded` / `grading_failed`).

The decision space:

- **The template's branching structure.** Add `{% elif attempt.status == 'graded' %}` and `{% elif attempt.status == 'grading_failed' %}` branches to `quiz_take.html.j2`'s existing `if/elif` chain. The existing `in_progress` and `submitted` branches are unchanged. The two new branches diverge only at the aggregate-block, per-Question explanation-block, correctness indicator, and the (failure-only) error-detail block — most of the per-Question content (the read-only `prompt` / `preamble` / `test_suite` / `response` / `.quiz-take-results`) is the same as the existing `submitted` render and naturally factors out as shared per-Question read-only content (Jinja macro or inline copy — implementer's call, not architecture).
- **The aggregate `<section class="quiz-take-grade">` block for the `graded` state.** Renders the score (`N / M` or `N` — implementer's call; the architectural commitment is "the score is visible at-a-glance near the top of the form area"), the Weak Topics list (a `<ul>` of plain-text tags; the relational vocabulary is deferred so there's nothing to link to yet — ADR-050), and the recommended Sections list (a `<ul>` of `<a href="/lecture/{chapter_id}#section-{n-m}-end">…</a>` links, using ADR-031's `#section-{n-m}-end` anchor recipe to land the learner where the Section ends rather than disrupting their position when they click). Position: above the per-Question loop (the aggregate is the headline, the per-Question detail is the breakdown).
- **The per-Question explanation block for the `graded` state.** A new read-only `<div class="quiz-take-explanation">` per Question, rendering `aq.explanation` (from `AttemptQuestion.explanation` per ADR-050) when not None. Position: within each `.quiz-take-question` block, near the `.quiz-take-results` panel (the explanation comments on the test result; visually adjacent makes the relationship clear). For an `is_correct = NULL` Question (defensive — `graded` should imply all `is_correct` are set per ADR-050, but a defensive render handles the case): no explanation block (rather than rendering an empty / "no explanation" placeholder — the absence carries the truth).
- **The per-Question correctness indicator.** A modifier class on the `.quiz-take-question` block (e.g. `.quiz-take-question-correct` when `aq.is_correct == True`, `.quiz-take-question-incorrect` when `aq.is_correct == False`) plus a small visible badge (a colored dot, a "Correct" / "Incorrect" pill, an icon — implementer's call within the existing color palette — see ADR-008's "the runner's `.quiz-take-results-pass` / `.quiz-take-results-fail` palette" precedent for the color choice; reusing those colors keeps the visual vocabulary coherent across "the runner says it passed" and "the Grade says it was correct" — which are the same truth per ADR-050's mapping).
- **The `grading_failed` state render.** An honest `<section class="quiz-take-grading-failed">` block at the top of the form area: a primary message ("Grading failed — try again on a new Attempt" or similar; implementer's call within the architectural commitment "the message is honest, not a fabricated Grade"), and a small read-only `<details>` element exposing the `attempt.grading_error` detail. Per-Question, the existing read-only blocks (`prompt` / `preamble` / `test_suite` / `response` / `.quiz-take-results`) render unchanged — no fabricated explanations, no correctness indicators (the `is_correct` is still NULL since `save_attempt_grade` rolls back on failure per ADR-050; the per-Question loop renders the runner's persisted test result honestly, which is the same content the `submitted` state renders).
- **The "show `grading_error` to the learner" question.** Two options: (a) hide it entirely behind the primary "Grading failed" message; (b) expose it in a small `<details>` (collapsible) block. The architect picks (b) — the author *is* the learner here (single-user, §5/§6), and the `grading_error` (the failure mode: rate limit, malformed response, etc.) is more useful to the author than a generic "something went wrong" hidden message; per MC-5's spirit (failures are visible and honest), exposing the detail in a collapsible block is more honest than hiding it. The collapsible (rather than always-shown) is so the visual hierarchy puts the primary message first and the technical detail second.
- **The `<details>`-with-`grading_error` element.** Plain HTML5 `<details>` + `<summary>`; no JavaScript needed (the browser handles the toggle natively); this is the no-JS shape that's "clean and sufficient" here (ADR-035 — describing what's built, not what's mandatory).
- **The route changes.** The existing `GET /lecture/{chapter_id}/sections/{section_number}/quiz/{quiz_id}/take` route in `app/main.py` already reads the latest Attempt via `get_latest_attempt_for_quiz` and passes it to the template. This ADR adds: a call to `get_grade_for_attempt(attempt.attempt_id)` when `attempt.status == 'graded'` (returns `Grade | None`; the template receives a `grade` context var that is the `Grade` dataclass or `None`), with the `attempt`'s `grading_error` already carried through the `QuizAttempt` dataclass (ADR-050 extension). No new route; no route-signature change.
- **The CSS rules.** New rules in `app/static/quiz.css` under the `quiz-take-*` namespace: `.quiz-take-grade`, `.quiz-take-grade-score`, `.quiz-take-grade-weak-topics`, `.quiz-take-grade-recommended-sections`, `.quiz-take-explanation`, `.quiz-take-question-correct`, `.quiz-take-question-incorrect`, `.quiz-take-grading-failed`, `.quiz-take-grading-failed-summary`, `.quiz-take-grading-failed-detail`. No `base.css` change; no new CSS file (ADR-008's "per-surface flat file" posture is already extended to `quiz.css` per ADR-038, and this slice's additions stay within that file).
- **JavaScript.** None needed (`<details>`/`<summary>` is native HTML; no fetch, no scroll-restore, no interactive behavior beyond the browser's). The no-JS rendering is "the clean and sufficient shape" per ADR-035; this ADR records *that* shape, not a no-JS posture.

The manifest constrains the decision through **§5** ("No live / synchronous AI results" — the render is what the learner sees *after* the processor has run, never inside a request that triggers the AI; "No AI tutor / chat interface for the learner" — the explanation is read-only commentary, not a chat interface; the page has no input field for replying to the explanation), **§6** ("AI failures are visible. If AI-driven processing fails, the failure is surfaced to the learner as a failure" — the `grading_failed` state shows the honest failure, never a fabricated Grade or hidden error; the `<details>`-exposed `grading_error` is the additional honesty), **§7** ("Every Quiz Attempt … persists across sessions" — the graded Attempt persists and the take page renders the same Grade on every revisit; "Every Question is a hands-on coding task" — the per-Question render shows the learner's `response` code, the `test_suite` code, the runner's verdict, and the LLM's commentary on the code — all coding-task content), and **§8** (the four Grade facets are rendered: per-Question correctness via the badge / modifier class; per-Question explanation via `.quiz-take-explanation`; aggregate score via `.quiz-take-grade-score`; Weak Topics via `.quiz-take-grade-weak-topics`; recommended Sections via `.quiz-take-grade-recommended-sections`; the Notification glossary is realized by the state flip from `submitted` to `graded` on `GET .../take`).

## Decision

### Template branching — `quiz_take.html.j2` gains `{% elif attempt.status == 'graded' %}` and `{% elif attempt.status == 'grading_failed' %}` branches

The existing `if/elif` chain in `quiz_take.html.j2` (rendering the `in_progress` / `submitted` / "not ready" states per ADR-038) extends to:

```
{% if attempt and attempt.status == 'in_progress' %}
  ... (unchanged — the take form with "Run tests" + "Submit" buttons; ADR-038, ADR-043, ADR-047)
{% elif attempt and attempt.status == 'submitted' %}
  ... (unchanged — the "Submitted — grading not yet available." state; ADR-038, ADR-043, ADR-047)
{% elif attempt and attempt.status == 'graded' %}
  ... (NEW — the graded state; see §The `graded` branch below)
{% elif attempt and attempt.status == 'grading_failed' %}
  ... (NEW — the grading-failed state; see §The `grading_failed` branch below)
{% else %}
  ... (unchanged — the "not ready to take" state for `requested`/`generating`/`generation_failed` Quizzes; ADR-038)
{% endif %}
```

The branches are mutually exclusive; the existing `in_progress` and `submitted` renders are unchanged. The new branches are additive — the test suite for the existing renders passes unchanged; new tests cover the two new branches.

### The `graded` branch — `<section class="quiz-take-grade">` aggregate + per-Question explanation + correctness indicator

The `graded` branch renders, in document order:

1. **The take-page header** (Section title, Chapter designation badge, "back to this Section" link) — unchanged from the existing `submitted`/`in_progress` branches; factored as a shared template chunk if useful, but the architect leaves the exact factoring to the implementer (it's a small render, not architecture).
2. **`<section class="quiz-take-grade">`** — the aggregate Grade block. Contains:
   - `<div class="quiz-take-grade-score">{{ grade.score }} / {{ attempt_questions|length }}</div>` — the score, visible at-a-glance. The denominator is the Attempt's Question count; the numerator is `grade.score` (recomputed from `SUM(is_correct)` per ADR-050 — the persisted truth). A perfect Attempt shows `5 / 5`; a partial Attempt shows `3 / 5`.
   - `<section class="quiz-take-grade-weak-topics">` (rendered only when `grade.weak_topics` is non-empty) — a heading "Weak Topics" and a `<ul>` of plain-text tags. (The relational Topic vocabulary is deferred per ADR-050; until the composition slice lands, there's nothing to *link* a tag to — plain text is the honest render.)
   - `<section class="quiz-take-grade-recommended-sections">` (rendered only when `grade.recommended_sections` is non-empty) — a heading "Recommended sections to re-read" and a `<ul>` of `<a href="/lecture/{chapter_id}#section-{n-m}-end">…</a>` links per recommended Section ID (ADR-002's composite form). Each link uses ADR-031's `#section-{n-m}-end` anchor (the no-relocate recipe pattern — the learner who clicks lands at the bottom of that Section's content, ≈ where they'd be after reading; the anchor target is the existing `.section-end` wrapper). The link text is the Section's number or title (implementer's call; mirrors how the rail lists Sections).
   - (Optional, implementer's call) A small `<time>` element showing `grade.graded_at` — "graded N minutes ago" — for the author's awareness. Not architecturally required; can be added without an ADR change.
3. **For each `AttemptQuestion` in `attempt_questions` (in `quiz_questions.position` order):**
   - A `<section class="quiz-take-question {% if aq.is_correct == True %}quiz-take-question-correct{% elif aq.is_correct == False %}quiz-take-question-incorrect{% endif %}">` wrapper — the modifier class drives the correctness indicator's visual treatment (color tint, side-border, badge — implementer's call within ADR-008's `quiz-take-*` palette; the existing `.quiz-take-results-pass` green / `.quiz-take-results-fail` red palette is the precedent, mirroring the runner's verdict visualization).
   - A visible badge or pill near the question heading: `<span class="quiz-take-question-correct-badge">Correct</span>` or `<span class="quiz-take-question-incorrect-badge">Incorrect</span>` (rendered conditional on `aq.is_correct`; absent when `aq.is_correct is None` — defensive; `graded` should mean every `is_correct` is set per ADR-050).
   - The existing per-Question read-only blocks:
     - `<p class="quiz-take-prompt">` — the Question's `prompt` text (unchanged).
     - `<pre class="quiz-take-preamble">` — the `preamble` (ADR-047), rendered only when non-empty (unchanged).
     - `<pre class="quiz-take-response-readonly">` — the learner's submitted `response` (unchanged).
     - `<pre class="quiz-take-test-suite">` — the Question's `test_suite` (ADR-043), rendered only when non-NULL (unchanged).
     - `<section class="quiz-take-results">` — the persisted test-run result (`.quiz-take-results-pass` / `.quiz-take-results-fail` / `.quiz-take-results-status` block per ADR-043, with the run output; unchanged).
   - A new `<div class="quiz-take-explanation">` block — renders `{{ aq.explanation }}` when `aq.explanation is not None` (ADR-050). The block carries an accessible heading ("Explanation" or similar; implementer's call). Position: after the `.quiz-take-results` panel (the explanation comments on the test result; visually adjacent makes the relationship clear).
4. **A "back to this Section" link** at the bottom — unchanged from the existing branches.

**No submit form. No "Run tests" button. No textarea.** Running tests is an `in_progress`-only action (ADR-043); submitting is `in_progress`-only (ADR-038); a `graded` Attempt is read-only. The form fields are absent; the per-Question response shows as `<pre class="quiz-take-response-readonly">`.

### The `grading_failed` branch — honest failure + collapsible `grading_error` detail

The `grading_failed` branch renders, in document order:

1. **The take-page header** — unchanged.
2. **`<section class="quiz-take-grading-failed">`** — the honest failure block. Contains:
   - `<p class="quiz-take-grading-failed-summary">` — the primary learner-facing message ("Grading failed for this Attempt — try again by submitting a new Attempt for this Quiz" or similar; the architectural commitment is "honest, not a fabricated Grade, and points the author at the recovery path: a new Quiz / Attempt").
   - `<details class="quiz-take-grading-failed-detail">` (rendered only when `attempt.grading_error` is non-NULL) — a collapsible disclosure with `<summary>Show technical detail</summary>` and a `<pre>` element rendering `attempt.grading_error` verbatim. The `<details>` defaults to closed (the summary is the only visible content until clicked); the failure-mode detail is one click away for the author to read, not hidden permanently. Native HTML; no JavaScript needed.
3. **For each `AttemptQuestion` in `attempt_questions` (in order):**
   - The existing per-Question read-only blocks (`prompt` / `preamble` / `response` / `test_suite` / `.quiz-take-results`) — unchanged. **No correctness indicator** (`aq.is_correct` is NULL since the persistence transaction rolled back; the modifier class is absent; no badge). **No `.quiz-take-explanation` block** (`aq.explanation` is NULL). The per-Question wrapper class is plain `.quiz-take-question` (no `-correct` / `-incorrect` modifier).
4. **A "back to this Section" link** at the bottom — unchanged.

**No submit form. No "Run tests" button. No fabricated correctness or explanation.** The `grading_failed` state is the honest "we tried to grade this and couldn't"; the runner's persisted test results are still there (the runner ran successfully before submit; the grading workflow failed, which is a separate step); the per-Question render shows those test results, exactly as the `submitted` state does — that's the truth.

### The route changes — `GET .../take` reads the Grade for a `graded` Attempt

The existing `take_quiz_page` handler in `app/main.py` (ADR-038):

- Validates `chapter_id` / `section_number` / `quiz_id` (unchanged).
- Reads the latest Attempt via `get_latest_attempt_for_quiz(quiz_id)` (unchanged); branches on its status (unchanged).
- For an Attempt with `status == 'graded'`: **new** — calls `get_grade_for_attempt(attempt.attempt_id)` (ADR-050; returns `Grade | None`; should never be `None` for a `graded` Attempt by ADR-050's transactional discipline, but the route handles `None` defensively — falling back to the same content the `submitted` state renders, which is a partial degradation that ADR-049's failure path should have prevented via `mark_attempt_grading_failed`; if it nevertheless happens, the take page renders the `submitted` content without a Grade rather than crashing).
- For an Attempt with `status == 'grading_failed'`: **new** — no new persistence call needed; `attempt.grading_error` is already on the `QuizAttempt` dataclass (ADR-050 extension).
- Passes the new `grade` context var to the template (`None` for non-`graded` Attempts, or for the defensive `graded`-but-no-`grades`-row degraded case).

No new route. No route-signature change. The route's path-param validation is unchanged. The route does **no** AI work (MC-4 trivially); does **not** generate a Quiz (MC-9); does **not** write under `content/latex/` (MC-6); does **not** transition any lifecycle state (the processor does that, ADR-049).

### The CSS rules — additive in `app/static/quiz.css`, reusing the `quiz-take-*` namespace

`app/static/quiz.css` gains new rules in the `quiz-take-*` namespace (no `base.css` change; no new file; ADR-008's per-surface posture extended unchanged):

- `.quiz-take-grade` — the aggregate block container (a card-like wrapper with a heading, a score, two lists; visually distinct from the per-Question blocks below).
- `.quiz-take-grade-score` — the score; large, readable.
- `.quiz-take-grade-weak-topics` and its `<ul>` / `<li>` descendants — the Weak Topics list.
- `.quiz-take-grade-recommended-sections` and its `<ul>` / `<li>` / `<a>` descendants — the recommended Sections list; the `<a>` styling matches the existing in-content link palette.
- `.quiz-take-explanation` — the per-Question explanation block (a small heading + the text; visually adjacent to `.quiz-take-results`, possibly indented or boxed to indicate "commentary on the result").
- `.quiz-take-question-correct`, `.quiz-take-question-incorrect` — modifier classes on the `.quiz-take-question` wrapper. The visual treatment reuses the runner's `.quiz-take-results-pass` (green) / `.quiz-take-results-fail` (red) palette per ADR-008 — a side-border, a tint, or a small badge. Implementer's call on the exact styling within that palette; the architectural commitment is "the indicator is visible at a glance and uses the same color vocabulary as the runner's verdict".
- `.quiz-take-grading-failed` — the honest-failure block container (a card-like wrapper, possibly with a subtle red-orange tint to indicate "this is the failure state", but the visual must not look like a fabricated Grade — implementer's call).
- `.quiz-take-grading-failed-summary` — the primary message; readable.
- `.quiz-take-grading-failed-detail` — the `<details>` element; `<summary>` styled as a small link or button; `<pre>` for the verbatim error monospace.

No JavaScript. No new fonts. No new images / SVGs (the correctness badges are CSS-only — a colored dot, a "Correct" / "Incorrect" pill rendered with CSS).

### Visual vocabulary — the runner's pass/fail palette extends to the Grade's correct/incorrect

ADR-044 / ADR-043's `.quiz-take-results-pass` (green) and `.quiz-take-results-fail` (red) palette is the runner's verdict visualization. ADR-050 maps `test_passed = True` to `is_correct = 1` and the runner's other states to `is_correct = 0` — so the runner-passed Questions and the graded-correct Questions are the same set, and conversely. Reusing the green/red palette on the `quiz-take-question-correct` / `quiz-take-question-incorrect` modifier classes makes this visually obvious: the same Question, the same color, the same truth — at the runner level and at the Grade level. (If a future supersedure decouples `is_correct` from `test_passed` — Alternative C of ADR-050 — the palette would split; for now, identical color vocabulary is the architecturally honest render.)

### Scope of this ADR

This ADR fixes only:

1. **The two new template branches** (`{% elif attempt.status == 'graded' %}` and `{% elif attempt.status == 'grading_failed' %}`) in `quiz_take.html.j2`; the existing branches unchanged.
2. **The `graded` branch's render shape:** aggregate `<section class="quiz-take-grade">` (score + Weak Topics list + recommended Sections list with ADR-031 anchor links); per-Question, the existing read-only blocks unchanged plus a new `<div class="quiz-take-explanation">` block and a correctness indicator via modifier classes / badge; no submit form / no "Run tests" button.
3. **The `grading_failed` branch's render shape:** honest `<section class="quiz-take-grading-failed">` block with primary message + a collapsible `<details>` exposing `grading_error`; per-Question, the existing read-only blocks unchanged (no correctness indicator, no explanation block, no submit form, no "Run tests" button).
4. **The route extension:** `GET .../take` calls `get_grade_for_attempt(attempt.attempt_id)` for a `graded` Attempt and passes the `grade` context var to the template; no new route, no signature change, no path-param-validation change.
5. **The new CSS rules** in `app/static/quiz.css`, reusing the `quiz-take-*` namespace; no `base.css` change; no new file; the runner's `.quiz-take-results-pass` / `.quiz-take-results-fail` palette extends to the Grade's correct/incorrect indicators.
6. **The architectural commitment on the failure render:** `grading_error` is exposed in a collapsible `<details>`, not hidden — the author is the learner; MC-5's spirit honored.
7. **The architectural commitment on what's *not* rendered:** no fabricated Grade in the `grading_failed` state; no correctness indicator in the `grading_failed` state; no per-Question explanation in the `grading_failed` state; no submit form / "Run tests" button in either of the new branches (graded/failed are not `in_progress`).
8. **No JavaScript** needed for either branch — the no-JS shape is "clean and sufficient" per ADR-035 (the `<details>` toggle is native HTML); this ADR does not introduce a "no JS" posture, just describes what this surface does.

This ADR does **not** decide:

- **The `grade_attempt` workflow's authoring surface** — owned by **ADR-048**.
- **The out-of-band processor's shape, lifecycle transitions, failure handling, `aiw run` invocation, "notified" obligation** — owned by **ADR-049**.
- **The Grade aggregate's persistence — the `grades` table, the `grading_error` column, the new persistence functions, the dataclass shapes, the `test_passed` → `is_correct` mapping, the score cross-check** — owned by **ADR-050**.
- **The active Notification entity** (a `notifications` table + chrome badge + `seen_at` lifecycle) — deferred per ADR-049 to a follow-on slice. This ADR realizes the take-page state flip that meets §8 Notification for this slice; the follow-on slice's render would add a chrome badge to `base.html.j2` and possibly a "you have a new Grade" notice on the take page itself (the integration shape is the follow-on slice's call).
- **A "Try grading again" button** on the `grading_failed` state — a future user-triggered surface; MC-9-compliant; not this slice. The collapsible `grading_error` detail surfaces *what* failed; a future button would let the author retry.
- **The relational Topic vocabulary** — deferred per ADR-050; Weak Topics render as plain text until the composition slice migrates them.
- **A "share my Grade" / "export my Grade" affordance** — out of scope; single-user; no use case.
- **A history of Grades across Attempts** for the same Quiz — out of scope; the take page renders the *latest* Attempt's Grade; a future surface might list all Attempts and their Grades.

## Alternatives considered

**A. Hide `grading_error` from the learner entirely (only the primary "Grading failed" message visible).**
Considered. Rejected on §6 / MC-5 grounds — single-user, the author is the learner; the failure-mode detail (rate limit, malformed LLM response, persistence error) is useful debugging information; hiding it forces the author to read the processor's stderr log, which they may not have kept. Exposing it in a collapsible `<details>` is the visible-but-not-loud shape — the primary message is the loud honest signal; the technical detail is one click away. MC-5's spirit (failures are visible and honest) is better served by the disclosure than the hide. The `<details>` is native HTML and adds no JS / CSS complexity.

**B. Always-shown `grading_error` (no `<details>` collapse).**
Considered. Rejected for visual hierarchy — the primary "Grading failed — try again" message should be the headline; a verbatim error string (which may be a multi-line stack trace, a long provider error, etc.) below the headline drowns the actionable signal. The `<details>` keeps the headline primary and the detail accessible. (A future tweak — show short errors inline, collapse long ones — is implementer's call; not architecturally fixed.)

**C. Split the `graded` branch's aggregate block into a separate "results summary" page on a different route.**
Rejected outright — the take page is the natural location ("the page where the learner sees the Quiz they took"); a separate "/result/{attempt_id}" route is needless surface; the take page renders the Quiz at every lifecycle state, the `graded` state included. Mirrors how ADR-038 chose to render `submitted` on the same route.

**D. JavaScript-driven progressive disclosure** (an animated reveal of per-Question explanations, a sortable Weak Topics list, an inline "Try grading again" fetch+update).
Rejected — out of scope and unnecessary. The no-JS render is clean and sufficient (the explanations are read-once, not interactive; the Weak Topics list is short; "Try grading again" is a future user-triggered button, MC-9-compliant, additive — and a server-side form-POST + PRG would be the conformant shape, not a `fetch()`). ADR-035 makes this an architecturally clean call ("no-JS where clean and sufficient, JS where genuinely needed"); the take-page render does not need JS.

**E. A single combined branch handling both `graded` and `grading_failed` with internal conditionals.**
Rejected for readability — the two states have very different shapes (an aggregate Grade vs an honest failure block; per-Question correctness indicators + explanations vs none of those) and Jinja's `{% elif %}` branching is the more readable shape. The shared per-Question read-only content (`prompt` / `preamble` / `response` / `test_suite` / `.quiz-take-results`) can be factored as a small Jinja `{% macro %}` if useful; implementer's call.

**F. Visual treatment of correctness via a separate column / aside / sidebar rather than a modifier class on the Question wrapper.**
Considered. Rejected — the per-Question wrapper modifier-class shape ties the correctness signal to the Question's content visually (color tint or side-border on the same block as the prompt, code, test suite, result, explanation) and keeps the three-column shell unchanged (LHS chapter rail, centered main, RHS Notes rail per ADR-029). A separate column / sidebar would either require a fourth column (too crowded on standard desktop widths) or push the rails out (architecturally invasive). The modifier-class shape is unobtrusive and reuses the runner's color palette.

**G. Reverse the position of the per-Question explanation and the `.quiz-take-results` panel.**
Considered (the explanation comments on the result; the result first then the explanation reads top-to-bottom as cause-then-commentary). Rejected as default: the result is *the answer to the question "did your code work?"* — the explanation is the *interpretation*; result-first matches the learner's natural reading order. Either order is defensible; the architect picks result-first; this is implementer-tweakable without architectural change.

**H. Render the per-Question explanation as a tooltip / hover-card instead of an inline block.**
Rejected — tooltips require JS (CSS-only `title` attributes are mobile-hostile and not learner-friendly for multi-paragraph commentary); the explanation is multi-line English text that's the point of grading; rendering it inline as a small block is the readable shape. Out of scope; no use case for hiding it.

**I. Show the score as a percentage instead of `N / M`.**
Considered. Rejected as default: `5 / 5` is clearer than `100%` for small Question counts (typical Quizzes are 3–6 Questions per the `question_gen` prompt); percentage is misleading for `1 / 3` (which is `33%` and reads as "you failed", but is in reality "you got one out of three on a small Quiz"). The `N / M` shape preserves the integer truth. (Implementer can layer both — `5 / 5 (100%)` — if useful; not architecturally fixed.)

## My recommendation vs the user's apparent preference

Aligned with the user's apparent preference, captured in TASK-019's task file (the "Architectural decisions expected" section forecasts this ADR with the shape "an aggregate-score block, per-Question explanation block, an `is_correct`-derived visual indicator, a green/red badge keyed to `attempt_questions.is_correct`, a `<section class="quiz-take-grading-failed">` honest-failure block, new `.quiz-take-grade-*` / `.quiz-take-explanation` / `.quiz-take-grading-failed` rules in `quiz.css`, reusing the `quiz-take-*` namespace per ADR-008; no new CSS file; no `base.css` change"), `quiz-grading-slice-shape.md`, ADR-031 (the no-relocate anchor recipe the recommended-Sections links reuse), and ADR-035 (the "no-JS where clean and sufficient" framing).

The architect's specific calls:

- **Reuse the runner's green/red palette for correctness indicators** — aligned with the user's framing ("the runner's `.quiz-take-results-pass` / `.quiz-take-results-fail` palette is the precedent — the grade's correct/incorrect colors may reuse it for consistency"); the architect makes this a definite call (reuse the palette by default) rather than an implementer-toss-up, because the visual vocabulary coherence is architecturally load-bearing for the §8 honest-rendering posture (the runner's verdict and the Grade's correctness are the same truth per ADR-050).
- **Expose `grading_error` in a collapsible `<details>`** — slightly more concrete than the task file's "`/design`'s call on whether to expose the `grading_error` detail to the learner" (the architect makes the call to expose, with reasoning).
- **Recommended-Sections links anchor to `#section-{n-m}-end`** (ADR-031's recipe), not `#section-{n-m}` — aligned with the principle ADR-031 established (the no-relocate landing); the recommended-Sections links are reading-flow actions (the learner clicks to re-read), and ADR-031's principle applies.
- **No JavaScript** — aligned with the user's apparent preference (the existing take page has no JS; ADR-035 makes "no-JS where clean and sufficient" the framing; the render needs none).

I am NOT pushing back on:

- **ADR-038's three-column shell** — consumed unchanged; the new branches render within the centered main column; the rails are unchanged.
- **ADR-008's per-surface CSS-file posture** — extended unchanged; the new rules live in `app/static/quiz.css`, reusing the existing `quiz-take-*` namespace.
- **ADR-031's no-relocate anchor recipe** — extended (the recommended-Sections links use `#section-{n-m}-end`).
- **ADR-049's "notified-by-state-flip" decision** — this ADR realizes it.
- **ADR-050's `Grade` dataclass, `get_grade_for_attempt` accessor, `QuizAttempt.grading_error` field, `AttemptQuestion.is_correct`/`.explanation` fields** — consumed unchanged.
- **MC-5 (no fabricated result)** — preserved: the `grading_failed` state shows the honest failure; no fabricated Grade; the score is the recompute (ADR-050).
- **MC-4 / MC-9** — preserved: the route does no AI work; the route does not generate a Quiz.

## Manifest reading

Read as binding for this decision:

- **§5 Non-Goals.** "No AI tutor / chat interface for the learner" — the explanation is read-only commentary; the page has no input field for replying to the explanation, no "ask a follow-up question" affordance, no conversational surface. "No live / synchronous AI results" — the render is what the learner sees *after* the processor has run, not in response to the request that submits.
- **§6 Behaviors and Absolutes.** "AI failures are visible. If AI-driven processing fails, the failure is surfaced to the learner as a failure" — the `grading_failed` state renders the honest failure; the collapsible `grading_error` `<details>` is the additional honesty (the failure mode is one click away, not hidden). "The system never fabricates a result to cover for it" — the `grading_failed` state has no fabricated Grade; the per-Question render shows the runner's verdict (which is real) without a fabricated correctness signal (`aq.is_correct` is NULL because ADR-050's transactional discipline rolled back); no fabricated explanation. "Code is written, run, and tested within the application" — the take page renders the learner's `response` code, the `test_suite` code, the runner's verdict, and the LLM's commentary on the code — all coding-task content. "Single-user" — no `user_id` in any rendered context.
- **§7 Invariants.** "Every Quiz Attempt … persists across sessions" — the rendered Grade persists; the take page renders the same Grade on every revisit (the `graded` Attempt doesn't change post-grading; the explanation, score, Weak Topics, recommended Sections are all read from the persisted columns). "Every Question is a hands-on coding task" — the per-Question render shows coding-task content; the explanation is *commentary on coding*, not a non-coding artifact.
- **§8 Glossary.** **Grade** — the take page renders all four facets: per-Question correctness via the modifier class and badge (derived from `is_correct`); per-Question explanation via `.quiz-take-explanation`; aggregate score via `.quiz-take-grade-score`; Weak Topics via `.quiz-take-grade-weak-topics`; recommended Sections via `.quiz-take-grade-recommended-sections`. **Notification** — "a learner-visible indication that an async AI result has become available (most commonly a Grade or a newly-generated Quiz)" — the take page's render branching from `submitted` to `graded` on next `GET .../take` is the learner-visible indication; per ADR-049's call, this is the "notified" mechanism for this slice; the active Notification entity is a follow-on slice. **Weak Topic** — rendered as plain text; the relational vocabulary is deferred per ADR-050; until the composition slice lands, the rendered list is honest (here are the Topics the workflow identified as weak) without a clickable cross-reference.

No manifest entries flagged as architecture-in-disguise for this decision. The template-branching shape, the CSS namespace, the `<details>`-vs-always-shown choice, the score-display form (`N / M` vs percentage), the correctness-indicator placement (modifier class vs separate column), and the no-JS render are all operational architecture the manifest delegates to the architecture document (manifest scope: "Technology choices, frameworks, data models, integration patterns, and implementation policies live in the architecture document").

## Conformance check

- **MC-1 (No direct LLM/agent SDK use) — ACTIVE.** Honored — `quiz_take.html.j2` and `app/static/quiz.css` are not Python modules and import nothing; the take-page route in `app/main.py` calls `app.persistence.get_grade_for_attempt` (a typed persistence function, no LLM SDK). **PASS.**
- **MC-2 (Quizzes scope to exactly one Section).** Honored — the take page renders one Attempt for one Quiz for one Section; no cross-Section render. **PASS.**
- **MC-3 (Mandatory/Optional designation respects the canonical mapping).** Honored — the take page header already renders the Section's parent Chapter's M/O designation badge (ADR-038, unchanged); the new branches do not modify it. **PASS** (manifest portion); **`cannot evaluate (ADR pending)`** for the mapping-source architecture portion.
- **MC-4 (AI work asynchronous).** Honored — the route does no AI work; the render is what the learner sees *after* the processor (ADR-049) has run, not in response to the request that submits or to a request that triggers grading. **PASS.**
- **MC-5 (AI failures surfaced, never fabricated).** Honored — the `grading_failed` state renders the honest failure (no fabricated Grade, no fabricated correctness, no fabricated explanation); the `grading_error` detail is exposed in a collapsible `<details>` (visible to the learner / author one click away); the `graded` state renders the persisted truth (the recomputed score from `SUM(is_correct)`, the per-Question explanations from the workflow, the Weak Topics from the workflow); MC-5's spirit is honored architecturally. **PASS.**
- **MC-6 (Lecture source read-only).** Honored — the take page reads from `data/notes.db` only; never touches `content/latex/`. **PASS.**
- **MC-7 (Single user).** Honored — no `user_id` in any rendered context, no auth, no session, no per-user partitioning. **PASS.**
- **MC-8 (Reinforcement loop preserved).** Honored — the take page renders the inputs the composition slice (next) will consume (the per-Question `is_correct` + the Grade's `weak_topics`); the take page does not change the composition path. **PASS.**
- **MC-9 (Quiz generation user-triggered).** Honored — the take page does **not** generate Quizzes; the `graded` and `grading_failed` branches contain no "Generate" / "Try grading again" / "Take this Quiz again" affordance this slice (deferred to a future slice if needed; a "Try grading again" affordance would be user-triggered and MC-9-compliant). **PASS.**
- **MC-10 (Persistence boundary) — ACTIVE.** Honored — the take-page route calls only typed public functions (`get_grade_for_attempt`, plus the existing `get_latest_attempt_for_quiz`, `list_attempt_questions`, etc.) from `app/persistence/__init__.py`; the template receives dataclasses; no `import sqlite3` or SQL literal anywhere in `app/main.py` or `app/templates/`. **PASS.**

Previously-dormant rule activated by this ADR: none.

## Consequences

**Becomes possible:**

- A learner sees their Grade on the take page: the score, the per-Question correctness indicators, the per-Question explanations, the Weak Topics, the recommended Sections. The §8 Grade is realized as a learner-visible artifact for the first time.
- The §6 loop closes one more notch — "the learner answers, runs, submits, sees a Grade with a learning signal" is now true end-to-end on real Questions for the first time (TASK-017 made the run real; TASK-018 made the test results meaningful; TASK-019 makes the Grade real).
- The `grading_failed` state renders honestly — the learner is not lied to with a fabricated Grade; the failure mode is one click away in the `<details>` block; the author can debug the failure quickly.
- The state flip from `submitted` to `graded` on next `GET .../take` is the §8 Notification mechanism for this slice (ADR-049's call); the learner returning to the take page sees the result, exactly as the per-Section status flip showed them "Ready" for the generation slice.
- The visual vocabulary across runner and Grade is unified (green/red palette for pass/fail at runner level and correct/incorrect at Grade level); the §8 commitment "correctness = test result" is reinforced visually.

**Becomes more expensive:**

- `quiz_take.html.j2` gains two branches; one extra context var (`grade`). Mitigation: additive; the existing branches are unchanged; the new branches mirror the `submitted` branch's per-Question read-only structure with one extra block (explanation).
- `app/static/quiz.css` gains ~10 new rules. Mitigation: all in the existing namespace; no new file; no `base.css` change.
- `app/main.py`'s take-page route gains one new persistence call (`get_grade_for_attempt`) and one new context-var pass. Mitigation: ~3 lines.
- The render is slightly more complex on `graded` Attempts (one aggregate block + the existing per-Question structure + the new explanation block + the modifier classes). Mitigation: the additional render cost is negligible (no DB calls per Question; the data is already in the `AttemptQuestion` dataclass and the `Grade` dataclass).

**Becomes impossible (under this ADR):**

- A take-page render that shows a `grading_failed` Attempt as graded (the template branches strictly on `attempt.status`; `grading_failed` falls into its own branch with no fabricated Grade).
- A take-page render that fabricates `is_correct` or `explanation` when they are NULL (the `graded` branch checks `is_correct is not None` / `explanation is not None` and renders only the persisted truth; the `grading_failed` branch does not render either at all).
- A take-page render that hides the failure mode from the author entirely (the `<details>` exposes `grading_error`; the author can read it without leaving the page).
- A submit form / "Run tests" button on a `graded` or `grading_failed` Attempt (the form / button is in the `in_progress` branch only).

**Future surfaces this ADR pre-positions:**

- **The active Notification entity** (a follow-on slice's concern) would add a chrome badge in `base.html.j2` that catches the learner wherever they are; a future addition to this ADR's render might be a small "you have a new Notification" notice on the take page itself, or this ADR's render path stays as-is and the chrome badge is the only addition. The follow-on slice's `/design` owns that.
- **A "Try grading again" button on the `grading_failed` state** — a future slice's addition; user-triggered (MC-9-compliant); the persistence side (ADR-050) is forward-compatible (a `reset_attempt_to_submitted(attempt_id)` function). This ADR's `grading_failed` branch is the natural place to add the button.
- **Clickable Weak Topics** — when the composition slice migrates to a relational `topics` table, the Weak Topics list could become links (to a future "Topic page" listing all Questions tagged with the Topic). Out of scope; the rendered list is forward-compatible (changing `<li>{{ topic }}</li>` to `<li><a href="/topic/{{ topic }}">{{ topic }}</a></li>` is mechanical).
- **A Grade history view** — a list of all `graded` Attempts for a Quiz, with their Grades; out of scope. The data is in `data/notes.db`; a future surface reads it.
- **Per-Question collapse / expand** — a future tweak if Quizzes grow large (a 6-Question Attempt's graded render is long); out of scope; the `<details>` element pattern extends naturally if needed.

**Supersedure path if this proves wrong:**

- If the `grading_error` `<details>` exposure proves too noisy or confusing → a future ADR can hide it (or move it to an author-only `/admin` page); the take page's user-facing render becomes the primary "Grading failed" message only. Bounded.
- If the modifier-class correctness indicator proves unclear (the green/red palette is too subtle, or color-blind users miss it) → a future ADR can add a more prominent badge or a text label; the modifier class stays as the data-attribute; the visual is updated. Bounded.
- If the take-page render becomes too long for `graded` Attempts → a future ADR could add per-Question collapse/expand or move some content to a separate "details" page; the data is forward-compatible. Bounded.
- If a future Notification entity slice requires structural changes to the take page (e.g. a "mark this Grade as seen" button) → that slice's `/design` adds them; this ADR's render is a structural-but-additive baseline. Bounded.
- If the `<details>` element proves to need JavaScript enhancement (animated reveal, programmatic open on hash anchor) → that's a future tweak; the no-JS baseline is correct. Bounded.

The supersedure path runs through new ADRs. This ADR does not edit any prior ADR in place; it consumes ADR-038 / ADR-039 / ADR-031 / ADR-008 / ADR-035 / ADR-049 / ADR-050 unchanged.
