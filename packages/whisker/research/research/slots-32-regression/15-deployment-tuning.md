# 15 - Deployment-Tuning-Scout

**Verdict:** revert-to-16 | Doubling `--max-num-seqs` without proportional scheduler co-tuning regressed measured wall time 57% on this MoE+393k-KV stack; production configs cluster at 8–16, not 32.
**Confidence:** high
## Findings

- [HIGH] Published DeepSeek H200×8 configs cap `--max-num-seqs` at **8–16**, not 32+. Evidence: alliance-pod launch template `https://raw.githubusercontent.com/cppalliance/runpod/master/templates/deepseek/H200SXM.txt` (`--max-num-seqs 16`, TP8+EP, `--max-model-len 393216`, no explicit MBT); GitHub #42265 production V4-Pro dump (`--max-num-seqs 8`, `--max-num-batched-tokens 8196`, same 393k context) `https://github.com/vllm-project/vllm/issues/42265`; Paralleliq MoE guide recommends **4–8** on 8×H100 for DeepSeek V3 `https://www.paralleliq.ai/blog/why-moe-models-break-your-vllm-configuration`. Impact: 32 is above every corroborated H200 DeepSeek deployment; the measured 692.3s→1090.2s regression is consistent with overslotting.

- [HIGH] Official vLLM DeepSeek recipes benchmark with **16 concurrent prompts**, not 32, and omit high `--max-num-seqs` in serve commands. Evidence: DeepSeek-V3/R1 recipe `https://docs.vllm.ai/projects/recipes/en/latest/DeepSeek/DeepSeek-V3.html` (`--num-prompts 16` in bench; serve uses TP8+EP only); vLLM large-scale blog `https://blog.vllm.ai/2025/12/17/large-scale-serving.html` (Wide-EP throughput gains come from DP+EP and DBO/EPLB, not raising per-node seq cap). Impact: community "default 1024" (`ROCm vLLM optimization doc`) is irrelevant for memory-bound MoE; tuned deployments explicitly **lower** the cap.

- [HIGH] Raising `--max-num-seqs` without raising `--max-num-batched-tokens` starves the scheduler token budget and amplifies MoE EP overhead. Evidence: vLLM optimization docs `https://docs.vllm.ai/en/stable/configuration/optimization/` (V1 prioritizes decodes; prefills consume MBT budget; smaller MBT favors ITL, larger favors throughput); ROCm tuning `https://rocm.docs.amd.com/en/latest/how-to/rocm-for-ai/inference-optimization/vllm-optimization.html` (online default MBT **8192**; offline throughput MBT **≥32k**; MBT should be swept with seq count). H200SXM.txt sets **no** `--max-num-batched-tokens`, so 0.24 likely runs MBT≈8192. At 32 seqs that is ~256 tokens/seq/prefill-chunk vs ~512 at 16. Impact: doubling seqs without doubling MBT (16k→32k minimum) increases prefill fragmentation and decode-step width without extra token throughput; MoE all-to-all scales with concurrent sequences (blog: single heavy prefill blocks entire EP group).

- [HIGH] `--max-model-len 393216` forces conservative scheduling; doubling seqs doubles reserved KV headroom. Evidence: ROCm doc `KV-cache token requirements are computed as max-num-seqs * max-model-len`; Paralleliq (long 1M context "single sequence can consume entire remaining KV cache"); GitHub #18681 maintainer guidance (~MBT should be ~¼ of max-model-len for headroom, i.e. ~98k at 393k, vs actual ~8k). Impact: at 393k, each +1 to `--max-num-seqs` is expensive; 32 reserves **2×** the worst-case KV envelope of 16, increasing preemption/eviction pressure on a stack already near VRAM ceiling (`gpu-memory-utilization 0.95`, full MoE weights resident).

- [MED] `--long-prefill-token-threshold` and partial-prefill limits are the correct co-tune for mixed 3k–100k prompts, but they do not rescue an overshot seq cap alone. Evidence: vLLM PR #31330 `https://github.com/vllm-project/vllm/pull/31330` (threshold best set **near max-num-batched-tokens**; `max_long_partial_prefills` prevents long prefills starving the queue); Red Hat args doc (default threshold ≈4% of context when unset). Impact: useful **after** reverting to 16 or **during** a controlled 32 retune; not a substitute for MBT+seq co-scaling.

- [LOW] `--enable-ep-weight-filter` does not affect runtime throughput. Evidence: vLLM PR #37351 `https://github.com/vllm-project/vllm/pull/37351` (skips non-local expert **disk I/O at load** only); H200SXM.txt already enables it. Impact: disabling it would not explain or fix the 57% regression; it is unrelated to decode scheduling.

- [MED] Raising `--max-num-seqs` alone can make throughput **worse**, not just plateau. Evidence: continuous-batching case study `https://dev.to/marcuswwchen/continuous-batching-wrecked-our-p99-latency-heres-the-trace-42d1` (raising max_num_seqs to 256 **made things worse** under KV pressure); local sweep `packages/whisker/research/llm-batching/20-sweep-results.md` (client c=32 with server cap **16** yielded 692.3s; server cap **32** yielded 1090.2s). Impact: 16 is not merely a safe default; it is the measured sweet spot for this pod/workload.

## Concrete recommendation for the operator (exact flags)

**Primary (do now): revert server to 16 and keep client concurrency ≤32.**

```bash
vllm serve deepseek-ai/DeepSeek-V4-Pro \
  --tensor-parallel-size 8 \
  --enable-expert-parallel \
  --enable-ep-weight-filter \
  --max-model-len 393216 \
  --max-num-seqs 16 \
  --max-num-batched-tokens 8192 \
  --long-prefill-token-threshold 8192 \
  --max-num-partial-prefills 2 \
  --max-long-partial-prefills 1 \
  --kv-cache-dtype fp8 \
  --gpu-memory-utilization 0.95 \
  --trust-remote-code \
  --served-model-name deepseek-v4-pro \
  --reasoning-parser deepseek_v4 \
  --enable-auto-tool-choice \
  --tool-call-parser deepseek_v4
```

Rationale: restores the proven H200SXM cap; makes MBT explicit (matches V4-Pro production 8196 pairing at seq=8, scaled to seq=16); adds long-prefill guardrails for 3k–100k prompts without widening the MoE decode fan-out.

**Optional A/B only if revert is insufficient (low prior): retune 32 with full triangle co-scale, one restart + 381-paper rerun.**

```bash
  --max-num-seqs 32 \
  --max-num-batched-tokens 32768 \
  --long-prefill-token-threshold 16384 \
  --max-num-partial-prefills 4 \
  --max-long-partial-prefills 1
```

Accept retune only if wall time beats **692.3 s** by ≥10% with 0 proxy timeouts. Do **not** ship 32 on MBT≤8192 alone.

**Do not expect fixes from:** `--no-enable-ep-weight-filter` (load-time only); raising seqs without MBT; `--max-num-seqs 64+` (DeepSeek V3.2 recipe's 256 example is DP8+EP on different parallelism, not TP8+EP at 393k).

## What would change my mind

1. A controlled A/B on the same 381-paper corpus showing `--max-num-seqs 32` with `--max-num-batched-tokens 32768` (+ long-prefill co-tune above) beats **692.3 s** by ≥10% with stable error rate (no RunPod proxy kills).
2. Nsight/DeepEP trace proving decode is compute-bound (not all-to-all bound) at 32 concurrent MLA+MoE sequences on this pod.
3. Lowering `--max-model-len` to operational p99 (e.g. 65536–131072 instead of 393216) with measured KV headroom, then re-sweeping seq 16 vs 32 with proportional MBT.
