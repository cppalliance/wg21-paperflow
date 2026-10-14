# P10 — LLM-as-Judge Eval-Science Researcher

**Persona:** 10 of 30 (Cluster C — Extraction quality & eval science)  
**Date:** 2026-07-18  
**Scope:** External judge-eval science only. No whisker production code inspected. No whisker verdict.

---

## 1. Question restated

What external evidence and validation protocol must an **advisory LLM judge** (used to assess document-to-markdown extraction quality, never as a hard gate) satisfy before its verdicts are trustworthy enough to inform operators, calibration, or regression tracking?

The research question decomposes into five sub-questions the literature treats as non-optional:

1. **Bias surface:** Which systematic judge biases (position, verbosity, self-preference/self-enhancement, sycophancy, authority, fallacy oversight, and others) are documented, and how are they measured?
2. **Human alignment:** Under what task conditions does judge–human agreement reach useful levels, and when does raw agreement overstate performance?
3. **Confidence calibration:** Are self-reported or token-level confidence scores aligned with actual correctness, or do judges exhibit overconfidence that hides errors?
4. **Verdict stability:** What is the run-to-run flip rate for identical inputs, and how many repeated trials are needed for a stable majority verdict?
5. **Pre-deployment validation:** What benchmark battery and acceptance thresholds constitute a defensible "judge validated" state before production advisory use?

This persona produces **audit criteria + an external bar**, not a whisker judgment.

---

## 2. Proposed audit criteria

Each criterion below includes: how to measure, audit method (from `00-FRAME.md` §5), scoring-design hook (§6), gaming vector, anti-gaming guard, evidence grade, and Tier 1–2 citations.

### Criterion J1 — Documented bias battery with quantified effect sizes

**Statement:** Before an advisory judge is trusted, the operator must run a **principle-guided perturbation battery** covering at minimum position, verbosity, self-preference (when judge and candidate share a model family), and sycophancy/authority cues, reporting effect sizes with confidence intervals—not pass/fail anecdotes.

**How to measure:**
- **Position:** Present each pairwise comparison in both AB and BA order; report order-inconsistency / flip rate and position-bias statistic (|P(first wins) − 0.5|). Mitigation: conservative double-call with swap; declare win only if preferred in both orders (Zheng et al., 2023).
- **Verbosity:** Run a "repetitive list" or length-inflation attack: pad candidate output with redundant content that adds no information; measure whether the judge upgrades the padded version (Zheng et al., 2023). Optionally regress verdict on length differential (Reliability-without-Validity study, 2026).
- **Self-preference:** When judge and evaluated system share a model family, compare judge win-rate for own outputs vs. human-labeled equivalence pairs; report excess self-preference beyond human preference gap (Pan et al., NeurIPS 2024; Wataoka et al., 2024).
- **Sycophancy / authority:** Inject user-belief or authority-bias cues ("the author believes X is correct") into judge prompts or metadata; measure verdict shift on objectively correct extraction pairs (Sharma et al., 2024; Ye et al., 2024 CALM authority-bias category).
- **Extended battery:** CALM framework enumerates 12 bias types with Robustness Rate (RR) and Consistency Rate (CR); best models reach RR ≈ 0.86, not 1.0 (Ye et al., 2024).

| Field | Value |
|---|---|
| Audit method | Metric construct-validity audit (#4); Adversarial / red-team probing (#6) |
| Scoring hook | §6.4 anti-gaming (criteria must resist cosmetic compliance); §6.2 hard-gate candidate |
| Gaming vector | Report "bias tested" without perturbation attacks or without effect sizes |
| Anti-gaming guard | Require automated perturbation (CALM-style) on a held-out judge-validation set; publish RR/CR or equivalent per bias axis; fail if any Tier-1 bias axis exceeds pre-registered ceiling |
| Evidence grade | **A** (multiple Tier-1 corroborating: Zheng 2023, Ye/CALM 2024, Pan 2024, Sharma 2024) |

---

### Criterion J2 — Chance-corrected human agreement on domain-relevant pairs

**Statement:** Judge–human agreement must be reported with **chance-corrected metrics** (Cohen's κ, Krippendorff's α, or equivalent) on labeled extraction-quality pairs drawn from the target domain—not raw accuracy alone.

**How to measure:**
- Build or adopt a labeled set of (source snippet, candidate markdown, reference markdown) triples with expert adjudication on semantic fidelity axes relevant to extraction (content, structure, reading order)—not chat preference.
- Report κ/α against human majority labels; also report raw agreement and the **kappa deflation gap** (EM − κ), which recent large-scale work shows is 33–41 pp on preference-style benchmarks even for frontier judges (Reliability without Validity, 2026).
- For extraction-specific semantic judging, Horn & Keuper (2026) validate LLM table judges against 1,500+ human ratings (Pearson r = 0.93 vs. TEDS r = 0.68); use similar human-validation correlation targets when ground-truth pairs exist.
- MT-Bench line: strong GPT-4 judges reach >80% agreement with humans on open-ended chat, comparable to human–human agreement—but only after position-swap mitigation and on tasks with clear quality gaps (Zheng et al., 2023). **Do not import chat numbers as extraction gates.**

| Field | Value |
|---|---|
| Audit method | Calibration / operating-point audit (#5); Comparative benchmarking (#3) |
| Scoring hook | §6.1 weighted dimension (extraction-quality/eval); §6.3 evidence grades |
| Gaming vector | Cherry-pick easy pairs; report EM only; tune on the same set used for acceptance |
| Anti-gaming guard | Held-out human-labeled set disjoint from prompt/rubric development; pre-register minimum κ and maximum deflation gap; per-axis breakdown (tables, math, prose) |
| Evidence grade | **A** (Zheng 2023; Tan/JudgeBench 2025; Reliability without Validity 2026; Horn & Keuper 2026) |

---

### Criterion J3 — Objective-correctness stress test (JudgeBench-class)

**Statement:** Preference-aligned judges can look excellent on crowdsourced chat while failing **objective correctness** discrimination. The judge must be evaluated on pairs where one response is factually/logically wrong by verifiable ground truth, not merely less preferred.

**How to measure:**
- Run JudgeBench or an extraction analogue: pairs with one objectively incorrect markdown conversion (cell swap, relation flip, dropped negation) vs. correct reference.
- Report accuracy with position swap; JudgeBench shows many strong models (e.g., GPT-4o) only slightly above random on hard pairs (Tan et al., ICLR 2025).
- For document extraction, construct corruption controls (row/column swap, header merge, formula sign flip) with deterministic oracle labels—parallel to adversarial QA methodology in extraction benchmarks.

| Field | Value |
|---|---|
| Audit method | Adversarial / red-team probing (#6); Metric construct-validity audit (#4) |
| Scoring hook | §6.2 hard-gate candidate (judge that fails objective pairs cannot inform gates); §6.4 anti-gaming |
| Gaming vector | Validate only on subjective "which reads better" pairs |
| Anti-gaming guard | Require minimum performance on objectively mislabeled pairs; separate reporting for preference vs. correctness strata |
| Evidence grade | **A** (Tan et al. 2025; Zheng et al. 2023 limitations on math/reasoning) |

---

### Criterion J4 — Verdict stability and replication protocol

**Statement:** Single-trial LLM judging is **too noisy** for high-stakes advisory use. Operators must quantify run-to-run flip rate and specify a replication count for stable majority verdicts.

**How to measure:**
- **Flip rate:** Re-run identical judge prompts N≥5 times (document temperature/sampling settings); measure fraction of items where pairwise verdict changes (Coin Flip Judge study: mean 13.6% flip rate across judges; 28% of questions >20%; one item 56%; 11 trials needed for 95% recovery of 50-trial reference majority on average—Coin Flip Judge, 2026).
- **Consistency–bias paradox:** High test–retest reliability (α > 0.95) can coexist with severe position bias; stability ≠ validity (Reliability without Validity, 2026). Report flip rate **and** position bias together.
- **Mitigation:** Position randomization or AB+BA double evaluation; majority vote across N runs; flag high-variance items for human review (PMC LLM-as-judge search parsing study, 2025; Schroeder & Wood-Doughty McDonald's ω framework).
- **Deterministic decoding:** Reduces but does not eliminate inconsistency (Coin Flip Judge, 2026).

| Field | Value |
|---|---|
| Audit method | Reproducibility replay (#8); Observability audit (#11) |
| Scoring hook | §6.3 confidence; §6.6 score uncertainty (report bands driven by flip-prone items) |
| Gaming vector | Report stability at temperature 0 only while production uses sampling; single-run evaluation |
| Anti-gaming guard | Document N, temperature, seed policy; publish flip-rate distribution; require multi-trial aggregation in operator docs |
| Evidence grade | **A** (Coin Flip Judge 2026; Reliability without Validity 2026; PMC 2025) |

---

### Criterion J5 — Confidence calibration and overconfidence guard

**Statement:** If the judge emits confidence scores, probabilities, or natural-language certainty, those signals must be **calibration-tested**. Uncalibrated overconfidence is a documented failure mode that lets wrong verdicts auto-accept.

**How to measure:**
- Plot reliability diagrams / Expected Calibration Error (ECE) or task-specific **TH-Score** (thresholded high-confidence region alignment) between stated confidence and actual correctness (Overconfidence in LLM-as-a-Judge, 2025).
- Treat verbalized confidence as unreliable unless validated; prefer constrained token-level probability when available (Sycophantic Anchors judge template, 2026).
- Operational rule: high-confidence wrong judgments must route to human review, not silent acceptance (Overconfidence paper; PMC 2025).

| Field | Value |
|---|---|
| Audit method | Calibration / operating-point audit (#5); Confidence / evidence grading (#12) |
| Scoring hook | §6.2 hard-gate candidate if confidence used for auto-accept; §6.3 evidence grades |
| Gaming vector | Hide confidence miscalibration behind aggregate accuracy |
| Anti-gaming guard | Pre-register ECE/TH-Score ceiling; prohibit auto-accept on uncalibrated confidence |
| Evidence grade | **B** (Overconfidence 2025 Tier-1 arXiv; converging Tier-2 PMC 2025; Reliability without Validity notes logprob limits) |

---

### Criterion J6 — Judge–generator independence and model-family disclosure

**Statement:** When the judge shares weights, vendor, or training lineage with the system under test, **self-preference and self-recognition** must be measured and bounded. Judges should prefer independent model families for extraction QA when feasible.

**How to measure:**
- Report judge model ID, version/date, and whether it matches the extraction stack.
- Quantify self-preference: Pan et al. (2024) show GPT-4 self-recognition >50% out of the box and **linear correlation** between self-recognition capability and self-preference strength; GPT-4 self-preference disproportionate to human quality gaps.
- Wataoka et al. (2024) tie self-preference to perplexity/familiarity bias—judges favor lower-perplexity text regardless of authorship.
- Mitigations: human reference answers in prompt (Pan et al. 2024); separate judge model family; CALM self-enhancement RR tracking (Ye et al. 2024).

| Field | Value |
|---|---|
| Audit method | Conformance checklist (#1); Anti-gaming / Goodhart (#7) |
| Scoring hook | §6.2 hard-gate candidate (same-model judge + unbounded self-preference); §6.4 |
| Gaming vector | Omit model identity; reuse same model silently |
| Anti-gaming guard | Mandatory disclosure table; self-preference RR/error-rate bound on validation set |
| Evidence grade | **A** (Pan NeurIPS 2024; Wataoka 2024; Ye/CALM 2024) |

---

### Criterion J7 — Structured rubric with chain-of-thought and parseable verdict schema

**Statement:** Free-form "rate 1–5" judging without explicit rubric steps is insufficient. Production judges should use **CoT decomposed criteria + form-filling structured output**, validated for human alignment on the target task.

**How to measure:**
- Adopt G-Eval pattern: auto-generate evaluation steps from criteria, then score via constrained output slot; Liu et al. (EMNLP 2023) report Spearman ρ ≈ 0.514 with humans on summarization—outperforming prior metrics—with documented bias toward LLM-generated text.
- Require schema validation (JSON/Pydantic) so verdicts are machine-auditable; retry on parse failure.
- Extraction prompts should force **error identification before scoring** (Horn & Keuper 2026 grounded judging pattern) to reduce halo scoring.

| Field | Value |
|---|---|
| Audit method | Metric construct-validity audit (#4); Documentation completeness (#9) |
| Scoring hook | §6.1 dimension scoring; §6.4 (cosmetic rubric vs. exercised rubric) |
| Gaming vector | Rubric exists but judge ignores it; unstructured prose verdicts |
| Anti-gaming guard | Schema compliance rate logged; ablation showing rubric steps change scores on corrupted pairs |
| Evidence grade | **A** (Liu/G-Eval EMNLP 2023; Horn & Keuper 2026) |

---

### Criterion J8 — Advisory-only contract enforced in operator semantics

**Statement:** Even a well-calibrated judge remains **non-gating**. Audit checks that judge output cannot directly pass/fail extraction QA, matching hybrid-architecture doctrine.

**How to measure:**
- Trace operator/CLI/docs: judge scores appear in trace/debug/advisory channels only; deterministic gates ignore judge fields.
- Red-team: attempt to configure pipeline so judge verdict bypasses deterministic anchor—must fail closed.
- Aligns with LLM-as-judge literature warning against using judge scores as training rewards without bias mitigation (Ye et al. 2024; Tan et al. 2025).

| Field | Value |
|---|---|
| Audit method | Conformance checklist (#1); Anti-gaming (#7) |
| Scoring hook | §6.2 hard gate (LLM signal must not hard-gate); §6.4 self-consistency of rubric |
| Gaming vector | Rename advisory score to "gate score" in docs while wiring it into exit codes |
| Anti-gaming guard | CI contract test: judge field removal does not change pass/fail; code search for judge→gate coupling |
| Evidence grade | **B** (architecture pattern from P05 frame; judge literature warns on reward misuse—Ye 2024) |

---

### Criterion J9 — Benchmark stratification and non-transferable ranking acceptance

**Statement:** Judge quality rankings **do not transfer** across benchmarks. Validation must span easy preference-style, hard objective-correctness, and domain extraction sets.

**How to measure:**
- Evaluate on ≥2 strata: (a) preference/open quality, (b) objective correctness, (c) extraction semantic pairs.
- Reliability without Validity (2026): same 21 judges shift up to **15 rank positions** across MT-Bench, JudgeBench, RewardBench; MT-Bench κ spread 13.5 pp vs. JudgeBench 60.4 pp.
- Do not declare "best judge" from a single leaderboard.

| Field | Value |
|---|---|
| Audit method | Comparative benchmarking (#3); Benchmarking integrity (feeds P12) |
| Scoring hook | §6.5 disagreement handling; §6.6 uncertainty bands |
| Gaming vector | Single-benchmark hero number in README |
| Anti-gaming guard | Publish per-stratum κ/accuracy; composite judge score forbidden without strata |
| Evidence grade | **A** (Reliability without Validity 2026; Tan/JudgeBench 2025) |

---

### Criterion J10 — Ongoing judge regression suite in CI (judge-of-judge)

**Statement:** Judge validation is not one-shot. A **frozen canary set** of labeled extraction pairs must run in CI; material judge or prompt changes require re-validation before advisory scores ship.

**How to measure:**
- Maintain frozen canary with known human labels and corruption controls; track κ, flip rate, RR against CALM perturbations monthly.
- Detect **criteria drift** when human reviewers re-adjudicate (PMC 2025).
- Version judge prompts with semver; changelog ties prompt changes to metric deltas.

| Field | Value |
|---|---|
| Audit method | Reproducibility replay (#8); CI/CD maturity lens (P04) |
| Scoring hook | §6.1 weighted dimension; §6.4 canary that must fail on corrupted inputs |
| Gaming vector | Refresh canaries until they pass; unversioned prompt edits |
| Anti-gaming guard | Canaries include must-fail corruptions; prompt version pinned in trace artifacts |
| Evidence grade | **B** (PMC 2025 Tier-1; CALM 2024; G-Eval reproducibility practices) |

---

## 3. External benchmark / exemplar bar

The external bar for a **production-grade advisory extraction judge** combines general LLM-as-judge science with emerging document-extraction judge practice:

| Layer | Exemplar bar | Key numbers / practices |
|---|---|---|
| **Foundational judge science** | Zheng MT-Bench / Chatbot Arena (NeurIPS 2023 D&B) | >80% human agreement for strong judges *after* swap mitigation; position bias can flip verdicts; verbosity "repetitive list" attack; self-enhancement documented |
| **Bias quantification** | CALM (Ye et al., 2024) | 12 bias types; automated perturbation; RR ≤ ~0.86 even for best models—bias never zero |
| **Objective judge stress** | JudgeBench (Tan et al., ICLR 2025) | Correctness-labeled pairs; GPT-4o ~ barely above chance on hard set; AB+BA evaluation mandatory |
| **Large-scale reliability** | Reliability without Validity (2026) | 21 judges × 3 benchmarks; κ deflation 33–41 pp; consistency–bias paradox; verbosity bias much reduced in 2026 cohort but position bias persists |
| **Stability** | Coin Flip Judge (2026) | ~13.6% mean flip rate; 11+ trials for stable majority on high-variance items |
| **Calibration** | Overconfidence in LLM-as-a-Judge (2025) | TH-Score + LLM-as-a-Fuser; overconfidence pervasive; ensemble improves accuracy/ECE |
| **Self-preference** | Pan et al. (NeurIPS 2024) | Self-recognition causally linked to self-preference; independent judge family preferred |
| **Sycophancy** | Sharma et al. (ICLR 2024) | Models favor user-aligned wrong answers; PMs prefer sycophantic responses up to ~45–95% in conditions |
| **Extraction-specific semantic judge** | Horn & Keuper table benchmark (2026) | LLM judge r=0.93 vs human on tables; beats TEDS/GriTS; still requires human validation study |
| **Structured rubric** | G-Eval (Liu et al., EMNLP 2023) | CoT + form-filling; higher human correlation; warns LLM-text bias |
| **Operational replication** | PMC search-query LLM judge (2025) | Position controls, repeated runs, McDonald's ω, category-specific prompts |

**Contradictions surfaced (not hidden):**
- **Optimist line (Zheng 2023):** Strong judges match humans at ~human–human agreement on MT-Bench/Arena after mitigations.
- **Skeptic line (Tan 2025; Reliability 2026; Coin Flip 2026):** Raw agreement overstates skill; single-trial judging is noisy; preference benchmarks compress differences; objective hard pairs expose near-random judges.
- **Extraction twist (Horn 2026):** LLM judges can correlate with humans *better than* traditional structural metrics on tables—but that is **metric alignment**, not proof of safe gating or stability under perturbation.
- **Sycophancy vs. judge prompts:** CoT can reduce sycophancy in final answers but also **mask** it via post-hoc rationalization (2026 reasoning study)—judge prompts with user metadata must be tested, not assumed safe.

**Minimum external bar (synthesis):** An advisory extraction judge is externally defensible only if it publishes (1) multi-bias RR/flip metrics on held-out labeled pairs, (2) chance-corrected human κ on domain data plus JudgeBench-class objective stress, (3) replication policy with documented N and flip rates, (4) calibration report if confidence is exposed, (5) independence disclosure with self-preference bounds, (6) structured rubric/schema with corruption-canary regression—**and** (7) provable non-gating wiring.

---

## 4. Recommended weight & hard-gate rationale

| Criterion | Recommended weight (within eval-science slice) | Hard gate? | Rationale |
|---|---:|---|---|
| J1 Bias battery | 15% | **Yes** — fail if position/verbosity/self-preference axes untested or above pre-registered RR floor | CALM + Zheng show biases are large enough to invert verdicts; untested judge is undefined |
| J2 Chance-corrected human κ | 20% | **Yes** — fail if domain κ below pre-registered minimum on held-out set | Core construct validity; raw EM gaming is documented (κ deflation) |
| J3 Objective stress | 15% | **Yes** — fail if near-random on corrupted/objective pairs | JudgeBench proves preference success ≠ correctness |
| J4 Verdict stability | 15% | No (weight heavily) | Single-trial noise is structural; mitigated by protocol not binary pass |
| J5 Calibration | 10% | **Yes** if confidence drives any automation | Overconfidence propagates silent errors |
| J6 Independence | 10% | **Yes** if same-model judge without measured self-preference bound | Pan 2024 causal self-preference |
| J7 Structured rubric | 5% | No | Raises quality; absence is immaturity not immediate unsafe |
| J8 Advisory-only | 5% | **Yes** — conjunctive with architecture gates | Non-negotiable hybrid contract |
| J9 Stratified benchmarks | 3% | No | Prevents leaderboard overclaim |
| J10 CI regression | 2% | No | Maturity indicator |

**Suggested pre-registered floors (to be calibrated on whisker labels later—method only here):**
- Domain κ ≥ 0.50 on held-out expert labels (stratum-wise reporting required).
- Position flip rate ≤ 0.15 after AB+BA conservative aggregation (stricter than Coin Flip mean if advisory influences human decisions).
- Objective corruption accuracy ≥ 0.70 on must-fail pairs (below this, judge is advisory noise).
- Self-preference error rate ≤ human baseline + 5 pp (Pan/Wataoka framing).
- If confidence exported: ECE or TH-Score in validated acceptable band (Overconfidence 2025).

Weights apply to the **extraction-quality/eval-science** dimension only; synthesis merges with P09 (metric validity), P11 (ground truth), P12 (benchmarking), P16 (threshold calibration).

---

## 5. Sources

Tier labels follow `00-FRAME.md` §4. All URLs stable as of 2026-07-18 research pass.

### Tier 1 — Authoritative / primary

| ID | Citation | URL | Date/version |
|---|---|---|---|
| S1 | Zheng, L. et al. *Judging LLM-as-a-judge with MT-Bench and Chatbot Arena.* NeurIPS 2023 Datasets & Benchmarks Track | https://arxiv.org/abs/2306.05685 | v4, 2023-12 |
| S2 | Liu, Y. et al. *G-Eval: NLG Evaluation using GPT-4 with Better Human Alignment.* EMNLP 2023 | https://arxiv.org/abs/2303.16634 | 2023-10 |
| S3 | Pan, S. et al. *LLM Evaluators Recognize and Favor Their Own Generations.* NeurIPS 2024 | https://arxiv.org/abs/2404.13076 | 2024-04 |
| S4 | Sharma, M. et al. *Towards Understanding Sycophancy in Language Models.* ICLR 2024 | https://arxiv.org/html/2310.13548v4 | 2024 |
| S5 | Ye, J. et al. *Justice or Prejudice? Quantifying Biases in LLM-as-a-Judge (CALM).* | https://arxiv.org/abs/2410.02736 | 2024-10 |
| S6 | Tan, J. et al. *JudgeBench: A Benchmark for Evaluating LLM-based Judges.* ICLR 2025 | https://arxiv.org/abs/2410.12784 | 2024-10 |
| S7 | *Overconfidence in LLM-as-a-Judge: Diagnosis and Confidence-Driven Solution.* | https://arxiv.org/abs/2508.06225 | 2025-08 |
| S8 | *Reliability without Validity: A Systematic, Large-Scale Evaluation of LLM-as-a-Judge Models.* | https://arxiv.org/html/2606.19544v1 | 2026-06 |
| S9 | *The Coin Flip Judge? Reliability and Bias in LLM-as-a-Judge Evaluation.* | https://arxiv.org/html/2606.13685 | 2026-06 |
| S10 | Horn, P. & Keuper, J. *Benchmarking PDF Parsers on Table Extraction with LLM-based Semantic Evaluation.* | https://arxiv.org/abs/2603.18652 | 2026-03 |
| S11 | Wataoka, S. et al. *Self-Preference Bias in LLM-as-a-Judge.* | https://arxiv.org/abs/2410.21819 | 2024-10 |
| S12 | Koo, R. et al. *Benchmarking LLM-as-a-Judge for Search Query Parsing* (PMC peer-reviewed) | https://pmc.ncbi.nlm.nih.gov/articles/PMC12319771/ | 2025 |

### Tier 2 — Strong secondary

| ID | Citation | URL | Date/version |
|---|---|---|---|
| S13 | Hugging Face dataset card: *pdf-parse-bench* (LLM judge validation methodology summary) | https://huggingface.co/datasets/piushorn/pdf-parse-bench | 2026 |
| S14 | SycEval: *Evaluating LLM Sycophancy* | https://arxiv.org/html/2502.08177v1 | 2025-02 |

### Tier 3 — Contextual (not load-bearing alone)

| ID | Citation | URL |
|---|---|---|
| S15 | Microsoft Learn: G-Eval metric for summarization (implementation notes, n=20 sampling) | https://learn.microsoft.com/en-us/ai/playbook/technology-guidance/generative-ai/working-with-llms/evaluation/g-eval-metric-for-summarization |

**Source count:** 12 Tier 1–2 distinct primary sources (floor ≥3 satisfied).  
**Evidence grades for criteria:** predominantly A/B on Tier 1 corpus; no criterion rests on Tier 4.

---

## 6. Overlap statement

This persona researched **external LLM-as-judge evaluation science** only.

**Avoided duplicating:**
- `llm-stack/` — code-level audit of whisker's tapetum LLM cascade, isolation, and injection defense (this file does not inspect tapetum or reach a whisker hardening verdict).
- `deepseek-v4-pro/` — model-specific selection for one candidate judge (this file is model-agnostic validation methodology).
- `persona/` — whisker deterministic metric/gate code scoring (TEDS/NID/MHS implementation findings).
- `buildvsbuy/` — library import decisions for metric code.
- `p09-extraction-quality-metrics.md` — construct validity of **non-LLM** metrics (TEDS, GriTS, NID); this persona covers the **judge layer** that may assess extraction, not replacement of structural metrics.
- `p16-threshold-calibration.md` — operating-point fitting on labels (complementary; J2/J5 reference calibration but do not design whisker gate thresholds).

**Confirmation:** No whisker production code was opened. No whisker `file:line` citations. No whisker quality verdict. Single output file: `p10-llm-as-judge-eval.md`.

---

## Return metadata (for orchestrator)

- **Tier 1–2 source count:** 12  
- **Strongest criterion:** **J2 — Chance-corrected human agreement on domain-relevant pairs** (κ/α on held-out expert labels with deflation reporting). It is the only criterion that directly validates the core claim "this judge measures extraction quality" rather than merely "this judge is reproducibly wrong." JudgeBench (S6) and Reliability-without-Validity (S8) show preference and raw EM are systematically misleading without it; Horn & Keuper (S10) anchor the same principle in document-extraction semantics.
