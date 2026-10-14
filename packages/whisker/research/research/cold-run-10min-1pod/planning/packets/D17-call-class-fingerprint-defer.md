# D17 — Defer call-class fingerprints

**Date:** 2026-07-24  
**Status:** Deferred (0 s on first cold)

---

## Decision needed

Schedule per-call-class fingerprints now as a cold-run ≤10 min ticket?

## Recommendation from research

**No — defer.** On a true cold with empty `whisker/llm/` sidecars, every class misses: **0 s saved**. Helps prompt-edit **reruns** after a prior fleet only. Resume after MoE package / dense path as a dev/ops accelerator; normalize guard-tags so HMAC tags do not poison keys.

## If yes (schedule on cold path)

- Burns engineering on iteration tax while first-cold N×L gap remains.
- Sidecar schema churn concurrent with det-metadata / dense ships.

## If no (defer)

- Program stays on call elimination and L cuts that move bare cold.
- Warm whole-paper skip (~64.8 s) remains the only fast incremental path today.

## Evidence

| Claim | Source |
|-------|--------|
| Cold first-run impact 0 s; rerun-only | `25-call-class-fingerprint.md`, ADR-022 |
| Not on cold path | `SYNTHESIS.md` |
| Warm skip 375/381 in 64.8 s irrelevant to bare cold | `00-baseline.md`, `PLANNING-HANDOFF.md` §1 |
