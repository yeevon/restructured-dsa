"""
Playwright conftest for TASK-003 — Playwright UI tests.

Provides a session-scoped `live_server` fixture that starts
`uvicorn app.main:app` on a free port for the duration of the test session
and yields the base URL (e.g. "http://127.0.0.1:54321").

ADR-010: The `live_server` fixture starts uvicorn on a free port for the
test session.  pytest-playwright fixtures (page, browser, etc.) are provided
by the pytest-playwright plugin.

Test artifacts (screenshots, traces) are written by pytest-playwright to
the `tests/playwright/artifacts/` directory per ADR-010.
"""

from __future__ import annotations

import socket
import subprocess
import sys
import time
import pathlib

import pytest
import requests


def _find_free_port() -> int:
    """Pick a free TCP port by binding and releasing a socket."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def live_server():
    """
    Start `uvicorn app.main:app` on a free port for the test session.

    Yields the base URL string (e.g. "http://127.0.0.1:54321").

    ADR-010: session-scoped `live_server` fixture starts uvicorn on a free
    port; Playwright tests use `page.goto(live_server + "/path")`.

    The fixture uses `subprocess.Popen` so the FastAPI app runs in a separate
    OS process.  This ensures Playwright drives a real browser against a real
    HTTP server — not an in-process test client.

    CONTENT_ROOT: the fixture inherits the default `app.config.CONTENT_ROOT`
    from the application (which points at `content/latex/`).  The live
    content corpus is what the Playwright tests navigate.  The live server
    must have at least one .tex file in content/latex/ that matches the
    ch-01-cpp-refresher chapter ID for the lecture-page tests to pass.
    """
    port = _find_free_port()
    host = "127.0.0.1"
    base_url = f"http://{host}:{port}"

    repo_root = pathlib.Path(__file__).parent.parent.parent
    # Launch uvicorn as a subprocess so pytest-playwright's browser can hit it
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app",
         "--host", host, "--port", str(port)],
        cwd=str(repo_root),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # Wait for the server to become ready (poll GET / up to 10 seconds)
    deadline = time.monotonic() + 10.0
    last_exc = None
    while time.monotonic() < deadline:
        try:
            r = requests.get(base_url + "/", timeout=0.5)
            if r.status_code < 600:
                break
        except Exception as exc:
            last_exc = exc
        time.sleep(0.15)
    else:
        proc.terminate()
        proc.wait(timeout=5)
        raise RuntimeError(
            f"live_server did not become ready on {base_url} within 10 s. "
            f"Last error: {last_exc!r}"
        )

    yield base_url

    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
