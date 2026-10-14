# Meta-Reviewer B — Hybrid Architecture, Determinism, Boundaries, Security, Failure, Sovereignty

**Reviewer:** Meta-Reviewer B (Opus)
**Date:** 2026-07-18
**Inputs:** `00-FRAME.md`, `00-ROSTER.md`, `p01`–`p30`.
**Mandate:** Cross-cut the swarm on hybrid deterministic-core + advisory-LLM architecture, determinism/reproducibility tiers, the user/Sean reconciliation method, package boundaries, injection/security, failure behavior, and model sovereignty. Re-verify load-bearing claims against primary sources and live web. Surface incompatible recommendations, leaky authority boundaries, cargo-cult patterns, unsupported hard gates, duplicate criteria, and remaining unknowns.
**Constraint honored:** No whisker production code was opened, cited (`file:line`), or scored. This is a review of the *audit design*, not of whisker.

---

## 0. Executive summary

The swarm's spine is sound: a strict deterministic core, an advisory LLM lane that can never gate, demote-only ratchets, fail-not-partial, and self-hosted model sovereignty. Those five load-bearing claims are corroborated by primary sources (Thinking Machines batch-invariance paper; OWASP LLM01:2025; NIST AI RMF; PyPA/OpenSSF; ISO/IEC 25010) and are internally consistent across `p05`, `p06`, `p07`, `p23`, `p25`.

The **weaknesses are not in the doctrine but in its operationalization**: (a) the single most important reconciliation input, the *concrete definition of "user determinism" vs "Sean determinism,"* is undefined and must stay undefined until the humans supply it; (b) several personas propose the *same* hard gate under different names (duplicate gates); (c) a handful of gates are stated as hard/pass-fail without the labeled data that would make them defensible (unsupported-at-Stage-0 gates); (d) two genuine cross-persona *contradictions* exist (lazy-import exemplars vs whisker invariant; check-mode exit-code semantics vs "0=success"). None are fatal; all are fixable before the rubric is frozen.

---

## 1. Verified claims (primary-source re-checked)

| # | Claim (as stated by swarm) | Verdict | Primary source | Confidence |
|---|---|---|---|---|
| V1 | Bit-exact LLM reproducibility on shared/hosted endpoints is not achievable without batch-invariant kernels; run-to-run nondeterminism is driven primarily by **server-load-dependent batch size**, not floating-point non-associativity alone. `p06`/`p07` tier taxonomy (T0 bit-exact only under kernel control; hosted → quality-stable) is correct. | **VERIFIED** | Thinking Machines Lab, *Defeating Nondeterminism in LLM Inference* (2025-09); `batch_invariant_ops` (RMSNorm/matmul/attention fixed reduction order). Matches `CLAUDE.md` determinism note. | High |
| V2 | Prompt injection has **no fool-proof prevention**; mitigation is defense-in-depth: constrain behavior, **structured output + deterministic validation**, I/O filtering, **least privilege (handle tools in code, not model)**, human-in-loop for high-risk, **segregate/identify untrusted content**. A guardrail LLM is itself injectable. `p23` criteria map 1:1. | **VERIFIED** | OWASP LLM01:2025 (genai.owasp.org + Top-10 v2025 PDF); OWASP LLM Prompt Injection Prevention Cheat Sheet (StruQ, dual-LLM). | High |
| V3 | Security-critical / release-gating decisions must **not** be hard-gated by an LLM signal; LLM output is untrusted data. `p05`, `p10`, `p23`, `p30`(E11) converge. | **VERIFIED** | OWASP LLM01 (least privilege, deterministic validation); zero-trust of model output is the cheat-sheet's core. | High |
| V4 | Model sovereignty: production analytical pipelines should run on **self-hosted open-weight** models; cloud SDKs stay optional. Cargo-culting LangExtract (`google-genai` in core) / Marker (cloud LLM defaults) is wrong. `p24`, `p26`, `p27`, `p28`, `p29` converge. | **VERIFIED** | LangExtract `pyproject.toml` v1.6.0 bundles Gemini client in core (negative exemplar, `p26`); NIST AI RMF (Govern/Map data-flow control) supports self-hosting rationale. | High |
| V5 | Composite scores must never be reported alone; per-axis decomposition + conjunctive hard gates is the eval-framework consensus. `p09`, `p12`, `p14`, `p15`, `p19`, `p27`, `p28`, `p29`, `p30` converge. | **VERIFIED** | Great Expectations Checkpoint (`success` conjunctive + `severity`); promptfoo named metrics; DeepEval `assert_test`; Giskard grade gate; Nougat/olmOCR per-modality tables. | High |
| V6 | Edit distance / string similarity is construct-invalid for math and table-structure fidelity; binary/unit tests and structure-aware metrics (TEDS/GriTS, grid+role diffs) are required. `p09`, `p13`, `p27`, `p28` converge. | **VERIFIED** | olmOCR-Bench (rejects edit distance/ROUGE/LLM-judge for primary scoring; `x^i` vs `x_i` = 1 char); Docling `verify_table_v2` grid+role assertions. | High |
| V7 | Package boundaries: acyclic deps, one-way core→optional, public-API-only consumption, CI-enforced import-linter. `p08` matches repo invariants. | **VERIFIED** | PyPA packaging guidance; import-linter as used by LangExtract (core↔provider forbidden). Matches `CLAUDE.md` invariants. | High |

---

## 2. Rejected / down-graded claims

| # | Claim | Verdict | Reason | Confidence |
|---|---|---|---|---|
| R1 | (ROSTER search-lead) "unstructured license change" as a BSL/SSPL relicensing event, transferable as a licensing cautionary tale. | **REJECTED (factually wrong premise)** | `p29` correctly re-checked: core `unstructured` + `unstructured-api` remain **Apache-2.0**; the shift is product-tier (OSS vs Platform SaaS), not a license swap. Keep only the *boundary-transparency* lesson, discard the relicensing framing. | High |
| R2 | LangExtract packaging as a positive exemplar to match ("PyPA-modern, typed, extras"). | **DOWN-GRADED to split verdict** | Pattern (extras + entry-point providers) is good; the *dependency graph* (cloud SDK in core, Gemini API-key quick-start) is a **negative** exemplar under sovereignty. `p26` flags this; must not be cited as an unqualified positive. | High |
| R3 | Fail-soft chunk parsing (`suppress_parse_errors=True`) and multi-pass stochastic recall as adoptable engineering. | **REJECTED for gate paths** | `p26`, `p27`, `p28` agree: fail-soft is the opposite of whisker fidelity; acceptable only as non-gating telemetry. Correctly labeled a negative exemplar. | High |
| R4 | LLM-as-judge (Ragas/DeepEval/TruLens defaults) as a CI gate. | **REJECTED as gate** | `p10`, `p28`, `p30`(E11) agree: judge scores self-prefer and drift; advisory / tie-break only unless P10-validated with chance-corrected human agreement. Transfer structure (score+reason+threshold), not authority. | High |
| R5 | OpenSSF silver badge / LF-style TSC governance as a whisker gate. | **DOWN-GRADED to informational** | `p27` itself scales this down: whisker is a single C++ Alliance package, not LF-hosted. Full TSC machinery is cargo-cult at this scale; "named maintainers + CONTRIBUTING + release notes" is the right bar. | Medium |

---

## 3. Reconciled doctrine (the parts that must hold)

These are the invariants the rubric should encode, phrased to survive the unresolved user/Sean question.

1. **Epistemic separation is the master invariant.** The deterministic core produces the authoritative verdict; the advisory LLM lane produces commentary. The lane is *opt-in*, has *zero default agency*, and its failure/absence must not change the core verdict. (`p05`, `p07`, `p23`, verified V2/V3.)
2. **Demote-only ratchet.** Advisory signals may only *lower* confidence or *raise* a flag for human review; they may never promote a failing artifact to pass. Any promotion path from the LLM lane is a hard-gate violation. (`p05`.)
3. **Fail-not-partial on fidelity-critical paths.** If the core cannot achieve full fidelity, it fails the paper with a clear error and preserves the debug transcript; it never emits a partial result mistakable for a complete one. Advisory-lane failure degrades gracefully to "advisory unavailable," never to a partial verdict. (`p25`, `CLAUDE.md` fidelity.)
4. **Determinism is tiered and honestly labeled, not binary.** Declare T0–T3 per output. The *core* verdict must be reproducible at the tier it claims (replay suite). The *advisory* lane may sit at a lower tier (quality-stable at best on hosted models) and must be labeled as such. Bit-exact claims are only defensible under batch-invariant kernel control (V1). (`p06`, `p07`.)
5. **Layered determinism contract with non-leakage.** The two doctrines are combined via a *named, versioned, layered contract* where the advisory layer's weaker guarantee cannot leak into the core's stronger guarantee. This is the reconciliation *mechanism*; the reconciliation *content* (what each layer must guarantee) awaits the user/Sean definitions. (`p07`.)
6. **Untrusted-data envelope is mandatory.** All paper/web text enters LLM prompts wrapped and delimiter-hardened; structured output with deterministic validation; least privilege for any tool; no security decision gated by the model. (`p23`, verified V2.)
7. **Model sovereignty by default.** Cloud SDKs are optional extras; the core install is self-host-capable; a maintained first-party self-hosted serving path outranks community plugin listings. (`p24`, `p26`, `p28`, `p29`, verified V4.)

### 3a. PRESERVED UNKNOWN — user vs Sean determinism (do not resolve)

> The **concrete definitions** of "user determinism" and "Sean determinism" are **unresolved and must remain so** until the two humans supply them. `p07` is explicit that these are placeholders. This meta-review supplies only the *reconciliation scaffolding* (layered contract + non-leakage + per-layer tier honesty). It deliberately does **not** invent: (i) which layer each person owns, (ii) the tier each demands (bit-exact vs quality-stable vs stated-precision), (iii) the tolerance envelope, or (iv) the transitional dual-truth window. Any rubric that hard-codes these before the humans decide is inventing architecture. **Flag any downstream synthesis that fills this gap.**

---

## 4. Audit tests (repeatable, Stage-0-defined)

Tests the rubric can define now without whisker code. Each is deterministic and gaming-resistant.

| ID | Test | Method | What it proves |
|---|---|---|---|
| T1 | **LLM-gating probe.** Force the advisory lane to emit a "pass" on an artifact the core fails, and a "fail" on one the core passes. Verdict must equal the core in both. | Fault injection / conformance | Non-leakage + demote-only (doctrine 1,2). |
| T2 | **Advisory-outage probe.** Kill the LLM backend mid-run. Core verdict must be identical to backend-present run; output labels "advisory unavailable," not partial. | Fault injection | Fail-not-partial + opt-in lane (doctrine 3). |
| T3 | **Core replay.** Run the deterministic core twice on the same input in the environment it claims T0/T1 for; assert the claimed tier (bit-exact or quality-stable) holds. | Reproducibility replay | Tier honesty (doctrine 4, V1). |
| T4 | **Import-graph acyclicity + core→optional direction.** Static import-linter contract in CI. | Conformance | Boundaries (V7). |
| T5 | **Untrusted-envelope check.** Inject forged delimiters / instruction text in paper + web content; assert it is wrapped and does not alter structured-output schema or verdict. | Adversarial / indirect injection | Injection defense (doctrine 6, V2). |
| T6 | **Zero-authoring baseline on 100% of pages** (non-empty, anti-repetition >N-gram, domain-calibrated charset). Must run before any labeled eval. | Conformance + anti-Goodhart | Catastrophic-failure floor (`p28` B1/B2). |
| T7 | **Per-axis decomposition + conjunctive gate.** Construct a case where composite ≥ pass band but one hard gate fails; overall verdict must be fail. | Anti-Goodhart stress | Non-compensability (V5, `p30` E4). |
| T8 | **Exit-code / stream contract.** stdout = machine result, stderr = progress; ≥3 distinct documented exit paths; `--json` parses without preprocessing. | Conformance | Operator trust surface (`p21` U1/U2). |

---

## 5. Hard gates (recommended, with support status)

**Supported now (Stage 0, no labels needed):**

- **G1 — No LLM hard-gating.** Any release/security/verdict decision gated by an LLM signal = fail. (V2/V3; `p05`,`p10`,`p23`,`p30`.)
- **G2 — Demote-only.** Any advisory→promote path = fail. (`p05`.)
- **G3 — Fail-not-partial on fidelity-critical paths.** Partial result mistakable for complete = fail. (`p25`,`CLAUDE.md`.)
- **G4 — Non-leakage / layered contract present.** No named+versioned layered determinism contract, or advisory tier leaks into core tier = fail. (`p07`.) *Content of the contract stays open per §3a.*
- **G5 — Untrusted content wrapped.** Raw untrusted paper/web text into an LLM prompt without the envelope = fail. (`p23`, V2.)
- **G6 — Boundaries.** Import cycle, or core depends on optional/LLM/cloud package, or import-linter CI absent = fail. (`p08`, V7.)
- **G7 — Excessive agency.** Advisory lane holds write/tool privileges beyond least-privilege = fail. (`p23`, V2.)
- **G8 — Composite-only reporting.** Any gate verdict reported as a lone number without per-axis table = fail. (V5.)

**Conditional / calibration-pending (must NOT be frozen as hard until labels exist — per `p16`,`p17`):**

- **C1 — Comprehension floor** (closed-book QA below operating point). Sound method (`p13`,`p28`) but the threshold needs a calibrated WG21 corpus; hard-gating an *uncalibrated* threshold is itself a §6.2 violation.
- **C2 — Table-fidelity gate** (paired TEDS + TEDS-S / grid diff). Method verified (V6); operating point pending calibration.
- **C3 — Mutation kill-rate floor on gate modules** (`p04`). Strongly recommended, not a Stage-0 hard gate.

---

## 6. Incompatible recommendations (genuine contradictions to resolve)

| # | Conflict | Sources | Resolution |
|---|---|---|---|
| X1 | **Lazy imports.** Docling exemplar praises lazy optional-dep imports (`p27`); whisker/`CLAUDE.md` invariant forbids lazy imports in production packages. | `p27` vs repo invariant | Repo invariant wins: optional deps live behind extras with import-graph tests, **not** function-level lazy imports. Do not cargo-cult Docling here. |
| X2 | **Exit-code semantics.** "0 = success, non-zero = failure" (clig.dev) vs check/lint mode where "found issues" = exit 1 by design (ruff/eslint). | `p21` U1 (self-surfaced) | Document **two success classes**: operational-success-with-findings (non-zero by CI design) vs operational-failure (higher codes). Already resolved inside `p21`; ensure synthesis carries it. |
| X3 | **Gate authority of LLM-judge frameworks.** Ragas/DeepEval/TruLens gate on judge scores by default; whisker doctrine forbids it. | `p30` E11 vs frameworks | Advisory-only unless P10-validated. Transfer score+reason+threshold *structure*, never gate authority. |
| X4 | **"Ground truth" language.** Several personas lean on "ground truth"; `p11` insists on imperfect-oracle honesty (label status ladder, IAA). | `p11` vs loose usage elsewhere | Adopt `p11`'s honesty: no absolute "ground truth" claim without adjudication + IAA; call it "reference/gold with provenance." |

---

## 7. Leaky authority boundaries (watch-list)

1. **Alt-text / image captions.** `CLAUDE.md` notes alt text is paper-controlled; if a future vision/caption path sends it to an LLM *outside* the `wrap_source` envelope, the untrusted-data guarantee leaks. (`p23` echoes.) Keep as an explicit invariant.
2. **Debug/trace artifacts as an exfil / retention channel.** `p24` (privacy) + `p25` (observability) intersect: full-fidelity debug logs may contain untrusted content and PII; indefinite retention is a governance leak. Gate retention, not just content.
3. **Advisory "confidence" bleeding into composite weight.** `p10`/`p30` warn uncalibrated LLM confidence must not silently drive automation; ensure the composite treats it as capped/advisory, not a real axis.
4. **Documentation drift as a gating channel.** `p20` G-DOC-2: if the deterministic/advisory boundary is only defined in prose that drifts, the boundary becomes unauditable and can effectively let the LLM gate by omission. Boundary must be greppable + tested, not documented-only.

---

## 8. Duplicate / overlapping criteria (consolidate before freezing)

| Theme | Personas asserting a near-identical gate/criterion | Action |
|---|---|---|
| "No single composite number; per-axis mandatory" | `p09`, `p12`, `p14`, `p15`, `p19`, `p27`(D27-02), `p28`(A2), `p29`(B1), `p30`(E1) | Collapse to **one** rubric-level rule (V5/G8); cite personas as evidence, don't create 9 gates. |
| "LLM signal must not hard-gate" | `p05`, `p10`, `p23`, `p26`, `p28`, `p30`(E11) | One gate (G1); others are corroboration. |
| "Fail-not-partial / fail-closed" | `p05`, `p06`, `p07`, `p25`, `p26`(2.9 neg), `p27` | One gate (G3). |
| "Untrusted input segregation / envelope" | `p23`, `p26`(2.11), `p29`(implicit) | One gate (G5). |
| "Explicit calibrated thresholds, no borrowed defaults" | `p16`, `p30`(E3) | One method rule; `p16` owns the protocol, `p30` is exemplar evidence. |
| "Per-modality metric + limitation prose" | `p09`, `p27`, `p28`, `p29`(B1/B2) | One eval-science criterion; case studies are evidence tiers. |

Net: the roster has **more criteria than distinct gates**. Synthesis should map ~8 hard gates (§5) and let the 30 personas serve as evidence weight behind them, or the rubric will double-count and inflate.

---

## 9. Cargo-cult patterns to reject (verified negatives)

- **google-genai/Gemini-in-core (LangExtract), cloud-LLM defaults (Marker):** violate sovereignty (V4). Port extras/entry-point *pattern* only.
- **HTML animated review widget (LangExtract), MkDocs/make targets (Docling), pnpm harness (firecrawl):** tool-stack specifics, not transferable; port the *provenance-linked review* concept, not the widget.
- **English-centric charset baseline (olmOCR CJK/emoji exclusion):** WG21 papers carry legitimate Unicode math; whisker needs domain-calibrated charset rules (`p28`).
- **~weekly release velocity (Docling ~195 releases), full LF/TSC governance, OpenSSF silver:** hygiene ≠ frequency; scale to a single-package project (`p27`, R5).
- **Fail-soft / multi-pass stochastic recall as engineering to copy:** negative exemplar for gates (R3).

---

## 10. Remaining unknowns (explicit)

1. **User vs Sean determinism definitions** — the top unknown; must stay open (§3a).
2. **Calibrated operating points** for comprehension (C1), table fidelity (C2), and any numeric gate — cannot be set without a labeled WG21 corpus and `p16` calibration; Stage-0 rubric can only define the *method*, not the *threshold*.
3. **Advisory-lane determinism tier on self-hosted models** — even self-hosted vLLM is only quality-stable, not bit-exact, without batch-invariant kernels (V1); whether whisker targets kernel-level determinism for any core-adjacent LLM use is undecided.
4. **Retention/governance policy** for full-fidelity debug artifacts (`p24`) — proportionate window undefined.
5. **Which self-hosted serving topology** whisker commits to (server/client split, concurrency ceiling) — `p28`/`p29` supply the bar; the choice is open.
6. **Weight vector** across dimensions — personas give cluster-local suggestions (doc ~8–12%, scoring ~18%, etc.) that sum inconsistently; final weights need cross-persona sensitivity analysis (`p15`,`p17`), not addition of local guesses.

---

## 11. Confidence

| Area | Confidence | Basis |
|---|---|---|
| Determinism tier doctrine (V1, doctrine 4/5) | **High** | Primary source re-verified (Thinking Machines). |
| Injection/security doctrine (V2/V3, G1/G5/G7) | **High** | OWASP LLM01:2025 + cheat sheet re-verified. |
| Hybrid separation + demote-only + fail-not-partial (G1–G3) | **High** | Convergent across `p05`/`p07`/`p25` + verified sources. |
| Model sovereignty (V4, doctrine 7) | **High** | LangExtract core-dep negative exemplar confirmed; NIST AI RMF supports. |
| Boundaries (V7, G6) | **High** | PyPA + import-linter precedent + repo invariant. |
| Duplicate-gate consolidation (§8) | **High** | Direct textual overlap across personas. |
| Contradictions (§6) | **High** | Both surfaced by the personas themselves. |
| Calibration-pending gates staying conditional (§5 C1–C3) | **Medium-High** | Depends on labels not yet present; method is sound. |
| Weight vector / final composite shape | **Low-Medium** | Requires cross-persona sensitivity analysis not yet run. |
| User/Sean reconciliation content | **N/A (intentionally unresolved)** | Preserved as unknown per mandate. |
