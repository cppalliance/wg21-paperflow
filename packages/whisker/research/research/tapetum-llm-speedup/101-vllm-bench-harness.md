# 101 - vLLM-Bench-Harness

**Verdict:** usable-with-conditions — `vllm bench serve` + `CustomDataset` can replay ~100 real judge prompts against `alliance-pod` off-hours at c∈{8,16,24,32} and decompose TTFT/TPOT/throughput to validate or refute the prefill-bound hypothesis; `auto_tune.sh` and `bench sweep serve` are **not** safe on the live shared pod (they restart/configure the server).
**Confidence:** high

## Findings

- [CRITICAL] **`benchmark_serving.py` is deprecated; production path is `vllm bench serve` (`vllm/benchmarks/serve.py`).** Evidence: stub exits with redirect message (`benchmarks/benchmark_serving.py:5-18`); implementation lives in `vllm/benchmarks/serve.py:1-19` (module docstring), CLI wired via `python -m vllm.entrypoints.cli.main bench serve` (`benchmarks/benchmark_serving.py:12-13`). Docs mirror: online benchmark section (`docs/benchmarking/cli.md:76-86`, `docs/cli/bench/serve.md:1-9`). Impact: **0 s** on 3003 s fleet (measurement-only lever); enables **evidence-backed** server/client tuning instead of guessing. Quality risk: **none** (read-only bench).

- [CRITICAL] **Reported metrics include TTFT, TPOT, ITL, E2EL, and throughput — exactly what we need to split prefill vs decode.** Evidence: `BenchmarkMetrics` dataclass fields `mean/median_ttft_ms`, `mean/median_tpot_ms`, `mean/median_itl_ms`, `mean/median_e2el_ms`, `output_throughput`, `total_token_throughput` (`vllm/benchmarks/serve.py:310-342`); printed as "Time to First Token", "Time per Output Token (excl. 1st token)", "Inter-token Latency", request/token throughput (`docs/benchmarking/cli.md:99-111`); aggregation in `calculate_metrics` (`vllm/benchmarks/serve.py:711-748`, TTFT/TPOT print at `1274-1277`). **Hypothesis test:** compute `TTFT_share = median_ttft_ms / median_e2el_ms` per concurrency; if **>0.45** across representative unit-check/monolith rows, prefill-bound (supports persona tapetum doc `tapetum_llm.md:301`); if **<0.25** with TPOT rising at c=24–32, decode/scheduling-bound (refutes). Impact: directs levers (prefix cache / payload scoping vs MTP / max-num-seqs). Quality risk: **none**.

- [HIGH] **`CustomDataset` replays our REAL prompts from a local `.jsonl`; no ShareGPT surrogate.** Evidence: `--dataset-name custom` documented (`docs/benchmarking/cli.md:43-44`, `146-175`); loader requires `prompt` column, optional per-row `output_tokens` (`vllm/benchmarks/datasets/datasets.py:2454-2464`, `2486-2495`, `2538-2553`); `--custom-skip-chat-template` skips re-templating when prompt is pre-rendered (`docs/benchmarking/cli.md:169`, `vllm/benchmarks/datasets/datasets.py:2558-2565`). `SampleRequest.chat_messages` exists for multi-turn/tool paths (`vllm/benchmarks/datasets/datasets.py:87-90`) but stock `CustomDataset` is single-field — extractor should emit **pre-applied chat strings** (system+user as our backend sends them) into `prompt`. Impact: bench fidelity to ~20 s/call production shape (`00-baseline.md:24-25`); mis-sized synthetic prompts would **invalidate** the prefill hypothesis test. Quality risk: **none** for bench; wrong extraction → wrong conclusion (mitigated below).

- [HIGH] **Safe concurrency sweep pattern: `--request-rate inf --max-concurrency N` matches production "users flood / gateway caps" and is the recommended maximum-throughput pattern.** Evidence: load-pattern table (`docs/benchmarking/cli.md:613-631`); `max_concurrency` defaults unlimited, explicit cap simulates load-balancer backpressure (`docs/benchmarking/cli.md:594`, `vllm/benchmarks/serve.py:771`); semaphore in benchmark loop (`vllm/benchmarks/serve.py:862-865`). Our fleet uses client c=32 against server `--max-num-seqs 16` (`00-baseline.md:34-35`, `cli.py:125-127`). Sweep **{8,16,24,32}** brackets the operating point without triggering RunPod proxy failure mode. Impact: **0 s** direct; identifies whether TTFT climbs at c>16 (prefill queueing) vs TPOT degrades (decode/MoE). Quality risk: **none** if run off-hours with ~100 prompts (~25–40 min total including cooldowns).

- [HIGH] **`auto_tune.sh` (Q3 card) sweeps `max-num-seqs` × `max-num-batched-tokens` by **restarting local vLLM** — do NOT run on `alliance-pod`.** Evidence: README requires clone + `bash auto_tune.sh`, iterates server start + `vllm bench serve`, writes `result.txt` with best `(max_num_seqs, max_num_batched_tokens, throughput, e2el)` (`benchmarks/auto_tune/README.md:1-6`, `52-56`, `88-96`, `108-116`); `pkill -f vllm` caveat (`benchmarks/auto_tune/README.md:52-53`). Safer equivalent for **read-only** remote pod: `vllm bench sweep serve_workload` varies client `--max-concurrency` only (`docs/benchmarking/sweeps.md:106-124`, `138-139`). Server-flag A/B belongs on **`h200x8-deepseek-v4-pro`** duplicate (`SERVICES.toml:47-57`) with operator approval, not the 24/7 advisory lane. Impact: misapplied auto_tune could **disrupt Sam's shared pod**; correct remote workload sweep saves mis-tuned flag experiments. Quality risk: **none** if confined to duplicate pod / maintenance window.

- [MED] **Per-request server metrics decompose queue vs prefill vs decode when `--enable-per-request-metrics` is on.** Evidence: `time_to_first_token_ms` = scheduled→first token; `generation_time_ms` = first→last token (decode only); `queue_time_ms` = scheduler wait (`docs/features/per_request_metrics.md:39-55`). Complements client-side TTFT from bench (`vllm/benchmarks/serve.py:600-601`). Spot-check 5 requests during bench: if `queue_time_ms` dominates at c=32, contention is scheduling/KV not prompt bytes. Impact: **0 s** fleet; narrows which lever (MBT, prefix cache, client c). Quality risk: slight CPU overhead at high concurrency (`docs/features/per_request_metrics.md:19-22`) — acceptable off-hours for 100 prompts.

- [MED] **Prefix-heavy control: `prefix_repetition` synthetic dataset isolates APC benefit; real replay isolates production share ratio.** Evidence: `--dataset-name prefix_repetition` (`docs/benchmarking/cli.md:955-963`); `PrefixRepetitionRandomDataset` params (`vllm/benchmarks/datasets/datasets.py:4289-4316`). Run once alongside custom replay: if prefix_repetition shows TTFT collapse but custom replay does not, guard-tag placement (`00-baseline.md:48-52`) is the bottleneck not server APC. Impact: prevents false "enable prefix caching fixes fleet" from synthetic-only evidence. Quality risk: **none**.

- [LOW] **Prometheus `/metrics` during bench: `vllm:num_requests_waiting`, prefix cache hit rate.** Evidence: fetch in serve benchmark (`vllm/benchmarks/serve.py:183-200`); metric definitions (`docs/design/metrics.md:35`, `52-53`); Red Hat triage note in Q3 card (`05-web.md:65-66`). Snapshot `/metrics` at start/end of each concurrency run. Impact: **0 s**; confirms waiting>0 under load. Quality risk: **none**.

## Concrete SAFE benchmark plan (alliance-pod, off-hours)

### Preconditions (do not skip)

1. **Window:** off-hours; no concurrent `whisker-tapetum-llm` fleet run on `alliance-pod`.
2. **Scope:** ~100 prompts, not 2284 — enough for stratified TTFT/TPOT distributions without saturating shared pod for >~45 min.
3. **Concurrency cap:** **32 max** — above this RunPod proxy kills idle connections (~100 s) and c=381 broke 257/381 requests (`cli.py:129-131`, `tapetum_llm.md:304-305`).
4. **Health probe first** — same gate as fleet CLI (`cli.py:910-951`, `_HEALTH_PROBE_TIMEOUT_SECONDS = 30.0` at `cli.py:204-205`).
5. **Do not** run `auto_tune.sh`, `vllm bench sweep serve` (starts local server), or change pod launch flags during measurement.

### Step 0 — Install bench client (laptop or CI, not on pod)

```bash
uv pip install "vllm>=0.24"   # provides `vllm bench serve`
```

### Step 1 — Build stratified replay JSONL from debug transcripts

Source: `$WG21_DATA_DIR/paperstore/<pid>.debug.tapetum_llm.md` (full I/O captured with `--debug`; blocks delimited by `<!-- call:` / `<!-- system -->` / `<!-- user -->` per `vision_task.py:147-153`).

Target schema (`CustomDataset`):

```json
{"prompt": "<pre-rendered chat string or exact messages flattened>", "output_tokens": 420, "call_type": "unit_check", "pid": "p4012r0"}
```

Stratified ~100 rows from last cold fleet sidecars/debug set:

| Stratum | Target n | Source labels in debug |
| --- | --- | --- |
| monolith | 15 | `pdf-judge-*` |
| metadata/outline | 15 | `metadata-outline-*` |
| unit_check | 55 | `unit-check-*` |
| page_escalation | 15 | `pdf-judge-page-*` |

Within each stratum, sample quartiles of **input token length** (use sidecar `usage.prompt_tokens` if present, else char/4). Store extractor under `_scratch/research-tapetum-llm-speedup/extract_judge_bench.py` (disposable).

For `openai-chat` fidelity, pre-render with the same template our backend uses, then `--custom-skip-chat-template`. Alternative: completions endpoint with `--endpoint /v1/completions` if prompts are raw (`docs/benchmarking/cli.md:166-168`).

### Step 2 — Health probe (RunPod)

```powershell
$env:ALLIANCE_POD_KEY = "<from .env>"
curl.exe -sf -H "Authorization: Bearer $env:ALLIANCE_POD_KEY" `
  "https://sgjy18glyi4blu-8000.proxy.runpod.net/health"
```

Failure here matches fleet pre-batch gate behavior (`cli.py:934-950`) — **abort**, do not bench into a cold/restarting pod (`docs/deployment/frameworks/runpod.md:36-43`).

### Step 3 — Concurrency sweep (remote only)

```powershell
$BASE = "https://sgjy18glyi4blu-8000.proxy.runpod.net"
$KEY  = $env:ALLIANCE_POD_KEY
$DATA = "_scratch/research-tapetum-llm-speedup/judge_replay_100.jsonl"
$OUT  = "_scratch/research-tapetum-llm-speedup/bench-results"

foreach ($C in 8,16,24,32) {
  uv run vllm bench serve `
    --backend openai-chat `
    --base-url $BASE `
    --endpoint /v1/chat/completions `
    --header "Authorization=Bearer $KEY" `
    --model deepseek-v4-pro `
    --dataset-name custom `
    --dataset-path $DATA `
    --custom-skip-chat-template `
    --num-prompts 100 `
    --max-concurrency $C `
    --request-rate inf `
    --output-len 512 `
    --num-warmups 3 `
    --ready-check-timeout-sec 600 `
    --save-result --save-detailed `
    --result-dir "$OUT/c$C"
  Start-Sleep -Seconds 120   # cooldown; avoid proxy keepalive kill (~100s idle)
}
```

**RunPod / proxy warnings:**

- Use `--base-url` (HTTPS proxy), not `--host 127.0.0.1` (`vllm/benchmarks/serve.py:1473-1477`).
- RunPod proxy returns **502** while model loads (`docs/deployment/frameworks/runpod.md:36-43`); `--ready-check-timeout-sec 600` waits through warm load (`vllm/benchmarks/serve.py:779`, `docs/benchmarking/cli.md:546`).
- **Do not** exceed c=32 or run full 2284 replay — proxy connection kills documented (`cli.py:129-131`).
- Health probe is **GET /health** on server root, not `/v1/health` (`cli.py:934`).
- aiohttp session timeout 6 h per request (`vllm/benchmarks/serve.py:805`) — safe for 120 s judge calls; fleet uses 120 s unit timeout (`constants.py:197`).

### Step 4 — Optional server-side decomposition (if operator enables flag)

If pod can temporarily enable `--enable-per-request-metrics` on **duplicate** instance only (`docs/features/per_request_metrics.md:10-14`), spot-check 10 calls:

```python
# metrics.time_to_first_token_ms vs metrics.generation_time_ms vs metrics.queue_time_ms
```

### Step 5 — Analyze (prefill vs decode verdict)

For each concurrency, from saved JSON (`--save-result`):

| Metric | Source | Prefill-bound signal |
| --- | --- | --- |
| `median_ttft_ms` | bench result | Rises sharply c=16→32 |
| `median_tpot_ms` | bench result | Flat or mild rise |
| `TTFT_share = median_ttft / median_e2el` | derived | **>0.45** |
| `output_throughput` | bench result | Sublinear in concurrency |
| `vllm:prefix_cache_hits_total/queries_total` | `/metrics` diff | Low on custom replay, high on prefix_repetition control |

Compare to baseline arithmetic: ~20 s/call, ~70 tok/s decode (`00-baseline.md:24-28`) ⇒ decode-only ≈ 7–22 s for 512–1536 output tokens; **residual above that in TTFT** is prefill+queue.

### Step 6 — Control run (synthetic prefix)

```powershell
uv run vllm bench serve `
  --backend openai-chat --base-url $BASE `
  --header "Authorization=Bearer $KEY" `
  --model deepseek-v4-pro `
  --dataset-name prefix_repetition `
  --num-prompts 100 --max-concurrency 16 `
  --prefix-repetition-prefix-len 3000 `
  --prefix-repetition-suffix-len 500 `
  --prefix-repetition-num-prefixes 5 `
  --prefix-repetition-output-len 400 `
  --request-rate inf --save-result `
  --result-dir "$OUT/prefix_control"
```

(`docs/benchmarking/cli.md:955-963`, `vllm/benchmarks/datasets/datasets.py:4289-4316`)

### What NOT to do on alliance-pod

| Action | Why unsafe |
| --- | --- |
| `bash benchmarks/auto_tune/auto_tune.sh` | Restarts vLLM, sweeps server flags (`benchmarks/auto_tune/README.md:52-56`) |
| `vllm bench sweep serve --serve-cmd 'vllm serve ...'` | Starts/configures server (`docs/benchmarking/sweeps.md:9-17`) |
| c=64 or 381 client concurrency | Proxy kills / 257 failures (`cli.py:129-131`) |
| Full 2284-call replay | ~76k slot-seconds; displaces production advisory lane for hours |

## False-pass hypothesis

Running `--dataset-name random` with `--random-input-len 4000 --random-output-len 400` instead of extracted judge prompts: TTFT/TPOT ratios look healthy on uniform random tokens, team concludes decode-bound and skips prefix-cache + payload-scoping levers — **silent wrong optimization target** while real fleet stays ~3003 s.

## False-fail hypothesis

Running bench during an active fleet run or at c=48: TTFT explodes from queue contention + proxy errors (`cli.py:129-131`), team concludes pod is "broken" and pursues dual-pod sharding or model swap — **infrastructure artifact**, not steady-state latency.

## What would change my mind

A completed off-hours replay where **TTFT_share < 0.25** at c=16 on the stratified custom JSONL **and** per-request `generation_time_ms / (generation_time_ms + time_to_first_token_ms) > 0.75` on unit_check rows — would refute prefill-bound for the median judge call and shift priority to MTP/decode flags (persona 40) over payload scoping (persona 13).
