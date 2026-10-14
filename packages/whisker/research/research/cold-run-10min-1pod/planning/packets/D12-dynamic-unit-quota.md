# D12 — Dynamic MAX_UNIT_CHECKS quota

**Date:** 2026-07-24  
**Status:** Open (holdout-gated; bundle with D11)

---

## Decision needed

Replace fixed fleet `MAX_UNIT_CHECKS = 5` with per-paper **dynamic quota** (base 3, ceiling 7; bumps for high/critical severity, `table_presence`, routable count >8)?

## Recommendation from research

**Yes, fleet mode only, A/B with combo_safe.** Do **not** permanently ship static cap-3 as default (SIGNAL_CLASS_QUOTA can starve `table_presence`). Keep inspect / exhaustive / all-pages uncapped; overflow → `coverage_complete=false` (fail-closed).

## If yes

- Reclaims ~**132–220** unit calls (~165–275 s) by dropping zero-yield slots 4–5 on clean PDFs while preserving table/severity floors.
- Requires stratified gate: 3/381 defect-group multiset unchanged; 16/381 reviewed; 48 holdout + 9 replay.
- Persist `unit_selection.max_checks_dynamic` in sidecars.

## If no

- Keep static 5; 179/180 PDFs stay saturated; forgo the largest safe unit-N cut on MoE-only path.
- Cap-3-only experiment remains optional for bump tuning, not the ship default.

## Evidence

| Claim | Source |
|-------|--------|
| Dynamic policy Design A; base 3 / ceiling 7 | ADR-008, `14-router-quota-1pod.md` |
| 179/180 PDFs saturate cap 5; static 3 risks quota starve | `58-max-unit-checks-knob.md` via `14` |
| Combined with combo_safe −190 to −310 s | `SYNTHESIS.md` lever #4 |
