# 23 - Cost-latency-analyst

**Verdict:** usable-with-conditions — review-mode `--all-pages` is pod-economically fine (one paper, hourly billing, 5–17 min typical) but the fixed 2,220 s envelope kills any n>5 paper under per-call timeout ceilings unless timeout scales with page count.
**Confidence:** high

## Findings

- [CRITICAL] Current PDF-judge outer timeout is fixed at **2,220 s** and does not scale with page count. Evidence: `_pdf_judge_timeout_seconds()` = `900 + 5×120 + (1+5)×120` = **2,220 s** (`cli.py:146-151`); applied via `asyncio.wait_for(..., timeout=_pdf_judge_timeout_seconds())` (`cli.py:1121-1126`). All-pages worst-case serial budget = monolith (`_PAPER_TIMEOUT_SECONDS` 900) + metadata (1×120) + n unit checks (n×120) + escalations (5×120) = **1,620 + 120n** s. Solve 1,620 + 120n > 2,220 → **n > 5**. Impact: a 15-, 33-, or 40-page golden review hits `asyncio.TimeoutError` whenever calls approach their 120 s caps (57 / 93 / 107 min needed vs 37 min allowed).

- [HIGH] Worst-case wall-clock at n ∈ {15, 33, 40} (every serial call at its cap, D11 serial). Evidence: constants `UNIT_CHECK_TIMEOUT_SECONDS=120`, `PAGE_ESCALATION_TIMEOUT_SECONDS=120`, `MAX_PAGE_ESCALATIONS=5` (`constants.py:191-197,241-242`); call chain monolith + metadata + n units + ≤5 escalations (`pdf_judge.py:642-675,729-815,843-850`; metadata at `unit_judge.py:218-227`). Computed: **n=15 → 3,420 s (57.0 min)**; **n=33 → 5,580 s (93.0 min)**; **n=40 → 6,420 s (107.0 min)**. Impact: timeout formula must budget these ceilings, not capped-mode 2,220 s.

- [HIGH] Typical review-mode wall-clock stays operator-tolerable; fleet cost objections do not transfer. Evidence: prior per-page band **8–28 s/call** for 33 serial scoped calls = **4.4–15 min** (`research/per-page-judging/SYNTHESIS.md:16-17`); add monolith + metadata (~25–60 s, `pdf_judge.py:642-675`). Computed typical (t_scoped=15 s, t_mono=30 s, t_meta=15 s, 0 escalations): **n=15 → 270 s (4.5 min)**; **n=33 → 540 s (9.0 min)**; **n=40 → 645 s (10.8 min)**. Low/high bands: n=33 → **297 s (4.9 min)** at 8 s/call or **984 s (16.4 min)** at 28 s/call. Pod is **billed per hour of uptime, not per token** (`00-baseline.md:36`; `unit_judge.py:284-285`). Impact: marginal dollar cost of one all-pages golden run is one pod-hour whether it takes 5 or 17 min; wall-clock and timeout correctness dominate, not token spend.

- [HIGH] Recommended timeout shape: keep capped default, add page-count branch for `--all-pages`. Evidence: existing additive pattern at `cli.py:146-151`; `(1 + MAX_UNIT_CHECKS)` term covers metadata + capped units (`unit_judge.py:218-227`, `constants.py:223-227`). Proposed: `_pdf_judge_timeout_seconds(page_count: int | None = None) -> float` returning `_PAPER_TIMEOUT_SECONDS + MAX_PAGE_ESCALATIONS * PAGE_ESCALATION_TIMEOUT_SECONDS + (1 + (page_count if page_count is not None else MAX_UNIT_CHECKS)) * UNIT_CHECK_TIMEOUT_SECONDS`. For n=40: **6,420 s**. Impact: preserves 2,220 s for fleet default; all-pages gets honest headroom without inflating every PDF run.

- [MED] Retry logic does not multiply per-call wall-clock beyond existing `asyncio.wait_for` caps on scoped calls; monolith is the exception. Evidence: alliance-pod uses `vllm_thinking` (`SERVICES.toml:64-65`); raw-JSON path `max_attempts = min(2, request_limit)` (`model_backends.py:300-350`) — up to **2** API round trips per logical call, sharing one timeout window. Metadata, unit checks, and page escalations each wrap `run_judge_task` in `asyncio.wait_for(..., timeout=120)` (`unit_judge.py:218-227,683-689`; `pdf_judge.py:412-417`). Monolith has **no** per-call `wait_for` (`pdf_judge.py:642-649`); outer envelope assigns 900 s and cli notes **600 s** httpx read timeout per call across retries (`cli.py:128-131`). Impact: worst-case planning should use 120 s × (1 + n + 5) scoped calls + 900 s monolith, not an extra retry multiplier on scoped calls; do not assume 2× on top of 120 s for units.

- [MED] Golden-PR ideal verification adds up to **900 s** outside the PDF-judge `wait_for`, not in the current formula. Evidence: `_attach_ideal` runs after `judge_pdf_extraction` returns (`cli.py:1127-1128`); ideal path uses `asyncio.wait_for(..., timeout=_PAPER_TIMEOUT_SECONDS)` (`cli.py:1070-1077`). Impact: operator-facing ceiling for a full golden `--all-pages` + ideal run is **pdf timeout + up to 900 s**; plan ~108 min worst case for n=40 with ideal, not 107 min.

- [LOW] `--all-pages` does not remove escalation or unit caps in current code; latency model must include both lanes. Evidence: `MAX_PAGE_ESCALATIONS=5` still gates recall-screen escalations (`pdf_judge.py:729-740`); unit path still routes via `route_pdf_units` today (`pdf_judge.py:837-849`, `00-baseline.md:22-23`). Impact: if `--all-pages` only forces required `page:N` units but leaves recall escalations capped at 5, worst-case LLM count is **2 + n + min(flagged, 5)**, not 2 + n alone; timeout formula above still upper-bounds this.

## False-pass hypothesis

none found — a timeout abort surfaces as `asyncio.TimeoutError` / error tombstone (`cli.py:1121-1126`), not a pass with full page coverage; the failure mode is incomplete review, not silent acceptance.

## False-fail hypothesis

A legitimate 33-page golden review on a slow pod day (each scoped call 90–110 s, monolith 120 s) accumulates **~4,000+ s** of real work and exceeds the fixed **2,220 s** envelope even though every call is healthy, producing a timeout false-fail before the last pages are judged.

## What would change my mind

Measured P95 end-to-end latency for `--all-pages` on alliance-pod over 10 golden PDFs spanning 15–40 pages, showing (1) scoped unit-check P95 < 45 s and (2) zero outer-timeout aborts with the fixed 2,220 s budget — would downgrade the timeout finding to MED and allow shipping without a page-count parameter.
