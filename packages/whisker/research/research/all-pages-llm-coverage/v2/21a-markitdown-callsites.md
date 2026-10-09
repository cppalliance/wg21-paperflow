# 21a - markitdown (SHA e144e0a)
**Claims tested:** C1, C2
**Exhaustive:** yes

## Method

Repo: `packages/whisker/research/repos/markitdown` at pinned SHA `e144e0a2be95b34df17433bac904e635f2c5e551` (verified via `git rev-parse HEAD`).

Search commands run (all from repo root, case-insensitive where noted):

```
rg -i -n "openai|anthropic|claude|gemini|google\.genai|genai|litellm|vllm|ollama|chat\.completions|completions\.create|messages\.create|generate_content|GenerativeModel|transformers|AutoModel|\.generate\(|pipeline\(|predict|invoke|system_prompt|LLM|VLM|gpt-|llama|qwen|llm_client|begin_analyze" --glob "*.py" --glob "!**/.git/**"

rg -n "chat\.completions\.create" --glob "*.py"

rg -i -l "openai|anthropic|claude|gemini|chat\.completions|llm_client|GenerativeModel|litellm|vllm|ollama|begin_analyze" --glob "!**/.git/**"

rg -i -n "benchmark|eval|judge|compare.*output|verify|score" --glob "*.py"
```

71 Python files under repo root searched via rg. Read in full: `packages/markitdown/src/markitdown/converters/_llm_caption.py`, `_image_converter.py`, `_pptx_converter.py`, `_cu_converter.py`, `_doc_intel_converter.py`; `packages/markitdown-ocr/src/markitdown_ocr/_ocr_service.py`, `_plugin.py`, `_pptx_converter_with_ocr.py`, `_pdf_converter_with_ocr.py`, `_docx_converter_with_ocr.py`, `_xlsx_converter_with_ocr.py`; `packages/markitdown/src/markitdown/_markitdown.py` (LLM kwargs plumbing); `packages/markitdown-mcp/src/markitdown_mcp/__main__.py`. Skimmed remaining `.py` hits via rg only.

## Inventory

### Direct OpenAI-compatible LLM/VLM invocation sites (production)

| File:Line | Function | Input | Output | Role | C2 class |
|-----------|----------|-------|--------|------|----------|
| `packages/markitdown/src/markitdown/converters/_llm_caption.py:49` | `llm_caption` | Image bytes as base64 data-URI + text prompt (default: `"Write a detailed caption for this image."`; overridable via `llm_prompt` kwarg) | `response.choices[0].message.content` (caption string or None on encode failure) | Shared helper: multimodal caption for embedded images | extraction |
| `packages/markitdown/src/markitdown/converters/_image_converter.py:137` | `ImageConverter._get_llm_description` | Same as `llm_caption` (duplicate inline implementation; does not call `_llm_caption.py`) | `response.choices[0].message.content` (description string) | Standalone image files (jpg/png): append `# Description:` section to markdown | extraction |
| `packages/markitdown-ocr/src/markitdown_ocr/_ocr_service.py:86` | `LLMVisionOCRService.extract_text` | Image stream as base64 data-URI + OCR prompt (default: `"Extract all text from this image..."`; overridable) | `response.choices[0].message.content` wrapped in `OCRResult.text` | LLM-vision OCR for embedded images and scanned PDF pages (markitdown-ocr plugin) | extraction |

### Call paths into the three direct sites (not separate API invocations)

| File:Line | Calls | Role |
|-----------|-------|------|
| `packages/markitdown/src/markitdown/converters/_pptx_converter.py:120` | `llm_caption(...)` → site 1 | PPTX embedded picture → LLM caption merged into `![alt](...)` alt text |
| `packages/markitdown/src/markitdown/converters/_image_converter.py:72` | `_get_llm_description(...)` → site 2 | Image converter entry when `llm_client` + `llm_model` configured |
| `packages/markitdown-ocr/src/markitdown_ocr/_pdf_converter_with_ocr.py:239` | `ocr_service.extract_text(...)` → site 3 | Per embedded PDF image on a page |
| `packages/markitdown-ocr/src/markitdown_ocr/_pdf_converter_with_ocr.py:370` | `ocr_service.extract_text(...)` → site 3 | Scanned PDF page rendered at 300 DPI (pdfplumber path) |
| `packages/markitdown-ocr/src/markitdown_ocr/_pdf_converter_with_ocr.py:403` | `ocr_service.extract_text(...)` → site 3 | Scanned PDF page rendered at 300 DPI (PyMuPDF fallback path) |
| `packages/markitdown-ocr/src/markitdown_ocr/_docx_converter_with_ocr.py:146` | `ocr_service.extract_text(...)` → site 3 | DOCX embedded image OCR |
| `packages/markitdown-ocr/src/markitdown_ocr/_xlsx_converter_with_ocr.py:197` | `ocr_service.extract_text(...)` → site 3 | XLSX embedded image OCR |
| `packages/markitdown-ocr/src/markitdown_ocr/_pptx_converter_with_ocr.py:129` | `ocr_service.extract_text(...)` → site 3 | PPTX image OCR fallback when caption path fails or returns empty |
| `packages/markitdown-ocr/src/markitdown_ocr/_plugin.py:42-47` | constructs `LLMVisionOCRService` from `llm_client`/`llm_model` kwargs | Plugin wiring only; no API call |

**Broken caption path in OCR plugin (not an invocation site):** `packages/markitdown-ocr/src/markitdown_ocr/_pptx_converter_with_ocr.py:99` does `from ._llm_caption import llm_caption`, but no `_llm_caption.py` exists in `markitdown_ocr` (ImportError caught at `:121`; OCR fallback at `:129` is the live path).

### Remote cloud multimodal extraction (no local `llm_client`; server-side VLM/LLM)

| File:Line | Function | Input | Output | Role | C2 class |
|-----------|----------|-------|--------|------|----------|
| `packages/markitdown/src/markitdown/converters/_cu_converter.py:557` | `ContentUnderstandingConverter.convert` → `self._client.begin_analyze_binary(...)` | File bytes, `analyzer_id`, `content_type` | `to_llm_input(result)` formatted markdown string (`:567`) | Optional `--use-cu` path: Azure Content Understanding produces conversion output from source document (documents, images, audio, video) | extraction |

### Remote cloud layout/OCR (not a user-supplied LLM client; listed per charter search floor)

| File:Line | Function | Input | Output | Role | C2 class |
|-----------|----------|-------|--------|------|----------|
| `packages/markitdown/src/markitdown/converters/_doc_intel_converter.py:244` | `DocumentIntelligenceConverter.convert` → `begin_analyze_document(...)` | Document bytes, `prebuilt-layout` model, OCR/layout features | `result.content` markdown (`:253`) | Optional `--use-docintel` path: Azure Document Intelligence layout/OCR extraction | other (cloud OCR/layout ML) |

### LLM kwargs plumbing (no API call)

| File:Line | Role |
|-----------|------|
| `packages/markitdown/src/markitdown/_markitdown.py:124-149` | Stores `llm_client`, `llm_model`, `llm_prompt` on `MarkItDown` init |
| `packages/markitdown/src/markitdown/_markitdown.py:588-593` | Forwards stored LLM kwargs to converter `convert()` calls |

### Non-LLM hits from search floor (listed, not invocation sites)

| File:Line | Role | C2 class |
|-----------|------|----------|
| `packages/markitdown/src/markitdown/_markitdown.py:724` | `self._magika.identify_stream(...)` — file-type detection (Magika), not LLM | other |
| `packages/markitdown/src/markitdown/converters/_transcribe_audio.py:48` | `recognizer.recognize_google(audio)` — Google Speech API, not LLM/VLM | other |
| `packages/markitdown-mcp/src/markitdown_mcp/__main__.py:23` | `MarkItDown(...).convert_uri(uri)` — MCP wrapper; no LLM unless caller configures `llm_client` on `MarkItDown` (default MCP path does not) | other |

### Test / docs hits (charter: list but mark)

| Location | Role |
|----------|------|
| `packages/markitdown/tests/test_module_misc.py:476-503` | Mock `chat.completions.create`; integration test with real OpenAI when `OPENAI_API_KEY` set (`:508+`) |
| `packages/markitdown/tests/test_cu_converter.py` | Mocks `begin_analyze_binary` |
| `README.md`, `packages/markitdown-ocr/README.md` | Usage docs for `llm_client` / `llm_model` |

No eval-harness or benchmark modules invoking LLM to score pre-existing conversion output (rg for `benchmark|eval|judge|compare.*output|verify|score` in `.py` returned zero production hits).

## Verdict on the claim(s)

**C1 (negative existential — no per-page verification of already-produced output by LLM/VLM):** **CONFIRMED.** At SHA e144e0a, no production or test code path invokes an LLM/VLM to judge an already-produced conversion output against the source document per page/chunk/unit. All LLM/VLM use is extraction during conversion: image captions (`_llm_caption.py:49`, `_image_converter.py:137`), vision OCR (`_ocr_service.py:86`), or remote Azure CU whole-file analysis (`_cu_converter.py:557`). None of these take pre-rendered markdown plus source and ask the model to verify, score, or compare fidelity.

**C2 (positive classification):** All LLM/VLM invocation sites classified above. Summary: 3 direct OpenAI-compatible extraction sites, 1 remote Azure CU extraction site, 1 remote Doc Intel layout/OCR site (other). Zero refinement sites. Zero eval-harness LLM judge sites.

## Coverage gaps

None. All 71 Python files searched; non-Python assets (README, test HTML fixtures, Dockerfiles) grep-scanned for LLM patterns; no additional languages with model calls found.

## What could still hide a counterexample

- Plugin packages installed at runtime but not vendored in this clone (only `markitdown-ocr` is present as a first-party plugin package).
- Azure CU / Doc Intel server-side behavior beyond what local `begin_analyze_*` calls reveal (local code only sends source bytes; no post-conversion verification loop).
- Dynamic client construction outside searched patterns (no `importlib`/`eval` LLM loading found in `.py`).
- Commits beyond pinned SHA e144e0a.
