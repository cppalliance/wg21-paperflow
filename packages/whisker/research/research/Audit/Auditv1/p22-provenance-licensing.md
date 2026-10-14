# P22 — Provenance, Licensing & Fork-Hygiene Researcher

**Persona:** 22 (Cluster G)  
**Date:** 2026-07-18  
**Scope:** External method and audit criteria only. No whisker production-code inspection, no whisker verdict.

---

## 1. Question Restated

What external bar should a professional Python library (especially one that may **port algorithms**, **vendor dependencies**, or **re-implement** functionality observed in third-party repos) meet for **license compatibility, attribution, port-vs-vendor discipline, copyright-header hygiene, and honest provenance** — and which of those obligations warrant **hard gates** in a composite audit?

This persona researches *how to audit* provenance and licensing conformance. It does not inspect whisker code, re-litigate LangExtract adoption, or score dependency SBOM integrity (that is P03).

---

## 2. Proposed Audit Criteria

Each criterion below maps to audit-method **#10 (Provenance / license conformance audit)** unless noted. Scoring hooks reference `00-FRAME.md` section 6.

---

### Criterion P22-1: Per-file license identity (SPDX short identifiers)

**Statement:** Every distributable source file carries an unambiguous license identity via `SPDX-License-Identifier` (or REUSE-equivalent), using identifiers from the SPDX License List or valid `LicenseRef-*` expressions with stored license text.

**How to measure:**
- Scan all Covered Files (REUSE definition: all files except VCS metadata, zero-byte files, and explicit ignores).
- Count files missing any license tag; count files using non-SPDX-list identifiers without a matching `LICENSES/` entry.
- For files containing mixed-origin code, verify compound expressions (e.g. `Apache-2.0 AND MIT`) reflect actual content.

**Audit method:** #10 Conformance checklist (SPDX Annex E / REUSE 3.3)

**Scoring-design hook:** 6.1 dimension sub-criterion (provenance/licensing maturity ladder 0–4); 6.3 evidence grade on scan output

**Gaming vector:** Bulk-insert a generic `SPDX-License-Identifier: Apache-2.0` on every file regardless of embedded third-party snippets.

**Anti-gaming guard:** Cross-check SPDX tags against (a) grep for known third-party copyright strings, (b) `THIRD_PARTY_NOTICES` / `NOTICE` inventory, (c) vendored directories. Flag files whose tag is singular but whose content includes foreign copyright blocks.

**Evidence grade:** A (multiple Tier-1 standards converge: SPDX Annex E, REUSE 3.3, Linux Foundation best practices)

**Sources:** SPDX Annex E (2022, spec v2.3); REUSE Spec 3.3 (2024-11-14); Linux Foundation License Best Practices (2025)

---

### Criterion P22-2: Root license artifact and `LICENSES/` corpus

**Statement:** The distribution root contains a project `LICENSE` (or equivalent) stating the project's outbound license. Every non-default license referenced by any Covered File has full license text stored in a discoverable location (`LICENSES/<SPDX-ID>.txt` per REUSE, or equivalent).

**How to measure:**
- Confirm root `LICENSE` exists and matches declared project license.
- For each SPDX ID in any file tag or `THIRD_PARTY_NOTICES` entry, confirm matching full text exists in-repo.
- REUSE lint (`reuse lint`) or manual audit: zero missing license files for referenced IDs.

**Audit method:** #10 Conformance checklist; #2 Maturity-model (0 = no root LICENSE; 4 = REUSE-compliant `LICENSES/` tree)

**Scoring-design hook:** 6.1; feeds 6.2 gate evidence

**Gaming vector:** Placeholder `LICENSE` copied from template without matching actual outbound terms; empty `LICENSES/` directory.

**Anti-gaming guard:** Diff root `LICENSE` text against SPDX canonical text for declared ID; fail if hash mismatch beyond permitted variants.

**Evidence grade:** A

**Sources:** REUSE Spec 3.3 § License Files (2024-11-14); SPDX License List (spdx.org/licenses); Linux Foundation License Best Practices

---

### Criterion P22-3: Third-party attribution inventory (`NOTICE` / `THIRD_PARTY_NOTICES`)

**Statement:** All third-party components **actually redistributed** (incorporated snippets, vendored trees, or build-time-linked into shipped artifacts) appear in a machine- or human-readable attribution file (`NOTICE`, `THIRD_PARTY_NOTICES`, or REUSE `REUSE.toml` annotations plus `LICENSES/`), each entry naming component, version (if applicable), SPDX license ID, and required copyright/NOTICE text.

**How to measure:**
- Build inventory from: vendored dirs, copied code blocks, and (for wheels/sdists) declared runtime deps whose code is bundled.
- Compare against `NOTICE` / `THIRD_PARTY_NOTICES` / SBOM license section.
- For Apache-2.0 upstream components with `NOTICE` files, verify Section 4(d) text is bubbled up.

**Audit method:** #10 Conformance checklist; #3 Comparative benchmarking (CNCF / Apache exemplar bar)

**Scoring-design hook:** 6.1; **6.2 hard-gate candidate**

**Gaming vector:** Minimal one-line "uses open source" disclaimer without per-component attribution; listing PyPI deps never bundled into the artifact.

**Anti-gaming guard:** Scope rule: inventory only **shipped** components (CNCF use cases 1–3). Require at least name + SPDX ID + copyright or NOTICE excerpt per shipped component. Spot-check 3 random entries against upstream LICENSE/NOTICE.

**Evidence grade:** A (Apache 2.0 §4(d); CNCF attribution guidance; Linux Foundation)

**Sources:** Apache License 2.0 §4(c–d); CNCF Recommendations for Attribution (cncf/foundation); Apache infra licensing-howto; Linux Foundation License Best Practices

---

### Criterion P22-4: License compatibility matrix — no forbidden combinations

**Statement:** The project's outbound license is compatible with every incorporated/vendored/bundled dependency license under the rules of combination (not merely "both are OSI-approved").

**Documented high-signal incompatibilities (non-exhaustive, context-dependent):**

| Dependency license | Project outbound (typical) | Verdict | Primary authority |
|---|---|---|---|
| MIT, BSD-2/3, ISC, BSL-1.0 | Apache-2.0 / MIT / BSD | Compatible (retain notices) | FSF GPLv2-compatible list; LF best practices |
| Apache-2.0 | GPL-2.0-only | **Incompatible** | Apache GPL compatibility page; FSF GPLv2-incompatible list |
| Apache-2.0 | GPL-3.0-or-later | Compatible (combined work → GPL-3) | FSF GPLv3-compatible list; Apache GPL compatibility |
| GPL-2.0-only | MIT/Apache outbound | **Incompatible** unless entire work relicensed | Copyleft obligations (LF) |
| AGPL-3.0 | Permissive outbound | **Incompatible** for proprietary/combined permissive distribution | LF Common License Conflicts |

**How to measure:**
- Produce compatibility matrix: rows = bundled/incorporated licenses, column = project outbound license.
- Flag any cell marked incompatible; require legal review memo or architectural removal for each.
- Explicitly test the Apache-2.0 ↔ GPL-2.0-only pair (historically common footgun).

**Audit method:** #10 Conformance checklist against published compatibility lists

**Scoring-design hook:** 6.1; **6.2 hard-gate candidate** (any confirmed incompatible combination in shipped artifact)

**Gaming vector:** Declare outbound MIT while statically linking GPL-2.0-only code; ignore "only" vs "or-later" SPDX suffix distinctions.

**Anti-gaming guard:** Use exact SPDX identifiers (`GPL-2.0-only` vs `GPL-2.0-or-later`); scan object/wheel contents, not just `pyproject.toml` declared deps.

**Evidence grade:** A (FSF compatibility lists; Apache Foundation primary guidance; Linux Foundation)

**Sources:** FSF Compatible licenses wiki (Apache 2.0 listed GPLv2-incompatible, GPLv3-compatible); apache.org/licenses/GPL-compatibility.html; Linux Foundation License Best Practices § Common License Conflicts

**Contradiction surfaced:** Community matrices (e.g. commercial SCA vendors) sometimes mark Apache+GPL-2.0 differently than FSF/Apache primary sources. **Decision rule (per frame 6.5):** prefer Tier-1 FSF + Apache Foundation statements; mark vendor-only matrices as Tier-3 corroboration, not override.

---

### Criterion P22-5: Port-vs-vendor discipline

**Statement:** Third-party code enters the project through one of two disciplined paths, never ambiguously:

1. **Vendor (preferred for whole components):** Unmodified upstream tree in a dedicated directory (`vendor/`, `third_party/`, etc.) with upstream LICENSE/NOTICE preserved intact.
2. **Port/incorporate (snippets or reimplemented algorithms):** Only necessary portions extracted; per-file copyright + license statement; SPDX compound expression; pointer to upstream origin; full license text in `LICENSES/`.

**How to measure:**
- Classify each foreign-origin module: vendored | incorporated snippet | clean reimplementation.
- Vendored: directory contains upstream LICENSE; no CNCF-project copyright substituted for upstream headers.
- Incorporated: CNCF checklist items present (exact copyright reproduction, license statement, optional URL).
- Reimplementation: see P22-6.

**Audit method:** #10; #3 Comparative (CNCF use cases 1 vs 2)

**Scoring-design hook:** 6.1 maturity ladder

**Gaming vector:** Copy upstream files into `src/` without `vendor/` boundary, stripping LICENSE to "look native."

**Anti-gaming guard:** Require directory convention OR inline provenance block; git-history spot-check for bulk paste without attribution commit.

**Evidence grade:** B (CNCF Tier-2 maintainer guidance; reinforced by Apache apply-license Tier-1)

**Sources:** CNCF Recommendations for Attribution § Use cases 1–2; Apache apply-license; REUSE snippet annotations (§ In-line Snippet comments)

---

### Criterion P22-6: Honest provenance for re-implemented algorithms

**Statement:** When functionality is **re-implemented** (not vendored, not copied) based on studying an external repo, paper, or API, the project maintains a **provenance record** that: (a) names the inspiration source (URL, version/commit if known), (b) states the upstream license, (c) clarifies that implementation was written independently (no literal copy), and (d) documents any license obligations still triggered (e.g. if patent or API terms apply — outside copyright, but must not be silently ignored).

**How to measure:**
- Maintain `PROVENANCE.md` or equivalent section in docs listing re-implementations.
- Each entry: source, license, date reviewed, implementing module(s), reviewer.
- For each listed module, confirm no byte-level match to upstream beyond incidental idioms (optional similarity scan flagged for human review, not automated verdict).

**Audit method:** #10; #2 Maturity-model (0 = silent reimplementation; 4 = documented independent implementation with traceable review)

**Scoring-design hook:** 6.1; 6.4 anti-gaming (prevents "clean-room theater")

**Gaming vector:** Claim "clean room" or "reimplemented" with no documentation while retaining upstream structure/comments; use AI rewrite to strip headers and assert originality.

**Anti-gaming guard:** Provenance record is **required** whenever public research/adoption docs reference an external algorithm source. Record must predate or accompany merge. Tier-3 legal literature uniformly treats clean-room as **evidentiary process**, not a license — documentation must exist before dispute, not after.

**Evidence grade:** B for process requirement (CNCF + REUSE cover attribution of copied code; clean-room process is Tier-3 legal commentary — criterion scoped to **documentation honesty**, not legal clearance)

**Sources:** CNCF § Use case 1 (pointer to origin recommended); REUSE 3.3; C4SIF clean-room overview (Tier-3, cited for process definition only)

**Note:** Copyright protects expressive elements, not ideas/algorithms (well-established doctrine referenced in clean-room literature). A reimplementation still triggers **attribution** if any literal code was copied; it does **not** automatically inherit upstream license if truly independent — but **honest provenance** is auditable regardless of legal outcome.

---

### Criterion P22-7: Copyright-header hygiene by license family

**Statement:** File headers satisfy the **minimum notice requirements** of their declared license:

| License | Minimum header obligation |
|---|---|
| MIT / BSD-2/3 / ISC | Copyright notice + permission text retained in distributions |
| Apache-2.0 | Copyright/patent/trademark notices retained; boilerplate header recommended |
| BSL-1.0 | **Full license statement** including copyright notices and disclaimer in all copies (no standard short header exists per SPDX) |
| GPL/LGPL | Copyright + license notice; source-offer obligations if copyleft triggered |

**How to measure:**
- Sample N files per license family; verify required elements present.
- BSL-1.0 files: confirm full BSL text or valid reference + included copy in `LICENSES/BSL-1.0.txt`.
- Modified files from third parties: "prominent notices" of changes (Apache §4(b)).

**Audit method:** #10 Conformance checklist per license text

**Scoring-design hook:** 6.1

**Gaming vector:** BSL-covered code with only `SPDX-License-Identifier: BSL-1.0` and no full statement anywhere in distribution.

**Anti-gaming guard:** BSL-specific sub-check: full statement present in at least one mandatory location per REUSE/SPDX practice.

**Evidence grade:** A (SPDX license texts; Apache §4(b–c); BSL-1.0 SPDX entry)

**Sources:** spdx.org/licenses/MIT.html; spdx.org/licenses/BSL-1.0.html; Apache License 2.0 §4(b–c)

---

### Criterion P22-8: Apache NOTICE propagation (conditional hard check)

**Statement:** If any bundled component is Apache-2.0-licensed **and** includes a `NOTICE` file, all notices pertaining to the redistributed portion appear in the project's `NOTICE` (or `THIRD_PARTY_NOTICES`) per Section 4(d).

**How to measure:**
- For each vendored Apache-2.0 component: diff upstream NOTICE against project NOTICE.
- Confirm no required attribution was dropped when trimming unused modules.

**Audit method:** #10

**Scoring-design hook:** **6.2 hard-gate candidate** (Apache §4(d) is a legal condition of redistribution)

**Gaming vector:** Strip upstream NOTICE to reduce file size; assume LICENSE alone suffices.

**Anti-gaming guard:** Automated NOTICE merge check in release checklist; Apache infra explicitly requires bubbling NOTICE contents.

**Evidence grade:** A

**Sources:** Apache License 2.0 §4(d); Apache infra licensing-howto; CNCF § Apache-2.0 and NOTICE files

---

### Criterion P22-9: Outbound license matches contribution policy

**Statement:** Project `LICENSE`, package metadata (`pyproject.toml` `license` field / classifier), and per-file SPDX tags agree on a single outbound license expression (or documented dual-licensing with selector).

**How to measure:**
- Compare PyPI/classifier license, root LICENSE, and modal file SPDX ID.
- Flag mismatches (e.g. metadata says MIT, files say Apache-2.0).

**Audit method:** #10; supports P01 release-readiness overlap at audit stage only

**Scoring-design hook:** 6.1

**Gaming vector:** PyPI metadata says permissive license while shipping copyleft-derived combined work.

**Anti-gaming guard:** Treat metadata mismatch as automatic fail pending resolution.

**Evidence grade:** B (Linux Foundation + SPDX practice)

**Sources:** Linux Foundation License Best Practices; SPDX Annex E

---

## 3. External Benchmark / Exemplar Bar

Professional OSS projects that set the provenance/licensing bar:

| Practice | Exemplar bar | Source tier |
|---|---|---|
| Per-file SPDX tags | Linux Foundation projects: "Add to every file" | Tier 2 (LF) |
| `LICENSES/` directory with full texts | REUSE 3.3 mandatory; CNCF recommends for non-Apache licenses | Tier 1 (REUSE) / Tier 2 (CNCF) |
| NOTICE file discipline | Apache Software Foundation: every distribution includes LICENSE + NOTICE | Tier 1 (Apache apply-license, infra howto) |
| Vendored components unmodified | CNCF use case 2: preserve upstream LICENSE/NOTICE in vendor dir | Tier 2 (CNCF) |
| Incorporated snippets annotated | CNCF use case 1: exact copyright + license + optional URL in file | Tier 2 (CNCF) |
| Compatibility caution Apache↔GPL | Apache Foundation publishes explicit one-way compatibility statement | Tier 1 (Apache) |
| BSL full-text requirement | SPDX notes no standard header; full statement required | Tier 1 (SPDX) |

**Maturity ladder (proposed 0–4 for synthesis):**

| Level | Descriptor |
|---|---|
| 0 | No root LICENSE; foreign code present without attribution |
| 1 | Root LICENSE only; no per-file IDs; no third-party inventory |
| 2 | SPDX tags on most files; `THIRD_PARTY_NOTICES` exists but incomplete vs shipped set |
| 3 | REUSE- or CNCF-aligned: `LICENSES/`, complete NOTICE, port/vendor rules documented |
| 4 | Level 3 + provenance log for re-implementations + release checklist gate + compatibility matrix archived per release |

---

## 4. Recommended Weight & Hard Gates

### Dimension weight (feeds 6.1)

Recommend **provenance/licensing** receive **moderate weight** in the composite (suggested band **8–12%** of total — synthesis must justify exact number with other personas). Rationale: licensing failure can invalidate redistribution regardless of quality scores; however most criteria are binary/checklist rather than gradational quality, so weight should not dominate extraction-quality dimensions.

### Hard gates (feeds 6.2)

Recommend these **non-compensatory gates** (any fail → overall audit fail regardless of weighted score):

| Gate ID | Condition | Rationale |
|---|---|---|
| **G-LIC-1** | Confirmed **incompatible license combination** in a shipped artifact (e.g. Apache-2.0 project statically bundling GPL-2.0-only code without GPL compliance) | Copyleft/compatibility violations cannot be offset by high test coverage |
| **G-LIC-2** | **Missing required attribution** for a redistributed third-party component (MIT/BSD/Apache NOTICE obligation unmet) | Direct license breach; LF and Apache treat attribution as non-optional |
| **G-LIC-3** | **BSL-1.0 or similar full-notice license** distributed without required license statement | BSL explicitly requires entire statement in all copies |
| **G-LIC-4** | **Outbound license metadata contradicts** actual bundled content (declared permissive, ships copyleft without compliance) | Consumer-facing misrepresentation |

**Not recommended as hard gate (weighted sub-criterion instead):**
- Incomplete but non-empty provenance docs for re-implementations (penalize maturity level, require remediation plan).
- Missing SPDX tag on non-code files (documentation/data) where REUSE allows `REUSE.toml` aggregation.

### Confidence propagation (6.3)

Compatibility findings based on FSF + Apache primary sources: **evidence grade A, confidence high**. Clean-room/reimplementation honesty: **grade B–C, confidence medium** (legal process varies by jurisdiction; audit checks documentation existence, not legal clearance).

### Anti-gaming summary (6.4)

Every criterion above includes a gaming vector. Cross-cutting guard: **attribution inventory must be derived from artifact contents**, not from lockfiles alone.

---

## 5. Sources

| # | Source | Tier | URL | Date/version |
|---|---|---|---|---|
| 1 | SPDX License List | 1 | https://spdx.org/licenses/ | Current (ISO/IEC 5962:2021 ecosystem) |
| 2 | SPDX Specification Annex E — short identifiers in source files | 1 | https://spdx.github.io/spdx-spec/v2.3/using-SPDX-short-identifiers-in-source-files/ | Spec v2.3 (2022) |
| 3 | REUSE Specification 3.3 | 1 | https://reuse.software/spec-3.3/ | 2024-11-14 |
| 4 | Apache License, Version 2.0 (full text) | 1 | https://www.apache.org/licenses/LICENSE-2.0 | 2004 (stable) |
| 5 | Apache — Applying the ALv2 | 1 | https://www.apache.org/legal/apply-license | Current ASF policy |
| 6 | Apache — GPL compatibility | 1 | https://www.apache.org/licenses/GPL-compatibility.html | Current ASF statement |
| 7 | Apache Infrastructure — LICENSE and NOTICE assembly | 2 | https://infra.apache.org/licensing-howto.html | Current ASF infra guidance |
| 8 | FSF — Compatible licenses (GPLv3 wiki archive) | 1 | https://gplv3.fsf.org/wiki/index.php/Compatible_licenses | Lists Apache 2.0 GPLv2-incompatible / GPLv3-compatible |
| 9 | Linux Foundation — Open Source License Best Practices | 2 | https://www.linuxfoundation.org/licensebestpractices | © 2025 LF (CC-BY-4.0) |
| 10 | CNCF — Recommendations for Attribution Notices | 2 | https://github.com/cncf/foundation/blob/main/policies-guidance/recommendations-for-attribution.md | Current CNCF guidance |
| 11 | SPDX — MIT License text | 1 | https://spdx.org/licenses/MIT.html | Canonical |
| 12 | SPDX — BSL-1.0 License text | 1 | https://spdx.org/licenses/BSL-1.0.html | Released 2003-08-17 |

**Tier-3 (context only, not load-bearing alone):** C4SIF clean-room overview; commercial compatibility matrices — used for contradiction surfacing only.

**Source count (Tier 1–2 load-bearing):** **12 distinct primary/strong-secondary sources** (floor ≥3 satisfied).

---

## 6. Overlap Statement

This persona **did not**:

- Open, inspect, or score whisker production code (`packages/whisker/src/**`).
- Cite whisker `file:line` or reach any whisker verdict.
- Clone, fork, or copy third-party code into this repository.
- Duplicate **P03** (dependency/supply-chain hygiene: SBOM, SLSA, vuln scanning, pinning policy).
- Re-litigate the **`langextract/`** swarm adoption verdict (Apache-2.0 attribution for the DP port).
- Perform dependency-tree or SBOM audits (P03 scope).

This persona **did** research external provenance, licensing, attribution, port-vs-vendor, and re-implementation documentation standards, producing audit criteria and candidate hard gates for downstream synthesis.

**Overlap boundary confirmed:** Prior folder avoided = **`p03-dependency-supply-chain`** (supply-chain integrity) and **`langextract/`** (adoption verdict). Unique niche = **license/attribution/fork hygiene** (frame section 8, single-owner dimension P22).

---

## Strongest Criterion (persona self-assessment)

**Strongest criterion: P22-4 (License compatibility matrix — no forbidden combinations)**, backed by converging Tier-1 authorities (FSF compatibility lists + Apache Foundation GPL-compatibility statement + Linux Foundation conflict guidance). It is objectively checkable, has the highest severity when violated (legal redistribution block), and directly supports hard gate **G-LIC-1**. Unlike documentation-quality criteria, compatibility failures cannot be cured by better tests or docs without changing what is shipped.
