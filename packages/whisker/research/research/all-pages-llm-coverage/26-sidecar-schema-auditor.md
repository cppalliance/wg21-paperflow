# 26 - sidecar-schema-auditor

**Verdict:** usable-with-conditions (+ planned `all_pages_requested` and `unit_selection` audit fields are the right additive shape, but today's sidecar surface is split across schema versions, `unit_selection` is unwired on both lanes, and `fusion.py` treats `coverage_complete=True` with empty `checked_unit_ids` as passable unless producer semantics and fusion gating change together)
**Confidence:** high

## Findings

- [CRITICAL] `schema_version` exists but is lane-split and never validated on read: `TapetumResult.to_dict()` stamps `8` (`models.py:397`), `PdfJudgeResult.to_sidecar_dict()` stamps `7` (`pdf_judge.py:556`), error tombstones omit it entirely (`cli.py:686-690`). `_validate_tapetum_sidecar()` accepts any dict with pid/suggested_verdict/confidence and does not inspect `schema_version` (`fusion.py:128-151`; re-used by `cli.py:669-671`). Impact: a planned bump documents intent but does not fail-closed stale sidecars; operators can mix v7 PDF and v8 text sidecars without any reader rejecting them.

- [CRITICAL] `coverage_complete` is a fusion input and cannot distinguish "nothing routed" from "every page checked": fusion caps at review when `unit_coverage.coverage_complete is not True` or lists are non-empty (`fusion.py:191-195`). PDF lane defaults `coverage_complete=True` with empty ID lists before any unit work (`pdf_judge.py:831-836`); when `route_pdf_units` yields no signals, `run_unit_checks` returns `None` (`unit_judge.py:287-288`) and that default survives into the sidecar (`pdf_judge.py:554-556`, `921`). Same routed-absence default on the text lane (`adjudicate.py:435-440`). Impact: old and capped sidecars parse everywhere, but fusion reads `coverage_complete=True` + empty lists as complete coverage; `--all-pages` must redefine completion (e.g. against `page_count` / `required_unit_ids`) and fusion must consult `all_pages_requested` (or equivalent) before trusting `coverage_complete`.

- [HIGH] Planned `unit_selection` partially exists but is not on the PDF sidecar path: `UnitJudgeResult` builds per-unit `{unit_id, status, signals, reason}` entries (`unit_judge.py:398-414`), `TapetumResult` can emit `unit_selection` when non-empty (`models.py:359`, `405-406`), but `adjudicate.py` never copies `unit_result.unit_selection` into `state.unit_selection` (only read at `adjudicate.py:468`; no assignment anywhere in repo). `PdfJudgeResult` has no `unit_selection` field and `to_sidecar_dict()` never emits it (`pdf_judge.py:421-560`). Impact: adding audit fields to the plan duplicates a half-wired field; PDF `--all-pages` must extend `PdfJudgeResult.to_sidecar_dict()` and wire selection from `run_unit_checks`, not only add top-level flags.

- [HIGH] New optional fields will parse on all in-repo readers (additive `.get()` pattern), but semantics are not backward compatible unless fusion is updated: readers use tolerant access — `inspect_report.py:180-190`, `fusion.py:191-195`, `parse_ideal_verification()` (`models.py:130-135`), `fusion_report.py:84-86`. Missing `all_pages_requested` / `unit_selection` will not crash. Impact: old sidecars remain readable; capped-mode sidecars without `all_pages_requested` must continue to mean "routed-risk completion only." Fusion must treat absent `all_pages_requested` as false and must not reinterpret old `coverage_complete=True` empty-list sidecars as all-pages complete.

- [MED] `inspect_report.py` renders `unit_coverage` counts but not `unit_selection`, `all_pages_requested`, or `textlayer_diff.page_count` reconciliation: operator block at `inspect_report.py:180-209` prints `complete={coverage_complete}` and ID list lengths only; PDF page total lives separately in `textlayer_diff.page_count` (`pdf_judge.py:544-548`) but inspect never joins them. Impact: even with correct sidecar fields, `--inspect` will under-report all-pages gaps until the report surfaces `all_pages_requested`, required/checked/unchecked selection rows, and `checked vs page_count`.

- [MED] Schema bump alone will not invalidate incremental skip: fingerprint uses `_LANE_VERSION` (`cli.py:111`, `548`) plus content hashes (`cli.py:515-565`), not `schema_version`. Impact: `--all-pages` needs `lane_version` bump and fingerprint keys (e.g. `all_pages: true`) so capped-mode sidecars are not reused; bumping only `schema_version` in `to_sidecar_dict()` is necessary documentation but insufficient for reuse safety.

- [LOW] `readback` is out of scope for sidecar compatibility: `readback.py` validates comprehension facts from `.facts.jsonl` and does not load `.tapetum.json` sidecars. Impact: no readback changes required for the planned sidecar extension.

- [LOW] `fusion_schema_version` (`constants.py:158`, emitted at `fusion.py:93`) is independent of tapetum `schema_version`; `--fuse-only` rewrites fusion blocks on existing sidecars without re-adjudicating (`cli.py:760-792`). Impact: fusion output can be refreshed without a tapetum schema bump, but changing coverage gating in fusion will alter merged verdicts on old sidecars when operators re-fuse.

## False-pass hypothesis

15-page PDF, zero router signals: sidecar carries `unit_coverage={"coverage_complete": true, "checked_unit_ids": [], "unchecked_unit_ids": [], "failed_unit_ids": []}` (`pdf_judge.py:831-836`, `554-556`), no `all_pages_requested`. Fusion enters source-aware path via `unit_coverage` key (`fusion.py:177-178`), metadata passes, `coverage_complete is True` (`fusion.py:192-193`), empty unchecked/failed lists (`fusion.py:194-195`), so LLM clear paths stay unblocked. Operator reads inspect `complete=True` with `checked=0` (`inspect_report.py:190-195`) and treats the run as fully verified though no scoped page judge ran.

## False-fail hypothesis

Operator re-runs `--fuse-only` after shipping fusion logic that requires `all_pages_requested=True` for any `coverage_complete` trust: legacy v7 PDF sidecars with honest routed-complete `coverage_complete=True` would start failing the new gate and force `source_aware_review_cap` on papers that previously merged to pass, without re-adjudication (`cli.py:786-787`, `fusion.py:398-411`).

## What would change my mind

A single PR showing (1) `PdfJudgeResult.to_sidecar_dict()` at schema `9` with `all_pages_requested`, populated `unit_selection`, and page-reconciled `unit_coverage`; (2) `fusion.py::_source_aware_requires_review()` branching on `all_pages_requested` so absent/false preserves today's routed semantics and true requires `len(checked_unit_ids) == textlayer_diff.page_count` (or explicit `required_unit_ids`); (3) `inspect_report.py` rendering required/checked/unchecked against `page_count`; and (4) a test that loads a pre-change v7 sidecar (no new keys) through `_validate_tapetum_sidecar`, `fuse_verdicts`, and `format_paper_section` unchanged while a synthetic all-pages sidecar fails fusion when one `page:N` is unchecked.

## Reader inventory (backward compatibility required)

| Reader | Location | Sidecar fields consumed |
|---|---|---|
| Tapetum sidecar validator | `fusion.py:128-151` | `pid`, `status`, `suggested_verdict`, `confidence`; strips bad `fingerprint` |
| Fusion merge | `fusion.py:336-537`, especially `_has_source_aware_data` (`167-179`), `_source_aware_requires_review` (`182-215`), `_ideal_summary` (`326-334`) | `schema_version`, `metadata_outline_check`, `unit_coverage`, `defect_groups`, `unit_checks`, `evidence_dispositions`, `axis_findings`, `ideal_verification`, `confidence`, `suggested_verdict`, `status` |
| CLI persist / re-fuse | `cli.py:619-622`, `644-647`, `669-671`, `760-792`, `1177`, `1253` | full dict via validator + `fuse_verdicts`; writes `fusion`, optional `fingerprint` |
| CLI fingerprint skip | `cli.py:568-588`, `1093-1100` | `fingerprint` block only |
| Inspect report | `inspect_report.py:81-320`, `format_report` (`323-375`) | `suggested_verdict`, `confidence`, `escalated`, tier models, `ideal_verification`, `axis_findings`, `metadata_outline_check`, `unit_coverage`, embedded `fusion`, `defect_groups`, `risk_signals`, `evidence_dispositions`, `evidence_summary`, `grounded_evidence`, `reasoning` |
| Merged rollup report | `fusion_report.py:67-129`, `_classify_cosmetic` (`143-162`) | whisker verdict + tapetum `suggested_verdict`, `fusion`, `confidence`, `axis_findings`, `ideal_verification` |
| Ideal field parser | `models.py:130-135` | `ideal_verification` only |

Not sidecar readers: `readback.py` (facts JSONL only). External research scripts under `packages/whisker/research/` that parse `*.tapetum.json` manually are human/tooling consumers and should tolerate unknown keys but are not validated in production code paths.
