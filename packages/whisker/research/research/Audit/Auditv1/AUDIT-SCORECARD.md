# AUDIT-SCORECARD — Whisker Professional-Grade Audit Instrument

**Purpose:** An executable, human-usable instrument for a **later** audit of whisker. This file is derived from `SYNTHESIS.md` and the 30 persona reports plus 5 Opus meta-reviews. It contains no whisker score and does not itself constitute a code audit.
**Companion:** read `SYNTHESIS.md` first for rationale, evidence, and doctrine.
**Non-negotiable framing rule:** report a **band with named flip conditions**, never a single certified number. A criterion may gate only against a property whisker actually claims (the fairness floor).

---

## 0. Instructions and evidence-collection protocol

### 0.1 How to run this instrument

1. Complete the **Scope Declaration / Claims Registry** (§1). Nothing else runs until this is filled, because gates activate against declared claims.
2. Answer the **pre-audit determinism questions** (§9). If unanswered, D2/G3 run in provisional mode only.
3. Collect evidence per §0.2 in one bounded pass.
4. Run the **7 hard gates** (§2). Any fail → band = Unsound; still complete the dimensions for a diagnostic profile, but the verdict is capped.
5. Score the **8 dimensions** (§3) on the 0-4 ladder with required evidence.
6. Compute the **composite, band, and uncertainty** (§4).
7. Emit the **mandatory output template** (§5).
8. Respect **stop conditions** (§7) at every step.

### 0.2 Evidence rules

- **Artifact-first:** the core is executable from docs, CI config, one instrumented run (trace+debug), one replay, one inverted canary, artifact greps, and the dependency manifest. No source inspection is required for the core.
- **Every scored number carries a reason** traceable to evidence (opus-A M-set, p30-E2). A bare float is not evidence.
- **Reference-metric integrity:** where an evaluator is mutable, compute against a locked reference path and log evaluator hash (p19-AG5).
- **Grade every finding A-D** (A = multiple Tier-1; B = single Tier-1 / converging Tier-2; C = Tier-3 / contested; D = speculative). LLM-judge-derived findings inherit at most B and are advisory.
- **No invented thresholds.** If a threshold is not calibrated on labeled whisker data, record it as `borrowed / uncalibrated` and treat the dependent criterion as a soft cap (dimension ≤ level 2), never a live hard gate.

---

## 1. Scope Declaration / Claims Registry (fill FIRST)

The audited party declares each claim. Gates and modules activate against these declarations.

| ID | Claim | Value (fill in) | Activates |
|---|---|---|---|
| C-VER | Version phase | `0.y.z` / `≥1.0` | If ≥1.0: API-stability bar at full strength (D7) |
| C-API | Stable public API claimed? | yes / no | If yes: deprecation policy becomes gate-eligible |
| C-CAL | Calibration status | `Stage 0 / uncalibrated` / `production-calibrated` | If calibrated: M1 gate-eligible; uncalibrated threshold → fail |
| C-LAB | Golden-label role | `advisory` / `gate-bearing` | If gate-bearing: M2 IAA/adjudication required |
| C-INF | Default inference path | `self-hosted` / `cloud` | If cloud default: cloud-governance becomes a gate (M5) |
| C-COMP | "Measures comprehension" claimed? | yes / no | If yes: M7 comprehension battery activates |
| C-PROD | "Production-grade ops" claimed? | yes / no | If yes: M4 observability depth activates |
| C-DET | Determinism tier claimed | bit-exact / quality-stable / stated-precision / non-guaranteed | Sets the equality contract for G3 |
| C-LIC | Outbound license + bundled licenses | e.g. BSL-1.0 + deps | Scopes G7 checks |

**Rule:** an unstated claim cannot be gated. Absence of a claim is scored as a documented boundary, not a failure.

---

## 2. Hard-gate checklist (7, conjunctive, non-compensatory)

Each gate is Pass / Fail / Not-applicable (only when the claims registry makes it N/A). Any Fail → overall band = **Unsound**. Required proof must be attached; an unproven gate is treated as Fail (opus-A: an unevaluable gate is vacuous, so demote to soft cap only when §0.2 permits, otherwise Fail).

| Gate | Pass rule | Fail rule | N/A rule | Required proof | Trace |
|---|---|---|---|---|---|
| **G1 Advisory non-leakage** | Removing the advisory field leaves the verdict unchanged; adversarial "all-clear" structured output is ignored by the deterministic layer | Any advisory/LLM signal can flip a gate to pass or hard-gate alone | Never N/A if an LLM lane exists | CI contract test output showing verdict invariance; adversarial-verdict rejection log | p05, p10-J8, p15, p30-E11 |
| **G2 Fail-not-partial** | Fidelity-critical fault → non-zero exit, no output artifact updated, debug preserved | Hollow/partial result emitted as complete, or exit 0 on failure | Never N/A | Fault-injection run: exit code, artifact-absence assertion, preserved debug path | p25-O4, p05, CLAUDE.md |
| **G3 Determinism by replay** | Re-run under the declared tier (C-DET) satisfies the tier's equality contract | Stated tier refuted by one replay | N/A only if C-DET = non-guaranteed AND no determinism claim is marketed | Two run manifests + equality-contract diff at the declared tier | p06, p07, CLAUDE.md D1-D11 |
| **G4 Per-axis reporting + eval integrity** | Report shows per-axis scores with `eligible/null` counts; table gate requires structure AND content at the same bar; no modality scored when absent | Single composite gates release with no per-axis floor, OR absent modality imputed, OR table passes on structure alone | Table sub-rule N/A on corpora with no tables (must be declared) | Axis score table with null counts; a structure-only+content-fail case that correctly fails | p09, p13, p29-B1, p30-E1, opus-A M1/M2/M3 |
| **G5 Untrusted-input mediation** | Paper/web text wrapped (segregation + delimiter hardening) and structured-output-validated before any prompt | Raw untrusted text concatenated into a prompt without wrapping/validation | N/A only if no LLM lane and no web fetch exist | Serialized prompt showing wrapped envelope; delimiter-forgery and instruction-in-data tests that hold | p23, OWASP LLM01:2025, CLAUDE.md |
| **G6 Baseline canary (inverted)** | A zero-authoring baseline runs on 100% of pages; inverting a canary (known-bad output) MUST fail the gate | No universal baseline, OR an inverted canary passes | Never N/A for a QA tool | Baseline coverage proof + inverted-canary run that fails as required | p28-B1/B2, p04, p19 |
| **G7 Licensing / attribution** | No incompatible license combination shipped; required third-party attribution present; BSL-1.0 full-notice satisfied | Incompatible combination (e.g. Apache-2.0 project bundling GPL-2.0-only) or missing attribution | Never N/A | Artifact-derived attribution inventory; Apache↔GPL and BSL checks | p22, p26-2.10, p29-C2 |

**Not gates (score in dimensions only):** calibration (unless C-CAL = production-calibrated), OpenSSF/TSC/foundation governance, SLSA/SBOM, overload/load testing, full privacy framework, release cadence, API stability (unless C-VER ≥ 1.0). Cloud-governance is a gate only if C-INF = cloud.

---

## 3. Eight weighted dimensions

Each dimension: weight, non-overlapping subcriteria, 0-4 anchors, measurement method, anti-gaming test, required evidence, source/persona trace. Subcriteria within a dimension are compensatory; the associated gate is not.

### D1 — Epistemic separation (hybrid core / advisory overlay) — weight 20

- **Subcriteria (non-overlapping):** (a) lane isolation documented; (b) demote-only ratchet (advisory can lower, never raise a verdict); (c) advisory output never sole gate (the G1 wiring); (d) advisory failure does not partial-gate the deterministic verdict.
- **0-4 anchors:** 0 no separation; 1 separation claimed in prose only; 2 lanes documented, wiring untested; 3 CI contract test proves non-leakage and demote-only; 4 level 3 plus adversarial-verdict rejection under injection.
- **Measurement:** conformance checklist + maturity model; run the G1 contract test.
- **Anti-gaming test:** feed an adversarial structured verdict; confirm no gate flips.
- **Required evidence:** wiring diagram/doc; CI verdict-invariance test.
- **Trace:** p05, p07 (non-leakage), p10-J8, p15, p30-E11; opus-A RC1/M11, opus-B.

### D2 — Determinism & reproducibility (replay-verified) — weight 15

- **Subcriteria:** (a) declared tier map (C-DET); (b) variance sources enumerated and in/out-of-scope stated; (c) replay equality contract defined; (d) serial-default preserved (no global concurrency flip).
- **0-4 anchors:** 0 no determinism posture; 1 asserted, no replay; 2 tier map documented; 3 one replay holds at the declared tier; 4 replay suite + variance controls + regression protection.
- **Measurement:** reproducibility replay.
- **Anti-gaming test:** replay with a different process/order; the declared tier must still hold.
- **Required evidence:** two run manifests + equality diff.
- **Trace:** p06, p07; CLAUDE.md D1-D11, opus-B. **Provisional until §9 answered.**

### D3 — Fidelity / fail-not-partial — weight 15

- **Subcriteria:** (a) fidelity-critical stages identified; (b) fail-closed on those stages; (c) no hollow-complete artifact; (d) debug preserved on failure.
- **0-4 anchors:** 0 silent partial success; 1 some errors surfaced; 2 fails sometimes; 3 fail-closed on all fidelity-critical paths with CI proof; 4 level 3 plus attributed errors and preserved forensics.
- **Measurement:** observability / fault-injection.
- **Anti-gaming test:** inject a stage failure; assert no schema-valid empty result with exit 0.
- **Required evidence:** fault-injection matrix with exit codes and artifact-absence assertions.
- **Trace:** p25-O4, p05; CLAUDE.md Fidelity; OWASP RAG §14.

### D4 — Metric construct validity & per-axis eval — weight 15

- **Subcriteria:** (a) per-axis reporting with null-eligibility; (b) table = structure + content paired; (c) constructs kept distinct (NID vs NED; order vs text; detection vs transcription); (d) comprehension not inferred from fidelity; (e) evaluator/match version pinned.
- **0-4 anchors:** 0 single opaque score; 1 multiple metrics collapsed in reporting; 2 per-axis but constructs blurred or unpinned evaluator; 3 per-axis + null-eligibility + paired table + pinned evaluator; 4 level 3 plus binary unit tests for construct-invalid cases.
- **Measurement:** metric construct-validity audit.
- **Anti-gaming test:** a structure-only pass with content fail must not satisfy a table claim; an absent modality must not be imputed.
- **Required evidence:** axis table with eligible/null counts; evaluator version record.
- **Trace:** p09, p12, p13, p27-D27-02/03, p28-A2, p29-B1, p30-E1; opus-A M1-M7 (verified A).

### D5 — Anti-gaming / Goodhart resistance — weight 12

- **Subcriteria:** (a) baseline canary on 100% of pages (the G6 teeth); (b) must-fail canary present and inverts correctly; (c) holdout secrecy (fit vs commit split); (d) LLM-judge advisory only; (e) each load-bearing criterion passes the p19 G1-G10 checklist.
- **0-4 anchors:** 0 no canaries; 1 canaries exist but never fail; 2 canaries fail but no holdout hygiene; 3 canaries + holdout split + advisory-only judge; 4 level 3 plus optimization-budget caps and proxy-divergence monitoring.
- **Measurement:** anti-gaming / Goodhart stress.
- **Anti-gaming test:** invert a canary (must fail); format-only perturbation must not flip a pass.
- **Required evidence:** canary catalog + inverted-canary run; holdout split policy.
- **Trace:** p18, p19, p28-B1/B2, p10; opus-A M6/M10/M11.

### D6 — Untrusted-input / prompt-injection defense — weight 10

- **Subcriteria:** (a) trust-boundary inventory; (b) wrap_source/segregation + delimiter hardening; (c) structured-output validation in deterministic code; (d) tool least-privilege; (e) document-embedded injection test corpus.
- **0-4 anchors:** 0 raw untrusted text in prompts; 1 wrapping for chat only; 2 wrapping documented, untested; 3 wrapping + validation + injection tests on document-sourced payloads; 4 level 3 plus least-privilege tools and honest impossibility disclosure.
- **Measurement:** conformance checklist + adversarial probing.
- **Anti-gaming test:** delimiter-forgery and instruction-in-data payloads from document body must not break the envelope or reach a tool.
- **Required evidence:** serialized wrapped prompt; injection test results by attack class.
- **Trace:** p23; CLAUDE.md; OWASP LLM01/LLM05/LLM06:2025.

### D7 — API contract + packaging (pre-1.0 proportionate) — weight 8

- **Subcriteria:** (a) documented public API + `__all__`; (b) `py.typed` if typed API claimed; (c) PEP 621 pyproject + correct wheel/sdist; (d) LLM/cloud deps isolated in optional extras; (e) no import cycles, core not depending on optional extras.
- **0-4 anchors:** 0 no packaging discipline; 1 installable, undocumented surface; 2 pyproject + docs, deps not isolated; 3 typed surface + extras isolation + acyclic imports; 4 level 3 plus import-linter contract in CI.
- **Anti-gaming test:** confirm core install does not pull heavy LLM deps; grep for import cycles.
- **API stability:** **unscored while C-VER = 0.y.z** (SemVer 2.0.0 "Major version zero: anything MAY change").
- **Measurement:** conformance checklist.
- **Required evidence:** pyproject, extras map, import graph.
- **Trace:** p01, p02, p08; opus-C, opus-E T1.

### D8 — Docs + operator CLI contract — weight 5

- **Subcriteria:** (a) greppable contract doc (deterministic/advisory boundary, exit-code table, trace/debug spec, calibration status, known gaps, architecture map); (b) exit-code contract + stdout/stderr discipline + `--json`; (c) actionable errors; (d) docs-alone operator reproduction.
- **0-4 anchors:** 0 README only; 1 partial docs, no contract doc; 2 contract doc present, CLI contract informal; 3 contract doc + documented exit codes + stream discipline + runnable path; 4 level 3 plus Diátaxis typing and AGENTS.md/CLAUDE.md hygiene.
- **Anti-gaming test:** perform install → run → interpret → diagnose from docs alone with zero source opens.
- **Measurement:** documentation-completeness audit + CLI conformance.
- **Required evidence:** contract doc; exit-code/stream test; docs-walk log.
- **Trace:** p20, p21; opus-C.

| Dimension | Weight |
|---|---|
| D1 Epistemic separation | 20 |
| D2 Determinism & reproducibility | 15 |
| D3 Fidelity / fail-not-partial | 15 |
| D4 Metric construct validity & per-axis eval | 15 |
| D5 Anti-gaming / Goodhart | 12 |
| D6 Untrusted-input / prompt-injection | 10 |
| D7 API contract + packaging | 8 |
| D8 Docs + operator CLI | 5 |
| **Total** | **100** |

---

## 4. Scoring formula, gate override, uncertainty, weakest-link grade

### 4.1 Normalized composite

Each dimension `Di` scored 0-4 → normalize to 0-100 as `Di_pct = (Di / 4) * 100`. Composite:

```
Composite = Σ ( weight_i / 100 * Di_pct )   over i = 1..8
```

The composite is **navigation only**. It is never reported alone (G4 rule).

### 4.2 Gate override (non-compensatory)

```
if any Gate in {G1..G7} == Fail:
    Band = "Unsound"   # regardless of Composite
else:
    Band = band_from_composite_and_grades()   # §4.4
```

### 4.3 Uncertainty interval / band

- Report the composite as an **interval** `[Composite - w, Composite + w]`, where `w` widens with each load-bearing input that is grade C, contested, or uncalibrated. Do not report two-decimal precision on uncalibrated or LLM-judge inputs.
- Name the single axis whose ±ε flips the band (sensitivity, opus-A layer 4, p30-E12).

### 4.4 Weakest-link evidence grade

```
CompositeGrade = min(evidence_grade of each load-bearing input)   # weakest-link
```

The verdict grade is the weakest grade among D1-D4 plus any active gate proof. If any load-bearing input is grade C or below, the band widens and cannot enter "Professional-grade."

### 4.5 Band thresholds

| Band | Entry condition |
|---|---|
| Unsound | any gate fails |
| Emerging | all gates pass; Composite ≥ 40; grade ≥ C |
| Professional-grade | all gates pass; Composite ≥ 65; D1-D4 grade ≥ B; ≥1 replay and ≥1 inverted canary evidenced |
| Best-defensible | Professional plus every claimed module ≥ level 3; band width ≤ one tier |

### 4.6 No-single-number rule (mandatory)

The verdict is **the band, its width, its named drivers, and the gate ledger** together. Reporting the composite number alone, or ranking whisker by it, is a protocol violation.

---

## 5. Mandatory output template (for the future whisker code audit)

```
# Whisker Audit Result — <date> — auditor: <name>

## Claims registry (as declared)
<table from §1>

## Gate ledger (conjunctive)
G1 Advisory non-leakage:      PASS | FAIL | N/A   evidence: <link>
G2 Fail-not-partial:          PASS | FAIL | N/A   evidence: <link>
G3 Determinism by replay:     PASS | FAIL | N/A   evidence: <link>   [tier: <C-DET>]
G4 Per-axis + eval integrity: PASS | FAIL | N/A   evidence: <link>
G5 Untrusted-input mediation: PASS | FAIL | N/A   evidence: <link>
G6 Baseline canary (inverted):PASS | FAIL | N/A   evidence: <link>
G7 Licensing / attribution:   PASS | FAIL | N/A   evidence: <link>

## Per-axis / per-dimension table (never a lone composite)
Dimension  Level(0-4)  Grade(A-D)  Reason  Evidence  Eligible/Null
D1 ...
...
D8 ...

## Composite (navigation only)
Composite: <value>   Interval: [<lo>, <hi>]   Weakest-link grade: <A-D>

## Band + width + drivers
Band: <Unsound|Emerging|Professional-grade|Best-defensible>
Width: <tiers>   Drivers of width: <named contested/uncalibrated inputs>

## Active extended modules (only those claimed)
<M1..M9 with level + grade>

## Flip conditions (named)
1. Advisory→gating: ...
2. Replay outcome: ...
3. Version-phase: ...
4. Calibration: ...
5. Label role: ...
6. Cloud default: ...

## Stop conditions triggered (if any)
<which, and why the audit halted>

## Open questions / blockers
<including any unanswered determinism definitions>
```

---

## 6. Staged execution order (avoids duplicate checking)

Run in this order; each stage consumes prior evidence and never re-checks it.

1. **Stage 0 — Scope & claims (§1) + determinism questions (§9).** Blocks everything.
2. **Stage 1 — Static artifacts:** docs, contract doc, pyproject/extras, license/SPDX, import graph. Feeds D7, D8, G7.
3. **Stage 2 — One instrumented run (trace+debug):** produces per-axis output, trace coverage, debug I/O. Feeds D3, D4, D6, G2, G4, G5.
4. **Stage 3 — One replay:** consumes Stage 2 run. Feeds D2, G3.
5. **Stage 4 — Inverted canary + adversarial verdict + injection payloads:** consumes Stage 2 harness. Feeds D1, D5, D6, G1, G5, G6.
6. **Stage 5 — Composite, band, uncertainty (§4).** Consumes all above.
7. **Stage 6 — Claimed extended modules (§ SYNTHESIS 4.2).** Only those in the claims registry.

Each gate is evaluated exactly once, in the earliest stage that produces its evidence. No criterion is measured twice.

---

## 7. Stop conditions

Halt and report (do not fabricate a verdict) when any of these occur:

1. **Insufficient evidence.** A gate cannot be evaluated because its evidence artifact does not exist (e.g. no fault-injection harness for G2). Record the gate as Fail-unproven and halt the "Professional-grade" claim.
2. **Uncalibrated thresholds on a calibration claim.** If C-CAL = production-calibrated but any threshold lacks recorded provenance (TPR/FPR, corpus, date), stop: the calibration claim is unmet.
3. **Failed fidelity-critical path.** If G2 fails, stop deeper eval scoring; the tool is Unsound regardless of remaining dimensions.
4. **Definition-blocked determinism.** If the §9 questions are unanswered, D2/G3 run in provisional mode only and the verdict is flagged determinism-definition-pending; do not certify a determinism tier.
5. **Fabricated or unverifiable evidence.** If any load-bearing citation cannot be resolved to a primary source, quarantine it and its dependents (precedent: the MinerU2.5-Pro / arXiv:2604.04771 quarantine in `SYNTHESIS.md` §2.3).
6. **Scope drift.** If the audit begins requiring enterprise-imitation machinery not claimed by whisker, stop and re-anchor to the fairness floor.

---

## 8. Anti-gaming test bank (per-criterion, applied before scoring)

Every load-bearing subcriterion must pass the p19 G1-G10 checklist before it is scored: orthogonal corroboration; non-compensatory integrity gate; canary that must fail; holdout hygiene (fit vs commit); reference-metric integrity; format-invariance; falsifiable wording (no adjective-only bars); weight sensitivity; optimization-budget cap; per-axis visibility. A subcriterion that cannot pass this checklist is downgraded to informational (max maturity 1) until rewritten (p19 §2.9, opus-A/E).

---

## 9. Pre-audit questions for user / Sean determinism definitions (BLOCKING for D2/G3)

D2 and G3 cannot be applied until these are answered. They cannot be invented (p07 left both doctrines undefined; opus-B/E confirm).

1. **User's definition:** what is the user's determinism definition, at which tier (bit-exact / quality-stable / stated-precision / non-guaranteed), over which artifacts (verdict / structure / byte output)?
2. **Sean's definition:** the same three questions for Sean's doctrine.
3. **Reconciliation:** where do the two agree, where do they diverge, and which governs a release gate on divergence?
4. **Equality contract:** what exact equality must a replay satisfy to pass G3 (semantic equality of findings, or byte equality)?
5. **Variance scope:** which variance sources are in-scope (concurrent in-flight requests, temperature, unordered set iteration, MoE routing) and which are accepted as out-of-scope?

Until answered: G3 uses interim semantic quality-stability, D2 is scored provisionally, and the verdict carries a `determinism-definition-pending` flag.

---

## 10. Traceability

Any row in this scorecard traces as: subcriterion → dimension (Dn) or gate (Gn) → persona report `pNN-*.md` in this directory → that report's Tier 1-2 source table. Binding corrections and the four-layer architecture come from `opus-A`, `opus-B`, `opus-C`, `opus-D` (quarantine), and `opus-E` (8 dimensions, 7 gates, bands, flip conditions, enterprise-imitation demotions). Rationale for every weight and gate is in `SYNTHESIS.md` §5-§6.
