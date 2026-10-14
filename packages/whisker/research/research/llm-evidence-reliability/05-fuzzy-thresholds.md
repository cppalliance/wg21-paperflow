# 05 - Fuzzy-Matching Threshold Auditor

**Verdict:** usable-with-conditions — olmOCR's length-relative `partial_ratio` is the right primitive for bidirectional quote checks, but whisker must split source and candidate operating points, keep `EVIDENCE_MIN_FUZZY_CHARS` as a whisker-only guard olmOCR lacks, and route the gap between tight and loose thresholds to `ambiguous`; flat `EVIDENCE_FUZZY_FLOOR=0.90` over a whole document is unsafe for candidate absence.
**Confidence:** high

## Findings

- [CRITICAL] **Whisker uses one flat whole-document fuzzy floor for source grounding; candidate absence has no threshold at all.** `ground_spans` tier 3 accepts `partial_ratio(norm_quote, norm_md) / 100.0 >= EVIDENCE_FUZZY_FLOOR` (0.90) when `len(norm_quote) >= EVIDENCE_MIN_FUZZY_CHARS` (20) (`grounding.py:232-237`, `constants.py:67-73`). `pdf_judge.py:513-520` applies this source-side only; no inverted pass runs on `tomd_md`. Baseline replay: 12/20 quotes already present in candidate markdown (`00-baseline.md:14-19`), evidence precision 8/20 = 40%. Impact: candidate-side thresholds must be **stricter and localized**, not a mirror of source thresholds.

- [CRITICAL] **olmOCR `TextPresenceTest` is symmetric PRESENT/ABSENT on one formula; whisker should port the formula, not the defaults.** `packages/whisker/research/repos/olmocr/olmocr/bench/tests.py:167-182` computes `threshold = 1.0 - max_diffs / len(reference_query)` and `best_ratio = fuzz.partial_ratio(reference_query, md_content) / 100.0`. PRESENT passes when `best_ratio >= threshold`; ABSENT passes when `best_ratio < threshold`. Same normalization on both sides (`tests.py:47-80`: strip bold/italic/HTML, collapse whitespace, NFC, quote-smartening). Whisker already ports this for page quotes only: `ground_page_quotes` uses `PAGE_QUOTE_MAX_DIFFS=2` (`grounding.py:272-273`, `constants.py:176-181`). Impact: page-scoped olmOCR thresholds are proven; document-global flat 0.90 is not.

- [HIGH] **`EVIDENCE_MIN_FUZZY_CHARS=20` is a whisker innovation olmOCR and Marker lack; it is load-bearing.** olmOCR has no minimum-length guard on `partial_ratio` (`tests.py:167-169` runs ratio on any non-empty text). Marker `HeuristicScorer` uses fixed `score_cutoff=70` on block alignment with no length guard (`heuristic.py:77-82`). Whisker blocks tier-3 ratio for quotes under 20 normalized chars (`grounding.py:232-234`, `constants.py:69-73`); `test_tapetum_llm.py:1298-1308` proves `"alpha beta"` (9 chars, `pr=0.889`) drops instead of false-grounding against `"alphaxbeta"`. Runtime (2026-07-16): `"the committee"` (12 chars) scores `pr=1.000` against a long document via substring overlap — olmOCR `max_diffs=2` would pass (`threshold=0.833`), whisker flat fuzzy correctly refuses (`len < 20`). Impact: **source** presence may use length-relative olmOCR slack; **candidate** refutation must keep the 20-char gate and require substring or DP confirmation for short quotes.

- [HIGH] **Recommended separate operating points (research artifact; provisional until nine-PR labeled replay).**

  | Role | Haystack scope | Tiers (in order) | Threshold |
  |------|----------------|------------------|-----------|
  | **Source presence** (retain quote) | PDF page text for page quotes; whole PDF text for monolith | exact normalized substring → length-relative `partial_ratio` → (optional) whole-doc ratio | `T_src_lo = 1 - D_src / len(q)`, `D_src = PAGE_QUOTE_MAX_DIFFS` (2) when page-scoped; `D_src = 0` for monolith quotes under 20 chars; `D_src = 2` otherwise. Whole-doc fallback: `>= EVIDENCE_FUZZY_FLOOR` only if `len(q) >= 20`. |
  | **Candidate refute** (quote already in markdown) | Full `tomd_md` via `_present_within` (`facts.py:299-326`) | exact substring → `partial_ratio_alignment` window + substring DP | `T_cand_hi = 1 - D_cand / len(q)`, `D_cand = 2` default; `D_cand = 0` when `len(q) < EVIDENCE_MIN_FUZZY_CHARS`. DP confirmation mandatory whenever `max_diffs > 0`. |
  | **Candidate confirm absent** | Same | inverse of refute at tight budget | `T_cand_lo = 1 - D_abs / len(q)`, `D_abs = 0` (olmOCR default in sample corpus: most tests omit `max_diffs`). Confirmed absent only when locate fails at `D_abs` AND fails DP at `D_cand`. |
  | **Ambiguous band** | Same | ratio-only hit without DP, or ratio between budgets | `T_cand_lo <= pr < T_cand_hi` OR (`len(q) < 20` and substring miss but `pr >= T_cand_lo`). Route to abstention; do not count as missing evidence (`05-web.md:152-159`, CRAG pattern). |

  Numeric example for `len(q)=50`: `T_cand_lo = 1.00`, `T_cand_hi = 0.96`. Runtime `long near miss` (100-char quote, one-char corruption): `pr=0.995` — fails absent at `D=0`, passes refute at `D=2` → **ambiguous**, not confirmed absent. This prevents the false-fail class where a near-identical passage is declared missing.

- [HIGH] **Marker block alignment is a different fuzzy regime and must not set whisker quote thresholds.** `HeuristicScorer.find_fuzzy_alignments` (`heuristic.py:74-99`) aligns each GT block into candidate markdown with `partial_ratio_alignment(..., score_cutoff=70)` — a **fixed 70% cutoff**, not length-relative. Scores are length-weighted block means blended with Kendall-τ order (`heuristic.py:35-42`). Marker does not run absence tests or length guards (`05-web.md:20-27`). Impact: borrow Marker's **localization** (`dest_start`/`dest_end` from alignment), not its `70` cutoff; quote-level thresholds should follow olmOCR/facts, not block-benchmark scoring.

- [MED] **`partial_ratio` behavior differs by haystack size and quote length; whole-document comparison is asymmetric.** `partial_ratio(needle, haystack)` finds the best matching window in `haystack`; cost grows with haystack length (`research/llm-stack/06-performance-scalability.md:19`: ~37 ms at 80k chars). Short needles in long haystacks inflate scores via incidental substring overlap — olmOCR documents this: `test_tests.py:174-180` ABSENT on `"max"` fails against `"There is a max set of diffs"` (substring hit); `"maximum"` also fails. Whisker `facts.py:314-320` mitigates with alignment window + exact DP. Impact: candidate refute must use `_present_within`, not raw `partial_ratio` on the full markdown.

- [MED] **olmOCR table tests add a 0.50 floor whisker does not use for quotes.** `TableTest.run` sets `threshold = max(0.5, 1.0 - max_diffs / len(cell))` (`tests.py:395-396`). Quote-level `TextPresenceTest` has no floor. Impact: do not import the 0.50 floor for prose quotes; reserve it for table-cell matching only (`10-table-semantics.md` scope).

- [LOW] **Page quotes already use the correct olmOCR formula; monolith quotes do not.** `ground_page_quotes` (`grounding.py:261-274`) normalizes, checks substring, then `threshold = 1.0 - PAGE_QUOTE_MAX_DIFFS / len(norm_quote)`. Monolith `ground_spans` tier 3 still uses flat 0.90 over the whole PDF text. Impact: unify monolith source grounding on length-relative thresholds before adding candidate-side checks.

## Adversarial examples (reproduced 2026-07-16)

| Case | Quote len | `partial_ratio` | Substring | olmOCR `D=0` | olmOCR `D=2` | Whisker flat fuzzy | Correct tri-state |
|------|-----------|-----------------|-----------|--------------|--------------|-------------------|-------------------|
| Short generic overlap | 12 | 1.000 | yes | pass | pass | **blocked** (`len<20`) | `refuted_present` (substring) |
| Short reformatted (`alpha beta` vs `alpha x beta`) | 9 | 0.889 | no | fail | **pass** (t=0.778) | blocked | `ambiguous` (no DP; olmOCR alone over-calls present) |
| Date line duplicate (PR #290 class) | 8 | 1.000 | yes | pass | pass | blocked | `refuted_present` |
| `constexpr` genuinely absent (PR #293 class) | 15 | 0.750 | no | fail | fail (t=0.867) | blocked | `confirmed_absent` |
| Dehyphenation (`implementation defined` vs `implementation-defined`) | 29 | 1.000 | yes | pass | pass | pass | `refuted_present` (sanctioned reformat) |
| Long one-char corruption (100 chars) | 100 | 0.995 | no | fail | **pass** (t=0.980) | pass | `ambiguous` (not `confirmed_absent`) |
| olmOCR substring trap (`max` vs `maximum`) | 3 | high | partial | fail* | varies | blocked | `ambiguous`/`refuted_present` — never `confirmed_absent` without DP |

\*Documented in `test_tests.py:174-180`.

**False-pass hypothesis:** PR #285/PR #290 class — judge quotes prose or date lines already in markdown. Source `ground_spans` retains them (`pr >= 0.90` or substring). Without candidate refute at `T_cand_hi`, sidecar labels them `"absent from markdown"` (`00-baseline.md:37-38`). Short-quote path: olmOCR `D=2` alone would refute `"alpha beta"` reformat (`pr=0.889 >= 0.778`) without DP — acceptable refute; the danger is the inverse, declaring absence on a near-match long quote (`pr=0.995`) when olmOCR `D=2` passes.

**False-fail hypothesis:** PR #293 `constexpr` class — if candidate check uses whole-doc `partial_ratio >= 0.90` without DP, a 75% ratio correctly stays absent, but a longer near-miss quote at 99.5% would false-refute a genuine miss. Length-relative ambiguous band prevents that. If `D_cand=0` is applied to long quotes without substring, legitimate one-edit reformats false-confirm absence.

## What would change my mind

A labeled nine-PR replay (`00-baseline.md:11-12`) applying the proposed `(T_cand_lo, T_cand_hi)` band with `_present_within` DP confirmation, reporting per-quote `confirmed_absent | refuted_present | ambiguous` labels against human annotation, achieving evidence precision >= 0.90 with recall on the eight confirmed-absent quotes >= 0.875, OR a counterexample where `D_abs=0` plus DP at `D_cand=2` false-refutes a verified-absent PR #293 quote.
