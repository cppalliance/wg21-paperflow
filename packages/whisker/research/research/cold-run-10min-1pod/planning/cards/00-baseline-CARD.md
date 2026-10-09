# CARD: Baseline — cold-run ≤10 min on ONE pod (no twin)

## Bottom line (3 sentences max)
Only `alliance-pod` (DeepSeek-V4-Pro, S=16, client c=32) is in scope; a second V4-Pro twin is forbidden. Cold fleet goal is 381 papers ≤600 s with fail-closed quality-stability. Prior dual-pod ~596 s path is out of scope unless framed as blocked.

## Numbers that matter
- Cold wall (v10): **3003 s**; calls ~**2284** (~6/paper); per-call ~**20 s**; warm **64.8 s**
- Server slots / client c: **16 / 32** (S_eff fixed at 16; never silent S=32)
- v11 short-circuit (working tree): **~−1059 to −1341 s** of fusion-dead units
- Single-pod MODERATE (prior math): **~1366–1493 s (~23–25 min)** — misses 10 min
- Gap to 600 s after MODERATE: **~800–900 s** still needed on one pod

## Architecture implication
Cut **N** (calls), **L** (decode/prefill), or client waste on one MoE pod. Dense offload to already-running Alliance dense endpoints is allowed and is **not** a second V4-Pro. Forbidden: twin pod, `--max-num-seqs` 32, client c>32, drop verification / fail-open, cloud LLM judges.

## Cite / do not re-open
- Twin / dual-pod as the answer (cite prior corpora as blocked)
- Raising seqs to 32 or client c>32
- Fail-open or cloud judges
- Arithmetic with S≠16

## Links to related reports
- `research/cold-run-10min-1pod/00-baseline.md` (this source)
- `research/tapetum-llm-speedup/SYNTHESIS.md`, `research/cold-run-10min/SYNTHESIS.md` (prior dual-pod proof; do not rediscover)
- Downstream cards: `10-impl-status-1pod`, `11-wall-arithmetic-1pod`, `18-packages-1pod`
