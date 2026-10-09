# Repo scan: Nougat (Meta)

**Does it verify LLM-readability?** **no**

Nougat evaluates PDF→markdown output with **gold-string similarity only**: char-level normalized edit distance, BLEU, METEOR, and word-token **set-F1**, reported per modality (Text / Math / Tables). There are no fact assertions, no LLM read-back, no downstream QA, no comprehension corpus, and no LLM-as-judge path. Set-F1 is order-invariant **token-set overlap**, not "can an LLM recover paper facts from this markdown."

---

## Findings

1. **[HIGH] Core metric suite is pure text-similarity against gold LaTeX/markdown** — `compute_metrics` returns char-NED (`edit_distance / max(len)`), BLEU, METEOR, precision/recall/F1 on whitespace-split **word sets**. Evidence: `nougat/metrics.py:27-44`. Impact: structural-fidelity / resemblance gate only; a scrambled-order markdown with all words present can score high on set-F1 while failing comprehension.

2. **[HIGH] Modality-stratified scoring (Text / Math / Tables), never merged for gating** — `split_text` strips inline math `\(...\)`, display math `\[...\]`, and `tabular` blocks into separate channels before metrics; CLI prints independent corpus means per stratum. Evidence: `nougat/metrics.py:22-24,63-83,104-117`. Impact: portable **axis stratification** pattern for whisker bench/guard; not comprehension.

3. **[HIGH] Set-F1 is word-set F1, not fact recovery** — `reference = set(gt.split())`, `hypothesis = set(pred.split())`, then `nltk.scores.f_measure`. Evidence: `nougat/metrics.py:39-43`. Impact: closest Nougat gets to "content coverage" is bag-of-words overlap; no neighbor/table/math assertions like olmOCR-bench or whisker Lane 3.

4. **[MED] Offline aggregate eval only; no regression baseline or CI** — `test.py` runs inference, accumulates running means per batch, writes one JSON blob (`predictions`, `ground_truths`, per-metric arrays). Evidence: `test.py:27-95`, `README.md:168-180`. No `.github/workflows`, no pytest suite (only root `test.py` inference script). Impact: negative control for whisker guard; Nougat cannot detect per-paper regressions.

5. **[MED] Short-sample exclusion (`minlen=4`)** — pages where pred or gt length `< 4` return `{}` and are omitted from stratum averages, not scored as zero. Evidence: `nougat/metrics.py:27-30,93-96`. Impact: portable **eligibility gate**; prevents empty conversions from polluting or zeroing means.

6. **[MED] Explicit conversion-failure taxonomy in output** — failed pages emit `[MISSING_PAGE_EMPTY:…]`, `[MISSING_PAGE_FAIL:…]`, `[MISSING_PAGE_POST]` via generation heuristics. Evidence: `predict.py:178-191`, `postprocessing.py:323-328`. Impact: portable **failure-marker detection** for whisker baseline rows (not metric-based LLM-readability).

7. **[MED] Reference-free failure detection at inference (not eval scoring)** — repetition/variance heuristics in `StoppingCriteriaScores` (threshold `0.015`, `model.py:443-474`) and post-decode varvar check (`model.py:627-645`, varvar `< 0.045`). Impact: advisory conversion-quality signal; whisker lacks equivalent on bench path (redteam aligns).

8. **[MED] Postprocessing for metric stability, not comprehension** — `markdown_compatible`, hallucination removal, repetition truncation applied before saved output (`predict.py:193-194`, `postprocessing.py:332-363`). `remove_numbers` strips digits/underscores for slice detection (`postprocessing.py:178-187`). Impact: normalization-before-diff pattern; does not test LLM consumability.

9. **[LOW] Training validation reuses same similarity metrics** — validation epoch logs mean edit_dist/BLEU/etc. from `get_metrics`. Evidence: `lightning_module.py:95-98`. Impact: confirms eval philosophy is end-to-end string match, not downstream task performance.

10. **[CONFIRMED ABSENT] Comprehension, fact assertions, LLM judge, downstream QA, pytest** — repo has no `facts`, `comprehension`, `QA`, or `LLM` eval modules; evaluation section documents only `test.py` + `python -m nougat.metrics` (`README.md:168-180`).

---

## Portable to whisker (ranked)

1. **Per-stratum dual metric: char-NED + word-set F1, regressed independently** — add `text_set_f1`, `math_set_f1`, `table_set_f1` (or doc-level set-F1 on normalized tokens) to `BenchRow`/baseline; never let `overall` absorb cross-stratum tradeoffs. Source: `nougat/metrics.py:31-43,104-117`. Highest ROI from Nougat; complements whisker `unigram_coverage` on score path.

2. **`minlen` / insufficient-content eligibility** — fail or mark `scorable: false` when conversion below minimum token/block count instead of diffing meaningless 1.0 TEDS on empty tables. Source: `nougat/metrics.py:27-30`.

3. **Modality strip before text-axis diff** — score text channel after extracting inline/display math and tabular blocks (mirror `split_text`), reducing delimiter churn in NID. Source: `nougat/metrics.py:63-83`.

4. **`[MISSING_PAGE_*]` marker gate** — baseline field counting failure markers; hard-fail on new markers even if metrics flat. Source: `predict.py:178-191`.

5. **Inference confidence heuristics as advisory (not gate)** — generation-score variance thresholds as reference-free `conversion_ok` hint. Source: `model.py:443-474,627-645`.

6. **Low priority:** BLEU/METEOR (Nougat prints but does not gate on them; METEOR can NaN-poison means — `metrics.py:37-38`, `test.py:84`).

**Not portable as LLM-readability proof:** entire Nougat eval stack compares to **training-domain gold strings**, not whether dissect/agora can recover facts. Whisker Lane 3 (`facts.py`) remains the comprehension lane; Nougat contributes **bench metric shape** only.

---

## Cross-check vs redteam report (`packages/whisker/research/redteam/nougat.md`)

| Redteam claim | Verdict | Evidence |
|---------------|---------|----------|
| No committed regression baseline, no CI, no pytest QA suite | **CONFIRMED** | `test.py:73-95` (aggregate JSON only); no `.github/`; no `tests/` directory |
| Modality-stratified dual metrics Text/Math/Tables | **CONFIRMED** | `nougat/metrics.py:63-117` |
| Set-F1 on word-token sets per stratum | **CONFIRMED** | `nougat/metrics.py:39-43` |
| Strips math/tables from text channel before text metric | **CONFIRMED** | `nougat/metrics.py:70-81` |
| `minlen=4` sample exclusion | **CONFIRMED** | `nougat/metrics.py:27-30` |
| `[MISSING_PAGE_*]` failure taxonomy | **CONFIRMED** | `predict.py:178-191` |
| Post-hoc normalization (`remove_numbers`, `markdown_compatible`) | **CONFIRMED** | `postprocessing.py:178-187,332-363`; wired at `predict.py:193-194` |
| Aggregate corpus means only (no per-item diff) | **CONFIRMED** | `test.py:79-84`, `metrics.py:117` |
| No ROC calibration / floors | **CONFIRMED** | no threshold module; hand-set inference constants only |
| BLEU/METEOR reported per stratum | **CONFIRMED** | `nougat/metrics.py:34-37` |

**Scope correction vs redteam:** redteam frames Nougat vs whisker **guard/calibrate** (regression plumbing). This scan adds: Nougat has **zero LLM-readability verification**; set-F1 is still gold-string token overlap, not olmOCR-style fact assertions or blind LLM read-back. Redteam's "top portable detail" (set-F1) is confirmed and ranked #1 here for **bench axis design**, not comprehension.

**No contradictions found** on cited line references.

---

*Sources: shallow clone at `packages/whisker/research/repos/nougat/` (facebookresearch/nougat, read-only, July 2026).*
