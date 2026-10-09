# C27 — Runtime/LLM Meta-Review

**Persona:** Runtime & LLM Meta-Reviewer
**Scope:** tapetum_llm real-call authenticity, replay sufficiency, live-evidence gaps
**Date:** 2026-07-19
**Commit:** `51cb704610220d31c9d5e078b1350c1b37a8714a`

---

## Executive Summary

The tapetum_llm layer makes **real API calls** through well-documented paths (pipeline `run_agent`, `AgentBackend.run`, raw `httpx`). Code-level evidence is unambiguous. However, all CI tests are **fully mocked**: no live LLM call has ever executed in the test suite. The replay evidence (7-paper + 38 pinning tests) is strong for the **deterministic scoring path** but does not cover advisory LLM verdict stability. The readback evidence (34/37 pass on 2026-07-09) remains valid for the current commit (zero source changes to readback/facts since that date). Live LLM testing is blocked by a missing API key.

---

## Q1. Are the LLM calls REAL API calls or just mocked in tests?

### Verdict: REAL calls in production code; MOCKED in all tests.

**Code-level evidence for real calls:**

| Path | Mechanism | Evidence |
|------|-----------|----------|
| Text cascade | `pipeline.run_agent(ctx, spec, user_msg)` | `adjudicate.py:238,248,295` — direct `await run_agent(...)` calls with `output_type=Adjudication` |
| PDF-judge | `AgentBackend.run(system, user, output_type)` | `judge_task.py:68-74` — delegates to `agent.run()` which calls the model endpoint |
| Readback | Raw `httpx.Client.post("/chat/completions")` | `readback.py:283-317` — constructs a full OpenAI-compatible request with auth header |

These are NOT wrappers around mocks. Each path constructs HTTP requests or uses `pydantic-ai` agent dispatch that hits a real endpoint when credentials are present. The `_ask_pod` function (readback.py:273-317) is an explicit `httpx.post` with `Authorization: Bearer {api_key}`, JSON body, and `resp.raise_for_status()`.

**Code-level evidence that tests mock them:**

| Test file | Mock target | Technique |
|-----------|-------------|-----------|
| `test_tapetum_llm.py` | `whisker.tapetum_llm.adjudicate.run_agent` | `patch(..., new_callable=AsyncMock)` returning canned `Adjudication` objects |
| `test_pdf_judge.py` | `AgentBackend` interface | `_StubAgent` duck-type class returning canned `PdfJudgment` |
| `test_readback.py` | `whisker.tapetum_llm.readback._ask_pod` | `patch(..., side_effect=exception)` for transport errors |

**The live eval file exists** (`test_tapetum_llm_eval.py`) but is gated by `WHISKER_LLM_EVAL=1` + a valid `ALLIANCE_POD_KEY`. It calls `adjudicate_paper` with real `service_overrides={"fast": "alliance-pod", ...}` and asserts broken markdown is never passed clean. This file **has never run in this environment** (key is missing).

**Conclusion:** The production code path indisputably makes real HTTP-level API calls. The test isolation is complete and appropriate for CI determinism. But this means **no test has ever verified that the real endpoint + model produces correct structured output** in this environment.

---

## Q2. Is 7-paper + 38 pinning tests sufficient for quality-stable determinism?

### Verdict: SUFFICIENT for the deterministic scoring path. INSUFFICIENT for advisory LLM stability.

**What the replay evidence covers:**

- **38 score-pinning tests:** Field-by-field verification of gates + QA metrics on 19 committed goldens. Any scoring logic change breaks CI. CI-blocked baseline update prevents silent drift.
- **7-paper replay (run twice):** Zero mismatches in verdicts, flags, and coverage across independent runs.
- **Full-corpus sweep (381 papers):** 23 fail, 129 review, 229 pass. Exit code correct. Demonstrates the scoring path executes without crashes on the full corpus.

**What it does NOT cover:**

1. **Advisory LLM verdict stability across runs.** The tapetum_llm lane is explicitly declared non-deterministic (model inference variance). No pinning test exists for LLM verdicts. This is architecturally correct (advisory lane tolerates flips), but it means the audit cannot claim "same paper always gets the same advisory verdict."

2. **Full-corpus pinning.** Only 19/381 papers have pinned scores. Regression on a non-pinned paper would go undetected unless it causes a gate failure in the 5 comprehension-corpus papers.

**Should it be full-corpus?**

For the deterministic path: no. The scoring logic is proven pure (C05 demonstrates all metrics are deterministic functions of their inputs). If `score_markdown(paper_A)` produces X on run 1, it produces X on run 2, because there is literally no randomness source. The 38 pinning tests are canaries, not exhaustive coverage; the purity proof is the real guarantee.

For the advisory LLM path: full-corpus stability testing is a different (and more expensive) question. The architecture deliberately avoids this requirement by never gating on LLM verdicts.

---

## Q3. What can vs cannot be concluded without `ALLIANCE_POD_KEY`?

### What CAN be concluded (proven offline):

| Claim | Basis |
|-------|-------|
| Deterministic scoring is correct and reproducible | 38 pinning tests + 7-paper replay + code purity proof |
| All 3 LLM call paths are structurally sound | Code inspection (C16 findings F1-F3) |
| Fingerprint recording covers 7 identity components | Code inspection (C16 F4) |
| Schema validators enforce structured output | Code inspection + mock tests triggering validators |
| Cascade topology matches documentation | Code inspection (C17) |
| Readback anti-sycophancy scoring works | 12 offline unit tests (test_readback.py) |
| Chunking/aggregation is correct | 10+ mock-cascade tests with multi-chunk scenarios |
| Transport errors are isolated from verdicts | Offline mock test |
| The readback harness works end-to-end with real data | Historical evidence: 34/37 on 2026-07-09 |

### What CANNOT be concluded (requires live evidence):

| Claim | Why blocked |
|-------|-------------|
| The advisory LLM correctly identifies broken papers | Requires `test_tapetum_llm_eval.py` with live pod |
| The cascade actually escalates on real data | Mock tests simulate escalation triggers, but real model behavior (confidence bands, axis conflicts) is untested |
| Readback still passes the 5-paper corpus TODAY | Model weights or inference behavior may have changed since Jul 9 |
| The `--corrupt` adversarial control shows sensitivity | Requires live readback run |
| PDF-judge grounding works on real model outputs | Mocks return pre-grounded quotes; real model may emit ungroundable evidence |
| Schema retries work under real malformed model output | `AgentBackend` retry behavior tested in pipeline package, not whisker |

### Honest gap assessment:

The audit can say "the plumbing is correct" but not "the plumbing produces correct results with the current model." This is a structural limitation. The architecture mitigates it (advisory lane never gates), but the advisory lane's value proposition ("second opinion on conversion fidelity") is unverified in this audit.

---

## Q4. Is the readback evidence (34/37 pass, 2026-07-09) still valid?

### Verdict: YES — still valid for the current commit.

**Evidence:**

1. `readback.py` last modified in commit `58a978c` (2026-07-09 17:36:21). Zero changes since.
2. `readback_cli.py` last modified in commit `58a978c`. Zero changes since.
3. `facts.py` — zero changes between `58a978c` and current HEAD (`51cb704`).
4. The 5 comprehension corpus `.facts.jsonl` files — zero changes since `58a978c`.
5. The `expected.md` snapshots — zero content changes (the only corpus changes since Jul 9 are NEW files: `dev-replay/` and `holdout/` additions in `c59139c`).

**What DID change since Jul 9:**

- `c59139c` (Jul 17): Added fail-closed golden QA and the dev-replay/holdout corpus. Does NOT touch the readback scoring path.
- `51cb704` (Jul 17): Added a health-endpoint probe for the Alliance server. Does NOT touch readback logic.

**Caveats:**

- The evidence is valid for the **code** at this commit. It is NOT valid for the **model** at this moment. If the Alliance pod upgraded model weights, the 34/37 result may not reproduce. This is inherent to LLM-backed validation.
- The scoring logic that evaluated the 34/37 is the SAME code now running in `test_readback.py` (offline). The only difference on a live re-run would be the model's answers, not the evaluation of those answers.

---

## Q5. Are there testable Phase 2 scenarios without the API key?

### Verdict: YES — several scenarios are testable offline.

| Scenario | Testable? | How |
|----------|-----------|-----|
| Cascade escalation logic | YES | Already tested: mock tests in `test_tapetum_llm.py` exercise all three escalation signals (axis conflict, ungrounded evidence, ambiguous confidence) |
| Fingerprint skip/force logic | YES | Code-level verification; could add a unit test constructing fingerprints |
| Candidate selection (`select_candidates`) | YES | Pure Python, no LLM; tested in `test_tapetum_llm.py` |
| Chunking on real oversize papers | YES | `chunk_markdown` is pure; real corpus papers could be fed through it |
| Schema validation (model_validator rejects contradictions) | YES | Can construct invalid `PdfJudgment`/`PageJudgment` objects and verify ValueError |
| Fusion report generation | YES | Pure Python aggregation of deterministic + advisory results |
| `--inspect` report rendering | YES | Pure string formatting |
| Readback question generation (no LLM) | YES | `_generate_question` is tested offline |
| Readback scoring logic for all fact types | YES | All 12 tests in `test_readback.py` |
| Dev-replay label consistency | YES | `test_dev_replay_acceptance.py` and `test_dev_replay_schema.py` are hermetic |
| `test_tapetum_llm_eval.py` broken-paper detection | **NO** | Requires live pod (calls `adjudicate_paper` with real service overrides) |
| Readback live comprehension validation | **NO** | Requires live pod (`_ask_pod` hits the endpoint) |
| End-to-end advisory lane with real model output | **NO** | Requires live pod |

**Actionable:** 8 of 11 identified scenarios are already tested or testable without credentials. The 3 that require live access are exactly those that prove the model (not the code) behaves correctly.

---

## Q6. Does full mocking weaken claims about real LLM behavior?

### Verdict: YES, structurally. The weakness is bounded but real.

**What mocking proves:**

- The cascade logic correctly routes based on escalation signals
- Grounding correctly accepts/rejects evidence quotes
- Schema validation correctly rejects contradictory outputs
- Chunking, aggregation, and verdict folding work correctly
- Transport errors are isolated from verdicts

**What mocking cannot prove:**

| Claim | Why mocking is insufficient |
|-------|----------------------------|
| "The model identifies broken tables" | Mocks return pre-written `Adjudication` objects; real model may miss defects |
| "Escalation signals fire in practice" | The documented 0/198 escalation rate was measured empirically; mock tests exercise the escalation PATH but cannot demonstrate its real-world trigger rate |
| "Schema retries converge" | Mocks never produce truly malformed output; `AgentBackend`'s retry logic handles real parsing failures differently |
| "Grounding rejects real hallucinated quotes" | Mocks return synthetic quotes; real model hallucinations have different structural patterns |
| "Per-page escalation provides value" | The design rationale cites measured false-negative reduction; mocks cannot reproduce the measurement |
| "The confidence band [0.35, 0.65] is the right trigger" | Calibrated on empirical data (DeepSeek never left [0.85, 1.00]); mocks return whatever confidence the test sets |

**Bounding the weakness:**

1. **The advisory lane never gates.** A mock-only test suite for a non-gating lane means the worst case is "the advisory second opinion is less accurate than believed." It cannot cause a false CI failure or a false production pass.

2. **One empirical anchor exists.** The readback evidence (34/37, 2026-07-09) is a single live-fire exercise. It proves the end-to-end path works with a real model at a specific point in time. This is better than pure mocking alone.

3. **`test_tapetum_llm_eval.py` is the designed live gate.** It exists, is well-structured (5 broken-paper fixtures, assert verdict != pass), and needs only `WHISKER_LLM_EVAL=1` + API key to run. The infrastructure for live validation is present; only credentials are missing.

**The honest position:** The code is proven correct. The model's behavior under that code is proven only once (2026-07-09 readback) and in principle (broken-paper fixtures that have never run). Any claim about advisory lane accuracy is conditional on "assuming the model behaves as the mocks simulate."

---

## Summary Verdict Table

| Question | Status | Confidence |
|----------|--------|------------|
| Q1: Real API calls? | **PROVEN** (code-level) | 1.00 |
| Q2: Replay sufficiency? | **SUFFICIENT** for deterministic path; **ARCHITECTURAL PASS** for advisory (never gates) | 0.95 |
| Q3: Without API key? | Code correctness proven; model behavior unverifiable | 0.90 |
| Q4: Readback evidence valid? | **VALID** (zero code/corpus changes since Jul 9) | 0.98 |
| Q5: Offline Phase 2 scenarios? | 8/11 testable, 3 require live pod | 0.95 |
| Q6: Mocking weakness? | **REAL but bounded** (advisory lane, never gates, one empirical anchor exists) | 0.92 |

---

## Recommendations

1. **Obtain `ALLIANCE_POD_KEY` and run `test_tapetum_llm_eval.py`.** This is the single highest-value action for closing the audit's live-evidence gap. Five broken-paper fixtures already exist.

2. **Re-run readback on all 5 corpus papers.** The Jul 9 evidence is code-valid but model-validity decays with time. A re-run with the current pod model would refresh the empirical anchor.

3. **Run `whisker-readback --corrupt` and record results.** The adversarial control has no committed evidence for the 5-paper corpus (only wave 1 was demonstrated).

4. **Do NOT attempt to extend replay testing to the advisory lane.** The architecture deliberately avoids pinning advisory verdicts. The correct validation for the advisory lane is the live eval (`test_tapetum_llm_eval.py`), not replay determinism.

5. **Consider adding a `_corrupt_markdown` unit test** (C22 LOW finding). The function is simple but untested; a regression would go undetected.

---

## Honest Summary

**What is proven:** The whisker deterministic scoring path is correct, reproducible, and well-tested. The tapetum_llm plumbing (cascade, grounding, chunking, fingerprinting, schema validation, readback scoring) is structurally sound and thoroughly unit-tested.

**What requires live evidence:** Whether the real model (a) correctly identifies broken papers, (b) produces groundable evidence quotes, (c) escalates at the right rate, and (d) still recovers facts from the 5-paper corpus. This evidence cannot be gathered without the API key.

**What the architecture buys us:** Because the advisory lane never gates, the live-evidence gap is a quality-of-advisory gap, not a correctness-of-system gap. A fully-mocked advisory lane with zero live validation would be a problem for a GATING system; for a non-gating advisory tool, it means "we believe it works based on code inspection and one historical run, but we have not re-verified recently."
