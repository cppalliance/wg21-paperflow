# ADR-002: Keep `--max-num-seqs` at 16 on alliance-pod

## Status

Accepted

## Context

With twin V4-Pro forbidden (ADR-001), a natural temptation is to raise `--max-num-seqs` from 16 to 32 on the single live MoE pod to fake the dual-pod slot multiplier. That change was measured on the same 381-paper corpus and made wall time worse, not better.

Four full-corpus runs (2026-07-08) isolated the effect:

| Server `--max-num-seqs` | Client concurrency | Wall time |
|-------------------------|-------------------:|----------:|
| 16 | 16 | 722.4 s |
| 16 | 32 | **692.3 s** (best) |
| 32 | 32 | 1090.2 s (**+57%** vs best) |
| 32 | 32 (warm) | 1465.2 s |
| 32 | 16 | 763.7 s |

Ratio 1090.2 / 692.3 ≈ 1.57 (+57%). Root cause is MoE decode bandwidth: cost scales with the union of activated experts per step, not dense-style batch amortization. At 32 concurrent decodes each GPU loads roughly ~1.6× more expert weights per step; per-request decode slows more than parallelism gains. Isolation (client c=16 against a 32-slot server → 763.7 s) shows simultaneous decode count, not the server flag alone when underfilled, drives the regression.

KV preemption, cold start, and client-code diffs were ruled out. Prefill contention (MBT left at 8192 while slots doubled) contributes instability but does not fully explain the ~1.57× ratio; MoE expert-union scaling does. Published DeepSeek H200 deployments cluster at 8–16 sequences, not 32. Official V4-Pro recipes pin `max-num-seqs 16`.

## Decision

Pin MoE server concurrency at 16; never raise to 32 (or 64) as a cold-run speed lever.

1. Operator: keep `--max-num-seqs 16` on `alliance-pod`. Decline offered higher caps.
2. Client: keep `_DEFAULT_CONCURRENCY = 32` (overfill against a 16-slot server removes idle bubbles without engaging >16 simultaneous decodes). Do not raise client c>32 (RunPod 524 / TTFT; separate forbid).
3. Wall arithmetic for this program uses `S_eff = 16` only. No silent S=32.
4. Server Tier-1 work (MBT 16384, decode CUDA graphs, EP / `deepep_low_latency`, etc.) may proceed; none of it may include raising max-num-seqs. If `running≈16` with elevated waiting under c=32, try `--no-async-scheduling` before any slot raise.
5. Re-test 32 only if a flip condition lands: MoE-aware / expert-affinity batch scheduling in vLLM that changes the expert-union cost curve.

## Consequences

**Positive**

- Preserves the measured optimal config: server 16 + client c=32 (692.3 s on the historical warm-ish corpus; planning baselines use the later 3003 s cold v10 figure separately).
- Blocks a high-confidence false lever that costs ~+57% wall.
- Aligns with recipe pins and deployment practice (8–16).

**Negative / cost**

- Single-pod compute term cannot be halved via scheduler slots; ≤10 min remains dependent on N/L cuts and dense offload, not S.
- Aggressive continuous-batching lore ("raise max-num-seqs") must be actively rejected in ops checklists.

**Invariants**

- Twin shard (two pods × 16) is not the same as one pod at 32 sequences. Twin is forbidden (ADR-001); one-pod S=32 is forbidden here.
- Dense endpoints may use higher S (e.g. 32–48) after payload scoping; that does not license raising MoE slots on `alliance-pod`.

## Evidence

| Claim | Source |
|-------|--------|
| Raise `--max-num-seqs` to 32 forbidden; +57% wall measured | `research/cold-run-10min-1pod/00-baseline.md` |
| Never `--max-num-seqs`>16; Twin / S=32 forbidden | `research/cold-run-10min-1pod/SYNTHESIS.md`, `research/cold-run-10min-1pod/16-server-ops-1pod.md` |
| S=16 fixed in package math; 32 wrong direction (~+1700 s class) | `research/cold-run-10min-1pod/11-wall-arithmetic-1pod.md`, `research/cold-run-10min-1pod/18-packages-1pod.md` |
| Recipe hopper + measured 16→32 wall +57% | `research/cold-run-10min-1pod/05d-web-single-node-serving.md` |
| Dual-pod substitute must not be seq-32 | `research/cold-run-10min-1pod/27-dualpod-dependency-rewrite.md` |
| Planning constraint C2: slots stay 16; S=32 +57% | `research/cold-run-10min-1pod/PLANNING-HANDOFF.md` |
| Measurement matrix; revert-to-16 verdict; best = 16/c=32 | `research/slots-32-regression/SYNTHESIS.md` |
| MoE expert-union decode explains ~1.57× | `research/slots-32-regression/11-moe-batch-scaling.md` |
| Prefill/MBT co-tune contributing; ratio matches MoE better than pure 2× | `research/slots-32-regression/13-prefill-interference.md` |
| KV preemption / cold start / client ruled out | `research/slots-32-regression/10-kv-preemption.md`, `12-cold-start.md`, `14-client-skeptic.md` |
| Production configs cluster 8–16; decline 64 | `research/slots-32-regression/15-deployment-tuning.md` |
| Dual-pod-era SYNTHESIS also forbids 16→32 (+57%) | `research/cold-run-10min/SYNTHESIS.md` |
