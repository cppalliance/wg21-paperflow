# 11a - docling (SHA fbd39b8)
**Claims tested:** C1, C2
**Exhaustive:** yes

## Method
Repo: `packages/whisker/research/repos/docling` at `fbd39b870859afbae21645ebe0e417109777da5a` (matches baseline pin).

Search commands (all under repo root):
```text
rg -i -n "openai|anthropic|claude|gemini|google\.genai|genai|litellm|vllm|ollama|chat\.completions|completions\.create|messages\.create|generate_content|GenerativeModel" --glob "*.py"
rg -i -n "transformers|AutoModel|\.generate\(|pipeline\(|predict\(|invoke\(|system_prompt|LLM|VLM|gpt-|llama|qwen" --glob "*.py"
rg -i -n "confidence.?score|Document Element QA|element.?qa|picture.?description|PictureDescription|VlmPipeline|vlm_pipeline" --glob "*.py"
rg -n "model\.generate\(|engine\.predict_batch\(|api_image_request\(|api_image_request_streaming\(|\.transcribe\(|mlx_whisper\.|transcribe_with_vad" docling --glob "*.py"
rg -i -n "Document Element QA|element_qa|doc.?element.?qa" .
rg -n "parse_score|layout_score|table_score|ocr_score|mean_score|confidence\.pages" docling --glob "*.py"
rg -n "predict_batch|\.generate\(|api_image_request|transcribe" tests docs/examples --glob "*.py"
```

Files read in full or in targeted sections: `docling/utils/api_image_request.py`, all `docling/models/inference_engines/vlm/*.py`, `docling/models/vlm_pipeline_models/*.py`, `docling/models/stages/vlm_convert/vlm_convert_model.py`, `docling/models/stages/picture_description/*.py`, `docling/models/stages/code_formula/*.py`, `docling/models/extraction/*.py`, `docling/models/stages/chart_extraction/granite_vision.py`, `docling/models/stages/table_structure/table_structure_model_granite_vision.py`, `docling/pipeline/asr_pipeline.py`, `docling/pipeline/extraction_vlm_pipeline.py`, `docling/experimental/pipeline/threaded_layout_vlm_pipeline.py`, `docling/models/stages/page_preprocessing/page_preprocessing_model.py`, `docling/datamodel/base_models.py`, `docling/pipeline/standard_pdf_pipeline.py`.

Scope note: inventory lists **generative LLM/VLM/ASR** sites only. Excluded as non-LLM/VLM: layout object-detection `predict_batch`, picture-classifier image-classification `predict_batch`, TableFormerV2 `model.generate` (`table_structure_model_v2.py:126`, `:415`; specialized vision seq2seq, not language/VLM).

## Inventory

### Production LLM/VLM/ASR call sites (29)

| file:line | function | input | output | role |
|---|---|---|---|---|
| `docling/utils/api_image_request.py:218` | `api_image_request` | PIL image + text prompt (+ API params) | HTTP JSON → generated text (`session.post`) | extraction (shared remote-VLM transport) |
| `docling/utils/api_image_request.py:317` | `api_image_request_streaming` | PIL image + prompt + optional `GenerationStopper`s | SSE stream → accumulated text (`session.post` stream) | extraction (shared remote-VLM transport) |
| `docling/models/inference_engines/vlm/transformers_engine.py:463` | `TransformersVlmEngine.predict_batch` | `VlmEngineInput` batch (image, prompt, gen config) | `VlmEngineOutput` text via `vlm_model.generate` | extraction |
| `docling/models/inference_engines/vlm/api_openai_compatible_engine.py:159` | `ApiVlmEngine.predict_batch` | `VlmEngineInput` | text via `api_image_request_streaming` | extraction |
| `docling/models/inference_engines/vlm/api_openai_compatible_engine.py:178` | `ApiVlmEngine.predict_batch` | `VlmEngineInput` | text via `api_image_request` | extraction |
| `docling/models/inference_engines/vlm/vllm_engine.py:322` | `VllmVlmEngine.predict_batch` | `VlmEngineInput` batch | text via `llm.generate` (vLLM) | extraction |
| `docling/models/inference_engines/vlm/mlx_engine.py:209` | `MlxVlmEngine.predict_batch` | `VlmEngineInput` | text via `stream_generate` (mlx-vlm) | extraction |
| `docling/models/inference_engines/vlm/auto_inline_engine.py:241` | `AutoInlineVlmEngine.predict_batch` | `VlmEngineInput` batch | delegates to selected backend `predict_batch` | extraction (engine selector) |
| `docling/models/vlm_pipeline_models/hf_transformers_model.py:388` | `HfTransformersVlmModel.process_images` | page/crop images + prompts | `VlmPrediction` via `vlm_model.generate` | extraction (legacy VlmPipeline path) |
| `docling/models/vlm_pipeline_models/api_vlm_model.py:150` | `ApiVlmModel.process_images` | image + prompt | `VlmPrediction` via streaming API | extraction (legacy VlmPipeline path) |
| `docling/models/vlm_pipeline_models/api_vlm_model.py:163` | `ApiVlmModel.process_images` | image + prompt | `VlmPrediction` via non-streaming API | extraction (legacy VlmPipeline path) |
| `docling/models/vlm_pipeline_models/vllm_model.py:321` | `VllmVlmModel.process_images` | images + prompts | `VlmPrediction` via `llm.generate` | extraction (legacy VlmPipeline path) |
| `docling/models/vlm_pipeline_models/mlx_model.py:244` | `MlxVlmModel.process_images` | images + prompts | `VlmPrediction` via `stream_generate` | extraction (legacy VlmPipeline path) |
| `docling/models/stages/vlm_convert/vlm_convert_model.py:191` | `VlmConvertModel.__call__` | PDF page images + preset prompt | `page.predictions.vlm_response` via `engine.predict_batch` | extraction (VlmPipeline / ThreadedLayoutVlmPipeline VLM stage) |
| `docling/models/stages/vlm_convert/vlm_convert_model.py:257` | `VlmConvertModel.process_images` | images + prompts | `VlmPrediction` via `engine.predict_batch` | extraction |
| `docling/models/stages/picture_description/picture_description_vlm_engine_model.py:142` | `PictureDescriptionVlmEngineModel._annotate_images` | picture crop images + description prompt | alt-text strings via `engine.predict_batch` | refinement (enrichment of detected pictures) |
| `docling/models/stages/picture_description/picture_description_api_model.py:57` | `PictureDescriptionApiModel._annotate_images` | picture crops + prompt | descriptions via `api_image_request` | refinement |
| `docling/models/stages/picture_description/picture_description_vlm_model.py:122` | `PictureDescriptionVlmModel._annotate_images` | picture crops + prompt | descriptions via inline `model.generate` | refinement |
| `docling/models/stages/code_formula/code_formula_vlm_model.py:272` | `CodeFormulaVlmModel.__call__` | code/formula crop images + label-specific prompts | extracted code/formula text via `engine.predict_batch` | refinement |
| `docling/models/stages/code_formula/code_formula_model.py:331` | `CodeFormulaModel.__call__` | code/formula crops + prompts | extracted text via `_model.generate` | refinement |
| `docling/models/extraction/transformers_extraction_model.py:185` | `TransformersExtractionModel.process_images` | document page images + extraction template prompt | structured/text JSON via `vlm_model.generate` | extraction |
| `docling/models/extraction/nuextract_transformers_model.py:275` | `NuExtractTransformersModel.process_images` | images + NuExtract templates | extracted text via `vlm_model.generate` | extraction (class present; no import/call sites found elsewhere in repo) |
| `docling/pipeline/extraction_vlm_pipeline.py:102` | `ExtractionVlmPipeline._extract_data` | per-page source images + template prompt | `ExtractedPageData` via `vlm_model.process_images` | extraction |
| `docling/models/stages/chart_extraction/granite_vision.py:267` | `_BaseChartExtractionModelGraniteVision.__call__` | chart picture crops + chart prompt | CSV/chart metadata via `_model.generate` | refinement |
| `docling/models/stages/chart_extraction/granite_vision.py:440` | `ChartExtractionModelGraniteVisionV4.__call__` | chart crops + prompts | chart metadata via `_model.generate` | refinement |
| `docling/models/stages/table_structure/table_structure_model_granite_vision.py:302` | `TableStructureModelGraniteVision.predict_tables` | table cluster crops + OTSL prompt | table structure tokens via `_model.generate` | refinement |
| `docling/pipeline/asr_pipeline.py:279` | `_NativeWhisperModel.transcribe` | audio file path | transcript segments via `whisper.transcribe` | extraction (ASR) |
| `docling/pipeline/asr_pipeline.py:390` | `_MlxWhisperModel.transcribe` | audio file path | transcript segments via `mlx_whisper.transcribe` | extraction (ASR) |
| `docling/pipeline/asr_pipeline.py:577` | `_WhisperS2TModel.transcribe` | audio file path | transcript segments via `model.transcribe_with_vad` | extraction (ASR) |

### Tests / examples / eval-harness (marked; not counted in production total)

| file:line | note | role |
|---|---|---|
| `tests/test_api_vlm_engine.py:61,97,119,141` | `[test]` mocks `api_image_request`; calls `ApiVlmEngine.predict_batch` | eval-harness |
| `tests/test_api_usage_propagation.py:110` | `[test]` `engine.predict_batch` with mocked API | eval-harness |
| `tests/test_api_image_request.py` | `[test]` unit tests for `api_image_request` / streaming parsers | eval-harness |
| `tests/test_asr_*.py`, `tests/test_asr_pipeline.py` | `[test]` mock or integration ASR `transcribe` paths | eval-harness |
| `tests/test_*_vlm.py` (e.g. `test_glmocr_vlm.py`, `test_falcon_ocr_vlm.py`, `test_deepseekocr_vlm.py`, …) | `[test]` E2E `DocumentConverter` + `VlmPipeline`; hits production sites above when server available | eval-harness |
| `tests/test_picture_description_*.py` | `[test]` picture-description stage behavior with mocks | eval-harness |
| `tests/test_extraction.py`, `tests/test_granite_vision_extraction.py` | `[test]` extraction pipeline / mocks | eval-harness |
| `docs/examples/vlm_pipeline_api_model.py` | `[example]` configures remote VLM; runtime calls production pipeline | other (example) |
| `docs/examples/picture_description_*.py`, `docs/examples/pictures_description_api.py` | `[example]` picture-description API/inline demos | other (example) |
| `docs/examples/gpu_vlm_pipeline.py`, `docs/examples/minimal_vlm_pipeline.py`, `docs/examples/compare_vlm_models.py` | `[example]` VlmPipeline demos | other (example) |
| `docs/examples/legacy/*` | `[example]` legacy API configuration samples | other (example) |
| `docs/examples/experimental/demo_layout_vlm.py` | `[example]` ThreadedLayoutVlmPipeline demo | other (example) |

## Confidence-scores layer

**No LLM/VLM call involved.** Scores are deterministic aggregates of parser/OCR/layout/table signals.

Per-page `parse_score`: `page_preprocessing_model.py:85-88` runs `rate_text_quality` on each text cell, then `np.nanquantile(text_scores, q=0.10)`.

Per-page `layout_score` / `ocr_score`: `layout_object_detection_model.py:126-137` uses `np.mean` of layout-cluster confidences and OCR-cell confidences from layout detection (not generative models).

Document-level roll-up: `standard_pdf_pipeline.py:1068-1086` sets `conv_res.confidence.{layout,parse,table,ocr}_score` to `np.nanmean` over per-page values.

`mean_score`: `base_models.py:581-590` computes `np.nanmean([ocr_score, table_score, layout_score, parse_score])`; `ConfidenceReport.mean_score` at `:652-659` averages page `mean_score`s unless overridden.

## Document Element QA / model-based validation

**NOT FOUND.** Repo-wide search for `Document Element QA`, `element_qa`, `doc element qa` returned zero matches (exit code 1). No model-based post-conversion QA path identified.

## Verdict on the claim(s)

**C1: CONFIRMED.** At SHA fbd39b8, docling has no production code path where an LLM/VLM judges an **already-produced conversion output** against the source document per page/chunk/unit. Every generative site takes **source** inputs (page image, crop, audio) and **produces** text/structure (extraction or enrichment). Enrichment stages (`picture_description`, `code_formula`, chart/table granite-vision) refine pipeline artifacts from source crops; they do not compare rendered markdown/HTML to the PDF for verification.

**C2:** All 29 production generative sites classified above as extraction (22), refinement (6), or engine-delegation extraction (1). Zero eval-harness sites in production code; test/example harnesses listed separately.

## Coverage gaps

None for production Python under `docling/`. Searched `tests/`, `docs/examples/`, `docling/experimental/`. `packages/`, `perfs/`, `scripts/` contain no additional generative call sites (rg over those trees returned no matches). Non-Python docs (README, CHANGELOG) mention VLM but add no call sites.

## What could still hide a counterexample

- A dynamically imported model wrapper not matching search tokens (none found).
- Remote Docling **service** client (`docling/service_client/`) sends documents to a server; server-side validation logic is out of this clone (client itself has no local LLM judge).
- TableFormerV2 `generate` (`table_structure_model_v2.py`) is vision seq2seq, excluded as non-LLM/VLM; it still does not compare prior output to source.
