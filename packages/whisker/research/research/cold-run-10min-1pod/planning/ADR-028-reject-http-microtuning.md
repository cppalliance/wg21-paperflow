# ADR-028: Reject HTTP micro-tuning as a cold-run program

## Status

Rejected — out of scope for this corpus

## Date

2026-07-24

## Context

Cold wall is approximately `(N × L_eff) / 16 + T + C` on one MoE queue (heterogeneous: `max(T_moe, T_dense)`). Measured L_eff ≈ **20 s/call** is dominated by model decode / thinking / queueing on `alliance-pod`, not by client HTTP stack overhead. Client concurrency is already capped at c≤32; in-paper calls are serial.

HTTP micro-tuning (connection pools, keepalive knobs, httpx timeouts, proxy hop shaving, retry jitter cosmetics) cannot remove hundreds of seconds of MoE decode or ~2284 → survivor call volume. SYNTHESIS lists HTTP micro-tuning beside SGLang migrate as out of scope. Legitimate timeout work already landed is **monolith/tier hang bounds** (`10`), not transport micro-optimization.

## Decision

1. **Do not** open cold-run tickets for HTTP client/proxy micro-tuning as a path to ≤10 min or Option A floors.
2. Keep existing paper/monolith timeouts and RunPod 524 mitigations as ops hygiene only; do not bank wall seconds from pool/timeout retunes.
3. Spend engineering on N cuts (det-metadata, verdict-first, router) and L cuts (Non-think probe, server Tier-1, dense when live) under ADR-025 measurement rules.

## Consequences

**Positive**

- Prevents busywork that looks like “infra wins” while leaving N×L unchanged.
- Keeps the reject ledger consistent with SYNTHESIS / NON-GOALS.

**Negative / cost**

- Occasional proxy/tail latency remains unoptimized at the HTTP layer (acceptable vs decode tax).

## Evidence

| Claim | Source |
|-------|--------|
| Out of scope: HTTP micro-tuning | `SYNTHESIS.md` §Out of scope, `NON-GOALS.md` |
| Wall model is N×L / S, not client transport | `00-baseline.md`, `11-wall-arithmetic-1pod.md`, `PLANNING-HANDOFF.md` §3 |
| Landed timeouts are hang bounds, not micro-tune | `10-impl-status-1pod.md` |
| Shared-pod / proxy risk is occupancy, not pool size | `28-shared-pod-noise.md` |
