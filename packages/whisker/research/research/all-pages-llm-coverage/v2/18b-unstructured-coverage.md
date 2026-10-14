# 18b - unstructured (element/page coverage accounting and eval metrics)
**Claims tested:** C4 (foreign facts subset: page metadata, partition fallbacks, CCT metrics)
**Exhaustive:** no (see Coverage gaps)

## Method

Repo: `packages/whisker/research/repos/unstructured` at SHA `f6eea758911fcf627cbe6f9df9f790e549500d7b`.

Search commands run:

```
rg -n "page_number" unstructured --glob "*.py"
rg -n "page_number\s*=" unstructured --glob "*.py"
rg -n "page_number.*None|None.*page_number|without.*page_number" unstructured --glob "*.py"
rg -l "page_number" unstructured/partition --glob "*.py"
rg -n -i "hi_res|fast|auto|strategy|fallback|partition_pdf" unstructured/partition --glob "*.py"
rg -n "cct-accuracy|cct-%missing|calculate_accuracy|calculate_percent_missing" . --glob "*.py"
rg -n "continue|drop|skip|clean_pdfminer|remove_duplicate" unstructured/partition/pdf.py unstructured/partition/pdf_image --glob "*.py"
```

Files read in full or in substantial part: `unstructured/partition/strategies.py`, `unstructured/partition/pdf.py`, `unstructured/partition/common/common.py`, `unstructured/partition/docx.py` (page metadata section), `unstructured/partition/html/parser.py` (`_page_number`), `unstructured/partition/html/transformations.py`, `unstructured/partition/html/convert.py`, `unstructured/documents/elements.py` (ElementMetadata), `unstructured/metrics/text_extraction.py`, `unstructured/metrics/evaluate.py` (TextExtractionMetricsCalculator), `unstructured/metrics/utils.py`, `unstructured/staging/base.py` (`elements_to_text`, `convert_to_text`), `unstructured/partition/pdf_image/pdfminer_processing.py` (`merge_inferred_with_extracted_layout`, `clean_pdfminer_inner_elements`, `remove_duplicate_elements`).

## Inventory

### (a) Per-element `metadata.page_number` assignment

| file:line | role |
|---|---|
| `documents/elements.py:201` | `ElementMetadata.page_number: Optional[int]` field declaration |
| `documents/elements.py:268,322` | Constructor param default `None`; stored on metadata object |
| `partition/common/common.py:161,209` | `add_element_metadata(..., page_number=...)` writes into `ElementMetadata` |
| `partition/pdf.py:495-497` | PDFMiner loop: `enumerate(..., start=starting_page_number)` yields per-page index |
| `partition/pdf.py:552-554` | PDFMiner text elements: `ElementMetadata(..., page_number=page_number)` |
| `partition/pdf.py:574-576` | PDFMiner widget fields: `ElementMetadata(..., page_number=page_number)` |
| `partition/pdf.py:1155-1160,1167-1174,1206-1209` | OCR path: per-page/image `page_number` passed into `ElementMetadata` |
| `partition/pdf.py:1420,1469,1506-1508` | hi_res `document_to_element_list`: assigns `page_number` per layout page |
| `partition/common/common.py:435-458` | `ocr_data_to_elements`: copies `common_metadata` (includes `page_number`) onto each element |
| `partition/docx.py:215,242,778,887` | DOCX counter; elements get `page_number=self._opts.metadata_page_number` |
| `partition/docx.py:270-281` | `metadata_page_number` returns `None` when document has no page-break indicators |
| `partition/pptx.py:360,382,394,419,482,493` | PPTX slide counter; `PageBreak` and content elements get `page_number` |
| `partition/xlsx.py:85-96,456-460` | Each sheet mapped to `page_number` via `enumerate(..., start=starting_page_number)` |
| `partition/html/parser.py:352-363` | `_page_number`: from `data-page-number` attr or parent; returns `None` if absent |
| `partition/html/parser.py:274,523,563` | HTML v1 parser writes `page_number=self._page_number` (may be `None`) |
| `partition/html/transformations.py:27,78,107-108,121,134,165` | HTML v2/ontology: propagates `page_number`; sets from `ontology.Page.page_number` when present |
| `partition/pdf_image/pdf_image_utils.py:369,387` | Image-as-PDF helper assigns `page_number=i+1` |
| `partition/pdf_image/pdf_image_utils.py:356` | Single-image fallback hardcodes `page_number=1` |
| `partition/pdf_image/pdfminer_processing.py:1061` | Annotation dict includes `"page_number": page_number` (not element metadata) |
| `partition/common/metadata.py:300-305` | Reads existing `page_number` to assign `sequence_number` on page |

**Partition modules with zero `page_number` references (elements never get page metadata from these partitioners):**

| file | partitioner |
|---|---|
| `partition/text.py` | plain text |
| `partition/md.py` | markdown |
| `partition/csv.py` | CSV |
| `partition/tsv.py` | TSV |
| `partition/json.py` | JSON |
| `partition/xml.py` | XML |
| `partition/email.py` | email |
| `partition/msg.py` | Outlook MSG |
| `partition/epub.py` | EPUB |
| `partition/odt.py` | ODT |
| `partition/org.py` | Org mode |
| `partition/rst.py` | reStructuredText |
| `partition/rtf.py` | RTF |
| `partition/ppt.py` | legacy PPT |
| `partition/audio.py` | audio/STT |
| `partition/api.py` | remote API wrapper (delegates) |

**Can elements lack `page_number`?** Yes.

| file:line | evidence |
|---|---|
| `documents/elements.py:201,268` | Field is `Optional[int]`, default `None` |
| `partition/docx.py:270-281,778,887` | DOCX omits page number in metadata when no page-break markers found |
| `partition/html/parser.py:352-363,274,523,563` | HTML v1: `_page_number` returns `None` without `data-page-number` ancestry |
| `partition/html/transformations.py:27,49,89` | HTML v2 default `page_number=None` |
| 14 partition modules above | Never assign `page_number` |
| `chunking/base.py:1841,1863` | Chunking treats `page_number == None` as non-incrementing |
| `staging/base.py:379,296-298` | HTML export with page grouping skips elements where `page_number is None` (logs warning) |

PDF/image paths assign a page index for every element they emit; omission is by partitioner choice (DOCX/HTML) or format (text/md/csv/...).

### (b) Partition fallback chains and content-drop paths

**Strategy constants:** `partition/utils/constants.py:17-21` (`AUTO`, `FAST`, `OCR_ONLY`, `HI_RES`).

**Fallback / resolution paths (`partition/strategies.py`):**

| # | file:line | trigger | result |
|---|---|---|---|
| 1 | `strategies.py:37-40,87-91` | `strategy=AUTO`, `is_image=True` | → `HI_RES` |
| 2 | `strategies.py:37-46,103-104` | `strategy=AUTO`, PDF, `infer_table_structure` or `extract_element` | → `HI_RES` |
| 3 | `strategies.py:37-46,106-107` | `strategy=AUTO`, PDF, `pdf_text_extractable=True` | → `FAST` |
| 4 | `strategies.py:37-46,108-109` | `strategy=AUTO`, PDF, `pdf_text_extractable=False` | → `OCR_ONLY` |
| 5 | `strategies.py:48-56` | no inference, no pytesseract, not text-extractable | `ValueError` (hard fail) |
| 6 | `strategies.py:58-67` | resolved `HI_RES`, `unstructured_inference` missing, pytesseract present | → `OCR_ONLY` (warning logged) |
| 7 | `strategies.py:58-70` | resolved `HI_RES`, inference missing, pytesseract missing | → `FAST` (warning logged) |
| 8 | `strategies.py:72-79` | resolved `OCR_ONLY`, pytesseract missing, `pdf_text_extractable=True` | → `FAST` (warning logged) |
| 9 | `strategies.py:72-82` | resolved `OCR_ONLY`, pytesseract missing, not text-extractable | → `HI_RES` (warning logged) |
| 10 | `strategies.py:84` | deps satisfied for requested strategy | unchanged |
| 11 | `strategies.py:20-21` | `FAST` on image file | `ValueError` |

**Pre-strategy modifiers (`partition/pdf.py`):**

| # | file:line | trigger | effect |
|---|---|---|---|
| 12 | `pdf.py:304-308` | `is_pdf_too_complex(...)` | skips `extractable_elements`; `pdf_text_extractable` stays `False` → tends toward OCR/hi_res |
| 13 | `pdf.py:326-328` | exception in text extraction probe | logs, skips text extraction; `pdf_text_extractable=False` |
| 14 | `pdf.py:330-337` | always | calls `determine_pdf_or_image_strategy(...)` |
| 15 | `pdf.py:347-377` | final strategy `HI_RES` | `_partition_pdf_or_image_local` |
| 16 | `pdf.py:379-384` | final strategy `FAST` | `_partition_pdf_with_pdfparser` |
| 17 | `pdf.py:386-401` | final strategy `OCR_ONLY` | `_partition_pdf_or_image_with_ocr` |
| 18 | `pdf.py:403` | unknown strategy | `ValueError` |
| 19 | `pdf.py:604-615` | `pdf_hi_res_max_pages` exceeded | `PageCountExceededError` (hard fail, no partial output) |
| 20 | `pdf.py:868-869` | `PdfRenderTooLargeError` | `UnprocessableEntityError` (hard fail) |

**Production content-drop / omission paths (no error to caller):**

| # | file:line | what is dropped |
|---|---|---|
| 21 | `pdf.py:539` | PDFMiner FAST: text snippets where `_text.strip()` is empty are not appended |
| 22 | `pdf.py:1047-1048` | hi_res output: `PageBreak` elements dropped when `include_page_breaks=False` |
| 23 | `pdf.py:1064-1065` | hi_res output: `Text` elements whose text is empty after whitespace collapse are not appended |
| 24 | `pdf.py:1260-1263` | PDFMiner FAST: `LTImage` objects yield `"\n"` only; image content not extracted |
| 25 | `pdf_image/pdfminer_processing.py:831-859` | hi_res: `clean_pdfminer_inner_elements` removes PDFMiner-sourced regions inside table/layout blocks |
| 26 | `pdf_image/pdfminer_processing.py:647,863-867` | hi_res PDFMiner pass: `remove_duplicate_elements` drops duplicate text regions |
| 27 | `pdf_image/pdfminer_processing.py:1155-1156` | widget text extraction skips entries with empty/strip-empty text |
| 28 | `staging/base.py:531` | `convert_to_text` / CCT: elements without `.text` or with falsy text omitted from concatenation |
| 29 | `html/convert.py:296-298` | `group_elements_by_page`: elements with `page_number is None` skipped (warning logged) |
| 30 | `metrics/evaluate.py:178-189,192-199` | eval harness: per-document processing failures return `None` and are omitted from aggregate rows |

**Path count (fallback + execution + silent-drop paths enumerated above): 30**

### (c) Metrics code (CCT accuracy / CCT %missing)

| file:line | symbol / column | scope | computation |
|---|---|---|---|
| `metrics/text_extraction.py:57-66` | `calculate_accuracy` | **document** (two strings) | Levenshtein distance between output and source CCT; returns `1 - bounded_distance` |
| `metrics/text_extraction.py:69-119` | `calculate_edit_distance` | document | underlying edit-distance / score helper |
| `metrics/text_extraction.py:123-157` | `bag_of_words` | document | tokenizes CCT into word frequencies |
| `metrics/text_extraction.py:160-203` | `calculate_percent_missing_text` | **document** | BOW comparison: fraction of source word counts absent from output (0–1); no duplication penalty |
| `metrics/utils.py:16-34` | `_prepare_output_cct` | document | JSON → `elements_to_text(elements_from_json)` or read `.txt`; full-doc CCT |
| `metrics/evaluate.py:341-362` | `TextExtractionMetricsCalculator` | **document-per-row** | one row per output file vs ground-truth `.txt` |
| `metrics/evaluate.py:409-423` | `_process_document` | document | builds `output_cct` + `source_cct`; sets `cct-accuracy`, `cct-%missing` |
| `metrics/evaluate.py:417-421` | size-ratio gate | document | if encoded length ratio outside (0.5, 2.0), `accuracy=0.01` without calling Levenshtein |
| `metrics/evaluate.py:434-435` | column headers | document | `["filename", "doctype", "connector", "cct-accuracy", "cct-%missing"]` |
| `metrics/evaluate.py:437-443` | aggregation | corpus | mean/stdev/count over documents; **not per-page** |

No page-scoped CCT metric found in production metrics code at this SHA. Object-detection and element-type calculators in `metrics/evaluate.py` are also document-scoped.

## Verdict on the claim(s)

**PARTIALLY (C4 foreign-facts subset).** Unstructured assigns `page_number` on PDF/image/PPTX/XLSX/DOCX(best-effort)/HTML(best-effort) elements, but the field is optional and many partitioners never set it. Partition `AUTO` resolves to FAST/OCR_ONLY/HI_RES with dependency fallbacks that can downgrade extraction quality with warnings only. CCT metrics (`cct-accuracy`, `cct-%missing`) are document-level bag-of-words / edit-distance scores over concatenated text; they do not verify per-page coverage or detect missing pages.

## Coverage guarantees the caller actually gets

**None of the following are guaranteed:**

1. **Every PDF page produces output elements.** Pages with no detected layout/text may yield zero elements; no fail-closed page-count check in `partition_pdf`.
2. **Every element has `metadata.page_number`.** Optional; absent for DOCX without breaks, HTML without `data-page-number`, and all text-like partitioners.
3. **Per-page coverage accounting.** No production metric counts pages present in source vs pages represented in output.
4. **Silent-loss detection.** Empty text filtering (`pdf.py:539,1064-1065`), table-inner PDFMiner removal (`pdfminer_processing.py:831-859`), and CCT concatenation (`staging/base.py:531`) can drop content without raising; CCT `%missing` only compares whole-document word bags and does not penalize missing pages with no words in GT.
5. **Strategy fidelity.** hi_res may silently fall back to ocr_only or fast (`strategies.py:58-70`).

**What the caller does get:**

- PDF/image hi_res, fast, and ocr_only paths assign a 1-based page index (offset by `starting_page_number`) to elements they emit (`pdf.py:495-497,1420,1508`).
- Hard failures for unprocessable inputs: missing deps (`strategies.py:48-56`), page limit (`pdf.py:604-615`), render too large (`pdf.py:868-869`).
- Document-level CCT accuracy and %missing when using `TextExtractionMetricsCalculator` (`evaluate.py:409-423`).

## Coverage gaps

- `unstructured_inference` package (external): hi_res layout model internals not in this clone.
- Not every `continue`/skip in `partition/pdf_image/pdfminer_processing.py`, `ocr.py`, `inference_utils.py` enumerated line-by-line (30+ sites).
- HTML partition entry modules (`partition/html/__init__.py`, VLM path) not read in full.
- Chunking, ingest pipeline, API server, and test fixtures not exhaustively audited.
- Non-CCT metrics (`ElementTypeMetricsCalculator`, `ObjectDetection*`, table structure) noted but not fully inventoried.

## What could still hide a counterexample

- Additional drop logic inside `unstructured.partition.pdf_image.ocr` or `unstructured_inference` not present in this repo.
- Page-break-based page counting in DOCX/PPTX diverging from rendered page count (acknowledged in `docx.py:276-279`).
- Remote `partition_via_api` applying different strategy/fallback behavior than local `partition_pdf`.
