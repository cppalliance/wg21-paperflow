# 05z - Web hosted latency (OpenRouter / Together / Fireworks, Pro vs Flash, think on/off)

**Verdict:** usable — hosted decode and think-mode wall ratios are stable enough to use as self-host priors; absolute tok/s from Together/Fireworks peaks are **not** (optimized stacks, not alliance-pod vLLM).
**Confidence:** medium-high on ratios; medium on absolute numbers (72h medians drift; OpenRouter "Latency" ≠ AA TTFT).

**Snapshot date:** 2026-07-24. Sources are live dashboards; re-check before staking a plan on a specific tok/s.

---

## Findings

- [CRITICAL] **Think on/off dominates wall, not Flash vs Pro decode.** On DeepSeek first-party (AA, past 72h), E2E time to 500 answer tokens: Flash non-think **5.76 s** vs Flash max **52.08 s** (~**9×**); Pro non-think **9.06 s** vs Pro max **73.78 s** (~**8×**). Reasoning time is ~88–90% of E2E at max. Evidence: [Artificial Analysis DeepSeek provider](https://artificialanalysis.ai/providers/deepseek). Impact: Non-think / high-effort routing moves `L_eff` far more than swapping Pro→Flash at fixed think mode.

- [HIGH] **Flash decode ≈ 1.5–1.8× Pro decode** when comparing same stack. DeepSeek first-party: Flash **111 tok/s** vs Pro **66 tok/s** non-think (**1.68×**); Flash max **120** vs Pro max **68** (**1.76×**). OpenRouter Fireworks same-provider: Flash **74 tps** vs Pro **51 tps** (**1.45×**). Active-param ratio is 49B/13B ≈ **3.8×**, but measured decode only ~1.7× (MoE serving compresses the gap). Impact: Flash on the same pod class is a ~**1.7×** `L` prior for decode-bound calls, not 4×.

- [HIGH] **tok/s is nearly flat across think modes; wall scales with reasoning tokens.** Flash: 111 / 110 / 120 tok/s (non / high / max). Pro: 66 / 67 / 68. Evidence: AA DeepSeek table. Impact: Do not model think-off as "faster decode." Model it as **fewer output tokens** (reasoning budget → 0).

- [HIGH] **Together/Fireworks Pro peaks are ceilings, not self-host priors.** AA Pro (max), 10k-input workload: Together **326 tok/s** / first-chunk **1.01 s** / E2E **15.95 s**; Fireworks **175 tok/s** / **1.66 s** / **29.44 s**; DeepSeek first-party **68 tok/s** / **1.65 s** / **73.78 s**. Together ≈ **4.8×** first-party decode. OpenRouter P50 for the same providers is far lower (Together **46 tps**, Fireworks **51 tps**) — different metric window and load mix. Evidence: [AA Pro providers](https://artificialanalysis.ai/models/deepseek-v4-pro/providers), [OpenRouter V4 Pro](https://openrouter.ai/deepseek/deepseek-v4-pro). Impact: Cap self-host optimism at DeepSeek-first-party / OpenRouter mid-tier (~**45–70 Pro**, ~**70–120 Flash**), not Together 326.

- [MED] **OpenRouter provider table (Pro vs Flash, target hosts).** P50 Latency (OR definition) / Throughput:

  | Host | Pro Latency | Pro tps | Flash Latency | Flash tps |
  |------|------------:|--------:|--------------:|----------:|
  | Together | 0.76 s | 46 | *(not listed; Together page says Flash "coming soon")* | — |
  | Fireworks | 1.46 s | 51 | 0.98 s | 74 |
  | DeepSeek (1P via OR) | 1.10 s | 47 | 0.78 s | 68 |
  | Best-of-OR (any host) | 0.67 s | 65 | 0.57 s | 74 |

  Evidence: [OpenRouter Pro](https://openrouter.ai/deepseek/deepseek-v4-pro), [OpenRouter Flash](https://openrouter.ai/deepseek/deepseek-v4-flash). Impact: Same-host Fireworks Flash/Pro throughput prior **~1.45×**; TTFT-ish latency Flash better by ~**0.7×** on Fireworks.

- [MED] **Think high is the useful middle, not max.** AA DeepSeek E2E: Flash high **17.0 s** (~**3.0×** non-think) vs max **52.1 s** (~**9.0×**); Pro high **38.7 s** (~**4.3×**) vs max **73.8 s** (~**8.1×**). Impact: If quality allows high instead of max, wall prior drops ~**2×** (Flash) to ~**1.9×** (Pro) vs max without going fully non-think.

- [LOW] **Provider variance on OpenRouter Pro is ~8× tok/s** (CoreWeave/DigitalOcean **8 tps** vs Baseten **65 tps**). Do not treat "OpenRouter DeepSeek V4" as one speed. Impact: Pin provider or use Nitro; for self-host, ignore OR outliers.

---

## Canonical matrix (DeepSeek first-party, AA, ~72h median)

Best apples-to-apples think on/off comparison. Workload: AA standard (E2E = TTFT + thinking + 500 answer tokens).

| Config | Median tok/s | First chunk (s) | Reasoning time (s) | E2E (s) |
|--------|-------------:|----------------:|-------------------:|--------:|
| Flash non-think | 111 | 1.25 | — | **5.76** |
| Flash high | 110 | 1.15 | 11.28 | **16.98** |
| Flash max | 120 | 1.15 | 46.76 | **52.08** |
| Pro non-think | 66 | 1.50 | — | **9.06** |
| Pro high | 67 | 1.57 | 29.67 | **38.68** |
| Pro max | 68 | 1.65 | 64.74 | **73.78** |

Source: https://artificialanalysis.ai/providers/deepseek (fetched 2026-07-24).

---

## Self-host priors (return line)

Use these **ratios** on `alliance-pod` / vLLM. Do **not** import Together 326 tok/s.

| Prior | Ratio | How to apply |
|-------|------:|--------------|
| Flash decode / Pro decode | **1.5–1.8×** (central **1.7×**) | `L_decode_Flash ≈ L_decode_Pro / 1.7` at same concurrency |
| Active-param naive / measured | 3.8× theoretical vs **~1.7×** measured | Do not scale wall by 49/13 |
| Non-think wall / think-high wall | Flash **~1/3**, Pro **~1/4** | `L_high ≈ 3–4 × L_non` (token-count driven) |
| Non-think wall / think-max wall | **~1/8 – 1/9** | `L_max ≈ 8–9 × L_non` |
| Think-high wall / think-max wall | Flash **~1/3**, Pro **~1/1.9** | Prefer high over max if quality holds |
| Flash E2E / Pro E2E (same think) | **~0.64–0.71×** | Flash cuts wall ~**30–35%** vs Pro at fixed think |
| Hosted TTFT (non-think) | Flash **~1.0–1.3 s**, Pro **~1.1–1.5 s** | Prefill floor prior; self-host under load will be worse |
| Optimized-host ceiling vs 1P | Together Pro up to **~5×** 1P tok/s | Treat as existence proof of headroom, not plan input |
| OpenRouter mid-tier absolute | Pro **~45–55 tps**, Flash **~70–75 tps** (Fireworks/Together-class) | Sanity band if 1P unavailable |

**Arithmetic sketch for this corpus (S=16 fixed):** if current Pro think-on calls sit at `L≈20 s`, a pure Flash swap at **same think** priors `L≈20/1.7≈12 s` → wall factor **0.59×** on the decode-bound term. A Pro **max→non-think** swap priors closer to **0.12×** on think-dominated calls (quality-gated). Neither alone clears 1,419 × L / 16 to 600 s without N cuts; ratios say **think budget >> model tier** for `L_eff`.

```
wall = (N_rem × L_eff) / 16 + T + C − L_abs
# L_eff_Flash ≈ L_eff_Pro / 1.7          # same think mode
# L_eff_non  ≈ L_eff_max / 8.5           # same model, rough
# L_eff_high ≈ L_eff_max / 2.0           # Flash; /1.9 Pro
```

---

## False-pass hypothesis

Treating Together/Fireworks AA peaks (326 / 175 tok/s Pro) as alliance-pod achievable would false-pass a Flash/Pro plan that only works on their speculative-decoding stacks. OpenRouter's lower P50 for the same brands is the caution flag.

## False-fail hypothesis

Claiming Flash cannot help because "active params are 3.8×" would false-fail a Flash offload: measured hosted decode is only ~1.7×, and think-off is a larger lever than either.

## What would change my mind

- Side-by-side AA (or our own) bench of Flash on Together/Fireworks once Together ships Flash serverless.
- alliance-pod measured tok/s for Pro non-think / high / max on the dissect prompt mix (invalidates hosted absolute priors).
- Confirmation that OR "Latency" column is TTFT vs E2E (definition drift vs AA).
