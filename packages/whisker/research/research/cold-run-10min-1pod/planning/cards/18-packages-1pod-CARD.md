# CARD: CONSERVATIVE / MODERATE / AGGRESSIVE packages (1 pod)

## Bottom line (3 sentences max)
None of the three packages **reliably** hits ≤600 s on one pod @ S=16. MODERATE central **~1366 s (~23 min)** is the honest quality-bounded single-pod floor after v11. AGGRESSIVE bare **585 s** touches the gate; with friction plan **715–910 s** — hairline maybe, not a guarantee.

## Numbers that matter
- BASELINE: N=2284, L=20, wall **3003 s** (~48–50 min)
- CONSERVATIVE: central **~2163 s** (~36 min) ❌ — dual-pod excluded from this package
- MODERATE: N_rem=1419, compute **1774 s**, wall **1366** (48) / **1493** (148) ❌; ~54% reduction
- AGGRESSIVE: N_rem=1229, L_eff=**11.74 s**, bare **585** ⚠️ / +friction **715** ❌ / 148+friction **910** ❌
- Twin gap vs dual-pod MODERATE (~596 s): **+887 s** from S 32→16 on N_rem=1419

## Architecture implication
CONSERVATIVE = prefix/HMAC/ops/LJF only (no verdict semantics). MODERATE adds short-circuit + escalation dedupe + verdict-first + survivor prefix. AGGRESSIVE adds router + dense offload (+ optional det. metadata); all quality gates mandatory before ship. Dense attacks **L**, not **S**; heterogeneous layout still MoE-bound without enough N cuts. Prefer shipping MODERATE over waiting for unvalidated 585 s.

## Cite / do not re-open
- Dual-pod shard inside CONSERVATIVE/MODERATE packages
- Shipping AGGRESSIVE on bare 585 without friction + 381/381 parity
- Rejecting MODERATE because 10 min is impossible
- Silent S=32 or c>32

## Links to related reports
- `research/cold-run-10min-1pod/18-packages-1pod.md` (this source)
- `00-baseline.md`, `11-wall-arithmetic-1pod.md`, `12-dense-offload-architecture.md`, `19-quality-gate-1pod.md`
- Prior: `cold-run-10min/SYNTHESIS.md` §3, `22-path-a-b-10min.md`
