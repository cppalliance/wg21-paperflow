# 60 - Continuous-batching trap (decode-bound MoE)

**Verdict:** usable — on decode-bound MoE, continuous batching stops helping when the per-step expert union grows so fast that TPOT rises faster than `1/B`; our 16→32 slot A/B is that trap (+57% fleet wall for everyone).
**Confidence:** high

## Angle (why this file)

Prior cold-run notes cover wall arithmetic (`11`), in-paper parallel risk (`13`), and DeepSeek/vLLM recipe pins (`05a`). This note isolates the **continuous-batching + MoE decode** interaction: when adding concurrent requests slows *every* in-flight sequence more than the parallelism gain, so fleet wall gets worse.

## Findings

- [CRITICAL] **Trap condition:** continuous batching helps only while `B × (1 / TPOT(B))` rises with concurrency `B`. On dense decode, weights load once per step so TPOT rises slowly; on MoE decode, step cost tracks `|⋃ experts activated by the batch|`, which grows with `B`, so TPOT can jump enough that *all* requests get slower and total fleet wall rises. Evidence: OEA (https://arxiv.org/pdf/2511.02237) — decode latency "effectively linear in the number of unique activated experts"; XShare / vLLM RFC #35550 (https://arxiv.org/abs/2602.07265, https://github.com/vllm-project/vllm/issues/35550) — DeepSeek-R1 (256 experts, k=8): batch 32 activates ~163/256 experts, batch 64 ~243/256. Impact: raising `--max-num-seqs` is not a free throughput knob on alliance-pod MoE; it can make the whole fleet slower.

- [CRITICAL] **Measured trap: 16→32 simultaneous decodes = +57% wall.** Evidence (`research/slots-32-regression/SYNTHESIS.md`): identical 381-paper corpus, client c=32 — server `--max-num-seqs 16` → **692.3 s**; `--max-num-seqs 32` → **1090.2 s** (ratio **1.574×**, +57%). Warm rerun at 32 slots was worse still (**1465.2 s**). Impact: doubling continuous-batch depth cut effective throughput; expected "more slots → shorter wall" failed.

- [HIGH] **Everyone slows, not just the marginal request — isolation proves it.** Evidence: same SYNTHESIS matrix — server 32 + client **c=16** → **763.7 s** (near the 16-slot band), while server 32 + client c=32 → 1090.2 s. "Only the number of SIMULTANEOUS DECODES matters." Impact: continuous batching is the coupling mechanism: every decode step pays the full expert-union tax; overfilling the GPU batch makes *each* stream's tokens slower.

- [HIGH] **Mechanism is expert-union HBM traffic, not KV cliff.** Evidence: `slots-32-regression/11-moe-batch-scaling.md` (ELDR + Perplexity EP8 notes); `10-kv-preemption.md` ruled out preemption (`num_preemptions_total 0`, KV peak ~15 GiB vs 100+ GiB headroom). Dense-model analogue (vLLM #17598): `max-num-seqs` 16→32 only +14% TPOT at fixed request rate — MoE amplification explains why we saw +57%, not +14%. Impact: operators who check "KV usage <40%" and then raise slots will walk into this trap.

- [MED] **Literature names the same knee; mitigations are not shipped for our stack.** Evidence: "Balance Activated Experts, Not Tokens" (https://arxiv.org/html/2512.09277v1) — balancing tokens can *increase* decode expert union and hurt TPOT; XShare claims +53% tok/s at concurrency 32 via decode-only expert pruning (vLLM #35550, closed/stale, not a production DeepSeek-V4-Pro lever today). Impact: until MoE-aware batch scheduling / expert-affinity lands on the pod, the operator control is **cap simultaneous decodes**, not raise them.

- [MED] **Arithmetic of "worse than linear":** naive 2× parallelism at constant per-request latency would cut wall ~2× (or hold wall if already slot-saturated). Observed wall **×1.57** at 2× slots means per-request decode cost rose enough to erase all parallelism gain *and* add 57% — superlinear relative to the "slots help" model, and worse than the dense +14% TPOT benchmark. Prefill interference (`13-prefill-interference.md`) contributes variance (1090 vs 1465) but cannot alone predict the 1.57× ratio without MoE decode slowdown.

## Operator rule of thumb

**On decode-bound MoE, raise continuous-batch concurrency only while measured TPOT grows slower than `1/B`; the first doubling that raises fleet wall (ours: 16→32 = +57%) is past the knee — keep server slots there and overfill the client queue instead.**

## False-pass hypothesis

Operator sees low KV %, raises `--max-num-seqs` to 32/64 for "throughput," fleet finishes slower, then blames client code or "cold start" while every paper's unit checks paid a higher TPOT under a wider expert union.

## False-fail hypothesis

none found (this is infra scheduling, not judge quality) — secondary risk: slower decode can trip client/proxy timeouts and mark units `failed` / fail-closed `review`, which looks like a lane quality regression (`tapetum-llm-throughput/13-determinism-guardian.md`).

## What would change my mind

A full-corpus A/B at `--max-num-seqs 32` with MoE-aware scheduling (expert-affinity batching or production XShare-style decode pruning) that restores wall ≤692 s at equal quality — then the trap is a *current-stack* limit, not a structural MoE law for this pod.

## Sources

| Source | Claim used |
|--------|------------|
| `research/slots-32-regression/SYNTHESIS.md` | 692.3 → 1090.2 s (+57%); c=16@32slots = 763.7 s isolation |
| `research/slots-32-regression/11-moe-batch-scaling.md` | expert-union / EP8 mechanism |
| `research/slots-32-regression/10-kv-preemption.md` | KV/preemption ruled out |
| `research/cold-run-10min/00-baseline.md` | 32 slots forbidden; decode-bound judge workload |
| XShare arXiv 2602.07265 / vLLM #35550 | batch 32 → ~163/256 experts on DeepSeek-R1 |
| OEA arXiv 2511.02237 | decode latency ∝ unique activated experts |
| arXiv 2512.09277 | memory-bound MoE: balance experts, not tokens |
| vLLM #17598 | dense +14% TPOT at 16→32 (contrast) |
