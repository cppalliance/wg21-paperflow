# r13 - Cross-repo survey: does ANYONE verify table cells source-vs-output?

**Verdict:** usable (+ 6/31 clones implement real cell-content-vs-ground-truth grid comparison, all offline/benchmark-only; whisker's missing table-cell compare is ecosystem-normal, not an outlier gap)
**Confidence:** high

## Findings

### Survey table (31 clones under `packages/whisker/research/repos/`)

| Repo | Cell-content vs GT grid? | Evidence |
|---|---|---|
| camelot | **yes** | `bench/_metrics.py:24-33` (`simple_teds`: row-major cell-text `SequenceMatcher` over pred/gt grids); `bench/benchmark_icdar.py:41-66` (ICDAR `-str.xml` `<cell><content>` → grid, scored via `score()`) |
| docling | **partial** | `tests/test_backend_html.py:224` (full `export_to_markdown()` golden string compare); `257-259` (row/col counts only). No per-cell GT grid metric in tests or CI |
| Dolphin | **no** | README mentions only; no eval code |
| firecrawl | **no** | `rg TEDS` hits are unrelated identifiers (redis/deep-research), not table metrics |
| grobid | **no** | `TableTrainer.java` trains/evaluates CRF field tagging on TEI corpus; no conversion-output cell grid vs source |
| html-to-markdown-go | **partial** | `plugin/table/table_test.go:14-27` (golden full-markdown file diff, not explicit cell-grid scorer) |
| html-to-markdown-py | **partial** | `crates/html-to-markdown/tests/tier1_tables_test.rs` (golden markdown fixtures, document-level) |
| html2text | **no** | No table eval |
| img2table | **no** | `src/img2table/tables/metrics.py` (CV char-length/line-sep for detection); no GT cell content compare |
| langextract | **no** | No table eval |
| markdownify | **no** | No table eval |
| marker | **yes** | `benchmarks/table/scoring.py:43-48,92-106` (APTED TEDS with Levenshtein on `<td>` cell token lists); `benchmarks/table/table.py:21-25` (pred vs `gt_table` HTML) |
| markitdown | **partial** | `tests/test_pdf_tables.py:14-37,74-94` (substring presence + row/col consistency in output; no source-derived cell grid) |
| mdream | **no** | No table cell eval |
| MinerU | **no** | Table recognition/merge code only; no GT cell-content scorer |
| node-html-markdown | **no** | No table eval |
| nougat | **partial** | `metrics.py:39-43,63-83` (table-stratum set-F1 on LaTeX `tabular` blocks; order-invariant text, not indexed cell grid) |
| olmocr | **yes** | `olmocr/bench/tests.py:342-480` (`TableTest`: fuzzy match target cell text + verify up/down/left/right/heading neighbor cell strings in parsed md/html grids via `table_parsing.py`) |
| opendataloader-bench-tmp | **yes** | `src/evaluator_table.py:68-83,138-162,222-247` (APTED TEDS with `_normalize` + Levenshtein on joined cell text; separate structure-only vs content modes) |
| opendataloader-pdf | **no** | Converter/processor only; cell eval lives in bench clone |
| pandoc | **no** | No table eval |
| PDF-Extract-Kit | **no** | No table eval |
| pdf-to-markdown | **no** | No table eval |
| pdfplumber | **no** | No table eval |
| PyMuPDF | **no** | `tests/test_tables.py:25-26` (regression vs pickled prior extracts, not source GT grid) |
| pymupdf4llm | **no** | No table eval |
| surya | **no** | No in-repo cell GT compare (external bench reporting only) |
| tabula-java | **no** | Extraction library; no GT cell scorer |
| tabula-java-tmp | **no** | Same |
| turndown | **no** | No table eval |
| unstructured | **yes** | `unstructured/metrics/table/table_alignment.py:59-179` (`get_element_level_alignment`: per-cell `content` match by row/col index + `compare_contents_as_df`); `table_eval.py:49-52,76-79` (`element_col/row_level_content_acc`) |

**Counts:** yes **6**, partial **5**, no **20** (of 31).

- [CRITICAL] Cell-content-vs-ground-truth grid comparison exists in **6/31** surveyed clones; **0/31** gate runtime conversion on an LLM that performs this check (consistent with baseline `00-baseline.md:82`: "0 of 31 surveyed document-conversion QA repos gate mechanically on LLM signals"). Impact: whisker's missing table-cell compare in `tapetum_llm` (`00-baseline.md:54-55`) is **not an outlier** — it matches ecosystem norms where cell-grid metrics live in offline benches, not advisory LLM lanes. Answer-class: **5**.

- [HIGH] The six **yes** repos all compare **predicted cell text at grid coordinates** (or TEDS tree nodes carrying cell tokens) against human/curated GT — not merely row/col counts or table detection F1. Evidence: camelot `simple_teds` over `_seq(grid)` (`bench/_metrics.py:20-33`); unstructured `compare_contents_as_df` on row/col-indexed DataFrames (`table_alignment.py:92-100`); opendataloader `CustomConfig.rename` Levenshtein on normalized cell strings (`evaluator_table.py:68-83`); marker APTED on `<td>` content tokens (`scoring.py:43-48`); olmocr neighbor-cell relational tests (`tests.py:412-468`). Impact: the P0 "table-cell compare" hypothesis is **ecosystem-validated** as a deterministic primitive, but **none** of these repos expect an LLM to spontaneously perform it during golden-PR review. Answer-class: **1**, **2**, **5**.

- [HIGH] **20/31** repos have **no** cell-content GT comparison at all; **5/31** are **partial** (golden full-document diff, substring presence, or block-level table F1 without indexed cell grid). Evidence: markitdown `validate_strings` / `validate_table_structure` (`test_pdf_tables.py:14-94`); docling markdown golden pairs (`test_backend_html.py:224`); nougat table set-F1 (`metrics.py:39-43`). Impact: expecting whisker's LLM lane alone to reach "100% golden verification" on table defects (PR #286 wrapped `SF`→`S`, `00-baseline.md:41-44`) mis-specifies the target relative to peer tooling. Answer-class: **5**.

- [HIGH] Where cell compare **does** exist, it is **benchmark/CI-scoped**, not routed under a unit budget like whisker's `MAX_UNIT_CHECKS=5` (`00-baseline.md:47-49`, `constants.py:223`). Evidence: marker `benchmarks/table/table.py:21-25` (batch TEDS on fintabnet); camelot `bench/benchmark_icdar.py` (offline ICDAR sweep); opendataloader `run.py` corpus means with committed floors (`thresholds.json`, per r08). Impact: portable pattern for whisker is a **deterministic lane gate** (TEDS or grid diff on poll-table pages), not expanding LLM unit checks. Answer-class: **2**, **5**.

- [MED] **Most portable implementation for whisker:** `unstructured/unstructured/metrics/table/{table_alignment,table_eval}.py` — explicit Deckerd cell dicts (`row_index`, `col_index`, `content`), table-level matching then **element-level content accuracy** (`table_eval.py:49-52`), plus `compare_contents_as_df` for column/row token ratios (`table_alignment.py:95-100`). Secondary: `opendataloader-bench-tmp/src/evaluator_table.py` (production-grade APTED TEDS with `_normalize` for `<br>`/whitespace, `167-171`) already cross-referenced in whisker redteam. Tertiary: camelot `bench/_metrics.py:24-33` (minimal grid `SequenceMatcher`, no apted dep). Impact: P0 table-cell compare should fork unstructured's indexed-cell model or opendataloader TEDS into **deterministic** `whisker/metrics` or `gates`, not `tapetum_llm/unit_judge`. Answer-class: **1**, **2**.

- [MED] olmocr `TableTest` (`tests.py:342-480`) is the closest **golden-PR-shaped** cell verifier (human-authored expected cell + neighbor relations, fuzzy thresholded), but it validates **parsed output structure**, not PDF geometry wrapped cells — would not catch PR #286's vertical wrap without encoding that rule in test JSON. Impact: useful for **spot-check fixtures** on dev-replay, not a substitute for PyMuPDF geometry + cell grid diff (`00-baseline.md:43-44`). Answer-class: **1**, **5**.

- [LOW] False-positive grep noise (firecrawl `TEDS` in unrelated TS, grobid `compareTo` in Java, PyMuPDF pickle regression) confirms keyword sweeps must be read at `file:line`, not match counts alone. Impact: prior persona r05's "empty clone" caveat is **stale** for unstructured (clone now populated with full `metrics/table/` tree); this survey re-verifies from live paths. Answer-class: **5**.

## False-pass hypothesis

PR #286 poll tables (`00-baseline.md:41-44`): even repos with **yes** cell compare (marker TEDS, opendataloader bench) score **offline** on curated GT HTML/markdown where wrapped header is already one cell string; none run post-tomd **source-text-layer geometry diff** on routed pages 8/9. Whisker deterministic lane already `pass` with QA 100 (`00-baseline.md:45`); adding only LLM units without importing camelot/unstructured-style grid compare would reproduce marker's benchmark-only blind spot (`r02-marker.md` finding on inference-time absence).

## False-fail hypothesis

Adopting opendataloader TEDS `_normalize` (`evaluator_table.py:167-171`) or unstructured whitespace-insensitive `compare_contents_as_df` without a shared WG21 golden vector would deterministic-fail papers whose only table delta is `<br>`/whitespace inside otherwise correct cells — same class as whisker `TEDS_FLOOR` formatting debates (`r02-marker.md` false-fail hypothesis).

## What would change my mind

Live `rg` in **≥3 additional** surveyed clones (beyond the current six) showing **runtime** (not bench-only) cell-grid compare wired into conversion QA gates **or** an LLM verifier prompt that receives an explicit source-derived cell grid packet and is measured to recall PR #286/#295 blockers — would refute the "cell compare is genuinely rare" conclusion and downgrade answer-class **5** weight.
