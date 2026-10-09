# ADR-018: SLA fork if dense stays down

## Status

Proposed

## Date

2026-07-24

## Context

≤10 min cold on one V4-Pro replica at quality is below the MoE-only physics floor (front-end alone ~948 s; MODERATE survivors ~1366–1493 s; AGGRESSIVE realistic ~680–715 s). The only arithmetic path under the twin ban is heterogeneous offload: `wall = max(T_moe, T_dense)` onto a live dense Alliance endpoint (primary: `h200-qwen3-32b`).

As of the 2026-07-24 probe, all four dense `SERVICES.toml` endpoints return HTTP 404. Only `alliance-pod` is up. Package C / Option B is infra-blocked. Continuing to hold a public ≤10 min goal while dense restart is uncertain produces a false program: MoE-only work still ships value (~15–20 min after the MoE package), but the 10-min target cannot be met without infra.

## Decision

Adopt an explicit **SLA fork** keyed on dense restart:

1. **Ask Alliance ops** to restart at least `h200-qwen3-32b` (smoke: `/v1/models` 200 + one unit-check completion). Track the ask with a clock start date.
2. Define **N** (calendar days after the ask is sent; proposed default **N = 14** unless ops commits a sooner date in writing).
3. **If dense is live within N days:** keep ≤10 min as the program goal; execute Option B (payload scoping → cascade → 381/381 parity → instrumented B ≤620 s).
4. **If dense is not restarted within N days** (or ops declines): **publish ~15–20 min** as the honest cold-fleet SLA after the MoE-only package (Option A + Option C). Stop the ≤10 min program as an executable commitment. Do not promise hairline AGGRESSIVE ~585 s without dense.
5. Until the fork resolves, plan **Option A + Option C language in the same doc**: ship MoE levers now; treat ≤10 min as blocked, not delayed-with-hope.

## Consequences

**Positive**

- Separates shippable MoE progress from an infra-blocked 10-min claim.
- Gives ops a clear deadline and a clear ask (`h200-qwen3-32b` first).
- Avoids indefinite “waiting for dense” while still landing ~12–23 min MoE package value.

**Negative / cost**

- Publishing 15–20 min is a product/comms reset if stakeholders still expect 10 min.
- N is a policy knob: too short pressures ops; too long leaves a zombie 10-min program.
- If dense returns after SLA reset, re-opening ≤10 min requires a new decision (re-enter Option B), not silent goal creep.

**Invariants**

- Twin V4-Pro remains forbidden (ADR-001). SLA fork does not revive the twin.
- MoE-only AGGRESSIVE may land ~12–15 min; that is still not ≤10 min and must not be marketed as such.

## Evidence

| Claim | Source |
|-------|--------|
| MoE-only cannot hit 10 min at quality; honest SLA ~15–20 min without dense | `SYNTHESIS.md`, `PLANNING-HANDOFF.md` §3, `17-physics-floor-skeptic.md` |
| Heterogeneous ~511 s MoE-bound only with scoping + parity | `12-dense-offload-architecture.md`, `20-heterogeneous-wall.md` |
| All dense endpoints 404; `alliance-pod` UP | `26-dense-pod-liveness.md`, `PLANNING-HANDOFF.md` §7 |
| Option C: if dense will not restart, publish ~15–20 min; stop 10-min program | `PLANNING-HANDOFF.md` §4 |
| Decision checklist: SLA keep 10 vs reset; dense restart yes/no/when | `PLANNING-HANDOFF.md` §5 |
| Dense-down risk → Option C SLA reset | `PLANNING-HANDOFF.md` §11 |
