"""
FastAPI application for Restructured CS 300.

Routes (ADR-005):
  GET /chapters/{chapter_id}/lecture  — Lecture Page for one Chapter
"""

from __future__ import annotations

import re
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from cs300.lecture import parse_chapter, render_html

app = FastAPI(title="Restructured CS 300")

_CONTENT_LATEX_DIR = Path(__file__).parent.parent / "content" / "latex"
_CHAPTER_ID_RE = re.compile(r"^ch-(\d{2})-([a-z0-9]+(?:-[a-z0-9]+)*)$")


@app.get("/chapters/{chapter_id}/lecture", response_class=HTMLResponse)
def lecture_page(chapter_id: str) -> HTMLResponse:
    """Render the Lecture Page for a Chapter.

    Returns 404 if chapter_id is malformed or the .tex file does not exist.
    """
    if not _CHAPTER_ID_RE.match(chapter_id):
        return HTMLResponse(content="Not found", status_code=404)

    tex_path = _CONTENT_LATEX_DIR / f"{chapter_id}.tex"
    if not tex_path.exists():
        return HTMLResponse(content="Not found", status_code=404)

    chapter = parse_chapter(tex_path)
    html = render_html(chapter)
    return HTMLResponse(content=html, status_code=200)
