# P18 — Adversarial / Red-Team Methodology Researcher

**Persona:** 18 of 30 (Cluster E: Adversarial / anti-gaming)  
**Date:** 2026-07-18  
**Scope:** External method and standards only. No whisker production-code inspection.

---

## 1. Question restated

How should an extraction-QA system be **red-teamed** so that attacks that **pass deterministic gates while corrupting meaning** are systematically found, measured, and turned into durable regression probes? This persona covers: attack taxonomies for gate-evasion (token-preserving reorderings, table row/cell swaps, math-relation flips, decoy tables, code garbling, visual-parse discrepancies), a **structured red-team process**, **coverage measurement** of the attack space, and a **probe catalog design** that feeds adversarial-robustness audit criteria. It researches *method*, not whisker code and not per-converter defect reports.

---

## 2. Proposed audit criteria

Each criterion is scored on a **0–4 maturity ladder** unless marked as a **hard gate** (pass/fail). Evidence grades follow `00-FRAME.md` §6.3: **A** = multiple Tier-1 corroborating; **B** = single Tier-1 or converging Tier-2; **C** = Tier-3 only or contested; **D** = Tier-4/speculative.

### Criterion ADV-1 — Multi-axis attack taxonomy (gate-evasion oriented)

| Field | Value |
|---|---|
| **Criterion** | The QA program maintains a **versioned attack taxonomy** spanning at least six orthogonal axes relevant to extraction gates: (1) **surface/token preservation** (high NID/TEDS, wrong semantics), (2) **reading-order / section permutation**, (3) **table structure corruption** (row/column/cell swap, decoy tables, header drift), (4) **math/logic relation flip** (comparator, negation, quantifier), (5) **code-block garbling** (syntax-preserving semantic flip), (6) **modality-specific structural loss** (footnotes, lists, captions detached from anchors). Each axis maps to expected gate behavior (must fail / must flag / must not silently pass). |
| **How to measure** | Inspect taxonomy document: ≥6 axes with ≥2 concrete operators each; each operator tagged with corruption intent (semantic vs cosmetic) and affected gate family (stability/fidelity/comprehension). Cross-walk to document-intelligence vulnerability classes (layout bbox shift, logical-stream vs visual order, TSR cell mis-association). Score 0 = ad hoc anecdotes; 4 = complete matrix with operator IDs stable across releases. |
| **Audit method** | Adversarial / red-team probing (§5.6) + metric construct-validity audit (§5.4) |
| **Scoring hook** | §6.1 dimension: adversarial-robustness; §6.4 anti-gaming (taxonomy must name semantic corruption, not only pixel noise) |
| **Gaming vector** | Taxonomy lists only OCR noise or typos (attacks surface metrics already cover); missing table/math/code axes so gates look comprehensive while semantic swaps untested. |
| **Anti-gaming guard** | Require ≥1 operator per axis with **controlled semantic delta** (gold diff shows meaning change while selected surface metrics stay green); independent reviewer signs axis completeness checklist. |
| **Evidence grade** | **A** |
| **Sources** | S3 (VDU multi-modal attacks), S4 (ProSA structural auditing), S5 (QA contextual breach taxonomy), S6 (PDF parse-discrepancy operators) |

**Contradiction surfaced:** Gradient-based adversarial attacks (bbox/pixel/text) optimize for model failure, while QA gate red-teaming optimizes for **metric pass + meaning fail**. **Resolution rule:** taxonomy must explicitly separate **model-robustness probes** (S3) from **gate-evasion probes** (semantic corruption under high fidelity scores); conflating them inflates coverage scores without testing QA gates.

---

### Criterion ADV-2 — Structured red-team process (layered testing)

| Field | Value |
|---|---|
| **Criterion** | Red-teaming follows a **documented multi-level process** adapted from authoritative AI evaluation frameworks: (L1) **automated probe battery** on fixed corpus slices, (L2) **adversarial human/crafted probing** targeting known gate blind spots, (L3) **realistic operator workflow replay** (full CLI path on representative papers). Each level has entry/exit criteria, recorded strategies, and post-run questionnaires or structured logs. |
| **How to measure** | Verify written runbook: levels defined; L1 runs in CI on every change; L2 scheduled or pre-release with assigned roles; L3 samples stratified by modality (PDF/HTML, tables-heavy, code-heavy, math-heavy). Check artifacts: probe logs, strategy notes, pass/fail rationale per level. Maturity 0 = informal manual poking; 4 = NIST ARIA-style three-level separation with CoRIx-like dimension tagging (risk dimension per finding). |
| **Audit method** | Adversarial / red-team probing (§5.6) + maturity model (§5.2) |
| **Scoring hook** | §6.1 adversarial-robustness; §6.2 candidate gate if L1 absent (no automated adversarial regression) |
| **Gaming vector** | Only L1 automated checks that never update; L2 "red team" performed by gate authors without independence; L3 skipped entirely. |
| **Anti-gaming guard** | L2 requires **independence** (tester ≠ threshold author); successful L2 findings must convert to L1 probes within one release cycle (promotion SLA); L3 uses papers not in L1 golden set. |
| **Evidence grade** | **A** |
| **Sources** | S1 (NIST ARIA pilot report), S2 (NIST ARIA design companion), S7 (OWASP GenAI Red Teaming Guide v1.0) |

---

### Criterion ADV-3 — Metamorphic relations as gate-oracle surrogates

| Field | Value |
|---|---|
| **Criterion** | For gate families where full reference oracle is expensive, the program defines **metamorphic relations (MRs)** linking controlled input transforms to **expected gate verdict changes** (pass→fail, fail→pass, or score delta bounds). MRs cover document-extraction-relevant transforms: section permutation, table row swap, negation insertion, entity substitution in headers, caption relocation. Catalog cites relation ID, input relation R_i, output relation R_o, and applicability (modality null-eligible when absent). |
| **How to measure** | Count MRs implemented vs cataloged; run MR suite on ≥N corpus pages per modality; record violation rate and manual true-positive review sample (target ≥50 violations reviewed per release). Compare to Chen/Liu baseline: diverse small MR set should catch faults oracle-free. Track false-positive rate of MR oracle separately from gate false-positive rate. |
| **Audit method** | Adversarial / red-team probing (§5.6) + reproducibility replay (§5.8) |
| **Scoring hook** | §6.1 adversarial-robustness; §6.4 anti-gaming; feeds §6.2 if MR suite empty while determinism/fidelity gates claim completeness |
| **Gaming vector** | MRs only test cosmetic paraphrase (synonym swap) while table/math MRs omitted; violations ignored as "MR noise" without TP review. |
| **Anti-gaming guard** | Require **structural MRs** (permutation, swap) not just lexical MRs; Cho et al. finding: prioritize high-effectiveness MRs (low FP, high fault rate) in CI; manual TP audit mandatory before discounting violations. |
| **Evidence grade** | **A** |
| **Sources** | S8 (Liu et al. IEEE TSE 2014), S9 (Chen et al. ACM CSUR 2018), S10 (Cho et al. ICSME 2025), S11 (MT4NLP catalog) |

**Contradiction surfaced:** Cho et al. report ~60% true-positive rate on MR violations for LLMs (intrinsic MT limits), while Liu et al. show MR sets can match oracle fault detection on traditional software. **Resolution rule:** MRs are **necessary complement**, not sole gate; high FP MRs demoted to exploratory (L2) until TP rate documented; load-bearing gates still need labeled or comprehension checks (ADV-6).

---

### Criterion ADV-4 — Attack-space coverage measurement (not just pass rate)

| Field | Value |
|---|---|
| **Criterion** | Red-team reports **coverage** over the attack taxonomy: for each axis/operator, track `(probes_run, probes_effective, gates_bypassed, downstream_failures)` and a **coverage index** (e.g., fraction of operator×modality cells exercised in trailing 90 days). Distinguish **footprint coverage** (bytes/area perturbed) from **structural coverage** (identity-bearing elements perturbed), following document-parser auditing research. |
| **How to measure** | Coverage matrix published each release; empty cells explicitly listed as blind spots; trend of bypass rate per operator. ProSA precedent: structural loss rate (B-SLR) correlates with downstream QA degradation better than affected area alone (R² 0.73–0.92 vs 0.11–0.38 in cited study). Require reporting both **gate outcome** and **downstream comprehension outcome** per cell. |
| **Audit method** | Adversarial / red-team probing (§5.6) + benchmarking integrity (§5.4 overlap with P12) |
| **Scoring hook** | §6.1 adversarial-robustness; §6.6 uncertainty (coverage gaps widen score band) |
| **Gaming vector** | 100% pass rate achieved by running only one easy operator; coverage metric omitted; area-based stress tests that miss topology swaps. |
| **Anti-gaming guard** | Minimum coverage floor: ≥80% of operator×modality cells exercised per major release OR documented waiver; waivers require synthesis approval; report **uncovered cells** alongside pass rate. |
| **Evidence grade** | **B** (structural metrics from recent preprint S4; process pattern from S1/S2) |
| **Sources** | S1, S2, S4 |

---

### Criterion ADV-5 — Versioned probe catalog with promotion workflow

| Field | Value |
|---|---|
| **Criterion** | All adversarial inputs live in a **versioned probe catalog**: stable probe ID, operator reference, source document provenance, expected gate verdict, expected comprehension impact, and regression test hook. Successful L2/L3 attacks **promote** to catalog within defined SLA; catalog feeds CI as deterministic fixtures (no regeneration drift in L1). |
| **How to measure** | Catalog schema review; count promoted probes per quarter; verify each probe runs in CI and fails on known-bad baseline (canary that must fail). Giskard pattern: scan finding → permanent test case → CI gate. Checksum or content hash on probe artifacts to detect silent edits. |
| **Audit method** | Adversarial / red-team probing (§5.6) + CI/test maturity overlap (P04) |
| **Scoring hook** | §6.1 adversarial-robustness; §6.2 candidate gate: zero promoted probes after ≥2 L2 cycles implies red team is theater |
| **Gaming vector** | Probes stored only in issue tracker; regenerated each run (non-deterministic); catalog never linked to CI. |
| **Anti-gaming guard** | Probe IDs immutable; changes require new ID + deprecation note; CI fails if catalog probes skipped; minimum catalog size scales with taxonomy size (synthesis sets floor). |
| **Evidence grade** | **B** |
| **Sources** | S7, S12 (Giskard scan-to-suite promotion), S1 |

---

### Criterion ADV-6 — Downstream comprehension verification on corrupted inputs

| Field | Value |
|---|---|
| **Criterion** | Every high-severity adversarial probe includes a **downstream check** that gate pass implies comprehension/fact recovery still holds: QA questions, fact-extraction checklist, or blind read-back on corrupted vs clean pairs. Surface-metric pass alone is insufficient for probe closure. |
| **How to measure** | For probe subset where gates pass, run comprehension eval (question set with known answers from clean doc); record **gate-pass-but-comprehension-fail rate**. Contextual Breach metrics adapted: robustness index, error rate under perturbation intensity levels. Target: zero undetected semantic corruption on promoted catalog. |
| **Audit method** | Adversarial / red-team probing (§5.6) + comprehension-vs-fidelity eval (P13 boundary) |
| **Scoring hook** | §6.1 adversarial-robustness + extraction-quality; §6.2 hard gate candidate: any promoted probe with gate-pass + comprehension-fail blocks release |
| **Gaming vector** | Red team stops at gate verdict; comprehension eval run only on clean corpus; corrupt-and-recheck skipped. |
| **Anti-gaming guard** | Probe closure requires signed row: `(gate_verdict, comprehension_verdict, human_review)`; automated fail if comprehension not run for operators tagged semantic-critical. |
| **Evidence grade** | **A** |
| **Sources** | S5, S13 (QA adversarial survey), S4 |

---

### Criterion ADV-7 — Threat modeling and success criteria before probing

| Field | Value |
|---|---|
| **Criterion** | Red-team charter defines **assets, trust boundaries, attacker goals** (evade gate, inject false pass, corrupt table/math meaning), and **success/failure definitions** before probes run. Maps to OWASP GenAI red-team scope phases and extraction-specific harms (silent semantic corruption vs crash vs false reject). |
| **How to measure** | Written threat model: STRIDE or equivalent; explicit "violative output" definitions per scenario (NIST ARIA red-teamer briefing pattern); alignment between threat model axes and ADV-1 taxonomy. |
| **Audit method** | Conformance checklist (§5.1) applied to red-team program docs |
| **Scoring hook** | §6.1 adversarial-robustness; §6.5 disagreement handling when threat model omits an axis later found in production |
| **Gaming vector** | Generic OWASP LLM list copied without extraction-QA goals; success = "no crashes" only. |
| **Anti-gaming guard** | Threat model must include ≥1 goal per ADV-1 axis; annual refresh or post-incident update required. |
| **Evidence grade** | **B** |
| **Sources** | S7, S1 |

---

### Criterion ADV-8 — Independence and anti-self-deception controls

| Field | Value |
|---|---|
| **Criterion** | Adversarial evaluation separates **probe authors**, **gate implementers**, and **comprehension oracle providers** (human or labeled QA). Blind variants: gate run without access to corruption metadata; comprehension questions authored before seeing gate outputs. |
| **How to measure** | Role separation in runbook; sample audit of probe commits vs gate threshold commits (different authors); blind read-back protocol documented. |
| **Audit method** | Adversarial / red-team probing (§5.6) + anti-gaming (§5.7 overlap with P19) |
| **Scoring hook** | §6.4 anti-gaming; §6.3 evidence grade capped at C if single actor performs all roles |
| **Gaming vector** | Same engineer writes gate thresholds and adversarial probes (overfit probes to current gate); LLM judge evaluates own pipeline output without isolation. |
| **Anti-gaming guard** | Mandatory reviewer not in gate PR authors for new probes; LLM advisory signals cannot be sole comprehension oracle (consistent with whisker advisory-only doctrine in frame §2). |
| **Evidence grade** | **B** |
| **Sources** | S1 (diverse red-team expertise), S7, S2 |

---

## 3. External benchmark / exemplar bar

### Tier-1/Tier-2 signals (method patterns, not whisker scores)

| Practice | NIST ARIA | OWASP GenAI RT | Metamorphic testing (MT) | Document QA robustness |
|---|---|---|---|---|
| Layered testing | Model + red team + field (3 levels) | Model + implementation + system + runtime (4 phases) | Source/follow-up pairs via MRs | Noise intensity ladders + robustness index |
| Human adversarial role | Skilled red teamers, violative-output briefings | Domain experts + security + ML engineers | MR violation triage (TP/FP audit) | Perturbation taxonomy (char/word/semantic) |
| Coverage philosophy | CoRIx multi-dimensional risk tree | OWASP LLM Top 10 + custom scenarios | 191 NLP MRs catalog; 36 implemented at scale | Structure-aware > footprint-only |
| CI integration | Pilot metrics + annotation pipeline | Scan grades, promote to permanent tests | LLMORPH ~560K executions | Downstream QA degradation on corrupted context |
| Failure definition | Guardrail violation / risk to validity | Harm categories + severity grades | R_i true, R_o false | Gate pass but answer wrong under corruption |

**Professional bar:** A defensible extraction-QA red-team program combines **NIST-style layered testing** (ADV-2), **OWASP-style threat-modeled campaigns** (ADV-7), **MT-based oracle-free probes** for gate logic (ADV-3), **structure-aware coverage metrics** (ADV-4), and **comprehension closure** on every promoted probe (ADV-6). Passing only automated similarity metrics without adversarial semantic probes is below bar.

**Probe catalog design (handoff artifact):**

```
probe_id: ADV-PROBE-{axis}{seq}   # e.g. ADV-PROBE-T03
taxonomy_ref: ADV-1 axis/operator ID
modality: pdf | html | null-eligible
transform: deterministic spec (reproducible)
gate_expect: pass | fail | flag
comprehension_checks: [question_id, ...]
promotion: {date, source_level: L1|L2|L3, author ≠ gate_author}
coverage_cell: operator × modality matrix coordinate
```

Catalog entries must be **deterministic transforms** (seeded or spec-based), not one-off LLM generations, so L1 CI replay stays stable (aligns with determinism doctrine in frame §1).

**Where exemplars diverge (do not cargo-cult):** NIST ARIA targets LLM application guardrails (toxicity, spoilers), not WG21 table fidelity. Giskard uses LLM-generated adversarial scenarios (non-deterministic generation); whisker-audit rubric should require **frozen probes** for gate regression. Gradient attacks on VDU models (S3) test model weights, not deterministic Python gates, unless gates consume model outputs directly.

---

## 4. Recommended weight & gate recommendation

| Recommendation | Rationale |
|---|---|
| **Dimension weight: 10%** of composite (shared adversarial cluster with P19 anti-Goodhart at ~8%; combined ~18% for "cannot game the score") | Adversarial robustness is load-bearing for extraction-QA credibility but depends on corpus + probe investment; weight cites NIST ARIA + MT literature: without red team, gate metrics are unvalidated. |
| **Hard gates (conjunctive): ADV-6 closure on promoted catalog; ADV-2 L1 automated probe suite present** | **ADV-6:** Gate-pass + comprehension-fail on any promoted probe is a silent corruption ship (S5, S4 downstream QA degradation). **ADV-2 L1:** No automated adversarial regression means fixes regress silently (S1 continuous evaluation intent). |
| **Soft cap (score ≤2 if unmet): ADV-4 coverage <80% cells; ADV-3 zero structural MRs** | Incomplete attack-space coverage widens uncertainty band (§6.6); MR gap leaves oracle problem unresolved (S8–S10). |
| **Evidence propagation** | Dimension inherits weakest grade among ADV-2, ADV-3, ADV-6 (typically **A** if CI + MR + comprehension enforced). |
| **Contested discount** | ADV-4 structural metrics from single recent preprint (S4): apply §6.5; use B-SLR as recommended, not mandatory, until replicated; reduce ADV-4 weight 30% if contested. |

**Strongest criterion (single load-bearing bar):** **ADV-6 — Downstream comprehension verification on corrupted inputs.** Gate metrics alone cannot certify semantic integrity under adversarial corruption (S4: structure-aware probes degrade downstream QA while area metrics miss; S5: contextual breach framework). A red-team method that does not close the loop from corrupted input → gate verdict → comprehension outcome is indistinguishable from cosmetic testing.

---

## 5. Sources

### Tier 1 — Authoritative / primary

| ID | Source | URL | Date/version |
|---|---|---|---|
| S1 | NIST AI 700-2 — Assessing Risks and Impacts of AI (ARIA) Pilot Evaluation Report | https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.700-2.pdf | Jan 2025 (NIST AI 700-2) |
| S2 | NIST ARIA Program Evaluation Design Companion Document | https://ai-challenges.nist.gov/aria/docs/ARIA_Program_Companion_Document_Dec20.pdf | Dec 2024 |
| S3 | Robustness Evaluation of OCR-based Visual Document Understanding under Multi-Modal Adversarial Attacks | https://arxiv.org/pdf/2506.16407 | 2025 (arXiv:2506.16407) |
| S4 | How Do Document Parsers Break? Auditing Structural Vulnerability in Document Intelligence (ProSA) | https://arxiv.org/html/2605.19309 | 2026 preprint (arXiv:2605.19309) |
| S5 | Contextual Breach: Assessing the Robustness of Transformer-based QA Models | https://doi.org/10.48550/arxiv.2409.10997 | 2024 (arXiv:2409.10997) |
| S6 | Adversarial PDF Parsing Taxonomy (8 operators, visual–parse discrepancy) | https://huggingface.co/datasets/Dean2Wang/Adversarial-PDF-Parsing-Taxonomy-8Ops | 2025 dataset card |
| S8 | Liu et al. — How Effectively Does Metamorphic Testing Alleviate the Oracle Problem? | https://doi.org/10.1109/tse.2013.46 | IEEE TSE 40(1), 2014 |
| S9 | Chen et al. — Metamorphic Testing: A Review of Challenges and Opportunities | https://doi.org/10.1145/3143561 | ACM Computing Surveys 51(1), 2018 |
| S10 | Cho et al. — Metamorphic Testing of Large Language Models for NLP | https://doi.org/10.1109/ICSME55400.2025.00039 | ICSME 2025 |
| S13 | From Text to Multimodal: A Survey of Adversarial Example Generation in QA Systems | https://arxiv.org/pdf/2312.16156 | 2023 (arXiv:2312.16156) |

### Tier 2 — Strong secondary

| ID | Source | URL | Date/version |
|---|---|---|---|
| S7 | OWASP Gen AI Security Project — GenAI Red Teaming Guide | https://genai.owasp.org/resource/genai-red-teaming-guide/ | v1.0, Jan 23, 2025 |
| S11 | MT4NLP — Metamorphic Relations Catalog for NLP Systems | https://mt4nlp.github.io/ | Catalog tied to Cho ICSME 2025; 191 MRs |
| S12 | Giskard — Scan vulnerabilities / promote to test suite | https://docs.giskard.ai/oss/solutions/scan-vulnerabilities | 2025–2026 docs |

### Tier 3 — Contextual (corroboration only)

| ID | Source | URL |
|---|---|---|
| S14 | OWASP Gen AI — AI Red Teaming Initiative overview | https://genai.owasp.org/ai-red-teaming-initiative/ |

**Source count:** 10 Tier-1 + 3 Tier-2 = **13 distinct Tier 1–2 sources** (floor ≥3 satisfied).

**Contradictions surfaced (summary):**

| Topic | Position A | Position B | Resolution for rubric |
|---|---|---|---|
| MR false positives | Cho ~60% TP on LLM MR violations | Liu: small diverse MR set ≈ oracle detection | MRs for exploration + CI subset after TP audit; not sole gate |
| Coverage metric | Area/footprint stress tests | B-SLR structural loss (S4) | Report both; prefer structural for semantic gate-evasion |
| Adversarial generation | OWASP/Giskard LLM-generated scenarios | Deterministic replay for CI gates | LLM generation allowed in L2 only; L1 requires frozen probes |

---

## 6. Overlap statement

This persona researched **external adversarial and red-team methodology for extraction-QA gates only**. It did **not** open whisker production code, cite whisker `file:line`, score whisker, clone/fork/copy code, or duplicate:

- **`redteam/`** — per-converter defect reports on external tools (docling, marker, MinerU, etc.); this persona defines red-team *method* for QA gates, not converter benchmarking.
- **`persona/`** — prior code-level "adversary-gate-evasion" findings on whisker; this hands synthesis **criteria**, not a re-derived whisker verdict.
- **`p19-anti-gaming-goodhart.md`** (boundary) — P19 owns Goodhart defenses and gaming-vector checklist for all criteria; P18 owns attack taxonomy, layered process, MR probes, coverage, and probe catalog design.
- **`p09` / `p12` / `p13`** — metric validity, benchmark integrity, comprehension science respectively; P18 consumes their outputs (comprehension closure, per-axis reporting) without redefining those metrics.

Boundary held: **adversarial-robustness criteria + probe catalog design + external bar**, for synthesis assembly into the audit rubric's adversarial dimension.
