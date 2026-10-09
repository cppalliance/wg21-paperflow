# P15 — Weighted-Scoring & Rubric-Design Researcher

**Persona:** 15 (Cluster D — Audit frameworks, scoring & calibration)  
**Date:** 2026-07-18  
**Scope:** External method only. No whisker production-code inspection, no whisker verdict, no whisker `file:line` citations.

---

## 1. Question restated

How should the whisker professional-grade audit design a **defensible weighted composite** and a **conjunctive hard-gate layer** so that dimension weights express declared policy importance (not hidden trade-offs), compensatory masking cannot let a failed safety or fidelity dimension be offset by high packaging scores, and every weight assignment is traceable, sensitivity-tested, and rubric-reliable?

This persona feeds **§6.1** (weighted composite with declared dimensions and written rationale per weight) and **§6.2** (hard gates independent of the weighted score) in `00-FRAME.md`. It does **not** assign numeric weights (deferred to synthesis) and does **not** calibrate metric thresholds (P16) or grade evidence uncertainty (P17).

---

## 2. Proposed audit criteria

Each criterion below is a **design rule** the synthesis must enforce when building the whisker audit rubric. Tags: **AM** = audit method (§5); **SD** = scoring-design hook (§6).

### Criterion P15-1 — Declare compensability before choosing aggregation

| Field | Content |
|---|---|
| **Criterion** | Every scored dimension must be labeled **compensatory** (deficits may be offset by surpluses elsewhere in the composite) or **non-compensatory** (must be evaluated and gated separately). The synthesis must document this label before any weight is assigned. |
| **How to measure** | Review the rubric spec: each dimension has an explicit compensability flag; dimensions marked non-compensatory are excluded from the linear/geometric composite and routed to the hard-gate layer (§6.2). |
| **AM** | Maturity-model scoring (§5.2) + anti-Goodhart stress (§5.7) |
| **SD** | §6.1 (dimension decomposition), §6.2 (gate routing) |
| **Gaming vector** | Treating a safety-critical dimension as "weighted lower" instead of gated, letting a high release-readiness score mask a licensing or injection failure. |
| **Anti-gaming guard** | Non-compensatory dimensions cannot enter the weighted sum; they appear only as pass/fail gates with conjunctive verdict logic. |
| **Evidence grade** | **A** — converging Tier-1 OECD + JRC + peer-reviewed MCDA literature |
| **Sources** | OECD (2008) §1.6, §6.13; Munda & Nardo (2005) §2–3; Greco et al. (2019) §3 |

---

### Criterion P15-2 — Weight/importance vs weight/trade-off consistency

| Field | Content |
|---|---|
| **Criterion** | If weights are justified as **importance coefficients** ("security matters more than docs"), aggregation must **not** use standard linear or geometric compensatory sums; those methods make weights **trade-off ratios**, not importance (OECD 2008; Munda & Nardo 2005). The rubric must either (a) use non-compensatory / Condorcet-consistent aggregation for importance weights, or (b) explicitly document pairwise trade-offs and renounce "importance" language. |
| **How to measure** | Checklist: for each weight, the synthesis cites which meaning applies (importance vs trade-off) and names the matching aggregation family from OECD Table 4 (EW/PCA/AHP + linear/geometric vs NCMC/outranking). Flag any "importance" label paired with linear aggregation as **methodologically inconsistent**. |
| **AM** | Metric construct-validity audit (§5.4) applied to the scoring formula itself |
| **SD** | §6.1 (rationale per weight), §6.5 (contested criteria when methods disagree) |
| **Gaming vector** | Publishing weights that sound like priorities while mathematically allowing unlimited substitution (e.g., "determinism weight 30%" still lets 70% elsewhere compensate a replay failure). |
| **Anti-gaming guard** | Mandatory inconsistency flag in the rubric template; failed consistency blocks publication of a composite score until resolved. |
| **Evidence grade** | **A** |
| **Sources** | Munda & Nardo (2005) conclusions 1–4; OECD (2008) pp. 31–35, §6.13; Greco et al. (2019) on compensability critique |

**Contradiction surfaced:** AHP is often taught as an importance-elicitation method, but OECD (2008) §6.7 states AHP weights represent **trade-offs**, not importance coefficients, when used with compensatory aggregation. Resolution rule (§6.5): prefer the OECD/JRC measurement-theory line for composite construction; use AHP pairwise judgments as **documented trade-off elicitation**, or pair importance weights with NCMC/outranking (§6.13), not with a naive weighted sum.

---

### Criterion P15-3 — Participatory weight elicitation with consistency audit (AHP / budget allocation)

| Field | Content |
|---|---|
| **Criterion** | Weights must be derived through a **documented participatory protocol** (AHP pairwise comparison, budget allocation, or structured expert panel), not assigned by intuition. For AHP: record the comparison matrix, eigenvector weights, and **consistency ratio (CR)**; reject or revise judgments when CR > 0.10 (OECD cites Saaty 1980; 0.20 sometimes tolerated but must be justified). |
| **How to measure** | Rubric appendix contains: stakeholder roster, pairwise matrix or budget shares, CR or equivalent consistency metric, and sensitivity of ranks to ±10% weight perturbation. |
| **AM** | Maturity-model scoring (§5.2) + comparative benchmarking (§5.3) against OECD TAI exemplar workflow |
| **SD** | §6.1 (written rationale per weight) |
| **Gaming vector** | Retrofitting weights to a desired whisker verdict after the fact ("post-hoc tuning"). |
| **Anti-gaming guard** | Pre-register dimension list and elicitation protocol before any repo scoring; weight sensitivity must be reported (OECD Step 7). |
| **Evidence grade** | **A** |
| **Sources** | OECD (2008) §6.7, §1.7; Saaty (1980); Doerner et al. (2021) on pairwise thresholds in MCDA |

---

### Criterion P15-4 — Hard gates as veto / non-compensatory outranking

| Field | Content |
|---|---|
| **Criterion** | Candidate hard gates (licensing violation, prompt-injection at trust boundary, LLM hard-gating the deterministic path, refuted determinism claim, disproven metric used as gate) must use **non-compensatory decision logic**: a single gate failure blocks pass regardless of composite score. Model this with ELECTRE-style **veto thresholds** or explicit conjunctive rules: if performance on criterion *g* falls below veto level, alternative fails irrespective of other criteria (Doerner et al. 2021; OECD §6.13). |
| **How to measure** | For each proposed gate: (1) pass/fail predicate is binary and evidence-backed; (2) gate outcome is computed **before** composite aggregation; (3) documented proof that no weighted sum can override a gate failure. |
| **AM** | Conformance checklist (§5.1) for gate predicates + anti-Goodhart (§5.7) |
| **SD** | §6.2 (hard gates), §6.4 (anti-gaming) |
| **Gaming vector** | Redefining a gate as a low-weight dimension so partial credit preserves a "passing" composite. |
| **Anti-gaming guard** | Gates are **conjunctive** with the composite (00-FRAME §6.2); synthesis template includes a "gate override impossible" checklist item. |
| **Evidence grade** | **A** |
| **Sources** | OECD (2008) §1.6, §6.13; Figueira et al. (2013) on ELECTRE veto/discordance; Doerner et al. (2021) on veto thresholds |

---

### Criterion P15-5 — Never report composite alone; always show per-dimension scores

| Field | Content |
|---|---|
| **Criterion** | The audit rubric must **forbid** publishing a single headline score without simultaneous per-dimension (and where applicable per-sub-criterion) scores, decomposition charts, or traffic-light profiles (OECD §1.8). Composite is a summary index, not the verdict. |
| **How to measure** | Report template requires bar/spider/traffic-light decomposition alongside composite; any executive summary that omits dimension scores is non-conformant. |
| **AM** | Documentation-completeness audit (§5.9) applied to score reporting |
| **SD** | §6.1 (no single composite alone) |
| **Gaming vector** | Quoting one "audit score: 82/100" while hiding a failed sub-dimension. |
| **Anti-gaming guard** | Automated report validator rejects composite-only output. |
| **Evidence grade** | **B** — OECD handbook + FRAME §6.1 internal requirement |
| **Sources** | OECD (2008) §1.8; 00-FRAME.md §6.1 |

---

### Criterion P15-6 — Mandatory weight and aggregation sensitivity analysis

| Field | Content |
|---|---|
| **Criterion** | Before fixing weights, run **uncertainty and sensitivity analysis** across plausible weight schemes, aggregation methods (linear, geometric, NCMC), and normalization choices; report which inputs most shift ranks or verdict bands (OECD Step 7; Greco et al. 2019 on robustness). |
| **How to measure** | Document: (1) ≥2 alternative weighting methods compared (e.g., equal vs AHP vs budget allocation); (2) Sobol or rank-stability analysis identifying top influential weights; (3) verdict band width when contested weights vary within elicitation uncertainty. |
| **AM** | Calibration / operating-point audit (§5.5) applied to **scoring** thresholds, not metric gates |
| **SD** | §6.6 (score uncertainty band, flip conditions) |
| **Gaming vector** | Cherry-picking the weight scheme that flatters whisker while claiming "evidence-based weights." |
| **Anti-gaming guard** | Multi-modelling principle (OECD): report range across schemes; synthesis must not adopt a single scheme without showing stability or naming instability drivers. |
| **Evidence grade** | **A** |
| **Sources** | OECD (2008) §1.7, Step 7; Greco et al. (2019) §5 on robustness; Saisana et al. (2005) cited in OECD |

---

### Criterion P15-7 — Analytic rubric with bounded ordinal levels and rater calibration

| Field | Content |
|---|---|
| **Criterion** | Per-dimension sub-criteria use an **analytic rubric** (separate score per criterion, not one holistic judgment) with **3–5 ordinal levels** (0–4 maturity aligned with P14) and **concrete level descriptors** (observable behaviors, not adjectives like "good"). Before audit execution, run **rater calibration** with exemplar cases; target inter-rater reliability (ICC or equivalent) on pilot samples (Jonsson & Svingby 2007; HEQCO 2020). |
| **How to measure** | Rubric rows have parallel wording across levels; pilot scoring yields documented IRR/ICC; descriptors pass the test "would two independent raters assign the same level?" (Moskal & Leydens 2000). |
| **AM** | Maturity-model scoring (§5.2) |
| **SD** | §6.1 (level descriptors), §6.3 (confidence tied to rater agreement) |
| **Gaming vector** | Vague level text ("adequate tests") letting raters inflate scores without evidence. |
| **Anti-gaming guard** | Each level cites required evidence artifacts; ambiguous rows fail rubric QA until rewritten. |
| **Evidence grade** | **A** |
| **Sources** | Jonsson & Svingby (2007); Moskal & Leydens (2000); HEQCO (2020) |

---

### Criterion P15-8 — No dictator dimension (weight cap)

| Field | Content |
|---|---|
| **Criterion** | No single dimension weight may exceed **50%** of the composite total; no dimension group may exceed 50% when sub-dimensions are nested (Munda 2005b via OECD §6.13). Prevents lexicographic "one dimension decides all." |
| **How to measure** | Weight vector sum check; flag any wi > 0.5 or grouped dimension sum > 0.5. |
| **AM** | Conformance checklist (§5.1) |
| **SD** | §6.1 |
| **Gaming vector** | Collapsing the entire audit into "extraction quality = 80%" by weighting one axis at 70%+. |
| **Anti-gaming guard** | Automated normalization rejects weight vectors violating cap unless explicitly approved as a **contested** non-standard model (§6.5) with steelman recorded. |
| **Evidence grade** | **B** — OECD §6.13 citing Munda (2005b); social-choice grounding |
| **Sources** | OECD (2008) §6.13; Munda & Nardo (2007) |

---

### Criterion P15-9 — Flip-condition register for weights and gates

| Field | Content |
|---|---|
| **Criterion** | The rubric spec must list **flip conditions**: which single criterion re-grade or weight change would move the overall verdict across a band boundary (00-FRAME §6.6). Tie to sensitivity analysis (P15-6). |
| **How to measure** | Published table: criterion ID, current grade, weight, marginal effect on composite, gate interaction, verdict if flipped. |
| **AM** | Confidence / evidence grading (§5.12) + anti-Goodhart (§5.7) |
| **SD** | §6.6 |
| **Gaming vector** | Hiding that the audit verdict rests on one contested sub-score. |
| **Anti-gaming guard** | Flip conditions mandatory in synthesis output; high-leverage contested criteria trigger lowered confidence (§6.3). |
| **Evidence grade** | **B** — FRAME §6.6 + OECD sensitivity practice |
| **Sources** | OECD (2008) §1.7; 00-FRAME.md §6.6 |

---

### Criterion P15-10 — Equal-weighting is explicit, not default lazy choice

| Field | Content |
|---|---|
| **Criterion** | Equal weighting (EW) is permitted only when accompanied by a **written justification** that all dimensions are equally policy-relevant *and* compensability is acceptable (OECD: EW "does not mean no weights" but implies equal worth). If dimensions differ in salience or compensability, EW is **contested** (§6.5). |
| **How to measure** | If EW used: rationale paragraph + sensitivity showing rank stability vs AHP/BAP alternative. |
| **AM** | Comparative benchmarking (§5.3) |
| **SD** | §6.1, §6.5 |
| **Gaming vector** | EW to avoid documenting controversial priorities (e.g., down-weighting security without stating so). |
| **Anti-gaming guard** | Default in template is "must justify aggregation choice"; EW requires sign-off. |
| **Evidence grade** | **A** |
| **Sources** | OECD (2008) §1.6; Greco et al. (2019) |

---

## 3. External benchmark / exemplar bar

Serious composite-index and audit-rubric practice meets **all** of the following (synthesized from OECD/JRC/MCDA/eval-measurement sources):

| Bar | Exemplar behavior | Whisker audit implication |
|---|---|---|
| **Transparency** | OECD 10-step checklist: theoretical framework, weighting, aggregation, sensitivity documented (OECD 2008) | Rubric spec is publishable; every weight traceable to elicitation or explicit trade-off |
| **Compensability honesty** | UNDP HDI moved from linear to geometric (2010) to reduce **perfect substitution** across dimensions (Greco et al. 2019); JRC insists importance weights need non-compensatory rules (Munda & Nardo 2005) | Hybrid audit: compensatory composite for *maturity progression*; **non-compensatory gates** for fidelity/security/licensing |
| **Weight stability** | OECD TAI shows country ranks shift materially across EW, FA, BAP, AHP (Table 22–23) — responsible indices report this | Whisker synthesis must show verdict stability band, not one number |
| **Gate semantics** | ELECTRE family: veto threshold blocks outranking regardless of concordance elsewhere (Figueira et al. 2013) | Mirror whisker's conjunctive guard/anchor/facts design at the **audit-meta** level |
| **Rubric reliability** | Analytic, topic-specific rubrics + rater training improve scoring consistency (Jonsson & Svingby 2007) | Stage-1 auditors calibrate on golden exemplar repos before scoring whisker |
| **Sensitivity** | Sobol/variance-based analysis identifies influential assumptions (OECD §1.7) | Weight uncertainty propagates to §6.6 score band |

**Two-layer scoring architecture (recommended external pattern):**

```
Layer A — Weighted maturity composite (compensatory OK within declared bounds)
  → ordinal 0–4 per dimension → explicit weights → sensitivity-tested sum
  → always decomposed; never headline-only

Layer B — Hard gates (non-compensatory, conjunctive)
  → veto / pass-fail predicates evaluated first
  → any failure → overall FAIL regardless of Layer A
```

This pattern resolves the core OECD/JRC tension: stakeholders want **importance-weighted** priorities (Layer A) without letting those weights **mask** non-negotiable failures (Layer B).

---

## 4. Recommended weight & hard-gate treatment (rationale for synthesis)

Numeric weights are **deferred** (00-FRAME §10). This persona recommends **structural** rules the Opus synthesis must follow when assigning numbers:

### 4.1 Dimension weighting (Layer A)

| Recommendation | Rationale |
|---|---|
| Use **AHP or budget allocation** with documented CR/consistency checks to elicit initial weights across the ~10 FRAME §6.1 candidate dimensions | Participatory methods are OECD-endorsed; beat opaque equal weighting when dimensions differ in policy salience |
| Run **≥3 weight schemes** (EW, participatory, one robustness variant) and report rank/verdict stability | OECD Step 7; prevents single-scheme manipulation |
| Cap any dimension at **≤50%** | Avoid dictator dimension (OECD §6.13 / Arrow) |
| Prefer **modest compensability** within Layer A only (geometric aggregation *if* trade-offs are explicitly accepted) OR keep linear but **lower weights** on dimensions partially covered by gates | Geometric reduces but does not eliminate substitution (Greco et al. 2019); gates carry non-negotiable load |
| **Do not** claim weights mean "importance" if using linear sum without gates | Munda & Nardo (2005) theoretical inconsistency otherwise |

**Illustrative weight *process* (not fixed numbers):** Clusters B+C (architecture, determinism, extraction/eval) likely draw **higher elicited importance** for a QA-tool audit than packaging polish, but exact ratios must come from documented AHP/BAP, not persona assertion.

### 4.2 Hard gates (Layer B) — recommend gate, not weight

| Candidate gate (from 00-FRAME §6.2) | Gate vs weight |
|---|---|
| Licensing / attribution violation | **Gate** — legal/provenance failure is non-substitutable (NCMC logic) |
| Prompt-injection hole at trust boundary | **Gate** — ELECTRE veto analog; security deficit cannot be traded for docs score |
| LLM signal hard-gating deterministic path | **Gate** — hybrid architecture non-compensatory requirement |
| Determinism claim refuted by replay | **Gate** — replay failure is veto, not partial credit |
| Disproven construct validity on a metric used as gate | **Gate** — invalid metric must not contribute to pass |

Everything else (release cadence, doc completeness, CI maturity, observability depth) remains **weighted maturity** unless later evidence elevates it to gate status.

### 4.3 Verdict rule

```
IF any Layer B gate fails → FAIL (stop)
ELSE IF Layer A composite ∈ [pass band] AND sensitivity band stable → PASS / conditional pass
ELSE → IMPROVE (with decomposition + flip conditions)
```

---

## 5. Sources

| Tier | Source | URL / identifier | Date | Role |
|---|---|---|---|---|
| **T1** | OECD/JRC, *Handbook on Constructing Composite Indicators: Methodology and User Guide* | https://www.oecd.org/content/dam/oecd/en/publications/reports/2008/08/handbook-on-constructing-composite-indicators-methodology-and-user-guide_g1gh9301/9789264043466-en.pdf | 2008 | Compensability, AHP, NCMC, sensitivity, decomposition |
| **T1** | Munda, G. & Nardo, M., *Constructing Consistent Composite Indicators: the Issue of Weights* (EUR 21834 EN) | https://publications.jrc.ec.europa.eu/repository/bitstream/JRC32434/EUR%2021834%20EN.pdf | 2005 | Importance vs trade-off inconsistency; Condorcet rules |
| **T1** | Greco, S. et al., "On the Methodological Framework of Composite Indices…" *Soc Indic Res* | https://doi.org/10.1007/s11205-017-1832-9 | 2018 (online 2017) | Weight/aggregation/robustness review; HDI compensability |
| **T1** | Jonsson, A. & Svingby, G., "The use of scoring rubrics…" *Educational Research Review* | https://doi.org/10.1016/j.edurev.2007.05.002 | 2007 | Rubric reliability, analytic rubrics, rater training |
| **T1** | Saaty, T. L., *The Analytic Hierarchy Process* | McGraw-Hill / RWS (canonical text); CR rule cited OECD §6.7 | 1980 | Pairwise weight elicitation, consistency ratio |
| **T1** | Figueira, J. et al., "An Overview of ELECTRE Methods…" *EJOR* / Wiley MCDA | https://doi.org/10.1002/mcda.1482 | 2013 | Veto thresholds, non-compensatory outranking |
| **T1** | Doerner, A. et al., "How to support the application of MCDA? A comprehensive taxonomy" | https://pmc.ncbi.nlm.nih.gov/articles/PMC7970504/ | 2021 | Veto/indifference/preference thresholds in MCDA |
| **T2** | Moskal, B. & Leydens, J., "Scoring Rubric Development: Validity and Reliability" | https://openpublishing.library.umass.edu/pare/article/1398/ | 2000 | Inter/intra-rater reliability, descriptor clarity |
| **T2** | HEQCO, *Guide to Developing Valid and Reliable Rubrics* | https://heqco.ca/wp-content/uploads/2020/06/Formatted_Rubric-Guide_FINAL.pdf | 2020 | IRR/ICC practice, phased rubric validation |

**Source count:** **9 distinct Tier 1–2 primary sources** (7 Tier 1, 2 Tier 2).

**Contradictions surfaced:**
- **AHP as importance vs trade-off:** Saaty frames pairwise judgments as relative importance; OECD §6.7 warns against interpreting AHP weights as importance coefficients under compensatory aggregation. **Resolution:** use AHP for structured elicitation with CR checks, but pair with explicit compensability declaration (P15-1) and gates (P15-4).
- **PROMETHEE vs ELECTRE compensability:** PROMETHEE compensation depends on preference functions (Dejaegere & De Smet 2023); ELECTRE veto is stricter. **Resolution:** prefer explicit conjunctive gates for audit meta-scoring; do not rely on outranking parameter tuning alone.

---

## 6. Overlap statement

This persona researched **external weighted-scoring and rubric-design method only**. It did **not**:

- inspect or score whisker production code;
- clone, fork, or copy whisker or exemplar repo code;
- duplicate **P14** (`p14-audit-frameworks-maturity.md` — maturity ladder skeleton);
- duplicate **P16** (threshold calibration / ROC operating points on labeled data);
- duplicate **P17** (GRADE-style evidence grading and score bands — though P15-6/P15-9 feed inputs to §6.6);
- duplicate **P19** (Goodhart gaming catalog — though compensability masking is related, P15 focuses on **weighting algebra**, P19 on **metric gaming**);
- duplicate **P30** (eval-framework case-study scoring patterns).

**Prior folders avoided:** `persona/`, `llm-stack/`, `buildvsbuy/`, `redteam/`, `langextract/` code-level verdicts. This file hands the synthesis **weighting + hard-gate design rules** for §6.1–6.2, not a whisker score.

---

**Strongest criterion (persona assessment):** **P15-2 — Weight/importance vs weight/trade-off consistency**, backed by Munda & Nardo (2005) and OECD (2008), because most composite audit rubrics silently use linear weighted sums while claiming weights reflect "priority," which **mathematically guarantees compensatory masking** — the exact failure mode a professional-grade whisker audit must prevent.
