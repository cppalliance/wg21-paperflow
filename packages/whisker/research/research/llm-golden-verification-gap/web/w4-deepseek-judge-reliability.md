# W4 — DeepSeek judge/evaluator reliability (web forage)

Topic: DeepSeek v3/v3.1/r1/v4 family as judges/evaluators, 2025–2026. Facts only.

---

- DeepSeek-R1 scores 14.3% hallucination rate on Vectara HHEM summarization benchmark vs 3.9% for DeepSeek-V3 on the same dataset (≈4× gap). URL: https://www.vectara.com/blog/deepseek-r1-hallucinates-more-than-deepseek-v3 — date: 2025 — relevance: R1 reasoning mode is materially less factually grounded than V3 in summarization QA, a direct analogue to source-grounded document QA.

- Vectara leaderboard (temperature 0) reports DeepSeek-R1 at 11.3% factual-inconsistency rate vs DeepSeek-V3 at 6.1%; DeepSeek-V3.1 at 6.1%; DeepSeek-V3.2 at 6.3%; DeepSeek-V3.2-Exp at 5.3%. URL: https://github.com/vectara/hallucination-leaderboard — date: 2025–2026 — relevance: even at temperature 0, R1 remains ~2× worse than V3 family on grounded summarization; V3.x variants cluster near 6%.

- Human validation on 50 R1/V3 divergent samples: 46/50 R1 summaries flagged hallucinated vs 19/50 V3; 33/46 R1 hallucinations classified "benign" (71.7%) vs 7/19 for V3 (36.8%). URL: https://www.vectara.com/blog/why-does-deepseek-r1-hallucinate-so-much — date: 2025 — relevance: R1 adds plausible-sounding unsupported content, matching false-clear patterns where the judge "finds" defects that aren't there or misses real ones with high confidence.

- Vanilla LLM-as-judge agreement with human hallucination labels: R1 14%, V3 63%; sentence-level reasoning LLM-as-judge: R1 78%, V3 62%. URL: https://www.vectara.com/blog/why-does-deepseek-r1-hallucinate-so-much — date: 2025 — relevance: raw R1 judge calls are near-random; structured sentence-level judging helps R1 but V3 is already stronger at vanilla judging.

- DeepSeek V4 Pro posts 94% AA-Omniscience hallucination rate and Omniscience Index −23; V4 Flash 96%; no confirmed Vectara score yet. URL: https://suprmind.ai/hub/ai-hallucination-rates-and-benchmarks/ — date: July 2026 — relevance: newest DeepSeek release (user's deepseek-v4-pro) shows extreme overconfidence on knowledge QA independent of grounded summarization scores.

- Sage benchmark (650 questions, no human labels): DeepSeek-R1-0528 overall IPI (local pairwise inconsistency) 0.115 / TOV (global transitivity violation) 1.759 on Sage-Easy; on Sage-Hard IPI 0.396 / TOV 6.362. URL: https://arxiv.org/pdf/2512.16041 — date: December 2025 — relevance: R1 is among the better open models on easy cases but still shows ~4× TOV degradation on hard pairwise judging, consistent with verdict flips when answer quality is subtle.

- Sage Sage-Hard: DeepSeek-V3-0324 IPI 0.467 / TOV 7.446; DeepSeek-V3.1 IPI 0.460 / TOV 7.756; DeepSeek-R1-0528 IPI 0.396 / TOV 6.362 (R1 slightly better than V3 on hard TOV but all mid-pack). URL: https://arxiv.org/pdf/2512.16041 — date: December 2025 — relevance: V3/V3.1/R1 all exhibit substantial judge inconsistency on close-call pairs; no DeepSeek model reaches top-tier Gemini-2.5-Pro robustness.

- Sage: all 13 benchmarked judges show ~200% IPI/TOV increase from Sage-Easy to Sage-Hard; GPT-5 and Gemini-2.5-Pro fail consistent preferences on nearly a quarter of difficult cases. URL: https://arxiv.org/pdf/2512.16041 — date: December 2025 — relevance: ≥25% verdict instability on identical reruns is within published SOTA judge failure rates, not an outlier of misconfiguration alone.

- Sage: explicit self-generated rubrics per question reduce IPI 16.1% and TOV 11.0% across models; situational preference (shifting criteria across answer pairs) identified as primary instability driver. URL: https://arxiv.org/pdf/2512.16041 — date: December 2025 — relevance: contract-encoding gaps in prompts (golden rules not in rubric) directly map to Sage's situational-preference failure mode.

- Sage: POLL multi-model panels improve judge robustness up to ~15%; weaker panel includes DeepSeek-V3.1 alongside Gemini-2.0-Flash-Lite and GPT-4o-mini; panel aggregation beats best individual in most cases. URL: https://arxiv.org/pdf/2512.16041 — date: December 2025 — relevance: ensemble/panel judging is a published mitigation when single DeepSeek judge flips.

- Sage: ChatEval multi-agent debate hurts judge quality vs single judge; only panel voting helps. URL: https://arxiv.org/pdf/2512.16041 — date: December 2025 — relevance: not all multi-call judge schemes help; self-consistency voting ≠ debate.

- "Reasoning Model Is Superior LLM-Judge" (DeepSeek-V3 vs DeepSeek-R1): R1 beats V3 on judgment accuracy and instruction-following (RR 95.48% vs 88.55%) but R1 BiasBench robustness 65.0% vs V3 81.25%; R1 shows stronger superficial-quality and position biases. URL: https://arxiv.org/pdf/2601.03630 — date: January 2026 — relevance: R1 is a better judge on average yet more bias-vulnerable; accuracy and stability diverge.

- PlanJudge (explicit evaluation plan before verdict): DeepSeek-R1 BiasBench robustness rises from 65.0% to 97.50% (+32.5 pp) with combined heuristic+self plan; DeepSeek-V3 from 81.25% to 98.75% (+17.5 pp). URL: https://arxiv.org/pdf/2601.03630 — date: January 2026 — relevance: lightweight prompt-only rubric/plan step is a published bias/stability mitigation without fine-tuning.

- DeepSeek-R1 underperforms DeepSeek-V3 on Knowledge judge tasks in the reasoning-judge paper; attributed to R1 "zero" training and higher knowledge hallucination. URL: https://arxiv.org/pdf/2601.03630 — date: January 2026 — relevance: R1-as-judge on factual/document QA may regress vs V3 despite overall judge gains elsewhere.

- WMT24 Metrics Benchmark: DeepSeek-R1 consistency correlation with humans 0.565 vs DeepSeek-V3 0.331 (+70%); but R1 underperforms V3 on most MT metric correlations (e.g., en-de 0.364 vs 0.490). URL: https://arxiv.org/pdf/2504.08120 — date: April 2025 — relevance: R1 judge gains are task-dependent; consistency evaluation improves but general NLG judging may worsen vs V3.

- "Are Reasoning Models More Prone to Hallucination?": DeepSeek-R1 improves SimpleQA accuracy over DeepSeek-V3-Instruct (28.5% vs 23.8%) via SFT+RL, but summarization hallucination benchmarks show the opposite direction for R1. URL: https://arxiv.org/html/2505.23646v1 — date: May 2025 — relevance: task and metric choice determines whether R1 is "better"; no single reliability verdict across judge/evaluator settings.

- DeepSeek API JSON mode (`response_format: json_object`) requires the word "json" in prompt plus an example schema; API docs warn JSON mode may occasionally return empty content. URL: https://api-docs.deepseek.com/guides/json_mode — date: 2025–2026 — relevance: structured-output reliability is prompt-dependent and not guaranteed even with schema mode.

- DeepSeek strict tool-calls (beta `/beta` endpoint, `strict: true`) enforce JSON Schema on function arguments; all object properties must be required and `additionalProperties: false`; server rejects unsupported schema constraints. URL: https://api-docs.deepseek.com/guides/tool_calls — date: 2025–2026 — relevance: schema compliance is achievable but with restrictive schema subset; differs from pydantic validators that only check post-hoc consistency.

- DeepSeek evaluation framework docs state JSON validity and schema correctness must be tested, not assumed; low-temperature calls can still vary across model versions, providers, and retrieval states. URL: https://chat-deep.ai/docs/deepseek-evaluation-framework/ — date: 2025–2026 — relevance: vendor acknowledges non-determinism and structured-output testing burden for production eval pipelines.

- vLLM batch invariance (`VLLM_BATCH_INVARIANT=1`) tested on DeepSeek-V3, V3-0324, DeepSeek-R1, DeepSeek-V3.1; forces deterministic kernels for matmul/RMSNorm/attention at performance cost. URL: https://docs.vllm.ai/en/latest/features/batch_invariance/ — date: 2025–2026 — relevance: primary published fix for MoE/vLLM run-to-run verdict flips under varying batch load on self-hosted DeepSeek.

- Thinking Machines / vLLM batch-invariance experiment: 1000 temperature-0 completions without batch-invariant kernels yielded 80 unique outputs; first divergence at token ~103; with batch-invariant kernels outputs were bitwise identical. URL: https://www.linkedin.com/posts/bunty-shah_defeating-nondeterminism-in-llm-inference-activity-7381001996125892608-_hfK — date: 2025 — relevance: quantifies how inference batch composition alone can flip judge verdicts even at temperature 0, matching observed ≥25% flip rate.

- NeurIPS 2025 oral (Yuan et al., via Medium summary): BF16 on DeepSeek-R1-Distill-Qwen-7B gives AIME accuracy std dev 9.15% vs 0% under FP32; tiny logit gaps mean rounding flips top token. URL: https://medium.com/@roanmonteiro/same-prompt-two-answers-the-anatomy-of-nondeterminism-in-llms-3cbbe2b39409 — date: 2025 — relevance: MoE/reasoning models with narrow token margins are especially sensitive to FP16/BF16 nondeterminism on vLLM.

- TBIK paper: MoE models suffer "much more severe" probability divergence across tensor-parallel sizes than dense models because small perturbations route to different experts; TBIK achieves bit-wise deterministic inference in vLLM. URL: https://arxiv.org/pdf/2511.17826 — date: November 2025 — relevance: expert-routing nondeterminism is a MoE-specific amplifier beyond batch variance; relevant to DeepSeek 671B MoE served on multi-GPU vLLM.

- vLLM reproducibility docs: vLLM does not guarantee reproducibility by default; online `vllm serve` cannot be fully deterministic without batch invariance; same hardware and vLLM version still required. URL: https://docs.vllm.ai/en/v0.18.0/usage/reproducibility/ — date: November 2025 — relevance: temperature 0 + fixed seed is insufficient on vLLM serve paths used for alliance pod judging.

- GitHub vLLM discussion: Qwen2.5-14B on vLLM still diverges with temperature=0, top_p=1, seed=42 across serve vs offline, GPU count, vLLM version, H100 vs H200. URL: https://github.com/vllm-project/vllm/discussions/17166 — date: 2025 — relevance: cross-environment judge reproducibility is best-effort even with greedy decoding pins.

- VERDI (May 2026): on Qwen3.5-4B/9B/27B with greedy decoding, answer-token logprobs are anti-calibrated (AUROC 0.32–0.49: higher logprob on errors); 99.4–100% of structured-JSON logprobs saturate above 0.999 on GPT models. URL: https://arxiv.org/html/2605.11334v1 — date: May 2026 — relevance: directly explains false-clears at 0.95–1.00 self-reported confidence; logprob confidence unusable for open-weight MoE judges with JSON output.

- VERDI recommends decomposed reasoning-trace signals (step-verdict alignment, evidence grounding) with Platt scaling instead of logprobs or verbalized confidence for judge trust. URL: https://arxiv.org/html/2605.11334v1 — date: May 2026 — relevance: published alternative to self-reported judge confidence fields in tapetum_llm sidecars.

- ACL 2026 industry paper "Calibrating LLM Judges": linear probes on hidden states beat verbalized confidence and self-consistency for calibration on dense and MoE judge models with less compute than multi-sample voting. URL: https://aclanthology.org/2026.acl-industry.14.pdf — date: 2026 — relevance: probe-based confidence requires hidden-state access (possible on self-hosted vLLM, not API).

- "Teaming LLMs to Detect and Mitigate Hallucinations" (Oct 2025): consortium voting (multi-model self-consistency) and consortium entropy beat single-model self-consistency in >92% of evaluated teams while reducing cost via smaller model pools. URL: https://arxiv.org/pdf/2510.19507 — date: October 2025 — relevance: ensemble judging mitigation extends beyond single DeepSeek reruns.

- "Overconfidence in LLM-as-a-Judge" (Aug 2025): LLM-as-a-Fuser ensemble on Qwen3-235B achieves +8.86% accuracy and −5.36% ECE vs self-confidence; Mistral-Nemo gains up to +47% accuracy / −53% ECE via fusion. URL: https://arxiv.org/html/2508.06225v2 — date: August 2025 — relevance: self-reported judge confidence is systematically overconfident; fusion/ensemble calibration is a published fix.

- vLLM 0.22 adds production DeepSeek V4 support (1.6T total, 49B active MoE) and batch-invariance latency improvements (28.9% Cutlass FP8 path). URL: https://www.besthub.dev/articles/vllm-0-22-release-production-ready-deepseek-v4-and-extreme-kv-cache-compression-ceb0901cf8f5 — date: 2026 — relevance: deepseek-v4-pro deployment stack has explicit batch-invariance path but V4 hallucination benchmarks already show severe overconfidence.
