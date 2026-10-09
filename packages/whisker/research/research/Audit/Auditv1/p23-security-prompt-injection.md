# P23 — Security & Prompt-Injection Defense Researcher

**Persona:** 23 of 30 (Cluster G: Provenance, licensing, security, privacy, observability)  
**Date:** 2026-07-18  
**Scope:** External method and standards only. No whisker production-code inspection.

---

## 1. Question restated

What is the **external security bar** for a pipeline that feeds **untrusted document and web text** to LLMs (directly or via retrieval), and how should that bar become **repeatable audit criteria** with candidate **hard gates**? This persona covers: prompt-injection and indirect prompt-injection defense (delimiter escaping, treat content as data not instructions, structured output validation), OWASP LLM Top 10 alignment (especially LLM01, LLM05, LLM06), input validation at trust boundaries, tool/scope least privilege, the NIST AI RMF / GenAI Profile / AML taxonomy posture on injection, and **how to test** injection defenses before deployment.

**Primary threat model for a WG21 document-QA tool:** attackers do not need direct chat access; they embed instructions in **paper markdown, HTML, PDF-derived text, table cells, footnotes, alt text, or web pages** fetched at runtime. Retrieval and summarization blur the data/instruction boundary (Greshake et al.; NIST AI 100-2 §3.4).

---

## 2. Proposed audit criteria

Each criterion is scored on a **0–4 maturity ladder** unless marked as a **hard gate** (pass/fail). Evidence grades follow `00-FRAME.md` §6.3: **A** = multiple Tier-1 corroborating; **B** = single Tier-1 or converging Tier-2; **C** = Tier-3 only or contested; **D** = Tier-4/speculative.

### Criterion S1 — Trust-boundary inventory and data/instruction separation doctrine

| Field | Value |
|---|---|
| **Criterion** | Every LLM call path has a documented trust-boundary map: which inputs are **trusted** (system/developer prompts, fixed schemas) vs **untrusted** (paper markdown, web fetch, user query, tool-returned text, image alt text). Architecture explicitly states that LLMs **commingle data and instructions** (NIST AI 100-2 §3.1 inference-time attacks; OWASP LLM01) and that untrusted bytes must never be assumed inert. |
| **How to measure** | Review architecture/docs for a boundary diagram or table listing each prompt component and its trust class. Verify no undocumented ingestion path (e.g., silent RAG, hidden tool). Cross-check against OWASP LLM01 prevention #6 (segregate external content) and NIST AI 600-1 Information Security §2.9 (prompt injection expands attack surface). |
| **Audit method** | Conformance checklist (§5.1) + maturity model (§5.2) |
| **Scoring hook** | §6.1 dimension: security/prompt-injection; §6.2 candidate gate if any production LLM path lacks boundary classification |
| **Gaming vector** | Generic "we use an LLM" paragraph with no per-path inventory; boundary doc lists only direct user chat, omitting document/web ingestion. |
| **Anti-gaming guard** | Require enumerated paths matching actual CLI/library entry points (named in docs, not code audit here); spot-check one untrusted source (e.g., converted paper file) traced through doc to prompt assembly stage. |
| **Evidence grade** | **A** |
| **Sources** | OWASP LLM01:2025; NIST AI 100-2 E2025 §3.1, §3.4; NIST AI 600-1 §2.9 Information Security |

### Criterion S2 — Untrusted-content segregation and delimiter hardening (hard gate candidate)

| Field | Value |
|---|---|
| **Criterion** | All untrusted text entering an LLM prompt is **wrapped** with: (a) unique delimiters unlikely to appear in source, (b) **escape/normalize** of delimiter-forgery sequences in the payload, (c) explicit system-level instruction to treat delimited regions as **data never instructions**. Applies to full paper bodies, web snippets, tool outputs, and paper-controlled alt text. |
| **How to measure** | Inject corpus strings containing delimiter tokens, "IGNORE PREVIOUS INSTRUCTIONS", XML/markdown comment escapes, homoglyphs, Base64/ROT13 obfuscation (OWASP LLM01 scenarios #8–#9; NIST AI 100-2 §3.3.1 mismatched generalization). Verify escaped delimiters appear in serialized prompt and forged closers do not terminate the envelope early. |
| **Audit method** | Adversarial / red-team probing (§5.6) + conformance checklist |
| **Scoring hook** | **§6.2 hard gate**: untrusted content concatenated raw into system or user prompt without segregation/escaping fails regardless of composite score |
| **Gaming vector** | Delimiters present in docs but no escaping; wrapping only user chat not document body; decorative XML tags without forgery handling. |
| **Anti-gaming guard** | Automated tests must include **delimiter-forgery** and **instruction-in-data** cases that fail if wrapping is bypassed; tests run on document-sourced payloads not chat-only strings. |
| **Evidence grade** | **A** |
| **Sources** | OWASP LLM01:2025 mitigations #1, #6; NIST AI 100-2 E2025 §3.3.3 (XML wrapping, separate instructions from user prompts); §3.4.4 (spotlighting, filter instructions from third-party data); Greshake et al. 2023 (data/instruction blur) |

**Contradiction surfaced:** Spotlighting/delimiter defenses are widely recommended (NIST §3.4.4, OWASP LLM01) yet NIST and OWASP both state **no fool-proof prevention** exists for prompt injection given stochastic models and shared channels. **Resolution rule:** segregation is **necessary but not sufficient**; gate on presence and testability of wrapping, not on claimed immunity. Maturity level 4 requires defense-in-depth (S4–S8), not "prompt engineering alone."

### Criterion S3 — Structured output with deterministic downstream validation

| Field | Value |
|---|---|
| **Criterion** | LLM steps that influence pipeline state use **machine-parseable structured output** (JSON/schema/constrained grammar) validated in **deterministic code** before any persistence, tool call, or gate decision. Free-text LLM output is never regex-parsed into security-relevant fields. Schema violations trigger fail-closed behavior, not partial emit. |
| **How to measure** | For each LLM step: identify `output_type`/schema, validator location, retry budget, and behavior on validation failure. Inject malformed and adversarial JSON (extra fields, instruction strings in string fields, type confusion). Align with OWASP LLM01 mitigation #2 (define/validate expected output formats) and LLM05 (improper output handling). |
| **Audit method** | Conformance checklist + adversarial probing |
| **Scoring hook** | §6.1 security; §6.2 gate if any security-relevant branch consumes unvalidated LLM free text |
| **Gaming vector** | Schema exists in prompt only; Pydantic/model validation disabled on retry exhaustion; "JSON mode" without post-parse semantic checks. |
| **Anti-gaming guard** | Tests must assert **reject** on instruction-bearing string fields and on schema drift; CI fails if validator bypassed via broad `except` swallowing. |
| **Evidence grade** | **A** |
| **Sources** | OWASP LLM01:2025 mitigation #2; OWASP LLM05:2025; NIST AI 100-2 §3.3.3 (constrain generation space for guardrails) |

### Criterion S4 — Tool and plugin least privilege (excessive agency controls)

| Field | Value |
|---|---|
| **Criterion** | LLM-invokable tools are **minimized**: narrowest function set, read-only where possible, scoped to one paper/context, no open-ended shell/URL/SQL primitives. Permissions enforced in **downstream code** (complete mediation), not by LLM discretion. High-impact actions require human approval or are unavailable. |
| **How to measure** | Inventory tools/plugins; map each to OWASP LLM06 checks (minimize extensions, functionality, permissions, autonomy). Verify authorization on downstream systems independent of model output (LLM06 mitigation #7). For document QA: e.g., `read_paper` capped lines, single-PID scope, no write tools in advisory lane. |
| **Audit method** | Conformance checklist (OWASP LLM06) + observability/fault-injection overlap (§5.11) |
| **Scoring hook** | §6.2 **hard gate** if LLM can invoke write/delete/network-exfil tools without parameterized, least-privilege mediation |
| **Gaming vector** | Tools documented as read-only but implementation accepts write parameters; orphaned plugins left enabled. |
| **Anti-gaming guard** | Red-team tests attempt tool hijack via indirect injection in document body (Greshake scenario: retrieved prompt drives API call); must not reach disallowed tool or scope. |
| **Evidence grade** | **A** |
| **Sources** | OWASP LLM06:2025; OWASP LLM01:2025 mitigation #4–#5; NIST AI 100-2 §3.5 Security of Agents; Greshake et al. 2023 (tool/API hijack via IPI) |

### Criterion S5 — Zero-trust handling of LLM outputs at trust boundaries

| Field | Value |
|---|---|
| **Criterion** | All LLM outputs crossing to **deterministic core**, filesystem, DB, subprocess, or user-facing security labels are treated as **untrusted**: encoded/sanitized per target context (HTML, shell, SQL, paths), parameterized, type-checked, and never passed to `eval`/`exec`/raw SQL. Matches "treat the model as any other user" (OWASP LLM05). |
| **How to measure** | Trace each LLM output consumer; verify OWASP ASVS-style validation (LLM05 references ASVS). Attempt output carrying XSS, path traversal, SQL, markdown exfil (`![](http://attacker/...)`) per OWASP LLM01 scenario #2 and LLM05 scenarios. |
| **Audit method** | Conformance checklist + adversarial probing |
| **Scoring hook** | §6.1 security; §6.2 gate on direct passthrough of LLM output to shell/SQL/file write |
| **Gaming vector** | Sanitization only on UI path, not on debug/trace logs that operators paste elsewhere. |
| **Anti-gaming guard** | Include debug/trace artifact paths in output-handling review; test exfil payloads in structured fields. |
| **Evidence grade** | **A** |
| **Sources** | OWASP LLM05:2025; OWASP LLM01:2025 scenario #2 (hidden webpage instructions); NIST AI 600-1 MS-2.7 (security measurement/red-teaming) |

### Criterion S6 — Security-critical decisions remain non-LLM-gated (hybrid alignment)

| Field | Value |
|---|---|
| **Criterion** | **Hard gates, licensing checks, and release-blocking QA verdicts** are computed by deterministic code; LLM outputs are **advisory** and cannot single-handedly pass a security or quality gate. Aligns audit rubric with hybrid architecture: injection may corrupt advisory text but must not flip an authoritative gate. |
| **How to measure** | List all pass/fail gates; verify none consume LLM output without deterministic aggregation/threshold. Attempt indirect injection instructing "return pass/all-clear" in structured verdict fields; deterministic layer must reject or ignore non-conformant schema/values. |
| **Audit method** | Maturity model + anti-gaming / Goodhart (§5.7) |
| **Scoring hook** | §6.2 **hard gate** (mirrors frame §6.2 candidate: "LLM signal that can hard-gate"); §6.4 anti-gaming |
| **Gaming vector** | LLM "suggests" pass but developer wires suggestion directly to exit code 0; composite score includes unaudited LLM grade. |
| **Anti-gaming guard** | Gate tests include adversarial structured output; exit-code contract documented and tested independently of LLM narrative. |
| **Evidence grade** | **B** (OWASP/NIST emphasize agency/output handling; explicit "advisory-only gate" is architecture pattern inferred from LLM06 + frame, not a single OWASP bullet) |
| **Sources** | OWASP LLM06:2025; OWASP LLM01:2025; `00-FRAME.md` §6.2 hard-gate candidates; NIST AI 600-1 GOVERN 3.2 (human-AI configuration oversight) |

### Criterion S7 — Document- and web-sourced indirect injection test suite

| Field | Value |
|---|---|
| **Criterion** | A **versioned adversarial corpus** exercises indirect prompt injection through realistic document carriers: markdown headings, HTML comments, table cells, footnotes, resume-style split payloads (OWASP LLM01 #6), white-on-white / comment-hidden text, multilingual and encoded instructions (OWASP #8–#9). Tests run in CI; results report pass/fail rate by attack class, not a single score. |
| **How to measure** | Minimum corpus derived from Greshake IPI taxonomy (integrity, availability, privacy subclasses) and OWASP LLM01 scenarios #2–#4, #6–#7. Execute black-box probes (NIST §3.6: Garak, AgentDojo-style) against staging endpoints. Track regression when prompts/models change. NIST AI 600-1 MS-2.7-007 mandates red-teaming for prompt injection. |
| **Audit method** | Adversarial / red-team probing (§5.6) + reproducibility replay (§5.8) for regression |
| **Scoring hook** | §6.1 security; §6.4 anti-gaming (corpus must evolve; holdout cases); feeds §6.6 uncertainty if coverage gaps remain |
| **Gaming vector** | Chat-only jailbreak tests while production ingests documents; static corpus never updated; tests assert "no crash" instead of "no policy violation / no tool hijack." |
| **Anti-gaming guard** | Require **document-embedded** cases ≥60% of injection tests; include canary instructions that must **not** change deterministic gate outcomes; periodic rotation of holdout attacks (P19 coordination). |
| **Evidence grade** | **A** |
| **Sources** | OWASP LLM01:2025 scenarios + mitigation #7; Greshake et al. 2023; NIST AI 600-1 MS-2.7-007; NIST AI 100-2 §3.6 (AgentDojo, Garak benchmarks); promptfoo LLM red teaming docs |

### Criterion S8 — Assume-breach defense-in-depth and impossibility disclosure

| Field | Value |
|---|---|
| **Criterion** | Public docs state that **prompt injection cannot be fully eliminated** (OWASP LLM01; NIST §3.4.4) and describe layered controls: segregation, schema validation, least-privilege tools, output sanitization, monitoring, human review for high risk. Design assumes untrusted sources may control **advisory** LLM behavior but not authoritative state. |
| **How to measure** | Documentation includes limitations section citing residual risk; architecture uses privilege-separated components where feasible (NIST §3.4.4: multiple LLMs with different permissions, well-defined interfaces). Operator guidance for incident response when injection suspected. |
| **Audit method** | Documentation-completeness audit (§5.9) + maturity model |
| **Scoring hook** | §6.1 security; §6.3 evidence grade for injection claims capped at B without S7 test evidence |
| **Gaming vector** | Marketing "injection-proof" claims; silent omission of indirect injection in threat model. |
| **Anti-gaming guard** | Doc review checklist item: must cite OWASP/NIST impossibility posture; claims of "full protection" auto-fail criterion. |
| **Evidence grade** | **A** |
| **Sources** | OWASP LLM01:2025 ("unclear if fool-proof methods"); NIST AI 100-2 §3.4.4, §4.1.2; NIST AI 600-1 GOVERN 4.1 / MEASURE 1.3 (structured red-teaming disclosure) |

### Criterion S9 — Web-fetch and retrieval hardening

| Field | Value |
|---|---|
| **Criterion** | Web-sourced text (if any) passes the **same** untrusted wrapping as local documents; retrieval limits (domain allowlist, size caps, timeout); no automatic execution of retrieved instructions. RAG/retrieval paths labeled untrusted in S1 map. |
| **How to measure** | If web tools absent, mark N/A with evidence. If present: test attacker-controlled URL/page content influencing tool calls or verdicts (OWASP LLM01 #2, #4; LLM08 vector weakness awareness for embedding stores). |
| **Audit method** | Conformance checklist + adversarial probing |
| **Scoring hook** | §6.1 security |
| **Gaming vector** | Web fetch bypasses wrap_source; only HTML stripped, scripts/instructions remain. |
| **Anti-gaming guard** | Fetch-harness tests with malicious pages; compare handling to local document corpus (S7). |
| **Evidence grade** | **B** |
| **Sources** | OWASP LLM01:2025; OWASP LLM08:2025 (vector/embedding weaknesses); Greshake et al. 2023 (passive SEO/web injection) |

### Criterion S10 — Monitoring, traceability, and injection incident evidence

| Field | Value |
|---|---|
| **Criterion** | Full-fidelity debug/trace captures **serialized prompts** (including delimited untrusted envelopes) and structured LLM I/O for post-incident analysis, without exposing secrets to untrusted consumers. Enables replay of injection attempts (NIST monitoring; OWASP LLM05 logging). |
| **How to measure** | Verify trace/debug separation (concise vs full I/O) per observability persona boundary; confirm injection regression tests archive reproducer payloads. |
| **Audit method** | Observability / fault-injection audit (§5.11) |
| **Scoring hook** | §6.1 security + observability cross-dimension; §6.3 evidence for injection findings |
| **Gaming vector** | Trace omits untrusted payload, preventing forensics; logs leak paper content to shared systems (P24 boundary). |
| **Anti-gaming guard** | Red-team exercise must produce a trace sufficient to diagnose which envelope failed; retention policy documented. |
| **Evidence grade** | **B** |
| **Sources** | OWASP LLM05:2025 (monitoring); NIST AI 600-1 MS-2.7; NIST AI 100-2 §3.3.3 (monitoring and response) |

---

## 3. External benchmark / exemplar bar

### Tier-1 synthesis: what "good" looks like for document+LLM pipelines

| Control layer | OWASP LLM Top 10 2025 | NIST AI 100-2 E2025 | NIST AI 600-1 GenAI Profile | Research baseline |
|---|---|---|---|---|
| Acknowledge data/instruction confusion | LLM01 root cause | §3.1 inference-time; §3.4 IPI | §2.9 Information Security | Greshake IPI taxonomy |
| Segregate untrusted content | LLM01 #6 | §3.3.3 wrapping; §3.4.4 spotlighting | — | Passive injection via documents/web |
| Validate structured outputs | LLM01 #2; LLM05 | Constrain generation space | — | — |
| Least-privilege tools | LLM06 | §3.5 Agents | GOVERN 3.2 oversight | Tool hijack demos |
| Test before deploy | LLM01 #7 | §3.6 benchmarks; §3.3.3 eval | MS-2.7-007 red-team | AgentDojo, Garak, promptfoo |
| Assume breach | LLM01 (no fool-proof fix) | §3.4.4 | MS-2.7 measurement | — |

**Professional bar (synthesis-level):** A document-QA pipeline with an LLM lane meets **OWASP LLM01+LLM05+LLM06 conformance** as floor, **NIST AI 100-2 indirect-injection mitigations** as design target, and **NIST AI 600-1 red-teaming** (MS-2.7-007) as operational proof. **Level 4 maturity** requires S7 CI corpus with document-embedded attacks, hard gates S2/S4/S6 enforced, and S8 honest impossibility disclosure.

**Where exemplars diverge (do not cargo-cult):** Consumer chatbots (Bing/Bard) prioritize UX over deterministic QA; their mitigations (RLHF, filters) do not satisfy **fail-closed fidelity** for WG21 QA. Agent frameworks (LangChain chains) illustrate **anti-patterns** (LLM output driving shell/SQL) per industry red-team disclosures. A QA tool should adopt **segregation + schema + least privilege**, not "more safety prompts alone."

**Strongest single criterion for this threat model:** **S2 (untrusted-content segregation and delimiter hardening)** — indirect injection via document bodies is the dominant attack class for paper pipelines (Greshake; NIST NISTAML.015; OWASP LLM01 indirect scenarios), and every other control assumes wrapped bytes at the trust boundary.

---

## 4. Recommended weight & gate recommendation

| Recommendation | Rationale |
|---|---|
| **Dimension weight: 10%** of composite (within security/privacy/supply-chain cluster shared with P03, P24) | Security is necessary for defensible QA when LLMs process untrusted WG21 text, but this package's primary claim is deterministic extraction quality; weight follows frame §6.1 candidate dimensions without exceeding architecture/eval dominance. |
| **Hard gates (conjunctive): S2, S4, S6** | **S2:** Raw untrusted document/web text in prompts is the OWASP LLM01 / NIST IPI failure mode. **S4:** Excessive agency is how injection escalates to exfil/RCE (LLM06; Greshake). **S6:** Matches frame §6.2 explicit candidate gate on LLM hard-gating. |
| **Soft gates (cap dimension at level 2): S7, S3** if either fails | Missing injection test corpus or unvalidated structured output caps security maturity until remediated, but monorepo-internal advisory-only experiments may temporarily score lower (synthesis records mode). |
| **Evidence propagation** | Dimension inherits weakest grade among S2, S4, S6, S7 load-bearing criteria; impossibility claims without S7 tests capped at **C** per §6.3. |
| **Contested criteria discount** | Delimiter-only defenses vs dual-LLM privilege separation (NIST §3.4.4): on equal Tier, prefer **tested** control (S7) over architectural novelty; mark untested dual-LLM patterns **contested** per §6.5. |

---

## 5. Sources

### Tier 1 — Authoritative / primary

| ID | Source | URL | Date/version |
|---|---|---|---|
| S1 | OWASP LLM01:2025 Prompt Injection | https://genai.owasp.org/llmrisk/llm01-prompt-injection/ | 2025 (Top 10 v2.0, Mar 2025) |
| S2 | OWASP LLM05:2025 Improper Output Handling | https://genai.owasp.org/llmrisk/llm052025-improper-output-handling/ | 2025 |
| S3 | OWASP LLM06:2025 Excessive Agency | https://genai.owasp.org/llmrisk/llm062025-excessive-agency/ | 2025 |
| S4 | NIST AI Risk Management Framework 1.0 | https://www.nist.gov/itl/ai-risk-management-framework | 2023-01-26 |
| S5 | NIST AI 600-1 Generative AI Profile | https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf | 2024-07-26 |
| S6 | NIST AI 100-2 E2025 Adversarial ML Taxonomy | https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.100-2e2025.pdf | 2025-03 (doi:10.6028/NIST.AI.100-2e2025) |
| S7 | Greshake et al., Indirect Prompt Injection | https://arxiv.org/abs/2302.12173 | 2023 (ACM CCS; arXiv v3) |

### Tier 2 — Strong secondary

| ID | Source | URL | Date/version |
|---|---|---|---|
| S8 | OWASP GenAI LLM Top 10 index (2025 edition) | https://genai.owasp.org/llm-top-10/ | 2025 |
| S9 | promptfoo — LLM red teaming guide | https://www.promptfoo.dev/docs/red-team/ | 2025–2026 docs |
| S10 | NIST CSRC AI 100-2 E2025 publication record | https://csrc.nist.gov/pubs/ai/100/2/e2025/final | 2025-03 |

### Tier 3 — Contextual (corroboration only)

| ID | Source | URL |
|---|---|---|
| S11 | NVIDIA blog: Securing LLM Systems Against Prompt Injection | https://developer.nvidia.com/blog/securing-llm-systems-against-prompt-injection/ |

**Source count:** 7 Tier-1 + 3 Tier-2 = **10 distinct Tier 1–2 sources** (floor ≥3 satisfied).

**Contradictions surfaced:**
- **Prevention vs impossibility:** OWASP/NIST recommend delimiter segregation and output validation, yet OWASP LLM01 states fool-proof prevention is unclear and NIST §3.4.4 states mitigations do not offer full protection. **Resolution:** gates require **controls + tests**, not immunity claims.
- **LLM-based detectors:** NIST §3.3.3 lists LLM judges for harmful input detection, but notes correlated failures with the primary model. **Resolution:** detectors are **supplemental** only; never sole gate (align S6).

---

## 6. Overlap statement

This persona researched **external prompt-injection security standards and test methods only**. It did **not** open whisker production code, cite whisker `file:line`, score whisker, clone/fork/copy code, or duplicate:

- **`llm-stack/`** — prior code-level audit of tapetum injection defense, cascade, and isolation (HIGH overlap risk). This persona supplies the **external rubric** that a later stage applies; it does not re-derive tapetum findings.
- **`p24-privacy-data-governance.md`** — privacy/retention/governance (distinct boundary; cross-reference only for trace/log sensitivity).
- **`p18-adversarial-methodology.md`** — extraction-QA content corruption attacks (complementary; P23 focuses on **LLM trust-boundary** security, not metric evasion).
- **`p05-hybrid-architecture.md`** — advisory vs authoritative lane pattern (P23 cites S6 gate alignment only).

Boundary held: **security criteria + external bar + hard-gate recommendations** for prompt-injection defense, handed to synthesis as rubric inputs for the security dimension.
