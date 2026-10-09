# 05h - Web forage: LLM-judge distillation → 7B–14B dense (SLMJury + peers)

**Query:** Distill MoE/LLM judges into 7B–14B dense models. Training-data needs,
agreement rates, serving speed vs MoE teacher. Relevance: cut unit-check
**decode** 3–5× using own labeled data (~**1510** judgments / cold run).

**Date:** 2026-07-24  
**Verdict:** usable-with-conditions — specialist 7B–14B judges are a proven
distillation target (JudgeLM / Prometheus / PandaLM), and SLMJury shows
off-the-shelf ≤14B can hit ~90% closed-ended oracle agreement at **10 output
tokens**. One cold run (~1510 labels) is **below** the JudgeLM scaling floor
(3.5K); expect **2–3 weeks to a lab 3–5× decode proof**, **6–10 weeks to a
production-safe unit-lane swap** (matches prior AGGRESSIVE dense-offload gate).  
**Confidence:** medium-high on literature numbers; medium on our wall arithmetic
(decode 3–5× ≠ fleet 3–5×; MoE pod still binds after offload).

---

## Card A — SLMJury: off-shelf ≤14B judges (no fine-tune)

**Source:** Laddha et al., arXiv:2606.07810 (2026); leaderboard
anishh15.github.io/SLMJury; code github.com/anishh15/SLMJury  
**Relevance:** HIGH — closest public study of **7B–14B dense as judges** under
explicit **token budgets** (decode cost).

### Findings

- [CRITICAL] **16 SLMs (0.6B–14B), 10 benchmarks, N=64,824 judgments/config.**
  Closed-ended binary + SummEval/MT-Bench open scoring. Best closed-ended:
  **Phi-4 14B @ B=10 tokens → 89.55%** oracle accuracy; Qwen3-14B 89.51%;
  Qwen3-8B 88.96%. Evidence: paper abstract + leaderboard. Impact: a dense
  8–14B can already judge closed-ended tasks near 90% **without** distillation
  if the task is binary/correctness-like (our unit check is closer to this
  than MT-Bench pairwise).

- [HIGH] **Overthinking is domain-dependent (decode killer).** Quick 10-token
  verdicts **match or beat** B=8192 reasoning on math judging (+2–7% where they
  help); reasoning wins on **general** tasks by **up to 23%**. Always-thinking
  models cannot use B=10 (reasoning tokens eat the budget). Impact: for
  pass-heavy unit checks (1057/1510 zero-defect), a **verdict-first / ≤10–60
  tok** budget is the largest decode lever *orthogonal* to model size; do not
  enable thinking mode on the dense student for the pass path.

- [HIGH] **Closed ≠ open judging.** Best binary judge (Phi-4) drops to rank 9
  on MT-Bench (ρ≈0.21); Phi-4-Reasoning rises to rank 1 (ρ≈0.57). Impact:
  do not cite SLMJury 89.55% as proof a 14B will match DeepSeek-V4 on our
  open-ended defect quotes / rubric; A/B on **our** unit schema is mandatory.

- [MED] **Ensembles / debate are negative EV for latency.** Top-3 majority
  adds ≈+0.06% once accuracy saturates near 89%; RCR multi-agent debate
  **degrades** binary accuracy across tested configs. Impact: skip jury/debate
  for the 10 min cold-run goal; one dense specialist + MoE fallback is enough.

- [MED] **SLMJury is evaluation, not distillation.** Table 1 explicitly
  contrasts JudgeLM/Prometheus (trained 7–33B) vs SLMJury (off-the-shelf ≤14B).
  Impact: SLMJury answers "can a dense 14B judge?"; JudgeLM answers "how much
  teacher data to train one?"

### Take for us

Unit checks are **defect discovery + binary verdict** with structured schema,
not MT-Bench chat scoring. SLMJury supports: (1) try **Qwen3-8B/14B or Phi-4
off-shelf** with **B≈10–60** before spending weeks on SFT; (2) expect quality
risk on general / open rubric axes up to the 23% swing.

---

## Card B — JudgeLM: GPT-4 → 7B/13B/33B distillation scaling

**Source:** Zhu et al., JudgeLM (ICLR 2025 / arXiv:2310.17631);
dataset BAAI/JudgeLM-100K; github.com/baaivision/judgelm  
**Relevance:** CRITICAL — only paper with a **data-size × model-size**
agreement curve for judge distillation.

### Training data

| Split | N | Teacher |
|-------|--:|---------|
| Train | 100K seed tasks (≈$4k GPT-4 at collection time) | GPT-4 judgments ± reference |
| Val | 5K | GPT-4 |

Also generated judgments **with and without** reference answers (2× labels per
seed). Techniques: swap augmentation, reference support, reference drop
(position / knowledge / format bias).

### Agreement vs teacher (plain JudgeLM, val w/o reference)

| Model | Data | Agreement | Consistency |
|-------|-----:|----------:|------------:|
| 7B | 3.5K | 75.87% | 73.45% |
| 7B | 10K | 78.89% | 78.25% |
| 7B | 30K | 81.43% | 80.89% |
| 7B | 100K | 83.71% | 82.62% |
| 13B | 3.5K | 80.61% | 78.91% |
| 13B | 10K | 83.19% | 81.90% |
| 13B | 100K | 85.87% | 83.01% |
| 33B | 100K | **90.06%** | **87.93%** |

Published JudgeLM-7B (with methods) ≈ **81–84%** agreement; JudgeLM-33B ≈
**89–90%**, claimed above human-human MT-Bench max (~82%).

### Serving speed (paper claim)

JudgeLM-7B: **~3 minutes to judge 5K samples on 8×A100** (batch eval, not
our interactive RunPod shape). Still: specialist 7B judges were built
explicitly for **throughput**, not just agreement.

### Take for us

- **1510 labels ≈ 0.4× JudgeLM's smallest scaling point (3.5K).** At 7B/3.5K
  they only hit ~76% teacher agreement on a broad pairwise task. Our domain
  is narrower (WG21 conversion units), so LoRA on a strong instruct base may
  beat that curve, but **one cold run is not enough** for a 90% teacher-match
  claim.
- Useful zone for open-weight SFT: **~5–15K** in-domain judgments
  (≈ **4–10 cold runs**, or 1–2 runs + synthetic hard-negatives / swap /
  defect injection).
- Target student size for quality: **8–14B** (JudgeLM 13B@10K ≈ 83% already;
  7B needs more data for the same agreement).

---

## Card C — Prometheus / PandaLM / LlamaIndex (data + agreement peers)

**Sources:**  
- Prometheus (Kim et al., arXiv:2310.08491): Feedback Collection **100K**,
  Llama-2-Chat 7B/13B; Pearson **0.897** vs humans with rubric+reference
  (GPT-4 teacher ≈0.882 in their setup).  
- Prometheus site: 1K rubrics → 20K instructions → 100K responses+feedback.  
- PandaLM (Wang et al.): **300K** filtered GPT-3.5 labels (from 1M raw);
  PandaLM-7B ≈ **88% of GPT-4** F1 on human test; 1K human test set.  
- LlamaIndex judge KD (docs): GPT-4 → GPT-3.5 with **~79** correctness
  examples → correlation **0.87→0.93**; pairwise FT agreement **~84%→87%**
  on tiny holdout.  

**Relevance:** HIGH for "how little data can work?"

### Findings

- [HIGH] **Public open-weight judges almost all train on 100K–300K teacher
  labels** for general-purpose pairwise/rubric judging. That is **66–200×**
  one of our cold runs. Impact: do not plan a general JudgeLM clone from
  1510 rows; plan a **narrow unit-check specialist**.

- [HIGH] **Tiny-N distillation works when teacher and student share API /
  format and the task is single-axis** (LlamaIndex correctness, N≈79).
  Impact: a **LoRA on Qwen3-8B** with 1.5–5K in-domain unit labels can move
  agreement if schema + prompt are frozen; it will not match JudgeLM's
  broad pairwise numbers.

- [MED] **Prometheus trains feedback-then-score (CoT FT)** with a `[RESULT]`
  delimiter to stop degeneration. Impact: keep **verdict-last or
  verdict-first + short reason** disciplined; long free-text feedback
  destroys the decode win.

---

## Card D — Serving: dense 7B–14B vs MoE teacher (decode)

**Sources:** Junyi TPU v6e MoE vs dense-32B; Gemma-4 H100 dense 31B vs
26B-A4B MoE (Markaicode); Epoch AI MoE vs dense inference note; Infercom
active-param decode; prior in-repo `105-vllm-dense-judge-throughput.md`,
`146-verifier-prefix-cache-contradiction.md`.

### Findings

- [CRITICAL] **Decode is memory-bandwidth bound → active params, not total
  params, set tok/s.** Large MoE with few active experts can **beat** a dense
  32B on TPOT (e.g. Qwen3-30B-A3B 7.0 ms vs dense-32B 17.9 ms BS1 on TPU
  v6e). Impact: swapping DeepSeek-V4-Pro → dense **14B does not
  automatically** give 3–5× decode. Measure. Our MoE under 16-slot load is
  already **~40 tok/s effective** (5.91 s decode / ~235 out tok, P146), far
  below solo **~70 tok/s** docstring — contention, not architecture, is half
  the pain.

- [HIGH] **Where dense wins for us:** (1) **dedicated pod** so unit checks
  stop fighting monolith on the MoE batch; (2) **higher `max-num-seqs`**
  (32–48 feasible on H200 for scoped 10–15k inputs, P105) that MoE cannot
  take (slots-32 → +57% wall); (3) **shorter outputs** (SLMJury B=10 /
  verdict-first) cutting decode tokens 5–10× on the 70% pass path; (4)
  **smaller student** (7–8B) if agreement holds. Combined, **3–5× per-call
  decode** is realistic; **architecture-only** swap of 14B dense onto the
  same contended MoE host is not.

- [HIGH] **JudgeLM-7B throughput claim** (5K/3 min / 8×A100) is batch-eval
  friendly. Our shape is long-prefill unit packets + short JSON. Prior P105
  models dense unit **L≈8–12 s** at S=32–48 after scoping vs MoE **~20 s**
  at S=16 → roughly **2× wall on the unit leg from slots+L**, not full 5×,
  unless outputs also shrink.

- [MED] **Speculative decoding (MTP/DFlash)** helps dense more under light
  concurrency; under c=16 TTFT can blow up (Gemma-4 H100). Impact: for fleet
  unit checks prefer **short max_tokens + high max-num-seqs**, not speculative
  decoding as the first lever.

---

## Card E — Mapping onto tapetum unit-check economics

**In-repo anchors (do not rediscover):**  
`research/cold-run-10min/00-baseline.md`,  
`research/tapetum-llm-speedup/{10,14,105,146,SYNTHESIS,48}.md`.

| Quantity | Value |
|----------|------:|
| Unit checks / cold run | **1510** |
| Zero-defect unit checks | **1057 (70%)** |
| Unit wall share (slot model) | **~1888 s / 3003 s** |
| Mean decode vs prefill | **5.91 s vs 0.46 s** |
| Effective decode rate (loaded MoE) | **~40 tok/s** (~235 out tok) |
| Prior dense-offload eng estimate | **6–10 weeks** (P48 / P105) |

### Implications

1. **Decode 3–5× on unit calls** ⇒ target **~1.2–2.0 s** decode or
   **~120–200 tok/s** effective, *or* cut mean output tokens from ~235 →
   ~50–80 (verdict-first pass path) while holding tok/s.
2. **1510 labels/run** are free teacher supervision every cold run — but
   need **accumulation + holdout** before trusting a student.
3. Distillation is AGGRESSIVE-tier (SYNTHESIS); quality gate remains
   **381/381 fused verdict parity** + MoE fallback on disagreement /
   oversize payloads (P105).

---

## Timeline (return answer)

### Realistic path to **unit-check decode 3–5×** with own labels

Assumptions: teacher = current MoE unit judge; student = Qwen3-8B or 14B /
Phi-4 dense on a **dedicated** H200-class pod; payload scoping lands or
inputs stay ≤~15k; pass-path `max_tokens` tightened (SLMJury-style).

| Phase | Calendar | Exit criterion |
|-------|----------|----------------|
| **0. Freeze contract** | 2–3 days | Export 1510 sidecar judgments → JSONL (prompt, scoped source, `UnitCheck` teacher). Freeze system prompt + schema hash. Hold out ≥2 golden PRs + 10% random papers. |
| **1. Grow data past JudgeLM floor** | **1–2 weeks** | Reach **≥5K** (ideally **8–12K**) via 3–5 more cold runs **or** 1–2 runs + swap/defect-injection/synthetic hard negatives. 1510 alone → expect JudgeLM-like **~75%** teacher agreement ceiling on a 7B, not 90%. |
| **2. SFT / LoRA student** | 2–4 days | LoRA on 8B or full/LoRA 14B; train feedback→verdict or verdict-first short reason. Smoke: parse IFR ≥99%, agreement on holdout. |
| **3. Decode bench (lab 3–5×)** | 3–5 days | `vllm bench serve` @ production shapes (12k in / 64–256 out) on dense vs alliance-pod MoE. **Pass if unit decode ≤1.2–2.0 s or ≥3× tok/s vs loaded MoE (~40 tok/s).** This is the earliest honest "3–5× decode" claim. |
| **4. Cascade A/B (quality)** | **3–6 weeks** | Dense-first; MoE on low-conf / disagree / oversize. Gate: 381/381 fused parity + no new false-clears on golden set (prior P105). Only then bump `_LANE_VERSION`. |

### Headline numbers

| Milestone | Realistic time | Notes |
|-----------|----------------|-------|
| **Lab proof: unit decode 3–5×** | **~2–3 weeks** | Needs data ≥5K + dense pod bench; may lean on **short max_tokens** as much as distillation |
| **Production unit-lane offload** | **~6–10 weeks** | Same band as prior AGGRESSIVE dense-judge estimate (P48:238–243, P105) |
| **One cold run (1510) only** | **insufficient** | Below JudgeLM 3.5K floor; OK for LoRA pilot, not for 90% teacher-match ship |
| **Decode win without any SFT** | **days–1 week** | Off-shelf Phi-4 / Qwen3-14B + B=10–60 + dedicated pod (SLMJury); higher quality risk on open defects |

### What would falsify this timeline

- Holdout teacher agreement **≥90%** after LoRA on **only 1510** rows (domain narrower than JudgeLM → accelerate to ~3–4 weeks production).  
- Dense 14B TPOT **worse** than loaded MoE (active-param trap) → pivot to **output-token cut + MoE cascade**, not model swap.  
- Payload scoping slips → dense KV caps S≤16 → timeline still burns but **decode 3–5× fails** (P105).

---

## False-pass / false-fail

**False-pass:** Ship a 14B student that matches teacher on the 70% zero-defect
majority, claim "89% SLMJury," and miss the **16/381** verdict-changing
papers (defect recall is the product metric, not majority accuracy).

**False-fail:** Reject distillation because public papers use 100K labels;
LlamaIndex shows narrow-axis judges move with **<100** examples, and our
every cold run already mints 1510 free labels.

## What would change my mind

A measured dual-pod canary: student vs teacher on **≥500 held-out unit
checks** with (a) verdict + defect-span agreement, (b) p50 decode seconds,
proving **≥3× decode and ≥95% teacher verdict agreement on non-pass cases**.
Then compress production gate toward **4–6 weeks**.
