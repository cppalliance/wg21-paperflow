# D21 — Oversize → MoE fallback

**Date:** 2026-07-24  
**Status:** Open (required with dense scoping)

---

## Decision needed

On hard-cap overflow or unresolved H2/page anchor, fail-closed **full-md on `alliance-pod`** instead of silent truncate on dense?

## Recommendation from research

**Yes — mandatory.** Scoped dense path must not silently truncate. Oversize / unresolved units skip dense and go straight to MoE; count separately from the ≤15% escalate band (D20). Assumption: ~8 oversize stay on MoE after scoping; if estimator shows ≫8 over 131k×0.80, retune caps before claiming wall.

## If yes

- Preserves correctness when window/index cannot cover the unit.
- MoE queue absorbs a small oversize tail; wall model already budgets monolith/oversize on Pro.
- Dense never sees corrupted partial candidates as if complete.

## If no (truncate on dense)

- Silent false-clear / false-fail from missing remote context.
- Negative EV for quality; defeats presence-index + grounding contract.

## Evidence

| Claim | Source |
|-------|--------|
| Hard-cap overflow → MoE fallback, not silent truncate | ADR-004 |
| ~8 oversize on MoE; A9 falsifier | `ASSUMPTIONS.md`, `12-dense-offload-architecture.md` |
| MoE role includes oversize units | `SYNTHESIS.md` heterogeneous table |
