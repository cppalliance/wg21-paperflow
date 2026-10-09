# P02 — Public API & Contract-Design Researcher

**Persona:** 2 (Cluster A — Professional Python package & release readiness)  
**Date:** 2026-07-18  
**Stage:** Internet-research only. No whisker production-code inspection. No whisker verdict.

---

## 1. Question restated

What external standard defines a **professional, stable, typed Python library public API contract** suitable for a hybrid WG21 extraction-QA package: explicit public surface (`__all__`, re-export discipline), typing distribution (`py.typed`, PEP 561), versioning and backward-compat guarantees (SemVer + documented exceptions), deprecation lifecycle, and the **“library returns data; caller persists”** separation-of-concerns boundary? What audit criteria, anti-gaming guards, evidence grades, and weight/gate advice should the synthesis embed in the release-readiness dimension?

---

## 2. Proposed audit criteria

Each criterion feeds **scoring-design section 6** (weighted composite, hard gates, evidence grades, anti-gaming). Audit methods reference `00-FRAME.md` section 5.

### Criterion 2.1 — Explicit public symbol registry

| Field | Content |
|---|---|
| **Criterion** | Every importable package/module that users are expected to call exposes a **statically analyzable** public symbol list: module-level `__all__` (or package-root aggregation), underscore-prefix for internals, and redundant re-export form `from .sub import X as X` for intentional facade exports. |
| **How to measure** | (Later code stage) Parse top-level `__init__.py` and documented entry modules; verify `__all__` is a literal list/tuple (per typing spec static rules), alphabetically maintained, covers all documented public names, and no `_`-prefixed symbol appears in `__all__`. Cross-check docs/API index against `__all__`. Run `griffe`/`import-linter`-style static check if configured. |
| **Audit method** | Conformance checklist + documentation-completeness audit |
| **Scoring hook** | 6.1 release-readiness sub-criterion; 6.4 anti-gaming |
| **Gaming vector** | Empty or stale `__all__` while docs advertise a wider surface; dynamic `__all__` built at runtime to satisfy grep without static checker support. |
| **Anti-gaming guard** | Require literal `__all__` per typing spec; docs must link to generated API reference derived from the same symbol set; **contest**: add a test that imports each name in `__all__` and asserts it resolves without importing private siblings. |
| **Evidence grade** | **A** (PEP 561 typing spec “Library interface” + Scientific Python Development Guide exports pattern converge) |
| **Sources** | [T1] typing.python.org distributing spec §“Library interface”; [T2] Scientific Python Development Guide — Exports |

---

### Criterion 2.2 — Typed package distribution (`py.typed`)

| Field | Content |
|---|---|
| **Criterion** | The installable distribution ships **`py.typed`** in every typed package root (PEP 561), recursively covering subpackages users import; public API symbols carry inline annotations or `.pyi` stubs; no `partial` marker unless documented incomplete typing with tracked gap list. |
| **How to measure** | Inspect wheel/sdist (later stage): `py.typed` present at package root(s) named in docs. Run `mypy`/`pyright` in strict mode against a **consumer stub project** that imports only public names. Count public functions lacking annotations. |
| **Audit method** | Conformance checklist (PEP 561) |
| **Scoring hook** | 6.1 release-readiness; candidate **hard gate** if project claims “typed API” in README/CLAUDE.md |
| **Gaming vector** | `py.typed` present but public callables typed `Any`; typing limited to internals while docs show typed public examples. |
| **Anti-gaming guard** | Consumer-project typecheck must pass on **documented** entry points only; gate fails if >0 undocumented `# type: ignore` on public signatures; Google style rule: “at least annotate your public APIs.” |
| **Evidence grade** | **A** (PEP 561 MUST + typing spec + Google public-API typing rule) |
| **Sources** | [T1] PEP 561; [T1] typing.python.org distributing spec; [T2] Google Python Style Guide §3.19 |

---

### Criterion 2.3 — Declared versioning policy aligned to public API

| Field | Content |
|---|---|
| **Criterion** | Project publishes a **written public-API definition** and versioning scheme: either strict SemVer (clauses 1–8) with explicit public API inventory, or a documented “loose SemVer” / CalVer deviation (NumPy-style) listing what semver bumps mean in practice. Version in metadata matches tagged releases; 0.y.z treated as unstable per SemVer. |
| **How to measure** | Read `CHANGELOG`, README, or `VERSIONING.md`; verify scheme named; map recent release notes to semver bump rationale; confirm PyPA-valid version strings. |
| **Audit method** | Conformance checklist + comparative benchmarking (exemplar policies) |
| **Scoring hook** | 6.1 release-readiness; 6.6 score uncertainty when policy absent |
| **Gaming vector** | “We use SemVer” with no definition of public API; patch releases containing signature changes; perpetual 0.x to evade stability promises. |
| **Anti-gaming guard** | Require **linked** public API section; retroactive semver audit of last N releases against declared API list; flag undeclared breaking changes as automatic gate fail. |
| **Evidence grade** | **A** (semver.org declares API-first versioning; PyPA versioning discussion documents maintainer obligation and known exceptions) |
| **Sources** | [T1] semver.org 2.0.0; [T2] PyPA Packaging User Guide — Versioning discussion |

**Contradiction surfaced:** SemVer promises backward-compatible patch releases ([T1] semver.org). **Hyrum’s Law** states all observable behavior becomes a dependency ([T2] hyrumslaw.com; [T3] Hynek — SemVer will not save you). **PyPA** notes most Python projects do not strictly follow SemVer ([T2] PyPA versioning). **Audit rule:** treat semver as **intent communication**, not proof of compatibility; require changelog + API inventory and downgrade confidence when only semver badges exist.

---

### Criterion 2.4 — Deprecation and removal lifecycle

| Field | Content |
|---|---|
| **Criterion** | Deprecated public symbols follow a **documented multi-release path**: runtime `DeprecationWarning` (or `@warnings.deprecated` / PEP 702), typeshed-style static deprecation for typed APIs, docs updated at deprecation time, removal only after stated interval. Soft deprecation distinguished from hard deprecation (PEP 387). |
| **How to measure** | Inventory `@deprecated` / `warnings.warn(..., DeprecationWarning)` on public symbols; verify docs “Deprecated” section; measure releases between deprecation and removal against stated policy (PEP 387: ≥2 minor versions, prefer ~5 years for hard removal). |
| **Audit method** | Conformance checklist (PEP 387, PEP 702) + maturity model (0=no policy … 4=automated CI deprecation tests) |
| **Scoring hook** | 6.1 release-readiness; 6.4 anti-gaming |
| **Gaming vector** | Docs-only deprecation without warnings; silent removal; deprecation of private `_` names only (cosmetic policy). |
| **Anti-gaming guard** | CI runs test suite with `warnings.defaultaction=error` for `DeprecationWarning` on **public** code paths; type checker deprecation mode enabled in CI for library’s own tests. |
| **Evidence grade** | **A** (PEP 387 + PEP 702; SemVer FAQ on deprecating in minor before major removal) |
| **Sources** | [T1] PEP 387; [T1] PEP 702; [T1] semver.org FAQ “How should I handle deprecating functionality?” |

**Contradiction surfaced:** SemVer FAQ suggests **one minor release** with deprecation before major removal ([T1] semver.org). PEP 387 requires **≥2 consecutive releases** with warning and prefers **~5 years** before removal ([T1] PEP 387). **Audit rule:** for libraries claiming production readiness, score against **PEP 387** (stricter); record SemVer FAQ as lower-bound only if explicitly chosen in VERSIONING.md.

---

### Criterion 2.5 — Side-effect boundary (“returns data, caller persists”)

| Field | Content |
|---|---|
| **Criterion** | **Library-layer** functions (importable API used by integrators) are **pure or return structured data**; filesystem, network, process-global mutation, and ambient environment reads are confined to CLI/adapters explicitly documented as imperative shell. Domain/core QA logic does not call `open()`, `write_*`, or network clients unless passed injected ports. |
| **How to measure** | (Later) Static grep + import graph: library modules under public package must not import persistence/HTTP/OS modules except allowlisted adapter subpackage; spot-check public callables for side effects via tests with tmp isolation; verify CLI module owns I/O. |
| **Audit method** | Conformance checklist + modularity/boundary audit (pairs with P08) |
| **Scoring hook** | 6.2 **hard gate** candidate (architectural invariant for QA libraries); 6.1 architecture/hybrid overlap |
| **Gaming vector** | Thin wrapper re-export that hides writes inside “helper”; default path writes to cwd; side effects in `@property` or module import time. |
| **Anti-gaming guard** | **Mandatory** unit test: run core public API on in-memory inputs with filesystem mocked read-only; assert zero file creations. Gate fails on any undeclared write. Document allowed adapter entry points in public API list. |
| **Evidence grade** | **B** (Hitchhiker’s Guide pure-function discipline [T3]; hexagonal/functional-core pattern in mature templates [T3]; strong internal precedent in repo CLAUDE.md invariant — cited as context only, not scored here) |
| **Sources** | [T3] Hitchhiker’s Guide — Structuring Your Project (pure functions / side-effect isolation); [T3] ArchiPy concepts (models vs adapters); exemplar separation in Docling typed `ConversionResult` return ([T2]) |

---

### Criterion 2.6 — Stable, documented return shapes at the public boundary

| Field | Content |
|---|---|
| **Criterion** | Public functions return **versioned, serializable data structures** (dataclass, TypedDict, Pydantic model, or documented dict schema) with fields documented for stability; exceptions/errors are typed or enumerated; no undocumented dict key additions that break strict consumers. |
| **How to measure** | API reference lists return types; snapshot tests or JSON schema for stable fields; breaking field renames tracked in changelog API section. |
| **Audit method** | Comparative benchmarking (Docling exemplar) + construct-validity audit |
| **Scoring hook** | 6.1 release-readiness + extraction-quality eval handoff (downstream metrics consume return shapes) |
| **Gaming vector** | `dict[str, Any]` returns; undocumented extra keys; pydantic models with `extra=allow` on public results. |
| **Anti-gaming guard** | Require frozen/explicit schema on public result types; contract test asserts **exact** key set for major version; new fields only via minor with deprecation path for renames. |
| **Evidence grade** | **B** (Docling `DocumentConverter` → `ConversionResult` pydantic-model pattern [T2]; typing spec encourages explicit interfaces) |
| **Sources** | [T2] Docling API reference — DocumentConverter / ConversionResult; [T1] typing.python.org stub files as API documentation |

---

### Criterion 2.7 — Minimal package facade and entry-point hygiene

| Field | Content |
|---|---|
| **Criterion** | Package `__init__.py` stays **thin**: re-exports curated surface, avoids eager submodule imports that trigger heavy side effects or circular imports; console scripts declared via `[project.scripts]` entry points (PyPA), not `python -m` undocumented modules as primary operator surface. |
| **How to measure** | Line count and import graph of `__init__.py`; import-time side-effect test; verify scripts map to documented stable callables. |
| **Audit method** | Conformance checklist (PyPA entry points) + observability (import cost) |
| **Scoring hook** | 6.1 release-readiness; pairs with P21 CLI UX |
| **Gaming vector** | Mega-`__init__` that imports LLM stack at import time; hidden `main()` in library module. |
| **Anti-gaming guard** | Import benchmark budget (e.g., `<N` ms without extras); static rule: optional extras not imported from core `__init__`. |
| **Evidence grade** | **B** (Scientific Python cookie warns on heavy `__init__.py`; PyPA pyproject scripts spec [T2]) |
| **Sources** | [T2] Scientific Python Development Guide — Exports; [T2] PyPA Writing pyproject.toml — `[project.scripts]` |

---

### Criterion 2.8 — Dependency leakage through public imports

| Field | Content |
|---|---|
| **Criterion** | Public API does not **re-export transitive dependency types** as stable contract (e.g., exposing vendor exception classes, ORM models, or LLM client types in function signatures) unless explicitly listed in stability policy; prefer domain-owned types at boundaries. |
| **How to measure** | Type inspection of public signatures: identify annotations referencing non-stdlib third-party modules; compare to DEPENDENCY.md stability list. |
| **Audit method** | Conformance checklist + provenance boundary (P08/P22 overlap) |
| **Scoring hook** | 6.1 release-readiness; 6.2 gate if vendor type in public signature without pinning/stability doc |
| **Gaming vector** | `from vendor import Thing` re-exported in `__all__` without semantic ownership. |
| **Anti-gaming guard** | Lint rule: public signatures may only use stdlib + first-party types + allowlisted stability exceptions documented in VERSIONING.md. |
| **Evidence grade** | **B** (typing spec: imported symbols private by default unless re-export idioms [T1]; Griffe public API guidance [T3]) |
| **Sources** | [T1] typing.python.org — Import Conventions; [T3] Griffe — Public APIs recommendations |

---

## 3. External benchmark / exemplar bar

| Exemplar | Practice | Bar for whisker audit | Wrong to cargo-cult |
|---|---|---|---|
| **CPython / PEP 387** | Public API set enumerated; multi-release deprecation | Professional libraries document removals ≥2 releases ahead | CPython’s multi-year timeline may exceed small-library needs if explicitly narrowed in policy |
| **typing spec + PEP 561** | `py.typed`, `__all__`, import re-export rules | Typed, statically enumerable public surface | Stub-only `*-stubs` split unnecessary if inline types complete |
| **SemVer 2.0 + PyPA versioning** | Declare public API; semver communicates intent | Published VERSIONING.md + valid bumps | Strict semver insufficient alone (Hyrum); most projects use “loose” semver |
| **IBM Docling** | Single entry class (`DocumentConverter`), pydantic **return models**, typed reference docs | One primary converter/QA entry type; structured results for downstream eval | Docling’s in-library persistence defaults; model-serving stack |
| **Scientific Python cookie** | Literal `__all__`, minimal `__init__.py` | Curated exports, no import-time heaviness | Cookie targets numpy-stack scale; whisker may have smaller surface |
| **Google Python Style** | Annotate public APIs | Public signatures fully typed | Google BUILD/pytype infra not required |

**Professional bar (synthesis-ready):** A release-ready QA library exposes a **small, typed, literally enumerated** public surface; versions and deprecations are **documented and test-detectable**; core API **returns data** with **stable schemas**; semver/changelog honesty acknowledges **Hyrum** (observable behavior is contract).

---

## 4. Recommended weight & hard-gate advice

| Item | Recommendation | Rationale |
|---|---|---|
| **Composite weight (release-readiness dimension)** | **14–18%** of total composite, split across 2.1–2.8 sub-scores | Cluster A shares release readiness with P01/P04; API contract is load-bearing for integrators and eval harnesses but not sole release signal |
| **Sub-weight emphasis** | 2.2 + 2.5 + 2.1 = **≥50%** of P02 sub-score | Typing, public registry, and side-effect boundary are most defensible and testable |
| **Hard gate candidates** | **(G1)** Undeclared write/network side effect in public library path on default call (2.5). **(G2)** Claims typed public API but missing `py.typed` or untyped documented entry points (2.2). **(G3)** Undocumented breaking public signature change in patch release while claiming strict SemVer (2.3). | Mirrors repo invariants (library returns data; fidelity); gates are falsifiable, not cosmetic |
| **Non-gate** | SemVer strictness alone; `__all__` affecting non-wildcard imports | Hyrum + PyPA looseness makes semver non-binary; `__all__` without tests still gameable |
| **Confidence** | **Medium–high** on 2.1–2.4 (Tier 1); **medium** on 2.5–2.8 (architecture patterns Tier 2–3) | Propagate **B** as weakest load-bearing grade unless consumer typecheck + side-effect tests pass |
| **Contested criteria handling** | Mark 2.3 semver strictness as **contested** when only semver badge present; widen score band per 6.6 | PyPA vs semver.org vs Hyrum triangulation |
| **Flip condition** | Reclassifying 2.5 from advisory to non-gate could flip release-readiness band for a library that writes golden files inside core API | Name in sensitivity note |

---

## 5. Sources

| ID | Tier | Source | URL | Version / date |
|---|---|---|---|---|
| S1 | **T1** | PEP 561 — Distributing and Packaging Type Information | https://peps.python.org/pep-0561/ | Final; updated 2023-01-13 |
| S2 | **T1** | PEP 387 — Backwards Compatibility Policy | https://peps.python.org/pep-0387/ | Active; updated 2025-01-27 |
| S3 | **T1** | PEP 702 — Marking deprecations using the type system | https://peps.python.org/pep-0702/ | Final; Python 3.13; 2023-11-07 |
| S4 | **T1** | Semantic Versioning 2.0.0 | https://semver.org/ | Spec 2.0.0 |
| S5 | **T1** | Typing spec — Distributing type information (incl. Library interface, Import Conventions) | https://typing.python.org/en/latest/spec/distributing.html | Current typing spec |
| S6 | **T2** | PyPA — Versioning (discussions) | https://packaging.python.org/en/latest/discussions/versioning/ | Reviewed 2023-12-14 page |
| S7 | **T2** | PyPA — Writing your pyproject.toml (scripts, metadata) | https://packaging.python.org/en/latest/guides/writing-pyproject-toml/ | Current guide |
| S8 | **T2** | Scientific Python Development Guide — Exports | https://scientific-python-cookie.readthedocs.io/en/latest/patterns/exports/ | Current |
| S9 | **T2** | Docling — DocumentConverter API reference | https://docling-project.github.io/docling/reference/document_converter/ | Current docs |
| S10 | **T2** | Google Python Style Guide (public API typing) | https://google.github.io/styleguide/pyguide.html | Current |
| S11 | **T2** | Hyrum's Law (primary observation) | https://www.hyrumslaw.com/ | Authoritative primary essay |
| S12 | **T3** | Hynek — Semantic Versioning Will Not Save You | https://hynek.me/articles/semver-will-not-save-you/ | Contextual; corroborates S11 |
| S13 | **T3** | Hitchhiker's Guide — Structuring Your Project (pure functions) | https://docs.python-guide.org/writing/structure/ | Contextual architecture |
| S14 | **T3** | Griffe — Public APIs recommendations | https://mkdocstrings.github.io/griffe/guide/users/recommendations/public-apis/ | Contextual tooling |

**Tier 1–2 distinct primaries used for criteria:** 10 (S1–S11, excluding T3-only). Floor satisfied (≥3).

---

## 6. Overlap statement

This persona researched **external public-API and contract-design standards only**. It did **not** open whisker production code, cite whisker `file:line`, or score whisker. It did **not** duplicate the code-level **persona/** swarm (including any prior “api-contract-design” code scorer) or **llm-stack/** tapetum isolation findings. It complements **P01** (packaging/release metadata) and **P04** (CI/test maturity) without re-auditing dependencies (**P03**) or module boundaries (**P08**). Case-study personas **P27/P29** may cite Docling/unstructured exemplars in more depth; this report uses Docling only as a **contract-shape** benchmark, not a converter red-team.

---

**Deliverable metadata:** 14 Tier 1–2 sources listed (10 load-bearing); **8 audit criteria** proposed. **Strongest criterion:** **2.5 — Side-effect boundary (“library returns data, caller persists”)** with **2.2 typed `py.typed` public surface** as close second; 2.5 is the highest-leverage **hard gate** because it is falsifiable by mock-filesystem tests, encodes QA-library trust, and cannot be satisfied by documentation cosmetics alone.
