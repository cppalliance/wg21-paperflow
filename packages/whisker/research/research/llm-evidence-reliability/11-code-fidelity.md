# 11 - Code-Block Fidelity Specialist

**Verdict:** usable-with-conditions — whisker already has fence-aware gates and raw-surface `code` facts, but tapetum evidence grounding and the PDF judge's one-sided proof normalize away the operators, brackets, and indentation that make C++ code semantically checkable; adopt fence-local raw checks before any prose normalizer touches a quote.
**Confidence:** high

## Findings

- [CRITICAL] **`normalized_text()` erases code semantics before grounding can use them.** `clean_string()` keeps only alnum + CJK (`metrics.py:115-126`), stripping `::`, `<<`, `>>`, `!=`, `()`, `[]`, `template`, and backticks. `ground_spans()` tiers 2–3 compare `normalized_text(quote)` against `normalized_text(markdown)` (`grounding.py:206-236`). Impact: an LLM quote like `constexpr int operator<<` grounds as `constexprintoperator` and can false-match prose elsewhere; operator/template/underscore distinctions needed for WG21 code are destroyed before absence is decided (`00-baseline.md:52-53`).

- [CRITICAL] **PDF judge proves source presence only; candidate absence for code is never verified.** `pdf_judge.py:513-520` grounds quotes against the PDF text layer via `ground_spans(spans, pdf_text)`; `to_sidecar_dict()` labels every survivor `"present in PDF text layer, absent from markdown"` (`pdf_judge.py:401-404`) without a candidate locate pass. PR #293's five `constexpr` quotes were genuinely absent (`00-baseline.md:19`), but PR #285's five date-line quotes were already present (`00-baseline.md:17-18`) — the same machinery would overstate absence for code reformatted inside fences or split across lines. Impact: code-missing claims need a second, fence-local candidate check (`05-web.md / Q1 / olmOCR-Bench`, `05-web.md:182-190`).

- [HIGH] **Whisker grounding tokenization is word-only and fence-blind.** `_TOKEN_RE = re.compile(r"\w+")` (`grounding.py:49-67`) ignores fence boundaries; exact tier aligns token subsequences anywhere in the document. Identifiers with underscores survive (`\w` includes `_`), but `::`, angle brackets, and stringized operators are not tokens, so alignment can succeed on identifier words while template brackets or `operator<<` differ. Impact: port olmOCR's bidirectional locate (`05-web.md:14-18`) on **extracted fence bodies**, not whole-document `\w+` windows.

- [HIGH] **Lane 3 `code` facts are the right surface but too narrow for quote-level evidence.** `FACT_CODE` uses `_raw_surface` (whitespace collapse only, operators/case preserved) with `max_diffs` edit budget (`facts.py:258-266`, `468-472`); corpus examples are short needles (`p4234r0.facts.jsonl:4-5`). No check for fence integrity, per-line indentation, language tag, or block completeness. Impact: reuse `_raw_surface` + `_present_within` inside fence extractors, not `normalized_text`, for candidate-side quote verification; extend facts to multi-line `constexpr` blocks for PR #293-class omissions.

- [HIGH] **MinerU preserves code structure in fences; marker does not tag language.** MinerU renders `CODE_BODY` as ` ```{guess_lang}\n{code}\n``` ` with `line.rstrip()` only (`pipeline_middle_json_mkcontent.py:287-297`), guesses language via Magika (`guess_suffix_or_lang.py:73-84`), and strips nested fence markers with `code_content_clean()` (`visual_magic_model_utils.py:69-86`). Marker `CodeProcessor` rebuilds indentation from bbox/avg char width (`marker/processors/code.py:19-47`), emits `<pre>` without a language tag (`marker/schema/blocks/code.py:13-17`), and `Markdownify` correctly skips whitespace collapse inside `<pre>` (`marker/renderers/markdown.py:241-247`). Impact: fence-local raw match should tolerate **missing/wrong lang tag** and **rstrip-only** line endings, but not reflowed lines or lost leading spaces; MinerU's `guess_lang` is advisory, not semantic equivalence.

- [HIGH] **Marker LLM refinement can rewrite code-bearing complex regions.** `LLMComplexRegionProcessor` instructs ` ``` ` code blocks (`marker/processors/llm/llm_complex.py:24`) and accepts rewrites down to 50% of extracted length (`:84-86`); benchmark `MarkdownCleaner` collapses all whitespace to single spaces (`marker/benchmarks/overall/scorers/clean.py:30-31`), which would destroy indentation in evaluation. Impact: never use marker-style global whitespace normalization for whisker code evidence; LLM-refined blocks are a false-pass source if quotes are verified only against PDF text.

- [MED] **Deterministic gate catches empty fences only, not semantic code loss.** `no_empty_code` fails on ` ``` ` pairs with no non-blank inner lines (`gates.py:115-129`); `no_toc_leak` is fence-aware in tests (`test_gates.py:149`). `unigram_coverage` tokenizes prose via `normalized_text` and is blind to in-fence identifier swaps when those tokens recur elsewhere (`research/persona/23-false-negative-hunter.md:10`, `18`). Impact: P3104R5 `template`→`typedef` / `constexpr`→`volatile` inside the first fence still passes (`opus-B-gate-soundness.md:24`); structural gates do not close the code-fidelity gap.

- [LOW] **Block matching deliberately drops fenced code from prose alignment.** `split_paragraph_blocks()` skips fence contents (`match.py:74-88`), so bench `block_text_nid` never scores code blocks. Impact: correct for prose NED; reinforces that code evidence must be a **separate axis** with its own extractors, not folded into `text_nid` or `content_recall`.

## False-pass hypothesis

PR #285-class: PDF judge quotes `constexpr float frexpf(...)` from the text layer; candidate markdown contains the same tokens inside a ` ```cpp ` fence but with one lost template argument or `operator`→`operator ` reflow. Source `ground_spans` passes on PDF text; document-level `partial_ratio(normalized_text(quote), normalized_text(md))` passes because identifiers survive `clean_string`; sidecar emits `absent from markdown` with no fence-local raw check — a false missing-content claim, or worse, a false pass if the corrupted fence still shares enough `\w+` tokens with the quote.

## False-fail hypothesis

Legitimate tomd output uses ` ```c++ ` vs source ` ```cpp `, or rstrip-trailing-space per MinerU convention, or moves a trailing `// see [library.c]` comment to the preceding prose line. A candidate verifier that normalizes language tags or collapses intra-fence whitespace would false-fail faithful conversions while the code remains executable-equivalent for a human reader.

## Proposed evidence checks (do not normalize semantic code away)

All checks run **deterministically** on extracted fence bodies first; prose `normalized_text` is forbidden for code quotes. Emit `present | absent | ambiguous` per quote (`05-web.md:182-190`).

1. **Fence extraction (prerequisite).** Parse candidate markdown fence-aware (reuse `gates._iter_body_lines` / `chunking.py:168-187` pattern). Record per block: `lang_tag`, raw `body`, `line_count`, `leading_ws[]` per line. Source side: extract code-like regions from PDF text layer by monospace/indent heuristics or page-screen low-recall pages; do not merge with prose.

2. **Raw-body presence (candidate tier 1).** Normalize only **outer** whitespace: strip one trailing newline after closing fence; do **not** collapse internal newlines or leading spaces. Quote `present` if `quote == body` or `quote` is a raw substring of `body` (olmOCR exact tier, `05-web.md:14-18`).

3. **Length-relative fuzzy on raw fence body only (candidate tier 2).** Apply `ground_page_quotes` thresholds (`grounding.py:272-273`, `PAGE_QUOTE_MAX_DIFFS`) to `norm_ws(body)` where `norm_ws` is **line-trim-right + single-space between lines only**, never `clean_string`. Short quotes (`< EVIDENCE_MIN_FUZZY_CHARS`, `constants.py:69-73`) require exact/raw-substring — no document-global `partial_ratio`.

4. **Operator and puncturation inventory.** For quotes containing `::`, `<<`, `>>`, `<=`, `>=`, `!=`, `&&`, `||`, `->`, `.*`, count occurrences in quote vs matched fence window; mismatch → `ambiguous`, not `absent`. Preserves template/operator semantics `clean_string` deletes.

5. **Template and `requires` bracket spans.** Extract `<...>` and `requires (...)` substrings from quote and candidate window on the **raw** surface; require identical span set or literal substring hit. Catches `template<typename T>` dropped to `typename T` without folding brackets away.

6. **Underscore identifier alignment.** On raw fence lines, match `\b[A-Za-z_][\w]*\b` sequences in order (monotonic DP like `grounding.py:102-168` but on identifier tokens including `_`, not document-wide `\w+` prose tokens). `constexpr` class omissions (PR #293) fail here when declaration identifiers are missing even if `constexpr` appears in prose elsewhere.

7. **Indentation vector.** Compare per-line leading space/tab counts between quote and matched fence lines; allow ±1 space OCR slack per line, sum slack capped at `ceil(0.05 * line_count)`; larger drift → `ambiguous`. Never collapse leading whitespace to a single space.

8. **Comment-line retention.** If quote contains `//` or `/*`, require the same comment text on the same logical line index in the fence block (raw compare). Catches dropped `// see [library.c]` tails common in WG21 wording examples.

9. **Language tag (advisory only).** Record `lang_tag` mismatch (`cpp` vs `c++` vs empty) as metadata; do not flip `present`→`absent`. Empty fence still hard-fails `no_empty_code` (`gates.py:115-129`).

10. **Block completeness for omission class.** For page-screen flagged pages, require every source text-layer line matching `^\s*(constexpr|template|struct|class|enum)\b` within a code-dense window to have a fence-local identifier alignment hit; unmatched lines → `absent` with line-anchored quote, not a prose-level paraphrase.

**Routing:** retain LLM quote only when source locate passes AND candidate locate returns `absent`; `present` demotes quote; `ambiguous` abstains and demotes verdict (`05-web.md / Q5 / CRAG`, `19-calibration-skeptic.md:41`). Report code evidence precision separately from structure verdict (`05-web.md:68-68`, `00-baseline.md:95-96`).

## What would change my mind

A labeled replay of the nine-PR quote set (or a 20-quote code-heavy holdout including PR #293 `constexpr` declarations) showing fence-local raw + identifier-tier checks achieve candidate-absence precision ≥ 0.85 while false-failing fewer than 1/20 genuinely absent lines, without applying `normalized_text` or document-global `partial_ratio` to code quotes.
