# 14 - Fingerprint + error tombstone audit

**Verdict:** usable — tombstone fingerprinting and error-skip are implemented at HEAD; the warm-run bug described in speedup/46 and speedup/150 is **closed in code** but **legacy fingerprintless tombstones still pay one full re-cascade per paper until rewritten.
**Confidence:** high

## Executive summary

| Question | Answer |
|----------|--------|
| Error papers re-run full cascade? | **Yes**, unless incremental skip fires (matching fingerprint + `status="error"` + no `--retry-errors`). Legacy tombstones without `fingerprint` always re-run. |
| Fingerprint written on error? | **Yes**, when `fp` is non-`None` at exception time (`cli.py:1491-1497` → `_write_error_tombstone` `827-828`). **No** when `fp` was never computed (ideal read failure, non-incremental run, or fingerprint compute exception). |
| `_LANE_VERSION` | **11** (`cli.py:123`). Bump invalidates all sidecars via `lane_version` in every fingerprint. |
| Warm-path bug still open? | **no** — fix landed; cite `cli.py:794-837`, `1266-1301`, `1491-1497`, `--retry-errors` at `373-378`. |

## speedup/46 and speedup/150 (cited)

From `research/cold-run-10min/00-baseline.md` and prior speedup corpus:

- **speedup/46-warm-run-auditor.md:** Warm wall **64.8 s** with **375/381 skipped**, **6 evaluated** (~85% LLM re-cascade). Root cause at time of write: error tombstones had **no fingerprint**, so `_fingerprint_matches` was always false. Proposal: store fingerprint on tombstone + skip unchanged errors; expose `--retry-errors` for operator retry.
- **speedup/150-verifier-warmrun-quality.md:** Confirmed the above against **pre-fix** line refs (`cli.py:747-769` tombstone without fingerprint). Also cites **≥25% verdict flip** on a **20-PID borderline subset** (not 381-paper A/A) and `_LANE_VERSION` cadence notes.
- **speedup P146** (`146-verifier-prefix-cache-contradiction.md`): Lifetime pod means **decode 5.91 s** vs **prefill 0.46 s** per request (96.7% APC hit rate on alliance-pod); used in cold-run baseline arithmetic, orthogonal to tombstone skip.

Lever ranking in `00-baseline.md` placed **error tombstone fingerprints** as CONSERVATIVE lever #5: warm **65 s → 10–15 s** steady state after fix.

## Current code path (HEAD)

### `_LANE_VERSION = 11`

Defined at `packages/whisker/src/whisker/tapetum_llm/cli.py:123` with changelog comments `101-122`:

| Version | Invalidates when |
|---------|------------------|
| v2 | Field-description caps + slot max tokens |
| v3 | Per-page recall screen + page escalations |
| v4 | Source-grounded missing-content provenance |
| v6 | Mandatory metadata/outline + fail-closed unit coverage; full prompt/schema/service fingerprint |
| v7 | Ideal verifier attached; ideal content + verifier identities in fingerprint |
| v8 | Fusion ideal validation (sidecar read path) |
| v9 | `coverage_mode` key (`default` / `exhaustive` / `all_pages`) |
| v10 | Routed units without packets pre-filtered before `MAX_UNIT_CHECKS` |
| v11 | Metadata-fail short-circuit; HMAC per-paper guard tag; user-message reorder (candidate md first) |

**Any bump forces re-adjudication** of all papers on the next bare full run (incremental compares `lane_version` in `_compute_fingerprint` / `_fingerprint_matches`).

### Fingerprint contents (`_compute_fingerprint`, `595-648`)

Keys that invalidate incremental skip when changed:

- `md_sha256`, `source_sha256` — converted markdown and staged source file
- `prompt_sha256` — lane prompt contract (PDF: monolith + page + metadata + unit prompts; text: cascade + metadata + unit)
- `model` — effective service contract JSON (`_effective_model_contract`)
- `lane_version` — `_LANE_VERSION`
- `lane` — `pdf_textlayer_judge` or `text`
- `schema_sha256` — structured output schemas for the lane
- `ideal_sha256`, `ideal_prompt_sha256`, `ideal_schema_sha256`, `ideal_model` — when an ideal exists
- `coverage_mode` — `default`, `exhaustive`, or `all_pages` (superset skip: existing `all_pages` satisfies lower modes; reverse never skips)

### Incremental skip (`_adjudicate_one`, `1257-1301`)

Bare full run enables incremental unless `--force` (`1173-1176`). For each paper:

1. Compute `fp` via `_compute_fingerprint` (skipped when `ideal_read_error` is set — see gap below).
2. If `_fingerprint_matches(pid, backend, fp)`:
   - **`status="error"` + `--retry-errors`:** fall through → full re-cascade.
   - **`status="error"` + no flag:** skip with log `previous error; use --retry-errors` (`1286-1297`).
   - **Success sidecar:** skip with `fingerprint match` or `fingerprint superset: …`.
3. Else: adjudicate full PDF or text cascade + ideal attach.

`_fingerprint_matches` (`679-702`): all keys must match except `coverage_mode` rank (existing ≥ requested thoroughness).

### Error tombstone write (`794-837`, `1482-1497`)

On any adjudication exception:

```python
_write_error_tombstone(
    pid, backend, exc,
    partial_progress=progress if progress else None,
    fingerprint=fp,
)
```

Payload: `pid`, `status="error"`, `error` (exception class name), optional `partial_progress`, optional `fingerprint`.

**Replaces** any stale pass sidecar (fail-not-partial). Fusion treats `status="error"` as unusable (`fusion.py:142-143`, `158-159`).

### `--retry-errors` (`373-378`, `1269-1277`)

Opt-in re-evaluation of error tombstones even when fingerprint matches. Without it, matching error tombstones skip LLM (steady-state warm target from speedup/46).

## Error papers and full cascade — behavior matrix

| Sidecar state | Next bare full run (incremental on) | Cascade |
|---------------|-------------------------------------|---------|
| Legacy error, no `fingerprint` | `_fingerprint_matches` → false | **Full cascade** every run until new error/success rewrites sidecar |
| Error + matching fingerprint | Skip unless `--retry-errors` | **No LLM** (hash + read only) |
| Error + matching fingerprint + `--retry-errors` | Re-adjudicate | **Full cascade** |
| Error + fingerprint mismatch (inputs/lane bump) | Re-adjudicate | **Full cascade** |
| Success + matching fingerprint | Skip | **No LLM** |

Tests: `packages/whisker/tests/test_incremental.py` — `TestErrorTombstoneFingerprint` (`1069-1237`).

## Fingerprint on error — when it is and is not written

| Condition at failure | `fingerprint` on tombstone |
|----------------------|----------------------------|
| Incremental on, ideal readable, fp computed before adjudicate | **Written** (normal warm fix path) |
| Incremental on, `ideal_read_error` set (`1213-1217`) | **Not written** — incremental block skipped, `fp` stays `None` (`1304-1305`) |
| Exception during `_compute_fingerprint` in skip block | **Not written** (`1302-1303`) |
| `--force` / non-incremental explicit PID run | **Not written on error** unless fp computed mid-success path (error before success-path recompute) |

Legacy v10 warm-run error PIDs (P3984R0, P4182R0, P4228R0 per speedup/46) were produced under pre-fix tombstones; **one more failure or `--retry-errors` run under HEAD** attaches fingerprint; **second** warm run skips.

## Warm-path bug status

**Closed (no).** speedup/46 and speedup/150 described missing tombstone fingerprinting. HEAD implements:

| Fix | Location |
|-----|----------|
| Tombstone accepts and persists fingerprint | `cli.py:794-837` (`800`, `827-828`) |
| Exception path passes `fingerprint=fp` | `cli.py:1491-1497` |
| Incremental skip for matching error tombstones | `cli.py:1266-1299` |
| Operator override | `cli.py:373-378` (`--retry-errors`) |
| Tests | `test_incremental.py:1069-1237` |

**Residual operational gap (not an open code bug):** fingerprintless legacy tombstones still trigger full cascade until migrated; `ideal_read_error` path still omits fingerprint on tombstone.

## False-pass hypothesis

Skipping a matching error tombstone preserves `status="error"`; fusion remains unavailable for that PID. No pass promotion without re-adjudication success.

## False-fail hypothesis

Transient `PdfLaneError` (e.g. JSON truncation) stored with fingerprint: nightly skip preserves stale error until `--retry-errors` or input/lane bump — honest stale error, not a conversion false-fail.

## What would change my mind

Measured warm run after HEAD deploy still showing **>0 evaluated papers** whose tombstones contain matching fingerprints and no `--retry-errors`, or second warm run still **64.8 s** with six full cascades after all error sidecars show `fingerprint` blocks.
