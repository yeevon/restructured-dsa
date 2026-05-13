# TASK-008 leak-path empirical confirmation

**Status:** Resolved by ADR-019 + ADR-020 + implementer's adjacent fix (new `_consume_balanced_bracket_optional_arg` helper at three optional-arg extraction sites). Empirical leak path confirmed in TASK-008 audit Run 004 / Run 005: ch-13 examplebox `$[2,5,3,0,2,3,0,3]$` title triggered an unbalanced-bracket regex on the success path (not the parse-failure fallback). The new bracket-consumption helper is the load-bearing fix; ADR-020's defensive helper is defense-in-depth for genuine `_escape(raw)` parse-failure cases. See audit Run 005 for the recommendation that a follow-up architect cycle codify the bracket helper as an ADR-017 sibling.
**Surfaced:** 2026-05-10 (TASK-008 architect Mode 2 `/design`)
**Decide when:** as the first step of `/implement TASK-008`, before the implementer applies the ADR-019 / ADR-020 fixes.

## Question

The TASK-008 architect, in Mode 2 (`/design`), was required by the task file to **reproduce Gap B's text-formatting-macro leak in code/output before picking the fix shape (the leak path is not yet confirmed)**. The architect had no shell access in `/design` mode and could not run a diagnostic test against the running FastAPI app.

The architect's `/design`-time corpus walk over `content/latex/*.tex` produced a different finding than the TASK-005 catalog suggested: there are **zero source-level unhandled `\begin{...}` environments in the corpus** that aren't explicitly handled or explicitly skipped by `app/parser.py`. The "28 unhandled `\begin{...}` instances, ch-09 (22)" framing in the TASK-005 catalog (orchestrator Run 008) does not survive corpus inspection.

The leaks the human observed in TASK-005 screenshots therefore must originate from a path other than "source-level unhandled env." Three candidate paths are identified statically in ADR-019 (Context section) and ADR-020 (Context section), but the architect did not confirm which is responsible. The implementer must run the diagnostic before applying the fix to ensure the fix targets the actual site.

## Options known

The implementer's first step in `/implement TASK-008` is to run a diagnostic test that exercises every Chapter's `GET /lecture/{id}` response and reports:

- For each Chapter: count and snippets of literal `\begin{X}` and `\end{X}` substrings outside `<pre>/<code>` blocks and outside `\[...\]` / `$...$` math zones.
- For each Chapter: count and snippets of literal `\textbf{`, `\textit{`, `\emph{`, `\textsc{` substrings outside the same safe zones.
- For each leaked substring: ~80 characters of surrounding context for the implementer's eyes.

The diagnostic is a one-shot pytest that runs against the FastAPI TestClient (the same fixture pattern used by `tests/test_task005_multi_chapter_smoke.py`). It does not assert anything (always passes); it prints findings to stdout for the implementer to read.

After running the diagnostic, the implementer:

1. Confirms whether the leak sites match ADR-019 (env-level wrapper, parser line 285-295 / 874-883) or ADR-020 (raw-text fallback, parser line 254-255 / 466 / 834-835 / 924-931) — or another site.
2. **If the leaks match either ADR**, proceeds to implement those ADRs.
3. **If the leaks DO NOT match either ADR**, raises an `ESCALATION:` to the architect for a supersedure ADR that targets the actual site. Does not apply ADR-019 / ADR-020 in this case, since the bug is not at those sites.

## Constraints

- ADR-019 (Accepted 2026-05-10) and ADR-020 (Accepted 2026-05-10) are designed to be robust to any of the three candidate sites the architect identified statically. If the actual site is one of those, the ADRs are correct as written.
- ADR-003 (Accepted) commits to "warn-per-node, do not crash, do not fabricate." The diagnostic test does not change parser behavior; it observes it.
- TASK-008 acceptance criteria require empirical confirmation: AC-1 ("zero substrings matching `\begin{algorithm}`, ...") cannot be verified without running the diagnostic.
- Manifest §3 (drive consumption): the leaks are real (the human saw them in TASK-005 screenshots); confirming the path is necessary to ensure the fix actually closes the visible damage.

## Resolution

When resolved, mark this issue `Resolved by ADR-019 + ADR-020 + diagnostic-test confirmation in TASK-008 audit Run NNN` (or `Resolved by ADR-NNN` if a supersedure ADR is needed because the actual site is different).
