# HTMX route testing strategy

**Status:** Open
**Surfaced:** 2026-05-07 (bootstrap)
**Decide when:** First non-trivial HTMX interaction surfaces (swap targets, OOB swaps, multi-step flows). Render-and-assert via `httpx` is sufficient until then.

## Question
How are HTMX routes tested?

## Options known
- **Render-and-assert via `httpx`.** Already the default per CLAUDE.md `## Stack`. Sufficient when the test only needs to verify the rendered HTML fragment.
- **Playwright (or similar headless-browser harness).** Worth adding only when assertions need to depend on HTMX-specific runtime behavior (swap targets, OOB swaps, hx-trigger composition, client-side state transitions).

## Resolution
This may stay open indefinitely if `httpx` keeps sufficing. If resolved, capture the trigger (the test that couldn't be expressed with `httpx`) in an ADR and mark this issue `Resolved by ADR-NNN`.
