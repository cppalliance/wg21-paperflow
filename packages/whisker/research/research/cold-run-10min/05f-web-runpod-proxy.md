# 05f - Web forage: RunPod proxy timeouts / streaming / concurrency

Research date: 2026-07-24. Path under study: Pod HTTP proxy
(`*.proxy.runpod.net`) used by `alliance-pod` and sibling pods in
`SERVICES.toml`. Also notes Serverless `/openai/*` limits for contrast.

Prior deep audit (do not rediscover): `research/concurrency-381/12-runpod-proxy.md`
(2026-07-08). This card refreshes primary docs and extracts **constraints that
forbid hundreds-of-concurrent HTTP submissions** through the pod proxy.

---

## Finding: RunPod expose-ports — 100 s proxy → HTTP 524

**URL:** https://docs.runpod.io/pods/configuration/expose-ports

**Summary:** Pod HTTP exposure path is `User → Cloudflare → RunPod Load Balancer
→ Pod`. Documented limitation: **Cloudflare enforces a maximum connection time
of 100 seconds**. If the service does not respond within that window, the
connection closes with a **`524`**. Docs explicitly recommend TCP for
long-running connections / WebSockets, and troubleshooting says: for 524s,
"consider using TCP or restructuring your application for faster responses."
HTTP ports max 10 (port count, not connection count). HTTPS-only on the proxy.

**Relevance:** CRITICAL

---

## Finding: RunPod proxy guide — first-byte / streaming gate

**URL:** https://www.runpod.io/blog/runpod-proxy-guide  
(Published 2024-11-13; `dateModified` 2026-06-10)

**Summary:** Cloudflare timeout is **~100 seconds if the connection is not kept
alive**. Non-streaming waits that take >100 s to fulfill time out. Explicit
LLM guidance: *"If the request starts streaming within 100 seconds that is
fine, but if it doesn't even start the initial stream by then, nothing will be
received at all as the connection will be closed."* Bypass: switch exposed
ports from HTTP to **TCP**, read public IP + mapped external port from Connect
→ TCP Port Mapping (external port is random and changes on reset; cannot expose
same port as both HTTP and TCP).

**Relevance:** CRITICAL

---

## Finding: Cloudflare Error 524 — Proxy Read Timeout

**URL:** https://developers.cloudflare.com/support/troubleshooting/http-status-codes/cloudflare-5xx-errors/error-524/

**Summary:** `524` = Cloudflare connected to origin, but origin did not provide
an HTTP response before **Proxy Read Timeout** (Cloudflare default **125 s**;
RunPod docs/community consistently cite **~100 s** for the pod proxy path).
Also: Proxy Write Timeout **30 s** (non-configurable) for incomplete writes.
Enterprise can raise read timeout to 6000 s — **not available to RunPod pod
tenants** (you do not own the Cloudflare zone). Recommended origin pattern:
kick off work and **poll**, do not hold a silent HTTP response.

**Relevance:** CRITICAL

---

## Finding: Cloudflare connection-limits table (read vs idle)

**URL:** https://developers.cloudflare.com/fundamentals/reference/connection-limits/

**Summary:** CF↔origin **Proxy Read Timeout 125 s → 524**; **Proxy Idle Timeout
900 s → 520**; client↔CF keep-alive/idle **400 s**. Read timeout is the first
response / continued read watchdog; idle timeout is longer. Practical effect
for vLLM: the dangerous window is **time-to-first-byte (TTFT)** including
scheduler queue wait with **zero SSE bytes**. After bytes flow, total decode
can exceed 100 s. If generation pauses >~100–125 s with no bytes (long
"thinking" gaps without keepalive comments), 524 can still fire mid-stream
(community SSE keepalive pattern: `: keep-alive` comments every ~15–30 s).

**Relevance:** HIGH

---

## Finding: Discord / AnswerOverflow — 524 is expected >100 s; switch HTTP→TCP

**URL:** https://www.answeroverflow.com/m/1270658283371237458  
**URL:** https://www.answeroverflow.com/m/1244694140407775317

**Summary:** RunPod staff/community: `*.proxy.runpod.net` 524 is **normal** when
request takes >100 s; Cloudflare timeout cannot be raised on pods. Fix for
pods: expose port as **TCP** instead of HTTP. Separate thread: no pod setting
to increase the 100 s timeout; serverless suggested for long jobs that need
native long-running job handling.

**Relevance:** HIGH

---

## Finding: Serverless rate limits — `/openai/*` 400 concurrent (different path)

**URL:** https://docs.runpod.io/serverless/endpoints/send-requests

**Summary:** Queue-based / OpenAI-compat Serverless endpoints enforce per-op
limits. `/openai/*` POST: **2000 req / 10 s**, **400 concurrent** (base).
Dynamic: `max(base, running_workers × requests_per_worker)`. Excess → `429`.
`/runsync` also 400 concurrent; `/run` 200 concurrent. Default
`executionTimeout` 600 s (10 min), TTL 24 h; long jobs use `/run` + `/status`
or raise policy timeouts (max 7 days). **This is not the Pod HTTP proxy path.**
`alliance-pod` uses `https://…proxy.runpod.net/v1` (pod), so the **100 s
first-byte** constraint dominates over the 400 concurrent Serverless cap.

**Relevance:** MED (contrast; forbids flood only on Serverless OpenAI path)

---

## Finding: Serverless vLLM OpenAI compatibility — stream + client timeout

**URL:** https://docs.runpod.io/serverless/vllm/openai-compatibility  
**URL:** https://docs.runpod.io/serverless/vllm/environment-variables

**Summary:** Base URL `https://api.runpod.ai/v2/ENDPOINT_ID/openai/v1`. Streaming
supported (`stream=True`). Troubleshooting: "Timeout errors → Increase client
timeout for large models." Worker env `MAX_CONCURRENCY` default **30** (RunPod
worker admission, not vLLM `--max-num-seqs`). `MAX_NUM_SEQS` default 256 on
worker-vllm. Rate limits "follow Runpod's policies." Useful for long jobs via
async `/run` queue, **not** a license to open hundreds of silent pod-proxy
connections.

**Relevance:** MED

---

## Finding: vLLM RunPod deploy — bind 0.0.0.0; 502 ≠ 524

**URL:** https://docs.vllm.ai/en/stable/deployment/frameworks/runpod/

**Summary:** Serve with `--host 0.0.0.0`; expose HTTP port →
`https://<pod-id>-8000.proxy.runpod.net`. **502** means origin not listening
(model loading, wrong bind, port mismatch, OOM). Distinct from **524** (origin
alive but no timely response bytes). Does not document concurrent connection
caps on the proxy.

**Relevance:** MED

---

## Finding: Tricks for long-running completions (ranked)

| Trick | Mechanism | Pod proxy? | Notes |
|-------|-----------|------------|-------|
| **Keep client in-flight ≤ server slots** | TTFT ≈ decode time of head-of-line, not deep FCFS wait | Required on HTTP proxy | With `--max-num-seqs 16`, c≫16 → queue wait >>100 s → 524 |
| **`stream=true` from first token** | Satisfies "start streaming within 100 s" | Helps only if scheduled before 100 s | `SERVICES.toml` already `stream = true` on alliance-pod |
| **SSE keepalive comments** | Bytes during thinking gaps | Helps mid-stream idle | Needs proxy/server support; stock vLLM may not emit `: keepalive` while thinking |
| **HTTP → TCP expose** | Bypass Cloudflare 100 s | Escapes 524 | Random external port; no auto TLS; update `base_url` |
| **Async job + poll** | Return fast, poll status | Serverless native (`/run`+`/status`) | Not available as Batch API on stock vLLM OpenAI server |
| **Raise client read timeout** | Avoid client-side abort after first byte | Orthogonal | Does **not** stop Cloudflare 524 before first byte |
| **Serverless executionTimeout / TTL** | Up to 7 days | N/A for pods | Only on `api.runpod.ai` job APIs |

**Relevance:** HIGH

---

## Constraints that forbid submitting hundreds of concurrent requests

These are the hard "do not open c≈100–400 simultaneous completions" constraints
for our stack (`SERVICES.toml` pod proxy + vLLM OpenAI `/v1/chat/completions`):

1. **[FORBID] Pod proxy TTFT ≤ ~100 s (first response byte).**  
   RunPod expose-ports + proxy guide: no stream start within ~100 s → **HTTP
   524**. Hundreds of concurrent POSTs against `--max-num-seqs 16` leave
   ~hundreds of accepted connections with **zero SSE bytes** until scheduled.
   Queue wait for the tail easily exceeds 100 s (prior concurrency-381
   projection: multi-minute idle). Streaming flag does **not** help while still
   queued.

2. **[FORBID] Deep idle queue behind Cloudflare.**  
   Cloudflare Proxy Read Timeout (~100–125 s) kills silent origins. Mass
   fan-out maximizes silent-queue population. Bounded fan-out (c≈ server slots,
   repo baseline c=16/32) keeps TTFT under the gate; submit-all-papers does not.

3. **[FORBID] Relying on raising the Cloudflare timeout.**  
   Pod tenants cannot edit `proxy_read_timeout` on RunPod's zone. Enterprise CF
   knobs are irrelevant. Official pod escape is **TCP expose**, not "just send
   more concurrent requests."

4. **[FORBID] Treating Serverless `400 concurrent /openai/*` as pod headroom.**  
   That limit is for `api.runpod.ai` Serverless. Pods have **no published
   concurrent-connection allowance** that would make c=381 safe; the published
   limit that bites first is **100 s first-byte**, not 400.

5. **[FORBID] Assuming client 600 s read timeouts protect the proxy path.**  
   Client timeouts only apply after bytes flow (or on total wait). Cloudflare
   cuts first; client never sees a successful stream for the killed request.

6. **[SOFT FORBID] Hundreds of parallel TLS sessions through the proxy.**  
   No RunPod-documented hard FD/connection cap found; operational risk
   (resets / 502 under FD pressure) is secondary to 524 but still argues against
   mass open-all connections.

**Operational rule (feeds `00-baseline.md` constraint):** do **not** raise
client concurrency into the "hundreds of in-flight completions" regime on
`*.proxy.runpod.net` without either (a) TCP/direct path with measured proof, or
(b) evidence that TTFT for every request stays &lt;100 s (i.e. effective queue
depth stays near `--max-num-seqs`). Prior corpus already marks
`c>32 / submit-all-381` as forbidden for proxy 524 / timeout risk.

---

## Local anchors

- `SERVICES.toml` `[services.alliance-pod]`: `base_url = …proxy.runpod.net/v1`,
  `stream = true`
- `research/concurrency-381/12-runpod-proxy.md` — full 381-at-once failure
  prediction
- `research/cold-run-10min/00-baseline.md:28` — `c>32 / submit-all-381` forbidden

---

## Sources (unique)

1. https://docs.runpod.io/pods/configuration/expose-ports
2. https://www.runpod.io/blog/runpod-proxy-guide
3. https://developers.cloudflare.com/support/troubleshooting/http-status-codes/cloudflare-5xx-errors/error-524/
4. https://developers.cloudflare.com/fundamentals/reference/connection-limits/
5. https://docs.runpod.io/serverless/endpoints/send-requests
6. https://docs.runpod.io/serverless/vllm/openai-compatibility
7. https://docs.runpod.io/serverless/vllm/environment-variables
8. https://docs.vllm.ai/en/stable/deployment/frameworks/runpod/
9. https://www.answeroverflow.com/m/1270658283371237458
10. https://www.answeroverflow.com/m/1244694140407775317
11. https://github.com/runpod/runpod-plugins-official/blob/main/plugins/runpod/skills/runpod-usage/reference/networking.md
