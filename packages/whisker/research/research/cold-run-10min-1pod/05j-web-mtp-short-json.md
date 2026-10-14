# 05j - Web: MTP speculative decoding for short structured JSON (DeepSeek V4, c≈16)

**Date:** 2026-07-24  
**Query:** Does MTP speculative decoding help or hurt short structured JSON on DeepSeek V4 at concurrency ~16 on the single-pod plan?  
**Prior (do not rediscover wholesale):** `research/cold-run-10min/05d-web-mtp-specdecode.md`, `research/cold-run-10min/05a-web-deepseek-vllm.md`, `00-baseline.md` (S_eff=16 fixed).  
**This card:** short-OSL + structured-JSON + concurrency≈16 only. Not a general MTP primer.

---

# 05j - Web-MTP-Short-JSON

**Verdict:** usable-with-conditions — for short structured JSON at concurrency ~16, MTP is more likely to be flat-to-hurt than a bankable wall cut; treat as A/B-gated ops, not a plan assumption.  
**Confidence:** high on the short-OSL amortization cliff and concurrency sensitivity; medium on exact alliance-pod seconds until measured.

## Findings

- [CRITICAL] **Short-output mixed loads are the documented MTP lose case.** vLLM GB300 blog (DeepSeek R1-0528, MTP k=1): at ISL=2k, OSL=64, “decode proportion is extremely low … MTP overhead cannot be amortized” → throughput **lower with MTP on** at both low and high concurrency ([blog.vllm.ai/2026/02/13/gb300-deepseek.html](https://blog.vllm.ai/2026/02/13/gb300-deepseek.html)). Impact: pass-path / verdict-first JSON tails that sit near ~55–80 tokens (after Non-think shrink) land on the wrong side of that cliff; do not bank MTP seconds for short JSON in 1-pod arithmetic.

- [CRITICAL] **Concurrency ~16 is not the batch=1 win regime.** Spec decode wins when decode is memory-bound and surplus compute exists for draft+verify. At higher QPS/concurrency, speedup collapses: vLLM DeepSeek MTP PR [#12755](https://github.com/vllm-project/vllm/pull/12755) shows k=1 TPOT speedup **1.63× @ QPS=1 → ~1.0× @ QPS=8** (and worse in some TP=8 rows). Production writeups put the wall-clock crossover often around concurrent request counts of **~4–8**, with regressions common when labs bench bs=1 then ship at p50 concurrency 16 ([tianpan.co speculative-decoding production traps](https://tianpan.co/blog/2026-04-17-speculative-decoding-production-hidden-traps)). Impact: alliance-pod S=16 / client c=32 is already in the saturated-batch band where MTP’s expected fleet gain is modest at best and negative if OSL is short.

- [CRITICAL] **MagicDec: short sequence + large batch → SD hurts.** For S below a hardware/model inflection length, speculative verification becomes compute-bound as batch grows; SD “negatively impacts batch inference efficiency” on short sequences ([MagicDec, arXiv:2408.11049](https://arxiv.org/html/2408.11049v3); ICLR 2025). Impact: short JSON + 16 in-flight seqs is exactly that quadrant; long CoT would be a different card.

- [HIGH] **Structured JSON raises acceptance; it does not cancel short-OSL overhead.** MindStudio / speculative-decoding primers: code and structured/templated outputs often see the highest draft acceptance (token space constrained). DeepSeek V4 MTP is native (`method=mtp`, typically `num_speculative_tokens=1`) via vLLM ([docs](https://docs.vllm.ai/en/latest/features/speculative_decoding/mtp/)). Healthy greedy k=1 acceptance still clusters ~80–90% when the path works (PR #12755; GB300 >80%). Impact: high acceptance is necessary but not sufficient; if there are few decode steps, draft+verify cost still fails to amortize (GB300 OSL=64 result).

- [HIGH] **k≥2 on short JSON is an anti-pattern; V4 recipe k=2 is not our regime.** Official DeepSeek-V4-Pro vLLM recipe exposes MTP with `num_speculative_tokens: 2` and labels Spec Decoding for “low latency & small batch” ([recipes.vllm.ai](https://recipes.vllm.ai/deepseek-ai/DeepSeek-V4-Pro)). Single-layer DeepSeek MTP weights degrade for larger k (Ascend MTP guide; prior `05d`). Impact: if anything is A/B’d on alliance-pod, use **k=1 only**; never plan on recipe k=2 for short judge JSON.

- [HIGH] **V4 MTP head can be silently missing on some quants → config looks on, speedup is zero.** Pasta-paul / HF Transformers `_keys_to_ignore_on_load_unexpected` can drop MTP weights; `--speculative-config method=mtp` becomes a no-op until the head is restored (e.g. community retrofit reporting +62% decode only after fix: [agentry.press](https://agentry.press/news/deepseek-v4-flash-quant-restores-mtp-head-for-62-throughput-gain/)). Impact: 1-pod plan must verify `SpeculativeConfig(method='mtp'...)` **and** `spec_decode_draft_acceptance_rate` under load; flag presence alone is insufficient.

- [MED] **Structured JSON × reasoning × MTP is version-sensitive (correctness risk, not just speed).** Prior `05d` citations: reasoning-boundary / grammar advance bugs (#34650, #44927, #43424, #44993, #44006). Impact: even a throughput win is worthless if JSON schema / `</think>` boundary breaks fail-closed judges; smoke one traced paper before fleet.

- [MED] **When MTP still helps: decode-heavy, longer generations, surplus compute.** GB300: MTP helps decode when context is not long and concurrency stays in a moderate band (acceptance >80%, concurrency ≤256 before cliff). HF V4-Flash MTP cards report ~1.5× decode at **bs=1**. Impact: long thinking / long structured dumps ≠ this card’s short-JSON question; do not mix those speedups into short-JSON wall math.

## Regime map (this pod)

| Axis | Our 1-pod regime | MTP implication |
|------|------------------|-----------------|
| Model | DeepSeek-V4-Pro on `alliance-pod` | Native MTP supported in vLLM when weights present |
| Concurrency | Server slots **16** (client c=32) | Near/past QPS collapse zone from #12755 |
| Output shape | Short structured JSON (verdict-first / pass-path ~tens–low hundreds tok) | On/near GB300 OSL=64 “cannot amortize” cliff |
| Prefill | Long paper markdown in prompts | Raises ISL; worsens short-OSL amortization |
| Goal metric | Fleet wall with S_eff=16 fixed | Need aggregate goodput, not bs=1 TPOT |

## False-pass hypothesis

Operators enable MTP k=1 from the V4 recipe, see healthy acceptance on a long-output smoke test, bank −100–200 s in the 1-pod plan, then ship verdict-first short JSON where MTP is flat/negative — plan arithmetic still “assumes” the savings.

## False-fail hypothesis

Operators disable MTP forever after one short-JSON microbench (OSL≪64, prefill-heavy) and leave decode-heavy monolith/thinking calls slower than necessary; or they run MTP without CUDA-graph decode and blame “MTP quality” for eager batch-size argmax drift.

## What would change my mind

Cold A/B on alliance-pod only, real whisker short-JSON mix at c≈16:

1. `method=mtp`, `num_speculative_tokens=1`, CUDA-graph decode on vs MTP off.  
2. Log `spec_decode_draft_acceptance_rate`, mean OSL, JSON validity, pass/review/fail flip rates, fleet wall.  
3. Flip this card toward **yes** only if acceptance ≥70%, JSON validity ≥ baseline, and wall improves by a material margin (not noise).  
4. Flip to hard **no** if acceptance <60%, JSON regressions, or wall regresses.

---

## Recommendation

| | |
|--|--|
| **Help or hurt (short structured JSON @ c≈16)?** | **Hurt or flat** as the prior; help only if measured OSL stays decode-amortizable and acceptance stays high. |
| **Enable MTP for 1-pod plan?** | **A-B** |
| **Plan accounting** | Do **not** put MTP wall cuts in the central ≤600 s stack. Optional Tier-1 flag with kill-switch: acceptance ≥70% + no JSON regression, else leave off. |
| **If forced binary before A/B** | Prefer **off** for short-JSON-dominant traffic; k=1 only if probing. |

**Return: A-B**
