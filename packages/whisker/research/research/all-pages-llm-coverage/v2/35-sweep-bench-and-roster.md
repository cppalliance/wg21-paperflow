# 35 - opendataloader-bench-tmp (sweep 35) + v2 roster completeness
**Claims tested:** C1
**Exhaustive:** yes for production/eval code (`src/`, `tests/`, `scripts/`, root docs, lockfiles); prediction benchmark artifacts enumerated by aggregate stats (1240 line matches / 226 files), not line-by-line (converted paper text, not code)

## Method

Search floor patterns (charter minimum, case-insensitive) run with `rg -i -n` from repo root `packages/whisker/research/repos/opendataloader-bench-tmp/`:

```
openai|anthropic|claude|gemini|google\.genai|genai|litellm|vllm|ollama|chat\.completions|completions\.create|messages\.create|generate_content|GenerativeModel|transformers|AutoModel|\.generate\(|pipeline\(|invoke|prompt|system_prompt|LLM|VLM|gpt-|llama|qwen|huggingface|api_key
```

Additional manual reads (all 26 `.py` files under `src/` and `tests/`; full file reads where hits occurred):

- `src/evaluator.py`, `src/evaluator_reading_order.py`, `src/evaluator_heading_level.py`, `src/evaluator_table.py`, `src/evaluator_table_detection.py`, `src/evaluator_triage.py`
- `src/run.py`, `src/pdf_parser.py`, `src/engine_registry.py`, `src/pdf_parser_upstage.py`
- All other `src/pdf_parser_*.py`, `src/generate_*.py`, `src/converter_markdown_table.py`

Roster: `Get-ChildItem -Directory packages/whisker/research/repos/ | Sort-Object Name` (31 directories).

## Roster completeness

| Directory | v2 assignment |
|---|---|
| camelot | sweep 31 |
| docling | individual |
| Dolphin | individual |
| firecrawl | deep A/B |
| grobid | sweep 30 |
| html-to-markdown-go | sweep 33 |
| html-to-markdown-py | sweep 33 |
| html2text | sweep 33 |
| img2table | sweep 32 |
| langextract | individual |
| markdownify | sweep 33 |
| marker | individual |
| markitdown | deep A/B |
| mdream | sweep 32 |
| MinerU | individual |
| node-html-markdown | sweep 32 |
| nougat | individual |
| olmocr | individual |
| opendataloader-bench-tmp | sweep 35 |
| opendataloader-pdf | deep A/B |
| pandoc | sweep 34 |
| PDF-Extract-Kit | sweep 30 |
| pdf-to-markdown | sweep 32 |
| pdfplumber | sweep 31 |
| PyMuPDF | sweep 30 |
| pymupdf4llm | sweep 30 |
| surya | individual |
| tabula-java | sweep 31 |
| tabula-java-tmp | sweep 31 |
| turndown | sweep 34 |
| unstructured | individual |

**Roster complete:** yes (31 directories on disk, 31 v2 assignments, no gaps, no duplicates).

## Eval methodology (opendataloader-bench-tmp)

**Deterministic.** The benchmark scores already-produced markdown predictions against ground-truth markdown using rule/string/tree metrics only:

| Metric | Module | Mechanism | Citations |
|---|---|---|---|
| NID / NID-S (reading order) | `evaluator_reading_order.py` | `rapidfuzz.fuzz.ratio` on normalized/stripped text | `evaluator.py:103`; `evaluator_reading_order.py:37-38` |
| TEDS / TEDS-S (tables) | `evaluator_table.py` | TEDS tree-edit on HTML table structure (PubTabNet-derived) | `evaluator.py:104`; `evaluator_table.py:139,223` |
| MHS / MHS-S (headings) | `evaluator_heading_level.py` | APTED tree edit + Levenshtein on heading trees | `evaluator.py:105`; `evaluator_heading_level.py:20-21,46-50` |
| Table detection P/R/F1 | `evaluator_table_detection.py` | Regex detection of markdown pipe-table separators vs `reference.json` | `run.py:226-236`; `evaluator_table_detection.py:43-50,122-141` |
| Hybrid triage P/R/F1 | `evaluator_triage.py` | Compare `triage.json` page routing vs GT table pages in `reference.json` | `run.py:252-261`; `evaluator_triage.py:97-139,251-284` |
| Regression gate | `run.py` | Threshold compare on aggregated JSON metrics | `run.py:53-117` |

Orchestration: `run.py:206-216` calls `evaluator.run`; no LLM imports or API calls on the eval path.

**Not LLM-as-judge:** No code path sends prediction markdown + source PDF/page to an LLM/VLM for scoring or verification.

## Inventory (search-floor hits, every item)

### Production / executable code (`src/*.py`)

| File:line | Role / triage |
|---|---|
| `src/pdf_parser_upstage.py:9` | `UPSTAGE_API_KEY` env read; **extraction API** (Upstage document-digitization), not eval |
| `src/pdf_parser_upstage.py:11` | Bearer auth header for Upstage API |
| `src/pdf_parser_upstage.py:16` | Request field `"model": "document-parse"` (Upstage hosted model name); **extraction**, not eval |
| `src/pdf_parser_upstage.py:19` | `requests.post` to `https://api.upstage.ai/v1/document-digitization`; **extraction**, not eval |
| `src/engine_registry.py:29` | **False positive:** DATA_ONLY engine version string `"pymupdf4llm"`; not an LLM invocation |
| `src/run.py:181` | **False positive:** function name `run_pipeline` matched `pipeline(` pattern; orchestrates deterministic eval |
| `src/run.py:391` | **False positive:** call to `run_pipeline` |

**Wiring note:** `pdf_parser_upstage.py` is **not** registered in `engine_registry.py:11-58` (`ENGINES`, `_ENGINE_MODULES`); no import/reference elsewhere in repo. Orphan parser module, not on the default bench pipeline path (`pdf_parser.py:62-66` uses `ENGINE_DISPATCH` only).

**Eval modules with zero search-floor hits:** `evaluator.py`, `evaluator_reading_order.py`, `evaluator_heading_level.py`, `evaluator_table.py`, `evaluator_table_detection.py`, `evaluator_triage.py`, all other `pdf_parser_*.py`, `converter_markdown_table.py`, `generate_*.py`.

**Tests:** zero search-floor hits across `tests/*.py` (5 files).

### Scripts

| File:line | Role / triage |
|---|---|
| `scripts/generate-licenses.sh:16` | **Docs:** Hugging Face dataset URL in license table |

### Documentation

| File:line | Role / triage |
|---|---|
| `CLAUDE.md:1` | **Docs:** filename contains "Claude" |
| `CLAUDE.md:3` | **Docs:** Cursor/Claude guidance text |
| `README.md:5` | **Docs:** prose "LLMs can't read PDFs" |
| `README.md:30` | **Docs:** benchmark table row engine name `pymupdf4llm` |
| `README.md:52` | **Docs:** link to prediction evaluation JSON |
| `README.md:229` | **Docs:** bibliography citing LLM prompt paper |
| `README.md:230` | **Docs:** bibliography citing LLM QA paper |
| `README.md:232` | **Docs:** Hugging Face DP-Bench dataset URL |
| `README.md:234` | **Docs:** Hugging Face PubLayNet dataset URL |

### Lockfile / transitive dependencies (not invocation sites)

| File:line | Role / triage |
|---|---|
| `uv.lock` (multiple) | **Deps:** `huggingface-hub`, `transformers` package entries pulled by docling/unstructured stack; no direct import in this repo's eval code |

### Benchmark data artifacts (not code paths)

| Scope | Stats | Role / triage |
|---|---|---|
| `prediction/**` | **1240 matches, 827 lines, 226 files** (rg `--stats`) | **DATA:** converted markdown containing source-paper text about LLMs (e.g. SOLAR paper mentions Llama/GPT); not executable |
| `history/**` | subset of archived `evaluation.json` | **DATA:** stored scores |
| `ground-truth/reference.json` | 49 pattern matches (rg count) | **DATA:** GT layout JSON; text fields from benchmark PDFs |
| `THIRD_PARTY_LICENSES.txt` | many `invoke`, `transformers`, `huggingface`, `Stallman` matches | **LICENSE:** third-party license text; not code |

## Verdict on the claim(s)

**C1 CONFIRMED** for `opendataloader-bench-tmp` at pinned SHA: no production eval-harness path uses an LLM/VLM to judge already-produced conversion output against the source per page/chunk/unit. Evaluation is fully deterministic (`evaluator.py:103-105`, metric modules cited above). The only remote-model call site in repo source is `pdf_parser_upstage.py:8-21` (Upstage extraction API), which produces output rather than scoring it, and is unwired from `engine_registry.py`.

## Coverage gaps

- `prediction/**` markdown: aggregate stats only (1240 matches); line-by-line listing would be paper-text duplication, not code-path evidence. Every executable `.py` under `src/` and `tests/` was pattern-scanned and spot-read.
- `THIRD_PARTY_LICENSES.txt` / full `uv.lock`: pattern hits triaged as license/dependency metadata, not enumerated line-by-line.

## What could still hide a counterexample

- Runtime behavior inside installed third-party packages invoked by parsers (`docling`, `unstructured` hi_res, `edgeparse`, `liteparse`, `markitdown`, `opendataloader_pdf`) is out of this repo's source tree; this sweep covers only `opendataloader-bench-tmp` itself.
- `pdf_parser_upstage.py` could be wired manually outside `engine_registry`; currently no reference found.
