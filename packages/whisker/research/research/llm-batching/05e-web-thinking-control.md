# Web Forager: vLLM 0.24 Thinking / Reasoning Control for DeepSeek V3.1 / V4

Research date: 2026-07-07. Target stack: vLLM **0.24.0**, self-hosted `deepseek-v4-pro`, OpenAI-compatible `/v1/chat/completions`. Client today: `max_tokens=4096`, no thinking budget, no `chat_template_kwargs`.

Question: What API-level knobs cap or disable reasoning per request, what latency guidance exists for thinking on vs off, and can thinking be toggled per request on an OpenAI-compatible endpoint?

---

## Finding: vLLM Reasoning Outputs (v0.24.0 official docs)

**URL:** https://docs.vllm.ai/en/v0.24.0/features/reasoning_outputs/

**Summary:** vLLM exposes per-request reasoning control on `/v1/chat/completions` via `chat_template_kwargs` (OpenAI Python: `extra_body={"chat_template_kwargs": {...}}`; raw JSON: top-level `"chat_template_kwargs"`). **DeepSeek-V3.1** uses `"thinking": true|false` (disabled by default). **DeepSeek-V4-Pro** requires `"enable_thinking": true` to emit reasoning tokens; without it, no reasoning is generated regardless of other flags. Top-level `"reasoning_effort": "none"` auto-injects `enable_thinking=false`; `"low"|"medium"|"high"` injects `enable_thinking=true` (explicit `chat_template_kwargs` overrides). Hard cap: `"thinking_token_budget": <int>` forces early termination of the reasoning block (needs `--reasoning-parser` at serve time). Reasoning is returned in message field `"reasoning"` (formerly `reasoning_content`). Server default: `--default-chat-template-kwargs '{"enable_thinking": false}'`; request kwargs always win.

**Relevance:** HIGH

---

## Finding: DeepSeek-V4-Pro vLLM Recipe — three reasoning modes

**URL:** https://recipes.vllm.ai/deepseek-ai/DeepSeek-V4-Pro

**Summary:** Official vLLM deployment guide lists three modes: **Non-think** ("fast, intuitive responses"), **Think High**, and **Think Max** (needs `--max-model-len >= 393216`). Non-think is the bare request with no extra fields. Think modes require `extra_body={"chat_template_kwargs": {"thinking": True, "reasoning_effort": "high"|"max"}}`. Serve flags: `--reasoning-parser deepseek_v4 --tokenizer-mode deepseek_v4`. No published ms benchmarks, but non-think is explicitly labeled the fast path; think high/max add chain-of-thought decode overhead.

**Relevance:** HIGH

---

## Finding: DeepSeek-V3.1 vLLM Recipe — per-request think toggle

**URL:** https://github.com/vllm-project/recipes/blob/main/DeepSeek/DeepSeek-V3_1.md

**Summary:** Hybrid V3.1 model switches think/non-think per request on the OpenAI-compatible endpoint. Disable: `extra_body={"chat_template_kwargs": {"thinking": False}}` or curl `"chat_template_kwargs": {"thinking": false}`. Enable: `"thinking": true`. Example compares outputs for the same prompt with thinking on vs off (thinking off yields shorter direct answers). Documents that vLLM supports dynamic mode switching without server restart; request-level kwargs are the control surface.

**Relevance:** HIGH

---

## Finding: DeepSeek API Thinking Mode (hosted API reference)

**URL:** https://api-docs.deepseek.com/guides/thinking_mode

**Summary:** On the **hosted DeepSeek API** (not vLLM), thinking defaults to **enabled**. Toggle: `extra_body={"thinking": {"type": "disabled"}}` or `"enabled"`. Effort: `"reasoning_effort": "high"|"max"` (low/medium map to high). Chain-of-thought returned as `reasoning_content` (vLLM uses `reasoning` instead). Docs do not publish latency tables, but describe thinking as pre-answer CoT that improves accuracy at the cost of extra generated tokens. **Do not copy hosted `thinking.type` syntax to vLLM**; self-hosted control is `chat_template_kwargs`.

**Relevance:** MED

---

## Finding: deepseek-v4-pro non-streaming timeout — thinking drives ~30 s TTFB

**URL:** https://github.com/deepseek-ai/DeepSeek-V3/issues/1464

**Summary:** Production report: `deepseek-v4-pro` non-streaming call with default thinking hit **~31.8 s TTFB** at ~2.9K input tokens, crossing a ~30 s client timeout. Maintainer/community consensus: non-streaming + default thinking means **TTFB ≈ full reasoning decode time**; latency-sensitive callers should send `extra_body={"thinking": {"type": "disabled"}}` (hosted API syntax) or use streaming. Issue filed against hosted API behavior but quantifies the latency gap our baseline suspects (15–30 s/paper decode dominated by reasoning traces when thinking is on).

**Relevance:** HIGH

---

## Finding: DeepSeek V4 Production Playbook — non-thinking is fastest/cheapest

**URL:** https://deepseekai.guide/api/deepseek-api-best-practices/

**Summary:** Third-party production guide (hosted API) states V4 enables thinking by default and recommends explicit opt-out for chat, classification, RAG, and structured extraction: `extra_body={"thinking": {"type": "disabled"}}`. Describes three tiers: **non-thinking = "fastest and cheapest"**, thinking high = multi-step reasoning with `reasoning_content`, thinking max = hardest agent workloads (384K context). Maps to vLLM self-host as: omit think kwargs (V4-Pro recipe non-think path) or pass `"reasoning_effort": "none"` / `"chat_template_kwargs": {"enable_thinking": false}` on the OpenAI-compatible endpoint.

**Relevance:** MED
