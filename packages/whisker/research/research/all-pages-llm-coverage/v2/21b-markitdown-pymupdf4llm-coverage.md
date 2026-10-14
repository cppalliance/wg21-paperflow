# 21b - markitdown + pymupdf4llm page coverage
**Claims tested:** C4 (decision-critical foreign facts: page iteration, loss semantics, LLM presence)
**Exhaustive:** no (see Coverage gaps)

## Method
Search commands run (repo roots: `packages/whisker/research/repos/markitdown`, `packages/whisker/research/repos/pymupdf4llm`):

```
rg -n -i "page|for.*range|page_count|get_text|except|try:" packages/markitdown/src/markitdown/converters/_pdf_converter.py packages/markitdown/src/markitdown/converters/_doc_intel_converter.py
rg -n -i "pdf|PDF|\.pdf" packages/markitdown/src --glob "*.py"
rg -n "_extract_tables_from_words|plain_page_indices" packages/markitdown/src
rg -n -i "openai|anthropic|claude|gemini|google\.genai|genai|litellm|vllm|ollama|chat\.completions|completions\.create|messages\.create|generate_content|GenerativeModel|transformers|AutoModel|\.generate\(|pipeline\(|predict|invoke|system_prompt|LLM|VLM|gpt-|llama|qwen" --glob "*.py"  (pymupdf4llm full tree)
rg -n -i "openai|anthropic|claude|gemini|google\.genai|genai|litellm|vllm|ollama|chat\.completions|completions\.create|messages\.create|generate_content|GenerativeModel|transformers|AutoModel|\.generate\(|pipeline\(|system_prompt|gpt-|qwen" src --glob "*.py"  (pymupdf4llm src only)
rg -n "for pno|for page|enumerate\(doc|load_page|page_filter" src --glob "*.py"  (pymupdf4llm)
rg -n "except|pass$|continue$" src/ocr --glob "*.py"  (pymupdf4llm)
Get-ChildItem -Recurse -Filter "*.py" .../markitdown/packages/markitdown/src  → 38 files
Get-ChildItem -Recurse -Filter "*.py" .../pymupdf4llm/src  → 17 files
```

Files read in full: `markitdown/.../converters/_pdf_converter.py`; `pymupdf4llm/src/__init__.py`; `pymupdf4llm/src/helpers/pymupdf_rag.py`; `pymupdf4llm/src/llama/pdf_markdown_reader.py`.

Files read partially: `markitdown/.../converters/_doc_intel_converter.py`, `_cu_converter.py`, `_markitdown.py`; `pymupdf4llm/src/helpers/document_layout.py`, `src/helpers/utils.py`, `src/ocr/analyze_page.py`, `src/ocr/tesseract_api.py`.

## Inventory

### markitdown — PDF-to-markdown production paths (3 direct + 1 indirect)

| # | file:line | role / finding |
|---|-----------|----------------|
| M1 | `_pdf_converter.py:520-589` | **Primary local PDF path.** `PdfConverter.convert` opens pdfplumber, iterates every page. |
| M2 | `_pdf_converter.py:553` | **Page iteration (local):** `for page_idx, page in enumerate(pdf.pages):` — only in-repo per-page loop for PDF markdown. |
| M3 | `_pdf_converter.py:554-564` | Per page: try form extraction; else `page.extract_text()`. Append chunk only if `page_content.strip()` or `text and text.strip()` — **blank/whitespace-only pages produce no output chunk (silent drop).** |
| M4 | `_pdf_converter.py:558-559` | Form path: append only when `page_content.strip()` — form-detected page with empty extraction dropped. |
| M5 | `_pdf_converter.py:561` | `plain_page_indices.append(page_idx)` collected but **never read afterward** — dead variable; no selective re-extraction. |
| M6 | `_pdf_converter.py:570-572` | If `form_page_count == 0`, **discards all per-page pdfplumber work**; replaces with `pdfminer.high_level.extract_text(pdf_bytes)` on whole document. |
| M7 | `_pdf_converter.py:576-579` | `except Exception:` — **any pdfplumber failure swallowed** (no log/re-raise); falls back to pdfminer whole-document extract. |
| M8 | `_pdf_converter.py:582-584` | If markdown still empty after pdfplumber path, second pdfminer whole-document attempt. |
| M9 | `_pdf_converter.py:574` | Non-fallback join: `"\n\n".join(markdown_chunks)` — **no page markers, indices, or metadata.** |
| M10 | `_pdf_converter.py:398-492` | `_extract_tables_from_words` defined but **zero call sites in repo** (rg confirms only definition + unused `plain_page_indices`). Dead helper, not a live path. |
| M11 | `_pdf_converter.py:120-395` | `_extract_form_content_from_words` can return `None` (lines 134, 199, 238, 246, 254, 257, 299) — triggers plain `extract_text` for that page, not a page skip. |
| M12 | `_pdf_converter.py:92-96` | `_to_markdown_table` filters empty rows — table cell loss inside a page, not whole-page loss. |
| M13 | `_doc_intel_converter.py:237-254` | **Optional Azure Document Intelligence PDF path.** Single `begin_analyze_document` call; **no local page iteration.** Returns `result.content` as one markdown string. |
| M14 | `_doc_intel_converter.py:253` | Strips HTML comments from cloud markdown — comment text dropped. |
| M15 | `_cu_converter.py:525-570` | **Optional Azure Content Understanding PDF path.** Single `begin_analyze_binary` + `to_llm_input(result)` — **no local page iteration.** `to_llm_input` is Azure SDK formatter name, not an LLM API call. |
| M16 | `_zip_converter.py:87-104` | **Indirect path:** ZIP entries re-dispatched via `MarkItDown.convert_stream` — a `.pdf` inside a ZIP reaches M1–M12. No PDF-specific page logic here. |
| M17 | `_markitdown.py:30,40-41` | Default registration imports `PdfConverter`; DocIntel/CU are opt-in at construction — not auto-enabled. |

**markitdown page-boundary audit:** Default `PdfConverter` output is a single concatenated string with `\n\n` between non-empty page chunks (M9). **No page separators, page numbers, or per-page sidecar.** Cloud paths (M13, M15) opaque — page boundaries depend on Azure output format, not markitdown code.

---

### pymupdf4llm — PDF-to-markdown production paths (3 top-level)

| # | file:line | role / finding |
|---|-----------|----------------|
| P1 | `src/__init__.py:199-203` | `to_markdown` dispatches: layout mode → `_layout_to_markdown`; else → `pymupdf_rag.to_markdown`. |
| P2 | `src/__init__.py:51-56` | Default attempts `pymupdf.layout` import; on failure falls back to legacy (`use_layout(False)`). |
| P3 | `src/__init__.py:59-114` | **Layout path entry:** `_layout_to_markdown` → `document_layout.parse_document` → `ParsedDocument.to_markdown`. |
| P4 | `document_layout.py:1166-1175` | Page selection: `pages is None` → `range(mydoc.page_count)`; else int or sequence. |
| P5 | `document_layout.py:1189-1190` | **Layout page iteration:** `for pno in page_filter: page = mydoc.load_page(pno)`. |
| P6 | `document_layout.py:1195-1204` | Optional OCR per page via `ocr_function(...)` when `make_ocr_decision` true — replaces page text layer. |
| P7 | `document_layout.py:1341` | Every selected page appended to `document.pages` — **no whole-page skip in parse loop.** |
| P8 | `document_layout.py:795-871` | **Layout markdown emit:** `for page in self.pages:` concatenates box text. Optional `page_separators` adds `--- end of page={page.page_number=} ---` (864-865). Optional `page_chunks=True` returns list of dicts with `metadata.page_number` (116-152, 869-870). |
| P9 | `document_layout.py:806-811` | `header=False` / `footer=False` skips page-header/page-footer boxes — **header/footer text dropped by option.** |
| P10 | `document_layout.py:993-1004` | `select_ocr_function`: bare `except:` swallows import/tessdata probe failures — OCR silently disabled, not page-dropped. |
| P11 | `document_layout.py:1156-1164` | Force-OCR without engine: raises `ValueError`; no engine available → warning + `OCRMode.NEVER`. |
| P12 | `pymupdf_rag.py:324-1315` | **Legacy path entry:** `to_markdown`. |
| P13 | `pymupdf_rag.py:426-427` | Default pages: `pages = list(range(doc.page_count))`. |
| P14 | `pymupdf_rag.py:415-424` | Reflowable docs: relayout to **one virtual page** covering full document — multi-page reflowable PDF collapsed before iteration. |
| P15 | `pymupdf_rag.py:119-120` | `IdentifyHeaders.__init__`: `for pno in pages: page = mydoc.load_page(pno)` — font scan only. |
| P16 | `pymupdf_rag.py:1285-1313` | **Legacy page iteration:** `for pno in pages: parms = get_page_output(...)`. |
| P17 | `pymupdf_rag.py:994-1253` | `get_page_output` processes one page; always returns `parms` (no early None for empty pages). |
| P18 | `pymupdf_rag.py:490-494` | `save_image`: returns `""` for images below `image_size_limit` — image dropped, not page. |
| P19 | `pymupdf_rag.py:499-500` | Zero-size pixmap → return `""` — image dropped. |
| P20 | `pymupdf_rag.py:560-561` | `write_text`: `if not outside_all_bboxes(lrect, parms.img_rects): continue` — **text lines overlapping image rects skipped.** |
| P21 | `pymupdf_rag.py:1047-1055` | Images filtered by size/intersection with clip — small/outside images dropped. |
| P22 | `pymupdf_rag.py:1071` | `img_info = img_info[:30]` — **max 30 images per page**; rest dropped. |
| P23 | `pymupdf_rag.py:1087-1089` | If `graphics_count > GRAPHICS_LIMIT`: sets `IGNORE_GRAPHICS = True` — vector graphics dropped for page. |
| P24 | `pymupdf_rag.py:1105-1107` | Tables with `row_count < 2` or `col_count < 2` → `omitted_table_rects` — **small tables dropped.** |
| P25 | `pymupdf_rag.py:1019-1021` | `accept_invisible = page_is_ocr(page) or ignore_alpha` — invisible text skipped unless OCR page or `ignore_alpha` false (default True at 352). |
| P26 | `pymupdf_rag.py:913-918` | `page_is_ocr`: bare `except: pass` — OCR detection failure returns False (not page drop). |
| P27 | `pymupdf_rag.py:1250-1252` | Optional `page_separators`: appends `\n\n--- end of page={parms.page.number} ---\n\n`. |
| P28 | `pymupdf_rag.py:1255-1312` | Optional `page_chunks=True`: returns list of dicts with `metadata.page` (965), `text`, tables, images per page. |
| P29 | `pymupdf_rag.py:1295-1296` | Default (`page_chunks=False`): concatenates `parms.md_string` — **no page boundaries unless `page_separators`.** |
| P30 | `llama/pdf_markdown_reader.py:60-65` | **LlamaIndex wrapper:** `for page in doc:` calls `_process_doc_page` per physical page. |
| P31 | `llama/pdf_markdown_reader.py:86-91` | Each page: `pymupdf_rag.to_markdown(doc, pages=[page_number], ...)` — one legacy conversion per page; metadata includes `page` and `total_pages` (103-104) in `extra_info`, not in markdown body. |
| P32 | `ocr/tesseract_api.py:35-36` | `if TESSDATA is None: return` — OCR callback no-op; page proceeds without OCR text. |
| P33 | `ocr/tesseract_api.py:56-59` | If existing OCR spans and `keep_ocr_text`: early `return` — skips re-OCR. |
| P34 | `ocr/analyze_page.py:48-53` | `predict_ocr_probability` uses `ort.InferenceSession` ONNX model — **OCR routing classifier, not an LLM/VLM API.** |
| P35 | `ocr/analyze_page.py:79-82` | Bare `except:` on pixmap mask merge — failure swallowed, continues OCR analysis. |

**pymupdf4llm page-boundary audit:** Default string output concatenates pages with no separator (P29). Auditable boundaries require caller to pass `page_separators=True` (P27/P8) or `page_chunks=True` (P28/P8) — opt-in, default off.

---

### pymupdf4llm — LLM/VLM call-site scan (charter search floor, `src/` only)

| # | file:line | classification |
|---|-----------|----------------|
| L1 | `rg` over `pymupdf4llm/src/**/*.py` for openai, anthropic, claude, gemini, genai, litellm, vllm, ollama, chat.completions, completions.create, messages.create, generate_content, GenerativeModel, transformers, AutoModel, .generate(, pipeline(, system_prompt, gpt-, qwen | **Zero matches in production `src/`.** |
| L2 | `ocr/analyze_page.py:48-53` | ONNX `InferenceSession.run` — local ML model for OCR need detection; **not LLM.** |
| L3 | `llama/pdf_markdown_reader.py:10-15` | Imports `llama_index.core` — framework adapter; **no model inference call.** |
| L4 | `examples/country-capitals/country-capitals.py:96-97` | `client.completions.create(model="gpt-3.5-turbo-instruct"...)` — **example script only, outside `src/`.** |
| L5 | `examples/GUI/browser-app.py:108-109` | `ConversationalRetrievalChain.from_llm(ChatOpenAI(...))` — **example only, outside `src/`.** |

---

## Verdict on the claim(s)

**C4 (foreign page-coverage facts): PARTIALLY CONFIRMED.**

- **markitdown:** Only `PdfConverter` iterates pages locally (M2). Blank pages silently omitted (M3-M4). Mixed-form documents can lose per-page pdfplumber extraction when any form page exists but others used plain path, then entire output re-built from chunks without page markers (M6-M9). No built-in page audit trail.
- **pymupdf4llm:** Both layout (P5) and legacy (P16) iterate all selected pages; legacy can collapse reflowable PDFs to one virtual page (P14). Substantial within-page loss paths (P18-P25) but whole pages are processed. Page-boundary audit is opt-in via `page_separators` / `page_chunks` (P8, P27-P28).
- **pymupdf4llm LLM:** **Name is misleading.** Production `src/` contains **no LLM/VLM API invocation** (L1). Package produces markdown *for* LLM/RAG consumption.

## Coverage gaps

- **markitdown:** 38 production `.py` files under `packages/markitdown/src`; read in full only `_pdf_converter.py`. Not fully read: remaining 37 files (most non-PDF). Plugin entry points (`_markitdown.py:76-81`) not enumerated — third-party converters could add PDF paths. Tests/examples not scanned.
- **pymupdf4llm:** 17 production `.py` files under `src/`; read in full: `__init__.py`, `pymupdf_rag.py`, `pdf_markdown_reader.py`. Not fully read: `multi_column.py`, `get_text_lines.py`, `progress.py`, `utils.py` (partial), all `ocr/*_api.py` except `tesseract_api.py`/`analyze_page.py` (partial). `examples/` and `tests/` excluded from production LLM verdict but noted for L4-L5.

## What could still hide a counterexample

- markitdown plugin converters registered via `markitdown.plugin` entry points (not in default builtins).
- pymupdf4llm OCR backend modules (`rapidocr_api.py`, `paddleocr_api.py`, etc.) may swallow errors on paths not fully line-read.
- Dynamic imports inside `pymupdf.layout` (external PyMuPDF package, not this clone) could add behavior outside `pymupdf4llm/src/`.
- Cloud markitdown paths (M13, M15) may drop pages inside Azure; not visible in local code.
