# Repo scan: olmOCR (olmocr/bench)

**Does it verify LLM-readability?** **yes** (partial on downstream-LLM proof: deterministic fact assertions proxy comprehension; no LLM-as-judge in the eval loop; separate continued-pretraining consumability study in the paper, not in `bench/` code)

Scanned: local shallow clone at `packages/whisker/research/repos/olmocr` (read-only).

## Findings

### Assertion taxonomy (8 test types)

Enum and loader dispatch in `olmocr/bench/tests.py`:

| Type | Class | Evidence |
|------|-------|----------|
| `baseline` | `BaselineTest` | `tests.py:26,484-545,797-798` |
| `present` | `TextPresenceTest` | `tests.py:27,128-182,789-790` |
| `absent` | `TextPresenceTest` | `tests.py:28,177-182,789-790` |
| `order` | `TextOrderTest` | `tests.py:29,186-226,791-792` |
| `table` | `TableTest` | `tests.py:30,342-480,793-794` |
| `math` | `MathTest` | `tests.py:31,548-613,795-796` |
| `format` | `FormatTest` | `tests.py:32,230-338,799-800` |
| `footnote` | `FootnoteTest` | `tests.py:33,616-763,801-802` |

All inherit `BasePDFTest` with shared fields `max_diffs`, optional `checked`, per-page `(pdf, page, id)` binding (`tests.py:83-112`).

### Baseline per-page quality checks (`BaselineTest`)

Auto-injected for every PDF lacking an explicit baseline entry (`benchmark.py:241-244`). Checks:

1. **Non-empty output**: zero alphanumeric chars fails (`tests.py:514-515`).
2. **Blank-page mode**: `max_length` caps allowed alnum count; optional skip of image alt tags (`tests.py:503-512`; sample `sample_data/blanks.jsonl:1`).
3. **Repeating n-grams**: `RepeatDetector` flags tail repetition above `max_repeats` (default 30) (`tests.py:520-526`).
4. **Unexpected scripts**: regex rejects CJK blocks and emoji ranges when `check_disallowed_characters` is true (`tests.py:528-543`).

### Fuzzy matching (`max_diffs`)

Shared semantics: length-relative threshold `1.0 - (max_diffs / len(text))` on `rapidfuzz` ratios.

- **Present/absent**: `fuzz.partial_ratio` vs threshold (`tests.py:168-169,171-182`).
- **Order**: `fuzzysearch.find_near_matches` with `max_l_dist=self.max_diffs`; any before/after pair with `before_match.start < after_match.start` passes (`tests.py:214-226`).
- **Table**: cell match uses `fuzz.ratio`; neighbor checks reuse per-string threshold with **hard floor 0.5** (`tests.py:395-396,415-418,442-443`).
- **Format / footnote context**: same ratio formula (`tests.py:320-326,705-725,731-749`).

Default `max_diffs=0` on `BasePDFTest` (`tests.py:100`).

### Zone-scoped presence

`TextPresenceTest` supports `first_n` / `last_n` to restrict search to header/footer zones (`tests.py:139-140,160-165`). Used in Headers & Footers stratum curation (`README.md:230`).

### Table: pipe + HTML, rowspan/colspan

- `TableTest.run` parses **both** markdown pipe tables and HTML `<table>` unless `ignore_markdown_tables` (`tests.py:360,398-404`).
- HTML path: BeautifulSoup extracts `rowspan`/`colspan`, builds occupancy grid and multi-neighbor relation sets (`table_parsing.py:390-444,82-260`).
- Markdown path: pipe tables only; all spans assumed 1x1; row 0 / col 0 treated as headings (`table_parsing.py:263-341`).
- README states max table score requires HTML for merged cells (`README.md:265-266`).

### Math: KaTeX render + relative symbol geometry

- Reference equation rendered at test construction via Playwright + KaTeX (`tests.py:561-564`; `katex/render.py:377-411`).
- Candidate: extract `$...$`, `$$...$$`, `\(...\)`, `\[...\]`; exact string match short-circuit, else render each hypothesis sorted by `fuzz.ratio` (`tests.py:567-608`).
- `compare_rendered_equations`: MathML inner containment, else backtracking match on span bounding boxes preserving up/down/left/right neighbor relations (`katex/render.py:414-549`).

### Human verification workflow

- Schema: `checked: "verified" | "rejected"` (`TestChecked` enum `tests.py:36-38`; field `tests.py:101`).
- Flask `review_app.py`: queues PDFs with unchecked tests (`checked is None`), displays PDF + facts, POST `/update_test` mutates any field including `checked`, `/reject_all` bulk-rejects (`review_app.py:26-35,127-166`).
- Dataset curation: LLM-assisted draft (GPT-4o / Gemini per stratum) then manual review (`README.md:218-234`).
- **Note:** benchmark scorer runs **all** loaded tests regardless of `checked`; provenance gate is dataset curation discipline, not enforced in `benchmark.py` (contrast whisker `facts.py:124-130`).

### Scoring harness

- Per-test binary pass; multi-repeat outputs pass if **majority** of repeats pass (`test_avg > 0.5`, `benchmark.py:103-126`).
- Overall = **macro-average of per-JSONL pass rates**, not micro over all 7,010 tests (`benchmark.py:343-350,387-388`).
- Bootstrap CI resamples within JSONL strata (`benchmark.py:328-330`; `utils.py` cited in redteam).
- Closed corpus: exit if any `(pdf, page)` lacks tests (`benchmark.py:246-251`); duplicate IDs rejected at load (`tests.py:860-865`).

### RLVR reward reuse

Training reuses the same `test.run()` path:

- `olmocr_bench_reward` loads tests by ID from JSONL, calls `test.run(completion)` per test (`grpo_train.py:638-656,1093-1166`).
- Reward = pass fraction (micro) or macro-average of per-`type` pass rates when `--reward_bench_macroavg` (`grpo_train.py:1153-1166`).
- Covered by `tests/test_grpo.py` (`test_grpo.py:266-382`).

### Normalization (all text checks)

`normalize_text`: `<br>` fold, markdown bold/italic strip, whitespace collapse, NFC, smart-quote/hyphen map (`tests.py:47-80`).

### Engine meta-tests

`tests/test_tests.py` contains **100** `def test_` cases exercising normalize, fuzzy boundaries, table adjacency, math render, footnotes, duplicate IDs (redteam cited 148; current clone count is 100).

### What olmOCR-bench has that whisker `facts.py` LACKS

Ranked by comprehension coverage gap:

1. **`format` facts** (heading/bold/italic must wrap specific text) — no whisker type (`tests.py:230-338` vs `facts.py:59-64`).
2. **`footnote` facts** (marker placement + before/after context) — no whisker type (`tests.py:616-763`).
3. **`baseline` quality gate** (empty page, repeat-ngram degeneration, disallowed scripts) — not in Lane 3 (`tests.py:484-545`; whisker structural overlap only in live `gates.py`, not fact JSONL).
4. **Zone-scoped `first_n`/`last_n` presence** — whisker has no header/footer zone assertions (`tests.py:160-165`).
5. **`case_sensitive` toggle** on presence — whisker always normalizes via `normalized_text` (`tests.py:138,156-158` vs `facts.py:343-344`).
6. **KaTeX geometric math equivalence** — whisker uses `pylatexenc` structural surface, not rendered layout (`katex/render.py:414-549` vs `facts.py:173-181,350-352`).
7. **HTML table graph with rowspan/colspan** — whisker pipe-table grid only, exact cell locate first-match-wins (`table_parsing.py:390-444` vs `facts.py:261-323`).
8. **Table fuzzy ratio + 0.5 neighbor floor** — whisker exact cell match + Levenshtein on neighbors (`tests.py:395-443` vs `facts.py:317-334`).
9. **`top_heading` / `left_heading` vs single `heading` neighbor** — whisker collapses heading axes (`tests.py:357-358,464-468` vs `facts.py:70,300-301`).
10. **Per-page closed corpus + auto baseline injection** — whisker has 2 papers, no page-level closure (`benchmark.py:241-251` vs `00-baseline.md`).
11. **Repeat-majority voting** for stochastic OCR — whisker assumes deterministic tomd (`benchmark.py:103-126`).
12. **Macro-average by JSONL stratum in rollup** — whisker macro-averages by fact *type* within a paper, not document-class strata (`benchmark.py:387-388` vs `facts.py:139-156`).
13. **Scale**: ~7,010 human/LLM-authored tests vs 17 verified facts (`README.md` / HF card vs `00-baseline.md`).

## Portable to whisker (ranked)

1. **BaselineTest trio** ported as optional `baseline` fact type or Lane-3 pre-check: non-empty, tail n-gram repeat cap, script filter (`tests.py:514-543`). Low dependency; catches model collapse olmOCR catches early.
2. **`first_n`/`last_n` on present/absent** for furniture strip regression (`tests.py:160-165`). Maps directly to WG21 header/footer noise.
3. **`format` and `footnote` fact types** — closes tapetum_llm axes with deterministic gates (`tests.py:230-338,616-763`).
4. **HTML table parser path** for merged-cell papers; keep pipe path for simple tables (`table_parsing.py:390-444`).
5. **Length-relative fuzzy + 0.5 table floor** already partially mirrored; adopt olmOCR table cell `fuzz.ratio` locate before neighbor Lev (`tests.py:395-418`).
6. **Macro-average by stratum** in guard/bench reports (document class or HTML/PDF), matching anti-collapse invariant (`benchmark.py:387-388`).
7. **KaTeX render compare** for math-heavy corpus members — heavy (Playwright); defer unless `#254` math paper joins corpus (`katex/render.py:377-549`).
8. **Engine meta-test depth** — expand whisker fact-engine tests toward `test_tests.py` coverage (100 cases).
9. **RLVR pattern** — not for whisker QA gate, but documents that the same `check_facts` engine could feed training rewards if ever needed (`grpo_train.py:644-656`).

## Cross-check vs redteam report

Reference: `packages/whisker/research/redteam/olmocr.md`.

| Redteam claim | Scan verdict |
|---------------|--------------|
| ~7 JSONL strata × thousands of binary fact assertions, not scalar snapshots | **Confirms** (`benchmark.py:79-137,387-388`; 8 types in `tests.py:23-33`). |
| Normalization + length-relative `max_diffs` | **Confirms** (`tests.py:47-80,168-169`). |
| Macro-average per JSONL category | **Confirms** (`benchmark.py:343-350,387-388`). |
| 148 meta-tests on assertion engine | **Partially confirms** — 100 `def test_` in `tests/test_tests.py` at scan time (direction correct, count lower). |
| Eight assertion classes with no whisker guard equivalent | **Confirms**; scan adds explicit evidence for `baseline`, `format`, `footnote`, zone-scoped presence, KaTeX geometry. |
| `checked: verified` human workflow | **Confirms** (`tests.py:36-38`; `review_app.py:26-166`). **Nuances:** olmOCR bench does not gate on `checked` at score time; whisker does (`facts.py:124-130`). |
| RLVR reuse of bench scorer | **Confirms** (`grpo_train.py:644-656,1093-1166`; `test_grpo.py:266-382`). |
| No LLM in eval loop | **Confirms** — pure Python + optional headless KaTeX. |

No material contradictions. Scan adds: baseline/format/footnote classes, HTML-span table requirement, KaTeX neighbor geometry, and explicit gap list vs whisker `facts.py`.
