# 07 - Test-Suite-Auditor

**Verdict:** usable-with-conditions — 522 tests and strong fuzzy-alignment oracles exist, but the highest-risk public API path (`extract()` + `resolver_params` + parallel `infer()`) is mostly verified via mocks and kwargs plumbing, not behavior.
**Confidence:** high

## Findings
- [CRITICAL] Issue #245 (`resolver_params={'fuzzy_alignment_threshold': 0.5}` → `TypeError` on `Resolver` construction, 05-web.md Q5) shipped because no test exercises the real wiring path. `test_extract_resolver_params_alignment_passthrough` (init_test.py:158-203) mocks `Resolver.align` and only asserts kwargs on the mock; `test_extract_resolver_params_none_handling` (init_test.py:301-353) mocks the entire `Resolver` class. Neither would fail if `extract()` passed alignment keys into `Resolver(**effective_params)` instead of stripping them (extraction.py:359-370). The missing test: an unmocked `lx.extract(..., resolver_params={"fuzzy_alignment_threshold": 0.5})` smoke that reaches `Resolver(...)` construction without patching.
  Impact: Public tuning knobs can break in release while the suite stays green; directly matches the false-pass failure class.

- [HIGH] `prompt_validation_test.py:457-458` and `505-506` wrap `extraction.extract(..., resolver_params=...)` in bare `except Exception: pass`, swallowing constructor/routing failures (including the #245 `TypeError`). `AlgorithmPolicyIntegrationTest` (prompt_validation_test.py:430-470) therefore passes even when `extract()` dies before prompt validation runs.
  Impact: Integration tests become false-green harnesses; regressions on the docs-advertised `resolver_params` path hide behind swallowed exceptions.

- [HIGH] `fuzzy_alignment_threshold` is never tested for behavioral effect — only passthrough/default equality (init_test.py:192-202, 417-426; fuzzy_alignment_cases_test.py:572). The oracle helper `_run()` (fuzzy_alignment_cases_test.py:125-162) calls `_lcs_fuzzy_align_extraction` / `_fuzzy_align_extraction` without passing a threshold, so all 16 fuzzy oracle cases run at the hardcoded 0.75 default. No test sweeps 0.5 vs 0.75 to prove tuning changes accept/reject.
  Impact: Threshold calibration (#245, 05-web.md Q5) can be silently broken; tests prove plumbing, not the feature users configure.

- [HIGH] ThreadPoolExecutor index-order preservation is untested on the realtime infer path. Baseline documents the contract at gemini.py:487-504 / openai.py:355-389; `TestGeminiParallelRetry` (gemini_retry_test.py:305-326) runs `infer(['ok','flaky','fine'])` with `max_workers=2` but only asserts `results[1]` content and retry count — never that `results[0]`/`results[2]` map to `'ok'`/`'fine'`. `TestOpenAILanguageModelInference` (inference_test.py:794-810) uses a single-prompt batch only. No test forces out-of-order `as_completed` completion and checks prompt-index stability.
  Impact: An ordering regression in the default `max_workers=10` path (00-baseline.md DQ1) would pass the suite while scrambling chunk-to-output mapping.

- [MED] Multi-document + parallel infer regression (#260, 05-web.md Q2) has no reproducer. `test_annotate_documents` (annotation_test.py:691-737) and `test_yields_documents_not_generators` (annotation_test.py:1160-1204) mock `infer` sequentially and never pass `max_workers>1`. Cross-chunk context test (annotation_test.py:1328-1336) uses `batch_length=1` without parallel workers.
  Impact: The fixed doc-bleed bug could return undetected; parallel collection bugs are structurally different from serial mocks.

- [MED] Compared to our anchor `test_tapetum_llm.py` (75 test fns), langextract grounding coverage is deep on resolver internals (resolver_test.py 37 fns, fuzzy_alignment_cases_test.py 16 fns) but shallow on the public entry point. Tapetum's `TestGrounding` (test_tapetum_llm.py:51-117) calls the real `ground_spans` with positive, negative, and fuzzy-floor edge cases without mocking the function under test. Langextract's equivalent user-facing path (`lx.extract` + alignment params) is verified mostly via `@mock.patch` on `Resolver`/`Annotator` (init_test.py:158-468).
  Impact: 522 tests inflate confidence; the path tapetum would treat as contract-critical is mock-verified, not behavior-verified.

- [LOW] CJK / mixed-script `char_interval` mis-grounding (Issue #334, 05-web.md Q5) lacks resolver-level oracle tests. `UnicodeTokenizerTest` (tokenizer_test.py:391-404, 462-474) covers tokenization; resolver_test.py and fuzzy_alignment_cases_test.py use ASCII/Latin medical fixtures only (e.g. resolver_test.py:860-909 en-dash case). No planted-span oracle for Chinese/Japanese text where char offsets were reported wrong.
  Impact: Tokenizer fixes can pass while alignment char spans remain wrong for non-ASCII documents.

## False-pass hypothesis
Calling `lx.extract(text_or_documents="...", prompt_description="...", examples=[...], api_key="k", resolver_params={"fuzzy_alignment_threshold": 0.5})` without mocks raises `TypeError` at `Resolver(**effective_params)` (Issue #245) while `test_extract_resolver_params_alignment_passthrough` (init_test.py:160-203) still passes because `Resolver.align` is patched and never constructs a real `Resolver`.

## False-fail hypothesis
A few-shot example with minor whitespace drift (extra space or newline between tokens) may fail `PromptValidationLevel.ERROR` alignment checks (prompt_validation_test.py:414-423) and block `extract()` even though the extraction would align acceptably at runtime with fuzzy matching enabled — strict pre-flight validation rejecting inputs the resolver would ground.

## What would change my mind
A committed, unmocked integration test module (run in default CI, not `@pytest.mark.live_api`) that (1) calls `lx.extract(..., resolver_params={"fuzzy_alignment_threshold": 0.5})` end-to-end with a stub model, (2) asserts threshold changes alignment accept/reject on a planted ambiguous span, and (3) runs multi-prompt `infer()` with `max_workers>1` and verifies full index-ordered output under simulated out-of-order completion.
