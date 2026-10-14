# C24 - VLM Boundary Auditor

**Mandate:** Assess the dormant VLM wiring.
**Focus dimensions:** D7 (package boundary integrity).

---

## 1. LOC Inventory Across VLM Files

| File | LOC (including headers/blanks) | Purpose |
|------|------|---------|
| `tapetum_llm/vlm_pipeline.py` | 98 | Entry point: rasterize -> transcribe -> diff |
| `tapetum_llm/vlm_diff.py` | 219 | Deterministic diff: VLM transcription vs tomd |
| `tapetum_llm/vision.py` | 124 | PDF page rasterization via PyMuPDF |
| `tapetum_llm/vision_task.py` | 211 | Whisker-local multimodal LLM dispatch |
| `tapetum_llm/transcribe.py` | 141 | Per-page VLM transcription schema + driver |
| **Total** | **793** | |

---

## 2. Production Entry Point Analysis

### 2.1 CLI Verbs

| Severity | **PASS** |
|----------|----------|
| Claim | No production CLI verb or flag calls VLM code. |
| Evidence | `__main__.py:1241-1263`: `main()` routes to `_score_main`, `_bench_main`, `_guard_main`, `_golden_main`, `_facts_main`, `_calibrate_main`, `_corpus_main`, `_score_file_main`, `_check_facts_main`. None of these import or call any VLM module. The `whisker-tapetum-llm` CLI (`tapetum_llm/cli.py`) is a separate console script. |
| Affected gate | D7 |
| Confidence | 0.99 |
| False-pass hypothesis | A hidden import in cli.py could pull VLM code into the text-lane CLI. |
| False-fail hypothesis | None. |

### 2.2 tapetum_llm CLI (cli.py)

| Severity | **PASS** |
|----------|----------|
| Claim | The `whisker-tapetum-llm` CLI does not invoke VLM code in its current text-lane-only implementation. |
| Evidence | `tapetum_llm/cli.py` (verified via `_source_kind` usage in test_vlm_lane.py:304-327): `_source_kind` is a routing helper that detects PDF/HTML/unknown, but the actual VLM pipeline (`vlm_adjudicate_paper`) is not called from the current CLI flow. The CLI routes to `adjudicate_paper` (the text-lane), not to `vlm_adjudicate_paper`. |
| Affected gate | D7 |
| Confidence | 0.95 |
| False-pass hypothesis | The `_source_kind` function exists in cli.py and is tested, suggesting VLM routing was planned but not connected. |
| False-fail hypothesis | None. |

---

## 3. `tapetum_llm/__init__.py` Exports

| Severity | **PASS** |
|----------|----------|
| Claim | VLM modules are NOT re-exported from `tapetum_llm/__init__.py`. |
| Evidence | `tapetum_llm/__init__.py:30-46`: re-exports only `Adjudication`, `AxisFinding`, `EvidenceSpan`, `FidelityAxis`, `TapetumResult`, `Verdict` from `tapetum_llm.models`. No imports from `vlm_pipeline`, `vlm_diff`, `vision`, `vision_task`, or `transcribe`. |
| Affected gate | D7 |
| Confidence | 0.99 |
| False-pass hypothesis | None: explicit inspection of `__all__` confirms no VLM exports. |
| False-fail hypothesis | None. |

---

## 4. Test Analysis (`test_vlm_lane.py`)

### 4.1 Test Composition

| Category | Test Count | Description |
|----------|-----------|-------------|
| Vision constants | 2 | `MAX_PAGES > 0`, `TARGET_PIXELS` range |
| Raster errors | 2 | Nonexistent file, non-PDF file |
| Transcription schema | 4 | `PageTranscription` with/without text, JSON roundtrip |
| Transcription result | 3 | Concatenation, empty, status default |
| Prompt content | 1 | Key instructions present in system prompt |
| VLM diff | 5 | Identical/different/similar text, source kind, sidecar format |
| Sidecar fusion compat | 2 | Required fields for fusion, sorted axis findings |
| Vision task | 6 | Pipeline stays text-only (GUARD TEST), agent construction, user_media signature, serial semaphore, retry budget, JSON extraction |
| Diff verdict mapping | 2 | Threshold ordering, empty-vs-empty |
| Fidelity error paths | 1 | Too many pages error |
| Source-kind routing | 5 | PDF/HTML/HTM/unknown/missing detection |
| **Total** | **33** | |

### 4.2 Guard Test: Pipeline Stays Text-Only

| Severity | **CRITICAL - PASS** |
|----------|---------------------|
| Claim | The pipeline package's signatures carry no vision parameters. This is a load-bearing guard test. |
| Evidence | `test_vlm_lane.py:215-224`: `test_pipeline_stays_text_only` asserts: `"user_media" not in inspect.signature(ModelBackend.run).parameters`, `"user_media" not in inspect.signature(AgentBackend.run).parameters`, `"user_media" not in inspect.signature(run_task).parameters`, `"vllm_vision" not in BACKEND_REGISTRY`. |
| Affected gate | D7 (package boundary) |
| Confidence | 0.99 |
| False-pass hypothesis | Someone adds `user_media` to pipeline and this test catches it. |
| False-fail hypothesis | None: the test is structural, not behavioral. |

### 4.3 Data Models vs Integration

| Severity | **INFO** |
|----------|----------|
| Claim | The 33 tests are primarily data model tests (schema validation, constant checks, error paths) and signature guards, not integration tests that exercise the full VLM pipeline with a real PDF + vision endpoint. |
| Evidence | No test calls `vlm_adjudicate_paper`, `transcribe_pages` with real images, or `rasterize_pdf` with a real PDF (the raster tests only check error paths with invalid inputs). The `diff_vlm_vs_tomd` tests use string-to-string comparison (identical/different text), not actual VLM transcription output. |
| Affected gate | D7 |
| Confidence | 0.95 |
| False-pass hypothesis | The tests prove the wiring compiles and the data shapes are correct, but they do not prove the pipeline works end-to-end with a real vision model. This is expected for dormant code. |
| False-fail hypothesis | None. |

---

## 5. Dependency Closure

### 5.1 Vision Module Dependencies

| Severity | **PASS** |
|----------|----------|
| Claim | The VLM modules do not require additional dependencies beyond what is already in `pyproject.toml`. |
| Evidence | - `vision.py:22`: `import pymupdf` - PyMuPDF is already a workspace dependency (used by tomd). - `vision_task.py:36-37`: `import openai; from openai import AsyncOpenAI` - `openai` is in the `tapetum-llm` optional extra. - `vision_task.py:38`: `from pydantic import BaseModel, ValidationError` - `pydantic` is in the `tapetum-llm` extra. - `transcribe.py:33`: `from pydantic import BaseModel, Field` - same. - `vlm_diff.py:27-33`: imports from `whisker.metrics` (internal). - `vlm_pipeline.py:20-25`: imports from whisker internal modules only. |
| Affected gate | D7 |
| Confidence | 0.97 |
| False-pass hypothesis | `pymupdf` is a workspace dependency but not explicitly listed in whisker's `pyproject.toml` `dependencies`. It is pulled transitively via `tomd` or other packages. If whisker were installed standalone without tomd, `vision.py` would fail to import. However, whisker already lists `tomd` as a core dependency, so `pymupdf` is available. |
| False-fail hypothesis | None. |

### 5.2 PyMuPDF Transitive Dependency Note

| Severity | **LOW** |
|----------|---------|
| Claim | `vision.py` imports `pymupdf` directly, but `pymupdf` is not listed in whisker's `pyproject.toml` dependencies. It is a transitive dependency via `tomd`. |
| Evidence | `pyproject.toml:20`: `"tomd"` is a core dependency. `vision.py:22`: `import pymupdf`. PyMuPDF is a dependency of tomd, not whisker directly. |
| Affected gate | D7 |
| Confidence | 0.90 |
| False-pass hypothesis | If tomd ever drops PyMuPDF, whisker's vision module would break. Low risk since vision is dormant. |
| False-fail hypothesis | None. |

---

## 6. Serial Semaphore (D11)

| Severity | **PASS** |
|----------|----------|
| Claim | The VLM lane uses the same serial dispatch pattern as the text lane: one in-flight vision request at a time. |
| Evidence | `vision_task.py:54-58`: `_VISION_TASK_CONCURRENCY = 1; _vision_task_semaphore = asyncio.Semaphore(_VISION_TASK_CONCURRENCY)`. `vision_task.py:155`: `async with _vision_task_semaphore:` wraps the API call. `test_vlm_lane.py:243-245`: `test_serial_dispatch_semaphore` asserts `vision_task._VISION_TASK_CONCURRENCY == 1`. |
| Affected gate | D7 (D11 compliance) |
| Confidence | 0.99 |
| False-pass hypothesis | None: module-level semaphore at 1 is structurally serial. |
| False-fail hypothesis | None. |

### 6.1 Sampling Pins (D5 Equivalent)

| Severity | **PASS** |
|----------|----------|
| Claim | Vision calls pin sampling parameters: temperature 0.0, top_p 1.0, seed 0. |
| Evidence | `vision_task.py:158-161`: `temperature=0.0, top_p=1.0, seed=0, max_tokens=agent.max_tokens`. |
| Affected gate | D7 (D5 compliance) |
| Confidence | 0.99 |
| False-pass hypothesis | None. |
| False-fail hypothesis | None. |

### 6.2 Finite Retry Budget (D10)

| Severity | **PASS** |
|----------|----------|
| Claim | Vision calls have a finite retry budget of 2 attempts. |
| Evidence | `vision_task.py:60-61`: `MAX_VISION_ATTEMPTS = 2`. `vision_task.py:156-205`: loop for `range(MAX_VISION_ATTEMPTS)` with retry on transient API errors and JSON parse failures. `test_vlm_lane.py:247-249`: `test_retry_budget_finite` asserts `1 <= MAX_VISION_ATTEMPTS <= 3`. |
| Affected gate | D7 (D10 compliance) |
| Confidence | 0.99 |
| False-pass hypothesis | None. |
| False-fail hypothesis | None. |

---

## 7. CLAUDE.md Known Gap #4 Status

| Severity | **CONFIRMED** |
|----------|---------------|
| Claim | CLAUDE.md Known gap #4 states: "`auto_baseline_checks` is not wired into `whisker facts`/`guard` output. Callable standalone only." |
| Evidence | `__main__.py`: no import or call of `auto_baseline_checks`. `facts.py` (per CLAUDE.md): `auto_baseline_checks(md)` exists but is not called from any CLI verb. This is accurately documented. The VLM lane is not directly related to this gap, but the gap is correctly documented as known. |
| Affected gate | D7 |
| Confidence | 0.95 |
| False-pass hypothesis | None. |
| False-fail hypothesis | None. |

---

## 8. D1 Exception Documentation

| Severity | **PASS** |
|----------|----------|
| Claim | The vision_task module's D1 exception (calling the LLM via raw openai client, not pipeline.run_agent) is documented with justification. |
| Evidence | `vision_task.py:8-26` (module docstring): "Documented D1 exception: D1 routes every LLM call through the pipeline framework, which cannot carry image parts without being changed. Package boundary (whisker-only changes) takes precedence, so this module performs the OpenAI-compatible multimodal call itself while preserving the framework's discipline: serial dispatch (D11), pinned sampling (D5 equivalent: temperature 0, top_p 1, seed 0), schema-in-prompt structured output (D6), finite retry budget (D10), full debug logging." |
| Affected gate | D7 |
| Confidence | 0.99 |
| False-pass hypothesis | None: the exception is explicitly justified and the module reimplements the framework's discipline. |
| False-fail hypothesis | None. |

---

## 9. Fidelity Policy

| Severity | **PASS** |
|----------|----------|
| Claim | The VLM lane follows the fidelity policy: any failure -> error (no partial results). |
| Evidence | `vlm_pipeline.py:49`: "Fidelity policy: any failure -> VlmLaneError (no partial results)." `vlm_pipeline.py:63-65`: `RasterError` -> `VlmLaneError`. `vlm_pipeline.py:77-78`: `TranscriptionError` -> `VlmLaneError`. `transcribe.py:128-131`: any page failure raises `TranscriptionError` (no partial transcription). |
| Affected gate | D7 |
| Confidence | 0.98 |
| False-pass hypothesis | None. |
| False-fail hypothesis | None. |

---

## Summary

| # | Finding | Severity | Status |
|---|---------|----------|--------|
| 1 | No production entry point calls VLM code | CRITICAL | PASS |
| 2 | VLM modules not re-exported from `__init__.py` | HIGH | PASS |
| 3 | Guard test: pipeline stays text-only | CRITICAL | PASS |
| 4 | 33 tests are data-model + signature guards, not integration | INFO | NOTED |
| 5 | VLM dependencies satisfied via existing extras | HIGH | PASS |
| 6 | `pymupdf` is transitive via `tomd`, not direct | LOW | NOTED |
| 7 | Serial semaphore (D11) enforced at module level | HIGH | PASS |
| 8 | Sampling pins (D5) hardcoded: temp 0, top_p 1, seed 0 | HIGH | PASS |
| 9 | Finite retry budget (D10) at 2 attempts | MEDIUM | PASS |
| 10 | D1 exception documented with full justification | HIGH | PASS |
| 11 | Fidelity policy: no partial results | HIGH | PASS |
| 12 | 793 LOC of dormant, well-structured, tested code | INFO | NOTED |

**Auditor verdict: The VLM boundary is clean and well-guarded.** 793 LOC of dormant code with a load-bearing guard test ensuring the pipeline package stays text-only. The VLM modules are self-contained within `tapetum_llm/`, not re-exported, and not called from any production entry point. The D1 exception is thoroughly documented and the module reimplements all framework discipline invariants (D5, D6, D10, D11).
