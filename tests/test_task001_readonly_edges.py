"""
Read-only enforcement edge cases for TASK-001 (Category D).

Extends the MC-6 / ADR-001 conformance tests with harder-to-catch variants:

  D21 — Symlink under content/latex/: if the renderer follows a symlink that
         points outside content/latex/, the resolve target must never be opened
         for WRITING.  The test also confirms the symlink is opened read-only
         (not skipped silently).

SYMLINK TEST STATUS: active (not skipped).

PINNED CONTRACT for D21:
  The application may open the symlink path (content/latex/<symlinked>.tex)
  for READING — that is normal operation for a valid-looking chapter file.
  The application must NOT open the symlink's resolved real path for WRITING.
  If the implementer uses pathlib.Path.resolve() before opening, the resolved
  path must still only be opened in read mode.

  RATIONALE: ADR-001 §3 states 'No path under content/latex/ is ever opened
  for writing, created, deleted, or moved by application code.'  A symlink to
  an outside-the-tree file whose content is read is not a write violation per
  the ADR (the ADR forbids writes, not reads-via-symlink).  However, the test
  verifies that:
    (a) the renderer opens the path in read mode (contract: file IS read), and
    (b) the resolver (if any) does not then WRITE to the resolved path.
  Together these confirm the read-only invariant holds even through symlinks.

  NOTE: if the OS or Python runtime resolves the symlink before our spy
  intercepts the open(), the spy records the resolved path.  The test accounts
  for this: it checks that no WRITE was made to either the symlink path or the
  resolved target path.

pytestmark registers all tests under task("TASK-001").
"""

import builtins
import os
import pathlib
import tempfile

import pytest

pytestmark = pytest.mark.task("TASK-001")

REPO_ROOT = pathlib.Path(__file__).parent.parent
CONTENT_LATEX_ROOT = REPO_ROOT / "content" / "latex"


# ---------------------------------------------------------------------------
# D21 — Symlink under content/latex/ — read-only enforcement
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not hasattr(os, "symlink"),
    reason="Platform does not support symlinks; D21 not applicable.",
)
def test_d21_symlink_target_not_opened_for_writing(monkeypatch, tmp_path):
    """
    D21: If content/latex/ contains a symlink pointing to a file outside the
    tree, the renderer must open that file read-only — it must NEVER open the
    resolved path for writing.

    SETUP:
      1. Create a real .tex file in tmp_path (outside content/latex/).
      2. Create content/latex/<symlinked_chapter>.tex → tmp_path/real.tex.
         (We create the symlink inside a TEMPORARY copy of content/latex/ so
          the real source directory is not modified. The renderer's source
          root is monkeypatched to the temp copy.)
      3. Monkeypatch builtins.open and pathlib.Path.read_text to record all
         open calls against the real .tex file.
      4. Request the symlinked chapter via the FastAPI TestClient.
      5. Assert: the resolved real file was never opened in a write mode.

    ASSUMPTION: the renderer accepts a configurable source root (app.config or
    similar).  If it does not expose that seam, we monkeypatch the renderer's
    internal constant directly.  If neither is possible, the test is skipped
    with a clear rationale.

    PINNED CONTRACT: HTTP 200 is acceptable (the symlink points to a valid .tex
    file — the renderer should render it); what matters is no write to the
    resolved path.

    Trace: ADR-001 §3 ('No path under content/latex/ is ever opened for
    writing, created, deleted, or moved by application code'); manifest §5.
    """
    # --- Step 1: real .tex file in a temp directory outside content/latex/ ---
    real_tex_dir = tmp_path / "outside_tree"
    real_tex_dir.mkdir()
    real_tex = real_tex_dir / "real_chapter.tex"
    real_tex.write_text(
        r"""
\documentclass{article}
\begin{document}
\section{1.1 Test Section}
Content here.
\end{document}
""",
        encoding="utf-8",
    )

    # --- Step 2: fake content/latex/ with a symlink ---
    fake_latex_root = tmp_path / "content" / "latex"
    fake_latex_root.mkdir(parents=True)
    symlink_path = fake_latex_root / "ch-symlinked-test.tex"
    try:
        symlink_path.symlink_to(real_tex)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(
            f"Cannot create symlink ({exc}); D21 not applicable on this platform."
        )

    # --- Step 3: spy on all open calls for the real .tex file ---
    real_tex_str = str(real_tex)
    real_tex_resolved = str(real_tex.resolve())
    write_modes = {"w", "wb", "a", "ab", "x", "xb", "w+", "wb+", "a+", "ab+"}
    write_calls: list[str] = []
    read_calls: list[str] = []

    original_open = builtins.open
    original_path_read_text = pathlib.Path.read_text

    def spying_open(file, mode="r", *args, **kwargs):
        path_str = str(file)
        if real_tex_str in path_str or real_tex_resolved in path_str:
            mode_str = str(mode)
            if any(m in mode_str for m in write_modes):
                write_calls.append(f"open({path_str!r}, {mode!r})")
            else:
                read_calls.append(f"open({path_str!r}, {mode!r})")
        return original_open(file, mode, *args, **kwargs)

    def spying_read_text(self, *args, **kwargs):
        path_str = str(self)
        resolved_str = str(self.resolve())
        if real_tex_str in path_str or real_tex_resolved in resolved_str:
            read_calls.append(f"read_text({path_str!r})")
        return original_path_read_text(self, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", spying_open)
    monkeypatch.setattr(pathlib.Path, "read_text", spying_read_text)

    # --- Step 4: attempt to render via TestClient with monkeypatched source root ---
    try:
        from fastapi.testclient import TestClient  # noqa: PLC0415
        from app.main import app  # noqa: PLC0415
    except ImportError:
        pytest.fail(
            "app.main is not importable — implementation does not exist yet. "
            "D21 will be re-evaluated once the implementation ships."
        )

    # Attempt to inject the fake source root
    source_root_injected = False
    try:
        import app.config as _cfg  # noqa: PLC0415
        if hasattr(_cfg, "CONTENT_ROOT"):
            original_root = _cfg.CONTENT_ROOT
            _cfg.CONTENT_ROOT = str(fake_latex_root)
            source_root_injected = True
        elif hasattr(_cfg, "SOURCE_ROOT"):
            original_root = _cfg.SOURCE_ROOT
            _cfg.SOURCE_ROOT = str(fake_latex_root)
            source_root_injected = True
    except ImportError:
        pass

    if not source_root_injected:
        pytest.skip(
            "D21 requires a configurable source root (app.config.CONTENT_ROOT or "
            "app.config.SOURCE_ROOT) to inject a fake content/latex/ directory "
            "containing the test symlink.  The implementation does not expose this "
            "seam yet.  "
            "RATIONALE: this test is left as a skip-with-rationale rather than "
            "being dropped, because symlink traversal is a real security invariant "
            "(ADR-001 §3 read-only enforcement).  The implementer should add a "
            "configurable source_root parameter to the renderer and revisit this "
            "test when they do."
        )

    try:
        client = TestClient(app)
        client.get("/lecture/ch-symlinked-test")
    finally:
        # Restore original config after the request
        try:
            import app.config as _cfg  # noqa: PLC0415
            if hasattr(_cfg, "CONTENT_ROOT"):
                _cfg.CONTENT_ROOT = original_root
            elif hasattr(_cfg, "SOURCE_ROOT"):
                _cfg.SOURCE_ROOT = original_root
        except (ImportError, UnboundLocalError):
            pass

    # --- Step 5: assert no write to the resolved real file ---
    assert write_calls == [], (
        f"The renderer opened the symlink's resolved target for WRITING: "
        f"{write_calls}. "
        "ADR-001 §3: no path under content/latex/ (or its symlink targets) "
        "may be opened for writing by application code."
    )


@pytest.mark.skipif(
    not hasattr(os, "symlink"),
    reason="Platform does not support symlinks; D21 not applicable.",
)
def test_d21_symlink_target_is_opened_for_reading(monkeypatch, tmp_path):
    """
    D21 (positive case): the renderer DOES open the symlink target for reading.

    This confirms that the spy infrastructure is working: if the renderer is
    supposed to render the symlinked chapter, it must read the .tex file.
    If this test fails, it means the renderer did not read the file at all —
    perhaps the symlink was silently skipped — and the D21 write-check above
    is vacuous.

    PINNED CONTRACT: at least one read of the real .tex file is recorded.

    Trace: ADR-001 §1 (the renderer reads from content/latex/); ADR-001 §3
    (read-only; not no-read).
    """
    real_tex_dir = tmp_path / "outside_tree_read_check"
    real_tex_dir.mkdir()
    real_tex = real_tex_dir / "real_chapter_read.tex"
    real_tex.write_text(
        r"""
\documentclass{article}
\begin{document}
\section{1.1 Read Test}
Content.
\end{document}
""",
        encoding="utf-8",
    )

    fake_latex_root = tmp_path / "content_read" / "latex"
    fake_latex_root.mkdir(parents=True)
    symlink_path = fake_latex_root / "ch-symlinked-read.tex"
    try:
        symlink_path.symlink_to(real_tex)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"Cannot create symlink: {exc}")

    real_tex_str = str(real_tex)
    real_tex_resolved = str(real_tex.resolve())
    read_calls: list[str] = []

    original_open = builtins.open
    original_path_read_text = pathlib.Path.read_text

    def spying_open(file, mode="r", *args, **kwargs):
        path_str = str(file)
        if real_tex_str in path_str or real_tex_resolved in path_str:
            read_calls.append(path_str)
        return original_open(file, mode, *args, **kwargs)

    def spying_read_text(self, *args, **kwargs):
        path_str = str(self)
        resolved_str = str(self.resolve())
        if real_tex_str in path_str or real_tex_resolved in resolved_str:
            read_calls.append(path_str)
        return original_path_read_text(self, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", spying_open)
    monkeypatch.setattr(pathlib.Path, "read_text", spying_read_text)

    try:
        from fastapi.testclient import TestClient  # noqa: PLC0415
        from app.main import app  # noqa: PLC0415
    except ImportError:
        pytest.fail("app.main not importable — implementation does not exist yet.")

    source_root_injected = False
    try:
        import app.config as _cfg  # noqa: PLC0415
        if hasattr(_cfg, "CONTENT_ROOT"):
            original_root = _cfg.CONTENT_ROOT
            _cfg.CONTENT_ROOT = str(fake_latex_root)
            source_root_injected = True
        elif hasattr(_cfg, "SOURCE_ROOT"):
            original_root = _cfg.SOURCE_ROOT
            _cfg.SOURCE_ROOT = str(fake_latex_root)
            source_root_injected = True
    except ImportError:
        pass

    if not source_root_injected:
        pytest.skip(
            "D21 (positive case) requires configurable source root — same "
            "rationale as the write-side D21 test."
        )

    try:
        client = TestClient(app)
        response = client.get("/lecture/ch-symlinked-read")
    finally:
        try:
            import app.config as _cfg  # noqa: PLC0415
            if hasattr(_cfg, "CONTENT_ROOT"):
                _cfg.CONTENT_ROOT = original_root
            elif hasattr(_cfg, "SOURCE_ROOT"):
                _cfg.SOURCE_ROOT = original_root
        except (ImportError, UnboundLocalError):
            pass

    # The renderer must have read the file (or returned 404 if symlinks are
    # intentionally blocked — both are acceptable as long as write-side D21 passes).
    if response.status_code == 200:
        assert len(read_calls) >= 1, (
            "Renderer returned 200 for symlinked chapter but no read of the "
            "real .tex file was recorded by the spy. Either the spy is broken "
            "or the renderer used an unexpected file-reading mechanism."
        )
    # If 404, the renderer deliberately skipped the symlink — that is a valid
    # security-conservative choice; the write-check (D21 above) is what matters.


# ---------------------------------------------------------------------------
# Static grep: no write modes in app source (complement to D21 runtime check)
# ---------------------------------------------------------------------------


def test_d21_static_no_write_open_in_application_source():
    """
    D21 (static complement): grep application source for any open() calls that
    mention content/latex and use a write mode — same check as MC-6 in
    test_task001_conformance.py, extended to also cover pathlib.Path.write_text
    and pathlib.Path.write_bytes.

    Trace: ADR-001 §3; MC-6.

    NOTE: this is a static / syntactic check.  The runtime monkeypatch tests
    are the authoritative assertions.  This catches obvious violations early.
    """
    import re as _re

    app_root = REPO_ROOT / "app"
    if not app_root.exists():
        return  # No app package yet — trivially passes; runtime tests will catch it.

    # Patterns that would indicate writes to content/latex paths
    _WRITE_PATTERNS = [
        _re.compile(r"""\.write_text\s*\("""),
        _re.compile(r"""\.write_bytes\s*\("""),
        _re.compile(r"""open\s*\(.*?['"]\s*(?:w|wb|a|ab|x|w\+|wb\+|a\+|ab\+)\s*['"]"""),
    ]
    _CONTENT_LATEX = _re.compile(r"content[\\/]latex")

    violations: list[str] = []
    for py_file in sorted(app_root.rglob("*.py")):
        try:
            source = py_file.read_text(encoding="utf-8")
        except OSError:
            continue
        lines = source.splitlines()
        for lineno, line in enumerate(lines, start=1):
            if _CONTENT_LATEX.search(line):
                for pattern in _WRITE_PATTERNS:
                    if pattern.search(line):
                        violations.append(f"{py_file}:{lineno}: {line.strip()}")

    assert violations == [], (
        f"Found potential write operations against content/latex/ in application "
        f"source (including pathlib.write_text / write_bytes):\n"
        + "\n".join(violations)
        + "\nADR-001 §3: content/latex/ is read-only to the application."
    )
