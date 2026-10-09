# 53 - Multi-GPU EP vs 1×H200 (decode @ 16 seqs, 10 min goal)

**Verdict:** garbage-as-premised / not-worth-for-10min — `alliance-pod` is already multi-GPU TP8+EP on 8×H200; DeepSeek-V4-Pro cannot load on 1×H200 at all. Further widening EP (2–8→16–128 GPUs) can cut loaded decode TPOT in principle, but for the ≤600 s cold target the infra dollar is better spent on a second identical 8×H200 twin (dual-pod S:16→32) plus client levers, not a wider single-replica EP fabric.
**Confidence:** high (template + recipe + weight footprint are hard facts; decode-latency upside of wider EP at fixed c=16 is medium, borrowed from V3/R1 EP literature)

**Worth for 10 min target?** **no**

---

## Premise check (blocks the counterfactual)

| Claim | Evidence | Status |
|-------|----------|--------|
| "alliance-pod is 1×H200" | RunPod template `H200-x8-deepseek`: `--tensor-parallel-size 8 --enable-expert-parallel` ([H200SXM.txt](https://raw.githubusercontent.com/cppalliance/runpod/master/templates/deepseek/H200SXM.txt)); ops checklist keeps **TP8+EP** (`26-server-ops-checklist.md:82`) | **False today** |
| V4-Pro fits 1×H200 (141 GB) | HF: 1.6T total / 49B active, FP4 experts + FP8 dense (~860–960 GB mixed checkpoint); vLLM recipe recommends **H200 (8× GPU)** DP/TEP ([recipes](https://recipes.vllm.ai/deepseek-ai/DeepSeek-V4-Pro)) | **Impossible** |
| Serving already uses EP | Template + `26`: `--enable-expert-parallel --enable-ep-weight-filter` | **Already on** |

`SERVICES.toml` does not declare GPU count for `alliance-pod`; the name is ambiguous. GPU topology is defined by the cppalliance/runpod H200SXM template and by the twin service name `h200x8-deepseek-v4-pro`. Dense-candidate notes that inferred "1×H200" for **Qwen** pods (`16-dense-judge-candidates.md:89`) must not be copied onto the MoE judge.

**Counterfactual still answered below:** if Pro somehow started on 1 GPU, "move to 2–8× EP" is first a **capacity** move (load weights + KV for 393k), only second a decode-latency move.

---

## Findings

- [CRITICAL] **1×H200 → multi-GPU is not optional latency tuning; it is the load path.** Evidence: ~860–960 GB mixed weights vs 141 GB HBM; recipe floor is 8×H200 for production context. Impact: "2×H200 EP" (282 GB) is still under weight floor for Pro; realistic first jump is **8×**, which is what the pod already runs. No 10 min delta from "adding EP" that is not already deployed.

- [CRITICAL] **Decode at concurrent 16 is already MoE-expert-union limited on EP8; wider EP helps the Pareto curve, not our gate.** Evidence: Perplexity multi-node DeepSeek note — at EP8, batch growth activates more local experts (up to 32/GPU), HBM-bound decode slows; higher EP (16→128) puts fewer experts per GPU and **raises output speed at the same throughput** ([article](https://research.perplexity.ai/articles/lower-latency-and-higher-throughput-with-multi-node-deepseek-deployment)); our slots-32 regression +57% wall when `--max-num-seqs` 16→32 (`slots-32-regression/11-moe-batch-scaling.md`). Impact: at **fixed c=16**, EP8 is already the ops sweet spot; wide-EP would mainly buy headroom to raise concurrency without TPOT collapse — we are forbidden from raising slots to 32 without new evidence (`00-baseline.md:28`).

- [HIGH] **For ≤600 s, dual identical replicas beat one wider EP replica.** Evidence: wall arithmetic — MODERATE single-pod ~1493 s, dual-pod S:16→32 → ~596 s central (`11-wall-arithmetic.md:76-77`, −887 s compute term). Wide-EP on one logical engine does **not** double `S_eff` the way two pods with separate `--max-num-seqs 16` do; it may shave per-token decode (L) while keeping one scheduler. Impact: even a generous **1.2–1.5×** loaded decode speedup on one pod (hypothesis from EP8→EP32-class literature) leaves MODERATE remainder ~1000–1250 s — **still misses 10 min**. Dual-pod is the infra multiplier that closes the gate.

- [HIGH] **Cost side: 2–8× incremental GPUs on one node are either impossible (2–4× under weight) or already paid (8×).** Evidence: template already bills 8×H200 24/7 (`SERVICES.toml` comment: uptime not tokens). Next spend is either (a) second 8× twin for sharding, or (b) multi-node wide-EP (16–128 GPUs) with InfiniBand AllToAll, DeepEP low-latency backend, EPLB — ops surface far above APC/MBT/MTP flags (`26-server-ops-checklist.md`). Impact: $/wall-second for wide-EP is worse than dual-pod + metadata short-circuit for this fleet shape (381 papers, ~2284 calls, decode-mean 5.91 s).

- [MED] **TEP vs DP+EP at our concurrency favors keeping TP8+EP, not reinventing topology.** Evidence: AMD/vLLM MoE playbook — TP+EP better latency at low–moderate concurrency; DP+EP wins at very high concurrency ([ROCm MoE playbook](https://rocm.blogs.amd.com/software-tools-optimization/vllm-moe-guide/README.html)); vLLM recipe lists single-node TEP with `max-num-seqs 16` for DeepSeek-V4-Pro. Impact: topology churn for "more EP" without a second pod does not align with c=16 interactive-batch judge traffic.

- [MED] **vLLM wide-EP literature targets tok/s/GPU at large scale, not our 10 min package.** Evidence: vLLM blog ~2.2k tok/s/H200 with wide-EP ([blog](https://vllm.ai/blog/2025-12-17-large-scale-serving)); Anyscale notes EP width should be the **smallest** that saturates throughput (blast radius). Impact: chasing wide-EP for a 16-slot advisory fleet is the wrong scale class.

- [LOW] **Partial benefit that is real but already stacked elsewhere:** MTP, CUDA-graph decode, MBT 16384, APC retention cut L without buying GPUs (`26` top-5 ~300–550 s envelope). Prefer those before any EP-width experiment.

---

## Cost / benefit for the 10 min goal

| Move | Capex / opex | Expected effect on cold wall @ c=16 | Hits ≤600 s? |
|------|--------------|--------------------------------------|--------------|
| Hypothetical 1× → 8× TP+EP | **Required to serve Pro** | Enables serving; not a delta from today's pod | N/A (already done) |
| 8× → 16–32× wide-EP (multi-node) | +1–3× node cost, IB + DeepEP ops | Cut L somewhat (expert HBM relief); S unchanged | **No** alone; maybe −10–30% L → still ~1000 s+ after MODERATE single-pod |
| Second 8× twin (`h200x8-deepseek-v4-pro`) | +1× identical pod | S:16→32, −887 s on MODERATE remainder | **Yes** with MODERATE client stack (~596 s) |
| Client MODERATE (metadata Tier A+B, prefix, verdict-first) | Eng time, no GPUs | −1082 s calls + −~436 s L_abs (overlap-correct) | Needed with dual-pod |

**Break-even intuition:** to replace dual-pod's −887 s with L-only EP widening, need roughly **L: 20 s → ~10 s** at S=16 on N_rem=1419 (`1419×10/16 ≈ 887`). That is a **~2×** loaded decode cut. Published EP8→EP128 wins are large on the **throughput-at-fixed-speed** Pareto curve, not a guaranteed 2× TPOT cut at batch 16 on an already-TEP8 node. Do not bet the 10 min gate on that without a measured A/B.

---

## False-pass hypothesis

Treat "enable more EP" as the 10 min plan while the twin pod is 404 and metadata short-circuit is unshipped: operators burn a multi-node EP rollout, see modest TPOT improvement, still land ~20–25 min, and conclude "MoE cannot hit 10 min."

## False-fail hypothesis

Reject all multi-GPU work because "EP doesn't help decode": false — EP is why Pro serves at all, and wider EP can help under larger batches. The rejection that is correct is narrower: **further EP width is not the cost-effective lever for this fleet's ≤600 s arithmetic.**

## What would change my mind

A controlled `vllm bench serve` (or 381-paper cold) on **EP8 TP8** vs **EP16/32 multi-node** at identical `--max-num-seqs 16`, same prompts, showing **≥2×** drop in mean decode time (or wall ≤700 s single-pod MODERATE). Absent that, keep EP8 and buy/heal the twin pod.

---

## Bottom line

| Question | Answer |
|----------|--------|
| Would 1×→ multi-GPU EP cut decode latency @ 16 seqs? | Counterfactual only: yes in mechanism (HBM/expert shard), but **1× cannot run Pro**; live pod is already 8× TP+EP. |
| Worth for 10 min target? | **no** — spend on dual-pod + client MODERATE; do not expand EP width as the primary lever. |
