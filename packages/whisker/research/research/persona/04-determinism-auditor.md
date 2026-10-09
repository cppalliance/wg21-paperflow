# 04 - Determinism Auditor

**Verdict:** usable-with-conditions (+ the no-LLM / no-network / no-randomness reproducibility claim holds for per-paper scoring and persisted artifacts; two stdout-ordering gaps and one missing full-corpus byte-identity gate prevent a clean "usable" stamp)
**Confidence:** high

## Findings

- [HIGH] Per-paper scoring is byte-stable on re-run. Evidence: runtime double-call of `score_paper` on P3100R6 and P3181R1 (`reference_engine=None`) produced identical `to_dict()`; oracle path on P3181R1 (`reference_engine='markitdown'`) also identical (`ref_nid=0.9805`, same verdict). CLI `--no-reference --no-write --json` for those two PIDs was byte-identical across two subprocess invocations. Impact: sidecar fields and verdicts are trustworthy for CI regression on fixed inputs.

- [HIGH] Persisted batch artifacts sort by pid before serialization. Evidence: `build_report` sorts `results` by `r.pid` (`report.py:89`); `render_report_md` sorts (`report.py:100`); `WhiskerResult.to_dict()` sorts `hard_flags` and `soft_flags` (`score.py:111-112`); region detail sorted by `token_start` (`score.py:219-223`). Runtime: `build_report` and `render_report_md` byte-identical on repeat. Impact: `whisker/report.json` and `report.md` are reproducible regardless of scoring order.

- [MED] `--json` stdout array order follows scoring order, not pid sort. Evidence: `__main__.py:253` emits `[r.to_dict() for r in results]` with no sort, while `build_report` sorts (`report.py:89`). With `--all`, scoring order comes from `list_all_paper_ids()` (`__main__.py:184-186`, `sqlite_backend.py:762-764`). Impact: machine consumers piping `--all --json` get a stable array only if DB physical row order is stable; diffing two full `--json` runs could show reordering with identical per-paper payloads.

- [MED] `list_all_paper_ids()` has no SQL `ORDER BY`. Evidence: `sqlite_backend.py:762-764` runs `SELECT paper_id FROM papers` bare. Current data dir returns insertion-sorted ids (runtime: 9129 ids, `rows == sorted(rows)`), but SQLite does not guarantee physical order across VACUUM/rebuild. Impact: `--all` batch iteration order (and thus `--json` array order) is environment-dependent; per-paper sidecars and sorted `report.json` are unaffected.

- [LOW] Hungarian assignment and fuzzy-rescue ties are deterministic. Evidence: `match.py:166` uses `scipy.optimize.linear_sum_assignment`; fuzzy rescue scans GT then pred in index order with "first qualifying pred wins" (`match.py:186-209`); `reading_order_ned` sorts internally (`match.py:290-291`). Runtime: symmetric swap tie `gt=['aaaa','bbbb']` / `pred=['bbbb','aaaa']` always yields `[(0,(1,),0.0),(1,(0,),0.0)]` across 5 repeats; ambiguous fuzzy case always picks pred index 1. `test_match.py:95-100` asserts repeat equality. Impact: bench `nid` / `reading_order` axes do not flip on ties across runs on the same platform/scipy build.

- [LOW] Float nondeterminism is bounded by explicit 4dp rounding at serialization and guard compare. Evidence: `WhiskerResult.to_dict()` rounds metrics to 4dp (`score.py:86-109`); guard uses `_NDIGITS = 4` with symmetric rounding before slack/floor compare (`guard.py:112-117`, redteam-synthesis Tier-1 #7 verified present). Internal verdict compares full-precision floats to named constants (`score.py:156-173`), but run-to-run variance is absent because inputs are pure functions. Impact: guard baseline diffs and sidecar JSON are not subject to IEEE-754 boundary flicker; unrounded in-memory compares are still theoretically sensitive at exact threshold edges (same input, same bit pattern).

- [LOW] No hash-seed or set-order leakage into outputs. Evidence: `set`/`frozenset` in `match.py:169-170`, `gates.py:63`, `facts.py:467` are membership-only; no `hash()`-sorted iteration feeds prompts or reports. `content_recall` iterates `Counter` built from left-to-right `findall` (`metrics.py:369-388`). `facts.py` sorts table neighbors by fixed direction order (`facts.py:452-453`). Impact: `PYTHONHASHSEED` does not affect whisker artifacts.

- [LOW] Human terminal summary is intentionally not byte-identical across runs. Evidence: `render_summary` takes `elapsed` from `time.monotonic()` (`__main__.py:201-218`, `report.py:248-249`); docstring states determinism requires fixed `elapsed` (`report.py:277`). Sidecars and `--json` omit elapsed. Impact: stdout human text varies by wall clock; not a scoring defect.

## False-pass hypothesis

none found (for determinism). Re-running the same staged source + converted markdown cannot flip a fail to pass via randomness or collection order: verified on real papers and synthetic tie matrices. A broken conversion that passes does so because thresholds are wrong, not because whisker is nondeterministic (see 00 section 3c: P3941R2/R3/R4 fail on `heading_monotone` with `uni=0.999`, a logic/threshold issue, not run variance).

## False-fail hypothesis

none found (for determinism). No case where identical inputs produced different verdicts across back-to-back runs. The closest operational false-fail risk is guard slack at exactly 4dp boundaries (`guard.py:112-117`), which is deterministic given the same float inputs, not run-to-run noise. Heading-monotone false fails (00 section 3c, 9/14 fails) are stable structural gates, not flaky scoring.

## What would change my mind

A byte-level diff of all 382 sidecars plus `report.json` from two consecutive `whisker --all --no-reference --no-write` runs (or `--json` redirected to file) showing any per-paper field or count mismatch would flip this to **garbage** for the reproducibility claim. Conversely, adding an integration test that writes sidecars twice and asserts byte identity (or sorting `--json` output by pid in `__main__.py:253`) would flip to **usable** unconditionally.
