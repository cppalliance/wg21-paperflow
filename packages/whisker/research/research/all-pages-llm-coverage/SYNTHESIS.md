# All-Pages LLM Coverage (golden-review mode) - Research Synthesis

> **v2 correction (2026-07-22, 40-agent exhaustive wave, see v2/VERIFICATION.md):** the claim "no surveyed repo runs an LLM per page for verification" holds for PRODUCTION pipelines but is REFUTED for eval harnesses: marker's `benchmarks/overall/scorers/llm.py` (`LLMScorer`) sends each rendered PDF page image plus the already-produced markdown to Gemini for structured fidelity scores. That is direct prior art for our --all-pages review mode (a golden review IS an offline eval). Also corrected: olmocr-bench's BaselineTest auto-injection is per-PDF (page 1), not per-page; our transplant must inject a per-page baseline check explicitly. All other findings below were re-verified line by line and stand.

**Verdict band:** usable-with-conditions   **Confidence:** high
**Decision vs our codebase:** adopt-partially - build `--all-pages` as an opt-in, fail-closed review-mode defect finder; keep deterministic lanes as the gate; do NOT chase extraction-pipeline parity.

## Summary

- **The operator's comparison is a category error, but the complaint is still right.** docling, langextract, MinerU, Dolphin, nougat, surya run models per page/chunk for EXTRACTION (the model produces the output, so touching every page is free); marker's `--use_llm` is block-selective refinement. **No surveyed repo runs an LLM per page for VERIFICATION.** The strongest verification prior art, olmocr-bench and ParseBench, is exhaustive-per-page but deliberately DETERMINISTIC (olmocr `benchmark.py:246-251` aborts if any (pdf, page) lacks a test; ParseBench authors explicitly reject LLM-as-judge). The only exhaustive LLM-judge precedent is table-scoped (pdf-parse-bench, judge r=0.93 vs TEDS r=0.68 after 1,500+ human ratings). So "docling does all pages with LLMs" is not a thing to copy - but the demand "in a golden review, every page must be individually examined" is legitimate on its own terms.
- **Why we "verkacken" today - three verified defects, one of them a lie in the docs.** (1) `--exhaustive-units` and `--inspect` are silently dead on the PDF lane: `cli.py:1186-1187` wires `exhaustive` only into the text lane; the PDF branch `cli.py:1120-1127` never passes it and `judge_pdf_extraction` cannot receive it. (2) Even if wired, exhaustive means "all ROUTED units": `unit_judge.py:287-288` returns None when the router finds no risk signals, and `pdf_judge.py:831-836` then reports `coverage_complete=True` with zero pages checked - fusion trusts that (`fusion.py:190-195`). (3) pr-golden-review.md step 3 documents behavior that does not exist for PDFs. P1068R11 result: 5/15 pages checked.
- **Review mode invalidates the fleet-mode noise objection.** The prior research (research/per-page-judging/SYNTHESIS.md) killed per-page LLM judging with doc-level noise math `1-(1-p)^n` at corpus scale. In review mode a human triages findings, so cost scales linearly (n*p ~ 0.3-2 spurious findings per 33-page paper), the pod is billed hourly, and wall-clock is 5-17 min per paper. The economics and noise math both flip. The prior synthesis's design stays correct for the FLEET default; --all-pages is a REVIEW-mode overlay.
- **All-pages finds defects; it cannot certify correctness.** LLM-judge TNR is <25% (arXiv 2510.11822); empty-defect passes are the cheapest false pass (persona 30); cross-page reordering, duplication, image-only content, and rubber-stamping survive per-page presence checks (persona 22). A clean all-pages run must be reported as "no additional findings (advisory)", never "verified correct". The deterministic gates and the manual fidelity diff remain load-bearing.

## Top findings (ranked)

- [CRITICAL][NOW] PDF lane silently ignores `--exhaustive-units`/`--inspect`. Evidence: cli.py:1186-1187 vs cli.py:1120-1127. adopt? fix in the --all-pages change, plus a loud error/warning for no-op coverage flags.
- [CRITICAL][NOW] `coverage_complete=True` when zero units were checked (empty router). Evidence: unit_judge.py:287-288, pdf_judge.py:831-836, fusion.py:190-195. adopt? all-pages mode must compute coverage against page_count, and fusion/sidecar must distinguish "nothing flagged" from "all pages checked".
- [CRITICAL][NOW] Fingerprint encodes no coverage mode; `--exhaustive-units` already has a cache-poisoning hole today (behavior changes, fingerprint does not: cli.py:543-565). adopt? add a coverage_mode field to the fingerprint, not just a _LANE_VERSION bump.
- [HIGH][NOW] Unit-check prompt contract is a subset of the escalation contract: missing the cross-page "anywhere in the markdown" rule (pdf_judge.py:238-241) and the TOC-leak-inverse/wording/comment sanctions (pdf_judge.py:152-189 vs unit_judge.py:66-76). Unfixed, every cross-page reflow and page-1/TOC page is a guaranteed false finding in all-pages mode. adopt? yes - all-pages prompt = full contract + neutral full-audit instruction.
- [HIGH][NOW] Fixed timeout formula (cli.py:140-157) kills any run needing >5 unit calls. adopt? page-count-aware budget, shape `base + n * UNIT_CHECK_TIMEOUT_SECONDS` (persona 23: ~6,420 s worst-case at n=40).
- [HIGH][NOW] olmocr-bench's fail-closed coverage audit is the pattern to copy: abort/flag when any (pdf, page) lacks a check; auto-inject a baseline check per page. Evidence: olmocr benchmark.py:241-251. adopt? yes - it is the only true all-pages verification prior art.
- [HIGH][NOW] Operator cannot verify coverage from the report: inspect_report.py renders none of page_screen/page_count/page_escalations that pdf_judge.py already writes. adopt? per-page coverage table (page, tokens, recall, checked, findings) + an explicit "N/N pages checked" line.
- [MED][NOW] Test suite could not have caught the unwired flag: test_tapetum_llm.py mocks judge_pdf_extraction without asserting kwargs. adopt? TDD the CLI-to-pdf_judge wiring explicitly.
- [MED][NOW] Timeout tombstone loses partial coverage audit (timeout at page 30/40 persists nothing of the enumerated progress; debug survives via cli.py:1129-1151). adopt? persist partial unit_coverage in the tombstone path, verdict review.
- [MED][LATER] Anti-rubber-stamp guard: n near-identical prompts with uniform empty-defect passes and no variance is itself a signal (judge TNR <25%). adopt? later - record per-page confidence in the sidecar now, gate on it once calibration data exists.
- [LOW][LATER] nougat's in-band `[MISSING_PAGE_FAIL:n]` sentinel and surya's typed per-page result objects are the cleanest per-page failure-surfacing patterns for the sidecar schema. adopt? shape inspiration only.

## Bugs / edge-cases in OUR code (surfaced by the comparison)

- cli.py:1120-1127 - coverage flags dead on the PDF lane (the headline bug).
- cli.py:543-565 - fingerprint blind to coverage mode; pre-existing incremental cache hole for `--exhaustive-units` on the text lane.
- pdf_judge.py:831-836 + fusion.py:190-195 - vacuous coverage_complete=True.
- unit_judge.py:66-76 - slimmed contract guarantees false fails on clean pages once unrouted pages are checked.
- .cursor/commands/pr-golden-review.md step 3 - documents `--inspect` as implying exhaustive unit checks; false for PDFs; must be corrected to `--all-pages` semantics once shipped.

## Top portable detail

olmocr-bench's coverage gate: evaluation refuses to score when any (pdf, page) has no test, and auto-injects a per-page baseline test otherwise (benchmark.py:241-251). Transplanted: `--all-pages` builds required = every `page:N` from the extractor, verifies checked-set equality against page_count after the run, and fail-closes the verdict on any gap. That single invariant is what separates "we ran some checks" from "every page was examined".

## Flip conditions

- If a labeled holdout later shows the all-pages unit checks produce >50% sanctioned-noise findings per paper even WITH the full contract, demote all-pages to page-screen + escalation only (the current hybrid) and mark the mode experimental.
- If pod economics change (per-token billing), re-run persona 23's arithmetic; the review-mode cost argument weakens.
- If a per-page VLM verification lane ships (rendered page image vs markdown), the text-layer all-pages mode becomes the cheap tier of a two-tier review, not the whole answer (images stay invisible until then).

---
Sources: local clones at packages/whisker/research/repos/ (olmocr f7cfe4c, docling fbd39b8, langextract 0dff547, marker ef16c2c, MinerU 3e60291, Dolphin befa5da, nougat 5a92920, surya 11d1884, grobid 4a5aadf, unstructured f6eea75, opendataloader ddd3d8e), workspace @ 51cb704, baseline 00-baseline.md, 2026-07-22.
Web: 05-web.md (25 finding cards, 25 unique URLs).
Personas: 25 (10-34, composer-2.5-fast) + 5 web foragers = 30 Composer subagents. Meta-review: opus-A (claim verification), opus-E (steelman balance) by orchestrator.
Prior corpus: research/per-page-judging/ (2026-07-14), findings re-verified not re-filed.
