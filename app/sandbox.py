"""
app/sandbox — In-app code-execution sandbox.

ADR-042: `run_test_suite(test_suite: str, response: str) -> RunResult`

Isolation mechanism: a bare subprocess under POSIX `resource` rlimits +
a `subprocess.run(timeout=...)` wall-clock cap in a throwaway
`tempfile.mkdtemp()` working directory.

The child runs `cwd=` the temp dir (never under content/latex/ or data/).
The temp dir is removed by `shutil.rmtree` in a `finally` block regardless
of outcome.  The corpus path is never passed to the child, never on its
argv, never in its env.

POSIX/Linux-only: `resource.setrlimit` and `os.setsid` are POSIX.  The dev
environment is Linux; this is consistent with the project being a locally-run
personal project (manifest §1, §5).

MC-1: this module lives under app/ but NOT under app/workflows/ (the AI-workflow
path MC-1 names).  It imports only stdlib — no AI SDK, no ai-workflows package.
MC-6: the child's cwd is always a throwaway temp dir — never content/latex/.
MC-7: no user_id anywhere in this module.
MC-10: no sqlite3 import, no SQL literals — this module returns RunResult to
       the route, which persists it via app.persistence.*.
"""

from __future__ import annotations

import os
import resource
import shutil
import signal
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration (tunable like ADR-036's tier-model string — implementer's call)
# ---------------------------------------------------------------------------

# Wall-clock timeout for compilation (g++ can be slow on pathological input).
_T_COMPILE: float = 30.0

# Wall-clock timeout for test execution.
_T_RUN: float = 10.0

# CPU-seconds rlimit for the child (defence-in-depth alongside wall-clock timeout).
_RLIMIT_CPU_SECONDS: int = 10

# Address-space cap: 256 MiB (a memory bomb is killed by the kernel).
_RLIMIT_AS_BYTES: int = 256 * 1024 * 1024

# Process-count cap (a fork bomb hits the limit).
_RLIMIT_NPROC: int = 64

# Written-file-size cap: 16 MiB (a disk bomb is bounded).
_RLIMIT_FSIZE_BYTES: int = 16 * 1024 * 1024

# Output truncation cap: 16 KiB (bound the size persisted to the DB).
_OUTPUT_TRUNCATION_BYTES: int = 16 * 1024


# ---------------------------------------------------------------------------
# Result shape
# ---------------------------------------------------------------------------


@dataclass
class RunResult:
    """
    The structured return type of run_test_suite.

    ADR-042 §The structured result shape:
      status  'ran' | 'timed_out' | 'compile_error' | 'setup_error'
      passed  True if status=='ran' and exit code was 0; False if status=='ran'
              and exit code was non-zero; None otherwise (never fabricated).
      output  combined stdout+stderr of the run, or the compiler diagnostic
              (compile_error), or the failure message (timed_out / setup_error);
              truncated to _OUTPUT_TRUNCATION_BYTES to bound the DB size.

    RunResult is a transient return type — NOT a persistence dataclass.  It
    lives in app.sandbox, not in app.persistence.  The route maps it to the
    four attempt_questions columns via save_attempt_test_result (ADR-044).
    """

    status: str          # 'ran' | 'timed_out' | 'compile_error' | 'setup_error'
    passed: bool | None  # meaningful only when status == 'ran'; None otherwise
    output: str          # combined output / diagnostic / failure message; truncated


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _truncate(text: str, max_bytes: int = _OUTPUT_TRUNCATION_BYTES) -> str:
    """Truncate output to max_bytes (UTF-8 bytes) to bound the DB size."""
    encoded = text.encode("utf-8", errors="replace")
    if len(encoded) <= max_bytes:
        return text
    return encoded[:max_bytes].decode("utf-8", errors="replace") + "\n[output truncated]"


def _preexec_setlimits(for_compiler: bool = False) -> None:
    """
    Called in the child process before exec (POSIX preexec_fn).

    Sets POSIX resource limits and creates a new process session so the
    timeout-kill reaps the whole child process group (not just the leader).

    ADR-042 §The isolation mechanism:
      RLIMIT_CPU   — CPU-seconds cap (defence-in-depth alongside wall-clock timeout)
      RLIMIT_AS    — address-space cap (memory bomb → kernel kill)
      RLIMIT_NPROC — process-count cap (fork bomb → limit);
                     NOT applied during compilation: g++ needs to fork cc1plus
                     internally, so a tight NPROC cap kills the compilation.
                     Applied only for the test-run step.
      RLIMIT_FSIZE — written-file-size cap (disk bomb → bounded)
      RLIMIT_CORE  — no core dumps

    for_compiler=True: skips RLIMIT_NPROC (g++ needs to fork cc1plus).
    for_compiler=False (default, used for the test-run step): all limits applied.
    """
    os.setsid()  # child is its own process group (so kill(-pgid) reaps the group)
    resource.setrlimit(resource.RLIMIT_CPU, (_RLIMIT_CPU_SECONDS, _RLIMIT_CPU_SECONDS))
    resource.setrlimit(resource.RLIMIT_AS, (_RLIMIT_AS_BYTES, _RLIMIT_AS_BYTES))
    if not for_compiler:
        resource.setrlimit(resource.RLIMIT_NPROC, (_RLIMIT_NPROC, _RLIMIT_NPROC))
    resource.setrlimit(resource.RLIMIT_FSIZE, (_RLIMIT_FSIZE_BYTES, _RLIMIT_FSIZE_BYTES))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


def _kill_process_group(proc: subprocess.Popen) -> None:  # type: ignore[type-arg]
    """Kill the process group of a Popen object (POSIX)."""
    try:
        pgid = os.getpgid(proc.pid)
        os.killpg(pgid, 9)  # SIGKILL
    except (ProcessLookupError, OSError):
        pass  # child already gone


def _sniff_language(test_suite: str) -> str:
    """
    Sniff the test_suite string to determine the programming language.

    ADR-042 §The supported languages:
      '#include' → C++ (compiled with g++)
      'import ' / 'def test' / 'unittest' / 'pytest' and no '#include' → Python
      anything else → 'unknown'

    Returns: 'cpp' | 'python' | 'unknown'
    """
    if "#include" in test_suite:
        return "cpp"
    if (
        "import " in test_suite
        or "def test" in test_suite
        or "unittest" in test_suite
        or "pytest" in test_suite
    ):
        return "python"
    return "unknown"


def _run_cpp(test_suite: str, response: str, tmpdir: str) -> RunResult:
    """
    Compile-and-run the C++ splice in tmpdir.

    ADR-042 §The splice: response + '\\n\\n' + test_suite → submission.cpp
    ADR-042 §Compile step: g++ -std=c++17 submission.cpp -o submission
    ADR-042 §Run step: ./submission
    """
    # Check that g++ is available (setup_error if not)
    if shutil.which("g++") is None:
        return RunResult(
            status="setup_error",
            passed=None,
            output="g++ not found on PATH; cannot compile C++ test suite",
        )

    # Write the spliced source
    source = response + "\n\n" + test_suite
    src_path = Path(tmpdir) / "submission.cpp"
    bin_path = Path(tmpdir) / "submission"
    src_path.write_text(source, encoding="utf-8")

    # Compile — use for_compiler=True to skip RLIMIT_NPROC (g++ forks cc1plus)
    try:
        compile_result = subprocess.run(
            ["g++", "-std=c++17", str(src_path), "-o", str(bin_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=tmpdir,
            timeout=_T_COMPILE,
            preexec_fn=lambda: _preexec_setlimits(for_compiler=True),
        )
    except subprocess.TimeoutExpired as exc:
        return RunResult(
            status="compile_error",
            passed=None,
            output=_truncate(
                (exc.output or b"").decode("utf-8", errors="replace")
                + "\n[compilation timed out]"
            ),
        )
    except (OSError, Exception) as exc:
        return RunResult(
            status="setup_error",
            passed=None,
            output=_truncate(f"Failed to invoke g++: {exc}"),
        )

    if compile_result.returncode != 0:
        return RunResult(
            status="compile_error",
            passed=None,
            output=_truncate(
                compile_result.stdout.decode("utf-8", errors="replace")
            ),
        )

    # Run
    return _run_binary([str(bin_path)], tmpdir)


def _run_python(test_suite: str, response: str, tmpdir: str) -> RunResult:
    """
    Run the Python splice (response + test_suite) in tmpdir via python3.

    ADR-042 §The supported languages (Python path):
    The splice is response + '\\n\\n' + test_suite written to test_suite.py,
    then run with `python3 test_suite.py`.  The test suite is expected to be
    self-executing (an `if __name__ == '__main__'` block or similar).
    """
    if shutil.which("python3") is None:
        return RunResult(
            status="setup_error",
            passed=None,
            output="python3 not found on PATH; cannot run Python test suite",
        )

    source = response + "\n\n" + test_suite
    src_path = Path(tmpdir) / "test_suite.py"
    src_path.write_text(source, encoding="utf-8")

    return _run_binary(["python3", str(src_path)], tmpdir)


def _run_binary(cmd: list[str], tmpdir: str) -> RunResult:
    """
    Run a command in tmpdir under rlimits and a wall-clock timeout.

    Returns RunResult with:
      status='ran', passed=True  — exit code 0
      status='ran', passed=False — exit code non-zero (assertion fired, abort, etc.)
      status='timed_out'         — subprocess.TimeoutExpired
    """
    # Minimal env: no inherited PWD/OLDPWD pointing at the corpus
    clean_env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": os.environ.get("HOME", "/tmp"),
        "LANG": os.environ.get("LANG", "C.UTF-8"),
    }

    proc = None
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            cwd=tmpdir,
            env=clean_env,
            preexec_fn=_preexec_setlimits,
        )
        try:
            stdout_bytes, _ = proc.communicate(timeout=_T_RUN)
        except subprocess.TimeoutExpired:
            _kill_process_group(proc)
            proc.communicate()  # drain
            return RunResult(
                status="timed_out",
                passed=None,
                output=_truncate("the test run timed out"),
            )

        output = _truncate(stdout_bytes.decode("utf-8", errors="replace"))
        # A negative return code means the child was killed by a signal (POSIX).
        # Only SIGXCPU (CPU-limit exceeded) and SIGKILL (our timeout handler)
        # indicate that the run was forcibly terminated due to a timeout/resource
        # limit.  All other signal-caused exits (e.g. SIGABRT=-6 from a C++
        # assert() failure, SIGSEGV=-11 from a crash) are legitimate test
        # outcomes and should be reported as status='ran', passed=False.
        _TIMEOUT_SIGNALS = {-signal.SIGXCPU, -signal.SIGKILL}
        if proc.returncode in _TIMEOUT_SIGNALS:
            return RunResult(
                status="timed_out",
                passed=None,
                output=_truncate(output + "\nthe test run timed out (killed by signal)"),
            )
        passed = proc.returncode == 0
        return RunResult(status="ran", passed=passed, output=output)

    except (OSError, Exception) as exc:
        if proc is not None:
            try:
                _kill_process_group(proc)
                proc.communicate()
            except Exception:
                pass
        return RunResult(
            status="setup_error",
            passed=None,
            output=_truncate(f"Failed to run binary: {exc}"),
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def run_test_suite(test_suite: str, response: str) -> RunResult:
    """
    Execute the learner's `response` against the Question's `test_suite` in
    a sandboxed subprocess and return a structured RunResult.

    ADR-042 §Decision:
    1. Creates a fresh throwaway working directory via tempfile.mkdtemp().
       All files produced by the run (source, binary, any learner writes)
       land there.  The directory is removed (shutil.rmtree) in a finally
       block regardless of outcome.
    2. Sniffs the test_suite string to select the runtime:
       - '#include' in test_suite → C++ (compile with g++, run binary)
       - 'import '/'def test'/'unittest'/'pytest' and no '#include' → Python
       - neither → RunResult(status='setup_error', passed=None,
                             output='unrecognized test-suite language')
    3. For C++: writes response + '\\n\\n' + test_suite → submission.cpp,
       compiles with `g++ -std=c++17`, runs the binary.
    4. For Python: writes response + '\\n\\n' + test_suite → test_suite.py,
       runs with `python3 test_suite.py`.
    5. The child runs cwd=tmpdir (never under content/latex/ or data/).
       The corpus path is never passed to the child.  MC-6 preserved.
    6. The child is subject to POSIX rlimits (CPU, address space, process
       count, file size, no core dumps) and a wall-clock timeout.
    7. Returns:
       RunResult(status='ran', passed=True/False, output=...)
         — the run completed (exit 0 → True, non-zero → False)
       RunResult(status='timed_out', passed=None, output=...)
         — the run exceeded the wall-clock timeout
       RunResult(status='compile_error', passed=None, output=...)
         — C++ compilation failed (g++ reported an error)
       RunResult(status='setup_error', passed=None, output=...)
         — unrecognized language, g++/python3 not on PATH, or other setup failure

    MC-1: no LLM SDK, no AI-workflow imports — this is code execution, not AI.
    MC-5 spirit: a failure (timeout/compile_error/setup_error) is reported
      as that status, never as a fabricated passed=True/False.
    MC-6: the child runs in a temp dir; the corpus path is never in the
      child's env or argv; content/latex/ is never written.
    MC-7: no user_id anywhere.
    MC-10: no sqlite3 import, no SQL literals.
    """
    tmpdir = tempfile.mkdtemp()
    try:
        lang = _sniff_language(test_suite)
        if lang == "cpp":
            return _run_cpp(test_suite, response, tmpdir)
        elif lang == "python":
            return _run_python(test_suite, response, tmpdir)
        else:
            return RunResult(
                status="setup_error",
                passed=None,
                output="unrecognized test-suite language",
            )
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
