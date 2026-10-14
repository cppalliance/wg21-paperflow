# Red-team: whisker guard + calibrate vs marker QA

**Source repo:** `packages/whisker/research/repos/marker-v1.10.2/` (VikParuchuri/marker, shallow clone)  
**Target code:** `packages/whisker/src/whisker/guard.py`, `calibrate.py`, supporting `bench.py`, `constants.py`, `__main__.py`

## Summary

- marker CI gates **corpus means only** (`heuristic ≥ 90`, table TEDS `≥ 0.7`) with **no committed per-item baseline**; whisker guard is stricter on per-paper regression but **weaker on stratified floors, block-level localization, and pre-score normalization** that marker uses before scoring.
- marker **never calibrates** thresholds (hard-coded magic numbers); whisker `calibrate` is ahead in principle but **fits only `unigram_coverage`**, not bench axes, and **does not enforce fail/review ordering** across two independent fits.
- marker stores **per-block and per-document-type scores** in benchmark output; guard collapses to four corpus axes and ignores `reading_order` for regression entirely.
- marker unit tests rely on **substring anchors** (cross-page, cross-column, unicode); guard has **no anchor/fact layer** beneath fuzzy metrics.
- **Top portable adoption:** pandoc round-trip `normalize_markdown` before metric computation (`clean.py:38-76`) plus block-weighted fuzzy alignment (`heuristic.py:35-40,77-82`).

---

## 1. REGRESSION-GATE GAPS

### 1.1 Corpus-mean-only CI backstop (no per-item baseline diff)

**marker:** `verify_scores.py` averages all sample heuristic scores and raises if mean `< 90`; table path averages `marker_score` and raises if mean `< 0.7` (`verify_scores.py:9-13`, `16-22`). CI runs fresh benchmarks with `--max_rows 5` then verifies the **ephemeral** `result.json` (`.github/workflows/benchmarks.yml:28-35`). No committed snapshot, no per-item diff, no refresh ritual.

**guard.py:** Per-paper, per-axis diff against committed baseline (`guard.py:201-222`), missing-paper hard fail (`guard.py:113-115`, `221`), `--update` refresh (`__main__.py:361-367`).

**Verdict:** guard **already exceeds** marker on per-item regression. **Do not regress** to mean-only. Optionally adopt marker's **dual independent floor gates** (text heuristic + table TEDS as separate CI jobs) as an additional backstop when baseline is absent/stale.

**Severity:** [LOW] (whisker ahead; marker exposes a simpler pattern worth documenting, not replacing guard)

---

### 1.2 Stratification by document type and block type

**marker:** Benchmark loop records scores per `sample["classification"]` (document type) and per `gt_block["block_type"]` (`overall.py:37-38`, `67-71`). Display/reporting computes separate averages per stratum (`display/table.py:17-47`). A table-block collapse can hide inside a healthy overall mean **within CI's mean-only gate**.

**guard.py:** Single flat per-pid axis dict; no `classification`, no block-type dimension (`guard.py:65-71`, `baseline_from_rows:143-146`).

**Verdict:** **Adopt stratified reporting + optional stratified floors** for bench corpora tagged by modality (tables-heavy vs prose). Without it, one document class can regress while aggregate pid-level axes look fine.

**Severity:** [HIGH] [ACTIONABLE-NOW] (extend baseline schema + diff for strata when GT metadata exists)

---

### 1.3 Block-level (per-GT-block) score regression

**marker:** `HeuristicScorer` returns `specific_scores["by_block"]` per GT markdown block (`heuristic.py:45-46`); benchmark aggregates `averages_by_block_type` (`overall.py:69-71`). Failures localize to block type (Table, Header, etc.).

**guard.py:** Four paper-level floats only (`guard.py:65-71`); no per-block snapshot, no block-level slack.

**Verdict:** **Adopt block-level regression** (or at minimum persist `by_block` in baseline and fail on any block drop > slack). Paper-level `nid` can stay flat while specific blocks collapse (marker's whole design assumes block alignment).

**Severity:** [HIGH] [ACTIONABLE-NOW] (needs bench to export block scores; guard diffs them)

---

### 1.4 Pre-score normalization before diff

**marker:** `MarkdownCleaner` runs **pandoc MD→HTML→MD round-trip** before fuzzy compare (`clean.py:38-76`), plus math/image/HTML cleanup (`clean.py:12-36`). Scoring measures content agreement **after** format canonicalization.

**guard.py / bench.py:** Metrics use OmniDocBench `clean_string` / block matching (`bench.py:153-160`, CLAUDE.md); guard diffs **raw metric outputs** with no normalization layer at diff time. Baseline stores `round(v, 4)` (`guard.py:144`, `177-180`) but live values are unrounded floats from `BenchRow`.

**Verdict:** **Adopt marker-style pre-score normalization** (or enforce symmetric rounding: round live axes to 4 decimals before diff). Without it, formatting-only churn can fire false regressions or slip through at IEEE boundaries.

**Severity:** [HIGH] [ACTIONABLE-NOW]

---

### 1.5 Order / reading-order as scored component

**marker:** Heuristic blends **80% block-weighted fuzzy score + 20% Kendall-τ order score** (`heuristic.py:39-40`, `49-71`). Order is not advisory; it moves the gated number.

**guard.py:** `reading_order` stored in baseline axes (`guard.py:71`) but **excluded from `GUARD_REGRESSION_AXES`** (`constants.py:99`); never fails regression.

**Verdict:** **Partially adopt:** keep content axes primary, but add optional order regression slack (or a composite axis matching marker's 0.8/0.2) for corpora where reading order is part of the contract. marker proves order belongs in the score, not only in a side column.

**Severity:** [MEDIUM]

---

### 1.6 Absolute floors without baseline (CI backstop)

**marker:** Hard floors `90` (0–100 heuristic scale) and `0.7` (TEDS) regardless of history (`verify_scores.py:12-13`, `21-22`).

**guard.py:** Floors on `nid/teds/mhs` at 0.90/0.80/0.80 (`constants.py:56-58`); `crossed_floor` for sub-slack downward floor cross (`guard.py:185-190`); monotonic known-bad (`guard.py:166-169`, tests `test_guard.py:84-98`).

**Verdict:** guard **already implements** marker-style floors plus monotonic weak baselines marker lacks. Ensure CLI/guard **always fails** `new_below_floor` and consider separate table-only floor gate mirroring marker's `--type table` path.

**Severity:** [LOW] (mostly present)

---

### 1.7 known-bad / expectedFailure

**marker:** No `expectedFailure` equivalent; failed benchmark samples are **dropped** from averages (`overall.py:72-77`, `display/dataset.py:14-15`).

**guard.py:** Monotonic model: weak baseline not re-flagged unless worse (`guard.py:171-197`, `test_guard.py:84-98`).

**Verdict:** guard is **ahead**. Do not adopt marker's silent drop; it hides collateral damage.

**Severity:** [LOW]

---

### 1.8 Missing / added-item detection

**marker:** Skips failed indices; no concept of corpus membership contract (`overall.py:72-77`).

**guard.py:** Missing baseline pid → hard fail (`guard.py:221`, `113-115`). New pids → `STATUS_NEW` pass (`guard.py:165-169`).

**Verdict:** Missing detection is **good**. **Gap:** added papers pass without review—marker N/A. Consider [MEDIUM] flagging `STATUS_NEW` when baseline exists (require explicit `--update` to bless additions).

**Severity:** [MEDIUM] [ACTIONABLE-NOW]

---

### 1.9 Refresh ritual

**marker:** None; thresholds are code constants (`verify_scores.py:12`, `21`).

**guard.py:** `--update` writes baseline (`__main__.py:361-367`).

**Verdict:** guard **ahead**. No change.

**Severity:** [LOW]

---

### 1.10 Tolerance semantics: statistical vs exact

**marker:** Fuzzy `partial_ratio_alignment` with `score_cutoff=70` (`heuristic.py:77-82`); CI thresholds are **exact** numeric compares on **means** (no slack).

**guard.py:** Deterministic slack `GUARD_AXIS_SLACK = 0.02` on rounded drops (`guard.py:177-184`, `constants.py:94`).

**Verdict:** guard's determinism matches whisker invariants. **Adopt** marker's **length-weighted block scoring** (`heuristic.py:35-39`) so slack applies to weighted content, not just paper mean.

**Severity:** [MEDIUM]

---

## 2. CALIBRATION GAPS

### 2.1 marker does not calibrate at all

**marker:** Floors `90` and `0.7` are engineering constants in `verify_scores.py:12-13`, `21-22`. No ROC, no labeled fit, no TPR/FPR reporting.

**calibrate.py:** Full ROC sweep, max-TPR-at-FPR with Youden fallback (`calibrate.py:149-185`).

**Verdict:** whisker is **ahead**. Gap is **coverage of marker's metric space**, not methodology.

**Severity:** [LOW] (field baseline)

---

### 2.2 Multi-threshold / multi-axis calibration

**marker:** Separate gates for overall heuristic vs table TEDS (`verify_scores.py:5-33`, CI runs both `benchmarks.yml:28-35`). LLM scorer defines **eight sub-scores** (overall, text, formatting, section_headers, tables, forms, equations, lists, images) (`llm.py:89-91`).

**calibrate.py:** Fits only `unigram_coverage_fail_edge` and `unigram_coverage_review_edge` from labels (`__main__.py:488-499`). **No** calibration for `nid`, `teds`, `mhs`, `reading_order`, or block-level scores.

**Verdict:** **Adopt per-axis calibration** for bench floors (`NID_FLOOR`, `TEDS_FLOOR`, `MHS_FLOOR`) using the same ROC machinery, emitting a `thresholds.json` comparable to opendataloader/marker floor sets.

**Severity:** [HIGH] [ACTIONABLE-NOW]

---

### 2.3 Operating-point selection and class definitions

**marker:** N/A (fixed floors).

**calibrate.py:** Positive = `label == fail` or `label in (fail, review)` (`__main__.py:488-491`); default `target_fpr=0.05` (`calibrate.py:43`, `__main__.py:466`).

**Verdict:** Reasonable. **Gap:** no check that `fail_edge <= review_edge` after independent fits—inverted edges silently break the verdict ladder.

**Severity:** [HIGH] [ACTIONABLE-NOW]

---

### 2.4 Cross-validation / holdout

**marker:** N/A.

**calibrate.py:** Single-batch fit on all labels; no k-fold, no holdout report.

**Verdict:** **Adopt** at least a held-out validation split reporting TPR/FPR on unseen pids before promoting to `constants.py`.

**Severity:** [MEDIUM]

---

### 2.5 Class imbalance

**marker:** N/A.

**calibrate.py:** Reports `n_pos`/`n_neg` (`calibrate.py:81-87`) but selection uses raw counts; tiny minority class makes ROC points unstable.

**Verdict:** **Adopt** minimum class size guard (e.g. refuse fit if `n_pos < 5`) and report Wilson/confidence bounds on chosen operating point.

**Severity:** [MEDIUM] [ACTIONABLE-NOW]

---

### 2.6 Metric choice for calibration

**marker:** Heuristic 0–100 scale, TEDS 0–1 (`verify_scores.py` vs `table/scoring.py:92-108`); different scales, different gates.

**calibrate.py:** Only `unigram_coverage` (0–1).

**Verdict:** Extend calibrate to accept `(metric_name, samples)` tuples for each axis used by guard floors.

**Severity:** [HIGH] [ACTIONABLE-NOW]

---

## 3. CONCRETE BUGS / EDGE-CASES IN OUR CODE

| Scenario | Function | What breaks | Severity |
|----------|----------|-------------|----------|
| `unigram_coverage = NaN` in labels | `calibrate._confusion` (`calibrate.py:110-111`) | `NaN < t` is False → bad papers never flagged; TPR understated | [CRITICAL] [ACTIONABLE-NOW] |
| Independent fail/review fits invert edges | `__main__._calibrate_main` (`__main__.py:494-499`) | e.g. fail_edge=0.92, review_edge=0.88 → papers in band mis-verdict | [HIGH] [ACTIONABLE-NOW] |
| Baseline stores rounded values, live raw floats | `guard._evaluate_paper` (`guard.py:144`, `173-180`) | Slack boundary asymmetry vs baseline commit | [HIGH] [ACTIONABLE-NOW] |
| `baseline["axis_slack"]` ignored | `guard.diff_rows` (`guard.py:141`, `205-206`, `214`) | Committed slack and CLI `--slack` can diverge silently | [MEDIUM] [ACTIONABLE-NOW] |
| Wrong/missing baseline `kind` | `guard.diff_rows` (`guard.py:213-214`) | Uses `.get("rows", {})` only; alien JSON partially diffs | [MEDIUM] [ACTIONABLE-NOW] |
| Duplicate `pid` in `rows` | `guard.diff_rows` (`guard.py:216-218`) | Duplicate findings, ambiguous report | [MEDIUM] [ACTIONABLE-NOW] |
| Empty corpus, no baseline | `guard.diff_rows` | Empty findings, `failed=False` (`guard.py:112-115`) | [MEDIUM] [ACTIONABLE-NOW] |
| Empty corpus, with baseline | `guard.diff_rows` | All pids in `missing` → fail (correct) | — |
| Single-class labels | `calibrate.calibrate_threshold` (`calibrate.py:166-169`) | `ValueError` (correct) | — |
| All identical coverage values | `calibrate._candidate_thresholds` (`calibrate.py:130-133`) | Degenerate ROC; tie-break picks max threshold (`calibrate.py:177`) | [LOW] |
| `target_fpr=0` with overlap | `calibrate.calibrate_threshold` | Youden fallback (`calibrate.py:178-180`); tested | — |
| Huge corpus | `guard.diff_rows` | O(n) per paper; no issue (marker also linear) | [LOW] |
| Unicode in markdown | bench metrics | Handled by normalizers; guard only sees floats | — |
| marker table verify denominator bug | `verify_scores.verify_table_scores` (`verify_scores.py:20`) | Uses `len(data)` not `len(data["marker"])` — lesson: wrong aggregate denominator hides regressions | [LOW] (their bug, our lesson) |

---

## 4. MISSING AXIS / CHECK

| marker check | Evidence | whisker equivalent | Adopt? |
|--------------|----------|-------------------|--------|
| Substring / anchor assertions | `tests/converters/test_pdf_converter.py:14-28`, `tests/renderers/test_markdown_renderer.py:13-14` | None in guard/bench gate | [HIGH] — per-paper `facts` file (anchors + ordered `find`) under metrics |
| Cross-page / cross-column join integrity | `test_pdf_converter.py:18-28` | None | [MEDIUM] |
| Multi-format smoke (epub, xlsx, html, docx, pptx) | `test_pdf_converter.py:31-78` | WG21 PDF/HTML only | [MEDIUM] (tomd scope) |
| Block-type score floors | `overall.py:69-71`, `display/table.py:33-47` | None | [HIGH] |
| Separate table benchmark gate | `verify_scores.py:16-22`, CI `benchmarks.yml:32-35` | `teds` axis only inside unified bench | [MEDIUM] — optional split job |
| LLM sub-scores (tables, equations, headers) | `llm.py:89-91` | None (whisker is no-LLM) | [LOW] — not applicable |
| Inference timing / throughput | `overall.py:53`, `throughput/main.py` | None | [LOW] — perf, not quality |
| OCR-garble / unicode regression | `test_garbled_pdf.py:25`, `test_table_processor.py:29` | None at guard layer | [MEDIUM] — corpus fixtures |
| Weighted-by-length block score | `heuristic.py:35-39` | Hungarian block match, unweighted at guard | [MEDIUM] |

---

## 5. TOP PORTABLE DETAIL

**Adopt: pandoc round-trip normalization before scoring, then length-weighted fuzzy block alignment.**

```38:76:packages/whisker/research/repos/marker-v1.10.2/benchmarks/overall/scorers/clean.py
    @staticmethod
    def normalize_markdown(md_text: str) -> str:
        with tempfile.TemporaryDirectory() as tmp_dir:
            ...
            subprocess.run(['pandoc', str(input_file), '-f', 'markdown+tex_math_dollars', ...])
            ...
            subprocess.run(['pandoc', str(html_file), '-f', 'html', '-t', 'markdown+tex_math_dollars', ...])
```

```35:40:packages/whisker/research/repos/marker-v1.10.2/benchmarks/overall/scorers/heuristic.py
        gt_weights = [len(g) for g in gt_markdown]
        weighted_scores = [score * weight for score, weight in zip(scores, gt_weights)]
        overall_score = sum(weighted_scores) / max(1, sum(gt_weights))
        overall_score = overall_score * 0.8 + order_score * 0.2
```

```77:82:packages/whisker/research/repos/marker-v1.10.2/benchmarks/overall/scorers/heuristic.py
            result = fuzz.partial_ratio_alignment(substr, main_string, score_cutoff=threshold)
            ...
            threshold: int = 70
```

**Why this one:** marker's CI false-positive rate is dominated by formatting drift; pandoc canonicalization is their explicit fix (`clean.py:13`). Length weighting prevents a single long block from masking many short GT block failures (`heuristic.py:35-39`). **`score_cutoff=70`** is their hand-tuned alignment gate—directly analogous to calibrating block-matching acceptance NED in whisker.

**Concrete whisker action:** run `normalize_markdown` (or equivalent) on candidate+reference **before** `run_bench`, persist per-block weighted scores in the guard baseline, and calibrate block acceptance threshold from labeled block outcomes—not from corpus-mean `overall` alone.

**Severity:** [HIGH] [ACTIONABLE-NOW] (bench pipeline change + guard baseline schema extension)
