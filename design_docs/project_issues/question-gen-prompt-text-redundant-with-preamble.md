# `question_gen` prompt-text redundant with preamble — the LLM tells the learner to "implement X" when X is already defined in the preamble

**Status:** Open
**Surfaced:** 2026-05-13 by the TASK-018 Verification Gate 2 run (real-engine end-to-end sanity on a regenerated Quiz)
**Related ADRs:** ADR-045 (the prompt + schema change this issue extends), ADR-040 (the original `question_gen` prompt this issue continues), ADR-036 (the `ai-workflows` integration shape — unchanged)
**Related task:** TASK-018 (which shipped the assertion-only + `preamble`-field mechanism this issue refines)
**Audit pointer:** `design_docs/audit/TASK-018-question-gen-prompt-assertion-only-test-suites.md` Run 009 §"Adjacent finding"

## Observed behavior

A regenerated Quiz Question (post-TASK-018) carries the expected three-piece shape:

- `preamble`: contains a full struct/class definition (e.g. `struct Point2D { int x; int y; };`).
- `test_suite`: assertion-only — references but does not redefine the struct.
- `prompt`: includes a coding-task instruction that **still asks the learner to "implement Point2D"** alongside (or instead of) asking them to implement the function-under-test that uses `Point2D`.

The mechanism (the splice, the persistence, the take-page rendering) is correct. The learner can still complete the task and get a real `passed=True` (verified — Verification Gate 2 passed). But the prompt-text is **editorially noisy**: it asks the learner to "implement" a type whose definition is already shown to them in the `preamble` block, so the prompt and the preamble carry overlapping / contradictory framing.

## Why it happens

`_question_gen_prompt_fn`'s STRICT REQUIREMENTs are silent on what to do when the function-under-test takes a type that is itself defined in the `preamble`:

- **STRICT REQUIREMENT 6** instructs the LLM to "NAME the exact function/class signature in the prompt." If the function-under-test takes a struct-typed parameter, the literal reading is "name the function signature, which mentions the struct, in the prompt." Some LLMs interpret this as "instruct the learner to implement everything named in the signature, including the struct."
- **STRICT REQUIREMENT 8** instructs the LLM to put shared struct/class shapes in `preamble` and forbids them from appearing in `prompt` or `test_suite`. But it does not affirmatively say "the prompt MUST NOT instruct the learner to implement a type whose definition is in `preamble`."

The LLM resolves the ambiguity by being thorough — naming all the entities — which produces the redundancy observed.

## Options

### (a) Add a STRICT REQUIREMENT 9 that disambiguates

Extend `_question_gen_prompt_fn`'s STRICT REQUIREMENTs with something like:

> **9.** When the function-under-test takes (or returns) a type defined in `preamble`, the `prompt` MUST describe the function-under-test only — never instructing the learner to define, implement, or re-declare that type. The type is given; the learner's task is the function. Example wording: "Implement `void update_and_calculate_distance_squared(Point2D& p, …)` that updates `p.x`/`p.y` and computes the squared distance." NOT "Implement a `Point2D` struct AND `update_and_calculate_distance_squared`."

Forecast: cleanest fix. A one-line prompt edit. No schema change. No ADR amendment required (ADR-045's positive commitments are unaltered — the new requirement adds a constraint to the prompt text the LLM produces, not to the schema/route/runtime). Resolves this issue directly.

### (b) Drop "name the function/class signature" from REQ-6 and rely on REQ-8 alone

Tighter prompt, but loses the affordance that the `prompt` text names the implementation target the learner is writing code against — risking a "what function am I supposed to write?" UX miss. Rejected forecast.

### (c) Move the implementation-target-naming into the take page's CSS / DOM rather than the prompt text

Out of scope. The current take page already surfaces `prompt` + `preamble` + `test_suite` as three distinct read-only blocks; the prompt's job is the human-readable instruction.

### (d) Leave as-is

The mechanism works. The redundancy is a minor editorial wrinkle, not a correctness issue. But it's noise the learner has to filter through on every regenerated Question.

## Forecast for `/design`

Option (a) — a one-line STRICT REQUIREMENT 9 on `_question_gen_prompt_fn` plus a corresponding wording tweak to REQ-6 (so the two don't appear to contradict). A small follow-up task; no new ADR required (TASK-018-style "prompt wording change with no schema/route/runtime change"); the existing TASK-018 ADRs (045/046/047) continue to apply.

After the prompt edit lands, the re-run real-engine generation gate is the verification: a regenerated Question's `prompt` should describe **only** the function-under-test, with the struct/class shapes living in `preamble` and not echoed in `prompt`.

## Conformance reasoning

- **MC-1:** `app/workflows/question_gen.py` imports unchanged (just a string-edit). PASS.
- **MC-5:** the `min_length=1` validator on `test_suite` stays; `preamble`'s empty-string-allowed semantic stays. PASS.
- **MC-7:** no `user_id` introduced. PASS.
- **MC-9:** no Quiz auto-generated. PASS.

## Out of scope

- The schema change (`GeneratedQuestion.prompt` / `.test_suite` / `.preamble`) — unchanged by this fix.
- The persistence layer — unchanged.
- The sandbox splice / runner — unchanged.
- The take page rendering — unchanged.
- Existing pre-fix Questions in the Question Bank — they keep their existing `prompt` text; the §8 no-delete posture stands. The fix improves *future* generations.

## Priority

**Low / editorial.** TASK-018 shipped the structural mechanism end-to-end; the runner returns honest pass/fail on real Questions today. This is a polish task that improves the learner's reading experience on regenerated Quizzes. Slot below the grading slice (the manifest's next §6 milestone — closing the reinforcement loop).
