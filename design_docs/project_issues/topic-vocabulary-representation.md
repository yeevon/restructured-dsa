# Topic vocabulary representation

**Status:** Open
**Surfaced:** 2026-05-07 (bootstrap)
**Decide when:** First quiz-generation task is proposed.

## Question
The manifest (§8 Glossary, "Weak Topic") says: *"Topics form a project-wide vocabulary maintained alongside Chapter content."* How is that vocabulary stored, tagged, surfaced, and fed back into Question generation?

## Options known
- A YAML file in `content/` listing canonical topics, optionally per-Chapter.
- A SQLite table seeded from a YAML file at startup, mutable at runtime.
- LaTeX custom commands (e.g., `\topic{...}`) extracted by plasTeX during the lecture-derivation pipeline.

## Constraints from the manifest
- Topic tags are attached to Questions (Glossary §Question, §Question Bank).
- Weak Topics are surfaced on Grades and drive fresh-Question generation in subsequent Quizzes (Glossary §Weak Topic, §7 invariants).
- LaTeX source is read-only from the app's perspective (§6, §7) — so if topics live in LaTeX, the extraction is a read-only walk.

## Resolution
When resolved, mark this issue `Resolved by ADR-NNN`.
