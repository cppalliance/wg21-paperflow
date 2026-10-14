# ADR-027: Reject SGLang migrate (out of scope for 10 min)

## Status

Rejected — out of scope for this corpus

## Date

2026-07-24

## Context

Alliance `alliance-pod` serves DeepSeek-V4-Pro via **vLLM** (`vllm_thinking` backend). Community lore and enthusiast stacks sometimes cite SGLang (or SGLang + kt-kernel) for tok/s wins on Flash-class or local setups (`05o`, `05i`). Migrating the production Alliance MoE endpoint (or the tapetum client stack) to SGLang is a multi-week infra program: recipe parity, thinking-block handling, structured-output path, MoE EP/DeepEP flags, and shared-tenant risk on a live hourly pod.

The 1-pod cold-run gap is dominated by **call count N** and **per-call L** under S=16, addressable by short-circuit, det-metadata, verdict-first, router, and (if live) dense offload — none of which require an engine swap. SYNTHESIS and NON-GOALS already list SGLang migrate as out of scope.

## Decision

1. **Do not** plan, ticket, or bank wall seconds for migrating `alliance-pod` or tapetum serving from vLLM to SGLang in the ≤10 min / 1-pod program.
2. Keep the existing `VllmThinkingBackend` / schema-in-prompt path; do not chase SGLang guided-decoding overlap as a cold-run project (`05i`, `05n`).
3. Reopen only under a separate infra charter with Alliance ops ownership and a dedicated A/B on V4-Pro judge shapes — not as a dependency of Option A/B tickets.

## Consequences

**Positive**

- Avoids coupling the 10-min program to an unbounded serving-stack rewrite.
- Keeps measurement comparable to the v10/v11 vLLM baselines already in corpus.

**Negative / cost**

- Forgoes any hypothetical SGLang-specific scheduling/mask wins until a later program.
- Deterministic-inference flags on SGLang remain unused (BI-class tradeoffs already rejected for speed).

## Evidence

| Claim | Source |
|-------|--------|
| Out of scope: SGLang migrate | `SYNTHESIS.md` §Out of scope, `NON-GOALS.md` |
| Stay schema-in-prompt; guided path is slow trap | `05i-web-community-workarounds.md` |
| Enthusiast SGLang lore does not size alliance-pod Pro | `05o-web-localllama.md`, `05i` |
| Reject ledger / planner hard constraints | `PLANNING-HANDOFF.md` §8 |
