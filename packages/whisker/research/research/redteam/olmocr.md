# Red-team: whisker guard/calibrate vs olmOCR QA

- olmOCR gates on **~7 JSONL strata × thousands of binary fact assertions** (present/absent/order/table/math/format/footnote/baseline), not committed scalar metric snapshots; whisker guard stores four floats per paper and cannot catch localized regressions olmOCR would flag at test ID granularity (`benchmark.py:33-159`, `tests.py:23-33`, `README.md:7-10`).
- olmOCR **normalizes before every check** (NFC, hyphen/quote folding, markdown strip, whitespace collapse) and uses **length-relative fuzzy tolerance** via `max_diffs` (`tests.py:47-80`, `168-169`); guard applies one global `0.02` absolute slack on pre-rounded floats and ignores committed `axis_slack` in the baseline payload (`guard.py:141,177-184,201-206`).
- olmOCR **macro-averages per JSONL category** (ArXiv, Tables, Multi-column, …) so one stratum cannot hide in a corpus mean; whisker folds `nid/teds/mhs` into `overall` and gates all axes with the same slack (`benchmark.py:343-350,387-388`, `bench.py:161`, `constants.py:99`).
- olmOCR ships **148 meta-tests** on the assertion engine alone (`tests/test_tests.py`, 148 `def test_`); guard has ~12 synthetic cases in `test_guard.py` and no duplicate-pid, schema, NaN, or vacuous-corpus tests.
- olmOCR does **not ROC-calibrate**; thresholds are per-test `max_diffs` and a hard `0.5` table floor (`tests.py:168-169,396`). `calibrate.py` is ahead on ROC fitting, but lacks macro/stratified operating points, per-axis floor fit, and fail/review ordering constraints.

---

## 1. REGRESSION-GATE GAPS

### 1.1 Per-fact binary assertions vs per-paper scalar snapshots

**olmOCR:** Each JSONL line is an independent pass/fail unit test keyed by `(pdf, page, id)`; scoring is the fraction of tests passed, with per-test explanations (`benchmark.py:79-137`, `tests.py:114-125`). README explicitly rejects whole-page edit distance as the primary metric because it misses localized failures (`README.md:10-11`).

**guard.py:** Commits and diffs four floats per paper (`guard.py:65-71,136-147`). A regression that drops one table caption or swaps section order while preserving aggregate NID/TEDS can pass.

**Adopt?** **Partially.** Full fact JSONL is a follow-on (see gap-matrix #9), but guard should at minimum diff **verdict transitions** and optional per-paper fact pass counts alongside metrics. Scalar-only baselines are a strict subset of olmOCR's contract.

**Severity:** [CRITICAL]

---

### 1.2 Normalization-before-diff

**olmOCR:** `normalize_text()` runs on both reference query and candidate markdown before every presence/order/table check: `<br>` folding, bold/italic strip, whitespace collapse, NFC, smart-quote/hyphen replacement (`tests.py:47-80,150-154,212`).

**guard.py:** Diffs raw `BenchRow` floats; only the **drop** is rounded to 4 decimals (`guard.py:177-180`). Baseline rows are rounded on write (`guard.py:144`) but current values are not normalized to the same grid before subtraction.

**Adopt?** **Yes [ACTIONABLE-NOW].** Round **both** `prior` and `cur` to 4 decimals before computing `drop`. Metric inputs (`bench.py`) already use deterministic normalizers; the guard boundary should not be IEEE-noise-sensitive.

**Severity:** [HIGH] [ACTIONABLE-NOW]

---

### 1.3 Length-relative / per-assertion tolerance semantics

**olmOCR:** Fuzzy match threshold is derived per test: `threshold = 1.0 - (max_diffs / len(reference_query))` (`tests.py:168-169`). Table tests floor at `max(0.5, threshold)` (`tests.py:395-396`). Tolerance scales with content length, not a global constant.

**guard.py:** One `GUARD_AXIS_SLACK = 0.02` for every axis on every paper (`constants.py:94`, `guard.py:180-184`).

**Adopt?** **Partially.** Keep absolute slack for bounded [0,1] metrics, but consider axis-specific slack (TEDS vs NID) mirroring olmOCR's per-test `max_diffs`. A proportional drop cap `(prior-cur)/prior > slack` catches collapse on high baselines.

**Severity:** [MEDIUM]

---

### 1.4 Modality-stratified scoring (macro-average, no collapse)

**olmOCR:** Overall score is the **mean of per-JSONL pass rates**, not micro-average over all tests (`benchmark.py:343-350,387-388`). Bootstrap CI resamples **within each JSONL stratum** then averages category means (`utils.py:47-60`, `benchmark.py:328-330`). GRPO reward supports the same macro-average toggle (`grpo_train.py:1118-1161`).

**guard.py:** `overall = mean(nid, teds, mhs)` per paper (`bench.py:161`) and diffs `overall` as a regression axis (`constants.py:99`). A table regression can be averaged away by strong NID/MHS on the same paper.

**Adopt?** **Yes.** Guard report should show **which axis regressed** (already does) and optionally gate on `min(nid,teds,mhs)` or macro-average of axis pass/fail bits, not unweighted mean. olmOCR's design principle: never let one modality hide another.

**Severity:** [HIGH]

---

### 1.5 Per-page / per-item granularity

**olmOCR:** Tests bind to `(pdf, page)`; missing MD for a page is a hard error (`benchmark.py:94-101`). Every PDF page must have at least one dataset entry or benchmark exits (`benchmark.py:246-251`).

**guard.py:** One row per paper PID; no page split. Missing paper in baseline is hard-fail (`guard.py:221`), but **new** papers pass as `STATUS_NEW` (`guard.py:165-169`).

**Adopt?** **Yes [ACTIONABLE-NOW].** Add `--strict-corpus` to fail on any `STATUS_NEW` until baseline refresh, mirroring olmOCR's closed page-level corpus.

**Severity:** [HIGH] [ACTIONABLE-NOW]

---

### 1.6 Known-bad / expectedFailure / monotonic baselines

**olmOCR:** No metric baseline or `expectedFailure` bit. Tests are immutable facts; a failing fact stays failing until the test definition or output improves. `checked: "verified"` marks human-reviewed facts in JSONL (`dataset.jsonl:15-17`, `tests.py:36-38`).

**guard.py:** Monotonic known-bad for metrics: papers below floor in baseline are not re-flagged unless they worsen (`guard.py:160-198`, `test_guard.py:84-99`). No equivalent for **verdict** degradation or per-axis skip masks.

**Adopt?** **Partially.** Metric monotonic model is sound; add baseline `"skip_axes"` and `"expected_failure"` bits for permanently weak papers, analogous to olmOCR's verified-but-flaky facts workflow.

**Severity:** [MEDIUM]

---

### 1.7 Refresh ritual and governance

**olmOCR:** Facts live in committed JSONL; refresh is human review via `review_app.py` / `checked: verified`, not an automated `--update` of scores. Benchmark requires clean git tree before remote runs (`run_benchmark.sh:90-101`).

**guard.py / `__main__.py`:** `--update` rewrites baseline with no CI guard (`__main__.py:361-367`). No `kind`/`schema_version` validation on read.

**Adopt?** **Yes [ACTIONABLE-NOW].** Refuse `--update` when `CI=true` unless `WHISKER_GUARD_UPDATE=1`; validate `kind == whisker-guard-baseline` on load.

**Severity:** [HIGH] [ACTIONABLE-NOW]

---

### 1.8 Missing-item vs added-item detection

**olmOCR:** Closed set: auto-injects `BaselineTest` per PDF (`benchmark.py:241-244`); exits if any `(pdf, page)` lacks tests (`benchmark.py:246-251`). Duplicate test IDs rejected at load (`tests.py:860-865`).

**guard.py:** Missing baseline PIDs hard-fail (`guard.py:221`). New PIDs pass (`STATUS_NEW`). Duplicate PIDs in `rows` produce duplicate findings with no dedup.

**Adopt?** **Yes [ACTIONABLE-NOW].** Dedupe by PID (fail on duplicate). Optional strict mode for new PIDs.

**Severity:** [MEDIUM] [ACTIONABLE-NOW]

---

### 1.9 Multi-run repeat stability

**olmOCR:** Supports multiple `_pg{N}_repeat{R}.md` outputs; test passes if **majority of repeats** pass (`test_avg > 0.5`, `benchmark.py:103-126`). Benchmark script accepts `--repeats` (`run_benchmark.sh:12-13,254-262`).

**guard.py:** Single deterministic scoring pass per paper (`bench.py:149-166`). No repeat variance absorption.

**Adopt?** **No for whisker today** (tomd is deterministic per CLAUDE.md). Document that guard assumes deterministic rescoring; if stochastic backends appear later, adopt majority voting.

**Severity:** [LOW]

---

### 1.10 Statistical vs exact gating

**olmOCR:** Bootstrap CI and permutation utilities exist for **reporting** (`utils.py:6-194`, `benchmark.py:328-330`); gate is exact binary per test. Permutation test is documented in module header but not invoked in `benchmark.py` (stale docstring `benchmark.py:12-13`).

**guard.py:** Exact absolute drop `> slack` (`guard.py:180-184`). No CI on whether a regression is statistically meaningful.

**Adopt?** **No for guard gate** (deterministic scorer). Optionally emit bootstrap CI on corpus means in bench report, matching olmOCR leaderboard format (`README.md:49`).

**Severity:** [LOW]

---

### 1.11 Meta-tests on gate logic

**olmOCR:** 148 tests in `test_tests.py` exercise `normalize_text`, fuzzy boundaries, table adjacency, math render, footnote markers, duplicate ID rejection (`tests.py:860-865`), unicode NFC (`test_tests.py:233-240`).

**guard.py:** `test_guard.py` covers slack, floor-cross, missing, monotonic weak paper (~12 cases). No NaN, duplicate PID, vacuous empty corpus, schema mismatch, or baseline `axis_slack` round-trip.

**Adopt?** **Yes.** Target olmOCR's engine-test depth for `_evaluate_paper` and `diff_rows`.

**Severity:** [MEDIUM]

---

## 2. CALIBRATION GAPS

### 2.1 olmOCR does not ROC-calibrate; it uses hand-set per-test tolerance

**olmOCR:** Threshold is `1.0 - max_diffs/len(text)` per assertion, manually chosen per fact during dataset curation (`tests.py:168-169`, `README.md:253-270`). Table fuzzy floor hard-coded at `0.5` (`tests.py:396`). No corpus-level FPR/TPR sweep.

**calibrate.py:** Sweeps ROC on `unigram_coverage` with `target_fpr` ceiling (`calibrate.py:149-185`). Strictly more principled for coverage edges.

**Adopt?** **Keep whisker ROC** for coverage; optionally expose olmOCR-style **per-assertion** `max_diffs` when fact files land.

**Severity:** [LOW]

---

### 2.2 Macro-average operating point (category-equal weight)

**olmOCR:** Training reward and leaderboard overall use macro-average across test categories so Tables and Multi-column contribute equally (`grpo_train.py:1153-1161`, `benchmark.py:387-388`).

**calibrate.py:** Pools all labeled papers into one ROC regardless of stratum (HTML vs PDF, table-heavy vs prose).

**Adopt?** **Yes.** When labels carry a `stratum` field, fit edges per stratum and take the **worst** stratum FPR (conservative) or macro-average TPR at fixed FPR.

**Severity:** [MEDIUM]

---

### 2.3 Multi-threshold / per-axis calibration

**olmOCR:** Eight assertion classes with independent pass rates reported (`benchmark.py:404-407`). No single scalar threshold.

**calibrate.py:** Only `unigram_coverage` fail/review edges (`__main__.py:488-499`). No `nid/teds/mhs` floor fitting.

**Adopt?** **Yes.** Extend calibrate to accept labeled bench rows and fit per-axis floors with the same ROC machinery.

**Severity:** [HIGH]

---

### 2.4 Fail/review edge ordering not enforced

**olmOCR:** N/A (binary pass/fail per test).

**calibrate.py:** `fail_fit` and `review_fit` are independent (`__main__.py:494-499`). Nothing requires `fail_edge <= review_edge`.

**Adopt?** **Yes [ACTIONABLE-NOW].** After both fits, assert ordering or constrain review sweep to thresholds `>= fail_edge`.

**Severity:** [HIGH] [ACTIONABLE-NOW]

---

### 2.5 Cross-validation / class imbalance / minimum sample size

**olmOCR:** Class balance is implicit in fact design (each test is its own label). No held-out calibration split.

**calibrate.py:** Single-sample ROC; requires both classes but no minimum count beyond `n_pos/n_neg > 0` (`calibrate.py:164-169`). No bootstrap CI on chosen operating point.

**Adopt?** **Yes.** Warn when `n_pos < 10` or `n_neg < 10`; emit bootstrap CI on TPR/FPR using olmOCR's `calculate_bootstrap_ci` pattern (`utils.py:6-67`).

**Severity:** [MEDIUM]

---

### 2.6 Per-axis / per-stratum calibration

**olmOCR:** Results table reports pass rate per document stratum (ArXiv, Tables, Headers & footers, …) (`README.md:23-36`). Thresholds are per-test, not per-stratum, but reporting is stratified.

**calibrate.py / guard:** Single global threshold set; no `--reference` engine or HTML/PDF stratification.

**Adopt?** **Partially.** Record stratum in calibration output; guard floors may need separate PDF vs HTML corpora.

**Severity:** [MEDIUM]

---

## 3. CONCRETE BUGS / EDGE-CASES IN OUR CODE

| Function | Scenario | Expected olmOCR behavior | whisker behavior | Severity |
|----------|----------|--------------------------|------------------|----------|
| `diff_rows` | `rows=[]`, baseline with N papers | Exit: no tests (`benchmark.py:232-234`) | `findings=[]`, `missing` populated, **`failed=True`** via missing — OK. But `rows=[]`, **`baseline=None`**: `failed=False` vacuous pass | [CRITICAL] [ACTIONABLE-NOW] |
| `diff_rows` | Duplicate PIDs in `rows` | `load_tests` raises `ValidationError` on duplicate id (`tests.py:863-864`) | Duplicate `GuardFinding` entries, last writer wins in dict export | [HIGH] [ACTIONABLE-NOW] |
| `_evaluate_paper` | `cur` or `prior` is `NaN`/`Inf` | Test `run` raises or returns fail with explanation | `drop = round(prior-cur, 4)` → NaN; `NaN > slack` is False → **silent pass** | [HIGH] [ACTIONABLE-NOW] |
| `diff_rows` | Baseline stores `axis_slack: 0.05`, CLI uses default 0.02 | N/A | Committed slack ignored; baseline field is decorative (`guard.py:141` vs `201-206`) | [HIGH] [ACTIONABLE-NOW] |
| `_evaluate_paper` | Paper improves from below-floor to above-floor without `--update` | Fact pass flips; score reflects immediately | `status=ok`; stale baseline still shows old weak values on next `--update` diff only | [LOW] |
| `calibrate_threshold` | All bad papers have **higher** coverage than good (mislabeled corpus) | N/A | ROC picks wrong edge with high confidence; no sanity check | [MEDIUM] |
| `calibrate_threshold` | `fail` and `review` fits on same samples | N/A | Can emit **`review_edge < fail_edge`**, inverting the band (`__main__.py:494-499`) | [HIGH] [ACTIONABLE-NOW] |
| `calibrate_threshold` | Single sample per class (n=1) | N/A | Valid (`n_pos=1`); TPR/FPR only 0 or 1, no warning | [MEDIUM] |
| `_confusion` | Identical values in both classes at same threshold | N/A | Handled; may fall back to Youden (`calibrate.py:174-180`, `test_calibrate.py:36-49`) | [LOW] |
| `run_bench` + guard | Corpus paper skipped (`MissingPaperMdError`) | Missing MD → candidate error, score 0 (`benchmark.py:69-77`) | `_load_corpus_pairs` **silently skips** (`__main__.py:256-258`); guard never sees missing paper unless it was in baseline | [MEDIUM] |
| `_evaluate_paper` | Uniform axis erosion: each axis −0.015 (< slack 0.02) | Each fact checked independently | Passes (`test_guard.py:109-114`); olmOCR would catch any single failed fact | [MEDIUM] |
| `baseline_from_rows` | Unicode PID keys | Test ids are ASCII | PID uppercased in loader (`__main__.py:253`); baseline keys must match | [LOW] |

---

## 4. MISSING AXIS / CHECK

olmOCR assertion classes with **no whisker guard equivalent**:

| olmOCR check | Evidence | whisker gap |
|--------------|----------|-------------|
| **Text presence** (required substrings) | `TextPresenceTest` (`tests.py:128-182`) | No per-paper anchor facts |
| **Text absence** (headers/footers must not appear) | `TextPresenceTest` ABSENT (`tests.py:177-182`); HF stratum (`README.md:230`) | `gates.py` furniture strip is structural, not regression-gated |
| **Reading order** (before/after pairs) | `TextOrderTest` (`tests.py:186-226`) | `reading_order` metric is advisory only (`bench.py:18-20`, `constants.py:97-98`) |
| **Table cell adjacency** | `TableTest` with up/down/left/right/heading relations (`tests.py:342-480`) | TEDS is holistic; no cell-neighbor facts |
| **Math formula** (KaTeX render compare) | `MathTest` (`tests.py:548-613`) | No math axis |
| **Format** (heading/bold/italic) | `FormatTest` (`tests.py:230-338`) | No format axis |
| **Footnote marker placement** | `FootnoteTest` (`tests.py:616-763`) | No footnote axis |
| **Baseline quality** (blank page, repeat ngrams, disallowed scripts) | `BaselineTest` (`tests.py:484-545`) | Partial overlap with `gates.py` on live score, **not** in guard baseline |
| **Zone-scoped presence** (`first_n`/`last_n`) | `TextPresenceTest` (`tests.py:160-165`, `test_tests.py:200-231`) | No header/footer zone assertions |
| **Verdict transition** (pass→review→fail) | Implicit: any fact flip | Guard diffs metrics only, not `WhiskerResult.verdict` |

**Severity:** [CRITICAL] for presence/absence/order/table facts (localized regressions invisible to scalar guard); [HIGH] for baseline-quality and math; [MEDIUM] for format/footnote.

---

## 5. TOP PORTABLE DETAIL

**Adopt olmOCR's length-relative fuzzy threshold formula as guard slack semantics for text-derived axes:**

```python
threshold = 1.0 - (max_diffs / (len(reference_query) if len(reference_query) > 0 else 1))
```

(`tests.py:168-169`)

For whisker's bounded [0,1] bench metrics, the portable mapping is:

```python
effective_slack = max(GUARD_AXIS_SLACK, max_diffs / max(len_context, 1))
# Equivalently: flag when (prior - cur) > max(absolute_slack, relative_slack * span)
```

where `len_context` could be token count or a baseline axis value span. Pair with olmOCR's **macro-average overall**:

```python
new_overall_score = sum(jsonl_pass_rates) / len(jsonl_pass_rates)
```

(`benchmark.py:387-388`)

Use macro-average of **per-axis pass bits** (did each axis stay above floor and not regress?) as the corpus rollup in guard reports, so a table stratum collapse cannot hide inside a healthy NID mean — the exact anti-collapse invariant olmOCR encodes in its leaderboard columns (`README.md:23-36`).

**Severity if not adopted:** [HIGH]
