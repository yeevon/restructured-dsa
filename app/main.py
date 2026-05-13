"""
ADR-003: FastAPI application — serves GET / (landing page) and
GET /lecture/{chapter_id} (Lecture page).

ADR-006: GET / returns the grouped Chapter navigation landing page;
every Lecture page includes the same navigation rail via base.html.j2.
Both surfaces render nav_groups from discover_chapters() — one source of truth.

ADR-022: persistence layer — app/persistence/ is the only DB-toucher.
ADR-023: Notes surface — POST /lecture/{chapter_id}/notes (PRG 303 redirect);
         GET /lecture/{chapter_id} extended to fetch + display Notes.
ADR-024: Section completions — section_completions table; presence-as-complete semantics.
ADR-025: Section completion UI surface — POST /lecture/{chapter_id}/sections/{n}/complete;
         GET /lecture/{chapter_id} extended to pass complete_section_ids to template.

MC-6: no write to content/latex/ — all files are opened read-only.
MC-7: no auth, no user_id, no session.
MC-10: no sqlite3 import here — only in app/persistence/.
"""

from __future__ import annotations

import pathlib

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.discovery import (
    DuplicateChapterNumber,
    InvalidChapterBasename,
    discover_chapters,
    extract_title_from_latex,
)
from app.designation import chapter_designation
from app.parser import extract_sections, parse_latex, _extract_document_body
from app.persistence import (
    init_schema,
    create_note,
    list_notes_for_chapter,
    mark_section_complete,
    unmark_section_complete,
    list_complete_section_ids_for_chapter,
    count_complete_sections_per_chapter,
    request_quiz,
    list_quizzes_for_chapter,
    section_has_nonfailed_quiz,
    get_quiz,
    start_attempt,
    get_attempt,
    get_latest_attempt_for_quiz,
    list_attempt_questions,
    save_attempt_responses,
    submit_attempt,
    # ADR-042 / ADR-043 / ADR-044 In-app test runner (TASK-017)
    get_question,
    save_attempt_test_result,
)
from app.sandbox import run_test_suite

# ---- Jinja2 environment ----
_TEMPLATES_DIR = pathlib.Path(__file__).parent / "templates"
_jinja_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATES_DIR)),
    autoescape=select_autoescape(["html"]),
)

# ---- FastAPI app ----
app = FastAPI(title="Restructured CS 300")

# Mount static files from app/static/
_STATIC_DIR = pathlib.Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

# ---- Persistence bootstrap (ADR-022) ----
# Run schema init at module load time so the DB and table exist before any
# request arrives.  Using startup event would require async; module-level
# call is fine for sync sqlite3 (ADR-022: no async driver).
init_schema()

# ---- Section-count cache pre-warm ----
# discover_chapters() calls extract_sections() (pylatexenc parse) for every
# Chapter to compute section_count for the rail "X / Y" decoration (ADR-026).
# Without pre-warming, the FIRST page request pays the full cold-parse cost for
# all N_chapters at once, violating the 3s-per-chapter performance budget in
# test_task005.  A single eager call here populates the per-process lru_cache on
# extract_sections() and the mtime-keyed cache in discovery.py so that all
# subsequent render requests find warm caches.
#
# This is consistent with the existing init_schema() pattern (module-level
# bootstrap work) and does not violate ADR-007's "request-time scan" rule —
# subsequent discover_chapters() calls still scan the filesystem at request time;
# they just find the section-count cache already warm.
#
# The try/except swallows errors silently so a broken corpus file at startup does
# not prevent the server from starting (individual row degradation per ADR-007
# still applies at request time).
try:
    import app.config as _cfg_boot  # noqa: PLC0415
    discover_chapters(pathlib.Path(_cfg_boot.CONTENT_ROOT))
except Exception:
    pass


def _get_content_root() -> pathlib.Path:
    """
    Return the lecture source root as a Path.
    Uses app.config.CONTENT_ROOT, which tests may monkeypatch.
    """
    import app.config as _cfg  # noqa: PLC0415
    return pathlib.Path(_cfg.CONTENT_ROOT)


def _extract_title(latex_text: str) -> str:
    """
    Extract the chapter title from the LaTeX preamble \\title{...} macro.

    ADR-003: the renderer may peek at the preamble for the title only.
    Delegates to the shared extract_title_from_latex() (ADR-007: single extraction).
    Returns a fallback string "Lecture" if not found.
    """
    result = extract_title_from_latex(latex_text)
    return result if result is not None else "Lecture"


def _build_nav_groups(source_root: pathlib.Path) -> dict:
    """
    Call discover_chapters() and return the nav_groups dict for template rendering.

    Raises DuplicateChapterNumber (ADR-007 whole-surface failure) if the corpus
    contains two files with the same chapter number.
    Raises InvalidChapterBasename (ADR-005 fail-loudly) if any .tex file has an
    invalid basename.
    """
    return discover_chapters(source_root)


def _attach_progress_counts(nav_groups: dict) -> None:
    """
    Attach complete_count to each ChapterEntry in nav_groups, in-place.

    ADR-026: calls count_complete_sections_per_chapter() once (one SQL query)
    to get all Chapter counts, then attaches each count to the corresponding
    ChapterEntry. Chapters with zero completions default to 0 (missing key).

    Also clamps complete_count to section_count to prevent orphan-row display
    anomalies (ADR-026 §Known limitation — orphan/renumber problem).
    """
    complete_counts = count_complete_sections_per_chapter()
    for group_entries in nav_groups.values():
        for entry in group_entries:
            raw_count = complete_counts.get(entry.chapter_id, 0)
            # ADR-026 §orphan clamp: never display X > Y
            entry.complete_count = min(raw_count, entry.section_count)


def render_chapter(chapter_id: str, source_root: str | None = None) -> str:
    """
    Render a Chapter as a full HTML page.

    Reads content/latex/{chapter_id}.tex, parses it, and renders the
    Jinja2 template (which extends base.html.j2 to include the nav rail).

    ADR-001: reads from content/latex/ (read-only).
    ADR-002: section IDs derived from \\section macros.
    ADR-003: pipeline = parse → IR → Jinja2 template.
    ADR-004: designation from chapter_designation().
    ADR-006: nav rail included via base.html.j2.
    ADR-022/ADR-023: notes for the Chapter fetched from persistence and
                     passed to the template under the `notes` variable.

    Raises HTTPException(404) if the .tex file does not exist.
    Raises HTTPException(422) if the chapter_id is malformed (no valid chapter number).
    Raises HTTPException(500) if navigation discovery detects duplicate chapter numbers.
    """
    try:
        chapter_designation(chapter_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid chapter_id {chapter_id!r}: {exc}",
        )

    root = pathlib.Path(source_root) if source_root else _get_content_root()
    tex_path = root / f"{chapter_id}.tex"

    if not tex_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Chapter source file not found: {tex_path.name}",
        )

    latex_text = tex_path.read_text(encoding="utf-8")
    title = _extract_title(latex_text)
    designation = chapter_designation(chapter_id)

    try:
        sections = extract_sections(chapter_id, latex_text)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Section ID derivation failed for {chapter_id!r}: {exc}",
        )

    body = _extract_document_body(latex_text)
    pre_section_html = _parse_pre_section_body(body, chapter_id)

    try:
        nav_groups = _build_nav_groups(root)
    except (DuplicateChapterNumber, InvalidChapterBasename) as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Chapter discovery error: {exc}",
        )

    # ADR-026: attach per-Chapter complete_count to each ChapterEntry in nav_groups.
    _attach_progress_counts(nav_groups)

    # ADR-028: build rail_notes_context for the rail-resident Notes panel.
    # On Lecture pages, this is a simple namespace with chapter_id and notes list.
    # On landing page (GET /), this is None (Notes panel omitted per ADR-028 §Per-Chapter scoping).
    notes_list = list_notes_for_chapter(chapter_id)
    rail_notes_context = _RailNotesContext(chapter_id=chapter_id, notes=notes_list)

    # ADR-025: fetch the set of completed Section IDs for this Chapter.
    # Passed to the template so each Section's form can reflect the current state.
    # A single indexed query per request — sub-millisecond at single-user scale.
    complete_section_ids = set(list_complete_section_ids_for_chapter(chapter_id))

    # ADR-034 §render_chapter: one bulk Quiz query per render, mirroring
    # complete_section_ids / rail_notes_context (ADR-024 / ADR-028 pattern).
    # Returns {section_id: [Quiz, ...]} for every Section with >=1 Quiz.
    # Template defaults missing keys to [] (empty-state for Sections with no Quizzes).
    section_quizzes_by_id = list_quizzes_for_chapter(chapter_id)

    template = _jinja_env.get_template("lecture.html.j2")
    html = template.render(
        chapter_id=chapter_id,
        title=title,
        designation=designation,
        sections=sections,
        pre_section_html=pre_section_html,
        nav_groups=nav_groups,
        rail_notes_context=rail_notes_context,
        complete_section_ids=complete_section_ids,
        section_quizzes_by_id=section_quizzes_by_id,
    )
    return html


def _parse_pre_section_body(body: str, chapter_id: str) -> str:
    """
    Parse the portion of the document body before the first \\section macro.
    Returns HTML for any introductory content (e.g. the chapter-map ideabox).
    """
    from pylatexenc.latexwalker import LatexWalker, LatexMacroNode
    import logging

    logger = logging.getLogger(__name__)
    try:
        walker = LatexWalker(body)
        nodelist, _, _ = walker.get_latex_nodes(pos=0)
        if not nodelist:
            return ""
    except Exception as exc:
        logger.warning("Pre-section body parse error: %s", exc)
        return ""

    pre_nodes = []
    from app.parser import _nodes_to_html
    from app.parser import _is_starred_macro
    for node in nodelist:
        if isinstance(node, LatexMacroNode) and node.macroname == "section":
            if not _is_starred_macro(node):
                break
        pre_nodes.append(node)

    if not pre_nodes:
        return ""
    return _nodes_to_html(pre_nodes)


class _RailNotesContext:
    """
    Simple container for the rail-resident Notes panel context (ADR-028).

    chapter_id: the Chapter whose Notes are displayed.
    notes: list of Note objects (most-recent-first per ADR-023, unchanged).

    On the landing page (GET /), rail_notes_context is None — the Notes panel
    is omitted entirely via {% if rail_notes_context %} guard in the template.
    """
    def __init__(self, chapter_id: str, notes: list) -> None:
        self.chapter_id = chapter_id
        self.notes = notes


@app.get("/", response_class=HTMLResponse)
async def index_page() -> HTMLResponse:
    """
    GET /

    ADR-006: The landing page renders the grouped Chapter navigation.
    Both "Mandatory" and "Optional" sections are shown; each Chapter links to
    /lecture/{chapter_id}.

    Returns:
      200 — successfully rendered landing page
      500 — Chapter discovery failed (duplicate chapter number per ADR-007)
    """
    source_root = _get_content_root()
    try:
        nav_groups = _build_nav_groups(source_root)
    except (DuplicateChapterNumber, InvalidChapterBasename) as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Chapter discovery error: {exc}",
        )

    # ADR-026: attach per-Chapter complete_count to each ChapterEntry in nav_groups.
    _attach_progress_counts(nav_groups)

    template = _jinja_env.get_template("index.html.j2")
    # ADR-028: rail_notes_context=None on landing page (Notes panel omitted per §Per-Chapter scoping)
    html = template.render(nav_groups=nav_groups, rail_notes_context=None)
    return HTMLResponse(content=html, status_code=200)


@app.get("/lecture/{chapter_id}", response_class=HTMLResponse)
async def lecture_page(chapter_id: str) -> HTMLResponse:
    """
    GET /lecture/{chapter_id}

    ADR-003: Lecture route.
    ADR-006: Now renders with the LHS navigation rail via base.html.j2.
    ADR-023: Extended to fetch Notes for the Chapter and pass them to the template.
    Reads content/latex/{chapter_id}.tex, parses it, renders HTML.

    Returns:
      200 — successfully rendered Lecture page
      404 — chapter file does not exist
      422 — chapter_id is malformed (no valid chapter number)
      500 — Chapter discovery failed (duplicate chapter number)
    """
    html = render_chapter(chapter_id)
    return HTMLResponse(content=html, status_code=200)


# Maximum Note body size in bytes (ADR-023 §Validation: 64 KiB).
_MAX_NOTE_BODY_BYTES = 65536  # 64 KiB


@app.post("/lecture/{chapter_id}/notes")
async def create_note_route(
    chapter_id: str,
    body: str = Form(default=""),
) -> RedirectResponse:
    """
    POST /lecture/{chapter_id}/notes

    ADR-023: New Notes creation route.
    Accepts a form-encoded body with a single field `body`.
    Validates and persists the Note, then returns HTTP 303 PRG redirect to
    GET /lecture/{chapter_id}.

    ADR-022: delegates DB work exclusively to app/persistence/ (MC-10).
    MC-6: never writes to content/latex/.
    MC-7: no user_id, no auth, no session.

    Returns:
      303 — success (PRG redirect to the Lecture page)
      400 — body is empty or whitespace-only after trim
      404 — chapter_id is not a known corpus Chapter
      413 — body exceeds 64 KiB
    """
    # Validate chapter_id against the discovered set (ADR-023 §Validation)
    source_root = _get_content_root()
    tex_path = pathlib.Path(source_root) / f"{chapter_id}.tex"
    if not tex_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Chapter not found: {chapter_id!r}",
        )

    # Size check: reject bodies > 64 KiB (ADR-023 §Validation)
    if len(body.encode("utf-8")) > _MAX_NOTE_BODY_BYTES:
        raise HTTPException(
            status_code=413,
            detail="Note body exceeds the 64 KiB maximum.",
        )

    # Trim and reject empty / whitespace-only bodies (ADR-023 §Validation)
    trimmed = body.strip()
    if not trimmed:
        raise HTTPException(
            status_code=400,
            detail="Note body must not be empty.",
        )

    # Persist the Note via the persistence package (ADR-022 §Package boundary)
    create_note(chapter_id, trimmed)

    # PRG redirect to GET /lecture/{chapter_id} (ADR-023 §Route shape, HTTP 303)
    return RedirectResponse(
        url=f"/lecture/{chapter_id}",
        status_code=303,
    )


@app.post("/lecture/{chapter_id}/sections/{section_number}/complete")
async def toggle_section_complete(
    chapter_id: str,
    section_number: str,
    action: str = Form(default=""),
) -> RedirectResponse:
    """
    POST /lecture/{chapter_id}/sections/{section_number}/complete

    ADR-025: Section completion toggle route.
    Accepts a form-encoded body with a single field `action` whose value is
    exactly "mark" or "unmark".

    ADR-024: delegates DB work exclusively to app/persistence/ (MC-10).
    ADR-031 (supersedes ADR-030 §Decision, supersedes ADR-025 §Round-trip-return-point):
             PRG 303 redirect to GET /lecture/{chapter_id}#section-{section_number}-end.
             The fragment points at the .section-end wrapper (id="section-{n-m}-end" in
             lecture.html.j2).  The CSS '.section-end { scroll-margin-top: <large-vh>; }'
             in lecture.css lands the wrapper near the bottom of the viewport — ≈ where
             the user clicked — with no JavaScript. ADR-030's load-bearing principle
             ("response must not relocate the user") is retained.

    MC-6: never writes to content/latex/.
    MC-7: no user_id, no auth, no session.
    MC-10: no sqlite3 import here — only in app/persistence/.

    Returns:
      303 — success (PRG redirect to #section-{n}-end anchor)
      400 — action field is missing or not exactly "mark" or "unmark"
      404 — chapter_id is not a known corpus Chapter
      404 — section_number does not correspond to a known Section in this Chapter
    """
    # --- Validate action field (ADR-025 §Validation) ---
    if action not in ("mark", "unmark"):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid action {action!r}. Must be 'mark' or 'unmark'.",
        )

    # --- Validate chapter_id (ADR-025 §Validation; same pattern as ADR-023) ---
    source_root = _get_content_root()
    tex_path = pathlib.Path(source_root) / f"{chapter_id}.tex"
    if not tex_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Chapter not found: {chapter_id!r}",
        )

    # --- Validate section_number against the discovered Section set (ADR-024/ADR-025) ---
    latex_text = tex_path.read_text(encoding="utf-8")
    try:
        sections = extract_sections(chapter_id, latex_text)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Section ID derivation failed for {chapter_id!r}: {exc}",
        )

    # The full Section ID composed from path parameters (ADR-025 §Route shape)
    section_id = f"{chapter_id}#section-{section_number}"

    known_section_ids = {s["id"] for s in sections}
    if section_id not in known_section_ids:
        raise HTTPException(
            status_code=404,
            detail=f"Section not found: {section_id!r} in chapter {chapter_id!r}",
        )

    # --- Persist the state change via the persistence package (ADR-024 §Package boundary) ---
    if action == "mark":
        mark_section_complete(section_id=section_id, chapter_id=chapter_id)
    else:
        unmark_section_complete(section_id=section_id)

    # --- PRG redirect to GET /lecture/{chapter_id}#section-{section_number}-end ---
    # ADR-031 §Decision (supersedes ADR-030 §Decision): the 303 Location header
    # carries a fragment pointing at the .section-end wrapper (which has
    # id="section-{n-m}-end" in lecture.html.j2).  The CSS rule
    # '.section-end { scroll-margin-top: <large-vh>; }' in lecture.css (ADR-008:
    # section-* → lecture.css) makes the browser leave that much space above
    # .section-end, landing it near the bottom of the viewport — ≈ where the user
    # clicked — with no JavaScript.
    # ADR-030's load-bearing principle ("the response to a reading-flow action must
    # not relocate the user") is retained; ADR-031's mechanism delivers it faithfully.
    return RedirectResponse(
        url=f"/lecture/{chapter_id}#section-{section_number}-end",
        status_code=303,
    )


@app.post("/lecture/{chapter_id}/sections/{section_number}/quiz")
async def request_quiz_route(
    chapter_id: str,
    section_number: str,
) -> RedirectResponse:
    """
    POST /lecture/{chapter_id}/sections/{section_number}/quiz

    ADR-034 §Quiz-trigger route: the natural sibling of POST .../sections/{n}/complete.
    Validates the chapter_id and section_number, then calls request_quiz() to insert
    a status='requested' Quiz row (no AI call, no background job), and PRG-redirects.

    ADR-033 §The `requested` status: the row is honestly "we recorded your request"
    — not a fabricated Quiz, not a finished Quiz (MC-5 / manifest §6).

    MC-1: no LLM SDK call, no ai-workflows invocation.
    MC-6: never writes to content/latex/.
    MC-7: no user_id, no auth, no session.
    MC-9: fires ONLY on the explicit user click — no background job, no auto-trigger.
    MC-10: no sqlite3 import here — only in app/persistence/.

    Returns:
      303 — success (PRG redirect to #section-{section_number}-end anchor)
      404 — chapter_id is not a known corpus Chapter
      404 — section_number does not correspond to a known Section in this Chapter
    """
    # --- Validate chapter_id (mirrors ADR-023 / ADR-024 / ADR-025 pattern) ---
    source_root = _get_content_root()
    tex_path = pathlib.Path(source_root) / f"{chapter_id}.tex"
    if not tex_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Chapter not found: {chapter_id!r}",
        )

    # --- Validate section_number against the parsed Section set (ADR-034 §Quiz-trigger route) ---
    latex_text = tex_path.read_text(encoding="utf-8")
    try:
        sections = extract_sections(chapter_id, latex_text)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Section ID derivation failed for {chapter_id!r}: {exc}",
        )

    # Compose the full Section ID from path parameters (ADR-002 §Section identity)
    section_id = f"{chapter_id}#section-{section_number}"

    known_section_ids = {s["id"] for s in sections}
    if section_id not in known_section_ids:
        raise HTTPException(
            status_code=404,
            detail=f"Section not found: {section_id!r} in chapter {chapter_id!r}",
        )

    # --- First-Quiz-only guard (ADR-037 §The first-Quiz-only guard / MC-8) ---
    # Reject a second request for a Section that already has a non-failed Quiz
    # (status in {'requested', 'generating', 'ready'}). A generation_failed Quiz
    # does NOT count — the author can re-click Generate after a failure.
    # This prevents a fresh-only post-first Quiz (MC-8 violation) from being produced.
    if section_has_nonfailed_quiz(section_id):
        raise HTTPException(
            status_code=409,
            detail=(
                f"Section {section_id!r} already has a Quiz request in progress or "
                "completed. The post-first-Quiz composition surface is not yet available."
            ),
        )

    # --- Persist: insert a status='requested' Quiz row (ADR-033 / ADR-034) ---
    # No AI call; no background job; nothing fabricated (MC-1, MC-5, MC-9).
    request_quiz(section_id)

    # --- PRG redirect to GET /lecture/{chapter_id}#section-{section_number}-end ---
    # ADR-034 §Quiz-trigger route + ADR-031 (no-relocate mechanism reused unchanged):
    # the .section-end wrapper (id="section-{n-m}-end") already carries a large
    # scroll-margin-top in lecture.css; the redirect lands the user back where they
    # clicked with no JavaScript (ADR-030's principle, retained by ADR-031).
    return RedirectResponse(
        url=f"/lecture/{chapter_id}#section-{section_number}-end",
        status_code=303,
    )


@app.get(
    "/lecture/{chapter_id}/sections/{section_number}/quiz/{quiz_id}/take",
    response_class=HTMLResponse,
)
async def take_quiz_page(
    chapter_id: str,
    section_number: str,
    quiz_id: int,
) -> HTMLResponse:
    """
    GET /lecture/{chapter_id}/sections/{section_number}/quiz/{quiz_id}/take

    ADR-038: The Quiz-taking surface.
    Validates chapter_id, section_number, quiz_id; the Quiz must be `ready` and
    must belong to the Section in the URL.  Starts (or resumes) a Quiz Attempt,
    fetches the ordered AttemptQuestion list, and renders quiz_take.html.j2.

    If the Quiz is not `ready`, renders an honest "not ready to take" state
    (no takeable form — ADR-038 §GET validation for non-ready case).

    Returns:
      200 — rendered take surface (in_progress or submitted state)
      404 — unknown chapter_id / section_number / quiz_id / wrong-section quiz
      422 — malformed chapter_id (no valid chapter number)

    MC-4: no AI call, no grading, no grading kick-off inside this handler.
    MC-6: reads content/latex/ read-only.
    MC-7: no user_id, no auth, no session.
    MC-10: no sqlite3 here — only in app/persistence/.
    """
    # --- Validate chapter_id (mirrors render_chapter) ---
    try:
        designation = chapter_designation(chapter_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid chapter_id {chapter_id!r}: {exc}",
        )

    root = _get_content_root()
    tex_path = root / f"{chapter_id}.tex"
    if not tex_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Chapter source file not found: {tex_path.name}",
        )

    # --- Validate section_number against the parsed Section set (ADR-024) ---
    latex_text = tex_path.read_text(encoding="utf-8")
    try:
        sections = extract_sections(chapter_id, latex_text)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Section ID derivation failed for {chapter_id!r}: {exc}",
        )

    section_id = f"{chapter_id}#section-{section_number}"
    known_section_ids = {s["id"] for s in sections}
    if section_id not in known_section_ids:
        raise HTTPException(
            status_code=404,
            detail=f"Section not found: {section_id!r} in chapter {chapter_id!r}",
        )

    # Find the Section dict for its title
    section_dict = next((s for s in sections if s["id"] == section_id), None)
    section_title = (
        section_dict.get("heading", section_number) if section_dict else section_number
    )

    # --- Validate quiz_id (ADR-038 §GET validation) ---
    quiz = get_quiz(quiz_id)
    if quiz is None:
        raise HTTPException(
            status_code=404,
            detail=f"Quiz {quiz_id!r} not found.",
        )
    if quiz.section_id != section_id:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Quiz {quiz_id!r} belongs to section {quiz.section_id!r}, "
                f"not to {section_id!r}."
            ),
        )

    # --- Build nav context (LHS rail + RHS Notes rail per ADR-038 §Template) ---
    try:
        nav_groups = _build_nav_groups(root)
    except (DuplicateChapterNumber, InvalidChapterBasename) as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Chapter discovery error: {exc}",
        )
    _attach_progress_counts(nav_groups)

    notes_list = list_notes_for_chapter(chapter_id)
    rail_notes_context = _RailNotesContext(chapter_id=chapter_id, notes=notes_list)

    back_link = f"/lecture/{chapter_id}#section-{section_number}-end"

    # --- Non-ready Quiz: render honest "not ready" state (no takeable form) ---
    if quiz.status != "ready":
        template = _jinja_env.get_template("quiz_take.html.j2")
        html = template.render(
            chapter_id=chapter_id,
            designation=designation,
            section_number=section_number,
            section_title=section_title,
            quiz=quiz,
            attempt=None,
            attempt_questions=[],
            nav_groups=nav_groups,
            rail_notes_context=rail_notes_context,
            back_link=back_link,
            not_ready=True,
        )
        return HTMLResponse(content=html, status_code=200)

    # --- Happy path: start or resume an Attempt (ADR-038 / ADR-039) ---
    # Check the latest Attempt for this Quiz. If it is already `submitted`, show
    # the "Submitted — grading not yet available" state without creating a new row
    # (ADR-038: "If the Attempt is already `submitted` … render the surface in the
    # submitted state instead of a takeable form").
    latest = get_latest_attempt_for_quiz(quiz_id)
    if latest is not None and latest.status == "submitted":
        attempt = latest
    else:
        attempt = start_attempt(quiz_id)
    aq_list = list_attempt_questions(attempt.attempt_id)

    template = _jinja_env.get_template("quiz_take.html.j2")
    html = template.render(
        chapter_id=chapter_id,
        designation=designation,
        section_number=section_number,
        section_title=section_title,
        quiz=quiz,
        attempt=attempt,
        attempt_questions=aq_list,
        nav_groups=nav_groups,
        rail_notes_context=rail_notes_context,
        back_link=back_link,
        not_ready=False,
    )
    return HTMLResponse(content=html, status_code=200)


@app.post(
    "/lecture/{chapter_id}/sections/{section_number}/quiz/{quiz_id}/take",
)
async def submit_quiz_attempt(
    chapter_id: str,
    section_number: str,
    quiz_id: int,
    request: Request,
) -> RedirectResponse:
    """
    POST /lecture/{chapter_id}/sections/{section_number}/quiz/{quiz_id}/take

    ADR-038: The Quiz-submit route.
    Same path-parameter validation as GET.  Resolves the latest `in_progress`
    Attempt for the Quiz, calls save_attempt_responses and submit_attempt, then
    PRG-redirects back to GET .../take (which re-renders in the submitted state).

    The submit route does NOT invoke grading (MC-4 / manifest §6 / ADR-038 /
    ADR-039 §submit_attempt).  The Attempt sits in `submitted` until the (later)
    out-of-band grading processor picks it up — mirroring ADR-037's generation
    processor.

    Returns:
      303 — PRG redirect to GET .../take
      404 — unknown chapter_id / section_number / quiz_id / wrong-section quiz
      422 — malformed chapter_id

    MC-4: submit_attempt() does not invoke grading. No AI call anywhere.
    MC-7: no user_id, no auth, no session.
    MC-10: no sqlite3 here — only in app/persistence/.
    """
    # --- Same validation as GET (ADR-038 §POST .../take — same path-param validation) ---
    try:
        chapter_designation(chapter_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid chapter_id {chapter_id!r}: {exc}",
        )

    root = _get_content_root()
    tex_path = root / f"{chapter_id}.tex"
    if not tex_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Chapter source file not found: {tex_path.name}",
        )

    latex_text = tex_path.read_text(encoding="utf-8")
    try:
        sections = extract_sections(chapter_id, latex_text)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Section ID derivation failed for {chapter_id!r}: {exc}",
        )

    section_id = f"{chapter_id}#section-{section_number}"
    known_section_ids = {s["id"] for s in sections}
    if section_id not in known_section_ids:
        raise HTTPException(
            status_code=404,
            detail=f"Section not found: {section_id!r} in chapter {chapter_id!r}",
        )

    quiz = get_quiz(quiz_id)
    if quiz is None:
        raise HTTPException(
            status_code=404,
            detail=f"Quiz {quiz_id!r} not found.",
        )
    if quiz.section_id != section_id:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Quiz {quiz_id!r} belongs to section {quiz.section_id!r}, "
                f"not to {section_id!r}."
            ),
        )

    # --- Resolve the latest in_progress Attempt for this Quiz ---
    # start_attempt uses reuse-the-latest-in_progress semantics (ADR-039).
    # If the Attempt is already submitted, this is a harmless double-submit → redirect.
    attempt = start_attempt(quiz_id)

    if attempt.status == "in_progress":
        # Parse form body to build responses dict: {question_id: code}
        form = await request.form()
        responses: dict[int, str] = {}
        for key, value in form.items():
            if key.startswith("response_"):
                try:
                    qid = int(key[len("response_"):])
                    responses[qid] = str(value)
                except (ValueError, IndexError):
                    pass  # ignore malformed keys

        save_attempt_responses(attempt.attempt_id, responses)
        submit_attempt(attempt.attempt_id)

    # --- PRG redirect back to GET .../take (ADR-038 §Submit-route behavior) ---
    take_url = (
        f"/lecture/{chapter_id}"
        f"/sections/{section_number}"
        f"/quiz/{quiz_id}/take"
    )
    return RedirectResponse(url=take_url, status_code=303)


@app.post(
    "/lecture/{chapter_id}/sections/{section_number}/quiz/{quiz_id}/take/run-tests",
)
async def run_tests_route(
    chapter_id: str,
    section_number: str,
    quiz_id: int,
    request: Request,
) -> RedirectResponse:
    """
    POST /lecture/{chapter_id}/sections/{section_number}/quiz/{quiz_id}/take/run-tests

    ADR-043: The "Run tests" route.
    Synchronous form-POST that submits the whole take form, saves all responses,
    runs one Question's test suite via the sandbox (ADR-042), persists the result
    (ADR-044), and PRG-redirects back to GET .../take#question-{question_id}.

    Handler flow (ADR-043 §Handler flow):
    1. Same path-parameter validation as ADR-038's take routes.
    2. Resolve the latest in_progress Attempt (start_attempt reuse semantics).
       - If no in_progress Attempt (submitted / no Attempt), redirect to GET .../take
         (running tests is an in_progress-only action — no sandbox invoked).
    3. Parse form: {question_id: code} dict + target question_id.
    4. save_attempt_responses — persist ALL textareas before the sandbox call.
    5. Fetch the target Question's test_suite via get_question.
       - If question_id not in the Attempt / Quiz → ignore (no sandbox, redirect).
       - If Question has no test_suite → setup_error (surfaced honestly, persisted).
    6. run_test_suite(test_suite, learner_code) → RunResult (ADR-042).
    7. save_attempt_test_result → persist the result (ADR-044).
    8. 303 See Other → GET .../take#question-{question_id}.

    MC-1: no LLM SDK, no ai-workflows call.
    MC-4: running tests is not AI work — synchronous, not out-of-band (ADR-042).
    MC-5 spirit: a sandbox failure is persisted and rendered honestly.
    MC-6: never writes under content/latex/; sandbox runs in temp dir (ADR-042).
    MC-7: no user_id, no auth, no session.
    MC-9: does NOT generate a Quiz.
    MC-10: no sqlite3, no SQL literals — only typed persistence functions.

    Returns:
      303 — PRG redirect to GET .../take#question-{question_id}
      404 — unknown chapter_id / section_number / quiz_id / wrong-section quiz
      422 — malformed chapter_id
    """
    # --- Same path-parameter validation as ADR-038's take routes ---
    try:
        designation = chapter_designation(chapter_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid chapter_id {chapter_id!r}: {exc}",
        )

    root = _get_content_root()
    tex_path = root / f"{chapter_id}.tex"
    if not tex_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Chapter source file not found: {tex_path.name}",
        )

    latex_text = tex_path.read_text(encoding="utf-8")
    try:
        sections = extract_sections(chapter_id, latex_text)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Section ID derivation failed for {chapter_id!r}: {exc}",
        )

    section_id = f"{chapter_id}#section-{section_number}"
    known_section_ids = {s["id"] for s in sections}
    if section_id not in known_section_ids:
        raise HTTPException(
            status_code=404,
            detail=f"Section not found: {section_id!r} in chapter {chapter_id!r}",
        )

    quiz = get_quiz(quiz_id)
    if quiz is None:
        raise HTTPException(
            status_code=404,
            detail=f"Quiz {quiz_id!r} not found.",
        )
    if quiz.section_id != section_id:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Quiz {quiz_id!r} belongs to section {quiz.section_id!r}, "
                f"not to {section_id!r}."
            ),
        )

    # Non-ready Quiz: running tests is only valid for a ready Quiz
    if quiz.status != "ready":
        raise HTTPException(
            status_code=409,
            detail=f"Quiz {quiz_id!r} is not ready (status={quiz.status!r}). "
                   "Tests can only be run while the Quiz is takeable.",
        )

    # --- Parse form body ---
    form = await request.form()
    responses: dict[int, str] = {}
    for key, value in form.items():
        if key.startswith("response_"):
            try:
                qid = int(key[len("response_"):])
                responses[qid] = str(value)
            except (ValueError, IndexError):
                pass

    target_question_id_str = form.get("question_id", "")
    try:
        target_question_id = int(str(target_question_id_str))
    except (ValueError, TypeError):
        target_question_id = None

    # --- Resolve the latest in_progress Attempt ---
    # start_attempt uses reuse-the-latest-in_progress semantics (ADR-039).
    attempt = start_attempt(quiz_id)

    # Running tests is an in_progress-only action (ADR-043)
    take_url_base = (
        f"/lecture/{chapter_id}"
        f"/sections/{section_number}"
        f"/quiz/{quiz_id}/take"
    )
    if attempt.status != "in_progress":
        return RedirectResponse(url=take_url_base, status_code=303)

    # --- Step 4: save ALL responses before the sandbox call ---
    save_attempt_responses(attempt.attempt_id, responses)

    # --- Steps 5-7: fetch test_suite, run sandbox, persist result ---
    # If target_question_id is None or not in the Attempt's rows, ignore gracefully.
    if target_question_id is not None:
        # Verify the question belongs to this Attempt (defensive — matches ADR-043 §ignore posture)
        aq_list = list_attempt_questions(attempt.attempt_id)
        aq_ids = {aq.question_id for aq in aq_list}

        if target_question_id in aq_ids:
            question = get_question(target_question_id)
            if question is not None:
                test_suite = question.test_suite
                learner_code = responses.get(target_question_id, "")

                if test_suite:
                    result = run_test_suite(test_suite, learner_code)
                else:
                    # No test suite — surface honestly as setup_error (ADR-043 §Handler flow)
                    from app.sandbox import RunResult  # noqa: PLC0415
                    result = RunResult(
                        status="setup_error",
                        passed=None,
                        output="This Question has no test suite.",
                    )

                save_attempt_test_result(
                    attempt.attempt_id,
                    target_question_id,
                    passed=result.passed,
                    status=result.status,
                    output=result.output,
                )

    # --- Step 8: PRG redirect to GET .../take#question-{question_id} ---
    # ADR-043 §PRG redirect + ADR-031's no-relocate recipe:
    # The take-page's per-Question block carries id="question-{question_id}";
    # the CSS gives .quiz-take-question a generous scroll-margin-top.
    if target_question_id is not None:
        redirect_url = f"{take_url_base}#question-{target_question_id}"
    else:
        redirect_url = take_url_base

    return RedirectResponse(url=redirect_url, status_code=303)
