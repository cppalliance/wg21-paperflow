# 54 - Chunked-Prefill Delta (decode-bound)

**Verdict:** garbage (as a cold-run ≤10 min lever) — under measured decode-bound means (**5.91 s decode vs 0.46 s prefill**), chunked prefill is already-on infrastructure, not a wall-clock dial; 94’s ~100–250 s MBT co-tune assumed prefill-step-dominated physics that lifetime metrics contradict.
**Confidence:** high

**Actionable for us?** **no**

## Prior claim (do not rediscover)

`research/tapetum-llm-speedup/94-vllm-chunked-prefill.md`:

- Chunked prefill is **default-on** in vLLM V1; “turn it on” = **~0 s**.
- Real recipe was co-tune **`max-num-batched-tokens` 8192→16384** + **`long-prefill-token-threshold=8192`**, estimated **~100–250 s** on the 3003 s cold run **if** long prefills burn ~17 s/call via multi-step chunks (5 steps @ MBT=8192 vs 3 @ 16384 on a 40k prompt).
- Quality risk of leaving defaults alone: **none**. Disabling chunked prefill: crash or monopoly-prefill regression.

## Decode-bound facts (settled)

| Metric | Value | Source |
|--------|------:|--------|
| Mean decode | **5.91 s** (65.6% of E2E) | P146 / cold-run `00-baseline.md` |
| Mean prefill | **0.46 s** (5.1% of E2E) | same |
| Mean queue | 2.38 s | P146 |
| Mean E2E | 9.01 s | P146 |
| APC token hit rate (lifetime) | 96.7% | P146 |

Prefill is a **rounding slice** of measured request time. Decode + queue dominate.

## Findings

- [CRITICAL] **Chunked prefill is not an on/off speed lever for us.** Evidence: 94 (`SchedulerConfig.enable_chunked_prefill` default True; V1 guide “enabled by default”); ops checklist already says **leave on** (`26-server-ops-checklist.md:54`). Impact: **0 s** toward 10 min from “enabling chunked prefill.” Quality risk: **none** if unchanged; **high operational** if disabled under MBT < max_model_len.

- [CRITICAL] **94’s ~100–250 s MBT savings do not survive the decode-bound mean.** Evidence: 94’s arithmetic used ~**17 s** prefill-bound steps/call (`94:8`, from uncached 40k counterfactual in 93); P146 cumulative mean prefill is **0.46 s**. Naive upper bound if *all* mean prefill vanished: `2284 × 0.46 / 16 ≈ 66 s` wall — and MBT only trims a **fraction** of scheduler rounds inside that prefill, not decode. Impact: chunked-prefill / MBT co-tune drops from “MODERATE fleet lever” to **≤ tens of seconds**, drowned by metadata short-circuit (~1059 s), dual-pod (~887 s), verdict-first (~155 s), MTP (decode-aligned). Quality risk: **none** for the math; risk is **mis-prioritizing ops** around a dead lever.

- [HIGH] **Decode-bound stack points elsewhere.** Evidence: SYNTHESIS rank #3 decode waste (`SYNTHESIS.md`); MTP + output-token shrink listed as decode-aligned in `96-vllm-metrics-probe.md` and `26-server-ops-checklist.md:156`. Impact: for ≤600 s planning, spend A/B budget on **MTP k=1**, **verdict-first / pass-path shrink**, and **call elimination** — not chunked-prefill experiments. Quality risk: **none** for skipping chunked-prefill work.

- [HIGH] **Cold-burst uncached prefill can still be long; that does not resurrect chunked prefill as a program item.** Evidence: P146: uncached tapetum counterfactual ~11–16 s prefill; prefill **>15 s** only **0.29%** of lifetime requests; TTFT **>20 s** on **5%**. Impact: MBT 16384 + threshold 8192 remain **safe ops hygiene** inside the prefix/APC envelope (`11-wall-arithmetic.md` prefix line; `26` launch delta) — apply when touching the pod launch command for APC/MTP, **do not open a dedicated chunked-prefill workstream**. Quality risk: **none**.

- [MED] **Decode-first scheduling already favors ITL under chunked prefill.** Evidence: 94 HIGH finding — running decodes drain before waiting prefills (`scheduler.py` running-then-waiting). Impact: our short-decode / long-prompt mix already gets the intended ITL bias; further chunked-prefill tuning fights the wrong phase. Quality risk: **none**.

## False-pass hypothesis

Ship “MBT 16384 + long-prefill threshold” as a claimed **~200 s** cold-run win from 94 without a run-interval `/metrics` scrape: operators attribute later wall drops from metadata short-circuit / dual-pod to chunked-prefill tuning and keep chasing prefill knobs while decode stays **~6 s**/call.

## False-fail hypothesis

Disable chunked prefill because “we’re decode-bound so prefill machinery is waste”: V1 requires it when MBT < max_model_len (393k), or monolithic long prefills starve co-slots — timeouts / coverage loss, not cleaner decode.

## What would change my mind

A cold 381-paper fleet with run-start `/metrics` deltas showing **interval** mean `request_prefill_time_seconds` **> 2×** mean `request_decode_time_seconds` (or p95 prefill ≫ p95 decode) **and** MBT=8192 vs 16384 A/B cutting wall by **≥100 s** — that would restore 94’s prefill-step lever as actionable.

## Executive answer (for parent agent)

| Question | Answer |
|----------|--------|
| Relevant when decode-bound (5.91 vs 0.46 s)? | **No** as a wall lever; yes only as “leave default-on, don’t disable.” |
| Actionable for us? | **no** |
| Still do anything? | If already editing pod launch for APC/MTP: keep MBT 16384 + threshold 8192 as free hygiene (`26`). Do **not** prioritize or A/B chunked prefill alone. |
| Prefer instead | Call elimination, dual-pod, verdict-first / output shrink, MTP. |
