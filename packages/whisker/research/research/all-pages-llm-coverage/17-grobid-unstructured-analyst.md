# 17 - grobid-unstructured-analyst

**Verdict:** usable-with-conditions — both repos offer strong deterministic coverage-accounting patterns (per-unit status, dual recall axes, tiered fuzzy gates, fail-closed corpus diff) but neither certifies per-page verification; adopt their audit mechanics for `--all-pages` sidecar fields and pre-LLM screens, not their extraction-time "all pages touched" assumption.
**Confidence:** high

## Findings

- [CRITICAL] Neither GROBID nor Unstructured implements per-page verification coverage. GROBID end-to-end eval scores whole-document TEI fields per article (`EndToEndEvaluation.java:563-640`); Unstructured text-extraction metrics concatenate source/output into document-level clean concatenated text and emit one `cct-accuracy` + `cct-%missing` row per file (`evaluate.py:434-435`, `text_extraction.py:160-203`). Impact: they are prior art for **deterministic QA sidecars**, not for proving an LLM judged every page; our `--all-pages` mode must add an explicit `checked_pages == page_count` gate they lack.

- [HIGH] Unstructured's dual-axis row shape (`cct-accuracy` + `cct-%missing`) catches content loss that a single similarity score misses: `%missing` is bag-of-words recall from source, penalizing absent words without penalizing duplication (`text_extraction.py:160-203`, `evaluate.py:434-435`). Impact: portable to sidecar audit as paired fields per `page:N` unit (token recall + percent-missing) beside the LLM verdict; mirrors our existing `PAGE_RECALL_FLOOR` screen in `00-baseline.md`.

- [HIGH] GROBID runs four parallel deterministic matchers on normalized text — strict, soft (punctuation-stripped), Levenshtein pass if `(max_len - dist)/max_len >= 0.8`, Ratcliff-Obershelp pass if `>= 0.95` — with fixed constants at `EndToEndEvaluation.java:66-67` and scoring at `:1126-1160`. Impact: portable tiered pre-LLM gate; formatting-only drift downgrades to advisory instead of burning serial LLM unit checks.

- [HIGH] GROBID consolidation models partial failure without aborting the document: items stay `status="extracted"` by default, flip to `"consolidated"` only after external lookup + optional Ratcliff post-validation (`Consolidation.java:43-44`, `:375-402`, `:493-502`); success/failure counted via `ConsolidationCounters` (`ConsolidationCounters.java:10-39`). Impact: direct template for sidecar per-page status enum (`checked`, `skipped_low_tokens`, `routed_only`, `timeout`, `error`) plus aggregate counters in `PdfJudgeResult`.

- [MED] Unstructured stamps `page_number` on element metadata for PDF/HTML/DOCX/PPTX (`elements.py:200-201`) and uses it for page-scoped overlap QA (`utils.py:576-596`) and chunk boundary detection (`chunking/base.py:1841-1874`). Impact: portable grounding for page-scoped deterministic units without LLM; does not prove every physical page emitted elements — a blank page may have no metadata footprint.

- [MED] Unstructured partition fallbacks degrade on partial upstream failure — PDF text extraction exceptions are logged and skipped (`pdf.py:326-328`), strategy cascades hi_res→ocr_only→fast when dependencies missing (`strategies.py:58-70`), complex PDFs force hi_res without fast pre-pass (`pdf.py:304-308`) — but no run artifact records which pages used which path. Impact: fallback pattern is useful for extraction robustness; for review mode, any fallback must be logged in sidecar or it becomes a silent false-pass vector.

- [MED] GROBID eval treats missing gold/tool output as warn-and-continue (skip directory with console warning at `:590-632`), reports corpus-level PDF parse failures explicitly (`Benchmarking-pmc.md:27`), and tracks instance-level all-fields-correct counts separate from field micro-F1 (`Benchmarking-pmc.md:98-110`, `EndToEndEvaluation.java:1174-1178`); both-empty fields are skipped (`:1420-1423`). Impact: portable fail-closed variant for `--all-pages`: require instance-level pass on every non-empty page, skip empty pages under token floor, fail run if any expected page lacks a check record.

- [LOW] Unstructured CI gates committed metric trees with zero-tolerance `diff -ru` and optional `OVERWRITE_FIXTURES` refresh (`check-diff-evaluation-metrics.sh:46-73`), plus output file-count invariant (`check-num-files-output.sh:19-22`). Impact: golden-review guard pattern, not runtime coverage; useful for sidecar schema regression tests once audit fields are committed.

## False-pass hypothesis

A 15-page WG21 PDF where pages 2–14 lose headings but page 1 is dense: Unstructured-style document-level `cct-%missing` can stay below threshold because one page's bag-of-words dominates the aggregate (`text_extraction.py:189-203`), and GROBID instance-level strict recall is only 10.55% on PMC anyway (`Benchmarking-pmc.md:107`), so most partially wrong documents still pass field-level fuzzy tiers. An `--all-pages` sidecar that only stores corpus-level metrics without per-page rows would inherit this blind spot.

## False-fail hypothesis

GROBID strict matching fails on punctuation/reflow that passes Levenshtein tier (`EndToEndEvaluation.java:1433-1473` vs `:1126-1134`); Unstructured CI fails on any byte change in committed TSV metrics (`check-diff-evaluation-metrics.sh:56-73`). A golden review that treats strict deterministic failure as blocking without a secondary fuzzy tier would false-fail benign markdown normalization.

## What would change my mind

A post-run artifact in either clone asserting `|{page_number from outputs}| == pdf_page_count` with a hard exit code on mismatch — grep shows no such certificate today; only element-level page metadata and document-level eval aggregates exist.
