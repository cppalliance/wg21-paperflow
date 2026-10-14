# Card 05d — Single-node 8×H200 serving @ max-num-seqs=16

**Source report:** `05d-web-single-node-serving.md`

## Bottom line

Hopper V4-Pro recipe is already a max-num-seqs=16 short-batch profile. Maximize output tok/s via MBT 16384, decode CUDA graphs, EP topology, MTP k=1 (A/B), and optional DeepEP/DBO — **not** by raising slots. Blind MTP k=2 on short JSON can regress.

## Numbers

- Recipe hopper pins: `--max-num-seqs 16`, `--max-num-batched-tokens 16384`, `gpu-memory-utilization 0.95`, `max-model-len 200000`, `FULL_DECODE_ONLY` (YAML) / `FULL_AND_PIECEWISE` (strategy override).
- H20 8-node forum (recipes#390): without MTP ≈**40 TPS**; MTP=1 ≈**60–70 TPS**.
- GB300 short-OSL (OSL≈64): MTP can be **worse than off**.
- Wide-EP 2.2k tok/s/H200 is multi-node; not a single-pod S=16 claim.
- Prefill chunk planning PR: ~4% E2E; prefer current image over exotic flags.
- Cold start compile + cudagraph capture: ~10–15 min expected.

## Architecture implication

Top ops rank for short JSON @ S=16: (1) MTP k=1, (2) decode CUDA graphs, (3) MBT 16384, (4) EP + TEP/DEP, (5) DeepEP low_latency + DBO if DEP+DeepEP and thresholds clear. Client Non-think keeps OSL in 50–300 band. Anti-levers: seqs>16, blind k=2, `--enforce-eager`, expecting multi-node TPS.

## Reject-or-A-B

**A/B MTP k=1** (accept rate under c=16). **Reject:** raising `--max-num-seqs`; banking recipe k=2 for short JSON; counting wide-EP 2.2k as ours. DBO: measure before banking (may sit under threshold at S=16 short gens).

## Links

- https://github.com/vllm-project/recipes/blob/main/models/deepseek-ai/DeepSeek-V4-Pro.yaml
- https://recipes.vllm.ai/deepseek-ai/DeepSeek-V4-Pro
- https://github.com/vllm-project/recipes/issues/390
- https://github.com/vllm-project/vllm/issues/41483
- https://docs.vllm.ai/en/latest/design/dbo/
