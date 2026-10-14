# 13 - CLAUDE-Invariant-Auditor

**Verdict:** usable-with-conditions — DeepSeek-V4-Pro meets model sovereignty and framework routing invariants on a dedicated self-hosted pod, but MoE routing variance, schema-in-prompt (non-constrained) structured output, and thinking-mode behavior create AT-RISK exposure on determinism, D6/D10, fidelity, and prompt-injection defense.
**Confidence:** medium

## Invariant Classification Matrix

| Invariant | Status | One-line rationale |
|---|---|---|
| **Model sovereignty** | **COMPLIANT** | MIT open-weight, self-hosted on RunPod. |
| **D1** (`run_agent`/`run_task`) | **COMPLIANT** | Model consumed only via `VllmThinkingBackend`; no direct API bypass required. |
| **D2** (sampling pins in backend) | **AT-RISK** | Pins sent (`temperature=0`, `seed=0`; `model_backends.py:310-312`), but vLLM lacks documented batch-invariant kernels; FP4+FP8 MoE adds tie-break flips. |
| **D3** (semaphore fan-out) | **COMPLIANT** | Framework defaults `Semaphore(1)`. |
| **D4** (`parallel_tool_calls=False`) | **COMPLIANT** | Enforced in backend; V4 also rejects `tool_choice="required"` in thinking mode. |
| **D5** (no per-call temp/seed override) | **COMPLIANT** | Backend owns pins; pipelines do not override per call. |
| **D6** (`output_type=PydanticModel`) | **AT-RISK** | Hooks declare Pydantic types, but V4 path is schema-in-prompt + brace-match JSON extract, not constrained decoding; ~40% free-text fallback in thinking tool runs. |
| **D7** (sort collections before prompts) | **COMPLIANT** | Caller/framework responsibility; tapetum sorts findings. |
| **D8** (see `MODELS.md`) | **AT-RISK** | 1.6T/49B-active MoE: batch composition affects expert routing; Qwen `unused1`/`unused2` stability trick does not apply to schema-in-prompt path. |
| **D9** (`UsageLimits` on `agent.run`) | **COMPLIANT** | Tool path passes `UsageLimits(request_limit=...)` to `agent.run`. |
| **D10** (`output_retries` + `ModelRetry`) | **AT-RISK** | Raw JSON path uses max 2 parse retries, not pydantic-ai `output_retries`/`ModelRetry`; structural refusal or semantic validator failure may exhaust budget. |
| **D11** (serial, one in-flight) | **AT-RISK** | Client semaphores satisfy D11; shared RunPod vLLM batching with foreign traffic reintroduces MoE routing variance. |
| **Fidelity** (dissect/agora) | **AT-RISK** | Pipeline fails on unreachable/invalid output, but V4's 94% "answer anyway" rate produces schema-valid wrong citations/evidence. |
| **Determinism** (overall bar) | **AT-RISK** | Greedy + serial client mitigates most variance; MoE + quantized matmul + possible shared pod prevent semantic-stability guarantee. |
| **Prompt-injection defense** | **AT-RISK** | `inject_untrusted`/`wrap_source` protect delimiters; thinking block processes untrusted text with limited instruction adherence. |
| **Structured output** (D6/D10) | **AT-RISK** | 7-field nested `Adjudication` relies on voluntary JSON; JSON-in-`reasoning` vLLM bug (fixed #41199) shows thinking/content split is fragile. |

## Findings

- [CRITICAL] **D6/D10 structured output is prompt-enforced, not decode-enforced.** `VllmThinkingBackend` appends JSON schema to the system prompt and extracts `{...}` from free text (`model_backends.py:125-132, 361-364`). DeepSeek API docs: JSON mode "designed to return valid JSON, not guaranteed"; ~40% fallback to free text in thinking agent runs.
  Impact: Valid Pydantic instances can be produced unreliably; dissect/agora steps fail loudly on parse exhaustion, but tapetum burns calls on demoted ungrounded evidence.

- [CRITICAL] **Fidelity invariant is structurally satisfied but semantically AT-RISK.** CLAUDE.md requires fail-not-partial for dissect/agora. Framework raises on invalid output. V4-Pro posts 94% hallucination rate on AA-Omniscience when uncertain, almost never abstaining.
  Impact: A complete-looking structured verdict with invented citations passes D6 validation and violates fidelity intent until downstream verification catches it.

- [HIGH] **D11 + D8: MoE determinism depends on pod isolation, not just client semaphores.** V4-Pro: 49B active of 1.6T MoE. Serial semaphores remove cross-request interference only when vLLM serves one client stream. `alliance-pod` is a separate instance but still a shared hourly pod.
  Impact: Re-running the same paper can flip expert routes and decision-boundary tokens if foreign batch traffic shares the vLLM scheduler.

- [HIGH] **D2/D8: Sampling pins are necessary but insufficient on vLLM MoE.** Backend sends `temperature=0.0`, `top_p=1.0`, `seed=0`. `MODELS.md` notes hosted vLLM flips tokens without batch-invariant kernels; V4 uses FP4+FP8 mixed precision. `torch.compile` on V4-Pro fails numerical correctness tolerance.
  Impact: Semantic-stability bar is aspirational, not guaranteed, even with D2/D5 compliance.

- [HIGH] **Prompt-injection: thinking mode adds a non-wrapped reasoning channel.** `inject_untrusted` escapes forged delimiters; framework floor treats delimited content as data. Thinking block defaults to English, does not fully respect language/system constraints. vLLM bug placed JSON in `reasoning` field when thinking enabled (#41132, fixed #41199).
  Impact: Extended reasoning over paper-controlled markdown may internalize injected instructions before JSON commit; delimiter defense does not constrain the thinking trace.

- [MED] **D10 gap on the primary V4 serving path.** CLAUDE.md requires `output_retries=N` paired with `ModelRetry` in validators. `VllmThinkingBackend` raw path: 2 JSON parse attempts with truncation growth, not pydantic-ai `output_retries`. No `ModelRetry` usage found in dissect package.
  Impact: Semantic self-correction has a thinner retry corridor than D10 specifies.

- [MED] **D4 tool path is declared but fragile on V4 thinking.** `alliance-pod` sets `tools_capable = true`. V4 rejects `tool_choice="required"` in thinking mode; DSML parser bugs reported.
  Impact: Any dissect/agora step routed to tool-capable V4 with thinking enabled risks D4-compliant but functionally broken tool loops.

- [LOW] **Model sovereignty: COMPLIANT with deployment discipline.** MIT license, weights under our control, RunPod self-host. No cloud-provider deprioritization or content filtering layer.

## False-pass hypothesis

Dissect Step N returns a valid Pydantic `CitationVerdict` with `status=verified` and a fabricated quote that is syntactically plausible WG21 prose but not a substring of `paper.md`. D6 passes (valid schema). Fidelity fails silently until a later verification step catches it, or never if that step trusts the structured field.

## False-fail hypothesis

Same paper, two runs on a shared pod under different batch load: Run 1 returns `verdict=objection` with 8 claims; Run 2 returns `verdict=objection` with 7 claims (MoE routing flip at a list-boundary token). Both are "correct" objections but fail the semantic-stability bar, causing spurious diff in trace/debug and eroding reproducibility claims.

## What would change my mind

A 30-day production log from exclusive-pod `h200x8-deepseek-v4-pro` (not `alliance-pod`) showing: (1) >=99% first-attempt JSON schema validation on all dissect/agora Pydantic models, (2) <=2% run-to-run verdict flips on 20 fixed papers re-run daily with serial semaphores, and (3) prompt-injection canary papers (forged delimiter instructions in body) never altering structured verdict fields across 100 trials.
