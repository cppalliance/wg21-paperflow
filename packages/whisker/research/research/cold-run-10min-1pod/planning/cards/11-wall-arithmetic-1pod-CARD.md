# CARD: Wall arithmetic — single pod (twin forbidden)

## Bottom line (3 sentences max)
≤600 s is **not** reachable on one pod at planning-grade confidence. Central full-stack estimate is **~680 s** (148 pessimistic AGGRESSIVE); honest floor **~680–715 s** with friction. Bare optimistic **~585 s** needs unvalidated AGGRESSIVE gates and zero friction — not a shippable target.

## Numbers that matter
- Model: `wall = (N_rem × L_eff) / 16 + T + C − L_abs`; **S_eff = 16** forever
- Baseline: N₀=**2284**, L≈**20 s**, wall=**3003 s**; T+C **148→28 s** after LJF+to_thread
- MODERATE: compute on 1419 calls = **1774 s** alone; walls **~906–1493 s** ❌
- AGGRESSIVE: bare **585 s** ⚠️; +friction **715 s** ❌; 148 planning **680 s** ❌; +friction **910 s** ❌
- Twin removal costs **~887 s** on MODERATE remainder; server-only net unique **−120 to −200 s** (does not close 800–900 s gap)

## Architecture implication
Stack N cuts first, then L_abs on survivors only, then L_eff (dense/MTP) on remaining mix — never silent S=32. Dense offload is necessary but not sufficient; planning-grade path lands ~11–12 min (AGGRESSIVE validated) or ~23 min (MODERATE). Flip to “reachable” only if instrumented AGGRESSIVE cold run measures **≤620 s**.

## Cite / do not re-open
- Naive stacked table without friction/overlap (~164–339 s fantasy)
- S=32 or twin shard as multipliers
- Summing full-fleet prefix/verdict on already-eliminated calls
- Treating bare 585 s as planning-grade yes

## Links to related reports
- `research/cold-run-10min-1pod/11-wall-arithmetic-1pod.md` (this source)
- `00-baseline.md`, `18-packages-1pod.md`, `17-physics-floor-skeptic.md`
- Prior: `research/cold-run-10min/{11-wall-arithmetic,22-path-a-b-10min}.md`, `tapetum-llm-speedup/48-combined-lever-modeler.md`
