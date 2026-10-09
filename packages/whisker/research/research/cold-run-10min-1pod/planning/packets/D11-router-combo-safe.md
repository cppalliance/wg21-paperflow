# D11 — Router combo_safe tightening

**Date:** 2026-07-24  
**Status:** Open (holdout-gated; bundle with D12)

---

## Decision needed

Ship Tier-2 **combo_safe** router tightening (one `table_presence` per paper; drop noisy PDF `heading_drift`; `SECTION_RECALL_FLOOR` 0.90→0.85) as part of the MoE package?

## Recommendation from research

**Yes, holdout-gated, bundled with dynamic quota (D12).** Tier-1 empty-packet `heading_drift` hygiene may ship immediately (zero LLM risk). Do not ship combo_safe alone on wall claims without the 3/381 + 16/381 gates.

## If yes

- Trims ~**63** post-v11-scaled unit calls (~**79 s** @ S=16); combined with D12 central **~150–250** calls / **~190–310 s**.
- Acceptable trade only if **6/47** defect-group FN stay inspect-only (merged unchanged) and holdout recall holds.
- Persist selection diagnostics; bump `_LANE_VERSION`.

## If no

- Leave residual router waste on clean saturated PDFs; forgo ~79 s class.
- Still may ship Tier-1 empty-packet skip without combo_safe.
- Static or dynamic quota alone still needs its own A/B.

## Evidence

| Claim | Source |
|-------|--------|
| combo_safe ~63 calls / ~79 s; 6/47 FN | `14-router-quota-1pod.md`, ADR-008 |
| Safe combined harvest ~150–220 calls | `14`, `50-router-false-economy.md` |
| Gate: 3/381 cap-drivers + 16/381 flip set | `PLANNING-HANDOFF.md` §5, `19` |
