# 15 - Gating-Semantics-Cartographer

**Verdict:** usable-with-conditions (+ baseline central claim holds after precision sharpening; two olmocr anchors mislabel line semantics; marker in-loop retry is a real hybrid that must be named explicitly)
**Confidence:** high

## Findings

- [CRITICAL] Sharpened claim: **zero of 31 repos use a separate LLM quality-judge signal to mechanically accept/reject converted document output or block CI/release.** Closest counterexamples are **in-loop self-critique** (marker table rewrite) and **advisory benchmark judges** (marker LLMScorer), neither of which gate shipment. Evidence: marker `benchmarks/verify_scores.py:12-13,21-22` (CI raises on deterministic heuristic mean `< 90` and table TEDS mean `< 0.7` only); marker `benchmarks/overall/overall.py:60-63` (LLM scorer exceptions caught, sample continues); marker `.github/workflows/benchmarks.yml:28-35` (CI invokes `verify_scores.py`, not `llm.py`). Impact: whisker's "deterministic gates decide + advisory LLM lane" matches ecosystem practice; the baseline is sound once "mechanical gate" is defined as **accept/reject/CI-block**, not any LLM-emitted number with any downstream effect.

- [HIGH] **Spot-check VALID — marker CI is deterministic-only.** `benchmarks/verify_scores.py:12-13` raises `ValueError("Marker score below 90")` on mean heuristic `< 90`; `:21-22` raises on table `marker_score` mean `< 0.7`. Baseline anchor `verify_scores.py:12-22` holds (lines exact in clone). Impact: supports 05-web.md / Q5 / Marker CI gates heuristic only.

- [HIGH] **Spot-check VALID — marker in-loop LLM score triggers bounded retry, not document reject.** `marker/processors/llm/llm_table.py:213-225`: `score = response.get("score", 5)`; if `score < 4` and `total_iterations < self.max_table_iterations`, recursive `rewrite_single_chunk` retry. Signal → effect → blast radius: **same-call LLM self-score → regenerate one table block → single block, max-iteration cap; document always emitted, CI unaffected.** Classify as **G4 (in-loop self-critique)**, not G9 (judge gate). Impact: blurs naive "zero LLM mechanical effect" wording but does **not** contradict whisker architecture; whisker fusion explicitly forbids LLM hard-fail (`fusion.py:124-252` per baseline §3).

- [HIGH] **Spot-check VALID — marker LLM-as-judge is advisory in benchmark harness.** `benchmarks/overall/scorers/llm.py:94-134` (`LLMScorer.__call__` / `llm_rater` returns structured integer scores); `benchmarks/overall/overall.py:60-63` catches scorer exceptions with comment "Some scorers can fail, like the LLM one" and `continue`. Signal → effect → blast radius: **Gemini judge scores → logged into `result.json` only → corpus telemetry; CI ignores.** Classify as **G5 (advisory judge)**. Impact: marker is the only repo with LLM-as-judge at all; it is explicitly non-blocking.

- [HIGH] **Spot-check VALID with line drift — olmOCR bench gates on deterministic fact pass-rate, not LLM judge.** `olmocr/bench/tests.py:150-176` (`TextPresenceTest.run`: `fuzz.partial_ratio` vs `threshold = 1.0 - max_diffs/len`); `olmocr/bench/benchmark.py:115-126` (majority-of-repeats pass, `final_passed = test_avg > 0.5`); `olmocr/bench/benchmark.py:387-388` (overall score = mean of per-JSONL pass rates). Baseline cited `tests.py:114-125` for gating — **STALE**: `:114-125` is `BasePDFTest.run` docstring, not gate logic; actual checks start at `:150-176`. Impact: olmOCR principle (machine-checkable facts) confirmed; anchor line needs correction.

- [MED] **Spot-check PARTIAL — olmOCR `checked: verified` is human workflow metadata, not a runtime LLM gate.** `olmocr/bench/tests.py:36-38,101` (`TestChecked.VERIFIED`, `checked` field on `BasePDFTest`); `olmocr/bench/review_app.py:26-34` finds PDFs with `checked is None` (unchecked), not verified-only filtering; `review_app.py:54-57` counts `status == "verified"`. `load_tests` (`tests.py:809-867`) loads **all** JSONL lines with no `checked == verified` filter; `benchmark.py:227-230` evaluates full loaded set. Baseline anchor `review_app.py:26-34` for "verified flag" is **STALE** (lines are unchecked-queue logic; verified counting is `:54-57`). Impact: ground-truth governance is **human-in-the-loop dataset curation**, then deterministic pytest-style checks — aligns with whisker/olmOCR precedent but overstates "bench gates only on verified" as an automated runtime filter.

- [MED] **Spot-check VALID — olmOCR pipeline never hard-fails a page; mechanical validity → retry → fallback.** `olmocr/pipeline.py:314-332`: rotation-invalid paths retry; after `MAX_RETRIES`, `make_fallback_result` (pdftotext fallback) at `:328-332`. Triggers are **structural validity** (`is_valid`, `is_rotation_valid`), not a separate judge model. Classify as **G3/G7 (structural retry + fallback lane)**. Baseline `pipeline.py:329-332` holds (off by 1 line). Impact: conversion always completes; quality control is post-hoc bench, not in-path judge gate.

- [MED] **Spot-check VALID — MinerU LLM title enrichment is fail-soft; E2E gates are deterministic.** `mineru/utils/llm_aided.py:217-218` (`return None` after max decode retries); `:221-223` (`if levels_by_index is None: return` in `_apply_levels_to_blocks` — no-op, document proceeds). `tests/unittest/test_e2e.py:163-169,213-219` hard-assert `fuzz.ratio > 90` on captions/text (deterministic, not LLM judge). Baseline `llm_aided.py:221-223` exact; `test_e2e.py:163-220` holds with drift (`:220` is `len(type_set) >= 4`). Classify LLM path as **G6 (optional enrichment fail-soft)**; E2E as **G1**. Impact: MinerU uses VLM as engine but does not let LLM QA block output.

- [MED] **Spot-check VALID with line drift — docling "grades" do not block conversion; layout drops use deterministic confidence thresholds.** `docling/datamodel/base_models.py:557-577` (`_score_to_grade`, `mean_grade`/`low_grade` computed fields on `PageConfidenceScores` — informational); `document_converter.py` has no `mean_grade`/`low_grade` abort (spot-checked). Mechanical pruning: `docling/utils/layout_postprocessor.py:175-193` (`CONFIDENCE_THRESHOLDS` per label); `:264-268` drops clusters where `c.confidence < self.CONFIDENCE_THRESHOLDS[c.label]`. Baseline `layout_postprocessor.py:175-193` cites thresholds correctly but omits drop site `:264-268`. Classify as **G2 (deterministic model-confidence prune)** — layout-model score, not LLM judge. Impact: docling "confidence drives workflow" is opt-in downstream; default conversion emits with pruned low-confidence clusters.

## Corrected gating taxonomy (signal → effect → blast radius)

| Tier | Name | Signal source | Mechanical effect | Blast radius | 31-repo examples |
|------|------|---------------|-------------------|--------------|------------------|
| G0 | Unconditional emit | — | Always accept output | Whole document | pandoc, html2text, pdfplumber, … |
| G1 | Deterministic validation | Rules, goldens, fuzzy anchors | Accept/reject test or CI job | Per-assertion / per-paper | olmOCR bench `tests.py:150-176`; MinerU `test_e2e.py:163-219`; langextract `resolver.py:1006-1014,691-707`; firecrawl/markitdown CI vectors |
| G2 | Deterministic model-confidence prune | Layout/OCR/detector scores (not judge LLM) | Drop/filter elements below threshold | Per-cluster / per-box | docling `layout_postprocessor.py:264-268` |
| G3 | Same-model structural validity | finish_reason, schema, rotation flags | Retry same model call | Per-page / per-block attempt | olmOCR `pipeline.py:314-341` |
| G4 | **LLM self-critique in-loop** | Score/analysis from **same** LLM rewrite call | **Retry/regenerate** sub-output | **Bounded sub-component** (one table block) | marker `llm_table.py:213-225` |
| G5 | LLM-as-judge advisory | Separate judge model scores | Log/telemetry; skip on failure | Benchmark report only | marker `llm.py:94-134`, `overall.py:60-63` |
| G6 | Optional LLM enrichment fail-soft | LLM post-processor output | No-op on failure; emit without enrichment | Metadata fields only | MinerU `llm_aided.py:217-223` |
| G7 | Mechanical reroute/fallback | Parse error, repeat loop, blank detection | Switch to fallback lane; still emit | Per-page | surya `recognition/__init__.py:292-324`; olmOCR `pipeline.py:328-332`; Dolphin `demo_page.py:203-208` |
| G8 | Human-verified ground truth | Human marks `checked: verified` in dataset | Deterministic tests run on committed facts | Benchmark corpus definition | olmOCR `tests.py:36-38,101`, `review_app.py:54-57` |
| **G9 (NOT FOUND)** | **LLM judge accept/reject gate** | Separate LLM quality verdict | **Block CI, abort conversion, or withhold accept** | **Document / release** | **None observed in 31 clones** |

**Whisker mapping:** `gates.py:209-218` = G1 hard-fail; `score.py:136-231` + unigram floors = G1 soft/review; `fusion.py:124-252` = G5 advisory bounded (can rescue to review, never G9 hard-fail). Whisker deliberately omits G4 (no in-loop LLM self-retry on conversion output).

## False-pass hypothesis

marker `llm_table.py:218-225` accepts the last rewrite when `score >= 4` or iterations exhaust — a table block with judge-score 4 can still ship with wrong cell structure, and CI never sees it because `verify_scores.py:12-13` averages unrelated heuristic/TEDS axes. Concrete case: scrambled table passes in-loop self-score, document emits, CI green.

## False-fail hypothesis

olmOCR `tests.py:167-176` fuzzy presence with `max_diffs` can false-fail a correct Unicode-normalized paraphrase that humans would accept — but that is a **deterministic** test false-fail, not an LLM-judge false-fail. No repo implements LLM-judge gating, so LLM-judge false-fail is **none found** across the 31-repo set.

## What would change my mind

A single reference repo where CI or `convert`/`parse` **aborts or returns non-success** conditioned on a **separate LLM judge verdict** (not same-call self-score, not deterministic alignment of LLM output) — e.g. `if judge_verdict == FAIL: raise` or `sys.exit(1)` in a workflow file analogous to marker `benchmarks.yml:28-35`. Grep target: judge model call → boolean gate → process exit in one chain.
