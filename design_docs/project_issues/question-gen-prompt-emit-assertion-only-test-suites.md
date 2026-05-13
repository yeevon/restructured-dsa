# Moved — Resolved by ADR-045 + ADR-046 + ADR-047 (TASK-018, 2026-05-13)

This project_issue was resolved and archived. The full file (with resolution note + original body) is at:

`design_docs/project_issues/Resolved/question-gen-prompt-emit-assertion-only-test-suites.md`

Architectural decisions resolving the issue:

- **ADR-045** — the `question_gen` prompt change to assertion-only test suites + the additive `GeneratedQuestion.preamble: str = Field(default="")` field; option (a) chosen over option (b).
- **ADR-046** — the `questions.preamble` persistence column + `Question.preamble` / `AttemptQuestion.preamble` dataclass fields.
- **ADR-047** — the `run_test_suite(test_suite, response, preamble="")` splice extension (no ADR-042 supersedure) + the take-surface read-only `<pre class="quiz-take-preamble">` block.
