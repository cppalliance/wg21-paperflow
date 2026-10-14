# 41 — vLLM GitHub issues: DeepSeek MoE slow decode, max-num-seqs, EP, MTP

**Date:** 2026-07-24  
**Source:** `gh search` / `gh issue view` on `vllm-project/vllm`  
**Scope:** Open (and notable closed) issues touching DeepSeek MoE slow decode, `max-num-seqs` regressions/mismatches, expert parallel, and MTP. Evidence cards only.

---

## Top five (quick index)

| # | State | One-line takeaway |
|---|-------|-------------------|
| [41306](https://github.com/vllm-project/vllm/issues/41306) | open | v0.20 MoE-only latency/throughput regression vs v0.19; DeepSeek-V2 TPOT/TTFT worse, dense models fine. |
| [45257](https://github.com/vllm-project/vllm/issues/45257) | open | Under async scheduling, `max-num-seqs` caps `len(running)` not scheduled batch size, so decode/prefill underfills. |
| [48066](https://github.com/vllm-project/vllm/issues/48066) | open | Marlin MoE `block_size_m` heuristic over-tiles under EP; decode TPOT can lose ~9–30%. |
| [43456](https://github.com/vllm-project/vllm/issues/43456) | open | DeepSeek-V4 MTP loader silently skips top-level `head`/`embed` weights → 0% draft acceptance, no error. |
| [47528](https://github.com/vllm-project/vllm/issues/47528) | open | DeepSeek-V4-Pro FP4 MoE garbles under TP; same model correct with DP+EP. |

---

## Issue cards

### Card 1 — #41306 — MoE slow decode / version regression

- **Title:** [Bug]: v0.20 latency and throughput regression on MoE models
- **URL:** https://github.com/vllm-project/vllm/issues/41306
- **State:** open · **Labels:** bug · **Updated:** 2026-05-19
- **Topic tags:** DeepSeek MoE, slow decode, regression
- **Summary:** Reporter benchmarks v0.19.0 vs v0.20.0 on 8×H200. Dense Llama models are flat; MoE regresses. Mixtral-8x7B: TPOT +21%, TTFT +59%, throughput −19%. DeepSeek-V2-Chat (MoE+MLA): TPOT +4.7%, TTFT +23% (table truncated in issue body). Concurrency=1 sonnet-style load (in=4096, out=512).
- **Why it matters:** Direct “MoE decode got slower after a version bump” signal; DeepSeek called out explicitly.
- **Relevance:** HIGH

### Card 2 — #45257 — max-num-seqs under-counts scheduled batch

- **Title:** [Bug]: max-num-seqs is not accurate when using async scheduling (especially affects P-D disaggregation prefills)
- **URL:** https://github.com/vllm-project/vllm/issues/45257
- **State:** open · **Labels:** bug · **Updated:** 2026-06-11
- **Topic tags:** max-num-seqs, async scheduling, P/D
- **Summary:** Documented meaning of `max_num_seqs` (“max sequences processed in a single iteration”) diverges from behavior under async scheduling. Finished/limited seqs stay in `self.running`; scheduler stops admitting when `len(running) == max_num_seqs`, so actual scheduled batch is almost always below the knob. Worst on P-D prefill nodes with `max_tokens=1`.
- **Why it matters:** Explains “I raised max-num-seqs but decode/prefill batch didn’t grow” without blaming MoE kernels.
- **Relevance:** HIGH (mechanism for concurrency regressions / underfill)

### Card 3 — #48066 — Expert-parallel decode TPOT tax (Marlin)

- **Title:** [Performance]: Marlin MoE block_size_m heuristic over-selects a large M-tile for expert-parallel decode (up to ~30% TPOT on gpt-oss)
- **URL:** https://github.com/vllm-project/vllm/issues/48066
- **State:** open · **Labels:** (none) · **Updated:** 2026-07-09
- **Topic tags:** expert parallel, MoE decode, performance
- **Summary:** `fused_marlin_moe` picks `block_size_m` from `M * topk / E` where `E` is **local** experts. Under EP, `E` shrinks → heuristic saturates at large tiles (e.g. 64) → high register/shared-memory use, low occupancy. Forcing smaller tiles recovers **9–30% decode TPOT** on gpt-oss-120b (DP8). Marlin path lacks device-aware autotune (unlike Triton fused-MoE).
- **Why it matters:** Concrete EP×decode slowdown mechanism; applies whenever serving MoE with `--enable-expert-parallel`.
- **Relevance:** HIGH

### Card 4 — #43456 — DeepSeek-V4 MTP silent 0% acceptance

- **Title:** [deepseek_v4] DeepSeekV4MTP loader silently skips top-level head.weight + embed.weight → 0% MTP draft acceptance with no error
- **URL:** https://github.com/vllm-project/vllm/issues/43456
- **State:** open · **Labels:** (none) · **Updated:** 2026-05-23
- **Topic tags:** MTP, DeepSeek-V4
- **Summary:** `DeepSeekV4MTP.load_weights` only accepts keys with a speculative-layer index. Top-level checkpoint keys `head.weight` / `embed.weight` hit `continue` → MTP head/embed stay random → drafts always rejected → **0% acceptance with no load error**. Spec decode looks “enabled” but is useless.
- **Why it matters:** Failure mode that looks like “MTP is slow / useless” when it is actually a silent load bug.
- **Relevance:** HIGH

### Card 5 — #47528 — TP vs DP+EP correctness on DeepSeek-V4-Pro

- **Title:** [Bug]: DeepSeek-V4-Pro … produces garbled / degenerate output under tensor parallelism (TP), while data parallelism + expert parallelism (DP+EP) works correctly
- **URL:** https://github.com/vllm-project/vllm/issues/47528
- **State:** open · **Labels:** bug · **Updated:** 2026-07-03
- **Topic tags:** expert parallel, DeepSeek-V4-Pro, FP4 MoE
- **Summary:** `DeepseekV4ForCausalLM` with `scale_fmt=ue8m0` / FP4 MoE: TP path yields garbled/degenerate tokens; same weights under DP+EP produce correct output. Reinforces recipe bias toward `--enable-expert-parallel` for V4-Pro.
- **Why it matters:** EP is not only a throughput knob; for V4-Pro FP4 it is a correctness path.
- **Relevance:** HIGH

---

## Runner-up cards (same forage)

### #30832 — DeepSeek-V3.2 decode ~30 tok/s on 8×H20

- **URL:** https://github.com/vllm-project/vllm/issues/30832
- **State:** open · **Labels:** performance, stale · **Updated:** 2026-07-22
- **Summary:** User reports ~30 decode tok/s/req on DeepSeek-V3.2 TP=8, below recipe-doc expectations; asks for config/root-cause.
- **Relevance:** MED (classic “DeepSeek MoE decode feels slow” usage/performance thread)

### #39981 — Batch queue size ≠ max-num-seqs

- **URL:** https://github.com/vllm-project/vllm/issues/39981
- **State:** open · **Labels:** bug · **Updated:** 2026-07-15
- **Summary:** On GPT-OSS-120B / v0.11.2, observed batch queue size diverges from documented `max-num-seqs` equality; related concurrency-knob confusion.
- **Relevance:** MED (max-num-seqs semantics)

### #43457 — MTP `num_speculative_tokens` capped at 1 on Hopper (DeepGEMM)

- **URL:** https://github.com/vllm-project/vllm/issues/43457
- **State:** open · **Updated:** 2026-06-16
- **Summary:** `paged_mqa_logits` asserts `next_n == 1 or 2`; vLLM passes `num_speculative_tokens+1`, so k=2 (`next_n=3`) crashes on Hopper. Effective MTP depth capped at 1 for that kernel path.
- **Relevance:** HIGH for MTP k>1 plans

### #49369 — DSpark slower than no-spec on DeepSeek-V4-Flash (B300)

- **URL:** https://github.com/vllm-project/vllm/issues/49369
- **State:** open · **Updated:** 2026-07-21
- **Summary:** Single B300, `max_num_seqs=256`, flashinfer_trtllm MoE: DSpark roughly halves aggregate throughput vs no-spec despite healthy acceptance. Notes deep_gemm_mega_moe requires EP (errors on 1 GPU).
- **Relevance:** MED-HIGH (spec decode can hurt saturated MoE batches)

### #20323 — RFC: Elastic Expert Parallelism

- **URL:** https://github.com/vllm-project/vllm/issues/20323
- **State:** open · **Labels:** RFC, keep-open · **Updated:** 2026-06-09
- **Summary:** EP today is static; RFC proposes scale-up/down EP for DeepSeek-V3/R1-class MoE without full restart.
- **Relevance:** MED (roadmap, not an immediate bug)

### #47273 — DeepSeek-V4 MTP IndexError at TP=16 (closed)

- **URL:** https://github.com/vllm-project/vllm/issues/47273
- **State:** closed · **Closed:** 2026-07-24
- **Summary:** `load_weights` IndexError in DeepSeek-V4 MTP module under TP=16 multi-node H100.
- **Relevance:** MED (recent MTP×TP crash class; verify whether your pin includes the fix)

### #41530 — TP worker hang with DeepSeek-V4-Pro + MTP

- **URL:** https://github.com/vllm-project/vllm/issues/41530
- **State:** open · **Labels:** bug · **Updated:** 2026-07-19
- **Summary:** TP=8 + MTP: workers hang ~5 min → `sample_tokens` RPC timeout → `EngineDeadError`.
- **Relevance:** MED-HIGH (stability under MTP at scale)

---

## Coverage map

| Theme | Primary card | Also see |
|-------|--------------|----------|
| DeepSeek MoE slow decode | #41306 | #30832, #49369, #48066 |
| max-num-seqs regression / mismatch | #45257 | #39981 |
| Expert parallel | #48066, #47528 | #20323 |
| MTP | #43456 | #43457, #41530, #47273 (closed) |

---

## Search notes (repro)

```text
gh search issues --repo vllm-project/vllm "DeepSeek" "slow" "decode"
gh search issues --repo vllm-project/vllm "max-num-seqs"
gh search issues --repo vllm-project/vllm "expert parallel" DeepSeek
gh search issues --repo vllm-project/vllm DeepSeek MTP
```
