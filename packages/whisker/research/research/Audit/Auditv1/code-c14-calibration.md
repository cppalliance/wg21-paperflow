# C14 -- Calibration Auditor

**Mandate:** Evaluate the implemented ROC workflow and provisional constants.
**Auditor role:** Calibration Auditor
**Date:** 2026-07-19
**Scope:** `calibrate.py`, `test_calibrate.py`, `_calibrate_main` in `__main__.py`, `constants.py`
**Focus dimension:** D4 (construct validity of the calibration workflow)

---

## 1. Calibration Workflow: `calibrate.py`

### F1: `calibrate_threshold` exists and implements a full ROC sweep

- **Severity:** INFO (confirmed correct)
- **Claim:** `calibrate_threshold` takes labeled `(value, is_bad)` samples, sweeps every candidate threshold that produces a distinct partition, computes the full ROC confusion (TP/FP/TN/FN, TPR/FPR/precision) at each, and selects the operating point.
- **Evidence:** `calibrate.py:150-195` -- the function signature, the threshold sweep via `_candidate_thresholds`, the `_point` computation at each threshold, and the selection logic.
- **Affected gate:** D4 (ROC correctness)
- **Confidence:** HIGH

### F2: Selection maximizes TPR at FPR ceiling, falls back to Youden-J

- **Severity:** INFO (confirmed correct)
- **Claim:** Primary: maximize TPR among thresholds with `fpr <= target_fpr` (tie-break: higher precision, then higher threshold). Fallback: when no threshold meets the FPR ceiling, maximize Youden's J (TPR - FPR).
- **Evidence:** `calibrate.py:184-190` -- `feasible = [op for op in curve if op.fpr <= target_fpr]`; if feasible, `max(feasible, key=lambda op: (op.tpr, op.precision, op.threshold))`; else `max(curve, key=lambda op: (op.youden_j, op.precision, op.threshold))`.
- **Affected gate:** D4 (selection correctness)
- **Confidence:** HIGH
- **False-pass hypothesis:** The tie-break on higher threshold (catch more, screening bias) is intentional and documented.
- **False-fail hypothesis:** The Youden fallback is a global maximizer, not constrained by FPR. This is the correct fallback when strict FPR control is infeasible.

### F3: Reports TPR/FPR/precision alongside the chosen edge

- **Severity:** INFO (confirmed correct)
- **Claim:** `CalibrationResult` carries the chosen `OperatingPoint` (with `tpr`, `fpr`, `precision`, `tp`, `fp`, `tn`, `fn`), the `target_fpr`, the selection `method`, class counts, and the full ROC `curve`.
- **Evidence:** `calibrate.py:80-100` -- `CalibrationResult` dataclass with `to_dict` serialization.
- **Confidence:** HIGH

### F4: Calibration is informational (never auto-promotes edges)

- **Severity:** INFO (confirmed correct)
- **Claim:** `calibrate.py` returns data only. The CLI writes a `thresholds.json` artifact but NEVER writes to `constants.py`. The module docstring states: "a human promotes the values into constants.py (thresholds are deliberate)". The constants docstring confirms: "The `calibrate` workflow replaces them from real data and records the measured TPR/FPR/precision next to the chosen edges."
- **Evidence:** `calibrate.py:24-27` module docstring. `__main__.py:1061-1160` (`_calibrate_main`) writes to `args.out` (a JSON file) and prints to stdout, never modifying any Python source.
- **Affected gate:** D4 (calibration authority boundary)
- **Confidence:** HIGH

### F5: Edge-ordering sanity check (fail < review)

- **Severity:** INFO (confirmed correct)
- **Claim:** `_calibrate_main` fits two edges independently (fail edge and review edge). If the fitted fail edge exceeds the review edge (an inverted, meaningless band), a WARNING is emitted: "inverted band, do NOT promote as-is."
- **Evidence:** `__main__.py:1115-1120` -- `edge_ordering_ok = fail_edge <= review_edge; if not edge_ordering_ok: logger.warning(...)`.
- **Affected gate:** D4 (edge consistency)
- **Confidence:** HIGH
- **False-pass hypothesis:** The check is a warning, not a hard error. A careless human could still promote an inverted band. The warning text is explicit ("do NOT promote as-is").

### F6: Input validation is strict

- **Severity:** INFO (confirmed correct)
- **Claim:** `calibrate_threshold` raises `ValueError` if: (a) `target_fpr` is outside [0, 1], (b) any sample value is non-finite (NaN/inf), or (c) either class is empty (no positive or no negative samples).
- **Evidence:** `calibrate.py:167-179`. Tests: `test_requires_both_classes`, `test_target_fpr_out_of_range_raises`, `test_nonfinite_sample_value_raises`.
- **Confidence:** HIGH

---

## 2. Calibration Has NOT Been Run on Production Data

### F7: All edges are borrowed/provisional

- **Severity:** MEDIUM (D4, honest limitation)
- **Claim:** The current content-coverage edges (`UNIGRAM_COVERAGE_FAIL_EDGE = 0.85`, `UNIGRAM_COVERAGE_REVIEW_EDGE = 0.95`) are PROVISIONAL, adopted from external benchmarks (DP-Bench/Docling clean-conversion recall norms, edgeparse NID CI floor), NOT fitted on the whisker corpus.
- **Evidence:** `constants.py:20-37` -- comment block states "PROVISIONAL, pre-calibration" and documents the source of each edge. `constants.py:92-94` -- `REF_NID_ADVISORY_EDGE = 0.85` "adopted from a literal repo constant: edgeparse's NID CI floor". CLAUDE.md "Calibration status" section: "the unigram edges (0.85 fail / 0.95 review) mirror DP-Bench/Docling clean-conversion recall norms but remain provisional, not yet fitted on our own labeled corpus."
- **Affected gate:** D4 (calibration maturity)
- **Confidence:** HIGH
- **Upgrade path:** "A calibrate step (label 30-50 papers, pick max recall at FPR <= 10%, commit fitted edges with recorded TPR/FPR/precision) would replace these with measured operating points."

### F8: The calibrate CLI wires everything needed for a real fit

- **Severity:** INFO (confirmed correct)
- **Claim:** `_calibrate_main` loads labeled samples (from a JSON file with optional pre-computed `unigram_coverage`), builds two sets of binary labels (fail-edge: positive = label fail; review-edge: positive = fail OR review), calls `calibrate_threshold` for each, checks edge ordering, and writes the result.
- **Evidence:** `__main__.py:1061-1160`. The sample loader supports both `{pid, label, unigram_coverage}` records and `{pid: label}` maps (computing coverage from the backend on the fly).
- **Confidence:** HIGH

---

## 3. Test Coverage Assessment (`test_calibrate.py`)

| Test | What it covers |
|------|----------------|
| `test_separable_data_recovers_a_perfect_edge` | Perfect separation: TPR=1.0, FPR=0.0, precision=1.0 |
| `test_fpr_ceiling_is_respected` | Overlapping classes: FPR=0.0 ceiling honored |
| `test_youden_fallback_when_no_threshold_meets_ceiling` | Infeasibility: Youden-J fallback |
| `test_requires_both_classes` | Error: empty class raises ValueError |
| `test_confusion_counts_are_consistent` | Invariant: TP+FN = n_pos, FP+TN = n_neg, rates in [0,1] |
| `test_monotonic_tpr_along_increasing_threshold` | Monotonicity: TPR non-decreasing as threshold rises |
| `test_result_is_json_serializable` | Serialization round-trip |
| `test_target_fpr_out_of_range_raises` | Error: invalid FPR range (negative, >1, NaN) |
| `test_nonfinite_sample_value_raises` | Error: NaN/inf sample values rejected |

**Gaps:** No test exercises the `_calibrate_main` CLI path end-to-end (integration test). No test checks the edge-ordering warning with an inverted band. These are acceptable gaps for a workflow that has not yet been run on production data.

---

## 4. Confusion Matrix Correctness

### F9: `_confusion` implements the "flag iff value < threshold" rule correctly

- **Severity:** INFO (confirmed correct)
- **Claim:** `_confusion` counts TP (is_pos AND flagged), FN (is_pos AND not flagged), FP (not is_pos AND flagged), TN (not is_pos AND not flagged) where `flagged = value < threshold`.
- **Evidence:** `calibrate.py:103-121`. The "lower is worse" convention matches the content-coverage domain (low coverage = bad paper).
- **Confidence:** HIGH

### F10: Candidate thresholds cover all distinct partitions

- **Severity:** INFO (confirmed correct)
- **Claim:** `_candidate_thresholds` returns the sorted unique values plus one point above the max, covering every distinct `value < t` partition boundary.
- **Evidence:** `calibrate.py:124-134`.
- **Confidence:** HIGH

---

## 5. Summary

| Finding | Severity | Dimension | Verdict |
|---------|----------|-----------|---------|
| F1: Full ROC sweep implemented | INFO | D4 | CONFIRMED |
| F2: TPR-at-FPR selection + Youden fallback | INFO | D4 | CONFIRMED |
| F3: Reports TPR/FPR/precision | INFO | D4 | CONFIRMED |
| F4: Never auto-promotes edges | INFO | D4 | CONFIRMED |
| F5: Edge-ordering sanity check | INFO | D4 | CONFIRMED |
| F6: Strict input validation | INFO | D4 | CONFIRMED |
| F7: All edges provisional/borrowed | MEDIUM | D4 | CONFIRMED (documented honestly) |
| F8: CLI wires complete calibration path | INFO | D4 | CONFIRMED |
| F9: Confusion matrix correct | INFO | D4 | CONFIRMED |
| F10: Threshold candidates complete | INFO | D4 | CONFIRMED |

**Overall assessment:** The calibration workflow is structurally sound, correctly implements ROC-based threshold selection, and enforces a strict human-in-the-loop promotion ceremony. The edges are honestly documented as provisional. The workflow has not yet been run on production data; this is the stated next step requiring 30-50 labeled papers.
