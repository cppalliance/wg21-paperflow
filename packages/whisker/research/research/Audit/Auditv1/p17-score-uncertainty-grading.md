# P17 — Score-Uncertainty & Evidence-Grading Researcher

**Persona:** 17 of 30 (Cluster D: Audit frameworks, scoring & calibration)  
**Date:** 2026-07-18  
**Scope:** External method and standards only. No whisker production-code inspection.  
**Feeds:** `00-FRAME.md` §6.3 (confidence and evidence grades) and §6.6 (score uncertainty).

---

## 1. Question restated

How should the whisker professional-grade audit **express uncertainty in its composite score** and **grade the evidence behind each finding**? This persona researches external precedents for: evidence-grading systems (GRADE-style certainty ratings), confidence levels in assessment reporting, propagating the weakest evidence grade through load-bearing inputs, reporting a **score band** rather than a single point, and **sensitivity / flip-condition** analysis that names which criterion re-grade would move the verdict across a boundary. Output is audit criteria and design rules for the synthesis stage, not a whisker score.

---

## 2. Proposed audit criteria

Each criterion below is scored on a **0–4 maturity ladder** for *whether the audit rubric itself implements the rule*, unless marked as a **meta-requirement** (mandatory shape of the scoring system). Evidence grades for this persona's recommendations follow `00-FRAME.md` §6.3: **A** = multiple Tier-1 corroborating; **B** = single Tier-1 or converging Tier-2; **C** = Tier-3 only or contested; **D** = Tier-4/speculative.

### Criterion G1 — Source-tier → evidence-grade mapping (hard meta-requirement)

| Field | Value |
|---|---|
| **Criterion** | Every audit finding and sub-criterion score carries an explicit **evidence grade (A/B/C/D)** mapped from the source hierarchy in `00-FRAME.md` §4, with stable URL + date/version on every load-bearing citation. |
| **How to measure** | For each finding in the synthesis report: verify grade assignment table exists; each A/B grade traces to ≥1 Tier-1 or Tier-2 source with URL and version; C/D findings are flagged and excluded from load-bearing composite inputs unless upgraded. |
| **Audit method** | Confidence / evidence grading of findings (§5.12) + conformance checklist (§5.1) |
| **Scoring hook** | **§6.3** — defines the evidence-grade alphabet the synthesis must use |
| **Gaming vector** | Bulk-assigning grade **A** to criteria backed only by blog posts; citing Tier-4 forums without Tier-1/2 primary underneath. |
| **Anti-gaming guard** | Synthesis template requires per-criterion citation list with tier tag; automated lint rejects findings with grade A/B but zero Tier-1/2 URLs; spot-audit 10% of grades. |
| **Evidence grade** | **A** |
| **Sources** | `00-FRAME.md` §4; GRADE Handbook (S1); Cochrane Handbook Ch.14 (S3) |

### Criterion G2 — Per-finding evidence profile with downgrade domains

| Field | Value |
|---|---|
| **Criterion** | Each load-bearing finding includes a structured **evidence profile** listing: (a) sources consulted with tier, (b) **downgrade domains** applied (adapted from GRADE: risk of bias / study limitations, inconsistency across sources, indirectness to whisker's domain, imprecision / thin evidence, publication or selection bias), (c) net certainty after downgrades, (d) one-sentence justification per domain touched. |
| **How to measure** | Sample N=20 findings across dimensions; count profiles with all four fields populated; verify downgrade domains cite explicit signals (e.g. "inconsistency: P09 TEDS validity vs P12 benchmark method disagree on table-only papers"). |
| **Audit method** | Confidence / evidence grading (§5.12) + metric construct-validity audit overlap (§5.4) |
| **Scoring hook** | **§6.3** — makes grading auditable, not adjective-only |
| **Gaming vector** | Empty profile with grade **B** copied from a persona header; listing domains as "none" without checking cross-persona disagreement. |
| **Anti-gaming guard** | §6.5 disagreement rule: contested sources force **inconsistency** downgrade; synthesis must record both positions before assigning grade. |
| **Evidence grade** | **A** |
| **Sources** | Core GRADE 1 BMJ 2024 (S2); GRADE Handbook Ch. Quality of evidence (S1); Cochrane Handbook §14.2.2 (S3) |

**Adaptation note (not a contradiction):** GRADE's four certainty levels (high / moderate / low / very low) map to whisker's A/B/C/D **evidence grades** for *audit evidence*, not to clinical effect estimates. GRADE's five downgrade domains transfer directly as *audit-evidence quality factors*; upgrade domains (large effect, dose-response) apply only when an exemplar shows an overwhelming, replicated engineering practice (e.g. OpenSSF Scorecard adopted by >100 orgs) and must be justified in the profile.

### Criterion G3 — Confidence level (high / medium / low) separate from evidence grade

| Field | Value |
|---|---|
| **Criterion** | Each finding carries a **confidence** label (high / medium / low) reflecting **source agreement** and **directness** of evidence to the measured property, explicitly **separated** from the evidence grade (mirroring GRADE's separation of certainty in effect estimates from strength of recommendations). |
| **How to measure** | Operational definitions enforced: **High** = ≥2 independent Tier-1/2 sources agree on direction and no Tier-1 contradiction unresolved; **Medium** = single Tier-1 or converging Tier-2, or resolved minor contradiction; **Low** = Tier-3 backbone, single secondary source, or unresolved Tier-1 disagreement. |
| **Audit method** | Confidence / evidence grading (§5.12) |
| **Scoring hook** | **§6.3** — confidence feeds band width in §6.6 |
| **Gaming vector** | Conflating "we like the answer" with high confidence; marking high confidence when only one persona supplied the criterion. |
| **Anti-gaming guard** | Confidence cannot exceed the highest agreement class supported by citation count; unresolved §6.5 contests cap confidence at **low** regardless of grade. |
| **Evidence grade** | **A** |
| **Sources** | GRADE Handbook §1.2 separation of confidence and recommendation strength (S1); Core GRADE 1 (S2); NIST SP 800-30 Rev.1 on documenting confidence in assessment results (S5) |

### Criterion G4 — Weakest-link propagation for composite and gates (hard meta-requirement)

| Field | Value |
|---|---|
| **Criterion** | The composite dimension score and overall audit verdict **inherit the weakest evidence grade** among **load-bearing** inputs (sub-criteria marked critical, hard gates, and any criterion whose failure would flip a dimension pass line). Formally: `composite_evidence_grade = min(critical_input_grades)` using order A > B > C > D. |
| **How to measure** | Recompute composite grade from per-criterion grades; verify matches reported grade; verify no gate passes with grade **D** evidence; verify a single **C** load-bearing input on a security/determinism gate triggers explicit "conditional pass" wording. |
| **Audit method** | Confidence / evidence grading (§5.12) + maturity-model scoring (§5.2) |
| **Scoring hook** | **§6.3** — "an audit is only as strong as its shakiest gate" |
| **Gaming vector** | Averaging grades across criteria; excluding weak sub-criteria from the min() set by reclassifying them as "informational" post hoc. |
| **Anti-gaming guard** | Pre-register **critical vs important** labels per dimension before scoring (GRADE "critical outcomes" analogue); changing labels after scores requires documented §6.5 review. |
| **Evidence grade** | **A** |
| **Sources** | GRADE Handbook — lowest critical outcome determines overall quality (S1); Cochrane Handbook Ch.14 overall certainty (S3); `00-FRAME.md` §6.3 weakest-link rule |

**GRADE precedent (direct quote, paraphrased):** When quality differs across critical outcomes, overall confidence cannot exceed the **lowest** confidence among critical outcomes (GRADE Handbook; Cochrane Ch.14). The whisker audit applies the same logic to critical **criteria** instead of patient outcomes.

**Documented exception (must be explicit, rare):** GRADE allows a critical outcome to become non-critical if the recommendation would not change across its effect range (statins / coronary mortality example, S1). The audit may apply the same exception only when a formal **decision-invariance note** proves re-grading the weak criterion cannot change the dimension verdict.

### Criterion G5 — Critical vs important criterion registry

| Field | Value |
|---|---|
| **Criterion** | Before scoring, each sub-criterion is labeled **critical** (load-bearing for verdict or gate) or **important** (reported, weighted, but not in weakest-link min-set). Registry is frozen before code audit stage. |
| **How to measure** | Registry file/table exists; 100% of hard gates (§6.2) marked critical; ≥90% of weighted sub-criteria have label; post-hoc relabeling count = 0 without §6.5 entry. |
| **Audit method** | Maturity-model / capability-level scoring (§5.2) + confidence grading (§5.12) |
| **Scoring hook** | **§6.3** — defines the min-set for propagation; **§6.2** gates must all be critical |
| **Gaming vector** | Marking a weak-evidence dimension "important" after seeing its grade to keep composite at A. |
| **Anti-gaming guard** | Critical set must include all §6.2 gates plus any criterion tagged "hard gate candidate" by any persona; changes require synthesis lead sign-off with written rationale. |
| **Evidence grade** | **B** |
| **Sources** | GRADE critical vs important outcomes (S1); `00-FRAME.md` §6.2–6.3 |

### Criterion U1 — Composite reported as score band, not point (hard meta-requirement)

| Field | Value |
|---|---|
| **Criterion** | The overall and per-dimension composite scores are reported as a **band** `[L, U]` on the 0–100 (or 0–4 maturity) scale, never as a lone point. Band width derives from documented uncertainty sources (below). |
| **How to measure** | Final synthesis report shows `score = 72 [68, 76]` or maturity `3 [2, 3]`; every band lists **named drivers**; point-only headline absent from executive summary. |
| **Audit method** | Confidence / evidence grading (§5.12) + weighted composite design (§5.2, feeds from P15) |
| **Scoring hook** | **§6.6** — primary deliverable |
| **Gaming vector** | Reporting band so narrow it is cosmetic (±0.1) without citing drivers; showing band in appendix only while headline uses point. |
| **Anti-gaming guard** | Minimum band width rules: each **C**-graded load-bearing input widens band by ≥1 maturity level or ≥5 composite points; each **low-confidence** critical criterion widens by same increment; bands narrower than minimum require written waiver citing direct remeasurement. |
| **Evidence grade** | **A** |
| **Sources** | OECD/JRC Composite Indicators Handbook Step 7 — accompany scores with uncertainty bounds (S4); Saltelli et al. 2005 JRSS (S6); `00-FRAME.md` §6.6 |

**Band construction protocol (recommended for synthesis):**

1. Compute point composite from weighted ordinal scores (P15).
2. Initialize band = point ± 0.
3. For each load-bearing input with evidence grade **C**, expand band outward one discrete step on that dimension's scale.
4. For each **low-confidence** critical input, same expansion.
5. For each **contested** criterion (§6.5), expand band and keep criterion score as range `{low, high}` until resolved.
6. Report `[L, U]` and list drivers in descending contribution to width.

### Criterion U2 — Uncertainty source enumeration (mandatory disclosure)

| Field | Value |
|---|---|
| **Criterion** | Every band is accompanied by an **uncertainty ledger** listing: contested criteria (§6.5), low-confidence inputs, uncalibrated thresholds (P16 pending), thin-evidence dimensions (grade C/D), and weight-sensitivity flags (P15). |
| **How to measure** | Ledger row count ≥ number of band drivers; each row links to criterion ID + persona source; empty ledger only if all load-bearing inputs are grade A/B with high confidence (explicit statement required). |
| **Audit method** | Confidence / evidence grading (§5.12) |
| **Scoring hook** | **§6.6** — names what drives uncertainty |
| **Gaming vector** | Generic boilerplate ("some uncertainty exists") without criterion IDs. |
| **Anti-gaming guard** | Template requires criterion IDs; synthesis reviewer rejects ledgers with >0 band width but <1 row. |
| **Evidence grade** | **A** |
| **Sources** | OECD Handbook Step 7 — identify all uncertainty sources (S4); NIST SP 800-30 — document assumptions, limitations, confidence (S5) |

### Criterion U3 — Sensitivity / flip-condition analysis (hard meta-requirement)

| Field | Value |
|---|---|
| **Criterion** | The synthesis publishes a **flip-condition table**: for each verdict boundary (fail → conditional pass → pass; or maturity level k → k+1), the **single criterion** whose re-grade or ±1 level change would cross the boundary, plus any **multi-flip** pairs if no single flip exists. |
| **How to measure** | Table covers overall verdict and each dimension pass line; each row validated by recomputing composite with perturbed input; at minimum **one-at-a-time** sensitivity (OAT) documented; ideally variance-based sensitivity indices for top-3 weight uncertainties (OECD/Saltelli). |
| **Audit method** | Confidence / evidence grading (§5.12) + anti-Goodhart stress (§5.7) overlap with P19 |
| **Scoring hook** | **§6.6** — flip conditions |
| **Gaming vector** | Cherry-picking flip conditions that make the audit look stable while hiding a fragile gate; reporting only dimension flips, not overall verdict flips. |
| **Anti-gaming guard** | Mandatory overall-verdict row; if OAT shows no single flip, report **minimal flip set** (smallest criterion set whose joint upgrade crosses boundary); gate failures listed first. |
| **Evidence grade** | **A** |
| **Sources** | OECD Handbook §7 sensitivity analysis of inference (S4); Saltelli et al. 2005 — first-order sensitivity indices (S6); JRC Composite Indicators Toolkit Step 8 (S7) |

**Flip-condition algorithm (OAT minimum):**

```
for each critical criterion c:
  temporarily set score(c) to best plausible re-grade
  recompute composite and gate conjunction
  if verdict class changes: record c as flip candidate
  restore score(c)
report smallest |c| or |{c}| that changes verdict
```

### Criterion U4 — Verdict class uses band overlap, not point threshold

| Field | Value |
|---|---|
| **Criterion** | Final whisker verdict (pass / conditional / fail) is determined by **where the band overlaps** pass thresholds, not by the point alone: if `[L, U]` straddles a boundary, verdict is **conditional** with flip table attached. |
| **How to measure** | Three worked examples in synthesis appendix; no case where point is pass but U < pass threshold without conditional verdict; gate failure forces fail regardless of band (§6.2 conjunctive rule preserved). |
| **Audit method** | Maturity-model scoring (§5.2) + confidence grading (§5.12) |
| **Scoring hook** | **§6.6** + **§6.2** gate conjunction |
| **Gaming vector** | Using point score to claim pass when band lower bound is below threshold. |
| **Anti-gaming guard** | Verdict function documented in rubric: `if any_gate_fail: FAIL; elif L >= pass_line: PASS; elif U < pass_line: FAIL; else: CONDITIONAL`. |
| **Evidence grade** | **B** |
| **Sources** | OECD uncertainty bounds on ranks (S4); NIST SP 800-30 qualitative bands and annotation (S5); `00-FRAME.md` §6.2–6.6 |

### Criterion U5 — Imprecision analogue for calibration-pending metrics

| Field | Value |
|---|---|
| **Criterion** | Any sub-criterion depending on **uncalibrated or borrowed thresholds** (P16 protocol not yet executed on whisker labels) is automatically graded evidence **≤ C**, confidence **low**, and forces minimum band width until calibration TPR/FPR are recorded. |
| **How to measure** | All gate thresholds traced to calibration record or flagged; flagged criteria appear in uncertainty ledger; composite band width includes +1 step for each uncalibrated load-bearing gate. |
| **Audit method** | Calibration / operating-point audit (§5.5) + confidence grading (§5.12) |
| **Scoring hook** | **§6.3** downgrade + **§6.6** band width |
| **Gaming vector** | Treating default named constants as calibrated because documented in CLAUDE.md without labeled corpus fit. |
| **Anti-gaming guard** | P16 calibration artifact (N, TPR, FPR, date) required to upgrade above C; until then threshold satisfies gate mechanics but not evidence grade. |
| **Evidence grade** | **A** |
| **Sources** | Core GRADE 2 — imprecision / CI crossing threshold (S8); `00-FRAME.md` §6.3, §10 open calibration question; Cochrane §14 imprecision domain (S3) |

---

## 3. External benchmark / exemplar bar

### GRADE / Cochrane (evidence certainty and weakest-link)

The global standard for transparent evidence grading treats certainty as **confidence that the true effect lies on one side of a threshold or within a range** (Core GRADE 1, 2024). Certainty is rated **per outcome**, then combined for decisions using explicit rules: among **critical** outcomes, the **lowest** certainty sets the ceiling for overall certainty unless a formal decision-invariance exception applies (GRADE Handbook; Cochrane Ch.14). Five **downgrade domains** (risk of bias, inconsistency, indirectness, imprecision, publication bias) are applied with structured justification; upgrades are rare and rule-bound.

**Transfer to whisker audit:** Each rubric sub-criterion is an "outcome"; critical sub-criteria are "critical outcomes"; overall audit certainty and composite evidence grade obey the same weakest-link logic. Confidence (high/medium/low) stays separate from evidence grade, as GRADE separates certainty from recommendation strength.

### OECD / JRC composite indicators (score bands and sensitivity)

The OECD/JRC *Handbook on Constructing Composite Indicators* (2008, still cited as methodological standard) requires constructors to **identify all uncertainty sources** and **accompany composite scores and ranks with uncertainty bounds**, plus conduct **sensitivity analysis of the inference** to show which assumptions most move scores/ranks (Step 7). Saltelli et al. (2005) demonstrate combined uncertainty + variance-based sensitivity analysis on composite indices, reporting how much each input uncertainty source contributes to output variance and rank shifts.

**Transfer to whisker audit:** The weighted audit composite is a composite indicator; professional bar is **band + ledger + sensitivity**, not a leaderboard point. Flip-condition analysis is the audit's OAT/minimal-set analogue to OECD rank-stability analysis.

### NIST SP 800-30 Rev.1 (assessment confidence documentation)

NIST SP 800-30 Rev.1 cautions that assessments reflect methodology limits, data quality, and expert judgment; assessors must **annotate ratings with rationale** and communicate **confidence in results**, assumptions, and limitations so decision makers interpret scores correctly. Qualitative/semi-quantitative scales are acceptable when bins are well-defined and documented.

**Transfer to whisker audit:** Even a qualitative 0–4 maturity composite requires explicit confidence statements and limitation ledgers, not false numeric precision.

### Exemplar bar (synthesis-level)

A defensible whisker audit report matches **GRADE-level** per-finding profiles and weakest-link propagation for critical criteria, **OECD-level** band + sensitivity reporting for the composite, and **NIST-level** confidence/limitations disclosure. Falling short on any of the three is a maturity defect in the **audit rubric itself**, independent of whisker's code quality.

---

## 4. Recommended weight & gate recommendation

| Recommendation | Rationale |
|---|---|
| **Meta-requirement cluster (not a weighted dimension)** | G1, G4, U1, U3 are **shape constraints** on the scoring system (§6.3, §6.6); they are not weighted sub-criteria but **mandatory** for synthesis acceptance. |
| **Dimension weight: 8%** of composite under "scoring-system integrity" (shared with P14 frameworks, P15 weighting, P16 calibration) | Uncertainty grading is cross-cutting; it modifies interpretation of all other dimensions rather than measuring whisker code directly. Weight reflects OECD/OECDD emphasis: without uncertainty analysis, composite indicators mislead regardless of other quality. |
| **Hard gates (conjunctive on the audit report, not whisker code)** | **G4 + U1 + U3**: synthesis rejected if composite is point-only, lacks weakest-link recomputation, or lacks flip-condition table. **G1**: any load-bearing finding with grade A/B but zero Tier-1/2 citation fails synthesis QA. |
| **Evidence propagation** | Scoring-system integrity dimension inherits **min** grade across G1–G5 and U1–U5 implementation checks; expected **A** if synthesis follows this persona. |
| **Interaction with P15 / P16** | P15 supplies weights; P16 supplies calibrated thresholds. P17 widens bands until P16 artifacts exist (U5). P19 anti-Goodhart rules constrain gaming of bands. |
| **Contested criteria** | Apply §6.5: contested inputs widen band, cap confidence at low, and appear in flip table even if point score unchanged. |

---

## 5. Sources

### Tier 1 — Authoritative / primary

| ID | Source | URL | Date/version |
|---|---|---|---|
| S1 | GRADE Handbook (GRADEpro) | https://gradepro.org/handbook/ | Updated through 2013 base; integrated in GRADEpro GDT (accessed 2026-07-18) |
| S2 | Core GRADE 1: overview of the Core GRADE approach (BMJ) | https://www.bmj.com/content/389/bmj-2024-081903 | 2024 |
| S3 | Cochrane Handbook Ch.14 — Summary of findings tables and grading certainty | https://www.cochrane.org/authors/handbooks-and-manuals/handbook/current/chapter-14 | Handbook v6.5, 2024 |
| S4 | OECD/JRC — Handbook on Constructing Composite Indicators: Methodology and User Guide | https://www.oecd.org/en/publications/handbook-on-constructing-composite-indicators_533411815016.html | 2008 (ISBN 978-92-64-04345-9) |
| S5 | NIST SP 800-30 Rev.1 — Guide for Conducting Risk Assessments | https://csrc.nist.gov/publications/detail/sp/800-30/rev-1/final | September 2012 |
| S6 | Saltelli, Saisana, Tarantola — Uncertainty and sensitivity analysis techniques as tools for the quality assessment of composite indicators (JRSS-C) | https://www.andreasaltelli.eu/file/repository/JRSS_2005.pdf | 2005; DOI 10.1002/sta4.2005.01004 |
| S7 | European Commission JRC — Composite Indicators Toolkit, Step 8: Sensitivity analysis | https://knowledge4policy.ec.europa.eu/composite-indicators/toolkit_en/navigation-page/10-step-guide_en/step-8-sensitivity-analysis_en | Toolkit v2021+ |
| S8 | Core GRADE 2: choosing the target of certainty rating and assessing imprecision (BMJ) | https://www.bmj.com/content/389/bmj-2024-081904 | 2024 |
| S9 | Hultcrantz et al. — The GRADE Working Group clarifies the construct of certainty of evidence | https://doi.org/10.1016/j.jclinepi.2017.03.013 | J Clin Epidemiol 2017;87:4–13 |
| S10 | GRADE Working Group — official criteria for claiming GRADE use | https://www.gradeworkinggroup.org/ | Updated 2023-05 |

### Tier 2 — Strong secondary

| ID | Source | URL | Date/version |
|---|---|---|---|
| S11 | Core GRADE 4: risk of bias, publication bias, rating up (BMJ) | https://www.bmj.com/content/389/bmj-2024-083864 | 2024 |
| S12 | Guyatt et al. — What is "quality of evidence" and why is it important? (BMJ GRADE series) | https://www.bmj.com/content/336/7651/995 | 2008 |
| S13 | Schünemann et al. — GRADE Guidance Group statement on claiming GRADE use | https://doi.org/10.1016/j.jclinepi.2023.05.010 | J Clin Epidemiol 2023 |

### Tier 3 — Contextual (corroboration only; not load-bearing)

| ID | Source | URL |
|---|---|---|
| S14 | BMJ Global Health — GRADE primer for global health systematic reviews | https://gh.bmj.com/content/4/Suppl_1/e000848 |

**Contradictions surfaced (not hidden):**

| Topic | Position A | Position B | Resolution for whisker audit |
|---|---|---|---|
| Overall certainty combination | **Weakest-link** among critical outcomes (GRADE Handbook S1; Cochrane S3) | **Decision-invariance** exception when weak outcome cannot change recommendation (GRADE statins example) | Default **min()**; exception allowed only with written decision-invariance proof |
| Composite score presentation | **Band + sensitivity required** (OECD S4, Saltelli S6) | Some maturity models report single level with narrative caveats (CMMI-style, P14) | Adopt bands for numeric composite; ordinal maturity may use `{L,U}` integer range |
| GRADE upgrades | Large effect / dose-response upgrades for observational evidence (Core GRADE 4, S11) | Upgrades rare and inapplicable to RCT-starting high certainty (Core GRADE 1, S2) | Upgrades for audit evidence only when exemplar practice is overwhelming and replicated; default no upgrade |

**Source count:** 10 Tier-1 + 3 Tier-2 = **13 distinct Tier 1–2 sources** (floor ≥3 satisfied).

---

## 6. Overlap statement

This persona researched **external methods for evidence grading, confidence reporting, score bands, and sensitivity/flip analysis only**. It did **not** open whisker production code, cite whisker `file:line`, score whisker, clone/fork/copy code, or duplicate:

- **`persona/` / `llm-stack/`** — prior code-level whisker audits and scores.
- **`buildvsbuy/`** — library-choice and calibration-ROC implementation decisions (P16 owns calibration *method*; P17 owns uncertainty *reporting shape*).
- **`p15-weighted-scoring-rubric.md`** (when present) — MCDA weighting mechanics; P17 consumes weights but does not set them.
- **`p16-threshold-calibration.md`** (when present) — operating-point fitting; P17 references uncalibrated thresholds only as band-width drivers (U5).
- **`p19-anti-gaming-goodhart.md`** (when present) — Goodhart defenses; P17 references flip analysis overlap but does not duplicate anti-gaming checklist.

Boundary held: **§6.3 + §6.6 design rules and audit criteria** for the synthesis scoring system, not a whisker verdict.
