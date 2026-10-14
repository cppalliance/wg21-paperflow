# Card 05 — Official DeepSeek V4 think-off

**Source report:** `05-web-think-off-official.md`  
**Date foraged:** 2026-07-24

## Bottom line

Non-think is the official Instant path for latency-sensitive structured work. Hosted API: `extra_body={"thinking": {"type": "disabled"}}`. vLLM: `chat_template_kwargs.enable_thinking=false` (verify against alliance-pod image). Default on V4 is thinking on. A prior 2026-07-07 probe said alliance-pod ignored `thinking_token_budget` and emitted no hidden reasoning — that may mean already Non-think, or kwargs not wired. Must re-probe with explicit false vs true under structured UnitCheck.

## Numbers

- Official: thinking defaults **on** (`reasoning_effort` high).
- Flash = Instant Mode model swap; Pro = Expert. Flash is not a flag.
- No fleet wall arithmetic in this short note; lever is per-call decode (L), not S.

## Architecture implication

Client-side think-off on mechanical unit/metadata judges is the first legal L dial under S_eff=16. Do not treat Flash as a software switch on the current Pro pod. Confirm which wire format alliance-pod honors before wiring whisker.

## Reject-or-A-B

**A/B required.** Probe `enable_thinking: false` vs true; measure `completion_tokens` + wall. Do not bank savings until the live kwargs path is proven.

## Links

- deepseekai.guide API docs; chat-deep.ai thinking mode; vLLM recipes
- Hosted: `thinking: {"type": "disabled"}`
- Related: `05a`, `05c`, `05q`
