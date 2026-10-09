# D26 — Reject VLLM_BATCH_INVARIANT

**Date:** 2026-07-24  
**Status:** Accepted (reject on speed path)

---

## Decision needed

Enable `VLLM_BATCH_INVARIANT=1` on `alliance-pod` for cold-run / ≤10 min work?

## Recommendation from research

**No.** Permanent reject for the speed path. Upstream ~**50%** throughput hit (PR #30018); MTP+BI field ~3× tok/s drop. Quality bar is quality-stability (findings/verdicts/structure), not bit-exact batch identity (`MODELS.md`). Do not bundle BI with Tier-1/Tier-2 speed flags.

## If yes

- Roughly doubles `L_eff` at S=16; moves wall **away** from ≤600 s.
- Erases MTP/DeepEP gains pursued under ops A/B.
- False-pass risk if microbench at c=1 looks “deterministic and fine.”

## If no

- Accept non-bit-exact token ids across batch compositions (already the program contract).
- Bit-exact campaigns must use a separate corpus/recipe.

## Evidence

| Claim | Source |
|-------|--------|
| BI = No; ~50% throughput | ADR-013, `05v-web-batch-invariant.md` |
| Reject ledger | `SYNTHESIS.md`, `PLANNING-HANDOFF.md` §8 |
| Quality-stability ≠ bit-exact | `MODELS.md` |
