# 00 - Baseline: tapetum-llm cold fleet run 50 min -> target 5-10 min, same quality

Research question: the cold `whisker-tapetum-llm` fleet run (381 papers) takes
**3003 s (~50 min)**. Target: **5-10 min maximum with the SAME finding quality**
(same defect classes caught, same fail-closed semantics, quality-stability across
runs). What does our architecture do worse than comparable systems (docling,
langextract, marker, olmocr, vLLM-based pipelines, LLM-judge harnesses), and which
of their techniques are portable?

This is a SPEEDUP study, not another why-is-it-slow study. The why is settled
(research/tapetum-llm-throughput/SYNTHESIS.md): call volume by design, not lost
concurrency. Every persona must propose or evaluate LEVERS, each with a
quality-impact assessment.

## Hard numbers (measured 2026-07-23, workspace HEAD with v10 fixes)

- Cold fleet run (v10, `_LANE_VERSION` bump): **3003.4 s**, 381 papers evaluated,
  37 pass / 295 review / 43 fail / 6 error, 55 model retries.
- Warm run right after: **64.8 s**, 375/381 skipped (fingerprint), only the 6
  error-tombstone papers re-tried.
- Call census (from tapetum-llm-throughput, sidecar aggregation over 381 papers):
  ~**2284 LLM calls total** = 381 monolith + 377 metadata/outline + ~1510 unit
  checks (median 5 = MAX_UNIT_CHECKS) + ~16 page escalations. **6.0 calls/paper.**
- Implied per-call latency ~**20 s** at 16 concurrent server slots.
  Wall ~= calls x latency / slots = 2284 x 20 / 16 ~= 2855 s. The model closes.
- Decode speed on the pod: ~**70 tok/s per request** (decode-bound; docstring
  `pdf_judge.py:27`). Unit-check output cap 1536 tokens (`cli.py` judge agent),
  reasoning capped at 40-60 words by prompt.
- 70% of unit checks (1057/1510) returned ZERO defect groups. Only 16/381 papers
  had their merged verdict changed by LLM findings (~143 calls per changed verdict).

## Architecture facts (file:line anchors)

- Client concurrency: `_DEFAULT_CONCURRENCY = 32` papers in flight
  (`cli.py:125`), semaphore at `cli.py:1096`, `asyncio.gather` at `cli.py:1369`.
- **Within one paper everything is SERIAL**: monolith call -> metadata/outline
  call -> 0-5 page escalations (serial loop `pdf_judge.py:753`) -> 0-5+ unit
  checks (serial loop `unit_judge.py:379+`). A 6-call paper spends ~120 s of
  serial wall regardless of fleet concurrency. `judge_task.py` bypasses the
  global pipeline Semaphore(1); the advisory lane is exempt from D11 per
  CLAUDE.md ("Only this advisory LLM lane adds cross-paper concurrency:
  requests within one paper remain serial").
- Unit checks send the **FULL candidate markdown** per call
  (`unit_judge.py:_check_one_unit`, user_msg includes entire `candidate_md`)
  plus one page's source text. Monolith sends full PDF text + full markdown.
  Page escalations send one page + full markdown. So a 6-call paper prefills
  the whole document ~6x.
- Shared system-prompt prefix: `CONVERSION_CONTRACT` (~3.7k chars) is embedded
  in JUDGE_SYSTEM_PROMPT, PAGE_JUDGE_SYSTEM_PROMPT, and UNIT_CHECK_SYSTEM_PROMPT
  (`unit_judge.py:70`, `pdf_judge.py:180/215`). BUT each call appends a fresh
  random guard tag (`guard_instruction(tag)`, tag = `SRC{secrets.token_hex(4)}`),
  which breaks prefix identity at the very END of the system prompt only.
- Timeouts: `UNIT_CHECK_TIMEOUT_SECONDS = 120`, `PAGE_ESCALATION_TIMEOUT_SECONDS
  = 120` (`constants.py:197,241`), paper budget 900 s + additive terms
  (`cli.py:152`).
- Caps: `MAX_UNIT_CHECKS = 5`, `MAX_PAGE_ESCALATIONS = 5` (`constants.py:191,223`).
- Incremental skip is PER PAPER (whole-paper fingerprint, `cli.py:565+`).
  A changed markdown re-runs the entire 6-call cascade even if only one page
  changed. No per-unit fingerprint exists.
- Retry budget: known BPE-corruption artifact, attempt 2 succeeds; 55 retries
  ~ 100 s wall total (~4%).

## Infrastructure inventory (SERVICES.toml)

- `alliance-pod`: vLLM, **deepseek-v4-pro** (MoE), 393k context, runs 24/7,
  billed per uptime-hour not per token. Server `--max-num-seqs 16`.
- `h200x8-deepseek-v4-pro`: **SAME MODEL, separate instance** (dual-pod sharding
  is infrastructurally available TODAY).
- Additional live pods: `b200-r1` (70B distill), `b200x2-gemma4` (31B),
  `b300-qwen36-27b`, `b300-qwen3-235b` (FP8), `h200-qwen3-32b` (dense 32B).
  A dense 32B decodes SUBSTANTIALLY faster than a MoE V4-pro per token.
- Model sovereignty rule (CLAUDE.md): open-weight self-hosted only for
  production. All listed pods qualify.

## Constraints (what personas may NOT propose without flagging it)

- Quality-stability: same findings, same verdicts, same structure across runs.
  Any lever must state its verdict-drift risk.
- Fidelity: no partial results; fail-closed coverage semantics stay.
- Measured negative results (do not re-propose blindly):
  client concurrency > 32 broke at 381 (research/concurrency-381);
  server max-num-seqs 16 -> 32 = +60% wall (research/slots-32-regression);
  MoE guidance says max-num-seqs 4-8 for DeepSeek-class, 16 is already high.
- Cutting MAX_UNIT_CHECKS, shrinking schemas/quote budgets: forbidden by
  fidelity rules unless a persona shows equivalent-quality evidence.
- D-rules: no per-call temperature/seed overrides; structured output stays.

## Known open levers (personas must quantify, not just name them)

1. Call elimination: router precision (70% zero-defect checks), metadata-fail
   short-circuit, monolith/unit redundancy, zero-defect prediction.
2. Per-call latency: output-token reduction (decode-bound!), thinking-token
   suppression, prefix caching (guard tag placement!), payload scoping (stop
   sending full markdown 6x per paper).
3. Parallelism: in-paper parallel unit checks (advisory lane exempt from D11;
   MoE batch-composition variance is the risk), dual-pod/multi-pod sharding
   (same model on 2 pods NOW), longest-job-first scheduling.
4. Batching: multi-unit prompts (N pages in one call), vLLM offline batch
   mode, cross-paper memoization.
5. Model: smaller dense judge for unit checks (h200-qwen3-32b), cascade
   (cheap model first, DeepSeek only on flags), speculative decoding, FP8 KV.
6. Incremental: per-unit fingerprints (changed paper re-judges changed pages
   only).

## Comparison anchors in our code

- `packages/whisker/src/whisker/tapetum_llm/cli.py` (concurrency, fingerprint,
  timeout budgets)
- `packages/whisker/src/whisker/tapetum_llm/pdf_judge.py` (serial per-paper chain)
- `packages/whisker/src/whisker/tapetum_llm/unit_judge.py` (unit checks, payload)
- `packages/whisker/src/whisker/tapetum_llm/judge_task.py` (dispatch, retries)
- `packages/pipeline/src/pipeline/` (AgentBackend, model backends, run_task gate)

## External targets (shallow clones under research/repos/)

docling, langextract, marker, olmocr, MinerU, unstructured, vllm, sglang,
nougat, surya, deepeval, promptfoo, ragas, litellm.

Key questions per repo: how do they bound LLM/VLM call count per document; how
do they parallelize within and across documents; what payload do they send per
call (scoped vs full-document); how do they cap output tokens; which server
flags/configs do they ship for vLLM/sglang; do they cache/memoize; what do they
sacrifice for speed and what do they refuse to sacrifice.

## Required persona report template

# NN - <Persona name>

**Verdict:** usable | usable-with-conditions | garbage   (+ 1 sentence why)
**Confidence:** high | medium | low

## Findings
- [CRITICAL|HIGH|MED|LOW] <claim>. Evidence: <file:line OR runtime number from 00>.
  Impact: <expected wall-clock saving on the 3003 s cold run AND quality risk>.
  (repeat; 3-8 findings, ranked)

## False-pass hypothesis
<one concrete case where a proposed speedup would silently degrade finding quality, or "none found">

## False-fail hypothesis
<one concrete case where a speedup would wrongly reject/flag a good conversion, or "none found">

## What would change my mind
<the single piece of evidence that would flip my verdict>
