# Notification mechanism

**Status:** Open
**Surfaced:** 2026-05-07 (bootstrap)
**Decide when:** First task involving an async ai-workflows Run (grading or generation).

## Question
How does the app surface a Notification when an `ai-workflows` Run completes? The manifest (§6) mandates async-only AI work; the user must see Grade / Quiz / Audio results when ready, without polling manually.

## Options known
- **Server-Sent Events (SSE).** One-way push from server to browser. Native to HTMX via `hx-sse`.
- **HTMX polling on `/notifications`.** Periodic `hx-trigger="every Ns"`. Simple, slightly chatty.
- **Long-poll.** Server holds connection open until something changes. Heaviest of the three.

## Constraints from the manifest
- Async-only — no synchronous return of Grade/Question/Audio (§6).
- No silent fallbacks — workflow failure must surface to the user, not be papered over (§7).

## Resolution
When resolved, capture as an ADR and mark this issue `Resolved by ADR-NNN`. The ADR should also state how workflow-failure notifications differ from success notifications, since "no silent fallbacks" applies.
