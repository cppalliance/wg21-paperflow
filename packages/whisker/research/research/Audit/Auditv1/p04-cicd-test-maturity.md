# P04 — CI/CD & Test-Suite Maturity Researcher

**Persona:** 4 of 30 (Cluster A: Professional Python package & release readiness)  
**Date:** 2026-07-18  
**Scope:** External method and standards only. No whisker production-code inspection.

---

## 1. Question restated

What external bar defines **test-suite and CI maturity** for a Python **QA tool** (a package whose job is to judge extraction/conversion quality), and how should that bar become **repeatable audit criteria**? This persona covers: coverage expectations and their limits (Goodhart), hermetic/deterministic CI tests, mutation/canary/metamorphic tests with **gate teeth**, OS/Python test matrices, property-based vs example-based testing, and what a QA tool must **itself** test to be trusted. Criteria are external standards only; no whisker code verdict.

---

## 2. Proposed audit criteria

Each criterion is scored on a **0–4 maturity ladder** unless marked as a **hard gate**. Evidence grades follow `00-FRAME.md` §6.3: **A** = multiple Tier-1 corroborating; **B** = single Tier-1 or converging Tier-2; **C** = Tier-3 only or contested; **D** = Tier-4/speculative.

### Criterion T1 — CI runs on every change with blocking status

| Field | Value |
|---|---|
| **Criterion** | Automated CI executes the full test suite (or declared tier-1 subset) on every pull request and protected-branch push; failing jobs block merge; workflow is version-controlled and reproducible from the repo alone. |
| **How to measure** | Inspect CI config: trigger on `pull_request` + `push` to default branch; required status checks enabled on branch protection; no manual-only test path as sole gate. Verify `fail-fast` policy documented (matrix jobs may set `fail-fast: false` for signal, not to hide failures). |
| **Audit method** | Conformance checklist (§5.1) + maturity model (§5.2) |
| **Scoring hook** | §6.1 release-readiness; §6.2 candidate **hard gate** if no CI on PR |
| **Gaming vector** | Workflow exists but is `workflow_dispatch` only; tests run on schedule but not on PR; allowed-to-fail jobs marked `continue-on-error: true` on gate steps. |
| **Anti-gaming guard** | Require branch-protection rule listing CI job names; audit that pytest/ruff/typecheck steps lack `continue-on-error`; spot-check last 20 merged PRs for green required checks. |
| **Evidence grade** | **B** |
| **Sources** | GitHub Actions matrix docs (2025–2026); pytest CI explanation (Tier 2) |

### Criterion T2 — Coverage is diagnostic, not a quality target (Goodhart guard)

| Field | Value |
|---|---|
| **Criterion** | Line/branch coverage is collected and reported for **gap identification** but is **not** the sole merge gate or numeric target that teams optimize. Policy explicitly cites coverage's weak correlation with fault detection when suite size is controlled. |
| **How to measure** | Check CI: if coverage threshold enforced, verify it is paired with assertion-quality or mutation/metamorphic checks (T4/T6). Read CONTRIBUTING/CLAUDE.md for "coverage is not a target" language. Compare to Inozemtseva & Holmes finding: low–moderate coverage↔effectiveness correlation when size controlled. |
| **Audit method** | Anti-gaming / Goodhart stress (§5.7) + metric construct-validity audit (§5.4) |
| **Scoring hook** | §6.4 anti-gaming rules; §6.1 release-readiness sub-criterion |
| **Gaming vector** | 80% coverage gate → assertion-free tests, `# pragma: no cover` on gate logic, excluding hard paths from coverage scope. |
| **Anti-gaming guard** | Forbid coverage-only merge gates; require diff/branch coverage on changed files **plus** at least one effectiveness metric (mutation kill rate on changed modules, metamorphic suite, or regression canaries). Document that coverage finds **untested** code, not **well-tested** code. |
| **Evidence grade** | **A** |
| **Sources** | Inozemtseva & Holmes, ICSE 2014 (Distinguished Paper); ACM TOSEM 2025 suite-size confound replication |

**Contradiction surfaced:** Many orgs still use coverage thresholds as policy. **Resolution rule:** coverage thresholds are **contested** (grade **C** as sole gate); acceptable only as **floor on changed code** combined with T4/T6 effectiveness checks. Prefer Inozemtseva & Holmes + Just et al. (mutation correlates with real faults independent of coverage) over dashboard culture.

### Criterion T3 — Hermetic, deterministic CI test execution

| Field | Value |
|---|---|
| **Criterion** | Default CI tests are **hermetic**: outcomes depend only on declared repo inputs (source, fixtures, golden files, pinned deps), not live network, wall-clock races, or host-global mutable state. Non-deterministic sources (RNG, time, concurrency) are injected/faked with documented seeds. |
| **How to measure** | Review test suite for outbound HTTP without VCR/mock; `sleep`-based synchronization; reliance on `$HOME`, `/tmp` without isolation; unordered set/dict iteration in golden diffs. CI uses fresh runners/containers per job. Re-run same commit twice: identical pass/fail and stable outputs (bit-exact or documented tolerances). |
| **Audit method** | Reproducibility replay (§5.8) + observability/fault-injection overlap (§5.11) |
| **Scoring hook** | §6.1 release-readiness; §6.2 gate candidate for QA tools claiming deterministic gates |
| **Gaming vector** | Tests pass locally with env vars unset in CI; flaky tests `@pytest.mark.flaky` without quarantine policy; integration tests hitting production APIs marked as "optional." |
| **Anti-gaming guard** | `--strict-markers` + ban undocumented xfail; network-off job (`pytest -m "not network"` or global socket block); repeat-run job (`--count=100` on critical subset) on presubmit or nightly; document hermetic contract in test README. |
| **Evidence grade** | **A** |
| **Sources** | Bazel Test Encyclopedia (hermeticity spec); Google *Software Engineering at Google* Ch.23 CI; Fuchsia testing best practices |

### Criterion T4 — Mutation-informed gate with teeth (scoped)

| Field | Value |
|---|---|
| **Criterion** | Mutation testing (or equivalent fault injection) runs in CI on **security-/gate-critical modules** (not necessarily whole repo). Documented kill-rate floor or "no new surviving mutants on touched lines" policy; surviving mutants triaged, not ignored. |
| **How to measure** | CI job runs `mutmut` (or cosmic-ray) on declared paths; parse kill rate = killed / (killed + survived). Verify policy threshold (exemplar: ≥85% on gate modules). Inspect that mutants on threshold/comparison operators in gate logic are killed. |
| **Audit method** | Adversarial / red-team probing (§5.6) + calibration overlap (§5.5) |
| **Scoring hook** | §6.2 **hard gate candidate** for QA-tool gate/scorer modules; §6.4 anti-gaming |
| **Gaming vector** | Mutation run only locally; threshold on easy modules while gate code excluded; counting timeouts as killed; never updating baseline so regressions hide. |
| **Anti-gaming guard** | Scope mutation to files listed in audit config; fail CI if kill rate drops below recorded baseline on PRs touching those files; export machine-readable mutation stats for trend tracking; pair with T6 canaries. |
| **Evidence grade** | **A** |
| **Sources** | Just et al., FSE 2014 (mutation↔real fault correlation independent of coverage); mutmut official docs (2025–2026); Papadakis et al., ICST 2018 mutation survey (Tier 1 secondary) |

**Contradiction surfaced:** Just et al. confirm mutation score predicts real faults, but ~20% of real faults are not simulable by mutants. **Resolution rule:** mutation gate is **necessary not sufficient**; require T6 metamorphic/canary tests for oracle-less QA paths.

### Criterion T5 — OS × Python version test matrix

| Field | Value |
|---|---|
| **Criterion** | CI matrix covers **every** Python version in `requires-python` on **≥2 OS families** (typically `ubuntu-latest` + `windows-latest` or `macos-latest`); uses `actions/setup-python` (or tox equivalent) for interpreter provisioning, not system Python alone. |
| **How to measure** | Parse workflow matrix vs `requires-python` and classifiers; verify `exclude` entries documented; `fail-fast: false` where cross-product signal needed. Optional: PyPy row if claimed supported. |
| **Audit method** | Conformance checklist + comparative benchmarking (§5.3) |
| **Scoring hook** | §6.1 release-readiness |
| **Gaming vector** | Matrix lists 3.10–3.13 but CI tests 3.12 only; Linux-only while Windows path bugs exist in path handling; `continue-on-error` on one OS. |
| **Anti-gaming guard** | Matrix must be superset of declared support (per P01 R5); import smoke + core test subset on every cell; full suite on primary cell, fast subset on secondary if runtime constrained (documented). |
| **Evidence grade** | **B** |
| **Sources** | GitHub Docs — Building and testing Python (2025–2026); actions/setup-python advanced matrix (v6) |

### Criterion T6 — Canary and metamorphic tests for QA oracle gaps

| Field | Value |
|---|---|
| **Criterion** | Because a QA tool often lacks a single golden oracle for all inputs, the suite includes **metamorphic relations** and **canary cases**: (a) known-bad inputs that **must fail** gates, (b) relation-preserving transforms (e.g., row reorder, whitespace normalization) where declared invariants hold, (c) relation-breaking transforms that **must** change verdicts. |
| **How to measure** | Inventory tests labeled metamorphic/canary/red-team; verify ≥1 test asserts gate **rejects** corrupted fixture; verify ≥1 metamorphic relation across paired inputs (Segura MT pattern: two executions, relation on outputs). For QA tools: tests that **intentionally broken goldens** still fail. |
| **Audit method** | Adversarial / red-team probing (§5.6) + anti-gaming (§5.7) |
| **Scoring hook** | §6.2 **hard gate**: QA tool with zero "must-fail" canary tests cannot be trusted; §6.4 |
| **Gaming vector** | All tests use valid goldens only; canary commented out; metamorphic relation so weak it always passes. |
| **Anti-gaming guard** | CI fails if canary suite passes on deliberately corrupted artifact; rotate canary fixtures periodically; metamorphic relations tied to documented invariants in CLAUDE.md/docs. |
| **Evidence grade** | **A** |
| **Sources** | Segura et al., *Metamorphic Testing: Testing the Untestable*, IEEE Software 2020; GeMTest framework paper (pytest integration); Segura MT survey |

**Limitation surfaced (MT literature):** Metamorphic testing alone cannot prove individual outputs correct, only relation violations. **Audit rule:** pair MT with goldens on curated corpus (P11) and downstream checks (P13).

### Criterion T7 — Property-based tests where invariants dominate examples

| Field | Value |
|---|---|
| **Criterion** | Modules with algebraic invariants (parsers, normalizers, metrics, sort/order, encode/decode round-trips) include **Hypothesis** (or equivalent) property tests alongside example/regression tests; properties are documented; `@example` or `@seed` pins discovered failures. |
| **How to measure** | Grep for `@given` / `st.*` strategies on critical modules; verify round-trip and invariant patterns per Hypothesis tutorial guidance; check `hypothesis` in dev/ci deps; failures shrink to minimal counterexample and are replayable. |
| **Audit method** | Metric construct-validity audit (§5.4) + maturity model |
| **Scoring hook** | §6.1 release-readiness; §6.4 (properties resist example-only gaming) |
| **Gaming vector** | `@given` with overly narrow strategies; properties that restate implementation (tautology); no `@example` for shrunk failures → irreproducible CI. |
| **Anti-gaming guard** | Require strategies at least as wide as public input domain; store Hypothesis `.hypothesis/` examples in repo or use `@example` in test; property tests must fail when implementation stubbed to `pass`. |
| **Evidence grade** | **B** |
| **Sources** | Hypothesis official docs v6.156 (tutorial: when to use PBT); Hypothesis quickstart |

**Contradiction surfaced:** Hypothesis docs state PBT is "not always a replacement" for unit tests. **Resolution rule:** score **complementarity**, not PBT-only suites; example tests remain for regressions and documented edge cases.

### Criterion T8 — Tests run against installed package, not checkout illusion

| Field | Value |
|---|---|
| **Criterion** | CI installs the **built wheel** (or tox env) before test collection so tests exercise packaged layout, entry points, and import paths—not editable `PYTHONPATH` hacks masking packaging defects. |
| **How to measure** | CI step order: `python -m build` → `pip install dist/*.whl` → `pytest`; or tox `usedevelop=false` env. Verify `--import-mode=importlib` per pytest recommendation for src layout. |
| **Audit method** | Conformance checklist + reproducibility replay |
| **Scoring hook** | §6.1 release-readiness (pairs with P01 R4/R11) |
| **Gaming vector** | `pip install -e .` only; tests import from repo root bypassing missing packaged data files. |
| **Anti-gaming guard** | Dedicated CI job `test-installed-wheel`; optional second job for editable dev speed but not as sole gate. |
| **Evidence grade** | **B** |
| **Sources** | pytest *Good Integration Practices* (stable docs, 2025–2026); pytest tox recommendation |

### Criterion T9 — QA tool self-tests its own gates and exit contract

| Field | Value |
|---|---|
| **Criterion** | The tool's **CLI/library gate behavior** is tested as a first-class product surface: exit codes (pass/fail/error) stable and documented; each gate type has tests for accept, reject, and error paths; regression suite covers historical bug/fixtures; "dogfooding" is structured (tests are oracles), not anecdotal. |
| **How to measure** | pytest subprocess tests on CLI with `capsys`; assert return codes; golden-file regression dir under version control; map each documented gate in CLAUDE.md to ≥1 test; verify fail-not-partial behavior on unreachable deps (mocked). |
| **Audit method** | Documentation-completeness audit (§5.9) applied to test coverage of **documented contract** |
| **Scoring hook** | §6.2 gate candidate: undocumented/untested exit-code contract; §6.4 |
| **Gaming vector** | Tests call internal functions only, never CLI; gates tested only on happy path; snapshot tests so broad they never fail. |
| **Anti-gaming guard** | Contract table (gate × input class × expected exit) must be 100% covered; CLI integration tests required for operator-facing commands; internal-only tests cannot satisfy this criterion alone. |
| **Evidence grade** | **B** (pytest patterns Tier 2; oracle/MT theory Tier 1 for QA-without-oracle) |
| **Sources** | Segura MT 2020 (oracle problem); pytest good practices; Bazel Test Encyclopedia (tests confirm repo invariants) |

### Criterion T10 — Flake quarantine with expiry, not silent retry

| Field | Value |
|---|---|
| **Criterion** | Flaky tests are detected (rerun plugins, CI flake rate), **quarantined** with tracked issue, and fixed or removed before expiry; retries are diagnostic (`--reruns` with `--reruns-delay`), not unlimited merge enablers. |
| **How to measure** | Policy for `@pytest.mark.flaky` / quarantine markers; max retry count; flake budget per sprint; no quarantined test on critical gate path without owner+date. |
| **Audit method** | Maturity model + observability audit overlap |
| **Scoring hook** | §6.1 release-readiness; §6.6 uncertainty (flake rate widens score band) |
| **Gaming vector** | Infinite `--reruns 5` on all tests; xfail without issue link; disabling failing matrix cells permanently via `exclude`. |
| **Anti-gaming guard** | Cap reruns at 2 on presubmit; quarantine list in repo with SLA; critical-path tests (T4/T6) may not carry flaky marker. |
| **Evidence grade** | **B** |
| **Sources** | Google SWE Book Ch.23 (flaky tests on presubmit); Fuchsia best practices (repeat 100–1000 locally before merge) |

---

## 3. External benchmark / exemplar bar

### Research-backed professional bar (QA tool / library)

| Maturity level | CI / test signals |
|---|---|
| **0 — Ad hoc** | Manual pytest locally; no CI; coverage unknown. |
| **1 — Baseline** | CI on PR; unit tests; coverage report only. |
| **2 — Professional** | Matrix (OS×Python); hermetic default; wheel install job; strict pytest; diff coverage **without** numeric gate; documented exit-code tests. |
| **3 — QA-tool trusted** | Level 2 + metamorphic/canary **must-fail** tests on gates; mutation or scoped fault injection on gate modules; Hypothesis on invariant-heavy code; flake quarantine policy. |
| **4 — Exemplar** | Level 3 + trend dashboards for mutation kill rate / canary pass rate; nightly full mutation; independent regression corpus job; presubmit/postsubmit tier split per Google CI guidance (fast hermetic presubmit, heavier postsubmit). |

### Tier-1/Tier-2 exemplar signals (public docs only)

| Practice | Serious Python OSS pattern | Research anchor |
|---|---|---|
| Matrix ubuntu+win+pyN | GitHub Actions Python tutorial default | setup-python v6 matrix docs |
| No coverage-only gate | pytest-cov reports, teams pair with review | Inozemtseva & Holmes ICSE 2014 |
| Mutation on critical paths | mutmut scoped paths in mature QA repos | Just et al. FSE 2014 |
| Property tests on parsers/metrics | Hypothesis in scientific Python stacks | Hypothesis official tutorial |
| Hermetic unit tests | Bazel/Fuchsia/Google CI presubmit | Test Encyclopedia hermeticity |
| Metamorphic when oracle missing | Extraction/eval tools with relation tests | Segura IEEE Software 2020 |

**Where not to cargo-cult:** Full-repo mutation on every PR is often too slow for presubmit (Google runs heavier tests postsubmit). Docling-scale matrix breadth may exceed whisker monorepo need, but **declared `requires-python` must match CI** (P01 linkage).

---

## 4. Recommended weight & gate recommendation

| Recommendation | Rationale |
|---|---|
| **Dimension weight: 14%** of composite (within release-readiness cluster with P01/P02) | CI/test maturity is **trust foundation** for a QA tool: if tests lie, gates lie. Weight below eval-science cluster (P09–P13) but above pure packaging metadata because whisker's product *is* quality judgment. |
| **Hard gates (conjunctive): T1, T6** | **T1:** No CI on PR → cannot claim professional engineering. **T6:** QA tool without must-fail canaries has **unproven gate teeth** (self-consistent with whisker's conjunctive guard design; audit rubric must not be weaker). |
| **Hard gate candidate (strongly recommended): T4 on gate/scorer modules** | Mutation kill-rate floor on modules that implement accept/reject thresholds; evidence **A** from Just et al. + industry mutmut practice. |
| **Anti-gates (must NOT be sole hard gates): T2 coverage %** | Inozemtseva & Holmes: coverage as target is **misleading**; enforce as diagnostic only. |
| **Soft cap at level 2 if missing: T3, T5, T8** | Hermeticity, matrix, wheel-install are professional norms; monorepo-private consumption may defer Windows cell temporarily if documented with expiry. |
| **Evidence propagation** | Dimension inherits weakest among T2, T4, T6 load-bearing criteria (target **A** when research-backed gates present). |
| **Contested discount** | Pure coverage thresholds without T4/T6: mark criterion **contested**, reduce dimension confidence per §6.5. |

**Strongest criterion (single best discriminator):** **T6 — Canary and metamorphic tests with must-fail cases.** It directly answers "does this QA tool test its own judgment?" and closes the Goodhart gap that T2 identifies for coverage-only shops. Backed by Tier-1 metamorphic-testing literature (oracle problem) and aligned with §6.4 anti-gaming ("tests exercise the gate's teeth with a canary that must fail").

---

## 5. Sources

### Tier 1 — Authoritative / primary

| ID | Source | URL | Date/version |
|---|---|---|---|
| S1 | Inozemtseva & Holmes — *Coverage Is Not Strongly Correlated with Test Suite Effectiveness* (ICSE) | https://cs.uwaterloo.ca/~rtholmes/papers/icse_2014_inozemtseva.pdf | 2014 (Distinguished Paper) |
| S2 | Just et al. — *Are Mutants a Valid Substitute for Real Faults in Software Testing?* (FSE) | https://doi.org/10.1145/2635868.2635929 | 2014 |
| S3 | Papadakis et al. — *Are mutation scores correlated with real fault detection?* (ICST) | https://doi.org/10.1145/3180155.3180183 | 2018 |
| S4 | Segura et al. — *Metamorphic Testing: Testing the Untestable* (IEEE Software) | https://personal.us.es/sergiosegura/files/papers/segura20-software.pdf | 2020 |
| S5 | Bazel Test Encyclopedia — hermeticity & environment spec | https://bazel.build/reference/test-encyclopedia | Bazel 8.x docs (2025–2026) |
| S6 | ACM TOSEM — *Understanding the Potentially Confounding Effect of Test Suite Size* | https://doi.org/10.1145/3748504 | 2025 |

### Tier 2 — Strong secondary

| ID | Source | URL | Date/version |
|---|---|---|---|
| S7 | Google — *Software Engineering at Google*, Ch.23 Continuous Integration | https://abseil.io/resources/swe-book/html/ch23.html | O'Reilly 2020 |
| S8 | Fuchsia — Testing best practices (hermetic, deterministic) | https://fuchsia.dev/fuchsia-src/contribute/testing/best-practices | current |
| S9 | Hypothesis — Official documentation (when to use PBT) | https://hypothesis.readthedocs.io/en/latest/tutorial/introduction.html | v6.156 (2025–2026) |
| S10 | pytest — *Good Integration Practices* | https://docs.pytest.org/en/stable/explanation/goodpractices.html | stable, 2025–2026 |
| S11 | GitHub Docs — Building and testing Python | https://docs.github.com/en/actions/tutorials/build-and-test-code/python | 2025–2026 |
| S12 | GitHub Docs — Matrix job variations | https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/run-job-variations | 2025–2026 |
| S13 | actions/setup-python — Matrix testing advanced usage | https://github.com/actions/setup-python/blob/main/docs/advanced-usage.md | v6 (2025–2026) |
| S14 | mutmut — Official documentation | https://mutmut.readthedocs.io/en/latest/ | 2025–2026 |
| S15 | Argüelles et al. — *Hermetic, Ephemeral Test Environments at Google* (ICSTW) | https://doi.org/10.1109/icstw58534.2023.00029 | 2023 |
| S16 | GeMTest — Metamorphic testing framework (pytest) | https://mediatum.ub.tum.de/doc/1779593/fp1b4dauqvhferfhponsfrklr.pdf | 2023 |

### Tier 3 — Contextual (corroboration only)

| ID | Source | URL |
|---|---|---|
| S17 | Laws of Software Engineering — Goodhart's Law | https://lawsofsoftwareengineering.com/laws/goodharts-law/ |
| S18 | Increment — *In praise of property-based testing* (Hypothesis author) | https://increment.com/testing/in-praise-of-property-based-testing/ |

**Source count:** 6 Tier-1 + 10 Tier-2 = **16 distinct Tier 1–2 sources** (floor ≥3 satisfied).

**Contradictions logged for synthesis:**
1. Coverage useful for gap analysis (S1) vs org habit of coverage gates (S17 contextual).
2. Mutation score predicts faults (S2) but cannot simulate all real faults (~20% gap, S2).
3. PBT complements unit tests (S9) vs pressure to replace examples entirely.
4. Hermetic presubmit ideal (S5, S7) vs need for occasional live integration (Google: postsubmit or quarantined).

---

## 6. Overlap statement

This persona researched **external CI/CD and test-suite maturity standards only**. It did **not** open whisker production code, cite whisker `file:line`, score whisker, clone/fork/copy code, or duplicate:

- **`persona/`** — prior code-level "test-suite-auditor" findings on whisker's deterministic core.
- **`llm-stack/`** — advisory LLM lane code audits (tapetum isolation, schema tests).
- **`redteam/`** — per-converter adversarial reports (this persona defines **method** for canary/metamorphic gates, not converter scores).
- **`buildvsbuy/`** — library-choice decisions for metric implementations.
- **`p19-anti-gaming-goodhart.md`** (future) — this persona supplies **test-specific** Goodhart evidence (coverage/mutation); P19 generalizes anti-gaming rules for all metrics.

Boundary held: **external test-maturity criteria and bar**, handed to synthesis as rubric inputs for the release-readiness / trust dimension.
