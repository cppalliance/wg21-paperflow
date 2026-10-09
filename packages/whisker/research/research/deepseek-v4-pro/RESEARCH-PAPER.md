# Evaluating DeepSeek-V4-Pro as an Advisory Conversion-Fidelity Judge for WG21 Technical Papers: A Persona-Swarm Analysis

**Authors:** Automated Research Pipeline (Fable 5 coordinator, Composer-2.5 persona swarm)
**Date:** 2 July 2026
**Affiliation:** wg21-paperflow project, C++ Alliance

---

## Abstract

This paper evaluates DeepSeek-V4-Pro, a 1.6-trillion-parameter Mixture-of-Experts language model, for deployment as an advisory conversion-fidelity judge in the wg21-paperflow document processing system. The model is assessed against seven fidelity axes (wording, code, stable names, tables, cross-references, mathematics, and structure) relevant to ISO C++ committee papers converted from PDF and HTML to Markdown. Using a staged persona-swarm methodology, sixteen independent analyst personas, five meta-reviewers, and a same-day freshness verification pass (2 July 2026) examined published benchmarks, community feedback, serving infrastructure, and codebase compliance. The analysis finds the model **usable-with-conditions**: competitive with frontier models on coding and long-document comprehension, but exhibiting a critical abstention failure (94% non-abstention rate on uncertainty benchmarks) that, combined with an identified asymmetry in the cascade's demotion logic, creates an unguarded false-pass channel. Three blocking conditions are specified for production adoption. No source-code modifications or live endpoint probing were performed; all evidence derives from published papers, community reports, and static codebase analysis.

---

## 1. Introduction

The WG21 committee of the International Organization for Standardization (ISO) produces hundreds of technical papers annually, proposing changes to the C++ programming language standard. These papers, distributed as PDF and HTML documents, must be converted to Markdown for downstream analytical pipelines including automated dissection, objection detection, and thread planning (Falco, 2026).

The `tomd` converter within the wg21-paperflow system handles this conversion, but automated conversion is imperfect. Tables may lose cell alignment, code blocks may be garbled, mathematical notation may collapse, and heading hierarchies may be corrupted. The `whisker` quality assurance package provides deterministic, LLM-free gating on conversion quality through structural checks, content-coverage metrics, and comprehension facts (Falco, 2026). However, whisker's token-based gates have known blind spots: token-preserving semantic corruption (e.g., table cell swaps where all words are present but in wrong positions) passes the unigram coverage gate.

To address this, the `tapetum_llm` advisory lane was designed as an opt-in second opinion. It feeds the converted Markdown to a large language model and asks it to judge fidelity across seven axes. Critically, this lane **never gates**: it cannot fail a paper, cannot block CI, and cannot overwrite the whisker verdict. Its purpose is to flag potential issues for human review and, conversely, to clear false alarms in whisker's review tier.

This paper evaluates whether DeepSeek-V4-Pro is a suitable model for this advisory role, given the project's constraints: open-weight models under operator control (model sovereignty), deterministic serial execution (D1-D11 invariants), structured JSON output, and fail-not-partial fidelity requirements.

## 2. Background

### 2.1 Model Identity

DeepSeek-V4-Pro was released on 24 April 2026 by DeepSeek AI (DeepSeek AI, 2026a). It is a Mixture-of-Experts Transformer with 1.6 trillion total parameters, of which 49 billion are activated per token. The model supports a native context window of one million tokens. Key architectural features include:

- **Hybrid attention:** Compressed Sparse Attention (CSA) combined with Heavily Compressed Attention (HCA), reducing KV cache to 10% of the predecessor DeepSeek-V3.2 at one million tokens (DeepSeek AI, 2026a).
- **Manifold-Constrained Hyper-Connections (mHC):** An enhancement to residual connections for numerical stability in deep stacks (DeepSeek AI, 2026a).
- **Muon optimiser:** Replacing AdamW for most parameters, with AdamW retained for embeddings, the prediction head, and RMSNorm weights (DeepSeek AI, 2026a).
- **Post-training:** Two-stage pipeline consisting of domain-specific specialist cultivation via supervised fine-tuning and Group Relative Policy Optimisation (GRPO), followed by on-policy distillation into a unified model (DeepSeek AI, 2026a).
- **Precision:** FP4 quantisation-aware training on MoE expert weights and the indexer QK path (DeepSeek AI, 2026a).
- **Modality:** Text-only. No native image, audio, or video input (deepseekai.guide, 2026).

The model is distributed under the MIT licence and is available on HuggingFace as `deepseek-ai/DeepSeek-V4-Pro` (DeepSeek AI, 2026b).

As of the freshness verification pass conducted on 2 July 2026, the April weights remain the current checkpoint: no revised weights have been published, the DSpark variants released on 27 June 2026 attach a speculative-decoding drafter to the identical checkpoint (serving optimisation only), and DeepSeek has announced that V4 will graduate from preview to stable in mid-July 2026 with unchanged model identifiers (TechNode, 2026). Community reports of a "V4.1" remain unconfirmed by any official channel.

### 2.2 Serving Stack

In the wg21-paperflow deployment, DeepSeek-V4-Pro is served via vLLM on RunPod infrastructure. Two service entries exist in `SERVICES.toml`:

1. `h200x8-deepseek-v4-pro`: Primary instance on 8x H200 GPUs.
2. `alliance-pod`: Shared Alliance instance, billed per hour of uptime (not per token), used as the tapetum_llm endpoint.

Both use the `VllmThinkingBackend` class, which implements schema-in-prompt structured output (not constrained decoding), BPE artifact cleanup, `<think>` block stripping, and a two-attempt JSON retry with truncation-growth logic.

### 2.3 The tapetum_llm Advisory Lane

The tapetum_llm lane operates as a two-tier cascade:

1. **Triage (fast slot):** A single LLM call per paper (or per H2-chunk for papers exceeding 500,000 characters) produces an `Adjudication` object with per-axis findings, an overall verdict, a confidence score, and evidence spans.
2. **Adjudication (deep slot):** Triggered only when tier-1 confidence falls within the ambiguous band [0.35, 0.65].
3. **Decide (pure Python):** Grounds evidence spans verbatim against the Markdown, applies severity-aware worst-axis verdict aggregation, and demotes uncertain or ungrounded non-pass verdicts to "review."

The lane evaluates seven fidelity axes: wording, code, stable names, tables, cross-references, mathematics, and structure.

## 3. Methodology

### 3.1 Persona-Swarm Design

This evaluation employed a three-stage persona-swarm methodology adapted from the research skill protocol:

- **Stage 0 (Evidence Baseline):** A single coordinator pass gathered internal evidence from the codebase (`SERVICES.toml`, `model_backends.py`, `MODELS.md`, `CLAUDE.md`, tapetum_llm source code) and resolved the model's public identity via web search. The baseline document anchored all subsequent analysis with file-line references and verified benchmark numbers.

- **Stage 1 (Persona Swarm):** Sixteen independent analyst personas, each assigned a specific failure class, evaluated the model in parallel. Twelve web-facing personas conducted independent web research; four code-comparison personas analysed the codebase in read-only mode. Each persona produced a structured report with a verdict (usable/usable-with-conditions/garbage), confidence level, ranked findings with evidence, and falsification criteria.

- **Stage 2 (Meta-Review):** Five meta-reviewers independently re-verified persona claims against primary sources. Reviewer A verified benchmark numbers, B checked extraction-axis soundness, C audited serving/engineering claims against actual code, D verified web-source provenance by fetching cited URLs, and E assessed verdict balance and decision-usefulness.

- **Stage 3 (Freshness Verification):** Four scouts re-checked the currency of all load-bearing claims on 2 July 2026, covering model releases, benchmark revisions, vLLM issue status, and June 2026 community feedback. All four returned "mostly current"; the corrections (chiefly serving-stack issue statuses) are recorded in the freshness addendum and incorporated in this paper.

### 3.2 Evidence Hierarchy

All evidence was classified by provenance:

1. **Primary:** The DeepSeek V4 technical report (arXiv:2606.19348), HuggingFace model card, NIST CAISI evaluation report.
2. **Secondary:** Independent benchmark reproductions (Vals.ai, Artificial Analysis), GitHub issues with reproducer code.
3. **Tertiary:** Developer blog posts, forum discussions, aggregator sites.

Claims supported only by tertiary sources were downgraded. Claims with dead links or misattributions were dropped.

### 3.3 Limitations

This evaluation did not include live endpoint probing. All capability assessments are based on published benchmarks, community reports, and architectural analysis. No WG21-specific fidelity evaluation (e.g., table-swap detection rate, code-fence verification accuracy) was conducted. The absence of such evaluation is itself a finding.

## 4. Findings by Extraction Axis

### 4.1 Images

DeepSeek-V4-Pro is text-only; no multimodal variant exists in the V4 family (DeepSeek AI, 2026b; deepseekai.guide, 2026). The tapetum_llm lane feeds only Markdown text; the model never receives pixel data. Image extraction fidelity (raster extraction, vector image detection, figure-caption correspondence) is structurally unverifiable by any text-only model. Alt text from `![alt](path)` references is the only image information available. This is a known, accepted architectural limitation: the lane's design assumes tomd handles image extraction and whisker's structural gates catch missing images.

### 4.2 Tables

No V4-Pro-specific table benchmark exists. Capability is inferred from DeepSeek-R1 and V3 evaluations on TableEval, CompTab, CoTabBench, and TableBench, which show mid-tier structural understanding with known weaknesses on merged cells (25-44% exact match), transposed layouts, and wide tables (persona 04). The tapetum_llm `tables` axis is the highest-stakes, least-validated axis. The model is likely to detect obvious table breakage (missing rows, empty cells) but may miss token-preserving cell swaps, which are the specific failure class the lane was designed to catch.

**Risk level:** HIGH. No independent validation exists for the core use case.

### 4.3 Headings and Structure

DeepSeek-V4-Pro shows strong long-document pretraining and competitive LongBench-V2 scores (51.5, leading open models). However, no benchmark tests ATX heading hierarchy audit or WG21 section-order fidelity. The model's comprehension of document structure is inferred from general long-context capabilities. The sighting run demonstrated successful heading-monotone rescue (P3941R4 at confidence 0.95, correctly labelling severity as "minor"), providing one data point of correct behaviour (persona 06, meta-reviewer B).

**Risk level:** MEDIUM. One successful rescue observed; systematic validation pending.

### 4.4 Code Blocks

DeepSeek-V4-Pro scores 93.5% on LiveCodeBench and 80.6% on SWE-bench Verified, demonstrating strong code generation and repair capabilities (DeepSeek AI, 2026b; deepseekai.guide, 2026). Independent harnesses bracket the self-reported SWE-bench figure: NIST CAISI's held-out agentic harness measures 74%, while Vals.ai's leaderboard (updated 1 July 2026) reports 82.8%, ranking it first among open-weight models (Vals.ai, 2026). The spread illustrates harness sensitivity rather than contradiction. However, code generation benchmarks do not measure code verification ability. The CRUXEval literature shows that HumanEval gains frequently fail to transfer to code understanding tasks (persona 05). WG21 C++ papers contain template syntax (`<>` nesting, `requires` clauses, concept definitions) that PDF converters frequently garble; whether V4-Pro can reliably detect such corruption is unvalidated.

**Risk level:** MEDIUM. Strong proxy evidence from generation benchmarks; no direct verification evidence.

### 4.5 Mathematical Notation

DeepSeek-V4-Pro scores 95.2% on HMMT 2026 and 92.6% on GSM8K, demonstrating strong mathematical reasoning (DeepSeek AI, 2026b). However, math solving is distinct from math notation verification. The specific risk is false passes: the model may mentally repair corrupted formulae (e.g., reading `a/b` as `\frac{a}{b}`) and approve readable-but-wrong notation. Combined with the abstention failure, the model may confidently pass notation that a human would flag (persona 07).

**Risk level:** MEDIUM. Strong reasoning proxy; false-pass risk from over-correction.

### 4.6 English Proficiency

DeepSeek's 33-trillion-token training corpus does not disclose English/Chinese ratios. Historical DeepSeek models showed Chinese-first optimisation. However, V4-Pro demonstrates strong English performance: MMLU-Pro 87.5%, the thinking block defaults to English (GitHub issue #1257 confirms this is a systemic behaviour, not a bug), and the model was explicitly trained on agentic English-language tasks (persona 03). For WG21 technical documents written in English, the model's language proficiency is adequate. Standards-register prose and idiomatic committee vocabulary remain unbenchmarked.

**Risk level:** LOW.

### 4.7 Long-Context Performance

DeepSeek-V4-Pro's MRCR 8-needle retrieval shows 0.82 at 256K tokens and 0.59 at 1M tokens, with failures distributed randomly across positions rather than clustering in a predictable weak zone (attributed to the Lightning Indexer's compressed-block selection; jacksunwei.me, 2026). June 2026 community stress tests corroborate that this degradation is non-deterministic: the indexer sporadically misses compressed blocks rather than decaying smoothly, meaning within-window retrieval failures cannot be predicted from document position. Claude Opus 4.6 leads significantly: MRCR 1M 92.9 vs 83.5, CorpusQA 1M 71.7 vs 62.0 (DeepSeek AI, 2026b).

The wg21-paperflow configuration limits the context window to 393,216 tokens. The tapetum_llm H2-chunking threshold (500,000 characters, approximately 125,000 tokens at 4.0 chars/token) places individual calls near the 128K inflection point where degradation begins (persona 09).

**Risk level:** MEDIUM-HIGH. Chunking mitigates but does not eliminate within-chunk retrieval failures.

## 5. Compliance Analysis vs CLAUDE.md Invariants

The root `CLAUDE.md` defines non-negotiable invariants for the wg21-paperflow project. The CLAUDE-Invariant-Auditor (persona 13) classified each against V4-Pro:

| Invariant | Status | Rationale |
|---|---|---|
| Model sovereignty | COMPLIANT | MIT licence, self-hosted on RunPod |
| D1 (run_agent routing) | COMPLIANT | All calls via VllmThinkingBackend |
| D2 (sampling pins) | AT-RISK | Pins sent, but vLLM lacks batch-invariant kernels for MoE |
| D4 (parallel_tool_calls=False) | COMPLIANT | Enforced in backend |
| D6 (output_type=PydanticModel) | AT-RISK | Schema-in-prompt, not constrained decoding |
| D8 (MoE caveats) | AT-RISK | 49B/1.6T MoE under shared-pod batch composition |
| D10 (output_retries + ModelRetry) | AT-RISK | 2 JSON retries, not pydantic-ai ModelRetry |
| D11 (serial execution) | AT-RISK | Client semaphores comply; shared pod introduces variance |
| Fidelity (fail-not-partial) | AT-RISK | 94% non-abstention produces schema-valid wrong output |
| Prompt-injection defense | AT-RISK | wrap_source protects, but thinking block processes untrusted text |

No invariant is fully VIOLATED under exclusive-pod deployment. Six invariants are AT-RISK, meaning they depend on deployment discipline (exclusive pod access, correct vLLM flags) rather than architectural guarantees.

## 6. The Demotion Asymmetry: Principal Finding

The single most important finding across all sixteen personas and five meta-reviewers is a **demotion asymmetry** in the tapetum_llm cascade logic.

The `_custom_decide` function in `adjudicate.py` implements two safety demotions:

```python
if suggested_verdict != VERDICT_PASS and not grounded:
    suggested_verdict = VERDICT_REVIEW
if confidence < CONFIDENCE_DECISION_FLOOR:
    suggested_verdict = VERDICT_REVIEW
```

The first guard demotes ungrounded non-pass verdicts to "review." However, it explicitly exempts passes: a confident `pass` whose hallucinated evidence spans were all dropped by the grounding step **remains a pass**. This means the lane's headline product (review-to-pass clears that tell humans not to look) is the one output channel with no safety net against hallucinated evidence.

Combined with V4-Pro's documented abstention failure (the model guesses instead of declining when uncertain), the expected failure mode is not a noisy false fail but a clean-looking false clear. The sighting run's 72 review-to-pass clears, none verified against ground truth, represent exactly this unguarded channel.

This is the cheapest CRITICAL finding to fix (one conditional in `adjudicate.py`) and should be a blocking condition for production adoption.

## 7. Threats to Validity

1. **No live probing.** All capability assessments rely on published benchmarks and community reports, not direct evaluation on WG21 papers. The model's actual performance on table-swap detection, code-fence verification, and heading-structure audit is unknown.
2. **Benchmark contamination.** DeepSeek's self-reported numbers may be inflated by training-set overlap. NIST CAISI's independent evaluation on held-out benchmarks showed 5-7 percentage point drops on some tasks (NIST CAISI, 2026).
3. **Single sighting run.** The 2026-07-01 run provides one data point with no ground truth, all slots using the same model (no Gemma/DeepSeek split), and zero tier-2 escalations.
4. **Persona pile-on.** The 94% hallucination figure was cited by approximately nine personas but independently analysed by only three. Severity weighting was adjusted accordingly in the synthesis, but the narrative emphasis may still overstate this single finding.
5. **Temporal validity.** DeepSeek-V4 is a "preview" release scheduled to graduate to stable in mid-July 2026 with stated performance and feature improvements (TechNode, 2026). The self-hosted weights are unaffected, but hosted-API comparisons may shift. A freshness verification pass on 2 July 2026 confirmed the April checkpoint remains current and no cited benchmark had been revised; serving-stack issue statuses, which evolve weekly, were corrected as of that date (see Section 8.1, condition 3, and the freshness addendum). Open June 2026 issues on the vLLM tracker (notably #46256, silent wrong output when `add_generation_prompt` is ignored on multi-turn inputs) illustrate that the serving layer remains a moving target.

## 8. Conclusions and Recommendations

### 8.1 Decision

**ADOPT** DeepSeek-V4-Pro for the tapetum_llm advisory lane, gated on three blocking conditions:

1. **Close the confident-pass grounding gap.** Modify `adjudicate.py` so that a `pass` verdict with all emitted evidence spans dropped (or with empty evidence on a PRIMARY-risk paper) is demoted to `review`.
2. **Ground-truth audit the sighting run.** Human-verify the 6 fail-to-review rescues and a random sample (20-30) of the 72 review-to-pass clears. Acceptance criterion: false-clear rate at most 5%.
3. **Verify pod deployment.** Confirm vLLM at v0.24.0 (released 29 June 2026; absolute minimum 0.21.0) with `--tokenizer-mode deepseek_v4 --reasoning-parser deepseek_v4 --tool-call-parser deepseek_v4`. Log vLLM version per call. Note that the parser bugs cited in earlier drafts (#41132, #41240, #41483) were fixed between v0.20.1 and v0.21.0; the current watchlist comprises #46256 (tokenizer ignores `add_generation_prompt`), #46710 (inline system message handling), #47174 (`--kv-cache-dtype auto` misresolution on SM120 hardware), and the unresolved edge case of #40801 (DSML fragment leak under automatic tool choice).

### 8.2 Operational Conditions (First 30 Days)

4. Telemetry: first-attempt JSON parse rate (target >= 98%), `ungrounded_dropped / total_spans_emitted` per run, fixed-paper re-run stability (verdict flip rate <= 2%).
5. Labeled mini-evaluation: 30-50 WG21 papers with human-verified fidelity labels across the seven axes. This fills the gap identified across personas 04-07 and 09.
6. Measure `chars_per_token` on the live V4-Pro endpoint including code-heavy papers. Update or remove the deprecated `token_multiplier` field.

### 8.3 Standing Exit Criterion

If a labeled holdout of at least 50 papers shows post-decide wrong advisory fails above 15% with human agreement, or the pass-channel audit shows a false-clear rate materially above 5% after condition 1 is applied, revisit the adoption. First recourse: re-split the cascade (Gemma tier-1, V4-Pro tier-2 as originally designed) before abandoning the model.

### 8.4 Rationale

The alternative set is empty or worse. The lane requires an open-weight, self-hostable model (model-sovereignty invariant). DeepSeek-V4-Pro is the strongest available open-weight model on the axes the lane exercises. It is already deployed on per-hour billing, making re-runs cost-free. One full-corpus run has demonstrated end-to-end viability. Rejecting it means either a weaker open-weight model with the same unknowns and less capability, or retreating to a cloud API, which the project architecture forbids.

---

## References

DeepSeek AI (2026a) 'DeepSeek-V4: Towards Highly Efficient Million-Token Context Intelligence', arXiv:2606.19348. Available at: https://arxiv.org/abs/2606.19348.

DeepSeek AI (2026b) 'DeepSeek-V4-Pro Model Card', HuggingFace. Available at: https://huggingface.co/deepseek-ai/DeepSeek-V4-Pro.

DeepSeek AI (2026c) 'DeepSeek V4 Preview Release', DeepSeek API Docs. Available at: https://api-docs.deepseek.com/news/news260424.

DeepSeek AI (2026d) 'Thinking Mode', DeepSeek API Docs. Available at: https://api-docs.deepseek.com/guides/thinking_mode.

deepseekai.guide (2026) 'DeepSeek Limitations: 10 Honest Drawbacks (2026)'. Available at: https://deepseekai.guide/guides/deepseek-limitations/.

Falco, V. (2026) wg21-paperflow: Ingestion, conversion, and analysis of WG21 committee papers. C++ Alliance. Available at: https://github.com/cppalliance/wg21-paperflow (internal repository).

jacksunwei.me (2026) 'DeepSeek-V4's Ascend pivot: cheaper tokens, shakier answers'. Available at: https://jacksunwei.me/digest/ai-research/deepseek-v4-ascend-pivot-cheaper-shakier/.

MindStudio (2026) 'DeepSeek V4: What the New Open-Source Model Means for AI Developers'. Available at: https://www.mindstudio.ai/blog/deepseek-v4-open-source-model-developers.

NIST CAISI (2026) 'CAISI Evaluation of DeepSeek V4 Pro', National Institute of Standards and Technology. Available at: https://www.nist.gov/news-events/news/2026/05/caisi-evaluation-deepseek-v4-pro.

syntaxdispatch.com (2026) 'DeepSeek V4 Review: 1M Context, Pro vs Flash, Coding, Agents, and Limits'. Available at: https://www.syntaxdispatch.com/blog/deepseek-v4-review.

vLLM Project (2026a) 'DeepSeek V4 in vLLM: Efficient Long-context Attention', vLLM Blog. Available at: https://vllm.ai/blog/2026-04-24-deepseek-v4.

vLLM Project (2026b) Issue #41132: 'DeepSeek V3.2 & V4 incorrect structured output when thinking enabled' (closed 1 May 2026, fixed in v0.20.1). Available at: https://github.com/vllm-project/vllm/issues/41132.

vLLM Project (2026c) Issue #41240: 'DeepSeek V4 DSML tool parser mishandles wrapped and reserved arguments' (closed 6 May 2026, fixed in v0.21.0). Available at: https://github.com/vllm-project/vllm/issues/41240.

vLLM Project (2026d) Release v0.24.0 (29 June 2026). Available at: https://github.com/vllm-project/vllm/releases/tag/v0.24.0.

vLLM Project (2026e) Issue #46256: 'deepseek_v4 tokenizer ignores add_generation_prompt / continue_final_message' (open). Available at: https://github.com/vllm-project/vllm/issues/46256.

vLLM Project (2026f) Issue #47174: 'kv-cache-dtype auto silently wrong on Blackwell SM120' (open). Available at: https://github.com/vllm-project/vllm/issues/47174.

Vals.ai (2026) 'SWE-bench Verified Leaderboard' (updated 1 July 2026). Available at: https://www.vals.ai/benchmarks/swebench.

TechNode (2026) 'DeepSeek to launch V4 in mid-July with new peak-time API pricing' (30 June 2026). Available at: https://technode.com/2026/06/30/deepseek-to-launch-v4-in-mid-july-with-new-peak-time-api-pricing/.

Epoch AI (2026) 'DeepSeek-V4-Pro model profile'. Available at: https://epoch.ai/models/deepseek-v4-pro.

Neo Research (2026) 'DeepSeek V4 Pro Safety Evaluation' (2 June 2026). Available at: https://neoresearch.ai/research/deepseek-v4-pro-safety-evaluation/.

GitHub (2026a) Issue #1376: 'DeepSeek V4 rejects tool_choice="required"', deepseek-ai/DeepSeek-V3. Available at: https://github.com/deepseek-ai/DeepSeek-V3/issues/1376.

GitHub (2026b) Issue #1257: 'DeepSeek V4 thinking block language drift', deepseek-ai/DeepSeek-V3. Available at: https://github.com/deepseek-ai/DeepSeek-V3/issues/1257.

GitHub (2026c) Issue #1464: 'deepseek-v4-pro non-streaming timeout from default thinking', deepseek-ai/DeepSeek-V3. Available at: https://github.com/deepseek-ai/DeepSeek-V3/issues/1464.

GitHub (2026d) Issue #1471: 'June 2026 community digest', deepseek-ai/DeepSeek-V3. Available at: https://github.com/deepseek-ai/DeepSeek-V3/issues/1471.

penguinwu (2026) 'DeepSeek V4 Pro eval plan', oss-model-graph-break-corpus. Available at: https://github.com/penguinwu/oss-model-graph-break-corpus/blob/main/experiments/deepseek_v4_pro_eval_plan.md.
