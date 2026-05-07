# ADR-003: Lecture parser produces an intermediate Chapter / Section model that both the HTML renderer and the future Script extractor consume

**Status:** Accepted
**Date:** 2026-05-07
**Task:** TASK-001

## Context
The manifest is explicit (§6 hard constraint): "Lecture Scripts are extracted from LaTeX, never from rendered HTML. … The Lecture Page (HTML) and the Lecture Script are sibling outputs of the same source; neither derives from the other." The Lecture Page is in-scope for TASK-001. The Lecture Script is out-of-scope for TASK-001. The decision now is the *shape* of the parser's output — because if the Lecture Page renderer consumes a "blob of HTML per Section" as the parser output, the Script extractor (a later task) is forced to either re-parse from LaTeX (acceptable but wasteful) or scrape from HTML (forbidden by §6).

The right shape is a structured intermediate model that retains semantic structure (headings, paragraphs, equations, code blocks, lists, etc.) without committing to an output format. Each downstream renderer (HTML for the Page, prose-for-TTS for the Script) consumes the same intermediate.

## Decision

The parser in `cs300/lecture/` is a pure function `parse_chapter(tex_path: Path) -> Chapter`. The returned `Chapter` is a Pydantic model:

```
Chapter:
  id: str                                    # "ch-01-<slug>", from filename (ADR-001)
  title: str                                 # plain text from \title{...} or first \section{...} fallback
  designation: Literal["mandatory","optional"]  # from designation_for_chapter_id (TASK-001)
  sections: list[Section]

Section:
  id: str                                    # "<chapter_id>#<section-slug>" (ADR-002)
  title: str                                 # plain text of the \section{...} heading
  blocks: list[Block]                        # the structured body (see below)

Block:  # tagged union; Pydantic discriminator on `kind`
  - ParagraphBlock(kind="paragraph", inlines: list[Inline])
  - HeadingBlock(kind="heading", level: int, inlines: list[Inline])   # subsection / subsubsection
  - ListBlock(kind="list", ordered: bool, items: list[list[Block]])
  - CodeBlock(kind="code", language: str | None, source: str)
  - EquationBlock(kind="equation", display: bool, latex: str)         # raw LaTeX preserved verbatim
  - PassthroughBlock(kind="passthrough", environment: str, raw_latex: str)  # see ADR-004
  # additional Block kinds added by later ADRs as the curriculum needs them

Inline:  # tagged union; smaller alphabet
  - TextInline(kind="text", text: str)
  - EmphasisInline(kind="emphasis", strong: bool, inlines: list[Inline])
  - CodeInline(kind="code", source: str)
  - MathInline(kind="math", latex: str)                                # $...$
  - LinkInline(kind="link", target: str, inlines: list[Inline])
```

The HTML renderer (in scope for TASK-001) is a `render_html(chapter: Chapter) -> str` function that walks this model and emits a Jinja2-templated HTML page. It consumes the model; it does not re-walk the plasTeX tree.

The future Script extractor (out of scope) will be a sibling `render_script(chapter: Chapter) -> str` that walks the same model. Both renderers depend on `Chapter`; neither depends on the other; neither re-parses LaTeX.

The parser uses plasTeX as the LaTeX-tokenization layer. plasTeX's own DOM is treated as parser-internal; it does not leak into the `Chapter` model. This isolates the rest of the codebase from plasTeX-specific types and lets the parser be replaced if plasTeX hits a wall (unlikely, but the decoupling is cheap).

The set of `Block` and `Inline` variants enumerated above is the v1 alphabet for TASK-001's seeded Chapter 1. Adding a new variant is a small ADR (or noted in `architecture.md` if trivial) — not a refactor.

## Alternatives considered
- **Parser emits HTML strings per Section.** Rejected: violates the manifest's "sibling outputs" constraint by forcing a future Script extractor to either re-parse or scrape HTML. The whole reason the constraint exists is to prevent exactly this shape.
- **Parser emits raw plasTeX DOM nodes; renderer walks them.** Rejected: plasTeX-specific types leak into `cs300/lecture/`, the test suite, and any future code that touches the model. Couples the project to a library it should be free to replace.
- **Parser emits a string of Markdown per Section, both renderers consume Markdown.** Rejected: Markdown is a lossy intermediate (loses LaTeX equation semantics, loses code-block language metadata in some flavors, no clean way to carry the `passthrough` block). The point of an intermediate is to preserve structure, not to flatten it twice.
- **Skip the intermediate; render HTML directly now and "deal with the Script later."** Rejected: §6 forbids deriving the Script from HTML and it would be expensive to re-architect the parser when the audio task comes in. Designing the model now, with a single concrete renderer, is cheap; retrofitting is not.

## Consequences
- TASK-001's parser test surface tests `parse_chapter(...)` returning the right `Chapter` shape — independent of FastAPI and independent of HTML output. Satisfies the task's "Test seam for the LaTeX pipeline" item without making it a separate ADR.
- The HTML renderer is a thin walker over the model. Jinja2 templates render `Chapter` and `Section` and dispatch on `Block.kind` and `Inline.kind`.
- A new LaTeX environment that the curriculum starts using will require either a new `Block` variant (if it's structural) or fall through to `PassthroughBlock` (per ADR-004). Either way, the plasTeX-internal handling is isolated to one file.
- The `latex` field on `EquationBlock` / `MathInline` is a verbatim slice of the LaTeX source. The HTML renderer can pipe it through MathJax / KaTeX at render time (or the HTML page can load MathJax client-side). The future Script extractor can choose to read equations as "Equation block omitted" or to TTS-paraphrase them — that's a Script-task decision, not this task's.
- Public surface: `parse_chapter`, `render_html`, and the `Chapter` / `Section` / `Block` / `Inline` types are the only exports from `cs300.lecture` that other modules touch.

## Manifest conformance
- §6 "Lecture Scripts are extracted from LaTeX, never from rendered HTML": satisfied by design — both renderers consume the LaTeX-derived model, not each other's output.
- §7 "Derived artifacts remain structurally aligned to source": the model preserves Section order and structure; both renderers produce artifacts aligned to the same Sections.
- §6 "LaTeX is the source of truth": the parser is the single read-path from LaTeX into the rest of the system.
