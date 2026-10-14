# Card 05e — LLM-as-judge fleets on ONE MoE endpoint

**Source report:** `05e-web-single-endpoint-judge.md`

## Bottom line

On a single MoE endpoint, latency SLAs are hit by **not calling** the MoE, **shortening** each call, or saturating continuous batching as an offline job — not by stacking MoE→MoE stages. Same-pod cheap→expensive MoE cascade pays the serial sum; blended p50 looks fine while p95 / fleet wall sit in the slow mode.

## Numbers

- FrugalGPT: up to ~98% cost cut vs always-GPT-4 (cheap scorer ≪ next stage, rule of thumb 10–20% of next-stage cost+latency).
- LLMTrace: DeBERTa fast-judge ~50 ms; ambiguous band default 0.3–0.7; escalate only in band; ~60-token JSON.
- Cascade trap example: kept @ 400 ms + escalated @ 2800 ms → median falls, **p95 in slow mode**.
- SLMJury: Phi-4 14B ≈ **89.55%** oracle at **10** output tokens; open axes can lose up to ~23%.
- RuVerBench: packing 4–5 rubrics → double-digit quality drop.
- SAJA: 5–10× fewer LLM calls; ~44% judgments automated at ~99.6% accuracy (their setting).
- Offline vs chatty HTTP: ~2× / util ~90% vs ~35% (prior corpus / DigitalOcean notes).
- Wall: `(N_rem × L_eff) / 16 + T + C − L_abs`.

## Architecture implication

Five portable patterns: (1) deterministic/SLM pre-gate, (2) ambiguous-band short-circuit, (3) upfront route > same-endpoint cascade (dense units default; Pro on flags), (4) tiny verdict-first schemas, (5) offline batch saturation at S=16. Dense offload to a live smaller endpoint is allowed; second identical MoE replica is not. Track escalation rate as SLO.

## Reject-or-A-B

**Reject:** MoE→MoE judge-the-judge; hedging dual-fire on one 16-slot server; multi-rubric packing without holdout; celebrating blended median while escalate rate drifts; raising c or seqs past measured cliffs. **A/B:** dense unit lane ≥99% agreement with DeepSeek fused verdicts before Pattern 3 becomes primary ≤600 s path.

## Links

- https://arxiv.org/abs/2305.05176 (FrugalGPT)
- https://github.com/epappas/llmtrace/issues/88
- https://tianpan.co/blog/2026-04-23-cascade-router-reliability-trap-bimodal-latency
- https://arize.com/llm-as-a-judge/
- Prior: `research/tapetum-llm-speedup/05-web.md` Q3/Q5
