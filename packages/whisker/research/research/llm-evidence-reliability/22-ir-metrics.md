# 22 - Information-Retrieval Metrics Analyst

**Verdict:** usable-with-conditions — whisker already owns the right IR primitives for quote-level verification, but they are split across modules, tuned for different tasks, and the PDF lane applies them one-sided; a precision-first cascade is adoptable without BM25 or new dependencies.
**Confidence:** high

## Findings

- [CRITICAL] **Evidence precision is 40% because candidate-side IR is missing.** Evidence: nine-PR replay (`00-baseline.md:11-24`) — 20 LLM "missing-content" quotes, 8 genuinely absent, 12 already present in markdown; `pdf_judge.py:513-520` grounds quotes only against the PDF text layer via `ground_spans(spans, pdf_text)`; sidecar still labels retained quotes `"present in PDF text layer, absent from markdown"` (`pdf_judge.py:401-404`). Impact: no IR metric on the candidate can fire until a symmetric check exists; document-level `content_recall` cannot repair quote-level false absence.

- [HIGH] **`content_recall` is the wrong granularity for quote absence.** Evidence: `metrics.py:372-389` — multiset bag-of-words recall over the whole reference/candidate; `pdf_judge.py:287-312` — per-page screen uses `content_recall(tomd_md, dehyphenated_page)` with floor 0.90 (`constants.py:154`). Impact: a quote whose tokens are scattered across the document or duplicated (PR #290 date lines twice, `00-baseline.md:18`) can yield high page recall while the verbatim span is present; conversely a localized drop can flag a page without proving which LLM quote is absent. Quote verification needs span/window IR, not corpus recall.

- [HIGH] **Whole-document `partial_ratio` is the dominant false-absence enabler if copied to the candidate side unchanged.** Evidence: olmOCR `TextPresenceTest.run` (`olmocr/bench/tests.py:167-182`) — `best_ratio = fuzz.partial_ratio(reference_query, md_content) / 100.0` against the full page/markdown; whisker ports the length-relative threshold in `ground_page_quotes` (`grounding.py:272-274`, `constants.py:176-181`) but `ground_spans` fuzzy tier still compares against the entire markdown (`grounding.py:233-236`, `EVIDENCE_FUZZY_FLOOR = 0.90`, `EVIDENCE_MIN_FUZZY_CHARS = 20`). Impact: PR #285/#290 false absence claims would likely flip to `present` with normalized containment or windowed match on the candidate; a naive whole-doc ratio keeps precision low on short quotes.

- [HIGH] **Best-window substring edit distance is the strongest existing quote-level scorer.** Evidence: `facts.py:276-321` — `fuzz.partial_ratio_alignment` locates a candidate window, then `_substring_edit_distance` (free-start/free-end Levenshtein DP) verifies within `max_diffs`; olmOCR uses the same length-relative budget pattern (`tests.py:168-169`: `threshold = 1.0 - max_diffs/len(query)`). Impact: this is the precision-first core for candidate absence: declare `present` when windowed edit distance ≤ budget; declare `absent` only when source-side pass AND candidate-side fail; route near-threshold hits to `ambiguous` (`05-web.md:183-190`, CRAG pattern).

- [MED] **Normalized containment is high-precision but recall-poor on legitimate reformats.** Evidence: `grounding.py:230-231` — `norm_quote in norm_md` after `normalized_text` (`metrics.py:88-126`, OmniDocBench `clean_string`: strips punctuation/markdown); exact token tier uses monotonic DP (`grounding.py:171-228`, langextract port). Impact: containment correctly kills PR #285/#290 false absences when checked on markdown; it false-fails dehyphenation (`test_pdf_judge.py:697-720` — without `_dehyphenate`, page recall drops below floor). Containment belongs as tier-1 `present`, not the sole absence oracle.

- [MED] **PyMuPDF and pdfplumber disagree on extraction surfaces; source-side IR must pin one path.** Evidence: whisker PDF lane uses PyMuPDF `page.get_text("text", sort=True)` (`textlayer.py:82-85`) plus header/footer stripping (`textlayer.py:132-187`, threshold 0.30) and dehyphenation before recall (`pdf_judge.py:100-108`); pdfplumber rebuilds text from `LTChar` via geometric clustering (`pdfplumber/page.py:498-536`, `utils/text.py:233-279` — `y_tolerance`, `x_density`, ligature expansion). PyMuPDF QA asserts exact word strings with geometric tolerance (`PyMuPDF/tests/gentle_compare.py:6-27`); pdfplumber is pdfminer-layout order, not MuPDF block sort. Impact: a quote can ground in PyMuPDF text but not in pdfminer/markitdown oracle text; source-presence and candidate-absence must share one normalized surface per side, with extractor version recorded (`05-web.md:53`, LitRAG locate-before-judge).

- [MED] **Document-level edit distance (`text_nid`) is advisory-only for quotes.** Evidence: `normalized_edit_distance` / `text_nid` (`metrics.py:64-78`, `350`); PDF judge demotes pass when `nid < PDF_JUDGE_NID_FLOOR` (0.80) or `content_recall < PDF_JUDGE_RECALL_FLOOR` (0.85) (`pdf_judge.py:527-537`, `constants.py:141-142`). Impact: whole-doc NED hides localized quote presence (12/20 false absences occurred with healthy document averages); keep NID/recall as verdict demotion signals, not quote evidence scorers.

- [LOW] **BM25 is not implemented and is not justified for v1.** Evidence: grep over `packages/whisker/src` finds no BM25; `05-web.md:192-194` — lowest-risk path is olmOCR-style checks from existing `ground_spans`, `ground_page_quotes`, `rapidfuzz`, markdown normalization. Impact: BM25 sliding windows would add ranking complexity and tuning surface without beating windowed edit distance on short verbatim quotes; skip unless windowed Levenshtein plateaus on labeled holdout.

## Metric comparison for quote presence / absence

Scores below are for a single LLM quote `q` against haystack `H` (source PDF text layer or candidate markdown). "Absent claim retained" means the pipeline labels the quote as genuinely missing from the candidate.

| Metric | Mechanism in whisker / olmOCR | Present signal | Absent signal | Precision on absence | Recall on absence | Primary failure mode |
|--------|------------------------------|----------------|---------------|----------------------|-------------------|----------------------|
| **Containment** | `norm_q in norm_H` (`grounding.py:230-231`) | substring hit after `normalized_text` | no substring | **High** when checked on candidate | Low under dehyphenation/markdown markup | Legitimate reformat drops substring hit → false `absent` |
| **Token recall** | `content_recall(H, q)` multiset (`metrics.py:372-389`) | most quote tokens appear somewhere in `H` | low recall | **Low** — scattered/duplicate tokens pass | Moderate for dropped paragraphs | PR #290-style duplicates: recall high, quote present |
| **Edit distance (whole doc)** | `text_nid(q, H)` | high NID | low NID | Low — quote is tiny vs document | Low | Dominated by non-quote text; not quote-local |
| **Edit distance (best window)** | `_best_match` / `_substring_edit_distance` (`facts.py:276-321`) | min edits ≤ `max_diffs` in aligned window | min edits > budget | **High** with length-scaled budget | **High** with dehyphenation | Near-threshold typos → needs `ambiguous` band |
| **BM25 best window** | not implemented | top window score | score below cutoff | Untested (likely medium) | Untested | Tuning + dependency cost; redundant with Levenshtein window |
| **Best-window ratio** | `partial_ratio(q, H)` whole haystack (`olmocr/bench/tests.py:169`, `grounding.py:233-236`) | ratio ≥ `1 - max_diffs/len(q)` | ratio below threshold | **Low** on short quotes vs whole document | High | Generic phrases match anywhere in `H` → false `absent` retention |

**Asymmetry today:** source-side uses containment + whole-doc fuzzy + exact token DP (`ground_spans` on `pdf_text`); candidate-side is **unchecked** for PDF missing-content quotes. Markdown adjudication grounds evidence on the candidate only (`tapetum_llm.md:181`), the inverse failure mode.

**Recommended bidirectional use (olmOCR + ALCE pattern, `05-web.md:13-18`, `74-76`):**

1. `source_present` := exact token DP OR containment OR page-scoped length-relative ratio on PDF text (page quotes already scoped: `ground_page_quotes`, `grounding.py:244-278`).
2. `candidate_present` := same tier order on markdown, but fuzzy tiers MUST use **window-local** `_best_match`, not whole-document `partial_ratio`.
3. Label:`absent` iff `source_present` AND NOT `candidate_present` at strict tier; `present` iff `candidate_present`; `ambiguous` if source or candidate passes fuzzy-only or edit distance ∈ (τ_strict, τ_loose].

## Precision-first composite metric

Optimize **evidence precision**, not verdict recall (`00-baseline.md:24`). Definitions on labeled quote set `Q`:

- `TP_abs`: claim absent, source_present, candidate absent (strict tiers)
- `FP_abs`: claim absent, candidate_present (the 12/20 replay failures)
- `FN_abs`: claim absent, source_present, candidate absent fails but human says absent
- `Amb`: routed to ambiguous (abstain; do not count as absent)

**Primary metric:**

`evidence_precision = TP_abs / (TP_abs + FP_abs)`

**Secondary guardrails** (report, do not optimize first):

- `evidence_recall = TP_abs / (TP_abs + FN_abs)`
- `abstention_rate = |Amb| / |Q|`
- `source_grounding_precision = source_located / source_claimed` (hallucinated PDF quotes)

**Operational rule (precision-first):**

> Retain a missing-content quote in the sidecar only when `source_present` is exact or containment AND `candidate_present` fails at the **strict** windowed-edit budget; fuzzy-only agreement on either side demotes to `ambiguous` and does not increment `TP_abs`.

This inverts today's policy: a candidate hit **overrides** an LLM absence claim (LitRAG pattern, `05-web.md:59-61`).

## Threshold learning plan

**Phase 0 — Seed labels (immediate, n=20):**

1. Transcribe the nine-PR replay quote set (`00-baseline.md:14-19`) into `{quote, pid, source_page?, label: absent|present, failure_class}`.
2. Add PR #293 constexpr quotes as positive absent controls (5/5 genuine).
3. Split: 14 fit / 6 holdout (stratify by `present`/`absent`).

**Phase 1 — Per-tier threshold sweep (fit set):**

| Tier | Parameter | Search grid | Selection rule |
|------|-----------|-------------|----------------|
| Exact token DP | none | on/off | always on |
| Containment | use `normalized_text` vs raw+WS collapse variant | {norm, raw_ws} | maximize `evidence_precision` |
| Windowed edit | `max_diffs` | {0,1,2,3} × length buckets: ≤20, 21-60, >60 chars | **precision-first:** max `evidence_precision` s.t. `FP_abs / (TP_abs+FP_abs) ≤ 0.05` |
| Length-relative ratio | `PAGE_QUOTE_MAX_DIFFS` analog | {1,2,3} | only as fallback when edit window fails; same FPR cap |
| Ambiguous band | `τ_loose - τ_strict` | edit distance gap 1-2 | minimize `FP_abs` while `FN_abs` ≤ 15% |

Use the olmOCR length-relative formula as the default parameterization (`threshold = 1.0 - max_diffs / len(norm_q)`, `tests.py:168-169`), not a flat `EVIDENCE_FUZZY_FLOOR` over the full markdown.

**Phase 2 — Negative controls (must pass before promotion):**

1. Replay golden PDF pages used for `PAGE_RECALL_FLOOR` calibration (107 healthy pages, `constants.py:149-153`) — candidate checks must not invent absences.
2. Dehyphenation fixture (`test_pdf_judge.py:697-720`) — thresholds must not flag present hyphen joins as absent.
3. Front-matter migration cases — quotes appearing only in YAML must classify `present` (conversion contract, `pdf_judge.py:129-136`).

**Phase 3 — Holdout validation (promotion gate):**

- Require `evidence_precision ≥ 0.90` on holdout (≥6 quotes; widen to 30+ quotes before production promotion).
- Require `FP_abs = 0` on the PR #285/#290 date-line subset (regression lock).
- Record `(TP, FP, FN, precision, recall, abstention_rate)` in a `quote-evidence-calibration.json` artifact; promote thresholds to `constants.py` only with documented operating point (mirrors `calibrate.py` / `whisker calibrate --labels`, `17-calibration-statistician.md:36-51`).

**Phase 4 — Expand labeled corpus (target n≥100 quotes):**

1. Mine olmOCR-Bench `TextPresenceTest` / `ABSENT` pairs (`05-web.md:124-129`) as methodology, not dependency.
2. Author WG21 holdout: 30 papers × 3 quotes (absent/present/reformat) checked against source PDF + markdown.
3. Re-fit length buckets annually or on extractor bump (PyMuPDF version-keyed goldens lesson, `research/redteam/PyMuPDF.md:15-19`).

**Explicit non-goals for v1:** BM25 index, embedding retrieval, NLI entailment (`05-web.md:118-120` — later resolver for `ambiguous` only).

## False-pass hypothesis

PR #285 replay: LLM emits date-line missing-content quotes; source-side `ground_spans` passes against PyMuPDF text (`pdf_judge.py:519`), candidate-side check omitted. A whole-document `partial_ratio` or high `content_recall` on the page does not fire because the date tokens exist elsewhere. Under the proposed composite, normalized containment or windowed `_best_match` on markdown classifies `candidate_present`, blocking `FP_abs`.

## False-fail hypothesis

A `constexpr` declaration absent from markdown but present in PDF with hyphenation across line break (`transla-\ntion`): strict containment fails on both sides, but windowed edit with `max_diffs=2` after `_dehyphenate` on the source page passes while candidate still fails — correctly retained absent. If dehyphenation is applied only to the source screen (`pdf_judge.py:299`) but not to the candidate-side haystack normalization, a mirrored hyphen artifact in markdown could falsely fail containment and retain a spurious absent quote.

## What would change my mind

A labeled holdout (≥30 quotes, including the 20-quote replay superset) where window-local edit distance with learned length buckets achieves `evidence_precision ≥ 0.90` **and** misses fewer than 2 of the 5 PR #293 genuine absences — proving precision-first tuning does not sacrifice the true constexpr misses.
