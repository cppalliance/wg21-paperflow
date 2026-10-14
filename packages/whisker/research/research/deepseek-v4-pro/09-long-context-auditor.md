# 09 - Long-Context-Auditor

**Verdict:** usable-with-conditions — The 393K configured window and H2 chunking at 500K chars keep tapetum_llm calls out of the worst 1M degradation band, but V4-Pro's hybrid CSA/HCA attention still degrades beyond 128K with random-position retrieval misses; scattered evidence-span tasks behave like multi-needle workloads, not the single-needle scores vendors highlight.
**Confidence:** medium

## Findings

- [CRITICAL] Official MRCR curve shows stability only through 128K; degradation is visible beyond that and steepens toward 1M. DeepSeek arXiv:2606.19348 §5.3 (Figure 9): "retrieval performance remains highly stable within a 128K context window. While a performance degradation becomes visible beyond the 128K mark." HuggingFace release analysis adds MRCR 8-needle accuracy ≥0.82 through 256K, falling to 0.59 at 1M (https://huggingface.co/blog/deepseekv4, April 24, 2026). Aggregate MRCR 1M (MMR): V4-Pro 83.5 vs Claude Opus 4.6 92.9 (`00-baseline.md` §1).
  Impact: tapetum_llm injects the full chunk as one prompt; any chunk whose paper body plus overhead exceeds ~128K tokens enters the degradation zone where random retrieval misses become plausible.

- [HIGH] The 393,216-token `max_context_window` in SERVICES.toml sits in the upper half of the empirically observed "effective context" band (200K–400K), not in the pre-128K safe zone. Linear interpolation between published MRCR 8-needle anchors (0.82 @ 256K, 0.59 @ 1M) yields ~0.76 at 393K — a ~28% relative drop from the 256K plateau. Independent long-context synthesis (Digital Applied, April 2026) recommends designing non-Gemini stacks for effective context at 200–400K, not claimed 1M. Evidence: `SERVICES.toml` lines 52, 69; https://www.digitalapplied.com/blog/long-context-retrieval-needle-in-haystack-2026.
  Impact: The pod cap is a prudent operational choice (38% of native 1M) that avoids serving at the 0.59 cliff, but a prompt that actually fills 393K tokens is still in measurable degradation territory — not a "safe zone" in the arXiv sense.

- [HIGH] Skywork stress tests and follow-on analysis report non-deterministic, position-random retrieval failures attributed to the Lightning Indexer missing compressed KV blocks — not classic "lost in the middle" positional bias. jacksunwei.me (April 2026) cites Skywork.ai: "Failures in retrieval and reasoning appear randomly across different positions in the 1M window rather than clustering in a fixed weak zone… attributed to the Lightning Indexer and sparse attention sporadically missing specifics during compression." Evidence: https://jacksunwei.me/digest/ai-research/deepseek-v4-ascend-pivot-cheaper-shakier/; Skywork guide referenced therein.
  Impact: tapetum_llm cannot rely on placing critical defects at prompt start/end; H2 chunking reduces window size but does not eliminate indexer false negatives within a chunk. Ungrounded evidence drops and confidence demotion catch some misses, but a confident wrong-axis pass on an unexamined region remains possible.

- [HIGH] Needle-in-a-haystack numbers understate tapetum_llm's workload; multi-needle and reasoning-over-context scores are much harsher. Digital Applied NIAH-2 (April 2026): V4-Pro single-needle 96% @ 200K → 78% @ 1M; 8-needle 84% @ 200K → 41% @ 1M (largest single→multi drop of any frontier model, −37 pts at 1M). tapetum_llm asks the model to locate multiple fidelity defects and quote verbatim spans across an entire chunk — structurally closer to 8-needle than single-needle. Evidence: https://www.digitalapplied.com/blog/long-context-retrieval-needle-in-haystack-2026.
  Impact: Chunks sized at ~125K tokens (500K chars ÷ 4.0 chars/token per `constants.py` MAX_PAPER_MD_CHARS) may still behave like multi-needle tasks; the 84% @ 200K multi-needle ceiling is the more relevant anchor than the 96% single-needle score.

- [MED] RULER-class evaluation is absent from the official model card; third-party RULER summaries place V4-Pro below the 80% production threshold at 256K. DeepSeek arXiv:2606.19348 reports LongBench-V2 (51.5 EM) and MRCR/CorpusQA but no RULER table. Digital Applied (April 2026): at RULER 256K, only Gemini 3 Deep Think stays above 80%; GPT-5.5 72%, Opus 4.7 61%, with V4-Pro implied in the sub-80% cohort. A separate blog (TechPlained) claims RULER 91.3% @ 1M — uncorroborated by arXiv or CAISI and likely cherry-picked. Evidence: arXiv:2606.19348 Table; https://www.digitalapplied.com/blog/long-context-retrieval-needle-in-haystack-2026.
  Impact: tapetum_llm requires reasoning over retrieved markdown (compare conversion vs expected structure, judge table integrity), not pure quote-back; RULER's 10–25 pt gap below NIAH suggests within-chunk fidelity judgments degrade faster than raw retrieval metrics imply.

- [MED] CSA/HCA hybrid attention trades KV efficiency for retrieval fidelity at long range; degradation is architectural, not merely a training-data artifact. CSA: 4× sequence compression + FP4 Lightning Indexer selecting top-1024 compressed blocks + 128-token local sliding window (HuggingFace blog; arXiv §3). HCA: 128× compression with dense attention on summaries — fine token detail is discarded. Acing AI and dissecting-ai.dev note indexer mis-scoring and HCA summary noise as distinct failure modes under domain shift or repetitive corpora. At 1M tokens V4-Pro uses 27% of V3.2 FLOPs and 10% KV cache (arXiv Figure 1) — the efficiency gain is real and paid for in compression loss.
  Impact: WG21 papers mix dense code blocks, pipe tables, and boilerplate section headers — repetitive structure increases HCA noise and CSA indexer collision risk; a table cell swap in the middle of a 120K-token chunk is exactly the token-level detail compression erases.

- [LOW] H2 chunking at MAX_PAPER_MD_CHARS=500,000 keeps typical tapetum_llm calls near the 128K inflection, not at the 393K cap. Budget math: 500,000 chars ÷ 4.0 chars/token (`SERVICES.toml` chars_per_token) ≈ 125,000 paper tokens per chunk, plus system prompt and schema overhead — well under 393,216 and far under 1M. Only ~6 corpus papers exceed the char threshold (`constants.py` comment); they are triaged serially and aggregated worst-axis (`chunking.py`). Evidence: `packages/whisker/src/whisker/tapetum_llm/constants.py` line 44; `00-baseline.md` §3.
  Impact: For the majority of papers the lane operates at the edge of the arXiv "stable through 128K" band, not in the 393K degradation band — but "edge" plus multi-needle task shape still permits within-chunk misses.

- [LOW] Anecdotal single-needle success at 435K (HuggingFace blog author test, V4-Flash non-thinking, 100% depth sweep) does not contradict the MRCR multi-needle curve — different task, different mode. Evidence: https://huggingface.co/blog/deepseekv4 (personal test note).
  Impact: Do not use vendor anecdotal NIAH passes to set tapetum_llm confidence; the advisory lane runs thinking mode with structured multi-axis output.

## False-pass hypothesis

A 480K-char WG21 paper split into one ~125K-token H2 chunk plus a smaller tail chunk. A table row transposition in section 7 (mid-chunk, ~60% depth) is missed because the Lightning Indexer fails to surface that compressed block during CSA sparse selection on this run. Triage returns `verdict=pass`, `tables=pass`, `confidence=0.68`, with evidence spans drawn only from the paper header and a code block the model did see. Grounding passes on those quotes; Decide emits pass because no axis flags fail and confidence exceeds 0.50.

## False-fail hypothesis

An oversize paper chunked into five serial H2 segments: chunk 3 alone contains a genuine `structure` defect, but aggregation takes the worst-axis fold across chunks and chunk 1's spurious `wording=review` ( indexer retrieved a boilerplate paragraph and over-interpreted punctuation) dominates, producing an overall `review` on a paper whose only real defect was localized and minor.

## What would change my mind

A tapetum_llm-specific long-context eval on ≥20 real WG21 papers in the 100K–350K token range (single-chunk and multi-chunk), measuring: (a) axis-level agreement with expert labels when the defect is placed at randomized depths, and (b) repeat-run stability under serial execution — showing ≥90% defect recall with ≤5% confident wrong-pass rate. Run on our alliance-pod vLLM stack at 393K cap, not DeepSeek's API harness.
