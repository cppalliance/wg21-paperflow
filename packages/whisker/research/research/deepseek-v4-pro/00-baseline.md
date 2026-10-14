# 00 - Evidence Baseline: DeepSeek-V4-Pro

**Date:** 2026-07-02
**Analyst:** Fable 5 coordinator (Step 0)
**Target:** DeepSeek-V4-Pro, served on Alliance RunPod via vLLM
**Comparison codebase:** wg21-paperflow monorepo (whisker tapetum_llm advisory lane)

---

## 1. Model Identity Resolution

**Served name:** `deepseek-v4-pro` (in SERVICES.toml lines 47, 64)
**Public release:** DeepSeek-V4-Pro, released April 24, 2026 (arXiv:2606.19348)
**HuggingFace:** `deepseek-ai/DeepSeek-V4-Pro`
**License:** MIT (open-weight)

### Architecture
- **Type:** Mixture-of-Experts (MoE) Transformer
- **Total parameters:** 1.6 trillion
- **Active parameters per token:** 49 billion
- **Native context window:** 1,000,000 tokens
- **Configured context (SERVICES.toml):** 393,216 tokens (`max_context_window` line 52, 69)
- **Precision:** FP4 + FP8 Mixed (quantization-aware training on MoE expert weights)
- **Attention:** Hybrid CSA (Compressed Sparse Attention) + HCA (Heavily Compressed Attention)
- **Optimizer:** Muon (AdamW for embeddings, prediction head, RMSNorm)
- **Pre-training data:** 33 trillion tokens, diverse multilingual
- **Sequence length schedule:** 4K -> 16K -> 64K -> 1M (dense attention first 1T tokens, then sparse)
- **Post-training:** Two-stage: domain-specific specialist SFT+GRPO, then On-Policy Distillation (OPD)
- **Vision:** Text-only. No native image, audio, or video input. (Source: deepseekai.guide/guides/deepseek-limitations/)

### Key Benchmark Numbers (from model card + independent evals)

| Benchmark | V4-Pro Score | Claude Opus 4.6 | Notes |
|---|---|---|---|
| SWE-bench Verified | 80.6% | 80.8% | Near-parity |
| Terminal-Bench 2.0 | 67.9% | 65.4% | V4-Pro leads |
| LiveCodeBench | 93.5% | 88.8% | V4-Pro leads |
| HLE | 37.7% | 40.0% | Opus leads |
| HMMT 2026 Math | 95.2% | 96.2% | Opus leads slightly |
| MMLU-Pro | 87.5% | - | Strong |
| GSM8K | 92.6% | - | Strong |
| MRCR 1M (retrieval) | 83.5 | 92.9 | **Opus leads significantly** |
| CorpusQA 1M | 62.0 | 71.7 | **Opus leads significantly** |
| BigCodeBench Pass@1 | 63.9 | - | 3-shot |
| LongBench-V2 | 51.5 | - | 1-shot, leads open models |

### NIST CAISI Independent Assessment (May 2026)
- CAISI evaluated DeepSeek V4 Pro across 5 domains (cyber, software engineering, natural sciences, abstract reasoning, mathematics) using 9 benchmarks including 2 held-out uncontaminated sets.
- **Finding:** Capabilities lag behind the US frontier by approximately 8 months (comparable to GPT-5, released August 2025).
- **ARC-AGI-2 semi-private:** "meaningfully behind" the US frontier.
- **CTF-Archive-Diamond:** Worse performance on held-out agentic/reasoning evaluations.
- DeepSeek's self-reported benchmarks suggested closer parity than CAISI's independent tests showed.

---

## 2. Infrastructure: How We Serve It

### Service Declarations (SERVICES.toml)

**Primary: `h200x8-deepseek-v4-pro`** (lines 47-57)
```toml
backend = "vllm_thinking"
base_url = "https://w80putgan2qou8-8000.proxy.runpod.net/v1"
model = "deepseek-v4-pro"
max_context_window = 393216
chars_per_token = 4.0
token_multiplier = 1.5
thinking_capable = true
tools_capable = true
stream = true
```

**Alliance Pod: `alliance-pod`** (lines 64-74)
```toml
backend = "vllm_thinking"
base_url = "https://sgjy18glyi4blu-8000.proxy.runpod.net/v1"
api_key = "$ALLIANCE_POD_KEY"
model = "deepseek-v4-pro"
max_context_window = 393216
# Same config as h200x8. Billed per hour, not per token.
```

### Backend: VllmThinkingBackend

File: `packages/pipeline/src/pipeline/model_backends.py` (lines 223-414)

Active workarounds (from MODELS.md workaround inventory):
1. **BPE cleanup** (lines 77-90): Translates U+0120 -> space, U+010A -> newline. Root cause: HF Transformers v5 regression #45920. Retire when: HF fix ships.
2. **`<think>` block stripping** (lines 93-101): Regex removes `<think>...</think>`. Retire when: vLLM unified parser #32713 ships.
3. **Schema-in-prompt** (lines 125-132): Appends JSON schema to system prompt. Retire when: vLLM unified parser OR pydantic-ai VLLMProvider #3515.
4. **Raw JSON extraction + retry** (lines 104-122, 360-410): Extracts JSON object from free text, retries on parse failure. Max 2 attempts. On `finish_reason == "length"`, grows `max_tokens` by 1.5x.
5. **Streaming accumulation** (lines 306-328): Accumulates streamed chunks, extracts finish_reason from terminal chunk.

Sampling pins (from MODELS.md):
- `temperature = 0.0` (greedy)
- `top_p = 1.0`
- `seed = 0`
- `max_tokens` per-call (default 16384)
- `parallel_tool_calls = False`

Tool-calling path (lines 416-479): Uses pydantic-ai Agent with OpenAI-compatible tool calling API. The `tools_capable = true` flag enables this path.

---

## 3. Consumer Contract: whisker tapetum_llm Advisory Lane

File: `packages/whisker/src/whisker/tapetum_llm/` (7 modules)

### What It Does
An opt-in advisory LLM layer that gives a second opinion on tomd conversion fidelity. **Never gates.** Never hard-fails. Never overwrites the whisker verdict on record.

### Seven Fidelity Axes
Defined in `models.py` line 30-38:
```python
FidelityAxis = Literal[
    "wording", "code", "stable_names", "tables",
    "xrefs", "math", "structure",
]
```

### Cascade Architecture
1. **Select** (pure Python): identifies candidate papers (pass-tier with risk signals, non-benign review, heading-only fails).
2. **Triage** (fast slot): one LLM call per paper (or per H2-chunk for oversized papers). Produces `Adjudication` with per-axis findings, overall verdict, confidence, evidence spans.
3. **Adjudicate** (deep slot): escalates only when tier1 confidence is in the ambiguous band [0.35, 0.65].
4. **Decide** (pure Python): grounds evidence spans verbatim against markdown, applies severity-aware worst-axis verdict, demotes on ungrounded evidence or sub-floor confidence.

### Output Schema: Adjudication (models.py lines 72-86)
7 fields total (>= 5, the stability floor from MODELS.md):
- `reasoning` (str, first so model deliberates before committing)
- `axis_findings` (list[AxisFinding])
- `worst_axis` (FidelityAxis)
- `verdict` (Verdict)
- `confidence` (float, [0, 1])
- `evidence_spans` (list[EvidenceSpan])
- `primary_concern` (str)

### Critical Constants (constants.py)
- `CONFIDENCE_AMBIGUOUS_LO = 0.35` (escalation threshold low)
- `CONFIDENCE_AMBIGUOUS_HI = 0.65` (escalation threshold high)
- `CONFIDENCE_DECISION_FLOOR = 0.50` (below -> forced review)
- `MAX_PAPER_MD_CHARS = 500,000` (H2-split threshold)
- `EVIDENCE_FUZZY_FLOOR = 0.90` (grounding threshold)

### Consumer Dependencies on the Model
The tapetum_llm lane depends on the model being able to:
1. **Parse and understand markdown structure** (headings, tables, code blocks, math, xrefs).
2. **Produce valid JSON matching the Adjudication schema** (7 fields, nested objects).
3. **Provide verbatim quotes from the input** (evidence grounding checks exact substring match).
4. **Reason about conversion fidelity** (compare what the markdown says vs what a correct conversion should say).
5. **Calibrate confidence** (the cascade's escalation logic relies on well-calibrated [0,1] confidence scores).

---

## 4. CLAUDE.md Invariants Under Scrutiny

Source: root `CLAUDE.md` (project-wide rules)

### Model Sovereignty
> "The analytical pipelines must run on open-weight models under our control."

DeepSeek-V4-Pro is open-weight (MIT license), self-hosted on RunPod. **Compliant.**

### Determinism (D1-D11)
- **D1:** All LLM calls through `run_agent`/`run_task`. tapetum_llm uses `run_agent` via `dispatch`. **Compliant.**
- **D4:** `parallel_tool_calls=False`. Set in VllmThinkingBackend tool path. **Compliant.**
- **D5:** No per-call temperature/seed override. Pins are in the backend. **Compliant.**
- **D6:** `output_type=Adjudication` (Pydantic model). **Compliant.**
- **D7:** Sort unordered collections before prompts. `TapetumResult.to_dict()` sorts axis_findings and grounded_evidence. **Compliant.**
- **D11:** Serial execution (one in-flight request at a time). tapetum_llm triages chunks serially. **Compliant.**

**Risk area for determinism:** MoE routing under concurrent load (from MODELS.md). The semaphore serialization mitigates this, but the model's internal expert selection may still vary with batch composition at the vLLM layer if other users share the pod.

### Fidelity
> "If full fidelity cannot be achieved, stop. Fail the paper with a clear error message."

tapetum_llm is advisory-only, so fidelity constraints apply differently: a partial result is demoted to "review" (never becomes a clean pass). `state.partial` flag enforces this.

### Structured Output (D6/D10)
Schema-in-prompt strategy for VllmThinkingBackend means the model is NOT constrained-decoded. It produces free text and the backend extracts JSON. This is less reliable than constrained decoding.

### Prompt-Injection Defense
`ctx.inject_untrusted(md)` wraps paper markdown with randomized delimiters. Framework floor tells the model to treat delimited content as data.

---

## 5. Known Issues from External Sources

### 5.1 Hallucination Rate
- Artificial Analysis AA-Omniscience: **94% hallucination rate** (V4-Flash: 96%). Not because the model is ignorant, but because it almost never abstains. GLM-5 posts dramatically better numbers via a trained refusal mechanism. (Source: jacksunwei.me/digest/ai-research/deepseek-v4-ascend-pivot-cheaper-shakier/)
- **Impact on tapetum_llm:** The model may invent evidence quotes that look plausible but are not verbatim substrings. The grounding step (`ground_spans`) catches these by requiring exact substring match, but a high ungrounded-drop rate wastes the call.

### 5.2 Long-Context Degradation
- MRCR 8-needle: 0.82 at 256K, **0.59 at 1M**. Failures distributed randomly across positions (Lightning Indexer misses compressed blocks). (Source: Skywork stress tests via jacksunwei.me)
- Opus 4.6 MRCR 1M: 92.9 vs V4-Pro 83.5.
- **Impact:** Papers approaching the 393K configured window may see random retrieval failures. The H2-chunking at 500K chars mitigates by keeping individual calls under the degradation cliff, but within-chunk misses are possible.

### 5.3 Structured Output / Tool Calling
- V4 rejects `tool_choice="required"` in thinking mode (GitHub deepseek-ai/DeepSeek-V3#1376). **40% fallback rate** to free text in real-world agent runs.
- vLLM structured output bug when thinking enabled: JSON ends up in the `reasoning` field instead of `content` (vllm-project/vllm#41132, fixed in PR #41199).
- DSML tool parser mishandles wrapped/reserved arguments (vllm-project/vllm#41240, fixed in #41801).
- **Impact on tapetum_llm:** The schema-in-prompt path avoids tool_choice entirely, but relies on the model voluntarily producing valid JSON. The 2-attempt retry with max_tokens growth covers truncation but not structural refusal.

### 5.4 Thinking Mode Language Drift
- `reasoning_content` does not respect language instructions. Thinking block defaults to English regardless of system prompt (GitHub deepseek-ai/DeepSeek-V3#1257).
- **Impact:** For our English-language pipeline, this is a non-issue (desirable behavior). But it confirms the thinking block is not fully controllable.

### 5.5 Non-Streaming Latency
- Non-streaming calls with thinking enabled: time-to-first-byte = full reasoning time (~28-32s for a 2K-token payload) (GitHub deepseek-ai/DeepSeek-V3#1464).
- **Impact:** tapetum_llm uses `stream = true`, mitigating this. But any future non-streaming path would hit this wall.

### 5.6 Text-Only Limitation
- No native image, audio, or video input. Text-only across all variants.
- **Impact on tapetum_llm:** The lane feeds markdown text only. Image extraction quality is tomd's responsibility (raster extraction, vector image detection); the model never sees pixel data. Alt text from `![alt](path)` is the only image information available to the model. This is a structural blind spot: the model cannot verify that an extracted figure matches the original PDF figure.

### 5.7 English Proficiency
- Training data: 33T tokens, multilingual. DeepSeek is a Chinese company; historical models showed Chinese-first optimization.
- V4 thinking block defaults to English (issue #1257 confirms English is the primary reasoning language).
- MMLU-Pro 87.5% (strong English academic benchmarks).
- MGSM multilingual math: 84.4 (competitive).
- **Assessment:** English proficiency is strong for V4-Pro. The model was explicitly trained for agentic English-language tasks. Chinese bias is more a concern for thinking-block language control than for English output quality.

### 5.8 Torch.compile Correctness
- `torch.compile(fullgraph=True)` on V4-Pro: max_abs_diff = 1.07 (4 orders of magnitude above 1e-4 tolerance). Graph breaks = 0, performance 3.58x speedup, but numerical correctness fails. (Source: penguinwu/oss-model-graph-break-corpus)
- **Impact:** Relevant only if our vLLM deployment uses torch.compile for inference optimization. Current SERVICES.toml does not specify compilation flags.

---

## 6. Comparison Anchors in Our Codebase

| Our component | Overlap with model capability | Risk |
|---|---|---|
| `model_backends.py:VllmThinkingBackend` | Entire structured output strategy | Schema-in-prompt reliability |
| `tapetum_llm/models.py:Adjudication` | 7-field nested schema | JSON compliance at scale |
| `tapetum_llm/grounding.py:ground_spans` | Evidence verbatim matching | Hallucinated quotes |
| `tapetum_llm/constants.py` confidence bands | Calibration of [0.35, 0.65] | Model confidence calibration |
| `tapetum_llm/chunking.py` H2 split | Long-context handling | Within-chunk retrieval failures |
| Root CLAUDE.md D1-D11 | Determinism pins | MoE batch-routing variance |
| Root CLAUDE.md fidelity | Fail-not-partial | Advisory lane's review demotion |
| MODELS.md BPE workarounds | Tokenizer artifacts | V4 uses different tokenizer than V3 |

---

## 7. Persona Selection

### Generic Core (16 personas)
| NN | Persona | Failure Class |
|---|---|---|
| 01 | Benchmark-Hunter | Published eval numbers misrepresented or cherry-picked |
| 02 | Community-Feedback-Miner | Recurring real-world failure reports missed |
| 03 | English-Training-Auditor | Training corpus English/Chinese imbalance affecting output quality |
| 04 | Table-Understanding | Failure to parse, verify, or reason about markdown tables |
| 05 | Code-Fidelity | Failure to recognize, preserve, or judge code block integrity |
| 06 | Heading-Structure | Failure to understand heading hierarchy and document structure |
| 07 | Math-Notation | Failure to handle LaTeX, Unicode math, formulas in markdown |
| 08 | Vision-Image-Capability | Structural inability to verify image extraction fidelity |
| 09 | Long-Context-Auditor | Degradation across the 393K configured window |
| 10 | Structured-Output-Schema | JSON/schema compliance under vLLM serving |
| 11 | Tokenizer-Serving-Quirks | BPE artifacts, think-block parsing, vLLM-specific bugs |
| 12 | Hallucination-Faithfulness | Invented evidence, confident wrong answers, abstention failure |
| 13 | CLAUDE-Invariant-Auditor | Risk to D1-D11, fidelity, model sovereignty invariants |
| 14 | Tapetum-Lane-Fit | Model weaknesses mapped to the 7 fidelity axes + cascade |
| 15 | Token-Budget-Skeptic | chars_per_token=4.0 / token_multiplier=1.5 defensibility |
| 16 | Steelman | Strongest honest case FOR the model in this role |

---

## Required Persona Report Template

```
# NN - <Persona name>

**Verdict:** usable | usable-with-conditions | garbage   (+ 1 sentence why)
**Confidence:** high | medium | low

## Findings
- [CRITICAL|HIGH|MED|LOW] <claim>. Evidence: <file:line OR runtime number from 00>.
  Impact: <why it makes the target more/less trustworthy or adoptable>.
  (repeat; 3-8 findings, ranked)

## False-pass hypothesis
<one concrete case the target/our-equivalent would wrongly accept, or "none found">

## False-fail hypothesis
<one concrete case it would wrongly reject, or "none found">

## What would change my mind
<the single piece of evidence that would flip my verdict>
```
