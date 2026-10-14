# r14 - Cross-repo survey: does ANYONE achieve ~100% LLM verification?

**Verdict:** usable — a full targeted grep sweep of all 31 clones under `packages/whisker/research/repos/` finds zero repos that treat an LLM/VLM as a complete-recall verification instrument for conversion output; one repo (marker) uses an LLM scorer for offline benchmark triage only, and CI gates elsewhere are deterministic.
**Confidence:** high

## Findings

### Survey table (31/31 repos, grep sweep 2026-07-22)

Patterns run repo-wide (excluding binary/corpus noise where noted): `llm.*(judge|verify|check|eval|valid)`, `(gpt|claude|openai).*(eval|judge|verify|check)`, `judge.*prompt`, `verifier`, `vlm.*(judge|verify|check|eval)`, `llm_judge`, `llm-as-judge`, plus per-repo co-occurrence of `llm|gpt|claude|openai|verifier|judge|vlm` with `verify|validation|quality.?check|llm.*score|llm.*correct`. Every "Yes" row cites inspective source paths; "No" rows had no conversion-QA LLM verify hit in `.py`/`.ts`/`.java`/`.go`/`.rs` after excluding fixture corpora.

| # | Repo | LLM/VLM verifies conversion output? | Gating vs advisory | Claimed or measured recall | Evidence (file paths) |
|---|------|-------------------------------------|--------------------|----------------------------|------------------------|
| 1 | camelot | No | — | Deterministic ICDAR-style table fixtures only | `camelot/tests/test_lattice.py:11-18` (`assert_frame_equal`); no LLM hits in source |
| 2 | docling | No | — | Deterministic e2e + heuristic agent eval script; no LLM judge | VLM is extraction pipeline (`docling/datamodel/pipeline_options_vlm_model.py`); `docling-evaluate.py:133-191` is rule-based heuristics (chars/page, replacement chars), not LLM |
| 3 | Dolphin | No | — | No in-repo eval loop | README describes two-stage VLM parsing only (`Dolphin/README.md:27-28`); no verify/judge module |
| 4 | firecrawl | No | — | Scrape: deterministic `toContain`; extract: fuzzy substring counts | LLM `judgeChange.ts:9-60` judges **monitoring diffs**, not PDF/HTML→MD fidelity; post-extract LLM validation commented out (`extraction-service.ts:943-984` per r12) |
| 5 | grobid | No | — | Published per-field P/R/F1 (e.g. header Levenshtein micro recall 93.09%); instance recall far lower | `EndToEndEvaluation.java:452-466` — XPath + string tiers, no LLM stage |
| 6 | html-to-markdown-go | No | — | — | Zero LLM/judge/verify hits in source |
| 7 | html-to-markdown-py | No | — | — | `docs/llms.txt` is crawler docs, not QA; zero verify hits in `.rs`/`.py` |
| 8 | html2text | No | — | — | Zero LLM hits |
| 9 | img2table | No | — | Golden HTML/XLSX compare in tests | `tests/tables/extraction/test_extraction.py:47-79`; no LLM |
| 10 | langextract | No | — | Alignment coverage is post-hoc on **emitted** spans only | `langextract/annotation.py:407-425`, `resolver.py:322-400` — generative extract + align, not output-vs-source audit |
| 11 | markdownify | No | — | — | Zero LLM hits |
| 12 | marker | **Partial — yes for eval; in-pipeline correction, not post-hoc QA** | **Advisory only** (LLM scorer failures skipped; CI uses heuristic) | No complete-recall claim; CI floor heuristic mean ≥90, table TEDS mean ≥0.7 | Benchmark: `benchmarks/overall/scorers/llm.py:15-134` (Gemini rates markdown vs page image); failures caught and skipped `benchmarks/overall/overall.py:60-63`; CI gates **heuristic** only `benchmarks/verify_scores.py:10-22`. In-pipeline: `marker/processors/llm/llm_page_correction.py:32-36`, `llm_table.py:64` compare vision+blocks and emit corrections — producer-side, exits on "No corrections needed" |
| 13 | markitdown | No | — | 18-file `FileTestVector` anchors | `_llm_caption.py:7-50` generates image alt text during conversion, not verification; vectors in `_test_vectors.py` |
| 14 | mdream | No | — | — | Zero conversion-QA LLM verify in source |
| 15 | MinerU | No | — | External OmniDocBench scores cited in docs; in-repo e2e uses substring + fuzz | `tests/unittest/test_e2e.py:171-218`; VLM/table paths are extraction (`batch_analyze.py`) |
| 16 | node-html-markdown | No | — | — | Zero LLM hits in library source |
| 17 | nougat | No | — | Offline stratum means (Text/Table/Math); no CI golden gate | `metrics.py:39-117`; vision model is converter, not verifier |
| 18 | olmocr | **No at score time** | — | ~7k pre-authored JSONL facts; deterministic `test.run()` pass/fail | Score loop: `olmocr/bench/benchmark.py:116-117`; GPT/Gemini only in offline miners e.g. `bench/miners/mine_tables_gpt.py:131-150`; README: facts are pass/fail without judge model |
| 19 | opendataloader-bench-tmp | No | — | Corpus means: NID, TEDS, MHS, table_detection_f1, triage_recall | `src/evaluator.py:25-27`; `thresholds.json` regression on **deterministic** axes only |
| 20 | opendataloader-pdf | No | — | CLI smoke + content needles | `verification/ci-verify.py:693-696` (`must_contain` wiring checks); hybrid Hancom AI is extraction backend, not output verifier |
| 21 | pandoc | No | — | 1,078+ command-test goldens | `Command.hs:13-31`, `Old.hs:380-403` — byte-exact expected output |
| 22 | PDF-Extract-Kit | No | — | Eval docs are stubs | `docs/en/evaluation/table_recognition.rst:5`; no eval Python in tree |
| 23 | pdf-to-markdown | No | — | — | Browser demo only; no LLM verify in source |
| 24 | pdfplumber | No | — | Exact cell list assertions | `tests/test_table.py:64-74`, `76-100` |
| 25 | PyMuPDF | No | — | — | Library bindings; `pymupdf4llm` is separate clone |
| 26 | pymupdf4llm | No | — | — | Name reflects markdown **for** LLMs; layout heuristics in `src/helpers/`, not LLM QA |
| 27 | surya | No | — | External olmOCR-bench reporting; CI is GPU smoke | `surya/inference/` is VLM OCR extraction; no verify stage |
| 28 | tabula-java | No | — | Golden CSV fixtures | Java extraction only; no LLM |
| 29 | tabula-java-tmp | No | — | Same as tabula-java | Duplicate clone; no LLM |
| 30 | turndown | No | — | — | Zero LLM hits |
| 31 | unstructured | No | — | Text: cct-accuracy + cct-%missing; table: 9-metric bundle | `scripts/user/evaluate.py` (deterministic); `metrics/table/table_eval.py`; zero LLM judge in eval path |

**Headline counts:** 31 repos surveyed · **1** uses LLM/VLM to compare/rate conversion output (marker, advisory offline scorer + in-pipeline vision correction) · **0** gate CI/release on LLM verification · **0** claim or measure complete recall via LLM · **30** rely on deterministic metrics, goldens, or human-authored fact corpora for QA.

- [CRITICAL] **No repo in the 31-clone corpus treats an LLM as a complete-recall golden verifier.** The only LLM "verification" hit is marker's optional benchmark `LLMScorer` (`benchmarks/overall/scorers/llm.py:15-134`), which holistically rates page image vs markdown on 0-5 axes, skips failures (`benchmarks/overall/overall.py:60-63`), and is **not** wired into CI gates (`benchmarks/verify_scores.py:10-13` checks heuristic mean ≥90 only). In-pipeline marker LLM processors (`llm_page_correction.py`, `llm_table.py`) compare vision to extracted blocks to **produce** corrections and exit on "No corrections needed" — same subtractive funnel as whisker (`00-baseline.md:50-51`, `84-85`). Impact: confirms baseline class **5** and the recorded fact "0 of 31 surveyed document-conversion QA repos gate mechanically on LLM signals" (`00-baseline.md:82`). Answer-class: **5**.

- [CRITICAL] **The closest "high recall" pattern is olmocr's deterministic fact bench, not LLM verification.** olmocr uses GPT offline to **author** JSONL test facts (`bench/miners/mine_tables_gpt.py:131-150`), then scores with deterministic `test.run(candidate_md)` only (`benchmark.py:116-117`; r01). Recall is bounded by human/LLM-authored facts and contract encoding (wrapped `SF`, secno headings), matching PR #286/#295 failure classes (`00-baseline.md:41-44`, `59-64`). Impact: even the ecosystem's best open recall instrument is **pre-encoded deterministic QA**, not runtime LLM rediscovery. Answer-class: **1**, **5**.

- [HIGH] **Repos that embed LLM/VLM at all use it as an extraction/correction producer, not as an output auditor.** docling VLM pipeline (`pipeline_options_vlm_model.py`), MinerU/surya/nougat/Dolphin vision OCR, markitdown `_llm_caption.py:7-50`, langextract generative extract — none compare final markdown to a committed golden via LLM at QA time. firecrawl's active LLM paths are structured extract (`llmExtract.ts`) or webpage **change** judging (`judgeChange.ts:9-11`), not conversion fidelity vs source. Impact: whisker's tapetum_llm lane is aligned with marker/docling **producer** patterns, not with a missing "verification product" any peer ships. Answer-class: **5**.

- [HIGH] **Where table or heading defects are caught, the mechanism is deterministic geometry or string tiers — portable to whisker P0, not to LLM recall.** pdfplumber/camelot/img2table/tabula: cell grids + exact lists (r10); opendataloader-bench: NID/TEDS/MHS means (`evaluator.py:25-27`); grobid: XPath field recall with Levenshtein tier (`EndToEndEvaluation.java:453-461`); unstructured: `%missing` + table-structure metrics (r05). None encode bikeshed secno stripping or wrapped poll-header reading unless gold corpus does (r08 MHS, r07 section_title). Impact: PR #286/#295 are **contract-encoding + deterministic compare** problems the ecosystem solves with coded rules, not LLM judges. Answer-class: **1**, **2**, **5**.

- [MED] **Marker's LLM benchmark scorer explicitly tolerates omissions that would fail human golden review.** Prompt allows omitting "page numbers and chapter headings" for a 5/5 (`benchmarks/overall/scorers/llm.py:47`); section-header score checks detection/levels, not secno contract stripping. Combined with non-gating CI, this is **triage**, not exhaustive verification — same role whisker assigns tapetum_llm (`00-baseline.md:77-82`). Impact: even the single LLM-verify-adjacent repo does not pursue 100% recall. Answer-class: **5**.

- [MED] **Broad grep false positives confirm the bar: corpus text and unrelated "llm" tokens dominate naive hits.** camelot/tabula hits are ICDAR XML fixtures containing substring "llm"; grobid trainer TEI corpora; html-to-markdown-py `llms.txt`; firecrawl example notebooks — none are conversion QA pipelines. Targeted co-occurrence grep in `.py`/`.ts`/`.java` reduced 31 repos to **one** substantive verify-adjacent codebase (marker). Impact: the baseline's 0/31 gating claim survives a fresh sweep, not an artifact of shallow search. Answer-class: **5**.

- [LOW] **Whisker is not an outlier failure; it is an outlier ambition.** Peer repos cap QA at deterministic means, pinned goldens, or offline fact corpora with known blind spots (opendataloader first-table-only TEDS `evaluator_table.py:146-148`; grobid instance recall 10.55% strict per r07). Expecting tapetum_llm alone to name every human-verified golden defect has **no surveyed precedent**. Answer-class: **5**.

## False-pass hypothesis

Operator runs marker with `--use_llm` on P1068R11 poll pages 8-9: `LLMTableProcessor` receives HTML where upstream pdftext already shows `S` in the header cell; model returns "No corrections needed." (`llm_table.py:64`, `207-209`); deterministic CI heuristic and TEDS bench (if run) may still pass while human golden requires `SF` — identical acceptance shape to whisker LLM lane `accepted defect groups: 0/1` (`00-baseline.md:52-53`).

## False-fail hypothesis

Marker benchmark `LLMScorer` rates a bikeshed HTML paper where candidate keeps `## 1. Abstract` and source outline also shows numbered headings; section_headers score stays high because prompt checks detection/levels, not secno stripping (`llm.py:42-43`, `47`) — false-clear on PR #295 class while a strict golden contract would fail; inverse risk for whisker if LLM scorer were promoted to gate without contract encoding.

## What would change my mind

Any of the 31 clones (or whisker itself) shipping a **gated** CI step where an LLM/VLM compares every committed golden row's conversion output to source PDF/HTML (or pre-authored fact list) and published docs claim **measured recall ≥95%** on a holdout corpus for defect classes including table cells and heading normalization — with file:line evidence of that gate in `.github/` or release scripts. None found in this sweep.
