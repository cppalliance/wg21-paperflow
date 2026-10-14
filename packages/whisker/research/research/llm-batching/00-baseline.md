# llm-batching - Evidence Baseline (Step 0)

**Goal:** cut the tapetum_llm full-corpus wall time from ~36 min (observed) toward
single-digit minutes, using provider-style batching / higher parallelism, with
code changes confined to `packages/whisker` (pipeline/paperstore are READ-ONLY).

Date: 2026-07-07. Self-target; comparison codebase is our own stack plus the
cloned research repos.

## Measured runtime facts (ground truth, do not re-derive)

- Full candidate rerun, 2026-07-07, pod on vLLM **0.24.0**: **200 papers in
  2159.8 s (36 min) at `--concurrency 3`** = 10.8 s/paper effective. Result
  100 pass / 87 review / 10 fail / 3 error, **1 model retry total** (CJK class
  retired by the pod upgrade).
- 9-paper batch at c=3: 104.4 s (11.6 s/paper effective). 3-paper batch at
  c=3: 28.2-45.6 s depending on retries.
- Single-paper latency observed ~15-30 s => c=3 yields only ~2-3x, meaning the
  pod (or our client path) absorbs more concurrency than we currently request.
- P2728R11/R12 (chunked, 7 chunks serial) took 755.8 s for 2 papers BEFORE the
  data-URI strip filter; after stripping they are 1-chunk papers inside a 28 s
  batch of 3.
- Escalation rate after gate hardening: 13/197 papers add a second (tier-2)
  call on the same pod.

## Infrastructure facts

- `SERVICES.toml:64-74`: `alliance-pod`, backend `vllm_thinking`,
  `base_url = https://sgjy18glyi4blu-8000.proxy.runpod.net/v1`,
  model `deepseek-v4-pro`, `max_context_window = 393216`, `stream = true`,
  thinking-capable. Comment: "Runs 24/7; billed per hour of uptime, NOT per
  token, so run size is not a cost question."
- Pod `/version` probed live: `{"version": "0.24.0"}`. Server flags
  (`--max-num-seqs`, prefix caching, batch-invariant mode) are UNKNOWN to us;
  we only consume the API. A comparable community deployment of DeepSeek-V4-Pro
  on H200x8 used `--max-num-seqs 8` (vllm issue #42265 config dump).
- The twin pod `h200x8-deepseek-v4-pro` (`SERVICES.toml:47-57`) is a second,
  separate instance of the same model, reachable with its own key: a potential
  second lane for load-splitting WITHOUT any code change (`--service` flag).

## Client-path code anchors (what limits us today)

- Paper-level fan-out EXISTS: `packages/whisker/src/whisker/tapetum_llm/cli.py`
  `--concurrency N` (default 1), `asyncio.Semaphore(concurrency)` +
  `asyncio.gather`, per-paper firewall, input-order persistence. This is the
  only whisker-side throttle; raising N is a one-line default change.
- `run_agent` (`pipeline/runner.py:266-272`) calls `agent.run` DIRECTLY, no
  global semaphore on this path. The D3/D11 semaphores throttle only
  `run_task` (`pipeline/tasks.py:38,57`) and `dispatch`'s parallel branch,
  neither of which tapetum uses. So paper-level concurrency is genuinely
  concurrent down to the HTTP client.
- Fresh `AsyncOpenAI` client is constructed PER CALL
  (`pipeline/model_backends.py:283`, also `:443,:535,:627`): no connection/
  pool reuse across calls; default httpx limits and timeouts apply per client.
  Pipeline is read-only for us, so any pooling fix must be argued as
  infrastructure or parked.
- Agents are built with `max_tokens=4096` and NO thinking budget forwarded
  (`whisker/tapetum_llm/adjudicate.py:450-458`); the authority doc's per-step
  2048/1024 budgets are parsed but not forwarded by the runner (known parked
  finding from research/llm-stack).
- Chunked papers triage their chunks SERIALLY inside one paper
  (`whisker/tapetum_llm/adjudicate.py:_custom_triage`, comment "D11: one
  in-flight request at a time"). After the data-URI filter, almost no paper
  chunks anymore (only true >500k-char prose papers would).
- System prompt is shared and identical across ALL papers
  (`tapetum_llm/tapetum_llm.md` system section, ~8 KB): ideal prefix-caching
  candidate; whether the pod has `enable_prefix_caching` on is unknown.
- Every call streams (`stream = true`) and the raw-JSON path assembles chunks.

## Constraints (non-negotiable)

- Code changes ONLY in `packages/whisker`. `pipeline`, `paperstore`, root
  `MODELS.md` are read-only (user directive, enforced once already).
- CLAUDE.md determinism: D11 binds dissect, NOT the advisory lane; tapetum may
  opt into N>1 via its own CLI flag (already implemented and documented).
  Advisory lane never gates, so throughput > bit-stability here, but
  reproducibility of verdict DISTRIBUTIONS should not silently degrade
  (VLLM_BATCH_INVARIANT exists as the infra answer, ~50% throughput cost).
- Fidelity: a paper that fails still fails loudly; no partial results.
- The pod is operated by the CTO; server-side flags are requests, not edits.

## The quantitative question for every persona

Wall time now: T = ceil(200/3) * ~30 s ~= 36 min. Levers, to be validated:
(a) raise client concurrency N (does the pod's continuous batching absorb
N=8/16/32 without per-request latency collapse? where is the knee?),
(b) cut per-call latency (output tokens dominate decode time: shrink
`max_tokens`, shrink reasoning verbosity, guided JSON, prefix caching),
(c) split load across the two pods (fast slot -> pod A, deep slot -> pod B, or
shard papers), (d) provider-style async batch APIs (OpenAI /v1/batches,
Anthropic Message Batches): does vLLM 0.24 expose an equivalent server-side
endpoint, or is `vllm run-batch` offline-only and therefore NOT usable by us
(no shell on the pod)?

## Required report template (every persona uses exactly this)

```
# NN - <Persona name>

**Verdict:** usable | usable-with-conditions | garbage   (+ 1 sentence why)
**Confidence:** high | medium | low

## Findings
- [CRITICAL|HIGH|MED|LOW] <claim>. Evidence: <file:line OR runtime number from 00 OR URL>.
  Impact: <effect on the 36-min wall time or on safety of raising concurrency>.
  (3-8 findings, ranked)

## False-pass hypothesis
<a way this speedup silently degrades verdict quality, or "none found">

## False-fail hypothesis
<a way this speedup makes good papers fail spuriously, or "none found">

## What would change my mind
<the single piece of evidence that would flip my verdict>
```
