# 04 - MinerU LLM/VLM scoring

**Verdict:** usable-with-conditions — MinerU has no LLM QA scoring or deterministic+LLM merge, but its optional LLM post-step, backend-stratified QA thresholds, and span-level CV confidences in `middle.json` are portable patterns for whisker's dual-lane design.
**Confidence:** high

## Findings

- [CRITICAL] MinerU does **not** implement hybrid deterministic+LLM **quality scoring** or score fusion; the only in-repo LLM module is optional title hierarchy optimization (`llm_aided_title`), not extraction QA. Evidence: `mineru/utils/llm_aided.py:352-383`, `mineru/utils/title_level_postprocess.py:32-44`; repo-wide search finds no `judge`, `quality_check`, or LLM score output beyond title levels.
  Impact: Goals 1–3 cannot copy a MinerU merge formula; tapetum remains the LLM lane; any merged score must be whisker-native (baseline C1–C2).

- [HIGH] LLM-aided title leveling is **opt-in and config-gated**; default is off. When disabled or misconfigured, finalize skips LLM entirely and keeps deterministic heading rules. Evidence: `mineru.template.json:16-23` (`enable: false`), `mineru/utils/title_level_postprocess.py:17-29`, `mineru/utils/config_reader.py:207-216`.
  Impact: Goal 1 — mirrors whisker's advisory/isolated LLM lane (C1): LLM never blocks parse output; whisker should treat missing/disabled LLM the same way baseline records 6 tapetum errors (00-baseline:51).

- [HIGH] LLM title failures **fall back silently** to deterministic levels: after 3 retries `_request_title_levels` returns `None`, `_apply_levels_to_blocks` no-ops (`llm_aided.py:189-218,221-223`), then pipeline `_post_block_process` assigns `doc_title→level 1`, `paragraph_title→level 2` (`model_json_to_middle_json.py:196-207,216-222`). No partial/error artifact is emitted.
  Impact: Goal 3 — merge design must handle `llm_lane: absent` without failing the paper; MinerU shows fail-open on LLM error, opposite of whisker fidelity (C5) for analytical lanes, but appropriate for non-gating post-processing.

- [HIGH] **Three backends** (`pipeline`, `vlm`, `hybrid`) share finalize hooks but differ in score provenance: pipeline/hybrid propagate layout/OCR `score` floats (`batch_analyze.py:373-397,893-895`; `hybrid_analyze.py:533,570`); pure VLM blocks document `score: null` in `model.json` (`docs/en/reference/output_files.md:522-523,531-532`). Hybrid = pipeline layout + VLM content extraction (`hybrid_analyze.py:15-36,670-676`; `hybrid_model_output_to_middle_json.py:181-188`).
  Impact: Goal 2 — persist `reference_engine` / backend in whisker sidecar so merged reports can apply backend-specific slack (extends redteam MinerU.md `test_e2e.py:198-201` pattern).

- [MED] Per-block **CV confidences** live in `model.json` and span-level `middle.json`, **not** in `content_list.json`. Layout cls scores in `model.json` (`output_files.md:73-97`); span `score` in pipeline `middle.json` (`output_files.md:222,278`); `make_blocks_to_content_list` emits type/text/bbox only, no score field (`pipeline_middle_json_mkcontent.py:609-651`). VLM `content_list` adds types but docs do not define QA scores (`output_files.md:660-675`).
  Impact: Goal 2 — if whisker co-persists lanes, middle-style span scores are the MinerU analogue for deterministic confidence, separate from tapetum `confidence`; do not expect conversion goldens to carry scores.

- [MED] Deterministic **confidence gates** filter low-quality spans before output (not LLM): `OcrConfidence.min_confidence = 0.5` drops/removes weak OCR (`ocr_utils.py:10-12`; `batch_analyze.py:897-918`); layout uses per-class thresholds (`pp_doclayoutv2.py:61-88`). PDF routing uses text-quality heuristics (`pdf_classify.py:20-21,165-168`), not LLM.
  Impact: Goal 3 — deterministic lane can expose min OCR/layout confidence as advisory axes; these are preprocessing filters, not fused with any LLM verdict.

- [MED] In-repo **eval for model/LLM stages is thin**: CI runs pipeline `txt`+`ocr` on one PDF with fuzzy/substring asserts (`test_e2e.py:50-71,152-220`); `vlm` branch in `assert_content` (0.7 table hit-rate) is **never invoked** in tests (`test_e2e.py:200-201` vs `50-71`); no `llm_aided` tests; CI meta-gate is code coverage ≥20% (`get_coverage.py:20`, `.github/workflows/cli.yml:37-39`); OmniDocBench Overall is README/marketing only (`docs/en/quick_start/index.md:99`).
  Impact: Goal 1 — MinerU does not validate LLM stages in CI; whisker should not borrow their eval story for tapetum, only the backend-stratified threshold idea from redteam.

- [LOW] **Hybrid effort** (`medium`/`high`) trades accuracy for speed and disables image/chart analysis on `medium` (`hybrid_analyze.py:81,117-121`; README 3.3 notes −0.13 OmniDocBench Overall for medium). Metadata persisted as `_effort` in `middle.json` (`hybrid_model_output_to_middle_json.py:181-188`).
  Impact: Goal 3 — merged scoring should treat `effort`/backend as context dimensions, not a single global threshold (aligns with redteam parse-method split).

## False-pass hypothesis

A table block with only 71% of required cell substrings present passes MinerU's VLM QA bar (`test_e2e.py:200-201`: `correct_count > 0.7 * len(target_str_list)`) while deterministic whisker TEDS/NID still look acceptable on sparse GT. A naive merge that takes `max(det_pass, llm_pass)` or averages without backend-aware floors would false-pass localized table loss that MinerU's txt/ocr path would reject at 90% (`test_e2e.py:198-199`).

## False-fail hypothesis

Pipeline OCR drops a span when `ocr_score < 0.5` (`batch_analyze.py:897-918`) even if the rendered text is mostly correct; no LLM rescue runs. Analogous to whisker deterministic `fail` on coverage with tapetum `pass`: a merge rule that requires **both** lanes to pass (AND) would false-fail papers where the LLM lane correctly adjudicates OCR noise the deterministic preprocessor discarded.

## What would change my mind

An in-repo module (post-3.4) that calls an LLM/VLM judge per block, writes numeric quality/confidence into `content_list.json` or a dedicated sidecar, and documents a fusion rule with deterministic layout/OCR scores — with tests that exercise the LLM path in CI.
