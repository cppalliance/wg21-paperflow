# Opus-A - Meta-Review: Gates & Error-Class Cluster

**Cluster:** 04-test-suite-auditor, 07-adversary-evasion, 08-false-positive-hunter,
09-false-negative-hunter, 19-ground-truth-auditor.

**Method:** every CRITICAL/HIGH claim re-read against `gates.py`/`score.py`/`fusion.py`/
`facts.py` at the cited lines, then reproduced live: `uv run python` from the repo root
against a throwaway script in `%TEMP%` importing `whisker.gates`/`whisker.score`/
`whisker.facts` with the exact claimed inputs (dot-leader TOC, roman-numeral suffix,
`Inhaltsverzeichnis`, `## C++ 26`/`## C++`, decoy-table neighbor check, `_decide` on a
token-preserving corruption signature). Script deleted after the run (output captured
below). `score-baseline.json` and `test_score_pinning.py` were read directly, not
executed, since the pinning claim is about assertion *shape*, not runtime output.

## Verdict on cluster

**Does not move the architecture answer.** Every CRITICAL/HIGH finding that survived
re-verification is a **bug or calibration gap inside a specific deterministic gate**
(`no_toc_leak`'s regex is simultaneously too narrow against 5+ bypass shapes and too
broad against 3 legitimate-heading shapes; `heading_monotone` is a blunt H-level-jump
trigger with no cosmetic exemption; anchorless table facts use ANY-semantics; the golden
pinning test checks shape-equality, not correctness). None of them are evidence that
**moving decision authority to the LLM** would do better: 05-web Q1/Q2/Q4 and all 31
reference repos in 00-baseline are unanimous that LLM-as-mechanical-gate trades a fixable
regex bug for unfixable variance, position/self-bias, and overconfidence — and marker
(the one repo with an LLM QA signal) still gates CI on the deterministic axis only. The
fixes for every confirmed finding here are **named upgrades within det-first**: better
regexes, a golden-grid, wiring `auto_baseline_checks`, a CI hook on `bless_stem`, a WG21
heading exemption. This confirms all five personas' independent "usable-with-conditions"
verdicts; my contribution is pinning down which specific claims are exactly right, which
are overstated, and which are unverified corpus-level extrapolations.

The one finding worth escalating past "gate bug" is the **selection-gap / token-preserving
corruption class** (07 CRITICAL, 09 CRITICAL x2): reorder, table-cell-swap, and
math-variable-swap all preserve the unigram multiset, so `_decide` (score.py:181-185)
never hard-fails them, and even when the LLM runs and catches it, `fusion.py`'s own rule
set (lines 229-240) caps the outcome at `review`, never `fail` when det=pass. This is a
real architectural blind spot, but it is a blind spot **shared by every reference repo's
cheapest-signal-first design** (marker's heuristic-only CI gate is evaded the same way,
per 07's own marker false-pass hypothesis), not a whisker-specific defect that an
LLM-decides architecture would close for free.

## Findings table

| Persona claim | Verdict | Evidence |
|---|---|---|
| 07/04: TOC bypass — dot-leader (`....... 3`), roman-numeral suffix (`iii`), parenthesized `(3)`, reworded entry, plain-text no-label line all **pass** `no_toc_leak` | **CONFIRMED** | Runtime repro, all 5 shapes -> `passed=True` |
| 04: `Inhaltsverzeichnis` (German label) and pipe-table TOC rows with no `Contents` label both **pass** | **CONFIRMED** | Runtime repro -> `passed=True` for both |
| 07: "only tab-separated digits trip the pairwise matcher" (implying space-separated does not) | **REFUTED** | `_PAGE_SUFFIX_RE = r"...\s+(?P<page>\d{1,4})$"` uses `\s+`, which matches space too; runtime repro shows the ordinary space-separated case (`## 1. Introduction 3`) **also fails** (correctly caught) — the gate's true positive case is not tab-exclusive. The 5 named bypass shapes are still real; only this one qualifier inside the same finding is wrong. |
| 08: `## Table of Contents` as a legitimate topic heading, and bare `Table of Contents` as prose, both **hard-fail** | **CONFIRMED** | Runtime repro, both -> `passed=False`, `detail="TOC label in body: ..."` |
| 08: `## C++ 26` then `## C++` fails; reverse order fails; `## ISO C++ 2026`/`## ISO C++` fails; `## C++26` (no space) passes; `## Contents of the proposal` passes but bare `## Contents` fails | **CONFIRMED** | Runtime repro reproduces every variant exactly, including the no-space asymmetry and the "Contents of the proposal" vs bare "Contents" asymmetry |
| 08: `heading_monotone` is 9/14 (64%) of ref-free hard fails on the real 382-paper corpus, `P3941R2/R3/R4` fail solely on H2->H4 with `uni=0.999` | **CONFIRMED** (secondary evidence + logic cross-check) | `packages/whisker/research/persona/00-EVIDENCE-BASELINE.md:59-88` states this exact rollup with matching pids and numbers; I did not have a populated `WG21_DATA_DIR` to re-run the full 382-paper scan myself, but confirmed the gate LOGIC (`gates.py:96-112`, any `level > prev+1` fails regardless of content quality) makes this outcome mechanically inevitable, and the cited document's specificity (exact pids, exact `uni=0.999`) is inconsistent with fabrication |
| 04/19: `score-baseline.json` pins `no_toc_leak: false` for p0533r9 / p1122r3 / p3968r0 and `heading_monotone: false` for p2040r0 | **CONFIRMED** | Direct read of `score-baseline.json` lines 2-9 (p0533r9), 94-101 (p1122r3), 255-262 (p3968r0), 117-121 (p2040r0) — pid keys and gate values match exactly |
| 04: `test_score_pinned` asserts `actual["gates"] == expected["gates"]` with no `all(passed)` invariant; `WHISKER_PIN_UPDATE=1` has no `CI=true` guard | **CONFIRMED** | `test_score_pinning.py:153-155` (bare dict equality), `:131-141` (fixture reads env var, no CI check anywhere in file) |
| 07: `_decide` hard-fails only on structural gates + `unigram_coverage`; token-preserving reorder/table-swap/math-swap survives as a clean pass | **CONFIRMED** | `score.py:174-231` read directly (only loop is `for gate in gates` + one `unigram_coverage` branch); runtime repro: `_decide(1.0, 0.0, 0, 0, 100, 0, all_pass_gates)` -> `verdict='pass', hard=[]` |
| 07: anchorless Lane-3 table fact passes on ANY occurrence, so a decoy table can shadow-satisfy a claim that contradicts the genuine table | **CONFIRMED** | Runtime repro via `check_facts`: decoy table (`alpha`->99) with no `table_heading` -> fact `passed=True`; same claim WITH `table_heading` anchor -> fact-closes and fails on the row that violates the neighbor check |
| 08: fusion RESCUE (`heading_monotone`-only fail + LLM pass/review) always caps at `review`, never `pass`; det=pass + LLM major-fail caps at `review`, never `fail` | **CONFIRMED** | `fusion.py:148-160` (`FUSION_RULE_LLM_RESCUE_HEADING` returns `VERDICT_REVIEW` unconditionally) and `:228-240` (`FUSION_RULE_LLM_ESCALATE_MAJOR` also returns `VERDICT_REVIEW`, and there is no branch anywhere in the function that returns `VERDICT_FAIL` when `det != VERDICT_FAIL`) |
| 04: no test exercises German/localized TOC labels, no multi-row TOC table beyond a one-line fixture, no `Table of Contents` (full phrase) heading case | **CONFIRMED** | `test_gates.py:99-161` enumerated in full: 8 `no_toc_leak` tests, none use a non-English label, a multi-row table, or the words "Table of Contents" (only bare `Contents`/`CONTENTS`) |
| 09: `_gate_front_matter` checks only key presence (`title`, `document`), not value shape/correctness — a wrong revision letter passes | **CONFIRMED** | `gates.py:60-75`: builds a `keys` set from front-matter line prefixes, checks only `_REQUIRED_FRONT_MATTER_KEYS` membership; no value validation exists anywhere in the function |
| 09: math variable substitution and table row/column permutation are token-preserving and therefore pass the fleet gate | **CONFIRMED** (corollary of the `_decide` finding above) | Same code path: neither `gates.py` nor `_decide` in `score.py` inspects table grids or math surfaces; those checks exist only in `facts.py` Lane 3, which gates ~37 authored facts across 5 of 381 papers, not the fleet |
| 19: `bless_stem` hard-fails on any gate at blessing time, but this is a local pre-commit step, not a CI hook on golden PRs | **CONFIRMED** (by absence) | `golden_qa.py` `bless_stem` call site confirmed by 19's own citation (`golden_qa.py:623-630`); no `.github/workflows/*.yml` reference to `bless_stem` or `run_gates` on `ideals/*.md` found in this session's file reads (not exhaustively re-audited; treat the CI-absence half as consistent with, not independently re-proven against every workflow file) |

## Canonical deduplicated findings, ranked by severity

1. **[CRITICAL] `no_toc_leak` is simultaneously under- and over-inclusive.** One regex pair
   (`_TOC_LABEL_RE`, `_PAGE_SUFFIX_RE` in `gates.py:132-176`) is asked to distinguish "TOC
   chrome that leaked" from "a heading that happens to end in a number or say
   'Contents'." It cannot: dot-leaders, roman numerals, parens, rewording, and
   unlabeled plain-text TOC blocks all leak through (false-pass, silently ships PR
   #290/#293-class defects); `## Table of Contents` as a real section title and any
   WG21 paper with a stable name reused across a revision year (`## C++ 26` / `## C++`)
   both hard-fail (false-fail, blocks a legitimate paper on every CI run with no
   review-only path unless the LLM lane happens to run). Both directions are proven
   live, not hypothetical. Consolidates 07-CRITICAL-1, 04-HIGH-1, 08-CRITICAL-1,
   08-HIGH-1, 08-MED-1.

2. **[CRITICAL] The golden-pinning safety net records known-broken gates as the expected
   state, with no correctness floor and no CI guard on refresh.** Three committed goldens
   carry `no_toc_leak: false` and one carries `heading_monotone: false`
   (`score-baseline.json`), and `test_score_pinned` only asserts the *current* gate dict
   equals the *committed* gate dict — a gate weakening that happens to match an already-
   broken golden would pass silently, and `WHISKER_PIN_UPDATE=1` can rewrite that baseline
   with no `CI=true` block. This is the mechanism by which finding #1's false-negatives
   have persisted in the fixture corpus. Consolidates 04-CRITICAL-1, 19-CRITICAL-1/2.

3. **[HIGH] `heading_monotone` is the dominant false-fail source on the real corpus (9/14,
   64%, per the cited 382-paper rollup) and has no cosmetic exemption in the hard gate
   itself** — any H2->H4 jump fails regardless of content quality (`uni=0.999` cases
   confirmed as mechanically inevitable given the gate logic). The advisory LLM lane only
   partially absorbs this (RESCUE routes 9/9 such fails to `review`, confirmed never to
   `pass` by code), so every one of those papers still needs a human, every run.
   Consolidates 08-CRITICAL-2, 08-HIGH-2.

4. **[HIGH] Token-preserving semantic corruption (reorder, table-cell swap, math-variable
   swap) is the fleet's structural blind spot, and the fusion layer cannot close it even
   when the LLM catches it.** `_decide` only inspects gates + `unigram_coverage`; none of
   those axes move when tokens are preserved. When the LLM does run and flags a major
   axis fail on a det=pass paper, fusion caps the outcome at `review`, by design, never
   `fail` — this is the correct conservative choice for an advisory lane (confirmed:
   `fusion.py` has no det=pass -> fail path at all), but it means the worst false-pass
   class survives to "ship" if an operator treats det-pass as sufficient. Shared with the
   entire ecosystem's cheapest-signal-first CI gates (marker's heuristic-only gate has the
   documented analogue), not whisker-unique. Consolidates 07-CRITICAL-2, 09-CRITICAL-1/2.

5. **[HIGH] Anchorless Lane-3 table facts use ANY-of-occurrences semantics and are
   provably exploitable by a decoy table**, confirmed live: a fact with no
   `table_heading` passes on a fabricated table that satisfies the neighbor check even
   though the genuine table contradicts it. The fail-closed ALL-semantics fix already
   exists and works correctly when a `table_heading` anchor is supplied; the gap is
   authoring discipline (facts written without an anchor), not missing code.
   Consolidates 07-HIGH-1.

6. **[MED] Test-suite coverage mirrors the exploit surface exactly** (no localized/
   multi-row/full-phrase TOC test, no mixed-hard-flag fusion test) and the front-matter
   gate validates key presence only, never value correctness (a wrong revision letter in
   `document:` passes all six hard gates). Both are real but lower severity than #1-#5:
   they widen or extend an already-known gap rather than opening a new one. Consolidates
   04-HIGH-2/3, 09-HIGH-2.

## Recommended actions, ranked by cost

1. **(~few LOC, mechanical)** Add a `test_score_pinned`-adjacent assertion (or a
   separate meta-test) that fails when a *newly touched* golden's baseline entry contains
   any `false` gate value without an explicit `expected_gate_failures` annotation, and
   block `WHISKER_PIN_UPDATE=1` when `CI=true` (mirrors pandoc's `--accept` discipline,
   cited in 04). Closes finding #2 without touching gate logic.
2. **(~10-20 LOC)** Add a WG21-specific exemption to `_gate_no_toc_leak`'s page-suffix
   pairwise check: skip the pairwise match when the stem's suffix-vs-plain difference is
   only a 2-4 digit trailing token AND the heading otherwise reads as a stable proposal
   name (e.g. a cheap heuristic: skip if the stem appears earlier in the SAME heading's
   own front-matter `document:` id, or simply demote this specific sub-case to a soft
   flag instead of hard fail). Also widen `_TOC_LABEL_RE` to require the label be
   isolated (not itself a normal section, e.g. only trip when it's the ONLY heading
   before a page-numbered duplicate follows) — needs a design decision, not a blind regex
   patch, since over-narrowing reopens PR #290. Closes half of finding #1 (false-fail
   side) without reopening the false-pass side.
3. **(~15-30 LOC each, already scoped by 09)** Wire `auto_baseline_checks` (duplication/
   degeneration) into `_decide` as a soft flag; promote the existing
   `unigram_coverage - coverage` gap signal from LLM-selector-only to a deterministic
   soft flag. Both close real corruption classes at near-zero new-code cost and reduce
   reliance on the LLM lane ever running (mitigates finding #4's severity without
   requiring an LLM-as-gate reversal).
4. **(medium, per-paper authoring cost)** Require every new Lane-3 `table` fact to carry
   a `table_heading` anchor (lint rule in `corpus_tools.py` or a CI check on
   `.facts.jsonl`), closing finding #5 by discipline rather than new gate code.
5. **(medium, ~20-40 test LOC)** Add the missing TOC test fixtures named in finding #6
   (German/localized label, multi-row TOC table, full-phrase `Table of Contents` heading,
   `## C++ 26`/`## C++` false-fail regression) so any future regex change is caught
   both ways.
6. **(high, needs a labeled decision, not code)** Decide `heading_monotone`'s operating
   point: either add a narrow WG21 exemption (stable-name-under-revision-year pattern) or
   accept the 64% false-fail rate as the cost of a zero-false-negative structural check
   and rely on the RESCUE path — this is a calibration/product decision (09's "what would
   change my mind" gate), not a code fix, and should NOT be resolved by promoting the LLM
   to decide it (that reintroduces the variance/bias problems 05-web documents).

## Summary

Every CRITICAL/HIGH claim in this cluster that could be checked against live code was
CONFIRMED by direct source read and runtime reproduction (`no_toc_leak` bypass and
false-fail families, golden-pinning without a correctness floor, decoy-table ANY-
semantics, fusion's review-only ceiling); one sub-claim (tab-only pairing) was REFUTED,
and one corpus-level statistic (heading_monotone 64% share) was confirmed only via a
cited secondary document plus logic cross-check, not an independent full-corpus rerun.
None of the confirmed findings move the architecture verdict: they are gate-implementation
bugs and calibration gaps with named, cheap, det-first fixes, not evidence that an
LLM-decides architecture would do better — the reference-repo and web evidence in
00-baseline/05-web says the opposite. Recommend the ranked actions above, cheapest first.
