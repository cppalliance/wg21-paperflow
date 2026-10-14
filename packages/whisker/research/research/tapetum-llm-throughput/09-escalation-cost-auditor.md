# 09 - Escalation-Cost-Auditor

**Verdict:** usable-with-conditions — both escalation paths are wired correctly and catch real gaps, but page-escalation refutes 69% of screen flags at full serial LLM cost, and the combined escalation tier accounts for only ~1.9% of tonight's LLM call volume, so it cannot explain the 692 s → 2886 s regression.
**Confidence:** high (page-escalation counts and confirmed/refuted split are direct from log + sidecars); medium (tier-2 verdict-flip rate: tier-1 outcome is not persisted separately for diff)

## Findings

- [HIGH] Tonight's fleet run logged exactly **16 page-escalation calls across 13 PDF papers**, matching sidecar `page_escalations` records (16 flagged pages total). Evidence: `_scratch/whisker-fullrun/llm-stderr.txt` (16 `escalation` lines); sidecar aggregate over `data/whisker/llm/*.whisker.tapetum.json`. Impact: page-escalation is a rare, PDF-only path (~7.2% of 180 PDF papers), not a fleet-wide multiplier.

- [HIGH] Page-escalation outcome split: **5 confirmed (`confirmed=True`, real `candidate_not_found` gaps) vs 11 refuted (`confirmed=False`, model returned `content_missing=False`)** — a **31% confirmation rate**. Evidence: log lines (e.g. `P4221R0: page-1 escalation -> content_missing=False confirmed=False quotes=0 conf=0.95`); sidecar field `content_missing` (5 true / 11 false). Impact: the lane is functioning as a **false-positive filter** on the deterministic screen, but **11 of 16 calls (~69%) bought no verdict change** and still ran at full latency.

- [HIGH] Page escalation fires when `screen_pages()` flags a page with `content_recall < PAGE_RECALL_FLOOR` (0.90) and `tokens >= PAGE_MIN_TOKENS` (50); capped at `MAX_PAGE_ESCALATIONS=5` per paper (`pdf_judge.py:296-321`, `constants.py:177-191`). Each flagged page triggers **one scoped `PageJudgment` LLM call** via `_escalate_page` → `run_judge_task` — **no vision** (`pdf_judge.py:370-404`; `vision_task.py` is not imported on this path). Impact: predictable +1 serial call per flagged page, text-only.

- [HIGH] Page escalations run **inside the paper's serial chain**, after monolith + metadata and before unit checks: monolith (`pdf_judge.py:646-657`) → metadata (`675+`) → serial `for entry in flagged_entries` (`753-832`) → unit checks (`834+`). `cli.py:143-145` documents D11: escalations run one at a time. Impact: each refuted escalation adds its full decode latency (~25-30 s per call per `00-baseline.md:59-60`) directly to that paper's wall-clock slot occupancy.

- [MED] Escalated papers do **not** correlate with the slowest sidecar completion gaps. Evidence: inter-write gap analysis on 381 sidecars — median gap involving escalated papers **3.6 s** vs fleet median **4.4 s**; only **1 of top-20** slowest gaps involves an escalated PID (P2034R6 at 30.9 s, rank 11). Escalated papers average **4.7 unit checks** vs fleet mean **4.0** — slightly above average but not outliers. Impact: escalation is not the tail-latency driver; unit-check depth dominates slow papers.

- [HIGH] Text-lane **tier-2 escalation** fired on **23 / 201 HTML papers (11.4%)** with signals `axis_conflict` (13) and `ungrounded_evidence` (10); **`confidence_ambiguous` fired 0 times** tonight. All 23 landed `review` (11) or `fail` (12); zero `pass`. Evidence: sidecar `tier2_model` + `escalation_signals` histogram; `adjudicate.py:256-300`. Impact: tier-2 triggers on observable tier-1 contradictions, not the dead confidence band (`constants.py:23-24`).

- [HIGH] Tier-2 does **not** call a bigger model tonight: `tapetum_llm.md:21-22` maps both `fast` and `deep` to **`alliance-pod` / `deepseek-v4-pro`**. Tier-2 buys a second adjudication with tier-1 context fed back (`adjudicate.py:697-716`) and a higher output budget (`adjudicate.py:89-90`: fast=1024, deep=2048 tokens) — same pod, same model. PDF page escalation uses the **`deep` slot judge agent** (`cli.py:1004-1014`), also `alliance-pod`. Impact: escalation latency is decode-time on identical hardware, not model-up tier cost.

- [CRITICAL] Combined escalation call volume is **39 / ~2111 total LLM calls (1.85%)** tonight: 16 page-esc + 23 tier-2, vs 381 monolith/tier-1 + 180 metadata + 1510 unit checks (sidecar aggregate). At ~27 s/call (`00-baseline.md:59-60`), serial escalation time ≈ **1053 s**; spread across client c=32 → **~33 s fleet wall (~1.1% of 2883 s)**. Impact: **escalation tiers are not the 4.2× regression driver**; source-aware unit checks (~72% of calls) dominate. Escalation is real cost on affected papers but negligible at fleet scale.

## False-pass hypothesis

P3978R0 page-1 and page-2: screen flagged (recall below 0.90), escalation returned `content_missing=False confirmed=False`. If the screen was right and the model wrongly cleared both pages, a localized gap could survive as `review`/`fail` only from other signals — but the confirmed page-3 escalation on the same paper shows the path can still catch real loss when the model agrees.

## False-fail hypothesis

P2034R6 page-1: screen flagged, escalation refuted (`confirmed=False`). If the screen was a false flag (healthy page with low recall due to reflow), the escalation correctly prevented a demotion — but the call still consumed ~25-30 s of serial slot time for zero verdict delta.

## What would change my mind

Per-call timestamps in sidecars or debug transcripts showing escalation calls averaging >>30 s (e.g. vision firing, or tier-2 on a repointed slower pod) would flip the fleet-scale pricing; tonight's evidence says escalation is ~2% of call volume on the same `alliance-pod`.
