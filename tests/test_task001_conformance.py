"""
Conformance pre-checks for TASK-001 (MC-6 / ADR-001).

These tests assert repository-level constraints that do not require the FastAPI
app to be running.  They can be evaluated against the source tree directly.

pytestmark registers all tests under the task marker.
"""

import pathlib
import re

import pytest

pytestmark = pytest.mark.task("TASK-001")

REPO_ROOT = pathlib.Path(__file__).parent.parent
CONTENT_LATEX_ROOT = REPO_ROOT / "content" / "latex"


# ---------------------------------------------------------------------------
# MC-6 / ADR-001 §3 — Application source must not write to content/latex/
# ---------------------------------------------------------------------------


def _collect_application_python_files() -> list[pathlib.Path]:
    """
    Return all Python files under the application package.

    Before the implementer creates the app package this returns an empty list,
    which means the grep-for-write-modes test trivially passes.  That is
    intentional: we cannot fail on code that does not yet exist.  The
    integration-level AC5 test (test_task001_lecture_page.py) will catch
    write operations at runtime once the implementation exists.
    """
    app_root = REPO_ROOT / "app"
    if not app_root.exists():
        return []
    return list(app_root.rglob("*.py"))


# Regex that matches file-open calls targeting content/latex/ in write mode.
# This is a syntactic (grep-level) check — it catches obvious violations but
# is not a substitute for the monkeypatched runtime check in AC5.
_WRITE_OPEN_PATTERN = re.compile(
    r"""(?:open|\.open)\s*\(.*?['"]\s*(?:w|wb|a|ab|x|w\+|wb\+|a\+|ab\+)\s*['"]"""
)
_CONTENT_LATEX_PATTERN = re.compile(r"""content[\\/]latex""")


def test_mc6_no_write_open_against_content_latex_in_source():
    """
    MC-6 / ADR-001 §3: No application source file contains an open() call that
    (a) targets a path containing 'content/latex' and (b) uses a write mode.

    This is a syntactic pre-check.  The runtime check (AC5 monkeypatch) is the
    authoritative one.  This test catches obvious static violations early.

    Trace: manifest §5 ("no in-app authoring"), §6 ("application does not
    modify the source"); ADR-001 §3; MC-6.
    """
    app_files = _collect_application_python_files()
    violations: list[str] = []

    for py_file in app_files:
        try:
            source = py_file.read_text(encoding="utf-8")
        except OSError:
            continue
        lines = source.splitlines()
        for lineno, line in enumerate(lines, start=1):
            # Look for lines that mention both content/latex and a write-mode open
            if _CONTENT_LATEX_PATTERN.search(line) and _WRITE_OPEN_PATTERN.search(line):
                violations.append(f"{py_file}:{lineno}: {line.strip()}")

    assert violations == [], (
        f"Found potential write operations against content/latex/ in application source:\n"
        + "\n".join(violations)
    )


def test_mc6_content_latex_is_present_and_readable():
    """
    ADR-001 §1: The lecture source root content/latex/ exists and contains
    ch-01-cpp-refresher.tex.

    This is a precondition check: if the source file is absent, nothing can be
    rendered and every other test is meaningless.
    """
    source_file = CONTENT_LATEX_ROOT / "ch-01-cpp-refresher.tex"
    assert CONTENT_LATEX_ROOT.is_dir(), (
        f"content/latex/ directory is missing at {CONTENT_LATEX_ROOT}"
    )
    assert source_file.is_file(), (
        f"Chapter 1 source file is missing at {source_file}"
    )
    # Confirm the file is non-empty
    content = source_file.read_text(encoding="utf-8")
    assert len(content) > 0, "ch-01-cpp-refresher.tex is empty"


def test_mc6_source_contains_document_environment():
    """
    ADR-001 §2: The source file uses \\begin{document} ... \\end{document}.
    The renderer must locate this environment to extract the Lecture body.

    Trace: ADR-001 §2 input contract.
    """
    source_file = CONTENT_LATEX_ROOT / "ch-01-cpp-refresher.tex"
    content = source_file.read_text(encoding="utf-8")
    assert r"\begin{document}" in content, (
        "ch-01-cpp-refresher.tex does not contain \\begin{document}"
    )
    assert r"\end{document}" in content, (
        "ch-01-cpp-refresher.tex does not contain \\end{document}"
    )
    begin_pos = content.index(r"\begin{document}")
    end_pos = content.index(r"\end{document}")
    assert begin_pos < end_pos, (
        "\\begin{document} appears after \\end{document} in the source file"
    )


def test_mc6_section_macros_have_leading_numbers_in_source():
    """
    ADR-002: Every \\section macro in ch-01-cpp-refresher.tex has a leading
    numeric pattern (e.g. '1.1 ', '1.10 ').  This is required for deterministic
    Section ID derivation.

    Trace: ADR-002 "if the source contains \\section macros that lack a leading
    numeric pattern ... the renderer fails loudly."

    ASSUMPTION: All sections in the real source do have leading numbers — which
    was verified by reading the file.  This test would catch a future content
    edit that removes a number.
    """
    source_file = CONTENT_LATEX_ROOT / "ch-01-cpp-refresher.tex"
    content = source_file.read_text(encoding="utf-8")

    # Extract all \section{...} headings from the document body
    body_start = content.find(r"\begin{document}")
    body_end = content.find(r"\end{document}")
    body = content[body_start:body_end]

    section_headings = re.findall(r"\\section\{([^}]+)\}", body)
    assert len(section_headings) > 0, "No \\section macros found in document body"

    # Each heading must start with a numeric pattern like "1.1 " or "1.10 "
    leading_number_re = re.compile(r"^\d+\.\d+")
    unnumbered = [h for h in section_headings if not leading_number_re.match(h)]
    assert unnumbered == [], (
        f"Found \\section headings without a leading numeric pattern: {unnumbered}. "
        "ADR-002 requires all sections to have 'N.M' leading numbers."
    )


def test_mc6_expected_section_count_in_source():
    """
    ADR-002 / AC2: There are exactly 15 \\section macros in the document body
    of ch-01-cpp-refresher.tex (verified by reading the file).

    This test guards against accidental deletion or addition of sections in
    the source file causing the integration test (AC2) to fail for the wrong
    reason.
    """
    source_file = CONTENT_LATEX_ROOT / "ch-01-cpp-refresher.tex"
    content = source_file.read_text(encoding="utf-8")

    body_start = content.find(r"\begin{document}")
    body_end = content.find(r"\end{document}")
    body = content[body_start:body_end]

    section_headings = re.findall(r"\\section\{([^}]+)\}", body)
    assert len(section_headings) == 15, (
        f"Expected 15 \\section macros in ch-01-cpp-refresher.tex body, "
        f"found {len(section_headings)}: {section_headings}"
    )
