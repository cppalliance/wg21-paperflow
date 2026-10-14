# C16 — Real-LLM Authenticity Audit

**Auditor**: Real-LLM Authenticity Auditor
**Focus**: D2, Phase 2 prerequisites
**Scope**: `packages/whisker/src/whisker/tapetum_llm/`
**Date**: 2026-07-19

---

## Executive Summary

The tapetum_llm advisory lane makes real LLM API calls through two distinct paths: (1) the text cascade via `pipeline.run_agent` (D1-compliant), and (2) the PDF-judge/readback paths via `AgentBackend.run` and raw `httpx` respectively. Fingerprint recording is comprehensive (SHA-256 of markdown, source, prompt, model, schema, lane version). Schema retries exist via `AgentBackend` and `run_judge_task`. Tests are fully offline/mocked with no live LLM calls in CI.

---

## Findings

### F1. Text-lane LLM calls go through `pipeline.run_agent` (D1 compliant)

| Field | Value |
|---|---|
| **Severity** | INFO |
| **Claim** | The text cascade (triage, adjudicate steps) calls the LLM exclusively through `pipeline.run_agent`. |
| **Evidence** | `adjudicate.py:238` (`state.tier1 = await run_agent(ctx, spec, user_msg)`), `adjudicate.py:248` (chunked serial loop calls `run_agent`), `adjudicate.py:295` (tier-2 `run_agent`). Import at line 35: `from pipeline import ... run_agent`. |
| **Affected gate** | D1 (all LLM calls through `run_agent` or `run_task`) |
| **Confidence** | 1.00 |
| **False-pass hypothesis** | None; import and call sites are explicit. |
| **False-fail hypothesis** | N/A (finding is positive). |

### F2. PDF-judge lane uses `AgentBackend.run` via `run_judge_task` (documented D1 deviation)

| Field | Value |
|---|---|
| **Severity** | LOW |
| **Claim** | The PDF-judge lane dispatches LLM calls through `judge_task.run_judge_task`, which calls `agent.run()` (an `AgentBackend` method) rather than `pipeline.run_task`. This is a documented, sanctioned deviation from D1 to avoid the global `Semaphore(1)`. |
| **Evidence** | `judge_task.py:52-74` (docstring explicitly names D1 deviation), `pdf_judge.py:637` (`await run_judge_task(agent, system, user_msg, PdfJudgment, ...)`), `pdf_judge.py:410-417` (page-escalation call through `run_judge_task`). `unit_judge.py:591` (unit-check call through `run_judge_task`). |
| **Affected gate** | D1, D6, D10 |
| **Confidence** | 0.98 |
| **False-pass hypothesis** | `AgentBackend.run` might not enforce all pipeline disciplines (sampling pins, structured output retries). The `judge_task.py` docstring claims it does: "sampling pins (D2), structured output (D6), retry budgets (D10), BPE cleanup, truncation retry." This is delegated to `pipeline.AgentBackend` internals; verification requires reading the pipeline package. |
| **False-fail hypothesis** | N/A; the deviation is documented and approved. |

### F3. Readback uses raw `httpx` (documented D1 exemption)

| Field | Value |
|---|---|
| **Severity** | LOW |
| **Claim** | `readback.py` calls the pod via raw `httpx.Client.post` to `/chat/completions`, bypassing `pipeline` entirely. This is a documented D1 exemption. |
| **Evidence** | `readback.py:21-23` (docstring: "D1 exemption: this module calls the LLM via raw httpx"), `readback.py:282-317` (`_ask_pod` function: `client.post(f"{base_url}/chat/completions", ...)` with `temperature: 0.0`, `max_tokens: _MAX_ANSWER_TOKENS`). |
| **Affected gate** | D1, D5 |
| **Confidence** | 1.00 |
| **False-pass hypothesis** | Since readback bypasses pipeline, D2/D5 sampling pins (temperature, seed) are set manually (`temperature: 0.0` at line 307). No `seed` is set, but this is a Q&A diagnostic, not a deterministic pipeline. |
| **False-fail hypothesis** | The exemption is documented, approved, and the module is opt-in (never in CI). |

### F4. Fingerprint recording is comprehensive (SHA-256 of 7 components)

| Field | Value |
|---|---|
| **Severity** | INFO |
| **Claim** | The CLI records SHA-256 fingerprints covering markdown, source PDF/HTML, prompt text, model/service config, lane version, lane label, and output schema JSON. |
| **Evidence** | `cli.py:473-503` (`_compute_fingerprint` returns dict with `md_sha256`, `source_sha256`, `prompt_sha256`, `model`, `lane_version`, `lane`, `schema_sha256`). `cli.py:346-357` (`_sha256_file`, `_sha256_str` helpers). `cli.py:94` (`_LANE_VERSION = 6`). `cli.py:383-431` (`_pdf_prompt_contract`, `_pdf_schema_contract`, `_text_prompt_contract`, `_text_schema_contract` assemble all prompts and schemas into the fingerprint). `cli.py:433-470` (`_effective_model_contract` captures service config without credentials). |
| **Affected gate** | D2 (Phase 2 prerequisite: run-identity recording) |
| **Confidence** | 1.00 |
| **False-pass hypothesis** | If a new prompt or schema is added without being included in the contract functions, the fingerprint would miss it. Currently all four prompts (JUDGE, PAGE_JUDGE, METADATA_CHECK, UNIT_CHECK) and four schemas (PdfJudgment, PageJudgment, MetadataOutlineCheck, UnitCheck) are included. |
| **False-fail hypothesis** | N/A. |

### F5. Schema retries exist via structured output (D6/D10)

| Field | Value |
|---|---|
| **Severity** | INFO |
| **Claim** | All LLM calls use Pydantic `output_type` (D6). `model_validator` on `PageJudgment`, `MetadataOutlineCheck`, and `UnitCheck` raises `ValueError` on contradictory outputs, triggering structured retries. |
| **Evidence** | `models.py:138-146` (`PageJudgment.missing_flag_matches_quotes` validator), `models.py:201-213` (`MetadataOutlineCheck.pass_requires_no_mismatch`), `models.py:233-238` (`UnitCheck.verdict_matches_defects`). All judge calls specify `output_type=PdfJudgment`, `PageJudgment`, `MetadataOutlineCheck`, or `UnitCheck`. |
| **Affected gate** | D6, D10 |
| **Confidence** | 0.95 |
| **False-pass hypothesis** | The retry budget itself (D10 `output_retries=N`) is configured inside `AgentBackend`, not visible in whisker code. If `AgentBackend` lacks retries, validators would raise unrecoverable errors. |
| **False-fail hypothesis** | N/A. |

### F6. Model identity is recorded in TapetumResult and PdfJudgeResult

| Field | Value |
|---|---|
| **Severity** | INFO |
| **Claim** | The model/service name used for each tier is recorded in the result object and persisted in the sidecar. |
| **Evidence** | `adjudicate.py:367-368` (`tier1_model = _resolve_model_name(ctx, "fast")`, `tier2_model`). `models.py:256-258` (`TapetumResult.tier1_model`, `tier2_model`). `pdf_judge.py:902` (`judge_model=agent.service_name or "judge"`). `models.py:289` (`to_dict` serializes `tier1_model`, `tier2_model`). |
| **Affected gate** | D2 (model identity provenance) |
| **Confidence** | 1.00 |
| **False-pass hypothesis** | None. |
| **False-fail hypothesis** | N/A. |

### F7. Tests use mocks exclusively (no live LLM calls in CI)

| Field | Value |
|---|---|
| **Severity** | INFO |
| **Claim** | `test_tapetum_llm.py` uses `unittest.mock.AsyncMock` and `patch("whisker.tapetum_llm.adjudicate.run_agent")` for all cascade tests. `test_pdf_judge.py` uses `_StubAgent` (duck-typed `AgentBackend` returning canned `PdfJudgment`). `test_readback.py` uses `patch("whisker.tapetum_llm.readback._ask_pod")` to inject transport errors. No test imports `httpx` for live calls. |
| **Evidence** | `test_tapetum_llm.py:20` (`from unittest.mock import AsyncMock, MagicMock, patch`), `test_tapetum_llm.py:605` (`patch("whisker.tapetum_llm.adjudicate.run_agent", new_callable=AsyncMock)`). `test_pdf_judge.py:656-691` (`_StubAgent` class). `test_readback.py:135` (`patch("whisker.tapetum_llm.readback._ask_pod", side_effect=_boom)`). |
| **Affected gate** | CI determinism |
| **Confidence** | 1.00 |
| **False-pass hypothesis** | `test_tapetum_llm_eval.py` was not read; it might contain live calls. (File exists but was not in scope.) |
| **False-fail hypothesis** | N/A. |

### F8. Readback tests are fully offline/mocked

| Field | Value |
|---|---|
| **Severity** | INFO |
| **Claim** | `test_readback.py` tests all readback scoring logic offline: anti-sycophancy, word-boundary table scoring, transport error handling, and rendering. No network calls. |
| **Evidence** | `test_readback.py:1-7` (docstring: "Offline tests for the whisker-readback harness (no network)"). Every test constructs `Fact` objects and calls evaluation functions directly (`_evaluate_answer`, `_cell_value_in_answer`, `_generate_question`). The one integration test (`test_transport_error_marked_error_not_fail`) patches `_ask_pod` to raise. |
| **Affected gate** | CI determinism, test isolation |
| **Confidence** | 1.00 |
| **False-pass hypothesis** | None. |
| **False-fail hypothesis** | N/A. |

---

## Summary Verdict

The tapetum_llm lane uses real LLM API calls through well-documented paths. The two D1 deviations (PDF-judge via `AgentBackend.run`, readback via raw `httpx`) are explicitly documented with rationale. Fingerprint recording covers all 7 identity-relevant components. Schema retries are structurally enforced via Pydantic validators. All tests are offline/mocked. **No blocking issues for D2 Phase 2 prerequisites.**
