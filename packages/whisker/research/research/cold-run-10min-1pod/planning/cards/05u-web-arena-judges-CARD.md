# CARD: 05u — Arena-Hard / AlpacaEval / MT-Bench judge patterns

## Bottom line
Eval harnesses already encode the two levers this corpus needs: shrink judge decode (AlpacaEval 1-token logprob classifier) and size client fan-out per endpoint latency class (Arena-Hard), not a second MoE replica. Prefer single-answer grading over pairwise (MT-Bench) to cut N.

## Numbers
- AlpacaEval weighted GPT-4 Turbo judge: `max_tokens: 1`, logprobs, `batch_size: 1`.
- Arena-Hard `parallel`: gpt-4.1 **64**, gemini-2.5 **16**, gpt-4o-mini / gemma-3-27b-it **128**, heavy Claude/DeepSeek **32**.
- MT-Bench: answer-gen `--parallel 50` vs judge default **1**; mode `single` preferred over pairwise.
- AlpacaFarm batching: `batch_size: 5`, `max_tokens: 250` when system prompt is long.
- AlpacaEval default API concurrency **5** (cloud rate-limit safe — do not copy onto self-host dense).
- Sketch: ~1502 unit calls dense at ~2–4 s verdict-token vs ~20 s free-form; MoE residual still floors wall at S=16.

## Architecture implication
Portable trick: verdict-token / tiny-enum + logprobs; raise client c on dense lanes only; keep alliance-pod S=16. Absolute unit rubric, no pairwise tournament. Caching/skip-existing is warm-path only (does not move cold wall).

## Reject-or-A-B
- **A/B:** dense verdict-token unit lane vs MoE unit schema on full 381 (false-clear / false-fail gate).
- **Reject:** raising MoE `--max-num-seqs`; copying cloud concurrency defaults of 5 onto dense pods.
- **Fallback:** if logprobs unavailable/non-deterministic → short constrained JSON, not 1-token.

## Links
- Source: `05u-web-arena-judges.md`
- Related: `12-dense-offload-architecture.md`, `15-verdict-first-design.md`, `00-baseline.md`
- `tatsu-lab/alpaca_eval` configs; `lmarena/arena-hard-auto` `api_config.yaml`; FastChat `llm_judge`
