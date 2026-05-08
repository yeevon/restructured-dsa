"""
Application configuration.

ADR-003: The renderer reads from content/latex/ (ADR-001 source root).
This module exposes CONTENT_ROOT as a configurable path, enabling tests
to inject a synthetic source root without touching the real content/latex/.

For production use, CONTENT_ROOT defaults to the repository's content/latex/
directory derived from this file's location.

Tests that drive a subprocess-based live server (Playwright fixture servers)
may set the CONTENT_ROOT environment variable to override the default.
"""

from __future__ import annotations

import os
import pathlib

# The lecture source root, per ADR-001.
# Default: content/latex/ relative to the repository root.
# Override this in tests to inject a synthetic directory.
_APP_DIR = pathlib.Path(__file__).parent
_REPO_ROOT = _APP_DIR.parent

_default_content_root: str = str(_REPO_ROOT / "content" / "latex")
CONTENT_ROOT: str = os.environ.get("CONTENT_ROOT", _default_content_root)
