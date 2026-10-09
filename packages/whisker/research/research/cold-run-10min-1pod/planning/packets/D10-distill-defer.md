# D10 — Defer judge distillation

**Date:** 2026-07-24  
**Status:** Open (program sequencing)

---

## Decision needed

Start a distill / SFT specialist-judge program now, or defer until Path F (scoped live dense + short pass tokens) fails the 381 quality gate?

## Recommendation from research

**Defer.** Literature: 3× unit decode does **not** require distillation first. Fastest path is off-shelf dense (`h200-qwen3-32b`) + payload scoping + short pass-path tokens (SLMJury-style). One fleet (~1510 labels) is below JudgeLM’s 3.5K scaling floor; production-safe SFT is weeks behind a dense canary. Distill only if P7 (cascade + gate) fails parity.

## If yes (start distill now)

- Parallel program: weeks of data (≥5K ideally 8–12K) + LoRA + 381 gate.
- May help if dense false-clears permanently; does not unblock today’s 404.
- Opportunity cost vs shipping Option A and asking for dense restart.

## If no (defer until Path F fails)

- Days–1 week to dense canary after restart vs 6–10 weeks for production SFT.
- Keeps ≤10 min path on infra + scoping, not on training.
- Accepts that distill is a contingency, not the critical path.

## Evidence

| Claim | Source |
|-------|--------|
| Distill only if Path F fails 381 gate | `SYNTHESIS.md` execution order §5 |
| 3× decode ≠ distill first; off-shelf dense primary | `05g-web-slmjury.md` |
| JudgeLM 3.5K / 100K scaling floors | `05g` (arXiv:2310.17631) |
| Path F = scoped dense + short pass tokens | `FILE-MANIFEST.md`, `05g` |
| Dense still 404 → distill cannot replace restart | `26` |
