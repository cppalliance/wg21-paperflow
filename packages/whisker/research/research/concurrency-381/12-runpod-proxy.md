# 12 - RunPod-Proxy-Auditor

**Verdict:** breaks — RunPod's HTTP proxy enforces a documented ~100 s Cloudflare origin-response ceiling; the 381-at-once plan holds hundreds of idle streaming connections open for projected queue depths up to ~12 min, which exceeds that limit before vLLM emits the first stream byte.

**Confidence:** high (official RunPod docs + blog, fetched 2026-07-08); medium on exact failure rate at 381 simultaneous connections (no RunPod-published concurrent-connection cap; today's measured run used c=16, not 381).

## Findings

- [CRITICAL] **HTTP proxy has a hard ~100 s origin-response timeout → HTTP 524.** Evidence: [RunPod expose-ports docs](https://docs.runpod.io/pods/configuration/expose-ports) ("100-second timeout: Cloudflare enforces a maximum connection time of 100 seconds… closes with a `524` error"); [RunPod proxy guide](https://www.runpod.io/blog/runpod-proxy-guide) (Nov 2024 blog, schema `datePublished` 2026-06-10: "approximately 100 seconds if the connection is not kept alive… If the request starts streaming within 100 seconds that is fine, but if it doesn't even start the initial stream by then, nothing will be received"). Impact: any request whose **time-to-first-byte** (including vLLM queue wait before decode starts) exceeds ~100 s through `*.proxy.runpod.net` should be cut with 524, regardless of client `AsyncOpenAI` read timeout (600 s per `15-concurrency-safety.md:8`).

- [CRITICAL] **Streaming does not bypass the limit while queued in vLLM.** Evidence: `SERVICES.toml:64-74` sets `stream = true` on `alliance-pod`; `00-baseline.md:68` confirms every tapetum call streams; RunPod blog states timeout applies until the **initial stream** starts. vLLM holds accepted HTTP connections without emitting SSE chunks until the request is scheduled (`--max-num-seqs 16` per user baseline). Impact: 365 connections waiting in the vLLM queue are indistinguishable from non-streaming waits at the proxy layer — no keepalive bytes until decode begins.

- [HIGH] **Today's successful 381-paper run does not validate the proposed plan.** Evidence: user baseline — 381 papers at **client c=16** = 722.4 s, 0 errors, max per-request queue ~1–2 min; plan under evaluation — **381 concurrent** HTTP requests at once with ~365 idle in queue up to ~12 min. At c=16 only ~16 proxy connections are in flight at any instant; the plan opens ~365 simultaneous long-idle connections. Impact: measured success is an envelope test for bounded fan-out, not a stress test of mass idle proxy connections.

- [HIGH] **RunPod recommends TCP exposure for long-queued / long-running requests.** Evidence: [expose-ports docs](https://docs.runpod.io/pods/configuration/expose-ports) ("Handle timeouts gracefully… use TCP for long-running connections"; troubleshooting: "524 timeout errors… consider using TCP"); [proxy guide](https://www.runpod.io/blog/runpod-proxy-guide) (switch HTTP exposed ports to TCP, use Connect → TCP Port Mapping). Impact: keeping `https://sgjy18glyi4blu-8000.proxy.runpod.net/v1` for a 12-min-queue batch is explicitly against RunPod's own guidance; direct `IP:external_port` bypasses Cloudflare's 100 s gate (TLS must be app-layer or accepted as plain HTTP on TCP).

- [MED] **No documented per-pod proxy concurrent-connection hard cap; 381 simultaneous TLS sessions is an unverified operational risk.** Evidence: RunPod docs specify "Expose HTTP Ports (Max **10**)" port *names*, not connection limits ([expose-ports](https://docs.runpod.io/pods/configuration/expose-ports)); no RunPod doc states a max parallel proxy connections per pod. Internal repo: `15-concurrency-safety.md:20` flags "per-IP connection caps… UNKNOWN"; `14-converter-batch.md:24` warns flooding proxy/vLLM queue. Cloudflare origin connection pooling docs ([connection-limits](https://developers.cloudflare.com/fundamentals/reference/connection-limits/)) govern CF↔origin behavior, not client↔CF fan-in. Impact: 524 from idle timeout is the documented failure mode; additional 502/connection-reset risk from LB/FD pressure at 381 parallel handshakes is plausible but unquantified in RunPod docs.

- [MED] **502 is a different failure class (origin down), not the queue-timeout class.** Evidence: [vLLM RunPod deployment guide](https://docs.vllm.ai/en/stable/deployment/frameworks/runpod/) ("502 Bad Gateway… server is not yet listening… wrong host binding… port mismatch"); RunPod vLLM article cites 502 when port not exposed. Impact: 502 during a long batch implies pod crash/restart or binding misconfig; 524 implies proxy killed a healthy-but-slow queued request — the plan's tail-latency failure signature is **524** or client `APIConnectionError`, not 502.

- [LOW] **Repo has no first-class RunPod 524/100 s guard; proxy risk is acknowledged but not instrumented.** Evidence: grep across `packages/whisker/research/` and `research/` finds no `524` or `100 s` proxy citations; closest is `15-concurrency-safety.md:20` (MED, proxy idle caps UNKNOWN). `SERVICES.toml:66` hardcodes proxy URL for `alliance-pod`. Impact: whisker will not preflight or attribute proxy 524 distinctly from generic `APIConnectionError` (`model_backends.py:341-351`).

## Predicted behavior of 365 queued connections through the proxy

1. **T+0 s:** Client opens 381 HTTPS POSTs to `https://sgjy18glyi4blu-8000.proxy.runpod.net/v1/chat/completions` with `stream=true`. Cloudflare terminates TLS; RunPod load balancer forwards to vLLM on port 8000.

2. **T+0–100 s:** vLLM accepts connections and enqueues ~365 requests beyond `--max-num-seqs 16`. No SSE chunks are emitted for queued work. Proxy sees an open upstream connection with **zero response bytes**.

3. **T≈100 s (tail of queue):** For requests still unscheduled, Cloudflare's origin-response timer fires per RunPod docs. Client receives **HTTP 524** (Cloudflare "A timeout occurred") or connection drop surfaced as `openai.APIConnectionError` after retry (`model_backends.py:341-351`, max 2 attempts). Whisker exception firewall logs error, **no sidecar** (`15-concurrency-safety.md:30`).

4. **T+100 s–12 min (if any connections survive):** Undocumented — today's c=16 run saw ~1–2 min max queue with 0 errors, which is already at or above the documented 100 s ceiling, suggesting either (a) TTFT measurement differs from operator "queue wait", (b) scheduling kept all 16 active slots fed so few requests sat fully idle, or (c) occasional slack in enforcement. Under 381-at-once, tail requests projected to ~12 min idle should fail en masse at ~100 s unless TCP/direct path is used.

5. **After first stream byte:** Once vLLM begins generation, streaming can continue beyond 100 s (RunPod blog: streaming started within 100 s is fine). Total decode may run minutes; proxy no longer blocks on TTFT. Risk shifts to client 600 s read timeout on very long decodes (`15-concurrency-safety.md:8`), not proxy 524.

6. **Concurrent-connection layer:** Even if some requests slip under 100 s TTFT, maintaining 365+ idle TLS sessions through Cloudflare may cause intermittent resets or elevated 502 during pod/network stress — undocumented, secondary to 524.

**Net prediction:** Under HTTP proxy + 381-at-once fan-out, expect a **large 524/APIConnectionError tail** on the last ~300+ papers, incomplete corpus, and wall time dominated by retries/failures rather than successful queue draining — unless queue depth stays ≤~16 active slots (i.e., effective c≈16, not 381).

## What would change my mind

1. **A controlled 381-at-once probe** on `alliance-pod` logging per-request: HTTP status, TTFT, queue depth, and whether 524 appears before 100 s idle — with pod logs confirming vLLM queue position. Zero 524s across all 381 would contradict current RunPod docs and warrant re-auditing.

2. **Switch to TCP exposure** for the same workload (pod template HTTP→TCP, `SERVICES.toml` `base_url` → `http://<public-ip>:<mapped-port>/v1`) and observe 381-at-once with 0 proxy 524s — would downgrade verdict to **risky** (vLLM/pod limits remain) rather than **breaks** (proxy limit).

3. **RunPod staff confirmation** (Discord/docs update) that the 100 s Cloudflare limit was lifted or does not apply to Pod HTTP proxy in 2026 — would require a primary source superseding [expose-ports](https://docs.runpod.io/pods/configuration/expose-ports).

4. **Evidence that vLLM emits keepalive/stream headers before scheduling** (e.g., immediate `200` + empty SSE comment) on the deployed 0.24 pod — would extend safe idle window beyond docs; not observed in repo or vLLM OpenAI-compat docs reviewed here.
