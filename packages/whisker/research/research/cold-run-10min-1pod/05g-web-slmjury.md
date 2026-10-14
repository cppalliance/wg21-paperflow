# 05g - Web: SLMJury, JudgeLM, Prometheus, PairRM

**Query:** Small judge models for evaluation. Speed vs teacher MoE. Distill
data volumes. Fastest path to **3× unit decode** on our labels (~**1510**/run)
**without a second V4-Pro**.

**Date:** 2026-07-24  
**Verdict:** usable-with-conditions — literature says **3× unit decode does
not require distillation**. Fastest honest path is **off-shelf dense on an
already-live Alliance pod** (`h200-qwen3-32b` primary) + **payload scoping** +
**SLMJury-style short pass-path tokens**; SFT on 1510 labels alone is below
the JudgeLM scaling floor and slows the decode win by weeks.  
**Confidence:** high on published data volumes / SLMJury budgets; medium on
our 3× wall claim until `vllm bench serve` at 12k/64–256 lands.

**Constraint:** No second DeepSeek-V4-Pro (`00-baseline.md`). Dense offload
to live `SERVICES.toml` endpoints is in scope (`12-dense-offload-architecture.md`).

---

## Findings

- [CRITICAL] **3× unit decode ≠ distill first.** Decode win comes from
  **(a)** dedicated dense queue (stop fighting monolith on MoE S=16),
  **(b)** higher dense `max-num-seqs` (32–48 after scoping),
  **(c)** shorter outputs (SLMJury B=10 beats B=8192 on verifiable domains).
  Evidence: SLMJury arXiv:2606.07810 §4.2; JudgeLM throughput is specialist
  serving, not MoE→dense magic; in-repo `12-dense-offload-architecture.md`,
  `16-dense-judge-candidates.md`, prior `05h-web-judge-distill.md`.
  Impact: days–1 week to a lab 3× decode canary; 6–10 weeks if you wait for
  production-safe SFT + 381/381 parity.

- [CRITICAL] **~1510 labels/run is free teacher data but below JudgeLM's
  smallest scaling point (3.5K).** JudgeLM 7B@3.5K ≈ **75.9%** teacher
  agreement; 7B@100K ≈ **83.7%**; 33B@100K ≈ **90%**. Evidence:
  arXiv:2310.17631 scaling table; BAAI/JudgeLM-100K. Impact: one cold run
  is enough for a LoRA **pilot**, not for a 90% teacher-match ship claim.

- [HIGH] **Public distill volumes cluster at 100K–300K for general judges.**
  JudgeLM 100K GPT-4 (~$4k era); Prometheus Feedback 100K + Preference 200K;
  PandaLM ~300K filtered. PairRM trains on six human-pref corpora (not
  GPT-4 KD of our schema). Impact: do not clone a general JudgeLM from one
  fleet run; if SFT, stay **narrow UnitCheck specialist** and grow to
  **≥5K** (ideally 8–12K) before production gate.

- [HIGH] **SLMJury: off-shelf ≤14B already ~90% on closed-ended binary at
  B=10.** Phi-4 14B **89.55%**, Qwen3-14B **89.51%**, Qwen3-8B **88.96%**
  (N=64,824/config). Quick verdicts match/beat long reasoning on math
  (+2–7%); lose **up to 23%** on general tasks. Evidence: arXiv:2606.07810;
  anishh15.github.io/SLMJury. Impact: our unit lane is closer to binary
  defect discovery than MT-Bench chat scoring — try **short max_tokens
  before SFT**; never cite 89.55% as 381/381 fused-verdict proof
  (`23-small-judge-evaluator.md`).

- [HIGH] **PairRM is the wrong tool shape for unit checks.** 0.4B
  DeBERTa-v3 pairwise ranker, max total context **2048**, scores A vs B
  preferences — not structured `UnitCheck` with quote grounding. Evidence:
  huggingface.co/llm-blender/PairRM; arXiv:2306.02561. Impact: useful as a
  **preference filter / best-of-n** idea, not as the unit-judge replacement.
  Skip for the 3× decode path.

- [MED] **Ensembles/debate are negative EV for latency.** SLMJury: majority
  +0.06% once ~89% saturated; RCR debate **degrades** binary accuracy.
  Impact: one dense specialist + MoE fallback; no jury of three for cold-run.

- [MED] **Dense-vs-MoE decode is not automatic from parameter count.**
  Active params + batch contention dominate; loaded MoE already ~**40 tok/s
  effective** vs solo ~70 (`05h` Card D / P146). Impact: measure
  `h200-qwen3-32b` at production shapes; do not assume 14B dense on the
  **same** MoE host yields 3×.

---

## Distill data volumes (comparison table)

| System | Student size | Teacher / labels | Train N | Notes |
|--------|-------------:|------------------|--------:|-------|
| **SLMJury** | 0.6B–14B off-shelf | None (no FT) | **0** | Eval framework; B∈{10, 8192} |
| **JudgeLM** | 7B / 13B / 33B | GPT-4 | **100K** (+5K val) | Scales 3.5K→100K; ~$4k GPT-4 era |
| **Prometheus 1** | 7B / 13B | GPT-4 Feedback Collection | **~100K** | Rubric + reference; CoT then score |
| **Prometheus 2** | 7B / Mixtral-8×7B | Feedback + Preference | **100K + 200K** | Weight-merge absolute + pairwise |
| **PandaLM** | 7B | GPT-3.5 filtered | **~300K** | From ~1M raw |
| **PairRM** | **0.4B** DeBERTa | 6 human-pref datasets | multi-corpus (HH, UltraFeedback, …) | Pairwise RM, **≠** generative judge |
| **Ours (one cold run)** | — | DeepSeek-V4-Pro unit judge | **~1510** | Free every fleet; 70% zero-defect |
| **Ours (production SFT floor)** | 8B–14B target | same | **≥5K (ideal 8–12K)** | ≈3–8 cold runs and/or hard-neg synth |

JudgeLM agreement vs teacher (plain, val w/o reference; paper table):

| Model | Data | Agreement |
|-------|-----:|----------:|
| 7B | 3.5K | 75.87% |
| 7B | 100K | 83.71% |
| 13B | 10K | 83.19% |
| 33B | 100K | **90.06%** |

Serving anecdote (not our shape): JudgeLM-7B **5K pairs in ~3 min on 8×A100**
with parallel judging + skip-reasoning mode (~133× vs naive single-GPU
reasoned baseline in their fig).

---

## Speed vs teacher MoE (what actually moves L_unit)

| Lever | Mechanism | Expected L_unit vs MoE ~20 s | Needs second V4-Pro? |
|-------|-----------|-----------------------------:|:--------------------:|
| Dedicated dense pod | Units leave MoE contention | large (queue isolation) | **No** — use live dense |
| Dense S=32–48 + FP8 KV | Higher concurrency after scoping | ~2× wall on unit leg | No |
| SLMJury B=10–60 pass path | Cut ~235 out-tok → ~50–80 | decode 3–5× on 70% zero-defect | No |
| Off-shelf 8–14B / live 32B | Smaller / dense TPOT | 1.5–3× **if** bench confirms | No |
| SFT/LoRA on V4 labels | Better agreement, optional shorter schema | quality; decode secondary | No |
| PairRM 0.4B | ms-class rank | N/A (wrong API) | No |
| Twin V4-Pro | S_eff 16→32 | fleet compute, not decode× | **Forbidden** |

**Arithmetic anchor (unit leg only):**  
`T_unit ≈ (N_unit × L_unit) / S_dense` with N≈1510 (or 663 after metadata
short-circuit). At **3×** (L=20→≈6.7 s) and S=48:  
`1510 × 6.7 / 48 ≈ 211 s` dense unit wall. Fleet remains
**`max(T_dense, T_moe)`** — monolith on `alliance-pod` still ~**500–710 s**
without MODERATE call cuts (`12-dense-offload-architecture.md`).  
**3× unit decode is a unit-leg KPI, not a solo path to ≤600 s fleet.**

---

## Fastest path to 3× unit decode (no second V4-Pro)

**Return answer — ordered by calendar, not by eventual quality ceiling.**

### Path F (fastest lab proof) — **days–1 week**

1. **Land payload scoping** (~10–15k tok unit window) — without it dense
   reverts to S≤16 / L≈20 → **negative EV** (`12` Scenario D).
2. **Route unit (+ optional metadata) to `h200-qwen3-32b`** (already live;
   not a second V4-Pro). Keep monolith / oversize-8 / page esc on
   `alliance-pod`.
3. **Apply SLMJury budget doctrine on the dense lane:** Non-think /
   thinking off for pass path; `max_tokens` **10–60** for zero-defect-shaped
   outputs; longer budget only on escalate / low-conf.
4. **Bench:** `vllm bench serve` @ **12k in / 64–256 out** dense vs
   alliance-pod. **Pass criterion for "3× unit decode":** p50 decode
   ≤~2.0 s **or** effective ≥**3×** loaded-MoE tok/s (~40 → ≥120 tok/s)
   **or** end-to-end L_unit ≤~6.7 s at S≥32.

**No SFT required for this milestone.** Quality remains
`QUALITY-UNVALIDATED` until 381/381 A/B (`12` gates).

### Path S (specialist, slower) — **2–3 weeks lab / 6–10 weeks ship**

Only if Path F fails quality (false-clear on the 16 verdict-changing papers
or open-rubric 23% class misses):

1. Export ~1510 `UnitCheck` teacher rows → freeze prompt+schema hash.
2. Grow to **≥5K** (more cold runs and/or defect-injection / swap aug).
3. LoRA **Qwen3-8B** or full/LoRA **14B** (JudgeLM curve prefers ≥13B@10K
   for ~83% broad agreement; our narrower domain may beat that).
4. Serve student on dense pod; MoE fallback on disagree / oversize /
   low-conf. Gate: 381/381 fused parity + golden recall (`25` / `12`).

Prometheus-style 100K+ / PairRM are **out of critical path** for 3× decode.

### Explicit non-paths

| Temptation | Why not |
|------------|---------|
| Twin V4-Pro | Forbidden (`00-baseline.md`) |
| PairRM as unit judge | Wrong modality + 2k context |
| Jury of 3 SLMs | Latency ↑, accuracy ≈ flat (SLMJury) |
| Wait for 100K GPT-4 KD | Wrong teacher; we already mint V4 labels |
| Dense swap **without** scoping | L stays ~20 s → no 3× |

---

## False-pass hypothesis

Ship off-shelf Phi-4 / Qwen3-14B with B=10, cite SLMJury **89.55%**, match
teacher on **1057/1510** empty-defect checks, and miss localized
`candidate_not_found` on the **16/381** verdict-changing papers
(P0957R8-class). Operators declare "3× decode done" while fused quality
quietly regresses.

## False-fail hypothesis

Block all dense decode work because JudgeLM/Prometheus used **100K** labels,
or because PairRM is "the small judge." That confuses **general open-ended
KD** with **narrow unit decode**. Path F needs scoping + bench, not 100K
rows. Rejecting Path F leaves ~1510 unit calls on contended MoE forever.

## What would change my mind

1. Bench shows dense 32B/14B **TPOT worse** than loaded MoE at our shape →
   pivot to **output-token cut on MoE** + call elimination; drop model swap.
2. LoRA on **only 1510** rows hits **≥95% teacher agreement on non-pass**
   holdouts → compress Path S data-growth phase.
3. Fleet wall still >>600 s after 3× unit decode (expected: MoE-bound) →
   confirm 3× is a **unit KPI**, not the 10 min package; pair with MODERATE
   short-circuit / deterministic metadata per `00-baseline.md` arithmetic.

---

## Sources (web)

1. SLMJury — https://arxiv.org/abs/2606.07810 ; https://github.com/anishh15/SLMJury  
2. JudgeLM — https://arxiv.org/abs/2310.17631 ; https://huggingface.co/datasets/BAAI/JudgeLM-100K  
3. Prometheus / Prometheus 2 — https://arxiv.org/abs/2310.08491 ; https://arxiv.org/abs/2405.01535 ;
   https://github.com/prometheus-eval/prometheus-eval ;
   Feedback-Collection / Preference-Collection on Hugging Face  
4. PairRM / LLM-Blender — https://arxiv.org/abs/2306.02561 ;
   https://huggingface.co/llm-blender/PairRM  
5. In-repo priors — `research/cold-run-10min/05h-web-judge-distill.md`,
   `research/cold-run-10min/16-dense-judge-candidates.md`,
   `research/cold-run-10min-1pod/{00-baseline,12-dense-offload-architecture}.md`,
   `research/tapetum-llm-speedup/23-small-judge-evaluator.md`

---

## Arithmetic obligation (unit decode KPI)

```
L_unit_3x ≈ 20 / 3 ≈ 6.7 s
T_unit@S48 ≈ 1510 × 6.7 / 48 ≈ 211 s   # full unit census
T_unit@S48_sc ≈ 663 × 6.7 / 48 ≈ 93 s  # after metadata Tier A+B
wall_fleet = max(T_dense, T_moe@S16) + T + C − L_abs
# S_eff on alliance-pod fixed at 16 — no silent S=32
```

**Bottom line:** Fastest path to **3× unit decode** without a second V4-Pro
is **Path F** (scoped dense offload + short pass-path tokens on live
`h200-qwen3-32b`), not JudgeLM/Prometheus-scale distillation. Use ~1510
labels to **accumulate** toward Path S only if Path F fails the quality gate.
