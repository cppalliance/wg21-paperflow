# max-num-seqs 32 Regression - Research Synthesis

**Verdict:** 32 concurrent decodes are intrinsically slower on this pod. Revert to 16.
**Confidence:** high (four full-corpus measurements, cause isolated empirically)

## The measurement matrix (381 papers, identical corpus and client code)

| Server --max-num-seqs | Client concurrency | Wall time | Errors | Date/Time |
|---|---|---|---|---|
| 16 | 16 | 722.4 s | 0 | 2026-07-08 morning |
| 16 | 32 | **692.3 s (best)** | 1 transient | 2026-07-08 ~15:10 |
| 32 | 32 | 1090.2 s | 1 | 2026-07-08 ~16:11 (post-reboot) |
| 32 | 32 (warm rerun) | 1465.2 s | 2 | 2026-07-08 ~16:39 |
| 32 | 16 | 763.7 s | 0 | 2026-07-08 ~17:05 |

## Root cause

MoE decode is memory-bandwidth-bound by the UNION of distinct experts activated
per step, not amortized like dense models. With 32 concurrent sequences each
GPU loads roughly 1.6x more expert weights per decode step (11-moe-batch-scaling.md).
Decode throughput per request drops by more than the parallelism gain.

The isolation test proves it: client c=16 against the 32-slot server restored
763.7 s. Only the number of SIMULTANEOUS DECODES matters; the server cap itself
is harmless when the client stays at 16.

## Ruled out

- **KV-cache preemption** (10-kv-preemption.md): V4's compressed attention needs
  ~15 GiB at 32x100k-token sequences vs >110 GiB available. Pod metrics after
  the slow runs: `num_preemptions_total 0`.
- **Cold start** (12-cold-start.md): the first post-reboot run showed a ~6-min
  slow ramp (sidecar mtime forensics), but the WARM rerun was even slower
  (1465.2 s) with uniformly low throughput. Cold start was noise, not cause.
- **Client code** (14-client-skeptic.md): only change between runs was the
  `_DEFAULT_CONCURRENCY` constant; all runs passed `--concurrency` explicitly.

## Contributing

- **Prefill contention** (13-prefill-interference.md): `max-num-batched-tokens`
  (8192) was not co-raised, so 32 sequences share the same per-step token
  budget. Explains part of the instability (1090 vs 1465 s: batch composition
  varies with completion order).

## Decision

- Operator: revert to `--max-num-seqs 16`. Decline the offered 64 (would be
  strictly worse). Published DeepSeek H200 deployments use 8-16
  (15-deployment-tuning.md).
- Client: keep `_DEFAULT_CONCURRENCY = 32`. Against a 16-slot server the
  overfill eliminates idle bubbles (692.3 vs 722.4 s) without engaging more
  than 16 simultaneous decodes.
- Optimal proven config: **server 16 slots + client c=32 = 692.3 s**.

## Flip conditions

- A vLLM release with MoE-aware batch scheduling (expert-affinity batching)
  would justify re-testing 32.
- If the corpus grows so large that queue depth at c=32 exceeds ~2 min waits,
  re-check the proxy idle-timeout boundary (see research/concurrency-381/).

---
Sources: reports 10-15 in this directory; sidecar mtime forensics; pod
/metrics probe (num_preemptions_total 0); four full-corpus runs 2026-07-08.
