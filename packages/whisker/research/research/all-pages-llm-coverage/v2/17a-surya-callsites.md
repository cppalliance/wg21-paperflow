# 17a - surya (pinned SHA 11d1884)
**Claims tested:** C1, C2
**Exhaustive:** yes

## Method
Repo: `packages/whisker/research/repos/surya` @ `11d18847e8b8c17fd55e254e3e5c44b3fed5c87e` (matches baseline pin `11d1884`).

Search commands run (from repo root):
```
rg -i -n "openai|anthropic|claude|gemini|google\.genai|genai|litellm|vllm|ollama|chat\.completions|completions\.create|messages\.create|generate_content|GenerativeModel|transformers|AutoModel|\.generate\(|pipeline\(|\.predict\(|\.invoke\(|LLM|VLM|gpt-|llama|qwen|system_prompt" --glob "*.py"
rg -n "\.generate\(|chat\.completions\.create|self\.model\(|manager\.generate|chat_completions_batch|_generate_one" --glob "*.py"
rg -n "judge|verify|eval|benchmark|compare.*output|golden|score.*output" --glob "*.py" -i
rg -n "chat\.completions\.create|self\.model\(" --glob "*"
```

Files read in full for call-chain tracing:
`surya/inference/__init__.py`, `surya/inference/backends/base.py`, `surya/inference/backends/openai_client.py`, `surya/inference/backends/vllm.py`, `surya/inference/backends/llamacpp.py`, `surya/layout/__init__.py`, `surya/recognition/__init__.py`, `surya/table_rec/__init__.py`, `surya/detection/__init__.py`, `surya/ocr_error/__init__.py`, `surya/common/predictor.py`.

All 68 `.py` files under the clone were covered by the `rg` passes above. Non-Python assets (static images, HTML templates, `katex.js`) contain no model invocation code.

## Inventory

### Leaf model invocations (HTTP / torch forward)

| file:line | function | input | output | role | C2 class |
|---|---|---|---|---|---|
| `surya/inference/backends/openai_client.py:113` | `_generate_one` | `BatchInputItem` (PIL image + prompt string / prompt_type + optional guided_json/regex) via OpenAI chat messages | `GenerationResult` (raw text, token_count, logprobs, error flag) | **VLM inference**: sole HTTP call `client.chat.completions.create(**kwargs)` to vllm or llama.cpp server | extraction |
| `surya/detection/__init__.py:111` | `DetectionPredictor.batch_detection` | `pixel_values` tensor batch (preprocessed page image splits) | `pred.logits` semantic-segmentation heatmaps (EfficientViT) | **Text-line detection** (CV foundation model, not generative LLM) | extraction |
| `surya/ocr_error/__init__.py:46` | `OCRErrorPredictor.batch_ocr_error_detection` | `batch_input_ids`, `batch_attention_mask` (tokenized OCR text strings) | `pred.logits` → argmax class label per string (DistilBert) | **OCR-error classifier** on text (no image, no comparison to pre-existing conversion) | other |

### VLM dispatch chain (all funnel to `openai_client.py:113`)

| file:line | function | input | output | role | C2 class |
|---|---|---|---|---|---|
| `surya/inference/backends/openai_client.py:175` | `chat_completions_batch._process` | `BatchInputItem` | `BatchOutputItem` via `_generate_one` | Initial VLM request per batch item (ThreadPoolExecutor worker) | extraction |
| `surya/inference/backends/openai_client.py:192` | `chat_completions_batch._process` (retry loop) | same item, raised temperature on repeat/error | `BatchOutputItem` via `_generate_one` | VLM retry on error or detected token repetition | refinement (in-pipeline retry, not output verification) |
| `surya/inference/backends/vllm.py:200` | `VllmBackend.generate` | `List[BatchInputItem]` | `List[BatchOutputItem]` via `chat_completions_batch` | vllm backend entry | extraction |
| `surya/inference/backends/llamacpp.py:200` | `LlamaCppBackend.generate` | `List[BatchInputItem]` | `List[BatchOutputItem]` via `chat_completions_batch` | llama.cpp backend entry | extraction |
| `surya/inference/__init__.py:102` | `SuryaInferenceManager.generate` | `List[BatchInputItem]` | `List[BatchOutputItem]` via `self.backend.generate` | Manager wrapper over active backend | extraction |

### Predictor-level VLM call sites (production tasks)

| file:line | function | input | output | role | C2 class |
|---|---|---|---|---|---|
| `surya/layout/__init__.py:67` | `LayoutPredictor.__call__` | Full-page PIL images + `PROMPT_TYPE_LAYOUT` (+ optional JSON schema) | `List[LayoutResult]` (layout bboxes/labels parsed from VLM JSON) | **Layout analysis** | extraction |
| `surya/recognition/__init__.py:197` | `RecognitionPredictor.__call__` (block mode) | Block crops + `PROMPT_TYPE_BLOCK` per non-skipped layout box | `List[PageOCRResult]` (per-block HTML) | **Per-block OCR** | extraction |
| `surya/recognition/__init__.py:283` | `RecognitionPredictor._full_page_ocr` | Full-page images + `PROMPT_TYPE_HIGH_ACCURACY_BBOX` | `List[PageOCRResult]` (parsed div/bbox HTML); on failure falls back to layout+block at `:363-364` (same enumerated sites) | **Full-page OCR** | extraction |
| `surya/table_rec/__init__.py:84` | `TableRecPredictor.predict_simple` | Table crop images + `PROMPT_TYPE_TABLE_REC` (+ JSON schema) | `List[TableResult]` (rows/cols/cells derived geometrically) | **Table structure (simple)** | extraction |
| `surya/table_rec/__init__.py:186` | `TableRecPredictor.predict_full` | Table crop images + `PROMPT_TYPE_BLOCK` | `List[TableResult]` (full HTML in `.html`) | **Table structure (full HTML)** | extraction |

### Test / CLI hits (same code paths, not additional invocation sites)

| file:line | note |
|---|---|
| `tests/conftest.py:21-54` | Fixtures construct `SuryaInferenceManager` + predictors; tests call `__call__` on enumerated predictors |
| `tests/test_layout.py:2`, `tests/test_recognition.py:2-6`, `tests/test_detection.py:2`, `tests/test_table_rec.py:13`, `tests/test_ocr_errors.py:6,14` | Test invocations through fixtures |
| `surya/scripts/detect_layout.py:27`, `surya/scripts/ocr_text.py:28`, `surya/scripts/table_recognition.py:63,79`, `surya/scripts/detect_text.py:25`, `surya/scripts/streamlit_app.py:128-262`, `surya/scripts/screenshot_app.py:46` | CLI/UI entry points calling same predictor `__call__` methods |

### C1-relevant negative findings (no verification harness)

| file:line | finding |
|---|---|
| `surya/inference/backends/spawn.py:325` | Comment "Verify model name" — server attach probe only, not document-output verification |
| `surya/inference/backends/vllm.py:28` | Comment "benchmarks land" — no benchmark/eval code present at this SHA |
| (repo-wide) | No matches for judge/compare-output/golden/score-output eval patterns in `.py` files |

## Verdict on the claim(s)

**C1: CONFIRMED.** At SHA `11d1884`, surya contains no production or test code path where an LLM/VLM judges an already-produced conversion output against the source document per page/chunk/unit. All VLM calls (`openai_client.py:113` and upstream predictors) take source images (or block crops) and **produce** layout/OCR/table structure. The recognition fallback (`recognition/__init__.py:350-366`) re-runs extraction (layout + block OCR) when full-page output fails; it does not compare against a pre-existing external conversion. The OCR-error predictor (`ocr_error/__init__.py:46`) classifies garbled text strings; it receives no source image and no prior markdown/html output to verify.

**C2:** All 13 production invocation sites classified above: 11 extraction, 1 refinement (VLM retry at `openai_client.py:192`), 1 other (DistilBert OCR-error classifier). Zero eval-harness sites.

## Coverage gaps
None. All 68 Python files searched; key inference chain files read in full; non-Python assets checked for model calls.

## What could still hide a counterexample
- Dynamic invocation (`getattr`, `exec`, importlib) — none found in `rg` passes for `generate`, `chat.completions`, or `self.model(`.
- External repos consumed at runtime (marker integration mentioned in comments) — out of this clone's scope; no in-repo verification lane found.
