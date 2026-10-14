# 10 - Consolidated Persona Findings (25 Personas)

## Repo Analysts (01-12)

### 01 olmocr-bench-analyst
**Verdict:** usable-with-conditions
**Top finding:** Source-anchored pass/fail unit tests (7,010 tests) are the right architecture for MC4 and partial MC3. Replace aggregate golden comparison with JSONL fact-check layer: `TextPresenceTest` + `partial_ratio` at `threshold = 1 - max_diffs/len(text)` (set `max_diffs=0` for single-char sensitivity), mined from HTML/PDF source, not from blessed converter output. No WG21 front-matter or TOC-leak rules. LLMs excluded from eval loop.

### 02 marker-hybrid-analyst
**Verdict:** usable-with-conditions
**Top finding:** Marker's `--use_llm` is a conversion correction layer with block-level reject-and-keep gates (empty JSON, length-ratio floors, table parse checks). LLM invocation gated by global flag + structural skip heuristics. Portable: lane separation, Pydantic validation, block-scoped sanity gates. **No title/author/date extraction or validation** (metadata = TOC + page_stats only). Does not close MC1.

### 03 docling-eval-analyst
**Verdict:** usable-with-conditions
**Top finding:** Dual-tail aggregation: page `parse_score` = `nanquantile(q=0.10)` over cell scores, document score = `nanquantile(q=0.10)` over pages ("worst 10% of pages"). `verify_table_v2` span-aware grid model. VLM path emits `ConversionStatus` only, no numeric per-page confidence. No source-anchored metadata/TOC validation. Golden replay freezes converter output like our bench.

### 04 MinerU-Dolphin-analyst
**Verdict:** usable-with-conditions
**Top finding:** Both are extraction pipelines, not QA judges. MinerU's `test_e2e.py` typed block checks (table substring hit-rate, `fuzz.ratio > 90`, `len(type_set) >= 4`) are the only adoptable self-scoring pattern. Dolphin adds normalization only (`truncate_repeated_tail`), zero validation. Neither addresses MC1 or MC2.

### 05 surya-nougat-analyst
**Verdict:** usable-with-conditions
**Top finding:** Nougat's `[MISSING_PAGE_FAIL:n]` markers and `varvar < 0.045` degeneration guard + Surya's `_detect_repeat_loop` → fallback with `mean_token_prob` per block. Both scope QA to page level. Zero TOC-stripping validation, no front-matter plausibility, no heading-level oracle. Surya layout emits flat labels (`Title`, `SectionHeader`, `Text`), not ATX depth.

### 06 grobid-unstructured-analyst
**Verdict:** usable-with-conditions
**Top finding:** GROBID's real metadata validation is offline four-tier field scoring against publisher gold XML (`EndToEndEvaluation` strict/soft/Levenshtein/Ratcliff). Runtime checks limited to structural rejection/demotion. `postValidation()` gate: Ratcliff >= 0.8 before merge. `Person.sanityCheck`, `DateParser.cleaning`. Unstructured: `Title`/`category_depth` are layout heuristics, not truth oracles. Neither runtime-validates metadata against source.

### 07 PyMuPDF-pdfplumber-analyst
**Verdict:** usable-with-conditions
**Top finding:** `page.get_text("dict")` yields per-span `{size, flags, font, bbox, text}` with `TEXT_FONT_BOLD=16`, `TEXT_FONT_ITALIC=2`. pymupdf4llm's `IdentifyHeaders` maps frequency-weighted body size → ranked larger sizes to `#` levels. tomd's `_detect_body_size` + `_rank_font_sizes` + section numbering is the stronger pattern whisker should mirror. pdfplumber adds char-level `fontname`/`size` but no style flags. Font size alone insufficient for WG21 (flat ladders, bold-only emphasis).

### 08 pandoc-html2text-markdownify-analyst
**Verdict:** usable-with-conditions
**Top finding:** All three map `hN` → N-level Markdown mechanically. None detect TOC leaks, validate YAML/title plausibility, or gate heading levels against source HTML. Pandoc's validation is committed golden/QuickCheck round-trip, not source-anchored fidelity. Adoptable: regression patterns (pandoc AST goldens, html2text exact micro-corpus, markdownify option-matrix tests).

### 09 markitdown-firecrawl-analyst
**Verdict:** usable-with-conditions
**Top finding:** Neither validates heading-level fidelity. Both gate on `must_include`/`toContain` substring anchors + monotonic `str.find()` section-order chains. Metadata (title, `statusCode`, og*) tested as separate axis from body. Pattern whisker needs for MC1/MC4: separate metadata axis, not more `ref_nid` slack.

### 10 table-tools-analyst
**Verdict:** usable-with-conditions
**Top finding:** camelot/img2table/tabula-java detect PDF/image geometry (ruled lines, contours, projection profiles). None parse markdown separators — no repo uses a more permissive dash regex than whisker's `-{2,}`. Fix `_TABLE_SEP_RE` against GFM/CommonMark spec (`|-|-|` = one hyphen per column). Optionally port camelot's `(accuracy/100)*(1-whitespace/100)` as reference-free table sidecar.

### 11 opendataloader-PDFKit-analyst
**Verdict:** usable-with-conditions
**Top finding:** opendataloader's `check_regression` gates corpus means (`nid_mean`/`teds_mean`/`mhs_mean >= threshold - 0.02`) and ignores per-document scores. Whisker adopted null-eligibility in `bench.py` and per-paper `GUARD_AXIS_SLACK=0.02` but not corpus-mean backstop. PDF-Extract-Kit YOLO-classifies 10 element types, drops table/figure blocks with no validation.

### 12 langextract-analyst
**Verdict:** usable-with-conditions
**Top finding:** Monotonic exact-DP + `char_interval is None` drop already in whisker's `grounding.py`. No metadata/TOC/golden-divergence fixes for MC1-MC4. Only tightens MC5 evidence anti-hallucination. Optional: plural stemming (~7 LOC) and treating document-level fuzzy quotes without locatable intervals as lower-trust.

## Miss-Class Hunters (13-20)

### 13 Front-Matter-Truth-Auditor
**Verdict:** usable-with-conditions
**Proposed checks (all deterministic, stdlib-only):**
1. **Title≠first-H2:** Normalize+compare front-matter `title` to first body `## ` heading (strip section prefix/trailing TOC page nums). ~5 lines.
2. **Reply-to shape:** Flag when `len>5`, any entry lacks `EMAIL_RE`, or entry matches `_NON_AUTHOR_RE`. ~4 lines.
3. **Date presence:** If page-0/1 `missing_regions` sample matches `date\s+\d{8}` and FM has no `date` key, hard-fail. Requires `score.py` to pass `missing_regions`. ~3 lines.
**Prior art:** olmOCR uses source-anchored binary metadata facts; GROBID runs per-field header sanity but no doc-level pass/fail.

### 14 TOC-Leak-Detective
**Verdict:** usable-with-conditions
**Proposed checks (all deterministic, stdlib-only, in `gates.py` or new `toc_detect.py`):**
1. **Duplicate heading:** Fence-aware ATX scan, normalize (strip trailing `\s+\d{1,4}$`, collapse ws, lower). If normalized text repeats and earlier heading had trailing page digit, fail.
2. **Page-number heading:** `^#{1,6}\s+\d+(?:\.\d+)*\s+\S.+\s+\d{1,4}\s*$` (section prefix required so `## Step 1` not flagged).
3. **TOC label/table:** Body line `^(?:#{1,6}\s+)?(?:table\s+of\s+contents|contents)\s*$` (case-insensitive), or early 2-column pipe table whose last column is mostly `\d{1,4}`.
**Wire as hard gate `no_toc_leak` in `gates.py`.**

### 15 Photocopy-Golden-Detector
**Verdict:** usable-with-conditions
**Proposed detection (deterministic, advisory only):**
- `detect_photocopy_ideal()` in `golden_ideals.py`: when ideal-panel NID >= 0.99 AND MHS/recall >= 0.99 AND `difflib.unified_diff` after `normalize_for_exact_lane` is <= ~10 lines, emit soft flag `"ideal may be uncurated photocopy of converter output (advisory)"`.
- Optional reconcile: diff ideal vs fresh `tomd_markdown(source)` (docx-parse-eval pattern).
**tomd already blocks byte-identical seeds at bless time** (`is_unedited_seed`); whisker lacks the near-photocopy warning.

### 16 Sub-Resolution-Diff-Stratege
**Verdict:** usable-with-conditions
**Simplest MC4 fix:** Add `ideal_diff_lines` (count of `difflib.unified_diff` lines after `normalize_for_exact_lane`) on candidate-vs-ideal. Advisory review when > 0. PR #294's dropped period is invisible because `metrics.clean_string` strips punctuation before NID/TEDS/MHS/content_recall.
**Caveat:** Exact diff fails MC3 photocopy-golden (both sides share the bug). Needs independent ideal correction.

### 17 LLM-Calibration-Skeptic
**Verdict:** usable-with-conditions
**Key findings:**
1. Evidence-count gate half-built: `ground_spans` drops hallucinations, but empty-evidence passes still sanctioned. RULERS-style rule: `pass` + 0 grounded quotes + source outline present → demote to `review`.
2. `SIGNAL_AXIS_CONFLICT` works only for pass+fail contradictions; uniformly-wrong passes have no internal conflict.
3. **Remove front-matter truth from LLM scope** (it only sees markdown). Validate YAML vs source deterministically (MC1).
4. **Heading-level NOT fixable by LLM** even with outline injection (#282 false-clear, #295 false-positive). Need deterministic source-vs-markdown outline diff.
5. Bias-adjusted calibration requires labeled holdout first.

### 18 Heading-Ground-Truth-Extractor
**Verdict:** usable-with-conditions
**Top finding:** pymupdf4llm's `IdentifyHeaders` implements deterministic font-size clustering: `page.get_text("dict")` → round `span["size"]` → char-weighted mode = body → up to 6 larger sizes map to heading levels. A whisker `pdf_outline.py` mirroring `html_outline.py` can oracle PDF heading levels and title-on-page-0 for MC1/MC5.
**Conditions:** WG21 papers with flat font ladders will mis-level. Prefer `doc.get_toc()` + `TocHeaders` when present; else size cluster + trailing-page-number heuristics. Bold is styling-only, not heading detection.

### 19 Table-Separator-Robustness
**Verdict:** Confirmed: `|-|-|` is valid GFM (delimiter cells need one or more hyphens, per GFM §4.10).
**Fix:** Change `-{2,}` to `-+` in both `tables.py:36` and `gates.py:132`. Export one shared constant from `tables.py`. Risk low: bare `---` HRs excluded by existing `|`-in-line guard. No existing test should break; add parametrized case for single-dash separators.

### 20 Gate-Fold-Skeptic
**Verdict:** usable-with-conditions
**Analysis:** `_is_benign_region_only` (`score.py:234-238`) requires every soft flag to contain `"misaligned region"`. Advisory `ref_nid` string doesn't match, so p3953r0 correctly stays `review`.
**Recommendation:** Prefer demoting oracle `ref_nid` to report-only (like `ref_teds`/`ref_mhs`) until corpus-calibrated. Narrow fold extension (fold sole advisory `ref_nid` when `unigram_coverage >= 0.95`) is second-best. **Never fold ideal-panel flags** (ideals are ground truth).

## Process Personas (21-25)

### 21 Prior-Research-Archaeologist
**Verdict:** usable-with-conditions
**Finding:** hybrid-llm-scoring and per-page-judging are largely implemented. MC1-MC5 fixes documented in prior research but NOT implemented: front-matter truth gate, TOC-leak signal, ideal-vs-source divergence warning, independent reference/byte diff, labeled calibration protocol. Also: heading_monotone demotion and `REGION_SOFT_COUNT > 1` (raised in opus-B, persona 24, persona 10).

### 22 Whisker-Boundary-Guardian
**Verdict:** All five MC fixes can stay under `packages/whisker/src/whisker/`.
**Key findings:**
- PyMuPDF imported in `tapetum_llm/` but NOT declared in whisker — add to `tapetum-llm` optional extra.
- All cross-package imports are read-only public API.
- MC1-MC4 deterministic fixes: extend `gates.py`, `score.py`, `golden_ideals.py`.
- MC5 LLM fixes: stay in `tapetum_llm/`.
- **Any proposal to modify tomd/pipeline for whisker QA is a boundary violation.**

### 23 Simplicity-Skeptic
**Effort rank (LOC, existing files, stdlib only):**
1. MC3 photocopy warning: ~3 LOC in `score.py` `_decide` (soft)
2. MC4 sub-resolution: ~5 LOC in `score.py` (soft)
3. MC2 TOC leak: ~10 LOC in `gates.py` (hard gate)
4. MC1 front-matter: ~12 LOC in `gates.py` (hard gate)
5. MC5 LLM backstop: ~18 LOC (strip FM from adjudicate.py prompt + deterministic outline compare + fusion cap)
**Rejected:** new modules/deps, Platt/VERDI calibration, ideal-vs-source divergence pipelines, abstraction factories.

### 24 Test-Suite-Auditor
**Coverage gaps:**
- `test_gates.py`: front-matter only checks key-presence; p1122r3 pinned as `front_matter_valid: true`.
- No TOC/duplicate-heading tests.
- No photocopy-golden or sub-resolution tests.
- **`test_tables.py` does not exist** — `parse_pipe_tables` / single-dash untested.
- `test_fusion.py` has full matrix.
- `test_html_outline.py` is extraction-only.
**Each MC fix needs a PR-replay regression test** using the actual PR data that would have caught the original defect.

### 25 Steelman
**What WORKS:** PR #286 three-lane agreement + `uncertain_count=1`; PR #293 LLM independently found 31 dropped `constexpr` at conf 0.95; p0957r8 closed end-to-end via `screen_pages`; `clear_blocked_missing_region` prevents LLM upgrade; ungrounded quotes dropped; rubric-bleed annotated.
**Fix regression risks:**
- Relaxing `_TABLE_SEP_RE` can false-detect pipe-adjacent prose as tables.
- Blunt title≠first-heading gate can false-flag papers whose title genuinely matches opening section.
- Narrowing `llm_clear_soft_review` would undo proven queue shrink (72 review→pass clears).
