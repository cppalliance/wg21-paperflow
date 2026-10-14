# Red-team: whisker guard + calibrate vs ByteDance/Dolphin

**Repo deep-read:** `packages/whisker/research/repos/Dolphin` (master @ `befa5da`, 32 tracked files). Dolphin ships **no** in-repo tests, **no** CI workflow, **no** committed metric snapshots, and **no** threshold calibration. Its QA surface is (a) optional **pre-score markdown normalization** in `utils/markdown_utils.py`, (b) **modality-stratified** parsing/eval philosophy documented against OmniDocBench in `README.md`, and (c) **document-type routing** heuristics in `utils/utils.py` / `demo_page.py`. Evaluation numbers are published externally; regression plumbing is absent. whisker guard/calibrate are ahead on regression gates; Dolphin exposes gaps in normalization pinning, axis stratification, and metric coverage.

## Summary (5 bullets)

- **[HIGH][ACTIONABLE-NOW]** Dolphin gates eval quality on a **pinned `post_process` normalization chain** (LaTeX canon, repeated-token truncation, table-HTML strip) before any score; `guard.py` snapshots raw `run_bench` metrics with **no baseline field** recording normalizer version or whether post-process ran — formatting-only churn can trip false regressions.
- **[HIGH]** OmniDocBench-style eval (Dolphin's published benchmark) uses **six separate axes** (Text Edit↓, Formula CDM↑, Table TEDS↑, Table TEDS-S↑, Read Order Edit↓, Overall↑) with **modality-aware reporting**; `guard.py` diffs four similarity axes plus `overall`, omits formula/CDM/TEDS-S/read-order-edit entirely, and can still let correlated sub-slack drops hide in `overall` when no single axis exceeds slack.
- **[MEDIUM][ACTIONABLE-NOW]** Dolphin routes **photographed/distorted** pages via `check_bbox_overlap(..., iou_threshold=0.1, overlap_box_ratio=0.25)` (`utils/utils.py:489-533`) into a different parse path; whisker guard has **no document-class axis** and no equivalent intrinsic gate — same corpus mix shift can move baselines without a regression flag.
- **[MEDIUM][ACTIONABLE-NOW]** `calibrate.py` fits only `unigram_coverage` ROC edges; Dolphin/OmniDocBench never collapse to one content scalar — **per-axis bench thresholds** (NID/TEDS/MHS floors in `constants.py`) remain hand-set with no labeled fit, ROC, or cross-validation.
- **[CRITICAL][ACTIONABLE-NOW]** Concrete foolers: **duplicate PIDs** in `baseline_from_rows` silently overwrite (`guard.py:143-146`); **NaN/Inf metrics** pass comparisons unchecked (`guard.py:172-184`); **corpus skip** in `_load_corpus_pairs` (`__main__.py:256-258`) can make a baseline paper vanish without an explicit missing-PID if the `.gt.md` file is removed but baseline row remains; **identical-label ties** in `calibrate_threshold` pick max threshold (`calibrate.py:177`) maximizing false flags on the tie bucket.

---

## 1. REGRESSION-GATE GAPS

### 1.1 Pre-score normalization pinned before diff

**Dolphin:** `MarkdownConverter(post_process=True)` applies `truncate_repeated_tail(text, threshold=20, keep=1)` (`markdown_utils.py:320-321`), LaTeX canonicalization (`remove_numeric_quad_ending`, `gathered_to_aligned`, `aligned_to_array`, `replace_repeated_cdots` at `markdown_utils.py:291-296`), and table HTML attribute stripping (`extract_table_from_html` strips `<table>` attrs at `markdown_utils.py:14-16`). CLI exposes this as an explicit ritual: `--post_process` (`demo_page.py:339`, wired through `save_outputs` at `utils/utils.py:243-244`).

**guard.py:** Diffs metrics from `run_bench` with no record of normalizer generation, post-process flag, or metric-code SHA in `baseline_from_rows` (`guard.py:136-147`).

**Adopt?** **Yes [HIGH][ACTIONABLE-NOW].** Pin `normalizer_version` + optional Dolphin-style repeat/LaTeX/table passes in the baseline payload; re-score through the same chain on diff. Without this, guard fires on formatting churn Dolphin explicitly strips before compare.

### 1.2 Per-modality / per-axis stratification (no averaging away)

**Dolphin / OmniDocBench (README):** Reports Text Edit, Formula CDM, Table TEDS, Table TEDS-S, Read Order Edit separately; Overall is derived but each axis is published independently (`README.md:60-73`). Element parsing batches by label (`tab` / `equ` / `code` / text) with distinct prompts (`demo_page.py:268-282`).

**guard.py:** Regresses `nid`, `teds`, `mhs`, `overall` only (`constants.py:99`; `guard.py:172-184`). No formula axis, no TEDS-S, no read-order distance metric. `reading_order` stored in baseline (`guard.py:71`) but **never gated** (`constants.py:98-99`).

**Adopt?** **Partially [HIGH].** Add null-eligibility: skip regression on an axis when both baseline and current lack that modality (Dolphin/OmniDocBench exclude absent strata from means). Add optional read-order regression with inverted semantics (lower-is-better). Formula/CDM is a new axis, not guard.py today.

### 1.3 Modality null eligibility

**Dolphin:** Tables without GT table content are not scored as structural failures at the element level; empty-table path returns stripped HTML only when present (`markdown_utils.py:271-280`).

**whisker bench:** `_table_score` returns `1.0` when neither side has tables (`bench.py:128-129`), so TEDS is **always 1.0** on table-free papers — stable but **non-informative**; guard still diffs TEDS regressions when values move from synthetic 1.0.

**Adopt?** **Yes [MEDIUM][ACTIONABLE-NOW].** Mark axis `eligible: false` in baseline when GT lacks modality; exclude from regression diff (opendataloader pattern cited in whisker notes).

### 1.4 Floors vs baseline slack

**Dolphin:** No committed floors or regression slack in-repo; relies on external benchmark leaderboard numbers (`README.md:58-106`).

**guard.py:** Absolute floors `_FLOORS` (`guard.py:62`, `constants.py:56-58`) plus per-paper slack (`GUARD_AXIS_SLACK=0.02`) and sub-slack floor-crossing (`guard.py:185-190`). **Ahead of Dolphin.**

**Adopt?** **Keep.** Dolphin offers no counter-pattern.

### 1.5 Known-bad / expectedFailure monotonic baselines

**Dolphin:** No equivalent. Demo swallows per-file errors and continues (`demo_page.py:389-391`), which ** hides** regressions rather than monotonic-tracking them.

**guard.py:** Papers below floor in baseline are not re-flagged unless they worsen (`guard.py:171-198`; tested in `test_guard.py:84-99`).

**Adopt?** **Keep.** Dolphin is anti-pattern here.

### 1.6 Refresh ritual

**Dolphin:** `--post_process` toggles normalization (`demo_page.py:339`) but there is **no** committed baseline refresh, no `--update`, no snapshot contract.

**guard.py:** `whisker guard --update` (`__main__.py:329-367`) rewrites baseline; explicit refresh ritual.

**Adopt?** **Keep.** whisker leads.

### 1.7 Missing / added item detection

**Dolphin:** No snapshot diff; multi-page PDF merges pages with separators (`utils/utils.py:131-134`) but no CI check that corpus cardinality is stable.

**guard.py:** `missing` PIDs hard-fail (`guard.py:220-221`, `109-115`). New PIDs get `STATUS_NEW` / `STATUS_NEW_BELOW_FLOOR` (`guard.py:165-169`). **Ahead.**

**Gap:** `_load_corpus_pairs` skips papers missing staged MD with a warning only (`__main__.py:256-258`) — if `.gt.md` is deleted from corpus dir, the paper disappears from the run **without** hitting `missing` (not in `base_rows` keys from current scan). Opposite of baseline-ghost.

**Adopt?** **Yes [MEDIUM][ACTIONABLE-NOW].** Fail if corpus `.gt.md` count drops vs baseline row count, not only if baseline PID absent from current rows.

### 1.8 Normalization-before-diff (metric path)

**Dolphin:** Normalizes **output markdown** before external OmniDocBench scoring.

**whisker:** `block_metrics` uses `normalized_text` (OmniDocBench `clean_string`) (`match.py:240`) but **does not** apply Dolphin's `truncate_repeated_tail`, `aligned_to_array`, or table attr strip. A VLM-style repetition tail can depress NID without semantic loss.

**Adopt?** **Yes [HIGH][ACTIONABLE-NOW].** Port `truncate_repeated_tail` (threshold=20, keep=1) into bench normalization or document why omitted.

### 1.9 Tolerance semantics: statistical vs exact

**Dolphin:** Deterministic decode (`do_sample=False`, `temperature=None` at `demo_page.py:106-108` in layout demo; same pattern in page demo). Eval is deterministic given model weights; no slack concept.

**guard.py:** Fixed absolute slack `0.02` on rounded 4-decimal metrics (`guard.py:177-184`). Deterministic for whisker (no LLM in bench path).

**Adopt?** **Keep slack; add baseline slack mismatch check [LOW][ACTIONABLE-NOW].** `baseline_from_rows` writes `axis_slack` (`guard.py:141`) but `diff_rows` ignores baseline value and uses CLI default (`guard.py:205-206`).

### 1.10 Per-item snapshots

**Dolphin:** Writes per-doc JSON + MD (`utils/utils.py:238-247`) but **never diffs** them in CI.

**guard.py:** Per-paper per-axis snapshot baseline (`guard.py:143-146`).

**Adopt?** **Keep.** Dolphin validates the need; whisker implements it.

### 1.11 Document-type stratification

**Dolphin:** `check_bbox_overlap` → `distorted_page` fallback (`demo_page.py:206-209`, `utils/utils.py:489-533`); separate holistic vs element-wise parse (`README.md:35-36`).

**guard.py:** No document-class field in baseline or report.

**Adopt?** **Yes [MEDIUM].** Record `document_class` per paper; stratify regressions or exclude photographed pages from digital baseline.

---

## 2. CALIBRATION GAPS

### 2.1 Operating-point selection

**Dolphin:** None in-repo. Published OmniDocBench numbers are point estimates, not ROC operating points (`README.md:74-104`).

**calibrate.py:** Max TPR at FPR ≤ target (default 0.05), Youden fallback (`calibrate.py:174-180`).

**Adopt?** **Keep whisker approach.** Dolphin offers nothing to copy; whisker is strictly more principled.

### 2.2 Metric choice

**Dolphin:** Six-axis OmniDocBench suite (text edit, formula CDM, table TEDS/TEDS-S, read order).

**calibrate.py:** Only `unigram_coverage` fail/review edges (`__main__.py:488-499`). Bench floors `NID_FLOOR`/`TEDS_FLOOR`/`MHS_FLOOR` (`constants.py:56-58`) are **not** fittable via `calibrate`.

**Adopt?** **Yes [HIGH].** Extend calibrate to accept per-axis bench labels (good/bad per paper per axis) or derive labels from guard baseline + human adjudication.

### 2.3 Multi-threshold / nested gates

**Dolphin:** Separate handling per element type in converter (`markdown_utils.py:328-345`); no unified threshold file.

**calibrate.py:** Two edges (fail + review) from same ROC machinery (`__main__.py:490-498`).

**Adopt?** **Partially [MEDIUM].** Fail edge should use stricter FPR than review edge; today both use identical `target_fpr` — review band may be too tight or too loose relative to fail.

### 2.4 Cross-validation

**Dolphin:** None.

**calibrate.py:** Single-sample ROC sweep, no holdout/k-fold (`calibrate.py:149-185`).

**Adopt?** **Yes [MEDIUM].** Minimum labeled-N guard (whisker CLAUDE.md says 30-50 papers); report confidence intervals or at least warn when n < 30.

### 2.5 Class imbalance

**Dolphin:** N/A.

**calibrate.py:** FPR ceiling handles good-paper cost; no explicit prevalence weighting or stratified sampling check.

**Adopt?** **Partially [LOW].** Log `n_pos/n_neg` ratio in output (already in `CalibrationResult`); fail calibration when positives < 5.

### 2.6 Per-axis calibration

**Dolphin:** Per-axis reporting only.

**calibrate.py:** Single scalar `unigram_coverage` only.

**Adopt?** **Yes [HIGH][ACTIONABLE-NOW].** Fit NID/TEDS/MHS slack or floors from labeled bench corpus, mirroring opendataloader `thresholds.json` pattern (cited in whisker notes, absent in Dolphin repo).

---

## 3. CONCRETE BUGS / EDGE-CASES IN OUR CODE

| Severity | Function | Scenario | Why it breaks / fools |
|----------|----------|----------|------------------------|
| **[CRITICAL][ACTIONABLE-NOW]** | `baseline_from_rows` (`guard.py:143-146`) | Duplicate `pid` in `rows` | Dict comprehension last-wins silently; baseline loses papers without warning. |
| **[CRITICAL][ACTIONABLE-NOW]** | `_evaluate_paper` (`guard.py:172-184`) | `cur` or `prior` is `NaN`/`Inf` from broken bench | `drop > slack` is False; `crossed_floor` comparisons false; paper passes as `ok`. |
| **[HIGH][ACTIONABLE-NOW]** | `diff_rows` + `_load_corpus_pairs` | `.gt.md` removed from corpus dir but row stays in baseline JSON | Current run never includes PID → not in `missing` if baseline file manually edited; ghost baseline rows untested. |
| **[HIGH][ACTIONABLE-NOW]** | `diff_rows` (`guard.py:213-214`) | `baseline["kind"]` ≠ `whisker-guard-baseline` or schema mismatch | Accepted blindly; diff against wrong artifact shape. |
| **[HIGH]** | `_evaluate_paper` (`guard.py:174-176`) | Baseline row missing an axis key | `continue` skips axis silently; regression on that axis undetected. |
| **[MEDIUM][ACTIONABLE-NOW]** | `diff_rows` (`guard.py:205-206`) | CLI `--slack` ≠ baseline `axis_slack` | Stored slack ignored; CI drift if only baseline updated. |
| **[MEDIUM]** | `run_bench` / guard path | Table-free paper TEDS always 1.0 (`bench.py:128-129`) | Baseline/current both 1.0 masks table-regression signal until first table appears; false `ok` on table introduction failures. |
| **[MEDIUM][ACTIONABLE-NOW]** | `_load_labeled_samples` (`__main__.py:441-452`) | Duplicate `pid` in labels file | Last label wins; calibration class counts wrong. |
| **[MEDIUM][ACTIONABLE-NOW]** | `calibrate_threshold` (`calibrate.py:177-178`) | Many ties at same coverage value | Tie-break prefers **higher** threshold → flags more good papers at identical scores. |
| **[MEDIUM]** | `calibrate_threshold` (`calibrate.py:166-169`) | Single positive or single negative | Raises `ValueError` (good) but CLI exits 1 with no partial result — empty corpus after filtering labels same as hard error. |
| **[LOW]** | `_candidate_thresholds` (`calibrate.py:133`) | All samples identical value | Returns `[v, v+1]` only; ROC degenerate but runs. |
| **[LOW]** | `GuardFinding.to_dict` (`guard.py:98`) | Unicode PID | Preserved in JSON; OK. |
| **[LOW]** | `diff_rows` | Huge corpus (10k papers) | O(n) OK; no batching issue. |
| **[LOW]** | `_evaluate_paper` | Uniform improvement vs baseline | Never auto-promotes baseline (monotonic); Dolphin same — intentional but can leave stale high bars. |

**Dolphin lesson — repetition fooler:** `truncate_repeated_tail(..., threshold=20, keep=1)` (`markdown_utils.py:52-79`) exists because VLMs emit long repeated tails that crush edit metrics. whisker bench has no equivalent → **false regression** on NID when tomd output adds benign repetition, or **false pass** when repetition masks missing content.

**Dolphin lesson — silent skip:** `demo_page.py:389-391` continues on errors. whisker `_load_corpus_pairs` (`__main__.py:256-258`) skips missing MD similarly — guard should treat skip count > 0 as fail when baseline expects those PIDs.

---

## 4. MISSING AXIS / CHECK (Dolphin gates, whisker has no equivalent)

| Dolphin / OmniDocBench axis or check | Evidence | whisker gap |
|--------------------------------------|----------|-------------|
| **Formula CDM** | `README.md:68-69` | No formula metric in bench or guard. |
| **Text Edit (char NED, ↓)** | `README.md:67-68` | whisker `nid` is block-matched similarity (↑); not the same axis. |
| **Table TEDS-S (structure-only)** | `README.md:70-71` | Only full TEDS (`bench.py:124-137`). |
| **Read Order Edit (↓)** | `README.md:72-73` | `reading_order` computed (`bench.py:164`) but excluded from guard (`constants.py:98-99`). |
| **Code-block element** | `markdown_utils.py:338-339`, `demo_page.py:255-257` | No code-preservation metric. |
| **Layout IoU / distorted-page routing** | `utils/utils.py:489-533`, `demo_page.py:206-209` | No intrinsic photographed-doc detection. |
| **LaTeX env canonicalization (`aligned`→`array`, `\quad` strip)** | `markdown_utils.py:23-45,291-296` | Partial overlap via `pylatexenc` in `normalized_text`; missing env transforms. |
| **Repeated-token tail truncation** | `markdown_utils.py:52-79,320-321` | Absent. |
| **Table HTML attribute normalization** | `markdown_utils.py:14-16` | TEDS uses markdown-extracted HTML (`bench.py:72-106`), not Dolphin strip. |
| **Element-level regression** | `demo_element.py` element-type prompts | Guard is per-paper only. |
| **In-repo CI regression gate** | No `.github/workflows`, no tests | whisker has guard; Dolphin does not — listed for completeness. |

---

## 5. TOP PORTABLE DETAIL

**Adopt:** `truncate_repeated_tail(s, threshold=20, keep=1)` from Dolphin **`markdown_utils.py:52-79`**, invoked on every text block before metric scoring (Dolphin wires it at **`markdown_utils.py:320-321`** inside `MarkdownConverter.convert` when `post_process=True`).

**Why this one:** It is the only Dolphin code that directly addresses **metric stability under VLM-style output degeneracy** — the exact class of false regressions a snapshot gate fears. It is deterministic, parameter-free except `(threshold=20, keep=1)`, and absent from whisker's OmniDocBench `clean_string` path. Wire into `run_bench` normalization (or pin as baseline `normalizer_version=2` with repeat truncation) before `guard` diffs.

**Exact formula (port verbatim):**

```python
# markdown_utils.py:52-79 — scan tail for pattern repeated > threshold times; keep one copy
def truncate_repeated_tail(s, threshold=20, keep=1):
    ...
    if count > threshold:
        return s[:pos] + pattern * keep
    return s
```

**Secondary (if one formula only):** OmniDocBench axis split from Dolphin **`README.md:67-73`** — never regress on a single `overall` composite; gate Text / Formula / Table / Read-order independently with null eligibility. whisker guard already diffs axes separately but omits three of five Dolphin-published axes.
