# LaTeX pipeline engine: plasTeX vs. pandoc (vs. hybrid)

**Status:** Open
**Surfaced:** 2026-05-07 (TASK-001)
**Decide when:** Immediately. TASK-001 is functionally complete (route, model, render pipeline, designation rule, tests, package layout) but cannot render real curriculum content usefully — Chapter 1 hits ADR-004 PassthroughBlock for ~6 box environments per Section, so the rendered page is dominated by raw-LaTeX dumps. Every downstream surface that consumes parsed Sections (Notes, Quiz generation, Lecture Script extraction, Lecture Audio) is blocked by, or compromised by, the same parser limitation.

## Question
What LaTeX-to-structured-content engine drives the Lecture Page (HTML), Lecture Script (TTS-ready text), and any future LaTeX-derived artifact?

## Background — what TASK-001 surfaced
CLAUDE.md picked plasTeX up front ("Python-native; keeps the stack uniform") and TASK-001's parser was built against it. Implementing the first real chapter (`ch-01-cpp-refresher`) revealed two hard plasTeX limits:

1. **No useful `\usepackage` cascade for real packages.** When plasTeX can resolve `\input{notes-style.tex}`, it follows the chain `tcolorbox → tikz → kvoptions` and the macro expander chokes mid-document, dropping section structure (real test: chapter parsed to **1 section, 3 passthroughs** instead of the ~11+ sections the source actually has). The parser currently *relies on* `\input` failing to keep document parsing intact — see the comment block in `cs300/lecture/parser.py`.
2. **No support for `\newtcolorbox` / `\newenvironment` definitions.** Even if the cascade were avoidable, plasTeX cannot expand the custom callout boxes (`defnbox`, `ideabox`, `warnbox`, `notebox`, `examplebox`) that structure every chapter. Each one hits ADR-004 passthrough and renders as raw LaTeX.

ADR-004's PassthroughBlock was designed for *occasional* unrecognized environments. The reality on real curriculum content is that passthrough is the dominant case, not the edge case — which inverts the design assumption.

## Options known

- **(a) plasTeX with custom shims.** Stay on plasTeX. Write a `cs300/plastex_packages/notesstyle.py` (and one per future style file) that registers each custom environment as a known plasTeX command that just renders its body, plus a per-environment label. Cost: scales linearly with curriculum complexity; every new `\newtcolorbox` or `\newenvironment` in the curriculum requires a Python shim. Maintenance burden distributed across every future LaTeX-touching task. Keeps the stack Python-native (CLAUDE.md goal).

- **(b) pandoc with a small filter.** Replace plasTeX with pandoc (external binary). Use `pandoc --from latex+raw_tex --to html` for HTML and `pandoc --from latex --to plain` (or markdown → script extraction) for the TTS Lecture Script. Custom box environments map cleanly via a small JSON or Lua filter (`defnbox` → `<div class="defnbox">` with a label). Cost: external Haskell binary in the runtime/dev environment, breaks the "Python-native stack" preference, requires rewriting `cs300/lecture/parser.py` (~300 LOC) but the `Chapter`/`Section`/`Block` model from ADR-003 survives unchanged.

- **(c) Hybrid: pandoc for the LaTeX → structured-blocks pass, native Python for the rest.** Use pandoc only as the LaTeX-AST source (call `pandoc -t json` and walk the pandoc-AST in Python). Same external-binary cost as (b), but keeps all higher-level logic in Python. Sometimes called "pandoc-as-library."

- **(d) Pre-process the LaTeX with a Python regex stripper, then plasTeX.** Strip `\input{notes-style.tex}` and rewrite `\begin{defnbox}[X] ... \end{defnbox}` → `\paragraph{Definition — X} ...` in memory before parsing. Keeps plasTeX. Cost: brittle text-level rewriting that has to be updated for every new environment and that risks corrupting nested LaTeX. Violates the spirit of "LaTeX is the source of truth" because the in-memory rewrite changes semantics.

## Manifest constraints

- **§6: "LaTeX is the source of truth for lecture content."** Whatever engine is chosen, the app must not modify LaTeX source files. Option (d) modifies the source *in memory* but not on disk — defensible but the architect should weigh it.
- **§6: "Lecture Page (HTML), Lecture Script (TTS-ready text), and Lecture Audio derive deterministically from LaTeX source."** Both options (a) and (b) satisfy this; the determinism question is about whether the chosen engine's output is stable across runs, which is an implementation concern, not a manifest one.
- **§7: "The Lecture Page and Lecture Script are sibling outputs of the same source; neither derives from the other."** ADR-003's `Chapter` model already enforces this — both renderers consume the same parsed model. The engine choice does not threaten this invariant; it just chooses the engine that produces the model.
- **CLAUDE.md "Python-native stack" preference** is a stack convention, not a manifest invariant. Switching to pandoc is allowed; it just needs to be explicit.

## Constraints from existing ADRs

- **ADR-001 (chapter-id-from-filename), ADR-002 (section-id-scheme), ADR-005 (lecture-page-routing)** are engine-agnostic and survive unchanged regardless of choice.
- **ADR-003 (lecture-parser-data-model)** survives unchanged — the `Chapter`/`Section`/`Block`/`Inline` Pydantic shape is the engine boundary. Only `parse_chapter`'s implementation rewrites.
- **ADR-004 (unrecognized-latex-passthrough)** survives but its *design center* shifts: under pandoc, passthrough becomes rare again (the original design assumption); under plasTeX-with-shims, passthrough remains rare only as long as shim coverage keeps up with curriculum.

## What "resolved" looks like
A new ADR (provisionally ADR-006) recording the chosen engine, the migration approach (if pandoc), and the policy for handling future custom environments. If pandoc is chosen, CLAUDE.md's "LaTeX parsing: plasTeX (Python-native; keeps the stack uniform)" line is updated in the same task and the implicit plasTeX choice in ADR-000 is **superseded**.

## Resolution
When resolved, mark this issue `Resolved by ADR-NNN` and update CLAUDE.md's stack section if the engine changed.
