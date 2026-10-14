# C16 Real-LLM Authenticity

**Role**: Document the LLM call architecture without running it.
**Audited state**: whisker 0.5.0, HEAD 51cb704 + local mods.
**Gates**: D1 (All LLM calls via pipeline), D2 (Model identity and fingerprinting).

## 1. Scope

Document how LLM calls are dispatched, which endpoint and model identity are
used, how fingerprinting ensures incremental correctness, and what the sidecar
schema records. ALL runtime evidence is BLOCKED (ALLIANCE_POD_KEY not set).

## 2. Commands and Exits

No runtime commands can be executed. All evidence is from code inspection.

```
# Would require:
uv run whisker-tapetum-llm --help
uv run whisker-tapetum-llm p1234r0 --debug
```

Both BLOCKED: credential denial prevents any live LLM interaction.

## 3. Current Evidence

### 3.1 Endpoint and model identity

`SERVICES.toml` lines 64-74 define `alliance-pod`:
- backend: `vllm_thinking`
- base_url: `https://sgjy18glyi4blu-8000.proxy.runpod.net/v1`
- api_key: `$ALLIANCE_POD_KEY` (env var, not committed)
- model: `deepseek-v4-pro`
- max_context_window: 393216
- thinking_capable: true
- tools_capable: true

`tapetum_llm.md` lines 21-23 declare all three slots (fast, deep, default)
resolve to `alliance-pod`. This means the entire advisory lane runs on one
model endpoint.

### 3.2 Service resolution chain

`tapetum_llm/cli.py` resolves services via:
1. `load_services()` from `pipeline.services` reads `SERVICES.toml`.
2. `resolve_pipeline_models()` maps slot names (fast, deep, default) to
   `AgentBackend` instances.
3. CLI `--service` override: `--service NAME` (all slots) or
   `--service SLOT=NAME` (one slot).

`adjudicate.py` lines 87-90: `_SLOT_MAX_TOKENS = {"fast": 1024, "deep": 2048}`.
These token ceilings are bound per slot at agent construction.

### 3.3 LLM call dispatch

Two dispatch paths exist, both using `AgentBackend.run()`:

1. **Text cascade** (`adjudicate.py`): Uses `run_agent()` from `pipeline`.
   This goes through `pipeline.runner` which manages the pipeline context,
   step hooks, and dispatch. The `AgentBackend` wraps a `ModelBackend`
   (`VLLMThinkingBackend` for `vllm_thinking` services).

2. **PDF judge** (`judge_task.py`): Uses `run_judge_task()` which calls
   `agent.run()` directly. Documented D1 deviation: bypasses `run_task`'s
   global semaphore but preserves all model-level disciplines (D2 sampling
   pins, D6 structured output, D10 retry budgets).

Both paths use `AgentBackend` which encapsulates:
- Sampling pins (temperature, seed) from D2/D5
- Structured output via `output_type` (D6)
- Retry budgets (`output_retries`) from D10
- BPE cleanup and truncation retry
- Thinking-block stripping

No raw `pydantic_ai.Agent` construction or `chat.completions.create` calls
exist in whisker code.

### 3.4 Fingerprinting for incremental correctness

`tapetum_llm/cli.py` computes a fingerprint per paper for incremental skip:

Components include:
- Paper markdown content hash
- Source file content hash
- System prompt hash (from tapetum_llm.md)
- Output schema version (currently 7, from `models.py`)
- Service configuration (model name, base_url)
- Lane version string
- Ideal presence/content hash (when applicable)

When a paper's fingerprint matches the existing sidecar, the paper is skipped
(`--incremental` mode or auto-skip in default full-run mode). A change in
any component invalidates the cached result.

### 3.5 Sidecar schema (v7)

`TapetumResult.to_dict()` (models.py line 361) produces the sidecar with:
- `pid`, `status` ("ok" or "error")
- `whisker_verdict` (deterministic, recorded for reference)
- `suggested_verdict` (advisory)
- `confidence` (rounded to 4 decimal places)
- `escalated` (bool), `escalation_signals` (sorted list)
- `tier1_model`, `tier2_model` (service names, None if unused)
- `axis_findings` (sorted by axis)
- `grounded_evidence` (sorted by quote + start)
- `evidence_dispositions`, `evidence_summary`
- `ungrounded_dropped` (count)
- `primary_concern`, `reasoning`
- `metadata_outline_check`, `unit_coverage`
- `advisory: True` (immutable)
- `schema_version: 7`
- Optional: `risk_signals`, `defect_groups`, `unit_checks`, `ideal_verification`

The PDF judge sidecar (`PdfJudgeResult.to_sidecar_dict()`, pdf_judge.py
line 457) adds:
- `source_kind: "pdf"`, `lane: "pdf_textlayer_judge"`
- `textlayer_diff: {text_nid, content_recall, page_count}`
- `page_screen` (per-page recall entries)
- `page_escalations` (scoped LLM results)

Both paths record model identity (`tier1_model`, `judge_model`) in the
sidecar, enabling provenance tracking.

### 3.6 Model identity in sidecar

`adjudicate.py` lines 367-368:
```python
tier1_model = _resolve_model_name(ctx, "fast")
tier2_model = _resolve_model_name(ctx, "deep") if escalated else None
```

`pdf_judge.py` line 907: `judge_model=agent.service_name or "judge"`.

These record the service name (e.g., "alliance-pod") in the sidecar, not just
the model name, enabling endpoint provenance.

### 3.7 No mock/stub bypass

The advisory lane has no mock mode, test mode, or stub endpoint. The only
path to an LLM call is through `AgentBackend.run()` which contacts the real
endpoint. The credential gate (`ALLIANCE_POD_KEY`) is the only barrier.

## 4. Findings

| # | Finding | Severity | Confidence |
|---|---------|----------|------------|
| F1 | All LLM calls go through AgentBackend.run(), no raw API calls | Informational (confirms D1) | HIGH |
| F2 | Service identity recorded in sidecar (tier1_model, judge_model) | Informational (confirms D2) | HIGH |
| F3 | Fingerprinting covers content, schema, prompt, service, and ideal | Informational | HIGH |
| F4 | Schema version 7 with deterministic serialization (sorted, rounded) | Informational | HIGH |
| F5 | No mock/stub bypass exists; credential gate is the only barrier | Informational | HIGH |

No violations found.

## 5. False-Pass Hypothesis

**Could an LLM call bypass AgentBackend and contact an unintended endpoint?**

`judge_task.py` is the only whisker-local dispatch module. It takes an
`AgentBackend` parameter (not a URL or model name) and calls `agent.run()`.
An attacker would need to inject a different `AgentBackend` instance, which
requires control over the Python runtime, not just paper content.

**Could fingerprint staleness cause wrong model attribution?**

The fingerprint includes the service configuration (model + URL). If the
service changes in `SERVICES.toml` but the paper content doesn't, the
fingerprint still changes because the service hash component changes.

## 6. Gate/Dimension Mapping

- **D1 (All LLM via pipeline)**: PASS (code inspection). Every call goes
  through `AgentBackend.run()`. The PDF judge's D1 deviation (bypassing
  `run_task` gate) is documented and preserves model disciplines.
- **D2 (Model identity)**: PASS (code inspection). Service names are recorded
  in sidecars. Fingerprinting includes service configuration.

## 7. Limitations

- **ALL RUNTIME EVIDENCE BLOCKED**: Cannot verify that live calls actually
  reach `alliance-pod`, that the model responds as `deepseek-v4-pro`, or that
  sampling pins produce deterministic output.
- Cannot verify vLLM server-side behavior (MoE routing, batch scheduling).
- Cannot verify that the recorded `tier1_model`/`judge_model` matches the
  actual responding model (requires runtime inspection of response headers
  or model self-identification).
- Fingerprint collision probability is uninspected (depends on hash function).

## 8. Conclusion

The LLM call architecture is well-structured: all calls route through
`AgentBackend.run()` (D1), service identity is recorded in sidecars (D2),
and fingerprinting covers all relevant state for incremental correctness.
The sidecar schema (v7) provides full provenance. However, ALL runtime
evidence is blocked: no live call has been verified. The code architecture
is sound; endpoint authenticity requires runtime confirmation.
