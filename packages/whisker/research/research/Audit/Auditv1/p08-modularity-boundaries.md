# P08 — Modularity, Coupling & Package-Boundary Research

**Persona:** Modularity, Coupling & Package-Boundary Researcher (Cluster B, persona 8)  
**Date:** 2026-07-18  
**Stage:** 0 evidence framing (external method only; no whisker code inspection)

---

## 1. Question restated

What external bar should a **standalone Python package** meet for module design and package boundaries: coupling/cohesion discipline, import-layering contracts, one-way dependency direction, consumption of other packages only via their public API, and **measurable** boundary integrity? This persona produces audit *criteria* and an external benchmark; it does not score whisker code.

---

## 2. Proposed audit criteria

Each criterion below is tagged with its audit-method (per `00-FRAME.md` §5), scoring-design hook (§6), gaming vector, anti-gaming guard, evidence grade, and Tier 1–2 citations.

### Criterion 2.1 — Declared import-layering contract exists and is CI-enforced

| Field | Content |
|---|---|
| **Criterion** | The package publishes a machine-readable import architecture (layer order, forbidden edges, protected modules) and enforces it on every CI run. |
| **How to measure** | (1) A committed `.importlinter` (or equivalent) file declares at least one `layers`, `forbidden`, or `protected` contract scoped to the package root. (2) CI runs `lint-imports` (Import Linter ≥2.x) and fails on violation. (3) Contracts cover all top-level subpackages (exhaustive mode or explicit `exhaustive_ignores` with documented rationale). Score 0 = none; 1 = config exists, not in CI; 2 = CI-enforced; 3 = CI + exhaustive; 4 = CI + exhaustive + no `ignore_imports` entries added in last release cycle without ADR. |
| **Audit-method** | Conformance checklist |
| **Scoring hook** | §6.1 (architecture dimension maturity); §6.2 candidate hard gate |
| **Gaming vector** | Empty or trivial one-layer contract that always passes; `ignore_imports` whitelist grows until checks are meaningless. |
| **Anti-gaming guard** | Require `exhaustive = true` on layer contracts with a bounded `exhaustive_ignores` list; fail CI if any `ignore_imports` pattern is unmatched (`unmatched_ignore_imports_alerting = error`); review net new ignores in PR checklist. |
| **Evidence grade** | **A** — multiple Tier-1 tool docs converge on layers/forbidden/protected as the enforceable unit. |

**Sources:** Import Linter contract types (layers, forbidden, protected, exhaustive) [S1, S2]; Grimp `find_illegal_dependencies_for_layers` as the underlying graph analysis [S3].

---

### Criterion 2.2 — Acyclic dependencies among architectural units (ADP)

| Field | Content |
|---|---|
| **Criterion** | The import graph among declared packages/subpackages/modules has **no cycles**; dependency direction is a directed acyclic graph (DAG). |
| **How to measure** | Build an internal import graph (Grimp `build_graph` or Import Linter independence/acyclic-siblings contracts). Report any cycle with shortest chain (`find_shortest_chain`). Maturity: 0 = cycles present, undetected; 1 = cycles known, accepted; 2 = cycles detected in CI warning; 3 = cycles fail CI; 4 = cycles fail CI + documented break strategy (extract shared module or dependency inversion) for any historical cycle removed. |
| **Audit-method** | Conformance checklist; Reproducibility replay (graph rebuild is deterministic) |
| **Scoring hook** | §6.2 hard gate (non-compensatory) |
| **Gaming vector** | Treating every module as one flat layer so cycles are "legal"; dynamic imports that static analysis misses. |
| **Anti-gaming guard** | Cycle detection must run on the same graph tool Import Linter uses (Grimp); spot-check for `importlib`/`__import__` in boundary modules; independence contracts between sibling subsystems that must not mutually depend. |
| **Evidence grade** | **A** — ADP is a named design principle; tool support makes it mechanically testable. |

**Sources:** Acyclic Dependencies Principle (Robert C. Martin) [S4]; Import Linter `independence` contract type [S1]; Grimp import-graph API [S3].

---

### Criterion 2.3 — Cross-package consumption via public API only

| Field | Content |
|---|---|
| **Criterion** | When this package depends on **other** packages (in a monorepo or multi-package workspace), imports reach only documented public entry points—not private modules, leading-underscore symbols, or transitive internal paths. |
| **How to measure** | (1) Inventory all imports of sibling/workspace packages. (2) Flag imports of modules named `_*` or paths not listed in the dependency's public docs/`__all__`/package `__init__` re-exports. (3) Import Linter `forbidden` or `protected` contracts: e.g. forbid `otherpkg._internal` and allow only `otherpkg` facade modules. Score by % of cross-package imports that are public-surface vs leaky. |
| **Audit-method** | Conformance checklist |
| **Scoring hook** | §6.1; §6.2 hard gate for workspace packages with explicit boundary rules |
| **Gaming vector** | Re-export private symbols in a thin "public" shim that re-exposes unstable internals; `# noqa` or ignore lists. |
| **Anti-gaming guard** | Require dependency's documented public API list (README or `__all__`) as the allow-list; ban wildcard re-exports of `_`-prefixed names; periodic diff of cross-package imports against allow-list. |
| **Evidence grade** | **A** — PEP 8 public/internal rules + Google public-API testing guidance + protected-module contracts. |

**Sources:** PEP 8 §Public and Internal Interfaces [S5]; Google SWE Book §Test via Public APIs [S6]; Import Linter `protected` contract [S1].

---

### Criterion 2.4 — Explicit public surface declaration inside the package

| Field | Content |
|---|---|
| **Criterion** | Every user-facing subpackage defines its public API explicitly (`__all__` in `__init__.py` or documented facade modules); internal helpers use single-leading-underscore naming. |
| **How to measure** | (1) `%` of subpackages with non-empty `__all__` or a single documented entry module. (2) Ruff/pyflakes clean on `__all__` members that exist. (3) No public re-export of sibling `_`-prefixed modules without ADR. Maturity 0–4 by coverage and linter cleanliness. |
| **Audit-method** | Documentation-completeness audit; Conformance checklist |
| **Scoring hook** | §6.1 (release-readiness / API contract overlap at method layer) |
| **Gaming vector** | Bloated `__all__` listing experimental internals; empty `__all__` with everything importable anyway. |
| **Anti-gaming guard** | Treat `__all__` as semver-bound: breaking changes require major bump; diff `__all__` in release checklist; underscore-prefix on everything not in `__all__`. |
| **Evidence grade** | **B** — PEP 8 is Tier 1; enforcement is convention + linter, not language-enforced. |

**Sources:** PEP 8 [S5]; Griffe public-API recommendations (underscore + `__all__` discipline) [S7].

---

### Criterion 2.5 — One-way dependency direction (core → optional, never reverse)

| Field | Content |
|---|---|
| **Criterion** | For a standalone package with optional extras (e.g. advisory LLM lane), the **core dependency graph is one-way**: optional/integration layers may depend on core, but core must not depend on optional extras or their transitive deps. |
| **How to measure** | Declare layers: `{optional_advisory, core_domain, utilities}`. Import Linter `layers` contract with optional layer in parentheses if absent in minimal install. Verify `pyproject.toml` `[project.optional-dependencies]` packages appear only in optional-layer modules. CI fails if core imports optional-only deps (detect via `include_external_packages = True` forbidden list). |
| **Audit-method** | Conformance checklist; Maturity-model |
| **Scoring hook** | §6.2 hard gate (hybrid architecture integrity) |
| **Gaming vector** | Lazy import inside core functions to hide optional dep edges from static analysis. |
| **Anti-gaming guard** | Static graph must pass without executing code; grep for optional-only distribution names in core paths; install test matrix runs `pip install .` (no extras) and asserts optional modules not importable from core entry points. |
| **Evidence grade** | **B** — layered architecture pattern in Import Linter/Grimp; Google third_party / dependency-direction guidance as analog. |

**Sources:** Import Linter layers (optional layers, containers) [S1, S2]; Google SWE Book Ch.21 source-control vs dependency management [S8]; Grimp closed layers (`closed=True`) to prevent "reach-through" [S3].

---

### Criterion 2.6 — Coupling budget between subsystems (CBO-inspired)

| Field | Content |
|---|---|
| **Criterion** | Inter-subpackage coupling stays within a declared budget: no single subsystem has excessive fan-out to distinct sibling subpackages (analog of Coupling Between Object classes, CBO, at module/package granularity). |
| **How to measure** | Using Grimp: for each top-level subpackage `P`, compute \|{ sibling subpackages directly or indirectly imported by P }\|. **Budget:** default warn at >5, fail at >8 (tunable constants in audit config). Report top-5 highest-CBO modules. Maturity 0 = unmeasured; 4 = measured, budgeted, trended in CI artifact. |
| **Audit-method** | Metric construct-validity audit (coupling as proxy, not truth); Comparative benchmarking |
| **Scoring hook** | §6.1 (architecture sub-score); not a hard gate unless extreme |
| **Gaming vector** | Re-export hub module that centralizes imports to game low per-module CBO; threshold set so high it never fires. |
| **Anti-gaming guard** | Count distinct **subpackages** not modules; flag "god" re-export `__init__.py` files; calibrate budget on exemplar packages and document chosen constants. |
| **Evidence grade** | **B** — CK CBO is Tier-1 empirical literature; package-level adaptation is Tier-2 engineering judgment. **Contested:** Briand et al. (1996) show CK metrics need careful empirical grounding—coupling count is indicative, not sufficient for quality [S9]. |

**Sources:** Chidamber & Kemerer (1994) CBO [S10]; Basili et al. validation of CK metrics [S11]; Grimp upstream/downstream queries [S3].

---

### Criterion 2.7 — Sibling cohesion / independence contract

| Field | Content |
|---|---|
| **Criterion** | Subsystems at the same architectural layer are either **explicitly independent** (no mutual imports) or **explicitly allowed** to depend (colon-separated siblings in layer config)—not accidentally coupled. |
| **How to measure** | Import Linter layer line uses `\|` for independent siblings or `:` for cooperating siblings. Audit verifies config matches documented architecture (README diagram). Any undocumented cross-sibling import fails. |
| **Audit-method** | Conformance checklist |
| **Scoring hook** | §6.1 |
| **Gaming vector** | Dump all siblings into one layer with `:` separators to avoid independence rules. |
| **Anti-gaming guard** | Architecture doc must justify each sibling group; independence contracts for known parallel lanes (e.g. separate eval vs gate subsystems). |
| **Evidence grade** | **A** — direct feature of Import Linter multi-item layers [S1, S2]. |

**Sources:** Import Linter §Multi-item layers (pipe vs colon) [S1, S2].

---

### Criterion 2.8 — Boundary integrity is regression-tested

| Field | Content |
|---|---|
| **Criterion** | Boundary checks are not one-time architecture reviews; they are **regression tests** that fail on new violations. |
| **How to measure** | CI job `lint-imports` + optional Grimp script exporting graph stats as build artifact. On PR: zero new violations vs base branch. Canary: intentionally add a forbidden import in a test branch and confirm CI catches it (mutation-style gate test). |
| **Audit-method** | Conformance checklist; Anti-gaming / Goodhart stress |
| **Scoring hook** | §6.4 anti-gaming (proves the gate has teeth) |
| **Gaming vector** | CI job present but allowed to fail (`continue-on-error`); architecture lint not run on PRs. |
| **Anti-gaming guard** | Required check on merge; periodic canary PR or dedicated test that asserts linter detects injected violation. |
| **Evidence grade** | **A** — Import Linter explicitly targets deployment pipelines [S12]; Google build graph checks on every change [S13]. |

**Sources:** Import Linter PyPI/readme (CI integration intent) [S12]; Google SWE Book Ch.18 Bazel dep graph [S13].

---

## 3. External benchmark / exemplar bar

### 3.1 Professional standalone Python package (floor)

| Practice | Bar | Exemplar source |
|---|---|---|
| Documented layer direction | Higher layers depend downward only; indirect imports count | Import Linter layers contract [S1] |
| No dependency cycles | ADP: package graph is a DAG | Martin ADP [S4] |
| Public vs internal | `__all__` + `_` prefix; no reliance on indirect imports unless documented API | PEP 8 [S5] |
| Enforced in CI | `lint-imports` required check | Import Linter [S12] |
| Optional features isolated | Core install graph excludes optional-extra deps | Layer + forbidden contracts [S1]; Google prefer explicit deps [S13] |

### 3.2 Monorepo / multi-package workspace (stretch)

Where a package lives beside siblings (typical in a workspace):

| Practice | Bar | Exemplar source |
|---|---|---|
| Explicit dependency lists | Every target/package declares deps; graph analyzable | Google Bazel BUILD deps [S13] |
| Third-party segregation | External code in dedicated namespace (`third_party` analog) | Google SWE Ch.21 [S8] |
| Public API is the test surface | Tests and dependents use same entry points as external users | Google SWE Ch.12 [S6] |
| One Version / boundary stability | Depend on stable public surfaces, not forked internals | Google SWE Ch.16 [S14] |

### 3.3 Measurement tooling bar

| Tool | Role | Version anchor |
|---|---|---|
| **Import Linter** | Declarative contracts, CI `lint-imports` | v2.13 (2026-07-03) [S12] |
| **Grimp** | Queryable import graph, layer violation detection, coupling metrics | v3.14 [S3] |
| **Ruff / pyflakes** | `__all__` consistency | Ecosystem standard |

### 3.4 Known limits (contradictions surfaced)

1. **CK metrics are necessary but not sufficient.** CBO/LCOM predict fault-proneness in OO systems [S10, S11] but Briand & Wüst (1996) argue formulation gaps—package-level coupling budgets must not be the sole quality signal [S9].
2. **Python visibility is conventional.** PEP 8 `_` and `__all__` do not block imports; mechanical enforcement requires Import Linter/grimp or custom AST checks [S5, S7].
3. **Monorepo ≠ standalone package.** Google/Bazel assumptions (BUILD files, third_party tree) do not map 1:1 to single-package PyPI releases; adapt criteria: workspace rules apply only when sibling packages exist [S8, S13].
4. **Closed vs open layers.** Grimp `closed=True` prevents "reach-through" imports; stricter than basic layers—use when hiding implementation tiers is required [S3].

---

## 4. Recommended weight & gate placement

### 4.1 Dimension weight (feeds §6.1 composite)

| Recommendation | Rationale |
|---|---|
| **Architecture / modularity dimension: 8–12% of composite** | Boundaries enable hybrid deterministic+LLM separation (P05/P07) but do not directly measure extraction quality or release metadata (P01). Evidence: Google treats dependency structure as enabler for scale, not user-visible quality [S13, S14]. |
| **Sub-criteria weights (within dimension)** | 2.1 CI layering 25%; 2.2 acyclic 20%; 2.3 public API consumption 20%; 2.5 one-way optional/core 15%; 2.6 coupling budget 10%; 2.4 `__all__` 5%; 2.7 sibling independence 3%; 2.8 regression proof 2%. |

### 4.2 Hard gates (feeds §6.2)

| Gate | Criterion | Rationale |
|---|---|---|
| **G-BND-1: No import cycles among declared architectural units** | 2.2 | ADP violation makes layering unenforceable; non-compensatory [S4]. |
| **G-BND-2: Core must not depend on optional-extra packages** | 2.5 | Hybrid architecture fails if nondeterministic/ heavy deps leak into deterministic core (aligns P05/P07 without scoring whisker here). |
| **G-BND-3: CI import-linter failure blocks merge** | 2.1 + 2.8 | Without enforced contracts, boundary criteria are cosmetic (§6.4 Goodhart). |

**Not recommended as hard gate:** CBO budget alone (2.6)—too context-sensitive; keep as maturity sub-score unless extreme outlier (>2× budget).

### 4.3 Confidence note (feeds §6.3)

Load-bearing criteria 2.1–2.3, 2.5 carry evidence grade **A**. Criterion 2.6 carries **B** (metric adaptation). Composite modularity score propagates weakest grade **B** unless coupling budget is excluded from composite (recommended: include as low-weight input only).

---

## 5. Sources

| ID | Tier | Source | URL | Version / date |
|---|---|---|---|---|
| **S1** | 1 | Import Linter — Contract types (forbidden, protected, independence, layers, exhaustive, multi-item) | https://import-linter.readthedocs.io/en/v2.5/contract_types.html | Docs v2.5 (2025-09+) |
| **S2** | 1 | Import Linter — Layers contract | https://import-linter.readthedocs.io/en/stable/contract_types/layers/ | Stable docs (accessed 2026-07-18) |
| **S3** | 1 | Grimp — Usage / ImportGraph API | https://grimp.readthedocs.io/en/latest/usage.html | v3.14 |
| **S4** | 2 | Acyclic Dependencies Principle (Robert C. Martin) | https://en.wikipedia.org/wiki/Acyclic_dependencies_principle | Principle; cites Object Mentor ADP material |
| **S5** | 1 | PEP 8 — Style Guide (Public and Internal Interfaces, `__all__`, imports) | https://peps.python.org/pep-0008/ | Active PEP |
| **S6** | 2 | *Software Engineering at Google* — Ch.12 Unit Testing, §Test via Public APIs | https://abseil.io/resources/swe-book/html/ch12.html | O'Reilly 2020 |
| **S7** | 2 | Griffe — Public APIs recommendations | https://mkdocstrings.github.io/griffe/guide/users/recommendations/public-apis/ | MkDocstrings project docs |
| **S8** | 2 | *Software Engineering at Google* — Ch.21 Dep management, third_party | https://abseil.io/resources/swe-book/html/ch21.html | O'Reilly 2020 |
| **S9** | 1 | Briand & Wüst — CK metrics measurement theory critique | https://doi.org/10.1109/32.491650 | IEEE TSE 22(4), 1996 |
| **S10** | 1 | Chidamber & Kemerer — A metrics suite for object oriented design (CBO, LCOM) | https://doi.org/10.1109/32.295895 | IEEE TSE 20(6), 1994 |
| **S11** | 1 | Basili et al. — Validation of OO design metrics as quality indicators | https://www.cs.umd.edu/~basili/publications/technical/T102.pdf | Empirical validation, UMD TR |
| **S12** | 1 | import-linter PyPI project page | https://pypi.org/project/import-linter/ | v2.13, 2026-07-03 |
| **S13** | 2 | *Software Engineering at Google* — Ch.18 Build systems, explicit deps / DAG | https://abseil.io/resources/swe-book/html/ch18.html | O'Reilly 2020 |
| **S14** | 2 | *Software Engineering at Google* — Ch.16 One Version Rule | https://abseil.io/resources/swe-book/html/ch16.html | O'Reilly 2020 |

**Tier 1–2 distinct primary sources used:** 14 (floor ≥3 satisfied).  
**Tier 1 count:** 8 (S1–S3, S5, S9–S11, S12).  
**Tier 2 count:** 6 (S4, S6–S8, S13–S14).

---

## 6. Overlap statement

This persona researched **external** modularity and package-boundary method only.

**Avoided duplicating:**

| Prior folder | Boundary held |
|---|---|
| `persona/` maintainability-complexity personas | Those scored whisker code complexity; this file defines external coupling/layering/import-linter criteria only—no whisker `file:line`, no code verdict. |
| `llm-stack/` | Isolation of tapetum LLM lane is a whisker code finding; criterion 2.5 here states the *general* one-way core→optional pattern as an audit bar, not whether whisker satisfies it. |
| `p02-api-contract-design.md` (sibling persona) | P02 owns semver/typing/deprecation public-API *contract*; P08 owns import-graph layering, cycles, and cross-package *boundary integrity* measurement. Overlap on `__all__` is minimal (2.4 defers semver to P02). |
| `p05-hybrid-architecture.md` / `p07-dual-determinism-reconciliation.md` | Those own hybrid/determinism doctrine; P08 supplies structural enforcement mechanisms (layers, acyclic graph) that make separation auditable. |

**Confirmation:** No whisker production code was opened. No code was cloned, forked, or copied. Output is exactly this file under `packages/whisker/research/Audit/`.

---

## Summary for synthesis fan-in

| Item | Value |
|---|---|
| **Criteria count** | 8 |
| **Source count (Tier 1–2)** | 14 distinct |
| **Recommended hard gates** | 3 (acyclic graph; core↛optional deps; CI import-linter required) |
| **Strongest criterion** | **2.1 — Declared import-layering contract CI-enforced** (mechanically verifiable, directly prevents boundary erosion, tool-supported at Import Linter v2.13, anti-gaming via exhaustive mode + ignore-list discipline) |
