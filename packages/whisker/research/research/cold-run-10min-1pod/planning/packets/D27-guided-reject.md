# D27 — Reject server guided_grammar

**Date:** 2026-07-24  
**Status:** Accepted (reject)

---

## Decision needed

Migrate tapetum judges to server `guided_grammar` / speculative `guided_json` for speed or “guaranteed JSON”?

## Recommendation from research

**No.** Stay on schema-in-prompt + extract + finite `output_retries` / `ModelRetry` (`VllmThinkingBackend`). Guided decoding is the slow trap under reasoning (SqueezeBits batch≥8; vLLM #12122 ~0.1 tok/s class; MTP×grammar `</think>` misses). Prefer Non-think + verdict-first + client validators.

## If yes

- Throughput cliffs at S=16 / c=32 decode-bound fleet.
- Trades retry fidelity for grammar masks that historically break with DeepSeek reasoning.

## If no

- Keep D6/D10 compliance strategy; accept soft schema (retries), not bit-guaranteed grammar.
- Aligns with ADR-019 keep-schema-in-prompt.

## Evidence

| Claim | Source |
|-------|--------|
| Guided = No; stay schema-in-prompt | ADR-012, `05i-web-community-workarounds.md` |
| Reject ledger | `SYNTHESIS.md`, `PLANNING-HANDOFF.md` §8 |
| Stack already schema-in-prompt | `MODELS.md`, ADR-019 |
