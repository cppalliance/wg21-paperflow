# 14a - MinerU LLM/VLM call sites

**Claims tested:** C1, C2
**Exhaustive:** no (see Coverage gaps)

## Method

Repo: `packages/whisker/research/repos/MinerU` at SHA `3e60291846cb7c3bf8fe7f4f16238f4fc6cce491` (matches `research/all-pages-llm-coverage/00-baseline.md`).

Files read in full:

- `mineru/utils/llm_aided.py`
- `mineru/utils/title_level_postprocess.py`
- `mineru/utils/config_reader.py` (llm-aided section)
- `mineru/backend/vlm/vlm_analyze.py`
- `mineru/backend/hybrid/hybrid_analyze.py` (VLM/MFR sections)
- `mineru/backend/pipeline/batch_analyze.py` (MFR section)
- `mineru/backend/vlm/model_output_to_middle_json.py` (finalize/title hook)
- `mineru/backend/pipeline/model_json_to_middle_json.py` (finalize/title hook)
- `mineru/backend/hybrid/hybrid_model_output_to_middle_json.py` (finalize/title hook)
- `mineru/model/mfr/unimernet/Unimernet.py`
- `mineru/model/mfr/pp_formulanet_plus_m/predict_formula.py`
- `mineru.template.json` (llm-aided-config keys)

Search commands (shell `rg`, repo root = MinerU clone):

```text
rg -i "openai|anthropic|claude|gemini|google\.genai|genai|litellm|vllm|ollama|chat\.completions|completions\.create|messages\.create|generate_content|GenerativeModel|transformers|AutoModel|\.generate\(|pipeline\(|predict|invoke|system_prompt|LLM|VLM|gpt-|llama|qwen|llm_aided" --glob "*.py"
rg -n "MinerUClient|batch_two_step|batch_extract_with_layout|chat\.completions|OpenAI\(|llm_aided|Qwen2VL|run_mfr_inference|\.generate\(" mineru --glob "*.py"
rg -n "formula_aided|title_aided|llm-aided" .
rg -n "benchmark|eval|judge|OmniDoc" --glob "*.py" -i
git rev-parse HEAD
```

Scope note: counted as LLM/VLM only generative language/vision-language inference (OpenAI chat API, `MinerUClient` VLM extractors, formula MFR encoder-decoders). Excluded from this inventory: layout detection (`pp_doclayoutv2`), OCR det/rec, table cls/rec CNNs, and other non-generative `predict()`/`batch_predict()` paths (listed under "Excluded non-LLM model hits").

## Inventory

### llm_aided (refinement; no source document)

Only `title_aided` exists in config (`mineru.template.json:16-17`; no `formula_aided` or other llm-aided keys in repo).

| # | file:line | function | input | output | role | source vs output? |
|---|---|---|---|---|---|---|
| 1 | `mineru/utils/llm_aided.py:191` | `_request_title_levels` | OpenAI-compatible chat prompt: dict `{title_id: [title_text, line_avg_height, page_num]}` built from `middle_json` title blocks (`llm_aided.py:58-68`, `71-111`, `114-157`) | Parsed dict `{title_id: heading_level_int}` (`llm_aided.py:203-207`) | refinement | **Reshape without source.** Prompt contains extracted title strings and geometry/page metadata only. No PDF page images, no full candidate markdown, no side-by-side comparison of existing conversion output against source. |
| 2 | `mineru/utils/title_level_postprocess.py:38` | `apply_title_leveling_to_pdf_info` | `pdf_info` list (post-extraction middle JSON) | Mutates title blocks in-place with `level` fields via `llm_aided_title` | refinement (orchestrator) | Same as #1. Gated by `title_aided.enable` in local config (`title_level_postprocess.py:17-29`). Called from finalize on all three PDF backends: `vlm/model_output_to_middle_json.py:115`, `pipeline/model_json_to_middle_json.py:221`, `hybrid/hybrid_model_output_to_middle_json.py:270`. |

### VLM backend (`MinerUClient`; extraction from source page images)

Implementation of `batch_two_step_extract`, `aio_batch_two_step_extract`, `batch_extract_with_layout`, `aio_batch_extract_with_layout` lives in external package `mineru_vl_utils` (`vlm_analyze.py:39`; changelog `docs/en/reference/changelog.md:130`). MinerU repo call sites:

| # | file:line | function | input | output | role | source vs output? |
|---|---|---|---|---|---|---|
| 3 | `mineru/backend/vlm/vlm_analyze.py:479` | `doc_analyze` | Window of PDF page PIL images (`images_pil_list`), `image_analysis` flag | `window_results` page block lists appended to `middle_json` | extraction | **Produces output from source.** Page images loaded from PDF (`vlm_analyze.py:464-470`). Not verification. |
| 4 | `mineru/backend/vlm/vlm_analyze.py:578` | `aio_doc_analyze` | Same as #3 (async image load) | Same as #3 | extraction | Same as #3. |
| 5 | `mineru/backend/hybrid/hybrid_analyze.py:981` | `hybrid_doc_analyze` (effort=`medium`) | Page PIL images + per-page layout block lists (`vlm_blocks_list`) | `window_model_list` VLM structured blocks | extraction | **Produces output from source.** Layout blocks derived from CV layout pass on same page images (`hybrid_analyze.py:656-657`, `972-978`). |
| 6 | `mineru/backend/hybrid/hybrid_analyze.py:1008` | `hybrid_doc_analyze` (effort=`high`, OCR on) | Page PIL images | `window_model_list` | extraction | Same as #3. |
| 7 | `mineru/backend/hybrid/hybrid_analyze.py:1021` | `hybrid_doc_analyze` (effort=`high`, OCR off) | Page PIL images + `not_extract_list` block-type filter | `window_model_list` | extraction | Same as #3; some block types skipped for generative extract (`hybrid_analyze.py:1023-1024`). |
| 8 | `mineru/backend/hybrid/hybrid_analyze.py:1190` | `aio_hybrid_doc_analyze` (effort=`medium`) | Same as #5 | Same as #5 | extraction | Async counterpart of #5. |
| 9 | `mineru/backend/hybrid/hybrid_analyze.py:1219` | `aio_hybrid_doc_analyze` (effort=`high`, OCR on) | Same as #6 | Same as #6 | extraction | Async counterpart of #6. |
| 10 | `mineru/backend/hybrid/hybrid_analyze.py:1233` | `aio_hybrid_doc_analyze` (effort=`high`, OCR off) | Same as #7 | Same as #7 | extraction | Async counterpart of #7. |

VLM model init (not per-page inference loop, but generative backend setup): `Qwen2VLForConditionalGeneration.from_pretrained` at `vlm_analyze.py:97-105` (transformers backend); `MinerUClient(...)` constructed at `vlm_analyze.py:222-238`.

### Pipeline / hybrid formula MFR (specialized vision-to-LaTeX; extraction)

| # | file:line | function | input | output | role | source vs output? |
|---|---|---|---|---|---|---|
| 11 | `mineru/backend/pipeline/batch_analyze.py:446` | `BatchAnalyze._analyze_images` via `run_mfr_inference` | Formula crop images from PDF pages + layout formula boxes (`batch_analyze.py:434-449`) | LaTeX strings written into layout formula dicts (`batch_analyze.py:454-457`) | extraction | **Produces output from source.** Formula crops from page images, not from prior markdown. |
| 12 | `mineru/backend/hybrid/hybrid_analyze.py:706` | `_process_ocr_and_formulas` via `run_mfr_inference` | Same pattern for hybrid supplement path | Inline formula LaTeX in hybrid blocks | extraction | Same as #11. |
| 13 | `mineru/model/mfr/unimernet/Unimernet.py:181` | `UnimernetModel.batch_predict` | Batched formula crop tensors | LaTeX strings via `self.model.generate(...)` (`Unimernet.py:181-186`; underlying `modeling_unimernet.py:189`) | extraction | Leaf inference for `unimernet_small` MFR backend. |
| 14 | `mineru/model/mfr/pp_formulanet_plus_m/predict_formula.py:197` | `FormulaRecognizer.batch_predict` | Batched formula crop tensors | LaTeX via `self.net(batch_data)` autoregressive head (`predict_formula.py:197-200`; head `generate` at `rec_ppformulanet_head.py:1378`) | extraction | Leaf inference for `pp_formulanet_plus_m` MFR backend. |

### Eval-harness / verification

No production or test code path invokes an LLM/VLM to score or judge an already-produced conversion against the source document. `rg` over `tests/` for `chat.completions`, `OpenAI(`, `batch_two_step`, `llm_aided` returned zero matches. Benchmark/eval references in repo are deterministic model-confidence scores (OCR/layout cls scores), not LLM-as-judge harnesses.

### Excluded non-LLM model hits (searched, not LLM/VLM)

Representative `predict`/`batch_predict` paths excluded from LLM/VLM inventory: layout `pp_doclayoutv2.py:1476`, pipeline OCR `batch_analyze.py:759+`, table cls/rec `batch_analyze.py:528-684`, hybrid layout `hybrid_analyze.py:657`, table orientation cls `hybrid_analyze.py:429`. These are CV/OCR/table models, not generative LLM/VLM per C2 classification.

### Docs / demo / test mentions (not production call sites)

- `demo/demo.py:222-223` — comments describing VLM/hybrid-http-client backends.
- `mineru/cli/gradio_app.py`, `mineru/cli/client.py`, `mineru/cli/api_request.py` — UI/help text for OpenAI-compatible servers; no inference calls.
- `mineru/model/mfr/unimernet/unimernet_hf/unimer_mbart/modeling_unimer_mbart.py:959` — docstring example only.

## llm_aided verdict (explicit)

**Reshape output without the source.** `llm_aided_title` sends a prompt containing already-extracted title text, average line height, and 1-based page numbers (`llm_aided.py:71-111`). It asks the LLM to assign heading levels and return `{id: level}`. It does not receive PDF images, rendered pages, or a candidate markdown document to compare against the PDF. On failure it returns `None` and leaves levels unchanged (`llm_aided.py:217-218`); conversion is not aborted.

## Verdict on the claim(s)

**C1: CONFIRMED for MinerU at SHA 3e60291.** No production code path in this repo invokes an LLM/VLM to judge an already-produced conversion output against the source document per page/chunk/unit. All LLM/VLM paths are either extraction (VLM/MFR from source images) or post-hoc refinement (`llm_aided` title leveling from extracted title text). No eval-harness LLM-judge loop found.

**C2:** All 14 production LLM/VLM invocation sites above classified. Breakdown: extraction 12, refinement 2 (one API site + one orchestrator), eval-harness 0, other 0.

## Coverage gaps

- **`mineru_vl_utils` not in corpus.** VLM inference bodies (`batch_two_step_extract`, `batch_extract_with_layout`, HTTP-client OpenAI-compatible calls) live in pip dependency `mineru_vl_utils` (see `pyproject.toml`, `vlm_analyze.py:39`). Only MinerU-side call sites (#3-#10) verified here; internal prompt/completion logic NOT VERIFIED line-by-line.
- **`tests/` and `demo/`** searched via `rg`; no LLM/VLM invocation sites found. Not every test file read in full (unnecessary given zero pattern hits).
- **Office backend** (`mineru/backend/office/`) not exhaustively re-read; `rg` found no `llm_aided`, `chat.completions`, `MinerUClient`, or `batch_two_step` references outside PDF backends above.

## What could still hide a counterexample

- Unpinned runtime code inside installed `mineru_vl_utils` (not at corpus SHA) could add verification logic not visible in this clone.
- A dynamically loaded plugin or user-supplied `server_url` HTTP backend could run arbitrary prompts; MinerU repo only passes page images/blocks into `MinerUClient` methods listed above, with no candidate-markdown verification parameters in those call signatures.
- Future `llm-aided-config` keys beyond `title_aided` (none present at pinned SHA).
