# CARD: Physics floor skeptic — one pod, S=16

## Bottom line (3 sentences max)
≤600 s cold on one `alliance-pod` is below the quality-preserving physics floor. Irreducible front-end alone is **~16 min**; quality-preserving MODERATE minimum is **~23 min**. Loaded decode alone exceeds 10 min before prefill and queue; solo 70 tok/s under load is a fantasy.

## Numbers that matter
- Front-end only (758 monolith+metadata): **948 s (~15.8 min)** > 600 s before any unit runs
- Quality-preserving N_irreducible: **~1419** → wall **1366–1493 s (~22.8–24.9 min)**
- Loaded decode @ **~19 tok/s/user** on ~204k output tok: **672 s (~11.2 min)** decode-only
- Solo 70 tok/s fantasy: **183 s** — not operative under S=16 continuous batching (understates ~3.7×)
- Gap to 600 s on MODERATE: **766–893 s** ≈ forbidden twin’s **~887 s** compute halving

## Architecture implication
Treat **~23 min** as the honest one-pod physics floor after quality-bounded cuts; **~16 min** as absolute call-graph floor (zero units). 10 min requires a second S=16 replica, a forbidden concurrency regression, or a different model class (dense offload — not one V4 pod). Do not abandon MODERATE (~23 min) because 10 min is impossible — short-circuit still removes verified waste.

## Cite / do not re-open
- Planning from solo 70 tok/s under fleet load
- S=16→32 as a speed dial (+57% wall measured)
- Claiming decode/MTP alone closes a ~766 s gap
- Dropping monolith/metadata to hit wall (quality floor)

## Links to related reports
- `research/cold-run-10min-1pod/17-physics-floor-skeptic.md` (this source)
- `00-baseline.md`, `11-wall-arithmetic-1pod.md`, `18-packages-1pod.md`
- Prior: `cold-run-10min/22-path-a-b-10min.md`, `tapetum-llm-speedup/52-h200-capacity-math.md`
