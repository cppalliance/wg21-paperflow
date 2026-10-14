# 04 - Concurrency-Plumbing-Auditor

**Verdict:** usable — client concurrency 32 was active end-to-end for the PDF and text lanes; no hidden global Semaphore(1) throttled tonight's fleet run.
**Confidence:** high

## Findings

- [CRITICAL] Paper-level concurrency 32 was the active bound tonight (bare run, no `--concurrency` override). Evidence: `cli.py:124` `_DEFAULT_CONCURRENCY = 32`; `cli.py:326-328` argparse default; `cli.py:1090` `sem = asyncio.Semaphore(concurrency)`; `cli.py:1363` `asyncio.gather(...)`. Runtime: `00-baseline.md:25-26` documents bare full run at default c=32; `00-baseline.md:37-39` throughput curve ~8 papers/min steady for 48 min (2883 s / 381 = 7.6 s/paper); log footer `2883.0s` matches baseline. Impact: rejects the "16 papers sat idle" failure class; fleet was not serial at the paper level.

- [CRITICAL] Every PDF-lane LLM call bypasses `pipeline.run_task` and its global `_task_semaphore`. Evidence: `judge_task.py:52-74` `run_judge_task` calls `agent.run` directly with no semaphore; `pdf_judge.py:650` monolith; `unit_judge.py:258` metadata/outline; `pdf_judge.py:398` page escalation; `unit_judge.py:755` unit checks — all route through `run_judge_task`. Contrast: `tasks.py:38` `_task_semaphore = asyncio.Semaphore(1)`; `tasks.py:57` `async with _task_semaphore`. Impact: the 07-09 batching fix is intact; PDF lane concurrency is bounded only by the CLI sem (32) plus per-paper serial cascade.

- [HIGH] The VLM/vision path did not fire in tonight's bare fleet run. Evidence: `vision_task.py:55-59` `_VISION_TASK_CONCURRENCY = 1` module-global semaphore; `vision_task.py:23-26` "No production CLI or service configuration invokes it"; `cli.py` has no import of `vlm_adjudicate`, `transcribe`, or `run_vision_task` (grep confirms). Runtime: all 181 logged verdict lines show `all_pages=False` (`00-baseline.md:35`); 381 sidecars have `all_pages_requested=false` (0 true); log grep for `vision|vlm|transcribe` returns 0 matches (the 2 "ideal" hits are `IdealVerificationError`, not vision). Impact: the Semaphore(1) vision gate priced at **0 s** tonight; not a regression contributor.

- [MED] `ideal_verify` is the one remaining global `run_task` chokepoint, but it fired negligibly tonight. Evidence: `ideal_verify.py:151` `verification = await run_task(...)`; `tasks.py:57` serial gate. CLI wires it post-judge: `cli.py:1129-1135` `_attach_ideal` after `judge_pdf_extraction` or `adjudicate_paper`. Runtime: 4 ideal files exist (`packages/tomd/tests/fixtures/golden/ideals/`); 3 overlap the 381-paper fleet (`p4182r0`, `p4228r0`, `p4020r0`); sidecars show 1 successful `ideal_verification` (p4020r0), 2 `IdealVerificationError` tombstones (P4182R0, P4228R0). Impact: at most ~3 ideal calls serialized through Semaphore(1) — upper bound ~90 s (<3% of 2883 s); cannot explain 4.2x regression.

- [HIGH] No shared HTTP client connection-pool bottleneck below 32. Evidence: `model_backends.py:283` creates a **new** `AsyncOpenAI(...)` per `ModelBackend.run()` call (not one shared client); OpenAI SDK default `Limits(max_connections=1000, max_keepalive_connections=100)` (runtime probe). `cli.py:133-134` comment references the **600 s read timeout**, not a pool cap below 32. Impact: the "pool < 32 throttles gather" hypothesis is dead; in-flight bound is CLI sem × per-paper serial calls, not httpx pool exhaustion.

- [MED] Text-lane papers (201/381 sidecars lack `lane`/`source_kind`; HTML path) also avoid `run_task` for adjudication. Evidence: `adjudicate.py:242,252,299` call `run_agent` directly; `runner.py:219-272` `run_agent` has no global semaphore; `adjudicate.py` has zero `run_task` imports. Unit checks on HTML path reuse `run_judge_task` via `run_unit_checks` (`unit_judge.py:755`). `dispatch()` parallel branch is a serial `for msg in user_msgs` loop (`runner.py:369-373`), not a missing `_parallel_semaphore` (symbol absent from codebase; doc drift only). Impact: 201 text-lane papers participated in the same c=32 gather; no second global gate.

- [MED] Within-paper serial cascade is intentional and is the dominant per-paper cost structure, not a hidden fleet chokepoint. Evidence: `pdf_judge.py:646-890` monolith → metadata → serial page escalations → serial unit loop (`unit_judge.py:379-410` `for unit_id in selected_unit_ids: await _check_one_unit`); `00-baseline.md:90-93` "concurrency: 1" in-paper. Log: 111 `unit section:N has no source packet` warnings; 16 escalation lines. Impact: explains higher s/paper (7.6 vs 1.8 baseline) via call-volume × serial chain, not lost paper slots.

- [LOW] Readback is not in the bare fleet path. Evidence: separate `whisker-readback` CLI; `readback.py:337` synchronous `httpx.Client`, not `pipeline.run_task`. Impact: zero fleet cost.

## False-pass hypothesis

An analyst sees `pipeline.tasks._task_semaphore = Semaphore(1)` in `tasks.py:38` and concludes the entire tapetum fleet serialized globally, missing that `judge_task.py` and `adjudicate.py`'s `run_agent` path bypass it — wrongly blaming concurrency loss for a call-count regression.

## False-fail hypothesis

An analyst sees steady ~8 papers/min (`00-baseline.md:38`) and interprets uniform throughput as proof of a single global bottleneck, when it is equally consistent with 32 papers each paying a uniform ~4-6 serial LLM calls (post-07-17 source-aware lane) while slots stay full.

## What would change my mind

A runtime trace showing at most one in-flight HTTP completion to `alliance-pod` across the full 2883 s window (e.g. OpenTelemetry span count peak == 1), or a log line proving `--concurrency 1` was passed despite the bare-run default.
