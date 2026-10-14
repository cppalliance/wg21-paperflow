# 06 - Performance-Scalability

**Verdict:** usable-with-conditions — LangExtract completes small demos quickly but its Annotator defaults (200-char chunks, fuzzy LCS per chunk, 10 parallel workers) make LLM and CPU costs scale linearly or super-linearly with document length unless every knob is retuned.
**Confidence:** high

## Findings
- [CRITICAL] Default `max_char_buffer=200` on `Annotator.annotate_documents` / `annotate_text` (`annotation.py:213,536`) forces one LLM call per ~200 source characters. Baseline: an 80k-char WG21 paper → `80000/200 = 400` inference calls per pass; our tapetum lane holds the whole paper in one request at `MAX_PAPER_MD_CHARS=500_000` (`whisker/tapetum_llm/constants.py:44`, `chunking.py:70-71`). The high-level `extract()` API defaults `max_char_buffer=1000` (`extraction.py:53`) and documents that smaller buffers increase call count (`extraction.py:95-96`), but direct Annotator use still lands on 200.
  Impact: call amplification is the dominant cost driver for long documents; default settings are ~400× our per-paper call budget and ~80× even the `extract()` default.

- [HIGH] Fuzzy fallback runs `_best_lcs_spans` at O(n·m²) time and O(m²) memory per unaligned extraction (`resolver.py:1293-1363`), invoked in a loop over every unaligned extraction after each chunk's LLM pass (`resolver.py:1038-1049`; chunk alignment entry `annotation.py:422-429`). With chunk size n ≈ 30–50 tokens (200-char buffer) and extraction length m, one fuzzy attempt is ~50·m² ops; E failed alignments × C chunks → O(C·E·n·m²). Issue #188 reports pathological fuzzy cost on large PDF markdown when few-shot examples are misaligned (https://github.com/google/langextract/issues/188).
  Impact: grounding is not "cheap post-processing"; misaligned examples or noisy model output turn alignment into a super-linear CPU wall that grows with both chunk count and extraction count.

- [HIGH] Default `max_workers=10` on Gemini/OpenAI providers (`gemini.py:129`, `openai.py:54`) fans out concurrent realtime API requests when `batch_length>1`. `extract()` ships `batch_length=10` + `max_workers=10` (`extraction.py:57-58`), opening up to 10 in-flight calls per batch. Issue #50 documents `429 RESOURCE_EXHAUSTED` at default settings; maintainer workaround is `max_workers=3` (https://github.com/google/langextract/issues/50). Annotator's own `batch_length=1` default (`annotation.py:214`) avoids intra-batch parallelism but does not protect callers of `extract()`.
  Impact: throughput tuning and rate-limit failures are coupled; raising batch_length for speed trades 429 storms unless workers are manually capped.

- [HIGH] `extraction_passes>1` re-runs the entire chunk → infer → align pipeline once per pass (`annotation.py:477-491`), materializing all documents upfront (`annotation.py:468`). Cost multiplier is linear in passes with no incremental/changed-chunk shortcut; docstring admits "potentially increasing costs" (`annotation.py:237-241`, `extraction.py:80-81`).
  Impact: a recommended recall knob doubles or triples LLM spend and alignment work with no deduplication until the merge step.

- [MED] Full alignment (tokenize source, tokenize all extractions, exact DP/difflib, fuzzy pass) executes per chunk, not once per document (`annotation.py:422-429` passes `text_chunk.chunk_text`). Each chunk re-tokenizes source text (`resolver.py:882-884`, `934-938`) and re-tokenizes every extraction individually in the exact-match loop (`resolver.py:924-928`, `993-998`) and again in fuzzy (`resolver.py:743-747`). Chunk count C multiplies fixed per-align overhead.
  Impact: redundant regex tokenization and difflib setup dominate CPU when chunks are small and extraction lists are long.

- [MED] Legacy fuzzy path `_fuzzy_align_extraction` scans all sliding windows with `difflib.SequenceMatcher` (`resolver.py:651-669`), O(n²·window) per extraction; still reachable via `fuzzy_alignment_algorithm='legacy'` (`resolver.py:1050-1058`, deprecated warning `866-872`). PR #442 replaced this with LCS DP for speed (Issue #188), but the legacy branch remains.
  Impact: mis-set resolver params revert to the pre-#442 cost profile on large sources.

- [MED] Gemini Batch API activates only when `len(batch_prompts) >= batch.threshold` (default 50, `gemini_batch.py:84`; gate `gemini.py:424-425`). A 40k-char doc at `max_char_buffer=1000` yields ~40 chunks — still realtime-priced. Sub-threshold jobs log a fallback to realtime API (`gemini.py:468-472`). Issue #287: one malformed JSONL row aborts the whole batch job (https://github.com/google/langextract/issues/287).
  Impact: batch savings require large chunk counts; partial failures waste an entire job's latency (poll_interval default 30s, `gemini_batch.py:85`).

- [LOW] `ChunkIterator.__next__` probes every token index in a sentence with `_tokens_exceed_buffer` (`chunking.py:460-483`), O(tokens per sentence) per chunk boundary. Usually dwarfed by LLM latency, but adds avoidable work when `max_char_buffer` is tiny (many chunk boundaries).
  Impact: secondary; matters only when LLM cost is already minimized.

## False-pass hypothesis
A 1–2k-char README demo with verbatim few-shot examples completes in seconds with exact alignment only, masking the ~400× LLM call amplification and fuzzy-LCS cost that appear only when `len(text)` reaches WG21 paper scale (80k+) or when examples drift from source (Issue #188 / #246).

## False-fail hypothesis
Raising `max_char_buffer` toward our 500k single-shot budget without shrinking extraction cardinality will hit provider context limits or degrade extraction quality (README recommends smaller contexts for accuracy, https://github.com/google/langextract/blob/main/README.md), forcing users back to small buffers and accepting the call-multiplication wall as "unfixable."

## What would change my mind
Published benchmarks or a reproducible profile showing ≤60s end-to-end on an 80k-char document with library defaults (200-char buffer, fuzzy on, max_workers=10) including LLM queue time — or a release that unifies defaults to ≥1000-char buffers and documents a single "cost calculator" (chars → chunks → calls) in the public API.
