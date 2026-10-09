# 05c - Web forage: MoE batching vs decode latency (2026-07-24)

**Question:** Why does raising `max-num-seqs` hurt MoE (DeepSeek-V3/V4, Mixtral)
decode latency, and which operator knobs help **without** raising seq slots?

**Constraint (from 00-baseline):** server slots 16 is settled; 32 slots was
**+57% wall** and is forbidden. Cards below prioritize alternatives.

Reddit signal was thin (no durable LocalLLaMA threads with numbers). Primary
sources: vLLM GitHub issues/RFCs, vLLM docs/recipes/blogs, ROCm MoE playbook,
XShare / Paralleliq operator writeups.

---

## Mechanism cards (why more seq slots hurt MoE decode)

- **[CRITICAL] Expert-union HBM blowup with decode batch (XShare RFC #35550 + arXiv 2602.07265)**
  https://github.com/vllm-project/vllm/issues/35550
  https://arxiv.org/abs/2602.07265
  During MoE decode, each step loads expert weights from HBM for every
  activated expert. Per-token top-k is small (DeepSeek k=8 of 256), but the
  **union** of experts across the batch grows with concurrent decode tokens:
  DeepSeek-R1 measured **163/256 experts at batch=32, 243/256 at batch=64**.
  Raising `max-num-seqs` directly raises that union → more HBM traffic per
  decode step → worse TPOT/ITL even when aggregate tok/s rises. This is the
  MoE-specific reason denser batching hurts per-request decode more than on
  dense models.

- **[HIGH] Larger schedule batch dilutes per-request compute (vLLM #17598)**
  https://github.com/vllm-project/vllm/issues/17598
  Fixed request-rate=16: `max-num-seqs` 16→32 raised mean TPOT 8.23→9.41 ms
  and ITL similarly (~14%). Maintainer explanation: `max-num-seqs` is how many
  sequences share one scheduling step; more concurrent work per step = less
  SM time per sequence. Pattern is general; MoE amplifies it via expert-union
  + collectives (next cards).

- **[HIGH] EP all-to-all + expert imbalance stragglers (vLLM wide-EP blog)**
  https://vllm.ai/blog/2025-12-17-large-scale-serving
  With `--enable-expert-parallel`, decode tokens are dispatched via all-to-all.
  Real traffic is not train-balanced: some EP ranks idle while others process
  large expert batches; the slowest rank gates the whole EP group. Bigger
  decode batches enlarge imbalance variance and collective volume. EPLB exists
  specifically because of this.

- **[HIGH] EP routing fluctuations at high concurrency (vLLM GB300 DeepSeek blog)**
  https://vllm.ai/blog/2026-02-13-gb300-deepseek
  EP can beat TP on decode TPOT under output-heavy load, but the EP curve
  **fluctuates** from unbalanced expert routing (varying expert load and
  all-to-all volume batch-to-batch). Raising concurrency without EPLB/DBO
  widens those spikes → p95/p99 decode latency pain.

- **[HIGH] Prefill in same EP group stalls all decode (wide-EP + DistServe)**
  https://vllm.ai/blog/2025-12-17-large-scale-serving
  One compute-bound prefill in an EP group forces dummy/sync work on unused
  ranks so combine collectives stay aligned. Higher `max-num-seqs` admits more
  mixed prefill+decode into the same step → decode ITL suffers. Disaggregated
  P/D is the structural fix (not more slots).

- **[MED] MoE VRAM headroom / preemption cascades (Paralleliq)**
  https://www.paralleliq.ai/blog/why-moe-models-break-your-vllm-configuration
  Weights ≈ total params (671B-class), not active params. KV budget after load
  is tight. High `max-num-seqs` → KV pressure → preemption/recompute. MoE
  recompute is expensive. Operator advice: start DeepSeek V3 on 8×H100 at
  `max-num-seqs` **4–8**, not dense-model 32–64. Aligns with our forbid-32
  finding even if their absolute numbers are conservative for H200.

- **[MED] Kernel path flips with concurrency (vLLM #28882, #41306)**
  https://github.com/vllm-project/vllm/issues/28882
  https://github.com/vllm-project/vllm/issues/41306
  DeepGEMM / FlashInfer MoE backends have batch-size sweet spots. Low-conc
  decode can fall into slow Triton paths (or vice versa after v0.20 flashinfer
  default). Raising `max-num-seqs` changes which kernel wins without operator
  intent. Fix is backend env flags, not more slots.

- **[MED] Ultra-sparse MoE: AllToAll can exceed benefit (ROCm MoE playbook)**
  https://rocm.blogs.amd.com/software-tools-optimization/vllm-moe-guide/README.html
  At ~0.78% activation density (Llama-4-Maverick), EP=0 beat EP=1 by 7–12%.
  Activation density = (experts_per_token / total_routed) × 100. DeepSeek
  ~3.13% still wants EP+DP for MLA KV reasons, but the same physics applies:
  more tokens in flight → more AllToAll relative to useful GEMM.

---

## Operator knobs that are NOT raising seq slots

Ranked for **decode-latency / cold-fleet wall** on DeepSeek-class MoE judges.
Do **not** raise `--max-num-seqs` / server slots as the first move.

### Tier A — try first on alliance-pod / H200 DeepSeek

- **[CRITICAL] `--enable-expert-parallel` + DP (TP=1) for MLA MoE**
  https://docs.vllm.ai/en/stable/serving/expert_parallel_deployment/
  https://recipes.vllm.ai/deepseek-ai/DeepSeek-V3.2-Exp
  `EP_SIZE = TP_SIZE × DP_SIZE`. Recipe default: `-dp 8 --enable-expert-parallel`
  (kernels optimized for TP=1). Why it helps without more seqs: DP attention
  **partitions** MLA KV (TP duplicates latent KV ×TP → starves concurrency
  budget). Same slot count, more effective KV / less weight traffic per rank.
  Fallback: plain `-tp 8` if EP hangs (more robust, usually slower).

- **[HIGH] `--all2all-backend deepep_low_latency` (decode-dominated)**
  https://docs.vllm.ai/en/stable/serving/expert_parallel_deployment/
  Backend matrix: `deepep_low_latency` = CUDA-graph-friendly, masked layout,
  decode-oriented. Use `deepep_high_throughput` only on prefill-heavy /
  disagg prefiller. Wrong backend at our decode-heavy mix inflates ITL without
  touching seq slots.

- **[HIGH] `--enable-dbo` (dual-batch overlap) + decode token threshold**
  https://vllm.ai/blog/2025-12-17-large-scale-serving
  Overlaps MoE dispatch/combine collectives with compute via microbatches.
  Profiled DeepSeek decode: without DBO, MoE Dispatch/Combine dominates;
  with DBO, ranks yield across microbatches. Knob:
  `--dbo-decode-token-threshold` (collective agrees microbatching is worth it).
  Directly attacks EP communication tax that grows with batch — without
  needing more slots.

- **[HIGH] `--enable-eplb` (+ async eplb-config)**
  https://docs.vllm.ai/en/stable/serving/expert_parallel_deployment/
  https://github.com/vllm-project/vllm/pull/43219
  Rebalances logical→physical expert placement from sliding-window load stats.
  Params: `window_size`, `step_interval`, `num_redundant_experts`,
  `use_async=true` (default in recent trees; sync EPLB stalls decode).
  Example shape:
  `--enable-eplb --eplb-config '{"window_size":100,"step_interval":1000,"num_redundant_experts":32,"use_async":true}'`
  Cuts straggler rank time when routing is skewed — the failure mode that
  high `max-num-seqs` worsens.

- **[HIGH] Tune `--max-num-batched-tokens` independently of `--max-num-seqs`**
  https://recipes.vllm.ai/deepseek-ai/DeepSeek-V3.2-Exp
  https://axiomlogica.com/ai-ml/vllm-mixtral-deepseek-v3-expert-parallelism
  Recipe sweet spots cited: **8192** (V3.2-Exp advanced), **16384**
  (DeepSeek-V4-Pro prior card in tapetum 05-web), ROCm example **32768**.
  This is the **token budget per engine step** (prefill chunking + mixed
  batches), not the sequence slot ceiling. Raising it can improve prefill
  efficiency / APC packing **at fixed seqs**. Lowering it reduces peak
  per-step MoE+KV pressure when decode ITL spikes. Sweep this before slots.

- **[HIGH] MTP speculative decode (not more concurrency)**
  Prior card (tapetum 05-web) + GB300 blog:
  `--speculative-config '{"method":"mtp","num_speculative_tokens":1|2}'`
  Amortizes MoE weight traffic across accepted draft tokens. Helps decode
  tok/s at moderate concurrency; weak when OSL very short. Orthogonal to
  `max-num-seqs`.

- **[HIGH] `--kv-cache-dtype fp8` (long prompts) / bf16 (short)**
  https://recipes.vllm.ai/deepseek-ai/DeepSeek-V3.2-Exp
  FP8 KV: more tokens cached at same VRAM → fewer preemptions at fixed
  `max-num-seqs`. Quant/dequant overhead; recipe says bf16 for short, fp8 for
  long. Our judge prompts are long-document → fp8 is the latency-stability
  play, not "add slots".

### Tier B — topology / scheduling / kernel hygiene

- **[HIGH] `--async-scheduling`**
  https://vllm.ai/blog/2025-12-17-large-scale-serving
  Overlaps CPU schedule with GPU execute; shrinks decode bubbles. Default in
  newer vLLM; disable with `--no-async-scheduling` only for A/B.

- **[MED] `--decode-context-parallel-size` (MLA only)**
  https://recipes.vllm.ai/deepseek-ai/DeepSeek-V3.2-Exp
  Shards KV at decode across TP ranks. Cap:
  `DCP ≤ tensor_parallel_size / num_kv_heads`. Helps long-context decode
  memory traffic without raising seq slots. Only if still on TP path.

- **[MED] MoE backend / DeepGEMM env toggles (low-conc decode)**
  https://github.com/vllm-project/vllm/issues/28882
  https://github.com/vllm-project/vllm/issues/41306
  - `VLLM_MOE_USE_DEEP_GEMM=0` when DeepGEMM hurts low concurrency
  - `--moe-backend=triton` if v0.20+ FlashInfer default regresses MoE
  - `VLLM_USE_FLASHINFER_MOE_FP8=1` when FlashInfer path is the winner
  Pick via nsys / bench at **our** concurrency (16), not blog defaults.

- **[MED] Lower `--max-model-len` to actual p99 (frees KV at fixed seqs)**
  Paralleliq + axiomlogica operator guides. Same 16 slots, less preemption,
  more stable decode. Do not reserve 128k/1M if judges never need it.

- **[MED] Conservative `--gpu-memory-utilization` (0.80–0.90 MoE)**
  Avoids KV oversubscription that forces preemption under burst. Opposite of
  "crank util + crank seqs".

- **[MED] TP+EP for low-conc latency vs DP+EP for high-QPS**
  https://rocm.blogs.amd.com/software-tools-optimization/vllm-moe-guide/README.html
  TP+EP: better interactive latency at low concurrency (ROCm: +52% throughput
  vs DP+EP at 64–128 req). DP+EP: larger effective batch / KV at high QPS.
  Our cold fleet is latency-of-16-slots constrained → confirm whether pod is
  already DP+EP; if stuck on pure TP without EP, enable EP before touching
  slots. JarvisLabs: EP+TP=4 beat no-EP on Qwen3.5 MoE TPOT; EP+DP can
  collapse at specific concurrency cliffs — measure.

- **[MED] Prefill/decode disaggregation + matching all2all backends**
  Prefiller: `deepep_high_throughput`. Decoder: `deepep_low_latency`.
  Removes prefill from the decode EP critical path. Large infra change;
  highest ceiling after single-node knobs.

### Tier C — experimental / model-gated (do not block 10-min plan)

- **[LOW–MED] `--moe-config` XShare pruning** (`expert_budget`, decode-only)
  https://github.com/vllm-project/vllm/pull/35551
  +53% tok/s at c=32 on GPT-OSS-120B in draft results. **Prefill pruning
  destroys quality** (MMLU-Pro 51→27). DeepSeek/Mixtral support was roadmap
  at RFC time — verify HEAD before relying. Quality-gated for our judges.

- **[LOW] Activation-density check before EP on non-MLA MoE**
  ROCm table: Mixtral-class density may want EP; ultra-sparse may not.
  DeepSeek MLA: still want EP+DP for KV reasons regardless.

---

## Anti-knobs (explicitly do not do these for decode latency)

| Anti-knob | Why |
|-----------|-----|
| Raise `--max-num-seqs` / server slots 16→32 | Expert-union HBM + diluted per-seq SM time; our 00-baseline +57% wall |
| Raise client `c` >32 without new evidence | Proxy/timeout risk (00-baseline) |
| `deepep_high_throughput` on decode-heavy mixed node | Wrong DeepEP kernel for TPOT |
| Sync EPLB / frequent `step_interval` without `use_async` | CPU stalls on decode path |
| Speculative / MTP with capture size not multiple of `(k+1)` | Falls off CUDA-graph path (DeepSeek-V4 capture truncation reports) |
| Prefill XShare pruning | Corrupts KV; hard quality fail |

---

## Best-of shortlist for this cold-run (no seq-slot raise)

1. Confirm pod topology: **DP + `--enable-expert-parallel`** (TP=1) if not already.
2. Decode path: **`--all2all-backend deepep_low_latency`** + **`--enable-dbo`**.
3. Skewed experts: **`--enable-eplb`** with **`use_async: true`**.
4. Sweep **`--max-num-batched-tokens`** at fixed `max-num-seqs=16` (8k / 16k / 32k).
5. Keep **fp8 KV** + **MTP k=1–2** if acceptance stays high on judge prompts.
6. MoE backend A/B at c=16: DeepGEMM on/off, triton vs flashinfer.
7. Only if still bound: P/D disagg — still not more slots.

---

## Source index

| Source | URL |
|--------|-----|
| XShare RFC | https://github.com/vllm-project/vllm/issues/35550 |
| XShare paper | https://arxiv.org/abs/2602.07265 |
| max-num-seqs TPOT issue | https://github.com/vllm-project/vllm/issues/17598 |
| Wide-EP / DBO / EPLB blog | https://vllm.ai/blog/2025-12-17-large-scale-serving |
| GB300 DeepSeek EP vs TP | https://vllm.ai/blog/2026-02-13-gb300-deepseek |
| EP deployment docs | https://docs.vllm.ai/en/stable/serving/expert_parallel_deployment/ |
| DeepSeek-V3.2-Exp recipe | https://recipes.vllm.ai/deepseek-ai/DeepSeek-V3.2-Exp |
| ROCm MoE playbook | https://rocm.blogs.amd.com/software-tools-optimization/vllm-moe-guide/README.html |
| Paralleliq MoE config | https://www.paralleliq.ai/blog/why-moe-models-break-your-vllm-configuration |
| Mixtral/DeepSeek EP guide | https://axiomlogica.com/ai-ml/vllm-mixtral-deepseek-v3-expert-parallelism |
| DeepGEMM low-conc | https://github.com/vllm-project/vllm/issues/28882 |
| v0.20 MoE backend reg | https://github.com/vllm-project/vllm/issues/41306 |
| Async EPLB default | https://github.com/vllm-project/vllm/pull/43219 |
| JarvisLabs EP strategies | https://jarvislabs.ai/blog/expert-parallelism-mixed-strategies-vllm |
| DP attention + EP RFC | https://github.com/vllm-project/vllm/issues/16037 |

---
Cards: mechanism + operator knobs. Feeds cold-run synthesis; no seq-slot raise.
