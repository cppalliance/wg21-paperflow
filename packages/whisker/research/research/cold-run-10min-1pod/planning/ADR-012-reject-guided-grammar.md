# ADR-012: Reject server guided_grammar / speculative guided_json

## Status

**Accepted** — stay on schema-in-prompt + extract + retry. Do not migrate judges to server `guided_grammar` or speculative `guided_json` for speed or "guaranteed JSON."

## Context

Whisker / pipeline structured path on `alliance-pod` is already **schema-in-prompt** via `VllmThinkingBackend` (prompt schema, extract, finite retries), matching MODELS.md. Community and vLLM issue lore for DeepSeek + reasoning show server guided decoding as the slow trap:

- Guided decoding throughput drops vs baseline especially at batch ≥8 (SqueezeBits).
- `guided_grammar` with reasoning reported ~0.1 tok/s / GPU idle (vLLM #12122).
- `guided_json` historically broken with DeepSeek reasoning until later V1 fixes; MTP × reasoning × grammar can miss `</think>` so grammar never arms (#34650).
- Spec + structured/tool paths can add multi-second decode stalls at JSON close (#49002).

For a decode-bound short-JSON judge fleet at S=16 / c=32, migrating to guided paths trades retry fidelity for known throughput cliffs. Reject ledger: **No** to server `guided_grammar` / speculative `guided_json`.

## Decision

1. **Keep** schema-in-prompt + structured extract + `output_retries` / `ModelRetry` path for all tapetum judges on `alliance-pod`.
2. **Do not** enable vLLM `guided_grammar`, `guided_json`, or OpenAI-style server `json_schema` guided decoding as a speed or correctness "fix."
3. Treat any proposal to arm guided decoding under MTP/reasoning as a **regression risk**, not an optimization.
4. Prefer Non-think on mechanical judges, verdict-first schema shrink, and client retry budgets for JSON validity (quality-gated).

## Consequences

**Positive**

- Avoids documented 0.1 tok/s / batch≥8 guided cliffs under reasoning.
- Preserves fail-closed retry behavior already wired in the backend.
- Aligns with community "fast + correct-enough" workaround ranking (`05i` rank 4).

**Negative / cost**

- Schema compliance remains prompt+retry soft; not bit-guaranteed by a grammar mask.
- Operators seeking "guaranteed JSON" must be redirected to retry/validator design, not guided_grammar.

**Invariants**

- D6/D10: `output_type` + finite retries stay the compliance strategy.
- Guided decoding is out of scope for the cold-run speed path (same reject class as BI mode and P/D).

## Evidence

| Claim | Source |
|-------|--------|
| Server guided_grammar / speculative guided_json = **No**; stay schema-in-prompt | `SYNTHESIS.md` reject ledger |
| Community: guided is slow trap; keep schema-in-prompt | `05i-web-community-workarounds.md` |
| SqueezeBits / #12122 / #16182 / #34650 / #49002 | `05i-web-community-workarounds.md` |
| Stack already schema-in-prompt (`VllmThinkingBackend`) | `05i-web-community-workarounds.md`, `MODELS.md` |
| Handoff reject ledger includes server guided_grammar | `PLANNING-HANDOFF.md` |
