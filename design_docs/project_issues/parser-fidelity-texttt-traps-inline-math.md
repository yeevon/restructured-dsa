# `\texttt{...$...$...}` traps inline math from MathJax (renders `$...$` literally)

**Status:** Open
**Surfaced:** 2026-05-09 (TASK-005 human screenshot review — "Picture the list", "Picture of the interior splice" callouts in ch-04; orchestrator Run 008 corpus-wide categorization)
**Decide when:** as part of TASK-007 candidate. High visible-bug surface — every typewriter-fonted ASCII-art-with-math illustration in the corpus is broken.

## Question

The corpus uses `\texttt{...}` to render typewriter-fonted text that frequently embeds inline math: `\texttt{head $\to$ [7 | $\bullet$] $\to$ [9 | $\bullet$] $\to$ [5 | null]}`. The current parser maps `\texttt{...}` to `<code>...</code>` and the rendered HTML preserves the inline `$...$` tokens inside that `<code>` element.

MathJax v3's default `skipHtmlTags` includes `code`, `pre`, `script`, `noscript`, `style`, `textarea`, `annotation`, and `annotation-xml` — meaning MathJax intentionally does **not** process inline math inside `<code>`. So `$\to$`, `$\bullet$`, `$\leftarrow$`, `$\nwarrow$`, etc., render as literal text strings, not as math glyphs.

The user-visible effect: every ASCII-art "node diagram" callout in ch-04 (and similar uses across other Chapters) shows raw LaTeX source instead of arrows and bullets.

**Corpus-wide count:**
- ~42 instances of inline math directly inside `<code>` (matches `<code>...$...$...</code>`), concentrated in ch-04 (39).
- ~119 additional `$...$` tokens inside callout bodies (across most Chapters).
- ~314 raw `\to` / `\bullet` / `\leftarrow` / `\rightarrow` / `\nwarrow` / `\searrow` / `\uparrow` / `\downarrow` tokens, mostly inside the same `\texttt{}`-as-`<code>` contexts (ch-04: 127, ch-10: 95).

Total visibly-broken render sites: order of 200+ across the corpus.

## Options known

- **Option 1: Render `\texttt{}` as `<span class="texttt">` instead of `<code>`.** MathJax processes `<span>`. CSS `.texttt { font-family: monospace; }` recovers the typewriter appearance. Bounded change; one parser handler. Aligns with the user's editorial intent (math should render inside typewriter-fonted illustrations).
- **Option 2: Pre-process inline math inside `\texttt{}` arguments before emitting the `<code>` wrapper.** Walk the texttt argument node; convert each `$...$` to a `<span class="math">...</span>` (or whatever shape MathJax v3 doesn't skip); emit `<code>...</code>` with the spans as children. MathJax does process `<span>` even inside `<code>` if the span has the right shape — needs verification. More fragile than Option 1.
- **Option 3: Configure MathJax to remove `code` from `skipHtmlTags`.** Affects every `<code>` in the corpus — including pure code blocks where `$` is meant to be a literal shell prompt or C++ string. Forbidden direction.
- **Option 4: Author-side workaround — replace `$\to$` with literal Unicode `→` in source.** Contradicts manifest §5 (no in-app authoring) only weakly (the source is human-authored, but the author would have to remember this rule). Brittle and editorially awkward; the LaTeX source is the canonical input.

## Constraints

- ADR-003 (Accepted) commits to pylatexenc + custom environment handlers. The `\texttt{}` mapping is a handler-level decision; either option 1 or option 2 stays inside ADR-003's strategy.
- Manifest §3 (drive consumption): the rendered surface must convey the editorial intent. Raw LaTeX is not consumption-grade.
- ADR-008 (CSS layering): a `.texttt` rule belongs in `lecture.css` (Lecture-body content styling).
- No prior ADR governs `\texttt{}` rendering — this category needs a new Proposed ADR.

## Why this is filed as a project_issue

ADR-015 amended bug-class partition routes class-1 to in-scope fold-in under new Proposed ADRs. The TASK-005 validation pass surfaced this category at corpus scale (~200+ visible defects). Per the human's gate decision (orchestrator Run 008), the category ships as a project_issue and a focused follow-up task (TASK-007 candidate) drafts the new ADR.

## Resolution

When resolved, mark this issue `Resolved by ADR-NNN`.
