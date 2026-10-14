# 02 - The Calibration Statistician

**Verdict:** usable-with-conditions — the ROC fitter is mechanically correct and red-team-hardened, but every production threshold is a borrowed prior with zero measured operating points on this corpus, and the dominant fail/review drivers (heading gates, misaligned regions) sit outside what `calibrate` can tune.
**Confidence:** high

## Findings

- [CRITICAL] No threshold in production has ever been validated against labeled outcomes; TPR, FPR, and precision are **unknown for the live gate**. Evidence: `00-EVIDENCE-BASELINE.md` §5 ("Calibration: NEVER PERFORMED"; "No measured TPR / FPR / precision exists for any threshold"), `constants.py:11-15` ("PROVISIONAL … not yet a value fitted on a labeled corpus"). Impact: the 163/382 pass (42.7%) and 14/382 fail (3.7%) ref-free distribution (`00` §3a) are **unlabeled prevalence**, not estimated error rates; whisker cannot claim a 5% or 10% false-positive budget anywhere.

- [HIGH] The hard-fail tier is dominated by **structural gates**, not the unigram floor `calibrate` targets, so tuning `UNIGRAM_COVERAGE_FAIL_EDGE` alone cannot calibrate most failures. Evidence: ref-free run hard flags — `heading_monotone` 9, unigram `< 0.85` 3, `no_empty_table` 2 (`00` §3a); `gates.py:96-112` (`heading_monotone` hard-fails on H{n}→H{n+2}+ jumps); `__main__.py:827-838` (calibrate fits only `unigram_coverage`). Impact: even a perfect unigram ROC fit leaves **~64% of hard fails** (9/14) on an uncalibrated, non-fitting axis; false-fail rate from heading pedantry is unbounded.

- [HIGH] The review tier (205/382 = **53.7%**, majority triage) is driven by soft signals **`calibrate` does not model**, chiefly misaligned regions at an unc calibrated count of one. Evidence: soft rollup `misaligned regions 186` vs `unigram coverage in review band 54` (`00` §3a); `constants.py:47` (`REGION_SOFT_COUNT = 1`); `score.py:164-166` (any `missing_count + extra_count >= 1` → review); `CLAUDE.md:233-236` (regions "expected on clean papers"). Impact: calibrating the 0.85–0.95 unigram band predicts at most ~26% of review flags; **triage precision of the default path is structurally unmeasurable** from coverage ROC alone.

- [HIGH] `calibrate`'s label definitions **misalign with production verdict fusion**: the review fit treats `fail|review` labels as positives on coverage only, while live `_decide` stacks drift, QA, uncertain markers, and optional `ref_nid` independently. Evidence: `__main__.py:827-830` (`review_samples`: positive iff label ∈ {fail, review}); `score.py:156-178` (hard/soft from gates + unigram band + `unigram_drift` + regions + `qa_score` + `uncertain_count` + `ref_nid`). Impact: a fitted `unigram_coverage_review_edge` reports TPR/FPR for **one sub-rule**, not for `verdict == review`; promoting fitted edges would overstate how much review volume and FPR are controlled.

- [MED] The max-TPR-at-FPR-ceiling rule in `calibrate_threshold` is **standard and implemented correctly**, but the **operating-point contract is weak** on small, in-sample data. Evidence: `calibrate.py:150-195` (full-sample ROC sweep; feasible set `fpr <= target_fpr`; tie-break `(tpr, precision, threshold)` preferring higher threshold; Youden-J fallback when infeasible); `test_calibrate.py:13-80` (separable recovery, FPR ceiling, monotonic TPR); redteam-synthesis Tier 3 ("per-axis / stratified calibration" deferred; no k-fold). Impact: on n≈30–50 labels the chosen edge will be **optimistically biased** (in-sample TPR/FPR); Youden fallback (`calibrate.py:188-190`) can silently violate the advertised FPR ceiling when no point is feasible.

- [MED] A **single global unigram edge** is a weak model for this corpus: coverage is high on mass and rarely triggers fail, while format mix is bimodal. Evidence: stale run `unigram_coverage` mean **0.966**, only **12** papers below 0.85, **64** in 0.85–0.95 band (`00` §3b); source formats html **198** / pdf **184** (`00` §3b); `constants.py:37-38` (one pair of edges for all papers). Impact: the 0.85 fail edge fires on **~0.8%** of papers (3/382 ref-free) — extremely **low sensitivity** to content loss if the borrowed DP-Bench/Docling prior is too loose for WG21; stratified edges (html vs pdf, table-heavy vs prose) are absent, so pooled calibration would hide subgroup FPR inflation.

- [MED] Advisory `REF_NID_ADVISORY_EDGE = 0.85` is equally uncalibrated and likely **floods review** when the oracle is on. Evidence: `constants.py:85-87` (borrowed from edgeparse); stale run mean `ref_nid` **0.836**, **147/382** below 0.85 advisory edge (`00` §3b); `score.py:175-178` (advisory review only). Impact: with default oracle, ~**38%** of papers get an extra review signal with no measured precision; `--no-reference` removes it but leaves ref-free review at 54% anyway.

- [LOW] Documented FPR budget **disagrees across spec layers**: CLAUDE.md promises calibration at "FPR <= **10%**" (`CLAUDE.md:318`) while `DEFAULT_TARGET_FPR = **0.05**` (`calibrate.py:41-44`, `__main__.py:805-806`). Impact: operators may target the wrong operating point when labels arrive; not a code bug, but an audit-trail inconsistency for a statistics workflow.

## False-pass hypothesis

A conversion that **drops a non-repeated paragraph or scrambles a table cell** but keeps multiset token recall above **0.85** and passes structural gates (valid front matter, monotone headings, non-empty tables/code) would **pass** the hard gate. Evidence: only **3/382** ref-free fails on `unigram coverage < 0.85` (`00` §3a) while mean coverage is **0.966** (`00` §3b); `_decide` hard-fails coverage only below `UNIGRAM_COVERAGE_FAIL_EDGE` (`score.py:156-160`). Plausible on this corpus given the loose borrowed floor and high baseline unigram scores.

## False-fail hypothesis

**P3941R2/R3/R4** (cited in `00` §3c): papers with `uni=0.999`, `drift=0.001` that **fail solely** on `heading_monotone` (H2→H4 jump) — content metrics green, structural gate hard-fails (`gates.py:105-109`). Confirmed pattern in runtime rollup: **9/14** ref-free hard fails are `heading_monotone`, not missing words (`00` §3a).

## What would change my mind

A **held-out labeled set** (≥30 papers, pass/fail/review adjudicated by humans, stratified pdf/html) run through `whisker calibrate --labels …`, with **committed edges plus recorded in-sample and holdout TPR/FPR/precision**, and a demonstration that (a) ref-free **fail** rate on holdout matches the fail-edge FPR/TPR tradeoff and (b) **review** rate drops materially when misaligned-region and advisory rules are included in the calibration objective — not just unigram bands.
