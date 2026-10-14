# Repo scan: PDF-Extract-Kit

**Does it verify LLM-readability?** **no**

Scanned: local shallow clone at `packages/whisker/research/repos/PDF-Extract-Kit` (read-only, release/1.0 tree, July 2026).

PDF-Extract-Kit is a **model toolbox**, not a conversion QA product. It ships demo inference scripts, hand-set YAML inference thresholds, and **placeholder** evaluation documentation (`XXX`). No pytest/unittest files (`.gitignore:8` ignores `test*`), no `.github/` CI, no committed goldens (`outputs/*`, `data/*` gitignored, `.gitignore:5-6`). End-to-end PDF→Markdown quality is explicitly deferred to **MinerU** (`README.md:34-36`, `144-145`). Nothing tests markdown LLM consumability, fact recovery, comprehension benchmarks, or LLM-as-judge QA.

## Findings

### 1. Evaluation section is stub; no runnable eval harness

- README: "**Evaluation Metrics — Coming Soon!**" (`README.md:84-86`).
- All seven evaluation RST pages are literal placeholders: `XXX` (`docs/en/evaluation/pdf_extract.rst:5`, `layout_detection.rst:5`, `ocr.rst:5`, `reading_order.rst:5`, and siblings).
- README claims "Comprehensive Evaluation Benchmarks" (`README.md:30`) but provides **zero** implemented metrics or scorer code in-repo.

### 2. No automated tests or CI

- `.gitignore:8`: `test*` ignored (discourages test files in tree).
- No `.github/workflows/` directory (confirmed absent).
- Repo-wide Python search: no `pytest`, `unittest`, or benchmark scorer modules; only task `evaluate: True` flags inside UniMERNet **training** config (`pdf_extract_kit/configs/unimernet.yaml:36-37`), not PDF→markdown QA.

### 3. E2E markdown demo drops modalities; no output verification

`project/pdf2markdown/scripts/pdf2markdown.py`:

- Reading order: heuristic `ymin*3000 + xmin` (`pdf2markdown.py:262-266`); README lists Reading Order as "Coming Soon!" (`README.md:49`).
- Span-to-block assignment: overlap ratio `> 0.6` (`pdf2markdown.py:300`; `merge_blocks_and_spans.py:111-134`).
- **`figure` and `table` blocks skipped** in markdown emit (`pdf2markdown.py:320-321` `continue`). Demo can ship table-free markdown with no failing gate.

No assertions on emitted markdown content, structure, or LLM recoverability.

### 4. Quality cuts are per-stage inference constants, not output comprehension

Hand-set YAML thresholds only:

| Stage | Threshold | Evidence |
|-------|-----------|----------|
| layout/formula YOLO | `conf_thres: 0.25`, `iou_thres: 0.45` | `configs/layout_detection.yaml:8-9` |
| OCR detection | `det_db_box_thresh: 0.3` | `configs/ocr.yaml:12` |
| span-in-block merge | overlap `> 0.6` | `pdf2markdown.py:300` |
| line grouping | y-overlap `> 0.8` | `merge_blocks_and_spans.py:7-17` |
| formula decode | `temperature: 0.0` | `unimernet.yaml:46` |

These gate **model confidence/geometry**, not whether markdown preserves facts for an LLM reader. No TEDS/NID, no fact assertions, no downstream QA track (contrast RealDocBench/ParseBench in `05-web.md` Q3).

### 5. Outputs and data gitignored; visual inspection only

- Scripts write to `outputs/*` (`scripts/layout_detection.py` pattern; `.gitignore:5`).
- Layout demo sets `visualize: True` (`configs/layout_detection.yaml:11`): **human eyeball**, not automated scoring.
- No `--update` baseline, no regression diff, no corpus contract.

### 6. Explicit product split: toolbox here, conversion QA in MinerU

> "If you are interested in extracting high-quality document content (e.g., converting PDFs to Markdown), please use MinerU" (`README.md:34-36`).

> "does not involve reconstructing extracted content into new documents, such as PDF to Markdown" (`README.md:144-145`).

PDF-Extract-Kit **delegates entirely** downstream markdown quality (including any OmniDocBench claims) to MinerU; this repo does not verify LLM-readability at all.

---

## Portable to whisker (ranked)

1. **Modality-presence gate (anti-pattern lesson)** — demo silently drops `figure`/`table` (`pdf2markdown.py:320-321`). Whisker must fail when GT has tables/images and candidate loses those modalities (guard baseline field `has_tables`, `modality_counts`); do **not** treat `teds=1.0` on table-free pairs as pass signal.

2. **Span-to-block overlap topology (`> 0.6`)** — `merge_blocks_and_spans.py:111-134`, `pdf2markdown.py:300`. Whisker guard could track `unmatched_gt_blocks` or block-match count vs baseline when aggregate NID is stable; catches mis-assignment drift.

3. **Per-stage threshold context in baseline** — separate YAML cuts per task (`layout_detection.yaml`, `ocr.yaml`, etc.). Whisker baseline should record `metric_version` + scoring context; optional per-axis slack (tighter TEDS, looser NID).

4. **Reading-order axis should gate when heuristic is used** — PDF-Extract-Kit defers reading order (`README.md:49`) but implements `order_blocks`; whisker already computes `reading_order` but excludes it from `GUARD_REGRESSION_AXES` (redteam note): consider gating reorder regressions.

5. **Do not adopt:** zero-gate CI model (no tests, gitignored outputs); "Coming Soon" eval stubs; defer-e2e-QA-to-downstream-product split; figure/table omission in demo markdown paths.

---

## Cross-check vs redteam report

**File:** `packages/whisker/research/redteam/PDF-Extract-Kit.md`

| Redteam claim | Verdict | Evidence |
|---------------|---------|----------|
| Zero pytest/unittest; `test*` gitignored | **Confirm** | `.gitignore:8`; no test files; no `.github/` |
| No committed goldens; outputs/data gitignored | **Confirm** | `.gitignore:5-6` |
| Eval docs are `XXX` placeholders | **Confirm** | `docs/en/evaluation/pdf_extract.rst:5`, `layout_detection.rst:5` |
| README "Evaluation Metrics — Coming Soon!" | **Confirm** | `README.md:84-86` |
| E2E PDF→Markdown deferred to MinerU | **Confirm** | `README.md:34-36`, `144-145` |
| Demo drops figure/table blocks | **Confirm** | `pdf2markdown.py:320-321` |
| Per-stage YAML thresholds (0.25/0.45/0.3/0.6/0.8) | **Confirm** | `layout_detection.yaml:8-9`, `ocr.yaml:12`, `pdf2markdown.py:300`, `merge_blocks_and_spans.py:7-17` |
| Reading order "Coming Soon!" vs heuristic | **Confirm** | `README.md:49`; `pdf2markdown.py:262-266` |
| UniMERNet `temperature: 0.0` for eval decode | **Confirm** | `unimernet.yaml:46` |
| No in-repo CI regression | **Confirm** | no `.github/workflows` |
| **Extend (LLM-readability scope):** no localized content asserts even at MinerU's weak n=1 level; purely pre-markdown CV/OCR cuts | **New** | PDF-Extract-Kit is strictly **no** for comprehension; MinerU carries the only OpenDataLab in-repo content asserts |

**Net:** Redteam findings **fully confirmed**. For #254 LLM-readability: **no** verification path exists in this repo; it is the negative control whisker guard was designed against.
