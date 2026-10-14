# ADR-014: MTP speculative decoding — A/B only (do not bank)

## Status

**Accepted, probed, revert.** Live A/B on `alliance-pod` (2026-08-25/26): MTP k=1 acceptance 92.3%, verdict flips at AA noise (14.8% vs 15.2%), wall 3315.6 s vs median-A 3185.2 s (+4.1% slower), JSON errors 30 vs A1 23 / A2 12. Gate failed on wall and JSON. Flags reverted. Do not bank MTP wall cuts. Full writeup: `packages/whisker/research/mtp-ab-experiment/RESULTS.md`.

## Context

DeepSeek-V4-Pro supports native MTP in vLLM (`method=mtp`). Community and recipe lore treat MTP as a major decode tok/s lever, and server ops Tier-1 historically listed k=1 speculative config with 100–200 s optimistic impact on the 3003 s baseline.

For **this** workload — short structured JSON, long ISL, concurrency ≈16 (S=16 / client c=32) — public evidence says MTP is in the lose/flat zone:

- vLLM GB300 DeepSeek blog: ISL=2k, OSL=64 → MTP overhead cannot amortize; throughput **lower with MTP on**.
- Spec decode speedup collapses as QPS rises (PR #12755: ~1.63× @ QPS=1 → ~1.0× @ QPS=8); production crossovers often ~4–8 concurrent requests.
- MagicDec: short sequence + large batch → speculative decode hurts batch efficiency.
- High structured-JSON acceptance is necessary but not sufficient when decode steps are few.
- Recipe `num_speculative_tokens: 2` is anti-pattern for short judge JSON; use **k=1 only** if probing.
- MTP head can be silently missing on some quants → flags look on, speedup is zero until verified.

Ngram/PLD as MTP substitute is only marginal (~37–75 s; keys only) and is not a banked substitute (`05w`).

Reject ledger: **MTP wall savings = A/B only — do not bank.**

## Decision

1. **Do not** include MTP seconds in central package arithmetic (MODERATE / AGGRESSIVE / heterogeneous ~511 s stacks).
2. Optional ops probe only: `--speculative-config '{"method":"mtp","num_speculative_tokens":1}'` with CUDA-graph decode on, after Tier-1 MBT/prefix/graphs hygiene (ADR-011).
3. **Acceptance gate:** keep MTP only if `spec_decode_draft_acceptance_rate` ≥70%, JSON validity ≥ baseline, fused-verdict flip budget OK, and cold wall improves by a material margin under load-matched occupancy. Else disable.
4. **Never** plan on k≥2 for short JSON; never claim recipe k=2 as our regime.
5. Verify `SpeculativeConfig(method='mtp'...)` **and** live acceptance under c≈16 — flag presence alone is insufficient.
6. Ngram/PLD: defer / keys-only; not a banked MTP replacement for this program.

## Consequences

**Positive**

- Prevents false ≤600 s plans that assume −100–200 s MTP on short-JSON traffic.
- Allows a kill-switched probe if alliance-pod OSL/acceptance unexpectedly clear the amortization cliff.
- Separates "recipe enables MTP" from "plan banks MTP."

**Negative / cost**

- Decode-heavy monolith / long-thinking tails might leave some MTP headroom unused if default stays off.
- Operators must run a real cold A/B (shared-pod noise aware) before claiming any MTP win.

**Invariants**

- Short JSON @ c≈16 → prior is hurt/flat; help only if measured.
- MTP is semantic-close / not bit-exact; quality A/B still required if left on.
- Bundling MTP with `VLLM_BATCH_INVARIANT` is forbidden (ADR-013).

## Evidence

| Claim | Source |
|-------|--------|
| MTP wall savings = **A/B only**; short JSON @ c≈16 lose/flat; do not bank | `SYNTHESIS.md` reject ledger |
| Regime map + recommendation Return: A-B | `05j-web-mtp-short-json.md` |
| GB300 OSL=64 cliff; QPS collapse; k=1 only | `05j-web-mtp-short-json.md` |
| Ops MTP acceptance ≥70%; k=1; revert MTP first | `16-server-ops-1pod.md` |
| Community MTP rank with A/B caveat | `05i-web-community-workarounds.md` |
| Execution order: server Tier-1 with no MTP banked | `SYNTHESIS.md` |
| Handoff: MTP k=1 A/B only (do not bank) | `PLANNING-HANDOFF.md` |
| Live A/B: accept 92.3%, wall +4.1% vs median-A, revert | `packages/whisker/research/mtp-ab-experiment/RESULTS.md` |
