# D23 — H2 window (±1 neighbor)

**Date:** 2026-07-24  
**Status:** Open (dense enabler; pair with D22)

---

## Decision needed

Scope unit LLM prompts to **H2 window ±1 neighbor** (+ preamble ≤2k chars; soft 8k / hard 12k chars) instead of full `candidate_md`?

## Recommendation from research

**Yes, for unit checks only (v1).** Fence-aware split via `chunking.py:_split_sections`. HTML `section:N` by index; PDF `page:N` by heading match then proportional fallback. Table-presence units: table section only (no ±1 prose). Do **not** scope monolith / metadata / escalation in v1.

## If yes

- P50 user payload ~9.3k → ~2.9k tok; P90 under ~10–12k with hard cap.
- Required for dense recipe S=32–48; without it offload collapses to MoE-class L.
- Hard overflow → D21 MoE fallback.

## If no

- Full-md p95 ~50k keeps dense at S≤16 / L≈20 s → negative EV cascade.
- MoE prefill-only savings (~198 s) insufficient as a solo 10-min lever.

## Evidence

| Claim | Source |
|-------|--------|
| H2±1 constants; unit-only v1 | ADR-004 |
| Full-md vs scoped sizes; S≤16 vs 32–48 | `23-payload-scope-dense.md` |
| Scoping before dense `_LANE_VERSION` bump | ADR-004 landing order |
