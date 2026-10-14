# 23 - Dolphin-analyst

**Verdict:** usable-with-conditions — Dolphin's two-stage analyze-then-parse architecture and element-type prompt routing are a strong structural reference for a VLM inventory lane, but the shipped code is a conversion pipeline (not QA), emits free-text layout strings instead of schema-bound inventories, and depends on finetuned Dolphin weights rather than a generic judge prompt.
**Confidence:** high

## Findings
- [HIGH] Stage 1 uses a single fixed layout prompt on the full page image: `"Parse the reading order of this document."` — `demo_page.py:186`, `demo_layout.py:173`. The model returns a free-text bracket-delimited string (not JSON/Pydantic), parsed by regex into `(bbox, label, tags)` tuples via `parse_layout_string()` — `utils/utils.py:172-201`. Example labels in the parser test fixture: `sec_0`, `para`, `tab`, `equ`, `fnote`, `watermark` — `utils/utils.py:536-537`.
  Impact: The prompt wording and output shape are directly reusable as a Stage-1 "page inventory" idea, but our lane must wrap this in structured output (D6) because the raw string is fragile and requires regex recovery on failure.

- [HIGH] Stage 2 routes cropped elements to four heterogeneous anchor prompts by label: `tab` → `"Parse the table in the image."`, `equ` → `"Read formula in the image."`, `code` → `"Read code in the image."`, all other labels → `"Read text in the image."`; `fig` skips VLM and saves the crop as PNG — `demo_page.py:231-282`, `demo_element.py:138-149`. Batches share one prompt per type (`max_batch_size` default 4) — `demo_page.py:289-320`, `demo_page.py:336-337`.
  Impact: Element-type-specific prompts are portable pattern for a two-stage QA lane (inventory types in Stage 1, type-aware content checks in Stage 2), but Dolphin's Stage-2 prompts ask for extraction, not "does markdown contain X?" verification.

- [HIGH] PDF rasterization uses PyMuPDF with longest-side scaling to 896 px (`target_size=896`), then `resize_img()` caps longest side at 1600 px before inference; coordinate remap uses `smart_resize(factor=28, min_pixels=784, max_pixels=2560000)` — `utils/utils.py:55-92`, `utils/utils.py:434-458`, `utils/utils.py:204-222`, `demo_page.py:59`. Aligns with our stack already shipping PyMuPDF — `00-baseline.md:74-84`.
  Impact: Dolphin validates PyMuPDF as the reuse-first rasterizer for our lane; 896 px page + 1600 px model cap is a concrete DPI/resolution baseline, though lower than olmocr's 1288–2048 px longest dim — `00-baseline.md:14-15`.

- [MED] Assembly merges figure paths + batched element texts, sorts by `reading_order`, and writes JSON + markdown; validation is limited to layout-string bracket check, bbox-overlap fallback to `distorted_page` holistic mode (>25% overlapping boxes), and per-element try/except — `demo_page.py:204-209`, `demo_page.py:266-286`, `utils/utils.py:489-533`, `utils/markdown_utils.py:308-354`. No cross-check against an external markdown ground truth.
  Impact: Overlap fallback and parse-failure degradation are worth porting as robustness guards, but there is zero conversion-fidelity QA logic — confirms baseline classification as CONVERSION not judge — `00-baseline.md:32-35`.

- [MED] Model stack: `Qwen2_5_VLForConditionalGeneration` + `AutoProcessor` + `qwen_vl_utils.process_vision_info`, BF16 on CUDA, `do_sample=False`, `max_new_tokens=4096` — `demo_page.py:12-27`, `demo_page.py:103-108`. Weights target `ByteDance/Dolphin-v2` (3B, MIT license per README) — `README.md:9`, `README.md:48`, `README.md:96-97`. README claims vLLM deployment exists upstream but `deployment/vllm/` is absent from our vendored clone — `README.md:52`.
  Impact: Self-hostable on Qwen2.5-VL infrastructure; vLLM path is plausible per upstream docs and `05-web.md` Q3 (OpenAI `image_url` base64), but our clone only demonstrates HuggingFace direct inference — integration would need a new vision backend class — `00-baseline.md:73`.

- [MED] For our proposed two-stage QA (Stage 1: VLM inventories page; Stage 2: deterministic markdown cross-check), Dolphin's Stage-1 output is the closest in-repo analogue: ordered list of `{label, bbox, tags, reading_order}` before content extraction — `demo_page.py:218-248`, `demo_layout.py:183-191`. However, prompts optimize for parsing not auditing; academic closer matches are DOCR-Inspector and coarse `extraction_qa.py` (image + parsed output judge) — `05-web.md` Q5.
  Impact: Borrow the architectural split and label taxonomy, not the prompts verbatim; Stage 2 for us should be deterministic (whisker det + markdown grep/structure), not Dolphin's second VLM extraction pass.

- [LOW] Determinism: `do_sample=False` and `temperature=None` in `demo_page.py` — `demo_page.py:106-107`; `demo_element.py` omits these flags — `demo_element.py:100-104`. Stage 2 runs batched element crops in parallel groups (tables, then formulas, then code, then text) — `demo_page.py:268-282`, which is serial across types but parallel within type; conflicts with our D11 serial dissect default unless we cap concurrency at 1 — `00-baseline.md:76`.

## False-pass hypothesis
Dolphin Stage 1 returns plausible bracket-layout strings even when labels are wrong (e.g., a table bbox labeled `para`), and Stage 2 `"Read text in the image."` would transcribe table cells as plain text without raising an error — `demo_page.py:280-281`. A QA lane that reused Dolphin's layout output as ground-truth inventory without structured validation would false-pass a markdown conversion that dropped or mis-typed the table structure.

## False-fail hypothesis
High bbox-overlap fallback forces `distorted_page` holistic mode when >25% of boxes overlap — `utils/utils.py:489-531`, causing Stage 2 to run `"Read text in the image."` on the full page instead of per-element checks — `demo_page.py:221-223`. For our QA lane, a photographed or dense WG21 page with legitimate column overlap could collapse to a single full-page inventory entry and false-fail granular markdown checks that are correct at element level.

## What would change my mind
A Dolphin-v2 checkpoint run (via upstream vLLM deployment) on 10+ WG21 paper pages showing Stage-1 layout inventories that match human element counts/types with >95% precision when compared against our tomd markdown structure — demonstrating the finetuned layout prompt generalizes to C++ committee papers without retraining.
