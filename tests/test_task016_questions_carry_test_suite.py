"""
TASK-016: Questions carry a test suite — the `question_gen` workflow emits one
runnable test-code string per Question, the generation processor persists it
with the Question, a Question whose LLM-supplied test suite is missing/blank/
whitespace-only makes the whole Quiz `generation_failed` (no placeholder
synthesized), and the per-Section surface remains unchanged.

Tests derive from the Acceptance Criteria in
`design_docs/tasks/TASK-016-questions-carry-a-test-suite.md`
and from the two Accepted ADRs this task lands:
  ADR-040 — Questions carry a test suite: `GeneratedQuestion` gains
             `test_suite: str` (min_length=1); the generation processor reads it
             from the `aiw run` artefact and persists it verbatim; a Question
             whose LLM-supplied test_suite is missing/empty/whitespace-only makes
             the whole Quiz `generation_failed` (zero `questions` rows; no
             placeholder — MC-5); the per-Section caption and the take surface
             are unchanged (ADR-040's explicit call).
  ADR-041 — The Question test-suite persistence layer: a nullable
             `questions.test_suite TEXT` column (additive via
             `_apply_additive_migrations`'s `PRAGMA table_info` check, mirroring
             ADR-037's `generation_error`; also in the `CREATE TABLE questions`
             block for fresh DBs); the `Question` dataclass gains
             `test_suite: str | None`; `add_questions_to_quiz`'s per-Question
             payload dict gains a `"test_suite"` key (no signature change); the
             row→dataclass converter and `list_questions_for_quiz`'s SELECT carry
             it through; no new public accessor.

Coverage matrix:
  Boundary:
    - test_generated_question_schema_has_test_suite_field:
        GeneratedQuestion schema carries test_suite field alongside prompt/topics.
    - test_generated_question_test_suite_min_length_one_enforced:
        An empty string test_suite is rejected by the pydantic validator
        (min_length=1 — the boundary is 0 vs 1).
    - test_generated_question_single_char_test_suite_is_valid:
        A single non-whitespace character satisfies min_length=1 (boundary = 1).
    - test_questions_test_suite_column_exists_fresh_db:
        questions.test_suite column exists after schema bootstrap on a fresh DB.
    - test_processor_happy_path_all_questions_carry_test_suite:
        With ≥1 question in the artefact, every persisted questions row carries
        a non-null, non-empty test_suite (boundary: ≥1).
    - test_processor_happy_path_test_suite_stored_verbatim:
        The stored test_suite equals the value in the artefact (verbatim —
        not transformed, not regenerated).
  Edge:
    - test_generated_question_whitespace_only_test_suite_handled_by_processor:
        A whitespace-only test_suite string (e.g. "   \n  ") passes pydantic
        min_length=1 (pydantic counts spaces as characters) BUT is an invalid
        test suite by ADR-040's processor sanity check → the processor must
        treat this as a generation failure (generation_failed, zero questions).
    - test_questions_test_suite_column_nullable_for_legacy_rows:
        A `questions` row inserted without test_suite (pre-TASK-016 style)
        has test_suite IS NULL — the column is nullable (ADR-041).
    - test_list_questions_for_quiz_returns_test_suite_field:
        list_questions_for_quiz returns Question dataclasses that carry the
        test_suite attribute (even if None for a legacy row).
    - test_questions_test_suite_column_additive_on_existing_db:
        On a DB that already has the questions table WITHOUT the test_suite
        column, calling init_schema() / bootstrap adds the column additively
        (ADR-041 / ADR-022 migration story — no data loss, no error).
    - test_processor_with_multiple_questions_all_test_suites_persisted:
        With 5 questions in the artefact (scale edge), every persisted row
        carries its test_suite.
    - test_processor_only_one_question_missing_test_suite_fails_whole_quiz:
        With 3 questions where only 1 is missing its test_suite, the whole
        Quiz ends generation_failed and zero questions rows are written
        (whole-Quiz reject — ADR-040's strictest reading, MC-5).
  Negative:
    - test_generated_question_no_non_coding_fields_present:
        GeneratedQuestion has no choice / correct_choice / answer_text /
        option_* / recall_* / describe_* field — the schema admits only test
        code (MC-1 / Manifest §5/§7 / ADR-040's "test code only" commitment).
    - test_question_gen_module_imports_only_ai_workflows_and_pydantic:
        question_gen.py imports only ai_workflows.* + pydantic (+ stdlib) —
        no forbidden LLM/agent SDK import (MC-1 / ADR-040).
    - test_processor_empty_test_suite_yields_generation_failed:
        An artefact where a question's test_suite is the empty string →
        generation_failed, zero questions rows (MC-5 / ADR-040).
    - test_processor_missing_test_suite_key_yields_generation_failed:
        An artefact where a question dict has no "test_suite" key at all →
        generation_failed, zero questions rows (MC-5 / ADR-040).
    - test_processor_missing_test_suite_zero_questions_persisted:
        Confirms the zero-questions invariant: after a bad-test-suite failure,
        the questions table is empty.
    - test_no_user_id_on_questions_table_after_task016:
        questions.test_suite column addition does not add a user_id column
        (MC-7 / ADR-041).
    - test_mc10_no_sqlite3_import_in_workflows:
        app/workflows/ must not import sqlite3 (MC-10 — SQL stays under
        app/persistence/).
    - test_mc10_no_sql_literals_in_workflows:
        app/workflows/ must not contain SQL string literals (MC-10).
    - test_section_quiz_surface_unchanged_for_ready_quiz:
        After a processor walk to ready (with test suites), the per-Section
        Quiz surface shows "Ready" + take-link and does NOT show any "Run tests"
        affordance (ADR-040: surface unchanged; ADR-040 Alternative E rejected).
    - test_take_surface_renders_prompt_and_test_suite:
        The take page (ADR-038/ADR-043's quiz_take.html.j2) renders the Question
        prompt unchanged AND renders the Question's test_suite read-only in a
        <pre class="quiz-take-test-suite"> block (ADR-043 §quiz_take.html.j2
        changes — the runner slice that resolved ADR-040's deferral).
  Performance:
    - test_processor_with_five_questions_persists_all_within_budget:
        Processing a Quiz with 5 generated questions (each with a test_suite)
        persists all 5 within 5 s (catches O(n²) regressions on the per-question
        INSERT path — ADR-037/ADR-041 one-transaction discipline).

Notes on the test seam (per ADR-036 §The test seam):
  The processor invokes the workflow via `subprocess.run`.  Tests mock that seam
  at the CS-300 processor boundary — NOT the framework's in-process StubLLMAdapter.

  A success-path mock returns a canned artefact whose stdout matches:
    json.dumps({"questions": [
        {"prompt": "...", "topics": [...], "test_suite": "..."},
        ...
    ]}, indent=2) + "\\ntotal cost: $0.0012"
  (Extending the TASK-014 artefact format to include test_suite per ADR-040.)

  A bad-test-suite mock returns a canned artefact where ≥1 question has a
  missing / empty / whitespace-only test_suite.

  A failure-path mock returns returncode=1 (as in TASK-014 tests).

ASSUMPTIONS:
  ASSUMPTION: `app.workflows.question_gen.GeneratedQuestion` has a `test_suite`
    field (ADR-040 §The question_gen output-schema extension). If the field is
    absent, the pydantic-model-inspection tests fail (red as expected).

  ASSUMPTION: The processor's bad-test-suite check happens at the processor
    boundary (ADR-040 §The bad-test-suite failure handling) — specifically, a
    whitespace-only test_suite in the artefact (which passes pydantic's
    min_length=1 check on raw bytes) is caught by the processor's `.strip()`
    check. If the processor only checks "non-empty before strip", the
    whitespace-only test fails; that is the expected red signal.

  ASSUMPTION: `app.persistence.Question` has a `test_suite` attribute (ADR-041
    §The Question dataclass). If the attribute is absent, the dataclass-inspection
    tests fail red.

  ASSUMPTION: The processor module entry point is `process_pending()` or
    `main()` (same as TASK-014 tests) — mocked via `subprocess.run`.

  ASSUMPTION: `add_questions_to_quiz`'s per-Question payload dict includes
    `"test_suite"` as a key; the function INSERTs it into `questions.test_suite`.
    If the payload key or INSERT is absent, the round-trip tests fail red.

pytestmark registers all tests under task("TASK-016").
"""

from __future__ import annotations

import json
import pathlib
import re
import sqlite3
import subprocess
import time
from typing import Any
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.task("TASK-016")

REPO_ROOT = pathlib.Path(__file__).parent.parent

# ---------------------------------------------------------------------------
# Chapter / Section IDs from the corpus
# ---------------------------------------------------------------------------

MANDATORY_CHAPTER_ID = "ch-01-cpp-refresher"
SECTION_ID_CH01_S1 = "ch-01-cpp-refresher#section-1-1"
MANDATORY_FIRST_SECTION = "1-1"

# ---------------------------------------------------------------------------
# Helpers — canned artefact builders
# ---------------------------------------------------------------------------


def _make_success_stdout_with_test_suites(questions: list[dict]) -> str:
    """
    Build the stdout `aiw run question_gen` produces on a successful run.
    ADR-040: the artefact now includes `test_suite` per question.
    ADR-036: `json.dumps(artifact, indent=2)` then `total cost: $X.XXXX`.
    """
    artefact = {"questions": questions}
    return json.dumps(artefact, indent=2) + "\ntotal cost: $0.0042\n"


def _make_completed_process(
    stdout: str = "",
    stderr: str = "",
    returncode: int = 0,
) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(
        args=["aiw", "run", "question_gen"],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


# Sample test-suite strings (realistic but compact)
_TEST_SUITE_HASH_TABLE = (
    "def test_hash_table_insert():\n"
    "    ht = HashTable()\n"
    "    ht.insert('key', 42)\n"
    "    assert ht.lookup('key') == 42\n"
)

_TEST_SUITE_BINARY_SEARCH = (
    "def test_binary_search_found():\n"
    "    assert binary_search([1, 2, 3, 4, 5], 3) == 2\n"
    "\n"
    "def test_binary_search_not_found():\n"
    "    assert binary_search([1, 2, 3], 99) == -1\n"
)

_TEST_SUITE_STACK = (
    "#include <cassert>\n"
    "int main() {\n"
    "    Stack s;\n"
    "    s.push(1);\n"
    "    assert(s.pop() == 1);\n"
    "    return 0;\n"
    "}\n"
)


# ---------------------------------------------------------------------------
# DB / bootstrap helpers
# ---------------------------------------------------------------------------


def _bootstrap_and_make_client(monkeypatch, db_path: str):
    """Bootstrap the DB and return a FastAPI TestClient."""
    monkeypatch.setenv("NOTES_DB_PATH", db_path)
    from fastapi.testclient import TestClient  # noqa: PLC0415
    from app.main import app  # noqa: PLC0415
    client = TestClient(app)
    client.get(f"/lecture/{MANDATORY_CHAPTER_ID}")
    return client


def _get_table_columns(db_path: str, table: str) -> set[str]:
    conn = sqlite3.connect(db_path)
    cur = conn.execute(f"PRAGMA table_info({table})")
    cols = {row[1] for row in cur.fetchall()}
    conn.close()
    return cols


def _db_rows(db_path: str, sql: str, params=()) -> list[dict]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.execute(sql, params)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def _run_processor(monkeypatch, db_path: str, mock_return: Any) -> None:
    """
    Import the processor module and invoke it with the subprocess call mocked.
    Mirrors the TASK-014 test helper (ADR-036 §The test seam).
    """
    monkeypatch.setenv("NOTES_DB_PATH", db_path)

    if isinstance(mock_return, type) and issubclass(mock_return, Exception):
        side_effect = mock_return("mocked failure")
        mock_rv = None
    else:
        side_effect = None
        mock_rv = mock_return

    with patch("subprocess.run", return_value=mock_rv, side_effect=side_effect):
        import app.workflows.process_quiz_requests as proc_module  # noqa: PLC0415
        if hasattr(proc_module, "process_pending"):
            proc_module.process_pending()
        elif hasattr(proc_module, "main"):
            proc_module.main()
        elif hasattr(proc_module, "run"):
            proc_module.run()
        else:
            pytest.fail(
                "app.workflows.process_quiz_requests has no callable entry point "
                "(process_pending / main / run). ADR-037: the processor module must "
                "expose a callable entry point for the test seam."
            )


# ===========================================================================
# AC-1 — `GeneratedQuestion` schema carries a `test_suite` field
# Trace: TASK-016 AC-1; ADR-040 §The question_gen output-schema extension;
#        Manifest §5/§7/§8 (Question "carries a test suite")
# ===========================================================================


def test_generated_question_schema_has_test_suite_field() -> None:
    """
    AC-1 (TASK-016) / ADR-040: `GeneratedQuestion` must carry a `test_suite`
    field alongside `prompt` and `topics`.

    ADR-040 §The question_gen output-schema extension: 'GeneratedQuestion gains
    a test_suite: str field alongside prompt: str and topics: list[str].'

    Tests the pydantic model schema — both that test_suite is a required field
    and that a well-formed value (a non-empty string of test code) is accepted.

    Trace: AC-1; ADR-040 §Schema extension; Manifest §8 (Question 'carries a
    test suite the learner runs in-app to verify the implementation').
    """
    from app.workflows.question_gen import GeneratedQuestion  # noqa: PLC0415

    # A well-formed GeneratedQuestion with all three fields must be instantiatable
    gq = GeneratedQuestion(
        prompt="Implement a hash table with open addressing in C++.",
        topics=["hashing", "arrays"],
        test_suite=_TEST_SUITE_HASH_TABLE,
    )
    assert hasattr(gq, "test_suite"), (
        f"GeneratedQuestion instance has no 'test_suite' attribute: {gq!r}. "
        "AC-1/ADR-040: GeneratedQuestion must carry a test_suite field."
    )
    assert gq.test_suite == _TEST_SUITE_HASH_TABLE, (
        f"GeneratedQuestion.test_suite={gq.test_suite!r}; "
        f"expected {_TEST_SUITE_HASH_TABLE!r}. "
        "The field must store the value exactly as provided."
    )

    # The model's fields should include test_suite
    field_names = set(GeneratedQuestion.model_fields.keys())
    assert "test_suite" in field_names, (
        f"GeneratedQuestion.model_fields does not include 'test_suite'. "
        f"Fields found: {field_names!r}. "
        "AC-1/ADR-040: the pydantic schema must declare test_suite as a field."
    )


def test_generated_question_test_suite_min_length_one_enforced() -> None:
    """
    AC-1 (TASK-016) / ADR-040: the `test_suite` field must reject an empty
    string (min_length=1 — belt-and-braces with the processor's sanity check).

    ADR-040 §Schema extension: 'the implementer adds a min_length=1 constraint
    so a literally-empty test suite is rejected at the validator layer too.'

    Boundary: the flip between invalid (length 0) and valid (length 1).

    Trace: AC-1; ADR-040 §Schema extension (min_length=1); MC-5 (AI failures
    surfaced, never fabricated — an empty test suite is not shippable).
    """
    from pydantic import ValidationError  # noqa: PLC0415
    from app.workflows.question_gen import GeneratedQuestion  # noqa: PLC0415

    # Step 1: confirm the test_suite field exists in the model before testing min_length
    field_names = set(GeneratedQuestion.model_fields.keys())
    assert "test_suite" in field_names, (
        f"GeneratedQuestion.model_fields does not include 'test_suite': {field_names!r}. "
        "AC-1/ADR-040: the field must exist before we can test its min_length=1 constraint."
    )

    # Step 2: an empty string must be rejected (min_length=1 constraint)
    raised = False
    try:
        _ = GeneratedQuestion(
            prompt="Implement a stack.",
            topics=["stack"],
            test_suite="",
        )
    except (ValidationError, ValueError):
        raised = True

    assert raised, (
        "GeneratedQuestion(test_suite='') did NOT raise ValidationError or ValueError. "
        "AC-1/ADR-040 §Schema extension (min_length=1): an empty string test_suite "
        "must be rejected by the pydantic validator. "
        "This is a belt-and-braces check: the processor also strips and checks emptiness, "
        "but the pydantic layer must catch the literally-empty case too (ADR-040 §Alternative C)."
    )


def test_generated_question_single_char_test_suite_is_valid() -> None:
    """
    AC-1 (TASK-016) / ADR-040: a single non-whitespace character as test_suite
    satisfies the min_length=1 constraint (boundary = 1 character).

    This confirms the boundary is at length 0/1 — length 1 passes.

    Trace: AC-1; ADR-040 §Schema extension (min_length=1 boundary).
    """
    from app.workflows.question_gen import GeneratedQuestion  # noqa: PLC0415

    try:
        gq = GeneratedQuestion(
            prompt="Implement a stack.",
            topics=["stack"],
            test_suite="x",
        )
    except Exception as exc:
        pytest.fail(
            f"GeneratedQuestion(test_suite='x') raised {exc!r}. "
            "AC-1/ADR-040: a single-character test_suite must satisfy min_length=1. "
            "Length 1 is the boundary: it must pass (length 0 must fail)."
        )
    assert gq.test_suite == "x", (
        f"Expected test_suite='x', got {gq.test_suite!r}."
    )


def test_generated_question_no_non_coding_fields_present() -> None:
    """
    AC-1 (TASK-016) / ADR-040 / Manifest §5/§7: `GeneratedQuestion` must NOT
    carry any non-coding-Question field alongside `test_suite`.

    ADR-040 §The test-suite representation: 'The test_suite: str field's type
    can hold only test code — it cannot hold an option list, a true/false key,
    a "describe in a sentence" prompt, a recall answer.' The schema's
    `extra="forbid"` and the absence of forbidden fields enforce this.

    Forbidden field name patterns: option_*, correct_choice, answer_text,
    describe_*, recall_*, choices.

    Trace: AC-1; ADR-040 §Test-suite representation ('test code only');
    ADR-036 §Shape commitment ('no non-coding field'); Manifest §5
    'No non-coding Question formats'; Manifest §7 'Every Question is a
    hands-on coding task'.
    """
    from app.workflows.question_gen import GeneratedQuestion  # noqa: PLC0415

    field_names = set(GeneratedQuestion.model_fields.keys())
    forbidden_patterns = [
        "option_",
        "correct_choice",
        "answer_text",
        "describe_",
        "recall_",
        "choices",
    ]
    violations = [
        name
        for name in field_names
        if any(pat in name.lower() for pat in forbidden_patterns)
    ]
    assert violations == [], (
        f"GeneratedQuestion carries non-coding-task field(s): {violations!r}. "
        "AC-1/ADR-040/Manifest §5/§7: the test_suite field must hold only test "
        "source code; the schema must not admit an option list / true-false key / "
        "describe prompt / recall answer. No option_*, correct_choice, answer_text, "
        "describe_*, recall_*, or choices field is allowed. "
        f"All fields found: {field_names!r}."
    )
    # Also check extra="forbid" is in force: instantiating with an extra field
    # must raise ValidationError (the schema rejects non-coding artifacts)
    from pydantic import ValidationError  # noqa: PLC0415
    with pytest.raises(ValidationError):
        GeneratedQuestion(
            prompt="Implement a BST.",
            topics=["BST"],
            test_suite=_TEST_SUITE_BINARY_SEARCH,
            choices=["A", "B", "C", "D"],  # a forbidden non-coding artifact
        )


# ===========================================================================
# AC-2 — `question_gen.py` imports only ai_workflows.* + pydantic (MC-1)
# Trace: TASK-016 AC-2; ADR-040 §Scope of this ADR (MC-1); ADR-036 §Forbidden-SDK
# ===========================================================================


_FORBIDDEN_SDK_PATTERNS = [
    r"\bimport openai\b",
    r"\bfrom openai\b",
    r"\bimport anthropic\b",
    r"\bfrom anthropic\b",
    r"\bimport google\.generativeai\b",
    r"\bfrom google\.generativeai\b",
    r"\bimport google\.genai\b",
    r"\bfrom google\.genai\b",
    r"\bimport cohere\b",
    r"\bfrom cohere\b",
    r"\bimport mistralai\b",
    r"\bfrom mistralai\b",
    r"\bimport groq\b",
    r"\bfrom groq\b",
    r"\bimport together\b",
    r"\bfrom together\b",
    r"\bimport replicate\b",
    r"\bfrom replicate\b",
    r"\bimport litellm\b",
    r"\bfrom litellm\b",
    r"\bimport langchain\b",
    r"\bfrom langchain\b",
    r"\bimport langgraph\b",
    r"\bfrom langgraph\b",
]


def test_question_gen_module_imports_only_ai_workflows_and_pydantic() -> None:
    """
    AC-2 (TASK-016) / MC-1 (architecture portion active per ADR-036) / ADR-040
    §Scope: `app/workflows/question_gen.py` must NOT import any forbidden
    LLM/agent SDK even after TASK-016 extends its output schema.

    ADR-040 §Schema extension: 'The module's imports stay ai_workflows.workflows.*
    + ai_workflows.primitives.tiers + pydantic (+ stdlib os) only — MC-1;
    ADR-036's architecture portion stays satisfied.'

    This tests the specific file that TASK-016 changes, not just `app/` broadly.

    Trace: AC-2; ADR-040 §Scope; ADR-036 §Forbidden-SDK list; MC-1 (blocker).
    """
    question_gen_file = REPO_ROOT / "app" / "workflows" / "question_gen.py"
    assert question_gen_file.exists(), (
        f"app/workflows/question_gen.py does not exist at {question_gen_file}. "
        "ADR-036/ADR-040: the CS-300 question_gen WorkflowSpec must live here."
    )

    text = question_gen_file.read_text(encoding="utf-8")
    compiled = [re.compile(p) for p in _FORBIDDEN_SDK_PATTERNS]
    violations = []
    for pattern in compiled:
        if pattern.search(text):
            violations.append(pattern.pattern)

    assert violations == [], (
        f"MC-1 BLOCKER: forbidden LLM/agent SDK import(s) found in "
        f"app/workflows/question_gen.py:\n"
        + "\n".join(f"  {v}" for v in violations)
        + "\n\nAC-2/ADR-040 §Scope: after TASK-016 extends the workflow's output "
        "schema, the module's imports must still be ai_workflows.* + pydantic "
        "(+ stdlib) only. ADR-036's forbidden-SDK list is enumerated above."
    )


def test_mc10_no_sqlite3_import_in_workflows() -> None:
    """
    AC-6 (TASK-016) / MC-10: `app/workflows/` must NOT import sqlite3.

    ADR-040 / ADR-036 / ADR-022 §Package boundary: `import sqlite3` may only
    appear under `app/persistence/`. The workflow module and the processor must
    call only typed public functions from `app/persistence/__init__.py` — they
    must never open a DB connection directly.

    TASK-016 extends the processor to pass a test_suite payload — this test
    confirms the extension does not introduce a sqlite3 import.

    Trace: AC-6; MC-10 (blocker — persistence package exists in code, ADR-022
    activated); ADR-040 §Conformance check MC-10.
    """
    workflows_dir = REPO_ROOT / "app" / "workflows"
    violations = []
    for py_file in sorted(workflows_dir.rglob("*.py")):
        text = py_file.read_text(encoding="utf-8")
        if "import sqlite3" in text:
            violations.append(str(py_file))

    assert violations == [], (
        f"MC-10 BLOCKER: `import sqlite3` found in app/workflows/: {violations!r}. "
        "AC-6/MC-10/ADR-040 §Conformance: SQL/DB driver imports must be confined "
        "to app/persistence/. The processor must call typed public functions only."
    )


def test_mc10_no_sql_literals_in_workflows() -> None:
    """
    AC-6 (TASK-016) / MC-10: `app/workflows/` must NOT contain SQL string literals.

    ADR-040 / ADR-022 §Package boundary: SQL string literals (SELECT/INSERT/
    UPDATE/DELETE/CREATE TABLE/ALTER TABLE) must appear only under `app/persistence/`.

    Trace: AC-6; MC-10 (blocker); ADR-040 §Conformance check MC-10.
    """
    workflows_dir = REPO_ROOT / "app" / "workflows"
    sql_pattern = re.compile(
        r"""(?x)
        (?:"|')
        [^"']*
        (?:
            \bSELECT\b |
            \bINSERT\b |
            \bUPDATE\b |
            \bDELETE\b |
            \bCREATE\s+TABLE\b |
            \bALTER\s+TABLE\b |
            \bBEGIN\b |
            \bCOMMIT\b |
            \bROLLBACK\b
        )
        [^"']*
        (?:"|')
        """,
    )
    violations = []
    for py_file in sorted(workflows_dir.rglob("*.py")):
        text = py_file.read_text(encoding="utf-8")
        if sql_pattern.search(text):
            violations.append(str(py_file))

    assert violations == [], (
        f"MC-10 BLOCKER: SQL string literals found in app/workflows/: {violations!r}. "
        "AC-6/MC-10/ADR-040 §Conformance: SQL must stay under app/persistence/."
    )


# ===========================================================================
# AC-3 — `questions.test_suite` column exists; additive; nullable; no user_id
# Trace: TASK-016 AC-3; ADR-041 §The storage; ADR-022 §Migration story; MC-7
# ===========================================================================


def test_questions_test_suite_column_exists_fresh_db(tmp_path, monkeypatch) -> None:
    """
    AC-3 (TASK-016) / ADR-041 §Storage: a fresh DB bootstrapped from `_SCHEMA_SQL`
    must have a `questions.test_suite` column.

    ADR-041: 'the column is added to the CREATE TABLE IF NOT EXISTS questions
    block in _SCHEMA_SQL so a fresh database gets the column directly.'

    Trace: AC-3; ADR-041 §Storage (fresh-DB path); ADR-022 §Migration story.
    """
    db_path = str(tmp_path / "fresh.db")
    _bootstrap_and_make_client(monkeypatch, db_path)

    cols = _get_table_columns(db_path, "questions")
    assert "test_suite" in cols, (
        f"After bootstrapping a fresh DB, questions table is missing 'test_suite' column. "
        f"Columns found: {cols!r}. "
        "AC-3/ADR-041: questions.test_suite TEXT must be declared in the "
        "CREATE TABLE questions block for fresh databases."
    )


def test_questions_test_suite_column_nullable_for_legacy_rows(
    tmp_path, monkeypatch
) -> None:
    """
    AC-3 (TASK-016) / ADR-041 §The storage: `questions.test_suite` must be
    nullable — a row inserted without `test_suite` must have `test_suite IS NULL`.

    ADR-041: 'nullable, no default … NULL = "no recorded test suite" (legacy
    rows only); a non-empty string = "the test suite" (every newly-persisted
    Question, by ADR-040's failure handling).'

    Edge: a pre-TASK-016 style INSERT (no test_suite provided) must work
    (additive migration; legacy rows have NULL).

    Trace: AC-3; ADR-041 §Storage (nullable column); ADR-022 §Migration story.
    """
    db_path = str(tmp_path / "nullable.db")
    _bootstrap_and_make_client(monkeypatch, db_path)

    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "INSERT INTO questions (section_id, prompt, topics, created_at) "
            "VALUES (?, 'Implement a queue.', 'queue', '2026-01-01T00:00:00Z')",
            (SECTION_ID_CH01_S1,),
        )
        conn.commit()
        row = conn.execute(
            "SELECT test_suite FROM questions WHERE prompt = 'Implement a queue.'"
        ).fetchone()
        assert row is not None, "Could not find the inserted questions row."
        assert row[0] is None, (
            f"questions.test_suite={row[0]!r} for a row inserted without test_suite; "
            "expected NULL. "
            "AC-3/ADR-041: test_suite must be nullable so pre-TASK-016 rows have "
            "test_suite IS NULL, not an empty string or error."
        )
    finally:
        conn.close()


def test_questions_test_suite_column_additive_on_existing_db(
    tmp_path, monkeypatch
) -> None:
    """
    AC-3 (TASK-016) / ADR-041 §Storage: the `_apply_additive_migrations` path
    must add `questions.test_suite` to an *existing* DB that was created without
    it (simulating a pre-TASK-016 DB).

    ADR-041 §Storage: 'In `_apply_additive_migrations(conn)` — a
    PRAGMA table_info(questions) check + a guarded ALTER TABLE questions ADD
    COLUMN test_suite TEXT, mirroring the quizzes.generation_error precedent
    ADR-037 set.' ADR-022 §Migration story: nullable ALTER TABLE ADD COLUMN
    is additive — no data loss, no migration-trigger.

    Edge: simulates a DB created by TASK-015 code (no test_suite column) being
    brought up to date by the TASK-016 bootstrap. We drop the column if SQLite
    were to support it, or we create a minimal DB without the column and then
    run init_schema().

    Trace: AC-3; ADR-041 §Storage (existing-DB path); ADR-022 §Additive-migration.
    """
    db_path = str(tmp_path / "existing.db")

    # Create a minimal DB with the questions table but WITHOUT test_suite —
    # simulating a pre-TASK-016 database.
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS quizzes (
                quiz_id INTEGER PRIMARY KEY AUTOINCREMENT,
                section_id TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'requested',
                created_at TEXT NOT NULL DEFAULT '2026-01-01T00:00:00Z',
                generation_error TEXT
            );
            CREATE TABLE IF NOT EXISTS questions (
                question_id INTEGER PRIMARY KEY AUTOINCREMENT,
                section_id TEXT NOT NULL,
                prompt TEXT NOT NULL,
                topics TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT '2026-01-01T00:00:00Z'
            );
            CREATE TABLE IF NOT EXISTS quiz_questions (
                quiz_id INTEGER NOT NULL,
                question_id INTEGER NOT NULL,
                position INTEGER NOT NULL DEFAULT 1,
                PRIMARY KEY (quiz_id, question_id)
            );
            CREATE TABLE IF NOT EXISTS quiz_attempts (
                attempt_id INTEGER PRIMARY KEY AUTOINCREMENT,
                quiz_id INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'in_progress',
                created_at TEXT NOT NULL,
                submitted_at TEXT,
                graded_at TEXT
            );
            CREATE TABLE IF NOT EXISTS attempt_questions (
                attempt_id INTEGER NOT NULL,
                question_id INTEGER NOT NULL,
                position INTEGER NOT NULL DEFAULT 1,
                response TEXT,
                is_correct INTEGER,
                explanation TEXT,
                PRIMARY KEY (attempt_id, question_id)
            );
            CREATE TABLE IF NOT EXISTS notes (
                note_id INTEGER PRIMARY KEY AUTOINCREMENT,
                chapter_id TEXT NOT NULL,
                section_id TEXT,
                body TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS section_completions (
                section_id TEXT PRIMARY KEY,
                chapter_id TEXT NOT NULL,
                marked_at TEXT NOT NULL
            );
            """
        )
        conn.commit()
    finally:
        conn.close()

    # Confirm test_suite column is absent before migration
    pre_cols = _get_table_columns(db_path, "questions")
    assert "test_suite" not in pre_cols, (
        f"Pre-condition failed: the manually-created 'existing' DB already has "
        f"'test_suite' in questions columns: {pre_cols!r}. "
        "This test simulates a pre-TASK-016 DB — test_suite must be absent before "
        "calling init_schema()."
    )

    # Now run init_schema() (the TASK-016 bootstrap) on the existing DB
    monkeypatch.setenv("NOTES_DB_PATH", db_path)
    try:
        from app.persistence import init_schema  # noqa: PLC0415
        init_schema()
    except Exception as exc:
        pytest.fail(
            f"init_schema() raised {exc!r} when called on an existing DB that "
            "lacks the questions.test_suite column. "
            "AC-3/ADR-041: _apply_additive_migrations must add the column without "
            "error via the PRAGMA table_info check + ALTER TABLE ADD COLUMN."
        )

    # After migration, test_suite must be present
    post_cols = _get_table_columns(db_path, "questions")
    assert "test_suite" in post_cols, (
        f"After init_schema() on a pre-TASK-016 DB, questions table still lacks "
        f"'test_suite' column. Post-migration columns: {post_cols!r}. "
        "AC-3/ADR-041: _apply_additive_migrations must add questions.test_suite TEXT "
        "to an existing DB via ALTER TABLE ADD COLUMN."
    )


def test_no_user_id_on_questions_table_after_task016(tmp_path, monkeypatch) -> None:
    """
    AC-3 (TASK-016) / MC-7 / ADR-041 §Scope: adding `questions.test_suite` must
    NOT introduce a `user_id` column on the `questions` table.

    ADR-041 §Scope: 'No user_id (MC-7).' MC-7: 'no user_id columns, no auth
    middleware, no per-user data partitioning, no role checks.'

    Trace: AC-3; ADR-041 §Scope; MC-7; Manifest §5 'No multi-user features'.
    """
    db_path = str(tmp_path / "no_user_id.db")
    _bootstrap_and_make_client(monkeypatch, db_path)

    cols = _get_table_columns(db_path, "questions")
    assert "user_id" not in cols, (
        f"questions table has a 'user_id' column after TASK-016 bootstrap: {cols!r}. "
        "AC-3/MC-7/ADR-041: adding questions.test_suite must NOT introduce a user_id. "
        "Manifest §5 'No multi-user features' — no user_id on any Quiz-domain table."
    )


# ===========================================================================
# AC-4 — Processor + well-formed artefact → Questions carry test_suite verbatim
# Trace: TASK-016 AC-4; ADR-040 §Processor wiring; ADR-041 §add_questions_to_quiz
# ===========================================================================


def test_processor_happy_path_all_questions_carry_test_suite(
    tmp_path, monkeypatch
) -> None:
    """
    AC-4 (TASK-016) / ADR-040 §Processor wiring: when the processor runs with a
    canned artefact in which each question has a well-formed `test_suite`, every
    persisted `questions` row must carry a non-null, non-empty `test_suite`.

    ADR-040: 'the generation processor reads it from the aiw run artefact and
    passes it to the persistence call verbatim.'

    Boundary: ≥1 question (confirmed).

    Trace: AC-4; ADR-040 §Processor wiring; ADR-041 §add_questions_to_quiz.
    """
    db_path = str(tmp_path / "happy_ts.db")
    client = _bootstrap_and_make_client(monkeypatch, db_path)

    client.post(
        f"/lecture/{MANDATORY_CHAPTER_ID}/sections/{MANDATORY_FIRST_SECTION}/quiz",
        follow_redirects=False,
    )

    success_stdout = _make_success_stdout_with_test_suites([
        {
            "prompt": "Implement a hash table with open addressing in C++.",
            "topics": ["hashing", "arrays"],
            "test_suite": _TEST_SUITE_HASH_TABLE,
        },
        {
            "prompt": "Write a binary search function over a sorted integer array.",
            "topics": ["search", "binary-search"],
            "test_suite": _TEST_SUITE_BINARY_SEARCH,
        },
    ])
    mock_proc = _make_completed_process(stdout=success_stdout)
    _run_processor(monkeypatch, db_path, mock_proc)

    # Quiz should be ready
    quiz_rows = _db_rows(db_path, "SELECT status FROM quizzes")
    assert quiz_rows and quiz_rows[0]["status"] == "ready", (
        f"Quiz status after processor run: {quiz_rows[0]['status'] if quiz_rows else 'NONE'}. "
        "AC-4: expected 'ready'."
    )

    # Every questions row must carry a non-null, non-empty test_suite
    question_rows = _db_rows(db_path, "SELECT prompt, test_suite FROM questions")
    assert len(question_rows) >= 1, (
        f"No questions rows persisted. AC-4: ≥1 question must be in the Bank."
    )
    for row in question_rows:
        assert row["test_suite"] is not None, (
            f"Question '{row['prompt']!r}' has test_suite=NULL. "
            "AC-4/ADR-040: every persisted Question must carry a non-null test_suite "
            "when the artefact provides one."
        )
        assert row["test_suite"].strip() != "", (
            f"Question '{row['prompt']!r}' has an empty/whitespace-only test_suite. "
            "AC-4/ADR-040: the test_suite must be a non-empty string of test code."
        )


def test_processor_happy_path_test_suite_stored_verbatim(
    tmp_path, monkeypatch
) -> None:
    """
    AC-4 (TASK-016) / ADR-040 §Processor wiring: the stored `test_suite` must
    equal the exact value from the artefact — not transformed, not regenerated.

    ADR-040: 'the generation processor reads it … and passes it to the
    persistence call verbatim.'

    Trace: AC-4; ADR-040 §Processor wiring (verbatim storage commitment).
    """
    db_path = str(tmp_path / "verbatim.db")
    client = _bootstrap_and_make_client(monkeypatch, db_path)

    client.post(
        f"/lecture/{MANDATORY_CHAPTER_ID}/sections/{MANDATORY_FIRST_SECTION}/quiz",
        follow_redirects=False,
    )

    exact_test_suite = (
        "# Exact test suite — must be stored byte-for-byte\n"
        "def test_unique_marker_abc123():\n"
        "    result = solve()\n"
        "    assert result == 42, f'Expected 42, got {result}'\n"
    )
    success_stdout = _make_success_stdout_with_test_suites([
        {
            "prompt": "Implement solve() to return 42.",
            "topics": ["coding"],
            "test_suite": exact_test_suite,
        },
    ])
    mock_proc = _make_completed_process(stdout=success_stdout)
    _run_processor(monkeypatch, db_path, mock_proc)

    rows = _db_rows(db_path, "SELECT test_suite FROM questions")
    assert len(rows) == 1, f"Expected 1 questions row, got {len(rows)}."
    stored = rows[0]["test_suite"]
    assert stored == exact_test_suite, (
        f"Stored test_suite differs from artefact value.\n"
        f"Expected: {exact_test_suite!r}\n"
        f"Got:      {stored!r}\n"
        "AC-4/ADR-040: the test_suite must be stored verbatim — not transformed, "
        "not regenerated."
    )


def test_list_questions_for_quiz_returns_test_suite_field(
    tmp_path, monkeypatch
) -> None:
    """
    AC-4 (TASK-016) / ADR-041 §No new accessor: `list_questions_for_quiz` must
    return `Question` dataclasses that carry the `test_suite` attribute.

    ADR-041: 'the existing Question-returning accessors … carry the new field
    through automatically … list_questions_for_quiz's SELECT adds q.test_suite
    so _row_to_question can read it.'

    Edge: also tests that a legacy Question (test_suite=NULL) has test_suite=None
    on the dataclass, not an AttributeError.

    Trace: AC-4; ADR-041 §No new accessor; ADR-039 (list_questions_for_quiz
    consumed, signature unchanged).
    """
    db_path = str(tmp_path / "round_trip.db")
    client = _bootstrap_and_make_client(monkeypatch, db_path)

    client.post(
        f"/lecture/{MANDATORY_CHAPTER_ID}/sections/{MANDATORY_FIRST_SECTION}/quiz",
        follow_redirects=False,
    )

    stored_suite = _TEST_SUITE_HASH_TABLE
    success_stdout = _make_success_stdout_with_test_suites([
        {
            "prompt": "Implement a hash table.",
            "topics": ["hashing"],
            "test_suite": stored_suite,
        },
    ])
    mock_proc = _make_completed_process(stdout=success_stdout)
    _run_processor(monkeypatch, db_path, mock_proc)

    quiz_rows = _db_rows(db_path, "SELECT quiz_id FROM quizzes WHERE status = 'ready'")
    assert quiz_rows, "No ready Quiz found after processor run."
    quiz_id = quiz_rows[0]["quiz_id"]

    from app.persistence import list_questions_for_quiz  # noqa: PLC0415
    questions = list_questions_for_quiz(quiz_id)

    assert len(questions) >= 1, (
        f"list_questions_for_quiz({quiz_id}) returned 0 questions. "
        "Expected ≥1 after a successful processor run."
    )

    for q in questions:
        assert hasattr(q, "test_suite"), (
            f"Question dataclass {q!r} has no 'test_suite' attribute. "
            "AC-4/ADR-041: Question dataclass must carry test_suite: str | None."
        )
    # The round-trip value must equal what was persisted
    first = questions[0]
    assert first.test_suite == stored_suite, (
        f"Question.test_suite={first.test_suite!r}; expected {stored_suite!r}. "
        "AC-4/ADR-041: list_questions_for_quiz must carry test_suite through the "
        "row→dataclass converter."
    )


# ===========================================================================
# AC-5 — Missing / empty / whitespace-only test_suite → generation_failed, zero rows
# Trace: TASK-016 AC-5; ADR-040 §Bad-test-suite failure handling; MC-5
# ===========================================================================


def test_processor_empty_test_suite_yields_generation_failed(
    tmp_path, monkeypatch
) -> None:
    """
    AC-5 (TASK-016) / MC-5 / ADR-040 §Bad-test-suite failure handling: when the
    artefact contains a question whose `test_suite` is the empty string, the
    processor must set the Quiz to `generation_failed`.

    ADR-040: 'a Question whose LLM-supplied test_suite is missing / empty /
    whitespace-only → the whole Quiz is generation_failed … zero questions rows
    persisted … no placeholder test suite synthesized anywhere.'

    Note: pydantic's min_length=1 may catch a literally-empty test_suite *inside
    the aiw run subprocess* (returning a non-zero exit), but the processor's own
    sanity check must catch it too (belt and braces — ADR-040 Alternative C).
    Either way, the outcome must be generation_failed.

    Negative: confirms MC-5 — no fabricated Question shipped.

    Trace: AC-5; ADR-040 §Bad-test-suite failure handling; MC-5 (blocker —
    'never fabricates a result'); Manifest §6 'AI failures are visible'.
    """
    db_path = str(tmp_path / "empty_ts_fail.db")
    client = _bootstrap_and_make_client(monkeypatch, db_path)

    client.post(
        f"/lecture/{MANDATORY_CHAPTER_ID}/sections/{MANDATORY_FIRST_SECTION}/quiz",
        follow_redirects=False,
    )
    quiz_id = _db_rows(db_path, "SELECT quiz_id FROM quizzes")[0]["quiz_id"]

    # Artefact with one question whose test_suite is empty string
    bad_stdout = _make_success_stdout_with_test_suites([
        {
            "prompt": "Implement a stack.",
            "topics": ["stack"],
            "test_suite": "",  # EMPTY — must trigger generation_failed
        },
    ])
    mock_proc = _make_completed_process(stdout=bad_stdout)
    _run_processor(monkeypatch, db_path, mock_proc)

    quiz_rows = _db_rows(
        db_path, "SELECT status FROM quizzes WHERE quiz_id = ?", (quiz_id,)
    )
    assert quiz_rows, "Quiz row not found."
    assert quiz_rows[0]["status"] == "generation_failed", (
        f"Quiz status={quiz_rows[0]['status']!r} after empty test_suite artefact; "
        "expected 'generation_failed'. "
        "AC-5/MC-5/ADR-040: an empty test_suite is not a shippable Question — "
        "the whole Quiz must end generation_failed."
    )


def test_processor_missing_test_suite_key_yields_generation_failed(
    tmp_path, monkeypatch
) -> None:
    """
    AC-5 (TASK-016) / MC-5 / ADR-040 §Bad-test-suite failure handling: when the
    artefact contains a question dict with no `test_suite` key at all, the processor
    must set the Quiz to `generation_failed`.

    ADR-040: 'a Question whose LLM-supplied test_suite is missing / empty /
    whitespace-only → the whole Quiz is generation_failed.'

    This tests the "missing key entirely" case (the LLM simply omitted the field).

    Trace: AC-5; ADR-040 §Bad-test-suite failure handling; MC-5.
    """
    db_path = str(tmp_path / "missing_ts_key.db")
    client = _bootstrap_and_make_client(monkeypatch, db_path)

    client.post(
        f"/lecture/{MANDATORY_CHAPTER_ID}/sections/{MANDATORY_FIRST_SECTION}/quiz",
        follow_redirects=False,
    )
    quiz_id = _db_rows(db_path, "SELECT quiz_id FROM quizzes")[0]["quiz_id"]

    # Artefact where test_suite is absent (pre-TASK-016 style from TASK-014)
    bad_stdout = _make_success_stdout_with_test_suites([
        {
            "prompt": "Implement a stack.",
            "topics": ["stack"],
            # "test_suite" key is intentionally MISSING
        },
    ])
    mock_proc = _make_completed_process(stdout=bad_stdout)
    _run_processor(monkeypatch, db_path, mock_proc)

    quiz_rows = _db_rows(
        db_path, "SELECT status FROM quizzes WHERE quiz_id = ?", (quiz_id,)
    )
    assert quiz_rows, "Quiz row not found."
    assert quiz_rows[0]["status"] == "generation_failed", (
        f"Quiz status={quiz_rows[0]['status']!r} after missing-test_suite artefact; "
        "expected 'generation_failed'. "
        "AC-5/MC-5/ADR-040: a Question without a test_suite key is not shippable — "
        "the whole Quiz must end generation_failed."
    )


def test_processor_missing_test_suite_zero_questions_persisted(
    tmp_path, monkeypatch
) -> None:
    """
    AC-5 (TASK-016) / MC-5 / ADR-040 §Bad-test-suite failure handling: when a
    Question's test_suite is missing/empty, ZERO `questions` rows must be persisted.

    ADR-040: 'zero questions rows persisted for that Quiz … no placeholder test
    suite synthesized anywhere (no "empty test file", no "pass test", no "TODO").'

    This is the MC-5 invariant in its most concrete form — not a single
    fabricated placeholder Question must appear in the Bank.

    Trace: AC-5; ADR-040 §Bad-test-suite failure handling; MC-5 (blocker).
    """
    db_path = str(tmp_path / "bad_ts_no_rows.db")
    client = _bootstrap_and_make_client(monkeypatch, db_path)

    client.post(
        f"/lecture/{MANDATORY_CHAPTER_ID}/sections/{MANDATORY_FIRST_SECTION}/quiz",
        follow_redirects=False,
    )

    bad_stdout = _make_success_stdout_with_test_suites([
        {
            "prompt": "Implement a queue.",
            "topics": ["queue"],
            "test_suite": "",  # empty — triggers generation_failed
        },
    ])
    mock_proc = _make_completed_process(stdout=bad_stdout)
    _run_processor(monkeypatch, db_path, mock_proc)

    question_rows = _db_rows(db_path, "SELECT question_id FROM questions")
    assert question_rows == [], (
        f"After a bad-test-suite artefact, {len(question_rows)} questions row(s) "
        "were persisted; expected 0. "
        "AC-5/MC-5/ADR-040: zero questions rows must be persisted when any Question "
        "lacks a real test suite. No placeholder test suite must be synthesized — "
        "that is a fabrication (MC-5 blocker). The whole Quiz ends generation_failed."
    )


def test_processor_only_one_question_missing_test_suite_fails_whole_quiz(
    tmp_path, monkeypatch
) -> None:
    """
    AC-5 (TASK-016) / ADR-040 §Bad-test-suite failure handling §Alternatives D:
    when a batch of 3 questions has only ONE with a missing/empty test_suite, the
    WHOLE Quiz ends `generation_failed` and ZERO questions rows are persisted.

    ADR-040 §Why the whole-Quiz check (reject the whole Quiz), not drop-and-proceed:
    'A partial-success path introduces a "how few is too few?" question … the
    whole-Quiz reject mirrors ADR-037's existing "no valid coding-task Questions →
    generation_failed, not ship whatever's valid" posture.'

    Edge: even 2 out of 3 questions having valid test suites is not enough —
    the whole batch fails if one Question is missing its test suite.

    Trace: AC-5; ADR-040 §Bad-test-suite failure handling (whole-Quiz reject);
    ADR-040 Alternative D rejected; MC-5.
    """
    db_path = str(tmp_path / "partial_bad.db")
    client = _bootstrap_and_make_client(monkeypatch, db_path)

    client.post(
        f"/lecture/{MANDATORY_CHAPTER_ID}/sections/{MANDATORY_FIRST_SECTION}/quiz",
        follow_redirects=False,
    )
    quiz_id = _db_rows(db_path, "SELECT quiz_id FROM quizzes")[0]["quiz_id"]

    # 3 questions: 2 good, 1 missing test_suite
    bad_stdout = _make_success_stdout_with_test_suites([
        {
            "prompt": "Implement a hash table.",
            "topics": ["hashing"],
            "test_suite": _TEST_SUITE_HASH_TABLE,  # good
        },
        {
            "prompt": "Write a binary search.",
            "topics": ["search"],
            "test_suite": _TEST_SUITE_BINARY_SEARCH,  # good
        },
        {
            "prompt": "Implement a stack.",
            "topics": ["stack"],
            "test_suite": "",  # BAD — empty
        },
    ])
    mock_proc = _make_completed_process(stdout=bad_stdout)
    _run_processor(monkeypatch, db_path, mock_proc)

    quiz_rows = _db_rows(
        db_path, "SELECT status FROM quizzes WHERE quiz_id = ?", (quiz_id,)
    )
    assert quiz_rows and quiz_rows[0]["status"] == "generation_failed", (
        f"Quiz status={quiz_rows[0]['status']!r} after a 2-good-1-bad batch; "
        "expected 'generation_failed'. "
        "AC-5/ADR-040 §Whole-Quiz reject: the whole Quiz must fail even if only "
        "ONE question has a bad test_suite (ADR-040 Alternative D rejected)."
    )

    question_rows = _db_rows(db_path, "SELECT question_id FROM questions")
    assert question_rows == [], (
        f"After a 2-good-1-bad batch, {len(question_rows)} questions row(s) were "
        "persisted; expected 0. "
        "AC-5/ADR-040: even the good Questions must NOT be persisted when the whole "
        "Quiz fails — zero rows, no partial bank."
    )


def test_processor_whitespace_only_test_suite_fails_generation(
    tmp_path, monkeypatch
) -> None:
    """
    AC-5 (TASK-016) / ADR-040 §Bad-test-suite failure handling: a whitespace-only
    test_suite (e.g. '   \\n  ') must cause `generation_failed`.

    ADR-040: 'The processor's .strip() check catches the "the LLM emitted
    whitespace" / "the artefact's JSON is malformed enough that test_suite is
    missing entirely" cases.'

    Note: pydantic's min_length=1 counts whitespace characters, so '   '
    passes the pydantic validator but the processor's .strip() check must
    catch it.  Either the pydantic validator strip-and-min_length rejects it
    (also fine) OR the processor catches it — either way the outcome must be
    generation_failed.

    Edge: whitespace-only is the grey zone between empty (pydantic rejects) and
    valid (non-empty after strip) — a real LLM response could emit this.

    Trace: AC-5; ADR-040 §Bad-test-suite failure handling (whitespace check);
    MC-5.
    """
    db_path = str(tmp_path / "whitespace_ts.db")
    client = _bootstrap_and_make_client(monkeypatch, db_path)

    client.post(
        f"/lecture/{MANDATORY_CHAPTER_ID}/sections/{MANDATORY_FIRST_SECTION}/quiz",
        follow_redirects=False,
    )
    quiz_id = _db_rows(db_path, "SELECT quiz_id FROM quizzes")[0]["quiz_id"]

    bad_stdout = _make_success_stdout_with_test_suites([
        {
            "prompt": "Implement a BST insert.",
            "topics": ["BST"],
            "test_suite": "   \n   \t   ",  # whitespace only — not real test code
        },
    ])
    mock_proc = _make_completed_process(stdout=bad_stdout)
    _run_processor(monkeypatch, db_path, mock_proc)

    quiz_rows = _db_rows(
        db_path, "SELECT status FROM quizzes WHERE quiz_id = ?", (quiz_id,)
    )
    assert quiz_rows, "Quiz row not found."
    assert quiz_rows[0]["status"] == "generation_failed", (
        f"Quiz status={quiz_rows[0]['status']!r} after whitespace-only test_suite; "
        "expected 'generation_failed'. "
        "AC-5/ADR-040: whitespace-only test_suite is not a real test suite — "
        "the processor's .strip() check must catch it and set generation_failed."
    )

    question_rows = _db_rows(db_path, "SELECT question_id FROM questions")
    assert question_rows == [], (
        f"After whitespace-only test_suite, {len(question_rows)} questions row(s) "
        "were persisted; expected 0 (MC-5 — no placeholder shipped)."
    )


# ===========================================================================
# AC-7 — Per-Section surface unchanged for a `ready` Quiz (no "Run tests" link)
# Trace: TASK-016 AC-7; ADR-040 §Per-Section ready-entry caption (unchanged);
#        ADR-040 Alternative E rejected; ADR-038 (surface spec)
# ===========================================================================


def test_section_quiz_surface_unchanged_for_ready_quiz(
    tmp_path, monkeypatch
) -> None:
    """
    AC-7 (TASK-016) / ADR-040 §Per-Section caption (unchanged): after the
    processor walks a Quiz (with test suites) to `ready`, the per-Section Quiz
    block must:
      - Show "Ready" (and the "Take this Quiz" link — ADR-038)
      - NOT show any "Run tests" or "run tests" affordance (that is the runner
        slice — TASK-016 deliberately does not ship it, ADR-040)
      - NOT show a "… Questions, each with tests" caption variant (ADR-040
        Alternative E rejected: 'a caption that mentions tests before the
        runner exists risks implying the learner can run them')

    Trace: AC-7; ADR-040 §Per-Section ready-entry caption (unchanged decision);
    ADR-040 Alternative E (rejected); ADR-038 §ready state.
    """
    db_path = str(tmp_path / "surface_unchanged.db")
    client = _bootstrap_and_make_client(monkeypatch, db_path)

    client.post(
        f"/lecture/{MANDATORY_CHAPTER_ID}/sections/{MANDATORY_FIRST_SECTION}/quiz",
        follow_redirects=False,
    )

    success_stdout = _make_success_stdout_with_test_suites([
        {
            "prompt": "Implement a min-heap.",
            "topics": ["heaps"],
            "test_suite": _TEST_SUITE_HASH_TABLE,
        },
    ])
    mock_proc = _make_completed_process(stdout=success_stdout)
    _run_processor(monkeypatch, db_path, mock_proc)

    response = client.get(f"/lecture/{MANDATORY_CHAPTER_ID}")
    assert response.status_code == 200
    html = response.text

    # Surface must still show "Ready" state (ADR-038 — the quiz is ready)
    ready_signalled = (
        "section-quiz-item--ready" in html
        or "Ready" in html
    )
    assert ready_signalled, (
        f"GET /lecture/{MANDATORY_CHAPTER_ID} does not show 'Ready' after the Quiz "
        "was walked to ready with test suites. "
        "AC-7/ADR-038/ADR-040: the surface must still show the 'Ready' state."
    )

    # Surface must NOT show any "Run tests" affordance (that is the runner slice)
    run_tests_present = (
        "run tests" in html.lower()
        or "run-tests" in html.lower()
        or "runtests" in html.lower()
    )
    assert not run_tests_present, (
        f"GET /lecture/{MANDATORY_CHAPTER_ID} shows a 'Run tests' affordance "
        "after TASK-016's quiz walk. "
        "AC-7/ADR-040 §Per-Section caption (unchanged) / Alternative E (rejected): "
        "TASK-016 does NOT ship the in-app test-runner affordance. The surface must "
        "remain unchanged from ADR-038 — no 'Run tests' button, link, or caption."
    )


# ===========================================================================
# AC-8 — Take surface renders prompt AND test_suite (ADR-043 resolved ADR-040 deferral)
# Trace: TASK-016 AC-8; ADR-040 §Take surface (deferred to runner slice);
#        ADR-043 §quiz_take.html.j2 changes (decided: show test_suite read-only);
#        ADR-038; ADR-039
# ===========================================================================


def test_take_surface_renders_prompt_and_test_suite(tmp_path, monkeypatch) -> None:
    """
    AC-8 (TASK-016) / ADR-043 §quiz_take.html.j2 changes: the Quiz-taking surface
    must render the Question prompt (unchanged from ADR-038) AND must render the
    Question's test_suite as a read-only block — a
    <pre class="quiz-take-test-suite">{{ aq.test_suite }}</pre> per in_progress
    Question (ADR-043 is the in-app-runner slice that resolved ADR-040's deferral).

    ADR-040 deferred the 'show the test suite on the take page or not?' decision
    to the in-app-runner slice. ADR-043 is that slice and decided: show it read-only.
    The prompt assertion (prompt must appear) remains valid. The former 'must NOT
    appear' assertion for test_suite is inverted: the test_suite content MUST appear
    in a .quiz-take-test-suite block on the in_progress take page.

    Trace: AC-8; ADR-040 §Take surface (deferred decision);
           ADR-043 §quiz_take.html.j2 changes (decided: show test_suite read-only);
           ADR-038; ADR-039.
    """
    db_path = str(tmp_path / "take_renders_test_suite.db")
    client = _bootstrap_and_make_client(monkeypatch, db_path)

    # Create and walk a Quiz to ready
    client.post(
        f"/lecture/{MANDATORY_CHAPTER_ID}/sections/{MANDATORY_FIRST_SECTION}/quiz",
        follow_redirects=False,
    )

    unique_prompt = "Implement two_sum(nums, target) in C++ — unique marker XYZ789."
    unique_test_suite = (
        "void test_two_sum_XYZ789() {\n"
        "    // This test suite string MUST appear on the take page (ADR-043)\n"
        "    auto result = two_sum({2, 7, 11, 15}, 9);\n"
        "    assert(result == std::vector<int>({0, 1}));\n"
        "}\n"
    )
    success_stdout = _make_success_stdout_with_test_suites([
        {
            "prompt": unique_prompt,
            "topics": ["arrays"],
            "test_suite": unique_test_suite,
        },
    ])
    mock_proc = _make_completed_process(stdout=success_stdout)
    _run_processor(monkeypatch, db_path, mock_proc)

    quiz_rows = _db_rows(db_path, "SELECT quiz_id FROM quizzes WHERE status = 'ready'")
    assert quiz_rows, "No ready Quiz found."
    quiz_id = quiz_rows[0]["quiz_id"]

    # GET the take surface (ADR-038)
    take_url = (
        f"/lecture/{MANDATORY_CHAPTER_ID}/sections/{MANDATORY_FIRST_SECTION}"
        f"/quiz/{quiz_id}/take"
    )
    response = client.get(take_url)
    assert response.status_code == 200, (
        f"GET {take_url} returned {response.status_code}; expected 200. "
        "The take surface must be reachable for a ready Quiz."
    )
    html = response.text

    # The Question's prompt must appear on the take page
    assert unique_prompt in html, (
        f"The take page does not contain the Question prompt {unique_prompt!r}. "
        "AC-8: the take page must render attempt_questions (the prompt)."
    )

    # The Question's test_suite MUST appear on the take page (ADR-043)
    assert "test_two_sum_XYZ789" in html, (
        f"The take page does not render the Question's test_suite content "
        "('test_two_sum_XYZ789' not found in HTML). "
        "ADR-043 §quiz_take.html.j2 changes: the in_progress take page must render "
        "a read-only <pre class='quiz-take-test-suite'>{{ aq.test_suite }}</pre> "
        "block per Question. ADR-040 deferred this decision to the runner slice; "
        "ADR-043 resolved it: show the test suite read-only."
    )


# ===========================================================================
# Scale / performance
# Trace: TASK-016 AC-4; ADR-040 §Processor wiring; ADR-041 §add_questions_to_quiz
#        (one-transaction discipline — ADR-037's existing posture)
# ===========================================================================


def test_processor_with_multiple_questions_all_test_suites_persisted(
    tmp_path, monkeypatch
) -> None:
    """
    AC-4 (TASK-016) / ADR-040 §Processor wiring: with 5 questions in the artefact
    (each with a distinct test_suite), every persisted `questions` row carries
    its own test_suite.

    Edge: tests the iteration over the full questions list (not just the first
    question).

    Trace: AC-4; ADR-040 §Processor wiring (all questions persisted verbatim).
    """
    db_path = str(tmp_path / "multi_q.db")
    client = _bootstrap_and_make_client(monkeypatch, db_path)

    client.post(
        f"/lecture/{MANDATORY_CHAPTER_ID}/sections/{MANDATORY_FIRST_SECTION}/quiz",
        follow_redirects=False,
    )

    questions_payload = [
        {
            "prompt": f"Implement concept {i} in C++.",
            "topics": [f"topic-{i}"],
            "test_suite": f"def test_concept_{i}():\n    assert concept_{i}() is not None\n",
        }
        for i in range(1, 6)  # 5 questions
    ]
    success_stdout = _make_success_stdout_with_test_suites(questions_payload)
    mock_proc = _make_completed_process(stdout=success_stdout)
    _run_processor(monkeypatch, db_path, mock_proc)

    question_rows = _db_rows(db_path, "SELECT prompt, test_suite FROM questions")
    assert len(question_rows) == 5, (
        f"Expected 5 questions rows, got {len(question_rows)}. "
        "Edge/ADR-040: all 5 questions from the artefact must be persisted."
    )
    for row in question_rows:
        assert row["test_suite"] is not None and row["test_suite"].strip() != "", (
            f"Question '{row['prompt']!r}' has a null/empty test_suite. "
            "AC-4/ADR-040: every question in the batch must carry its test_suite."
        )
    # Also verify test_suites differ (verbatim, not all the same placeholder)
    test_suites = {row["test_suite"] for row in question_rows}
    assert len(test_suites) == 5, (
        f"All {len(question_rows)} questions have identical test_suites: {test_suites!r}. "
        "Expected 5 distinct test_suite values (each question has its own)."
    )


def test_processor_with_five_questions_persists_all_within_budget(
    tmp_path, monkeypatch
) -> None:
    """
    Performance (TASK-016) / ADR-041 §add_questions_to_quiz (one-transaction
    discipline): processing a Quiz with 5 generated questions (each with a
    test_suite) must complete within 5 seconds.

    ADR-037's existing posture: add_questions_to_quiz uses one transaction for
    all INSERTs. TASK-016 adds one more column per INSERT (test_suite) —
    this test confirms the extension does not degrade performance.

    The 5-second budget is generous (the goal is to catch O(n²) regressions,
    not to micro-benchmark). Scale surface: the processor iterates the questions
    list; a per-question transaction with an extra SELECT per row would be O(n²).

    Trace: Performance; ADR-037 §One-transaction discipline; ADR-041
    §add_questions_to_quiz.
    """
    db_path = str(tmp_path / "perf.db")
    client = _bootstrap_and_make_client(monkeypatch, db_path)

    client.post(
        f"/lecture/{MANDATORY_CHAPTER_ID}/sections/{MANDATORY_FIRST_SECTION}/quiz",
        follow_redirects=False,
    )

    questions_payload = [
        {
            "prompt": f"Implement concept {i} in C++ with a test.",
            "topics": [f"concept-{i}"],
            "test_suite": (
                f"def test_concept_{i}_perf():\n"
                f"    result = concept_{i}()\n"
                f"    assert result is not None, 'concept_{i} returned None'\n"
            ),
        }
        for i in range(1, 6)
    ]
    success_stdout = _make_success_stdout_with_test_suites(questions_payload)
    mock_proc = _make_completed_process(stdout=success_stdout)

    t0 = time.monotonic()
    _run_processor(monkeypatch, db_path, mock_proc)
    elapsed = time.monotonic() - t0

    question_rows = _db_rows(db_path, "SELECT question_id FROM questions")
    assert len(question_rows) == 5, (
        f"Expected 5 questions rows after performance run, got {len(question_rows)}."
    )
    assert elapsed < 5.0, (
        f"Processing 5 questions with test_suites took {elapsed:.2f}s (limit: 5s). "
        "Performance/ADR-037/ADR-041: the one-transaction discipline must prevent "
        "O(n²) behavior. 5s is a generous ceiling for an in-memory SQLite operation."
    )
