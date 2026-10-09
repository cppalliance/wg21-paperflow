# CARD: Deterministic metadata / outline diff

## Bottom line (3 sentences max)
The metadata LLM call is structurally redundant with data `source_router` / `html_outline` already extract; **~471 s @ S=16** is arithmetic-solid. Not shippable today (AGGRESSIVE; 0/1 at HEAD) — A/B only until holdout parity. Necessary but not sufficient for ≤600 s (~1191 s after short-circuit + this lever).

## Numbers that matter
- Metadata LLM calls: **377**; Δwall = 377 × 20 / 16 ≈ **471 s** (~7.9 min)
- After v11 short-circuit (−1341) + det. metadata (−471): **~1191 s (~20 min)** on 3003 s baseline
- Ship stop/go: >**5%** metadata verdict disagreement **or any** fused-verdict change → do not ship
- Pass criteria: ≥**95%** verdict agreement on 381; **zero** fused `combined_verdict` changes on holdout+replay; PDF false-fail ≤**2%** on clean papers
- Orthogonal to short-circuit: short-circuit skips units; this eliminates the metadata LLM itself

## Architecture implication
Implement `compare_metadata_outline()` returning `MetadataOutlineCheck` without `run_judge_task`; wire behind flag + `TAPETUM_METADATA_SHADOW` dual-run. Port prompt rules as explicit policy (PID fail hard; date/title/PDF noise → review). Reuse HTML outline/level diff already in router; PDF needs conservative review caps. Whisker-only; bump `_LANE_VERSION` on ship; rollback via `--llm-metadata`.

## Cite / do not re-open
- Shipping code-only without shadow/holdout gates
- Treating LLM as uniquely powerful detector (it adds fuzzy PDF lenience, not recall power on HTML)
- Conflating with table compare or dual-pod
- Claiming this alone reaches 600 s

## Links to related reports
- `research/cold-run-10min-1pod/13-deterministic-metadata.md` (this source)
- `00-baseline.md`, `10-impl-status-1pod.md`, `19-quality-gate-1pod.md`
- Prior: `tapetum-llm-speedup/131-surya-model-sizing.md`, `cold-run-10min/17-metadata-shortcircuit-design.md`
