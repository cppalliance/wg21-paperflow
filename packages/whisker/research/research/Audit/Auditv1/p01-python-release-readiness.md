# P01 — Python Packaging & Release-Readiness Auditor

**Persona:** 1 of 30 (Cluster A: Professional Python package & release readiness)  
**Date:** 2026-07-18  
**Scope:** External method and standards only. No whisker production-code inspection.

---

## 1. Question restated

What external bar defines a **professional, releasable** Python library, and how should that bar be turned into **repeatable audit criteria** for `packages/whisker`? This persona covers: `pyproject.toml` conformance (PEP 517/518/621/639), build-backend selection, wheel/sdist correctness, semantic versioning and release cadence, changelog discipline, console-script/entry-point hygiene, Python-version support policy, and packaging metadata completeness judged against PyPA authoritative guidance and serious extraction-tool exemplars (Docling, LangExtract).

---

## 2. Proposed audit criteria

Each criterion is scored on a **0–4 maturity ladder** unless marked as a **hard gate** (pass/fail). Evidence grades follow `00-FRAME.md` §6.3: **A** = multiple Tier-1 corroborating; **B** = single Tier-1 or converging Tier-2; **C** = Tier-3 only or contested; **D** = Tier-4/speculative.

### Criterion R1 — PEP 517/518 build-system declaration

| Field | Value |
|---|---|
| **Criterion** | `[build-system]` table present with pinned `requires` and explicit `build-backend` per PEP 517/518. |
| **How to measure** | Parse `pyproject.toml`: verify `requires` lists backend with minimum version (e.g. `setuptools >= 61.0`, `hatchling`); verify `build-backend` matches backend docs. Run `python -m build --no-isolation` only after confirming isolation path works in CI. |
| **Audit method** | Conformance checklist (§5.1) |
| **Scoring hook** | §6.1 dimension: release-readiness; §6.2 candidate gate if absent (unbuildable = unreleasable) |
| **Gaming vector** | Declaring a backend name without a working build (empty `requires`, wrong entry point). |
| **Anti-gaming guard** | CI must run `python -m build` in clean env and fail on error; artifact must contain importable package namespace. |
| **Evidence grade** | **A** |
| **Sources** | PEP 517 (2017), PEP 518 (2016), PyPA *Writing your pyproject.toml* (2025–2026) |

### Criterion R2 — PEP 621 `[project]` static metadata completeness

| Field | Value |
|---|---|
| **Criterion** | Required PEP 621 fields populated: `name`, `version` (or declared `dynamic`), `description`, `readme`, `requires-python`, `authors` or `maintainers`, `license` (PEP 639 string), `license-files`, and `[project.urls]` with at least Repository + Changelog. |
| **How to measure** | Checklist against PyPA pyproject.toml spec and packaging tutorial. Verify `dynamic` list matches fields actually computed at build time. Run `twine check --strict dist/*` and inspect PKG-INFO/METADATA for field parity. |
| **Audit method** | Conformance checklist + maturity model (§5.1, §5.2) |
| **Scoring hook** | §6.1 release-readiness; §6.3 evidence grade propagates from metadata validation |
| **Gaming vector** | Placeholder description/readme; `dynamic = ["version"]` without reproducible version source; missing `requires-python`. |
| **Anti-gaming guard** | Require `twine check --strict` in CI; spot-install wheel in fresh venv and import top-level package; compare PKG-INFO to committed `pyproject.toml`. |
| **Evidence grade** | **A** |
| **Sources** | PEP 621 (2020), PyPA pyproject.toml specification (updated Jan 2026), PyPA core metadata spec (Metadata 2.4) |

### Criterion R3 — PEP 639 license clarity (hard gate candidate)

| Field | Value |
|---|---|
| **Criterion** | `license` uses SPDX license expression string; `license-files` globs include actual LICENSE file(s); no reliance on deprecated `License ::` Trove classifiers as primary license signal. |
| **How to measure** | Verify SPDX expression parses (single identifier or compound); confirm LICENSE file exists and is included in wheel/sdist via `unzip -l` / tar listing. Check METADATA for `License-Expression` and `License-File` fields. |
| **Audit method** | Conformance checklist (§5.1) + provenance audit overlap (§5.10) |
| **Scoring hook** | **§6.2 hard gate**: missing or incompatible license metadata fails regardless of composite score |
| **Gaming vector** | SPDX string present but license file omitted from artifact; classifier-only licensing. |
| **Anti-gaming guard** | Automated check: LICENSE path in `license-files` must appear in built wheel; legal review for compound expressions. |
| **Evidence grade** | **A** |
| **Sources** | PEP 639 (Final, Dec 2024), PyPA core metadata §License-Expression (Metadata 2.4) |

### Criterion R4 — Wheel + sdist build correctness

| Field | Value |
|---|---|
| **Criterion** | Clean build produces **both** sdist and wheel; wheel installs and imports; sdist rebuilds identical metadata (non-dynamic fields match). |
| **How to measure** | `python -m build` → `twine check --strict dist/*` → `pip install dist/*.whl` in fresh venv → import smoke test. For libraries with CLI, invoke installed console script. Compare wheel tag to `requires-python` (no stale `py2.py3` universal tag when py2 dropped). |
| **Audit method** | Reproducibility replay (§5.8) + conformance checklist |
| **Scoring hook** | §6.1 release-readiness; §6.2 gate if wheel fails install/import |
| **Gaming vector** | Publishing wheel-only with broken sdist; universal wheel tag after py3-only declaration. |
| **Anti-gaming guard** | CI matrix builds from sdist (`pip install dist/*.tar.gz`) and from wheel; fail on tag/classifier mismatch per PyPA dropping-Python guide. |
| **Evidence grade** | **A** |
| **Sources** | PyPA packaging tutorial, PyPA distribution formats guide, twine docs (`twine check --strict`), PyPA dropping older Python versions |

### Criterion R5 — `requires-python` support policy

| Field | Value |
|---|---|
| **Criterion** | Explicit lower bound aligned with tested matrix; Python version classifiers match bound; drops are semver-minor/major events with changelog entry; **no upper-bound** caps unless extraordinary justification documented. |
| **How to measure** | Compare `requires-python`, Trove `Programming Language :: Python :: 3.x` classifiers, and CI test matrix. Verify pip resolver behavior on unsupported Python fails predictably. |
| **Audit method** | Conformance checklist + maturity model |
| **Scoring hook** | §6.1 release-readiness |
| **Gaming vector** | Classifiers claim 3.10–3.13 support but CI tests only 3.12; silent drop without release note. |
| **Anti-gaming guard** | CI matrix must be the superset of declared support; dropping a version requires dedicated release + CHANGELOG + `requires-python` bump in same commit. |
| **Evidence grade** | **B** (PyPA guide explicit; upper-bound warning is guidance not RFC MUST) |
| **Sources** | PyPA *Dropping support for older Python versions*, PEP 621 `requires-python`, PyPA versioning discussion |

**Contradiction surfaced:** PyPA warns against upper bounds on `requires-python` (resolver conflicts), yet some enterprises pin `<4.0` defensively. **Resolution rule:** prefer PyPA guidance (no upper bound) unless documented downstream packaging need; mark contested installs as lower confidence.

### Criterion R6 — Semantic versioning contract

| Field | Value |
|---|---|
| **Criterion** | Published versioning policy referencing SemVer 2.0.0; version in artifacts immutable once published; breaking API changes increment MAJOR (or documented pre-1.0 exception); deprecation cycle documented for public API. |
| **How to measure** | README/CHANGELOG states SemVer adherence; git tags match `project.version`; PyPI history shows no re-uploaded same version; deprecation notices appear ≥1 minor before removal. |
| **Audit method** | Maturity model (§5.2) + comparative benchmarking |
| **Scoring hook** | §6.1 release-readiness; §6.4 anti-gaming (version policy must be operational, not decorative) |
| **Gaming vector** | "We use SemVer" in README while shipping breaking changes in PATCH; re-tagging/re-uploading (PyPI yank abuse). |
| **Anti-gaming guard** | Compare CHANGELOG "Breaking" sections to version bump level; verify tag immutability; use PyPI yank only with documented incident response. |
| **Evidence grade** | **B** |
| **Sources** | semver.org 2.0.0, PyPA versioning discussion (2024–2026) |

**Contradiction surfaced:** semver.org requires strict MAJOR bump for any incompatible public API change; PyPA notes most Python projects use "SemVer-like" behavior and may reserve MAJOR bumps for large incompatibility. **Resolution rule:** audit requires **declared policy** + **internal consistency**, not strict semver.org clause-by-clause unless project claims strict compliance; prefer reproducible tag↔version mapping over doctrinal purity.

### Criterion R7 — Changelog discipline (Keep a Changelog)

| Field | Value |
|---|---|
| **Criterion** | `CHANGELOG.md` (or equivalent) follows Keep a Changelog 1.1.0 structure: `[Unreleased]` section, reverse-chronological versions, grouped change types (Added/Changed/Fixed/Deprecated/Removed/Security), dates per release, explicit SemVer link. |
| **How to measure** | Structural lint: every published PyPI version has changelog section; breaking changes labeled; `[project.urls] Changelog` points to file; release tag date ≈ changelog date. |
| **Audit method** | Documentation-completeness audit (§5.9) applied to release artifacts |
| **Scoring hook** | §6.1 release-readiness; §6.4 anti-gaming |
| **Gaming vector** | Empty "Updated dependencies" only entries; GitHub Releases as sole changelog (non-portable, Keep a Changelog discourages). |
| **Anti-gaming guard** | Require machine-checkable: version in CHANGELOG must match latest tag; each release section must contain ≥1 categorized bullet; `[Unreleased]` must not be empty >N commits on main (threshold set by synthesis). |
| **Evidence grade** | **B** |
| **Sources** | keepachangelog.com 1.1.0, PyPA versioning discussion, pyOpenSci CHANGELOG guide (Tier 3 corroboration) |

### Criterion R8 — Console scripts and entry-point hygiene

| Field | Value |
|---|---|
| **Criterion** | CLI exposed via `[project.scripts]` (maps to `console_scripts`); object refs are valid `module:attr` import paths; no duplicate `[project.entry-points.console_scripts]`; names stable and case-safe; GUI tools use `[project.gui-scripts]` on Windows when needed. |
| **How to measure** | Parse entry points from installed `.dist-info/entry_points.txt`; run each console script `--help` (or documented no-arg behavior); verify `sys.exit` contract (int or None). |
| **Audit method** | Conformance checklist |
| **Scoring hook** | §6.1 release-readiness (operator surface depends on this) |
| **Gaming vector** | Script entry points to private module path that works in editable install but not wheel. |
| **Anti-gaming guard** | Test only **installed wheel**, not editable install; verify entry point target importable from wheel contents alone. |
| **Evidence grade** | **A** |
| **Sources** | PEP 621 entry points, PyPA entry points specification (updated Jan 2026), PyPA *Creating and packaging command-line tools* |

### Criterion R9 — Release cadence and automated publishing pipeline

| Field | Value |
|---|---|
| **Criterion** | Documented release process; tag-triggered CI builds artifacts once, publishes via Trusted Publishing (OIDC) or equivalent short-lived credentials; TestPyPI smoke before PyPI for pre-1.0 or high-risk releases. |
| **How to measure** | Inspect CI workflow: `python -m build`, artifact upload, `twine check --strict`, tag guard for production index, `id-token: write` for PyPI trusted publishing; manual approval on production environment. |
| **Audit method** | Maturity model + comparative benchmarking (§5.3) |
| **Scoring hook** | §6.1 release-readiness; §6.2 gate for long-lived PyPI tokens in CI secrets (supply-chain) |
| **Gaming vector** | Manual `twine upload` from maintainer laptop only (non-reproducible); building on tag but not from tagged commit. |
| **Anti-gaming guard** | Require CI-built artifacts are the only publish path; GHA environment protection on `pypi`; attestations (PEP 740) when available. |
| **Evidence grade** | **B** |
| **Sources** | PyPA GitHub Actions publishing guide (2025–2026), twine docs, pypa/gh-action-pypi-publish |

### Criterion R10 — Optional extras and dependency declaration hygiene

| Field | Value |
|---|---|
| **Criterion** | Runtime deps in `[project.dependencies]`; heavy/LLM/vision stacks in `[project.optional-dependencies]` extras with documented names; no undeclared transitive reliance; version specifiers follow PEP 508 without overly tight pins in library deps. |
| **How to measure** | `pip install .` vs `pip install .[extra]` matrix; import-check optional modules; compare lock/constraints if monorepo workspace documents them separately. |
| **Audit method** | Conformance checklist + maturity model |
| **Scoring hook** | §6.1 release-readiness (feeds P03 supply-chain persona, not duplicated here) |
| **Gaming vector** | Core import pulls heavy deps not listed in `[project.dependencies]`; extras that are required for documented default workflow. |
| **Anti-gaming guard** | Document "minimal install" vs "full install" in README; CI job tests minimal extra-free install path. |
| **Evidence grade** | **B** |
| **Sources** | PEP 621 optional-dependencies, PyPA dependency specifiers, PyPA writing pyproject.toml |

### Criterion R11 — Src layout and import-name correctness (PEP 794)

| Field | Value |
|---|---|
| **Criterion** | Package uses `src/` layout (recommended) or documented flat layout; build backend packages correct import name; PEP 794 `import-names` / `import-namespaces` set when distribution name ≠ import name. |
| **How to measure** | Verify wheel contains `whisker/` (or declared name) under site-packages; `import whisker` after install; no accidental inclusion of tests/docs in wheel top-level. |
| **Audit method** | Conformance checklist |
| **Scoring hook** | §6.1 release-readiness |
| **Gaming vector** | Tests pass via editable path injection masking missing packaged modules. |
| **Anti-gaming guard** | CI test job installs built wheel before test collection (or dedicated packaging job). |
| **Evidence grade** | **B** |
| **Sources** | PyPA src vs flat layout discussion, PyPA pyproject.toml spec (PEP 794, Oct 2025) |

---

## 3. External benchmark / exemplar bar

### Tier-1/Tier-2 exemplar signals (observed from public docs, not code audit)

| Practice | Docling (IBM) | LangExtract (Google) | PyPA canonical bar |
|---|---|---|---|
| `pyproject.toml` as source of truth | Yes; modular `docling-slim` + meta-package split (2026) | Yes; hatch/setuptools in public repo | Mandatory `[build-system]` + `[project]` |
| Release cadence | ~195 releases; automated version comments in pyproject | Fewer releases; early-stage | Tag-driven CI recommended |
| Changelog URL in metadata | `[project.urls] changelog` → CHANGELOG.md | Release notes in GitHub | Keep a Changelog + SemVer link |
| `requires-python` | `>=3.10,<4.0` with explicit drop notes in README | Follows modern 3.10+ ecosystem | Lower bound required; avoid upper bound |
| Console scripts | CLI in `docling-slim` wheel after modular split | Public CLI examples | `[project.scripts]` → `console_scripts` |
| CI publish | GitHub Actions + bot releases (Tier 2) | Google release process opaque | Trusted Publishing preferred |

**Professional bar (synthesis-level):** A releasable extraction-QA library matches **PyPA conformance** (R1–R4, R8) as floor, **Docling-grade** metadata richness (classifiers, urls, changelog linkage, explicit Python floor) as target, and **automated tag→build→check→publish** (R9) as release maturity. Pre-1.0 projects may score lower on R6/R7 if policy is documented, but not on R3/R4 (license + build must pass).

**Where exemplars diverge (do not cargo-cult):** Docling's `<4.0` upper bound and dual-package split serve IBM scale, not required for whisker monorepo workspace consumption. LangExtract's cloud-first defaults are irrelevant to packaging shape; only its eval/release artifact discipline transfers (handled by P26).

---

## 4. Recommended weight & gate recommendation

| Recommendation | Rationale |
|---|---|
| **Dimension weight: 12%** of composite (within release-readiness cluster shared with P02 API contract and P04 CI/test) | Packaging is necessary but not sufficient for "professional-grade" whisker; hybrid architecture and eval quality dominate. Weight cites PyPA: metadata correctness is table stakes, not differentiator. |
| **Hard gates (conjunctive): R3, R4** | **R3:** PEP 639 license failure is legal/redistribution risk (PEP 639 goals). **R4:** Non-installable wheel/sdist voids "release-ready" claim regardless of doc/score quality. |
| **Soft gates (cap score at level 2): R1, R2, R8** if any fail | Missing build-system, incomplete metadata, or broken CLI block professional release but may be acceptable for private monorepo-only consumption; synthesis should record "workspace-only" vs "PyPI-ready" modes. |
| **Evidence propagation** | Dimension composite inherits weakest grade among R1–R4 load-bearing criteria (likely **A** if CI enforced). |
| **Contested criteria discount** | R5 upper-bound policy and R6 strict-SemVer vs SemVer-like: apply §6.5 disagreement rule; reduce weight 20% on R6 if policy ambiguous. |

---

## 5. Sources

### Tier 1 — Authoritative / primary

| ID | Source | URL | Date/version |
|---|---|---|---|
| S1 | PEP 517 — Build system interface | https://peps.python.org/pep-0517/ | Final, 2017 |
| S2 | PEP 518 — Build system requirements | https://peps.python.org/pep-0518/ | Final, 2016 |
| S3 | PEP 621 — Project metadata in pyproject.toml | https://peps.python.org/pep-0621/ | Final, 2020 |
| S4 | PEP 639 — License clarity metadata | https://peps.python.org/pep-0639/ | Final, Dec 2024 |
| S5 | SemVer 2.0.0 specification | https://semver.org/ | 2.0.0 |
| S6 | Keep a Changelog 1.1.0 | https://keepachangelog.com/en/1.1.0/ | 1.1.0 |
| S7 | PyPA pyproject.toml specification | https://packaging.python.org/en/latest/specifications/pyproject-toml/ | Updated Jan 2026 |
| S8 | PyPA core metadata specifications | https://packaging.python.org/en/latest/specifications/core-metadata/ | Metadata 2.4 |
| S9 | PyPA entry points specification | https://packaging.python.org/en/latest/specifications/entry-points/ | Updated Jan 2026 |

### Tier 2 — Strong secondary

| ID | Source | URL | Date/version |
|---|---|---|---|
| S10 | PyPA — Writing your pyproject.toml | https://packaging.python.org/en/latest/guides/writing-pyproject-toml/ | 2025–2026 |
| S11 | PyPA — Packaging Python Projects tutorial | https://packaging.python.org/en/latest/tutorials/packaging-projects/ | 2025–2026 |
| S12 | PyPA — Dropping support for older Python versions | https://packaging.python.org/en/latest/guides/dropping-older-python-versions/ | 2025–2026 |
| S13 | PyPA — Versioning discussion | https://packaging.python.org/en/latest/discussions/versioning/ | 2025–2026 |
| S14 | PyPA — Publishing with GitHub Actions (Trusted Publishing) | https://packaging.python.org/en/latest/guides/publishing-package-distribution-releases-using-github-actions-ci-cd-workflows/ | 2025–2026 |
| S15 | twine documentation (`twine check --strict`) | https://twine.readthedocs.io/en/stable/ | 6.2.0 |
| S16 | Docling `pyproject.toml` (public) | https://github.com/docling-project/docling/blob/main/pyproject.toml | v2.106.0+, Apr 2026 |
| S17 | Docling CHANGELOG (linked from project.urls) | https://github.com/docling-project/docling/blob/main/CHANGELOG.md | ongoing |

### Tier 3 — Contextual (corroboration only)

| ID | Source | URL |
|---|---|---|
| S18 | pyOpenSci CHANGELOG guide | https://www.pyopensci.org/python-package-guide/documentation/repository-files/changelog-file.html |

**Source count:** 9 Tier-1 + 8 Tier-2 = **17 distinct Tier 1–2 sources** (floor ≥3 satisfied).

---

## 6. Overlap statement

This persona researched **external Python packaging and release-readiness standards only**. It did **not** open whisker production code, cite whisker `file:line`, score whisker, clone/fork/copy code, or duplicate:

- **`buildvsbuy/`** — library-choice decisions for metric mechanisms (not packaging standards).
- **`persona/` / `llm-stack/`** — prior code-level whisker audits.
- **`langextract/`** — algorithm adoption verdict (P26 handles LangExtract as exemplar separately).
- **`redteam/`** — converter defect reports.

Boundary held: **packaging-standard criteria and external bar**, handed to synthesis as rubric inputs for the release-readiness dimension.
