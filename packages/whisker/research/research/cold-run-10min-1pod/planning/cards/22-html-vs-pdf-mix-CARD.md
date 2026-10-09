# CARD: HTML vs PDF mix (381-paper fleet)

## Bottom line (3 sentences max)
Fleet is **201 HTML (52.8%)** / **180 PDF (47.2%)**; HTML is already ~**11%** cheaper per paper (median 6 vs 7 calls) via cascade + routing. Mix is already baked into the 3003 s baseline and is **not** a separate path to ≤600 s. Leverage is **port HTML deterministic outline patterns to PDF** (metadata diff), not “optimize HTML harder.”

## Numbers that matter
- Calls/paper: HTML median **6** / mean **5.73**; PDF **7** / **6.43**; fleet ~**2308** calls
- Lane wall share (call-linear): HTML ~**43%** (~1295 s); PDF ~**53%** (~1589 s)
- HTML incremental det-metadata: ~**251 s** (201 calls); fleet-wide same lever ~**471 s** (377)
- Unit load: HTML ~**614** vs PDF ~**896** (PDF = ~**59%** of units)
- Tier-2: **23/201** HTML (11%); page escalation ~**16** PDF-only

## Architecture implication
Ship deterministic metadata fleet-wide (HTML-first staging OK for ~251 s), then stack MODERATE + AGGRESSIVE + dense offload. Do not drop HTML tier-1 on “clean” papers (same class as dropping PDF monolith). Dense keeps HTML tier-1/tier-2 on MoE; HTML mix raises MoE first-pass share vs PDF-only fleets.

## Cite / do not re-open
- Treating HTML cascade as if papers were already 1–2 LLM calls
- HTML-only tuning as sufficient to close the 1-pod gap
- Dropping tier-1 on clean HTML for speed
- Assuming v11 short-circuit is HTML-specific (it is lane-agnostic)

## Links to related reports
- `research/cold-run-10min-1pod/22-html-vs-pdf-mix.md` (this source)
- `00-baseline.md`, `13-deterministic-metadata.md`, `18-packages-1pod.md`, `12-dense-offload-architecture.md`
- Prior: `tapetum-llm-throughput/01-call-count-accountant.md`, `cold-run-10min/68-cascade-early-exit-map.md`
