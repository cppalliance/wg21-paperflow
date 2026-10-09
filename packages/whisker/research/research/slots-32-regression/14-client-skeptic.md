# 14 - Client-Side-Skeptic

**Verdict:** client-ruled-out — the inter-run workspace delta cannot explain +398 s when both runs used explicit `--concurrency 32` and full re-evaluation.
**Confidence:** high

## Findings

- [HIGH] **`_DEFAULT_CONCURRENCY` 16→32 is dead code for both measured runs.** Evidence: `git diff packages/whisker/src/whisker/tapetum_llm/cli.py` hunk at lines 63 and 184–186 — only the constant literal and its comment changed between runs; `default=_DEFAULT_CONCURRENCY` is bypassed whenever `--concurrency 32` is passed on the CLI. Impact: zero scheduling, semaphore, or fan-out difference between Run A and Run B.

- [HIGH] **`c=32` does not enter the tested-ceiling warning path and the warning is log-only anyway.** Evidence: `cli.py:659-666` — `if concurrency > _MAX_TESTED_CONCURRENCY` with `_MAX_TESTED_CONCURRENCY = 32` (line 68); equality at 32 skips the branch. The warning body is `logger.warning(...)` with no alternate code path. Impact: no throttling, no serial fallback, no extra work at c=32.

- [HIGH] **Both footers confirm full LLM adjudication, not incremental skip.** Evidence: `cli.py:654,693-709,830-838` — `--incremental` defaults off (`action="store_true"`); skip path runs only when `incremental` is True; footer computes `evaluated = len(pids) - skipped` and appends `", {skipped} skipped (incremental)"` only when `skipped > 0`. Both runs reported `381 evaluated` with no skip clause. Impact: sidecar fingerprint logic did not short-circuit papers in either run.

- [HIGH] **Inter-run workspace delta is comment/default-only plus a non-runtime doc edit.** Evidence: `git diff --stat` shows large uncommitted whisker churn vs HEAD, but user timeline pins the *between-run* change to `cli.py` constant/comment and `.cursor/skills/research/SKILL.md` (research orchestration docs, no import by `whisker-tapetum-llm`). Impact: no client module on the hot path changed behavior between 692.3 s and 1090.2 s.

- [MED] **Client concurrency mechanics were identical: `Semaphore(32)` + `asyncio.gather`.** Evidence: `cli.py:656-671,812-814` — `concurrency = max(1, args.concurrency)` then `sem = asyncio.Semaphore(concurrency)`; all 381 tasks launched via `gather`. Impact: client offered the same 32-wide request fan-out to the pod in both runs; wall-time delta must come from server-side per-request latency or queueing, not client parallelism change.

- [MED] **Verdict mix shifted (252→237 pass, 118→130 review, 10→13 fail) but that is downstream of model output, not the constant flip.** Evidence: measured footers; escalation inside `adjudicate_paper`/`judge_pdf_extraction` depends on LLM confidence bands, unchanged between runs. Impact: Run B may have incurred marginally more tier-2 calls via stochastic verdict drift, but this cannot account for a +57% wall-time jump and correlates with server `--max-num-seqs` change, not client code.

- [LOW] **Fixed per-batch overhead is negligible vs +398 s.** Evidence: `cli.py:504-544` health probe capped at `_HEALTH_PROBE_TIMEOUT_SECONDS = 30.0`; `_BATCH_QUIET_LOGGERS` / `_BarAwareHandler` affect logging only. Impact: at most tens of seconds one-time overhead, unchanged between runs.

- [LOW] **Local machine load is an unlikely confounder.** Evidence: user reports two earlier runs today completed normally; both batch runs used remote `alliance-pod` LLM endpoint. Impact: client host contention ruled weak but not measured; not the leading hypothesis.

## What would confirm/refute this

**Confirm client ruled out:** Re-run the same 381-PID command with current `cli.py`, explicit `--concurrency 32`, no `--incremental`, against pod at `--max-num-seqs 16`; if wall time returns near 692 s, the regression is server-config-bound regardless of `_DEFAULT_CONCURRENCY` comment edits.

**Refute (client suspect):** `git stash` to the pre-Run-A `cli.py` (default 16, same comment block otherwise) and re-run against the same pod config; if wall time drops materially while server slots stay at 32, a hidden client behavioral delta beyond the constant exists in the uncommitted diff and must be bisected.
