# Red-team: whisker guard/calibrate vs opendataloader-pdf QA

**Scope:** `guard.py`, `calibrate.py` vs opendataloader-pdf CI + its companion bench (`opendataloader-bench`, invoked by `scripts/bench.sh --check-regression`).

## Summary

- **Corpus-mean floor gate:** opendataloader CI gates **aggregate means** against committed `thresholds.json` with `regression_tolerance: 0.02` (`score >= threshold - tol`); whisker guard only diffs **per-paper baselines** and never re-checks corpus means against published floors.
- **Null-axis eligibility:** opendataloader returns `None` and **excludes** TEDS/MHS/NID when GT lacks that modality; whisker bench returns `1.0` for no-table papers, so guard baselines treat “N/A” as “perfect” and corpus means are inflated.
- **Multi-axis contract file:** opendataloader ships one `thresholds.json` for NID/TEDS/MHS plus table-detection F1, speed, triage; whisker guard/calibrate cover bench axes only and calibrate fits **unigram_coverage** alone.
- **No ROC in opendataloader:** threshold values are hand-set engineering judgment; `calibrate.py` is ahead on methodology but lacks a unified thresholds artifact and bench-floor fitting.
- **Portable detail to adopt:** `regression_tolerance: 0.02` subtracted from each quality floor at the **corpus-mean** layer (`check_regression`), as a backstop alongside per-paper guard diffs.

---

## 1. REGRESSION-GATE GAPS

### 1.1 Corpus-mean absolute floors (committed thresholds.json)

**[HIGH][ACTIONABLE-NOW]** opendataloader `check_regression()` compares **corpus means** (`nid_mean`, `teds_mean`, `mhs_mean`) to committed floors minus tolerance (`run.py:73-86`, `thresholds.json:1-9`). CI fails the job on any breach (`run.py:396-400`, `test-benchmark.yml:114-115`). whisker `guard.py` never aggregates or compares means; it only calls `diff_rows()` per paper. A change can leave every per-paper drop within slack while the **corpus mean** falls below the published NID/TEDS/MHS bar (exact “mean hides collateral” failure mode, inverted: per-paper slack passes, corpus fails).

**Adopt?** Yes. Add a corpus-mean pass in guard (or chain after `aggregate()`) using the same `score >= floor - regression_tolerance` semantics as a backstop. Per-paper guard stays primary; mean gate catches diffuse erosion.

### 1.2 Per-item scores recorded but not gated (opendataloader) vs per-item gated (whisker)

**[MEDIUM]** opendataloader `evaluator.py` writes per-document scores to `evaluation.json` (`evaluator.py:252`, `DocumentScores.to_json:49-62`) but `check_regression()` **ignores** the `documents` array and only checks means (`run.py:66-86`). whisker guard **does** gate per paper (`guard.py:216-218`). whisker is stricter here; the gap is whisker lacking the **forensic artifact** pattern (evaluation.json + CSV + history archive).

**Adopt?** Partially. Keep per-paper guard; add optional guard report export aligned with opendataloader’s per-doc JSON/CSV shape for bisect.

### 1.3 Null / ineligible axis handling (modality-stratified means)

**[CRITICAL][ACTIONABLE-NOW]** opendataloader returns `(None, None)` when GT has no tables (`evaluator_table.py:234-235`) or no headings (`evaluator_heading_level.py:138-139`), and `_aggregate_document_scores` **excludes nulls** from means while publishing `teds_count` / `mhs_count` / `nid_count` (`evaluator.py:131-162`). whisker `_table_score()` returns `1.0` when neither side has tables (`bench.py:128-129`); guard stores and diffs that `1.0` as a real score (`guard.py:64-71`, `172-184`). A table-less paper baseline of `teds=1.0` masks “GT has tables, pred lost them” until a large drop, and inflates corpus means opendataloader would not count.

**Adopt?** Yes. Mark axis `eligible: false` (or store `null`) when GT lacks modality; exclude from regression diff and from `overall` aggregation, matching opendataloader semantics.

### 1.4 Structure-only companion metrics (nid_s, teds_s, mhs_s)

**[HIGH]** opendataloader evaluates content **and** structure-only variants (`evaluator_reading_order.py:37-38`, `evaluator_table.py:242-246`, `evaluator_heading_level.py:147-151`) and logs both (`evaluator.py:187-197`). whisker guard diffs only `nid/teds/mhs/overall` (`constants.py:99`, `guard.py:172-173`); no `_s` axes.

**Adopt?** Yes for table/heading structure regressions that formatting churn hides in content scores. Lower priority for NID if whisker block-match already separates order.

### 1.5 Pre-score normalization before diff

**[MEDIUM][ACTIONABLE-NOW]** opendataloader normalizes inputs before every metric: `convert_to_markdown_with_html_tables()` (`evaluator_table.py:228-229`, `converter_markdown_table.py:67-68`), whitespace collapse (`evaluator_reading_order.py:14-15`, `evaluator_table.py:167-170`). whisker guard diffs **raw bench outputs** with no normalization layer; a pipe-table vs HTML-table representation change can register as a TEDS regression despite semantic identity (opendataloader tests assert cross-format table parity: `test_evaluator_table.py:36-41`).

**Adopt?** Yes at metric time (already partially in whisker `metrics.py`); guard should diff scores produced under the same normalization contract, not ad-hoc markdown formatting drift.

### 1.6 Additional regression axes: table detection, speed, triage

**[HIGH]** opendataloader gates `table_detection_f1` (`run.py:88-91`), `elapsed_per_doc` upper bound with **no** tolerance slack (`run.py:93-96`), `triage_recall` with tolerance, and hard `triage_fn_max` count (`run.py:98-108`). whisker guard has no equivalent.

**Adopt?** Table-detection F1 and speed: adopt if tomd pipeline exposes the signals. Triage: N/A unless hybrid path exists. At minimum document the omission.

### 1.7 Known-bad / expectedFailure / SKIP

**[MEDIUM][ACTIONABLE-NOW]** opendataloader-pdf `ci-verify.py` documents known failures and **skips** them without failing CI (`ci-verify.py:46`, `1128-1129`: `STRIKETHROUGH_KNOWN_ISSUE`). whisker guard implements tabula-style **monotonic** baselines (weak paper stable → pass: `test_guard.py:84-92`, `guard.py:192-197`) but has no explicit `expectedFailure` / `skip` entry in baseline JSON for papers under active repair.

**Adopt?** Yes. Baseline row flag `expected_failure: true` → report but do not fail unless score worsens beyond slack (extends monotonic model with explicit audit trail).

### 1.8 Missing / added item detection

**[MEDIUM]** whisker guard fails hard when a baseline pid vanishes (`guard.py:112-115`, `221`). opendataloader tracks `missing_predictions` (`evaluator.py:147`, `162`) but **`check_regression` does not fail** on missing predictions (`run.py:53-117`). whisker is stricter on dropped papers; opendataloader is stricter on **missing output files per doc** visibility.

**Adopt?** whisker should also fail (or warn→fail) when candidate markdown is missing for a corpus GT file, mirroring `prediction_available: false` semantics (`evaluator.py:101`, `61`).

### 1.9 Refresh ritual / history archive

**[LOW]** opendataloader archives dated evaluation snapshots (`generate_history.py:58-84`, `run.py:271-286`); refresh is `--force` re-run + human threshold bump (`thresholds.json`). whisker has `--update` baseline rewrite (`__main__.py:361-367`) but no dated history.

**Adopt?** Optional. History helps bisect; not blocking for CI gate.

### 1.10 Fail-open on missing thresholds file

**[LOW]** opendataloader `check_regression` returns **True** (pass) when `thresholds.json` is absent (`run.py:59-61`). whisker warns and judges new papers against floors only when baseline missing (`__main__.py:377-381`). Both fail open; whisker should fail closed in CI.

**Adopt?** Yes for CI path: missing baseline or thresholds → non-zero exit.

### 1.11 Tolerance semantics: absolute floor minus tol vs per-paper drop slack

**[MEDIUM]** opendataloader applies one `regression_tolerance` subtracted from **absolute** floors at the mean layer (`run.py:69`, `75-86`). whisker applies `GUARD_AXIS_SLACK` to **per-paper drops** vs baseline (`guard.py:180-184`) plus a separate `crossed_floor` path for sub-slack floor crossings (`guard.py:185-190`). The models are complementary, not interchangeable; whisker does not apply `threshold - tol` to corpus means.

**Adopt?** Add mean-layer `threshold - tol` (§1.1). Keep per-paper slack for baseline diff.

### 1.12 Statistical vs exact

**[LOW]** Both are deterministic exact scores; opendataloader uses rapidfuzz ratios (`evaluator_reading_order.py:37-38`), whisker uses deterministic TEDS/MHS/block-match. No gap.

---

## 2. CALIBRATION GAPS

opendataloader has **no ROC / labeled calibration**; all values in `thresholds.json` are hand-set (`thresholds.json:1-9`, `CONTRIBUTING.md:105`). whisker `calibrate.py` is methodology-stronger. Gaps are about **threshold contract shape**, not ROC math.

### 2.1 Unified multi-metric thresholds artifact

**[HIGH][ACTIONABLE-NOW]** opendataloader commits one JSON file gating six metric families with shared `regression_tolerance` (`thresholds.json:1-9`, `run.py:63-108`). `calibrate.py` emits only `unigram_coverage_{fail,review}_edge` (`__main__.py:504-515`); no path to calibrate or commit NID/TEDS/MHS floors, speed, or table-detection thresholds.

**Adopt?** Extend calibrate (or a sibling `calibrate-bench`) to output a opendataloader-shaped `thresholds.json` for bench axes, even if values remain hand-set initially.

### 2.2 Operating-point selection on bench metrics

**[MEDIUM]** opendataloader floors are engineering judgment anchored to corpus capability (e.g. TEDS 0.49, MHS 0.74 in `thresholds.json:3-4`). whisker `constants.py` ships provisional NID/TEDS/MHS floors (`constants.py:56-58`) with no fit workflow. `calibrate.py` does not accept bench metric samples.

**Adopt?** Add optional `(nid, teds, mhs, is_bad)` calibration using the same `max TPR @ FPR ceiling` selector, or document hand-set parity with opendataloader.

### 2.3 Class imbalance / corpus size

**[MEDIUM]** opendataloader evaluates ~200 docs (`CLAUDE.md:68-69`); thresholds tolerate noise via `regression_tolerance`. `calibrate.py` has no minimum-n guard beyond both-classes check (`calibrate.py:164-168`); small labeled sets can overfit edges.

**Adopt?** Require minimum n per class; report confidence warning when n < 30 (whisker CLAUDE.md calibration plan).

### 2.4 Cross-validation

**[LOW]** Neither repo cross-validates. whisker sweeps in-sample only (`calibrate.py:171-172`). Same gap.

**Adopt?** Optional holdout fold later; not opendataloader-derived.

### 2.5 Fail vs review edge ordering

**[HIGH][ACTIONABLE-NOW]** `_calibrate_main` fits fail and review edges **independently** (`__main__.py:493-499`). Nothing enforces `fail_edge <= review_edge`. opendataloader avoids this by using non-overlapping metric families (quality floors vs speed upper bound).

**Adopt?** Post-process: assert `fail_edge <= review_edge` or fit review conditional on fail.

### 2.6 Per-axis calibration

**[MEDIUM]** opendataloader sets **independent** floors per axis (`thresholds.json:2-4`). whisker calibrate is single-metric (unigram only). Bench axes share one slack constant (`constants.py:94`) but floors differ (`constants.py:56-58`).

**Adopt?** Per-axis calibrate invocations or one multi-output fit.

---

## 3. CONCRETE BUGS / EDGE-CASES IN OUR CODE

| Scenario | Function | What breaks / fools |
|----------|----------|---------------------|
| GT has no tables | `bench._table_score` → `guard._evaluate_paper` | Returns `teds=1.0` (`bench.py:128-129`); guard diffs 1.0 as real score. Opposite of opendataloader `None` exclusion. **[CRITICAL]** |
| GT gains tables later | `baseline_from_rows` / `diff_rows` | Old baseline `teds=1.0`; new real score looks like massive regression or crosses floor. **[HIGH]** |
| Paper stable below floor in baseline | `guard._evaluate_paper` | `below_floor` populated but `status=ok` (`guard.py:160-163`, `192-197`; `test_guard.py:84-92`). Corpus-mean gate would still fail opendataloader-style; whisker guard silent. **[MEDIUM]** intentional monotonic, but diverges from ODL absolute floors |
| `slack` in baseline JSON ignored | `diff_rows` | `baseline_from_rows` writes `axis_slack` (`guard.py:141`) but `diff_rows` only uses the `slack` parameter (`guard.py:205-206`), not baseline payload. CLI override silently desyncs from committed baseline. **[MEDIUM][ACTIONABLE-NOW]** |
| Duplicate `pid` in `rows` | `diff_rows` | List comprehension emits duplicate `GuardFinding`s; last-wins in dict only if keyed—report counts wrong. **[MEDIUM][ACTIONABLE-NOW]** |
| `unigram_coverage=NaN` in labels | `calibrate._confusion` | `float('nan')` makes all comparisons false; TPR/FPR undefined behavior, no error. **[HIGH][ACTIONABLE-NOW]** |
| `unigram_coverage=inf` | `calibrate._candidate_thresholds` | Thresholds include `inf+1`; degenerate ROC point. **[MEDIUM]** |
| Identical values both classes | `calibrate_threshold` | Handled via Youden fallback (`calibrate.py:178-180`; `test_calibrate.py:36-49`) but can pick threshold flagging all samples. **[LOW]** |
| Empty `rows`, nonempty baseline | `diff_rows` | `missing` lists all baseline pids → `report.failed` (`guard.py:112-115`, `221-222`). Correct. |
| Empty labels file | `_calibrate_main` | Caught (`__main__.py:484-486`). Correct. |
| Single-class labels | `calibrate_threshold` | Raises `ValueError` (`calibrate.py:166-168`). Correct. |
| All labels `pass` for review fit | `_calibrate_main` | `review_samples` has `n_pos=0` → `ValueError`. **[MEDIUM]** no partial result for fail-only fit |
| Float slack boundary | `guard._evaluate_paper` | `round(prior-cur,4) > slack` (`guard.py:180-181`); tested (`test_guard.py:55-60`). Sound. |
| Unicode pid / content | guard/calibrate | No normalization issue in guard; scoring depends on `run_bench`. **[LOW]** |
| Huge corpus | `diff_rows` | O(n) per paper; fine. **[LOW]** |
| Missing baseline file in CI | `_guard_main` | Warns, floors-only (`__main__.py:377-381`); should fail closed. **[MEDIUM]** |

---

## 4. MISSING AXIS / CHECK

| opendataloader check | Source | whisker equivalent |
|---------------------|--------|-------------------|
| Corpus `nid_mean` floor − tol | `run.py:73-76`, `thresholds.json:2` | None (guard is per-paper only) |
| Corpus `teds_mean` floor − tol | `run.py:78-81`, `thresholds.json:3` | None |
| Corpus `mhs_mean` floor − tol | `run.py:83-86`, `thresholds.json:4` | None |
| `table_detection_f1` | `run.py:88-91`, `thresholds.json:5` | None |
| `elapsed_per_doc` upper bound | `run.py:93-96`, `thresholds.json:6` | None |
| `triage_recall` / `triage_fn_max` | `run.py:98-108`, `thresholds.json:8-9` | None |
| `nid_s` / `teds_s` / `mhs_s` structure axes | `evaluator.py:44-59`, `131-137` | None |
| `missing_predictions` visibility | `evaluator.py:147`, `162` | Partial (`missing` pids only) |
| Content `must_contain` / `must_not_contain` | `ci-verify.py:163-200`, `849-861` | None (whisker score path) |
| Level 3 byte-identical option compare | `ci-verify.py:273-319` | None |
| Option coverage fail-closed | `ci-verify.py:326-354` | None |
| Stack-trace leak forbidden strings | `ci-verify.py:63-67`, `493-510` | None |

whisker **has** per-paper regression diff, explicit `--update`, and monotonic weak-baseline behavior opendataloader **does not** implement in `check_regression`.

---

## 5. TOP PORTABLE DETAIL

**Adopt:** committed `thresholds.json` with `"regression_tolerance": 0.02` and quality gate rule **`mean_score >= threshold - regression_tolerance`** for each of NID/TEDS/MHS at the **corpus aggregate** layer.

```json
{
  "nid": 0.90,
  "teds": 0.49,
  "mhs": 0.74,
  "regression_tolerance": 0.02
}
```

Implementation reference: `opendataloader-bench/src/run.py:69-86` (invoked from `opendataloader-pdf/scripts/bench.sh:115`, CI `test-benchmark.yml:148-162`). whisker already cites the 0.02 value for per-paper slack (`constants.py:89-94`); the portable piece is applying the **same tolerance to committed absolute floors on corpus means** as a backstop, not only as per-paper drop slack.

---

*Bench regression logic read from companion repo `opendataloader-bench` (cloned at `packages/whisker/research/repos/opendataloader-bench-tmp/` via `opendataloader-pdf/scripts/bench.sh:58-64`). Primary repo paths cite `packages/whisker/research/repos/opendataloader-pdf/`.*
