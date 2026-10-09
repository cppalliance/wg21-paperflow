# D25 — Avoid R1 as unit primary

**Date:** 2026-07-24  
**Status:** Accepted (reject as primary)

---

## Decision needed

Use `b200-r1` (DeepSeek-R1-distill-70B) as the primary dense unit-check judge?

## Recommendation from research

**No.** Avoid as unit primary. 70B + thinking blocks; ≤1.5× decode hypothesis; no throughput-persona support for our short JSON UnitCheck path. Prefer Qwen3-32B; do not prioritize R1 restart in INFRA-ASK.

## If yes (use R1 primary)

- Likely re-imports CoT wall into the “fast” leg; undercuts why units left MoE.
- Still needs 381 gate; thinking-off on R1 is unproven for our schema at fleet scale.

## If no (avoid)

- Dense ask stays on Qwen3-32B (+ optional 27B reserve).
- Aligns with reject/avoid ledger alongside Gemma-4 primary ban.

## Evidence

| Claim | Source |
|-------|--------|
| Avoid `b200-r1` (thinking overhead) | ADR-005, `SYNTHESIS.md`, `12` |
| ≤1.5× decode; no throughput support | ADR-005 |
| H4: R1 ban softens only if thinking-off matches Qwen latency+parity | `FALSIFIERS.md` |
