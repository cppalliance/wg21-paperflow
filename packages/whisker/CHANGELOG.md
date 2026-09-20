# whisker changelog

All notable changes to the `whisker` QA + benchmark package. Schema version
refers to `WHISKER_SCHEMA_VERSION`, the stamp on every whisker artifact (sidecar,
report, bench leaderboard, guard baseline, calibration).

## 2026-09-18: truncated_leak typed question names poll captions as prose (issue #426)

`_LANE_VERSION` 24 -> 25. No schema bump, no det change, no `rules.toml`
change (the `per-unit-count-dump` probe text "leaked rows or prose?" still
holds). The unit-probe question is not part of `prompt_sha256`, so the bump
is what re-evaluates incremental sidecars.

### Fixed

- **`llm/table_probes.py` `_build_truncated_leak_question`.** The closed
  question now states that a short `Label: value` caption directly under
  the table (`Result: Consensus`, `Outcome: No consensus`) is prose, and
  that `leaked rows` is the answer whenever the text carries cell values
  that belong in the table's columns, even if it names a meeting, a date or
  a poll (the exemption is the caption shape, not the vocabulary; a
  `Meeting | Date | Outcome` table's leaked `Wrocław 2024-11-20 Forwarded`
  row stays a leak). det `_is_truncated_leak` (frozen) flags a filled
  `SF | F | N | A | SA` poll grid whose single numeric body row is followed
  by `Result: Consensus`; on P3290R4 that is all five polls (T1-T5). Since
  v24 no source grid pairs them (20 page-layout pseudo-grids, `no pairing`),
  so the typed answer decides; it decided `prose` already, the rubric now
  says why. The signature text in `llm.md` records the non-signature.
- **`llm/table_probes.py` `_estimate_line_after`.** Matched the first line
  equal to the header text. Five identical poll headers sent every later
  poll's lookahead (the 4-6 prose lines the model is shown) to the first
  poll's trailing prose. Now requires the unit's body rows under the header
  (separator skipped unless `has_separator` is False, the outer-pipe run
  without a separator line) and falls back to the first header hit. Same
  arithmetic (header + separator + body rows) otherwise. Residue, marked
  `shortcut:` in the function: two byte-identical tables both resolve to
  the first; det's `_PipeScan.line_after` knows the exact value but
  `table_units_from_markdown` (frozen) drops it.
- **Not changed.** T8 (bibliography smashed into a 4-col table,
  `header_is_data`) is source-confirmed (`glue` on textlayer page 19) and
  stays a DEFECT until tomd stops claiming it (#426 part 1). Controls
  P0876R23, P3596R0, N5040 carry only `aligned` units, which never see the
  question.

## 2026-09-18: unit-dump grid pairing skips pseudo-header source grids (issue #425)

`_LANE_VERSION` 23 -> 24. No schema bump, no prompt change, no det change.
Evidence lane only: fused verdicts do not read unit dumps, but sidecars carry
`DEFECT` stamps that this change withdraws, so incremental runs re-evaluate.

### Fixed

- **`llm/table_compare.py` pseudo-header rules.** `extract_pdf_table_grids`
  now returns `SourceGrid(page, rows, pseudo_header)`. Row 0 of a grid is
  pseudo when a word's x-span reaches into two cells (`_header_words_straddle`,
  the `strategy="text"` column gaps fall inside prose words: `Of Operati | on
  Stat`, `Docume | nt Number:`, `Revision | History`), when fewer than
  `_MIN_ALPHABETIC_HEADER_CELLS` (2) cells carry a letter (`} | |`,
  `// For free functions`, `21 | PROPOSAL`), when a cell ends in one of
  `_CODE_TAIL_CHARS` (`{};=[`: `const auto | a = [`, `nothrow = see below;`)
  or starts a `//` comment, or when the joined row reads `document number`
  (`Document | Number: | P4007R0`). The flag rides on
  `TableGridMatch.source_pseudo`; `grid_match_for_unit` skips such matches
  in both the header-overlap and the column-count pass. `_match_tables` and
  the score-0 pairing are untouched (a T5 wrong header has zero overlap with
  the source header by definition; `test_t5_row0_mismatch`,
  `test_pairs_t5_by_candidate_header` unchanged), and
  `TableCompareResult.matches` still lists every grid for the risk-signal
  consumers (`pdf_judge`).
- **Why.** `_match_tables` paired a same-width pseudo-grid with a real
  markdown table at header score 0; that match carried a measured
  `row0_mismatch`, and `resolve_source_typed_probe` held the det class
  against the model's `prose` (P3373R2 T0-T2 `truncated_leak`, P4003R0 T1
  `truncated_leak`, T3/T5-T7 `header_is_data` via `} | |`). Fleet audit
  2026-09-18 (189 PDF+MD pairs, 532 units): 188 pairings fall to
  `unreliable`, every one of the 82 distinct source headers a pseudo-grid;
  0 units gain a signal; 28 units keep `row0_mismatch` but re-pair to the
  next same-width grid (P4127R0 T0/T4/T5 to the real `Mechanism | ...`
  table, P3100R6 to page grids the rules miss: `ntime-checkable: | Yes`,
  `fy [basic.stc...]`, cut at the grid's outer edge); 2 units (P3596R2
  T8/T11, aligned) move from `row0_mismatch` to `extra_or_missing_rows` on a
  header-token overlap with `Category | UB stable name`. Kept: P4127R0 T1
  (`Mechanism | Delivers to operator new? | Reduces`), P4182R1 T5/T11
  (`Field | Value`), N5040 T2 (`54 | US 75-138 20.3.2.2
  [util.smartptr.shared] | Accepted`, the reason `]` is not a code tail).
- **`llm/inspect_report.py` `_format_unit_dumps`.** A det-flagged unit with
  `passed=False, defect_confirmed=False, skipped=False` renders `ABSTAIN`
  with its own counter (`abstain=N`), not `FAIL`; `FAIL` stays for aligned
  units whose source verdict was not `match` and for transport errors.
  Sidecar fields (`passed`, `defect_confirmed`, `fail_count`) unchanged.
- **`table_probes.resolve_source_typed_probe(grid_note=...)`.** The abstain
  reason names why the grid is unreliable via
  `table_compare.grid_pairing_note`: `(no source grids)`, `(no pairing, N
  pseudo-grids excluded)` or `(no pairing)`. Without a note the string is
  the v23 one.
- Not covered: page grids whose row 0 is whole-word prose (`A.1 | Example
  Algorithm | Specification`, TOC lines) or cut only at the grid's outer edge
  (`ntime-checkable:`); an outer-edge rule is unsafe because PyMuPDF clips
  real tables the same way (N5040 G12 `(` protrudes 1.8pt). P4016R0 T12
  `header_is_data` stays grid-kept by `A.1 | Example Algorithm |
  Specification` (unchanged from v23).

## 2026-09-18: unit-dump grid pairing skips candidate-less source grids (issue #424)

`_LANE_VERSION` 22 -> 23. No schema bump, no prompt change. Evidence lane
only: fused verdicts do not read unit dumps, but 37 sidecars carry a
`DEFECT` stamp that this change withdraws, so incremental runs re-evaluate.

### Fixed

- **`llm/table_compare.py` `grid_match_for_unit`.** Source grids that found
  no markdown candidate (`candidate_header is None`) are no longer pairing
  candidates for a unit. `_match_from_grids` sets `row0_mismatch=True` on
  such a match to mean "no candidate", and `resolve_source_typed_probe`
  read that synthetic flag as a measured header mismatch (reject-and-keep);
  the same match also supplied the "PDF source header row" quoted into the
  `header_is_data` / `wording_clause` typed question. On WG21 PDFs
  `find_tables(strategy="text")` emits page-layout pseudo-grids (title block
  `D | ocument Number:`, running header `P3978R0 | 1 Changelog`) that never
  pair with a table; a one-letter substring hit (`N` in `ocument Number:`)
  was enough to pair a poll unit with one. Fleet audit before the change:
  all 40 `truncated_leak` DEFECTs and 58 of 70 `header_is_data` DEFECTs
  were grid-kept, and the LLM had answered `prose` on every one of the 40.
  After: 37 candidate-less pairings (all pseudo-grids on inspection) fall
  to `unreliable` and the typed answer decides; all 40 pairings with a real
  candidate keep their signal. Control papers P0876R23, P3596R0, N5040 have
  only `aligned` units, which never consult the grid signal. Motivation:
  P3978R0's three faithful empty poll forms (blank ballot in the PDF, blank
  body row in the markdown) were stamped `truncated_leak DEFECT` over the
  model's `prose`.
- Not covered, separate calibration: a pseudo-grid that `_match_tables`
  pairs with a same-width markdown table at header score 0 carries a
  measured `row0_mismatch` (P3373R2-R4 `Of Operati | on Stat | es and`) and
  still confirms `truncated_leak`. Raising that pairing threshold would drop
  T5 wrong-header detection (a wrong GFM header has zero overlap with the
  source header by definition).

## 2026-09-16: code-boundary source font evidence (issue #413)

`_LANE_VERSION` 21 -> 22. No schema bump.

### Added

- **`src/whisker/llm/fence_fonts.py`.** Per-fence source font evidence for
  the tapetum `code_boundary` judge. `fence_font_evidence` reads the PDF
  font layer (shared `det.pdf_geometry` loader) and classifies each fence
  body line as monospace-set, proportional-set or unmatched; the CB user
  message gains a `SOURCE FONT EVIDENCE` block and the prompt declares it
  authoritative for C9 `prose_in_fence`. `clamp_source_monospace` rewrites
  a surviving `prose_in_fence` finding on a monospace-set source line to
  `clean` (reasoning `source-monospace clamp: monospace in PDF`, sidecar
  key `source_monospace_clamped`). Abstains on non-PDF, unreadable or
  monospace-free sources. Motivation: P4016R0 data literals and
  ASCII-diagram captions were C9-flagged although monospace in the PDF.

## 2026-09-07: lane restructure (det/ + llm/ + shared root)

Source-tree restructure only. No behavior change: CLI verbs, console script
names (`whisker`, `whisker-tapetum-llm`, `whisker-readback`), the
`tapetum-llm` extra, exit codes, sidecar filenames, and the
`WG21_DATA_DIR/whisker/det|llm` artifact layout are all unchanged. No schema
bump, no `_LANE_VERSION` bump.

### Changed

- **`src/whisker/det/` (new).** The 21 deterministic modules plus `compare/`
  and `llm_readability/` moved under `det/`; the deterministic verb bodies
  were extracted from `__main__.py` into `det/cli.py`.
- **`src/whisker/tapetum_llm/` renamed to `src/whisker/llm/`.** Python
  package only: the tapetum brand stays in the console script, the extra,
  and the sidecar filenames. The authority doc `tapetum_llm.md` is now
  `llm/llm.md`.
- **Shared root.** `constants.py`, `metrics.py`, `tables.py`, `facts.py`,
  `gates.py`, `golden_ideals.py` stay at the package root (exactly the
  modules the LLM lane imports), joined by the new `cli_common.py` (shared
  CLI helpers), `menu.py`, and a slim dispatcher `__main__.py`. `survey/`
  and `branding/` stay top-level.
- **Tests mirror the lanes**: `tests/det/`, `tests/llm/`, and `tests/` root
  (shared modules plus the cross-lane contract guards).
- **Research reorg**: topic dirs and loose reports moved to
  `research/research/`, plans to `research/plans/`; `research/repos/` and
  `research/.gitignore` stay at the research root.
- Import-linter contracts updated (`whisker.llm` as the forbidden module,
  `whisker.det.*` and `whisker.cli_common` in `source_modules`). The one-way
  rule is unchanged: the core never imports `llm`, the lane imports the
  core read-only.

## 2026-09-04: tapetum-llm v21 verdict-stability hardening

`_LANE_VERSION` 20 -> 21. Verdict-relevant changes: all sidecars must be
re-evaluated.

### Changed

- **PDF `_fold_monolith_verdict` hardened.** A `fail` without at least one
  grounded `candidate_not_found` quote folds to `review`. Empty
  `missing_content` (independent structure concern) caps at `review`.
- **HTML corroboration rule.** A `fail` stays only when corroborated by a
  verified unit defect, metadata `fail`, or TOC clamp; otherwise `review`.
- **`SHORT_CIRCUIT_CONFIDENCE`** (`constants.py`, 0.01) replaces the
  `confidence=0.0` sentinel in the HTML metadata-first skip stub. The
  demotion was a no-op (the stub verdict is already review/fail) but 0.0
  polluted stability measurements.
- **Metadata date rule.** `METADATA_CHECK_SYSTEM_PROMPT` now instructs the
  model that a missing date on either side is not a mismatch. Deterministic
  post-check in `run_metadata_outline_check` corrects `date_matches=False`
  when either side lacks a date (matches `metadata_compare._date_matches`).
- **PDF outline guard.** Metadata `fail` demoted to `review` when
  `source_outline <= 1` entries and title/doc match (sparse outline cannot
  credibly claim missing sections).
- **Retry footer.** Per-cause breakdown (`parse N, truncated N, transient N`)
  with per-retry DEBUG log line including the call label. Backend warnings
  in `pipeline.model_backends` now include the label.

## 2026-09-04: tapetum-llm --trace, event-loop probes, constant guard tag

Advisory lane only. No `_LANE_VERSION` bump: prompts and judge logic are
unchanged; the guard tag already differed between runs before this change.

### Fixed

- `--trace` writes per-paper traces for both lanes with phase durations; previously a silent no-op.
- Readability probes (`build_llm_readability_block`, sync httpx) run via
  `asyncio.to_thread` in both lanes instead of blocking the event loop that
  serves the other in-flight papers.

### Changed

- **Constant `GUARD_TAG`** (`constants.py`) replaces the per-run HMAC tag in
  the PDF lane and the random per-context tag in the HTML lane (which never
  received a tag, so its metadata and unit calls used a fresh random tag per
  call). Identical prompt bytes across papers (prefix-cache reuse of the
  shared system prompt) and across runs (stable-verdict measurement).
  `cli._paper_guard_tag` removed.

## 2026-09-03: tapetum-llm non-think pin (_LANE_VERSION 20)

Advisory lane only. `_LANE_VERSION` 19 -> 20: pin thinking off at every LLM
call site after the pod default flipped to thinking-on (probe 2026-09-03).

### Changed

- **`thinking_budget=0`** on ideal, judge, fast, and deep `AgentBackend`
  constructions (`cli.py`, `adjudicate.py`).
- **`chat_template_kwargs.enable_thinking=false`** on raw httpx probe payloads
  (`table_probes.py`, `code_probes.py`, `readback.py`).
- Removed dead `CONFIDENCE_DECISION_FLOOR` constant and superseded
  `table_probes._find_label_shift` / `_find_continuation` helpers.

## 2026-09-01: tapetum-llm fleet default c=16 + in-run retry wave

Advisory lane only. No schema bump, no `_LANE_VERSION` bump (prompts and
judge logic are unchanged).

### Changed

- **`_DEFAULT_CONCURRENCY` 32 -> 16** (`tapetum_llm/cli.py`). Matches the
  pod's `--max-num-seqs 16` so the waitlist lives in the client semaphore.
  Queue wait against `wait_for` budgets plus the RunPod ~100s idle kill
  produced 62 error tombstones on the 2026-08-27 `--force --inspect` fleet
  (issue 401). `_MAX_TESTED_CONCURRENCY` stays 32 as the warning ceiling.
- **In-run retry wave.** After the main gather, this-run errors
  (`verdict_str is None`) are re-adjudicated at concurrency 16 for up to 2
  rounds before the counts fold, footer, and merged report. Prior-run
  tombstones stay skipped unless `--retry-errors` is passed.

## 2026-08-25: Prune and placement refactor

Deterministic/LLM boundary housekeeping. No behavioral change to any scoring
path, lane, or CLI verb (except the removed `qa review`). Import-linter
contracts expanded from 19 to 30 guarded modules.

### Removed

- **`payload_scope.py`** (tapetum_llm) trashed with its test. The module was
  implemented and tested but never wired into production.
- **`qa review` verb** (`qa_cli.py`) and its backing functions
  `review_ideal`, `_claude_runner`, `download_source` in `golden_qa.py`.
  `generate_ideal` now fails closed (`FileNotFoundError`) if no source is
  staged locally. `_cmd_add` prints an error instead of downloading.
- **R13 certification code** stripped from `table_probes.py` (1895 to 1326
  lines): `run_probes`, `make_table_probe_check`, `score_aligned_dump`,
  `ProbeRunResult`, and 10 R13 helpers. Trashed to
  `_trash/table_probes_r13.py`. The unit-dumps surface (`run_unit_dumps`,
  `unit_dumps_to_dict`) and all its scorers are unchanged.

### Moved

- **`toc_leak.py`** from `whisker/` to `whisker/tapetum_llm/`. The module is
  deterministic code whose sole consumer is the advisory LLM lane. Imports in
  `adjudicate.py`, `pdf_judge.py`, and `test_toc_leak.py` updated.
- **`calibration_sampler.py`** and **`golden_labels.py`** (plus their tests)
  from `src/whisker/` and `tests/` to `packages/whisker/corpus/calibration/`
  as standalone siblings. They are calibration-workflow tooling, not core
  library modules. `_draw_coverage_sample.py` and the tests use `sys.path`
  sibling imports. `PROTOCOL.md` updated.

### Changed

- **`build_table_readability_block`** renamed to **`build_llm_readability_block`**
  in `unit_judge.py`, `adjudicate.py`, `pdf_judge.py`, and
  `test_tapetum_llm.py`. Persisted JSON keys (`llm_readability`,
  `table_readability`, `table_contract`) are unchanged.
- **Import-linter contracts** (`pyproject.toml`) expanded from 19 to 30
  guarded source modules. New entries: `golden`, `golden_compare`,
  `golden_gaps`, `golden_qa`, `qa_cli`, `corpus_tools`, `delta`,
  `probe_strength`, and subpackages `branding`, `compare`, `survey`.
  Both contracts pass (148 files, 701 dependencies).
- **CLAUDE.md** updated: `golden_qa.py` and `qa_cli.py` module descriptions
  reflect the stripped functions and removed verb.

### Tests

- 286 tests passed for `test_table_probes.py` and `test_tapetum_llm.py` after
  R13 strip. 55 tests passed for `test_golden_qa.py` and `test_qa_cli.py`
  after the `golden_qa` strip. 29 tests passed for the relocated calibration
  modules.

## 2026-08-18: Table-probe reject-and-keep (T5/T7)

Typed fallback can no longer clear a det `header_is_data` / `truncated_leak`
when DeepSeek answers `match` then `column headers`. `compare_pdf_tables`
runs once per paper in `run_unit_dumps`; a `row0_mismatch` or
`extra_or_missing_rows` grid signal keeps the det class. `wrap_orphan` typed
veto (T0) is unchanged. Advisory only; not a certification.

### Tests

- `tests/test_table_compare.py`: T5/T7/T0 grid-pair signals.
- `tests/test_table_probes.py`: `resolve_source_typed_probe` reject-and-keep.

## 2026-08-10: Dead-import purge (CI ruff green)

Removed all dead imports, dead locals, and dead symbols across the whisker
package so `uv run ruff check packages tests` passes cleanly.

### Removed

- 46 unused imports (F401) across src, tests, benchmark, and research scripts.
- 1 dead local variable (`old_pattern` in `survey/adapters/marker.py`, F841).
- 1 placeholders-free f-string (`readback.py:550`, F541).
- `RunData` dead dataclass in `survey/runner.py` (zero references, no ADR).
- `UNIT_SCOPE_SOFT_CHARS` stray import from `payload_scope.py` (the constant
  definition stays with an ADR-004 comment: planned soft-cap, not yet wired).

### Fixed

- **F821 `registry` undefined** in `test_survey_install.py`: the lambda
  referenced a bare `registry` that was never imported. Fixed to
  `cli.registry.get_competitor(...)`, which also resolved the coupled
  "cli unused" F401 on the same function.
- **E741 ambiguous variable `l`** in a benchmark pilot render tool: renamed
  to `line`.

### Changed

- Added `[tool.ruff] extend-exclude = ["packages/whisker/research/repos"]` to
  the root pyproject.toml so local ruff stops dying on the broken third-party
  `PDF-Extract-Kit/pyproject.toml` (untracked vendored clone absent from CI).
- Refreshed `research/repos/README.md` manifest with 11 missing vendored
  clones (deepeval, langextract, litellm, marker-v1.10.2, marker-v2.0.0,
  mineru-vl-utils, promptfoo, ragas, sglang, unstructured-ingest, vllm).

### Tests

- Suite: 2230 passed, 9 skipped, 3 xfailed.

## 2026-08-10: Menu freshness prompt, result pause, first-run delta message

Operator-facing cleanup after the delta work landed. No behavior change to any
lane, only to how the menu asks and how a missing baseline is reported.

### Changed

- **The warm/cold choice is now one named prompt.** Options (2) and (3) ask
  `Run mode?` with `warm` (fingerprint skip on, the default), `cold`
  (`--force`), and `preview` (`--would-skip`), each with a one-line
  explanation printed above the prompt (`_TAPETUM_MODES`,
  `_prompt_tapetum_mode`). Previously the flag ladder had grown one y/n per
  capability until option (3) asked seven questions and option (2) asked
  nine, with the freshness decision buried as `Force re-evaluation of
  unchanged papers?` at position two. The words "warm" and "cold" appeared
  nowhere in the menu, so the switch the README documents was unfindable from
  the interface. Common path is now two questions.
- **Diagnostics moved behind one gate.** `--retry-errors`, `--debug`, and
  `--trace` are asked only after `Advanced options?` (default no,
  `_prompt_tapetum_advanced`). `--inspect` rides along on warm and cold
  without a prompt (it was already defaulted to yes and only writes
  `tapetum-inspect.md`); preview omits it because it returns before
  adjudicating. The `--review-all` arm asks no mode, since `--force` is
  ignored there.
- **Option (1) states why it has no switch.** The deterministic lane rescores
  from scratch and has no cache, so it prints that instead of offering a
  freshness choice it cannot honor.
- **The menu pauses on a result.** `run_menu` waits for Enter before
  redrawing (`_pause`), so a delta or fleet report is readable instead of
  scrolling away behind the redrawn menu. EOF and interrupt are swallowed so
  a non-interactive stdin falls through rather than raising out of the loop.
- **A missing delta baseline reads as a first run, not an errno.** Both delta
  paths catch `FileNotFoundError` ahead of `OSError` and explain that the
  snapshot is written when the *next* run overwrites the current report, so
  it exists from the second run onward (`_log_missing_baseline`,
  `_log_missing_current`). Previously a correct first-run state surfaced as
  `[Errno 2] No such file or directory`, which reads like a defect. Exit
  code is unchanged at 1.

### Tests

- 13 new menu tests: mode-to-flag mapping for all three modes, preview
  excluding `--inspect`, every mode being explained before the prompt, the
  scope fork asking or skipping the mode prompt, the advanced gate not
  falling into the ladder when declined, and `_pause` surviving both EOF and
  KeyboardInterrupt. The prompt layer had no tests at all before, which is
  why the flag ladder could accumulate unnoticed.
- Suite: 2230 passed, 9 skipped, 3 xfailed.

## 2026-08-09: LLM-lane delta (report-merged.prev.json + whisker delta --llm)

LLM-lane before/after comparison, mirroring the deterministic delta that
landed earlier today.

### Added

- **`report-merged.prev.json` snapshot.** The tapetum CLI now copies
  `report-merged.json` to `report-merged.prev.json` before overwriting on
  full runs and `--fuse-only`, following the same pattern as the det lane's
  `report.prev.json`.
- **`whisker delta --llm`.** Compares `report-merged.json` against its
  previous snapshot. Renders two sections: the deterministic verdict tier
  (`det` field) plus the `unigram` metric, then LLM verdict tier movers
  (`llm`/`suggested_verdict`) separately, flagged as possible judge noise
  because single-run LLM judge flip rates are documented at 25% or higher.
  Replayed (warm-skipped) rows are counted as unchanged by construction.
  **Exit codes are 0 or 1 only: this view renders, it never gates**
  (see "Why the LLM-lane delta does not gate" below). `--json` emits
  `det_delta`, `llm_advisory_movers`, `replayed_count`, and `stale`; a
  consumer wanting the deterministic movement without a gate reads
  `det_delta.any_regressed`.
- **`compute_delta` generalized.** Accepts optional `verdict_field`,
  `watched_metrics`, `results_key`, and `verdict_sentinels` parameters. The
  det caller uses unchanged defaults; the LLM caller passes
  `verdict_field="det"`, `watched_metrics=("unigram",)`, `results_key=None`
  (bare list), and the merged report's two sentinels.
- **`verdict_sentinels`: the missing-sidecar false-regression guard.**
  `build_merged_json` defaults a missing or malformed whisker sidecar to
  `det: "?"` and its coverage to `unigram: 0.0` (`fusion_report._verdict`,
  `_safe_float(..., 0.0)`), and a paper with no tapetum data to `llm: "-"`.
  Neither marker is a verdict tier, but `_rank` maps any unrecognized string
  to the review rank, so a paper whose det sidecar vanished between runs
  read as `pass -> "?"`: an exit-3 regression that never happened, carrying
  a fabricated `unigram 0.98 -> 0.0000`. The reverse, `fail -> "?"`, read as
  an improvement and retired a real failure from the report. A row carrying
  a sentinel on either side is now classified `unchanged` with reason
  `not comparable`, withholding the whole row (verdict and metrics both,
  since the metrics are equally synthetic) rather than only its verdict.
  This mirrors the pre-existing null-metric doctrine. `None` is a legal
  sentinel and the LLM caller passes it, covering a row that omits the
  verdict field outright rather than spelling its absence as a marker. The
  det lane passes no sentinels and is behaviorally unchanged: `score.py`
  only ever emits pass/review/fail.
- **Menu (6) Delta** now prompts `det | llm | both`. Selecting `both`
  renders both reports sequentially; an operational failure in either lane
  outranks a verdict code, so a regression exit cannot mask a lane that
  never produced a comparison at all.

### Changed

- **Why the LLM-lane delta does not gate.** An earlier draft of this feature
  had `--llm` exit 3 on a deterministic regression, on the reasoning that the
  `det` column is deterministic data and so gating on it is not "the LLM
  gating." The column is indeed honest: `build_merged_json` re-derives `det`
  from the live `whisker/det/<pid>.whisker.json` sidecar on every rebuild, so
  it is never a stale cached value. The defect is the sampling interval, not
  the value. `whisker delta` compares consecutive `whisker --all` runs;
  `whisker delta --llm` compares consecutive aggregate rebuilds, and the
  aggregate is rebuilt only by a full LLM run or `--fuse-only`. The two axes
  drift apart in both directions, so gating both is wrong either way:
  - `whisker --all` with no tapetum run afterwards moves `report.json` and
    leaves the aggregate untouched. `whisker delta` exits 3, `--llm` exits 0.
    A gate here would have reported clean while a real regression existed.
  - `whisker --all` twice, then a late `--fuse-only`: the det lane has already
    absorbed the change into `report.prev.json`, so `whisker delta` is clean
    while the aggregate only now picks the move up. A gate here would have
    failed a build for a regression the authoritative gate no longer reports.

  One authoritative emitter per signal: `whisker delta` owns deterministic
  regression gating because it reads the artifact whose baseline moves in
  lockstep with it. The det section stays rendered here because the movement
  is worth seeing, with a pointer line to `whisker delta` printed whenever it
  shows a regression, since exit 0 beside a rendered "regressed" section is
  otherwise confusing.
- **`_llm_report_is_stale` watches det sidecars too.** It compared the
  aggregate's mtime only against `*.whisker.tapetum.json`, which made it blind
  to exactly the drift above: a bare `whisker --all` freezes the aggregate's
  `det` column while no tapetum sidecar moves, and the probe called that
  fresh. It now takes an optional det directory and globs `*.whisker.json`
  there as well (the two patterns cannot collide, so a flat `--report-dir`
  holding both lanes is safe). Of the two columns this is the more important
  one to flag, because `det` is the column a reader is most likely to mistake
  for authoritative.
- README "After a tomd change" runbook updated with LLM delta step (5).
- README command reference for `whisker delta` updated with `--llm` docs,
  including the `--json` payload shape per lane and the non-gating rationale.
- Menu (6) scope prompt now labels which scope gates.

### Tests

- `uv run --package whisker pytest packages/whisker/tests`: 2217 passed, 9
  skipped, 3 xfailed (baseline 2183). `tests/test_delta.py` grew to 64 tests.
  Seven pin the missing-det-sidecar class: `pass -> "?"` is not a regression,
  `fail -> "?"` is not an improvement, `"?" -> pass` is not an improvement, a
  row missing `det` entirely (`None`) is not a regression, a sentinel row does
  not mask a real regression on another paper, `compute_delta` withholds the
  whole sentinel row, and the det lane without sentinels keeps ranking unknown
  verdicts as before. Four cover `_snapshot_prev_merged_report`, previously
  untested despite being the seam that produces every `--llm` baseline: no-op
  on first run, copy without touching the live aggregate, overwrite of a prior
  snapshot, and a round trip whose snapshot `whisker delta --llm` reads back
  clean. One more mirrors the absent-marker filter onto the curr side
  (`pass -> "-"` is coverage loss, not judge disagreement). Four pin the
  widened staleness probe, including the one that names the old blind spot
  directly: same fixture, `_llm_report_is_stale(llm_dir)` false and
  `_llm_report_is_stale(llm_dir, det_dir)` true. Two pin the non-gating exit
  contract: a rendered det regression exits 0 and prints the pointer line, and
  a clean run omits it.

## 2026-08-09: whisker delta verb, tapetum --would-skip, fingerprint gap closure (_LANE_VERSION 12)

Det-lane run-to-run comparison, plus tapetum warm-run visibility and a
one-time fingerprint fix.

### Added

- **`whisker delta` verb (`delta.py`, `_delta_main`).** Compares the previous
  deterministic run against the current one: sections regressed / improved /
  new / gone / unchanged, worst-first within each. Verdict ordering
  (`pass` < `review` < `fail`) is primary; an unchanged verdict falls back to
  the watched metrics (`unigram_coverage`, `coverage`, `qa_score`, `ref_nid`)
  with epsilon `DELTA_METRIC_EPSILON` (0.01). Flags: `--baseline PATH`,
  `--report-dir`, `--workspace`, `--json`. Exit codes: 0 clean, 3 any
  regression, 1 operational error. The det lane (`_score_main`) now
  snapshots `report.json` to `report.prev.json`
  (`_snapshot_prev_report`) before every overwrite, giving `delta` a stable
  baseline with no extra operator step.
- **`whisker-tapetum-llm --would-skip`.** Dry-run flag: resolves the paper
  set and prints the exact fingerprint skip decision each paper would get
  (`run`, `skip (fingerprint match)`, `skip (superset: MODE)`,
  `skip (tombstone)`), with no LLM call, no health probe, and no sidecar or
  report write.
- **Skip visibility.** A fingerprint skip on a live run now logs at INFO
  (previously buried at debug level in batch mode), and the batch footer
  reports a breakdown instead of a bare count: `N skipped (incremental: X
  fingerprint, Y superset, Z tombstone)`.
- **Sidecar `evaluated_at` (schema_version 9).** Every tapetum sidecar
  carries a UTC ISO 8601 timestamp, set only on an actual evaluation, never
  on a fingerprint skip.
- **Merged-report `replayed` marker.** `report-merged.md`/`.json` rows now
  state whether the LLM result is a warm-skip carryover from a previous run
  (`_is_replayed`, `build_merged_json`) rather than freshly evaluated this
  run.
- **Fusion refresh on fingerprint skip (`_refresh_fusion_on_skip`).** A
  fingerprint skip reuses the tapetum sidecar's LLM verdict unchanged but
  recomputes its fusion block against the CURRENT deterministic sidecar,
  deterministically and with zero LLM calls, so a skip never pairs a stale
  fusion with a fresher det verdict.

### Changed

- **Fingerprint gap closure, `_LANE_VERSION` 11 -> 12.** The fingerprint now
  also covers the `UnitCheckClear`/`UnitCheckDefects` verdict-first schemas
  (dispatched to the LLM but never previously hashed) and a new
  `unit_check_mode` key tracking the `TAPETUM_VERDICT_FIRST` toggle. This is
  a one-time cache invalidation: every paper re-evaluates once on the next
  warm run after upgrading, then resumes normal incremental skip.
- **Menu integration (`menu.py`).** New menu item (6) "Delta". The tapetum
  "all" scope prompt gained "Retry error tombstones?" and "Preview only
  (list would-skip decisions, no LLM calls)?" prompts, appending
  `--retry-errors` / `--would-skip`. Item (3)'s description now states the
  warm/fingerprint-skip semantics explicitly instead of "auto-skip".

### Tests

- `uv run --package whisker pytest packages/whisker/tests`: 2183 passed, 9
  skipped, 3 xfailed (no change to package behavior tested by this pass;
  menu and docs only).

## Calibration tooling: P16 fit/holdout compliance, blind-labeling sampler, promotion policy

Tooling and policy prep for the eventual real calibration run. No real
calibration has been run yet: the labeled corpus is 9 papers, far short of the
30-50 target, so `UNIGRAM_COVERAGE_FAIL_EDGE`/`UNIGRAM_COVERAGE_REVIEW_EDGE`
in `constants.py` remain PROVISIONAL.

### Added

- **Fit/holdout calibration (`calibrate.py`).** `calibrate_threshold_with_holdout`
  selects tau on the `"calibration"` split only and reports TPR/FPR/precision
  once on the never-touched `"holdout"` split (P16 2.2). Two distinct FPR
  ceilings replace the old single `DEFAULT_TARGET_FPR`:
  `DEFAULT_TARGET_FPR_FAIL_EDGE = 0.05` (the fail edge, where a false positive
  wrongly hard-fails a good paper) and `DEFAULT_TARGET_FPR_REVIEW_EDGE = 0.10`
  (the review edge, a cheaper, recoverable error). An underpowered-data guard,
  `InsufficientCalibrationDataError`, fires below
  `MIN_SAMPLES_PER_CLASS_PER_SPLIT = 5` per class per split. A deterministic
  bootstrap holdout band, `bootstrap_holdout_band`, and a new
  `CALIBRATION_ARTIFACT_SCHEMA_VERSION`, independent of
  `WHISKER_SCHEMA_VERSION`, round out the module.
- **`whisker calibrate` P16 §2.7 provenance (`__main__.py`).** The fitted-
  thresholds artifact now carries `labels_file_sha256`,
  `calibration_timestamp`, and `calibrator_version`. `--labels` requires a
  frozen `split` field (`"calibration"`/`"holdout"`) per record; the old bare
  `{pid: label}` mapping is no longer accepted. The old single `--target-fpr`
  flag is replaced by `--fail-target-fpr` (default 0.05) and
  `--review-target-fpr` (default 0.10).
- **Deterministic calibration sampler (`calibration_sampler.py`).**
  `sample_calibration_candidates` performs deterministic stratified sampling
  over the scored corpus; `build_blind_worksheet` generates a labeling
  worksheet that never leaks whisker's own verdict or score to the labeler
  (anti-circularity).
- **Calibration operating policy (`corpus/calibration/PROTOCOL.md`).**
  Documents the P16 criteria this tooling satisfies: asymmetric FPR ceilings,
  class definitions, the blindness rule, frozen split assignment, the target
  N=30-50 vs today's actual N=9, recalibration triggers, the C-LAB/M2
  consequence on promotion, and holdout-corpus separation, backed by a new
  `tests/test_calibration_consistency.py` guard enforcing all-or-nothing
  promotion into `constants.py`.

### Tests

- `tests/test_calibrate.py` + `tests/test_calibration_sampler.py`: 50 passed.

## Phase 6: D6 least-privilege proof and impossibility disclosure, D7 import-linter contract in CI

D6 (untrusted-input defense) and D7 (API contract and packaging) were both
at level 3 with narrow, mechanically closable gaps to level 4. Together the
two are worth +4.50 composite points.

### Added

- **Hermetic injection corpus (`tests/test_injection_corpus.py`).** Five
  payload classes driven by a named table and parametrized via pytest: direct
  instruction override, forged envelope close, forged SYSTEM line, nested
  delimiter, and alt-text payload. Each calls the real
  `pipeline.tools.inject_untrusted` (not a mock) and asserts the envelope is
  intact, the payload is fully contained inside the delimited region, and any
  forged delimiter in the payload is escaped. Skips cleanly when the
  `tapetum-llm` extra is not installed.
- **Zero-tool guard (`tests/test_tool_privilege.py`).** AST scan of every
  `.py` file under `tapetum_llm/` asserting no `@tool` decorator, no
  `FunctionTool()` constructor, no non-empty `tools=` kwarg, and no
  `parallel_tool_calls=True` (project rule D4). Driven by a named
  `_BANNED_PATTERNS` set so the guard is extensible.
- **Trust-boundary inventory and impossibility disclosure (`README.md`).**
  New section per OWASP LLM01 / NIST 3.4.4 / audit criterion S8. States that
  prompt injection cannot be fully eliminated, inventories the five layered
  controls (source segregation, structured output, zero tool exposure,
  deterministic firewall / `FUSION_RULE_LLM_REVIEW_CAP`, output caps), then
  discloses what live testing (E15) proved and did not prove: injections did
  not flip the verdict, but the PDF lane is a loss detector, not an addition
  detector, so fabricated content is structurally invisible; both injection
  variants reported confidence 1.0, the value the payload demanded.
- **`py.typed` marker (PEP 561).** New empty marker file at
  `src/whisker/py.typed`, force-included in the wheel via
  `pyproject.toml`. Closes D7 subcriterion (b): "py.typed if typed API
  claimed". No `py.typed` existed anywhere under `packages/` before this.
- **Import-linter contracts (`pyproject.toml` at repo root).** Two forbidden
  contracts measured and verified before committing:
  - *Deterministic core must not import the advisory LLM lane.* 19 core
    modules (`score`, `metrics`, `match`, `gates`, `report`, `bench`,
    `constants`, and 12 more) are forbidden from importing
    `whisker.tapetum_llm`. This is the invariant that keeps the advisory lane
    from reaching the deterministic verdict.
  - *Deterministic core must not import the pipeline framework.* Same 19
    modules forbidden from importing `pipeline`. Today `pipeline` appears
    only under `tapetum_llm/`, matching the optional-extra declaration.
  Both contracts analyzed 132 files and 562 dependencies and passed (KEPT).
- **`lint-imports` in CI (`.github/workflows/tests.yml`).** Added to the
  lint job alongside `ruff check`. The sync step now uses `--all-extras` so
  grimp can see `tapetum_llm/` modules even though they live behind an
  optional extra.

### Tests

- `tests/test_injection_corpus.py`: 5 parametrized payload classes, plus a
  dedicated forged-delimiter-rewrite assertion.
- `tests/test_tool_privilege.py`: parametrized per `.py` file under
  `tapetum_llm/`, reports exact file and line on any violation.
- Full package suite: 1934 passed, 8 skipped, 3 xfailed, zero failures.

## Phase 3 canary teeth: inverted canaries, a platform-independent holdout lock, and a readback control that can fail

The G6 audit gate fails when an inverted canary passes, and Auditv3 found four
that did. Two are answered here. The permuted-document canary was already
closed by `FUSION_RULE_LLM_REVIEW_CAP`, and the punctuation-corruption canary
(CR1) provably cannot be answered in the deterministic scoring lane: the
fleet-wide separation measurement in
`research/Audit/Auditv4/signal-separation-measurement.md` showed clean-fleet
p95 punctuation divergence sits an order of magnitude above every mutation, so
no threshold exists that catches the corruption without failing the fleet. The
teeth for that class therefore live in the Lane 3 comprehension corpus, which
compares the raw surface and can see an operator flip.

Alongside that, two controls that could not fail: the holdout fingerprint lock
had drifted stale and its hash was line-ending dependent, and
`whisker-readback --corrupt` exited 0 no matter what it found.

### Added

- **Three hermetic inverted canaries (`tests/test_comprehension_corpus.py`).**
  Each corrupts the committed `corpus/<pid>.expected.md` in memory and asserts
  a specific pre-existing `checked: verified` fact catches it, by id, so a
  canary that fails for the wrong reason still fails the test.
  `test_canary_arrow_operator_corruption_fails` flips `pf1->resume();` to
  `pf1.resume();` on P0876R23, the load-bearing CR1 case the scoring lane is
  blind to. `test_canary_semicolon_punctuation_corruption_fails` swaps a
  terminating `;` for `,` on P4234R0's raw-surface fact.
  `test_canary_permuted_headings_fails` swaps two heading texts on N5040 while
  leaving the bodies in place, caught by an `order` fact. N5040 and P0876R23
  had no canary at all before this.
- **Canary coverage meta-tests.** `test_canary_coverage_matrix_complete` drives
  off named module-level maps `_REQUIRED_CANARY_CLASSES` (corruption class ->
  canary function) and `_EXCLUDED_CANARY_CLASSES` (documented gap -> reason),
  asserting no class is both covered and excluded, every covering entry
  resolves to a real callable, and every exclusion carries a reason.
  `test_canary_paper_coverage_complete` pins one canary per corpus paper.
  Renaming or deleting a canary now goes red instead of silently removing
  teeth.
- **`_sha256_candidate_text` and `_sha256_source_bytes`
  (`tests/test_dev_replay_schema.py`).** Split by artifact kind rather than one
  shared helper, because the two must not be confused: candidates are markdown
  and are hashed as UTF-8 text with `\r\n` and lone `\r` normalized to `\n`, so
  the fingerprint is identical on CRLF and LF checkouts; sources are binary
  PDFs and stay raw-byte hashed.
- **`test_candidate_fingerprint_tripwire_detects_content_drift`.** Proves the
  lock still bites after re-pinning: appends a line to an in-memory copy of
  each real candidate and asserts the hash no longer matches the pinned value,
  then re-encodes identical content with the opposite line ending and asserts
  the hash is unchanged.
- **`--corrupt-banner` (`readback_cli.py`), off by default.** The priming
  banner is now opt-in, and `ReadbackResult.banner_applied` records what
  actually happened. Both `render_terminal` and `render_markdown` state whether
  it was applied, so a banner-assisted run cannot be mistaken for the
  unconfounded control.

### Fixed

- **The holdout lock was line-ending dependent (H5 audit finding).** The
  p4182r0 candidate fingerprint had been failing since PR #311 (commit
  `b7d3d48`, 2026-07-31) corrected two heading levels in the blessed ideal
  after the 2026-07-17 lock. This was a stale lock, not a scoring regression:
  all anchor dispositions for all three locked papers (18, 16, 14) were
  re-verified against the current files and matched their
  `expected_candidate_status` before any hash was touched, and the source PDF
  hash was never in question. All three `candidate_sha256` values were
  recomputed under the normalized method and `manifest.json` gained a
  `fingerprint_method` field plus a `repinned` provenance map recording why
  each was changed, so the re-pin is auditable rather than silent. p4182r0
  stays an active, non-quarantined holdout member. Worth noting what the old
  scheme was hiding: two of the three candidates happened to be committed CRLF
  and so matched by luck, while p4182r0 is LF. The lock would have flipped its
  verdict on a Linux checkout.
- **`whisker-readback` could not fail (H2 audit finding).** `main` returned 0
  whenever at least one paper ran, regardless of failure count, which makes a
  negative control decorative. `_readback_exit_code` now returns typed codes,
  and corrupt mode inverts the expectation because that is what an adversarial
  control means:

  | Mode | All checks pass | At least one fails | Operational error |
  |---|---|---|---|
  | clean | `EXIT_OK` | `EXIT_FAIL` | `EXIT_ERROR` |
  | `--corrupt` | `EXIT_FAIL`, inverted canary passed | `EXIT_OK`, corruption caught | `EXIT_ERROR` |

  `EXIT_FAIL` rather than `EXIT_REVIEW` for both failing branches: a
  comprehension miss and a toothless canary are both definite defects, not
  ambiguous states. `EXIT_ERROR` stays reserved for no corpus, workspace, key,
  or papers.

### Known gap, recorded rather than papered over

Reference-qualifier corruption (`T&&` vs `T&`) has no canary. No
`checked: verified` fact in the 37-fact corpus asserts text containing a
reference-qualifier token, and blessing a fact to `verified` is a manual human
step the tooling must never perform on its own. Rather than inventing a
fixture to close the matrix, the class is registered in
`_EXCLUDED_CANARY_CLASSES` with that reason, so it is visible in the coverage
meta-test instead of merely missing.

### Tests

- `tests/test_comprehension_corpus.py`: three new canaries plus two coverage
  meta-tests, existing three canaries untouched.
- `tests/test_readback.py`: banner-neutrality plus every exit-code branch
  (clean pass and fail, corrupt caught and missed, operational error), all
  mocking the `_ask_pod` boundary. No pod is contacted.
- `tests/test_dev_replay_schema.py`: the fingerprint tripwire test above.
- Full package suite: 1899 passed, 8 skipped, 3 xfailed, zero failures. This
  clears the holdout failure the suite had been carrying.

## Phase 2a null-eligibility: reading_order and the ideal-lane availability status (schema 7 -> 8)

Two truth defects. First: `match.block_metrics` reported `reading_order=0.0`
on the matrix-budget fallback, which reads as "perfect order" when reading
order was never measured at all. Second (M1 audit): an installed whisker with
no ideals checkout reports every `ideal_*` field as `null`, indistinguishable
from a checkout that legitimately found no ideal for that paper. Both close a
gap between "we measured this and it's clean" and "we could not measure this".

### Added

- **`IDEAL_STATUS_UNAVAILABLE` / `IDEAL_STATUS_ABSENT` / `IDEAL_STATUS_PRESENT`
  (`golden_ideals.py`).** Named status constants distinguishing WHY a paper's
  `ideal_*` panel is empty: the ideals checkout is unreachable in this
  environment (`UNAVAILABLE`, e.g. an installed wheel with no workspace
  checkout on disk) vs the checkout is reachable but this pid has no ideal yet
  (`ABSENT`) vs an ideal was found and scored (`PRESENT`).
- **`resolve_ideal(pid, ideals_dir) -> (ideal_md, status)` (`golden_ideals.py`).**
  Pure function centralizing the three-way resolution above. `score_paper` now
  calls it instead of inlining the discovery-and-read logic, and it is
  independently unit-testable with no backend (see tests).
- **`WhiskerResult.ideal_status: str | None` (`score.py`).** New sidecar field,
  always emitted in `to_dict()`. `score_paper` passes the status
  `resolve_ideal` computed; `score_markdown` accepts an explicit
  `ideal_status` override for tests and defaults to `IDEAL_STATUS_PRESENT`
  when `ideal_md` was given, else `IDEAL_STATUS_UNAVAILABLE` (the
  backend-free core cannot otherwise distinguish "unreachable" from
  "reachable but absent").
- **`report.py` leaderboard "ideal" column** now renders `unavailable` instead
  of the generic `-` when `ideal_status == IDEAL_STATUS_UNAVAILABLE`, so a
  reader scanning `report.md` can tell "this environment has no ideals lane
  at all" from "checked, this paper has none" without opening a sidecar.
- **`BlockMetrics.reading_order: float | None` (`match.py`).** On the
  matrix-budget fallback (`len(gt_blocks) * len(pred_blocks) >
  BLOCK_MATRIX_CELL_BUDGET`), `reading_order` is now `None` (not measured)
  instead of a synthetic `0.0`. The both-empty and no-match cases are
  unchanged: those `0.0`s are genuine measurements (vacuous perfect agreement,
  measured disagreement), not fallbacks.
- **`BenchRow.reading_order: float | None` (`bench.py`).** Mirrors the
  `teds`/`mhs` null-eligibility pattern: `to_dict()` emits JSON `null` when
  unmeasured, `aggregate()` computes an eligibility-weighted mean (`None`
  when zero rows are eligible) with a new `eligible_counts["reading_order"]`
  denominator, and the empty-rows shortcut now returns `reading_order: None`
  to match.

### Tests

- **`tests/test_match.py`.** `test_reading_order_none_on_budget_fallback`
  forces the fallback with enough tiny paragraphs that
  `gt_blocks * pred_blocks > BLOCK_MATRIX_CELL_BUDGET` and asserts
  `reading_order is None` while `nid` stays a real float.
  `test_reading_order_still_zero_on_small_identical_docs` guards the normal
  path (small docs keep the genuinely-measured `0.0`).
- **`tests/test_bench.py`.** `test_reading_order_none_on_budget_fallback`,
  `test_aggregate_reading_order_eligibility_weighted` (mixed
  eligible/ineligible rows, mean over the eligible row only),
  `test_aggregate_reading_order_mean_is_none_when_all_ineligible`, and
  `test_aggregate_empty_has_reading_order`. The budget-exceed cases
  monkeypatch `BLOCK_MATRIX_CELL_BUDGET` to `0` rather than constructing a
  giant corpus, since the fallback branch is a cheap short-circuit
  independent of document size.
- **`tests/test_golden_ideals.py`.** `test_resolve_ideal_unavailable_when_dir_missing`,
  `test_resolve_ideal_absent_when_pid_missing`,
  `test_resolve_ideal_present_when_file_exists` unit-test the pure resolver.
  `test_no_ideal_leaves_fields_none` and the perfect-panel test now also
  assert `ideal_status`; `test_score_markdown_ideal_status_absent_explicit`
  covers the explicit-override path; `test_report_md_distinguishes_unavailable_from_absent`
  proves the leaderboard column difference.

### Schema

- **Bump 7 -> 8.** Both changes follow the same precedent already set in this
  file: the schema was bumped at 2 -> 3 for introducing null-eligibility on
  `teds`/`mhs`, and at 3 -> 4 for the purely-additive golden-ideal panel
  fields. `reading_order` gaining null-eligibility is a value-shape change on
  an existing field (a consumer that assumed "always a float" now sees
  `null` on the budget-fallback path), the same class of change as the
  teds/mhs precedent; `ideal_status` is a new field on `WhiskerResult`, the
  same class of change as the ideal-panel precedent. A stale guard baseline
  at schema 7 hard-fails (`_validate_baseline`) and must be regenerated with
  `whisker guard --update`. `score.py::_decide` and `guard.py`'s
  `GUARD_REGRESSION_AXES` needed no changes: `_decide` already guarded
  `reading_order is not None`, and `reading_order` was never a member of
  `GUARD_REGRESSION_AXES` (advisory, never gated). `FUSION_SCHEMA_VERSION`
  (tapetum_llm) is untouched; this PR does not touch `tapetum_llm/`.

## Fusion review cap on primary-verdict disagreement (audit finding M2)

Closes audit finding M2 (evidence E19/E32): `fuse_verdicts` could report
`combined_verdict: "pass"` on a record whose primary `tapetum_verdict` was
`"review"`, or `"fail"` without a major-severity axis finding, because only
the fail+major-axis case (`llm_escalate_major`) and the schema-v6/ideal caps
had an upward channel to `review`. No schema bump; additive (see Schema).

### Added

- **`FUSION_RULE_LLM_REVIEW_CAP` (`tapetum_llm/constants.py`).** New fusion
  rule alongside `FUSION_RULE_SOURCE_AWARE_REVIEW_CAP` and
  `FUSION_RULE_IDEAL_REVIEW_CAP`: caps `det=pass` at `review` whenever the
  primary `suggested_verdict` is anything other than `pass` and no more
  specific cap already fired. Placed after `llm_escalate_major` inside the
  `det == VERDICT_PASS` branch of `fuse_verdicts` (`tapetum_llm/fusion.py`),
  so the more specific fail+major-axis rule reports its own reason first and
  is never shadowed by the generic cap. Demote-only: it can only move a
  non-fail merge to `review`, never to `fail`, and never touches `det=fail`.
- **Fusion matrix docstring (`fusion.py:15-32`)** updated to document the new
  cap, keeping the module docstring in sync with the implemented behaviour.
- **Inspect report (`tapetum_llm/inspect_report.py`)** now shows the fusion
  block's own `tapetum_verdict` directly beside `combined_verdict` on the
  `**Fusion verdict:**` line, so a reader does not need to correlate it with
  the separate whisker-vs-tapetum line above. `report-merged.md`'s
  `det | llm | merged` columns and `render_terminal_fusion_line` already
  rendered the primary verdict beside the merged one; unchanged.
- **Tests (`tests/test_fusion.py`).** New coverage for `det=pass` against
  `llm=review`, `llm=fail` with no axis findings, `llm=pass` (unchanged,
  proves the lane is not trigger-happy), the specific rule ordering against
  `llm_escalate_major`, and a gate-G1 regression proving an adversarial
  all-clear advisory (`llm=pass`, confidence 1.0) still leaves a
  deterministic `fail` at `fail`. `test_escalate_ignores_non_major_fail`
  (renamed `test_escalate_ignores_non_major_fail_but_review_cap_still_fires`)
  now asserts the corrected `review` outcome instead of the pre-fix `pass`.
- **Fleet impact measurement.** Replayed old vs. new fusion logic offline
  over all 381 papers with both a deterministic and a tapetum sidecar in the
  local workspace: 19 papers change `combined_verdict`, all `pass -> review`
  (P3181R1, P3440R2, P3865R1, P3865R2, P3962R0, P3973R0, P3985R0, P4010R1,
  P4015R0, P4025R2, P4136R0, P4151R1, P4174R0, P4205R0, P4211R0, P4212R0,
  P4220R0, P4230R0, P4233R0), 0 in the other direction. No `pass -> fail` or
  `fail -> anything` changes, confirming the demote-only ratchet held.

### Schema

- **No bump.** `FusionResult.to_dict()`'s field set is unchanged; only a new
  value for the existing free-text `combined_rule` field was added, the same
  precedent as every prior additive rule (`llm_rescue_heading`,
  `llm_escalate_major`, `source_aware_review_cap`, `ideal_review_cap`), none
  of which bumped `FUSION_SCHEMA_VERSION`. A bump is reserved for structural
  field additions/removals (e.g. the 3 -> 4 bump for the ideal-verifier
  fields), not new enum-like string values on an existing field.

## Benchmark accuracy: closing the Marker blind spots (schema 6 -> 7)

The 2026-08 pilot benchmark proved that a green Whisker run did not prove
correctness. Marker scored 8/8 on Lane 3 and lost only 9 NID points while
producing 0 of 112 code fences and destroying 466 C++ identifiers via `\_`
escaping. This release closes the three blind spots the pilot exposed.

### Added

- **`canonical.py`.** Convention-level canonicalization for fair block-agreement
  comparison. Symmetrically removes `:::wording` fenced-div lines,
  `<ins>`/`<del>` edit markup, and leading heading section numbers (arabic and
  roman) from both candidate and reference, so the comparison measures
  conversion quality, not markup dialect. Neither tomd nor the ideals change.
- **`structural.py`.** Structural marker counts (nine classes: `code_fence`,
  `inline_code`, `indented_code`, `heading`, `table_row`, `empty_table_row`,
  `image`, `escaped_underscore`, `list_item`) for cheap, deterministic
  conversion triage. Ported from `benchmark/tools/structural_sweep.py`.
- **`probe_strength.py`.** Probe-strength mutilators (`strip_all_structure`,
  `shuffle_sections`, `keep_fraction`) for Lane-3 fact-set quality assurance.
  Ported from `benchmark/tools/probe_fact_strength.py`. A new test gate
  rejects any fact set that still passes at 1.0 under `structure_stripped` or
  `keep_10pct`.
- **Three new advisory axes in `BenchRow`** (reported and stored, never folded
  into `overall`):
  - `block_agreement`: exact block-pair match share on convention-canonicalized
    text. Separates tomd from Marker by a factor of ~4.5, vs ~1.1 for NID.
  - `structural_parity`: per marker-class zero-vs-many parity. 1.0 = no
    categorical marker loss. Promoted to a hard gate on labeled GT in bench and
    guard.
  - `heading_level_parity`: fraction of positionally aligned headings whose
    levels match. Catches the MHS level-blindness (uniform level shift is an
    isomorphic tree, so MHS = 1.0) without modifying MHS or churning baselines.
- **Ideal panel extended.** `IdealPanel` and `WhiskerResult` carry the three new
  axes as advisory soft flags, consistent with the existing ideal-panel doctrine.
- **Fact corpus hardened.** Every benchmark paper now has an `absent` fact on
  `\_` (surface `raw`), catching Marker's F2 backslash-escaping defect directly.
  Papers with code fences carry at least one `code` fact with an
  underscore-containing identifier. `p1068r11` gains `table` facts on its poll
  tables. `p4182r0` gains `table` facts on its platform capability matrices.
- **Proof test.** `test_marker_proof.py` verifies that Marker output from the
  2026-08 pilot run falls on `structural_parity` while tomd does not, and that
  `nid`/`mhs` remain bitwise deterministic (no algorithm change).
- **Probe-strength gate test.** `test_probe_strength.py` verifies every corpus
  fact set measurably degrades under `structure_stripped` and `keep_10pct`.

### Changed

- **`benchmark/tools/score_v2.py`** now persists all `BenchRow` metrics (via
  `to_dict()`) and writes the structural sweep into `scores.json`.
- **`benchmark/tools/structural_sweep.py`** and **`corrected_agreement.py`**
  import from the core modules, eliminating duplicate regex definitions.
- **`structural_parity`** is a hard gate in `bench` (papers below 1.0 appear in
  `below_floor`) and in `guard` (via `GUARD_REGRESSION_AXES`). Floor calibrated
  exclusively from dev-replay papers (p1068r11, p2040r0, p3556r0), never from
  the holdout (p4182r0).

### Schema

- **6 -> 7.** Sidecars/reports carry `block_agreement`, `structural_parity`, and
  `heading_level_parity`. Guard baselines at schema 6 require regeneration.

## Code-fence boundary alignment (schema 5 -> 6)

Closes the second token-preserving structural blind spot after paragraph
boundaries. A prose line swallowed into a fence or a code listing left unfenced
moves no token, so coverage, drift, punct recall and the LLM lane all stay
green. Nothing in whisker or tomd's QA checked fences against the source font
geometry: `qa.py unfenced_code_lines` is markdown-only by design,
`golden_compare._code_axis` compares against a blessed ideal only, and
`no_empty_code` only finds empty fence pairs.

### Added

- **`pdf_geometry.py`.** Shared PDF geometry extraction for source-aware
  structural checks. Owns `PdfLine`, `load_pdf_lines`, `body_font_size`, and
  `is_monospace_line`. Both `paragraph_align` and `code_fence_align` import
  from here (was private in `paragraph_align`).
- **`code_fence_align.py`.** Deterministic PDF-font comparison of source
  monospace classification against candidate fence boundaries, no LLM.
  `compare_code_fence_boundaries(source_path, candidate_md) -> CodeFenceAlignment`.
  Two directions: `prose_in_fence` (fenced line matched a non-monospaced PDF
  line), `code_outside_fence` (a run of >= 3 consecutive monospaced PDF lines
  appeared outside any fence). Abstains when the source is not a PDF, has no
  monospaced font, or matches are ambiguous.
- **Score path.** `score_paper` computes the panel from the staged source;
  `score_markdown` takes it precomputed (like `paragraph`). Sidecars gain
  `fence_status`, `fence_prose_in_fence_count`, and
  `fence_code_outside_fence_count`. `score-file --source` mirrors the signal
  and emits a full `fence_alignment` block.
- **Soft flag only.** `code fence boundary mismatch: N prose line(s) inside
  fence, M code line(s) outside fence (advisory)`. Never hard, same rationale
  as the paragraph signal.

### Fixed

- **Monospace detection in `paragraph_align._is_body`.** The original check
  `"Courier" in font` missed cmtt, lmtt, Consolas, Menlo and other monospace
  families used in LaTeX-generated WG21 PDFs. Replaced with tomd's public
  `classify_monospace(font_name)` via the new `pdf_geometry.is_monospace_line`.

### Validation

9 synthetic tests: clean fences (no findings), prose swallowed into fence
(Direction 1 positive control), code left outside fence (Direction 2 positive
control), short mono run below threshold (no false fire), cmtt font correctly
classified (monospace bug regression), HTML unsupported, unreadable source
abstains, no monospace font abstains, front matter excluded. All pass. One
available PDF golden (p4182r0) produced zero findings as expected.

## Paragraph-boundary alignment (schema 4 -> 5)

Closes a structural blind spot that let a real defect through a full review.
Every source-aware signal whisker had was token-based, so a candidate that
drops a paragraph break moves no token: coverage, drift, punct recall and the
advisory LLM lane all stay green. On PR #284 (p0957r8) an all-pages LLM run
covering 33/33 pages returned `pass` at 0.98 over two destroyed source
paragraphs, the second high-confidence clear on that paper.

### Added

- **`paragraph_align.py`.** Deterministic PDF-geometry comparison of source
  paragraph starts against candidate paragraph blocks, no LLM.
  `compare_paragraph_boundaries(source_path, candidate_md) -> ParagraphAlignment`.
  Detects one of two conventions per document and abstains when neither is
  identifiable. Two naive detectors were built, measured and rejected first:
  ranking indent clusters by frequency picks p0957r8's wording-block indent
  (x0=75.0, 123 lines) over the real paragraph indent (x0=62.5, 109 lines), so
  ranking is by ISOLATION (0.67 against 0.00) instead; and measuring vertical
  gaps from bbox tops lets a 7pt footnote superscript fake a break (p3556r0:
  15.57 against an 11.96 leading, two false positives on an already-blessed
  golden), so gaps are measured baseline to baseline.
- **Score path.** `score_paper` computes the panel from the staged source;
  `score_markdown` takes it precomputed (like `content`) and stays
  filesystem-free. Sidecars gain `paragraph_status`, `paragraph_convention`
  and `paragraph_merged_count`. `score-file --source` mirrors the signal and
  emits a full `paragraph_alignment` block.
- **Soft flag only.** `N source paragraph break(s) missing from the candidate
  (advisory)`. Never hard: tomd flattens paragraph structure by design, and
  hard-gating a structural axis over-failed twice before (`ref_nid`, shingle
  `coverage`). The golden-QA bless path is where it can legitimately bite.

### Fixed

- **`heading_drift` false positives on every numbered heading.** The secno
  strip was applied to source titles but not to candidate heading keys, and
  `_text_key` removes whitespace before `_SECNO_RE` can match, so `1 History`
  keyed as `history` on one side and `1history` on the other. Every numbered
  section reported as a missing heading. Normalization is now symmetric and
  happens before keying.

### Validation

Five PDF goldens plus the PR #284 before/after pair: 2 true positives (both
blockers, rediscovered with no hardcoded geometry), 0 false positives. The
four HTML goldens report `unsupported` and never flag.

## Golden-ideal panel (schema 3 -> 4)

Wires the tomd golden-QA ideals (upstream PR #257,
`packages/tomd/tests/fixtures/golden/ideals/`) into the deterministic lane as
human-blessed ground truth. Zero configuration: any new ideal that lands in
the directory is picked up on the next `whisker` run.

### Added

- **`golden_ideals.py`.** Auto-discovery of the ideals directory (walk up
  from the whisker source, cwd fallback), `ideal_path`/`list_ideal_stems`
  (stem-scanned, case-insensitive on every OS), and `score_against_ideal`
  computing the Lane-2 panel (nid, teds, mhs, content recall, overall) of a
  candidate against its ideal. teds/mhs follow bench null-eligibility: `None`
  when the ideal lacks the modality, excluded from `overall`, never a
  synthetic 1.0. Read-only file access into tomd's fixture tree; no
  tomd-private imports (package-boundary rule intact).
- **Score path.** `score_paper` auto-discovers the ideal per pid;
  `score_markdown` accepts `ideal_md`. `WhiskerResult` and the sidecar gain
  nullable `ideal_nid`/`ideal_teds`/`ideal_mhs`/`ideal_recall`/
  `ideal_overall`. `_decide` raises ADVISORY soft flags
  (`ideal <axis> ... (advisory)`) when an axis sits below its Lane-2 bench
  floor. The calibrated hard gate is untouched: an ideal can move a
  borderline pass to review, never to fail.
- **Reports.** `report.md` gains an `ideal` column plus a per-axis
  "Golden ideals" section; the terminal summary appends `idl=` for
  ideal-backed papers; the fusion (`report-merged`) table gains an `ideal`
  column.
- **Menu.** Corpus Lanes gains `(5) ideals`: deterministic scoring
  restricted to exactly the papers that have an ideal.

### Schema

- **3 -> 4.** Sidecars/reports carry the five nullable `ideal_*` fields and
  ideal-backed papers can pick up new advisory soft flags. Guard baselines
  at schema 3 hard-fail; regenerate with `whisker guard --update`.

## Red-team hardening pass (research/llm-readability-fixpath self-audit)

Closes the six weaknesses the 25-persona self-target research run
(`research/llm-readability-fixpath/`) found in the finished fix-path work.
Full rationale, verification evidence, and the golden-file outlook live in
`FIXPATH-REPORT.md`. No schema bump; additive.

### Fixed

- **Decoy-table fail-closed (`facts.py`, CRITICAL).** With a `table_heading`
  anchor, `_check_table` now requires EVERY occurrence of the target cell in
  heading-matching tables to satisfy the neighbor checks (fail-closed): a
  decoy table sharing the heading and contradicting the genuine row fails
  the fact instead of being shadowed by the genuine occurrence. Anchorless
  facts keep ANY-semantics (cell values legitimately repeat across unrelated
  tables). Canary `test_canary_decoy_table_all_occurrences` now asserts the
  decoy FAILS.
- **Readback sycophancy (`readback.py`, HIGH).** YES/NO checks
  (`present`/`code`/`xref`/`image_ref`) passed on a bare "YES". Now
  `_grounded_quote` requires the fact's needle in the answer (fuzzy within
  the fact's `max_diffs`, on the fact's own surface; for `image_ref` the
  `![...](...)` reference itself). `xref`/`image_ref` questions now request
  the quote explicitly. `absent` passes on NO but is flagged `weak` (a
  correct NO cites nothing) in terminal and markdown output.
- **Readback substring scoring (`readback.py`, HIGH).** Expected table cell
  "8" matched an answer containing "18". `_cell_value_in_answer` matches on
  alphanumeric word boundaries; "(8)" and "8," still match.
- **Stratum classifier fence-blindness (`corpus_tools.py`, MED).**
  `classify_paper` counted `$$...$$` inside code fences as display math
  (P4234R0's `$`-identifiers). `_strip_fenced_blocks` removes fenced content
  before the math regex, in `classify_paper` and `draft_facts_scaffold`.
- **Readback transport errors conflated with FAIL (`readback.py`, MED).**
  `httpx` timeouts now mark `ReadbackCheck.error`; ERROR checks render as
  `[!]`, are excluded from pass/fail counts, and the CLI summary reports
  them separately with a rerun hint.

### Added

- **Hermetic CI snapshots for wave 2.** `corpus/N5040.expected.md`,
  `corpus/P0876R23.expected.md`, `corpus/P4234R0.expected.md` committed; all
  5 corpus papers (37 verified facts) now gate in CI via
  `test_comprehension_corpus.py`. New code canary
  `test_canary_scrambled_code_fails` (scrambled P4234R0 asm-alias must fail),
  completing the canary set: table cell, math relation, code snippet.
- **`golden-hook:` anchor convention.** Four greppable comments
  (`rg -n "golden-hook:"`) mark where the future golden-file layer plugs in:
  `_check_table` (golden-grid compare), `tables.py` (span-aware grid model),
  `_corpus_pairs` in the CI gate (construct-isolated golden pairs), and the
  `golden` CLI verb (extend, never duplicate). See `FIXPATH-REPORT.md`.
- **`tests/test_readback.py`** (offline, no network): anti-sycophancy,
  word-boundary scoring, ERROR-state rendering, question-blindness tests.
- **Live readback rerun under the stricter scoring** (alliance-pod,
  2026-07-09, all 5 papers): 34 pass / 3 fail / 0 error of 37. The 3 fails
  are pod column-alignment misreads (advisory findings about the model, not
  the markdown; the deterministic gate passes all 37). Readback pass rates
  are not comparable across scoring versions: earlier 100% claims were made
  under the sycophancy-prone scorer.

## LLM-readability fix path (research/llm-readability Meta-E ranked path)

Hardens Lane 3 comprehension and the tapetum_llm advisory lane against the
false-pass classes found during the `research/llm-readability` audit. No
schema bump; additive.

### Fixed

- **#277 condition 1 (`adjudicate.py`).** A confident tapetum_llm `pass` whose
  evidence spans were emitted but ALL dropped by grounding (the model claimed
  evidence, none of it verified verbatim) now demotes to `review`. Previously
  only a non-`pass` verdict demoted on ungrounded evidence; a `pass` sailed
  through. Sanctioned empty-evidence passes (no `evidence_spans` at all) are
  untouched.
- **Vacuous-green gate (`__main__.py`).** `whisker facts` and `whisker guard`
  now FAIL (previously silently passed) when a paper's `.facts.jsonl` has zero
  `checked: verified` facts, mirroring the pre-existing pytest guard in
  `test_comprehension_corpus.py`. The summary line lists the vacuous PIDs and
  draft count.
- **Decoy-table false pass (`facts.py`).** A `table` fact's target cell value
  repeating across multiple tables with different neighbors previously
  first-match-won on whichever table the scanner reached first. Now, without
  an anchor, ALL occurrences are tried and the fact passes if ANY satisfies the
  neighbor checks; with the new optional `table_heading` field, only tables
  whose header row matches are searched.
- **HTML-table blindness (`facts.py`, new `tables.py`).** `table` facts only
  saw markdown pipe tables; tomd-emitted HTML `<table>` blocks (Tony tables,
  SPEC_TABLE, NB_BALLOT) were invisible. `tables.py` adds an HTML grid parser
  (stdlib `html.parser`) alongside the existing pipe scanner; both feed the
  same cell-neighbor check.
- **Math-scope lowercasing (`facts.py`).** `_math_surface` folded case and
  relational operators away, so `X >= Y` and `x <= y` compared equal. Now
  preserves case and relational symbols; LaTeX unicode-folding (`$...$` ->
  bare) is unchanged, and the existing P4185R0 corpus facts still pass.
- **Math-scope blind to display-math delimiters (`facts.py`).** Found live via
  `whisker-readback` against the alliance-pod (2026-07-08): `_math_surface`
  only folded `$...$`/`\(...\)` (the shared `metrics.textblock2unicode`
  inline-only scope), so a formula the pod correctly reproduced inside
  `\[...\]` display math, or across multiple lines
  (`\[\n x^{2k} \geq 0 \n\]`), compared unequal to the same formula written
  inline. `_fold_display_math_delims` rewrites `\[...\]` to `\(...\)` and
  flattens embedded newlines before folding, scoped to `_math_surface` only
  (the shared Lane 2 `nid` axis normalizer is untouched).
- **Math-scope blind to doubled LaTeX backslashes (`facts.py`).** Same
  `whisker-readback` run surfaced a second escaping variant: some formulas
  came back with every command backslash doubled (`\\text{rms}` instead of
  `\text{rms}`), which pylatexenc parses as a line-break command, leaving the
  command name as literal unfolded text. `_undouble_latex_backslashes`
  collapses `\\` immediately followed by a letter to `\` before folding;
  scoped to that pattern only, so a genuine LaTeX line break (followed by
  whitespace, `[...]`, or end of string) is never touched.
- **Duplicated pipe-table parser.** `facts.py` and `bench.py` each had their
  own pipe-table scanner. Unified into `tables.parse_pipe_tables` /
  `tables.split_pipe_cells`; both call sites now share one implementation.

### Added

- **`surface: "raw"` mode** for `present`/`absent`/`order` facts: whitespace-
  collapse only, preserving operators and case (default surface still folds to
  alnum-only via `normalized_text`). Lets a fact distinguish `x != y` from
  `x == y` and `C++` from `c++`.
- **Three new fact types**: `code` (raw-surface snippet presence, fence-
  aware), `xref` (raw-surface revision-sensitive paper reference like
  `[P1234R5]`), `image_ref` (`![...](...)` presence, optional path/alt
  match). Both `code` and `xref` are always raw-surface.
- **`auto_baseline_checks(md)`** (olmOCR BaselineTest pattern): zero-authoring
  structural sanity checks (non-empty alphanumeric content, no long repeated
  n-grams / mojibake). Standalone helper in `facts.py`, not yet wired into the
  `whisker facts` report.
- **`whisker-readback` CLI** (new console script, `tapetum-llm` extra). Blind
  LLM read-back: sends a fact-derived question per verified fact to the
  alliance-pod, renders PASS/FAIL per fact in the terminal, and writes
  `<pid>.readback.md` for human review. `--corrupt` runs an adversarial
  control (scrambled tables/operators/exponents) to prove the questions are
  sensitive to content, not answerable from prior knowledge. Never gates,
  never in CI. See `whisker.tapetum_llm.readback`.
  Verified live against the alliance-pod and the two-paper corpus
  (2026-07-08): P4182R0 8/8, P4185R0 8/9 (see Fixed, display-math delimiters,
  for the one bug this run surfaced and closed). Two CLI-only bugs found and
  fixed during that run: `_resolve_service` read SERVICES.toml through
  `pipeline.services.load_services()`, whose `ModelBackend` instances expose
  `base_url`/`api_key`/`model` as private attributes by design; it now parses
  SERVICES.toml directly (whisker-standalone, no `pipeline` import). Windows
  consoles default to cp1252 and raised `UnicodeEncodeError` on pod answers
  containing non-ASCII math/prose; `main()` now reconfigures stdout to UTF-8
  with `errors="replace"`.
- **Corpus wave 2 (2026-07-09): 2 -> 5 papers.** Selected via
  `whisker corpus stratify` over the 381 converted papers, one per
  underrepresented stratum: P4234R0 (`$` in identifiers; code fences with
  `$$` symbols, xref), N5040 (Croydon minutes; pipe AND HTML tables),
  P0876R23 (fiber_context; poll tables, code, xref). 20 new verified facts.
  Provenance: facts were drafted by `whisker corpus draft` and then verified
  by the agent against the ORIGINAL staged sources (P4234R0 HTML, N5040 and
  P0876R23 PDFs via pymupdf text extraction), not only against the converted
  markdown, at the user's direction (no human-in-the-loop for this wave).
  Each fact's needle was located verbatim in the original source before being
  marked `checked: verified`. Blind readback against the alliance-pod:
  P4234R0 6/6, P0876R23 8/8, N5040 6/6 (after the table-question phrasing
  fix below; one transient pod read-timeout on a first attempt).
- **Readback table-question phrasing (`readback.py`).** The table question
  embedded the expected neighbor values verbatim ("Specifically: right:
  N5031, heading: Meeting"), violating the Persona 22 blindness requirement
  the module documents, and phrased `heading` ambiguously (a live N5040 run
  answered the neighbor column's heading, "Minutes", instead of the target
  cell's column heading, "Meeting"). Questions now name only the directions
  ("the cell immediately right of X; the column heading of the column
  containing X") and never the expected values.
- **`whisker corpus` CLI** (`stratify` / `draft` subcommands). `stratify`
  classifies zero-fact-coverage papers by structural stratum (pipe/HTML
  tables, display math, code-heavy, footnotes, images) for representative
  sampling. `draft` generates a `checked: draft` `.facts.jsonl` scaffold per
  paper for human review and promotion to `verified`. See
  `whisker.corpus_tools`.

## tapetum_llm 0.1.0 - advisory LLM lane (opt-in)

A SEPARATE, opt-in advisory layer on top of the deterministic gate
(`whisker[tapetum-llm]`, `whisker-tapetum-llm` CLI). It gives a second opinion on
conversion fidelity for the false-pass blind spot (token-preserving semantic
corruption the order-blind token gate misses) and the false-fail blind spot
(cosmetic heading-monotone-only fails). Advisory only: it never hard-fails, is
never in `whisker --gate`, and never overwrites the whisker verdict on record.
The deterministic gate stays LLM-free and reproducible; full details in
`src/whisker/CLAUDE.md`.

### Added

- **Candidate selection** (`select_candidates`, no LLM): three populations,
  PRIMARY (pass-tier papers with gate-ignored risk signals), SECONDARY
  (non-benign review papers), RESCUE (`heading_monotone`-only fails).
- **Two-tier cascade**: a fast model triages every candidate; only a confidence
  inside the ambiguous band escalates to the deep model. Per-axis findings on
  seven fidelity axes; evidence grounded verbatim against the markdown.
- **Severity-aware worst-axis decide**: the overall verdict equals the worst
  axis, but an axis `fail` forces an overall `fail` only at severity `major`; a
  non-major `fail` (cosmetic, e.g. a heading-level jump) folds to `review`. This
  rescues the heading-monotone-only false-fail population instead of escalating a
  cosmetic defect to a hard fail.
- **Oversize handling**: papers above `MAX_PAPER_MD_CHARS` are split on H2
  boundaries, triaged serially (one in-flight request, deterministic), and folded
  (worst axis, minimum confidence, union of evidence). A section too large to read
  in full marks the read partial and can never become a clean `pass`. Fixes the
  `413 Payload Too Large` the largest papers (> 1 MB markdown) hit.
- **Sanctioned tomd markers**: the system prompt declares tomd's
  honest-uncertainty markers (`tomd:uncertain`, glyph placeholders,
  `tomd:vector-extraction-uncertain`) so the model does not flag them as defects.
- **Inspect report**: `whisker-tapetum-llm --inspect` writes a side-by-side
  whisker-vs-advisory report for human review.

### Availability

- The Alliance self-hosted pod runs 24/7, so the lane may run anytime; there is
  no hourly-cost rationing. Production targets open-weight self-hosted models
  (model-sovereignty); every call is serial and deterministic.

## 0.5.0 - scoring v2 (schema 3)

This is a coordinated scoring release. Several axes changed meaning at once so
the corpus is re-baselined a single time rather than once per change. After
upgrading, regenerate every committed guard baseline with `whisker guard
--update` and re-review the diff: a stale schema-2 baseline hard-fails on load
by design.

### Three-lane framing

whisker is now explicitly a three-lane regression system, and the three lanes
are deliberately NOT interchangeable:

- **Lane 1 Stability** (`whisker golden`): did the output change.
- **Lane 2 Fidelity** (`whisker bench` / `whisker guard`): is the output close
  to a reference (`nid`/`teds`/`mhs`). This release hardens it and adds
  `content_recall`.
- **Lane 3 Comprehension** (`whisker facts`): can an LLM still read it.

Fidelity is not comprehension. A reflow can score high on every Lane 2 axis and
still scramble a table cell or drop an exponent so a downstream LLM answers "row
3, column 2" wrong. Only Lane 3 catches that, and only it needs no perfect
golden file (a few source-verified facts suffice). This is the gap the two repo
audits found: across 28 converters only `olmocr` tests comprehension, and no
repo has an automatic "this file is 100% correct" oracle. All three lanes are
documented in `src/whisker/CLAUDE.md`.

### Added (Lane 3 comprehension, Phase D)

- **`facts.py` + `whisker facts` verb.** Deterministic, source-verified fact
  assertions over `<pid>.facts.jsonl`, adopted from olmocr; NO LLM in the
  scoring loop. Five assertion types: `present` / `absent` (fuzzy substring
  within a `max_diffs` edit budget via rapidfuzz alignment + an exact
  free-start/free-end substring DP), `order` (each item appears strictly after
  the previous), `table` (locate a cell, verify its `up`/`down`/`left`/`right`/
  `heading` neighbors, the direct "row 3, column 2" test), and `math` (presence
  on a LaTeX-folded surface that keeps `^`/`_`/`=` for a structural compare).
- **`checked: verified` provenance gate.** A fact gates ONLY when a human set
  `"checked": "verified"`; drafts are evaluated and reported but never fail the
  build. `whisker facts --strict` also gates drafts (for authoring). Macro-
  average pass-rate per assertion type in the report.
- **Conjunctive in `whisker guard`.** A failed verified fact is a hard fail even
  when the numeric slack holds, alongside the existing substring anchors.
- **Shared micro-corpus** under `packages/whisker/corpus/` (README + an
  `EXAMPLE.facts.jsonl` template). Lane 1 golden and Lane 3 facts run on the same
  `<pid>` members to amortize annotation cost.

### Changed (expect metric shifts, this is a correction not a regression)

- **Heading parsing via mistune AST.** `mhs` headings are now parsed from
  mistune's CommonMark AST (the same engine tomd QA uses) instead of an
  ATX-only line regex. Setext headings (`Title` over `=====`) now count, inline
  markup in heading text is flattened to prose (`## **Bold** [x](u)` ->
  `Bold x`), YAML front matter is stripped before parsing, and only top-level
  headings are collected (nested `> ##` / `- ##` skipped, matching tomd QA).
  **Impact:** `mhs` rises on papers whose GT used setext or rich inline heading
  markup (previously invisible or mismatched); unchanged on plain ATX corpora.
- **Null-axis eligibility for `teds` / `mhs`.** When the reference has no tables
  (`teds`) or no headings (`mhs`), the axis is recorded as `null`, not a
  synthetic `1.0`. `overall` is now the mean of the ELIGIBLE structural axes
  only (`nid` is always eligible), so a table-less / heading-less paper is no
  longer inflated toward `1.0`. Corpus means average only eligible rows and
  publish `eligible_counts`. The guard skips a `null` axis for both the floor
  and the regression check (a real NaN/inf is still `STATUS_INVALID`). Adopted
  from opendataloader-pdf. **Impact:** `mean_teds`, `mean_mhs`, and per-paper
  `overall` drop on table-sparse / heading-sparse corpora (honest correction).

### Added

- **`content_recall` axis.** Multiset bag-of-words recall of ground-truth
  content present in the candidate (`metrics.content_recall`), the Unstructured
  `cct-%missing` complement. It catches a dropped paragraph/section that
  block-matched `nid` hides on the surviving blocks. A first-class gate
  (`CONTENT_RECALL_FLOOR`, per-paper guard via `GUARD_REGRESSION_AXES`) but
  deliberately NOT folded into `overall` (Nougat/Unstructured keep missing-
  content strata separate). Order-invariant; extra/duplicate candidate words are
  not penalized (additive drift is a separate, score-path signal).
- `aggregate()` now reports `eligible_counts` (per-axis scored-row denominators).
- `BenchRow` gains `content_recall`; `teds`/`mhs` become `float | None`.
- **`grits_con` advisory table axis (Phase C).** GriTS-Con cell-content F1
  (`grits-metric`, MIT) over order-matched tables, a complementary signal to
  `teds` that catches localized cell / merge-split errors a tree-edit distance
  smooths over. ADVISORY only: stored and reported (per-row + corpus mean with
  its own `eligible_counts`) but never folded into `overall` and never gated,
  until it earns its own calibrated floor. `None` when the reference has no
  tables (same eligibility as `teds`).

### Dependencies

- **License fix: `levenshtein` (GPL-2.0) -> `rapidfuzz` (MIT).** All
  `.distance` call sites in `metrics.py` and `match.py` now use
  `rapidfuzz.distance.Levenshtein`. Score-identical to the old package for both
  strings and integer sequences (frozen parity vectors in
  `tests/test_edit_distance_parity.py`; the GPL import is lint-banned there).
  **Impact:** none on scores; removes the GPL dependency.
- **`mistune ~= 3.2.0` declared explicitly** (previously only transitive via
  `tomd`), pinned to tomd's version so the two bump together.
- **`grits-metric >= 0.6.0` (MIT)** added for the advisory `grits_con` axis
  (pulls `pylcs`, `pybind11`; deterministic, no LLM).

### Migration

1. Upgrade the package; the schema is now 3.
2. Run `whisker guard --update` on each corpus to regenerate baselines (now
   carrying `content_recall`, `null` ineligible axes, and recomputed `overall`).
3. Re-review the regenerated baseline diff: `mhs` may rise (setext/inline), and
   `teds`/`mhs`/`overall` may fall where the reference lacks the modality. Both
   are intended one-shot corrections, not converter regressions.

## 0.4.x - versioned baselines (schema 2)

- Guard baselines embed `tool_versions` (`tomd`/`whisker`); a mismatch
  hard-fails before any per-paper diff so a dependency bump cannot silently pass
  against wrong-era metrics. Schema bumped 1 -> 2.
- `mhs` tree edit distance moved from a hand-rolled Zhang-Shasha implementation
  to `apted` (the same engine as `teds`); parity-tested to leave scores
  unchanged.
- Golden Lane 1 (`whisker golden`) and per-paper substring anchors
  (`whisker guard` + `<pid>.anchors.json`) added.
