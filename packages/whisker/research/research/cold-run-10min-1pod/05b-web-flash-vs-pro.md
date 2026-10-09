# 05b — Web: DeepSeek-V4-Flash vs V4-Pro (unit-judge / structured checks)

**Query:** Can Flash replace Pro for structured verification / coding / document QA
unit checks on self-hosted vLLM? Public weights? Deployed on Alliance today?

**Date:** 2026-07-24  
**Corpus constraint:** single pod (`alliance-pod` = DeepSeek-V4-Pro). No twin Pro pod.

---

## Verdict (operator ask)

| Question | Answer |
|----------|--------|
| **Flash as unit-judge candidate?** | **yes** — with caveats below |
| Public open weights for self-host? | **yes** — MIT, Hugging Face |
| Flash live on Alliance today? | **no** — `SERVICES.toml` only lists `deepseek-v4-pro` on `alliance-pod` / `h200x8-deepseek-v4-pro` |

**One-liner:** Flash is a credible **fast unit-check** model (schema verdicts, short coding/doc checks) if you can **serve it** and A/B against Pro; it is **not** a drop-in quality equal for hard agentic / knowledge-heavy / fail-closed edge cases, and it is **not deployed** on the one pod we have.

---

## Architecture (official)

| | V4-Flash | V4-Pro |
|---|---------:|-------:|
| Total / active params | 284B / **13B** | 1.6T / **49B** |
| Context | 1M | 1M |
| Modes | Non-think, High, Max | Non-think, High, Max |
| Weights | MIT, open | MIT, open |
| HF id | `deepseek-ai/DeepSeek-V4-Flash` | `deepseek-ai/DeepSeek-V4-Pro` |

Source: [Hugging Face DeepSeek-V4-Flash](https://huggingface.co/deepseek-ai/DeepSeek-V4-Flash) (model card + mode table). Official framing: Flash-Max is “comparable reasoning to Pro with larger thinking budget,” behind on pure knowledge and hardest agentic workflows.

---

## Speed

| Signal | Flash | Pro | Notes |
|--------|------:|----:|-------|
| Active params / forward | 13B | 49B | ~3.8× less MoE activate → decode advantage |
| Hosted API decode (blog range) | ~120–160 tok/s Non-think | ~60–80 tok/s Non-think | [aimadetools Pro vs Flash](https://www.aimadetools.com/blog/deepseek-v4-pro-vs-flash/) |
| AA-style throughput (aggregator) | ~2× Pro class | baseline | Aggregators disagree on absolute tok/s; direction is consistent |
| vLLM quickstart GPU floor | **4×B200/B300** DP4+EP | **8×B200/B300** DP8+EP | [vLLM DeepSeek V4 blog](https://vllm.ai/blog/2026-04-24-deepseek-v4) |
| H200 recipe shape (prior forage) | DP4+EP on 4 of 8 H200 | DP8+EP / TP8+EP on full node | `research/cold-run-10min/40-vllm-deepseek-recipe.md` |

**Impact on single-pod wall:** Flash cuts **L** (per-call latency) if unit checks move to Flash Non-think/High with short structured decode. It does **not** raise `S_eff` above 16 on Pro. To use Flash without a second machine you must **swap** `alliance-pod` weights (lose Pro for that node) or stand up a **different** Flash endpoint (allowed as non-Pro capacity, but not free ops).

---

## Quality by workload (primary: official HF mode table)

Numbers below are **official DeepSeek instruct evals** from the V4-Flash model card (same table as Pro). Prefer these over third-party blogs when they conflict.

### Coding / verification-adjacent

| Benchmark | Flash Non | Flash High | Flash Max | Pro Non | Pro High | Pro Max |
|-----------|----------:|-----------:|----------:|--------:|---------:|--------:|
| LiveCodeBench | 55.2 | 88.4 | **91.6** | 56.8 | 89.8 | **93.5** |
| SWE Verified | 73.7 | 78.6 | **79.0** | 73.6 | 79.4 | **80.6** |
| Terminal Bench 2.0 | 49.1 | 56.6 | **56.9** | 59.1 | 63.3 | **67.9** |
| Codeforces (rating) | — | 2816 | 3052 | — | 2919 | 3206 |

**Read for unit checks:** short structured pass/fail on code snippets ≈ LiveCodeBench / SWE band → Flash Max within ~2 pts of Pro Max on SWE; **Terminal Bench gap is large** (~11 pts Max). Hard multi-step “verified agent” judging still wants Pro (or escalate).

### Document / long-context QA

| Benchmark | Flash Max | Pro Max | Gap |
|-----------|----------:|--------:|----:|
| MRCR 1M | 78.7 | 83.5 | −4.8 |
| CorpusQA 1M | 60.5 | 62.0 | −1.5 |
| SimpleQA-Verified | 34.1 | 57.9 | **−23.8** |
| GPQA Diamond | 88.1 | 90.1 | −2.0 |

**Read:** local doc-chunk QA with evidence in context is close enough to trial; **parametric / open-world fact** checks are not Flash’s job.

### Structured / instruction following

- Both V4 tiers expose JSON mode + tool calling on the hosted API; vLLM recipes enable `--tool-call-parser deepseek_v4` / `--reasoning-parser deepseek_v4` for **both** Flash and Pro.
- JSON mode is “valid JSON designed, not guaranteed”; schema still needs client validation / retries (same for both). Official JSON guide examples use Pro; feature is not Pro-only.
- Artificial Analysis IFBench (aggregator snapshot): Flash **79.2%** vs Pro **76.5%** — Flash can be *better* at instruction following while worse on TerminalBench Hard (35.6 vs 46.2). Useful for **verdict-first JSON schemas**; not proof of judge correctness.

### Hallucination (prior corpus)

AA Omniscience hallucination-when-wrong ≈ **96% Flash Max / 94% Pro Max** — fail-closed abstention is weak on both; do not expect Flash to “know when to stop” better than Pro. Cite: `packages/whisker/research/deepseek-v4-pro/12-hallucination-faithfulness.md`.

---

## Self-host / public weights

| Item | Status | Evidence |
|------|--------|----------|
| Open weights | **Yes**, MIT | HF `deepseek-ai/DeepSeek-V4-Flash` (+ Base) |
| Also | ModelScope mirrors | Same model card table |
| vLLM support | **Yes** (native V4 family) | [vLLM blog 2026-04-24](https://vllm.ai/blog/2026-04-24-deepseek-v4); recipe `https://recipes.vllm.ai/deepseek-ai/DeepSeek-V4-Flash` |
| Approx weight footprint | ~158GB class (FP4+FP8 MoE) | HF / self-host guides; fits fewer GPUs than Pro (~862GB class) |
| Alliance deployed today | **No** | `SERVICES.toml`: `alliance-pod` and `h200x8-deepseek-v4-pro` both `model = "deepseek-v4-pro"` |

**Implication:** Flash is not a software switch on the current pod. Paths:

1. **Swap** `alliance-pod` → Flash (gain unit-check L; lose Pro ceiling for fusion/hard calls on that node).
2. **New Flash vLLM endpoint** on spare GPUs / another paid box (not a twin Pro pod; still ops + budget).
3. Keep Pro; use **dense offload** already in baseline scope (`h200-qwen3-32b`, Gemma, Qwen3.6) instead of Flash.

---

## Can Flash replace Pro for *unit* checks?

### Yes, as candidate, when

- Checks are **short, structured** (enum/boolean verdict + small evidence span).
- Mode is at least **High** (Non-think Flash collapses on hard reasoning: e.g. HLE 8.1 Non vs 34.8 Max).
- Pipeline keeps **fail-closed** retries / schema validators (D6/D10 style).
- Hard / ambiguous units **escalate** to Pro or denser expert (router), not silent Flash-only.

### No / not yet, when

- You need **same** quality as current Pro Max on agentic Terminal-Bench-like unit chains.
- Document checks need **world knowledge** outside the paper chunk (SimpleQA gap).
- Flash is **not running** and ops cannot swap the only Pro pod for the cold-run window.
- You treat Flash Non-think as “free speed” without A/B — that is the quality cliff.

### False-pass / false-fail hypotheses

- **False-pass:** Flash High/Max agrees with Pro on easy units, misses subtle doc contradictions → green units that Pro would fail. Mitigate: shadow 5–10% units dual-judge; escalate on low-confidence / disagreement.
- **False-fail:** Flash over-rejects on schema nitpicks or weaker long-context MRCR → extra retries inflate N and erase L wins. Mitigate: verdict-first schema + measured retry rate vs Pro baseline.

### Arithmetic (sketch only; S_eff=16)

If a large share of ~2284 calls are unit checks and Flash Non-think/High cuts `L_eff` by ~1.5–2× on those calls only:

`wall ≈ (N_rem × L_eff) / 16 + T + C − L_abs`

Flash helps **L_eff**, not slot count. Without deployment, wall savings are **zero**. With swap, also model any Pro-only calls that regress and retry.

---

## What would change my mind

- Live A/B on tapetum unit-check prompts: Flash High agreement ≥99% with Pro High on fail-closed units, retry rate not up.
- Ops ships Flash on spare H200s **without** displacing the Pro pod (true parallel L cut).
- Measured Non-think Flash structured-output validity ≥ Pro Non-think under our `output_type` + `output_retries`.

---

## Sources (primary first)

1. https://huggingface.co/deepseek-ai/DeepSeek-V4-Flash — architecture, mode table, MIT weights  
2. https://vllm.ai/blog/2026-04-24-deepseek-v4 — vLLM Flash/Pro serve recipes  
3. https://recipes.vllm.ai/deepseek-ai/DeepSeek-V4-Flash — Flash recipe  
4. https://api-docs.deepseek.com/guides/json_mode/ — JSON output constraints (both tiers)  
5. https://www.aimadetools.com/blog/deepseek-v4-pro-vs-flash/ — speed/pricing secondary  
6. https://ominigate.ai/en/vs/deepseek-v4-flash-vs-deepseek-v4-pro — AA aggregates (TerminalBench Hard, IFBench); treat as secondary  
7. Workspace: `SERVICES.toml` (`alliance-pod` = Pro only); `research/cold-run-10min/40-vllm-deepseek-recipe.md`

---

## Bottom line for cold-run-10min-1pod

**Flash = yes as unit-judge candidate**, not as full Pro replacement. Public weights + vLLM path are real. **We do not have Flash deployed**; using it requires a weight swap or new endpoint. Prefer Flash High/Max + escalate hard units; do not bet the 10‑min plan on Flash until that endpoint exists and A/B clears fail-closed quality.
