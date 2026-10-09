# 18 - Grounding-Engineer

**Verdict:** usable-with-conditions — our path already ports langextract's best tier (monotonic exact DP + post-alignment guard) and correctly rejects their LCS fuzzy tier; the remaining gap is demotion policy (`adjudicate.py:296-310`) not using the `exact`/`fuzzy` status we already emit, plus optional plural-stem token normalization.
**Confidence:** high

## Side-by-side algorithm map

| Stage | Whisker (`grounding.py`) | Langextract (`resolver.py`) |
| --- | --- | --- |
| Tokenize | `\w+` regex, lowercased, char offsets (`grounding.py:49-67`) | `RegexTokenizer` / injectable tokenizer; per-token `char_interval` (`resolver.py:1250-1260`, `align:372-385`) |
| Tier 1 exact | Monotonic occurrence DP (`grounding.py:102-168`, `201-204`) | Same DP (`resolver.py:1103-1232`, applied `942-953`) |
| Post-exact guard | Raw slice must re-normalize to quote (`grounding.py:221-228`) | None — interval trusted from token boundaries (`resolver.py:1224-1230`) |
| Tier 2 partial | *(absent)* | difflib `SequenceMatcher` blocks → `MATCH_LESSER` if `accept_match_lesser=True` (`resolver.py:956-1013`, default `accept_match_lesser=True` at `328-330`) |
| Tier 3 fuzzy | Normalized substring OR document-wide `partial_ratio >= 0.90`, min 20 norm chars (`grounding.py:230-237`, `constants.py:67-73`) | LCS subsequence + coverage `>= ceil(n×0.75)` AND density `>= 1/3` (`resolver.py:56-58`, `1360-1387`, `711-781`); legacy sliding-window ratio fallback (`685-707`, `1044-1053`) |
| Per-span coupling | Exact DP is global; fuzzy tiers evaluated per span independently (`grounding.py:210-239`) | Exact DP global; losers compete for difflib/LCS; overlapping batch can drop valid shorter spans (`resolver.py:1015-1019`, `1187-1188`) |
| Output | `GroundedSpan(status, start?, end?)` — dropped if none (`grounding.py:53-60`, `238-239`) | `alignment_status` ∈ `{MATCH_EXACT, MATCH_LESSER, MATCH_FUZZY, None}` + `token_interval` + `char_interval` (`resolver.py:999-1013`, `780-780`) |
| Normalization | `normalized_text` = LaTeX fold + strip to alnum/CJK (`metrics.py:118-126`, `338-340`) | Lowercase tokens + light plural stem on fuzzy path only (`resolver.py:1263-1268`, `745`) |

## Findings

- [HIGH] **Monotonic exact DP is already aligned; our post-alignment guard is the critical delta langextract lacks.** Evidence: identical frontier DP in both (`grounding.py:102-168` vs `resolver.py:1103-1175`); we reject intervals whose raw slice fails `normalized_text(markdown[start:end]) == norm_quote` (`grounding.py:221-228`); langextract sets `MATCH_EXACT` from token indices alone (`resolver.py:1224-1230`). Impact: langextract can pin a wrong char span when token alignment and normalized surface diverge; our guard closes that failure mode and is the right selective adopt (already shipped).

- [HIGH] **Overlapping / multi-occurrence behavior diverges after Tier 1.** Evidence: both map repeated identical quotes to successive non-overlapping exact occurrences (`grounding.py:179-181`, `test_tapetum_llm.py:1189-1204`; `resolver.py:1109-1113`). **Trace — overlapping batch:** source `"Patient with arthritis is prescribed Naprosyn."`, model outputs E1 `"Naprosyn"` then E2 `"arthritis"` (or interleaved order). Langextract: monotonic DP + fuzzy fallback can leave one extraction at `char_interval=None` when the longer chain wins overlap budget (`resolver.py:1146-1175`, `1015-1019`; regression `resolver_test.py:1024-1057` cited in `research/langextract/12-false-negative-hunter.md:20`). Whisker: spans not in exact `selection` fall through per-span (`grounding.py:216-239`); both `"naprosyn"` and `"arthritis"` are `normalized_text` substrings → both `GROUND_FUZZY` kept (`grounding.py:230-231`). Impact: langextract false-fails valid overlapping evidence; we false-pass neither but may keep fuzzy-only quotes langextract would drop.

- [HIGH] **Unicode / whitespace / hyphenation: same token splits, different fuzzy recovery.** Evidence: whitespace — `clean_string` deletes all `\t/\n` and non-alnum (`metrics.py:121-126`); quote `"Hello world test"` vs md `"Hello   world   test"` → normalized identity → `GROUND_FUZZY` substring (`grounding.py:230-231`, `test_tapetum_llm.py:61-70`). Langextract: tokenizer emits separate word tokens; Tier 1 exact on `["hello","world","test"]` → `MATCH_EXACT` with char interval (`resolver.py:1224-1230`). Hyphenation: both split `"Napro-syn"` into two tokens (`\w+` at `grounding.py:49`; langextract `resolver_test.py:922-941`). Punctuation: our exact tier strips commas in normalization but post-guard realigns to raw `"value, therefore, is 42"` (`grounding.py:221-228`, `test_tapetum_llm.py:1226-1234`); langextract has no char-level fold — NFC/NFD mismatch fails all tiers (`resolver.py:1254-1260`, `tokenizer.py:329-330` per `research/langextract/12-false-negative-hunter.md:10`). Impact: we are **more lenient** on punctuation/whitespace via `normalized_text`; langextract is **stricter** on Unicode compatibility forms but **more lenient** on reordered tokens via LCS.

- [CRITICAL] **Do not adopt langextract Tier 3 (0.75 / density 1/3): it accepts gapped wrong spans our design deliberately rejected.** Evidence: `_accept_lcs_match` requires `matches >= ceil(extraction_len × 0.75)` and `matches/span_len >= 1/3` (`resolver.py:56-58`, `1381-1387`); oracle test expects extraction `"metformin hydrochloride tablet"` grounded to a nine-token clinical-noise window (`fuzzy_alignment_cases_test.py:213-222`, cited `research/langextract/11-false-positive-hunter.md:8`). Whisker docstring explicitly excludes this tier (`grounding.py:19-21`). Our Tier 3 is document-wide `partial_ratio >= EVIDENCE_FUZZY_FLOOR` (`grounding.py:186-187`, `constants.py:67`) — coarser location, but **no invented localized composite span**. Impact: adopting 0.75 LCS would regress inspect trust and violate fidelity; keep 0.90 `partial_ratio` or tighten further, not loosen.

- [HIGH] **`MATCH_LESSER` granularity would improve demotion rules; our binary grounded/dropped leaves signal on the table.** Evidence: langextract lesser branch accepts prefix-only alignment (`resolver.py:1003-1008`, default `accept_match_lesser=True` at `328-330`); **trace:** source `"Section 3.2 describes the algorithm in detail"`, quote `"section describes the algorithm"` → `MATCH_LESSER` span `"Section"` only (3/4 tokens absent from interval). Whisker: same quote → `partial_ratio` 0.929 ≥ 0.90 → `GROUND_FUZZY` kept, no interval (`grounding.py:232-237`, `constants.py:67`). Adjudicate demotes only on `not grounded` (`adjudicate.py:299-310`) — treats one `GROUND_FUZZY` quote like `GROUND_EXACT`; sidecar already records `status` (`adjudicate.py:329-331`, `inspect_report.py:104-106`) but demotion ignores it. Impact: **adopt the concept, not the algorithm:** demote `pass` → `review` when surviving evidence is exclusively `GROUND_FUZZY` (analogous to distrusting `MATCH_LESSER`/`MATCH_FUZZY` for certification); optionally require `GROUND_EXACT` when a non-pass axis cites evidence.

- [MED] **Threshold 0.75 vs 0.90: different false-pass/false-fail frontiers, neither dominates.** Evidence: langextract **misses** `"headache and fever"` vs `"Patient reports back pain and a fever."` — 2/4 tokens = 0.50 < 0.75 (`resolver.py:1383-1387`; `resolver_test.py:1601-1619`). Langextract **accepts** gapped 75%+ subsequence matches with wrong intervening tokens (above). Whisker **misses** reorderings that clear 0.75 token coverage but fall below 0.90 `partial_ratio` on the collapsed document string. Whisker **accepts** long-document `partial_ratio` without locality — mitigated by `EVIDENCE_MIN_FUZZY_CHARS=20` (`constants.py:69-73`, `grounding.py:232-234`, `test_tapetum_llm.py:1214-1224`) but not eliminated for ≥20-char boilerplate (`research/llm-stack/22-grounding-robustness-auditor.md:7`). Impact: lowering to 0.75 would increase fuzzy accepts; raising above 0.90 would increase drops on legitimate OCR/punctuation drift. Calibrate on tapetum span-drop telemetry, do not transplant langextract constants.

- [MED] **Plural stemming is the one low-cost langextract normalization worth porting to Tier 1 tokens.** Evidence: `_normalize_token` strips trailing `s` when `len>3` and not `ss` (`resolver.py:1263-1268`); applied on LCS path (`resolver.py:745`). Whisker exact tier compares raw lowercased `\w+` tokens only (`grounding.py:63-67`, `197-199`) — `"tables"` vs `"table"` fails exact, may still pass fuzzy substring/ratio. Impact: ~7 LOC stem helper before `_find_token_occurrences` would reduce false drops without opening gapped-span acceptance.

- [LOW] **Architecture question alignment:** langextract grounding validates LLM *extractions* (product path `annotation.py:404-431`, `00-baseline.md:34`) but does not gate CI; whisker grounding validates advisory *evidence quotes* and feeds fusion demotion (`adjudicate.py:296-310`, `fusion.py:124-252`). Same DP lineage; different trust contract — we already treat grounding as fail-soft demotion, not accept/reject, matching ecosystem pattern (`05-web.md` Q4 cascade cards).

## Divergent-case trace sheet (paper)

| Case | Whisker branch | Langextract branch |
| --- | --- | --- |
| Repeated quote ×2 in doc | Exact DP → successive `GROUND_EXACT` intervals (`grounding.py:216-227`) | `MATCH_EXACT` successive (`resolver.py:1109-1113`, `1224-1230`) |
| Reordered quote `"problems heart"` | Exact miss → fuzzy: collapsed substring miss → ratio maybe (`grounding.py:229-237`) | LCS subsequence → `MATCH_FUZZY` if ≥0.75 coverage + ≥1/3 density (`resolver.py:757-780`, `1360-1387`) |
| Gapped 3-token clinical noise | Fuzzy ratio may pass; **no** char interval (`grounding.py:231-237`) | `MATCH_FUZZY` with **wrong** 9-token `char_interval` (`resolver.py:774-780`, oracle `fuzzy_alignment_cases_test.py:213-222`) |
| Prefix paraphrase lesser | `GROUND_FUZZY` if ratio ≥0.90 (`grounding.py:232-237`) | `MATCH_LESSER` prefix span only (`resolver.py:1003-1008`) |
| Short boilerplate `"the following"` (<20 norm chars) | Dropped unless exact/substring (`grounding.py:232-234`, `constants.py:73`) | Token LCS may still align if density passes on small windows (`resolver.py:1360-1387`) |
| Overlapping `"Naprosyn"` + `"arthritis"` | Both kept via independent fuzzy substring (`grounding.py:230-231`) | Second may stay `alignment_status=None` (`resolver.py:1015-1019`) |

## Adopt / reject ledger

| Item | Verdict | Rationale |
| --- | --- | --- |
| Monotonic exact DP | **Adopted** (done) | `grounding.py:102-204` |
| Post-alignment guard | **Adopted** (done) | `grounding.py:221-228` |
| `exact`/`fuzzy` status + char interval | **Adopted** (done) | `grounding.py:46-60`, `adjudicate.py:329-331` |
| Use `status` in demotion rules | **Adopt next** | `adjudicate.py:296-310` — fuzzy-only pass demotion |
| Plural stem on token tier | **Adopt optional** | port `resolver.py:1263-1268` |
| LCS fuzzy 0.75 / 1/3 density | **Reject** | `resolver.py:56-58`, `1360-1387`; `grounding.py:19-21` |
| `MATCH_LESSER` / difflib Tier 2 | **Reject** | prefix-only wrong spans (`resolver.py:1003-1008`) |
| Lower `EVIDENCE_FUZZY_FLOOR` to 0.75 | **Reject** | loosens without locality compensation (`constants.py:67`) |

## False-pass hypothesis

Source chunk contains `"metformin … pulmonary … hydrochloride … hypertension … tablet"` with three target tokens scattered. Langextract LCS returns `MATCH_FUZZY` with a multi-word `char_interval` whose substring is mostly unrelated noise (`resolver.py:757-780`, `1360-1387`). Whisker may also keep the quote via `partial_ratio >= 0.90` on the full markdown (`grounding.py:232-237`) but emits **no** misleading char interval — inspect shows `fuzzy` not `"exact at chars X-Y"` (`inspect_report.py:104-106`). **Shared false-pass:** both can certify a paraphrase that omits intervening words; langextract adds a false **location**.

## False-fail hypothesis

Model outputs overlapping entities from `"Patient with arthritis is prescribed Naprosyn."`: quotes `"arthritis"` and `"Naprosyn"`. Langextract leaves one at `char_interval=None` after monotonic DP consumes the non-overlapping window (`resolver.py:1146-1175`, `1015-1019`). Whisker keeps both as normalized substrings (`grounding.py:230-231`). Conversely: NFC `"café"` quote against NFD source — langextract all tiers miss (`resolver.py:1254-1260`); whisker `normalized_text` likely collapses both to the same alnum surface (`metrics.py:118-126`, `338-340`) and grounds via substring.

## What would change my mind

A labeled tapetum holdout (≥30 papers, human-marked evidence quotes) showing that demoting `pass` when all evidence is `GROUND_FUZZY` reduces false-pass rate without increasing false-fail rate versus current `adjudicate.py:296-310`, **or** a merged langextract char-substring post-check that rejects LCS spans whose raw text fails `partial_ratio >= 0.90` against the extraction — would flip LCS from **reject** to **usable-with-conditions** as a Tier 3 behind our guard.
