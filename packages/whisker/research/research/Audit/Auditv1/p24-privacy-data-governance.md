# P24 — Privacy & Data-Governance Researcher

**Persona:** 24 of 30 (Cluster G: Provenance, licensing, security, privacy, observability)  
**Date:** 2026-07-18  
**Scope:** External method and standards only. No whisker production-code inspection.

---

## 1. Question restated

What **data-governance and privacy bar** should a WG21 paper extraction-QA pipeline meet when it ingests document content (mostly public committee papers), optionally sends content to LLM inference endpoints (self-hosted or cloud), and retains diagnostic artifacts (trace, debug, prompts, calibration corpora)? This persona produces **proportionate audit criteria**: WG21 papers are overwhelmingly **public-by-design**, which lowers baseline confidentiality risk, but **does not eliminate** governance obligations around author contact data, operator-local copies, log/trace retention, third-party inference, and the **reproducibility-vs-privacy** tension.

---

## 2. Proposed audit criteria

Each criterion is scored on a **0–4 maturity ladder** unless marked as a **hard gate** (pass/fail). Evidence grades follow `00-FRAME.md` §6.3: **A** = multiple Tier-1 corroborating; **B** = single Tier-1 or converging Tier-2; **C** = Tier-3 only or contested; **D** = Tier-4/speculative.

### Criterion G1 — Contextual data-flow inventory and risk tiering

| Field | Value |
|---|---|
| **Criterion** | Documented inventory of every data action (ingest, transform, persist, transmit to LLM, emit in logs/trace/debug, export for calibration) with processing environment (local, self-hosted GPU, third-party API), data-element classes, and a **risk tier** proportional to sensitivity. |
| **How to measure** | Check for a data-flow map listing: source (open-std.org mailing vs local workspace), stored artifacts (`*.pdf`, `*.md`, `*.trace.*`, `*.debug.*`, prompts JSON), LLM transmission points, retention locations. Map to NIST PF ID.IM-P1–P8 inventory subcategories. Explicitly record WG21 paper baseline: **public document body** vs **embedded PII** (author emails in `reply-to`, employer affiliation in headers). |
| **Audit method** | Maturity-model scoring (§5.2) + conformance checklist against NIST Privacy Framework Identify-P |
| **Scoring hook** | §6.1 dimension: security/privacy/supply-chain; §6.3 evidence grade on inventory completeness |
| **Gaming vector** | One-page diagram omitting debug full-I/O path or cloud fallback endpoint. |
| **Anti-gaming guard** | Inventory must enumerate **every persisted artifact type** named in operator docs; spot-check one end-to-end run against map; missing LLM egress = automatic level-0. |
| **Evidence grade** | **A** |
| **Sources** | NIST Privacy Framework Core ID.IM-P1–P8 (Jan 2020); NIST AI RMF 1.0 MAP function (Jan 2023) |

### Criterion G2 — Proportionate processing purpose and public-data doctrine

| Field | Value |
|---|---|
| **Criterion** | Written **purpose limitation** stating QA scope (conversion fidelity/comprehension checking on WG21 papers), legal/operational basis for processing public committee documents, and explicit acknowledgment that **publication on open-std.org does not remove** obligations for derived copies, logs, or third-party inference. |
| **How to measure** | Policy/README section cites: papers are public per ISO/IEC JTC 1 distribution rules (open-std.org); operator workspace copies and diagnostic artifacts are **not automatically public**; any redistribution of derived artifacts requires separate decision. GDPR Art. 5(1)(b) purpose limitation mapped even if GDPR not legally applicable (best practice). |
| **Audit method** | Conformance checklist (§5.1) + documentation-completeness audit (§5.9) |
| **Scoring hook** | §6.1 privacy dimension; §6.4 anti-gaming (purpose statement must constrain actual behavior) |
| **Gaming vector** | Boilerplate "we process public data" with no scope boundary on logs, cloud LLM, or cross-paper retention. |
| **Anti-gaming guard** | Purpose doc must list **prohibited uses** (e.g., training vendor models on ingested papers, publishing debug transcripts) and tie to config flags/defaults. |
| **Evidence grade** | **A** |
| **Sources** | GDPR Art. 5(1)(b) purpose limitation (EUR-Lex 32016R0679); open-std.org papers index ("Most of the papers are available publically, as per ISO/IEC JTC 1 rules") |

**WG21 proportionality note:** For **paper body text**, confidentiality risk is **low** relative to enterprise document pipelines; criteria weight should reflect that. For **author contact fields, operator notes, and local debug bundles**, risk rises to **moderate** because these create non-public copies and may contain PII beyond what operators republish.

### Criterion G3 — Data minimization in processing and LLM prompts

| Field | Value |
|---|---|
| **Criterion** | Technical and procedural **data minimization**: collect/process only fields required for QA gates; LLM prompts include the **minimum excerpt** needed for the advisory task; default path avoids sending full paper when a slice suffices; periodic review that stored fields remain necessary (GDPR Art. 5(1)(c); NIST CT.DM-P; Privacy by Design data minimization). |
| **How to measure** | Review prompt construction and tool scopes: chunk sizes, section filters, redaction of `reply-to` when not needed for comprehension QA. Verify configuration documents minimum scopes. NIST CT.DP-P / ISO 27701 A.7.4.1 collection limitation evidenced. |
| **Audit method** | Conformance checklist + metric construct-validity style review of "what each transmitted byte accomplishes" |
| **Scoring hook** | §6.1 privacy; §6.4 anti-gaming |
| **Gaming vector** | "Minimization" claim while default `--debug` ships entire paper to cloud LLM each run. |
| **Anti-gaming guard** | Measure **bytes transmitted per LLM call vs bytes required** for declared task on sample corpus; fail if ratio exceeds documented ceiling without exception register. |
| **Evidence grade** | **A** |
| **Sources** | GDPR Art. 5(1)(c) data minimisation; NIST PF CT.DM-P + CT.DP-P (Jan 2020); Cavoukian Privacy by Design data minimization principle (2011) |

### Criterion G4 — Debug/trace artifact governance with log minimization (hard gate candidate)

| Field | Value |
|---|---|
| **Criterion** | Separate **trace** (compact progress) vs **debug** (full I/O) policies: retention schedules per artifact class; **debug minimization** where full paper text in logs is not default for routine runs; audit/log records incorporate data minimization (NIST CT.DM-P8); access controls on workspace; secure deletion at end of retention. |
| **How to measure** | Document retention TTL per artifact (`*.trace.*`, `*.debug.*`, prompts JSON, DB rows). Verify trace omits full document bodies where possible. Confirm deletion/disposal procedure (ISO 27701 A.7.4.7–A.7.4.8). Run: produce artifacts → wait policy interval → verify deletion job or manual procedure. |
| **Audit method** | Conformance checklist + observability overlap method (§5.11) limited to **data content** of artifacts, not failure semantics |
| **Scoring hook** | **§6.2 hard gate candidate**: undeclared indefinite retention of full-fidelity debug containing third-party/cloud LLM payloads **fails** regardless of composite score |
| **Gaming vector** | Retention policy in docs only; artifacts accumulate unbounded in workspace. |
| **Anti-gaming guard** | Automated retention job or CI check on workspace age; exception register for holds (calibration, incident) with owner + expiry. |
| **Evidence grade** | **A** |
| **Sources** | NIST PF CT.DM-P8 audit/log minimization; NIST PF CT.PO-P2 retention/deletion; GDPR Art. 5(1)(e) storage limitation |

**Reproducibility-vs-privacy tension (explicit):** Full-fidelity debug aids determinism audits (P06/P25) but **increases privacy surface**. Mature bar: **tiered artifacts** — reproducibility bundles are **opt-in, time-bounded, access-controlled**, not default CI output. Contradiction surfaced, not hidden: NIST AI 600-1 GV-1.5-003 requires TEVV history retention while CT.DM-P8 demands minimization. **Resolution:** retain **hashes, gate verdicts, model IDs, seeds, and redacted excerpts** as default; full I/O only under explicit debug flag with shorter TTL.

### Criterion G5 — Self-hosted vs cloud LLM inference governance

| Field | Value |
|---|---|
| **Criterion** | Documented **inference routing policy**: preferred self-hosted/open-weight endpoints under operator control; cloud/third-party use requires **contractual or policy controls**: no training on customer inputs, data residency, subprocessors, deletion on request, and vendor documentation of inference logging. Align with NIST AI 600-1 Data Privacy + Value Chain risks and OMB M-24-10 vendor data-rights expectations for AI procurement patterns. |
| **How to measure** | `SERVICES.toml` or equivalent documents backend class (self-hosted vs SaaS). For each cloud backend: evidence of no-training terms, retention of vendor logs, DPA/security addendum or provider trust center citation. For self-hosted: network boundary, who can read GPU host storage. |
| **Audit method** | Conformance checklist + provenance/supply-chain method (§5.10) scoped to **data egress**, not SPDX |
| **Scoring hook** | **§6.2 hard gate candidate** if default/cloud path sends document content to provider **without** documented no-training + retention limits |
| **Gaming vector** | "We prefer self-hosted" while CLI default resolves to cloud; optional flag buried. |
| **Anti-gaming guard** | Default config audit + integration test asserting default backend class; cloud use emits stderr warning with data-handling link. |
| **Evidence grade** | **A** |
| **Sources** | NIST AI 600-1 GenAI Profile §4 Data Privacy + Value Chain (Jul 2024); OMB M-24-10 §5 data governance + AI procurement (Mar 2024) |

**Contradiction surfaced:** Model-sovereignty doctrine (internal project invariant) pushes self-hosted; some operators may use cloud for development. **Resolution rule:** audit scores **governance controls**, not ideology — cloud allowed only with **documented, testable** contractual minimization; self-hosted without access control still fails G5.

### Criterion G6 — PII and sensitive-field handling in document pipelines

| Field | Value |
|---|---|
| **Criterion** | Identify **non-public-sensitive fields** in WG21 papers: `reply-to` emails, private correspondence if ever ingested, operator-added notes. Apply field-level handling: suppress in logs, hash for correlation, or tokenize in shared artifacts; red-team privacy (NIST AI 600-1 MS-2.10-001) for memorization/leakage paths. |
| **How to measure** | Sample papers with `reply-to` blocks; verify debug/trace/prompt exports redact or minimize emails unless email fidelity is an explicit QA target. Privacy red-team: query whether LLM outputs reproduce author emails from prior runs. |
| **Audit method** | Adversarial/red-team probing (§5.6) scoped to **privacy leakage**, not gate evasion |
| **Scoring hook** | §6.1 privacy; §6.2 soft gate if emails appear in default trace |
| **Gaming vector** | Redact in trace but leave emails in prompts JSON on disk. |
| **Anti-gaming guard** | Grep-based CI canary on artifact directory for email regex patterns in default mode. |
| **Evidence grade** | **B** |
| **Sources** | NIST AI 600-1 MS-2.10-001 privacy red-teaming; GDPR Art. 4(1) personal data definition (EUR-Lex) |

### Criterion G7 — Retention, deletion, and decommissioning lifecycle

| Field | Value |
|---|---|
| **Criterion** | End-to-end **data lifecycle**: retention schedules by artifact and backend; secure disposal; decommission checklist covering data leakage after shutdown (NIST AI 600-1 GV-1.7-002: retention requirements, containment, dependencies). Calibration corpora labeled with provenance and TTL distinct from production logs. |
| **How to measure** | Table: artifact type → purpose → max retention → deletion method → legal hold exception. Decommission drill: remove tool → verify workspace + model host + backup scopes. ISO 27701 A.7.4.7–A.7.4.8 alignment. |
| **Audit method** | Maturity model (§5.2) + conformance checklist |
| **Scoring hook** | §6.1 privacy; §6.6 uncertainty if retention contested |
| **Gaming vector** | Retention table excludes SQLite DB or prompt cache. |
| **Anti-gaming guard** | Inventory (G1) must be join key for retention table — every persisted store appears in both. |
| **Evidence grade** | **A** |
| **Sources** | NIST AI 600-1 GV-1.7-002 decommissioning factors; NIST PF CT.PO-P2; GDPR Art. 5(1)(e); ISO/IEC 27701:2025 A.7.4.7–A.7.4.8 (Oct 2025) |

### Criterion G8 — Third-party and subprocessors in the data-processing ecosystem

| Field | Value |
|---|---|
| **Criterion** | For each third party receiving content (cloud LLM, hosted OCR, mailing scrape CDN): contract or public terms covering processing purpose, retention, subprocessors, audit rights; NIST PF ID.DE-P3–P5 ecosystem management. |
| **How to measure** | Subprocessor list; annual review record; mapping from `SERVICES.toml` slot to vendor terms URL + version date. |
| **Audit method** | Conformance checklist + provenance audit (§5.10) |
| **Scoring hook** | §6.1 privacy/supply-chain overlap with P03 — **boundary:** P03 covers SBOM/SLSA; this criterion covers **data-processing agreements** only |
| **Gaming vector** | Link to generic ToS without inference-specific addendum. |
| **Anti-gaming guard** | Require capture of **inference-specific** data handling statement (API data usage policy) with review date in repo docs. |
| **Evidence grade** | **B** |
| **Sources** | NIST PF ID.DE-P1–P5; NIST AI 600-1 Value Chain and Component Integration risk |

### Criterion G9 — Privacy-enhanced defaults (Privacy by Design)

| Field | Value |
|---|---|
| **Criterion** | **Privacy as default:** routine QA runs do not enable full debug, do not use cloud LLM unless configured, do not retain beyond default TTL; opt-in flags for higher-fidelity/reproducibility modes with conspicuous operator notice. Cavoukian Principle 2; GDPR Art. 25 data protection by design/default where applicable. |
| **How to measure** | Default CLI/config profile documented; `--debug` / cloud backend require explicit flags; first-run or `--help` summarizes data handling. |
| **Audit method** | Documentation-completeness + conformance checklist |
| **Scoring hook** | §6.4 anti-gaming; §6.1 privacy |
| **Gaming vector** | Secure defaults in docs but dev `.env` committed with cloud keys + debug on. |
| **Anti-gaming guard** | `.env.example` shows safe defaults; CI runs default profile only; secrets scan blocks committed credentials. |
| **Evidence grade** | **B** |
| **Sources** | Cavoukian Privacy by Design Principles 1–2 (2011); GDPR Art. 25 (EUR-Lex) |

### Criterion G10 — Governance documentation and accountability

| Field | Value |
|---|---|
| **Criterion** | Named governance artifacts: data-handling section in operator docs; who may access workspace; incident response for accidental exfiltration (debug bundle shared publicly); alignment with NIST PF Govern-P (GV.PO-P, GV.MT-P) and AI RMF GOVERN function. |
| **How to measure** | Docs list roles (even if single maintainer), review cadence for retention policy, contact for privacy questions. |
| **Audit method** | Maturity model + documentation-completeness audit |
| **Scoring hook** | §6.1 privacy; feeds P20 doc matrix without duplicating general doc rubric |
| **Gaming vector** | Generic "contact security@" with no WG21-tool-specific guidance. |
| **Anti-gaming guard** | Doc must mention **artifact types and LLM routing** by name; generic boilerplate scores ≤ level 1. |
| **Evidence grade** | **B** |
| **Sources** | NIST PF Govern-P GV.PO-P1, GV.MT-P1–P4; OMB M-24-10 governance + CAIO patterns (adapted for OSS operator context) |

---

## 3. External benchmark / exemplar bar

### Tier-1 synthesis: what "good" looks like for a WG21 QA tool

| Bar | Expectation |
|---|---|
| **Floor** | G1 inventory + G2 purpose statement + G4 retention policy exists (even if manual deletion) |
| **Professional** | G3 minimization operationalized; G5 inference routing documented; G7 lifecycle table covers all stores; defaults per G9 |
| **Best defensible** | G4 tiered debug with minimization + TTL; G5 self-hosted default with cloud exception register; G6 privacy red-team canary; G8 vendor reviews dated; reproducibility bundles **explicitly scoped** (hash-first, full I/O rare) |

### Public WG21 context lowers but does not zero privacy work

| Factor | Risk implication |
|---|---|
| Paper PDF/HTML on open-std.org | **Low confidentiality** for committee submission content; aligns with OMB M-24-10 encouragement of appropriate **publicly available information** use |
| Author `reply-to` and affiliation | **Moderate** — public in paper but still **personal data** under GDPR; unwanted aggregation in logs increases harm |
| Local workspace + debug | **Moderate** — non-public copies; combine with cloud LLM → **elevated** third-party exposure |
| Calibration/golden corpora | **Moderate** — intentional retention; needs provenance + TTL (P11 overlap boundary) |

### Reproducibility vs privacy: accepted industry pattern

NIST AI 600-1 simultaneously demands **TEVV history** (GV-1.5-003) and warns of **data privacy leakage** from GAI (Risk #4). Mature systems resolve with **layered retention**: long-lived **verdict metadata**, short-lived **full I/O captures**. This matches Privacy by Design **end-to-end lifecycle** principle: secure destruction when purpose ends.

---

## 4. Recommended weight & gate recommendation

| Recommendation | Rationale |
|---|---|
| **Dimension weight: 8%** of composite (privacy/governance within security/privacy/supply-chain cluster shared with P03, P23) | WG21 public papers reduce absolute privacy risk vs enterprise PII pipelines; weight is **non-zero** because debug/trace + LLM egress create real governance obligations and reputational harm if mishandled. |
| **Hard gates (conjunctive): G4, G5** | **G4:** Indefinite full-fidelity debug without minimization/TTL is unbounded storage of document content (GDPR Art. 5(1)(e); NIST CT.DM-P8). **G5:** Undocumented cloud inference on paper content without no-training/retention assurances fails vendor governance bar (NIST AI 600-1 Data Privacy). |
| **Soft gates (cap dimension at level 2): G1, G3** if failed | Missing inventory or minimization means other controls cannot be verified. |
| **Proportionality adjustment** | Synthesis may apply **−30% weight discount** to G6 (email PII) if operator scope excludes `reply-to` from all processing; must document exclusion, not assume. |
| **Evidence propagation** | Dimension inherits weakest grade among G4, G5, G7 (likely **A** if policies exist; **C** if cloud terms undocumented). |
| **Contested handling** | Self-hosted vs cloud default: prefer **documented controls** over deployment ideology (§6.5); mark contested if team disputes cloud ban. |

---

## 5. Sources

### Tier 1 — Authoritative / primary

| ID | Source | URL | Date/version |
|---|---|---|---|
| S1 | NIST Privacy Framework v1.0 (full) | https://nvlpubs.nist.gov/nistpubs/CSWP/NIST.CSWP.01162020.pdf | Jan 16, 2020 |
| S2 | NIST Privacy Framework Core (ID/CT/PR subcategories) | https://www.nist.gov/system/files/documents/2021/05/05/NIST-Privacy-Framework-V1.0-Core-PDF.pdf | Jan 16, 2020 |
| S3 | NIST AI Risk Management Framework 1.0 | https://www.nist.gov/itl/ai-risk-management-framework | Jan 26, 2023 |
| S4 | NIST AI 600-1 Generative AI Profile | https://doi.org/10.6028/nist.ai.600-1 | Jul 26, 2024 |
| S5 | GDPR Regulation (EU) 2016/679 Art. 5 principles | https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX%3A02016R0679-20160504 | Apr 27, 2016 |
| S6 | GDPR Art. 25 — Data protection by design and by default | https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A02016R0679 | Apr 27, 2016 |
| S7 | Cavoukian — Privacy by Design: 7 Foundational Principles | https://www.sfu.ca/~palys/Cavoukian-2011-PrivacyByDesign-7FoundationalPrinciples.pdf | 2011 |
| S8 | OMB Memorandum M-24-10 (agency AI governance) | https://www.whitehouse.gov/wp-content/uploads/2024/03/M-24-10-Advancing-Governance-Innovation-and-Risk-Management-for-Agency-Use-of-Artificial-Intelligence.pdf | Mar 28, 2024 |
| S9 | ISO/IEC 27701:2025 Privacy Information Management (A.7.4.x controls) | https://www.iso.org/standard/85951.html | Oct 14, 2025 |

### Tier 2 — Strong secondary

| ID | Source | URL | Date/version |
|---|---|---|---|
| S10 | open-std.org WG21 papers index (public availability statement) | https://www.open-std.org/jtc1/sc22/wg21/docs/papers/ | accessed 2026-07-18 |
| S11 | wg21.org community resources (public paper archive) | https://wg21.org/community/ | accessed 2026-07-18 |
| S12 | NIST news release — AI 600-1 final publication | https://www.nist.gov/news-events/news/2024/07/department-commerce-announces-new-guidance-tools-270-days-following | Jul 2024 |

### Tier 3 — Contextual (corroboration only)

| ID | Source | URL |
|---|---|---|
| S13 | BSI ISO/IEC 27701:2025 transition summary | https://www.bsigroup.com/en-GB/products-and-services/standards-services/iso-iec-27701-key-changes-and-guidance/ |

**Source count:** 9 Tier-1 + 3 Tier-2 = **12 distinct Tier 1–2 sources** (floor ≥3 satisfied).

**Contradictions surfaced (not hidden):**

1. **TEVV retention vs minimization:** NIST AI 600-1 GV-1.5-003 vs NIST PF CT.DM-P8 — resolved by tiered artifacts (§3).
2. **Public paper vs PII in headers:** open-std.org public distribution vs GDPR personal data for emails — resolved by field-level handling (G6), not blanket "public = no privacy."
3. **Reproducibility vs privacy:** determinism audit wants full debug; privacy wants deletion — resolved by opt-in, TTL-bound full I/O (G4).

---

## 6. Overlap statement

This persona researched **external privacy and data-governance standards only**. It did **not** open whisker production code, cite whisker `file:line`, score whisker, clone/fork/copy code, or duplicate:

- **`p23-security-prompt-injection.md`** — prompt-injection and trust-boundary **security** (this persona covers **data handling, retention, inference routing, PII minimization**).
- **`p25-observability-failure-handling.md`** — trace/debug **semantics and fail-closed behavior** (this persona covers **what data those artifacts may contain and how long they live**).
- **`p03-dependency-supply-chain.md`** — SBOM/SLSA/vuln scanning (this persona covers **data-processing vendor terms**, not package integrity).
- **`persona/` / `llm-stack/`** — prior whisker code audits.
- **`p11-ground-truth-corpus.md`** — annotation methodology (this persona references calibration retention only at G7 boundary).

Boundary held: **privacy/governance criteria and external bar**, proportionate to a **public WG21 paper QA tool**, handed to synthesis as rubric inputs for the privacy/governance dimension.
