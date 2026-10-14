# 16 - Product-Decision-Skeptic

**Verdict:** usable-with-conditions — the olmOCR-style Lane 3 architecture is sound and the two-paper POC is honest engineering, but issue #254's fleet-scale claim ("converted output is actually LLM-readable: read -> understood -> correct") is not closed; what shipped is a methodology demo on 1% of the paperstore, not proof for ~200 papers.
**Confidence:** high

## Findings

- [CRITICAL] **Fleet LLM-readability is unproven; coverage is 2/~200 papers with selection bias.** Evidence: `00-baseline.md:77-79` (corpus = 2 members vs sighting run 196); `comprehension-poc-report.md:66-70` (P4182R0 chosen because it "converts close to 100%"). Impact: any statement that comprehension is "theoretically and practically confirmed" for the converted fleet overstates delivery; at best it is confirmed for two hand-picked, near-perfect conversions.

- [CRITICAL] **CI does not gate live converter output; it gates frozen snapshots.** Evidence: `test_comprehension_corpus.py:12-14` (substrate is committed `corpus/<pid>.expected.md`, "no backend, no data/"); `test_comprehension_corpus.py:62-63` (reads snapshot, not paperstore). Impact: regressions in `tomd` that only appear on the ~198 papers without corpus facts never trip Lane 3; the gate proves "facts hold on blessed markdown," not "today's convert is LLM-readable."

- [HIGH] **One-time read-backs license a narrow proxy claim, not general LLM comprehension.** Evidence: `P4182R0.validation.md:43-47` (3 blind runs, 8/8); `P4185R0.validation.md:53-54` (1 run, gpt-5.5-medium, 9/9); `P4182R0.validation.md:30-39` (8 questions map 1:1 to fact ids). Impact: the anchor shows "these 17 human-authored Q&A pairs are recoverable by 2–3 model contexts on 2 clean papers," not that deterministic facts equal downstream dissect/agora comprehension across models, prompts, or chunk boundaries.

- [HIGH] **Our 4 table facts (2 per paper) mostly avoid the TabVerse structural failure class.** Evidence: `facts.py:309-323` (locate cell by normalized exact string match, first-match-wins, then neighbor equality); `05-web.md:46-48` (TabVerse mean cell-lookup structural accuracy ~9.9%, row retrieval ~5.0%). Impact: facts like `tableA-gpu-coro-no` (`P4182R0.facts.jsonl:7`) give the cell anchor text "GPU device code (CUDA, SYCL)" rather than "row 3, column Coro"; this is a curated substring+neighbor test, not the coordinate-confusion regime where LLM table comprehension collapses. Sampling 2 such facts per paper does not stress the ~10% risk class from published benchmarks.

- [HIGH] **Lane 3 omits major risk axes that tapetum_llm already names but never gates.** Evidence: `00-baseline.md:80-83` (no `code`, `xref`, or `image-ref` fact types; tapetum adjudicates 7 axes); `CLAUDE.md:361-371` (tapetum "NEVER hard-fails, is never in the `whisker --gate` CI contract"). Impact: a conversion can pass all 17 verified facts while garbling code blocks or cross-references that dissect relies on; tapetum may flag them but 72 review→pass clears from the sighting run remain unaudited (`00-baseline.md:84-85`, `tapetum-sighting-run-2026-07-01.md:27-28`).

- [MED] **Scale gap vs the adopted benchmark (olmOCR) makes "we test comprehension" a category error at current corpus size.** Evidence: `05-web.md:18-20` (olmOCR: 7,010 test cases over 1,403 PDFs, 1,020 table tests on 188 table PDFs); baseline count 17 verified facts on 2 papers (`00-baseline.md:53-57`). Impact: we inherited the right *pattern* but not the *statistical power*; a WG21 stakeholder comparing to olmOCR/ParseBench (`05-web.md:74-78`, 169K deterministic rules) will read Lane 3 as aspirational infrastructure, not completed verification.

- [MED] **Read-back conclusions overreach their sample design.** Evidence: `P4182R0.validation.md:56-58` ("deterministic facts are a faithful proxy… gate may stand in for the LLM in CI"); `comprehension-poc-report.md:55-57` (same inference documented as one-time anchor). Impact: the inference is methodologically licensed only for the authored fact set on known-easy papers; extending it fleet-wide without holdout facts, multi-model replication, or adversarial strata is the exact claim-vs-delivery mismatch #254 was opened to prevent.

## False-pass hypothesis

A table-heavy WG21 paper passes `whisker --no-reference` because `unigram_coverage >= 0.85` (`CLAUDE.md:215-216`) while two platform-table cells swap values; no `<pid>.facts.jsonl` exists for that paper (`__main__.py:495-496`: only corpus members with facts files are checked), so Lane 3 never runs and the corruption reaches dissect unchanged.

## False-fail hypothesis

A readable conversion with a hand-verified `present` fact whose source phrase differs by one whitespace-normalization edge from `max_diffs: 0` default (`corpus/README.md:50-55`) fails the comprehension gate on an otherwise shippable paper; less likely than false-pass given current corpus size but possible as fact authoring scales.

## What would change my mind

A stratified comprehension corpus of at least 30 papers drawn from the ~200-paper fleet (multi-column tables, merged cells, display math, code-heavy, xref-dense—not near-100% converts), each with ≥10 verified facts including code/xref coverage, plus blind holdout read-backs on the production self-hosted model stack showing ≥90% fact-recovery macro rate *without* question-to-fact-id leakage, with CI failing any new convert whose facts regress against live `paperstore` markdown—not only frozen snapshots.
