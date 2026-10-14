# 05i - Web: Guided Decoding / Structured Output Cost on vLLM

**Verdict:** usable-with-conditions — modern XGrammar/llguidance make **repeated, simple JSON schemas** nearly free on decode tok/s when the engine overlaps mask work with GPU; schema enforcement hurts **badly** when (1) schemas are unique/complex every request, (2) batch concurrency is high without mask overlap (classic vLLM V0 / non-overlapped mask path), (3) generations are **short** so compile+mask fixed cost dominates wall, or (4) the request falls back to **Outlines**. Our MoE judge path today is mostly **schema-in-prompt** (`VllmThinkingBackend`), so this tax is latent until we turn on server `response_format` / guided JSON.

**Confidence:** high on mechanisms and when-hurts conditions; medium on exact %-of-baseline for alliance-pod (no local A/B with our UnitCheck schema).

**Date:** 2026-07-24. Sources: vLLM structured-decoding blog (2025-01-14), Red Hat Developer structured outputs (2025-06-03), SqueezeBits XGrammar vs LLGuidance on vLLM/SGLang (2025-09-16), XGrammar MLSys paper, dreaming.press Outlines vs XGrammar vs llguidance (2026-06-22), vLLM forum structured-output backend Q&A, Friendli structured-output + speculative note, `MODELS.md`, `packages/pipeline/src/pipeline/model_backends.py`, prior tapetum levers (`SYNTHESIS.md` verdict-first / pass-path).

---

## Findings

- [CRITICAL] **Hurt regime #1 — unique / complex schemas (cache miss + context-dependent mask work).** XGrammar wins on **repetitive** simple schemas via precompute + grammar cache; on unique schemas (JSONSchemaBench Github_easy/medium), **LLGuidance beats XGrammar** on throughput/TPOT, and XGrammar on vLLM shows **erratic throughput stalls** from CPU mask generation for new complex schemas (SqueezeBits Fig 5–7, Qwen3-8B/32B, vLLM 0.10). Impact: if every judge call embeds a different expanded JSON Schema (or `auto` falls back often), decode tok/s collapses even with XGrammar. Our fleet reuses a small set of Pydantic models → **cache-friendly if server-side guidance is enabled**.

- [CRITICAL] **Hurt regime #2 — engine integration / batch: non-overlapped mask on the critical path.** Outlines-era vLLM: FSM compile + sync logit masking **blocks the whole batch** → high TTFT, lower throughput; XGrammar cut TPOT under load by up to **~5×** vs that path (vLLM blog). SqueezeBits: even with XGrammar/LLGuidance, **vLLM drops vs unconstrained baseline especially at concurrency ≥8** because mask generation is sequential/non-overlapped; **SGLang** overlaps mask with GPU and stays near baseline. V0: one constrained request could degrade the engine; V1: init non-blocking, TPOT only marginally higher when schemas are cached (Red Hat). Impact: alliance-pod at `--max-num-seqs 16` is exactly where a bad guided-decoding path taxes **all** in-flight decode, not just structured calls.

- [HIGH] **Hurt regime #3 — short outputs: fixed cost does not amortize.** Grammar compile (esp. Outlines FSM / XGrammar precompute on cold schema) shows up in **TTFT**; per-token mask tax shows up in **TPOT**. Red Hat: XGrammar = low TPOT / long gens + reuse; Guidance/llguidance = fast TTFT / dynamic schemas. XGrammar paper: up to **100×** faster per-token grammar work and **near-zero** end-to-end when overlapped; without overlap or on complex schemas with many context-dependent tokens, mask work stays on the critical path (SqueezeBits). Impact for tapetum: unit-check pass path is **~55–77 output tokens** (`38-speculative-decoding-scout`, throughput auditors). Any per-request compile or heavy mask that costs milliseconds×batch shows as a large **fraction of call wall**, while monolith (~283 tok) amortizes better.

- [HIGH] **Hurt regime #4 — Outlines / fallback backends.** Outlines: token-level FSM, Python-heavy, CFG mode especially slow/crashy (vLLM blog). Forum summaries: XGrammar ~**2.12 req/s / ~1726 tok/s** class numbers vs Outlines **order-of-magnitude slower** TTFT/throughput in older benches; CPU↔GPU sync + list→tensor conversion dominate. vLLM `auto` falls back when XGrammar cannot express the schema (regex/`pattern`/`patternProperties`, numeric ranges historically, Literal quirks). Impact: a "fancy" Pydantic schema that trips fallback silently reintroduces the Outlines tax on MoE serving.

- [HIGH] **Our stack today often pays the prompt tax, not the mask tax.** `VllmThinkingBackend` injects `model_json_schema()` into the system prompt and parses JSON after `<think>` strip (`model_backends.py` `_schema_instruction`); it does **not** set vLLM `guided_json` / `response_format`. `Llama3Backend` / tool-capable paths use pydantic-ai with `supports_json_schema_output=True` (server constrained decoding). Impact: enabling OpenAI-compat `json_schema` on DeepSeek-V4-Pro is a **behavior + perf A/B**, not free correctness. Prior risk note: strict guided JSON on MoE can cause repetition / reject loops (langextract persona 88 / olmOCR precedent). Schema field count still matters for **determinism under constrained decoding** (`MODELS.md` unused1/unused2), orthogonal to tok/s.

- [MED] **When guidance is cheap or even helpful.** Cached JSON schemas on vLLM V1: TPOT only **marginally** above unconstrained (Red Hat). XGrammar claims near-zero overhead with engine co-design. Friendli: `response_format` up to **+21%** throughput with speculative decoding (acceptance↑); gain collapses to ~**+3%** with speculation off — so guidance can **help** long structured gens when draft acceptance rises, not a universal tax. Impact: keep full schemas on long, reused, nested outputs (monolith defects, tool calls); do not fear XGrammar on those paths if V1 + cache + no Outlines fallback.

- [MED] **pydantic-ai / MoE practical mapping.** pydantic-ai `output_type=<PydanticModel>` becomes either (a) schema-in-prompt + client validate/retry (current `vllm_thinking`), or (b) provider `response_format` / guided JSON when the model profile advertises JSON-schema output. For (b) on vLLM: prefer **stable, small, reused** schemas; avoid per-call schema mutation; pin `guided_decoding_backend` / structured backend if `auto` flaps to Outlines; watch MoE batch composition (D11 serial for dissect; tapetum already fans out — guided mask CPU contention stacks with MoE routing variance).

---

## When schema enforcement hurts decode tok/s badly (checklist)

| Condition | Why tok/s dies | Severity |
|-----------|----------------|----------|
| Unique schema every request | XGrammar cache miss + precompute; CPU stalls (SqueezeBits medium) | Critical |
| Complex schema, many context-dependent tokens | Per-step mask not precomputable | High |
| Concurrency ≥ ~8 on vLLM without mask overlap | Mask serializes decode for the batch | Critical |
| Outlines / unsupported-schema fallback | FSM + sync logit path | Critical |
| Very short OSL (tens of tokens) | Compile/TTFT fraction >> decode | High |
| Regex / `pattern*` / exotic JSON Schema keywords | Forces fallback or slow path | High |
| Mixed batch: few guided + many free | V0-style: one guided request poisons batch (mitigated in V1) | Med (V0) / Low (V1) |

| Condition | Why mostly fine | Severity if violated |
|-----------|-----------------|----------------------|
| Same simple JSON schema, cached | XGrammar near baseline TPOT | — |
| Long structured generation | Amortizes compile; jump-decoding opportunity | — |
| SGLang-style mask/GPU overlap | Hides CPU grammar work | — |
| Speculative decoding + tight schema | Higher draft accept (Friendli) | — |

---

## Pass-path tips: keep / slim / drop guidance

Target: short unit-check **pass** responses (~55 tok of JSON nobody needs reasoning for; 70% zero-defect, `00-baseline`). Aligns with prior lever "verdict-first / terse pass-path schema" (~180–360 s).

### KEEP full schema (+ server guidance if enabled)

- Fail / review paths that emit **lists of defects** with quotes, enums, nested objects: invalid JSON here is retries (~20 s) or silent parse garbage.
- Any call where pydantic validators / Literal enums are load-bearing and client retry budget is tight.
- Long outputs (monolith, multi-finding) where XGrammar TPOT tax amortizes and may help speculation.
- Reused fleet schemas already hot in the grammar cache.

### SLIM schema (preferred default for pass-path)

- **Verdict-first micro-schema** for expected pass: e.g. `{verdict, confidence}` or `{verdict, confidence, defect_count:0}` — tens of tokens, few FSM states, trivial mask.
- Drop free-text `reasoning` on pass (or make it `maxLength` / omit via separate model). Prior estimate ~55 wasted tokens × 1057 zero-defect units.
- Prefer **enums / literals / booleans** over open strings; avoid `pattern`, `minLength` gardens, and deep `$ref` graphs that trip XGrammar→Outlines fallback.
- Two-schema fork: `UnitCheckPass` vs `UnitCheckFindings` selected by a cheap prior or first-token policy — do **not** send the full findings schema when the model will emit zero findings.
- If staying on `VllmThinkingBackend`: slimming the **prompt-injected** schema still cuts output tokens and parse surface even without guided decoding.

### DROP guidance (prompt + parse only; or unconstrained + validate)

- Ultra-short classification / ternary verdicts where unconstrained compliance is already ≥90% (SqueezeBits Github_easy unconstrained ~90–94%) **and** you have fail-closed Pydantic retry (`output_retries`).
- When A/B shows guided JSON causes MoE **repetition / whitespace stall** (Friendli failure mode; olmOCR-class loops) — keep D6 client schema, turn off server `response_format`.
- When TTFT/compile dominates a <64-token pass call and server is on a non-overlapped mask path: schema-in-prompt + extract may beat guided for **wall**, at the cost of more parse retries.
- Never drop **client** validation (D6/D10). "Drop guidance" means drop **server logit masks**, not drop `output_type`.

### Decision rule (short pass-path)

```
if expected_findings == 0 and output_tokens_budget < ~64:
    use SLIM pass schema
    prefer schema-in-prompt OR cached XGrammar on slim schema
    avoid Outlines fallback (no exotic JSON Schema keywords)
elif nested findings / quotes required:
    KEEP full schema; ensure XGrammar/llguidance not Outlines
else:
    SLIM fields; KEEP structural enums
```

---

## False-pass hypothesis

Slim pass schema + dropped server guidance: model emits `verdict=pass` with truncated/omitted defect list that would have been forced present under the full schema; fusion accepts clean paper while quotes proving omission never appear. Mitigate: mechanical pre-gate + keep full schema whenever any defect signal exists; A/B verdict parity on 48-paper holdout.

## False-fail hypothesis

Strict guided JSON on DeepSeek-V4-Pro MoE forces repetition or schema-reject loops → timeout/error tombstone → review/fail inflation vs today's schema-in-prompt path. Mitigate: A/B `json_schema` vs schema-in-prompt on 50 papers (retry count, verdict drift, p95 decode tokens) before fleet enable.

## What would change my mind

A measured alliance-pod A/B: same UnitCheck payloads, `response_format=json_schema` (XGrammar) vs schema-in-prompt, at c=16, reporting output tok/s, TTFT, TPOT, parse retries, and verdict delta — if guided is within ~5% of unconstrained tok/s on pass-path **and** cuts retries without verdict drift, promote KEEP guidance on slim schemas to CONSERVATIVE; if tok/s drops >15% or retries rise, treat server guidance as **anti-lever** for short pass calls.
