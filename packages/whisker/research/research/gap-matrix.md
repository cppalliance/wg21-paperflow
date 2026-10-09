# Whisker Gap Matrix: Practice -> Current Status -> Action

Derived from the 28-repo QA swarm (`cross-repo-qa-research.md`). Ranked by impact
on the goal: **when tomd changes, prove no conversion quality was lost.**

Status legend: ABSENT (not in whisker) / PARTIAL (exists, incomplete) / PRESENT
(solid) / LEADS (whisker ahead of field).

| # | Practice | Field evidence | whisker status | Action | Phase |
|---|----------|----------------|----------------|--------|-------|
| 1 | Per-item metrics-as-snapshots regression gate | unstructured, opendataloader, tabula-java, marker | **ABSENT** (`bench --baseline` only checks corpus-mean `overall`) | Build `whisker guard`: per-paper baseline JSON, fail on any per-paper regression beyond slack | 4a |
| 2 | Per-axis diffing (nid/teds/mhs/unigram separately) | nougat, opendataloader | **ABSENT** (`overall = mean` collapses axes) | Diff every axis independently in the guard; report which axis regressed | 4a |
| 3 | Verdict-transition detection (pass->review->fail) | tabula-java monotonic baselines | **ABSENT** | Guard flags any paper whose verdict degraded vs baseline | 4a |
| 4 | Explicit golden refresh ritual | pandoc `--accept`, go `-update`, py `--bless`, unstructured `OVERWRITE_FIXTURES` | **ABSENT** | `whisker guard --update` rewrites baseline; review diff in PR | 4a |
| 5 | Per-axis absolute floors (CI backstop) | marker, opendataloader `thresholds.json`, MinerU | **PARTIAL** (`constants.py` floors used in verdict, not as a corpus CI backstop) | Guard enforces per-axis floors even with no/stale baseline | 4a |
| 6 | Threshold calibration on labeled data (TPR/FPR) | almost nobody (field blind spot) | **ABSENT** (documented, never implemented) | Implement `whisker calibrate`: fit edges, emit TPR/FPR/precision, write thresholds | 4b |
| 7 | Metric invariant tests (identity/symmetry/bounds/monotonic) | pandoc QuickCheck, pdfplumber | **PARTIAL** (functional tests, no invariants) | Add invariant + property/fuzz tests for nid/teds/mhs/coverage | 4c |
| 8 | Gate + decision meta-tests | olmocr (148 engine tests) | **PARTIAL** (`test_score`, `test_bench` exist) | Add guard-logic + gate-fixture meta-tests | 4c |
| 9 | Required/forbidden substring anchors | markitdown, firecrawl, olmocr | **ABSENT** | Recommended follow-on: per-paper `facts` file (anchors) | later |
| 10 | Reading-order / section-order assertion | markitdown ordered `find()`, olmocr `order` | **PARTIAL** (bench tracks reading_order metric; no per-paper assert) | Follow-on: section-order facts | later |
| 11 | Intrinsic reference-free confidence | camelot geometry formula | **PARTIAL** (gates + unigram coverage) | Follow-on: table-raggedness intrinsic score | later |
| 12 | Pre-score normalization | Dolphin LaTeX canon | **PRESENT** (`normalized_text`, OmniDocBench clean_string) | Confirmed sound; harden if drift appears | n/a |
| 13 | Per-stage intermediate goldens | pdf-to-markdown, img2table, MinerU | **ABSENT** (tomd-side concern) | Out of scope for whisker; note for tomd | n/a |
| 14 | Multi-tier field matching | grobid (4 tiers) | **PARTIAL** (NID is one tier) | Low priority; NID + TEDS already cover the need | n/a |
| 15 | Order-invariant content floor | nougat, docling separate order from content | **LEADS** (unigram coverage is exactly this) | Keep | n/a |
| 16 | Real metric math in-repo | most repos cite external benchmarks only | **LEADS** (verbatim TEDS/MHS/NID) | Keep; guard invariant-tests protect it | 4c |
| 17 | Advisory cross-converter oracle | node-html-markdown (harness only) | **LEADS** (markitdown agreement, never hard-fail) | Keep | n/a |
| 18 | CI exit-code contract + no-LLM determinism | surya tiered CI | **LEADS** (0/1/3/5 codes) | Extend codes to the guard | 4a |

## Build order (consensus-weighted)

1. **4a regression guard** addresses gaps #1-#5 and #18 in one component. This is
   the single highest-leverage change and the direct answer to the user's ask.
2. **4c tests** (#7, #8) protect the metric engine the guard depends on.
3. **4b calibrate** (#6) turns the field's blind spot into whisker's differentiator.
4. **Follow-on** (#9-#11): per-paper anchor/order facts + intrinsic table
   confidence. Documented here, not built this pass (scope discipline).
