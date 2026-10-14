# 25 - False-Negative Hunter

**Verdict:** usable-with-conditions — a candidate-side verifier that reuses `normalized_text` + `partial_ratio` at `EVIDENCE_FUZZY_FLOOR` will false-assert presence on operator, negation, revision, and sign corruptions that WG21 papers actually carry; the two-sided architecture in `00-baseline.md` §4 is right but needs surface routing and an `ambiguous` band, not a symmetric copy of `ground_spans`.
**Confidence:** high

## Findings

- [CRITICAL] **`clean_string` erases relational operators and unary signs, so corrupted markdown reads as an exact normalized substring match.** Evidence: `normalized_text` keeps alnum+CJK only (`metrics.py:115-126`, `338-339`); runtime adversarial pair `The constraint requires x >= y for all T.` (source quote) vs candidate `... x <= y ...` → both normalize to `TheconstraintrequiresxyforallT`, `ground_spans` returns `grounded=True`, `partial_ratio=1.000`, normalized substring hit (`grounding.py:206-231`; reproduced 2026-07-16). Same for `Offset by +1` vs `Offset by -1` → `Offsetby1fromthebaseindex` exact match. Impact: a two-sided check mirroring source grounding would suppress legitimate "missing/wrong constraint" quotes; olmOCR math/operator tests and whisker Lane 3 `surface: raw` / `type: math` exist precisely because this surface is blind (`facts.py:258-265`, `whisker/CLAUDE.md` comprehension section).

- [CRITICAL] **Negation deletion clears the fuzzy floor on sentence-length quotes.** Evidence: source `Implementations must not throw on empty input.` vs corrupted candidate `Implementations must throw on empty input.` → `partial_ratio=0.917`, `ground_spans` `grounded=True` at `EVIDENCE_FUZZY_FLOOR=0.90` (`constants.py:67`, `grounding.py:232-237`; runtime reproduced). Normalized strings differ (`...mustnotthrow...` vs `...mustthrow...`) but whole-document `partial_ratio` treats the 3-char gap as noise. Impact: AbsenceBench-class surface absence (`05-web.md` Q1 AbsenceBench) is exactly what alnum folding + ratio matching cannot see; candidate "present" would drop a true PDF-layer missing-negation finding.

- [HIGH] **Single-digit revision corruption (P2583R3→P2583R4) false-asserts presence at both fuzzy tiers.** Evidence: baseline replay flagged PR #293 as 5/5 genuinely absent `constexpr` declarations (`00-baseline.md:19`); adjacent class, revision-sensitive xrefs are first-class WG21 defects (`facts.py` `type: xref`, `surface: raw`). Runtime: `This paper is document P2583R3 dated January.` vs `...P2583R4...` → whole-document `partial_ratio=0.974`, `grounded=True`; the longer page-scoped pair also grounded at 0.978 against its 0.956 threshold (`grounding.py:232-237`, `269-275`; reproduced). Impact: candidate fuzzy presence would have blocked 40%-precision replay quotes that were actually correct absences; xref/revision bugs false-pass the cheapest proposed verifier.

- [HIGH] **No candidate-side verifier exists today; the sidecar label already over-claims absence without checking markdown.** Evidence: `pdf_judge.py:401-404` emits `"present in PDF text layer, absent from markdown"` for every grounded PDF quote; `ground_spans` runs only against the PDF text layer (`pdf_judge.py:513-520`, `00-baseline.md:28-44`). Planned fix is candidate locate then retain missing only when candidate fails (`00-baseline.md:61-68`, `05-web.md` olmOCR `TextPresenceTest`, LitRAG locate-before-judge). Impact: until candidate locate lands, false-negative risk is latent; once it lands naively, operator/negation/revision corruptions above become immediate false negatives on defect detection (defect present, verifier says content found).

- [HIGH] **Duplicate boilerplate can mask contradictory prose when the LLM quotes the surviving duplicate.** Evidence: broken markdown with `The proposal recommends approval` in §1 and `...rejection` in §3; quote targets approval sentence → `ground_spans` `grounded=True` (exact substring in candidate) even though the paper's operative conclusion is wrong. Reading-order / wrong-section retention is outside whole-doc ratio but inside "is this the right occurrence?" (`05-web.md` olmOCR optional first/last windows; langextract monotonic DP is source-side only, `grounding.py:171-241`). Impact: poll/wording papers that repeat boilerplate then amend it false-pass candidate presence for the stale clause.

- [MED] **`EVIDENCE_MIN_FUZZY_CHARS` blocks short table-cell and compact poll-row quotes, but only by length.** Evidence: `| Q1 | 12 | 3 |` vs `| Q1 | 21 | 3 |` → `partial_ratio=0.917` yet `grounded=False` because normalized quote length 12 < 20; `Question 1 | 12 | 3 | 1` vs `21` likewise remains blocked at ratio 0.923 because its normalized form is still below the length gate (`constants.py:69-73`; runtime). Neighbor-aware checks exist in `facts.py:_check_table` (`facts.py:360-390`) but are not wired into tapetum evidence (`00-baseline.md:46-57`). Impact: compact table digit transpositions are protected accidentally by quote length, not cell semantics; adding surrounding prose can cross the gate while preserving a high ratio.

- [MED] **`anchors.py` normalized `must_contain` inherits the same operator/negation blindness.** Evidence: `check_anchors` on `surface: normalized` uses `normalized_text(md)` (`anchors.py:121-124`, `136-137`); test documents markup stripping (`test_anchors.py:63-69`) but not operator sensitivity. A `must_contain: "x >= y"` anchor passes on `x <= y` body text after normalization. Impact: anchor tripwires and a fuzzy candidate verifier must not share one surface; raw or math surfaces already exist for Lane 3 (`facts.py:445-467`).

- [LOW] **Near-threshold corruptions (`not` deletion, `constexpr`→`const`, qualifier drop) currently fail at 0.90 but sit in an `ambiguous` band, not safe absence.** Evidence: `This design is not exception-safe` vs without `not` → ratio 0.880; `constexpr int max_size = 1024` vs `const int` → 0.857; qualifier stripped → 0.897 (all runtime, below floor). `05-web.md` CRAG / olmOCR pattern: route 0.85–0.95 to `ambiguous`, abstain from counting as present (`05-web.md` Q5 CRAG). Impact: threshold tuning alone is brittle; a single char insertion in a long quote can flip present/absent.

## False-pass hypothesis

Broken candidate markdown:

```markdown
## 3. Constraints
The constraint requires x <= y for all T.
Implementations must throw on empty input.
document: P2583R4
```

Source PDF text layer quotes the correct `>=`, `must not`, and `P2583R3` lines. A symmetric `ground_spans(candidate_md)` check returns `grounded=True` for all three quotes (operators/signs erased, negation ratio 0.917, revision ratio 0.974). Candidate presence succeeds; the quote is dropped from the missing set; the paper false-passes the absence defect the LLM correctly identified.

## False-fail hypothesis

Faithfully converted markdown with legitimate dehyphenation and markup reflow: source PDF quote `sub-\nsequent` vs candidate `subsequent`, or quote with `## Abstract` heading vs body line `Abstract`. Exact tier fails; normalized substring may fail if hyphenation changed token boundaries; only fuzzy tier saves it — but a raw-surface candidate check with zero edit budget would false-fail these as absent (`00-baseline.md` §4 legitimate exceptions; `05-web.md` chopdiff cosmetic-token pattern). Safe path: exact → normalized → fuzzy with `ambiguous` abstention, never raw-only for prose quotes.

## What would change my mind

A labeled holdout of 50 source-grounded "missing-content" quotes from the nine-PR replay (`00-baseline.md:11-19`), run through a prototype candidate locator with (a) normalized+fuzzy only vs (b) surface-routed checks (`raw` for xrefs/operators, math surface for formulas, table neighbors for cells): if (b) achieves ≥90% recall on genuine absences with ≤5% false "present" on the 12 replay false-absence quotes (#284/#285/#290), upgrade verdict to **usable**; if (a) misses ≥3 of the 5 PR #293 constexpr/revision cases or accepts ≥2 operator/negation synthetics above, keep **usable-with-conditions** and block symmetric `ground_spans` on the candidate.
