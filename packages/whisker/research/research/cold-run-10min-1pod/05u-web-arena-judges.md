# 05u - Web: Arena-Hard / AlpacaEval / MT-Bench judge implementations

**Verdict:** usable — all three stacks already encode the two levers this corpus needs (decode shrink + client fan-out sized to judge latency class), not a second MoE replica.
**Confidence:** high (claims pinned to public configs / scripts; quality transfer to tapetum still needs A/B)

**Date:** 2026-07-24. Scope: model-size and concurrency tricks only. Cloud-judge brand names appear as historical defaults in those repos; this corpus forbids cloud LLM judges for production (see `00-baseline.md`).

---

## Findings

- [CRITICAL] AlpacaEval 2.0 judge is a **1-token logprob classifier**, not a long rationale. Evidence: `tatsu-lab/alpaca_eval` `evaluators_configs/weighted_alpaca_eval_gpt4_turbo/configs.yaml` sets `max_tokens: 1`, `logprobs: true`, `top_logprobs: 5`, `fn_completion_parser: logprob_parser`, `batch_size: 1`. Impact: collapses judge decode length `L` toward one token; largest portable cut to per-call wall when unit checks today emit multi-hundred-token JSON.

- [HIGH] Arena-Hard-Auto sizes **client `parallel` per endpoint / model class**, not globally. Evidence: `lmarena/arena-hard-auto` `config/api_config.yaml` — `gpt-4.1` `parallel: 64`, `gemini-2.5` `parallel: 16`, `gpt-4o-mini` `parallel: 128`, local `gemma-3-27b-it` `parallel: 128`, heavier Claude/DeepSeek entries `parallel: 32`. Judgment loop uses `ThreadPoolExecutor(max_workers=endpoint_settings["parallel"])` in `gen_judgment.py`. Impact: dense offload lanes (`h200-qwen3-32b`, etc.) can take higher client fan-out than `alliance-pod` S=16 without raising MoE `--max-num-seqs`.

- [HIGH] MT-Bench separates **answer-gen concurrency** from **judge concurrency**, and recommends single-answer grading over pairwise. Evidence: FastChat `llm_judge/README.md` — judge `gen_judgment.py --parallel N` (default `1`); vLLM answer path `gen_api_answer.py --parallel 50`; default mode `single` (score 1–10) vs `pairwise-baseline` / `pairwise-all`. Impact: pairwise multiplies N; single-answer / absolute rubric cuts call count. Shuffle-before-map (`np.random.shuffle(matches)` then `ThreadPoolExecutor`) balances long vs short judge prompts.

- [MED] AlpacaEval also batches **multiple examples into one prompt** when the system prompt is long. Evidence: `alpaca_farm_greedy_gpt4` config `batch_size: 5`, `max_tokens: 250`. Docs: batching "decreases cost and time for annotations if the prompt is long." Impact: amortizes shared rubric prefill; orthogonal to 1-token logprob path (which keeps `batch_size: 1`).

- [MED] Local / smaller judges are first-class in Arena-Hard configs. Evidence: `api_config.yaml` ships `gemma-3-27b-it` (OpenAI-compatible local) and `qwq-32b` (SGLang `local_engine`) alongside proprietary judges; README points at vLLM/SGLang OpenAI servers. Impact: matches dense-offload thesis in `12-dense-offload-architecture.md` — 27B–32B class is the throughput lane, not a second V4-Pro.

- [MED] Caching / skip-existing is universal. Evidence: Arena-Hard skips UIDs already in `model_judgment/`; AlpacaEval caches annotation triples; MT-Bench writes append-style judgment jsonl. Impact: warm / resume path only; does not move cold wall, but prevents double-spend during A/B.

- [LOW] AlpacaEval default API concurrency is conservative (`OPENAI_MAX_CONCURRENCY` / `API_MAX_CONCURRENCY` default **5**, overridable via env). Evidence: `alpaca_eval/constants.py`. Impact: their defaults are rate-limit-safe for paid APIs; self-hosted dense pods should raise this toward server `max-num-seqs`, not copy the cloud default of 5.

---

## Portable trick

**Verdict-token decode:** force the judge to emit a **single classification token** (or tiny enum) and read the decision from **logprobs**, with `max_tokens=1`. Pair with **per-lane client parallel** scaled to that judge's latency class (Arena-Hard: ~128 on 27B-class local, lower on heavy reasoners). Do not raise MoE S; raise dense-lane fan-out and shrink decode.

Mapping for this corpus:

| Lever | Upstream pattern | Tapetum use |
|-------|------------------|-------------|
| Shrink `L` | AlpacaEval `max_tokens: 1` + logprob parse | Unit / metadata verdict-first schema; cap decode |
| Raise useful concurrency | Arena-Hard per-endpoint `parallel` | Higher client c on dense pods only; keep alliance-pod S=16 |
| Cut `N` | MT-Bench prefer single-answer over pairwise | Absolute unit rubric, no pairwise tournament of units |
| Prefill amortize | AlpacaFarm `batch_size: 5` | Only if shared rubric ≫ answer; watch schema compliance |

Arithmetic sketch (illustrative, S_eff=16 on MoE unchanged): if ~1502 unit calls move dense and each drops from ~20 s free-form to ~2–4 s verdict-token at dense S≥32, that lane stops dominating cold wall; residual MoE ~400 calls × L / 16 still sets the floor (see `12-dense-offload-architecture.md`).

---

## False-pass hypothesis

Logprob-1 / tiny-enum judges agree on easy clears but miss subtle WG21 wording defects that only appear in long chain-of-thought rationales → false CLEARs rise if dense 1-token lane replaces MoE unit checks without 381/381 parity.

## False-fail hypothesis

Aggressive `max_tokens` caps or brittle token parsers (`m`/`M` style) reject valid structured output → retries inflate N and wall, or fail-closed aborts papers that would have passed under free-form JSON.

## What would change my mind

- Measured A/B: dense verdict-token unit lane vs current MoE unit schema on full 381, false-clear / false-fail within gate.
- Proof that logprobs are unavailable or non-deterministic on the target dense vLLM endpoint (then fall back to short constrained JSON, not 1-token).
- Evidence that raising dense client parallel past server S only adds TTFT / 524s (same failure mode as c>32 on alliance-pod).
