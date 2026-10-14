# 05 - docling-vlm

**Verdict:** usable-with-conditions — Docling’s `ConfidenceReport` grade-aggregation pattern is directly portable for goal 3, but there is no hybrid deterministic+LLM score fusion and the VLM pipeline emits status flags, not numeric confidence.
**Confidence:** medium

## Findings
- [CRITICAL] Docling fuses multi-axis numeric scores into two document-facing grades via `PageConfidenceScores`: `mean_score = np.nanmean([ocr, table, layout, parse])`, `low_score = np.nanquantile(..., q=0.05)`, then `_score_to_grade` maps both to `POOR|FAIR|GOOD|EXCELLENT` at thresholds 0.5 / 0.8 / 0.9. Evidence: `docling/datamodel/base_models.py:531-606`.
  Impact: Closest upstream analog to whisker goal 3 — keep det and LLM lanes visible, add a reported `mean_grade`/`low_grade` composite without touching the deterministic verdict (C1).
- [HIGH] Document-level aggregation is two-stage and pessimistic on parse: per-page scores are written during stages; at pipeline end `standard_pdf_pipeline` sets doc-level `layout_score`/`ocr_score`/`table_score` via `np.nanmean` over pages but `parse_score` via `np.nanquantile(..., q=0.10)` (“worst 10% of pages”). Evidence: `docling/pipeline/standard_pdf_pipeline.py:1060-1088`, `docling/models/stages/page_preprocessing/page_preprocessing_model.py:78-88`.
  Impact: Whisker merge should not use one reducer for every axis; a worst-page / worst-axis tail (like tapetum `worst_axis`) matches Docling’s parse aggregation and our 2026-07-06 triage data (00-baseline: 123/194 tapetum verdict diffs).
- [HIGH] `table_score` is schema-only today: docs mark it “not yet implemented”; no TableFormer stage writes page `table_score` (only NaN aggregation in the pipeline). Evidence: `docs/concepts/confidence_scores.md:42`, `docling/pipeline/standard_pdf_pipeline.py:1079-1082` (no writers in `docling/models/stages/table_structure/*`).
  Impact: Docling’s four-axis `mean_grade` effectively runs on three live axes; whisker should not treat “missing axis = pass” when copying the pattern (aligns with 00-baseline: 6 tapetum errors leave no LLM sidecar).
- [HIGH] Standard-PDF confidence is deterministic-only: layout clusters carry model `confidence`; page `layout_score` = mean of postprocessed cluster confidences; page `ocr_score` = mean of OCR cell confidences (`from_ocr` only). Evidence: `docling/models/stages/layout/layout_model.py:208-238`, `docling/models/stages/layout/layout_object_detection_model.py:126-136`.
  Impact: Docling confidence measures pipeline self-consistency, not external oracle agreement — parallel to whisker `ref_*` advisory metrics, not a substitute for tapetum.
- [MED] Model confidence gates routing, not fusion: layout postprocessor drops clusters below per-label thresholds (0.45–0.5) and resolves overlaps by confidence/area rules; EasyOCR drops lines below `confidence_threshold` (default 0.5); picture VLM description skips images below `classification_min_confidence`. Evidence: `docling/utils/layout_postprocessor.py:175-192`, `docling/models/stages/ocr/easyocr_model.py:193`, `docling/datamodel/pipeline_options.py:400-408`, `docling/models/picture_description_base_model.py:147-179`.
  Impact: Portable for tapetum cascade thresholds (goal 1), not for merged numeric verdict math (goal 3).
- [MED] VLM pipeline (SmolDocling / `VlmConvertOptions.from_preset("smoldocling")`) validates output via `ConversionStatus`, not `ConfidenceReport`: `_determine_status` marks `PARTIAL_SUCCESS` when a page lacks VLM output or `stop_reason` is `LENGTH` or `CONTENT_FILTERED`. Evidence: `docling/pipeline/vlm_pipeline.py:236-273`, `docling/datamodel/stage_model_specs.py:1030-1036`, `tests/test_vlm_pipeline_status.py:1-120`.
  Impact: No upstream pattern for LLM-lane numeric confidence or VLM-vs-standard merge; tapetum’s `confidence [0..1]` field is already richer than Docling VLM.
- [MED] Confidence artifacts are first-class and precomputed for consumers: `ConversionResult.confidence: ConfidenceReport`; persisted as `confidence.json` inside the conversion ZIP; remote API exposes a JSON-safe `ConfidenceScores` snapshot with stored `mean_grade`/`low_grade` (document-level only, no per-page wire field yet). Evidence: `docling/datamodel/document.py:382`, `docling/datamodel/document.py:466`, `docling/datamodel/service/responses.py:28-60`, `docling/service_client/client.py:396-399`.
  Impact: Direct template for goal 2 — extend `<pid>.whisker.json` with a `lanes`/`merged` block mirroring Docling’s “grades on the result object + sidecar JSON” shape while keeping separate lane fields visible.
- [LOW] Product guidance: docs tell users to rely on `mean_grade` and `low_grade`, treating raw scores as internal and subject to change. Evidence: `docs/concepts/confidence_scores.md:12-14`.
  Impact: Supports C1 — merged grade is a reported composite; deterministic `verdict` stays authoritative on record.

## False-pass hypothesis
Adopt Docling `mean_grade` only (nanmean of det pass-tier signals + tapetum `confidence`) on a paper like 00-baseline `p4003r0` (whisker `review`, tapetum `fail` at 0.95 confidence on `tables/major`): a simple mean can land in `GOOD`/`EXCELLENT` while the LLM lane found a major tables fail, wrongly “accepting” a bad conversion in a merged column.

## False-fail hypothesis
Adopt Docling `low_score` / 5th-percentile tail across whisker axes plus tapetum axis findings: one minor OCR/layout blip on an otherwise clean WG21 paper (whisker `pass`, tapetum `pass`) could drag `low_grade` to `FAIR`/`POOR` and force unnecessary review — matching Docling’s intentional “highlight worst-performing areas” bias (`docs/concepts/confidence_scores.md:48-49`).

## What would change my mind
Finding in `docling/pipeline/vlm_pipeline.py` (or a VLM model stage) that populates `ConfidenceReport.pages` or a documented det+VLM hybrid merge path — neither exists in current HEAD; VLM quality is status-only.
