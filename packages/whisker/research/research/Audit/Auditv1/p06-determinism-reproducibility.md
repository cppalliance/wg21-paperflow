# P06 — Determinism & Reproducibility Standards Researcher

**Persona:** 6 (Cluster B — Architecture & hybrid deterministic+LLM design)  
**Date:** 2026-07-18  
**Scope:** External standards and verification methods only. No whisker production-code inspection, no whisker verdict.

---

## 1. Question restated

What external bar should a professional hybrid QA pipeline use to **claim**, **document**, and **verify** determinism and reproducibility? Specifically:

- How do authoritative sources distinguish **repeatability**, **reproducibility**, and **replicability**, and what precision do they require (bit-exact vs stated tolerance vs quality-stable)?
- What are the documented **sources of run-to-run variance** (concurrency, unordered iteration, floating-point non-associativity, PRNG/seed drift, environment drift, hosted-LLM batching)?
- What **verification methods** (rerun-and-diff, idempotency replay, metamorphic relations, variance metrics) prove or falsify a determinism claim?
- How should a system that mixes a **strict deterministic core** with **nondeterministic advisory components** scope its guarantees without conflating tiers?

This persona supplies audit **criteria and an external bar** for the synthesis rubric. It does not score whisker.

---

## 2. Proposed audit criteria

Each criterion includes: how to measure, audit method(s) from `00-FRAME.md` §5, scoring-design hook from §6, gaming vector + anti-gaming guard, evidence grade, and Tier 1–2 citations.

### Criterion 2.1 — Publish a reproducibility tier taxonomy and map every output path to exactly one tier

**Statement:** The package must declare, in operator-facing docs, which outputs are guaranteed at which tier. Minimum tier set (synthesized from ACM artifact policy, HPC survey, and ML practice):

| Tier | Guarantee | Typical comparator | When acceptable |
|------|-----------|-------------------|-----------------|
| **T0 — Bit-exact replay** | Same inputs + pinned environment → byte-identical artifacts | `diff`, cryptographic hash, structural equality | Deterministic core gates, regression goldens, bisect/debug baselines |
| **T1 — Quality-stable / semantic replay** | Same inputs → same verdicts, structure, and ranked outcomes; numeric fields may differ within documented tolerance | Schema-level equality on gate verdicts; tolerance-bounded numeric fields; no flip of pass/fail | Analytical pipelines where bit-exact is infeasible on hosted GPU/LLM paths but findings must be stable |
| **T2 — Stated-precision reproduction (ACM-style)** | Independent rerun reproduces **main claims** within declared tolerance; exact replication not required | Claim-level equivalence; main metrics within ε | Benchmark papers, cross-machine reproduction |
| **T3 — Non-guaranteed / advisory** | Reruns may differ; output is explicitly non-authoritative | Stability statistics only (flip rate, agreement) | LLM advisory overlays, judge lanes |

**How to measure:** Documentation matrix: every CLI exit path, artifact type (`*.md`, trace, debug, JSON verdict), and lane (deterministic vs advisory) maps to T0–T3. Synthesis checks for **no silent default** (undocumented tier = audit fail).

**Audit method:** Conformance checklist (§5.1) + maturity model (§5.2).

**Scoring hook:** §6.1 dimension **determinism** sub-criteria; §6.2 candidate **hard gate** when a T0 claim exists but replay refutes it.

**Gaming vector:** Label everything T2/T3 to avoid hard replay obligations.

**Anti-gaming guard:** Tier assignment is binding: T0 paths must have automated replay tests (Criterion 2.5); T3 paths must be labeled **advisory-only** and barred from gating (feeds hybrid-architecture persona P05/P07).

**Evidence grade:** **A** (converging Tier 1: ACM badging + peer-reviewed HPC survey + PyTorch official limits).

**Sources:** ACM Artifact Review and Badging v1.1; Antunes & Hill 2024; PyTorch Reproducibility notes.

---

### Criterion 2.2 — Pin the reproducibility envelope (environment, versions, seeds, ordering)

**Statement:** Repeatable computation requires documenting and pinning everything that affects outputs: code revision, dependency lockfiles, Python version, optional GPU/driver notes, explicit RNG seeds, and **iteration order** over unordered collections.

**How to measure:** Checklist derived from artifact-evaluation and HPC practice:

1. **Artifacts available:** scripts, configs, and inputs sufficient for an independent party to rerun (ACM *Artifacts Available* / *Results Validated* bar).
2. **Version pinning:** lockfiles or exact version pins; no floating `latest` in CI or release paths.
3. **Seed contract:** every stochastic step names seed source and scope (global vs per-paper vs per-chunk).
4. **Ordering contract:** sets/dicts/maps that feed prompts, gates, or merges are sorted or otherwise canonically ordered before use (determinism doctrine for hybrid pipelines).
5. **Environment capture:** CI records OS, Python, and key native libs; container digest or equivalent when used.

**Audit method:** Conformance checklist (§5.1) + reproducibility replay setup (§5.8).

**Scoring hook:** §6.1 determinism maturity levels 0–4; §6.3 evidence grade on whether pins are **verified by replay** vs merely documented.

**Gaming vector:** "We document seeds" without pinning deps or iteration order.

**Anti-gaming guard:** Require a **replay manifest** (single file or CI artifact) emitted on every run listing resolved versions + seed + git SHA; auditor diff manifest across two replays.

**Evidence grade:** **A** (ACM artifact policy + NIST numerical reproducibility program + Antunes & Hill 2024 on workflow/version loss).

**Sources:** ACM Artifact Review and Badging; NIST Numerical Reproducibility; Antunes & Hill 2024.

---

### Criterion 2.3 — Maintain a variance-source inventory with containment per source

**Statement:** Mature pipelines catalog known nondeterminism sources and state containment for each. Minimum inventory (from HPC/DL and LLM-inference literature):

| Source | Mechanism | Containment strategies |
|--------|-----------|------------------------|
| Floating-point non-associativity | Parallel reduction order changes bitwise sums | Fixed reduction order; deterministic parallel sums; higher precision in sensitive reductions |
| GPU atomic reductions | Nondeterministic accumulation order | Deterministic alternatives; avoid atomics in verified paths |
| Unordered iteration (`set`, hash maps) | Prompt/gate order drift | Sort keys before consumption |
| Concurrency / race | Shared mutable state | Serial execution; hermetic tests; isolation |
| PRNG | Unseeded or cross-test leakage | Explicit seeds; injectable RNG in tests |
| Dynamic LLM batching | Batch-size-dependent kernels (**batch invariance** failure) | Batch-invariant kernels; serial in-flight=1; offline batch |
| Environment drift | Different PyTorch/CUDA/driver | Pin versions; document non-guarantee across releases (PyTorch explicitly warns cross-release non-guarantee) |
| Time / async / remote I/O | Flaky ordering | Test doubles; injected clocks; Fowler quarantine |

**How to measure:** Written inventory in docs with **(source → affected paths → tier → containment → test ID)** rows. Auditor verifies each T0 path has a row and a linked test.

**Audit method:** Maturity model (§5.2) + reproducibility replay (§5.8).

**Scoring hook:** §6.1 determinism; §6.4 anti-gaming (inventory must be live, not boilerplate).

**Gaming vector:** Generic paragraph "floating point may vary" with no path mapping.

**Anti-gaming guard:** Spot-audit: pick one T0 path, trace inventory row to a failing replay test when containment is disabled (fault injection).

**Evidence grade:** **A** (Shanmugavelu et al. 2024 FPNA; He & Thinking Machines Lab 2025 batch invariance; PyTorch reproducibility).

**Sources:** arXiv:2408.05148; Thinking Machines Lab 2025; PyTorch Reproducibility.

---

### Criterion 2.4 — Separate run-to-run determinism from batch-/load-determinism (LLM and GPU serving)

**Statement:** For hosted or batched LLM inference, **run-to-run deterministic kernels are insufficient**. A separate guarantee — **batch invariance** — is required for user-visible determinism at temperature 0: per-request outputs must not depend on batch size, batch position, or concurrent load.

**How to measure:**

1. Docs state whether LLM paths are T0, T1, or T3.
2. If any path claims T0/T1 with LLM: evidence of batch-invariant execution **or** serial single-flight inference with fixed batch size 1.
3. Empirical probe (external bar): N≥100 identical prompts at temperature 0; report unique output count (Thinking Machines benchmark pattern: default kernels → many uniques; batch-invariant → 1 unique).

**Audit method:** Reproducibility replay (§5.8) + comparative benchmarking (§5.3) against vLLM batch-invariance and Thinking Machines baselines.

**Scoring hook:** §6.2 **hard gate** candidate: "determinism claim at LLM boundary" falsified by batch-variance probe.

**Gaming vector:** Test LLM determinism only offline with batch size 1 while production uses dynamic batching.

**Anti-gaming guard:** Replay tests must include **load proxy** (minimum: two batch sizes or concurrent request fixture) for any T0/T1 LLM claim.

**Evidence grade:** **A** (Thinking Machines Lab 2025 primary; vLLM official batch-invariance docs Tier 2 corroboration).

**Sources:** He & Thinking Machines Lab 2025; vLLM Batch Invariance docs.

---

### Criterion 2.5 — Reproducibility replay suite (rerun-and-diff) with tier-appropriate comparators

**Statement:** Determinism claims must be verified by automated **rerun-and-diff**, not by narrative. Protocol:

1. **Select fixtures:** representative corpus slice covering each modality and gate family.
2. **Run R≥2** (recommend R=3 for CI, R≥10 for calibration studies) with identical inputs and pinned manifest.
3. **Compare:**
   - T0: byte-identical or canonical serialized equality (hash of normalized output).
   - T1: structural equality on gate verdicts + bounded numeric deltas; **zero** pass↔fail flips.
   - T2: claim-level metrics within documented ε (ACM *Results Validated* tolerance, not necessarily bitwise).
4. **Report:** pass rate, diff artifacts, max drift, flip count.
5. **Idempotency variant (data-pipeline bar):** run twice back-to-back; row counts and content hashes unchanged (merge/upsert idempotency pattern).

**Audit method:** Reproducibility replay (§5.8) — primary method for this persona.

**Scoring hook:** §6.2 hard gate: any T0 replay failure; §6.6 score uncertainty driven by replay pass rate variance.

**Gaming vector:** Golden test with R=1; compare with loose `allclose` defaults that hide gate flips.

**Anti-gaming guard:** Tests named by tier (`test_replay_T0_*` uses `==`/hash; `test_replay_T1_*` asserts verdict stability first); CI fails on any T0 mismatch; metamorphic canary that **must** fail if ordering guard removed.

**Evidence grade:** **A** (ACM Results Validated + idempotency replay practice + Antunes & Hill on bitwise debugging need).

**Sources:** ACM Artifact Review and Badging; Antunes & Hill 2024; Martin Fowler 2011 (quarantine/flake discipline, Tier 3 contextual for CI).

---

### Criterion 2.6 — CI and test-suite determinism hygiene (no flaky gate tests)

**Statement:** Tests that enforce determinism must themselves be deterministic. Non-deterministic tests erode trust in the entire regression suite (Fowler: "virulent infection").

**How to measure:**

1. Hermetic unit/integration tests for deterministic core (no network, no wall clock, no shared mutable global state).
2. **Quarantine policy** for flaky tests: separate suite, time-boxed fix, numeric cap — never "re-run until green" on gate tests.
3. Property/metamorphic tests use **recorded seeds** for failure reproduction (CockroachDB / metamorphic testing pattern).
4. CI matrix documents OS/Python versions; gate jobs use frozen deps.

**Audit method:** Conformance checklist (§5.1) + maturity model (§5.2).

**Scoring hook:** §6.4 anti-gaming: "has tests" → "gate tests are flake-free at R consecutive CI runs".

**Gaming vector:** High coverage with quarantined gate tests permanently disabled.

**Anti-gaming guard:** Gate-test flake rate metric public in CI; >0% flake on T0 tests = maturity cap.

**Evidence grade:** **B** (Fowler Tier 3 + ACM artifact exercisability Tier 1 for CI artifact bar).

**Sources:** Martin Fowler, *Eradicating Non-Determinism in Tests* (2011); ACM Artifact Review and Badging.

---

### Criterion 2.7 — Numeric reproducibility: declare FP policy and use deterministic reductions where T0 is claimed

**Statement:** Parallel floating-point reductions are a primary bitwise variance source. T0 paths must use fixed-order reductions or verified deterministic kernels; otherwise downgrade tier to T1 with explicit tolerance.

**How to measure:** For each numeric gate: document dtype, reduction order, use of deterministic PyTorch mode (`torch.use_deterministic_algorithms(True)` where applicable), and known exceptions (PyTorch documents ops that remain nondeterministic or lack deterministic implementations). Quantify variance with metrics such as elementwise relative mean absolute variation (Shanmugavelu et al.) when comparing deterministic vs default kernels.

**Audit method:** Metric construct-validity audit (§5.4) applied to **variance metrics** + reproducibility replay (§5.8).

**Scoring hook:** §6.1 determinism; §6.5 disagreement handling when ACM "stated precision" conflicts with HPC "bitwise for debugging" — synthesis must record both (see §3).

**Gaming vector:** Claim T0 on GPU without enabling deterministic algorithms or documenting exceptions.

**Anti-gaming guard:** Automated scan of replay diffs at bitwise level; any nondeterministic op in T0 call graph without documented exception → fail.

**Evidence grade:** **A** (Shanmugavelu et al. 2024; PyTorch Reproducibility; NIST numerical reproducibility).

**Sources:** arXiv:2408.05148; PyTorch Reproducibility; NIST Numerical Reproducibility.

---

### Criterion 2.8 — Hybrid boundary: deterministic core outputs must not depend on advisory reruns

**Statement:** When an advisory LLM lane exists, the **authoritative deterministic artifact** (gate verdict, exit code, structured gate state) must be computable without LLM invocation and must not change when the advisory layer is re-run or omitted.

**How to measure:**

1. **Dual replay:** Run A = core-only; Run B = core + advisory; gate verdicts and exit codes identical.
2. **Advisory instability metric:** N reruns of advisory layer; report flip rate separately (T3), never merged into core diff.
3. Documentation states one-way data flow: core → optional advisory display, never advisory → core threshold.

**Audit method:** Reproducibility replay (§5.8) + architecture conformance (feeds P05).

**Scoring hook:** §6.2 hard gate: advisory signal mutates core gate or exit code.

**Gaming vector:** Core "determinism" tested only with LLM disabled once, while production couples them.

**Anti-gaming guard:** CI job matrix includes `{llm=off, llm=on, llm=rerun×5}` with core artifact hash equality.

**Evidence grade:** **B** (Thinking Machines on eval/RL need for stable core + ACM separation of claims; hybrid pattern inferred from batch-invariance eval discipline).

**Sources:** He & Thinking Machines Lab 2025; ACM Artifact Review and Badging.

---

## 3. External benchmark / exemplar bar

### 3.1 Terminology and precision (what "good" looks like)

**ACM Artifact Review and Badging (v1.1)** distinguishes repeatability (same team), reproducibility (different team, same artifacts, **stated precision**), and replicability (different team, independent artifacts). For *Results Validated / Reproduced*, exact replication is **not** required; results must agree within tolerance such that **main claims still hold**. That is the canonical **quality-stable / claim-level** bar for published computational science.

**Antunes & Hill (2024)** survey HPC reproducibility and surface an important tension: classical deterministic computing often needs **bitwise-identical** reruns for debugging, especially under parallelism, while ACM/NISO definitions allow **stated precision**. A professional hybrid QA package should **explicitly adopt both** as T0 and T2 rather than eliding the conflict.

**PyTorch official documentation** sets a sober ceiling: completely reproducible results are **not guaranteed** across releases, platforms, or CPU vs GPU even with identical seeds; determinism requires `torch.use_deterministic_algorithms(True)` plus seed control, and still may exclude some ops. Exemplar bar: **honest tier labeling** beats over-claiming bit-exact cross-platform ML.

### 3.2 Verification exemplars

| Exemplar | Bar | Transferable practice |
|----------|-----|------------------------|
| ACM AEC / Results Reproduced | Independent rerunner validates main claims with artifacts | Replay scripts + tolerance table tied to claims |
| Data pipeline idempotency tests | Double-run row/hash equality | Rerun-and-diff integration tests on QA outputs |
| Shanmugavelu et al. FPNA study | Quantified bitwise variance metrics; deterministic GPU sum replacements | Measure variance before accepting T1 tolerance |
| Thinking Machines + vLLM batch invariance | 1000× greedy decode → 1 unique output when batch-invariant | Load-sensitive LLM determinism probe |
| Fowler flake discipline | Quarantine nondeterministic tests | CI trust for gate suite |

### 3.3 Contradictions surfaced (not hidden)

1. **Bit-exact vs stated precision:** HPC debugging culture (Antunes & Hill) vs ACM artifact badges — resolve by tier taxonomy (Criterion 2.1), not by picking one silently.
2. **"Deterministic forward pass" vs user-visible nondeterminism:** Thinking Machines shows server-internal determinism can coexist with user-visible variance without batch invariance — audits must test at the **operator-visible boundary**.
3. **PyTorch determinism flag vs full reproducibility:** Enabling deterministic algorithms is necessary but not sufficient (PyTorch docs) — inventory + replay still required.

---

## 4. Recommended weight & hard gate rationale

### 4.1 Recommended weight (determinism dimension)

Recommend **determinism / reproducibility** receive **12–18%** of composite weight in the synthesis rubric (mid-high among architecture-adjacent dimensions), with sub-weights:

| Sub-criterion | Suggested share of determinism dimension |
|---------------|------------------------------------------|
| 2.1 Tier taxonomy | 15% |
| 2.2 Environment pin | 15% |
| 2.3 Variance inventory | 10% |
| 2.4 Batch invariance / LLM boundary | 20% |
| 2.5 Replay suite | 25% |
| 2.6 CI flake hygiene | 5% |
| 2.7 FP / numeric policy | 5% |
| 2.8 Hybrid core/advisory isolation | 5% |

**Rationale:** Replay verification (2.5) and tier honesty (2.1) are the load-bearing evidence; inventory and pins are necessary preconditions; LLM batch invariance (2.4) and hybrid isolation (2.8) are decisive for hybrid QA architectures cited in Stage 0 objective.

Evidence for weighting shape: ACM makes **results validation** a badge independent of packaging; Collberg-style CS reproduction studies (~30% reproducible) show determinism documentation is a common failure mode — under-weighting invites false professional-grade verdicts.

### 4.2 Hard gates (non-compensatory)

Recommend **three conjunctive hard gates** for overall audit pass:

1. **Replay refutes T0 claim:** Any documented T0 path fails rerun-and-diff at R≥2 with pinned manifest → **fail** (mirrors `00-FRAME.md` §6.2 candidate gate: "determinism claim that replay refutes").
2. **Advisory mutates core:** LLM or advisory rerun changes deterministic gate verdict, exit code, or persisted gate state → **fail**.
3. **Missing tier map:** Any authoritative output path lacks T0–T3 classification → **fail** (cosmetic determinism language without binding tiers).

Weighted score cannot override these gates.

---

## 5. Sources (tiered)

### Tier 1 — Authoritative / primary

| # | Source | URL | Date / version | Used for |
|---|--------|-----|----------------|----------|
| S1 | ACM, *Artifact Review and Badging Policy* (current v1.1) | https://reviewers.acm.org/training-course/artifact-review-and-badging | v1.1 (current policy page) | Repeatability/reproducibility/replicability; Results Validated tolerance; artifact exercisability |
| S2 | ACM SIGSAC CCS, *Call for Artifacts* (Results Reproduced criteria) | https://www.sigsac.org/ccs/CCS2025/call-for-artifacts/ | CCS 2025 | Independent rerun within tolerance; claim validation bar |
| S3 | Antunes, B. & Hill, D.R.C., *Reproducibility, Replicability and Repeatability: A survey…* (Computer Science Review) | https://doi.org/10.1016/j.cosrev.2024.100655 | 2024 | Terminology standardization; bitwise vs stated precision tension; HPC variance sources |
| S4 | Shanmugavelu, S. et al., *Impacts of floating-point non-associativity on reproducibility for HPC and deep learning applications* | https://arxiv.org/pdf/2408.05148 | 2024 | FPNA mechanisms; deterministic reduction; variance metrics; PyTorch GPU nondeterminism |
| S5 | NIST, *Numerical Reproducibility* program | https://www.nist.gov/programs-projects/numerical-reproducibility | Active program (accessed 2026-07-18) | Catalog of platform attributes breaking bitwise reproducibility; UQ for numerical drift |
| S6 | He, H. & Thinking Machines Lab, *Defeating Nondeterminism in LLM Inference* | https://thinkingmachines.ai/blog/defeating-nondeterminism-in-llm-inference/ | 2025-09-10 (DOI 10.64434/tml.20250910) | Batch invariance definition; load-driven nondeterminism; 1000× replay empirical bar |

### Tier 2 — Strong secondary

| # | Source | URL | Date / version | Used for |
|---|--------|-----|----------------|----------|
| S7 | PyTorch, *Reproducibility* / `torch.use_deterministic_algorithms` | https://docs.pytorch.org/docs/stable/notes/randomness.html | PyTorch stable docs (accessed 2026-07-18) | Seed control; deterministic algorithm mode; cross-release/platform limits |
| S8 | vLLM, *Batch Invariance* | https://docs.vllm.ai/en/stable/features/batch_invariance/ | vLLM stable docs (accessed 2026-07-18) | `VLLM_BATCH_INVARIANT=1`; engineering containment for serving determinism |

### Tier 3 — Contextual (not load-bearing alone)

| # | Source | URL | Date | Used for |
|---|--------|-----|------|----------|
| S9 | Martin Fowler, *Eradicating Non-Determinism in Tests* | https://martinfowler.com/articles/nonDeterminism.html | 2011 | CI flake quarantine discipline |

**Distinct Tier 1–2 primaries cited for criteria:** 8 (S1–S8). **Minimum floor (≥3):** satisfied.

---

## 6. Overlap statement

This persona researched **external determinism and reproducibility standards and verification methods only**. It did **not**:

- Open, inspect, or score whisker production code (`packages/whisker/src/**`).
- Cite whisker `file:line` or reach any whisker pass/fail verdict.
- Re-derive findings from the **`persona/`** swarm (deterministic-core code audit: metrics, gates, TEDS/NID/MHS, calibration, corpus) or the **`llm-stack/`** swarm (tapetum LLM lane isolation, injection defense, cascade).
- Duplicate **`llm-batching/`** throughput research (batch endpoints/concurrency tuning excluded per roster).
- Clone, fork, or copy code from exemplar repositories.

It operates one level up: **method and external benchmark** for determinism/reproducibility, handing the synthesis a rubric for the determinism dimension and candidate hard gates. Reconciliation of dual determinism doctrines (user vs Sean) is explicitly owned by **P07**, not this file.

---

## Return metadata (dispatch)

| Field | Value |
|-------|-------|
| **Tier 1–2 source count** | **8** distinct primaries (S1–S8) |
| **Strongest criterion** | **2.5 — Reproducibility replay suite (rerun-and-diff) with tier-appropriate comparators** — directly falsifies determinism claims, implements ACM *Results Validated* discipline, and anchors the recommended hard gate when T0 replay fails |
