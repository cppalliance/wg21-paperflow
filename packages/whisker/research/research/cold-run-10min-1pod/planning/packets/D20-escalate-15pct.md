# D20 — Escalate-to-Pro band ≤15%

**Date:** 2026-07-24  
**Status:** Open (Option B only; inert while dense 404)

---

## Decision needed

Enforce **≤15%** escalate-to-Pro of dense unit attempts as a ship gate for the heterogeneous cascade?

## Recommendation from research

**Yes, when Option B is live.** Planning band 10–20%; ship ceiling **15%**. Calibrate confidence λ on holdout. At ~30% escalate, Pro queue can break ≤600 s even if dense is fast. Oversize-direct-to-MoE counts **separately** from escalate %.

## If yes

- Keeps MoE-bound ~511 s arithmetic plausible; matches FrugalGPT/Jung cheap-first share.
- Instrument `{accepted_dense, escalated_pro, dense_conf, fused_delta}`; fail closed if rate >15% at parity-passing λ.
- Triggers: schema invalid, conf < λ, empty defect quote on non-pass, dense 5xx after one retry.

## If no (no rate ceiling)

- Silent fat escalate tail → wall regresses while average looks green.
- Risk shipping a cascade that is effectively dual-pay (dense + Pro) on too many units.

## Evidence

| Claim | Source |
|-------|--------|
| Escalate ≤15%; ~30% breaks ≤600 s | ADR-020, `05l`, `PLANNING-HANDOFF.md` §4/§11 |
| FrugalGPT strong-tier ~16.6% class | `05p-web-frugalgpt.md` |
| Dense false-clear mitigation = escalate + 381 gate | `SYNTHESIS.md` |
