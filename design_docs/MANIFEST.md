# Restructured CS 300 — Project Manifest

**Status:** Source of truth. Locked. Editable only by the human author.
**Authority:** This document supersedes any other document, comment, or generated artifact in this project. Where a downstream document, agentic workflow output, or implementation conflicts with the manifest, the manifest wins and the downstream artifact must be corrected.
**Audience:** The human author, and every agentic workflow that operates on this project.

---

## 1. Identity

**Name:** Restructured CS 300
**Elevator:** A single-user, locally-run learning web app that consumes a curated augmentation of SNHU CS-300 (Zybooks) with MIT OCW data structures material, organized around per-Chapter Lectures and Notes and per-Section Quizzes, with an LLM-driven reinforcement loop in which each post-first Quiz combines replayed wrong-answer Questions with freshly-generated Questions targeting Weak Topics.
**Repo intent:** Personal project. Single author, single user. Coexists with active SNHU CS-300 enrollment; does not replace it.

## 2. Problem Statement

SNHU CS-300 coursework is too shallow and unfocused for the rigor expected at top-tier MS programs (Columbia, Georgia Tech). The author has already curated an augmented curriculum by combining Zybooks content with MIT OCW data structures material. The remaining problem is **consumption**: an unstructured pile of curated material expands faster than it can be absorbed and decays into unread PDFs without scaffolding. This project supplies the scaffolding: a per-chapter learning surface and a feedback loop that surfaces and re-targets weak topics.

## 3. Primary Objective

Drive consumption and retention of the augmented CS-300 + MIT OCW curriculum at a rigor level appropriate for top-tier MS admissions, via per-Chapter Lectures and Notes and per-Section Quizzes whose results feed back into next-Quiz generation — combining replayed wrong-answer Questions with fresh Questions targeting Weak Topics.

The primary objective is singular. All scope, architecture, and prioritization decisions are evaluated against it first.

## 4. Secondary Objective

Serve as a working dogfood deployment of `ai-workflows`, demonstrating that the framework's primitives — tier routing, durable state, async runs, structured I/O, MCP exposure, retry / gate / validator constructs — are leverageable for a real consumer application.

`ai-workflows` is a framework, not a turnkey set of AI features. It provides the plumbing and the composable shapes (`WorkflowSpec`, `LLMStep`, `ValidateStep`, `GateStep`, `TransformStep`, `FanOutStep`, tier registry, etc.) for *authoring* workflows. This project provides the workflow-specific logic on top: prompts, rubrics, schemas, generation strategies, weak-topic extraction. The framework's features are leveraged deliberately, not depended on by default.

The secondary objective is **explicitly ranked below primary** and cannot compete with it for scope. When a tradeoff exists between primary and secondary, primary wins. The secondary objective never justifies adding a feature; it is a constraint on *how* primary-objective features are built (use `ai-workflows`), not a license to expand them.

## 5. Non-Goals

The following are out of scope for this project. Agentic workflows must not propose, design, or implement any of them. If a need surfaces that appears to require crossing one of these lines, it must be raised to the human author for a manifest decision before any work proceeds.

- **No cross-Section quiz machinery.** A Quiz spans exactly one Section.
- **No live / synchronous AI work.** All AI-service work — quiz grading, question generation, lecture audio generation — is asynchronous, processed by `ai-workflows` runs and surfaced via Notification on completion.
- **No multi-user features.** No accounts, no auth, no sharing, no social, no roles. Single-user by construction.
- **No mobile app.** Web only. Responsive styling is acceptable but not required for v1.
- **No LMS features.** No gradebook export, no course management, no enrollment, no roster, no instructor surface.
- **No in-app content authoring of lecture material.** LaTeX source is edited externally. The app reads lecture content; it never writes it.
- **No AI tutor / chat interface for the learner.** The Quiz reinforcement loop is the only AI-facing surface the learner interacts with.
- **No content beyond the augmented CS-300 / MIT OCW DSA scope.** This is not a generic learning platform.
- **No substitute for SNHU CS-300 enrollment.** This project coexists with the official course; it does not replace coursework, submissions, or grades-of-record.
- **No deployment target beyond local-first.** Hosting, multi-tenancy, and remote-user access are out of scope.

## 6. Hard Constraints

These are non-negotiable. Architecture must conform; implementation must conform.

- **Atomic units differ by surface.** Chapter is the atomic unit for Lectures and Notes. Section is the atomic unit for Quizzes and completion state. There is no entity above the Chapter that aggregates these for a learner. Per-Chapter quiz aggregation, if ever surfaced, is computed from per-Section data; no Chapter-bound Quiz entity exists.
- **Async grading only.** A Quiz Attempt is submitted, enqueued, processed by an `ai-workflows` run, and surfaced via Notification on completion.
- **Mandatory / Optional split is preserved everywhere.** Every surface that displays content (Lectures, Notes, Quizzes, completion tracking, weak-topic surfacing) must respect and expose the split.
- **`ai-workflows` is the only AI workflow engine.** All AI-service calls — LLM-based work (grading, weak-topic extraction, question generation) and TTS-based work (lecture audio generation) alike — are implemented as `WorkflowSpec` modules registered with `ai-workflows`. Workflows are composed of framework primitives (`LLMStep`, `ValidateStep`, `GateStep`, `TransformStep`, `FanOutStep`); where no built-in primitive covers a need (e.g., a TTS-specific step), a custom step type is subclassed from the framework's `Step` base. No parallel ad-hoc AI calls in the site backend; no custom HTTP clients to model or TTS providers; no shadow workflow runner. The framework's plumbing is used; it is not bypassed and it is not reimplemented.
- **LaTeX is the source of truth for lecture content.** All lecture-derived artifacts — the Lecture Page (HTML), the Lecture Script (TTS-ready text), and the Lecture Audio (audio file) — derive deterministically from LaTeX source. The app does not modify LaTeX source.
- **Lecture Scripts are extracted from LaTeX, never from rendered HTML.** TTS input is produced by a LaTeX-aware extraction pipeline that preserves semantic structure (headings, equations, code blocks, lists) appropriate for spoken delivery. The Lecture Page (HTML) and the Lecture Script are sibling outputs of the same source; neither derives from the other.
- **Workflows are loaded via `AIW_EXTRA_WORKFLOW_MODULES`** (or equivalent first-class extension surface). The project does not vendor or fork `ai-workflows`.
- **Single-user / local-first.** No code path may assume multi-tenant capability.

## 7. Invariants and Principles

These are the rules every later decision honors. They are tested implicitly by every feature and explicitly in code where reasonable.

- **The reinforcement loop is the reason this project exists.** Quiz performance MUST drive next-Quiz generation targeting Weak Topics. A Quiz feature without the loop is not v1.
- **A Quiz is bound to exactly one Section.**
- **Every post-first Quiz for a Section contains both replayed wrong-answer Questions and freshly-generated Questions.** Replay-only or fresh-only Quizzes are a bug. The first Quiz for a Section contains only fresh Questions (the bank is empty).
- **Quiz generation is always explicitly user-triggered.** The system never auto-generates a Quiz in response to background events.
- **A Note is bound to exactly one Chapter.** A Note may optionally reference one Section within that Chapter, but the Chapter binding is primary.
- **Completion state is per-Section, not per-Chapter.** Chapter-level progress is derived.
- **Mandatory and Optional content are separable in every UI surface.** The user must always be able to view Mandatory-only.
- **The site never modifies LaTeX source.** Read path only.
- **Derived artifacts remain structurally aligned to source.** The Lecture Page, Lecture Script, and Lecture Audio for a given Chapter all correspond to the same Sections in the same order. A change to a Section's LaTeX source invalidates all three derived artifacts for that Section; the Lecture is not consistent again until each derived artifact is regenerated.
- **Every Quiz Attempt, Note, and Completion mark persists across sessions** and is owned by the single user.
- **Workflows are minimal by default.** A workflow uses a single tier unless a concrete requirement (cost, latency, quality) justifies multi-tier routing. Validators, retries, gates, and tier overrides are added in response to real failure modes or concrete needs — not preemptively. The previous iteration of this project drifted because workflow complexity preceded user-facing requirement; this iteration treats that as a constraint, not a stylistic preference.
- **No silent fallbacks in the AI pipeline.** If a workflow run fails, the failure surfaces to the user; the site does not fabricate a Grade or Question to fill the gap.

## 8. Glossary

These definitions are locked. Code, docs, and agentic outputs use these terms with these meanings only. New terms are added by manifest edit only.

- **Chapter** — A top-level unit of curriculum content. Sourced from one or more LaTeX files. Has a stable id (e.g., `ch-04-trees`). The atomic unit for Lectures and Notes. Carries a Mandatory or Optional designation, or contains both Mandatory and Optional Sections.
- **Section** — A subdivision within a Chapter, anchored by a LaTeX heading. Has a stable id within its Chapter (e.g., `ch-04-trees#bst-insertion`). The atomic unit for Quizzes and completion tracking, and the unit of lecture anchor navigation. Carries a Mandatory or Optional designation.
- **Lecture** — A Chapter's content prepared for consumption. Comprises a Lecture Page and, where generated, a Lecture Audio. Read-only in the app.
- **Lecture Page** — The HTML rendering of a Chapter's LaTeX source for visual consumption. Section anchors are preserved.
- **Lecture Script** — The TTS-ready text representation of a Chapter's LaTeX source, produced by a LaTeX-aware extraction pipeline. Sole input to the workflow that generates Lecture Audio. Never derived from HTML.
- **Lecture Audio** — The audio rendering of a Chapter, generated by an `ai-workflows` TTS workflow from a Lecture Script. Aligned to the Chapter's Sections.
- **Note** — User-authored markdown bound to a Chapter, optionally referencing one Section. Editable by the user. Never auto-generated.
- **Quiz** — A graded assessment scoped to exactly one Section, composed of one or more Questions. Has a stable id and a Section binding. Generated by an `ai-workflows` workflow on manual user trigger. The first Quiz for a Section contains only freshly-generated Questions; every subsequent Quiz for that Section is composed of a mix of replayed Questions (the user previously answered them incorrectly) and freshly-generated Questions (targeting Weak Topics from prior Attempts).
- **Question** — A single graded item belonging to a Section's Question Bank. Has a type, a body, an expected answer or rubric, and one or more Topic tags. Persists with full Attempt history (which Attempt(s) it appeared in, correctness in each). May appear in multiple Quizzes for its Section over time. Question types are defined in the architecture document, not the manifest.
- **Question Bank** — The persisted set of all Questions ever generated for a Section. Each Question retains its full Attempt history (which Attempt(s) it appeared in, whether the user answered it correctly each time). Used both for replay logic and as a historical record. Never deleted; only superseded by content reorganization.
- **Quiz Attempt** — A single submission of a Quiz by the user. Has a unique id, a timestamp, a status (`submitted` | `grading` | `graded` | `failed`), the user's responses, and — once graded — a Grade.
- **Grade** — The result of grading a Quiz Attempt. Includes per-Question correctness, per-Question explanation of why the response was right or wrong, an aggregate score, identified Weak Topics, and recommended Sections to re-read.
- **Weak Topic** — A topic the user demonstrated insufficient understanding of in one or more Quiz Attempts. Tagged on Questions and surfaced on Grades. Drives the fresh-Question portion of subsequent Quizzes for the same Section. The replay portion of those Quizzes is driven separately by per-Question wrong-answer history, not by Weak Topic alone. Topics form a project-wide vocabulary maintained alongside Chapter content.
- **Mandatory** — Content required by the SNHU CS-300 syllabus.
- **Optional** — Content added by the augmentation (MIT OCW and any subsequent additions) for grad-school-prep depth, not required by SNHU.
- **Run** — An execution of an `ai-workflows` workflow, identified by a `run_id`. The site stores `run_id`s to track async grading and generation.
- **Workflow** — A `WorkflowSpec` registered with `ai-workflows`, authored in this project's package (e.g., `cs300.workflows.grade_quiz`, `cs300.workflows.generate_quiz`), composed of framework primitives (`LLMStep`, `ValidateStep`, `GateStep`, `TransformStep`, `FanOutStep`), and loaded into `ai-workflows` at startup via `AIW_EXTRA_WORKFLOW_MODULES`.
- **Notification** — An in-app indication that an async Run has completed, surfacing the result (most commonly a Grade or a newly-generated Quiz).

## 9. Change Protocol

The manifest is locked. Agentic workflows do not edit this file; the human author handles enforcement at the workflow layer.

When the human author edits the manifest, any downstream document, workflow definition, or code that references a changed item is updated in the same commit. Drift between the manifest and downstream artifacts is treated as a bug.

---

*Manifest version: 0.1 — initial draft. Updates tracked via git history.*
