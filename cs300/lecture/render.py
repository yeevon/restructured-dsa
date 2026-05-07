"""
Chapter -> HTML renderer.

Per ADR-003: consumes the Chapter/Section/Block model; does not re-walk plasTeX.
Per ADR-004: PassthroughBlock renders as a visible, marked block.
Per ADR-005: Section wrappers carry id="section-{slug}" and data-designation.
"""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .models import (
    Block,
    Chapter,
    CodeBlock,
    EmphasisInline,
    EquationBlock,
    HeadingBlock,
    Inline,
    LinkInline,
    ListBlock,
    MathInline,
    CodeInline,
    ParagraphBlock,
    PassthroughBlock,
    Section,
    TextInline,
)

_TEMPLATES_DIR = Path(__file__).parent.parent / "templates"


def _get_jinja_env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATES_DIR)),
        autoescape=select_autoescape(["html"]),
    )
    return env


def render_inline(inline: Inline) -> str:
    """Render a single Inline node to an HTML string."""
    if isinstance(inline, TextInline):
        from markupsafe import escape

        return str(escape(inline.text))
    if isinstance(inline, MathInline):
        from markupsafe import escape

        return f"<span class='math-inline'>\\({escape(inline.latex)}\\)</span>"
    if isinstance(inline, EmphasisInline):
        tag = "strong" if inline.strong else "em"
        inner = "".join(render_inline(i) for i in inline.inlines)
        return f"<{tag}>{inner}</{tag}>"
    if isinstance(inline, CodeInline):
        from markupsafe import escape

        return f"<code>{escape(inline.source)}</code>"
    if isinstance(inline, LinkInline):
        from markupsafe import escape

        inner = "".join(render_inline(i) for i in inline.inlines)
        return f'<a href="{escape(inline.target)}">{inner}</a>'
    # Fallback
    return ""


def render_block(block: Block) -> str:
    """Render a single Block node to an HTML string."""
    if isinstance(block, ParagraphBlock):
        inner = "".join(render_inline(i) for i in block.inlines)
        return f"<p>{inner}</p>"
    if isinstance(block, HeadingBlock):
        tag = f"h{block.level}"
        inner = "".join(render_inline(i) for i in block.inlines)
        return f"<{tag}>{inner}</{tag}>"
    if isinstance(block, CodeBlock):
        from markupsafe import escape

        lang_attr = (
            f' data-language="{escape(block.language)}"' if block.language else ""
        )
        return f"<pre{lang_attr}><code>{escape(block.source)}</code></pre>"
    if isinstance(block, EquationBlock):
        from markupsafe import escape

        if block.display:
            return f"<div class='math-display'>\\[{escape(block.latex)}\\]</div>"
        return f"<span class='math-inline'>\\({escape(block.latex)}\\)</span>"
    if isinstance(block, PassthroughBlock):
        from markupsafe import escape

        env_name = escape(block.environment)
        raw = escape(block.raw_latex)
        return (
            f'<div class="lecture-passthrough" data-environment="{env_name}">'
            f'<p class="lecture-passthrough-label">[unrendered LaTeX: {env_name}]</p>'
            f'<pre class="lecture-passthrough-source"><code>{raw}</code></pre>'
            f"</div>"
        )
    if isinstance(block, ListBlock):
        tag = "ol" if block.ordered else "ul"
        items_html = ""
        for item_blocks in block.items:
            item_content = "".join(render_block(b) for b in item_blocks)
            items_html += f"<li>{item_content}</li>"
        return f"<{tag}>{items_html}</{tag}>"
    return ""


def render_section(section: Section, designation: str) -> str:
    """Render a Section to an HTML string with proper anchor and designation."""
    slug = section.id.split("#")[1] if "#" in section.id else section.id
    blocks_html = "".join(render_block(b) for b in section.blocks)
    from markupsafe import escape

    title_escaped = escape(section.title)
    return (
        f'<section id="section-{slug}" data-designation="{designation}">'
        f"<h2>{title_escaped}</h2>"
        f"{blocks_html}"
        f"</section>"
    )


def render_html(chapter: Chapter) -> str:
    """Render a full Chapter to an HTML page string."""
    env = _get_jinja_env()
    template = env.get_template("lecture.html")
    return template.render(
        chapter=chapter,
        render_section=render_section,
        render_block=render_block,
        render_inline=render_inline,
    )
