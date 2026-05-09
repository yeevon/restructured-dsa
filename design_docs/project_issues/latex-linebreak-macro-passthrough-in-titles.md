# LaTeX `\\` linebreak macro passes through to rendered title text

**Status:** Resolved by ADR-014 (Accepted 2026-05-08)
**Surfaced:** 2026-05-08 (TASK-002 audit Run 009 adjacent finding; `/design TASK-003` deferred from styling scope)
**Decide when:** before the next task that adds a Chapter title source change, OR before the next task that surfaces titles in a *third* surface (the rail and the Lecture-page header are surfaces 1 and 2; a third surface would multiply the visible-bug surface area), whichever comes first. Defensible to defer to a focused fidelity task at any time.

## Question

Each Chapter's `\title{...}` macro contains a literal `\\` LaTeX linebreak macro (e.g., `\title{CS 300 -- Chapter 1 Lectures\\ \large C++ Refresher: Pointers, References, ...}`). The shared `extract_title_from_latex()` extractor (`app/discovery.py`, called by both the Lecture page header per ADR-003 and the navigation rail label per ADR-007) reads this string and returns it verbatim — the `\\` substring survives into the rendered HTML, where browsers display it as a literal backslash-backslash sequence rather than rendering as a line break or being elided.

What is the correct rendered behavior for `\\` inside a title?

The question has multiple defensible answers and no single Accepted ADR resolves it:

- **Render as nothing (strip).** The `\\` is layout-only LaTeX; rendered HTML titles do not need a hard line break inside the title. Stripping produces a clean single-line title in both surfaces. Concrete example: `"CS 300 -- Chapter 1 Lectures\\ \large C++ Refresher: ..."` → `"CS 300 — Chapter 1 Lectures C++ Refresher: ..."` (also strips `\large` per same principle).
- **Render as a HTML `<br>` in the Lecture-page header; strip in the rail label.** The Lecture-page header has space for a multi-line title; the rail row is a single-line-truncated affordance. This is two behaviors at the consuming site, not a single extraction rule.
- **Render as a space in both surfaces.** Treats `\\` as a soft separator, joining the two lines into one with a space. Closest to the visual outcome of a LaTeX title rendered as a single-line caption.
- **Strip `\\` and also strip `\large` (and any other formatting macro inside the title).** Treats title extraction as "plain-text title" — every formatting macro removed. This is the broadest answer and it's what `lecture.css` does for *body* content via the existing pylatexenc-based parser (`app/parser.py`); the title extraction is a simpler regex that does not run the body parser.

A related question: should the extractor handle other LaTeX macros that may appear in titles (`\textbf{...}`, `\emph{...}`, `\textit{...}`, math like `$...$`)? The current extractor is regex-based and fragile against any macro it has not anticipated. Manifest §6 ("A Lecture has a single source") implies the title in the rail and the title in the header agree by construction — which they do today (both surfaces show the same broken `\\` sequence) — but the failure mode is that *both* are broken consistently rather than one being right.

## Options known

1. **Strip `\\` (and a small whitelist of formatting macros) inside `extract_title_from_latex()`.** Single-extraction rule; both surfaces inherit the cleaned title. Architectural commitment: title extraction is "plain text," not "LaTeX-formatted text." Implementer change: regex-based macro stripping inside the existing extractor (~10 lines).

2. **Run the title text through the existing pylatexenc-based body parser (`app/parser.py`) instead of the regex extractor, and emit the parser's plain-text or HTML output.** Reuses an existing engine; handles unknown macros via the same warn-per-node strategy ADR-003 commits to for body content. Heavier change: requires either factoring a new entry point on the parser or accepting some HTML in the title (e.g., `<em>`).

3. **Render `\\` as `<br>` in the Lecture-page header but strip in the rail label** — divergent rendering at the consuming site, single extraction returning a marker the consuming sites interpret. Adds a site-specific transform layer the project does not currently have.

4. **Defer indefinitely — accept the `\\` substring in rendered titles as a known cosmetic defect.** Not recommended; bug is visible at every Lecture page header and every rail row, and grows in visibility as the corpus grows.

## Constraints

- Manifest §6 ("A Lecture has a single source") — the title shown in the rail and the title shown in the Lecture page header come from the same extraction; they cannot disagree silently. Option 3 (divergent rendering at consuming sites) introduces two transformation rules that the manifest §6 reading would tolerate (the *source* is one) but that complicates the architectural surface.
- ADR-003 ("Rendering pipeline") — the body parser (`app/parser.py`) handles unknown LaTeX nodes via warn-per-node and continues; the title extractor (`extract_title_from_latex()`) is a separate, simpler regex-based mechanism. ADR-003 does not commit to which mechanism owns title extraction; that is implicit in the current code, not architectural.
- ADR-007 ("Chapter discovery and display") — committed to "extract once, reuse twice" via the shared helper. Whatever this issue resolves, it must preserve the single-extraction principle.
- The `\\` macro is the most-frequent offender in the current corpus; other macros (`\large`, `\textbf`, `\emph`) appear in some titles. Resolution should at minimum cover `\\` and ideally have a story for the others.
- The bug is visible at all 12 chapter rows and at every Lecture-page header that renders a title containing `\\` — surface area is substantial. The only thing keeping the bug bounded is that the title text is editorially crafted and the human knows roughly what it is supposed to say.

## Why this is filed as a project_issue, not folded into ADR-008 or a TASK-003 in-scope item

TASK-003's framing ("Architectural concerns I want to raise") explicitly offers this as an in-scope-or-defer architect decision. The architect (in `/design TASK-003`) judges defer because:

- The bug is not a *styling* bug. It is a *content extraction* bug. ADR-008 (proposed in `/design TASK-003`) scopes the styling layer; folding a content-extraction decision in would muddy that ADR's scope and complicate its supersedure path.
- The fix is not large but the *decision* is — choosing between options 1, 2, and 3 has real architectural consequences (whether the title extractor returns plain text or HTML, whether one engine or two handle title extraction, whether consuming sites get a marker to interpret). Making that decision well requires a focused look at the parser/extractor architecture that is not in TASK-003's scope.
- TASK-003's primary deliverable (a usable styled navigation surface) is already substantial. Adding a parser-architecture decision to the same ADR risks the styling work being held up by a parser-design discussion.
- The styling surface is *more* visible (and therefore more important to fix promptly) than the linebreak cosmetic. Once the rail is styled and the human is using the surface, the linebreak bug becomes a visible-but-bounded annoyance — exactly the right shape for a focused follow-up.

Defensible to revisit at any point; the issue is `Open` so the next architect run that touches title rendering can pick it up.

## Resolution

Resolved by ADR-014 (Accepted 2026-05-08). The decision is Option 1 from this issue: strip the `\\` linebreak macro inside `extract_title_from_latex()` by adding `re.sub(r'\\\\', ' ', raw)` before the existing letter-named-macro strip. Title extraction remains regex-based plain-text; the single-extraction principle (ADR-007) is preserved; both surfaces (rail + Lecture-page header) render the same clean string. The fix is folded into TASK-005's `/implement` phase.
