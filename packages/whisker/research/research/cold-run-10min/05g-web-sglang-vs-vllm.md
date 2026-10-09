# 05g - Web forage: SGLang vs vLLM (DeepSeek MoE, radix, cache-aware)

**Date:** 2026-07-24
**Question:** Would migrating `alliance-pod` from vLLM → SGLang (RadixAttention +
cache-aware / LPM scheduling) help a **decode-bound structured-output judge**
fleet toward ≤10 min cold wall?
**Prior reject (must not rediscover):**
`research/tapetum-llm-speedup/113-sglang-anti-steelman.md` (garbage, high confidence)
+ `112-sglang-benchmark-evidence.md`. Flip gate there: same H200, guard-tag fixed,
sglang LPM beats vLLM APC by **>15% aggregate prefill wall** AND persona-47
`flip_AB ≤ flip_AA + margin`.

**Delta verdict:** **stay** — no post-2026-07-23 evidence flips the prior reject.
Radix / cache-aware scheduling remain a **prefill** lever on a fleet that is
**~13× decode-heavy** (5.91 s decode vs 0.46 s prefill mean). Blog "migrate for
structured output" claims assume server-side guided decoding; our judge path is
**schema-in-prompt** (`VllmThinkingBackend`), so that win does not apply.
**Revisit:** `revisit-in-6-months` only if the open Rust/gRPC + free-threaded
stack ships *and* we switch the client to real guided decoding (separate A/B).

---

## Finding cards (new / re-checked 2026-07-24)

### Card A — Decode-bound arithmetic still kills the radix migration case
**Sources:** cold-run `00-baseline.md` (decode 5.91 vs prefill 0.46); vLLM APC docs
https://docs.vllm.ai/en/latest/features/automatic_prefix_caching/
**Weight:** CRITICAL
**Claim:** Official vLLM APC docs state APC **does not reduce decode time**; it
only skips shared-prefix prefill. Our measured phase split is decode-dominated.
SGLang RadixAttention + LPM scheduling optimize the same phase (prefix match /
prefill reorder). Even a perfect engine-side prefix win is bounded by the prior
counterfactual of **~0–120 s** residual over tuned vLLM APC after client reorder
(`113` HIGH finding), against **~2400 s** still needed for ≤600 s wall.
**Does it flip prior reject?** No. Confirms reject.

### Card B — Marketing 2026 blogs recycle the same prefix-heavy story (already weighed)
**Sources:**
- Particula (2026-03-26) https://particula.tech/blog/sglang-vs-vllm-inference-engine-comparison
  (+29% H100 baseline; up to 6.4× prefix-heavy; gap collapses on unique prompts;
  "default SGLang for DeepSeek"; structured-output "3×" via compressed FSM)
- TURION / CodeBrew / YottaLabs (2026 comparison posts) — same Radix vs Paged
  framing; endorse SGLang for RAG / multi-turn / agents
**Weight:** MED (architecture true; fleet mapping weak)
**Claim:** No new DeepSeek-V4-Pro @ `--max-num-seqs 16` / H200 / schema-in-prompt
judge bake-off. Particula itself cites RunPod unique-prompt case where **vLLM
beat SGLang** (60 vs 52.7 tok/s) and Spheron: "RadixAttention's benefit disappears
for unique-prompt workloads." Our serial per-paper 6-call chain + shared-pod
traffic is closer to mixed/unique than their RAG multi-user ideal.
**Does it flip prior reject?** No. Same Q4 evidence class as `05-web.md` Q4.

### Card C — DSV4 HiCache / UnifiedRadix correctness churn is still active (post-reject)
**Sources:**
- SGLang v0.5.12 release notes (HiCache + UnifiedRadix for DSV4; cascade/tombstone/
  partial-match stability fixes) https://github.com/sgl-project/sglang/releases/tag/v0.5.12
- [#25889](https://github.com/sgl-project/sglang/pull/25889) stale `cached_loc` after
  SWA mapping rebuild → OOB / wrong outputs (May 2026)
- [#29106](https://github.com/sgl-project/sglang/pull/29106) DSV4 PP HiCache SWA
  allocation / layer mapping (merged ~2026-06-27); discussion notes KL instability
  on approximate C4 top-k unless `SGLANG_TOPK_TRANSFORM_512_TORCH=1`
- [#24691](https://github.com/sgl-project/sglang/pull/24691) HiCache for DeepSeek_V4
  under UnifiedTree (tester: ~20% throughput drop with L2 HiCache on 16k prefill)
**Weight:** CRITICAL (quality-stability)
**Claim:** Since the 2026-07-23 anti-steelman, upstream is still patching DSV4
hybrid-cache correctness. A judge fleet that migrates for wall time inherits
stale-hit / OOB classes that can shrink defect groups while looking "faster."
vLLM side has its own DSV4 APC history ([#42948](https://github.com/vllm-project/vllm/issues/42948)
0% hit bug; fix path [#43447](https://github.com/vllm-project/vllm/pull/43447)
retention → 74.3% hits / 4.5× tok/s on **our** concurrency) — already wired and
recipe-backed https://recipes.vllm.ai/deepseek-ai/DeepSeek-V4-Pro
**Does it flip prior reject?** No. Strengthens reject on quality risk.

### Card D — Structured-output "SGLang wins" does not map to our client path
**Sources:**
- SqueezeBits (2025-09-16) https://blog.squeezebits.com/guided-decoding-performance-vllm-sglang
  (SGLang overlaps per-step grammar mask with GPU forward; vLLM 0.10 shows
  guided-decoding throughput drop at batch ≥8)
- `packages/pipeline/src/pipeline/model_backends.py` `VllmThinkingBackend`:
  schema-in-prompt + raw JSON parse/retry; **not** `guided_json` / XGrammar
  (workaround for tool-calling broken #28219; MODELS.md)
- Red Hat / vLLM V1 structured-output notes: V1 much faster than V0; still
  correctness churn on concurrent bitmasking (PRs #19565, #22896) — not a
  measured decode win for DeepSeek-V4-Pro judges
**Weight:** HIGH
**Claim:** Blogs that say "migrate for JSON schema fleets" assume **server-side
constrained decoding**. Our advisory lane ships the schema in the system prompt
and validates client-side. Engine swap alone cannot claim the SqueezeBits /
Particula structured-output delta. Activating guided decoding would be a
**client+server** change (schema determinism, thinking+constraints interaction,
persona-47 revalidation) — not a pod flag flip.
**Does it flip prior reject?** No for current stack. Conditional reopen only if
we deliberately move judges onto overlapped guided decoding *and* measure decode
tok/s on DSV4-Pro @ 16 slots.

### Card E — GIL / Python router bottleneck not retired; mitigations still experimental/RFC
**Sources:**
- [#21061](https://github.com/sgl-project/sglang/issues/21061) (closed inactive):
  at ~150 concurrent, SGLang throughput **<50% of vLLM**, host CPU ~127% (GIL);
  maintainer points at experimental C++ radix (`SGLANG_EXPERIMENTAL_HIRADIX_CACHE=1`)
- [#22558](https://github.com/sgl-project/sglang/issues/22558) RFC native Rust gRPC
  (GIL for parse/tokenize/serialize)
- [#22889](https://github.com/sgl-project/sglang/issues/22889) free-threaded 3.14t
  support — **open** as of mid-2026
**Weight:** HIGH (ops / burst)
**Claim:** No shipped default that retires the Python orchestration bottleneck
cited in `113`. Our c=32 × 16 slots is milder than the 150-way flood, but
shared-pod bursts still hit the same layer. Migration cost (shared RunPod cutover
+ ~100–150 min persona-47 gate) unchanged.
**Does it flip prior reject?** No.

### Card F — Cache-aware scheduling buys near-zero on serial in-paper chains
**Sources:** prior `106-sglang-radixattention.md` / `113` (LPM default-OFF;
call N+1 only after N completes); cold-run baseline (per-paper serial 6-call)
**Weight:** HIGH
**Claim:** LPM / radix-priority scheduling helps when many requests with shared
prefixes are **concurrently queueable**. Tapetum submits unit checks serially
inside a paper; cross-paper interleave dilutes document locality. Engine-side
scheduler cannot invent concurrency the client does not offer. Prefill savings
remain client-layout-bound (HMAC guard tag + document-before-query reorder),
which vLLM APC already captures once layout is fixed.
**Does it flip prior reject?** No.

---

## Steelman (best case for migrate)

1. Isolate a second H200 pod on SGLang (not shared `alliance-pod` cutover).
2. Ship client guided decoding (XGrammar/LLGuidance) with overlapped masks.
3. Fix guard-tag + prompt order so prefixes actually hit.
4. Measure 20-paper × 6-call decode wall + persona-47 on 381.

Even then, expected wall from engine alone remains a **prefill-sized** or
**guided-overhead-sized** delta, not the metadata-fail / call-count levers that
dominate the settled ranking in `00-baseline.md`.

## What would flip to migrate

All of:
1. Live bake-off: SGLang decode+guided tok/s beats vLLM by **>15% fleet wall**
   on DeepSeek-V4-Pro @ 16 slots with **identical** schemas and prompts.
2. persona-47 `flip_AB ≤ flip_AA + margin`.
3. DSV4 HiCache/SWA release notes quiet for ≥2 minor versions (no OOB/stale-loc
   class).
4. Prefer isolated second pod; shared-pod cutover still needs an outage budget.

Absent (1)–(3): stay.

---

## Verdict

| Decision | Choice |
|----------|--------|
| **migrate / stay / revisit-in-N-months** | **stay** |
| Secondary watch | **revisit-in-6-months** (Rust gRPC / free-threaded default + optional guided-decoding client path) |
| Confidence | **high** |

**One-liner:** New 2026 web evidence reconfirms SGLang's radix/cache-aware edge is
real for **prefix-heavy prefill** and (separately) for **server guided decoding**;
our fleet is **decode-bound** and **schema-in-prompt**, so migration does not
move the 48→10 min needle and still fails the prior quality/ops gate.
