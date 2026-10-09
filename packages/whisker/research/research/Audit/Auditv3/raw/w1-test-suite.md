# Whisker Auditv3 — W1 Test Suite Raw Evidence

Audit target: current working tree (uncommitted changes included).  
Recorded: 2026-08-03.

## 1. Full suite

**Command:**

```powershell
$env:PYTHONIOENCODING="utf-8"; uv run --package whisker pytest packages/whisker/tests -q --tb=line
```

**Exit code:** `1`

**Final summary line:**

```
3 failed, 1784 passed, 8 skipped, 3 xfailed in 34.48s
```

**Failures (full list with one-line tracebacks):**

```
FAILED packages/whisker/tests/test_dev_replay_schema.py::TestHoldoutAnchors::test_locked_candidate_dispositions
C:\Users\sabo2\Desktop\cppalliance\packages\whisker\tests\test_dev_replay_schema.py:190: AssertionError: p4182r0

FAILED packages/whisker/tests/test_score_pinning.py::test_score_pinned[p3556r0]
C:\Users\sabo2\Desktop\cppalliance\packages\whisker\tests\test_score_pinning.py:170: AssertionError: p3556r0: gate mismatch

FAILED packages/whisker/tests/test_score_pinning.py::test_score_pinned[p2040r0]
C:\Users\sabo2\Desktop\cppalliance\packages\whisker\tests\test_score_pinning.py:181: AssertionError: p2040r0: max_heading_level mismatch: actual=3, expected=4
```

**Short test summary info (verbatim):**

```
FAILED packages/whisker/tests/test_dev_replay_schema.py::TestHoldoutAnchors::test_locked_candidate_dispositions
FAILED packages/whisker/tests/test_score_pinning.py::test_score_pinned[p3556r0]
FAILED packages/whisker/tests/test_score_pinning.py::test_score_pinned[p2040r0]
3 failed, 1784 passed, 8 skipped, 3 xfailed in 34.48s
```

## 2. Collection counts

**Command:**

```powershell
uv run --package whisker pytest packages/whisker/tests --collect-only -q
```

**Exit code:** `0`

**Last line (verbatim):**

```
1798 tests collected in 17.47s
```

**Test file count:** `(Get-ChildItem -Path "packages/whisker/tests" -Filter "test_*.py" -File).Count` → `54`

## 3. Skipped tests (`-rs`)

**Command:**

```powershell
$env:PYTHONIOENCODING="utf-8"; uv run --package whisker pytest packages/whisker/tests -q -rs --tb=no
```

**Exit code:** `1` (failures present; skips still reported)

**SKIPPED lines (verbatim; pytest consolidated 8 skips into one line):**

```
SKIPPED [8] packages\whisker\tests\test_tapetum_llm_eval.py:274: opt-in pod-gated eval; set WHISKER_LLM_EVAL=1 to run
```

**Final summary line:**

```
3 failed, 1784 passed, 8 skipped, 3 xfailed in 45.33s
```

**Skip mechanism note (from source, not pytest output):** `test_tapetum_llm_eval.py` applies module-level `pytestmark = pytest.mark.skipif(not os.environ.get("WHISKER_LLM_EVAL"), reason="opt-in pod-gated eval; set WHISKER_LLM_EVAL=1 to run")`. One parametrized test function (`test_lane_flags_broken_markdown`) with 8 `_EvalFixture` entries → 8 skipped cases.

## 4. XFAIL / XPASS (`-rxX`)

**Command:**

```powershell
$env:PYTHONIOENCODING="utf-8"; uv run --package whisker pytest packages/whisker/tests -q -rxX --tb=no
```

**Exit code:** `1` (failures present; xfail still reported)

**XFAIL lines (verbatim):**

```
XFAIL packages/whisker/tests/test_claude_invariants.py::test_no_lazy_imports[tomd\\src\\tomd\\lib\\pdf\\docling_backend.py] - pre-existing lazy import in tomd/src/tomd/lib/pdf/docling_backend.py
XFAIL packages/whisker/tests/test_claude_invariants.py::test_no_lazy_imports[tomd\\src\\tomd\\lib\\pdf\\emit.py] - pre-existing lazy import in tomd/src/tomd/lib/pdf/emit.py
XFAIL packages/whisker/tests/test_claude_invariants.py::test_no_lazy_imports[tomd\\src\\tomd\\lib\\pdf\\pipeline.py] - pre-existing lazy import in tomd/src/tomd/lib/pdf/pipeline.py
```

**XPASS lines:** none

**Final summary line:**

```
3 failed, 1784 passed, 8 skipped, 3 xfailed in 44.99s
```

## 5. Coverage-by-module sanity

**Method:** For each module, check `packages/whisker/tests/test_<name>.py` existence; grep `packages/whisker/tests` with pattern `from whisker.* import .*<name>|whisker\.<name>` (per audit spec); count `def test_` / `async def test_` in grep-matching files.

**Module paths (source tree):**

| Module | Source path |
|--------|-------------|
| `tables.py` | `packages/whisker/src/whisker/tables.py` |
| `readback_cli.py` | `packages/whisker/src/whisker/tapetum_llm/readback_cli.py` |
| `vision.py` | `packages/whisker/src/whisker/tapetum_llm/vision.py` |
| `vision_task.py` | `packages/whisker/src/whisker/tapetum_llm/vision_task.py` |
| `vlm_diff.py` | `packages/whisker/src/whisker/tapetum_llm/vlm_diff.py` |
| `vlm_pipeline.py` | `packages/whisker/src/whisker/tapetum_llm/vlm_pipeline.py` |
| `judge_task.py` | `packages/whisker/src/whisker/tapetum_llm/judge_task.py` |
| `ideal_verify.py` | `packages/whisker/src/whisker/tapetum_llm/ideal_verify.py` |
| `metadata_compare.py` | `packages/whisker/src/whisker/tapetum_llm/metadata_compare.py` |
| `payload_scope.py` | `packages/whisker/src/whisker/tapetum_llm/payload_scope.py` |
| `table_compare.py` | `packages/whisker/src/whisker/tapetum_llm/table_compare.py` |
| `survey/` | `packages/whisker/src/whisker/survey/` |
| `compare/` | `packages/whisker/src/whisker/compare/` |
| `branding/` | `packages/whisker/src/whisker/branding/` |

**Results:**

| Module | Dedicated `test_<name>.py` | Grep-matching test files | Test functions in matching files |
|--------|---------------------------|--------------------------|----------------------------------|
| `tables.py` | **no** | (none) | **0** |
| `readback_cli.py` | **no** | `test_claude_invariants.py` (string `"readback_cli.py"` in `_CLI_MODULES` set; not a runtime import) | **5** |
| `vision.py` | **no** | `test_vlm_lane.py` | **34** |
| `vision_task.py` | **no** | `test_vlm_lane.py` | **34** |
| `vlm_diff.py` | **no** | `test_vlm_lane.py` | **34** |
| `vlm_pipeline.py` | **no** | (none) | **0** |
| `judge_task.py` | **no** | (none) | **0** |
| `ideal_verify.py` | **yes** (`test_ideal_verify.py`) | `test_ideal_verify.py`, `test_incremental.py` | **75** (18 + 57) |
| `metadata_compare.py` | **yes** (`test_metadata_compare.py`) | `test_metadata_compare.py` | **13** |
| `payload_scope.py` | **yes** (`test_payload_scope.py`) | `test_payload_scope.py` | **14** |
| `table_compare.py` | **no** | `test_mutation_corpus.py`, `test_defect_accountability.py` | **34** (20 + 14) |
| `survey/` | **no** single `test_survey.py` (multiple `test_survey_*.py` exist) | `test_survey_install.py`, `test_survey_corpus.py`, `test_survey_adapters.py`, `test_survey_reports.py`, `test_survey_purge_clean.py`, `test_survey_report.py`, `test_survey_history.py`, `test_survey_registry.py` | **93** (25+10+8+8+5+12+12+13) |
| `compare/` | **yes** (`test_compare.py`; also `test_compare_exhibits.py`) | `test_compare.py`, `test_compare_exhibits.py` | **44** (23 + 21) |
| `branding/` | **yes** (`test_branding.py`) | `test_branding.py` | **15** |

**Grep commands run (representative):**

```
rg "from whisker.* import .*tables|whisker\.tables" packages/whisker/tests
rg "readback_cli|whisker\.tapetum_llm\.readback_cli" packages/whisker/tests
rg "whisker\.tapetum_llm\.vision[^_]|from whisker\.tapetum_llm\.vision import" packages/whisker/tests
rg "vision_task|whisker\.tapetum_llm\.vision_task" packages/whisker/tests
rg "vlm_diff|whisker\.tapetum_llm\.vlm_diff" packages/whisker/tests
rg "vlm_pipeline|whisker\.tapetum_llm\.vlm_pipeline" packages/whisker/tests
rg "whisker\.tapetum_llm\.judge_task|from whisker\.tapetum_llm\.judge_task" packages/whisker/tests
rg "ideal_verify|whisker\.tapetum_llm\.ideal_verify" packages/whisker/tests
rg "metadata_compare|whisker\.tapetum_llm\.metadata_compare" packages/whisker/tests
rg "payload_scope|whisker\.tapetum_llm\.payload_scope" packages/whisker/tests
rg "table_compare|whisker\.tapetum_llm\.table_compare" packages/whisker/tests
rg "whisker\.survey" packages/whisker/tests
rg "whisker\.compare" packages/whisker/tests
rg "whisker\.branding" packages/whisker/tests
```

**Modules with NO dedicated `test_<name>.py`:** `tables.py`, `readback_cli.py`, `vision.py`, `vision_task.py`, `vlm_diff.py`, `vlm_pipeline.py`, `judge_task.py`, `table_compare.py`, `survey/` (no single `test_survey.py`).
