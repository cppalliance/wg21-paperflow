# 26 - surya-ocr-error-analyst

**Verdict:** usable-with-conditions — the OCR-error DistilBERT is a real, text-only, CPU-cheap garbled-text signal worth a third lane, but OpenRAIL-M model-weight terms and its narrow binary scope block naive in-repo bundling for a public BSL-1.0 project.
**Confidence:** high (OCR-error path read in-repo); medium (layout-as-grounding, license risk for C++ Alliance scale)

## Findings

- [CRITICAL] Model weights are **not** Apache-2.0: `MODEL_LICENSE` is a modified AI Pubs OpenRAIL-M license with revenue/funding caps ($5,000,000 prior-year gross revenue or total equity/debt funding, `MODEL_LICENSE:56-57`), a **competing-product ban** if you offer a product/service that competes with datalab.to (`MODEL_LICENSE:58`), and a **Share-a-Like** clause requiring the same license on Model derivatives and on Output derivatives (`MODEL_LICENSE:39`). Source code alone is Apache-2.0 (`LICENSE:1-4`, `README.md:67-69`). For a public BSL-1.0 repo shipping conversion QA, this is the adoption gate: legal review before bundling weights or calling the model in production; datalab commercial terms at `README.md:69`.
  Impact: OCR-error and layout checkpoints cannot be treated like olmOCR's Apache-2.0 weights (`05-web.md` Q2); GPL is **not** the issue here, OpenRAIL-M revenue/compete/share-alike is.

- [HIGH] OCR-error detection is **text-only**: `OCRErrorPredictor.__call__` takes `List[str]`, tokenizes with DistilBERT, runs sequence classification, returns string labels — no images (`surya/ocr_error/__init__.py:18-52`, `surya/ocr_error/schema.py:6-8`). Input is extracted/plain text; it classifies **surface OCR quality** (garbled vs readable), not fidelity vs the PDF.
  Impact: It can score tomd markdown directly as a garbled-text detector without opening the PDF, independent of the deterministic whisker lane and the tapetum LLM lane — but it does **not** judge "did we lose content vs the page image."

- [HIGH] Labels are a hard **binary argmax** with no confidence threshold: `ID2LABEL = {0: 'good', 1: 'bad'}` (`surya/ocr_error/model/config.py:9-12`); inference uses `logits.argmax(dim=1)` inside `torch.inference_mode()` (`surya/ocr_error/__init__.py:45-51`). Tests expect `"bad"` on Hindi-script garbage and `"good"` on English prose (`tests/test_ocr_errors.py:1-15`).
  Impact: Portable as a cheap lane only if whisker runs **softmax scores through `calibrate.py`** (redteam surya §2.7); raw argmax will false-fail/format-sensitive prose and false-pass semantic corruption that reads cleanly.

- [HIGH] Model architecture and limits: custom DistilBERT seq-classifier, 6 layers / 768 dim / 512 max positions (`surya/ocr_error/model/config.py:24-38`), checkpoint `s3://ocr_error_detection/2025_02_18` (`surya/settings.py:119`). Default device falls back to **CPU** with float32 (`surya/settings.py:29-37,134-137`); OCR-error batch defaults `cpu: 8` (`surya/ocr_error/__init__.py:16`). No CLI entry — only Python API + pytest fixture (`pyproject.toml:34-40`, `tests/conftest.py:54-55`).
  Impact: ~66M-param footprint, sub-GB RAM, no GPU required for this component alone; integration is a library call or thin subprocess, not `surya_ocr`. Full papers exceed 512 tokens — must chunk (by H2/paragraph) and aggregate (worst chunk wins).

- [MED] **No shipped CLI or production wiring** for OCR-error in v0.20.0: README mentions it (`README.md:31,113`) but `pyproject.toml` scripts are detect/ocr/layout/table/gui only (`pyproject.toml:34-40`); `OCRErrorPredictor` appears only in `tests/conftest.py` and `tests/test_ocr_errors.py`. Surya's own QA story for quality is external olmOCR-bench pass rates (`README.md:25,378-408`), not in-repo OCR-error gates.
  Impact: We would be the first consumer integrating this as a gate; no upstream operating-point or ROC to copy.

- [MED] Layout/reading-order in **Surya 2** is VLM-backed, not the old ~80M Segformer cited elsewhere: `LayoutPredictor` sends page images through `SuryaInferenceManager.generate` with JSON-schema guided decoding (`surya/layout/__init__.py:54-67,97-125`); reading order is `LayoutBox.position` (`surya/layout/schema.py:11-12`, `README.md:252-258`). Default generation uses `temperature=0.0` (`surya/inference/backends/openai_client.py:161-162`), so outputs are **mostly** deterministic at the API layer, but still depend on a 650M VLM server (`README.md:23`, `surya/settings.py:40-44,79-83`).
  Impact: Bbox inventory + reading order can ground a VLM judge (DocVAL-style region checks, `05-web.md` Q4 DocVAL card) or supply structural sidecars, but this is **not** a cheap third lane — it needs PDF rasterization + vLLM/llama.cpp (12GB+ class per `models-vram-deployment-survey.md:149-153`), orthogonal to the text-only OCR-error model.

- [MED] **Detection** (line bboxes) remains a separate lightweight torch model (EfficientViT semantic segmentation, `surya/detection/loader.py:8-46`, checkpoint `surya/settings.py:110-116`) with image-adaptive thresholds (`surya/detection/heatmap.py:13-23`) and CPU batch 8 (`surya/detection/__init__.py:24`). It gives deterministic-ish line boxes without the VLM, but **not** typed layout labels or reading order.
  Impact: Partial structural grounding without full layout VLM cost; still OpenRAIL-M weight terms for the detector checkpoint.

- [LOW] Pulling `surya-ocr` as a dependency drags **torch>=2.7**, transformers, opencv-headless, pypdfium2, optional vLLM/docker stack for anything beyond OCR-error (`pyproject.toml:12-29`, `README.md:79-88`). OCR-error alone avoids the VLM server; the full package does not.
  Impact: Value/footprint ratio is excellent for **OCR-error only** (~250MB class weights + CPU inference); poor if we import all of surya to get one DistilBERT.

## False-pass hypothesis

A WG21 paper whose markdown reads as fluent English (high `unigram_coverage`, tapetum pass) but silently swaps a table cell or drops a math exponent: OCR-error returns `"good"` on every chunk because the surface text is not garbled (`tests/test_ocr_errors.py:10-15` trains the opposite failure mode), while the deterministic and LLM lanes also miss it unless Lane-3 facts or a PDF-grounded VLM fires.

## False-fail hypothesis

A clean conversion with legitimate Devanagari/CJK technical terms, heavy inline `$...$` math, or markdown punctuation clusters tokenized as `"bad"` by the English-biased DistilBERT (`do_lower_case=True`, `surya/ocr_error/tokenizer.py:88-90`) — argmax flips to `"bad"` with no calibrated threshold, forcing review on valid international WG21 papers.

## What would change my mind

Measured ROC on our WG21 markdown corpus (softmax scores, not argmax) showing ≥90% TPR at ≤10% FPR for garbled-output detection **plus** written confirmation that C++ Alliance / paperflow use is outside OpenRAIL-M §5.2 compete/revenue caps (or a datalab commercial license on file) — or datalab re-releases the OCR-error checkpoint under Apache-2.0.
