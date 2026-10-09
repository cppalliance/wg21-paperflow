# 72 - olmocr-Server-Management

**Verdict:** usable-with-conditions — olmOCR owns vLLM lifecycle and pairs a 16k `max_model_len` cap with per-page (not per-document) requests and a 1600-wide client semaphore; the pattern is portable, but copying flags alone onto our 393k shared pod does nothing until unit-check payloads are scoped to fit a short-context instance.
**Confidence:** high

## Findings

- [CRITICAL] olmOCR spawns and owns vLLM inside the pipeline process: `vllm_server_task` builds `vllm serve …` subprocess (`pipeline.py:807-842`), started via `vllm_server_host` with up to 5 restart attempts (`pipeline.py:911-926`), cancelled on shutdown (`pipeline.py:1464-1473`). Readiness is polled against `{server}/models` for up to 600 s (`pipeline.py:929-953`), not `/health`. External-server mode skips spawn when `--server` is set (`pipeline.py:1242-1246`, `1286-1287`, `1446-1451`). Impact: we cannot adopt restart/ready logic without pod-operator cooperation on a 24/7 shared endpoint; lifecycle ownership is the main non-portable piece. Quality risk: none from pattern alone.

- [CRITICAL] Default vLLM launch flags: `--max-model-len 16384` (`pipeline.py:830-831`, `1255`), optional `--gpu-memory-utilization` passthrough (`pipeline.py:827-828`, `1252-1253`), `--tensor-parallel-size` / `--data-parallel-size` (`pipeline.py:819-822`, `1256-1257`), `--disable-log-requests`, `--uvicorn-log-level warning`, `--served-model-name olmocr`, `--limit-mm-per-prompt '{"video": 0}'` (`pipeline.py:814-824`). Default model is FP8 weights `allenai/olmOCR-2-7B-1025-FP8` (`pipeline.py:1214`). README documents the same recipe: `vllm serve … --max-model-len 16384` (`README.md:330`). **No `--max-num-seqs` anywhere in the olmOCR repo** (full-repo grep); extra vLLM flags pass through `parse_known_args` → `unknown_args` (`pipeline.py:1272`, `833-834`). Impact: olmOCR's throughput is not tuned via server slot count; it relies on tiny per-request KV (16k cap) plus aggressive client-side inflight. Our pod's `--max-num-seqs 16` at 393k context (`00-baseline.md:65-66`) is the binding constraint for long documents, not a missing olmOCR flag.

- [CRITICAL] Client concurrency is decoupled from server slot math: global `asyncio.BoundedSemaphore(args.max_concurrent_requests)` default **1600** (`pipeline.py:88`, `1224`, `1289`), acquired per HTTP completion in `try_single_page` (`pipeline.py:184-185`). Default **20 workers** pull work items (`pipeline.py:1223`, `1457-1459`); within each PDF **all pages launch concurrently** via `asyncio.TaskGroup` (`pipeline.py:548-551`). External providers run `--workers 1 --max_concurrent_requests 20` (`README.md:339-341`). Impact: olmOCR achieves H100 3050 output tok/s (`05-web.md:38-39`) because requests are page-scoped (~3–8k image tokens + ≤8k output, `pipeline.py:107`, `144`) under a 16k server cap (`pipeline.py:162`, `202-203`), not because it raises `max-num-seqs`. Our unit checks send **full `candidate_md` per call** (`00-baseline.md:43-44`, `unit_judge.py:776`), so the same 1600 client semaphore would OOM or queue forever on a 393k MoE pod. Quality risk: lowering client concurrency alone saves wall but does not change findings.

- [HIGH] Server monitoring parses vLLM stdout: regex on `Running: (\d+)` and `(?:Waiting|Pending):\s*(\d+)` updates global `vllm_queued_requests` (`pipeline.py:868-880`, `81-82`). When queue depth hits 0, failed page retries fire in parallel (`pipeline.py:345-363`). Fatal log line `Detected errors during sampling` → `sys.exit(1)` (`pipeline.py:861-863`). Peak running requests logged (`pipeline.py:871-873`). Metrics reporter every 10 s (`pipeline.py:983-989`). Impact: queue-aware retry parallelism is portable and could shave retry wall on our lane (~55 retries, `00-baseline.md:18`) with zero verdict drift if gated on existing queue telemetry. Quality risk: low if retry logic unchanged.

- [HIGH] Slot math — olmOCR vs tapetum (KV slots ≈ GPU KV budget ÷ tokens per active sequence, capped by `max-num-seqs`):

  | Dimension | olmOCR | tapetum-llm (alliance-pod) |
  |---|---|---|
  | `max_model_len` | 16 384 (`pipeline.py:1255`) | 393 216 (`00-baseline.md:65-66`, `SERVICES.toml:69`) |
  | Server `--max-num-seqs` | not set (vLLM default) | 16 (`00-baseline.md:66`) |
  | Client inflight cap | 1 600 (`pipeline.py:1224`) | 32 papers × serial 6 calls/paper (`00-baseline.md:34-38`) |
  | Payload per call | one page image + prompt (`pipeline.py:106-146`) | full PDF text + full markdown × ~6 (`00-baseline.md:43-45`) |
  | Typical sequence tokens | ~4–12k (image + ≤8k output) | ~15–80k+ input on unit checks (full md + page; P2728R11 2.5 MB md per throughput study) |

  **olmOCR effective slots:** 16k cap means each concurrent page reserves at most 16k KV tokens; with ~8k average active length, one H100 can sustain tens to hundreds of concurrent page decodes — client semaphore 1600 is the practical ceiling (`pipeline.py:1224`), not `--max-num-seqs`.

  **Our effective slots today:** 16 server slots × long sequences. Implied wall from baseline: 2 284 calls × ~20 s ÷ 16 ≈ 2 855 s (`00-baseline.md:22-24`). Unit checks alone: 1 510 × 20 ÷ 16 ≈ **1 888 s** (~63% of cold run).

  **Hypothesis — second short-context pod for unit checks only:** If operator provisions a second instance with `max_model_len=16384` (or 32 768) and `--max-num-seqs 64` (4× slots, conservative vs olmOCR's unset default), **and** unit-check input is scoped to ≤12k tokens (page section + headings packet, not full md), unit-check wall drops to 1 510 × 20 ÷ 64 ≈ **472 s**, saving ~**1 416 s (~47% of 3 003 s cold run)**. Remaining ~774 calls on the 393k pod at 16 slots ≈ 968 s → projected **~1 440 s (~24 min)** total. **Without payload scoping, a 16k instance rejects or truncates >80% of papers** — the second pod is useless. Quality risk: **high** if truncation drops evidence the judge needs; **medium** if scoping preserves the same source page + structural packet already used by routing.

- [MED] `gpu_memory_utilization` is optional in the main pipeline (no default) but bench runner sets **0.8** (`run_olmocr_pipeline.py:30`, `pipeline.py:1252-1253`). OOM guidance explicitly pairs `--gpu_memory_utilization 0.80 --max_model_len 16384` (`pipeline.py:1282-1284`). Beaker jobs cap container memory at 125 GB (`pipeline.py:1092`). Impact: on a shared pod we cannot tune utilization; on a dedicated short-context judge pod, 0.8 + 16k is the olmOCR-proven starting point. Quality risk: none.

- [MED] Health semantics differ by entrypoint: production pipeline uses **`GET /v1/models`** (`pipeline.py:932-944`); benchmark scripts use **`GET /health`** with 600 s timeout (`scripts/run_server_benchmark.sh:245-252`, `scripts/run_qianfan_benchmark.sh:207-212`). PII sub-pipelines add a **semaphore bootstrap**: release worker gate if queue empty 30 s (`scripts/pii/tagging_pipeline.py:474-477`, `765-767`) — not used in main OCR pipeline. Impact: `/models` polling is what we should mirror for RunPod readiness checks. Quality risk: none.

- [LOW] In-process validation mirrors server cap: `MODEL_MAX_CONTEXT = 16384`; responses with `total_tokens > MODEL_MAX_CONTEXT` marked invalid and retried (`pipeline.py:162-163`, `202-203`). Impact: olmOCR refuses to accept over-cap outputs rather than silently truncating — aligns with our fail-closed semantics. Quality risk: none.

## False-pass hypothesis

Routing unit checks to a 16k-context pod **without** payload scoping: vLLM truncates or rejects the prefill, the judge returns empty or schema-minimal output, and the 70% zero-defect rate (`00-baseline.md:29-30`) rises further — table/heading defects on pages buried after the truncation window would stop surfacing, silently upgrading conversions that today land in `review`.

## False-fail hypothesis

Splitting unit checks onto a second pod with a **different model** (e.g. dense 32B on `h200-qwen3-32b`, `00-baseline.md:70-71`) while keeping monolith on DeepSeek V4: cross-model disagreement on borderline heading drift could push more papers into `fail` or `review` even when the monolith pass would have held, unless calibration proves equivalent defect recall on the holdout corpus.

## What would change my mind

A measured A/B on 50 held-out papers: same scoped unit-check payload on (a) alliance-pod 393k/16-seq vs (b) a dedicated 16k/64-seq DeepSeek instance, reporting defect-group recall and verdict agreement ≥99% — would flip verdict to **usable** if wall drops ≥3× on unit checks with no recall loss.
