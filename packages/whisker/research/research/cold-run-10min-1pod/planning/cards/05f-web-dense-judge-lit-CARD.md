# Card 05f — Dense ~27–32B as judge vs MoE teachers

**Source report:** `05f-web-dense-judge-lit.md`  
**Verdict in source:** usable-with-conditions

## Bottom line

Best dense candidate class for unit-check offload from DeepSeek-V4-Pro: **Qwen3 dense 27–32B** (primary `h200-qwen3-32b`; latency pilot `b300-qwen36-27b`). **Not Gemma-4-31B** (structured JSON/grammar collapse). No public study measures these three vs V4-Pro on our UnitCheck schema; A/B mandatory. Class label: `qwen3-dense-27-32b`.

## Numbers

- Judge's Verdict: Qwen3-30B-A3B κ≈0.780 Tier 1; gemma-3-27b-it κ=0.812 (Gemma-3 ≠ Gemma-4; A3B ≠ dense 32B).
- Qwen-3-Nemotron-32B-Reward JudgeBench overall **72.3** vs Llama-3.3-Nemotron-70B **73.7**; Code **83.3**.
- Cascaded Selective Evaluation: ≥80% human agreement at 77.6% coverage, **0.215×** GPT-4 cost (−78.5%).
- SLMJury ≤14B ~89.5% closed-ended @ B=10 (not V4-Pro parity proof).
- AA: Qwen3-32B ~91–94 tok/s vs large MoE sibling ~61–68 tok/s (API medians).
- Neysa: Qwen3-32B FP8 @ c=100 ≈ **~6099** tok/s agg; 235B MoE latency walls under concurrency.
- Qwen3.6-27B vs MoE 35B-A3B: SWE 77.2 vs 73.4; MoE sibling ~3–4× faster (active params).
- Gemma-4 JSON: ~0–1/10 valid under schema/grammar in Ollama/community; vLLM needs workarounds.
- Fleet sketch: offload ~1510 units → `wall ≈ max(T_dense, T_moe)`; prior hetero ~620–710 s MoE-bound after offload alone.

## Architecture implication

Dense-first + MoE escalate (not replace V4-Pro forever). Live Alliance services in scope when up. Quality gate: 381/381 fused verdict parity before `_LANE_VERSION` bump. Payload scoping required for dense S>16.

## Reject-or-A-B

**A/B gated adopt** for Qwen3-32B (primary). **Reject as primary:** Gemma-4-31B for structured unit path. Reopen Gemma only if ≥99% valid JSON + 381/381 parity on our stack. Abort speed claim if `L_dense ≥ L_moe` at 12k/256 shape.

## Links

- https://arxiv.org/abs/2510.09738 (Judge's Verdict)
- https://arxiv.org/abs/2407.18370
- https://huggingface.co/nvidia/Qwen-3-Nemotron-32B-Reward
- https://github.com/ollama/ollama/issues/15502
- Sibling: `12-dense-offload-architecture.md`
