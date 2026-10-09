# CARD: Skip monolith revisit (1-pod pressure)

## Bottom line (3 sentences max)
Do **not** skip monolith (conditional or fleet-wide) when metadata+units “suffice”; quality cost is unbounded by that gate. Under dense offload, monolith becomes MoE-critical-path visible (~511 s), but the right MoE cut is **deterministic metadata (−377 calls)**, not deleting the document-wide lens. Skip alone does not close ≤600 s; with dense it only buys ~159 s margin at fusion risk.

## Numbers that matter
- Full skip Δwall: single MoE **−476 s** (381×20/16); dense hetero **−159 s** (511→~352 s)
- Conditional naive (metadata pass + risk_signals): ~**180/181 PDF**, ~**21 s** — no-op for speed
- Aggressive clean-screen skip: ~**165/181 PDF**, ~**206 s**; **34** papers retain monolith cnf screen missed; **16** mono-only cnf
- Full skip quality: **8/181** PDF verdict delta; **6/378** material fusion via `llm_clear_soft_review`; **392** inspect quotes gone
- v11 MODERATE + full skip without dense: ~**890 s** — still misses 600 s

## Architecture implication
Keep monolith on `alliance-pod`. Prefer AGGRESSIVE deterministic metadata diff (A/B-gated) and dense unit/metadata offload to hit 10 min without cutting the reorder/structure prompt. Defer outline-only reorder substitute to a future replacement architecture, not a skip.

## Cite / do not re-open
- Skip monolith when metadata+units scheduled
- Fleet-wide monolith skip for 1-pod speed
- Treating zero reorder hits today as license to delete the only reorder prompt
- Claiming skip closes 10 min without other levers

## Links to related reports
- `research/cold-run-10min-1pod/21-skip-monolith-revisit.md` (this source)
- `12-dense-offload-architecture.md`, `10-impl-status-1pod.md`, `13-deterministic-metadata.md`
- Prior: `cold-run-10min/49-monolith-keep.md`, `tapetum-llm-speedup/{16-monolith-redundancy-skeptic,34-verdict-value-analyst,147-verifier-monolith-textlane}.md`
