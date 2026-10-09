# CARD: Dual-pod dependency rewrite (1-pod substitutes)

## Bottom line (3 sentences max)
Prior Path A hit ~**596 s** only via MODERATE + **dual-pod S=32**; twin is forbidden. The 1-pod substitute for that multiplier is **heterogeneous dense offload** (`wall = max(T_dense, T_moe)`), not a second V4-Pro. MoE-only software cannot hit ≤600 s at the quality floor; Package C heterogeneous is the rewrite of Path A.

## Numbers that matter
- Dual-pod compute halving: ~**887 s** (N_rem=1419 at /32 vs /16)
- One MoE MODERATE: ~**1366–1493 s**; CONSERVATIVE dual still ~**945 s**
- Dense hetero central: ~**511 s** optimistic; ~**620–715 s** with friction / metadata on MoE
- Offload split: ~**1879** dense / ~**428** MoE; dense Sem **32–48**, MoE Sem **16**
- Forbidden substitutes: twin revive, seqs=32 (**+57%** wall), c>32, wider EP as S gain

## Architecture implication
Replace Day-3 twin+`--shard-pods` with call-class service router (units/metadata→dense, monolith→MoE), dual-endpoint liveness, and fingerprint of routing profile. Keep all non-twin Path A software levers on one pod. Quality gate becomes **381/381 dense vs MoE parity**, not cross-replica verdict identity.

## Cite / do not re-open
- Twin / second V4-Pro / manual two-process MoE split
- `--max-num-seqs 32`, client c>32, LiteLLM as shard vehicle
- MODERATE-alone ≤600 s on one MoE pod
- Wider EP / multi-node as substitute for doubled S_eff

## Links to related reports
- `research/cold-run-10min-1pod/27-dualpod-dependency-rewrite.md` (this source)
- `12-dense-offload-architecture.md`, `18-packages-1pod.md`, `17-physics-floor-skeptic.md`, `26-dense-pod-liveness.md`
- Prior: `cold-run-10min/SYNTHESIS.md`, `22-path-a-b-10min.md`
