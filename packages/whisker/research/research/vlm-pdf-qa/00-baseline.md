# 00 - Evidence Baseline: VLM-on-PDF for the whisker LLM QA lane

## 1. Goal

The operator has decided the whisker LLM QA lane (`packages/whisker/src/whisker/tapetum_llm/`) must ALWAYS receive the ORIGINAL PDF, not only the converted markdown, and must judge conversion fidelity INDEPENDENTLY of the deterministic lane before the existing fusion layer compares/fuses the two verdicts. Today the LLM lane sees only markdown + deterministic whisker signals and never opens the PDF. This baseline records, with file:line anchors, exactly how the surveyed open-source repos feed PDFs to LLMs/VLMs (rasterization, DPI, image packaging, prompts, per-page loop, aggregation, verification patterns, model choice, self-hostability) and what our own stack does today, so Step-1 personas can judge which code/logic is portable.

## 2. Fact sheet: surveyed repos

Paths are relative to `packages/whisker/research/repos/` (git-ignored; searched with `rg --no-ignore`).

### Repos WITH a real LLM/VLM-on-page-image code path

**olmocr** (finetuned Qwen2.5-VL, self-hosted vLLM) - the closest match to what we want.
- Rasterization: `render_pdf_to_base64png(local_pdf_path, page_num, target_longest_image_dim=2048)` shells out to poppler `pdftoppm` at scale `target_longest_image_dim * 72 / longest_dim` px/point, returns base64 PNG - `olmocr/olmocr/data/renderpdf.py:39-60`. NOT PyMuPDF (poppler subprocess).
- Runtime default longest dim = 1288 px - `olmocr/olmocr/pipeline.py:1229`.
- Image packaging: OpenAI chat `content` parts = `{"type":"text",...}` + `{"type":"image_url","image_url":{"url":"data:image/png;base64,..."}}`, `temperature=0.0`, `max_tokens=8000` - `olmocr/olmocr/pipeline.py:133-146`.
- Prompt: `build_no_anchoring_v4_yaml_prompt()` (page->YAML), older variants incl. `build_finetuning_prompt` and anchor-text prompts - `olmocr/olmocr/prompts/prompts.py:147,156,164`, `olmocr/olmocr/prompts/anchor.py:17`.
- Per-page loop + retry: `try_single_page(...)` posts to `{server}/chat/completions` (vLLM), `MODEL_MAX_CONTEXT=16384`, temperature escalates by attempt - `olmocr/olmocr/pipeline.py:149-175`.
- Model: `model_name="olmocr"` (Qwen2.5-VL finetune), served via local vLLM - `olmocr/olmocr/pipeline.py:106,161`. Self-hostable (open weights). `pipeline.py` = 1274 LOC, `renderpdf.py` = 97 LOC, `prompts.py` = 159 LOC.

**marker** (`--use_llm` block refinement; cloud-default but self-hostable).
- Page render: pypdfium2 `page.render(scale=dpi/72).to_pil()` - `marker/marker/providers/pdf.py:411`; DPI settings `lowres_image_dpi=96` (layout), `highres_image_dpi=192` (OCR/LLM) - `marker/marker/builders/document.py:18-25,41-42`.
- Block-image crop for the LLM: `extract_image(..., highres=True, expansion=(ratio,ratio))` - `marker/marker/processors/llm/__init__.py:69-78`; `image_expansion_ratio` at line 46.
- Image->base64: `BaseService.img_to_base64(img, format="WEBP")` - `marker/marker/services/__init__.py:22`.
- Services (self-host path exists): `azure_openai.py, claude.py, gemini.py, ollama.py, openai.py, vertex.py` under `marker/marker/services/`; Gemini default `gemini-2.0-flash` - `marker/marker/services/gemini.py:23`.
- Nature: LLM REFINES already-converted blocks (`llm_table`, `llm_equation`, `llm_page_correction`, `llm_mathblock`, ... under `marker/marker/processors/llm/`), it does NOT independently judge the whole conversion. `processors/llm/__init__.py` = 170 LOC.

**MinerU** (VLM backend "MinerU2-VLM", Qwen2-VL family).
- Backend switch supports `transformers` (`Qwen2VLForConditionalGeneration.from_pretrained`), `vllm-engine`, `vllm-async-engine`, `lmdeploy-engine`, `mlx-engine`, and `http-client` (remote server_url) - `MinerU/mineru/backend/vlm/vlm_analyze.py:56-196` (Qwen2VL at :86-97, vllm at :118-149). Self-hostable. `vlm_analyze.py` = 557 LOC.
- Nature: VLM page->structured-doc CONVERSION, not QA-of-conversion.

**Dolphin** (Qwen2.5-VL doc parsing, two-stage).
- Model: `Qwen2_5_VLForConditionalGeneration.from_pretrained` + `qwen_vl_utils.process_vision_info` - `Dolphin/demo_page.py:12-27`.
- `chat(prompt, image)` runs the VLM on a PIL page image - `Dolphin/demo_page.py:43-103`.
- Two-stage prompts: layout first `model.chat("Parse the reading order of this document.", image)` then per-element `"Parse the table in the image."` etc - `Dolphin/demo_page.py:186,201-269`. Self-hostable HF. `demo_page.py` = 354 LOC. Nature: CONVERSION.

**nougat** (Donut-style vision encoder-decoder, no text prompt).
- Rasterization: `rasterize_paper(..., dpi=96)` via **pypdfium2** `PdfBitmap.to_pil` (NOT fitz) - `nougat/nougat/dataset/rasterize.py:9,18-49`.
- Architecture: `SwinEncoder` (Swin `swin_base_patch4_window12_384`) + mBART decoder - `nougat/nougat/model.py:37-114`. Trained model, no prompt string. Self-hostable HF. `rasterize.py` = 73 LOC. Nature: CONVERSION.

**docling** (SmolDocling / GraniteDocling VLM pipeline; strongest packaging reference for a self-hosted API).
- Pipeline supports `ApiVlmOptions` (remote/self-hosted OpenAI-style) and `InlineVlmOptions` with MLX / TRANSFORMERS / VLLM frameworks - `docling/docling/pipeline/vlm_pipeline.py:163-199`. `vlm_pipeline.py` = 623 LOC.
- Model specs: GraniteDocling + SmolDocling-256M, prompt `"Convert this page to docling."`, image `scale=2.0` (2x = ~144 DPI), vLLM/Ollama API at `http://localhost:8000/v1/chat/completions` - `docling/docling/datamodel/vlm_model_specs.py:22-113` (prompt :24,100; scale :34,50,90,104; vllm-api url :57). `vlm_model_specs.py` = 534 LOC.
- Image packaging (portable): base64 PNG into `content` parts `{"type":"image_url","image_url":{"url":"data:image/png;base64,..."}}` - `docling/docling/utils/api_image_request.py:190-199,283-290`. `api_image_request.py` = 328 LOC.
- QA/verification signal worth porting: API stop reasons incl. `VlmStopReason.CONTENT_FILTERED` when the provider filters - `docling/docling/utils/api_image_request.py:92-94`. Nature: CONVERSION, but the API-VLM image request code and the PARTIAL/stop-reason handling are directly reusable.

**surya** (OCR/layout foundation models; the engine under marker).
- Recognition foundation model checkpoint `datalab-to/surya-ocr-2` - `surya/surya/settings.py:40`; separate detection/layout checkpoints - `settings.py:110`.
- Verification-relevant: an OCR-error detection model `OCR_ERROR_MODEL_CHECKPOINT` - `surya/surya/settings.py:119` (a conversion-quality/confidence signal, not a chat LLM). Self-hostable HF. Nature: OCR/layout, no page-image->chat-LLM judging.

### Repos with vision MODELS but NO page-image->chat-LLM (no QA-of-conversion) path

- **PDF-Extract-Kit**: task modules are `formula_detection, formula_recognition, layout_detection, ocr, table_parsing` - `PDF-Extract-Kit/pdf_extract_kit/tasks/`; only specialized vision models (UniMERNet formula, PaddleOCR `tasks/ocr/models/paddle_ocr.py`). No `openai`/`image_url`/base64 chat path.
- **unstructured**: `partition_pdf(strategy in {hi_res, ocr_only, fast})` uses a layout-detection model, not an LLM - `unstructured/unstructured/partition/pdf.py:127-236`; no base64/image_url/openai in the PDF path.

### Repos with NO LLM/VLM-on-PDF path (one line each)

- **markitdown**: multimodal LLM only for single-image-file captioning ("Write a detailed caption for this image.") via optional `llm_client`, not PDF-page QA - `markitdown/packages/markitdown/src/markitdown/converters/_image_converter.py:69-97`.
- **langextract**: text-based structured extraction (`extract(...)`), Gemini/Ollama on text, not page images - `langextract/langextract/__init__.py:53`.
- **camelot**: table extraction from PDF vector/text; no LLM.
- **firecrawl**: web scraping; LLM extract runs on HTML/markdown text, not PDF page images.
- **grobid**: CRF/DL bibliographic TEI extraction; no VLM chat.
- **pdfplumber / PyMuPDF / pymupdf4llm / pdf-to-markdown**: deterministic PDF text/layout extraction; no LLM.
- **img2table / tabula-java**: table extraction; no LLM.
- **html2text / markdownify / turndown / node-html-markdown / html-to-markdown-go / html-to-markdown-py / mdream / pandoc**: HTML/doc->markdown text converters; no LLM, no PDF page images.

## 3. OUR-side facts

- **LLM lane is markdown-only.** `_custom_select` loads ONLY markdown via `backend.get_paper_md(pid)` plus the whisker det sidecar; no PDF anywhere in state (`_PipelineState.paper_md`, `whisker_signals`) - `packages/whisker/src/whisker/tapetum_llm/adjudicate.py:175-199,153-169`. Triage/adjudicate messages inject only markdown text via `ctx.inject_untrusted(md)` - `adjudicate.py:391,423`.
- **Oversize handling** is H2 chunking at `MAX_PAPER_MD_CHARS = 500_000` - `packages/whisker/src/whisker/tapetum_llm/constants.py:61`; chunk loop in `_custom_triage` - `adjudicate.py:209-223`.
- **CLI + sidecars + fusion**: `whisker-tapetum-llm` CLI writes sidecars via `sidecar_path`/`whisker_output_dir`; fusion via `fuse_verdicts` - `packages/whisker/src/whisker/tapetum_llm/cli.py:34-36`.
- **Pipeline has NO multimodal support today.** The single LLM entry `run_agent(ctx, spec, user_msg)` takes `user_msg: str` - `packages/pipeline/src/pipeline/runner.py:219-225`; every backend's `run(system_prompt, user_message, output_type, ...)` takes `user_message: str` (no image/content-parts arg) - `packages/pipeline/src/pipeline/model_backends.py:191-203`. `StepContext.inject_untrusted(content: str) -> str` is text-only - `runner.py:119-121`. The only "image" code in pipeline is figure EXTRACTION for tomd conversion (`process.py` image handoff, `postconditions.py` image counts), never image INPUT to a model - `packages/pipeline/src/pipeline/process.py:241-488`, `postconditions.py:49-58`. **Adding a VLM path requires a new multimodal message type end-to-end** (StepContext -> run_agent -> ModelBackend.run) plus a vision-capable backend.
- **SERVICES.toml: no vision-capable service today.** All `[services.*]` are `vllm_thinking` or `anthropic` text models: `deepseek-v4-pro` (h200x8, alliance-pod), `deepseek-r1-distill-70b`, `google/gemma-4-31B-it`, `Qwen/Qwen3.6-27B`, `Qwen/Qwen3-235B-A22B-FP8`, `Qwen/Qwen3-32B`, `claude-opus-4-6` - `SERVICES.toml:47-164`. There is NO `vision_capable` capability flag in the schema (only `thinking_capable`, `tools_capable`). The 24/7 self-hosted `alliance-pod` runs `deepseek-v4-pro` (text) - `SERVICES.toml:64-74`. A VLM (e.g. Qwen2.5-VL) would be a NEW service + a new `vllm`-family vision backend class.
- **paperstore CAN hand over the PDF.** `get_source_path(pid) -> Path` returns the staged `.pdf`/`.html` (`_SOURCE_SUFFIXES = (".pdf",".html",".htm")`) - `packages/paperstore/src/paperstore/sqlite_backend.py:1119-1135,927`; ABC contract at `backend.py:357-362`. No PDF-specific accessor is needed; `get_source_path` already exists. Extracted page/figure images use `get_paper_image_path(pid,page,index,ext)` - `sqlite_backend.py:1019`.
- **tomd already depends on PyMuPDF** (`pymupdf~=1.27.0`) - `packages/tomd/pyproject.toml:10`. Reuse beats adding a rasterizer dep (poppler/pypdfium2). Confirmed importable in the workspace venv: PyMuPDF 1.27.2.3 (runtime, section 4).
- **Constraints that bind a VLM design** (root `CLAUDE.md`): model-sovereignty (self-hosted open-weight, `vllm` backends; Opus only as dev ceiling), determinism D1-D11 (all calls through `run_agent`; serial, `temperature=0`/`seed=0` pinned in-backend; structured output `output_type`), fidelity (fail not partial), prompt-injection defense (`wrap_source`/`inject_untrusted` on all untrusted content - and a page IMAGE is untrusted too). Fusion layer STAYS (prior research `research/hybrid-llm-scoring/SYNTHESIS.md`); only what the LLM lane SEES changes.

## 4. Runtime facts (reproduced)

- **189 PDFs** in `data/paperstore/*.pdf`; also 189 total under `data/` (all PDFs live in `data/paperstore/`).
- Sample sizes/pages: `n5035.pdf` 56,124 B / 3 pages; `n5036.pdf` 356,472 B / 13 pages; `n5037.pdf` 56,212 B / 3 pages (page counts via `fitz.open(p).page_count` in the venv). WG21 papers are typically small (single-digit to low-dozens of pages), so per-page VLM rasterization is tractable.
- **PyMuPDF present**: `uv run --package tomd python -c "import fitz"` -> "PyMuPDF 1.27.2.3: Python bindings for the MuPDF 1.27.2 library." No new rasterization dependency required.
- Hot-module LOC (portability sizing): olmocr `pipeline.py` 1274 / `renderpdf.py` 97 / `prompts.py` 159; marker `processors/llm/__init__.py` 170 / `services/gemini.py` 122; MinerU `vlm_analyze.py` 557; Dolphin `demo_page.py` 354; nougat `rasterize.py` 73; docling `vlm_pipeline.py` 623 / `api_image_request.py` 328 / `vlm_model_specs.py` 534.
- Rasterizer choice across hot repos (portability): olmocr = poppler `pdftoppm` subprocess; marker + nougat + docling default = pypdfium2; MinerU/Dolphin operate on pre-rendered PIL images. We already ship PyMuPDF, so `page.get_pixmap(matrix=fitz.Matrix(dpi/72, dpi/72))` is the reuse-first path (mirrors marker's `scale=dpi/72`).

## 5. Step-1 persona roster

Generic core (10):
1. Security-Auditor
2. Determinism-Auditor
3. API-Contract-Analyst
4. Adversary-Evasion
5. False-Pass-Hunter
6. False-Fail-Hunter
7. Portability-Analyst
8. Downstream-Consumer
9. Product-Decision-Skeptic
10. Steelman

Ad-hoc per hot repo / concern (15):
11. olmocr-VLM-pipeline-analyst
12. marker-LLM-refinement-analyst
13. MinerU-VLM-backend-analyst
14. Dolphin-analyst
15. nougat-vision-analyst
16. docling-VLM-analyst
17. surya-ocr-error-analyst
18. page-rasterization-engineer
19. vision-prompt-designer
20. token-budget-economist
21. self-hosted-VLM-feasibility
22. multimodal-pipeline-integrator
23. independence-purist
24. cost-latency-analyst
25. fidelity-failure-mode-analyst

## 6. Web questions for Step 1

1. {question: "Which open-weight VLMs are viable self-hosted for document-QA / page-image judging in 2026, and how do they compare?", search_query: "self-hostable open-weight VLM document QA page image 2026 Qwen2.5-VL vs InternVL vs Granite"}
2. {question: "Are the olmOCR (Qwen2.5-VL finetune) weights openly available and under what license for self-hosting?", search_query: "olmOCR 2 model weights huggingface license Qwen2.5-VL allenai self-host"}
3. {question: "How is Qwen2.5-VL served under vLLM (image input format, max_pixels/min_pixels, OpenAI image_url compatibility)?", search_query: "Qwen2.5-VL vLLM serving image_url base64 max_pixels min_pixels OpenAI chat completions 2026"}
4. {question: "What does marker's LLM mode cost/latency look like and does it work against a local OpenAI-compatible server?", search_query: "marker pdf --use_llm ollama openai-compatible local server cost latency 2026"}
5. {question: "What are measured hallucination / error rates of VLMs on document QA, and how do people mitigate them?", search_query: "VLM hallucination rate document QA benchmark OCR fabrication mitigation 2026"}

## 7. Persona report template (verbatim for Step 1)

```
# NN - <Persona name>

**Verdict:** usable | usable-with-conditions | garbage   (+ 1 sentence why)
**Confidence:** high | medium | low

## Findings
- [CRITICAL|HIGH|MED|LOW] <claim>. Evidence: <file:line OR runtime number from 00>.
  Impact: <why it makes the target more/less trustworthy or adoptable>.
  (repeat; 3-8 findings, ranked)

## False-pass hypothesis
<one concrete case the target/our-equivalent would wrongly accept, or "none found">

## False-fail hypothesis
<one concrete case it would wrongly reject, or "none found">

## What would change my mind
<the single piece of evidence that would flip my verdict>
```
