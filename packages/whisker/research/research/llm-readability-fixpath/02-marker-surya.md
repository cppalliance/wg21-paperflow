# 02 - marker+surya

**Verdict:** usable-with-conditions — marker and surya are strong structural-benchmark references (fuzzy GT alignment, TEDS, HF datasets, degeneracy guards) but neither verifies LLM comprehension; our fix-path implementation (`facts.py`, `readback.py`, `tables.py`, `corpus_tools.py` per `00-baseline.md`) is strictly better for the compared concern.
**Confidence:** high

## Findings

- [CRITICAL] Neither repo ships discrete fact-assertion comprehension QA (`present`/`absent`/`order`/`table`/`math`); marker gates corpus-mean fuzzy resemblance and TEDS only (`marker/benchmarks/verify_scores.py:9-22`, CI `marker/.github/workflows/benchmarks.yml:28-35`); surya gates smoke CLI execution with no output scoring (`surya/.github/workflows/scripts.yml:29-38`). Impact: both would green-light token-preserving semantic corruption that whisker Lane 3 catches; our `facts.py:419-471` typed assertions + `checked: verified` gate (`facts.py:84`, `00-baseline.md:19-21`) are the only in-repo comprehension layer among the three.

- [HIGH] Marker’s primary scorer is GT-block fuzzy alignment blended with Kendall-τ order, not fact recovery (`marker/benchmarks/overall/scorers/heuristic.py:25-40`, `:49-71`, `:77-82` `partial_ratio_alignment` cutoff 70). Whisker wins on comprehension: `facts.py` tests human-verified claims independently of a single reference markdown (`facts.py:17-23`). Marker wins on bulk fidelity regression: length-weighted block scores + order in one number (`heuristic.py:35-40`) localize regressions better than corpus-mean facts alone. Impact: marker is Lane 2-class (same family as whisker `bench`/`metrics.py`); our Lane 3 is orthogonal and strictly stronger for “can an LLM recover facts.”

- [HIGH] Marker optional LLM judge compares page image + markdown holistically (`marker/benchmarks/overall/scorers/llm.py:15-51`, `:108-134` returns `response["overall"]`); registered but not CI-default (`marker/benchmarks/overall/registry.py:11-14`, `overall.py:93`, `benchmarks.yml:30` runs heuristic only). No blind Q&A from markdown alone, no span grounding, no adversarial corrupt control. Whisker `readback.py:106-177` generates questions without embedding answers (table blindness fix at `:138-158`), evaluates deterministically (`:180-205`), and ships `--corrupt` (`:284`, `:297-313`). Impact: marker LLM judge is subjective fidelity reporting; our readback is a methodology-controlled comprehension probe (37/37 live per `00-baseline.md:50-52`).

- [HIGH] Surya in-repo QA is smoke + geometry only: table test asserts row/col/cell counts, never cell text (`surya/tests/test_table_rec.py:4-25`); reading-order test checks `>= 0` only (`surya/tests/test_recognition.py:14-15`); OCR health is garbled/good binary (`surya/tests/test_ocr_errors.py:1-15`). Public quality numbers cite external olmOCR-bench fact assertions (`surya/README.md:378-408`) with no harness in repo. Impact: surya’s published comprehension story is borrowed from allenai; whisker `facts.py` implements that methodology natively and gates CI (`00-baseline.md:46-47`, `test_comprehension_corpus.py`).

- [MED] Table verification diverges by lane: marker table bench uses HTML-tree TEDS (`marker/benchmarks/table/scoring.py:92-108`, `table.py:21-25` loads `datalab-to/fintabnet_bench_marker`); whisker already ports the same TEDS family for Lane 2 (`whisker/metrics.py:14-20`). Lane 3 table facts use cell-neighbor checks on pipe + HTML grids (`whisker/tables.py:44-135`, `facts.py:341-406`) — a direct “row X, column Y reads what?” test TEDS cannot express per-cell without a full GT HTML tree. Impact: adopt TEDS as aggregate fidelity axis (already done); do not replace neighbor facts with TEDS for comprehension — complementary, not substitutable (`00-baseline.md:25-28`).

- [MED] Corpus authoring: marker loads HF datasets with `classification` strata (`marker/benchmarks/overall/overall.py:37-38`, `:67-71`, default `datalab-to/marker_benchmark:90`); table path uses `datalab-to/fintabnet_bench_marker` (`table.py:31`, `:49`). Surya smoke uses wget zip + one PDF (`scripts.yml:25-28`). Whisker `corpus_tools.py:70-139` stratifies paperstore by structural heuristics (tables/math/code/footnotes/images) and drafts `.facts.jsonl` scaffolds (`:145-259`) with explicit `checked: draft` provenance (`:149-150`). Impact: marker/surya scale GT via published HF sets; whisker scales comprehension authoring locally with human blessing — better provenance for Lane 3, weaker volume.

- [LOW] Marker unit tests use substring presence anchors on one fixture PDF (`marker/tests/converters/test_pdf_converter.py:14-28`) — proto-`present` facts without JSONL typing or verified gate. Whisker already promoted this pattern to verified facts (`00-baseline.md:37-40`). Impact: marker anchors are regression smoke, not comprehension corpus.

- [LOW] Failed benchmark samples are dropped from marker averages (`marker/benchmarks/overall/overall.py:72-77`); `verify_table_scores` divides by `len(data)` not `len(data["marker"])` (`verify_scores.py:20`). Whisker vacuous-green gate and missing-pid hard fail are stricter (`00-baseline.md:16-18`). Impact: marker CI can hide collateral damage; our guard design is more conservative.

## False-pass hypothesis

Marker heuristic + TEDS green when GT fuzzy blocks align but a table cell’s right neighbor is swapped: `heuristic.py:77-82` scores block resemblance, `scoring.py:92-108` scores whole-table tree distance — neither asserts “cell Alice, right neighbor = New York.” Whisker `facts.py:373-406` neighbor check would fail. Surya `test_table_rec.py:22-25` would pass (geometry only) even if OCR returned scrambled text in every cell.

## False-fail hypothesis

Whisker `facts.py` table neighbor check fails when the same cell value appears in multiple tables and `table_heading` is omitted — we fixed decoy-table first-match via all-occurrence search (`facts.py:376-404`), but ambiguous headings can still false-fail. Marker TEDS on a full GT HTML table (`scoring.py:92-108`) would pass if only non-adjacent cells drift. Neither surya nor marker would false-fail here; they simply would not test the neighbor relation.

## Adoption candidate

**`marker/benchmarks/overall/scorers/clean.py:38-76` `MarkdownCleaner.normalize_markdown`** (pandoc round-trip canonicalization before diff/scoring). Highest leverage for Lane 2 guard false regressions (formatting-only drift). **License: GPL-3.0** (`marker/LICENSE:1-6`) — blocks direct port into BSL whisker; reimplement the idea with documented pandoc subprocess or negotiate license. License-compatible alternative: **`surya/surya/recognition/__init__.py:81-108` `_detect_repeat_loop`** (Apache-2.0, `surya/LICENSE:1-4`) as a reference-free degeneracy gate complementing `facts.py:auto_baseline_checks` (`facts.py:631-672`).

## What would change my mind

A committed marker or surya module with olmOCR-bench-style deterministic `present`/`absent`/`order`/`table`/`math` assertions gated in CI (not README links to external eval), showing per-item pass/fail JSONL and a blind markdown-only LLM Q&A harness with leak prevention — i.e., parity with whisker Lane 3 + `readback.py` as shipped in `00-baseline.md`.
