# ADR-013: Reject `VLLM_BATCH_INVARIANT` on the speed path

## Status

**Accepted** — never enable `VLLM_BATCH_INVARIANT` for cold-run ≤10 min / throughput work on `alliance-pod`. Leave off unless a separate bit-exact campaign explicitly accepts a large wall regression.

## Context

`VLLM_BATCH_INVARIANT=1` forces deterministic kernels and consistent numerics across batch sizes by disabling optimizations that introduce non-determinism (e.g. custom all-reduce in TP). Official docs state the performance trade-off is intentional. Upstream PR #30018 quantifies ~**50% throughput reduction**. Field report with MTP: decode ~75→23 tok/s under BI (~3× slowdown).

This program's quality bar is **quality-stability** (same findings / verdicts / structure), not bit-exact rerun identity (`MODELS.md`). Enabling BI roughly doubles `L_eff` at fixed S_eff=16 and moves wall **away** from ≤600 s. It is the wrong tool for the speed path and can erase any MTP decode gains pursued under ADR-014.

Feature remains beta; DeepSeek-V4-Pro is not a documented first-class tested pin for BI.

## Decision

1. **Do not** set `VLLM_BATCH_INVARIANT=1` (or equivalent) on `alliance-pod` for cold-run / ≤10 min planning.
2. Do not bundle BI with Tier-1/Tier-2 speed flags (MTP, CUDA graphs, DeepEP).
3. If a future campaign needs batch-composition bit-stability, treat it as a **separate** corpus with an accepted wall tax; do not mix into this program's arithmetic.
4. Keep BI listed in the permanent reject / do-not-bank ledger until upstream documents ≤~5% tax on H200 TP8 V4-Pro continuous batching **and** goals change.

## Consequences

**Positive**

- Avoids ~2× wall blow-up class regression on the MoE queue.
- Prevents self-defeating "determinism for speed" false-pass on concurrency=1 microbenches.
- Keeps quality-stability strategy aligned with MODELS.md (findings parity, not bit-exact).

**Negative / cost**

- Rerun token-id identity across batch compositions remains non-guaranteed under continuous batching (accepted for this program).
- Bit-exact CI campaigns must not silently reuse this pod's speed recipe.

**Invariants**

- Speed path and bit-exact path are separate knobs; this ADR only rejects BI **for speed**.
- Out of scope: BI mode as a ≤10 min lever (`SYNTHESIS.md` Out of scope).

## Evidence

| Claim | Source |
|-------|--------|
| `VLLM_BATCH_INVARIANT` = **No**; ~50% throughput hit | `SYNTHESIS.md` reject ledger |
| Docs + PR #30018 ~50%; MTP+BI ~3× tok/s drop | `05v-web-batch-invariant.md` |
| Purpose is batch-composition determinism, not latency | `05v-web-batch-invariant.md` |
| Quality-stability ≠ bit-exact | `MODELS.md`, `05v-web-batch-invariant.md` |
| Handoff reject ledger includes BI mode | `PLANNING-HANDOFF.md` |
