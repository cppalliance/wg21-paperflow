# 05d - Web forage: DeepSeek MTP / speculative decoding (vLLM)

**Date:** 2026-07-24  
**Scope:** DeepSeek V3/V4 MTP on vLLM — acceptance rates, determinism, structured JSON.  
**Prior (do not rediscover):** `research/tapetum-llm-speedup/38-speculative-decoding-scout.md`, `103-vllm-mtp-determinism.md`, `05-web.md`.  
**This card:** fresh external delta + short-output (55–200 tok) decode-bound judge verdict.

---

# 05d - Web-MTP-SpecDecode

**Verdict:** usable-with-conditions — MTP k=1 is a real decode lever for DeepSeek V3/V4 on vLLM when acceptance stays high and CUDA graphs are on; short judge JSON (~55–200 tok) is above the GB300 OSL=64 “cannot amortize” cliff for decode-bound calls, but not a free lunch for quality-stability or structured-output edge cases.
**Confidence:** high (acceptance/speedup numbers from multiple sources); medium (fleet A/B still required for verdict drift)

## Findings

- [CRITICAL] **Enablement on vLLM is native MTP, no separate draft weights.** Config: `--speculative-config '{"method":"mtp","num_speculative_tokens":1}'` (older aliases: `deepseek_mtp`). Docs: [vLLM MTP](https://docs.vllm.ai/en/latest/features/speculative_decoding/mtp/), [speculative decoding overview](https://docs.vllm.ai/en/stable/features/speculative_decoding/). DeepSeek-V4 keeps the same MTP modules as V3 ([V4 report](https://arxiv.org/html/2606.19348)). Impact: pod-restart flag only; no client change.

- [CRITICAL] **Healthy k=1 acceptance clusters ~80–90% at temp=0; collapsed acceptance is a known bug class, not “MTP is useless”.** Evidence:
  - vLLM PR [#12755](https://github.com/vllm-project/vllm/pull/12755): R1 k=1 acceptance **81–82.3%**; speedup **1.63× TPOT at QPS=1**, ~1.0× by QPS=8.
  - GB300 blog (2026-02-13): R1 MTP k=1 acceptance **>80%**; helps concurrency **≤256**; hurts at very high concurrency ([gb300-deepseek.html](https://blog.vllm.ai/2026/02/13/gb300-deepseek.html)).
  - HF canada-quant V4-Flash MTP: **89% calibrated / 70% random**, **1.49×** decode at bs=1 k=1.
  - Issue [#33497](https://github.com/vllm-project/vllm/issues/33497): V3.2 acceptance collapsed to **~15%** (temp≠0 bench) / **~56%** (temp=0 after MoE compile regression); fixed in hotfix PR #33624 — **91%** restored on pre-regression commit. Impact: treat acceptance as a **runtime health metric** (`vllm:spec_decode_*`); if <~60%, disable MTP.

- [CRITICAL] **Short-output amortization: OSL≈64 is the danger zone; 55–200 tok decode-bound judges are usually OK at k=1.** GB300: at ISL=2k, OSL=64, “decode proportion is extremely low … MTP overhead cannot be amortized” → MTP **worse** than off at both low and high concurrency. Our fleet unit-check / terse JSON sits ~55–200 tok with **decode >> prefill** (baseline decode 5.91 s vs prefill 0.46 s mean). Impact: for a **decode-bound** judge, k=1 should still win if acceptance ≥~70%; **k≥2** on ~55-tok tails is the anti-pattern (single-layer DeepSeek MTP weights also degrade for k>1; Ascend docs warn accuracy/perf not guaranteed for MTP≥3).

- [HIGH] **Determinism: algorithmically lossless at greedy; not hardware bit-exact vs non-MTP.** vLLM docs: theoretical + algorithmic losslessness; greedy-with-spec == greedy-without in e2e tests; still disclaim FP/batch-size drift ([lossless section](https://docs.vllm.ai/en/stable/features/speculative_decoding/)). Issue [#42518](https://github.com/vllm-project/vllm/issues/42518): MTP verify batch_size=2 vs decode batch_size=1 → argmax flips in **eager**; CUDA graphs restore token identity; `VLLM_BATCH_INVARIANT=1` fixes but can erase most MTP gain. Impact: for quality-stability, ship MTP only with CUDA-graph decode (not eager) and A/B verdict counts; do not claim bit-identical fingerprints.

- [HIGH] **Structured JSON + reasoning + MTP has been repeatedly broken and patched.** Issues/PRs: [#34650](https://github.com/vllm-project/vllm/issues/34650) (missed `</think>` → grammar never armed), [#44927](https://github.com/vllm-project/vllm/pull/44927) (MTP off-by-one in `should_advance`), [#43424](https://github.com/vllm-project/vllm/pull/43424) (post-boundary bonus garbage before JSON), [#44993](https://github.com/vllm-project/vllm/pull/44993) (reasoning-boundary grammar advance; `json_object`+MTP k=4 went 0/50→50/50 clean JSON), [#44006](https://github.com/vllm-project/vllm/issues/44006) (strict tool calling + MTP FSM fail; reporter notes DeepSeek V4 + MTP). Impact: JSON schema mode is **compatible in principle** (rejection sampling still target-distribution) but **version-sensitive**; alliance-pod image must include these fixes before trusting structured judges under MTP.

- [MED] **Speedup is latency/QPS-sensitive, not a constant 1.5×.** PR #12755 table: 1.63×→1.0× as QPS 1→8. Spec decode docs: best under medium-to-low QPS, memory-bound decode. Impact: at 16 concurrent slots, expect **modest** wall savings (prior scout ~7–16% of cold wall), not a path to 10 min alone.

- [LOW] **V4 MTP config identical to V3; method name prefers `mtp`.** V4 paper: “MTP configuration remains identical to DeepSeek-V3.” Prefer `method: mtp` over legacy `deepseek_mtp` on current vLLM.

## Acceptance rate cheat-sheet

| Source | Model | k | Temp | Acceptance | Notes |
|--------|-------|---|------|------------|-------|
| PR #12755 | DeepSeek-R1 | 1 | (greedy bench) | 81–82% | 1.63× @ QPS=1 |
| GB300 blog | R1-0528 | 1 | — | >80% | Helps ≤256 conc |
| HF canada-quant | V4-Flash | 1 | — | 89% / 70% | calibrated / random |
| #33497 pre-fix | V3.2 | 1 | 0 | ~56% | MoE compile bug |
| #33497 fixed baseline | R1-NVFP4 | 1 | 0 | ~91% | same setup |
| #33497 broken + temp≠0 | V3.2 | 1 | >0 | ~15–28% | do not bench at default temp |

## False-pass hypothesis

MTP + unpatched structured-output path silently disables grammar after reasoning end (`should_advance` miss); model emits free-text that still parses as “valid enough” JSON for a soft validator → unit check marks pass while schema constraints never ran.

## False-fail hypothesis

Enable recipe k=2 (or k=1 under OSL≈55 pass-path JSON with heavy prefill) → acceptance/overhead makes TPOT worse; operators blame “MTP quality” and disable a lever that would have helped at k=1 on decode-bound 100–200 tok calls.

## What would change my mind

Alliance-pod cold A/B: `mtp` k=1 + CUDA-graph decode vs baseline, logging `spec_decode_draft_acceptance_rate`, structured JSON validity rate, and pass/review/fail counts. Flip to **usable** if acceptance ≥70%, JSON validity ≥ baseline, and flip_AB ≤ flip_AA + margin. Flip to **garbage** if acceptance <60% or structured/reasoning regressions reappear on the installed image.

---

## Recommendation (decode-bound judge, ~55–200 output tokens)

**yes / conditions**

| | |
|--|--|
| **Answer** | **Yes, with conditions** |
| **Conditions** | (1) `method=mtp`, **`num_speculative_tokens=1` only**; (2) CUDA-graph decode path (not eager); (3) measure acceptance ≥~70% on real judge traffic; (4) vLLM build that includes structured-output×MTP reasoning-boundary fixes if using reasoning+JSON schema; (5) fleet A/B before treating as quality-neutral. |
| **No if** | Expecting bit-exact non-MTP equality without batch-invariant mode; OSL≪64 with prefill-dominated calls; k≥2 on single-layer DeepSeek MTP; unpatched image for reasoning+structured JSON. |
