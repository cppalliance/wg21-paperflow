# ADR-001: No twin V4-Pro pod

## Status

Accepted

## Context

The cold-run ≤10 min program previously treated dual-pod sharding (two DeepSeek-V4-Pro replicas, effective S: 16→32) as the clean arithmetic path to ~596 s central wall under a MODERATE software package. That plan lived in `research/cold-run-10min/` and required a live twin endpoint (`h200x8-deepseek-v4-pro`) plus a shard / dual-lane client.

On 2026-07-24 the operator closed that path: no budget or authority to revive a second V4-Pro replica. All execution planning must assume only `alliance-pod` (DeepSeek-V4-Pro, `--max-num-seqs 16`, client c=32). The twin is also infra-dead today (HTTP 404 on health/models probes), so even a temporary "use it if it comes back" dependency would strand the program.

Without a twin, single-pod MODERATE lands ~1366–1493 s (~23–25 min). The missing ~887 s is almost entirely parallel MoE slot capacity. Raising `--max-num-seqs` to 32 on one pod is not a substitute (see ADR-002: measured +57% wall). The only remaining ≤10 min candidate is heterogeneous offload to an already-running dense Alliance endpoint (`wall = max(T_moe, T_dense)`), not a second V4-Pro.

## Decision

Forbid twin V4-Pro as an executable lever for this program.

1. Do not revive, require, or plan around `h200x8-deepseek-v4-pro` (or any second identical DeepSeek-V4-Pro replica).
2. Treat `research/cold-run-10min/` dual-pod recommendations as superseded context only; cite them as blocked, never as the ship path.
3. Keep `S_eff = 16` on the MoE pod. Recover the lost dual-pod multiplier via call elimination, decode shrink, and dense-judge offload to existing non-V4-Pro Alliance endpoints (e.g. `h200-qwen3-32b`), with quality gates.
4. If dense endpoints stay down and twin stays forbidden, publish an honest SLA of ~15–20 min after the MoE package; stop treating ≤10 min as MoE-only physics.

## Consequences

**Positive**

- Planning stays inside real budget/authority; no false dependency on a 404 twin.
- Forces the correct substitute architecture: dense offload + `max(T_moe, T_dense)`, not silent S=32.
- Clears dual-pod CLI / LiteLLM shard / two-process PID split from the critical path.

**Negative / cost**

- MoE-only MODERATE cannot hit ≤600 s at the quality floor (physics floor: front-end alone ~948 s).
- Heterogeneous Package C is blocked until Alliance restarts at least one dense endpoint (all four dense `SERVICES.toml` services returned 404 as of 2026-07-24 probe).
- Dual-pod era central ~596 s is not reclaimable without either twin revival (out of scope) or validated dense offload + scoping.

**Invariants**

- Second pod means second identical V4-Pro. Dense offload is a different model on a sunk Alliance endpoint and is in scope.
- No plan may use silent S=32 or twin shard in wall arithmetic.

## Evidence

| Claim | Source |
|-------|--------|
| Operator ban: no second DeepSeek pod; only `alliance-pod` | `research/cold-run-10min-1pod/00-baseline.md` |
| Twin / S=32 / c>32 forbidden in reject ledger | `research/cold-run-10min-1pod/SYNTHESIS.md` |
| Prior dual-pod path ~596 s central; this corpus exists because that path is forbidden | `research/cold-run-10min-1pod/00-baseline.md`, `research/cold-run-10min/SYNTHESIS.md` |
| Twin `h200x8-deepseek-v4-pro` 404; `alliance-pod` live | `research/cold-run-10min/15-dual-pod-liveness.md` |
| Twin removal costs ~887 s; MODERATE single-pod ~1366–1493 s | `research/cold-run-10min-1pod/11-wall-arithmetic-1pod.md`, `research/cold-run-10min-1pod/18-packages-1pod.md` |
| Dual-pod dependencies rewritten to dense hetero offload | `research/cold-run-10min-1pod/27-dualpod-dependency-rewrite.md` |
| ≤10 min MoE-only below physics floor; only path is `max(T_moe, T_dense)` | `research/cold-run-10min-1pod/17-physics-floor-skeptic.md`, `research/cold-run-10min-1pod/SYNTHESIS.md` |
| Dense pods also 404; Package C infra-blocked | `research/cold-run-10min-1pod/26-dense-pod-liveness.md`, `research/cold-run-10min-1pod/SYNTHESIS.md` |
| Planning constraints C1 (twin forbidden) | `research/cold-run-10min-1pod/PLANNING-HANDOFF.md` |
