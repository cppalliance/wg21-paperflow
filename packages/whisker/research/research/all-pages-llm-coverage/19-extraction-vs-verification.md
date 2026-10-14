# 19 - extraction-vs-verification-framing

**Verdict:** usable-with-conditions — The operator's docling/langextract comparison is a category error (extraction coverage ≠ verification coverage), but `--all-pages` review mode is still justified on golden-PR terms if it ships fail-closed page accounting and inherits the full conversion contract, borrowing orchestration from olmocr not semantics from extraction pipelines.
**Confidence:** high

## Findings

- [CRITICAL] **The operator complaint compares extraction to verification; that comparison does not hold.** Docling's VLM lane iterates every page to *produce* structure (`vlm_pipeline.py:245-257` checks each `page.predictions.vlm_response`; `368-388` assembles all page outputs). Langextract runs the model over every chunk to *extract* entities (`annotation.py:396-408`). Tapetum's unit lane injects SOURCE TEXT and CANDIDATE MARKDOWN and asks the model to judge fidelity (`unit_judge.py:673-680`; monolith at `pdf_judge.py:579-580`). Impact: "docling/langextract LLM every page" proves **(a) per-page extraction**, not **(c) per-page verification**; our gap is real but the cited prior art is the wrong class.

- [CRITICAL] **Clone-corpus classification (LLM/VLM role by repo).** Spot-checked in code unless noted.

  | Repo | Primary LLM/VLM role | Category | Evidence |
  |---|---|---|---|
  | olmocr | VLM transcribes every page; bench scores output deterministically | **(a)** pipeline; bench is deterministic **(c)-analogue, no LLM** | `pipeline.py:548-551`; `tests.py:168-173`; `benchmark.py:94-116` |
  | docling | Default: deterministic parse/OCR/layout. Optional VLM: one inference per page to convert. Confidence scores: deterministic post-hoc advisory | **(a)** on VLM path; standard path has no LLM; scores are not LLM verification | `vlm_pipeline.py:245-257`; `standard_pdf_pipeline.py:1073-1077`; 05-web Q1 |
  | langextract | Chunk-scoped entity extraction with grounding | **(a)** per-chunk extraction (not page, not verification) | `annotation.py:396-408`; 05-web Q2 |
  | marker | Block-selective LLM rewrite/correction on qualifying layout blocks | **(b)** per-unit refinement | `marker/processors/llm/__init__.py:163-168`; 05-web Q5 |
  | MinerU | VLM `batch_two_step_extract` over page windows | **(a)** per-page extraction | `vlm_analyze.py:462-482` |
  | Dolphin | Page image → layout VLM → cropped region VLM transcribe | **(a)** per-page extraction | `demo_page.py:186-190` |
  | nougat | One autoregressive decode per page raster | **(a)** per-page extraction | `predict.py:166-169` |
  | surya | One OCR/VLM request per page (block mode on fallback) | **(a)** per-page extraction | `recognition/__init__.py:265-272` |
  | grobid | No LLM; CRF/DL labels + deterministic per-element sanity checks | **none** (deterministic post-rules only) | `FullTextParser.java:318-319` |
  | unstructured | Layout model assigns element types; no second-pass fidelity judge | **(a)** if hi_res layout model counts; no verification lane | `common.py:58-68`; 05-web N/A |

  Impact: **zero** surveyed repos run **(c) LLM per-page verification** ("does this markdown preserve this page's source?"). Extraction repos guarantee every page was *processed*; they never compare output to an independent reference at page scope with an LLM.

- [CRITICAL] **Honest prior-art set for tapetum's category (c) is eval harnesses and scoped judges, not conversion pipelines.** Strongest page-scoped verification without LLM: olmocr-bench fuzzy fact tests bound to `(pdf, page, id)` (`tests.py:83-94`, `benchmark.py:94-116`; SYNTHESIS finding 2). Closest LLM-as-judge exhaustive precedent: pdf-parse-bench applies an LLM judge to every matched **table pair**, not every page (05-web Q4, arXiv 2603.18652). ParseBench and olmocr paper explicitly **reject** LLM-as-judge for primary scoring (05-web Q3-Q4). Routed deep-validation at scale (clinical arXiv 2604.06028) is the practical alternative to exhaustive judging (05-web Q4). Impact: `--all-pages` would be **novel in OSS** at full-page LLM verification scope; portable pieces are page enumeration (olmocr), deterministic fact engine (olmocr-bench), scoped table judging (pdf-parse-bench), and reject-and-keep gates (marker), not docling/langextract coverage guarantees.

- [HIGH] **The operator expectation (every page LLM-checked in review mode) is legitimate on its own terms, not because docling/langextract do it.** Review-mode assumptions from `00-baseline.md:36-37` re-weigh fleet objections: n≈10-40 pages, hourly pod billing, human triage of flags, and a missed golden defect is permanent. Under those terms, demanding an auditable "LLM saw page k" sidecar is reasonable even though extraction pipelines are irrelevant precedent. Impact: `--all-pages` addresses an operator trust gap, not a parity gap with docling.

- [HIGH] **Fleet-mode objections survive as design constraints, not as veto.** Per-page-judging SYNTHESIS worst-page-wins noise (`1-(1-p)^n`, 28.1% at n=33, p=1%) and agreeableness bias (LLM validators TPR >96%, TNR <25%, 05-web Q4 arXiv 2510.11822) still apply to raw per-page LLM passes. What changes in review mode: cost is one paper not 189, and false flags are triaged by a human rather than blocking fleet throughput. Impact: `--all-pages` should emit per-page audit fields and cap document verdict conservatively, not promise extraction-style "full coverage = high precision."

- [HIGH] **Current PDF lane cannot deliver even routed exhaustive checks, let alone all pages.** `--exhaustive-units` / `--inspect` are wired only to the text lane (`cli.py:1186-1187`); PDF calls `judge_pdf_extraction` without exhaustive (`cli.py:1122-1127`). `run_unit_checks` is invoked without `exhaustive` (`pdf_judge.py:843-850`) and returns `None` when routing yields no signals (`unit_judge.py:287-288`), so silent pages never get a unit check. Impact: the operator's live P1068R11 result (5/15 pages) is a wiring defect plus routing semantics, not evidence that all-pages verification is inherently impossible.

- [MED] **Extraction "all pages" still has holes extraction advocates elide.** olmocr falls back to pdftotext after retries with document-level ratio gate only (`pipeline.py:557-567` per `10-olmocr-pipeline-coverage.md`). marker `--use_llm` may incur zero LLM calls on text-only pages (`05-web Q5`). langextract can silently drop failed chunks with `suppress_parse_errors=True` (05-web Q2). Impact: even category (a) "full coverage" is not fail-closed verification; copying extraction accounting without our stricter audit would false-pass golden review.

- [LOW] **Portable orchestration from olmocr, portable semantics from olmocr-bench.** Enumerate `range(1, num_pages+1)` and fail closed on missing page results (`pipeline.py:548-551`); score with deterministic page-scoped facts (`tests.py:168-173`) where LLM is unnecessary; use LLM only for semantic gaps the fact engine cannot encode. Impact: `--all-pages` should be "required `page:N` units + coverage bitmap + separate fingerprint" (`00-baseline.md:44`), not "run docling VLM again."

## False-pass hypothesis

A 15-page golden PDF where pages 3, 7, and 11 have no router signals (high recall, no caption/table drift) and the monolith returns `pass` with empty `missing_content`: under today's code those pages never enter `run_unit_checks` (`unit_judge.py:287-288`), and even `--all-pages` that only forces LLM units without a deterministic per-page screen could rubber-stamp at conf ≥ 0.95 (SYNTHESIS agreeableness finding) while localized corruption persists on "quiet" pages.

## False-fail hypothesis

Forcing LLM `page:N` checks on every page without injecting the full conversion contract (YAML front matter on page 1, TOC removal, figure-internal text sanctions, header/footer below 3 pages) reproduces the per-page-judging page-1/TOC traps (SYNTHESIS summary): each sanctioned omission becomes a spurious `missing_content` flag, and worst-page-wins aggregation caps the document at `review` despite a faithful conversion.

## What would change my mind

A labeled golden holdout (≥30 papers) showing that deterministic per-page recall + monolith + scoped escalation already catches ≥90% of verified defects **and** that adding mandatory LLM `page:N` checks on the remaining pages does not materially increase caught defects while adding <5% human-triage noise — would downgrade `--all-pages` from justified to redundant.
