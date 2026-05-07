# ADR-000: Baseline architecture decisions

**Status:** Accepted
**Date:** 2026-05-07
**Task:** bootstrap

## Context
CLAUDE.md was drafted with several architectural decisions already made (stack/frontend, LaTeX parser, tier routing, quiz scope, quiz size, quiz composition, question persistence, plus local-first interpretation). The reviewer agent flags structural decisions in the diff that lack ADR coverage. Without a baseline ADR, the very first task's diff would trigger that check against pre-decided context.

## Decision
The decided baseline lives in CLAUDE.md across `## Stack`, `## Tier routing`, `## Question persistence`, and `## Quiz composition`. Each line item in those sections is hereby imported as accepted architectural baseline and treated as if it were an Accepted ADR for the purpose of the reviewer's architecture-artifact check.

In addition, the following decision is part of the baseline but is not explicitly stated as a section in CLAUDE.md and is recorded here:

- **Local-first interpretation.** Local-first means data and lecture content live locally; the hosted-tier LLM provider is permitted because local hardware can't viably handle code grading. TTS provider is local OR hosted depending on the still-open TTS-provider question (to be decided when the first lecture-audio task is proposed).

No new ADR is required for code that exercises a baseline decision listed above.

## Alternatives considered
- Separate bootstrap ADRs per decision (one for HTMX, one for plasTeX, etc.). Rejected as paperwork without proportional benefit — one-line decisions ("we use HTMX") don't warrant standalone ADRs.
- No bootstrap ADR; rely on the reviewer to recognize CLAUDE.md as authoritative. Rejected because it leaves an ambiguous trust boundary — what counts as "decided in CLAUDE.md"? The explicit section list resolves that.

## Consequences
- The reviewer's "structural decision without ADR" check applies to NEW structural decisions surfacing in code, not to baseline decisions in the CLAUDE.md sections enumerated above.
- If any baseline decision is later revisited, that revisit gets a real ADR (e.g., ADR-007) which supersedes the relevant line of ADR-000 for that line item.
- Architect Mode 2 does NOT need to re-ADR HTMX, plasTeX, tier routing, etc., on every task.
- If a CLAUDE.md section listed above is renamed or split, this ADR must be updated (or superseded) so the pointers still match.

## Manifest conformance
This ADR codifies decisions made in alignment with design_docs/MANIFEST.md §3, §4, §6, §7. Nothing here tensions with the manifest.
