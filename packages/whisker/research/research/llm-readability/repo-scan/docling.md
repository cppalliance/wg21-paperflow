# Repo scan: docling

**Does it verify LLM-readability?** **no** (partial: structural golden replay + pipeline self-confidence grades proxy conversion quality; no fact assertions, QA benchmarks, LLM read-back, or downstream consumability gates in CI)

Scanned: local shallow clone at `packages/whisker/research/repos/docling` (read-only, depth 1, July 2026).

## Findings

### CI gate = multi-artifact golden replay (structural fidelity)

Primary e2e test walks every PDF under `tests/data/pdf/sources/` and calls `verify_conversion_result_v2` (`tests/test_e2e_conversion.py:23-72`). Before any diff, conversion must succeed (`tests/verify_utils.py:366-368`).

Per source file, four committed ground-truth artifacts are compared (`tests/verify_utils.py:382-438`):

| Artifact | Check |
|----------|-------|
| `.pages.meta.json` | Page cell counts (`verify_cells`, `verify_utils.py:116-131`) |
| `.json` | Full `DoclingDocument`: labels, provenance, bbox, item counts, per-cell table text + header flags (`verify_docitems`, `verify_table_v2`, `verify_utils.py:219-344,134-172`) |
| `.md` | Exported markdown string equality or fuzzy NED (`verify_md` → `verify_text`, `verify_utils.py:347-348,99-112`) |
| `.doctags.txt` | Doctags export equality (skippable per file via `SKIP_DOCTAGS_COMPARISON`, `test_e2e_conversion.py:17,65-71`) |

Tolerance model (`tests/verify_utils.py:23-31,64-72,99-112`):

- Coordinates rounded to `COORD_PREC=2`, confidences to `CONFID_PREC=3`.
- Strict bbox tolerance `max(10^-2, page_extent × 0.0025)`; fuzzy OCR path uses `0.006`.
- Text: line-level strict equality, or fuzzy Levenshtein `dist/len(gt) < 0.4`.

**814** files under `tests/data/` at scan time (redteam cited ~801 multi-artifact items; counts align). Golden refresh requires `DOCLING_GEN_TEST_DATA=1 uv run pytest` (`CONTRIBUTING.md:76-80`); CI asserts flag is off (`tests/test_data_gen_flag.py:5-9`). Golden PRs to `tests/data/**` require **two reviewers** (`.github/mergify.yml:16-24`).

This is **resemblance to committed structural gold**, not "can an LLM recover facts from exported markdown."

### No comprehension / fact-assertion / LLM-eval benchmark in repo

Repo-wide search for `comprehension`, `fact assert`, `QA`, `LLM-as-judge`, `OmniDocBench`, `docling-eval`, `downstream consumability` in `*.py` / `docs/*.md`: **no CI benchmark** matching olmOCR-style fact JSONL, ParseBench rules, or RealDocBench field QA.

External `docling-eval` is **not referenced** in this clone (no submodule, no CI job, no import).

Agent skill docs reference `scripts/docling-evaluate.py` for iterative quality evaluation (`docs/examples/agent_skill/docling-document-intelligence/SKILL.md:286-318`), but **`scripts/` contains only** `check_max_lines.py`, `check_tach_module_coverage.py`, `render_cli_reference.py`, `render_notebooks.py` — **the evaluator script is absent** (documentation drift).

### Pipeline confidence grades (self-assessment, not LLM consumability)

Since v2.34.0, `ConversionResult.confidence` exposes layout/ocr/parse/table scores and grades (`docs/concepts/confidence_scores.md:7-49`). Grades use fixed bands (`docling/datamodel/base_models.py:557-565`): `<0.5 POOR`, `<0.8 FAIR`, `<0.9 GOOD`, `≥0.9 EXCELLENT`. Document rollup uses `mean_grade` and **`low_grade` from 5th percentile** of component scores (`base_models.py:574-598`; docs `confidence_scores.md:48-49`).

Tested in CI (`tests/test_options.py:544-549`) on a fixture PDF — asserts grades land in expected band, not that an LLM can read output.

`table_score` component is documented as **not yet implemented** (`confidence_scores.md:42`). These scores measure **internal model/layout confidence**, not downstream LLM fact recovery (contrast olmOCR paper continued-pretraining consumability study cited in `05-web.md` Q3).

### Chunking for RAG (readability-relevant design, not gated in CI)

Chunkers live in `docling-core` (dependency); docling documents and integrates them:

| Chunker | Boundary behavior | Evidence |
|---------|-------------------|----------|
| `HierarchicalChunker` | One chunk per detected document element; optional list-item merge | `docs/concepts/chunking.md:107-113` |
| `HybridChunker` | Hierarchical first, then token-aware split/merge; **`repeat_table_header=True`** repeats headers when tables span chunks; `omit_header_on_overflow` for wide rows | `docs/concepts/chunking.md:61-83` |
| `LineBasedTokenChunker` | **Preserves line boundaries**; splits a line only if it alone exceeds token limit; suited to tables/code/logs | `docs/concepts/chunking.md:99-105`, `docs/examples/line_based_chunking.ipynb` |

RAG example notebooks (`docs/examples/rag_*.ipynb`, `retrieval_qdrant.ipynb`) use chunkers + external vector DB + **LLM Q&A for demos**, not as conversion QA gates.

**No chunker unit tests** in docling `tests/` (only service-client chunk API mocks, `tests/test_service_client_sdk_unit.py:1675-1697`). Table/code boundary respect is **documented**, not CI-proven in this repo.

### Table verification vs olmOCR-style comprehension

Docling golden `verify_table_v2` checks row/col counts, per-cell text (strict or fuzzy NED), and header-bit flags (`verify_utils.py:134-170`). It does **not** assert spatial neighbor relations (above/below/left/right) between cells the way olmOCR `TableTest` does. Closer to structural grid fidelity than LLM table-QA.

### What docling does NOT do (vs Lane 3 / #254 goal)

- No human-verified fact JSONL corpus gating markdown export.
- No blind LLM read-back in CI.
- No LLM-as-judge eval loop.
- No downstream task benchmark (MMLU-style consumability) in repo code.

## Portable to whisker (ranked)

1. **Fuzzy NED text gate** `dist/len(gt) < threshold` as secondary tolerance on text-like axes (`verify_utils.py:110-112`) — redteam already flags; adopt for `nid`/presence-like checks distinct from absolute metric slack.
2. **Serialize-then-compare** at fixed decimal precision before numeric tolerance (`verify_utils.py:64-72`) — round baseline and current bench floats on same grid before diff.
3. **`low_grade` / 5th-percentile worst-area rollup** alongside per-axis guard (`base_models.py:593-598`) — catches single bad table/page Docling-style.
4. **Per-item axis skip lists** (`SKIP_DOCTAGS_COMPARISON`, `SKIP_E2E_TEST`, per-backend filters) — baseline `"skip_axes"` for known-noisy WG21 papers.
5. **HybridChunker table-header repeat + LineBasedTokenChunker line atomicity** — document as whisker chunking guidance (H2 + atomic pipe-table/code fences); optional chunk-boundary canaries in comprehension corpus, not copied from Docling code.
6. **Golden refresh CI lockout + 2-reviewer governance** on committed expected artifacts (`test_data_gen_flag.py:5-9`, `mergify.yml:16-24`, `CONTRIBUTING.md:76-82`).
7. **Confidence grades as advisory triage** (like tapetum_llm): surface `mean_grade`/`low_grade` on conversion, never gate Lane 3 — Docling explicitly warns scores are internal (`confidence_scores.md:11-13`).
8. **Per-cell table grid checks with header flags** — extend whisker `table` facts or Lane 2 sidecar when GT has structured table JSON; Docling's neighbor-free grid is weaker than olmOCR but stronger than scalar TEDS alone.

## Cross-check vs redteam report

Reference: `packages/whisker/research/redteam/docling.md` (guard/calibrate vs Docling **regression** gates — different axis from LLM-readability, but structural claims overlap).

| Redteam claim | Scan verdict |
|---------------|--------------|
| Gates on ~801 committed multi-artifact goldens (JSON + MD + doctags + page meta) | **Confirms** (`verify_conversion_result_v2`, `tests/data/` ≈814 files; 28 PDF stems with `.json` groundtruth at scan). |
| CI-safe refresh `DOCLING_GEN_TEST_DATA=0` | **Confirms** (`test_data_gen_flag.py:5-9`, `CONTRIBUTING.md:78-80`). |
| 2-reviewer Mergify on `tests/data/**` | **Confirms** (`.github/mergify.yml:16-24`). |
| Tiered tolerances: strict bbox `0.0025`, fuzzy `0.005`, OCR text NED `<0.4`, serialize-then-compare | **Confirms** (`verify_utils.py:25-27,64-72,110-112`). |
| Per-item axis skips / xfail flaky items | **Confirms** (`test_e2e_conversion.py:17-20,65-71`; `test_backend_msword.py:129-132` cited in redteam). |
| Docling uses hand-set grade bands, not ROC | **Confirms** (`base_models.py:557-565`; `confidence_scores.md:11-13`). |
| Docling verifies LLM-readability / comprehension | **Not claimed in redteam** — scan adds: **no**; redteam scope was scalar guard gaps, not Lane 3. |
| `docling-eval` benchmark in repo | **Not in redteam** — scan: **absent** from clone; no CI hook. |
| Agent skill `docling-evaluate.py` | **Not in redteam** — scan: **contradicts skill doc** (script missing from `scripts/`). |

No material contradictions on regression-gate claims. Scan adds explicit **no comprehension** verdict, chunking-as-docs-only, missing evaluator script, and confidence-as-self-assessment not LLM consumability.
