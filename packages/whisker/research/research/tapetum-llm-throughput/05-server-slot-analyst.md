# 05 - Server-Slot-Analyst

**Verdict:** usable — tonight's 2886 s wall is consistent with a healthy 16-slot pod executing the post-07-17 call cascade at historical ~30 s/call decode; blaming pod degradation or lost concurrency is the wrong failure class.
**Confidence:** high

## Findings

- [CRITICAL] **Slot-limited fleet wall follows `wall ≈ total_calls × per_call_latency / 16`.** Evidence: server `--max-num-seqs 16` (`tapetum_llm.md:29`, `00-baseline.md:84-85`); client c=32 overfills by design (`cli.py:124`, `00-baseline.md:81-85`); prior mean decode ~30.4 s/call back-solved from 213 calls at c=3 in 2159.8 s (`17-latency-decomposer.md:10-11`, `00-baseline.md:59-62`). Impact: any diagnosis must factor call volume before inferring pod sickness.

- [CRITICAL] **Back-solve from tonight's run points to ~1540 total calls (~4.0/paper), not ~370 (~1.0/paper).** Evidence: `2883 s × 16 / 30 s ≈ 1538 calls` (`00-baseline.md:28,41`); ratio vs 07-09: `2883 / 692.3 = 4.17×`, matching `1540 / 370 ≈ 4.16×` call volume without any latency drift. Impact: the 4.2× regression is priced by cascade growth, not slot loss.

- [CRITICAL] **07-09 benchmark validates the model on the same pod config.** Evidence: `381 × 1 call × 30 s / 16 ≈ 714 s` vs observed **692.3 s** (`00-baseline.md:13,51-53`); 204-paper c=3 baseline **213 calls** for ~1 call/paper (`00-baseline.md:61-62`). At `58a978c`, `unit_judge.py` did not exist (`00-baseline.md:66-68`); PDF path was effectively monolith-only (+ rare page escalations). Impact: historical floor under old cascade is ~700 s for 381 papers on one healthy 16-slot pod.

- [HIGH] **Current cascade floor is 2 mandatory LLM calls per PDF paper before any routing.** Evidence: monolith `run_judge_task` (`pdf_judge.py:650`) then metadata `run_metadata_outline_check` (`pdf_judge.py:677`, `unit_judge.py:231-267`); optional +0–5 page escalations (`constants.py:191`, `pdf_judge.py:753`) and +0–5 unit checks when `route_pdf_units` emits signals (`constants.py:223`, `unit_judge.py:355-410`). Minimum fleet calls: `381 × 2 = 762`. Impact: **absolute healthy-pod floor for current code is `762 × 30 / 16 ≈ 1429 s (~24 min)`**, even with zero unit/page calls; returning to 692 s requires call-count reduction, not infra tuning.

- [HIGH] **Tonight's observed wall matches K≈4 calls/paper at unchanged decode, not a degraded pod at K≈1.** Evidence: `381 × 4 × 30 / 16 ≈ 2858 s` vs **2883.0 s** footer (`00-baseline.md:28`); steady throughput ~8 papers/min with no tail stall (`00-baseline.md:37-40`) contradicts progressive pod degradation or queue pathology. 54 model retries add at most `≈54 × 30 / 16 ≈ 101 s` (~3.5%) if each retry is a full decode (`00-baseline.md:28`). Impact: latency-only hypotheses need implausible per-call growth (≥60 s at K=2, ≥121 s at K=1) to explain 2883 s alone.

- [MED] **MoE saturation widens per-call latency under load but does not explain a 4× wall jump by itself.** Evidence: continuous batching TPOT widens under 16 concurrent decodes (`17-latency-decomposer.md:14`, `05a-web-concurrency-knee` cited there); raising server slots 16→32 regressed wall ~60% on identical client code (`research/slots-32-regression/SYNTHESIS.md:8-14`, `00-baseline.md:84-85`). Uniform bucket rates 7/57/78/102/83/54 papers per 10 min (`00-baseline.md:37-38`) show stable effective throughput, not a saturation cliff worsening through the run. Impact: modest latency inflation (30→35–40 s) may coexist with call growth; it is a secondary term, not the primary driver.

- [MED] **07-22 prompt growth (full `CONVERSION_CONTRACT` in `UNIT_CHECK_SYSTEM_PROMPT`) is a latency lever, not a slot lever.** Evidence: `00-baseline.md:74-77`; prefill is ~7% of ~30 s budget at P50 (`17-latency-decomposer.md:12-13`). Even a 2× prefill bump on unit checks saves only ~1–2 s/call on typical papers. Impact: explains single-digit percent drift at most; cannot substitute for ~4× call volume.

- [LOW] **Second-pod sharding buys ~2× wall when a twin endpoint is live; it is blocked on infra today.** Evidence: `--service` per-process split (`18-load-splitter.md:10-14`, `cli.py:365,429-435`); twin `h200x8-deepseek-v4-pro` returned HTTP 404 at 2026-07-07 probe (`18-load-splitter.md:8`). Projected wall with two healthy clones at K≈4: `2883 / 2 ≈ 1440 s`. Impact: hardware parallelism helps; it does not shrink per-call work or restore the 692 s single-pod floor without also cutting calls.

## Scenario table (381 papers, 16 server slots)

Formula: `wall_s = 381 × K × L / 16`, where K = mean LLM calls/paper, L = mean per-call latency (s).

| K calls/paper | L (s/call) | Total calls | Wall (s) | Wall (min) | Consistency with evidence |
|---|---:|---:|---:|---:|---|
| 1.0 | 30 | 381 | 714 | 11.9 | **07-09 benchmark era** (`692.3 s`, `00-baseline.md:13`) |
| 1.0 | 121 | 381 | 2883 | 48.1 | Latency-only 4× — **rejected** (no mechanism; thinking off, `tapetum_llm.md:33`) |
| 2.0 | 30 | 762 | 1429 | 23.8 | **Current-code floor** (monolith + metadata only, every paper) |
| 2.0 | 61 | 762 | 2883 | 48.1 | Latency-only 2× at minimum call count — **unlikely** (would need decode collapse without retry storm; only 54 retries) |
| 3.0 | 30 | 1143 | 2143 | 35.7 | Low unit routing — possible lower bound if many papers skip unit checks |
| 3.0 | 40 | 1143 | 2858 | 47.6 | Latency inflation + moderate calls — **secondary scenario** |
| **4.0** | **30** | **1524** | **2858** | **47.6** | **Primary fit** — matches footer `2883.0 s` within 1% |
| 4.0 | 35 | 1524 | 3341 | 55.7 | Heavy saturation + high routing — overshoots observed wall |
| 5.0 | 30 | 1905 | 3572 | 59.5 | Upper routed bound (monolith + metadata + avg 3 optional) — bracket ceiling |
| 7.0 | 30 | 2667 | 5001 | 83.4 | Theoretical mid (2 + 5 page + 0 unit avg) — not observed |

**Evidence favors:** **K ≈ 4.0, L ≈ 30 s** on a healthy 16-slot pod. Supporting signals: mandatory +2 calls vs 07-09 (`00-baseline.md:66-73`); `321 source_aware_review_cap` on 381 papers (`00-baseline.md:29-30`) implying widespread unit routing; only **16** logged page escalations (`00-baseline.md:32`) so page calls are negligible (~0.04/paper); 111 `unit section:N has no source packet` warnings (`00-baseline.md:32-33`) consistent with many unit-check attempts.

## Realistic wall-time floors (current cascade, one `alliance-pod`)

| Regime | Assumption | Wall (381 papers) |
|---|---|---:|
| **Hard floor** | Every paper exactly 2 calls (no unit/page/ideal), L=30 s, no retries | **~1429 s (24 min)** |
| **Observed-equivalent** | K≈4, L≈30 s (matches tonight) | **~2860 s (48 min)** |
| **Upper routed bound** | K≈5–7 (heavy unit quota use + occasional pages), L=30 s | **~3570–5000 s** |
| **07-09 nostalgia target** | K≈1, L=30 s (pre-07-17 cascade) | **~714 s (12 min)** — **not reachable** on current code with one pod |

Raising server slots to 32 is **counterproductive** (proven ~60% regression, `research/slots-32-regression/SYNTHESIS.md:12-14`). Optimal proven pairing remains **server 16 + client 32** (`SYNTHESIS.md:53-54`).

## Second pod (sharding)

When a second live clone exists, disjoint PID lists or future `--shard-pods` round-robin (`18-load-splitter.md:10-14`) approximate:

| Config | Expected wall (K≈4, L≈30 s) |
|---|---:|
| 1 pod (tonight) | ~2880 s |
| 2 healthy pods, even split | **~1440 s (~24 min)** |
| 2 pods, hard floor K=2 | **~715 s (~12 min)** |

This buys calendar time only; total GPU-seconds consumed is unchanged. Twin endpoint `h200x8-deepseek-v4-pro` was **404** at last probe (`18-load-splitter.md:8`), so the 2× cut is not available without operator action.

## Throughput-bound vs latency-bound

| Regime | Condition | Tonight |
|---|---|---|
| **Throughput-bound** | `32 papers × ≥1 in-flight` keeps 16 decode slots full; wall set by `calls / 16` | **Yes** — steady ~8 papers/min (`00-baseline.md:37-39`) |
| **Latency-bound** | Slot vacancies (final wave) or per-call decode explosion | Minor tail only (`03-cascade-topology-auditor.md:16-17`); not the 2191 s delta vs 692 s |

In-paper serial cascade (`pdf_judge.py:646-890`) sums latencies per paper but, at fleet scale with c=32 overfilling 16 slots, **paper-level concurrency already saturates the pod** (`03-cascade-topology-auditor.md:14-15`). Serialization explains second-order effects, not the 4.2× regression.

## False-pass hypothesis

Declaring the pod healthy and ignoring call-count growth would falsely accept **~48 min** as the permanent fleet price while a code-side call budget (e.g. tighter unit routing, skipping redundant metadata on clean monolith passes) could restore a **~24 min** floor without any hardware change.

## False-fail hypothesis

Blaming RunPod degradation or "lost batching" would send operators to reboot pods or re-tune `--max-num-seqs` to 32, **both proven dead ends** (`research/slots-32-regression/SYNTHESIS.md`), while the actual driver is **~4× LLM call volume** from the 07-17 source-aware lane (`00-baseline.md:66-73`).

## What would change my mind

A per-paper LLM call census from tonight's 381 `*.whisker.tapetum.json` sidecars showing median **K ≤ 2.5** would force re-attribution to decode latency growth or hidden global serialization. At **K ≥ 3.5**, the slot model stands and infra is exonerated.
