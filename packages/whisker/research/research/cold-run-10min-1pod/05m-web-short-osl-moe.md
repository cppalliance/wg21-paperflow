# 05m - Web: short-OSL MoE scheduler flags (seqs=16)

**Verdict:** usable-with-conditions — V1 already decode-prioritizes via chunked prefill; the win is MBT/MTP/CUDA-graph decode path, not disabling chunked prefill or flipping `--scheduling-policy`.
**Confidence:** high (official vLLM optimization + EP docs; DeepSeek-V4-Pro recipe; prior measured 16→32 regression)

Workload assumed: many concurrent short completions (OSL 50–200) on MoE (DeepSeek-V4-Pro class) at fixed `--max-num-seqs 16`, longish judge prefills, single pod. S_eff stays 16.

## Findings

- [CRITICAL] **Do not turn chunked prefill off for short-OSL concurrency.** Evidence: vLLM optimization docs (V1: chunked prefill enabled by default; decode requests batched before prefills; remaining `max_num_batched_tokens` budget fills with prefill chunks) — https://docs.vllm.ai/en/stable/configuration/optimization/ ; issue #18547 (V1 cannot disable chunked prefill; simulate "no chunk" only by maximizing MBT) — https://github.com/vllm-project/vllm/issues/18547 . Impact: decode-first scheduling is exactly what many concurrent short generations need; `--no-enable-chunked-prefill` is a no-op / error on V1 and would reintroduce prefill-starves-decode behavior if it worked.

- [CRITICAL] **At seqs=16, raise `--max-num-batched-tokens` (MBT) to 16384; do not raise `--max-num-seqs`.** Evidence: official DeepSeek-V4-Pro recipe pins `--max-num-seqs 16 --max-num-batched-tokens 16384` — https://recipes.vllm.ai/deepseek-ai/DeepSeek-V4-Pro ; docs: MBT >8192 for throughput, smaller MBT (e.g. 2048) for ITL — same optimization page; measured 16→32 = +57% wall (`research/slots-32-regression/SYNTHESIS.md`, `00-baseline.md`). Impact: packs more prefill+decode tokens per step under a 16-seq ceiling; raising seqs regresses MoE decode fan-out.

- [HIGH] **V1's internal priority is decode-over-prefill, not `--scheduling-policy priority`.** Evidence: chunked-prefill policy "batches all pending decode requests before scheduling any prefill" (optimization docs); `--scheduling-policy {fcfs,priority}` only reorders admission by request `priority` field (lower = sooner) — https://docs.vllm.ai/en/v0.8.5.post1/serving/engine_args.html . Impact: for a uniform short-OSL fleet, leave FCFS; priority policy helps only if the client tags latency-critical calls. Short-OSL MoE does not need `--scheduling-policy priority` to get decode-first behavior.

- [HIGH] **Short-OSL decode path: MTP k=1 + FULL_DECODE_ONLY CUDA graphs.** Evidence: recipe Spec Decoding toggle for low latency / small batch; MTP docs start with `num_speculative_tokens: 1` — https://docs.vllm.ai/en/latest/features/speculative_decoding/mtp/ ; recipe `compilation-config` uses `"cudagraph_mode": "FULL_DECODE_ONLY"`; prior ops checklist: k=2 hurts short OSL (`research/cold-run-10min/26-server-ops-checklist.md`). Impact: cuts per-call decode wall at OSL 50–200 without widening the 16-seq batch.

- [MED] **MoE EP extras that help decode-heavy batches (conditional).** Evidence: `--enable-expert-parallel` in recipe; EP deployment recommends `--async-scheduling` (overlap schedule/execute) and, with DP>1 + DeepEP, `--enable-dbo` + `--all2all-backend deepep_low_latency` for decode-dominated work — https://docs.vllm.ai/en/stable/serving/expert_parallel_deployment/ , https://docs.vllm.ai/en/latest/design/dbo/ . Impact: EP already baseline on H200 TEP; async-scheduling is a cheap A/B; DBO/DeepEP low-latency only applies if the pod is DP+EP (not plain TP8+EP), and DeepEP kernels warn mixed prefill/decode can lose.

- [MED] **Co-tune long prefills with `--long-prefill-token-threshold 8192` alongside MBT 16384.** Evidence: prior auditor/checklist ranks this incremental vs MBT alone; optimization docs: MBT≈`max_model_len` ≈ V0 prefill-ish policy while still decode-prioritizing. Impact: stops giant paper prefills from monopolizing the token budget while 16 short decodes are live.

## Flags that help short-OSL MoE at seqs=16

| Flag | Value | Why for OSL 50–200 @ 16 |
|---|---|---|
| `--max-num-seqs` | **16** (hold) | Measured sweet spot; 32 regresses wall |
| `--max-num-batched-tokens` | **16384** | Throughput under decode-first V1 scheduler |
| chunked prefill | **leave on** (V1 default) | Decode-before-prefill; do **not** `--no-enable-chunked-prefill` |
| `--scheduling-policy` | **fcfs** (default) | Priority only if client sets per-request priority |
| `--speculative-config` | `{"method":"mtp","num_speculative_tokens":1}` | Spec decode for short completions; start k=1 |
| `--compilation-config` | `{"mode": 3, "cudagraph_mode": "FULL_DECODE_ONLY"}` | Decode-path CUDA graphs (recipe; mode may be 0/3 by image) |
| `--enable-expert-parallel` | on | MoE EP (recipe baseline) |
| `--long-prefill-token-threshold` | **8192** | Protect short decodes from huge prefills |
| `--async-scheduling` | A/B on | Experimental schedule/execute overlap |
| `--enable-dbo` + `deepep_low_latency` | only if DP>1 + DeepEP | Decode-dominated EP; skip on pure TP+EP |

**Anti-flags (hurt or no-op):**

- `--no-enable-chunked-prefill` — useless/wrong on V1; would worsen concurrent short decode if it worked
- `--max-num-seqs 32` — measured +57% wall
- `--scheduling-policy priority` without client priority tags — no gain
- MTP `num_speculative_tokens: 2+` before acceptance metrics — overhead risk on short OSL
- `deepep_high_throughput` — prefill-oriented; wrong for short-OSL decode pressure

## Minimal launch delta (scheduler / short-OSL slice)

```bash
--max-num-seqs 16 \
--max-num-batched-tokens 16384 \
--long-prefill-token-threshold 8192 \
--enable-expert-parallel \
--speculative-config '{"method":"mtp","num_speculative_tokens":1}' \
--compilation-config '{"mode": 3, "cudagraph_mode": "FULL_DECODE_ONLY"}'
# optional A/B:
# --async-scheduling
```

## False-pass hypothesis

Ops enables MTP k=2 and reports "tok/s up" from a solo smoke while fleet JSON retries climb; short-OSL wall looks better in `/metrics` TPOT but cold wall flat or worse from rejection + re-decode.

## False-fail hypothesis

Someone disables chunked prefill (or chases V0) after seeing "chunked_prefill=True" in logs, attributes TTFT blips to chunking, and loses decode-first batching under c=16 — short completions stretch while prefills monopolize steps.

## What would change my mind

- Pod A/B at fixed seqs=16 showing MBT 8192 beats 16384 on cold wall for this exact judge mix (would imply ITL-bound, not token-budget-bound).
- Client-tagged priority classes with measured head-of-line wins vs FCFS on the same short-OSL mix.
- Single-node TP8+EP proving `--enable-dbo` without DP>1 (docs currently require DP>1).

## Arithmetic note (S_eff=16)

Scheduler flags cut **L** (per-call decode/prefill), not S:

`wall ≈ (N_rem × L_eff) / 16 + T + C − L_abs`

Expected L cut from MBT+MTP+CUDA-graph decode path is the ops envelope already ranked in `research/cold-run-10min/26-server-ops-checklist.md` (~300–550 s combined), not a path to S=32.
