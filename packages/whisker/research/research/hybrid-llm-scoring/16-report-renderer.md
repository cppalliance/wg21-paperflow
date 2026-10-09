# 16 - Report Renderer

**Verdict:** usable-with-conditions (+ merged rendering is straightforward as a tapetum-owned artifact with det|llm|merged columns and a fusion-driven leaderboard, but whisker core `report.py` must stay tapetum-free per C2; do not let tapetum rewrite the deterministic `report.md` writer.)
**Confidence:** high

## Findings

- [CRITICAL] **C2 blocks merged columns inside whisker `report.py`.** `render_report_md` is a pure `WhiskerResult` renderer with a fixed 12-column PID-sorted table (`report.py:98-122`); whisker `__main__` persists it as `report.md` (`__main__.py:254-255`). tapetum_llm already owns a separate join renderer in `inspect_report.py:45-146` and persists `tapetum-inspect.md` (`cli.py:231-243`). Core must never import tapetum (`00-baseline.md:39`). Impact: goal 3 needs a **third artifact** (`report-merged.md` + `report-merged.json`) written only from `tapetum_llm`, not an edit to `packages/whisker/src/whisker/report.py`.
- [HIGH] **Extend the table pattern, not the whisker table.** Reuse `_MARK` verdict tokens and `_cell` null rendering (`report.py:26`, `report.py:112-113`) in a new `tapetum_llm/fusion_report.py`. Proposed header (10 columns, fits ~120-col terminal without wrapping flags):

  `| PID | det | llm | merged | δ | conf | unigram | overall | flags |`

  - `det` = whisker `verdict` (on record, C1).
  - `llm` = tapetum `suggested_verdict`, or `-` when sidecar absent (measured on disk: 204 `*.whisker.tapetum.json` vs 381 `*.whisker.json` in `data/whisker/`, so 177 papers have no LLM lane; 6/200 candidates errored with no sidecar at `00-baseline.md:51`).
  - `merged` = `combined_verdict` from fusion matrix in persona 13 (`13-score-fusion-architect.md:27-55`).
  - `δ` = `agree` | `esc+` | `llm-` | `-` (mirrors `inspect_report.py:55-56` agree/DIFFERS, plus rule id).
  - `conf` = tapetum `confidence` or `-`.
  - `overall` / `unigram` from whisker sidecar (`ref_overall` computed at `score.py:~215`, shown in live `report.md` rows).

  **Example lines (2026-07-06 run):**

  ```
  | P4003R0 | REVIEW | FAIL   | REVIEW | esc+ | 0.95 | 0.974 | 0.281 | 1 uncertain marker(s); 62 misaligned region(s); reference text agreement 0.824 low (advisory) |
  | P4182R0 | REVIEW | -      | REVIEW | -    | -    | 0.954 | 0.308 | 2 misaligned region(s) |
  | P1040R9 | REVIEW | PASS   | REVIEW | llm- | 0.98 | 0.979 | 0.616 | 15 misaligned region(s) |
  | N5035   | FAIL   | -      | FAIL   | -    | -    | 0.953 | 0.569 | gate:heading_monotone:heading level jumps H1 -> H3; 9 misaligned region(s); ... |
  ```

  Impact: all three lanes visible in one scan; `-` encodes "LLM lane did not run" without mistaking absence for pass (C5).
- [HIGH] **Terminal summary: whisker unchanged; fusion summary is a sibling.** `render_summary` is contract-tested as a pure deterministic function (`report.py:258-301`, `test_report.py:78-140`): sections keyed on **whisker** `verdict`, `_worst_first` sorted by `unigram_coverage` then advisory `ref_overall` (`report.py:145-163`), capped at `SUMMARY_SECTION_CAP=15` (`constants.py:145`, `test_report.py:102-109`). Changing whisker triage to merged would break CI semantics (C1) and existing tests. Impact: add `render_fusion_summary(pairs, ...)` in `tapetum_llm/fusion_report.py` where **merged tier drives section headers** (`fail (N)`, `review (N)`), but each `_fusion_item_line` keeps per-lane suffix:

  ```
    P4003R0     uni=0.974 ovr=0.281  det:REVIEW llm:FAIL(0.95) -> merged:REVIEW [esc+]
    P4182R0     uni=0.954 ovr=0.308  det:REVIEW (no llm) -> merged:REVIEW
    P1040R9     uni=0.979 ovr=0.616  det:REVIEW llm:PASS(0.98) -> merged:REVIEW [llm-]
  ```

  Footer shows merged counts plus tapetum coverage: `17 failed, 89 review, 88 passed (194 adjudicated, 187 whisker-only) in 4826.0s` (194 adjudicated, 123 differs from `00-baseline.md:49`). Whisker `--score` keeps printing `render_summary` only (`__main__.py:263-268`).
- [HIGH] **Dedicated `report-merged.md`, not a second writer to `report.md`.** Two CLIs already split persistence: whisker writes `report.md` + `report.json` (`__main__.py:250-255`); tapetum writes `tapetum-inspect.md` (`cli.py:231-243`). A tapetum post-pass should write `report-merged.md` (worst-merged-first leaderboard) and `report-merged.json` (`{schema_version, counts: {merged:..., det:..., llm:...}, results: [FusionResult...]}`) beside existing sidecars. Keep `tapetum-inspect.md` for per-paper evidence depth (`inspect_report.py:76-112` axis tables, grounded quotes). Impact: goal 2 persistence stays three files per paper (`*.whisker.json`, `*.whisker.tapetum.json`, `*.fusion.json` per persona 13) plus three run-level reports (`report.md`, `report-merged.md`, `tapetum-inspect.md`) with clear ownership.
- [MED] **Merged leaderboard sort: verdict tier first, content gate second.** PID sort in `render_report_md` (`report.py:100`) is correct for deterministic audit trails but wrong for hybrid triage (123/194 disagreements, `00-baseline.md:49`). Invert `_worst_first` priority: primary key = merged verdict severity (`fail=0, review=1, pass=2`), secondary = whisker `unigram_coverage` ascending (same content gate rationale at `report.py:148-153`), tertiary = tapetum `confidence` descending within bucket (surface high-confidence escalations), tiebreak = `pid`. Papers with `llm=-` sort inside their merged bucket by unigram only; never promote them above adjudicated disagreements solely because LLM is missing.
- [MED] **Column-width budget: drop oracle triplet from merged table.** Full deterministic table is already 12 columns wide (`report.py:108`); duplicating `nid|teds|mhs` in the merged view pushes past comfortable Markdown viewing. Keep `overall` (advisory composite) + `unigram` (verdict driver) as the two numeric lanes; link to `report.md` for full oracle columns. `flags` column should stay truncated to first hard flag + count, matching terminal `_flags_text` precedence (`report.py:45-47`).
- [LOW] **`tapetum-inspect.md` header counts should gain a merged rollup line.** `format_report` already prints `papers / adjudicated / differs` (`inspect_report.py:130-140`). Add `merged: X pass, Y review, Z fail` from fusion counts so operators do not need to open two files for batch posture.

## False-pass hypothesis

P1040R9: whisker `review` (15 misaligned regions, `report.md` row + `tapetum-inspect.md:44-48`) with tapetum `pass` at confidence 0.98. Conservative fusion keeps `merged=review` / `llm_lenient` (persona 13 matrix). A **display-only** merge that painted tapetum PASS in the `merged` column without the escalation matrix would false-pass the paper in a merged-sorted triage view even though deterministic gates still say review.

## False-fail hypothesis

N5035: whisker `FAIL` (`report.md` row: heading_monotone gate, `unigram_coverage=0.953`) with no tapetum sidecar (`llm=-`). Fusion returns `merged=FAIL` / `whisker_only`. If merged sort or terminal summary **elevated** "no LLM" papers into the fail section ahead of adjudicated `esc+` cases solely because deterministic fail count is 15 (`00-baseline.md:48`), operators waste time on already-gated papers instead of 123 tapetum disagreements; sort key must not treat `-` as worst-than-fail.

## What would change my mind

A side-by-side operator study (or even a counted diff) showing that maintaining **two** run-level Markdown files (`report.md` + `report-merged.md`) causes systematic mis-triage versus a single file, *and* a tapetum-only rewrite of `report.md` that preserves whisker `--gate` output exactly when tapetum has not run — would flip the dedicated-file recommendation to a guarded single-file append.
