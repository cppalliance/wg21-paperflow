# CARD: Implementation status — single-pod path (no twin)

## Bottom line (3 sentences max)
v11 in the working tree already lands the largest single-pod call cut (metadata short-circuit); expected cold wall at HEAD is **~1260–1493 s (~21–25 min)**, not 3003 s. MODERATE software alone cannot hit 10 min on one pod. Closing ≤600 s needs dense offload plus AGGRESSIVE call/schema cuts, not a twin.

## Numbers that matter
- v11 metadata short-circuit: **−1059 to −1341 s** (44.6% fleet calls); `_LANE_VERSION = 11`
- Gap after v11 MODERATE: **~660–893 s** vs 600 s
- Stack @ S=16: v11 only ~**1366 s** ❌ → +verdict-first ~**1240** ❌ → +router ~**1170** ❌ → +det. metadata ~**920** ❌ → +dense ~**585–715** ⚠️ hairline
- Tier-1 remaining: dense offload **−850 to −1200 s**; deterministic metadata **−~471 s**; verdict-first **−124 to −360 s**; router combo_safe **−~80 to −130 s**
- Partial/unrealized: text-lane HMAC **−100 to −200 s**; LJF+to_thread already **~−30 to −90 s** class

## Architecture implication
Execution order: measure post-v11 cold → finish HMAC/md-first → instrument `call_timings[]` → MODERATE verdict-first → AGGRESSIVE payload scoping → dense routing → deterministic metadata → router. Dual-pod shard / twin health probes explicitly excluded. Dense offload is the only remaining code lever with enough headroom; requires Tier-1 quality validation, not a flag flip.

## Cite / do not re-open
- Dual-pod as the close-the-gap answer
- Claiming MODERATE alone hits 600 s
- Shipping dense without 381/381 fused-verdict parity
- Treating post-v11 arithmetic as measured fact (no fresh cold run yet)

## Links to related reports
- `research/cold-run-10min-1pod/10-impl-status-1pod.md` (this source)
- `00-baseline.md`, `11-wall-arithmetic-1pod.md`, `12-dense-offload-architecture.md`
- `13-deterministic-metadata.md`, `14-router-quota-1pod.md`, `15-verdict-first-design.md`
- Prior: `research/cold-run-10min/10-impl-status-auditor.md`, `22-path-a-b-10min.md`
