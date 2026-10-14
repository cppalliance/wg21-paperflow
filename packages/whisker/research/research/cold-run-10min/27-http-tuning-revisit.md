# 27 - HTTP Client Tuning Revisit

**Verdict:** usable — original persona 27 rejection stands; HTTP transport is still not a cold-fleet bottleneck at c=32, and no new code path makes connection pooling, HTTP/2, or keepalive tuning a schedulable lever toward ~10 min.
**Confidence:** high

**Revisit?** **no**

## Source audit

Original report: `research/tapetum-llm-speedup/27-http-client-tuner.md` (2026-07-23, HEAD 51cb704 era). User path `speedup/27-http-client-tuner.md` does not exist; the authoritative doc is under `research/tapetum-llm-speedup/`.

Original verdict: **garbage** — pool caps are not throttling (≤32 live connections vs httpx defaults 1000/100), per-call TLS churn saves at most ~10–30 s on a ~3003 s run (~0.3–1%), not the ~40 min gap to 5–10 min.

## Findings (HEAD re-check, 2026-07-24)

- [CRITICAL] **Judge hot path still mints a fresh `AsyncOpenAI` on every LLM call.** Evidence: `client = AsyncOpenAI(base_url=..., api_key=...)` inside every `VllmThinkingBackend.run()` entry and tool paths (`packages/pipeline/src/pipeline/model_backends.py:283`, `:443`, `:535`, `:627`); no backend-level client field, no `await client.close()`. `load_services()` still builds one long-lived `VllmThinkingBackend` per service (`packages/pipeline/src/pipeline/services.py:200`), and the CLI reuses `AgentBackend` instances per batch (`packages/whisker/src/whisker/tapetum_llm/cli.py:1075-1113`), but each `agent.run()` still creates a new httpx pool. Impact: original TLS estimate unchanged in shape; **not** a regression, **not** a new opportunity without a `packages/pipeline/` change.

- [CRITICAL] **Concurrency bound unchanged; pool-cap tuning still irrelevant.** Evidence: `_DEFAULT_CONCURRENCY = 32`, `asyncio.Semaphore(concurrency)` on the paper worker (`cli.py:133`, `cli.py:1178-1193`); within one paper judge calls remain serial (`pdf_judge.py` chain, `unit_judge.py` unit loop). OpenAI SDK still uses default `httpx.Limits(max_connections=1000, max_keepalive_connections=100)` when no override is passed (persona 27 runtime probe on `openai==2.34.0`; no override at `model_backends.py:283`). Impact: **≈0 s** from raising pool limits; the 381-at-once failure mode remains proxy idle-timeout, not sub-32 pool starvation (`research/concurrency-381/12-runpod-proxy.md`).

- [HIGH] **v11 metadata short-circuit shrinks the TLS-hygiene ceiling, not expands it.** Evidence: `_LANE_VERSION = 11` documents metadata-fail short-circuit eliminating ~44.6% of calls with zero verdict drift (`cli.py:119-122`, `tapetum_llm.md` lane log); `pdf_judge.py:742-756`, `adjudicate.py:521-528`. Original estimate: ~2284 calls × ~100–150 ms TLS ≈ **10–30 s** fleet wall. Post short-circuit effective call count ≈ **~1260** → shared-client savings fall to roughly **~5–17 s** (~0.2–0.6% of legacy 3003 s wall). Impact: HTTP tuning matters **less** after the highest-ranked client lever lands, not more.

- [HIGH] **New batch plumbing does not add connection reuse on the judge path.** Evidence: CLI now loads `registry = load_services()` once per batch and passes it into `adjudicate_paper` / `judge_pdf_extraction` (`cli.py:1071-1075`, `adjudicate.py:768-769`); health gate uses ephemeral `async with httpx.AsyncClient(...)` for one `GET .../health` (`cli.py:967-1008`). Impact: eliminates repeated TOML parse and catches cold pods early; **≈0 s** on steady-state cold fleet HTTP transport. Not a connection-pool code path for LLM POSTs.

- [HIGH] **HTTP/2 and keepalive tuning remain unverified or actively risky on RunPod proxy.** Evidence: still no `http2=` on `AsyncOpenAI(...)` (`model_backends.py:283`); endpoint still `https://*.proxy.runpod.net/v1` with `stream = true` on `alliance-pod` (`SERVICES.toml:64-74`). Persona 27: HTTP/2 off by default, Cloudflare-terminated hop, ≤32 concurrent long-lived POSTs — multiplexing gain speculative. Keepalive reuse risk unchanged: shared client + `keepalive_expiry=5.0` after 120 s unit stalls → dead socket → `APIConnectionError` → retry (`model_backends.py:341-350`), infrastructure false-fail. Disabling `stream=true` to shave client overhead would **increase** proxy 524 risk under queue (`research/concurrency-381/12-runpod-proxy.md:11`). Impact: **≈0 s** measured win; quality/reliability downside on the only tested transport.

- [MED] **Persistent httpx pools exist elsewhere in the repo, not on tapetum.** Evidence: `BraveBackend` holds long-lived `httpx.AsyncClient` (`packages/pipeline/src/pipeline/backends/brave.py:78`); `WebResearcher` same pattern (`session.py:133`); readback reuses one sync `httpx.Client` per paper (`readback.py:337-344`); dormant VLM lane still per-call `AsyncOpenAI` (`vision_task.py:125`). Pipeline invariant explicitly separates search backends from model backends (`pipeline/CLAUDE.md`: "Backends are long-lived" applies to Brave, not `VllmThinkingBackend`). Impact: no new pattern to port without crossing the whisker/package-boundary rule for a sub-minute gain.

- [MED] **Cold-run delta ranking still excludes HTTP transport.** Evidence: `research/cold-run-10min/00-baseline.md:32-38` settled levers are metadata short-circuit, prefix/APC layout, dual-pod, tombstones, client stalls (LJF, `to_thread`, monolith `wait_for`) — not pool/HTTP/2. Persona 27 listed in the "garbage tier" alongside personas 34–36, 38, 40–47 in `48-combined-lever-modeler.md`. Impact: revisiting HTTP tuning would distract from levers with **100×–1000×** larger envelopes.

- [LOW] **Implementation cost crosses package boundary for negligible return.** Evidence: `.cursor/rules/package-boundary.mdc` — whisker tasks must not edit `packages/pipeline/`; shared `AsyncOpenAI` on `ModelBackend` is a pipeline change. Whisker-local D1 exemptions (`readback.py`, `judge_task.py`) exist for dispatch, not for duplicating httpx pool logic beside the SDK. Impact: even the hygiene fix needs explicit user approval and A/B proof; payoff remains below noise floor for the 10 min goal.

## Code drift since persona 27

| Area | 2026-07-23 claim | HEAD 2026-07-24 |
|------|------------------|-----------------|
| Per-call `AsyncOpenAI` | Yes | **Unchanged** |
| c=32 semaphore | Yes | **Unchanged** |
| `stream=true` on alliance-pod | Yes | **Unchanged** |
| HTTP/2 | Off | **Unchanged** |
| Batch `load_services()` once | Per-paper fallback noted | **Improved** (CLI batch only) |
| Health probe | Not present | **Added** (one GET, negligible) |
| Call count | ~2284 | **Lower** after v11 metadata short-circuit |
| Client-stall fixes | Paper-only | **Partially landed** (LJF, `to_thread`, monolith timeout — separate lever #6) |

No new connection-pool, HTTP/2, or keepalive code path on the tapetum judge POST path.

## False-pass hypothesis

Implementing shared `AsyncOpenAI` on `ModelBackend` to "recover" ~10–30 s: operators attribute a ~5–15 s wall drop post-v11 to HTTP tuning and defer metadata/APC/dual-pod work; fleet still sits at ~40+ min cold wall while looking "optimized."

## False-fail hypothesis

Enabling HTTP/2 or tightening keepalive on a shared client during a future c>32 experiment: tail papers queue without SSE bytes, proxy closes idle connections at ~100 s, retries succeed on lighter load — faster wall time with **fewer completed judgments** (same failure class persona 27 documented for `stream=false`).

## What would change my mind

1. Cold run at c=32 with per-call timestamps showing **≥5% of per-call wall** in connect/TLS (median TTFT minus vLLM queue time **>500 ms**) — persona 27's original upgrade criterion.
2. **Infrastructure change** that removes RunPod HTTPS proxy (TCP/direct pod access) **and** measured connect latency becomes a double-digit percent of call time — would reopen transport tuning in a **different** threat model, still not HTTP/2 on Cloudflare proxy.
3. Call graph grows back toward ~2284+ calls/paper (short-circuit disabled) **and** connect share is proven — would raise the TLS hygiene ceiling toward ~30 s, still not minute-scale.

None of these are satisfied at HEAD without new measurements.

## Bottom line

Persona 27 was **rightly rejected as noise** for the 10 min cold-run goal. HTTP client tuning addresses **~0.2–1%** of legacy wall time while the settled gap is **~80%**. New code since the audit (batch registry, health probe, v11 short-circuit, LJF/`to_thread`) either does not touch LLM connection reuse or **reduces** the remaining TLS savings. Connection pooling, HTTP/2, and keepalive tweaks are **not worth revisiting** until connect/TLS is proven material or the transport stack changes off RunPod HTTPS proxy.

**Revisit? no**
