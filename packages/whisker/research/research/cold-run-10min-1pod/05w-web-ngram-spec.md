# 05w - Web: ngram / prompt-lookup speculative decoding (vs MTP)

**Date:** 2026-07-24  
**Scope:** N-gram / prompt-lookup decoding (PLD) as a draft-model-free speculative path for repetitive / structured JSON — compared to native MTP on DeepSeek.  
**Prior (do not rediscover):** `research/cold-run-10min/05d-web-mtp-specdecode.md`, `research/cold-run-10min-1pod/15-verdict-first-design.md`, `research/cold-run-10min-1pod/16-server-ops-1pod.md`.  
**Hard constraint:** Single `alliance-pod`, `S_eff=16` (`00-baseline.md`).

---

# 05w - Web-Ngram-SpecDecode

**Verdict:** usable-with-conditions — ngram/PLD is a real, zero-draft-weight lever that helps **templated** continuations (JSON keys, punctuation, copied schema fragments), but it is a **weak substitute for MTP on DeepSeek-V4-Pro** and only a **marginal** UnitCheck decode lever at our short OSL (~20–77 tok pass path). Prefer MTP k=1 on alliance-pod; keep ngram as fallback for non-MTP dense offload endpoints.
**Confidence:** high on mechanism + vLLM config; medium on fleet wall savings (no alliance-pod ngram A/B in this corpus)

## Findings

- [CRITICAL] **Mechanism is prompt-continuation lookup, not a neural draft.** Prompt Lookup Decoding (Saxena / HF assisted-generation lineage; popularized as [apoorvumang/prompt-lookup-decoding](https://github.com/apoorvumang/prompt-lookup-decoding)) takes the last *n* generated tokens, finds an earlier match in the prompt+prefix, and proposes the next *k* tokens after that match. vLLM exposes this as `method: "ngram"` with `num_speculative_tokens`, `prompt_lookup_min`, `prompt_lookup_max` ([vLLM n-gram docs](https://docs.vllm.ai/en/stable/features/speculative_decoding/n_gram/), [overview](https://docs.vllm.ai/en/stable/features/speculative_decoding/)). Impact: **pod-restart flag only**, no draft weights, no client change — same ops class as MTP.

- [CRITICAL] **Vendors pitch it for structured JSON; acceptance is workload-bimodal.** Friendli markets n-gram speculation for “Structured JSON generation” and templated writing ([Friendli blog, 2025-08-08](https://friendli.ai/blog/n-gram-speculative-decoding)). Third-party synthesis puts n-gram acceptance at **~10–90%+** (near zero on novel prose, very high on copy/paste-like repetition) vs MTP **~50–70%** more stable ([Glukhov speculative-decoding survey](https://www.glukhov.org/llm-performance/optimization/speculative-decoding/)). Impact: gains concentrate where the **output re-emits prompt fragments**; free-text `reasoning` / quotes do not.

- [CRITICAL] **On DeepSeek alliance-pod, MTP dominates ngram as the primary spec method.** vLLM comparison table: MTP = high gain (when native); n-gram = low–medium latency / medium high-QPS, “modest speedups without increasing workload during peak traffic” ([spec decoding overview](https://docs.vllm.ai/en/stable/features/speculative_decoding/)). DeepSeek-V4-Pro already has native MTP (`05d`: k=1 acceptance often ~80–90% when healthy). Spec config is one `method` — enabling ngram **instead of** MTP is a downgrade on this pod; enabling both is not the documented primary path. Impact: ngram is **not** the preferred decode lever for V4-Pro cold-run; it is the fallback when MTP is unavailable (dense offload models) or MTP acceptance collapses.

- [HIGH] **UnitCheck JSON is only partly “repetitive schema.”** Anchor schema (`models.py:298-320`): `reasoning` (≤40 words, field-first), `unit_id`, nested `defects[]` of `DefectFinding` (7 fields, free strings), `verdict`, `confidence`. Measured P50 pass JSON **~77 tok** with **~55 tok in `reasoning`** (`15-verdict-first-design.md`). Proposed `UnitCheckClear` shrinks pass path to **~20 tok** (keys + unit_id + verdict + confidence). Ngram can draft repeated JSON punctuation/keys **if** those token sequences appear earlier in context (schema text, few-shots, or already-emitted prefix). It cannot draft novel defect quotes or CoT. Impact: **fraction of draftable tokens is small on current UnitCheck; higher on UnitCheckClear but absolute OSL is tiny.**

- [HIGH] **Short OSL amortization still bites.** Same cliff as MTP (`05d` / GB300): speculative overhead needs enough decode steps to pay for draft+verify. Pass-path UnitCheckClear (~20 tok) and even current pass (~77 tok) sit near/under the “hard to amortize” band. At saturated **16 slots**, ngram’s advertised advantage is “no extra draft compute,” so it may retain a **small** high-QPS edge over heavy draft methods — but absolute seconds saved stay modest vs call-count cuts.

- [HIGH] **Low `prompt_lookup_min` + repetitive schema/tool templates can corrupt structured output.** [vLLM #40875](https://github.com/vllm-project/vllm/issues/40875): default `prompt_lookup_min=2` matched short template fragments in the system prompt and corrupted tool-call / structured continuations (~50% clean → **100% clean** with `prompt_lookup_min=8` on that workload). Later comment notes at temp=0 the sampler itself is lossless; residual corruption classes also involve cudagraph/TurboQuant stacks. Impact for UnitCheck: if the system prompt embeds JSON schema / example objects (guided decoding, tool defs, few-shots), **raise `prompt_lookup_min` to 4–8** or accept near-zero drafting; do not ship default min=2 blind on structured judges.

- [MED] **Constrained decoding can raise speculative acceptance on JSON.** Friendli reports `response_format` JSON schema improving throughput largely **through** speculative decoding (acceptance up when the token set is narrowed) ([Friendli structured-output blog](https://friendli.ai/blog/structured-output)). Impact: if alliance-pod already uses grammar/XGrammar for `UnitCheck`, ngram drafts of schema-legal punctuation may accept more often — still subject to the short-OSL and free-text limits above.

- [MED] **vLLM enablement (ops-only).** Example from docs:

```python
speculative_config={
    "method": "ngram",
    "num_speculative_tokens": 5,
    "prompt_lookup_max": 4,
    # for structured/tool-heavy prompts, also set:
    # "prompt_lookup_min": 8,
}
```

CLI: `--speculative-config '{"method":"ngram","num_speculative_tokens":3,"prompt_lookup_min":8,"prompt_lookup_max":10}'` (safe structured recipe from #40875). Impact: same restart class as MTP in `16-server-ops-1pod.md`; **do not replace MTP on V4-Pro without A/B proof that MTP acceptance is broken.**

## Arithmetic (why this is not a ≤600 s path alone)

Post short-circuit unit survivors ≈ **663** calls (`15`). Assume decode ≈ **6 s** of ~20 s/call (decode-bound judge, `05d`). Optimistic ngram TPOT cut on that decode slice **15%** (high-QPS “modest” band; not MTP’s best-case ~1.5×):

```
ΔL ≈ 0.15 × 6 s = 0.9 s/call
wall_save ≈ (663 × 0.9) / 16 ≈ 37 s
```

Even **30%** decode cut → ~75 s. Negligible vs the **~800–900 s** gap to 600 s after MODERATE (`00-baseline.md`). Ngram does not move the single-pod ceiling; it is a small **L** tweak or a dense-offload fallback.

## Comparison: ngram/PLD vs MTP (UnitCheck lens)

| Axis | MTP (DeepSeek native) | Ngram / PLD |
|------|------------------------|-------------|
| Draft source | Trained MTP heads on target | String match in prompt+prefix |
| Extra VRAM | Small (heads) | ~None |
| Acceptance stability | ~50–90% when healthy | Bimodal: template high, novel low |
| Best on UnitCheck | Free-text + keys (neural) | Keys/punctuation/copied fragments |
| Short OSL (~20–77 tok) | k=1 usually OK if decode-bound | Often fails to amortize |
| Structured-output risk | Reasoning-boundary bugs (patched class in `05d`) | Spurious short ngram matches (#40875) |
| alliance-pod default choice | **Yes (k=1)** | Only if MTP off/broken |
| Dense offload (Qwen/Gemma w/o MTP) | N/A or model-specific | **Primary cheap lever** |

## Answer: useful for UnitCheck JSON?

| | |
|--|--|
| **Answer** | **Marginally yes, with conditions — not as MTP replacement on V4-Pro** |
| **When useful** | (1) Dense-offload UnitCheck endpoints **without** native MTP; (2) after `UnitCheckClear` shrink, where a larger *fraction* of tokens are schema keys (still tiny absolute wall); (3) MTP acceptance collapsed and ops need *some* zero-weight speculation. |
| **When not** | Expecting a primary cold-run lever on `alliance-pod`; current reasoning-first UnitCheck (majority tokens = novel CoT); replacing healthy MTP k=1. |
| **Config if tried** | `method=ngram`, `prompt_lookup_min≥8` for schema-heavy prompts, small `num_speculative_tokens` (2–3), measure `spec_decode_*` acceptance + JSON validity + verdict flip vs baseline. |

## False-pass hypothesis

Ngram with `prompt_lookup_min=2` drafts a wrong continuation from a repeated schema/example fragment in `UNIT_CHECK_SYSTEM_PROMPT` / grammar scaffolding; rejection sampling under non-greedy or buggy verify paths accepts a corrupted JSON that still parses (empty defects, wrong `unit_id`) → silent false clear. Mitigate: min≥8, greedy/temp=0, structured-output A/B.

## False-fail hypothesis

Ops enable ngram **instead of** MTP, see weak acceptance on reasoning-heavy UnitCheck, conclude “speculation useless,” and disable the MTP k=1 recipe that `05d`/`16` already budget as part of the server bundle.

## What would change my mind

- Alliance-pod A/B: ngram (min=8, k=3) vs MTP k=1 vs neither on **real** unit-check traffic, logging acceptance, JSON validity, and pass/review/fail. Flip ngram to **usable** as co-equal if acceptance ≥~MTP and wall ≤ MTP path.  
- Flip to **garbage** for UnitCheck if acceptance stays &lt;~30% on pass-path JSON (expected if CoT dominates) or structured corruption reappears at min=8.  
- Flip to **primary lever** only if MTP is unavailable on the serving image and measured wall_save ≫ ~1 min (unlikely on short OSL).

## Sources (web)

1. https://github.com/apoorvumang/prompt-lookup-decoding  
2. https://docs.vllm.ai/en/stable/features/speculative_decoding/n_gram/  
3. https://docs.vllm.ai/en/stable/features/speculative_decoding/  
4. https://friendli.ai/blog/n-gram-speculative-decoding  
5. https://friendli.ai/blog/structured-output  
6. https://github.com/vllm-project/vllm/issues/40875 (prompt_lookup_min + structured/tool corruption)  
7. https://www.glukhov.org/llm-performance/optimization/speculative-decoding/ (acceptance ranges MTP vs ngram)  
8. Local anchors: `05d-web-mtp-specdecode.md`, `15-verdict-first-design.md`, `models.py:298-320`
