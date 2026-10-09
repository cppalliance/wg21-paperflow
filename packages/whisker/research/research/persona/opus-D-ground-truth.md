# Opus D - Ground-Truth, Corpus, Comprehension & Downstream Trust

**Verdict:** usable-with-conditions — whisker is an honest, well-engineered smoke test that catches gross breakage (truncation, structural malformation); it cannot certify conversion correctness, comprehension safety, or table/math fidelity because no ground truth exists and 3 of 4 scoring lanes are inert on real data.
**Confidence:** high (all claims verified against live runtime and filesystem)

---

## Claim verification

| # | Claim (from baseline / personas) | Verdict | Evidence |
|---|---|---|---|
| 1 | Corpus is empty (only README + EXAMPLE.facts.jsonl) | **CONFIRMED** | `dir corpus\` shows exactly 2 files (787 B + 3471 B). `Get-ChildItem data -Filter *.facts.jsonl -Recurse` and `*.gt.md`: zero results. |
| 2 | Lanes 1/2/3 non-operational on real data | **CONFIRMED** | `whisker facts --corpus packages/whisker/corpus` exits error: "no <pid>.facts.jsonl files with a staged candidate found". No `.gt.md` or `.expected.md` exist anywhere in repo or data dir. |
| 3 | Ref-free verdict: 14 fail / 205 review / 163 pass on 382 papers | **CONFIRMED** | Live run `whisker --all --no-reference --no-write --stats` (exit 5): "14 failed, 205 review, 163 passed (382 scored) in 100.4s". Matches baseline exactly. |
| 4 | ref_nid mean 0.836, 147/382 below 0.85 advisory edge | **CONFIRMED** | PowerShell extraction from stale `data/whisker/report.json`: mean=0.8362, below085=147. Schema is 1 (stale vs code schema 3). |
| 5 | Calibration never performed; thresholds provisional | **CONFIRMED** | `constants.py:10-15`: "PROVISIONAL ... not yet a value fitted on a labeled corpus". No `labels.json` or `thresholds.json` anywhere. `calibrate` CLI exists but has never been run with real labels. |
| 6 | 9/14 hard fails are heading_monotone (not content loss) | **CONFIRMED** | Flag rollup: `9 hard gate:heading_monotone`, `3 hard unigram coverage <`, `2 hard gate:no_empty_table`. 9/14 = 64% from heading pedantry. |
| 7 | facts.py table/math gates have zero real instances | **CONFIRMED** | Zero `.facts.jsonl` in data dir. `check_facts` is never called on real papers. Lane 3 code (405 LOC, 5 assertion types) is fully implemented but exercises 0 production papers. |
| 8 | Markitdown oracle "agreement != correctness" is honestly documented | **CONFIRMED** | `reference.py:10-14`, `score.py:142-147`, `CLAUDE.md:247-250` all state this. `_decide` (score.py:175-178) makes ref_nid advisory-only, never hard-fail. |
| 9 | Review tier dominated by benign "misaligned regions" (186/382) | **CONFIRMED** | Flag rollup: `186 soft misaligned regions` is the #1 soft flag; `REGION_SOFT_COUNT=1` fires on any single region. CLAUDE.md declares these "expected on clean papers". |
| 10 | Persona 07's "self-referential" claim (tomd judges tomd) | **PARTIALLY CONFIRMED** | `score.py:28-29` imports `check_paper_content` and `compute_metrics` from tomd. This reuses tomd's own QA, so structural gates share blind spots with the converter. However, `unigram_coverage` compares against source PDF/HTML text (not tomd's own output), which is genuinely independent. The structural QA folding is partially self-referential; the content gate is not. |
| 11 | Persona 26's cost estimate (55-90h for full corpus) | **PLAUSIBLE, UNVERIFIED** | Cannot verify time estimates without running a labeling exercise. Architecture is sound: separate labels vs gt.md authorship is correct decomposition. |

## Can any accuracy claim be made today?

**No.** Not a single defensible accuracy claim can be made about whisker's verdict quality today. Specifically:

1. **No TPR/FPR/precision exists.** Without labeled ground truth (human adjudication of "should this paper pass/review/fail?"), the 163/205/14 split is prevalence, not performance. "42.7% pass" does not mean "42.7% are safe to ship."

2. **The only operational path is a smoke test.** The reference-free hard gate catches: (a) truncated conversions via unigram_coverage < 0.85 (fires on 3/382), and (b) structural malformations via heading_monotone (9/382, many false-positive on valid WG21 heading conventions) and no_empty_table (2/382). That is 14 total hard-fails, 9 of which are heading pedantry on papers with uni >= 0.997.

3. **Comprehension is 0% covered.** Lane 3 (table cell position, math exponents, ordering) is the designed answer to "can an LLM read this?" but runs on 0/382 papers. A table-column swap that preserves all tokens passes every operational gate.

4. **The oracle adds noise, not signal.** With mean ref_nid (0.836) below the advisory edge (0.85), the oracle flags ~38% of papers as "low agreement" when that IS the statistical norm. Only 28 papers actually change tier from oracle-only review. The flag is indistinguishable from genuine content loss.

**What CAN be said:** whisker reliably catches catastrophic failures (empty outputs, massive content drops below 15% token loss). For 97% of the corpus, it certifies "not catastrophically broken," which is a useful but weak guarantee.

## Corpus-build plan assessment

Persona 26's two-phase plan (Phase A: 50 labels / 12h; Phase B: 25 gt.md + facts / 55-90h) is **architecturally sound and the most realistic path I've seen**:

**Strengths:**
- Correct separation of labels (cheap, enables calibrate) from full GT (expensive, enables bench/guard/facts)
- Stratified sampling matrix covers the right failure modes (format, verdict tier, table/math)
- 20% holdout prevents overfit on small n
- Recognition that gt.md for table/math papers (2-4h each) is the cost bottleneck
- `calibrate` CLI contract is already implemented and ready

**Weaknesses / risks:**
- **Adjudication rubric is undefined.** The plan notes P3941R2 heading-only fails need special handling but does not specify a rubric. Without one, inter-rater reliability is unknown and labels may encode inconsistent standards.
- **50 labels may be marginal for two-class calibration.** With 40 fit / 10 holdout, and a base rate of ~3.7% hard-fail, the holdout may contain 0-1 true positives. Confidence intervals on TPR will be wide.
- **No timeline or ownership.** The plan describes WHAT but not WHO or WHEN. At 55-90h, this is ~2 FTE-weeks. Without a committed schedule it remains aspirational.
- **gt.md "corrected tomd output" shortcut** may encode systematic tomd biases into the ground truth (the very thing being measured). Prose-only papers may tolerate this; table/math papers must be authored from source.

**Realism score: 7/10.** The plan is executable by one experienced WG21 reader in 2-3 weeks. The critical path is the 8 table/math gt.md papers (16-32h). Phase A alone (labels + calibrate) is achievable in 2-3 days and would immediately make whisker's fail-edge defensible.

## My independent verdict

**usable-with-conditions**

**Conditions:**
1. Operators MUST understand "pass" means "not catastrophically broken," NOT "safe to ship" or "LLM-comprehensible"
2. The oracle (`--no-reference` omitted) adds review noise without proven signal; default should be `--no-reference` for triage until calibrated
3. No CI gate should treat whisker pass as a quality certificate until Phase A calibration is complete

**Confidence: high** — every numerical claim I checked matched live runtime exactly; the code is well-engineered and honestly self-documenting about its limitations; the gap is entirely in the missing labeled data, not in bugs or architectural flaws.

## Top-3 issues

1. **Zero comprehension coverage on 382 papers.** Lane 3 (table/math/order facts) is the only gate that catches token-preserving semantic corruption (swapped table cells, dropped exponents). It runs on 0 papers. This is the single largest reliability gap: whisker cannot detect the failure modes that most damage downstream LLM consumers.

2. **No calibration = no defensible operating points.** Every threshold is borrowed from other benchmarks (DP-Bench, OmniDocBench, edgeparse). The 0.85 unigram fail edge, the 0.95 review edge, and the 0.85 oracle advisory edge have unknown TPR/FPR on this corpus. The tool cannot state its false-pass or false-fail rate.

3. **Review tier is triage noise, not a quality signal.** 205/382 (54%) land in review, dominated by 186 "misaligned region(s)" flags the spec itself declares benign. Without labels proving these flags correlate with human-needed fixes, the review tier is functionally a catch-all that requires 54% manual inspection, providing weak triage value over "look at everything."
