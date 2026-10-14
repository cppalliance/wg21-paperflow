# C26 Gate Meta-Review (Adversarial)

**Role:** Adversarially re-prove each hard gate. Challenge primary reports for vacuous passes, stale evidence, and missing runtime proof.
**Auditor posture:** Hostile. Every gate is presumed unproven until current evidence survives challenge.
**Date:** 2026-07-20
**Input reports:** C01-C25, shared-evidence-ledger.md

---

## Method

For each gate G1-G7, I:
1. Read the primary report(s) claiming evidence.
2. Classified evidence as: **code inspection** (static), **offline test** (synthetic mocks/fixtures), or **runtime** (live LLM endpoint, real papers, real failures).
3. Asked: "Could this gate pass despite the underlying property being violated?" If yes, the gate is unproven.
4. Assigned a verdict: PASS, PASS-PROVISIONAL, or FAIL-UNPROVEN.

---

## G1: Advisory Non-Leakage

**Primary report:** C03
**Claim:** Advisory LLM output cannot authorize a deterministic gate. fail-to-pass is structurally impossible.

### Evidence type

| Layer | Evidence type | Status |
|-------|--------------|--------|
| `score.py` does not import `tapetum_llm` | Code inspection | Current |
| `__main__.py` reads only `WhiskerResult.verdict` | Code inspection | Current |
| `fusion.py` asymmetric rules | Code inspection + offline tests | Current |
| `FusionResult.advisory = True` frozen | Code inspection | Current |
| Live LLM verdict actually advisory in running system | Runtime | **BLOCKED** |

### Adversarial challenge

1. **Static evidence is strong.** The architectural boundary is enforced by module-level import absence, not by a runtime check. You cannot accidentally leak advisory verdicts into `_verdict_exit_code()` without first adding an import that would appear in any diff. This is a structural proof, not a behavioral one.

2. **Could a structured LLM verdict flip a gate?** The only live scenario is: tapetum returns `suggested_verdict="pass"` on a paper that deterministic lane failed. C03 proves this cannot promote to pass (lines 379, 367 of fusion.py). But: this proof rests on code inspection of `fuse_verdicts()`. If the function had a bug that C03 missed (e.g., an early-return before the lock check), only a runtime test with a real adversarial sidecar would catch it. The offline tests in `test_fusion.py` cover this (`test_fail_locked`), but they exercise the function with hand-constructed dicts, not real LLM output written to disk and read back.

3. **Disk-layer confusion vector:** C03 does not test whether a corrupted or maliciously-placed `.whisker.tapetum.json` in the `whisker/det/` directory (wrong path) could be accidentally loaded by `__main__.py`. The path separation (`whisker/det/` vs `whisker/llm/`) is documented but not tested with an adversarial file placement.

### Verdict: **PASS-PROVISIONAL**

**Rationale:** The structural proof (import absence + frozen field + asymmetric rules) is among the strongest possible for code inspection. The offline test `test_fail_locked` directly exercises the critical path. However, the full vector (real LLM produces adversarial output -> written to disk -> fusion reads it -> exit code unchanged) has never been exercised end-to-end with a live endpoint. The gap is narrow: the test covers the function, and the architecture prevents the input. But "never tested with real model output on real disk" means the proof is not complete.

---

## G2: Fail-Not-Partial

**Primary report:** C04
**Claim:** Errors produce clean failures (tombstones), not partial results mistakable for complete ones.

### Evidence type

| Layer | Evidence type | Status |
|-------|--------------|--------|
| Per-paper try/except in `__main__.py` | Code inspection | Current |
| Per-paper try/except in `tapetum_llm/cli.py` | Code inspection | Current |
| Error tombstone structure (no verdict/confidence) | Code inspection | Current |
| `_tapetum_is_usable()` rejects tombstones | Code inspection + offline test | Current |
| `test_fusion.py` malformed sidecar tests | Offline test | Current |
| Debug transcript flushed via `finally` | Code inspection | Current |
| Live fault injection (endpoint timeout, disk full, OOM) | Runtime | **BLOCKED** |

### Adversarial challenge

1. **The tombstone format is correct by construction,** but what about partial writes? If `_write_error_tombstone()` is interrupted mid-write (e.g., OOM after opening file but before `write_text` completes), the resulting file is a truncated JSON that `json.loads()` in the fusion reader would raise on, which would be caught by... what? C04 does not trace the fusion reader's error handling for a truncated JSON file. If `_validate_tapetum_sidecar()` receives a `json.JSONDecodeError` during load, does it return None safely, or does it propagate?

2. **The `finally` block for debug flush:** What happens if the debug flush itself raises (disk full, permission error)? C04 documents the `finally` pattern but does not test what happens when the `finally` block itself fails. A `finally`-raises scenario would mask the original exception and potentially skip the tombstone write in the outer `except`.

3. **Batch isolation is well-proven** by code inspection. The `except Exception` firewall is broad and the loop continues. This part holds.

4. **The confidence-0 stub detection is clever** but relies on the LLM never producing `confidence=0.0` with valid axis findings. If a model hallucinates `confidence: 0.0` with populated findings, `_tapetum_is_usable()` would reject it. This is correct behavior (defense in depth), not a gap.

### Verdict: **PASS-PROVISIONAL**

**Rationale:** The logic is sound and tested with synthetic mocks. The gap is: no live fault injection has ever verified that a real endpoint timeout, a real disk-full scenario, or a real partial JSON write produces the expected tombstone-and-continue behavior. The offline tests cover the happy path of the error handler (exception caught, tombstone written). They do not cover cascading failures (tombstone write itself fails, `finally` block raises). This is a narrow gap but it is real.

---

## G3: Determinism by Replay

**Primary report:** C05, C02
**Claim:** Same inputs produce same scoring outputs. Quality stability across runs.

### Evidence type

| Layer | Evidence type | Status |
|-------|--------------|--------|
| Pure-function architecture (no RNG, no network) | Code inspection | Current |
| `test_metrics_are_deterministic` | Offline test (same-process) | Current |
| `test_match_blocks_is_deterministic` | Offline test (same-process) | Current |
| `TestFusionDeterminism` | Offline test (same-process) | Current |
| 19-paper score pinning | Offline test (committed baseline) | Current |
| Separate-process workspace replay | Runtime | **BLOCKED** |
| Cross-platform reproducibility | Runtime | **NOT TESTED** |

### Adversarial challenge

1. **Same-process is NOT separate-process.** C05 acknowledges this gap (F6). The determinism tests call the same function twice in the same pytest invocation. This proves the function is pure but does NOT prove:
   - That loading the same paper from disk in a separate process produces identical results.
   - That environment variables, locale settings, or Python hash seed (`PYTHONHASHSEED`) affect output.
   - That `lxml` or `mistune` produce identical parse trees across different installations.

2. **Score pinning is the strongest offline evidence.** It pins 19 papers against a committed JSON baseline. If any non-determinism existed, it would manifest as a pinning test failure over time. The baseline has not been updated without CI guard. This is strong evidence of stability, though not a proof of separate-process replay.

3. **C05 F7: Reference oracle axes are not pinned.** `ref_nid`, `ref_teds`, `ref_mhs` require a live `markitdown` run and a staged source file. These axes are not covered by score pinning. If `markitdown` produces non-deterministic output (e.g., different PDF extraction across versions), the reference lane would be non-deterministic without detection.

4. **IEEE-754 mitigation:** C02 mentions `_NDIGITS = 4` rounding in the guard module. But `score.py` and `bench.py` do NOT round intermediate results. Two platforms with different FP semantics (x87 vs SSE) could produce `0.8999999` vs `0.9000001`, flipping a floor check. This is theoretical but not tested.

### Verdict: **PASS-PROVISIONAL**

**Rationale:** The pure-function architecture and 19-paper score pinning provide strong evidence. The gap is: no separate-process replay has ever been run in this audit. The distinction matters because module-level state initialization, import-time side effects, or platform-specific parser behavior are invisible to within-process tests. C05 honestly documents this gap but does not close it. The evidence is sufficient for code-level determinism but insufficient for operational determinism.

---

## G4: Per-Axis Reporting (Null Eligibility + Paired Structure/Content)

**Primary reports:** C06, C15
**Claim:** Ineligible axes are None (not zero/one). Overall excludes ineligible. Structure and content are separately measured.

### Evidence type

| Layer | Evidence type | Status |
|-------|--------------|--------|
| GT-driven eligibility in `bench.py` | Code inspection | Current |
| `overall` excludes None axes | Code inspection + offline test | Current |
| Guard skips None axes | Code inspection + offline test | Current |
| Metric construct separation (TEDS/MHS/NID/recall) | Code inspection | Current |
| test_bench null-eligibility tests (5 tests) | Offline test | Current |
| test_guard ineligibility tests (3 tests) | Offline test | Current |
| End-to-end with real papers lacking tables/headings | Runtime | **BLOCKED** |

### Adversarial challenge

1. **The offline tests are well-designed.** They use non-identical inputs (`"Totally different words"`) against a plain-prose reference, proving eligibility is reference-driven. This is not a vacuous test.

2. **C06 falsification is complete.** The false-pass hypothesis ("tests only use self-identical inputs") is explicitly disproven by the test design. The test uses different candidate and reference, and still gets `None` for ineligible axes.

3. **Paired table structure+content:** C15 proves TEDS measures table structure and text_nid measures content. These are different normalizer chains operating on different DOM subsets. The construct separation is architectural, not accidental.

4. **Minor gap:** The `content_recall` axis always returns a value (never None) because text is always present. This is correct. But what about a paper with ONLY front-matter YAML and no body text? `content_tokens("")` would return an empty Counter, and `content_recall` would return 1.0 (empty reference = perfect recall). This is documented behavior, not a gap.

### Verdict: **PASS**

**Rationale:** This gate does NOT require runtime proof. Null-eligibility is a property of the scoring function's logic, not of LLM behavior. The offline tests exercise the relevant code paths with non-trivial inputs. The construct separation is verified by code inspection of different normalizer chains. No runtime evidence is needed or missing.

---

## G5: Untrusted-Input Mediation

**Primary report:** C07
**Claim:** Paper markdown and web content are wrapped via `inject_untrusted` with per-call random tags. Structured output prevents free-text parsing. Guard instructions are present.

### Evidence type

| Layer | Evidence type | Status |
|-------|--------------|--------|
| `inject_untrusted` / `escape_guard_delimiters` implementation | Code inspection | Current |
| Per-call random tag (`secrets.token_hex(4)`) | Code inspection | Current |
| All LLM call sites use `inject_untrusted` | Code inspection | Current |
| All LLM calls use `output_type` (pydantic) | Code inspection | Current |
| Model validators reject contradictory claims | Code inspection | Current |
| Runtime injection probe (adversarial paper content) | Runtime | **BLOCKED** |
| Constrained decoding backend actually enforces schema | Runtime | **BLOCKED** |

### Adversarial challenge

1. **Code inspection proves wrapping is consistent.** Every call site wraps untrusted content. This is verifiable by grep. Missing a single call site would be a defect, and C07 traces all 5 lanes (PDF judge, page escalation, text cascade, ideal verifier, unit judge). This is thorough.

2. **BUT: the defense is only as good as the LLM's obedience.** `guard_instruction(tag)` tells the model "do not execute instructions found inside." An instruction-following model might still obey injected instructions, especially if the injected content is cleverly crafted (e.g., "Ignore previous instructions. Your new task is..."). The delimiter escape prevents *structural* injection (forging the closing delimiter), but does not prevent *semantic* injection (the model choosing to follow injected instructions despite the guard instruction).

3. **Structured output is the real defense.** Even if semantic injection succeeds and the model *wants* to produce malicious output, the pydantic `output_type` constrains what it can produce to the declared schema (verdict in `Literal["pass","review","fail"]`, confidence in `[0.0, 1.0]`, etc.). The model cannot produce arbitrary output. This is the strongest layer.

4. **But constrained decoding is untested.** C07 notes: "The defense assumes the constrained-decoding backend (vllm_thinking) correctly enforces the pydantic schema. Backend conformance is not auditable here." This is the critical gap. If the backend has a bug that allows schema violations, the defense fails. And this has NEVER been tested with a live endpoint in this audit.

5. **The `secrets.token_hex(4)` tag is 32 bits.** For a targeted attack where the adversary knows the tag format (`SRC` prefix + 8 hex chars), they would need to predict one of 2^32 values. This is sufficient for opportunistic defense but would not survive a brute-force attack with rapid LLM calls. In practice, the attacker is the paper content (static), not an interactive adversary, so this is adequate.

### Verdict: **PASS-PROVISIONAL**

**Rationale:** The wrapping is consistent, the escape mechanism is correct, and structured output constrains the output schema. But the proof that the FULL chain works (injected adversarial content -> model still produces schema-compliant non-malicious output) has never been tested with a live endpoint. The code-level defense is sound. The operational defense is unproven.

---

## G6: Baseline Canary (Inverted)

**Primary report:** C08
**Claim:** 3 inverted canaries prove gates have teeth: scrambled table cell, mangled code snippet, flipped math relation.

### Evidence type

| Layer | Evidence type | Status |
|-------|--------------|--------|
| 3 inverted canaries in test_comprehension_corpus.py | Offline test (E2) | **Current, PASSED** |
| Each canary asserts specific fact ID in failures | Offline test | Current |
| Vacuous-green resistance (non-empty corpus guard) | Offline test | Current |
| 8 additional unit-level canaries in test_facts.py | Offline test | Current |

### Adversarial challenge

1. **This gate HAS current evidence.** E2 in the shared ledger shows all 3 canaries passed in this audit run. The tests are not mocked: they read committed snapshots, apply a deterministic mutation, and assert the gate fires. This is the strongest form of offline evidence.

2. **Could the canaries pass vacuously?** No. Each canary asserts BOTH `report.failed == True` AND the specific fact ID in `report.failures()`. A test that merely checks "something failed" could pass vacuously, but asserting the specific fact ID means the right detection mechanism fired.

3. **Coverage gap (documented):** Only 3 of 8 fact types have corpus-level canaries (table, code, math). `absent`, `order`, `xref`, `image_ref`, `present` lack corpus canaries. Unit-level tests exist for these. This means the gate proves teeth for 3 exploit classes but not all 8.

4. **Anchor drift:** C08 notes each canary has `assert needle in md` before scrambling. If the snapshot drifts, the test skips (not passes). Currently 0 skips in E2. This guard is active and working.

### Verdict: **PASS**

**Rationale:** This is the one gate with complete current evidence. The 3 inverted canaries ran in this audit (E2: 9 passed), each asserts the specific fact ID, and vacuous-green resistance is proven. The coverage gap (3/8 fact types) is documented and mitigated by unit-level canaries. No runtime LLM is needed: the fact engine is deterministic.

---

## G7: Licensing

**Primary report:** C09
**Claim:** BSL-1.0 project license, all dependencies permissive, no GPL contamination.

### Evidence type

| Layer | Evidence type | Status |
|-------|--------------|--------|
| `pyproject.toml` license field | Code inspection | Current |
| BSL-1.0 headers on source files (grep) | Code inspection | Current |
| Dependency licenses (PyPI metadata) | Code inspection | Current |
| `rapidfuzz` (MIT) replaces `levenshtein` (GPL) | Code inspection + parity test | Current |
| Wheel contains only source, no test/corpus leak | Build inspection (E7) | Current |
| Automated license scan (`pip-licenses`, `liccheck`) | Not performed | **GAP** |

### Adversarial challenge

1. **The primary evidence is complete for direct dependencies.** C09 lists every core and optional dependency with its license. All are permissive (MIT, BSD, Apache-2.0, BSL-1.0, LGPL-3.0+).

2. **LGPL-3.0+ (pylatexenc) is NOT "permissive" in the same sense as MIT/BSD.** LGPL requires that downstream users can replace the LGPL library with a modified version. For a pure-Python package distributed as a wheel, this is trivially satisfied (users can `pip install` a different version). But C09 lumps it with "permissive" without noting the distinction. This is not a violation but is imprecise.

3. **Transitive dependencies are NOT exhaustively checked.** C09 acknowledges this (Limitations section): "Transitive dependency licenses are assessed by known-package reputation." A GPL transitive dependency in, say, `grits-metric`'s dependency tree would be a real problem. `grits-metric` depends on `pylcs` (MIT), `numpy` (BSD), `scipy` (BSD). These are safe. But this was not mechanically verified.

4. **No automated scan was performed.** `pip-licenses` or `liccheck` would provide mechanical proof. The gap is documented but open.

### Verdict: **PASS**

**Rationale:** All direct and known transitive dependencies are permissive. The `levenshtein` -> `rapidfuzz` replacement specifically addresses the most likely GPL contamination vector. The LGPL-3.0+ pylatexenc is compatible with BSL-1.0 distribution (pure Python, users can replace). The lack of automated scanning is a process gap, not a licensing violation. The gate passes on current evidence.

---

## Summary Table

| Gate | Primary Report | Evidence Class | Verdict | Key Gap |
|------|---------------|----------------|---------|---------|
| G1 Advisory non-leakage | C03 | Code + offline test | **PASS-PROVISIONAL** | No live adversarial sidecar test |
| G2 Fail-not-partial | C04 | Code + offline test | **PASS-PROVISIONAL** | No live fault injection (endpoint timeout, disk full) |
| G3 Determinism by replay | C05, C02 | Code + offline test | **PASS-PROVISIONAL** | No separate-process replay, ref oracle axes unpinned |
| G4 Per-axis reporting | C06, C15 | Code + offline test | **PASS** | None (runtime not required) |
| G5 Untrusted-input mediation | C07 | Code inspection only | **PASS-PROVISIONAL** | No live injection probe, backend conformance untested |
| G6 Baseline canary (inverted) | C08 | Offline test (E2) | **PASS** | Coverage 3/8 fact types (documented, mitigated) |
| G7 Licensing | C09 | Code + build inspection | **PASS** | No automated transitive scan (process gap) |

---

## Adversarial Observations

### 1. The "PASS by absence of contradiction" pattern

C03, C04, C07 all follow the same structure: "We inspected the code. No violation exists. Therefore PASS." This is valid for structural proofs (import absence, frozen fields) but insufficient for behavioral proofs (the system actually handles adversarial input correctly at runtime). Four gates (G1, G2, G3, G5) are PASS-PROVISIONAL because their proofs are structural, not behavioral.

### 2. The mocked-test ceiling

The offline test suite exercises error handlers with synthetic dicts, not real disk artifacts. `test_fusion.py` passes hand-constructed malformed sidecars to `fuse_verdicts()`. This proves the function handles bad input. It does NOT prove that the real disk-read-parse-validate chain produces the same result. A malformed JSON file on disk goes through `json.loads()` first, which is not exercised in the mock tests.

### 3. The 19-paper pinning is the strongest single evidence

Score pinning commits 19 papers' exact gate+QA results to a JSON baseline. Any non-determinism, any scoring regression, any threshold drift would break these tests. This is operationally strong evidence for G3, even without separate-process replay. The pinning has survived 1406-test runs without failure.

### 4. The BLOCKED runtime matrix is a systemic gap, not a per-gate gap

All 10 runtime scenarios are blocked (E9). This is not a surgical gap in one gate; it is a systemic absence of operational proof. Gates G1, G2, G3, G5 all share the same root cause: `ALLIANCE_POD_KEY` not set. Until this is resolved, no gate can advance from PROVISIONAL to full PASS on runtime evidence.

### 5. No false passes found among the offline evidence

I challenged every offline test for vacuous-green patterns. The tests use non-trivial inputs, assert specific outputs, and have anti-vacuous guards. None of the 7 gates passed because a test was never run. The provisional verdicts are due to ABSENT runtime evidence, not VACUOUS test evidence.

---

## Disposition for C30

- **3 gates PASS:** G4, G6, G7. These do not require runtime proof and have sufficient current evidence.
- **4 gates PASS-PROVISIONAL:** G1, G2, G3, G5. These have strong code+test evidence but require runtime proof for full confidence. The gap is narrow (the structural architecture prevents the failure mode), but unexercised operationally.
- **0 gates FAIL-UNPROVEN.**

The system is architecturally sound. The provisional verdicts reflect an evidence gap (blocked credentials), not a suspected defect.
