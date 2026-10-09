# 03 - Cascade-Topology-Auditor

**Verdict:** usable-with-conditions (in-paper serialization is real and avoidable, but it is not the primary driver of the 4.2x wall regression; call-volume growth is)
**Confidence:** high

## Findings

- [CRITICAL] The PDF fleet path executes a strictly serial LLM chain per paper inside one CLI semaphore slot: monolith → metadata → page escalations (0–5) → unit checks (0–5), plus optional ideal verifier. Evidence: `pdf_judge.py:646-890` (`await run_judge_task` monolith at 650, `await run_metadata_outline_check` at 677, serial `for entry in flagged_entries: await _escalate_page` at 753-763, `await run_unit_checks` at 882; `unit_judge.py:379-410` serial `for unit_id in selected_unit_ids: await _check_one_unit`; `cli.py:1098-1204` entire `judge_pdf_extraction` runs under `async with sem`). Impact: per-paper wall is the **sum** of call latencies, not the max; this matches the baseline's uniform ~7.6 s/paper effective cost (`00-baseline.md:41-42`, `2883s / 381`) rather than a scheduling stall.

- [CRITICAL] Call count per paper exploded vs the 07-09 benchmark era (~1 LLM call/paper, `00-baseline.md:61-62`) to **2 mandatory + up to 10 optional** in routed PDF mode: always monolith + metadata (`pdf_judge.py:650,677`); up to `MAX_PAGE_ESCALATIONS=5` page calls (`constants.py:191`, `pdf_judge.py:753`); up to `MAX_UNIT_CHECKS=5` unit calls when `route_pdf_units` emits signals (`constants.py:223`, `unit_judge.py:355-410`). Tonight's log: 16 escalation lines on 381 papers (~0.04/paper, `00-baseline.md:32-33`); unit routing dominates. Impact: back-of-envelope `381 × K × ~30s decode / 16 slots` with K≈5 gives ~3500s ceiling vs K≈1 giving ~714s (`00-baseline.md:103-107`), matching 692s→2883s without invoking lost concurrency.

- [HIGH] Most serial steps lack a true cross-step data dependency; they are embarrassingly parallel by design policy, not by necessity. Monolith output is not input to metadata (metadata uses `page_units` + candidate md, `pdf_judge.py:662-684`), page escalations (only need `page_screen` + page text, computable before monolith at `pdf_judge.py:636`), or unit checks (`route_pdf_units(page_units, raw_tomd_md)` at 851, independent of monolith verdict). Only final verdict folding (`pdf_judge.py:710-931`) needs all branches. `tapetum_llm.md:27-28` documents `concurrency: 1` as intentional in-paper policy. Impact: parallelizing unit/page calls would shorten **isolated** per-paper wall but does not explain tonight's fleet regression.

- [HIGH] In-paper parallelism would barely help at fleet scale because paper-level concurrency already saturates the pod. Client `c=32` overfills server `--max-num-seqs 16` (`00-baseline.md:81-85`, `cli.py:124,1090`; `tapetum_llm.md:29`). Steady-state: up to 32 papers each hold one in-flight LLM request (`judge_task.py:52-74`, no global gate), competing for 16 decode slots. Parallelizing K unit checks inside one paper would consume multiple slots for one PID and **reduce** cross-paper fill when the pod is already slot-bound. Impact: serialization is a second-order knob; the 4.2x is priced by K×latency/16, not by in-paper ordering.

- [MED] Tail / end-of-run slot-idle effect from in-paper serialization is negligible on this run. Throughput buckets: 7 / 57 / 78 / 102 / 83 / **54** papers per 10-min window (`00-baseline.md:37-39`); baseline explicitly records "No stall, no warm-up cliff, **no long tail**. Uniform per-paper cost" (`00-baseline.md:39-40`). Last bucket 54 papers still ≈5.4/min, not an idle pod. Even if the final ≤32 papers ran fully serial internally with zero overlap, added wall ≈ `(K-1) × latency × 32 / 16` with K≤5 and latency≈7s effective → tens of seconds, not the ~2191s delta vs 692s. Impact: do not chase in-paper parallelism to fix tonight's regression.

- [MED] Deterministic / CPU work runs inside the paper semaphore and can block a **paper slot** (not a server slot). Before first LLM: PyMuPDF `extract_textlayer` (`pdf_judge.py:596-598`), `screen_pages` (`636`), metrics (`628-629`). Between LLM calls: `extract_page_units` (`662-668`) sits **between monolith and metadata** while the paper still holds `sem`. After LLM: `ground_spans` / `classify_candidate_evidence` (`692-706`, `777-786`), `route_pdf_units` (`851`), `verify_unit_evidence` (`unit_judge.py:412`). Impact: minor paper-slot inflation (large PDFs hold 1/32 client slots during PyMuPDF); does not consume vLLM slots. Moving `extract_page_units` before monolith would also unlock metadata ∥ monolith overlap.

- [LOW] `judge_task.py:65-66` comment ("Each paper issues at most one judge call") is stale post-07-17; PDF papers now issue 2–12+. Impact: documentation hazard only; dispatch itself correctly has no global `Semaphore(1)` (`judge_task.py:10-22`).

- [LOW] Evidence verification is CPU-only (no LLM) and is already local/fast: monolith quotes grounded at `pdf_judge.py:692-706`; unit quotes batched post-loop at `unit_judge.py:412-728`. Per-page escalation verifies inline after each page LLM (`777-786`). Independent claim dispositions could run concurrently with each other but cost is negligible vs decode. Impact: not a throughput lever.

## Exact sequential chain (one PDF paper, fleet routed mode)

```
[CPU, inside sem]
  extract_textlayer (596) → clean/normalize/strip (608-613) → context guard (615-626)
  → text_nid/content_recall (628-629) → screen_pages (636)

[LLM #1, serial]
  monolith pdf-judge (650)

[CPU]
  extract_page_units (662-668)

[LLM #2, serial]
  metadata/outline check (677-684)

[CPU, evidence]
  ground_spans + classify_candidate_evidence on monolith quotes (692-706)
  → partial verdict fold (710-731)

[LLM #3..#3+N, serial N≤5]
  for each flagged page: _escalate_page (753-763) → per-page CPU evidence (777-786)

[CPU]
  route_pdf_units (851) — deterministic, no LLM

[LLM #4..#4+M, serial M≤5 if risk_signals]
  run_unit_checks → for each selected unit: _check_one_unit (unit_judge.py:379-410)

[CPU]
  verify_unit_evidence + defect aggregation (unit_judge.py:412-464)

[LLM optional, serial, cli.py]
  verify_against_ideal if ideal exists (1129-1137)

[CPU]
  final verdict fold + PdfJudgeResult (pdf_judge.py:926-1035)
```

**Could be concurrent without changing verdict inputs** (needs explicit gather + deterministic merge order): metadata ∥ monolith (after moving `extract_page_units` earlier); all page escalations in parallel; all unit checks in parallel; ideal verifier ∥ unit-check batch (independent of judge outputs). **True dependencies:** page escalations need `page_screen`; unit checks need `route_pdf_units`; final fold needs all branch results.

## Saturation arithmetic (baseline numbers)

| Quantity | Value | Source |
|---|---|---|
| Papers | 381 | `00-baseline.md:27,41` |
| Wall (2026-07-23) | 2883 s | `00-baseline.md:28,41` |
| Wall (2026-07-09) | 692.3 s | `00-baseline.md:13,41` |
| Effective s/paper | 7.6 vs 1.8 | `00-baseline.md:41-42` |
| Client concurrency | 32 | `00-baseline.md:25-26`, `cli.py:124` |
| Server slots | 16 | `00-baseline.md:84-85` |
| Fleet wall (LLM-dominated) | ≈ `total_calls × mean_decode / 16` | `00-baseline.md:92-93` |

With K≈1 call/paper: `381 × 30s / 16 ≈ 714s` ≈ 692s observed.
With K≈5 calls/paper: `381 × 5 × 30s / 16 ≈ 3572s` bracket; observed 2883s implies effective decode ≈24s/call or K≈4 after retries/errors (`54 model retries`, `00-baseline.md:28`).

In-paper parallelization at full fleet: **zero** expected wall gain when `32 papers × 1 in-flight ≥ 16 slots` (always true until the final wave). Last-bucket throughput 54/10min (`00-baseline.md:38`) shows the pod still fed; tail slot-idle from serialization is ≪ regression magnitude.

## False-pass hypothesis

Parallelizing unit checks without preserving deterministic merge order (sorted unit ids, quota selection at `unit_judge.py:175-213`) could change which units fit under `MAX_UNIT_CHECKS=5`, letting a different subset run and missing a critical `table_corruption` signal — verdict fold differs, coverage appears complete when the highest-severity unit was quota-skipped.

## False-fail hypothesis

None found from topology alone. Serialization inflates wall time but does not by itself demote verdicts; fail-closed caps come from unchecked units (`unit_judge.py:460-464`) and missing source packets (`unit_judge.py:382-385`), not from await ordering.

## What would change my mind

A sidecar-level per-paper call census from tonight's 381 JSON outputs showing median K≤2 LLM calls/paper would collapse the call-volume story and force re-attribution to decode latency growth or hidden global serialization (e.g. vision semaphore). Without that, the serial chain × K model stands.
