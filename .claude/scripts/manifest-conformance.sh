#!/usr/bin/env bash
set -euo pipefail

# Block commits that violate locked manifest constraints.
# Inspects STAGED CONTENT (via `git show :path`), not the working tree —
# the working tree may differ from what's about to be committed.
#
# Known limitations of v1 (intentional; iterate when one bites):
#   - Detects only direct top-level imports of common LLM libraries by name.
#     Misses `import openai as ai`, `importlib.import_module("openai")`,
#     direct `httpx`/`requests` calls to provider URLs, etc.
#   - Does not enforce that imports inside cs300/workflows/ are limited to
#     ai-workflows Step subclasses (vs. ad-hoc helpers). That rule lives in
#     CLAUDE.md and the reviewer's prompt.
#   - When grep misses something, the reviewer is the safety net. When
#     grep flags wrong things, fix the script.

STAGED_FILES=$(git diff --cached --name-only --diff-filter=ACMR)

# --- Constraint 1: ai-workflows is the only AI engine (Manifest §6) ---
# Walk each staged Python file and check its STAGED content.
violation_files=()
for f in $STAGED_FILES; do
  case "$f" in
    *.py) ;;
    *) continue ;;
  esac
  case "$f" in
    cs300/workflows/*) continue ;;  # AI work is allowed here
  esac
  if git show ":$f" 2>/dev/null \
      | grep -qE "^[[:space:]]*(import|from)[[:space:]]+(langchain|llamaindex|openai|anthropic|elevenlabs)\b"; then
    violation_files+=("$f")
  fi
done

if (( ${#violation_files[@]} > 0 )); then
  echo "BLOCKED: Direct LLM/TTS library imports outside cs300/workflows/:" >&2
  for f in "${violation_files[@]}"; do echo "  - $f" >&2; done
  echo "" >&2
  echo "All AI-service work goes through ai-workflows WorkflowSpec modules." >&2
  echo "See MANIFEST §6 ('ai-workflows is the only AI workflow engine')." >&2
  exit 1
fi

# --- Constraint 2: LaTeX source is read-only from app's perspective ---
# A single commit MUST NOT touch both content/latex/ AND application code.
has_latex=0
has_app=0
for f in $STAGED_FILES; do
  case "$f" in
    content/latex/*) has_latex=1 ;;
    *) has_app=1 ;;
  esac
done

if (( has_latex == 1 && has_app == 1 )); then
  echo "BLOCKED: Same commit modifies LaTeX source AND application code." >&2
  echo "These must be separate commits (per MANIFEST §6, §7)." >&2
  exit 1
fi

# Add more checks as the project surfaces real failure modes.
# Don't preemptively add checks for things that haven't gone wrong yet.

exit 0
