# 03 - The Adversary (Gate Evasion)

**Verdict:** usable-with-conditions — the reference-free hard gate reliably catches missing words and broken structure, but it systematically false-passes semantic corruption (reordered sections, permuted table rows, garbled cell-to-column assignment) whenever the token multiset stays intact.
**Confidence:** high

## Findings

- [CRITICAL] The only hard fails on the reference-free path are structural gate failures plus `unigram_coverage < 0.85`; reading order, table fidelity, and cell adjacency are not gated. Evidence: `score.py:149-184` (`_decide`: gates + unigram floor are the sole hard paths; shingle `coverage` explicitly "never a verdict flag"). Impact: a conversion can scramble tables and invert document order yet receive `pass` if every source word still appears somewhere in the markdown.

- [CRITICAL] `unigram_coverage` is multiset token recall and is invariant to reordering — the content gate cannot see permutations. Evidence: `check_content.py:621` (`unigram_coverage = _multiset_coverage(src_tokens, md_tokens)`); `test_check_content.py:464-474` (fully reversed word order → `unigram_coverage == 1.0` while shingle `coverage < 0.5`). Impact: reordering entire sections or table rows is invisible to the hard gate by design.

- [HIGH] **Demonstrated false-pass on a real paper.** Starting from clean `P1040R10` (baseline pass, `uni=0.9993`, `cov=0.9914`, 0 regions), I applied: (1) reverse all 11 `##` sections so `## References` precedes `## Abstract`, (2) swap adjacent table row pairs in every pipe table (24 swaps). Full `check_paper_content` + `score_markdown` on staged temp copy → **`verdict=pass`**, `uni=0.9993`, `cov=0.9759`, `regions=0`, `qa_score=100`, all gates pass. Sample row corruption: `| #embed GCC | 0.201 s | ...` became `| Circle @embed | 0.199 s | ...` (label column swapped with timing column). Impact: downstream LLM reads wrong row/column semantics; whisker says ship.

- [HIGH] The attack generalizes across the corpus. On 76 papers that pass whisker today and have ≥3 sections plus tables, the same reverse-sections + adjacent-row-swap attack yields **74 pass, 2 review, 0 fail** (97.4% false-pass rate). Examples: `P1040R10` (`cov` 0.9914→0.9759), `P2728R11` (0.998→0.9906), `P2728R12` (0.998→0.9909). Impact: the dominant pass tier (163/382 = 42.7% ref-free passes per `00-EVIDENCE-BASELINE.md` §3a) is not evidence of semantic fidelity.

- [MED] Column-reverse table swaps (mirror every row's cells) survive the hard gate but downgrade to `review` via misaligned regions — still not `fail`. Evidence: runtime on `P1040R10` with column swap only → `verdict=review`, `uni=0.9993`, `33 misaligned region(s)` (`score.py:164-166`, `REGION_SOFT_COUNT=1` in `constants.py:47`). Impact: CI with default `--gate review` catches this; `--gate pass` does not; neither tier marks it broken.

- [MED] Structural gates inspect markdown well-formedness, not semantic layout. Evidence: `gates.py:153-161` runs `non_empty`, `front_matter_valid`, `heading_monotone`, `no_empty_code`, `no_empty_table` only; reversed sections keep monotone H2 headings. `heading_monotone` catches H2→H4 jumps (9/14 corpus fails per `00-EVIDENCE-BASELINE.md` §3c) but not section permutations. Impact: pedantic heading-level fails while gross content reorder passes.

- [MED] Lane 3 (`facts.py` `table`/`math` assertions) is the documented defense for cell/exponent errors (`CLAUDE.md:37-44`, `facts.py:309-325`), but the in-repo corpus has zero labeled facts (`00-EVIDENCE-BASELINE.md` §4: `whisker facts --corpus` → ERROR). Impact: the only check that would catch "row 3 column 2" errors is built but non-operational on real data.

- [LOW] Provisional thresholds were never calibrated on labeled data (`constants.py:11-15`, `00-EVIDENCE-BASELINE.md` §5). Impact: we cannot quote TPR/FPR for the false-pass rate above; the 0.85 unigram floor is borrowed, not measured.

## False-pass hypothesis

**Achieved.** Take any passing WG21 paper with pipe tables (e.g. `P1040R10`): reverse the order of all body sections after front matter, then swap adjacent rows within each table. All words remain in the multiset → `unigram_coverage` stays ≥0.999; pairwise row swaps preserve local token windows enough to avoid misaligned-region soft flags → `verdict=pass` with `qa_score=100`. A human (or Lane 3 `table` fact on a specific cell neighbor) would reject it immediately.

Minimal synthetic analogue (unit-test shape, mirrors `test_check_content.py:464-474`):

```markdown
---
title: "Demo"
document: P9999R0
---
## Conclusion
Zebra alpha beta gamma delta epsilon.
## Introduction
Alpha beta gamma delta epsilon zebra.
| Metric | Value |
|--------|-------|
| latency | 10 ms |
| throughput | 99 qps |
```

Sections reversed + row order swapped: structurally valid, words present, whisker hard gate passes; reading order and table semantics are wrong.

## False-fail hypothesis

**Present on corpus, opposite failure mode.** `P3941R2`/`R3`/`R4` fail with `uni=0.999, drift=0.001` solely on `heading_monotone` H2→H4 jump (`00-EVIDENCE-BASELINE.md` §3c; `gates.py:105-110`). Good content, pedantic structure rule → `fail`. Asymmetric: strict on heading depth, blind to section/table permutations.

## What would change my mind

A measured operating point from `whisker calibrate --labels` on ≥30 hand-labeled papers **plus** at least one operational Lane 3 fact per table-heavy paper (cell + neighbor assertions), showing the reverse-and-swap attack fails at the intended FPR — or a new hard signal (e.g. reading-order floor on shingle `coverage` drop magnitude, or `bench`-style `content_recall` on source blocks) with documented false-fail cost.
