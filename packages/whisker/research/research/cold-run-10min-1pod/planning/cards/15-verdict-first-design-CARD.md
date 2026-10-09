# CARD: Verdict-first design — UnitCheckClear + fail-path bifurcation

## Bottom line (3 sentences max)
Two-stage `UnitCheckClear` → `UnitCheckDefects` is the highest-yield decode shrink on surviving metadata-pass units. Post-v11 rescale @ S=16: unit bifurcation **~92 s** central (**77–110**); full MODERATE verdict-first stack **~155 s** (**124–155**). Leaves wall ~**1338 s (~22 min)** — necessary MODERATE lever, not sufficient for ≤600 s alone.

## Numbers that matter
- Post Tier A+B: **1419** calls, **663** units, ~**463** zero-defect survivors (~70%)
- Pass P50 JSON **77 tok** (~55 in reasoning) → `UnitCheckClear` target ~**15–25 tok**
- Caps: pass **max_tokens=128** (retry 192); fail path **768** (retry ceiling 1152)
- Apply L_abs on survivors only — naive full-fleet −250 s includes ~**319 s phantom** on eliminated units
- After short-circuit + verdict-first: **~1493 − 155 ≈ 1338 s**; still **~738 s** above 600 s

## Architecture implication
Ship flat pass micro-schema (verdict-first field order); escalate to slimmed full schema on low confidence / high-risk / pre-screen fail. Map both stages to existing `UnitCheck` for persistence; include `unit_schema_variant` in lane fingerprint. Default: Stage 1 only on metadata-pass, non-high-risk units — avoid +~250 s worst-case double-call on defect papers. Gates: 48-anchor ≥95% verdict stability; Stage-1 false-clear ≤5%.

## Cite / do not re-open
- Cap-alone without schema change (saves 0 s at 77-tok decode)
- Always Stage1→Stage2 on every unit without holdout proof
- Stacking full-fleet verdict savings on post-short-circuit survivors
- Claiming this closes 10 min on one pod

## Links to related reports
- `research/cold-run-10min-1pod/15-verdict-first-design.md` (this source)
- `00-baseline.md`, `11-wall-arithmetic-1pod.md`, `18-packages-1pod.md`
- Prior: `cold-run-10min/{47-max-tokens-shrink,62-schema-slim-web,14-output-token-surgeon}.md`
