# ADR-024: Reject Gemma-4 as primary unit judge

## Status

Rejected — do not use as unit primary

## Date

2026-07-24

## Context

Heterogeneous offload (ADR-003) needs a dense primary for ~1510 unit checks. `SERVICES.toml` lists `b200x2-gemma4` (`google/gemma-4-31B-it`) beside Qwen3 dense endpoints. Public structured-output reports show Gemma-4 under JSON-schema / grammar constraints entering repetition loops; prior Alliance hypothesis is false-fail on `:::wording-remove` / `<del>` wording markup (`12`, `05f`).

ADR-005 already selects `h200-qwen3-32b` as primary. This card locks the **negative** decision so Gemma is not revived as a “faster dense” shortcut when Qwen pods are down.

As of 2026-07-24, `b200x2-gemma4` also returns HTTP 404 (`26`); liveness is irrelevant to the quality reject.

## Decision

1. **Do not** assign `b200x2-gemma4` (or Gemma-4-31B generally) as the primary unit-check or metadata judge.
2. Primary remains `h200-qwen3-32b`; reserve/pilot #2 is `b300-qwen36-27b` after 32B A/B (ADR-005).
3. Reopen Gemma only if: ≥99% valid JSON on our vLLM + UnitCheck schema **and** full 381/381 fused-verdict parity vs Pro, including wording-markup holdouts.

## Consequences

**Positive**

- Avoids structured-output collapse and wording false-fails on the highest-volume call class.
- Keeps dense class label `qwen3-dense-27-32b`, not “any ~30B.”

**Negative / cost**

- One fewer dense failover candidate while Qwen pods are 404.
- `tools_capable` on Gemma is unused for UnitCheck schema; not a compensating advantage.

## Evidence

| Claim | Source |
|-------|--------|
| Avoid Gemma-4 primary; wording false-fail | `12-dense-offload-architecture.md`, `SYNTHESIS.md` |
| Rank 3 avoid; JSON/grammar collapse (Ollama #15502, gemma#622) | `05f-web-dense-judge-lit.md` |
| Primary = Qwen3-32B | ADR-005 |
| Gemma endpoint 404 today | `26-dense-pod-liveness.md` |
| Non-goal ledger | `NON-GOALS.md`, `PLANNING-HANDOFF.md` §8 |
