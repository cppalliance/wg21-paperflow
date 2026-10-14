# P07 — Dual-Determinism Reconciliation Researcher

**Persona:** 7 of 30 (Cluster B — Architecture & hybrid deterministic+LLM design)  
**Date:** 2026-07-18  
**Author role:** Internet-research persona (Stage 0 evidence framing)  
**Scope:** External precedents for reconciling two distinct determinism doctrines into one coherent contract. No whisker production-code inspection, no whisker verdict.

---

## 1. Question restated

How do mature systems **reconcile two conflicting determinism doctrines**—typically a **strict, reproducible, gate-bearing core** and a **deliberately nondeterministic, advisory overlay**—into a **single documented contract** that:

1. names which guarantee applies in which layer;
2. prevents the weaker layer's nondeterminism from **leaking** into authoritative decisions;
3. remains auditable without pretending the layers share one guarantee class; and
4. survives future doctrine changes via explicit decision history rather than silent drift?

**Whisker-specific framing (audit objective, not a code finding):** The whisker audit must eventually judge whether whisker "combines the user's and Sean's determinism approaches" into one defensible doctrine. **The concrete definitions of those two approaches are an open question** (see Section 1.1). This persona researches the **reconciliation method** so criteria hold once those definitions are supplied.

### 1.1 Open question preserved — user vs Sean definitions (unresolved)

Per `00-FRAME.md` section 10, **neither doctrine is fully specified in available research artifacts**:

| Party | Status in Stage 0 | What synthesis must obtain before scoring |
|---|---|---|
| **User's determinism approach** | **Not defined here.** No stable, citable formulation of scope, guarantee class (bit-exact vs quality-stable), or enforcement surface was found in `research/**` or `CLAUDE.md` alone. | Explicit written definition: which subsystems, which outputs, which replay protocol, what failure mode when violated. |
| **Sean's determinism approach** | **Not defined here.** Identity of "Sean" and the exact shape of his determinism doctrine are **not resolvable** from research files. | Same fields as above, plus any stated trade-offs against the user's doctrine. |

**P07 does not assume, merge, or pick a winner between these doctrines.** Criteria below test whether *any* pair of doctrines is **cleanly combined**, not whether a particular party is right. The Opus synthesis **must obtain both definitions from the user** (or designated stakeholders) before applying the reconciliation dimension to whisker code.

**Contested analogy (surfaced, not resolved):** External literature often maps "strict core" to **linearizability / complete mediation** and "advisory overlay" to **eventual consistency / tolerated variance** (Kleppmann consistency spectrum, cited as **analogy only**). Whether user vs Sean map to those poles is **unknown until defined**; the analogy informs criterion design, not whisker scoring.

---

## 2. Proposed audit criteria

Each criterion includes: how to measure, audit-method tag (`00-FRAME.md` §5), scoring-design hook (`00-FRAME.md` §6), gaming vector + anti-gaming guard, evidence grade, and Tier 1–2 citations.

---

### Criterion R1 — Layered determinism contract is named, bounded, and versioned

**Statement:** The system publishes a **layered determinism contract** that lists every execution lane, assigns each lane exactly one **guarantee class**, and states what is *out of scope* for strict replay.

**Guarantee classes (minimum vocabulary, drawn from external standards):**

| Class | Meaning (external definition) | Typical layer |
|---|---|---|
| **Repeatability** | Same team, same artifacts, same procedure → same result within stated tolerance (ACM/NISO) | Deterministic gate core |
| **Quality-stable reproducibility** | Same findings/verdicts/structure across reruns; not necessarily bit-identical (operational doctrine; must be written down) | Hybrid boundary outputs |
| **Advisory nondeterminism (documented)** | Outputs may vary run-to-run; **explicitly not** used as authoritative gate inputs unless demoted per R4 | LLM / judge / oracle overlay |

**How to measure:** Documentation-completeness matrix: for each lane (CLI gate, metrics, advisory judge, trace/debug, CI contract), locate a **single canonical section** that states guarantee class, inputs, outputs, and replay command. Score partial if classes are implied but unnamed; fail if one global "deterministic" claim covers both gate and LLM paths.

- **Audit method:** Conformance checklist (#1) + Documentation-completeness audit (#9)
- **Scoring hook:** §6.1 dimension "determinism / hybrid architecture"; §6.2 candidate hard gate if contract absent
- **Gaming vector:** Boilerplate "we value determinism" with no per-lane table.
- **Anti-gaming guard:** Require **lane × guarantee class × replay command** table; empty cells fail.
- **Evidence grade:** **A** (ACM badging + NIST MEASURE 1.1 converge on scoped, documented measurement claims)
- **Sources:** [S1], [S2], [S3]

---

### Criterion R2 — Conflicting doctrines are reconciled via explicit decision records, not silent merge

**Statement:** When two determinism doctrines coexist (e.g., user vs Sean, or "strict core" vs "tolerated LLM variance"), the reconciliation is captured as **first-class architectural decisions** with traceable history: context, trade-offs, chosen boundary, and **supersession** when doctrine changes.

**How to measure:** Inspect decision log (ADR or equivalent) for at least one record whose **context** names both doctrines (or their guarantee classes) and whose **decision** states how they combine. Check for `supersedes` / `reconciles-with` / `conflicts-with` links when doctrine evolves (immutable originals + new record, per ADR practice). Score fail if reconciliation exists only in chat, issue comments, or implicit code paths.

- **Audit method:** Conformance checklist (#1) + Maturity-model scoring (#2)
- **Scoring hook:** §6.1 architecture/hybrid; §6.5 disagreement handling (both doctrines recorded before synthesis picks weights)
- **Gaming vector:** Retroactive ADR written after audit starts, with no changelog linkage.
- **Anti-gaming guard:** ADR must predate or coincide with **first release** claiming combined doctrine; supersession chain required for changes.
- **Evidence grade:** **A** (peer-reviewed ADM formalization + cloud prescriptive guidance)
- **Sources:** [S4], [S5], [S6]

---

### Criterion R3 — Dependency integrity: incompatible guarantee claims cannot coexist without a reconciling decision

**Statement:** Formal **(in)compatibility** between determinism decisions is modeled explicitly—mirroring architectural decision models where alternatives can be `isIncompatibleWith` unless a **reconciling** parent decision defines the boundary.

**How to measure:** Extract determinism-related decisions into a small graph. Verify: (a) no two **accepted** decisions assign the same lane contradictory guarantee classes without a reconciling node; (b) dependency edges (`triggers`, `forces`, `constrains`) are documented for migration/dual-run periods. Automated tooling optional; manual graph audit acceptable for Stage 0 rubric.

- **Audit method:** Maturity-model scoring (#2)
- **Scoring hook:** §6.5 contested criteria; §6.3 evidence grade propagates weakest link in decision graph
- **Gaming vector:** Hide conflict by splitting one lane across undocumented micro-modules.
- **Anti-gaming guard:** Lane inventory (R1) cross-checked against import/call graph in later code stage; Stage 0 requires **documented lane list** as audit input.
- **Evidence grade:** **A**
- **Sources:** [S4], [S7]

---

### Criterion R4 — Non-leakage boundary: advisory nondeterminism cannot authoritatively gate

**Statement:** The **enhancement boundary** is one-directional: deterministic core → optional advisory enrichment → presentation/logging. **Complete mediation** applies: downstream authorization and gate logic **never** rely on LLM output as the sole authority for pass/fail (OWASP LLM06 Excessive Agency).

**How to measure:**

1. **Static contract review:** Document every code path where advisory output could alter gate verdict, exit code, or persisted pass/fail state. Allowed: explicit human opt-in, documented demotion-only ratchet, or structured merge where **deterministic path alone** defines fail-closed behavior.
2. **Fault-injection / replay review (method for later code stage):** With LLM stubbed to flip verdicts, core gate outcome unchanged unless advisory path is explicitly enabled and non-gating.

- **Audit method:** Conformance checklist (#1) + Reproducibility replay (#8) + Observability/fault-injection (#11)
- **Scoring hook:** §6.2 **hard gate** candidate — LLM signal hard-gating violates hybrid contract
- **Gaming vector:** Advisory lane disabled in CI but enabled in operator docs without labeling; or "shadow mode" that still writes gate fields.
- **Anti-gaming guard:** Test that **must fail** if advisory output is wired to gate; CI runs deterministic core without LLM credentials.
- **Evidence grade:** **A**
- **Sources:** [S8], [S9]

---

### Criterion R5 — Per-layer measurement honesty (what is measured vs documented as unmeasurable)

**Statement:** Following NIST AI RMF MEASURE 1.1, the contract **documents which determinism properties are measured, which are intentionally not measured, and why**. Probabilistic components are not claimed as "valid and reliable" on the same evidentiary bar as deterministic replay unless evidence supports it.

**How to measure:** Checklist against MEASURE 1.1 / 2.x: metrics selected for strict core; limitations documented for advisory layer; independent assessor path noted for nondeterministic components. Fail if marketing language equates "LLM judge score" with "reproducible gate."

- **Audit method:** Conformance checklist (#1) + Metric construct-validity audit (#4) for cross-layer claims
- **Scoring hook:** §6.1 determinism dimension; §6.4 anti-gaming (cosmetic "measurement" without replay)
- **Gaming vector:** Publish replay badge for whole product while only core subset replays.
- **Anti-gaming guard:** Scope statement on every reproducibility claim ("repeatability applies to lanes A,B; not C").
- **Evidence grade:** **A**
- **Sources:** [S1], [S2]

---

### Criterion R6 — Consistency-model discipline: no unnamed "strong determinism"

**Statement:** Like distributed consistency, **determinism is not one dial**—subsystems must name their guarantee (strict serializable / linearizable / causal / eventual analogues). Mixed systems document **per-subsystem** guarantees and forbidden promotions (e.g., eventual → linearizable without migration ADR).

**How to measure:** Review architecture docs for banned vague phrases ("fully deterministic") without subsystem qualifier. Require mapping table: subsystem → named guarantee → failure behavior.

- **Audit method:** Documentation-completeness audit (#9); consistency analogy explicitly labeled **non-literal**
- **Scoring hook:** §6.1; feeds §6.5 when user vs Sean use different guarantee names
- **Gaming vector:** Reuse distributed-systems buzzwords without operational meaning.
- **Anti-gaming guard:** Each named guarantee must link to a **replay or tolerance test** (R7).
- **Evidence grade:** **B** (foundational textbook + secondary summaries; analogy tier clearly marked)
- **Sources:** [S10], [S11]

---

### Criterion R7 — Scoped replay verification protocol per guarantee class

**Statement:** Verification method matches guarantee class:

- **Strict core:** Repeatability / reproduced results protocol (ACM artifact badging)—rerun-and-diff with fixed seeds, ordered inputs, hermetic deps; tolerance only where standard allows.
- **Advisory layer:** Stability **metrics** (verdict flip rate, confidence calibration) — not bit-exact replay — documented separately.

**How to measure:** Existence of written replay script + expected diff policy for core; separate stability eval protocol for advisory (even if "not yet calibrated," must be stated). Later code audit executes both.

- **Audit method:** Reproducibility replay (#8) + Calibration operating-point audit (#5) for advisory stability
- **Scoring hook:** §6.2 hard gate if core replay refutes determinism claim; §6.6 uncertainty band widens if advisory stability unmeasured
- **Gaming vector:** Replay only golden happy-path; exclude ordering/concurrency paths.
- **Anti-gaming guard:** Replay corpus includes **ordering stress** and **concurrency-off** checks for core; advisory reports flip-rate upper bound or "unknown."
- **Evidence grade:** **A**
- **Sources:** [S2], [S3]

---

### Criterion R8 — Transitional dual-truth periods are bounded and reconciled

**Statement:** When migrating from one doctrine to another (or running parallel lanes during reconciliation), the system defines **bounded dual-truth** with reconciliation dependencies—analogous to strangler migrations where two stores coexist until a documented cutover ADR.

**How to measure:** If two determinism regimes coexist in one release, locate: cutover criteria, reconciliation job/tests, and `blocks_migration_of` / `reconciles_with` links in decision log. Fail if dual regimes run indefinitely without documented reconciliation owner.

- **Audit method:** Maturity-model scoring (#2) + Observability/fault-injection (#11)
- **Scoring hook:** §6.5; lower confidence if migration state unclear
- **Gaming vector:** Permanent "beta" advisory lane bypassing gate indefinitely.
- **Anti-gaming guard:** Time-bounded or release-bounded migration ADR with explicit exit test.
- **Evidence grade:** **B** (strong practitioner secondary on ADR dependency typing)
- **Sources:** [S7], [S5]

---

## 3. External benchmark / exemplar bar

### 3.1 Reconciliation pattern (synthesis of Tier 1–2 sources)

Mature **dual-determinism** systems converge on a **four-part pattern** (names vary; structure recurs):

```text
┌─────────────────────────────────────────────────────────────┐
│  Governance / decision log (ADR): doctrines + reconciliation │
├─────────────────────────────────────────────────────────────┤
│  Deterministic core: authoritative, replay-verified (R7)     │
│       │ one-way data                                        │
│       ▼                                                     │
│  Advisory nondeterministic layer: enrich, never sole gate    │
│       │ complete mediation (R4)                             │
│       ▼                                                     │
│  Execution / operator surface: fail-closed on core alone     │
└─────────────────────────────────────────────────────────────┘
```

**Bar elements:**

1. **Decision log as source of truth for doctrine pairs** — AWS/Azure/ADR community: immutable accepted records, supersession on change, trade-offs in consequences ([S5], [S6], [S7]).
2. **Formal incompatibility + reconciliation edges** — Zimmermann et al. ADM: `(in)compatibility` relations and integrity constraints prevent silent merge of contradictory outcomes ([S4]).
3. **Named guarantee spectrum** — Kleppmann: strongest guarantees cost performance/availability; mixed systems must **name** the guarantee per operation, not assert "strong consistency" globally ([S10]).
4. **Complete mediation at boundary** — OWASP LLM06: authorization and high-impact actions validated in **downstream deterministic systems**, not by LLM self-policing ([S8]).
5. **Scoped reproducibility claims** — ACM/NISO: repeatability vs reproducibility vs replicability are **distinct**; claims must specify team, setup, and tolerance ([S2], [S3]).
6. **Honest measurement scope** — NIST AI RMF: risks/trustworthiness characteristics that **cannot** be measured must be documented ([S1]).

### 3.2 What "cleanly combined" means (audit bar)

Two doctrines (user's + Sean's, once defined) are **cleanly combined** iff:

| # | Bar question | Pass indicator |
|---|---|---|
| 1 | Is each lane assigned exactly one guarantee class (R1)? | Lane × class table complete |
| 2 | Is the merge explained in a reconciling ADR, not implied (R2)? | Linked decision records |
| 3 | Are contradictions explicitly modeled (R3)? | No orphan incompatible decisions |
| 4 | Can advisory variance change authoritative pass/fail (R4)? | **No** — hard gate |
| 5 | Are reproducibility claims scoped (R5, R7)? | Core replay + advisory stability split |
| 6 | Is dual-truth temporary if present (R8)? | Cutover ADR or single doctrine |

**Not required for pass:** Bit-exact reproducibility of advisory LLM outputs (externally unrealistic for hosted inference); **is** required: documented advisory nondeterminism and non-gating.

### 3.3 Exemplar practices (external, not whisker)

| Exemplar pattern | Lesson for reconciliation audit | Whisker-relevant caveat |
|---|---|---|
| NIST AI RMF GOVERN + MEASURE cross-cut | Governance infuses map/measure/manage; unmeasurable AI risks must be documented | Model-sovereignty context: self-hosted vs cloud does not remove nondeterminism; changes evidence bar |
| OWASP LLM06 complete mediation | Downstream enforcement, HITL for high impact | Maps to "advisory never gates" |
| ACM artifact badging | Separate repeatability from independent reproduction | Core gate should target **repeatability** minimum |
| ADR supersession chains | Doctrine changes are auditable events | User vs Sean merge should leave a trace |
| Kleppmann consistency spectrum (analogy) | Prevents vague "deterministic" marketing | Do not literal-map DB consistency to LLM semantics without definition |

---

## 4. Recommended weight & gate recommendation

### 4.1 Dimension placement

Assign criteria R1–R8 primarily to audit dimension **"hybrid architecture / dual determinism reconciliation"** (pairs with P05 hybrid pattern, P06 reproducibility standards; P07 owns **doctrine merge** only).

### 4.2 Suggested weight rationale (deferred numeric value)

| Criterion | Gate? | Weight rationale |
|---|---|---|
| **R4 Non-leakage / complete mediation** | **YES — hard gate** | OWASP + hybrid-system pattern agree: probabilistic layer must not be sole authority. Failure voids "hybrid" claim regardless of composite score. |
| **R1 Layered contract** | **YES — hard gate** | Without named classes, reconciliation is unauditable; mirrors §6.2 "determinism claim replay refutes." |
| R2 ADR reconciliation | Soft gate / high weight | Without decision record, user vs Sean merge cannot be verified post hoc. |
| R7 Scoped replay | **Hard gate for core only** | Core determinism claim must be replay-verified; advisory uses separate stability metric. |
| R3, R5, R6, R8 | Weighted sub-criteria | Lower confidence if missing, but not automatic fail unless they undermine R1/R4/R7. |

**Numeric weights:** Deferred to Opus synthesis per `00-FRAME.md` §6.1 (evidence-backed). This persona recommends **R4 + R1 + core-scoped R7** as the **non-compensatory gate cluster** for the reconciliation dimension.

### 4.3 Confidence band drivers (§6.6)

Uncertainty widens when:

- User or Sean doctrine still undefined (mandatory pre-score blocker).
- Advisory stability (flip rate) unmeasured.
- Dual-truth migration (R8) lacks cutover ADR.

---

## 5. Sources (tiered)

| ID | Tier | Source | URL | Date / version |
|---|---|---|---|---|
| **S1** | 1 | NIST AI Risk Management Framework (AI RMF 1.0), NIST AI 100-1 | https://www.nist.gov/publications/artificial-intelligence-risk-management-framework-ai-rmf-10 | 2023-01-26 |
| **S2** | 1 | ACM Artifact Review and Badging (current policy) | https://www.acm.org/publications/policies/artifact-review-and-badging-current | Current (NISO-harmonized terminology v1.1) |
| **S3** | 1 | ACM / NISO badging terminology change (Reproduced vs Replicated definitions) | https://www.acm.org/publications/badging-terms | Updated post-2020 harmonization |
| **S4** | 1 | Zimmermann, O. et al., "Managing architectural decision models with dependency relations, integrity constraints, and production rules," *Journal of Systems and Software* | https://doi.org/10.1016/j.jss.2009.01.039 | 2009-08 (Vol. 82, Iss. 8) |
| **S5** | 2 | AWS Prescriptive Guidance — Using architectural decision records | https://docs.aws.amazon.com/prescriptive-guidance/latest/architectural-decision-records/architectural-decision-records.pdf | AWS doc (2024 track) |
| **S6** | 2 | Microsoft Azure Well-Architected — Maintain an ADR | https://learn.microsoft.com/en-us/azure/well-architected/architect-role/architecture-decision-record | Microsoft Learn (maintained) |
| **S7** | 2 | ADR dependency typing (`reconciles_with`, `conflicts_with`, migration reconciliation) | https://www.nilus.be/blog/architecture_decision_dependencies_in_adr_systems/ | Practitioner design doc (2024–2025) |
| **S8** | 1 | OWASP Top 10 for LLM Applications — LLM06:2025 Excessive Agency | https://owasp.org/www-project-top-10-for-large-language-model-applications/assets/PDF/OWASP-Top-10-for-LLMs-v2025.pdf | 2025 |
| **S9** | 1 | OWASP Gen AI Security Project — LLM06 Excessive Agency (web summary of v2025) | https://genai.owasp.org/llmrisk/llm06-sensitive-information-disclosure/ | 2025 |
| **S10** | 1 | Kleppmann, M., *Designing Data-Intensive Applications*, Ch. 9 Consistency and Consensus | https://www.oreilly.com/library/view/designing-data-intensive-applications/9781491903063/ch09.html | 2017 (2nd ed. in progress) |
| **S11** | 2 | adr.github.io — Architectural Decision Records organization | https://adr.github.io/ | Maintained |

**Tier 1–2 distinct primary sources used for criteria:** 9 (S1–S6, S8–S10). **Floor met:** ≥ 3.

**Contradiction surfaced:** ACM historically swapped "reproduced" vs "replicated" labels to match NISO ([S3]); audits must cite **current** ACM definitions when scoring replay criteria. Kleppmann consistency guarantees are **analogical** for mixed deterministic/nondeterministic **compute** pipelines—not literal database consistency ([S10]); criteria R6 requires explicit analogy labeling.

---

## 6. Overlap statement

**Confirmed:** This persona did **not**:

- Open, inspect, or score whisker production code; cite no whisker `file:line`; reach no whisker verdict.
- Clone, fork, or copy external code.
- Re-audit whisker deterministic core (`persona/` swarm) or advisory LLM lane (`llm-stack/` swarm).
- Duplicate **P06** (general determinism/reproducibility standards — P07 adds **doctrine reconciliation** only) or **P05** (general hybrid architecture pattern — P07 adds **two-doctrine merge criteria** and preserves open user vs Sean definitions).
- Re-litigate prior adoption/red-team/build-vs-buy verdicts.

**Unique boundary:** No prior research folder addressed **reconciling two determinism doctrines into one contract**; this file supplies that rubric slice for synthesis.

---

## Appendix — Synthesis handoff checklist

Before Opus scores whisker on this dimension:

1. ☐ Obtain **user's** determinism doctrine (written, scoped).
2. ☐ Obtain **Sean's** determinism doctrine (written, scoped).
3. ☐ Map each doctrine to lanes in R1 table.
4. ☐ Apply R2–R8 against documentation + (later) code.
5. ☐ Record contested points per §6.5 if doctrines disagree on guarantee class for the same lane.

**Source count (Tier 1–2 listed in §5):** 9 distinct sources (11 rows; S7/S11 Tier 2; S9 corroborates S8).

**Strongest criterion (highest leverage for pass/fail):** **R4 — Non-leakage boundary / complete mediation** (advisory nondeterminism cannot authoritatively gate), supported by OWASP LLM06 [S8] and aligned with NIST measurement honesty [S1] and hybrid-system one-way boundary precedent in practitioner architecture literature.
