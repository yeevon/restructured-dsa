"""
TASK-017: In-app test runner — sandbox primitive tests.

Tests derive from the Acceptance Criteria in
`design_docs/tasks/TASK-017-in-app-test-runner.md` (AC-1 through AC-4)
and from ADR-042 (in-app code-execution sandbox).

Coverage matrix:
  Boundary:
    - test_sandbox_passing_cpp_response_returns_ran_true:
        A response that fully implements the function + an assertion-only
        test suite → RunResult(status='ran', passed=True). The splice is
        response + test_suite in one TU (ADR-042 §The splice).
    - test_sandbox_failing_cpp_response_returns_ran_false:
        Same test suite + a response whose implementation is deliberately
        wrong → RunResult(status='ran', passed=False).
    - test_sandbox_passed_false_has_output:
        When passed=False the .output field carries the failing assertion
        diagnostic (non-empty string).
    - test_sandbox_passed_is_none_when_status_is_not_ran:
        For timed_out / compile_error / setup_error, passed is None (never
        fabricated — ADR-042 §RunResult shape, MC-5's spirit).
    - test_sandbox_status_ran_passed_true_no_corpus_write:
        A passing run does NOT create or modify any file under content/latex/
        (MC-6). Corpus file list + mtimes snapshot before/after.
    - test_sandbox_status_ran_passed_false_no_corpus_write:
        A failing run also leaves content/latex/ byte-for-byte unchanged.
    - test_sandbox_compile_error_has_diagnostic_in_output:
        A test_suite with a deliberate syntax error → status='compile_error'
        (or 'setup_error') and the g++ diagnostic appears in .output.
    - test_sandbox_unrecognized_language_setup_error:
        A test_suite with neither #include nor Python markers → 'setup_error'
        with "unrecognized" in output.
  Edge:
    - test_sandbox_infinite_loop_returns_within_bounded_wall_clock:
        A response containing an infinite loop → status='timed_out' and the
        call returns within 30 s (well under pytest-level timeouts); the
        child does NOT hang the test process.
    - test_sandbox_corpus_write_attempt_blocked:
        A response that tries to open "../../content/latex/evil.tex" for
        writing → content/latex/ is byte-for-byte unchanged after the run.
    - test_sandbox_reference_impl_embedding_gives_compile_error:
        A test_suite that embeds a full reference implementation of the target
        function inline (mimicking ADR-040's current generator output) + a
        response that also defines the same function → 'compile_error' (the
        double-definition is reported honestly, never fabricated as pass/fail).
    - test_sandbox_python_passing_response:
        A Python test_suite (import + def test_*) with a passing response →
        RunResult(status='ran', passed=True).
    - test_sandbox_python_failing_response:
        Same Python test_suite with a response that returns a wrong value →
        RunResult(status='ran', passed=False).
    - test_sandbox_empty_response_with_compile_error:
        An empty response string with a valid assertion-only test suite →
        'compile_error' (the function is declared-but-undefined or missing
        main — reported honestly, not fabricated).
  Negative:
    - test_sandbox_invalid_cpp_syntax_in_test_suite:
        A test_suite string that is pure gibberish (not valid C++ or Python)
        → compile_error or setup_error; never passed=True or passed=False.
    - test_sandbox_passed_none_for_timed_out:
        A timed-out run → passed is None, not True or False.
    - test_sandbox_passed_none_for_compile_error:
        A compile-error run → passed is None, not True or False.
    - test_sandbox_passed_none_for_setup_error:
        An unrecognized-language run → passed is None, not True or False.
    - test_sandbox_module_no_sqlite3_import:
        app/sandbox.py must not import sqlite3 (MC-10 boundary).
    - test_sandbox_module_no_forbidden_sdk_import:
        app/sandbox.py must not import any forbidden LLM/agent SDK (MC-1).
    - test_sandbox_module_not_under_app_workflows:
        The sandbox module lives under app/ but NOT under app/workflows/ (MC-1).
  Performance:
    - test_sandbox_passing_run_completes_within_5s:
        A passing C++ run on a small canned suite completes within 5 s
        (catches runaway compilation or test-execution regressions).

ASSUMPTIONS:
  ASSUMPTION: The sandbox module is importable as `app.sandbox` and exposes
    `run_test_suite(test_suite: str, response: str) -> RunResult` where
    `RunResult` is a dataclass with .status / .passed / .output attributes.
    ADR-042 pins this interface.

  ASSUMPTION: `g++` is available on PATH in the test environment.
    Tests that require C++ compilation use `pytest.mark.skipif(not _HAS_GPP, ...)`
    to emit a meaningful skip rather than a cryptic failure. Tests asserting
    the setup_error path for missing g++ do NOT skip.

  ASSUMPTION: The sandbox's Python path uses `python3` to run Python test suites
    (ADR-042 §Supported languages). Tests that exercise the Python path require
    `python3` on PATH.

  ASSUMPTION: content/latex/ is the lecture source root (ADR-042 §Consequences —
    MC-6). The test derives the path as REPO_ROOT / "content" / "latex".
"""

from __future__ import annotations

import os
import pathlib
import re
import shutil
import stat
import subprocess
import time

import pytest

pytestmark = pytest.mark.task("TASK-017")

REPO_ROOT = pathlib.Path(__file__).parent.parent
CORPUS_ROOT = REPO_ROOT / "content" / "latex"

# ---------------------------------------------------------------------------
# Environment probes (used for conditional skips)
# ---------------------------------------------------------------------------

_HAS_GPP = shutil.which("g++") is not None
_HAS_PYTHON3 = shutil.which("python3") is not None


# ---------------------------------------------------------------------------
# Canned test suites and responses (hand-written, assertion-only — ADR-042 §Test-writer pre-flag)
# ---------------------------------------------------------------------------

# A minimal assertion-only C++ test suite that calls add(int,int).
_CPP_TEST_SUITE_ADD = """\
#include <cassert>
int add(int a, int b);
int main() {
    assert(add(2, 3) == 5);
    assert(add(0, 0) == 0);
    assert(add(-1, 1) == 0);
    return 0;
}
"""

# A correct response for the add function.
_CPP_RESPONSE_ADD_CORRECT = """\
int add(int a, int b) {
    return a + b;
}
"""

# A wrong response (always returns 0).
_CPP_RESPONSE_ADD_WRONG = """\
int add(int a, int b) {
    return 0;
}
"""

# An infinite-loop response (the add function body never terminates).
_CPP_RESPONSE_INFINITE_LOOP = """\
int add(int a, int b) {
    while (true) {}
    return 0;
}
"""

# A test suite with deliberate C++ syntax error.
_CPP_TEST_SUITE_SYNTAX_ERROR = """\
#include <cassert>
int add(int a, int b);
int main() {
    assert(add(2, 3) == 5)  // MISSING SEMICOLON — syntax error
    return 0;
}
"""

# A test suite that embeds a full reference implementation (mimics ADR-040's
# current generator output — the double-definition splice).
_CPP_TEST_SUITE_WITH_REFERENCE_IMPL = """\
#include <cassert>
// Reference implementation (the LLM generated this inline):
int add(int a, int b) {
    return a + b;
}
int main() {
    assert(add(2, 3) == 5);
    return 0;
}
"""

# A test suite in a completely unrecognized language (no #include, no Python markers).
_GIBBERISH_TEST_SUITE = """\
FUNCTION add(a, b) := a + b
ASSERT add(2, 3) = 5
"""

# A Python assertion-only test suite (no #include).
_PYTHON_TEST_SUITE_ADD = """\
def test_add_positive():
    assert add(2, 3) == 5

def test_add_zero():
    assert add(0, 0) == 0

if __name__ == '__main__':
    test_add_positive()
    test_add_zero()
    print('all passed')
"""

# A correct Python response for the add function.
_PYTHON_RESPONSE_ADD_CORRECT = """\
def add(a, b):
    return a + b
"""

# A wrong Python response.
_PYTHON_RESPONSE_ADD_WRONG = """\
def add(a, b):
    return 0
"""

# A response that tries to write to the corpus root (path traversal attempt).
# When spliced with the C++ test suite, it will try to open the file but the
# cwd is a temp dir so the write target will be under the temp dir (not corpus).
# We also include a version that uses an absolute path derived at compile time —
# but since the path is only known at runtime, we use an env variable injection.
_CPP_RESPONSE_CORPUS_WRITE_ATTEMPT = """\
#include <cstdio>
int add(int a, int b) {
    // Attempt to write under ../../content/latex/ — should land in temp dir cwd
    // not in the real corpus root.
    FILE* f = fopen("../../content/latex/injected_evil.tex", "w");
    if (f) {
        fputs("evil content", f);
        fclose(f);
    }
    return a + b;
}
"""


# ---------------------------------------------------------------------------
# Snapshot helpers
# ---------------------------------------------------------------------------


def _snapshot_corpus(corpus: pathlib.Path) -> dict[str, tuple[float, int]]:
    """Return a {rel_path: (mtime, size)} snapshot of the corpus directory."""
    if not corpus.exists():
        return {}
    result: dict[str, tuple[float, int]] = {}
    for p in corpus.rglob("*"):
        if p.is_file():
            st = p.stat()
            result[str(p.relative_to(corpus))] = (st.st_mtime, st.st_size)
    return result


# ---------------------------------------------------------------------------
# AC-1: Passing code → RunResult(status='ran', passed=True)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _HAS_GPP, reason="g++ not found — C++ sandbox path requires g++")
def test_sandbox_passing_cpp_response_returns_ran_true() -> None:
    """
    AC-1 (TASK-017) / ADR-042: run_test_suite(test_suite, response) with a response
    that genuinely passes the assertion-only C++ test suite must return
    RunResult(status='ran', passed=True) and a non-None output string.

    The splice is response + '\\n\\n' + test_suite in one translation unit (ADR-042
    §The splice). A correct implementation of add(int,int) must pass the cassert suite.
    """
    # AC: sandbox returns status='ran', passed=True for a passing response
    from app.sandbox import run_test_suite  # noqa: PLC0415

    result = run_test_suite(_CPP_TEST_SUITE_ADD, _CPP_RESPONSE_ADD_CORRECT)

    assert result.status == "ran", (
        f"run_test_suite with a correct response returned status={result.status!r}; "
        "ADR-042: a passing run must return status='ran'."
    )
    assert result.passed is True, (
        f"run_test_suite with a correct response returned passed={result.passed!r}; "
        "ADR-042: a passing run must return passed=True."
    )
    assert isinstance(result.output, str), (
        f"run_test_suite returned output={result.output!r}; expected a str. "
        "ADR-042: .output is always a string."
    )


@pytest.mark.skipif(not _HAS_GPP, reason="g++ not found — C++ sandbox path requires g++")
def test_sandbox_failing_cpp_response_returns_ran_false() -> None:
    """
    AC-1 (TASK-017) / ADR-042: run_test_suite with a response that fails the
    assertion-only test suite must return RunResult(status='ran', passed=False).

    The 'wrong' implementation always returns 0; the cassert suite asserts
    add(2,3)==5, which will fire and abort the child (non-zero exit).
    """
    # AC: sandbox returns status='ran', passed=False for a failing response
    from app.sandbox import run_test_suite  # noqa: PLC0415

    result = run_test_suite(_CPP_TEST_SUITE_ADD, _CPP_RESPONSE_ADD_WRONG)

    assert result.status == "ran", (
        f"run_test_suite with a failing response returned status={result.status!r}; "
        "ADR-042: a run that reaches assertion failure is still status='ran'."
    )
    assert result.passed is False, (
        f"run_test_suite with a failing response returned passed={result.passed!r}; "
        "ADR-042: a run where an assertion fires must return passed=False."
    )


@pytest.mark.skipif(not _HAS_GPP, reason="g++ not found — C++ sandbox path requires g++")
def test_sandbox_passed_false_has_output() -> None:
    """
    AC-1 (TASK-017) / ADR-042: when passed=False the .output field must be a
    non-empty string carrying the failing assertion diagnostic.
    """
    # AC: failing run carries meaningful output (not an empty string)
    from app.sandbox import run_test_suite  # noqa: PLC0415

    result = run_test_suite(_CPP_TEST_SUITE_ADD, _CPP_RESPONSE_ADD_WRONG)

    assert result.output, (
        "run_test_suite with a failing response returned empty .output; "
        "ADR-042: .output must carry the failing diagnostic so the learner knows what failed."
    )


# ---------------------------------------------------------------------------
# AC-1 (continued): neither passing nor failing run writes under content/latex/
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _HAS_GPP, reason="g++ not found — C++ sandbox path requires g++")
def test_sandbox_status_ran_passed_true_no_corpus_write() -> None:
    """
    AC-1 / AC-4 (TASK-017) / ADR-042 / MC-6: a passing run must not create or
    modify any file under content/latex/. The corpus snapshot before and after
    the run must be identical.
    """
    # AC: passing run leaves content/latex/ byte-for-byte unchanged (MC-6)
    from app.sandbox import run_test_suite  # noqa: PLC0415

    before = _snapshot_corpus(CORPUS_ROOT)
    run_test_suite(_CPP_TEST_SUITE_ADD, _CPP_RESPONSE_ADD_CORRECT)
    after = _snapshot_corpus(CORPUS_ROOT)

    assert before == after, (
        "content/latex/ snapshot changed after a passing sandbox run. "
        "MC-6 / ADR-042: the sandbox must never write under the lecture source root."
    )


@pytest.mark.skipif(not _HAS_GPP, reason="g++ not found — C++ sandbox path requires g++")
def test_sandbox_status_ran_passed_false_no_corpus_write() -> None:
    """
    AC-1 / AC-4 (TASK-017) / ADR-042 / MC-6: a failing run must also leave
    content/latex/ byte-for-byte unchanged.
    """
    # AC: failing run leaves content/latex/ byte-for-byte unchanged (MC-6)
    from app.sandbox import run_test_suite  # noqa: PLC0415

    before = _snapshot_corpus(CORPUS_ROOT)
    run_test_suite(_CPP_TEST_SUITE_ADD, _CPP_RESPONSE_ADD_WRONG)
    after = _snapshot_corpus(CORPUS_ROOT)

    assert before == after, (
        "content/latex/ snapshot changed after a failing sandbox run. "
        "MC-6 / ADR-042: even a failed test run must not write under the lecture source root."
    )


# ---------------------------------------------------------------------------
# AC-2: Infinite-loop / over-limit response → timed_out, within bounded time
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _HAS_GPP, reason="g++ not found — C++ sandbox path requires g++")
def test_sandbox_infinite_loop_returns_within_bounded_wall_clock() -> None:
    """
    AC-2 (TASK-017) / ADR-042: a response that contains an infinite loop must
    cause run_test_suite to return within a bounded wall-clock window (≤ 30 s)
    with status='timed_out' and passed=None — the call must NOT hang.

    The 30 s bound is generous (well under any pytest-session timeout) and
    well above the implementer's actual T_RUN (a few seconds per ADR-042).
    """
    # AC: sandbox returns status='timed_out' within a bounded wall-clock window for a
    #     non-terminating response
    from app.sandbox import run_test_suite  # noqa: PLC0415

    t0 = time.monotonic()
    result = run_test_suite(_CPP_TEST_SUITE_ADD, _CPP_RESPONSE_INFINITE_LOOP)
    elapsed = time.monotonic() - t0

    assert elapsed <= 30.0, (
        f"run_test_suite took {elapsed:.1f}s for an infinite-loop response; "
        "ADR-042: the call must return within a bounded wall-clock window (≤ 30 s). "
        "The child process was not killed — the sandbox timeout is not working."
    )
    assert result.status == "timed_out", (
        f"run_test_suite returned status={result.status!r} for an infinite-loop response; "
        "ADR-042: a non-terminating child must produce status='timed_out'."
    )
    assert result.passed is None, (
        f"run_test_suite returned passed={result.passed!r} for a timed-out run; "
        "ADR-042 / MC-5: passed must be None when status != 'ran' (never fabricated)."
    )


# ---------------------------------------------------------------------------
# AC-3: Compile error / setup error → honest status, not fabricated
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _HAS_GPP, reason="g++ not found — C++ sandbox path requires g++")
def test_sandbox_compile_error_has_diagnostic_in_output() -> None:
    """
    AC-3 (TASK-017) / ADR-042: a test_suite with a C++ syntax error must produce
    status='compile_error' (not a fabricated pass/fail) and the g++ diagnostic
    in .output so the learner can diagnose the issue.
    """
    # AC: sandbox returns status='compile_error' with diagnostic for an invalid test_suite
    from app.sandbox import run_test_suite  # noqa: PLC0415

    result = run_test_suite(_CPP_TEST_SUITE_SYNTAX_ERROR, _CPP_RESPONSE_ADD_CORRECT)

    assert result.status in ("compile_error", "setup_error"), (
        f"run_test_suite with an invalid test_suite returned status={result.status!r}; "
        "ADR-042: a test suite that fails to compile must return 'compile_error' or 'setup_error'."
    )
    assert result.passed is None, (
        f"run_test_suite with a compile error returned passed={result.passed!r}; "
        "ADR-042 / MC-5: passed must be None when the run did not complete (never fabricated)."
    )
    assert result.output, (
        "run_test_suite with a compile error returned empty .output; "
        "ADR-042: the compiler diagnostic must be in .output so the learner can see it."
    )


def test_sandbox_unrecognized_language_setup_error() -> None:
    """
    AC-3 (TASK-017) / ADR-042: a test_suite in an unrecognized language
    (no #include, no Python markers) must return status='setup_error' and
    'unrecognized' in .output. No g++ required — the sniff happens before compilation.
    """
    # AC: sandbox returns status='setup_error' for an unrecognized-language test_suite
    from app.sandbox import run_test_suite  # noqa: PLC0415

    result = run_test_suite(_GIBBERISH_TEST_SUITE, "// some response")

    assert result.status == "setup_error", (
        f"run_test_suite with an unrecognized-language test_suite returned "
        f"status={result.status!r}; ADR-042: unrecognized language → 'setup_error'."
    )
    assert result.passed is None, (
        f"run_test_suite for an unrecognized language returned passed={result.passed!r}; "
        "ADR-042 / MC-5: passed must be None when status != 'ran'."
    )
    output_lower = (result.output or "").lower()
    assert "unrecognized" in output_lower or "language" in output_lower or "unknown" in output_lower, (
        f"run_test_suite setup_error .output={result.output!r} does not mention "
        "'unrecognized' or 'language'; ADR-042: the output should tell the learner why the run failed."
    )


# ---------------------------------------------------------------------------
# AC-4: Corpus-write attempt → content/latex/ unchanged
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _HAS_GPP, reason="g++ not found — C++ sandbox path requires g++")
def test_sandbox_corpus_write_attempt_blocked() -> None:
    """
    AC-4 (TASK-017) / ADR-042 / MC-6: a response that attempts to write a file
    using a relative path traversal to ../../content/latex/ must NOT result in
    any file under content/latex/ being created or modified.

    The child runs cwd=temp_dir, so '../../content/latex/' resolves relative
    to the temp dir — not to REPO_ROOT. The corpus snapshot must be unchanged.
    """
    # AC: response attempting corpus write leaves content/latex/ byte-for-byte unchanged
    from app.sandbox import run_test_suite  # noqa: PLC0415

    before = _snapshot_corpus(CORPUS_ROOT)
    run_test_suite(_CPP_TEST_SUITE_ADD, _CPP_RESPONSE_CORPUS_WRITE_ATTEMPT)
    after = _snapshot_corpus(CORPUS_ROOT)

    assert before == after, (
        "content/latex/ snapshot changed after a sandbox run where the response "
        "attempted to write ../../content/latex/. MC-6 / ADR-042: the sandbox must "
        "run the child in a temp cwd so path-traversal writes never reach the corpus."
    )


# ---------------------------------------------------------------------------
# Edge: reference-impl-embedding test suite → compile_error (honest, not fabricated)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _HAS_GPP, reason="g++ not found — C++ sandbox path requires g++")
def test_sandbox_reference_impl_embedding_gives_compile_error() -> None:
    """
    AC-3 / Edge (TASK-017) / ADR-042 §The splice: a test_suite that embeds a full
    reference implementation of the target function inline (mimicking ADR-040's
    current generator output) combined with a response that also defines the same
    function must produce status='compile_error' (the double-definition is surfaced
    honestly — never fabricated as pass/fail).

    This pins the splice behavior: response + '\\n\\n' + test_suite → two
    definitions of add() → redefinition error. The new project_issue
    question-gen-prompt-emit-assertion-only-test-suites.md tracks fixing the
    generator side.
    """
    # AC: reference-impl-embedding test_suite + any response → compile_error (honest)
    from app.sandbox import run_test_suite  # noqa: PLC0415

    result = run_test_suite(
        _CPP_TEST_SUITE_WITH_REFERENCE_IMPL,
        _CPP_RESPONSE_ADD_CORRECT,
    )

    assert result.status in ("compile_error", "setup_error"), (
        f"run_test_suite with a reference-impl-embedding test_suite + correct response "
        f"returned status={result.status!r}; ADR-042 §The splice: the double-definition "
        "must produce 'compile_error', not a fabricated pass/fail."
    )
    assert result.passed is None, (
        f"run_test_suite returned passed={result.passed!r} for a double-definition compile "
        "error; MC-5: passed must be None when the run did not complete."
    )


# ---------------------------------------------------------------------------
# Edge: Python test suite paths
# ---------------------------------------------------------------------------


def test_sandbox_python_passing_response() -> None:
    """
    AC-1 / Edge (TASK-017) / ADR-042 §Supported languages: a Python test_suite
    (contains 'def test_' + self-executing __main__, no #include) with a correct
    Python response → RunResult(status='ran', passed=True).
    """
    # AC: Python test_suite with passing response → status='ran', passed=True
    from app.sandbox import run_test_suite  # noqa: PLC0415

    result = run_test_suite(_PYTHON_TEST_SUITE_ADD, _PYTHON_RESPONSE_ADD_CORRECT)

    assert result.status == "ran", (
        f"run_test_suite (Python path) with correct response returned status={result.status!r}; "
        "ADR-042: a Python test run that completes and all assertions pass → status='ran'."
    )
    assert result.passed is True, (
        f"run_test_suite (Python path) with correct response returned passed={result.passed!r}; "
        "ADR-042: a Python test run where all assertions pass → passed=True."
    )


def test_sandbox_python_failing_response() -> None:
    """
    AC-1 / Edge (TASK-017) / ADR-042 §Supported languages: a Python test_suite with
    a wrong response → RunResult(status='ran', passed=False).
    """
    # AC: Python test_suite with failing response → status='ran', passed=False
    from app.sandbox import run_test_suite  # noqa: PLC0415

    result = run_test_suite(_PYTHON_TEST_SUITE_ADD, _PYTHON_RESPONSE_ADD_WRONG)

    assert result.status == "ran", (
        f"run_test_suite (Python path) with wrong response returned status={result.status!r}; "
        "ADR-042: a Python test run where an assertion fails is still status='ran'."
    )
    assert result.passed is False, (
        f"run_test_suite (Python path) with wrong response returned passed={result.passed!r}; "
        "ADR-042: a Python test run where an assertion fires → passed=False."
    )


@pytest.mark.skipif(not _HAS_GPP, reason="g++ not found — C++ sandbox path requires g++")
def test_sandbox_empty_response_with_compile_error() -> None:
    """
    Edge (TASK-017) / ADR-042: an empty response string with a valid assertion-only
    C++ test suite (which forward-declares the function) → compile_error because
    the linker cannot find the definition. Surfaced honestly.
    """
    # AC: empty response + valid assertion-only test suite → compile_error (undeclared/undefined)
    from app.sandbox import run_test_suite  # noqa: PLC0415

    result = run_test_suite(_CPP_TEST_SUITE_ADD, "")

    # An empty response means the declaration is in the test suite (forward-declared)
    # but never defined — the linker should produce a link error (which g++ reports
    # as a compile/link error). This is an honest compile_error, never a fabricated pass.
    assert result.status in ("compile_error", "setup_error"), (
        f"run_test_suite with empty response returned status={result.status!r}; "
        "ADR-042: an empty response + forward-declared-only function must produce "
        "'compile_error' (undefined reference), not a fabricated pass/fail."
    )
    assert result.passed is None, (
        f"run_test_suite with empty response returned passed={result.passed!r}; "
        "MC-5: passed must be None when the run did not complete."
    )


# ---------------------------------------------------------------------------
# Negative: invalid inputs, passed invariant
# ---------------------------------------------------------------------------


def test_sandbox_invalid_cpp_syntax_in_test_suite() -> None:
    """
    Negative (TASK-017) / ADR-042: a test_suite string that is pure gibberish (not
    valid C++ or Python) → compile_error or setup_error; passed is never True or False.
    """
    # AC: gibberish test_suite → never passed=True or passed=False (MC-5 spirit)
    from app.sandbox import run_test_suite  # noqa: PLC0415

    # A string containing '#include' (so it's sniffed as C++) but completely invalid C++
    gibberish_cpp = "#include <cassert>\n@@@ this is not valid C++ at all @@@\n"
    result = run_test_suite(gibberish_cpp, "int add(int a, int b) { return a+b; }")

    assert result.status in ("compile_error", "setup_error"), (
        f"run_test_suite with gibberish #include content returned status={result.status!r}; "
        "ADR-042: invalid C++ test_suite must produce 'compile_error' or 'setup_error'."
    )
    assert result.passed is None, (
        f"run_test_suite returned passed={result.passed!r} for a gibberish test_suite; "
        "ADR-042 / MC-5: passed must be None when status != 'ran'."
    )


def test_sandbox_passed_none_for_timed_out() -> None:
    """
    Negative (TASK-017) / ADR-042: for a timed-out run, passed is always None.
    (g++ required to compile the infinite-loop response; skip if absent.)
    """
    # AC: passed is None for status='timed_out' (MC-5 spirit — never fabricated)
    pytest.importorskip("app.sandbox")
    if not _HAS_GPP:
        pytest.skip("g++ not available — C++ compilation required for this test")

    from app.sandbox import run_test_suite  # noqa: PLC0415

    result = run_test_suite(_CPP_TEST_SUITE_ADD, _CPP_RESPONSE_INFINITE_LOOP)
    if result.status == "timed_out":
        assert result.passed is None, (
            f"run_test_suite returned passed={result.passed!r} for status='timed_out'; "
            "ADR-042 / MC-5: passed is None when status != 'ran' — never fabricated."
        )


def test_sandbox_passed_none_for_compile_error() -> None:
    """
    Negative (TASK-017) / ADR-042: for a compile-error run, passed is always None.
    g++ required to reach the compile step.
    """
    # AC: passed is None for status='compile_error' (MC-5 spirit — never fabricated)
    if not _HAS_GPP:
        pytest.skip("g++ not available")

    from app.sandbox import run_test_suite  # noqa: PLC0415

    result = run_test_suite(_CPP_TEST_SUITE_SYNTAX_ERROR, _CPP_RESPONSE_ADD_CORRECT)
    assert result.status in ("compile_error", "setup_error")
    assert result.passed is None, (
        f"run_test_suite returned passed={result.passed!r} for a compile error; "
        "ADR-042 / MC-5: passed must be None when status != 'ran'."
    )


def test_sandbox_passed_none_for_setup_error() -> None:
    """
    Negative (TASK-017) / ADR-042: for a setup_error (unrecognized language) run,
    passed is always None. No g++ required.
    """
    # AC: passed is None for status='setup_error' (MC-5 spirit — never fabricated)
    from app.sandbox import run_test_suite  # noqa: PLC0415

    result = run_test_suite(_GIBBERISH_TEST_SUITE, "some response")
    assert result.status == "setup_error"
    assert result.passed is None, (
        f"run_test_suite returned passed={result.passed!r} for a setup_error; "
        "ADR-042 / MC-5: passed must be None when status != 'ran'."
    )


# ---------------------------------------------------------------------------
# Negative: MC-1 / MC-10 boundary greps on app/sandbox.py
# ---------------------------------------------------------------------------

_FORBIDDEN_SDKS = [
    "openai",
    "anthropic",
    "google.generativeai",
    "google.genai",
    "cohere",
    "mistralai",
    "groq",
    "together",
    "replicate",
    "litellm",
    "langchain",
    "langgraph",
    "ai_workflows",
]


def test_sandbox_module_no_sqlite3_import() -> None:
    """
    Negative / MC-10 (TASK-017) / ADR-042: app/sandbox.py must not import sqlite3.
    SQL and DB connections belong only under app/persistence/ (MC-10 / ADR-022).
    """
    # AC: app/sandbox.py has no import sqlite3 (MC-10 boundary)
    sandbox_path = REPO_ROOT / "app" / "sandbox.py"
    if not sandbox_path.exists():
        pytest.fail(
            "app/sandbox.py does not exist — TASK-017 implementation is missing. "
            "ADR-042: the sandbox module must be created at app/sandbox.py."
        )
    source = sandbox_path.read_text(encoding="utf-8")
    assert "import sqlite3" not in source, (
        "app/sandbox.py contains 'import sqlite3'; MC-10: SQL/DB access belongs only "
        "under app/persistence/. The sandbox module must not touch the DB."
    )


def test_sandbox_module_no_forbidden_sdk_import() -> None:
    """
    Negative / MC-1 (TASK-017) / ADR-042 / ADR-036: app/sandbox.py must not import
    any forbidden LLM/agent SDK. Running test code is not AI work.
    """
    # AC: app/sandbox.py imports no forbidden LLM/agent SDK (MC-1)
    sandbox_path = REPO_ROOT / "app" / "sandbox.py"
    if not sandbox_path.exists():
        pytest.fail("app/sandbox.py does not exist — TASK-017 implementation is missing.")
    source = sandbox_path.read_text(encoding="utf-8")
    for sdk in _FORBIDDEN_SDKS:
        assert sdk not in source, (
            f"app/sandbox.py contains forbidden SDK reference '{sdk}'; "
            "MC-1 / ADR-036: no LLM/agent SDK may be imported in app/ code. "
            "Running tests is not AI work and requires no AI SDK."
        )


def test_sandbox_module_not_under_app_workflows() -> None:
    """
    Negative / MC-1 (TASK-017) / ADR-042: the sandbox module must live under app/ but
    NOT under app/workflows/ (which is the AI-workflow path MC-1 guards).
    """
    # AC: app/sandbox.py exists at app/sandbox.py (not app/workflows/sandbox.py)
    sandbox_under_workflows = REPO_ROOT / "app" / "workflows" / "sandbox.py"
    assert not sandbox_under_workflows.exists(), (
        "app/workflows/sandbox.py exists; ADR-042 / MC-1: the sandbox module must live "
        "under app/ but NOT under app/workflows/ (the AI-workflow path). "
        "Correct location: app/sandbox.py."
    )
    sandbox_correct = REPO_ROOT / "app" / "sandbox.py"
    assert sandbox_correct.exists(), (
        "app/sandbox.py does not exist; ADR-042: the sandbox module must be created at "
        "app/sandbox.py (not under app/workflows/)."
    )


# ---------------------------------------------------------------------------
# Performance: passing run completes within 5 s
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _HAS_GPP, reason="g++ not found — C++ sandbox path requires g++")
def test_sandbox_passing_run_completes_within_5s() -> None:
    """
    Performance (TASK-017) / ADR-042: a passing C++ run on a small canned suite
    must complete within 5 s. Catches runaway compilation or test-execution
    regressions (O(n²) compile steps, etc.).

    5 s is generous for a tiny C++ compile + assert — normal expectation is < 1 s.
    """
    # Performance: passing run completes within 5 s (catches runaway compile regressions)
    from app.sandbox import run_test_suite  # noqa: PLC0415

    t0 = time.monotonic()
    result = run_test_suite(_CPP_TEST_SUITE_ADD, _CPP_RESPONSE_ADD_CORRECT)
    elapsed = time.monotonic() - t0

    assert elapsed <= 5.0, (
        f"run_test_suite took {elapsed:.2f}s for a small C++ suite; expected ≤ 5 s. "
        "ADR-042: compilation + execution of a tiny assertion suite should be fast."
    )
    assert result.status == "ran", (
        f"run_test_suite returned status={result.status!r} in the performance test; "
        "expected 'ran'. The test must actually run (not timeout or error) to be meaningful."
    )
