# 09 - Error-Handling-Robustness

**Verdict:** usable-with-conditions — the batch firewall correctly isolates per-paper LLM failures, but failure paths leave no authoritative sidecar record and a rerun failure after a prior success silently preserves a stale pass sidecar, which hides data loss from downstream consumers.
**Confidence:** high

## Findings
- [CRITICAL] Rerun failure after a prior successful adjudication leaves a stale `*.tapetum.json` on disk. The batch worker catches all exceptions and skips persistence (`cli.py:304-315`); `_persist_result` runs only on the success path (`cli.py:289`). There is no tombstone, delete, or error sidecar write on failure. A paper adjudicated `pass` yesterday that fails today with `"Raw JSON completion failed after 3 attempt(s)"` (`model_backends.py:418-421`, baseline:49) still presents yesterday's pass sidecar as the current advisory result.
  Impact: corrupts the advisory record; a downstream integrator reading sidecars alone cannot detect the failed rerun and may treat stale output as fresh — the exact failure class this persona hunts (hidden data loss).

- [HIGH] Hard failures produce no structured sidecar at all, only an optional debug transcript. Baseline: **200** debug files vs **197** sidecars (00-baseline:44-45); all 9 hard failures were JSON retry exhaustion (00-baseline:49). The exception path increments `counts["error"]` and logs one line (`cli.py:304-311`) but never writes `{pid}.tapetum.json`. First-run failures are indistinguishable from "never adjudicated" without log scraping or debug-file inventory.
  Impact: failure state is not machine-readable; batch reruns are idempotent for never-succeeded papers but asymmetric for previously succeeded ones (see CRITICAL above).

- [HIGH] Partial-read disclosure stops at verdict demotion and never reaches the persisted sidecar. `state.partial` forces `pass` → `review` in decide (`adjudicate.py:245-246`) but `TapetumResult.to_dict()` omits `partial`, `chunked`, and any read-coverage metadata (`models.py:106-124`). A consumer parsing sidecars cannot tell a `review` driven by an oversized hard-split section (`chunking.py:64-78`, `partial=True`) from a full-document human-review signal.
  Impact: partial adjudication can masquerade as a complete one — violates the spirit of the root Fidelity contract ("Never produce a partial result mistakable for a complete one", `CLAUDE.md:127`) even though tapetum is advisory.

- [HIGH] Partial demotion is pass-only; `fail` and `review` from an incomplete read stand unchanged. Decide applies the partial guard only when `suggested_verdict == VERDICT_PASS` (`adjudicate.py:245-246`). A hard-split oversized section (`chunking.py:76-78`) leaves most of that section unread by a single chunk call; the model can still emit `fail`/`review` on the fragment, and decide preserves it.
  Impact: a verdict backed by a fraction of the document can present as a full-paper advisory finding with no partial flag — false-fail or over-confident review from hidden truncation.

- [MED] The `_result is None` fallback returns a normal-looking `TapetumResult` that the CLI would persist as a sidecar if dispatch ever completed without decide setting `_result`. Fallback: `suggested_verdict=VERDICT_REVIEW`, `confidence=0.0`, `primary_concern="pipeline did not produce a result"` (`adjudicate.py:427-439`). Decide exits early when `working is None` (`adjudicate.py:217-219`) without raising. No `error`, `failed`, or schema version field distinguishes pipeline abort from a content-driven review.
  Impact: if this path fires (guard skip, future hook regression, or `stop_after` misuse), a broken run looks like a legitimate advisory review — partial failure masquerading as complete output.

- [MED] `--review-all` candidate discovery silently drops corrupt whisker sidecars. `_collect_sidecar_dicts` catches `json.JSONDecodeError` and `OSError` and `continue`s with no log (`cli.py:181-186`). Contrast: `_custom_select` loads the same file with bare `json.loads` (`adjudicate.py:164-165`), which raises and fails the whole paper — inconsistent error handling across two read paths for the same artifact.
  Impact: papers with damaged `*.whisker.json` vanish from the candidate set with no audit trail; data loss in selection, not in verdict, but still hides failure.

- [MED] Batch summary footer aggregates outcomes but not error taxonomy. Footer reports `pass/review/fail/error` counts and a single retry counter (`cli.py:322-331`). Retry warnings from `"Raw JSON parse failed"` and `"Transient API error"` share one swallowed filter (`cli.py:55-58`, `:61-73`); exhausted retries surface as generic `error` with no distinction from other exceptions. Exit code is always `_EXIT_OK` (`cli.py:37`, `:351`) despite nonzero `counts["error"]`.
  Impact: operators must parse unstructured ERROR lines to classify the 3-sidecar-gap failures; automation cannot gate on exit code or footer alone.

- [LOW] Retry exhaustion error content is adequate at the exception layer but truncated in batch mode. `VllmThinkingBackend` raises `MalformedModelOutputError` with attempt count and `content[:500]` (`model_backends.py:418-421`). Batch mode logs `Failed to adjudicate %s: %s` without traceback (`cli.py:307-311`); single-paper mode keeps `logger.exception` (`cli.py:312-313`). Debug transcript is flushed on failure via `dispatch` `finally` (`runner.py:402-403`), preserving ground truth when `--debug` is set.
  Impact: acceptable for interactive batch runs; insufficient for unattended reruns without `--debug`.

## False-pass hypothesis
Paper P was adjudicated `pass` in an earlier run. A rerun hits JSON retry exhaustion (`model_backends.py:418-421`). The batch firewall logs one ERROR line and writes no sidecar (`cli.py:304-315`). The old `pass` sidecar remains. A human or script reading only `*.tapetum.json` treats the paper as advisory-pass with no signal that the latest run failed.

## False-fail hypothesis
An oversized H2 section is hard-split (`chunking.py:76-78`, `partial=True`). One chunk sees a table fragment without headers; triage returns `fail` on the `tables` axis. Partial demotion does not apply because verdict is not `pass` (`adjudicate.py:245-246`). Sidecar records `suggested_verdict=fail` with no `partial` field — a false fail driven by incomplete read, not full-document corruption.

## What would change my mind
A batch rerun test demonstrating that on adjudication failure the CLI either (a) deletes or tombstones any existing `{pid}.tapetum.json`, or (b) writes an explicit error sidecar with `failed: true` and the exception class — and that downstream inspect/report tooling surfaces it — would flip stale-sidecar and no-sidecar findings to resolved.
