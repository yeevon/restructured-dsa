# Multi-chapter source file naming convention

**Status:** Open
**Surfaced:** 2026-05-07 (TASK-001 / ADR-002)
**Decide when:** the first task that renders a Chapter other than `ch-01-cpp-refresher` lands, OR when an index page covering multiple Chapters is required, whichever comes first.

## Question

Existing chapter source files in `content/latex/` use two distinct naming styles:

- `ch-01-cpp-refresher.tex` (kebab-case with two-digit zero-padded number and a slug)
- `ch2.tex`, `ch3.tex`, `ch4.tex`, `ch5.tex`, `ch6.tex`, `ch7.tex`, `ch9.tex`, `ch10.tex`, `ch11.tex`, `ch12.tex`, `ch13.tex` (compact `ch{N}` form, no slug, no zero padding, with `ch8.tex` absent)

ADR-002 fixes the rule "Chapter ID = file basename without extension." Under that rule, the resulting Chapter IDs are `ch-01-cpp-refresher`, `ch2`, `ch3`, … — a mix of two conventions exposed in URLs and (eventually) Quiz/Note foreign keys.

The unresolved question is: **which naming convention wins, and how is the migration handled?** Specifically:

1. Should every Chapter file follow the `ch-{NN}-{slug}` form (rename `ch2.tex` → `ch-02-...tex`)?
2. Or should Chapter 1 be renamed to match `ch1.tex` (lossy — drops the descriptive slug)?
3. Should the gap (`ch8.tex` absent) be filled, or does Chapter 8 not exist in the curriculum?
4. Do the existing `ch{N}.tex` files actually contain rendered-Lecture content, or are they stubs/raw imports that need restructuring before they can be rendered?

## Options known

- **A. Standardize on `ch-{NN}-{slug}` everywhere.** Requires renaming 11 files and choosing a slug for each. Renames are an editorial action the user takes outside the application (manifest §5: source is edited outside the application), so the migration is straightforward — but it is a content-management commit that competes for scope with whatever task forces this issue.
- **B. Standardize on `ch{N}.tex` everywhere.** Requires renaming `ch-01-cpp-refresher.tex`. Loses descriptive metadata in the filename. URLs become `/lecture/ch1` (less informative).
- **C. Allow both conventions and have the parser tolerate them.** ADR-002's "Chapter ID = basename" rule already does this implicitly. The cost is permanently inconsistent IDs; the win is no migration.
- **D. Rename none of them yet; revisit when an index page or multi-Chapter render forces a uniform style.** This is the current state. Option D is what TASK-001 effectively chose by deciding to render only Chapter 1.

## Constraints from the manifest

- §5 (Non-Goals): "Lecture source is edited outside the application." Any rename is a manual action the user performs; no application code does it.
- §6: "A Lecture has a single source." A rename is a single-source migration; the new filename becomes the new source. No parallel-source state may exist mid-migration.
- §7: "Every Quiz Attempt, Note, and completion mark persists across sessions." Once persistence lands and Chapter IDs are foreign-keyed, rename = ID change = data migration. The cost of resolving this issue rises sharply once Quiz Attempts exist for a Chapter whose ID is about to change. **This is the primary reason to resolve before persistence-bearing data references the IDs.**

## Resolution

When resolved, mark this issue `Resolved by ADR-NNN`.
