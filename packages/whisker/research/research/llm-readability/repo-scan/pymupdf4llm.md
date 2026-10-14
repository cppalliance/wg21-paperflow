# Repo scan: pymupdf4llm

**Does it verify LLM-readability?** **no** (markets "LLM-ready" markdown and ships RAG integration examples, but CI/regression verifies **byte-exact committed markdown goldens** and a handful of OCR/layout invariants only; no fact assertions, no LLM-as-judge, no downstream consumability benchmark)

Scanned: local shallow clone at `packages/whisker/research/repos/pymupdf4llm` (read-only).

## Findings

### Marketing vs verification gap

README positions output for "RAG pipelines, vector embeddings, and LLM ingestion" (`README.md:26-28,122-125`) and documents page-chunk metadata for vector stores (`README.md:228-240`). None of this is scored by automated comprehension or retrieval tests in-repo.

### Primary QA: exact full-string golden compare

Every regression fixture pairs PDF + committed `*.expected.md`; tests assert `md == expected` with zero slack:

| Test | Evidence |
|------|----------|
| General regression | `tests/test_370.py:45` `assert actual == expected` |
| SCE-150 styling/tables/OCR | `tests/test_sce-150.py:21,40,59` |
| Malicious link (nolayout) | `tests/test_137.py:58` |
| pdf4llm entry-point parity | `pdf4llm/tests/test_general.py:48` |

Failures print `difflib.unified_diff` (`tests/test_370.py:35-42`). This is **structural snapshot fidelity**, the same class as opendataloader-bench (Q3 baseline), not olmOCR-style fact recovery.

### Normalization and kwargs contract

- CRLF stripped before compare on Windows CI: `expected.replace('\r', '')` (`tests/test_sce-150.py:13,32,51`).
- Each golden pins a fixed `to_markdown()` kwargs bundle (`tests/test_sce-150.py:14-19`; `tests/test_370.py:21-31`: `write_images=False`, `header=False`, `footer=False`, etc.).
- Dependency version enforced at import: `src/__init__.py:12-15`; pins in `setup.py:26-28`.

### OCR / replacement-char invariants (weak LLM-proxy only)

- `U+FFFD` must be absent when Tesseract or RapidOCR available, must remain when not (`tests/test_ocr.py:35-38`).
- `use_ocr=False` preserves bad layer (`tests/test_ocr.py:43-46`).
- When OCR runs, output longer than no-OCR path (`tests/test_ocr.py:60-61`).
- Version-gated skip when `mupdf_version_tuple < (1, 28)` (`tests/test_ocr.py:27-28,49-50`).

OCR decision uses hand-set cascade thresholds, not fitted QA: `BAD_CHAR_THRESHOLD = 0.05`, `OCR_MODEL_THRESHOLD = 0.93` (`src/ocr/analyze_page.py:26-29,318-344`).

### Layout dual-path and security golden

- `use_layout(True/False)` toggles extractors (`src/__init__.py:22-47`; tested `tests/pymupdf4llm/llama_index/test_layout.py:8-28`).
- Malicious PDF link suppression golden under nolayout (`tests/test_137.py:39-58`).

### RAG / framework examples without assertions

- `examples/country-capitals/country-capitals.py`: OpenAI RAG demo loop; **no automated pass/fail** on answer correctness (lines 94-120).
- LlamaIndex reader tests early-return when fixture PDF missing (`tests/pymupdf4llm/llama_index/_test_pdf_markdown_reader.py:28-30,62-63`).
- `test_376.py`: subprocess smoke that reader loads empty PDF; no content assertions (`tests/test_376.py:9-33`).
- README LangChain chunking example is documentation only (`README.md:257-271`).

### CI scope

Multi-OS matrix ubuntu/windows/macos (`.github/workflows/test_push.yml:20-24`) runs Aptest harness (`test_push.yml:59`), not comprehension eval.

### Absent (confirmed by scan)

- No JSONL fact corpus, no present/absent/order/table/math assertion engine.
- No LLM-as-judge or blind read-back in CI.
- No downstream MMLU/RAG accuracy benchmark (contrast olmOCR paper Q3 card).
- `tests/test_tablulate.py`: crash-only smoke, no assert on output (`tests/test_tablulate.py:6-23`).

## Portable to whisker (ranked)

1. **CRLF-normalize before golden/metric compare** — `expected.replace('\r', '')` pattern (`tests/test_sce-150.py:13`) for Windows CI parity with whisker `.gt.md` loading.
2. **Embed conversion kwargs + schema_version in baseline metadata** — pymupdf4llm bakes kwargs into each test; whisker guard should record tomd/whisker version and converter flags (redteam 1.3/1.4).
3. **`U+FFFD` / replacement-char gate** on candidate markdown when OCR path expected (`tests/test_ocr.py:36`) — cheap structural proxy whisker lacks today.
4. **Env-conditional expected outcomes** (OCR backend present vs absent) for CI tiers (`tests/test_ocr.py:35-38`).
5. **Output-length delta oracle** when enrichment expected (`tests/test_ocr.py:61`) as optional sidecar field in guard baseline.
6. **Cross-entry-point determinism check** — same golden, two APIs must match (`pdf4llm/tests/test_general.py:9-48`); whisker meta-test: re-score same PID twice.
7. **Multi-threshold OCR cascade as calibration template** — hand-set OR cascade (`analyze_page.py:318-344`), not literal values; whisker already ahead with ROC on coverage.
8. **Do not adopt byte-exact full-md goldens as primary gate** — whisker fuzzy bench + Lane 3 facts is the correct comprehension direction; pymupdf4llm proves the field stops at snapshot regression.

## Cross-check vs redteam report

Reference: `packages/whisker/research/redteam/pymupdf4llm.md`.

| Redteam claim | Scan verdict |
|---------------|--------------|
| Byte-exact committed `.expected.md` goldens, zero slack | **Confirms** (`tests/test_370.py:45`, `tests/test_sce-150.py:21`). |
| CRLF normalization before compare | **Confirms** (`tests/test_sce-150.py:13,32,51`). |
| Pinned `to_markdown()` kwargs per fixture | **Confirms** (`tests/test_sce-150.py:14-19`, `tests/test_370.py:21-31`). |
| Version skip at MuPDF < 1.28 | **Confirms** (`tests/test_137.py:13-15`, `tests/test_ocr.py:27-28`). |
| Env-conditional OCR / U+FFFD assertions | **Confirms** (`tests/test_ocr.py:35-38,43-46`). |
| Layout on/off dual paths tested | **Confirms** (`test_layout.py:8-28`, `tests/test_137.py:19-61`). |
| pdf4llm vs pymupdf4llm same golden | **Confirms** (`pdf4llm/tests/test_general.py:9-48`). |
| Multi-OS CI matrix | **Confirms** (`.github/workflows/test_push.yml:20-24`). |
| OCR cascade constants 0.05 / 0.93 | **Confirms** (`src/ocr/analyze_page.py:26-29,344`). |
| tabulate test crash-only, no assert | **Confirms** (`tests/test_tablulate.py:6-23`). |
| No comprehension / fact-assertion benchmark | **Confirms** — scan adds: RAG demo and LlamaIndex tests are smoke/docs only, no scored LLM recovery. |

No material contradictions. Scan adds explicit **no LLM-readability verification** conclusion despite LLM marketing, and documents the RAG-example gap.
