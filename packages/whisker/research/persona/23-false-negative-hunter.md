# 23 - THE FALSE-NEGATIVE HUNTER

**Verdict:** usable-with-conditions — the 163-paper pass tier proves structural well-formedness and ≥95% token-set recall, not semantic fidelity; multiple real and crafted broken conversions score `pass` with zero flags.
**Confidence:** high

## Findings

- [CRITICAL] **Pass requires only gates + `unigram_coverage ≥ 0.95` with no soft flags; reading order, table cell assignment, code fidelity, and formatting are ungated.** Evidence: `_decide` hard-fails solely on gate failures and `unigram_coverage < 0.85` (`score.py:152-160,180-184`); shingle `coverage` is "never a verdict flag" (`score.py:136-137`, `constants.py:32-33`). Impact: the 163 ref-free passes (`00-EVIDENCE-BASELINE.md` §3a) are a **multiset-presence** certificate, not a ship-safe conversion certificate.

- [CRITICAL] **Crafted semantic corruption on a live pass-tier paper still passes.** Starting from `P3104R5` (baseline `pass`, `uni=0.999`, `cov=0.989`, `qa=100`, 0 regions), runtime `score_markdown` after mutating the staged markdown (same source, recomputed content metrics): **swap two adjacent table rows → `pass`** (`uni=0.999`); **swap two `##` section bodies (headings fixed) → `pass`**; **strip all `[text](url)` links → `pass`**; **strip `*`/`**` emphasis → `pass`**; **replace `template`/`constexpr` inside first fenced block → `pass`**; **merge adjacent paragraphs → `pass`**. Impact: wrong row/column semantics, lost navigation, wrong code, and broken rhetorical structure all ship green.

- [CRITICAL] **Real pass-tier papers already exhibit large reading-order gaps with zero flags.** On all 163 passes, `missing_region_count + extra_region_count = 0` (runtime JSON sweep). Five papers pass with `unigram_coverage - coverage > 0.05`; worst: **`P4178R0` `pass` with `uni=0.952`, `cov=0.837`** (11.5pp gap, no soft flags). Evidence: `check_content.py:621` (unigram is order-invariant multiset); `test_check_content.py:464-474` (reversed words → `unigram=1.0`, shingle `coverage<0.5`). Impact: severely scrambled reading order is already in the pass tier today, not a hypothetical attack.

- [HIGH] **The pass band allows ~5% token loss before downgrade; rare vocabulary loss can pass silently.** Evidence: minimum `unigram_coverage` among 163 passes is **0.9505** (runtime); edges `UNIGRAM_COVERAGE_REVIEW_EDGE=0.95` / `FAIL_EDGE=0.85` (`constants.py:37-38`). Impact: a conversion can drop up to ~5% of source tokens (often a section, table column of rare terms, or all math operators if duplicated elsewhere) and remain `pass`, not `review`.

- [HIGH] **Table semantics and lossy extraction are reported but never fail.** `lossy_table_count` and `table_parse_errors` are stored on `WhiskerResult` (`score.py:67-68,249-250`) but absent from `_decide`. **`P3724R3` and `P3724R4` pass** with `<!-- tomd:lossy-table -->` in the markdown and `lossy_table_count=1`, `qa=100` (runtime). Lane 2 TEDS/grits_con and Lane 3 `table` facts are non-operational on real data (`00` §4; `notes/redteam-synthesis.md` Tier 3). Impact: corrupted or flattened tables pass if pipe syntax survives `no_empty_table` (`gates.py:135-150`).

- [HIGH] **Code-block and inline-code corruption is invisible to the content gate.** Markdown tokenization strips fence markers and normalizes punctuation (`check_content.py:219-233,400+`); swapping identifiers inside a fence does not change the token multiset when those tokens appear elsewhere in the paper. Runtime: `corrupt_code_block` mutation on `P3104R5` → **`pass`**. Impact: a WG21 wording/code example can be syntactically wrong while whisker reports full coverage.

- [MED] **Encoding damage can pass.** `P4211R0` passes ref-free with **`qa_score=80`** driven by `16 mojibake sequences` (`qa.py:421-428` penalizes but `_decide` only soft-flags `qa_score < 70`, `constants.py:51`). Impact: visible character corruption survives the pass tier if unigram recall stays ≥0.95.

- [MED] **Asymmetric strictness: heading pedantry fails, permutations pass.** Nine of fourteen ref-free fails are `heading_monotone` H2→H4 jumps with `uni≈0.999` (`00` §3c; `gates.py:105-110`), while section/table permutations that preserve monotone H2 headings pass (`03-adversary-gate-evasion.md` verified: reverse-sections + row-swap attack on `P1040R10` → `pass`). Impact: CI rejects cosmetic heading depth errors but accepts gross semantic reordering.

## False-pass hypothesis

**Achieved (crafted).** Take `P3104R5` (`pass`, `uni=0.999`): swap the bodies of two mid-document `##` sections (leave headings in place), swap adjacent rows in the first pipe table, strip link targets to bare text. Re-score against the same PDF source: **`verdict=pass`**, `uni≥0.999`, `qa=100`, 0 hard/soft flags. A downstream LLM reads wrong section order, wrong table row semantics, and dead references; whisker says ship.

**Already live (uncrafted).** `P4178R0` is in today's 163 passes with `cov=0.837` vs `uni=0.952` and zero region flags — strong evidence the production converter (or source/markdown alignment) already scrambled reading order below the level any ref-free signal surfaces, yet whisker marks it clean.

## False-fail hypothesis

**Present on corpus.** `P3941R2`/`R3`/`R4` fail ref-free with `uni=0.999`, `drift=0.001` solely on `gate:heading_monotone:heading level jumps H2 -> H4` (`00` §3c). Content-complete papers fail on heading depth while permuted pass-tier papers (`P3104R5` mutations above) remain `pass`.

## What would change my mind

Measured TPR/FPR from `whisker calibrate --labels` on ≥30 hand-labeled papers **plus** operational Lane 3 facts (especially `table` cell-neighbor and `order` assertions) on table-heavy passes, showing the section-swap/row-swap attack fails at the intended false-pass rate — or a new hard/soft signal for reading-order degradation (e.g. flag when `unigram_coverage - coverage` exceeds a calibrated gap, or gate `content_recall` on source blocks) with documented false-fail cost on faithful multi-column reflows.
