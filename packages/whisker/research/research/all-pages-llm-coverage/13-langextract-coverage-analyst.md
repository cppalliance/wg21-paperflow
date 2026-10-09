# 13 - langextract-coverage-analyst

**Verdict:** usable-with-conditions — langextract guarantees every text chunk receives an LLM infer() call, but default `suppress_parse_errors=True` silently drops failed chunks with no completion certificate; adopt the chunk/char-offset iteration model inverted to fail-closed, not the silent-loss default.
**Confidence:** high

## Findings

- [CRITICAL] Langextract does not issue any completion or coverage certificate; progress tracks characters processed during iteration only, with no post-run audit that all chunks succeeded or that document char ranges are fully represented in outputs. Evidence: `langextract/progress.py:271-328` (stats are display-only); `langextract/annotation.py:358-438` (increments `chars_processed` per chunk, never compares to expected total). Impact: the operator belief that langextract "guarantees all-pages coverage" is unsupported; a run can finish with silent gaps and still print "Extraction processing complete" (`langextract/progress.py:122-124`).

- [CRITICAL] Default `extract()` sets `suppress_parse_errors=True`, so a chunk whose LLM output fails JSON/YAML parse or schema validation returns `[]` and the run continues. Evidence: `langextract/extraction.py:136-138,365`; `langextract/resolver.py:309-320` ("Skipping chunk: parse error" / "schema error" → `return []`). Impact: direct anti-pattern for our `--all-pages` review mode; we must fail-closed on any page/chunk judge failure, not swallow it.

- [HIGH] Chunk iteration is architectural and exhaustive over tokenized text: `_document_chunk_iterator` yields every `ChunkIterator` slice up to `max_char_buffer`, and each batch chunk gets `language_model.infer()`. Evidence: `langextract/annotation.py:118-160,348-392`; `langextract/chunking.py:343-506` (`SentenceIterator` walks all tokens until `StopIteration`). Impact: for EXTRACTION inference coverage (LLM sees every chunk), this is sound prior art; it does not map to PDF page boundaries and says nothing about verification quality per region.

- [HIGH] Empty model output aborts the document; this is the one fail-closed inference gate. Evidence: `langextract/annotation.py:399-402` raises `InferenceOutputError` when `not scored_outputs`. Impact: worth copying for our review mode (no silent skip on empty judge response), but it is narrower than full coverage — a non-empty but unparseable response passes with zero extractions when suppression is on.

- [HIGH] Multi-pass (`extraction_passes > 1`) re-runs the full chunk loop independently and merges with first-pass-wins on overlapping `char_interval`s; docs frame it as recall/sensitivity, not guarantee. Evidence: `langextract/annotation.py:46-84,447-528`; https://google-langextract-27.mintlify.app/concepts/chunking-strategy; `docs/examples/longer_text_example.md:154-158`. Impact: not a verification mechanism; later-pass findings in overlap regions are discarded, so merge logic must not be mistaken for exhaustive adjudication.

- [MED] `char_interval` grounding is per-extraction alignment to source text, not chunk-coverage proof; unalignable extractions retain `char_interval=None`. Evidence: `langextract/core/data.py:74-76`; `langextract/resolver.py:811-813,1016-1019,1021-1025`; https://google-langextract-27.mintlify.app/concepts/source-grounding. Impact: useful for citation anchoring in extraction pipelines, irrelevant as a page-level "was this region judged?" audit for golden review.

- [MED] Retries apply only to transient API errors at the provider layer, not to parse failures or missing extractions. Evidence: `langextract/providers/gemini.py:351-391` (`_is_retryable_error`, per-prompt retry loop); https://github.com/google/langextract/releases (per 05-web.md). Impact: retry budget does not recover silently dropped chunks; our sidecar must record per-page judge outcomes explicitly.

- [LOW] Langextract operates on flat text chunks, not PDF pages; the user's "all pages" framing is a category error when citing langextract as verification prior art. Evidence: `langextract/chunking.py:15-21` (sentence/token chunking); 05-web.md Q2 ("Recall improvement, not a coverage guarantee"). Impact: strengthens the baseline distinction between EXTRACTION coverage (trivially all chunks infer'd) and VERIFICATION coverage (LLM judges every page against output) — langextract is only weakly analogous to the former.

## False-pass hypothesis

A 40-chunk clinical note run with default `suppress_parse_errors=True`: chunk 17 returns valid JSON, chunk 23 returns `"I don't see any entities."` (unparseable). Test `test_mixed_chunks_valid_extractions_survive` (`tests/init_test.py:873-893`) confirms the run completes with partial extractions and no failure flag. Operator sees success; chunk 23's region was infer'd but produced zero retained output with only a log warning.

## False-fail hypothesis

Any single chunk returning empty `scored_outputs` raises `InferenceOutputError` and aborts the entire document (`annotation.py:399-402`), even if all other chunks succeeded — no partial-result mode for inference failures (unlike parse failures).

## What would change my mind

A post-run sidecar or result field listing expected chunk count, succeeded chunk count, and failed chunk `char_interval`s with a hard fail when `succeeded < expected` — none exists at SHA 0dff547 in the clone or docs.
