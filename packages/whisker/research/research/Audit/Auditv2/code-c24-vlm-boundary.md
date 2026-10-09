# C24 Optional/VLM Boundary

**Role:** Audit dormant VLM code for boundary safety and truthful status.
**Auditor scope:** `tapetum_llm/vision.py`, `tapetum_llm/vision_task.py`, `tapetum_llm/vlm_diff.py`, `tapetum_llm/vlm_pipeline.py`, `tests/test_vlm_lane.py`, `tapetum_llm/__init__.py`, `CLAUDE.md`
**Maps to:** D7 (dormant-code boundary), D1 (determinism)

## 1. Audited State

- whisker 0.5.0, HEAD 51cb704 + local mods
- VLM modules: 5 files, ~788 LOC
  - `vision.py`: 127 lines (PDF rasterization)
  - `vision_task.py`: 212 lines (multimodal LLM dispatch)
  - `vlm_diff.py`: 222 lines (deterministic diff scoring)
  - `vlm_pipeline.py`: 101 lines (pipeline entry point)
  - `transcribe.py`: referenced by vlm_pipeline.py (page transcription)
- Test file: `test_vlm_lane.py`: 328 lines
- All 1406 tests passing (E1)

## 2. Commands and Exits

```
E1:  uv run --package whisker pytest packages/whisker/tests  -> 1406 passed (exit 0)
```

## 3. Current Evidence

### 3.1 No Production Command

**Claim:** VLM modules have no production command.

**Evidence:**
1. `__main__.py` command dispatch (L1317-1333): The command router handles `bench`, `guard`, `golden`, `facts`, `calibrate`, `corpus`, `score-file`, `check-facts`, and bare scoring. **No `vlm` command exists.**

2. `tapetum_llm/cli.py`: The tapetum CLI (`whisker-tapetum-llm`) handles `--review-all`, `--inspect`, `--fuse-only`, and per-paper adjudication. **No VLM entry point.**

3. The `vlm_pipeline.py` function `vlm_adjudicate_paper` is a library function that is never called from any CLI command. It requires a `VisionAgent` parameter that no service configuration provides.

4. `SERVICES.toml` (repo root): No vision endpoint is configured. The VLM lane requires a vision-capable vLLM endpoint that does not exist in the service registry.

### 3.2 Truthful Dormant Status in CLAUDE.md

**Evidence from CLAUDE.md (whisker-level):**

1. Module docstrings declare dormant status:
   - `vision.py` L17: "Dormant status: this rasterizer is used only by the unwired VLM prototype. It is retained as tested prior art and is not production coverage."
   - `vision_task.py` L25-26: "The VLM lane is dormant (no vision endpoint deployed)."
   - `vlm_diff.py` L22-23: "Dormant status: this prototype is reachable only from the unwired VLM entry point."
   - `vlm_pipeline.py` L14-15: "Dormant status: no production CLI or service configuration invokes this prototype."

2. CLAUDE.md "Known gaps" item 4: "VLM lane is unwired. 788 LOC across 5 files (`tapetum_llm/vlm_*.py`, `vision_task.py`) never reached integration. Decision pending: delete vs. quarantine behind a feature flag."

**Assessment:** Dormant status is truthfully and consistently documented across all module docstrings and the CLAUDE.md.

### 3.3 Import Isolation: Core Never Imports tapetum_llm

**Claim:** whisker core never imports `tapetum_llm`.

**Evidence from grep:**

Core whisker modules (`score.py`, `facts.py`, `metrics.py`, `match.py`, `tables.py`, `gates.py`, `golden.py`, `bench.py`, `guard.py`, `anchors.py`, `reference.py`, `report.py`, `constants.py`, `corpus_tools.py`, `golden_ideals.py`, `calibrate.py`): **ZERO imports from `whisker.tapetum_llm`.**

The ONLY core-adjacent file that imports `tapetum_llm` is `menu.py` (L182, L195), and those are **lazy imports inside functions** (not at module level):
```python
def _run_tapetum(...):
    from whisker.tapetum_llm.cli import main as tapetum_main  # lazy
```

The `__main__.py` file does NOT import from `tapetum_llm`. The tapetum CLI is a separate entry point (`whisker-tapetum-llm`), not reached from the `whisker` command.

`tapetum_llm/__init__.py` declares the invariant (L25): "Isolation invariant: whisker core never imports `tapetum_llm`. This lane imports whisker core read-only (one-way dependency)."

### 3.4 One-Way Dependency Direction

`tapetum_llm` modules import FROM core:
- `chunking.py` imports `whisker.score` (verdict constants)
- `vlm_diff.py` imports `whisker.metrics` (text_nid, content_recall, mhs, etc.)
- `vlm_pipeline.py` imports `paperstore.backend`

Core modules NEVER import from `tapetum_llm`. The dependency is strictly one-way.

### 3.5 Package Boundary Safety (Pipeline Stays Text-Only)

**Guard test** in `test_vlm_lane.py` L215-224 (`test_pipeline_stays_text_only`):

```python
def test_pipeline_stays_text_only(self):
    """Pipeline signatures carry no vision parameters."""
    import inspect
    from pipeline.agents import AgentBackend
    from pipeline.model_backends import BACKEND_REGISTRY, ModelBackend
    from pipeline.tasks import run_task
    assert "user_media" not in inspect.signature(ModelBackend.run).parameters
    assert "user_media" not in inspect.signature(AgentBackend.run).parameters
    assert "user_media" not in inspect.signature(run_task).parameters
    assert "vllm_vision" not in BACKEND_REGISTRY
```

This test asserts that the `pipeline` package has no vision parameters or vision backend type. It is a guard test that would fail if someone added vision support to the pipeline package (violating the package boundary).

### 3.6 VLM Module Architecture

The VLM lane follows the same patterns as the text lane:

1. **vision.py**: Rasterizes PDF pages to PNG bytes via PyMuPDF. Page cap (`MAX_PAGES=50`) enforced. No partial results (fidelity rule).

2. **vision_task.py**: Documented D1 exception (L16-17): uses OpenAI-compatible API directly instead of `pipeline.run_task`, because the pipeline framework cannot carry image parts. Preserves framework discipline: serial dispatch (D11 via semaphore), pinned sampling (temperature 0, top_p 1, seed 0), schema-in-prompt structured output (D6), finite retry budget (D10: `MAX_VISION_ATTEMPTS=2`).

3. **vlm_diff.py**: Deterministic diff using existing whisker metrics (`text_nid`, `content_recall`, `mhs`). No LLM, no randomness. Produces a tapetum-compatible sidecar for fusion.

4. **vlm_pipeline.py**: Ties the three modules together: rasterize -> transcribe -> diff. Library-pure: returns data, never persists.

### 3.7 Test Coverage for Dormant Code

`test_vlm_lane.py` has 37 tests across 8 test classes:

| Class | Tests | What it covers |
|-------|-------|---------------|
| `TestVisionConstants` | 2 | MAX_PAGES, TARGET_PIXELS bounds |
| `TestRasterError` | 2 | Error paths (nonexistent, non-PDF) |
| `TestPageTranscription` | 4 | Schema validation |
| `TestTranscriptionResult` | 3 | Text concatenation, empty, status |
| `TestTranscriptionPrompt` | 1 | Prompt content checks |
| `TestVlmDiff` | 8 | Verdict mapping, sidecar format, axis sorting |
| `TestVisionTask` | 6 | Pipeline guard, agent construction, semaphore, retry budget |
| `TestDiffVerdictMapping` | 2 | Threshold ordering, empty-vs-empty |
| `TestFidelityErrorPaths` | 1 | Page cap exceeded |
| `TestSourceKindRouting` | 5 | PDF/HTML/unknown detection |

## 4. Findings

### F1: VLM code is completely isolated from production paths (INFO)

**Severity:** INFO | **Confidence:** HIGH

No CLI command invokes VLM code. No service configuration provides a vision endpoint. The `vlm_adjudicate_paper` function is unreachable from any user-facing entry point. The code is dead in the strictest sense: it compiles, it is tested, but it cannot execute in production.

### F2: Import isolation is correctly enforced (INFO)

**Severity:** INFO | **Confidence:** HIGH

Core whisker modules have zero imports from `tapetum_llm`. The only core-adjacent reference is a lazy import in `menu.py` (inside a function body, not at module level). The one-way dependency is strictly maintained.

### F3: Pipeline guard test is load-bearing (INFO)

**Severity:** INFO | **Confidence:** HIGH

`test_pipeline_stays_text_only` explicitly asserts that `pipeline` signatures have no `user_media` parameter and no `vllm_vision` backend. This test would catch any attempt to add vision support to the pipeline package, which would violate the package boundary rule.

### F4: Dormant status is truthfully documented everywhere (INFO)

**Severity:** INFO | **Confidence:** HIGH

All 4 VLM module docstrings and the CLAUDE.md "Known gaps" section consistently declare the VLM lane as dormant/unwired. No documentation claims it is functional or production-ready.

### F5: D1 exception is documented and disciplined (INFO)

**Severity:** INFO | **Confidence:** HIGH

`vision_task.py` uses the OpenAI API directly (not `pipeline.run_task`) due to the pipeline's text-only constraint. The D1 exception is documented in the module docstring with explicit reasoning. The module preserves all other framework invariants (serial dispatch, pinned sampling, structured output, retry budget).

## 5. False-Pass Hypothesis

**Q:** Could dormant VLM code accidentally affect production behavior?

1. **Import side effects:** Core modules do not import `tapetum_llm` at module level. Even if `tapetum_llm` had import-time side effects, they would never execute from the `whisker` command.

2. **Menu lazy import:** `menu.py` imports `tapetum_llm.cli` inside a function. This only executes when a user explicitly selects the tapetum option from the interactive menu. It does not affect any CLI command.

3. **Shared dependencies:** VLM modules use `whisker.metrics` (read-only). They cannot affect metric behavior because the dependency is one-way and read-only.

**Conclusion:** The isolation is robust. Dormant code cannot affect production behavior.

## 6. Gate/Dimension Mapping

| Gate | Dimension | Status |
|------|-----------|--------|
| D7 Dormant-code boundary | VLM code is unreachable from production, import-isolated, guard-tested | PASS |
| D1 Determinism | `vlm_diff.py` is pure deterministic; `vision_task.py` D1 exception is documented | PASS |

## 7. Limitations

- This report audits boundary safety, not the VLM code's functional correctness (it is dormant and cannot be tested end-to-end without a vision endpoint).
- `transcribe.py` was referenced but not audited in detail (it is part of the dormant pipeline).
- The decision to delete vs. quarantine the VLM code is pending and outside this audit's scope.

## 8. Conclusion

The dormant VLM code is cleanly isolated. No production command invokes it. No core module imports it. A guard test enforces the pipeline's text-only boundary. Dormant status is truthfully documented in all module docstrings and the CLAUDE.md. The D1 exception in `vision_task.py` is documented and preserves all other framework invariants. The boundary is safe.

**Gate verdict: PASS**
