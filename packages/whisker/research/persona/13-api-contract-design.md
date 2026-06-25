# 13 - The API / Contract Designer

**Verdict:** usable-with-conditions — dataclass contracts, library/CLI separation, and bench/guard null-eligibility are sound and tested, but the oracle scoring path and bench baseline reader violate the same null-vs-0.0 semantics the schema-3 bump was meant to unify, and several public docstrings misstate what drives the verdict.
**Confidence:** high

## Findings

- [HIGH] **Oracle `ref_*` axes break bench null-eligibility: ineligible modalities become synthetic 1.0, not `None`.** Evidence: `run_bench` sets `teds_v = None` when the reference has no tables (`bench.py:223-227`) and `mhs_v = None` when the reference has no headings (`bench.py:228`); `overall` averages only eligible axes (`bench.py:238-243`). The default score path always calls `table_score` (returns **1.0** when neither side has tables, `bench.py:150-155`) and `mhs` (returns **1.0** when both lack headings, `metrics.py:690-691`), then `ref_overall = (ref_nid + ref_teds + ref_mhs) / 3.0` (`score.py:212-215`). `WhiskerResult.ref_teds`/`ref_mhs` are typed `float | None` (`score.py:79-80`) but are never set to `None` when the oracle runs. Impact: sidecar `ref_overall` and terminal `ovr=` lines (`report.py:72-77`) use a **different overall formula** than `BenchRow.overall`; table-less/heading-less oracle pairs look artificially high on informational axes even though `_decide` never hard-fails on them (`score.py:175-178`).

- [HIGH] **`whisker bench --baseline` reads leaderboard JSON with no `schema_version` or shape contract.** Evidence: guard rejects stale baselines via `_validate_baseline` (`guard.py:251-271`, schema must equal `WHISKER_SCHEMA_VERSION = 3`, `constants.py:166`); bench `--baseline` only does `base["aggregate"]["overall"]` with bare `json.loads` (`__main__.py:328-340`), no schema check. Stale on-disk `data/whisker/report.json` at schema **1** while code is schema **3** (`00` §3b). Impact: CI can diff against a pre-null-eligibility leaderboard and get a meaningless regression signal, or silently accept wrong-shaped files until `KeyError`.

- [MED] **Region detail contract is split: full counts, capped lists — easy for programmatic consumers to misread.** Evidence: `missing_region_count` / `extra_region_count` use `len(content.missing_regions)` (`score.py:244-245`); `missing_regions` / `extra_regions` lists are capped at `REGION_DETAIL_CAP` (`score.py:218-223`, `constants.py:150`). Tests assert the cap explicitly (`test_score.py:273-279`) but not that count can exceed list length. Impact: a sidecar consumer treating `missing_regions` as exhaustive will under-locate content gaps; only the count field is complete.

- [MED] **Public docstrings contradict the verdict contract (oracle is advisory, not primary).** Evidence: `WhiskerResult` field comment says ref fields "are the primary verdict signal" (`score.py:74-76`); `score_markdown` docstring says reference agreement "drives the verdict" (`score.py:198-200`). `_decide` uses only `ref_nid` as one **soft** flag and never hard-fails on reference (`score.py:175-178`); hard fails are gates + unigram floor only (`score.py:152-160`). Impact: API readers and downstream integrators will wire oracle `ref_overall` into pass/fail logic the code explicitly forbids.

- [MED] **`aggregate([])` mixes null-ineligible and numeric-zero empty sentinels.** Evidence: empty input returns `teds`/`mhs`/`grits_con` as **`None`** but `nid`/`overall`/`content_recall`/`reading_order` as **`0.0`** (`bench.py:265-273`); covered by `test_bench.py:60-62,128-131`. Impact: unlike per-row null-eligibility (GT lacks modality), empty-corpus callers must special-case two different "no data" encodings; averaging code that treats `None` as skip and `0.0` as measured will skew empty-run dashboards.

- [MED] **Sidecar path derivation diverges under `--report-dir`.** Evidence: default path uses `sidecar_path` → `md_path.stem + ".whisker.json"` preserving store casing (`score.py:307-314`); `--report-dir` writes `f"{pid.lower()}.whisker.json"` (`__main__.py:233-236`). Impact: the same paper gets different sidecar filenames depending on CLI flags; tools that derive paths via `sidecar_path()` will miss `--report-dir` outputs.

- [LOW] **`score_markdown(..., content=...)` accepts an untyped `content` blob.** Evidence: parameter has no type annotation (`score.py:191`); tests use `SimpleNamespace` mimicking `ContentCheckResult` fields (`test_score.py:46-68`). Impact: library callers get no static or runtime schema for the hardest fused input; a missing `unigram_drift` attribute fails late inside `_decide`.

- [LOW] **`__init__.py` is re-export-only (invariant holds).** Evidence: `__init__.py:10-106` — imports, `__all__`, `__version__` only; no logic. `score.py`, `bench.py`, `gates.py` perform no filesystem writes (grep clean). Persistence confined to `__main__.py:227-247,321,400,451,...`. Impact: positive — "library returns data, CLI persists" is enforced in practice.

## False-pass hypothesis

A conversion with **oracle on** where markitdown and tomd both lack tables/headings: `ref_teds=1.0`, `ref_mhs=1.0`, `ref_overall` inflated (`score.py:212-215`), `ref_nid` above the advisory edge, unigram ≥ 0.85, gates green → **pass** with headline `ovr=` suggesting strong cross-converter agreement (`report.py:72-77`) even though two informational axes are **ineligible zeros masquerading as perfect** under bench rules (`bench.py:223-228`). Verdict tier is still structurally correct (reference never hard-fails), but the **reported agreement contract lies**.

## False-fail hypothesis

**P3941R2/R3/R4** pattern from `00` §3c: `uni=0.999`, `drift=0.001`, **fail solely** on `heading_monotone` (`gates.py:105-109`; 9/14 ref-free hard fails are this gate, `00` §3a). API contract is consistent here — `GateResult` surfaces in `WhiskerResult.gates` and `hard_flags` (`score.py:152-154`) — but a consumer trusting `verdict` alone without reading `gates` gets a false "broken content" signal on an otherwise green metrics row.

## What would change my mind

A **schema-3 sidecar fixture test** showing `score_paper` with `--no-reference` vs oracle on the same table-less paper: `ref_teds`/`ref_mhs` serialize as JSON **`null`** (not `1.0`), `ref_overall` matches the eligible-axis mean used in `run_bench`, and `whisker bench --baseline` **rejects** a schema-1 leaderboard with the same hard error guard uses — demonstrating one null-eligibility story across score, bench, and artifact read paths.
