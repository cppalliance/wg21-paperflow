# 21 - Output-Discipline Prompt (executed 2026-07-07)

Follow-up to the c=16 rerun (20-sweep-results.md). Goal: push 9.3 min
toward 4 min with client-side levers only.

## Probe: the thinking hypothesis was wrong

A live probe (4 conditions, real 40k-char paper, `_debug_thinking_probe.py`,
deleted after) against alliance-pod (vLLM 0.24.0, DeepSeek V4 Pro):

| Condition | Wall | completion_tokens | reasoning |
|-----------|------|-------------------|-----------|
| A baseline (production path)      | 13.7 s | 948  | none |
| B `chat_template_kwargs thinking=true` | 26.5 s | 2048 (cap hit) | none separated |
| C `thinking_token_budget=512`     | 12.7 s | 975  | ignored by server |
| T terse-instruction               | 7.7 s  | 496  | none |

Findings:

- **DeepSeek V4 Pro emits no reasoning content on this template by
  default.** There is no thinking phase to cap; the `thinking-budget`
  step meta is a dead knob for this pod (server ignores
  `thinking_token_budget` silently).
- Latency is decode-bound at ~70 tok/s solo: call duration is linear in
  output length. **Output length is the only per-call client lever.**
- The terse variant halved output tokens and still found the same real
  defects (table structure break included).

## Change

`tapetum_llm.md` system prompt gained a binding "Output discipline"
section: reasoning <= 60 words, axis notes <= 12 words, <= 3 evidence
spans of <= 20 verbatim words, no rubric restating. Judgment, axis
coverage, and severities explicitly unaffected. No Python changes.

## A/B on the fixed 20-PID set (c=16)

- Wall: **57.6 s** vs ~90 s pre-change (36 % faster), 0 errors/retries.
- Verdicts: 10 pass / 10 review / 0 fail vs baseline 12/7/1.
  7/20 flips, both directions (3 pass->review, 2 review->pass,
  1 fail->review, 1 pass->review). Comparable to the 5/20 flip rate
  measured between two IDENTICAL c=32 runs (20-sweep-results.md), so
  the drift is dominated by the known MoE batch non-invariance band,
  not by the prompt change.

## Full-corpus rerun (204 papers, c=16)

- **406.2 s (6.8 min)**, 2.0 s/paper effective, 0 errors, 0 retries.
- vs 556.3 s (9.3 min) with the verbose prompt: **27 % faster**;
  vs the 36 min c=3 baseline: **5.3x**.
- Verdict histogram 105 pass / 88 review / 11 fail
  (previous run: 118/75/11; within the established drift band).

## Why 6.8 min, not 4, and what 4 would take

Output tokens halved but wall fell only 27 %: under 16 concurrent
sequences the run is increasingly **prefill-bound**. Input is the whole
paper (~10-100k tokens each, ~3M prefill tokens per corpus) and cannot
shrink without breaking the fidelity mission (the adjudicator must see
the full document). Client concurrency above 16 only adds queue depth
(server `--max-num-seqs 16`). Remaining paths to ~4 min are
infrastructure: a second pod (halves everything), or a higher
`--max-num-seqs` with enough KV headroom (fp8 KV cache, 0.95 GPU util:
uncertain). Both are CTO territory, not whisker code.

For routine operation the practical time is lower anyway: only new or
re-converted papers need adjudication, so the 6.8 min figure is the
worst case (full-corpus re-run), not the steady state.
