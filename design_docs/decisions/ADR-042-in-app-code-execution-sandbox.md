# ADR-042: The in-app code-execution sandbox — a bare subprocess under `resource` rlimits + a wall-clock timeout in a throwaway temp working directory; the learner's code is concatenated with the Question's test suite and compiled as a single C++ translation unit (Python sniffed as a secondary path); a structured `RunResult` with a `ran | timed_out | compile_error | setup_error` status; no new `pyproject.toml` dependency

**Status:** `Accepted`
**Auto-accepted by /auto on 2026-05-12**
**Date:** 2026-05-12
**Task:** TASK-017
**Resolves:** part of `design_docs/project_issues/in-app-test-runner-slice-shape.md` (with ADR-043 + ADR-044) — the sandbox / code-execution sub-question
**Supersedes:** none — consumes ADR-040 / ADR-041 (the `questions.test_suite` representation), ADR-022 (the persistence boundary, for the route side), MC-6 (the lecture-source read-only invariant), MC-1 (the AI-engine boundary), MC-4 (the async-AI rule — reasoned around explicitly here), unchanged

## Context

The 2026-05-12 manifest amendment added §6 "**Code is written, run, and tested within the application. The learner answers a Question by writing code, running it, and running tests against it — all inside the application's own interface. No external editor, no separate test runner, no copy-paste-into-another-tool workflow**" and tightened §8 (Quiz Attempt "the in-app test results for each response"; Grade correctness "determined by whether the learner's code passed the Question's tests"). TASK-016 (ADR-040 / ADR-041) shipped the precondition — a Question now carries a runnable test-code string in `questions.test_suite` — but nothing executes it. TASK-017 is the slice that makes it *run*: the learner, on the take page (ADR-038's surface), clicks "Run tests" and the application executes that test suite against the code they wrote. This ADR owns the **execution engine** — the isolation mechanism, the test-suite/learner-code splice, the supported languages, and the structured result shape. ADR-043 owns the "Run tests" route + the take-surface affordance; ADR-044 owns the `attempt_questions` test-result persistence layer.

Constraints that bind this decision:

- **The threat model is "the author can already run anything on their own machine."** The project is single-user, single-machine, locally-run, no remote deployment (manifest §5). The "attacker" who could submit malicious code is the author themselves. So the requirement here is **robustness**, not adversarial isolation: a learner's infinite loop must not hang the app; a learner's `rm -rf` / `open("../../content/latex/...", "w")` must not touch the lecture source (MC-6) or `data/notes.db`. We are not defending against a determined attacker with code-execution on their own laptop — that's a non-goal under §5's "no remote deployment".
- **MC-6 (lecture source read-only) is load-bearing.** The sandbox must never be able to write under `content/latex/`. The learner's code runs in a freshly-created temp working directory away from the corpus; the corpus path is never passed to the child; the child inherits no working directory or env that points at it.
- **MC-1 is not implicated.** The sandbox runs *test code* against *implementation code* — there is no LLM, no `ai-workflows` call, no forbidden SDK. The module lives under `app/` but **not** under `app/workflows/` (which is the AI-workflow path MC-1 names). MC-1 stays vacuously clean.
- **MC-4 does not bind the test-run path** — see "Conformance check" below. Running a test suite is executing code, not AI work; the manifest's async-AI rule is about LLM-driven processing (generation, grading, lecture audio), which this isn't. A synchronous, timeout-bounded run is permitted (ADR-043 makes the synchronous-vs-async call; this ADR records *why* MC-4 is not in play).
- **The runner must work with ADR-040's *current* output.** The TASK-016 real-engine gate (`quiz_id=6`) revealed that the LLM-generated `test_suite` strings currently embed a *reference implementation* of the function under test inline (e.g. a 2.3 KB C++ `#include <cassert>` file that *defines* `void append(LinkedList&, Node*)` itself and then `assert`s against it). The runner cannot depend on a `question_gen`-prompt change that hasn't happened. See "The splice" and the new project_issue this ADR files.
- ADR-040's `question_gen` prompt steers the LLM toward C++ implementations; the real-engine gate produced C++ `#include <cassert>` test files. The sandbox must compile-and-run C++. If a `test_suite` targets Python, the sandbox runs Python.

## Decision

### The isolation mechanism — a bare subprocess under POSIX `resource` rlimits + a `subprocess.run(timeout=...)` wall-clock cap, in a throwaway `tempfile.mkdtemp()` working directory

A new module **`app/sandbox.py`** (not under `app/workflows/`) exposes one public entry point — `run_test_suite(test_suite: str, response: str) -> RunResult` — that:

1. **Creates a fresh throwaway working directory** via `tempfile.mkdtemp()` (under the OS temp root — never under `content/latex/` or `data/`). All files the run produces (source files, the compiled binary, any file the learner's code writes) land there. The directory is removed (`shutil.rmtree`) in a `finally` after the run, regardless of outcome.
2. **Writes the spliced source** into that directory (see "The splice" below).
3. **Compiles** (for C++) by invoking `g++` (a system binary — see "The `pyproject.toml` question") as a subprocess, with `cwd=` the temp dir, a `subprocess.run(timeout=...)` cap on the compile step, and a `resource`-rlimit preexec that bounds CPU time and address space so a pathological test suite can't wedge the compiler. Compilation failure → `RunResult(status="compile_error", passed=None, output=<the g++ diagnostic, truncated>)`.
4. **Runs** the resulting program as a subprocess with:
   - `cwd=` the temp dir (so any file the learner's code writes goes there, not under `content/latex/`),
   - a fresh minimal env (no inherited `PWD`/`OLDPWD` pointing at the corpus; no need to pass anything in),
   - `stdin` closed / `/dev/null`,
   - `subprocess.run(timeout=T_RUN)` — a wall-clock cap (a few seconds; the exact value is the implementer's, tunable like ADR-036's tier model string); on `TimeoutExpired` the child (and its process group) is killed and the result is `RunResult(status="timed_out", passed=None, output=<partial output + "the test run timed out">)`,
   - a `preexec_fn` (POSIX) that calls `resource.setrlimit` for:
     - `RLIMIT_CPU` — a CPU-seconds cap (defence-in-depth alongside the wall-clock timeout, against a busy loop that the wall-clock timeout would also catch),
     - `RLIMIT_AS` — an address-space cap (a memory bomb is killed by the kernel, not by swapping the host to death),
     - `RLIMIT_NPROC` — a process-count cap (a fork bomb hits the limit instead of the host),
     - `RLIMIT_FSIZE` — a written-file-size cap (a disk bomb is bounded),
     - `RLIMIT_CORE = 0` (no core dumps),
     - and `os.setsid()` so the child is its own process group (the timeout-kill reaps the whole group, not just the leader).
   - Exit code 0 (and the program ran the assertions) → `RunResult(status="ran", passed=True, output=<combined stdout+stderr, truncated>)`. Non-zero exit (an `assert` fired, or the program aborted) → `RunResult(status="ran", passed=False, output=<combined stdout+stderr, truncated>)`.
5. **Any sandbox-setup failure** that is not a compile error or a timeout (the temp dir can't be created, `g++` is not on `PATH`, an unrecognized test-suite language — see below) → `RunResult(status="setup_error", passed=None, output=<the failure message>)`. Never a fabricated `passed`.

No container, no `bubblewrap`/`nsjail`/`firejail`, no WASM/`pyodide`. The bare-subprocess-under-rlimits approach is the lean fit for the single-user/single-machine/locally-run threat model; a Linux-native jail is a reasonable *future upgrade* if the bare subprocess ever proves leaky (it can be slotted in behind the same `run_test_suite` interface without changing ADR-043 or ADR-044). The `RunResult` interface is the stable seam: the route and persistence depend on the result shape, not on the mechanism.

`app/sandbox.py` uses only the stdlib (`subprocess`, `resource`, `tempfile`, `shutil`, `os`, `pathlib`). It imports nothing from `app.persistence` (the route, not the sandbox, persists the result), nothing from `app.workflows`, no LLM SDK, no `ai_workflows.*`. **POSIX/Linux-only** — `resource.setrlimit` and `os.setsid` are POSIX; the dev environment is Linux; this is documented in the module and is consistent with the project being a locally-run personal project (manifest §1, §5).

### The supported languages — C++ via `g++` (primary), Python via `python3` (secondary, sniffed); an unrecognized language is a `setup_error`

`run_test_suite` sniffs the test-suite string to pick a runtime:

- **C++** — the source contains `#include` (ADR-040's prompt steers the LLM toward C++ `#include <cassert>` test files; the real-engine gate confirmed this). The runner writes `submission.cpp`, compiles with `g++` (`-std=c++17` or similar — implementer's call), and runs the binary under the limits above.
- **Python** — the source contains `import ` / `def test` / `unittest` / `pytest` markers and no `#include`. The runner writes `test_suite.py`, runs it with `python3` under the limits above (a `python3 test_suite.py` invocation; the test suite is expected to self-execute its assertions / `unittest.main()` — same "the test suite is self-contained" expectation as the C++ path).
- **Anything else** → `RunResult(status="setup_error", passed=None, output="unrecognized test-suite language")` — surfaced honestly; never a fabricated pass/fail.

The sniff is a heuristic (like ADR-036's prompt wording), tunable without a re-decision. C++ is the language the current generator produces; Python is supported because §8 / the task ask for it; the unrecognized-language path is the honest fallback.

### The splice — concatenate the learner's `response` followed by the Question's `test_suite` into a single translation unit

`run_test_suite` builds the source it compiles/runs as `response + "\n\n" + test_suite` (the learner's implementation first, then the test suite). For a **clean assertion-only test suite** — one that *references* the implementation target by name (e.g. calls `append(...)`) but does *not* define it — this is the correct splice: the learner provides the definition, the test suite provides the assertions, one translation unit, it compiles and runs. The pytest tests for the sandbox (and a fixed `question_gen` prompt — see below) use this form.

For ADR-040's **current** output — a `test_suite` that *embeds a reference implementation* of the target inline — the concatenation double-defines the target → `g++` reports a redefinition / `main` ambiguity → `RunResult(status="compile_error", ...)`, surfaced honestly. The runner does **not** attempt to textually strip the reference implementation from the test suite (a heuristic body-replacement splice — match `void append(...) {` to its closing `}` and swap the body — was considered and rejected as too fragile: it depends on exact formatting, brace balance, overloads, templates, and name mangling, and a wrong strip silently corrupts the test). The honest engineering call is: the **runner** is built right for assertion-only test suites; the **generator** needs a small prompt change to emit assertion-only test suites; that change is a separate TASK. This ADR files `design_docs/project_issues/question-gen-prompt-emit-assertion-only-test-suites.md` capturing it, and notes that **the real-engine end-to-end run-tests gate in TASK-017's "Verification gates" depends on that prompt change landing first** (until then a real `quiz_id=6`-style Question's reference-impl-embedding `test_suite` will report `compile_error`, not pass/fail — an honest result, not a fabricated one, so MC-5's spirit is intact, but not the responsive pass/fail loop the gate describes). This is upflow, surfaced for the human: either the `question_gen`-prompt-change TASK is scheduled before TASK-017's real-engine gate is filled, or the gate is filled against a hand-written assertion-only test suite. The architect does not edit TASK-017's task file in Mode 2; this ADR records the dependency and the project_issue carries the follow-on work.

### The structured result shape — a `RunResult` dataclass with `status`, `passed`, `output`

`app/sandbox.py` defines:

```
@dataclass
class RunResult:
    status: str            # 'ran' | 'timed_out' | 'compile_error' | 'setup_error'
    passed: bool | None    # meaningful only when status == 'ran'; None otherwise
    output: str            # combined stdout+stderr of the run, or the compiler
                           # diagnostic (compile_error), or the failure message
                           # (timed_out / setup_error); truncated to a sane cap
                           # (e.g. 16 KiB) to bound the size persisted to the DB
```

`status` is the load-bearing field for honesty: `passed` alone (a bare `INTEGER`) cannot distinguish "the tests ran and failed" from "the tests timed out" from "the test suite didn't compile" — and conflating those would be the MC-5-spirit violation the task warns against. The route (ADR-043) reads this and the persistence layer (ADR-044) stores all of it (`test_passed` ← `passed`, `test_status` ← `status`, `test_output` ← `output`, `test_run_at` ← now). `RunResult` is the sandbox module's transient return type — it is *not* a persistence dataclass and does not live in `app/persistence/`; the persisted view is ADR-044's `AttemptQuestion` extension. Two dataclasses at two layers, deliberately.

### The `pyproject.toml` question — no new dependency

`subprocess`, `resource`, `tempfile`, `shutil`, `os`, `pathlib` are all stdlib. `g++` and `python3` are system binaries, not pip packages — invoked via `subprocess`, not imported. A `psutil` was considered for cross-platform process limits and rejected: `resource` covers what's needed on Linux, the project is Linux-only, and adding a dependency to dodge a Linux assumption that the project already makes everywhere else is not worth it. **No `pyproject.toml` change.** If the implementer's investigation finds a genuine need (it shouldn't), the implementer makes the edit and flags it — the architect does not edit `pyproject.toml` in Mode 2 (ADR-036's precedent: the human/implementer owns dependency edits).

## Alternatives considered

**A. A container — `docker run --network=none --read-only --memory=... --cpus=... --workdir=/tmp ...` with the spliced source mounted in.** More isolation (a real kernel namespace boundary, no filesystem visibility into the host at all). Rejected: it adds Docker as a hard runtime dependency the project does not have and does not want — the manifest's "no remote deployment / locally-run" simplicity ceiling (§5) reads against pulling in a container runtime to run a few seconds of C++ on a personal laptop; the single-user threat model ("the attacker is the author") does not justify it; and a Docker dependency would have to be installed, daemon-running, and image-pulled before the take page works — a heavy precondition for a "click Run, see pass/fail" loop. If the bare subprocess ever proves leaky, a container (or a lighter jail) slots in behind `run_test_suite` — but starting there is over-engineering for the threat model. (It would have made adversarial isolation easier and made the "just works on a fresh checkout" property harder.)

**B. A Linux-native jail — `bubblewrap` / `nsjail` / `firejail` wrapping the subprocess.** More isolation than a bare subprocess (a real mount/PID namespace, `--ro-bind` the corpus or don't bind it at all), fewer dependencies than Docker, Linux-only (fine — the dev env is Linux). Rejected *for this slice* as more than the threat model needs: the bare subprocess + a temp `cwd` + rlimits already gives the robustness guarantees (no host hang, no `content/latex/` write, no `data/notes.db` corruption — the child runs in a temp dir and the route, not the child, touches the DB); a jail's extra hardening is defence against an adversary the §5 non-goals say we're not defending against. It is the documented upgrade path if the bare subprocess proves leaky — recorded here so a future task can take it without re-litigating the whole decision. (It would have made adversarial isolation easier and made the module a touch more complex / a `bwrap`-binary precondition.)

**C. A WASM / `pyodide` in-browser sandbox — the learner's code never reaches the server; it runs in the browser tab.** Maximal isolation for the host (the code literally never touches the server's filesystem or process table). Rejected for the grading-feeding path: §8 Grade's "correctness determined by whether the learner's code passed the Question's tests" requires the server to *trust* the test result — and a result computed in the browser is trivially forgeable (the learner can edit the JS to report "passed"), which is fine if the learner is the only user and is honest with themselves, but it makes the persisted `attempt_questions` test result (which the grading slice reads, which the composition slice's wrong-answer-replay history reads — MC-8) a value the server cannot stand behind. It could be a *preview* layer on top of a server-side runner some day, but it cannot *be* the runner. Also: it adds a browser-side WASM toolchain (Emscripten for C++, `pyodide` for Python) — a heavy front-end build the project does not have. (It would have made host-isolation trivial and made a trustworthy grading signal impossible.)

**D. A heuristic body-replacement splice — parse the `test_suite` to find the reference implementation of the target and swap in the learner's body, so ADR-040's current output works as-is.** Rejected as too fragile (see "The splice"): finding `void append(LinkedList&, Node*) { ... }` and its matching `}` reliably means a real C++ parse (overloads, templates, default args, nested braces, comments-with-braces, string-literals-with-braces); a wrong strip silently corrupts the test and produces a wrong verdict — the exact failure mode MC-5's spirit forbids. Concatenate-and-let-`g++`-report-the-redefinition is *honest* (a compile error is a true statement about a self-contained-test-suite + learner-code pair) where a botched strip is *dishonest*. The right fix is the generator, not the runner — and that's a small, well-scoped, separate change (the new project_issue).

**E. A new `attempt_question_runs` table for run-history vs denormalized columns on `attempt_questions`** — this is ADR-044's call, not this ADR's; noted here only to record that the sandbox ADR is language/mechanism/result-shape and does not pre-decide the persistence shape.

**F. Out-of-band test running — a "Run tests" click records a request, an out-of-band runner processes it, the result shows on the next page load (mirroring ADR-037's generation processor).** This is ADR-043's call (synchronous vs async); recorded here only because the sandbox engine is the same either way — `run_test_suite` is a plain function; whether it's called from a request handler or from a poll-loop is the route ADR's decision. The architect's position (carried into ADR-043): synchronous, because MC-4 does not apply (running tests is not AI work) and §6 reads as wanting a responsive write→run→see loop.

## My recommendation vs the user's apparent preference

**Aligned with the task's forecast and with ADR-040's reordering**, with these calls made:

- **The isolation mechanism — a bare subprocess under `resource` rlimits + a wall-clock timeout in a throwaway temp dir.** Exactly the task's forecast ("a bare subprocess with `resource` limits + a timeout + a restricted temp `cwd` … given the single-user/single-machine threat model and the robustness need"). The roadmap memory frames the code-runner as the "future big feature: in-browser IDE + run-tests-against-learner-code" with "VS Code online" as a *reference point, not a literal spec* — and lists it *last* in a now-stale order; ADR-040 §My recommendation already established (and the human auto-accepted ADR-040) that the conformant order is Questions-carry-tests → in-app test-runner (this task) → grading → composition → TTS. This ADR builds the runner, not an IDE; a richer editing surface is a separate later consideration if ever wanted (the take page's `<textarea>` + "Run tests" + a results panel satisfies §6). No tension with the manifest; the roadmap memory note is the stale artifact (the architect owns nothing there — flagged for the human to update).
- **The splice — concatenate, not strip; and `question_gen`'s prompt needs to emit assertion-only test suites.** This is the one place the slice's reality bites: ADR-040's *current* output embeds a reference impl, which the concatenate splice (correctly) rejects with a compile error. The architect's call is to build the runner right (concatenate; correct for assertion-only test suites) and file the generator fix as a project_issue rather than bolt a fragile strip into the runner or fold a `question_gen` change into TASK-017 (out of scope — see TASK-017 §Out of scope: "If `/design` concludes `question_gen`'s prompt should change … file a project_issue, don't fold it in"). The cost: TASK-017's real-engine end-to-end gate depends on that follow-on. The architect surfaces this as upflow and lets the human decide the ordering — it is not a manifest tension (the manifest is fine; the generator output and the runner expectation are out of step, a known and small gap).
- **The supported languages — C++ primary, Python sniffed secondary, unrecognized → setup_error.** The task said "C++ via `g++` per ADR-040's prompt steer; Python if a `test_suite` targets it" — done, with the honest unrecognized-language fallback.
- **No `pyproject.toml` dependency.** The task forecast was "probably none, `resource` + `subprocess` are stdlib" — confirmed.

Re-flag (not actioned): `design_docs/project_issues/tooling-lint-and-type-check.md` (Open, 11th+ recurrence) — `app/sandbox.py` (subprocess handling, rlimit preexec, temp-dir lifecycle) is exactly the kind of code where a type-checker earns its keep, but the architect's standing recommendation holds: not while there's a feature slice; the lint/type-check ADR lands in a non-feature cycle.

## Consequences

**Becomes possible / easier:**

- §6's "Code is written, run, and tested within the application" becomes *true* — the learner can run the Question's tests against their code, in-app, and see the verdict (ADR-043 wires the route + surface; this ADR is the engine).
- A §8-conformant Grade becomes *buildable* — "correctness determined by whether the learner's code passed the Question's tests" needs the test result; this slice produces it; the grading slice (next) reads it.
- The runner's mechanism is swappable behind `run_test_suite(test_suite, response) -> RunResult` — a `bubblewrap` jail (or, in extremis, a container) can replace the bare subprocess without touching ADR-043 or ADR-044.

**Becomes more expensive:**

- A new `app/` module (`app/sandbox.py`) with subprocess + rlimit + temp-dir lifecycle code. Mitigation: stdlib only; one public function; the `RunResult` dataclass; ~150 lines; pinned by pytest (pass / fail / timeout-within-bounded-wall-clock / compile-error / setup-error / no-`content/latex/`-write).
- A POSIX/Linux assumption made explicit in code (`resource.setrlimit`, `os.setsid`). Mitigation: the project is already Linux-only and locally-run (manifest §1, §5); this is consistent, not a new constraint.
- A follow-on TASK to change `question_gen`'s prompt to emit assertion-only test suites (the new project_issue). Mitigation: small (a prompt-wording change + a re-run of the real-engine gate), well-scoped, and the runner is correct in the meantime (honest compile error, never fabricated).

**Becomes impossible (under this ADR):**

- A learner's infinite loop hanging the app (`subprocess.run(timeout=...)` + `RLIMIT_CPU` + process-group kill).
- A learner's code writing under `content/latex/` (the child runs `cwd=` a throwaway temp dir; the corpus path is never passed to the child; MC-6 preserved) or corrupting `data/notes.db` (the child never touches the DB — the route persists the result via `app.persistence.*` after the child returns).
- A fork bomb / memory bomb / disk bomb taking the host down (`RLIMIT_NPROC` / `RLIMIT_AS` / `RLIMIT_FSIZE`).
- A fabricated test result (a sandbox failure — timeout, crash, compile error, setup error — is surfaced as that status, never as `passed=True`/`passed=False`; `status` carries the truth; MC-5's spirit honored).
- An LLM call from the run path (`app/sandbox.py` imports no AI; it is not under `app/workflows/`; MC-1 vacuously clean).

**Supersedure path if it proves wrong:** if the bare subprocess proves leaky (a `resource` limit doesn't bind on some path, a `g++` toolchain quirk, a child escapes the process group), a new ADR slots a `bubblewrap`/`nsjail` jail behind `run_test_suite` — the interface is stable, so ADR-043 (route) and ADR-044 (persistence) are untouched. If the concatenate splice proves wrong even for assertion-only test suites (some C++ ordering issue), a new ADR revisits the splice — but the generator-side fix (assertion-only emission) should land first regardless.

## Manifest reading

- **§6 "Code is written, run, and tested within the application … all inside the application's own interface. No external editor, no separate test runner, no copy-paste-into-another-tool workflow"** — read as **binding product behavior** and as the entry this slice implements. It reads as wanting a responsive write→run→see loop (the learner clicks Run and sees pass/fail), which informs ADR-043's synchronous-route call. Not architecture-in-disguise — it says *what* the product does (the learner runs tests in-app), not *how* (subprocess vs container vs WASM is this ADR's call).
- **§5 "No remote deployment / hosted product"** and **"No multi-user features"** — read as **binding**. The former bounds the sandbox's complexity ceiling (a local sandbox, not a cloud-execution service; it argues against the container alternative); the latter means no `user_id` on anything the runner produces (ADR-044's columns; no auth/session). Not architecture-in-disguise — they're scope/non-goal statements.
- **§8 Quiz Attempt "the in-app test results for each response"; Grade correctness "determined by whether the learner's code passed the Question's tests"** — read as **binding glossary/behavior**. They name the downstream consumer of the `RunResult` (the test result is persisted on the Attempt; the Grade is defined in terms of it). Not architecture-in-disguise.
- **§1 "Personal project. Single author, single user … does not replace [SNHU enrollment]"** — read as **binding context**; it justifies the Linux-only / locally-run posture and the lean threat model. Not architecture-in-disguise.
- No manifest entry read as architecture-in-disguise for this decision. No manifest entry flagged. No manifest tension — the manifest is internally consistent; the only cross-artifact gap (ADR-040's current generator output vs the runner's assertion-only-test-suite expectation) is between two ADRs / a project_issue, not with the manifest.

## Conformance check

- **MC-1 (No direct LLM/agent SDK use).** `app/sandbox.py` lives under `app/` but **not** under `app/workflows/` (the path MC-1 names for AI-workflow code); it imports only the stdlib — no `openai`/`anthropic`/`google.*`/`cohere`/`mistralai`/`groq`/`together`/`replicate`/`litellm`/`langchain*`/`langgraph*`, no raw provider HTTP, not even `ai_workflows.*`. There is no AI in the run path — it executes test code. **PASS** (vacuously — this ADR adds no AI surface).
- **MC-4 (AI work asynchronous from the learner's perspective).** **Reasoned around explicitly, not violated.** MC-4 binds *AI-driven processing* — generation, grading, lecture audio — which complete out-of-band and notify the learner when ready. **Running a test suite is not AI work** — it is executing code; there is no LLM, no `ai-workflows` invocation, no model call. So MC-4 does not require the test run to be out-of-band, and ADR-043 may (and does) make it synchronous-with-a-timeout. Separately, MC-4 stays satisfied: this slice adds no new AI-driven processing; the existing AI surfaces (generation; future grading; future TTS) remain out-of-band; the submit route (ADR-038) is unchanged; grading is still invoked from no request handler. **PASS** (the manifest principle is untouched; the test-run path is correctly identified as outside its scope).
- **MC-5 (AI failures surfaced, never fabricated).** Orthogonal to the runner in the letter (no AI in the run path) but binding in spirit: a runner failure — `timed_out`, `compile_error`, `setup_error`, or a child crash — is reported as that `status`, never as a fabricated `passed=True`/`passed=False`. The `RunResult.status` field exists precisely so the failure modes are not conflated with "tests ran and passed/failed". **PASS** (spirit honored).
- **MC-6 (Lecture source read-only).** **Load-bearing and honored.** The child runs `cwd=` a freshly-created `tempfile.mkdtemp()` directory under the OS temp root — never under `content/latex/` or `data/`; the corpus path is never passed to the child, never in its env, never on its argv; the child inherits no working directory pointing at the corpus. The temp dir is `shutil.rmtree`'d after the run. A pytest case asserts that a `response` which attempts a write under `content/latex/` leaves the corpus byte-for-byte unchanged. **PASS.**
- **MC-7 (Single user).** No `user_id` anywhere in `app/sandbox.py`, the `RunResult` dataclass, or anything this ADR introduces; no auth, no session, no per-user partitioning. **PASS.**
- **MC-10 (Persistence boundary).** `app/sandbox.py` imports no `sqlite3`, embeds no SQL literal, never opens a DB connection, never touches `data/notes.db` — it returns a `RunResult` to the route, which persists it via `app.persistence.*` (ADR-044). **PASS** (the sandbox is on the right side of the boundary).
- **MC-2 / MC-3 / MC-8 / MC-9** — orthogonal (no Quiz-scope/designation/loop/generation logic in the runner); unaffected. **PASS.**

## Test-writer pre-flag

New pytest (the substantive new tests of this slice — `app/sandbox.py` is the thing under test):

- `run_test_suite` with an assertion-only `test_suite` + a `response` that genuinely implements the target → `RunResult(status="ran", passed=True, ...)`, completes well within the wall-clock timeout.
- Same `test_suite` + a `response` that genuinely fails the assertions → `RunResult(status="ran", passed=False, ...)` with the failing output in `.output`.
- A `response` that does not terminate (an infinite loop) → the call returns within a **bounded wall-clock time well under the test-suite-level pytest timeout** (the test asserts wall-clock < some small bound — the run does **not** hang the calling process) with `RunResult(status="timed_out", passed=None, ...)`.
- A `test_suite` that is structurally invalid / does not compile (a syntax error) → `RunResult(status="compile_error", passed=None, ...)` with the `g++` diagnostic in `.output` — surfaced as that, never a fabricated pass/fail.
- A reference-impl-embedding `test_suite` (mimicking ADR-040's current output) + any `response` → `RunResult(status="compile_error", ...)` (the redefinition) — honest, not fabricated. (This pins the splice behavior the new project_issue tracks fixing on the generator side.)
- A `response` that attempts `open("<content/latex/...>", "w")` (or otherwise writes under the corpus root) → after the run, every file under `content/latex/` is byte-for-byte unchanged (MC-6); the `RunResult` reflects whatever the child did in its temp dir (a write *there* is allowed; a write under `content/latex/` must not have happened).
- A Python `test_suite` (`import unittest` / `def test_*`, no `#include`) + a passing `response` → `RunResult(status="ran", passed=True, ...)`; a failing `response` → `passed=False`.
- An unrecognized-language `test_suite` (neither `#include` nor Python markers) → `RunResult(status="setup_error", passed=None, output=<"unrecognized test-suite language">)`.
- A boundary grep: `app/sandbox.py` contains no `import sqlite3`, no SQL literal, no `import openai`/`anthropic`/`litellm`/`langchain*`/`langgraph*`/etc., no `ai_workflows` import; `app/workflows/` is unchanged by this task.

(The take-surface Playwright pre-flag is in ADR-043; the persistence round-trip pytest pre-flag is in ADR-044.)
