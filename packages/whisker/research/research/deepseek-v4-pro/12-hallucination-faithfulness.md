# 12 - Hallucination-Faithfulness

**Verdict:** usable-with-conditions — DeepSeek-V4-Pro's abstention failure is a genuine calibration defect, not a headline artifact, but tapetum_llm's post-hoc `ground_spans` gate converts most invented quotes into review demotions rather than false passes; expect ~30–40% of emitted evidence spans to fail verbatim grounding.
**Confidence:** medium

## Findings

- [CRITICAL] AA-Omniscience reports a **94% hallucination rate** for V4-Pro (Max), 96% for V4-Flash (Max), meaning when the model lacks the correct answer it almost always guesses instead of abstaining. V4-Pro's Omniscience Index improved from -21 (V3.2) to -10, driven by higher accuracy, not better refusal. Evidence: [Artificial Analysis V4 release article](https://artificialanalysis.ai/articles/deepseek-is-back-among-the-leading-open-weights-models-with-v4-pro-and-v4-flash) (Apr 24, 2026); [BenchLM mirror](https://benchlm.ai/benchmarks/omniscienceHallucinationRate) lists V4-Pro Max at 94.0%, V4-Pro High at 88.6% (Jun 30, 2026).
  Impact: The behavioral trait transfers to tapetum_llm: when the model is uncertain about a conversion defect it is more likely to emit a confident verdict with fabricated or paraphrased evidence than to return `review` with empty spans as the system prompt instructs.

- [CRITICAL] The 94% figure is **not** "94% of all outputs are wrong." AA-Omniscience defines hallucination rate as `incorrect / (partial + incorrect + not_attempted)` among non-correct responses on 6,000 parametric-knowledge questions across 42 topics ([arXiv:2511.13029](https://arxiv.org/html/2511.13029v1), [AA methodology](https://artificialanalysis.ai/evaluations/omniscience)). It measures **overconfidence on knowledge gaps**, not quote fidelity to an in-context document. The concern for tapetum is real (same guess-instead-of-abstain reflex) but the number must not be read as a direct ungrounded-quote rate.
  Impact: Do not set `EVIDENCE_FUZZY_FLOOR` or escalation thresholds from the 94% headline; calibrate on tapetum's own span-drop telemetry instead.

- [HIGH] Independent benchmarks beyond AA-Omniscience confirm DeepSeek's citation/quoting weakness on **parametric** tasks. Digital Applied's 2026 5-model study (5,000 prompts, automated grading + 8% human audit) reports DeepSeek V4 at **15.7% citation hallucination with CoT**, 19.1% without, vs a frontier average of 12.4% on citation accuracy (worst task family). Evidence: [Digital Applied hallucination study](https://www.digitalapplied.com/blog/ai-model-hallucination-rate-benchmarks-2026-study). A separate biomedical reference study found DeepSeek at **91.43% incorrect reference generation** (likely pre-V4 API model; title/DOI/journal fields 71–100% wrong), vs ChatGPT 39.14% ([Research Square rs-6676676](https://doi.org/10.21203/rs.3.rs-6676676/v1)).
  Impact: V4-Pro is a poor choice for any workflow that trusts model-generated citations without verification. tapetum mitigates this by requiring quotes to be substrings of the provided markdown, but the same "fill the slot with plausible text" reflex drives paraphrase and invention when copying from context.

- [HIGH] Faithfulness-to-source span extraction is structurally hard for instruction-tuned LLMs even when the source is in the prompt. FullCite (Jun 2026) reports high document-level F1 but **Snippet-F1 as low as 12.8%** (prompt-only Qwen3-8B on ASQA); best posthoc alignment reaches ~62% Snippet-F1. Claim-Anchored Multi-document Summarization (Jun 2026) notes that "instruction-tuned models routinely miscount positions and **hallucinate spans**" when asked for verbatim quotes, and decouples claim extraction from deterministic offset recovery. Evidence: [FullCite arXiv:2606.07130](https://arxiv.org/html/2606.07130v1); [CAMS arXiv:2606.23989](https://arxiv.org/html/2606.23989).
  Impact: tapetum_llm's task (quote a defect from line-numbered markdown) is closer to Snippet-F1 than to AA-Omniscience. Expect materially more span failures than AA-Omniscience's headline suggests for pass-tier calls, but fewer than 94% because the source is in-context.

- [HIGH] Our grounding gate is deterministic and forgiving but not permissive. `ground_spans` (`packages/whisker/src/whisker/tapetum_llm/grounding.py`) accepts a span if `normalized_text(quote)` is a substring of `normalized_text(markdown)`, OR if `rapidfuzz.partial_ratio >= EVIDENCE_FUZZY_FLOOR` (0.90). `normalized_text` strips whitespace, punctuation, and most non-alnum (via `clean_string` in `metrics.py`), so exact-match is on an aggressive fold, not raw markdown bytes. Pure invention drops; near-miss punctuation/whitespace often survives.
  Impact: Paraphrased "evidence" (same meaning, different tokens) still drops unless fuzzy ratio saves it. BPE cleanup in `VllmThinkingBackend` can introduce quote/markdown mismatches on edge characters. Wrong-section quotes that substring-match elsewhere in the paper **pass grounding** (false-pass path).

- [MED] Abstention failure manifests in tapetum_llm as four observable patterns: (1) **invented quotes** that fail `ground_spans` and increment `ungrounded_dropped`; (2) **paraphrased quotes** of real defects that fail fuzzy floor; (3) **high `confidence` with empty or dropped evidence** on non-pass verdicts, triggering demotion in `_custom_decide` (`adjudicate.py` lines 234–240: non-pass + no grounded spans → forced `review`; confidence < 0.50 → forced `review`); (4) **wrong-but-grounded quotes** from a similar-looking region (table row elsewhere, shared identifier text) that pass grounding but misidentify the defect.
  Impact: Patterns 1–3 are caught by existing safety demotions (lane never hard-fails). Pattern 4 is the residual false-pass risk the grounding layer cannot see.

- [MED] GLM-5 demonstrates that refusal calibration is a **trainable design choice**, not a MoE ceiling: Artificial Analysis reports GLM-5 achieved a **56 percentage-point reduction** in AA-Omniscience hallucination rate via a trained refusal mechanism, while DeepSeek V4 did not ([OfficeChai V4 summary](https://officechai.com/ai/deepseek-v4-pro-becomes-second-highest-rated-open-model-on-artificial-analysis-index-with-score-of-52/)). No HaluEval, FActScore, or RAGAS faithfulness score for V4-Pro was found in public sources.
  Impact: Do not expect V4-Pro to self-correct abstention via prompt engineering alone; the deep slot should stay behind `ground_spans` + demotion, not replace them.

- [LOW] **Quantified expected `ungrounded_dropped` rate** (no V4-Pro tapetum production telemetry exists yet; estimate from benchmark analogs + grounding mechanics):

  | Scope | Expected drop rate | Basis |
  |---|---|---|
  | Per emitted evidence span | **30–40%** (point: **35%**) | FullCite prompt-only Snippet-F1 13–44% on multi-doc QA; tapetum is single-doc with explicit verbatim instruction and fuzzy 0.90 recovery, which should beat that floor but not eliminate paraphrase/invention under abstention failure |
  | Adjudications with ≥1 span | **~40%** lose ≥1 span | Conditional on model emitting evidence (fail/review cases) |
  | All deep-tier calls (population-weighted) | **~8–15%** lose ≥1 span | Most candidates are pass-tier with empty `evidence_spans` per system prompt ("pass with high confidence and empty evidence"); drops concentrate in ambiguous defect calls |

  Scenarios: pass-only calls → 0% span drop; table/code defect flags with 2–3 spans → upper band (~45–55% per-span drop); rescue heading-monotone cases → lower band (~15–25%) because quotes are short and local.

  Impact: Budget deep-slot cost assuming ~1 in 3 evidence-bearing calls wastes at least one span. Track `ungrounded_dropped / len(evidence_spans)` in inspect reports before tightening confidence bands.

## False-pass hypothesis

A silently transposed table row in a 200-column straw-poll pipe table: V4-Pro flags `tables`/`pass` on other axes, emits `confidence=0.68`, and quotes a **real substring** from a different table in the same chunk ("N/A" cell text that appears in both tables). `ground_spans` passes; Decide does not demote; advisory suggests pass while the transposition remains invisible.

## False-fail hypothesis

A genuine merged-cell flattening defect in a feature-test table: V4-Pro correctly identifies the axis (`tables`, `fail`, `major`) but paraphrases the cell value ("__cpp_lib_foo" → "cpp lib foo bar") instead of copying verbatim. Quote fails substring and fuzzy floor; `ungrounded_dropped=1`; non-pass + no grounded spans forces demotion to `review`. Human must re-read the paper despite a real major defect.

## What would change my mind

A production tapetum_llm run on ≥50 WG21 candidate papers (deep tier, same vLLM thinking + schema-in-prompt stack) logging `ungrounded_dropped / total_spans_emitted < 15%` with ≤2% of non-pass adjudications grounding to the wrong document region (human audit of inspect reports).
