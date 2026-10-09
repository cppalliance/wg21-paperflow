# P05 — Hybrid Deterministic-Core + Advisory-LLM Architecture Research

**Persona:** 5 of 30 (Cluster B — Architecture & hybrid deterministic+LLM design)  
**Date:** 2026-07-18  
**Stage:** 0 evidence framing (external method only; no whisker code inspection)

---

## 1. Question restated

What is the external bar for a **strict deterministic core with an opt-in, never-gating advisory LLM overlay**—the architectural pattern where a trusted decision path remains fully deterministic while a nondeterministic assistive layer may suggest, warn, or enrich but must never become authoritative? Specifically:

- How do serious systems **separate** authoritative (gating) decisions from advisory (assistive) outputs?
- What does a one-way **demote-only ratchet** look like in practice (advisory may downgrade confidence or flag issues, but cannot promote a failing deterministic verdict to pass)?
- How is **lane isolation** enforced so LLM-as-judge or LLM-as-oracle cannot create **confirmation bias** (e.g., judging artifacts it influenced)?
- What **fail-safe / fail-closed** posture applies when the advisory layer errors, times out, or is disabled?
- How does an auditor **verify** that the separation actually holds in implementation, not merely in documentation?

This persona researches the **general pattern and audit method**. It does not inspect whisker production code, score tapetum isolation, or address batch/throughput design.

---

## 2. Proposed audit criteria

Each criterion includes: measure, audit-method (from `00-FRAME.md` §5), scoring-design hook (§6), gaming vector + anti-gaming guard, evidence grade, and Tier 1–2 citations.

---

### Criterion H1 — Authoritative vs advisory epistemic separation

**Statement:** The system maintains a strict semantic boundary: **authoritative** state (deterministic gate verdicts, validated thresholds, persisted pass/fail) is distinct from **advisory** state (LLM suggestions, judge scores, oracle hints). Advisory entities may reference authoritative context but **must not modify or replace** authoritative elements without an explicit, auditable human-validation step.

**How to measure:**
- Trace data-flow from LLM output to any field that affects exit code, CI gate, or persisted verdict.
- Confirm no write path from advisory modules into authoritative verdict structures except through a documented, human-gated promotion API (if any).
- Review type/schema boundaries: advisory outputs use separate types or namespaces from gate results.

**Audit-method:** Conformance checklist (§5.1) + maturity-model scoring (§5.2).

**Scoring-design hook:** Feeds **§6.2 hard gates** (candidate: "LLM signal that can hard-gate violates advisory contract") and **§6.1 architecture/hybrid dimension**.

**Gaming vector:** Document an "advisory overlay" that is never invoked in CI, satisfying separation on paper while production silently uses LLM to gate.

**Anti-gaming guard:** Require **runtime call-graph evidence** from integration tests: run with LLM enabled and disabled; prove exit codes and authoritative artifacts are identical when advisory returns pass; prove advisory cannot flip a deterministic fail to pass under fault-injection (see H6).

**Evidence grade:** A (multiple Tier-1 sources converge on authoritative/advisory distinction).

**Sources:** SACO (Shamsaei et al., 2026); NIST AI RMF Appendix C / Playbook Govern 3.2 & MAP 3.4 (Tabassi, 2023).

---

### Criterion H2 — Deterministic enforcement on the critical path

**Statement:** All **safety- and quality-gating** decisions on the critical path are computed by **deterministic code** (rules, metrics, thresholds, schema validation). LLM components sit **off** the critical path or behind a deterministic policy-enforcement point (PEP) that enforces verdicts without delegating authorization to the model.

**How to measure:**
- Map the critical path from input document to pass/fail verdict; mark each step as deterministic vs probabilistic.
- Verify no LLM `run`/`complete`/`agent.run` call sits between final metric aggregation and verdict emission without an intervening deterministic PEP.
- Static analysis or import-layer check: gating modules must not import advisory LLM backends.

**Audit-method:** Conformance checklist (§5.1) + observability/fault-injection audit (§5.11).

**Scoring-design hook:** **§6.2 hard gate** (non-negotiable for hybrid claim); **§6.1 architecture/hybrid dimension**.

**Gaming vector:** Run deterministic checks first in docs, but implement `if llm_says_pass: override_metrics()`.

**Anti-gaming guard:** **Canary injection test:** feed a document that passes all deterministic metrics but fails a planted LLM-judge check; verdict must remain deterministic pass. Reverse canary: deterministic fail must not be cleared by LLM pass.

**Evidence grade:** A.

**Sources:** OWASP LLM06 Excessive Agency (2025); NIST AI RMF Playbook MAP 3.5 (2023); Asimov Safety Architecture draft Gate 1 ordering (Baysal, 2026).

---

### Criterion H3 — Parallel independent monitoring path (shutdown-system analogy)

**Statement:** The deterministic gate operates as an **independent channel** analogous to a safety-critical **shutdown system**: it has its own inputs (metrics, rules), runs in parallel with (not downstream of) the advisory lane, and can force a safe/fail state regardless of advisory opinion. Advisory lane failure must not disable the monitoring path.

**How to measure:**
- Architecture diagram or module graph showing two parallel lanes merging only at a **one-way join** (advisory may annotate; gate decides).
- Kill-switch test: disable LLM endpoint; pipeline completes with full deterministic verdict.
- Compare to embedded **shutdown-system** pattern: primary system + independent monitor with separate sensors.

**Audit-method:** Comparative benchmarking against exemplars (§5.3) + fault-injection audit (§5.11).

**Scoring-design hook:** **§6.1 architecture/hybrid**; supports **§6.6 flip-condition** analysis ("what if advisory lane becomes load-bearing?").

**Gaming vector:** Sequential pipeline labeled "parallel" where deterministic step reads LLM-enriched features.

**Anti-gaming guard:** **Feature-provenance audit:** every input to deterministic gate must trace to non-LLM sources or to deterministic transforms of fixed inputs; LLM-derived features forbidden on gate input list.

**Evidence grade:** B (Tier-1 safety pattern via IEC 61508 / embedded literature; analogy to QA pipelines is Tier-2 inference).

**Sources:** Embedded.com safety-critical shutdown architecture (Barr, 2013); IEC 61508 MooN structures (HIMA, 2024); SACO deterministic reconstruction requirement (Shamsaei et al., 2026).

---

### Criterion H4 — Demote-only ratchet (no silent promotion)

**Statement:** Information flow from advisory → authoritative is **monotone demoting**: advisory output may add warnings, lower confidence bands, or attach `advisory_fail` annotations, but **cannot promote** a deterministic failure to pass, raise a score above a gate threshold, or remove a failed check. The only permitted "promotion" path requires explicit human validation recorded with provenance.

**How to measure:**
- Enumerate all advisory→authoritative write APIs; verify each is append-only annotation or demotion (flag, downgrade), never deletion of fail state.
- Property test: for any input where deterministic verdict is `fail`, no sequence of advisory outputs can yield `pass` without human-validation event in audit log.
- Review changelog/ADR for "LLM override" features.

**Audit-method:** Anti-gaming / Goodhart stress (§5.7) + reproducibility replay (§5.8).

**Scoring-design hook:** **§6.2 hard gate**; **§6.4 anti-gaming rules** (prevents cosmetic hybrid compliance).

**Gaming vector:** Advisory "recommendation" field interpreted by CLI as soft pass when deterministic fail is present.

**Anti-gaming guard:** **Exit-code contract test:** deterministic fail + advisory pass → non-zero exit; deterministic pass + advisory fail → still zero exit (advisory never gates). Document the contract in operator docs and test it.

**Evidence grade:** A.

**Sources:** SACO advisory entities "not permitted to modify or replace authoritative context" (Shamsaei et al., 2026); OWASP LLM06 "require user approval" for high-impact actions (2025); NIST AI RMF on selective adherence / automation bias (Tabassi, 2023, citing Alon-Barkat & Busuioc, 2022).

---

### Criterion H5 — Lane isolation and judge independence (anti-confirmation-bias)

**Statement:** When an LLM serves as judge or oracle, it must be **isolated** from the artifact-under-test generation path: no shared prompt context that leaks prior model influence; prefer **stateless, context-free** judge calls; separate model instance or session from producer; blind evaluation where the judge does not know which tool produced the output.

**How to measure:**
- Dependency graph: judge module must not import or call converter/QA logic it evaluates.
- Prompt audit: judge prompts must not include chain-of-thought from the producer model.
- Bias stability tests: position-consistency and repetition-stability metrics on held-out judge set (see Shi et al., 2025).
- For dual-gate designs: judge model ≠ reasoner model (ASA P1).

**Audit-method:** Metric construct-validity audit (§5.4) + adversarial probing (§5.6).

**Scoring-design hook:** **§6.1 architecture/hybrid**; **§6.3 confidence** (judge bias lowers evidence grade for advisory scores).

**Gaming vector:** Reuse same LLM session for extraction and evaluation; claim "isolation" via different prompt templates only.

**Anti-gaming guard:** **Blind swap test:** evaluate tool A output with judge configured for tool B neutrality; verdict distribution must not collapse when producer identity is hidden. Measure position-bias metrics per Shi et al. (2025) on internal judge harness.

**Evidence grade:** A.

**Sources:** Shi et al., IJCNLP 2025 (position bias); Zheng et al., NeurIPS 2023 (LLM-as-judge limitations); ASA draft §9 stateless judge requirement (Baysal, 2026); HITL systematic review on trust calibration (Rahman et al., 2026).

---

### Criterion H6 — Fail-closed / fail-safe default for advisory failure

**Statement:** When the advisory LLM is unavailable, times out, returns invalid schema, or is explicitly disabled, the system **defaults to the deterministic verdict unchanged** (fail-safe for QA: a failed doc stays failed; a passed doc stays passed). Advisory failure must not crash the pipeline into partial output, must not downgrade deterministic pass, and must not bypass deterministic fail. For **security-adjacent** boundaries, prefer **fail-closed** (deny) when enforcement layer itself fails.

**How to measure:**
- Fault injection: LLM 503/timeout, malformed JSON, empty response, max-token truncation.
- Verify deterministic artifacts and exit codes match no-LLM baseline.
- Distinguish QA fail-safe (preserve deterministic outcome) vs security fail-closed (block on enforcement error) per use case; document which applies where.

**Audit-method:** Observability / fault-injection audit (§5.11) + conformance checklist (§5.1).

**Scoring-design hook:** **§6.2 hard gate** (partial result on advisory failure = fidelity violation); **§6.1 observability/failure** overlap.

**Gaming vector:** Catch LLM exception and treat as advisory pass ("benefit of the doubt").

**Anti-gaming guard:** **Fault matrix test:** catalog N advisory failure modes; assert zero change to authoritative verdict for each. Log advisory failures at WARN+ without altering exit code.

**Evidence grade:** A.

**Sources:** OWASP LLM06 least privilege + downstream authorization (2025); Wikipedia/engineering fail-safe vs fail-secure distinction (foundational); Embedded.com shutdown on monitor untrustworthiness (Barr, 2013); NIST AI RMF Manage function on drift and negative impacts (Tabassi, 2023).

---

### Criterion H7 — Documented human–AI authority gradient

**Statement:** Architecture docs and operator guidance explicitly place each component on an **authority gradient** (advisory → persuasive → authoritative → autonomous) and justify the chosen level. Hybrid QA tools must document themselves at **advisory** for the LLM lane and **authoritative** for the deterministic gate, including known automation-bias risks for operators.

**How to measure:**
- Documentation matrix: each feature tagged with authority level and override mechanics.
- Check for NIST Govern 3.2 / MAP 3.4 elements: differentiated human roles, proficiency requirements, selective-adherence risks.
- Operator runbook states: "LLM output is never sufficient to ship."

**Audit-method:** Documentation-completeness audit (§5.9) + maturity-model scoring (§5.2).

**Scoring-design hook:** **§6.1 documentation/operator-UX** cross-dimension; **§6.4 anti-gaming** ("documented" → operator can reproduce run understanding advisory limits).

**Gaming vector:** CLAUDE.md claims advisory-only; user-facing README implies "AI-verified quality."

**Anti-gaming guard:** **Doc/code alignment spot check:** grep user-facing strings for "AI-approved", "LLM-verified pass", etc.; must match advisory contract.

**Evidence grade:** B (NIST + sociotechnical literature; gradient framing also in practitioner SWE writing).

**Sources:** NIST AI RMF Appendix C human-AI configurations (2023); NIST Playbook Govern 3.2 / MAP 3.4 (2023); SWE All Together authority-gradient article (2026); HITL systematic review governance section (Rahman et al., 2026).

---

### Criterion H8 — Opt-in advisory with zero default agency

**Statement:** The advisory LLM lane is **opt-in** (explicit flag, extra, or subcommand), default-off in CI/release paths, and granted **no tools, plugins, or side effects** beyond emitting structured advisory records. Matches "least functionality / least permission" for LLM components.

**How to measure:**
- Default invocation path never calls LLM.
- Optional extra dependency group; CI matrix includes LLM-off job as required check.
- Tool/API surface audit: advisory agent has read-only scoped tools at most; no write, network, or exec beyond model endpoint.

**Audit-method:** Conformance checklist (§5.1) against OWASP LLM06.

**Scoring-design hook:** **§6.2 hard gate** candidate; **§6.1 architecture/hybrid**.

**Gaming vector:** LLM off by default but `WHISKER_SKIP_LLM=0` in hidden config; or test suite mocks LLM while prod enables it.

**Anti-gaming guard:** **Release-path test:** run full QA on golden corpus with zero LLM env vars set; must succeed. Count LLM HTTP calls = 0 via network stub.

**Evidence grade:** A.

**Sources:** OWASP Top 10 for LLM Applications 2025, LLM06 (2025); NIST AI RMF Map 3.5 human oversight proportional to risk (2023).

---

### Criterion H9 — Auditability of boundary crossings

**Statement:** Every boundary crossing (deterministic verdict emitted, advisory attached, human promotion if any) produces **append-only, labeled audit records** suitable for trace/debug separation: concise progress trace vs full-fidelity I/O debug, with advisory calls logged separately from gate steps.

**How to measure:**
- Trace artifact lists gate steps and advisory steps under distinct headings.
- Debug log includes model/prompt identity for advisory calls but gate steps show rule/threshold inputs only.
- Replay: given trace + inputs, deterministic verdict reproducible without advisory logs.

**Audit-method:** Observability audit (§5.11) + reproducibility replay (§5.8).

**Scoring-design hook:** **§6.3 evidence grades**; **§6.6 sensitivity** (can auditor drop advisory logs and still verify gate?).

**Gaming vector:** Single merged log mixing LLM prose with gate verdict, impeding replay.

**Anti-gaming guard:** **Replay-without-advisory test:** reconstruct verdict from gate-only log slice; must match full run.

**Evidence grade:** B.

**Sources:** SACO provenance and deterministic reconstruction (Shamsaei et al., 2026); NIST AI RMF Measure/Manage logging guidance (2023).

---

## 3. External benchmark / exemplar bar

### Tier 1–2 convergence (what "good" looks like)

| Pattern element | External bar | Exemplar source |
|---|---|---|
| Authoritative vs advisory semantics | Formal epistemic separation; advisory cannot mutate authoritative context | SACO ontology (Applied Sciences, 2026) |
| Critical-path determinism | Deterministic gate before any probabilistic judge; PEP/PDP split | ASA Gate 1 → Gate 2 ordering (IETF draft, 2026); XACML PEP pattern (cited in policy-enforcement literature) |
| Independent monitor channel | Parallel shutdown/monitor with separate inputs | Safety-critical shutdown architecture (Embedded.com, 2013); IEC 61508 MooN |
| LLM never self-gates | No excessive agency; human approval for high-impact; least tools | OWASP LLM06:2025 |
| Human–AI configuration clarity | Explicit roles; map autonomy spectrum; counter automation bias | NIST AI RMF 1.0 + Playbook Govern 3.2, MAP 3.4–3.5 (2023) |
| Judge bias containment | Position/verbosity/self-preference measured; stateless judge | Zheng et al. NeurIPS 2023; Shi et al. IJCNLP 2025 |
| Fail-safe on advisory loss | Deterministic outcome preserved | Fail-safe engineering principle; shutdown on monitor failure |
| Opt-in assistive AI | Default manual/deterministic path; AI as "additional opinion" | NIST Appendix C: "used by a human decision-maker as an additional opinion" |

### Maturity ladder (proposed 0–4 descriptors for synthesis)

| Level | Hybrid architecture maturity |
|---|---|
| **0** | LLM output directly affects pass/fail or exit code; no documented separation. |
| **1** | Deterministic checks exist but LLM can override or share critical-path features; separation documented only. |
| **2** | Deterministic gate authoritative; LLM advisory by convention but boundary not fully tested; demotion not proven. |
| **3** | Proven demote-only ratchet, opt-in LLM, fault-injection passed, lane isolation in module graph; trace/debug separated. |
| **4** | Level 3 plus blind judge bias metrics on record, human-authority gradient documented, independent monitor analogy implemented and tested, replay without advisory reproduces gate. |

### Contradictions surfaced (not hidden)

1. **Dual-gate with LLM judge (ASA Gate 2) vs zero LLM on critical path:** ASA places a **stateless LLM judge** after deterministic Gate 1 for *action-execution agents*. For **QA gating**, the stricter reading (supported by OWASP + SACO) is: LLM judge output remains **advisory** even when present; only deterministic Gate 1 may gate. ASA is cited as **partial exemplar** (separation of reasoner and judge), not as license to LLM-gate QA verdicts.

2. **LLM-as-judge reliability (Zheng et al. ~80%+ human agreement) vs bias studies (Shi et al. systematic position bias):** Judges are useful **assistive metrics** but construct-validity audit (P10) must gate trust. Hybrid architecture criterion: judge scores **must not** hard-gate regardless of agreement statistics.

3. **Fail-safe vs fail-closed:** QA pipelines should be **fail-safe** on advisory loss (preserve deterministic outcome). Security enforcement at trust boundaries should be **fail-closed** (OWASP/NIST). Audits must tag which boundary applies; conflating them is a design error.

4. **Human-in-the-loop as rubber stamp:** NIST and public-administration literature (Alon-Barkat & Busuioc, 2022; Green, 2021) warn that nominal HITL does not satisfy oversight if selective adherence persists. Hybrid design must keep humans **able to override advisory**, not required to approve deterministic fails.

---

## 4. Recommended weight & hard-gate rationale

### Hard gates (§6.2) — recommend **yes** for:

| Gate | Criterion | Rationale |
|---|---|---|
| **LLM hard-gating** | H1, H2, H4, H8 | OWASP LLM06 + NIST human-AI role separation + SACO authoritative/advisory split converge: a system claiming "deterministic core" that lets LLM flip pass/fail **fails the hybrid contract** regardless of weighted score elsewhere. Matches `00-FRAME.md` §6.2 candidate gate verbatim. |
| **Advisory failure → partial/m wrong verdict** | H6 | Fidelity doctrine: fail-not-partial. Fault-injection must show unchanged deterministic outcome. |
| **Demote-only violation** | H4 | Single promotion path without human validation collapses hybrid into LLM-gated QA. |

### Weighted dimension (§6.1) — architecture/hybrid

Recommend **high weight** within the architecture/hybrid dimension (exact numeric weight deferred to synthesis with P07/P08 evidence):

- **Load-bearing criteria:** H1, H2, H4, H5, H6, H8 ( collectively define whether hybrid claim is true).
- **Supporting criteria:** H3, H7, H9 ( strengthen auditability and operator understanding).
- **Rationale:** The Stage 0 objective (`00-FRAME.md` §1) lists hybrid design as a first-class audit question. External standards (NIST, OWASP, SACO) treat autonomy/separation as **risk-proportional non-negotiables** for systems that could harm integrity of decisions—not optional maturity nice-to-haves.

### Confidence / evidence grade for this persona's package

Overall persona evidence grade: **A** (multiple Tier-1 standards + peer-reviewed papers agree on separation; exemplar drafts align). Confidence: **high** for gating/separation criteria; **medium** for exact maturity level descriptors (synthesis may refine with P07 dual-determinism reconciliation).

---

## 5. Sources

Sources ranked by tier. Floor met: **≥3 distinct Tier 1–2** (actual count: **10** Tier 1–2).

### Tier 1 — Authoritative / primary

| ID | Source | Version / date | URL |
|---|---|---|---|
| S1 | NIST AI Risk Management Framework (AI RMF 1.0), NIST AI 100-1 | 2023-01-26 | https://www.nist.gov/publications/artificial-intelligence-risk-management-framework-ai-rmf-10 |
| S2 | NIST AI RMF Playbook (Govern 3.2, MAP 3.4–3.5, Appendix C human-AI interaction) | 2023 | https://airc.nist.gov/docs/AI_RMF_Playbook.pdf |
| S3 | OWASP Top 10 for LLM Applications 2025 (LLM06: Excessive Agency) | 2025 | https://owasp.org/www-project-top-10-for-large-language-model-applications/assets/PDF/OWASP-Top-10-for-LLMs-v2025.pdf |
| S4 | Shamsaei et al., "Ontological Foundations for Deterministic Assurance Context Construction and Governed AI Reasoning" (SACO) | *Applied Sciences* 16(4):1984, 2026 | https://www.mdpi.com/2076-3417/16/4/1984 |
| S5 | Shi et al., "Judging the Judges: A Systematic Study of Position Bias in LLM-as-a-Judge" | IJCNLP/AACL 2025 | https://aclanthology.org/2025.ijcnlp-long.18/ |
| S6 | Zheng et al., "Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena" | NeurIPS 2023 D&B | https://proceedings.neurips.cc/paper_files/paper/2023/file/91f18a1287b398d378ef22505bf41832-Paper-Datasets_and_Benchmarks.pdf |
| S7 | Rahman et al., "Human-in-the-Loop Artificial Intelligence: A Systematic Review of Concepts, Methods, and Applications" | *Entropy* 28(4):377, 2026 | https://www.mdpi.com/1099-4300/28/4/377 |
| S8 | IEC 61508 (functional safety); MooN architecture guidance | Ed. 2 (2010), cited 2024–2025 | https://www.hima.com/en/shareandexplore/structures_of_safety-critical_systems |

### Tier 2 — Strong secondary

| ID | Source | Version / date | URL |
|---|---|---|---|
| S9 | Baysal, "The Asimov Safety Architecture for Autonomous AI Agents" (Internet-Draft) | 2026-03-27 | https://datatracker.ietf.org/doc/html/draft-baysal-asimov-safety-architecture-00 |
| S10 | Barr, "Architecture of safety-critical systems" (shutdown / dual-channel patterns) | Embedded.com, 2013 | https://www.embedded.com/architecture-of-safety-critical-systems/ |

### Tier 3 — Contextual (not load-bearing alone)

- Alon-Barkat & Busuioc, automation bias / selective adherence, *JPART* 2022 (cited via NIST Playbook).
- SWE All Together, "Human Systems & AI: authority gradient" (2026).

---

## 6. Overlap statement

**Confirmed:** This persona did **not** open, inspect, or score whisker production code. No whisker `file:line` citations. No verdict on tapetum implementation.

**Prior folders avoided:**
- **`llm-stack/`** — that swarm performed a code-level audit of whisker's advisory LLM lane (isolation, cascade, injection). This persona researches the **general hybrid pattern and audit method** only.
- **`persona/`** — code-level deterministic-core audit; not duplicated.
- **`llm-batching/`** — throughput/concurrency excluded per roster boundary.

**Handoff to synthesis:** Criteria H1–H9, maturity ladder, hard-gate recommendations, and contradiction notes feed the architecture/hybrid dimension and §6.2 gate list. P07 (dual-determinism reconciliation) and P08 (modularity boundaries) should be read alongside this file without merging criteria blindly.

---

**Source count (Tier 1–2):** 10  
**Strongest criterion:** **H1 — Authoritative vs advisory epistemic separation** (SACO + NIST + OWASP convergence; directly encodes the hybrid contract and supports the recommended LLM hard-gating gate)
