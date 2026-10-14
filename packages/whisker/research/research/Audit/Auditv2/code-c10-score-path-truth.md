# C10 Score-Path Truth

**Role:** Trace what actually influences verdicts and exit codes.
**Auditor scope:** `score.py` (`_decide`), `__main__.py` (exit code logic), `constants.py`
**Maps to:** D1 (determinism), D3 (advisory non-leakage)

## 1. Audited State

- whisker 0.5.0, HEAD 51cb704 + local mods
- `score.py`: 399 lines, `__main__.py`: 1338 lines, `constants.py`: ~200 lines
- All 1406 tests passing (E1)

## 2. Commands and Exits

```
E1:  uv run --package whisker pytest packages/whisker/tests  -> 1406 passed (exit 0)
```

## 3. Current Evidence

### 3.1 The `_decide` Function (score.py L136-231)

`_decide` is a pure function that takes 9 parameters and returns `(verdict, hard_flags, soft_flags)`. The verdict is strictly trichotomous: `pass`, `review`, `fail`.

**Hard fail paths (the ONLY ways to produce verdict=fail):**

1. **Structural gates failed** (L177-179):
   ```python
   for gate in gates:
       if not gate.passed:
           hard.append(f"gate:{gate.name}:{gate.detail or 'failed'}")
   ```

2. **Unigram coverage below fail edge** (L181-183):
   ```python
   if unigram_coverage < C.UNIGRAM_COVERAGE_FAIL_EDGE:  # 0.85
       hard.append(...)
   ```

3. **Verdict derivation** (L217-218): `if hard: return VERDICT_FAIL, hard, soft`

**Verified: ONLY these two conditions produce a hard fail.** No other code path appends to `hard`.

**Soft signal paths (produce verdict=review):**

- Unigram coverage in review band [0.85, 0.95) (L186-187)
- Region count >= `REGION_SOFT_COUNT` (L189-191)
- Unigram drift > `DRIFT_SOFT_EDGE` (L193-194)
- QA score < `QA_SCORE_SOFT_EDGE` (L195-196)
- Uncertain marker count > 0 (L197-198)
- `ref_nid < REF_NID_ADVISORY_EDGE` (L200-203) - **advisory only**
- Ideal panel below-floor axes (L205-215) - **advisory only**

**Verified: `ref_nid` is ADVISORY.** It only appends to `soft`, never to `hard`. The comment at L161-165 states this explicitly: "low `ref_nid` adds a review flag but NEVER hard-fails."

**Verified: ideal panel is ADVISORY.** L205-215 only append to `soft`, never to `hard`. The comment at L169-172 states: "flags are still ADVISORY (review, never hard fail)."

### 3.2 Benign-Region Fold (score.py L225-227)

When the ONLY soft flags are region flags AND unigram coverage >= `REGION_BENIGN_UNIGRAM_FLOOR` (0.95), the verdict is `pass` (not `review`). The region flags are kept but annotated `(benign)` for auditability.

```python
if soft and _is_benign_region_only(soft, unigram_coverage):
    benign_soft = [f"{f} (benign)" for f in soft]
    return VERDICT_PASS, hard, benign_soft
```

This is the only path that downgrades a would-be `review` to `pass`.

### 3.3 Exit Code Mapping (__main__.py L130-136)

```python
_GATE_ACCEPTS = {
    "pass": {"pass"},
    "review": {"pass", "review"},
    "fail": {"pass", "review", "fail"},
}

def _verdict_exit_code(verdicts, gate):
    accepted = _GATE_ACCEPTS[gate]
    if VERDICT_FAIL in verdicts and VERDICT_FAIL not in accepted:
        return C.EXIT_FAIL      # 5
    if VERDICT_REVIEW in verdicts and VERDICT_REVIEW not in accepted:
        return C.EXIT_REVIEW    # 3
    return C.EXIT_OK            # 0
```

**Exit code truth table** (default `--gate review`):

| Worst verdict | `--gate pass` | `--gate review` (default) | `--gate fail` |
|--------------|---------------|--------------------------|--------------|
| pass | 0 | 0 | 0 |
| review | 3 | 0 | 0 |
| fail | 5 | 5 | 0 |

Additional exit code: `1` (`EXIT_ERROR`) for operational errors (no backend, no papers, etc.), returned directly from error handlers, never from `_verdict_exit_code`.

### 3.4 Score-File Exit Codes (__main__.py L392-393)

The `score-file` subcommand has a parallel verdict logic (L377-393) that mirrors `_decide` but is simpler: gates -> hard, unigram coverage -> hard/soft, drift -> soft, ref_nid -> soft. Exit codes are directly mapped: `EXIT_FAIL if hard else EXIT_REVIEW if soft else EXIT_OK`.

### 3.5 Constants Trace

| Constant | Value | Role |
|----------|-------|------|
| `UNIGRAM_COVERAGE_FAIL_EDGE` | 0.85 | Hard fail threshold |
| `UNIGRAM_COVERAGE_REVIEW_EDGE` | 0.95 | Review band upper edge |
| `REF_NID_ADVISORY_EDGE` | 0.85 | Advisory-only review signal |
| `DRIFT_SOFT_EDGE` | 0.10 | Soft drift flag |
| `QA_SCORE_SOFT_EDGE` | 70 | Soft QA flag |
| `REGION_SOFT_COUNT` | 1 | Region flag threshold |
| `REGION_BENIGN_UNIGRAM_FLOOR` | 0.95 | Benign-fold coverage floor |
| `EXIT_OK` | 0 | CI: acceptable |
| `EXIT_ERROR` | 1 | CI: operational error |
| `EXIT_REVIEW` | 3 | CI: needs human |
| `EXIT_FAIL` | 5 | CI: broken |

## 4. Findings

### F1: Hard-fail paths are exactly two, as documented (INFO)

**Severity:** INFO | **Confidence:** HIGH

Code trace confirms: structural gate failure and `unigram_coverage < 0.85` are the only paths that append to `hard`. No other condition can produce a fail verdict. This matches the CLAUDE.md documentation exactly.

### F2: Reference NID is strictly advisory (INFO)

**Severity:** INFO | **Confidence:** HIGH

`ref_nid` (L200-203) only ever appends to `soft`, never to `hard`. The advisory status is correctly enforced in code, not just documented. `ref_teds` and `ref_mhs` are computed and reported but never flag at all (not even soft), matching the design that cross-converter table/heading metrics carry no reliable signal against a weak oracle.

### F3: Ideal panel is strictly advisory (INFO)

**Severity:** INFO | **Confidence:** HIGH

Ideal panel axes (L205-215) only append to `soft`. Below-floor axes raise review flags but never hard-fail. Null-eligibility (axis value is None) correctly skips flagging.

### F4: Exit code mapping is complete and monotonic (INFO)

**Severity:** INFO | **Confidence:** HIGH

The four exit codes (0, 1, 3, 5) cover all states. The `--gate` parameter correctly controls which verdicts are accepted. The mapping is monotonic: fail is always worse than review, review is always worse than pass. No gaps.

### F5: Benign-region fold has a narrow, documented scope (LOW)

**Severity:** LOW | **Confidence:** HIGH

The benign-region fold (L225-227) only fires when ALL soft flags end with "misaligned region(s)" AND unigram coverage >= 0.95. This is conservative: any non-region soft flag (drift, QA, coverage band, advisory) keeps the paper in review. The fold is the only verdict-downgrade path. Correctly annotated as `(benign)` for auditability.

## 5. False-Pass Hypothesis

**Q:** Could a paper pass when it should fail?

1. **Gate bypass:** Structural gates are iterated exhaustively (`for gate in gates`). A new gate added to `gates.py` automatically enters the fail path. No registration gap.

2. **Coverage bypass:** The fail edge (0.85) is a hard-coded constant. It cannot be overridden per-call or per-paper. The only way to change it is to edit `constants.py`.

3. **Advisory leak:** Could an advisory signal accidentally hard-fail? No: `ref_nid`, `ref_teds`, `ref_mhs`, and ideal axes only ever touch `soft`. The code structure makes this clear: only L177-183 touch `hard`.

4. **Benign fold over-promotion:** Could the benign fold hide a real problem? Only if unigram coverage >= 0.95 AND the only flags are region flags. At 0.95 coverage, content is demonstrably present; the fold is correct.

**Conclusion:** The score path is faithful to its documented contract.

## 6. Gate/Dimension Mapping

| Gate | Dimension | Status |
|------|-----------|--------|
| D1 Determinism | `_decide` is pure, no randomness, no LLM | PASS |
| D3 Advisory non-leakage | `ref_nid`/ideal never hard-fail, only soft | PASS |

## 7. Limitations

- This report traces static code paths. Runtime verification with actual paper data requires `WG21_DATA_DIR` (not available in this audit).
- The `score-file` subcommand has a parallel verdict implementation (not shared with `_decide`); divergence between the two is a maintenance risk, not verified to be impossible.
- Threshold calibration is PROVISIONAL (not fitted on labeled data); this report verifies the MECHANISM, not the OPERATING POINT.

## 8. Conclusion

The verdict path is truthful and minimal. Exactly two conditions produce hard fails (structural gates, unigram coverage < 0.85). Advisory signals (reference NID, ideal panel) are provably confined to soft flags. Exit codes map cleanly to the four-state CI contract (0/1/3/5). The benign-region fold is narrow and correctly annotated.

**Gate verdict: PASS**
