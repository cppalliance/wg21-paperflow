# 01 - olmocr

**Verdict:** usable — olmOCR-bench remains the strongest deterministic fact-assertion reference we adopted from, but our post-fix-path whisker now exceeds it on blind LLM readback proof, provenance gating, and WG21-specific fact types while still lacking format/footnote/KaTeX-geometry/span-table depth and industrial corpus scale.
**Confidence:** high

## Findings

- [HIGH] Assertion taxonomy: olmOCR still ships **8** test types (`baseline`, `present`, `absent`, `order`, `table`, `math`, `format`, `footnote`) via `TestType` enum and `load_single_test` dispatch (`olmocr/bench/tests.py:23-33,789-802`). Our `FACT_TYPES` (`packages/whisker/src/whisker/facts.py:65-76`) now has **9** types but a different split: we added `code`, `xref`, `image_ref` and `surface: "raw"` (`facts.py:78-80,257-265,451-470`) that olmOCR has no analog for; olmOCR still has **`format`** (`tests.py:230-338`) and **`footnote`** (`tests.py:616-763`) which we lack entirely. Impact: olmOCR covers heading/bold/italic wrapping and footnote marker+context; we cover code blocks, paper xrefs, and image-ref syntax — complementary gaps, not a strict superset either way.

- [HIGH] Baseline checks partially closed. olmOCR `BaselineTest` enforces non-empty output, blank-page `max_length`, tail n-gram repeat cap via `RepeatDetector`, and disallowed-script/emoji filter (`tests.py:484-545`). We ported a subset as `auto_baseline_checks` — alnum floor + repeating-ngram ratio only (`facts.py:625-674`, constants from `00-baseline.md` A3). We still lack blank-page mode, image-alt skip, and CJK/emoji rejection. Impact: olmOCR catches charset hallucinations and intentional blank pages; our auto-baseline catches vacuous-green and mojibake debris but not script pollution.

- [HIGH] Table comparison: olmOCR is stronger on merged cells; whisker is stronger on decoy disambiguation. olmOCR `TableTest` parses pipe + HTML, locates cells with `fuzz.ratio` (0.5 floor, `tests.py:395-418`), checks neighbors via a **rowspan/colspan relation graph** built by `_build_table_data_from_specs` (`table_parsing.py:82-260,390-444`), and supports separate `top_heading` / `left_heading` axes (`tests.py:357-358,464-468`). Our `tables.py` uses stdlib `html.parser` with **no span expansion** (`tables.py:80-135`) and `_check_table` does **exact** cell locate with **all-occurrence** retry plus optional `table_heading` filter (`facts.py:373-406`). Impact: olmOCR wins on Tony Tables / colspan papers; we win when duplicate cell values appear across tables (first-match-wins false-pass that olmOCR's fuzzy-first-match still risks without a heading filter).

- [HIGH] Math: olmOCR uses KaTeX render + geometric neighbor matching (`tests.py:561-608`; `katex/render.py:377-549`). We use `pylatexenc` structural surface with display-math fold and backslash undoubling (`facts.py:190-254,428-430`). Impact: olmOCR tolerates layout-equivalent paraphrases; we tolerate inline/display delimiter swaps and LLM escaping artifacts but not visually equivalent rewrites — trade-off favors olmOCR on math-heavy strata, favors whisker on zero-Node/Playwright determinism.

- [MED] Zone-scoped presence and case toggle remain olmOCR-only. `TextPresenceTest` supports `first_n` / `last_n` header/footer zones and `case_sensitive` (`tests.py:138-165`). Our present/absent always runs through `normalized_text` or `_raw_surface` with no zone scoping (`facts.py:412-427`). Impact: olmOCR can assert furniture-strip behavior; we cannot without new fields.

- [MED] No blind LLM readback in olmOCR. Repo-wide search for readback/comprehension/question-answer validation returned **zero** matches in `olmocr/bench/` and scripts. The eval loop is pure Python (+ optional headless KaTeX) per prior scan confirmation. Our `readback.py` generates blind questions per verified fact (`readback.py:106-177`), scores deterministically per type (`readback.py:180-205`), and ships `--corrupt` adversarial control (`readback.py:267-313`). Impact: we are the only side that empirically proves downstream LLM comprehension; olmOCR proxies comprehension via deterministic facts only.

- [MED] Corpus authoring: olmOCR industrial scale vs whisker lightweight heuristics. olmOCR stratifies into ~7 JSONL categories (README benchmark table: Tables, Old scans, Headers & footers, Multi-column, etc., `README.md:50-65`), drafts tests via vision-LLM miners (`bench/miners/mine_tables_gpt.py:1-15`, `mine_footnotes_gpt.py:1-13`), and human-verifies through Flask `review_app.py` (`review_app.py:26-35,127-166`). `checked: verified` is **not** enforced at score time (all loaded tests run, `benchmark.py:241-251`). Our `corpus_tools.py` classifies by markdown heuristics (`corpus_tools.py:70-94`), stratifies zero-coverage candidates (`corpus_tools.py:97-139`), drafts scaffolds with `checked: "draft"` (`corpus_tools.py:145-259`), and `check_facts` gates **only** `checked == "verified"` (`facts.py:484-489`). Impact: olmOCR has ~7,010 tests and closed per-page corpus (`benchmark.py:246-251`); we have 5 papers / 37 verified facts (`00-baseline.md`) but stronger provenance discipline and WG21-tuned draft scaffolds.

- [LOW] Scoring extras we lack: repeat-majority voting for stochastic OCR (`benchmark.py:103-126`), macro-average rollup by JSONL stratum (`benchmark.py:343-350,387-388`), RLVR reward reuse (`grpo_train.py` per prior scan). Our `FactReport.by_type` macro-averages within a paper by fact type (`facts.py:156-173`), not document-class strata. Impact: olmOCR anti-collapse scoring; not needed for deterministic tomd but documents a pattern if we scale the corpus.

## False-pass hypothesis

olmOCR `TableTest` fuzzy cell locate with a **0.5 similarity floor** (`tests.py:395-396,442-443`) can accept a near-miss decoy cell in the wrong table when the true cell is one edit away but neighbor relations belong to a different grid — especially without a `table_heading` disambiguator (whisker `facts.py:376-380`).

## False-fail hypothesis

olmOCR `MathTest` requires Playwright+KaTeX render at construction (`tests.py:561-564`); any render failure or headless-environment miss rejects structurally correct `pylatexenc`-equivalent markdown that our `_math_surface` (`facts.py:237-254`) would accept.

## Adoption candidate

**`FootnoteTest.run`** (`olmocr/bench/tests.py:655-763`) — marker detection across `[^n]`, `<sup>`, and Unicode superscripts plus fuzzy before/after context checks. License: **Apache 2.0** (`LICENSE`). Zero new runtime deps beyond `rapidfuzz` (already in whisker). Maps directly to our `STRATUM_FOOTNOTES` in `corpus_tools.py:50,89-90` and closes the largest remaining comprehension-axis gap olmOCR has that we lack.

## What would change my mind

A WG21 paper with merged-cell HTML tables where whisker `parse_html_tables` (`tables.py:124-135`) produces a wrong grid but olmOCR `parse_html_tables` (`table_parsing.py:390-444`) passes — would flip the table verdict from "whisker stronger on decoys" to "olmOCR table parser is mandatory port."
