# whisker QA Reliability Verdict: 30-Persona Swarm + 5-Opus Meta-Eval

Third-pass audit (June 2026). 30 `composer-2.5-fast` persona subagents each took one
critical lens against the whisker QA package, grounded in a shared evidence baseline
(`research/persona/00-EVIDENCE-BASELINE.md`): the green test suite, the 382-paper
reference-free run, and the empty in-repo corpus. Then 5 Opus subagents
(`research/persona/opus-A..E-*.md`, 3x opus-4.8-high + 2x opus-4.6-medium) independently
**re-ran every material claim through the production code path** (not trusting the
personas) and rated severity. This note ranks the CONSENSUS findings (how many of the 30
independently raised each), reconciles them with the 5 Opus cross-checks, and answers the
one question: **is whisker usable QA, or garbage?**

Raw reports: `research/persona/NN-<slug>.md` (01-30), `research/persona/opus-<A-E>-*.md`.

---

## Executive verdict: USABLE-WITH-CONDITIONS. Confidence: HIGH.

Not garbage. Not yet a ship/no-ship oracle. **30 of 30 personas and 5 of 5 Opus
reviewers reached the same verdict, unanimously, including the adversary (03), the
false-negative hunter (23), and the steelman (30).** Nobody said "garbage." Nobody said
"usable" unqualified.

whisker is a **sound, deterministic, well-engineered instrument that measures exactly one
thing well, is mislabeled by what `pass` implies, and is uncalibrated.** Used as a
**coarse triage floor** ("block grossly broken artifacts, route the rest to a human") it
is trustworthy today. Used as an **autonomous "this conversion is faithful" gate** (how
`pass` will be read downstream) it is not, because reading-order, table-cell, and
code-block semantics are categorically ungated and the layer designed to catch them
(Lane 3) runs on zero papers.

The instrument is honest about its own limits in `constants.py` and `CLAUDE.md`. The risk
is not deception; it is the **gap between what `pass` certifies (word presence +
well-formedness) and what a downstream consumer will assume `pass` means (fidelity).**

---

## Where we stand: per lane + hard gate + the 382-paper run

| Component | Status | Evidence |
|---|---|---|
| **Hard gate (`whisker --no-reference`)** | OPERATIONAL, sound-for-contract | runs on all 382; deterministic; 2 hard-fail conditions only |
| **Lane 1 Stability (`golden`)** | NON-OPERATIONAL in-repo | `corpus/` holds only README + EXAMPLE.facts.jsonl; no `*.gt.md` |
| **Lane 2 Fidelity (`bench`)** | NON-OPERATIONAL in-repo | no `*.expected.md`; metric code unit-tested but unfed |
| **Lane 3 Comprehension (`facts`)** | NON-OPERATIONAL, **0/382** | no `*.facts.jsonl`; the documented defense for order/table/math errors never runs |
| **Calibration (`calibrate`)** | NEVER RUN | 0.85/0.95 edges self-declared "PROVISIONAL" (`constants.py:11`); no measured TPR/FPR |
| **markitdown oracle (default-on)** | OPERATIONAL, advisory, noisy | 147/382 flags, only 28 change tier; review-only, never hard-fails |

**382-paper reference-free run (fresh schema-3):** 163 pass (42.7%), 205 review (53.7%),
14 fail (3.7%). The gate **blocks 3.7% and routes 54% to humans.** The pass tier is
structurally capped near 42.7% because every pass requires `missing+extra == 0` regions,
so a single benign furniture region forces review.

---

## Reliability evidence

- **Test suite:** 353 passed in 1.62s. But this validates metric *math* and guard *diff
  logic*, not verdict *accuracy* against labeled outcomes. Green CI is a code-quality
  signal, not a QA-trustworthiness signal (personas 16, 22; Opus C).
- **Determinism:** byte-identical re-runs verified on real papers (no LLM / network /
  randomness); 4dp rounding at serialization bounds float flicker (persona 04; Opus C).
  The model-sovereignty / determinism invariant holds.
- **Verdict distribution:** see above. Hard fails decompose as **3 genuine content-loss**
  (unigram < 0.85), **9 heading-typography**, **2 empty-table** (baseline §3a).
- **Calibration:** none. Every operating point is borrowed from
  edgeparse/OmniDocBench/DP-Bench and never fitted to WG21 outcomes.
- **Prior hardening:** all 7 Tier-1 redteam bugs verified still fixed in current code
  (persona 28; Opus C).

---

## Consensus findings, ranked (Tier 1/2/3), reconciled with the 5 Opus cross-checks

### Tier 1: near-unanimous, material, gate trust depends on these

| # | Finding | Personas | Opus cross-check |
|---|---|---|---|
| 1 | **`pass` is a word-multiset-presence + well-formedness certificate, NOT a fidelity certificate.** Reading order, table row/cell assignment, and fenced-code identifiers are categorically ungated (`unigram_coverage` is order-invariant `check_content.py:621`; shingle `coverage` "never a verdict flag" `score.py:136-137`). | 01,03,08,18,19,20,21,23 (8) | **Opus B reproduced at scale: 96% (24/25) of passing table-papers survive an adversarial section-reverse + row-swap as `pass`.** `P1040R10` cov 0.991->0.976 stays pass. `P4178R0` already passes *uncrafted* at cov=0.837. **CRITICAL, confirmed.** |
| 2 | **No calibration. Thresholds are borrowed priors with zero measured TPR/FPR on WG21.** Knife-edge at 0.95 (`P4136R0` passes at 0.9505). | 01,02,07,10,16,26,29,30 (8) | **Opus A confirmed**; the 0.85/0.95 edges control one sub-rule, not `verdict==review`. **HIGH, confirmed.** |
| 3 | **Lane 3 (the designed defense for #1) runs on 0/382 papers; the entire 3-lane corpus is empty in-repo.** So nothing operational catches order/table/math corruption. | 07,08,19,20,25,26 (6) | **Opus D confirmed**: corpus-build plan is architecturally sound but operationally absent; current metrics cannot support any accuracy claim. **HIGH, confirmed.** |

### Tier 2: strong consensus, the false-POSITIVE / cry-wolf axis

| # | Finding | Personas | Opus cross-check |
|---|---|---|---|
| 4 | **`heading_monotone` HARD-fails clean, PDF/convention-faithful papers: 9/14 hard fails (64%)** are WG21 wording numbering / meeting-minute conventions with uni 0.947-0.999. The gate rejects cosmetics while accepting semantic reordering: backwards asymmetry. | 18,24 + 01 (3) | **Opus B confirmed full roster** (`P3941R2/R3/R4`, `N5035/37/43`, `P3161R5/P3647R1`, `P4160R0`). **HIGH, confirmed.** Recommend demote to review or normalize WG21 heading depth. |
| 5 | **Review tier (54%) is a benign-noise majority** dominated by "misaligned region(s)" firing at `REGION_SOFT_COUNT=1`, which the spec itself calls "expected on clean papers." ~18% of corpus reviews on a single furniture region. | 22,24,29 (3) | **Opus B confirmed**: every pass has `missing+extra==0`; one benign region forces review. **MED-HIGH, confirmed.** Raise `REGION_SOFT_COUNT` above 1. |
| 6 | **markitdown oracle adds noise, not signal, default-on:** 147/382 flags, 81% redundant (fire on already-review papers), only 28/382 incremental tier changes; ~18 min full-corpus cost. Not a correctness oracle (shared-failure blind spot on scanned PDFs). | 13,14,22 (3) | Opus E/C consistent: advisory is correctly *coded* (never hard-fails) but over-surfaced and operating point unvalidated. **MED.** Treat `--no-reference` as triage default. |

### Tier 3: engineering nits, real but localized

| # | Finding | Personas | Opus cross-check |
|---|---|---|---|
| 7 | **`--all` scorer exceptions never flip the exit code** -> a broken conversion behind a scorer crash looks green in CI; stale pass sidecars persist. | 09,15 (2) | **Opus C confirmed real bug.** Count errored papers into the exit contract. |
| 8 | **Test suite validates math, not verdict accuracy**; no integration test on real `check_paper_content`; missing CLI exit-code tests. | 16,22 (2) | **Opus C confirmed.** |
| 9 | **Docs overclaim:** `score.py:74-76`/`198-200` call the oracle the "primary verdict signal"/"drives the verdict" while `_decide` uses it as one *soft, never-fail* flag; CLAUDE.md/CHANGELOG oversell verbatim parity + 3-lane completeness. | 13,17 (2) | **Opus E confirmed.** Fix docstrings; they will mislead integrators into wiring oracle into pass/fail. |
| 10 | **License:** GPL `levenshtein` is gone (good), all deps permissive; still needs a consolidated third-party NOTICE for Apache-2.0 verbatim ports + a manifest-level GPL guard. | 12 (1) | **Opus C confirmed** as a distribution-blocker nit. |
| 11 | **Performance / robustness:** oracle path ~18 min; TEDS block-match matrix fallback is a silent metric cliff on 13+ large papers; NaN-path false-pass edge. | 11,14 (2) | **Opus B/C confirmed** NaN false-pass + fallback cliff. |
| 12 | **Positive: all 7 prior Tier-1 redteam fixes hold** and are unit-tested. | 28 (1) | **Opus C confirmed.** Regression guard is trustworthy on a frozen GT corpus. |

### Disputes / where Opus corrected the personas

- **Opus B vs persona 23:** persona claimed `merge_paragraphs` mutation -> `pass`; Opus B
  reproduced it as -> `review` (6 regions). whisker is marginally *better* than stated.
  Does not change any Tier-1 verdict.
- **Opus A vs a calibration persona:** refuted one claim about the Youden-J fallback
  behavior; the ROC fitter is mechanically correct and red-team-hardened.
- **No Opus reviewer found a Tier-1 finding the personas missed in the other direction**,
  and **no persona's CRITICAL was downgraded below HIGH by Opus.** The swarm did not
  inflate severity.

---

## Gap list: what must happen for whisker to be trustworthy QA (not just triage)

Ordered by leverage. These are the exact conditions that flip "usable-with-conditions" to
"usable."

1. **Calibrate.** Label >=30-50 WG21 papers with human pass/fail, run `whisker calibrate
   --labels`, replace the PROVISIONAL 0.85/0.95 edges with measured operating points,
   and **publish the resulting TPR/FPR.** Until this exists, every threshold is a guess.
2. **Close the fidelity gap (Tier 1 #1).** Add at least one *operational* order/table
   signal to the score path: either a calibrated soft flag when `unigram_coverage -
   coverage` exceeds a fitted gap, or populate Lane 3 `table`/`order`/`math` facts on
   table-heavy and math-heavy papers so the documented defense actually runs.
3. **Rename / re-document `pass`** as "content-present + well-formed", never "faithful",
   everywhere a downstream consumer (dissect/agora, CI) reads it.
4. **Fix the false-positive asymmetry (Tier 2 #4, #5):** demote `heading_monotone` to
   review (or make it WG21-heading-depth-aware), and raise `REGION_SOFT_COUNT` above 1 so
   a single benign furniture region stops forcing review.
5. **Make CI honest (Tier 3 #7):** fold errored-paper count into the exit-code contract so
   a scorer crash cannot present as a green batch.
6. **Populate the in-repo corpus** (Lanes 1/2/3) so the 3-lane architecture stops being
   unit-tested-but-unfed; add an integration test asserting verdict behavior on real
   `check_paper_content` output.
7. **Demote or gate the oracle:** make `--no-reference` the documented triage default, or
   corpus-fit `REF_NID_ADVISORY_EDGE`, or move the overlay to report-only.

---

## Bottom line

**whisker is usable QA today as a conservative triage floor: it deterministically blocks
the 3.7% of conversions with gross word loss or structural malformation and honestly
routes 54% to human review. It is not garbage.** Its engineering is sound, its
determinism holds, its prior bugs stay fixed, and it never silently false-passes the one
thing it gates (word presence).

**But a `pass` is a word-presence receipt, not a fidelity guarantee, and the corpus that
would let us prove any accuracy number is empty.** Until calibration runs and the
order/table/code gap is closed (operationally, not just in unit tests), `pass` must be
read as "safe to look at," never "safe to ship blindly," and whisker must not be the sole
ship/no-ship authority for the analytical pipelines.
