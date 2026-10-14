# 16 - nougat-surya-analyst

**Verdict:** usable-with-conditions — both repos guarantee one model pass per PDF page and surface decode failures, but they are extraction pipelines, not verification judges; Surya's structured per-page result objects map cleanly to our sidecar audit schema, while Nougat's in-band `[MISSING_PAGE_*:n]` markers are the stronger anti-silent-absence pattern but must not pollute golden markdown.
**Confidence:** high

## Findings

- [CRITICAL] Neither Nougat nor Surya implements verification coverage (LLM judges output against source); both architecturally guarantee extraction coverage via one inference call per page. Evidence: `packages/whisker/research/repos/nougat/predict.py:166-195` (per-page `model.inference` loop); `packages/whisker/research/repos/surya/surya/recognition/__init__.py:274-283` (one `BatchInputItem` per page); `05-web.md` Q3 olmOCR-Bench — deterministic per-page baseline tests, no LLM in eval loop. Impact: prior art validates "every page got a model call," not "every page was LLM-verified against golden"; our `--all-pages` review mode must not cite these as verification analogues.

- [HIGH] Nougat makes failed pages visible in-band with numbered sentinel tokens instead of omitting them. Evidence: `packages/whisker/research/repos/nougat/predict.py:178-190` emits `[MISSING_PAGE_EMPTY:{page_num}]` when postprocessing yields `[MISSING_PAGE_POST]` or repetition index is 0, and `[MISSING_PAGE_FAIL:{page_num}]` when `repeats[j] > 0`; postprocessing seeds `[MISSING_PAGE_POST]` at `packages/whisker/research/repos/nougat/nougat/postprocessing.py:323`. Impact: downstream consumers can grep/count markers and reconcile `page_count`; portable to our sidecar as out-of-band status codes (`empty`, `fail`, `repetition`) keyed by page number, not as markdown inserts.

- [HIGH] Nougat detects decoder failure per page at two layers: token-logit repetition during generation and string-level tail repetition in postprocess. Evidence: `packages/whisker/research/repos/nougat/nougat/model.py:618-651` (logit-variance `repeats` index, sequences truncated at repeat point); `packages/whisker/research/repos/nougat/nougat/postprocessing.py:102-165,360-363` (`truncate_repetitions`, then `remove_hallucinated_references`). Impact: gives us a cheap deterministic pre-screen before expensive LLM unit checks (similar to olmOCR non-empty/no-runaway-repetition baseline in `05-web.md` Q3); not a substitute for semantic golden review.

- [MED] Nougat's fail-closed markers are opt-out and known to false-positive on CPU/older GPUs. Evidence: `packages/whisker/research/repos/nougat/predict.py:74-77,181` (`--no-skipping` disables heuristic; skipping gated on `args.skipping`); `packages/whisker/research/repos/nougat/README.md:184-188` documents all-`[MISSING_PAGE]` outputs and recommends `--no-skipping`. Impact: copying Nougat verbatim without a sidecar escape hatch would false-fail legitimate golden pages in review mode; any adopted marker logic needs human-triage semantics, not hard pipeline abort.

- [HIGH] Surya always returns one structured page object per input page; CLI writes a fixed-length page list with explicit page numbers. Evidence: `packages/whisker/research/repos/surya/surya/input/load.py:26-29` (default `page_range = list(range(last_page))`); `packages/whisker/research/repos/surya/surya/recognition/__init__.py:368-375` (backfill `PageOCRResult` for any still-None slot); `packages/whisker/research/repos/surya/surya/scripts/ocr_text.py:28-37` (`zip(loader.names, page_results)` then `"page": len(out_preds[name]) + 1`). Impact: sidecar pattern is `pages_checked == pdf_page_count` by construction; directly portable to `PdfJudgeResult` audit fields planned in `00-baseline.md`.

- [HIGH] Surya surfaces per-block failure and confidence in typed results, not in document text. Evidence: `packages/whisker/research/repos/surya/surya/recognition/schema.py:8-19` (`BlockOCRResult.error`, inherits `PolygonBox.confidence` from `packages/whisker/research/repos/surya/surya/common/polygon.py:11`); `packages/whisker/research/repos/surya/surya/recognition/__init__.py:226-237` sets `error=True, confidence=0.0` when batch output missing or `out.error`; `packages/whisker/research/repos/surya/surya/inference/schema.py:39-45` (`BatchOutputItem.error`, `mean_token_prob`). Impact: best prior art for our sidecar `{page, unit_status, confidence, error_reason}` records; UI can color red/orange/green as in `packages/whisker/research/repos/surya/surya/scripts/streamlit_app.py:165,383-424`.

- [MED] Surya heals full-page failures via layout+block fallback, so first-pass failure is not recorded at page level. Evidence: `packages/whisker/research/repos/surya/surya/recognition/__init__.py:267-366` (`needs_fallback` on `out.error`, empty non-blank output, `_detect_repeat_loop`, or parse exception; fallback replaces `results[page_idx]` with block-mode output). Impact: `results.json` can show a fully green page even when full-page OCR failed; for golden review we must log escalation/fallback in sidecar (Nougat's explicit FAIL marker is more honest for operator triage).

- [LOW] Nougat's HTTP app uses a different, non-numbered failure surface than the CLI. Evidence: `packages/whisker/research/repos/nougat/app.py:96-149` (pre-sized `predictions` list per page; repetition/empty pages get `+++ ==WARNING==` / `+++ ==ERROR==` disclaimers appended, per-page files under `pages/`). Impact: confirms the core idea (never drop a page slot) but shows marker format is not stable across entrypoints; our sidecar should own the canonical schema.

## False-pass hypothesis

Surya full-page OCR fails on a non-blank golden page, block-mode fallback returns partial HTML with `error=False` on surviving blocks (`packages/whisker/research/repos/surya/surya/recognition/__init__.py:350-366`), and `results.json` lists a normal page entry — an operator (or our `--all-pages` sidecar mirroring only final status) would treat the page as successfully processed with no record of the first-pass failure.

## False-fail hypothesis

Nougat flags a valid dense table or repeated boilerplate as repetition (`packages/whisker/research/repos/nougat/nougat/model.py:636-645`) and replaces the page with `[MISSING_PAGE_FAIL:n]` (`packages/whisker/research/repos/nougat/predict.py:184-185`); in review mode that would look like a golden defect when the PDF page is fine.

## What would change my mind

Finding post-extraction per-page QA in either clone that compares model output back to the source page (image or text layer) with an explicit pass/fail verdict per page — analogous to our planned LLM unit check, not merely decode-health heuristics.
