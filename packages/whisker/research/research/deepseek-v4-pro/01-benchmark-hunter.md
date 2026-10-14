# 01 - Benchmark-Hunter

**Verdict:** usable-with-conditions — Strong open-weight scores on code and English knowledge benchmarks are real but narrower than DeepSeek's frontier-parity narrative; independent evals show an ~8-month capability lag, a 94% "answer anyway" hallucination rate when uncertain, and material long-context retrieval gaps that matter for full-paper advisory triage.
**Confidence:** medium

## Findings

- [CRITICAL] DeepSeek's self-reported frontier parity does not survive NIST CAISI's held-out benchmark suite. CAISI (May 1, 2026) placed V4-Pro closest to GPT-5 (~8 months behind the US frontier), with IRT Elo 800 ± 28 vs GPT-5.5 at 1260 ± 28 and Opus 4.6 at 999 ± 27; CAISI explicitly notes V4 "scores better on DeepSeek's self-reported evaluations than on CAISI evaluations." On uncontaminated tasks: ARC-AGI-2 semi-private 46% (Opus 4.6 max 63%, GPT-5.5 79%), PortBench 44% (GPT-5.5 78%), CTF-Archive-Diamond 32% (GPT-5.5 71%). Evidence: https://www.nist.gov/news-events/news/2026/05/caisi-evaluation-deepseek-v4-pro (May 1, 2026).
  Impact: tapetum_llm asks for cross-axis document reasoning and calibrated verdicts; CAISI's agentic and abstract-reasoning gaps predict false confidence on ambiguous conversion defects, not just slow inference.

- [CRITICAL] Independent hallucination measurement: 94% hallucination rate on Artificial Analysis AA-Omniscience (V4-Pro Max, April 24, 2026). When the model lacks knowledge, it "nearly always respond[s] anyway" rather than abstaining; AA-Omniscience index improved to -10 vs V3.2's -21, but refusal calibration did not. Evidence: https://artificialanalysis.ai/articles/deepseek-is-back-among-the-leading-open-weights-models-with-v4-pro-and-v4-flash (April 24, 2026); corroborated by https://jacksunwei.me/digest/ai-research/deepseek-v4-ascend-pivot-cheaper-shakier/ (2026).
  Impact: tapetum_llm's `ground_spans` catches non-verbatim quotes, but a model that almost never abstains will burn triage calls on invented evidence and may still emit high `confidence` before grounding demotes the result.

- [HIGH] Long-context retrieval trails the frontier benchmark DeepSeek itself re-standardized. On MRCR 1M (MMR): V4-Pro 83.5 vs Claude Opus 4.6 92.9; on CorpusQA 1M (ACC): V4-Pro 62.0 vs Opus 4.6 71.7 (DeepSeek arXiv re-eval, June 2026). HuggingFace's release analysis adds MRCR 8-needle accuracy ~0.82 at 256K, falling to ~0.59 at 1M. Evidence: https://arxiv.org/html/2606.19348 (arXiv:2606.19348, April 2026); https://huggingface.co/blog/deepseekv4 (April 24, 2026).
  Impact: H2-chunking at 500K chars keeps individual calls below the worst cliff, but within-chunk random retrieval misses can cause false "pass" on xrefs, structure, or tables when the defect sits in a missed region of a long paper.

- [HIGH] Vendor SWE-bench Verified headline (80.6%) is not reproduced under independent harnesses. CAISI SWE-Bench Verified: 74% (notes CAISI scores "tend to be lower" due to scaffolding/token budget). Vals.ai mirror: 77.40%. DeepSeek self-report: 80.6%. benchr.org (May 30, 2026) labels 80.6% "DeepSeek-reported, not yet independently reproduced" on a public leaderboard. On harder suites: SWE-bench Pro ~55.4% (vendor aggregate per evals.report, Apr 2026); DeepSWE ~7.5–8% pass@1 (evals.report, Apr 2026). Evidence: NIST CAISI table (May 2026); https://benchlm.ai/benchmarks/valsSweBench (2026); https://benchr.org/articles/deepseek-review (May 30, 2026); https://evals.report/models/deepseek-v4-pro (Apr 24, 2026).
  Impact: The `code` fidelity axis may look strong on short, well-scoped blocks but underperform on messy real-repo-style diffs; WG21 code blocks with subtle formatting regressions are closer to the latter.

- [MED] English language proficiency benchmarks are solid but not independently exceptional for advisory fidelity. MMLU-Pro EM 87.5% (DeepSeek model card / arXiv:2606.19348 Table, April 2026). Artificial Analysis Intelligence Index 52 for V4-Pro Max (#2 open-weights reasoning model, April 24, 2026). CAISI GPQA-Diamond 90% (near GPT-5.5 96%). No independent English-only document-fidelity benchmark found for V4-Pro.
  Impact: English markdown parsing and academic register are unlikely to be the bottleneck; the gap is judgment under ambiguity, not basic comprehension.

- [MED] Structured JSON output has no independent compliance benchmark for V4-Pro; vendor docs admit imperfection. DeepSeek API JSON mode is "designed to return valid JSON, not guaranteed"; `json_schema` response format is not supported for chat completions; empty content can occur under load. Our stack uses schema-in-prompt + free-text extraction (see `00-baseline.md` §2), not constrained decoding. Evidence: https://api-docs.deepseek.com/guides/json_mode (2026); https://deepseekai.guide/api/deepseek-api-best-practices/ (2026).
  Impact: The 7-field `Adjudication` schema (nested `axis_findings`, `evidence_spans`) is more complex than API JSON-mode demos; parse/retry failures are a measurable operational risk even when semantic reasoning is correct.

- [LOW] No published independent table-understanding or document-QA score for V4-Pro. TableBench leaderboard lists DeepSeek-R1 (56.31 overall, Jan 2025) and DeepSeek-V3 (50.56, Mar 2025), not V4-Pro. DocVQA leaderboards cover DeepSeek-VL2 (93.3%), a separate vision model; V4-Pro is text-only per DeepSeek limitations docs. Evidence: https://tablebench.github.io/ (leaderboard, 2025–2026); https://aiwartracker.com/benchmarks/docvqa (2026); `00-baseline.md` §1 (text-only).
  Impact: `tables` and figure-adjacent fidelity (alt-text only) lack external validation; vendor LongBench-V2 lead (51.5 EM, arXiv) is self-reported and measures long-document QA, not markdown table preservation.

## False-pass hypothesis

A 350K-character WG21 paper with a silently merged table header row: V4-Pro triage returns `verdict=pass` on the `tables` axis with `confidence=0.72`, citing an evidence span that is a real substring from the document but from the wrong table section ( Lightning Indexer / sparse attention retrieves a similar-looking row elsewhere in the chunk). Grounding passes; Decide does not demote.

## False-fail hypothesis

A conversion that correctly normalizes WG21 editorial punctuation (hyphen vs en-dash policy) but leaves wording semantically identical: V4-Pro flags `wording` axis `fail` with `confidence=0.78` and a quote that matches the markdown verbatim, triggering unnecessary deep-slot adjudication on a benign stylistic delta the deterministic whisker tier already accepted.

## What would change my mind

A held-out, third-party benchmark on WG21-style markdown fidelity (verbatim span extraction + per-axis verdict agreement with expert annotators on ≥50 full papers, including 100K–400K char cases) showing ≥90% axis-level agreement and ≤5% confident wrong-pass rate — run with the same vLLM thinking + schema-in-prompt stack we deploy, not DeepSeek's API JSON mode alone.
