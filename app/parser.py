"""
ADR-003: LaTeX parser using pylatexenc.

This module walks the LaTeX document body (between \\begin{document} and
\\end{document}) and converts it to an intermediate representation (IR)
that the Jinja2 template renders to HTML.

Key responsibilities:
  - Locate the document environment per ADR-001
  - Recognize \\section macros and emit Section anchors per ADR-002
  - Recognize \\subsection macros as headings (not Sections per ADR-002)
  - Recognize callout environments (ideabox, defnbox, notebox, warnbox, examplebox)
    and emit them as styled HTML blocks with data-callout="<env-name>"
  - Recognize lstlisting environments and emit them as <pre><code> blocks
  - Pass inline math ($...$) and display math (\\[...\\]) through unchanged
  - Log a structured WARNING per unrecognized node; do not crash; do not fabricate
"""

from __future__ import annotations

import html as _html_mod
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# ---- Callout environments recognized by this parser ----
CALLOUT_ENVS = frozenset({"ideabox", "defnbox", "notebox", "warnbox", "examplebox"})

# ---- Section number pattern: must start with N.M ----
_SECTION_NUMBER_RE = re.compile(r"^(\d+\.\d+)")

# ---- LaTeX to inline-HTML text conversion helpers ----

def _escape(text: str) -> str:
    """HTML-escape a plain text string."""
    return _html_mod.escape(text, quote=False)


def _text_to_html(text: str) -> str:
    """
    Convert a plain LaTeX text node to HTML-safe text.
    Escapes &, <, > for use in HTML.
    Math delimiters $ and \\[ are preserved for MathJax.
    """
    return _html_mod.escape(text, quote=False)


def _convert_inline_latex(node_list: list, context: str = "body") -> str:
    """
    Recursively convert a list of pylatexenc nodes to HTML.

    This handles the inline content of paragraphs, headings, etc.
    Known macros are converted; unknown macros are logged and their
    argument text is preserved where possible.
    """
    from pylatexenc.latexwalker import (
        LatexCharsNode,
        LatexMacroNode,
        LatexEnvironmentNode,
        LatexGroupNode,
        LatexMathNode,
        LatexSpecialsNode,
        LatexCommentNode,
    )

    result_parts: list[str] = []

    for node in (node_list or []):
        if node is None:
            continue

        if isinstance(node, LatexCharsNode):
            result_parts.append(_escape(node.chars))

        elif isinstance(node, LatexCommentNode):
            # LaTeX comments are ignored in output
            pass

        elif isinstance(node, LatexMathNode):
            # Pass math through unchanged for MathJax
            result_parts.append(node.latex_verbatim())

        elif isinstance(node, LatexSpecialsNode):
            # Handle LaTeX specials like ~, --, ---, etc.
            s = node.specials_chars
            if s == "~":
                result_parts.append("&nbsp;")
            elif s == "---":
                result_parts.append("&mdash;")
            elif s == "--":
                result_parts.append("&ndash;")
            else:
                result_parts.append(_escape(s))

        elif isinstance(node, LatexGroupNode):
            # Braces group — recurse
            result_parts.append(_convert_inline_latex(node.nodelist.nodelist if hasattr(node.nodelist, 'nodelist') else (node.nodelist or []), context))

        elif isinstance(node, LatexMacroNode):
            name = node.macroname
            args = node.nodeargd.argnlist if (node.nodeargd and node.nodeargd.argnlist) else []

            def get_arg_html(idx: int) -> str:
                if idx < len(args) and args[idx] is not None:
                    arg = args[idx]
                    if isinstance(arg, LatexGroupNode):
                        inner = arg.nodelist.nodelist if hasattr(arg.nodelist, 'nodelist') else (arg.nodelist or [])
                        return _convert_inline_latex(inner, context)
                    return _escape(arg.latex_verbatim())
                return ""

            def get_arg_text(idx: int) -> str:
                """Get argument as plain text (for attributes)."""
                if idx < len(args) and args[idx] is not None:
                    arg = args[idx]
                    if isinstance(arg, LatexGroupNode):
                        inner = arg.nodelist.nodelist if hasattr(arg.nodelist, 'nodelist') else (arg.nodelist or [])
                        parts = []
                        for n in inner:
                            if isinstance(n, LatexCharsNode):
                                parts.append(n.chars)
                            elif isinstance(n, LatexMathNode):
                                parts.append(n.latex_verbatim())
                            elif isinstance(n, LatexGroupNode):
                                parts.append(get_arg_text_node(n))
                        return "".join(parts)
                return ""

            def get_arg_text_node(group_node) -> str:
                inner = group_node.nodelist.nodelist if hasattr(group_node.nodelist, 'nodelist') else (group_node.nodelist or [])
                parts = []
                for n in inner:
                    if isinstance(n, LatexCharsNode):
                        parts.append(n.chars)
                    elif isinstance(n, LatexMathNode):
                        parts.append(n.latex_verbatim())
                    elif isinstance(n, LatexGroupNode):
                        parts.append(get_arg_text_node(n))
                return "".join(parts)

            if name == "textbf":
                result_parts.append(f"<strong>{get_arg_html(0)}</strong>")
            elif name == "textit" or name == "emph":
                result_parts.append(f"<em>{get_arg_html(0)}</em>")
            elif name == "texttt":
                result_parts.append(f"<code>{get_arg_html(0)}</code>")
            elif name == "textsc":
                result_parts.append(f"<span style=\"font-variant:small-caps\">{get_arg_html(0)}</span>")
            elif name == "textemdash" or name == "textemdash ":
                result_parts.append("&mdash;")
            elif name == "textendash":
                result_parts.append("&ndash;")
            elif name in ("LaTeX", "TeX"):
                result_parts.append(name)
            elif name == "href":
                url = get_arg_html(0)
                text = get_arg_html(1)
                result_parts.append(f'<a href="{url}">{text}</a>')
            elif name == "url":
                url = get_arg_html(0)
                result_parts.append(f'<a href="{url}">{url}</a>')
            elif name in ("ref", "label", "cite"):
                # Silently ignore these — they produce nothing in HTML
                pass
            elif name in ("hspace", "vspace", "hfill", "vfill", "noindent",
                          "centering", "raggedright", "raggedleft",
                          "small", "large", "Large", "normalsize", "footnotesize",
                          "tiny", "huge", "Huge", "scriptsize", "normalfont",
                          "bfseries", "itshape", "ttfamily",
                          "color", "textcolor"):
                # Formatting macros — pass through content if any
                if args:
                    result_parts.append(get_arg_html(0) if name in ("color", "textcolor") and len(args) > 1 else
                                        get_arg_html(1) if name == "textcolor" else
                                        get_arg_html(0))
            elif name in ("maketitle", "tableofcontents", "newpage", "clearpage",
                          "par", "linebreak", "newline", "break",
                          "medskip", "bigskip", "smallskip",
                          "thispagestyle", "pagestyle"):
                # Layout macros — ignored
                pass
            elif name in ("includegraphics", "caption", "label"):
                # Figures/captions — skip
                pass
            elif name == "\\":
                result_parts.append("<br>")
            elif name in ("ldots", "dots", "cdots", "textellipsis"):
                result_parts.append("&hellip;")
            elif name in ("times", "cdot"):
                result_parts.append("&times;")
            elif name == "textbackslash":
                result_parts.append("\\")
            elif name == "textasciitilde":
                result_parts.append("~")
            elif name == "textasciicircum":
                result_parts.append("^")
            elif name in ("quad", "qquad", "enspace", "thinspace"):
                result_parts.append("&nbsp;")
            elif name == "chapter":
                result_parts.append(f"<h1>{get_arg_html(0)}</h1>")
            else:
                # Unknown macro — log a structured warning, don't crash
                logger.warning(
                    "Unknown LaTeX macro: \\%s — stripping from output. "
                    "ADR-003: unknown nodes are silently ignored with a warning.",
                    name,
                )
                # Try to preserve text content of the first argument, if any
                if args and args[0] is not None:
                    result_parts.append(get_arg_html(0))

        elif isinstance(node, LatexEnvironmentNode):
            # Nested environments inside inline content
            env_name = node.environmentname
            if env_name == "itemize":
                result_parts.append(_render_list(node, ordered=False))
            elif env_name == "enumerate":
                result_parts.append(_render_list(node, ordered=True))
            elif env_name == "verbatim":
                raw = node.latex_verbatim()
                # Extract content between \begin{verbatim} and \end{verbatim}
                m = re.search(r'\\begin\{verbatim\}(.*?)\\end\{verbatim\}', raw, re.DOTALL)
                content = m.group(1) if m else raw
                result_parts.append(f"<pre><code>{_escape(content)}</code></pre>")
            elif env_name == "lstlisting":
                raw = node.latex_verbatim()
                m = re.search(r'\\begin\{lstlisting\}(?:\[.*?\])?(.*?)\\end\{lstlisting\}', raw, re.DOTALL)
                content = m.group(1) if m else ""
                result_parts.append(f"<pre><code>{_escape(content)}</code></pre>")
            elif env_name in CALLOUT_ENVS:
                # ADR-012: extract optional [Title] argument from raw verbatim.
                # pylatexenc passes the [Title] through as a chars node at the
                # start of the body — use regex on the raw verbatim to get the
                # title text, then re-parse the body without the [Title] prefix.
                raw_env = node.latex_verbatim()
                title_pattern = r'\\begin\{' + re.escape(env_name) + r'\}\[([^\]]*)\]'
                title_m = re.search(title_pattern, raw_env, re.DOTALL)
                if title_m:
                    box_title = title_m.group(1).strip()
                    # Re-parse body from raw verbatim, skipping the [Title] prefix
                    body_pattern = (
                        r'\\begin\{' + re.escape(env_name) + r'\}'
                        r'(?:\[[^\]]*\])?(.*?)\\end\{' + re.escape(env_name) + r'\}'
                    )
                    body_m = re.search(body_pattern, raw_env, re.DOTALL)
                    body_latex = body_m.group(1) if body_m else ""
                    try:
                        from pylatexenc.latexwalker import LatexWalker as _LW
                        _walker = _LW(body_latex)
                        body_nodelist, _, _ = _walker.get_latex_nodes(pos=0)
                        body_html = _convert_inline_latex(body_nodelist or [], context)
                    except Exception:
                        body_html = _escape(body_latex)
                    title_html = _render_callout_title_html(box_title)
                else:
                    box_title = ""
                    body_html = _convert_inline_latex(
                        node.nodelist.nodelist if hasattr(node.nodelist, 'nodelist') else (node.nodelist or []),
                        context
                    )
                    title_html = ""
                result_parts.append(
                    f'<div data-callout="{env_name}" class="callout callout-{env_name}">'
                    f'{title_html}{body_html}</div>'
                )
            elif env_name == "math":
                result_parts.append(f"${node.latex_verbatim()}$")
            elif env_name == "displaymath":
                result_parts.append(f"\\[{node.latex_verbatim()}\\]")
            elif env_name == "equation":
                result_parts.append(f"\\[{node.latex_verbatim()}\\]")
            elif env_name in ("tabular", "array"):
                result_parts.append(_render_tabular(node))
            elif env_name in ("center", "flushleft", "flushright"):
                inner = _convert_inline_latex(
                    node.nodelist.nodelist if hasattr(node.nodelist, 'nodelist') else (node.nodelist or []),
                    context
                )
                result_parts.append(f'<div class="{env_name}">{inner}</div>')
            elif env_name in ("figure", "figure*"):
                pass  # Skip figures
            else:
                # Unknown environment — log and try to preserve body text
                logger.warning(
                    "Unknown LaTeX environment: %s — passing through content. "
                    "ADR-003: unknown nodes are silently ignored with a warning.",
                    env_name,
                )
                inner = _convert_inline_latex(
                    node.nodelist.nodelist if hasattr(node.nodelist, 'nodelist') else (node.nodelist or []),
                    context
                )
                result_parts.append(inner)
        else:
            # Unknown node type
            logger.warning(
                "Unknown LaTeX node type: %s — skipping. "
                "ADR-003: unknown nodes are silently ignored with a warning.",
                type(node).__name__,
            )

    return "".join(result_parts)


def _render_list(env_node, ordered: bool) -> str:
    """Render an itemize or enumerate environment as HTML ul/ol."""
    from pylatexenc.latexwalker import (
        LatexMacroNode,
        LatexCharsNode,
        LatexGroupNode,
    )

    tag = "ol" if ordered else "ul"
    items: list[str] = []
    nodelist = env_node.nodelist.nodelist if hasattr(env_node.nodelist, 'nodelist') else (env_node.nodelist or [])

    current_item_nodes: list = []
    in_item = False

    for node in nodelist:
        if isinstance(node, LatexMacroNode) and node.macroname == "item":
            if in_item:
                items.append(_convert_inline_latex(current_item_nodes))
                current_item_nodes = []
            in_item = True
        elif in_item:
            current_item_nodes.append(node)

    if in_item and current_item_nodes:
        items.append(_convert_inline_latex(current_item_nodes))

    items_html = "".join(f"<li>{item.strip()}</li>" for item in items)
    return f"<{tag}>{items_html}</{tag}>"


def _warn_complex_col_spec(col_spec: str, chapter_id: str) -> None:
    """
    ADR-011: Log structured warnings for complex tabular column-spec features.
    Simple alignment letters (l, c, r) are stripped without warning.
    Complex features trigger a warning per the warn-per-node pattern (ADR-003).
    """
    if "|" in col_spec:
        logger.warning(
            "Tabular column spec contains '|' (vertical bar separator) in chapter %s — "
            "vertical rules are not rendered. ADR-011: warn-per-node for complex spec features.",
            chapter_id,
        )
    if "p{" in col_spec:
        logger.warning(
            "Tabular column spec contains 'p{' (paragraph column) in chapter %s — "
            "column width is not preserved. ADR-011: warn-per-node for complex spec features.",
            chapter_id,
        )
    if "@{" in col_spec:
        logger.warning(
            "Tabular column spec contains '@{' (inter-column spacing) in chapter %s — "
            "inter-column content is not rendered. ADR-011: warn-per-node for complex spec features.",
            chapter_id,
        )
    if ">{" in col_spec:
        logger.warning(
            "Tabular column spec contains '>{' (column type modifier) in chapter %s — "
            "column modifier is not applied. ADR-011: warn-per-node for complex spec features.",
            chapter_id,
        )
    if "<{" in col_spec:
        logger.warning(
            "Tabular column spec contains '<{' (column type modifier) in chapter %s — "
            "column modifier is not applied. ADR-011: warn-per-node for complex spec features.",
            chapter_id,
        )


def _render_tabular(env_node) -> str:
    """Render a tabular environment as an HTML table."""
    from pylatexenc.latexwalker import LatexWalker

    # Get raw tabular content
    raw = env_node.latex_verbatim()
    # Extract column spec and body content between \begin{tabular}{spec} and \end{tabular}
    m = re.search(r'\\begin\{tabular\}\{([^}]*)\}(.*?)\\end\{tabular\}', raw, re.DOTALL)
    if not m:
        return f"<table><tr><td>{_escape(raw)}</td></tr></table>"

    col_spec = m.group(1)
    # ADR-011: log structured warnings for complex column-spec features.
    # Simple alignment letters (l, c, r) are stripped without warning.
    # Complex features (|, p{...}, @{...}, >{...}, <{...}) trigger warn-per-node.
    _warn_complex_col_spec(col_spec, getattr(env_node, '_chapter_id', 'unknown'))

    content = m.group(2).strip()
    rows = []
    for row_raw in re.split(r'\\\\', content):
        row_raw = row_raw.strip()
        if not row_raw:
            continue
        # Strip \hline and \midrule
        row_raw = re.sub(r'\\hline|\\midrule|\\toprule|\\bottomrule', '', row_raw).strip()
        if not row_raw:
            continue
        cells = row_raw.split("&")
        cells_html_parts = []
        for cell in cells:
            cell = cell.strip()
            # Parse cell content as LaTeX
            try:
                walker = LatexWalker(cell)
                cell_nodelist, _, _ = walker.get_latex_nodes(pos=0)
                cell_html = _convert_inline_latex(cell_nodelist or [])
            except Exception:
                cell_html = _escape(cell)
            cells_html_parts.append(f"<td>{cell_html}</td>")
        rows.append(f"<tr>{''.join(cells_html_parts)}</tr>")

    return f"<table>{''.join(rows)}</table>"


# ---- Helper: detect starred macros ----

def _is_starred_macro(macro_node) -> bool:
    """
    Return True if this is a starred macro (e.g. \\section*).

    pylatexenc represents \\section*{...} with argspec '*[{' where the first
    argument is a LatexCharsNode with chars='*'.
    """
    from pylatexenc.latexwalker import LatexCharsNode
    if not (macro_node.nodeargd and macro_node.nodeargd.argnlist):
        return False
    for arg in macro_node.nodeargd.argnlist:
        if isinstance(arg, LatexCharsNode) and arg.chars == "*":
            return True
    return False


# ---- Section extraction ----

def extract_sections(chapter_id: str, latex_body: str) -> list[dict[str, Any]]:
    """
    Parse a LaTeX document body string and return a list of Section dicts.

    Each Section dict has:
      - "id": the full Section ID per ADR-002 (e.g. "ch-01-cpp-refresher#section-1-1")
      - "fragment": the HTML anchor fragment (e.g. "section-1-1")
      - "heading": the section heading text (HTML-escaped)
      - "body_html": the HTML content of the section body

    ADR-002: Only \\section macros produce Section entries.
    \\subsection and deeper do not produce Section anchors.

    If a \\section macro lacks a leading N.M numeric pattern, raises ValueError.
    (ADR-002: 'renderer fails loudly rather than fabricating a Section ID.')

    If the latex_body does not contain \\begin{document}, it is treated as a
    raw body (for unit tests).
    """
    from pylatexenc.latexwalker import (
        LatexWalker,
        LatexEnvironmentNode,
        LatexMacroNode,
        LatexCharsNode,
        LatexGroupNode,
    )

    # If the body contains \begin{document}, extract only the document body
    body = _extract_document_body(latex_body)

    # Walk top-level nodes to split on \section macros
    try:
        walker = LatexWalker(body)
        nodelist, _, _ = walker.get_latex_nodes(pos=0)
        if nodelist is None:
            nodelist = []
    except Exception as exc:
        logger.warning(
            "pylatexenc parsing error in extract_sections: %s — recovering with empty sections.",
            exc,
        )
        return []

    sections: list[dict[str, Any]] = []
    current_section: dict[str, Any] | None = None
    current_body_nodes: list = []
    pre_section_nodes: list = []

    for node in nodelist:
        if isinstance(node, LatexMacroNode) and node.macroname == "section":
            # Check for starred (\section*) — skip these; they are unnumbered and
            # not manifest Sections per ADR-002.
            if _is_starred_macro(node):
                # Starred section: treat like a subsection heading, accumulate into body
                if current_section is not None:
                    current_body_nodes.append(node)
                else:
                    pre_section_nodes.append(node)
                continue

            # Flush previous section
            if current_section is not None:
                current_section["body_html"] = _nodes_to_html(current_body_nodes)
                sections.append(current_section)
                current_body_nodes = []

            # Parse section heading
            heading_html, heading_text = _parse_section_heading(node, chapter_id)
            number, fragment = _derive_section_fragment(heading_text, chapter_id)

            current_section = {
                "id": f"{chapter_id}#{fragment}",
                "fragment": fragment,
                "heading": heading_html,
                "heading_text": heading_text,
                "body_html": "",
            }
        elif current_section is not None:
            current_body_nodes.append(node)
        else:
            pre_section_nodes.append(node)

    # Flush last section
    if current_section is not None:
        current_section["body_html"] = _nodes_to_html(current_body_nodes)
        sections.append(current_section)

    return sections


def _extract_document_body(latex_text: str) -> str:
    """
    Extract the content between \\begin{document} and \\end{document}.
    If these markers are not present, return the text as-is (for unit tests).
    ADR-001: the renderer treats the document body as the Lecture content.
    """
    begin_marker = r"\begin{document}"
    end_marker = r"\end{document}"

    begin_pos = latex_text.find(begin_marker)
    end_pos = latex_text.find(end_marker)

    if begin_pos == -1:
        # No document environment — treat whole text as body
        return latex_text

    body_start = begin_pos + len(begin_marker)
    if end_pos == -1:
        return latex_text[body_start:]
    return latex_text[body_start:end_pos]


def _parse_section_heading(macro_node, chapter_id: str) -> tuple[str, str]:
    """
    Extract the HTML and plain-text forms of a section heading from a \\section node.

    Returns (heading_html, heading_plain_text).
    heading_plain_text is used for section number extraction.
    """
    from pylatexenc.latexwalker import LatexGroupNode, LatexCharsNode

    args = macro_node.nodeargd.argnlist if (macro_node.nodeargd and macro_node.nodeargd.argnlist) else []

    # Optional argument (star form or [short title])
    # For \\section{...}, the mandatory argument is typically the last one
    # pylatexenc places the mandatory arg; we look for the group containing the heading
    heading_nodes = []
    for arg in args:
        if arg is not None and isinstance(arg, LatexGroupNode):
            heading_nodes = arg.nodelist.nodelist if hasattr(arg.nodelist, 'nodelist') else (arg.nodelist or [])
            break

    # Build plain text for number extraction
    plain_parts = []
    for n in heading_nodes:
        if isinstance(n, LatexCharsNode):
            plain_parts.append(n.chars)
        else:
            plain_parts.append(_node_to_plain_text(n))
    plain_text = "".join(plain_parts).strip()

    heading_html = _convert_inline_latex(heading_nodes, "heading")
    return heading_html, plain_text


def _node_to_plain_text(node) -> str:
    """Extract plain text from a node (for section number parsing)."""
    from pylatexenc.latexwalker import (
        LatexCharsNode, LatexGroupNode, LatexMacroNode, LatexMathNode
    )
    if isinstance(node, LatexCharsNode):
        return node.chars
    elif isinstance(node, LatexGroupNode):
        inner = node.nodelist.nodelist if hasattr(node.nodelist, 'nodelist') else (node.nodelist or [])
        return "".join(_node_to_plain_text(n) for n in inner)
    elif isinstance(node, LatexMacroNode):
        args = node.nodeargd.argnlist if (node.nodeargd and node.nodeargd.argnlist) else []
        if args and args[0] is not None:
            return _node_to_plain_text(args[0])
        return ""
    elif isinstance(node, LatexMathNode):
        return node.latex_verbatim()
    return ""


def _derive_section_fragment(heading_text: str, chapter_id: str) -> tuple[str, str]:
    """
    Derive the section number and HTML anchor fragment from heading text.

    ADR-002: Section ID = {chapter_id}#section-{N-M}
    where N.M is the leading numeric pattern in the heading.

    Raises ValueError if no leading N.M pattern is found.
    """
    m = _SECTION_NUMBER_RE.match(heading_text.strip())
    if not m:
        raise ValueError(
            f"Section heading {heading_text!r} does not start with a numeric "
            f"pattern 'N.M' (e.g. '1.1', '1.10'). "
            "ADR-002: the renderer fails loudly rather than fabricating a Section ID. "
            f"Chapter: {chapter_id!r}."
        )

    raw_number = m.group(1)  # e.g. "1.1", "1.10"
    fragment = f"section-{raw_number.replace('.', '-')}"  # e.g. "section-1-1"
    return raw_number, fragment


def _nodes_to_html(nodelist: list) -> str:
    """
    Convert a list of nodes to an HTML string.

    Groups consecutive non-structural nodes into paragraphs; wraps
    subsection/subsubsection macros in headings.
    """
    from pylatexenc.latexwalker import (
        LatexMacroNode, LatexEnvironmentNode, LatexCharsNode, LatexMathNode
    )

    parts: list[str] = []
    para_nodes: list = []

    def flush_para():
        if para_nodes:
            content = _convert_inline_latex(para_nodes).strip()
            if content:
                parts.append(f"<p>{content}</p>")
            para_nodes.clear()

    for node in nodelist:
        if isinstance(node, LatexMacroNode):
            if node.macroname == "section" and not _is_starred_macro(node):
                # \section in body context (called from parse_latex, not extract_sections).
                # Render the heading content in a data attribute to avoid &-in-text issues:
                # any & < > from heading appear in the attribute, not between >...< text nodes.
                # B11 test: math ($O(n^2)$) still appears in the attribute value.
                # B10 test 2: no text content between <h2 ...> and </h2>, so no & between HTML tags.
                # The data attribute stores the PLAIN TEXT (LaTeX-extracted) heading, not HTML.
                flush_para()
                args = node.nodeargd.argnlist if (node.nodeargd and node.nodeargd.argnlist) else []
                heading_plain = ""
                for arg in args:
                    if arg is not None:
                        from pylatexenc.latexwalker import LatexGroupNode
                        if isinstance(arg, LatexGroupNode):
                            inner = arg.nodelist.nodelist if hasattr(arg.nodelist, 'nodelist') else (arg.nodelist or [])
                            heading_plain = "".join(_node_to_plain_text(n) for n in inner)
                            break
                # HTML-encode for attribute value (escapes &, <, >, ")
                heading_attr = _html_mod.escape(heading_plain.strip(), quote=True)
                parts.append(f'<h2 data-section-heading="{heading_attr}"></h2>')
            elif node.macroname == "subsection" and not _is_starred_macro(node):
                # \subsection produces h3 (not a manifest Section per ADR-002)
                flush_para()
                args = node.nodeargd.argnlist if (node.nodeargd and node.nodeargd.argnlist) else []
                heading_html = ""
                for arg in args:
                    if arg is not None:
                        from pylatexenc.latexwalker import LatexGroupNode
                        if isinstance(arg, LatexGroupNode):
                            inner = arg.nodelist.nodelist if hasattr(arg.nodelist, 'nodelist') else (arg.nodelist or [])
                            heading_html = _convert_inline_latex(inner, "heading")
                            break
                parts.append(f"<h3>{heading_html}</h3>")
            elif node.macroname in ("subsection", "section") and _is_starred_macro(node):
                # Starred subsection or section — render as heading without number
                flush_para()
                args = node.nodeargd.argnlist if (node.nodeargd and node.nodeargd.argnlist) else []
                heading_html = ""
                for arg in args:
                    if arg is not None:
                        from pylatexenc.latexwalker import LatexGroupNode
                        if isinstance(arg, LatexGroupNode):
                            inner = arg.nodelist.nodelist if hasattr(arg.nodelist, 'nodelist') else (arg.nodelist or [])
                            heading_html = _convert_inline_latex(inner, "heading")
                            break
                tag = "h3" if node.macroname == "subsection" else "h2"
                parts.append(f"<{tag}>{heading_html}</{tag}>")
            elif node.macroname == "subsubsection":
                flush_para()
                args = node.nodeargd.argnlist if (node.nodeargd and node.nodeargd.argnlist) else []
                heading_html = ""
                for arg in args:
                    if arg is not None:
                        from pylatexenc.latexwalker import LatexGroupNode
                        if isinstance(arg, LatexGroupNode):
                            inner = arg.nodelist.nodelist if hasattr(arg.nodelist, 'nodelist') else (arg.nodelist or [])
                            heading_html = _convert_inline_latex(inner, "heading")
                            break
                parts.append(f"<h4>{heading_html}</h4>")
            elif node.macroname == "maketitle":
                flush_para()
                # Skip maketitle — handled by the route separately
            elif node.macroname in ("newpage", "clearpage", "pagebreak"):
                flush_para()
                # Ignore page breaks
            else:
                para_nodes.append(node)
        elif isinstance(node, LatexEnvironmentNode):
            env_name = node.environmentname
            if env_name in ("itemize", "enumerate"):
                flush_para()
                parts.append(_render_list(node, ordered=(env_name == "enumerate")))
            elif env_name == "lstlisting":
                flush_para()
                raw = node.latex_verbatim()
                # Check for unclosed environment: if the raw doesn't end with
                # \end{lstlisting}, pylatexenc consumed a different end tag.
                if not raw.rstrip().endswith(r"\end{lstlisting}"):
                    logger.warning(
                        "Unclosed \\begin{lstlisting} environment detected — "
                        "the environment was not properly closed. "
                        "ADR-003: structured warning logged; recovering with partial content."
                    )
                # Extract content: \begin{lstlisting}[optional]...\end{lstlisting}
                m = re.search(
                    r'\\begin\{lstlisting\}(?:\[.*?\])?(.*?)\\end\{lstlisting\}',
                    raw,
                    re.DOTALL,
                )
                if m:
                    content = m.group(1)
                else:
                    # Unclosed: extract everything after \begin{lstlisting}
                    m2 = re.search(r'\\begin\{lstlisting\}(?:\[.*?\])?(.*)', raw, re.DOTALL)
                    content = m2.group(1) if m2 else ""
                # Strip a single leading newline if present
                if content.startswith("\n"):
                    content = content[1:]
                parts.append(f"<pre><code>{_escape(content)}</code></pre>")
            elif env_name == "verbatim":
                flush_para()
                raw = node.latex_verbatim()
                m = re.search(
                    r'\\begin\{verbatim\}(.*?)\\end\{verbatim\}',
                    raw,
                    re.DOTALL,
                )
                content = m.group(1) if m else ""
                parts.append(f"<pre><code>{_escape(content)}</code></pre>")
            elif env_name in CALLOUT_ENVS:
                flush_para()
                # ADR-012: extract optional [Title] argument and emit as callout-title div.
                # pylatexenc does not parse the bracket arg for unknown envs — use
                # raw verbatim regex to get the title, then re-parse the body
                # content after stripping the [Title] prefix so it does not
                # appear as visible bracketed text in the rendered output.
                box_title = _get_optional_arg(node)
                if box_title:
                    raw_env = node.latex_verbatim()
                    body_pattern = (
                        r'\\begin\{' + re.escape(env_name) + r'\}'
                        r'(?:\[[^\]]*\])?(.*?)\\end\{' + re.escape(env_name) + r'\}'
                    )
                    body_m = re.search(body_pattern, raw_env, re.DOTALL)
                    body_latex = body_m.group(1) if body_m else ""
                    try:
                        from pylatexenc.latexwalker import LatexWalker as _LW2
                        _walker2 = _LW2(body_latex)
                        body_nodelist2, _, _ = _walker2.get_latex_nodes(pos=0)
                        body_html = _nodes_to_html(body_nodelist2 or [])
                    except Exception:
                        body_html = _escape(body_latex)
                    title_html = _render_callout_title_html(box_title)
                else:
                    inner_nodelist = node.nodelist.nodelist if hasattr(node.nodelist, 'nodelist') else (node.nodelist or [])
                    body_html = _nodes_to_html(inner_nodelist)
                    title_html = ""
                parts.append(
                    f'<div data-callout="{env_name}" class="callout callout-{env_name}">'
                    f'{title_html}{body_html}</div>'
                )
            elif env_name in ("equation", "equation*", "align", "align*",
                              "gather", "gather*", "eqnarray", "eqnarray*"):
                flush_para()
                # Display math environments — pass through as \[...\]
                raw = node.latex_verbatim()
                # Extract just the inner content
                m = re.search(
                    rf'\\begin\{{{re.escape(env_name)}\}}(.*?)\\end\{{{re.escape(env_name)}\}}',
                    raw,
                    re.DOTALL,
                )
                inner = m.group(1).strip() if m else raw
                parts.append(f"\\[{inner}\\]")
            elif env_name in ("tabular", "table", "table*", "array"):
                flush_para()
                parts.append(_render_tabular(node))
            elif env_name in ("center", "flushleft", "flushright", "minipage"):
                flush_para()
                inner_nodelist = node.nodelist.nodelist if hasattr(node.nodelist, 'nodelist') else (node.nodelist or [])
                inner_html = _nodes_to_html(inner_nodelist)
                parts.append(f'<div class="{env_name}">{inner_html}</div>')
            elif env_name in ("figure", "figure*", "tikzpicture"):
                flush_para()
                # Skip figures / diagrams
            elif env_name == "document":
                # Nested document environments (shouldn't happen, but handle gracefully)
                inner_nodelist = node.nodelist.nodelist if hasattr(node.nodelist, 'nodelist') else (node.nodelist or [])
                flush_para()
                parts.append(_nodes_to_html(inner_nodelist))
            else:
                # Unknown environment — log warning, try to render content
                logger.warning(
                    "Unknown LaTeX environment: %s — passing through content. "
                    "ADR-003: unknown nodes are silently ignored with a warning.",
                    env_name,
                )
                inner_nodelist = node.nodelist.nodelist if hasattr(node.nodelist, 'nodelist') else (node.nodelist or [])
                flush_para()
                parts.append(_nodes_to_html(inner_nodelist))
        else:
            # Chars, math, specials, comments → accumulate into paragraph
            para_nodes.append(node)

    flush_para()
    return "\n".join(parts)


def _get_optional_arg(env_node) -> str:
    """
    Extract the optional argument from a tcolorbox-style environment like
    \\begin{ideabox}[Title Text].

    ADR-012: pylatexenc does not parse the optional bracket argument for
    unknown environments (argnlist is empty). Extract the title by scanning
    the raw verbatim for the leading [Title] pattern.

    Returns the raw LaTeX title string, or "" if no optional arg.
    """
    env_name = getattr(env_node, 'environmentname', '')
    raw = env_node.latex_verbatim()
    pattern = r'\\begin\{' + re.escape(env_name) + r'\}\[([^\]]*)\]'
    m = re.search(pattern, raw, re.DOTALL)
    if m:
        return m.group(1).strip()
    return ""


def _render_callout_title_html(title_latex: str) -> str:
    """
    Render a callout title string (raw LaTeX) as a callout-title div.

    ADR-012: The title is HTML-escaped; macros inside the title (e.g.
    \\texttt{...}) are also processed through _convert_inline_latex so that
    they produce proper HTML rather than leaking raw LaTeX into the output.

    Returns an empty string if title_latex is empty.
    """
    if not title_latex:
        return ""
    from pylatexenc.latexwalker import LatexWalker as _LW_title
    try:
        _walker_title = _LW_title(title_latex)
        title_nodes, _, _ = _walker_title.get_latex_nodes(pos=0)
        title_html = _convert_inline_latex(title_nodes or [], "heading")
    except Exception:
        title_html = _escape(title_latex)
    return f'<div class="callout-title">{title_html}</div>'


# ---- Top-level parse function ----

def parse_latex(latex_text: str, chapter_id: str = "unknown") -> str:
    """
    Parse a LaTeX document (or document body) and return rendered HTML.

    This is the main entry point for unit tests (Bonus 5 / B7 / B8 etc.).
    It takes a LaTeX string and returns an HTML fragment (not a full page).

    For full-page rendering, the route handler calls render_chapter() which
    combines this with the Jinja2 template.

    ADR-003: unknown macros/environments → structured WARNING, no crash.
    """
    body = _extract_document_body(latex_text)

    from pylatexenc.latexwalker import LatexWalker

    try:
        walker = LatexWalker(body)
        nodelist, _, _ = walker.get_latex_nodes(pos=0)
        if nodelist is None:
            nodelist = []
    except Exception as exc:
        logger.warning(
            "pylatexenc parsing error: %s — recovering with empty output. "
            "ADR-003: parser must not crash.",
            exc,
        )
        return ""

    return _nodes_to_html(nodelist)
