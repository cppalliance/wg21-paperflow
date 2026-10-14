# 24 - False-Positive Hunter

**Verdict:** usable-with-conditions — a candidate-side `ground_spans` leg is mandatory to stop the 12/20 false-missing sidecar labels (`00-baseline.md:14-24`), but **strict** absence (inverted `dropped` → `verified_missing` at `EVIDENCE_FUZZY_FLOOR = 0.90` with no ambiguous band) still false-verifies absence on faithful WG21 markdown for links, YAML front matter, underscore markup, HTML tables, pipe-table layout, and display math; olmOCR and Marker clones show markdown-aware normalization or block alignment is required alongside the check.
**Confidence:** high

## Findings

- [CRITICAL] **Markdown link xrefs: PDF-layer quote present in candidate, strict candidate locate fails.** Evidence: runtime `ground_spans` on candidate `See [P1234R5](P1234R5.html) for wording.` with PDF quote `See P1234R5 for wording` → `present=False`, `dropped=1`; same on `ground_page_quotes` (`grounding.py:244-278`, `PAGE_QUOTE_MAX_DIFFS=2` at `constants.py:181`); `partial_ratio(normalized_text(q), normalized_text(md)) = 0.80` < `EVIDENCE_FUZZY_FLOOR` (`constants.py:67-73`, `grounding.py:232-236`). Bracket-only form `[P1234R5]` passes (exact tier). Impact: every HTML paper with linked xrefs reproduces PR #285/#290-class false missing-content if the judge quotes PDF text without URL syntax; strict absence keeps the quote as `verified_missing`.

- [CRITICAL] **Front-matter migration: title/document live in YAML keys, not as consecutive prose.** Evidence: candidate `---\ntitle: "Paper Title"\ndocument: P2583R3\n---\n\nBody.` with quote `Paper Title P2583R3` → `present=False`; `normalized_text(q) = PaperTitleP2583R3` is **not** a substring of `normalized_text(md) = titlePaperTitledocumentP2583R3Body` (runtime); body-only `# Paper Title` heading passes. Whisker `clean_string` keeps YAML key tokens (`metrics.py:118-126`, `CLAUDE.md` front-matter field order). Impact: LLM quotes PDF cover-line prose; tomd correctly lifts metadata into YAML; strict absence flags a shippable conversion as missing title/document.

- [HIGH] **Underscore emphasis: token tier sees markup, normalized substring keeps underscores.** Evidence: candidate `This _important_ word.` with quote `This important word` → `present=False`; `_tokenize` yields `['_important_']` not `important` (`grounding.py:63-67`, post-alignment guard at `224-228`); `normalized_text` retains `_` because `\w` includes underscore (`metrics.py:118-126`). olmOCR `normalize_text` strips `(\*|_)(.*?)\1` before matching (`packages/whisker/research/repos/olmocr/olmocr/bench/tests.py:60-65`, `150-176`). Impact: strict whisker locate false-absences common `_emphasis_` and identifier-adjacent underscores that olmOCR would treat as present.

- [HIGH] **HTML tables: tag names pollute the normalized haystack, breaking cell-run quotes.** Evidence: candidate `<table><tr><td>Cell</td><td>value</td></tr></table>` with quote `Cell value` → `present=False`; `normalized_text(md) = tabletrtdCelldtdvaluedrable` vs `normalized_text(q) = Cellvalue` (runtime); olmOCR `TableTest` parses HTML/markdown grids and checks cell **neighbors**, not flat substring (`tests.py:342-381`, `tables.py` in same module). Impact: Tony/SPEC HTML-table papers (whisker `facts.py` / `tables.py` dual parser) pass comprehension checks but fail strict quote absence on row-shaped PDF quotes.

- [HIGH] **Pipe tables: PDF row-shaped quotes miss grid-normalized concatenation.** Evidence: candidate `| A | B |\n|---|---|\n| 1 | 2 |` with PDF quote `A 1 B 2` → `present=False`; `normalized_text(md) = AB12`, `normalized_text(q) = A1B2` (runtime); individual cell `1` locates. Marker `HeuristicScorer` fuzzy-aligns GT **blocks** into candidate markdown at `score_cutoff=70` (`packages/whisker/research/repos/marker-v1.10.2/benchmarks/overall/scorers/heuristic.py:25-26`, `74-82`), not flat substring. Impact: table quotes copied from PDF text layer (space-separated row) false-absence against correct pipe tables; block-window rescue needed for `ambiguous` (`05-web.md:92-94`, `03-bidirectional-design.md:44`).

- [HIGH] **Display math: LaTeX delimiters vs PDF prose quote.** Evidence: candidate `$$\n\sum_{i=0}^{n} i\n$$` with prose quote `sum from i equals 0 to n` → `present=False`; inline `$x^2$` and unicode `x²` vs `x^2` pass (exact/fuzzy). olmOCR `MathTest` renders reference LaTeX and compares rendered equations (`tests.py:549-589`), not document-wide substring. Impact: strict absence false-fails faithful display-math conversions whenever the judge quotes the PDF text layer's verbalization.

- [MED] **Strict floor without ambiguous band replicates baseline false-missing on borderline fuzzy hits.** Evidence: proposed S2 in `03-bidirectional-design.md:20-24` maps candidate `dropped` → `verified_missing`; xref case ratio `0.80 ∈ [0.85, 0.90)` would be `ambiguous` only with `CANDIDATE_AMBIGUOUS_BAND` (`03-bidirectional-design.md:44`); current sidecar already over-claims absence without any candidate leg (`pdf_judge.py:401-404`, `513-520`). Forced replay: 12/20 quotes already present in markdown (`00-baseline.md:16-21`); strict inverted-`dropped` without markup-aware haystack and gray band would **retain** link/FM/table/math-shaped subsets. Impact: evidence precision improves only if `present | absent | ambiguous` is tri-state, not binary strict.

- [LOW] **Moved text and images are not primary false-absence drivers under `ground_spans`.** Evidence: reordered sections (`Section B … Section A` with quote `Section A content`) → `present=True` exact (`grounding.py:171-241`, order-agnostic substring tier); `![Figure 1: diagram](…)` / HTML `<img alt=…>` vs caption quote → present (runtime). Impact: reordering and figure captions are safe for v1 prose locate; do not spend complexity budget here before link/FM/table/math.

## False-pass hypothesis

PDF quote `constexpr int x = 42` locates inside a markdown code fence via `normalized_text` substring (`grounding.py:230-231`) while the surrounding declaration block was dropped — strict candidate presence returns `present_in_candidate` and suppresses a genuine miss (same tradeoff as `03-bidirectional-design.md:72-74`). Mitigation: route code-axis quotes through raw-surface locate (`facts.py` `surface: raw`, `CLAUDE.md` Lane 3).

## False-fail hypothesis

**WG21 xref link:** faithful `[P1234R5](P1234R5.html)` with PDF quote `See P1234R5 for wording` → strict candidate `dropped` → false `verified_missing` (runtime above; matches PR #285/#290 replay shape in `00-baseline.md:17-18`).

**YAML front matter:** `title` + `document` in `---` block with PDF cover quote `Paper Title P2583R3` → false `verified_missing` despite metadata present (`00-baseline.md:52-53` normalization-loss class).

## What would change my mind

A labeled replay of the 20-quote holdout (`00-baseline.md:14-21`) using candidate-side locate with **markdown-aware normalization** (olmOCR `normalize_text` class stripping at `tests.py:47-80`, or raw/link-stripped haystack) plus the tri-state ambiguous band, showing ≥90% evidence precision **and** zero demotions of the 8 genuine absences (PR #293 `constexpr` block) to `present_in_candidate`.
