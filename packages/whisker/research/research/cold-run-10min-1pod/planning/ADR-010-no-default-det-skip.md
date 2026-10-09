# ADR-010: No default `--det-skip` (advisory opt-in only)

## Status

**Accepted** — do not make strong-deterministic skip the default cold path. Optional advisory speed tier only, with explicit audit marking.

## Context

No shipped mode skips all in-paper LLM calls when whisker deterministic signals are strong/pass. Closest behaviors today:

| Mechanism | LLM left | Cold after `_LANE_VERSION` bump? |
|-----------|---------:|----------------------------------|
| v11 metadata short-circuit | ≥2 calls/paper | Yes |
| Empty router `risk_signals` | skips units only | Yes |
| Incremental fingerprint (C2) | 0 on match | **No** (warm only) |
| `--fuse-only` | 0 | Needs prior sidecars |
| Hypothetical `--det-skip` | 0 on clean-pass cohort | Yes |

A clean-pass det-skip tier is architecturally safe for the **gate** (tapetum never gates; fusion → `whisker_only`), but weak for the **advisory** lane: selection-gap coverage and ~16/381-class merged flips disappear on skipped PIDs. Modeled wall save is ~250–350 s at S=16 (~100–140 clean-pass papers × 2 remaining calls), not additive with the metadata-fail short-circuit cohort, and still hundreds of seconds short of ≤600 s alone.

`--review-all` is the inverse filter (skip clean passes by candidate selection), not a det-skip implementation. Fingerprint skip is useless on cold after a lane bump.

## Decision

1. **Do not** enable `--det-skip` (or equivalent "strong det → zero LLM") as the default cold-fleet path.
2. If implemented, ship only as an **explicit opt-in** advisory speed tier (e.g. `--det-skip` / `--profile nightly`) with sidecar `coverage_mode: det_skip` for audit.
3. Prefer higher-yield partial cuts already in the package stack: v11 metadata short-circuit (landed), deterministic metadata diff (A/B), unit zero-defect predictor, dense offload.
4. Never treat det-skip as a bankable ≤10 min lever in central wall arithmetic.

## Consequences

**Positive**

- Keeps default advisory coverage on the selection-gap / semantic-corruption cohort that order-blind det can miss.
- Avoids shipping a "green wall / empty advisory" false-pass posture on clean-pass papers.
- Forces planning effort onto levers that preserve second-opinion value.

**Negative / cost**

- Forgoes ~250–350 s on cold after lane bump if an opt-in tier is never used.
- Nightly/det-primary operators must opt in deliberately; no silent default speedup.

**Invariants**

- Gate/CI safety of det-skip does not license default use; advisory value is the bar for the default lane.
- Fusion `whisker_only` on absent tapetum remains correct; that is not permission to skip by default.

## Evidence

| Claim | Source |
|-------|--------|
| `--det-skip` as default = **No**; advisory opt-in; ~250–350 s | `SYNTHESIS.md` reject ledger |
| No mode skips all LLM on strong det; partial skips only | `24-det-skip-llm.md` |
| Gate-safe / advisory-conditional; insufficient alone for 600 s | `24-det-skip-llm.md` |
| Fingerprint 0 s on cold after lane bump | `24-det-skip-llm.md`, `25-call-class-fingerprint.md` |
| Reject ledger + handoff checklist item 9 | `PLANNING-HANDOFF.md` |
