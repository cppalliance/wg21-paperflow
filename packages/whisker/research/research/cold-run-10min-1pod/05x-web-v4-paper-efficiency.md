# 05x — Web: DeepSeek-V4 paper claims on inference efficiency vs V3.2

**Query:** What does the V4 technical report claim about inference efficiency
vs V3 / V3.2, and are we leaving those architectural wins unused on
`alliance-pod`?

**Date:** 2026-07-24  
**Corpus constraint:** single pod (`alliance-pod` = DeepSeek-V4-Pro). No twin Pro.

**Primary source:** DeepSeek-AI, *DeepSeek-V4: Towards Highly Efficient
Million-Token Context Intelligence*, arXiv HTML
[2606.19348](https://arxiv.org/html/2606.19348) (fetched 2026-07-24).  
**Cross-check:** [HF DeepSeek-V4 blog](https://huggingface.co/blog/deepseekv4)
(figures from the same report).

**Related cards (do not rediscover):** `05-web-think-off-official.md`,
`05b-web-flash-vs-pro.md`, `16-server-ops-1pod.md`,
`research/cold-run-10min/59-deepseek-v4-release.md`.

---

## Verdict (operator ask)

| Question | Answer |
|----------|--------|
| **Headline paper claim @ 1M ctx** | V4-Pro ≈ **27% FLOPs / 10% KV** vs V3.2; Flash ≈ **10% / 7%** |
| **Mechanism** | Hybrid **CSA + HCA** (replaces MLA), FP8 KV (+ BF16 RoPE dims), FP4 lightning indexer, smaller top-k vs V3.2, FP4 MoE experts |
| **Are CSA/HCA "unused" on alliance-pod?** | **No** — baked into V4-Pro weights + vLLM V4 kernels when serving Pro |
| **Are we leaving V4 efficiency on the table?** | **Partially yes**, but the unused part is **product dials + serving recipe**, not a missing attention switch |

**One-liner:** The paper's 3.7× FLOPs / 9.5× KV win vs V3.2 is already paid by running V4-Pro; cold-run headroom is Non-think / Flash / MTP / APC / DeepEP, not "turn on CSA."

---

## Paper headline numbers (vs DeepSeek-V3.2)

Measured as **estimated single-token inference FLOPs** (equivalent FP8) and
**accumulated KV cache size** at **1M-token context** (paper intro + Fig. 1 right).

| Model | Activated | Single-token FLOPs vs V3.2 | KV cache vs V3.2 | Approx. factor |
|-------|----------:|---------------------------:|-----------------:|----------------|
| DeepSeek-V3.2 | 37B | 1.00× | 1.00× | baseline |
| DeepSeek-V4-Pro | **49B** | **0.27×** | **0.10×** | ~3.7× less compute, ~10× less KV |
| DeepSeek-V4-Flash | **13B** | **0.10×** | **0.07×** | ~10× / ~14× |

Caveats from the paper text (not third-party blogs):

1. Gains are **"especially in long-context settings"** (intro + §2.3.4). The
   27% / 10% pair is the **1M** point on Fig. 1, not a constant for every
   sequence length.
2. Pro has **more** activated params than V3.2 (49B vs 37B) and still wins on
   long-context FLOPs/KV — the win is architectural compression, not a smaller
   MoE activate count.
3. Flash's further cut is mostly **smaller activate + same hybrid attention**.
4. Vs **BF16 GQA-8** (common dense baseline), V4 KV at 1M is ~**2%** (§2.3.4 /
   HF blog). That is not a V3.2 comparison; do not mix the two baselines.

---

## What the architecture changes (vs V3 / V3.2)

Paper §2 upgrades over DeepSeek-V3 family:

| Change | Efficiency role | Training-only? |
|--------|-----------------|----------------|
| **CSA** (Compressed Sparse Attention) | Compress KV ~**4×** (overlapped pooling), then DSA top-k over compressed blocks + sliding-window branch | No — inference path |
| **HCA** (Heavily Compressed Attention) | Compress KV ~**128×**, dense attend over short compressed stream + SWA | No — inference path |
| **Hybrid interleave** | Layers alternate CSA/HCA (Pro: layers 0–1 HCA, then alternate; MTP block SWA-only) | No |
| **FP8 KV + BF16 RoPE dims** | ~½ KV vs pure BF16 before compression | Serving must store FP8 |
| **FP4 lightning indexer (CSA QK)** | Faster long-context index scores; QAT keeps top-k recall ~99.7% (§5.2.1) | Needs FP4 kernels |
| **Smaller attention top-k vs V3.2** | Helps **short- and medium-length** texts (§2.3.4) | Weight hyperparam |
| **Grouped low-rank output projection** | Cuts wide attention output cost | No |
| **FP4 MoE routed experts** (instruct) | Memory / bandwidth for experts | Weight format |
| **mHC** | Residual capacity / depth, not the FLOPs headline | Mostly quality |
| **Muon optimizer** | Training convergence | Training-only |
| **MTP modules** | Same config as V3; speculative decode enabler | Needs server MTP |
| **MegaMoE fine-grained EP** (§3.1) | Claims **1.50–1.73×** vs non-fused EP baselines (up to ~1.96× latency-sensitive) | Serving kernel / backend |

CSA Pro knobs (paper §4.2.1): compression rate 4, top-k **1024**, SWA `win=128`.  
HCA: compression rate **128**. Flash CSA top-k is **512** (smaller model).

Replaces V3's **MLA** with this hybrid local + long-range design (HF transformers
doc / paper §2.3).

---

## Mapping to our single-pod stack

| Paper win | On `alliance-pod` today? | Evidence / note |
|-----------|--------------------------|-----------------|
| Serving **V4-Pro** (CSA/HCA/mHC weights) | **Yes** | `SERVICES.toml` `model = "deepseek-v4-pro"` |
| **FP8 KV** storage | **Yes** (ops card: keep) | `16-server-ops-1pod.md` — `--kv-cache-dtype fp8` already live; **0 s incremental** |
| **FP4 experts / indexer kernels** | Assumed via V4 vLLM image | Confirm image; not a client flag |
| **Smaller top-k / hybrid attention** | **Yes** (weight graph) | No client toggle; wrong tokenizer/parser can break it |
| **Flash (13B activate)** | **No** | Only Pro on Alliance; see `05b-web-flash-vs-pro.md` |
| **Non-think mode** | **No** | Fleet stays thinking-on; see `05-web-think-off-official.md`, persona 59 |
| **MTP speculative decode** | **Not confirmed live** | Target recipe: MTP k=1; gate acceptance ≥70% (`16-server-ops-1pod.md`) |
| **APC + retention (#43447)** | **Partial / unverified** | Pre-#43447 → 0% hits; Tier-1 recipe |
| **DeepEP low-latency + DBO** | **Optional A/B** | Paper MegaMoE story; Tier-2 after smoke |
| **Raise max-num-seqs** | Forbidden | Measured +57% wall; orthogonal to paper |

---

## Are we leaving V4 architectural wins unused?

### Short answer

**Core paper architecture: no. Serving + product efficiency dials: yes.**

### Detail

1. **Do not treat Fig. 1 as an untapped switch.**  
   Running DeepSeek-V4-Pro already instantiates CSA/HCA, grouped projections,
   and (with correct vLLM V4 path) FP8 KV / FP4 indexer. There is no client
   flag that "enables hybrid attention" for another 3.7×. Claiming the cold
   fleet "isn't using V4 architecture" is false.

2. **The 1M FLOPs/KV headline is the wrong denominator for our wall.**  
   Tapetum calls are mid-context (tens of k, monolith up to ~393k), decode-bound
   under thinking. Paper gains grow with sequence length; at short/medium lengths
   the paper itself credits the **smaller top-k** more than the 1M compression
   curve. Prefill/KV headroom from CSA/HCA is already why Pro fits 393k at S=16;
   it does not by itself cut **~20 s decode** thinking tails.

3. **What we actually leave unused (paper-adjacent, wall-relevant):**
   - **Non-think** — official fast path; paper/product modes, not a missing kernel
     (`59-deepseek-v4-release.md`).
   - **Flash** — paper's second efficiency pillar (0.10× FLOPs / 0.07× KV @ 1M;
     13B activate). Unused unless we swap the one pod or add a non-Pro endpoint
     (`05b`).
   - **MTP** — inherited from V3, kept in V4; speculative decode needs server
     `speculative-config` + acceptance gate (`16`).
   - **MegaMoE / DeepEP+DBO class overlap** — paper §3.1 infra win; ops Tier-2.
   - **APC retention** — not in the paper FLOPs table, but required to harvest
     prefix reuse the architecture makes cheap to store.

4. **Implication for ≤600 s on one pod.**  
   Paper architecture already bought the long-context economics that let Pro
   serve our context window. Closing the remaining ~660–900 s gap is still
   **N cuts + decode shrink + dense offload + ops recipe**, not rediscovering
   CSA. Using Flash/Non-think is a **quality-gated model/mode change**, not
   "finally enabling V4."

---

## False-pass hypothesis

Ops claims "we enabled V4 efficiency" after flipping APC/MTP, then attributes
wall wins to CSA/HCA as if those were newly activated — masking a Non-think or
Flash quality cliff as an architectural free lunch.

## False-fail hypothesis

Rejecting all V4 efficiency work because "we're already on Pro so the paper is
irrelevant" — MTP, DeepEP/DBO, APC retention, Non-think, and Flash are still
real unused dials with measured or official latency stories.

## What would change my mind

1. Startup log shows `alliance-pod` is **not** loading V4 attention kernels /
   FP8 KV → then weight-level wins really are unused (fix image/flags first).
2. Cold-run A/B where **Pro Non-think** or **Flash** on unit/metadata matches
   Pro-High defect-group recall within flip budget **and** drops L enough to
   close the post-v11 gap → upgrade "product dials" from optional to required
   path for 10 min.
3. Paper figure or internal profiling showing mid-context (~32k–128k) Pro FLOPs
   still ≫ V3.2 by a large factor under our prompt shapes → revisit how much
   "already paid" vs remaining attention headroom.

---

## Arithmetic note (single-pod, S=16)

Paper FLOPs ratios do **not** plug into
`wall = (N_rem × L_eff) / 16 + T + C − L_abs` as a multiplier on current L.
L today is dominated by **thinking decode**, not V3.2-vs-V4 attention FLOPs.
Treat paper numbers as **capacity / prefill / KV justification** for staying on
V4-Pro at 393k, and treat **Non-think / Flash / MTP / dense offload** as the L
and N levers.
