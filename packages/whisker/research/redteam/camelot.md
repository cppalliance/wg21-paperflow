# Red-team: whisker guard/calibrate vs camelot-py QA

- Camelot gates on **exact extracted output** (DataFrame equality + pinned `parsing_report` + mpl plot baselines); whisker guard gates on **fuzzy per-axis metric drops**, so cell-level or structural regressions can slip through slack.
- Camelot ships **reference-free intrinsic quality** (`accuracy`, `whitespace`, `confidence`, lattice `_GRID_WHITESPACE_REJECT`); whisker guard has **no equivalent intrinsic axis** on the bench/guard path.
- Camelot **never calibrates ROC-style**; thresholds are ICDAR-measured constants with inclusive boundary tests. whisker `calibrate.py` is ahead on methodology but **misses dual-threshold coupling, cross-validation, and per-axis fits** camelot encodes manually.
- Several **concrete whisker bugs** surfaced: ignored baseline `axis_slack`, missing-axis silent skip, duplicate PIDs, unvalidated `target_fpr`, independent fail/review fits that can invert the band, NaN/inf inputs.
- **Top portable adoption**: camelot's composite `confidence = (accuracy/100) * (1 - whitespace/100)` with documented `>= 0.8` operating point (`core.py:688-705`, `utils.py:1615-1638`).

---

## 1. REGRESSION-GATE GAPS

### [CRITICAL] Exact per-fixture output regression (DataFrame goldens)

**Camelot:** Every extraction test builds expected cell matrices in `tests/data.py` and asserts with `pandas.testing.assert_frame_equal` (e.g. `tests/test_stream.py:12-17`, `tests/test_lattice.py:11-18`). Any cell change fails CI; refresh = edit the golden in the PR.

**whisker guard:** `diff_rows` only compares rounded metric axes with `GUARD_AXIS_SLACK` tolerance (`guard.py:172-184`, `constants.py:94`).

**Adopt?** Partially. Exact markdown goldens are the wrong primary gate for tomd (formatting churn), but camelot proves **metric slack is a blind spot**: a regression that preserves NID/TEDS/MHS within 0.02 still fails camelot. whisker should add optional per-paper anchor/substring facts (gap-matrix #9) or tighten slack on a micro-corpus. Do not replace fuzzy guard with byte-exact bench output.

### [HIGH] Pinned composite metric snapshot (not just cell content)

**Camelot:** `test_parsing_report` pins `accuracy`, `whitespace`, `order`, `page`, and derived `confidence` to exact floats for `foo.pdf` (`tests/test_common.py:30-45`), alongside the DataFrame golden.

**whisker guard:** Baseline stores `nid/teds/mhs/overall/reading_order` only (`guard.py:65-71`); no separate snapshot of reference-free intrinsic signals.

**Adopt?** Yes for any intrinsic score whisker adds (see section 4). Pin composite intrinsics in the baseline the same way camelot pins `parsing_report`.

### [HIGH] Visual/plot regression baselines (pytest-mpl)

**Camelot:** Nine plot tests compare rendered debug output against committed PNGs under `tests/files/baseline_plots/` via `@pytest.mark.mpl_image_compare(..., remove_text=True)` (`tests/test_plotting.py:11-79`).

**whisker guard:** No visual or intermediate-representation regression.

**Adopt?** Low priority for markdown QA unless whisker gains layout-debug artifacts. Concept worth copying: **second regression layer** orthogonal to scalar metrics.

### [HIGH] Table/artifact count assertions

**Camelot:** CLI and tests assert extraction cardinality: `"Found 1 tables"` (`tests/test_cli.py:41`, `69`), `len(tables) == 2` (`tests/test_lattice.py:33-41`), `len(tables) == 1` for auto flavor (`tests/test_auto_flavor.py:19-21`).

**whisker guard:** No check that the number of tables, headings, or blocks is unchanged vs baseline.

**Adopt?** Yes. Add optional count axes (tables extracted, heading count) to baseline rows; a metric-improving swap that drops a table is invisible today.

### [MEDIUM] Parser-level precision gate before scoring (intrinsic reject)

**Camelot:** Lattice drops near-empty ruled grids at `whitespace >= 90.0` (`camelot/parsers/lattice.py:32`, `299-308`), tested in `tests/test_lattice.py:109-119`. Network parser explicitly does **not** inherit the gate (`tests/test_lattice.py:122-128`).

**whisker guard:** Floors apply to bench metrics after full conversion; no upstream "this output is structurally nonsense" reject separate from GT comparison.

**Adopt?** Yes on the reference-free `whisker score` path (not guard.py itself): an intrinsic reject reduces false passes on garbage that still scores ~0.9 against weak GT.

### [MEDIUM] Inclusive threshold boundary semantics (documented and tested)

**Camelot:** `TableList.filter` keeps tables at **exact** `min_accuracy` / `max_whitespace` boundaries (`core.py:1272-1273`); `tests/test_filter.py:50-58` asserts boundary values pass.

**whisker guard:** Regression uses strict `drop > slack` (`guard.py:181`); floor breach uses strict `axes[axis] < floor` (`guard.py:162`). Asymmetric vs camelot's `>=` / `<=` filter API.

**Adopt?** Document whisker's strict semantics in baseline JSON schema; add meta-tests mirroring camelot's inclusive-boundary table (`test_filter_thresholds_are_inclusive`). Do not silently flip to inclusive without revisiting all guard tests.

### [MEDIUM] Platform-conditioned regression scope

**Camelot:** Ghostscript/poppler tests skip on Windows (`tests/conftest.py:6-13`); CI runs `ubuntu`, `windows`, `macos` matrix (`.github/workflows/tests.yml:39-40`) knowing some goldens are platform-specific.

**whisker guard:** No platform tag on baseline rows; same committed baseline is diffed everywhere.

**Adopt?** Yes if bench scores vary by OS/backend. Tag baseline rows or skip guard on platforms where oracle/markitdown differs.

### [LOW] Coverage meta-regression (project health gate)

**Camelot:** Codecov project target `auto` with `threshold: 1%` (`codecov.yml:11-12`); local coverage `fail_under = 90` (`pyproject.toml:115`).

**whisker guard:** No analogous meta-gate on whisker's own test coverage.

**Adopt?** Optional CI hygiene, not guard.py logic.

### [LOW] Explicit refresh ritual for non-metric goldens

**Camelot:** Golden updates are manual PR edits to `tests/data.py` / `baseline_plots/`; no `--accept` CLI. whisker's `--update` (`__main__.py:329-367`) is **stronger** than camelot here.

**Adopt?** Already present; extend docs to require PR review of baseline diff (camelot's implicit review norm).

### [LOW] Monotonic known-bad / expectedFailure

**Camelot:** No `expectedFailure` field; weak outputs still have exact goldens. whisker's monotonic model (stable below-floor baseline passes, `tests/test_guard.py:84-92`) is closer to tabula-java than camelot.

**Adopt?** Keep whisker's approach; camelot does not add anything here.

### [LOW] Missing/added item detection asymmetry

**Camelot:** New PDF fixture = new test function (explicit). **whisker guard:** missing baseline PIDs hard-fail (`guard.py:221`, `113-115`); **new** PIDs pass as `status: new` (`guard.py:169`, `__main__.py:393-395`) without `--update`.

**Adopt?** Optional `--fail-on-new` flag for frozen corpora; camelot's norm is implicit via test inventory.

### [LOW] Normalization before diff

**Camelot:** Compares extracted DataFrames directly (no pre-diff canonicalization layer in tests). whisker normalizes inside metrics (`bench.py` / `metrics.normalized_text`).

**Adopt?** whisker is ahead; no change.

### [LOW] Statistical vs exact tolerance semantics

**Camelot:** Primary gate is **exact**; codecov/mpl layers add small statistical tolerance. whisker guard is **deterministic exact float compare after 4-decimal rounding** (`guard.py:177-180`).

**Adopt?** Keep deterministic rounding; camelot validates the need for a documented slack boundary (already tested in `test_slack_boundary_exact_is_not_a_regression`).

---

## 2. CALIBRATION GAPS

### [HIGH] Dual coupled thresholds (accuracy AND whitespace), not one ROC edge

**Camelot:** Post-extraction quality uses **two** independent axes with defaults `min_accuracy=0.0`, `max_whitespace=100.0`, composed in `filter()` (`core.py:1230-1274`). Production guidance: `confidence >= 0.8` as first-cut (`core.py:688-689`).

**whisker calibrate:** Fits a **single** `unigram_coverage` edge per band via one-dimensional ROC (`calibrate.py:149-185`); fail and review edges fitted **independently** in `__main__.py:494-498` with no constraint `fail_edge <= review_edge`.

**Adopt?** Yes. After independent fits, enforce ordering or fit jointly. camelot's composite `confidence` collapses two axes into one score with a documented 0.8 cut; whisker could calibrate `confidence`-like composite instead of two uncoupled unigram edges.

### [HIGH] Empirical constant tuning with published measurement rationale (not ROC)

**Camelot:** `_GRID_WHITESPACE_REJECT = 90.0` chosen from ICDAR false-positive whitespace sitting at 91-95% (`camelot/parsers/lattice.py:26-31`). No sweep, no TPR/FPR report.

**whisker calibrate:** ROC sweep with FPR ceiling (`calibrate.py:40-43`, `174-180`) but **no** helper to document why a floor constant was chosen on a versioned micro-corpus.

**Adopt?** Merge both: keep ROC for labeled verdict calibration; add `notes/` rationale block next to committed floors the way camelot comments ICDAR measurement in source.

### [MEDIUM] No cross-validation / holdout

**Camelot:** N/A (no calibrator). All tuning is in-sample on ICDAR fixtures embedded in tests.

**whisker calibrate:** Full-sample ROC; no k-fold or holdout split.

**Adopt?** Yes before promoting edges to `constants.py`. camelot's in-sample pinning (`test_common.py:35-40`) is acceptable for **regression snapshots**, not for **generalization claims**.

### [MEDIUM] Class imbalance handling

**Camelot:** N/A. Filter defaults are no-ops until caller sets thresholds.

**whisker calibrate:** Maximize TPR at FPR ceiling with no explicit prevalence weighting or minimum positive count (`calibrate.py:164-169` raises only on zero-class, not on tiny `n_pos`).

**Adopt?** Report confidence intervals or require minimum `n_pos`/`n_neg` before emitting a fitted edge; warn when `n_pos < 10`.

### [MEDIUM] Per-axis / per-flavor calibration

**Camelot:** Thresholds differ by parser flavor (lattice reject vs network passthrough, `tests/test_lattice.py:122-128`); accuracy/whitespace are flavor-agnostic fields.

**whisker calibrate:** Only `unigram_coverage` (`__main__.py:488-491`); bench axes (`nid`, `teds`, `mhs`) use hand floors (`constants.py:56-58`).

**Adopt?** Optional per-axis ROC on labeled bench corpus; camelot shows flavor-specific gates are normal.

### [LOW] Operating-point selection objective

**Camelot:** Implicit "maximize precision" via exact goldens; filter is caller-driven.

**whisker calibrate:** `max_tpr_at_fpr` then Youden fallback (`calibrate.py:174-180`) is **more principled** than camelot.

**Adopt?** Keep; camelot has nothing to teach here.

### [LOW] Multi-threshold cascade reporting

**Camelot:** `filter()` chains (`core.py:1263-1264`); tests compose `min_rows` + `min_accuracy` (`tests/test_filter.py:42-46`).

**whisker calibrate:** Emits two edges but not a full cascade report (fail vs review overlap).

**Adopt?** Emit derived band table: `[0, fail_edge)`, `[fail_edge, review_edge)`, `[review_edge, 1]`.

---

## 3. CONCRETE BUGS / EDGE-CASES IN OUR CODE

### [CRITICAL] `calibrate_threshold` + `__main__`: fail/review edges can invert `[ACTIONABLE-NOW]`

**Scenario:** Small labeled set where ROC places `review_edge` below `fail_edge` (independent fits, `__main__.py:494-498`).

**Function:** `calibrate_threshold`, `_calibrate_main`.

**Break:** Review band wider than fail band; papers get `fail` verdict logic inconsistent with calibrated intent.

**Fix:** Assert `fail_fit.chosen.threshold <= review_fit.chosen.threshold` or fit review only on samples not flagged at fail edge.

### [HIGH] `diff_rows`: duplicate PIDs in `rows` produce duplicate findings and ambiguous baseline `[ACTIONABLE-NOW]`

**Scenario:** Corpus loader or bench returns two `BenchRow` with same `pid`.

**Function:** `diff_rows` (`guard.py:216-218`).

**Break:** `report.count` inflated; last row wins in `baseline_from_rows` dict (`guard.py:143-146`) but guard diffs both; CI summary misleading.

**Fix:** Dedupe by pid (error or last-wins with warning).

### [HIGH] `_evaluate_paper`: missing axis key in baseline row silently skips regression on that axis `[ACTIONABLE-NOW]`

**Scenario:** Hand-edited baseline omits `"teds"` key for a paper.

**Function:** `_evaluate_paper` (`guard.py:174-176`).

**Break:** Large TEDS regression passes; camelot would never ship a partial golden.

**Fix:** Fail closed if any `GUARD_REGRESSION_AXES` key missing from baseline row when `base is not None`.

### [HIGH] `calibrate_threshold`: NaN / inf sample values `[ACTIONABLE-NOW]`

**Scenario:** `unigram_coverage` is `float('nan')` from a broken score.

**Function:** `_candidate_thresholds`, `_point` (`calibrate.py:130-134`, `136-146`).

**Break:** Sort order undefined; comparisons `value < threshold` always False for NaN; silent wrong operating point.

**Fix:** Reject non-finite inputs at entry.

### [MEDIUM] `diff_rows`: baseline `axis_slack` field ignored `[ACTIONABLE-NOW]`

**Scenario:** Committed baseline written with `axis_slack: 0.02`; CLI omits `--slack`.

**Function:** `baseline_from_rows` stores it (`guard.py:141`); `diff_rows` uses parameter only (`guard.py:205`, `221`).

**Break:** Slack drift between baseline metadata and actual gate; camelot pins constants in code + test literals, not split metadata.

**Fix:** Default `slack` from `baseline.get("axis_slack", C.GUARD_AXIS_SLACK)`.

### [MEDIUM] `diff_rows`: no `kind` / `schema_version` validation on baseline `[ACTIONABLE-NOW]`

**Scenario:** Point `--baseline` at a bench `report.json` leaderboard by mistake.

**Function:** `diff_rows` (`guard.py:212-214`).

**Break:** Partial diff against wrong schema; silent nonsense or empty `rows`.

**Fix:** Require `baseline["kind"] == GUARD_BASELINE_KIND` and matching `schema_version`.

### [MEDIUM] `calibrate_threshold`: `target_fpr` out of range unvalidated `[ACTIONABLE-NOW]`

**Scenario:** `--target-fpr 1.5` or negative.

**Function:** `calibrate_threshold` (`calibrate.py:149-154`).

**Break:** `feasible = [op for op in curve if op.fpr <= target_fpr]` always nonempty for high target; nonsense selection.

**Fix:** Validate `0.0 <= target_fpr <= 1.0`.

### [MEDIUM] `calibrate_threshold`: identical values across all samples

**Scenario:** All labeled papers have `unigram_coverage=0.91` (ties).

**Function:** `_candidate_thresholds`, selection (`calibrate.py:130-134`, `177`).

**Break:** Youden fallback may pick threshold `uniq[-1]+1.0` flagging **zero** papers (`calibrate.py:133`); TPR=0 report looks valid.

**Fix:** Detect zero variance; refuse calibration with explicit error.

### [MEDIUM] `diff_rows`: empty `rows`, nonempty baseline

**Scenario:** All corpus pairs skipped in CLI; empty list passed to `diff_rows`.

**Function:** `diff_rows` (`guard.py:216-221`).

**Break:** Every baseline PID in `missing`; correct but harsh. Opposite (empty baseline, rows present) handled as all-new.

**Fix:** CLI already errors on empty pairs (`__main__.py:354-356`); library should document or short-circuit.

### [LOW] Float slack at 4-decimal boundary

**Scenario:** `prior=0.97`, `cur=0.949999999`, `slack=0.02`.

**Function:** `_evaluate_paper` (`guard.py:180-181`).

**Break:** Rounding saves determinism (tested `test_slack_boundary_exact_is_not_a_regression`); values not rounded in baseline load from hand edit could edge-case.

**Fix:** Round `cur`/`prior` before drop computation, not only `drop`.

### [LOW] `calibrate_threshold`: duplicate `(pid, label)` rows double-count in ROC

**Scenario:** Labels file lists same PID twice.

**Function:** `_load_labeled_samples` (`__main__.py:441-452`), `_confusion`.

**Break:** Inflated `n_pos`/`n_neg`; wrong TPR/FPR.

**Fix:** Dedupe by pid with last-wins or error.

### [LOW] Unicode / huge corpus

**Scenario:** PID `P3181R1` with CJK in markdown; 500-paper corpus.

**Function:** `diff_rows`, `calibrate_threshold`.

**Break:** Unicode in pid strings is fine; huge corpus is O(n) guard, O(n*k) calibrate k=unique values. No bug, but no progress/logging like camelot's `Processing page` log pin (`tests/test_common.py:19-26`).

---

## 4. MISSING AXIS / CHECK

| Camelot gate | Evidence | whisker equivalent |
|--------------|----------|-------------------|
| **Intrinsic `confidence` / `accuracy` / `whitespace`** | `core.py:682-732`, `utils.py:1583-1638`, pinned `tests/test_common.py:35-40` | None on guard/bench path (reference-free score uses unigram coverage only) |
| **Lattice whitespace reject (90%)** | `lattice.py:32`, `308` | No table-empty-cell / raggedness intrinsic |
| **Exact cell matrix equality** | `tests/test_stream.py:17`, `tests/data.py` | GT bench metrics only; guard allows slack |
| **Extracted table count** | `tests/test_cli.py:41`, `tests/test_lattice.py:39` | None |
| **`min_rows` / `min_columns` shape filter** | `core.py:1270-1271`, `tests/test_filter.py:22-26` | Structural gates in `gates.py` for verdict, not bench guard |
| **Plot/contour debug fidelity** | `tests/test_plotting.py:11-79` | None |
| **Per-page / per-flavor isolation** | `tests/test_per_page.py:37-42`, `tests/test_lattice.py:122-128` | Single bench row per pid; no flavor dimension |
| **Verdict transition (pass→review→fail)** | N/A (camelot has no verdict trichotomy) | Not in guard (gap-matrix #3); camelot does not help |

**Highest-value missing axis for whisker:** reference-free **composite confidence** analogous to camelot's `(accuracy/100)*(1-whitespace/100)`, adapted to markdown/table structure (empty pipe cells, heading misalignment), gating before GT bench.

---

## 5. TOP PORTABLE DETAIL

**Adopt:** Per-table (or per-document) composite confidence

```python
confidence = max(0.0, (accuracy / 100.0) * (1.0 - whitespace / 100.0))
```

- **Definition:** `camelot/core.py:705` (`Table.confidence` property).
- **Components:** `accuracy` from weighted cell-alignment errors (`utils.py:1583-1612`); `whitespace` = % empty stripped cells (`utils.py:1615-1638`).
- **Operating point:** Documented first-cut filter `confidence >= 0.8` (`core.py:688-689`).
- **Precision gate constant:** `_GRID_WHITESPACE_REJECT = 90.0` with ICDAR measurement note (`lattice.py:26-32`).

**whisker mapping:** Define markdown analogs (e.g. `% empty table cells`, `% misassigned heading levels`), multiply into `[0,1]`, pin in guard baseline like `tests/test_common.py:35-40`, optional hard reject before GT comparison. ROC calibrate the 0.8 cut on labeled papers instead of hand-copying camelot's literal.

---

*Sources: vendored `packages/whisker/research/repos/camelot/` (camelot-py 2.0.0 snapshot). whisker modules read at commit time: `guard.py`, `calibrate.py`, `bench.py`, `constants.py`, `__main__.py`.*
