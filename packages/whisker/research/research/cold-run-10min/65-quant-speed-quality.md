# 65 — DeepSeek-V4-Pro quantization on H200 (FP8 / FP4 / NVFP4)

**Date:** 2026-07-24  
**Query:** Quantization options for V4-Pro on H200, decode speed vs quality for
structured judging, and whether a quant A/B is worth doing for the ≤10 min
cold-run goal.  
**Prior (do not rediscover):** `05a-web-deepseek-vllm.md`, `05d-web-mtp-specdecode.md`,
`22-path-a-b-10min.md`, `00-baseline.md`.  
**Scope:** Evidence cards from official recipes, NVIDIA/community checkpoints,
and InferenceX. No implementation changes.

---

## Answer (front)

| Question | Answer |
|----------|--------|
| Worth quant A/B on current H200 MoE pods for ≤10 min? | **No** |
| Why | NVFP4 speedups are **Blackwell-only**; H200 already serves the native **FP4+FP8 mixed** checkpoint. Switching toward pure FP8 is the wrong direction for decode bandwidth. |
| When worth revisiting | If MoE judge moves to **B200/B300**, A/B native MXFP4 vs `nvidia/DeepSeek-V4-Pro-NVFP4` (or canada-quant NVFP4+MTP) at c≈16. |

---

## Checkpoint map

| Artifact | Expert weights | Attention / shared / router | Documented target HW | Notes |
|----------|----------------|-----------------------------|----------------------|-------|
| `deepseek-ai/DeepSeek-V4-Pro` (native) | FP4 / MXFP4 | FP8 | H200 + Blackwell | Official Instruct; ~864–960 GiB class. vLLM H200 recipe uses this. |
| `deepseek-ai/DeepSeek-V4-Pro-Base` | FP8 mixed | FP8 mixed | Broader | Base, not the Instruct judge path. |
| `nvidia/DeepSeek-V4-Pro-NVFP4` | NVFP4 (ModelOpt) | FP8 (attn, shared, router, MTP) | **Blackwell only** (card: B200 / GB300) | MoE linears only; no `deep_gemm_mega_moe` (FP8-only kernel). |
| `canada-quant/DeepSeek-V4-Pro-NVFP4-FP8-MTP` | NVFP4 trunk experts | FP8 attn/shared; MTP byte-identical native | **8× B300** measured | +25–37% vs upstream MXFP4 at production conc; MTP acceptance ~91%. |
| `vultr/DeepSeek-V4-Pro-NVFP4` (+ custom kernel) | Aggressive uniform NVFP4 + selective upcast | Loader upcasts router / compressor / LM head | **Blackwell exclusive** | Not stock vLLM/SGLang. |

**Naming trap:** vLLM recipe labels the native variant `precision: fp8` in YAML while the prose says FP4+FP8 mixed. “FP8 checkpoint” in recipe docs often means “not the NVFP4 variant,” not “experts in FP8.”

---

## H200 reality (what alliance-pod can actually A/B)

### Supported on Hopper (H200)

1. **Native FP4+FP8 mixed** (`deepseek-ai/DeepSeek-V4-Pro`) — verified vLLM H200 recipe:
   `--kv-cache-dtype fp8`, `--max-num-seqs 16`, EP/DP, `cudagraph_mode: FULL_DECODE_ONLY`,
   context often capped (`--max-model-len 800000` in DP+EP notes).
2. **KV / indexer precision knobs** (not weight-checkpoint swaps): FP8 KV cache
   (recipe default); optional FP4 indexer cache (`use_fp4_indexer_cache`) from the
   V4 attention blog — covered in `05a`, not a ModelOpt re-quant.
3. **Historical / fallback full-FP8 expert paths** — InferenceX notes Day-0 H200/MI355X
   sometimes ran non-native FP8 when FP4 expert kernels were immature. On AMD, moving
   experts **FP8 → native FP4** was a major bandwidth win. Implication for H200 today:
   if the pod already runs native FP4 experts, an “upgrade” to FP8 experts is likely
   **slower**, not faster.

### Not an H200 option

- **`nvidia/DeepSeek-V4-Pro-NVFP4`**: model card lists **NVIDIA Blackwell** under
  supported microarchitecture; inference test HW is B200/GB300. NVFP4 tensor-core
  path is Blackwell-native (vultr kernel README: will not run on earlier arches).
- Community NVFP4+MTP and vultr aggressive NVFP4: same Blackwell constraint.

**Conclusion:** On `alliance-pod` / `h200x8-deepseek-v4-pro`, there is no credible
checkpoint A/B of “FP8 vs FP4 vs NVFP4” that matches the published speed literature.
The live stack is already the Hopper-supported mixed native path.

---

## Decode speed evidence

### Native MXFP4 vs NVFP4 (Blackwell only — do not apply to H200)

canada-quant, same vLLM build, same 8× B300, MTP n=1 + cuda graphs:

| Concurrency | Upstream MXFP4 | NVFP4 | Δ |
|------------:|---------------:|------:|--:|
| c=1 | 110.8 tok/s | 139.3 tok/s | **+25.7%** |
| c=16 | 491.4 tok/s | 672.6 tok/s | **+36.9%** |
| c=64 | 1699 tok/s | 1927 tok/s | +13.4% |
| c=128 | 2807 tok/s | 3005 tok/s | +7.1% |

Peak gain lands at **c≈16**, which is exactly their MoE `--max-num-seqs 16` recipe
pin — but only if the GPUs are Blackwell.

### Fleet arithmetic if NVFP4 were available (counterfactual)

Baseline Path B MODERATE (`22`): `L≈20 s`, `N_rem=1419`, `S=16` → ~1366 s.  
Optimistic −30% on MoE compute only: `1419 × 14 / 16 ≈ 1242 s` — still **≫600 s**.  
Path A MODERATE already ~596 s with dual-pod; a Blackwell NVFP4 swap would be
margin, not the unlock.

Quant is dominated by call cuts + dual-pod, not the other way around.

---

## Quality evidence (judging relevance)

### NVIDIA ModelOpt NVFP4 vs FP8 reference

| Precision | GPQA Diamond | AA-LCR | τ²-Bench Telecom | SciCode | IFBench |
|-----------|-------------:|-------:|-----------------:|--------:|--------:|
| FP8 (AA Ref) | 89.00 | 66.00 | 96.00 | 50.00 | 76.00 |
| FP8 (Ours) | 89.49 | 66.89 | 94.25 | 51.08 | 77.82 |
| NVFP4 | 89.33 | 66.33 | 94.83 | 53.45 | 77.21 |

Deltas are within ~1–2 pts; IFBench (instruction following) is the closest public
proxy to schema-shaped judging and stays at parity.

### canada-quant NVFP4 vs native MXFP4 (same harness)

- GSM8K matched-300: 296/300 vs 297/300 (Wilson CIs overlap).
- MTP acceptance: 91.21% vs 90.92%.
- EvalPlus HumanEval/MBPP deltas ≤ ~0.013.

**Gap:** No published tapetum / fused-verdict / `defect_groups` parity for any
quant swap. Public benches do **not** prove 381/381 judge stability. That is
irrelevant for H200 A/B deferral (no valid speed A/B), but would be mandatory
before any future Blackwell cutover.

### Aggressive uniform NVFP4 (vultr)

Flattening *everything* to NVFP4 caused generation collapse until router,
compressor helpers, and LM head were walked back to BF16/FP8. Treat “full 4-bit”
as unsafe for judging without that precision floor.

---

## Finding cards

### 1. Official native = FP4 experts + FP8 rest; H200 recipe exists

- **Title:** deepseek-ai/DeepSeek-V4-Pro | vLLM Recipes  
- **URL:** https://recipes.vllm.ai/deepseek-ai/DeepSeek-V4-Pro  
- **Summary:** Checkpoint is FP4+FP8 mixed. H200 recommended with DP+EP; NVFP4
  variant called out as Blackwell + FP4 indexer path; NVFP4 cannot use
  `deep_gemm_mega_moe`.  
- **Relevance:** HIGH

### 2. NVIDIA NVFP4 card: Blackwell + quality ≈ FP8

- **Title:** nvidia/DeepSeek-V4-Pro-NVFP4  
- **URL:** https://huggingface.co/nvidia/DeepSeek-V4-Pro-NVFP4  
- **Summary:** ModelOpt NVFP4 on MoE linears; supported HW Blackwell; GPQA/IFBench
  table shows near-FP8 accuracy; serve with `--kv-cache-dtype fp8`.  
- **Relevance:** HIGH (speed irrelevant on H200; quality ceiling useful later)

### 3. canada-quant: +25–37% decode at c=16 on B300, quality in noise

- **Title:** DeepSeek-V4-Pro NVFP4-FP8 MTP  
- **URL:** https://huggingface.co/canada-quant/DeepSeek-V4-Pro-NVFP4-FP8-MTP  
- **Summary:** Throughput win vs native MXFP4 on 8× B300; MTP parity; GSM8K within CI.  
- **Relevance:** HIGH for Blackwell migration; **NONE** for current H200 A/B

### 4. InferenceX: FP4 expert path is the bandwidth win; H200 ≠ NVFP4 story

- **Title:** DeepSeekV4 1.6T Day 0 to Day 43 Performance  
- **URL:** https://inferencex.semianalysis.com/blog/deepseekv4-16t-day-0-to-day-43-performance  
- **Summary:** Day-0 recipes mostly native mixed FP4 MoE + FP8 attn; some H200/MI355X
  runs used full FP8 when FP4 kernels missing; later FP4 MoE path recovered large
  throughput. NVFP4 called out as remaining vLLM work item, not Hopper default.  
- **Relevance:** HIGH

### 5. NIM / docs: Hopper listed for mixed FP4+FP8, not NVFP4

- **Title:** deepseek-ai / deepseek-v4-pro (NVIDIA NIM reference)  
- **URL:** https://docs.api.nvidia.com/nim/reference/deepseek-ai-deepseek-v4-pro  
- **Summary:** H100/H200 listed; precision “FP4 + FP8 Mixed (MoE experts in FP4,
  other parameters in FP8).”  
- **Relevance:** MED

---

## Cross-check vs 10 min path (`22`)

| Lever class | Moves ≤600 s? | Quant A/B role |
|-------------|:-------------:|----------------|
| Metadata Tier A+B + escalation dedupe | Yes (N cut) | None |
| Dual-pod S=32 | Yes (~887 s on MODERATE) | None |
| Dense-judge offload | AGGRESSIVE margin | Different model, not V4-Pro quant |
| NVFP4 on H200 | N/A (unsupported) | **Skip** |
| Hypothetical −30% L on one H200 pod | Still Path B ~1240 s | Insufficient alone |

---

## False-pass / false-fail

**False-pass:** Operator downloads `nvidia/DeepSeek-V4-Pro-NVFP4` onto H200,
sees load errors or silent dequant fallback, assumes “quant A/B done,” and
burns a weekend while twin-pod / metadata cuts stay unshipped.

**False-fail:** Operator hears “NVFP4 is +37% at c=16” and blocks MODERATE
shipping until a quant A/B completes — but that +37% is B300-only and would
not close Path B anyway.

---

## What would change my mind

1. **Documented H200 NVFP4 (or equivalent) serve recipe** with measured tok/s at
   `max-num-seqs=16` on their image → reopen speed A/B.  
2. **Measured Path A cold wall ≤600 s already**, and remaining risk is decode
   margin on Blackwell pods → then NVFP4 A/B for cost/margin, not for 10 min.  
3. **Evidence that alliance-pod is still on full-FP8 experts** (not native FP4) →
   then A/B toward native FP4+FP8 mixed is high value (opposite of NVFP4 story).

---

## Sources

1. https://recipes.vllm.ai/deepseek-ai/DeepSeek-V4-Pro  
2. https://github.com/vllm-project/recipes/blob/main/models/deepseek-ai/DeepSeek-V4-Pro.yaml  
3. https://huggingface.co/nvidia/DeepSeek-V4-Pro-NVFP4  
4. https://huggingface.co/canada-quant/DeepSeek-V4-Pro-NVFP4-FP8-MTP  
5. https://github.com/vultr/deepseek-v4-nvfp4-kernel  
6. https://docs.api.nvidia.com/nim/reference/deepseek-ai-deepseek-v4-pro  
7. https://vllm.ai/blog/2026-04-24-deepseek-v4  
8. https://inferencex.semianalysis.com/blog/deepseekv4-16t-day-0-to-day-43-performance  
9. https://huggingface.co/deepseek-ai/DeepSeek-V4-Pro  
