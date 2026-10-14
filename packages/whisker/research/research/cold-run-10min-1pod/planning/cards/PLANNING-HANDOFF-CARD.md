# CARD: PLANNING HANDOFF — entry for architecture planner

## Bottom line (3 sentences max)
Single entry point for a downstream planning agent: cut bare full-fleet cold (**381** papers, ~**2284** calls) from ~**2883–3003 s** to **≤600 s** under fused-verdict quality, with **no second V4-Pro** and MoE **S_eff=16** forever. MoE-only cannot hit 10 min at quality; choose Option A (~12–23 min shippable), Option B (heterogeneous ≤10 min design), or Option C (reset SLA to ~15–20 min). Dense restart is a hard prereq for Option B — all dense endpoints **404** as of 2026-07-24.

## Numbers that matter
- Floors: front-end **948 s**; MODERATE survivors ~**1366–1493 s**; MoE AGGRESSIVE realistic ~**680–715 s**
- Heterogeneous candidate: **~511 s** MoE-bound if scoping + 2× dense decode + parity
- Warm incremental: **~64.8 s** (irrelevant after `_LANE_VERSION` bump)
- Quality validation wall: ~**0.8–1.2 h** (excludes implementation); instrumented B ≤**620 s** to claim 10 min
- Det-metadata staging: HTML-first ~**251 s**, then fleet ~**471 s**

## Architecture implication
Planner must answer SLA (keep 10 min vs reset), dense restart yes/no/when, and phase tickets P0–P8 (remeasure v11 → ship short-circuit → det-metadata → verdict-first/router → server Tier-1 → dense restart → scoping/router → cascade+gate → distill if needed). Produce Option A+B/C plan with infra ask, quality gates from `19`, and explicit non-goals; cite report IDs for every major claim.

## Cite / do not re-open
- Second V4-Pro / `--max-num-seqs 32` / c>32
- Skip monolith; default `--det-skip`; P/D on one node; BI mode
- Bank MTP; Flash without deploy; Gemma-4 as primary unit judge; guided_grammar
- Ideal-verify deletion as 10-min lever; re-forage dual-pod plan as executable

## Links to related reports
- `research/cold-run-10min-1pod/PLANNING-HANDOFF.md` (this source)
- `SYNTHESIS.md`, `FILE-MANIFEST.md`, `planning/` ADRs, `00-baseline.md`, `19-quality-gate-1pod.md`
- Load-bearing: `12`, `17`, `26`, `28`; prior dual-pod era `research/cold-run-10min/` (context only)
