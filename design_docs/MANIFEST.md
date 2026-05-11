# Restructured CS 300 — Project Manifest

**Status:** Source of truth. Locked. Editable only by the human author.
**Authority:** This document supersedes any other document, comment, or generated artifact in this project. Where a downstream document, agentic workflow output, or implementation conflicts with the manifest, the manifest wins and the downstream artifact must be corrected.
**Audience:** The human author, and every agentic workflow that operates on this project.
**Scope of this document:** *What* the project is and what it is not. *What* it does and what it must never do. The manifest does not specify *how* any of this is built. Technology choices, frameworks, data models, integration patterns, and implementation policies live in the architecture document and are not constrained by the manifest beyond what is stated here as product behavior.

---

## 1. Identity

**Name:** Restructured CS 300
**Elevator:** A single-user learning system that consumes a curated augmentation of SNHU CS-300 with MIT OCW data structures material, organized around per-Chapter Lectures and Notes and per-Section Quizzes, with a reinforcement loop in which each post-first Quiz combines replayed wrong-answer Questions with freshly-generated Questions targeting Weak Topics.
**Repo intent:** Personal project. Single author, single user. Coexists with active SNHU CS-300 enrollment; does not replace it.

## 2. Problem Statement

SNHU CS-300 coursework is too shallow and unfocused for the rigor expected at top-tier MS programs (Columbia, Georgia Tech). The author has already curated an augmented curriculum by combining Zybooks content with MIT OCW data structures material. The remaining problem is **consumption**: an unstructured pile of curated material expands faster than it can be absorbed and decays without scaffolding. This project supplies the scaffolding: per-section learning surfaces and a feedback loop that surfaces and re-targets weak topics.

## 3. Primary Objective

Drive consumption and retention of the augmented CS-300 + MIT OCW curriculum at a rigor level appropriate for top-tier MS admissions, via per-Chapter Lectures and Notes and per-Section Quizzes whose results feed back into next-Quiz generation — combining replayed wrong-answer Questions with fresh Questions targeting Weak Topics.

The primary objective is singular. All scope and prioritization decisions are evaluated against it first.

## 4. Secondary Objective

Demonstrate that `ai-workflows` (the author's AI workflow framework) is a viable engine for AI-driven features in a real consumer application beyond its own examples. The choice of `ai-workflows` for this project's AI work is the only architectural commitment made at the manifest level; everything about *how* that integration is shaped lives in the architecture document.

The secondary objective is **explicitly ranked below primary** and cannot compete with it for scope. When a tradeoff exists between primary and secondary, primary wins. The secondary objective never justifies adding a feature.

## 5. Non-Goals

The following are out of scope. Agentic workflows must not propose, design, or implement any of them. If a need surfaces that appears to require crossing one of these lines, it must be raised to the human author for a manifest decision before any work proceeds.

- **No cross-Section Quizzes.** A Quiz scope is one Section.
- **No non-coding Question formats.** No multiple-choice, no true/false, no short-answer, no describe-the-concept, no interview-style verbal Questions. Every Question is a hands-on coding task.
- **No live / synchronous AI results.** Output from any AI-driven feature (grading, question generation, lecture audio) arrives when ready and is surfaced via Notification — not in real time at the moment of request.
- **No multi-user features.** No accounts, no auth, no sharing, no social, no roles.
- **No mobile-first product.** A polished mobile experience is not a goal; usable layout in a desktop browser is sufficient.
- **No LMS features.** No gradebook export, no course management, no enrollment, no roster, no instructor surface.
- **No in-app authoring of lecture content.** Lecture source is edited outside the application; the application reads it, never writes it.
- **No AI tutor / chat interface for the learner.** The Quiz reinforcement loop is the only AI-driven surface the learner interacts with.
- **No content beyond the augmented CS-300 / MIT OCW DSA scope.** This is not a generic learning platform.
- **No coverage of CS-300 Chapters 1–2.** Foundational introductory material is treated as already mastered by the author no Quizzes, no Question Bank.
- **No substitute for SNHU CS-300 enrollment.** This project coexists with the official course; it does not replace coursework, submissions, or grades-of-record.
- **No remote deployment / hosted product.**

## 6. Behaviors and Absolutes

These are non-negotiable product behaviors. Architecture must support them; implementation must honor them. They do not specify tech, framework, or pattern.

- **Quizzes scope to Sections; Lectures and Notes scope to Chapters.** Per-Chapter quiz aggregations, if ever surfaced, are computed from per-Section results. There is no Chapter-bound Quiz entity.
- **AI work is asynchronous from the learner's perspective.** Submission, processing, and result delivery are decoupled in time. The learner submits, continues working, and is notified when results are ready.
- **AI failures are visible.** If AI-driven processing fails, the failure is surfaced to the learner as a failure. The system never fabricates a result to cover for it.
- **Mandatory and Optional content are honored everywhere.** Every learner-facing surface respects and exposes the split. The learner can always view Mandatory-only.
- **A Lecture has a single source.** Every form in which a learner consumes that lecture (reading, listening, future modes) derives from the same source. The application does not modify the source.
- **Single-user.** No learner-facing or data path may assume multi-tenant capability.

## 7. Invariants and Principles

- **The reinforcement loop is the reason this project exists.** Quiz performance MUST drive next-Quiz generation. A Quiz feature without the loop is not the project.
- **A Quiz is bound to exactly one Section.**
- **Every Question is a hands-on coding task.** The learner writes code that implements a concept from the Section under study. Questions never ask the learner to describe, explain, recall, or choose among options.
- **Every post-first Quiz for a Section contains both replayed wrong-answer Questions and freshly-generated Questions.** Replay-only or fresh-only Quizzes are a bug. The first Quiz for a Section contains only fresh Questions (the bank is empty).
- **Quiz generation is always explicitly user-triggered.** The system never auto-generates a Quiz in response to background events.
- **A Note is bound to exactly one Chapter** and may optionally reference one Section within it.
- **Completion state lives at the Section level.** Chapter-level progress is derived from Section state.
- **Mandatory and Optional are separable in every learner-facing surface.**
- **Consumption modes of a Lecture remain consistent.** Where a Lecture is consumable in multiple modes (e.g., reading and listening), all modes for the same Section reflect the same source content. A change to the source for a Section invalidates every derived consumption mode for that Section until each is brought back into alignment.
- **Every Quiz Attempt, Note, and completion mark persists across sessions** and is owned by the single user.

## 8. Glossary

These definitions are locked. Code, docs, and agentic outputs use these terms with these meanings only. New terms are added by manifest edit only. Implementation-named entities (e.g., specific file formats, framework objects, derived artifacts named after their producing tech) live in the architecture document, not here.

- **Chapter** — A top-level unit of curriculum content. The atomic unit for Lectures and Notes. Carries a Mandatory or Optional designation. Mandatory and Optional are mutually exclusive at the Chapter level — a Chapter is one or the other, never a mix.
- **Section** — A subdivision within a Chapter. The atomic unit for Quizzes and completion state. The unit of in-lecture navigation. Inherits its Mandatory or Optional designation from its parent Chapter; Sections do not carry their own designation independent of the Chapter.
- **Lecture** — A Chapter's content prepared for consumption. Available in two consumption modes: reading (a visual rendering of the Chapter) and listening (a spoken-audio rendering of the Chapter). Read-only to the learner.
- **Note** — User-authored content bound to a Chapter, optionally referencing one Section. Editable by the user. Never auto-generated.
- **Quiz** — A graded assessment scoped to exactly one Section, composed of one or more Questions. Generated by AI-driven processing on manual user trigger. The first Quiz for a Section contains only freshly-generated Questions; every subsequent Quiz is composed of a mix of replayed Questions (the user previously answered them incorrectly) and freshly-generated Questions targeting Weak Topics from prior Attempts.
- **Question** — A single graded item belonging to a Section's Question Bank. A Question is a hands-on coding task: it asks the learner to implement a concept from the Section in code. Has one or more Topic tags. Persists with full Attempt history (which Attempts it appeared in, correctness in each). May appear in multiple Quizzes for its Section over time.
- **Question Bank** — The persisted set of all Questions ever generated for a Section, each retaining its full Attempt history. Used for replay logic and as a historical record. Never deleted; only superseded by content reorganization.
- **Quiz Attempt** — A single submission of a Quiz by the user. Carries the user's responses, a progress status through grading, and — once graded — a Grade.
- **Grade** — The result of grading a Quiz Attempt. Includes per-Question correctness, per-Question explanation, an aggregate score, identified Weak Topics, and recommended Sections to re-read.
- **Weak Topic** — A topic the user has demonstrated insufficient understanding of in one or more Quiz Attempts. Drives the fresh-Question portion of subsequent Quizzes for the same Section. The replay portion is driven separately by per-Question wrong-answer history, not by Weak Topic alone. Topics form a project-wide vocabulary maintained alongside Chapter content.
- **Mandatory** — A Chapter required by the SNHU CS-300 syllabus and within the project's scope. Currently Chapters 1–6.
- **Optional** — A Chapter added beyond the SNHU CS-300 syllabus for grad-school-prep depth, drawn from MIT OCW and any subsequent curated additions. Not required by SNHU. Currently Chapter 7 onward.
- **Notification** — A learner-visible indication that an async AI result has become available (most commonly a Grade or a newly-generated Quiz).

## 9. Change Protocol

The manifest is locked. Agentic workflows do not edit this file; the human author handles enforcement at the workflow layer.

When the human author edits the manifest, any downstream document, workflow definition, or code that references a changed item is updated in the same commit. Drift between the manifest and downstream artifacts is treated as a bug.

---

*Manifest version: 0.2 — architecture-and-tech contamination removed. Updates tracked via git history.*
