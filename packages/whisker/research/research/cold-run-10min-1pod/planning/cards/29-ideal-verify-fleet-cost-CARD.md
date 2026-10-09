# CARD: Ideal verification fleet cost

## Bottom line (3 sentences max)
`ideal_verification` is a **0.13%** call-class: **3/381** papers (0.79%) when golden ideals exist; ~**60–90 s** direct LLM wall (**2–3%** of v10 cold). No CLI skip flag; 378 papers already skip via missing ideal file. Not a ≤600 s lever — deleting ideals frees ≤90 s; gap after MODERATE is still ~660–893 s.

## Numbers that matter
- Ideal LLM calls: **3** max per cold fleet; share of 2284 ≈ **0.13%**
- Direct cost: **~60–90 s** serial (`run_task` concurrency 1); fleet wall same band
- Ideal-attributable judge waste (2 error tombstones): **11–13** calls → ~**14–16 s** fleet-eq @ S=16
- Fail-fast reorder (ideal first on 2 errors only): upper bound ~**14–16 s** cold win
- Overlap ideals: P4020R0, P4182R0, P4228R0; `cwg1.md` not in fleet

## Architecture implication
Leave ideal verify on the quality path for golden-QA papers; do not bank deletion or reorder as a 10-min program. Prefer unit/metadata N-cuts. Optional later: ideal-only retry on `IdealVerificationError` to avoid discarding completed judge work; never skip source-aware cascade on ideal `agree`.

## Cite / do not re-open
- Ideal-verify deletion as a 10-min lever
- Assuming `--skip-ideal` exists
- Ideal-`agree` short-circuit of the source-aware cascade
- Removing ideals from fixtures to “speed” cold fleet

## Links to related reports
- `research/cold-run-10min-1pod/29-ideal-verify-fleet-cost.md` (this source)
- `00-baseline.md`, `10-impl-status-1pod.md`, `14-router-quota-1pod.md`
- Prior: `tapetum-llm-speedup/{37-ideal-verifier-accountant,10-call-graph-accountant}.md`
