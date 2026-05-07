"""
LaTeX -> Chapter parser using plasTeX.

Per ADR-001: Chapter ID is the basename of the .tex file (without extension).
Per ADR-002: Only \\section{} produces a Section; subsections stay inline.
Per ADR-003: Returns a structured Chapter/Section/Block intermediate model.
Per ADR-004: Unrecognized environments produce PassthroughBlock, never silent drops.
"""

from __future__ import annotations

import logging
import re
import warnings
from pathlib import Path

from .designation import designation_for_chapter_id
from .models import (
    Block,
    Chapter,
    CodeBlock,
    EmphasisInline,
    EquationBlock,
    HeadingBlock,
    Inline,
    MathInline,
    ParagraphBlock,
    PassthroughBlock,
    Section,
    TextInline,
    CodeInline,
)

logger = logging.getLogger(__name__)

# ADR-001: valid filename pattern
_FILENAME_RE = re.compile(r"^ch-(\d{2})-([a-z0-9]+(?:-[a-z0-9]+)*)$")

# plasTeX node names that are inline formatting (emphasis-like)
_STRONG_NODES = frozenset({"textbf"})
_EM_NODES = frozenset({"textit", "emph", "textsl"})
_CODE_INLINE_NODES = frozenset({"texttt", "verb"})


def _slugify(text: str) -> str:
    """Pure ADR-002 slugify: lowercase, collapse non-alphanumeric runs to hyphens, strip edges."""
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = text.strip("-")
    return text or "section"


def _node_is_begin_unknown(node) -> str | None:  # type: ignore[no-untyped-def]
    """If node looks like \\begin{X} for an unknown environment, return the env name; else None."""
    src = str(node.source).strip()
    if src.startswith("\\begin{") and node.nodeName not in _KNOWN_BLOCK_ENVS:
        env_name = node.nodeName
        if env_name != "#text":
            return env_name
    return None


def _node_is_end_unknown(node, env_name: str) -> bool:  # type: ignore[no-untyped-def]
    """Return True if node looks like \\end{env_name}."""
    src = str(node.source).strip()
    return src == f"\\end{{{env_name}}}"


def _walk_inlines(nodes) -> list[Inline]:  # type: ignore[no-untyped-def]
    """Convert a sequence of plasTeX inline nodes to Inline model objects."""
    result: list[Inline] = []
    for node in nodes:
        name = node.nodeName
        if name == "#text":
            text = str(node)
            if text:
                result.append(TextInline(text=text))
        elif name == "math":
            # Inline math: $...$
            latex = node.source
            result.append(MathInline(latex=latex))
        elif name in _STRONG_NODES:
            inner = _walk_inlines(node.childNodes)
            result.append(EmphasisInline(strong=True, inlines=inner))
        elif name in _EM_NODES:
            inner = _walk_inlines(node.childNodes)
            result.append(EmphasisInline(strong=False, inlines=inner))
        elif name in _CODE_INLINE_NODES:
            result.append(CodeInline(source=node.textContent))
        else:
            # Unknown inline command — degrade to plain text
            text = node.textContent
            if text:
                result.append(TextInline(text=text))
    return result


# Known block-level environments that the parser handles natively
_KNOWN_BLOCK_ENVS = frozenset(
    {
        "document",
        "equation",
        "equation*",
        "align",
        "align*",
        "verbatim",
        "itemize",
        "enumerate",
        "lstlisting",
        "par",
        "section",
        "subsection",
        "subsubsection",
        "maketitle",
        "title",
        "label",
        "newpage",
        "clearpage",
        "#comment",
        "#text",
        "math",
    }
    | _STRONG_NODES
    | _EM_NODES
    | _CODE_INLINE_NODES
)


def _collect_passthrough_from_par_children(
    children: list,  # type: ignore[type-arg]
    i: int,
    env_name: str,
) -> tuple[PassthroughBlock, int]:
    """Scan children starting at i (which is the \\begin{env_name} node).

    Returns (PassthroughBlock, new_index) where new_index is the index AFTER
    the matched \\end{env_name} node (or end of list if never closed).
    """
    begin_src = str(children[i].source)
    raw_parts = [begin_src]
    j = i + 1
    while j < len(children):
        node = children[j]
        src = str(node.source)
        if _node_is_end_unknown(node, env_name):
            raw_parts.append(src)
            j += 1
            break
        raw_parts.append(src)
        j += 1
    raw_latex = "".join(raw_parts)
    return PassthroughBlock(environment=env_name, raw_latex=raw_latex), j


def _walk_par_children(children) -> list[Block]:  # type: ignore[no-untyped-def]
    """Walk the children of a par node, handling unknown-environment passthrough."""
    blocks: list[Block] = []
    inlines: list[Inline] = []
    i = 0
    child_list = list(children)

    def flush_inlines() -> None:
        nonlocal inlines
        non_empty = [
            il
            for il in inlines
            if not (isinstance(il, TextInline) and not il.text.strip())
        ]
        if non_empty:
            blocks.append(ParagraphBlock(inlines=list(inlines)))
        inlines = []

    while i < len(child_list):
        node = child_list[i]
        name = node.nodeName
        src = str(node.source).strip()

        # Detect start of an unknown \\begin{X} environment
        if (
            name not in _KNOWN_BLOCK_ENVS
            and src.startswith("\\begin{")
            and not src.startswith("\\begin{document}")
        ):
            flush_inlines()
            passthrough_block, i = _collect_passthrough_from_par_children(
                child_list, i, name
            )
            blocks.append(passthrough_block)
            continue

        # Known block-level environments embedded in a par
        if name == "equation" or name == "equation*":
            flush_inlines()
            blocks.append(EquationBlock(display=True, latex=node.textContent))
        elif name in ("align", "align*"):
            flush_inlines()
            blocks.append(EquationBlock(display=True, latex=node.source))
        elif name == "verbatim":
            flush_inlines()
            blocks.append(CodeBlock(language=None, source=node.textContent))
        elif name == "lstlisting":
            flush_inlines()
            blocks.append(CodeBlock(language=None, source=node.textContent))
        elif name in ("#text",):
            text = str(node)
            if text:
                inlines.append(TextInline(text=text))
        elif name == "math":
            inlines.append(MathInline(latex=node.source))
        elif name in _STRONG_NODES:
            inner = _walk_inlines(node.childNodes)
            inlines.append(EmphasisInline(strong=True, inlines=inner))
        elif name in _EM_NODES:
            inner = _walk_inlines(node.childNodes)
            inlines.append(EmphasisInline(strong=False, inlines=inner))
        elif name in _CODE_INLINE_NODES:
            inlines.append(CodeInline(source=node.textContent))
        elif name in ("maketitle", "label", "newpage", "clearpage", "#comment"):
            pass  # structural — skip
        else:
            # Unknown inline command — treat as plain text if it has text content
            text = node.textContent
            if text and text.strip():
                inlines.append(TextInline(text=text))

        i += 1

    flush_inlines()
    return blocks


def _walk_blocks(nodes) -> list[Block]:  # type: ignore[no-untyped-def]
    """Convert a sequence of plasTeX nodes (direct children of a section) to Block objects."""
    blocks: list[Block] = []

    for node in nodes:
        name = node.nodeName

        if name == "par":
            blocks.extend(_walk_par_children(node.childNodes))
        elif name == "subsection":
            title_frag = node.attributes.get("title")
            heading_text = title_frag.source if title_frag is not None else ""
            inlines: list[Inline] = [TextInline(text=heading_text.strip())]
            blocks.append(HeadingBlock(level=3, inlines=inlines))
            # Walk the subsection's own children
            blocks.extend(_walk_blocks(node.childNodes))
        elif name == "subsubsection":
            title_frag = node.attributes.get("title")
            heading_text = title_frag.source if title_frag is not None else ""
            inlines2: list[Inline] = [TextInline(text=heading_text.strip())]
            blocks.append(HeadingBlock(level=4, inlines=inlines2))
            blocks.extend(_walk_blocks(node.childNodes))
        elif name == "equation" or name == "equation*":
            blocks.append(EquationBlock(display=True, latex=node.textContent))
        elif name in ("align", "align*"):
            blocks.append(EquationBlock(display=True, latex=node.source))
        elif name == "verbatim":
            blocks.append(CodeBlock(language=None, source=node.textContent))
        elif name == "lstlisting":
            blocks.append(CodeBlock(language=None, source=node.textContent))
        elif name in ("#text",):
            text = str(node).strip()
            if text:
                blocks.append(ParagraphBlock(inlines=[TextInline(text=text)]))
        elif name in (
            "maketitle",
            "label",
            "newpage",
            "clearpage",
            "#comment",
            "title",
        ):
            pass  # structural — skip
        else:
            # Unknown environment/command — PassthroughBlock per ADR-004
            raw = node.source
            if raw and raw.strip():
                blocks.append(PassthroughBlock(environment=name, raw_latex=str(raw)))

    return blocks


def parse_chapter(tex_path: Path) -> Chapter:
    """Parse a single .tex file into a Chapter model.

    Raises ValueError if the filename does not match the required pattern.
    """
    # ADR-001: validate filename
    stem = tex_path.stem
    if not _FILENAME_RE.match(stem):
        raise ValueError(
            f"Filename {tex_path.name!r} does not match required pattern "
            r"'^ch-(\d{2})-([a-z0-9]+(?:-[a-z0-9]+)*)$'"
        )

    chapter_id = stem
    designation = designation_for_chapter_id(chapter_id)

    # Parse with plasTeX, suppressing the unrecognised-env warnings we handle ourselves.
    # NOTE: the file handle must remain open for the entire duration of tex.parse().
    # We deliberately do NOT chdir into the .tex file's directory: when plasTeX can resolve
    # \input{notes-style.tex} it cascades into the full \usepackage chain (tcolorbox -> tikz
    # -> kvoptions) and the macro expander chokes mid-document, dropping section structure.
    # Letting \input fail gracefully keeps the document body parseable. The cost — custom
    # environments defined in style files render as PassthroughBlocks (ADR-004) — is the
    # subject of design_docs/project_issues/custom-latex-environments.md.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        from plasTeX.TeX import TeX  # type: ignore[import-untyped]

        fh = tex_path.open()
        try:
            tex = TeX()
            tex.input(fh)
            doc = tex.parse()
        finally:
            fh.close()

    # Extract document title from \title{...}
    chapter_title = _extract_document_title(doc, chapter_id)

    # Collect \section{} nodes — direct children of the document body only
    section_nodes = [
        n for n in doc.getElementsByTagName("section") if _is_top_level_section(n)
    ]

    # ADR-002: if no \section{} exists, produce one implicit Section with id #main
    if not section_nodes:
        body_nodes = _get_document_body_nodes(doc)
        sections: list[Section] = [
            Section(
                id=f"{chapter_id}#main",
                title=chapter_title,
                blocks=_walk_blocks(body_nodes),
            )
        ]
        return Chapter(
            id=chapter_id,
            title=chapter_title,
            designation=designation,
            sections=sections,
        )

    # ADR-002: build Section objects with slug-based IDs
    seen_slugs: dict[str, int] = {}
    sections_list: list[Section] = []

    for sec_node in section_nodes:
        title_frag = sec_node.attributes.get("title")
        heading_text = title_frag.source if title_frag is not None else ""
        section_title = heading_text.strip()
        slug = _slugify(section_title)

        # Collision handling: second occurrence gets -2, third -3, etc.
        if slug in seen_slugs:
            seen_slugs[slug] += 1
            slug = f"{slug}-{seen_slugs[slug]}"
            logger.warning(
                "Section slug collision; assigned disambiguated slug %r", slug
            )
        else:
            seen_slugs[slug] = 1

        section_id = f"{chapter_id}#{slug}"
        blocks = _walk_blocks(sec_node.childNodes)
        sections_list.append(Section(id=section_id, title=section_title, blocks=blocks))

    return Chapter(
        id=chapter_id,
        title=chapter_title,
        designation=designation,
        sections=sections_list,
    )


def _extract_document_title(doc, fallback: str) -> str:  # type: ignore[no-untyped-def]
    """Extract plain-text title from \\title{...} in the document."""
    title_nodes = doc.getElementsByTagName("title")
    if title_nodes:
        return title_nodes[0].textContent.strip()
    return fallback


def _is_top_level_section(node) -> bool:  # type: ignore[no-untyped-def]
    """Return True if the section node is a direct child of the document body.

    Prevents double-counting when sections nest (shouldn't happen in article class,
    but guards against it).
    """
    parent = node.parentNode
    if parent is None:
        return True
    return parent.nodeName not in ("section",)


def _get_document_body_nodes(doc):  # type: ignore[no-untyped-def]
    """Return the child nodes of the document body element."""
    doc_nodes = doc.getElementsByTagName("document")
    if doc_nodes:
        return list(doc_nodes[0].childNodes)
    return list(doc.childNodes)
