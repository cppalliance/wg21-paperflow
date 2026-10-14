# CARD: Heterogeneous wall model — MoE S=16 + dense S=32–48

## Bottom line (3 sentences max)
Correct layout is parallel pods with **`wall = max(T_moe, T_dense)`**, not sum. At **70% fleet calls offloaded @ 2×**, central wall is **~856 s (~14 min)**, MoE-bound, and misses ≤600 s. Full unit+metadata offload (~82.6%) or MODERATE + 70% on remainder can reach **~511–533 s** (fragile; quality-blocked).

## Numbers that matter
- Model: `T_pod = Σ(N×L)/S`; `wall = max(T_moe, T_dense) + T_client`; S_moe=**16**, S_dense=**32–48**
- 70% @ 2×: N_dense=**1599**, N_moe=**685**, L_dense=**10 s**, L_moe=**20 s** → T_dense~**333**, T_moe~**856** → wall **856 s**
- S_dense 32–48: **no wall change** at 70% (always MoE-bound)
- Full units+metadata @ 2× (scoped): wall **~511 s**; 70% @ 2× after MODERATE (N_rem=1419): **~533 s**
- Selective “70% of zero-defect units only”: wall **~1534 s** — reject as wall lever

## Architecture implication
Offloading 70% does not subtract 70% of baseline wall; the slow MoE leg sets fleet time. Prerequisites for 2×: payload scoping + FP8 KV — without them dense reverts to L≈20/S≤16 (negative EV). Prefer ~82.6% offload (units+metadata) over 70% alone; raise MoE cuts (short-circuit, det. metadata, prefix on monolith) rather than dense slot tuning when MoE-bound.

## Cite / do not re-open
- Summing T_moe + T_dense as fleet wall
- Reporting 70%×2× as ~42% wall cut (~1050 s fantasy vs correct ~856 s)
- Tuning S_dense expecting wall move at 70% offload
- Confusing “70% zero-defect units” with “70% fleet offload”

## Links to related reports
- `research/cold-run-10min-1pod/20-heterogeneous-wall.md` (this source)
- `00-baseline.md`, `12-dense-offload-architecture.md`, `11-wall-arithmetic-1pod.md`
- Prior: `cold-run-10min/16-dense-judge-candidates.md`, `tapetum-llm-speedup/105-vllm-dense-judge-throughput.md`
