# P11 — Ground-Truth & Corpus-Construction Methodologist

**Persona:** 11 of 30 (Stage 0 internet-research)  
**Date:** 2026-07-18  
**Scope:** External methodology for building trustworthy ground truth without a perfect oracle. No whisker code inspection. No whisker verdict.

---

## 1. Question restated

What external bar should a professional extraction-QA audit apply when judging whether a **ground-truth corpus** (golden references, human labels, adjudicated verdicts) is **trustworthy enough to calibrate gates, score regressions, and defend quality claims**, given that no perfect oracle exists?

Sub-questions this persona resolves into audit criteria:

1. **Annotation protocol** — Are guidelines versioned, pilot-tested, and sufficient to resolve edge cases before scale?
2. **Inter-annotator agreement (IAA)** — Is the right chance-corrected statistic used, on the right unit, with raw agreement reported alongside?
3. **Label provenance** — Can every label be traced through a status ladder (draft → pilot → adjudicated → verified) with actor, timestamp, and guideline version?
4. **Corpus representativeness** — Is the evaluation set built by **stratified sampling** over the target population, not convenience or single-axis random draw?
5. **Independence** — Are author, primary annotator, adjudicator, and downstream evaluator **role-separated** so labels are not circularly self-validating?

---

## 2. Proposed audit criteria

Each criterion includes: measure, audit-method tag (§5 of `00-FRAME.md`), scoring-design hook (§6), gaming vector, anti-gaming guard, evidence grade, and Tier 1–2 citations.

### Criterion P11-01 — Versioned annotation guidelines with pilot iteration

| Field | Content |
|---|---|
| **Criterion** | A written annotation rubric exists **before** production labeling; it defines labels, edge-case rules, positive/negative examples, and a version ID. At least **two pilot rounds** on a representative sample refine the rubric until disagreement sources are documented and resolved. |
| **How to measure** | Checklist: (a) rubric artifact with version/date; (b) pilot sample size and count of guideline revisions logged; (c) changelog linking disagreements to rubric edits. Maturity 0 = no rubric; 4 = versioned rubric + ≥2 pilot cycles + disagreement-driven revisions documented. |
| **Audit method** | Conformance checklist; Documentation-completeness audit |
| **Scoring hook** | §6.1 dimension: extraction-quality/eval; §6.4 anti-gaming |
| **Gaming vector** | Publish a one-page "guidelines" stub that restates task names without edge-case rules; claim "pilot" without iteration log. |
| **Anti-gaming guard** | Require **disagreement-to-rubric traceability**: each pilot round lists top disagreement categories and the rubric clause added/changed to address them (Kunilovskaya et al. bare-minimum: guideline access is not optional metadata). |
| **Evidence grade** | **A** — converging Tier 1: iterative guideline practice (Krippendorff 2018 Ch. 12 reliability designs; Kunilovskaya et al. 2026 §7; Gebru et al. 2021 labeling section). |

---

### Criterion P11-02 — Correct IAA statistic for task geometry

| Field | Content |
|---|---|
| **Criterion** | IAA is computed with a metric matched to annotator count and data type: Cohen's κ for **two** nominal raters with complete overlap; Fleiss' κ for **≥3** fixed raters; **Krippendorff's α** when raters vary per item, data are ordinal/interval, or labels are missing. Raw percent agreement is reported **alongside** chance-corrected scores. |
| **How to measure** | Inspect IAA reports for metric choice vs. setup. Flag: κ on ordinal severity without weighting; κ with >2 raters; percent-only reporting. Score 0–4 by number of violations. |
| **Audit method** | Metric construct-validity audit |
| **Scoring hook** | §6.1 extraction-quality/eval; §6.3 evidence grade propagates from mis-specified metrics |
| **Gaming vector** | Report only percent agreement on imbalanced labels (inflates apparent quality); pick κ because it is familiar though α is required. |
| **Anti-gaming guard** | Mandate **dual reporting**: chance-corrected statistic + raw agreement + confusion/disagreement matrix; require explicit justification when κ is used despite known prevalence/bias limitations (Di Eugenio & Glass 2004; Krippendorff 2018). |
| **Evidence grade** | **A** — Tier 1 statistical standards (Krippendorff 2018/2019; Artstein & Poesio 2008 via Kunilovskaya et al. 2026). |

**Contradiction surfaced:** Cohen's κ remains widely used in NLP despite known prevalence and marginal-distribution sensitivity. Di Eugenio & Glass (2004) recommend reporting Co, Scott & Pi, and prevalence-adjusted measures together. **Audit rule:** prefer α for multi-rater / missing-data setups; if κ is retained, document why and report supplementary agreement decomposition.

---

### Criterion P11-03 — Stated IAA threshold met before production scale

| Field | Content |
|---|---|
| **Criterion** | Production labeling does not proceed until IAA on the pilot sample meets a **pre-registered threshold** appropriate to task difficulty, or items failing threshold are routed to adjudication/redesign. |
| **How to measure** | Verify documented threshold (e.g., α ≥ 0.67 for exploratory tasks, higher for gate-bearing labels — team must cite rationale). Check pilot IAA vs. threshold before bulk label commit. |
| **Audit method** | Calibration / operating-point audit (method design); Maturity-model scoring |
| **Scoring hook** | §6.2 candidate hard gate for **benchmark labels used to set production thresholds** |
| **Gaming vector** | Post-hoc threshold selection after seeing pilot scores; unlimited pilot relabel until α looks good. |
| **Anti-gaming guard** | Threshold and stopping rule **frozen before pilot scoring**; report pilot *n*, metric, and point estimate with confidence interval where sample size allows (Krippendorff 2018: α valid at small *n* but interpret cautiously). |
| **Evidence grade** | **B** — Krippendorff (Tier 1) + Kunilovskaya et al. reporting norms (Tier 1 arXiv 2026); threshold values are task-specific (Tier 2 practice, not universal constant). |

---

### Criterion P11-04 — Adjudication workflow with label-of-record provenance

| Field | Content |
|---|---|
| **Criterion** | Multi-annotator disagreements follow a documented adjudication path (senior expert / SME tie-break). The **label of record** is the adjudicated label, not silent majority vote. Every item logs: annotator IDs, timestamps, guideline version, adjudicator (if any), and rationale for override. |
| **How to measure** | Sample ≥5% of corpus: can each label row be traced to adjudication event? Maturity 0 = single annotator, no log; 4 = two-labeler-plus-adjudication with full audit row. |
| **Audit method** | Conformance checklist; Provenance / license conformance audit (metadata lineage, not copyright) |
| **Scoring hook** | §6.2 **hard gate** candidate: benchmark/golden labels used for calibration must be adjudicated, not unaudited plurality |
| **Gaming vector** | Majority vote without expert review on ambiguous cases; discard disagreements instead of adjudicating. |
| **Anti-gaming guard** | Require **disagreement retention**: all annotator votes preserved even when adjudicator overrides; random 5–10% agreed items also spot-adjudicated (federal labeling workflow pattern cited in precision engineering literature; aligns with ISO/IEC 5259-4 verification-at-each-stage principle). |
| **Evidence grade** | **A** — ISO/IEC 5259-4:2024 §6 (verify at each stage); Kunilovskaya et al. 2026 (adjudication underreported but essential); Klie et al. 2024 cited therein on adjudicated consensus approximating ground truth. |

---

### Criterion P11-05 — Label status ladder (draft / pilot / adjudicated / verified)

| Field | Content |
|---|---|
| **Criterion** | Every label carries a **provenance status**, not just a value: at minimum `draft` (single annotator, unaudited), `pilot` (calibration sample), `adjudicated` (consensus or expert tie-break), `verified` (independent re-review or gold-set confirmation). Promotion between states is logged; regression from verified requires explicit invalidation reason. |
| **How to measure** | Schema check on label store/metadata: status field + promotion log. % of gate-bearing labels at ≥ `adjudicated`. |
| **Audit method** | Maturity-model scoring; Observability audit (trace completeness for label lifecycle) |
| **Scoring hook** | §6.1 extraction-quality/eval; §6.2 gate: **calibration corpus labels must be ≥ adjudicated** |
| **Gaming vector** | Mark all labels `verified` without independent review; conflate pilot labels with production golden files. |
| **Anti-gaming guard** | **Independent verification sample**: hold a frozen gold subset; periodic re-label-from-scratch on random sample compared to stored labels (IAA measures consistency, not accuracy — gold set required per encord/industry QC pattern; aligns with Krippendorff's distinction of reliability vs. validity). |
| **Evidence grade** | **A** — W3C PROV-O / OASIS DPS provenance model (Tier 1 standards for entity lifecycle); ISO/IEC 5259-4 labeling lifecycle; Gebru et al. 2021 preprocessing/labeling documentation questions. |

---

### Criterion P11-06 — Stratified, population-aligned corpus sampling

| Field | Content |
|---|---|
| **Criterion** | Evaluation/golden corpus construction defines a **target population**, partitions it into **strata** (modality, layout class, committee, language feature, table density, etc.), and samples **proportionally or with explicit minimum per stratum** so no stratum is absent unless null-eligible. Convenience samples must be labeled as such and barred from threshold calibration. |
| **How to measure** | Compare stratum distribution in corpus vs. declared target population (χ² or max absolute proportion delta). B-VAT precedent: flag if any stratum deviates >5–10 pp from wild-type proportions without justification. Document stratum definitions before sampling. |
| **Audit method** | Comparative benchmarking against exemplars; Metric construct-validity audit (representativeness as construct) |
| **Scoring hook** | §6.1 extraction-quality/eval; §6.4 anti-gaming (holdout secrecy separate — see P12) |
| **Gaming vector** | Cherry-pick papers that score well; single-layout golden set for heterogeneous WG21 PDF/HTML mix. |
| **Anti-gaming guard** | **Pre-registered stratum table** frozen before items selected; report per-stratum *n* alongside aggregate metrics (Scale "coverage not averages" / semantic stratification principle: aggregate metrics hide structural failure modes). |
| **Evidence grade** | **A** — Afanador & Irvine 2020 USENIX CSET (stratified sampling for benchmark representativeness); software-repository stratified sampling methodology (Baltes et al. 2024 arXiv 2410.00639); Klearman et al. 2026 semantic stratification (arxiv 2604.20763). |

---

### Criterion P11-07 — Role independence (author ≠ annotator ≠ verifier ≠ evaluator)

| Field | Content |
|---|---|
| **Criterion** | **Separation of roles** is enforced: (1) corpus authors / tool implementers do not serve as sole annotators on gate-bearing labels; (2) adjudicators are not the same individuals as primary annotators on the same item without a second independent view; (3) test-set annotators are **disjoint** from training/golden-set annotators where labels encode stylistic or procedural fingerprints; (4) LLM-as-judge evaluators are not the same model family that produced the candidate output being scored (preference leakage). |
| **How to measure** | Role matrix audit: list personnel/model IDs per role; check overlaps. For ML-heavy setups, test generalization to held-out annotators (Geva et al. protocol). |
| **Audit method** | Anti-gaming / Goodhart stress; Adversarial probing (circularity attacks) |
| **Scoring hook** | §6.2 **hard gate** — failed independence invalidates calibration and benchmark claims regardless of composite score |
| **Gaming vector** | Developer self-annotates golden files; rerun judge with same model that generated extraction; reuse annotators across train and test splits. |
| **Anti-gaming guard** | **Disjoint-annotator test split** mandatory for any corpus used to claim generalization; document role assignments in datasheet (Gebru et al. 2021 collection-process questions). For LLM judges, declare generator–judge relatedness and measure preference-leakage score (Hong et al. 2024). |
| **Evidence grade** | **A** — Geva et al. 2019 EMNLP (annotator bias / disjoint test annotators); Hong et al. 2024 preference leakage (Tier 1 workshop/paper); Kunilovskaya et al. 2026 on annotator identity as validity factor. |

---

### Criterion P11-08 — Dataset datasheet / ISO 5259-4 labeling process documentation

| Field | Content |
|---|---|
| **Criterion** | The corpus ships with a **datasheet** (Gebru et al.) or equivalent ISO/IEC 5259-4 process record covering: motivation, composition, collection/sampling, preprocessing, **labeling protocol**, intended uses, maintenance, and known gaps. Labeling section answers: who labeled, training, compensation (where applicable), QC, IAA, adjudication, and whether labels are draft or verified. |
| **How to measure** | Score Reportage-style completeness (adapt Kunilovskaya taxonomy): ≥80% of applicable universal attributes for resource-creation corpora; ≥90% for calibration/golden corpora. |
| **Audit method** | Documentation-completeness audit; Conformance checklist (ISO/IEC 5259-4:2024) |
| **Scoring hook** | §6.1 documentation/operator-UX crossover; §6.3 evidence grade capped at C if datasheet absent |
| **Gaming vector** | README paragraph instead of structured datasheet; omit labeling section while claiming "golden" status. |
| **Anti-gaming guard** | Use **checklist with applicable-field logic** (Kunilovskaya Reportage Score denominator is task-sensitive — inapplicable fields do not inflate score). |
| **Evidence grade** | **A** — Gebru et al. 2021 Commun. ACM; ISO/IEC 5259-4:2024 (published 2024-06). |

---

### Criterion P11-09 — Embedded gold-set monitoring for label drift

| Field | Content |
|---|---|
| **Criterion** | A small **expert-verified gold set** is frozen before production labeling and **seeded** throughout the labeling stream to detect annotator drift; workers falling below accuracy vs. gold set are retrained or removed before their labels enter gate-bearing corpus. |
| **How to measure** | Verify gold-set size (typical 1–5% of label volume or fixed *n* ≥ 30 per major stratum), seeding frequency, and action policy when accuracy drops. |
| **Audit method** | Maturity-model scoring; Observability audit |
| **Scoring hook** | §6.4 anti-gaming (IAA alone is gameable without accuracy anchor) |
| **Gaming vector** | Compute IAA among equally miscalibrated annotators (consistent but wrong); no external anchor. |
| **Anti-gaming guard** | **IAA + gold-set accuracy dual control**: IAA measures consistency; gold set measures correctness — both required (explicit in multiple QC frameworks; Krippendorff distinguishes reliability from validity). |
| **Evidence grade** | **B** — Tier 1 reliability theory (Krippendorff 2018); Tier 2 operational QC patterns; supported by Kunilovskaya et al. emphasis on quality-control reporting. |

---

### Criterion P11-10 — Imperfect-oracle honesty (no false "ground truth" claims)

| Field | Content |
|---|---|
| **Criterion** | Public claims distinguish **reference labels** (human consensus with stated IAA and limitations) from **oracle truth**. Where source documents are ambiguous (scanned tables, unclear reading order), labels record `uncertain` / `expert-judgment` / `not-eligible` rather than forcing a single correct answer. |
| **How to measure** | Review claim language in docs vs. label metadata. Count forced labels on null-eligible modalities. |
| **Audit method** | Metric construct-validity audit; Anti-gaming / Goodhart stress |
| **Scoring hook** | §6.2 gate: using undisclosed expert-judgment references as bitwise oracle for automatic gates |
| **Gaming vector** | Brand noisy human consensus as "ground truth"; hide adjudication rate and unresolved disagreement count. |
| **Anti-gaming guard** | Require **disagreement budget reporting**: % items adjudicated, % marked uncertain, median annotator count per item. |
| **Evidence grade** | **A** — Krippendorff 2018 (data as communications, not physical truth); ISO/IEC 5259-4 validation against requirements; Kunilovskaya et al. 2026 on interpretability of human judgments. |

---

## 3. External benchmark / exemplar bar

Serious ground-truth construction (adapted to extraction QA) looks like this in the literature:

| Practice | Exemplar bar | Source tier |
|---|---|---|
| Iterative guidelines + blind multi-annotator pilot | Kunilovskaya et al. 2026 bare minimum: source, *n* annotators, items, annotators/item, **training**, language proficiency, expertise, compensation, **quality control**, **guideline access** | Tier 1 |
| Adjudicated meta-gold for evaluators | Annotated_gold: 72 tasks, dual annotation + two-stage adjudication; ~€6.3k expert cost acknowledged | Tier 1 |
| Chance-corrected IAA with task-appropriate metric | Krippendorff α as general standard; human–human α ≈ 0.585 on taxonomy, adjudicated consensus as benchmark | Tier 1 |
| Stratified benchmark design | B-VAT: CWE pillars as strata; proportional sample sizes; reject datasets whose stratum mix diverges wildly from wild population | Tier 1 |
| Annotator independence | Geva et al.: up to 23 accuracy-point drop when test annotators disjoint from training; mandate disjoint splits | Tier 1 |
| Labeling process standard | ISO/IEC 5259-4:2024 — plan, measure, monitor, improve; verify at each lifecycle stage; document labeling execution | Tier 1 |
| Provenance documentation | Gebru et al. datasheets — labeling/cleaning section mandatory for any dataset claiming benchmark status | Tier 1 |
| Coverage-aware eval sets | Semantic stratification: evaluate per stratum, not corpus average alone | Tier 1 (2026 preprint) |

**WG21 extraction-QA mapping (method only, not whisker-specific):** strata should cross **source modality** (PDF vs HTML), **layout complexity** (tables, code, math), **committee/era**, and **reading-order difficulty**; golden labels must record modality-null eligibility when a metric axis does not apply (feeds P09/P12 without duplicating their metric/benchmark criteria).

---

## 4. Recommended weight & hard gates

### Weight (feeds §6.1 composite — extraction-quality/eval cluster)

| Criterion | Suggested relative weight within P11 bundle | Rationale |
|---|---|---|
| P11-07 Role independence | **25%** | Strongest epistemic guard; failure collapses calibration validity |
| P11-06 Stratified representativeness | **20%** | Wrong corpus ⇒ right-looking metrics on wrong population |
| P11-04 Adjudication + label-of-record | **15%** | Without it, "consensus" is unobservable |
| P11-05 Label status ladder | **12%** | Enables honest use of partial-quality labels |
| P11-02 Correct IAA metric | **10%** | Mis-specified metric invalidates reported agreement |
| P11-01 Versioned guidelines + pilot | **8%** | Foundational but necessary-not-sufficient |
| P11-08 Datasheet / ISO process doc | **5%** | Transparency multiplier |
| P11-03 IAA threshold before scale | **3%** | Threshold values are task-specific |
| P11-09 Gold-set drift monitoring | **2%** | Operational QC |
| P11-10 Imperfect-oracle honesty | **(gate, not weight)** | Binary integrity constraint |

**Bundle weight suggestion for Opus synthesis:** assign **8–12%** of total audit composite to the ground-truth/corpus-construction dimension (co-owned with P09 metrics, P12 benchmarking, P16 calibration — do not double-count).

### Hard gates (§6.2 candidates)

1. **P11-07 failed** — implementers are sole annotators/adjudicators on calibration golden set, or test annotators not disjoint from golden-set creators (**non-compensatory**).
2. **P11-04 failed** — gate-bearing labels lack adjudication trail (silent majority vote on ambiguous extraction references).
3. **P11-06 failed** — calibration corpus is convenience sample with no stratum map while claiming WG21-wide coverage.
4. **P11-10 failed** — documentation claims "ground truth" where label metadata shows unresolved multi-annotator disagreement above pre-registered threshold without `uncertain` handling.

---

## 5. Sources

Tier legend per `00-FRAME.md` §4.

| Tier | Source | URL | Date/version |
|---|---|---|---|
| **1** | Klaus Krippendorff, *Content Analysis: An Introduction to Its Methodology* (4th ed.), Sage — especially Ch. 12 Reliability | https://doi.org/10.4135/9781071878781 | 2018 (4th ed.); α computing guide updated 2013 | 
| **1** | Krippendorff, "Computing Krippendorff's Alpha-Reliability" (UPenn ASC) | https://www.asc.upenn.edu/sites/default/files/2021-03/Computing%20Krippendorff%27s%20Alpha-Reliability.pdf | 2013-09-13 update |
| **1** | Kunilovskaya et al., "Who Annotates in NLP? A Large-scale Assessment of Human Annotation Reporting between 2018 and 2025" | https://arxiv.org/abs/2606.02255 | 2026 (arXiv v1) |
| **1** | Gebru et al., "Datasheets for Datasets," *Communications of the ACM* | https://doi.org/10.1145/3458723 | 2021; arXiv:1803.09010 |
| **1** | ISO/IEC 5259-4:2024, *Data quality for analytics and ML — Part 4: Data quality process framework* | https://www.iso.org/standard/81093.html | Published 2024-06 |
| **1** | Geva et al., "Are We Modeling the Task or the Annotator?" EMNLP-IJCNLP 2019 | https://aclanthology.org/D19-1107/ | 2019 |
| **1** | Afanador & Irvine, "Representativeness in the Benchmark for Vulnerability Analysis Tools (B-VAT)," USENIX CSET | https://www.usenix.org/system/files/cset20-paper-afanador_0.pdf | 2020 |
| **1** | W3C PROV-O: The PROV Ontology (Recommendation) | https://www.w3.org/TR/prov-o/ | REC 2013-04-30 |
| **1** | Klearman et al., "Coverage, Not Averages: Semantic Stratification for Trustworthy Retrieval Evaluation" | https://doi.org/10.48550/arxiv.2604.20763 | 2026 preprint |
| **2** | Baltes et al., "On the Creation of Representative Samples of Software Repositories" | https://arxiv.org/pdf/2410.00639 | 2024 |
| **2** | Hong et al., "Preference Leakage: A Contamination Problem in LLM-as-a-judge" | https://howiehwong.github.io/preference_leakage.pdf | 2024 |
| **2** | Di Eugenio & Glass, "The Kappa Statistic: A Second Look" | https://www.eecis.udel.edu/~carberry/CIS-885/Papers/DiEugenio-Kappa-Second-Look.pdf | 2004 |
| **2** | OASIS Data Provenance Metadata v1.0 (csd01) | https://docs.oasis-open.org/dps/prov-meta/v1.0/csd01/prov-meta-v1.0-csd01.pdf | OASIS CSD 2024 |
| **3** | Artstein & Poesio, inter-annotator agreement survey (cited in Kunilovskaya 2026) | (via Kunilovskaya related work) | 2008 |

**Source count:** **14 distinct Tier 1–2 primary sources** (9 Tier 1, 5 Tier 2). Tier 3 used only for contextual QC patterns, not as sole basis for any criterion.

**Contradictions surfaced:**

- **κ vs α:** NLP practice favors κ for historical reasons; Krippendorff and Di Eugenio & Glass show κ's prevalence/bias failure modes → audit prefers α for variable-rater extraction QA.
- **IAA vs accuracy:** High IAA does not imply correct labels → dual control with expert gold set (Krippendorff reliability ≠ validity).
- **Reporting vs practice:** Kunilovskaya et al. find training/adjudication/IAA often omitted in model-eval papers even when present in resource papers → audit treats omissions as **unknown quality**, not pass.

---

## 6. Overlap statement

This persona researched **external ground-truth and corpus-construction methodology only**.

**Avoided duplicating:**

- `packages/whisker/research/persona/` — especially the **ground-truth-provenance** code-level finding (whisker verdicts, evidence baseline scores). P11 supplies **audit criteria and external bar**, not a re-audit of whisker labels or golden files.
- `buildvsbuy/` — library/mechanism choice for metrics (TEDS, edit distance, etc.); P11 does not re-pick metric libraries (see P09 construct validity).
- `p12-benchmarking-methodology.md` territory — held-out splits, per-axis leaderboard integrity, tuning-on-holdout (P12 owns benchmark *reporting*; P11 owns label *construction* and corpus *sampling*).
- `p16-threshold-calibration.md` — ROC/operating-point fitting protocol once labels exist; P11 defines whether those labels are trustworthy enough to calibrate at all.
- `p10-llm-as-judge-eval.md` — judge bias science generally; P11 cites preference leakage only for **independence** (generator–judge separation), not full judge-validation methodology.

**Confirmation:** No whisker production code was opened. No whisker `file:line` citations. No whisker quality verdict. No code cloned or copied.

---

## Return metadata (for dispatch fan-in)

| Field | Value |
|---|---|
| **Tier 1–2 source count** | **14** (9 Tier 1, 5 Tier 2) |
| **Strongest criterion** | **P11-07 — Role independence (author ≠ annotator ≠ verifier ≠ evaluator)** |
| **Strongest-criterion rationale** | Without role separation, every other corpus-quality control (IAA, stratified sampling, adjudication) can be **self-confirming**: the same actor or model family defines, labels, and validates references, producing high agreement on a circular artifact rather than on extraction quality. Geva et al. (2019) show large generalization drops under annotator shift; Hong et al. (2024) show judge–generator relatedness bias. Independence is the only criterion that attacks the **epistemic absence of a perfect oracle** directly — it is therefore the recommended **hard gate**, not merely a weighted sub-score. |
