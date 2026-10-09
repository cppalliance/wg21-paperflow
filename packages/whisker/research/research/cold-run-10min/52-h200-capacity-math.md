# 52 - H200 Capacity Math: DeepSeek-V4-Pro / V3 Decode vs ~70 tok/s

**Verdict:** measured ~**70 tok/s** solo decode on `alliance-pod` is **healthy for this model class**, not underperforming. It sits near the HBM bandwidth ceiling for ~49B activated MoE weights on Hopper, after realistic MoE / multi-GPU efficiency.

**Confidence:** high on param counts and bandwidth arithmetic; medium on exact FP4-byte mix of the 49B active path (official docs say experts FP4 / rest FP8, not the exact active-byte split).

**Date:** 2026-07-24.

---

## Model sizes (official)

| Model | Total params | Activated / token | Weight precision (release) | Source |
|-------|-------------:|------------------:|----------------------------|--------|
| DeepSeek-V3 / V3.2 | **671B** | **37B** | FP8 (main) | DeepSeek-V3 tech report; HF model card |
| DeepSeek-V4-Flash | **284B** | **13B** | FP4 experts + FP8 rest (instruct) | [HF DeepSeek-V4-Pro README](https://huggingface.co/deepseek-ai/DeepSeek-V4-Pro) |
| DeepSeek-V4-Pro | **1.6T** | **49B** | FP4 experts + FP8 rest (instruct) | same; arXiv 2606.19348 |

Notes:

- HF V3 download size is **685B** because it adds **14B MTP** module weights on top of 671B main.
- V4-Pro activates **~1.32×** more params per token than V3 (49B / 37B). Decode weight traffic scales with **activated**, not total.
- V4 paper: at 1M context, V4-Pro claims **~27%** of V3.2 single-token FLOPs and **~10%** KV size (hybrid CSA/HCA). That helps long-context; short-context solo decode is still dominated by **active weight reads**.

---

## Fit reality: not literally 1×H200

| Constraint | Number |
|------------|--------|
| H200 HBM | **141 GB** @ **4.8 TB/s** ([NVIDIA H200](https://www.nvidia.com/en-us/data-center/h200/)) |
| V3 FP8 weights (order) | ~671 GB → needs **multi-GPU** (typ. 8×H200) |
| V4-Pro mixed FP4/FP8 | experts ~0.5 B/param; HF/vLLM recipes target **8×H200** (or B200). Dense trunk often **replicated** across DP ranks; experts sharded |

So "1×H200 FP8/FP4" here means: **per-stream bandwidth ceiling from activated bytes**, and/or **per-GPU share of an 8×H200 V4-Pro node**. It does **not** mean the full 1.6T checkpoint resides on one card.

Our pod (`alliance-pod` / `h200x8-deepseek-v4-pro`) is this multi-GPU serving class. Measured ~70 tok/s is **per-request decode** (ITL), not aggregate tok/s/gpu under fat batching.

---

## Bandwidth ceiling (batch = 1, weights dominate)

Decode is memory-bound:

```
tok/s_ceiling ≈ HBM_BW / bytes_read_per_token
bytes_read_per_token ≈ activated_params × bytes_per_param   (+ small KV term at short ctx)
```

H200: `4.8 TB/s = 4800 GB/s`.

### Ideal ceilings (100% BW, ignore KV / comms / kernels)

| Scenario | Bytes / token | Ceiling tok/s |
|----------|--------------:|--------------:|
| V3, 37B @ FP8 (1 B/param) | 37 GB | **~130** |
| V4-Pro, 49B @ FP8 equivalent | 49 GB | **~98** |
| V4-Pro, 49B @ all-FP4 (0.5 B/param) | 24.5 GB | **~196** |
| V4-Pro, mixed ~0.6 B/param (≈80% FP4 expert bytes + 20% FP8) | ~29 GB | **~165** |
| Dense 70B @ FP8 on 1×H200 (sanity anchor) | 70 GB | **~69** ([ITK memory-wall note](https://itkservices3.com/background/token_memory)) |

Hopper has **no native FP4 tensor path**: FP4 expert weights still need **dequant → FP8 GEMM**. Storage bandwidth benefit of FP4 remains; compute/dequant tax pulls realized rate below the pure-FP4 ceiling. DeepSeek's own V4 writeup notes FP4×FP8 peak on current HW matches FP8×FP8 (future HW can do better).

### Realistic band after MoE + multi-GPU tax

Apply **~45–70%** of ideal (expert gather/scatter, TP/DP all-reduce, kernel inefficiency, short KV):

| Model / precision story | Ideal | Realized solo decode (expected) |
|-------------------------|------:|--------------------------------:|
| V3 37B FP8 | ~130 | **~60–90** tok/s |
| V4-Pro 49B FP8-eq | ~98 | **~45–70** tok/s |
| V4-Pro 49B mixed FP4/FP8 | ~165 | **~75–115** tok/s (Hopper dequant pulls toward low/mid) |
| Dense 70B FP8 (1×H200) | ~69 | **~50–70** tok/s |

**~70 tok/s** lands in the **middle of the V4-Pro expected band**, and matches the dense-70B-FP8 H200 ceiling coincidentally (49B MoE active ≈ 70B dense traffic after MoE/comms tax).

---

## External anchors (not our pod)

| Anchor | Number | How to read it |
|--------|--------|----------------|
| Our baseline solo decode | **~70 tok/s/request** | `pdf_judge.py:28`, `tapetum-llm-speedup/00-baseline.md` |
| Our loaded per-user @ c=16 | **~19 tok/s** (also ~36–40 tok/s TPOT in some scrapes) | MoE continuous-batch penalty; `16-dense-judge-candidates.md`, persona 146 |
| SemiAnalysis InferenceX H200 V4-Pro | aggregate **~70–222 tok/s/gpu** across interactivity points; high interactivity ≈ concurrency ~2 | throughput ≠ solo ITL; [InferenceX H200 vs MI355X](https://inferencex.semianalysis.com/compare/deepseek-v4-h200-vs-mi355x) |
| Commentary on same family | ~**150 tok/s/gpu @ ~20 tok/s/user** interactivity on H200; large regression vs V3 batched serving | FP4→FP8 dequant + 49B vs 37B + single-node EP; secondary source |
| vLLM Wide-EP DeepSeek (V3-class) | **~1.5k–2.2k tok/s/H200** | **batched / multi-node** aggregate, not solo ITL |

Do not compare our **70 tok/s solo ITL** to **2.2k tok/s/gpu Wide-EP** numbers. Different operating point (batch, EP width, interactivity).

---

## Comparison to measured ~70 tok/s

| Question | Answer |
|----------|--------|
| Is 70 tok/s below the physics floor? | **No.** Ideal V4-Pro FP8-eq ceiling is ~98; mixed-FP4 ideal ~165; realized 45–115. |
| Is 70 "slow for a 49B-active MoE"? | **No.** It is what H200 HBM predicts once MoE routing and Hopper FP4 dequant are priced in. |
| Would V3 solo be faster? | **Yes, modestly** (~15–30% higher ceiling from 37B vs 49B), all else equal. |
| Would 1×H200 dense 32B be faster? | **Yes** for solo ITL (32 GB FP8 → ideal ~150 tok/s). Different quality class. |
| Does 70 imply the pod is misconfigured? | **Not from decode rate alone.** Misconfig would look like **<<40 tok/s solo** or GPU idle with high ITL. |
| Does fleet ~20 s/call contradict 70 tok/s? | **No.** 150–300 out tokens ÷ 70 ≈ **2–4 s decode**; residual is **queue + prefill** (baseline ~20 s/call @ 16 slots). |

---

## Verdict for cold-run planning

**~70 tok/s solo decode on DeepSeek-V4-Pro / H200 is healthy.**

- Treat it as **in-band for this model class**, not a serving bug to chase.
- Latency levers that matter for the 48→10 min goal remain **call count, APC/prefill, concurrency topology, dual-pod**, not "fix the 70 tok/s decode."
- Loaded **~19 tok/s/user @ 16 seqs** is the MoE batching trade we already priced; raising `--max-num-seqs` to 32 was measured to **hurt** wall (+57%).

### What would change this verdict

1. Solo decode probe (concurrency 1, short prompt, long `max_tokens`) sustaining **<40 tok/s** with GPUs saturated → underperforming, investigate kernels / FP8 path / graph mode.
2. Same probe sustaining **>120 tok/s** sustained → we were leaving headroom (unlikely on Hopper V4-Pro without MTP).
3. Official active-byte breakdown showing active path is **>>49 GB FP8-equivalent** per token → revise ceiling down; 70 would then look stronger, not weaker.
