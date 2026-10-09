# 17b - surya (per-page result structure and failure semantics)

**Claims tested:** C4 (foreign per-page failure/coverage facts); C1/C2/C3 out of scope for this report.

**Exhaustive:** yes

## Method

Repo: `packages/whisker/research/repos/surya/` at SHA `11d18847e8b8c17fd55e254e3e5c44b3fed5c87e` (matches baseline `11d1884`).

Search commands run:

```
rg -n "class \w+" surya/ --glob "*.py" | rg -i "BaseModel|dataclass|schema|Result|Page"
rg -n "error\s*=\s*True|out\.error|needs_fallback|except Exception|\.error\b" surya/ --glob "*.py"
git -C packages/whisker/research/repos/surya rev-parse HEAD
```

Files read in full: `recognition/schema.py`, `recognition/__init__.py`, `layout/schema.py`, `layout/__init__.py`, `detection/schema.py`, `detection/__init__.py`, `detection/heatmap.py`, `table_rec/schema.py`, `table_rec/__init__.py`, `ocr_error/schema.py`, `ocr_error/__init__.py`, `inference/schema.py`, `inference/__init__.py`, `inference/backends/openai_client.py`, `inference/backends/vllm.py`, `inference/backends/llamacpp.py`, `inference/backends/base.py`, `inference/parsers.py`, `inference/util.py`, `common/polygon.py`, `common/predictor.py`, `common/blank.py`, `input/load.py`, `scripts/ocr_text.py`, `scripts/detect_layout.py`, `scripts/detect_text.py`, `scripts/table_recognition.py`, `scripts/config.py`, `tests/conftest.py`, `tests/test_recognition.py`, `tests/test_layout.py`, `tests/test_table_rec.py`, `README.md` (lines 155-262).

Glob inventory: 58 Python files under `surya/surya/`; 6 test files under `tests/`. All predictor entrypoints and schema modules read; remaining modules (model weights loaders, debug draw, spawn, s3, streamlit) scanned via `rg` for error/failure hits only.

## Inventory

### Per-page (or per-page-element) result models

| Model | Def | Page-level? | error field | confidence field | Role |
|---|---|---|---|---|---|
| `PolygonBox` | `common/polygon.py:9-11` | base for boxes | none | `confidence: Optional[float]` | Shared bbox/polygon + optional confidence |
| `BlockOCRResult` | `recognition/schema.py:8-14` | block within page | `error: bool = False` | inherited from `PolygonBox` | OCR block: `skipped`, `html`, layout labels |
| `PageOCRResult` | `recognition/schema.py:17-19` | **yes (one per page image)** | **none** | **none (page-level)** | `blocks: List[BlockOCRResult]`, `image_bbox` |
| `LayoutBox` | `layout/schema.py:8-12` | block within page | none | inherited from `PolygonBox` | Layout box: label, position, count |
| `LayoutResult` | `layout/schema.py:15-19` | **yes** | `error: bool = False` | **none (page-level)**; per-box via `LayoutBox.confidence` | `bboxes`, `image_bbox`, optional `raw` |
| `TextDetectionResult` | `detection/schema.py:8-12` | **yes** | **none** | per-bbox via `PolygonBox.confidence` | Line-detection bboxes + optional heatmaps |
| `TableRow` / `TableCol` / `TableCell` | `table_rec/schema.py:8-37` | table-scoped geometry | none | inherited from `PolygonBox` | Row/col/cell polygons |
| `TableResult` | `table_rec/schema.py:40-48` | **per table crop** (not whole page) | `error: bool = False` | **none** | rows/cols/cells or full-path `html` |
| `OCRErrorDetectionResult` | `ocr_error/schema.py:6-8` | **no (text batch, not page)** | none | none | `texts` + `labels` (`good`/`bad`) |
| `GenerationResult` | `inference/schema.py:27-35` | request-level (internal) | `error: bool = False` | `mean_token_prob: Optional[float]` | Single VLM HTTP call result |
| `BatchOutputItem` | `inference/schema.py:38-45` | request-level (internal) | `error: bool` | `mean_token_prob: Optional[float]` | Batch wrapper passed into predictors |
| `ParsedLayoutBlock` | `inference/parsers.py:19-23` | parse intermediate | none | none | Internal layout JSON parse |
| `ParsedTableElement` | `inference/parsers.py:82-85` | parse intermediate | none | none | Internal table-rec JSON parse |
| `ParsedFullPageBlock` | `inference/parsers.py:127-131` | parse intermediate | none | none | Internal full-page HTML parse |

**PageOCRResult has no page-level `error` or `confidence`.** Block-level flags only (`recognition/schema.py:8-14`). README documents block-level `confidence`, `skipped`, `error` in JSON output (`README.md:157-166`) but not a page-level error flag.

**LayoutResult records page-level failure explicitly** via `error=True` with empty `bboxes` (`layout/schema.py:19`, `layout/__init__.py:79-94`).

### Failure / fallback paths (every production handler)

| # | Location | Trigger | Recorded how | Caller sees |
|---|---|---|---|---|
| F1 | `inference/backends/openai_client.py:112-138` | Any exception on `chat.completions.create` | `GenerationResult(error=True, raw="")` → `BatchOutputItem.error=True` | Internal only; surfaced by predictors below |
| F2 | `inference/backends/openai_client.py:186-202` | Retry loop when F1 or repeat-token (`_should_retry:148-153`) | Up to 3 retries; final `BatchOutputItem.error` preserved if still failing | Same as F1 |
| F3 | `layout/__init__.py:79-84` | `out.error or not out.raw` for a page | `LayoutResult(bboxes=[], error=True, raw=out.raw)` | CLI: `results.json` page dict with `"error": true`, empty `bboxes` (`detect_layout.py:49-51`) |
| F4 | `layout/__init__.py:88-94` | `parse_layout()` raises | `LayoutResult(bboxes=[], error=True, raw=out.raw)` | Same as F3 |
| F5 | `layout/__init__.py:107-115` | Text-labeled block over blank/uniform crop | Block dropped (not an error flag) | Fewer `bboxes`; no failure marker |
| F6 | `recognition/__init__.py:226-237` | Block mode: `out is None or out.error` for a block | `BlockOCRResult(error=True, confidence=0.0, html="")` | OCR CLI JSON: block has `"error": true` (`ocr_text.py:35-37`, `README.md:166`) |
| F7 | `recognition/__init__.py:292-294` | Full-page: `out is None or out.error` | **No page flag**; page index added to `needs_fallback` | Caller gets fallback result only; original full-page failure **not recorded** |
| F8 | `recognition/__init__.py:296-301` | Full-page: empty `out.raw` and `is_blank_region(img)` | `PageOCRResult(blocks=[])` — treated as success | Empty page, no error |
| F9 | `recognition/__init__.py:303-307` | Full-page: empty `out.raw` on non-blank page | `needs_fallback` → layout+block OCR | Same silent heal as F7 |
| F10 | `recognition/__init__.py:309-314` | Full-page: `_detect_repeat_loop(out.raw)` | `needs_fallback` | Same silent heal as F7 |
| F11 | `recognition/__init__.py:318-323` | `parse_full_page_html()` raises | `needs_fallback` | Same silent heal as F7 |
| F12 | `recognition/__init__.py:351-366` | Any F7/F9/F10/F11 page | Re-run `LayoutPredictor` (if needed) + block-mode OCR | Final `PageOCRResult`; may contain F6 block errors or empty blocks if layout also failed (F3/F4) |
| F13 | `recognition/__init__.py:368-375` | Page slot still `None` after fallback | `PageOCRResult(blocks=[])` — **no error flag** | Empty page in JSON; indistinguishable from intentional blank |
| F14 | `recognition/__init__.py:52-78` | Full-page block over blank region | Block removed from list | Fewer blocks; no error |
| F15 | `table_rec/__init__.py:90-100` | `predict_simple`: `out.error or not out.raw` | `TableResult(..., error=True)` empty rows/cols/cells | CLI JSON: `"error": true` per table entry (`table_recognition.py:94-98`) |
| F16 | `table_rec/__init__.py:105-118` | `predict_simple`: `parse_table_rec()` raises | `TableResult(..., error=True)` | Same as F15 |
| F17 | `table_rec/__init__.py:191-201` | `predict_full`: `out.error` | `TableResult(..., error=True)` | Same as F15 |
| F18 | `table_rec/__init__.py:204-215` | `predict_full`: empty/non-error raw | `TableResult(error=False, html=cleaned)` even if `html==""` | Empty table HTML with **no error flag** |
| F19 | `input/load.py:70-76` | `PIL.UnidentifiedImageError` on folder image | File skipped with log warning | Page never appears in output batch |
| F20 | `detection/__init__.py:26-45` + `detection/heatmap.py:142-165` | (none explicit) | Always returns `TextDetectionResult`; empty `bboxes` if nothing detected | No error field; empty detection is normal output |

Torch predictors (`DetectionPredictor`, `OCRErrorPredictor`) propagate no per-page error schema; uncaught model exceptions would abort the call (no in-repo handler).

### Full-page failure: recorded vs healed silently

| Pipeline | Page-level failure recorded? | Evidence |
|---|---|---|
| Layout (`LayoutPredictor`) | **Yes** | `LayoutResult.error=True` per page (`layout/__init__.py:79-94`, `layout/schema.py:19`) |
| OCR full-page default (`RecognitionPredictor`, `full_page=True`) | **No (healed silently)** | Failures routed to `needs_fallback` (`recognition/__init__.py:287-366`); `PageOCRResult` has no `error` field (`recognition/schema.py:17-19`). Worst case: empty `blocks=[]` backfill (`recognition/__init__.py:368-375`) with no error bit |
| OCR block mode | **Per-block only** | `BlockOCRResult.error=True` (`recognition/__init__.py:226-237`); no page rollup |
| Text detection | **No error field** | `TextDetectionResult` schema lacks error (`detection/schema.py:8-12`) |
| Table rec | **Per-table, not per-page** | `TableResult.error=True` (`table_rec/schema.py:48`); pages with zero detected tables produce no table entries (`table_recognition.py:68-77`) |

## Verdict on the claim(s)

**C4 (surya per-page failure semantics): CONFIRMED** — Surya is inconsistent across lanes. Layout exposes `error` per page; OCR's primary `PageOCRResult` does not, and full-page VLM failures are auto-retried via layout+block fallback without preserving the original failure on the returned page object (`recognition/__init__.py:292-366`). Silent empty pages are possible (`recognition/__init__.py:368-375`).

## Coverage gaps

None for the scoped question (per-page models + failure paths). Full line-by-line read of all 58 `surya/surya/*.py` files not performed; every schema module, every predictor `__init__.py`, inference client, CLI entrypoints, and all `rg` hits for `error`/`needs_fallback`/`except Exception` in production paths were covered.

## What could still hide a counterexample

- Failure handling inside vendored model code (`detection/model/`, `ocr_error/model/`) if it swallows errors before returning to predictors (not observed in predictor wrappers).
- `scripts/streamlit_app.py` / `scripts/screenshot_app.py` UI-only exception handlers (not on CLI JSON path).
- Marker or other downstream repos consuming Surya output with additional failure semantics (out of repo scope).
