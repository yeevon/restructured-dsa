# ADR-018: Render `\texttt{}` as `<span class="texttt">` so MathJax processes embedded inline math

**Status:** `Accepted`
**Date:** 2026-05-09
**Task:** TASK-007
**Accepted:** 2026-05-09 (human gate; accepted as written — `<span class="texttt">` element choice with CSS reproducing existing inline-code look; recorded in TASK-007 audit Run 003)
**Resolves:** `design_docs/project_issues/parser-fidelity-texttt-traps-inline-math.md`
**Supersedes:** none

## Context

The corpus uses `\texttt{...}` to render typewriter-fonted text that frequently embeds inline math — most prominently in ch-04's "Picture the list" / "Picture of the interior splice" callouts:

```
\texttt{head $\to$ [7 | $\bullet$] $\to$ [9 | $\bullet$] $\to$ [5 | null]}
```

The current parser (`app/parser.py:147–148`) maps `\texttt{}` to `<code>...</code>`:

```python
elif name == "texttt":
    result_parts.append(f"<code>{get_arg_html(0)}</code>")
```

`get_arg_html` recurses through the texttt argument's nodelist, and `LatexMathNode` instances are passed through verbatim (line 83 — `node.latex_verbatim()`), so the rendered HTML preserves `$\to$` literally inside the `<code>` element.

MathJax v3's default `skipHtmlTags` set includes `code`, `pre`, `script`, `noscript`, `style`, `textarea`, `annotation`, and `annotation-xml`. The project's MathJax loader (`app/templates/base.html.j2:9–18`) does **not** override `skipHtmlTags`, so MathJax intentionally does not process inline math inside `<code>`. The user-visible result is that `$\to$`, `$\bullet$`, `$\leftarrow$`, `$\nwarrow$`, `$\searrow$` etc. render as literal `$\to$` text instead of math glyphs (→, •, ←).

The TASK-005 corpus-wide validation pass (orchestrator Run 008) catalogued the corpus impact:

- ~42 instances of inline math directly inside `<code>` (`<code>...$...$...</code>`), concentrated in ch-04 (39 of 42).
- ~119 additional `$...$` tokens inside callout bodies (across most Chapters).
- ~314 raw `\to` / `\bullet` / `\leftarrow` / `\rightarrow` / `\nwarrow` / `\searrow` / `\uparrow` / `\downarrow` tokens, mostly inside the same `\texttt{}`-as-`<code>` contexts (ch-04: 127, ch-10: 95).
- **Total visibly-broken render sites: order of 200+** across the corpus.

No existing ADR governs `\texttt{}` rendering. ADR-003 (rendering pipeline) commits the project to "pylatexenc + custom environment/macro handlers" but is silent on the specific HTML element `\texttt{}` produces. ADR-008 (CSS layering) commits Lecture-body styling to `app/static/lecture.css`. ADR-012 (callout title rendering) is the sibling-shape precedent for "parser handler change + matching CSS rule in `lecture.css`."

This decision is forced now because TASK-007's acceptance criteria require that inline math inside `\texttt{}` renders as math glyphs, and that the typewriter font is preserved visually.

The corpus's editorial intent is unambiguous: the human-author wrote `\texttt{$\to$}` *because* they wanted typewriter-fonted text with math-rendered arrows inside. Stripping the math, escaping the dollars, or asking the author to use Unicode arrows in source all contradict that intent.

## Decision

The parser handler for `\texttt{}` (in `_convert_inline_latex`, `app/parser.py:147–148`) emits **`<span class="texttt">...</span>`** instead of `<code>...</code>`. The argument's contents continue to be processed by `_convert_inline_latex` recursively, which already passes `LatexMathNode` instances through verbatim — so `$\to$` inside the texttt argument flows out as `$\to$` inside the `<span class="texttt">`, and MathJax processes it normally because `<span>` is not in MathJax's default `skipHtmlTags` set.

A new CSS rule lands in `app/static/lecture.css` (per ADR-008's Lecture-body content-styling scope):

```css
.texttt {
  font-family: 'Courier New', Courier, monospace;
  background: #f3ede2;
  padding: 0.1em 0.3em;
  border-radius: 2px;
  font-size: 0.9em;
}
```

The visual properties (background, padding, border-radius, font-size) reproduce the existing `p code` styling (`lecture.css:128–133`) so the rendered appearance of inline `\texttt{}` content is unchanged for the cases that did **not** contain math. The `font-family` reproduces the existing bare `code` rule (`lecture.css:124–126`). Readers see the same typewriter-fonted inline appearance they saw before, plus correctly-rendered math glyphs where math is embedded.

The `<code>` element is reserved for `<pre><code>` blocks emitted by the `verbatim` and `lstlisting` environments (`app/parser.py` lines 226, 231, 749, 759). Those emissions are unchanged — block-level code listings legitimately want MathJax to skip them (a `$` inside a code listing is typically a shell prompt or string-literal delimiter, not math). The bare `code { font-family: ... }` rule (`lecture.css:124–126`) continues to apply to those `<pre><code>` blocks. The `p code { background: ... }` rule (`lecture.css:128–133`) remains as a defensive style for any future inline `<code>` use, but no parser path currently emits inline `<code>`.

### Element choice rationale

Among `<span>`, `<kbd>`, `<samp>`, `<var>`:

- **`<span class="texttt">` (chosen).** Semantically neutral; styled via class. MathJax processes `<span>`. Matches the project's existing pattern for class-styled inline content (`<span style="font-variant:small-caps">` for `\textsc{}` at `app/parser.py:150`; `<div class="callout-title">` for callout titles per ADR-012).
- `<kbd>` rejected: HTML semantics is "user keyboard input," which is a wrong meaning for the corpus's typewriter-font usage. Accessibility tools may announce `<kbd>` content distinctly.
- `<samp>` rejected: HTML semantics is "sample output from a program," also a wrong meaning for arbitrary typewriter-fonted text including ASCII-art diagrams.
- `<var>` rejected: HTML semantics is "variable name," wrong for corpus uses like `\texttt{head $\to$ [7 | $\bullet$]}`.

### Multi-line `\texttt{}` content

The corpus's `\texttt{}` usage is inline (single-line). pylatexenc's `\texttt` macro takes one mandatory argument, which can syntactically contain newlines, but the corpus instances are all single-line ASCII-art diagrams. `<span>` is appropriate for this scope. If a future Chapter introduces multi-line block-level `\texttt{}` content where `<span>` proves visually inadequate (e.g., line-breaks within the span collapse to a single line), the supersedure path is bounded: a new ADR introduces a parser-side detection of line-break-containing `\texttt{}` arguments and emits `<pre class="texttt">` for those cases. No corpus instance currently triggers this.

### What this ADR does *not* decide

- **A new MathJax configuration.** The MathJax `skipHtmlTags` default is unchanged; we route around it by switching the emitted element, not by reconfiguring MathJax. (This was the project_issue's explicitly forbidden Option 3.)
- **Removing inline `<code>` for any other macro.** Only `\texttt{}` changes; `verbatim`, `lstlisting` continue to emit `<pre><code>`.
- **Per-character HTML escaping rules inside `\texttt{}`.** The existing `_convert_inline_latex` recursion handles HTML-special characters via `_escape`; that mechanism is unchanged.
- **Math-passthrough policy outside `\texttt{}`.** Independent; `LatexMathNode.latex_verbatim()` passthrough at `app/parser.py:83` is unchanged for all contexts.

## Alternatives considered

**A. Pre-process inline math inside `\texttt{}` arguments before emitting `<code>`.**
Walk the texttt argument node; for each `LatexMathNode`, emit a `<span class="math">$...$</span>` (or `<mjx-container>` placeholder) instead of the raw `$...$` text; emit `<code>...</code>` with the spans as children. MathJax does process some elements inside `<code>` if the inner element has the right shape — needs verification. Rejected because:
- Fragile: relies on MathJax v3's specific behavior around nested elements inside `skipHtmlTags` parents, which the MathJax docs do not strongly guarantee (MathJax may walk children for math, but the documented behavior is "skip the entire subtree under `skipHtmlTags`").
- Adds a special inline-math emission rule that only fires inside `\texttt{}` — every other `\texttt{}`-equivalent context would need the same special case if it ever appears. Option C (the chosen path) is structurally simpler.
- Doesn't solve the visual-inspection-of-source `$\to$`-vs-→ ambiguity the corpus already uses uniformly: math should render where math is written.

**B. Configure MathJax to remove `code` from `skipHtmlTags`.**
A one-line change in the MathJax config inline in `base.html.j2`. Rejected because:
- It applies globally — every `<pre><code>` listing emitted from `verbatim` and `lstlisting` would also have its `$` characters interpreted as math. For source code where `$` is a shell prompt (`echo $PATH`) or a string-literal start (`std::string s = "$" + ...`) or a Perl variable, this would visibly break the rendered code listings.
- Forbidden direction per the project_issue's explicit rejection of Option 3.

**C. Author-side workaround — replace `$\to$` with literal Unicode `→` in source.**
Rejected because:
- The LaTeX source is the canonical input; manifest §6 ("A Lecture has a single source") commits the project to deriving renders from that source. Asking the author to rewrite the source to compensate for a parser bug shifts the bug into the editorial layer.
- Manifest §5 ("No in-app authoring") only weakly applies (the source is human-authored), but the brittleness is real — any LaTeX user might use `$\to$` and expect MathJax to render it. The fix belongs in the parser/CSS layer.

**D. Emit `<kbd class="texttt">` or `<samp class="texttt">` instead of `<span class="texttt">`.**
Rejected (see "Element choice rationale" above). The semantics of `<kbd>` and `<samp>` are not what `\texttt{}` means; using them would surface the wrong content type to assistive technologies and to any future class-targeting CSS.

**E. Emit `<span class="texttt">` but skip the inline-code visual treatment** (only `font-family: monospace`; no background, no padding).
A minimal CSS rule. Rejected because the existing `p code` styling treats inline `<code>` as a slightly-set-off inline element with a soft background — the rendered look across the corpus relies on that styling for inline texttt readability. Dropping the background/padding would be a visible regression for ch-09/ch-10's many inline `\texttt{}` uses (variable names, function names, ASCII fragments) where the ambient background helps the reader spot the typewriter span. The chosen CSS rule reproduces the visual exactly.

**F. Append a clarifying Resolution-note to ADR-003 instead of writing a new ADR.**
ADR-003 commits to pylatexenc + custom handlers; one could read this fix as "extending a custom handler." Rejected because:
- ADR-003 is silent on the specific HTML mapping for `\texttt{}` — there is no claim in ADR-003 to clarify; this is a fresh decision.
- Per project discipline (mirrors the ADR-017 / ADR-011 relationship in TASK-007), in-place edits to Accepted ADRs erase the chronology. A fresh ADR is the right shape.

## My recommendation vs the user's apparent preference

The user's direction (TASK-007 task file, "Architectural decisions expected" and `parser-fidelity-texttt-traps-inline-math.md`) recommends **Option 1 (span-with-CSS)**. The architect agrees and writes Option 1 here. No substantive disagreement.

On the element choice (`<span>` vs `<kbd>` vs `<samp>` vs `<var>`), the project_issue defaults to `<span>` and the architect concurs (rationale above). The user has not signaled a preference among these.

On the CSS rule's specific properties, the architect is making a judgment call: the rule reproduces the existing `p code` styling so the visual look is preserved across the corpus. If the human prefers a more austere rule (only `font-family: monospace`), that's a small CSS tweak at gate-time and not a substantive re-decision; the architect's preference is to preserve the visual look that ch-09/ch-10 readers already see.

Aligned with user direction on Option 1; mildly opinionated on element choice (`<span>`) and CSS shape (reproduce `p code` look). Both can be challenged at gate.

## Consequences

**Becomes possible:**

- Every ASCII-art callout in ch-04 (and ch-09/ch-10's inline `\texttt{}` usages) renders inline math as math glyphs (→, •, ←, ↖, etc.) while preserving the typewriter font. ~200+ visibly-broken render sites are corrected.
- A Playwright assertion of the form "rendered DOM contains `<mjx-container>` inside `<span class="texttt">` for ch-04's first ASCII-art callout" is a stable regression test.
- Future corpus uses of `\texttt{}` with embedded math (any Chapter, any pattern) work without further changes.
- Other inline math contexts (paragraph text, headings) are unaffected — only the `\texttt{}` element changes.

**Becomes more expensive:**

- Adding **block-level `\texttt{}` content** (multi-line typewriter blocks where `<span>` collapses lines visually) requires a future ADR that introduces parser-side detection of line-break-containing arguments and emits `<pre class="texttt">`. Not currently needed; deferred.
- Changing the `\texttt{}` element again later (to reverse this decision) requires a supersedure ADR and a CSS-rule rename. Cost is bounded — one parser line, one CSS block.

**Becomes impossible (under this ADR):**

- `\texttt{}` rendering as `<code>` without a supersedure ADR.
- Inline math inside `\texttt{}` rendering as literal `$...$` text (the bug this ADR fixes).

**Supersedure path:**

- If a future Chapter introduces multi-line block-level `\texttt{}` content where `<span>` is visually inadequate, supersede with an ADR that adds a `<pre class="texttt">` branch for line-break-containing arguments. The visual class (`.texttt`) survives; only the wrapping element diverges.
- If MathJax's behavior around `<span>` changes in a future major version such that `<span>` enters `skipHtmlTags`, supersede with an ADR that picks the next-best non-skipped element. Unlikely.
- If the project later refactors toward a fully structured IR (per ADR-012's "supersedure path"), this ADR's parser-emission point moves from `_convert_inline_latex` into the template; the `.texttt` CSS class survives.

## Manifest reading

Read as binding for this decision:

- **§3 Primary Objective ("drive consumption … via per-Chapter Lectures").** Bound the requirement: 200+ visibly-broken render sites are an obstacle to consumption; this ADR closes them.
- **§5 Non-Goals: "No in-app authoring of lecture content."** Honored — the fix lives in `app/parser.py` and `app/static/lecture.css`, not in `content/latex/`. No source file is edited.
- **§6 Behaviors and Absolutes: "A Lecture has a single source"; "AI failures are visible" (read more broadly as "visible failure, no fabrication").** Bound the requirement that the rendered surface convey the editorial intent (math-rendered glyphs in typewriter contexts) rather than a fabricated approximation.
- **§7 Invariants.** Not directly touched; texttt rendering does not interact with M/O separability or the reinforcement loop.

No manifest entries flagged as architecture-in-disguise.

## Conformance check

- **MC-1 (No direct LLM/agent SDK use).** Not touched. No AI surface.
- **MC-2 (Quizzes scope to one Section).** Not touched.
- **MC-3 (Mandatory/Optional designation).** Not touched.
- **MC-4 (AI work asynchronous).** Not touched.
- **MC-5 (AI failures surfaced).** Not touched.
- **MC-6 (Lecture source read-only).** *Honored.* The fix edits `app/parser.py` and `app/static/lecture.css`; no path under `content/latex/` is touched.
- **MC-7 (Single user).** Not touched.
- **MC-8..MC-10.** Not touched.

ADR-relationship checks:

- **ADR-003 (rendering pipeline).** Honored. This ADR uses ADR-003's "extend environment-specific handlers" clause for a macro-level handler change. The `_convert_inline_latex` recursion model and the `LatexMathNode.latex_verbatim()` passthrough are unchanged.
- **ADR-008 (CSS layering).** Honored. The new `.texttt` rule lives in `app/static/lecture.css` (Lecture-body content styling), not in `app/static/base.css` (page chrome).
- **ADR-010 (Playwright verification).** TASK-007 acceptance criteria require Playwright tests verifying that `<mjx-container>` elements appear inside `<span class="texttt">` for at least one ch-04 ASCII-art callout. This ADR's decision is verified through the ADR-010 gate.
- **ADR-012 (callout title rendering).** Sibling-shape precedent: parser handler change + matching CSS rule in `lecture.css`. ADR-018 follows the same shape; no conflict.
- **ADR-013 (split verification harness).** TASK-007 reuses the 12-Chapter parameterized screenshot harness from TASK-005 for cross-corpus re-verification.

## Project_issue resolution

`design_docs/project_issues/parser-fidelity-texttt-traps-inline-math.md` is updated in this `/design` cycle to `Status: Resolved by ADR-018 (Proposed; contingent on acceptance)` with a one-line resolution note. Per the project's resolution discipline, an issue resolved by a `Proposed` ADR carries the resolution pointer immediately; if ADR-018 is rejected at gate, the project_issue's status reverts to Open and is re-triaged in a follow-up `/design` cycle.
