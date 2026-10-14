# Card 05b — DeepSeek-V4-Flash vs V4-Pro (unit judge)

**Source report:** `05b-web-flash-vs-pro.md`

## Bottom line

Flash is a credible **fast unit-check** candidate (short structured / coding/doc checks) if served and A/B’d against Pro. It is **not** a drop-in quality equal for hard agentic / knowledge-heavy cases, and it is **not deployed** on Alliance today (`SERVICES.toml` = Pro only). Flash = yes as unit-judge candidate, not as full Pro replacement.

## Numbers

- Active params: Flash **13B** vs Pro **49B** (~3.8× less activate).
- Hosted decode blogs: Flash ~120–160 tok/s Non-think vs Pro ~60–80.
- LiveCodeBench Max: Flash 91.6 vs Pro 93.5; SWE Verified Max: 79.0 vs 80.6; Terminal Bench Max gap ~11 pts (56.9 vs 67.9).
- SimpleQA-Verified Max: Flash 34.1 vs Pro 57.9 (−23.8). MRCR/CorpusQA closer (−4.8 / −1.5).
- IFBench (AA): Flash 79.2% vs Pro 76.5% — Flash can win instruction-following while losing TerminalBench Hard.
- Hallucination-when-wrong ≈ 96% Flash / 94% Pro (both weak abstention).
- vLLM GPU floor: Flash 4×B200 DP4+EP; Pro 8×B200 DP8+EP.

## Architecture implication

Flash helps **L_eff** on unit checks, not S_eff. Paths: (1) swap alliance-pod → Flash (lose Pro ceiling); (2) new Flash endpoint (ops/budget, not twin Pro); (3) keep Pro and use dense offload (`h200-qwen3-32b`, etc.). Prefer Flash High/Max + escalate hard units. Without deployment, wall savings = **zero**.

## Reject-or-A-B

**A/B after deploy.** Gate: Flash High ≥99% agreement with Pro High on fail-closed units; retry rate not up. **Reject for now as plan assumption** — not live. Do not bet ≤10 min on Flash Non-think without A/B.

## Links

- https://huggingface.co/deepseek-ai/DeepSeek-V4-Flash
- https://vllm.ai/blog/2026-04-24-deepseek-v4
- https://recipes.vllm.ai/deepseek-ai/DeepSeek-V4-Flash
- `SERVICES.toml`; `research/cold-run-10min/40-vllm-deepseek-recipe.md`
