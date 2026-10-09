# D03 — Ship MoE-only package (Option A)

**Date:** 2026-07-24  
**Status:** Open (engineering)

---

## Decision needed

Ship the MoE-only package on `alliance-pod` without waiting for dense: remeasure v11 → det-metadata (A/B) → verdict-first → router/quota → server Tier-1?

## Recommendation from research

**Yes.** This is the only shippable path under the twin ban while dense is 404. Order: P0 remeasure local v11 (~21–25 min expected) → commit v11 baseline → HTML-first det-metadata staging (~251 s) then fleet (~471 s) → verdict-first → router combo_safe + dynamic quota → Tier-1 server flags. Do **not** promise ≤10 min from this package alone.

## If yes (ship Option A)

- Central wall after full MoE AGGRESSIVE stack (no dense): **~680–910 s (~12–15 min)** realistic; MODERATE ~1366 s (~23 min).
- Unblocks honest SLA language and later A/B baselines for Option B.
- Cost: shadow A/B fleets + holdouts; shared-pod noise requires off-hours measurement.

## If no (defer MoE package)

- Stay on uncommitted v11 arithmetic; continue quoting 3003 s as baseline (confounds every later gate).
- No wall progress until dense returns; product stuck near ~48–50 min measured or ~21–25 min unrevalidated.
- Quality gate Config A stays dishonest.

## Evidence

| Claim | Source |
|-------|--------|
| v11 short-circuit −1059…−1341 s; expect ~21–25 min | `10-impl-status-1pod.md`, `ADR-017` |
| Package rollups MODERATE ~1366 s; AGGRESSIVE realistic ~715 s | `18-packages-1pod.md` |
| Det-metadata −~471 s A/B-only; HTML-first staging | `13`, `22`, handoff §6 |
| Verdict-first −124…−155 s; router −190…−310 s | `15`, `14` |
| MoE-only still misses 600 s | `17`, `SYNTHESIS.md` |
