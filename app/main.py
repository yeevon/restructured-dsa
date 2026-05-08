"""
ADR-003: FastAPI application — serves GET / (landing page) and
GET /lecture/{chapter_id} (Lecture page).

ADR-006: GET / returns the grouped Chapter navigation landing page;
every Lecture page includes the same navigation rail via base.html.j2.
Both surfaces render nav_groups from discover_chapters() — one source of truth.

MC-6: no write to content/latex/ — all files are opened read-only.
MC-7: no auth, no user_id, no session.
"""

from __future__ import annotations

import pathlib

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
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

    template = _jinja_env.get_template("lecture.html.j2")
    html = template.render(
        chapter_id=chapter_id,
        title=title,
        designation=designation,
        sections=sections,
        pre_section_html=pre_section_html,
        nav_groups=nav_groups,
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

    template = _jinja_env.get_template("index.html.j2")
    html = template.render(nav_groups=nav_groups)
    return HTMLResponse(content=html, status_code=200)


@app.get("/lecture/{chapter_id}", response_class=HTMLResponse)
async def lecture_page(chapter_id: str) -> HTMLResponse:
    """
    GET /lecture/{chapter_id}

    ADR-003: Lecture route.
    ADR-006: Now renders with the LHS navigation rail via base.html.j2.
    Reads content/latex/{chapter_id}.tex, parses it, renders HTML.

    Returns:
      200 — successfully rendered Lecture page
      404 — chapter file does not exist
      422 — chapter_id is malformed (no valid chapter number)
      500 — Chapter discovery failed (duplicate chapter number)
    """
    html = render_chapter(chapter_id)
    return HTMLResponse(content=html, status_code=200)
