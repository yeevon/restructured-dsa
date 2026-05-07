# ADR-001: Chapter ID is derived from the LaTeX filename

**Status:** Proposed
**Date:** 2026-05-07
**Task:** TASK-001

## Context
A Chapter has a stable id (manifest §8: `ch-04-trees`-shape). That id is the URL key (`/chapters/<chapter_id>/lecture`), the lookup key for the Mandatory/Optional designation function, and the prefix of every Section id within the Chapter. The id has to come from somewhere deterministic and the source has to be a single well-known place — collision in the source-of-id between filename, directory, and an inline LaTeX command is the kind of drift the manifest's "derived artifacts remain structurally aligned to source" invariant rules out.

The Chapter id source also implicitly decides how a new Chapter is added. The simpler the ceremony, the less the LaTeX-source-is-read-only invariant gets eroded by "but I had to add a metadata file."

## Decision
The Chapter id is the basename of its `.tex` file under `content/latex/`, without extension. Files are named `content/latex/ch-NN-<slug>.tex` where `NN` is a zero-padded two-digit number (`01`..`99`) and `<slug>` is a kebab-case slug. The parser validates the filename matches the regex `^ch-(\d{2})-([a-z0-9]+(?:-[a-z0-9]+)*)$` and rejects files that do not. Adding a Chapter is `cp my-chapter.tex content/latex/ch-07-graphs.tex` — no metadata file, no inline LaTeX command, no directory layout.

The numeric prefix is what the Mandatory/Optional designation function reads (`ch-01`..`ch-06` → mandatory; `ch-07+` → optional), as locked in TASK-001.

## Alternatives considered
- **Directory layout (`content/latex/ch-01-bst/index.tex`).** Rejected: empty directories of one file each are pure ceremony for v1; revisit only if a Chapter genuinely needs sibling files (figures, includes) and even then `\input{...}` from a single top-level `.tex` solves it without changing the id source.
- **Inline LaTeX command (`\chapterid{ch-01-bst}` at the top of the file).** Rejected: the manifest treats LaTeX source as read-only from the app's perspective and externally edited. Requiring the author to maintain an id token inside the file in addition to giving the file a sensible name doubles the coupling and creates a second source of truth for the id.
- **A sidecar metadata file (`content/latex/ch-01-bst.meta.yaml`).** Rejected: the only metadatum we currently need (designation) is derivable from the numeric prefix. A sidecar is the right answer when per-Chapter override is needed; defer until that need surfaces. Writing this ADR is cheap; un-writing a YAML schema isn't.

## Consequences
- Adding a Chapter is a single-file copy; no app-side write happens.
- The filename regex is enforced in the parser. A malformed filename (`Chapter1.tex`, `ch-1-bst.tex`, `ch-01_bst.tex`) is a parser-level error, not a render-time 500.
- The two-digit numeric prefix caps Chapters at 99. That is hilariously larger than the curriculum and is fine.
- Re-numbering a Chapter (rare) means renaming the file and accepting that all Section ids and URLs for it change. That is correct behavior — re-numbering is a curriculum reorganization, and per the manifest §8 "Question Bank — never deleted; only superseded by content reorganization" the cost of supersedure is intentional.
- The designation function and the parser both hard-depend on this filename shape. Tested in TASK-001's unit tests.

## Manifest conformance
- §6 "LaTeX is the source of truth": the filename is part of the source; the app reads it, never writes it.
- §6 "Site never modifies LaTeX source": no app-side write involved.
- §7 "Derived artifacts remain structurally aligned to source": a single deterministic id source eliminates one drift vector.
