# Cross-cutting verification patterns (31 converter repos)

Sweep date: 2026-07-06. Method: targeted grep + PowerShell `Select-String` over
`packages/whisker/research/repos/` (read-only; excludes `.venv`, `node_modules`,
ground-truth markdown content). One evidence anchor per repo per pattern row.

Baseline context: `research/llm-readability/00-baseline.md`, Q1/Q3 in `05-web.md`.
Whisker already has golden diff (Lane 1), structural NID/TEDS/MHS (Lane 2),
deterministic fact assertions (Lane 3, olmOCR-derived), and advisory tapetum_llm.

## Pattern × repo matrix

| # | Pattern | Repo hits (one `file:line` each) |
|---|---------|-------------------------------------|
| **1** | **QA / fact-assertion evaluation** (typed assertions, fixture expected-values, benchmark evaluators) | **olmocr** `olmocr/bench/tests.py:484` (`BaselineTest` + 5 other `TestType`s); **opendataloader-bench-tmp** `tests/test_evaluator_table.py:7` (`evaluate_table` + `assert approx`); **opendataloader-pdf** `CLAUDE.md:25` (NID/TEDS/MHS via external bench); **marker** `benchmarks/table/scoring.py:2` (TEDS table scorer); **camelot** `bench/_metrics.py:4`; **docling** `tests/test_backend_doclang.py:89` (`assert roundtrip_doc.export_to_markdown() == …`); **html2text** `test/test_html2text.py:191`; **langextract** `benchmarks/benchmark.py:16` (extraction quality suite); **markitdown** `packages/markitdown/tests/test_cli_misc.py:27`; **pymupdf4llm** `pdf4llm/tests/test_general.py:48`; **tabula-java** `src/test/java/technology/tabula/TableTest.java:7`; **tabula-java-tmp** (duplicate checkout, same anchor); **unstructured** `scripts/performance/benchmark_partition.py:12`; **grobid** `doc/benchmarks/Benchmarking-biorxiv.md:1`; **node-html-markdown** `benchmark/execute.js:105`; **mdream** `bench/bundle/src/string.ts:1600`; **firecrawl** `.github/scripts/eval_run.py:7` |
| **2** | **LLM-as-judge / LLM-based eval of own output** | **firecrawl** `apps/api/src/services/monitoring/search/run-defenses.test.ts:219` (`judgeEnabled` gates LLM judge on search results, not conversion); **langextract** `tests/extract_precedence_test.py:25` (OpenAI in extraction tests); **marker** `tests/services/test_service_init.py:7`; **markitdown** `packages/markitdown/tests/test_module_misc.py:30`; **olmocr** `olmocr/bench/miners/check_headers_footers.py:6` (LLM assists test *mining*, scorer stays deterministic); **docling** `tests/test_api_image_request.py:369`; **unstructured** `test_unstructured/documents/test_ontology_to_unstructured_parsing.py:23`. **Note:** no cloned converter repo gates markdown output with an LLM judge; olmOCR explicitly avoids it (Q1/Q3 web cards). |
| **3** | **Round-trip / property testing** (convert→parse→compare, idempotence) | **docling** `tests/test_backend_doclang.py:77` (`test_docling_document_doclang_roundtrip_from_groundtruth`); **html-to-markdown-go** `internal/tester/goldenfiles.go:14` (`enableRoundTrip` flag); **html-to-markdown-py** `crates/html-to-markdown/tests/compact_tables_test.rs:149`; **camelot** `tests/test_export.py:74`; **langextract** `tests/format_handler_test.py:232`; **opendataloader-pdf** `java/.../hybrid/ElementMetadataTest.java:129` (`roundTripDeserialization`); **unstructured** `test_unstructured/documents/test_elements.py:391`; **firecrawl** `apps/api/src/__tests__/nuq-fdb/core.test.ts:89`. **Property-based:** no converter-repo hits outside vendored `.venv` (hypothesis/quickcheck/fast-check absent in project test code). |
| **4** | **Output linting / markdown validity** (CommonMark compliance, broken-construct detection) | **html-to-markdown-py** `crates/html-to-markdown/tests/commonmark_compliance_test.rs:7` (full spec JSONL); **html-to-markdown-go** `converter/convert_test.go:9`; **opendataloader-pdf** `java/.../markdown/MarkdownGeneratorTest.java:123` (CommonMark §6.4 angle-bracket links); **mdream** `crates/core/tests/conversion.rs:322`; **turndown** `src/turndown.js:1` (CommonMark-oriented rules in converter source). No repo runs `markdownlint`/`remark-lint` on PDF-derived output. |
| **5** | **Self-reported extraction confidence** (per-element/table scores exposed to consumer) | **docling** `tests/test_options.py:548` (`doc_result.confidence.mean_grade`); **opendataloader-pdf** `java/.../hybrid/TriageProcessor.java:142` (`confidence` 0–1 on triage JSON); **opendataloader-pdf** `java/.../json/serializers/SerializerUtil.java:48` (element-level metadata incl. confidence); **marker** `marker/builders/line.py:83`; **MinerU** `mineru/backend/hybrid/hybrid_model_output_to_middle_json.py:22`; **img2table** `src/img2table/tables/borderless/tables/filter/model.py:121`; **camelot** `camelot/core.py:720`; **grobid** `grobid-core/.../BibDataSet.java:26`; **markitdown** `packages/markitdown-ocr/src/markitdown_ocr/_ocr_service.py:18`; **PDF-Extract-Kit** `pdf_extract_kit/.../visualizer.py:721` (layout detection confidence, not md output). |
| **6** | **Baseline sanity checks** (non-empty, repetition, garbled/unexpected scripts) | **olmocr** `olmocr/bench/tests.py:496` (`max_repeats` n-gram guard + `check_disallowed_characters`); **opendataloader-pdf** `verification/ci-verify.py:192` (empty-output vacuous-pass guard); **marker** `tests/builders/test_garbled_pdf.py:10` (`test_garbled_pdf`); **surya** `tests/test_ocr_errors.py:1` (`test_garbled_text` → label `bad`); **docling** `tests/test_backend_msword.py:212` (`assert len(all_text) > 0`); **camelot** `tests/test_network.py:179`; **markitdown** `packages/markitdown/tests/test_module_misc.py:330`; **olmocr** `olmocr/bench/miners/mine_headers_footers.py:168` (non-empty page checks). No repo hits for literal `mojibake` string; garbled/repetition coverage is sparse beyond olmOCR. |

### Repos with no conversion-relevant hit in any pattern row

Dolphin, nougat, pdf-to-markdown, markdownify, pandoc, PyMuPDF (generic pytest only),
pdfplumber (non-empty asserts only), html2text (pattern 1 only).

---

## Patterns whisker lacks entirely (ranked for WG21 paper markdown)

1. **Baseline sanity auto-checks on every page** (repeating n-grams, disallowed script sets): olmOCR `BaselineTest` is the only comprehension-adjacent guard; whisker Lane 3 facts do not catch degeneration loops or unexpected CJK/emoji injection.
2. **CommonMark output validity lint**: pipe-table link syntax, angle-bracket destinations, and fence integrity are untested post-tomd; only a few HTML converters test CommonMark compliance on *their* output.
3. **Per-element extraction confidence in consumer-facing markdown sidecars**: docling/opendataloader expose confidence for routing human review; whisker verdicts are paper-level, not per-table/per-formula.
4. **Round-trip idempotence** (internal doc model ↔ markdown ↔ re-parse): present in docling/html converters but absent from whisker/tpmd QA loop.
5. **Property-based / fuzz output testing** (hypothesis, fast-check): essentially zero across all 31 repos; whisker matches the field.
6. **LLM-as-judge gating of conversion output**: deliberately avoided by olmOCR/ParseBench; whisker already has advisory tapetum_llm (#277 conditions), so absence here is intentional, not a gap.

---

## Cross-cutting takeaways

- **Widespread:** golden/expected-value unit tests (pattern 1 lite) and benchmark directories with *structural* metrics (TEDS/NID/MHS via opendataloader-bench, marker TEDS, grobid TEI benchmarks).
- **Rare but high-value:** olmOCR-style typed fact assertions (pattern 1 full) and CommonMark compliance suites (pattern 4).
- **Absent as a field norm:** LLM-as-judge on own markdown output (pattern 2); property-based markdown fuzz (pattern 3).
