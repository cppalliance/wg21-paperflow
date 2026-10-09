# 00 - Evidence Baseline: tapetum-llm fleet-run throughput regression (692 s -> 2886 s)

Target: `packages/whisker/src/whisker/tapetum_llm/` (self-target, throughput angle).
Comparison codebase: same package at commit `58a978c` (2026-07-09, the benchmarked
state) vs HEAD. Date: 2026-07-23.

## The question

A bare full fleet run (`uv run --package whisker whisker-tapetum-llm`, no flags,
default client concurrency 32) over 381 papers took **2886.4 s (48.1 min)** on
2026-07-23. The committed benchmark from 2026-07-09
(`packages/whisker/research/llm-batching/20-sweep-results.md`) records
**692.3 s (11.5 min)** for the same 381 papers at the same client c=32.
That is a **4.2x wall-time regression**. Why, and what (if anything) should change?

The paper-level batching strategy is NOT gone. Evidence below. The suspicion to
test: the per-paper LLM call count and per-call cost exploded between 07-09 and
today, through two code events (source-aware lane 07-17, all-pages/contract work
07-22), and 48 min might even be the *correct* price for what the lane now does.
Personas must confirm or kill that story with code and numbers, and find which
part of the cost buys nothing.

## Hard numbers from the 2026-07-23 run (tonight)

- Command: bare full run, no PIDs, defaults. Client concurrency 32
  (`cli.py:124` `_DEFAULT_CONCURRENCY = 32`).
- Footer: `381 total: 381 evaluated, 11 pass, 321 review, 45 fail, 4 error
  (54 model retries) in 2883.0s`.
- Merged fusion: `23 pass, 344 review, 14 fail (LLM coverage 377/381)`,
  321 `source_aware_review_cap`, 202 cosmetic fast-track.
- Raw log: `_scratch/whisker-fullrun/llm-stderr.txt` (361 lines): 181 explicit
  `pdf-judge verdict` lines, 16 `escalation` lines, 111 `unit section:N has no
  source packet` warnings, 4 ERROR lines (2x visible `IdealVerificationError`,
  P4182R0, P4228R0).
- Every logged paper shows `all_pages=False` (fleet default is routed mode;
  `--all-pages` is per-PID review tooling only).
- Throughput curve (sidecar `LastWriteTime`, 381 files, first 01:08:27, last
  01:54:48): 10-min buckets 7 / 57 / 78 / 102 / 83 / 54. Steady ~8 papers/min
  the whole run. No stall, no warm-up cliff, no long tail. Uniform per-paper
  cost, not a scheduling pathology.
- Effective rate: 2883 s / 381 = **7.6 s/paper**. 07-09 benchmark: 692.3 s / 381
  = **1.8 s/paper**.
- All 381 were evaluated cold: the 07-22 work bumped `_LANE_VERSION` to 9
  (`cli.py`), invalidating every stored fingerprint, so incremental skip (on by
  default for the bare run) skipped nothing. This was a full cold re-adjudication.

## Committed prior benchmarks (packages/whisker/research/llm-batching/)

From `20-sweep-results.md`:

- 204 papers in 556.3 s (9.3 min) at c=16 = 2.7 s/paper, 0 errors, "3.9x faster
  than the 2159.8 s / 36 min c=3 baseline".
- **381 papers in 692.3 s at c=32** vs 722.4 s at c=16 (-4.2%).
- Variance already on record: a later 381-paper c=32 run took 1090.2 s, a warm
  rerun 1465.2 s. So the 07-09 numbers themselves wobble ~2x; even the worst
  recorded prior run (1465 s) is still ~2x faster than tonight.
- c=381 experiment: negative result, 257/381 peer-closed errors. Client c>32
  breaks (RunPod proxy idle kill ~100s, `research/concurrency-381/`).
- `17-latency-decomposer.md`: per-call wall is decode-dominated (~25-28 s of
  ~30 s mean at that time); prefill ~7% at P50; sidecars record no timings.
- The 36-min c=3 baseline was **213 LLM calls total** (200 tier-1 + 13 tier-2)
  for 204 papers: i.e. the 07-09-era cascade was ~1 call per paper.

## Code timeline (git, load-bearing)

- `58a978c` 2026-07-09: "whisker: menu, fusion, readback, VLM lane, corpus
  tools + research corpus". State that the 692 s benchmark measured.
  `pdf_judge.py` exists but `unit_judge.py` does NOT.
- `c59139c` 2026-07-17: "whisker: add fail-closed source-aware golden QA".
  Adds `unit_judge.py` (scoped per-unit LLM checks), two-sided evidence
  verification, risk routing. This multiplies per-paper calls: metadata/outline
  check + up to `MAX_UNIT_CHECKS` routed unit checks + escalation + evidence
  verification calls.
- Uncommitted 07-22 work (this workspace): `--all-pages` feature. Fleet-relevant
  side effects to audit: full `CONVERSION_CONTRACT` moved into
  `UNIT_CHECK_SYSTEM_PROMPT` (`unit_judge.py`), larger system prompt for every
  unit check; `_LANE_VERSION` bumped to 9 (cold rerun); PDF sidecar schema v8.

## Concurrency plumbing (verified in code tonight)

- Paper-level: `cli.py:1090` `sem = asyncio.Semaphore(concurrency)` with
  default 32, `cli.py:1363` `asyncio.gather(...)`. Client c=32 deliberately
  overfills the pod's server-side `--max-num-seqs 16` (documented
  `tapetum_llm.md:29`; raising server slots to 16->32 regressed wall ~60%,
  `research/slots-32-regression/SYNTHESIS.md`).
- The historical "16 papers sat idle" bug is FIXED: `judge_task.py:10-22` exists
  precisely because `pipeline.run_task` holds a global `asyncio.Semaphore(1)`;
  the judge lane bypasses it (per-package mechanism sanctioned by D11). The
  batching strategy the operator remembers is alive.
- Inside one paper the cascade is SERIAL by design (`tapetum_llm.md:27`
  "concurrency: 1" for the in-paper cascade; `pdf_judge.py:649` comment).
  So per-paper wall = sum of that paper's serial LLM calls, and fleet wall ~=
  (total calls x per-call latency) / effective slots.
- `vision_task.py:55-59`: `_VISION_TASK_CONCURRENCY = 1`, a module-level
  GLOBAL semaphore. If the VLM/vision path fired during the fleet run, it is a
  global serialization point across all 32 papers. Personas: check whether it
  fired tonight and how often.
- Pod: `alliance-pod` (deepseek-v4-pro on RunPod, vllm_thinking backend),
  healthy at run start (health check 200). 54 model retries and 4 errors during
  the run indicate intermittent stress or schema retries.

## Back-of-envelope to attack

If the 07-17 lane does ~1 (metadata) + ~3-5 (units) + ~0.1 (escalation) + ~1-3
(evidence verification) calls per paper, total calls are roughly 1500-3500 vs
~400 in the 07-09 benchmark, i.e. a 4-9x call-volume increase, matching the
observed 4.2x wall regression WITHOUT any lost concurrency. Personas must
replace this estimate with exact counts from code paths and tonight's log/
sidecars, and price the 07-22 prompt growth separately.

## What each report must cite

Every claim: `file:line` in this workspace, a number from this baseline, or a
URL from `05-web.md`. Arguing from vibes is rejected in synthesis.

## Required persona report template

# NN - <Persona name>

**Verdict:** usable | usable-with-conditions | garbage   (+ 1 sentence why)
**Confidence:** high | medium | low

## Findings
- [CRITICAL|HIGH|MED|LOW] <claim>. Evidence: <file:line OR runtime number from 00>.
  Impact: <why it makes the target more/less trustworthy or adoptable>.
  (repeat; 3-8 findings, ranked)

## False-pass hypothesis
<one concrete case the target/our-equivalent would wrongly accept, or "none found">

## False-fail hypothesis
<one concrete case it would wrongly reject, or "none found">

## What would change my mind
<the single piece of evidence that would flip my verdict>
