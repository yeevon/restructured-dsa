# Restructured CS 300

Single-user, locally-run learning web app for the SNHU CS-300 + MIT OCW augmented curriculum. See `design_docs/MANIFEST.md` for the locked product spec.

## Setup

```
uv sync
```

## Run the dev server

```
uv run uvicorn cs300.app:app --reload
```

Then open the seeded chapter at:

```
http://localhost:8000/chapters/ch-01-cpp-refresher/lecture
```

There is no landing page yet — the Chapter index is a later task. Navigate directly to a Chapter URL.

## Run the test suite, lint, and type-check

```
uv run pytest
uv run ruff check --fix && uv run ruff format
uv run mypy cs300/
```

## Curriculum content layout

LaTeX source lives under `content/latex/<chapter-id>.tex`. Chapter IDs follow the pattern `ch-NN-<slug>` (e.g., `ch-01-cpp-refresher`); see ADR-001. The shared style file (`notes-style.tex`) lives at the repo root so chapters can `\input{../../notes-style.tex}` from `content/latex/`.

## Project docs

- `design_docs/MANIFEST.md` — locked product spec (source of truth)
- `design_docs/architecture.md` — index of accepted ADRs
- `design_docs/decisions/` — individual ADRs
- `design_docs/project_issues/` — open architectural questions awaiting the right task
- `design_docs/tasks/` — current and historical task definitions
- `CLAUDE.md` — agent-facing project conventions
