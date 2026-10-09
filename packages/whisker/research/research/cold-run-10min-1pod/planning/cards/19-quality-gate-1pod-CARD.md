# CARD: Quality gate protocol — 1-pod AGGRESSIVE

## Bottom line (3 sentences max)
Ship AGGRESSIVE (deterministic metadata + dense unit offload) only via A/A noise floor at MODERATE single-pod baseline, one bundled `--force` B, and three post-hoc gates. Quality pass does **not** imply ≤600 s (realistic B ~**715 s**). Minimum validation wall: **~0.8 h** (cached A2) or **~1.2 h** (fresh A/A).

## Numbers that matter
- Config A: MODERATE single-pod **~1366–1493 s (~23–25 min)** per run — not v10 3003 s
- Config B bundle: **~585–715 s** central; wall_B ≤**620 s** upgrades 10-min claim; >**720 s** = quality OK, 10 min missed
- Equivalence: `flip_AB ≤ flip_AA + margin` on four-component vector; margin `max(0.02, 1.96×sqrt(...))`
- Dev-replay: `recall_B ≥ recall_A − 0.05` on 9 PRs / 29 groups; holdout 48 anchors non-regressing
- Protocol totals: fresh A/A+B **71–76 min**; cached A2+B **46–51 min**; isolated debug path **~105–110 min**

## Architecture implication
A runs = MODERATE single-pod; B = A + det. metadata + dense units (scoped) + lane bump; router optional co-bundle. Dense ≠ second V4-Pro; monolith/esc/oversize stay on MoE. Do not require exact 0% flip or persona-23 strict 381/381 as primary bar — use equivalence + flip_AA margin. Wall is secondary success metric, not tier-1 pass. Suspect dense false-clear first if dev-replay fails.

## Cite / do not re-open
- Measuring A/A at v10 ~50 min (confounds already-shipped MODERATE cuts)
- Separate B runs per lever when shipping the minimum-wall bundle
- Blocking ship on wall alone when three quality tiers pass
- Claiming ≤600 s without measured B1 ≤620 s
- Twin/dual-pod revival in this protocol

## Links to related reports
- `research/cold-run-10min-1pod/19-quality-gate-1pod.md` (this source)
- `00-baseline.md`, `10-impl-status-1pod.md`, `12-dense-offload-architecture.md`, `13-deterministic-metadata.md`
- Prior: `cold-run-10min/25-quality-gate-protocol.md`, `tapetum-llm-speedup/47-quality-equivalence.md`
