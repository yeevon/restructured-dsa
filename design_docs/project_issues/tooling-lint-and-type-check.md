# Project tooling — add a linter and a type-checker

**Status:** Open
**Surfaced:** 2026-05-08 (TASK-003 architect Mode-1 flagged CLAUDE.md placeholders) — recurring at every `/next` cycle since (TASK-004 → TASK-009 inclusive; fourth-recurrence noted in TASK-009 audit Run 001).
**Decide when:** low priority. Address either (a) when the codebase stops growing as fast and friction-per-suppression drops, or (b) when a defect surfaces that lint or type-checking would have caught and the cost-of-not-having-it becomes concrete. Not blocking on any task.

## Question

`CLAUDE.md` carries two unfilled placeholders in its Commands section:

```
- Lint: <project lint command>
- Type check: <project type-check command>
```

The placeholders are visible at every architect `/next` and conformance walk, but no defect has yet surfaced that lint or type-checking would have caught. Solo-developer project (MC-7 single user); no CI configured; all public functions already type-hinted by convention; test suite is broad (619 passing as of TASK-009). The question is whether the value of adding tooling exceeds the build-mode friction of suppression decisions on every new file.

## Options known

### Option A — Add `ruff` (linter only), defer type-checking

- **Why ruff:** fast (sub-second on this codebase), zero-dependency, catches real bugs (unused imports, undefined names, shadowed builtins, F-rules class). Replaces flake8 / isort / pyupgrade / pylint in a single tool. Stdlib-adjacent in the Python ecosystem.
- **Cost:** one `[tool.ruff]` block in `pyproject.toml`; an initial pass to fix or suppress existing warnings (expected: tens, not hundreds).
- **Pros:** catches mistakes that tests miss (dead code, name typos in conditionals never exercised, accidental shadowing). Cheap to maintain. No per-file decisions — config is global.
- **Cons:** small one-time cost to land. Adds another check the human runs before commit (or that a hook runs automatically).

### Option B — Add `ruff` + `mypy` (or `pyright`)

- **Why mypy/pyright:** the persistence layer just landed (`app/persistence/`), the parser is non-trivial (`app/parser.py`), and the Notes/Quiz/AI surfaces are growing. Type-checking catches a class of bugs (None-handling, dict-shape mismatches, route-handler signatures) that the test suite doesn't cover by construction.
- **Cost:** more invasive than ruff. Every new file becomes a typing-strictness decision; `Any` accumulates if not policed; third-party libs without stubs require `# type: ignore` or stub installation.
- **Pros:** catches a real class of defects. Forces public API discipline on the persistence package (already mostly there per ADR-022).
- **Cons:** high friction in build-mode. Each new feature pays a typing tax. Strictness level is itself an ADR-worthy decision (`--strict` vs. `--no-strict-optional` vs. default).

### Option C — Defer indefinitely

- **Pros:** zero cost. Tests + ADR discipline are doing the work.
- **Cons:** the CLAUDE.md placeholders remain a recurring `/next` flag. As the codebase grows past the Notes/Quiz vertical slices, the cost-of-not-having-tooling rises.

## Recommendation (architect's forecast at decide-time, not binding)

When this issue is picked up, the likely shape is **one ADR covering both**, with `ruff` Accepted (low-friction) and `mypy` Accepted-at-low-strictness (defer `--strict` to a future supersedure ADR). Followed by a small task: config in `pyproject.toml`, fix the initial warning batch, fill the two CLAUDE.md placeholders, run lint + type-check in the verify phase of every subsequent task.

The placeholder fill itself is **not architecture-on-spec** — it's the operational closing of a process gap. The ADR is needed to choose the tools (architecture-in-disguise risk: picking ruff over flake8 is a tooling decision but ratifying "we have a linter that runs in verify" is the actual architectural commitment).

## Cross-references

- `CLAUDE.md` §Commands (placeholders to fill)
- TASK-003 audit Run 001 (first surfacing as project-setup gap)
- TASK-009 audit Run 001 (fourth-recurrence note)
- ADR-022 §Schema (persistence package would benefit from mypy on the public API; not blocking)
