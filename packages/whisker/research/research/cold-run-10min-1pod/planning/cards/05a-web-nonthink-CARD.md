# Card 05a — Non-think / Instant vs Thinking (JSON judge)

**Source report:** `05a-web-nonthink.md`  
**Verdict in source:** usable-with-conditions

## Bottom line

Non-think is the real single-pod decode dial for structured unit checks, but blanket force is a quality cliff on hard adjudication. Docs and community support JSON-with-thinking-off for classification/extraction, not STEM-hard judging. Default policy: escalate-shaped routing — Non-think on cheap majority, Think High on hard/escalate — only after holdout. Blanket force = no.

## Numbers

- HF V4-Pro Non-Think → High cliffs: GPQA 72.9→89.1; LiveCodeBench 56.8→89.8; HLE 7.7→34.5; HMMT 31.7→94.0; MMLU-Pro only 82.9→87.1.
- Third-party token bands: ~200–500 (Non-think) vs ~2k–8k (High) vs ~8k–50k (Max).
- Sketch: N_u=800, L_u=20, k=4 → Δwall ≈ 800×15/16 ≈ **750 s** (only if quality A/B holds; measure on alliance-pod).
- Think Max: never for cold unit-check fleet.

## Architecture implication

Moves **L**, not S. Prefer Pro Non-think before Flash. Schema-bound / local-evidence / verdict-first units → Non-think; code-semantics / multi-hop / rescue → keep Think High. Thinking-on hurts structured reliability on self-host (vLLM #41132 JSON in `reasoning`; hosted #1376 rejects forced `tool_choice`).

## Reject-or-A-B

**A/B, not blanket.** Holdout: Pro Non-think vs High — defect recall / flip rate within same-model noise; fail-closed not worse. **Reject:** Think Max on cold units; global force without A/B; twin/S=32 fantasies.

## Links

- https://api-docs.deepseek.com/guides/thinking_mode/
- https://api-docs.deepseek.com/guides/json_mode/
- https://huggingface.co/deepseek-ai/DeepSeek-V4-Pro
- https://github.com/vllm-project/vllm/issues/41132
- Prior: `research/cold-run-10min/59-deepseek-v4-release.md`
