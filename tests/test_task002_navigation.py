"""
Integration and unit tests for TASK-002: Chapter navigation grouped by
Mandatory/Optional designation.

ADR-010 MIGRATION NOTE:
  DOM-content assertions (body text / href substring checks) have been moved to
  tests/playwright/test_task002_navigation_dom.py per ADR-010's migration scope.
  This file retains only:
  - HTTP-protocol shape checks (status code, content-type)
  - Byte-equality determinism check (response equality, no DOM walk)
  - Source-tree static analysis checks (MC-3, MC-6 static grep)
  - Runtime side-effect checks (MC-6 monkeypatch write-detection)

Acceptance criteria tested here:

  AC-index-1 (HTTP)   GET / returns 200 with an HTML response.
  AC-determinism      Two consecutive GET / calls against the same fixture corpus
                      produce identical response bodies (ADR-003).
  AC-bad-name (HTTP)  Bad naming corpus → HTTP response (5xx or 200; status only).
  AC-missing-title (HTTP)  Missing title corpus → HTTP response (status only).
  AC-dup-number (HTTP)     Duplicate number corpus → HTTP 5xx (status only).

  MC-3 (arch) No chapter-number literal (1,2,3,4,5,6 or <7 / <=6) appears in
              any module under app/ other than app/designation.py (ADR-004).
  MC-6 (arch) No path under content/latex/ is opened for write by the
              application code (ADR-001).

pytestmark registers all tests under the task marker so they can be targeted
with:  pytest -m 'task("TASK-002")'
"""

from __future__ import annotations

import importlib
import pathlib
import re

import pytest

pytestmark = pytest.mark.task("TASK-002")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = pathlib.Path(__file__).parent.parent
TESTS_FIXTURES = pathlib.Path(__file__).parent / "fixtures"

FIXTURE_MINIMAL = TESTS_FIXTURES / "latex_minimal"
FIXTURE_UNORDERED = TESTS_FIXTURES / "latex_unordered"
FIXTURE_BAD_NAMING = TESTS_FIXTURES / "latex_bad_naming"
FIXTURE_DUPLICATE = TESTS_FIXTURES / "latex_duplicate_number"
FIXTURE_MISSING_TITLE = TESTS_FIXTURES / "latex_missing_title"


# ---------------------------------------------------------------------------
# Helpers: inject fixture root into the app via app.config.CONTENT_ROOT
# ---------------------------------------------------------------------------

def _make_client_with_root(source_root: pathlib.Path):
    """
    Return a FastAPI TestClient pointing at source_root instead of the live
    content/latex/ directory.
    """
    from fastapi.testclient import TestClient  # noqa: PLC0415
    import app.config as _cfg  # noqa: PLC0415
    from app.main import app  # noqa: PLC0415

    old = _cfg.CONTENT_ROOT
    _cfg.CONTENT_ROOT = str(source_root)
    try:
        client = TestClient(app)
        return client, old, _cfg
    except Exception:
        _cfg.CONTENT_ROOT = old
        raise


# ---------------------------------------------------------------------------
# AC-index-1 — HTTP shape only (DOM content migrated to Playwright)
# ---------------------------------------------------------------------------


def test_ac_index_1_root_returns_200():
    """
    AC: GET / returns HTTP 200.

    ADR-006: 'GET / → returns the landing page. Status 200 unless Chapter
    discovery itself fails.'

    DOM-content assertions (chapter IDs, section labels, hrefs) migrated to
    tests/playwright/test_task002_navigation_dom.py per ADR-010.

    Trace: TASK-002 AC 'a navigation surface is reachable'; ADR-006.
    """
    from fastapi.testclient import TestClient  # noqa: PLC0415
    import app.config as _cfg  # noqa: PLC0415
    from app.main import app  # noqa: PLC0415

    old = _cfg.CONTENT_ROOT
    _cfg.CONTENT_ROOT = str(FIXTURE_MINIMAL)
    try:
        client = TestClient(app)
        response = client.get("/")
    finally:
        _cfg.CONTENT_ROOT = old

    assert response.status_code == 200, (
        f"GET / returned {response.status_code}, expected 200. "
        "ADR-006: GET / must return the landing page."
    )


def test_ac_index_1_root_returns_html():
    """
    AC: GET / returns an HTML response.

    ADR-006 + ADR-003: server-side rendered HTML.

    Trace: TASK-002 AC 'navigation surface is reachable'; ADR-006.
    """
    from fastapi.testclient import TestClient  # noqa: PLC0415
    import app.config as _cfg  # noqa: PLC0415
    from app.main import app  # noqa: PLC0415

    old = _cfg.CONTENT_ROOT
    _cfg.CONTENT_ROOT = str(FIXTURE_MINIMAL)
    try:
        client = TestClient(app)
        response = client.get("/")
    finally:
        _cfg.CONTENT_ROOT = old

    content_type = response.headers.get("content-type", "")
    assert "text/html" in content_type, (
        f"GET / returned content-type {content_type!r}, expected text/html. "
        "ADR-006: landing page is HTML."
    )


# ---------------------------------------------------------------------------
# AC-determinism — Byte-equality of two consecutive GET / responses
# ---------------------------------------------------------------------------


def test_ac_determinism_two_root_calls_identical():
    """
    AC: Two consecutive GET / calls against the same fixture corpus produce
    identical response bodies.

    ADR-003 Determinism: "The pipeline is deterministic for a fixed input file."
    Stays in pytest (byte-equality assertion on two responses; no DOM walk).

    Trace: TASK-002 AC; ADR-003.
    """
    from fastapi.testclient import TestClient  # noqa: PLC0415
    import app.config as _cfg  # noqa: PLC0415
    from app.main import app  # noqa: PLC0415

    old = _cfg.CONTENT_ROOT
    _cfg.CONTENT_ROOT = str(FIXTURE_MINIMAL)
    try:
        client = TestClient(app)
        r1 = client.get("/")
        r2 = client.get("/")
    finally:
        _cfg.CONTENT_ROOT = old

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.text == r2.text, (
        "Two consecutive GET / calls returned different response bodies. "
        "ADR-003: the navigation pipeline must be deterministic."
    )


# ---------------------------------------------------------------------------
# AC-bad-name — HTTP status only (body assertions migrated to Playwright)
# ---------------------------------------------------------------------------


def test_ac_bad_name_http_status():
    """
    AC (HTTP status portion): given a corpus with an invalid filename, GET /
    returns either HTTP 200 (with per-row error) or HTTP 5xx (whole-surface
    failure).  Both are acceptable per the fail-loudly contract.

    Body-content assertions (checking that 'ch01' appears with an error
    indicator) have been migrated to tests/playwright/test_task002_navigation_dom.py
    per ADR-010 migration scope.

    ADR-005; ADR-007.
    Trace: TASK-002 AC 'fails loudly'; ADR-010 migration (status-code stays).
    """
    from fastapi.testclient import TestClient  # noqa: PLC0415
    import app.config as _cfg  # noqa: PLC0415
    from app.main import app  # noqa: PLC0415

    old = _cfg.CONTENT_ROOT
    _cfg.CONTENT_ROOT = str(FIXTURE_BAD_NAMING)
    try:
        client = TestClient(app)
        response = client.get("/")
    finally:
        _cfg.CONTENT_ROOT = old

    # Acceptable: HTTP 5xx (whole-surface failure) or 200 (per-row degradation)
    # NOT acceptable: any 4xx that would suggest the route itself is broken
    assert response.status_code in (200, 500, 503), (
        f"GET / returned {response.status_code} for bad-naming corpus. "
        "Expected 200 (per-row degradation) or 500 (whole-surface failure). "
        "ADR-005: invalid basenames are rejected; ADR-007: surface must fail loudly."
    )


# ---------------------------------------------------------------------------
# AC-missing-title — HTTP status only (body assertions migrated to Playwright)
# ---------------------------------------------------------------------------


def test_ac_missing_title_http_status():
    """
    AC (HTTP status portion): given a Chapter with no \\title{}, GET / returns
    either HTTP 200 (per-row degradation) or HTTP 5xx (whole-surface failure).

    Body-content assertions migrated to Playwright per ADR-010.

    ADR-007.
    Trace: TASK-002 AC; ADR-010 migration (status-code stays).
    """
    from fastapi.testclient import TestClient  # noqa: PLC0415
    import app.config as _cfg  # noqa: PLC0415
    from app.main import app  # noqa: PLC0415

    old = _cfg.CONTENT_ROOT
    _cfg.CONTENT_ROOT = str(FIXTURE_MISSING_TITLE)
    try:
        client = TestClient(app)
        response = client.get("/")
    finally:
        _cfg.CONTENT_ROOT = old

    assert response.status_code in (200, 500, 503), (
        f"GET / returned {response.status_code} for missing-title corpus. "
        "Expected 200 (per-row degradation) or 5xx (whole-surface failure). "
        "ADR-007: the surface must fail loudly for missing titles."
    )


# ---------------------------------------------------------------------------
# AC-dup-number — HTTP 5xx only (body assertions migrated to Playwright)
# ---------------------------------------------------------------------------


def test_ac_dup_number_returns_5xx():
    """
    AC (HTTP status portion): given two files with the same chapter number,
    GET / must return HTTP 5xx (whole-surface failure per ADR-007).

    Body-content assertions migrated to Playwright per ADR-010.

    ADR-007: 'the navigation helper fails loudly for the entire surface.'
    Trace: TASK-002 AC; ADR-010 migration (status-code stays).
    """
    from fastapi.testclient import TestClient  # noqa: PLC0415
    import app.config as _cfg  # noqa: PLC0415
    from app.main import app  # noqa: PLC0415

    old = _cfg.CONTENT_ROOT
    _cfg.CONTENT_ROOT = str(FIXTURE_DUPLICATE)
    try:
        client = TestClient(app)
        response = client.get("/")
    finally:
        _cfg.CONTENT_ROOT = old

    # ADR-007 requires whole-surface failure for duplicate chapter numbers
    assert response.status_code >= 500, (
        f"GET / returned {response.status_code} for duplicate-chapter-number corpus. "
        "ADR-007: duplicate chapter numbers are an unrecoverable ambiguity; "
        "the navigation helper must fail the entire surface (HTTP 5xx)."
    )


# ---------------------------------------------------------------------------
# MC-3 (architecture) — No chapter-number literals outside app/designation.py
# ---------------------------------------------------------------------------


def test_mc3_no_chapter_number_literals_outside_designation():
    """
    MC-3 architecture-portion: no chapter-number literal (1, 2, 3, 4, 5, 6,
    or < 7, <= 6) appears in any module under app/ other than app/designation.py,
    in a Mandatory/Optional context.

    ADR-004: 'The threshold (<=6) is a single source of truth in the application
    code.'
    MC-3 / ADR-004.
    Trace: TASK-002 AC 'MC-3's architecture-portion check passes'; ADR-004; MC-3.
    """
    app_root = REPO_ROOT / "app"
    if not app_root.exists():
        return  # No app package yet — trivially passes.

    designation_file = app_root / "designation.py"

    _THRESHOLD_PATTERNS = [
        re.compile(r"<=\s*6"),
        re.compile(r"<\s*7"),
        re.compile(r">=\s*7"),
        re.compile(r">\s*6"),
        re.compile(r"\brange\s*\(\s*1\s*,\s*7\s*\)"),
        re.compile(r"\brange\s*\(\s*7\s*\)"),
        re.compile(r"\[1,\s*2,\s*3,\s*4,\s*5,\s*6\]"),
        re.compile(r"chapter_number\s*==\s*[1-6]\b"),
        re.compile(r"chapter_number\s*in\s*\(.*[1-6]"),
    ]

    violations: list[str] = []
    for py_file in sorted(app_root.rglob("*.py")):
        if py_file.resolve() == designation_file.resolve():
            continue
        try:
            source = py_file.read_text(encoding="utf-8")
        except OSError:
            continue
        lines = source.splitlines()
        for lineno, line in enumerate(lines, start=1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            for pattern in _THRESHOLD_PATTERNS:
                if pattern.search(line):
                    violations.append(f"{py_file}:{lineno}: {line.strip()}")
                    break

    assert violations == [], (
        f"Found chapter-number threshold literals outside app/designation.py:\n"
        + "\n".join(violations)
        + "\nADR-004 / MC-3: the threshold (<= 6, < 7, etc.) must live ONLY in "
        "app/designation.py's chapter_designation() function."
    )


# ---------------------------------------------------------------------------
# MC-6 (architecture) — No write path to content/latex/ in app source
# ---------------------------------------------------------------------------


def test_mc6_no_write_open_against_content_latex_in_navigation_code():
    """
    MC-6: No application source file introduced by TASK-002 contains an open()
    call that targets content/latex/ in a write mode.

    ADR-001 §3; MC-6.
    Trace: TASK-002 AC; ADR-001 §3; MC-6.
    """
    app_root = REPO_ROOT / "app"
    if not app_root.exists():
        return

    _CONTENT_LATEX = re.compile(r"content[\\/]latex")
    _WRITE_MODES = re.compile(
        r"""['"]\s*(?:w|wb|a|ab|x|xb|w\+|wb\+|a\+|ab\+)\s*['"]"""
    )

    violations: list[str] = []
    for py_file in sorted(app_root.rglob("*.py")):
        try:
            source = py_file.read_text(encoding="utf-8")
        except OSError:
            continue
        lines = source.splitlines()
        for lineno, line in enumerate(lines, start=1):
            if _CONTENT_LATEX.search(line) and _WRITE_MODES.search(line):
                violations.append(f"{py_file}:{lineno}: {line.strip()}")

    assert violations == [], (
        "Found potential write operations against content/latex/ in application source:\n"
        + "\n".join(violations)
        + "\nADR-001 §3 / MC-6: content/latex/ is read-only to the application."
    )


# ---------------------------------------------------------------------------
# MC-6 (runtime) — GET / does not write to content/latex/
# ---------------------------------------------------------------------------


def test_mc6_root_route_does_not_write_to_content_latex(monkeypatch):
    """
    MC-6 runtime check: GET / must not open any path under content/latex/
    for writing.

    ADR-001 §3 / MC-6.
    Trace: TASK-002 AC; ADR-001; ADR-010 (runtime side-effect check stays in pytest).
    """
    import builtins  # noqa: PLC0415

    content_latex_str = str(REPO_ROOT / "content" / "latex")
    write_modes = {"w", "wb", "a", "ab", "x", "xb", "w+", "wb+", "a+", "ab+"}
    write_calls: list[str] = []

    original_builtin_open = builtins.open
    original_path_open = pathlib.Path.open

    def guarded_open(file, mode="r", *args, **kwargs):
        if any(m in str(mode) for m in write_modes):
            if content_latex_str in str(file):
                write_calls.append(f"open({str(file)!r}, {mode!r})")
        return original_builtin_open(file, mode, *args, **kwargs)

    def guarded_path_open(self, mode="r", *args, **kwargs):
        if any(m in str(mode) for m in write_modes):
            if content_latex_str in str(self):
                write_calls.append(f"Path.open({str(self)!r}, {mode!r})")
        return original_path_open(self, mode, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", guarded_open)
    monkeypatch.setattr(pathlib.Path, "open", guarded_path_open)

    from fastapi.testclient import TestClient  # noqa: PLC0415
    import app.config as _cfg  # noqa: PLC0415
    from app.main import app  # noqa: PLC0415

    old = _cfg.CONTENT_ROOT
    _cfg.CONTENT_ROOT = str(FIXTURE_MINIMAL)
    try:
        client = TestClient(app)
        response = client.get("/")
    finally:
        _cfg.CONTENT_ROOT = old

    assert write_calls == [], (
        f"GET / opened content/latex/ for writing: {write_calls}. "
        "ADR-001 §3 / MC-6: the application must never write to content/latex/."
    )
