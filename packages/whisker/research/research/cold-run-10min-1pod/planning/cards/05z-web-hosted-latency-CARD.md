# CARD: 05z — Hosted latency priors (Pro vs Flash, think on/off)

## Bottom line
Hosted ratios are usable self-host priors; absolute Together/Fireworks peaks are not. Think on/off dominates wall (~8–9× E2E), not Flash vs Pro decode (~1.5–1.8×). Tok/s is nearly flat across think modes — wall scales with reasoning token count.

## Numbers
- AA DeepSeek 1P E2E to 500 answer tokens: Flash non **5.76 s** vs max **52.08 s** (~**9×**); Pro non **9.06 s** vs max **73.78 s** (~**8×**); reasoning ~**88–90%** of E2E at max.
- Decode: Flash **111** vs Pro **66** tok/s non-think (**1.68×**); Fireworks OR **74** vs **51** (**1.45×**). Active-param 3.8× ≠ measured ~1.7×.
- Think-high vs non: Flash ~**3×**, Pro ~**4.3×**; high vs max ~**1/3** Flash, ~**1/1.9** Pro.
- Together Pro peak **326** tok/s (~**4.8×** 1P) — ceiling, not plan input. OR mid-tier: Pro ~**45–55**, Flash ~**70–75** tps.
- Corpus sketch @ L≈20 s Pro think-on: Flash same-think → L≈**12 s** (~0.59×); Pro max→non-think ~**0.12×** on think-dominated calls (quality-gated). Neither alone clears ≤600 s without N cuts.

## Architecture implication
Model Non-think as fewer output tokens, not faster decode kernels. Prefer high over max if quality holds before full Non-think. Cap self-host optimism at DeepSeek-1P / OR mid-tier; use ratios on alliance-pod arithmetic (`L_Flash ≈ L_Pro/1.7` same think).

## Reject-or-A-B
- **Use as priors:** think-budget >> model-tier for `L_eff`; Flash ~1.7× decode; Non-think ~1/8–1/9 of max wall.
- **Reject:** Together 326 / Fireworks 175 as alliance-pod achievable; scaling wall by 49/13 activate ratio.
- **A/B on pod:** measure Pro non/high/max on dissect mix to invalidate hosted absolutes.

## Links
- Source: `05z-web-hosted-latency.md`
- Related: `05b-web-flash-vs-pro.md`, `05q-web-official-think-off.md`, `00-baseline.md`
- https://artificialanalysis.ai/providers/deepseek
- https://openrouter.ai/deepseek/deepseek-v4-pro
- https://openrouter.ai/deepseek/deepseek-v4-flash
