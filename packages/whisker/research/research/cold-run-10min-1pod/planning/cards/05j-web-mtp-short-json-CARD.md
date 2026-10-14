# Card 05j — MTP for short structured JSON @ c≈16

**Source report:** `05j-web-mtp-short-json.md`  
**Verdict in source:** usable-with-conditions · **Return: A-B**

## Bottom line

For short structured JSON at concurrency ~16, MTP is more likely **flat-to-hurt** than a bankable wall cut. Treat as A/B-gated ops, not a plan assumption. Do **not** put MTP wall cuts in the central ≤600 s stack. If forced binary before A/B: prefer **off** for short-JSON-dominant traffic; probe k=1 only.

## Numbers

- GB300 (R1, MTP k=1, ISL=2k, OSL=64): MTP overhead cannot amortize → throughput **lower with MTP on**.
- vLLM MTP PR #12755: k=1 TPOT speedup **1.63× @ QPS=1 → ~1.0× @ QPS=8**; production crossover often ~**4–8** concurrent.
- MagicDec: short sequence + large batch → speculative decode hurts.
- Healthy greedy k=1 acceptance ~**80–90%** when path works — necessary but not sufficient for short OSL.
- Recipe advertises `num_speculative_tokens: 2` for “low latency & small batch” — **not** our short-judge regime; use **k=1 only** if probing.
- Pass-path / verdict-first tails ~55–80 tok land on the wrong side of the OSL=64 cliff.
- Kill criteria: acceptance <60%, JSON regressions, or wall regress → leave off; flip yes only if acceptance ≥70%, JSON ≥ baseline, material wall win.

## Architecture implication

Alliance-pod S=16 / client c=32 is in the saturated-batch band. High structured acceptance does not cancel short-OSL draft/verify cost. Verify MTP head present in weights (`spec_decode_draft_acceptance_rate` under load); flag alone can be a silent no-op. Optional Tier-1 with kill-switch only.

## Reject-or-A-B

**A-B** (source return). **Reject as central plan bank.** **Reject:** recipe k=2 for short JSON; banking −100–200 s from long-output smokes. Smoke one traced paper for reasoning×MTP×JSON correctness before fleet.

## Links

- https://blog.vllm.ai/2026/02/13/gb300-deepseek.html
- https://github.com/vllm-project/vllm/pull/12755
- https://arxiv.org/html/2408.11049v3 (MagicDec)
- https://recipes.vllm.ai/deepseek-ai/DeepSeek-V4-Pro
- https://tianpan.co/blog/2026-04-17-speculative-decoding-production-hidden-traps
