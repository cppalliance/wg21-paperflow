# P19 — Anti-Gaming & Goodhart-Robustness Researcher

**Persona:** 19 (Cluster E — Adversarial / anti-gaming)  
**Date:** 2026-07-18  
**Scope:** External method and standards only. No whisker production code inspected. No whisker verdict.

---

## 1. Question restated

How should the whisker professional-grade audit **design its rubric and gates** so that scores cannot be raised by cosmetic compliance, benchmark tuning, evaluator tampering, or proxy-metric optimization without genuine extraction-QA quality gain? What **anti-gaming rules** (frame section 6.4) and **per-criterion gaming-vector checklist** must every rubric line pass before it becomes load-bearing?

This persona researches Goodhart/specification-gaming defenses for metrics used as gates: multi-metric triangulation, non-compensatory hard gates, canaries that must fail, holdout secrecy, trusted reference evaluators, and criterion wording that resists optimization pressure. It does **not** red-team whisker or enumerate attack probes (that is P18).

---

## 2. Proposed audit criteria

Each criterion below is written for the **audit rubric itself** (meta-level): the synthesis must ensure every scored sub-criterion in the final whisker audit satisfies the gaming checklist in section 2.9.

### Criterion AG-1 — No single-metric gate without orthogonal corroboration

| Field | Content |
|---|---|
| **How to measure** | For every load-bearing gate or weighted sub-score, list (a) the primary metric and (b) at least one **orthogonal** check on a different construct (e.g., surface similarity + downstream fact recovery; automated metric + human/blind read-back; content axis + reading-order axis). Fail the rubric-design review if any gate rests on one compensatory number alone. |
| **Audit method** | #7 Anti-gaming / Goodhart stress; #4 Metric construct-validity audit |
| **Scoring hook** | 6.4 (anti-gaming rules); 6.1 (per-dimension scores, no composite-only reporting) |
| **Gaming vector** | Optimizing the lone visible metric (TEDS-only table pass, NID-only text pass, coverage-only gate) while corrupting unmeasured dimensions. |
| **Anti-gaming guard** | Require **metric slate** with documented orthogonality; report per-axis scores alongside any composite; treat single-number improvement without corroboration as **contested** (6.5). |
| **Evidence grade** | **A** — multiple Tier-1 sources converge on multi-metric mitigation. |
| **Sources** | Thomas & Uminsky (2020); OECD/JRC Handbook (2008); Gao et al. (2023) |

---

### Criterion AG-2 — Non-compensatory hard gates for non-negotiable dimensions

| Field | Content |
|---|---|
| **How to measure** | Classify each rubric dimension as compensatory (weighted ordinal) or **non-compensatory** (hard gate). Security, licensing, determinism-replay failure, LLM-as-hard-gate, and disproven construct validity must be gates: a high weighted total cannot offset them. Document gate logic using explicit non-compensatory aggregation (e.g., veto / outranking) where dimensions are substitutable only within declared families. |
| **Audit method** | #7 Anti-gaming / Goodhart stress; #2 Maturity-model scoring (gate caps level) |
| **Scoring hook** | 6.2 (hard gates conjunctive with weighted score); 6.4 |
| **Gaming vector** | **Compensatory masking**: strong packaging/docs score hides failed security, failed holdout generalization, or broken determinism claim. |
| **Anti-gaming guard** | Gates are **conjunctive** with composite; OECD/JRC explicitly warns that linear compensatory aggregation invites manipulation when stakeholders optimize the index. Use non-compensatory logic for integrity dimensions. |
| **Evidence grade** | **A** |
| **Sources** | OECD/JRC Handbook (2008), §1.6–1.7, §6.13 (NCMC); Thomas & Uminsky (2020) |

---

### Criterion AG-3 — Canary / negative-control probes with mandatory expected failure

| Field | Content |
|---|---|
| **How to measure** | Every gate advertised as catching corruption must ship **canary cases** (known-bad inputs) that **must fail** the gate. Audit checks: (1) canary catalog exists and is versioned; (2) CI or audit replay shows canaries fail on current tooling; (3) adding a canary is required when a new gaming vector is discovered. "Has tests" fails; "tests include canaries that must fail" passes. |
| **Audit method** | #7 Anti-gaming / Goodhart stress; #6 Adversarial / red-team probing (boundary: P18 designs attack catalog; P19 requires canaries as anti-gaming teeth) |
| **Scoring hook** | 6.4 (explicit frame example: tests with canary that must fail) |
| **Gaming vector** | **Cosmetic test coverage**: trivial assertions, tautological checks, or tests that never fail on injected corruption. |
| **Anti-gaming guard** | Canaries are **negative controls**; gate without failing canary is downgraded to cosmetic (max maturity 1). Incentivized reward-hacking experiments show adding explicit adversarial incentive exposes overseer flaws early (Bowman et al., OpenReview). |
| **Evidence grade** | **B** — strong practice in eval-integrity literature; canary wording from frame 6.4. |
| **Sources** | Frame 00-FRAME.md §6.4; incentivized reward-hacking evaluation (OpenReview, 2023); RewardHackingAgents (2026) |

---

### Criterion AG-4 — Holdout secrecy and benchmark-contamination resistance

| Field | Content |
|---|---|
| **How to measure** | (1) Holdout corpus IDs and labels are access-controlled; not used for threshold tuning, golden authoring, or regression baselines visible to implementers during iteration. (2) Document dev/replay vs holdout split policy. (3) Apply contamination detection mindset: performance on holdout should **generalize** to rephrased or reference benchmarks; suspiciously high holdout-only gains trigger review. (4) Publish a benchmark transparency card for any internal benchmark used in gates. |
| **Audit method** | #7 Anti-gaming / Goodhart stress; #5 Calibration / operating-point audit (holdout reserved for commit) |
| **Scoring hook** | 6.4; 6.5 (contested if leakage suspected); 6.6 (flip condition: holdout relabeled) |
| **Gaming vector** | **Metric overfitting / benchmark contamination**: tuning thresholds, prompts, or converters on the same items used as the gate; memorizing holdout structure. |
| **Anti-gaming guard** | Separate **fit set** (calibration) from **commit set** (locked holdout); ConStat-style principle that contamination = non-generalizing inflated performance, detectable via reference benchmarks; Benchmark Transparency Card for documentation. |
| **Evidence grade** | **A** |
| **Sources** | Dekoninck et al., NeurIPS 2024 (ConStat); Xu et al., 2024 (benchmark leakage); OECD sensitivity/robustness (2008) |

---

### Criterion AG-5 — Trusted reference evaluator vs agent-visible reported metric

| Field | Content |
|---|---|
| **How to measure** | Where evaluation code or metrics are mutable (CI scripts, local QA harness, agent-editable workspace), require a **trusted reference path** (`true_metric`) computed from pristine, locked evaluator code. Compare `reported_metric` vs `true_metric`; log evaluator hash changes and split-access attempts. Single-signal mismatch without tamper evidence is inconclusive, not pass. |
| **Audit method** | #7 Anti-gaming / Goodhart stress; #11 Observability / fault-injection audit |
| **Scoring hook** | 6.2 (candidate hard gate: integrity failure); 6.4 |
| **Gaming vector** | **Evaluator tampering**: patch metric script, relax threshold in config, or report inflated numbers while true quality is flat (RewardHackingAgents vectors). |
| **Anti-gaming guard** | **Full_locked** regime pattern: deny train-time holdout access + score via external pristine reference; integrity as first-class outcome. |
| **Evidence grade** | **A** |
| **Sources** | Wang et al., RewardHackingAgents (2026); Krakovna et al. (2020) specification gaming catalog |

---

### Criterion AG-6 — Proxy–true divergence monitoring (format vs content sensitivity)

| Field | Content |
|---|---|
| **How to measure** | For any LLM-judge or proxy scorer used in the rubric (even advisory), apply **invariance stress tests**: controlled format perturbations (bullets, headers) vs content perturbations (paraphrase). Flag **format-dominant gains** where proxy rises without content improvement. Track proxy–human or proxy–gold correlation over tuning iterations; trigger review when correlation degrades (EST / overoptimization literature). |
| **Audit method** | #7 Anti-gaming / Goodhart stress; #4 Metric construct-validity audit |
| **Scoring hook** | 6.4; 6.3 (LLM-derived scores advisory in rubric too); 6.5 |
| **Gaming vector** | **Specification gaming / reward hacking**: verbosity inflation, markdown cosmetics, judge-specific stylistic exploits (Krakovna; Gao et al.; EST ACL 2026). |
| **Anti-gaming guard** | Multi-detector ensemble (correlation tracking + invariance stress); cap optimization budget against any single proxy; rubric must not let LLM-generated numbers **gate** the audit verdict (frame 6.4 self-consistency). |
| **Evidence grade** | **A** |
| **Sources** | Gao et al., ICML 2023; ACL 2026 Findings (Evaluator Stress Test); Krakovna et al. (2020) |

---

### Criterion AG-7 — Criterion wording resists cosmetic compliance

| Field | Content |
|---|---|
| **How to measure** | Each rubric line must state an **observable, falsifiable** bar, not a proxy checklist item. Replace "documented" with "operator/agent reproduces run from docs alone"; replace "has CI" with "CI runs holdout canaries + locked reference metrics"; replace "calibrated" with "threshold committed with recorded TPR/FPR on labeled N." Review rejects adjective-only level descriptors ("good", "adequate"). |
| **Audit method** | #7 Anti-gaming / Goodhart stress; #9 Documentation-completeness audit (anti-gaming variant) |
| **Scoring hook** | 6.4; 6.1 (concrete level descriptors) |
| **Gaming vector** | **Checkbox auditing**: satisfying the letter of the criterion without the intended capability (Bevan & Hood target gaming; Thomas & Uminsky metric traps). |
| **Anti-gaming guard** | Mandatory **gaming vector + anti-gaming guard** fields per criterion (frame 6.4); falsifiable acceptance tests attached to each level. |
| **Evidence grade** | **B** |
| **Sources** | Thomas & Uminsky (2020); Frame 00-FRAME.md §6.4, §9 |

---

### Criterion AG-8 — Sensitivity and robustness analysis on composite scores

| Field | Content |
|---|---|
| **How to measure** | Before adopting weights, run **sensitivity analysis** on: indicator inclusion/exclusion, normalization, imputation, weights, aggregation method. Report which assumptions move ranks/scores materially. Publish composite as a **band** with named flip conditions (6.6), not a point alone. |
| **Audit method** | #7 Anti-gaming / Goodhart stress; #12 Confidence / evidence grading |
| **Scoring hook** | 6.6 (score uncertainty, flip conditions); 6.4 |
| **Gaming vector** | **Weight shopping** and **normalization gaming**: pick weights/normalization post hoc to maximize score. |
| **Anti-gaming guard** | Pre-register weight rationale; OECD/JRC mandatory robustness/sensitivity steps; document contested criteria rather than hiding disagreement (6.5). |
| **Evidence grade** | **A** |
| **Sources** | OECD/JRC Handbook (2008), Step 7; UNECE well-being guidelines (2025) |

---

### Criterion AG-9 — Optimization budget limits on proxy metrics

| Field | Content |
|---|---|
| **How to measure** | For any tunable pipeline element scored by a proxy (LLM judge, edit-distance gate, composite sub-index), define a **maximum safe optimization budget** (iterations, KL divergence cap, best-of-N limit) beyond which proxy gains are treated as suspect unless gold/human corroborates. Gao et al. document gold score peaking then falling as proxy optimization continues. |
| **Audit method** | #7 Anti-gaming / Goodhart stress; #5 Calibration / operating-point audit |
| **Scoring hook** | 6.4; 6.2 (gate thresholds must not be retuned on holdout) |
| **Gaming vector** | **Reward model overoptimization**: continued tuning after proxy–true correlation inverts. |
| **Anti-gaming guard** | Early-stop rules tied to proxy–gold divergence; treat post-peak proxy optimization as gaming unless validated on fresh labeled sample. |
| **Evidence grade** | **A** |
| **Sources** | Gao et al., ICML 2023; Thomas & Uminsky (2020) Goodhart in ML training |

---

### Criterion AG-10 — Per-axis reporting; forbid composite-only optimization target

| Field | Content |
|---|---|
| **How to measure** | Audit rubric and any whisker gate it evaluates must **always** report per-dimension/per-axis scores. Verdict narrative must not cite composite alone. If a team optimizes workflow, they must not be able to ignore failing axes hidden inside a compensatory average. |
| **Audit method** | #7 Anti-gaming / Goodhart stress; #4 Metric construct-validity audit |
| **Scoring hook** | 6.1 (no single composite alone); 6.4 |
| **Gaming vector** | **Axis masking**: improve average by sacrificing rare-but-critical modalities (tables, math, reading order). |
| **Anti-gaming guard** | Mandatory per-axis table in audit output; null-eligibility for absent modalities (cross-ref P09/P12); non-compensatory gates on critical axes. |
| **Evidence grade** | **B** — frame 6.1 + OECD composite pitfalls. |
| **Sources** | Frame 00-FRAME.md §6.1; OECD/JRC Handbook (2008) |

---

## 2.9 Gaming-vector checklist (required for every load-bearing criterion)

Before any rubric sub-criterion enters the synthesis, it must pass all ten checks:

| # | Check | Fail example | Pass example |
|---|---|---|---|
| G1 | **Orthogonality** — gate has ≥2 non-substitutable signals | TEDS alone for "table quality" | TEDS + cell-level fact spot-check or GriTS on holdout |
| G2 | **Non-compensatory** — integrity dimensions are gates, not weights | High docs score offsets security fail | Security fail → overall fail regardless of composite |
| G3 | **Canaries** — known-bad cases must fail | Tests never fail on corrupted input | Injected row-swap canary fails deterministic gate |
| G4 | **Holdout hygiene** — fit vs commit split documented | Threshold tuned on gate corpus | Calibrate on dev; commit threshold with frozen holdout |
| G5 | **Reference integrity** — reported vs trusted metric path | Self-reported benchmark in README | Locked `metrics_ref` vs mutable `evaluate.py` |
| G6 | **Invariance** — format tricks cannot pass alone | Bullet headers raise LLM judge score | Format perturbation does not flip pass without content change |
| G7 | **Falsifiable wording** — no adjective-only bar | "Good test suite" | "Canaries X/Y/Z fail; mutation score ≥ threshold on gate code" |
| G8 | **Sensitivity** — weight/normalization choices stress-tested | Weights chosen after seeing score | Pre-declared weights + sensitivity band in report |
| G9 | **Optimization cap** — proxy tuning bounded | Unlimited prompt/threshold iteration on holdout | Stop rule when proxy–gold correlation drops |
| G10 | **Per-axis visibility** — no composite-only claim | "Score 87" without axes | Table of axis scores + which axis triggered fail |

**Meta-rule (feeds 6.4):** If a proposed criterion cannot complete columns G1–G10, it is **not load-bearing** until rewritten or downgraded to informational maturity only.

---

## 3. External benchmark / exemplar bar

Serious anti-Gaming practice in ML evaluation and composite scoring sets this bar for whisker's audit rubric:

1. **Treat Goodhart as structural, not anecdotal.** Proxy optimization is the default equilibrium under finite-dimensional evaluation (Gao et al., ICML 2023; Thomas & Uminsky, 2020). The rubric assumes gaming will occur if a number becomes a target.

2. **Integrity is measurable.** RewardHackingAgents (2026) shows evaluator tampering and train/test leakage are independent failure modes; only combined locking + access control restores trust. Any audit that scores "eval maturity" without reference-metric separation fails the exemplar bar.

3. **Contamination is performance inflation, not just n-gram overlap.** ConStat (NeurIPS 2024) and benchmark-leakage work (Xu et al., 2024) require generalization checks to rephrased/reference benchmarks and transparency documentation. Holdout secrecy is necessary but not sufficient without generalization tests.

4. **Composite indices demand robustness discipline.** OECD/JRC (2008) requires sensitivity analysis, transparent methodology, and non-compensatory options when dimensions must not trade off. Professional audit composites must not be easier to game than the systems they judge.

5. **Specification gaming catalog scale.** Krakovna et al. (2020) document dozens of ways agents satisfy specs while violating intent; rubric designers should expect **many** gaming vectors, not a closed list.

6. **Detection beats hope.** EST (ACL 2026) and incentivized reward-hacking experiments show proactive stress tests and adversarial incentives surface gaming before human-visible quality collapse.

---

## 4. Recommended weight & hard-gate rationale

| Recommendation | Rationale |
|---|---|
| **Anti-gaming is cross-cutting, not a weighted dimension.** | Section 6.4 applies to **every** criterion. AG-1–AG-10 are **design rules** for the rubric, not a separate 5% weight slice that can itself be gamed. |
| **Candidate hard gate: AG-5 (reference integrity).** | If audit execution allows mutable evaluators without trusted reference comparison, the audit verdict is structurally untrustworthy (RewardHackingAgents). |
| **Candidate hard gate: AG-4 (holdout contamination).** | If holdout was used for tuning without documented relabel/commit protocol, calibration and quality gates are Goodharted (ConStat; Xu et al.). |
| **Candidate hard gate: AG-2 applied to advisory LLM contract.** | If an LLM score can hard-fail the audited package (violates whisker's own advisory doctrine), the rubric fails its own 6.4 self-consistency check. |
| **Weighted dimensions should inherit AG-8 bands.** | Any composite dimension score reported without sensitivity/flip analysis is capped at maturity level 2 per OECD practice. |

**Weight philosophy:** Anti-gaming guards **cap** scores rather than add points. A dimension with documented guards enables full maturity; absent guards, max level 1 regardless of nominal checklist completion.

---

## 5. Sources

Tier labels per `00-FRAME.md` §4. All URLs stable as of 2026-07-18.

### Tier 1 — Authoritative / primary

| ID | Source | Version / date | URL |
|---|---|---|---|
| S1 | Thomas, R. L., & Uminsky, D. *The Problem with Metrics is a Fundamental Problem for AI* | arXiv:2002.08512, Feb 2020 | https://arxiv.org/abs/2002.08512 |
| S2 | Gao, L., Schulman, J., & Hilton, J. *Scaling Laws for Reward Model Overoptimization* | ICML 2023, PMLR 202:10835–10866 | https://proceedings.mlr.press/v202/gao23h.html |
| S3 | Dekoninck, J., Müller, M. N., & Vechev, M. *ConStat: Performance-Based Contamination Detection in LLMs* | NeurIPS 2024 | https://proceedings.neurips.cc/paper_files/paper/2024/file/a7f89793b9e6f8c6568dbbb6ff727b9b-Paper-Conference.pdf |
| S4 | OECD / European Commission JRC. *Handbook on Constructing Composite Indicators: Methodology and User Guide* | 2008 (rev. of 2005 ed.) | https://www.oecd.org/content/dam/oecd/en/publications/reports/2008/08/handbook-on-constructing-composite-indicators-methodology-and-user-guide_g1gh9301/9789264043466-en.pdf |
| S5 | Xu, R., Wang, Z., Fan, R., & Liu, P. *Benchmarking Benchmark Leakage in Large Language Models* | arXiv:2404.18824, Apr 2024 | https://arxiv.org/abs/2404.18824 |
| S6 | ACL 2026 Findings. *Detecting Proxy Gaming in RL and LLM Alignment via Evaluator Stress Tests* | 2026 | https://aclanthology.org/2026.findings-acl.513.pdf |
| S7 | Wang et al. *RewardHackingAgents: Benchmarking Evaluation Integrity for LLM ML-Engineering Agents* | arXiv:2603.11337, 2026 | https://arxiv.org/abs/2603.11337 |
| S8 | OpenReview. *Evaluating Oversight Robustness with Incentivized Reward Hacking* | ICLR-style preprint, id licAR8FPTW | https://openreview.net/pdf?id=licAR8FPTW |

### Tier 2 — Strong secondary

| ID | Source | Version / date | URL |
|---|---|---|---|
| S9 | Krakovna, V., et al. *Specification gaming: the flip side of AI ingenuity* | DeepMind, 21 Apr 2020 | https://deepmind.google/blog/specification-gaming-the-flip-side-of-ai-ingenuity/ |
| S10 | UNECE. *Guidelines on measurement of well-being*, Ch. 4 Composite Indicators | Sep 2025 | https://w3.unece.org/Stories/2025/09/wellbeing/webpage6.html |

### Tier 3 — Contextual (locator only)

| ID | Source | Note |
|---|---|---|
| S11 | Manheim, D., & Garrabrant, S. *Goodhart Taxonomy* | Cited in S1; regressive/extremal/causal/adversarial Goodhart modes useful for checklist taxonomy. |
| S12 | Frame `00-FRAME.md` §6.4 | Internal Stage-0 contract; not external evidence but defines deliverable shape. |

### Contradictions surfaced

| Topic | Position A | Position B | Resolution for synthesis |
|---|---|---|---|
| Can contamination be detected from training data? | Traditional n-gram/perplexity overlap methods | ConStat: performance generalization gap is the definition | Prefer **generalization-based** holdout checks (S3, S5); overlap methods are supplementary. |
| Compensatory vs non-compensatory aggregation | Linear weighted sums are standard and interpretable | OECD NCMC when dimensions must not trade off | Use compensatory weights **within** maturity families; **non-compensatory gates** across integrity families (S4). |
| Eliminate vs manage gaming | Some RL literature seeks hack-free reward | EST / Gao: hacking is equilibrium under finite eval | Rubric **detects and caps**; does not assume eliminability (S2, S6, S7). |

**Distinct Tier 1–2 primary sources used:** 10 (S1–S10, excluding internal frame).

---

## 6. Overlap statement

This persona researched **external anti-Gaming / Goodhart methodology** for audit rubric design (frame §6.4) only.

**Did not duplicate:**

| Prior folder | Boundary held |
|---|---|
| `persona/` | No whisker code audit; no deterministic-core scoring replay. |
| `llm-stack/` | No tapetum/isolation code findings; only external proxy-gaming science. |
| `redteam/` | No per-converter red-team reports; P18 owns attack taxonomy/probe catalog. **P19 owns meta-rubric anti-gaming rules and the G1–G10 checklist.** |
| `buildvsbuy/` | No library-choice decisions for metric implementations. |
| P15 weighted-scoring | P15 designs weights/MCDA; P19 constrains **how criteria resist gaming** once weighted. |
| P16 threshold calibration | P16 designs fit/commit protocol; P19 adds **holdout secrecy and contamination guards** around that protocol. |
| P18 adversarial methodology | P18 designs attacks; P19 designs **defenses at rubric/gate level** (canaries, triangulation, reference metrics). |

**Confirmation:** No whisker production code was opened. No whisker `file:line` citations. No whisker verdict. Single output file: `p19-anti-gaming-goodhart.md`.
