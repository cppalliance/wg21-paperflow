# Red-team: whisker guard/calibrate vs Surya QA

**Source repo:** `packages/whisker/research/repos/surya/` (datalab-to/surya v0.20.0)  
**Target code:** `packages/whisker/src/whisker/guard.py`, `calibrate.py`, supporting `bench.py`, `constants.py`, `__main__.py`

## Summary

- Surya has **no committed per-item regression baseline, no golden diff, and no in-repo metric calibration**; CI is smoke-only (`tests/*.py`, `.github/workflows/scripts.yml`). whisker guard is already ahead on snapshot regression, but Surya's **tiered CI matrix** and **stage-local smoke jobs** expose guard as a single monolithic gate with no fast path.
- Surya gates quality through **environment-aware skips, block-level error/confidence flags, blank-region filters, and repeat-loop degeneracy detection** (`conftest.py`, `recognition/__init__.py`, `common/blank.py`); guard diffs four paper-level floats and never sees conversion failure markers or hallucination filters.
- Surya's **image-adaptive detection thresholds** (`detection/heatmap.py:13-23`) and **hand-set named constants** (`settings.py:112-113`, `common/blank.py:22-27`) are never ROC-fitted; whisker `calibrate` is ahead on labeled ROC but **fits only `unigram_coverage`**, not bench axes or Surya-style adaptive slack.
- External benchmarks stratify by **document source/modality** (olmOCR ArXiv/Tables/MultCol columns, `README.md:404-408`); guard has flat per-pid axes with no stratum tag, so one modality can regress while corpus axes hold.
- **Top portable detail:** `get_dynamic_thresholds` scales fixed detection thresholds by document signal strength (`detection/heatmap.py:17-21`) — adopt as per-paper slack scaling instead of a global `GUARD_AXIS_SLACK`.

---

## 1. REGRESSION-GATE GAPS

### 1.1 No committed snapshot diff (Surya anti-pattern; guard must not regress)

**Surya:** Unit tests assert structural invariants only (`test_detection.py:4-8` bbox count; `test_ocr_errors.py:6-15` label strings). GPU smoke in `scripts.yml:25-40` runs CLI on a **runtime-downloaded** PDF (`switch_trans.pdf`, page 0) with **no output comparison**. README benchmarks (`README.md:378-408`) are external (olmOCR-bench), not CI gates.

**guard.py:** Per-paper baseline JSON, missing-pid hard fail (`guard.py:113-115`, `221`), `--update` refresh (`__main__.py:329-331`).

**Adopt?** **Do not copy Surya's smoke-only CI.** Guard already implements the regression contract Surya lacks. Keep guard; optionally add a lightweight smoke tier *alongside* guard, not instead of it.

**Severity:** [CRITICAL] (negative control)

---

### 1.2 Tiered CI: fast matrix vs heavy GPU smoke

**Surya:** `ci.yml:6-11` runs `pytest` on a **3-runner matrix** (`t4_gpu`, `ubuntu-latest`, `windows-latest`) with `fail-fast: false`. CPU/Windows runners **skip** all VLM tests via session-scoped `pytest.skip` when the backend is unavailable (`conftest.py:16-25`). Heavy integration is isolated in **`scripts.yml`** (GPU-only, downloads benchmark zip, runs detect/OCR/layout/table sequentially with `--keep_server` reuse, `scripts.yml:25-40`).

**guard.py / `__main__.py`:** Single `whisker guard` command scores the full corpus every time; no fast subset, no stage split, no runner-tier contract.

**Adopt?** **Yes [ACTIONABLE-NOW].** Add a `--smoke` / `--max-papers N` / tagged corpus tier so PR CI runs guard on 2–3 papers while nightly runs the full baseline. Mirror Surya's separation: cheap gate vs expensive gate, same tool.

**Severity:** [HIGH] [ACTIONABLE-NOW]

---

### 1.3 Modality- / source-stratified regression

**Surya:** olmOCR-bench results are reported **per source stratum** (ArXiv, Tables, MultCol, OldScan, etc., `README.md:404-408`), never collapsed into one headline pass rate. Multilingual eval is similarly per-language (`README.md:411-437`).

**guard.py:** Flat `pid → {nid,teds,mhs,overall}` (`guard.py:143-146`); no `classification`, language, or modality tag in baseline schema. A tables-heavy paper can crater on `teds` while `overall` stays within slack via `nid`/`mhs` compensation (`test_guard.py:109-114`).

**Adopt?** **Yes [ACTIONABLE-NOW].** Extend baseline rows with optional stratum metadata; fail on **any axis regression within a stratum** and report stratum rollups. Do not let cross-stratum averaging hide collateral damage.

**Severity:** [HIGH] [ACTIONABLE-NOW]

---

### 1.4 Block-level error / confidence / skipped flags

**Surya:** Output schema carries per-block `error`, `skipped`, `confidence` (0–1), and `html` emptiness (`README.md:156-167`). Block-mode OCR marks failed blocks explicitly (`recognition/__init__.py:226-238` sets `error=True`, `confidence=0.0`). Layout drops hallucinated text over blank regions (`layout/__init__.py:107-115`, `common/blank.py:40-64`).

**guard.py:** Four paper-level floats (`guard.py:65-71`); no block count, error rate, or confidence roll-up in baseline or diff.

**Adopt?** **Yes.** Persist `block_error_count`, `blocks_skipped`, mean/min confidence in baseline; guard fails when error count rises or confidence drops beyond slack even if aggregate `nid` is flat. Surya treats block failures as first-class signals, not noise around a mean.

**Severity:** [HIGH]

---

### 1.5 Degeneracy detection (repeat-loop / blank-page semantics)

**Surya:** Full-page OCR detects decoder repetition loops and falls back to block mode (`recognition/__init__.py:309-315`, `_detect_repeat_loop:81-108`). Empty output on a **non-blank** page triggers fallback (`recognition/__init__.py:296-307`); blank pages accept empty output via `is_blank_region` (`common/blank.py:40-64`). Repeat detection also exists in `inference/util.py:61-91`.

**guard.py:** `run_bench` always returns finite metric floats; no check for repetitive markdown, empty conversion on non-trivial source, or `[MISSING_*]`-style failure markers.

**Adopt?** **Yes [ACTIONABLE-NOW].** Add a reference-free degeneracy gate (repeat-line detector + minimum block/token count) that guard treats like a hard axis regression. A looping or empty conversion can score misleadingly high on empty-table `teds=1.0` (`bench.py:128-129`).

**Severity:** [HIGH] [ACTIONABLE-NOW]

---

### 1.6 Image-adaptive tolerance (dynamic thresholds vs fixed slack)

**Surya:** Detection thresholds are **not fixed globally**: `get_dynamic_thresholds` scales `DETECTOR_TEXT_THRESHOLD` / `DETECTOR_BLANK_THRESHOLD` per image from top-10% heatmap intensity (`detection/heatmap.py:13-23`, base constants `settings.py:112-113`).

**guard.py:** Single global `GUARD_AXIS_SLACK = 0.02` (`constants.py:94`) and fixed floors (`constants.py:56-58`); short/noisy papers and long stable papers share the same drop budget.

**Adopt?** **Yes [ACTIONABLE-NOW].** Scale per-paper slack by a document complexity proxy (GT token count, block count, or baseline metric magnitude) using Surya's clamped scaling pattern. Fixed slack is wrong for heterogeneous WG21 corpora.

**Severity:** [MEDIUM] [ACTIONABLE-NOW]

---

### 1.7 Pre-score normalization / hallucination filter before diff

**Surya:** Layout and OCR **drop** text blocks over blank/uniform regions before downstream use (`layout/__init__.py:107-115`, `recognition/__init__.py:52-78`). Parsers strip fences and coerce malformed JSON (`inference/parsers.py:29-76`). Metrics are computed on filtered structure, not raw model spew.

**guard.py:** Diffs metric outputs from `run_bench` (`bench.py:157-160`) with no guard-time normalization pass. Baseline stores `round(v, 4)` (`guard.py:144`) but live axes in `_evaluate_paper` use unrounded `BenchRow` floats (`guard.py:172-173`).

**Adopt?** **Yes [ACTIONABLE-NOW].** Round live axes to baseline granularity before diff; optionally strip known furniture/hallucination patterns before scoring (whisker already has `normalized_text` on the score path — extend to bench/guard).

**Severity:** [MEDIUM] [ACTIONABLE-NOW]

---

### 1.8 Silent pass on backend / inference failure (anti-pattern)

**Surya:** `test_recognition.py:3-5` and `test_layout.py:6-8` **return without asserting** when `error` is set; `test_table_rec.py:16-17` same. Session fixture skips all VLM tests if spawn fails (`conftest.py:24-25`). CI can go green with **zero meaningful OCR assertions** on ubuntu/windows.

**guard.py:** Missing corpus pairs error out (`__main__.py:354-356`); missing baseline pid hard-fails (`guard.py:221`). Does not silently pass on partial scoring failure.

**Adopt?** **Do not adopt silent pass.** Guard should **fail loud** if any corpus paper cannot be scored (contrast Surya). Optionally adopt Surya's **explicit `error` flag in baseline** so a paper that previously scored and now errors is a regression.

**Severity:** [CRITICAL] (Surya exposes the failure mode; guard should explicitly reject it)

---

### 1.9 Stage-local smoke (localize which pipeline leg broke)

**Surya:** `scripts.yml:29-40` runs **detect, OCR, layout, table** as separate CI steps on the same PDF, reusing `--keep_server`. A layout regression does not require re-running detection.

**guard.py:** Single `run_bench` produces one metric bundle per paper; no per-stage intermediate baseline.

**Adopt?** **Partially (tomd-side).** Out of scope for guard today, but guard report should name **which axis** regressed (already does) and optionally tag **which bench sub-score** (table extract vs block match) when bench is split. Document as follow-on for tomd stage goldens.

**Severity:** [LOW]

---

### 1.10 known-bad / expectedFailure / refresh ritual

**Surya:** No monotonic weak baseline; no refresh ritual; thresholds are code constants (`settings.py:112-113`).

**guard.py:** Monotonic weak baseline (`guard.py:171-197`, `test_guard.py:84-98`); `--update` refresh (`__main__.py:329-331`).

**Adopt?** **Guard is ahead.** No change.

**Severity:** [LOW]

---

### 1.11 Missing / added-item detection

**Surya:** No corpus membership contract; benchmark data downloaded at CI time (`scripts.yml:25-28`), not committed.

**guard.py:** Missing baseline pid → hard fail (`guard.py:221`). New pid → `STATUS_NEW` passes (`guard.py:165-169`).

**Adopt?** **Partially [ACTIONABLE-NOW].** Keep missing detection. Flag `STATUS_NEW` when a baseline exists (require `--update` to bless additions), matching explicit corpus contracts Surya never enforced.

**Severity:** [MEDIUM] [ACTIONABLE-NOW]

---

### 1.12 Statistical vs exact tolerance

**Surya:** Detection uses **continuous heatmap thresholds** with dynamic scaling (`detection/heatmap.py:13-23`); OCR error is **argmax binary** (`ocr_error/__init__.py:47`), not a swept ROC. External benchmarks report **pass rates**, not per-doc diffs.

**guard.py:** **Exact deterministic** float diff with fixed slack and 4-decimal drop rounding (`guard.py:177-181`).

**Adopt?** **Keep exact diff for deterministic whisker metrics.** Optionally layer Surya-style **adaptive slack** (§1.6) without introducing statistical noise. Do not adopt argmax-without-calibration for gate edges.

**Severity:** [LOW]

---

## 2. CALIBRATION GAPS

### 2.1 No in-repo ROC / operating-point fit

**Surya:** All production thresholds are **hand-set constants**: `DETECTOR_TEXT_THRESHOLD=0.6`, `DETECTOR_BLANK_THRESHOLD=0.35` (`settings.py:112-113`); blank heuristics `BLANK_WHITE_THRESHOLD=245`, `BLANK_PIXEL_FRACTION=0.99`, `UNIFORM_COLOR_STD=8.0` (`common/blank.py:22-27`); OCR error uses **hard argmax** on logits (`ocr_error/__init__.py:47`) with no recorded TPR/FPR. README cites external benchmark scores only (`README.md:387-408`).

**calibrate.py:** Sweeps ROC, picks max TPR at FPR ceiling, records TPR/FPR/precision (`calibrate.py:149-185`).

**Adopt?** **Calibrate is ahead.** Promote Surya's constants as **candidates** for future calibrate targets (blank fraction, detector thresholds on a labeled WG21 subset), not as replacements for ROC fit.

**Severity:** [LOW] (whisker ahead)

---

### 2.2 Image-adaptive thresholds without labeled calibration

**Surya:** `get_dynamic_thresholds` adapts thresholds per input from heatmap statistics (`detection/heatmap.py:17-21`) — **unsupervised** adaptation, not class-labeled ROC.

**calibrate.py:** Supervised fit from `(value, is_bad)` only; no per-document covariate (length, DPI, language).

**Adopt?** **Yes.** Combine supervised ROC for fail/review edges with Surya-style **covariate-adjusted** thresholds (e.g., scale unigram edge by source page count or GT length). Single global edge misfits short memos vs 40-page papers.

**Severity:** [MEDIUM] [ACTIONABLE-NOW]

---

### 2.3 Multi-threshold / per-axis calibration

**Surya:** Separate threshold families per subsystem (detection, blank, OCR error, VLM token budgets `inference/util.py:94-96`, GPU batch scaling `inference/backends/vllm.py:28-60`).

**calibrate.py:** CLI fits only `unigram_coverage_fail_edge` and `unigram_coverage_review_edge` (`__main__.py:490-498`); **no** `nid`/`teds`/`mhs`/`REF_NID_ADVISORY_EDGE` fits despite bench floors in `constants.py:56-58`.

**Adopt?** **Yes [ACTIONABLE-NOW].** Extend calibrate to bench axes and advisory oracle edge; Surya's multi-constant `settings.py` shows every gate needs its own operating point documentation.

**Severity:** [HIGH] [ACTIONABLE-NOW]

---

### 2.4 Fail/review edge ordering not constrained

**Surya:** N/A (no dual-edge band).

**calibrate.py:** `fail_fit` and `review_fit` are **independent** ROC runs (`__main__.py:494-498`); nothing enforces `fail_edge <= review_edge`.

**Adopt?** **Yes [ACTIONABLE-NOW].** After independent fits, clamp or re-select so the fail band is nested inside review (fail threshold ≤ review threshold for a lower-is-worse gate).

**Severity:** [MEDIUM] [ACTIONABLE-NOW]

---

### 2.5 Class imbalance and stratified calibration

**Surya:** Multilingual benchmark spans 91 languages with scores from 72.7% to 93.0% (`README.md:421-437`); no per-language threshold table in-repo.

**calibrate.py:** Pooled ROC over all labels; no stratification, no per-stratum FPR budget, no cross-validation.

**Adopt?** **Yes.** When labels span imbalanced strata (few `fail`, many `pass`), report per-stratum TPR/FPR or require minimum per-class counts before promoting an edge. Surya's stratified **reporting** (`README.md:404-408`) without stratified **gates** is half a lesson — whisker should do both.

**Severity:** [MEDIUM]

---

### 2.6 Cross-validation / holdout

**Surya:** None in-repo.

**calibrate.py:** Fits on all provided samples; no holdout split.

**Adopt?** **Optional [MEDIUM].** Not Surya-specific, but labeled corpus growth will overfit a single sweep without k-fold or holdout reporting alongside `chosen`.

**Severity:** [MEDIUM]

---

### 2.7 Binary classifier without score calibration

**Surya:** OCR error model outputs `good`/`bad` via argmax (`ocr_error/__init__.py:47`); tests only check label strings (`test_ocr_errors.py:6-15`), not confidence or threshold sweep.

**calibrate.py:** Could calibrate a future OCR-quality axis but does not today.

**Adopt?** **Later.** If whisker adds a garbled-text detector (Surya analogue), run it through `calibrate_threshold` on softmax scores, not argmax.

**Severity:** [LOW]

---

## 3. CONCRETE BUGS / EDGE-CASES IN OUR CODE

| Function | Scenario | Expected failure mode | Actual behavior | Severity |
|----------|----------|----------------------|-----------------|----------|
| `baseline_from_rows` | Duplicate `pid` in `rows` | Error or merge policy | Dict comprehension **last row wins silently** (`guard.py:143-146`); `diff_rows` emits **duplicate findings** for same pid (`guard.py:216-218`) | [HIGH] [ACTIONABLE-NOW] |
| `_evaluate_paper` | `axes[axis]` is `NaN` or `inf` | Hard fail / invalid metric | Comparisons silently false; paper may **pass as `ok`** despite corrupt score | [CRITICAL] [ACTIONABLE-NOW] |
| `_evaluate_paper` | Baseline has rounded 4dp, live value unrounded | Symmetric boundary | `drop = round(prior - cur, 4)` uses mixed precision (`guard.py:177-180`); boundary cases differ from fully rounded pipeline | [MEDIUM] [ACTIONABLE-NOW] |
| `diff_rows` | `baseline["rows"]` contains unknown axis keys | Ignore or validate | `.get(axis)` skips missing axis (`guard.py:174-176`); **silent skip** of regression on new axes added to bench | [MEDIUM] |
| `diff_rows` | `baseline` wrong `kind` / missing `rows` | Reject | Accepts any dict; empty `rows` → every paper looks **new** (`guard.py:213-214`) | [MEDIUM] [ACTIONABLE-NOW] |
| `diff_rows` | `slack=0` or negative | Reject | No validation; **zero slack** flags any strict drop; negative slack inverts semantics | [MEDIUM] [ACTIONABLE-NOW] |
| `run_bench` + guard | Empty candidate and reference (no tables) | Fail or `insufficient` | `teds=1.0` (`bench.py:128-129`); guard sees perfect table score on empty content | [HIGH] [ACTIONABLE-NOW] |
| `_load_corpus_pairs` + guard | Some pids missing candidate md | Fail closed on partial corpus | Skipped with warning (`__main__.py:256-258`); vanished pid triggers **missing** hard fail — correct but **surprising** if skip was unintentional | [MEDIUM] |
| `calibrate_threshold` | `samples=[]` | `ValueError` | Raises at class check (`calibrate.py:166-169`) — OK | [LOW] |
| `calibrate_threshold` | All identical values, both classes | Undefined / tie policy | Tie-break `(tpr, precision, threshold)` (`calibrate.py:177`); test covers 0.50/0.50 (`test_calibrate.py:36-49`) — OK but **precision arbitrary** | [LOW] |
| `calibrate_threshold` | Single positive, single negative, overlapping | Youden fallback | Works; **high variance** — Surya would not ship on n=2 | [MEDIUM] |
| `_calibrate_main` | All labels `pass` or all `fail` | Clear error | `ValueError` from calibrate — OK | [LOW] |
| `_calibrate_main` | Independent fail/review fits | `fail_edge <= review_edge` | Can emit **inverted band** if fits disagree | [HIGH] [ACTIONABLE-NOW] |
| `guard` CLI | VLM-unavailable analogue: `run_bench` throws on one paper | Abort or mark failed | Uncaught exception → exit 1; unlike Surya skip, but **no partial report** | [LOW] |

**Surya-motivated foolers:** Repeat-loop markdown (§1.5) and blank-page high scores (§1.5) are the highest-risk inputs Surya explicitly guards against but whisker guard does not.

---

## 4. MISSING AXIS / CHECK

| Surya gate or signal | Source | whisker equivalent | Gap |
|---------------------|--------|-------------------|-----|
| Per-block `error` / `skipped` / `confidence` | `README.md:156-167`, `recognition/__init__.py:226-238` | None on bench/guard path | [HIGH] |
| Repeat-loop / degenerate output detection | `recognition/__init__.py:309-315`, `util.py:61-91` | None | [HIGH] |
| Blank-region / hallucination filter | `common/blank.py:40-64`, `layout/__init__.py:107-115` | Reference-free gates partial; **not in guard/bench** | [MEDIUM] |
| OCR garbled-text binary (`good`/`bad`) | `ocr_error/__init__.py:47`, `test_ocr_errors.py:6-15` | No garbled-text axis | [MEDIUM] |
| Layout reading order / `position` | `README.md:252-258`, `test_recognition.py:15` | `reading_order` advisory only (`constants.py:99`) | [MEDIUM] |
| Modality-stratified pass rates | `README.md:404-408` | Flat corpus axes | [HIGH] |
| Detection dynamic thresholds | `detection/heatmap.py:13-23` | Fixed slack/floors | [MEDIUM] |
| Inference `error` flag on page | `README.md:262`, `layout/__init__.py:79-84` | No conversion-status field in `BenchRow` | [HIGH] |
| Tiered CI smoke vs full eval | `ci.yml:6-11`, `scripts.yml:25-40` | Single guard invocation | [MEDIUM] |
| GPU-scaled resource baselines | `inference/backends/vllm.py:28-60` | N/A (deterministic CPU metrics) | [LOW] |

---

## 5. TOP PORTABLE DETAIL

**Adopt Surya's image-adaptive threshold scaling as per-paper guard slack.**

From `detection/heatmap.py`:

```python
avg_intensity = np.mean(np.partition(flat_map, top_10_count)[top_10_count:])
scaling_factor = np.clip(avg_intensity / typical_top10_avg, 0, 1) ** (1 / 2)
low_text = np.clip(low_text * scaling_factor, 0.1, 0.6)
text_threshold = np.clip(text_threshold * scaling_factor, 0.15, 0.8)
```

(`detection/heatmap.py:15-21`, with `typical_top10_avg=0.7` at line 13)

**Port to whisker:** replace fixed `GUARD_AXIS_SLACK` with `slack(pid) = clip(base_slack * sqrt(baseline_strength(pid) / corpus_median_strength), slack_min, slack_max)` where `baseline_strength` is mean(`nid`,`teds`,`mhs`) or GT token count. Noisy/short papers get tighter slack; stable high-signal papers tolerate the current 0.02. Surya proves **heterogeneous documents cannot share one global tolerance**; whisker guard currently assumes they can (`constants.py:94`).

**Severity:** [HIGH] [ACTIONABLE-NOW]
