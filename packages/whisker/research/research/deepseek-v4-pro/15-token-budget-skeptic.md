# 15 - Token-Budget-Skeptic

**Verdict:** usable-with-conditions — `chars_per_token = 4.0` is a reasonable provisional default inherited from R1/Qwen measurements, but it is unverified on V4-Pro and is **not** conservative for code-heavy WG21 windows; `token_multiplier = 1.5` is stale dead config with no active consumers.
**Confidence:** medium

## Findings

- **[HIGH] V4-Pro does not use the same tokenizer as V3/R1.** Evidence: HuggingFace `deepseek-ai/DeepSeek-V4-Pro` ships `tokenizer_class: "PreTrainedTokenizerFast"` and a dedicated `encoding/` module; V3 uses `tokenizer_class: "LlamaTokenizerFast"` with a different chat template. Impact: R1-Distill-70B's measured 4.20 chars/token is same-family-adjacent, not a V4 calibration. The ratio must be re-measured on V4.

- **[HIGH] `chars_per_token = 4.0` is conservative for average WG21 mix but unsafe for code-heavy windows.** Evidence: `MODELS.md:111` — code-heavy 256-token windows drop to ~2.5 chars/token; prose reaches ~5.5; stdev 0.36-0.70. At 2.5 actual: 4000 chars = ~1600 tokens (+60% vs nominal). Impact: chunk sizing invariant breaks on code-dense sections; context math underestimates tokens where overflow risk is highest.

- **[MED] Average-case 4.0 is defensible as a fleet-wide default, not as a V4-specific truth.** Evidence: Qwen3 measured 4.05, R1-Distill measured 4.20; both use 4.0 in SERVICES.toml. Using 4.0 vs 4.20 overestimates tokens on average text (conservative for fit checks). Impact: acceptable until V4 measurement; wrong if V4 tokenizes denser than R1 on technical English.

- **[MED] The 393,216-token configured window is safe for current consumers, with headroom.** Evidence: native V4 window = 1M; configured = 393,216 (~38% of native). tapetum_llm caps at `MAX_PAPER_MD_CHARS = 500,000` for nginx 413, not model context. Worst-case paper tokens at 2.5 cpt: 500,000 / 2.5 = 200,000 input tokens, plus system/schema/thinking — still under 393K. Impact: window size is not the bottleneck; per-chunk ratio error is.

- **[MED] `token_multiplier = 1.5` is deprecated and unused in active code.** Evidence: `AgentBackend.token_multiplier` docstring says deprecated. Zero `.py` call sites beyond config plumbing. Impact: wrong value cannot affect assay/tapetum today; documentation debt, not a live failure mode.

- **[LOW] Assay RAG hardcodes `_CHARS_PER_TOKEN = 4` (integer), bypassing per-service calibration.** Evidence: `rag.py:32,97`. Impact: if V4 ratio diverges from 4.0, RAG chunk sizing drifts independently of SERVICES.toml.

- **[LOW] Fallback constant `CHARS_PER_TOKEN = 3.25` is more conservative than V4's 4.0.** Evidence: `tokens.py:21-30`. If `chars_per_token` were unset, estimates would be more conservative. V4 entries explicitly set 4.0, so this fallback never applies.

## False-pass hypothesis

Assay runs on V4-Pro with `chunk-tokens: 1000`. A chunk spanning a long C++ code block tokenizes at ~2.5 chars/token (~1600 actual tokens) but is budgeted at 1000. Combined with thinking-budget and max-output, the call fits the 393K window but the input slice is 60% larger than intended, leaving less room for thinking+output. Truncated JSON gets retried and looks like model reliability, not tokenizer misconfiguration.

## False-fail hypothesis

A prose-heavy WG21 paper (measured ~5.5 chars/token) gets chunked at 4.0 cpt, producing smaller-than-necessary chunks. The pipeline completes correctly but with extra serial LLM calls and wall-clock cost. Inefficiency, not a functional reject.

## What would change my mind

Run token-ratio measurement against the live alliance-pod endpoint on the four canonical papers plus at least one code-heavy WG21 paper. If V4-Pro mean >= 3.8 and code-heavy floor >= 2.3, keep 4.0. If code floor < 2.3 or mean < 3.8, drop to 3.5 or adopt per-content-type ratios.
