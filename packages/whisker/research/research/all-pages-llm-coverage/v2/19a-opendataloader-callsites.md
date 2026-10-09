# 19a - opendataloader-pdf
**Claims tested:** C1, C2
**Exhaustive:** yes (full-repo `rg` at SHA `ddd3d8e`; all production hybrid/AI paths read; docling **in-pipeline** model steps run inside the `docling` dependency at `converter.convert()` boundaries, not as additional source lines in this clone)

## Method
```text
cd packages/whisker/research/repos/opendataloader-pdf
git rev-parse HEAD   # ddd3d8e9607a525cc3d00d4b05448a10c89c6935

rg -i -l "HybridDocumentProcessor|BACKEND|openai|anthropic|llm|vlm|prompt|generate_content|chat\.completions|litellm|ollama|vllm|gemini|claude|gpt-|qwen|llama|transformers|GenerativeModel|system_prompt" --glob "!*.git/*"

rg -n "HybridDocumentProcessor|processBackendPath|client\.convert|callModule|DocumentConverter|converter\.convert|PictureDescriptionVlm|do_formula|do_picture|OPEN_API_NAME|visualinfo|HybridClient" java/opendataloader-pdf-core/src/main python/opendataloader-pdf/src --glob "*.java" --glob "*.py"

rg -n -i "llm|judge|read.?back|as.?judge|verify.*markdown|openai|anthropic|gemini|GenerativeModel|chat\.completion" verification scripts docs examples python java --glob "*.{py,java,sh,md}"

rg -n "DocumentConverter|converter\.convert|PictureDescription|callModule|getVisualInfo" scripts python/opendataloader-pdf-mcp --glob "*.py"

rg -n "convertAsync|\.convert\(" java/opendataloader-pdf-core/src/main python/opendataloader-pdf/src --glob "*.java" --glob "*.py"
```

Files read in full (production AI/hybrid paths):
- `java/opendataloader-pdf-core/src/main/java/org/opendataloader/pdf/processors/HybridDocumentProcessor.java`
- `java/opendataloader-pdf-core/src/main/java/org/opendataloader/pdf/processors/DocumentProcessor.java` (extract/hybrid entry)
- `java/opendataloader-pdf-core/src/main/java/org/opendataloader/pdf/hybrid/HybridClient.java`
- `java/opendataloader-pdf-core/src/main/java/org/opendataloader/pdf/hybrid/HybridClientFactory.java`
- `java/opendataloader-pdf-core/src/main/java/org/opendataloader/pdf/hybrid/DoclingFastServerClient.java`
- `java/opendataloader-pdf-core/src/main/java/org/opendataloader/pdf/hybrid/HancomClient.java`
- `java/opendataloader-pdf-core/src/main/java/org/opendataloader/pdf/hybrid/HancomAIClient.java`
- `java/opendataloader-pdf-core/src/main/java/org/opendataloader/pdf/hybrid/TriageProcessor.java` (deterministic routing only; confirmed no model calls)
- `python/opendataloader-pdf/src/opendataloader_pdf/hybrid_server.py`
- `verification/ci-verify.py` (sampled: Level 2/3 compare logic)
- `scripts/bench.sh` (external bench wiring)

## Inventory

### Production — hybrid orchestration and BACKEND routing

| file:line | function | input | output | role / C2 class |
|---|---|---|---|---|
| `DocumentProcessor.java:182-183` | `extractContents` | PDF path, `Config` with `--hybrid` | delegates to hybrid processor | **Routing only** (not a model call); selects hybrid when `config.isHybridEnabled()` |
| `HybridDocumentProcessor.java:285-287` | `processDocument` → `TriageProcessor.triageAllPages` | filtered page `IObject`s, `HybridConfig` | `Map<Integer,TriageResult>` JAVA/BACKEND | **Deterministic triage** (line/grid/heuristics); no LLM |
| `HybridDocumentProcessor.java:273-281` | `processDocument` (full mode) | all pages | all pages → `TriageDecision.BACKEND` | **Routing only**; skips triage, sends all pages to backend |
| `HybridDocumentProcessor.java:694` | `processBackendPath` → `client.convert` | `HybridRequest` (PDF bytes, 1-indexed page set, JSON format) | `HybridResponse` → transformed `IObject`s per page | **Gateway**: single production entry for all AI backends on BACKEND-routed pages; **extraction** |

Supported backends (`HybridClientFactory.java:92-106`): `docling-fast`, `hancom`, `hancom-ai`. `azure`/`google` throw `UnsupportedOperationException`.

### Production — docling-fast backend (Java HTTP client → Python hybrid server → docling)

| file:line | function | input | output | role / C2 class |
|---|---|---|---|---|
| `DoclingFastServerClient.java:134-139` | `convert` | `HybridRequest` PDF bytes + optional page range | `HybridResponse` DoclingDocument JSON | **Extraction**: HTTP POST `/v1/convert/file` to local hybrid server |
| `hybrid_server.py:565-575` | `lifespan` → `create_converter` | CLI OCR/enrichment/device flags | singleton `DocumentConverter` | **Model load/config** (layout, OCR, table, optional formula/VLM weights loaded here) |
| `hybrid_server.py:482-488` | `create_converter` | `enrich_picture_description`, optional `picture_description_prompt` | `PictureDescriptionVlmOptions(repo_id="HuggingFaceTB/SmolVLM-256M-Instruct")` | **VLM config** (SmolVLM for alt text when `--enrich-picture-description`) |
| `hybrid_server.py:656` | `convert_file` → `_do_convert` | temp PDF path + optional `page_range` tuple | `ConversionResult` | **Extraction**: `DocumentConverter.convert(..., page_range=...)` — docling runs layout + OCR + table_structure (+ optional formula enrichment + optional picture VLM) inside dependency |
| `hybrid_server.py:658` | `convert_file` → `_do_convert` | temp PDF path (all pages) | `ConversionResult` | **Extraction**: same pipeline, full document |
| `hybrid_server.py:763` | `profile_file` → `_run` | temp PDF path | per-profile timings JSON | **Extraction** (profiling endpoint `/v1/profile/file`; runs `converter.convert` for base / +picture / +formula profiles) |

### Production — hancom cloud backend

| file:line | function | input | output | role / C2 class |
|---|---|---|---|---|
| `HancomClient.java:130-141` | `convert` | PDF bytes | `HybridResponse` visual-info JSON | **Extraction** orchestrator |
| `HancomClient.java:134` | `convert` → `uploadFile` | PDF bytes | `fileId` | Upload only (not inference) |
| `HancomClient.java:138` | `convert` → `getVisualInfo` | `fileId`; query `engine=pdf_ai_dl&dlaMode=ENABLED&ocrMode=FORCE` | Hancom visual-info JSON | **Extraction**: remote Document AI layout+OCR |

### Production — hancom-ai HOCR SDK backend

| file:line | function | input | output | role / C2 class |
|---|---|---|---|---|
| `HancomAIClient.java:188-257` | `convert` | PDF bytes (+ per-request crop dir) | merged JSON (DLA/OCR, TSR, figure captions) | **Extraction** orchestrator |
| `HancomAIClient.java:207` | `convert` → `callModule` | PDF bytes, module `DOCUMENT_LAYOUT_WITH_OCR` | DLA+OCR page/object JSON | **Extraction**: full-document layout analysis + OCR (once per chunk) |
| `HancomAIClient.java:790-832` | `callModule` | PDF bytes, `OPEN_API_NAME` | HOCR `RESULT` JSON | **HTTP inference primitive** for PDF modules |
| `HancomAIClient.java:496` | `recognizeTableStructures` → `callModuleImage` | table/regionlist PNG crop | TSR cells/HTML JSON | **Extraction**: per-table structure recognition (loop; count = table regions) |
| `HancomAIClient.java:561-605` | `callModuleImage` | PNG bytes, module name | HOCR `RESULT` JSON | **HTTP inference primitive** for image modules |
| `HancomAIClient.java:368` | `captionFigures` → `callImageCaptioning` | figure PNG crop | caption string + confidence | **Extraction**: VLM/image-captioning per figure (loop; count = figure regions) |
| `HancomAIClient.java:748-784` | `callImageCaptioning` | PNG bytes, module `IMAGE_CAPTIONING` | caption JSON | **HTTP inference primitive** for figure captioning |
| `HancomAIClient.java:670-732` | `fetchPageImage` | PDF bytes, page index | PNG via `/support/pdf2img` | **Rendering** (feeds crops; not scored as separate VLM call) |

`convertAsync` on all three clients (`HancomAIClient.java:271`, `DoclingFastServerClient.java:144`, `HancomClient.java:151`) wraps synchronous `convert`; no additional inference path.

### Production — post-backend merge (not model calls)

| file:line | function | input | output | role |
|---|---|---|---|---|
| `HybridDocumentProcessor.java:892-1008` | `enrichBackendResults` | backend + Java-filtered page objects | enriched `IObject`s with StreamInfo / alt text | **Deterministic merge** (`TextSimilarity` stream-vs-OCR at `1215`; author `/Alt` wins over AI caption at `917-944`) |

### Non-production / eval / experiment hits (listed, not production)

| file:line | function | input | output | role / C2 class |
|---|---|---|---|---|
| `scripts/experiments/docling_subprocess_bench.py:92` | main loop | PDF path | timing JSON | **Experiment extraction** (direct `DocumentConverter.convert`) |
| `scripts/experiments/docling_fastapi_bench.py:90` | benchmark loop | PDF path | timing | **Experiment extraction** |
| `scripts/experiments/docling_baseline_bench.py:40` | `convert_pdf` | PDF file | HTTP response from external docling-serve | **Experiment extraction** (external server) |
| `scripts/bench.sh:57-85` | CI wrapper | cloned `opendataloader-bench` | NID/TEDS/MHS corpus means | **Eval-harness wiring** (bench code external; metrics are deterministic fuzzy/structural, no LLM in eval loop) |
| `verification/ci-verify.py:163-200` | Level 2 content checks | output text | pass/fail on `must_contain` substrings | **Deterministic smoke** (not LLM) |
| `verification/ci-verify.py:273-319` | Level 3 compare | baseline vs variant files | byte-identical / must-differ | **Deterministic regression** (not LLM) |
| `java/.../HancomAIClientRequestIdTest.java:49` | test hook | mock PDF bytes | asserts REQUEST_ID | **Test** (mock server) |

No `openai`, `anthropic`, `chat.completions`, `GenerativeModel`, `litellm`, or LLM-as-judge strings in production Java/Python. MCP server (`python/opendataloader-pdf-mcp/src/opendataloader_pdf_mcp/server.py`) calls `opendataloader_pdf.convert(..., hybrid=...)` and inherits the Java paths above; no direct model API in MCP layer.

## Verdict on the claim(s)

**C1 (negative existential — no per-page LLM/VLM verification of already-produced output): CONFIRMED for this repo.**

No production or in-repo eval path sends an **existing** conversion artifact back to an LLM/VLM for per-page/chunk judgment against the source PDF. All model/backend usage is **forward extraction** (PDF/page/crop → structure/text/caption JSON). Post-backend steps compare stream vs OCR text with deterministic `TextSimilarity` (`HybridDocumentProcessor.java:1210-1224`), not an LLM judge. CI (`verification/ci-verify.py`) uses substring and byte-identity checks. Benchmark regression (`scripts/bench.sh` → external opendataloader-bench) uses deterministic NID/TEDS/MHS structural metrics; no LLM in the eval loop (confirmed by prior scan of bench repo; not re-run here).

**C2 (classification):** All production model/AI invocation sites above are **extraction**. None are refinement, eval-harness (in-repo), or verification. Eval-harness classification applies only to the **external** bench invoked by `scripts/bench.sh` (deterministic, no LLM).

## Coverage gaps

None material for production AI paths. Docling's internal step graph (layout model, OCR nets, TableFormer, formula model, SmolVLM inference kernels) lives inside the installed `docling` package; this repo's observable boundaries are `DocumentConverter(...)` construction (`hybrid_server.py:508-511`) and `converter.convert(...)` (`hybrid_server.py:656,658,763`). Every `.java`/`.py` file under `java/.../src/main` and `python/opendataloader-pdf/src` matching the charter search floor was found via `rg`; individual Java unit-test files were not read line-by-line but test-only hooks were captured when matched.

## What could still hide a counterexample

- A dynamically loaded docling plugin or OCR engine registered at runtime but not referenced in this clone's source (charter search floor includes `pipeline(` / `transformers` — none in production code).
- Future/unimplemented backends (`HybridClientFactory.java:99-102` azure/google stubs).
- Behavior inside Hancom HOCR / docling closed-source server binaries not visible in this repo.
- External `opendataloader-bench` clone could add LLM scoring in a newer SHA (out of scope for this repo at `ddd3d8e`; this agent did not re-clone bench).
