# 06 - Regression-Bisector

**Verdict:** usable (Event A owns the regression; Event B is a second-order prefill bump plus a one-off cache invalidation, not a hidden call multiplier)
**Confidence:** high

## Findings

- [CRITICAL] **Event A (c59139c, 2026-07-17) multiplied per-paper LLM dispatch from ~1 to ~6–7 calls and explains ~85% of the 4.2× wall regression.** Evidence: at `58a978c`, `pdf_judge.py` had a single `await run_judge_task` (monolith only, line 285 in that revision; no `screen_pages`, `run_metadata_outline_check`, `_escalate_page`, or `run_unit_checks`). At `c59139c`, `pdf_judge.py` adds four serial dispatch points: monolith (`637`), mandatory metadata (`663` via `unit_judge.run_metadata_outline_check`), page escalation loop (`739`, cap `MAX_PAGE_ESCALATIONS=5`, `constants.py:191`), and routed unit checks (`835`, cap `MAX_UNIT_CHECKS=5`, `constants.py:223`). `unit_judge.py` (new at c59139c) holds two `run_judge_task` call sites: metadata (`run_metadata_outline_check`) and per-unit `_check_one_unit`. Measured tonight: **2308 LLM calls / 377 successful sidecars = 6.11 calls/paper** vs reconstructed 07-09 **~389 calls** for the same PDF/HTML mix (`01-call-count-accountant.md:8-21`; `00-baseline.md:61-62`). Wall ratio 2883/692.3 = **4.17×** vs call ratio **5.9×** implies per-call decode is ~30% cheaper (shorter output discipline), not a scheduling bug. Impact: blaming Event B or pod variance as primary cause is mis-attribution.

- [CRITICAL] **Event B (uncommitted 07-22) does not add LLM call sites on the bare fleet path; `--all-pages` is inert tonight.** Evidence: log parse of `_scratch/whisker-fullrun/llm-stderr.txt`: **181 `all_pages=False`, 0 `all_pages=True`** (`00-baseline.md:35-36`). `cli.py:1185-1192` passes `all_pages=getattr(args, "all_pages", False)`; bare run never sets the flag. `pdf_judge.py:858-890` unit-check branch for fleet default is `elif risk_signals:` (routed cap), not the `if all_pages:` exhaustive branch. Event B diff adds `all_pages` wiring, `coverage_mode` fingerprinting, and `CONVERSION_CONTRACT` promotion in `unit_judge.py`, but the serial cascade topology at c59139c is unchanged for routed mode. Impact: the 4.2× regression would reproduce on committed c59139c alone; 07-22 work is not required to explain it.

- [HIGH] **Event A cascade BEFORE vs AFTER (PDF fleet path).** BEFORE (07-09, `58a978c`): **1 LLM call/paper** (monolith `pdf_judge.py:285`) + rare tier-2 only on HTML adjudicate path (~13/200, `00-baseline.md:61`). AFTER (c59139c+): **2 mandatory** (monolith + metadata, `pdf_judge.py:650,677`) + **0–5 page escalations** (serial loop `753-763`; tonight **16 escalation lines / 181 PDF verdict lines ≈ 0.09/paper**, `00-baseline.md:32`) + **0–5 unit checks** when `route_pdf_units` emits signals (`880-890`; **179/180 PDFs ran 5 checked units**, median fleet **7 calls/paper**, `01-call-count-accountant.md:11,38`). Evidence verification (`classify_candidate_evidence`, `verify_unit_evidence`) is CPU-only, zero LLM (`pdf_judge.py:696-706`, `unit_judge.py:412-728`; `01-call-count-accountant.md:17`). Impact: the "metadata + routed units + evidence verification" story is half wrong only on evidence verification (not LLM); metadata + units are the cost.

- [HIGH] **Event B cost is prompt growth on existing unit calls, not call-count growth.** Evidence: `UNIT_CHECK_SYSTEM_PROMPT` grew **1745 → 3696 chars (+112%)** when short `_UNIT_CONVERSION_CONTRACT` (511 chars at c59139c) became full `CONVERSION_CONTRACT` (2096 chars at HEAD, `unit_judge.py:70-106,129-159`; `02-prompt-token-auditor.md:12-13`). Monolith `JUDGE_SYSTEM_PROMPT` unchanged 07-17 → HEAD (`02-prompt-token-auditor.md:10`). At ~4000 tok/s prefill (`00-baseline.md:59`), +488 tok/system × ~5 unit calls ≈ **<1 s prefill/paper** vs **~108 s added decode** from Event A new calls (`02-prompt-token-auditor.md:31-32`). `_LANE_VERSION` **6 → 9** (`cli.py:112-114`; was 6 at c59139c) invalidated all fingerprints so incremental skip re-adjudicated **381/381 cold** (`00-baseline.md:43-45`). Impact: lane-version bump explains **why nothing was skipped tonight**, not **why each paper costs ~4× more** than 07-09.

- [MED] **Approximate multipliers assigned to each event and variance.** | Factor | Multiplier | Notes |
|--------|------------|-------|
| Event A call count | **~5.9×** (389 → 2308 calls) | Dominant; serial in-paper cascade (`00-baseline.md:90-93`) |
| Event A effective wall | **~4.2×** (692 → 2883 s) | Lower than call ratio because unit/metadata calls decode faster |
| Event B prompt (unit system) | **~1.1× prefill on unit calls only** | +112% on ~5 calls; <5% of per-paper wall |
| Event B cold cache | **1× cost vs warm skip** for this run | One-off trigger: all papers evaluated; not a latency spike per paper |
| Pod variance (historical) | **~1.4–2.1×** | 692 / 1090 / 1465 s prior c=32 runs (`00-baseline.md:54-56`) |
| `--all-pages` (not fired) | **0× tonight** | Would multiply to O(pages) LLM calls; absent from bare fleet |

- [MED] **Tonight's 48.1 min is the new steady state for full cold fleet runs at HEAD, not a one-off pod anomaly.** Evidence: uniform throughput **~8 papers/min** across all buckets, no tail stall (`00-baseline.md:37-39`); effective **7.6 s/paper** vs **1.8 s/paper** at 07-09 (`00-baseline.md:41-42`). The lane-version bump made this run cold (no incremental skips), but a cold rerun at c59139c would still land ~45–50 min because call topology is already expanded; Event B adds ~1–2% on top via unit prefill. **Warm incremental reruns** (fingerprints match at `_LANE_VERSION=9`) would skip unchanged papers and be dramatically faster—that is operational savings, not a return to 11.5 min for a full re-adjudication. Impact: operators should expect ~48 min for any logic/prompt bump that forces cold full fleet; expect much less only when fingerprints hit.

- [LOW] **Mis-attribution traps ruled out.** Vision/VLM global semaphore did not fire (dormant path, `01-call-count-accountant.md:22`). Ideal verifier: 1 paper only. HTML text-lane prompt +402 chars over the period is irrelevant to PDF-heavy log (`02-prompt-token-auditor.md:18`). Concurrency plumbing intact at c=32 (`00-baseline.md:81-89`). Impact: do not chase lost batching or `--all-pages` leakage.

## False-pass hypothesis

Attributing the regression primarily to Event B prompt bloat or `_LANE_VERSION=9` "cold pod warmup" would wrongly suggest reverting 07-22 contract text or re-running warm fixes the problem; a warm run at HEAD still pays ~6 LLM calls/paper whenever fingerprints miss, and committed c59139c alone already saturates `MAX_UNIT_CHECKS=5` on most PDFs.

## False-fail hypothesis

Treating tonight as a permanent 48 min floor for every future `whisker-tapetum-llm` invocation would ignore incremental skip: unchanged papers after a stable `_LANE_VERSION` would skip LLM entirely (`cli.py:1161-1168`), yielding wall time proportional to changed papers only.

## What would change my mind

A full cold fleet run checked out at **c59139c exactly** (no 07-22 diff) completing near **692–1465 s** would implicate Event B or uncommitted changes as primary; measured expectation is **~2400–2800 s** (same call shape, slightly shorter unit prompts).
