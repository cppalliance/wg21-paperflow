# 14 - The Performance / Scalability Reviewer

**Verdict:** usable-with-conditions — reference-free `--all` is CI-viable (~70–86s / 382 papers); default oracle path is not (~18 min extrapolated) and the block-match matrix fallback is a silent metric cliff on 13+ large papers.
**Confidence:** high

## Findings

- [CRITICAL] **Default oracle path is dominated by markitdown, not whisker metrics — ~5–12× slower than `--no-reference`.** Evidence: `P3100R6` timing (2026-06-25): ref-free `score_paper` **1.41s**, markitdown alone **9.29s**, full oracle score **16.58s** (`reference.py:64-65`, `score.py:283-284`); 3-PID sample **3.18s** ref-free vs **17.25s** oracle; 30-PID oracle batch **83.5s** → extrapolated **~1060s (~17.7 min)** for 382 papers vs ref-free `--all` **69.9s** (this run) / **86.1s** (`00` §3a). Impact: CI or nightly jobs that run default `whisker --all` pay a second full PDF/HTML conversion per paper for an advisory overlay that never hard-fails (`score.py:175-178`); operators should treat `--no-reference` as the scale path (`CLAUDE.md:100-101`, `__main__.py:147-148`).

- [HIGH] **Block-matrix budget fallback is silent and changes the metric semantics on large papers — a quality cliff for `bench`, not oracle.** Evidence: `BLOCK_MATRIX_CELL_BUDGET = 400_000` (`constants.py:128`); when `gt_blocks * pred_blocks` exceeds budget, `block_metrics` returns whole-document `text_nid`, `matched=0`, `reading_order=0.0` with no flag (`match.py:253-255,229-230`); corpus scan: **13/382** candidate papers have `blocks² > 400k` (worst: `P3596R2` **3219** blocks); synthetic 650-block reorder: under-budget block nid **1.0**, over-budget fallback nid **0.958** (reorder penalized); real symmetric fallback on `P3596R2`: **0.132s**, `matched=0`. `BenchRow` stores only `nid`, not whether fallback ran (`bench.py:216-217`). No test covers fallback (`test_match.py` has no budget case). Impact: Lane 2 `bench`/`guard` can falsely regress large faithful reflows below `NID_FLOOR=0.90` (`constants.py:58`) without any observable "degraded mode" in output — operators cannot distinguish OmniDocBench-grade block NID from order-sensitive full-doc NID.

- [HIGH] **Near-budget block matching is seconds-to-minutes per paper pair on real WG21 text, not milliseconds.** Evidence: `constants.py:123-124` documents "~25s" for ~1700 blocks; runtime with real `P3045R8` blocks (632 blocks, avg **565** chars): Hungarian path **11.29s**, `matched=626`; synthetic short blocks at 632 cells: **0.24s** only. Matrix build is O(gt×pred) NED per cell (`match.py:110-116`). Impact: a labeled micro-corpus that includes long WG21 papers will make `whisker bench`/`guard` batch runs CPU-heavy; pseudo-page bucketing noted as the fix (`constants.py:126-127`) is not implemented.

- [MED] **Fuzzy rescue is an O(pred_len × gt_len) sliding window per unmatched pair, capped only by `BLOCK_FUZZY_MAX_PRED_LEN=2000`.** Evidence: `_sub_gt_fuzzy_matching` scans every window (`match.py:131-137`); rescue loop skips pred blocks longer than 2000 chars (`match.py:195-196`) but still iterates all unmatched GT×pred pairs (`match.py:189-209`). Impact: under-budget papers with many unmatched blocks after Hungarian assignment can spike latency; worst case bounded by block count squared times window cost, not by the matrix budget alone.

- [MED] **Oracle `table_score` (TEDS per table) adds multi-second per-paper cost on table-heavy papers.** Evidence: `P3045R8` (29 tables): self-compare `table_score` **4.28s** (oracle path calls this via `score.py:213`); `P3100R6` (7 tables): **0.155s**; memory peak modest (**2.3 MB** traced on `P3045R8`). Impact: table-rich PDFs inflate oracle scoring beyond markitdown conversion time; memory is not the bottleneck on current corpus, CPU is.

- [MED] **`--all` with `--no-reference --no-write` is CI-viable at current corpus size; default oracle is not for tight per-PR gates.** Evidence: ref-free `--all --no-write -q`: **69.9s / 382 scored** (~183 ms/paper); sequential single-threaded loop (`__main__.py:202-217`); exit contract supports `--gate pass` for strict CI (`__main__.py:159-162`, `constants.py:136-139`). Impact: wire CI to `--no-reference --no-write --gate pass` (or `review` if triage desired); reserve default oracle for scheduled/ad-hoc runs unless budget allows ~18 min per full corpus.

- [LOW] **Whole-document `text_nid` / rapidfuzz path is appropriately fast; memory on giant tables/papers is not a current risk.** Evidence: `metrics.py:64-78` (SIMD rapidfuzz, "milliseconds" for full-doc); fallback on `P3596R2` **0.132s**; TEDS peak **≤2.3 MB** on table-heavy paper above. Impact: performance risk is algorithm choice (block matrix, markitdown, TEDS count), not RSS blowups on the 382-paper corpus.

## False-pass hypothesis

A **large WG21 paper (>632 blocks per side)** where tomd faithfully reflows multi-column text: block matching would score **nid≈1.0** (`test_match.py:36-42`), but matrix budget forces whole-document fallback (`match.py:253-255`) yielding **nid≈0.96** on reorder — still above `NID_FLOOR=0.90`, so `bench` passes. If GT block granularity differs enough that fallback plus genuine localized loss compound below **0.90**, the paper fails for the wrong reason (order-sensitive cliff) while `content_recall` may stay high — a false fail, not pass. For the **default score path**, oracle-off ref-free gates ignore block NID entirely; false-pass via performance path is N/A there.

## False-fail hypothesis

**`P3045R8`-scale paper** in a future labeled corpus: candidate matches GT with block reorder fidelity, but **1730×1730** cells exceed budget → fallback `text_nid` **<0.90** → `guard`/`bench` flags `nid` regression (`bench.py:285-291`, `NID_FLOOR=0.90`) while human review would accept the conversion. Extrapolation from synthetic 650-block reorder cliff (0.958 vs 1.0) and 13 corpus papers already over budget.

## What would change my mind

A **schema-3 `whisker bench` run** on ≥5 labeled papers including one `blocks>632` member, logging `BlockMetrics.matched/gt_blocks/pred_blocks` alongside `nid`, showing block path (not fallback) completes in **<30s** per pair and **nid** within **0.02** of a forced full block match (budget disabled in a one-off script) — proving the cliff is rare or pseudo-page bucketing fixes it before Lane 2 goes operational.
