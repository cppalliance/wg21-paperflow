# D19 — PDF det-metadata → fleet flip

**Date:** 2026-07-24  
**Status:** Open (after D18 HTML ship)

---

## Decision needed

Extend deterministic metadata to PDF and flip **fleet-wide**, removing the metadata LLM from the hot path?

## Recommendation from research

**Yes, only after PDF holdout.** Target: ≤**2%** false-fail on clean papers (`review` demotion OK); shadow agreement and zero fused advisory changes on holdout + 9 replay PRs. Do not block D18 on this gate. Full fleet save ~**471 s** (377 calls) once both lanes flip.

## If yes (fleet flip after PDF gate)

- Eliminates remaining ~180 PDF metadata LLM calls; drops `metadata` from prompt fingerprint class list.
- Bump `_LANE_VERSION`; optional `--llm-metadata-audit` for inspect.
- PDF page-1 font noise must stay capped at `review`, never `fail` unless PID wrong.

## If no

- HTML stays det while PDF keeps paying ~20 s × 180 / 16 ≈ **~225 s** class forever.
- Or keep LLM everywhere if PDF drift >5% / any fused holdout change (ADR-006 mind-changer → reject replacement).

## Evidence

| Claim | Source |
|-------|--------|
| Fleet ~471 s; PDF noisier than HTML | `13`, ADR-006, `22` |
| PDF false-fail ≤2%; review demotion OK | ADR-006 quality gate |
| Status AGGRESSIVE / not started | `10-impl-status-1pod.md` |
