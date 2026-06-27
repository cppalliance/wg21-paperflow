# Red-team: whisker guard/calibrate vs img2table QA

## Summary

- img2table gates **per-stage structural goldens** (contours→lines→cells→tables→HTML/XLSX) with **exact equality** and **count assertions**; whisker guard diffs only four float axes and cannot see table-count, geometry, or output-format regressions.
- img2table's borderless filter uses a **hard-reject ladder** (minimum rows/columns, per-submetric floors) then a **weighted composite score ≥ 0.425**; guard has single floors + flat slack with no prerequisite gates and an unweighted `overall`.
- img2table **normalizes before diff** (sorted coordinates, set-equality for clusters, `pytest.approx` for floats); guard ignores `reading_order` drift, does not dedupe duplicate PIDs, and reads live `constants.py` floors instead of committed baseline floors.
- img2table explicitly tests **empty/blank inputs** (`None` metrics, `[]` tables); guard allows silent **STATUS_NEW** corpus growth and **NaN axes pass** without regression signal.
- **Top portable detail:** `StructuredSection.table_score` hard-reject chain + weighted `TableMetrics.score()` with **`is_structured()` cutoff 0.425** (`filter/model.py:118-162`, `filter/metrics/__init__.py:37-50`).

---

## 1. REGRESSION-GATE GAPS

### Per-stage intermediate goldens (structural, not scalar)

img2table chains committed fixtures across the pipeline: `contours.json` → `lines.json` → `expected.csv` / `cells_clustered.json` → `tables_from_cells.json` → `expected_tables.json` / `table.html` / `expected.xlsx` (`tests/tables/bordered/lines/test_lines.py:15-32`, `tests/tables/bordered/cells/test_cells.py:9-21`, `tests/tables/bordered/tables/creation/test_creation.py:56-69`, `tests/tables/extraction/test_extraction.py:47-56`, `tests/document/image/test_image.py:109-114`). Each stage fails independently, localizing regressions.

**guard.py** stores only rounded `nid/teds/mhs/overall/reading_order` per PID (`guard.py:65-71`, `136-146`). A tomd change that preserves fuzzy scores but breaks table geometry, cell count, or export shape passes guard.

**Adopt?** Partially. Full staged goldens belong in tomd; guard should at minimum add **structural sidecar fields** (table count, max row/col, heading depth) diffed per paper. **[HIGH]** Not in guard today; follow-on unless whisker sidecar already exposes counts.

### Count / cardinality assertions

img2table asserts `len(result) == 2`, `nb_rows`/`nb_columns`, `len(contours) == 86`, `len(cc) == 98` (`tests/tables/extractor/test_extractor.py:16-20`, `tests/tables/extractor/test_metrics.py:52`, `tests/document/rotation/test_rotation.py:19`). These are hard gates independent of fuzzy scores.

**guard.py** has no cardinality axis; `bench._table_score` returns `1.0` when neither side has tables (`bench.py:128-129`), masking "lost all tables" if both sides empty.

**Adopt?** Yes. Add per-paper **table-count / heading-count** (or non-null axis flags) to baseline and fail on drop beyond zero. **[HIGH] [ACTIONABLE-NOW]** (extend baseline schema + `_evaluate_paper`).

### Normalization-before-diff / order invariance

img2table sorts lines and cells before equality (`tests/tables/bordered/lines/test_lines.py:27-32`, `tests/tables/bordered/cells/test_cells.py:19-21`) and uses **set equality** for unordered clusters (`tests/tables/bordered/tables/creation/test_cell_clustering.py:19-23`). Reading-order permutations that preserve sets pass; order-sensitive paths use separate asserts.

**guard.py** diffs axes in fixed order but does not sort regression strings beyond axis name; `reading_order` is stored in baseline (`guard.py:71`) but excluded from `GUARD_REGRESSION_AXES` (`constants.py:99`). Reordered prose can regress reading order with no gate.

**Adopt?** Yes for `reading_order` as optional guard axis (config flag), or a dedicated slack separate from content axes. **[MEDIUM] [ACTIONABLE-NOW]**

### Tolerance semantics: exact vs approximate vs statistical

img2table mix: **exact** `==` on structures, **`pytest.approx`** on floats (`tests/document/image/test_image.py:68-71`, `tests/tables/borderless/tables/filter/test_metrics.py:189-204`), **`nested_approx`** for nested floats (`tests/conftest.py:76-86`, currently unused but ready), and **statistical** rotation gate `np.mean(similarities) >= 0.85` over a sweep (`tests/document/rotation/test_rotation.py:56-65`).

**guard.py** uses deterministic absolute slack `drop > slack` with 4-decimal rounding (`guard.py:177-184`). No relative tolerance, no per-axis slack, no distributional gate.

**Adopt?** Relative slack for high-magnitude axes is optional; the rotation pattern suggests a **corpus-level distributional backstop** (e.g. mean `reading_order` drop) as supplement to per-paper gate. **[MEDIUM]**

### Hard-reject prerequisite gates (multi-threshold per stage)

Before scoring, img2table returns `0.0` if `len(merged_rows) < 3`, `nb_columns < 2`, `spacing_consistency < 0.25`, `network_connectivity < 0.35`, etc. (`src/img2table/tables/borderless/tables/filter/model.py:125-152`). Only survivors reach `metrics.score()` and the **0.425** cutoff (`model.py:155-162`).

**guard.py** applies uniform floors (`NID/TEDS/MHS`) and slack; `below_floor` on known-weak papers is informational only (`guard.py:160-163`, `test_guard.py:84-92`). No multi-threshold prerequisite ladder.

**Adopt?** Yes for whisker bench: **hard-fail** when an axis is null/zero (e.g. `teds==1.0` because no tables on both sides) rather than treating as perfect. **[HIGH] [ACTIONABLE-NOW]** in guard floor logic.

### Missing / added item detection

img2table: every new behavior needs an explicit fixture file; CI has no concept of "new paper passes silently." Blank corpus returns `[]` / `None` (`tests/document/image/test_image.py:42-54`, `tests/tables/extractor/test_metrics.py:24-28`).

**guard.py**: missing baseline PIDs **hard-fail** (`guard.py:221`, `114-115`). **New** PIDs get `STATUS_NEW` and **pass** (`guard.py:165-169`, `113-115`). Corpus can grow without `--update`, hiding coverage expansion without committed review.

**Adopt?** Yes: optional **`--fail-on-new`** (default off for local dev, on in CI) or require new PIDs to appear in baseline with explicit `"accepted": true`. **[MEDIUM] [ACTIONABLE-NOW]**

### Known-bad / expectedFailure

img2table has no monotonic expectedFailure; weak sections score `0.0` and fail tests unless fixtures updated. whisker's monotonic known-bad (`test_guard.py:84-99`) is **ahead** of img2table here.

**Adopt?** Keep whisker model. **[LOW]** (no gap)

### Refresh ritual

img2table: manual JSON/CSV/XLSX edits; no `--update` command (`Makefile:10-18` only syncs deps). whisker **`--update`** (`__main__.py:329-367`) is ahead.

**Adopt?** Keep. **[LOW]**

### Committed baseline metadata not honored

**guard.py** writes `axis_slack` and `floors` into baseline (`guard.py:141-142`) but **`diff_rows` ignores them**, always using live `C.GUARD_AXIS_SLACK`, `C.*_FLOOR`, and CLI `--slack` (`guard.py:155`, `201-206`). Constants change silently redefines the contract.

img2table encodes thresholds in source next to logic (`filter/model.py:135-162`); tests pin exact outcomes so drift is visible.

**Adopt?** Yes: diff against `baseline["floors"]` and `baseline["axis_slack"]` when present; warn on mismatch with CLI override. **[HIGH] [ACTIONABLE-NOW]**

### Schema version / kind validation

Baseline carries `schema_version` and `kind` (`guard.py:139-140`) but **`diff_rows` never validates** them (`guard.py:212-214`).

**Adopt?** Yes: reject stale or wrong-kind baselines. **[MEDIUM] [ACTIONABLE-NOW]**

### CI tiering

img2table **`fast-test`** skips OCR and rotation (`Makefile:17-18`); full test on 5 Python versions (`.github/workflows/test_workflow.yml:10-20`).

**guard.py** has no fast/slow corpus split.

**Adopt?** Optional micro-corpus for PR vs full GT nightly. **[LOW]**

---

## 2. CALIBRATION GAPS

img2table **does not ROC-calibrate**; thresholds are engineering constants embedded in filter code and tests (`filter/model.py:135-162`, `filter/metrics/misc.py:48-50` sparsity target **0.35**, rotation **0.85** in `test_rotation.py:65`, default **`min_confidence=50`** in `document/image.py:48`).

### Operating-point selection

img2table: fixed cutoff **`table_score >= 0.425`** after hard rejects (`model.py:162`). calibrate.py: ROC sweep with max TPR at FPR ceiling (`calibrate.py:174-180`). Different domains, but img2table shows **two-tier** selection (hard rejects, then composite threshold) that calibrate lacks.

**Adopt?** calibrate should emit **paired hard-reject + edge** recommendations, not a single scalar. **[MEDIUM]**

### Metric choice / weighted composite

img2table `TableMetrics.score()` uses explicit weights (0.20 alignment, 0.15 min alignment, 0.15 spacing, 0.20 connectivity, 0.05 row pattern, 0.05 sparsity, −0.025 full_text) (`filter/metrics/__init__.py:42-50`), unit-tested at **0.5675** (`tests/.../test_metrics.py:192-204`).

whisker **`overall = mean(nid, teds, mhs)`** (`bench.py:161`); calibrate fits only **`unigram_coverage`** edges (`__main__.py:488-499`), not bench floors.

**Adopt?** Yes: extend calibrate to fit **NID/TEDS/MHS floors** from labeled bench outcomes; consider weighted overall instead of unweighted mean. **[HIGH]**

### Multi-threshold / per-axis calibration

img2table: **six+ submetric floors** before aggregation (`model.py:135-152`). calibrate.py: one threshold per call; CLI runs two independent fits for fail/review (`__main__.py:494-499`) with **no ordering constraint** (`review_edge` could end ≤ `fail_edge`).

**Adopt?** Yes: enforce **`review_edge >= fail_edge`** post-fit; calibrate each bench axis. **[MEDIUM] [ACTIONABLE-NOW]**

### Cross-validation / class imbalance

Neither img2table nor calibrate.py cross-validates. img2table tests use fixed tiny fixtures; calibrate uses full-sample ROC (`calibrate.py:149-185`) with no stratification or min-class-size guard beyond empty-class error.

**Adopt?** calibrate: report confidence when `n_pos` or `n_neg` < 30; optional k-fold for small corpora. **[MEDIUM]**

### Per-axis calibration scope

img2table calibrates **implicitly** via per-metric constants in filter submodules (spacing 0.25, connectivity 0.35, presence 0.5, sparsity target 0.35). calibrate ignores TEDS/MHS/NID entirely.

**Adopt?** Yes for bench guard floors. **[HIGH]**

---

## 3. CONCRETE BUGS / EDGE-CASES IN OUR CODE

| Scenario | Function | Behavior | Severity |
|----------|----------|----------|----------|
| **`NaN` or `inf` axis value** | `_evaluate_paper` (`guard.py:162-163`, `180-181`) | `NaN < floor` is False; `drop > slack` is False → **silent pass** | **[CRITICAL] [ACTIONABLE-NOW]** |
| **Duplicate PIDs in `rows`** | `diff_rows` (`guard.py:216-221`) | Duplicate findings; `current_pids` set collapses duplicates → **missing detection wrong** | **[HIGH] [ACTIONABLE-NOW]** |
| **Empty `rows`, baseline exists** | `diff_rows` | All baseline PIDs in `missing` → fails (good) | OK |
| **Empty `rows`, no baseline** | `diff_rows` | Empty findings, `failed=False` → **false green** | **[HIGH] [ACTIONABLE-NOW]** |
| **New PID not in baseline** | `_evaluate_paper` (`guard.py:165-169`) | `STATUS_NEW` passes; corpus grows unchecked | **[MEDIUM] [ACTIONABLE-NOW]** |
| **Both sides table-less** | `bench._table_score` (`bench.py:128-129`) | `teds=1.0` masks structural loss | **[HIGH]** |
| **Baseline floors changed in constants** | `diff_rows` vs `baseline["floors"]` | Uses live `_FLOORS` (`guard.py:62`, `161`) → **unreviewed threshold drift** | **[HIGH] [ACTIONABLE-NOW]** |
| **Slack CLI ≠ baseline `axis_slack`** | `diff_rows` (`guard.py:205`) | CLI wins silently | **[MEDIUM] [ACTIONABLE-NOW]** |
| **`review_edge` fit < `fail_edge` fit** | `_calibrate_main` (`__main__.py:494-499`) | Incoherent band; no validation | **[MEDIUM] [ACTIONABLE-NOW]** |
| **`NaN` in calibration sample value** | `_confusion` (`calibrate.py:110-111`) | `NaN < t` is False → never flagged as bad | **[HIGH] [ACTIONABLE-NOW]** |
| **All samples same float, mixed labels** | `calibrate_threshold` (`calibrate.py:171-180`) | Tie-break picks higher threshold; may leave **TPR=0** while claiming fit | **[MEDIUM]** |
| **Single-class labels** | `calibrate_threshold` (`calibrate.py:166-169`) | Raises `ValueError` (good) | OK |
| **Identical good/bad at same coverage** | `calibrate_threshold` | Youden fallback (`calibrate.py:178-180`); test covers (`test_calibrate.py:36-49`) | OK |
| **Huge corpus** | both | Linear; no issue | OK |
| **Unicode PID** | `_load_corpus_pairs` (`__main__.py:253`) | `.upper()` only; no normalization | **[LOW]** |

---

## 4. MISSING AXIS / CHECK

| img2table gates on | whisker equivalent | Gap |
|--------------------|-------------------|-----|
| **Table count / bbox / nb_rows×nb_columns** | none in guard | **[HIGH]** |
| **HTML output byte match** | none | **[MEDIUM]** (export fidelity) |
| **XLSX cell values match** | none | **[MEDIUM]** |
| **Intermediate geometry** (lines, cells, contours) | none | out of scope for whisker; tomd-side |
| **Blank/zero-content input** (`None` metrics) | no explicit empty-doc bench case | **[MEDIUM]** |
| **OCR `min_confidence` filter** | no OCR confidence axis | **[LOW]** (different domain) |
| **Borderless composite `table_score ≥ 0.425`** with submetric ladder | flat floors + slack | **[HIGH]** pattern missing |
| **Rotation quality (SSIM mean ≥ 0.85)** | none | **[LOW]** |
| **Metric formula regression test** (`score()==0.5675`) | `test_invariants.py` covers metrics, not guard decision | **[MEDIUM]** extend meta-tests |

---

## 5. TOP PORTABLE DETAIL

**Adopt:** img2table borderless **hard-reject ladder + weighted composite threshold**.

```python
# src/img2table/tables/borderless/tables/filter/model.py:125-162
if len(self.merged_rows) < 3: return 0.0
if self.nb_columns < 2 or self.nb_rows < 2 or max(self.nb_rows, self.nb_columns) < 3: return 0.0
# ... presence_ratios, spacing_consistency, network_connectivity floors ...
return metrics.score()  # weighted sum

# is_structured(): table_score >= 0.425
```

```python
# src/img2table/tables/borderless/tables/filter/metrics/__init__.py:42-50
0.20 * mean_column_alignment + 0.15 * min_column_alignment + 0.15 * spacing_consistency
+ 0.20 * network_connectivity + 0.05 * row_pattern_consistency + 0.05 * sparsity
- 0.025 * full_text
```

**Port to whisker:** Replace unweighted `overall` (`bench.py:161`) with a **documented weighted composite**; add **prerequisite null checks** before slack (e.g. if GT has tables and candidate `teds` is 1.0 with 0 tables extracted, hard-fail); gate at a committed composite floor analogous to **0.425**, with submetric floors matching img2table's ladder pattern. Unit-test the composite at a fixed fixture like img2table's **0.5675** pin (`tests/tables/borderless/tables/filter/test_metrics.py:204`).

**[HIGH] [ACTIONABLE-NOW]** for guard/bench; calibrate can later ROC-fit the composite cutoff instead of hand-setting 0.425.
