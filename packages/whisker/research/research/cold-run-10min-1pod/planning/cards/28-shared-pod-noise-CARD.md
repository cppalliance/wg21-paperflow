# CARD: Shared pod noise (alliance-pod multi-tenant)

## Bottom line (3 sentences max)
`alliance-pod` is a dedicated RunPod instance but **Alliance-shared** (no tenant slot isolation); API key authenticates, does not reserve GPU slots. Cold-run variance risk is **HIGH**: wall jitter from foreign occupancy plus ≥**25%** MoE flip floor at c=32. Measurement confounder, not a primary −800 s lever — instrument `/metrics`, prefer off-hours, never treat single A/B as ground truth without matched occupancy.

## Numbers that matter
- Sustained fleet window: ~**50 min** at c=**32** over **16** slots (~2284 calls)
- Modeled half-slot theft (8/16 external): ~**2×** wall on that pod’s work
- Baseline identical-rerun flip: **≥25%** at c=32 (before shared-neighbor effects)
- `VLLM_BATCH_INVARIANT=1`: mitigates semantic variance, ~**50%** throughput — rejected for speed
- Downgrade to MED only if quiet window + double-A `flip_AA ≤ 5%` (neither evidenced)

## Architecture implication
Accept advisory-lane variance budget on alliance-pod; do not enable BI on the speed path. Reject levers that compound neighbor diversity (in-paper parallel, c>32, seqs=32). For A/B claims, log `num_requests_running/waiting` and match external load across runs.

## Cite / do not re-open
- Treating API key or separate twin URL as exclusive slot isolation on alliance-pod
- Enabling `VLLM_BATCH_INVARIANT` to “fix” 10-min variance
- Attributing wall/verdict swings to client levers without occupancy-matched double-A
- Raising seqs/c to absorb shared load

## Links to related reports
- `research/cold-run-10min-1pod/28-shared-pod-noise.md` (this source)
- `00-baseline.md`, `05v-web-batch-invariant.md`, `MODELS.md`, `SERVICES.toml` (alliance-pod)
- Prior: `tapetum-llm-speedup/140-litellm-router-loadbalancing.md`, `cold-run-10min/51-determinism-risk-matrix.md`
