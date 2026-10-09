# 05e - Web: LLM-as-judge fleets on ONE MoE endpoint

**Corpus:** `cold-run-10min-1pod` (operator forbid: twin DeepSeek pod).
**Question:** How production systems run large LLM-as-judge / eval fleets against a
**single MoE (or single shared) endpoint**, not a multi-replica pool, and still
hit latency / wall-clock SLAs.
**Scope keywords:** cascades, short-circuit, small schemas, offline batch.
**Date:** 2026-07-24. Evidence only; no adopt/replace verdict.

---

## Bright-line (read first)

Cascades that run **cheap MoE call → score → expensive MoE call on the same
pod** do **not** improve wall clock. Escalated traffic pays the **serial sum**
of both generations; blended p50 looks fine while p95 / fleet wall land in the
slow mode (General Compute cascade notes; Tian Pan cascade-router trap).

On a single MoE endpoint, latency SLAs are hit by **not calling** the MoE, by
**shortening** each call, or by **saturating** continuous batching as an
offline throughput job — not by stacking MoE→MoE stages.

Dense-model offload to an already-live smaller endpoint is a different machine
(allowed in this corpus). A second identical MoE replica is not.

---

## Finding cards

### Cascades & short-circuit (production + research)

- **[HIGH] FrugalGPT (Chen/Zaharia/Zou, Stanford)**
  https://arxiv.org/abs/2305.05176 · https://github.com/stanford-futuredata/frugalgpt
  LLM cascade: cheapest API first, DistilBERT-class **post-query quality
  scorer**, escalate only below threshold. Up to ~98% cost cut vs always-GPT-4
  on their benches. Scoring function must be **≪ next stage** (rule of thumb
  10–20% of next-stage cost+latency) or the cascade is pure overhead.
  Impact for us: the portable piece is the **cheap scorer / pre-gate**, not a
  second DeepSeek stage on alliance-pod.

- **[HIGH] LLMTrace Judge Cascade ADR (epappas/llmtrace)**
  https://github.com/epappas/llmtrace/issues/88 · docs mirrors
  Production pattern: Tier0 heuristics → Tier2 DeBERTa fast-judge (~50 ms GPU)
  → escalate to Tier3 vLLM/Qwen **only if confidence ∈ [ambiguous_low,
  ambiguous_high]** (default 0.3–0.7). Confident high **or** low short-circuits
  (no slow call). `slow_backend: null` ships as fast-only. Shadow mode before
  enforcement. Hard `total_deadline_ms` on the judge path.
  Impact: ambiguous-band short-circuit is the template for tapetum unit→MoE
  escalation; keep/escalate as **two populations**.

- **[HIGH] Cascade latency trap (Tian Pan, 2026-04)**
  https://tianpan.co/blog/2026-04-23-cascade-router-reliability-trap-bimodal-latency
  Kept @ 400 ms + escalated @ 2800 ms → blended median falls, **p95 sits in
  slow mode**. Treat kept-p95, escalated-p95, and **escalation rate** as
  first-class SLOs. Shadow slice required so the cheap tier does not go stale.
  Impact: for ≤600 s fleet wall, report escalation rate; a 5 pt rise is a wall
  regression even if per-call L is flat.

- **[HIGH] General Compute cascade writeup**
  https://www.generalcompute.com/blog/cascade-inference-using-small-models-to-route-to-big-ones
  Interactive strict-tail SLOs favor **upfront routers** (RouteLLM-class) over
  post-generation cascades. Cascades fit **batch / document** workloads with
  loose per-item latency. Combine: coarse router for “obviously hard,” cascade
  only on the remainder.
  Impact: tapetum cold-run is a batch job → cascade/router OK; do not put
  MoE→MoE cascade on the critical path of every paper.

- **[MED] glide TTFT cascade (phanisaimunipalli/glide)**
  https://github.com/phanisaimunipalli/glide
  Proxy: per-model TTFT budget, abort-and-failover, hedge when p95 approaches
  budget. Latency-aware routing, not quality scoring.
  Impact: portable as **deadline abort** on a dense fast tier; hedging two
  MoE calls on one pod **wastes** slots (anti-pattern under S_eff=16).

- **[MED] Sub-second triage case study (Bessa)**
  https://bessavagner.com/blog/sub-second-llm-triage/
  Measured: nano/mini latency curves overlapped; cascade was **slowest** in the
  middle of the distribution because escalations serialize. Cost win, latency
  loss — same math as our single-pod constraint.

### Small schemas / short decode

- **[HIGH] SLMJury (arXiv 2606.07810)** *(also carded in tapetum 05-web Q5)*
  Phi-4 14B judge ≈ 89.55% oracle agreement at **10 output tokens**; tiny
  Qwen3-4B only ~1.74 pt behind. Quick verdicts beat 8k-token reasoning on
  some domains, lose up to ~23% on others — domain-calibrate.
  Impact: verdict-first + tiny `max_tokens` is the highest-leverage **L** cut
  on a capacity-bound MoE.

- **[HIGH] LLMTrace judge setup**
  ~60-token structured JSON, hardened system prompt + prompt caching, deadline
  ceiling. Pair with cascade so most traffic never reaches the LLM.
  Impact: schema floor already in our D6/output_type direction; pin decode
  budget to enum+brief reason, not essay CoT.

- **[HIGH] Industry eval practice (Arize / Cizmar / evaluate.live)**
  https://arize.com/llm-as-a-judge/
  Deterministic code checks (schema, enums, required fields) for everything
  that is not semantic; LLM judge only for the residual. Structured
  pass/fail or small numeric scale, not free text.
  Impact: every deterministic metadata / schema gate is a free short-circuit
  before alliance-pod.

- **[HIGH] RuVerBench (arXiv 2606.29920)** *(tapetum 05-web)*
  Packing 4–5 rubrics per call → double-digit quality drop on long-context
  agentic tasks. Multi-criterion packing is a **false** latency win.
  Impact: do not “save N” by stuffing many unit checks into one MoE prompt
  without holdout; prefer skip/short-circuit over pack.

- **[MED] SAJA (ACL industry 2026)** *(tapetum 05-web)*
  One structured extraction + cheap calibration head → 5–10× fewer LLM calls;
  confidence triage automates ~44% of judgments at ~99.6% accuracy in their
  setting.
  Impact: extract-once / judge-many-times pattern maps to monolith→units.

### Offline / batch saturation (single endpoint)

- **[HIGH] Provider Batch APIs as architectural pattern (OpenAI / Anthropic)**
  https://developers.openai.com/api/docs/guides/batch
  Eval / classify / embed as **async JSONL jobs**: separate rate-limit pool,
  no interactive SLA, 24h ceiling (often minutes–hours). The product is
  **headroom isolation**, not only the 50% discount.
  Impact: portable idea without cloud: treat whisker fleet as a **batch
  lane** — fill `max_num_seqs=16`, short decode, no interactive co-tenants,
  accept paper-level latency variance for higher sustained utilization.

- **[HIGH] DeepEval async / concurrent evaluate**
  https://github.com/confident-ai/deepeval
  `run_async=True`, `AsyncConfig.max_concurrent`, metric pruning, caching of
  identical (input, output) tuples. Guidance: size concurrency to provider
  RPM / local slot count, not “as high as possible.”
  Impact: client c=32 already matches; pruning metrics ≡ cutting unit checks.

- **[HIGH] Offline / continuous-batching utilization**
  DigitalOcean vLLM p99 notes; continuous-batching writeups; prior corpus
  card (swfte): offline / Ray-style batch ~2× vs chatty HTTP on same HW;
  sustained util ~90% vs ~35% online.
  https://www.digitalocean.com/community/tutorials/when-your-vllm-p99
  Chunked prefill + `max_num_batched_tokens` trade TTFT vs ITL; long prefills
  poison decode tails (Sarathi-Serve: up to ~28× ITL blowup).
  Impact: short judge outputs + scoped prompts keep the single MoE in the
  high-utilization decode regime; giant paper resends hurt everyone in the
  batch.

- **[MED] promptfoo / Ragas posture** *(see tapetum 135-promptfoo)*
  High client concurrency helps when tests are independent rows. Does **not**
  fix serial in-document cascades. Offline CI evals still win by **N
  reduction** and caching more than by spinning workers.

---

## Five portable patterns for the tapetum lane

| # | Pattern | What production does | Tapetum mapping (single `alliance-pod`) | Moves |
|---|---------|----------------------|----------------------------------------|-------|
| 1 | **Deterministic / SLM pre-gate before MoE** | LLMTrace DeBERTa; FrugalGPT DistilBERT scorer; Arize “code evals first” | Schema/metadata/heuristic gates + optional dense classifier on live Qwen/Gemma pods; **never** spend a MoE slot on known-pass structure | Cuts **N** |
| 2 | **Ambiguous-band short-circuit** | Fast verdict if conf ∉ [lo,hi]; escalate only the band; shadow-calibrate | Router / metadata short-circuit + unit escalate only when uncertain; track escalation rate as SLO; fail-closed on band miss | Cuts **N**, protects quality |
| 3 | **Upfront route > same-endpoint cascade** | RouteLLM / General Compute: pick tier before generate; avoid serial MoE→MoE | Dense unit lane by default; DeepSeek only on flags / holdout-risk classes. Same-pod cheap→dear MoE cascade is forbidden by latency math | Cuts **N** on MoE, uses sunk dense |
| 4 | **Tiny structured schemas (verdict-first)** | SLMJury ~10 tok; LLMTrace ~60-tok JSON; pass/fail enums | Pin `output_type` to verdict+short reason; hard `max_tokens`; Non-think / low reasoning_effort where quality holds | Cuts **L_eff** |
| 5 | **Offline batch saturation, not interactive chat** | Provider Batch pool; DeepEval async+cache; vLLM continuous batching for bulk | Fleet = throughput job: keep S_eff=16 filled with short-decode judges; no hedge/race; prefer skip+reorder over raising `max_num_seqs`; optional vLLM offline/engine path if HTTP tax measured | Cuts **C** / raises util |

### Explicit anti-patterns (single MoE)

- MoE call → MoE “judge the judge” on the same pod (serial L×2).
- Request hedging / dual-fire against one 16-slot server (steals slots).
- Multi-rubric / multi-unit prompt packing without holdout (RuVerBench).
- Celebrating blended median while escalation rate drifts (bimodal trap).
- Raising client concurrency or `max_num_seqs` past measured TTFT cliff
  (forbidden / already burned in this corpus).

### Arithmetic reminder (from `00-baseline.md`)

```
wall = (N_rem × L_eff) / 16 + T + C − L_abs
```

Patterns 1–3 attack **N_rem**. Pattern 4 attacks **L_eff**. Pattern 5 attacks
**C** (client/queue waste) and keeps the denominator honest at **S_eff=16**.

---

## Sources (unique)

1. https://arxiv.org/abs/2305.05176 — FrugalGPT
2. https://github.com/stanford-futuredata/frugalgpt
3. https://github.com/epappas/llmtrace/issues/88 — Judge cascade primitive
4. https://tianpan.co/blog/2026-04-23-cascade-router-reliability-trap-bimodal-latency
5. https://www.generalcompute.com/blog/cascade-inference-using-small-models-to-route-to-big-ones
6. https://github.com/phanisaimunipalli/glide
7. https://bessavagner.com/blog/sub-second-llm-triage/
8. https://arize.com/llm-as-a-judge/
9. https://developers.openai.com/api/docs/guides/batch
10. https://github.com/confident-ai/deepeval
11. https://www.digitalocean.com/community/tutorials/when-your-vllm-p99
12. Prior corpus cards: `research/tapetum-llm-speedup/05-web.md` Q3/Q5
   (SLMJury, RuVerBench, SAJA, offline~2×)

---

## False-pass / false-fail watch (for personas consuming this note)

- **False-pass:** aggressive pre-gate / ambiguous-band accept without shadow
  calibration → silent defect escape on the 16/381 changers.
- **False-fail:** deadline abort or tiny schema truncating reason → schema
  retry storms that **increase** N on the same pod.

## What would change the pattern ranking

Measured holdout: dense unit lane ≥99% agreement with DeepSeek fused verdicts
at ≤0.3 pt defect-recall loss → Pattern 3 becomes the primary path to ≤600 s.
If agreement fails, Patterns 1+2+4 on MoE-only remain the only legal path.
