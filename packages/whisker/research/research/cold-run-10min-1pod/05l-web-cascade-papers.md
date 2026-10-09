# 05l - Web: cascade LLM judges (cheap → expensive)

**Query:** Jung Cascaded Selective Evaluation, FrugalGPT, LLM cascade/routing
surveys. Numbers for cost/latency cut while keeping agreement. Design return:
**monolith = Pro, units = dense**.

**Date:** 2026-07-24  
**Verdict:** usable — literature supports cheap-first escalate for *judges*
with **~50–98% cost cut** at matched quality / **≥80% agreement with
calibration**; for our fleet the portable shape is **dense unit lane + Pro
monolith**, not a second V4-Pro.  
**Confidence:** high on published cascade numbers; medium on our wall (depends
on payload scoping + dense parity A/B already gated in `12-dense-offload-architecture.md`).

**Fleet anchors (do not re-derive):** `00-baseline.md`,
`12-dense-offload-architecture.md`. Dense offload ≠ twin Pro pod.

---

## Card A — Jung et al.: Cascaded Selective Evaluation (judge cascade)

**Source:** Jung, Brahman, Choi — *Trust or Escalate: LLM Judges with Provable
Guarantees for Human Agreement* (ICLR 2025 Oral), arXiv:2407.18370  
**Relevance:** CRITICAL — cascade purpose-built for **LLM-as-judge**, with
**human-agreement risk control**, not general QA.

### Mechanism

1. Cheap judge scores the instance + estimates confidence that humans would
   agree (Simulated Annotators: K-shot multi-persona ICL → agreement ratio).
2. If confidence ≥ calibrated λ → **trust** and stop.
3. Else **escalate** to next stronger judge. Thresholds from fixed-sequence
   testing on a small human-pref calibration set (risk α, error δ).

### Headline numbers

| Setting | Target agreement | Coverage / composition | Cost vs GPT-4 alone |
|---------|-----------------:|------------------------|---------------------|
| ChatArena, cascade | ≥80% human | ~79% coverage; **88.1%** of covered done by Mistral-7B or GPT-3.5 | — |
| ChatArena, stronger cascade (incl. GPT-4 tier) | 1−α = 0.8 | High guarantee success | **−78.5%** |
| ChatArena, weaker cascade (Mistral → Mixtral → GPT-3.5, no GPT-4) | 1−α = 0.8 | Trades coverage for cost | **−87.4%** (≈ **12.6%** of GPT-4 cost) |
| TL;DR | 1−α = 0.9 | Cascade only method with high guarantee success + high coverage | Majority of evals on 7B / 3.5 |
| Simulated Annotators N=1..5 | 1−α = 0.85 | Larger N → better coverage; N=1 still OK | Up to **−40%** API cost vs GPT-4 no-abstention |

Simulated Annotators: **−50% ECE**, **+13% AUROC** vs predictive/verbalized
confidence (GPT-4 on AlpacaEval). Weak judges stay usable as *first* tier
because they calibrate *when they would agree*, even if absolute accuracy is
lower.

### Take for us

- Our unit checks are closer to closed/binary defect discovery than ChatArena
  pairwise chat. Jung’s **escalate-on-low-confidence** maps cleanly:
  dense unit → Pro only on ambiguous / low-conf / schema-invalid.
- Do **not** port Simulated Annotators N=5 as-is (multiplies judge calls). Prefer
  structured confidence already in schema (verdict + severity + defect quote)
  + calibration on our labels; keep N≤1 unless A/B proves coverage lift.
- Fail-closed: low conf / abstain → escalate or `review`, never silent pass.

---

## Card B — FrugalGPT: learned LLM cascade (generation + stop judge)

**Source:** Chen, Zaharia, Zou — *FrugalGPT* (TMLR 2024 / arXiv:2305.05176)  
**Relevance:** HIGH — canonical cheap→expensive cascade with learned stop score.

### Mechanism

Query ordered APIs cheap→expensive. Generation scoring function `g(q,a) ∈ [0,1]`
(DistilBERT-class quality estimator in paper). Accept if score ≥ threshold;
else next LLM. Router learns sequence + thresholds on validation under budget.

### Headline numbers

| Claim | Magnitude |
|-------|----------:|
| Match best single LLM (e.g. GPT-4) performance | up to **98%** inference cost reduction |
| Same cost as GPT-4 | up to **+4%** accuracy (abstract); up to **~5%** in figure discussion |
| Example (OVERRULING) | **+1%** accuracy and **−73%** cost vs GPT-4 alone |
| Price heterogeneity motivating cascade | API fees differ by **~100×** |

Example cascade logic (paper HTML): accept ChatGPT answer if score > **0.96**,
else escalate (thresholds task-specific).

### Take for us

- FrugalGPT’s external DistilBERT scorer is optional; AutoMix/Jung show
  self-verify or selective confidence can substitute.
- **98%** is an upper envelope on heterogeneous classification/QA APIs — do not
  promise 98% wall cut on our MoE fleet. Portable claim: **most easy unit
  checks should never touch Pro**.

---

## Card C — AutoMix: self-verify + POMDP escalate

**Source:** Aggarwal et al. — *AutoMix* (NeurIPS 2024), arXiv:2310.12963  
**Relevance:** HIGH — black-box friendly; few-shot self-verify before escalate.

### Mechanism

1. Small LM generates answer.  
2. Same (or small) LM few-shot **self-verifies** (entailment-style).  
3. POMDP / threshold meta-verifier decides accept vs escalate to larger LM
   (and can refuse “unsolvable” to avoid wasted strong calls).

### Headline numbers

| Claim | Magnitude |
|-------|----------:|
| Cost cut at comparable performance | **>50%** across 5 LMs × 5 hard datasets |
| vs naive always-large | consistently better cost–quality Pareto (IBC metric) |

### Take for us

- Self-verify adds a call; only worth it if it **prevents** a Pro call more
  often than it costs. For unit lane: prefer **schema confidence + cheap
  dense once**, not dense + verify + Pro on every item.
- POMDP overkill for v1; threshold on structured fields is enough.

---

## Card D — Agreement-Based Cascading (ABC)

**Source:** Kolawole, Dennis, Talwalkar, Smith — *Agreement-Based Cascading*
(TMLR), arXiv:2407.02348; github.com/stevenkolawole/Agreement-Based-Cascading  
**Relevance:** MED–HIGH — training-free deferral via ensemble agreement.

### Headline numbers

| Scenario | Saving |
|----------|-------:|
| Edge→cloud communication | up to **14×** |
| Cloud GPU rental | **~3×** |
| Black-box LLM API vs SOTA cascades | **2–25×** avg $/token or $/request |

Ensemble at a tier exits early on unanimous / majority agreement; else escalate.

### Take for us

- **Latency trap:** tier-1 ensemble of 2–3 dense models can beat one Pro on
  *cost* but **hurts** wall if serial on one client. SLMJury also finds
  ensembles ~neutral once accuracy saturates.
- For ≤10 min cold run: **one dense specialist**, not ABC jury at unit tier.
  Optional: dual-sample agreement only on escalate candidates (rare path).

---

## Card E — Surveys / routing cousins (cascade vs route)

**Sources:**

- *Dynamic Model Routing and Cascading for Efficient LLM Inference: A Survey*
  (arXiv:2603.04445) — taxonomy: **route** = one pre-pick; **cascade** =
  cheap first, escalate on quality fail. FrugalGPT = mix (router + quality
  estimator + stop judge). Dekoninck et al. unify route+cascade.
- RouteLLM (LMSYS, 2024) — **pre-generation** router: **95% of GPT-4** quality
  with up to **−85%** cost (MT-Bench); **−45%** MMLU; **−35%** GSM8K; best
  MF router ~**14%** GPT-4 calls after LLM-judge augmentation.
- Industry writeups (e.g. tianpan.co 2025-11): cascade latency stacks; prefer
  route when p95 latency binds, cascade when calibration + safety net matter.

### Routing vs cascade for our wall

| Pattern | Extra latency on hard path | Fits unit offload? |
|---------|----------------------------|--------------------|
| Route (classifier → dense \| Pro) | ~0 model hops if correct | Yes for **call class** (monolith vs unit) — already decided by pipeline stage |
| Cascade (dense → ? Pro) | +L_dense on escalate | Yes for **per-unit confidence** |
| Hybrid | route class, cascade within unit | **Recommended** |

RouteLLM’s −85% is **not** a second hop; Jung/FrugalGPT pay sequential
latency on the escalate fraction. Our wall formula is
`max(T_dense, T_moe)` — escalate fraction must stay small or Pro queue
re-binds.

---

## Numbers cheat-sheet (cite in synthesis)

| Paper | Cost / compute cut | Quality / agreement held |
|-------|-------------------:|--------------------------|
| Jung stronger cascade | **78.5%** | Guaranteed **≥80%** human agreement (calibrated) |
| Jung weaker cascade | **87.4%** | Same guarantee, lower coverage |
| Jung ChatArena composition | **88%** of covered on cheap judges | ≥80% human agreement @ ~79% coverage |
| FrugalGPT | up to **98%** vs best LLM | Match best accuracy; or **+4%** @ same $ |
| AutoMix | **>50%** | Comparable task performance |
| ABC (API) | **2–25×** vs SOTA cascades | Competitive accuracy |
| RouteLLM (route, not cascade) | up to **85%** | **95%** of GPT-4 (MT-Bench) |
| PoLL (panel; 05b) | **>7×** vs GPT-4 judge | Better human corr. on studied tasks |

**Latency caveat (all cascades):** hard queries pay **sum of tier latencies**.
Survey consensus: calibrate exit rate so escalate fraction is small
(Jung: often **≤15–30%** to strongest tier when coverage is high).

---

## Cascade design — monolith = Pro, units = dense

Maps literature → Alliance fleet under **one** `alliance-pod` (DeepSeek-V4-Pro)
plus **existing** dense endpoints (`h200-qwen3-32b` primary;
`b300-qwen36-27b` pilot #2; avoid `b200x2-gemma4` for units — markup
false-fail, see `12-dense-offload-architecture.md`).

```
paper
  │
  ├─► [Pro / alliance-pod]  monolith | HTML tier-1 | oversize units | escalate
  │         S_eff = 16, L ≈ 19–20 s, full context (393k)
  │
  └─► [dense / h200-qwen3-32b]  unit checks (scoped md)
            S_client = 32–48 (after scoping), L_target = 8–12 s
            │
            ├─ confident pass/fail + schema-valid  → ACCEPT (Jung stop)
            └─ low conf | invalid schema | severity≥X | router flag
                      → ESCALATE → Pro unit re-judge (FrugalGPT/AutoMix)
```

### Tier roles

| Tier | Service | Workload | Exit rule |
|------|---------|----------|-----------|
| T0 deterministic | CPU | metadata short-circuit / diff (when landed) | never LLM |
| T1 dense judge | `h200-qwen3-32b` | ~82.6% of LLM calls (units) | accept if structured conf ≥ λ and schema OK |
| T2 Pro judge | `alliance-pod` | monolith, HTML tier-1, oversize (>dense ctx), escalate band | always authoritative for whole-doc; unit escalate overwrites dense |

### Escalation policy (portable from Jung/FrugalGPT/AutoMix)

Escalate unit → Pro if **any**:

1. Missing / invalid structured fields (fail-closed).
2. Self-reported or logit conf &lt; λ (calibrate λ on holdout for
   fused-verdict parity ≥ target; start λ so escalate ≈ **10–20%** of units).
3. Defect quote empty on non-pass, or unit id not in scoped payload.
4. Dense timeout / 5xx (retry once dense, then Pro).
5. Paper flagged oversize for dense context → **skip T1**, Pro only.

Do **not** escalate on every `review` if fusion already caps; prefer accept
`review` from dense when conf high (cuts Pro queue).

### Confidence without Simulated Annotators tax

Prefer (cheapest → richer):

1. Verdict-first schema + short max_tokens (SLMJury B≈10–60 on pass path).
2. Single verbalized conf field in JSON (calibrate; Jung shows raw verbalized
   overconfident — threshold from our labels).
3. Optional: second dense sample only if conf ∈ grey band (ABC-lite); never
   5× ICL annotator sim on cold path.

### Wall arithmetic (literature-shaped, fleet numbers)

From `12-dense-offload-architecture.md` Scenario C class:

| Leg | Calls (order) | L | S | T |
|-----|--------------:|--:|--:|--:|
| Dense units (after MODERATE short-circuit) | ~1040 | ~8–10 s | 32–48 | **~180–220 s** |
| Pro monolith + esc + oversize | ~428 | ~20 s | 16 | **~510–540 s** |
| **Heterogeneous wall** | | | | **max ≈ 510–540 s** (MoE-bound) |

Literature’s **78–87% judge-cost cut** ≈ fraction of *unit* work that stays on
dense. It does **not** shrink monolith T; cascade wins only if escalate band
stays small. If escalate → **30%** of units, Pro adds
`0.3 × N_unit × 20 / 16` and can push wall back above 600 s.

**Target escalate rate:** ≤15% of dense unit attempts (Jung-like strong-tier
share). Instrument `{accepted_dense, escalated_pro, dense_conf, fused_delta}`.

### Quality gates (unchanged, cascade-specific add-ons)

1. 381/381 fused verdict parity: dense-accept path vs all-Pro baseline.
2. Zero-defect cohort (1057/1510): no silent false-clear on dense-accept.
3. Escalation A/B: among escalated set, Pro must change fused outcome often
   enough to justify cost; if rarely, raise λ (more dense accept).
4. Calibration set: few hundred human or Pro-oracle labels → pick λ for
   agreement ≥ target (Jung fixed-sequence testing if we want formal bound).

### Explicit non-goals

- Twin `h200x8-deepseek-v4-pro` (forbidden).
- ABC multi-dense jury on every unit (latency).
- Cloud proprietary judges (baseline forbidden).
- FrugalGPT DistilBERT router training before schema-threshold cascade ships.

---

## False-pass / false-fail

**False-pass:** Cite FrugalGPT **98%** or Jung **87%** as proof cold wall ≤600 s
without scoping / escalate-rate control — those % are **API $ or judge-call
mix**, not `max(T_dense,T_moe)` under S=16 Pro.

**False-fail:** Reject cascade because sequential latency “always doubles
wall” — only escalate fraction pays double; Jung keeps most work on cheap
tier. Heterogeneous pods hide T1 under T2 when MoE-bound.

## What would change my mind

- Measured escalate rate &gt;25% with λ set for 381/381 parity → cascade EV
  collapses; need better dense student (distill, 05h) or more short-circuit.
- Dense L stays ≥20 s after scoping → negative EV (`12`); cascade irrelevant
  until decode fixed.
- Formal Jung risk control required by product → budget calibration labels
  + Simulated Annotators only on escalate band, not fleet-wide.

---

## Sources

- https://arxiv.org/abs/2407.18370 — Jung Cascaded Selective Evaluation  
- https://arxiv.org/abs/2305.05176 — FrugalGPT  
- https://arxiv.org/abs/2310.12963 — AutoMix  
- https://arxiv.org/abs/2407.02348 — Agreement-Based Cascading  
- https://arxiv.org/abs/2603.04445 — Routing & cascading survey  
- https://www.lmsys.org/blog/2024-07-01-routellm/ — RouteLLM  
- Sibling: `05b-web-llm-judge-harness.md`, `05h-web-judge-distill.md`,
  `12-dense-offload-architecture.md`
