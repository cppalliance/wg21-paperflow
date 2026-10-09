# 20 - Retry-Policy-Analyst

**Verdict:** usable-with-conditions — the truncation-vs-malformation split is sound and attempt 3 is empirically justified for double-corruption, but malformation retries echo full failed outputs into history (context-contamination risk), retries misclassify the vLLM #41985 server bug as stochastic noise, and token growth cannot fix garbage-input chunks like P2728R11/12.
**Confidence:** high

## Findings

- [CRITICAL] Malformation retries append the entire `raw_content` (including `<think>` reasoning) plus a generic corrective user turn to `messages`, so failed attempts accumulate in the next request's context. Evidence: `model_backends.py:409-416`; `test_truncation_retry.py:159-160` (attempt 3 carries 6 messages after two malformation echoes). Impact: matches the arXiv context-contamination model (super-linear reliability decay when failed outputs stay in history, `05-web.md:96-98`, https://arxiv.org/html/2605.08563v1) and the pydantic-ai #4908 history-bloat pattern (`05-web.md:100-102`, https://github.com/pydantic/pydantic-ai/issues/4908); attempt 3 may self-correct JSON syntax while degrading field accuracy.

- [HIGH] The dominant CJK-in-JSON artifact is a systematic vLLM server defect (#41985 MLA FP8 decode), not recoverable model variance — yet the loop treats it like stochastic noise and retries. Evidence: `temperature=0.0` pins at `model_backends.py:321-323`; 9/200 papers hit double corruption at the old 2-attempt budget (`00-baseline.md:48`, `MODELS.md:121`); root cause and merged fix #42287 documented in `05-web.md:30-32` (https://github.com/vllm-project/vllm/issues/41985). Impact: retries absorb the symptom and delay the cheaper fix (pod upgrade); they do not retire the workaround row in `MODELS.md:121`.

- [HIGH] Attempt 3 adds measurable recovery for malformation-only double-corruption; the two remaining hard failures after rerun are a different failure class. Evidence: batch rerun of the 9 failed PIDs at `_RAW_JSON_MAX_ATTEMPTS = 3` recovered **7/9** (5 pass, 2 review); **P2728R11/P2728R12** still fail with max_tokens truncation on base64 garbage chunks, not CJK token injection (rerun transcript, 2026-07-03); unit test `test_double_corruption_recovers_on_third_attempt` (`test_truncation_retry.py:146-160`) models the 9/200 scenario. Impact: raising 2→3 was correct for #41985 double-hits; a 4th attempt would not help the P2728 pair.

- [HIGH] P2728R11/12: growing `max_tokens` 4096→6144→9216 (`4096 × 1.5²`, `_RETRY_MAX_TOKENS_GROWTH = 1.5` at `model_backends.py:64-65`, `:395-398`) is the wrong response when the INPUT chunk is unreadable base64 — the model narrates the blob until the output budget exhausts. Evidence: converted markdown embeds multi-kilobyte `data:image/png;base64,...` blocks (`packages/tomd/tests/fixtures/golden/p2728r11.golden.md:36+`); P2728R12 chunks into 7 parts with chunk 6/7 carrying the garbage block (rerun observation; initial sighting lists both among JSON failures, `tapetum-sighting-run-2026-07-01.md:52-56`); `chunking.py:57-92` splits on H2/char budget only, with no content-sanity gate. Impact: chunk-level base64-blob detection and strip-or-skip (before the LLM call) would fail-fast honestly instead of burning three truncation retries; token growth on garbage input is misattribution of the same kind the truncation branch explicitly avoids for output (`model_backends.py:391-394`).

- [MED] The truncation branch is correctly implemented: `finish_reason == "length"` grows `effective_max`, re-issues the original system+user request, and does NOT echo truncated output or append an "invalid JSON" nudge. Evidence: `model_backends.py:388-404`; `test_truncation_retry.py:83-101` (message count stays 2, budget grows). Impact: this half of the policy avoids the contamination and misattribution hazards that the malformation branch introduces.

- [MED] Malformation feedback nudge is untargeted: a fixed string plus raw exception text, with no JSON path, no field name, and no "same field fails twice → escalate" heuristic. Evidence: `model_backends.py:410-415`; recommended pattern in `05-web.md:112-114` (https://pub.towardsai.net/llm-structured-outputs-in-production-how-to-stop-json-from-breaking-your-ai-workflow-66703754d341). Impact: on attempt 2 the model may "fix" the wrong field or repeat the same corruption; no early exit distinguishes retry-worthy (transient CJK) from escalate-worthy (systematic bug, garbage chunk).

- [MED] Truncation regrowth is capped at `_max_context_window` and the 3-attempt × 1.5× ladder from 4096 lands at 9216, well under typical pod windows. Evidence: `model_backends.py:64-74`, `:395-398`; `test_truncation_retry.py:123-130` (8192×1.5 capped to 9000). Impact: regrowth cannot run unbounded; persistent truncation raises after exactly `_RAW_JSON_MAX_ATTEMPTS` (`test_truncation_retry.py:133-143`).

- [LOW] Attempt budget is bounded by caller `request_limit`: `max_attempts = min(_RAW_JSON_MAX_ATTEMPTS, request_limit)` (`model_backends.py:311`). Impact: D10 compliance is structurally enforced; tapetum's default path leaves headroom (`DEFAULT_REQUEST_LIMIT = 500`, `model_backends.py:53`).

## False-pass hypothesis

A paper hits CJK double-corruption on attempts 1–2; attempt 3 succeeds after two contaminated assistant echoes in context. JSON validates and pydantic accepts it, but a numeric field (e.g. `confidence`) or a free-text `reasoning` field was silently mutated during "repair" — schema-valid, semantically wrong `Adjudication`. Matches the field-mutation failure mode catalogued in `05-web.md:112-114`.

## False-fail hypothesis

P2728R11 chunk 6 contains a hard-split base64 PNG line (`chunking.py:76-78`, `partial=True`). Three attempts grow output to 9216 tokens while the model describes unreadable embedded image data; all exhaust with `finish_reason == "length"`. A chunk-level base64 strip (or skip-with-review) would have adjudicated the readable prose sections normally — honest failure today, avoidable false-fail tomorrow.

## What would change my mind

A 200-paper batch on a pod build containing #42287 (CJK injection eliminated) plus chunk-level base64-blob stripping in `chunking.py`, showing (a) hard-failure count ≤ 1 without any 3rd-attempt recovery events in debug transcripts, and (b) P2728R11/12 produce sidecars — would flip the verdict to **usable** and justify trimming malformation retries to 2 attempts with clean-restart (no history echo) instead of accumulated context.
