# tapetum-llm fleet-run throughput (692 s -> 2886 s) - Research Synthesis

**Verdict band:** usable-with-conditions   **Confidence:** high
**Decision vs our codebase:** keep the architecture; fix routing waste; no concurrency change

## Summary

- **The batching strategy is NOT lost.** Client `--concurrency 32` was live end-to-end
  (`cli.py:1090` semaphore + `asyncio.gather`), every pdf-lane LLM call bypasses the
  global `pipeline.run_task` Semaphore(1) via `judge_task.py` (the historical
  "16 papers sat idle" bug stays fixed), vision never fired, no HTTP-pool cap below 32.
  The pod was healthy: implied per-call latency 20.2 s at 16 server slots.
- **The 4.2x regression is call-volume, by design.** The 2026-07-09 benchmark cascade
  made ~1 LLM call/paper (213 calls / 204 papers). The 2026-07-17 source-aware lane
  (c59139c) makes **6.0 calls/paper** (my aggregation over all 381 sidecars: 381
  monolith + 377 metadata/outline + 1510 unit checks (median 5 = MAX_UNIT_CHECKS cap)
  + 16 escalations = ~2284 calls). Wall ~= calls x latency / 16 slots. 6x calls,
  4.2x wall (per-call latency actually fell 30 -> 20 s because unit calls are smaller).
- **Tonight was artificially cold.** The 07-22 `_LANE_VERSION` 8->9 bump invalidated
  all 381 fingerprints, so incremental skip (on by default) skipped nothing. The next
  bare fleet run re-evaluates only changed papers + the 4 error tombstones
  (P3400R3, P3977R0, P4182R0, P4228R0): projected ~1-2 min, to be confirmed by the
  next run.
- **07-22 prompt/schema growth is noise:** monolith system prompt +22% chars,
  unit-check contract +1951 chars; combined single-digit-% of the regression.
  Retries: 54 model retries ~ 100 s wall (~4%). Zero timeout hits.
- **The real inefficiency is routing quality, not plumbing:** 70% of unit checks
  (1057/1510) returned zero defect groups; only 16/381 papers had their merged
  verdict changed by LLM findings (fusion: llm_rescue_heading=9 +
  llm_clear_soft_review=7), i.e. ~143 calls per changed verdict; 111 routed units
  had no source packet, cost no LLM call but consume selection slots and force
  `coverage_complete=false` -> review cap (`unit_judge.py:379-385`).

## Top findings (ranked)

- [HIGH][ACTIONABLE-NOW] No-source-packet units burn MAX_UNIT_CHECKS slots and
  force incomplete-coverage review caps without any LLM look. Evidence:
  `unit_judge.py:379-385`, 111 log occurrences. Fix direction: filter units with
  empty source packets BEFORE selection/capping, so real pages get the slots.
- [HIGH][ACTIONABLE-NOW] 4 error papers tombstone AFTER the full call cascade
  (IdealVerificationError post-hoc); fail-not-partial is correct, but the retry
  granularity wastes ~24 calls. Evidence: log ERROR lines; 07-retry report.
- [MED][DECISION] Wall-time levers that are OFF the table: client c>32
  (`research/concurrency-381/` negative result), server max-num-seqs 16->32
  (`research/slots-32-regression/SYNTHESIS.md`: +60% wall), cutting unit caps or
  schema/quotes (fidelity rules, CLAUDE.md). Allowed-with-conditions: dual-pod
  sharding (~2x, verdict-drift caveat documented in `llm-batching/18-load-splitter.md`),
  in-paper parallel unit checks (advisory lane is exempt from D11, but adds MoE
  batch-composition variance; only worth it for interactive --all-pages runs where
  one paper's serial chain dominates).
- [MED] Metadata-outline-fail short-circuit: when the outline check already fails
  hard, up to 5 unit checks still run and cannot lift the verdict. Skipping them
  saves ~45% of calls on affected papers (12-false-economy). Needs a fidelity
  decision: unit findings are still reported to humans even when the verdict is
  already capped, so this trades report completeness for speed. Not free.
- [LOW] Prompt/deocde growth from the 07-22 all-pages work is negligible for the
  fleet path, and `--all-pages` itself never fires in fleet runs (181x
  `all_pages=False` in the log).

## Bugs / edge-cases in OUR code (surfaced by the comparison)

- `unit_judge.py:379-385`: no-source-packet units selected then dropped (slot waste
  + forced review cap). See above.
- Sidecar path collision: routed fleet run overwrites an existing `--all-pages`
  sidecar for the same pid once the paper re-evaluates (fingerprint `coverage_mode`
  separates cache identity but not the on-disk artifact). If all-pages review
  artifacts must survive nightly fleet runs, they need their own filename or an
  overwrite guard.

## How the others do it (05-web.md, 20 cards)

Nobody in the surveyed ecosystem out-batches us at the judge layer: marker
`--use_llm` defaults to a 3-thread pool per document and its benchmark LLMScorer is
fully serial; promptfoo defaults maxConcurrency=4 (judge assertions 3), DeepEval 20,
Ragas 16, OpenAI evals 10 threads. olmOCR floods 1600 concurrent requests, but at a
dense 7B VLM it self-hosts; the MoE guidance (paralleliq card) is max-num-seqs 4-8
for DeepSeek-class models, which makes our server-side 16 already aggressive and
explains the measured 16->32 regression. Docling's official path is exactly ours:
decoupled vLLM serving + client concurrency matched to server capacity. The one
portable trick we lack: **prefix caching** for the shared system prompt
(vLLM `--enable-prefix-caching`), worth ~1-3 min per cold fleet run, prefill-only.

## Top portable detail

olmOCR's work-item design ("flood the server with everything from one work item,
drain, next item") is the scaled version of our c=32-overfills-16 approach; it
validates the pattern but adds nothing for a single-pod setup. The actionable
import is vLLM server flags: `--enable-prefix-caching` (shared 3.7k-char system
prompt) and keeping max-num-seqs at 16 per the MoE guidance.

## Flip conditions

- If the next bare fleet run (warm fingerprints) still takes >10 min, the
  incremental-skip projection is wrong and this synthesis must be reopened.
- If a measured A/B (dual pod) shows verdict drift beyond the documented advisory
  variance budget, the sharding lever moves to forbidden.

---
Sources: self-target at workspace HEAD 51cb7046 (uncommitted 07-22 changes included),
baseline 00-baseline.md, 2026-07-23.
Web: 05-web.md (20 finding cards, 20 unique URLs).
Personas: 14 (01-14). Meta-review: opus-A-verification.md (combined A/B/E pass,
all load-bearing numbers independently reproduced).
