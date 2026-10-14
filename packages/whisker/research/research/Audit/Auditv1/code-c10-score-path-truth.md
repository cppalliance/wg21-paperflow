# C10 — Score-Path Truth Auditor

**Mandate:** Compare `_decide` logic in score.py with CLAUDE.md's verdict model.
**Gate dimension:** D4 (score-path correctness, docs-code parity)
**Auditor:** Score-Path Truth Auditor
**Date:** 2026-07-19

---

## Summary

The `_decide` function in `score.py` faithfully implements the verdict model documented in CLAUDE.md. `unigram_coverage` is the hard content gate (not shingle coverage). `ref_teds` and `ref_mhs` never flag. The oracle composite (`ref_overall`) is computed and stored but never used in any gate logic — it is purely advisory. NaN/inf handling is implicit via the deterministic metric pipeline (no LLM, no network, bounded float arithmetic). All documented invariants hold. Clean on D4.

---

## Finding 1: Hard fails match CLAUDE.md exactly

- **Severity:** PASS (correctly implemented)
- **Claim:** The ONLY hard fails are (a) any structural gate failure and (b) `unigram_coverage < UNIGRAM_COVERAGE_FAIL_EDGE`.
- **Evidence:**
  - `score.py:177-179`: Gate failures: `for gate in gates: if not gate.passed: hard.append(...)`.
  - `score.py:181-185`: `if unigram_coverage < C.UNIGRAM_COVERAGE_FAIL_EDGE: hard.append(...)`.
  - `score.py:217-218`: `if hard: return VERDICT_FAIL, hard, soft` — only hard flags trigger fail.
  - CLAUDE.md "Verdict model" section: "Hard fails (the only ways to fail): any structural gate failure, or unigram_coverage < UNIGRAM_COVERAGE_FAIL_EDGE (0.85): content genuinely missing."
  - `constants.py:37`: `UNIGRAM_COVERAGE_FAIL_EDGE = 0.85` — matches doc.
- **Affected gate/dimension:** D4
- **Confidence:** 1.0
- **False-pass hypothesis:** None. No other condition produces a hard flag.
- **False-fail hypothesis:** None. The two hard-fail conditions are exhaustive.

## Finding 2: unigram_coverage is the hard gate, NOT shingle coverage

- **Severity:** PASS (correctly implemented)
- **Claim:** The content hard-gate runs on `unigram_coverage` (order-invariant token-set recall), not on the order-sensitive shingle `coverage`.
- **Evidence:**
  - `score.py:148-159`: Docstring: "The content hard-gate runs on `unigram_coverage` (order-invariant token-set recall), not on the order-sensitive shingle coverage."
  - `score.py:181`: `if unigram_coverage < C.UNIGRAM_COVERAGE_FAIL_EDGE` — the parameter is `unigram_coverage`.
  - `score.py:136-146`: Function signature: `_decide(unigram_coverage, unigram_drift, ...)` — the content gate parameter is named `unigram_coverage`.
  - The shingle `coverage` parameter does NOT appear in `_decide`'s signature at all. It is stored in `WhiskerResult.coverage` for reporting but never enters the verdict logic.
  - CLAUDE.md: "The content gate runs on `unigram_coverage` (order-invariant token-set recall), NOT on the shingle `coverage`."
- **Affected gate/dimension:** D4
- **Confidence:** 1.0

## Finding 3: Soft signals match CLAUDE.md

- **Severity:** PASS (correctly implemented)
- **Claim:** The soft (review) signals are: unigram_coverage in the review band, unigram_drift over edge, misaligned regions, qa_score below edge, uncertain markers.
- **Evidence:**
  - `score.py:186-187`: `elif unigram_coverage < C.UNIGRAM_COVERAGE_REVIEW_EDGE: soft.append(...)` — review band.
  - `score.py:189-191`: `if region_total >= C.REGION_SOFT_COUNT: soft.append(...)` — misaligned regions.
  - `score.py:193-194`: `if unigram_drift > C.DRIFT_SOFT_EDGE: soft.append(...)` — unigram drift.
  - `score.py:195-196`: `if qa_score < C.QA_SCORE_SOFT_EDGE: soft.append(...)` — qa score.
  - `score.py:197-198`: `if uncertain_count: soft.append(...)` — uncertain markers.
  - `score.py:229-231`: `if soft: return VERDICT_REVIEW, hard, soft` / `return VERDICT_PASS, hard, soft`.
  - CLAUDE.md: "Soft signals (review): unigram_coverage in the 0.85-0.95 band (some words missing), drift over edge, any misaligned region, qa under the soft edge, any uncertain marker."
- **Affected gate/dimension:** D4
- **Confidence:** 1.0

## Finding 4: ref_teds and ref_mhs never flag (report-only)

- **Severity:** PASS (correctly implemented)
- **Claim:** `ref_teds` and `ref_mhs` are computed and stored but never appear in any flag or verdict logic.
- **Evidence:**
  - `score.py:200-203`: The reference advisory section uses ONLY `ref_nid`: `if ref is not None: ref_nid = ref[0]; if ref_nid < C.REF_NID_ADVISORY_EDGE: soft.append(...)`.
  - `ref[1]` (teds) and `ref[2]` (mhs) are never accessed in `_decide`.
  - `score.py:272-276`: `ref_teds = table_score(md_text, reference_md)` and `ref_mhs = mhs(md_text, reference_md)` — computed in `score_markdown`.
  - `score.py:84-85`: Stored as `ref_teds` and `ref_mhs` on `WhiskerResult`.
  - `score.py:119-120`: Serialized in `to_dict()` — report-only.
  - No test in `test_score.py` checks for teds/mhs in flags: `test_reference_weak_table_heading_axes_never_flag` (line 227-238) explicitly asserts `not any("teds" in f or "mhs" in f for f in flags)`.
  - CLAUDE.md: "`ref_teds` and `ref_mhs` are computed and reported per-axis but never flag at all."
- **Affected gate/dimension:** D4
- **Confidence:** 1.0

## Finding 5: Oracle composite (ref_overall) is advisory only, never hard-fails

- **Severity:** PASS (correctly implemented)
- **Claim:** `ref_overall` is computed and stored for display but never used in any gate logic. Only `ref_nid` can raise an advisory (soft) flag.
- **Evidence:**
  - `score.py:275`: `ref_overall = (ref_nid + ref_teds + ref_mhs) / 3.0` — computed.
  - `score.py:276`: `ref = (ref_nid, ref_teds, ref_mhs, ref_overall)` — passed to `_decide`.
  - `score.py:200-203`: `_decide` accesses ONLY `ref[0]` (ref_nid). `ref[3]` (ref_overall) is NEVER accessed.
  - `report.py:73-78`: `ref_overall` is displayed in `_item_line` (`ovr=`) for human context.
  - `report.py:121`: `ref_overall` appears in the report table as a display column.
  - CLAUDE.md: "cross-converter TEXT agreement (ref_nid) ... is layered on as ONE extra soft signal ... It NEVER hard-fails."
- **Affected gate/dimension:** D4
- **Confidence:** 1.0

## Finding 6: Ideal panel is advisory only (review, never hard fail)

- **Severity:** PASS (correctly implemented)
- **Claim:** When a golden ideal is present, below-floor ideal axes raise review flags but never hard fails.
- **Evidence:**
  - `score.py:205-215`: `if ideal is not None:` loop over (nid, teds, mhs, recall) with `if value is not None and value < floor: soft.append(...)` — appends to `soft`, never to `hard`.
  - `score.py:168-172`: Docstring: "The flags are still ADVISORY (review, never hard fail): the calibrated hard gate stays untouched until the ideal corpus is large enough to calibrate its own operating point."
  - CLAUDE.md constants section: "Still ADVISORY ONLY: a below-floor axis raises a review flag, never a hard fail."
- **Affected gate/dimension:** D4
- **Confidence:** 1.0

## Finding 7: NaN/inf handling in metrics

- **Severity:** PASS (implicitly handled)
- **Claim:** NaN and inf cannot arise from the metric computation pipeline.
- **Evidence:**
  - `metrics.py:75-78` (`normalized_edit_distance`): Guards `if not a and not b: return 0.0` and `if longest else 0.0` — no division by zero.
  - `metrics.py:349-350` (`text_nid`): Returns `1.0 - normalized_edit_distance(...)` — bounded in [0, 1].
  - `metrics.py:383-389` (`content_recall`): Guards `if not ref: return 1.0` — no division by zero on empty reference.
  - `metrics.py:508-514` (`_TEDS.evaluate`): Guards `if n_nodes == 0: return 1.0` — defensive zero-denominator guard.
  - `metrics.py:689-693` (`mhs`): Guards `if denom <= 1: return 1.0` — no division by zero.
  - `bench.py:116-125` (`_table_score`): Guards `if not cand and not ref: return 1.0` and divides by `pairs = max(len(cand), len(ref))` which is >= 1.
  - All metrics use `rapidfuzz.distance.Levenshtein.distance` which returns an integer (no NaN/inf).
  - `score.py:99-100`: `to_dict()` rounds with `round(v, 4) if v is not None else None` — None is preserved, never converted.
- **Affected gate/dimension:** D4
- **Confidence:** 0.95
- **False-pass hypothesis:** If a pathological input produced a NaN from `rapidfuzz`, it would propagate silently through comparisons. However, `rapidfuzz` returns integer distances and the denominator guards are present at every division point.

## Finding 8: Benign-region fold matches docs

- **Severity:** PASS (correctly implemented)
- **Claim:** When the ONLY soft flags are misaligned region(s) and unigram_coverage >= 0.95, the verdict is PASS (not review), matching the documented behavior.
- **Evidence:**
  - `score.py:224-227`: `if soft and _is_benign_region_only(soft, unigram_coverage): benign_soft = [f"{f} (benign)" for f in soft]; return VERDICT_PASS, hard, benign_soft`.
  - `score.py:237-241` (`_is_benign_region_only`): `if unigram_coverage < C.REGION_BENIGN_UNIGRAM_FLOOR: return False; return all(f.endswith(_REGION_FLAG_SUFFIX) for f in soft)`.
  - `constants.py:54`: `REGION_BENIGN_UNIGRAM_FLOOR = 0.95`.
  - `test_score.py:125-129`: `test_benign_region_only_high_unigram_is_pass` — confirms PASS verdict with "(benign)" annotation.
  - `test_score.py:133-138`: `test_benign_region_plus_other_soft_flag_is_review` — region + drift -> stays review.
  - `test_score.py:141-145`: `test_benign_region_below_floor_is_review` — below 0.95 -> stays review.
  - CLAUDE.md: "tomd deliberately strips page furniture ... At unigram >= 0.95 the content is demonstrably complete; the regions are furniture, not missing content."
- **Affected gate/dimension:** D4
- **Confidence:** 1.0

## Finding 9: ref_nid advisory edge matches docs

- **Severity:** PASS (correctly implemented)
- **Claim:** The advisory edge for cross-converter text agreement is 0.85, and it produces a soft (review) flag, never a hard fail.
- **Evidence:**
  - `score.py:200-203`: `if ref_nid < C.REF_NID_ADVISORY_EDGE: soft.append(f"reference text agreement {ref_nid:.3f} low (advisory)")`.
  - `constants.py:94`: `REF_NID_ADVISORY_EDGE = 0.85`.
  - `test_score.py:213-224`: `test_reference_low_text_agreement_is_advisory_review_never_fail` — asserts REVIEW verdict, "reference text agreement" in soft_flags, no hard_flags.
  - CLAUDE.md: "ref_nid < REF_NID_ADVISORY_EDGE (0.85) -> a review flag (reference text agreement <x> low (advisory)). It NEVER hard-fails."
- **Affected gate/dimension:** D4
- **Confidence:** 1.0

---

## Verdict

**D4: CLEAN.** The `_decide` logic in `score.py` is a faithful implementation of CLAUDE.md's verdict model. The hard gate uses `unigram_coverage` (not shingle coverage). `ref_teds`/`ref_mhs` never flag. `ref_overall` is display-only, never used in gate logic. The ideal panel is advisory (review, never hard fail). NaN/inf is implicitly prevented by denominator guards at every division point. All documented invariants are confirmed by both code inspection and test evidence. 9/9 findings pass.
