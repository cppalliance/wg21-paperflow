# Meta-Reviewer D — Evidence & Provenance Audit

**Role:** Meta-Reviewer D (audit-of-the-audit; evidence provenance).
**Date:** 2026-07-18.
**Scope of THIS document:** audit the *evidence* in `00-FRAME.md`, `00-ROSTER.md`, and
`p01`–`p30`. URL validity, source-tier accuracy, recency/version, does-the-source-support-
the-criterion, licensing/provenance/fork hygiene, contradictions, overlap. Verify all
proposed hard gates and weights. Build a source-quality + coverage matrix. List
unverifiable / hallucinated / mis-tiered claims. Define what may enter synthesis.
**Explicit non-goal (per user):** no whisker production-code inspection, no whisker scoring.

---

## 0. Method

1. Read all 32 files (frame, roster, p01–p30) end-to-end.
2. Extracted every report's self-declared Tier 1–2 count and its load-bearing anchors.
3. Web-verified the highest-risk citations: every **forward-dated arXiv preprint**
   (2025–2026 IDs) and every load-bearing case-study anchor, because fabricated-but-
   plausible preprints are the dominant hallucination vector in this corpus.
4. Canonical standards (PEP/PyPA, OWASP LLM Top 10 2025, NIST AI RMF / AI 100-2 / AI 600-1 /
   Privacy Framework, SLSA, SPDX, ISO/IEC 27701, GDPR, GRADE, Krippendorff, TEDS/GriTS,
   ROC/PR, Diátaxis, OpenTelemetry, Google SRE Book, Principles of Chaos, Great Expectations)
   are treated as **high-confidence real** by recognition; only novel/preprint/version-
   specific claims were individually fetched.

**Verification verdict headline:** the evidence base is **overwhelmingly sound**. Of the
~250+ distinct citations, exactly **one fabricated Tier-1 source** was found (p28), plus a
small set of minor version/count imprecisions. All other web-checked anchors resolved to
real, correctly-tiered, on-topic sources.

---

## 1. Web-verified anchors (spot-check results)

| Citation | Where | Claimed | Verified reality | Verdict |
|---|---|---|---|---|
| olmOCR 2 — *Unit Test Rewards for Document OCR*, arXiv:2510.19817 | p28 S2, A3 | Tier 1, Oct 2025 | Real. Title, date, RLVR/binary-unit-test content all match. | ✅ REAL, correct tier |
| olmOCR — arXiv:2502.18443 | p28 S1 | Tier 1, Feb 2025 | Real (Poznanski et al.). | ✅ REAL |
| OmniDocBench, arXiv:2412.07626 (CVPR 2025) | p12, p28 S3 | Tier 1, Ouyang et al., 1,651 pages | Real. CVPR 2025, 1,651 pages, author match. | ✅ REAL, correct tier |
| Docling Technical Report, arXiv:2408.09869 | p27 S1 | Tier 1, IBM, 225-page test set | Real. 225-page set (3 arXiv + 2 IBM Redbooks) matches; v2 Oct 2024. | ✅ REAL |
| Google LangExtract v1.6.0 (PyPI 2026-07-02) + release history | p26 | v1.0.9 2025-08-31 … v1.6.0 2026-07-02 | Real. PyPI/GitHub release dates match report line-for-line; DOI 10.5281/zenodo.17015089 correct. | ✅ REAL (see §4 minor count nit) |
| Goel et al., ML4H 2023, arXiv:2312.02296 | p26 T1-1 | Tier 1 | Real (PMLR 225, Google Research). | ✅ REAL |
| **MinerU2.5-Pro, "Wang et al.", arXiv:2604.04771v2, Apr 2026** | **p28 S4** | **Tier 1** | **FABRICATED.** Real paper is *MinerU2.5* (no "-Pro"), **Niu et al.**, **arXiv:2509.22186**, **Sept 2025**. No such ID as 2604.04771; no "-Pro" variant; wrong author, title, date. | ❌ **HALLUCINATED + mis-tiered** |
| MinerU2.5, arXiv:2509.22186 | (correct source) | — | Real (Niu et al., Sept 2025). This is what p28 *should* have cited. | ✅ REAL (not the one cited) |

Canonical-standard anchors carrying the security/privacy/observability/eval-method clusters
(OWASP LLM01/05/06:2025, NIST AI 100-2 E2025, NIST AI 600-1, NIST Privacy Framework, GDPR,
Greshake arXiv:2302.12173, Nougat arXiv:2308.13418, Ragas arXiv:2309.15217, OpenTelemetry,
Google SRE Book, Great Expectations, promptfoo, Cavoukian PbD, OMB M-24-10, ISO/IEC 27701) are
**high-confidence real** and correctly tiered; no anomaly on recognition.

---

## 2. Source-quality & coverage matrix (per report)

Floor = `00-FRAME.md` §4: ≥3 distinct Tier 1–2 primary sources, stable URL + date/version.

| Rpt | Dimension | Self-declared T1–2 | Floor | Provenance verdict |
|---|---|---|---|---|
| p01 | release-readiness | ≥3 (PEP/PyPA, semver, packaging guides) | ✅ | Canonical standards; sound |
| p02 | API contract | ≥3 (`__all__`, py.typed, PEP typing, deprecation) | ✅ | Sound |
| p03 | dependency/supply-chain | ≥3 (SLSA, SBOM/SPDX, OSV/vuln) | ✅ | Sound |
| p04 | CI/CD & test maturity | ≥3 (mutation/metamorphic, matrices) | ✅ | Sound |
| p05 | hybrid architecture | ≥3 | ✅ | Pattern-inferred criteria flagged B by author; honest |
| p06 | determinism/reprod. | ≥3 (incl. batch-invariance) | ✅ | Sound |
| p07 | dual-determinism | ≥3 | ✅ | Correctly flags "user vs Sean" as open question (mirrors frame §10) |
| p08 | modularity/boundaries | ≥3 (import-linter, acyclic) | ✅ | Sound |
| p09 | extraction metrics | ≥3 (TEDS, GriTS, NID) | ✅ | Benchmark-defining papers; sound |
| p10 | LLM-as-judge | ≥3 (bias, calibration) | ✅ | Sound |
| p11 | ground-truth corpus | ≥3 (Krippendorff α, IAA) | ✅ | Sound |
| p12 | benchmarking | ≥3 (OmniDocBench verified) | ✅ | Sound |
| p13 | comprehension vs fidelity | ≥3 | ✅ | Sound |
| p14 | audit maturity model | ≥3 (OpenSSF/SAMM-style) | ✅ | Sound |
| p15 | weighted rubric | ≥3 | ✅ | Sound |
| p16 | threshold calibration | ≥3 (ROC/PR) | ✅ | Sound |
| p17 | score uncertainty | ≥3 (GRADE-style) | ✅ | Sound |
| p18 | adversarial method | ≥3 (metamorphic relations) | ✅ | Sound |
| p19 | anti-gaming/Goodhart | ≥3 | ✅ | Sound |
| p20 | documentation/agent | ≥3 (Diátaxis) | ✅ | Sound |
| p21 | operator/CLI UX | ≥3 (exit-code/stream discipline) | ✅ | Sound |
| p22 | provenance/licensing | ≥3 (SPDX, BSL-1.0, license-compat) | ✅ | Sound |
| p23 | security/prompt-injection | 7 T1 + 3 T2 = 10 | ✅ | All canonical (OWASP/NIST/Greshake); **strongest evidence base** |
| p24 | privacy/governance | 9 T1 + 3 T2 = 12 | ✅ | Canonical; sound |
| p25 | observability/failure | 11 T1 + 2 T2 = 13 | ✅ | Canonical (OTel/SRE/OWASP/Chaos); sound |
| p26 | LangExtract case | 13 | ✅ | Anchors web-verified real; sound (minor count nit §4) |
| p27 | Docling case | 4 T1 + 8 T2 = 12 | ✅ | TR + official repo/docs verified; sound |
| p28 | olmOCR/Marker/MinerU | 4 T1 + 6 T2 = 10 | ✅ (nominal) | **1 of 4 Tier-1 sources fabricated (S4).** olmOCR/OmniDocBench anchors real. See §3 |
| p29 | unstructured/Nougat/Surya | 3 T1 + 11 T2 = 14 | ✅ | Real projects; Nougat/OpenRAIL anchors sound. Correctly debunks its own roster lead ("unstructured license change" → no relicensing) |
| p30 | eval-framework family | 2 T1 + 15 T2 = 17 | ✅ | Official framework docs; sound |

**Coverage:** all 13 required areas (frame §8) covered by ≥2 non-redundant lenses except
the intentional single-owner niches (P22 provenance, P25 observability). No coverage gap.
Every report includes a §6 overlap statement asserting no whisker `file:line` inspection and
no duplication of the named prior folder (`persona/`, `llm-stack/`, `langextract/`, `redteam/`,
`buildvsbuy/`); these are self-declared but specific, mutually consistent, and consistent with
the frame §3 overlap map. No overlap violation detected in the evidence.

---

## 3. Unverifiable / hallucinated / mis-tiered claims

### 3.1 CRITICAL — one fabricated Tier-1 source (must be struck before synthesis)

**p28 S4 — "Wang et al., *MinerU2.5-Pro: Pushing the Limits of Data-Centric Document Parsing
at Scale*, arXiv:2604.04771v2, Apr 2026" (tagged Tier 1).**

- The arXiv ID `2604.04771` does not exist; `2604` is a non-existent submission month scheme.
- There is no "MinerU2.5-**Pro**" paper. The real work is **MinerU2.5**, Niu et al.,
  **arXiv:2509.22186**, Sept 2025.
- Wrong author family ("Wang et al." vs "Niu et al."), wrong title, wrong date.
- **Contaminated dependent claims** (all trace to this fabricated source, all unverifiable):
  - "OmniDocBench **v1.6** with Base / Hard (296 complex) / Full (1,651) tiers"
  - "**Multi-Granularity Adaptive Matching** to fix v1.5 element-matching bias"
  - the entire "MinerU2.5-Pro (Apr 2026)" eval-methodology-maturity narrative in A2 contrast.
- **Impact on the rubric:** p28 Criterion **C3** ("eval-protocol versioning" — a proposed
  **hard-gate candidate**) uses this fabricated paper as its primary "protocols drift"
  evidence. The gate *concept* survives on independent real evidence (OmniDocBench, olmOCR
  post-hoc bench design), but the MinerU2.5-Pro justification and the "v1.5→v1.6 bias fix"
  proof point must be **deleted**.
- **Action:** strike S4; re-ground any surviving C3/A2 claim on arXiv:2509.22186 (real) or on
  olmOCR/OmniDocBench. Do **not** admit any Base/Hard/Full-tier or MGAM claim into synthesis.

### 3.2 MEDIUM — unverified secondary claims (admit only if independently checked)

- **p27** "Linux Foundation DocLang WG press release, 2026-06-09" and "≈195 releases" —
  not web-verified; Tier-2/3 contextual. Docling's high release cadence is plausible and the
  core TR is verified, but do not quote the DocLang-WG date or the exact release count as fact.
- **p28** head-to-head figures (olmOCR-Bench Overall 75.5 / 70.1 / 61.5; Marker "25 pages/sec",
  "122 pages/sec"; olmOCR "+14.2 pp", "12% retry") — sources real, **specific numbers not
  re-verified**. Admit the *methods*; verify the *numbers* before any are quoted in a verdict.

### 3.3 LOW — minor imprecisions (not disqualifying)

- **p26** "16 releases in ~12 months to v1.6.0" — GitHub shows **18** releases (PyPI more).
  Understated, immaterial; the dated release table itself is accurate.
- **p26** lists "Apache License 2.0" as **Tier 1** — a license text as "authoritative/primary"
  is borderline but defensible; not a finding.
- Several reports (p05, p06 S6, p25 O3/O10) self-grade pattern-*inferred* criteria as **B**
  and say so explicitly — this is correct discipline, not a defect.

### 3.4 No other fabrications found

Every other web-checked forward-dated preprint (olmOCR 2 2510.19817, OmniDocBench 2412.07626,
MinerU2.5 2509.22186, LangExtract release chain) resolved to a **real** source. The corpus's
future-2026 dates are consistent with the in-scenario clock (2026-07-18) and are not, by
themselves, evidence of fabrication — except S4, which is fabricated on the merits above.

---

## 4. Hard-gate verification (deep)

Proposed gates rest on two evidence classes: (a) **external standards** and (b) **frame §6.2
internal logic** (advisory-only doctrine). Verdicts:

| Gate (report) | Basis | Verdict |
|---|---|---|
| Missing license / installable-artifact clarity (p01) | PyPA/SPDX | ✅ well-founded |
| Undeclared side effects / untyped-when-claimed API (p02) | typing PEPs | ✅ |
| Critical CVE w/o exception; no CI vuln scan; heavy LLM dep in core (p03) | SLSA/OSV + model-sovereignty | ✅ |
| No CI on PRs; no must-fail QA canary (p04) | mutation-testing lit | ✅ |
| LLM signal can hard-gate; advisory failure → partial verdict (p05, p06, p25-O4, p30-E11, p23-S6, p26) | frame §6.2 + OWASP fail-closed | ✅ **convergent across 6 reports** — strongest gate in the set |
| Non-leakage / layered determinism contract (p07) | frame + reproducibility lit | ✅ (dimension itself gated on obtaining "user vs Sean" defs — correctly flagged open) |
| Import cycles; core depends on optional extras (p08) | import-layering | ✅ |
| Modality null-eligibility; TEDS-S conflated with TEDS (p09) | TEDS/GriTS papers | ✅ |
| Untested judge bias; low human agreement; judge hard-gates (p10) | LLM-judge lit | ✅ |
| Failed role independence; no adjudication trail (p11) | IAA methodology | ✅ |
| Conflated content/order metrics; tuning on holdout (p12) | OmniDocBench (verified) | ✅ |
| Comprehension inferred only from fidelity (p13) | construct-validity | ✅ |
| Any non-compensatory dimension fails (p15); E4/E8 conjunctive+fail-closed CI (p30) | GE/Giskard/promptfoo (verified) | ✅ |
| Prod threshold w/o versioned calibration; holdout used for selection (p16) | ROC/PR | ✅ |
| Untrusted content raw into prompt (S2); excessive agency (S4); LLM hard-gates (S6) (p23) | OWASP LLM01/05/06 (verified) | ✅ **A-grade** |
| Indefinite full-fidelity debug retention (G4); undocumented cloud inference (G5) (p24) | NIST PF / GDPR / AI 600-1 | ✅ |
| Fail-not-partial (O4); trace proves all steps (O3); ≥5 fault-injection scenarios (O7) (p25) | OWASP/SRE/Chaos | ✅ |
| Grounding-status on every LLM output; default-deny doc network fetch (p26) | LangExtract (verified) | ✅ |
| Per-modality eval (D27-02); span-aware table grid (D27-03) (p27) | Docling (verified) | ✅ |
| Baseline-on-all-pages; silent empty/garbled pass (B1/B2); edit-distance-only for math/tables (A2) (p28) | olmOCR / olmOCR 2 (**verified**) | ✅ **survives** — these gates rest on the *real* olmOCR anchors, not the fabricated S4 |
| Eval-protocol versioning (C3, p28) | **partly the fabricated S4** | ⚠️ concept OK; **re-ground off OmniDocBench/olmOCR, strike MinerU2.5-Pro** |
| OSS/commercial deception (A3); undeclared weight-license (C2) (p29) | Apache/OpenRAIL (verified) | ✅ |

**Net:** every proposed hard gate is defensibly grounded **except** the MinerU-derived proof
in p28-C3, which must be re-sourced. The advisory-cannot-gate family is the most robust
(independently converged by p05/p06/p23/p25/p30/p26).

---

## 5. Weights verification

- Frame §6.1/§10 **deliberately defers numeric weights to evidence**; reports supply only
  *suggestions*. Verdict: correct posture, no report may set final weights.
- Suggested dimension weights (p23 10%, p24 8%, p25 8–12%, p30 18%, plus case-study cluster-
  local %s in p26/p27/p28/p29) are **internally reasonable but not mutually reconciled** and
  **do not sum to a fixed total**; several claim overlapping shares of the same
  security/privacy/supply-chain and scoring/calibration clusters.
- **Synthesis obligation:** renormalize across the fixed dimension set; do not add per-report
  percentages (they double-count shared clusters). Each final weight needs the written
  rationale + evidence tier required by frame §6.1. No weight is load-bearing on the
  fabricated S4.

---

## 6. Contradictions & overlap (handled honestly)

Reports **surface** contradictions rather than hide them, satisfying frame §4/§6.5:
fail-closed vs graceful degradation (p25); delimiter defense vs "no fool-proof prevention"
(p23); TEVV retention vs data minimization (p24); binary unit tests vs edit-distance/TEDS
composite (p28); compensatory weighting (promptfoo) vs conjunctive `assert_test` (DeepEval)
(p30); model-sovereignty vs cloud-for-dev (p24). Each ships an explicit resolution rule. This
is a **strength** of the evidence base, not a defect. Overlap statements are consistent with
the frame §3 map; no evidence of re-auditing whisker code or duplicating prior swarms.

---

## 7. What may enter synthesis

**ADMIT (evidence sound, tiers accurate, on-topic):** all criteria and external bars from
**p01–p27, p29, p30**, and the **olmOCR/olmOCR-2/OmniDocBench-grounded** portions of **p28**
(A1, A2 core, A3, B1, B2, C1 olmOCR/MinerU-official-docs parts, C2). Carry each finding's
self-assigned evidence grade; propagate the weakest grade per frame §6.3.

**QUARANTINE (do not admit until re-sourced):**
- p28 **S4** and every claim depending on it: "MinerU2.5-Pro / arXiv:2604.04771", "OmniDocBench
  v1.6 Base/Hard/Full tiers", "Multi-Granularity Adaptive Matching", "v1.5→v1.6 bias fix".
- p28 **C3** hard-gate: admit the *concept*, re-ground on arXiv:2509.22186 / OmniDocBench /
  olmOCR post-hoc-bench; strike the MinerU2.5-Pro proof.

**FLAG (admit method, verify number before quoting as fact):** p28 head-to-head scores &
throughput figures; p27 DocLang-WG date and exact release count; p26 release-count "16".

**GATE FLOOR FOR SYNTHESIS:** the audit rubric must be no weaker than the systems it judges
(frame §6.2). The advisory-cannot-hard-gate gate (6-report convergence, A-grade) and the
security gates (p23, OWASP/NIST, A-grade) are the load-bearing, fully-verified core.

---

## 8. Bottom line

The 30-persona evidence base **meets the frame's Tier 1–2 floor and is fit to enter
synthesis**, with **one mandatory excision**: p28's fabricated MinerU2.5-Pro / arXiv:2604.04771
Tier-1 citation and its dependent claims. All other web-verified anchors are real, correctly
tiered, recent, and support their criteria; hard gates are defensibly grounded (fix p28-C3's
source); weights are unreconciled suggestions to be renormalized by synthesis, not adopted.
