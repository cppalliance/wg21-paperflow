# P14 — Audit-Framework & Maturity-Model Research

**Persona:** 14 — Audit-Framework & Maturity-Model Researcher  
**Date:** 2026-07-18  
**Stage:** 0 evidence framing (no whisker code inspection)

---

## 1. Question restated

How should the whisker professional-grade audit structure its **maturity model**: dimension decomposition, ordinal capability levels with concrete descriptors, evidence requirements per level, and rules for deriving an overall posture from per-dimension profiles—drawing on rigorous external audit frameworks (OpenSSF Scorecard, OWASP SAMM, ISO/IEC 33004, CMMI/SCAMPI)?

Deliverable: the **skeleton** of whisker's audit maturity model (feeds `00-FRAME.md` section 6.1), not a whisker score.

---

## 2. Proposed audit criteria

Each criterion below is a **meta-criterion** for how the synthesis must build the rubric. Tags reference `00-FRAME.md` section 5 (audit-method) and section 6 (scoring-design hook).

---

### Criterion M1 — Hierarchical dimension decomposition (business functions → practices)

**What to measure:** The audit rubric decomposes into a fixed top-level set of **business functions** (coarse domains aligned to the decision question), each containing 2–4 **practices** (scorable sub-dimensions). Every practice has a stated purpose, observable outcomes, and explicit mapping to whisker audit concerns (release, hybrid architecture, eval science, etc.).

**How to measure:** Review the rubric document for (a) a declared domain/scope statement, (b) a tree with ≥8 practices across ≥5 functions, (c) unique IDs per practice, (d) purpose + outcome statements per practice (ISO process-description pattern).

**Audit-method:** Maturity-model / capability-level scoring (#2)

**Scoring-design hook:** 6.1 — weighted composite with declared dimensions

**Gaming vector:** Flat checklist of 50 unrelated bullets with no hierarchy; auditors cherry-pick easy items.

**Anti-gaming guard:** Require explicit parent→child mapping; synthesis rejects any practice that cannot name its parent function and at least one Tier-1-2 external precedent for inclusion.

**Evidence grade:** A (converging Tier-1: ISO/IEC 33004 §5.4 process descriptions; OWASP SAMM 5×15 structure; ISO/IEC 33004 §7.3.5 basic/extended process sets)

**Sources:** ISO/IEC 33004:2015 §5.3–5.4, §7.3.5; OWASP SAMM v2 About/Model (2026-07-18)

---

### Criterion M2 — Ordinal maturity scale with operational level descriptors (0–4)

**What to measure:** Each practice is scored on a **continuous ordinal scale** (recommended: 0–4) where every level has **operational descriptors** tied to observable evidence—not adjectives like "good" or "mature."

**Proposed whisker level skeleton (adapt per practice):**

| Level | Label | Descriptor pattern (must be instantiated per practice) |
|-------|-------|--------------------------------------------------------|
| **0** | Absent / unknown | No documented or observable implementation; assessor cannot collect minimum evidence |
| **1** | Initial / ad hoc | Activity exists informally; evidence is anecdotal or single artifact; not repeatable |
| **2** | Defined / repeatable | Documented policy or implementation; evidence from ≥1 process instance (repo, CI run, eval corpus) |
| **3** | Managed / measured | Activity measured against defined metrics or gates; evidence includes metrics output + procedure |
| **4** | Optimized / evidenced | Metrics drive improvement; evidence triangulated (artifact + operational proof); known gaps published |

**How to measure:** For each practice, verify level descriptors name **concrete evidence types** (see M4) and **minimum process instances** (e.g., one CI workflow, one labeled eval split).

**Audit-method:** Maturity-model / capability-level scoring (#2)

**Scoring-design hook:** 6.1 — per-dimension sub-criteria on bounded ordinal scale

**Gaming vector:** Vague L3/L4 labels that any project can self-claim ("we care about security").

**Anti-gaming guard:** Each level descriptor must cite at least one **negative definition** (what L(n) lacks relative to L(n+1)) and one **evidence artifact class** required at that level; contested levels default to L(n−1).

**Evidence grade:** A (SAMM L1–L3 objectives; CMMI staged levels 1–5; ISO 33004 §7.3.4 ordinal scale requirement)

**Sources:** OWASP SAMM v2 release notes (L1 initial, L2 structured, L3 optimized); CMMI-SW V1.1 staged representation; ISO/IEC 33004:2015 §7.3.4

---

### Criterion M3 — Dual streams or sub-objectives within each practice

**What to measure:** Each practice splits into **two streams** (or equivalent sub-objectives) that cover different aspects of the same concern and align activities across maturity levels—preventing "orphan" criteria that apply only at one level.

**How to measure:** Every practice documents Stream A and Stream B (or named equivalents) with per-level objectives, following SAMM's stream pattern (e.g., Strategy & Metrics: Stream A "Create and Promote," Stream B "Measure and Improve").

**Audit-method:** Maturity-model / capability-level scoring (#2)

**Scoring-design hook:** 6.1 — dimension decomposition

**Gaming vector:** Single-stream practices that collapse "having a document" and "measuring whether it works" into one checkbox.

**Anti-gaming guard:** Streams must be **independently scorable**; composite practice score = function of both streams (SAMM: average of stream maturity contributions), not maximum of the two.

**Evidence grade:** A (OWASP SAMM v2 stream structure; peer-reviewed SAMM assessment methodology)

**Sources:** OWASP SAMM Model / Strategy and Metrics streams (2026-07-18); OWASP SAMM v2 release notes; Software: Practice and Experience (2024) SAMM evaluation paper

---

### Criterion M4 — Evidence triangulation requirements per level

**What to measure:** Level ratings require **objective evidence** drawn from multiple indicator types; higher levels demand broader triangulation.

**Evidence indicator taxonomy (adapted from ISO 33004 + CMMI SCAMPI):**

| Indicator type | Examples in a whisker audit context |
|----------------|-------------------------------------|
| **Direct artifacts** | `pyproject.toml`, CI logs, eval reports, `CLAUDE.md`, trace/debug samples, SBOM, license files |
| **Indirect artifacts** | PR review history, issue threads showing maintenance, changelog entries, calibration commit records |
| **Affirmations / operational proof** | Reproducible replay command output, rerun-and-diff logs, operator walkthrough from docs alone |

**Minimum triangulation rules:**

- **L1:** ≥1 indicator type present  
- **L2:** ≥1 direct artifact + documented procedure  
- **L3:** direct artifact + indirect artifact + quantitative metric output  
- **L4:** all three indicator types; **oral/operational proof cannot be replaced by docs alone** (SCAMPI: ratings not from artifacts alone)

**How to measure:** Audit record links each level claim to cited evidence items by indicator type; assessor checklist verifies SCAMPI-style corroboration.

**Audit-method:** Conformance checklist (#1) + maturity-model (#2)

**Scoring-design hook:** 6.3 — evidence grades on every finding

**Gaming vector:** Policy documents that describe intended behavior without runnable proof; screenshot-only evidence.

**Anti-gaming guard:** Hard rule: **no level ≥3** if only direct artifacts exist with no operational replay or CI/eval output; evidence grade capped at C.

**Evidence grade:** A (ISO/IEC 33004 §6.3.1 assessment indicators; SCAMPI A Types of Objective Evidence; ISO/IEC 33002 assessment data requirements)

**Sources:** ISO/IEC 33004:2015 §6.3.1; ISO/IEC 33002:2015 §4.2; SCAMPI A Method Definition (CMU/SEI)

---

### Criterion M5 — Process profiles always reported; composite is secondary

**What to measure:** Assessment output is a **multi-dimensional process profile** (vector of practice-level scores), not a single headline number. Any composite index is explicitly derived and labeled subordinate to per-dimension scores.

**How to measure:** Report template includes full practice×level matrix; composite (if shown) includes formula, weights, and per-dimension breakdown. Scorecard explicitly warns aggregate scores obscure behavior; SAMM allows per-practice targets below max.

**Audit-method:** Maturity-model / capability-level scoring (#2)

**Scoring-design hook:** 6.1 — "No single composite number reported alone"

**Gaming vector:** Publishing one "whisker audit score: 78/100" while hiding failed hybrid-isolation or calibration dimensions.

**Anti-gaming guard:** Synthesis template **forbids** executive summary without full profile table; composite omitted entirely if any hard gate failed.

**Evidence grade:** A (OpenSSF Scorecard aggregate-score disclaimer; OWASP SAMM target-maturity flexibility; ISO 33004 §6.3.3 process profiles)

**Sources:** OpenSSF Scorecard README §Aggregate Score (2026-07-18); OWASP SAMM About; ISO/IEC 33004 §6.3.3

---

### Criterion M6 — Risk-weighted composite (when computed)

**What to measure:** If a weighted composite is computed, weights are tied to **risk or decision criticality**, not equal weighting. Document weight rationale per dimension.

**Exemplar formula (Scorecard):**  
`composite = Σ(check_score × risk_weight) / Σ(risk_weight)`  
with weights: Critical=10, High=7.5, Medium=5, Low=2.5.

**Proposed whisker weight classes (synthesis to assign per practice):**

| Class | Candidate whisker practices | Weight multiplier |
|-------|----------------------------|-------------------|
| Critical | Hard-gate dimensions (hybrid separation, fail-not-partial, licensing) | 10 |
| High | Determinism, eval/calibration integrity, security at trust boundary | 7.5 |
| Medium | Packaging, CI, observability, corpus quality | 5 |
| Low | Documentation polish, contributor diversity proxies | 2.5 |

**How to measure:** Weight table published with Tier-1-2 rationale per class; sensitivity analysis shows composite movement if one Critical dimension drops one level.

**Audit-method:** Maturity-model (#2) + comparative benchmarking (#3)

**Scoring-design hook:** 6.1 — explicit weights with written rationale

**Gaming vector:** Equal weights let low-risk doc completeness compensate for failed security/determinism.

**Anti-gaming guard:** Critical-class dimensions feed **hard gates** (M8); weight alone cannot override gate failure.

**Evidence grade:** A (OpenSSF Scorecard source code + README weight table)

**Sources:** github.com/ossf/scorecard README §Aggregate Score; checker/check_result.go `AggregateScoresWithWeight`

---

### Criterion M7 — Non-compensatory tiered sub-criteria within high-risk checks

**What to measure:** For high-risk practices, sub-requirements use **tiered (cumulative) scoring**: higher tiers unreachable until all lower tiers satisfied—mirroring Scorecard Branch-Protection tiers and CMMI goal satisfaction rules.

**How to measure:** High-risk practice rubrics define Tier 1→N requirements; partial upper-tier compliance without lower tiers yields **zero** upper-tier points (non-compensatory within practice).

**Audit-method:** Maturity-model (#2) + anti-gaming / Goodhart (#7)

**Scoring-design hook:** 6.2 — hard gates; 6.4 — anti-gaming

**Gaming vector:** "We have SLSA provenance (tier 5)" while branch protection and code review (tiers 1–2) are absent.

**Anti-gaming guard:** Template requires tier diagram for every Critical/High practice; automated checks where possible (CI present before claiming L3 test maturity).

**Evidence grade:** A (Scorecard checks.md Branch-Protection tier rules; CMMI/SCAMPI goal satisfaction before level rating)

**Sources:** OpenSSF Scorecard docs/checks.md §Branch-Protection (v5.5.0, 2026-04-23); SCAMPI A §4.4 rating rules

---

### Criterion M8 — Basic vs extended process sets and target profiles

**What to measure:** The maturity model defines:

1. **Basic process set** — minimum practices required for "professional baseline" (ISO maturity level 1 = process performance attribute achieved for all basic-set processes).  
2. **Extended sets** — additional practices for advanced posture.  
3. **Target profile** — explicit per-practice target levels (SAMM: not all practices need L3).

**How to measure:** Rubric includes marked basic-set practices; verdict includes gap analysis vs declared target profile, not only vs maximum level.

**Audit-method:** Maturity-model (#2)

**Scoring-design hook:** 6.1 — dimensions; 6.2 — gates on basic set

**Gaming vector:** Declaring audit pass by averaging in many L0 extended practices while basic-set practices fail.

**Anti-gaming guard:** **Pass requires all basic-set practices ≥ L2** (synthesis to fix number); extended practices affect composite only.

**Evidence grade:** A (ISO/IEC 33004 §7.3.5 basic/extended process sets; OWASP SAMM target maturity)

**Sources:** ISO/IEC 33004:2015 §7.3.5–7.3.6; OWASP SAMM About

---

### Criterion M9 — Formal rules for deriving organizational maturity from profiles

**What to measure:** Documented, auditable rules map practice-level profiles to an **overall maturity band** (not an arbitrary judgment).

**Proposed derivation rules (synthesis to refine):**

1. Compute per-practice level Lp ∈ {0,1,2,3,4}.  
2. **Gate check:** if any hard-gate practice fails → overall verdict = FAIL regardless of profile.  
3. **Basic-set rule:** org baseline level = min(Lp) over basic set (weakest-link for baseline).  
4. **Composite band:** risk-weighted average of Lp mapped to bands (e.g., 0–1.4 = Initial, 1.5–2.4 = Defined, 2.5–3.4 = Managed, 3.5–4.0 = Optimized).  
5. Report **both** weakest-link baseline and weighted composite band; they may diverge.

**How to measure:** Synthesis document includes worked example with sample profile; rules reference ISO 33004 §7.3.6 derivation requirement.

**Audit-method:** Maturity-model (#2)

**Scoring-design hook:** 6.1, 6.6 — score band not point

**Gaming vector:** Hand-waving "mostly L3" when one Critical practice is L0.

**Anti-gaming guard:** Weakest-link on basic set + hard gates; band must name flip conditions (6.6).

**Evidence grade:** A (ISO 33004 §7.3.6; SCAMPI maturity/capability rating rules)

**Sources:** ISO/IEC 33004:2015 §7.3.6; SCAMPI A §4.4.5 maturity level rules

---

### Criterion M10 — Quality criteria on activities (coverage + quality)

**What to measure:** Each activity within a practice carries **quality criteria** (SAMM v2)—assessors score both whether the activity is present (coverage) and whether it is performed effectively (quality).

**How to measure:** Rubric activities include binary/near-binary quality checks (e.g., "metric defined" vs "metric tracks gate TPR/FPR with published operating point").

**Audit-method:** Maturity-model (#2) + calibration audit (#5) where applicable

**Scoring-design hook:** 6.1 — level descriptors; 6.3 — evidence grades

**Gaming vector:** Checkbox compliance—CI exists but does not run gate tests; calibration doc exists but thresholds are borrowed.

**Anti-gaming guard:** Quality criteria escalate with level; L3+ requires published measurement results, not just definitions.

**Evidence grade:** B (OWASP SAMM v2 release notes quality criteria; SAMM assessment 4-point scale literature)

**Sources:** OWASP SAMM v2 release notes (2026-07-18); Journal of Systems and Software (2024) SAMM in-practice evaluation

---

### Criterion M11 — Assessment scope declaration and minimum instances

**What to measure:** Before scoring, assessment declares scope: org unit (whisker package + ops surface), process instances (e.g., ≥2 CI workflows, ≥2 eval corpus slices, ≥2 replay runs), and excluded areas.

**How to measure:** Assessment plan document exists; ISO 33002 requires sufficient objective evidence for scope; Class-2 assessments require ≥2 process instances per assessed process where available.

**Audit-method:** Conformance checklist (#1)

**Scoring-design hook:** 6.3 — confidence grades

**Gaming vector:** Scoring only the happy-path demo repo path while production eval corpus differs.

**Anti-gaming guard:** Scope lists **minimum instances**; scoring uses stratified sample across WG21 paper types (delegated to P11/P12 personas for corpus rules).

**Evidence grade:** A (ISO/IEC 33002:2015 assessment scope; Automotive SPICE PAM v4.0 assessment indicators)

**Sources:** ISO/IEC 33002:2015 §4.2; Automotive SPICE PAM v4.0 §3.3 (ISO 33004 conformant)

---

### Criterion M12 — Mapping table from practices to audit methods

**What to measure:** Every practice maps to one or more methods from `00-FRAME.md` §5 (conformance, maturity, benchmarking, construct validity, calibration, red-team, etc.) so the synthesis coverage matrix has no orphan methods or orphan practices.

**How to measure:** Traceability matrix: practice ID × method ID × persona source file.

**Audit-method:** Meta (structural requirement)

**Scoring-design hook:** 6.1 — dimension set completeness

**Gaming vector:** Maturity scoring applied to questions that need adversarial probing or calibration.

**Anti-gaming guard:** Methods with teeth (red-team, replay) must attach to ≥1 practice at L3+ evidence tier.

**Evidence grade:** B (ISO 33004 §6.3.2 explicit mapping requirement)

**Sources:** ISO/IEC 33004 §6.3.2; `00-FRAME.md` §5

---

## 3. External benchmark / exemplar bar

### 3.1 OWASP SAMM v2 — prescriptive maturity model

**Bar:** Five business functions, fifteen practices, three maturity levels, two streams per practice, activities with quality criteria, coverage+quality scoring, organization-defined target profiles (not max-everywhere). Assessment via structured questionnaire (90 questions) producing 0–3 practice ratings from stream averages.

**Transfer to whisker audit skeleton:**

```
Governance          → Audit program meta (scope, targets, improvement roadmap)
Design              → Hybrid architecture, determinism doctrine, API contract
Implementation      → Release/packaging, CI, dependency hygiene
Verification        → Eval science, calibration, adversarial probes, replay
Operations          → Operator UX, observability, failure handling, privacy
```

Map whisker-specific practices under each (synthesis task); keep SAMM's **measurable + actionable + versatile** design goals.

### 3.2 OpenSSF Scorecard — automated check portfolio with weighted aggregation

**Bar:** ~18 checks across three themes; each check 0–10 with documented tier rules; risk-labeled weights; aggregate is weighted mean; explicit warning that aggregate alone is misleading.

**Transfer:** Treat each whisker practice like a Scorecard check: documented sub-tiers, automation where possible (CI, SBOM, license files), risk class for weighting. Prefer **per-check scores visible in CI/badge** over opaque rollup.

### 3.3 ISO/IEC 33004 — normative maturity-model requirements

**Bar:** Maturity model must: sit on a process assessment model; define ordinal levels characterized by process profiles; specify basic + extended process sets; publish rules for deriving org maturity from profiles; use assessment indicators (practices, information items, resources) mapped to outcomes.

**Transfer:** Whisker audit documentation must satisfy §7.3 checklist before synthesis calls the model "ISO-aligned." Full certification is not the goal; **structural conformance** is.

### 3.4 CMMI SCAMPI A — evidence rigor for ratings

**Bar:** Multiple evidence types required; artifacts alone insufficient; practice implementation indicators; goal satisfaction before level claims; verification-based appraisal preferred over discovery-only.

**Transfer:** Stage-2 whisker audit should collect an **evidence pack** before assessor review; L3+ requires operational proof (replay, eval runs), not doc review alone.

---

## 4. Proposed whisker audit maturity model skeleton (synthesis artifact)

This section is the direct deliverable for section 6.1 fan-in.

### 4.1 Top-level functions and practice inventory (draft)

| Function | Practice ID | Practice name | Primary audit methods |
|----------|-------------|---------------|----------------------|
| **F1 Release & supply chain** | PR-01 | Packaging & release readiness | Conformance, maturity |
| | PR-02 | Public API & contract stability | Conformance, maturity |
| | PR-03 | Dependency & supply-chain integrity | Conformance, maturity |
| | PR-04 | CI & test-suite maturity | Maturity, anti-gaming |
| **F2 Architecture & determinism** | AD-01 | Hybrid deterministic core + advisory LLM separation | Maturity, red-team |
| | AD-02 | Determinism & reproducibility | Replay, maturity |
| | AD-03 | Dual-determinism doctrine reconciliation | Maturity, doc audit |
| | AD-04 | Modularity & package boundaries | Conformance, maturity |
| **F3 Extraction quality & eval** | EQ-01 | Metric construct validity | Construct validity |
| | EQ-02 | LLM-as-judge trustworthiness | Construct validity, calibration |
| | EQ-03 | Ground truth & corpus quality | Maturity, benchmarking |
| | EQ-04 | Benchmarking & leaderboard integrity | Benchmarking |
| | EQ-05 | Comprehension vs fidelity evaluation | Construct validity |
| **F4 Scoring & audit integrity** | SC-01 | Weighted rubric & gate design | Maturity (meta) |
| | SC-02 | Threshold calibration & operating points | Calibration |
| | SC-03 | Evidence grading & score uncertainty | Confidence grading |
| **F5 Adversarial & anti-gaming** | AG-01 | Red-team / adversarial robustness | Red-team |
| | AG-02 | Goodhart resistance | Anti-gaming |
| **F6 Operator & documentation** | OP-01 | Documentation & agent guidance completeness | Doc audit |
| | OP-02 | CLI & operator UX | Conformance, maturity |
| **F7 Trust & operations** | TR-01 | Provenance & licensing | Provenance audit |
| | TR-02 | Security & prompt-injection defense | Conformance, red-team |
| | TR-03 | Privacy & data governance | Conformance, maturity |
| | TR-04 | Observability & failure handling | Observability, fault injection |

**Basic process set (baseline professional):** PR-01, PR-04, AD-01, AD-02, EQ-01, EQ-03, AG-02, OP-01, TR-01, TR-02, TR-04 (synthesis may adjust after P01–P25 fan-in).

### 4.2 Universal level descriptors (instantiate per practice)

Use M2 table: **0 Absent → 1 Ad hoc → 2 Defined → 3 Measured → 4 Optimized**, with practice-specific evidence lists under M4.

### 4.3 Stream template (apply per practice)

- **Stream A — Establish:** policy, implementation, documentation trail  
- **Stream B — Verify:** measurement, replay, independent check, published results  

### 4.4 Output artifacts of a whisker maturity assessment

1. **Process profile** — table of all practices × achieved level + evidence links  
2. **Target gap matrix** — current vs target per practice  
3. **Hard-gate register** — pass/fail independent of composite  
4. **Composite band** — risk-weighted, with ± uncertainty from contested/low-confidence criteria (P17)  
5. **Flip conditions** — which practice re-grade moves verdict across band boundary  

---

## 5. Recommended weight & hard-gate rationale

| Item | Recommendation | Rationale |
|------|----------------|-----------|
| **Maturity-model structure (M1–M12)** | Meta-layer; not directly weighted | Defines shape of all other scores; failure here invalidates synthesis |
| **Basic-set minimum (M8)** | **Hard gate:** all basic-set practices ≥ L2 | ISO basic maturity = process performance on essential set; professional baseline |
| **Hybrid separation (AD-01)** | **Hard gate** at L2+ with tiered sub-criteria (M7) | Critical risk class; compensatory composite must not override |
| **Evidence triangulation (M4)** | **Hard gate** for any L3+ claim | SCAMPI/ISO: no rating without objective evidence |
| **Process profile reporting (M5)** | **Hard gate** on report format | Prevents Goodhart collapse to single number |
| **Risk-weight classes (M6)** | Weight rationale required in synthesis | Scorecard precedent; weights are claims requiring citations |
| **Overall maturity derivation (M9)** | Report weakest-link baseline **and** weighted band | Surfaces hidden weak dimensions |

Weights for individual practices (PR-01 vs EQ-04 etc.) are **deferred to P15** and persona cluster evidence; this persona supplies the **structural skeleton** only.

---

## 6. Sources

| Tier | Source | URL / identifier | Version / date | Used for |
|------|--------|------------------|----------------|----------|
| **T1** | ISO/IEC 33004:2015 — Process assessment — Requirements for process reference, process assessment and maturity models | https://www.iso.org/standard/54178.html (content via ISO/IEC 33004:2015 text) | 2015-03-01 | M1, M2, M4, M5, M8, M9, M11, M12 — maturity model normative requirements |
| **T1** | ISO/IEC 33002:2015 — Requirements for performing an assessment | https://www.iso.org/standard/54176.html | 2015-03-01 | M4, M11 — objective evidence sufficiency, assessment records |
| **T1** | OWASP SAMM v2 — About, Model, Release notes | https://owaspsamm.org/about/ ; https://owaspsamm.org/model/ ; https://owaspsamm.org/release-notes-v2/ | v2.0 (2019+); accessed 2026-07-18 | M1–M3, M5, M8, M10 — 5×15 structure, streams, levels, quality criteria |
| **T1** | OpenSSF Scorecard — checks.md + README Aggregate Score | https://github.com/ossf/scorecard/blob/main/docs/checks.md ; https://github.com/ossf/scorecard | checks.md v5.5.0 (2026-04-23); README 2026-07-18 | M5–M7 — tiered checks, risk weights, aggregate disclaimer |
| **T1** | CMMI SCAMPI A Method Definition | https://www.sei.cmu.edu/ (SCAMPI A v1.2 method definition document) | SCAMPI A v1.2 | M4, M7, M9 — evidence types, goal satisfaction, rating rules |
| **T2** | OpenSSF Scorecard — checker/check_result.go | https://github.com/ossf/scorecard/blob/main/checker/check_result.go | main branch, 2026-07-18 | M6 — `AggregateScoresWithWeight` implementation |
| **T2** | Automotive SPICE PAM v4.0 (ISO/IEC 33004 conformant assessment model) | https://vda-qmc.de/wp-content/uploads/2023/12/Automotive-SPICE-PAM-v40.pdf | v4.0, 2023-12 | M4, M11 — assessment indicators, evidence accumulation |
| **T2** | Evaluating software security maturity using OWASP SAMM (in-practice study) | https://www.sciencedirect.com/science/article/pii/S0164121224001079 | Journal of Systems and Software, 2024 | M3, M10 — stream scoring, coverage+quality, assessment mechanics |

**Source count:** 8 distinct Tier 1–2 primary sources (floor: ≥3 met).

**Contradictions surfaced:**

- **Aggregate vs profile:** Scorecard publishes a weighted aggregate but warns it is easily misleading; SAMM discourages max-level-everywhere. **Resolution:** adopt ISO/Scorecard profile-first reporting; composite is secondary (M5, M9).  
- **Artifacts vs automation:** Scorecard is fully automated from repo signals; SCAMPI requires human affirmations. **Resolution:** whisker audit uses automation for PR-* practices where possible, but L3+ on AD/EQ/TR requires operational replay (SCAMPI-aligned).  
- **Level count:** SAMM uses 3 levels; CMMI uses 5; ISO requires ordinal scale without fixing count. **Resolution:** whisker uses 0–4 (5 points) as compromise with SAMM L1–L3 mapped to levels 1–3 and CMMI L4–5 mapped to level 4.

---

## 7. Overlap statement

This persona researched **external audit-framework and maturity-model structure only**. It did **not**:

- Open, inspect, or score whisker production code (no `file:line` citations)  
- Clone, fork, or copy whisker or third-party code  
- Duplicate **`persona/`** or **`llm-stack/`** code-level audit verdicts  
- Duplicate **`p15`** (weighted-scoring mechanics detail), **`p17`** (evidence grading detail), or **`p30`** (eval-framework scoring patterns)—this file feeds **section 6.1 skeleton** only; those personas own weights, uncertainty, and eval-framework case study respectively  
- Re-litigate any prior **`redteam/`**, **`langextract/`**, or **`buildvsbuy/`** findings  

**Overlap boundary confirmed:** Unique ownership of the audit's **maturity-model skeleton** (dimension decomposition, level descriptors, evidence rules, profile derivation). Prior folders did not assemble this meta-rubric.

---

**Strongest criterion:** **M4 — Evidence triangulation requirements per level** (backed by ISO/IEC 33004 assessment indicators and SCAMPI's prohibition on artifact-only ratings). Without triangulated objective evidence, maturity levels collapse to self-assessment theater—the failure mode all four exemplar frameworks explicitly guard against.
