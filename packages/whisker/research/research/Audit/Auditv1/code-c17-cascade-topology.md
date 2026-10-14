# C17 — Cascade and Model-Topology Audit

**Auditor**: Cascade and Model-Topology Auditor
**Focus**: D1 (determinism, serial guarantees)
**Scope**: `packages/whisker/src/whisker/tapetum_llm/`
**Date**: 2026-07-19

---

## Executive Summary

The text lane implements a two-tier fast/deep cascade with three derived escalation signals (axis conflict, ungrounded evidence, ambiguous confidence). Chunking splits oversize papers on H2 boundaries, processes serially, and aggregates with worst-axis/min-confidence/union-evidence. The PDF lane uses per-page recall screens with capped escalation. Concurrency is serial-within-paper (one in-flight LLM call per paper) and concurrent across papers (bounded by `--concurrency` semaphore).

---

## Findings

### F1. Two-tier cascade: fast model triage -> deep model adjudication

| Field | Value |
|---|---|
| **Severity** | INFO |
| **Claim** | The text lane uses a 4-step pipeline: Select, Triage (fast slot), Adjudicate (deep slot, conditional), Decide. Tier-2 only fires when escalation signals are present. |
| **Evidence** | `adjudicate.py:514-525` (`_build_hooks` maps step names to hooks: "0. Select", "1. Triage" with `output_type=Adjudication`, "2. Adjudicate" with `output_type=Adjudication`, "3. Decide"). `adjudicate.py:228-249` (`_custom_triage` calls `run_agent(ctx, spec, user_msg)`). `adjudicate.py:278-296` (`_custom_adjudicate` checks `_escalation_signals` before calling `run_agent`). |
| **Affected gate** | D1 |
| **Confidence** | 1.00 |
| **False-pass hypothesis** | None; the conditional escalation path is explicit. |
| **False-fail hypothesis** | N/A. |

### F2. Three escalation triggers replace the dead scalar-band-only gate

| Field | Value |
|---|---|
| **Severity** | INFO |
| **Claim** | Escalation fires on: (1) `SIGNAL_AXIS_CONFLICT` (tier-1 findings contain both pass and fail), (2) `SIGNAL_UNGROUNDED_EVIDENCE` (at least one evidence quote failed grounding), (3) `SIGNAL_CONFIDENCE_AMBIGUOUS` (confidence in [0.35, 0.65] band). The scalar band alone was dead (0/198 escalations measured). |
| **Evidence** | `adjudicate.py:252-275` (`_escalation_signals` function). `constants.py:27-40` (signal names and band edges). `constants.py:18-26` (docstring: "0/198 escalations; DeepSeek's self-reported confidence never left [0.85, 1.00]"). |
| **Affected gate** | D1 (escalation determinism) |
| **Confidence** | 1.00 |
| **False-pass hypothesis** | The axis-conflict trigger fires on pass+fail co-occurrence but not on pass+review. A paper with only pass+review axes would not escalate via this trigger. This is by design (review is not contradictory). |
| **False-fail hypothesis** | N/A. |

### F3. Chunking splits on H2 boundaries, fence-aware

| Field | Value |
|---|---|
| **Severity** | INFO |
| **Claim** | `chunk_markdown` splits oversize papers (> `MAX_PAPER_MD_CHARS` = 500,000 chars) on H2 headings. The splitter is fence-aware (``## `` inside fenced blocks is not treated as a heading). Chunks are packed greedily. A section exceeding the budget is hard-split on line boundaries, setting `partial=True`. Concatenation is lossless. |
| **Evidence** | `chunking.py:129-164` (`chunk_markdown`). `chunking.py:167-194` (`_split_sections`, fence-aware: tracks `in_fence` and `fence_marker`). `chunking.py:197-220` (`_hard_split`, last-resort line-boundary split). `constants.py:61` (`MAX_PAPER_MD_CHARS = 500_000`). Tests: `test_tapetum_llm.py:1161-1193` (fits, H2 split lossless, oversize sets partial, deterministic, fence-aware). |
| **Affected gate** | D1, D3 |
| **Confidence** | 1.00 |
| **False-pass hypothesis** | None; extensive test coverage. |
| **False-fail hypothesis** | N/A. |

### F4. Oversize paper handling: serial triage, partial read → review demotion

| Field | Value |
|---|---|
| **Severity** | INFO |
| **Claim** | When a paper is chunked, chunks are triaged serially in a `for` loop (one `run_agent` call at a time). A partial read (hard-split section) forces the verdict to `review`. Tier-2 escalation is skipped for chunked papers ("re-injecting the full markdown for tier2 would 413 again"). |
| **Evidence** | `adjudicate.py:228-249` (`_custom_triage`: `for index, chunk in enumerate(chunks): ... parts.append(await run_agent(...))`). `adjudicate.py:278-296` (`_custom_adjudicate`: `if state.chunked: return` skips tier-2). `adjudicate.py:346-349` (partial read → review: `if state.partial and suggested_verdict == VERDICT_PASS: suggested_verdict = VERDICT_REVIEW`). |
| **Affected gate** | D1 (serial-within-paper), D11 |
| **Confidence** | 1.00 |
| **False-pass hypothesis** | None. |
| **False-fail hypothesis** | N/A. |

### F5. Per-slot output-token ceilings and MAX_PAPER_MD_CHARS are named constants

| Field | Value |
|---|---|
| **Severity** | INFO |
| **Claim** | Token budgets and char budgets are named constants, not bare literals. |
| **Evidence** | `adjudicate.py:87-91` (`_SLOT_MAX_TOKENS = {"fast": 1024, "deep": 2048}`, `_DEFAULT_MAX_TOKENS = 2048`). `constants.py:61` (`MAX_PAPER_MD_CHARS = 500_000`). `cli.py:104` (`_DEFAULT_CONCURRENCY = 32`). `cli.py:109` (`_MAX_TESTED_CONCURRENCY = 32`). `cli.py:115` (`_PAPER_TIMEOUT_SECONDS = 900.0`). |
| **Affected gate** | Invariant: named constants |
| **Confidence** | 1.00 |
| **False-pass hypothesis** | None. |
| **False-fail hypothesis** | N/A. |

### F6. Concurrent across papers, serial within paper

| Field | Value |
|---|---|
| **Severity** | INFO |
| **Claim** | The CLI uses `asyncio.Semaphore(concurrency)` to bound concurrent paper adjudications. Within each paper, LLM calls are sequential (one `run_agent` or `run_judge_task` per step, `for` loop over chunks). Papers are independent (own state, own sidecar). |
| **Evidence** | `cli.py:923` (`sem = asyncio.Semaphore(concurrency)`). `cli.py:926-1082` (`_adjudicate_one` acquires semaphore, processes one paper). `cli.py:1086-1088` (`asyncio.gather` fans out all papers). `cli.py:98-103` (docstring: "papers are independent (own state, own sidecar file) and the lane never gates"). `adjudicate.py:244-248` (serial chunk loop). `adjudicate.py:675` (`default_concurrency=1` on `StepContext`). |
| **Affected gate** | D11 |
| **Confidence** | 1.00 |
| **False-pass hypothesis** | None; `asyncio.Semaphore` wakes FIFO so with N=1 papers run in input order. |
| **False-fail hypothesis** | N/A. |

### F7. PDF lane: per-page screen with MAX_PAGE_ESCALATIONS cap

| Field | Value |
|---|---|
| **Severity** | INFO |
| **Claim** | `screen_pages` computes deterministic per-page `content_recall`. Pages below `PAGE_RECALL_FLOOR` (0.90) are flagged. Scoped LLM escalation runs on flagged pages, capped at `MAX_PAGE_ESCALATIONS` (5). Over the cap, no escalation calls are made and the verdict is capped at review. |
| **Evidence** | `pdf_judge.py:310-335` (`screen_pages` function). `constants.py:159` (`PAGE_RECALL_FLOOR = 0.90`). `constants.py:173` (`MAX_PAGE_ESCALATIONS = 5`). `pdf_judge.py:719-734` (over-cap path: `if len(flagged_entries) > MAX_PAGE_ESCALATIONS: ... verdict = "review"`). `pdf_judge.py:736-815` (per-page escalation loop, serial `await _escalate_page`). |
| **Affected gate** | D1, D11 |
| **Confidence** | 1.00 |
| **False-pass hypothesis** | None. |
| **False-fail hypothesis** | N/A. |

### F8. Aggregation: worst axis, min confidence, union of evidence

| Field | Value |
|---|---|
| **Severity** | INFO |
| **Claim** | `aggregate_adjudications` folds per-chunk results: most severe finding per axis (sorted by axis name, deterministic), severity-aware worst verdict, minimum confidence, union of evidence spans (deduped by axis/quote/reason). |
| **Evidence** | `chunking.py:226-292` (`aggregate_adjudications`). `chunking.py:250-256` (per-axis worst finding). `chunking.py:258-259` (worst verdict, min confidence). `chunking.py:268-275` (union of evidence, dedup by key tuple). Tests: `test_tapetum_llm.py:1218-1553` (major wins, minor folds, empty, order invariance, severity tie determinism). |
| **Affected gate** | D1 (determinism) |
| **Confidence** | 1.00 |
| **False-pass hypothesis** | None; deterministic sorting confirmed by tests. |
| **False-fail hypothesis** | N/A. |

---

## Summary Verdict

The cascade topology is well-structured: a two-tier text cascade with three observable escalation triggers, H2-boundary chunking with serial triage, and a per-page screen with capped LLM escalation in the PDF lane. Serial-within-paper is enforced by sequential `await` calls and `for` loops. Concurrent across-paper is bounded by the CLI's semaphore. **No issues found. D1 compliance is solid.**
