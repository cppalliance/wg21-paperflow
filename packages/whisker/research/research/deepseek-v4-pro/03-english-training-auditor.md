# 03 - English-Training-Auditor

**Verdict:** usable-with-conditions — English technical reasoning is benchmark-strong and thinking defaults to English, but the undisclosed bilingual corpus still skews Chinese on factual/educational axes and leaves WG21 prose quality unvalidated.
**Confidence:** medium

## Findings

- [HIGH] DeepSeek publishes no English/Chinese/other token-percentage split for V4-Pro's 33T corpus; the V4 technical report (arXiv:2606.19348 §4.1) lists category mix only (math, code, web, long documents, multilingual) and states the corpus is "built on top of" V3 data, which itself said only that "English and Chinese constitute the majority." Evidence: arXiv:2606.19348 §4.1; DeepSeek-V3 report (arXiv:2412.19437) §2.1. Impact: we cannot quantify English exposure or rule out Chinese-first weighting; the failure class remains structurally un falsifiable from public docs.

- [HIGH] V3 explicitly traded English factual tokens for Chinese knowledge: "DeepSeek-V3 assigns more training tokens to learn Chinese knowledge, leading to exceptional performance on C-SimpleQA" while trailing GPT-4o on English SimpleQA (24.9 vs 38.2). Evidence: DeepSeek-V3 report §4.2, Table 6. Impact: historical Chinese-first optimization is documented, not inferred; V4 may have rebalanced but the company never retracted this design choice.

- [MED] V4-Pro-Max benchmark asymmetry still favors Chinese factual/educational suites over their English twins, though the English gap narrowed sharply. V4-Pro-Max: MMLU-Pro 87.5, SimpleQA-Verified 57.9, Chinese-SimpleQA 84.4; base-model C-Eval 93.1 vs MMLU-Pro 73.5 (5-shot EM). Evidence: HuggingFace model card / 00-baseline.md §1 benchmark table. Impact: English academic reasoning (MMLU-Pro) is frontier-class, but English open-web factual recall remains weaker than Chinese and than Gemini/Opus on HLE (37.7 vs Opus 40.0, Gemini 44.4); WG21 papers mix normative C++ vocabulary with committee procedural English that SimpleQA/HLE proxies do not cover.

- [MED] V4 training additions directly relevant to WG21 markdown: long-document curation prioritizing "scientific papers, technical reports, and other materials that reflect unique academic values," plus mid-training agentic traces and a dedicated coding specialist in post-training (SFT+GRPO, consolidated via on-policy distillation). Evidence: arXiv:2606.19348 §4.1, §5. Impact: the corpus shape matches technical English standards documents better than V3; code-fidelity and structure axes in tapetum_llm should benefit. No ISO C++ / WG21 wording benchmark exists to confirm standards-register recall (`SFINAE`, `noexcept`, plenary motion phrasing).

- [MED] English benchmark position vs Chinese-origin peers is strong; vs English-first frontier it is mixed. V4-Pro-Max beats GLM-5.1 Thinking on MMLU-Pro (87.5 vs 86.0), HLE (37.7 vs 34.7), LiveCodeBench (93.5 vs unreported), and leads Qwen3.5-35B-A3B on the same English-heavy suite; trails Opus 4.6 Max on MMLU-Pro (89.1), HLE (40.0), and MRCR 1M (92.9 vs 83.5). BigCodeBench Pass@1: 63.9 (V4-Pro-Base) / 59.2 (V4-Pro-Max) vs historical baseline 63.9 in 00-baseline.md. Evidence: HuggingFace README; llmreference.com comparisons; 00-baseline.md. Impact: for English code+reasoning tasks the model ranks at or above other Chinese open-weights and near US frontier on coding; for hardest English knowledge (HLE) it still lags English-first models by 2–7 points.

- [MED] Reported English prose weaknesses are real but mostly affect generative/natural-language output, not structured JSON adjudication. Third-party translation tests note Chinese-influenced English (over-passive, literal restructuring); DeepSeek's own white-collar eval (Figure 12, arXiv:2606.19348) shows V4-Pro-Max leading Opus on Chinese professional tasks (63% non-loss) while trailing on instruction-following vs Opus 4.5 on hardest multi-turn writing (45.9% win rate). Evidence: arXiv:2606.19348 §6.3; GitHub deepseek-ai/DeepSeek-V3#1255, #1257. Impact: tapetum_llm consumes English WG21 markdown and emits schema-bound findings, not literary prose; idiom/grammar risk matters mainly for `primary_concern` and `reasoning` string fields, not for axis classification or code-block spans.

- [LOW] Thinking block defaults to English at max reasoning effort, and DeepSeek acknowledges `reasoning_content` lacks stable language anchoring (issues #1226, #1257). Evidence: 00-baseline.md §5.4; GitHub #1257 official response ("in max effort mode, reasoning engine currently prioritizes English path"). Impact: positive for our English-only pipeline (`VllmThinkingBackend` strips thinking blocks before JSON extraction); occasional Chinese leakage into final output remains possible via reasoning-to-content bleed (#1226) but is rare and detectable.

- [LOW] NIST CAISI (May 2026) found V4-Pro ~8 months behind the US frontier on aggregate capability across cyber, SWE, science, reasoning, and math; no language-specific breakdown. Evidence: 00-baseline.md §1 NIST CAISI; nist.gov/news-events/news/2026/05/caisi-evaluation-deepseek-v4-pro. Impact: independent confirmation that self-reported parity is optimistic; does not isolate English training imbalance but supports treating English technical depth as "strong open-weight, not frontier" for HLE-class reasoning.

## False-pass hypothesis

A WG21 paper with subtly non-idiomatic but grammatically acceptable English (committee boilerplate, British vs American spelling mix, archaic "shall" wording) passes tapetum_llm wording-axis review because the model's Chinese-heavy factual prior treats any fluent English as correct, missing that a phrasing diverges from standard WG21 register even when the markdown is internally consistent.

## False-fail hypothesis

A correctly converted paper with dense C++20 concepts, `requires`-clauses, and standard-library proper nouns triggers a wording-axis "review" verdict because the model maps rare English standards terms to Chinese-equivalent mental glosses during thinking, then flags English phrasing as "awkward" or misattributes a legitimate term (`mandates`, `trivially copyable`) as a conversion artifact.

## What would change my mind

DeepSeek publishes V4 pre-training language histograms (English / Chinese / other token shares) showing English ≥50%, or an independent WG21-paper register benchmark where V4-Pro-Max matches or beats Opus 4.6 on terminology retention and idiomatic committee English at ≥95% agreement with expert annotators.
