# D28 — Reject P/D disaggregation (one 8×H200)

**Date:** 2026-07-24  
**Status:** Accepted (reject)

---

## Decision needed

Pursue prefill/decode disaggregation on the single `alliance-pod` 8×H200 for cold-run speed?

## Recommendation from research

**No.** Workload is short-OSL decode-bound JSON; twin/second node forbidden. DeepSeek FP8 needs the full 8×H200 per replica — classic 4P+4D cannot hold a second weight copy. Prefer call elimination, Non-think/verdict-first, APC/prefix, MTP A/B (unbanked), dense offload when live.

## If yes

- High ops cost (proxy, NIXL/MORI, P:D tune) with no deployable topology under the twin ban.
- Ports Qwen-235B / long-OSL PD headlines that do not apply.

## If no

- Reject ledger stays closed unless measured ≥15% wall drop on unit shapes at S=16/c=32 **without** a second node (ADR-023 reopen bar).

## Evidence

| Claim | Source |
|-------|--------|
| P/D = No; short OSL; can't split node | ADR-023, `05k-web-pd-disagg.md` |
| Reject ledger / NON-GOALS | `SYNTHESIS.md`, `PLANNING-HANDOFF.md` §8 |
