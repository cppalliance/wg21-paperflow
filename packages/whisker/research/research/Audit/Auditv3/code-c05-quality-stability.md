# C05 Quality-Stability

**Role**: Assess whether the same input produces the same findings across runs, on BOTH the deterministic lane and the advisory LLM lane.
**Audited state**: whisker 0.5.0, working tree, manifest b9ad8ab0a464aaaf030bfb9a9576bdeed986f6510b83dbd87945bdd7fe68f771 (HEAD 0d18a65 + 7205 uncommitted insertions).
**Gates**: G3 (Scoring determinism), and (for the advisory half) the doctrine claim that instability is measured, bounded, and never gates.

## 1. Scope

Deterministic lane: does re-running whisker on unchanged input reproduce the same score, across processes and across time (the pinned baseline)? Advisory lane: does re-running the LLM adjudication on unchanged input reproduce the same suggested verdict, measured live, and does the documented instability claim (">= 25% verdict-flip rate") hold up against a live measurement?

## 2. Commands and Exits

| Evidence | Command / source | Exit |
|---|---|---|
| E1 | offline suite | **1** (3 failed, 1784 passed, 8 skipped, 3 xfailed) |
| E10 | separate-process replay, 3 papers x 2 runs | 0 (both), stdout byte-identical 3/3 |
| E13 | S7 `--retry-errors` re-evaluation | 0 |
| E17 | `rt4_canaries.py`, 4 mutations x re-score | n/a (metric-value + verdict comparison) |
| E20 | `rt7_repeat.py`, 3 forced re-runs x 3 papers | n/a (advisory verdict comparison, no exit-code contract) |

## 3. Current Evidence

### 3.1 Deterministic lane: same-process purity holds, cross-time reproducibility does not (E1, E10)

E10 proves same-input reproducibility WITHIN this run: 3 papers scored twice each in separate OS processes produced byte-identical stdout JSON, 3 of 3. This is strong evidence the scoring function itself (`score_markdown`/`_decide`, `score.py:136-331`) is a pure function of its inputs, consistent with the no-randomness/no-network/no-LLM code trace in C02 §3.1.

E1 proves the opposite claim, "the SAME input reproduces the SAME findings ACROSS TIME (i.e. against the committed baseline)," does not currently hold for all pinned material: `test_score_pinning.py` fails on 2 of 19 papers (`p3556r0` gate mismatch, `p2040r0` `max_heading_level` 3 vs 4 expected), and `test_dev_replay_schema.py::test_locked_candidate_dispositions` fails on the p4182r0 holdout candidate's SHA-256 fingerprint. These are not the same failure mode as a non-deterministic function: E10 shows the function does not vary run-to-run on the SAME markdown text. What has moved is the INPUT (a tomd golden fixture, or the parsing logic reading it, per C02 §3.6), which the pinning harness is specifically built to detect, and did detect. **Quality-stability's "same input, same findings" promise is scoped to a fixed artifact; the artifacts in these two failing cases are not currently fixed relative to their pinned commitments.**

### 3.2 Metrology canaries: same input, same deterministic score, across four distinct mutations (E17)

E17 re-scored the same base document (25157 chars, 9 H2 sections) under four independent token-preserving or content-removing mutations, once each:

| Canary | Mutation | det verdict | `unigram_coverage` |
|---|---|---|---|
| control | none | pass | 0.9542 |
| C1 | delete Section 3 (46.7%) | fail | 0.5021 |
| C2 | reverse section order | pass | 0.9542 |
| C3 | swap two table cells | pass | 0.9542 |
| C4 | corrupt 14 code spans | pass | 0.9542 |

This demonstrates the deterministic metrics respond correctly and consistently to the ONE mutation class they are designed to catch (content removal, C1: `unigram_coverage` drops from 0.9542 to 0.5021, a hard fail) and are stably, repeatably blind to the three token-preserving mutation classes (C2-C4 all report the identical `unigram_coverage` 0.9542 as the control). "Stably blind" is itself a form of quality-stability: the SAME blind spot reproduces identically across all three token-preserving canaries, which is consistent with the metric surface's C02 §3.7 finding (normalizer strips non-word characters symmetrically), not evidence of run-to-run noise.

### 3.3 Advisory lane: live-measured instability corroborates the documented claim (E20)

`CLAUDE.md` claims ">= 25% verdict-flip rate" for identical LLM reruns (same paper, same model, same prompt). E20 (`rt7_repeat.py`) forced 3 re-runs (`--force`) of the same 3 papers, same model, same prompts:

| Paper | run 1 | run 2 | run 3 | stable |
|---|---|---|---|---|
| control | review | review | **pass** | **no** |
| C2 permute | review | review | **pass** (`whisker_only`) | **no** |
| C4 mathflip | review | review | review | yes |

Including the original canary run (a 4th observation per paper), the control produced `pass` in 1 of 4 observations (25%) and C2 produced `pass` in 2 of 4 (50%). Both figures meet or exceed the documented ">= 25%" floor. The flip is traced to the metadata/outline check specifically (§3.4 below), not to the primary judge's headline verdict alone.

### 3.4 The flip mechanism is a specific, identifiable component, not generic LLM noise

Per the ledger's own trace and cross-checked against `fusion.py` (already read in full for C02/C03): the metadata/outline check returned `verdict: pass` in run 3 for the control and `verdict: review` in runs 1-2 for the IDENTICAL input. `_source_aware_requires_review` (`fusion.py:182-227`) gates its review-cap on `metadata.get("verdict") != VERDICT_PASS` (`fusion.py:188`); when that one component's verdict flips (same input, same model, same prompt, different run), the review cap stops firing and the fusion default branch (`fusion.py:538`, traced in C03 §3.7) can then let a `det=pass` paper's combined verdict settle at `pass` even when the primary judge maintained `review`. This localizes the instability to one specific structured-output field (the metadata check's binary verdict), not to "the LLM is generally noisy" as an undifferentiated claim; it is a precise, reproducible failure mode of one component under resampling.

### 3.5 What quality-stability can and cannot claim given E1 and E20 together

Two lanes, two different stability profiles, and both matter to the SAME gate:

- Deterministic lane: pure and reproducible AS A FUNCTION (E10), but the artifact it scores against (a pinned baseline) has drifted on 2/19 papers (E1). This is an input-management problem, not a function-purity problem.
- Advisory lane: unstable BY DESIGN and BY MEASUREMENT (E20), at a magnitude (25-50%) that meets the doctrine's own stated floor. The architectural response (never let the LLM gate, C03) is the correct doctrine given this measurement, and this run's live evidence is the first CORROBORATION of the ">= 25%" figure with fresh numbers rather than a repetition of the documented claim.

A claim of "whisker has quality-stability" without qualifying WHICH lane and WHAT is held fixed would be misleading in both directions: too strong for the deterministic lane (E1 shows a real, current mismatch against committed history) and too strong for the advisory lane in the opposite way if read as "the LLM lane is also stable" (E20 shows it plainly is not, and was never claimed to be).

## 4. Findings

| # | Finding | Severity | Confidence |
|---|---|---|---|
| F1 | Deterministic scoring is reproducible byte-for-byte across separate processes on fixed input (E10, 3/3) | Informational | HIGH |
| F2 | Deterministic scoring does NOT currently reproduce its own committed baseline for 2 of 19 pinned papers, plus one locked-candidate hash mismatch (E1) | **High** | HIGH |
| F3 | The deterministic metric surface is stably blind (not noisily inconsistent) to three of four canary mutation classes (E17): the blind spot itself reproduces identically across repeated scoring | Medium | HIGH |
| F4 | Advisory-lane verdict instability is live-measured at 25% (control) and 50% (C2) flip rate across 4 observations each, meeting or exceeding the documented ">= 25%" claim (E20) | Informational (confirms doctrine) | HIGH |
| F5 | The advisory flip is traceable to one specific structured-output field (the metadata/outline check's verdict), not to the model's headline suggested_verdict alone (E20 cross-referenced against `fusion.py:182-227`) | Medium | HIGH |

## 5. False-Pass Hypothesis

**Could quality-stability look satisfied while actually failing on one lane or the other?**

The specific false-pass risk is citing E10 (deterministic replay, 3/3 identical) as proof of "whisker has quality-stability" without also surfacing E1 (the pinning suite is red). E10 and E1 test different things: E10 fixes the input and asks "does the function vary," E1 fixes the function-as-committed and asks "does the currently-checked-out input still score what it used to." Both are legitimate readings of "quality-stability," and a report that used only the favorable one (E10) while suppressing the unfavorable one (E1) would be a textbook false pass. This file deliberately reports both, in the same section (§3.1), specifically to prevent that selective citation. On the advisory side, the equivalent risk would be treating a single favorable observation (e.g. C4's 3/3 stable `review` in E20) as representative, when the SAME evidence set shows the control and C2 flipping 25-50% of the time; §3.3 reports the full 3-paper table, not just the stable outlier.

## 6. Gate/Dimension Mapping

**PROPOSED, not a settled verdict.** G3 (Scoring determinism), deterministic half: the underlying function is proven pure and reproducible live (E10, F1), but the claim that the deterministic lane currently reproduces its committed regression baseline is FALSE for 2 of 19 pinned papers and 1 locked-candidate hash (E1, F2). PROPOSED: this half should be scored **CONDITIONAL**, matching C02's proposed mapping, not a clean pass, and the planner should treat F2 as the single most important fact in this file. Advisory half (not a formal gate in the G1-G6 set, but load-bearing for the doctrine claim in C01 #6): the ">= 25%" instability claim is corroborated, not contradicted, by live measurement (E20, F4); PROPOSED status for this half is **verified as documented**, i.e. the architecture's premise (the LLM is measurably unstable, so it must never gate) is empirically sound on this run's fresh data.

## 7. Limitations

- The root cause of the 2 score-pinning mismatches and 1 locked-candidate hash mismatch was not isolated in this file (see C02 §7); this file treats the FACT of the mismatch as settled by E1 but does not adjudicate whether it reflects an intended tomd-side change awaiting baseline reconciliation or an unannounced regression.
- E20's sample size is small (3 papers, 4 observations each); the 25%/50% figures are point estimates from a live but limited resampling, not a large-N statistical measurement. They corroborate the documented claim's DIRECTION and ORDER OF MAGNITUDE, not a precise rate.
- The metadata/outline check's own internal decision process (why it flips) was not independently probed at the prompt/token level in this run; §3.4's localization is based on cross-referencing the ledger's narrative against the `fusion.py` gating logic, not on inspecting the model's raw reasoning trace for the flipped call.

## 8. Conclusion

Quality-stability must be reported per-lane, and this file does so deliberately. The deterministic lane's scoring FUNCTION is proven reproducible byte-for-byte across processes (E10), and its metric surface reproduces the same blind spots consistently across repeated canary mutations (E17), but the lane's regression-detection HARNESS currently disagrees with live code on 2 of 19 pinned papers and 1 locked candidate hash (E1); this is the single fact this audit batch must not let slide past a planner unremarked. The advisory lane is, as documented, measurably unstable: this run's live resampling (E20) reproduces a 25-50% verdict-flip rate, matching or exceeding the doctrine's own stated floor, and localizes to one specific structured-output component rather than generic noise.

## 9. Delta vs Auditv2

Auditv2's C05 (`Auditv2/code-c05-quality-stability.md`) covered ONLY the deterministic lane (score pinning, metric/match/fusion determinism unit tests, guard regression detection, golden stability, comprehension corpus replay), scored a clean **1406 passed, 8 skipped, 3 xfailed, zero failures** baseline, and concluded "the deterministic core is well-covered" with two documented, non-defect gaps (no separate-process replay, no score pinning of `ref_nid`/`ref_teds`/`ref_mhs`). It explicitly could NOT address the advisory lane at all, because its runtime evidence was blocked by credential denial (Auditv2 §1, §14). This run inverts both halves of that picture: (a) the deterministic lane's OWN test suite is now red (E1), closing Auditv2's "no separate-process replay" gap in the favorable direction (E10 proves it live, 3/3 identical) while opening a new, more serious gap Auditv2 could not have seen (the baseline itself has drifted); (b) the advisory lane, entirely absent from Auditv2's C05, is now populated with live, first-time evidence (E20) that directly corroborates the project's own ">= 25%" doctrine claim with fresh numbers. Auditv2's two documented non-defect gaps (separate-process replay, `ref_*` pinning) are not re-litigated here except to note the first is now closed by E10.
