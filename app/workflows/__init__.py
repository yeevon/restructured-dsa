"""
app/workflows — CS-300-owned ai-workflows workflow modules and the out-of-band
Quiz-request processor.

ADR-036: workflow modules live under app/workflows/; the question-generation
workflow is at app/workflows/question_gen.py.
ADR-037: the out-of-band processor is at app/workflows/process_quiz_requests.py
(a __main__ module — python -m app.workflows.process_quiz_requests).

MC-1: no forbidden LLM/agent SDK import here — only ai_workflows.* imports.
MC-10: no DB driver imports here; no SQL literals here; DB access goes through
       app.persistence.* typed public functions only.
"""
