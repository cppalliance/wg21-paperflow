# 18a - unstructured
**Claims tested:** C1, C2
**Exhaustive:** yes (full-repo `rg` at SHA `f6eea75`; all production model paths in `unstructured/` read; inference kernels inside the external `unstructured_inference` dependency run at the `process_file_with_model` / `process_data_with_model` / `tables_agent.*` boundaries declared in this clone)

## Method
```text
cd packages/whisker/research/repos/unstructured
git rev-parse HEAD   # f6eea758911fcf627cbe6f9df9f790e549500d7b

rg -i -n "openai|anthropic|claude|gemini|google\.genai|genai|litellm|vllm|ollama|chat\.completions|completions\.create|messages\.create|generate_content|GenerativeModel|transformers|AutoModel|\.generate\(|pipeline\(|predict|invoke|prompt|system_prompt|LLM|VLM|gpt-|llama|qwen|whisper|embed_documents|embed_query|embeddings\.create|hi_res|unstructured_inference|chipper|vlm|load_agent|get_model|process_file_with_model|process_data_with_model|document_text_detection|\.ocr\(|transcribe\(" --glob "*.py"

rg -i -n "benchmark|eval|metric|judge|verify.*output|golden|read.?back" unstructured --glob "*.py"
```

Files read in full or substantial part (production model paths):
- `unstructured/partition/pdf.py` (`_partition_pdf_or_image_local`, `_partition_image_with_ocr`)
- `unstructured/partition/pdf_image/ocr.py`
- `unstructured/partition/pdf_image/analysis/layout_dump.py`
- `unstructured/partition/model_init.py`
- `unstructured/partition/audio.py`
- `unstructured/partition/utils/speech_to_text/whisper_stt.py`
- `unstructured/partition/utils/ocr_models/tesseract_ocr.py`
- `unstructured/partition/utils/ocr_models/paddle_ocr.py`
- `unstructured/partition/utils/ocr_models/google_vision_ocr.py`
- `unstructured/embed/{openai,bedrock,huggingface,vertexai,octoai,voyageai,mixedbreadai}.py`
- `unstructured/metrics/table_structure.py`
- `unstructured/metrics/evaluate.py` (sampled: no LLM calls; deterministic CCT / OD / table metrics)
- `unstructured/partition/html/transformations.py` (VLM partitioner is external caller only)
- `unstructured/partition/api.py` (remote REST wrapper; no local model)

## Inventory

### Production — hi_res layout detection (`unstructured_inference`)

| file:line | function | input | output | role / C2 |
|---|---|---|---|---|
| `partition/pdf.py:872` | `_partition_pdf_or_image_local` → `_run_layout_inference(process_file_with_model, …)` | PDF/image path, `hi_res_model_name`, DPI | `DocumentLayout` (per-page layout boxes) | **Extraction**: YOLOX/Detectron/chipper layout model via dependency |
| `partition/pdf.py:931` | `_partition_pdf_or_image_local` → `_run_layout_inference(process_data_with_model, …)` | PDF/image bytes, model name | `DocumentLayout` | **Extraction** (in-memory path) |
| `partition/model_init.py:14` | `initialize` → `get_model(model_name=…)` | model name string | cached weights | **Other**: preload/warmup (optional multi-model env) |
| `partition/model_init.py:16` | `initialize` → `get_model(UNSTRUCTURED_HI_RES_MODEL_NAME)` | env model name | cached weights | **Other**: default preload |
| `partition/pdf_image/analysis/layout_dump.py:54` | `object_detection_classes` → `get_model(model_name)` | `hi_res_model_name` | model instance (class label map only) | **Other**: analysis/debug metadata when `analysis=True` |

Internal `predict()` for layout lives inside `unstructured_inference.inference.layout.process_*_with_model` (external package); observable call sites in this repo are the two `_run_layout_inference` lines above.

### Production — OCR (per-page or per-block; strategy `hi_res` / `ocr_only`)

| file:line | function | input | output | role / C2 |
|---|---|---|---|---|
| `partition/pdf_image/ocr.py:234` | `supplement_page_layout_with_ocr` → `_ocr_agent.get_layout_from_image` | full page PIL image | `TextRegions` | **Extraction** (full-page OCR merge) |
| `partition/pdf_image/ocr.py:258` | `supplement_page_layout_with_ocr` → `_ocr_agent.get_text_from_image` | cropped block image | text string | **Extraction** (individual-block OCR) |
| `partition/pdf.py:1204` | `_partition_image_with_ocr` → `ocr_agent.get_layout_elements_from_image` | PIL image | vectorized OCR layout | **Extraction** (`ocr_only` strategy) |

#### Tesseract backend (`OCRAgentTesseract`)

| file:line | function | input | output | role / C2 |
|---|---|---|---|---|
| `partition/utils/ocr_models/tesseract_ocr.py:48` | `get_text_from_image` → `unstructured_pytesseract.image_to_string` | numpy image array | plain text | **Extraction** |
| `partition/utils/ocr_models/tesseract_ocr.py:101` | `image_to_data_with_character_confidence_filter` → `image_to_pdf_or_hocr` | numpy image array | hOCR → DataFrame bboxes | **Extraction** (layout OCR) |

(`get_layout_from_image` at `tesseract_ocr.py:55` delegates to line 101.)

#### PaddleOCR backend (`OCRAgentPaddle`)

| file:line | function | input | output | role / C2 |
|---|---|---|---|---|
| `partition/utils/ocr_models/paddle_ocr.py:45` or `:54` | `load_agent` → `PaddleOCR(...)` | language code | PaddleOCR instance | **Other**: model load |
| `partition/utils/ocr_models/paddle_ocr.py:79` | `get_layout_from_image` → `self.agent.ocr` | numpy image | OCR boxes/text | **Extraction** |

#### Google Cloud Vision backend (`OCRAgentGoogleVision`)

| file:line | function | input | output | role / C2 |
|---|---|---|---|---|
| `partition/utils/ocr_models/google_vision_ocr.py:40` | `get_text_from_image` → `client.document_text_detection` | PNG bytes | full-page text | **Extraction** (cloud OCR) |
| `partition/utils/ocr_models/google_vision_ocr.py:52` | `get_layout_from_image` → `client.document_text_detection` | PNG bytes | paragraph bboxes + text | **Extraction** (cloud OCR layout) |

### Production — table structure (Table Transformer / TATR via `unstructured_inference`)

| file:line | function | input | output | role / C2 |
|---|---|---|---|---|
| `partition/pdf_image/ocr.py:276` | `supplement_page_layout_with_ocr` → `tables.load_agent()` | (global) | `tables_agent` model | **Other**: load TATR weights |
| `partition/pdf_image/ocr.py:327` | `supplement_element_with_table_extraction` → `tables_agent.predict` | table crop PIL + OCR tokens | cell grid / HTML | **Extraction** (per detected table region) |
| `partition/pdf_image/ocr.py:350` | `get_table_tokens` → `ocr_agent.get_layout_from_image` | table crop image | OCR token list for TATR | **Extraction** (feeds table model) |

### Production — speech-to-text (Whisper)

| file:line | function | input | output | role / C2 |
|---|---|---|---|---|
| `partition/utils/speech_to_text/whisper_stt.py:47` | `SpeechToTextAgentWhisper.__init__` → `whisper.load_model` | model size, device | Whisper model | **Other**: model load |
| `partition/utils/speech_to_text/whisper_stt.py:67` | `transcribe_segments` → `self._model.transcribe` | audio file path | segment dicts (text + timestamps) | **Extraction** |
| `partition/audio.py:87` | `partition_audio` → `agent.transcribe_segments` | audio path | list of segments → `NarrativeText` elements | **Extraction** (orchestration entry; delegates to Whisper site above) |

### Production — embedding encoders (post-partition RAG vectors; not conversion)

| file:line | function | input | output | role / C2 |
|---|---|---|---|---|
| `embed/openai.py:53` | `embed_query` → `client.embed_query` | query string | float vector | **Other** (downstream embedding, not doc conversion) |
| `embed/openai.py:57` | `embed_documents` → `client.embed_documents` | element text list | vectors on elements | **Other** |
| `embed/bedrock.py:62` | `embed_query` → `bedrock_client.embed_query` | query string | vector | **Other** |
| `embed/bedrock.py:66` | `embed_documents` → `bedrock_client.embed_documents` | element texts | vectors | **Other** |
| `embed/huggingface.py:52` | `embed_query` → `client.embed_query` | query string | vector | **Other** |
| `embed/huggingface.py:56` | `embed_documents` → `client.embed_documents` | element texts | vectors | **Other** |
| `embed/vertexai.py:63` | `embed_query` → `client.embed_query` | query string | vector | **Other** |
| `embed/vertexai.py:68` | `embed_documents` → `client.embed_documents` | element texts | vectors | **Other** |
| `embed/octoai.py:55` | `embed_query` → `client.embeddings.create` | query string, model name | embedding vector | **Other** |
| `embed/octoai.py:59` | `embed_documents` → loop `embed_query` | each element text | vectors | **Other** |
| `embed/voyageai.py:145` | `_embed_batch` → `client.contextualized_embed` | text batch (context models) | embedding list | **Other** |
| `embed/voyageai.py:153` | `_embed_batch` → `client.embed` | text batch | embedding list | **Other** |
| `embed/voyageai.py:194` | `embed_documents` → `_embed_batch` | element texts (batched) | vectors on elements | **Other** |
| `embed/voyageai.py:210` | `embed_query` → `_embed_batch` | query string | vector | **Other** |
| `embed/mixedbreadai.py:123` | `_embed` → `client.embeddings` | text batch | embedding list | **Other** |
| `embed/mixedbreadai.py:165` | `embed_documents` → `_embed` | element texts | vectors | **Other** |
| `embed/mixedbreadai.py:178` | `embed_query` → `_embed` | query string | vector | **Other** |

Each encoder's `get_exemplary_embedding()` (e.g. `openai.py:38`, `bedrock.py:47`, `huggingface.py:40`, `vertexai.py:48`, `octoai.py:40`, `voyageai.py:69`, `mixedbreadai.py:74→_embed`) calls the same APIs with fixed probe strings during encoder validation; same C2 class **Other**.

### Production — metrics / eval harness (offline scoring)

| file:line | function | input | output | role / C2 |
|---|---|---|---|---|
| `metrics/table_structure.py:18` | `image_or_pdf_to_dataframe` → `load_agent()` | (global) | TATR agent | **Eval-harness** setup |
| `metrics/table_structure.py:27` | `image_or_pdf_to_dataframe` → `tables_agent.run_prediction` | table-only image/PDF + OCR tokens | predicted DataFrame | **Eval-harness** (isolated table metric) |
| `metrics/table_structure.py:42-48` | `eval_table_transformer_for_file` → `compare_contents_as_df` | pred vs CSV ground truth | float score 0–1 | **Eval-harness** (deterministic compare; no LLM) |
| `metrics/evaluate.py:125-150` | `BaseMetricsCalculator.calculate` | partition output dir vs ground-truth dir | TSV metrics | **Eval-harness** (CCT accuracy, OD mAP, table structure; all deterministic — no model API in this module) |
| `metrics/object_detection.py:48+` | `ObjectDetectionEvalProcessor` | saved bbox preds vs targets | precision/recall/mAP | **Eval-harness** (torch tensor math; no LLM) |

### Non-production hits (listed; charter requires marking)

| file:line | function | role / C2 |
|---|---|---|
| `partition/api.py:24+` | `partition_via_api` | **Other**: HTTP client to hosted unstructured-api; model runs server-side, not in this clone |
| `scripts/performance/benchmark_partition.py` | `partition(..., strategy="hi_res")` | **Experiment** (timing only) |
| `scripts/elasticsearch-test-helpers/.../test-ingest-elasticsearch-output.py:20` | `embedding_encoder.embed_query` | **Test helper** |
| `test_unstructured/embed/test_*.py` | mocked `embed_documents` | **Test** |
| `test_unstructured/partition/pdf_image/test_ocr.py:446` | `tables.load_agent()` | **Test** |
| `chunking/base.py:69,144` | tiktoken model name `"gpt-4"` | **Not a model call** (tokenizer only) |
| `partition/html/transformations.py:70,117,159` | `detection_origin="vlm_partitioner"` | **Not a model call** in-repo; external VLM partitioner feeds HTML into `partition_html` |
| `partition/pdf_image/form_extraction.py:15` | `run_form_extraction` | **Stub** (`NotImplementedError`; no model) |

No matches for `anthropic`, `claude`, `chat.completions`, `messages.create`, `GenerativeModel`, `litellm`, `vllm`, `ollama`, or LLM-as-judge strings in production Python.

## Verdict on the claim(s)

**C1 (negative existential — no per-page/chunk LLM/VLM verification of already-produced conversion output): CONFIRMED for this repo at `f6eea75`.**

Every model invocation is forward **extraction** (layout detection, OCR, table structure, STT, embeddings) or offline **eval-harness** scoring (deterministic CCT/OD/table metrics; TATR rerun in `metrics/table_structure.py` for isolated table eval). No production or in-repo eval path sends an existing element stream or markdown artifact to an LLM/VLM for judgment against the source PDF/page. Post-OCR merge logic (`merge_out_layout_with_ocr_layout`, `merge_inferred_with_extracted_layout`) is deterministic geometry/text reconciliation, not model verification. The referenced "VLM partitioner" (`partition/html/transformations.py:70`) consumes HTML produced elsewhere; this clone contains no VLM inference code.

**C2 (classification):** All production model sites above classify as **extraction** (partition pipeline), **eval-harness** (`metrics/table_structure.py`, `metrics/evaluate.py`), or **other** (embeddings, model preload, analysis dump, remote API wrapper). None are **refinement** (no model fixes its own prior output blocks) or verification.

## Coverage gaps

None material for in-repo Python. Layout/TATR/chipper forward passes inside `unstructured_inference` (separate install) are not line-enumerated here; boundaries are `process_file_with_model` / `process_data_with_model` / `tables_agent.predict` / `tables_agent.run_prediction`. Non-`.py` assets (Docker, workflows, example-docs) were not read line-by-line; charter search floor found no additional production model calls there. Individual unit-test files were not read in full; test hits captured when matched by `rg`.

## What could still hide a counterexample

- A dynamically selected OCR/STT/embed backend registered at runtime but not referenced in source (charter patterns include `pipeline(` — none in production partition code).
- Hosted `partition_via_api` / unstructured-api server behavior at a newer SHA (out of scope for this clone; local code is HTTP-only).
- Closed-source weights or inference paths inside `unstructured_inference`, PaddleOCR, Whisper, or cloud Vision/Bedrock/OpenAI SDK versions not visible here.
- Future `run_form_extraction` implementation (`form_extraction.py:15` currently raises `NotImplementedError`).
