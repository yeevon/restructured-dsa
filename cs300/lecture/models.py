"""
Pydantic models for the Chapter / Section / Block intermediate representation.

Per ADR-003: the parser produces this model; both the HTML renderer and the
future Lecture Script extractor consume it. Neither re-parses LaTeX.
"""

from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Inline variants
# ---------------------------------------------------------------------------


class TextInline(BaseModel):
    kind: Literal["text"] = "text"
    text: str


class EmphasisInline(BaseModel):
    kind: Literal["emphasis"] = "emphasis"
    strong: bool
    inlines: list["Inline"]


class CodeInline(BaseModel):
    kind: Literal["code"] = "code"
    source: str


class MathInline(BaseModel):
    kind: Literal["math"] = "math"
    latex: str


class LinkInline(BaseModel):
    kind: Literal["link"] = "link"
    target: str
    inlines: list["Inline"]


Inline = Annotated[
    Union[TextInline, EmphasisInline, CodeInline, MathInline, LinkInline],
    Field(discriminator="kind"),
]


# ---------------------------------------------------------------------------
# Block variants
# ---------------------------------------------------------------------------


class ParagraphBlock(BaseModel):
    kind: Literal["paragraph"] = "paragraph"
    inlines: list[Inline]


class HeadingBlock(BaseModel):
    """Subsection / subsubsection — in-section structure, NOT a top-level Section."""

    kind: Literal["heading"] = "heading"
    level: int  # 3 for subsection, 4 for subsubsection, etc.
    inlines: list[Inline]


class ListBlock(BaseModel):
    kind: Literal["list"] = "list"
    ordered: bool
    items: list[list["Block"]]


class CodeBlock(BaseModel):
    kind: Literal["code"] = "code"
    language: str | None
    source: str


class EquationBlock(BaseModel):
    """Display math equation.  latex is verbatim LaTeX."""

    kind: Literal["equation"] = "equation"
    display: bool
    latex: str


class PassthroughBlock(BaseModel):
    """Unrecognized LaTeX environment — preserved verbatim per ADR-004."""

    kind: Literal["passthrough"] = "passthrough"
    environment: str
    raw_latex: str


Block = Annotated[
    Union[
        ParagraphBlock,
        HeadingBlock,
        ListBlock,
        CodeBlock,
        EquationBlock,
        PassthroughBlock,
    ],
    Field(discriminator="kind"),
]


# ---------------------------------------------------------------------------
# Section and Chapter
# ---------------------------------------------------------------------------


class Section(BaseModel):
    id: str  # "<chapter_id>#<section-slug>" per ADR-002
    title: str
    blocks: list[Block]


class Chapter(BaseModel):
    id: str  # "ch-NN-<slug>" per ADR-001
    title: str
    designation: Literal["mandatory", "optional"]
    sections: list[Section]
