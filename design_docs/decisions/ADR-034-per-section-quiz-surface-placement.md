# ADR-034: Per-Section Quiz surface placement on the Lecture page — a Quiz block inside the `.section-end` wrapper at the bottom of each `<section>`, with an empty-state caption and a real user-triggered "Generate a Quiz for this Section" affordance that records a `requested`-status Quiz row

**Status:** `Accepted`
Auto-accepted by /auto on 2026-05-11
**Date:** 2026-05-11
**Task:** TASK-013
**Resolves:** none (no project_issue was filed against the per-Section Quiz surface placement; ADR-027 §Future-surfaces *forecast* the Quiz affordance living in/near the `.section-end` wrapper, but that is a forecast in ADR-027, not pre-allocated structure — this ADR decides the placement afresh, applying the placement-quality principles ADR-027/028/030 encoded, and reaches the forecast's conclusion as a *decision*)
**Supersedes:** none — ADR-027's `.section-end` wrapper, its bottom-of-Section placement of the completion form, its visual-break treatment, and ADR-031's `id="section-{n-m}-end"` + `scroll-margin-top` no-relocate mechanism are all *consumed unchanged*; ADR-022/024 are consumed unchanged; ADR-033 (the Quiz schema, Proposed in the same `/design` cycle) supplies the persistence shape this surface reads and writes. No prior ADR is re-decided.
**Superseded by:** none

## Context

TASK-013 ships the first vertical slice of the Quiz pillar — the Quiz domain model (ADR-033) + a per-Section Quiz read surface — with Quiz *generation* (the `ai-workflows` integration, async delivery, Notification, replay-+-fresh composition) deferred to the next task(s). This ADR decides where the per-Section Quiz surface goes on the Lecture page, what it renders, and whether a placeholder Quiz-trigger affordance ships.

The Lecture page is settled (TASK-009 Notes, TASK-010 section-completion, TASK-011 chapter-progress + placement supersedures, TASK-012 RHS Notes rail + no-snap completion redirect — all committed). The relevant established structure: `GET /lecture/{chapter_id}` parses the `.tex`, renders `lecture.html.j2` (which extends `base.html.j2` for the three-column layout: LHS chapter rail | centered `.page-main` | RHS Notes rail), passing per-Section data sets to the template (`complete_section_ids` per ADR-024, `rail_notes_context` per ADR-028); each `<section>` in `lecture.html.j2` carries `<h2 class="section-heading">`, `<div class="section-body">`, and a `<div class="section-end" id="{{ section.fragment }}-end">` wrapper (ADR-027) containing the completion `<form>`; `.section-end` carries a large `scroll-margin-top` in `lecture.css` (ADR-031) so a PRG redirect anchored at `#section-{n-m}-end` lands the user ≈ where they clicked, with no JavaScript. CSS layering per ADR-008: `section-*` / `lecture-*` / `callout-*` / `designation-*` classes → `lecture.css`; `page-*` / `nav-*` / `rail-*` → `base.css`.

The placement-quality principles binding on this decision (encoded by the post-TASK-010/011/012 supersedures):
- **ADR-027:** action affordances follow the cognitive sequence, not the template scope. A "mark complete" / "Generate a Quiz for this Section" affordance presupposes the learner has *read* the Section — so it belongs at the moment they've earned the right to act, not at the moment they first encounter the Section. ADR-027 §Future-surfaces forecasts: "The architect's forecast is that the Quiz affordance lives inside the same `.section-end` wrapper (alongside the completion form) so the bottom-of-Section becomes the standard per-Section action zone. Quiz-bootstrap's own ADR will commit to the precise shape." — that commitment is this ADR.
- **ADR-028:** visibility follows scroll-position-cost — a surface a user must scroll past the entire content to reach is, at scale, invisible *for an at-a-glance need*; but for an *after-reading* affordance, bottom-of-Section is exactly right (the cost of scrolling past the Section is the cost of *reading* it, which the affordance presupposes).
- **ADR-030's principle (retained by ADR-031):** the response to a reading-flow action should not relocate the user — completion (and, here, a Quiz request) is an annotation on what was just read, not a navigation event. If the affordance PRG-redirects, it anchors at the element the user touched (`#section-{n-m}-end`) and relies on `.section-end`'s `scroll-margin-top` to land them back where they were — the established no-JS recipe.

The decision space has materially different alternatives:

- **Placement in the reading flow:** inside the existing `.section-end` wrapper (alongside the completion form, at the bottom of each `<section>`); a separate `.section-quiz` block as a *sibling* of `.section-end` (also bottom-of-Section, but its own wrapper); a "Quizzes for this Section" header *above* the Section body; a per-Chapter Quiz-status decoration in a rail; a separate `GET /lecture/{chapter_id}/quizzes` page.
- **What the surface renders for the populated case:** a minimal list of each Quiz's status in plain language (scaffolded now); deferred entirely (only the empty-state ships, the populated case is the generation task's render concern).
- **Whether a placeholder Quiz-trigger affordance ships, and in what form:** (1) a real `POST /lecture/{chapter_id}/sections/{section_number}/quiz` route that inserts a `requested`-status `quizzes` row (no AI call) and PRG-redirects; (2) a disabled button / "coming next" caption with no route; (3) nothing — the empty-state is read-only this task.
- **CSS namespace:** `section-quiz-*` vs `quiz-*` vs reusing `section-*`.
- **The empty-state copy:** "No quizzes yet for this Section" vs other phrasings.

The manifest constrains the decision through §3 (per-Section Quizzes are a named consumption surface; the surface should read clearly in the reading flow), §5 ("No non-coding Question formats" — the surface introduces no Question-format chrome that implies multiple-choice etc.; "no AI tutor chat" — the surface is not a chat; "no live AI" — the surface makes no AI call), §6 ("Quizzes scope to Sections" — the surface is per-Section; "AI failures visible … never fabricates a result" — the surface never presents a `requested` Quiz as a finished one; "Mandatory and Optional honored everywhere" — the per-Section surface inherits the Chapter's designation via ADR-004's function, hides nothing; "Lecture source read-only" — template + CSS + a route-handler change; no source writes), §7 ("A Quiz is bound to exactly one Section"; "Quiz generation is always explicitly user-triggered" — the trigger fires only on the explicit user click; "Mandatory and Optional are separable in every learner-facing surface"), §8 (Quiz, Question, Question Bank, Quiz Attempt — consumed; the surface renders the Quiz lifecycle honestly per the §8 definitions).

## Decision

### Placement — a Quiz block inside the existing `.section-end` wrapper, at the bottom of each `<section>`, alongside the completion form

The per-Section Quiz surface is a new block rendered inside the `<div class="section-end">` wrapper of each `<section>` in `lecture.html.j2`, *after* the completion `<form>`. The `.section-end` wrapper becomes the standard per-Section *action zone* (the cognitive-sequence position ADR-027 named: read → act), now hosting two affordances: "mark/unmark complete" (ADR-027) and "Generate a Quiz for this Section" (this ADR), plus the per-Section Quiz status display.

```html
{% for section in sections %}
<section id="{{ section.fragment }}"
         class="{% if section.id in complete_section_ids %}section-complete{% endif %}">
  <h2 class="section-heading">{{ section.heading | safe }}</h2>
  <div class="section-body">
    {{ section.body_html | safe }}
  </div>
  <div class="section-end" id="{{ section.fragment }}-end">
    <form class="section-completion-form" method="post"
          action="/lecture/{{ chapter_id }}/sections/{{ section.section_number }}/complete">
      {# ... existing completion form, unchanged (ADR-027) ... #}
    </form>

    <div class="section-quiz">
      <h3 class="section-quiz-heading">Quizzes</h3>
      {% set section_quizzes = section_quizzes_by_id.get(section.id, []) %}
      {% if section_quizzes %}
        <ul class="section-quiz-list">
          {% for quiz in section_quizzes %}
          <li class="section-quiz-item section-quiz-item--{{ quiz.status }}">
            {{ quiz_status_label(quiz.status) }}
            {# 'requested' -> "Requested — generation pending"
               'generating' -> "Generating…"
               'ready' -> "Ready"   (no takeable affordance ships this task)
               'generation_failed' -> "Generation failed" #}
          </li>
          {% endfor %}
        </ul>
      {% else %}
        <p class="section-quiz-empty">No quizzes yet for this Section.</p>
      {% endif %}
      <form class="section-quiz-form" method="post"
            action="/lecture/{{ chapter_id }}/sections/{{ section.section_number }}/quiz">
        <button type="submit" class="section-quiz-button">Generate a Quiz for this Section</button>
      </form>
    </div>
  </div>
</section>
{% endfor %}
```

(Exact markup is implementer-tunable within the architectural commitments below — element nesting, heading levels, where the status label string is computed (a Jinja filter, a precomputed dict, or inline `{% if %}` chain — implementer's choice, but the *labels must be plain language and must not present a `requested`/`generating` Quiz as ready or takeable*). The status-label mapping above is the contract.)

**The architectural commitments:**

- The per-Section Quiz surface lives **inside the `<div class="section-end">` wrapper**, after the completion form — the same bottom-of-Section action zone, for the same cognitive-sequence reason (ADR-027): "Generate a Quiz for this Section" presupposes the learner has read the Section, so it belongs where the completion toggle is, not above the Section body.
- It is **per-Section**: one Quiz block per `<section>`, keyed by `section.id` (the full ADR-002 composite ID). There is no per-Chapter Quiz block, no rail Quiz decoration this task (MC-2 / §6: Quizzes scope to Sections; per-Chapter aggregations are a future query, not a stored entity or a shipped-now surface).
- With **zero Quizzes** for a Section, the surface shows an **empty-state caption** — "No quizzes yet for this Section." (the exact copy is the must-ship; minor wording is implementer-tunable, but it must read as "this is where Quizzes for this Section will live" and must not imply a Quiz exists).
- With **one or more Quizzes**, the surface shows a **list of each Quiz's status in plain language** — `requested` → "Requested — generation pending"; `generating` → "Generating…"; `ready` → "Ready"; `generation_failed` → "Generation failed". **No takeable affordance ships this task** even for a `ready` Quiz (the Quiz-taking surface is a later task; no TASK-013 path produces a `ready` row anyway). The list **never presents a `requested` or `generating` Quiz as a finished one** — MC-5's "never fabricated" obligation applied to the read surface (a `requested` row is honestly "we recorded your request," not a Quiz the learner can take).
- A **real, user-triggered "Generate a Quiz for this Section" affordance ships** — a `<form method="post" action="/lecture/{chapter_id}/sections/{section_number}/quiz">` with a single submit button, inside the `.section-quiz` block. See §The Quiz-trigger route below.
- **This surface needs no JavaScript.** It is template + CSS + a synchronous form post + a PRG redirect — the same shape the Notes and section-completion surfaces use because a no-JS recipe was clean and sufficient there, not because "no JavaScript" is a project rule. (Framing correction, not a decision change — this surface's mechanism is unchanged; see ADR-035, which establishes that ADRs describe the architecture *used* rather than restricting the toolkit, and that JavaScript is part of the available toolkit even though no-JS solutions are preferred where clean and sufficient.)

### The Quiz-trigger route — `POST /lecture/{chapter_id}/sections/{section_number}/quiz`, creates a `requested`-status Quiz row, PRG-redirects to `#section-{n-m}-end`

A new route handler in `app/main.py`:

```python
@app.post("/lecture/{chapter_id}/sections/{section_number}/quiz")
async def request_quiz_route(chapter_id: str, section_number: str) -> RedirectResponse:
    # 1. Validate chapter_id against the discovered set (ADR-024's pattern: tex_path.exists()).
    # 2. Validate section_number against the parsed Section set: compose
    #    section_id = f"{chapter_id}#section-{section_number}"; reject (404) if not in
    #    {s["id"] for s in extract_sections(chapter_id, latex_text)}.
    # 3. Persist: app.persistence.request_quiz(section_id)  -> inserts a quizzes row,
    #    status='requested', created_at=<now>; NO AI call, NO background job, NO
    #    quiz_questions rows, NO quiz_attempts row (ADR-033 §The `requested` status).
    # 4. PRG redirect: 303 -> /lecture/{chapter_id}#section-{section_number}-end
    #    (ADR-031's no-relocate mechanism, reused unchanged — the `.section-end`
    #    wrapper the user clicked in already carries id="section-{n-m}-end" and a
    #    large scroll-margin-top in lecture.css; the redirect lands the user back
    #    where they were).
```

Route shape rationale (mirrors the existing per-Section completion route — ADR-025/ADR-027/ADR-031 — for consistency): `POST /lecture/{chapter_id}/sections/{section_number}/quiz` is the natural sibling of `POST /lecture/{chapter_id}/sections/{section_number}/complete`; the Section ID is composed from path parameters and validated at the route handler against the parsed Section set (ADR-024's validation split — the persistence layer trusts the caller); no form body is needed (the action is unambiguous — "request a Quiz for this Section" — unlike completion's `mark`/`unmark`); the PRG 303 redirect reuses ADR-031's `#section-{n-m}-end` anchor + `scroll-margin-top` recipe so the request does not relocate the reader (ADR-030's principle, retained by ADR-031: a reading-flow action's response leaves the user where they were).

**Why a real route (Option 1), not a disabled affordance (Option 2) or nothing (Option 3):**

- **Option 1 is the genuine vertical slice.** TASK-013 is the first slice of the Quiz pillar; a vertical slice is schema + a route that writes it + a route that reads it + a template that renders it + tests. A read-only empty-state with no write path (Option 3) is closer to a horizontal layer (a schema + a static caption). The `requested`-status row gives the next task (`ai-workflows` generation) a concrete input — "here are the Quiz requests to process" — rather than starting from an empty table.
- **It does not fabricate anything (MC-5).** MC-5 forbids fabricating an *AI result* — a placeholder grade, a fabricated Question, a stand-in Notification. A `requested`-status `quizzes` row is none of those: it is honestly "the user clicked 'Generate a Quiz' and we recorded the request." No AI call is made; no Questions are produced; no Grade is invented; the read surface renders the row's status in plain language ("Requested — generation pending"), never as a finished Quiz. This is the same honest-state posture ADR-033 §The `requested` status commits to.
- **It is user-triggered (MC-9 / §7).** The route fires *only* on the explicit user click on the "Generate a Quiz for this Section" button. No background job, no scheduled task, no auto-trigger. Nothing auto-generates anything — the `requested` row sits until the next task's generation workflow (itself user-context-bound) processes it.
- **It makes no LLM SDK call (MC-1).** The route handler validates, calls `app.persistence.request_quiz`, and redirects. There is no AI dependency, no SDK import, no workflow invocation. MC-1's architecture portion stays `cannot evaluate (ADR pending)` — the AI-engine ADR is the next task's job; this route does not pre-empt it.
- **Option 2 (disabled/caption) is the safe-but-thin choice** — it ships a button that does nothing, which is a worse user experience than either a working button or no button (a disabled "coming next" button is a promise the surface can't yet keep). **Option 3 (nothing)** is the thinnest — a static empty-state — and would make the "vertical slice" claim weakest. The bounded risk of Option 1 (a `requested` row with no processor *if the next task slips*) is acceptable: the next task is explicitly scheduled, the row is honest, and worst-case it's a few `requested` rows in a single-user dev database — recoverable, not corrupting.

**If the next task slips** (the generation task is delayed): the `requested` rows accumulate harmlessly; the read surface keeps rendering them as "Requested — generation pending" honestly; no user is misled (the surface never claims a Quiz is ready); a future task can add a "cancel request" affordance if needed. This is a far smaller risk than the architecture-on-spec the project has rejected elsewhere (a Topic vocabulary with nothing reading it; an `ai-workflows` spike with no feature) — here there *is* a concrete next consumer, and the slice is vertical.

### What the surface renders — empty-state must-ship; the populated-case list scaffolded minimally now

- **Empty-state (must-ship):** "No quizzes yet for this Section." — a `<p class="section-quiz-empty">`.
- **Populated case (scaffolded minimally now):** a `<ul class="section-quiz-list">` of `<li>` items, one per Quiz, each showing the Quiz's status as a plain-language label per the mapping above. This is scaffolded *now* (rather than deferred to the generation task) because TASK-013's own placeholder trigger creates `requested` rows — so a populated case exists the moment the user clicks the button, and the surface must render it honestly. The *richer* populated rendering (a list of past Attempts and their Grades, once those exist) is deferred — the generation/grading tasks add it; this ADR's scaffold is "list each Quiz's status," nothing more.
- **No takeable affordance** for any status this task. A "take this Quiz" surface is a later task; no TASK-013 path produces a `ready` Quiz; the `ready` label is in the mapping only so the surface is forward-compatible (it shows "Ready" without offering a take-button — the take-button is the later task's addition).

### CSS — `section-quiz-*` namespace in `lecture.css` per ADR-008

The per-Section Quiz surface is a per-Section body element, so its CSS lives in `app/static/lecture.css` (ADR-008's `section-*` → `lecture.css` convention; `section-quiz-*` is a `section-*`-prefixed namespace, so it falls cleanly on the `lecture.css` side of the prefix split). New classes: `.section-quiz` (the block wrapper inside `.section-end`), `.section-quiz-heading`, `.section-quiz-list`, `.section-quiz-item` (+ `.section-quiz-item--{status}` modifiers for the four statuses, e.g. a muted color for `requested`/`generating`, a warning color for `generation_failed`), `.section-quiz-empty` (the empty-state caption), `.section-quiz-form`, `.section-quiz-button`. The block is visually a *footer-like* element of the Section (it lives inside `.section-end`, the visual end-of-Section zone) — distinct from the Section body, consistent with how the completion form is styled there. The exact colors/spacing/alignment are implementer-tunable within `lecture.css`; the namespace and the file are the architectural commitment. **No new CSS file; no `base.css` change** (the surface is not a rail decoration this task).

### `render_chapter` — one bulk Quiz query per request, mirroring `complete_section_ids` / `rail_notes_context`

`render_chapter` in `app/main.py` gains one call: `section_quizzes_by_id = app.persistence.list_quizzes_for_chapter(chapter_id)` (the bulk accessor ADR-033 commits to — `{section_id: [Quiz, ...]}` for every Section of the Chapter that has ≥1 Quiz), passed to the template as `section_quizzes_by_id`. This is the same shape as ADR-024's `complete_section_ids = set(list_complete_section_ids_for_chapter(chapter_id))` and ADR-028's `rail_notes_context` — one query per Lecture-page render, not one per Section. The template defaults missing keys to `[]` (Sections with no Quizzes), so the empty-state renders for them.

### What is NOT changed by this ADR

- **The `.section-end` wrapper, its `id="section-{n-m}-end"`, its `scroll-margin-top`, its visual-break treatment, its placement at the bottom of each `<section>`** — all unchanged (ADR-027, ADR-031). This ADR *adds* a `.section-quiz` block inside it; it does not move, re-style, or re-anchor the wrapper.
- **The completion form** (ADR-025/ADR-027/ADR-031) — unchanged; the Quiz block is rendered *after* it inside `.section-end`.
- **The three-column layout, the LHS chapter rail, the RHS Notes rail, the chapter-progress decoration** (ADR-006/008/026/028/029) — unchanged; this task adds no rail surface.
- **The `base.css` / `lecture.css` split** (ADR-008) — unchanged; `section-quiz-*` falls on the `lecture.css` side per the prefix convention.
- **The Notes surface, the section-completion route, the parser, discovery** — unchanged; this task only *adds* the per-Section Quiz surface.
- **`ai-workflows`** — not touched (the Quiz-trigger route makes no AI call; the AI-engine ADR is the next task's job; MC-1 architecture portion stays `cannot evaluate (ADR pending)`).
- **The parked ADR-032 (Notes-save scroll)** — not touched; this task does not touch the Notes form or the page-layout grid (the `.section-quiz` block lives inside `.section-end` in `.page-main`, not in a layout column), so ADR-032's "Decide when: a future task that touches the Notes form or the page layout" does not activate.

### Test-writer pre-flag — new tests; no existing test broken (this task only adds)

This task *adds* a per-Section surface and a route; it does not change any existing surface or route. So:

- **No existing test breaks by design.** The Notes/completion/rail/chapter-progress tests are untouched (the `.section-end` wrapper, the completion form, the layout — all unchanged). If an existing test fails after the implementer's change, that is a *regression* to fix, not routine ADR-driven evolution.
- **New pytest** (under `tests/`): HTTP-protocol tests for the per-Section Quiz surface render (each Section's Lecture page has a `.section-quiz` block with the empty-state present when no Quizzes; after a `POST .../quiz`, the surface lists the new Quiz with the `requested` status label and never presents it as ready); the `POST /lecture/{chapter_id}/sections/{section_number}/quiz` route (returns 303, `Location` ends with `#section-{section_number}-end`, creates exactly one `requested`-status `quizzes` row, makes no AI call — there is none to make; 404 on unknown `chapter_id`; 404 on unknown `section_number`); plus the ADR-033 schema/persistence tests (created/list round-trips, the MC-10 boundary grep, `section_id` validation, migration idempotency, no-`user_id`, Question-in-multiple-Quizzes).
- **New Playwright** (under `tests/playwright/`): each Section has a Quiz surface with the empty-state present; the surface renders on both a Mandatory Chapter and an Optional Chapter (M/O inheritance — the surface shows on Sections of both, nothing hides the split); the "Generate a Quiz for this Section" button is present and live; (welcome, not required) clicking it does not produce a jarring scroll jump (the same `#section-{n-m}-end` + `scroll-margin-top` mechanism the completion toggle's regression test locks — a fresh assertion here is in keeping with the project's test style, but the completion test already locks the mechanism).
- The test-writer should **not** raise `CANNOT TEST AC-N` on the rendered-surface-verification gate — that gate is correctly placed under TASK-013's "Verification gates (human-only; not programmatic ACs)" section, not under Acceptance criteria.

### Scope of this ADR

This ADR fixes only:

1. The placement of the per-Section Quiz surface: inside the existing `<div class="section-end">` wrapper, after the completion form, at the bottom of each `<section>` — the standard per-Section action zone (ADR-027's cognitive-sequence position).
2. What the surface renders: the empty-state caption ("No quizzes yet for this Section.") as the must-ship; a plain-language status list for the populated case (scaffolded minimally now, because the placeholder trigger creates `requested` rows); no takeable affordance for any status this task; the surface never presents a `requested`/`generating` Quiz as finished (MC-5 applied to the read surface).
3. The Quiz-trigger affordance: a real, user-triggered `POST /lecture/{chapter_id}/sections/{section_number}/quiz` route that calls `app.persistence.request_quiz(section_id)` (inserts a `requested`-status `quizzes` row — no AI call, no background job, nothing fabricated) and PRG-redirects (303) to `/lecture/{chapter_id}#section-{section_number}-end` (ADR-031's no-relocate recipe, reused unchanged). Route shape mirrors the per-Section completion route.
4. `render_chapter`'s one new bulk query (`list_quizzes_for_chapter(chapter_id)` → `section_quizzes_by_id`), mirroring `complete_section_ids` / `rail_notes_context`.
5. The CSS namespace and file: `section-quiz-*` classes in `app/static/lecture.css` (ADR-008); no new file; no `base.css` change.
6. The test-writer pre-flag (new tests; no existing test broken by design).

This ADR does **not** decide:

- The Quiz domain schema, the lifecycle enums, the Topic-tags column, the persistence module shape — owned by ADR-033 (Proposed in the same `/design` cycle).
- The `ai-workflows` integration mechanics, the workflow module path, the async-result-delivery mechanism, the replay-+-fresh composition logic — owned by the next task(s)' `/design`. The `requested` row this route creates is processed by the next task; this ADR's route does not pre-empt how.
- The Quiz-taking surface (where the learner writes code against a Question, response persistence, the "submit Attempt" route) — a later task; the `attempt_questions.response` column (ADR-033) is the slot.
- The Notification surface (the learner-visible "your Grade is ready" indication) — the async-delivery task.
- The richer populated-case rendering (past Attempts + their Grades) — the generation/grading tasks add it; this ADR's scaffold is "list each Quiz's status."
- Any per-Chapter Quiz-status decoration in a rail — out of scope (no consumer yet; architecture-on-spec); a later task with a real reason to surface per-Chapter Quiz status owns it.
- A separate `GET /lecture/{chapter_id}/quizzes` page — rejected (ADR-023 set the precedent that per-Section/per-Chapter surfaces live inside the Lecture page, not on separate routes).
- The exact empty-state copy beyond "must read as 'this is where Quizzes for this Section will live' and must not imply a Quiz exists" — minor wording is implementer-tunable.
- Confirmation dialogs on "Generate a Quiz" — none required (the action is reversible-ish — a future "cancel request" affordance can be added if `requested` rows pile up; for now, a stray `requested` row is harmless).

## Alternatives considered

**A. A separate `.section-quiz` block as a *sibling* of `.section-end` (also bottom-of-Section, but its own wrapper after `</div>` closes `.section-end`).**
Considered. The Quiz surface is arguably a distinct concern from the completion toggle, deserving its own wrapper. **Rejected** because (a) ADR-027 explicitly forecast "the Quiz affordance lives inside the same `.section-end` wrapper … so the bottom-of-Section becomes the standard per-Section action zone" — a sibling wrapper fragments that zone into two; (b) the `.section-end` wrapper already carries the `id="section-{n-m}-end"` anchor and the `scroll-margin-top` (ADR-031), so a Quiz-trigger affordance *inside* it gets the no-relocate behavior for free (a sibling wrapper would need its own anchor + `scroll-margin-top`, duplicating the mechanism); (c) one action zone per Section is the cleaner mental model — "the stuff you do after reading a Section is at the bottom of the Section, in one place." The `.section-quiz` block is a child of `.section-end`, not its sibling.

**B. A "Quizzes for this Section" header *above* the Section body.**
Rejected. Presupposes reading hasn't happened — fights the cognitive sequence (ADR-027): "Generate a Quiz for this Section" earns its place after the learner has read the Section, not before. A header above the body asks the learner to commit to a Quiz-request action before the act (reading) that gives it meaning — exactly the failure mode ADR-027 superseded the top-of-Section completion affordance for. Also: an above-body header pushes the Section content down and competes visually with the `<h2>` heading.

**C. A per-Chapter Quiz-status decoration in a rail (e.g., "Quizzes: N" on each chapter row in the LHS rail, like the chapter-progress "X / Y").**
Rejected for this task. No consumer yet — a per-Chapter Quiz-status surface needs a reason (what does "N Quizzes" tell the learner that the per-Section surface doesn't?), and there is none until the loop is running. Shipping it now is architecture-on-spec (the same anti-pattern the project rejected for a Quiz-status rail decoration in prior task files). And it would touch `base.css` (`rail-*` / `nav-*` namespace per ADR-008) and the rail-rendering path (ADR-006/026), expanding the surface area for no offsetting benefit. A later task with a real per-Chapter-Quiz-status need owns it. (Note: per-Chapter quiz aggregations, if ever surfaced, are *computed from per-Section results* per manifest §6 — a query, not a stored entity, and not a shipped-now surface.)

**D. A separate `GET /lecture/{chapter_id}/quizzes` page.**
Rejected. ADR-023 set the precedent that per-Section/per-Chapter surfaces (Notes, completion) live *inside* the Lecture page, not on separate routes — the learner stays on one page per Chapter. A separate Quizzes page fragments the Chapter's surfaces across routes, breaks the established navigation model, and forces a round-trip away from the reading flow to see a Section's Quizzes. The per-Section surface inside `.section-end` keeps everything for a Chapter on one page.

**E. Option 2 — a disabled "Generate a Quiz (coming next)" button / caption, no route.**
Considered (the task names it). Rejected. A disabled button is a promise the surface can't keep — it tells the learner "you'll be able to do this soon" without a "soon" the surface controls. It also ships *less* than Option 1 (a button that does nothing vs a button that records a request) while not being meaningfully *safer* (Option 1's worst case — a `requested` row with no processor if the next task slips — is harmless and recoverable; a disabled button's worst case is a stale "coming next" promise if the next task slips, which is *also* a bad look). Option 1 is the genuine vertical slice and is no riskier in practice.

**F. Option 3 — nothing; the per-Section surface is a read-only empty-state this task.**
Considered (the task names it as acceptable). Rejected as the weakest "vertical slice" — a schema + a static caption with no write path is close to a horizontal layer (the thing the project's task discipline rejects). The task itself flags this: "option (3) is the safest but thinnest." Option 1 ships a real write path (the `requested`-row route), making the slice genuinely vertical, at acceptable bounded risk. If the architect's read were that the placeholder-trigger fork should go to the human, this is where a `> NEEDS HUMAN` would land — but the task's framing grants the architect the authority, the risk is bounded, and Option 1 is the right call; no escalation.

**G. CSS namespace `quiz-*` instead of `section-quiz-*`.**
Considered. `quiz-*` is shorter. **Rejected** because ADR-008's prefix split routes `section-*` → `lecture.css` and a bare `quiz-*` prefix is not in ADR-008's enumerated set (it would need a new line in the prefix convention, and a future per-Chapter or rail Quiz surface might want `quiz-*` for *its* classes, creating a collision). `section-quiz-*` is unambiguously a `section-*`-prefixed namespace → `lecture.css`, no ADR-008 amendment needed, no collision with a future non-per-Section Quiz surface. Keeping the surface's classes inside the `section-*` family is the right call for a per-Section surface.

**H. Render the populated case as a list of past Attempts + their Grades now (not just Quiz statuses).**
Rejected for this task. No Attempts exist (the Quiz-taking surface is a later task) and no Grades exist (the grading task is a later task) — so a "list of past Attempts + Grades" rendering would render nothing this task, which is exactly the empty-state. Scaffolding it now (with no data to render) is speculative. The minimal scaffold this ADR ships — "list each Quiz's status" — *does* have data to render (the placeholder trigger creates `requested` rows), so it's the right level. The generation/grading tasks add the richer rendering when there's data for it.

**I. Confirmation dialog on "Generate a Quiz for this Section" (to prevent accidental requests).**
Rejected. A confirmation dialog would need either JavaScript (which this surface otherwise has no need for — not a hard "no", see ADR-035, just not warranted here) or a two-step server round-trip (a "confirm?" page — heavy for a low-stakes action). A stray `requested` row is harmless (it's a single-user dev database; the next task's generation workflow processes whatever's there; a future "cancel request" affordance can be added if needed). The action is low-stakes enough that no confirmation is warranted — same as "mark complete" (which also has no confirmation per ADR-025).

## My recommendation vs the user's apparent preference

The TASK-013 task file forecasts this ADR with explicit framing: "Per-Section Quiz surface placement on the Lecture page — where the Quiz block goes in the reading flow, what it renders, and whether a placeholder trigger ships." It names the placement forecast ("in or near the `.section-end` wrapper per ADR-027 §Future-surfaces — but `/design` decides afresh"), the rendering ("an empty-state caption … a list of past Quiz Attempts and their statuses/Grades — the rendering shape for the populated case can be scaffolded minimally now or deferred — `/design` decides; the empty-state is the must-ship"), the CSS file/namespace ("`lecture.css` … under a `quiz-*` / `section-quiz-*` namespace per ADR-008"), and — the genuine fork — the three placeholder-trigger options, with the instruction: "The architect should name in 'My recommendation vs the user's apparent preference' which option was chosen and why."

This ADR is **aligned with the task's forecast**, with these `/design` calls made:

- **Placement — inside the `.section-end` wrapper (ADR-027's forecast, reached as a decision).** The architect applied the placement-quality principles afresh: ADR-027's cognitive-sequence ("Generate a Quiz" presupposes reading → bottom-of-Section action zone, like the completion toggle), ADR-028's scroll-position-cost (an after-reading affordance correctly sits past the Section content), ADR-030's no-relocate (the trigger PRG-redirects with ADR-031's `#section-{n-m}-end` + `scroll-margin-top` recipe, leaving the user where they were). The conclusion matches ADR-027's forecast — *as a decision*, not as inheritance: the `.section-quiz` block is a child of `.section-end`, making it the standard per-Section action zone. No disagreement to surface.
- **What it renders — empty-state must-ship; populated case scaffolded minimally (status list).** The architect chose to scaffold the populated case *now* (rather than defer it) because the placeholder trigger creates `requested` rows — so a populated case exists the moment the user clicks the button, and the surface must render it honestly (MC-5 applied to the read surface). The richer rendering (Attempts + Grades) is deferred to the tasks that produce that data. Aligned with the task's "the rendering shape for the populated case can be scaffolded minimally now or deferred — `/design` decides; the empty-state is the must-ship."
- **CSS — `section-quiz-*` in `lecture.css`.** The architect chose `section-quiz-*` over the task's alternative `quiz-*` (rationale: §Alternative G — `section-quiz-*` is unambiguously a `section-*`-prefixed namespace per ADR-008, no convention amendment, no collision with a future non-per-Section Quiz surface). Aligned with the task's "`lecture.css` … per ADR-008."
- **The placeholder Quiz-trigger fork — Option 1 (real `requested`-row route).** The architect chose Option 1 (a real, user-triggered `POST .../quiz` route that inserts a `status='requested'` Quiz row — no AI call, no background job, nothing fabricated — and PRG-redirects with ADR-031's no-relocate recipe) over Option 2 (disabled/caption) and Option 3 (nothing). **Why:** Option 1 is the genuine vertical slice (schema + write route + read route + template + tests, vs Option 3's schema + static caption ≈ horizontal layer); it gives the next task (`ai-workflows` generation) a concrete input ("here are the Quiz requests to process"); it does not violate MC-5 (a `requested` row is honestly "we recorded your request," not a fabricated AI result — MC-5 is about fabricating *AI results*, and no result is fabricated, no AI is called); it is user-triggered (MC-9 / §7 — fires only on the explicit click); it makes no LLM SDK call (MC-1 — no AI dependency, the architecture portion stays `cannot evaluate (ADR pending)`); and its worst case (a `requested` row with no processor if the next task slips) is harmless and recoverable in a single-user dev database. Option 2 ships less while being no safer; Option 3 ships least and weakens the vertical-slice claim. **The architect does not route this to `> NEEDS HUMAN`** — the task's framing explicitly grants the architect the authority ("the task's framing gives the architect the authority to pick"), the risk is bounded, and Option 1 is clearly right; escalating a decision the task asked the architect to make would be the wrong move. (The schema side of the `requested` row is in ADR-033 §The `requested` status; this ADR owns the route + template + the honest-rendering posture.)

I am NOT pushing back on:

- ADR-027's `.section-end` wrapper, its bottom-of-Section placement, its visual-break treatment, the load-bearing cognitive-sequence principle — all consumed unchanged; the `.section-quiz` block is added inside the wrapper.
- ADR-031's `id="section-{n-m}-end"` + `scroll-margin-top` no-relocate mechanism — consumed unchanged; the Quiz-trigger route's PRG redirect reuses it (anchors at `#section-{section_number}-end`).
- ADR-030's principle ("the response to a reading-flow action should not relocate the user") — honored: the Quiz request is an annotation on what was just read, not a navigation event; the redirect leaves the user where they clicked.
- ADR-008's CSS layering — followed: `section-quiz-*` → `lecture.css`; no new file; no `base.css` change.
- ADR-024/ADR-028's per-Section-data-set pattern (`complete_section_ids`, `rail_notes_context`) — mirrored: `section_quizzes_by_id` is one bulk query per render.
- ADR-024's validation split (route handler validates the Section ID against the parsed set; persistence trusts the caller) — mirrored by the Quiz-trigger route.
- ADR-025/ADR-027/ADR-031's per-Section completion route shape — mirrored: `POST /lecture/{chapter_id}/sections/{section_number}/quiz` is the natural sibling of `.../complete`.
- The no-JS form-handling shape the Notes and section-completion surfaces use (ADR-023/025/027/028/029/030/031) — followed here too, because a synchronous form post + PRG redirect is clean and sufficient for this surface; no client-side code is needed. (Not a constraint future surfaces must honor — see ADR-035; the no-JS recipe is the preference where it is clean, not a project invariant.)
- The single-user posture (manifest §5 / §6 / §7, MC-7) — preserved: the route has no `user_id`, no auth, no session; the surface has no per-user logic.
- The read-only Lecture source rule (manifest §6, MC-6) — preserved: template + CSS + a route-handler change; the route *reads* `content/latex/{chapter_id}.tex` (to validate the Section ID), read-only, identical to the completion route; nothing under `content/latex/` is written.
- The persistence-boundary rule (MC-10, active per ADR-022) — preserved: the route calls only `app.persistence.request_quiz` / `list_quizzes_for_chapter` (typed public functions); no `sqlite3` import or SQL literal in `app/main.py` or the template.
- The "Quizzes scope to Sections" rule (MC-2 / §6 / §7) — preserved: the surface is per-Section; one Quiz block per `<section>`; no per-Chapter Quiz block, no rail decoration; the route writes exactly one `section_id`.
- The "Quiz generation is user-triggered" rule (MC-9 / §7) — preserved: the route fires only on the explicit user click; no background job.
- The "AI failures visible, never fabricated" rule (MC-5) — preserved: the surface renders Quiz status in plain language; never presents a `requested`/`generating` Quiz as finished or takeable; no AI result is fabricated (no AI is called).
- The "no direct LLM SDK use" rule (manifest §4, MC-1) — preserved: the route makes no AI call; MC-1's architecture portion stays `cannot evaluate (ADR pending)`.
- The "Mandatory/Optional honored everywhere" rule (manifest §6, MC-3) — preserved: the per-Section Quiz surface inherits the parent Chapter's designation via ADR-004's function (the Lecture page is per-Chapter); the surface shows on Sections of both Mandatory and Optional Chapters; nothing about it hides the M/O split.
- ADR-022's persistence layer / ADR-033's Quiz schema — consumed: the surface reads `list_quizzes_for_chapter` and writes via `request_quiz`, both ADR-033's public API.

## Manifest reading

Read as binding for this decision:

- **§3 Primary Objective.** Per-Section Quizzes are one of the three named consumption surfaces; the surface should read clearly in the reading flow. Placing the Quiz block at the bottom-of-Section action zone (after reading) makes it read as "this is where Quizzes for this Section live, and how you request one" — consistent with the completion toggle's placement and the cognitive sequence.
- **§5 Non-Goals.** "No non-coding Question formats" — the surface introduces no Question-format chrome (no multiple-choice radio buttons, no true/false toggles); it shows Quiz *statuses* and a "Generate a Quiz" button. "No AI tutor / chat interface for the learner" — the surface is not a chat; it's a per-Section status list + a request button. "No live / synchronous AI results" — the "Generate a Quiz" button makes no AI call; the request is recorded and processed asynchronously by a later task. "No LMS features" — the surface is not a gradebook; it shows per-Section Quiz status, no export, no roster. "No mobile-first" — the surface is desktop-tuned (it lives inside `.section-end`, which is already desktop-tuned per ADR-027/ADR-031).
- **§6 Behaviors and Absolutes.** "Quizzes scope to Sections; … There is no Chapter-bound Quiz entity" — the surface is per-Section; one Quiz block per `<section>`; no per-Chapter Quiz block; per-Chapter aggregations (if ever surfaced) are a future query, not this surface. "AI work is asynchronous from the learner's perspective" — the "Generate a Quiz" button submits and returns; the result (a generated Quiz) arrives later (a later task) via Notification (a later task); the surface shows the `requested` status in the interim. "AI failures are visible … never fabricates a result" — the surface renders Quiz status honestly; never presents a `requested`/`generating` Quiz as finished or takeable; no AI result is fabricated. "Mandatory and Optional are honored everywhere" — the surface inherits the Chapter's designation via ADR-004; shows on both; hides nothing. "Single-user" — no `user_id` in the route or surface. "Lecture source read-only" — template + CSS + a route-handler change; no source writes.
- **§7 Invariants.** **"A Quiz is bound to exactly one Section."** — the surface is per-Section; the Quiz-trigger route writes exactly one `section_id` (validated at the route handler). **"Quiz generation is always explicitly user-triggered."** — the route fires *only* on the explicit user click on "Generate a Quiz for this Section"; no background job, no auto-trigger; nothing auto-generates anything. **"Mandatory and Optional are separable in every learner-facing surface."** — the per-Section Quiz surface respects it (shows on Sections of both designations; the Lecture page's M/O badge and the rail's M/O grouping are untouched). **"Every Quiz Attempt … persists across sessions"** — orthogonal to this surface (no Attempts created this task; the Quiz-taking surface is a later task) but consistent with it (the `quiz_attempts` table ADR-033 ships persists).
- **§8 Glossary.** **Quiz** ("scoped to exactly one Section … Generated by AI-driven processing on manual user trigger") — the surface shows per-Section Quizzes; the "Generate a Quiz" button is the manual user trigger; the AI-driven generation is a later task (the button records a `requested` row). **Question / Question Bank** — orthogonal to this surface (no Questions rendered this task; the Quiz-taking surface is a later task). **Quiz Attempt** — orthogonal (no Attempts this task). **Notification** ("a learner-visible indication that an async AI result has become available") — the surface's `requested`/`generating` statuses are the *interim* display; the Notification (when the Quiz becomes `ready`) is a later task's addition. No new glossary terms are forced — every entity this surface references is already named in §8.

No manifest entries flagged as architecture-in-disguise for this decision. The surface placement is operational UI design applying the project's encoded placement-quality principles (ADR-027/028/030); no manifest-level change. (The standing flag from the project's MEMORY.md — "affordance placement follows the reading flow, not template scope" — is *applied* here, not flagged: the `.section-quiz` block is placed where the cognitive sequence puts it (bottom-of-Section action zone, after reading), not where the template's Section loop happens to end; this ADR names the reading-flow position, per that memory entry's prescription.)

## Conformance check

- **MC-1 (No direct LLM/agent SDK use).** Honored. The Quiz-trigger route makes no AI call — it validates, calls `app.persistence.request_quiz`, and PRG-redirects; no LLM SDK import, no `ai-workflows` invocation, no AI dependency anywhere in this surface. **Manifest portion: PASS.** **Architecture portion: stays `cannot evaluate (ADR pending)`** — the forbidden-SDK list and the workflow module path come from the AI-engine ADR, which is the *next* task's job; this ADR's route does not pre-empt it.
- **MC-2 (Quizzes scope to exactly one Section).** Honored by construction. The surface is per-Section (one Quiz block per `<section>`, keyed by `section.id`); the Quiz-trigger route accepts exactly one `section_number` path parameter, composes exactly one `section_id`, and calls `request_quiz(section_id)` which writes exactly one `quizzes.section_id`; no per-Chapter Quiz block, no aggregation surface, no route accepting multiple Section IDs. **PASS.**
- **MC-3 (Mandatory/Optional designation respects the canonical mapping).** Honored. The per-Section Quiz surface is inside the Lecture page (per-Chapter), which already renders the designation via ADR-004's `chapter_designation()` function; the surface shows on Sections of both Mandatory and Optional Chapters; nothing about the surface hides the M/O split; no hardcoded chapter-number rule introduced. **PASS** (architecture portion of MC-3 — the canonical-mapping source — remains as ADR-004 defined).
- **MC-4 (AI work asynchronous).** Honored — the "Generate a Quiz" route does not complete AI processing synchronously inside the request (there is no AI processing — it records a `requested` row and returns); the actual generation is decoupled in time (a later task). The workflow-name enumeration stays `cannot evaluate (ADR pending)`. **PASS** (manifest principle).
- **MC-5 (AI failures surfaced, never fabricated).** Honored. The surface renders Quiz status in plain language (`requested` → "Requested — generation pending"; `generation_failed` → "Generation failed"); it never presents a `requested`/`generating` Quiz as finished or takeable; no takeable affordance ships for any status this task. The `requested` row the trigger creates is honestly "we recorded your request" — not a fabricated Quiz, Question, or Grade; no AI result is fabricated (no AI is called). No fallback path synthesizes a "looks like a grade" object — there is no AI surface to fail. **PASS.**
- **MC-6 (Lecture source read-only).** Honored. The surface change is template (`lecture.html.j2`) + CSS (`lecture.css`) + a route handler (`app/main.py`) + the persistence read/write (via `app/persistence/`); nothing under `content/latex/` is opened for write. The Quiz-trigger route *reads* `content/latex/{chapter_id}.tex` (to validate the Section ID) — read-only, identical to what the completion route already does. **PASS.**
- **MC-7 (Single user).** Honored. The Quiz-trigger route has no `user_id`, no auth, no session, no per-user partitioning; the surface has no per-user logic; `request_quiz` writes a row with no `user_id` (ADR-033). **PASS.**
- **MC-8 (Reinforcement loop preserved).** Honored — the surface does not foreclose the loop. It ships no Quiz-composition path (the replay-+-fresh composition is a later task), so the "skip the replay query" / "skip fresh generation" forbidden paths are not yet exercisable; the `requested` rows it creates are the input the generation task processes; the schema behind them (ADR-033) leaves room for both loop portions without a non-additive migration. **PASS** (no composition code to evaluate yet; surface does not foreclose).
- **MC-9 (Quiz generation is user-triggered).** Honored. The "Generate a Quiz for this Section" route fires *only* on the explicit user click on the button; no background job, no scheduled task, no auto-trigger; nothing auto-generates anything (the `requested` row sits until a later task's generation workflow — itself user-context-bound — processes it). **PASS.**
- **MC-10 (Persistence boundary).** Honored. The Quiz-trigger route and `render_chapter` call only the typed public functions from `app/persistence/__init__.py` (`request_quiz`, `list_quizzes_for_chapter`); no `import sqlite3` or SQL string literal in `app/main.py` or `lecture.html.j2`; the SQL lives in `app/persistence/quizzes.py` (ADR-033). **PASS.**
- **UI-1 / UI-2 / UI-3 (ui-task-scope).** UI-1 satisfied at the task level (TASK-013 declares the per-Section Quiz surface change in scope). UI-2 satisfied by this ADR (the styling target — `app/static/lecture.css` — is named; the new `section-quiz-*` namespace is committed; no layout change, no new file). UI-3 satisfied by the diff naming the modified files (`app/templates/lecture.html.j2`, `app/static/lecture.css`, `app/main.py`).
- **UI-4 / UI-5 / UI-6 (rendered-surface verification gate).** Honored. ADR-010's Playwright harness covers the new surface (each Section has a Quiz block with the empty-state; M/O inheritance; the "Generate a Quiz" button present and live); TASK-013's "Verification gates (human-only; not programmatic ACs)" section records the rendered-surface review (the per-Section Quiz surface reads clearly in the reading flow; the empty-state is legible; the trigger button is visually clear what state it's in; no layout regression) as `rendered-surface verification — pass (TASK-013 per-Section Quiz surface)` in the audit Human-gates table. The test-writer does not write tests against that gate (it's correctly placed under Verification gates, not Acceptance criteria).

Previously-dormant rule activated by this ADR: none. (MC-1's architecture portion stays dormant — the AI-engine ADR doesn't exist yet. MC-7's and MC-10's architecture portions are already active per ADR-022; this ADR consumes both.)

## Consequences

**Becomes possible:**

- A per-Section Quiz surface on every Lecture page — an empty-state ("No quizzes yet for this Section.") when no Quizzes, a plain-language status list when there are — that reads clearly in the bottom-of-Section action zone (the cognitive-sequence position, alongside the completion toggle).
- A user-triggered "Generate a Quiz for this Section" affordance that records a `requested`-status Quiz row (manifest §7 / MC-9: user-triggered; MC-1: no AI call; MC-5: nothing fabricated) — the first concrete piece of the Quiz pillar's write side, and a concrete input for the next task's `ai-workflows` generation workflow.
- The Quiz-trigger route's PRG redirect reuses ADR-031's `#section-{n-m}-end` + `scroll-margin-top` no-relocate recipe for free (the `.section-end` wrapper the user clicked in already carries the anchor and the margin) — the request does not relocate the reader.
- A per-Section render path (`section_quizzes_by_id` via `list_quizzes_for_chapter`) that does one bulk query per Lecture-page render — the same shape as `complete_section_ids` / `rail_notes_context`.
- The next task (`ai-workflows` generation) to focus purely on the AI integration: it walks `requested` Quiz rows to `generating` → `ready`; it does not invent the schema, the surface, or the trigger.
- The bottom-of-Section `.section-end` wrapper validated as the standard per-Section action zone (now hosting two affordances + a status display) — future per-Section affordances (the Quiz-taking surface's "take this Quiz" button once Quizzes are `ready`; a future "completed on …" timestamp) inherit the zone.

**Becomes more expensive:**

- `lecture.html.j2`'s per-Section block grows (the `.section-quiz` block inside `.section-end`). Mitigation: localized to the per-Section loop; the existing Section content and the completion form are untouched.
- `lecture.css` grows (`section-quiz-*` rules). Mitigation: contained within the existing file (ADR-008); no new file; no `base.css` change.
- `app/main.py` grows (the `POST .../quiz` route handler + one line in `render_chapter`). Mitigation: the route mirrors the existing `.../complete` route's shape; the `render_chapter` change mirrors the existing `complete_section_ids` line.
- A `requested`-status `quizzes` row is created on every "Generate a Quiz" click, with no processor until the next task. Mitigation: harmless in a single-user dev database; the read surface renders them honestly; a future "cancel request" affordance can be added if they pile up; the next task is scheduled.

**Becomes impossible (under this ADR):**

- A per-Section Quiz surface that presents a `requested`/`generating` Quiz as finished or takeable. The status-label mapping and the "no takeable affordance this task" commitment forbid it.
- A per-Chapter Quiz block, or a rail Quiz decoration, this task. The surface is per-Section; out-of-scope for a per-Chapter or rail surface (no consumer).
- A separate `GET /lecture/{chapter_id}/quizzes` page. ADR-023's precedent (surfaces live inside the Lecture page) governs.
- A Quiz-trigger affordance that auto-generates, runs a background job, or calls an LLM SDK. MC-9 / MC-1 forbid it; the route fires only on the explicit click and makes no AI call.
- A Quiz-trigger affordance that relocates the reader on the PRG redirect. ADR-030's principle (retained by ADR-031) + the reused `#section-{n-m}-end` + `scroll-margin-top` recipe forbid it.
- An above-body "Quizzes for this Section" header. The cognitive-sequence principle (ADR-027) governs — the affordance is bottom-of-Section.

**Future surfaces this ADR pre-positions:**

- The `ai-workflows` generation workflow — processes `requested` Quiz rows; when a Quiz reaches `ready`, the per-Section surface's status label flips to "Ready" (no take-button yet — that's the next-next surface). The next task.
- The Quiz-taking surface — adds a "take this Quiz" affordance to the `.section-quiz` block for `ready` Quizzes; creates a `quiz_attempts` row; renders the Quiz's Questions on a take-page or in-place. A later task.
- The Notification surface — when a Quiz becomes `ready` or an Attempt is `graded`, a learner-visible Notification (a later task); the per-Section surface's status list is the *in-context* view, the Notification is the *out-of-context* alert.
- A richer populated-case rendering — past Attempts + their Grades, inside the `.section-quiz` block. The generation/grading tasks add it; this ADR's scaffold is "list each Quiz's status."
- A "completed on …" timestamp display inside `.section-end` (surfacing `section_completions.completed_at` per ADR-024) — a natural neighbor of the Quiz block in the action zone. A later task.

**Supersedure path if this proves wrong:**

- If the bottom-of-Section placement proves too easy to miss (the learner finishes a Section and scrolls past the Quiz block) → a future ADR refines (a sticky-within-Section affordance, or a Quiz-status cue elsewhere); the `.section-quiz`-inside-`.section-end` placement remains the static fallback. Cost: template + CSS edit; bounded.
- If a `requested`-status row with no processor proves a problem (the next task slips badly; `requested` rows pile up; the surface gets cluttered) → a future ADR adds a "cancel request" affordance, or the next task lands and processes them. Cost: bounded; nothing is corrupted.
- If the `section-quiz-*` namespace collides with a future Quiz surface (a per-Chapter or rail one) → a future ADR carves the namespace (e.g., `section-quiz-*` for the per-Section surface, `chapter-quiz-*` for a per-Chapter one); ADR-008's prefix convention is extended accordingly. Cost: bounded.
- If Option 1 (real trigger route) proves to have been the wrong call (the next task is cancelled; the Quiz pillar is descoped) → revert the route + the `.section-quiz-form`; the empty-state remains. Cost: bounded; ~one route handler + one form.
- If the populated-case scaffold proves insufficient or misleading once Attempts/Grades exist → the generation/grading tasks supersede the rendering shape; the placement (inside `.section-end`) and the empty-state stand.

The supersedure path, in every case, runs through a new ADR (and, where the placement-quality principles themselves are what's wrong, through a superseding ADR that names why — per ADR-027's / ADR-030's "name the reason" burden). This ADR does not edit any prior ADR in place; it adds the per-Section Quiz surface inside the action zone ADR-027 forecast and consumes ADR-031's no-relocate mechanism unchanged.
