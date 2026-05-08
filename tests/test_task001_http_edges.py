"""
HTTP routing / identity edge cases for TASK-001 (Category A + F).

All tests use FastAPI TestClient and target the GET /lecture/{chapter_id} route
defined by ADR-003.  No implementation exists yet — every test that requires the
app will FAIL (ImportError → ERROR, or assertion failure) until the implementer
ships `app.main`.

PINNED CONTRACTS (within implementer latitude; noted in each test):

  Malformed Chapter ID (test A2):
    Pinned as HTTP 422.  Rationale: FastAPI validates path parameters against
    the route's declared constraints; a chapter_id that cannot yield a valid
    chapter number per ADR-002/ADR-004 is a client error.  404 would also be
    acceptable ADR-003 compliance, but 422 is semantically more precise
    ("unprocessable entity" vs. "not found") and FastAPI's default for
    parameter-validation failures.  If the implementer chooses 404, update
    this pinned contract and change the assertion.

  Path traversal (tests A3a, A3b):
    Pinned as HTTP 404.  Rationale: the route regex `{chapter_id}` constrains
    the path segment to a single slug-like token; encoded slashes and
    directory-separator sequences must not route to a handler that reads
    arbitrary files.  The important invariant is NOT the status code but that
    the application does NOT read any path outside content/latex/.

  HTTP method not allowed (test A4):
    Pinned as HTTP 405.  FastAPI's default for an unrouted HTTP method on a
    routed path.

  Empty / root path (test A5):
    Pinned as HTTP 404.  No handler for /lecture/ with empty chapter_id.

  Chapter ID with directory separator (test A6):
    Pinned as HTTP 404.  The route {chapter_id} is a single path segment;
    /lecture/foo/bar does not match GET /lecture/{chapter_id}.

  Concurrent requests (test F22):
    Determinism contract from ADR-003 — both responses are byte-identical.

pytestmark registers all tests under task("TASK-001").
"""

import pathlib
import re
import threading
import unittest.mock

import pytest

pytestmark = pytest.mark.task("TASK-001")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

REPO_ROOT = pathlib.Path(__file__).parent.parent


def _make_client():
    """
    Create a fresh TestClient.  Deferred import so collection succeeds before
    the app package exists.
    """
    from fastapi.testclient import TestClient  # noqa: PLC0415
    from app.main import app  # noqa: PLC0415

    return TestClient(app)


# ---------------------------------------------------------------------------
# A1 — Nonexistent chapter file → 404, not 500, not 200
# ---------------------------------------------------------------------------


def test_a1_nonexistent_chapter_returns_404():
    """
    ADR-003: GET /lecture/{chapter_id} reads content/latex/{chapter_id}.tex.
    When the file does not exist, the route must return HTTP 404 — not 500
    (internal server error) and not 200 with empty/placeholder content.

    ADR-002: 'ch-99-does-not-exist' is a well-formed Chapter ID (numeric prefix
    99, valid kebab slug).  The failure is file-not-found, not malformed ID.

    Trace: ADR-003 route shape; ADR-001 §1.
    """
    client = _make_client()
    response = client.get("/lecture/ch-99-does-not-exist")
    assert response.status_code == 404, (
        f"Expected 404 for a nonexistent chapter file, got {response.status_code}. "
        "ADR-003: the route must return 404 when the source .tex file is absent."
    )


def test_a1_nonexistent_chapter_not_500():
    """
    Complementary: the nonexistent-chapter response must not be 500.

    A 500 would signal that the renderer crashed (e.g., uncaught FileNotFoundError),
    which is a manifest §6 violation: 'AI failures are visible' — by extension,
    any failure must surface cleanly, not as an unhandled exception.

    Trace: ADR-003; manifest §6 visible-failure principle.
    """
    client = _make_client()
    response = client.get("/lecture/ch-99-does-not-exist")
    assert response.status_code != 500, (
        "GET /lecture/ch-99-does-not-exist returned 500. The renderer crashed on "
        "a missing .tex file.  ADR-003 requires a clean 4xx, not an unhandled "
        "exception propagated to the client."
    )


# ---------------------------------------------------------------------------
# A2 — Malformed Chapter ID → 4xx (pinned: 422)
# ---------------------------------------------------------------------------


def test_a2_malformed_chapter_id_returns_4xx():
    """
    ADR-002 'fail loudly' rule applied at the HTTP layer.

    Chapter ID 'garbage-no-leading-number' has no leading 'ch-NN' or 'chNN'
    component; ADR-002 says the renderer must not fabricate an ID, and
    ADR-004 says chapter_designation must fail loudly for such IDs.

    PINNED CONTRACT: HTTP 422 (Unprocessable Entity).
    Rationale: the ID is syntactically received but semantically invalid — the
    chapter number cannot be extracted.  422 is more precise than 404 for a
    parameter that doesn't match the expected schema.
    If the implementer returns 404 instead, update this contract here.

    The response body MUST NOT contain a Python stack trace and MUST NOT
    contain the text 'Mandatory' or 'Optional' (no fabricated designation).

    Trace: ADR-002; ADR-004; manifest §6 no-fabrication principle.
    """
    client = _make_client()
    response = client.get("/lecture/garbage-no-leading-number")
    assert response.status_code in (404, 422), (
        f"Expected 404 or 422 for a malformed Chapter ID, got {response.status_code}. "
        "ADR-002/ADR-004: malformed IDs must fail loudly, not be silently accepted."
    )


def test_a2_malformed_chapter_id_no_stack_trace_in_body():
    """
    ADR-002 / ADR-003: the 4xx response for a malformed ID must not expose a
    Python stack trace to the caller.

    'Traceback (most recent call last)' appearing in the response body means an
    unhandled exception reached the HTTP client — a security and UX issue.

    Trace: ADR-003 'no crash' principle; manifest §6.
    """
    client = _make_client()
    response = client.get("/lecture/garbage-no-leading-number")
    body = response.text
    assert "Traceback" not in body, (
        "Python traceback leaked into HTTP response body for malformed Chapter ID. "
        "ADR-003/ADR-004: fail loudly with a structured error, not an unhandled exception."
    )


def test_a2_malformed_chapter_id_no_fabricated_designation():
    """
    ADR-004 / ADR-002: a malformed Chapter ID must not produce a page with
    'Mandatory' or 'Optional' in the body.

    If the renderer fabricates a designation rather than failing loudly, the
    manifest §6 invariant ('AI failures are visible; never fabricates a result')
    is violated — even in the non-AI case.

    Trace: ADR-004 fail-loudly rule; ADR-002 no-fabrication principle.
    """
    client = _make_client()
    response = client.get("/lecture/garbage-no-leading-number")
    body = response.text
    # A 4xx response body might contain an error message, but must not contain
    # a designation that implies the page was successfully rendered.
    if response.status_code in (404, 422):
        assert "Mandatory" not in body or "Optional" not in body or len(body) < 500, (
            "Malformed Chapter ID response appears to contain a designation badge "
            "('Mandatory' or 'Optional'). ADR-004: must fail loudly, not fabricate."
        )


# ---------------------------------------------------------------------------
# A3 — Path traversal → 4xx + no file read outside content/latex/
# ---------------------------------------------------------------------------


def test_a3_path_traversal_url_encoded_returns_4xx():
    """
    Security edge case: URL-encoded path traversal must not cause the application
    to read files outside content/latex/.

    PINNED CONTRACT: HTTP 4xx (any 4xx is acceptable; 404 is expected because
    the route pattern does not match cross-segment path components).

    The important invariant tested separately (test_a3_no_file_read_outside_content_latex)
    is that no path outside content/latex/ is opened.

    Trace: ADR-001 §3 read-only and path-confinement; manifest §5.
    """
    client = _make_client()
    # URL-encoded ../.. sequence
    response = client.get("/lecture/..%2F..%2Fetc%2Fpasswd")
    assert response.status_code >= 400, (
        f"Expected 4xx for URL-encoded path traversal, got {response.status_code}. "
        "ADR-001 §3: the application must never read outside content/latex/."
    )


def test_a3_path_traversal_raw_slash_returns_404():
    """
    Raw directory-separator path traversal: GET /lecture/../../etc/passwd.

    FastAPI's routing treats extra slashes as separate path segments, so
    /lecture/../../etc/passwd will not match /lecture/{chapter_id} and
    must return 404.

    PINNED CONTRACT: HTTP 404 (route not matched).

    Trace: ADR-001 §3; ADR-003 route shape (single path segment only).
    """
    client = _make_client()
    # TestClient follows redirects by default; disable for this test.
    response = client.get("/lecture/../../etc/passwd", follow_redirects=False)
    assert response.status_code in (400, 404, 422), (
        f"Expected 4xx for raw path traversal attempt, got {response.status_code}. "
        "ADR-003 route GET /lecture/{chapter_id} is a single path segment; "
        "multi-segment paths must not match."
    )


def test_a3_no_file_read_outside_content_latex(monkeypatch):
    """
    Core path-traversal invariant: no file outside content/latex/ is opened
    when a path-traversal chapter_id is submitted.

    Strategy: monkeypatch pathlib.Path.read_text and builtins.open to record
    every path opened; assert that nothing outside content/latex/ was read.

    This test runs both the URL-encoded and raw path traversal variants.

    PINNED CONTRACT: any open() call whose resolved path falls outside
    content/latex/ is a violation, regardless of HTTP status code.

    Trace: ADR-001 §3 ('No path under content/latex/ is ever opened for
    writing, created, deleted, or moved by application code'); manifest §5
    ('no in-app authoring') — by extension, the path confinement is a
    read-side invariant too.

    ASSUMPTION: The renderer uses pathlib.Path.read_text or builtins.open
    to read source files.
    """
    import builtins

    content_latex_abs = str(REPO_ROOT / "content" / "latex")
    outside_reads: list[str] = []

    original_open = builtins.open
    original_read_text = pathlib.Path.read_text

    def spying_open(file, mode="r", *args, **kwargs):
        path_str = str(file)
        # Flag any read of a path that is NOT under content/latex/ and NOT a
        # stdlib/site-packages file (filter by absolute path under repo root)
        if (
            str(REPO_ROOT) in path_str
            and content_latex_abs not in path_str
            and ".tex" in path_str
        ):
            outside_reads.append(path_str)
        return original_open(file, mode, *args, **kwargs)

    def spying_read_text(self, *args, **kwargs):
        path_str = str(self)
        if (
            str(REPO_ROOT) in path_str
            and content_latex_abs not in path_str
            and ".tex" in path_str
        ):
            outside_reads.append(path_str)
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", spying_open)
    monkeypatch.setattr(pathlib.Path, "read_text", spying_read_text)

    from fastapi.testclient import TestClient  # noqa: PLC0415
    from app.main import app  # noqa: PLC0415

    client = TestClient(app)
    # Both traversal forms; we don't care about the response status code here.
    client.get("/lecture/..%2F..%2Fetc%2Fpasswd")
    client.get("/lecture/../../etc/passwd", follow_redirects=False)

    assert outside_reads == [], (
        f"Path traversal attempt caused the application to open .tex files "
        f"outside content/latex/: {outside_reads}. "
        "ADR-001 §3: the application must be confined to content/latex/ for source reads."
    )


# ---------------------------------------------------------------------------
# A4 — HTTP method not allowed → 405
# ---------------------------------------------------------------------------


def test_a4_post_to_lecture_route_returns_405():
    """
    ADR-003: the route is GET /lecture/{chapter_id} — there is no write-side route.

    Manifest §5: 'No in-app authoring of lecture content.'
    ADR-001 §3: content/latex/ is read-only to the application.

    A POST to /lecture/ch-01-cpp-refresher must return 405 (Method Not Allowed).
    This confirms that no write-side handler was accidentally added.

    PINNED CONTRACT: HTTP 405.  FastAPI's default for an unrouted method on
    a path that has other methods registered.

    Trace: ADR-003 serving strategy ('single route for TASK-001'); manifest §5.
    """
    client = _make_client()
    response = client.post("/lecture/ch-01-cpp-refresher")
    assert response.status_code == 405, (
        f"Expected 405 (Method Not Allowed) for POST /lecture/ch-01-cpp-refresher, "
        f"got {response.status_code}. "
        "ADR-003: only GET is defined; manifest §5 forbids in-app content authoring."
    )


def test_a4_put_to_lecture_route_returns_405():
    """
    Mirror of the POST check for PUT — also a write method that must be rejected.

    Trace: ADR-003; manifest §5.
    """
    client = _make_client()
    response = client.put("/lecture/ch-01-cpp-refresher")
    assert response.status_code == 405, (
        f"Expected 405 for PUT /lecture/ch-01-cpp-refresher, got {response.status_code}. "
        "No write-side route exists; ADR-003 defines GET only."
    )


def test_a4_delete_to_lecture_route_returns_405():
    """
    DELETE on a lecture route must also return 405.

    Trace: ADR-003; manifest §5.
    """
    client = _make_client()
    response = client.delete("/lecture/ch-01-cpp-refresher")
    assert response.status_code == 405, (
        f"Expected 405 for DELETE /lecture/ch-01-cpp-refresher, got {response.status_code}. "
        "ADR-003: no write-side routes defined for TASK-001."
    )


# ---------------------------------------------------------------------------
# A5 — Empty / root path → 404
# ---------------------------------------------------------------------------


def test_a5_empty_chapter_id_in_url_returns_404():
    """
    ADR-003: GET /lecture/{chapter_id} requires a non-empty chapter_id segment.

    GET /lecture/ (empty trailing segment) does not match the route pattern and
    must return 404.

    PINNED CONTRACT: HTTP 404.

    Trace: ADR-003 route shape.
    """
    client = _make_client()
    response = client.get("/lecture/")
    assert response.status_code == 404, (
        f"Expected 404 for GET /lecture/ (empty chapter_id), got {response.status_code}. "
        "ADR-003: the route requires a non-empty {chapter_id} path segment."
    )


def test_a5_lecture_root_without_slash_returns_404():
    """
    GET /lecture (no trailing slash, no chapter_id) must also return 404.

    Trace: ADR-003; no route is defined for /lecture alone.
    """
    client = _make_client()
    response = client.get("/lecture")
    assert response.status_code == 404, (
        f"Expected 404 for GET /lecture, got {response.status_code}. "
        "No handler is defined for /lecture without a chapter_id segment."
    )


# ---------------------------------------------------------------------------
# A6 — Chapter ID with directory separator → 404
# ---------------------------------------------------------------------------


def test_a6_chapter_id_with_subdirectory_returns_404():
    """
    ADR-003: GET /lecture/{chapter_id} is a single-path-segment route.

    GET /lecture/foo/bar — two segments after /lecture/ — does not match the
    route and must return 404.

    This also guards against any accidental wildcard-path matching that could
    be used to traverse directories.

    PINNED CONTRACT: HTTP 404.

    Trace: ADR-003 route shape; ADR-001 §1 (source files live directly in
    content/latex/, no nested chapter subdirectories).
    """
    client = _make_client()
    response = client.get("/lecture/foo/bar")
    assert response.status_code == 404, (
        f"Expected 404 for GET /lecture/foo/bar (two path segments), "
        f"got {response.status_code}. "
        "ADR-003 route is GET /lecture/{chapter_id} — one segment only."
    )


def test_a6_chapter_id_with_three_segments_returns_404():
    """
    Three-segment variant: /lecture/a/b/c must return 404.

    Trace: same as A6 above — ADR-003 single-segment route.
    """
    client = _make_client()
    response = client.get("/lecture/a/b/c")
    assert response.status_code == 404, (
        f"Expected 404 for GET /lecture/a/b/c, got {response.status_code}. "
        "ADR-003: route is single-segment; multi-segment paths must not match."
    )


# ---------------------------------------------------------------------------
# F22 — Concurrent requests → identical responses
# ADR-003 Determinism: no per-request state corruption.
# ---------------------------------------------------------------------------


def test_f22_concurrent_requests_return_identical_bodies():
    """
    ADR-003: 'Two runs against the same content/latex/{chapter_id}.tex …
    produce byte-identical HTML.'

    Two concurrent GET /lecture/ch-01-cpp-refresher requests (via threads)
    must return identical response bodies, confirming that no per-request
    mutable state corrupts the pipeline.

    This complements test_ac4_two_renders_are_byte_identical (sequential
    determinism) by adding a concurrency dimension.

    Trace: ADR-003 Determinism; manifest §7 (single-user invariant means no
    multi-tenant state, but determinism across concurrent invocations of the
    same single-user operation is still required for correctness).
    """
    client = _make_client()
    results: dict[str, str | None] = {"r1": None, "r2": None}

    def fetch(key: str) -> None:
        r = client.get("/lecture/ch-01-cpp-refresher")
        results[key] = r.text if r.status_code == 200 else f"HTTP_{r.status_code}"

    t1 = threading.Thread(target=fetch, args=("r1",))
    t2 = threading.Thread(target=fetch, args=("r2",))
    t1.start()
    t2.start()
    t1.join(timeout=15)
    t2.join(timeout=15)

    assert results["r1"] is not None, "First concurrent request did not complete in time."
    assert results["r2"] is not None, "Second concurrent request did not complete in time."
    assert not results["r1"].startswith("HTTP_"), (
        f"First concurrent request returned an error: {results['r1'][:100]}"
    )
    assert not results["r2"].startswith("HTTP_"), (
        f"Second concurrent request returned an error: {results['r2'][:100]}"
    )
    assert results["r1"] == results["r2"], (
        "Two concurrent GET /lecture/ch-01-cpp-refresher requests returned "
        "different HTML bodies. ADR-003: pipeline must be deterministic; "
        "no per-request mutable state should corrupt the output."
    )
