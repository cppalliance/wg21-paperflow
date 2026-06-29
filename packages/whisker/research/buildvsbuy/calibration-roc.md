VERDICT: KEEP-AS-IS - stdlib ROC already fits whisker's inverted gate rule

# BUILD-vs-BUY: Threshold Calibration / ROC / Operating-Point Selection

Research for `whisker` Phase 4b (`calibrate.py`). Question: replace the hand-rolled ROC sweep with `scikit-learn` (`roc_curve`, `precision_recall_curve`), or refactor with numpy-only vectorization?

Constraints: deterministic, no LLM in scoring, minimalism ladder (stdlib first; new heavy dep must clearly beat ~80 lines), permissive license only, Python >=3.12, lib funcs return data.

Prior art: `notes/cross-repo-qa-research.md`, `notes/redteam-synthesis.md`, `research/redteam/*.md`. Cloned repos under `research/repos/` were grepped for `calibrat|roc_curve|precision_recall|Youden|operating` — **zero hits** in repo source trees (calibration evidence lives in redteam markdown reports and upstream docs, not in cloned code).

---

## 1. Current state (`packages/whisker/src/whisker/calibrate.py`)

| Symbol | Role |
|--------|------|
| `_confusion(samples, threshold)` | Count `(tp, fp, tn, fn)` for rule **flag iff `value < threshold`** (positive = bad conversion) |
| `_candidate_thresholds(values)` | Every distinct downward partition: sorted unique values plus `max+1` sentinel |
| `_point(samples, threshold)` | Build `OperatingPoint` with TPR/FPR/precision from `_confusion` |
| `calibrate_threshold(...)` | Sweep all candidates, select **max TPR** among points with `fpr <= target_fpr` (default 0.05), tie-break `(tpr, precision, threshold)` preferring **higher threshold**; Youden-J fallback if infeasible |
| `OperatingPoint` | Frozen dataclass; `youden_j = tpr - fpr`; JSON via `to_dict()` |
| `CalibrationResult` | Chosen point + full curve + class counts + method tag (`max_tpr_at_fpr` / `youden_j`) |

**Size:** ~161 lines total (~120 lines of logic excluding module docstring/copyright). **Dependencies:** stdlib only (`math`, `dataclasses`). **Tests:** `tests/test_calibrate.py` (10 cases: separable recovery, FPR ceiling, Youden fallback, class validation, confusion consistency, monotonic TPR, JSON shape, `target_fpr` bounds, non-finite rejection).

**Whisker-specific semantics baked in (not generic ML):**

- Inverted gate: **lower coverage = worse**, not "higher score = positive."
- Screening bias tie-break: among equal TPR/FPR, pick the **higher** threshold (flag more aggressively within the tie bucket).
- Full confusion counts returned per curve point (sklearn returns rates only).
- Human promotion path: CLI writes `thresholds.json`; values are deliberately promoted into `constants.py`.

---

## 2. Candidate comparison

| Candidate | License | Dep weight | Determinism | Max-TPR @ FPR + Youden | Verdict |
|-----------|---------|------------|-------------|------------------------|---------|
| **Keep stdlib (current)** | BSL-1.0 (whisker) | **0 new** | **Fully deterministic:** sorted unique thresholds, explicit tie-break keys, no BLAS/thread pools | **Out of the box** in `calibrate_threshold` | **Best fit** |
| **numpy-only refactor** | BSD (already dep) | **0 new** (numpy in `pyproject.toml`) | Deterministic if using `np.sort`, stable ordering; avoid multithreaded BLAS surprises on exotic builds | **Still custom:** vectorized curve only; selection logic unchanged | **Marginal; not justified now** |
| **sklearn.metrics** (`roc_curve`, `precision_recall_curve`) | BSD-3-Clause | **Heavy new tree:** `scikit-learn` + `joblib` + `threadpoolctl` (scipy already present) | **Mostly deterministic** on fixed inputs (stable `argsort` in modern sklearn); `drop_intermediate=True` (default) drops collinear ROC points — same `(fpr,tpr)` envelope, fewer threshold rows | **Not out of the box:** returns `(fpr, tpr, thresholds)` or PR analog; **no** FPR-ceiling argmax, **no** Youden fallback, **no** whisker tie-break, **no** full confusion matrix | **Not worth it** |

### 2.1 sklearn details (why BUY loses)

**Semantic inversion.** `sklearn.metrics.roc_curve` assumes **higher `y_score` ⇒ more likely positive** and classifies with **`score >= threshold`**. whisker flags with **`value < threshold`** and lower scores are worse. Adapter required: pass `-value` as `y_score`, flip `pos_label`, then map thresholds back — easy to get wrong and untested against whisker's sentinel `max+1` partition.

**Threshold set mismatch.** whisker sweeps **every** distinct `< t` partition (plus `max+1`). `roc_curve` with default `drop_intermediate=True` omits thresholds that do not change the ROC polyline. Operating-point selection among **feasible FPR points** can differ when tie-break uses **precision** and **higher threshold** among equal TPR/FPR — whisker tests encode those ties; sklearn curve may not enumerate them.

**Selection logic stays ours.** Even with `roc_curve`, whisker still needs ~30–40 lines for: FPR-ceiling filter, `(tpr, precision, threshold)` tie-break, Youden fallback, `OperatingPoint`/`CalibrationResult` shaping, inverted-gate mapping, validation (`target_fpr`, non-finite, single-class). sklearn replaces `_confusion` + `_point` loop, not the product value.

**Install cost vs usage.** Calibration is an **offline admin ritual** on a labeled corpus (tens–low hundreds of papers), not a hot path. Pulling scikit-learn (~15–30 MB installed, joblib/threadpoolctl) for one CLI subcommand fails the minimalism ladder: it does not clearly beat ~120 lines that already pass tests.

**precision_recall_curve** optimizes a different operating point (PR tradeoff). whisker's primary selector is **FPR-ceiling on TPR** (screening gate); PR curve does not replace it.

### 2.2 numpy-only middle ground

Possible vectorization: sort samples once, cumulative sums for TPR/FPR at each distinct threshold (same algorithm as sklearn's `_binary_clf_curve`, ~40 lines).

**Pros:** Reuses existing numpy dep; faster if `n` grows large.

**Cons:**

- Calibration `n` is tiny; stdlib loop is microseconds.
- Adds numpy import to a module that is intentionally stdlib-pure today.
- Saves maybe 20–40 lines while **keeping all selection/validation logic**.
- Fails the "~80 lines saved" bar for taking on even an existing heavy numeric stack in this file.

**Conclusion:** numpy refactor is **BUILD-IMPROVE deferred** — only reconsider if labeled corpus exceeds ~10k samples or calibrate becomes batch-hot.

---

## 3. Per-repo calibration evidence (sparse)

Grep of `research/repos/**` for calibration/ROC symbols: **no matches**. Evidence is from redteam reads and notes:

| Repo / pattern | Calibration? | Evidence |
|----------------|--------------|----------|
| **Field (28 repos)** | **Almost none** | `cross-repo-qa-research.md`: "Almost nobody calibrates thresholds." Floors are engineering judgment. |
| **opendataloader-pdf** | Hand-set floors only | `thresholds.json` (NID/TEDS/MHS); `check_regression()` uses `mean >= threshold - 0.02`; **no ROC fit** (`redteam/opendataloader-pdf.md`) |
| **marker** | Fixed floors | `verify_scores.py`: heuristic ≥90, TEDS ≥0.7; no labeled fit |
| **grobid** | Fixed constants | Levenshtein 0.8, Ratcliff 0.95 / 0.5 by context; documented, not ROC-fit |
| **camelot** | Fixed 0.8 | `confidence >= 0.8` in filter code |
| **img2table** | Embedded constants | Composite `table_score >= 0.425` + hard-reject ladder |
| **nougat / olmocr / pdf-to-markdown** | Hand-set / per-test tolerance | Generation heuristics, `max_diffs` scaling; no corpus ROC |
| **unstructured / tabula-java** | Per-doc diff, no fit | Regression on committed metrics, not threshold calibration |
| **whisker `calibrate.py`** | **ROC sweep + operating point** | Only surveyed project with labeled TPR/FPR/precision fit |

**Takeaway:** BUYing sklearn would import ML-metric machinery **the converter field does not use**. whisker's stdlib calibrator is already **ahead of the field** on methodology; the gap is **per-axis extension** (NID/TEDS/MHS floors), not ROC math.

---

## 4. VERDICT: **KEEP-AS-IS**

**Why (minimalism + determinism):**

1. **Minimalism ladder:** ~120 lines of stdlib, tested, do exactly one whisker-specific job. sklearn adds a heavy dependency to shrink a cold-path loop while **keeping** custom selection, adapter, and dataclass contract.
2. **Determinism:** Current code is a pure Python sweep with explicit sort and tie-breaks — no joblib, no thread pools, no `drop_intermediate` threshold pruning surprises.
3. **Semantic fit:** Inverted `< threshold` gate, higher-threshold tie-break, and full confusion counts are first-class; sklearn would be an impedance layer.
4. **Field context:** Nobody else calibrates; advantage is **having** principled fit, not **which library** computes TPR.

**Not BUILD-IMPROVE (numpy) now:** corpus size and clarity favor readable stdlib loops.

**Not BUY (sklearn):** cost >> benefit; operating-point logic remains ours regardless.

**Future work (separate from this BUILD-vs-BUY):** extend `calibrate_threshold` calls to bench axes (NID/TEDS/MHS), enforce `fail_edge <= review_edge`, holdout/bootstrap reporting — all compose on the **existing** sweep/selector without new deps.

---

## 5. Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| **Small-n overfit** on labeled corpus | Medium | Document min class size; future holdout/bootstrap (no new dep) |
| **Inverted fail/review band** when two independent fits | Medium | Already flagged in redteam; CLI ordering guard (separate from ROC lib choice) |
| **Identical-value ties** (good/bad same coverage) | Medium | Youden fallback + explicit tie-break; covered in tests |
| **sklearn adapter bug** if adopted later | High (if BUY) | Would need parity tests for inverted gate, sentinel threshold, tie-breaks — current stdlib avoids this class entirely |
| **Performance at large n** | Low today | Revisit numpy vectorization only if `n` ≫ 1k |
| **Per-axis calibration scope** | Medium (feature) | Extend current module; do not block on sklearn |

---

## References

- `packages/whisker/src/whisker/calibrate.py` — implementation
- `packages/whisker/tests/test_calibrate.py` — contract tests
- `packages/whisker/pyproject.toml` — numpy/scipy present; scikit-learn absent
- `packages/whisker/notes/cross-repo-qa-research.md` — "almost nobody calibrates"
- `packages/whisker/notes/redteam-synthesis.md` — calibrate hardening history
- scikit-learn `roc_curve` / `_binary_clf_curve`: stable sort, `drop_intermediate`, `score >= threshold` semantics (BSD-3-Clause)
