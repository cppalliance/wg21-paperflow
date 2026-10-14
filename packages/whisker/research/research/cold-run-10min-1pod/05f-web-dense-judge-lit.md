# 05f - Web: dense ~27–32B as LLM-judge / structured verifier vs MoE teachers

**Query:** Qwen3-32B / Qwen3.6-27B / Gemma-4-31B as LLM-judge or structured
verifier vs larger MoE teachers. Agreement rates, latency. Best dense
candidate **class** for offloading unit checks from DeepSeek-V4-Pro on a
single MoE pod (dense offload ≠ second V4-Pro replica).

**Forage date:** 2026-07-24  
**Verdict:** usable-with-conditions — public judge literature and serving
numbers support **Qwen3-class dense ~27–32B** as the offload class; **Gemma-4-31B
is the wrong class for structured unit checks** (JSON/grammar collapse). No
public study measures agreement of these three specifically against
DeepSeek-V4-Pro on our unit schema; A/B still mandatory.  
**Confidence:** medium-high on class ranking from lit; medium on absolute
agreement % transfer; low on Alliance-pod L_eff until `vllm bench serve`.

**Live Alliance endpoints (already paid, in scope):**
`h200-qwen3-32b`, `b300-qwen36-27b`, `b200x2-gemma4` (`SERVICES.toml`).

**Prior (do not rediscover):**
`research/cold-run-10min/16-dense-judge-candidates.md`,
`research/cold-run-10min-1pod/12-dense-offload-architecture.md`,
`research/cold-run-10min/05b-web-llm-judge-harness.md`,
`research/cold-run-10min/05h-web-judge-distill.md`.

---

## Return (one line)

**Best dense candidate class for unit-check offload from DeepSeek-V4-Pro:
Qwen3 dense 27–32B (primary: Qwen3-32B; latency pilot: Qwen3.6-27B). Not
Gemma-4-31B.**

---

## Finding cards

### Agreement / judge quality vs larger teachers

- **[CRITICAL] Judge's Verdict (NVIDIA, arXiv:2510.09738) — size ≠ judge tier**  
  https://arxiv.org/abs/2510.09738 · https://huggingface.co/datasets/nvidia/judges-verdict  
  54 LLM judges on RAG/agent accuracy scoring; Tier 1 = r≥0.80 then Cohen's κ
  vs human consensus (human–human κ≈0.801). **Qwen3-30B-A3B-Instruct-2507**
  lands Tier 1 human-like: κ≈0.780, **|z|=0.04** (closest to natural human
  variation). **gemma-3-27b-it** lands Tier 1 super-consistent: **κ=0.812**,
  z=1.34. Top human-like judges span **30B–72B**; architecture/alignment beat
  raw parameter count.  
  **Caveat:** Qwen3-30B-A3B is MoE-family sibling, not our dense 32B; Gemma-3
  ≠ Gemma-4. Still the strongest public agreement ladder for ~30B-class judges.  
  **Impact:** validates ~30B open-weight judges as Tier 1 vs humans; does
  **not** certify V4-Pro parity on unit defects.

- **[HIGH] Qwen-3-Nemotron-32B-Reward — 32B dense ≈ 70B RM on JudgeBench**  
  https://huggingface.co/nvidia/Qwen-3-Nemotron-32B-Reward  
  Built on **Qwen3-32B**. JudgeBench (as of 2025-05-29): overall **72.3** vs
  Llama-3.3-Nemotron-70B-Reward **73.7** (Knowl 70.1 / Reason 67.4 / Math 78.6
  / **Code 83.3**). Half the size, near-parity overall, **stronger on code**.  
  **Impact:** strongest direct evidence that a **Qwen3-32B dense spine** can
  match a much larger teacher-class reward model on judge-style tasks —
  especially code/structure, closest public analog to unit checks.

- **[HIGH] Cascaded Selective Evaluation — small first, escalate for agreement**  
  https://arxiv.org/abs/2407.18370 (ICLR 2025 Oral)  
  Target human agreement **1−α=0.8**: stronger cascades **80.2%** agreement at
  **77.6%** coverage, **0.215×** GPT-4 cost (−78.5%); weaker cascades
  **80.3%** / **68.3%** coverage / **0.126×** (−87.4%). GPT-4 alone: 77.8%
  agreement at full coverage, guarantee success only 13.9%.  
  **Impact:** production pattern for unit offload = dense first + MoE on
  abstain/ambiguous/fail — not "replace V4-Pro forever."

- **[HIGH] SLMJury / CodeJudge family — closed-ended vs open judging**  
  SLMJury (arXiv:2606.07810): off-shelf ≤14B hit **~89.5%** closed-ended
  oracle at **B=10** tokens; open/general axes can swing **up to ~23%**.  
  CodeJudgeBench (via Emergent Mind / Jiang et al. 2025): Qwen3-8B pairwise
  CodeGen **71.27%** (avg across CodeGen/Repair/TestGen **65.61%**); Softtech
  summary places **Qwen3-32B / QwQ-32B among top open judges** for code, with
  thinking models beating larger non-thinking judges.  
  **Impact:** unit checks (binary defect + short structured fields) sit closer
  to closed-ended / code-judge than MT-Bench chat scoring — Qwen3 dense is the
  right family; do not cite 89% SLMJury as V4-Pro verdict parity.

- **[MED] Future AGI 2026 judge ranking — cascade is the default**  
  https://futureagi.com/blog/best-llm-judge-models-2026/  
  Production stacks: fine-tuned / cheap first pass, frontier on close calls;
  claims **~90%** of volume caught at cheap layer → **~90%** frontier bill cut.  
  **Impact:** reinforces dense-first + MoE escalate; cloud judges forbidden in
  this corpus, but the cascade shape ports.

### Latency / throughput (dense vs large MoE)

- **[HIGH] Artificial Analysis — Qwen3-32B decode faster than large MoE sibling**  
  https://artificialanalysis.ai/models/comparisons/qwen3-5-397b-a17b-vs-qwen3-32b-instruct  
  Qwen3-32B (non-reasoning API median): **~91–94 tok/s** output vs Qwen3.5
  397B-A17B reasoning **~61–68 tok/s**. TTFT similar (~2.4 s API class; not
  our RunPod). Intelligence gap is large (Index 9* vs 34) — expected when
  comparing non-think 32B to reasoning MoE.  
  **Impact:** dense 32B is in the **faster decode class** vs large MoE
  teachers on public APIs; our unit path wants **thinking-capable but
  verdict-first / tiny max_tokens** so decode stays short.

- **[HIGH] Neysa production bench — Qwen3-32B vs Qwen3-235B-A22B concurrency**  
  https://neysa.ai/blog/llama-3-vs-qwen-3-benchmarking-in-production/  
  On 8 GPUs: Qwen3-32B FP8 @ c=100 ≈ **~6099 tok/s** aggregate, TTFT **176 ms**;
  Qwen3-235B-A22B hits a latency wall (c=10 ≈2.6 s E2E → c=50 ≈5.7 s → c=100
  ≈9.1 s).  
  **Impact:** large MoE teachers degrade hard under concurrency; dense 32B
  keeps throughput — matches why MoE V4-Pro at S=16 is the fleet bottleneck
  and why offloading unit volume helps even without a second V4-Pro.

- **[HIGH] Qwen3.6-27B dense vs same-family MoE 35B-A3B — quality↑, speed↓**  
  Official / secondary writeups (HF model card via Groundy, ZoliBen 2026-04):  
  Dense 27B beats MoE 35B-A3B on every listed coding/agent bench (SWE-bench
  Verified **77.2 vs 73.4**, Terminal-Bench 2.0 **59.3 vs 51.5**, SkillsBench
  **48.2 vs 28.7**). MoE sibling is **~3–4× faster** (≈3B active vs 27B).  
  vLLM recipe: MTP for low-latency decode; BF16 needs 1×H200 or 2×H100; FP8
  fits single 40 GB.  
  https://recipes.vllm.ai/Qwen/Qwen3.6-27B ·
  https://groundy.com/articles/qwen36-27bs-dense-architecture-challenges-the-moe-only-playbook-for-flagship/  
  **Impact:** among Alliance dense pods, **27B is the quality-over-sibling-MoE
  choice and likely best raw tok/s among live dense** (smaller + B300 + MTP),
  but judge-specific agreement vs V4-Pro is **unmeasured** — treat as latency
  pilot after 32B A/B.

- **[MED] Gemma-4-31B serving latency is fine; structured JSON is not**  
  InferenceBench (H100): TTFT **~279 ms** @ c=1, ISL=128; scales with TP.  
  https://inferencebench.io/blog/gemma-4-31b-h100-complete-inference-benchmark  
  Cerebras/API: structured outputs + tool calling advertised; reasoning off by
  default.  
  **Counter-evidence (CRITICAL for us):** Ollama #15502 / gemma#622 —
  gemma4:31b under JSON-schema / grammar constraints enters repetition loops;
  short+schema trials report **~0–1/10 valid JSON** on Ollama; vLLM default
  xgrammar can whitespace-pad loop (**0/10** valid) until
  `disable_any_whitespace=True` (~9/10). Free-text string fields in schema are
  the accelerant.  
  https://github.com/ollama/ollama/issues/15502 ·
  https://github.com/google-deepmind/gemma/issues/622  
  **Impact:** our unit path is **structured verifier** (`output_type` /
  schema-in-prompt / constrained JSON). Gemma-4-31B's public failure mode is
  exactly that path — disqualify as primary unit judge even if TTFT looks good.

- **[MED] GPUStack / H100 Qwen3-32B throughput class**  
  https://docs.gpustack.ai/2.0/performance-lab/qwen3-32b/h100/  
  Optimized ShareGPT aggregate **~4.3k tok/s** (baseline ~2.3k) on 1×H100;
  mean TPOT tens–hundreds of ms depending on prompt class. Not our prompt
  shape; use only as "dense 32B is a high-throughput single-GPU class."

### Structured verifier fitness

| Model | Structured / schema evidence | Judge evidence | Latency class vs large MoE |
|-------|------------------------------|----------------|----------------------------|
| **Qwen3-32B** | vllm_thinking schema-in-prompt well-trodden in our stack; Nemotron-32B RM proves judge spine | JudgeBench ~72.3 (RM); CodeJudge family strong; Judge's Verdict sibling Tier 1 | Faster decode (~90+ tok/s API); better concurrency than 235B MoE |
| **Qwen3.6-27B** | Same Qwen tool/thinking family; MTP for short decode | No dedicated JudgeBench card found; beats sibling MoE on coding benches | Likely **fastest** Alliance dense; denser quality than 35B-A3B MoE |
| **Gemma-4-31B** | **Fails** constrained JSON often (rep loops); needs engine workarounds | Gemma-3-27B was Tier 1 super-consistent; **Gemma-4 unproven as judge** | Good TTFT on H100 / dual B200; irrelevant if JSON invalid |

---

## Class ranking for DeepSeek-V4-Pro unit offload

| Rank | Class | Alliance service | Why |
|-----:|-------|------------------|-----|
| **1** | **Qwen3 dense 32B** | `h200-qwen3-32b` | Best public **judge** evidence (Nemotron-32B RM ≈70B; CodeJudge/Qwen3 family); schema path mature; deepest prior throughput modeling (`16`, `12`). |
| **2** | **Qwen3.6 dense 27B** | `b300-qwen36-27b` | Best public **dense-vs-MoE quality** story in-family + expected decode win; promote only after 32B A/B or as parallel latency pilot. |
| **3 — avoid primary** | **Gemma-4 dense 31B** | `b200x2-gemma4` | Structured-output collapse + prior false-fail wording hypothesis; tools_capable does not help UnitCheck schema. |

**Class label to carry forward:** `qwen3-dense-27-32b` (not "any ~30B dense").

---

## Fleet arithmetic (portable, S_eff=16 on MoE)

Baseline cold wall ~3003 s, ~2284 calls, ~20 s/call on V4-Pro @ S=16
(`00-baseline.md`).

If **~1510 unit** (+ optionally **377 metadata**) move to dense at
**L_dense ≈ 8–12 s** and MoE keeps **~400–430** heavy calls:

```
T_moe   ≈ (N_moe × L_moe) / 16
T_dense ≈ (N_dense × L_dense) / S_dense   # S_dense may be 32–48
wall    ≈ max(T_dense, T_moe) + T_overhead
```

Prior heterogeneous math (`12`, `105`): MoE-bound **~620–710 s** after unit
offload — **necessary, not sufficient** for ≤600 s without MODERATE call cuts.
**Quality gate:** 381/381 fused verdict parity before `_LANE_VERSION` bump
(SLMJury ~90% is not enough).

---

## False-pass hypothesis

Ship Gemma-4-31B as "31B dense judge" because Gemma-3-27B had κ=0.812 and
InferenceBench TTFT looks great — then unit lane emits truncated/looped JSON,
retries inflate wall, or silent schema repair masks wrong verdicts while
operators credit "dense 2×."

## False-fail hypothesis

Reject all dense offload because no paper reports "Qwen3-32B κ vs DeepSeek-V4-Pro
on WG21 unit checks" — cascade lit + Nemotron-32B JudgeBench already justify a
**gated** offload (dense first, MoE escalate), which is the only in-scope path
to cut the 1510-call MoE queue without a twin V4-Pro.

## What would change my mind

1. Measured **dense↔V4-Pro unit agreement < ~95%** on verdict-changing papers
   after payload scoping → demote offload to metadata-only / escalate-heavier.
2. Alliance `vllm bench serve` shows **L_dense ≥ L_moe** at our 12k/256 shape
   → class stays quality-OK but latency-negative; abort speed claim.
3. Gemma-4 on **our** vLLM + `disable_any_whitespace` + short enum schemas
   hits **≥99%** valid JSON and 381/381 parity → reopen as rank-2 latency
   contender on dual B200.

---

## Sources (web)

| ID | URL |
|----|-----|
| Judge's Verdict | https://arxiv.org/abs/2510.09738 |
| Cascaded Selective Evaluation | https://arxiv.org/abs/2407.18370 |
| Qwen-3-Nemotron-32B-Reward | https://huggingface.co/nvidia/Qwen-3-Nemotron-32B-Reward |
| SLMJury | https://arxiv.org/abs/2606.07810 |
| Qwen3 LLM-as-a-Judge survey | https://www.emergentmind.com/topics/qwen-3-llm-as-a-judge |
| AA Qwen3-32B vs large MoE | https://artificialanalysis.ai/models/comparisons/qwen3-5-397b-a17b-vs-qwen3-32b-instruct |
| Neysa Qwen3 prod bench | https://neysa.ai/blog/llama-3-vs-qwen-3-benchmarking-in-production/ |
| Qwen3.6-27B vLLM recipe | https://recipes.vllm.ai/Qwen/Qwen3.6-27B |
| Qwen3.6 dense vs MoE | https://groundy.com/articles/qwen36-27bs-dense-architecture-challenges-the-moe-only-playbook-for-flagship/ |
| Gemma-4 JSON collapse | https://github.com/ollama/ollama/issues/15502 |
| Gemma-4 InferenceBench | https://inferencebench.io/blog/gemma-4-31b-h100-complete-inference-benchmark |
| Future AGI judges 2026 | https://futureagi.com/blog/best-llm-judge-models-2026/ |
