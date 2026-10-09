# ADR-026: Keep ideal-verify (not a 10-min lever)

## Status

Proposed — keep; do not delete for speed

## Date

2026-07-24

## Context

`ideal_verification` fires on **3/381** papers (0.79%) when a golden ideal exists under `packages/tomd/tests/fixtures/golden/ideals/`. Direct cost: **3 LLM calls**, **~60–90 s** serial (~2–3% of v10 3003 s wall). Post-v11 survivor mix still carries ~1 ideal call.

There is no `--skip-ideal` flag; 378 papers skip only because no ideal file. Ideal-stage failures after a completed cascade wasted ~11–13 judge calls on v10 (~14–16 s fleet-equivalent). Deleting ideals or skipping verify recovers ≤90 s and does not close the post-v11 gap (~660–893 s to 600 s).

Ideal verify is quality-bearing on golden-QA overlap papers; short-circuiting the source-aware cascade on ideal `agree` would false-clear source divergence that matches an ideal (`29`).

## Decision

1. **Keep** ideal verification on the cold path for papers with ideal fixtures.
2. Do **not** treat ideal-verify deletion, disable flags, or ideal-first cascade skip as a ≤10 min / Option A wall lever.
3. Optional hygiene (non-blocking): ideal-only retry on `IdealVerificationError` to avoid redoing the full judge cascade on warm reruns — savings are small; do not schedule ahead of det-metadata / dense work.
4. Do **not** remove ideal files from the fixture tree to “speed” fleets.

## Consequences

**Positive**

- Preserves golden-QA cross-check on the three overlap PIDs.
- Avoids a high-risk quality cut for a ≤3% wall distraction.

**Negative / cost**

- ~60–90 s remains on cold when all three ideals fire.
- No CLI opt-out for operators who want a pure speed run (by design).

## Evidence

| Claim | Source |
|-------|--------|
| 3/381; ~60–90 s; not a ≤600 s lever | `29-ideal-verify-fleet-cost.md` |
| Drop ideal-verify as 10-min lever = non-goal | `NON-GOALS.md`, `PLANNING-HANDOFF.md` §8 |
| 0.13% call class; reject ledger | `SYNTHESIS.md` / FILE-MANIFEST via `29` |
| Ideal-first skip cascade = false-pass risk | `29-ideal-verify-fleet-cost.md` |
