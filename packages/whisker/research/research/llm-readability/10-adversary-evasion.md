# 10 - Adversary-Evasion

**Verdict:** usable-with-conditions — the olmOCR-style fact model is the right primitive, but the current 8–9 verified facts per paper, first-match table lookup, and alnum-only normalization leave large, demonstrated false-pass windows.
**Confidence:** high

## Findings

- [CRITICAL] Verified facts cover ~1.8% of P4182R0 by character (8 assertions vs 411 lines / ~25k chars). Evidence: `00-baseline.md:53-57` (8 and 9 verified facts); runtime char ratio 464/25160 on `corpus/P4182R0.expected.md`. Impact: ~98% of prose, legend text, xref targets, and table rows are ungated; an adversary can corrupt them freely while Lane 3 stays green.

- [CRITICAL] `_check_table` binds the first normalized cell match and never revisits later tables, so a decoy pipe-table can satisfy neighbors while the real table is scrambled. Evidence: `facts.py:313-323` (first-match loop); runtime on P4182R0 — prepend decoy tables after front matter, replace only the real rows (`| GPU device code (CUDA, SYCL) | No | No | No | N/A |` → Coro=Yes; `| Game consoles … | Often off | Arenas common |` → `Often on | Heap only`); all 8 verified facts pass and `run_gates` is clean. Impact: direct exploit of the CI canary class (`test_comprehension_corpus.py:77-95`); downstream LLM reads wrong Coro/Alloc cells.

- [CRITICAL] `present`/`absent`/`order` facts run on `normalized_text`, which strips every non-alnum/non-CJK character via `_CLEAN_KEEP_RE`. Evidence: `metrics.py:115-126`, `facts.py:343-348`; runtime `normalized_text('foo != bar') == normalized_text('foo == bar') == 'foobar'`. Impact: semantic flips in operators, punctuation, markdown emphasis, and `C++` tokenization (`C++20` → `C20`) are invisible to three of five fact types; prose can assert the opposite relation and still pass.

- [HIGH] `order` facts only require five short anchor phrases to appear in monotonic normalized positions, not faithful section bodies or paragraph order. Evidence: `facts.py:353-365`; `corpus/P4182R0.facts.jsonl` `section-flow` sequence (5 fragments spanning ~400 lines). Impact: swapping unrelated sentences between anchors (runtime: exchange two middle paragraphs — all 8 facts pass) preserves order while destroying local argument flow an LLM needs.

- [HIGH] Lane 0 content gating uses order-blind `unigram_coverage` with fail edge 0.85, so sentence-level shuffles that preserve token multiset can pass whisker even when reading order is broken. Evidence: `score.py:130-133`, `score.py:156-160`; `constants.py:37`; `00-baseline.md:86-88` (provisional thresholds). Impact: complements the order-fact gap — a corruption can pass both Lane 3 order anchors and the hard content gate if words are retained.

- [HIGH] Default `max_diffs=0` still allows a one-edit math false pass when `max_diffs>=1`; at `max_diffs=0`, flipping `\geq`→`\leq` correctly fails (CI canary, `test_comprehension_corpus.py:98-116`), but flipping `-G`→`+G` in the gravitational formula passes when another `-G` instance remains elsewhere in the paper. Evidence: `facts.py:350-351`; runtime Levenshtein 1 on `_math_surface`; single-replace `+G` fails, whole-doc still contains `-G` at `corpus/P4185R0.facts.jsonl:602`. Impact: presence checks are global substring, not instance-scoped; one correct copy launders arbitrarily many corrupted copies.

- [MED] Structural gates (`gates.py`) do not catch semantic table shadowing or operator corruption — only syntax (front matter, heading jumps, empty fences/tables). Evidence: `gates.py:153-161`; runtime dual-shadow corrupt markdown passes all five gates. Impact: a document can be structurally well-formed yet materially wrong for LLM consumption.

- [MED] External benchmark scale gap: olmOCR ships 7,010 deterministic assertions across 1,403 PDFs (721 presence, 1,020 table, 3,385 math). Evidence: https://olmocr.allenai.org/papers/olmocr.pdf (Table 3, cited in `05-web.md` Q1). Our corpus has 8+9 verified facts on 2 papers (`00-baseline.md:77-79`). Impact: evasion surface shrinks with density; current coverage is orders of magnitude below the adopted reference design.

## False-pass hypothesis

On `P4182R0.expected.md`, insert two decoy pipe-tables immediately after YAML front matter that reproduce the verified cell/neighbor patterns for `tableA-gpu-coro-no` and `tableB-console-alloc`. Then scramble only the real Table A GPU row (Coro `No`→`Yes`) and Table B console row (`Often off | Arenas common`→`Often on | Heap only`) using row-unique replacement strings so decoys are untouched. All 8 verified facts pass (`check_facts` green), all structural gates pass, yet a downstream LLM answering "Does GPU device code support coroutines?" or "What alloc strategy do game consoles use?" reads the corrupted primary tables. TabVerse reports mean cell-lookup accuracy ~9.9% even on honest tables (https://arxiv.org/html/2606.09578v1, `05-web.md` Q2), so feeding deliberately wrong primary grids is a high-impact failure mode Lane 3 currently certifies as safe.

## False-fail hypothesis

A faithful conversion that renders a verified math anchor with a Unicode relation glyph (e.g., `≥` instead of `\geq`) or a table cell with an en-dash variant outside the neighbor `max_diffs` budget could fail a verified `math` or `table` fact despite being semantically correct for an LLM reader. Evidence: `_math_surface` lowercases and folds LaTeX but is strict at `max_diffs=0` (`facts.py:173-181`, `facts.py:333-334`); olmOCR uses richer math verification (KaTeX layout, `05-web.md` Q1). Impact: brittle encoding/format variants reject good markdown while adversarial shadows pass.

## What would change my mind

Demonstrate that a dual-shadow + dual-scramble corrupt markdown fails after (a) table facts require matching on ALL occurrences or a heading-anchored table identity, not first-match (`facts.py:313-323`), and (b) P4182R0 carries ≥40 verified facts spanning every table row, code/xref surfaces, and operator-sensitive prose — with CI canaries for each exploit class above — re-run blind read-back at 8/8 (or 40/40) on the corrupted artifact and show failure.
