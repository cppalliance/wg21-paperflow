# 59 - DeepSeek-V4-Pro Official Release / API Notes

**Verdict:** usable — official V4 Preview notes give a clear latency dial (Non-think / Flash / thinking-off) that our cold fleet never turns; local sampling tip (`temperature=1.0`) is quality/serving guidance, not a wall-time lever under thinking mode.
**Confidence:** high (primary claims from DeepSeek API docs + HF model card, fetched 2026-07-24)

## Sources (official / first-party)

| Source | URL | Date / note |
|--------|-----|-------------|
| DeepSeek V4 Preview Release | https://api-docs.deepseek.com/news/news260424 | 2026-04-24 changelog sibling |
| API Change Log (V4) | https://api-docs.deepseek.com/updates/ | Date: 2026-04-24 |
| Thinking Mode guide | https://api-docs.deepseek.com/guides/thinking_mode | live API guide |
| First API Call | https://api-docs.deepseek.com/ | model IDs + curl sample |
| Temperature Parameter | https://api-docs.deepseek.com/quick_start/parameter_settings | defaults + use-case table |
| Context Caching | https://api-docs.deepseek.com/guides/kv_cache | prefix-hit rules |
| Context Caching launch note | https://api-docs.deepseek.com/news/news0802/ | FT latency example |
| HF DeepSeek-V4-Pro README | https://huggingface.co/deepseek-ai/DeepSeek-V4-Pro | modes + local sampling |
| HF inference README | …/inference/README.md | convert / torchrun serving sketch |

Third-party blogs (NVIDIA NIM card, HF blog, chat-deep.ai) only used as cross-checks; latency claims below cite DeepSeek or HF card text.

## Findings

- [CRITICAL] **Official latency dial is Non-thinking (and Flash), not more Pro thinking.** Release note: V4-Flash is the "fast, efficient" tier with "faster response times"; V4-Pro is the quality/agentic tier. Thinking Mode guide: toggle defaults to **enabled**; Non-think is the opt-out via `thinking: {"type": "disabled"}` (OpenAI SDK: `extra_body`). HF card: Non-think = "Fast, intuitive responses" / routine tasks; Think High = "slower but more accurate"; Think Max = fullest effort. Impact: our cold path pins `model=deepseek-v4-pro` on `vllm_thinking` (`SERVICES.toml` alliance-pod / h200x8) and never sends Non-think; baseline decode dominates (~5.91 s vs 0.46 s prefill). **This is the official latency tip we ignore.**

- [HIGH] **Reasoning API surface (hosted):** `thinking.type` = `enabled`|`disabled` (default enabled); `reasoning_effort` = `high`|`max` (default high; some agent clients auto-`max`; `low`/`medium`→`high`, `xhigh`→`max`). Example curl uses `deepseek-v4-pro` + thinking enabled + `reasoning_effort: high`. CoT returns in `reasoning_content` beside `content`. Impact: self-hosted path uses vLLM `chat_template_kwargs.enable_thinking` / `thinking_token_budget` (`model_backends.py`), not the hosted `thinking` / `reasoning_effort` objects; tapetum intentionally omits `thinking_budget` (pod ignores it per `tapetum_llm.md` / `cli.py`). No client path maps unit-check "routine" work onto Non-think.

- [HIGH] **Think Max needs ≥384K context.** HF README: local deploy recommend `temperature=1.0, top_p=1.0`; Think Max recommend context window **≥384K**. Our pods set `max_context_window = 393216` (~384K) — aligned for Max, but we do not select Max vs High via API. Impact: context floor for Max is already satisfied; not a ignored latency tip.

- [HIGH] **Thinking mode ignores sampling knobs.** Official Thinking Mode guide: thinking mode **does not support** `temperature`, `top_p`, `presence_penalty`, `frequency_penalty` (setting them is a no-op, no error). Non-thinking temperature table: default `1.0`; Coding/Math `0.0`; Data analysis `1.0`; Conversation/Translation `1.3`; Creative `1.5`. HF local recommend stays `temperature=1.0, top_p=1.0` across modes. Impact: our hard pin `temperature=0.0` (`MODELS.md` / `VllmThinkingBackend`) is a **determinism** choice (D5), not an official latency optimization; under thinking it is officially inert on the hosted API. Do not treat "switch to 1.0" as a cold-run wall-time lever.

- [MED] **Hosted Context Caching latency tip (prefix identity).** Caching guide: hits require full match of a persisted **cache prefix unit** (request-boundary, common-prefix detection, or fixed token intervals). Launch note: long repetitive inputs cut first-token latency (example: 128K high-reference prompt **13s → 500ms**). Impact: applies to DeepSeek's hosted disk cache; our RunPod/vLLM APC is a different mechanism. Client-side we already chase prefix reuse (HMAC guard + markdown-first reorder, persona 12). Not "ignored" on the self-host path; the 13s→500ms number is not a pod claim.

- [MED] **Legacy IDs die today (UTC).** `deepseek-chat` / `deepseek-reasoner` retire **2026-07-24 15:59 UTC**, previously aliased to V4-Flash non-thinking / thinking. Impact: our services already use `deepseek-v4-pro`; no migration debt. Confirms Flash Non-think was the official "chat/fast" productization.

- [LOW] **Suggested serving (weights).** HF: FP4 experts + FP8 elsewhere for instruct; convert.py with `EXPERTS=384`, `MP=8` for Pro; torchrun generate. NVIDIA NIM card (secondary): vLLM + sparse-attention optimization, Hopper H100/H200, FP4+FP8. Impact: matches our H200×8 / vLLM posture; no unused official serving flag found that would cut decode without changing thinking policy.

## Official latency tip we ignore (answer)

**Disable thinking (Non-think / Instant) for latency-sensitive or routine structured work — and/or use Flash when Pro-depth is not required.**

DeepSeek products this explicitly: thinking defaults **on**; Non-think is the fast path; Flash is marketed for faster responses; Think High/Max trade latency for accuracy. Our cold fleet keeps **V4-Pro + thinking always on**, while measured time is **decode-bound**. That is the gap between official guidance and our serving policy. (Prefix caching and `temperature=1.0` are secondary; the former we already pursue on vLLM, the latter is not a thinking-mode latency control.)

## False-pass hypothesis

Flipping unit checks to Non-think because the HF table says "routine daily tasks," then declaring quality unchanged without a 381-paper A/B — Non-think collapses hard STEM/coding scores on the official mode table; a silent quality cliff would look like a free wall win.

## False-fail hypothesis

Rejecting Non-think entirely because "MODELS.md requires temperature=0 thinking" — hosted thinking mode already ignores temperature; Non-think is an orthogonal, officially supported mode, not a violation of the sampling pin.

## What would change my mind

A holdout A/B where Non-think (or Flash Non-think) on unit-check / zero-defect-heavy calls matches Pro-High defect-group recall within the existing ≥25% same-model flip noise, with measured mean decode dropping enough to put the residual fleet under 600 s after metadata short-circuit.
