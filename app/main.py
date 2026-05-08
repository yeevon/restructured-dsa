"""
ADR-003: FastAPI application — serves GET /lecture/{chapter_id}.

The route reads content/latex/{chapter_id}.tex (ADR-001), parses it with
the pylatexenc-based parser (ADR-003), resolves the Mandatory/Optional
designation (ADR-004), and renders the Jinja2 template.

MC-6: no write to content/latex/ — the file is opened read-only.
MC-7: no auth, no user_id, no session.
"""

from __future__ import annotations

import pathlib
import re

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.config import CONTENT_ROOT
from app.designation import chapter_designation, parse_chapter_number
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
    # Re-import to pick up any test monkeypatching of CONTENT_ROOT
    import app.config as _cfg  # noqa: PLC0415
    return pathlib.Path(_cfg.CONTENT_ROOT)


def _extract_title(latex_text: str) -> str:
    """
    Extract the chapter title from the LaTeX preamble \\title{...} macro.

    ADR-003: the renderer may peek at the preamble for the title only.
    ADR-001: preamble is not Lecture content; only the body is Lecture content.
    Returns a plain-text title, or a fallback string if not found.
    """
    m = re.search(r'\\title\{([^}]+)\}', latex_text)
    if m:
        raw = m.group(1)
        # Strip LaTeX formatting: \\ (line break), \large, etc.
        raw = re.sub(r'\\[a-zA-Z]+', ' ', raw)
        raw = re.sub(r'\{|\}', '', raw)
        return re.sub(r'\s+', ' ', raw).strip()
    return "Lecture"


def render_chapter(chapter_id: str, source_root: str | None = None) -> str:
    """
    Render a Chapter as a full HTML page.

    Reads content/latex/{chapter_id}.tex, parses it, and renders the
    Jinja2 template. Returns the HTML string.

    ADR-001: reads from content/latex/ (read-only).
    ADR-002: section IDs derived from \\section macros.
    ADR-003: pipeline = parse → IR → Jinja2 template.
    ADR-004: designation from chapter_designation().

    Raises HTTPException(404) if the .tex file does not exist.
    Raises HTTPException(422) if the chapter_id is malformed (no valid chapter number).
    """
    # Validate chapter_id can yield a chapter number (ADR-004 fail-loudly)
    # This catches malformed IDs before we attempt a file read
    try:
        chapter_designation(chapter_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid chapter_id {chapter_id!r}: {exc}",
        )

    root = pathlib.Path(source_root) if source_root else _get_content_root()
    tex_path = root / f"{chapter_id}.tex"

    # ADR-001 §3: read-only — never open in write mode
    if not tex_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Chapter source file not found: {tex_path.name}",
        )

    # Read source (read-only, per ADR-001)
    latex_text = tex_path.read_text(encoding="utf-8")

    # Extract chapter title from preamble (ADR-003 exception to preamble-ignore)
    title = _extract_title(latex_text)

    # Resolve Mandatory/Optional designation (ADR-004)
    designation = chapter_designation(chapter_id)

    # Extract sections from the document body (ADR-002)
    # extract_sections raises ValueError if any \\section lacks a leading number
    try:
        sections = extract_sections(chapter_id, latex_text)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Section ID derivation failed for {chapter_id!r}: {exc}",
        )

    # Parse the pre-section body (content before the first \\section)
    # This renders the intro/chapter-map callout that appears before section 1.1
    body = _extract_document_body(latex_text)
    pre_section_html = _parse_pre_section_body(body, chapter_id)

    # Render via Jinja2 template (ADR-003)
    template = _jinja_env.get_template("lecture.html.j2")
    html = template.render(
        chapter_id=chapter_id,
        title=title,
        designation=designation,
        sections=sections,
        pre_section_html=pre_section_html,
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
        # Stop at non-starred \section (which marks the first manifest Section)
        if isinstance(node, LatexMacroNode) and node.macroname == "section":
            if not _is_starred_macro(node):
                break
        pre_nodes.append(node)

    if not pre_nodes:
        return ""
    return _nodes_to_html(pre_nodes)


@app.get("/lecture/{chapter_id}", response_class=HTMLResponse)
async def lecture_page(chapter_id: str) -> HTMLResponse:
    """
    GET /lecture/{chapter_id}

    ADR-003: Single route for TASK-001.
    Reads content/latex/{chapter_id}.tex, parses it, renders HTML.

    Returns:
      200 — successfully rendered Lecture page
      404 — chapter file does not exist
      422 — chapter_id is malformed (no valid chapter number)
    """
    html = render_chapter(chapter_id)
    return HTMLResponse(content=html, status_code=200)
