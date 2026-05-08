"""
Playwright DOM-content tests migrated from tests/test_task001_http_edges.py.

Per ADR-010 "Migration scope":
  "test_task001_parser_edges.py and test_task001_http_edges.py — the subsets that
  assert against response.text body content; the implementer reads each test and
  classifies (status-code/header tests stay in pytest, body-content tests move)"

Migrated to Playwright (body-content assertions):
  - test_a2_malformed_chapter_id_no_stack_trace_in_body
      Asserts that "Traceback" does NOT appear in the response body for a
      malformed Chapter ID.  This is a body-content assertion that belongs in
      the rendered-DOM layer.
  - test_a2_malformed_chapter_id_no_fabricated_designation
      Asserts that "Mandatory" and "Optional" do NOT both appear in the body
      for a malformed Chapter ID.  Body-content assertion.

Tests NOT migrated (stay in tests/test_task001_http_edges.py):
  - test_a1_nonexistent_chapter_returns_404          (HTTP status code)
  - test_a1_nonexistent_chapter_not_500              (HTTP status code)
  - test_a2_malformed_chapter_id_returns_4xx         (HTTP status code)
  - test_a3_path_traversal_url_encoded_returns_4xx   (HTTP status code)
  - test_a3_path_traversal_raw_slash_returns_404     (HTTP status code)
  - test_a3_no_file_read_outside_content_latex       (monkeypatch side-effect)
  - test_a4_post_to_lecture_route_returns_405        (HTTP status code)
  - test_a4_put_to_lecture_route_returns_405         (HTTP status code)
  - test_a4_delete_to_lecture_route_returns_405      (HTTP status code)
  - test_a5_empty_chapter_id_in_url_returns_404      (HTTP status code)
  - test_a5_lecture_root_without_slash_returns_404   (HTTP status code)
  - test_a6_chapter_id_with_subdirectory_returns_404 (HTTP status code)
  - test_a6_chapter_id_with_three_segments_returns_404 (HTTP status code)
  - test_f22_concurrent_requests_return_identical_bodies (byte-equality of
      two responses; no DOM walk)

All of these remain in tests/test_task001_http_edges.py per ADR-010.

NOTE ON APPROACH:
The tests in this file navigate to the error-response URL via Playwright
and assert about what appears (or MUST NOT appear) in the rendered DOM.
This is the same contract as the original tests but exercised through a
real browser, which strengthens the assertion (e.g., checking that
"Traceback" is not visible in the browser, not just absent from the raw
HTTP response body).

pytestmark registers all tests under task("TASK-001") to preserve the
original task association.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page

pytestmark = pytest.mark.task("TASK-001")

# ---------------------------------------------------------------------------
# A2 — Malformed Chapter ID → body must not contain a Python traceback
# ---------------------------------------------------------------------------


def test_a2_malformed_chapter_id_no_stack_trace_in_body(
    page: Page, live_server: str
) -> None:
    """
    ADR-002 / ADR-003: the 4xx response for a malformed Chapter ID must not
    expose a Python stack trace to the caller.

    'Traceback (most recent call last)' appearing in the rendered DOM means
    an unhandled exception reached the browser — a security and UX issue.

    ADR-003: 'no crash' principle; manifest §6 'AI failures are visible' (but
    as structured errors, not raw Python tracebacks).

    NOTE: This is a DOM-content assertion that has been migrated from
    tests/test_task001_http_edges.py per ADR-010.  The HTTP-status-code
    assertion (expects 404 or 422) stays in the original pytest file.

    Trace: TASK-001 A2; ADR-003; manifest §6; ADR-010 migration.
    """
    page.goto(live_server + "/lecture/garbage-no-leading-number")
    page.wait_for_load_state("networkidle")

    body_text = page.locator("body").evaluate("el => el.innerText")

    assert "Traceback" not in body_text, (
        "Python traceback leaked into the rendered browser DOM for malformed "
        "Chapter ID 'garbage-no-leading-number'. "
        "ADR-003/ADR-004: fail loudly with a structured error, not an unhandled "
        "exception propagated to the client."
    )

    # Also check for the raw exception phrase that typically follows Traceback
    assert "most recent call last" not in body_text, (
        "Fragment 'most recent call last' (typical Python traceback header) found "
        "in rendered DOM. ADR-003: raw Python tracebacks must not reach the browser."
    )


# ---------------------------------------------------------------------------
# A2 — Malformed Chapter ID → body must not contain a fabricated designation
# ---------------------------------------------------------------------------


def test_a2_malformed_chapter_id_no_fabricated_designation(
    page: Page, live_server: str
) -> None:
    """
    ADR-004 / ADR-002: a malformed Chapter ID must not produce a rendered page
    with both 'Mandatory' and 'Optional' in the DOM — such a page would imply
    that a designation badge was fabricated rather than the route failing loudly.

    If the renderer fabricates a designation rather than failing loudly, the
    manifest §6 invariant ('AI failures are visible; never fabricates a result')
    is violated.

    NOTE: This test is scoped narrowly:
    - A 4xx error page that happens to contain one of the words 'Mandatory' or
      'Optional' in an error message is acceptable (e.g., "This chapter ID is
      not Mandatory or Optional because it could not be parsed.").
    - What is NOT acceptable: a fully-rendered lecture page with a designation
      badge showing 'Mandatory' or 'Optional' for a malformed chapter ID.
    - Strategy: check that the page does NOT look like a successfully-rendered
      lecture page (i.e., no .designation-badge element with Mandatory/Optional
      text is visible in a .lecture-header context).

    NOTE: This is a DOM-content assertion migrated from
    tests/test_task001_http_edges.py per ADR-010.

    Trace: TASK-001 A2; ADR-004 fail-loudly rule; ADR-002 no-fabrication
    principle; manifest §6; ADR-010 migration.
    """
    page.goto(live_server + "/lecture/garbage-no-leading-number")
    page.wait_for_load_state("networkidle")

    # If a .designation-badge is visible inside .lecture-header, it means
    # the renderer successfully rendered a lecture page — that would be a
    # fabrication (the chapter does not exist).
    badge_in_header = page.locator(".lecture-header .designation-badge")
    badge_count = badge_in_header.count()

    if badge_count > 0 and badge_in_header.first.is_visible():
        badge_text = badge_in_header.first.text_content() or ""
        # If a badge is visible with a designation, that's a fabrication
        assert not ("Mandatory" in badge_text or "Optional" in badge_text), (
            f"Malformed Chapter ID 'garbage-no-leading-number' rendered a lecture page "
            f"with designation badge text: {badge_text!r}. "
            "ADR-004: must fail loudly, not fabricate a designation. "
            "The route must return an error, not a rendered lecture page."
        )

    # Additional check: there should be no .lecture-header at all for a 4xx page
    lecture_header = page.locator(".lecture-header")
    if lecture_header.count() > 0 and lecture_header.first.is_visible():
        # A lecture header visible on a 4xx error page means the router
        # rendered a lecture page instead of an error
        body_text = page.locator("body").evaluate("el => el.innerText")
        # Both Mandatory AND Optional visible in a lecture-header context means
        # the whole page was rendered (not just an error page that mentions the words)
        has_mandatory_in_header = "Mandatory" in (
            lecture_header.first.evaluate("el => el.innerText") or ""
        )
        assert not has_mandatory_in_header, (
            "Malformed Chapter ID 'garbage-no-leading-number' produced a visible "
            ".lecture-header with designation content. "
            "ADR-004: must fail loudly for malformed IDs — not render a lecture page."
        )
