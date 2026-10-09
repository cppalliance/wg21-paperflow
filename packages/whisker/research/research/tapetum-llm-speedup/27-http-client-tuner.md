# 27 - HTTP-Client-Tuner

**Verdict:** garbage — HTTP transport is not throttling the cold fleet at c=32; pool caps are 1000/100 vs ≤32 live connections, and per-call TLS churn saves at most ~10–30 s on a 3003 s run, not the 40+ min gap to 5–10 min.
**Confidence:** high

## Findings

- [CRITICAL] **At most 32 simultaneous HTTP connections; no pool-cap throttling.** Evidence: `_DEFAULT_CONCURRENCY = 32` with `asyncio.Semaphore(concurrency)` wrapping the full per-paper chain (`cli.py:127`, `cli.py:1097-1112`, `cli.py:1120`); within one paper all judge calls are serial (`00-baseline.md:36-38`, `pdf_judge.py:753`, `unit_judge.py:389`). OpenAI SDK default `httpx.Limits(max_connections=1000, max_keepalive_connections=100)` (runtime probe 2026-07-23 on `openai==2.34.0`). Impact: **≈0 s** from raising pool limits; the 381-at-once catastrophe was **365 idle queued connections**, not a sub-32 pool cap (`cli.py:130-131`, `research/concurrency-381/12-runpod-proxy.md:13`).

- [CRITICAL] **`AsyncOpenAI` is constructed per call, not per backend — no TLS/keep-alive reuse across the ~2284-call cold run.** Evidence: `client = AsyncOpenAI(base_url=..., api_key=...)` inside every `ModelBackend.run()` entry (`model_backends.py:283`, and tool paths `:443`, `:535`, `:627`); no `await client.close()`. `load_services()` builds one long-lived `VllmThinkingBackend` per service (`services.py:200`), and the CLI reuses one `AgentBackend` per batch (`cli.py:994-1036`), but each `agent.run()` still mints a fresh httpx pool. Prior audit: 381 independent pools at burst (`research/concurrency-381/11-client-timeouts.md:18`). Impact: ~2284 TLS handshakes × ~100–150 ms ≈ **10–30 s fleet wall** (order **0.3–1%** of 3003 s) if a shared client were added; **not** minutes.

- [HIGH] **`stream=true` from SERVICES.toml is active on every tapetum judge call and does not shorten decode.** Evidence: `[services.alliance-pod] stream = true` (`SERVICES.toml:74`); forwarded via `services.py:197-199` into `VllmThinkingBackend.__init__(stream=...)` (`model_backends.py:244-252`); non-tool path uses `stream=True` and accumulates all chunks before JSON parse (`model_backends.py:306-328`). Comment at `services.py:187` cites Cloudflare/proxy motivation. Decode is server-bound ~70 tok/s (`00-baseline.md:26-28`); streaming vs buffered completion does not change token generation time. Impact: toggling `stream=false` saves **≈0–5 s** (chunk-loop overhead only); disabling streaming **hurts** proxy TTFT safety under deep queues (`research/concurrency-381/12-runpod-proxy.md:11`) with **no decode win**.

- [HIGH] **HTTP/2 is off; enabling it is unverified on RunPod proxy and unlikely to help this workload.** Evidence: `httpx.AsyncClient` default `http2=False` (runtime probe 2026-07-23); `AsyncOpenAI(...)` passes no `http2=` override (`model_backends.py:283`). Endpoint is `https://*.proxy.runpod.net/v1` (`SERVICES.toml:66`). Cloudflare-terminated HTTPS proxy path; no repo evidence of HTTP/2 support on that hop. Impact: **≈0 s** measured saving; speculative multiplexing gain is moot when ≤32 concurrent POSTs each hold one connection for ~20 s.

- [MED] **RunPod proxy ~100 s origin-response ceiling is irrelevant at c=32, lethal above ~32 idle queued connections.** Evidence: `cli.py:130-131` documents c=381 → 257/381 proxy-killed connections (2026-07-08); c=32 validated on 381-paper corpus (`cli.py:125-126`). Proxy kills connections with no response bytes for ~100 s (`research/concurrency-381/12-runpod-proxy.md:9-11`). At c=32 with `--max-num-seqs 16`, queue depth stays ~1–2 min max on measured runs (`00-baseline.md:24-25`, `research/concurrency-381/11-client-timeouts.md:16`). Impact: **0 s saving** from HTTP tuning at current concurrency; raising client concurrency without TCP/direct bypass remains a **reliability break**, not a speed lever.

- [MED] **SDK read timeout 600 s and connect 5 s are defaults; not the cold-run bottleneck.** Evidence: no `timeout=` on `AsyncOpenAI(...)` (`model_backends.py:283`); SDK `Timeout(connect=5.0, read=600, write=600, pool=600)` (runtime probe); `_PAPER_TIMEOUT_SECONDS = 900.0` outer guard (`cli.py:138`). Cold run: 55 retries, 6 errors, no timeout tombstone pattern (`00-baseline.md:17-18,60-61`). Impact: lowering read timeout saves **≈0 s** on happy path; only tail-hang papers (`26-timeout-budget-auditor.md:8-12`).

- [LOW] **Whisker-local HTTP paths mirror the same per-call-client pattern outside the hot judge path.** Evidence: health probe uses ephemeral `async with httpx.AsyncClient(...)` (`cli.py:938-940`); readback reuses one sync `httpx.Client` per paper (`readback.py:337-344`); dormant VLM lane creates per-call `AsyncOpenAI` (`vision_task.py:125`). Impact: **≈0 s** on 3003 s cold run (readback/VLM not in fleet path).

## False-pass hypothesis

Switching `stream=false` to shave client overhead during a future concurrency experiment (>32): tail papers sit in vLLM queue without SSE bytes, RunPod proxy closes idle connections at ~100 s (`research/concurrency-381/12-runpod-proxy.md:11`), retries succeed on lighter load, and the fleet finishes faster with **fewer completed judgments** — operators see green wall time while ~N papers land in `error` tombstones (`cli.py:1382-1387`) with no sidecar.

## False-fail hypothesis

Shared `AsyncOpenAI` on `ModelBackend` with aggressive `keepalive_expiry=5.0` (SDK default, runtime probe): after a 120 s unit-check stall, the proxy half-closes the idle socket; the next serial call on the same paper reuses a dead connection → `APIConnectionError` → backend retry (`model_backends.py:341-350`) adds 2–4 s and can fail-closed a paper chain that a fresh per-call client would have survived — infrastructure false-fail, not conversion defect.

## What would change my mind

`whisker-tapetum-llm` cold run with debug timestamps showing **≥5% of per-call wall** in connect/TLS (not queue/decode) on the alliance-pod proxy at c=32 — e.g. median TTFT minus vLLM-reported queue time >500 ms — would upgrade shared-client reuse from ~10–30 s hygiene to a schedulable minute-level lever worth a `packages/pipeline/` change.
