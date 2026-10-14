# ADR-029: Oversize unit checks → MoE fallback

## Status

Proposed — routing invariant for Option B

## Date

2026-07-24

## Context

Dense primary `h200-qwen3-32b` has a **131k** context window. Fleet accounting: **373/381** papers fit unit checks in-budget; **~8/381** exceed a 131k × 0.80 safety margin and must not be truncated onto dense (`12`, `23`).

ADR-004 scopes unit prompts to ~10–12k tokens (H2 window + presence index). Hard-cap overflow after neighbor trim, or unresolved PDF anchor with zero heading overlap, is the same failure class: dense cannot see a faithful unit payload. Silent truncate on dense is a recall / false-clear hazard. Full-md unit calls on dense without scoping collapse S≤16 and erase offload EV.

## Decision

1. **Preflight oversize / scope-fail units to `alliance-pod`** (full `candidate_md`, MoE S=16 path). Expected volume: **~8 unit calls** fleet-wide in the architecture census (plus any per-unit hard-cap overflows after scoping).
2. **Never** silent-truncate an oversize or unscoped unit onto dense to “keep the dense queue busy.”
3. Wire the fallback in the service router / `_check_one_unit` hook before the dense HTTP attempt (ADR-003 router + ADR-004 overflow).
4. Quality gate: **0 mis-routed oversize** on Config B (`QUALITY-PROTOCOL.md`); oversize cohort must match Pro baseline fused behavior.
5. This fallback is **expected routing**, not a dense-down incident (contrast ADR-030).

## Consequences

**Positive**

- Preserves recall on giant H2 / table / oversize-md papers.
- Keeps dense KV math honest for the in-budget ~1502 units.
- Small MoE add (~8 calls) fits the ~428 MoE budget in `12`.

**Negative / cost**

- Slight MoE queue load; if oversize rate >>8 after scoping, revisit window constants before raising dense S claims.
- Router complexity and tests for the overflow path.

## Evidence

| Claim | Source |
|-------|--------|
| ~8/381 oversize → MoE; 373/381 in 131k | `12-dense-offload-architecture.md` |
| Hard-cap / unresolved anchor → fail-closed MoE | `23-payload-scope-dense.md`, ADR-004 |
| Routing ~1510 dense / ~8 MoE / 0 mis-routed | `QUALITY-PROTOCOL.md` |
| Cascade: oversize skip T1 | `05l-web-cascade-papers.md`, ADR-003 |
| Payload scoping recall risk → MoE oversize fallback | `PLANNING-HANDOFF.md` §11, `RISK-REGISTER.md` |
