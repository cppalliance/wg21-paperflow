# 05p - Web: FrugalGPT / AutoMix / cascade routing (latency)

**Verdict:** usable-with-conditions — published cascades routinely keep **~70–85%** of queries on the cheap model at matched quality, but cascade *latency* is additive on escalations, so wall-clock savings need predictive routing or a cheap first hop much faster than V4-Pro, not a same-size cascade.
**Confidence:** high (on literature % ranges); medium (on transfer to dissect unit-checks).

**Headline number (return):** typically **~70–85% of calls can stay on the cheap model** (escalation **~15–30%**). Optimistic peer-reviewed peaks: **~83–86%** cheap / **~14–17%** strong. Ops target for cascades: keep escalation **under ~30%**.

## Findings

- [CRITICAL] FrugalGPT HEADLINES case study (budget ≈ 1/5 GPT-4 cost): cascade invokes GPT-J → J1-L → GPT-4; **only 16.6% of queries reach GPT-4**, so **~83.4% never need the expensive model**. Intermediate stage: ~33.7% of queries escalate past GPT-J to J1-L. Evidence: Chen et al., FrugalGPT TMLR / arXiv:2305.05176, Figure 2 (e) caption ("FrugalGPT sends only 16.6% queries to GPT-4"); also https://lingjiaochen.com/papers/2024_FrugalGPT_TMLR.pdf. Impact: if unit-checks have a similar easy/hard split, offloading ~5/6 of MoE judge calls to a dense pod cuts alliance-pod N sharply toward ≤600 s.

- [HIGH] FrugalGPT cost-matched quality: **50–98% cost savings** vs best single LLM (HEADLINES **98.3%**, OVERRULING 73.3%, AGNEWS 75.4%, COQA 59.2%, SCIQ 52.3%). Oracle pairwise on HEADLINES: Llama-3-70B identical to GPT-4 Turbo on **87%** and better on **5%** → **92%** of queries need not go to GPT-4 Turbo. Evidence: same paper Table 2 / Figure 1(c). Impact: upper bound on "stay cheap" for classification-like tasks is ~90%+, not 50/50.

- [HIGH] RouteLLM (LMSYS / ICLR 2025): matrix-factorization router hits **95% of GPT-4 quality with only 14% of calls to GPT-4** on MT Bench → **86% stay on weak model**; reported **>85% cost cut** on that bench (MMLU/GSM8K need more strong calls: ~54% GPT-4 for 95% quality on MMLU with domain aug). Evidence: https://www.lmsys.org/blog/2024-07-01-routellm/ ; arXiv:2406.18665. Impact: predictive routing (pick once) is the latency-friendly cousin of FrugalGPT cascades.

- [HIGH] AutoMix (NeurIPS 2024): SLM generate → few-shot self-verify → POMDP escalate; **>50% compute cost cut** at comparable quality vs always-LLM. Router overhead **&lt;1 ms**; network ~10 ms ≪ generation (seconds). Evidence: Aggarwal et al. arXiv:2310.12963 §latency; NeurIPS PDF. Ops guidance (LLMRouter Automix README): monitor routing %, **aim 20–40% escalation** (i.e. **60–80% stay on SLM**). Impact: verification adds an SLM call even when you do not escalate — latency/cost of "stay cheap" is not free in cascade designs.

- [MED] HybridLLM (Ding et al., arXiv:2404.14618): **predictive** router (DeBERTa) picks small vs large once — no sequential double-generate. On small gap (Llama-2 7B vs 13B): **20–40% to small** at ≤0.2% quality drop; abstract: up to **40% fewer large-model calls** with no quality drop. Explicitly contrasts cascades as paying multiple LLM invocations. Evidence: https://arxiv.org/html/2404.14618. Impact: for cold-run wall clock, HybridLLM-style routing beats FrugalGPT-style cascade when the cheap hop is not much faster than the expensive one.

- [MED] Production / survey rules of thumb for cascade economics: cascades win when cheap model handles a large majority and **escalation stays under ~30%** (else you pay C_cheap on every request *plus* C_expensive on escalations). Worked example: 80% solvable by small + 95% judge precision → **~76% resolved by small alone**, ~24% escalate; escalated path latency ≈ L_small + L_judge + L_big (e.g. 300 ms + 50 ms + 1.5 s ≈ 1.85 s vs 1.5 s direct = **~23% latency penalty on escalations**). Evidence: https://www.generalcompute.com/blog/cascade-inference-using-small-models-to-route-to-big-ones ; https://jatinbansal.com/ai-engineering/model-routing/. Impact: on a latency SLO (fleet wall), p99 is dominated by the escalate path; average wall still drops if escalate rate is low *and* cheap L ≪ expensive L.

- [LOW] Industry roundups commonly quote **60–70%** cheap share (~37–46% cost cut) as the "safe" production band and **~80%** cheap (~70%+ cost cut) as the aggressive band; RouteLLM's **86%** is the peer-reviewed optimistic end on chat-like benches. Evidence: secondary digests citing RouteLLM / cascade practice (treat as corroboration, not primary). Impact: for planning arithmetic, use **~75% stay cheap** as the central planning assumption unless A/B says otherwise.

## Latency vs cost (cascade-specific)

| Design | Calls per query (typical) | Latency shape | Cheap-stay % (literature) |
|--------|---------------------------|---------------|---------------------------|
| Always strong | 1× strong | L_strong | 0% |
| Predictive router (HybridLLM / RouteLLM) | 1× (small or strong) + tiny classifier | max(L_small, L_strong) + ms | **~60–86%** small |
| Cascade + external judge (FrugalGPT) | 1× cheap (+1× mid) (+1× strong) | **sum** along escalate path | **~70–83%** stop before strong |
| Cascade + self-verify (AutoMix) | ≥1× SLM + verify samples + optional LLM | **sum**; POMDP &lt;1 ms | **~60–80%** accepted at SLM (ops target) |

For this corpus: alliance-pod L ≈ 20 s/call. A cascade that still runs V4-Pro as the first hop does **not** help wall. Cascade/routing only helps if the cheap hop is a **faster dense endpoint** already in SERVICES.toml, and escalate fraction stays in the **15–30%** band.

## False-pass hypothesis

Dissect unit-checks look "easy" in aggregate (high cheap-stay %), but a DistilBERT/DeBERTa-style scorer trained on classification/QA labels **over-accepts** analytical objections → false OK / missed fail-closed. Literature judges are trained on answer correctness, not WG21 objection fidelity.

## False-fail hypothesis

Self-verification (AutoMix) or a strict FrugalGPT threshold **over-escalates** on long paper chunks → escalate rate drifts toward 40–90%, cascade becomes **slower and more expensive** than always-dense or always-V4-Pro. Monitor escalate % as an SLO.

## What would change my mind

- Measured escalate rate on a 50–100 paper dissect sample with a concrete dense judge (Qwen/Gemma) vs V4-Pro: if cheap-stay **&lt;50%** at fail-closed quality, literature 70–85% does not transfer.
- If cheap dense L_eff is not ≪ 20 s (e.g. similar decode length / queue), even 80% stay-cheap may miss the 600 s wall under S_eff=16.

## Arithmetic sketch (illustrative only)

Assume after v11 short-circuit N_rem ≈ 1200 calls, L_eff=20 s, S_eff=16:

- Always V4-Pro: wall ≈ (1200×20)/16 = **1500 s**
- Predictive offload with **75% stay cheap**, L_cheap=5 s, L_strong=20 s, escalate 25%:  
  L_eff ≈ 0.75×5 + 0.25×20 = **8.75 s** → wall ≈ (1200×8.75)/16 ≈ **656 s** (near 600; needs slightly higher cheap-stay or lower L_cheap)
- Same split but **cascade** (always pay L_cheap, then +L_strong on 25%):  
  L_eff ≈ 5 + 0.25×20 = **10 s** → wall ≈ **750 s** (worse than predictive)

## Sources (primary)

1. Chen, Zaharia, Zou — FrugalGPT, arXiv:2305.05176 / TMLR PDF  
2. Aggarwal et al. — AutoMix, arXiv:2310.12963 / NeurIPS 2024  
3. Ding et al. — Hybrid LLM, arXiv:2404.14618  
4. Ong et al. — RouteLLM, arXiv:2406.18665 ; LMSYS blog 2024-07-01  
5. Cascade latency/econ blogs: General Compute cascade inference; Jatin Bansal model routing
