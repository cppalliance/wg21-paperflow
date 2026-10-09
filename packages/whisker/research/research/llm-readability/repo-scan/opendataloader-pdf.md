# Repo scan: opendataloader-pdf

**Does it verify LLM-readability?** **no** (structural smoke assertions + external opendataloader-bench NID/TEDS/MHS means; no fact assertions, QA, LLM read-back, or comprehension gates in this repo)

Scanned: local shallow clone at `packages/whisker/research/repos/opendataloader-pdf` (read-only, depth 1, July 2026). Structural bench logic cross-read from companion clone `packages/whisker/research/repos/opendataloader-bench-tmp` (invoked by `scripts/bench.sh`).

## Findings

### Converter repo does not ship a comprehension benchmark

README and FAQ market Markdown output **for LLM/RAG** (`README.md:290,486-553`: "Clean text for LLM context", "feed directly into LLM context windows"). That is product positioning, not verified LLM comprehension.

Repo-wide search for `comprehension`, `fact assert`, `QA benchmark`, `LLM-as-judge`, `read-back` in `*.py`, `verification/`, `docs/`: **zero CI comprehension tests**.

### CI verification = three-level structural contract (`verification/ci-verify.py`)

Docstring defines levels (`ci-verify.py:3-4`):

| Level | Mechanism | LLM-readability? |
|-------|-----------|------------------|
| **1 Smoke** | CLI exit 0 + output file exists (`ci-verify.py:141-156`) | No |
| **2 Content assertion** | Substring `must_contain` / `must_not_contain` on output text (`ci-verify.py:163-200`) | No — feature smoke only (e.g. `must_contain=["\|"]` for `--table-method cluster`, `ci-verify.py:1209`; `must_contain=["~~"]` for strikethrough, `ci-verify.py:1143-1144`) |
| **3 Comparison** | Byte-identical or must-differ between CLI variants (`ci-verify.py:273-319`) | No — option wiring regression |

When no needles supplied, Level 2 falls back to non-empty file check (`ci-verify.py:191-196`) — vacuous-pass guard, not semantic QA.

**Known-issue skip pattern:** `STRIKETHROUGH_KNOWN_ISSUE = True` skips strikethrough content check without failing CI (`ci-verify.py:46,1128-1129`) — redteam cited; **confirms**.

Stack-trace leak forbidden strings enforced (`ci-verify.py:63-67,493-510`). Option coverage fail-closed against `options.json` (`ci-verify.py:326-354`).

Runs on every PR touching Java/Python/verification (`.github/workflows/test-benchmark.yml:60-63`).

### External structural bench (not in-repo)

Benchmark code lives in **opendataloader-bench**, cloned at CI time (`scripts/bench.sh:57-64`, default `/tmp/opendataloader-bench`).

`bench.sh` runs `uv run python src/run.py --engine opendataloader` with optional `--check-regression` (`.github/workflows/test-benchmark.yml:114-115`).

`check_regression()` gates **corpus means** only (`opendataloader-bench-tmp/src/run.py:53-117`):

- `nid_mean`, `teds_mean`, `mhs_mean` ≥ `threshold - regression_tolerance` (`run.py:73-86`; `thresholds.json:1-9`, `regression_tolerance: 0.02`)
- Plus `table_detection_f1`, `elapsed_per_doc` upper bound, `triage_recall`, `triage_fn_max`

Metrics are **rapidfuzz / APTED / TEDS** structural similarity (`evaluator_reading_order.py`, `evaluator_table.py`, `evaluator_heading_level.py` — see `repo-scan/opendataloader-bench-tmp.md`). No QA, fact recovery, or LLM judge.

Per-document scores written to `evaluation.json` but **`check_regression` ignores the documents array** (`run.py:66-86`; redteam `evaluator.py:252` citation directionally correct).

Null-axis handling: returns `(None, None)` when GT lacks tables/headings; excluded from means (`evaluator_table.py:234-235` at scan) — redteam **confirms** vs whisker's `teds=1.0` placeholder.

### Tests/ directory

This repo has **no top-level `tests/`** for conversion QA. Java unit tests under `java/**/src/test/java/` cover processors, CLI options, hybrid mocks — not markdown comprehension. Python hybrid server tests are integration-scoped.

### Docs / experiments

`docs/hybrid/experiments/` tracks triage accuracy and speed thresholds — structural/triage metrics, not LLM comprehension. `scripts/experiments/docling_fastapi_bench.py` measures **latency** (<0.8s/doc), not readability.

## Portable to whisker (ranked)

1. **Corpus-mean `threshold - regression_tolerance` backstop** on NID/TEDS/MHS (`run.py:69-86`, `thresholds.json`) — redteam top portable; complements per-paper guard.
2. **Null-axis eligibility** (`None` when GT lacks modality; exclude from mean/diff) — adopt in whisker bench/guard (`evaluator_table.py:234-235` pattern).
3. **Three-level verification taxonomy** (smoke / targeted content needles / option comparison) — organize whisker CLI smoke layer; map `must_contain` to minimal feature assertions (table pipe char, page separator token) without claiming comprehension.
4. **Unified `thresholds.json` artifact** with shared `regression_tolerance` — extend whisker calibrate output shape (redteam §2.1).
5. **`expected_failure` / known-issue skip with audit trail** (`STRIKETHROUGH_KNOWN_ISSUE`, `ci-verify.py:46,1128-1129`) — explicit baseline flag vs silent xfail.
6. **Structure-only companion axes** `nid_s` / `teds_s` / `mhs_s` — optional guard axes when formatting churn hides content regressions (redteam §1.4).
7. **Pre-score normalization contract** before metric diff (HTML-table wrapper, whitespace collapse in bench) — align guard diff with normalized scores (redteam §1.5).
8. **Do not adopt** Level-2 `must_contain` as Lane 3 substitute — needles prove CLI flags fired (`"|"`, `"<table"`), not that an LLM recovers paper facts.

## Cross-check vs redteam report

Reference: `packages/whisker/research/redteam/opendataloader-pdf.md` (guard/calibrate vs opendataloader regression — structural focus).

| Redteam claim | Scan verdict |
|---------------|--------------|
| CI gates corpus means via `thresholds.json` + `regression_tolerance: 0.02` | **Confirms** (`run.py:69-86`; CI `test-benchmark.yml:114-115,148-162`). |
| Bench invoked via `scripts/bench.sh` cloning opendataloader-bench | **Confirms** (`bench.sh:57-85`). |
| No ROC; hand-set floors | **Confirms** (`thresholds.json`; no calibrate code in either repo). |
| Null TEDS/MHS when GT lacks modality | **Confirms** (`evaluator_table.py:234-235`; heading path per redteam). |
| `must_contain` / `must_not_contain` in `ci-verify.py` | **Confirms** (`ci-verify.py:166-200,695+,849+`). |
| Level 3 byte-identical option compare | **Confirms** (`ci-verify.py:273-319`). |
| Known-issue skip (strikethrough) | **Confirms** (`ci-verify.py:46,1128-1129`). |
| Per-paper scores in `evaluation.json` not gated by `check_regression` | **Confirms** (`run.py:66-86`). |
| opendataloader verifies LLM-readability | **Not claimed in redteam** — scan adds explicit **no**; README LLM claims are marketing only. |
| Converter ships comprehension QA separate from bench | **Clarifies redteam** — converter has **only** ci-verify structural checks + external structural bench; **no** comprehension layer anywhere in the stack. |

No material contradictions. Scan aligns with `05-web.md` Q3 card: opendataloader-bench is the counter-example where structural gating has **not** moved to comprehension.
