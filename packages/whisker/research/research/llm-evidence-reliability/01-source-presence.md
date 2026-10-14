# 01 - Source-Presence Auditor

**Verdict:** usable-with-conditions (+ monolith and page paths need a unified, stricter source-presence contract; document-wide `partial_ratio` and `normalized_text`-only hits must not be promoted to verified source presence without tier provenance)
**Confidence:** high

## Recommended precision-first source-presence contract

A quote is **source-present** only when it locates in the **same corpus the judge saw**, via an ordered tier ladder that records how it matched. Candidate absence is a separate axis (Persona 02).

```text
source_presence(quote, source_corpus) -> present | absent | ambiguous

source_corpus:
  monolith: normalize_textlayer(pages) after clean_pages
            (textlayer.py:190-204; injected at pdf_judge.py:464,496)
  page escalation: _dehyphenate(cleaned_pages[N-1])
            (pdf_judge.py:561-573)

tiers (precision-first, stop at first hit):
  1. exact: monotonic token DP (_select_monotonic_matches, grounding.py:102-168)
     + post-alignment guard (grounding.py:221-224)
     -> status exact, char interval required
  2. normalized_substring: norm_quote in norm_corpus
     (normalized_text via metrics.py:338-340)
     -> status normalized, no char interval
  3. length_relative_fuzzy: threshold = 1.0 - MAX_DIFFS / len(norm_quote)
     scoped to the relevant corpus unit (whole doc OR one page)
     (olmOCR pattern; already in ground_page_quotes, grounding.py:272-274)
     -> status fuzzy_scoped
  4. ambiguous: near-miss only; never counts as verified present

reject for source presence:
  - langextract LCS fuzzy (resolver.py:717-787; accepts gapped spans,
    fuzzy_alignment_cases_test.py:213-236)
  - document-wide partial_ratio at EVIDENCE_FUZZY_FLOOR (grounding.py:232-237)
    as a verified-present tier (candidate-lane tolerance, not source oracle)
  - any match whose raw slice fails the post-alignment guard when exact tier fired

provenance (required in sidecar/evidence schema):
  source_axis: present | absent | ambiguous
  source_tier: exact | normalized | fuzzy_scoped | none
  source_corpus: textlayer_whole | textlayer_page_N
  char_interval: (start, end) when exact tier succeeds
```

**Why this contract:** LangExtract proves source support only (`resolver.py:811-813`: unaligned extractions keep `char_interval is None`). LitRAG and olmOCR-Bench add deterministic locate-before-judge and bidirectional presence tests (`05-web.md` Q1/Q2). Whisker already has the exact DP port and page-scoped olmOCR fuzzy; the gap is applying them consistently to PDF source text and not reusing candidate-markdown fuzzy policy for source oracle duty.

## Findings

- [CRITICAL] Monolith source grounding reuses `ground_spans()` built for **candidate markdown**, not PDF text layer. Docstring targets markdown (`grounding.py:10-12,175-191`); `pdf_judge.py:513-520` passes `pdf_text` anyway. Tier 3 is document-wide `partial_ratio` (`grounding.py:232-237`), while page escalation uses length-relative `ground_page_quotes` (`grounding.py:244-278`, `pdf_judge.py:572-574`). **Impact:** identical quote can pass/fail differently across monolith vs page paths; precision is path-dependent.

- [CRITICAL] Sidecar reason overstates verification. `to_sidecar_dict()` labels every retained quote `"present in PDF text layer, absent from markdown"` (`pdf_judge.py:401-404`) but post-hoc code only runs source locate (`pdf_judge.py:513-520`); no candidate check exists. **Impact:** 8/20 candidate-absence precision in replay (`00-baseline.md:14-24`) is invisible in provenance; operators trust a bidirectional claim from a one-sided proof.

- [HIGH] LangExtract LCS fuzzy is correctly **excluded** from whisker; porting it would be unsafe for source presence. LCS accepts gapped spans (`langextract/tests/fuzzy_alignment_cases_test.py:213-236`, `resolver.py:1377-1404`); whisker runtime rejects the same gapped quote (`gapped_whisker_ground_spans: 0 1`, reproduced 2026-07-16). **Impact:** current omission is sound; any future "parity" port would inflate false-pass source presence.

- [HIGH] Exact monotonic DP + post-alignment guard is sound and should anchor tier 1. Port matches langextract `_select_monotonic_matches` (`resolver.py:1113-1185` vs `grounding.py:102-168`); guard blocks wrong-span emission (`grounding.py:221-224`, rationale at `grounding.py:14-21`). Tests lock successive-occurrence mapping (`test_tapetum_llm.py:1273-1288`). **Impact:** safe to adopt as the precision-first source oracle core.

- [HIGH] Source corpus consistency with LLM input is sound on the monolith path. `normalize_textlayer()` states LLM and verifier share output (`textlayer.py:190-196`); same `pdf_text` is injected and grounded (`pdf_judge.py:464,496,519`). **Impact:** quotes dropped as hallucinated truly were not in the judge's source view (modulo tier slack).

- [MED] `normalized_text()` is punctuation-insensitive and can false-pass source presence. Runtime: `normalized_text('value, therefore, is 42') in normalized_text('value therefore is 42 percent')` → `True` (2026-07-16). Tier-2 alone cannot prove verbatim PDF copy the prompt demands (`pdf_judge.py:188-191`). **Impact:** tier-2 hits should be `ambiguous` or `normalized`, never promoted to highest-confidence "present" without exact tier or scoped fuzzy confirmation.

- [MED] Dehyphenation is applied only on the page-escalation grounding path, not monolith `pdf_text`. Page path: `_dehyphenate(cleaned_pages[...])` before `ground_page_quotes` (`pdf_judge.py:561-573`); monolith uses raw `normalize_textlayer` join without dehyphenation (`pdf_judge.py:464`). Runtime: hyphen-split quote grounds fuzzy on monolith, exact on dehyphenated page (`hyphen_split_monolith: ['fuzzy']`, `hyphen_split_page_dehyphenated: ['implementation strategy']`, 2026-07-16). **Impact:** monolith tolerates more slack (fuzzy) than page path (exact); unified contract should dehyphenate source corpus once upstream.

- [LOW] `ground_page_quotes` page scoping is sound. Test proves document-wide presence does not rescue off-page quotes (`test_pdf_judge.py:771-778`). Length-relative threshold is documented (`constants.py:176-181`, `grounding.py:272-274`). **Impact:** page escalation source-presence logic is the better precision template for the monolith.

## False-pass hypothesis

Judge quotes `"value therefore is 42"` from PDF text containing `"value, therefore, is 42 percent."` Tier-2 `normalized_substring` accepts (`norm_collision: True`, runtime 2026-07-16) even though the quote is not a verbatim slice of the text layer. Under current code the quote is retained as source-grounded and sidecar-labeled absent from markdown (`pdf_judge.py:401-404`), inflating evidence precision failures.

## False-fail hypothesis

Judge copies a running header/footer line verbatim from raw page text before `clean_pages` stripping. `normalize_textlayer` removes lines on ≥30% of pages (`textlayer.py:145-163,190-204`). Quote is absent from the verifier corpus and dropped (`ground_spans`/`ground_page_quotes` drop path, `grounding.py:238-239,275-276`) despite the model having seen the raw page in a page-scoped prompt. Precision-safe (furniture should not be missing-content evidence per `pdf_judge.py:190-192`) but counts as source-presence false-fail if header lines are quoted.

## What would change my mind

A labeled replay on the nine-PR holdout showing that restricting monolith source presence to exact + normalized + length-relative fuzzy (dropping document-wide `partial_ratio`) does not increase source-presence false-fails (dropped hallucination rate) while reducing retained quotes later found present in markdown.
