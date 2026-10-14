# 16 - Dense-Judge Offload Candidates

**Verdict:** usable-with-conditions — four live dense open-weight pods (27B–70B) can offload **1887/2284 (82.6%)** of tapetum LLM calls (1510 unit + 377 metadata/outline) off `alliance-pod` / DeepSeek-V4-Pro MoE, but **no candidate has measured verdict parity**; speed gains are **2–2.5× per call (hypothesis ~850–1200 s fleet savings)**, not sufficient alone for ≤600 s without paired call cuts.

**Confidence:** medium (throughput arithmetic grounded in personas 23/105; quality unproven)

**Date:** 2026-07-24. Sources: `SERVICES.toml`, `MODELS.md`, `research/tapetum-llm-speedup/{00-baseline,23-small-judge-evaluator,105-vllm-dense-judge-throughput,48-combined-lever-modeler,76-olmocr-dense-model-choice,SYNTHESIS}.md`, `research/cold-run-10min/00-baseline.md`.

---

## Scope

**Offload target:** unit checks (~1510 calls) and metadata/outline checks (377 calls). Monolith (381), page escalations (~16), and oversize payloads stay on MoE (`393216` context only on `alliance-pod` / `h200x8-deepseek-v4-pro`).

**Baseline comparator:** DeepSeek-V4-Pro MoE on H200 @ `--max-num-seqs 16`, ~**20 s/call** fleet mean, ~**70 tok/s** solo decode but ~**19 tok/s** loaded per-user decode at c=16 (`tapetum-llm-speedup/00-baseline.md`, `105-vllm-dense-judge-throughput.md`).

**Quality parity:** **Not claimed.** Persona 23 requires **381/381 fused verdict parity** + matching `defect_groups` / `evidence_dispositions` on all 16 verdict-changing papers before `_LANE_VERSION` bump. SLMJury ~90% oracle agreement would still miss verdict-changing papers (`23-small-judge-evaluator.md`). Any parity statement below is tagged **HYPOTHESIS**.

---

## Live open-weight pods: dense 7B–70B filter

From `SERVICES.toml` active `[services.*]` entries. Backend for all candidates: `vllm_thinking` (`MODELS.md`: schema-in-prompt JSON, `<think>` strip, greedy sampling pins).

| Service | Model | Size class | Active params | Context | Thinking | Tools | Dense? |
|---------|-------|------------|---------------|---------|----------|-------|--------|
| `h200-qwen3-32b` | `Qwen/Qwen3-32B` | **32B dense** | 32B | 131072 | yes | no | yes |
| `b200x2-gemma4` | `google/gemma-4-31B-it` | **31B dense** | 31B | 131072 | yes | **yes** | yes |
| `b300-qwen36-27b` | `Qwen/Qwen3.6-27B` | **27B dense** | 27B | 131072 | yes | no | yes |
| `b200-r1` | `deepseek-r1-distill-70B` | **70B dense** | 70B | 131072 | yes | no | yes |

### Excluded from dense offload inventory

| Service | Reason excluded |
|---------|-----------------|
| `alliance-pod`, `h200x8-deepseek-v4-pro` | MoE baseline judge, not offload target |
| `b300-qwen3-235B-A22B-FP8` | MoE (~22B active), outside dense 7–70B class |
| `anthropic-opus` | Not open-weight / not self-hosted |
| `# b200-qwen35` (commented) | MoE 122B-A10B, not live |
| `# b200-llama` (commented) | Would qualify (70B dense) but **not live** |

### Gap: no live 7B–14B pod

Personas 23/76 propose future **Qwen3-8B** or **Phi-4-14B** fine-tunes (SLMJury anchor, `05-web.md:88-90`) but **no 7B–14B service is declared live** in `SERVICES.toml`. Long-term specialist path only (`76-olmocr-dense-model-choice.md`).

---

## Why dense may decode faster than DeepSeek-V4-Pro MoE (mechanisms)

Evidence-backed vs inferred:

1. **MoE continuous-batch penalty (measured external + baseline).** At concurrency 16, MoE per-user decode ~**19 tok/s** vs solo ~**70 tok/s** (~3.7× penalty); raising MoE `--max-num-seqs` 16→32 adds **+57–60% wall** (`slots-32-regression`, `105`). Dense 32B can target **S=32–48** with FP8 KV (`105`).

2. **Higher feasible server concurrency (KV math, persona 105).** Scoped unit payload ~10–15k tokens (not yet implemented; today full `candidate_md`): dense Qwen3-32B on 1×H200 supports ~**22 seqs** BF16 KV or ~**44** with `--kv-cache-dtype fp8` at 12k tokens/req. MoE recipe locks at **16 seqs**.

3. **Per-token compute (hypothesis).** Dense 27–32B activates all weights every token; MoE V4-Pro routes experts — total FLOPs per token typically lower for dense at same hardware when batch is KV-bound, but **no clone benchmark quotes Qwen3-32B vs V4-Pro on our prompt shape**.

4. **External Qwen3-32B anchor (not our pod).** Prefix-heavy benchmark **427→1513 tok/s** aggregate with APC (+254%, `05-web.md:70-73`); APC does not shrink decode for unique suffixes. Conservative unit-check **L=8–12 s** at S=32–48 vs MoE **L≈20 s** (`105` table).

5. **Payload scoping prerequisite (not landed).** Without scoping, p95 markdown ~134k chars breaks 131k effective budget; dense pod reverts to **S≤16**, **L≈20 s** → **negative EV** vs queue isolation alone (`105`, `23`).

---

## Speedup persona synthesis (dense-judge)

| Persona | Key claim | Impact on 3003 s cold run |
|---------|-----------|---------------------------|
| **23-small-judge-evaluator** | Only unit + metadata movable; 373/381 fit 131k @ 0.80 margin; 8 need MoE fallback | **~850–1200 s** save at 2–2.5× per-call on 82.6% of calls |
| **105-vllm-dense-judge-throughput** | Heterogeneous fleet wall = **max(T_dense, T_moe)**; MoE leg ~620–710 s still limits | Dense alone **~2300 s** saved vs baseline but **>600 s** without router/metadata cuts |
| **48-combined-lever-modeler** | AGGRESSIVE package adds dense-judge + metadata diff + router | Target **~300–500 s** only with **all** levers + validation |
| **76-olmocr-dense-model-choice** | Raw dense swap < fine-tuned 7–14B specialist; SFT on V4-pro labels | Same **~850–1200 s** near-term; quality needs distillation, not raw swap |
| **00-baseline (tapetum)** | Dense 32B "decodes SUBSTANTIALLY faster" than MoE V4-pro per token | Listed as lever #5 in AGGRESSIVE tier |
| **cold-run-10min/00-baseline** | Lever #7 settled ranking: dense-judge offload | Delta re-verify, not rediscover |

**False-clear hypothesis (23):** P0957R8-style localized omission; dense judge returns zero defects on 70% zero-defect cohort while V4-pro would flag `candidate_not_found`.

**False-fail hypothesis (23):** Gemma-4 / Qwen3-32B mis-read sanctioned `:::wording-remove` / `<del>` blocks → spurious structure defects.

---

## Per-candidate profile

### 1. `h200-qwen3-32b` — primary AGGRESSIVE anchor

| Field | Value |
|-------|-------|
| Size class | 32B dense |
| Thinking / tools | yes / **no** (schema-in-prompt OK for unit checks) |
| GPU | 1×H200 (inferred from service name) |
| Persona coverage | **23, 105, 76, 48, 00-baseline** — deepest throughput modeling |
| Decode speedup vs MoE | **2–2.5×** inferred (`L=8–12 s` @ S=32–48 with scoping); **HYPOTHESIS** until `vllm bench serve` on pod |
| Quality parity | **HYPOTHESIS ONLY** — 381/381 A/B gate not run |

**Why faster (ranked):** (1) dense + higher `max-num-seqs` feasible; (2) no MoE expert routing under batch load; (3) external Qwen3-32B throughput class; (4) dedicated queue removes 1510 calls from MoE contention.

---

### 2. `b300-qwen36-27b` — smallest live dense

| Field | Value |
|-------|-------|
| Size class | 27B dense |
| Thinking / tools | yes / no |
| GPU | B300 |
| Persona coverage | **23** lists explicitly; no dedicated throughput persona |
| Decode speedup vs MoE | **≥2× HYPOTHESIS** — smaller than 32B → likely highest tok/s among live pods; no measured bench |
| Quality parity | **HYPOTHESIS ONLY** — smaller model may increase false-clear risk vs 32B |

**Why faster:** Same mechanisms as #1; fewer parameters → **hypothesis** best raw decode latency; more KV headroom for S=48–64 if scoping lands.

---

### 3. `b200x2-gemma4` — tools-capable dense

| Field | Value |
|-------|-------|
| Size class | 31B dense |
| Thinking / tools | yes / **yes** (only live dense with `tools_capable = true`) |
| GPU | 2×B200 (`b200x2` prefix) |
| Persona coverage | **23, 76**; false-fail wording hypothesis names Gemma explicitly |
| Decode speedup vs MoE | **~2× HYPOTHESIS** — TP-2 may add comm overhead vs single-GPU 32B; net unknown |
| Quality parity | **HYPOTHESIS ONLY** — higher false-fail on wording markup (persona 23) |

**Why faster:** Dense decode + dual B200 memory bandwidth; tools flag irrelevant for current `UnitCheck` schema path but may help future cascade tooling.

---

### 4. `b200-r1` — 70B thinking distill

| Field | Value |
|-------|-------|
| Size class | 70B dense |
| Thinking / tools | yes / no |
| GPU | B200 |
| Persona coverage | **21, 22** (heterogeneous cascade warning only); **no throughput modeling** |
| Decode speedup vs MoE | **≤2× HYPOTHESIS, possibly <1.5×** — 70B dense is heavier than 32B; R1 thinking blocks may inflate output tokens (`31-thinking-token-auditor` class risk) |
| Quality parity | **HYPOTHESIS ONLY** — reasoning style differs from V4-pro; no A/B |

**Why faster (weak case):** Still dense (no MoE routing penalty); likely **slower per token than 27–32B** candidates. Only attractive if quality tracks V4-pro better than smaller dense — **untested**.

---

## Ranked offload candidates (with risk tags)

| Rank | Service | Expected speed tier | Risk tags |
|------|---------|---------------------|-----------|
| **1** | `h200-qwen3-32b` | **HIGH** (2–2.5× inferred, best documented) | `QUALITY-UNVALIDATED` `AB-GATE-381` `MOE-FALLBACK-8` `PAYLOAD-SCOPE-BLOCKER` `FALSE-CLEAR` `LANE-VERSION-BUMP` `THROUGHPUT-INFERRED` |
| **2** | `b300-qwen36-27b` | **HIGH** (fastest dense **hypothesis**) | `QUALITY-UNVALIDATED` `SMALLER-MODEL-DRIFT` `AB-GATE-381` `MOE-FALLBACK-8` `PAYLOAD-SCOPE-BLOCKER` `FALSE-CLEAR` `NO-BENCH-DATA` |
| **3** | `b200x2-gemma4` | **MED–HIGH** (2× **hypothesis**, TP overhead unknown) | `QUALITY-UNVALIDATED` `FALSE-FAIL-WORDING` `AB-GATE-381` `MOE-FALLBACK-8` `PAYLOAD-SCOPE-BLOCKER` `NEWER-ARCH-HYPOTHESIS` |
| **4** | `b200-r1` | **LOW–MED** (70B + thinking overhead) | `QUALITY-UNVALIDATED` `THINKING-TOKEN-PENALTY` `AB-GATE-381` `MOE-FALLBACK-8` `NO-THROUGHPUT-PERSONA` `FALSE-CLEAR` |

### Risk tag legend

| Tag | Meaning |
|-----|---------|
| `QUALITY-UNVALIDATED` | No 381-paper A/B; swapping judge changes lane semantics (`105` CRITICAL) |
| `AB-GATE-381` | Required: 100% fused verdict parity on 381 papers, not ~90% SLMJury |
| `MOE-FALLBACK-8` | 8/381 papers exceed 131k effective budget; must route to V4-pro |
| `PAYLOAD-SCOPE-BLOCKER` | Full `candidate_md` per unit check not scoped; dense S≥32 may fail (`105`) |
| `FALSE-CLEAR` | Silent pass on localized omission (persona 23 P0957R8 hypothesis) |
| `FALSE-FAIL-WORDING` | Spurious defects on sanctioned markup (persona 23, Gemma/Qwen) |
| `THINKING-TOKEN-PENALTY` | Thinking models emit extra tokens → decode-bound slowdown |
| `THROUGHPUT-INFERRED` | Speed from external Qwen3-32B / proportional model, not measured on pod |
| `NEGATIVE-EV-WITHOUT-SCOPE` | Offload without scoping + FP8 KV can **increase** wall (`105` false-pass) |
| `LANE-VERSION-BUMP` | Fingerprint binds model identity; swap requires cold rerun (`cli.py:99-117`) |

---

## Operational layout (persona 105)

**Proposed heterogeneous fleet:**

- **Dense pod:** 1510 unit checks → ranked candidate #1–#2 default.
- **MoE pod:** 381 monolith + 377 metadata (if not also offloaded) + 8 oversize unit fallbacks + ~16 page escalations.
- **Wall:** `max(T_dense, T_moe)` ≈ **620–710 s** MoE-bound without call elimination — dense offload **necessary but insufficient** for ≤600 s.

**Metadata/outline on dense:** 377 calls, tiny payload (`unit_judge.py:241-256`); same quality gate as unit checks (`23`).

---

## Quality parity status (explicit)

| Claim | Status |
|-------|--------|
| Dense 32B matches V4-pro findings on unit checks | **HYPOTHESIS — no evidence** |
| 2× speed without verdict drift | **HYPOTHESIS — proportional model only** |
| Fine-tuned 7–14B beats raw 32B swap on quality | **HYPOTHESIS — olmocr/SLMJury analog, not our task** |
| Metadata LLM replaceable by deterministic diff | Separate AGGRESSIVE lever (`SYNTHESIS` #7); not dense-judge parity |

---

## Recommended validation order

1. **Payload scoping** to ~10–15k tokens (unblocks S=32–48 KV math).
2. **`vllm bench serve`** on `h200-qwen3-32b` vs `alliance-pod` at **12k/256** and **40k/900** prompt shapes (`105`).
3. **Pilot A/B:** unit + metadata only, `h200-qwen3-32b` vs `alliance-pod`, 381 papers, persona 47 protocol.
4. If #1 passes, evaluate `b300-qwen36-27b` for incremental decode win before Gemma/R1.

---

## False-pass hypothesis (fleet level)

Ship dense judge at `--max-num-seqs 64` without FP8 KV or payload scoping: KV preemption inflates latency to ≥20 s, operators attribute success to "dense 2×" from prefix-heavy benchmarks that do not match short JSON decode — fleet stays **>15 min** (`105`).

## False-fail hypothesis (fleet level)

Reject all dense offload because clone lacks Qwen3-32B cards: even inferred dense **35–50 tok/s** at S=48 saves **~700–1100 s** on the 1510-call leg when MoE-bound; abandoning second pod leaves unit checks competing with monolith on one MoE queue (`105`).

## What would change this ranking

Measured cold run with dual routing: (1) bench sweeps on top two pods at production shapes; (2) `{pod, cached_tokens, latency}` per call; (3) **381/381 verdict parity**. If `b300-qwen36-27b` shows **L_unit ≤8 s** at S=48 **and** parity holds, it overtakes `h200-qwen3-32b` for default offload.
