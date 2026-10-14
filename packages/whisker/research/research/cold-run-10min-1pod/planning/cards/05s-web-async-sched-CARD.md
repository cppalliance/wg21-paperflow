# CARD: 05s — vLLM #45257 async-scheduling underfill

## Bottom line
Real scheduler bug: under async scheduling, finished-but-not-drained seqs still consume `max_num_seqs`, so scheduled batch can underfill while waiting queues grow. At c=32 / S=16 this is ops hygiene (keep-or-disable A/B), not a reason to raise slots to 32. Upstream fix #45366 not merged (2026-07-24).

## Numbers
- Fixed: `S_eff=16`, client c=32; raising seqs to 32 measured **+57%** cold wall.
- Underfill hypothesis: mild churn → S_eff ~14–15 (**~+7–14%** compute term); short-OSL/`max_tokens≈1` style can drop far below 16.
- Signature: `num_requests_running≈16` + elevated waiting + soft GPU util / throughput.
- Does **not** close ≤600 s; at best recovers honest S=16 envelope.

## Architecture implication
Short-OSL / Non-think / verdict-first raises finish rate → higher underfill risk exactly when cutting L. Treat async-scheduling as optional (not required by V4-Pro H200 recipe). Never paper over underfill with higher `--max-num-seqs`.

## Reject-or-A-B
- **Ops A/B:** confirm async on/off; if underfill signature → `--no-async-scheduling`; keep S=16.
- **Reject:** “fix” by `max-num-seqs` 16→32; blocking cold-run plan on unmerged #45366.
- **Re-enable async** only after image includes merged #45366 (or cherry-pick) and A/B shows L down with waiting flat.

## Links
- Source: `05s-web-async-sched.md`
- Related: `00-baseline.md`, `11-wall-arithmetic-1pod.md`, slots-32 regression, `41-vllm-github-issues.md` Card 2
- https://github.com/vllm-project/vllm/issues/45257
- https://github.com/vllm-project/vllm/pull/45366
