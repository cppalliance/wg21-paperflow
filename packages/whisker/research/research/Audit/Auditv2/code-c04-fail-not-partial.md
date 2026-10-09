# C04 Fail-Not-Partial

**Role**: Audit fault handling. Errors produce clean failures, not partial results.
**Audited state**: whisker 0.5.0, HEAD 51cb704 + local mods.
**Gates**: G2 (Fidelity: fail not partial), D3 (Batch isolation).

## 1. Scope

Verify that errors produce clean failures (not partial results), debug
transcripts are preserved before error tombstones, malformed sidecar handling
is robust, and batch isolation prevents one paper's failure from aborting the run.

## 2. Commands and Exits

```
uv run --package whisker pytest packages/whisker/tests/test_fusion.py -v
uv run --package whisker pytest packages/whisker/tests/test_incremental.py -v
```

Exit: Offline suite passes (E1). Runtime LLM paths BLOCKED.

## 3. Current Evidence

### 3.1 Batch isolation in deterministic lane

`__main__.py` `_score_main()` (lines 218-233):
```python
except (MissingPaperMdError, MissingSourceError) as exc:
    skipped += 1
    logger.warning("skipping %s: %s", pid, exc)
except Exception:
    errored += 1
    logger.exception("error scoring %s (skipped)", pid)
```
Each paper is scored in its own try/except. One paper's exception increments
`errored` and the loop continues. The batch never aborts on a single paper.
At line 237: `if not results: ... return EXIT_ERROR` only fires when ALL
papers failed. Otherwise errored papers are skipped and remaining results
are reported.

### 3.2 Batch isolation in advisory lane

`tapetum_llm/cli.py` `_adjudicate_one()` (lines 1246-1258):
```python
except Exception as exc:
    if batch:
        logger.error("Failed to adjudicate %s [%s]: %s: %s", ...)
    else:
        logger.exception(...)
    _write_error_tombstone(pid, backend, exc)
```
Each paper runs in its own async task with a per-paper try/except firewall.
Failure writes an error tombstone and continues. The `asyncio.gather()` call
at line 1265 collects all results including errors.

### 3.3 Error tombstones

`_write_error_tombstone()` (lines 667-691):
```python
payload = {"pid": pid, "status": "error", "error": type(exc).__name__}
out_path.write_text(json.dumps(payload, ...), ...)
```
This ensures a stale pass from a previous run is replaced by an error marker.
The fusion layer handles this: `_tapetum_is_usable()` (line 155) returns False
when `tapetum.get("status") == "error"`, so fusion falls back to the
deterministic verdict only.

### 3.4 Debug transcript preservation before tombstone

In `_adjudicate_one()`, the PDF judge path uses a `try/finally` block
(lines 1127-1144):
```python
try:
    judge_result = await asyncio.wait_for(...)
    await _attach_ideal(judge_result, judge_debug)
finally:
    if judge_debug and hasattr(backend, "get_debug_md_path"):
        debug_path = backend.get_debug_md_path(pid, tool="tapetum_llm")
        ...
        write_debug_file(debug_path, judge_debug)
```
The `finally` block runs before the outer except that writes the tombstone.
The debug transcript is flushed with all accumulated calls even when a later
call (metadata, page escalation, ideal verification) fails.

The text lane has the same pattern (lines 1189-1221) for ideal debug.

### 3.5 Malformed sidecar handling

`fusion.py` validates both sidecars before use:

- `_validate_whisker_sidecar()` (line 116): Rejects non-dict, missing pid,
  missing verdict, or verdict not in the recognized set. Returns None on invalid.
- `_validate_tapetum_sidecar()` (line 129): Rejects non-dict, missing pid.
  Sanitizes fingerprint. Handles `status="error"`. Rejects missing/invalid
  `suggested_verdict` or `confidence`.
- `_finite_float()` (line 105): Rejects bool, non-numeric, Inf, NaN.

When validation fails, `fuse_verdicts()` (lines 335-338) substitutes a stub
`{"pid": "", "verdict": "?"}` for whisker and None for tapetum. The
`_tapetum_is_usable()` check then produces `whisker_only` fusion, preserving
the deterministic verdict.

### 3.6 Confidence-0 stub detection

`_tapetum_is_usable()` (line 163): A sidecar with `confidence == 0.0` and no
`axis_findings` is treated as unusable (a partial/incomplete adjudication).
This prevents a partially-completed LLM call from being treated as a valid
advisory opinion.

### 3.7 Pipeline error handling

`adjudicate_paper()` in `adjudicate.py` (lines 693-706): When the pipeline
dispatch produces no result (`state._result is None`), a TapetumResult with
`status="error"` and `confidence=0.0` is returned. This is then caught by
`_tapetum_is_usable()` returning False.

### 3.8 Partial read protection

`adjudicate.py` `_custom_decide()` (lines 347-349):
```python
if state.partial and suggested_verdict == VERDICT_PASS:
    suggested_verdict = VERDICT_REVIEW
```
An oversized paper whose chunk was hard-split (partial read) can never become
a clean pass. This prevents incomplete reads from masquerading as complete
assessments.

## 4. Findings

| # | Finding | Severity | Confidence |
|---|---------|----------|------------|
| F1 | Batch isolation: per-paper try/except in both lanes, errored papers skipped | Informational (confirms claim) | HIGH |
| F2 | Error tombstones replace stale passes on adjudication failure | Informational | HIGH |
| F3 | Debug transcripts flushed via finally before tombstone write | Informational | HIGH |
| F4 | Malformed sidecars validated and rejected with fallback to deterministic | Informational | HIGH |
| F5 | Confidence-0 stubs treated as unusable, preventing partial advisory opinion | Informational | HIGH |
| F6 | Partial-read papers demoted to review, never pass | Informational | HIGH |

No violations found.

## 5. False-Pass Hypothesis

**Could a partial/error result be mistaken for a complete result?**

The only vector is if an error tombstone had a valid-looking
`suggested_verdict` and non-zero confidence. Code inspection of
`_write_error_tombstone()` shows the payload has only `pid`, `status`, and
`error` fields, never `suggested_verdict` or `confidence`.
`_validate_tapetum_sidecar()` requires `suggested_verdict` in the recognized
set and valid `confidence`; without them, validation returns None, and fusion
falls back to whisker_only. The vector does not exist.

## 6. Gate/Dimension Mapping

- **G2 (Fidelity)**: PASS. Errors produce clean failure states (tombstones),
  never partial results mistakable for complete ones.
- **D3 (Batch isolation)**: PASS. Per-paper exception handling in both lanes
  prevents one paper's failure from aborting the batch.

## 7. Limitations

- Runtime proof BLOCKED: cannot verify live error-tombstone writes or debug
  transcript preservation during actual LLM failures.
- Malformed sidecar handling tested only with synthetic dicts in test_fusion.py,
  not with corrupted on-disk JSON files.

## 8. Conclusion

The fail-not-partial claim holds. Both the deterministic and advisory lanes
use per-paper firewalls that log, tombstone, and continue. Debug transcripts
are preserved via `finally` blocks before tombstones are written. Malformed
sidecars are validated and rejected, falling back to the deterministic verdict.
Partial reads are demoted to review. No code path produces a partial result
mistakable for a complete one.
