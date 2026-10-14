# llm-batching - Research Synthesis

**Verdict band:** usable-with-conditions   **Confidence:** high
**Decision vs our codebase:** adopt-partially (raise client concurrency + small whisker hardening + infra asks; REJECT provider-style batch infrastructure)

## Summary

- The 36-min wall time is 213 LLM calls (200 tier-1 + 13 tier-2) at a back-solved
  **~30.4 s mean per call**, throttled by our own `--concurrency 3`. The
  `run_agent` path has no global semaphore (`pipeline/runner.py:266-272`), so the
  CLI semaphore is the only client throttle (`11-throughput-auditor.md`).
- Per call, **decode dominates (~82-92%)**: P50 input ~8.5K tok prefills in ~2 s;
  the ~635-900-token JSON decodes at 22-32 tok/s (`17-latency-decomposer.md`).
  Input shrinking and prefix caching are sub-second levers; concurrency and
  server capacity are the real ones.
- **Provider batch APIs are the wrong abstraction**: OpenAI/Anthropic batches are
  24h-SLA cost-discount jobs; the pod is billed per hour, discount irrelevant.
  vLLM 0.24 has **no** HTTP `/v1/batches` (offline `run-batch` needs pod shell we
  do not have; feature request closed `not_planned`) (`05b`, `05d`).
  Self-hosted "batching" = raising concurrent requests into continuous batching.
- **The knee is likely ~8**: community H200x8 DeepSeek-V4-Pro configs run
  `--max-num-seqs 8`; client N above the server knee only adds queue depth and
  600 s-timeout risk (`05a`, `15-concurrency-safety.md`). Projections: c=8 =>
  ~9.4-13.5 min; c=16/32 without a server change => no better than c=8 (`19-steelman.md`).
- **The twin pod `h200x8-deepseek-v4-pro` returned 404 on all probes today**
  (distinct RunPod instance, currently down). When live, sharding across both
  pods halves wall time; a ~15-line round-robin in `cli.py` or two parallel CLI
  processes with `--service` overrides suffices (`18-load-splitter.md`).
- Determinism: batch non-invariance + MoE routing variance are **already active
  at c=3**; higher N raises distribution-drift risk incrementally. Permitted:
  D11 binds dissect, not the advisory lane. `tapetum_llm.md` needs an honest
  "Determinism (advisory)" note (`16-determinism-auditor.md`).

## Top findings (ranked)

- [CRITICAL][NOW] Raise client concurrency to the pod knee (default 8, sweep
  8/16/32 first). Evidence: `cli.py:409-416`, projections in `19-steelman.md`.
  adopt? yes.
- [CRITICAL][NOW] 15-minute empirical sweep gates everything: 3x20 papers at
  c=8/16/32; wall time, retries, errors, verdict histogram vs c=3. adopt? yes.
- [HIGH][NOW] Infra asks to CTO (no code): restart/repair twin pod; report
  `--max-num-seqs`, prefix-caching, reasoning-parser/thinking defaults; optional
  raise max-num-seqs toward 16-32 if KV headroom allows. adopt? yes.
- [HIGH][NOW] Whisker hardening for N>3 (all in `packages/whisker`): pre-batch
  `GET /models` health gate (olmocr/docling pattern), per-paper
  `asyncio.wait_for` budget, `asyncio.to_thread` for sync paper/sidecar reads in
  `_custom_select`, lock around `_BarAwareHandler.emit`. Evidence: `12`, `14`,
  `15`. adopt? yes.
- [HIGH][AFTER-POD] Dual-pod shard: `--shard-pods` round-robin (fast+deep
  colocated per paper) or zero-code two-process split. Evidence: `18`. adopt?
  yes, once twin pod is live.
- [MED][AFTER-SWEEP] Tier-specific budgets in `adjudicate.py:450-458` (fast
  `max_tokens=2048` per authority doc); thinking-cap only if `--debug` probe
  shows reasoning blocks are non-empty (server default for V4-Pro is
  thinking-off; expected saving 0 s if default holds). Evidence: `17`, `05e`.
  adopt? partial.
- [MED][LATER] Guided JSON via xgrammar (`response_format json_schema`):
  throughput win under batching in 0.24, defers constraints until after
  reasoning; needs pod `--reasoning-parser` confirmation. Evidence: `05c`.
  adopt? partial (behind a flag, A/B first).
- [LOW] Hoist `load_services()`/agent construction out of the per-paper loop
  (<0.2% wall, but removes linear CPU tax and creates a shared-client seam).
  Evidence: `11`. adopt? yes, opportunistic.

## Rejected workstreams (explicit)

- Provider-style batch endpoint emulation (`/v1/batches`, JSONL job machinery):
  wrong semantics, no server support, no shell on pod (`05b`, `05d`, `19`).
- Work queues / job runners: `Semaphore + gather` IS the queue (`19`).
- Chunk-level parallelism: dead lever post base64 strip; <1% of corpus seconds
  (`13`, `19`).
- Connection pooling / step-meta budget forwarding in `pipeline`: read-only
  package; TLS overhead is <1% of a 30 s call. PARKED as infra note (`11`).
- LiteLLM dependency: heavy, thread-based, poor fit (`05d`).

## Bugs / edge-cases in OUR code (surfaced by the comparison)

- `cli.py` `_BarAwareHandler.emit` mutates shared state without a lock; UX
  degrades at N>=8 (`15`).
- `adjudicate.py:_custom_select` does sync sqlite/file I/O on the event loop;
  blocks other workers' progress under high N (`15`).
- `AsyncOpenAI` default 600 s read timeout: queued requests at N>>knee can burn
  10 min then error with no sidecar; needs per-paper `wait_for` + N cap (`15`).
- `tapetum_llm.md` claims budgets (`max-output: 2048`, `thinking-budget: 1024`)
  that are never forwarded; doc must be honest or budgets wired whisker-side (`16`).

## Top portable detail

olmocr's dual-layer throttle (paper workers vs LLM inflight `BoundedSemaphore`)
plus its pre-flight `GET /models` server gate (`olmocr/pipeline.py:929-953,
1287-1289`), mirrored by docling's `_run_bounded` (default max concurrency 8):
the mature pattern is "separate document parallelism from HTTP inflight, probe
the server before fan-out, keep N near the server knee."

## Flip conditions

- Sweep shows c=8 wall >= c=3 projection or retry/error rates superlinear in N:
  bottleneck is pod-side; stop client work, escalate to CTO.
- Twin pod probe returns 200: dual-pod shard jumps to the top of the queue.
- `--debug` probe shows median reasoning blocks >3000 chars: thinking-cap
  becomes the rank-1 per-call lever (10-18 s/call).

## Expected wall-time ladder (200 papers)

- today, c=3, one pod: 36 min (measured)
- c=8, one pod: ~9.4-13.5 min (degraded-ideal bracket)
- c=8 per pod, two pods: ~5-7 min
- + max-num-seqs raised to 16-32 and c matched: ~3-4 min
- + output/thinking trims and guided JSON: marginal further gains

---
Sources: self-target (packages/whisker + read-only pipeline), baseline
00-baseline.md, 2026-07-07. Web: 05a-05e (28 finding cards). Personas: 9
(11-19). Meta-review: performed inline by the orchestrating agent (claims
cross-checked against cli.py, adjudicate.py, runner.py, tasks.py,
model_backends.py, SERVICES.toml and the live pod probes recorded in 18).
