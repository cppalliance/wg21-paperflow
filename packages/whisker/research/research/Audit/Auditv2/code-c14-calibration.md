# C14 Calibration

**Role:** Audit calibration status and the accuracy of calibration claims.
**Audited state:** whisker 0.5.0, HEAD 51cb704, Python 3.12.10, pytest 8.4.2.
**Date:** 2026-07-20

## 1. Scope

Verify that the `calibrate.py` workflow exists and is functional, that the
coverage band edges are documented as provisional, that the `calibrate` CLI
command is wired, and that no fitted edges are committed to `constants.py`.
Assess the accuracy of the C-CAL (calibration) claim.

## 2. Commands and Exits

| Evidence | Command / source | Exit |
|----------|-----------------|------|
| E1 | Full test suite 1406p/8s/3x | 0 |
| E4 | Core metric/scoring 218p | 0 |

## 3. Current Evidence

### 3.1 `calibrate.py` exists and is well-structured

The module (196 lines) implements a complete ROC-based calibration workflow:

**Core algorithm** (`calibrate_threshold`, lines 150-195):
- Takes `(value, is_bad)` labeled samples
- Sweeps all candidate thresholds (distinct partitions of observed values)
- Computes full ROC confusion (TP/FP/TN/FN) at each threshold
- Selects operating point: max TPR at `fpr <= target_fpr` (default 0.05),
  with tie-breaking by precision then by higher threshold (screening bias)
- Falls back to Youden's J maximizer when no threshold meets the FPR ceiling
- Input validation: rejects empty classes, non-finite values, out-of-range FPR

**Data model:**
- `OperatingPoint` (frozen dataclass): threshold, tpr, fpr, precision, tp/fp/tn/fn,
  youden_j property
- `CalibrationResult` (frozen dataclass): chosen point, target_fpr, method
  (max_tpr_at_fpr or youden_j), class counts, full ROC curve

**Output:** `to_dict()` produces a JSON-serializable result with the chosen
edge, its measured TPR/FPR/precision, the full ROC curve, and the selection
method.

### 3.2 CLI wiring

The `calibrate` command is documented in CLAUDE.md:
> `calibrate` emits fitted-edge JSON to stdout and optionally writes `--out`;
> it does not promote thresholds.

The command is listed in the CLAUDE.md "Module layout" and "Command history"
sections. It does not appear in the `[project.scripts]` of pyproject.toml
as a separate script; it is a subcommand of `whisker`.

### 3.3 Provisional edge documentation

`constants.py` explicitly documents the provisional status of every edge:

**Header comment** (lines 8-16):
> Every value here is a named module-level constant. The coverage band edges
> are PROVISIONAL: they encode the clean-paper expectation, not yet a value
> fitted on a labeled corpus. The `calibrate` workflow replaces them from
> real data and records the measured TPR/FPR/precision next to the chosen
> edges.

**Content coverage edges** (lines 21-37):
```python
# -- Content coverage band edges (PROVISIONAL, pre-calibration) --
UNIGRAM_COVERAGE_FAIL_EDGE = 0.85
UNIGRAM_COVERAGE_REVIEW_EDGE = 0.95
```

**Benchmark metric floors** (lines 60-74):
```python
# -- Benchmark metric floors (PROVISIONAL) --
TEDS_FLOOR = 0.80
MHS_FLOOR = 0.80
NID_FLOOR = 0.90
CONTENT_RECALL_FLOOR = 0.90
```

**Reference oracle edge** (lines 76-94):
```python
# Edge adopted from a literal repo constant: 0.85 = edgeparse's NID CI floor
REF_NID_ADVISORY_EDGE = 0.85
```

All edges are documented with their provenance (DP-Bench/Docling norms,
edgeparse CI floor, opendataloader-pdf thresholds) and their status
(provisional, pre-calibration, adopted from external repos).

### 3.4 No fitted edges committed

All values in `constants.py` are the provisional hand-set values documented
above. No `calibrate` output has been committed to replace them. Evidence:

- `UNIGRAM_COVERAGE_FAIL_EDGE = 0.85` matches the documented provisional
  value, not a fitted threshold with measured TPR/FPR.
- No `thresholds.json` artifact exists in the whisker package or fixtures.
- The CLAUDE.md "Calibration status" section confirms: "The unigram edges
  (0.85 fail / 0.95 review) mirror DP-Bench/Docling clean-conversion recall
  norms but remain provisional, not yet fitted on our own labeled corpus."

### 3.5 Calibration workflow design

The `calibrate.py` module follows a principled design:

1. **The module returns data; the CLI writes.** `calibrate_threshold` returns
   a `CalibrationResult` with the chosen edge and full ROC. The CLI decides
   where to write it.
2. **No automatic promotion.** Per CLAUDE.md: "it does not promote thresholds."
   A human reviews the fitted edge and its TPR/FPR/precision before manually
   updating `constants.py`.
3. **Honest selection reporting.** The `method` field reports whether the
   selection used `max_tpr_at_fpr` (FPR ceiling met) or `youden_j` (fallback).
4. **Full ROC exposure.** The entire curve is in the output, so a reviewer can
   inspect all candidate operating points, not just the chosen one.

### 3.6 C-CAL claim assessment

The CLAUDE.md calibration status accurately describes the current state:
- Edges are provisional (confirmed: no fitted values in constants.py)
- The calibrate workflow exists and is functional (confirmed: 196 LOC module)
- No fitted edges have been committed (confirmed: no thresholds.json)
- The upgrade path is documented (label 30-50 papers, pick max recall at
  FPR <= 10%, commit with recorded metrics)

### 3.7 Test coverage

The calibrate module is covered by tests (within the 218 core metric/scoring
tests). The `calibrate_threshold` function has input validation for:
- Non-finite sample values (raises ValueError)
- Single-class samples (raises ValueError)
- Out-of-range target_fpr (raises ValueError)

## 4. Findings

| # | Finding | Severity | Confidence |
|---|---------|----------|------------|
| F1 | `calibrate.py` implements a complete, well-structured ROC calibration workflow | PASS | HIGH |
| F2 | All coverage band edges are explicitly documented as PROVISIONAL | PASS | HIGH |
| F3 | No fitted edges have been committed to `constants.py` | PASS (expected state) | HIGH |
| F4 | The calibrate workflow does not auto-promote thresholds (human review required) | PASS | HIGH |
| F5 | Edge provenance is documented (DP-Bench, Docling, edgeparse, opendataloader-pdf) | PASS | HIGH |
| F6 | **The calibration workflow has not been executed on a labeled corpus.** This is the documented gap: the module exists, the edges are provisional, and the upgrade path is specified, but no labeled data set has been assembled. | MEDIUM | HIGH |
| F7 | The `calibrate` CLI subcommand is documented but not exercised in the test suite against real labeled data. Unit tests cover the algorithm; end-to-end coverage requires labeled samples. | LOW | MEDIUM |

## 5. False-Pass Hypothesis and Falsification

**Hypothesis:** The calibration module could produce incorrect operating
points if the confusion matrix computation has an off-by-one error in the
`value < threshold` rule.

**Falsification:** The `_confusion` function (lines 103-121) uses strict
`value < threshold` for flagging, which is the standard convention for
lower-is-worse gates (flag everything strictly below the threshold). The
`_candidate_thresholds` function (lines 124-134) generates one threshold at
each observed value plus one above the maximum, covering all possible
partitions. The tie-breaking rule (max tpr, then max precision, then higher
threshold) biases toward catching bad papers (screening bias), which is
appropriate for a quality gate.

## 6. Gate/Dimension Mapping

| Gate | Dimension | Status |
|------|-----------|--------|
| D4: Scoring accuracy | Threshold calibration | PROVISIONAL |
| D5: Corpus integrity | Calibration data | NOT STARTED |

## 7. Limitations

- No labeled calibration dataset exists. The calibration module is ready but
  unused. This is a documented gap with a specified upgrade path.
- The provisional edges have a known history of two earlier designs that
  over-failed (documented in CLAUDE.md "Calibration status"). The current
  edges are the third iteration, informed by field survey but not empirically
  fitted.
- The `calibrate` subcommand's integration with the CLI is documented but not
  independently verified by an end-to-end test in this audit (would require
  labeled data).

## 8. Conclusion

The calibration infrastructure is architecturally sound: a complete ROC
calibration module exists, all edges are honestly documented as provisional
with their provenance, no fitted edges have been committed, and the upgrade
path is specified. The calibration module follows the "returns data, CLI
writes" invariant and requires explicit human promotion. The primary gap is
that the workflow has not been executed on a labeled corpus, which is the
documented next step. The C-CAL claim is accurate: provisional edges, ready
infrastructure, pending labeled data.
