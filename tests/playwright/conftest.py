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

TASK-018 extension: the live_server now runs uvicorn in a background thread
(not a subprocess) so that `os.environ` mutations made inside test bodies
are immediately visible to the server.  This is required for the TASK-018
preamble-DOM tests, which set NOTES_DB_PATH to a per-test tmp_path DB before
calling page.goto() to bootstrap the schema.

The thread-based server still behaves identically to the subprocess-based one
for existing tests — they neither set nor read NOTES_DB_PATH and continue to
use the default data/notes.db path.

An autouse function-scoped `_restore_notes_db_path` fixture saves the current
NOTES_DB_PATH (or its absence) before each test and restores it afterwards,
so a TASK-018 test cannot leak its tmp_path DB path into subsequent tests.
"""

from __future__ import annotations

import asyncio
import os
import pathlib
import socket
import threading
import time

import pytest
import requests
import uvicorn


def _find_free_port() -> int:
    """Pick a free TCP port by binding and releasing a socket."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]


class _ThreadedUvicorn:
    """
    Runs uvicorn in a background daemon thread so that os.environ mutations
    in the test process are visible to the ASGI app at request-handling time.

    ADR-010: session-scoped; Playwright tests use `page.goto(live_server + "/path")`.
    TASK-018: thread-based (not subprocess-based) so NOTES_DB_PATH env var set in a
    test body is picked up by the server's get_connection() call (which reads
    os.environ at call time, not at server startup time).
    """

    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port
        self._loop: asyncio.AbstractEventLoop | None = None
        self._server: uvicorn.Server | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        # Import app here (not at module level) so NOTES_DB_PATH monkeypatches
        # applied before the server starts are visible.
        from app.main import app  # noqa: PLC0415

        config = uvicorn.Config(
            app=app,
            host=self.host,
            port=self.port,
            loop="asyncio",
            log_level="error",
            access_log=False,
        )
        self._server = uvicorn.Server(config=config)

        # Create a dedicated event loop for this server thread.
        self._loop = asyncio.new_event_loop()

        def _run() -> None:
            asyncio.set_event_loop(self._loop)
            self._loop.run_until_complete(self._server.serve())

        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._server is not None:
            self._server.should_exit = True
        if self._thread is not None:
            self._thread.join(timeout=5)
        if self._loop is not None and not self._loop.is_closed():
            self._loop.call_soon_threadsafe(self._loop.stop)


@pytest.fixture(scope="session")
def live_server():
    """
    Start `uvicorn app.main:app` in a background thread for the test session.

    Yields the base URL string (e.g. "http://127.0.0.1:54321").

    ADR-010: session-scoped `live_server` fixture starts uvicorn on a free
    port; Playwright tests use `page.goto(live_server + "/path")`.

    TASK-018 change: uses a background thread instead of subprocess so that
    os.environ changes in test bodies (e.g. NOTES_DB_PATH = tmp_path/db.db) are
    visible to the server when it handles the subsequent page.goto() call.
    The server's _get_db_path() reads os.environ at call time, so setting
    NOTES_DB_PATH before calling page.goto() bootstraps the correct DB.

    CONTENT_ROOT: the fixture inherits the default `app.config.CONTENT_ROOT`
    from the application (which points at `content/latex/`).  The live
    content corpus is what the Playwright tests navigate.  The live server
    must have at least one .tex file in content/latex/ that matches the
    ch-01-cpp-refresher chapter ID for the lecture-page tests to pass.
    """
    port = _find_free_port()
    host = "127.0.0.1"
    base_url = f"http://{host}:{port}"

    server = _ThreadedUvicorn(host=host, port=port)
    server.start()

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
        server.stop()
        raise RuntimeError(
            f"live_server did not become ready on {base_url} within 10 s. "
            f"Last error: {last_exc!r}"
        )

    yield base_url

    server.stop()


@pytest.fixture(autouse=True)
def _restore_notes_db_path():
    """
    Save and restore NOTES_DB_PATH around each test.

    TASK-018: the preamble-DOM tests set os.environ["NOTES_DB_PATH"] to a
    per-test tmp_path DB.  Without this fixture, that leaked env var would
    remain set for subsequent tests and cause them to hit a now-deleted DB path.

    autouse=True means this fixture runs for every Playwright test without
    any test needing to request it explicitly.
    """
    original = os.environ.get("NOTES_DB_PATH")
    yield
    if original is None:
        os.environ.pop("NOTES_DB_PATH", None)
    else:
        os.environ["NOTES_DB_PATH"] = original
