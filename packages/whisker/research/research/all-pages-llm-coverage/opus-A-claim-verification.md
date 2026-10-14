# opus-A - Claim re-verification (orchestrator, against code)

Every decision-critical persona claim re-checked against the working tree at 51cb704. Personas 10-19 (repo analysts) were spot-checked against 05-web.md cross-references; personas 20-34 (our-code auditors) were re-verified line by line where the claim is load-bearing.

## Verified (reproduced against code)

1. **Unwired exhaustive on the PDF branch** (personas 20, 27, 33). `cli.py:1186-1187` passes `exhaustive=args.exhaustive_units or args.inspect` only inside the text-lane `adjudicate_paper` call; the PDF branch `cli.py:1120-1127` calls `judge_pdf_extraction(pid, backend, judge_agent, debug_log=...)` with no exhaustive parameter, and `judge_pdf_extraction` has no such parameter to receive. No warning is emitted. CONFIRMED.
2. **"Complete because nothing was flagged" masquerades as full coverage** (personas 20, 26). `unit_judge.py:287-288` returns `None` when `risk_signals` is empty; `pdf_judge.py:831-836` pre-fills `unit_coverage = {"coverage_complete": True, ...}` and only overwrites it when unit checks ran. CONFIRMED.
3. **Fusion trusts that default** (persona 26). `fusion.py:190-195`: review is forced only when `coverage_complete is not True` or unchecked/failed lists are non-empty. A capped-or-empty run and a true all-pages run are indistinguishable to fusion today. CONFIRMED.
4. **Fingerprint has no coverage-mode key** (persona 24). `_compute_fingerprint` (`cli.py:543-565`) hashes md, source, prompt, model, `_LANE_VERSION`, lane, schema, ideal fields. Nothing encodes exhaustive/all-pages. Consequence verified: `--exhaustive-units` ALREADY changes text-lane behavior without changing the fingerprint, so an incremental run can serve a capped sidecar to an exhaustive request today. CONFIRMED (pre-existing bug, not hypothetical).
5. **Unit-check prompt contract is a slimmed subset of the escalation contract** (personas 21, 25). `_UNIT_CONVERSION_CONTRACT` (`unit_judge.py:66-76`) has 6 one-line sanctions. The PDF contract `_CONVERSION_CONTRACT` (`pdf_judge.py:152-189`) additionally carries: the TOC-leak INVERSE rule, the tomd/tapetum HTML-comment sanction, the wording-markup color caveat with review-cap instruction, and PAGE_JUDGE's cross-page presence rule ("counts as present if it appears ANYWHERE in the markdown, in any order", `pdf_judge.py:238-241`). The unit prompt says "THIS UNIT ONLY" with no anywhere-rule, so cross-page reflow at page boundaries is a structural false-fail in all-pages mode. CONFIRMED.
6. **Fixed timeout kills all-pages runs** (persona 23). `cli.py:140-157` budgets `(1 + MAX_UNIT_CHECKS)` unit calls; with MAX_UNIT_CHECKS=5 and UNIT_CHECK_TIMEOUT_SECONDS the budget cannot cover n=15..40 required units. Formula must become page-count-aware. CONFIRMED (formula read directly; exact seconds per persona 23's arithmetic, shape verified).
7. **Category error in the operator comparison** (persona 19 + web cards). docling VLM pipeline, langextract chunks, MinerU/Dolphin/nougat/surya are per-page/per-chunk EXTRACTION; marker is block-selective REFINEMENT; none is per-page VERIFICATION. olmocr-bench and ParseBench, the strongest verification prior art, are exhaustive-per-page but DETERMINISTIC, explicitly rejecting LLM-as-judge. The only exhaustive LLM-judge precedent found is table-scoped (pdf-parse-bench, arXiv 2603.18652). CONFIRMED via 05-web.md plus persona code citations.

## Accepted on persona evidence (not independently re-run)

- Persona 23's exact wall-clock numbers (5-17 min typical for n=15-40) and the recommendation `1620 + n*120` s. Shape verified, arithmetic trusted.
- Persona 32's claim that `content_recall` is multiset token presence (`metrics.py:376-393`), making page-local structure errors invisible to the screen at recall >= 0.90. Consistent with constants.py docs; medium confidence, flagged for the implementer to re-read.
- Persona 29/operator finding that `inspect_report.py` never renders `page_screen`/`page_count`/`page_escalations`. Not re-read; the implementer must verify when touching the report.
- langextract `suppress_parse_errors=True` default (persona 13 + release notes card): silent chunk loss. Two independent sources, accepted.

## Downgraded / nuanced

- Persona 21's claim that sanctioned page-1/TOC quotes "still force review via evidence_uncertain": plausible mechanism but not re-traced end-to-end; treat as a test case to write, not an established fact.
- Persona 31's "all-pages is mostly theater": the deterministic screen DOES touch every page, but it measures token presence only; "theater" overstates it for the structure/qualifier defect classes the unit prompt can see. Rebalanced in opus-E.
