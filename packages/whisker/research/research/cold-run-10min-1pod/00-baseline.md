# 00 - Baseline: cold-run ≤10 min on ONE pod (no twin)

**Hard constraint (operator, 2026-07-24):** No second DeepSeek pod. No budget
or authority to revive `h200x8-deepseek-v4-pro`. All plans must assume
**only `alliance-pod`** (DeepSeek-V4-Pro, 16 server slots, client c=32).

**Goal:** Cold `whisker-tapetum-llm` fleet 381 papers → **≤600 s (~10 min)**
on that single pod, same finding quality (fail-closed, quality-stability).

**Prior corpus (cite, do not rediscover dual-pod as the answer):**
`research/tapetum-llm-speedup/SYNTHESIS.md`,
`research/cold-run-10min/SYNTHESIS.md`.
Those corpora proved dual-pod is the clean path to ~596 s. **This corpus
exists because that path is forbidden.** Dual-pod recommendations are
**out of scope** unless framed as "blocked / not available."

## Settled numbers

| Metric | Value |
|--------|------:|
| Cold wall (v10) | 3003 s |
| Calls | ~2284 (~6/paper) |
| Server slots / client c | 16 / 32 |
| Per-call | ~20 s |
| Warm | 64.8 s |
| v11 short-circuit (working tree) | ~−1059 to −1341 s of fusion-dead units |
| Single-pod MODERATE (prior math) | **~1366–1493 s (~23–25 min)** — misses 10 min |
| Gap to 600 s after MODERATE | **~800–900 s still needed on one pod** |

## What is FORBIDDEN in this corpus

- Revive / require twin pod
- Raise `--max-num-seqs` to 32 (+57% wall measured)
- Raise client c>32 (RunPod 524 / TTFT)
- Drop verification / fail-open
- Cloud LLM judges
- "Just use docling" (wrong workload class)

## What IS in scope

Anything that cuts **N** (calls), **L** (per-call decode/prefill), or
**client waste** on one pod:

1. Call elimination beyond metadata short-circuit (router, MAX_UNIT_CHECKS,
   deterministic metadata, escalation, fail-fast)
2. Decode shrink (verdict-first schema, max_tokens, Non-think / Flash tradeoffs)
3. Dense-judge offload onto **existing** live dense pods in SERVICES.toml
   (`h200-qwen3-32b`, `b200x2-gemma4`, `b300-qwen36-27b`, `b200-r1`) — these
   are NOT a second V4-Pro; they are different models already paid for
4. Server flags on alliance-pod only (MBT, MTP, DeepEP, DBO, CUDA graphs, APC)
5. DeepSeek-V4 / vLLM community: Non-think, Flash vs Pro, reasoning_effort,
   serving recipes for single-node H200
6. Similar tech stacks: DeepEval, Ragas, promptfoo, SLMJury, JudgeLM distill,
   other MoE judge fleets on one endpoint

## Dense offload is NOT "second pod"

Second pod = second identical DeepSeek-V4-Pro replica (blocked).
Dense offload = route unit checks to an **already-running** smaller dense
model on a different Alliance endpoint. Quality A/B required. Budget for
those pods is assumed already sunk (24/7 Alliance fleet).

## Required persona report template

```
# NN - <Persona name>

**Verdict:** usable | usable-with-conditions | garbage   (+ 1 sentence why)
**Confidence:** high | medium | low

## Findings
- [CRITICAL|HIGH|MED|LOW] <claim>. Evidence: <file:line OR runtime OR URL>.
  Impact: <how it moves single-pod wall toward ≤600 s>.
  (3-8 findings)

## False-pass hypothesis
...

## False-fail hypothesis
...

## What would change my mind
...
```

## Arithmetic obligation

Every persona that claims a path to ≤600 s must show:
`wall = (N_rem × L_eff) / 16 + T + C − L_abs`
with **S_eff fixed at 16**. No silent S=32.
