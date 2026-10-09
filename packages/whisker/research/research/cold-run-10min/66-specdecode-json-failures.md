# 66 - Speculative decoding × grammar-constrained JSON: known failure modes

**Date:** 2026-07-24  
**Scope:** External failure modes when speculative decoding (ngram / EAGLE / MTP) coexists with grammar- or schema-constrained JSON.  
**Prior (do not rediscover):** `05d-web-mtp-specdecode.md` (MTP + structured JSON on vLLM), `MODELS.md` (our structured-output contract), `packages/pipeline/.../model_backends.py` (`VllmThinkingBackend` path).  
**Question answered at bottom:** safe with our pydantic structured outputs?

---

## Verdict (short)

| Path | Spec decode + structured JSON |
|------|-------------------------------|
| **Server grammar** (`guided_json` / `response_format=json_schema` / XGrammar) | **Not safe by default** — version-sensitive FSM bugs (esp. reasoning boundary + MTP); truncated or unconstrained JSON historically common |
| **Our `VllmThinkingBackend`** (schema-in-prompt → extract → `model_validate` → retry) | **Mostly safe for parse fidelity** — we do not arm server grammar, so most spec×grammar bugs do not apply; still exposed to truncation, thinking-strip edge cases, and wrong-but-valid JSON |
| **pydantic-ai backends with native JSON schema** (`Llama3Backend` / `Qwen3Backend` when provider honors schema) | **Conditional** — inherits server guided-decoding bugs if the provider actually enforces schema under speculation |

---

## Mechanism (why the combo is hard)

1. **Constrained decoding** masks logits so only grammar-legal next tokens remain (Outlines FSM / XGrammar / llguidance / GBNF). It guarantees syntax, not semantics ([pr1nt.dev](https://pr1nt.dev/posts/constrained-json-decoding/)).
2. **Speculative decoding** proposes a draft token sequence; the target verifies/rejects. Correctness requires grammar state to advance over **accepted** tokens, including mid-batch splits when a reasoning-end token sits inside a draft.
3. If the draft is unconstrained, illegal draft tokens are rejected → **acceptance collapses** (perf), not necessarily wrong finals — *if* the target always applies the mask ([TensorRT-LLM blog](https://nvidia.github.io/TensorRT-LLM/blogs/tech_blog/blog12_Combining_Guided_Decoding_and_Speculative_Decoding.html)). If the engine **fails to apply** the mask on the target or after a boundary, you get **silent unconstrained output**.

---

## Failure-mode catalog

### F1 — Truncated / incomplete JSON under ngram + guided

- **Symptom:** `{"a": 1` instead of `{"a": 1}`; tool-call args cut mid-string.
- **Evidence:** vLLM [#9423](https://github.com/vllm-project/vllm/issues/9423) (ngram + outlines → incomplete object; OK with speculation off); [#10442](https://github.com/vllm-project/vllm/issues/10442) (guided + ngram → ~5-token truncations; also tool args).
- **Related:** MQA scorer path produced wrong logits / truncated JSON unless `--speculative-disable-mqa-scorer` (#9423 thread).
- **Impact:** Hard parse failures; client retries help only if the second draw completes.

### F2 — Reasoning-end missed inside speculated batch → grammar never armed

- **Symptom:** After `</think>` (or equivalent), `reasoning_ended` stays false; JSON schema bitmask never fills; post-think content is free text / markdown fences / pseudo-JSON.
- **Evidence:** vLLM [#34650](https://github.com/vllm-project/vllm/issues/34650) (MTP + structured + reasoning); [#43388](https://github.com/vllm-project/vllm/issues/43388) (async scheduling + spec decode misses reasoning end for `json_object`); fix PR [#36138](https://github.com/vllm-project/vllm/pull/36138) (“grammar ignored when reasoning ended within speculated tokens”).
- **Subtle residual:** Even after detecting the boundary, tokens already sampled in the **same** speculative batch after the end token were unconstrained; can yield `` ```json `` fences or duplicated `{{` when the FSM expects `{` next (#43388 discussion).
- **Impact:** Highest severity for thinking models + server schema. Matches prior card `05d` “false-pass” hypothesis.

### F3 — Guided constraints silently ignored on speculative path

- **Symptom:** No error; unconstrained completion that may still look JSON-ish.
- **Evidence:** LMDeploy [#4559](https://github.com/InternLM/lmdeploy/pull/4559) — `GuidedDecodingManager` never reached MTP/spec path until fixed. Class of bug: feature composition without a hard failure.
- **Impact:** Validators that only check “parses as object” green-light garbage.

### F4 — Draft unconstrained → acceptance cliff (perf / thrashing)

- **Symptom:** Speculative speedup vanishes; more reject loops; sometimes worse latency than no-spec.
- **Evidence:** TensorRT-LLM: draft without grammar hurts acceptance; target-only constraint still correct if implemented. Friendli: `response_format` speeding up largely via **higher draft acceptance** when constraints narrow the corridor.
- **Impact:** Ops false-negative (“spec decode is useless”) rather than wrong JSON — unless operators raise `k` or disable CUDA graphs to chase speed.

### F5 — Local mask ≠ future-valid distribution (biased-but-valid JSON)

- **Symptom:** Schema-valid output drawn from the wrong conditional; fields systematically biased.
- **Evidence:** arXiv [2605.07698](https://arxiv.org/html/2605.07698) (future validity Φ; local mask approximates Φ≡1); arXiv [2603.03305](https://doi.org/10.48550/arxiv.2603.03305) (draft-conditioned constrained decoding; hard masks accumulate distortion).
- **Impact:** Quality / calibration, not parse errors. Relevant to semantic-stability bars, not Pydantic `ValidationError`.

### F6 — Schema engine incompleteness / hangs (independent of spec, worse under load)

- **Symptom:** Server hang, OOM, ignored `$ref` / `minItems` / `maxItems`, recursive schema crash.
- **Evidence:** XGrammar gaps tracked in vLLM [#12131](https://github.com/vllm-project/vllm/issues/12131); hangs [#14151](https://github.com/vllm-project/vllm/issues/14151); recursive crashes across Outlines/XGrammar ([pr1nt.dev](https://pr1nt.dev/posts/constrained-json-decoding/)).
- **Impact:** Spec decode amplifies pressure (more mask advances per step) but root cause is grammar backend.

### F7 — Thinking × structured conflicts (engine-level)

- **Symptom:** Empty content, leaked think tags into JSON, constraint applied to think stream or never applied to answer.
- **Evidence:** Ollama / SGLang issue clusters cited in [pr1nt.dev](https://pr1nt.dev/posts/constrained-json-decoding/); overlaps F2 on vLLM.

### F8 — Soft semantic failures (always true for constrained JSON)

- Discriminator-last schemas commit to wrong union branch ([pr1nt.dev](https://pr1nt.dev/posts/constrained-json-decoding/)).
- Whitespace stalls when prompt under-steers field names ([Friendli](https://friendli.ai/blog/structured-output)).
- Valid JSON, wrong facts — constraint cannot help.

---

## Mapping to our stack

| Component | How structured output is obtained | Spec×grammar exposure |
|-----------|-----------------------------------|------------------------|
| `VllmThinkingBackend` | Schema JSON in system prompt; strip `<think>`; extract JSON; `output_type.model_validate`; finite retry (`MODELS.md`, `model_backends.py`) | **No server grammar FSM.** Spec decode can still truncate streams or scramble think boundaries; client retry catches parse/validate fails. |
| `Llama3Backend` | pydantic-ai + `supports_json_schema_output=True` / provider parser | **Yes** if endpoint enforces guided schema under EAGLE/ngram. |
| `Qwen3Backend` | hermes + thinking toggle; unused1/unused2 field anchors | **Yes** when Fireworks/vLLM schema mode is on; Fireworks Eagle3 already accepted in `MODELS.md` for semantic-stability (not bit-exact). |
| Alliance-pod MTP (DeepSeek) | Same as `VllmThinkingBackend` for dissect/agora slots using that backend | F1–F3 **do not apply** unless we switch to `guided_json` / `json_schema` response_format. F2 still matters for **thinking strip** correctness, not grammar arming. |

---

## Safe with our pydantic structured outputs?

**Answer: Yes for the production `VllmThinkingBackend` path, with conditions. Not a free pass if we enable server-side grammar under MTP/EAGLE.**

### Why mostly safe

1. **Pydantic is the gate, not XGrammar.** D6 + backend `model_validate` rejects non-conforming payloads; `output_retries` / internal retry budgets re-ask. Spec×grammar FSM arming bugs (F2/F3) require a server grammar we currently do not send on that backend.
2. **Truncation is already a first-class failure.** `test_truncation_retry.py` and finish_reason handling exist because incomplete JSON happens without speculation too; speculation can increase rate (F1) but does not invent a new unhandled class if retries remain.
3. **Semantic bar matches `MODELS.md`.** Eagle3/MTP are documented as “semantic pretty-darn-close,” not bit-exact. F5 (biased-valid JSON) and F8 are already in-scope for A/B verdict checks, not for “did Pydantic accept it.”

### Conditions / remaining risks

| Risk | Severity on our path | Mitigation |
|------|----------------------|------------|
| Spec raises incomplete JSON rate | Med | Keep retries; alert on validate-fail rate when enabling MTP/EAGLE |
| Think tags leak into extract | Med | Existing strip; watch dual-boundary + stream quirks |
| Wrong-but-valid fields | High for fidelity, invisible to Pydantic | Fleet A/B verdict counts (same as `05d`) |
| Future switch to `guided_json` / OpenAI `json_schema` on MTP image | High | Require vLLM builds with F2 fixes (#36138 / #44993-class); A/B JSON validity; prefer k=1 |
| pydantic-ai native schema on Qwen/Llama under Eagle3 | Med | Same as server-grammar checklist; Fireworks Eagle3 already in ops bar |

### One-liner for the parent synthesis

**Pydantic structured outputs remain safe under speculative decoding on `VllmThinkingBackend` because we validate client-side and do not depend on server grammar; do not enable server-side grammar-constrained JSON under MTP/EAGLE without a patched image and validity A/B.**
