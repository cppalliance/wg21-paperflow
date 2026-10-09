# CARD: 05n — V4 structured / guided-decoding latency

## Bottom line
Hosted DeepSeek V4 gives JSON syntax (`json_object`), not server `json_schema` on final content. Self-hosted guided JSON (XGrammar/llguidance) is near-free only for small, fixed, reused schemas; complex/unique nests, Outlines fallback, or short outputs make compile/mask cost dominate. First structured-call wall lever is disable thinking + slim pass schema, not grammar alone.

## Numbers
- Hosted: `response_format: {type: json_object}` only; thinking default on.
- Synthetic JSON check (thinking off, max_tokens=500): Flash median ~8.2 s vs Pro ~8.6 s.
- Fleet call wall ~20 s/call; clean UnitCheck JSON is a small fraction of that.
- Guided decode: XGrammar up to ~5× TPOT vs Outlines-era sync FSM under load; nesting past ~4 levels → 3–10× slowdown; Outlines FSM build >60 s timeout on fat schemas; prewarm cut cold p99 3–5×.
- Drop server guidance when unconstrained compliance ~90–94% or OSL <~64 tok (compile amortizes poorly).

## Architecture implication
Keep client Pydantic `output_type` + retries (D6/D10). Bifurcate pass vs findings schemas; flatten ≤2–3 nest; drop `minItems`/`pattern`/`ge` from served schema; fix+prewarm schema set if enabling guided JSON on alliance-pod. Hosted path: compact example shape + Non-think, not XGrammar.

## Reject-or-A-B
- **A/B (optional):** server guided JSON on alliance-pod only with cached slim pass schema + Non-think; pin backend (no silent Outlines).
- **Reject as wall-closer:** schema-slim alone closing the ~800–900 s post-MODERATE gap.
- **Do not:** treat pydantic-ai `output_type` as “already paying XGrammar”; copy OpenAI-style `json_schema` assumptions onto hosted V4; slim away `verdict`/`confidence` (raises rerun variance).

## Links
- Source: `05n-web-v4-structured.md`
- Related: `05i-web-guided-decoding-cost.md`, `62-schema-slim-web.md`, `00-baseline.md`, `15-verdict-first-design.md`
- https://api-docs.deepseek.com/guides/json_mode/
- https://blog.squeezebits.com/guided-decoding-performance-vllm-sglang
- https://vllm.ai/blog/2025-01-14-struct-decode-intro
