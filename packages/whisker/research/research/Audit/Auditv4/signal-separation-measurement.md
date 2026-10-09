# Auditv4 — Signal separation measurement (Phase 2 Vorschaltung)

Date: 2026-08-04. Workspace: 381 converted papers under `$WG21_DATA_DIR`.
No code changes. Measurement only.

## Question

Can `punct_missing_abs`, `punct_divergence`, or source-based
`source_reading_order` hard-gate operator corruption (MANGLE / PERMUTE /
CELLSWAP) without massacring the clean fleet?

## Answer

**No.** None of the three signals separates mutations from clean papers.
Hard-gating any of them would recreate the ref_nid / shingle-coverage fleet
massacre. Phase 2b and Phase 2c gate paths are cancelled on this evidence.

## Clean-fleet distributions (381 papers)

| Signal | min | p50 | p90 | p95 | p99 | max |
|---|---:|---:|---:|---:|---:|---:|
| `punct_divergence` | −0.036 | 0.153 | 0.373 | **0.421** | 0.518 | 0.533 |
| `punct_missing_abs` | 3 | 237 | 1352 | **1883** | 2976 | 10490 |
| `source_reading_order` | 0.0 | 0.200 | 0.743 | **0.796** | 0.899 | 0.935 |

HTML dominates punct noise (divergence p50 0.26 vs 0.07 PDF). Six HTML papers
hit `BLOCK_MATRIX_CELL_BUDGET` and report `source_reading_order = 0.0` as
non-measurement.

## Separation vs mutations

Five pass papers for MANGLE/PERMUTE; CELLSWAP on P4186R0 / P4212R0 (only
pass+table papers).

| Signal | Mutation | Clean p95 | Mutation range | Separates? |
|---|---|---:|---|:---:|
| `punct_missing_abs` | MANGLE | 1883 | 4–26 (Δ +0 to +6) | **No** |
| `punct_divergence` | MANGLE | 0.421 | 0.004–0.013 | **No** |
| `source_reading_order` | PERMUTE | 0.796 | 0.0–0.958 | **No** |
| all three | CELLSWAP | — | 0 change | **No** |

Clean papers already score far worse on punct than MANGLE canaries. PERMUTE
min is 0.0 while clean max is 0.935. CELLSWAP leaves the token multiset
unchanged, so punct/order axes are blind to table cell swaps.

## Disposition for remediation

- Do **not** add hard gates on these three signals.
- Keep them advisory / diagnostic if useful for operators.
- Phase 2a (null eligibility: `reading_order` as `None` on budget fallback,
  ideal_* ineligible vs absent) remains valid truth-reporting work.
- Table corruption needs a different mechanism (Lane 3 facts, cell-level
  comparison), not these axes.
- README drift-guard for "reading order never gates" stays aligned: no Phase
  2c gate change will invert that claim.
