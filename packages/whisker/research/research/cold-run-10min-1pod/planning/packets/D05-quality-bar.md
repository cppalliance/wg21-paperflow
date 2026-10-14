# D05 — Quality bar for ship

**Date:** 2026-07-24  
**Status:** Open (engineering / product)

---

## Decision needed

Adopt the report-19 gate as the ship bar: A/A noise floor + bundled B + three tiers (fleet flip, dev-replay, holdout), with wall as a **secondary** metric (B ≤620 s to claim 10 min)?

## Recommendation from research

**Yes.** Ship bar = equivalence vector parity within `flip_AA` margin, not exact-match 0% flips. Config A = MODERATE single-pod on post-v11 (~23–25 min), never v10 3003 s. Quality pass ≠ ≤600 s proof. Dense+det-metadata must share one bundled B when claiming AGGRESSIVE wall.

## If yes (adopt 19 protocol)

- Prevents silent defect drops and dense false-clears; ~0.8–1.2 h validation wall (excludes impl time).
- Forces honest Config A baseline and matched occupancy for A/A.
- May delay “10 min” claims until instrumented B ≤620 s even if quality passes at ~715 s.

## If no (weaker / skip gates)

- Risk fusion false-clears, wording false-fails, and shipping a lane that flips outside MoE noise.
- Faster calendar ship, destroyed credibility on advisory findings.
- Violates quality-stability contract (CLAUDE.md / MODELS.md).

## Evidence

| Claim | Source |
|-------|--------|
| Three-tier gate + equivalence vector | `19-quality-gate-1pod.md` |
| flip_AA margin; not 0% exact-match | `19`, `NON-GOALS.md` |
| Config A = MODERATE ~23–25 min post-v11 | `19`, `ADR-017` |
| Quality pass ≠ ≤600 s; need B ≤620 s | `19`, handoff §10 |
| Skip monolith rejected (false-clears) | `21`, `ADR-009` |
