# 84 - langextract-Batch-Design

**Verdict:** usable-with-conditions — langextract's batch abstraction is a two-knob dispatch pattern (chunk grouping + in-batch thread parallelism) that maps cleanly to our OpenAI-compatible vLLM pod, but it is not multi-prompt packing and has no core vLLM offline-batch path.
**Confidence:** high

## Findings

- [CRITICAL] `batch_length` groups text chunks into one `infer(batch_prompts=[...])` call; it does NOT create a single multi-prompt HTTP request. Chunks are batched at `chunking.make_batches_of_textchunk` (`chunking.py:265-279`), prompts are built per chunk (`annotation.py:370-375`), then the provider receives a list of independent prompts (`annotation.py:392`). Impact: adopting this pattern for tapetum unit checks means up to `min(batch_length, max_workers)` separate `chat.completions.create` calls in flight per paper-batch, not one fused judge prompt; on a 6-call paper with 5 unit checks, in-paper parallel could cut the unit-check segment from ~100 s serial to ~20 s (~80 s/paper on affected papers, ~400-600 s fleet-wide if ~50% of papers hit unit checks), with MoE batch-composition variance risk (00-baseline open lever #3).

- [CRITICAL] OpenAI-compatible realtime dispatch (our pod shape) is N parallel HTTP calls via `ThreadPoolExecutor`, capped at `min(max_workers, len(batch_prompts))` (`openai.py:355-358`, `_process_single_prompt` at `openai.py:244-250` uses `self._client.chat.completions.create(**api_params)` with `base_url` set at `openai.py:167-171`). Impact: zero code novelty needed beyond an asyncio/thread pool that fires separate completions against `alliance-pod`; expected saving is throughput-bound (same ~20 s/call latency but overlapped), not call-count reduction; quality risk is server-side scheduling variance under higher in-flight count per paper, not prompt-fusion drift.

- [HIGH] Effective in-batch parallelism is explicitly `min(batch_length, max_workers)`; defaults are both 10 (`extraction.py:57-58`, docstring `extraction.py:122-126`), and a warning fires when `batch_length < max_workers` (`extraction.py:243-248`). Impact: for our `--max-num-seqs 16` pod, setting both knobs to 16 (not 32) aligns client dispatch with server slots; mis-setting wastes parallelism or over-subscribes (research/slots-32-regression); quality risk low if capped at 16.

- [HIGH] Batches are processed serially at the annotation layer: `for batch in batch_iter` then one blocking `infer()` (`annotation.py:366-392`). There is no cross-batch pipelining or second-level worker pool above the provider. Impact: langextract's cross-document throughput comes from filling each batch with chunks from multiple documents (`annotation.py:227`, test `annotation_test.py:673-688`), not from concurrent batches; our fleet already exceeds this with 32 papers × 1 serial call each — langextract teaches in-paper widening, not fleet widening.

- [HIGH] Gemini mirrors the same pattern: optional cloud Batch API when `batch_cfg.enabled` and `len(batch_prompts) >= threshold`, else `ThreadPoolExecutor` parallel realtime calls (`gemini.py:424-464`, `gemini.py:476-478`). Impact: cloud async batch modes (24 h completion window, poll loop in `openai_batch.py:347-407` / `gemini_batch.py:707-759`) are irrelevant to our 5-10 min realtime judge SLO; copying them would add latency, not cut wall clock.

- [MED] Ollama provider ignores batch parallelism entirely: sequential `for prompt in batch_prompts` (`ollama.py:291-310`). Impact: if model routing hits Ollama patterns (`patterns.py:35-63`) instead of OpenAI, all batch_length/max_workers tuning is dead; quality-neutral but zero speedup.

- [MED] No built-in vLLM offline batch engine. Core repo lists vLLM only as a community plugin (`COMMUNITY_PROVIDERS.md:17`); the in-tree OpenAI "batch" path is the vendor Batch API (JSONL upload + poll, `openai_batch.py:411-429`), not vLLM `LLM.generate` offline mode. Impact: the ~2× offline-vs-HTTP lever cited in `05-web.md` Q3 is not accessible through langextract core; attempting to bolt it on via their abstraction would require a new provider, not config toggles.

- [LOW] `max_workers` is wired at model construction via `provider_kwargs` (`extraction.py:307-314`) and stored on the provider instance (`openai.py:154`, `gemini.py:231`); it is not re-read from `infer(**kwargs)` at call time. Impact: fleet dispatch must set concurrency at backend init, not per-call; quality-neutral operational detail.

## False-pass hypothesis

Treating langextract `batch_length` as "pack N unit-check rubrics into one prompt" would silently degrade findings: their code never concatenates prompts (`annotation.py:370-375` builds one prompt per chunk). Multi-rubric packing dropped Spearman rho ~5.3% in `05-web.md` Q3 (arXiv 2605.26046); RuVerBench shows double-digit drops on long-context agentic tasks (`05-web.md` Q5). Copying the name "batch" without the separate-request semantics would look faster while missing page-scoped defects.

## False-fail hypothesis

Raising in-paper parallel unit checks to `min(5, 16)` separate HTTP calls (langextract realtime pattern) could cause false escalations or missed zero-defect short-circuits if MoE expert routing shifts under heterogeneous concurrent prefill lengths (full `candidate_md` repeated per call, same as 00-baseline payload fact). A paper whose unit checks currently return zero defects might get spurious defect groups on rerun, flipping ~16/381 merged verdicts (`00-baseline` line 30) without any prompt change.

## What would change my mind

A controlled A/B on `alliance-pod`: same 381-paper cold fleet, serial unit checks vs langextract-style `batch_length=5, max_workers=5` separate completions, measuring verdict delta rate and zero-defect unit-check stability. If merged-verdict change rate stays ≤ current warm-run retry noise (~4%) with zero-defect rate unchanged, upgrade verdict to plain `usable`.
