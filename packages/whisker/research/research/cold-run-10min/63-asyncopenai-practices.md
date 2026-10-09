# 63 - AsyncOpenAI / httpx practices (c=32, long vLLM via RunPod proxy)

**Verdict:** **REJECT as noise** — no AsyncOpenAI/httpx knob clears the **>30 s fleet wall** bar for the cold tapetum run at c=32 behind `*.proxy.runpod.net`. Best practices that matter elsewhere (pool sizing, HTTP/2, Expect:100-continue) are either already satisfied by SDK defaults, unavailable in httpx, or save **≈0–17 s** of TLS hygiene while decode/queue dominate.
**Confidence:** high
**Date:** 2026-07-24

Barrier: tip must save **>30 s** fleet wall (or reject). Prior envelopes: persona 27 / revisit 27 (`research/tapetum-llm-speedup/27-http-client-tuner.md`, `27-http-tuning-revisit.md`); proxy constraints in `05f-web-runpod-proxy.md`.

---

## Workload anchors (this repo)

| Fact | Evidence |
|------|----------|
| ≤32 in-flight papers | `_DEFAULT_CONCURRENCY = 32`, paper semaphore (`whisker/.../cli.py`) |
| Fresh `AsyncOpenAI` per LLM call | `VllmThinkingBackend.run` and tool paths (`model_backends.py:283`, `:443`, `:535`, `:627`) |
| SDK pool defaults already huge | OpenAI `DEFAULT_CONNECTION_LIMITS`: **1000** max / **100** keepalive; timeout **600 s** read / **5 s** connect |
| `stream = true` on alliance-pod | `SERVICES.toml`; proxy TTFT safety |
| Post-v11 call count down | Metadata short-circuit cuts TLS ceiling to ~**5–17 s** (revisit 27) |

At c=32, live connections ≪ pool caps. Bottleneck is **vLLM decode + queue**, not client pool starvation.

---

## Tip triage (web practices × fleet savings)

### 1. Reuse one `AsyncOpenAI` / `httpx.AsyncClient` (connection pooling)

**Web:** httpx docs: do not instantiate clients in a hot loop; one scoped client enables TCP/TLS reuse. OpenAI docs: pass `DefaultAsyncHttpxClient(limits=...)` when customizing.

**Local:** Every judge call mints a new client → no keepalive across ~1k+ calls. Shared client on `ModelBackend` is the textbook fix.

| Envelope | Wall |
|----------|------|
| Pre-v11 (~2284 TLS × ~100–150 ms) | ~**10–30 s** |
| Post-v11 (~1260 calls) | ~**5–17 s** |

**>30 s?** **No** (ceiling touches 30 s only on optimistic pre-v11 TLS; post-v11 clearly under). Pipeline package change for sub-minute hygiene.
**Disposition:** **noise** for this barrier (hygiene OK later; not a cold-run lever).

---

### 2. Raise `httpx.Limits(max_connections, max_keepalive_connections)`

**Web:** Baseten / OpenAI issues recommend raising limits when hitting `PoolTimeout` at hundreds of concurrent short requests. Raw httpx defaults are 100/20; **OpenAI SDK already uses 1000/100**.

**Local:** Peak concurrency 32 ≪ 1000. No `PoolTimeout` pattern in cold-run failure modes.

**>30 s?** **≈0 s**
**Disposition:** **noise**

---

### 3. Enable HTTP/2 (`httpx[http2]`, `http2=True`)

**Web:** OpenAI issue #2726: multiplexing helps high-QPS short requests; SDK maintainers say pass custom httpx client (`http1=False, http2=True`). Falls back to HTTP/1.1 if proxy lacks H2.

**Local:** ≤32 **long-lived** streamed POSTs (tens of seconds each). Multiplexing gains show up when many short RPCs share one connection; here each request occupies a connection for decode duration. RunPod path is Cloudflare-terminated; H2 support unverified. Risk: new failure modes for zero measured win.

**>30 s?** **≈0 s** (speculative; no measurement)
**Disposition:** **noise** (do not schedule)

---

### 4. `Expect: 100-continue`

**Web:** httpx maintainers (discussion #1713): **no** body-delay 100-continue support (same as `requests`). Irrelevant for OpenAI-compatible chat completions.

**>30 s?** **N/A / 0 s**
**Disposition:** **noise** (not implementable; not a lever)

---

### 5. Tune `keepalive_expiry` (httpx default 5 s)

**Web:** Keepalive expiry below proxy idle close avoids dead sockets on reuse. Baseten suggests ~30 s when server keeps 60–120 s.

**Local:** Only bites with a **shared** client. Aggressive keepalive + long unit stalls can yield `APIConnectionError` → retry (revisit 27 false-fail). Fresh per-call clients sidestep reuse bugs at the cost of TLS (still &lt;30 s).

**>30 s?** **No** (reliability knob, not wall saver)
**Disposition:** **noise** for wall; if shared client lands later, set expiry deliberately vs RunPod/CF idle behavior

---

### 6. Keep `stream=true`; do not buffer full completion through proxy

**Web / RunPod:** Proxy guide + expose-ports: ~**100 s** to first response byte or **HTTP 524**. Streaming within 100 s is required; silent non-stream waits die. Cloudflare proxy read timeout ~100–125 s.

**Local:** Already `stream = true`. Disabling stream does **not** shorten decode; under deep queue it **increases** 524 risk (persona 27 false-pass).

**>30 s?** **≈0 s** savings from toggling; **keeping stream is mandatory** for reliability, not a speed tip.
**Disposition:** **noise as speed lever**; **do not disable**

---

### 7. Lengthen client read timeout / pool timeout

**Web:** httpx: `read` timeout is per chunk idle for streams; OpenAI default 600 s. Long generations need large read timeouts.

**Local:** Defaults already 600 s; outer paper guard 900 s. Cold-run pain is CF **524 before first byte**, which **client timeouts cannot fix**. Raising read further: **0 s** happy path.

**>30 s?** **≈0 s**
**Disposition:** **noise**

---

### 8. Match client concurrency to `--max-num-seqs` (admission, not httpx)

**Web / ops:** Flooding concurrent POSTs past server slots → silent queue → TTFT >100 s → 524. Not an httpx pool setting.

**Local:** c=32 validated; c≫32 / submit-all forbidden (`00-baseline.md`, `05f`). Binding fan-out to server slots prevents **failures**, not a new &gt;30 s speedup vs current c=32.

**>30 s?** Does not unlock a new HTTP win at current c; forbidding higher c avoids **losing** papers.
**Disposition:** **constraint**, not a new tip (already settled)

---

## Canonical “good” client (for documentation only)

If/when pipeline shares a client (hygiene, not cold-run ranking):

```python
import httpx
from openai import AsyncOpenAI, DefaultAsyncHttpxClient

client = AsyncOpenAI(
    base_url=...,
    api_key=...,
    http_client=DefaultAsyncHttpxClient(
        # retain SDK 1000/100 unless PoolTimeout appears
        limits=httpx.Limits(
            max_connections=1000,
            max_keepalive_connections=100,
            keepalive_expiry=30.0,  # only if measuring dead-socket retries
        ),
        http2=False,  # leave off until proxy H2 proven
        timeout=httpx.Timeout(600.0, connect=5.0),
    ),
)
# reuse across calls; await client.close() on shutdown
```

Expected fleet delta at c=32: **~5–17 s**, still **under the &gt;30 s bar**.

---

## False-pass / false-fail

- **False-pass:** Attribute a few-second wall drop to “HTTP/2 + pool tuning” and defer metadata/APC/dual-pod; gap to 10 min still ~tens of minutes.
- **False-fail:** Shared client + short keepalive → mid-stall dead sockets → retries / incomplete sidecars attributed to “model flakiness.”

## What would clear &gt;30 s

1. Measured median connect+TLS **>500 ms** per call with call count high enough that product **>30 s** fleet wall, **or**
2. Leave RunPod HTTPS proxy for TCP/direct and prove connect share is material.

Neither is evidenced at HEAD.

---

## Bottom line

| Practice | Fleet Δ | Verdict |
|----------|---------|---------|
| Shared `AsyncOpenAI` | ~5–17 s (post-v11) | **reject (&lt;30 s)** |
| Raise pool limits | ~0 s | **reject** |
| HTTP/2 | ~0 s unverified | **reject** |
| Expect:100-continue | N/A | **reject** |
| keepalive_expiry | reliability only | **reject** |
| stream on/off | 0 s / anti-pattern off | **reject as speed tip** |
| Longer client timeouts | ~0 s | **reject** |

**Return to parent:** **no tip worth &gt;30 s — reject AsyncOpenAI/httpx tuning as noise** for the cold-run-10min goal. Keep `stream=true`; keep c≤ server/proxy safe; do not schedule pool/H2/expect100 work.

## Sources

1. https://www.python-httpx.org/async/
2. https://www.python-httpx.org/advanced/resource-limits/
3. https://www.python-httpx.org/advanced/timeouts/
4. https://github.com/openai/openai-python/issues/2726
5. https://github.com/encode/httpx/discussions/1713
6. https://docs.baseten.co/inference/http-client-configuration
7. https://www.runpod.io/blog/runpod-proxy-guide
8. https://docs.runpod.io/pods/configuration/expose-ports
9. Local: `27-http-client-tuner.md`, `27-http-tuning-revisit.md`, `05f-web-runpod-proxy.md`, `model_backends.py`
