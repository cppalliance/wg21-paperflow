# 69 - Sidecar timing fields (P96 playbook)

**Verdict:** gap confirmed — tapetum LLM sidecars persist paper-level `duration_seconds` only; per-call wall time, token usage, and retry attribution are absent. P96 fleet A/B requires client-side `call_timings[]` plus a fleet-window `/metrics` scrape (not lifetime pod counters).
**Confidence:** high (code-verified at HEAD)

## What exists today

| Location | Field / artifact | Scope | Notes |
|---|---|---|---|
| `packages/whisker/src/whisker/tapetum_llm/cli.py:740-741` | `duration_seconds` | Per-paper sidecar | Rounded to 2 dp; injected in `_persist_lane_result`, not in `to_sidecar_dict()` |
| `packages/whisker/src/whisker/tapetum_llm/cli.py:768-769` | `duration_seconds` | Per-paper sidecar (text lane) | Same contract in `_persist_result` |
| `packages/whisker/src/whisker/tapetum_llm/cli.py:1202` | `paper_started = time.monotonic()` | Ephemeral | Wall clock for one paper worker |
| `packages/whisker/src/whisker/tapetum_llm/cli.py:1375-1378` | `paper_duration` → persist | PDF lane | End-to-end paper wall including ideal verify |
| `packages/whisker/src/whisker/tapetum_llm/cli.py:1463-1466` | `paper_duration` → persist | HTML/text lane | Same |
| `packages/whisker/src/whisker/tapetum_llm/cli.py:1168,1523-1534` | Batch `elapsed`, retry footer | Fleet log only | `{retries} model retries) in {elapsed:.1f}s`; not written to disk |
| `packages/whisker/src/whisker/tapetum_llm/cli.py:229-247` | `_RetryCountFilter.count` | Fleet aggregate | Swallowed backend retry warnings; no per-call class |
| `packages/whisker/src/whisker/tapetum_llm/pdf_judge.py:129-132` | `_set_progress(progress, **fields)` | Error tombstone only | Phase markers (`monolith`, `metadata`, `unit_checks`, …); no timestamps |
| `packages/whisker/src/whisker/tapetum_llm/cli.py:825-826` | `partial_progress` | Error sidecar | Attached on failure; phase + unit ids, not timings |
| `packages/pipeline/src/pipeline/runner.py:346-395` | `StepMetrics.duration_s` | In-memory (text lane) | Step-level wall (includes non-LLM work in custom hooks); never copied to sidecar |
| `packages/pipeline/src/pipeline/runner.py:79-82` | `StepMetrics.input_tokens` / `output_tokens` | Declared, unused | Never populated anywhere in pipeline |
| `packages/pipeline/src/pipeline/agents.py:151-160` | Debug HTML comment | Debug transcript only | `call: {label} | service=… | model=…`; no wall ms, no usage |
| `packages/whisker/src/whisker/tapetum_llm/readback.py:282-310` | `latency_ms` | Readback Q&A only | Precedent pattern; not tapetum sidecar |

## What is missing from LLM sidecars

Both lane serializers omit per-call data:

- **PDF lane:** `PdfJudgeResult.to_sidecar_dict()` (`pdf_judge.py:455-561`) — verdict, coverage, unit audit; no `call_timings`, no token usage.
- **Text lane:** `TapetumResult.to_dict()` (`models.py:363-398`) — cascade verdict fields only.
- **Error tombstone:** `cli.py:820-824` — `status`, `error`; no `duration_seconds`, no partial timings.
- **VLM lane (dormant):** `vlm_diff.py:82-121` — same gap if wired later.

`judge_task.run_judge_task()` (`judge_task.py:52-74`) is the single dispatch choke for PDF/metadata/unit/page calls; it records nothing beyond forwarding `label` to `AgentBackend.run`.

Text-lane tier-1/tier-2 calls bypass `run_judge_task` and go through `run_agent()` (`runner.py:266-272`, labels = step names `"1. Triage"` / `"2. Adjudicate"` from `adjudicate.py:650-651`).

Ideal verification uses `run_task()` (`ideal_verify.py:151-158`, label `IDEAL_VERIFY_TASK_LABEL`); also untimed.

Backend reads HTTP responses but does not surface `usage` to whisker (`model_backends.py:330-340` assigns content/finish_reason only; no prompt/completion token export).

Prior fleet parse: 204 sidecars, zero timing keys beyond paper-level `duration_seconds` where present (`research/tapetum-llm-speedup/79-olmocr-metrics-observability.md:10`, `packages/whisker/research/llm-batching/17-latency-decomposer.md:8`).

## P96 playbook = two measurement planes

**P79** (client / sidecar): per-call wall + optional token fields in each `*.whisker.tapetum.json`, plus fleet rollup file.

**P96** (server / scrape): 10 s `/metrics` JSONL during the run (`research/tapetum-llm-speedup/96-vllm-metrics-probe.md:14-48`) — queue, prefill, decode, prefix-cache deltas. Cross-check client `call_timings[].wall_ms` against server phase histograms; never use lifetime pod counters alone.

Prerequisite stated in synthesis: no lever claim (prefix cache, metadata short-circuit, dual-pod) is measurable without both planes (`research/tapetum-llm-speedup/SYNTHESIS.md:66`, `research/cold-run-10min/10-impl-status-auditor.md:19,33`).

## Fields to add

### 1. Per sidecar — `call_timings[]` (required for P79)

Append at persist time or in result serializers. **Do not add to fingerprint keys** (`cli.py:595-648`); observability must not invalidate incremental skip.

Each element:

```json
{
  "label": "pdf-judge-P1234R0",
  "call_class": "monolith",
  "wall_ms": 19842,
  "status": "ok",
  "attempts": 1
}
```

**`call_class` enum** (derive from `label` prefix or explicit arg):

| `call_class` | Typical `label` pattern | PDF | HTML/text |
|---|---|---|---|
| `monolith` | `pdf-judge-{pid}` | yes | — |
| `metadata_outline` | `metadata-outline-{pid}` | yes | yes |
| `unit_check` | `unit-check-{pid}-{unit_id}` | yes | yes |
| `page_escalation` | `pdf-judge-page-{n}` | yes | — |
| `tier1_triage` | `1. Triage` (step name) | — | yes |
| `tier2_adjudicate` | `2. Adjudicate` | — | yes |
| `tier1_chunk` | `1. Triage` (chunked paper) | — | yes (N entries) |
| `ideal_verify` | `ideal-verify` (constant) | optional | optional |

Optional phase-2 fields (needs pipeline approval or response parsing in whisker):

- `prompt_tokens`, `completion_tokens`, `finish_reason`
- `timeout_s` (configured cap: `constants.py` monolith/unit/page timeouts)
- `queue_ms` (only if `--enable-per-request-metrics` on pod)

Keep **`duration_seconds`** as paper-level end-to-end wall (already shipped). Optionally add **`llm_wall_ms`** = sum of `call_timings[].wall_ms` for quick sanity check vs `duration_seconds` (difference = CPU grounding, `screen_pages`, table compare, ideal verify overhead).

### 2. Error tombstone — partial timings

When `partial_progress` is written (`cli.py:806-826`), also attach:

- `call_timings[]` for calls completed before failure
- retain existing `partial_progress.phase` / unit ids (`pdf_judge.py:916-935`, `1033-1050`)

### 3. Fleet rollup — `whisker/llm/run-manifest.json` (P79 §3)

Write once after batch `asyncio.gather` (`cli.py:1507-1542`):

```json
{
  "run_id": "20260724T120000Z",
  "wall_s": 3003.4,
  "concurrency": 32,
  "papers_evaluated": 375,
  "papers_skipped": 6,
  "model_retries": 55,
  "calls_by_class": {"monolith": 181, "metadata_outline": 381, "unit_check": 1510},
  "sum_wall_ms_by_class": {"monolith": 3620000, "unit_check": 28000000}
}
```

Aggregate by scanning sidecars just written (same pattern as `_build_merged_report`, `cli.py:854-883`).

### 4. Server scrape — P96 JSONL columns (not in sidecar)

From `96-vllm-metrics-probe.md:23-42`: `ts`, `running`, `waiting`, `waiting_capacity`, `kv_cache_usage`, `prefix_queries`, `prefix_hits`, `gen_tokens`, TTFT/TPOT/queue/prefill/decode `_sum/_count` deltas per 10 s sample.

Store under `_scratch/` (not sidecar schema). Join to fleet run via overlapping `run_id` + timestamps.

## Call-site inventory (labels today)

| File:line | Function | Label |
|---|---|---|
| `pdf_judge.py:678` | monolith | `pdf-judge-{pid}` |
| `unit_judge.py:269` | metadata | `metadata-outline-{pid}` |
| `unit_judge.py:804` | unit check | `unit-check-{pid}-{unit_id}` |
| `pdf_judge.py:408` | page escalation | `pdf-judge-page-{page_num}` |
| `adjudicate.py:245-259` | tier1 (incl. chunks) | step name via `run_agent` |
| `adjudicate.py:307-309` | tier2 | step name via `run_agent` |
| `ideal_verify.py:156` | ideal | `IDEAL_VERIFY_TASK_LABEL` |

Metadata + unit checks on HTML path: `adjudicate.py:512-554`. PDF unit path inside `judge_pdf_extraction`: `pdf_judge.py:702-945`.

## Patch sites (file:line)

Implementation order: instrument dispatch → collect on results → persist → fleet rollup → tests.

| Priority | File:line | Change |
|---|---|---|
| P0 | `judge_task.py:52-74` | Add optional `timings: list[dict] \| None`; wrap `agent.run` with `time.monotonic()`; append `{label, call_class, wall_ms, status, attempts}` |
| P0 | `judge_task.py:52-74` | Add `call_class: str` param (or map from label prefix) |
| P0 | `pdf_judge.py:568-590` | Add `timings: list[dict] \| None = None` to `judge_pdf_extraction`; pass through all `run_judge_task` / `run_metadata_outline_check` / `run_unit_checks` / `_escalate_page` |
| P0 | `unit_judge.py:240-273` | Thread `timings` into `run_metadata_outline_check` |
| P0 | `unit_judge.py:760-807` | Thread `timings` into per-unit `run_judge_task` |
| P0 | `pdf_judge.py:415-453` | Add `call_timings: list[dict]` field on `PdfJudgeResult` |
| P0 | `pdf_judge.py:455-561` | Emit `"call_timings": self.call_timings` in `to_sidecar_dict()` |
| P1 | `adjudicate.py:753-821` | After `dispatch`, map `ctx.step_metrics` + custom-hook timings into unified `call_timings` on `TapetumResult` (step metrics alone are insufficient: they merge LLM + Python) |
| P1 | `adjudicate.py:244-310` | Prefer wrapping `run_agent` calls with whisker-local timer (same shape as judge_task) inside `_custom_triage` / `_custom_adjudicate` |
| P1 | `models.py:324-398` | Add `call_timings: list[dict]` to `TapetumResult`; include in `to_dict()` |
| P1 | `ideal_verify.py:134-158` | Accept `timings` sink; record ideal call |
| P1 | `cli.py:1219-1241` | Pass shared `timings` list into `judge_pdf_extraction` / collect from `adjudicate_paper` return |
| P1 | `cli.py:719-776` | Merge result `call_timings` into payload in `_persist_lane_result` / `_persist_result` (if not already on result object) |
| P2 | `cli.py:794-826` | On error, persist partial `call_timings` alongside `partial_progress` |
| P2 | `cli.py:1507-1542` | Write `run-manifest.json` after batch |
| P2 | `cli.py:595-648` | Document / test: fingerprint keys unchanged when only timings differ |
| P3 | `packages/whisker/tests/test_tapetum_llm.py:3102-3147` | Extend duration tests for `call_timings[]` presence and fingerprint exclusion |
| P3 | `packages/whisker/tests/test_pdf_judge.py` | Assert sidecar schema includes `call_timings` on mock judge path |
| Future | `model_backends.py:330-370` | Return usage dict (pipeline change; needs explicit boundary approval) |
| Future | `vlm_diff.py:82-121` | Same `call_timings` contract when VLM lane ships |

## Fingerprint / skip invariant

`_compute_fingerprint()` hashes inputs only (`cli.py:625-648`). **`call_timings` must never enter that dict.** Sidecar observability fields (`duration_seconds`, future `call_timings`) are persist-layer overlays, same as `fusion` and `fingerprint` blocks.

## False-pass / false-fail guards (from P79)

- **False-pass:** logging `wall_ms` without `attempts` hides BPE retry pairs (fast fail + slow success) as two "normal" calls.
- **False-fail:** hashing `call_timings` into fingerprint would force full re-judge on jitter-identical verdicts.

## Cross-references

- P79 design: `research/tapetum-llm-speedup/79-olmocr-metrics-observability.md:22-23`
- P96 scrape playbook: `research/tapetum-llm-speedup/96-vllm-metrics-probe.md`
- Impl status: `research/cold-run-10min/10-impl-status-auditor.md:19,33`
- Latency back-solve (why per-call class matters): `packages/whisker/research/llm-batching/17-latency-decomposer.md`
