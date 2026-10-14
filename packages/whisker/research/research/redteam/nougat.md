# Red-team: whisker guard/calibrate vs Nougat QA

- Nougat has **no committed regression baseline, no CI, and no pytest QA suite**; evaluation is offline JSON + running corpus means (`test.py:79-84`). whisker guard is already ahead on regression plumbing, but Nougat's **modality-stratified dual metrics** expose blind spots guard's scalar `overall` axis hides.
- Nougat scores **Text / Math / Tables separately** with **char-NED + set-F1 per stratum** (`metrics.py:63-117`, `compute_metrics:27-44`); guard diffs `nid/teds/mhs/overall` but has **no set-F1 axis** and lets `overall` absorb cross-stratum tradeoffs.
- Nougat **strips math/tables from text** before the text metric and applies **post-hoc normalization** (`split_text:70-81`, `postprocessing.py:178-187`); guard scores precomputed bench axes with no stratum-aware normalization pass or failure-marker gate.
- Nougat's **`minlen=4` sample exclusion** and **`[MISSING_PAGE_*]` failure taxonomy** (`metrics.py:29-30`, `predict.py:178-191`) show whisker lacks **short-corpus / failed-conversion preconditions**; empty or broken papers can still produce plausible floats in `run_bench`.
- **Top portable detail:** per-stratum **set-F1** (`f_measure` on word-token sets, `metrics.py:39-43`) alongside char-NED, reported independently per Text/Math/Tables, never averaged into one headline number (`metrics.py:114-117`).

---

## 1. REGRESSION-GATE GAPS

### 1.1 No per-item snapshot diff (Nougat anti-pattern; guard must not regress)

**Nougat:** `test.py` accumulates per-batch running means and writes one JSON blob (`test.py:73-95`). `python -m nougat.metrics` prints **corpus means per stratum** only (`metrics.py:116-117`). There is no committed baseline, no diff, no `--update` ritual, and **no `.github` CI** in the repo.

**guard.py:** Per-paper baseline JSON, missing-paper hard fail, `--update` refresh (`guard.py:201-222`, `__main__.py:329-331`).

**Adopt?** **Do not copy Nougat's aggregate-only eval.** Guard already fixes the exact failure mode Nougat encodes. Keep guard; optionally add a CI job that fails if someone reintroduces mean-only gating like `bench --baseline`.

**Severity:** [CRITICAL] (negative control)

---

### 1.2 Modality-stratified regression (Text / Math / Tables)

**Nougat:** `split_text` partitions each page into text, inline/display math, and tabular LaTeX via regex (`metrics.py:22-24,63-83`). The CLI loop scores **three strata independently** and prints separate means (`metrics.py:104-117`); it never collapses Text+Math+Tables into one regression decision.

**guard.py:** Axes are `nid` (block text), `teds` (tables), `mhs` (headings), plus `overall = mean(nid,teds,mhs)` in `GUARD_REGRESSION_AXES` (`constants.py:96-99`, `bench.py:161`). A table-only collapse with stable text can leave `overall` within slack while `teds` regresses sub-slack if compensated by `nid`/`mhs` gains (see `test_guard.py:109-114`: uniform small drops pass).

**Adopt?** **Yes [ACTIONABLE-NOW].** Drop `overall` from the regression axes (keep it report-only), or fail on **any** stratum regression with **no cross-axis compensation**. Mirror Nougat: never let one modality's gain cancel another's loss.

**Severity:** [HIGH] [ACTIONABLE-NOW]

---

### 1.3 Dual metric per stratum: order-sensitive NED + order-invariant set-F1

**Nougat:** Every stratum gets both `edit_dist` (char-level NED, `metrics.py:31`) and `f_measure` on **word-token sets** (`metrics.py:39-43`). Set-F1 is order-invariant content coverage; edit distance is sequence fidelity. Both are printed per stratum (`metrics.py:116-117`).

**guard.py:** Bench `nid` is block-matched NED-like; `reading_order` is advisory (`bench.py:18-20`). There is **no set-F1 / unigram-recall axis on the bench/guard path** (only on the reference-free `score.py` path via `unigram_coverage`).

**Adopt?** **Yes.** Add `set_f1` (or token-set F1 on normalized text) to `BenchRow` and baseline; regress it independently. A reflow that preserves words but scrambles order should not mask missing content the way NID-only guard can.

**Severity:** [HIGH]

---

### 1.4 Pre-score stratification / normalization-before-diff

**Nougat:** Before text metrics, inline math, display math, and `tabular` blocks are **stripped from the text channel** (`metrics.py:70-81`). Postprocessing applies `remove_numbers` (strip digits/underscores for similarity), `markdown_compatible`, and hallucination removal before output (`postprocessing.py:178-187,332-363`).

**guard.py:** Metrics run on full markdown via `block_metrics` / `teds` / `mhs` (`bench.py:157-160`). No stratum strip pass; formatting-only churn in math delimiters can move `nid` without semantic loss.

**Adopt?** **Partially.** whisker already has `normalized_text` (OmniDocBench `clean_string`); extend bench to score text **after** table/math extraction analogous to `split_text`, so guard diffs content axes not delimiter churn. Full Nougat postprocess is out of scope for guard.

**Severity:** [MEDIUM]

---

### 1.5 Short-sample / failed-page exclusion (`minlen`)

**Nougat:** `compute_metrics` returns `{}` when `len(pred) < minlen or len(gt) < minlen` with `minlen=4` (`metrics.py:27-30`). Those pages are **omitted from stratum averages** (`metrics.py:93-96`), not scored as zero.

**guard.py:** `run_bench` always emits floats; empty candidate+reference tables score `teds=1.0` (`bench.py:128-129`). No minimum content length; a blank conversion can look "perfect" on empty-table papers.

**Adopt?** **Yes [ACTIONABLE-NOW].** Guard should fail papers below a minimum token/block count (or emit `status=insufficient_content`) instead of diffing meaningless 1.0 scores.

**Severity:** [HIGH] [ACTIONABLE-NOW]

---

### 1.6 Explicit failure markers vs silent low scores

**Nougat:** Inference marks failed pages with `[MISSING_PAGE_EMPTY:…]`, `[MISSING_PAGE_FAIL:…]`, `[MISSING_PAGE_POST]` (`predict.py:178-191`, `postprocessing.py:323-328`). Failure detection uses generation-score variance heuristics (`model.py:627-645`, `StoppingCriteriaScores` threshold `0.015` at `model.py:443-464`).

**guard.py:** No conversion-status field in `BenchRow` or baseline. `_load_corpus_pairs` skips missing candidates with a warning (`__main__.py:256-258`) but guard never sees **partial** failures inside scored markdown.

**Adopt?** **Yes.** Baseline rows should carry `conversion_ok: bool` or count `[MISSING_PAGE` markers; guard fails on new markers even if metrics are flat.

**Severity:** [MEDIUM]

---

### 1.7 Floors / known-bad / expectedFailure

**Nougat:** No absolute floors, no monotonic known-bad, no xfail. Weak pages stay in the running mean unless `minlen` drops them.

**guard.py:** Per-axis floors + monotonic known-bad (`guard.py:160-198`, `test_guard.py:84-99`).

**Adopt?** **Keep whisker.** Nougat provides no model here. Optional: baseline flag `expected_failure` for papers that should only fail on regression (analogous to Nougat `--no-skipping` bypass, `predict.py:74-77`).

**Severity:** [LOW] (whisker leads)

---

### 1.8 Missing / added corpus items

**Nougat:** Eval set is a fixed `jsonl` (`README.md:172-174`); no runtime check for added/removed items vs a committed manifest.

**guard.py:** Missing baseline PIDs hard-fail (`guard.py:221,113-115`); new PIDs pass as `STATUS_NEW` (`guard.py:165-169`).

**Adopt?** **Keep missing detection; tighten new-paper policy.** Nougat's closed jsonl implies **no silent new items**; add `--strict-corpus` to fail `STATUS_NEW` until baseline update (same recommendation as Docling red-team).

**Severity:** [MEDIUM] [ACTIONABLE-NOW]

---

### 1.9 Refresh ritual

**Nougat:** `--recompute` on predict discards cached `.mmd` (`predict.py:53-55,139-142`); no metric baseline refresh.

**guard.py:** `--update` rewrites baseline (`__main__.py:361-367`).

**Adopt?** **Keep whisker; add CI lockout** (refuse `--update` when `CI=true`), since Nougat has no CI guard at all.

**Severity:** [MEDIUM] [ACTIONABLE-NOW]

---

### 1.10 Statistical vs exact tolerance

**Nougat:** Metrics are **exact deterministic functions** on stripped strings; no slack, no ROC gate on eval output. Training uses validation means only (`lightning_module.py:96-98`).

**guard.py:** Absolute drop `> slack` with 4-decimal drop rounding (`guard.py:177-184`).

**Adopt?** **Partially.** Round **both** `prior` and `cur` to 4 decimals before subtraction (today only `drop` is rounded). Nougat's `edit_dist` uses `max(len(pred), len(gt))` denominator (`metrics.py:31`); consider relative slack `(prior-cur)/max(prior,ε)` for high-baseline papers.

**Severity:** [MEDIUM] [ACTIONABLE-NOW] (rounding both sides)

---

### 1.11 Baseline `axis_slack` field ignored

**Nougat:** N/A.

**guard.py:** Written at `guard.py:141`, never read in `diff_rows` (`guard.py:205-206`).

**Adopt?** **Yes [ACTIONABLE-NOW].** `slack = baseline.get("axis_slack", slack)`.

**Severity:** [HIGH] [ACTIONABLE-NOW]

---

## 2. CALIBRATION GAPS

### 2.1 Nougat does not ROC-calibrate eval thresholds

**Nougat:** No labeled operating-point fit on eval metrics. Training validation logs mean `edit_dist`, BLEU, etc. (`lightning_module.py:96-98`). Failure heuristics use hand-set constants (`model.py:443` threshold `0.015`, `model.py:635` varvar `< 0.045`).

**calibrate.py:** Full ROC sweep with FPR ceiling + Youden fallback (`calibrate.py:149-185`).

**Adopt?** **Keep whisker ROC** for coverage edges; optionally document Nougat's generation thresholds as **reference-free advisory** candidates, not bench guard floors.

**Severity:** [LOW] (whisker leads on calibration)

---

### 2.2 Staircase / Gini multi-threshold calibration (anomaly detection)

**Nougat:** `Staircase.fit` learns **multiple class boundaries** by minimizing Gini impurity on token-length or score distributions (`staircase.py:216-296`, `statistic_fit:180-214`). `predict` assigns discrete classes via `stair_func` (`staircase.py:17-18,307-314`).

**calibrate.py:** Single scalar threshold per fit; two independent fits for fail/review (`__main__.py:494-499`).

**Adopt?** **Partially.** For three-way verdict (pass/review/fail), fit **two ordered thresholds** in one pass (Nougat-style staircase) instead of two independent ROC runs that can invert the band.

**Severity:** [MEDIUM]

---

### 2.3 Per-axis / per-stratum calibration

**Nougat:** Implicitly per-stratum via `split_text` reporting (`metrics.py:104-117`); no threshold commit.

**calibrate.py:** Only `unigram_coverage` fail/review edges (`__main__.py:488-499`). No `nid/teds/mhs/set_f1` floor fitting.

**Adopt?** **Yes.** Extend calibrate to labeled bench rows: ROC-fit `TEDS_FLOOR`, `NID_FLOOR`, `MHS_FLOOR` per axis with the same FPR machinery.

**Severity:** [HIGH]

---

### 2.4 Fail/review edge ordering not enforced

**Nougat:** N/A (no two-edge band).

**calibrate.py:** Independent `fail_fit` and `review_fit` (`__main__.py:494-499`).

**Adopt?** **Yes [ACTIONABLE-NOW].** Assert `fail_edge <= review_edge` or constrain review candidates to thresholds `>= fail_edge`.

**Severity:** [HIGH] [ACTIONABLE-NOW]

---

### 2.5 Class imbalance / short-corpus / cross-validation

**Nougat:** `minlen` drops ambiguous pages from metrics (`metrics.py:29-30`); no held-out calibration.

**calibrate.py:** Requires both classes (`calibrate.py:164-169`); no k-fold, no minimum class size warning, no bootstrap FPR CI.

**Adopt?** **Yes.** With Nougat-scale eval sets (often hundreds of pages but few labeled bad conversions), warn when `n_pos < 10` or `n_neg < 10`; report leave-one-out max FPR.

**Severity:** [MEDIUM]

---

### 2.6 NaN propagation in aggregate metrics

**Nougat:** `meteor` returns `np.nan` on missing NLTK data (`metrics.py:37-38`); `np.mean(vals)` in `test.py:84` **poisons** the running average.

**calibrate.py:** No NaN guard on sample values.

**Adopt?** **Yes [ACTIONABLE-NOW].** Reject NaN/inf in `calibrate_threshold` inputs; guard should reject non-finite axis values.

**Severity:** [HIGH] [ACTIONABLE-NOW]

---

### 2.7 Operating-point selection: corpus mean vs worst stratum

**Nougat:** Always reports **mean** per stratum (`metrics.py:117`, `test.py:79`). No worst-page or 5th-percentile gate.

**calibrate.py:** Per-paper samples only; no `min(axis)` rollup across nid/teds/mhs for bench calibration.

**Adopt?** **Yes for bench floors.** Calibrate on `min(nid,teds,mhs)` per labeled paper so one collapsed stratum drives the edge (Nougat mean would hide it).

**Severity:** [MEDIUM]

---

## 3. CONCRETE BUGS / EDGE-CASES IN OUR CODE

| Function | Scenario | Nougat lesson | Actual behavior | Severity |
|----------|----------|---------------|-----------------|----------|
| `diff_rows` | Baseline `axis_slack: 0.05`, CLI default `0.02` | Nougat has no baseline slack; committed constants should bind | Ignores baseline field (`guard.py:141,205-206`) | [HIGH] [ACTIONABLE-NOW] |
| `diff_rows` | `nid` +0.03, `teds` -0.03, `mhs` stable; `overall` unchanged | Nougat never averages strata for gate | May pass if each axis drop ≤ slack (`guard.py:172-184`) | [HIGH] |
| `diff_rows` | Duplicate `pid` in `rows` | Nougat dedupes by page index in jsonl | Duplicate findings; set hides dup (`guard.py:216-221`) | [MEDIUM] [ACTIONABLE-NOW] |
| `diff_rows` | Axis value `NaN` in baseline or current | Nougat `meteor` NaN poisons means (`metrics.py:37-38`, `test.py:84`) | `NaN < floor` False; `drop > slack` False → silent pass (`guard.py:162,180-181`) | [HIGH] [ACTIONABLE-NOW] |
| `diff_rows` | Empty `rows`, `baseline=None` | Nougat skips eval with no dataset | `failed=False`, empty report (`guard.py:216-222`) | [MEDIUM] |
| `run_bench` / `_evaluate_paper` | Both sides empty tables | Nougat `minlen` skips; empty stratum omitted | `teds=1.0` (`bench.py:128-129`) | [HIGH] |
| `run_bench` | Candidate is `"[MISSING_PAGE_FAIL:3]"` only | Nougat marks failure explicitly (`predict.py:185`) | Still computes metrics; may score ~0 or odd 1.0 | [MEDIUM] |
| `calibrate_threshold` | Sample contains `float("nan")` | Nougat NaN mean bug | Undefined comparisons (`calibrate.py:110-111`) | [HIGH] [ACTIONABLE-NOW] |
| `calibrate_threshold` | All samples identical value, mixed labels | Nougat excludes `minlen` ties by omission | Youden fallback; arbitrary tie-break (`calibrate.py:179-180`) | [MEDIUM] |
| `_calibrate_main` | Fail fit → 0.92, review fit → 0.88 | Nougat uses ordered staircase classes (`staircase.py:255-295`) | Emits inverted band (`__main__.py:494-499`) | [HIGH] [ACTIONABLE-NOW] |
| `_calibrate_main` | 30 fail, 2 pass labels | Nougat eval sets are large but unlabeled for ROC | Fits without imbalance warning (`__main__.py:488-502`) | [MEDIUM] |
| `_load_corpus_pairs` | New `*.gt.md` not in baseline | Nougat fixed jsonl (closed set) | `STATUS_NEW` passes (`guard.py:169`) | [MEDIUM] |
| `calibrate_threshold` | `target_fpr=-0.1` or `1.5` | — | No validation; all thresholds "feasible" or none (`calibrate.py:174-180`) | [LOW] [ACTIONABLE-NOW] |
| `get_metrics` analogue | Unicode math in GT, ASCII in pred | Nougat uses raw NLTK token split (`metrics.py:32-33`) | whisker normalizer handles; guard inherits bench behavior | OK |

---

## 4. MISSING AXIS / CHECK (Nougat evaluates, whisker guard has no equivalent)

| Nougat check | Source | Whisker gap |
|--------------|--------|-------------|
| Text stratum char-NED | `metrics.py:31`, text channel after `split_text` | Partially covered by `nid`; not stratum-isolated |
| Text stratum **set-F1** (order-invariant) | `metrics.py:39-43` | **Absent** on bench/guard path |
| Math stratum NED + set-F1 | `metrics.py:104-117`, math lists | **Absent** (inline LaTeX not a guard axis) |
| Tables stratum NED + set-F1 | `metrics.py:104-117`, `table_reg` | Partially `teds`; no set-F1 on table cell tokens |
| BLEU / METEOR per stratum | `metrics.py:34-37` | Not scored (acceptable; not used for gating in Nougat either) |
| `[MISSING_PAGE_*]` failure count | `predict.py:178-191` | No marker detection in guard |
| Generation repetition / early-stop confidence | `model.py:627-645`, `StoppingCriteriaScores:443-474` | No reference-free confidence in bench row |
| `minlen` eligibility flag | `metrics.py:29-30` | No `scorable: bool` on baseline row |
| Per-page granularity | `test.py:56-72` (page-level loop) | Guard is per-paper only |
| `--no-skipping` bypass audit | `predict.py:74-77`, `README.md:83` | No baseline flag for "failure detection off" |

---

## 5. TOP PORTABLE DETAIL

**Adopt Nougat's per-stratum dual metric: char-NED plus word-set F1, never merged.**

```python
# metrics.py:31-43 (inside compute_metrics, repeated per Text/Math/Tables stratum)
metrics["edit_dist"] = edit_distance(pred, gt) / max(len(pred), len(gt))
reference = set(gt.split())
hypothesis = set(pred.split())
metrics["f_measure"] = nltk.scores.f_measure(reference, hypothesis)
```

Reporting contract (do not average across strata):

```python
# metrics.py:104-117
for i, (gt, pr) in enumerate(zip(split_text(args.gt), split_text(args.pred))):
    sub = ["Text", "Math", "Tables"][i]
    metrics = get_metrics(gt, pr)
    print({key: sum(values) / len(values) for key, values in metrics.items()})
```

**For whisker today:** add `text_set_f1`, `math_set_f1`, `table_set_f1` (or one `set_f1` on normalized full-doc tokens) to `BenchRow` and baseline JSON; regress each independently with `GUARD_AXIS_SLACK`. Use `edit_dist`-style NED only as the sequence axis; use set-F1 as the **content-presence** axis mirroring Nougat's separation from order-sensitive NED, aligned with whisker's existing unigram-coverage philosophy on the score path.

**Single anchor:** `metrics.py:39-43` (set-F1) + `metrics.py:104-117` (per-stratum reporting, no cross-stratum mean gate).

---

*Sources: nougat clone at `packages/whisker/research/repos/nougat/` (facebookresearch/nougat, shallow clone June 2026). Whisker: `guard.py`, `calibrate.py`, `bench.py`, `constants.py`, `__main__.py`, `test_guard.py`, `test_calibrate.py`.*
