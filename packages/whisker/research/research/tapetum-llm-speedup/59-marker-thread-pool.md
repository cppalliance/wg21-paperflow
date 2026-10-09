# 59 - marker-Thread-Pool

**Verdict:** usable-with-conditions — marker's per-document `ThreadPoolExecutor(max_workers=3)` pattern for independent block-level LLM calls is directly portable to our serial unit-check loop, but it is a partial lever (~10–20% cold-fleet wall, not 5–10 min alone) and requires keyed merge plus a hard in-paper cap to avoid MoE tail blowups.
**Confidence:** high

## Findings

- [CRITICAL] **Default in-document LLM concurrency is 3 via `BaseLLMProcessor.max_concurrency`.** Evidence: `marker/processors/llm/__init__.py:42-45` (`max_concurrency: ... = 3`). Impact: portable cap for tapetum unit checks; at ~20 s/call (00-baseline), 5 serial unit checks cost ~100 s vs ~40 s at pool=3 (~60 s/paper saved on heavy papers). Quality risk: low if merge is keyed; MoE batch-composition variance at 3× in-paper slot use (00-baseline lever #3).

- [CRITICAL] **Complex processors parallelize all matching blocks/pages within one PDF using `ThreadPoolExecutor` + `as_completed`.** Evidence: `marker/processors/llm/__init__.py:163-172` (fan-out over pages×blocks, `max_workers=self.max_concurrency`); same pattern in `llm_page_correction.py:283-291`, `llm_table_merge.py:284-292`, `llm_mathblock.py:152-160`. Impact: confirms marker runs multiple LLM calls per document concurrently (contrast: our `unit_judge.py:379+` serial loop). Expected fleet effect: if we mirror on ~1510 unit calls (66% of 2284), per-paper unit-phase wall drops up to ~3×; fleet cold run ~300–600 s savings (~10–20%) because monolith/metadata/page escalations stay serial and 32-paper fleet concurrency already fills 16 slots. Quality risk: medium (MoE logits drift under mixed concurrent prompts).

- [HIGH] **Simple LLM processors share one meta-processor pool across processor types (forms, math, handwriting, etc.).** Evidence: `marker/converters/__init__.py:48-62` (collects `BaseLLMSimpleBlockProcessor` instances into `LLMSimpleBlockMetaProcessor`); `llm_meta.py:39-49` (single pool submits all prompts from all simple processors); `llm_meta.py:44` (`max_workers=self.max_concurrency`). Impact: one bounded pool per document stage, not one pool per check type — matches our model of one `max_workers=3` pool for all unit checks rather than separate pools per rubric. Quality risk: low.

- [HIGH] **Result merge is deterministic-by-key, not by completion order.** Evidence: `llm_meta.py:51-59` (drains futures in submission order, dispatches to owning processor via `futures_map`; each `rewrite_block` writes to a specific `block` object); `llm_form.py:98-117` (`block.html = corrected_html` on the prompt's block); `__init__.py:110-129` (`handle_rewrites` resolves `block_id` from LLM JSON). Complex processors use `as_completed` but each future mutates a disjoint block/page (`llm_page_correction.py:247-266`). Impact: tapetum should `gather` unit checks then merge findings sorted by `(page_index, unit_id)` — completion order must not affect verdict. Quality risk: low if we sort before merge; high if we append findings in finish order.

- [HIGH] **LLM services are strictly synchronous single-request; no batch API, no asyncio.** Evidence: `marker/services/__init__.py:46-55` (`__call__` raises NotImplementedError; one prompt in/out); `gemini.py:78-93`, `openai.py:91-109` (blocking SDK calls). Parallelism lives only in processor thread pools. Impact: our `judge_task.py` async dispatch + thread pool mirrors this architecture; no vLLM batching win from marker. Quality risk: none.

- [HIGH] **Rate limiting is per-call retry with linear backoff, not a global LLM semaphore.** Evidence: `marker/services/__init__.py:13-17` (`timeout=30`, `max_retries=2`, `retry_wait_time=3`); `gemini.py:94-108` (HTTP 429/443/503 → sleep `tries * retry_wait_time`); `openai.py:110-123` (`RateLimitError` same pattern); `claude.py:98-111`. No fleet-wide LLM concurrency gate beyond `max_concurrency=3` per processor. Impact: portable retry policy only; does not explain marker speed (pool=3 is the lever). At 32 papers × pool 3 competing for 16 server slots, tail latency inflates — expect p99 call time >20 s (quality-stable retries add wall). Quality risk: medium on fleet tail (timeout tombstones).

- [MED] **Processor stages remain serial; only calls within a stage parallelize.** Evidence: `marker/converters/pdf.py:206-207` (`for processor in self.processor_list: processor(document)`); table merge runs after table rewrite in default order (`pdf.py:97-107`). Exception: `LLMSectionHeaderProcessor` overrides to one document-level call (`llm_sectionheader.py:145-163`, no thread pool). Impact: tapetum should keep monolith → metadata/outline → page escalations serial; parallelize only independent unit checks (and only page escalations if proven independent). Quality risk: low if dependencies respected; high if monolith/unit run concurrently.

- [MED] **Document-level batch parallelism is separate: `mp.Pool` PDF workers with VLM concurrency budget, not LLM pool sizing.** Evidence: `marker/scripts/convert.py:198-199` (`workers = kwargs["workers"] or get_worker_count()`); `convert.py:205-212` (sets `SURYA_INFERENCE_PARALLEL` ≈ `1.5 × capacity / total_processes`); `convert.py:230-237` (`mp.Pool(processes=total_processes, ... imap_unordered`); `marker/utils/batch.py:8-29` (worker count bounded by CPU cores and server parallel). Impact: we already exceed this with `_DEFAULT_CONCURRENCY=32` papers (`cli.py:125`); marker's cross-doc LLM pattern adds worker breadth but caps each worker's LLM fan-out at 3. Dual-pod sharding (00-baseline) is our analogue, not marker's mp.Pool. Quality risk: none for LLM quality.

- [LOW] **`max_concurrency` is overridable via shared CLI/config (`--max_concurrency`, `--config_json`).** Evidence: `marker/config/printer.py:54-68` (registers shared attrs from processor annotations); `marker/util.py:47-68` (`assign_config` applies dict keys to processor instances). Impact: tunable A/B for tapetum (2 vs 3 vs 4) without code fork. Quality risk: raising above 3 increases MoE variance and slot contention (measured 16→32 server slots +60% wall, 00-baseline constraints).

## False-pass hypothesis

Parallel unit checks on the same paper all prefill the full `candidate_md` (~6× today, 00-baseline) with distinct guard tags; at pool=3, three near-identical long prefills hit the MoE server simultaneously, evicting each other's prefix-cache blocks (05-web Q1: DeepSeek V4 APC collapse at concurrency 16). Decode logits drift on borderline table/footnote defects → zero-defect checks that serial runs caught now return empty `defect_groups`, silently passing a bad conversion.

## False-fail hypothesis

With 32 papers in flight and in-paper pool=3, peak demand approaches 96 logical requests on 16 server slots (`cli.py:125`, SERVICES.toml `--max-num-seqs 16`). Queue depth spikes p99 latency past `UNIT_CHECK_TIMEOUT_SECONDS=120` (`constants.py:197`), producing error tombstones and false `fail`/`review` on papers that serial execution would have completed within budget.

## What would change my mind

A controlled tapetum replay on the 381-paper cold corpus: serial unit checks vs `asyncio.Semaphore(3)` unit gather with sorted merge, same model/pod, reporting both wall time and verdict diff rate (target: ≤1% papers change merged verdict, matching marker's block-keyed isolation). If verdict diff is 0% and wall drops ≥25%, upgrade verdict to `usable` without conditions.

## Portable pattern (tapetum mapping)

| Marker | Tapetum today | Portable change |
|---|---|---|
| `ThreadPoolExecutor(3)` on blocks (`__init__.py:163-172`) | Serial unit loop (`unit_judge.py:379+`) | `asyncio.gather` / task group with `Semaphore(3)` after monolith+metadata |
| Keyed block write (`llm_form.py:117`) | Serial append to findings | Merge by sorted `(page, unit_id)` after all tasks complete |
| One meta pool for simple processors (`llm_meta.py:44-49`) | N/A | Single in-paper pool for all unit rubrics, not per-rubric pools |
| Processor stages serial (`pdf.py:206-207`) | Full paper chain serial | Keep monolith/metadata/pages serial; only parallelize independent units |
| No global LLM semaphore | 32-paper × serial calls | Do not raise paper concurrency when enabling in-paper pool; optionally lower to ~16 |

**Expected effect on 3003 s cold fleet:** ~300–600 s wall reduction (~10–20%) from unit-phase critical-path shortening; insufficient alone for 5–10 min target. **Fleet tail:** p99 per-call latency rises when many papers overlap unit phase (32×3 logical vs 16 slots); longest-job papers remain tail-dominated unless combined with dual-pod sharding or call elimination (00-baseline levers #1–#2).

**Clone note:** `research/repos/marker` @ `6ea35fe`; `benchmarks/overall/scorers/llm.py` (serial judge loop cited in tapetum-llm-throughput/05-web) absent in this shallow clone — production processor paths above verified directly.
