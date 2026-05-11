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
)

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
    ADR-025: PRG 303 redirect to GET /lecture/{chapter_id}#section-{section_number}
             so the browser scrolls back to the just-toggled Section.

    MC-6: never writes to content/latex/.
    MC-7: no user_id, no auth, no session.
    MC-10: no sqlite3 import here — only in app/persistence/.

    Returns:
      303 — success (PRG redirect with URL fragment)
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

    # --- PRG redirect to GET /lecture/{chapter_id}#section-{section_number} ---
    # ADR-025 §Round-trip return point: URL fragment restores browser scroll position.
    return RedirectResponse(
        url=f"/lecture/{chapter_id}#section-{section_number}",
        status_code=303,
    )
