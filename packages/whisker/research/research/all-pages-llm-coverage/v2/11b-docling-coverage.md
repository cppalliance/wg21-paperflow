# 11b - docling page iteration and failure semantics (StandardPdfPipeline + VlmPipeline)

**Claims tested:** None (C1–C3 are whisker-internal; this report supplies C4-adjacent foreign facts on docling page coverage, status semantics, and confidence scoring)

**Exhaustive:** yes (all production code paths in `StandardPdfPipeline`, `VlmPipeline`, shared `PaginatedPipeline`/`BasePipeline`, confidence writers, and pre-pipeline policy gates at pinned SHA `fbd39b8`; experimental/service-client paths listed under Coverage gaps only)

## Method

Repo: `packages/whisker/research/repos/docling` @ `fbd39b870859afbae21645ebe0e417109777da5a`.

Search commands run:

```text
rg -n "ConversionStatus|PARTIAL_SUCCESS|FAILURE|SUCCESS|SKIPPED" --type py -g "!tests/**" docling
rg -n "page_batch_size|document_timeout|failed_page|ErrorItem|FailureCategory|page\.size is None|is_failed|missing_page" --type py -g "!tests/**" docling
rg -n "confidence\.pages|table_score|layout_score|ocr_score|parse_score" --type py -g "!tests/**" docling
rg -n "conv_res\.errors\.append" docling --type py
rg -n "page_range|max_num_pages" docling --type py -g "!tests/**" -g "!docs/**"
rg -n "VlmPipeline|StandardPdfPipeline|LegacyStandardPdfPipeline" docling --type py
rg -n "settings\.perf\.page_batch_size|chunkify" docling --type py
```

Files read in full:

- `docling/pipeline/base_pipeline.py`
- `docling/pipeline/vlm_pipeline.py`
- `docling/models/stages/vlm_convert/vlm_convert_model.py`
- `docling/models/stages/page_preprocessing/page_preprocessing_model.py`
- `docling/models/stages/page_assemble/page_assemble_model.py`
- `docling/datamodel/settings.py`
- `docling/pipeline/standard_pdf_pipeline.py` (lines 1–1155)
- `docling/pipeline/legacy_standard_pdf_pipeline.py` (lines 1–282)
- `docling/datamodel/base_models.py` (lines 85–296, 539–674)
- `docling/datamodel/document.py` (lines 194–217, 692–740)
- `docling/document_converter.py` (lines 195–203, 692–740)
- `docling/models/stages/layout/layout_model.py` (`predict_layout`)
- `docling/models/stages/layout/layout_object_detection_model.py` (`predict_layout`)
- `docling/models/stages/ocr/kserve_v2_ocr_model.py` (lines 240–282)
- `docling/cli/main.py` (lines 885–947, 1193–1219)

## Inventory

### ConversionStatus and FailureCategory definitions

| # | File:line | Role |
|---|-----------|------|
| 1 | `docling/datamodel/base_models.py:85-91` | `ConversionStatus` enum: `PENDING`, `STARTED`, `FAILURE`, `SUCCESS`, `PARTIAL_SUCCESS`, `SKIPPED` |
| 2 | `docling/datamodel/base_models.py:256-277` | `FailureCategory` enum used on `ErrorItem` (`TIMEOUT`, `BACKEND_FAILURE`, `INFERENCE_FAILURE`, `POLICY`, etc.) |
| 3 | `docling/datamodel/base_models.py:280-296` | `ErrorItem` schema; optional `page_no` (1-indexed) for page-scoped errors |

### Pre-pipeline policy: pages never enqueued

| # | File:line | Role |
|---|-----------|------|
| 4 | `docling/datamodel/document.py:200-207` | `max_num_pages` exceeded → `InputDocument.valid=False`, `FailureCategory.POLICY`; converter returns document-level `FAILURE` (`document_converter.py:736-739`) |
| 5 | `docling/datamodel/document.py:209-217` | `page_range[0] > page_count` → invalid input, `FAILURE` |
| 6 | `docling/pipeline/base_pipeline.py:256-259` | **PaginatedPipeline (VlmPipeline):** only pages where `(start_page-1) <= i <= (end_page-1)` appended to `conv_res.pages` |
| 7 | `docling/pipeline/standard_pdf_pipeline.py:755-762` | **StandardPdfPipeline:** `_get_expected_page_nos` same `page_range` ∩ `[1, page_count]` |
| 8 | `docling/pipeline/standard_pdf_pipeline.py:784-786` | Empty `expected_page_nos` → `ConversionStatus.FAILURE`, no pages processed |
| 9 | `docling/document_converter.py:708-710` | Disallowed format → `ConversionStatus.SKIPPED` (whole document, not per-page) |

### Shared `BasePipeline.execute` status normalization

| # | File:line | Role |
|---|-----------|------|
| 10 | `docling/pipeline/base_pipeline.py:83-87` | After `_determine_status`, if status is `SUCCESS` but `conv_res.errors` non-empty → downgrade to `PARTIAL_SUCCESS` |
| 11 | `docling/pipeline/base_pipeline.py:88-98` | Unhandled exception in `execute` → `FAILURE`; append `ErrorItem` when `raises_on_error=False`, else re-raise |

### PaginatedPipeline page iteration (`page_batch_size`, timeout, filtering) — used by **VlmPipeline** and deprecated **LegacyStandardPdfPipeline**

| # | File:line | Role |
|---|-----------|------|
| 12 | `docling/datamodel/settings.py:32` | Default `page_batch_size=4` |
| 13 | `docling/pipeline/base_pipeline.py:264-266` | `chunkify(conv_res.pages, settings.perf.page_batch_size)` — batching only affects scheduling, not which pages exist |
| 14 | `docling/pipeline/base_pipeline.py:270-275` | Per batch: `initialize_page` then `_apply_on_pages` (runs `build_pipe` models) |
| 15 | `docling/pipeline/base_pipeline.py:294-313` | `document_timeout`: append document-scoped `ErrorItem` (`FailureCategory.TIMEOUT`), set `PARTIAL_SUCCESS`, **break** (later batches never run) |
| 16 | `docling/pipeline/base_pipeline.py:319-328` | Unhandled exception in `_build_document` → set `FAILURE`, log, **re-raise** (entire document aborts; no per-page recovery) |
| 17 | `docling/pipeline/base_pipeline.py:330-339` | **Post-build filter:** drop pages where `page.size is None` (timeout/init failures); log count only, **no `ErrorItem` per dropped page** |
| 18 | `docling/pipeline/base_pipeline.py:353-372` | `_determine_status`: for each remaining page, if `_backend is None` or `not is_valid()` → append `BACKEND_FAILURE` `ErrorItem`, set `PARTIAL_SUCCESS` |
| 19 | `docling/cli/main.py:947` | CLI sets `settings.perf.page_batch_size` (applies to PaginatedPipeline paths only) |

**`page_batch_size` on errors (PaginatedPipeline):** batching does not skip pages on success path. On stage exception (16), the **whole document** fails, not just the batch. On timeout (15), remaining **batches** are never submitted; already-finished pages kept. `page_batch_size` does not change error semantics beyond batch scheduling.

### StandardPdfPipeline — page producer and threaded stages (does **not** use `page_batch_size`)

| # | File:line | Role |
|---|-----------|------|
| 20 | `docling/document_converter.py:200-201` | Default PDF pipeline class: `StandardPdfPipeline` |
| 21 | `docling/pipeline/standard_pdf_pipeline.py:789-792` | Create `Page` shell for every `expected_page_nos` entry |
| 22 | `docling/pipeline/standard_pdf_pipeline.py:742-753` | `_iter_requested_page_backends`: random-access `load_page` or sequential `iter_pages` filtered to expected set |
| 23 | `docling/pipeline/standard_pdf_pipeline.py:816-818` | Backend page_no not in `page_by_no` → `continue` (skip enqueue; page never enters pipeline) |
| 24 | `docling/pipeline/standard_pdf_pipeline.py:820-825` | `get_size()` exception: re-raise if backend still `is_valid()` |
| 25 | `docling/pipeline/standard_pdf_pipeline.py:826-834` | Producer queue `put` returns False → `break` (stop enqueueing; pages not yet queued) |
| 26 | `docling/pipeline/standard_pdf_pipeline.py:835-839` | Producer thread exception → logged; queue closed in `finally` |
| 27 | `docling/pipeline/standard_pdf_pipeline.py:847-863` | `document_timeout` during drain → `timeout_exceeded=True`, add `run_id` to `timed_out_run_ids`, close input queue, **break drain loop** (in-flight work not awaited) |
| 28 | `docling/pipeline/standard_pdf_pipeline.py:870-875` | Output item `is_failed` or `error` → append to `proc.failed_pages`; else append to `proc.pages` |
| 29 | `docling/pipeline/standard_pdf_pipeline.py:877-904` | Output queue closed early with missing expected pages → extend `failed_pages` with `FailureCategory.UNKNOWN` |
| 30 | `docling/pipeline/standard_pdf_pipeline.py:906-925` | After timeout: every expected page not in success∪failed → `failed_pages` with `FailureCategory.TIMEOUT` |
| 31 | `docling/pipeline/standard_pdf_pipeline.py:296-313` | `ThreadedPipelineStage._process_batch`: if `run_id in timed_out_run_ids` → mark items failed, `FailureCategory.TIMEOUT`, pass through without model call |
| 32 | `docling/pipeline/standard_pdf_pipeline.py:324-338` | Batch item `payload is None` → `is_failed`, `FailureCategory.UNKNOWN` |
| 33 | `docling/pipeline/standard_pdf_pipeline.py:355-358` | Model returned wrong page count → `RuntimeError` → caught at 368, **entire good subset of batch** marked failed |
| 34 | `docling/pipeline/standard_pdf_pipeline.py:368-384` | Model exception → mark all non-failed items in batch `is_failed`; category from `STAGE_FAILURE_CATEGORY` (`ocr`/`layout`/`table`/`assemble` → `INFERENCE_FAILURE`) or `UNKNOWN` |
| 35 | `docling/pipeline/standard_pdf_pipeline.py:393-394` | Output queue closed while emitting → error log (item may be lost) |
| 36 | `docling/pipeline/standard_pdf_pipeline.py:426-441` | `PreprocessThreadedStage`: timeout run_id path (same as 31) |
| 37 | `docling/pipeline/standard_pdf_pipeline.py:454-465` | Preprocess: `payload is None` → failed |
| 38 | `docling/pipeline/standard_pdf_pipeline.py:466-479` | Preprocess: `page._backend is None` → failed |
| 39 | `docling/pipeline/standard_pdf_pipeline.py:480-491` | Preprocess: `not page._backend.is_valid()` → `BACKEND_FAILURE` |
| 40 | `docling/pipeline/standard_pdf_pipeline.py:530-548` | Preprocess model exception → failed all valid pages in batch, `FailureCategory.UNKNOWN` |
| 41 | `docling/pipeline/standard_pdf_pipeline.py:947-951` | `_integrate_results`: **remove failed pages from `conv_res.pages`** (only successes kept in runtime page list) |
| 42 | `docling/pipeline/standard_pdf_pipeline.py:953-965` | Append each `proc.failed_pages` entry to `conv_res.errors` (preserve `failure` `ErrorItem` when present) |
| 43 | `docling/pipeline/standard_pdf_pipeline.py:966-985` | Set status: timeout → `PARTIAL_SUCCESS` + document-scoped TIMEOUT error; all failed → `FAILURE`; partial → `PARTIAL_SUCCESS`; else `SUCCESS` |
| 44 | `docling/pipeline/standard_pdf_pipeline.py:1098-1134` | `_add_failed_pages_to_document`: insert empty `PageItem` placeholders for expected pages missing from `conv_res.document.pages` (preserves page numbering in exports) |
| 45 | `docling/pipeline/standard_pdf_pipeline.py:1145-1146` | `_determine_status` returns `conv_res.status` already set in `_integrate_results` (no extra backend scan) |

**StandardPdfPipeline batch sizes on errors:** uses per-stage `ocr_batch_size`, `layout_batch_size`, `table_batch_size` (`standard_pdf_pipeline.py:691-713`), not `page_batch_size`. On model error (34), **only that batch's pages** fail; pipeline continues for other batches unless timeout (27) closes input.

### StandardPdfPipeline — stage-level partial output (page continues, may lack content/scores)

| # | File:line | Role |
|---|-----------|------|
| 46 | `docling/models/stages/page_preprocessing/page_preprocessing_model.py:42-43` | Invalid backend → yield page unchanged (no `parse_score`) |
| 47 | `docling/models/stages/page_preprocessing/page_preprocessing_model.py:47-48` | `skip_cell_extraction=True` → skip `_parse_page_cells` (no `parse_score`) |
| 48 | `docling/models/stages/layout/layout_model.py:168-169` | Invalid backend excluded from layout batch |
| 49 | `docling/models/stages/layout/layout_model.py:191-195` | Invalid backend → empty `LayoutPrediction`, no confidence write |
| 50 | `docling/models/stages/layout/layout_object_detection_model.py:90-94` | Invalid backend → empty layout |
| 51 | `docling/models/stages/layout/layout_object_detection_model.py:96-101` | `page_image is None` → empty layout, no confidence write |
| 52 | `docling/models/stages/page_assemble/page_assemble_model.py:158-159` | Invalid backend → yield without `page.assembled` |
| 53 | `docling/models/stages/ocr/kserve_v2_ocr_model.py:251-270` | Per-rectangle OCR failure → append page-scoped `INFERENCE_FAILURE`, **continue** other rects; page still yields |
| 54 | `docling/pipeline/standard_pdf_pipeline.py:1000-1004` | Assembly: only pages with `p.assembled` contribute elements (failed/unassembled pages contribute nothing) |

### VlmPipeline — initialization, VLM convert, assembly

| # | File:line | Role |
|---|-----------|------|
| 55 | `docling/cli/main.py:1193-1214` | CLI `--pipeline vlm` selects `VlmPipeline` + `VlmConvertModel` |
| 56 | `docling/pipeline/vlm_pipeline.py:207-222` | `initialize_page`: load backend; set `page.size` only when backend valid |
| 57 | `docling/pipeline/vlm_pipeline.py:212-214` | `ThreadedDoclingParseDocumentBackend` → `RuntimeError` (unsupported; aborts build) |
| 58 | `docling/models/stages/vlm_convert/vlm_convert_model.py:142-144` | Stage disabled → pass pages through unchanged |
| 59 | `docling/models/stages/vlm_convert/vlm_convert_model.py:164-168` | `page.get_image()` returns None → skip VLM for that page (no `vlm_response`) |
| 60 | `docling/models/stages/vlm_convert/vlm_convert_model.py:174-176` | No valid images in batch → **return without yielding** (generator produces zero outputs for that batch) |
| 61 | `docling/models/stages/vlm_convert/vlm_convert_model.py:208-210` | VLM engine exception → log and **re-raise** (triggers PaginatedPipeline 16) |
| 62 | `docling/models/stages/vlm_convert/vlm_convert_model.py:212-213` | On success: `yield from page_list` (includes image-skipped pages without predictions) |
| 63 | `docling/pipeline/vlm_pipeline.py:236-274` | `_determine_status`: `vlm_response is None` → `INFERENCE_FAILURE` + `PARTIAL_SUCCESS`; `stop_reason` in `{LENGTH, CONTENT_FILTERED}` → same |
| 64 | `docling/pipeline/vlm_pipeline.py:378-388` | DOCLANG: no `<doclang>` fragment → `INFERENCE_FAILURE`, `PARTIAL_SUCCESS`, empty page doc |
| 65 | `docling/pipeline/vlm_pipeline.py:418-428` | DOCLANG deserialize exception → `BACKEND_FAILURE`, `PARTIAL_SUCCESS`, empty placeholder page doc |
| 66 | `docling/pipeline/vlm_pipeline.py:367-394` | `_turn_doclang_into_doc` iterates **all** `conv_res.pages` (after filter 17), appends empty doclang for missing fragments |
| 67 | `docling/pipeline/vlm_pipeline.py:446-457` | `_turn_dt_into_doc` iterates all pages; missing `vlm_response` → empty doctags string (no error here; errors from 63) |

**VlmPipeline and confidence:** no confidence writes or document-level aggregation in `vlm_pipeline.py`. Per-page confidence dict typically empty unless populated elsewhere.

### Confidence score computation and aggregation

| # | File:line | Role |
|---|-----------|------|
| 68 | `docling/datamodel/base_models.py:539-543` | `PageConfidenceScores`: `parse_score`, `layout_score`, `table_score`, `ocr_score` default `np.nan` |
| 69 | `docling/datamodel/base_models.py:609-612` | `ConfidenceReport.pages`: `defaultdict(PageConfidenceScores)` — entries created **only on keyed write** |
| 70 | `docling/models/stages/page_preprocessing/page_preprocessing_model.py:75-89` | **`parse_score`:** 10th percentile (`np.nanquantile`, q=0.10) of per-cell `rate_text_quality` scores |
| 71 | `docling/models/stages/page_preprocessing/page_preprocessing_model.py:120-145` | `rate_text_quality`: hard 0.0 on glyph/`/G`/garbage patterns; else penalty for fragmented words |
| 72 | `docling/models/stages/layout/layout_model.py:233-239` | **`layout_score`:** mean cluster confidence; **`ocr_score`:** mean OCR cell confidence (layout_model path) |
| 73 | `docling/models/stages/layout/layout_object_detection_model.py:125-138` | Alternate layout backend: `layout_score` mean or 0.0 if no clusters; `ocr_score` mean if OCR cells exist |
| 74 | `docling/pipeline/standard_pdf_pipeline.py:1068-1087` | **Document aggregation (StandardPdfPipeline):** `layout_score`/`ocr_score`/`table_score` = `nanmean` of page values; `parse_score` = `nanquantile` q=0.1 across pages |
| 75 | `docling/pipeline/legacy_standard_pdf_pipeline.py:251-271` | Same aggregation formulas as 74 (Legacy pipeline) |
| 76 | `docling/datamodel/base_models.py:650-674` | Document `ConfidenceReport.mean_score` / `low_score`: `nanmean` of per-page `mean_score` / `low_score` when `pages` non-empty |
| 77 | NOT FOUND | **`table_score` per-page:** no production assignment to `conv_res.confidence.pages[...].table_score` anywhere in repo; page-level `table_score` stays `NaN`; doc-level aggregates NaN-only slices |

### Pages missing from confidence report

| # | Finding | Evidence |
|---|---------|----------|
| 78 | Pages never reaching preprocess/layout never get a dict entry | `defaultdict` only on write (`base_models.py:609-612`); no pre-seeding over `expected_page_nos` |
| 79 | Timeout/unprocessed pages may have zero confidence keys | Timeout before preprocess (`standard_pdf_pipeline.py:906-925`); Paginated filter before scores (`base_pipeline.py:330-339`) |
| 80 | Failed pages removed from `conv_res.pages` may still appear in `confidence.pages` if partially processed | Writes happen on shared `conv_res` during stages before `_integrate_results` (`standard_pdf_pipeline.py:947-951` vs stage writes 70-73) |
| 81 | VlmPipeline produces no confidence page entries by default | No writers in `vlm_pipeline.py` or `vlm_convert_model.py` |
| 82 | `table_score` never populated at page level | See 77; doc-level `table_score` is mean of all-NaN |

## Verdict on the claim(s)

**PARTIALLY (docling extraction coverage vs verification):** Within configured `page_range`, both pipelines architecturally iterate expected pages. **StandardPdfPipeline** records per-page failures in `conv_res.errors`, sets `PARTIAL_SUCCESS`/`FAILURE`, and inserts placeholder `PageItem`s for failed pages (`standard_pdf_pipeline.py:1098-1134`). **VlmPipeline** records missing/truncated VLM output per page (`vlm_pipeline.py:247-272`) but **drops** init-failed pages from `conv_res.pages` without `ErrorItem` (`base_pipeline.py:330-339`) and does not add failed-page placeholders to the document. **`page_batch_size`** affects only PaginatedPipeline batch scheduling; it does not skip pages on the happy path (`base_pipeline.py:264-266`). Confidence scores are deterministic post-hoc heuristics on the standard path only; they are not LLM verification and pages can be absent from `confidence.pages` (78–82).

## Coverage gaps

- `docling/experimental/pipeline/threaded_layout_vlm_pipeline.py` (experimental VLM variant; not default CLI/API production path).
- Individual OCR implementations beyond `kserve_v2_ocr_model.py` (standard path uses factory-selected OCR; grep shows no other `conv_res.errors.append` in OCR models).
- VLM legacy model classes (`ApiVlmModel`, `HuggingFaceTransformersVlmModel`, etc.) when CLI preset uses deprecated `InlineVlmOptions`/`ApiVlmOptions` (`vlm_pipeline.py:134-205`).
- Remote service client rehydration paths (`docling/service_client/client.py`).
- Tests, docs examples, perf scripts.

## What could still hide a counterexample

- OCR/layout/table model implementation selected at runtime via factories but not grep-matched for error append patterns.
- Export-layer behavior that omits placeholder pages despite `PageItem` insertion (not traced in this report).
- Operator ignoring `PARTIAL_SUCCESS` and `errors[]` while trusting aggregate confidence grades (document-level score can look acceptable when many pages failed: `standard_pdf_pipeline.py:1068-1087` + timeout path `966-979`).
