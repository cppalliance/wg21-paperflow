# D13 — Non-think probe (unit checks)

**Date:** 2026-07-24  
**Status:** Open (probe + holdout before ship)

---

## Decision needed

Probe `alliance-pod` / client path for Non-think on schema-bound unit checks, then A/B Pro Non-think vs Think High before any fleet force?

## Recommendation from research

**Yes: probe first, then holdout A/B; no blanket force.** Prefer `extra_body={"chat_template_kwargs": {"thinking": False}}` (or `enable_thinking=false` / `reasoning_effort="none"`). Never send hosted `{"thinking":{"type":"disabled"}}`. Never `reasoning_effort="low"` (maps to High). Keep Think High on escalate / hard slices.

## If yes

- Confirms whether pod already Non-think; measures `L_u'` under matched occupancy (`28`).
- Order-of-magnitude decode cut when CoT dominated wall (hosted classifier ~31.8 s → ~2.7 s class).
- Avoids think+`json_object` empty-content retries.

## If no

- Leave unknown think state; risk banking L cuts that are already on or still CoT-heavy.
- Schema/JSON stalls may keep masquerading as “slow pod.”

## Evidence

| Claim | Source |
|-------|--------|
| Exact vLLM kwargs; never low→High; never think+json_object | ADR-015, `05q`, `05c`, `05y` |
| Non-think for shallow JSON judges; not blanket | `05a-web-nonthink.md` |
| Re-probe; prior probe may already be Non-think | `SYNTHESIS.md` Think-off section |
