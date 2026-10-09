# 63 - marker-Retry-Error-Handling

**Verdict:** usable-with-conditions — marker's per-block graceful degradation is a valid extraction-side pattern, but only a bounded slice (one cheap retry + honest `failed`/`unchecked` audit without promoting to pass) is portable to our advisory lane without breaking fail-closed coverage semantics.
**Confidence:** high

## Findings

- [CRITICAL] **Shared retry defaults: 2 retries, 30 s timeout, 3 s linear backoff base.** `BaseService` sets `timeout=30`, `max_retries=2`, `retry_wait_time=3` (`marker/services/__init__.py:13-17`). Every cloud service computes `total_tries = max_retries + 1` (3 attempts) and uses per-attempt timeout override (`openai.py:70-74`, `89`; same pattern in `claude.py:53-57`, `72`; `azure_openai.py:52-56`, `71`; `openrouter.py:81-84`, `104`; `gemini.py:52-56`, `61`). **Impact:** marker caps a stuck call at ~30 s × 3 + 9 s sleep ≈ 99 s worst case per block; our unit checks use 120 s × 1 attempt + pipeline retry (`constants.py:241`, `unit_judge.py:779-785`, `model_backends.py:300-350`). Shortening advisory timeouts toward 30–60 s on optional checks could save serial wall on failure paths (6 error papers in baseline) but risks more `failed_unit_ids` unless paired with one bounded retry; quality risk medium on timeout-induced false-unchecked.

- [HIGH] **Rate-limit / timeout retry is linear backoff; other errors fail immediately.** OpenAI-compatible services catch `(APITimeoutError, RateLimitError)`, sleep `tries * retry_wait_time` (3 s, then 6 s), and only retry those (`openai.py:110-123`; identical in `claude.py:98-111`, `azure_openai.py:92-105`, `openrouter.py:123-135`). Any other `Exception` logs and `break`s with no retry (`openai.py:124-126`). Gemini additionally retries `APIError` codes 429/443/503 with the same linear sleep (`gemini.py:94-108`) and retries `JSONDecodeError` with temperature bumped to 0.2 (`gemini.py:112-125`). **Impact:** marker spends at most ~9 s sleeping per block on rate limits; our fleet measured 55 BPE retries ≈ 100 s (~4% of 3003 s cold run, `00-baseline.md:19-20`). A single cheap retry on BPE/JSON/transient for unit checks is low-risk and may recover failed coverage without marker-scale call multiplication; quality risk low (same model, same prompt).

- [HIGH] **Ultimate LLM failure returns `{}`; processors keep the non-LLM block.** All cloud services end with `return {}` after give-up (`openai.py:128`, `claude.py:116`, `gemini.py:131`, `azure_openai.py:110`, `openrouter.py:140`). Processors treat empty/invalid responses as no-op: e.g. `if not response or "corrected_markdown" not in response: block.update_metadata(llm_error_count=1); return` (`llm_complex.py:73-75`; same guard pattern in `llm_equation.py:118-120`, `llm_table.py:199-201`, `239-241`, `llm_handwriting.py:73-78`, `llm_form.py:102-113`, `llm_image_description.py:76-81`). Original OCR/layout HTML is never cleared. **Impact:** marker never tombstones a document for LLM failure; conversion always completes. We cannot copy this wholesale (judge lane must record coverage gaps), but optional routed units could skip LLM rewrite while preserving deterministic markdown — zero extra calls, zero added review cap only if we accept silent skip (see middle-ground below); quality risk high if skip hides real defects on flagged units.

- [HIGH] **Document-level fail-open: processor exceptions are swallowed, pipeline continues.** `BaseLLMComplexBlockProcessor.__call__` wraps `rewrite_blocks` in try/except and logs a warning only (`processors/llm/__init__.py:137-144). `LLMSimpleBlockMetaProcessor` catches per-future errors and continues the batch (`llm_meta.py:51-61`). `PdfConverter.build_document` runs the full processor list with no abort hook (`converters/pdf.py:206-207`). **Impact:** marker trades audit completeness for throughput — the opposite of our `coverage_complete=false → review` contract (`unit_judge.py:460-477`, `pdf_judge.py:960-970). Portable lever: isolate fail-open to **non-required, quota-skipped** units only, never metadata/required units; estimated wall savings negligible on happy path, but avoids 120 s timeout × failed optional unit on error papers; quality risk medium.

- [MED] **Ollama path: zero retries, single POST, warn and `{}`.** `OllamaService.__call__` has no retry loop; one `requests.post`, on any exception logs warning and returns `{}` (`ollama.py:54-71`). **Impact:** self-hosted marker deployments fail fast (good for speed); our advisory lane on alliance-pod already uses pipeline retries (`model_backends.py:300-350`, max 2 attempts, exponential 2/4 s on transient API errors). Aligning optional checks with fail-fast (0–1 retry) vs mandatory checks with 2 retries is a tunable middle ground; quality risk low on required path if mandatory keeps current budget.

- [MED] **LLM concurrency capped at 3 threads per document; complex blocks parallelize independently.** `BaseLLMProcessor.max_concurrency=3` (`processors/llm/__init__.py:42-45`; used in `BaseLLMComplexBlockProcessor.rewrite_blocks` at `:163-172` and `LLMSimpleBlockMetaProcessor` at `llm_meta.py:44-49`). Table LLM adds inner quality retries (`max_table_iterations=2`, `llm_table.py:35-38`, `:252-263`) separate from service retries. **Impact:** marker parallelizes within-document LLM (we serialise unit checks per `00-baseline.md:38-39`). Retry/error semantics are orthogonal to the bigger parallelism lever; no direct wall saving from copying marker retries alone.

- [LOW] **Failure telemetry is block-local, not run-fatal.** `BlockMetadata.llm_error_count` increments on processor-side reject (`base.py:17-18`, `update_metadata` at `:340-351`; processors pass `llm_error_count=1`). Successful calls record `llm_request_count` / `llm_tokens_used` in services (`openai.py:105-108`). No aggregate "coverage incomplete" blocks export. **Impact:** marker optimizes for completed markdown, not inspectable coverage — our sidecar `unit_selection` / `failed_unit_ids` / `unchecked_unit_ids` (`unit_judge.py:484-517`) is the non-negotiable delta; keep audit fields even if we soften verdict cap.

## Contrast with our fail-closed contract

| Event | marker | tapetum-llm advisory |
|---|---|---|
| Rate limit / timeout | Up to 3 tries, linear sleep, then `{}` (`openai.py:89-128`) | Pipeline `max_attempts=min(2, request_limit)` with exponential backoff on transient API errors (`model_backends.py:300-350); BPE retry observed 55× fleet-wide (`00-baseline.md:19-20`) |
| Per-call timeout | 30 s default (`services/__init__.py:13`) | 120 s unit/page (`constants.py:197,241`), 900 s+ paper budget (`cli.py:138-161`) |
| LLM returns nothing / bad JSON | Keep OCR block; `llm_error_count+=1` (`llm_complex.py:73-75`) | Unit exception → `failed_unit_ids` → `coverage_complete=false` → verdict `review` (`unit_judge.py:419-423,460-477`) |
| Unchecked routed units | N/A (no coverage concept) | Quota skip → `unchecked_unit_ids` → `coverage_complete=false` → `review` (`unit_judge.py:370-372,460-477`) |
| Paper-level exception | Document still renders | `_write_error_tombstone` with `status="error"` (`cli.py:747-777`); batch exit 1 |

## Bounded middle ground for advisory lane

1. **One cheap retry on failed unit check (transient/BPE/timeout only):** Acceptable. Matches existing fleet retry culture (~4% wall), preserves fail-closed semantics if retry still fails → `failed_unit_ids`. Does not violate fidelity rules; may recover coverage without marker-style silent pass.

2. **Optional routed units: failure → `unchecked-advisory` without `coverage_complete` penalty (marker-style skip):** Conditionally acceptable only if (a) unit was non-required / quota-selected, (b) sidecar still lists `status: failed` or `skipped_llm`, and (c) verdict floor stays **`review`** whenever any routed unit lacks a successful check — never `pass`. Full marker pass-through (failed check = no signal = pass) **violates** our documented v6 fail-closed coverage contract (`cli.py:106-116`, `tapetum_llm.md` via CLAUDE.md) even though the lane never gates deterministic verdicts: it would inflate advisory pass rate and hide inspection gaps.

3. **Shorter timeout on optional checks (30–60 s) + fail-fast:** Acceptable with retry (1) above; mirrors marker's 30 s service default. Saves serial wall on hung calls; unacceptable without audit trail if timeout is treated as success.

**Net speed expectation:** Retry/error semantics alone are a **secondary** lever (~100 s known retry wall + timeout savings on error papers), dwarfed by call elimination and in-paper parallelism in `00-baseline.md`. Marker teaches **fail-fast + keep prior artifact**, not **fail-open + pretend complete**.

## False-pass hypothesis

Advisory `pass` after marker-style degradation on a quota-selected table unit: router flagged `table_presence` on P4182R0-style cell swap, LLM times out, we record no defect and lift `coverage_complete` — human sees advisory pass while deterministic pass stands; the swapped cell survives because 70% of unit checks already return zero defects (`00-baseline.md:29-30`) and only 16/381 merged verdicts change from LLM (`00-baseline.md:29-30`).

## False-fail hypothesis

Mandatory metadata/outline check gets one cheap retry on BPE corruption (attempt 2 succeeds, per baseline retry pattern) — currently a thrown parse error might tombstone the paper (`cli.py:1373-1387`) instead of recovering; extra retry adds ~20 s on that paper but avoids error tombstone and unnecessary re-run on warm cache.

## What would change my mind

A dev-replay or holdout run showing that treating **only** quota-skipped optional unit failures as `failed` status with verdict capped at `review` (not pass) reduces cold fleet wall by ≥10% with zero change in the 16/381 merged-verdict-changed rate (`00-baseline.md:29-30`).
