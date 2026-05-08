"""
Application configuration.

ADR-003: The renderer reads from content/latex/ (ADR-001 source root).
This module exposes CONTENT_ROOT as a configurable path, enabling tests
to inject a synthetic source root without touching the real content/latex/.

For production use, CONTENT_ROOT defaults to the repository's content/latex/
directory derived from this file's location.
"""

from __future__ import annotations

import pathlib

# The lecture source root, per ADR-001.
# Default: content/latex/ relative to the repository root.
# Override this in tests to inject a synthetic directory.
_APP_DIR = pathlib.Path(__file__).parent
_REPO_ROOT = _APP_DIR.parent

CONTENT_ROOT: str = str(_REPO_ROOT / "content" / "latex")
