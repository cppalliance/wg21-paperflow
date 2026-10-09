# 19 - HTTP-Server-Limits-Auditor

**Verdict:** risky — vLLM 0.24's uvicorn/FastAPI front door accepts all 381 POSTs with no HTTP-level cap or 429/503 shedding; each becomes a long-lived asyncio task held silent until the engine responds, so the API layer survives connection count but amplifies idle-timeout failures on streaming clients.
**Confidence:** high (vLLM 0.24 CLI docs, uvicorn defaults, api_server source patterns, repo client code); medium on exact API-process RAM at 381×long-prompt without a live probe

## Findings

- [CRITICAL] **No HTTP-level concurrency cap in vLLM 0.24 `serve`; uvicorn `limit-concurrency` defaults to unlimited.** Evidence: v0.24.0 `serve` CLI docs (`https://docs.vllm.ai/en/v0.24.0/cli/serve/`) list `--max-num-seqs` and `--max-num-batched-tokens` under SchedulerConfig but no `--limit-concurrency`, `--max-waiting-queue-length`, or `--max-unfinished-requests`; closed PR #11997 (API max-concurrency) never merged; issue #15609 maintainer: "`--max_num_seqs` does not limit the number of concurrent requests that the API will accept"; uvicorn docs (`https://uvicorn.dev/settings/`, Resource Limits): `--limit-concurrency` default `None` = no 503 shedding. Impact: all 381 TCP connections are accepted and each spawns an in-flight handler task; rejection is not the failure mode at the HTTP layer.

- [CRITICAL] **`--max-num-batched-tokens` and `--max-num-seqs` are engine-scheduler knobs, not API connection limits.** Evidence: v0.24.0 serve docs SchedulerConfig (`--max-num-batched-tokens`: "tokens processed in a single iteration"; `--max-num-seqs`: "sequences in a single iteration"); issue #15609 distinction between engine parallelism and API acceptance. Impact: with `--max-num-seqs 16`, the HTTP server still holds 381 open connections while only 16 engine slots rotate; 365 connections sit idle at the API/uvicorn layer with zero response bytes.

- [HIGH] **Our client uses streaming (`stream=true`); queued requests are silent HTTP connections until first SSE chunk.** Evidence: `SERVICES.toml:64-74` (`stream = true` on `alliance-pod`); `services.py:187-199` passes `stream` kwarg to `VllmThinkingBackend`; `model_backends.py:244,306-328` calls `chat.completions.create(..., stream=True)` and `async for chunk in stream` (non-stream path at `330-340` only when `stream=false`). Impact: streaming does not emit keepalive bytes while waiting in queue — the connection is indistinguishable from a hung request to proxies and httpx read timers; only after vLLM schedules decode does the SSE stream start (`12-runpod-proxy.md:11`).

- [HIGH] **`VLLM_HTTP_TIMEOUT_KEEP_ALIVE` (default 5 s) is not an in-flight request timeout.** Evidence: `vllm/envs.py` (`VLLM_HTTP_TIMEOUT_KEEP_ALIVE: int = 5`); v0.24 api_server passes `timeout_keep_alive=envs.VLLM_HTTP_TIMEOUT_KEEP_ALIVE` to uvicorn (`https://github.com/vllm-project/vllm/blob/bebfe55b/vllm/entrypoints/openai/api_server.py`); PR #18472 rationale: keep-alive between requests on persistent connections, not streaming generation duration. Impact: vLLM will not close idle in-queue connections at 5 s; long-queue waits persist until client/proxy timeout or engine output.

- [HIGH] **`VLLM_ENGINE_ITERATION_TIMEOUT` is an internal engine-step watchdog, not a user-facing queue cap.** Evidence: `async_llm_engine.py` uses `VLLM_ENGINE_ITERATION_TIMEOUT_S` to abort if `engine_step()` hangs (NCCL/distributed failures); web synthesis and issue #18826 confirm it is unrelated to HTTP 429/503 shedding. Impact: 381 queued requests are not rejected or timed out by this env var; they remain open at the HTTP layer.

- [HIGH] **No 429 behavior at the API server; 503 only from optional caps not present in 0.24 defaults.** Evidence: issue #13395: "429 return code … is not implemented"; RFC #18826 / PR #27064 (`--max-waiting-queue-length` → HTTP 503 when scheduler queue full) — parameter absent from v0.24.0 serve CLI docs; PR #27064 still open/unmerged per issue #18826 (Apr 2026 comment). Impact: default 0.24 pod admits every POST with HTTP 200 acceptance path; overload surfaces as slow TTFT and downstream connection drops, not explicit rate-limit responses.

- [MED] **Uvicorn backlog 2048 and raised FD ulimit accommodate 381 connections; ZMQ ceiling is far higher.** Evidence: uvicorn default `--backlog 2048` (`https://uvicorn.dev/settings/`); vLLM api_server calls `set_ulimit()` before serving (issue #8204 footgun workaround); PR #7394: ZMQ `SOCKET_LIMIT` ≈ 65535 concurrent frontend↔engine sockets. Impact: 381 simultaneous connections should not hit kernel backlog or ZMQ hard caps; HTTP-layer "connection refused" is unlikely — the risk is sustained idle load, not accept-queue overflow.

- [MED] **API server tokenizes every request before engine handoff; burst tokenization is effectively serial.** Evidence: vLLM architecture docs (API server "performs input processing (tokenization)"); PR #10635: OpenAI server uses `ThreadPoolExecutor(max_workers=1)` for async tokenization to avoid GIL races; issue #19012: requests tokenized sequentially at API layer, then token IDs passed to engine. Impact: 381 simultaneous POSTs all pass HTTP accept immediately, but the last request may wait behind ~380 serial tokenizations (hundreds of ms each for multi-k-token tapetum prompts) before even entering the engine queue — API-layer latency stacked on engine FCFS wait.

- [MED] **Per-open-request memory at API process is prompt-sized text + handler state, not KV cache.** Evidence: vLLM architecture (tokenization in API server process; KV in engine); tapetum typical 5k–8.5k tokens (`10-vllm-scheduler.md`); 381 × ~30 KB text ≈ low tens of MB plus asyncio overhead. Impact: API-process OOM from connection count alone is unlikely at 381; unbounded waiting *engine* deque OOM (RFC #18826) is engine-side, but each HTTP handler still retains the parsed request body for the connection lifetime.

- [MED] **Client has no custom httpx timeout; default 600 s read applies to time-to-first-byte.** Evidence: `model_backends.py:283` (`AsyncOpenAI(base_url=..., api_key=...)` — no `timeout=` kwarg); `15-concurrency-safety.md:8` (default `Timeout(read=600)`). Impact: tail requests with ~700+ s queue wait (`10-vllm-scheduler.md:14`) hit `APITimeoutError` at the client while vLLM HTTP server still holds the connection — server does not proactively close.

- [LOW] **Non-streaming would behave identically while queued (silent connection) but buffer the full JSON body at release.** Evidence: `model_backends.py:329-340` non-stream path waits for complete `response.choices[0].message.content`; alliance-pod uses `stream=true`. Impact: if `stream` were disabled, queue-wait idle-timeout risk is the same or worse (no incremental bytes); memory spike at response delivery is higher for long thinking+JSON outputs.

## HTTP-layer behavior summary (381 concurrent POSTs)

| Layer | Default in vLLM 0.24 | At 381 connections |
|-------|----------------------|-------------------|
| TCP accept / backlog | uvicorn backlog 2048 | All 381 accepted |
| Active handler tasks | `limit-concurrency=None` (unlimited) | 381 concurrent asyncio tasks |
| HTTP 429 / 503 shedding | Not implemented / not configured | None; all admitted |
| In-flight idle timeout | None (keep-alive 5 s is between requests) | Connections held until engine emits output or client/proxy closes |
| Tokenization | Serial thread pool (max_workers=1) | ~380× serial delay before engine sees tail requests |
| Streaming vs non-streaming | Both hold connection; stream emits SSE only after scheduling | `stream=true` on alliance-pod; silent until first chunk |

## What would change my mind

1. **Live probe on alliance-pod v0.24** logging uvicorn active task count, time from POST accept to first SSE byte, and RSS of API process at 381 simultaneous `stream=true` POSTs — if all connections stay open with 0 resets and API RSS stays bounded, downgrade HTTP-layer verdict toward **safe**.

2. **Evidence that `--max-waiting-queue-length` or `--max-unfinished-requests` is enabled on the deployed pod** (would cause HTTP 503 rejection once cap hit, flipping failure mode from idle-timeout to explicit shed — **breaks** for c=381 burst, but confirms HTTP-layer rejection exists).

3. **vLLM 0.24 release notes or pod template showing `--limit-concurrency` wired into uvicorn** — would cap active handlers and return 503 above N, making 381-at-once **breaks** at the HTTP layer rather than risky idle hold.

4. **Confirmation that vLLM emits an immediate HTTP 200 + SSE comment/heartbeat on accept before engine scheduling** — would extend safe idle window for proxy layers; not documented in OpenAI-compat server or observed in repo.
