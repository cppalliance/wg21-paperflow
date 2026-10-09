# 11 - False-Positive-Hunter

**Verdict:** usable-with-conditions — the aligner routinely emits `MATCH_FUZZY` / `MATCH_LESSER` spans whose `char_interval` text is not the extraction (gapped noise, prefix-only lesser, duplicate-span reuse); safe only if callers tighten `accept_match_lesser`, raise the fuzzy threshold, and post-verify span text.
**Confidence:** high

## Findings

- [CRITICAL] LCS fuzzy accepts gapped spans whose matched substring is mostly unrelated source noise. Evidence: `_best_lcs_spans` + `_accept_lcs_match` at threshold 0.75 and density 1/3 (`resolver.py:1287-1404`, constants `resolver.py:57-58`); oracle test expects a 9-token window for a 3-token extraction (`fuzzy_alignment_cases_test.py:213-235`). Runtime reproduce: source with tokens planted every 4 positions yields `MATCH_FUZZY` span `'metformin pulmonary antibiotics assessment hydrochloride hypertension pressure with tablet'` for extraction `'metformin hydrochloride tablet'` — 6 intervening tokens grounded as if evidence.
  Impact: visualization and downstream consumers treat the span as provenance; users see a "grounded" extraction anchored to text the model never emitted.

- [HIGH] `accept_match_lesser=True` (default) grounds paraphrases to prefix-only spans, not the full extraction. Evidence: lesser branch at `resolver.py:1009-1014`, default `accept_match_lesser=True` at `resolver.py:335`; runtime: source `'Section 3.2 describes the algorithm in detail'` + extraction `'section describes the algorithm'` → `MATCH_LESSER` span `'Section'` only (3 of 4 tokens absent from span). **Shared with whisker:** `partial_ratio` 0.929 ≥ `EVIDENCE_FUZZY_FLOOR` 0.90 (`grounding.py:51`, `constants.py:50`) — both accept the paraphrase; langextract additionally pins a wrong char span.
  Impact: dual false positive — quote "grounded" while neither system verifies the full phrase; langextract adds a misleading highlight location.

- [HIGH] Duplicate extractions when the source has only one occurrence reuse the first span for the second (`MATCH_FUZZY`). Evidence: `resolver_test.py:2564-2574` (`test_duplicate_extractions_with_single_occurrence_share_span`); monotonic DP + fuzzy fallback leave second extraction at `first.char_interval` with `AlignmentStatus.MATCH_FUZZY`.
  Impact: ordered extraction lists imply distinct provenance; the second item is grounded to a span that cannot be its source.

- [HIGH] LCS fuzzy accepts partial extractions, grounding to a dense suffix and dropping leading/wrong tokens. Evidence: `_lcs_fuzzy_align_extraction` tries decreasing k and accepts first passing gate (`resolver.py:763-771`); regression test `test_sparse_max_match_falls_back_to_dense_submatch` (`fuzzy_alignment_cases_test.py:491-514`). Runtime: extraction `'alpha beta gamma delta'` on noisy source → `MATCH_FUZZY` span `'beta gamma delta'` (missing `'alpha'`); extraction `'alpha beta gamma delta'` on `'alpha beta gamma'` → `MATCH_FUZZY` span `'alpha beta gamma'` (trailing `'delta'` ungrounded).
  Impact: 75% coverage gate (`ceil(n×0.75)`) treats wrong-token tail/head as success; char_interval understates or misstates what was extracted.

- [MED] Reported wrong `char_interval` for CJK, accented Latin, and emoji (character-level wrong-span). Evidence: Issue #334 (https://github.com/google/langextract/issues/334), summarized in `05-web.md` Q5; tokenizer merge fixes in PR #350 / PR #479 target `RegexTokenizer` but issue class is wrong-span acceptance, not rejection.
  Impact: non-ASCII WG21 papers (author names, standardese in multiple scripts) get visually "grounded" highlights at shifted offsets — worse than `None` for audit trails.

- [MED] Light plural stemming in `_normalize_token` (`resolver.py:1275-1281`) lets fuzzy tiers match stem-collapsed tokens across distinct words. Evidence: suffix strip when `len>3`, ends with `s`, not `ss`; runtime lesser match `'class run'` → span `'class'` in `'The class runs fast. The glass breaks.'`. **Shared with whisker:** `normalized_text` substring check passes the same quote (`grounding.py:49-50`).
  Impact: both stacks accept stem-normalized quotes; langextract assigns a span that omits the second token entirely (`MATCH_LESSER`).

- [MED] Production logs show `MATCH_FUZZY` on few-shot example text that is not verbatim in the prompt template. Evidence: Issue #246 (https://github.com/google/langextract/issues/246), `05-web.md` Q5; maintainer guidance that examples must be verbatim — fuzzy proceeds with warnings by default.
  Impact: spurious grounding on prompt examples propagates into validation UX and falsely calibrates trust in the aligner.

- [LOW] Tie-break policy prefers earliest equal-length LCS span, so repeated identical phrases ground to the first occurrence when disambiguation by extraction order is unavailable. Evidence: `test_tie_break_earliest_start` (`fuzzy_alignment_cases_test.py:336-339`); `_best_lcs_spans` "earliest start wins" comment (`resolver.py:1296-1297`). Legacy difflib path scans all windows and picks max ratio without occurrence index (`resolver.py:651-674`).
  Impact: single-extraction calls on documents with repeated boilerplate ("Note:", "Draft", section numbers) highlight the wrong instance.

## False-pass hypothesis

Source: `'Section 3.2 describes the algorithm in detail.'` LLM extraction: `'section describes the algorithm'` (paraphrase, reordered casing). LangExtract: `MATCH_LESSER` span `'Section'` (`resolver.py:1009-1014`). Whisker: kept (`partial_ratio` 0.929 ≥ 0.90, `grounding.py:51`). Both falsely certify grounding; langextract also returns an incorrect, truncated highlight.

## False-fail hypothesis

none found — this persona hunts wrong-span acceptance; false rejects are persona 12's mandate.

## What would change my mind

A shipped post-alignment invariant test (or default gate) that rejects any aligned extraction whose source span normalized text is not a supersequence of the extraction tokens at the configured threshold, with zero known regressions on the 522-test suite and Issue #334 fixed — demonstrating wrong-span acceptance is closed, not documented.
