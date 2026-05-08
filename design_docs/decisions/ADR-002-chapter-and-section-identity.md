# ADR-002: Chapter and Section identity

**Status:** `Accepted`
**Date:** 2026-05-07
**Task:** TASK-001
**Resolves:** none (no project_issues filed against this question)

## Context

TASK-001 acceptance criterion 2 requires that "each Section in the LaTeX source appears as an addressable region of the page (with a stable per-Section identifier sufficient for future deep-linking and future per-Section Quiz attachment)." Manifest §6 fixes Quizzes to scope to exactly one Section, and manifest §7 makes the Section the atomic unit for Quizzes and completion state. Manifest-conformance rule MC-2 (Quizzes scope to exactly one Section) is already active and forbids any data path that loses Section identity.

Chapter 1 source illustrates the shape we have to identify against. The file is `content/latex/ch-01-cpp-refresher.tex`. Within it, Sections appear as `\section{1.1 Arrays and Vectors (general concept)}`, `\section{1.2 Vectors (in C++)}`, etc. The Section number is baked into the heading text rather than carried in a separate macro argument. There is no `\label{...}` next to each section heading. Subsections (`\subsection{...}`) exist but are not the manifest's "Section" — manifest §8 fixes "Section" as the atomic unit for Quizzes and completion, which corresponds to the LaTeX `\section` macro for this corpus.

This ADR has to commit to:

1. **A stable Chapter identifier.** Used by code, URLs, and future Quiz/Note bindings.
2. **A stable Section identifier scheme.** Used by URL fragments (deep-linking), and reserved as the future foreign key Quiz and Question Bank entities will point at.
3. **A rule for what counts as a "Section" in the source.** (LaTeX `\section` only; subsections are body content, not Section anchors.)

The IDs must be deterministic with respect to a fixed source file (TASK-001 acceptance criterion 4) and stable across re-runs of the renderer (because future tasks will store Quiz Attempts and Notes against them — manifest §7).

This ADR does *not* persist anything to a database. TASK-001 has no persistence layer. The IDs only need to be computable at render time and to remain identical the next time the renderer runs against the same source.

## Decision

### Chapter ID

A Chapter ID is a kebab-case slug derived from the chapter source file's basename (without the `.tex` extension). For Chapter 1: `ch-01-cpp-refresher`.

When the user adds future Chapters, the file basename *is* the Chapter ID, with no transformation. This makes Chapter ID computable by anyone who can `ls content/latex/` and is stable as long as the file is not renamed. Renames are equivalent to creating a new Chapter (and are a content-management action the user takes deliberately, outside the application).

### Section ID

A Section ID is a structured composite: `{chapter_id}#section-{section_number_kebab}`.

- `{chapter_id}` is the Chapter ID defined above.
- `{section_number_kebab}` is the Section's leading number, lowercased, with the dot replaced by a hyphen. For `\section{1.1 Arrays and Vectors (general concept)}` in `ch-01-cpp-refresher.tex`, the Section ID is `ch-01-cpp-refresher#section-1-1`.

Rationale for using the section number rather than the section heading slug: the leading number (`1.1`, `1.2`, …) is stable across editorial rewrites of the heading text. The author can rename "Arrays and Vectors (general concept)" to "Arrays and Vectors — overview" without invalidating future Quiz Attempts already bound to `ch-01-cpp-refresher#section-1-1`. The heading text is content; the number is identity.

The `#` separator is chosen so that Section IDs are also valid URL fragments when appended to a Chapter page URL (`/lecture/ch-01-cpp-refresher#section-1-1`). The renderer is free to use Section IDs as HTML anchor IDs directly, with the part before `#` being implicit because the page is the Chapter.

### What counts as a "Section"

Only LaTeX `\section{...}` macros at the document body level produce a Section anchor. `\subsection{...}` and deeper produce body structure but are *not* manifest Sections — they do not get Section IDs and are not Quiz attachment points. The manifest defines Section as a subdivision of a Chapter that is the atomic unit for Quizzes (§7, §8); for this corpus, `\section` is that subdivision.

If the source contains `\section` macros that lack a leading numeric pattern (`\section{Foo}` rather than `\section{1.5 Foo}`), the renderer **fails loudly** rather than fabricating a Section ID. This honors manifest §6's "AI failures are visible" principle as applied to non-AI failures: the system never invents identity for content that does not have it. (This case does not occur in `ch-01-cpp-refresher.tex`; surfacing the failure mode preserves the invariant for future Chapters.)

### Scope of this ADR

This ADR only fixes the *identity scheme*. It does not decide:

- How `\section{...}` macros are extracted from the LaTeX source — that is the parser strategy, owned by ADR-003.
- Where Section IDs are persisted as foreign keys — TASK-001 has no persistence; that becomes relevant when Quizzes / Notes / Question Bank / Quiz Attempts land.
- What URL routes the application exposes — owned by ADR-003 to the extent TASK-001 needs.

## Alternatives considered

**A. Use the LaTeX heading text as the Section slug (e.g., `arrays-and-vectors-general-concept`).**
Rejected. Heading text is editorial content; the author may revise it. Manifest §7 requires that Quiz Attempts persist across sessions, and once the Question Bank exists (manifest §8), Question rows will reference Section IDs as historical record. A Section ID that changes when prose is polished would corrupt that history. Section numbers are the stable handle.

**B. Use auto-generated UUIDs per Section, persisted in a sidecar index file.**
Rejected. UUIDs are stable across renames but require a sidecar that the application would need to either read or write. Writing it would violate ADR-001 (`content/latex/` is read-only to the application). Reading a hand-maintained UUID index is fragile and forces the user to do bookkeeping outside the application — exactly the kind of thing the manifest's "consume the curriculum" objective should not require. The numeric scheme already gives stability across editorial rewrites; UUIDs add no new stability and add a maintenance burden.

**C. Use `\label{...}` macros embedded in the source as the Section IDs.**
Rejected for TASK-001. `\label{...}` is a LaTeX-native mechanism and would be ideal in principle, but the existing source does not use `\label` next to `\section` headings. Adopting this scheme would require a content edit pass before TASK-001 can render anything — that is content migration, not rendering, and it competes with the primary objective for scope. If the author wants to add `\label`s later, a future ADR can supersede this one and migrate IDs (the migration is mechanical: the IDs become `\label` text instead of `section-{number}`). The current scheme degrades gracefully into a `\label` scheme.

**D. Use only the section number as the Section ID, without prefixing the Chapter (`section-1-1` instead of `ch-01-cpp-refresher#section-1-1`).**
Rejected. Section IDs need to be globally unique across the project once more than one Chapter is rendered. Without a Chapter prefix, `1.1` collides across Chapters. Manifest §7 requires Quiz Attempts to persist across sessions; a Quiz Attempt row pointing at `section-1-1` is ambiguous. The prefix is cheap and removes the ambiguity now.

## My recommendation vs the user's apparent preference

No apparent user preference to override. The task forecasts this ADR ("Chapter and Section identity") without prescribing a scheme; this ADR fills it in with the minimal scheme TASK-001 needs. No pushback raised against the user.

One observation: the existing chapter file naming is inconsistent (`ch-01-cpp-refresher.tex` vs `ch2.tex`, `ch3.tex`, …). This ADR's rule "Chapter ID = basename without extension" makes that inconsistency visible (Chapter IDs would be `ch-01-cpp-refresher` for one Chapter and `ch2`, `ch3`, … for the others, mixing two naming conventions). TASK-001 only renders Chapter 1 and so does not have to resolve this — but a future "render all Mandatory chapters" task will. Filed as `design_docs/project_issues/multi-chapter-source-naming.md` rather than decided here.

## Manifest reading

Read as binding:
- §6: "Quizzes scope to Sections; Lectures and Notes scope to Chapters." — Bound the requirement that Section IDs be stable, distinct from Chapter IDs, and unambiguously per-Section.
- §7: "A Quiz is bound to exactly one Section"; "Every Quiz Attempt […] persists across sessions." — Bound the stability requirement: Section IDs cannot change as a side effect of editorial revisions to source.
- §8 Glossary entries for Chapter, Section, Question, Question Bank, Quiz Attempt — Bound the foreign-key direction (Question → Section, Quiz Attempt → Quiz → Section). The Section ID is the stable handle those references will point at.

No manifest entries flagged as architecture-in-disguise.

## Conformance check

- **MC-2 (Quizzes scope to exactly one Section).** The Section ID scheme is the technical means by which a Quiz row carries exactly one Section reference. ADR-002 gives MC-2's downstream check a concrete handle to grep for: a Quiz/Question/Attempt that references a Chapter ID instead of a Section ID is a violation.
- **MC-3 (Mandatory/Optional designation respects the canonical mapping).** Orthogonal to this ADR — Section IDs do not encode M/O. M/O is owned by ADR-004 and is a Chapter-level attribute (manifest §8: Section inherits from Chapter).
- **MC-6 (Lecture source is read-only to the application).** Honored: the ID derivation reads source only.

No previously-dormant rule becomes evaluable solely because of this ADR; MC-2's path-name-specific check is not part of MC-2's evaluable definition.

## Consequences

**Becomes possible:**
- Future Quiz, Question, Question Bank, Quiz Attempt, and Note rows can foreign-key on a stable Section ID.
- Deep-linking to a Section via URL fragment (`/lecture/ch-01-cpp-refresher#section-1-1`) works without additional infrastructure.
- The renderer can produce HTML anchor IDs directly from Section IDs.

**Becomes more expensive:**
- If the user later wants to renumber Sections (e.g., insert a new "1.1.5" between 1.1 and 1.2), Section IDs shift and any persisted reference becomes stale. This cost is accepted: renumbering is rare and a known-cost editorial operation, and the same migration cost would apply under any heading-derived scheme.

**Becomes impossible:**
- A Section ID that depends on heading text or on a runtime-assigned UUID. Both are ruled out under this ADR; superseding it requires a new ADR.

**Future surfaces this ADR pre-positions:**
- Question Bank rows will key on Section ID. (Future ADR for persistence.)
- Notes that optionally reference a Section will key on Section ID (manifest §8).
- The Mandatory-only filter in a future index page filters Chapters by ID against the M/O mapping (ADR-004).
