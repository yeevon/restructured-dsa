"""
cs300.lecture — LaTeX parsing and HTML rendering for Lecture Pages.

Public exports (consumed by tests and by cs300.app):
  parse_chapter          — Path -> Chapter (pure parser)
  render_html            — Chapter -> str (HTML renderer)
  designation_for_chapter_id — str -> Literal["mandatory","optional"]
  Chapter, Section       — top-level Pydantic models
  PassthroughBlock       — block model for unrecognised LaTeX environments
"""

from .designation import designation_for_chapter_id
from .models import (
    Block,
    Chapter,
    CodeBlock,
    EquationBlock,
    HeadingBlock,
    Inline,
    ListBlock,
    ParagraphBlock,
    PassthroughBlock,
    Section,
)
from .parser import parse_chapter
from .render import render_html

__all__ = [
    "parse_chapter",
    "render_html",
    "designation_for_chapter_id",
    "Chapter",
    "Section",
    "Block",
    "Inline",
    "ParagraphBlock",
    "HeadingBlock",
    "ListBlock",
    "CodeBlock",
    "EquationBlock",
    "PassthroughBlock",
]
