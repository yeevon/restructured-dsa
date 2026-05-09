# ADR-014: Strip the `\\` linebreak macro (and other non-letter LaTeX macros) from title extraction

**Status:** `Accepted`
**Date:** 2026-05-08
**Task:** TASK-005
**Accepted:** 2026-05-08 (human gate; accepted as written — broader-than-whitelist strip is the right shape for this corpus; recorded in TASK-005 audit Run 004)
**Resolves:** `design_docs/project_issues/latex-linebreak-macro-passthrough-in-titles.md`
**Supersedes:** none

## Context

The `latex-linebreak-macro-passthrough-in-titles.md` project_issue (Open since TASK-002) records that every Chapter's `\title{...}` macro contains a literal `\\` LaTeX linebreak (e.g., `\title{CS 300 -- Chapter 2 Lectures\\\large Introduction to Algorithms}`), and that the `\\` substring survives `extract_title_from_latex()` (`app/discovery.py`) into the rendered HTML in both the navigation rail and the Lecture-page header.

Verified against the corpus during `/design TASK-005`: every one of the 12 `.tex` files carries the same shape — `\title{CS 300 -- Chapter N Lectures\\\large <subtitle>}`. A grep of `\title{` across `content/latex/` confirms 12 hits, all matching that shape.

The current extractor (`app/discovery.py:34–51`) does:

```python
raw = re.sub(r'\\[a-zA-Z]+', ' ', raw)   # strips \large, \textbf, etc.
raw = re.sub(r'[{}]', '', raw)
normalized = re.sub(r'\s+', ' ', raw).strip()
```

Applied to `CS 300 -- Chapter 2 Lectures\\\large Introduction to Algorithms`, the regex `\\[a-zA-Z]+` (a backslash followed by one or more letters) does not match `\\` (which is two backslashes — neither character is a letter). It matches `\large` after the second backslash, replacing it with a space. The result keeps a stray `\\` in the rendered title across all 12 Chapter rows of the navigation rail and on every Lecture-page header.

The project_issue enumerates four options (strip; render as `<br>` in header / strip in rail; render as space; broader formatting-macro strip including `\\`). Manifest §6 ("A Lecture has a single source") and ADR-007 ("extract once, reuse twice") require that whatever the rail and the Lecture-page header show, they show the same string. ADR-007's display-label rationale already commits to "plain text" extraction (`raw_title` is normalized through whitespace collapse and used as a label).

This decision is forced now because TASK-005's validation pass produces 12 Lecture-page screenshots; the bug will be visible in the title position of every screenshot and in the rail of every screenshot, multiplying the visual-defect surface from "Chapter 1's title looks slightly off" to "every Chapter is broken in the same way." Resolving in this task converts the screenshot set from "12 instances of a known cosmetic bug + whatever new bugs we find" to "12 clean title renderings + whatever new bugs we find" — strictly cleaner triage signal.

The corpus is editorially uniform on the `\\\large <subtitle>` shape — there is no Chapter where the `\\` linebreak is meant to render as a structural break that stripping would lose. Stripping is the editorially correct outcome for this corpus.

## Decision

The title extraction in `extract_title_from_latex()` strips **the `\\` linebreak macro** alongside the existing letter-named macro stripping. The strategy stays "regex-based plain-text extraction" — Option 1 from the project_issue — extended to cover `\\` specifically.

Concretely, `extract_title_from_latex()` is amended to add **one substitution before the existing `\\[a-zA-Z]+` substitution**:

```python
raw = re.sub(r'\\\\', ' ', raw)            # strip the \\ linebreak macro (this ADR)
raw = re.sub(r'\\[a-zA-Z]+', ' ', raw)     # strip letter-named macros (existing)
raw = re.sub(r'[{}]', '', raw)             # strip braces (existing)
normalized = re.sub(r'\s+', ' ', raw).strip()
```

Order matters: the `\\\\` substitution must precede the `\\[a-zA-Z]+` substitution. If the order were reversed and `\large` were matched first via `\\[a-zA-Z]+`, the leftmost-longest semantics would still work; but the explicit ordering documents the precedence and avoids any future regex change introducing a subtle interaction.

The architectural commitment in this ADR:

- Title extraction returns **plain text**. Layout LaTeX inside a `\title{...}` (`\\`, `\large`, `\textbf`, `\emph`, `\small`, `\Large`) is treated as formatting-only and stripped.
- The single-extraction principle (ADR-007) is preserved: the same function feeds both the rail label and the Lecture-page header.
- The whitelist-vs-blacklist question raised by the project_issue is answered **blacklist** (strip what we recognize as layout-only, pass anything else through). The current regex `\\[a-zA-Z]+` already strips *every* letter-named macro, which means new editorial macros like `\textsc` or `\emph` are stripped too. That is acceptable for this corpus; if a future title needs a macro to render rather than strip (e.g., math `\alpha` inside a title), this ADR is superseded by one that introduces a whitelist or routes titles through the body parser.
- `\\` (linebreak) is stripped with no replacement structure (no `<br>`, no marker, no escape). Both surfaces (rail + header) honor manifest §6 by showing the same single-line title.

### What this ADR does *not* decide

- **Routing titles through the pylatexenc body parser** (Option 2 from the project_issue). That is a heavier architectural shift — title extraction would gain HTML output (e.g., `<em>...</em>` from `\emph`), the IR contract would expand, and the helper signature would need to change. Out of scope here. The current bug (literal `\\` in titles) does not justify the heavier shift; if a future task surfaces a Chapter whose title legitimately needs HTML, supersede this ADR with one that adopts Option 2.
- **Per-surface divergent rendering** (Option 3 from the project_issue: `<br>` in header, strip in rail). Rejected on manifest §6 grounds; one extraction, one output.
- **Math passthrough inside titles.** No current title contains math (`$...$`). If one is added, the regex `\\[a-zA-Z]+` will not strip the dollar-delimited math (math delimiters are not backslash-letter macros) and the math substring will pass through to the rendered title verbatim — which, since titles are plain-text rendered, will display as `$x$` to the user. A future ADR addresses this if and when a title introduces math.

## Alternatives considered

**A. Route titles through the pylatexenc body parser (project_issue Option 2).**
Considered. The body parser already handles `\\` inline (`name == "\\"` → `<br>`) and would naturally handle `\large`, `\emph`, etc. through the warn-per-node discipline. Rejected here because:
- The change is large: title extraction returns plain text today; routing through the body parser would either return HTML (breaking the existing `display_label: str` contract in `ChapterEntry` and the existing `_extract_title()` fallback string `"Lecture"`) or require the implementer to call the parser and then strip HTML (adding a new code path that is itself fragile).
- The current bug is bounded: one macro (`\\`), 12 chapters, 1-line fix. The Option-2 shift is justified only when the editorial demand for in-title HTML rendering surfaces — it has not.
- ADR-007 already commits the project to "title extraction is a separate, simpler regex-based mechanism" (its scope-delineation language). Option 2 contradicts that commitment without a current need; Option 1 stays inside it.
- If a future task surfaces the demand (e.g., a Chapter whose title is `\emph{Trees:} Theory and Practice` and the editorial intent is to italicize "Trees:"), the supersedure path is well-defined (this ADR is replaced by an Option-2 ADR; the helper signature changes; the consumers update; the test suite extends). The current ADR does not foreclose that path; it just defers the cost.

**B. Render `\\` as a `<br>` in the Lecture-page header but strip in the rail (project_issue Option 3).**
Rejected. Two transformation rules at the consuming sites is more architectural surface than the project needs. Manifest §6's "single source" reading is technically satisfied (the source `\title{...}` is one), but introducing two rules where one suffices runs against the project's existing "extract once, reuse twice" discipline (ADR-007). If the rail later needs a single-line truncation rule for very long titles, that is a CSS truncation rule, not an extraction-layer divergence.

**C. Render `\\` as a space in both surfaces (project_issue Option 3 alt).**
Functionally equivalent to the chosen approach — `re.sub(r'\\\\', ' ', raw)` followed by `re.sub(r'\s+', ' ', raw).strip()` collapses the inserted space with adjacent whitespace. Stated as "replace with a space" to make the implementer's regex obvious. (The chosen substitution is exactly this.)

**D. Defer indefinitely (project_issue Option 4).**
Rejected on the grounds the project_issue itself rejected: the bug is visible at every Lecture page header and every rail row; deferral grows the visible-bug surface area as the rail surfaces more Chapters. TASK-005 explicitly forces a decision because the validation pass would produce 12 screenshots showing the bug.

**E. Whitelist-driven stripping (only `\\`, `\large`, `\textbf`, `\emph`; pass anything else through).**
Considered. The project_issue lists this as a possible refinement of Option 1. Rejected because:
- The current behavior is already blacklist-style via `\\[a-zA-Z]+` (every letter-named macro is stripped). A whitelist would *narrow* the strip surface and re-introduce passthrough for any macro not in the whitelist.
- For this corpus, every macro that appears in titles (`\large`, `\\`) is layout-only. Adding the whitelist is more code with no editorial benefit.
- If a future Chapter introduces a title macro that should render rather than strip, the right answer is Option 2 (body parser), not a whitelist that has to be maintained per macro.

## My recommendation vs the user's apparent preference

**Aligned with the task's stated recommendation.** TASK-005's "Architectural decisions expected" section recommends "fold the fix into this task's scope and resolves the issue with a new ADR — choosing Option 1 (regex strip + small macro whitelist)." TASK-005's "Architectural concerns" section recommends Option 1 explicitly: "regex strip + whitelist for `\\`, `\large`, and similar pure-formatting macros."

The architect aligns with Option 1 (regex strip). The architect mildly diverges from "small macro whitelist" — the existing extractor already strips every letter-named macro via `\\[a-zA-Z]+`, which is broader than a whitelist; this ADR adds `\\` to that broad strip rather than narrowing to a whitelist. The net effect is what the task and the project_issue both ask for: the literal `\\` no longer appears in rendered titles, and the existing `\large` strip behavior is unchanged. The architect's reading is that the task author meant "strip these macros (e.g., `\\`, `\large`)" rather than "introduce a whitelist mechanism" — the language is informal but the intent reads as the plain-text-extraction commitment this ADR makes.

If the human's reading is genuinely "introduce a maintained whitelist," surface that at gate time and the architect supersedes with the whitelist version. Default reading: the broader strip is right for this corpus.

## Consequences

**Becomes possible:**

- Both surfaces (rail + Lecture-page header) render every Chapter's title without the literal `\\` substring. The 12 screenshots TASK-005 captures show clean titles.
- The bug surface remaining for titles is bounded: any macro that appears in a `\title{...}` is either letter-named (already stripped by `\\[a-zA-Z]+`) or a special character (caught by future ADRs). The corpus has no current case that fails the new regex.
- The single-extraction principle (ADR-007) is preserved: one function, two surfaces, identical output.

**Becomes more expensive:**

- One more regex line in `extract_title_from_latex()`. Trivial.
- One new test (added by `/implement TASK-005`'s test-writer phase) asserting that a title containing `\\\large foo` extracts to `... foo` with no backslash residue. Trivial.

**Becomes impossible (under this ADR):**

- A title that survives extraction with a literal `\\` substring. The regex strips it.
- Routing titles through the body parser without a supersedure ADR (the architectural commitment is "regex-based plain-text extraction").

**Supersedure path if this proves wrong:**

- If a future Chapter's title needs HTML output (e.g., `\emph{Trees:} Theory`), supersede this ADR with one that routes titles through the body parser (project_issue Option 2). The supersedure changes `display_label: str` to a richer type and updates the templates.
- If the broader strip is too aggressive (e.g., a title contains `\alpha` and the editorial intent is to render the Greek letter), supersede with a whitelist-narrowed regex that strips only known layout macros.
- If the regex itself is wrong on a corner case (e.g., a Chapter introduces escaped backslashes inside braces), the test suite catches it and the implementer extends the regex inline; if the case requires a structural change, supersede.

## Manifest reading

Read as binding for this decision:

- **§3 Primary Objective ("drive consumption").** Bound the requirement that the rendered title be readable without literal LaTeX macros visible. A title that reads "CS 300 -- Chapter 2 Lectures\\ Introduction to Algorithms" degrades the consumption surface.
- **§5 Non-Goals: "No in-app authoring of lecture content."** Honored — the fix lives in the extractor, not in `content/latex/`. No source file is edited.
- **§6 Behaviors and Absolutes: "A Lecture has a single source."** Bound the single-extraction principle: rail and header render the same string from the same function.
- **§7 Invariants: "Mandatory and Optional are separable in every learner-facing surface."** Not directly touched; M/O separability is independent of the title extraction fix.

No manifest entries flagged as architecture-in-disguise.

## Conformance check

- **MC-1 (No direct LLM/agent SDK use).** Not touched.
- **MC-2 (Quizzes scope to exactly one Section).** Not touched.
- **MC-3 (Mandatory/Optional designation respects the canonical mapping).** Not touched. Title extraction does not interact with designation.
- **MC-4 (AI work asynchronous).** Not touched.
- **MC-5 (AI failures surfaced).** Not touched.
- **MC-6 (Lecture source read-only).** *Honored.* The fix edits `app/discovery.py`'s extractor; no path under `content/latex/` is touched by code or by editorial intent.
- **MC-7 (Single user).** Not touched.
- **MC-8..MC-10.** Not touched.

UI-skill rules: not directly implicated by this ADR (UI surface render-time transformation; no new UI surface introduced).

Authority-state rules:
- **AS-1..AS-7.** Honored. ADR-014 is `Proposed`. The project_issue `latex-linebreak-macro-passthrough-in-titles.md` will be marked `Resolved by ADR-014` mechanically once the human accepts ADR-014 (status update is a function of the gate, not pre-emptive).

No previously-dormant rule is activated by this ADR.

## Project_issue resolution

`design_docs/project_issues/latex-linebreak-macro-passthrough-in-titles.md` is updated in this `/design` cycle to `Status: Resolved by ADR-014` with a one-line resolution note. Per the project's resolution discipline, an issue resolved by a `Proposed` ADR carries the resolution pointer immediately; the file's resolution row records that the issue's resolution is contingent on ADR-014's human acceptance. (If ADR-014 is rejected at gate, the project_issue's status reverts to Open and the issue gets re-triaged in a follow-up `/design` cycle.)
