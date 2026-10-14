# Red-team: whisker guard + calibrate vs PDF-Extract-Kit QA

**Repo deep-read:** `packages/whisker/research/repos/PDF-Extract-Kit` (release/1.0 clone, June 2026). PDF-Extract-Kit is a **negative control**: zero pytest/unittest files (`.gitignore:8` ignores `test*`), no `.github/` CI, no committed goldens (`outputs/*`, `data/*` gitignored at `.gitignore:5-6`), evaluation docs are literal `XXX` placeholders (`docs/en/evaluation/layout_detection.rst:5`, `pdf_extract.rst:5`), and README declares **"Evaluation Metrics — Coming Soon!"** (`README.md:84-86`). End-to-end PDF→Markdown QA is explicitly deferred to **MinerU** (`README.md:34-36`, `144-145`). whisker guard/calibrate are **ahead** on regression plumbing; this repo exposes gaps via **modality omission**, **per-stage hand thresholds**, **reading-order heuristics**, and **anti-patterns whisker must not copy**.

## Summary (5 bullets)

- **[CRITICAL]** PDF-Extract-Kit’s demo `pdf2markdown` **drops figure/table blocks** from output (`project/pdf2markdown/scripts/pdf2markdown.py:320-321`); whisker `bench._table_score` returns **`teds=1.0` when neither side has tables** (`bench.py:128-129`), so guard diffs a synthetic axis and **cannot detect modality loss** PDF-Extract-Kit would silently ship.
- **[HIGH][ACTIONABLE-NOW]** PDF-Extract-Kit gates quality only through **per-task YAML thresholds** (`conf_thres: 0.25`, `iou_thres: 0.45` at `configs/layout_detection.yaml:8-9`; `det_db_box_thresh: 0.3` at `configs/ocr.yaml:12`; span-in-block overlap **`0.6`** at `pdf2markdown.py:300`; y-line overlap **`0.8`** at `merge_blocks_and_spans.py:7-17`); guard stores **no pipeline/threshold context** in baseline (`guard.py:136-147`) and ignores committed `axis_slack` (`guard.py:141`, `205-206`).
- **[HIGH]** Reading order is **"Coming Soon!"** in the product (`README.md:49`) but implemented ad hoc as `ymin*3000 + xmin` (`pdf2markdown.py:262-266`); whisker computes `reading_order` but **excludes it from `GUARD_REGRESSION_AXES`** (`constants.py:99`), matching PDF-Extract-Kit’s deferral and leaving reorder regressions ungated.
- **[MEDIUM]** PDF-Extract-Kit has **no calibration** (hand-set inference cuts only; UniMERNet eval pins `temperature: 0.0` for determinism at `pdf_extract_kit/configs/unimernet.yaml:46`); `calibrate.py` fits **`unigram_coverage` only** (`__main__.py:488-499`), not bench axes (`nid`/`teds`/`mhs`) that PDF-Extract-Kit’s staged pipeline would need if evaluation were ever built.
- **[MEDIUM][ACTIONABLE-NOW]** PDF-Extract-Kit’s **absence of CI** (no tests, gitignored outputs) is the field’s failure mode whisker guard was built to fix; remaining foolers: **silent corpus skips** (`__main__.py:256-258`), **duplicate pid overwrite** (`guard.py:143-146`), **NaN axes** (`guard.py:162,180-181`), **inverted fail/review edges** (`__main__.py:494-499`).

---

## 1. REGRESSION-GATE GAPS

### 1.1 No regression gate at all (committed snapshots absent)

**PDF-Extract-Kit:** No per-item metrics, no golden outputs in git, no `--update` ritual. Scripts write ephemeral results to gitignored `outputs/` (`scripts/layout_detection.py:24`, `.gitignore:5`). README evaluation section is a stub (`README.md:84-86`).

**guard.py:** Per-paper baseline JSON + `--update` refresh (`__main__.py:329-367`), per-axis diff (`guard.py:172-184`). **Ahead.**

**Adopt?** **Keep guard.** PDF-Extract-Kit proves the default for model toolboxes is **zero in-repo regression**; whisker must not regress toward this.

**Severity:** [CRITICAL] (field gap whisker closes; not an adoption item)

---

### 1.2 Modality-stratified per-stage thresholds vs single metric slack

**PDF-Extract-Kit:** Each pipeline stage carries its own operating constants in YAML: layout/formula YOLO `conf_thres: 0.25`, `iou_thres: 0.45` (`configs/layout_detection.yaml:8-9`, `configs/formula_detection.yaml:8-9`, `project/pdf2markdown/configs/pdf2markdown.yaml:10-18`); OCR box threshold `det_db_box_thresh: 0.3` (`configs/ocr.yaml:12`); geometry merge `fill_spans_in_blocks(..., 0.6)` (`pdf2markdown.py:300`); line grouping y-overlap **> 0.8** (`merge_blocks_and_spans.py:7-17`, duplicated in `paddle_ocr.py:81-91`); OCR recognition filtered at `score >= self.drop_score` (`paddle_ocr.py:445`).

**guard.py:** One `GUARD_AXIS_SLACK` for all regression axes (`constants.py:94-99`); baseline records metric floats only, not stage configs (`guard.py:136-147`).

**Adopt?** **Yes [HIGH][ACTIONABLE-NOW].** Record `metric_version` + scoring context in baseline; consider **per-axis slack** (e.g. tighter on `teds`, looser on `nid`) mirroring PDF-Extract-Kit’s per-task threshold files. A single global slack collapses stages the way PDF-Extract-Kit refuses to collapse models.

---

### 1.3 Silent modality omission (figure/table dropped)

**PDF-Extract-Kit:** `convert2md` skips `figure` and `table` layout blocks entirely (`pdf2markdown.py:320-321`), emitting text/formula-only markdown while the layout model still detects tables (`yolo.py:18-28` class id 5 = `table`).

**guard.py:** If GT and candidate both lack pipe tables, `teds=1.0` (`bench.py:128-129`). A regression that stops emitting tables but keeps prose can show **unchanged or improved `overall`** while PDF-Extract-Kit’s demo would still “pass” visually if nobody reads output.

**Adopt?** **Yes [CRITICAL][ACTIONABLE-NOW].** Gate on **modality presence flags** (baseline field: `has_tables`, `table_count`, layout-class counts) or fail when GT has tables and candidate table count drops to zero regardless of `teds`.

---

### 1.4 Per-item vs aggregate

**PDF-Extract-Kit:** No corpus aggregation; demo runs on `assets/demo/*` paths in configs (`configs/layout_detection.yaml:1`) with **visual inspection** (`visualize: True`, `layout_detection.yaml:11`). No mean-over-corpus metric.

**guard.py:** Per-paper diff. **Ahead.**

**Adopt?** **Keep.**

**Severity:** [LOW]

---

### 1.5 Floors / known-bad / expectedFailure

**PDF-Extract-Kit:** Hand-set inference floors only (conf/iou/det thresholds above); no monotonic known-bad baseline; no `expectedFailure` pattern.

**guard.py:** `_FLOORS` + monotonic known-bad (`guard.py:161-198`; `test_guard.py:84-99`). **Ahead.**

**Adopt?** **Keep.**

**Severity:** [LOW]

---

### 1.6 Missing / added item detection

**PDF-Extract-Kit:** No benchmark corpus contract; `.gitignore` excludes `data/*` and `test*`. New demo inputs do not fail CI because there is no CI.

**guard.py:** Baseline PIDs absent from current run → `missing` hard-fail (`guard.py:220-221,113-115`). New papers → `STATUS_NEW` passes if above floors (`guard.py:165-169`).

**Gap:** `_load_corpus_pairs` skips papers without staged MD (`__main__.py:256-258`) without adding them to `missing` when a `.gt.md` exists but candidate is absent — inverse of PDF-Extract-Kit’s problem but same blind spot: **corpus set drift**.

**Adopt?** **Yes [MEDIUM][ACTIONABLE-NOW].** Fail when any `*.gt.md` in corpus dir lacks a scorable candidate; optionally fail `STATUS_NEW` unless `--update`.

---

### 1.7 Normalization-before-diff

**PDF-Extract-Kit:** Pre-output transforms: `latex_rm_whitespace` on formulas (`pdf2markdown.py:23-39,188`); `ocr_escape_special_markdown_char` on text (`merge_blocks_and_spans.py:207-215,244`); zh/en spacing rules (`merge_blocks_and_spans.py:264-267`); detection scores rounded to 2 decimals (`pdf2markdown.py:93-94`, `paddle_ocr.py:305`).

**guard.py:** Metrics use OmniDocBench `normalized_text` / block match (`bench.py:153-157`) but baseline stores **no normalizer generation** (`guard.py:136-147`).

**Adopt?** **Yes [MEDIUM].** Pin `WHISKER_SCHEMA_VERSION` + normalizer id in baseline; PDF-Extract-Kit’s multi-layer text cleanup shows formatting-only changes are expected — guard refresh must be explicit when normalizers change.

---

### 1.8 Tolerance semantics: statistical vs exact

**PDF-Extract-Kit:** **Stochastic inference** (GPU models, YOLO NMS `iou_threshold=self.iou_thres`, `yolo.py:75`); thresholds are **confidence cuts**, not diff slack. No committed expected outputs to diff exactly. UniMERNet eval uses `temperature: 0.0` for greedy decode (`unimernet.yaml:46`) — determinism pinned at model config, not at output snapshot.

**guard.py:** Deterministic metrics with absolute drop slack (`guard.py:177-184`); appropriate for tomd re-runs.

**Adopt?** **Do not adopt PDF-Extract-Kit’s non-gating stochastic model for guard.** If whisker ever scores ML-backed paths, record **seed/temperature/model weights hash** in baseline the way `unimernet.yaml:46` pins decode.

**Severity:** [MEDIUM]

---

### 1.9 Refresh ritual

**PDF-Extract-Kit:** None. Outputs gitignored; no human-reviewed baseline bump.

**guard.py:** `whisker guard --update` (`__main__.py:361-367`). **Ahead.**

**Gap:** No CI env lockout on `--update` (unlike repos that never refresh in CI).

**Adopt?** **Yes [LOW][ACTIONABLE-NOW].** Refuse `--update` when `CI=true` unless explicit env override.

---

### 1.10 External benchmark delegation (anti-pattern)

**PDF-Extract-Kit:** Claims "Comprehensive Evaluation Benchmarks" (`README.md:30`) but ships empty evaluation RST stubs (`docs/en/evaluation/*.rst:5`) and redirects PDF→Markdown users to MinerU (`README.md:144-145`).

**guard.py:** In-repo guard + bench.

**Adopt?** **Never split whisker guard from tomd the way PDF-Extract-Kit splits model kit from MinerU.** Regression gate must live in the conversion QA tool, not a downstream product.

**Severity:** [HIGH]

---

## 2. CALIBRATION GAPS

### 2.1 No ROC / operating-point fit (field default)

**PDF-Extract-Kit:** Zero calibration module. All cuts are engineering constants in YAML (`conf_thres`, `iou_thres`, `det_db_box_thresh`, span overlap `0.6`, y-overlap `0.8`).

**calibrate.py:** ROC sweep + max-TPR-at-FPR + Youden fallback (`calibrate.py:149-185`). **Ahead** for `unigram_coverage`.

**Adopt?** **Extend, not revert.** PDF-Extract-Kit shows the field norm: hand-set thresholds without TPR/FPR audit.

**Severity:** [MEDIUM]

---

### 2.2 Per-axis / per-stage calibration

**PDF-Extract-Kit:** Separate threshold blocks per task in config (`layout_detection.yaml`, `formula_detection.yaml`, `ocr.yaml`, `pdf2markdown.yaml`). No single "overall" score.

**calibrate.py:** Only `unigram_coverage_fail_edge` and `unigram_coverage_review_edge` (`__main__.py:488-499`). **No fit for `NID_FLOOR`/`TEDS_FLOOR`/`MHS_FLOOR`** used by guard floors (`constants.py:56-58`, `guard.py:62`).

**Adopt?** **Yes [HIGH].** Run the same ROC machinery on labeled bench rows per axis; emit a `thresholds.json` analogous to opendataloader, covering the axes PDF-Extract-Kit would gate if evaluation existed.

---

### 2.3 Operating-point selection

**PDF-Extract-Kit:** Fixed constants (0.25, 0.45, 0.3, 0.6, 0.8) with no FPR ceiling, no fallback policy.

**calibrate.py:** `DEFAULT_TARGET_FPR=0.05`, Youden when infeasible (`calibrate.py:43-46,174-180`). **Strictly better** when labels exist.

**Adopt?** **Keep calibrate selection.** Document that PDF-Extract-Kit-style fixed cuts are what provisional `constants.py` floors are until calibrate promotes them.

**Severity:** [LOW]

---

### 2.4 Multi-threshold ordering (fail vs review band)

**PDF-Extract-Kit:** Nested implicit ordering (det before rec, layout before OCR in pipeline) but no fail/review band.

**calibrate.py:** Independent fail and review fits (`__main__.py:494-499`); no invariant `fail_edge <= review_edge`.

**Adopt?** **Yes [HIGH][ACTIONABLE-NOW].** Enforce monotonic band after both fits.

---

### 2.5 Cross-validation / class imbalance

**PDF-Extract-Kit:** No labeled corpus in repo; no class balance concerns documented.

**calibrate.py:** Requires both classes (`calibrate.py:166-169`); no minimum `n`, no bootstrap CI, no warning on skew.

**Adopt?** **Yes [MEDIUM].** Warn when `n_pos < 10` or `n_neg < 10`; PDF-Extract-Kit’s "evaluate on diverse documents" claim (`README.md:28`) is unimplemented — do not calibrate on n=3 and call it done.

---

### 2.6 Metric choice mismatch

**PDF-Extract-Kit:** Would gate layout mAP, formula det/rec, OCR CER at task level (per empty `docs/en/evaluation/*.rst` structure) — **not** markdown NID/TEDS/MHS.

**calibrate.py / guard:** Markdown structural fidelity axes. Orthogonal to PDF-Extract-Kit’s computer-vision metrics.

**Adopt?** **Document boundary.** `calibrate` targets reference-free `unigram_coverage`; guard targets bench GT axes. PDF-Extract-Kit reminds that **upstream CV threshold drift** can break markdown without moving whisker metrics if tomd’s input PDF path unchanged — out of scope unless whisker scores layout/OCR stages.

**Severity:** [LOW]

---

## 3. CONCRETE BUGS / EDGE-CASES IN OUR CODE

| Function | Scenario | PDF-Extract-Kit lesson | Actual behavior | Severity |
|----------|----------|------------------------|-----------------|----------|
| `_table_score` / `diff_rows` | GT has tables; candidate loses all pipe tables (PDF-Extract-Kit demo drops tables at `pdf2markdown.py:320-321`) | Modality omission is shippable in demo | `teds=1.0` if **both** lack tables (`bench.py:128-129`); partial loss scores low TEDS but guard may pass on sub-slack drop | [CRITICAL] [ACTIONABLE-NOW] |
| `_table_score` / `diff_rows` | Neither side has tables | Demo never emits tables | `teds=1.0` always; guard diffs meaningless 1.0→1.0 | [HIGH] [ACTIONABLE-NOW] |
| `diff_rows` | `reading_order` collapses (PDF-Extract-Kit `order_blocks` heuristic `pdf2markdown.py:262-266`) | Reading order is explicit future work (`README.md:49`) | Axis stored but **not in `GUARD_REGRESSION_AXES`** (`constants.py:99`) → pass | [HIGH] [ACTIONABLE-NOW] |
| `baseline_from_rows` | Duplicate `pid` in `rows` | Single-doc demo | Last row wins in dict comp (`guard.py:143-146`) | [MEDIUM] [ACTIONABLE-NOW] |
| `diff_rows` | Hand-edited baseline NaN on an axis | No baseline to corrupt | `NaN < floor` False; `drop > slack` False → silent pass (`guard.py:162,180-181`) | [HIGH] [ACTIONABLE-NOW] |
| `diff_rows` | Baseline stores `"axis_slack": 0.05`, CLI uses default 0.02 | PDF-Extract-Kit pins thresholds in committed YAML | CLI `slack` overrides; baseline field ignored (`guard.py:141`, `205-206`) | [HIGH] [ACTIONABLE-NOW] |
| `_load_corpus_pairs` + `diff_rows` | `.gt.md` present, candidate MD missing | No corpus contract | Skip with warning; not in `missing` (`__main__.py:256-258`) | [MEDIUM] [ACTIONABLE-NOW] |
| `diff_rows` | Empty `rows`, `baseline=None` | n/a | Vacuous pass (`guard.py:216-222`) | [MEDIUM] |
| `diff_rows` | `baseline["kind"]` wrong / schema drift | PDF-Extract-Kit has no schema | Accepted if `rows` key parses (`guard.py:213-214`) | [MEDIUM] [ACTIONABLE-NOW] |
| `calibrate_threshold` | Sample contains NaN `unigram_coverage` | OCR can return `None` (`paddle_ocr.py:404`) | Undefined comparisons (`calibrate.py:110-111`) | [HIGH] [ACTIONABLE-NOW] |
| `calibrate_threshold` | Single class labels | n/a | `ValueError` (`calibrate.py:166-169`) | OK |
| `calibrate_threshold` | Bad/good tie at same coverage | Stochastic ties at conf threshold | Youden fallback; ambiguous edge (`calibrate.py:179-180`) | [MEDIUM] |
| `_calibrate_main` | Fail edge 0.92, review edge 0.88 | Nested stage thresholds imply ordering | Emits inverted band (`__main__.py:494-499`) | [HIGH] [ACTIONABLE-NOW] |
| `_calibrate_main` | Empty labels file after parse | n/a | `EXIT_ERROR` (`__main__.py:484-486`) | OK |
| `diff_rows` | Huge corpus, all papers identical metrics | Demo n=1 | O(n) pass; no collision detection | [LOW] |

---

## 4. MISSING AXIS / CHECK

| PDF-Extract-Kit stage / check | Evidence | whisker equivalent | Gap |
|------------------------------|----------|-------------------|-----|
| Layout detection (10 classes: title, text, figure, table, formula, …) | `yolo.py:18-28` | None in guard/bench | [CRITICAL] No layout-class regression; table/figure loss invisible |
| Formula detection + recognition | `pdf2markdown.yaml:13-26`, `pdf2markdown.py:154-190` | None | [HIGH] Equation/LaTeX axis absent from guard |
| OCR detection (`det_db_box_thresh`) + rec (`drop_score`) | `ocr.yaml:12`, `paddle_ocr.py:445` | None | [HIGH] Low-confidence text drop not gated |
| Table recognition (StructEqTable) | `README.md:48`, `table_parsing` task | `teds` on pipe tables only | [HIGH] HTML/LaTeX table paths in PDF-Extract-Kit not covered by markdown TEDS extractor |
| Reading order model | `README.md:49` "Coming Soon!" | `reading_order` metric, **not gated** | [HIGH] Heuristic order regressions unguarded (`constants.py:99`) |
| Figure/image content in markdown | Dropped in demo (`pdf2markdown.py:320-321`) | No image-embedding check | [HIGH] |
| End-to-end PDF extract evaluation | `docs/en/evaluation/pdf_extract.rst:5` `XXX` | `whisker bench` + guard | whisker **has** e2e gate; PDF-Extract-Kit does not |
| Deterministic decode pin | `unimernet.yaml:46` `temperature: 0.0` | Deterministic tomd path | OK for tomd; document if ML oracle added |
| In-repo CI regression | Absent (no tests, gitignored outputs) | `whisker guard` | whisker **leads** |

---

## 5. TOP PORTABLE DETAIL

**Adopt: span-to-block overlap gate `calculate_overlap_area_in_bbox1_area_ratio(...) > 0.6` used when assigning OCR/formula spans to layout blocks** (`merge_blocks_and_spans.py:111-134`, invoked at `pdf2markdown.py:300`).

This is the repo’s most concrete, named, reproducible quality cut unrelated to ML confidence: a span joins a block only if **>60% of the span bbox area lies inside the block bbox**. whisker’s block matcher uses NED thresholds (`constants.py:107-109`) but guard does not fail when **block assignment topology** changes while aggregate NID holds.

**Portable use for whisker:** add baseline fields `block_match_count`, `unmatched_gt_blocks`, or a binary `rescue_fired` flag from `block_metrics`; fail guard when unmatched GT blocks increase versus baseline even if `nid` drop ≤ slack. That catches PDF-Extract-Kit-class failures (mis-assigned spans after layout drift) that scalar TEDS/NID miss.

**Do not adopt:** PDF-Extract-Kit’s **zero-gate CI model** (`.gitignore:5-8`, `README.md:84-86`) or **defer-e2e-QA-to-downstream** pattern (`README.md:144-145`).
