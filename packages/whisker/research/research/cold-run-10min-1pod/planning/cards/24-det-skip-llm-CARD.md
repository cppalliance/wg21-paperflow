# CARD: Det-skip LLM (strong deterministic signals)

## Bottom line (3 sentences max)
**No shipped mode** skips all in-paper LLM calls on strong det; closest are v11 metadata short-circuit (2-call min), empty-router (2 calls), fingerprint (warm only), and `--fuse-only` (needs sidecars). A new `--det-skip` is architecturally safe for the advisory lane (`whisker_only` fusion) but trades speed for the selection-gap blind spot. Viable as **opt-in nightly tier**, not default cold path; insufficient alone for ≤600 s.

## Numbers that matter
- Clean-pass skip cohort (modeled): ~**100–140** papers → **200–280** calls → ~**250–350 s** @ S=16
- Still **~500+ s** short of 600 s alone; disjoint from metadata-fail short-circuit
- Best-case paper today: **1–2 LLM calls**, not zero (~44.6% of v10 unit calls eliminated by partial skips)
- Fingerprint after `_LANE_VERSION` bump: **0 s** cold savings
- Advisory loss risk: **16/381**-class merged flips on skipped cohort

## Architecture implication
Prefer shipped/partial N-cuts first: v11 short-circuit → deterministic metadata → unit zero-defect predictor; optional `--det-skip` / `--profile nightly` with sidecar `coverage_mode: det_skip` for audit. Do not confuse `--review-all` (inverse: skips clean passes via candidate filter) with strong-det skip.

## Cite / do not re-open
- Default `--det-skip` replacing full advisory cold
- Claiming a mode already exists that skips all LLM on strong det
- Treating `--review-all` as det-skip
- Banking det-skip as the primary 1-pod 10-min lever

## Links to related reports
- `research/cold-run-10min-1pod/24-det-skip-llm.md` (this source)
- `00-baseline.md`, `13-deterministic-metadata.md`, `10-impl-status-1pod.md`
- Prior: `cold-run-10min/{68-cascade-early-exit-map,24-fusion-dead-reverify}.md`, `hybrid-llm-scoring/SYNTHESIS.md`
