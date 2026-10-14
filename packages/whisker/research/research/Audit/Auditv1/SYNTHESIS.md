# SYNTHESIS — Whisker Professional-Grade Audit Methodology

**Role:** Final Opus synthesis of a methodology-only audit research project.
**Date:** 2026-07-18.
**Inputs:** `00-FRAME.md`, `00-ROSTER.md`, 30 Composer persona reports (`p01`–`p30`), 5 Opus verification passes (`opus-A` through `opus-E`).
**Scope boundary:** This document synthesizes only verified external methodology and the two declared project invariants (model sovereignty, advisory-only LLM). It does **not** inspect, score, or imply any audit of whisker production code. No whisker verdict is issued or implied. The instrument that will later be applied to code is `AUDIT-SCORECARD.md`; this file is the research spine that justifies it.

---

## 1. Executive verdict on the audit methodology

The research portfolio is **evidentially sound and, after the meta-review corrections, fit to become a professional-grade audit instrument for a pre-1.0, hybrid, fidelity-first, model-sovereign document-QA package.** The methodology verdict is:

> **Methodology band: Professional-grade audit design (upper), conditional on adopting the deduplications, gate triage, and enterprise-imitation demotions carried out below. Confidence: HIGH on the core (eight dimensions, seven gates, per-axis discipline, the five load-bearing invariants); MEDIUM on any numeric threshold (all thresholds are calibration-pending); LOW and explicitly deferred on the determinism dimension until the user and Sean supply concrete definitions.**

Three facts drive this verdict:

1. **The evidence base is real.** Opus-A re-fetched 10 of 10 load-bearing measurement-validity citations against live primary sources and found no hallucinations, including the high-risk 2026-dated arXiv papers. Opus-D audited provenance across all thirty personas and found the base overwhelmingly sound, with exactly one fabricated source that is quarantined below.
2. **The portfolio over-prescribed and the meta-reviews corrected it.** The raw swarm proposed 30+ hard-gate candidates and overlapping weight shares that sum past 100 percent. Opus-A and Opus-E triaged this to a non-compensatory layer of seven gates and a compensatory composite of eight dimensions. That correction is what makes the methodology usable rather than a rubric that fails everything.
3. **The methodology audits whisker against its own thesis, not against enterprise scale.** The load-bearing gates (advisory non-leakage, fail-not-partial, determinism-by-replay, per-axis reporting, untrusted-input mediation, baseline canary, licensing) are precisely the properties that define whisker's stated design. Auditing a project against its own thesis is the fairest possible frame, and it is the frame this instrument adopts.

The methodology is **not** ready to certify any absolute quality number, because every numeric operating point in the corpus is a placeholder awaiting calibration on a labeled whisker corpus that may not yet exist. The instrument therefore reports **bands with named flip conditions**, never a single certified score.

---

## 2. What was researched, and the quality of the evidence

### 2.1 Structure of the research

- **30 Composer persona reports**, organized in eight clusters: release/packaging/API/supply-chain (p01-p04), architecture/modularity/determinism (p05-p08), extraction and eval science (p09-p13), audit-framework and scoring design (p14-p17), adversarial and anti-gaming (p18-p19), documentation and operator UX (p20-p21), provenance/security/privacy/observability (p22-p25), and repository/framework case studies (p26-p30).
- **5 Opus verification passes**: `opus-A` (measurement validity), `opus-B` (hybrid/determinism doctrine), `opus-C` (engineering quality), `opus-D` (evidence provenance), `opus-E` (steelman and balancing). A, B, and E consolidated and triaged criteria; C consolidated engineering criteria; D audited citations for fabrication.

### 2.2 Source and evidence quality

Every persona was required to cite at least three Tier 1-2 primary sources, surface contradictions rather than hide them, tag an audit method and scoring hook, name a gaming vector with an anti-gaming guard, and grade its own evidence A-D. That structural discipline is the portfolio's biggest strength and is what made independent meta-review possible.

Load-bearing anchors verified verbatim against primary sources (opus-A ledger) include: TEDS (Zhong et al., ECCV 2020, [arXiv:1911.10683](https://arxiv.org/abs/1911.10683)); GriTS (Smock et al., ICDAR 2023, [arXiv:2203.12555](https://arxiv.org/abs/2203.12555)); olmOCR-Bench 7,010 tests / 1,402 PDFs and its explicit rejection of edit distance and LLM-as-judge for primary scoring ([arXiv:2502.18443](https://arxiv.org/abs/2502.18443)); JudgeBench objective-correctness near-random result (Tan et al., ICLR 2025, [arXiv:2410.12784](https://arxiv.org/abs/2410.12784)); the Coin-Flip judge 13.6 percent mean pairwise flip rate ([arXiv:2606.13685](https://arxiv.org/abs/2606.13685)); Horn and Keuper table-judge correlations r=0.93 vs TEDS 0.68 / GriTS 0.70 ([arXiv:2603.18652](https://arxiv.org/abs/2603.18652)); self-recognition causally driving self-preference (Pan et al., NeurIPS 2024, [arXiv:2404.13076](https://arxiv.org/abs/2404.13076)); DeepEval default-0.5 and promptfoo `threshold:0` gate footguns.

### 2.3 Known defect and mandatory quarantine

**Quarantined (binding, per opus-D):** the source cited in `p28-case-olmocr-marker-mineru.md` as **"MinerU2.5-Pro: Pushing the Limits of Data-Centric Document Parsing at Scale," arXiv:2604.04771 (Apr 2026)** does not resolve to a real primary source. It is treated as **fabricated**.

- **Excluded:** every claim that depends on that source, specifically the MinerU2.5-Pro-specific assertions in `p28` criterion C3 (the "OmniDocBench v1.6 Base/Hard/Full tier protocol," "Multi-Granularity Adaptive Matching fixing v1.5 element-matching bias," and any MinerU2.5-Pro leaderboard numbers).
- **Preserved:** the `p28` report itself remains in the repository as research history. It is not deleted.
- **Survives on independent evidence:** the *general* lesson of C3 (published benchmark scores must pin an eval-protocol version, and unversioned scores are stale evidence) stands on OmniDocBench (Ouyang et al., CVPR 2025, [arXiv:2412.07626](https://arxiv.org/abs/2412.07626)) and olmOCR's leakage-resistant post-hoc benchmark design ([arXiv:2502.18443](https://arxiv.org/abs/2502.18443)), both real and independently verified. The lesson is retained; the MinerU2.5-Pro evidence for it is not.
- **Also downgraded (opus-A, not fabrication):** the olmOCR head-to-head point estimates in `p28` (75.5 / 70.1 / 61.5) are version-drift and are used **directionally only**; the ranking and the "per-axis diverges, composite hides it" lesson hold, the exact numbers do not.

Nothing else in the corpus was found to be fabricated. The MinerU *serving* lessons (C1, from MinerU official Docker and CLI docs) rest on real Tier-2 sources and are retained.

---

## 3. Nonredundant audit-method portfolio (why each method exists)

The frame's method taxonomy collapses, after deduplication, to a portfolio where each method has a distinct job. Redundancy across personas is benign at the research level but becomes weight inflation if left additive, so overlaps are merged here (opus-A §5, opus-E §10).

| Method | Why it exists | Primary personas |
|---|---|---|
| Conformance checklist | Verify objective, binary contract items (exit codes, SPDX tags, `py.typed`, stream discipline) | p01, p02, p21, p22 |
| Maturity-model scoring (0-4) | Grade gradational quality where a binary is too blunt | p14, and every dimension ladder |
| Comparative benchmarking | Set the external bar from exemplars without cargo-culting them | p26-p30 |
| Metric construct-validity audit | Ensure a metric measures what the gate claims (TEDS pairs, null-eligibility, edit distance is invalid for math) | p09, p13, opus-A |
| Calibration / operating-point audit | Set thresholds from labeled data, not vendor defaults | p16 |
| Adversarial / red-team probing | Find inputs that pass gates while corrupting meaning | p18 |
| Anti-gaming / Goodhart stress | Ensure the rubric itself cannot be satisfied cosmetically | p19 |
| Reproducibility replay | Verify determinism and regression claims by re-running | p06, p07 |
| Documentation-completeness audit | Ensure an operator/agent can succeed from docs alone | p20 |
| Provenance / license conformance | Ensure lawful redistribution and honest origin | p22 |
| Observability / fault-injection | Prove failure behavior under injected faults, not just happy paths | p25 |

Meta-scoring methods (p14-p17, p30) are **not** product methods; they define how the audit scores, and carry **0 percent product weight** (opus-A layer 3, opus-E T12).

---

## 4. Smallest-complete core audit vs optional extended modules

**Governing fairness principle (opus-E §4):** *a criterion may gate only against a property whisker actually claims.* If whisker declares "gates are uncalibrated, Stage 0," the absence of calibration is a documented boundary, not a failure. If whisker declares "cloud inference is dev-only," the cloud-governance check tests the default, not the possibility.

### 4.1 Smallest complete core (executable from artifacts alone)

The core is roughly one third of the raw surface: **eight dimensions and seven gates**, all executable by reading docs and CI config, running the pipeline once with trace and debug, replaying once, inverting one canary, grepping artifacts for leaked secrets, and inspecting the dependency manifest. **No source inspection is required to run the core.**

### 4.2 Optional extended modules (run only on the matching claim)

| Module | Personas | Activation trigger |
|---|---|---|
| M1 Calibration & threshold provenance | p16, p17 | whisker claims *calibrated* production gates |
| M2 Ground-truth corpus rigor (IAA, adjudication) | p11 | labels are *gate-bearing* |
| M3 Supply-chain hygiene (SBOM/SLSA beyond lockfile+scan) | p03 | any formal release/attestation claim |
| M4 Observability depth & fault-injection breadth | p25 | claims "production-grade" ops |
| M5 Privacy / data governance (light) | p24 | debug retention or cloud inference in use |
| M6 Provenance/licensing depth (per-file audit) | p22 | redistribution / fork claims |
| M7 Comprehension eval battery | p13, p28 | claims "measures comprehension" |
| M8 Scoring-system meta-conformance | p14, p15, p30 | always, as audit self-check (0 percent product weight) |
| M9 Case-study benchmarking | p26-p30 | informational reference only |

---

## 5. Final 8 audit dimensions, weights, rationale, compensability

Weights govern the **compensatory maturity composite only**. They were assigned once per deduplicated dimension (never summed across personas) and normalized to exactly 100 (opus-A RJ5, opus-E §5). The seven hard gates in §6 sit **above** the composite: a perfect composite with any failed gate is an overall fail.

| # | Dimension | Weight | Rationale | Compensability boundary |
|---|---|---|---|---|
| D1 | Epistemic separation (hybrid deterministic core / advisory overlay) | 20 | The defining whisker invariant; a tool that violates it is not a lesser whisker but a different, unsound tool | Compensatory within its own subcriteria; the underlying non-leakage rule is a hard gate (G1) and cannot be bought back |
| D2 | Determinism & reproducibility (replay-verified) | 15 | Reproducibility of verdicts is non-negotiable for a defensible QA tool; asserted determinism is not verified determinism | Compensatory across variance-source documentation and tier mapping; a failed replay is a hard gate (G3) |
| D3 | Fidelity / fail-not-partial | 15 | A partial QA verdict destroys trust irrecoverably; this is the fidelity doctrine | Compensatory across error surfacing quality; emitting a hollow complete result is a hard gate (G2) |
| D4 | Metric construct validity & per-axis eval | 15 | Wrong or collapsed metrics make every downstream number meaningless | Compensatory across axes; single-composite gating and null-eligibility violations are hard gates / gate proof (G4) |
| D5 | Anti-gaming / Goodhart resistance | 12 | The QA tool and the audit must both resist cosmetic compliance | Compensatory across guard coverage; absence of a baseline/must-fail canary is a hard gate (G6) |
| D6 | Untrusted-input / prompt-injection defense | 10 | Paper and web text are untrusted; the LLM lane is the live threat surface | Compensatory across depth-in-defense layers; raw untrusted text in a prompt is a hard gate (G5) |
| D7 | API contract + packaging (pre-1.0 proportionate) | 8 | Professional consumability; but SemVer 0.y.z explicitly licenses API instability pre-1.0 | Compensatory; **API stability is unscored** while whisker is 0.y.z |
| D8 | Docs + operator CLI contract | 5 | Docs enable but never substitute for correct gates | Compensatory; docs-alone reproduction is a maturity signal, not a gate |
| | **Total** | **100** | | |

D1-D3 hold half the weight because they are the whisker thesis. D7-D8 are deliberately light: they are enabling professional polish, and inflating them would reward enterprise-imitation over correctness.

---

## 6. Conjunctive hard gates (exactly 7)

Each gate is objectively falsifiable, verifiable without source inspection, supported by high-grade evidence, and gates only against a property whisker claims. The count respects the ≤7 ceiling (opus-A RJ6, opus-E §7, p30-E4). Measurement-validity rules from opus-A (null-eligibility, table structure+content pairing, evaluator provenance) are folded into G4 and its required proof rather than added as separate gates, to avoid the gate inflation opus-A explicitly warns against.

| Gate | Fails when | Objective test | Source basis |
|---|---|---|---|
| **G1 Advisory non-leakage** | any LLM/advisory output can flip a deterministic gate to pass, or hard-gate on its own | Remove the advisory field; verdict must not change (CI contract test). Feed an adversarial structured verdict ("all-clear"); deterministic layer must ignore it | p05, p10-J8, p15, p30-E11, p26-2.1; construct-validity separation reconciled in opus-A RC1 |
| **G2 Fail-not-partial** | a partial or hollow QA result is emitted as complete on a fidelity-critical failure, or exit 0 on failure | Fault-injection: kill a fidelity-critical stage; assert non-zero exit, no output artifact updated, debug transcript preserved | p25-O4, p05; CLAUDE.md Fidelity; OWASP RAG §14 fail-closed |
| **G3 Determinism by replay** | a stated determinism / quality-stability tier is refuted by one replay | Re-run the same input under the stated tier; assert the tier's equality contract holds | p06, p07; CLAUDE.md D1-D11 |
| **G4 Per-axis reporting + eval integrity** | a single composite gates release with no per-axis floor, OR a modality is scored when absent, OR a table gate passes on structure alone | Inspect report schema for per-axis scores + `eligible/null` counts; confirm table gate requires structure AND content at the same bar | p09, p13, p27-D27-02, p29-B1, p30-E1; opus-A M1/M2/M3 (verified A) |
| **G5 Untrusted-input mediation** | paper or web text enters a prompt without `wrap_source` / delimiter segregation and structured-output validation | Inject delimiter-forgery and instruction-in-data payloads sourced from document body; assert wrapping holds and structured validation rejects | p23; CLAUDE.md prompt-injection defense; OWASP LLM01:2025 |
| **G6 Baseline canary (inverted)** | the QA gate lacks a zero-authoring baseline / must-fail canary on 100 percent of pages | Invert a canary (feed known-bad empty/garbled/repetition output); the gate MUST fail. If it passes, G6 fails | p28-B1/B2 (olmOCR, verified), p04, p19 |
| **G7 Licensing / attribution** | an incompatible license combination is shipped, or required third-party attribution is missing | Build attribution inventory from artifact contents; run the Apache↔GPL-2.0-only and BSL-1.0 full-notice checks | p22 (FSF + Apache + SPDX), p26-2.10, p29-C2 |

**Deliberately not gates (maturity-scored only):** threshold calibration (unless production-claimed), OpenSSF/TSC/foundation governance, SLSA/SBOM, overload/load testing, full privacy framework, release cadence, API stability. Cloud-inference governance becomes a gate only if cloud is the default path.

---

## 7. Maturity, evidence grades, confidence, bands, uncertainty

### 7.1 Maturity semantics (0-4, per dimension)

- **0** Absent or ad hoc.
- **1** Present but cosmetic (a flag exists, a log line exists) with no proven behavior; anti-gaming guard not closed.
- **2** Functional and documented, but not verified under fault/adversarial conditions or thresholds uncalibrated.
- **3** Verified behavior: gate teeth demonstrated (canary fails when inverted, replay holds, fault-injection asserts fail-closed), thresholds calibrated or explicitly flagged.
- **4** Level 3 plus independent-evidence triangulation and durable regression protection.

A gate failure caps the affected dimension at the "unsound" band regardless of maturity level.

### 7.2 Evidence grades (A-D) and confidence

- **A** multiple Tier-1 corroborating; **B** single Tier-1 or converging Tier-2; **C** Tier-3 only or contested; **D** Tier-4/speculative.
- Confidence is **high** where evidence is A and the check is executable today; **medium** where the check depends on an uncalibrated threshold; **low** where a definition is missing (determinism, §10).
- Any score resting on an LLM-judge signal inherits at most grade **B** and is advisory (opus-A M10/M11).

### 7.3 Score bands (report a band, never a point)

| Band | Entry condition |
|---|---|
| Unsound | any gate G1-G7 fails |
| Emerging | all gates pass; composite ≥ 40; grade ≥ C |
| Professional-grade | all gates pass; composite ≥ 65; core dims D1-D4 grade ≥ B; ≥1 replay and ≥1 inverted canary evidenced |
| Best-defensible | Professional plus every *claimed* extended module at ≥ level 3; band width ≤ one tier |

### 7.4 Uncertainty propagation

The composite inherits the **weakest evidence grade** among its load-bearing inputs (weakest-link, opus-A layer 4, p30-E12). The band **widens** whenever any load-bearing input is grade C, contested, or uncalibrated. No two-decimal precision on uncalibrated or LLM-judge inputs; round to defensible precision and state the band, its width, and the named drivers of that width.

---

## 8. Anti-gaming / Goodhart controls, disagreement, flip conditions

### 8.1 Anti-gaming controls (cross-cutting, from p19 and opus-A/E)

Every load-bearing criterion must pass the p19 G1-G10 checklist before it is scored: orthogonal corroboration (no single-metric gate), non-compensatory integrity gates, canaries that must fail, holdout secrecy (fit set separate from commit set), reference-metric integrity (locked evaluator vs mutable script), invariance to format-only perturbation, falsifiable wording (no adjective-only bars), sensitivity analysis on weights, optimization budget caps on proxy metrics, and mandatory per-axis visibility. The audit's own residual Goodhart risk (a thirty-input rubric satisfied cosmetically) is answered by making the composite subordinate to the seven gates and requiring at least one inverted canary (G6) on the audit's own gate list.

### 8.2 Disagreement resolution (contested criteria)

When sources conflict, record both positions and prefer the higher-tier construct-validity argument (frame §6.5). Worked reconciliations carried forward: (a) the LLM judge is a *more* construct-valid table metric than TEDS/GriTS, yet stays advisory-only for determinism and model-sovereignty reasons, not because it measures tables badly (opus-A RC1); (b) binary unit tests gate the construct-invalid cases (math sign, cell adjacency, order), reference-matching metrics are per-axis diagnostics (RC2); (c) graceful degradation applies to availability subpaths, fail-not-partial applies to fidelity subpaths (RC4); (d) reliability and validity are orthogonal and both must be reported (RC5).

### 8.3 Flip conditions (verdict fragility, named)

1. **Advisory→gating reclassification.** If any advisory signal turns out to influence pass/fail, G1 fails → Unsound. Highest-impact flip.
2. **Replay outcome.** A determinism replay flipping pass→fail flips G3 → Unsound.
3. **Version-phase claim.** whisker declaring ≥1.0 / "stable API" activates the API-stability bar at full strength (deprecation policy becomes gate-eligible).
4. **Calibration claim.** "Uncalibrated Stage 0" keeps calibration a boundary; "production-calibrated" makes an uncalibrated threshold a failure.
5. **Label role.** Golden labels declared gate-bearing activate IAA/adjudication as required (M2).
6. **Cloud default.** If cloud inference is the default, cloud-governance becomes a gate.

---

## 9. Benchmark / eval doctrine

- **Per-modality metrics, never a lone composite.** TEDS and TEDS-S (structure only), GriTS_Top/Con/Loc, NID (insert/delete) vs NED/Levenshtein (substitutions, not directly comparable), reading-order edit, formula CDM, detection P/R/F1 and mAP are construct-distinct. The OmniDocBench "Overall" formula literally omits reading order, which is the point: any single quality number silently drops an axis (opus-A VF1, verified).
- **Table fidelity requires structure AND content, paired.** A structure-only pass with a content fail is the signature of cosmetic HTML compliance masking OCR/content corruption (opus-A VF2). This is folded into G4.
- **Null-eligibility.** Absent modality → `null`, never imputed 0.0 or 1.0; composites computed over eligible units only with the denominator disclosed (opus-A VF3, folded into G4).
- **Fidelity vs comprehension.** Comprehension is never inferred from fidelity metrics. Edit distance is construct-invalid for semantics ("x^i vs x_i" is one character but a meaning inversion). Comprehension is measured by fact-recovery/closed-book QA or binary unit tests on labeled data, not surface similarity (p13, p28-A2, opus-A VF4).
- **Ground-truth independence.** author ≠ annotator ≠ adjudicator ≠ evaluator; judge family ≠ generator family, or self-preference measured and bounded (self-recognition causally drives self-preference, opus-A VF7). Labels need adjudication and provenance; convenience samples must not be sold as "ground truth" (p11).
- **Calibration.** Every threshold is explicit with recorded provenance (date, corpus, TPR/FPR) or flagged "borrowed, uncalibrated." Vendor defaults (DeepEval 0.5, promptfoo `threshold:0`) are documented footguns where "has an eval" hides "gate never fires" (opus-A VF9).
- **Holdout firewall.** Separate fit set (calibration) from commit set (locked holdout). Contamination is inflated non-generalizing performance, detected via generalization to rephrased/reference benchmarks, not only n-gram overlap (p12, p19).
- **Advisory LLM-judge validation.** Multi-trial aggregation (single trials flip up to 56 percent), position-bias and self-preference measurement, chance-corrected human agreement (Krippendorff's α preferred over κ), and an objective-corruption stratum with deterministic oracle labels. Until a labeled corpus exists, judge-quality criteria are soft caps (dimension ≤ level 2), not hard gates (opus-A RJ4).

---

## 10. Hybrid / determinism doctrine

### 10.1 Authoritative vs advisory (project invariant, not universal standard)

The strict deterministic core is **authoritative**; the opt-in LLM overlay is **advisory** and demote-only. This is a **declared whisker project invariant** (CLAUDE.md model-sovereignty and the advisory-only boundary), reinforced by external practice (OWASP treats LLM output as untrusted; eval frameworks keep LLM-judge scores non-gating without validation), **but it is not a universal external standard** and must not be labeled as one. External evidence supports the *mechanism* (advisory scores need validation before gating); the *choice* to forbid LLM gating outright is doctrine.

Similarly, **model sovereignty** (open-weight, self-hosted inference) is a whisker invariant justified by determinism, security, and fine-tuning goals, not an external professional requirement. The audit scores governance controls, not the ideology: cloud is permissible with documented no-training and retention terms; the invariant is that self-hosted is the default (p24-G5, opus-B, opus-C).

### 10.2 Load-bearing sub-doctrine (external-supported)

- **Demote-only ratchet:** advisory confidence can lower but never raise a deterministic verdict.
- **Replay tiers:** determinism is claimed at a stated tier and verified by re-running (G3). Tiers span bit-exact, quality-stable (same findings/verdicts/structure), stated-precision, and non-guaranteed. Bit-exact reproducibility on hosted endpoints is impossible without batch-invariant kernels (CLAUDE.md Determinism).
- **Fail-not-partial:** fidelity-critical failure stops the run (G2).
- **Prompt-injection boundary:** untrusted bytes are wrapped and validated before any prompt; injection may corrupt an advisory signal but must never flip an authoritative gate (G1 + G5).

### 10.3 Unresolved input (must be obtained before D2 can be applied)

`p07` was tasked with reconciling two determinism doctrines, "the user's" and "Sean's." Both are **undefined open questions in the report itself** (opus-B and opus-E confirm p07's standalone value is thin for exactly this reason). The concrete definitions **cannot be invented**. The determinism dimension (D2) and gate (G3) are structurally ready but cannot be *applied* until the following are answered:

1. What is the user's determinism definition, at which tier (bit-exact, quality-stable, stated-precision, non-guaranteed), and over which artifacts (verdict, structure, byte output)?
2. What is Sean's determinism definition, at which tier and over which artifacts?
3. Where do they agree, where do they diverge, and which governs a release gate when they diverge?
4. What is the exact equality contract a replay must satisfy to "pass" G3 (semantic equality of findings, or byte equality)?
5. Which variance sources are in-scope (concurrent in-flight requests, temperature, unordered set iteration, MoE routing) and which are accepted?

Until these are answered, D2 is scored provisionally and flagged low-confidence; G3 uses semantic quality-stability as the interim contract and is marked calibration-of-definition-pending.

---

## 11. Professional package / docs / CLI / provenance / security / observability bars

These are the enabling professional bars, stated at the pre-1.0-proportionate level with enterprise-imitation traps removed (opus-C, opus-E §4).

- **Packaging (p01):** PEP 621 `pyproject.toml`, `requires-python`, correct wheel/sdist, unambiguous license, categorized changelog, console entry points. Wheel/sdist correctness and license clarity are the strong items.
- **API (p02, p08):** documented public surface, `__all__`, `py.typed` if a typed API is claimed, "library returns data, caller persists" boundary, no import cycles, core does not depend on optional LLM extras. **API stability is unscored while 0.y.z** (SemVer 2.0.0 "Major version zero: anything MAY change at any time," primary-verified in opus-E).
- **Supply chain (p03):** core keeps lockfile plus a CI vulnerability scan and heavy LLM deps isolated in extras. SBOM/SLSA/signed attestation are an optional module, not a core gate.
- **Docs (p20):** Diátaxis quadrant typing, a greppable contract doc (deterministic/advisory boundary, exit-code table, trace/debug spec, calibration status, known gaps, architecture map), runnable examples, and root `AGENTS.md` plus package `CLAUDE.md` (≤200 lines each, non-conflicting). The operative test is docs-alone operator reproduction.
- **CLI (p21):** documented exit-code contract (including that a check mode may exit non-zero on findings by design), stdout-is-result / stderr-is-progress discipline, machine-readable `--json`, triaged actionable summaries, TTY-aware output. U1 (exit codes), U2 (stream discipline), U6 (actionable errors) are the floor.
- **Provenance (p22):** per-file SPDX, `LICENSES/` corpus, third-party attribution derived from artifact contents, BSL-1.0 full-notice handling, honest provenance for re-implemented algorithms.
- **Security (p23):** trust-boundary inventory, delimiter hardening, structured-output validation in deterministic code, tool least-privilege, zero-trust handling of LLM outputs, a document-embedded injection test corpus, and honest "injection cannot be fully eliminated" disclosure.
- **Observability (p25):** structured logging (no library `print()`), correlation IDs, deliberate trace (concise progress, every state field, no silent steps) vs debug (full untruncated I/O) split, fail-closed on fidelity paths, differentiated error surfacing, and a CI fault-injection suite with negative assertions.

**Enterprise imitation traps removed (do not apply as gates):** stable-API/deprecation gate, release-cadence matching, OpenSSF silver / TSC / foundation hosting, SLSA/SBOM ceremony, overload/death-spiral testing, continuous production chaos, full NIST Privacy Framework + ISO 27701 + DPA reviews, datasheets-for-datasets in full, mutation testing at scale, full OS×Python matrix breadth, typed full-layout IR / HTML review widgets, and scoring-system design as product weight.

---

## 12. Transferable lessons from case studies (and where not to cargo-cult)

| Exemplar | Adopt (transferable) | Do NOT cargo-cult |
|---|---|---|
| **LangExtract** (p26) | Explicit grounding provenance on every span (`char_interval` or explicit ungrounded sentinel); prompt-example alignment validation; provenance-linked review artifacts; extras + entry-point provider pattern; opt-in URL fetch | Cloud SDK (`google-genai`) in core; `suppress_parse_errors=True` fail-soft default; multi-pass stochastic recall on the gate path; leaving ungrounded spans silently to the caller |
| **Docling** (p27) | Typed internal truth separated from export projections; per-modality eval harness with published recipes; span/role-aware table grid verification; golden regeneration protocol with double review; technical report with pinned hardware/dataset | Full-layout IR ontology; ~195-release cadence as a quality signal; OpenSSF silver / TSC / LF governance at whisker scale; lazy optional-dep imports (violates whisker no-lazy-import invariant unless scoped to extras) |
| **olmOCR / Marker / MinerU** (p28) | olmOCR zero-authoring per-page BaselineTest (non-empty, >30-char repetition, charset sanity); binary fact-level unit tests instead of edit distance / LLM-judge for primary scoring; server/client inference separation; throughput reported with hardware and serial+batch | English-centric CJK/emoji charset exclusion (WG21 has legitimate Unicode math); LM-pretraining downstream eval scale; Marker cloud LLM defaults and LLM-judge-as-primary; **MinerU2.5-Pro claims (quarantined, fabricated source)** |
| **unstructured / Nougat / Surya** (p29) | Optional-dependency matrix by format/mode; Nougat per-modality multi-metric tables with limitation prose adjacent to numbers; Surya code-vs-weights dual-license transparency; shared inference manager; breaking-change migration guides | 20+ format ingest breadth; Nougat legacy `setup.py`; multilingual internal benchmarks as domain-fit evidence for WG21; treating a GitHub license badge as sufficient for weight rights |
| **Eval frameworks** (p30) | Suite-of-checks (versioned, named, diffable); score+reason on every number; explicit calibrated thresholds; conjunctive gates independent of composite; regression baseline pinned; severity tiers; banded composite reporting; adversarial score orthogonal to quality | Cloud-default judge models (Ragas/DeepEval/TruLens demos); LLM-judge scores as CI gates without validation; Ragas RAG axis names on document-QA; promptfoo pass-rate alone without per-axis floors |

**General cargo-cult warning:** these are converters and general extraction/eval tools; whisker is a fidelity-first QA gate over converted markdown. Transfer the *pattern* (grounding, per-modality eval, baseline canary, typed truth, suite-of-checks), never the *cloud defaults, fail-soft semantics, or enterprise governance machinery*.

---

## 13. Source register summary and traceability

- **30 persona reports** each carry a self-contained source table (Tier 1-2 floor ≥ 3 satisfied in every report). Traceability from any criterion in `AUDIT-SCORECARD.md` runs: scorecard subcriterion → dimension → persona report `pNN-*.md` → that report's source table.
- **5 meta-reviews** provide the binding corrections: `opus-A` (measurement-validity verification ledger, deduplicated M1-M12, four-layer architecture), `opus-B` (hybrid/determinism doctrine, user-vs-Sean open question), `opus-C` (engineering-quality consolidation), `opus-D` (provenance audit and the MinerU2.5-Pro quarantine), `opus-E` (steelman, 8-dimension core, 7-gate set, enterprise-imitation demotion list, bands, flip conditions).
- **Primary-source anchors** for load-bearing claims are inline in §2.2 and §12 with stable URLs; the full per-claim ledger lives in `opus-A` §1 and §8.

---

## 14. Honest limitations and open questions

1. **No labeled whisker corpus is assumed to exist.** Every numeric threshold in the corpus is a placeholder. The methodology can be applied structurally today, but calibration (M1) and judge-quality gates (M10) cannot fire until labeled, stratified, adjudicated pairs exist. Gating on calibration before the corpus exists would fail whisker for being early, not wrong.
2. **The determinism dimension is definition-blocked.** D2/G3 cannot be applied until the five questions in §10.3 are answered by the user and Sean.
3. **Judge validation is deferred.** The advisory-judge battery is a soft cap until it can actually run on labeled data.
4. **Case-study point estimates drift.** olmOCR head-to-head numbers are directional only; do not quote them as fixed.
5. **One fabricated source was found and quarantined.** The audit assumes no other undetected fabrication, on the strength of opus-A's 10/10 verification and opus-D's provenance pass, but this is a sampled assurance, not exhaustive.

### Exact inputs required before the later code audit

- Answers to the five determinism questions (§10.3).
- Whisker's declared version phase (0.y.z vs ≥1.0) and whether a stable-API claim is made.
- Whisker's declared calibration status (Stage 0 / uncalibrated vs production-calibrated) and, if calibrated, the calibration records.
- Whisker's declared label role (advisory vs gate-bearing) for its golden corpus.
- Whisker's declared default inference path (self-hosted vs cloud) and, if cloud is reachable, its data-handling terms.
- The location and licensing metadata of the whisker package (`packages/whisker/`) so G7 can run against artifact contents.

---

## 15. Anti-convergence check (what the swarm over-prescribed, what the meta-review corrected)

- **Over-prescribed: 30+ hard gates.** The raw swarm proposed a non-compensatory layer so large it would fail nearly every real system. **Corrected:** triaged to seven gates with written rationale (opus-A RJ6, opus-E §7).
- **Over-prescribed: additive weights.** Overlapping "% of composite" proposals summed past 100. **Corrected:** weight assigned once per deduplicated dimension, normalized to 100; meta-scoring moved to 0 percent product weight (opus-A RJ5, opus-E T12).
- **Over-prescribed: enterprise imitation.** OpenSSF/TSC governance, SLSA/SBOM, overload testing, full privacy framework, release cadence, API-stability gate were proposed at gate strength. **Corrected:** demoted to optional modules or maturity notes, gated only against claims whisker makes; SemVer 0.y.z primary-verified as licensing pre-1.0 API instability (opus-E §4).
- **Over-prescribed: false precision.** Judge floors (κ ≥ 0.50, flip ≤ 0.15, corruption acc ≥ 0.70) and head-to-head leaderboard numbers were presented as fixed. **Corrected:** dimensions kept, numbers struck as calibration-pending; point estimates used directionally only (opus-A RJ1/RJ3).
- **Over-prescribed: construct confusion.** "LLM judge is advisory-only" read as if the judge measured tables badly. **Corrected:** advisory-only is a determinism/sovereignty decision; the judge is in fact the more construct-valid table metric, and the two claims were separated (opus-A RC1).
- **Fabrication caught.** A single fabricated MinerU2.5-Pro source and its dependent claims were quarantined while the raw report was preserved (opus-D).

**Bottom line:** the methodology is professional-grade and ready to guide a later code audit, once the determinism definitions and whisker's own claims are supplied. It scores whisker against its own thesis, reports bands not points, and refuses to certify any number that has not been calibrated.
