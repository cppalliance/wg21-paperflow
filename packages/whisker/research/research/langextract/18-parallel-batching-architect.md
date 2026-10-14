# 18 - Parallel-Batching-Architect

**Verdict:** usable-with-conditions   The index-keyed ordered-yield pattern is sound and matches our `gather_concurrent` shape, but langextract's ThreadPoolExecutor defaults, shared sync client, and conflation of output-order stability with semantic determinism make the shipped model unsafe to copy verbatim under D11.
**Confidence:** high

## Findings
- [CRITICAL] Shipped `extract()` defaults activate up to 10 concurrent in-flight LLM calls: `batch_length=10`, `max_workers=10` (`extraction.py:57-58`) satisfy the pool gate `len(batch_prompts) > 1 and self.max_workers > 1` (`gemini.py:476-479`, `openai.py:355-358`). Baseline DQ1 and our D11 (`CLAUDE.md:88`, `tasks.py:30-38` `_TASK_CONCURRENCY=1`) require serial-by-default; langextract's primary API violates that before any user opt-in. Impact: tapetum must NOT inherit these defaults; `--concurrency N` must default to 1 and opt in explicitly.
- [HIGH] **Index-ordered yield claim verified within a batch.** `ThreadPoolExecutor` submits `{future: i}` (`gemini.py:480-485`), drains `as_completed` into a pre-sized `results[index]` (`gemini.py:487-493`), checks for `None` holes (`gemini.py:499-503`), then yields in input order (`gemini.py:499-504`). OpenAI mirrors this (`openai.py:366-385`). This is the same contract as `StepContext.gather_concurrent` (sort by index after bounded completion, `runner.py:133-162`). Impact: adopt the **index-slot + sort-by-index** shape for tapetum chunk/paper fan-out; do not reimplement ordering via completion order.
- [HIGH] **Output-order stability ≠ semantic determinism under concurrency.** Index-yield preserves prompt-to-result alignment, but concurrent hosted/vLLM requests can return different token choices across runs (Issue #50: 429/RESOURCE_EXHAUSTED at `max_workers=10`, `05-web.md`; vLLM #10269: client concurrency must track pod `--max-num-seqs`, `llm-stack/05-web.md`). vLLM batch invariance docs (`llm-stack/05-web.md`) state `temperature=0` alone does not guarantee identical outputs when batch size/order changes. Impact: tapetum `--concurrency N>1` may speed throughput but must document a variance budget; it does not satisfy D11's "same findings" guarantee on a shared MoE pod without server-side batch-invariant mode.
- [HIGH] **Cross-batch document attribution is a separate hazard from pool ordering; it already failed once.** Issue #260 (`05-web.md`): multi-document extraction with `max_workers=4` returned only the last document's results (fixed PR #276 via lazy streaming). The current guard is an orchestrator-level emit cursor: `doc_order` + `next_emit_idx` (`annotation.py:307-346`) over a **serial** batch loop (`annotation.py:366-392`), not the thread pool. Impact: if tapetum parallelizes chunk triage within one paper, it must keep a fold/emit cursor (worst-axis fold today at `adjudicate.py:171-246`) independent of pool completion order; copying only the provider pool without this layer repeats the #260 failure class.
- [MED] **`list(outputs)` materialization before `zip` is a deliberate ordering guard.** `infer()` returns a lazy generator (`gemini.py:393-504`), but the annotator forces full consumption (`annotation.py:392-394`) then pairs with `zip(batch, outputs)` (`annotation.py:396`). Parallel work therefore completes entirely before resolve/align runs for that batch, preventing a streaming zip mismatch. Impact: tapetum should materialize indexed results before fold/grounding, not stream partial results into aggregation.
- [MED] **Mid-pool exceptions fail the whole batch (good for fidelity, bad for partial progress).** Any worker exception raises `InferenceRuntimeError('Parallel inference error: ...')` immediately (`gemini.py:494-497`); unfilled slots trigger `'Failed to process one or more prompts'` (`gemini.py:499-503`). Impact: matches our fail-not-partial invariant (`CLAUDE.md` Fidelity); tapetum should abort the chunk/paper on any fan-out failure, not emit partial adjudication.
- [MED] **Shared sync client across pool threads is an unverified concurrency hazard.** One `genai.Client` (`gemini.py:284-291`) and one OpenAI `_client` (`openai.py:55`) serve all `_process_single_prompt` calls submitted to the pool (`gemini.py:481-482`, `openai.py:360-362`). Retry backoff uses per-thread jitter `random.uniform(0.5, 1.5)` (`gemini.py:376-377`), so parallel workers retry on independent schedules. Impact: tapetum must NOT copy ThreadPoolExecutor + shared sync client; use async `gather_concurrent` with our existing `AgentBackend`/`run_task` path and cap N to the pod's seq budget.
- [LOW] Baseline cites `Annotator` default `batch_length=1` (`annotation.py:214`, baseline §3) but the shipped `extract()` API overrides to `batch_length=10` (`extraction.py:57`, `extraction.py:393-399`). Impact: integrators reading baseline DQ1 alone may underestimate default parallelism; tapetum docs must state concurrency defaults explicitly.

## False-pass hypothesis
A tapetum run with `--concurrency 4` on four H2 chunks of one paper uses `gather_concurrent` correctly (sorted indices, stable chunk order in the final fold) but the shared alliance-pod vLLM server schedules requests into a different continuous batch than a serial rerun; deep-tier confidence shifts on one chunk, flipping an axis from `review` to `pass`, while all ordering invariants appear green.

## False-fail hypothesis
A tapetum run keeps `default_concurrency=1` (`adjudicate.py:409`), uses `gather_concurrent` only at CLI paper-level fan-out with `--concurrency 2` across independent PIDs (not within-paper chunk triage), and treats langextract's index-yield as an ordering primitive only; no ordering bug manifests, but throughput doubles with acceptable operational risk.

## What would change my mind
A langextract regression test (or our tapetum integration test) demonstrating two back-to-back runs with `max_workers=N>1` on a fixed fixture produce identical extraction/adjudication content—not just index order—on our self-hosted vLLM endpoint with documented `--max-num-seqs` and `VLLM_BATCH_INVARIANT=1`, plus proof the genai/OpenAI client is thread-safe under their pool.

## Tapetum `--concurrency N`: copy vs do-not-copy

**Copy:**
- Index-keyed result slots + yield/sort in input order (`gemini.py:487-504` ≈ `runner.py:133-162` `gather_concurrent`).
- Serial orchestrator over batches with an explicit emit/fold cursor for multi-chunk or multi-document attribution (`annotation.py:307-346`, `366-392`).
- Full materialization of fan-out results before zip/fold/ground (`annotation.py:392-396`).
- Fail-whole-batch on any fan-out error (`gemini.py:494-503`).
- Per-package opt-in via `StepContext.default_concurrency` (`runner.py:106`, `adjudicate.py:409`), never raising `_task_semaphore` / global semaphores (`tasks.py:30-38`).

**Do NOT copy:**
- `ThreadPoolExecutor` + shared sync HTTP client (`gemini.py:477-491`, `openai.py:356-362`).
- `max_workers=10` / `batch_length=10` shipped defaults (`extraction.py:57-58`, `gemini.py:129`).
- Treating index-ordered yield as semantic determinism under concurrent vLLM/hosted load (Issue #50, vLLM #10269, `llm-stack/05-web.md`).
- Parallel multi-chunk inference within one paper without a tested emit/fold cursor (Issue #260 class, `05-web.md`).
- Jittered retry scheduling as a silent variance source under parallel load (`gemini.py:376-377`).
