# Card 05c — `reasoning_effort` / thinking knobs vs decode latency

**Source report:** `05c-web-reasoning-effort.md`

## Bottom line

Only **Non-think** is a first-class short-decode dial among effort strings people confuse with low/medium/high. On DSV4, `reasoning_effort="low"` maps to **high** (no-op toward shorter CoT). Max lengthens decode (system prefix + longest CoT). Prefer explicit vLLM `chat_template_kwargs.thinking=false` or top-level `reasoning_effort="none"`.

## Numbers

- Official modes: Non-think / Think High / Think Max (no native `low`).
- Hosted classifier-shaped non-stream (~2.9K input): default thinking **31.8 s** → disabled **2.7 s** (~12×); heavy-reasoning thinking-on **86.3 s** / 5638 out-tok (DeepSeek-V3 #1464).
- HF Pro cliffs Non→High: GPQA 72.9→89.1; LiveCodeBench 56.8→89.8; HLE 7.7→34.5. High→Max gains smaller.
- Think Max needs context ≥384K; injects “absolute maximum” system prefix.
- vLLM mapping: `low`/`medium`/`minimal` → high; `xhigh` → max; `none` → disable thinking (PR #40982).

## Architecture implication

Wire request-level Non-think for unit-check JSON on alliance-pod; do not rely on omit-kwargs if defaults think. Pair with tight `max_tokens` / verdict-first. Hosted wire (`thinking.type`) ≠ vLLM `chat_template_kwargs`. Optional: `thinking_token_budget` only if live pod honors it.

## Reject-or-A-B

**A/B Non-think** for quality. **Reject as levers:** `reasoning_effort="low"` (trap), `"max"` for unit checks. Quality A/B still required despite ~12× hosted classifier win.

## Links

- https://huggingface.co/deepseek-ai/DeepSeek-V4-Flash (mode table)
- https://recipes.vllm.ai/deepseek-ai/DeepSeek-V4-Flash
- https://github.com/vllm-project/vllm/pull/40982
- https://github.com/deepseek-ai/DeepSeek-V3/issues/1464
- https://docs.vllm.ai/en/stable/features/reasoning_outputs/
