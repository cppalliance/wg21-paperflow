# 19b - opendataloader-pdf page routing/coverage and failure semantics

**Claims tested:** C4-adjacent foreign facts (hybrid JAVA vs BACKEND triage, partial_success, per-page failure handling, caller reconciliation)

**Exhaustive:** no (Coverage gaps: `ContentFilterProcessor`, `HiddenTextProcessor`, `HancomClient`, azure/google hybrid stubs if present, Node/Python CLI wrappers beyond `hybrid_server.py` partial_success builder, all schema-transformer element-level skips; production paths in scope are fully enumerated below)

## Method

Repo: `packages/whisker/research/repos/opendataloader-pdf` @ `ddd3d8e9607a525cc3d00d4b05448a10c89c6935`.

Search commands run:

```text
rg -i "JAVA|BACKEND|partial_success|PartialSuccess|fallbackToJava|RouteDecision|triage" --glob "*.java" --line-number
rg -i "skip|unprocessed|failed|failure|pageCount|page_count|shouldProcessPage|pagesToProcess|backendFailedPages|failed_pages" --glob "*.java" --line-number
rg -i "partial_success|failed_pages" --glob "*.py" --line-number
rg -n "shouldProcessPage|mergeResults|createEmptyContents|failFastIfBackendFailedWithoutFallback|getValidPageNumbers" --glob "*.java"
```

Files read in full or in targeted sections:

- `java/opendataloader-pdf-core/src/main/java/org/opendataloader/pdf/hybrid/TriageProcessor.java`
- `java/opendataloader-pdf-core/src/main/java/org/opendataloader/pdf/processors/HybridDocumentProcessor.java`
- `java/opendataloader-pdf-core/src/main/java/org/opendataloader/pdf/processors/DocumentProcessor.java` (extractContents, getValidPageNumbers, processDocument, shouldProcessPage, generateOutputs)
- `java/opendataloader-pdf-core/src/main/java/org/opendataloader/pdf/processors/TaggedDocumentProcessor.java`
- `java/opendataloader-pdf-core/src/main/java/org/opendataloader/pdf/hybrid/DoclingFastServerClient.java` (parseResponse, extractFailedPages)
- `java/opendataloader-pdf-core/src/main/java/org/opendataloader/pdf/hybrid/HybridClient.java` (HybridResponse.failedPages)
- `java/opendataloader-pdf-core/src/main/java/org/opendataloader/pdf/hybrid/TriageLogger.java`
- `java/opendataloader-pdf-core/src/main/java/org/opendataloader/pdf/hybrid/HancomAIClient.java` (caption/TSR failure branches)
- `java/opendataloader-pdf-core/src/main/java/org/opendataloader/pdf/json/JsonWriter.java`
- `java/opendataloader-pdf-cli/src/main/java/org/opendataloader/pdf/cli/CLIMain.java`
- `python/opendataloader-pdf/src/opendataloader_pdf/hybrid_server.py` (lines 117–244, partial_success builder)
- `verification/ci-verify.py` (lines 440–486, hybrid fail-fast contract)

## Inventory

### A. Page selection / intentional skip (not hybrid triage)

| # | File:line | Role / finding |
|---|-----------|----------------|
| A1 | `DocumentProcessor.java:210-234` | `--pages` values outside `[1, pageCount]` logged WARNING and dropped from `pagesToProcess` |
| A2 | `DocumentProcessor.java:236-240` | All requested pages invalid → empty `pagesToProcess` set |
| A3 | `DocumentProcessor.java:505-506` | `shouldProcessPage`: page not in filter → not processed |
| A4 | `DocumentProcessor.java:307-308` | Java-only path: non-selected page gets empty `ArrayList` |
| A5 | `HybridDocumentProcessor.java:245-247` | Empty `pagesToProcess` → `createEmptyContents(totalPages)` (all slots empty, no throw) |
| A6 | `HybridDocumentProcessor.java:510-512` | `filterAllPages`: non-selected pages get empty filtered contents |
| A7 | `HybridDocumentProcessor.java:1425-1426` | `mergeResults`: non-selected pages left untouched (remain empty from init) |
| A8 | `HybridDocumentProcessor.java:1465-1466` | Same `shouldProcessPage` predicate as DocumentProcessor |
| A9 | `TaggedDocumentProcessor.java:44-73` | Struct-tree path skips loops when `!shouldProcessPage` |
| A10 | `TaggedDocumentProcessor.java:149` | `addObjectToContent`: objects on filtered-out pages not added |
| A11 | `CLIMain.java:222-224` | Non-PDF in batch directory silently skipped (exit 0) |
| A12 | `CLIMain.java:229-235` | Invalid PDF inside directory: WARNING + skip (exit 0); direct CLI arg fails |

### B. Hybrid triage routing (JAVA vs BACKEND) — exact conditions

| # | File:line | Role / finding |
|---|-----------|----------------|
| B1 | `HybridDocumentProcessor.java:273-281` | `--hybrid-mode full`: skip triage; every selected page → `TriageDecision.BACKEND` |
| B2 | `HybridDocumentProcessor.java:285-287` | `--hybrid-mode auto` (default): `TriageProcessor.triageAllPages(filteredContents, …)` |
| B3 | `TriageProcessor.java:658-660` | Signal 0: `StaticLayoutContainers.getReplacementCharRatio(page) >= 0.3` → BACKEND |
| B4 | `TriageProcessor.java:664-665` | Signal 1: `signals.hasTableBorder()` → BACKEND |
| B5 | `TriageProcessor.java:669-670` | Signal 2: `signals.hasVectorTableSignal()` → BACKEND |
| B6 | `TriageProcessor.java:674-675` | Signal 3: `signals.hasTextTablePattern()` → BACKEND |
| B7 | `TriageProcessor.java:680-681` | Signal 3.5: `signals.hasLargeImage()` → BACKEND |
| B8 | `TriageProcessor.java:688-690` | Signal 4 (`hasSuspiciousPattern`): **disabled** (commented out) |
| B9 | `TriageProcessor.java:693-694` | Signal 5: `lineToTextRatio > thresholds.lineRatioThreshold` (default 0.3) → BACKEND |
| B10 | `TriageProcessor.java:701-703` | Signal 6 (`alignedLineGroups >= threshold`): **disabled** (commented out) |
| B11 | `TriageProcessor.java:706` | Default: simple content → JAVA |
| B12 | `TriageProcessor.java:722-723` | Null/empty filtered contents → empty signals → default JAVA at B11 |
| B13 | `HybridDocumentProcessor.java:299-300` | Split: `filterByDecision(…, JAVA)` vs `filterByDecision(…, BACKEND)` |
| B14 | `HybridDocumentProcessor.java:256-265` | Phase 0 health check fail + `--hybrid-fallback` → **all pages Java** (`processAllPagesAsJavaFallback`) |
| B15 | `HybridDocumentProcessor.java:256-265` | Phase 0 health check fail, no fallback → throw (whole document fails) |

Triage audit output (routing only, not failure):

| # | File:line | Role / finding |
|---|-----------|----------------|
| T1 | `HybridDocumentProcessor.java:291` | INFO log triage summary |
| T2 | `HybridDocumentProcessor.java:294-295` | If `outputDir != null`, writes `triage.json` via `TriageLogger` |
| T3 | `DocumentProcessor.java:183` | CLI/library path calls 3-arg `processDocument` → **`outputDir` always null** → no `triage.json` in normal runs |
| T4 | `TriageLogger.java:161-185` | `triage.json` records per-page `decision` (JAVA/BACKEND), confidence, signals; summary counts |

### C. Backend partial_success semantics (Docling hybrid server path)

| # | File:line | Role / finding |
|---|-----------|----------------|
| C1 | `hybrid_server.py:197-229` | Server builds `failed_pages` on `partial_success`: union of (a) regex on error messages, (b) gap detection vs expected page range |
| C2 | `hybrid_server.py:219-221` | Gap detection WARNING when no page range/total_pages: boundary failures may be undetectable |
| C3 | `hybrid_server.py:238` | Response always includes `failed_pages` array (possibly empty) |
| C4 | `DoclingFastServerClient.java:207-210` | Backend `status == "failure"` → throw `IOException` (whole request fails) |
| C5 | `DoclingFastServerClient.java:214-218` | `status == "partial_success"` → WARNING log only; **does not throw** |
| C6 | `DoclingFastServerClient.java:231-237` | Parses `failed_pages` (1-indexed) into `HybridResponse` |
| C7 | `DoclingFastServerClient.java:279-291` | Missing/empty `failed_pages` → empty list (even if status were partial_success) |
| C8 | `HybridClient.java:366-384` | `getFailedPages()` / `hasFailedPages()` accessors |
| C9 | `HancomAIClient.java:255-256` | Hancom-ai client always passes `Collections.emptyList()` for failedPages |
| C10 | `HancomClient.java:141` | Hancom client uses constructor without failedPages → empty list |

### D. Per-page backend failure handling in Java orchestrator

| # | File:line | Role / finding |
|---|-----------|----------------|
| D1 | `HybridDocumentProcessor.java:717-724` | Collect `response.getFailedPages()` (1→0 indexed) into `backendFailedPages` |
| D2 | `HybridDocumentProcessor.java:744-745` | Failed pages excluded from backend result map (await Java retry) |
| D3 | `HybridDocumentProcessor.java:760-761` | `page0 >= transformedContents.size()` → store **empty** page list (no throw) |
| D4 | `HybridDocumentProcessor.java:764-772` | Chunk-level `IOException`: all pages in chunk added to `backendFailedPages`, continue next chunk |
| D5 | `HybridDocumentProcessor.java:328-334` | Whole backend path exception + fallback → re-run backend pages on Java |
| D6 | `HybridDocumentProcessor.java:328-334` | Whole backend path exception, no fallback → throw `IOException` |
| D7 | `HybridDocumentProcessor.java:339-349` | Non-empty `backendFailedPages` + `--hybrid-fallback` → Java reprocess failed pages |
| D8 | `HybridDocumentProcessor.java:351-353` | Non-empty `backendFailedPages`, no fallback → `failFastIfBackendFailedWithoutFallback` |
| D9 | `HybridDocumentProcessor.java:483-495` | Fail-fast message: `"Backend processing failed for N page(s) with fallback disabled: pages […]"` (1-indexed list) |
| D10 | `HybridDocumentProcessor.java:583-586` | Java path per-page `catch (Exception)`: WARNING only; **page may ship partial/stale content** |
| D11 | `HybridDocumentProcessor.java:1435` | `mergeResults`: if page neither in javaResults nor backendResults → **empty list, no error** |

### E. Document-level / non-hybrid failure

| # | File:line | Role / finding |
|---|-----------|----------------|
| E1 | `DocumentProcessor.java:404-405` | Java parallel pipeline unhandled exception → `IOException("Parallel page processing failed")` |
| E2 | `CLIMain.java:246-248` | Processing exception → SEVERE log, exit 1 |
| E3 | `StaticLayoutContainers.java:99-102` | ContrastRatioConsumer init fail → image extraction + hidden-text filtering skipped document-wide (SEVERE log) |

### F. Hancom-ai enrichment partial failures (page still "processed")

| # | File:line | Role / finding |
|---|-----------|----------------|
| F1 | `HancomAIClient.java:334-336` | Page image fetch fail → skip captioning for that page (WARNING) |
| F2 | `HancomAIClient.java:387-388` | Figure caption fail → skip figure (WARNING) |
| F3 | `HancomAIClient.java:455-456` | TSR page image fetch fail → skip TSR for page (WARNING) |
| F4 | `HancomAIClient.java:530` | TSR module fail → WARNING; page content still emitted from DLA |

## Verdict on the claim(s)

**Hybrid JAVA vs BACKEND triage:** In `--hybrid-mode auto`, every selected page is classified by `TriageProcessor.classifyPage` using signals B3–B11; default is JAVA. In `--hybrid-mode full`, triage is bypassed and all selected pages go BACKEND (B1). Routing is conservative toward BACKEND for table-like signals; two signals are explicitly disabled (B8, B10).

**partial_success semantics:** Only the Docling fast-server path propagates per-page failure lists. Server (`hybrid_server.py:197-238`) computes `failed_pages`; Java client (`DoclingFastServerClient.java:214-237`) accepts partial_success without throwing and passes failed pages to `HybridDocumentProcessor`. With `--hybrid-fallback`, failed backend pages are reprocessed on Java (D7); without fallback, processing aborts with an `IOException` listing 1-indexed pages (D8–D9). Hancom/hancom-ai clients do not surface partial_success page lists (C9–C10).

**Caller reconciliation vs source page count:**

| Source | What it records |
|--------|-----------------|
| JSON output | `numberOfPages` = full PDF page count (`JsonWriter.java:121`); flat `kids` array iterates all pages but emits only non-empty IObjects per page (`JsonWriter.java:87-96`) |
| Exit code | 0 unless document-level exception or fail-fast (D8–D9, E2) |
| Logs | partial_success page lists at WARNING (`HybridDocumentProcessor.java:344-352`, `DoclingFastServerClient.java:216-217`) |
| `triage.json` | Per-page JAVA/BACKEND routing only; **not written on CLI path** (T3) |
| Structured per-page failure field in JSON | **NOT VERIFIED** — no page-level status in primary JSON schema |

**Reconciliation verdict:** Caller can compare `numberOfPages` to distinct page numbers appearing in output elements, but **cannot reliably distinguish** (a) intentionally skipped pages (`--pages`), (b) legitimately empty PDF pages, (c) silent processing failures (D10, D11, D3), or (d) legacy/missing `failed_pages` (C7). Fail-closed reconciliation requires `--hybrid-fallback` off + hybrid backend partial_success + non-zero exit (D8–D9), or log scraping.

## Coverage gaps

- `ContentFilterProcessor`, `HiddenTextProcessor`, image/base64 skip paths (`Base64ImageUtils.java:35-45`) not line-enumerated.
- `HancomClient`, azure/google hybrid client implementations not read (only Docling + Hancom-ai partial_success plumbing verified).
- Node.js bindings and Python high-level `process()` wrapper not read.
- Schema-transformer element-level skips (missing provenance/bbox) affect page content density but were not exhaustively listed.

## What could still hide a counterexample

- A hybrid backend other than docling-fast that returns partial results without populating `HybridResponse.failedPages`.
- Filter/preprocessing paths that drop page content before triage without logging at page granularity.
- Library callers invoking `HybridDocumentProcessor.processDocument(…, outputDir)` and treating `triage.json` as coverage proof while ignoring backend partial_success handling.
