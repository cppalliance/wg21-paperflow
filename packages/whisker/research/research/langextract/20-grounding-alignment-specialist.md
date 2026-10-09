# 20 - Grounding-Alignment-Specialist

**Verdict:** usable-with-conditions — the three-tier aligner is architecturally stronger than tapetum's boolean drop (spans, status tiers, monotonic DP), but LCS subsequence matching plus a 1/3 density gate still accepts gapped wrong spans, and CJK char_interval bugs (Issue #334) block wholesale adoption on WG21 markdown.
**Confidence:** high

## End-to-end trace (paper)

Source chunk: `"Patient has severe heart problems with fever."`  
Model extractions (output order): E1 `"heart problems"`, E2 `"heart problems"`, E3 `"problems heart"`.

1. **Tokenize** via `_tokenize_with_lowercase` → source tokens `["patient","has","severe","heart","problems","with","fever"]` (indices 0–6); each token carries a `char_interval` from `RegexTokenizer` (`core/tokenizer.py:108-131`, default at `231`).
2. **Tier 1 — monotonic exact DP** (`resolver.py:948-959`, `1113-1243`): `_find_token_occurrences` finds E1/E2 at start=3; `_select_monotonic_matches` picks E1 at 3 (weight 2), skips overlapping E2 (only one occurrence), leaves E3 unmatched. E1 gets `MATCH_EXACT`, `token_interval=(3,5)`, `char_interval` from tokens[3].start_pos .. tokens[4].end_pos plus `char_offset` (`1235-1240`).
3. **Tier 2 — difflib blocks** (`resolver.py:962-1019`): joined extraction sequence aligned via `SequenceMatcher.get_matching_blocks()`; E2/E3 still unaligned (E3 has no exact block; E2 may get lesser if a partial block exists with `accept_match_lesser=True`).
4. **Tier 3 — LCS fuzzy** (`resolver.py:1027-1065`, `717-787`): E3 tokens normalized `["problem","heart"]` (`1275-1281`); `_best_lcs_spans` finds subsequence at source indices 4,3; coverage `2/2 ≥ ceil(2×0.75)` and density `2/span_len ≥ 1/3` (`1377-1404`); sets `MATCH_FUZZY`, `char_interval` from `tokenized_text.tokens[3]` and `[4]` (`780-785`). Chunk-global offsets applied via `chunking.py:216-243` pattern.

## Findings

- [CRITICAL] LCS fuzzy accepts **gapped, semantically wrong spans** when three extraction tokens match as a subsequence inside a nine-token window. Evidence: `_best_lcs_spans` is subsequence-based, not contiguous (`resolver.py:1287-1363`); `_accept_lcs_match` passes at default `_FUZZY_ALIGNMENT_MIN_THRESHOLD=0.75` and `_FUZZY_ALIGNMENT_MIN_DENSITY=1/3` (`resolver.py:57-58`, `1377-1404`); oracle expects span `'metformin pulmonary antibiotics assessment hydrochloride hypertension pressure with tablet'` for extraction `'metformin hydrochloride tablet'` (`tests/fuzzy_alignment_cases_test.py:213-222`). Impact: adopting Tier 3 as-is would **ground evidence quotes to wrong locations**; tapetum's `partial_ratio(norm_quote, norm_md) ≥ 0.90` over the full document (`grounding.py:51`, `constants.py:50`) is coarser but does not invent a localized composite span.

- [HIGH] **Threshold semantics are not portable**: langextract gates token coverage at 0.75 plus density 1/3; tapetum gates document-level `partial_ratio` at 0.90 with no density term. Evidence: `resolver.py:57-58` vs `constants.py:50` / `grounding.py:49-52`. Impact: naïvely copying 0.75 would **loosen** fuzzy acceptance relative to our floor on short quotes; calibrating would require a labeled tapetum corpus, not a constant transplant. Issue #245 (https://github.com/google/langextract/issues/245) shows users tried `resolver_params={'fuzzy_alignment_threshold': 0.5}` and hit `TypeError` when passing keys to `Resolver(**kwargs)` (`resolver.py:261-264`); v1.6.0 `extract()` peels alignment keys first (`extraction.py:359-401`), but direct `Resolver` construction remains a footgun.

- [HIGH] **CJK and mixed-script char_interval mis-grounding** is an open failure class independent of threshold tuning. Evidence: Issue #334 (https://github.com/google/langextract/issues/334, `05-web.md:100-103`); default `RegexTokenizer` fragments CJK per grapheme (`core/tokenizer.py:249-251`, `378-383`); PR #480 substring fallback (`05-web.md:108-110`) unmerged. Impact: WG21 papers with author names, Unicode math, or non-Latin text would get shifted spans; tapetum `normalized_text` retains CJK via `clean_string` (`metrics.py:338-340`) but never emits spans, so the bug surface is lower today.

- [HIGH] **Monotonic exact DP (Tier 1) is the clearest tapetum upgrade**: repeated entity/evidence strings map to successive non-overlapping occurrences in model output order. Evidence: `_select_monotonic_matches` maximizes total matched tokens with Pareto frontier (`resolver.py:1113-1185`); `_apply_monotonic_exact_matches` assigns `MATCH_EXACT` spans (`1188-1243`). Impact: tapetum has no occurrence disambiguation (`grounding.py:43-54`); port cost ~150 LOC plus chunk `token_offset`/`char_offset` plumbing when H2 sections are triaged serially. Does not require LCS or difflib fuzzy.

- [MED] **Graded `AlignmentStatus` + `char_interval` enable inspect/trace locatability** tapetum lacks. Evidence: tiers `MATCH_EXACT | MATCH_LESSER | MATCH_FUZZY | None` set at `resolver.py:1005-1018`, `786`, `1241`; intervals derived from tokenizer char spans (`782-785`, `chunking.py:216-243`). Impact: `ground_spans` returns only kept/dropped counts (`grounding.py:34-35`); adopting status+span return shape is a clean API extension for `--inspect` without importing the full resolver. Complexity: tokenizer dependency (~514 LOC module or minimal regex port) plus interval bookkeeping per chunk.

- [MED] **Plural stemming (`_normalize_token`, lru_cache 10k)** closes a false-negative gap our substring path misses before fuzzy. Evidence: `resolver.py:1275-1281`; legacy/LCS both normalize extraction tokens (`629`, `751`). Impact: `"tables"` vs `"table"` in evidence quotes fails tapetum exact substring (`grounding.py:49`) until whole-document partial_ratio saves it; token-level stem is cheaper and localized. Port cost: ~7 LOC; must align with `normalized_text` folding rules to avoid double-normalization surprises.

- [LOW] **Legacy difflib fuzzy (Tier 3 alternate) has no density gate** and remains reachable despite deprecation. Evidence: `_fuzzy_align_extraction` scans all windows, accepts on ratio alone (`resolver.py:591-715`, `1050-1058`); Issue #188 / PR #442 migration to LCS (`05-web.md:112-114`). Impact: any tapetum port must hard-disable `legacy`; default LCS is strictly better bounded but still gapped.

## Tapetum adoption ledger (tiers vs complexity)

| langextract tier | What tapetum gains | Complexity cost |
| --- | --- | --- |
| Tier 1 monotonic exact DP | Disambiguate repeated quotes; exact char spans | ~150 LOC; per-chunk token/char offsets; lightweight tokenizer |
| Tier 2 difflib lesser | Partial exact with `MATCH_LESSER` status | +difflib join/delim protocol (`892-929`); delimiter-in-text validation |
| Tier 3 LCS fuzzy + gates | Recover reordered/gappy token overlap | +O(n·m²) per dropped span (`1293`); **mis-grounding risk**; recalibrate 0.75/0.333 vs `EVIDENCE_FUZZY_FLOOR=0.90` |
| Status + char_interval | Inspect reports show WHERE quote landed | Return-type change to `ground_spans`; no LLM change |
| Plural stem | Fewer false drops on inflection | ~7 LOC |

**Recommended selective adopt:** Tier 1 + status/span return + plural stem; keep tapetum document-level `partial_ratio` as Tier 3 fallback instead of LCS, or add a post-alignment check that `markdown[char_interval]` meets `partial_ratio ≥ 0.90`.

## False-pass hypothesis

Extraction `"metformin hydrochloride tablet"` on a gapped source with those three tokens planted every fourth position: LCS returns `MATCH_FUZZY` with a nine-token `char_interval` whose substring is mostly unrelated clinical noise (`fuzzy_alignment_cases_test.py:213-222`, `resolver.py:1377-1404`). Tapetum would still accept the quote at document level via `partial_ratio` but would not assert a wrong localized span.

## False-fail hypothesis

Extraction `"headache and fever"` against source `"Patient reports back pain and a fever."`: only `"and"` + `"fever"` overlap (2/4 tokens = 0.50 < 0.75); all tiers leave `char_interval=None` (`resolver_test.py:1601-1619`). Tapetum might still pass if `partial_ratio("headache and fever", full_md) ≥ 0.90` on a long paper where unrelated "fever" contexts inflate the score, or fail together if the score stays low — different failure boundary, not strictly more lenient.

## What would change my mind

A merged PR #480-style char-substring fallback plus multilingual oracle tests demonstrating `<1%` wrong-span rate on a WG21-representative corpus (CJK author names, en-dash headings, fenced code), with threshold sweeps proving `fuzzy_alignment_threshold` changes accept/reject on planted ambiguous spans end-to-end through `extract()` — would flip to **usable** for full three-tier adoption.
