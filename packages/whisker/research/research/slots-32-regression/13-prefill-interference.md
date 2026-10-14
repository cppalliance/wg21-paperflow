# 13 - Prefill-Interference-Auditor

**Verdict:** contributing — Raising `--max-num-seqs` 16→32 doubled in-flight sequences on a fixed 8192-token per-step budget, increasing prefill-decode contention and decode batch weight, but the measured +57% wall time matches MoE decode superlinearity (~1.57×) better than a pure 2× prefill-stall model (~1384 s predicted).
**Confidence:** high

## The token-budget math

### Pod defaults (only knob changed today)

| Parameter | Value | Source |
|-----------|-------|--------|
| `--max-num-seqs` | 16 → **32** (only change) | measured fact + `H200SXM.txt` |
| `--max-num-batched-tokens` | **8192** (unchanged, not in launch cmd) | vLLM 0.24 `EngineArgs.get_batch_defaults()` — H200 (≥70 GiB, non-A100) + `OPENAI_API_SERVER` → 8192 ([arg_utils.py v0.24.0](https://github.com/vllm-project/vllm/blob/v0.24.0/vllm/engine/arg_utils.py#L2387-L2391)) |
| `--enable-chunked-prefill` | **on** (V1 default) | [optimization docs v0.24](https://docs.vllm.ai/en/v0.24.0/configuration/optimization/) |
| `max_num_partial_prefills` | **1** (default) | [scheduler.py v0.24.0](https://github.com/vllm-project/vllm/blob/v0.24.0/vllm/config/scheduler.py) |
| `long_prefill_token_threshold` | **0** (no chunk cap; only budget caps) | same; threshold auto-set to 4%×max_model_len only when `max_num_partial_prefills > 1` |

**Key constraint:** `max_num_batched_tokens` is **not** auto-scaled when the user overrides `max_num_seqs`. The pod left token budget at 8192 while doubling sequence slots. vLLM requires `max_num_batched_tokens ≥ max_num_seqs` (8192 ≥ 32 ✓) but docs and `benchmarks/auto_tune/` treat the pair as co-tuned knobs ([auto_tune README](https://github.com/vllm-project/vllm/blob/main/benchmarks/auto_tune/README.md)).

### Per scheduler step (V1 unified budget)

V1 scheduler (`vllm/v1/core/sched/scheduler.py`) starts each step with `token_budget = max_num_scheduled_tokens` (= 8192 here) and walks **all running** requests FCFS until budget is exhausted. There is no hard decode/prefill phase split; a prefill request early in `running` can consume the entire remaining budget in one step, starving later running decoders that step.

**Steady-state all-decode step (32 slots, all decoding):**

```
scheduled_tokens = 32 × 1 = 32
remaining_for_prefill = 8192 − 32 = 8160   (available if a running request is still prefilling)
```

At 16 slots: 16 decode tokens/step → **half the decode batch tokens** per forward pass vs 32 slots.

**Large-prefill steal (single 50k prompt, chunked at 8192):**

```
prefill_steps = ceil(50_000 / 8192) = 7 forward passes
```

Each of those 7 steps can schedule up to 8192 prefill tokens on the **first** running prefill in FCFS order, potentially scheduling **zero** tokens for the other 31 decoders that step. Prefill steps are compute-bound (attention on thousands of tokens); decode-only steps with 32 tokens are memory-bound — a mixed step dominated by an 8192-token prefill chunk is orders of magnitude slower than a pure 32-token decode step.

**Prompt range (3k–100k tokens):**

| Prompt | Prefill steps @ 8192/chunk | Steps if 32 decodes share step (best case) |
|--------|---------------------------|---------------------------------------------|
| 3k | 1 | 1 |
| 10k | 2 | 2 |
| 50k | 7 | 7 |
| 100k | 13 | 13 |

Prefix caching on the shared ~2.9k system+schema prefix ([20-sweep-results.md](../../packages/whisker/research/llm-batching/20-sweep-results.md)) reduces effective prefill for repeat prefix but **not** the per-paper body (PDF text + markdown pairs dominate 3k–100k).

### Does per-request latency doubling explain 692 → 1090?

```
observed_ratio = 1090.2 / 692.3 = 1.574  (+57.4%)
pure_2x_prediction = 692.3 × 2 = 1384 s   (NOT observed)
```

A naive "every decode step 2× slower because 32 vs 16 tokens" model **overpredicts** by ~26%. The measured 1.57× ratio is **consistent with MoE decode superlinearity** (expert-union growth, see `11-moe-batch-scaling.md`) and **partial** prefill interference, not a full 2× per-request latency doubling.

**Queueing asymmetry (measured workload):**

| Config | In-flight on GPU | Queued (zero GPU) |
|--------|------------------|-------------------|
| server=16, client=32 | 16 decode/prefill | 16 wait |
| server=32, client=32 | **32 decode/prefill** | 0 wait |

Before: 16 queued requests cost nothing. After: all 32 compete every step for the same 8192-token budget and the same MoE forward pass. The regression is not "more queue wait" — it is "more simultaneous work per step."

**Rough batch wall-time model (381 papers, c=32):**

```
waves ≈ ceil(381 / 32) ≈ 12
Δwall ≈ waves × Δt_per_wave

If Δt_per_wave / t_per_wave ≈ 1.57  →  Δwall ≈ +57%   ✓ matches measured
```

Prefill interference adds **spike steps** at wave boundaries (many new prefills entering `running` together) and **ongoing contention** when any running request is mid-chunk-prefill alongside 31 decoders — but cannot alone produce exactly 1.57× without MoE decode slowdown on the non-blocked steps.

## Findings

- [HIGH] **`max_num_batched_tokens` stayed at 8192 while slots doubled; budget is global per step, not per-sequence.** Evidence: pod launch cmd has no `--max-num-batched-tokens` ([H200SXM.txt](https://github.com/cppalliance/runpod/blob/master/templates/deepseek/H200SXM.txt)); vLLM 0.24 H200 default 8192 ([arg_utils.py](https://github.com/vllm-project/vllm/blob/v0.24.0/vllm/engine/arg_utils.py#L2387-L2391)); scheduler `token_budget = self.max_num_scheduled_tokens` shared across all running requests ([scheduler.py:407-578](https://github.com/vllm-project/vllm/blob/v0.24.0/vllm/v1/core/sched/scheduler.py)). Impact: 32 sequences now share the **same** 8192-token step budget that previously served 16 — each decode step processes 2× decode tokens, and prefill chunks compete for the same pool.

- [HIGH] **Chunked prefill is on by default; large prefills (3k–100k) consume multiple 8192-token steps that can block decoders.** Evidence: [vLLM optimization v0.24](https://docs.vllm.ai/en/v0.24.0/configuration/optimization/) — "When there are available tokens in the `max_num_batched_tokens` budget, it schedules pending prefills… automatically chunks"; 50k prompt = 7 steps @ 8192. Impact: at 32 concurrent slots, more requests sit in `running` during multi-step prefills, increasing the fraction of scheduler steps where an 8192-token prefill chunk delays 31 decoders.

- [HIGH] **Raising `max_num_seqs` alone does not raise `max_num_batched_tokens`; co-tune is documented.** Evidence: vLLM `benchmarks/auto_tune/README.md` sweeps both knobs jointly; [Vultr concurrency guide](https://docs.vultr.com/inference-cookbook/cuda/optimization/concurrency-tuning) lists separate tiers for `--max-num-seqs` and `--max-num-batched-tokens`; optimization docs: "Smaller values (e.g., 2048) achieve better ITL because there are fewer prefills slowing down decodes" ([v0.24 optimization](https://docs.vllm.ai/en/v0.24.0/configuration/optimization/)). Impact: today's change violated the documented co-tune pattern — slots up, token budget flat.

- [HIGH] **Measured +57% is less than a pure 2× per-request latency model (+100%).** Evidence: 1090.2/692.3 = 1.574; 692.3×2 = 1384 s. Impact: prefill interference is real but **cannot be the sole explanation**; MoE expert-union decode slowdown (`11-moe-batch-scaling.md`, ~1.57× TPOT) aligns with the observed ratio without requiring every decode step to double.

- [MED] **Default `max_num_partial_prefills=1` limits concurrent chunked prefills to one, but does not prevent a single 8192-token chunk from monopolizing a step.** Evidence: [scheduler.py config](https://github.com/vllm-project/vllm/blob/v0.24.0/vllm/config/scheduler.py) defaults; V1 running-queue FCFS loop assigns `num_new_tokens = min(remaining_work, token_budget)` with `long_prefill_token_threshold=0`. Impact: one active long prefill can still stall all other running decoders for that step; with 32 running vs 16, more decoders are victims per stall event.

- [MED] **Production DeepSeek-V4 H200×8 configs explicitly set both knobs; our pod only set seqs.** Evidence: GitHub #42265 — `--max-num-seqs 8 --max-num-batched-tokens 8196` on H200×8 DeepSeek-V4 ([05a-web-concurrency-knee.md](../../packages/whisker/research/llm-batching/05a-web-concurrency-knee.md)); our pod had 16/8192, now 32/8192. Impact: raising seqs toward 32 without raising batched tokens moves away from published MoE-safe configs.

- [LOW] **Alternative default 2048 (SchedulerConfig constant) does not apply to this pod.** Evidence: `DEFAULT_MAX_NUM_BATCHED_TOKENS = 2048` is overridden by `create_engine_config` for H200 API server → 8192. Impact: math in this report uses 8192, not 2048; if pod were on non-H200 fallback, prefill steal would be **worse** (ceil(50k/2048)=25 steps).

## What would confirm/refute this

**Confirm:** Re-run 381-paper corpus at `--max-num-seqs 32` with `--max-num-batched-tokens 16384` (2× budget, H200 LLM_CLASS default) or 32768; if wall time drops toward 692 s while keeping client c=32, prefill-decode budget contention was a major contributor. Capture vLLM scheduler metrics: fraction of steps with >1000 scheduled prefill tokens while >16 decode requests are running; compare 16 vs 32 slots.

**Refute:** If `--max-num-batched-tokens 16384` at 32 slots does **not** improve wall time but `--max-num-seqs 16` at any batched-tokens value restores ~692 s, the regression is almost entirely MoE decode batch scaling (report 11), not prefill stealing. If ITL/TPOT metrics show no increase in "prefill-heavy steps" at 32 slots, interference is negligible.

**Actionable co-tune (if keeping 32 slots):** Raise `--max-num-batched-tokens` proportionally (e.g., 16384–32768 on H200), consider `--max-num-partial-prefills` / `long_prefill_token_threshold` to cap chunk size and protect decode ITL, or revert server to 16 with client c=32 (measured optimal: 692.3 s, [20-sweep-results.md](../../packages/whisker/research/llm-batching/20-sweep-results.md)).
