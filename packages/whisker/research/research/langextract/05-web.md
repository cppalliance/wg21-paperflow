# 05 - Web Finding Cards: google/langextract

Collected 2026-07-03 by 2 Composer foragers (5 questions from `00-baseline.md`).
Cards are grouped under their originating question. Deduplicated by URL.

## Q1: Maintenance pulse and release cadence around v1.6.0 (2026)

**v1.6.0 GitHub Release (2026-07-02)** [HIGH]
https://github.com/google/langextract/releases/tag/v1.6.0
Published 2026-07-02 by maintainer aksg87. Highlights: user-provided `output_schema` for Gemini and OpenAI, Ollama GPT-OSS JSON chat support. Confirms v1.6.0 is a real tagged release, not a PyPI-only artifact.

**PyPI Version History (latest = 1.6.0)** [HIGH]
https://pypi.org/project/langextract/
PyPI confirms 1.6.0 uploaded 2026-07-02. Prior releases: 1.5.0 (2026-05-20), 1.4.0 (2026-05-15), 1.3.0 (2026-04-29). Cadence rapid Mar-May 2026, then a ~6-week gap before v1.6.0.

**GitHub main branch commits (Jul 2026 activity burst)** [HIGH]
https://github.com/google/langextract/commits/main/
Three commits on 2026-07-02: PR #483 (`output_schema`), PR #484 (Prepare v1.6.0), PR #485 (alignment fix). Prior cluster 2026-05-21. Repo not archived; last meaningful push was yesterday relative to query date.

**v1.5.0 Release (prior stable, May 2026)** [MED]
https://github.com/google/langextract/releases/tag/v1.5.0
Published 2026-05-20. Added OpenAI Batch API support, bumped default Gemini model to `gemini-3.5-flash`. Marks the start of the pre-v1.6.0 quiet period.

**google/langextract repository overview** [MED]
https://github.com/google/langextract
~37K stars, ~107 open issues, Apache-2.0, ~30 contributors. Not archived. Maintained-but-not-daily-release cadence.

## Q2: Parallel inference ordering, ThreadPoolExecutor races, batch-API scheduling bugs

**Issue #50: feat: Add delay/retry between requests (OPEN)** [HIGH]
https://github.com/google/langextract/issues/50
Users hit `Parallel inference error: Gemini API error: 429 RESOURCE_EXHAUSTED` with default `max_workers=10`. Workaround: reduce `max_workers` to 3. PR #332 (exponential backoff on 429) referenced Jan 2026 but issue remains open. Parallel-scheduling pain point, not an ordering race.

**Issue #287: Batch job fails on single bad JSONL row (OPEN)** [HIGH]
https://github.com/google/langextract/issues/287
Vertex AI Batch API jobs complete but extraction aborts when one predictions.jsonl row has malformed output. One bad record kills the batch; `suppress_parse_errors=True` initially did not help. Workaround (Feb 2026): `max_workers=1`, `batch_length=1000`, `resolver_params={"suppress_parse_errors": True}`.

**Issue #285: Gemini Batch API missing project param (CLOSED)** [HIGH]
https://github.com/google/langextract/issues/285
`language_model_params["project"]` not propagated to `storage.Client.create_bucket()`, causing 400 at batch submission. Fixed in PR #286 (Nov 2025).

**Issue #240: Chunking does not recover from 503 overload (CLOSED)** [HIGH]
https://github.com/google/langextract/issues/240
Single 503/429 during parallel chunk processing failed the entire document. Fixed via commit `3aab86c` (~Apr 2026): per-chunk exponential backoff for transient errors. Failure propagation, not result ordering.

**Issue #260: Multi-document extraction bleed with max_workers=4 (CLOSED)** [MED]
https://github.com/google/langextract/issues/260
Multiple documents with `max_workers=4` returned only the last document's results. Fixed in PR #276 (Nov 2025) by refactoring the annotation layer to lazy streaming. Ordering/collection bug in the parallel multi-document path.

## Q3: vLLM guided_json / guided decoding / self-hosted structured output

**vLLM community plugin tracking (Issue #236)** [HIGH]
https://github.com/google/langextract/issues/236
Maintainer accepted the `langextract-vllm` community plugin (registry via PR #244); a draft PR #393 for built-in vLLM support was closed without merge. No discussion of vLLM `guided_json`, guided decoding, or schema-constrained generation anywhere in the thread.

**ResolverParsingError with vLLM/lmdeploy vs Ollama (Issue #414)** [HIGH]
https://github.com/google/langextract/issues/414
vLLM and lmdeploy OpenAI-compatible backends fail JSON parsing while the same prompt works on Ollama; maintainer workaround `fence_output=False, use_schema_constraints=False`, but success rate stays below 20%. The main self-hosted structured-output pain thread; framed as format/parsing compatibility, not constrained decoding.

**Fix fenced JSON from OpenAI-compatible backends (PR #444)** [HIGH]
https://github.com/google/langextract/pull/444
Open PR targeting Issue #414: strips markdown-fenced JSON when raw JSON mode is expected from vLLM/lmdeploy. Post-processing of model output, not vLLM `guided_json`/`response_format` wiring.

**langextract-vllm plugin README** [MED]
https://github.com/wuli666/langextract-vllm
Community provider documents `provider_kwargs` for sampling/server connection only. No `guided_json`, `structured_outputs`, or schema-constrained decoding; integration is plain OpenAI-compatible chat/completions.

**Ollama vs OpenAI provider schema behavior (README)** [MED]
https://github.com/google/langextract/blob/main/README.md
First-class self-hosted structured output only for Ollama via `FormatModeSchema` (JSON mode). OpenAI-compatible providers use `response_format={"type":"json_object"}` only; README explicitly says OpenAI has no schema-class constraints. No first-class vLLM guided-decoding path.

## Q4: Comparison to alternatives on evidence-span grounding

**google/langextract README - source grounding model** [HIGH]
https://github.com/google/langextract
Differentiator is `char_interval` on every extraction, computed by aligning LLM output back to source text; ungrounded items get `char_interval = None`. Span grounding is a separate post-LLM alignment stage, not model-emitted.

**How offsets are computed (Issue #259)** [HIGH]
https://github.com/google/langextract/issues/259
Maintainer confirms vanilla LLMs do not return verified character offsets; LangExtract uses sequence/token alignment in `resolver.py` after extraction. Authoritative statement on why LangExtract differs from Instructor/Outlines/LangChain (schema-valid JSON, no verified evidence spans).

**LangChain extraction template - evidence + approximate alignment (Issue #12739)** [HIGH]
https://github.com/langchain-ai/langchain/issues/12739
LangChain's recommended pattern: ask for verbatim `evidence` text, never for counted offsets, then align approximately against the source. LangExtract bakes exactly that alignment pipeline in as `char_interval` plus visualization.

**LangExtract vs Instructor / Outlines / GLiNER comparison (genmind.ch)** [MED]
https://genmind.ch/posts/LangExtract-Production-LLM-Powered-Information-Extraction/
Third-party comparison positions LangExtract for long documents plus compliance traceability via built-in character positions. Instructor/Outlines = schema enforcement without native grounding; GLiNER/spaCy = offline NER spans without LLM-flexible schemas.

**GLiNER2 - schema-driven spans without LLM post-alignment** [MED]
https://arxiv.org/html/2507.18546
GLiNER2 is a 205M encoder model producing entity spans natively from the model rather than LLM-output-to-text fuzzy alignment. A different grounding architecture: local, deterministic spans vs LangExtract's LLM-plus-resolver pipeline.

## Q5: Fuzzy alignment wrong spans / dropped extractions / 0.75 threshold calibration

**Fuzzy alignment threshold not applied (Issue #245)** [HIGH]
https://github.com/google/langextract/issues/245
`resolver_params={'fuzzy_alignment_threshold': 0.5}` raises `TypeError` because the Resolver constructor did not unpack alignment kwargs. Fix PR #318 unmerged as of July 2026. Direct evidence that threshold calibration via `resolver_params` was broken in released code.

**Wrong char_interval for non-ASCII/CJK text (Issue #334)** [HIGH]
https://github.com/google/langextract/issues/334
`char_interval` values shifted or wrong for Chinese, Japanese, accented Latin, emoji. Fix attempts PR #350 and PR #479 target `RegexTokenizer` merging CJK with adjacent Latin. Wrong-span grounding, not just missing extractions.

**Prompt alignment failures and fuzzy non-exact matches (Issue #246)** [HIGH]
https://github.com/google/langextract/issues/246
Logs show `FAILED to align` with `status=None` and `MATCH_FUZZY` spans on few-shot example text itself. Maintainer guidance: examples must be verbatim and ordered; fuzzy matches proceed with warnings by default.

**CJK substring fallback for dropped alignments (PR #480)** [MED]
https://github.com/google/langextract/pull/480
Adds substring-based fallback after token exact/fuzzy alignment fails on CJK text; includes an unaligned-extractions panel for items that fail all alignment tiers.

**Fuzzy match performance and disabling guidance (Issue #188)** [MED]
https://github.com/google/langextract/issues/188
Expensive fuzzy matching on large PDF markdown; misaligned prompt examples trigger the fuzzy fallback. PR #442 replaced the legacy difflib aligner with faster LCS DP. The default 0.75 threshold behavior is tied to example alignment quality, not user-tuned calibration.
