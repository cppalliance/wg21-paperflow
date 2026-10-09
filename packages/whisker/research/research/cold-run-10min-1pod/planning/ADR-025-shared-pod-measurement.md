# ADR-025: Shared-pod measurement protocol

## Status

Proposed — mandatory for all cold A/B claims

## Date

2026-07-24

## Context

`alliance-pod` is an Alliance-shared RunPod instance (same model as the forbidden twin, different scheduler). Bearer auth does not reserve GPU slots. Cold fleets at client c=32 overfill `--max-num-seqs 16` for tens of minutes; foreign traffic can steal slots.

Modeled half-occupancy (8/16 external) ≈ **2× wall** on the tapetum shard. Verdict floor is already ≥25% identical-rerun flip at c=32 from MoE batch composition; neighbors add an uncontrolled axis. `VLLM_BATCH_INVARIANT=1` would mitigate flips at ~50% throughput and is rejected for the speed path (`05v`).

Without occupancy-matched measurement, lever A/B (det-metadata, verdict-first, dense) confounds code deltas with shared-pod noise.

## Decision

1. Run bare full-fleet colds in **off-hours / quiet windows** when possible.
2. Scrape and record Prometheus `/metrics` for the full run: at least `num_requests_running`, `num_requests_waiting`, and queue-time signals. Persist beside wall and call census.
3. **Never** treat a single cold wall as ground truth. For speed claims: **double-A** (or A/A then A/B) under **matched occupancy** bands; reject attribution if occupancy differs materially between legs.
4. Do **not** enable BI mode, raise S above 16, or restart/`auto_tune` the shared pod mid-fleet to “fix” noise.
5. Document metrics next to every package wall quoted in planning tickets and quality-gate Config A/B (`19`).

## Consequences

**Positive**

- Stops false “missed 10 min” or false lever regressions from daytime slot theft.
- Makes Config A (post-v11 remeasure) honest relative to later packages.

**Negative / cost**

- Scheduling friction (wait for quiet windows).
- Double-A roughly doubles validation wall (~0.8–1.2 h class becomes longer under contention).

**Invariants**

- Twin exclusive lane remains forbidden (ADR-001); measurement protocol does not invent isolation.
- Quality-stability still uses `flip_AA` margin, not bit-exact sidecars (`19`).

## Evidence

| Claim | Source |
|-------|--------|
| Alliance-shared; HIGH variance; ~2× wall if half slots stolen | `28-shared-pod-noise.md` |
| ≥25% flip floor; measure with `/metrics` | `28-shared-pod-noise.md`, `SYNTHESIS.md` |
| Decision checklist item 10: off-hours + matched occupancy | `PLANNING-HANDOFF.md` §5, §11 |
| Risk: shared noise → false-fail revert | `RISK-REGISTER.md` |
| Config A / quality gate honesty | `19-quality-gate-1pod.md` |
