# Meta-Review C — Engineering-Quality Rubric (Package/Release, API, Supply-Chain, CI/Test, Modularity, Docs, CLI, Observability, Privacy, Repo Practices)

**Role:** Meta-Reviewer C (Opus synthesis, engineering-quality cluster).
**Date:** 2026-07-18.
**Inputs consumed:** `00-FRAME.md`, `00-ROSTER.md`, and persona reports **P01, P02, P03, P04, P08, P20, P21, P24, P25** (primary) plus case studies **P26 (LangExtract), P27 (Docling), P28 (olmOCR/Marker/MinerU), P29 (unstructured/Nougat/Surya), P30 (eval frameworks)** for transferable repo practices.
**Scope of THIS document:** consolidate the engineering-quality criteria into a deduplicated, defensible rubric slice. **No whisker production-code inspection, no whisker `file:line`, no whisker verdict or score.** I produce criteria, hard gates, a maturity ladder, and confidence grades for a later stage to apply.

The engineering-quality cluster answers one sub-question of the FRAME objective: *Is whisker a professional, releasable, well-documented, observable, boundary-clean Python package by external standards, and where must it improve?* Eval-science, determinism, adversarial/anti-gaming, scoring-calibration, security-injection, and provenance/licensing depth are owned by other meta-reviewers; I cite them only at boundaries.

---

## 1. Method

1. Read all ten cluster reports plus five case studies end-to-end.
2. **Source verification** (FRAME §4 duty): live-checked a representative cross-section of load-bearing Tier-1/Tier-2 URLs (§2 below).
3. **Deduplication:** collapsed ~110 persona sub-criteria into **30 unique engineering-quality criteria** (§4), recording which personas feed each.
4. **Classification** per criterion: *universal professional bar* vs *project-specific choice*; *objective-executable* (mechanically checkable by a script) vs *judgment-based*.
5. **Rejection/downgrade** of tool-prescriptive, arbitrary-threshold, or unjustified requirements (§5).
6. **Hard gates** (§6), **maturity ladder** (§7), **weights** (§8), **confidence + flip conditions** (§9).

---

## 2. Primary-source verification

I HEAD-checked 28 URLs spanning every criterion family, chosen to include (a) the most load-bearing standards and (b) the sources most at risk of fabrication (future-dated 2026 releases / unusual arXiv IDs). **All returned HTTP 200.**

| Source | Status | Persona(s) relying |
|---|---|---|
| PEP 639 (license clarity) | 200 | P01 |
| PEP 561 (typed distribution) | 200 | P02 |
| PEP 794 (import-names, Oct 2025) | 200 | P01 |
| clig.dev (CLI guidelines) | 200 | P21 |
| NIST SP 800-218 SSDF | 200 | P03 |
| SLSA v1.1 levels | 200 | P03 |
| OpenTelemetry Logs Data Model | 200 | P25 |
| Diátaxis start-here | 200 | P20 |
| agents.md | 200 | P20 |
| OpenAI Codex AGENTS.md guide | 200 | P20 |
| Import Linter — layers contract | 200 | P08 |
| OWASP RAG Security Cheat Sheet | 200 | P25 |
| NIST AI RMF | 200 | P24 |
| Great Expectations GX overview | 200 | P30 |
| Keep a Changelog 1.1.0 | 200 | P01 |
| OpenSSF Scorecard checks.md | 200 | P03 |
| PyPA pylock.toml spec | 200 | P03 |
| Astral `uv audit` blog | 200 | P03 |
| ISO/IEC 27701:2025 | 200 | P24 |
| github.com/google/langextract | 200 | P26 |
| PyPI langextract 1.6.0 (2026-07-02) | 200 | P26 |
| docling docs site | 200 | P27 |
| docling release v2.113.0 (2026-07-14) | 200 | P27 |
| arXiv 2502.18443 (olmOCR) | 200 | P28 |
| arXiv 2510.19817 (olmOCR 2) | 200 | P28 |
| arXiv 2604.04771 (MinerU2.5-Pro) | 200 | P28 |
| surya release v0.20.0 (2026-05-27) | 200 | P29 |

**Verification note (honest caveat):** a 200 on the landing URL confirms the resource exists; it does **not** independently confirm that each cited *claim inside* the source (e.g., "olmOCR-Bench = 7,010 tests", "docling ~195 releases") is accurate. Those content-level claims are graded, not re-derived; the later stage that turns this rubric into a verdict should spot-verify any claim it makes load-bearing. arXiv `2604.04771` (April 2026) is recent relative to the frame's "today" and resolved on both `abs/` and `html/` forms; treated as live but flagged as the single lowest-corroboration citation in the cluster.

Sampling, not exhaustion: I verified a representative subset, not all ~150 cited URLs. Confidence in link-liveness is **high** for the standards backbone (PEP/NIST/OWASP/OTel/clig.dev/PyPA), **medium** for very recent vendor release tags.

---

## 3. Deduplication map (110 persona sub-criteria → 30 unique)

The personas overlap heavily. The most-duplicated ideas, and where they collapse:

| Recurring idea | Personas that raised it | Collapsed into |
|---|---|---|
| Heavy/LLM deps belong in optional extras; core stays lean | P01 R10, P03 C7, P08 2.5, P26 2.6, P29 A2 | **EQ-09** |
| Typed, enumerated public API (`__all__` + `py.typed`) | P02 2.1/2.2, P08 2.4, P27 D27-01, P29 A1 | **EQ-05** |
| Stable/typed return shapes, not `dict[str,Any]` | P02 2.6, P27 D27-01, P29 A1 | **EQ-07** |
| Per-axis reporting; never a single composite number as gate | P27 D27-02, P28 A2/C3, P29 B1, P30 E1/E6 | **EQ-28** |
| Exit-code contract as public API | P21 U1, P20 C03/C09, P04 T9 | **EQ-22** |
| stdout=result / stderr=progress; no `print()` in library | P21 U2/U3, P25 O1 | **EQ-18 / EQ-23** |
| Must-fail canary / metamorphic tests ("gate teeth") | P04 T6/T9, P08 2.8, P28 B1/B2, P26 2.1 | **EQ-15** |
| Fault-injection with negative assertions | P04 T6, P25 O7 | **EQ-16** |
| Fail-closed / fail-not-partial on fidelity paths | P25 O4, P26 2.9, P27 (fail-mode) | **EQ-20** |
| Build → install → import smoke on the wheel, not editable | P01 R1/R4/R11, P04 T8, P26 2.6 | **EQ-01** |
| License clarity (SPDX in artifact; code≠weights) | P01 R3, P26 2.10, P29 C2 | **EQ-02** |
| Versioning policy + categorized changelog + migration notes | P01 R6/R7, P02 2.3/2.4, P27 D27-07, P29 C4 | **EQ-04** |
| Import boundaries: acyclic, public-API-only, CI-enforced | P08 2.1/2.2/2.3/2.7 | **EQ-17** |
| Trace vs debug artifact separation; retention/minimization | P25 O3, P24 G4, P26 2.4 | **EQ-19 / EQ-29** |
| Docs let a new operator reproduce install→run→interpret | P20 C09/C05, P21 U12 | **EQ-26** |
| Agent-guidance files (AGENTS.md/CLAUDE.md) consistent + executable | P20 C06/C07/C08 | **EQ-27** |
| Named maintainers / release process / governance (scaled) | P27 D27-06/07, P20 C10 | **EQ-30** |

Full consolidated list in §4. This dedup directly serves FRAME §5's "no duplicate lens" requirement.

---

## 4. Consolidated engineering-quality criteria

Legend — **Class:** `U` = universal professional bar, `P` = project-specific choice (score against whisker's own stated doctrine, not as an external MUST), `U*` = universal only *if the project claims the capability*. **Exec:** `●` objective-executable (a script yields pass/fail), `◐` semi-objective (needs a sampled human check), `○` judgment. **Grade** per FRAME §6.3.

| ID | Criterion (one line) | Feeds | Class | Exec | Grade |
|---|---|---|---|---|---|
| EQ-01 | Clean build yields installable wheel **and** sdist; wheel imports; console script runs (tested on installed artifact, not editable path) | P01,P04 | U | ● | A |
| EQ-02 | License clarity: SPDX expression + LICENSE file present *inside* the built artifact; code vs model-weight licenses separated where applicable | P01,P26,P29 | U | ● | A |
| EQ-03 | PEP 621 metadata complete (`name`, `requires-python`, urls incl. changelog, classifiers match tested matrix); `twine check --strict` clean | P01 | U | ● | A |
| EQ-04 | Declared versioning policy + categorized changelog (Keep a Changelog) + breaking-change migration notes; tag↔version consistent | P01,P02,P27,P29 | U | ◐ | B |
| EQ-05 | Public surface is small, statically enumerable (`__all__`), and typed (`py.typed`, annotated public signatures) | P02,P08,P27,P29 | U* | ● | A |
| EQ-06 | Side-effect boundary: library functions return data; filesystem/network/process-global writes confined to CLI/adapters | P02 | U | ● | B |
| EQ-07 | Public return shapes are versioned, serializable, documented (dataclass/TypedDict/pydantic), not `dict[str,Any]` | P02,P27,P29 | U | ◐ | B |
| EQ-08 | Library dep ranges in metadata + committed lockfile consumed by CI (`--locked`/`--require-hashes`) | P03,P01 | U | ● | A |
| EQ-09 | Core install pulls **only** deterministic-path deps; heavy/LLM/network stacks are optional extras; core cannot import optional-only deps | P01,P03,P08,P26,P29 | U | ● | A |
| EQ-10 | CI vulnerability scan on lockfile (OSV/PyPA advisory), fail-closed on Critical/High, exceptions time-bounded with owner | P03 | U | ● | A |
| EQ-11 | Release SBOM (CycloneDX/SPDX, NTIA elements) + build provenance (SLSA ≥L1) | P03 | U | ● | A |
| EQ-12 | CI runs the test suite on every PR and protected-branch push; failing required checks block merge; reproducible from repo alone | P04,P26 | U | ● | B |
| EQ-13 | Default CI tests hermetic/deterministic: no live network, injected time/RNG/seeds, rerun-and-diff stable | P04 | U | ● | A |
| EQ-14 | Test matrix covers every declared Python version on ≥2 OS families (scaled to declared support) | P04 | U | ● | B |
| EQ-15 | Must-fail canary + metamorphic tests: deliberately corrupted fixtures **must** be rejected; CI fails if a canary passes | P04,P08,P28,P26 | U | ● | A |
| EQ-16 | Automated fault-injection suite (≥N scenarios) with **negative** assertions (no output artifact + non-zero exit) | P25,P04 | U | ● | A |
| EQ-17 | Import boundaries enforced in CI: acyclic graph among declared units; cross-package imports hit public API only | P08 | U | ● | A |
| EQ-18 | Structured logging via a hierarchical logger with stable fields; **no `print()`** for operational telemetry in library paths | P25 | U | ● | A |
| EQ-19 | Deliberate trace (concise progress, every state write appears, no silent steps) vs debug (full-fidelity I/O) artifact split | P25,P24,P26 | U | ◐ | B |
| EQ-20 | **Fail-closed / fail-not-partial** on fidelity-critical paths: on failure, non-zero exit, no result mistakable for a complete verdict | P25,P26,P27 | U | ● | A |
| EQ-21 | Errors are stage-attributed, differentiate retriable vs permanent, and are actionable (cause + remedy), not bare stack traces | P25,P21 | U | ◐ | A |
| EQ-22 | Documented, stable exit-code taxonomy (success / findings / usage-error / internal-error distinguishable) | P21,P20 | U | ● | A |
| EQ-23 | stdout = machine-parseable result, stderr = progress; `--json`/structured mode emits valid, schema-stable output | P21,P25 | U | ● | A |
| EQ-24 | TTY-aware output (NO_COLOR/non-TTY disables animation) and explicit check-vs-mutate modes with distinct exit semantics | P21 | U | ● | B |
| EQ-25 | Contract doc enumerates invariants, failure modes, exit codes, calibration status (fitted vs placeholder), and known gaps as greppable entries | P20 | U | ◐ | B |
| EQ-26 | A new operator can install → run → interpret result → find diagnostics from docs alone (zero mandatory source reads) | P20,P21 | U | ● | A |
| EQ-27 | Agent-guidance (AGENTS.md/CLAUDE.md) is version-controlled, non-conflicting across layers, and every build/test command is executable verbatim | P20 | U | ● | B |
| EQ-28 | Quality/eval reporting is per-axis; any composite is shown *alongside* axis scores, never a lone headline number used as a gate | P27,P28,P29,P30 | U | ● | A |
| EQ-29 | Debug/trace artifacts have retention + minimization policy; LLM inference routing (self-hosted vs cloud) governed and documented | P24 | P/U | ◐ | A |
| EQ-30 | Named maintainers + CONTRIBUTING + documented release process (proportionate; not full foundation/TSC machinery) | P27,P20 | U | ◐ | B |

### 4.1 Objective-executable audit methods (the part a later stage can run unattended)

FRAME §5 asks for objective, executable methods. These consolidated criteria reduce to concrete scripts:

- **Build/install (EQ-01,03,05):** `python -m build` → `twine check --strict dist/*` → fresh venv `pip install dist/*.whl` → `import <pkg>` → console-script `--help` → assert `py.typed` present in wheel → run a consumer-side `mypy`/`pyright` on documented public imports.
- **Core/optional isolation (EQ-09):** in a clean venv, `pip install .` (no extras); assert optional/LLM modules raise `ImportError`; run the deterministic test subset; SBOM/`pipdeptree` diff of `core` vs `[extra]` must show disjoint heavy deps.
- **Side-effect boundary (EQ-06):** run public API on in-memory inputs with the filesystem mocked read-only; assert **zero** file creations / network calls.
- **Import boundaries (EQ-17):** build the import graph (any tool: grimp, importlab, or a custom AST walk) and assert no cycles among declared units + no imports of `_private` cross-package paths; canary PR that adds a forbidden import must fail CI.
- **No-print (EQ-18):** grep library paths for `print(`; assert only CLI/adapter modules match.
- **Exit codes + streams (EQ-22,23):** scripted matrix over {success, findings, usage-error, internal-error}; capture `$LASTEXITCODE`; run with `> out 2> err`; assert `jq empty < out` succeeds in `--json` mode and that `err` carries the progress text.
- **Canary/fault (EQ-15,16,20):** corrupt a golden fixture → assert gate rejects (non-zero exit, no artifact written, debug preserved); mock LLM-unreachable → assert non-zero exit + no hollow-but-schema-valid result.
- **Vuln scan (EQ-10):** `pip-audit`/`osv-scanner` on the lockfile; inject a known-CVE pin in a test branch and assert CI fails.
- **Docs-alone reproduction (EQ-26):** scripted doc-walk that performs install→run→interpret using only published docs; record every mandatory source-code open (any = fail).
- **Hermeticity (EQ-13):** run the suite twice on the same commit with the network blocked; diff outputs.

Criteria EQ-04, EQ-07, EQ-19, EQ-21, EQ-25, EQ-27, EQ-29, EQ-30 need a sampled human check (◐) and are therefore weaker gate candidates than the ● criteria.

---

## 5. Rejected and downgraded claims

The FRAME requires rejecting tool-prescriptive, arbitrary, or unjustified requirements and distinguishing universal bars from project choices. The following persona proposals are **rejected** (removed as requirements) or **downgraded** (kept but demoted from gate/high-weight, or reframed tool-agnostically).

| # | Persona claim | Action | Reason |
|---|---|---|---|
| R1 | **Import Linter** specifically required (P08 2.1) | **Downgrade → tool-agnostic** | The *contract* (acyclic, enforced boundaries) is universal; mandating one library is tool-prescriptive. EQ-17 states the property, not the tool. |
| R2 | CBO coupling budget "warn >5, fail >8" (P08 2.6) | **Reject as gate; keep as low-weight signal** | Numeric thresholds are arbitrary; Briand & Wüst show CK metrics are indicative, not sufficient. Contested by its own author-cited literature. |
| R3 | Mutation kill-rate ≥85% via **mutmut** on gate modules (P04 T4) | **Downgrade** | Fault-injection *concept* kept (EQ-15/16); the specific tool and 85% figure are not a universal bar. Just et al. support mutation's validity but not a fixed threshold. |
| R4 | Coverage % as a merge gate (P04 T2) | **Reject** | Inozemtseva & Holmes: coverage weakly correlates with effectiveness at controlled suite size. Diagnostic only, never a gate. |
| R5 | SLSA **L2** as hard gate (P03 C3) | **Downgrade → maturity** | P03 itself concedes many worthy projects sit at L1. L1 gate, L2 aspiration. |
| R6 | SBOM on **every release** as hard gate (P03 C2) | **Downgrade → maturity** | Valuable; not universal enough to fail an otherwise-professional package. Kept as EQ-11 maturity. |
| R7 | OpenSSF **Scorecard ≥7** / silver badge (P03, P27 D27-09) | **Reject as universal bar** | Exemplar-specific and gameable (badge ≠ substance); aspirational, not a professional floor. |
| R8 | Dependabot/Renovate **presence** (P03 C5) | **Downgrade** | Bot-enabled ≠ maintained; tool-prescriptive. Signal, not gate. |
| R9 | Trusted Publishing / PyPI OIDC pipeline (P01 R9) | **Conditional** | Only applies if the package publishes to PyPI. A workspace-internal package is not unprofessional for lacking it. |
| R10 | **≤200-line** CLAUDE.md hard number (P20 C07) | **Downgrade → guidance** | Vendor-specific (Anthropic) heuristic, not a standard. Keep "concise, non-conflicting, executable" (EQ-27); drop the exact line cap as a gate. |
| R11 | **Diátaxis four-quadrant** coverage mandatory (P20 C01) | **Downgrade → functional-quality dims** | Diátaxis is one framework; its *underlying* dims (accuracy, completeness, consistency, navigation — P20 C02) are the universal bar. Do not fail a project for not adopting a specific IA taxonomy. |
| R12 | Bundled **HTML visualization** (P26 2.4) | **Reject as requirement** | Implementation choice. The transferable idea is provenance-linked review, satisfiable by golden diffs. |
| R13 | CI annotation formats **SARIF/JUnit/GitHub** (P21 U4) | **Downgrade → nice-to-have** | Ecosystem-specific; JSON + one format suffices. |
| R14 | SIGINT/signal handling (P21 U10) | **Downgrade → low-weight** | Real but minor for a batch QA tool; not a professionalism gate. |
| R15 | Foundation hosting / **TSC governance** (P27 D27-06/11) | **Reject at whisker scale** | LF/TSC machinery is for multi-repo foundations. Reduce to EQ-30 (named maintainers + CONTRIBUTING + release process). |
| R16 | **Self-hosted-default / model-sovereignty** as an external professional bar (P24 G5, P26/P28 "wrong for whisker" notes) | **Reclassify → project-specific (`P`)** | Model-sovereignty is a *whisker doctrine*, not a universal packaging standard. Score it against whisker's own stated invariants, not as an external MUST. What *is* universal (EQ-29): inference routing must be *documented and governed*, whichever way it points. |
| R17 | Multi-pass stochastic extraction, RLVR training, throughput/pages-per-sec benchmarks (P26 2.5, P28 A3/C2) | **Out of scope for gates** | Advisory-lane or research concerns; throughput ≠ QA quality (P28 concurs). |
| R18 | LLM-judge score used as a **gate** by default (P30 E11, DeepEval/Ragas pattern) | **Reject for gating** | Self-consistent with whisker's advisory-only doctrine and P10 validation need. Keep structure (threshold + reason), reject gate authority. |

**Contradictions carried forward (record both, do not resolve arbitrarily — FRAME §6.5):**
- *Graceful degradation vs fail-not-partial* (P25 O3/O4): SRE permits degraded output; OWASP/fidelity demands fail-closed. **Rule:** classify subpaths — deterministic gate = fail-closed; optional advisory lane may degrade *without* gating.
- *Strict vs loose SemVer* (P01 R6, P02 2.3, Hyrum's Law): score **declared policy + internal consistency**, not doctrinal purity.
- *TEVV retention vs data minimization* (P24 G4): resolve via tiered artifacts (hash/verdict/seed default; full I/O opt-in, TTL-bound).

---

## 6. Hard gates (conjunctive; a fail caps the verdict regardless of weighted score)

Kept deliberately short (FRAME §6.2). All are objective-executable ● except where noted. Each mirrors whisker's own conjunctive design, so the rubric is no weaker than the thing it audits.

| Gate | Criterion | Why non-compensatory | Objective test |
|---|---|---|---|
| **EG-1 Buildable** | EQ-01 | A non-installable wheel/sdist voids any "release-ready" claim | build → install in fresh venv → import + script `--help` |
| **EG-2 License clear** | EQ-02 | Missing/incompatible license is a redistribution/legal defect | SPDX in METADATA + LICENSE file inside wheel/sdist |
| **EG-3 CI blocks on PR** | EQ-12 | Untested merges cannot be "professional"; a QA tool that isn't itself CI-gated is self-refuting | branch-protection lists required checks; steps lack `continue-on-error` |
| **EG-4 Fail-not-partial** ★ | EQ-20 | A partial QA verdict mistaken for complete destroys trust irrecoverably | fault-inject each critical stage → assert non-zero exit + no result artifact |
| **EG-5 CLI contract** | EQ-22 + EQ-23 | CI conjunctive gates need a predictable `$?` and clean stdout stream | exit-code matrix + `jq empty` on `--json` stdout |
| **EG-6 Gate teeth** | EQ-15 | A QA tool with zero must-fail canaries has *unproven* gates | corrupt golden → assert rejection; CI fails if canary passes |
| **EG-7 Boundary integrity** | EQ-17 + EQ-09 | Cycles / core→optional leakage make the hybrid separation unenforceable | acyclic graph check + core-only install cannot import optional deps |
| **EG-8 Vuln floor** | EQ-10 | Shipping a known Critical CVE with no documented exception is indefensible | scanner fail-closed on injected CVE fixture |
| **EG-9 Operable from docs** | EQ-26 | Operators cannot trust verdicts they cannot run or interpret; "documented" must mean operable (§6.4) | scripted doc-walk with zero mandatory source opens |

**Conditional gates (fire only when the trigger holds):**
- **EG-10 (typed claim):** if README/CLAUDE.md advertises a *typed API*, `py.typed` must ship and public signatures must type-check (EQ-05). Not-claimed ⇒ weighted-only.
- **EG-11 (cloud inference):** if content is sent to a cloud LLM by default, documented no-training + retention terms are required, and indefinite full-fidelity debug retention fails (EQ-29). WG21 papers being public lowers baseline risk, so this is proportionate/conditional, not a blanket gate (P24).

**★ Strongest single gate: EG-4 (fail-not-partial).** It is the one non-compensatory property where perfect packaging, docs, and tests still leave the tool dangerous: it can emit a hollow "pass" that operators trust. It is also cheanly falsifiable by fault injection. This is the cluster's highest-leverage criterion.

---

## 7. Engineering-quality maturity ladder (0–4)

Applied to the cluster as a whole; per-criterion sub-ladders live in the source personas.

| Level | Descriptor |
|---|---|
| **0 — Prototype** | Manual local runs; no CI; unstructured `print()`; installable-only-in-checkout; license/exit-codes/streams undocumented; silent partial output on failure. |
| **1 — Baseline** | CI on PR; builds a wheel; core deps declared; some structured logging; a README quickstart; errors surface but are generic; single-number reporting. |
| **2 — Professional** | EG-1..EG-3,EG-5 hold: installable+imports, license clear, CI blocks, exit-code/stream contract documented and tested; hermetic default tests; OS×Python matrix; typed public surface if claimed; per-axis reporting (EQ-28); actionable errors (EQ-21). |
| **3 — Trusted QA tool** | Level 2 + **all hard gates** (EG-4 fail-not-partial, EG-6 canary teeth, EG-7 boundary integrity, EG-8 vuln floor, EG-9 docs-operable); trace/debug artifact split with no silent steps; contract doc with invariants/failure-modes/calibration-status/known-gaps; lockfile-driven CI; retention/inference-routing governance documented. |
| **4 — Exemplar** | Level 3 + automated fault-injection suite in CI with negative assertions; SBOM + SLSA≥L1 provenance; import-boundary regression canary; consumer-side typecheck job; agent-guidance non-conflicting and executable; governance (named maintainers + release process) and migration-noted changelog; per-axis regression baseline. |

"Professional-grade" per the FRAME objective = **Level 3 floor**. Level 2 with any failed hard gate is a failing verdict regardless of composite.

---

## 8. Weights (intra-cluster; cross-cluster normalization deferred to top synthesis)

Weights are claims, not vibes (FRAME §6.1). These are **relative weights within the engineering-quality cluster**, summing to 100%. The cluster's share of the *overall* composite should be roughly **35–45%** (engineering quality is large but must leave room for eval-science, determinism, adversarial, and security/provenance clusters owned by other meta-reviewers); exact cross-cluster weights belong to the final synthesis.

| Sub-dimension (criteria) | Intra-cluster weight | Rationale |
|---|---|---|
| Failure-handling & observability (EQ-16,18,19,20,21) | **22%** | Contains the strongest gate (EG-4); a QA tool's trust rests here; OWASP/OTel/SRE Tier-1 backing. |
| Release/packaging correctness (EQ-01,02,03,04) | **16%** | Table-stakes; PyPA Tier-1; necessary not differentiating. |
| CI & test maturity (EQ-12,13,14,15) | **16%** | Trust foundation: if tests lie, gates lie. Canary teeth (EG-6) here. |
| API & contract design (EQ-05,06,07) | **12%** | Load-bearing for integrators and downstream eval; side-effect boundary is falsifiable. |
| Modularity & boundaries (EQ-09,17) | **10%** | Enables the hybrid deterministic/advisory separation to be enforceable. |
| Docs & operator/agent UX (EQ-22,23,24,25,26,27) | **12%** | Operability gate (EG-9) + CLI contract (EG-5) here; enables but does not substitute for correct gates. |
| Supply-chain & deps (EQ-08,10,11) | **8%** | Vuln floor is a gate (EG-8); SBOM/SLSA are maturity. |
| Privacy/governance (EQ-29,30) | **4%** | Proportionate: WG21 papers are public-by-design (P24), lowering baseline risk; non-zero because debug retention + inference egress create real obligations. |

**Composite reporting rule (EQ-28 applied to the audit itself):** report per-sub-dimension scores alongside the cluster composite; never a lone headline number. Composite inherits the **weakest evidence grade** among load-bearing inputs (§6.3) — here typically **A**, dropping toward **B** if EQ-19/EQ-25/EQ-27 (all grade B, ◐) become load-bearing.

---

## 9. Confidence, contested items, and flip conditions

**Overall confidence: HIGH** for the universal engineering bars. The rubric rests on a strong, live-verified Tier-1 backbone: PEPs 517/518/621/639/561/387/702/794, NIST SP 800-218 / AI RMF / Privacy Framework, SLSA, OWASP RAG, OpenTelemetry, clig.dev, PyPA, Keep a Changelog, semver.org. Grade **A** dominates the objective-executable gates.

**Medium-confidence (grade B, judgment-based):**
- EQ-19 trace-vs-debug split — an *assembled* pattern (OTel severity + SRE + Great Expectations result tiers); no single standard names "trace vs debug files."
- EQ-27 agent-guidance — vendor docs (Anthropic/OpenAI/agents.md), fast-moving; the *format* conventions are less stable than the *executable-command* requirement.
- EQ-30 governance scaling — judgment call on how far to scale down foundation practice.
- EQ-04 versioning — Hyrum's Law means SemVer communicates intent, not guarantees.

**Contested (widen the band, lower weight until resolved — FRAME §6.5/§6.6):**
1. Fail-closed vs graceful-degradation default (resolve by subpath classification).
2. Coverage/mutation numeric thresholds (rejected as gates; kept diagnostic).
3. Self-hosted vs cloud inference default — reclassified as whisker *doctrine*, needs the user's own stance (see FRAME §10 open question); scored as project-specific, not external bar.
4. Strict vs loose SemVer.

**Flip conditions (single re-grades that move the cluster verdict across a band boundary):**
- Reclassifying **EG-4 (fail-not-partial)** from gate to weighted would let a well-packaged tool with hollow-output-on-failure reach "professional" — the largest single lever; do not soften without explicit user approval.
- Reclassifying **EQ-06 (side-effect boundary)** from gate-adjacent to advisory flips release-readiness for any library that writes inside core API calls.
- Treating **EG-11 (cloud inference)** as unconditional rather than proportionate would over-penalize a public-WG21 tool; keep conditional.

**Anti-gaming posture (FRAME §6.4):** every gate above is paired with a falsification test (inject-and-assert), not a documentation check. "Has tests" → "a canary that must fail does fail"; "documented" → "an operator reproduces a run from docs alone"; "typed" → "a consumer typecheck passes on public imports." Cosmetic compliance is closed at each gate.

---

## 10. Overlap / boundary statement

This meta-review consumed only `research/Audit/**` persona outputs and public standards; it did **not** open whisker production code, cite whisker `file:line`, or score whisker. It did not re-litigate the code-level `persona/` or `llm-stack/` swarms, the `langextract/`/`buildvsbuy/`/`redteam/` decisions, or other meta-reviewers' clusters (eval-science P09–P13, determinism P05–P07, scoring/calibration P14–P17, adversarial P18–P19, security P23, provenance/licensing P22). At boundaries I cite them (e.g., EQ-28 hands eval-science the per-axis rule; EG-11 defers to P23/P24 for security/privacy depth; EQ-02 defers full license-compatibility to P22). Output is exactly this one file under `packages/whisker/research/Audit/`.

---

*End of Meta-Review C — Engineering-Quality Rubric.*
