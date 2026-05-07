# TTS provider for Lecture Audio

**Status:** Open
**Surfaced:** 2026-05-07 (bootstrap)
**Decide when:** First lecture-audio task is proposed.

## Question
Which TTS provider generates Lecture Audio from the Lecture Script?

## Options known
- **Local** (Coqui XTTS, Bark, etc.) — purely local-first, but slower and lower-quality on CPU.
- **Hosted** (OpenAI TTS, ElevenLabs) — faster and better quality, but adds a second hosted dependency on top of the hosted-tier LLM.

## Manifest tension
None directly — the manifest's "local-first" interpretation (per ADR-000) already permits a hosted provider when local hardware can't deliver acceptable quality. The decision is whether TTS quality on local hardware is acceptable, not whether hosted is allowed.

## Resolution
When resolved, add the chosen provider as a `synth_audio` workflow tier in CLAUDE.md `## Tier routing`, and mark this issue `Resolved by ADR-NNN`.
