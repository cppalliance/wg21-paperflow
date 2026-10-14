# Opus-A - Meta-verification of persona claims (measurement validity + lane logic + balance)

Verifier: orchestrator (Fable 5), re-ran the load-bearing aggregations independently
against the 381 sidecars and the code. Combined pass covering the suggested A
(measurement validity), B (lane-logic soundness), and E (steelman balance) angles;
the persona convergence was strong enough that separate passes would have re-verified
the same five numbers.

## Independently reproduced numbers (my own aggregation, 2026-07-23)

Script over `data/whisker/llm/*.whisker.tapetum.json` (381 files):

- unit checks total: **1510**, median **5.0/paper**, max 5 (= `MAX_UNIT_CHECKS` cap).
- metadata/outline checks: **377** (4 error papers have none).
- page escalations: **16** (matches log).
- monolith/tier-1: 381.
- Estimated total calls: **~2284**, i.e. **6.0 calls/paper**. Implied per-call
  latency at 16 server slots for 2883 s wall: **20.2 s**, consistent with a
  HEALTHY pod (07-09 measured ~30 s on bigger single calls).
- Empty unit checks (zero defect groups): **1057/1510 = 70%**.

## Claim dispositions

- 01 Call-Count-Accountant (2308 calls, ~6.1/paper): **CONFIRMED** (my count 2284;
  delta is retry/readback accounting). The 07-09 cascade was ~1 call/paper
  (`llm-batching/SYNTHESIS.md`: 213 calls for 204 papers).
- 04 Concurrency-Plumbing (no hidden Semaphore(1); c=32 live; vision did not fire):
  **CONFIRMED** structurally; `judge_task.py` bypass covers all pdf-lane calls,
  `run_judge_task` call sites verified.
- 05 Server-Slot-Analyst (2886 s consistent with healthy 16-slot pod):
  **CONFIRMED**, arithmetic reproduced above (20.2 s/call implied).
- 06 Regression-Bisector (Event A c59139c owns ~85%; Event B <5% + forced cold
  run; --all-pages did not fire): **CONFIRMED**; log shows 181x `all_pages=False`,
  0x True.
- 02/11 Prompt/Decode auditors (prompt bloat and schema growth are single-digit-%
  effects): **CONFIRMED** in direction; exact percentages are estimates, treated
  as bounds, not point values.
- 07 Retry-Timeout (~4.5% wall from 54 retries, zero timeouts): **CONFIRMED**
  order of magnitude (54 extra calls / 2284 = 2.4% of calls; with slot math
  ~100 s wall).
- 08 Fingerprint-Incremental (next bare run ~45-120 s; only the 4 error
  tombstones retry): **PLAUSIBLE, code-verified logic**, runtime number is a
  projection until the next run measures it. Caveat CONFIRMED in code: coverage
  modes share one sidecar path per paper, so a fleet run that re-evaluates a
  paper overwrites an existing `--all-pages` sidecar.
- 12 False-Economy (~47-58% of LLM wall changed no merged verdict; 70% empty
  unit checks; 111 no-source-packet units): **CORE NUMBERS CONFIRMED**
  (1057/1510 empty reproduced; `unit_judge.py:379-385` shows no-source-packet
  units are skipped BEFORE any LLM call, so they cost no tokens, but they
  consume selection slots and land in `unchecked_unit_ids`, which caps coverage
  and forces review). The "% of wall that bought nothing" is an interpretation:
  an empty unit check is only "waste" ex post; ex ante it is the audit. Kept as
  a routing-quality finding, not as recoverable wall time at zero risk.
- 09 Escalation-Cost (~1-2% of calls; 11/16 escalations refuted the screen flag):
  **CONFIRMED** counts from log.
- 10 Evidence-Verification (deterministic, no LLM calls, ~62 ms/paper CPU):
  **CONFIRMED**; `grounding.py` is string-search based.
- 13 Determinism-Guardian (c>32 forbidden, server slots 16->32 forbidden by
  negative result, dual-pod and in-paper parallel allowed-with-conditions):
  **CONFIRMED** against `research/concurrency-381/`, `research/slots-32-regression/
  SYNTHESIS.md`, `llm-batching/18-load-splitter.md`, CLAUDE.md D11.
- 14 Steelman (48 min is a cold-run one-off; steady state is incremental):
  **ACCEPTED** with the 08 caveat that the projection needs one measured run.

## Downgrades

- None fatal. Two personas used slightly different total-call figures
  (2111/2284/2308) from different accounting of retries and the text lane;
  synthesis uses ~2300 +- 100 and 6 calls/paper.
