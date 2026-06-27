# whisker changelog

All notable changes to the `whisker` QA + benchmark package. Schema version
refers to `WHISKER_SCHEMA_VERSION`, the stamp on every whisker artifact (sidecar,
report, bench leaderboard, guard baseline, calibration).

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
golden file (a few human-verified facts suffice). This is the gap the two repo
audits found: across 28 converters only `olmocr` tests comprehension, and no
repo has an automatic "this file is 100% correct" oracle. All three lanes are
documented in `src/whisker/CLAUDE.md`.

### Added (Lane 3 comprehension, Phase D)

- **`facts.py` + `whisker facts` verb.** Deterministic, human-verified fact
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
