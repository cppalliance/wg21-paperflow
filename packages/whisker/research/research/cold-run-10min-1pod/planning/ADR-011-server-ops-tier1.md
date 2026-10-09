# ADR-011: Server ops Tier-1 (MBT / CUDA graphs / DeepEP; MTP A/B only)

## Status

**Proposed** — ops recipe for `alliance-pod` only. Apply Tier-1 after image/pre-flight checks; DeepEP (+ optional DBO) as measured Tier-2; MTP k=1 behind acceptance gate only (do not bank wall seconds). See also ADR-014.

## Context

Server-only levers cut per-call **L**, not call count **N**. At fixed `--max-num-seqs 16` (raise to 32 forbidden: +57% wall), max optimistic server-only save is ~680 s on the 3003 s raw baseline (~422 s on post-short-circuit ~1921 s) — still ~25 min, not ≤10 min. Client call cuts remain mandatory.

Reject ledger and ops forage pin the Tier-1 shape:

- **MBT 16384**, decode **CUDA graphs**, prefix cache (+ retention build), long-prefill threshold: recipe bundle, highest confidence.
- **`deepep_low_latency`**: plan ~10–15% output tok/s at seqs=16 vs default AGRS (~12% planning pin); most of the fixed-seqs win is DeepEP-LL, not DBO.
- **`--enable-dbo`**: usually flat at seqs=16 unless effective concurrent decode tokens ≥32 (MTP / thresholds); enable only if DEP thresholds fire and A/B improves wall.
- **MTP k=1**: short structured JSON @ c≈16 is lose/flat zone (`05j`); A/B only, never central-stack savings.
- **Async scheduling**: if `running≈16` + elevated waiting + soft util under c=32, try `--no-async-scheduling`; never raise S to "fix" underfill (`05s`).
- **P/D disagg on one 8×H200**: reject (short OSL; DeepSeek FP8 needs full node; twin forbidden) (`05k`).

## Decision

1. **Ship Tier-1 recipe flags** on `alliance-pod` (pod restart / image bump; no whisker deploy):
   - `--max-num-batched-tokens 16384`
   - `--enable-prefix-caching` + `VLLM_PREFIX_CACHE_RETENTION_INTERVAL=32768` on a build ≥ PR #43447
   - `--compilation-config '{"mode": 3, "cudagraph_mode": "FULL_DECODE_ONLY"}'`
   - `--long-prefill-token-threshold 8192`
   - DeepSeek V4 parsers: `--tokenizer-mode deepseek_v4`, `--reasoning-parser deepseek_v4`, `--tool-call-parser deepseek_v4`
2. **Tier-2 after Tier-1 smoke:** `--all2all-backend deepep_low_latency`; then optional `--enable-dbo` only if measured gain at fixed seqs=16.
3. **MTP:** may appear in the launch template for A/B (`method=mtp`, `num_speculative_tokens=1`) but **do not bank** seconds in ≤600 s arithmetic; kill-switch if acceptance &lt;70% or JSON regresses (ADR-014).
4. **Hard anti-knobs:** never `--max-num-seqs` &gt;16; never client c&gt;32; never `deepep_high_throughput` on this mixed judge node; never MTP k≥2 for short JSON; never P/D split of one FP8 8×H200; never raise S to paper over async underfill.
5. Confirm async-scheduling state; disable if underfill signature present (`05s`).
6. Treat server ops as Phase P4 after det-metadata / verdict-first / router work; alone they do not close 10 min.

## Consequences

**Positive**

- Cuts L on the surviving MoE queue (~300–550 s recipe envelope on 3003 s; ~186–342 s post-SC planning band).
- DeepEP-LL alone is the honest ~10–15% tok/s planning gain at S=16 without touching forbidden seq raise.
- Clear ops checklist with verify metrics (`/metrics`, startup greps, MTP acceptance).

**Negative / risks**

- Server-only ceiling still leaves post-SC wall ~25 min; false sense of "ops done = 10 min."
- APC on pre-#43447 builds → 0% hits (false-pass that tuning landed).
- DBO / EPLB / MTP can regress if applied as unmeasured blog recipes; revert order MTP → CUDA graphs → DeepEP/DBO; keep MBT + retention.
- Shared multi-tenant noise on `alliance-pod` can confound single A/B (`28`).

**Invariants**

- `--max-num-seqs 16` forever for this program.
- MTP wall cuts are not part of the central stack (ADR-014).
- P/D, BI mode, guided_grammar stay rejected (ADR-012, ADR-013, `05k`).

## Evidence

| Claim | Source |
|-------|--------|
| Server Tier-1: MBT 16384, decode CUDA graphs, EP; ~10–15% tok/s DeepEP-LL; DBO only if thresholds; MTP A/B; async hygiene | `SYNTHESIS.md` |
| Ops checklist, envelopes, anti-knobs, launch delta | `16-server-ops-1pod.md` |
| DeepEP-LL ~10–15% @ seqs=16; DBO often 0–5% alone | `05t-web-dbo-deepep.md` |
| Async underfill: disable, never raise S | `05s-web-async-sched.md` |
| P/D on one 8×H200 = waste for short-OSL judges | `05k-web-pd-disagg.md` |
| MTP short JSON @ c≈16 = A/B only | `05j-web-mtp-short-json.md`, ADR-014 |
| Max server-only post-SC ~422 s → still ~25 min | `16-server-ops-1pod.md`, `SYNTHESIS.md` |
