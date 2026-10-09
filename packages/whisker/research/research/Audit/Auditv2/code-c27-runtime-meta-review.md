# C27 Runtime Meta-Review (Adversarial)

**Role:** Independently verify what runtime evidence exists vs what is blocked. Assess material impact on gates and dimensions.
**Auditor posture:** Hostile. Claims dependent on runtime that cannot be verified are treated as unproven assertions, not findings.
**Date:** 2026-07-20
**Input:** shared-evidence-ledger.md (E9), C01-C25 primary reports

---

## 1. Runtime Matrix Status

The shared evidence ledger (E9) declares all 10 runtime scenarios BLOCKED:

| # | Scenario | Status | Reason |
|---|----------|--------|--------|
| 1 | Positive control (known-good paper) | BLOCKED | ALLIANCE_POD_KEY not set |
| 2 | Known structural defect (known-fail paper) | BLOCKED | Same |
| 3 | Instruction in document (prompt injection) | BLOCKED | Same |
| 4 | Delimiter forgery (escape bypass attempt) | BLOCKED | Same |
| 5 | Adversarial advisory verdict (LLM tries to flip gate) | BLOCKED | Same |
| 6 | Grounding failure (hallucinated evidence) | BLOCKED | Same |
| 7 | Operational failure (endpoint timeout/crash) | BLOCKED | Same |
| 8 | status="error" fallback (tombstone path) | BLOCKED | Same |
| 9 | Mixed batch (some papers fail, batch continues) | BLOCKED | Same |
| 10 | Readback corruption control | BLOCKED | Same |

**Root cause:** Single credential (`ALLIANCE_POD_KEY`). The pod infrastructure is reachable (HTTP 401 confirms the endpoint exists) but authentication is denied.

**Answer to the primary question: How many of the 10 runtime scenarios actually ran?**

**ZERO.** Not a single runtime scenario has current evidence in this audit.

---

## 2. What the Test Suite Covers (Per Scenario)

For each blocked scenario, I assess what the offline test suite proves and what only runtime can prove.

### Scenario 1: Positive Control (known-good paper adjudicated, verdict matches expectation)

**Test suite covers:**
- `test_tapetum_llm.py`: Tests the cascade topology (triage -> escalation -> deep dive) with mocked LLM responses. Proves routing logic.
- `test_pdf_judge.py`: Tests PDF judge orchestration with mocked vision/text inputs. Proves judgment schema.
- `test_fusion.py`: Tests verdict fusion with synthetic sidecars. Proves merge logic.
- 19-paper score pinning: Proves deterministic scoring of committed goldens.

**Only runtime can prove:**
- That a real model (deepseek-v4-pro on vllm_thinking) produces a sensible verdict on a real paper.
- That the prompt+schema combination actually elicits useful analysis (not degenerate "pass everything" or "fail everything").
- That token limits, context windows, and thinking budgets produce complete (not truncated) responses.
- That the end-to-end pipeline (disk read -> prompt construction -> API call -> response parse -> sidecar write -> fusion) works without errors.

**Substitutability:** LOW. Mocked tests prove logic; they say nothing about model quality or end-to-end integration.

### Scenario 2: Known Structural Defect (known-fail paper correctly identified)

**Test suite covers:**
- `test_score_pinning.py`: 19 papers include papers with known gate failures (documented in `_EXPECTED_GATE_FAILURES`).
- `test_gates.py`: Gate teeth tests prove gates trip on specific defects.
- `test_comprehension_corpus.py`: 3 canaries prove fact engine detects corruption.

**Only runtime can prove:**
- That the advisory LLM lane correctly identifies a structural defect that the deterministic lane also catches (convergent validation).
- That the model does not hallucinate defects in good papers or miss defects in bad ones.

**Substitutability:** MEDIUM. The deterministic lane detects structural defects without LLM. The advisory lane is a secondary check. Score pinning proves the deterministic lane works.

### Scenario 3: Instruction in Document (prompt injection)

**Test suite covers:**
- Nothing directly. No test feeds adversarial content to a real LLM.
- C07 proves `inject_untrusted()` wraps content and `escape_guard_delimiters()` neutralizes forgery.
- Structured output (`output_type`) constrains responses to pydantic schema.

**Only runtime can prove:**
- That a real model obeys the guard instruction and does not follow injected commands.
- That the constrained decoding backend (vllm_thinking) actually enforces the pydantic schema.
- That sophisticated prompt injection (e.g., multi-step jailbreak, instruction hierarchy confusion) fails.

**Substitutability:** VERY LOW. This is inherently a runtime property. Code inspection proves the defense is installed, not that it works against a real adversary.

### Scenario 4: Delimiter Forgery (escape bypass attempt)

**Test suite covers:**
- Nothing directly exercises a forged delimiter against a real LLM.
- `escape_guard_delimiters()` is tested implicitly by being called in the wrapping path. But no test verifies that a paper containing `<<<SRC12345678>>>` text is correctly escaped and that the model does not see a closing boundary.

**Only runtime can prove:**
- That `escape_guard_delimiters` output, when sent to a real model, is not interpreted as a boundary.
- That the model's tokenizer does not reconstruct the original delimiter from the escaped form.

**Substitutability:** LOW. The escape is deterministic code (testable offline), but whether the LLM respects it is a runtime property.

### Scenario 5: Adversarial Advisory Verdict (LLM tries to override a deterministic fail)

**Test suite covers:**
- `test_fusion.py::test_fail_locked`: Proves `fuse_verdicts()` keeps fail when tapetum says pass.
- `test_fusion.py::test_rescue_never_upgrades_to_pass`: Proves heading rescue caps at review.
- Full parametric fusion matrix coverage.

**Only runtime can prove:**
- That a real model does not produce an out-of-schema response that somehow bypasses pydantic validation.
- That the sidecar-write -> sidecar-read round-trip preserves the exact structured output (no encoding issues, no float precision loss).

**Substitutability:** HIGH. The fusion logic is deterministic and thoroughly tested. The model output is constrained to schema by pydantic. Even if the model "tries" to override, the code provably prevents it. This scenario has the highest offline-test substitutability.

### Scenario 6: Grounding Failure (hallucinated evidence)

**Test suite covers:**
- `test_tapetum_llm.py`: Tests grounding logic (exact match, fuzzy match, normalized match) with known inputs.
- `grounding.py` tests verify that evidence_spans are validated against the actual document.

**Only runtime can prove:**
- That a real model hallucinating evidence is caught by the grounding validator.
- That the grounding thresholds correctly distinguish between model paraphrasing (acceptable) and fabrication (unacceptable).
- Real-world hallucination patterns (subtle rewording, off-by-one-paragraph quotes) are caught.

**Substitutability:** MEDIUM. Grounding logic is tested offline. But the distribution of real model hallucinations is unknown without runtime data.

### Scenario 7: Operational Failure (endpoint timeout/crash)

**Test suite covers:**
- `test_incremental.py::test_partial_pdf_debug_is_flushed_before_tombstone`: Proves debug is flushed before tombstone on mocked failure.
- Error handling paths tested with `pytest.raises` and exception injection.

**Only runtime can prove:**
- That a real HTTP timeout (endpoint unresponsive) triggers the correct exception path.
- That `asyncio.wait_for()` correctly fires on real network latency.
- That the RunPod proxy's error responses (502, 503, 504) are handled gracefully.
- That partial HTTP responses (connection reset mid-stream) do not corrupt state.

**Substitutability:** LOW. Timeout handling depends on the real network stack, HTTP library behavior, and asyncio event loop interaction. Mocking `asyncio.wait_for` does not prove the real timeout fires correctly.

### Scenario 8: status="error" Fallback (tombstone path)

**Test suite covers:**
- `test_fusion.py`: Tests that `_tapetum_is_usable()` returns False for `status="error"` sidecars.
- Fusion falls back to whisker_only when tapetum is unusable.

**Only runtime can prove:**
- That `_write_error_tombstone()` creates a valid JSON file on disk after a real error.
- That the tombstone file survives disk sync and is readable by a subsequent fusion run.
- That race conditions (concurrent tombstone write + fusion read) do not corrupt.

**Substitutability:** MEDIUM-HIGH. The tombstone logic is simple (`json.dumps` -> `write_text`). The main untested vector is filesystem behavior under concurrent access. For serial execution (current default), substitutability is high.

### Scenario 9: Mixed Batch (some papers fail, batch continues)

**Test suite covers:**
- C04 documents the per-paper try/except firewall in both lanes.
- No test runs a multi-paper batch where one paper actually triggers a live error and others succeed.

**Only runtime can prove:**
- That a real error in paper A does not corrupt shared state used by paper B.
- That asyncio task isolation actually works with real concurrent LLM calls.
- That the error counter and skipped-paper reporting work correctly in a live multi-paper run.

**Substitutability:** MEDIUM. The firewall is trivial code (try/except in a loop). For serial execution, isolation is near-certain. For concurrent execution (`--concurrency N > 1`), asyncio task isolation would need runtime proof.

### Scenario 10: Readback Corruption Control

**Test suite covers:**
- `test_readback.py`: Tests question generation, scoring, and corruption detection with mocked responses.
- Tests the readback scoring logic offline.

**Only runtime can prove:**
- That a real model, given a known-good paper, produces readback answers that score above threshold.
- That a real model, given a corrupted paper, produces readback answers that score below threshold (detecting corruption).
- That readback's raw-httpx approach (D1 exemption) actually works with the live endpoint.

**Substitutability:** LOW. Readback's value proposition is "LLM comprehension of the paper." This is inherently a runtime property. Offline tests prove the scoring logic, not the model's comprehension.

---

## 3. Impact Assessment on Gates and Dimensions

### Which gates require runtime proof?

| Gate | Requires runtime? | Severity of gap |
|------|-------------------|-----------------|
| G1 Advisory non-leakage | Partially (scenario 5) | Low: fusion logic is deterministic; test_fail_locked is equivalent |
| G2 Fail-not-partial | Partially (scenarios 7, 8) | Medium: timeout/disk-failure paths untested |
| G3 Determinism by replay | Yes (separate-process replay) | Medium: no same-workspace replay, but 19-paper pinning is strong |
| G4 Per-axis reporting | No | N/A: pure scoring logic |
| G5 Untrusted-input mediation | Yes (scenarios 3, 4) | High: injection defense is inherently a runtime property |
| G6 Baseline canary | No | N/A: fact engine is deterministic |
| G7 Licensing | No | N/A: static analysis |

### Which dimensions require runtime proof?

| Dimension | Claims requiring runtime | Impact |
|-----------|------------------------|--------|
| D1: All LLM via pipeline | Readback D1 exemption works | Low (documented exemption) |
| D3: Batch isolation | Concurrent batch isolation | Medium (serial path is safe) |
| D6: Structured output enforcement | Backend actually constrains | High (assumed, not proven) |
| Advisory lane quality | Useful verdicts on real papers | High (entire advisory value is unproven) |
| Readback comprehension | Model actually comprehends papers | High (core readback claim) |

---

## 4. Can Test-Suite Evidence Substitute for Runtime Proof?

### Where substitution is VALID:

1. **Deterministic scoring correctness (G3, G4):** The scoring core is a pure function. Test inputs are representative. Score pinning against 19 papers is operationally equivalent to a replay. No LLM is involved. **Substitution: FULL.**

2. **Fusion logic (G1 partial):** `fuse_verdicts()` is a deterministic function of two dicts. Testing it with synthetic dicts is equivalent to testing it with real dicts (the function does not know where its inputs came from). **Substitution: FULL.**

3. **Canary detection (G6):** The fact engine is deterministic. The canary tests feed known mutations and check known outcomes. No LLM involved. **Substitution: FULL.**

4. **License compliance (G7):** Static analysis. No runtime needed. **Substitution: FULL.**

### Where substitution is PARTIAL:

5. **Error handling (G2):** The exception-catching logic is correct by inspection. But the behavior of the real error (what exception type a timeout raises, whether the stack unwinds cleanly) depends on the runtime environment. **Substitution: PARTIAL (logic proven, trigger unverified).**

6. **Deterministic replay (G3, workspace-level):** Score pinning proves function-level determinism. Workspace-level replay (disk read -> parse -> score -> write) is not tested but each step is individually tested. **Substitution: PARTIAL (composition gap).**

### Where substitution is INVALID:

7. **Prompt injection resistance (G5):** Whether a real model obeys guard instructions is a property of the model, not the code. You cannot mock this. **Substitution: INVALID.** The code proves the defense is installed; only runtime proves it works.

8. **Advisory lane quality:** Whether the LLM produces useful verdicts cannot be tested offline. The entire advisory lane's value proposition depends on model behavior. **Substitution: INVALID.**

9. **Readback comprehension:** Same as above. The model either comprehends the paper or it does not. Offline tests prove the scoring infrastructure, not the model's capability. **Substitution: INVALID.**

10. **Constrained decoding enforcement (D6):** Whether the vllm_thinking backend actually constrains output to the pydantic schema is a property of the backend software, not of the whisker code. **Substitution: INVALID.**

---

## 5. Impact on Final Verdict

### The two-lane architecture limits the damage

Whisker's most important property is that the **deterministic lane operates independently of the advisory LLM lane.** This means:

- The core scoring (gates, metrics, facts, guard, golden) is fully testable offline.
- The advisory lane's blocked runtime evidence does NOT affect the deterministic lane's claims.
- Fusion cannot promote fail-to-pass (proven offline with full substitutability).
- The exit codes are computed from the deterministic lane only.

The blocked runtime therefore affects the **advisory lane's quality claims** but NOT the **deterministic lane's correctness claims.**

### What the final verdict CANNOT claim without runtime:

1. "The advisory lane produces useful verdicts." (Unproven.)
2. "Prompt injection is resisted in practice." (Defense installed, efficacy unproven.)
3. "The system handles real endpoint failures gracefully." (Logic proven, real failures untested.)
4. "Readback validates paper comprehension." (Infrastructure tested, model capability unproven.)
5. "The constrained decoding backend enforces schema." (Assumed, not verified.)

### What the final verdict CAN claim without runtime:

1. "The deterministic scoring pipeline is correct and deterministic." (Proven: 19-paper pinning, explicit determinism tests, pure-function architecture.)
2. "Gates trip on known defects." (Proven: 3 inverted canaries, gate teeth tests.)
3. "Advisory verdicts cannot override deterministic gates." (Proven: fusion logic, import absence, frozen fields.)
4. "Ineligible axes are None, not inflated." (Proven: non-trivial offline tests.)
5. "All dependencies are permissively licensed." (Proven: inspection + parity test.)
6. "Batch isolation prevents cascade failures." (Proven for serial execution: per-paper try/except.)
7. "Prompt injection defenses are architecturally installed." (Proven: code inspection of all call sites.)

---

## 6. Blocked Evidence Is Not Negative Evidence

A critical distinction for C30:

- **Blocked** means "we could not run the test." It does NOT mean "we ran the test and it failed."
- The blocked runtime matrix is an **evidence gap**, not a **finding of deficiency.**
- The system may well handle all 10 scenarios correctly. We simply cannot prove it in this audit.
- Historical runs (Audit v1, developer testing) may have covered some scenarios, but per Runbook section 8: "Historical runs do not replace a current proof."

---

## 7. Recommendations for C30

1. **Do not claim runtime-verified for any advisory lane property.** All advisory lane claims should carry the qualifier "code-verified, runtime-unproven."

2. **The deterministic lane CAN be claimed as verified.** The offline evidence is operationally equivalent to runtime proof for pure-function scoring.

3. **G5 (Prompt injection) is the weakest gate.** Its proof is entirely code inspection. No substitute for runtime exists. If forced to give a binary pass/fail, it passes on architecture (defense installed) but fails on efficacy (defense untested).

4. **The 4 PASS-PROVISIONAL gates (C26) should remain provisional.** Do not upgrade them to full PASS without runtime evidence.

5. **Acknowledge the systemic root cause.** The entire runtime gap has one root cause: `ALLIANCE_POD_KEY` not set. When credentials become available, all 10 scenarios can be run in a single session to close all gaps simultaneously.

---

## 8. Meta-Observation: The Audit's Structural Honesty

The primary reports (C01-C25) consistently and honestly declare their runtime limitations. Every report that touches the advisory lane includes a "Limitations" section noting "Runtime proof BLOCKED." No report claims runtime-verified status for a blocked scenario. No report hides the gap.

This structural honesty is itself evidence of audit integrity. A dishonest audit would omit the limitations or claim that offline tests are equivalent to runtime proof. These reports do neither.

The adversarial meta-reviewer's job is to ensure this honesty translates into the final verdict: **the audit is sound, the evidence is partial, and the partial evidence is clearly labeled.** That is the case here.
