# ADR-019: Keep schema-in-prompt (VllmThinkingBackend path)

## Status

Accepted

## Date

2026-07-24

## Context

`alliance-pod` and other `vllm_thinking` services produce structured judge output through `pipeline.model_backends.VllmThinkingBackend`: schema text injected into the system prompt, raw completion, JSON extract, retry. That path exists because tool-calling / server guided decoding on thinking models is unreliable or slow (vLLM issues catalogued in `MODELS.md` and community forage `05i`).

Cold-run speed work repeatedly surfaces the temptation to “fix” JSON or cut decode via server `guided_json` / `guided_grammar`, OpenAI-style `json_schema`, or speculative decode paired with grammar masks. Community and prior corpus evidence say the opposite for our stack: guided decoding drops throughput at batch ≥8; `guided_grammar` with reasoning can collapse to ~0.1 tok/s; MTP × reasoning × grammar fails when `</think>` is missed; schema-in-prompt already avoids most of those cliffs while preserving D6 structured output + output retries.

## Decision

Keep **schema-in-prompt + extract + retry** as the structured-output path for tapetum LLM judges on `vllm_thinking` backends.

1. Do **not** migrate whisker/tapetum judges to server `guided_grammar`, speculative `guided_json`, or “guaranteed JSON” server masks for speed.
2. Continue emitting Pydantic `output_type` schemas into the prompt via `VllmThinkingBackend` (and equivalent backends for dense Qwen judges on the same registry key).
3. Pursue decode shrink via **client** levers only: verdict-first / terse pass schema, per-call `max_tokens`, Non-think kwargs on mechanical judges after A/B — not via guided decoding.
4. Treat proposals to arm guided decoding on `alliance-pod` for cold-wall wins as **rejected** unless new evidence overturns `05i` / `MODELS.md` under load-matched c≈16.

## Consequences

**Positive**

- Avoids known throughput cliffs and MTP×grammar failure modes.
- Preserves existing retry / validation fidelity (D6 + output_retries).
- Aligns cold-run program with production pipeline invariants; no second structured-output stack.

**Negative / cost**

- Schema compliance remains probabilistic; invalid JSON still costs retries (bounded by `request_limit` / output_retries).
- Not bit-guaranteed JSON at the sampler; quality gates and holdouts remain mandatory when shrinking schemas or disabling thinking.

**Invariants**

- Never `thinking.enabled` with `json_object` (client CN/hosted invariant).
- Do not enable thinking solely to “fix” schema compliance.
- MTP k=1 remains A/B-only and must not depend on guided masks.

## Evidence

| Claim | Source |
|-------|--------|
| Stack path = schema-in-prompt + extract + retry, not server guided_json | `05i-web-community-workarounds.md`, `VllmThinkingBackend` in `packages/pipeline/src/pipeline/model_backends.py` |
| Guided decoding slow / grammar~0.1 tok/s; keep schema-in-prompt | `05i-web-community-workarounds.md` (SqueezeBits, vLLM#12122, #16182, #34650) |
| Reject ledger: server `guided_grammar` / speculative `guided_json` | `SYNTHESIS.md`, `PLANNING-HANDOFF.md` §8 |
| Client invariants: thinking × json_object | `SYNTHESIS.md` |
| Workaround inventory / retire-when | `MODELS.md` |
