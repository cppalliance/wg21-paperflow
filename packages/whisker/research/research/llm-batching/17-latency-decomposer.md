# 17 - Latency-Decomposer

**Verdict:** usable-with-conditions — per-call wall time is decode-dominated (~25–28 s of ~30 s mean), not prefill/input; input-shrink and prefix-cache levers save sub-second to low-single-digit seconds on typical papers, while thinking-cap and tier1 `max_tokens` alignment are the only whisker-side per-call cuts with multi-second upside (conditional on pod thinking state, which artifacts do not record).
**Confidence:** medium

## Findings

- [CRITICAL] **Sidecar JSON records verdicts, not timings.** Evidence: 204 `*.whisker.tapetum.json` under `data/whisker/llm/` parsed; keys are `whisker_verdict`, `reasoning`, `axis_findings`, `escalated`, `tier1_model`, `tier2_model` — no `duration`, `usage`, `tokens`, or retry counters. Distribution: 7 pass / 188 review / 9 fail; 14 escalated (6.9%). Impact: latency decomposition must back-solve from `00-baseline.md:12-14` wall time, not read per-call timers from artifacts.

- [CRITICAL] **Mean per-call latency is ~30.4 s, not ~10.8 s/paper.** Evidence: `00-baseline.md:12-14` (2159.8 s, c=3, 200 papers, 13 tier-2 escalations → 213 LLM calls); arithmetic `2159.8 × 3 / 213 = 30.4 s/call` (matches `11-throughput-auditor.md:66`). Impact: any lever saving <2 s on prefill is noise against a 30 s budget; levers must target decode.

- [CRITICAL] **Decode dominates; prefill is ~7% on a typical paper.** Evidence: P50 stripped input `22242 chars ≈ 5560 tok` (`strip_binary_payloads` on 204 whisker papers); shared prefix `system 8139 + schema 3528 = 11667 chars ≈ 2916 tok` (`tapetum_llm.md` system section, `model_backends.py:285-286`); P50 total input `≈ 8538 tok`. Prefill at MoE-under-load `4000 tok/s` → `8538/4000 = 2.1 s`. Remainder `30.4 − 2.1 = 28.3 s` decode. Impact: cutting input tokens is optimizing the wrong term for P50; only P99 outliers (one paper `420262 chars ≈ 105065 tok` post-strip) flip prefill to co-dominant (~26 s prefill alone).

- [HIGH] **Final JSON output is ~635–900 tokens; sidecar `reasoning` field is not hidden thinking.** Evidence: reconstructed tier1 `Adjudication`-shaped JSON from 204 sidecars: P50 `2540 chars ≈ 635 tok`, P90 `3602 chars ≈ 900 tok`; sidecar `reasoning` field P50 `829 chars ≈ 207 tok` (in-schema prose, not `` block). `model_backends.py:352-363` strips `` before JSON parse; stripped thinking is never persisted to sidecar. Zero `*.debug.tapetum_llm.md` / `*.trace.tapetum_llm.md` under `data/` (batch ran without `--debug`/`--trace`, `cli.py:128-135`). Impact: implied decode throughput `635–900 tok / 28.3 s ≈ 22–32 tok/s`, consistent with busy MoE continuous-batching (`05a-web-concurrency-knee.md:47-51` reports TPOT widening under CB load).

- [HIGH] **Thinking state is UNKNOWN; if ON it would dominate, but server default is OFF.** Evidence: `adjudicate.py:450-457` sets `max_tokens=4096`, forwards no `thinking_budget` (`model_backends.py:294-298` sends `extra_body` only when budget set); `05e-web-thinking-control.md:13` (V4-Pro server default `enable_thinking: false`; thinking requires explicit enable); `05e-web-thinking-control.md:49-53` (hosted V4 ~31.8 s TTFB at ~2.9K input with thinking on — TTFB ≈ full reasoning decode). Observed ~30 s with P50 ~8.5K input and ~635 tok visible JSON fits **thinking-off + JSON decode**, not thinking-on. Impact: lever (a) saves **0 s/call** if pod default holds; **10–18 s/call** if CTO enabled thinking without client cap (back-solve: `28.3 s − 635tok/30tok/s ≈ 7–20 s` unaccounted thinking).

- [MED] **Input-shrink residual fat is small post base64 strip; front matter is intentional.** Evidence: 10/204 papers had strip events; largest raw `2552961 → 420262 chars` (`chunking.strip_binary_payloads`); P50 shrink `23688 → 22242` (−6%). `tapetum_llm.md:110` keeps front matter by design. `inject_untrusted` adds ~30-char guard wrapper only (`tools.py:49-52`); authority doc claims "line-numbered" but code does not add line numbers. Corpus `.md` P50 `34280 chars` (581 files) vs whisker-subset P50 `22242` stripped. Impact: further input cut saves `Δtok/4000` seconds prefill — e.g. drop 2000 tok → **~0.5 s/call** typical; **~20 s** only on the one 105K-tok outlier.

- [MED] **Prefix caching of shared ~2.9K-tok system+schema saves <1 s/call when warm.** Evidence: shared prefix `2916 tok` is `34%` of P50 input `8538 tok`; `05c-web-prefix-guided.md:21-24` (APC skips prefill on cached prefix; savings scale with prefix/input ratio, not Jarvis −78% ceiling where prefix dominates). Arithmetic: `2916 tok / 4000 tok/s = 0.73 s` saved per warm hit; cold/miss or APC-off → **0 s**. Impact: on 213-call run, upper bound `213 × 0.73 s ≈ 155 s` (~2.6 min) only if every call hits warm cache — realistic warm-batch fraction yields **~0.3–1.0 s/call**, **~1–3 min** total wall, not path to single-digit minutes alone.

- [LOW] **`max_tokens=4096` overshoots actual tier1 output (~635 tok) but ceiling rarely binds.** Evidence: `adjudicate.py:453` vs `tapetum_llm.md:119` (`max-output: 2048`); 1 model retry on full 200-paper run (`00-baseline.md:14`). Reconstructed JSON max `6447 chars ≈ 1612 tok` ≪ 4096. Impact: lowering 4096→2048 saves **~0–2 s/call** if model does not run to ceiling; saves **~5–10 s** only on truncation-retry path (`model_backends.py:377-379` doubles budget on `finish_reason=length`).

## Latency budget arithmetic (typical P50 paper, tier1)

| Term | Tokens (est.) | Rate (assumed) | Seconds | Share of 30.4 s |
|------|---------------|----------------|---------|-----------------|
| Prefill (system+schema+header+md) | 8,538 | 4,000 tok/s (MoE, c=3 load) | 2.1 | 7% |
| Decode (JSON output) | 635–900 | 25–32 tok/s | 25–28 | 82–92% |
| HTTP client setup (parked) | — | — | 0.05–0.2 | <1% |
| **Total** | | | **~30.4** | |

Back-solve check: `28.3 s × 30 tok/s ≈ 849 output tokens` — brackets reconstructed JSON P50–P90 (635–900) plus small raw-json/fence overhead before `_extract_json`.

## Per-call lever ranking (expected seconds saved)

| Rank | Lever | Condition | Arithmetic | Est. saving/call |
|------|-------|-----------|------------|------------------|
| 1 | **(a) Cap/disable thinking** (`thinking_budget=0` or `1024` on fast slot) | Pod has thinking ON | If thinking adds ~1500–2500 hidden tok at 30 tok/s: `1500/30 = 50 s` upper bound; observed gap vs JSON-only ≈ **7–20 s** | **0 s** (default-off) to **10–18 s** (if on) |
| 2 | **(b) Tier1 `max_tokens` 4096→2048** | Authority doc already specifies 2048 (`tapetum_llm.md:119`) | Actual output ~635 tok; savings only if model wastes decode toward ceiling or hits length-retry: `Δtok/decode_rate` | **0–2 s** typical; **5–10 s** on truncation retries |
| 3 | **(d) Prefix cache warm hit** on ~2.9K shared prefix | APC on (`05c-web-prefix-guided.md:11-13`, pod flag unknown) | `2916/4000 = 0.73 s` per hit | **0.3–1.0 s** |
| 4 | **(c) Shrink input** (front matter, code blocks) | Post base64-filter corpus | Remove 2000 tok prefill: `2000/4000 = 0.5 s`; P99 105K-tok paper prefill ~26 s → cutting 50% saves ~13 s | **0.3–1 s** typical; **~13 s** outlier only |

**Failure-class note:** optimizing (c) or (d) on P50 papers chases ≤7% of wall time while (a) and decode-rate levers (concurrency, guided JSON — out of scope here) chase the other 93%. Input shrink is the wrong default target; thinking-cap / output-budget alignment is the right per-call target pending pod thinking verification.

## False-pass hypothesis

Disabling or capping thinking (`thinking_budget=0`) on a pod where thinking currently improves table/code fidelity could shorten calls by 10+ s but yield sloppier `axis_findings`, dropping escalation rate and letting scrambled-table papers stay at tier1 `review` instead of tier2 — a faster false negative on conversion defects.

## False-fail hypothesis

Aggressive `max_tokens=2048` without monitoring `finish_reason=length` triggers the growth-retry path (`model_backends.py:377-379`), doubling effective decode on borderline papers and adding a second 15–30 s attempt — net slower and noisier, surfacing as spurious `error` or `ungrounded_evidence` escalations.

## What would change my mind

One 9-paper batch with `--debug` on alliance-pod, logging `<!-- reasoning -->` block char length per call alongside wall time: if median thinking chars >3000 while JSON chars ~2500, thinking is the dominant term and lever (a) jumps to rank 1 with measured (not inferred) 10–18 s savings; if reasoning blocks are empty, input-shrink advocates should stand down permanently for this corpus.
