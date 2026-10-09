# 05v - Web: VLLM_BATCH_INVARIANT throughput cost

**Verdict:** garbage (for speed) — `VLLM_BATCH_INVARIANT=1` is a determinism/reproducibility switch that intentionally slows inference; never enable it on the cold-run ≤10 min path.
**Confidence:** high

**Decision for this corpus:** **REJECT for speed path.** Do not set `VLLM_BATCH_INVARIANT` on `alliance-pod` as a throughput lever. Leave it off unless a separate quality/stability campaign explicitly accepts a large wall-clock regression.

## Findings

- [CRITICAL] **Official docs state batch invariance trades performance for reproducibility.** Evidence: [vLLM Batch Invariance (stable)](https://docs.vllm.ai/en/stable/features/batch_invariance/) and [latest](https://docs.vllm.ai/en/latest/features/batch_invariance/): enable via `export VLLM_BATCH_INVARIANT=1`; when enabled, vLLM uses deterministic kernels, consistent numerics across batch sizes, and **disables optimizations that introduce non-determinism** (e.g. custom all-reduce in TP). Docs quote: "Enabling batch invariance may impact performance compared to the default non-deterministic mode. This trade-off is intentional to guarantee reproducibility." Feature is **beta** ([Issue #27433](https://github.com/vllm-project/vllm/issues/27433)). Impact: enabling BI moves wall **away** from ≤600 s; it is anti-aligned with this corpus's speed goal.

- [CRITICAL] **Upstream PR quantifies ~50% throughput reduction.** Evidence: [vLLM PR #30018](https://github.com/vllm-project/vllm/pull/30018) (merged): "Enabling batch-invariant mode results in approximately **50% throughput reduction** in our tests." Mechanism includes forcing deterministic FA2/LoRA paths (`num_splits` / `split_k=1`). Impact on single-pod arithmetic with `S_eff=16`: if `L_eff` roughly doubles, wall roughly doubles for the same `N_rem` — e.g. a post-MODERATE ~1400 s fleet would become ~2800 s, not approach 600 s.

- [HIGH] **Field repro on MTP shows ~3× decode slowdown under BI.** Evidence: [vLLM Issue #42518](https://github.com/vllm-project/vllm/issues/42518) (cited in prior corpus `research/tapetum-llm-speedup/103-vllm-mtp-determinism.md`): maintainer recommendation is `VLLM_BATCH_INVARIANT=1` for token-id parity; reporter measured MTP eager **~75→23 tok/s** with BI on. Impact: BI can erase MTP decode gains that this corpus might otherwise pursue; bundling BI with speed flags is self-defeating.

- [HIGH] **Purpose is batch-composition determinism, not latency.** Evidence: docs + env description ([env vars](https://docs.vllm.ai/en/v0.22.1/configuration/env_vars/)): "deterministic results regardless of batch composition." Default is off (`VLLM_BATCH_INVARIANT` getenv default `"0"`). Our cold-run already runs shared continuous batching at c=32 / 16 slots; BI would make that path slower while solving a different problem (rerun bit-stability). Impact: wrong tool for ≤10 min wall; quality-stability for this fleet remains "same findings," not bit-exact (see `MODELS.md`).

- [MED] **DeepSeek-V4-Pro not on the documented tested-model list; BI is still beta.** Evidence: prior local read of vLLM `batch_invariance.md` (via `103-vllm-mtp-determinism.md`) lists DeepSeek-V3/R1/V3.1 and Qwen3 MoE, not V4-Pro; docs still mark beta and list "Performance optimizations" as future work. Impact: even if someone wanted BI for stability, alliance-pod would need a dedicated A/B; that is out of scope for the speed path.

## Arithmetic (why reject)

Assume BI ≈ 2× `L_eff` (PR #30018 ~50% throughput cut):

`wall ≈ (N_rem × L_eff_BI) / 16 + T + C − L_abs` with `S_eff=16` fixed.

Any plan that enables BI **increases** `L_eff` and cannot close the ~800–900 s gap to 600 s. Speed path must keep BI **off**.

## False-pass hypothesis

Someone enables `VLLM_BATCH_INVARIANT=1` hoping "more stable kernels = faster / less retry," then reports a green microbench on concurrency=1 and claims a speed win. Reality: docs and PR #30018 say the opposite; fleet wall would worsen under continuous batching.

## False-fail hypothesis

Someone rejects all determinism work because BI is slow, then claims quality is impossible. False: BI is the right lever for **bit-exact / rerun identity** campaigns, not for cold-run wall. Speed and bit-exactness are separate knobs; this persona only rejects BI **for speed**.

## What would change my mind

- Upstream ships a BI mode with documented **≤5%** throughput tax on H200 TP8 DeepSeek-V4-Pro continuous batching, measured on our pod; or
- A cold-run plan whose goal flips from ≤600 s wall to bit-exact CI stability (different corpus).

Until then: **confirm reject for speed path — never enable `VLLM_BATCH_INVARIANT` for speed.**

## Sources (web)

1. https://docs.vllm.ai/en/stable/features/batch_invariance/
2. https://docs.vllm.ai/en/latest/features/batch_invariance/
3. https://docs.vllm.ai/en/v0.22.1/configuration/env_vars/
4. https://github.com/vllm-project/vllm/pull/30018 (~50% throughput reduction)
5. https://github.com/vllm-project/vllm/issues/27433 (tracking / beta)
6. https://github.com/vllm-project/vllm/issues/42518 (MTP + BI ~3× tok/s drop)
