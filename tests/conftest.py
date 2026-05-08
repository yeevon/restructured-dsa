"""
Shared fixtures for TASK-001 tests.

No implementation exists yet; these fixtures will import the application once
the implementer creates it.  The imports themselves are deferred inside the
fixtures so that collection still succeeds (ImportError is raised at fixture
call-time, not at module-import time).
"""

import pytest


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
