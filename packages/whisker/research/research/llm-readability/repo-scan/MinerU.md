# Repo scan: MinerU

**Does it verify LLM-readability?** **partial**

Scanned: local shallow clone at `packages/whisker/research/repos/MinerU` (read-only, July 2026).

MinerU does **not** test whether an LLM can recover facts from emitted markdown. In-repo QA is a single-PDF deterministic assertion suite on intermediate `content_list.json` (fuzzy text, table substring anchors, equation token presence, modality count). Published quality claims cite **OmniDocBench End-to-End Overall** scores in docs/changelog (`docs/en/quick_start/index.md:99`, `README.md:88-105`), which per `05-web.md` Q3 are **structural-fidelity** metrics (edit distance, TEDS, CDM), not comprehension or downstream QA. No fact corpus, no blind read-back, no LLM-as-judge eval path, no markdown-output comprehension gate in CI.

## Findings

### 1. In-repo gate: typed per-block assertions on `content_list.json`, not markdown

`tests/unittest/test_e2e.py` runs one fixture (`tests/unittest/pdfs/test.pdf`) under `parse_method="txt"` and `"ocr"` (`test_e2e.py:50-71`), writes `.md` but **never asserts on markdown** (`test_e2e.py:119-128` write only; assertions at `:152-220` read JSON).

Per-block checks:

| Modality | Check | Evidence |
|----------|-------|----------|
| image | caption `fuzz.ratio > 90` | `test_e2e.py:161-168` |
| table | caption ratio + `validate_html(table_body)` + substring hit-rate | `test_e2e.py:171-201` |
| equation | token presence (`$$`, `lambda`, `frac`, `bar`) | `test_e2e.py:205-209` |
| text | `fuzz.ratio > 90` vs hardcoded paragraph | `test_e2e.py:211-218` |
| all | `len(type_set) >= 4` modality diversity | `test_e2e.py:157,220` |

Table anchors: 11 literals, pass if `correct_count > 0.9 * len(targets)` for txt/ocr, `> 0.7 *` for vlm (`test_e2e.py:181-201`). This is **localized structural content recovery**, closer to olmOCR presence/table tests than to LLM-readability, but runs on JSON blocks not final markdown and covers **n=1** PDF.

### 2. No committed goldens, no benchmark harness, no eval scripts

- Output written at test time to `tests/unittest/output/` (`test_e2e.py:57-59,125-128`); **no committed expected JSON**; inline hardcoded strings only.
- Repo search: no `eval/`, `benchmark/`, or OmniDocBench scorer code; only `tests/` tree (`tests/unittest/test_e2e.py`, `get_coverage.py`, `clean_coverage.py`).
- `pyproject.toml` pins coverage to that single test file (`pyproject.toml:157`).

### 3. CI gates code coverage, not conversion comprehension

`.github/workflows/cli.yml:31-39`: `coverage run` + `python tests/get_coverage.py`.

`get_coverage.py:20`: asserts HTML coverage report `>= 0.2` (20% line coverage). **Not** a conversion-quality or LLM-readability gate.

Other workflows (`python-package.yml`, `mkdocs.yml`) handle release/install/docs; none run comprehension or OmniDocBench.

### 4. External OmniDocBench: publish-only structural metrics

- Docs footnote: "Accuracy metrics are the End-to-End Evaluation Overall scores from OmniDocBench (v1.6)" (`docs/en/quick_start/index.md:99`).
- Changelog cites OmniDocBench v1.6 deltas for OCR/Hybrid backends (`README.md:88-105`).
- No in-repo script to reproduce those scores; aligns with `05-web.md` Q3: OmniDocBench Overall = structural fidelity, **no comprehension metrics**.

### 5. Product positioning targets LLM/RAG downstream, but does not verify consumability

README tagline: "High-accuracy document parsing engine for LLM · RAG · Agent workflows" (`README.md:49`). Docs: output is "machine-readable formats such as Markdown and JSON for downstream retrieval, extraction, and processing" (`docs/en/index.md:45`). **No** continued-pretraining or field-QA study in repo (contrast olmOCR paper downstream gate in `05-web.md` Q3).

### 6. No LLM-as-judge, no fact JSONL corpus, no provenance gate

Unlike olmOCR-bench (`05-web.md` Q1): no `present`/`absent`/`order`/`math` fact types over a multi-PDF corpus; no `checked: verified` provenance; no review app; no deterministic scorer over markdown output.

---

## Portable to whisker (ranked)

1. **Modality-stratified substring hit-rate with backend-specific operating point** — table anchor list + `correct_count / len(targets) > 0.9` (txt/ocr) vs `> 0.7` (vlm) (`test_e2e.py:181-201`). Map to whisker `facts.json` table substrings + `min_hit_rate` keyed by baseline `backend`; strongest MinerU pattern guard lacks beneath scalar TEDS.

2. **Modality diversity gate** — `len(type_set) >= 4` (`test_e2e.py:220`). Whisker guard should fail when GT-derived modalities (table, math, figure) disappear from candidate markdown even if aggregate metrics hold.

3. **Per-modality typed checks beneath corpus metrics** — image caption fuzz, equation token presence, table HTML well-formedness (`test_e2e.py:161-209`). Extend Lane 3 fact types or guard pre-checks for caption/math/HTML-parse axes tapetum already adjudicates.

4. **Dual-backend threshold stratification** — same fixture, txt and ocr paths with shared asserts (`test_e2e.py:50-71`). Whisker baseline rows should record `parse_method` / engine and apply MinerU-style slack split.

5. **Do not adopt:** n=1 inline hardcoded asserts without committed goldens; 20% code-coverage meta-gate as proxy for QA (`get_coverage.py:20`); reliance on publish-only OmniDocBench numbers without in-repo reproduction.

---

## Cross-check vs redteam report

**File:** `packages/whisker/research/redteam/MinerU.md`

| Redteam claim | Verdict | Evidence |
|---------------|---------|----------|
| One PDF e2e fixture, no committed conversion goldens | **Confirm** | `test_e2e.py:25-33,57-59`; no expected JSON in git |
| Typed per-block assertions on `content_list.json` | **Confirm** | `test_e2e.py:152-220` |
| Parse-method-stratified table thresholds 0.9 vs 0.7 | **Confirm** | `test_e2e.py:198-201` |
| Modality coverage `len(type_set) >= 4` | **Confirm** | `test_e2e.py:220` |
| CI runs txt+ocr in one test, coverage >= 20% | **Confirm** | `test_e2e.py:50-71`; `cli.yml:37-39`; `get_coverage.py:20` |
| OmniDocBench leaderboard in README, not in-repo | **Confirm** | `docs/en/quick_start/index.md:99`; `README.md:88-105`; no eval scripts |
| No ROC calibration | **Confirm** | hand-set `fuzz.ratio > 90`, substring rates inline |
| **Extend (LLM-readability scope):** MinerU has localized deterministic asserts resembling olmOCR **presence/table** tests but on JSON, n=1, no markdown gate, no comprehension corpus | **New** | Assertions never read `.md`; no fact JSONL; OmniDocBench cited is structural per `05-web.md` Q3 |
| Redteam framed vs whisker guard/calibrate | **Scope note** | This scan adds: **partial** for structural localized recovery, **no** for LLM-readability / downstream consumability proof |

**Net:** Redteam regression-gate findings **confirmed**. For #254 LLM-readability: MinerU is **partial at best** (single-fixture JSON asserts); primary quality narrative **delegates to external OmniDocBench structural metrics**, not comprehension.
