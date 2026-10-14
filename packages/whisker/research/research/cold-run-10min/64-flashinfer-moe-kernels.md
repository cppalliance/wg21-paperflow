# 64 — FlashInfer / fused MoE / DeepEP (DeepSeek on vLLM)

**Query:** Can ops enable FlashInfer fused MoE kernels and/or DeepEP so that
**effective tok/s rises** on DeepSeek (alliance-pod: V4-Pro, 8×H200, EP) **without
changing `--max-num-seqs`**?

**Constraint:** `max-num-seqs=16` is settled; 16→32 was +57% cold wall
(`slots-32-regression`). Do not recommend raising slots.

**Ops-actionable: YES**

(DeepEP decode backend + dual-batch overlap are pod-restart flags independent of
seq slots. FlashInfer fused MoE is *also* ops-flippable, but is **not** the
default V4-Pro H200 win and can regress — A/B only.)

---

## Finding cards

### 1. DeepEP all2all is an ops flag; orthogonal to max-num-seqs

- **Title:** Expert Parallel Deployment — vLLM
- **URL:** https://docs.vllm.ai/en/stable/serving/expert_parallel_deployment/
- **Summary:** With `--enable-expert-parallel`, ops pick the dispatch/combine
  path via `--all2all-backend`. Matrix includes default
  `allgather_reducescatter`, `deepep_high_throughput` (prefill / high-throughput),
  `deepep_low_latency` (decode, CUDA-graph friendly, masked layout), and
  FlashInfer NVLink variants (MNNVL). Docs also recommend `--enable-dbo` to
  overlap all-to-all with compute, and note DeepEP HT/LL kernels are tuned for
  disaggregated P/D and **may show poor performance for mixed workloads**.
- **Relevance:** HIGH — this is the primary ops lever in the “DeepEP” bucket
  that does not touch `--max-num-seqs`.
- **Alliance-pod note:** H200SXM / prior audits do not pin `--all2all-backend`
  or `--enable-dbo`. If still on default allgather, a decode-oriented
  `deepep_low_latency` + DBO A/B is the first ops experiment at fixed seqs=16.

### 2. Wide-EP blog: DeepEP + DBO cut communication tax at fixed concurrency

- **Title:** vLLM Large Scale Serving: DeepSeek @ 2.2k tok/s/H200 with Wide-EP
- **URL:** https://vllm.ai/blog/2025-12-17-large-scale-serving
- **Summary:** DeepSeek-scale serving gains cite DeepEP high-throughput /
  low-latency all-to-all, dual-batch overlap, EPLB, DeepGEMM, async scheduling.
  Mechanism: EP all-to-all volume and straggler ranks gate decode; overlapping
  dispatch/combine with compute raises effective tok/s **without** needing a
  larger `max-num-seqs`.
- **Relevance:** HIGH for DeepEP+DBO; does not claim FlashInfer MoE alone is
  the H200 decode win.

### 3. FlashInfer fused MoE is real, but CLI/env selection (not free)

- **Title:** Env vars + `--moe-backend` deprecation (vLLM)
- **URLs:**
  - https://docs.vllm.ai/en/v0.10.1/configuration/env_vars.html
  - https://github.com/vllm-project/vllm/pull/43148
  - https://github.com/vllm-project/vllm/pull/36838
- **Summary:** Ops can force FlashInfer fused MoE via
  `VLLM_USE_FLASHINFER_MOE_FP8=1` / `_FP16=1` / `_FP4=1` and
  `VLLM_FLASHINFER_MOE_BACKEND=throughput|latency` (CUTLASS vs TRTLLM). Newer
  trees deprecate those envs in favor of `--moe-backend
  flashinfer_{cutlass,trtllm,cutedsl}`. PR #36838 shows FlashInfer CUTLASS /
  TRTLLM selectable under DP+EP (with later illegal-mem caveats on some
  Cutlass+DP combos).
- **Relevance:** MED for alliance-pod — knobs exist and do not change
  `max-num-seqs`, but selection must match checkpoint dtype + GPU gen.

### 4. Official V4-Pro H200 recipe does **not** enable FlashInfer MoE

- **Title:** deepseek-ai/DeepSeek-V4-Pro recipe YAML
- **URL:** https://github.com/vllm-project/recipes/blob/main/models/deepseek-ai/DeepSeek-V4-Pro.yaml
- **Summary (verified 2026-07-10 recipe):** Hopper override pins
  `--max-num-seqs 16`, `--max-num-batched-tokens 16384`,
  `--no-enable-flashinfer-autotune`, `FULL_DECODE_ONLY` graphs. It does **not**
  set `--moe-backend flashinfer_*` or `VLLM_USE_FLASHINFER_MOE_*`.
  `deep_gemm_mega_moe` is a **Blackwell** FP8-checkpoint override only. NVFP4
  experts cannot use MegaMoE and fall back to the default MoE backend.
  FlashInfer *autotune* is explicitly disabled on H200 (startup cost / stability),
  which is a different switch from FlashInfer *fused MoE*.
- **Relevance:** CRITICAL — “turn on FlashInfer MoE” is **not** the verified
  H200 V4-Pro path. Ops should not treat FlashInfer MoE as a recipe default.

### 5. Wrong MoE backend at our concurrency can *lose* tok/s

- **Title:** [H200] DeepSeek-R1 EP MoE backend behavior (#28882)
- **URL:** https://github.com/vllm-project/vllm/issues/28882
- **Summary:** On H200 EP DeepSeek-R1, DeepGEMM vs Triton/FlashInfer MoE has
  concurrency sweet spots. Low concurrency fell off DeepGEMM (M&lt;128) into
  Triton; forcing FlashInfer / disabling DeepGEMM changed which phase won.
  Mis-selection produced **~1.5× worse TTFT** even when high-concurrency
  throughput looked ~1.06× better. Operator pattern from the issue:
  `VLLM_MOE_USE_DEEP_GEMM=0` + optional `VLLM_USE_FLASHINFER_MOE_FP8=1` — measure
  at the target concurrency, do not copy blog defaults.
- **Relevance:** HIGH — alliance-pod runs at **seqs=16** (decode-heavy judge
  mix). Backend flips are A/B territory, not “always on.”

### 6. Internal prior: V4 MegaMoE path leaves little FlashInfer headroom

- **Title:** 98-vllm-moe-serving (in-repo)
- **Path:** `research/tapetum-llm-speedup/98-vllm-moe-serving.md`
- **Summary:** DeepSeek-V4-Pro decode path in the cloned vLLM tree is MLA +
  MegaMoE/`deep_gemm.fp8_fp4_mega_moe` (+ optional EPLB). Prior verdict: decode
  is HBM-bound on MLA KV + expert reads; **little headroom from MoE backend
  swaps alone**. DeepEP/DBO attack the all2all tax; they do not remove
  expert-union growth when slots rise (slots stay forbidden).
- **Relevance:** HIGH for scoping expectations — FlashInfer fused MoE is
  unlikely to be a large cold-wall lever on this checkpoint if MegaMoE is
  already selected.

### 7. Sibling forage already ranked DeepEP ahead of FlashInfer MoE

- **Title:** 05c-web-moe-batching
- **Path:** `research/cold-run-10min/05c-web-moe-batching.md`
- **Summary:** Tier A at fixed seqs: DP+EP, `deepep_low_latency`, `--enable-dbo`,
  EPLB, MBT sweep, MTP, fp8 KV. FlashInfer / DeepGEMM toggles are Tier B
  (“A/B at c=16”). Anti-knob: `deepep_high_throughput` on a decode-heavy mixed
  node.
- **Relevance:** HIGH — consistent with this card’s ranking.

---

## Ops action matrix (fixed `--max-num-seqs 16`)

| Knob | How | Expected effect | Risk |
|------|-----|-----------------|------|
| `--all2all-backend deepep_low_latency` | Launch flag + restart | Lower decode all2all / TPOT if EP-bound | Mixed P+D may regress vs default; A/B |
| `--enable-dbo` (+ decode token threshold) | Launch flag + restart | Overlap dispatch/combine with compute | Needs EP; profile before keep |
| `--enable-eplb` (`use_async: true`) | Launch flag + restart | Cut straggler EP ranks | Redundant experts eat KV; numeric drift windows |
| `--moe-backend flashinfer_*` or `VLLM_USE_FLASHINFER_MOE_FP8=1` | Env / flag + restart | Possible GEMM win **if** current backend is wrong for c=16 | **Can lose TTFT/tok/s**; not V4-Pro H200 recipe |
| `VLLM_MOE_USE_DEEP_GEMM=0` | Env + restart | Escape slow DeepGEMM at low M | Prefill/TTFT may worsen (#28882) |
| `--moe-backend deep_gemm_mega_moe` | Launch flag | Blackwell FP8 recipe path | **Not** H200 recipe pin; ignore unless on B200+ |

**Do not do:** raise `--max-num-seqs`; enable `deepep_high_throughput` on the
mixed judge node; flip FlashInfer MoE without a fixed-seqs A/B.

---

## Recommended ops experiment (one restart cycle)

1. Confirm current startup log: `all2all_backend`, `moe_backend` / DeepGEMM /
   FlashInfer MoE selection, `enable_dbo`.
2. If all2all is default: A/B **`--all2all-backend deepep_low_latency
   --enable-dbo`** at **`--max-num-seqs 16`** (same MBT / MTP / KV as baseline).
3. Only if EP+DeepEP still leaves MoE GEMM hot in nsys: A/B
   FlashInfer vs DeepGEMM / MegaMoE at the **same** seqs=16 load shape
   (judge prefill lengths + short structured decode). Keep the winner; revert
   on TTFT or tok/s regression.
4. Pass criterion: higher effective decode tok/s **or** lower cold fleet wall
   at identical client c=32 and identical verdict fingerprints — not “kernel
   selected” alone.

---

## Verdict

**Ops-actionable: YES.** DeepEP (`deepep_low_latency`) + `--enable-dbo` are
the concrete no-seq-raise levers in this topic. FlashInfer fused MoE kernels
are available as ops toggles but are **not** a verified free win for
DeepSeek-V4-Pro on H200; treat them as a measured fallback, not a default enable.

---

## Source index

| Source | URL / path |
|--------|------------|
| EP / DeepEP docs | https://docs.vllm.ai/en/stable/serving/expert_parallel_deployment/ |
| Wide-EP blog | https://vllm.ai/blog/2025-12-17-large-scale-serving |
| V4-Pro recipe YAML | https://github.com/vllm-project/recipes/blob/main/models/deepseek-ai/DeepSeek-V4-Pro.yaml |
| FlashInfer MoE env | https://docs.vllm.ai/en/v0.10.1/configuration/env_vars.html |
| `--moe-backend` deprecation | https://github.com/vllm-project/vllm/pull/43148 |
| FlashInfer MoE DP+EP | https://github.com/vllm-project/vllm/pull/36838 |
| H200 MoE backend sweet spots | https://github.com/vllm-project/vllm/issues/28882 |
| MoE kernel feature matrix | https://github.com/vllm-project/vllm/blob/main/docs/design/moe_kernel_features.md |
| Prior MoE serving audit | `research/tapetum-llm-speedup/98-vllm-moe-serving.md` |
| Prior MoE batching forage | `research/cold-run-10min/05c-web-moe-batching.md` |
