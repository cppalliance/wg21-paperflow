# 20 - Concurrency Sweep Results (Phase 0, executed 2026-07-07)

Protocol per `19-steelman.md`: fixed 20-PID list sampled evenly across the
204-sidecar corpus (N5034 ... P4205R0), run against the live alliance-pod
(vLLM 0.24.0) with the pre-change CLI (`--concurrency` flag, default 1).

## Wall times

| Run | Concurrency | Wall (footer) | s/paper effective | Errors | Model retries |
|-----|-------------|---------------|-------------------|--------|---------------|
| 1   | 8           | 91.2 s        | 4.6               | 0      | 0             |
| 2   | 16          | 89.9 s        | 4.5               | 0      | 0             |
| 3   | 32          | 59.9 s        | 3.0               | 0      | 0             |
| 4   | 32 (rerun)  | 64.2 s        | 3.2               | 0      | 0             |

Baseline projection from the 200-paper c=3 run (10.8 s/paper): 216 s for 20
papers. Even c=8 beats it 2.4x; c=32 by 3.4x.

## Interpretation

- **The knee is NOT at 8.** At c=32 all 20 papers were in flight
  simultaneously and wall time collapsed to the longest single chain
  (~60 s = tier-1 + tier-2 escalation). Per-request latency stayed ~30 s,
  so the pod absorbs at least 20 concurrent sequences without latency
  collapse. The community `--max-num-seqs 8` assumption (05a) does not
  match this pod's behavior; its actual limit is >= 20.
- **c=16 ~= c=8 on 20 papers** is a tail artifact, not a knee signal: with
  waves of 8 vs 16, the escalated papers dominate the last wave either way.
- **Zero errors, zero retries at every N.** The 600 s-timeout failure class
  (persona 15) did not materialize up to 32 in flight.
- **Verdict drift is real and NOT concurrency-specific:** run 3 vs run 4
  (identical c=32, identical PIDs) produced 15 pass / 5 review vs
  10 pass / 10 review. The c=8 run also flipped individual papers vs the
  c=3 corpus baseline (e.g. N5034 pass -> review, P4023R0 review -> fail,
  P3842R1 review -> pass). This matches the Determinism-Auditor's
  prediction (16): MoE batch non-invariance drifts borderline verdicts
  between ANY two runs; concurrency amplifies at most incrementally.
  Consequence: advisory distributions are comparable, per-PID verdicts on
  borderline papers are not rerun-stable without a server-side
  batch-invariant mode.

## Decisions taken (implemented in packages/whisker)

- `_DEFAULT_CONCURRENCY = 8` (conservative default; sweep-verified),
  warning above `_MAX_TESTED_CONCURRENCY = 32`.
- Pre-batch health gate `GET {base_url}/models` (olmocr/docling pattern).
- Per-paper `asyncio.wait_for` budget `_PAPER_TIMEOUT_SECONDS = 900`.
- `load_services()` hoisted to batch scope, shared via new optional
  `registry` kwarg on `adjudicate_paper`.
- Slot output budgets bound at agent construction (fast=2048, deep=4096)
  per the authority doc's `max-output` meta; A/B on 6 live papers showed
  no error/retry regression (33.4 s before, 37.8 s after, within run noise).
- Rejected: `asyncio.to_thread` for paper reads (SqliteBackend is
  documented not thread-safe) and a lock in `_BarAwareHandler.emit`
  (Handler.handle already serializes; the loop is single-threaded).

## Full-corpus rerun with the new setup (2026-07-07, post-change)

`whisker-tapetum-llm --review-all --concurrency 16`, all changes above live
(health gate, per-paper timeout, shared registry, slot budgets):

- **204 papers in 556.3 s (9.3 min)** = 2.7 s/paper effective.
- **3.9x faster** than the 2159.8 s / 36 min c=3 baseline; 0 errors.
- Verdict histogram: 118 pass / 75 review / 11 fail (c=3 baseline on the
  200-paper set: 100/87/10). The shift is within the run-to-run MoE drift
  band established by the sweep (runs 3 vs 4), plus 4 extra papers.
- One `max_tokens` truncation retry on the fast slot (2048 -> 3072 grow
  path worked as designed); its warning marker
  ("Raw JSON output truncated") is now included in
  `_RETRY_WARNING_MARKERS` so it rolls into the footer count instead of
  printing above the progress bar.
- Remaining ladder: twin-pod shard (blocked on pod restart, see
  CTO-REQUEST.md) projects ~4-5 min; server-side `max-num-seqs`
  confirmation may allow c=32 (~sub-4 min).

## Full-corpus c=32 validation (2026-07-08)

`whisker-tapetum-llm <381 pids> --concurrency 32`, post-optimization
(output discipline, text-layer normalization, parallel judge dispatch):

- **381 papers in 692.3 s (11.5 min)** vs 722.4 s at c=16 = **-4.2%**.
- 1 transient error (`peer closed connection`), 1 model retry. Not
  systematic: the same paper passed on the c=16 run and prior batches.
- Verdict histogram: 252 pass / 118 review / 10 fail (c=16 baseline on
  same corpus: 246/125/10). Within established MoE drift band.
- Win source: c=32 overfills the 16 scheduler slots by 16, so the server
  back-fills immediately as slots free. At c=16 each slot sits idle for
  the ~1 s local grounding/persist window between completion and the next
  request dispatch. 381 papers x ~1 s / 16 slots = ~24 s theoretical
  bubble, matching the ~30 s measured delta.
- `_DEFAULT_CONCURRENCY` raised from 16 to 32 based on this result.

## Server --max-num-seqs 32 experiment (2026-07-08, negative result)

The operator raised the pod to `--max-num-seqs 32` on request. Result:
381 papers at client c=32 took 1090.2 s, a warm rerun 1465.2 s (vs 692.3 s
at 16 slots). Isolation test: client c=16 against the 32-slot server
restored 763.7 s, proving the number of SIMULTANEOUS DECODES is the
variable. MoE decode loads more distinct expert weights per step as the
batch grows; the pod is bandwidth-bound. Pod metrics showed zero
preemptions (KV cache innocent). Server reverted to 16 on our request.
Optimal proven config: server 16 slots + client c=32. Full analysis:
research/slots-32-regression/SYNTHESIS.md.

## c=381 experiment (2026-07-08, negative result)

Fired all 381 papers at once to test the hourly-pricing "free queue"
hypothesis. Result: **257/381 errors** (all `peer closed connection
without sending complete message body`), 124 succeeded, 299.2 s wall.
The RunPod proxy kills idle connections after ~100 s; with --max-num-seqs
16, tail requests wait >600 s in the vLLM queue before first byte.
Confirms: client concurrency above ~32 adds only queue depth and proxy
risk, no throughput. Research reports in `research/concurrency-381/`.

## CTO answers (2026-07-07, closes the open infra questions)

Source: https://github.com/cppalliance/runpod/blob/master/templates/deepseek/H200SXM.txt

- **There is only one pod.** The `h200x8-deepseek-v4-pro` SERVICES.toml
  entry is stale; its 404 is expected, not an outage. Dual-pod sharding is
  cancelled permanently, the ~4-5 min ladder rung does not exist.
- **`--max-num-seqs 16`** is the confirmed server scheduler cap. This
  explains the sweep numbers precisely: c=32 collapsed 20 papers into one
  wave because 20 > 16 only queues 4 excess requests briefly. Client
  default raised 8 -> 16 to exactly fill the scheduler (c > 16 only adds
  queue depth).
- **`--reasoning-parser deepseek_v4`** is set (plus deepseek_v4 tool-call
  parser), so structured output via `response_format: json_schema` /
  xgrammar is available if we ever want it.
- Prefix caching: not disabled in the launch flags, so vLLM V1 default-on
  applies; the shared ~2.9k-token system+schema prefix benefits passively.
- Realistic floor with one pod at c=16: the measured 9.3 min for 204
  papers is close to saturation (16 sequences x ~30 s per call, 217
  calls). Further gains now require per-call cuts (thinking caps, guided
  JSON), not more client concurrency.
