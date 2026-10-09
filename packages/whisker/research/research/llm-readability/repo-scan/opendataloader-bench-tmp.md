# Repo scan: opendataloader-bench

**Does it verify LLM-readability?** **no** (structural fidelity only: reading-order similarity, table tree edit distance, heading hierarchy; no fact assertions, QA, or downstream LLM consumability tests)

Scanned: local shallow clone at `packages/whisker/research/repos/opendataloader-bench-tmp` (read-only). **No redteam report exists** for this repo (`packages/whisker/research/redteam/` has `olmocr.md` only); cross-check uses `research/llm-readability/05-web.md` Q3 and `00-baseline.md` survey claims instead.

## Findings

### Stated scope (README)

Project measures three structural axes only (`README.md:11-13`):

- **Reading Order** — text sequence correctness
- **Table Fidelity** — table reconstruction
- **Heading Hierarchy** — document structure

No mention of comprehension, QA, fact recovery, or LLM-based evaluation anywhere in README sections 1–6.

### Evaluation pipeline (`src/evaluator.py`)

End-to-end evaluator imports three modules and nothing else (`evaluator.py:25-27`):

```python
from evaluator_heading_level import evaluate_heading_level
from evaluator_reading_order import evaluate_reading_order
from evaluator_table import evaluate_table
```

Per document (`evaluator.py:94-125`):

- `evaluate_reading_order` → `nid`, `nid_s`
- `evaluate_table` → `teds`, `teds_s`
- `evaluate_heading_level` → `mhs`, `mhs_s`
- `overall` = mean of available `{nid, teds, mhs}` (`evaluator.py:107-113`)

Aggregate report emits scalar means only (`evaluator.py:128-157`). Output shape documented in README `evaluation.json` section: `overall_mean`, `nid_mean`, `teds_mean`, `mhs_mean` (`README.md:141-147`).

### Metric implementations (all reference-vs-prediction edit distance)

| Metric | File | Mechanism | Evidence |
|--------|------|-----------|----------|
| NID / NID-S | `src/evaluator_reading_order.py` | `rapidfuzz.fuzz.ratio` on normalized full text; NID-S strips HTML tables first | `evaluator_reading_order.py:22-40` |
| TEDS / TEDS-S | `src/evaluator_table.py` | PubTabNet APTED tree edit on HTML table DOM (structure ± cell text) | `evaluator_table.py:1-6,22-50` |
| MHS / MHS-S | `src/evaluator_heading_level.py` | APTED on flat heading/content tree from `#` headings | `evaluator_heading_level.py:1-12,46-50` |

All require hand-labeled `ground-truth/markdown/` vs engine `prediction/<engine>/markdown/` (`evaluator.py:30-31`; README project structure).

### Tests (`tests/`)

Four test modules, all metric plumbing:

- `tests/test_evaluator_table.py`
- `tests/test_evaluator_reading_order.py`
- `tests/test_evaluator_heading_level.py`
- `tests/test_converter_markdown_table.py`

Repo-wide search for `QA`, `comprehension`, `fact`, `question`, `assert` in `src/` and `*.md`: **zero matches**.

### Downstream / LLM consumability

- No fixed extraction LLM pass (contrast RealDocBench in `05-web.md`).
- No unit-test fact JSONL (contrast olmOCR).
- No continued-pretraining consumability probe in this repo.
- References cite MDEval and table-to-text augmentation papers (`README.md:159-164`) as **related work**, not implemented metrics.

### Regression mode

`--check-regression` in CI compares scalar `evaluation.json` snapshots (`CLAUDE.md:19-22`) — same structural contract as whisker Lane 2, not comprehension.

## Portable to whisker (ranked)

Limited portability for Lane 3; mostly confirms whisker Lane 2 choices:

1. **Null-eligibility per axis** when GT lacks modality — already mirrored in whisker `bench.py` (`evaluator.py:107-113`; whisker `CLAUDE.md` bench section).
2. **Separate advisory axes** (NID-S, TEDS-S, MHS-S) — whisker already reports `reading_order`, `grits_con` advisory-only; opendataloader validates not folding everything into one gate.
3. **NID/TEDS/MHS implementation references** — whisker already ports PubTabNet TEDS and block NID from same lineage; low incremental value for comprehension.
4. **NOT portable for #254 goal**: no fact schema, no human-verified assertions, no LLM-readability proxy — confirms opendataloader-bench is a **counter-example** for comprehension gating (`05-web.md:94-97`).

## Cross-check vs survey claims

| Source claim | Scan verdict |
|--------------|--------------|
| `05-web.md` Q3: "purely structural (NID reading order, TEDS/TEDS-S, Markdown Heading Similarity) over 200 PDFs … No QA or fact recovery" | **Confirms** (`README.md:11-13`; `evaluator.py:25-27,103-105`; `CLAUDE.md:7-8`). |
| `00-baseline.md` / POC: comprehension testing exists only in olmOCR among surveyed converters | **Confirms for this repo** — no comprehension path found. |
| whisker Lane 2 already adopts NID/TEDS/MHS from this lineage | **Confirms** — opendataloader-bench is structural sibling, not Lane 3 source. |

**Redteam:** no `packages/whisker/research/redteam/opendataloader-bench-tmp.md` — nothing to confirm/contradict at redteam granularity; survey card stands verified.
