# 96 - vllm-Metrics-Probe

**Verdict:** usable — vLLM V1 exposes a complete queue/prefill/decode decomposition at `/metrics` on our RunPod proxy (verified live on `alliance-pod`); a 10 s scrape loop during the next cold fleet run will replace bottleneck speculation with measured facts.
**Confidence:** high

## Findings

- [CRITICAL] **Exact bottleneck-decomposition metrics live in `vllm/v1/metrics/loggers.py` (PrometheusStatLogger), enabled by default.** Evidence: queue gauges `vllm:num_requests_running` / `vllm:num_requests_waiting` / `vllm:num_requests_waiting_by_reason{reason="capacity|deferred"}` (`loggers.py:493-533`); prefix counters `vllm:prefix_cache_queries` / `vllm:prefix_cache_hits` (`loggers.py:584-601`); TTFT `vllm:time_to_first_token_seconds` (`loggers.py:796-826`); TPOT `vllm:inter_token_latency_seconds` (`loggers.py:829-856`) plus per-request mean `vllm:request_time_per_output_token_seconds` (`loggers.py:859-886`); e2e `vllm:e2e_request_latency_seconds` (`loggers.py:912-919`); phase histograms `vllm:request_queue_time_seconds`, `vllm:request_prefill_time_seconds`, `vllm:request_decode_time_seconds` (`loggers.py:922-959`). Default `--disable-log-stats` is **False** (`arg_utils.py:535`); disabling it kills all of the above (`observability.py:48-51`). Impact: zero-code probe on next 3003 s run; quality risk **none** (read-only).

- [CRITICAL] **There is no `prefix_cache_hit_rate` gauge — compute hit rate from counters.** Evidence: deprecated gauge removed; design doc specifies PromQL `rate(vllm:prefix_cache_hits[$I]) / rate(vllm:prefix_cache_queries[$I])` (`docs/design/metrics.md:411-429`); log fallback prints rolling 1k-query hit rate every `VLLM_LOG_STATS_INTERVAL` (default 10 s, `envs.py:47`, `loggers.py:287-297`, `stats.py:106-111`). Live `alliance-pod` (idle scrape 2026-07-23): `prefix_cache_hits_total / prefix_cache_queries_total ≈ 96.7%`, `enable_prefix_caching="True"` in `vllm:cache_config_info` (`loggers.py:1082-1098`). Impact: if hit rate drops below ~50% during a fleet burst, guard-tag / payload-scoping levers (`00-baseline.md:48-52`) are confirmed broken; if stays high, prefill is NOT the lever.

- [HIGH] **RunPod HTTP proxy exposes `/metrics`; operator must use pod Bearer key, not the `/v1` chat path.** Evidence: `SERVICES.toml:66` base_url `https://sgjy18glyi4blu-8000.proxy.runpod.net/v1` → metrics host is same origin without `/v1`. vLLM mounts `/metrics` unauthenticated (`server_utils.py:42-54`, `instrumentator/metrics.py:77-82`). Live probe: bare `curl …/metrics` → HTTP 401 `{"error":"Unauthorized"}`; `curl -H "Authorization: Bearer $ALLIANCE_POD_KEY" …/metrics` → full Prometheus text (131k+ finished requests on pod). **401 is RunPod proxy gate, not vLLM.** Impact: no TCP/SSH hop required; same key as tapetum lane.

- [HIGH] **Concrete probe plan for the NEXT cold fleet run (381 papers, c=32).** Record one snapshot every **10 s** (matches vLLM log interval, `envs.py:47`) for full run duration (~3003 s ⇒ ~300 rows). Store as `_scratch/research-tapetum-llm-speedup/metrics_<run_id>.jsonl`.

  ```powershell
  $POD = "https://sgjy18glyi4blu-8000.proxy.runpod.net"   # strip /v1 from SERVICES.toml base_url
  $KEY = $env:ALLIANCE_POD_KEY
  $OUT = "_scratch/research-tapetum-llm-speedup/metrics_$(Get-Date -Format yyyyMMdd_HHmmss).jsonl"
  while ($true) {
    $ts = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
    $m = curl -s -H "Authorization: Bearer $KEY" "$POD/metrics"
    $row = [ordered]@{
      ts = $ts
      running = [double](($m | Select-String 'vllm:num_requests_running\{[^}]*\}\s+(\S+)' | Select-Object -Last 1).Matches.Groups[1].Value)
      waiting = [double](($m | Select-String 'vllm:num_requests_waiting\{[^}]*\}\s+(\S+)' | Select-Object -Last 1).Matches.Groups[1].Value)
      waiting_capacity = [double](($m | Select-String 'reason="capacity"\}\s+(\S+)' | Select-Object -Last 1).Matches.Groups[1].Value)
      kv_cache_usage = [double](($m | Select-String 'vllm:kv_cache_usage_perc\{[^}]*\}\s+(\S+)' | Select-Object -Last 1).Matches.Groups[1].Value)
      prefix_queries = [double](($m | Select-String 'vllm:prefix_cache_queries_total\{[^}]*\}\s+(\S+)' | Select-Object -Last 1).Matches.Groups[1].Value)
      prefix_hits = [double](($m | Select-String 'vllm:prefix_cache_hits_total\{[^}]*\}\s+(\S+)' | Select-Object -Last 1).Matches.Groups[1].Value)
      gen_tokens = [double](($m | Select-String 'vllm:generation_tokens_total\{[^}]*\}\s+(\S+)' | Select-Object -Last 1).Matches.Groups[1].Value)
      ttft_sum = [double](($m | Select-String 'vllm:time_to_first_token_seconds_sum\{[^}]*\}\s+(\S+)' | Select-Object -Last 1).Matches.Groups[1].Value)
      ttft_count = [double](($m | Select-String 'vllm:time_to_first_token_seconds_count\{[^}]*\}\s+(\S+)' | Select-Object -Last 1).Matches.Groups[1].Value)
      tpot_sum = [double](($m | Select-String 'vllm:request_time_per_output_token_seconds_sum\{[^}]*\}\s+(\S+)' | Select-Object -Last 1).Matches.Groups[1].Value)
      tpot_count = [double](($m | Select-String 'vllm:request_time_per_output_token_seconds_count\{[^}]*\}\s+(\S+)' | Select-Object -Last 1).Matches.Groups[1].Value)
      queue_sum = [double](($m | Select-String 'vllm:request_queue_time_seconds_sum\{[^}]*\}\s+(\S+)' | Select-Object -Last 1).Matches.Groups[1].Value)
      queue_count = [double](($m | Select-String 'vllm:request_queue_time_seconds_count\{[^}]*\}\s+(\S+)' | Select-Object -Last 1).Matches.Groups[1].Value)
      prefill_sum = [double](($m | Select-String 'vllm:request_prefill_time_seconds_sum\{[^}]*\}\s+(\S+)' | Select-Object -Last 1).Matches.Groups[1].Value)
      prefill_count = [double](($m | Select-String 'vllm:request_prefill_time_seconds_count\{[^}]*\}\s+(\S+)' | Select-Object -Last 1).Matches.Groups[1].Value)
      decode_sum = [double](($m | Select-String 'vllm:request_decode_time_seconds_sum\{[^}]*\}\s+(\S+)' | Select-Object -Last 1).Matches.Groups[1].Value)
      decode_count = [double](($m | Select-String 'vllm:request_decode_time_seconds_count\{[^}]*\}\s+(\S+)' | Select-Object -Last 1).Matches.Groups[1].Value)
    }
    ($row | ConvertTo-Json -Compress) | Add-Content $OUT
    Start-Sleep -Seconds 10
  }
  ```

  **Post-run deltas** (compare first vs last snapshot, plus peak waiting): `Δgen_tokens/Δwall` = server output tok/s; `Δprefix_hits/Δprefix_queries` = interval hit rate; `decode_sum/decode_count` vs `prefill_sum/prefill_count` = phase means. Cross-check client wall from sidecars (`79-olmocr-metrics-observability.md:10`). Impact: decomposes implied ~20 s/call (`00-baseline.md:24-25`) into queue vs prefill vs decode with **±10 s** scrape granularity; quality risk **none**.

- [HIGH] **Decision tree (apply to scrape JSONL + cumulative histograms).**

  | Observation | Interpretation | Lever (quality-stable first) | Expected wall impact |
  |---|---|---|---|
  | `waiting > 0` for >50% of samples AND `running ≈ 16` (`00-baseline.md:66`) | Scheduler queue-bound; client over-subscribed vs `--max-num-seqs` | Lower paper concurrency, dual-pod shard (`21-dual-pod-sharder.md`), call elimination | 300–800 s if queue p95 >5 s |
  | `request_queue_time_seconds` p95 > 10 s (`loggers.py:922-929`) | Tail queue wait inflates TTFT; RunPod 524 risk if queue+prefill >100 s before first byte (`12-runpod-proxy.md:9-11`) | Same as above; never 381-at-once | Fail-closed proxy errors, not quality drift |
  | `prefill_sum/count` > `decode_sum/count` AND interval prefix hit rate < 30% | Prefill-bound; APC not sharing (`docs/design/metrics.md:193-199`) | Move guard tag to user-only tail (`45-guard-tag-cryptanalyst.md`), payload scoping | 400–900 s if full markdown prefilled 6× |
  | `decode_sum/count` > 2× `prefill_sum/count` AND mean TPOT > 0.04 s (~25 tok/s) | Decode-bound (live pod idle mean: prefill **0.46 s**, decode **5.9 s**, TPOT **0.028 s**) | MTP (`38-speculative-decoding-scout.md`), output-token caps (`14-output-token-surgeon.md`), dense unit-check model (`23-small-judge-evaluator.md`) | 500–1200 s on 2284 calls |
  | `TTFT_mean > TPOT_mean × 400` (≈1536 token cap) AND low prefix hits | Long uncached prefill dominates | APC + scoping; `--max-num-batched-tokens 16384` (`40-server-flag-auditor.md`) | 100–400 s |
  | `kv_cache_usage_perc` > 0.85 sustained OR `num_preemptions_total` rising (`loggers.py:661-667`) | KV pressure / churn | FP8 KV already on; reduce concurrent long contexts; retention env | 100–300 s + stability |
  | `rate(spec_decode_num_accepted_tokens)/rate(spec_decode_num_draft_tokens)` < 50% when MTP enabled | Spec decode overhead | Drop `num_speculative_tokens` to 1 or disable (`spec_decode/metrics.py:180-184`) | −50–100 s (negative if mis-tuned) |

- [MED] **Optional flags — what they add beyond the default `/metrics` bundle.**

  | Flag | Extra metrics | When to enable |
  |---|---|---|
  | *(default)* `disable_log_stats=False` | All core `vllm:*` above | Always on for fleet runs |
  | `--enable-per-request-metrics` | Response JSON `metrics.{queue,ttft,generation,mean_itl}_ms` (`docs/features/per_request_metrics.md:39-55`) | Per-call ground truth without PromQL; needs `stream_options.include_usage=true` |
  | `--enable-mfu-metrics` | `vllm:estimated_flops_per_gpu`, read/write bytes (`observability.py:65-66`, `perf.py`) | GPU util audit only; already partially present on pod |
  | `--kv-cache-metrics --kv-cache-metrics-sample 0.01` | `vllm:kv_block_lifetime_seconds`, idle, reuse_gap (`loggers.py:1003-1035`) | Diagnose APC eviction under c=16 |
  | `--cudagraph-metrics` | CUDA graph dispatch stats (`observability.py:56-58`, `loggers.py:119-123`) | After adding `FULL_DECODE_ONLY` compilation |
  | `--disable-log-stats` | **Disables everything** | Never on production judge pods |

- [MED] **Throughput sanity checks without PromQL server.** Counters: `vllm:generation_tokens_total`, `vllm:prompt_tokens_total`, `vllm:prompt_tokens_by_source{source="local_cache_hit|local_compute"}` (`loggers.py:670-701`). Interval output tok/s ≈ `Δgeneration_tokens / Δwall`. If output tok/s flat while waiting rises, slots are idle in queue not compute. Impact: validates whether 3003→5–10 min needs more slots vs faster decode.

- [LOW] **HTTP-level metrics ride the same scrape.** `http_request_duration_seconds{handler="/v1/chat/completions"}` from prometheus_fastapi_instrumentator (`docs/design/metrics.md:70-78`, `instrumentator/metrics.py:65-75`) includes client-visible queue+generation; use only as cross-check (includes tokenization/network).

## False-pass hypothesis

Polling only `vllm:num_requests_running` and `waiting` during a run would show `waiting=0` at c=32 while per-request `request_queue_time_seconds` p95 is still 8–15 s (queue drains between bursts), falsely crediting "no queue problem" and steering away from dual-pod sharding that would cut tail TTFT without touching judge prompts.

## False-fail hypothesis

Using cumulative histogram `_sum/_count` from a pod that ran for days before the fleet (131k requests on idle scrape) without deltaing against a run-start baseline would show decode-heavy means and mis-attribute an old workload to the tapetum fleet, falsely rejecting a prefill-scoping lever that helps only when prefix hit rate drops during the actual 381-paper burst.

## What would change my mind

A cold fleet run with concurrent 10 s `/metrics` scrapes where `request_prefill_time_seconds` p95 exceeds `request_decode_time_seconds` p95 **and** interval prefix hit rate stays below 20% — that would flip the live-pod idle finding (96.7% hits, decode 13× prefill) and elevate prefill/APC over decode/MTP in the lever stack.
