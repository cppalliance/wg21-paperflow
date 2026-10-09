# Card 05i — Community workarounds (V4-Pro slow / thinking tax / structured)

**Source report:** `05i-web-community-workarounds.md`  
**Verdict in source:** usable

## Bottom line

Community consensus: **default thinking is the dominant latency tax**; **MTP k=1 (or tuned MTP-2) is the main decode tok/s lever**; **server guided decoding is a trap** for our schema-in-prompt path. DSpark-on-saturated-batch, guided_grammar, and stream:false-alone are anti-patterns for alliance-pod.

## Numbers

- Classifier non-stream: **31.8 s → 2.7 s** with thinking disabled (#1464); depot: reasoning ~**77%** of completion tokens, wall ~**3×**; disable+Flash → **19 s vs 60 s+**.
- Trivial prompts still burn **30–300** reasoning_tokens (harness C1); uncapped reasoning **8000+** chunks / ~84 s (C3).
- GH200 Pro MTP: 13.0 → 17.8 (k=1) → 21.2 (k=2) → 18.9 (k=3) tok/s; Flash W4A16+MTP **52.9→85.5** (+62%).
- DSpark marketing +57–78%; saturated B300 Flash: DSpark **~344** vs no-spec **~773** aggregate tok/s (#49369).
- guided_grammar + reasoning: ~**0.1 tok/s** (#12122); breakable-cudagraph fix ~**1.57×** (#49370).
- Prior scout: verdict-first **−124 to −360 s**; MTP k=1 ~**7–16%** cold wall. Stack 1+2+3 + call elimination; none alone hits ≤600 s from MODERATE ~1366–1493 s.

## Architecture implication

Ranked: (1) Non-think on mechanical judges, (2) verdict-first + tight max_tokens, (3) MTP k=1 + CUDA graphs, (4) keep schema-in-prompt / ban guided_grammar for speed, (5) dense/Flash-class offload, (6) cudagraph env audit, (7) prefix-stable prompts, (8) defer DSpark. Keep `stream=true`.

## Reject-or-A-B

**A/B ranks 1–3.** **Reject:** twin Pro; seqs=32 / c>32; stream:false under default thinking; guided_grammar for stricter JSON; fail-open. If Non-think flips ≥5% review/fail on holdout → demote to escalation-only disable.

## Links

- https://github.com/deepseek-ai/DeepSeek-V3/issues/1464
- https://github.com/HenryZ838978/deepseek-harness
- https://dnhkng.github.io/posts/gh200-benchmarking-part-2/
- vLLM #16182 / #12122 / #34650 / #49002 / #49369 / #49370
- https://blog.squeezebits.com/guided-decoding-performance-vllm-sglang
