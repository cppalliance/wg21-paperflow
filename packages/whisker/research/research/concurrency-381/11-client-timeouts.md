# 11 - Client-Timeout-Auditor

**Verdict:** breaks — default 600 s httpx read timeout fires on tail-queued requests before the server emits the first byte, and the 900 s paper wrapper cancels before SDK+backend retries recover.
**Confidence:** high

## Findings

- [CRITICAL] **OpenAI SDK default read timeout is 600 s (10 min), connect is 5 s.** Evidence: installed `openai==2.34.0`, `.venv/Lib/site-packages/openai/_constants.py:8-9` → `DEFAULT_TIMEOUT = httpx.Timeout(timeout=600, connect=5.0)`; runtime `as_dict()` → `{connect: 5.0, read: 600, write: 600, pool: 600}`. `VllmThinkingBackend.run` constructs `AsyncOpenAI(base_url=..., api_key=...)` with no `timeout=` override (`packages/pipeline/src/pipeline/model_backends.py:283`). Impact: any request held in the vLLM FCFS queue without a response byte for >600 s raises `httpx.TimeoutException` → `openai.APITimeoutError`.

- [CRITICAL] **SDK retries timeouts up to 2 times (3 total attempts), each with a fresh 600 s read budget.** Evidence: `openai/_constants.py:10` → `DEFAULT_MAX_RETRIES = 2`; `openai/_base_client.py:1017` → `for retries_taken in range(max_retries + 1)`; `1653-1666` → `except httpx.TimeoutException` retries when `remaining_retries > 0`, else `raise APITimeoutError(request=request) from err`; backoff `INITIAL_RETRY_DELAY=0.5`, `MAX_RETRY_DELAY=8.0` (`_constants.py:13-14`, `_base_client.py:788`). Impact: a single `chat.completions.create` can burn ~1800 s + backoff before surfacing `APITimeoutError`, but each retry re-enters the server queue at the tail — it does not preserve FCFS position.

- [CRITICAL] **Backend catches `APITimeoutError` but only 2 attempts, with short backoff.** Evidence: `model_backends.py:341-351` → transient tuple includes `openai.APITimeoutError`; `max_attempts = min(2, request_limit)` (`:300`); backoff `delay = 2 ** (attempt + 1)` → 2 s then 4 s. Impact: after SDK exhausts 3 tries, backend retries once; total theoretical budget is large, but each SDK retry re-queues behind 365 other waiting connections, so recovery is unlikely for tail papers.

- [CRITICAL] **Paper-level `asyncio.wait_for(..., timeout=900)` fires before deep retry stacks complete.** Evidence: `packages/whisker/src/whisker/tapetum_llm/cli.py:76` → `_PAPER_TIMEOUT_SECONDS = 900.0`; `:722-727` and `:763-772` wrap judge/adjudicate calls. Comment at `:74-75` explicitly names the 600 s AsyncOpenAI read timeout. Impact: at c=381, a tail paper queued ~630+ s hits read timeout at 600 s; SDK retry starts a new 600 s wait; `wait_for` cancels the whole coroutine at 900 s with `asyncio.TimeoutError` (not caught by backend transient list) → CLI `except Exception` → `counts["error"] += 1` (`cli.py:796-823`).

- [HIGH] **Tail queue wait at c=381 exceeds 600 s for ~60 papers.** Evidence: measured baseline 381 papers at c=16 in 722.4 s, 0 errors; server `--max-num-seqs 16` (`cli.py:59-60`, `H200SXM.txt`); mean service ~30 s/call (722.4/381 × 16/16 ≈ 1.9 s effective per-paper wall, saturated 16-wide → ~30 s active). FCFS queue position *i* waits ≈ `floor((i-1)/16) × 30 s` before first prefill. Paper 321: `floor(320/16)×30 = 600 s` (boundary); paper 381: `floor(380/16)×30 = 720 s`. Impact: papers ~321–381 (~15% of corpus) predict `APITimeoutError` or `asyncio.TimeoutError` under burst; c=16 kept queue shallow so none exceeded 600 s (measured 0 errors).

- [MED] **Per-call fresh `AsyncOpenAI` → 381 independent httpx pools, not one shared pool.** Evidence: `model_backends.py:283` (and `:443`, `:535`, `:627`) each `client = AsyncOpenAI(...)` inside `run()`; `openai/_base_client.py:1421-1426` → `_DefaultAsyncHttpxClient` sets `limits=DEFAULT_CONNECTION_LIMITS`; `_constants.py:11` → `httpx.Limits(max_connections=1000, max_keepalive_connections=100)`. Impact: pool `max_connections=1000` is irrelevant per client (1 active request each); real cost is **381 simultaneous TCP+TLS sockets**, 381 TLS handshakes at burst, 381 `AsyncHttpxClientWrapper` instances with `__del__`→`aclose()` cleanup (`_base_client.py:1464-1472`) — no explicit `await client.close()` in our code. Connect failures within 5 s surface as `APIConnectionError` (also in transient list, `:341-342`).

- [LOW] **Windows ephemeral ports are not the bottleneck at 381.** Evidence: `netsh int ipv4 show dynamicport tcp` on this host → start 49152, count 16384 (range 49152–65535); 381 outbound connections to one remote host consume ~2.3% of ephemeral ports. Impact: port exhaustion and `TIME_WAIT` accumulation are not predicted at N=381; they become relevant at multi-thousand concurrent outbound connections or rapid connect/disconnect churn, not this scenario.

- [LOW] **httpx `pool` timeout also defaults to 600 s but is moot for one-request-per-client.** Evidence: `DEFAULT_TIMEOUT.as_dict()` → `pool: 600`. Impact: `pool` timeout governs waiting to acquire a connection from the pool; with one in-flight request per client the read timeout dominates.

## Predicted failure mode at c=381

1. `asyncio.gather` launches 381 `_adjudicate_one` workers; with `--concurrency 381` the semaphore admits all immediately (`cli.py:673-814`).
2. Each paper calls `VllmThinkingBackend.run` → fresh `AsyncOpenAI` → POST to vLLM; server admits all into unbounded FCFS queue, schedules 16.
3. Papers 1–~320: queue wait <600 s, response arrives within read timeout → success (same as c=16 throughput, ~730–800 s wall).
4. Papers ~321–381: HTTP connection open, no response bytes for >600 s → `httpx.ReadTimeout` → SDK retries (re-queues) → at 900 s `asyncio.wait_for` cancels → `asyncio.TimeoutError` logged as `Failed to adjudicate ... TimeoutError` → `error` count ~15% of corpus.
5. Secondary mode: early burst of 381 TLS handshakes; any connect >5 s → `APIConnectionError` → SDK retry (2×) → backend retry (1×) → same paper error bucket if unrecovered.

Exception chain for read-timeout path: `httpx.ReadTimeout` (subclass of `httpx.TimeoutException`) → SDK `APITimeoutError` (`openai/_exceptions.py:112`, subclasses `APIConnectionError`) → optionally backend retry → ultimately `asyncio.TimeoutError` from CLI wrapper.

## What would change my mind

- A live `whisker-tapetum-llm --review-all --concurrency 381` on the same 381-PID corpus with **0 errors** and wall within 5% of 722.4 s would flip to **safe** (empirical proof tail papers complete within 600 s read budget, e.g. if mean service time is much lower than 30 s or queue drains faster than FCFS model predicts).
- Passing `timeout=httpx.Timeout(connect=5.0, read=1800.0)` (or `read=None`) to `AsyncOpenAI` in `model_backends.py` **and** raising `_PAPER_TIMEOUT_SECONDS` above worst-case queue depth would flip to **risky** (timeouts deferred, but 365 idle connections for 30+ min remain).
- Enabling vLLM `--max-waiting-queue-length N` with 503 rejection would make c=381 **breaks** differently (mass HTTP 503, not timeout) — a separate failure class.
