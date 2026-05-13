# ADR-047: The sandbox splice extension (`run_test_suite(test_suite, response, preamble="")` with the splice `preamble + response + test_suite` in one TU; default-`""` keeps ADR-042's pre-task splice byte-equivalent) + the take-surface `preamble` block (a read-only `<pre class="quiz-take-preamble">` rendered per Question with a non-empty preamble, omitted when empty; new `.quiz-take-preamble` CSS rule in `quiz.css`, reusing the `quiz-take-*` namespace per ADR-008; the "Run tests" route fetches the preamble via `get_question` and passes it to the sandbox)

**Status:** `Accepted`
Auto-accepted by /auto on 2026-05-13
**Date:** 2026-05-13
**Task:** TASK-018
**Resolves:** none — the companion **ADR-045** resolves `design_docs/project_issues/question-gen-prompt-emit-assertion-only-test-suites.md`; this ADR is the runner + take-surface half of that resolution (the structural extension the assertion-only prompt change needs in order to produce a learner-visible pass-path).
**Supersedes:** none — consumes **ADR-042** (the in-app code-execution sandbox — the bare-subprocess-under-rlimits isolation mechanism, the wall-clock timeout, the temp `cwd` away from `content/latex/` (MC-6), the C++/Python language sniff, the `RunResult` shape (`status` / `passed` / `output`), the honest-failure surfacing (`ran` / `timed_out` / `compile_error` / `setup_error`), the no-fabricated-pass/fail posture (MC-5's spirit), the bare-stdlib-imports posture — **all consumed unchanged**; what extends is *only* the `run_test_suite` signature with one additional optional parameter `preamble: str = ""` and the splice shape from `learner_response + test_suite` to `preamble + learner_response + test_suite`; the default `preamble=""` makes the splice **byte-equivalent to ADR-042's pre-task splice** when no preamble is passed, so pre-task call-sites and pre-task Questions in the Bank work unchanged; no supersedure of ADR-042 is needed — this is the additive-extension shape ADR-044 used to cite ADR-039), **ADR-043** (the "Run tests" route + take-surface affordance — the route shape, the synchronous `POST .../take/run-tests` PRG-redirect form post, the no-JS posture (per ADR-035), the `save_attempt_responses` whole-form persistence step, the `get_question` fetch step, the `save_attempt_test_result` persistence step, the `#question-{id}` anchor + `scroll-margin-top` no-relocate recipe (ADR-031), the `quiz_take.html.j2` `quiz-take-*` namespace per ADR-008, the read-only `<pre class="quiz-take-test-suite">` block — **all consumed unchanged**; what extends is *only* (a) the route now also reads the Question's `preamble` via `get_question` (ADR-046) and passes it as the additional argument to `run_test_suite`, and (b) the template renders a new read-only `<pre class="quiz-take-preamble">` block per Question with a non-empty `preamble`, omitted when empty), **ADR-044** (the `attempt_questions` test-result persistence + `get_question` accessor + `AttemptQuestion.test_suite` extension — consumed unchanged; the `AttemptQuestion` dataclass also carries `preamble` now per ADR-046; `save_attempt_test_result` is unchanged; the four `test_*` columns are unchanged), **ADR-046** (the `questions.preamble` column + `Question.preamble` / `AttemptQuestion.preamble` dataclass fields + the carry-through in `list_questions_for_quiz` / `get_question` / `list_attempt_questions` — this ADR consumes those mechanics; the `get_question` call now reads one more attribute on the returned `Question`, the take template reads `aq.preamble` from the `AttemptQuestion` dataclass), **ADR-008** (the per-surface CSS namespacing — the new `.quiz-take-preamble` CSS rule reuses the `quiz-take-*` namespace in the existing `app/static/quiz.css`; no `base.css` change, no new CSS file), **ADR-035** (the no-JS-is-preferred-where-clean posture — preserved; this ADR adds no JS), **ADR-031** (the `#question-{id}` + `scroll-margin-top` no-relocate recipe — preserved; the existing `.quiz-take-question` scroll-margin-top covers this surface), and **ADR-045** (the assertion-only prompt + `preamble`-field decisions this ADR consumes structurally — the splice's three-piece shape and the take-page's three-block rendering are the structural realization of ADR-045's field separation). The companion **ADR-045** owns the prompt + schema + processor; the companion **ADR-046** owns the storage mechanics; this ADR owns the runner-splice extension + the take-surface block. No prior ADR is re-decided.

## Context

ADR-045 decides that a Question carries a `preamble` field (a string of shared struct/class/header source code) alongside `prompt` / `topics` / `test_suite`. ADR-046 decides how the preamble is stored and exposed (the `questions.preamble` column, the `Question.preamble: str | None` dataclass field, the carry-through in `list_questions_for_quiz` / `get_question` / `list_attempt_questions`, the `AttemptQuestion.preamble: str | None` dataclass field).

This ADR decides the **two remaining structural pieces**:

1. **How the sandbox uses the preamble** — `app/sandbox.py`'s `run_test_suite` is the engine that ADR-042 built; it currently takes `(test_suite: str, response: str)` and splices `learner_response + test_suite` into one translation unit. Now that the preamble exists, it needs to be in the same translation unit, ahead of the learner's code (so the learner's implementation can reference the struct/class shapes the preamble declares) and ahead of the test suite (so the assertions can reference the same shapes). The splice becomes a three-piece concatenation.
2. **How the take page surfaces the preamble** — the learner needs to *see* the preamble (read-only) alongside the existing read-only test-suite block, so they know what shared shapes their implementation must agree with. The template needs a new block; the CSS needs a new rule. The block must be omitted cleanly when the Question's `preamble` is empty (so a Question with no shared shapes doesn't render a visible empty box).

The constraints binding this decision:

- **ADR-042's `RunResult` shape is the stable seam.** The route and persistence depend on the result shape, not on the mechanism. The signature extension must be additive — a default-`""` `preamble` parameter — so pre-task call-sites continue to work without modification and the splice is byte-equivalent to ADR-042's when no preamble is passed. This preserves backward compatibility for pre-TASK-018 Questions in the Bank (which have `preamble = NULL`) and for any test or call-site that doesn't yet pass a preamble.
- **ADR-042's runner is unchanged in all decisions but the splice signature.** The bare-subprocess-under-rlimits isolation mechanism, the wall-clock timeout, the temp `cwd` away from `content/latex/` (MC-6), the C++/Python language sniff, the `RunResult` shape, the honest-failure surfacing, the no-fabricated-pass/fail posture, the bare-stdlib-imports posture — all stay. Only the splice signature and the splice shape extend additively.
- **ADR-043's route shape is the stable interface.** The `POST .../take/run-tests` route's path-param validation, the synchronous PRG redirect, the `save_attempt_responses` whole-form persistence step, the `get_question` fetch step, the `save_attempt_test_result` persistence step, the `#question-{id}` anchor + `scroll-margin-top` no-relocate recipe, the no-JS posture — all stay. Only one additional read (the Question's `preamble`) and one additional argument (`preamble=`) on the `run_test_suite` call extend the route.
- **The take template's `quiz-take-*` namespace is the established CSS vocabulary** (ADR-008 / ADR-038 / ADR-043). The new block reuses the namespace; no `base.css` change; no new CSS file. The block is omitted when the preamble is empty.
- **MC-5's spirit (honest failure)** is preserved: a `preamble` that doesn't compile is still surfaced as `compile_error`, never fabricated as `passed=True/False`. The splice change does not introduce any new failure-fabrication path.
- **MC-6 (Lecture source read-only)** is preserved: the sandbox's temp `cwd` is unchanged; the preamble's source-code is concatenated into the spliced file in the temp dir; nothing under `content/latex/` is touched.
- **MC-4 (AI work asynchronous)** — preserved; running tests is not AI work; the route is synchronous-with-a-timeout (ADR-043's reasoning unchanged).
- **MC-9 (Quiz generation user-triggered)** — preserved; running tests generates no Quiz.
- **MC-10 (Persistence boundary)** — preserved; the sandbox imports no `sqlite3` and contains no SQL literal; the route calls only the typed `app.persistence.*` functions.

The decision space is small (the pattern is well-established):

- **The splice signature.** `run_test_suite(test_suite: str, response: str, preamble: str = "")` (positional default — the obvious shape) — vs. a keyword-only parameter — vs. a new entry-point that the existing entry-point delegates to. The default-`""` positional form is the simplest and source-compatible with pre-task call-sites; ADR-044's `save_attempt_test_result` follows the same shape (keyword-only is fine but default-positional is cleaner here since `preamble` is conceptually a peer of `test_suite` and `response`).
- **The splice order.** `preamble + response + test_suite` (preamble first — declarations visible to both response and test_suite) — vs. `preamble + test_suite + response` (test_suite before response — the response can call functions the test_suite declares, but the test_suite's `main()` would run *before* the response's definitions are in scope which doesn't work in C++) — vs. `response + preamble + test_suite` (response first — same as ADR-042's order, but the preamble's struct declarations come *after* the response's implementation that depends on them, which doesn't work in C++ either, since the response references types not yet declared). The only order that works in C++ — where forward declarations matter — is **preamble first, then response, then test_suite**: the preamble declares the shapes, the response defines the implementation against those shapes, the test_suite (which comes last and typically holds the `main()` with assertions) calls the implementation. For Python the order is less load-bearing (functions/classes can be redefined; imports float to the top in well-formed code), but the same `preamble + response + test_suite` order works there too — the preamble's `import` lines or constant definitions are visible before both. So the architectural commitment is **preamble first, then response, then test_suite**.
- **The block placement on the take page.** Above the response textarea (the preamble is shared context the learner needs *before* they start writing code — the natural top-of-Question placement) — vs. below the textarea (the preamble follows the response code that uses it — but the learner needs the preamble *to write* the response, so it should be visible first) — vs. alongside the test-suite block in a side panel (would change the page's column structure, which is out of scope per ADR-038's unchanged-shell commitment). The architectural commitment is **above the response textarea**, near the top of each Question block, so it appears in the reading flow before the textarea and the test-suite block.
- **The CSS rule.** A new `.quiz-take-preamble` rule in `app/static/quiz.css`, visually distinct from `.quiz-take-test-suite` (the spec the tests check) and the response textarea (the learner's code) — the three visual layers correspond to the three roles ("shared shapes", "your code", "the asserts"). The rule reuses the `quiz-take-*` namespace per ADR-008; no `base.css` change; no new CSS file.
- **The omitted-when-empty rendering.** Jinja `{% if aq.preamble %}` guard — if `preamble` is `None` or `""`, the block is omitted entirely (no visible empty box); the rest of the Question renders exactly as ADR-043 specified for the no-preamble case.

## Decision

### The sandbox splice extension — `run_test_suite(test_suite: str, response: str, preamble: str = "") -> RunResult`; the splice becomes `preamble + "\n\n" + response + "\n\n" + test_suite`

`app/sandbox.py`'s `run_test_suite` signature is **extended** with one optional parameter:

```python
def run_test_suite(test_suite: str, response: str, preamble: str = "") -> RunResult:
    ...
```

The splice is **changed** from ADR-042's `response + "\n\n" + test_suite` to:

```
preamble + "\n\n" + response + "\n\n" + test_suite
```

(or the implementer's exact concatenation/separator choice — `"\n"` vs `"\n\n"` is implementer-followable; the architectural commitment is "all three pieces in one TU, in the order preamble-then-response-then-test_suite"). When `preamble == ""` (the default), the splice begins with one leading separator and is **byte-equivalent to ADR-042's pre-task splice up to a leading newline** (the leading separator could be elided in that case for true byte-equivalence — implementer's call; either form is acceptable since a leading newline is meaningless to both `g++` and `python3`). Pre-task call-sites that pass no `preamble` continue to work unchanged; pre-TASK-018 Questions in the Bank (with `preamble = NULL`) splice byte-equivalently to ADR-042's pre-task behavior.

**Why `preamble + response + test_suite` and not another order:**

- **C++ requires forward declarations.** A `struct Node` referenced by `void append(LinkedList&, int)` (the learner's response) must be declared *before* `append`'s body, or `g++` reports "unknown type 'Node'". The preamble's struct declarations must precede the response.
- **The test suite typically holds `main()` (for C++) or `unittest.main()` / module-level test calls (for Python).** It must come after both the preamble (which declares the shapes the assertions reference) and the response (which defines the implementation the test calls). Putting the test_suite before the response would put `main()` ahead of the function it calls — fine in Python via name-lookup-at-call-time, but in C++ the call site would either succeed via implicit forward declaration (fragile) or fail to link.
- **Python is order-tolerant but still benefits from the same order.** A module-level `import` or constant in the preamble is naturally at the top; the response's `def` follows; the test suite's `unittest.main()` runs last. The same order works.

**No other change to `app/sandbox.py`.** ADR-042's *all other* decisions are consumed unchanged:

- The bare-subprocess-under-rlimits isolation mechanism (`resource.setrlimit` for `RLIMIT_CPU` / `RLIMIT_AS` / `RLIMIT_NPROC` / `RLIMIT_FSIZE` / `RLIMIT_CORE = 0`; `os.setsid()`).
- The `subprocess.run(timeout=...)` wall-clock cap.
- The `tempfile.mkdtemp()` throwaway working directory (MC-6 load-bearing — never under `content/latex/`).
- The `cwd=` the temp dir, fresh minimal env, `stdin` closed.
- The C++ via `g++` (primary, sniffed by `#include`) and Python via `python3` (secondary, sniffed by `import`/`def test`/`unittest`/`pytest`) language detection.
- The unrecognized-language `setup_error` fallback.
- The `RunResult` dataclass shape (`status` / `passed` / `output`) and the truncate-output cap.
- The honest-failure surfacing (`ran` / `timed_out` / `compile_error` / `setup_error`, never a fabricated pass/fail — MC-5's spirit).
- The POSIX/Linux-only posture.
- The bare-stdlib-only imports (`subprocess`, `resource`, `tempfile`, `shutil`, `os`, `pathlib`); no LLM SDK, no `ai_workflows.*`, no `app.persistence.*`.
- The `no new pyproject.toml dependency` posture.

**Why an additive default parameter, not a `run_test_suite_v2` / new entry-point:** the default-`""` form is source-compatible with all existing call-sites (the route's existing `run_test_suite(test_suite, learner_code)` call works unchanged until the route is updated to pass `preamble`), and the splice is byte-equivalent for the `preamble=""` case so pre-task Questions in the Bank produce the same compile/run behavior as before. A new entry-point would introduce a v1/v2 split with no real benefit — the splice change is too small to warrant a parallel entry-point, and ADR-042's `RunResult` shape stays the stable seam.

### The "Run tests" route — fetches the Question's `preamble` via `get_question` (ADR-046's extension) and passes it as the third argument to `run_test_suite`

The `POST /lecture/{chapter_id}/sections/{section_number}/quiz/{quiz_id}/take/run-tests` route (ADR-043) is **extended** in one place: the existing `get_question(question_id)` call (which ADR-043 introduced to fetch the target Question's `test_suite` for the sandbox) now also reads the returned `Question`'s `preamble` attribute (ADR-046 adds it). The call to `run_test_suite` becomes:

```python
result = run_test_suite(
    test_suite=question.test_suite,
    response=responses[question_id],
    preamble=question.preamble or "",
)
```

The `or ""` handles the legacy-NULL case (a pre-TASK-018 Question has `preamble = None`; the `or ""` flattens to the default-`""` shape). No other change to the route. ADR-043's path-param validation, the synchronous form-POST, the `save_attempt_responses` whole-form persistence step, the `save_attempt_test_result` call, the PRG redirect to `GET .../take#question-{id}`, the `#question-{id}` anchor + `scroll-margin-top` recipe — all unchanged.

### The take template — renders a read-only `<pre class="quiz-take-preamble">` block per Question with a non-empty preamble, above the response textarea; omitted when empty

`app/templates/quiz_take.html.j2` is **extended** in two places (the `in_progress` branch and the `submitted` branch of the per-Question rendering — both branches show the preamble read-only when present, since the preamble is part of the Question's specification, not a per-state artifact):

In each per-Question block (inside `.quiz-take-question`, before the response textarea), add:

```html
{% if aq.preamble %}
<pre class="quiz-take-preamble">{{ aq.preamble }}</pre>
{% endif %}
```

(The implementer's exact placement, caption text, and any wrapping `<div>` / `<label>` / `<figure>` / `<figcaption>` are implementer-followable; the architectural commitment is "above the response textarea, near the top of the Question block, read-only, monospace, omitted when the preamble is empty or NULL". A short caption like "Shared code — your implementation and the tests both depend on this" or similar is reasonable; the exact wording is the implementer's call.)

The `{% if aq.preamble %}` guard handles both the legacy-NULL case (`preamble is None` → the Jinja truthiness check is `False`) and the TASK-018+-empty case (`preamble == ""` → also `False`). So a Question with no shared shapes (pre-TASK-018 or TASK-018+) renders no preamble block — the take page looks exactly as ADR-043 specified for that Question. Only Questions with a non-empty preamble get the new block.

Jinja's autoescape is **correct and intentional** for this block (the preamble is source code, displayed as text; escaping handles `<`, `>`, `&` correctly; no `| safe`).

In both the `in_progress` branch (alongside the response textarea, the "Run tests" button, the test-suite block, the results panel) and the `submitted` branch (alongside the read-only response and the read-only last test result) the preamble block renders the same way (read-only `<pre>`, omitted when empty). The `not_ready` state is unchanged (no takeable form, no preamble block — the Quiz isn't `ready`).

The existing read-only `<pre class="quiz-take-test-suite">` block (ADR-043) is **unchanged in placement and content**. After the change, the per-Question rendering surface reads top-to-bottom as: prompt → preamble (read-only, if non-empty) → response textarea (or read-only response in the submitted state) → test-suite block (read-only) → "Run tests" button (in_progress only) → results panel. The three "code surfaces" the learner sees (preamble, response, test_suite) correspond cleanly to the three pieces the runner splices.

### The CSS — a new `.quiz-take-preamble` rule in `app/static/quiz.css`, visually distinct from `.quiz-take-test-suite` and the response textarea

A new rule in the existing `app/static/quiz.css` (no new file, no `base.css` change):

- `.quiz-take-preamble` — a monospace `<pre>`, scrollable on overflow (`max-height` + `overflow: auto`), with a background tint and/or border distinct from `.quiz-take-test-suite` and the response textarea, so the learner can tell "the shared shapes" from "the tests" from "your code" at a glance. The exact palette is implementer-followable (e.g. a third tint in the established `quiz-take-*` color vocabulary); the architectural commitment is "visually distinct from the other two code surfaces, reusing the `quiz-take-*` namespace per ADR-008".

No other CSS change. The existing `.quiz-take-test-suite`, `.quiz-take-response`, `.quiz-take-results-*`, `.quiz-take-question` (and its `scroll-margin-top`), `.quiz-take-run-tests`, and `.quiz-take-submit-button` rules are unchanged.

### Scope of this ADR

This ADR fixes only:

1. **The sandbox splice extension** — `run_test_suite(test_suite, response, preamble="")`; splice = `preamble + response + test_suite` (one TU, in that order); default-`""` keeps ADR-042's pre-task splice byte-equivalent; pre-task call-sites and pre-TASK-018 Questions in the Bank work unchanged.
2. **The "Run tests" route's pass-through** — the existing `get_question` call returns a `Question` carrying `preamble`; the route passes `preamble=question.preamble or ""` to `run_test_suite`; ADR-043's other decisions consumed unchanged.
3. **The take template's `preamble` block** — a read-only `<pre class="quiz-take-preamble">` rendered above the response textarea per Question with a non-empty `preamble` (in both the `in_progress` and `submitted` branches); omitted when empty; ADR-043's other template structure consumed unchanged.
4. **The `.quiz-take-preamble` CSS rule** — monospace, scrollable, visually distinct from `.quiz-take-test-suite` and the response textarea; in `app/static/quiz.css`; reuses the `quiz-take-*` namespace per ADR-008; no `base.css` change; no new CSS file.

This ADR does **not** decide:

- **The `question_gen` prompt + schema decisions** — owned by **ADR-045**.
- **The persistence storage mechanics** — owned by **ADR-046**.
- Any change to **ADR-042's isolation mechanism** (rlimits / timeout / temp `cwd` / language sniff / `RunResult` shape / honest-failure surfacing / bare-stdlib-imports) — all unchanged.
- Any change to **ADR-043's route shape** beyond the one-argument extension on the `run_test_suite` call (path-param validation, PRG redirect, anchor + scroll-margin-top recipe, `save_attempt_responses` / `save_attempt_test_result` calls, no-JS posture — all unchanged).
- Any change to **ADR-044's `attempt_questions` test-result columns or `save_attempt_test_result`** — unchanged; the runner still persists `passed` / `status` / `output` / `run_at` per ADR-044.
- Any change to **`base.css`, the three-column shell, the rails, the designation badge, the "Submit Quiz" button, the per-Section Quiz surface caption** — all unchanged.
- The **deprioritized Quiz-prompt-rendering bug** (`{{ aq.prompt }}` autoescaped — literal backticks) — user-deprioritized; out of scope. The new `<pre class="quiz-take-preamble">` block uses Jinja autoescape correctly for source code (which is what we want for raw source; backticks render verbatim — the literal-backticks bug is a property of the existing `prompt` rendering, untouched by this slice).

## Alternatives considered

**A. A new entry-point on the sandbox (`run_test_suite_with_preamble(...)`) rather than extending `run_test_suite`'s signature with a default parameter.**
Rejected. The default-`""` extension is source-compatible with all existing call-sites; the splice change is too small to warrant a parallel entry-point; ADR-042's `RunResult` shape stays the stable seam either way. A new entry-point would introduce a v1/v2 split with no real benefit (every call-site would migrate to v2 within this task anyway, leaving v1 as dead code).

**B. A different splice order — `response + preamble + test_suite` or `preamble + test_suite + response` or `test_suite + preamble + response`.**
Rejected — see §The sandbox splice extension. Only `preamble + response + test_suite` works in C++ (preamble's struct/class declarations must precede the response's implementation that depends on them; the test_suite typically holds `main()` and must come last). Python is order-tolerant but the same order also works. Any other order risks compile failures on real generated Questions even when the preamble + response + test_suite are individually correct.

**C. A keyword-only parameter (`*, preamble: str = ""`) instead of a positional default.**
Considered. Defensible — forces explicit naming at call-sites; harder to misuse with positional args. Rejected as overcautious here — `preamble` is a peer of `test_suite` and `response`, all three are short string parameters, and the call-site `run_test_suite(test_suite=..., response=..., preamble=...)` is already keyword-driven by convention. A positional default with documented kwarg-friendliness is the cleaner shape. (If a future change adds more parameters, keyword-only might become valuable then; not now.)

**D. Render the preamble block *below* the response textarea (after the learner's code), or in a side panel.**
Rejected. The preamble is *prerequisite reading* — the learner needs to see the shared shapes *to write* the response correctly. Placing it after the textarea puts it after the code that depends on it (the wrong reading order). Placing it in a side panel would change the page's column structure (out of scope per ADR-038's unchanged-shell commitment). Above the textarea, near the top of the Question block, is the natural reading-flow placement.

**E. Render the preamble block *only in the `in_progress` state*, not the `submitted` state.**
Rejected. The preamble is part of the Question's specification (§8 Question); a `submitted` Attempt that hides it is less honest than one that shows it (read-only, fabricating nothing). Same shape as ADR-043's "show the last test result read-only in the submitted state" decision. The cost is one block rendered in both branches.

**F. Render the preamble block when `preamble` is `None` *or* `""`, with an explicit "no shared shapes" caption when empty.**
Rejected. A Question with no shared shapes simply doesn't need a "Shared code" surface — rendering an explicit "no shared shapes" caption adds cognitive noise. The omitted-when-empty form is cleaner: the take page looks the same as ADR-043 specified for Questions that don't need shared shapes. The `{% if aq.preamble %}` Jinja truthiness check handles both `None` and `""` uniformly.

**G. Fold this ADR's decisions into ADR-045 (one big ADR for the whole slice).**
Considered. Rejected for record-keeping: this slice splits along the same seams as TASK-016 (ADR-040 + ADR-041) and TASK-017 (ADR-042 + ADR-043 + ADR-044). The split keeps each ADR focused and independently citable. ADR-045 owns the prompt + schema + processor (the AI-engine-facing decisions); ADR-046 owns the storage mechanics (the persistence layer); ADR-047 owns the runner-splice extension + the take-surface block (the runtime + UI layer). Three ADRs, three clear layers; matches the codebase's existing slice-shape precedent.

**H. Supersede ADR-042 in place (the splice signature change is a substantive change to the runner).**
Rejected. ADR-042's *all other* decisions are consumed unchanged; only the splice signature extends additively (one optional parameter, default `""`). ADR-042 §The splice explicitly recorded the project_issue this ADR resolves and the dependency; resolving that dependency consumes ADR-042's other decisions unchanged. The right framing is an additive extension citing ADR-042, mirroring how ADR-044 cited ADR-039 (the Attempt-lifecycle persistence layer) — ADR-039's decisions consumed unchanged; ADR-044 extended additively. Same pattern here.

## My recommendation vs the user's apparent preference

Aligned with the user's apparent preference, captured in the TASK-018 task file's "Architectural decisions expected" section and the project_issue's option (a). The task forecast the splice extension as `run_test_suite(test_suite, response, preamble="")`, the splice order as `preamble + response + test_suite`, the take-page block as a read-only `<pre class="quiz-take-preamble">` above the response textarea, the CSS rule as `.quiz-take-preamble` in `quiz.css`, the omitted-when-empty rendering, no `base.css` change, no new CSS file, and explicitly flagged that the splice extension is additive (no supersedure of ADR-042). The architect adopts all of these.

The one architect's-judgement call recorded here (not a disagreement with the user, an architect's affirmation of the cleanest form): **the preamble block renders in both the `in_progress` and `submitted` branches** (Alternative E). The task forecast didn't explicitly resolve this; the architect's choice is "both branches", on the same grounds ADR-043 chose to show the last test result read-only in the submitted state — the preamble is part of the Question's specification (§8) and hiding it is less honest than showing it read-only with nothing fabricated.

**On the empirical-confirmation gate.** This ADR's structural extensions (the splice, the route's one-argument pass-through, the template's new block, the CSS rule) are individually trivial and pin-testable; the load-bearing empirical question — does the regenerated Quiz's `test_suite` + `preamble` triple actually splice cleanly with a hand-written correct implementation and produce `passed=True`? — is owned by ADR-045 (the prompt change) and exercised by TASK-018's "real-engine end-to-end" verification gate. This ADR's structural extensions are correct by construction *given* a clean assertion-only `test_suite` and a meaningful `preamble`; if ADR-045's prompt change produces output that doesn't follow STRICT REQUIREMENTs 7 and 8, this ADR's extensions still hold (the splice still concatenates three pieces; the take page still renders three blocks) — they just don't produce `passed=True` until the prompt change converges. So this ADR is robust to ADR-045's empirical confirmation cycle.

**On the no-JS posture (ADR-035).** Preserved. The new block is a read-only `<pre>`; the new CSS rule is a static stylesheet rule; no `<script>` is added; the existing no-JS take-page form-POST + PRG mechanic (ADR-043) is unchanged. ADR-035's "no-JS is preferred where clean and sufficient" framing applies: this surface needs no JS, and the no-JS shape is clean (a `{% if %}` Jinja guard + a `<pre>` element + a CSS rule — three lines of template + a CSS block).

**On the deprioritized Quiz-prompt-rendering bug.** Out of scope (user-deprioritized 2026-05-12). Adjacent (the new `.quiz-take-preamble` block lives on the same template), but the user's deprioritization stands. The new block is autoescape-correct for source code (raw `<`, `>`, `&` are escaped; backticks render verbatim — exactly what we want for source); the literal-backticks bug is a property of the existing `prompt` rendering, untouched.

I am NOT pushing back on:

- ADR-042's isolation mechanism — consumed unchanged (the splice signature extension is the *only* change).
- ADR-043's route shape — consumed unchanged (one-argument pass-through is the *only* change).
- ADR-044's `attempt_questions` test-result columns and `save_attempt_test_result` — consumed unchanged.
- ADR-046's storage mechanics — consumed (the route reads `question.preamble` from `get_question`; the template reads `aq.preamble` from `AttemptQuestion`; both are dataclass attributes ADR-046 added).
- ADR-008's `quiz-take-*` namespace — preserved.
- ADR-031's no-relocate `#anchor` + `scroll-margin-top` recipe — preserved (the existing `.quiz-take-question` scroll-margin-top covers the new block layout — the anchor still lands on the Question block, the preamble block is inside it).
- ADR-035's no-JS-is-preferred-where-clean posture — preserved.
- The single-user posture (MC-7) — preserved.
- The MC-6 lecture-source-read-only posture — preserved (the sandbox's temp `cwd` is unchanged; the preamble's source-code is concatenated into the spliced file in the temp dir; nothing under `content/latex/` is touched).
- The MC-4 async-AI posture — preserved (the route is synchronous-with-a-timeout; running tests is not AI work).

## Manifest reading

Read as binding for this decision:

- **§5 Non-Goals.** "No non-coding Question formats" — the preamble block renders source code (read-only `<pre>`); never a non-coding artifact. "No live / synchronous AI results" — the route does no AI work (the test-runner is not AI); the synchronous form-POST is permitted (ADR-042 / ADR-043's reasoning). "No multi-user features" — no `user_id`; no auth.
- **§6 Behaviors and Absolutes.** "Code is written, run, and tested within the application … running tests against it" — this ADR makes the pass-path *empirically reachable* on real generated Questions (the structural part shipped in TASK-017; the runner now consumes the preamble the generator emits, so the splice produces a clean TU). "AI failures are visible … never fabricates a result" — preserved: the runner's `compile_error` / `timed_out` / `setup_error` / `setup_error` paths are unchanged; the splice change does not introduce any new failure-fabrication path. "Single-user" — preserved.
- **§7 Invariants.** "Every Question is a hands-on coding task" — preserved; the three code surfaces (preamble, response, test_suite) are all coding-task artifacts. "Every Quiz Attempt, Note, and completion mark persists across sessions" — the preamble persists on the Question (ADR-046).
- **§8 Glossary.** **Question** — "carries a test suite the learner runs in-app to verify the implementation" — preserved; the test suite still runs in-app; the new preamble surface is *additional* context (the shared shapes the test suite uses), not a replacement. **Quiz Attempt** — "the in-app test results for each response" — preserved; the route persists the test result via `save_attempt_test_result` per ADR-044. **Grade** — "correctness determined by whether the learner's code passed the Question's tests" — preserved; this ADR makes the "passed the tests" signal *reach* `True/False` on real generated Questions (the prerequisite for the grading slice).

No manifest entries flagged as architecture-in-disguise. The splice-signature shape, the splice order, the block placement, the omitted-when-empty rule, and the CSS-rule placement are operational architecture the manifest delegates to "the architecture document".

## Conformance check

- **MC-1 (No direct LLM/agent SDK use).** Vacuously preserved — `app/sandbox.py` imports no AI; `app/main.py`'s extended route imports no AI; the template renders no AI surface. **PASS.**
- **MC-2 (Quizzes scope to one Section).** Honored — the preamble is per Question; each Question belongs to one Section (unchanged); the route operates on one Quiz which belongs to one Section. **PASS.**
- **MC-3 (Mandatory/Optional designation).** Orthogonal — the take page renders Questions of both designations identically. **PASS.**
- **MC-4 (AI work asynchronous).** Honored — the route does no AI work; running tests is not AI. The synchronous form-POST is permitted (ADR-042 / ADR-043's reasoning). **PASS.**
- **MC-5 (AI failures surfaced, never fabricated).** Honored — the runner's `compile_error` / `timed_out` / `setup_error` paths are unchanged; the splice change does not introduce any new failure-fabrication path. A preamble that doesn't compile is surfaced as `compile_error`, honestly. **PASS.**
- **MC-6 (Lecture source read-only).** Honored — the sandbox's temp `cwd` is unchanged (never under `content/latex/`); the preamble's source-code is concatenated into the spliced file in the temp dir; nothing under `content/latex/` is opened for write. **PASS.**
- **MC-7 (Single user).** Honored — no `user_id` anywhere new. **PASS.**
- **MC-8 (Reinforcement loop preserved).** Honored — this ADR makes the loop's raw signal reach pass/fail on real generated Questions (the prerequisite for the grading slice's read signal); no fresh-only-post-first path created; the first-Quiz-only guard (ADR-037) is unchanged. **PASS.**
- **MC-9 (Quiz generation user-triggered).** Honored — running tests generates no Quiz; the route does no `request_quiz` call. **PASS.**
- **MC-10 (Persistence boundary).** Honored — `app/sandbox.py` imports no `sqlite3` and contains no SQL literal (consumed unchanged); the route calls only typed `app.persistence.*` functions (`get_question`, `save_attempt_responses`, `save_attempt_test_result`); no SQL in `app/main.py`; no SQL in `app/templates/quiz_take.html.j2`. **PASS.**

No previously-dormant rule is activated.

## Consequences

**Becomes possible:**

- The §6 loop's pass-path *reaches* on real generated Questions: writing a real correct implementation of one Question's named signature on a regenerated Quiz's take page, clicking "Run tests", and observing `passed=True` (a green `.quiz-take-results-pass` block).
- The take page surfaces the preamble as a first-class read-only block (a third "code surface" alongside the test suite and the response), so the learner sees the shared shapes their code must implement against — addressing the §6-spirit concern that the learner can't run tests they can't read.
- Pre-TASK-018 Questions in the Bank continue to splice byte-equivalently to ADR-042's pre-task behavior (the default-`""` `preamble` path).
- The grading slice (next) reads a now-meaningful per-Question pass/fail signal from ADR-044's `test_*` columns.

**Becomes more expensive:**

- `app/sandbox.py` grows one optional parameter and a three-piece concatenation. Mitigation: ~3 lines; ADR-042's other decisions unchanged; the bare-stdlib-only imports unchanged; no new pyproject.toml dependency.
- `app/main.py`'s "Run tests" route grows one attribute read and one keyword argument on the `run_test_suite` call. Mitigation: ~2 lines.
- `app/templates/quiz_take.html.j2` grows a `{% if aq.preamble %}` guard + a `<pre class="quiz-take-preamble">` block, in both the `in_progress` and `submitted` branches. Mitigation: ~6 lines (3 per branch); the existing structure is unchanged.
- `app/static/quiz.css` grows one new rule (`.quiz-take-preamble`). Mitigation: a small CSS block; no `base.css` change.

**Becomes impossible (under this ADR):**

- A `RunResult` whose `status` is fabricated (the structured `status` field is unchanged; the splice change does not introduce any new failure-fabrication path).
- The preamble being written under `content/latex/` (the splice writes to the temp `cwd`; ADR-042's MC-6 protection is preserved).
- A non-coding artifact in the preamble block (the template renders raw source via `<pre>`; if the persisted preamble were somehow a non-coding artifact (which the upstream schema's `extra="forbid"` forbids), it would still render as escaped text in a `<pre>`, not as an interactive surface).
- The take page rendering an empty preamble block as a visible empty box (the `{% if aq.preamble %}` guard omits it cleanly).

**Future surfaces this ADR pre-positions:**

- A future ADR adding a runner-side default header (e.g. `#include <cassert>`) injected before the preamble — additive (the splice gains a leading prefix); bounded.
- A future ADR adding language-specific splice variants (the C++ splice differs from the Python splice in some way ADR-042's sniff doesn't handle) — additive (the language sniff already routes to per-language code paths); bounded.
- A future ADR adding a "show test output inline with the test suite" mode — additive to the take template.

**Supersedure path if this proves wrong:**

- If the splice order proves wrong (a runner slice's `/design` finds a real case where `preamble + response + test_suite` fails) → a future ADR adjusts the order or introduces per-language splice variants; bounded.
- If the omitted-when-empty rule proves wrong (the learner wants an explicit "no shared shapes" caption for clarity) → a future ADR changes the template's empty-case rendering; bounded.
- If the additive splice signature proves insufficient (a runner slice wants to support multiple preambles, or a structured preamble with metadata) → a future ADR supersedes the signature; bounded.

The supersedure path runs through a new ADR. This ADR does not edit any prior ADR in place; it builds on ADR-042 (the runner — consumed unchanged but for the splice signature), ADR-043 (the route + surface — consumed unchanged but for the one-argument pass-through and the one new template block), ADR-044 (the test-result persistence — consumed unchanged), ADR-046 (the storage mechanics — consumed as a peer), ADR-008 (the CSS namespacing — preserved), ADR-035 (the no-JS posture — preserved), ADR-031 (the no-relocate recipe — preserved), and ADR-045 (the prompt + schema decisions whose structural realization this ADR is).
