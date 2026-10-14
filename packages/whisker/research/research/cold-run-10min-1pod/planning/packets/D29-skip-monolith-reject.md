# D29 — Reject skip monolith

**Date:** 2026-07-24  
**Status:** Accepted (reject; C5)

---

## Decision needed

Skip fleet-wide or conditional monolith (e.g. when metadata+units pass) to cut MoE wall toward ≤10 min?

## Recommendation from research

**No.** Keep monolith for every paper that reaches the LLM lane. Full skip saves ~476 s single-queue / ~159 s hetero but reopens fusion soft-clear and mono-only `candidate_not_found` / reorder loss. Heterogeneous ≤10 min design already reachable **without** skip (~511 s MoE-bound). Prefer det-metadata and other N/L cuts that preserve the document-wide judge.

## If yes

- 6/378 material fusion deltas class; 8/181 PDF suggested_verdict shifts; 16 PDF mono-only cnf risk.
- Conditional “safe” gates save ~21 s only; aggressive PDF skip reopens false-pass history.

## If no

- Monolith remains MoE bottleneck under dense offload (~381/428 calls) — shrink N/L around it, do not delete it.
- Reopen only per `21` evidence bar (labeled reorder holdout, or still >650 s MoE-bound after det-metadata with explicit fusion acceptance).

## Evidence

| Claim | Source |
|-------|--------|
| Skip monolith = No | ADR-009, `21-skip-monolith-revisit.md` |
| Planning C5; reject ledger | `PLANNING-HANDOFF.md`, `SYNTHESIS.md` |
| Prior dual-pod keep | `research/cold-run-10min/49-monolith-keep.md` |
