# 16 - The Test-Suite Auditor

**Verdict:** usable-with-conditions — 353 passing tests give strong regression coverage of metric math, guard diff logic, and threshold wiring, but almost none of the verdict path is validated against labeled outcomes or real `check_paper_content` output; green CI is false comfort for QA trustworthiness until integration and accuracy tests exist.
**Confidence:** high

## Findings

- [CRITICAL] **No test measures verdict accuracy against human labels.** Evidence: `00-EVIDENCE-BASELINE.md` §2 ("353 passing tests is a quality signal for the CODE, not for the VERDICT's real-world accuracy"); §4 (corpus has zero real `<pid>.gt.md` / facts); §5 (`calibrate` never run, no `--labels` JSON). Impact: the suite can stay green while pass/review/fail rates on 382 real papers (163/205/14 ref-free, `00` §3a) are unvalidated; tests prove internal consistency, not that triage is right.

- [HIGH] **The primary verdict path is tested with injected mocks, not production inputs.** Evidence: `test_score.py:46-68` builds a `SimpleNamespace` `_content(...)` with hand-set `unigram_coverage`/`drift`/regions and passes it to `score_markdown`; `score.py:264-288` `score_paper` calls `check_paper_content(pid, backend)` but has **zero** test references (grep across `packages/whisker/tests`). Impact: threshold band logic is verified (`test_score.py:71-139`) but the fusion of real tomd content metrics + gates + oracle is untested; a bug in `check_paper_content` wiring or field mapping would not fail CI.

- [HIGH] **Entire CLI surface (~794 LOC) is untested.** Evidence: `__main__.py` defines `_score_main`, `_bench_main`, `_guard_main`, `_golden_main`, `_facts_main`, `_calibrate_main` (lines 123–885); no test file imports `whisker.__main__` or exercises subprocess/exit codes. Impact: CI contract (`EXIT` codes, `--gate`, `--no-write`, batch `--all`, anchor/fact conjunctive guard in `_run_anchor_checks`/`_run_fact_checks` at lines 462–501) is unverified; redteam Tier-1 guard fixes are unit-tested in isolation but not through the command users run.

- [HIGH] **`_decide` soft-flag branches for `qa_score` and `uncertain_count` have no tests.** Evidence: `score.py:170-173` (`qa_score < QA_SCORE_SOFT_EDGE`, `uncertain_count` → review); grep for `qa_score|uncertain_count|mojibake|table_parse|lossy_table` across `packages/whisker/tests` returns **no matches**. Impact: two signals listed in `CLAUDE.md` as soft review drivers are dead code from a test perspective; ref-free stats show **6** qa and **30** uncertain flags on real papers (`00` §3a) with no regression net if `_decide` or `compute_metrics` mapping breaks.

- [MED] **`content_recall` guard axis is stored but never regression-tested.** Evidence: `guard.py:105-110` includes `content_recall` in `_FLOORS`; `test_guard.py:261-266` `_ineligible_row` only checks null-axis eligibility for teds/mhs; all floor-crossing tests (`test_crossed_floor_sub_slack_still_fails` at line 68, `test_new_paper_below_floor` at line 77) use synthetic `nid`/`teds`/`mhs` only. Impact: bench's first-class content-recall gate (`bench.py`, `CONTENT_RECALL_FLOOR=0.90` in `constants.py`) could regress in guard without CI catching it once a GT corpus exists.

- [MED] **`BLOCK_MATRIX_CELL_BUDGET` whole-document fallback is untested.** Evidence: `match.py:253-255` falls back to `text_nid` when `len(gt)*len(pred) > BLOCK_MATRIX_CELL_BUDGET`; `test_match.py` covers reorder, fuzzy rescue, and reading order but never forces the budget path. Impact: large WG21 papers may silently switch scoring models (block-matched nid → full-document nid, `reading_order=0.0` per `match.py:229-230`) with no test pinning behavior; bench/guard aggregates could shift without detection.

- [MED] **Property coverage is narrow: fixed grids, no fuzz, no end-to-end bad-paper fixture.** Evidence: `test_invariants.py:22-44` uses small static `_TEXTS`/`_TABLES`/`_DOCS` tables (identity/symmetry/bounds only); no `hypothesis` or generative markdown; no staged paperstore fixture asserting a known-broken conversion fails. Impact: edge cases in gates (`gates.py:136-150` table vs thematic-break discrimination is tested) but not cross-module failures (e.g., good gates + bad content from real PDF tokenization).

- [LOW] **`calibrate` CLI ordering guard is library-tested but CLI-untested.** Evidence: `test_calibrate.py` covers `calibrate_threshold` only; `__main__.py:849-861` emits `edge_ordering_ok` and warns on inverted bands (redteam-synthesis Tier-1 #3, fixed). No test asserts warning/`edge_ordering_ok: false` on adversarial label JSON. Impact: low today (calibration never run per `00` §5) but the shipped CLI path lacks a regression net.

## False-pass hypothesis

A table where **one body cell is wrong** (e.g., `| 1 | 9 |` instead of `| 1 | 2 |`) but prose dominates token multiset: `unigram_coverage` stays ≥ 0.85, structural gates pass, zero or one misaligned region. Evidence: `test_bench.py:156-159` shows teds drops on cell change but ref-free `_decide` never sees teds (`score.py:156-184`); only **3/382** ref-free fails hit unigram floor (`00` §3a); Lane 3 facts and GT bench do not run (`00` §4). Whisker would **pass** while a downstream LLM reads the wrong cell.

## False-fail hypothesis

**P3941R2/R3/R4-style papers**: `uni=0.999`, `drift=0.001`, hard-fail solely on `heading_monotone` H2→H4 (`00` §3c, `gates.py:105-109`, `test_gates.py:57-60` proves the gate fires but not that real WG21 headings are wrong). Separately, any clean paper with **one** furniture-stripped region hits review via `REGION_SOFT_COUNT=1` (`score.py:164-166`, **186** papers `00` §3a) — good conversions buried in the review majority.

## What would change my mind

A committed **micro-corpus of ≥10 hand-labeled papers** (pass/review/fail labels + optional `<pid>.facts.jsonl`) with integration tests calling `score_paper` on real staged sources in a temp paperstore and asserting **expected verdict labels** (not just metric ranges) — even 80% label agreement on that set would flip this from "false comfort" to "measured operating point."
