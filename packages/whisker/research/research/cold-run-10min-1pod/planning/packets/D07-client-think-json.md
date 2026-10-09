# D07 — Client Non-think / JSON kwargs

**Date:** 2026-07-24  
**Status:** Open (engineering)

---

## Decision needed

Probe and lock Non-think kwargs on unit checks (and only after A/B), and enforce client invariants for think + JSON?

## Recommendation from research

**Yes.** Re-probe `alliance-pod` (may already be Non-think). For unit checks after A/B: `chat_template_kwargs.thinking=false` / `enable_thinking=false` / hosted `thinking: {type: "disabled"}` / `reasoning_effort="none"`. **Never** `reasoning_effort="low"` (maps to High on DSV4). **Never** `thinking.enabled` with `json_object`; **never** `thinking.disabled` + `reasoning_effort` together (400). Do not enable thinking to “fix” schema. Stay schema-in-prompt; no server `guided_grammar`.

## If yes (probe + lock invariants)

- Cuts think-on wall dominance on unit lane; think on/off often beats Flash decode theory.
- Avoids 400s and silent High-effort traps.
- Needs unit-lane A/B so Non-think does not raise false-clears.

## If no (leave think defaults / misuse knobs)

- Risk paying full reasoning tokens on short JSON units.
- API 400s or High-effort mapping under “low”.
- Guided JSON path is the slow trap if someone “fixes” schema server-side.

## Evidence

| Claim | Source |
|-------|--------|
| Official think-off → vLLM kwargs | `05q`, `05-web-think-off-official.md` |
| Non-think quality cliffs; unit-only after A/B | `05a` |
| `reasoning_effort="low"` → High on DSV4 | `05c` |
| Hosted/CN invariants (json_object / disabled+effort) | `05y` |
| guided_grammar slow trap | `05i`, `NON-GOALS.md` |
