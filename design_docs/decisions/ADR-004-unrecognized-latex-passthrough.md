# ADR-004: Unrecognized LaTeX environments and commands render as visible passthrough blocks, never as silent drops

**Status:** Accepted
**Date:** 2026-05-07
**Task:** TASK-001

## Context
The Chapter 1 LaTeX file will contain at least one environment or command the v1 parser does not yet have a render rule for — `lstlisting`, a custom curriculum macro, an exotic `tikzpicture`, etc. TASK-001's acceptance criteria require these to "render as a clearly-marked passthrough or a visible TODO block — not a silent drop and not a 500."

The manifest's invariant "no silent fallbacks in the AI pipeline" (§7) is about workflow runs, not about the LaTeX renderer; but the spirit applies. A Section quietly missing its key example because the parser didn't know what to do with the `lstlisting` environment is exactly the kind of drift that makes a derived artifact lie about its source.

## Decision

The parser maintains an explicit allowlist of supported LaTeX environments and commands. Anything outside the allowlist is captured as a `PassthroughBlock(environment=<env-name>, raw_latex=<verbatim source>)` (per ADR-003) at the level it was encountered.

The HTML renderer renders a `PassthroughBlock` as:

```html
<div class="lecture-passthrough" data-environment="<env-name>">
  <p class="lecture-passthrough-label">[unrendered LaTeX: <env-name>]</p>
  <pre class="lecture-passthrough-source"><code>{{ raw_latex }}</code></pre>
</div>
```

This is visible in the page, marked unmistakably, and shows the source so the human can see what's there and either (a) add a render rule or (b) decide it's fine as-is.

The v1 allowlist for TASK-001 is the union of:
- Whatever variants are enumerated in ADR-003's `Block` and `Inline` alphabet.
- Whatever environments and commands plasTeX handles natively that map cleanly onto those variants.

The author records in the TASK-001 close-out notes which environments are mapped vs. passed through, per the task's acceptance criterion.

A `PassthroughBlock` at parse time does not produce a parser warning by default. (It will be visible in the rendered page — that's a louder signal than a log line.) A parser-level error is reserved for actually-malformed LaTeX, not unsupported-but-well-formed.

## Alternatives considered
- **Drop unrecognized environments silently.** Rejected: violates the task's acceptance criteria and the spirit of §7. The Lecture Page would lie about its source.
- **Hard-fail (raise) on unrecognized environments.** Rejected: makes Chapter onboarding hostile. The author drops a `.tex` file in and gets a 500; the iterative loop of "see what's missing, decide what to support" disappears.
- **Render unrecognized environments as their plain-text body, dropping the wrapper.** Rejected: loses semantic information (a `lstlisting` rendered as a paragraph of run-on code text is worse than a clearly-marked passthrough).
- **Allowlist + log warning, no visible UI marker.** Rejected: the page is the surface the human reads; a logfile is a weaker signal than a visible block. Both is fine, but the visible block is the primary signal.

## Consequences
- The author iteratively grows the parser's render rules by reading the rendered page, finding passthrough blocks, and either adding a rule (because the environment is curriculum-relevant) or accepting the passthrough (because it's incidental).
- Future Script extraction (TTS) will need its own rule for `PassthroughBlock`: probably "skip with a brief spoken acknowledgement" or "skip silently." That's a Script-task decision; the Page-side decision here doesn't constrain it.
- The visible passthrough styling is intentionally ugly — manifest non-goal: functional, not pretty. A passthrough block that looks bad is a feature; it nags the author to handle it.
- A curriculum-critical environment (e.g., `algorithm` if Chapter 1 uses it for pseudocode) becoming a passthrough is a loud, visible signal during TASK-001 review. The author can add a render rule before close-out, or accept it and add later.

## Manifest conformance
- §7 "no silent fallbacks" (in spirit, since this is the renderer not the AI pipeline): unrecognized content surfaces, never gets papered over.
- §6 "LaTeX is the source of truth" / §7 "derived artifacts remain structurally aligned": passthrough preserves the source verbatim, so the derived artifact still reflects what's in the source even when it can't fully render it.
- §3 Primary Objective (consumption): a Section with one passthrough block is still consumable; a Section silently missing its key example is not.
