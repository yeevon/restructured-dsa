# ADR-002: Section IDs are slugged from `\section{...}` headings, scoped within a Chapter, with deterministic collision suffixes

**Status:** Accepted
**Date:** 2026-05-07
**Task:** TASK-001

## Context
The manifest fixes the public Section identity at `ch-NN-slug#section-slug` (§8 Glossary "Section"). Section ids drive: anchors on the Lecture Page, the URL fragment, the foreign key on Questions and Quizzes (per CLAUDE.md `## Question persistence`), and — because Question Bank is "never deleted; only superseded by content reorganization" (§8) — the long-term key by which Question history survives across re-renders. A Section id that drifts every time the parser runs would corrupt the Question Bank on the next render. So the rule needs to be both deterministic and stable across runs of the same `.tex` source.

There are two independent sub-questions: (1) which LaTeX heading levels become Sections, and (2) how the slug is generated.

## Decision

**Anchor level.** Only `\section{...}` produces a Section. `\subsection{...}` and deeper render as in-Section structure (h3 / h4 in the HTML) and do not get Section-level anchors. Rationale: the manifest defines a Section as the atomic unit for Quizzes; making `\subsection` a Section would multiply the per-Section Question Bank in ways the curriculum author did not intend. If a Chapter has no `\section{...}` at all, the entire Chapter body is a single implicit Section with id `<chapter_id>#main` and title equal to the Chapter title. (Defensive: Chapter 1 is expected to have `\section{...}` divisions; the implicit-Section path is for safety, not a primary path.)

**Slug source.** The slug is derived from the heading text via a pure function `slugify(heading_text) -> str`:

1. Lowercase.
2. Replace any run of non-`[a-z0-9]+` characters with a single hyphen.
3. Strip leading and trailing hyphens.
4. If the result is empty, fall back to `section`.

LaTeX-specific characters (`\`, `{`, `}`, `$`, `&`, `%`, `_`, `#`, `^`, `~`) are all in the non-alphanumeric class and get collapsed to hyphens by step 2. LaTeX commands inside the heading (e.g., `\section{The \textbf{BST} Insertion Algorithm}`) have their command tokens stripped first; the slug is built from the rendered plain-text of the heading.

**Explicit-label override.** If a `\section{...}` is immediately followed by `\label{sec:<custom>}`, the slug is `<custom>` (after the same `slugify` pass, in case the author wrote a non-conforming label). This gives the curriculum author an escape hatch when two Sections in the same Chapter have title text that slugs identically (e.g., two Sections both titled "Examples").

**Collision handling.** After slug generation per Chapter, if two Sections produce the same slug, the second occurrence (in document order) gets `-2` appended, the third `-3`, etc. The first occurrence keeps its bare slug. A WARNING is logged at parse time. (We expect collisions to be rare in practice — the curriculum is curated by the author — but a duplicate-`\section{Examples}` Chapter shouldn't 500 the app.)

**Stability guarantee.** Given the same `.tex` file content, the parser produces the same ordered list of Section ids on every run. Tested in TASK-001's "parse twice, assert identical id list" test.

## Alternatives considered
- **Use `\label{...}` exclusively as the slug source, ignore heading text.** Rejected: forces the author to add a label to every Section in source. Couples the id to a LaTeX construct most LaTeX writers don't bother with for `\section`. The override path captures the cases where a label is genuinely useful without making it mandatory.
- **Hash-based ids (e.g., the first 8 chars of `sha1(heading_text)`).** Rejected: unreadable URLs and unreadable foreign keys in the eventual Question table. Stable, yes, but illegible.
- **Document-order numbering only (`#section-1`, `#section-2`).** Rejected: every reordering of the LaTeX source renumbers every later Section, invalidating Question Bank foreign keys for content that didn't actually change. The manifest's "supersedure" cost should be paid when content reorganizes, not when the author moves a paragraph.
- **Both `\section{...}` and `\subsection{...}` produce Sections.** Rejected: doubles the Quiz surface in a way the curriculum author has not signaled; the author's mental model of a "Section that gets a Quiz" matches `\section` granularity. Re-open if the curriculum begins routinely structuring `\section` as a thin wrapper around several Quiz-worthy `\subsection` units.

## Consequences
- Section ids are human-readable, stable across runs, and survive heading-text edits ONLY if those edits don't change the slug. Editing "BST Insertion" to "BST Insertion (Recursive Variant)" does change the slug; the curriculum author either accepts that as a content reorganization or adds a `\label{sec:bst-insertion}` to lock the slug. This tradeoff is on purpose — it's the same pattern as renaming a public function: free if you don't, breaking if you do.
- Collisions are detectable and degrade gracefully. The WARNING gives the author a clear signal to add a `\label{...}`.
- Future Lecture Script extraction (TTS) walks the same Chapter / Section model produced here; Section ids align between the HTML page and the future audio's Section markers (manifest §7 "derived artifacts remain structurally aligned").
- The implicit-Section fallback (`#main`) means the Chapter renderer never has zero Sections, even for a degenerate `.tex`. Quiz routing later can assume `len(chapter.sections) >= 1`.

## Manifest conformance
- §8 Glossary: stable Section id of shape `ch-NN-slug#section-slug` is satisfied.
- §6 "LaTeX is the source of truth": every Section id is derivable from LaTeX source alone.
- §7 "Derived artifacts remain structurally aligned to source": deterministic slug + stable order satisfies alignment.
