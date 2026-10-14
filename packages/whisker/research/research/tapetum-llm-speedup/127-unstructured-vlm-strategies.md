# 127 - unstructured-VLM-Strategies

**Verdict:** usable-with-conditions — OSS `unstructured` ships a clean document-level cost router (pdfminer text probe → FAST / OCR_ONLY / HI_RES) with dependency fallbacks, but VLM invocation lives outside this repo (external partitioner + `unstructured_inference` table agent); no per-page strategy split.
**Confidence:** high

## Findings

- [CRITICAL] **Auto strategy is document-level, not per-page.** `_determine_pdf_auto_strategy` picks one strategy for the whole PDF: `infer_table_structure` or any image-block extraction flag → `hi_res`; else if `pdf_text_extractable` → `fast`; else → `ocr_only`. Evidence: `strategies.py:94-109`, `test_strategies.py:80-122`. Impact: mirrors tapetum's whole-paper serial cascade — a portable router must fingerprint/route per unit (page/check), not one predicate for 381 papers. Quality risk: low if ported correctly; mis-applying doc-level FAST to mixed born-digital/scanned PDFs would miss scan-only pages (~5-15% of WG21 corpus estimate).

- [CRITICAL] **Deterministic cheap probe before expensive path: pdfminer text-extractability.** Before routing, `partition_pdf_or_image` runs `extractable_elements` (pdfminer) and sets `pdf_text_extractable = any(Text with non-empty stripped text across all pages)`. Evidence: `pdf.py:302-325`, `test_strategies.py:44-59`. Impact: direct analog for tapetum — run deterministic diff/heuristic on candidate vs source BEFORE the 1536-token unit judge (~1057/1510 zero-defect checks in 00-baseline). Skipping judge when probe is clean could save ~700-1400 calls (~23-47 min at 20 s/call / 16 slots) with quality risk only on probe false-negatives.

- [HIGH] **Complexity heuristic bypasses the text probe entirely.** `is_pdf_too_complex` scans each page's raw content stream; if any page exceeds graphics-op count AND graphics-to-text ratio thresholds, text extraction is skipped (leaving `pdf_text_extractable=False`). Evidence: `pdf.py:304-308`, `pdf.py:618-738`. Impact: one bad page blocks FAST for the whole doc — same failure mode as whole-paper fingerprint skip in `cli.py:565+`. Per-page routing would recover wall on multi-mode docs. Quality risk: forcing OCR/hi_res on CAD-like pages avoids garbage pdfminer output (fail-closed).

- [HIGH] **HI_RES always invokes the layout model on every page; pdfminer merge is conditional.** In `_partition_pdf_or_image_local`, `process_file_with_model` / `process_data_with_model` always runs; `process_file_with_pdfminer` runs only `if pdf_text_extractable`. Evidence: `pdf.py:858-889`, `pdf.py:931-950`. Impact: even "hybrid" hi_res pays full OD-model cost — cost savings come from skipping pdfminer merge/OCR supplement, not from skipping vision. For tapetum: a cheap-first cascade must skip the expensive model entirely on confident units, not just skip auxiliary work. Quality risk: medium if cheap model misses layout-only defects.

- [HIGH] **Fallback chain is dependency-driven, not quality-driven.** Missing `unstructured_inference` → hi_res falls back to ocr_only (if tesseract) else fast; missing pytesseract on ocr_only → fast (if text extractable) else hi_res. Evidence: `strategies.py:48-82`. Impact: not a confidence-band cascade (cf. LLMTrace ADR in 05-web.md); no score threshold routes ambiguous cases to slow judge. Porting this literally would not cut the 70% zero-defect LLM calls. Quality risk: low (graceful degradation, not silent quality drop).

- [MED] **Feature flags force the expensive path regardless of text extractability.** `infer_table_structure`, `extract_images_in_pdf`, or non-empty `extract_image_block_types` all force `hi_res` under auto. Evidence: `strategies.py:37-46`, `strategies.py:103-104`, `auto.py:37-38` (PDFs default `skip_infer_table_types=["pdf",...]` so table inference off unless opted in). Impact: opt-in expensive features map to tapetum's `MAX_PAGE_ESCALATIONS`/`infer_table_structure`-like caps — only escalate when caller explicitly needs structure. Quality risk: disabling forced escalation preserves speed but drops table/layout defect classes.

- [MED] **Per-element (not per-page) OCR supplement inside hi_res.** `supplement_page_layout_with_ocr` in `individual_blocks` mode OCR-crops only elements with empty text; table extraction runs per detected Table bbox. Evidence: `ocr.py:241-259`, `ocr.py:266-286`, `ocr.py:311-318`. Impact: within an expensive page, work is scoped to empty regions — partial payload scoping analog for tapetum unit checks (stop sending full `candidate_md` when check scope is one page). Quality risk: low for text checks; table OCR adds latency only where tables detected.

- [LOW] **VLM is not part of OSS strategy routing.** References to "VLM partitioner" are HTML-output plumbing (`detection_origin="vlm_partitioner"`); `table_extraction_method` metadata accepts `"vlm"` but routing/strategy code never selects a VLM. Evidence: `html/transformations.py:70-71,117,159`, `elements.py:221`, `CHANGELOG.md:117`. Impact: no portable VLM routing predicates in this clone — hi_res uses OD models (YOLOX/Chipper via `unstructured_inference`, `default_hi_res_model()` at `pdf.py:115-122`). Quality risk: n/a for OSS port.

## False-pass hypothesis

Routing a born-digital WG21 paper to FAST because pdfminer finds extractable text, while embedded vector figures or rotated `/Rotate` pages lose content that hi_res+OCR would recover (`pdf.py:304-308` complexity bypass; hi_res rotation merge at `CHANGELOG.md:69`). A tapetum router using only "source PDF has text layer" would skip LLM checks and miss figure/table conversion defects on otherwise text-extractable papers.

## False-fail hypothesis

Forcing hi_res (full OD model on all pages) when auto would pick FAST on text-extractable PDFs — e.g. setting `infer_table_structure=True` globally. Every paper pays layout-model latency (~10-50x pdfminer per 00-baseline implied 20 s/call economics) with no gain on text-only defect classes; equivalent to running DeepSeek unit checks on all 1510 units instead of the 70% zero-defect subset.

## What would change my mind

Evidence that unstructured's SaaS VLM partitioner (not in this OSS clone) implements per-page strategy selection with measured cost/quality tradeoffs — e.g. API logs showing page N routed to VLM while page M used fast, with F1 within 1 pt of all-hi_res on a 381-paper WG21-like corpus.
