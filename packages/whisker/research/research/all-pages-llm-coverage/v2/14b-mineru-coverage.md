# 14b - MinerU page coverage and failure semantics

**Claims tested:** C4 (decision-critical foreign facts: page coverage / silent loss)
**Exhaustive:** no (see Coverage gaps)

## Method

Repo: `packages/whisker/research/repos/MinerU` at SHA `3e60291846cb7c3bf8fe7f4f16238f4fc6cce491` (matches `research/all-pages-llm-coverage/00-baseline.md`).

Files read in full:

- `mineru/backend/vlm/model_output_to_middle_json.py`
- `mineru/backend/pipeline/model_json_to_middle_json.py`
- `mineru/backend/hybrid/hybrid_model_output_to_middle_json.py`
- `mineru/backend/office/model_output_to_middle_json.py`
- `mineru/backend/vlm/vlm_analyze.py`
- `mineru/backend/pipeline/pipeline_analyze.py`
- `mineru/backend/hybrid/hybrid_analyze.py`
- `mineru/backend/pipeline/batch_analyze.py`
- `mineru/cli/common.py`
- `mineru/utils/pdf_image_tools.py`
- `mineru/utils/pdfium_guard.py`

Partial reads (targeted sections): `vlm_magic_model.py`, `pipeline_magic_model.py`, `hybrid_magic_model.py`, `vlm_middle_json_mkcontent.py`, `pipeline_middle_json_mkcontent.py`, `office/mkcontent/output_builders.py`, `span_pre_proc.py`, `html_image_utils.py`.

Search commands:

```text
rg -l "model_output_to_middle_json|middle_json" --type py
rg -n "page_info is None|pdf_info\.append|zip\(.*model|zip\(.*images|batch_two_step|batch_extract|broken_page|loadable_page|discarded_blocks|_prune_empty|span\['content'\] = ''" mineru --type py -g "!tests/**"
rg -n "continue|skip|empty|page_count|page_idx|start_page_id|end_page_id|if not paras" mineru/backend mineru/cli/common.py mineru/utils/pdf_image_tools.py mineru/utils/pdfium_guard.py mineru/utils/span_pre_proc.py --type py
git rev-parse HEAD  # 3e60291846cb7c3bf8fe7f4f16238f4fc6cce491
```

## Inventory

Each row is one code path where a page can be skipped, dropped from the working PDF, omitted from output lists, or left with empty/absent content. `zip(A,B)` means Python truncates to the shorter iterable with no error.

### A. PDF input: pages removed before inference

| # | file:line | Role |
|---|---|---|
| A1 | `mineru/cli/common.py:686-714` | `do_parse` accepts `start_page_id` / `end_page_id`; `_prepare_pdf_bytes` rewrites PDF bytes to that slice only. |
| A2 | `mineru/cli/common.py:778-808` | Same slice rewrite in `aio_do_parse`. |
| A3 | `mineru/cli/common.py:218-234` | `convert_pdf_bytes_to_bytes` fallback: `get_loadable_pdfium_page_indices` drops `broken_page_indices`; rewrite uses `page_indices=loadable_page_indices` only. Logs warning, no structured skip record in output. |
| A4 | `mineru/cli/common.py:223-228` | If no loadable pages in range, returns original bytes unchanged (caller may still fail later). |
| A5 | `mineru/utils/pdfium_guard.py:98-99` | Per-page probe: exception on `pdf_doc[page_index].get_size()` adds index to `broken_page_indices`. |
| A6 | `mineru/utils/pdfium_guard.py:86-87` | `normalized_start_page_id > normalized_end_page_id` returns `[], []` (no pages). |
| A7 | `mineru/utils/pdfium_guard.py:81-82` | `total_page_count == 0` returns empty index lists. |
| A8 | `mineru/utils/pdfium_guard.py:125-134` | `rewrite_pdf_bytes_with_pdfium` with explicit `page_indices` copies only that subset; out-of-range indices filtered silently. |
| A9 | `mineru/utils/pdf_image_tools.py:275-276` | `_load_images_from_pdf_bytes_range`: `end_page_id < start_page_id` returns `[]` (zero images for window). |

### B. Middle-json assembly: page slot loss or empty page record

| # | file:line | Role |
|---|---|---|
| B1 | `mineru/backend/vlm/model_output_to_middle_json.py:92-101` | `append_page_blocks_to_middle_json`: `zip(model_output_blocks_list, images_list)`; if VLM batch returns fewer block lists than images, trailing pages never appended. |
| B2 | `mineru/backend/pipeline/model_json_to_middle_json.py:82-102` | `append_page_model_infos_to_middle_json`: same `zip` truncation; `page_info is None` branch (96-99) substitutes empty `preproc_blocks` but still appends one `pdf_info` entry. |
| B3 | `mineru/backend/pipeline/model_json_to_middle_json.py:119-122` | `append_batch_results_to_middle_json`: `zip(images_list, batch_results)` pairs layout output to images; shorter `batch_results` drops tail pages from `page_model_infos`. |
| B4 | `mineru/backend/hybrid/hybrid_model_output_to_middle_json.py:202-220` | `append_page_results_to_middle_json`: `zip(model_list, images_list)` truncation. |
| B5 | `mineru/backend/office/model_output_to_middle_json.py:128-130` | One `pdf_info` entry per `model_output_blocks_list` element only; no PDF page count cross-check. |
| B6 | `mineru/backend/vlm/vlm_analyze.py:479-500` | `window_results = predictor.batch_two_step_extract(...)` then append; no `len(window_results) == len(images_pil_list)` guard before B1. |
| B7 | `mineru/backend/vlm/vlm_analyze.py:578-599` | Async path: same as B6. |
| B8 | `mineru/backend/hybrid/hybrid_analyze.py:981-1060` | `batch_extract_with_layout` / `batch_two_step_extract` then append; no output-length guard before B4. |
| B9 | `mineru/backend/hybrid/hybrid_analyze.py:1190-1274` | Async hybrid: same as B8. |
| B10 | `mineru/backend/pipeline/pipeline_analyze.py:149-154` | `_emit_zero_page_contexts`: `page_count == 0` finalizes with empty `pdf_info`. |
| B11 | `mineru/backend/pipeline/pipeline_analyze.py:199-205` | `total_pages == 0` early return after emitting zero-page contexts. |
| B12 | `mineru/backend/pipeline/pipeline_analyze.py:287-288` | `result_slice = batch_results[result_offset: result_offset + take_count]`; if `batch_results` shorter than accumulated `take_count`, slice is short (partial window). |

### C. Per-page content emptied (page slot may exist)

| # | file:line | Role |
|---|---|---|
| C1 | `mineru/backend/pipeline/model_json_to_middle_json.py:96-99` | Empty-page fallback: `make_page_info_dict([], page_index, page_w, page_h, [])`. |
| C2 | `mineru/backend/pipeline/model_json_to_middle_json.py:185-193` | `_apply_post_ocr`: score `<= OcrConfidence.min_confidence` and no fallback sets `span['content']=''`, `score=0.0`. |
| C3 | `mineru/backend/pipeline/model_json_to_middle_json.py:189-190` | `_restore_post_ocr_fallback(span)` on low OCR score preserves prior content (not empty). |
| C4 | `mineru/backend/hybrid/hybrid_model_output_to_middle_json.py:154-162` | Hybrid `_apply_post_ocr`: same empty-span path as C2/C3. |
| C5 | `mineru/utils/span_pre_proc.py:54-62` | `page_char_count > MAX_NATIVE_TEXT_CHARS_PER_PAGE` reroutes spans to post-OCR (`_prepare_post_ocr_spans`). |
| C6 | `mineru/utils/span_pre_proc.py:152-157` | Low contrast span: removed from `spans` list (dropped from page text). |
| C7 | `mineru/utils/span_pre_proc.py:159` | Post-OCR candidate: `span['content']=''` before deferred OCR. |
| C8 | `mineru/utils/span_pre_proc.py:550` | `chars_to_content`: zero chars after filter sets `span['content']=''`. |
| C9 | `mineru/backend/pipeline/batch_analyze.py:166-179` | `_prune_empty_ocr_text_blocks`: removes `ocr_text` layout items with blank `text` when `ocr_enable`. |
| C10 | `mineru/backend/pipeline/batch_analyze.py:897-919` | OCR rec: low score / heuristic removes layout item from page `layout_res`. |
| C11 | `mineru/backend/pipeline/batch_analyze.py:933-970` | Seal OCR: empty crop / empty result leaves `layout_res_item["text"]=""` or skips enrichment. |
| C12 | `mineru/backend/pipeline/batch_analyze.py:402-403` | `_extract_table_inline_objects`: removes absorbed inline image/formula items from page `layout_res`. |
| C13 | `mineru/backend/pipeline/batch_analyze.py:463-465` | `formula_enable=False`: strips all `inline_formula` labels from each page layout. |
| C14 | `mineru/backend/pipeline/pipeline_magic_model.py:307-311` | `__fix_axis`: deletes layout dets with width or height `<= 2` px from page model. |
| C15 | `mineru/backend/pipeline/pipeline_magic_model.py:203-210` | Header/footer/page_number/aside/page_footnote blocks moved to `discarded_blocks` (excluded from `preproc_blocks`). |
| C16 | `mineru/backend/vlm/vlm_magic_model.py:60-63` | Invalid VLM block JSON: logged warning, block skipped (missing from page). |
| C17 | `mineru/backend/vlm/vlm_magic_model.py:110-112` | Missing text `content` coerced to `""`. |
| C18 | `mineru/backend/vlm/vlm_magic_model.py:265-272` | Header/footer/page_number/aside/page_footnote to `discarded_blocks`. |
| C19 | `mineru/backend/hybrid/hybrid_magic_model.py:116-119` | Invalid block: skip (same pattern as C16). |
| C20 | `mineru/backend/hybrid/hybrid_magic_model.py:345-367` | Discarded block types to `discarded_blocks`. |
| C21 | `mineru/backend/hybrid/hybrid_analyze.py:374-388` | `_build_medium_vlm_layout_blocks`: unmapped label or invalid bbox skips layout block for VLM extract. |
| C22 | `mineru/backend/hybrid/hybrid_analyze.py:489-516` | `_filter_inline_formulas_inside_containers`: removes inline formulas inside table/image/chart/display_formula from page layout. |
| C23 | `mineru/backend/hybrid/hybrid_analyze.py:182-188` | `ocr_det`: non-candidate or degenerate bbox `continue` (no OCR lines for that region). |
| C24 | `mineru/backend/hybrid/hybrid_analyze.py:805` | VLM-OCR sidecar: `_build_ocr_text_model_item(..., keep_text=False)` emits empty `text` hints. |
| C25 | `mineru/backend/utils/html_image_utils.py:39` | Unrecognized vector image on page: skip inline image replacement. |
| C26 | `mineru/backend/utils/html_image_utils.py:80` | Unrecognized base64 image on page: skip. |

### D. Final markdown / content-list: page omitted from rendered output

| # | file:line | Role |
|---|---|---|
| D1 | `mineru/backend/vlm/vlm_middle_json_mkcontent.py:907-908` | `union_make` MM_MD/NLP_MD: `if not paras_of_layout: continue` (page absent from markdown string). |
| D2 | `mineru/backend/vlm/vlm_middle_json_mkcontent.py:913-914` | CONTENT_LIST: skip page when no layout+discarded blocks. |
| D3 | `mineru/backend/vlm/vlm_middle_json_mkcontent.py:920-926` | CONTENT_LIST_V2: always appends `page_contents` (may be `[]` for empty page). |
| D4 | `mineru/backend/pipeline/pipeline_middle_json_mkcontent.py:979-980` | Pipeline MM_MD: same skip as D1. |
| D5 | `mineru/backend/pipeline/pipeline_middle_json_mkcontent.py:987-988` | Pipeline CONTENT_LIST: same skip as D2. |
| D6 | `mineru/backend/pipeline/pipeline_middle_json_mkcontent.py:997-1003` | Pipeline CONTENT_LIST_V2: empty `page_contents` slot preserved. |
| D7 | `mineru/backend/office/mkcontent/output_builders.py:767-768` | Office MM_MD: skip page with empty `para_blocks`. |
| D8 | `mineru/backend/office/mkcontent/output_builders.py:775` | Office CONTENT_LIST: skip empty page. |

### E. Reconciliation metadata (not skip paths; cited for caller)

| # | file:line | Field | Role |
|---|---|---|---|
| E1 | `mineru/backend/vlm/model_output_to_middle_json.py:70-75` | `page_idx`, `page_size`, `preproc_blocks`, `discarded_blocks` | Per-page middle-json record after VLM path. |
| E2 | `mineru/backend/pipeline/model_json_to_middle_json.py:256-262` | `page_idx`, `page_size`, `preproc_blocks`, `discarded_blocks` | Pipeline page record (pre-finalize). |
| E3 | `mineru/backend/vlm/model_output_to_middle_json.py:106-117` | `para_blocks` (via `build_para_blocks_from_preproc`) | Added at finalize; markdown uses `para_blocks`. |
| E4 | `mineru/backend/vlm/model_output_to_middle_json.py:79-80` | `_backend`, `_version_name` | Backend tag only; no source page count. |
| E5 | `mineru/backend/hybrid/hybrid_model_output_to_middle_json.py:181-188` | `_backend`, `_effort`, `_ocr_enable` | Hybrid metadata; no source page count. |
| E6 | `mineru/cli/common.py:405` | log `len(middle_json['pdf_info'])` | Debug log only at pipeline doc ready. |

**Inventory path count: 48** (A1-A9, B1-B12, C1-C26, D1-D8; E-rows are reconciliation fields, not skip paths).

## Verdict on the claim(s)

**PARTIALLY (C4 foreign fact).** MinerU does not guarantee one output page per source PDF page. Broken PDF pages can be dropped at preprocess (A3/A5) with log-only notice. VLM/hybrid paths can silently omit page slots when batch output is shorter than the image list (B1/B4/B6-B9). Middle json retains `page_idx` on entries that exist, but there is no authoritative `source_page_count` or skip manifest; callers must compare `len(middle_json["pdf_info"])` and max `page_idx` against an independent PDF page count. Final markdown can omit pages that exist in middle json with empty `para_blocks` (D1/D4/D7) without marking them skipped.

## Coverage gaps

- **`mineru_vl_utils.MinerUClient`** (`batch_two_step_extract`, `batch_extract_with_layout`, aio variants): external package; internal page-drop logic NOT VERIFIED in this corpus.
- **`mineru/cli/router.py`**, **`mineru/cli/api_client.py`**, **`mineru/cli/client.py`**: not fully read; may add page-range or error handling.
- **`mineru/model/**`**: layout/OCR/MFR/table submodels read only where referenced by `batch_analyze.py`; not every `continue` in model code traced.
- **`tests/**`, `demo/**`**: excluded per charter production focus.
- **`mineru/backend/office/docx_analyze.py`**, **`pptx_analyze.py`**, **`xlsx_analyze.py`**: office slide/sheet enumeration not fully traced (office PDF path partially covered via `model_output_to_middle_json.py`).

## What could still hide a counterexample

- Page-level exception handlers in `mineru_vl_utils` that swallow failures and return empty block lists per page.
- API/router paths that subset pages without passing `start_page_id`/`end_page_id` through to output metadata.
- Client-side-only finalize (`client_side_output_generation=True`) altering `para_blocks` after server middle json is staged.

## Caller reconciliation (middle json vs final markdown)

| Artifact | Can reconcile page count? | Fields |
|---|---|---|
| **middle json** | Partial | `len(pdf_info)`; each element's `page_idx` (0-based source index at conversion time), `page_size`, block lists (`preproc_blocks` then `para_blocks` after finalize), `discarded_blocks`. No `source_page_count`, no `skipped_pages`, no `expected_page_count`. After A3, indices refer to rewritten PDF, not original broken-page numbering. |
| **final markdown** (`union_make` MM_MD) | No | Concatenated blocks only; pages with empty/missing `para_blocks` dropped at D1/D4/D7 with no placeholder. |
| **content_list** | Partial | Skips empty pages (D2/D5/D8). Each item includes `page_idx` when present. |
| **content_list_v2** | Best | One outer list entry per middle-json page (D3/D6); empty pages appear as `[]`. |
| **`_model.json` / infer results** | Partial | Parallel list returned alongside middle json from analyze functions; not written into middle json; caller must keep separately. |
