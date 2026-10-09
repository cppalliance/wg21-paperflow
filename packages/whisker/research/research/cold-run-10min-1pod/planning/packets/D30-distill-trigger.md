# D30 — Distill trigger (Path S)

**Date:** 2026-07-24  
**Status:** Deferred unless Path F fails

---

## Decision needed

Start judge distillation (SLMJury / JudgeLM-style 7B–14B LoRA) now as a cold ≤10 min lever?

## Recommendation from research

**No — only if Path F fails the 381 gate.** Path F first: scoped dense on live `h200-qwen3-32b` + short pass-path tokens (days–1 week). ~1510 labels/run is below JudgeLM’s smallest scaling point (3.5K); SFT is Path S (2–10 weeks) **only** if off-shelf dense fails fused-verdict parity. Distill is a backup program, not a parallel banked 10-min closer.

## If yes (start distill now)

- Months of labeling/LoRA while dense restart + scoping still unblock the honest ≤10 min design.
- 3× unit decode is a unit-leg KPI, not a solo ≤600 s path.

## If no (wait for Path F failure)

- Execute MoE package + dense restart + scoping + cascade gate first.
- Open Path S only when scoped dense + short tokens fail 381/381 (or equivalent vector) with no acceptable escalate retune.

## Evidence

| Claim | Source |
|-------|--------|
| Distill only if Path F fails 381 gate | `SYNTHESIS.md` §Execution, `05g-web-slmjury.md` |
| A26 assumption / backup | `ASSUMPTIONS.md` |
| FAQ Q52 | `PLANNER-FAQ.md` |
| ~1510 labels/run ≪ JudgeLM 3.5K | `05g` |
