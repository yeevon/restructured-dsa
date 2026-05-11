"""
Shared fixtures for the test suite.

The application imports are deferred inside the fixtures so that collection
still succeeds even if the app is mid-change (ImportError is raised at
fixture call-time, not at module-import time).

Test database isolation
-----------------------
The app reads ``NOTES_DB_PATH`` at connection time (ADR-022) — both the
in-process ``TestClient`` and the ``live_server`` uvicorn subprocess.  Before
any test runs we point ``NOTES_DB_PATH`` at a throwaway per-session temp file
and delete it at session end, so:

  - the real ``data/notes.db`` is never written to by the test suite, and
  - no test data persists after the run.

This is done in ``pytest_configure`` (runs before collection / before
``app.main`` is imported) rather than a fixture so the subprocess that
``tests/playwright/conftest.py`` spawns inherits it from ``os.environ``.
"""

import os
import pathlib
import tempfile

import pytest

# Holds the per-session TemporaryDirectory and the prior NOTES_DB_PATH (if any)
# so pytest_unconfigure can clean up and restore the environment.
_test_db_dir = None
_prior_notes_db_path = None


def pytest_configure(config):  # noqa: ARG001 — pytest hook signature
    global _test_db_dir, _prior_notes_db_path
    _test_db_dir = tempfile.TemporaryDirectory(prefix="cs300-test-db-")
    _prior_notes_db_path = os.environ.get("NOTES_DB_PATH")
    os.environ["NOTES_DB_PATH"] = str(pathlib.Path(_test_db_dir.name) / "notes.db")


def pytest_unconfigure(config):  # noqa: ARG001 — pytest hook signature
    global _test_db_dir, _prior_notes_db_path
    if _prior_notes_db_path is None:
        os.environ.pop("NOTES_DB_PATH", None)
    else:
        os.environ["NOTES_DB_PATH"] = _prior_notes_db_path
    if _test_db_dir is not None:
        _test_db_dir.cleanup()
        _test_db_dir = None


@pytest.fixture(scope="session")
def lecture_client():
    """
    A FastAPI TestClient for the application.

    ADR-003: FastAPI serves GET /lecture/{chapter_id}.
    Raises ImportError at test-time (failing the test) until implementation exists.
    """
    from fastapi.testclient import TestClient  # must be importable once app exists
    from app.main import app  # noqa: PLC0415 — deferred intentionally

    return TestClient(app)


@pytest.fixture(scope="session")
def ch01_lecture_response(lecture_client):
    """
    Single GET /lecture/ch-01-cpp-refresher response, fetched once per session.
    """
    response = lecture_client.get("/lecture/ch-01-cpp-refresher")
    return response


@pytest.fixture(scope="module")
def repo_root():
    """Absolute path to the repository root (not import-dependent)."""
    import pathlib

    return pathlib.Path(__file__).parent.parent
