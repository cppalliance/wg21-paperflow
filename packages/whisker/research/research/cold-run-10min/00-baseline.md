# 00 - Baseline: cold-run 48 min -> 10 min (delta research 2026-07-24)

**Goal:** Cut cold `whisker-tapetum-llm` fleet wall time from ~48-50 min to
**~10 min** on `alliance-pod` / DeepSeek-V4-Pro, without degrading finding quality.

**Prior work (must cite, do not rediscover):**
`research/tapetum-llm-speedup/SYNTHESIS.md` (2026-07-23, HEAD 51cb704, 150 agents).
Verdict already: MODERATE package → **~596 s central (9-11 min)**.

This corpus is a **delta**: implementation readiness, code drift since that
synthesis, fresh external serving research, and whether anything NEW beats the
already-ranked levers.

## Hard numbers (settled)

| Metric | Value | Source |
|--------|-------|--------|
| Cold wall (v10 accounting) | 3003.4 s (~50 min) | tapetum-llm-speedup/00-baseline.md |
| Cold wall (throughput footer) | 2883-2886 s (48.1 min) | tapetum-llm-throughput/00-baseline.md |
| Warm wall | 64.8 s (375/381 skip) | speedup/46-warm-run-auditor.md |
| Papers / LLM calls | 381 / ~2284 (~6.0/paper) | speedup synthesis |
| Server slots / client c | 16 / 32 | SERVICES.toml ops + cli.py |
| Per-call implied | ~20 s at 16 slots | wall ≈ calls × lat / slots |
| Decode vs prefill | 5.91 s vs 0.46 s mean | speedup P146 |
| Fusion-dead unit calls | 44.6% (1047 calls) after metadata fail/review | speedup P145 |
| Zero-defect unit checks | 70% (1057/1510) | speedup baseline |
| 32 server slots | **+57% wall** — forbidden | slots-32-regression |
| c>32 / submit-all-381 | proxy 524 / 600s timeout risk — forbidden | concurrency-381 |

## Settled lever ranking (from prior SYNTHESIS — re-verify, do not invent rivals without evidence)

1. Metadata-fail short-circuit (~1341 s) — verdicts unchanged when stripped
2. HMAC guard tag + prompt reorder (APC reuse of document payload)
3. Verdict-first / terse pass schema (~180-360 s, overlaps #1)
4. Dual-pod shard alliance-pod + h200x8-deepseek-v4-pro (~1.9× on remainder)
5. Error tombstone fingerprints (warm 65→10-15 s)
6. Client stalls: to_thread, LJF, monolith wait_for (~90-220 s)
7. AGGRESSIVE: deterministic metadata diff (~471 s), dense-judge offload

## This delta's open questions

1. Which levers from SYNTHESIS are **already implemented** at HEAD vs still paper-only?
2. Is `h200x8-deepseek-v4-pro` **alive** today? Dual-pod is the biggest infra multiplier.
3. Fresh (post-2026-07-23) DeepSeek-V4 / vLLM serving tricks: MTP, MoE batch, APC, tokenizer-mode.
4. Can dense pods (`h200-qwen3-32b`, `b200x2-gemma4`, etc.) take unit-check load without quality collapse?
5. Exact arithmetic to **≤600 s** with only CONSERVATIVE+MODERATE (no AGGRESSIVE).
6. Implementation order with smallest A/B cost first.

## Constraints (non-negotiable)

- Quality-stability across runs; fail-closed; no partial results mistaken for complete.
- Do not raise server slots to 32. Do not raise client c>32 without new evidence.
- Do not propose "drop verification" or "use GPT-4o batch API".
- Images/VLM skipped for now (operator note).
- Dissect D11 serial path must stay untouched; tapetum uses `judge_task.py` exemption.

## Comparison codebase anchors

- `packages/whisker/src/whisker/tapetum_llm/cli.py` — concurrency, lane version, fleet gather
- `packages/whisker/src/whisker/tapetum_llm/unit_judge.py` — unit checks, full-md payload
- `packages/whisker/src/whisker/tapetum_llm/pdf_judge.py` — monolith / page escalation
- `packages/whisker/src/whisker/tapetum_llm/judge_task.py` — D11 bypass
- `SERVICES.toml` — alliance-pod, h200x8-deepseek-v4-pro
- `research/tapetum-llm-speedup/SYNTHESIS.md` — prior verdict

## Required persona report template

```
# NN - <Persona name>

**Verdict:** usable | usable-with-conditions | garbage   (+ 1 sentence why)
**Confidence:** high | medium | low

## Findings
- [CRITICAL|HIGH|MED|LOW] <claim>. Evidence: <file:line OR runtime number from 00>.
  Impact: <why it moves wall time toward/away from 10 min>.
  (repeat; 3-8 findings, ranked)

## False-pass hypothesis
<one concrete case a speed lever would wrongly accept, or "none found">

## False-fail hypothesis
<one concrete case it would wrongly reject, or "none found">

## What would change my mind
<the single piece of evidence that would flip my verdict>
```
