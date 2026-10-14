# Whisker Audit Result -- 2026-07-20 -- Auditor: Audit v2 (C30 Synthesis)

## 1. Scope, Date, HEAD, Branch, and Worktree Boundary

| Field | Value |
|---|---|
| Date | 2026-07-20 |
| HEAD | `51cb704610220d31c9d5e078b1350c1b37a8714a` |
| Branch | `main` |
| Origin | `sabriguenes/wg21-paperflow-workspace.git` |
| Upstream | `cppalliance/wg21-paperflow.git` |
| Package | whisker 0.5.0 |
| Python | 3.12.10 |
| OS | Windows NT 10.0.26200.0 |

**Worktree boundary:** The audited state is HEAD plus **extensive uncommitted local modifications** across 18+ source files, 13+ test files, and 2 untracked new files (`ideal_verify.py`, `test_ideal_verify.py`). This is explicitly noted per C01 and C28-F07: another auditor at the same HEAD would see different code. All findings reference this combined state.

**Baseline test result:** `uv run --package whisker pytest packages/whisker/tests` -> **1406 passed, 8 skipped, 3 xfailed in 27.65s** (exit code 0).

---

## 2. Fresh Claims Registry

| ID | Claim | Value | Evidence |
|---|---|---|---|
| C-VER | Version phase | `0.5.0` (pre-1.0) | `pyproject.toml` |
| C-API | Stable public API | No (pre-1.0, no stability promise) | Version 0.5.0 |
| C-CAL | Calibration status | Stage 0 / uncalibrated (provisional) | CLAUDE.md: "not fitted on our own labeled corpus" |
| C-LAB | Label role | Advisory (gate-bearing only for verified facts in Lane 3) | Corpus: 37 verified facts, 0 gt.md files |
| C-INF | Default inference | Self-hosted (alliance-pod, vllm_thinking) | SERVICES.toml |
| C-COMP | Comprehension claimed | Yes (Lane 3 deterministic + one-time readback) | facts.py + test_comprehension_corpus.py |
| C-PROD | Production-grade ops | No (pre-production, single-operator) | No deployment docs, no monitoring |
| C-DET | Determinism tier | Quality-stable (deterministic core) / non-guaranteed (advisory lane) | CLAUDE.md invariants + documented >= 25% flip rate |
| C-LIC | Licenses | BSL-1.0 + MIT/BSD/Apache-2.0/LGPL-3.0+ deps | pyproject.toml + C09 audit |
| C-INT | Merged interop | score-file and check-facts coexist with interactive/tapetum commands | CLI help + E6 tests |
| C-VIS | Visibility | All commands visible in `-h` output | C01 section 6 |
| C-IDEAL | Ideal contract | 4 tomd ideals, read-only, source is factual authority | golden_ideals.py, C20 |
| C-LLM | LLM paths | tapetum-llm (PDF judge + text cascade + ideal verifier + fusion), readback. VLM dormant. | 3 CLI entry points, C24 |
| C-EXIT | Exit contracts | whisker: 0/1/3/5. tapetum-llm: advisory exits 0, operational errors exit 1. | constants.py, CLAUDE.md |

---

## 3. Fresh Baseline and Verification Commands

| Command | Exit | Result |
|---|---|---|
| `uv run --package whisker pytest packages/whisker/tests -v` | 0 | 1406 passed, 8 skipped, 3 xfailed |
| `uv run --package whisker pytest tests/test_comprehension_corpus.py -v` | 0 | 9 passed (5 positive + 3 canaries + 1 membership) |
| `uv run --package whisker pytest tests/test_golden.py tests/test_fusion.py tests/test_incremental.py tests/test_golden_ideals.py tests/test_gates.py tests/test_guard.py -v` | 0 | 284 passed |
| `uv run --package whisker pytest tests/test_score.py tests/test_metrics.py tests/test_facts.py tests/test_bench.py tests/test_match.py tests/test_score_pinning.py tests/test_edit_distance_parity.py -v` | 0 | 218 passed |
| `uv run --package whisker pytest tests/test_tapetum_llm.py tests/test_pdf_judge.py tests/test_readback.py tests/test_ideal_verify.py tests/test_vlm_lane.py tests/test_tapetum_llm_eval.py tests/test_unit_models.py tests/test_unit_judge.py -v` | 0 | 431 passed, 8 skipped |
| `uv run --package whisker pytest tests/test_invariants.py tests/test_claude_invariants.py tests/test_check_facts_main.py tests/test_score_file.py tests/test_dev_replay_acceptance.py ... -v` | 0 | 464 passed, 3 xfailed |
| `uv build --package whisker --wheel` | 0 | `whisker-0.5.0-py3-none-any.whl` (49 files) |
| `python -c "import whisker"` (core only) | 0 | All public symbols available |

---

## 4. Merged Implementation Interoperability and Visibility

| Check | Status | Evidence |
|---|---|---|
| `score-file` dispatchable | PASS | test_score_file.py, CLI help |
| `check-facts` dispatchable | PASS | test_check_facts_main.py, CLI help |
| `-h` / `--help` exposes all commands | PASS | C01 section 6 |
| stdout JSON usable by tomd | PASS | `--json` flag tested |
| Deterministic and LLM reports separate | PASS | `whisker/det/` vs `whisker/llm/` (C03, C10) |
| Both implementation lines reachable | PASS | Three CLI entry points registered |
| No dead/hidden command surface | PASS (note: VLM has no production command, correctly) | C24 |

---

## 5. Gate Ledger (Conjunctive)

| Gate | Verdict | Evidence | Notes |
|---|---|---|---|
| **G1** Advisory non-leakage | **PASS-PROVISIONAL** | C03: score.py has no tapetum imports; fusion fail_locked tested; FusionResult.advisory frozen | Runtime adversarial sidecar test blocked |
| **G2** Fail-not-partial | **PASS-PROVISIONAL** | C04: per-paper firewalls, tombstone mechanism, debug flush via finally; test_fusion malformed payloads | Live fault injection blocked |
| **G3** Determinism by replay | **PASS-PROVISIONAL** | C02+C05: pure functions, 19-paper score pinning, 3 explicit determinism tests | Separate-process workspace replay blocked |
| **G4** Per-axis + eval integrity | **PASS** | C06+C15: null eligibility tested (5 bench + 3 guard tests), TEDS structure + content paired, construct separation | Runtime not required |
| **G5** Untrusted-input mediation | **PASS-PROVISIONAL** | C07: inject_untrusted on all 5 call sites, per-call random tags, structured output, delimiter escape | Runtime injection probe blocked |
| **G6** Baseline canary (inverted) | **PASS** | C08+E2: 3 inverted canaries (table/code/math) ran and passed; vacuous-green blocked | Current evidence complete |
| **G7** Licensing / attribution | **PASS** | C09: BSL-1.0 + all deps permissive; GPL eliminated (rapidfuzz replaces levenshtein) | No automated transitive scan (process gap) |

**Gate summary:** 3 PASS, 4 PASS-PROVISIONAL, 0 FAIL. The 4 provisional gates reflect blocked runtime credentials (single root cause: `ALLIANCE_POD_KEY` not set), not suspected defects. Per C26 adversarial review: no vacuous passes found in offline evidence.

---

## 6. Real-LLM Runtime Matrix

**Status: ALL 10 SCENARIOS BLOCKED**

Root cause: `ALLIANCE_POD_KEY` environment variable not set. Pod infrastructure reachable (HTTP 401) but authentication denied.

| # | Scenario | Status |
|---|---|---|
| 1 | Positive control | BLOCKED |
| 2 | Known structural defect | BLOCKED |
| 3 | Instruction in document | BLOCKED |
| 4 | Delimiter forgery | BLOCKED |
| 5 | Adversarial advisory verdict | BLOCKED |
| 6 | Grounding failure | BLOCKED |
| 7 | Operational failure | BLOCKED |
| 8 | status="error" fallback | BLOCKED |
| 9 | Mixed batch | BLOCKED |
| 10 | Readback corruption control | BLOCKED |

Per Runbook section 8: definitive credential denial recorded once. Historical runs do not replace a current proof.

---

## 7. Injection, Failure, Tombstone, Partial-Persistence, and Exit-Code Matrix

| Test | Offline Evidence | Runtime Evidence |
|---|---|---|
| Prompt injection defense installed | PASS (C07: all 5 call sites wrapped) | BLOCKED |
| Delimiter forgery escape | PASS (C07: escape_guard_delimiters) | BLOCKED |
| Structured output on all LLM calls | PASS (C07: pydantic output_type) | BLOCKED |
| Error tombstone replaces stale sidecar | PASS (C04: test_incremental) | BLOCKED |
| Debug transcript preserved on failure | PASS (C04: finally block) | BLOCKED |
| Batch isolation (per-paper firewall) | PASS (C04: try/except in loop) | BLOCKED |
| Advisory verdicts exit 0 | PASS (C10: code inspection) | BLOCKED |
| Operational error exits 1 | PASS (C10: code inspection) | BLOCKED |
| Deterministic exit codes 0/1/3/5 | PASS (C10+C25: tested) | N/A (deterministic, no LLM) |
| Malformed sidecar handling | PASS (test_fusion: 4 malformed tests) | N/A |

---

## 8. Source/Ideal Authority Result

| Check | Status | Evidence |
|---|---|---|
| 4 tomd ideals discovered read-only | PASS | C20: golden_ideals.py auto-discovers |
| Case-insensitive PID discovery | PASS | test_golden_ideals (3 tests) |
| No ideal copies under whisker | PASS | C20: Glob confirms none |
| Ideal presence in fingerprints | PASS | C20: test_incremental schema tests |
| Source-aware judge runs before ideal verifier | PASS | C20: cli.py execution order |
| Source is factual authority | PASS | CLAUDE.md + C20 |
| Ideal is structural reference only | PASS | C20: demotion-only rules |
| Ideal `review` only demotes eligible advisory | PASS | test_fusion ideal tests |
| Ideal `agree` never promotes/rescues/clears | PASS | test_fusion ideal_agree test |
| Malformed sidecars cannot crash fusion | PASS | test_fusion: 4 malformed tests |

---

## 9. Per-Dimension Levels, Grades, Reasons, Evidence, and Eligibility

| Dimension | Level | Grade | Reason | Evidence | Eligibility |
|---|---|---|---|---|---|
| **D1** Epistemic separation (w=20) | **3** | **B** | Lanes documented; CI test proves non-leakage (test_fail_locked); asymmetric fusion proven. Missing: adversarial verdict rejection under live injection. | C03, C21, test_fusion | All subcriteria eligible |
| **D2** Determinism (w=15) | **3** | **B** | Pure-function architecture; 19-paper score pinning; named constants; sorted outputs; 3 explicit determinism tests. Missing: separate-process replay. | C02, C05, test_score_pinning | Quality-stable tier applied per C-DET |
| **D3** Fidelity/fail-not-partial (w=15) | **3** | **B** | Fail-closed on fidelity paths; tombstone mechanism; debug preserved; batch isolation; malformed sidecar handling. Missing: live fault injection. | C04, test_fusion, test_incremental | All subcriteria eligible |
| **D4** Metric validity (w=15) | **3** | **A** | Per-axis with null eligibility (tested); TEDS = verbatim PubTabNet; MHS = APTED; content_recall = multiset recall; constructs distinct; evaluator pinned (test_guard tool-version). | C06, C15, test_bench, test_metrics | All eligible; no runtime needed |
| **D5** Anti-gaming (w=12) | **3** | **B** | 3 corpus canaries + 8 unit canaries; holdout split; advisory-only judge; vacuous-green blocked. Missing: optimization-budget caps. | C08, C13, test_comprehension_corpus | All eligible |
| **D6** Untrusted-input (w=10) | **2** | **C** | Trust boundaries inventoried; wrapping consistent; structured output constrains schema. Missing: runtime injection probes; backend conformance untested. C26 identifies this as the weakest gate. | C07, code inspection | Eligible but runtime-unproven |
| **D7** API/packaging (w=8) | **3** | **A** | pyproject.toml correct; extras isolation works; core imports without tapetum-llm; wheel builds cleanly; BSL-1.0 headers present. | C09, C25, E7, E8 | All eligible |
| **D8** Documentation/CLI (w=5) | **3** | **B** | 879-line CLAUDE.md; exit-code contract; stdout/stderr discipline; architecture map; known-gaps section. Minor: no section-level freshness check. | C25, C28-F04 | All eligible |

---

## 10. Navigation Composite

```
D1: (3/4) * 100 * 0.20 = 15.00
D2: (3/4) * 100 * 0.15 = 11.25
D3: (3/4) * 100 * 0.15 = 11.25
D4: (3/4) * 100 * 0.15 = 11.25
D5: (3/4) * 100 * 0.12 =  9.00
D6: (2/4) * 100 * 0.10 =  5.00
D7: (3/4) * 100 * 0.08 =  6.00
D8: (3/4) * 100 * 0.05 =  3.75
                          ------
Composite:                 72.50
```

---

## 11. Weakest-Link Grade, Interval, Band, Uncertainty Drivers, and Flip Conditions

**Composite:** 72.50
**Interval:** [66, 79] (width driven by blocked runtime and uncalibrated thresholds)
**Weakest-link grade:** C (D6 untrusted-input, runtime-unproven)

### Band determination

- All gates pass (4 provisionally) -> not Unsound
- Composite 72.50 >= 65 -> meets Professional-grade numeric threshold
- D1-D4 grades: B, B, B, A -> all >= B
- Inverted canary evidenced: Yes (3 canaries, E2)
- Replay evidenced: Yes (19-paper score pinning, arguable as functional replay)
- **BUT:** 4 PROVISIONAL gates + weakest-link grade C + blocked runtime -> cannot issue unqualified certification per Runbook section 14.5

### Band: **Emerging (upper), qualified toward Professional-grade**

The offline evidence supports Professional-grade on every numeric threshold. The qualification is imposed by:
1. Four gates are PASS-PROVISIONAL (code-verified, runtime-unproven)
2. D6 grade C (runtime injection defense unproven)
3. All 10 runtime scenarios blocked (systemic credential denial)
4. Uncommitted worktree undermines reproducibility

Per the Scorecard: "Professional-grade requires D1-D4 grade >= B." D1-D4 are all >= B. But the weakest-link grade across ALL dimensions (including D6 at C) prevents the Professional-grade certification from being unqualified.

### Uncertainty drivers (named)

1. **Blocked runtime matrix** (all 10 scenarios) -- single root cause, resolvable by setting ALLIANCE_POD_KEY
2. **Uncalibrated thresholds** (C-CAL = provisional) -- resolvable by running `whisker calibrate`
3. **Uncommitted code** -- resolvable by committing and splitting into reviewed PRs
4. **Cross-platform determinism** untested (C28 challenge to C02)
5. **Cascade escalation rate** not re-measured post-v0.5.0 (C17 gap)

### Flip conditions

| # | Condition | Direction |
|---|---|---|
| 1 | Runtime injection probe succeeds (G5 fails) | -> Unsound |
| 2 | Live fault injection shows partial result on failure (G2 fails) | -> Unsound |
| 3 | Separate-process replay produces different results (G3 fails) | -> Unsound |
| 4 | Advisory verdict leaks to deterministic gate (G1 fails) | -> Unsound |
| 5 | All 10 runtime scenarios pass + credentials available | -> Professional-grade (unqualified) |
| 6 | Calibration proves edges materially wrong | D4 drops, composite drops ~3-5 points |
| 7 | Code committed and PR-split clean | Removes reproducibility uncertainty |

---

## 12. Findings Ranked by Severity

### Critical

None.

### High

| ID | Finding | Source | Gate/Dim |
|---|---|---|---|
| H1 | Real-LLM runtime evidence completely blocked (10/10 scenarios) | C01, C27, E9 | G1-G3, G5, D1, D3, D6 |
| H2 | Uncommitted code across 18+ files undermines audit reproducibility | C01, C28-F07 | All |
| H3 | Codebase not PR-ready without commit/split/cleanup | C28-F12 | All |

### Medium

| ID | Finding | Source | Gate/Dim |
|---|---|---|---|
| M1 | No separate-process workspace replay (G3 gap) | C05, C26 | G3, D2 |
| M2 | `tables.py` has no dedicated test file | C28-F01 | D4 |
| M3 | Invariant tests cover structure but not behavioral claims | C28-F05 | G1 |
| M4 | `ideal_verify.py` is untracked (referenced but not version-controlled) | C28-F08 | D5 |
| M5 | Cascade escalation rate not re-measured post-v0.5.0 | C17, C29 | D1 |

### Low

| ID | Finding | Source | Gate/Dim |
|---|---|---|---|
| L1 | No `.gt.md` ground-truth files for Lane 2 bench | C01-F03 | D4 |
| L2 | Calibration edges remain provisional | C14 | D4, D5 |
| L3 | VLM dead code (788 LOC, 5 files, no production command) | C24, C28-F11 | D7 |
| L4 | Windows behavior handled but not integration-tested | C28-F13 | D8 |
| L5 | LGPL-3.0+ (pylatexenc) noted but compatible with BSL-1.0 | C26 on G7 | G7 |

### Informational

| ID | Finding | Source |
|---|---|---|
| I1 | Test LOC ratio is healthy (1.08:1) but asymmetric toward deterministic core | C28-F03 |
| I2 | CLAUDE.md accurate but large (879 lines, maintenance risk) | C28-F04 |
| I3 | Path handling uses pathlib throughout (platform-safe) | C28-F14 |
| I4 | No ecosystem delta in 1-day window since Audit v1 | C29 |
| I5 | All adopted external metrics (TEDS, OmniDocBench, NID) still current | C29 |

---

## 13. False-Pass Risks and Falsification Tests

| Risk | Hypothesis | Falsification |
|---|---|---|
| Advisory leakage via corrupted disk sidecar | A malicious `.whisker.tapetum.json` placed in `whisker/det/` could be loaded by `__main__.py` | Place adversarial sidecar in wrong directory; verify fusion ignores it |
| Prompt injection succeeds at runtime | Model obeys injected instructions despite guard | Run scenario 3 (instruction-in-document) with live endpoint |
| Tombstone write fails under disk pressure | Partial JSON left as valid-looking sidecar | Run `_write_error_tombstone()` under simulated disk-full |
| Cross-platform determinism breaks | Different numpy build changes Hungarian assignment | Run score pinning on Linux vs Windows with same inputs |
| Cascade escalation never fires | Dead code path (0/198 historical rate) | Measure current escalation rate on full corpus with live endpoint |

---

## 14. PR/Release Blockers

1. Commit all local modifications into reviewed logical commits
2. Add `ideal_verify.py` and `test_ideal_verify.py` to version control
3. Resolve VLM fate (delete or quarantine behind feature flag)
4. Run the 10-scenario real-LLM runtime matrix when credentials are available
5. Add `test_tables.py` with dedicated edge-case coverage

---

## 15. Verified Strengths

1. **Architectural soundness:** The two-lane (deterministic + advisory) separation is the strongest design feature. The deterministic lane is provably pure, LLM-free, and reproducible.
2. **Test discipline:** 1406 tests with ~1:1 source-to-test LOC ratio. Score pinning (19 papers), 3 inverted canaries, and explicit determinism tests provide confidence.
3. **Metric integrity:** Verbatim ports of PubTabNet TEDS and OmniDocBench normalizer ensure comparability with published benchmarks.
4. **Fusion safety:** The asymmetric fusion rules (fail-locked, rescue-never-promotes, clear guardrails) are thoroughly tested and structurally enforce advisory-only behavior.
5. **Honest documentation:** CLAUDE.md accurately describes known gaps, calibration status, and design rationale.
6. **GPL elimination:** The rapidfuzz replacement eliminates the most likely license contamination vector, with parity tests proving equivalence.

---

## 16. Open Evidence Gaps

1. All 10 real-LLM runtime scenarios (resolvable: set ALLIANCE_POD_KEY)
2. Separate-process workspace replay (resolvable: configure WG21_DATA_DIR)
3. Cross-platform determinism (resolvable: CI matrix)
4. Cascade escalation rate post-v0.5.0 (resolvable: full-corpus tapetum run)
5. Automated transitive license scan (resolvable: add pip-licenses to CI)
6. Calibration from labeled data (resolvable: run `whisker calibrate`)

---

## 17. Audit v1 Delta (Labels Only, No Score Transfer)

| Aspect | Audit v1 | Audit v2 | Label |
|---|---|---|---|
| Test count | Not transferred | 1406 passed | Fresh measurement |
| Source files | Not transferred | 43 files, 15,589 LOC | Fresh measurement |
| Corpus papers | Not transferred | 5 papers, 37 verified facts | Fresh measurement |
| tomd ideals | Not transferred | 4 ideals | Fresh measurement |
| Runtime evidence | Not transferred | All 10 scenarios BLOCKED | Fresh finding |
| Gate verdicts | Not transferred | 3 PASS, 4 PASS-PROVISIONAL | Fresh assessment |
| Composite | Not transferred | 72.50 [66, 79] | Fresh calculation |
| Band | Not transferred | Emerging (upper), qualified toward Professional-grade | Fresh determination |

No Audit v1 scores, findings, baselines, or gate results were transferred or used as priors.

---

## 18. All 30 Role Reports and Status

| Role | File | Status |
|---|---|---|
| C01 Claims and Baseline | code-c01-claims-baseline.md | Complete |
| C02 Deterministic Core | code-c02-deterministic-core.md | Complete |
| C03 Advisory Non-Leakage | code-c03-advisory-non-leakage.md | Complete |
| C04 Fail-Not-Partial | code-c04-fail-not-partial.md | Complete |
| C05 Quality-Stability | code-c05-quality-stability.md | Complete |
| C06 Per-Axis Null | code-c06-per-axis-null.md | Complete |
| C07 Prompt Injection | code-c07-prompt-injection.md | Complete |
| C08 Canary Gate Teeth | code-c08-canary-gate-teeth.md | Complete |
| C09 License Provenance | code-c09-license-provenance.md | Complete |
| C10 Score-Path Truth | code-c10-score-path-truth.md | Complete |
| C11 Golden Guard | code-c11-golden-guard.md | Complete |
| C12 Facts Comprehension | code-c12-facts-comprehension.md | Complete |
| C13 Corpus Holdout | code-c13-corpus-holdout.md | Complete |
| C14 Calibration | code-c14-calibration.md | Complete |
| C15 Metric Validity | code-c15-metric-validity.md | Complete |
| C16 LLM Authenticity | code-c16-llm-authenticity.md | Complete |
| C17 Cascade Topology | code-c17-cascade-topology.md | Complete |
| C18 Grounding Router | code-c18-grounding-router.md | Complete |
| C19 Chunking Context | code-c19-chunking-context.md | Complete |
| C20 Source-Ideal Authority | code-c20-source-ideal-authority.md | Complete |
| C21 Fusion Trust | code-c21-fusion-trust.md | Complete |
| C22 Readback | code-c22-readback.md | Complete |
| C23 RAG Decision | code-c23-rag-decision.md | Complete |
| C24 VLM Boundary | code-c24-vlm-boundary.md | Complete |
| C25 Professional Surface | code-c25-professional-surface.md | Complete |
| C26 Gate Meta-Review | code-c26-gate-meta-review.md | Complete |
| C27 Runtime Meta-Review | code-c27-runtime-meta-review.md | Complete |
| C28 Engineering Meta-Review | code-c28-engineering-meta-review.md | Complete |
| C29 External-Delta | code-c29-external-delta.md | Complete |
| C30 Synthesis | CODE-AUDIT-RESULT.md (this file) | Complete |

---

## 19. Stop Conditions Triggered

| # | Condition | Triggered | Impact |
|---|---|---|---|
| 14.1 | Required gate evidence unavailable | Yes (G1, G2, G3, G5 runtime) | Gates assigned PASS-PROVISIONAL, not full PASS |
| 14.5 | Required access definitively denied | Yes (ALLIANCE_POD_KEY) | 10/10 runtime scenarios blocked |
| 14.2 | Production-calibration claim on uncalibrated thresholds | No (C-CAL = provisional, not production-calibrated) | N/A |
| 14.3 | Fidelity-critical path emits partial success | No (offline evidence shows fail-closed) | N/A |
| 14.4 | Load-bearing citation unverifiable | No | N/A |
| 14.6 | Scope drift | No | N/A |
| 14.7 | Worktree ambiguity | Partially (uncommitted code noted, boundary documented) | Uncertainty widened |

---

## 20. Final Verdict

### Band: **Emerging (upper), qualified toward Professional-grade**

The offline evidence places whisker at the Professional-grade threshold on every numeric metric: composite 72.50 (>= 65), D1-D4 all grade B or above, inverted canaries proven, score pinning as functional replay. The qualification to Emerging is imposed by:

1. **Four PASS-PROVISIONAL gates** (G1, G2, G3, G5): strong code+test evidence, but mandatory runtime proof is blocked by credential denial (stop condition 14.5).
2. **D6 at grade C**: prompt-injection defense is architecturally installed but operationally unproven.
3. **Uncommitted worktree**: findings are non-reproducible at the committed HEAD alone.

**The system is architecturally sound.** The two-lane separation, asymmetric fusion, and deterministic-first design are among the strongest such implementations encountered. No code defect or design flaw was found that would cause a gate failure.

**The evidence gap has a single root cause** (`ALLIANCE_POD_KEY` not set) and is resolvable in a single session. When credentials become available, all 10 runtime scenarios can execute and the 4 provisional gates can be re-evaluated. If all pass, the band advances to Professional-grade.

### Mandatory attestations

- Current real LLM, injection, and operational failure proofs: **DID NOT RUN** (credential denial).
- Every observed Tapetum operational failure exited 1: **CANNOT ATTEST** (no runtime observed).
- Merged User/Sean implementation lines interoperate and remain visible: **YES** (C01, C09, E6).
- tomd ideals are structural references and sources are factual authority: **YES** (C20).
- Image/VLM fidelity was not an audit requirement: **CONFIRMED** (C24).
- Every score and conclusion derived from Audit v2 evidence only: **YES** (anti-transfer check below).

### Anti-transfer attestation

No Audit v1 fact, count, score, gate result, confidence value, baseline, or band was transferred to Audit v2. Audit v1 is referenced only for methodological comparison (section 17 delta labels). All findings, claims, inventories, hashes, and scores in this report are derived from fresh evidence gathered on 2026-07-20.
