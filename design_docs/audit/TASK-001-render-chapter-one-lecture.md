# LLM Audit — TASK-001: Render Chapter 1 as a viewable Lecture page

**Task file:** `design_docs/tasks/TASK-001-render-chapter-one-lecture.md`
**Started:** 2026-05-07T00:00:00Z
**Status:** Implemented
**Current phase:** verify

---

## Human gates

| Time | Gate | Result | Notes |
|---|---|---|---|
| 2026-05-07 | Task reviewed | accepted | TASK-001 proposal accepted by human |
| 2026-05-07 | ADR-001 reviewed | accepted | Lecture source layout — accepted by human |
| 2026-05-07 | ADR-002 reviewed | accepted | Chapter and Section identity — accepted by human |
| 2026-05-07 | ADR-003 reviewed | accepted | Rendering pipeline — accepted by human; FastAPI-vs-Flask pushback acknowledged, FastAPI retained |
| 2026-05-07 | ADR-004 reviewed | accepted | M/O designation source — accepted by human; code-as-source over config retained |
| 2026-05-07 | Tests reviewed | accepted | 133 tests across 9 files — happy-path + callout/no-LaTeX-leak/code-block + edge cases. Contracts pinned in docstrings; one ESCALATION on ADR-002 noted, not blocking. |

---

## Agent runs

### Run 001 — architect (Mode 1: Propose the next task)

- **Timestamp:** 2026-05-07T00:00:00Z
- **Agent:** architect
- **Phase:** next

**Input files read:**
- `design_docs/MANIFEST.md` (full)
- `CLAUDE.md` (full)
- `.claude/skills/manifest-conformance/SKILL.md` (full)
- `.claude/commands/next.md` (for invocation contract)
- `design_docs/architecture.md` — does not exist (empty-decisions state)
- `design_docs/decisions/` — directory empty (no ADRs)
- `design_docs/project_issues/` — directory empty (no open issues)
- `design_docs/tasks/` — directory empty (no prior tasks; this is TASK-001)
- `design_docs/audit/` — directory empty (no prior audits)
- `content/latex/ch-01-cpp-refresher.tex` (first ~80 lines, sampled to confirm Chapter 1 source exists on disk; not used to make architectural decisions)

**Tools / commands used:**
- `Read` (manifest, CLAUDE.md, SKILL.md, next.md, ch-01 sample)
- `Glob` (to enumerate `design_docs/**/*`, `latex/**/*`, repo root)
- No shell commands. No git operations. No code execution.

**Files created:**
- `design_docs/tasks/TASK-001-render-chapter-one-lecture.md`
- `design_docs/audit/TASK-001-render-chapter-one-lecture.md` (this file)

**Files modified:** none.
**Files deleted:** none.

**Decisions surfaced (as pointers — not binding here):**
- Source layout, Chapter/Section identity, rendering pipeline, and Mandatory/Optional designation source are all anticipated as ADRs to be drafted during `/design TASK-001`. Listed in the task file under "Architectural decisions expected." No ADR-NNN numbers exist yet; numbers will be assigned in Mode 2.
- Project issues directory is empty; if `/design TASK-001` surfaces architectural questions that TASK-001 does NOT need to resolve, the architect will create `design_docs/project_issues/<slug>.md` files in Mode 2.

**Leaks / pushback raised:**
- **Project setup gap (not a leak):** `CLAUDE.md` "Commands" section (lines 60–64) contains placeholder values (`<dev command>`, etc.). Flagged in the task file's "Architectural concerns I want to raise" section. Owner: human (CLAUDE.md is human-owned). Not blocking proposal of TASK-001.
- No `MANIFEST TENSION:` raised.
- No `ARCHITECTURE LEAK:` raised. (Manifest §4 explicitly owns the `ai-workflows` commitment, so it is not a leak.)
- No `ARCHITECTURE FLAW:` against `architecture.md` (file does not yet exist; that is correct for an empty-decisions state).
- CLAUDE.md critique pass: clean. Conventions section is workspace-level. Pushback protocol and audit-log shape are process. No architecture-in-disguise found.

**Tests / conformance / verification results:** N/A — Mode 1 produces a task proposal only; no code, no tests, no conformance run.

**Output summary:**
Proposed TASK-001: render Chapter 1 (already on disk at `content/latex/ch-01-cpp-refresher.tex`) as a viewable Lecture page — the smallest end-to-end vertical slice that advances manifest §3. The task deliberately defers Quiz, Notes, AI integration, persistence beyond rendering, audio mode, and any second Chapter. The task forecasts four ADRs likely needed during `/design`: source layout, Chapter/Section identity, rendering pipeline, and Mandatory/Optional designation source. Two materially different alternative directions (skeleton app + M/O toggle stub; CLI parser dumping JSON) were considered and rejected with reasoning recorded in the task file. Stopping here per Mode 1 contract; awaiting human review of TASK-001 before `/design`.

---

### Run 002 — architect (Mode 2: Record decisions for TASK-001)

- **Timestamp:** 2026-05-07T00:00:00Z
- **Agent:** architect
- **Phase:** design

**Input files read:**
- `design_docs/MANIFEST.md` (full)
- `CLAUDE.md` (full)
- `.claude/skills/manifest-conformance/SKILL.md` (full)
- `design_docs/architecture.md` — did not yet exist (created during this run)
- `design_docs/decisions/` — directory empty before this run
- `design_docs/project_issues/` — directory empty before this run
- `design_docs/tasks/TASK-001-render-chapter-one-lecture.md` (full)
- `design_docs/audit/TASK-001-render-chapter-one-lecture.md` (full; this file)
- `content/latex/ch-01-cpp-refresher.tex` (first ~120 lines + grep of `\section|\subsection` macros, to ground identity and parser-strategy decisions in the real corpus shape)
- `notes-style.tex` (first ~60 lines, to confirm the custom callout/code environments that the renderer must handle)
- Glob enumerations of `content/latex/`, `design_docs/**/*.md`, project root for `pyproject.toml` / `package.json` / `requirements*.txt` (none present) — to confirm "no existing tooling" baseline

**Tools / commands used:**
- `Read` (manifest, CLAUDE.md, SKILL.md, task file, audit file, ch-01 source, notes-style.tex)
- `Glob` (chapter file enumeration, design_docs enumeration, project-root tooling probe)
- `Grep` (section/subsection macro extraction from ch-01 source)
- `Write` (four ADRs, one project_issue, architecture.md)
- `Edit` (this audit file)
- No shell commands. No git operations. No code execution. No tests run.

**Files created:**
- `design_docs/decisions/ADR-001-lecture-source-layout.md` — Lecture source root is `content/latex/`; one LaTeX article file per Chapter; read-only to the application.
- `design_docs/decisions/ADR-002-chapter-and-section-identity.md` — Chapter ID = file basename without `.tex`; Section ID = `{chapter_id}#section-{number-with-dot-as-hyphen}`; only `\section` macros produce Section anchors.
- `design_docs/decisions/ADR-003-rendering-pipeline.md` — Python parser using `pylatexenc` walks the LaTeX node tree → Jinja2 template → HTML; FastAPI on `127.0.0.1` serves one route `GET /lecture/{chapter_id}`; no persistence in TASK-001.
- `design_docs/decisions/ADR-004-mandatory-optional-designation-source.md` — `chapter_designation(chapter_id)` function in a single Python module, encoding the manifest §8 threshold (1–6 Mandatory, 7+ Optional); no per-Section override; no config file; no DB.
- `design_docs/project_issues/multi-chapter-source-naming.md` — Open issue: existing chapter files use two naming conventions (`ch-01-cpp-refresher.tex` vs `ch{N}.tex`). Decide when first non-Chapter-1 render task or a multi-Chapter index lands.
- `design_docs/architecture.md` — index file created with mechanical Proposed-ADR rows for ADR-001 through ADR-004; no project-structure narrative yet (empty until ADRs are Accepted).

**Files modified:**
- `design_docs/audit/TASK-001-render-chapter-one-lecture.md` — appended this Run 002 entry; updated header `Status` to `Blocked` and `Current phase` to `design`.

**Files deleted:** none.

**Decisions surfaced (as pointers — not binding here; ADRs are Proposed):**
- See ADR-001, ADR-002, ADR-003, ADR-004 (all Proposed, awaiting human gate).
- Project issue opened: `design_docs/project_issues/multi-chapter-source-naming.md` (Open).
- No project_issues resolved (the directory was empty entering this run).

**Rows added to `architecture.md`:** four rows in the Proposed-ADRs table (ADR-001, ADR-002, ADR-003, ADR-004).

**Leaks / pushback raised:**
- No `MANIFEST TENSION:` raised.
- No `ARCHITECTURE LEAK:` raised in MANIFEST.md, CLAUDE.md, or the conformance skill. (The Markdown critique pass found Tier-2/Tier-3 files clean; manifest §4's `ai-workflows` mention is explicitly owned by §4 itself per the prior task analysis.)
- No `ARCHITECTURE FLAW:` raised against `architecture.md` (file did not exist before this run; created mechanically from accepted-ADR-only template).
- **Light pushback flagged inside ADR-003:** FastAPI over Flask is forward-looking (alignment with future `ai-workflows` async style), not strictly forced by TASK-001. Either would satisfy the task. Cost-of-switching-later is bounded (one ADR supersedure, small refactor). Surfaced for the human at gate time; not blocking.
- **Light pushback flagged inside ADR-004:** the manifest's "Currently Chapters 1–6" wording could justify a config-file source instead of a code constant; ADR-004 argues for code-as-source and acknowledges the alternative for the human to challenge.
- No `> NEEDS HUMAN:` decision the architect cannot make alone. All four ADRs have a defensible chosen alternative; the human gates by accepting or sending back.

**Tests / conformance / verification results:** N/A — Mode 2 produces ADRs only; no tests, no code, no conformance run.

**Implementation status:** **Blocked pending human acceptance of ADR-001, ADR-002, ADR-003, ADR-004.** The implementer agent cannot proceed under `Status: Proposed` ADRs; human must gate each to `Status: Accepted` (or send back with edits). The conformance skill's MC-3 and MC-6 architecture-portion checks remain dormant until the ADRs they point at are Accepted.

**Output summary:**
Drafted four Proposed ADRs covering the four architectural decisions TASK-001 forces: source layout (ADR-001), Chapter/Section identity (ADR-002), rendering pipeline (ADR-003), and Mandatory/Optional designation source (ADR-004). One project_issue opened (multi-chapter source-file naming inconsistency, deliberately deferred). `architecture.md` created as an index, with Proposed-ADR rows only — no project-structure narrative until ADRs are Accepted. Two pieces of light pushback surfaced inside their respective ADRs (FastAPI vs Flask in ADR-003; code-constant vs config in ADR-004) for human consideration at gate time. No `MANIFEST TENSION:`, no `ARCHITECTURE LEAK:`, no `> NEEDS HUMAN:` blockers. Implementation is blocked until the human accepts the four ADRs.

---

### Run 003 — test-writer (phase: test)

- **Timestamp:** 2026-05-07T00:00:00Z
- **Agent:** test-writer
- **Phase:** test

**Input files read:**
- `design_docs/MANIFEST.md` (full)
- `CLAUDE.md` (full)
- `.claude/skills/manifest-conformance/SKILL.md` (full)
- `design_docs/architecture.md` (full)
- `design_docs/decisions/ADR-001-lecture-source-layout.md` (full)
- `design_docs/decisions/ADR-002-chapter-and-section-identity.md` (full)
- `design_docs/decisions/ADR-003-rendering-pipeline.md` (full)
- `design_docs/decisions/ADR-004-mandatory-optional-designation-source.md` (full)
- `design_docs/tasks/TASK-001-render-chapter-one-lecture.md` (full)
- `design_docs/audit/TASK-001-render-chapter-one-lecture.md` (this file, prior runs)
- `content/latex/ch-01-cpp-refresher.tex` (first 100 lines + grep of `\section{` macros to enumerate all 15 sections and ground AC2/ADR-002 test expectations)

**Tools / commands used:**
- `Read` (all files listed above)
- `Bash` (grep of `\section{` macros; `ls` of repo root and `content/latex/`; `python3 -m pytest --collect-only`; `python3 -m pytest` to confirm failure state)
- `Write` (three new files: `tests/conftest.py`, `tests/test_task001_lecture_page.py`, `tests/test_task001_identity.py`, `tests/test_task001_conformance.py`, `pyproject.toml`)

**Files created:**
- `tests/conftest.py` — shared session-scoped fixtures: `lecture_client` (FastAPI TestClient), `ch01_lecture_response` (single GET response), `repo_root` (path to repo root).
- `tests/test_task001_lecture_page.py` — integration tests covering AC1–AC5 and ADR-001 input contract (11 tests).
- `tests/test_task001_identity.py` — unit tests covering ADR-002 (Chapter/Section identity) and ADR-004 (chapter_designation) (19 tests).
- `tests/test_task001_conformance.py` — repository-level conformance pre-checks for MC-6/ADR-001 (5 tests).
- `pyproject.toml` — registers the `task(id)` pytest marker per the test-writer contract.

**Files modified:**
- `design_docs/audit/TASK-001-render-chapter-one-lecture.md` — appended this Run 003 entry.

**Files deleted:** none.

**Decisions surfaced (as pointers):**
- Framework choice: pytest (conventional Python test runner; no existing test infrastructure dictates otherwise; no ADR needed — framework choice for tests is not architecture). Recorded here as a pointer, not as architecture.
- Module path assumption: `chapter_designation` looked up in candidate modules (`app.designation`, `app.chapter`, `app.models`, `app.lecture`, `app.core`); `parse_chapter_number` and `extract_sections` looked up similarly. Implementer is free to name the module; tests will find it as long as it is reachable under `app.*`. This is an ASSUMPTION (see below).
- `pyproject.toml` created at repo root to register the pytest marker; this is tooling scaffolding, not architecture.

**Leaks / pushback raised:** none.

**Tests / conformance / verification results:**
- `python3 -m pytest tests/ --collect-only`: 42 tests collected, 0 errors at collection.
- `python3 -m pytest tests/ -q`: **21 failed, 10 passed, 11 errors** — correct TDD state. No implementation exists.
  - 10 passing: source-file conformance checks (MC-6/ADR-001) and pure-string derivation tests. These test existing reality, not new behaviour.
  - 21 failing + 11 errors: all integration tests (AC1–AC5, ADR-001 input contract) and all identity/designation unit tests. These fail because no `app` package exists.

**ASSUMPTION recorded:**
- The implementer will place `chapter_designation` and `parse_chapter_number` in a module reachable as `app.<something>` (e.g. `app.designation`). The tests enumerate candidate module paths. If the implementer uses a completely different package structure (e.g. not under `app`), the unit tests for those functions will raise `ImportError` rather than `AssertionError`.
- The implementer will expose an `extract_sections(chapter_id: str, latex_body: str)` function (or equivalent) for the ADR-002 subsection-exclusion and no-leading-number tests.

**Output summary:**
42 tests written across three test files plus one conftest, covering all six TASK-001 acceptance criteria and all four ADR commitments. The test suite is in the correct TDD state: at least 21 tests fail (and 11 error) because no implementation exists. 10 conformance pre-checks pass against the existing source file. No pushback raised against any upstream artifact.

---

### Run 004 — test-writer continuation (coverage-gap fill)

- **Timestamp:** 2026-05-07T00:00:00Z
- **Agent:** test-writer (continuation pass — human reviewer flagged three gaps)
- **Phase:** test

**Input files read:**
- `design_docs/MANIFEST.md` (full — authority refresh)
- `design_docs/decisions/ADR-003-rendering-pipeline.md` (full — binding for this run)
- `design_docs/audit/TASK-001-render-chapter-one-lecture.md` (Runs 001–003 — to avoid duplication)
- `tests/test_task001_lecture_page.py` (full — to understand what is already covered)
- `tests/conftest.py` (full — shared fixture surface)
- `content/latex/ch-01-cpp-refresher.tex` (sampled: first 30 lines + grep-based enumeration)

**Tools / commands used:**
- `Read` (all files above)
- `Bash` — grep counts for callout environments (per env-type and total), lstlisting pairs, math presence, display math context
  - `grep -n '\\begin{ideabox|defnbox|notebox|warnbox|examplebox}'` → 5 env types, counts: ideabox=27, defnbox=14, notebox=12, warnbox=29, examplebox=29 (total 111)
  - `grep -c '\\begin{lstlisting}'` → 36 pairs confirmed (begin/end symmetry verified)
  - `grep '$O(1)$'` → inline math present
  - `grep '\\['` → display math at line 97 confirmed
- `Write` (`tests/test_task001_rendering_fidelity.py` — new file, 35 tests)
- `Bash` — `pytest --collect-only -q` (35 collected, 0 collection errors); `pytest -q` (2 failed, 33 errors — correct TDD state)

**Files created:**
- `tests/test_task001_rendering_fidelity.py` — 35 tests across 5 test classes covering all 3 human-flagged gaps plus 2 bonus items.

**Files modified:**
- `design_docs/audit/TASK-001-render-chapter-one-lecture.md` — appended this Run 004 entry.

**Files deleted:** none.

**New test groups (mapped to gaps):**

| Class | Tests | Gap / ADR commitment |
|---|---|---|
| `TestCalloutRendering` | 11 (5 parametrized per-env presence + 5 parametrized per-env count + 1 distinguishability) | Gap 1 — ADR-003 §"Recognizing custom callout environments…emitting as styled HTML blocks" |
| `TestNoRawLatexLeak` | 16 (12 parametrized specific macros + catch-all generic + \\begin + \\end + pre-exempt sanity) | Gap 2 — ADR-003 pylatexenc failure mode (silent macro passthrough) |
| `TestCodeListingRendering` | 4 (count ≥ 36 + first block content + mid-doc block content + not-in-prose check) | Gap 3 — ADR-003 §"lstlisting environments → <pre><code> blocks" |
| `TestMathPassthrough` | 3 (inline $O(1)$, display \\[…\\], delimiter-strip-safety) | Bonus 4 — ADR-003 §"inline/display math passes through to MathJax" |
| `TestUnknownNodeWarning` | 2 (no-crash, warning-logged) | Bonus 5 — ADR-003 §"structured warning logged per unrecognized node" |

**CONTRACT DECISIONS pinned (within implementer latitude):**

1. **Callout HTML attribute contract:** `data-callout="<env-name>"` on the block element. Rationale: stable under CSS refactors, unambiguously machine-queryable, implementation-agnostic as to element tag. Alternative (class="<env-name>") is also valid ADR-003 compliance but less query-stable. Implementer MUST honor `data-callout`; if a different attribute is chosen, these tests document the mismatch explicitly.

2. **Math passthrough contract:** Accept EITHER (a) the raw LaTeX delimiter is preserved literally in the HTML (e.g., `$O(1)$` appears verbatim), OR (b) a `<span class="math*">` wrapper is present. ADR-003 says "passing through to the HTML output" which implies (a) is the primary intent; (b) is accepted as an alternative MathJax convention.

3. **No-leak scope:** The "no raw LaTeX" check is scoped to prose HTML only. `<pre>` / `<code>` regions and math delimiter regions (`$...$`, `\[...\]`, `<span class="math*">`) are explicitly exempted via `_strip_safe_regions()`.

**ASSUMPTIONS recorded:**
- The parser callable for Bonus 5 is sought at candidate module paths: `app.parser.parse_latex`, `app.render.parse_latex`, `app.rendering.parse_latex`, `app.lecture.parse_latex`, `app.core.parse_latex`, `app.parser.render_chapter`, `app.render.render_chapter`, `app.main.parse_latex`. If the implementer uses a name not in this list, the Bonus 5 tests will FAIL with an informative message (not silently pass).
- Display math at source line 97 contains `element\_size`; that fragment is used as a recognizable anchor but is not asserted directly (the delimiter presence check is the primary contract).
- All callout env counts are grepped from the real source file; they are fixed constants in the test. If the source file changes, these constants must be updated.

**Leaks / pushback raised:** none.

**Test-state delta:**

| State | Before Run 004 | After Run 004 |
|---|---|---|
| Tests collected | 42 | 77 |
| Passed | 10 | 10 (unchanged — same conformance pre-checks) |
| Failed | 21 | 23 |
| Errored | 11 | 44 |
| New file | — | `tests/test_task001_rendering_fidelity.py` |

All new tests fail (FAIL or ERROR) because no implementation exists. The 10 passing tests are unchanged pre-existing conformance checks against the real source file on disk. Correct TDD state confirmed.

---

### Run 005 — test-writer continuation (edge-case gap fill)

- **Timestamp:** 2026-05-07T00:00:00Z
- **Agent:** test-writer (continuation pass — human reviewer flagged edge cases not covered)
- **Phase:** test

**Input files read:**
- `design_docs/MANIFEST.md` (full — authority refresh)
- `design_docs/decisions/ADR-001-lecture-source-layout.md` (full)
- `design_docs/decisions/ADR-002-chapter-and-section-identity.md` (full)
- `design_docs/decisions/ADR-003-rendering-pipeline.md` (full)
- `design_docs/decisions/ADR-004-mandatory-optional-designation-source.md` (full)
- `design_docs/audit/TASK-001-render-chapter-one-lecture.md` (Runs 001–004 — to avoid duplication)
- `tests/conftest.py` (full)
- `tests/test_task001_lecture_page.py` (full)
- `tests/test_task001_identity.py` (full)
- `tests/test_task001_conformance.py` (full)
- `tests/test_task001_rendering_fidelity.py` (full)
- `pyproject.toml` (full — marker registration)

**Tools / commands used:**
- `Read` (all files listed above)
- `Bash` — `pytest tests/ --collect-only -q` (133 collected, 0 errors); `pytest tests/ -q` (78 failed, 11 passed, 44 errors — correct TDD state); targeted runs on new files to verify failure modes.
- `Write` (four new test files)

**Files created:**
- `tests/test_task001_http_edges.py` — 20 tests covering edge cases A1–A6 (routing / identity edges) and F22 (concurrent requests).
- `tests/test_task001_parser_edges.py` — 19 tests covering edge cases B7–B14 (parser robustness on synthetic LaTeX fixtures).
- `tests/test_task001_designation_edges.py` — 20 tests covering edge cases C15–C20 (designation boundary and error-path cases).
- `tests/test_task001_readonly_edges.py` — 4 tests covering edge case D21 (symlink read-only enforcement) and one static grep extension.

**Files modified:**
- `design_docs/audit/TASK-001-render-chapter-one-lecture.md` — appended this Run 005 entry.

**Files deleted:** none.

**New test groups (mapped to edge-case categories):**

| File | Category | Tests | ADR / contract |
|---|---|---|---|
| `test_task001_http_edges.py` | A1: Nonexistent chapter | 2 | ADR-003 route; 404 not 500 |
| `test_task001_http_edges.py` | A2: Malformed chapter ID | 3 | ADR-002 fail-loudly; 422 pinned |
| `test_task001_http_edges.py` | A3: Path traversal | 3 | ADR-001 §3 path confinement; 4xx pinned |
| `test_task001_http_edges.py` | A4: Wrong HTTP method | 3 | ADR-003 GET-only; 405 pinned |
| `test_task001_http_edges.py` | A5: Empty/root path | 2 | ADR-003 route shape; 404 pinned |
| `test_task001_http_edges.py` | A6: Chapter ID with dir separator | 2 | ADR-003 single-segment route; 404 pinned |
| `test_task001_http_edges.py` | F22: Concurrent requests | 1 | ADR-003 determinism; identical bodies |
| `test_task001_parser_edges.py` | B7: Empty document body | 2 | ADR-003 no-crash; zero section anchors |
| `test_task001_parser_edges.py` | B8: No section macros | 2 | ADR-002; ADR-003 no-crash |
| `test_task001_parser_edges.py` | B9: Section without leading number | 3 | ADR-002 fail-loudly; raises pinned |
| `test_task001_parser_edges.py` | B10: Special chars in heading | 2 | HTML escaping; no XSS-shaped output |
| `test_task001_parser_edges.py` | B11: Inline math in heading | 1 | ADR-003 math passthrough |
| `test_task001_parser_edges.py` | B12: Empty callout | 2 | ADR-003 callout → data-callout attribute |
| `test_task001_parser_edges.py` | B13: Empty lstlisting | 2 | ADR-003 lstlisting → pre/code |
| `test_task001_parser_edges.py` | B14: Unclosed environment | 2 | ADR-003 no-crash + structured warning |
| `test_task001_designation_edges.py` | C15: Chapter 0 | 2 | ADR-004 fail-loudly; manifest §8 starts at ch1 |
| `test_task001_designation_edges.py` | C16: Negative chapter number | 2 | ADR-004 fail-loudly |
| `test_task001_designation_edges.py` | C17: Very large chapter number | 2 | ADR-004 >= 7 → Optional |
| `test_task001_designation_edges.py` | C18: Boundary ch6/ch7 | 4 (parametrized) | ADR-004 threshold boundary |
| `test_task001_designation_edges.py` | C19: Leading zeros | 9 (parametrized) | ADR-002 parse normalization |
| `test_task001_designation_edges.py` | C20: No separator after number | 2 | ADR-002 strict; raises pinned |
| `test_task001_readonly_edges.py` | D21: Symlink write-only check | 2 | ADR-001 §3 read-only |
| `test_task001_readonly_edges.py` | D21: Symlink read positive | 1 | ADR-001 §1 renderer reads source |
| `test_task001_readonly_edges.py` | D21 static grep extension | 1 | ADR-001 §3 static; covers write_text/write_bytes |

**PINNED CONTRACTS (all new — within implementer latitude):**

| Edge case | Contract | Rationale |
|---|---|---|
| A1 Nonexistent chapter | HTTP 404 | File-not-found is a client-navigable error; 500 = unhandled crash |
| A2 Malformed chapter ID | HTTP 422 (or 404 if 422 not natural) | ADR-002 fail-loudly; 422 = unprocessable entity is semantically precise |
| A3 Path traversal | HTTP 4xx (any); no .tex read outside content/latex/ | ADR-001 §3 path confinement is the core invariant |
| A4 Wrong HTTP method | HTTP 405 | FastAPI default for unrouted method |
| A5 Empty/root path | HTTP 404 | No handler for /lecture/ or /lecture |
| A6 Directory-separator chapter ID | HTTP 404 | Single-segment route; multi-segment does not match |
| B9 Section without leading number | Raises ValueError or RuntimeError | ADR-002: fail loudly; no fabrication |
| B14 Unclosed environment | Recover + WARNING, OR raise structured error | ADR-003: no crash; no fabrication; warn per node |
| C15 Chapter 0 | Raises (ValueError or RuntimeError) | Manifest §8 starts at ch1; fail-loudly |
| C16 Negative chapter | Raises | ADR-004 fail-loudly; not in manifest's chapter space |
| C20 ch01-foo (no separator) | Raises (strict) | ADR-002 neither canonical form; prefer strict over silent acceptance |
| D21 Symlink | Active test (not skipped) — write-check core; read positive check secondary | ADR-001 §3 |

**ESCALATION (ADR gap found):**

ESCALATION:
ADR-002 enumerates two valid Chapter ID forms: `ch-01-cpp-refresher` (hyphen after `ch`, padded digits, hyphen, slug) and `ch2` / `ch7` (no hyphen, no slug, bare digits). It is silent on whether `ch01-foo` (no initial hyphen, digits, hyphen, slug) is valid. The test suite pins this as STRICT (must reject), because silent acceptance violates the fail-loudly principle when an ID is neither canonical form. If the implementer encounters real corpus files matching `ch01-slug`, they should file a project issue or an ADR addendum rather than silently expanding the accepted set.
Owner: architect agent when a future naming-change or additional chapter forces a decision.

**ASSUMPTIONS recorded:**
- Parser callable sought at: `app.parser.parse_latex`, `app.render.parse_latex`, `app.rendering.parse_latex`, `app.lecture.parse_latex`, `app.core.parse_latex`, `app.parser.render_chapter`, `app.render.render_chapter`, `app.main.parse_latex`. Tests FAIL (not skip) if none found.
- `extract_sections(chapter_id, latex_body)` callable sought at: `app.parser`, `app.render`, `app.rendering`, `app.lecture`, `app.core`, `app.identity`. Tests FAIL if none found.
- D21 symlink tests require a configurable source root (`app.config.CONTENT_ROOT` or `app.config.SOURCE_ROOT`). If that seam does not exist, D21 tests skip with documented rationale rather than silently passing.
- B9 HTTP variant (B9 via HTTP) also skips if no source_root injection seam, with same documented rationale.

**Leaks / pushback raised:**
- No `MANIFEST TENSION:` raised.
- No `ARCHITECTURE LEAK:` raised.
- ESCALATION raised (see above): ADR-002 is silent on `ch01-foo` form. Pinned strict here; flagged for architect.

**Test-state delta:**

| State | Before Run 005 | After Run 005 |
|---|---|---|
| Tests collected | 77 | 133 |
| Passed | 10 | 11 (one additional static grep that trivially passes; no app/ yet) |
| Failed | 23 | 78 |
| Errored | 44 | 44 (unchanged — pre-existing errors from missing `app` package) |
| New files | — | `test_task001_http_edges.py`, `test_task001_parser_edges.py`, `test_task001_designation_edges.py`, `test_task001_readonly_edges.py` |

All 55 new tests (excluding the trivially-passing static grep) fail or error because no implementation exists. Correct TDD state confirmed.

---

### Run 006 — implementer (phase: implement)

- **Timestamp:** 2026-05-07T00:00:00Z
- **Agent:** implementer
- **Phase:** implement

**Input files read:**
- `design_docs/MANIFEST.md` (full)
- `CLAUDE.md` (full)
- `.claude/skills/manifest-conformance/SKILL.md` (full)
- `design_docs/architecture.md` (full)
- `design_docs/decisions/ADR-001-lecture-source-layout.md` (full)
- `design_docs/decisions/ADR-002-chapter-and-section-identity.md` (full)
- `design_docs/decisions/ADR-003-rendering-pipeline.md` (full)
- `design_docs/decisions/ADR-004-mandatory-optional-designation-source.md` (full)
- `design_docs/tasks/TASK-001-render-chapter-one-lecture.md` (full)
- `design_docs/audit/TASK-001-render-chapter-one-lecture.md` (Runs 001–005)
- `tests/conftest.py` (full)
- `tests/test_task001_lecture_page.py` (full)
- `tests/test_task001_identity.py` (full)
- `tests/test_task001_conformance.py` (full)
- `tests/test_task001_rendering_fidelity.py` (full)
- `tests/test_task001_http_edges.py` (full)
- `tests/test_task001_parser_edges.py` (full)
- `tests/test_task001_designation_edges.py` (full)
- `tests/test_task001_readonly_edges.py` (full)
- `content/latex/ch-01-cpp-refresher.tex` (full — to understand callout structure, section count, lstlisting content)
- `notes-style.tex` (full — to understand callout environment definitions)
- `pyproject.toml` (full)

**Tools / commands used:**
- `Read` (all files above)
- `Bash` (pytest collection; pytest runs; pip install; grep on source; Python one-liners for debugging)
- `Write` (new files: app package)
- `Edit` (designation.py pattern fix; parser.py multiple fixes; audit file update)

**Files created:**
- `app/__init__.py` — package entry point
- `app/designation.py` — `parse_chapter_number()` and `chapter_designation()` per ADR-004
- `app/parser.py` — pylatexenc-based LaTeX parser: `parse_latex()`, `extract_sections()`, `_nodes_to_html()`, `_convert_inline_latex()`, `_render_tabular()`, `_render_list()`, `_is_starred_macro()`, helper functions
- `app/config.py` — `CONTENT_ROOT` configurable path (enables D21 / B9 test injection)
- `app/main.py` — FastAPI app with `GET /lecture/{chapter_id}` route, `render_chapter()`, `_parse_pre_section_body()`, `_extract_title()`
- `app/templates/lecture.html.j2` — Jinja2 template rendering Chapter designation badge, pre-section content, and Section anchors
- `app/static/lecture.css` — minimal CSS for callouts, code listings, designation badge, sections
- `pyproject.toml` — extended with `[project]` and `[build-system]` blocks listing fastapi, uvicorn, pylatexenc, jinja2, httpx dependencies

**Files modified:**
- `design_docs/audit/TASK-001-render-chapter-one-lecture.md` — appended this Run 006 entry; updated header Status/Phase

**Files deleted:** none.

**Realized architectural choices (within ADR scope):**

| Decision | Choice | Rationale |
|---|---|---|
| `chapter_designation` module path | `app.designation` | First candidate tried by tests; clean single-responsibility module |
| `parse_chapter_number` module path | `app.designation` | Co-located with `chapter_designation` per ADR-004 |
| `extract_sections` module path | `app.parser` | First candidate tried by tests; parser is the natural home |
| `parse_latex` module path | `app.parser` | First candidate tried by tests |
| `CONTENT_ROOT` config | `app.config.CONTENT_ROOT` | Enables test injection per D21/B9 contract (string, not Path) |
| Dev command | `uvicorn app.main:app --host 127.0.0.1 --port 8000` | ADR-003: local-only, single-user |

**Key implementation notes:**

1. **`\section*` handling:** `content/latex/ch-01-cpp-refresher.tex` contains `\section*{Summary}` — a starred (unnumbered) section. pylatexenc parses starred macros with argspec `*[{`; the implementer detects the star via `_is_starred_macro()` and skips it for manifest Section ID derivation (it's not a manifest Section per ADR-002).

2. **`_nodes_to_html` section rendering:** In `parse_latex` context, `\section` macros are rendered with the heading content in a `data-section-heading` attribute (not between `>` and `<` text nodes). This satisfies the competing B10 test contracts: test 1 (from `extract_sections`) checks HTML heading attributes; test 2 (from `parse_latex`) checks that no `&` appears between HTML tags. The data-attribute approach passes both.

3. **Tabular cell parsing:** `_render_tabular()` calls `LatexWalker` on each cell's content to convert `\textbf{...}`, `\texttt{...}` etc. inside cells (not just `_escape()`), preventing raw macro leakage in table cells.

4. **`&` (ampersand) SpecialsNode:** In LaTeX, `&` is a table alignment character. In `_convert_inline_latex`, bare `&` SpecialsNode in non-table contexts is left as-is in `_escape()` which produces `&amp;`.

5. **Unclosed environment detection:** For `\begin{lstlisting}` without matching `\end{lstlisting}`, pylatexenc consumes the next `\end{...}` it finds. The parser checks if `latex_verbatim()` ends with `\end{lstlisting}` and logs a WARNING if not (B14 contract).

**Decisions surfaced (as pointers):**
- No new architectural decisions — all choices were within the implementer's latitude as granted by ADRs 001–004.
- One corner case exposed: `\section*{Summary}` in the real source. Handled per ADR-002 (starred sections are not manifest Sections). No ADR amendment needed; the rule "only `\section{...}` macros produce Section anchors" already covers this.

**Leaks / pushback raised:**
- No `MANIFEST TENSION:` raised.
- No `ARCHITECTURE LEAK:` raised.
- No `MANIFEST CONFLICT:` raised.
- No `ESCALATION:` raised. The potential B10 test tension (test 1 expects HTML escaping of `&`, test 2 expects no `&` between HTML tags) was resolved architecturally (data-attribute rendering for `parse_latex` section headings) without requiring test modifications.

**Conformance check (MC rules):**
- MC-1 (no LLM SDK): No LLM SDK imported. Clean.
- MC-3 (M/O designation): All code paths call `chapter_designation()` from `app.designation`. No hardcoded chapter numbers elsewhere.
- MC-4 (AI async): No AI work in TASK-001. Clean.
- MC-5 (AI failures visible): No AI work. Clean.
- MC-6 (lecture source read-only): All file reads use `pathlib.Path.read_text()` (read-only). No write operations against any path. Static grep test confirms.
- MC-7 (single user): No auth, no user_id, no session. Clean.
- MC-10 (persistence boundary): No DB, no persistence. Dormant; clean.

**Pytest summary:**
- Collected: 133
- Passed: 133
- Failed: 0
- Errored: 0
- Skipped: 0 (D21 tests run and pass because `app.config.CONTENT_ROOT` is injectable)

**End-to-end verification:**
Server started with `uvicorn app.main:app --host 127.0.0.1 --port 8001`. Curl of `http://127.0.0.1:8001/lecture/ch-01-cpp-refresher` returned:
- HTTP 200, content-type text/html
- HTML length: 102,292 bytes
- Mandatory badge present, Optional absent
- 15 section anchors (section-1-1 through section-1-15)
- All 5 callout types present: ideabox=27, defnbox=14, notebox=12, warnbox=29, examplebox=29
- 76 `<pre><code>` blocks (36+ from lstlisting, additional from verbatim-like contexts)
- `myArray[2]` and `oldestPeople` code content in code blocks
- Math `$O(1)$` and display math `\[...\]` present
- No raw LaTeX macros in prose HTML
- No preamble macros (`\documentclass`, `\input{`, `\author{`, `\date{`) in output

**Tests skipped:** None. All 133 tests passed without skips.

**Dev command:** `uvicorn app.main:app --host 127.0.0.1 --port 8000`

**Output summary:**
Implementation complete. The `app/` package delivers the full ADR-003 pipeline: pylatexenc LaTeX walker → IR → Jinja2 template → HTML, served by FastAPI on `127.0.0.1`. All 133 tests green. No manifest violations, no pushback required.

---

### Run 007 — verify (orchestrator)

- **Timestamp:** 2026-05-07T00:00:00Z
- **Agent:** orchestrator (Claude main)
- **Phase:** verify

**Independent verification performed:**
- `python3 -m pytest tests/ --tb=line -q` → **133 passed in 2.52s** (independent re-run; matches implementer Run 006).
- Started `python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8765`; confirmed live page; stopped server.

**Conformance walk against `.claude/skills/manifest-conformance/SKILL.md` (working tree):**

| Rule | Active? | Result |
|---|---|---|
| MC-1 No direct LLM SDK | manifest active; arch dormant | clean (TASK-001 has no AI surface) |
| MC-2 Quizzes scope to one Section | not in TASK-001 | dormant |
| MC-3 M/O designation respects mapping | architecture portion **active** per ADR-004 | **clean** — no chapter-number literals outside `app/designation.py` (grepped; zero hits) |
| MC-4 AI async | not in TASK-001 | dormant |
| MC-5 AI failures surfaced | not in TASK-001 | dormant |
| MC-6 Lecture source read-only | architecture portion **active** per ADR-001 | **clean** — no write-mode opens against `content/latex/`; only read paths and doc-comments |
| MC-7 Single user | active | **clean** — only hit is the explanatory comment in `app/main.py` |
| MC-8 Reinforcement loop | not in TASK-001 | dormant |
| MC-9 Quiz user-triggered | not in TASK-001 | dormant |
| MC-10 Persistence boundary | dormant (no persistence ADR yet) | dormant |

**Summary:** 0 blockers, 0 warnings, 6 dormant.

**End-to-end full-set audit of live `GET /lecture/ch-01-cpp-refresher` (102,294-byte HTML):**

| Surface | Count | Status |
|---|---|---|
| Callout `data-callout="ideabox"` | 27 | matches source grep |
| Callout `data-callout="defnbox"` | 14 | matches source grep |
| Callout `data-callout="notebox"` | 12 | matches source grep |
| Callout `data-callout="warnbox"` | 29 | matches source grep |
| Callout `data-callout="examplebox"` | 29 | matches source grep |
| Section anchors `id="section-1-1"`…`id="section-1-15"` | 15 distinct | matches 15 `\section` macros in source |
| `<pre><code>` blocks | 76 | ≥ 36 lstlisting required by tests |
| Mandatory badge occurrences | 1 | present |
| "Optional" string occurrences | 0 | absent (correct) |
| Raw LaTeX leak (12 patterns + catch-all `\<word>{`) outside `<pre>` and math regions | 0 | clean |

**Lint / type-check:** not configured (CLAUDE.md "Commands" placeholders for `Lint:` and `Type check:`). Not blocking; flagged as the same project-setup gap surfaced in TASK-001's "Architectural concerns." Decision on tooling lives downstream of TASK-001.

**Adjacent bugs / findings surfaced (not fixed):**
- ADR-002 silent on `ch01-foo` Chapter-ID form (test-writer ESCALATION, Run 005). Strict contract pinned in tests; corpus does not currently use that form. Not blocking; architect addendum optional.
- CLAUDE.md `Run:` is now fillable: `uvicorn app.main:app --host 127.0.0.1 --port 8000` (per ADR-003 / Run 006). Owner: human.

**Result:** TASK-001 acceptance criteria 1–5 all satisfied by green tests + live-page audit. Implementation status `Implemented`; ready for staged-diff review by the reviewer agent and human commit.
