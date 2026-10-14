# Meta-Review A — Measurement Validity

**Reviewer:** Opus Meta-Reviewer A (measurement-validity lane)
**Date:** 2026-07-18
**Inputs reviewed:** `00-FRAME.md`, `00-ROSTER.md`, and all persona reports `p01`–`p30`.
**Scope:** Measurement validity only — extraction metrics, benchmark design, ground truth, LLM-judge validity, threshold calibration, maturity levels, weighted scoring, evidence grades, score uncertainty, anti-gaming. I did **not** open whisker production code, cite whisker `file:line`, or score whisker. This document evaluates the **audit's own measurement apparatus**, not the tool under audit.
**Method:** For load-bearing claims I re-fetched the primary sources with live web access and compared the persona's wording/numbers against the source. Verdicts below carry a source URL and a pass/fail.

---

## 0. Headline

The measurement-validity core of this audit (p09 metrics, p10 judge science, p11 ground truth, p12 benchmarking, p16 calibration, p17 uncertainty, p19 anti-gaming, plus the eval-science case studies p28/p30) is **evidentially sound**. Every load-bearing citation I re-checked resolved to a real primary source with the stated numbers intact. **No citation hallucinations were found** in the sample, including the high-risk 2026-dated arXiv papers.

The defects are not fabrication. They are three structural measurement errors the synthesis must fix before these criteria become a score:

1. **Gate inflation.** The roster proposes ~30+ "hard-gate candidates." A non-compensatory layer that large fails almost everything and destroys the discriminating power a gate exists to provide. p30-E4 itself caps gates at ≤7 with written rationale; the roster violates its own rule.
2. **Weight double-counting.** Personas propose overlapping "% of composite" for co-owned dimensions. Naively summing them exceeds 100%. Weights must be assigned once, at the cluster level, by the synthesis (P15 owns this), never summed across personas.
3. **False precision on uncalibrated numbers.** Several numeric floors (judge κ ≥ 0.50, flip ≤ 0.15, corruption acc ≥ 0.70) and one head-to-head leaderboard triple are presented as if fixed when they are placeholders or version-specific.

There is also one genuine **construct contradiction** the roster half-buries: on tables, the most recent primary evidence says an LLM judge is *more* construct-valid than TEDS/GriTS, which sits awkwardly beside the roster-wide "LLM judge is advisory-only, deterministic metrics gate" doctrine. Reconciled in §4.

---

## 1. Verification ledger (primary-source re-checks)

| # | Claim (persona) | Primary source re-fetched | Verdict |
|---|---|---|---|
| V1 | TEDS = 1 − EditDist/max(\|Ta\|,\|Tb\|); td-td substitution = normalized Levenshtein; Zhong et al. ECCV 2020 / PubTabNet (p09-2.2/2.3) | arXiv:1911.10683v5; ecva.net ECCV 2020 PDF; ibm-aur-nlp/PubTabNet | **PASS** — formula and substitution rule verbatim |
| V2 | GriTS decomposes into GriTS_Top (topology, IoU), GriTS_Con (content, normalized LCS), GriTS_Loc (location, IoU); 2D-MSS from NP-hard 2D-LCS; Smock/Pesala/Abraham, arXiv:2203.12555, ICDAR 2023 (p09-2.4) | arXiv:2203.12555v3; MS Research page; kensho-technologies/grits | **PASS** — three variants, similarity functions, and 2D-MSS derivation all confirmed |
| V3 | olmOCR-Bench = 7,010 tests across 1,402 PDFs; rejects edit distance/ROUGE/LLM-as-judge; cites Panickssery 2024 self-preference; "x^i vs x_i is one char in edit distance" (p28-A2) | olmocr.allenai.org paper PDF; arXiv:2502.18443v3; HF allenai/olmOCR-bench | **PASS** — "1,402 distinct PDF documents … 7,010 unique test cases"; rejection rationale and math example verbatim |
| V4 | JudgeBench: strong models e.g. GPT-4o only slightly above random on objective-correctness pairs; Tan et al. ICLR 2025, arXiv:2410.12784 (p10-J3) | ICLR 2025 proceedings PDF; arXiv:2410.12784 | **PASS** — "GPT-4o … just slightly better than random guessing"; 50%→56% with Arena-Hard confirmed |
| V5 | Coin Flip Judge: mean 13.6% pairwise flip rate; 28% of questions >20%; one at 56%; 11 trials for 95% majority recovery (15 for high-variance) (p10-J4) | arXiv:2606.13685 | **PASS** — every number verbatim. **Caveat:** both judges are OpenAI (single provider); authors flag cross-provider replication as open |
| V6 | Horn & Keuper table judge: LLM r=0.93 vs TEDS r=0.68, GriTS r=0.70; 1,500+ human ratings; 21 parsers; arXiv:2603.18652 (p10-S10, p09) | arXiv:2603.18652v2; phorn1/pdf-parse-bench | **PASS** — r=0.93 vs 0.68/0.70 verbatim; rule-based band r=0.56–0.70 confirmed |
| V7 | Pan et al.: self-recognition >50% out of box (GPT-4 73.5%); *linear, causal* correlation between self-recognition and self-preference; NeurIPS 2024, arXiv:2404.13076 (p10-J6) | NeurIPS 2024 proceedings PDF; OpenReview 4NJBV6Wp0h | **PASS** — 73.5%, linear trend, confounder controls all confirmed |
| V8 | DeepEval default threshold 0.5; strict_mode overrides to 1.0; is_successful iff score ≥ threshold; assert_test gates CI (p30-E3) | deepeval.com metrics-introduction / metrics-llm-evals / ci-cd docs | **PASS** — "defaulted to 0.5 for all metrics" verbatim |
| V9 | promptfoo exit code 100 on failure/below PROMPTFOO_PASS_RATE_THRESHOLD (default 100%); threshold:0 makes a test always pass; weighted assertions default 1.0 (p30-E4/E6) | promptfoo.dev command-line + expected-outputs docs | **PASS** — exit 100, default 100%, threshold:0 footgun all confirmed |
| V10 | OmniDocBench Overall = ((1 − TextEdit)×100 + TableTEDS + FormulaCDM)/3; reading order excluded from composite (p09-2.10) | github.com/opendatalab/OmniDocBench README | **PASS** — formula verbatim; reading order is a *separate* column, not in Overall (supports p09's collapse argument) |

**Sample verdict:** 10/10 load-bearing claims verified. The measurement-validity personas are unusually disciplined about sourcing. Confidence in the underlying evidence base is **HIGH**.

---

## 2. Verified findings (adopt as-is)

These are the load-bearing, primary-source-confirmed conclusions the score architecture should be built on.

- **VF1 — Per-axis reporting is the master rule; composites are navigation only.** TEDS, TEDS-S, GriTS_Top/Con/Loc, NID/NED, reading-order edit, formula CDM, and layout mAP are construct-distinct. The OmniDocBench Overall formula literally omits reading order (V10), which is the point: any single "extraction quality" number silently drops an axis. Converging evidence: p09-2.10, p27-D27-02, p28-C3, p29-B1, p30-E1. **Grade A.**

- **VF2 — Table fidelity requires a structure metric AND a content metric.** A structure-only pass (TEDS-S / GriTS_Top) with a full-TEDS/GriTS_Con fail is the exact signature of cosmetic HTML compliance masking OCR/content corruption (V1). Gate on the pair, never on structure alone. p09-2.3, p27-D27-03, p28-A2. **Grade A.**

- **VF3 — Modality-specific metrics must be null-eligible.** Scoring a table metric on a page with no tables (imputing 1.0 or 0.0) is a category error encoded as an exclusion in both DP-Bench and OmniDocBench. Report `eligible_count`/`null_count`; compute composites only over eligible units. p09-2.1, p12. **Grade A.**

- **VF4 — Edit distance is construct-invalid for the errors that matter most.** "x^i vs x_i" is one character in edit distance but a semantic inversion (V3). This is the strongest argument for binary, machine-verifiable unit tests on math/table/order properties as the primary construct, with edit distance demoted to a diagnostic. p28-A2, p13, p29-B2. **Grade A.**

- **VF5 — Single-trial LLM judging is too noisy for any consequential use.** 13.6% mean flip rate, some items at 56%, 11+ trials to stabilize a majority (V5). Any judge signal must document N, temperature, and aggregation, and report a flip-rate distribution alongside position bias (stability ≠ validity). p10-J4. **Grade A.**

- **VF6 — Preference success ≠ correctness.** Judges that look excellent on chat-preference benchmarks sit near random on objective-correctness pairs (V4). Judge validation must include an objective-corruption stratum (cell swap, sign flip, dropped negation) with deterministic oracle labels. p10-J3. **Grade A.**

- **VF7 — Same-family judge self-preference is causal, not incidental.** Self-recognition linearly drives self-preference and survives confounder controls (V7). Judge–generator independence must be disclosed and, where the family is shared, self-preference must be measured and bounded. p10-J6, p11-P11-07. **Grade A.**

- **VF8 — Chance-corrected agreement, correctly specified, is the core validity statistic.** κ for two nominal raters; Krippendorff's α for variable raters / ordinal / missing data; raw agreement reported alongside. Percent-agreement-only on imbalanced labels inflates apparent quality. p11-P11-02, p10-J2. **Grade A** (Krippendorff, Di Eugenio & Glass are established; not separately re-fetched but low-risk).

- **VF9 — Thresholds must be explicit and calibrated, or flagged uncalibrated.** DeepEval's silent 0.5 (V8) and promptfoo's `threshold:0`/`pass:true` (V9) are documented footguns where "has an eval" hides "gate never fires." Every gate boundary needs a numeric value plus calibration provenance or an explicit "borrowed — uncalibrated" flag. p16, p30-E3. **Grade A.**

- **VF10 — Conjunctive hard gates independent of the weighted composite are standard practice** in mature eval systems (GE `severity:critical`, Giskard grade gate, promptfoo pass-rate, V9). A high composite must never buy back a failed non-negotiable. p14, p15, p19, p30-E4. **Grade A.**

- **VF11 — Zero-authoring baseline sanity checks on 100% of pages** (non-empty alphanumeric, trailing-n-gram repetition >30 chars, charset sanity) catch catastrophic failure before any labeled eval and cost nothing. Necessary, not sufficient. p28-B1/B2. **Grade A/B** (olmOCR primary + framework practice).

---

## 3. Rejected / downgraded claims (with reasons)

- **RJ1 — DOWNGRADE the olmOCR head-to-head triple to "directional only."** p28 cites "olmOCR v0.1.75 anchored **75.5 ± 1.0** > Marker v1.7.5 **70.1 ± 1.1** > MinerU v1.3.10 **61.5 ± 1.1**" from "Table 4." The live HF/paper tables show different anchored values (e.g., 77.4 ± 1.0, 76.3 ± 1.1) depending on model/version row. The *ranking direction* and the *"per-axis diverges, composite hides it"* lesson hold; the specific point estimates are version-drift and should not be quoted as fixed. **False-precision risk, not hallucination.**

- **RJ2 — DOWNGRADE olmOCR unit tests from "construct-superior" to "construct-valid but coverage-limited."** p28-A2 frames binary unit tests as strictly better than fuzzy metrics. The primary olmOCR source and the LlamaIndex review agree the table tests check only *narrow adjacency relations* and the reading-order tests only *local pairwise ordering* — deliberately skipping spanning, grouping, completeness, captions, footnotes, multi-column. A model can pass the unit tests while producing globally broken output. Keep VF4 (edit distance is invalid for semantics), but the replacement is **unit tests + structure metrics + human-validated judge**, not unit tests alone.

- **RJ3 — REJECT the judge numeric floors as calibrated.** p10-§4 lists "domain κ ≥ 0.50," "position flip ≤ 0.15," "objective-corruption accuracy ≥ 0.70," "self-preference ≤ human + 5 pp." p10 itself says these are "to be calibrated on whisker labels later — method only here." Presenting them in a floors table invites their use as if fixed. **Keep the *dimensions* to calibrate; strike the numbers** until labeled data exists. Any of these used as a live hard gate today is an **unsupported gate** (no data to evaluate against).

- **RJ4 — REJECT most judge-validation criteria as *hard gates at this stage*.** p10 marks J1, J2, J3, J5, J6, J8 as hard-gate candidates (six). At methodology Stage 0 with no validated judge and no labeled corpus, a hard gate that cannot be evaluated is vacuous. Retain **J8 (advisory-only wiring)** as a hard gate — it is a testable architectural contract, not a data-dependent threshold. Convert J1/J2/J3/J5/J6 to **soft caps** (dimension capped at level 2 until the validation battery runs), matching p30-E3/E7's soft-cap logic.

- **RJ5 — REJECT summing persona dimension weights.** p24 (8%), p25 (8–12%), p30 (18%), p11 (8–12%), p26 (8–12%), p27 (cluster-local %), p28/p29 (deferred) are each "% of composite" for **overlapping** clusters. Added up, the measurement-validity and adjacent dimensions alone exceed 100%. These are proposals *within* co-owned clusters; the synthesis (P15) assigns weight **once per deduplicated dimension**. **This is a structural double-counting trap, not a per-persona error.**

- **RJ6 — DOWNGRADE the roster-wide hard-gate count.** Counting hard-gate candidates across p09 (4), p10 (6), p11 (4), p12, p13, p16 (3), p19, p24 (2), p25 (4), p28 (2), p30 (3) yields well over 30. p30-E4's own rule is ≤7 with written rationale each. A 30-gate non-compensatory layer means virtually every real system fails on something, collapsing the score's discriminating power. **Triage to a small conjunctive set (see §5).**

- **RJ7 — FLAG naming/parity risk (not a rejection).** "TEDS-S" (DP-Bench) = "TEDS_structure_only" (OmniDocBench) = "Table TEDS-S" (leaderboard). Same construct, different implementations; NID (insert/delete only) and NED/Levenshtein (substitutions allowed) are **not** directly comparable. p09-2.3/2.5 surface this correctly; the synthesis must forbid merging scores across benchmarks without implementation parity. **Keep, with emphasis.**

---

## 4. Reconciled contradictions

- **RC1 — "LLM judge is advisory-only" vs "LLM judge beats TEDS/GriTS on tables."**
  Horn & Keuper (V6) show the LLM judge is the *more construct-valid* table metric (r=0.93 vs 0.68/0.70). The roster-wide advisory-only doctrine (p05, p10-J8, p19, p28-A2, p30-E11) reads as if the judge were construct-*inferior*. **Reconciliation:** the advisory-only rule is a **determinism/model-sovereignty/robustness** decision (a stochastic same-family judge must not silently gate), **not** a construct-validity claim. The two are compatible once separated: use the judge as a high-validity *advisory* signal and, per VF5–VF7, only let it inform gates after multi-trial aggregation, independence disclosure, and objective-corruption validation. Do **not** justify advisory-only by asserting the judge is a bad measure of table quality — the evidence says the opposite.

- **RC2 — Binary unit tests vs reference-matching (olmOCR vs OmniDocBench/MinerU).**
  olmOCR rejects edit distance; OmniDocBench/MinerU report NED+TEDS+CDM composites. **Reconciliation (p28-C3, p9-2.10 already gesture at this):** binary unit tests for the construct-invalid cases (math sign, cell adjacency, order) are the **primary gate signal**; reference-matching metrics are **per-axis diagnostics** reported separately, never a lone composite. Neither replaces the other.

- **RC3 — κ vs α.** NLP habitually uses Cohen's κ; Krippendorff/Di Eugenio & Glass show κ's prevalence/marginal sensitivity. **Reconciliation:** prefer α for variable-rater/ordinal/missing-data extraction QA; if κ is retained, document why and report a disagreement decomposition. (p11-P11-02.)

- **RC4 — Graceful degradation vs fail-not-partial.** SRE (p25) permits degraded output under load; OWASP/QA-fidelity doctrine requires fail-closed. **Reconciliation:** classify subpaths. Deterministic gate outputs are fidelity-first (fail-not-partial); optional advisory lanes may degrade, but a degraded advisory result may never populate a gate verdict. (p25-O3/O4.)

- **RC5 — Reliability vs validity.** High test–retest stability (α > 0.95) can coexist with severe position bias (Coin Flip, V5); high IAA can coexist with consistently wrong labels (p11-P11-09). **Reconciliation:** stability and validity are orthogonal and both must be reported — IAA plus a gold-set accuracy anchor for labels; flip-rate plus position-bias for judges.

---

## 5. Deduplicated criterion set (measurement validity)

The roster's measurement-validity criteria collapse to **12 non-overlapping criteria**. Each lists its source personas and whether it is a gate.

| ID | Criterion (deduplicated) | Merged from | Gate? | Evidence |
|---|---|---|---|---|
| M1 | **Per-axis reporting; no lone composite.** Every load-bearing axis scored and displayed separately; composite is derived and shown beside axes. | p09-2.10, p12, p13, p27-D27-02, p28-C3, p29-B1, p30-E1 | **Reporting gate** | A (V10) |
| M2 | **Null-eligibility.** Absent modality → `null`, never imputed; composites over eligible units only, denominator disclosed. | p09-2.1, p12 | **Gate** | A |
| M3 | **Table = structure + content, paired.** Structure-only pass cannot satisfy a table gate without full-TEDS/GriTS_Con at the same bar. | p09-2.2/2.3/2.4, p27-D27-03, p28 | **Gate** | A (V1,V2) |
| M4 | **Text/order/detection constructs kept distinct.** NID/NED = text serialization; reading order = block-sequence construct (not char NED); P/R/F1 & mAP = detection, not transcription. No cross-benchmark score merging without implementation parity. | p09-2.5/2.6/2.7, RJ7 | No (per-axis floors) | A |
| M5 | **Binary unit tests for construct-invalid cases.** Math sign, cell adjacency, reading order verified by deterministic pass/fail, not edit distance — with acknowledged coverage limits (RJ2). | p28-A2, p13, p29-B2 | Gate candidate | A (V3) |
| M6 | **Zero-authoring baseline on 100% of pages.** Non-empty, anti-repetition (>30-char n-gram), charset sanity (domain-calibrated, not English-centric). | p28-B1/B2 | **Gate** | A/B |
| M7 | **Evaluator/matching contract pinned.** match_method, ignore masks, evaluator version/commit recorded; unpinned → evidence grade capped at C. | p09-2.9, p12 | Process gate | A |
| M8 | **Ground-truth trustworthiness.** Versioned guidelines + pilots; correct chance-corrected IAA (α preferred) with raw agreement; adjudicated label-of-record with provenance ladder; stratified population-aligned sampling; imperfect-oracle honesty. | p11-P11-01..06/08/10 | Gate (adjudication + honesty) | A |
| M9 | **Role independence.** author ≠ annotator ≠ adjudicator ≠ evaluator; judge family ≠ generator family, or bounded self-preference; disjoint train/test annotators. | p11-P11-07, p10-J6 | **Gate** | A (V7) |
| M10 | **LLM-judge validity battery (advisory).** Multi-bias RR/flip metrics; chance-corrected human κ on domain pairs; objective-corruption stratum; calibration if confidence exposed; multi-trial aggregation. | p10-J1..J5/J7/J9/J10 | Soft cap now; gate after labels (RJ3/RJ4) | A (V4,V5,V6) |
| M11 | **Advisory-only wiring.** Judge output cannot pass/fail a gate; removing the judge field must not change verdict (CI contract test). | p05, p10-J8, p19, p28, p30-E11 | **Gate** | A (arch + RC1) |
| M12 | **Calibrated thresholds + banded, evidence-graded reporting.** Explicit values with calibration provenance or "uncalibrated" flag; composite reported as a band with named flip conditions; weakest-link evidence grade propagation. | p16, p17, p30-E3/E12 | Reporting gate | A (V8,V9) |

Criteria that are *not* measurement-validity (packaging p01-p03, CI p04, architecture p05-p08, docs/CLI/provenance/security/privacy/observability p20-p25, non-eval case-study material in p26/p27/p29) are out of my lane and pass through to Meta-Reviewers on those dimensions; I only flagged their weight/gate arithmetic (RJ5/RJ6).

---

## 6. Recommended score architecture

A four-layer structure, consistent with the verified evidence and the eval-framework exemplars (GE + promptfoo + DeepEval/Giskard, V8/V9):

1. **Per-axis scores (the truth layer).** Report every axis in M1–M4 with score + machine-checkable reason + evidence grade + `eligible/null` counts. No axis is ever hidden behind a headline number. This is the layer against which everything else is defined.

2. **Conjunctive hard gates (non-compensatory, triaged to ≤7).** A high composite cannot buy these back. Recommended set, each testable *today*:
   - G1 — Null-eligibility integrity (M2): any modality scored when absent = fail.
   - G2 — Table structure+content paired (M3): structure-only pass with content fail = fail.
   - G3 — Zero-authoring baseline on all pages (M6): silent empty/garbled pass = fail.
   - G4 — Advisory-only wiring (M11): any LLM-signal→gate coupling = fail.
   - G5 — Role independence on calibration labels (M9): implementer-as-sole-annotator or shared judge/generator family without bounded self-preference = fail.
   - G6 — Adjudication + imperfect-oracle honesty (M8): unaudited plurality labels sold as "ground truth" = fail.
   - G7 — Evaluator/threshold provenance (M7+M12): scores without pinned evaluator version or with undeclared thresholds = capped, not gated (soft).
   Judge-quality gates (M10) stay **soft caps** (dimension ≤ level 2) until a labeled corpus exists — promote to hard gates only when the validation battery can actually run (RJ4).

3. **Weighted maturity composite (compensatory, navigation only).** Assigned once per deduplicated dimension by P15 — never summed from persona proposals (RJ5). Weights carry written rationale; mandatory sensitivity analysis names the single axis whose ±ε flips the band.

4. **Banded, evidence-graded verdict.** Report the composite as a band, not a point. Round to defensible precision (no two-decimal LLM scores, RJ1/RJ3). Propagate the weakest evidence grade among load-bearing inputs. Verdict class uses band overlap, not point comparison. (M12, p17, p30-E12.)

**Maturity ladder** (0–4) applies per dimension, gates sit orthogonal to it, and the composite is only meaningful once all gates pass — matching p14/p30 and the GE `severity:critical` pattern.

---

## 7. Confidence

| Element | Confidence | Basis |
|---|---|---|
| Underlying citations (extraction metrics, judge science, calibration, eval frameworks) | **HIGH** | 10/10 re-fetched claims verified verbatim; no hallucinations |
| Deduplicated criterion set (M1–M12) | **HIGH** | Direct collapse of converging, primary-source-backed criteria |
| Four-layer score architecture | **HIGH** | Matches verified exemplar practice (GE/promptfoo/DeepEval/Giskard) and internal FRAME §6 |
| Gate triage to ≤7 | **MEDIUM-HIGH** | Principle is sound (p30-E4); exact membership is a synthesis judgment call |
| Judge numeric floors (κ, flip, corruption) | **LOW until calibrated** | Placeholders by the authors' own admission (RJ3) |
| olmOCR head-to-head point values | **LOW (directional only)** | Version-drift vs live tables (RJ1) |
| Weight percentages | **N/A — do not sum** | Overlapping cluster proposals (RJ5) |

**Open questions handed forward:** (a) which self-hosted judge family the M10 battery is calibrated against (model-sovereignty constraint); (b) whether the whisker golden corpus can supply enough labeled, stratified, adjudicated pairs to convert M10 soft caps into hard gates; (c) final weight vector, owned by P15.

---

## 8. Sources re-verified (live, 2026-07-18)

- TEDS: Zhong, ShafieiBavani, Yepes, arXiv:1911.10683 (ECCV 2020); ecva.net ECCV 2020 PDF; github.com/ibm-aur-nlp/PubTabNet
- GriTS: Smock, Pesala, Abraham, arXiv:2203.12555 (ICDAR 2023); microsoft.com/en-us/research GriTS; github.com/kensho-technologies/grits
- olmOCR / olmOCR-Bench: arXiv:2502.18443v3; olmocr.allenai.org paper; huggingface.co/datasets/allenai/olmOCR-bench; llamaindex.ai olmOCR-Bench review
- JudgeBench: Tan et al., arXiv:2410.12784 (ICLR 2025); proceedings.iclr.cc
- Coin Flip Judge: arXiv:2606.13685
- Horn & Keuper: arXiv:2603.18652; github.com/phorn1/pdf-parse-bench
- Pan et al.: arXiv:2404.13076 (NeurIPS 2024); proceedings.neurips.cc; OpenReview 4NJBV6Wp0h
- DeepEval: deepeval.com/docs (metrics-introduction, metrics-llm-evals, evaluation-unit-testing-in-ci-cd)
- promptfoo: promptfoo.dev/docs (command-line, configuration/expected-outputs, configuration/reference)
- OmniDocBench: github.com/opendatalab/OmniDocBench (Overall formula, v1.5/v1.6 leaderboard)
