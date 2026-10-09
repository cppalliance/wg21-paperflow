# P03 — Dependency & Supply-Chain Hygiene Researcher

**Persona:** 3 of 30 (Cluster A — Professional Python package & release readiness)  
**Date:** 2026-07-18  
**Stage:** Internet-research persona (external method only; no whisker code inspection)

---

## 1. Question restated

What external bar should a **professional, release-ready Python library** (especially one with optional LLM/heavy extras) meet for **dependency and supply-chain integrity**—covering declaration vs locking discipline, SBOM/provenance, build integrity (SLSA), transitive and optional-extra risk containment, and continuous vulnerability management—and how should that bar be turned into **auditable criteria** for the whisker professional-grade audit rubric?

This persona researches **how to audit** dependency/supply-chain hygiene and **what "good" looks like** against authoritative standards and exemplar practice. It does not inspect whisker's dependency tree, `pyproject.toml`, or CI configuration.

**Boundary vs P22:** P22 covers license/attribution/fork hygiene of ported or reimplemented code. This persona covers **dependency graph integrity, provenance, vuln lifecycle, and build-time supply-chain controls**. License *visibility* via SBOM fields is in scope here; license *compatibility matrices* and port-vs-vendor attribution are P22.

---

## 2. Proposed audit criteria

Each criterion is designed for later application to whisker by the synthesis stage. Evidence grades follow `00-FRAME.md` §6.3 (A = multiple Tier-1 corroborating; B = single Tier-1 or converging Tier-2).

---

### Criterion 1 — Library-vs-application dependency declaration discipline

| Field | Content |
|---|---|
| **Criterion** | **Core runtime dependencies** in distributable metadata (`[project].dependencies`) use **compatible-release or bounded ranges**, not exact pins, so downstream consumers are not over-constrained. **Dev/CI/test environments** use a **committed lockfile** (e.g. `uv.lock`, `pylock.toml`, Poetry/Pipenv lock) with exact resolved versions for reproducibility. |
| **How to measure** | Inspect `pyproject.toml`: core `dependencies` are specifier strings per PEP 508, not `==` pins unless justified (e.g. known ABI break). Confirm a lockfile exists, is committed, and is the input to CI install (`uv sync --locked`, `pip install --require-hashes`, etc.). Score partial if lockfile exists but CI ignores it. |
| **Audit method** | Conformance checklist (#1); maturity model (#2) — levels 0–4 on declaration/lock split. |
| **Scoring-design hook** | §6.1 dimension: release-readiness / supply-chain; §6.4 anti-gaming. |
| **Gaming vector** | Pinning everything in `pyproject.toml` passes "reproducibility" cosmetically while breaking library composability; or declaring ranges in metadata but never locking CI so tests drift silently. |
| **Anti-gaming guard** | Require **both**: (a) metadata ranges appropriate to a library, and (b) CI install provably from lockfile with a documented tool command in contributor docs. Canary: bump a transitive in lockfile only—CI must still pass with `--locked`. |
| **Evidence grade** | **A** — PyPA `pyproject.toml` spec (PEP 621), `pylock.toml` spec, and packaging community consensus on library vs application roles. |
| **Sources** | PyPA pyproject.toml spec; PyPA pylock.toml spec; pip dependency-resolution guidance. |

---

### Criterion 2 — SBOM per release with NTIA minimum elements

| Field | Content |
|---|---|
| **Criterion** | Each **release artifact** (or tagged release CI job) produces a **machine-readable SBOM** in CycloneDX or SPDX format listing **direct and transitive** Python components with NTIA minimum elements: supplier, component name, version, unique identifier (PURL/CPE), dependency relationships, SBOM author, timestamp. |
| **How to measure** | CI or release workflow emits SBOM (e.g. `cyclonedx-py environment`, `cyclonedx-py requirements`, or `pip-audit -f cyclonedx-json`). Validate with NTIA/SPDX conformance tooling. SBOM attached to GitHub Release or stored as build artifact; updated when any component changes (NIST PS.3.2). |
| **Audit method** | Conformance checklist (#1); provenance/license audit (#10) — SBOM slice only. |
| **Scoring-design hook** | §6.1 supply-chain dimension; §6.2 candidate hard gate (missing SBOM on release). |
| **Gaming vector** | SBOM generated once manually and never regenerated; or SBOM lists only direct deps omitting transitives. |
| **Anti-gaming guard** | SBOM must be **CI-generated** from the same lockfile/resolver output used to build/test the release; include `dependencies` graph edges; timestamp within release window; diff SBOM across two releases with a dependency bump—component set must change. |
| **Evidence grade** | **A** — NIST SSDF PS.3.2; NTIA minimum elements; ISO/IEC 5962 (SPDX); CycloneDX spec/tooling. |
| **Sources** | NIST SP 800-218 PS.3.2; SPDX NTIA HOWTO; CycloneDX Python docs; NTIA conformance checker. |

---

### Criterion 3 — SLSA Build Track provenance (minimum L1, target L2)

| Field | Content |
|---|---|
| **Criterion** | Release wheels/sdists are built with **documented, automated provenance** meeting at least **SLSA Build L1** (provenance exists describing builder, process, top-level inputs). Target **Build L2** for production releases: provenance **generated and signed by a hosted CI platform**, consumer-verifiable. |
| **How to measure** | For latest release: provenance attestation present (GitHub Actions `slsa-github-generator`, Sigstore, or equivalent). Verify L1 fields: build platform id, source commit digest, build invocation id. L2: signature validates against hosted builder. Document level claimed vs achieved. |
| **Audit method** | Conformance checklist (#1); reproducibility replay (#8) — provenance complements rerun-and-diff. |
| **Scoring-design hook** | §6.1 supply-chain; §6.2 hard gate candidate only if org claims SLSA L2+ but provenance is forgeable/missing. |
| **Gaming vector** | Local `python -m build` releases without provenance while marketing "secure supply chain"; or provenance file checked in manually without CI binding. |
| **Anti-gaming guard** | Provenance digest must match release tag commit; CI workflow must be the sole release publisher; provenance unavailable for ad-hoc PyPI uploads. |
| **Evidence grade** | **A** — SLSA spec v1.1/v1.2 build track levels. |
| **Sources** | SLSA spec levels v1.1; SLSA spec v1.2 overview. |

---

### Criterion 4 — CI vulnerability scanning against authoritative advisories

| Field | Content |
|---|---|
| **Criterion** | CI runs **automated dependency vulnerability scanning** on every PR and default branch, using **PyPA advisory database and/or OSV** (e.g. `pip-audit`, `uv audit`, `osv-scanner` on lockfile). **Fails closed** on configured severity threshold (e.g. known Critical/High in resolved graph) unless a **time-bounded exception** is recorded with CVE id, risk rationale, and remediation ticket. |
| **How to measure** | CI config contains audit step; logs show scanner version and DB source; failing CVE injected in a test branch causes non-zero exit. Exception register exists (SECURITY.md or equivalent) per NIST RV.1.3 / RV.2. |
| **Audit method** | Conformance checklist (#1); observability/fault-injection (#11) — inject known-vulnerable pin in test PR. |
| **Scoring-design hook** | §6.2 **hard gate** (recommended): unreleased Critical CVE in locked deps without documented exception. §6.1 supply-chain weight. |
| **Gaming vector** | Scanner runs only on `requirements.txt` while CI installs from unlocked resolver; or `--ignore-vuln` list grows without review; or scanner in `continue-on-error` mode. |
| **Anti-gaming guard** | Scan input must be **lockfile or frozen env** identical to test install; ignore list requires expiry date + owner; monthly CI job proves scanner still fails on synthetic CVE fixture. |
| **Evidence grade** | **A** — NIST SSDF PW.4.4 (automatic vuln detection), RV.1.1 (monitor databases); PyPA pip-audit/OSV integration. |
| **Sources** | NIST SP 800-218 PW.4.4, RV.1.1; pip-audit README/PyPI; OSV docs; Astral uv audit blog. |

---

### Criterion 5 — Dependency update automation (out-of-date deps)

| Field | Content |
|---|---|
| **Criterion** | Project enables **automated dependency update tooling** (Dependabot, Renovate, PyUp, or equivalent) for Python lockfile/manifest **and** GitHub Actions pin updates, with merge policy documented. |
| **How to measure** | Config file present (`.github/dependabot.yml`, `renovate.json`). OpenSSF Scorecard **Dependency-Update-Tool** check passes. Evidence of bot-opened PRs within last 90 days or documented exemption. |
| **Audit method** | Comparative benchmarking (#3) vs OpenSSF Scorecard; maturity model (#2). |
| **Scoring-design hook** | §6.1 supply-chain (maintenance signal); not a hard gate alone (bot enabled ≠ bot merged). |
| **Gaming vector** | Dependabot enabled for a dummy ecosystem only; or update PRs auto-merged without CI. |
| **Anti-gaming guard** | Config must cover **Python ecosystem** lockfile path actually used; require CI green on update PRs; score capped if zero merged updates in 12 months without justification. |
| **Evidence grade** | **B** — OpenSSF Scorecard checks (Tier-2 exemplar bar converging with NIST PW.4.1 maintenance tasks). |
| **Sources** | OpenSSF Scorecard Dependency-Update-Tool; NIST SSDF PW.4.1 task 7. |

---

### Criterion 6 — Pinned CI/build dependencies (Actions, containers)

| Field | Content |
|---|---|
| **Criterion** | **Build and release** workflows pin third-party actions and container images by **immutable digest (SHA256)** or exact version, not mutable tags (`@v4`, `:latest`). |
| **How to measure** | OpenSSF Scorecard **Pinned-Dependencies** check on repo; manual spot-check: `uses: actions/checkout@<40-char-sha>`, container `image: digest@sha256:...`. |
| **Audit method** | Conformance checklist (#1); adversarial probing (#6) — tag substitution attack surface. |
| **Scoring-design hook** | §6.1 supply-chain; supports SLSA L2/L3 builder trust chain. |
| **Gaming vector** | Pin actions but leave reusable workflows or composite actions unpinned; pin only release workflow, not PR CI. |
| **Anti-gaming guard** | All workflows in `.github/workflows/` subject to check; Renovate `pinDigests` or equivalent enabled for Docker. |
| **Evidence grade** | **B** — OpenSSF Scorecard Pinned-Dependencies; SLSA L2 hosted-platform requirement. |
| **Sources** | OpenSSF Scorecard checks.md; SLSA Build L2; Microsoft .NET OpenSSF guidance. |

---

### Criterion 7 — Optional extras and core dependency minimization

| Field | Content |
|---|---|
| **Criterion** | **Core install** (`pip install package`) pulls only dependencies required for the default deterministic path. Heavy, network, or LLM-stack deps are isolated in **`[project.optional-dependencies]`** extras (PEP 621), documented with install strings. No optional extra is required for core QA gate functionality. |
| **How to measure** | `pip install .` (no extras) dependency tree reviewed via SBOM or `pipdeptree`: count and classify deps. Compare core vs `[extra]` trees. Extras named per PyPA conventions; each extra has README/docs entry explaining scope and supply-chain risk. |
| **Audit method** | Maturity model (#2); metric construct validity (#4) — "core deps count" must correlate with attack surface. |
| **Scoring-design hook** | §6.1 release-readiness + architecture (hybrid lane isolation); §6.4 anti-gaming. |
| **Gaming vector** | Sneak LLM SDK into core `dependencies` while claiming "optional LLM lane"; or one mega-extra that pulls entire stack by default in docs. |
| **Anti-gaming guard** | CI matrix job installs **core only** and runs deterministic test subset; SBOM diff core vs `[tapetum-llm]` (or equivalent) must show disjoint heavy deps. |
| **Evidence grade** | **A** — PyPA pyproject.toml `optional-dependencies`; PyPA writing guide; NIST PW.4.1 (evaluate components in context of use). |
| **Sources** | PyPA pyproject.toml spec; PyPA writing pyproject.toml guide; NIST SSDF PW.4.1. |

---

### Criterion 8 — Transitive dependency visibility and review trigger

| Field | Content |
|---|---|
| **Criterion** | **Transitive dependencies** are visible in SBOM/lockfile with **dependency relationships** (NTIA element). Process exists to **review new transitive packages** when lockfile changes (PR diff summary, bot comment, or policy in CONTRIBUTING). |
| **How to measure** | Lockfile PRs show transitive delta; SBOM `dependsOn`/`CONTAINS` edges populated. Documented trigger: any net-new package name in lock → human or automated policy check (maintainer count, typosquat signals, deprecated status via PEP 792/adverse metadata where available). |
| **Audit method** | Provenance audit (#10); maturity model (#2). |
| **Scoring-design hook** | §6.1 supply-chain; §6.3 evidence grade propagates from SBOM quality. |
| **Gaming vector** | Lockfile committed but never reviewed; SBOM flat list without edges. |
| **Anti-gaming guard** | CI comment bot lists net-new packages on lockfile diff; sample audit of 3 random transitives matches SBOM entries. |
| **Evidence grade** | **A** — NTIA minimum elements (relationship); NIST PW.4.1 task 3 (provenance analysis); CycloneDX dependency graph. |
| **Sources** | SPDX NTIA HOWTO; NIST SSDF PW.4.1; CycloneDX Python usage docs. |

---

### Criterion 9 — Vulnerability response and remediation SLA

| Field | Content |
|---|---|
| **Criterion** | Published **vulnerability disclosure and remediation policy** (SECURITY.md or equivalent) aligned with NIST SSDF **RV.1.3 / RV.2**: intake channel, severity rubric, target remediation windows, and process for **third-party component CVEs** affecting releases. |
| **How to measure** | SECURITY.md exists; references dependency CVE handling; table mapping severity → SLA; evidence of at least one dependency CVE drill or real response. RV.2.1 prioritization by risk documented. |
| **Audit method** | Documentation-completeness audit (#9); maturity model (#2). |
| **Scoring-design hook** | §6.1 supply-chain; §6.2 gate if policy wholly absent for a release-claiming package. |
| **Gaming vector** | Boilerplate SECURITY.md with no dependency clause; SLAs with no owner. |
| **Anti-gaming guard** | Policy must mention **dependency/CVE sources** (OSV, GitHub Advisories, PyPA); link to exception register used by Criterion 4. |
| **Evidence grade** | **A** — NIST SSDF RV.1.3, RV.2.1. |
| **Sources** | NIST SP 800-218 RV.1.3, RV.2.1. |

---

### Criterion 10 — Supply-chain tooling integration in developer workflow

| Field | Content |
|---|---|
| **Criterion** | Documented, one-command paths for contributors to: sync locked env, run vuln audit, and (optionally) generate local SBOM—without undocumented manual steps. |
| **How to measure** | README/CONTRIBUTING lists commands (`uv sync`, `uv audit`, `cyclonedx-py`, etc.); `make`/task runner targets optional; CI uses same commands. |
| **Audit method** | Documentation-completeness audit (#9); operator UX cross-link to P21. |
| **Scoring-design hook** | §6.4 — "documented" means operator can reproduce from docs alone. |
| **Gaming vector** | Docs reference stale pip-tools commands while CI uses uv; audit steps only in maintainer wiki. |
| **Anti-gaming guard** | Fresh clone test: contributor script sequence from docs reproduces CI env + audit pass/fail behavior. |
| **Evidence grade** | **B** — PyPA managing-dependencies tutorial; Real Python / Veracode lockfile practice (Tier-2 convergence). |
| **Sources** | PyPA managing application dependencies; Real Python dependency-management best practices. |

---

## 3. External benchmark / exemplar bar

### Authoritative floor (must cite for any pass claim)

| Standard | Bar for a professional Python QA library |
|---|---|
| **NIST SSDF v1.1** | PW.4.1: obtain SBOM/provenance for components; PW.4.4: automatic vuln detection in toolchain; PS.3.2: maintain/release SBOM; RV.1.1: monitor OSV/advisory sources continuously. |
| **NTIA + SPDX/CycloneDX** | SBOM with all seven minimum elements; prefer SPDX ISO/IEC 5962 or CycloneDX Ecma-424; validate with NTIA/CISA conformance checker where possible. |
| **SLSA Build L1→L2** | L1 for all tagged releases; L2 for projects claiming supply-chain hardening (signed CI provenance). |
| **PyPA** | PEP 621 metadata for deps/extras; lockfile (`uv.lock` / `pylock.toml`) for CI reproducibility; library ranges vs application locks. |

### Exemplar practice (Scorecard + modern Python tooling)

Mature OSS Python projects converge on:

1. **OpenSSF Scorecard ≥ 7** on Dependency-Update-Tool, Vulnerabilities, Pinned-Dependencies, and CI-Tests checks (Tier-2 benchmark, not worship).
2. **Lockfile-first CI** with `uv` or equivalent; **`uv audit` / `pip-audit`** in GitHub Actions on push/PR.
3. **Dependabot or Renovate** for Python + GitHub Actions ecosystems.
4. **Release SBOM** as artifact (CycloneDX JSON common in security tooling; SPDX for license-heavy compliance).
5. **Optional extras** for ML/LLM stacks (PyPA pattern), keeping PyPI default install lightweight.

**Exemplar composite bar (maturity levels 0–4 summary):**

| Level | Descriptor |
|---|---|
| **0** | No lockfile; no CI vuln scan; manual releases; no SBOM. |
| **1** | Lockfile in repo; ad-hoc `pip-audit`; deps declared in pyproject. |
| **2** | CI vuln scan fails on Critical; Dependabot enabled; SBOM on release; core/extra split documented. |
| **3** | Locked CI + exception register; pinned Actions; SBOM with transitive edges; SECURITY.md with CVE SLAs; SLSA L1 provenance. |
| **4** | SLSA L2 signed provenance; regular merged dependency updates; SBOM validated NTIA; synthetic CVE canary in CI; adverse/deprecated package metadata monitored (PEP 792 / uv audit adverse status). |

**Where exemplars may be wrong for whisker:** Cloud-first packages that pin entire stacks in core metadata, or that treat LLM APIs as core dependencies, violate whisker's hybrid doctrine and model-sovereignty constraints. Cargo-culting their dependency breadth into whisker's core install would fail Criterion 7 even if the exemplar scores highly on Scorecard.

---

## 4. Recommended weight & hard gates

### Recommended composite weight: **9–11%** of total audit score

**Rationale:** Supply-chain sits in the `00-FRAME.md` security/privacy/supply-chain dimension shared with P23 (security/injection) and P24 (privacy). P03 owns **dependency graph, SBOM, vuln lifecycle, and build provenance**—not prompt injection or data retention. Weight below documentation or determinism dimensions but above nice-to-have UX niches, because NIST SSDF and EO 14028 mappings treat component integrity and vuln response as **foundational** producer practices, not optional hardening.

Sub-weight suggestion within dimension:

| Sub-criterion | Share of P03 block |
|---|---|
| C4 CI vuln scanning | 25% |
| C2 SBOM / NTIA | 20% |
| C1 declaration/lock discipline | 15% |
| C7 optional-extras isolation | 15% |
| C3 SLSA provenance | 10% |
| C5 update automation | 8% |
| C6 pinned CI deps | 7% |
| C8 transitive visibility | 5% |
| C9 vuln response policy | 3% |
| C10 contributor tooling docs | 2% |

### Recommended hard gates (conjunctive; independent of weighted score)

| Gate | Condition | Rationale |
|---|---|---|
| **G-SC-1** | **Known Critical CVE** in the locked release dependency graph **without** a documented, time-bounded exception and remediation plan. | NIST PW.4.4 / RV.2; unreleased critical vulns invalidate "professional release-ready" claim regardless of feature quality. |
| **G-SC-2** | **No CI vulnerability scanning** against OSV/PyPA (or equivalent authoritative DB) on PR/default branch. | RV.1.1 requires ongoing identification; manual ad-hoc scans are not auditable. |
| **G-SC-3** | **Heavy/LLM/network stack in core dependencies** when documentation claims LLM lane is optional (Criterion 7 failure). | Supply-chain risk and install footprint violate stated hybrid architecture; anti-cargo-cult gate. |

**Not recommended as hard gates (weighted only):** SLSA L2 (many worthy Python projects still at L1); Dependabot presence without execution; SBOM on every commit (release-level suffices per PS.3.2 examples).

### Strongest criterion (highest evidence defensibility)

**Criterion 4 — CI vulnerability scanning against authoritative advisories (OSV / PyPA advisory database)** is the strongest single criterion:

- **Triple Tier-1 anchoring:** NIST SSDF PW.4.4 explicitly requires automatic known-vulnerability detection in the toolchain; RV.1.1 requires monitoring vulnerability databases and reviewing composition data; PS.3.2 ties remediation to maintained provenance/SBOM.
- **Tier-2 tooling convergence:** PyPA-maintained `pip-audit` (advisory-database + OSV), OSV.dev (OpenSSF vulnerability schema aggregator), and `uv audit` (lockfile-native) implement the same bar with fail-closed CI integration.
- **Measurable anti-gaming:** Synthetic CVE injection in CI is an objective falsification test unmatched by softer criteria like "has a lockfile."
- **Direct consumer protection:** Addresses active exploits in the resolved graph, not just documentation of good intentions.

---

## 5. Sources (tiered)

### Tier 1 — Authoritative / primary

| ID | Source | Version / date | URL |
|---|---|---|---|
| T1-1 | NIST SP 800-218 — Secure Software Development Framework | v1.1, Feb 2022 (final) | https://csrc.nist.gov/pubs/sp/800/218/final |
| T1-2 | NIST SP 800-218 PDF (full text) | v1.1, 2022 | https://nvlpubs.nist.gov/nistpubs/specialpublications/nist.sp.800-218.pdf |
| T1-3 | SLSA specification — Security levels | v1.1 (current track); v1.2 spec published | https://slsa.dev/spec/v1.1/levels ; https://slsa.dev/spec/v1.2/ |
| T1-4 | SPDX + NTIA Minimum Elements HOWTO | SPDX 2.3 mapping; NTIA 2021 min elements | https://spdx.github.io/spdx-ntia-sbom-howto/ |
| T1-5 | ISO/IEC 5962:2021 — SPDX Specification | Ed. 1, Aug 2021 | https://www.iso.org/standard/81870.html |
| T1-6 | PyPA — `pyproject.toml` specification (PEP 621) | Packaging guide, 2025–2026 | https://packaging.python.org/en/latest/specifications/pyproject-toml/ |
| T1-7 | PyPA — `pylock.toml` specification | Packaging guide, 2025–2026 | https://packaging.python.org/en/latest/specifications/pylock-toml/ |
| T1-8 | CycloneDX — SBOM Generation Tool for Python (official docs) | v7.3.0 | https://cyclonedx-bom-tool.readthedocs.io/en/latest/ |

### Tier 2 — Strong secondary

| ID | Source | Version / date | URL |
|---|---|---|---|
| T2-1 | PyPA — Writing your pyproject.toml (optional-dependencies) | 2025–2026 | https://packaging.python.org/en/latest/guides/writing-pyproject-toml/ |
| T2-2 | PyPA — Managing application dependencies | 2025–2026 | https://packaging.python.org/en/latest/tutorials/managing-dependencies/ |
| T2-3 | pip — Dependency resolution (lockfiles / constraints) | pip 26.1.x stable | https://pip.pypa.io/en/stable/topics/dependency-resolution/ |
| T2-4 | PyPA — pip-audit (GitHub / PyPI) | v2.10.1 | https://github.com/pypa/pip-audit/ ; https://pypi.org/project/pip-audit/ |
| T2-5 | OSV — Introduction / schema infrastructure | OpenSSF OSV.dev | https://osv.dev/docs/ |
| T2-6 | Astral — Vulnerability and malware checks in uv (`uv audit`) | Blog, 2026 | https://astral.sh/blog/uv-audit |
| T2-7 | OpenSSF Scorecard — checks (Dependency-Update-Tool, Pinned-Dependencies, Vulnerabilities) | main branch docs | https://github.com/ossf/scorecard/blob/main/docs/checks.md |
| T2-8 | SPDX — NTIA conformance checker | 2024 (FSCT3 + NTIA) | https://github.com/spdx/ntia-conformance-checker |
| T2-9 | Real Python — dependency management best practices | Reference guide | https://realpython.com/ref/best-practices/dependency-management/ |

### Tier 3 — Contextual (non-load-bearing)

| ID | Source | Note |
|---|---|---|
| T3-1 | discuss.python.org — pinning thread | Illustrates library vs lockfile consensus; not normative. |
| T3-2 | Veracode — Pick a Python lockfile | Practitioner blog supporting lockfile security motivation. |
| T3-3 | DEV Community — uv audit vs pip-audit comparison | Useful limitation notes (preview status, OSV list-matching); corroborates Tier-2. |

### Contradictions surfaced

| Topic | Position A | Position B | Resolution for rubric |
|---|---|---|---|
| **Library pinning** | Pin everything for max reproducibility (application pattern) | Never pin library deps in metadata (PyPA/discuss.python.org) | **Split contract:** ranges in `[project].dependencies`, pins in lockfile only. |
| **SBOM format** | CycloneDX favored by security tooling | SPDX favored for license/compliance (ISO 5962) | Accept **either** if NTIA minimum elements satisfied; prefer project-standard + conformance check. |
| **Scanner choice** | `pip-audit` mature, PyPA-backed | `uv audit` faster, lockfile-native but preview | Either satisfies C4 if OSV/PyPA-backed and CI fail-closed; document scanner version in CI logs. |

**Distinct Tier 1–2 primary sources used for criteria:** **17** (8 Tier-1, 9 Tier-2).

---

## 6. Overlap statement

This persona **did not**:

- Open, inspect, or score **whisker production code**, `pyproject.toml`, lockfiles, CI workflows, or dependency trees.
- Cite whisker `file:line` or reach any whisker pass/fail verdict.
- Clone, fork, or copy any repository code.
- Duplicate **P22** (provenance/licensing/fork hygiene of ported algorithms) — license compatibility matrices and THIRD_PARTY_NOTICES attribution are out of scope here except SBOM license *fields* for visibility.
- Duplicate **`buildvsbuy/`** library-choice decisions (which calibration/metric package to import).
- Duplicate **`persona/`** or **`llm-stack/`** code-level audits (those scored whisker's existing deps and tapetum isolation).
- Re-litigate **`langextract/`** adoption (Apache-2.0 DP port attribution is P22/langextract swarm territory).

This persona **did** research external dependency/supply-chain standards (NIST SSDF, SLSA, NTIA/SPDX/CycloneDX, PyPA, OSV/PyPA advisory tooling, OpenSSF Scorecard) and produced **audit criteria + exemplar maturity bar** for the synthesis stage to apply later against whisker.

---

*End of P03 report.*
