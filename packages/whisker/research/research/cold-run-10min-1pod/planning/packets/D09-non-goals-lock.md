# D09 — Lock non-goals for this planning cycle

**Date:** 2026-07-24  
**Status:** Open (human override required to reopen)

---

## Decision needed

Lock the reject ledger as permanent non-goals for this cycle (no reopen without new evidence + explicit human override)?

## Recommendation from research

**Yes, lock.** Permanent rejects: twin V4-Pro, S=32 / `--max-num-seqs`>16, client c>32, skip monolith as default, default `--det-skip`, P/D on one 8×H200, `VLLM_BATCH_INVARIANT` on speed path, bank MTP seconds, Flash without deploy, Gemma-4 / R1 as primary unit judge, server `guided_grammar`, same-pod MoE→MoE cascade, ideal-verify deletion as 10-min lever, SGLang migrate / HTTP micro-tuning as the cold-run program, images/VLM.

## If yes (lock)

- Stops rediscovery loops in planning; tickets stay on Option A/B/C.
- Twin / S=32 / skip-monolith proposals fail closed at triage.
- Override path: new measured evidence + human sign-off only.

## If no (leave reopenable)

- Planner and agents re-litigate forbidden levers every session.
- Risk regressing to dual-pod plan or S=32 (+57% wall).
- Dilutes focus from dense restart + MoE package.

## Evidence

| Claim | Source |
|-------|--------|
| Full non-goals table | `planning/NON-GOALS.md` |
| Reject ledger | `SYNTHESIS.md`, handoff §8 |
| Twin forbidden; S=32 +57% | `ADR-001`, `ADR-002`, `00-baseline.md` |
| Skip monolith / default det-skip | `21`, `24`, `ADR-009`, `ADR-010` |
| P/D, BI, MTP bank, guided_grammar | `05k`, `05v`, `05j`, `05i` |
