# 146 - Verifier-B (Prefix-Cache Contradiction)

**Verdict:** usable — live `/metrics` probe resolves the contradiction: **96 is right on measured pod state** (APC on, 96.7% token hit rate, decode-heavy cumulative phase split); **93 is right as tapetum cold-fleet counterfactual** (~17 s uncached prefill+queue on 40k prompts, not reflected in lifetime means); **40/15 overstate “APC off”** — flag is `True` and hits are massive, though 15 remains correct that per-call guard tags block *in-paper document* sharing.
**Confidence:** high

## Findings

- [CRITICAL] **Live probe succeeded (2026-07-23 ~16:08 UTC).** Bare `curl https://sgjy18glyi4blu-8000.proxy.runpod.net/metrics` → HTTP **401** `{"error":"Unauthorized"}` (RunPod proxy gate). `Authorization: Bearer $ALLIANCE_POD_KEY` → HTTP **200**, 60 637 bytes Prometheus text saved to `_scratch/research-tapetum-llm-speedup/metrics-probe.txt`. Pod version `GET /version` → **v0.24.0**; `/server_info` → **404** (retention env not introspectable on this build). Impact: 96’s auth path confirmed; 96’s numbers are reproducible, not fabricated.

- [CRITICAL] **APC is enabled on the running pod — contradicts 40/15 “not effectively enabled”.** Evidence: `vllm:cache_config_info{...,enable_prefix_caching="True",cache_dtype="fp8",block_size="4",sliding_window="128",prefix_caching_hash_algo="sha256",num_gpu_blocks="17679",...}`. Counters: `prefix_cache_hits_total` **1.1677317632×10¹⁰** / `prefix_cache_queries_total` **1.2081100981×10¹⁰** → **96.66% token hit rate** (matches 96’s 96.7%). Cross-check: `prompt_tokens_by_source{source="local_cache_hit"}` **1.1677307904×10¹⁰** vs `local_compute` **4.03685928×10⁸** → same 96.66%. Impact: server-side APC is live and working at fleet scale; 40’s “enable `--enable-prefix-caching` + retention env” is still a valid *upgrade checklist* but not a description of today’s pod.

- [CRITICAL] **96’s phase means are real pod data, not idle health-probe artifacts — but they are lifetime-cumulative, not tapetum-isolated.** Evidence: `e2e_request_latency_seconds_count` **131 568** finished requests (96 claimed “131k+”). Per-request averages from counters: **91 823 prompt tokens**, **235.3 generation tokens**, **3 068 locally-computed prefill tokens** (~3.3% fresh / 96.7% cached). Idle gauges at scrape: `num_requests_running=0`, `num_requests_waiting=0`. These are full inference requests with large prompts, not tiny probes. Impact: 96’s decode-vs-prefill *means* are trustworthy for “what this pod has processed since boot”; 96’s own false-fail hypothesis applies — **do not attribute tapetum cold-fleet behavior to these means without a run-start delta scrape**.

- [CRITICAL] **Cumulative histogram means (computed from `_sum/_count`, pod lifetime window):**

  | Metric | Mean (s) | % of E2E (9.01 s) |
  | --- | ---: | ---: |
  | `request_queue_time_seconds` | **2.38** | 26.4% |
  | `request_prefill_time_seconds` | **0.46** | 5.1% |
  | `request_decode_time_seconds` | **5.91** | 65.6% |
  | `time_to_first_token_seconds` | **3.15** | — |
  | `request_time_per_output_token_seconds` (TPOT) | **0.0278** (~36 tok/s) | — |
  | `e2e_request_latency_seconds` | **9.01** | 100% |

  96 reported prefill **0.46 s**, decode **5.9 s**, TPOT **0.028 s** — independently confirmed. **Fleet is decode-dominated in cumulative means**, not prefill-dominated. Impact: MTP/output-token levers align with measured pod history; prefill-scoping still matters for the **uncached tail**, not for aggregate means today.

- [HIGH] **93’s ~17 s (queue + prefill) decomposition is the uncached tapetum physics, not what cumulative metrics show under 96.7% APC.** Evidence: with **3 068 computed tokens/request** at ~3500 tok/s → **~0.9 s** fresh prefill (observed mean **0.46 s**). Tapetum counterfactual without document-level sharing: ~40k tokens × 6 calls/paper, ~11–16 s prefill/call (`93:16-23`, `00-baseline:46-47`) plus **4–6 s queue** at c=32 vs 16 slots. Tail buckets (requests exceeding threshold): prefill **>15 s: 388 (0.29%)**, **>20 s: 320 (0.24%)**; TTFT **>10 s: 11 781 (8.9%)**, **>20 s: 6 643 (5.0%)**, p95 TTFT **~40 s**. Impact: saturated cold tapetum burst would inflate the tail and interval hit rate; 93 is the right planning model for that burst; 96 is the right reading of current pod history.

- [HIGH] **15’s guard-tag claim is scoped wrong at “0% hits / impossible” but right at document-level sharing.** Block-hash APC matches from token 0 (`92:8-8`). Per-call `SRC{hex}` at the **system tail** still allows ~925+ shared system tokens to hit; **unit metadata before `candidate_md`** prevents cross-unit reuse of the document body (`15:10-10`). Observed **96.66% token hits** with **91k prompt tokens/request** proves massive prefix reuse somewhere (repeated papers, shared system prefix, warm reruns) — not that all six tapetum calls share full markdown. Impact: client reorder + per-paper tag remains a **600–900 s class lever** (`15:22-22`); guard tags do **not** zero APC.

- [MED] **Window problem (mandatory caveat for synthesis).** All histogram `_sum/_count` ratios are **since pod start** (~131k requests, ~1.21×10¹⁰ prompt tokens processed). Interval hit rate during a 381-paper cold fleet requires delta scrapes (96’s JSONL plan). `prefix_cache_*_created` gauges show Unix ts **~1.783525368×10⁹** (pod/process epoch). Impact: synthesis must pair cumulative means with **run-start baselines** before choosing levers for the 3003 s target.

- [MED] **Large-prompt TTFT/TPOT split (best available without per-request labels).** For the **~5%** of requests with TTFT **>20 s** (likely long uncached prefill + queue), TTFT tail reaches **40 s+** while median TTFT is **<1 s** (71 854 / 131 825 ≤1 s). Decode mean **5.91 s** on **235 output tokens** ≈ **40 tok/s effective** (below 00’s 70 tok/s docstring — MoE contention at 16 slots). Cannot isolate “tapetum unit check only” from Prometheus alone; need `--enable-per-request-metrics` or labeled scrape during fleet run.

## False-pass hypothesis

Treating **96.66% lifetime token hit rate** as proof tapetum’s six-call cascade already shares full `candidate_md` KV would skip guard-tag and user-reorder work; interval hit rate during a cold fleet could drop sharply for calls 2–6 while lifetime mean stays high from warm reruns and shared system-prefix hits.

## False-fail hypothesis

Deploying `--enable-prefix-caching` because 40/15 say it is “off” would change nothing — APC is already `True` with 96.7% hits; operators might duplicate config churn and miss the real client-side blockers (guard placement, user block order).

## What would change my mind

A cold 381-paper fleet with 10 s `/metrics` delta scrapes showing **interval** `prefix_cache_hits/queries < 20%` **and** `request_prefill_time_seconds` p95 **> `request_decode_time_seconds` p95** — that would flip the lever stack to 93/15 over 96’s lifetime decode-bound picture.

## Probe appendix (load-bearing numbers)

| Quantity | Value |
| --- | --- |
| Auth | no header → 401; Bearer → 200 |
| `enable_prefix_caching` | **True** |
| Token hit rate | **96.66%** (1.1677×10¹⁰ / 1.2081×10¹⁰) |
| Finished requests | **131 568** |
| Idle queue | running **0**, waiting **0** |
| Mean queue / prefill / decode / E2E | **2.38 / 0.46 / 5.91 / 9.01 s** |
| Mean TTFT / TPOT | **3.15 s / 0.0278 s** |
| Avg prompt / gen / computed tokens per req | **91 823 / 235 / 3 068** |
| Prefill >15 s (tail) | **388 req (0.29%)** |
| TTFT >20 s (tail) | **6 643 req (5.0%)** |
