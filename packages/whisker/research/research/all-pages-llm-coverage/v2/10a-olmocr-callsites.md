# 10a - olmocr (packages/whisker/research/repos/olmocr)
**Claims tested:** C1, C2
**Exhaustive:** yes

## Method

Search commands run from repo root `packages/whisker/research/repos/olmocr`:

```bash
rg -i -n "openai|anthropic|claude|gemini|google\.genai|genai|litellm|vllm|ollama|chat\.completions|completions\.create|messages\.create|generate_content|GenerativeModel|transformers|AutoModel|\.generate\(|pipeline\(|predict\(|invoke\(|system_prompt|LLM|VLM|gpt-|llama|qwen" --glob "*.py"
rg -n "\.generate\(|\.chat\(|chat\.completions|completions\.parse|LLM\(|generate_content|messages\.create|AsyncOpenAI|OpenAI\(|client\.post|requests\.post|\.ocr\.|apost\(|llm\.chat|urlopen\(|outputs = model\(" --glob "*.py"
rg -n "call_claude|claude_stream" --glob "*.py"
```

Files read in full or in relevant sections: `olmocr/pipeline.py`, `olmocr/filter/coherency.py`, `olmocr/data/clean_olmocrmix.py`, `olmocr/synth/claude_client.py`, `olmocr/synth/mine_html_templates.py`, `olmocr/synth/augmentations.py`, `olmocr/train/train.py`, `olmocr/train/grpo_train.py`, `olmocr/train/compare_vllm_checkpoint.py`, all files under `olmocr/bench/runners/`, all LLM-bearing files under `olmocr/bench/miners/`, `olmocr/bench/scripts/run_difference.py`, `olmocr/bench/scripts/screen_pdfs.py`, `scripts/pii/*.py`, `scripts/qianfan_bench_convert.py`, `scripts/hf_local_test.py`, `olmocr/bench/convert.py`.

Excluded as non-invocations: test mocks (`tests/test_pipeline.py` mock `apost`), batch-submission-only scripts (`scripts/data/runopenaibatch.py`, `olmocr/data/runopenaibatch.py` upload JSONL, no inline completion), infini-gram count API (`scripts/infinigram_count.py`), docs/plots string references.

## Inventory

| # | File:line | Category | Calling function | Input | Output | Role |
|---|-----------|----------|------------------|-------|--------|------|
| 1 | `olmocr/pipeline.py:185` | production | `try_single_page` | Page PNG (base64) + OCR prompt (+ optional anchor text in query build) | YAML front matter + page markdown (`PageResponse`) | extraction |
| 2 | `olmocr/filter/coherency.py:50` | production | `get_document_coherency` | Existing text (tokenized chunks) | Per-token log-likelihood / coherency score | other (filter metric) |
| 3 | `olmocr/data/clean_olmocrmix.py:140` | data-pipeline | `clean_document_with_chatgpt` | Existing OCR markdown + page PNG | Structured cleaned markdown (`CleanedDocument`) | refinement |
| 4 | `olmocr/synth/claude_client.py:27` | synth | `call_claude` | Caller-supplied messages (often image + text) | Claude message response | other (shared wrapper) |
| 5 | `olmocr/synth/claude_client.py:47` | synth | `claude_stream` | Caller-supplied messages | Final streamed Claude message | other (shared wrapper) |
| 6 | `olmocr/synth/augmentations.py:21` | synth | `densify_html` | HTML string | Denser synthetic HTML | other (synth augmentation) |
| 7 | `olmocr/synth/mine_html_templates.py:392` | synth | `generate_html_from_image` | Page PNG | Orientation label | other (synth gate) |
| 8 | `olmocr/synth/mine_html_templates.py:437` | synth | `generate_html_from_image` | Page PNG | Layout analysis text | other (synth analysis) |
| 9 | `olmocr/synth/mine_html_templates.py:477` | synth | `generate_html_from_image` | Page PNG + analysis text | Initial HTML | extraction |
| 10 | `olmocr/synth/mine_html_templates.py:563` | synth | `generate_html_from_image` | Original PNG + rendered PNG + existing HTML | Revised HTML | refinement |
| 11 | `olmocr/train/train.py:237` | train | training loop (SFT) | Batched image+text tensors | Loss / gradients | other (training) |
| 12 | `olmocr/train/train.py:643` | train | eval loop (SFT) | Batched image+text tensors | Loss | other (training) |
| 13 | `olmocr/train/compare_vllm_checkpoint.py:155` | train/dev | `process_single_prompt` | Page image + prompt messages | Generated markdown text (vLLM) | other (checkpoint debug) |
| 14 | `olmocr/train/compare_vllm_checkpoint.py:188` | train/dev | `process_single_prompt` | Prompt+generated token IDs + image | HF logits / logprobs | other (checkpoint debug) |
| 15 | `olmocr/train/grpo_train.py:1571` | train | `main` | GRPO batch (image prompts via TRL) | Policy completions via vLLM (inside TRL) | other (RL training generation) |
| 16 | `olmocr/train/grpo_train.py:1574` | train | `main` | same | same | other (RL training generation) |
| 17 | `olmocr/bench/runners/run_chatgpt.py:86` | bench-runner | `run_chatgpt` | Page PNG + anchor text + prompt | Markdown / JSON OCR | eval-harness (baseline OCR) |
| 18 | `olmocr/bench/runners/run_claude.py:33` | bench-runner | `run_claude` | Page PNG + anchor text | Markdown OCR | eval-harness |
| 19 | `olmocr/bench/runners/run_gemini.py:111` | bench-runner | `run_gemini` | Page PNG + prompt | JSON OCR fields | eval-harness |
| 20 | `olmocr/bench/runners/run_gemini.py:143` | bench-runner | `run_gemini` | Page PNG + prompt (plain mode) | Markdown OCR | eval-harness |
| 21 | `olmocr/bench/runners/run_mistral.py:60` | bench-runner | `run_mistral` | PDF page (uploaded) | Markdown OCR | eval-harness |
| 22 | `olmocr/bench/runners/run_gotocr.py:62` | bench-runner | `run_gotocr` | Page PNG file path | Markdown OCR | eval-harness |
| 23 | `olmocr/bench/runners/run_nanonetsocr.py:77` | bench-runner | `run_nanonetsocr` | Page PNG + prompt | Markdown OCR | eval-harness |
| 24 | `olmocr/bench/runners/run_nanonetsocr_2.py:80` | bench-runner | `run_server` | Page PNG + prompt via HTTP | Markdown OCR | eval-harness |
| 25 | `olmocr/bench/runners/run_transformers.py:103` | bench-runner | `run_transformers` | Page PNG + prompt | Markdown/YAML OCR | eval-harness |
| 26 | `olmocr/bench/runners/run_server.py:85` | bench-runner | `run_server` | Page PNG + anchor/prompt via HTTP | Markdown OCR | eval-harness |
| 27 | `olmocr/bench/runners/run_rolmocr.py:48` | bench-runner | `run_rolmocr` | Page PNG via HTTP | Markdown OCR | eval-harness |
| 28 | `olmocr/bench/runners/run_dotsocr.py:123` | bench-runner | `_run_dotsocr_on_page` | Single-page PDF | Markdown OCR (via external `DotsOCRParser.parse_file`) | eval-harness |
| 29 | `olmocr/bench/runners/run_paddlevl.py:17` | bench-runner | `run_paddlevl` | PDF path | Markdown OCR (`PaddleOCRVL.predict`) | eval-harness |
| 30 | `olmocr/bench/scripts/run_difference.py:47` | bench-script | `run_difference` | Page PNG + **two existing OCR outputs** (ChatGPT + Gemini) | Difference / accuracy judgment | eval-harness (**C1-like verification**) |
| 31 | `olmocr/bench/scripts/screen_pdfs.py:54` | bench-script | `screen_pdf` | Page PNG + screening prompt | JSON flags (PII/resume/etc.) | other (dataset screening) |
| 32 | `olmocr/bench/miners/check_headers_footers.py:56` | bench-miner | `verify_header_footer_match` | Page PNG + **previously extracted header/footer text** | correct/incorrect JSON verdict | eval-harness (**C1-like verification**) |
| 33 | `olmocr/bench/miners/check_old_scans_math.py:59` | bench-miner | `verify_latex_match` | Page PNG + **previously extracted LaTeX string** | correct/incorrect JSON verdict | eval-harness (**C1-like verification**) |
| 34 | `olmocr/bench/miners/check_multicolumn.py:61` | bench-miner | `process_test_case` | Page PNG + before/after test strings | YES/NO same-region judgment | other (test-case QC, not full-page OCR fidelity) |
| 35 | `olmocr/bench/miners/mine_blank_pages_gpt.py:93` | bench-miner | `check_blank_page` | Page PNG + anchor text | Structured OCR JSON (null natural_text check) | other (corpus mining) |
| 36 | `olmocr/bench/miners/mine_diffs.py:52` | bench-miner | `clean_base_sentence` | Page PNG + candidate sentence from diff voting | Corrected sentence from image | other (ground-truth mining for tests; reads image, not judging full OCR output) |
| 37 | `olmocr/bench/miners/mine_footnotes_gpt.py:101` | bench-miner | `check_for_footnotes` | Page PNG | Footnote detection JSON | other (test mining) |
| 38 | `olmocr/bench/miners/mine_length_gpt_simple.py:127` | bench-miner | `analyze_document_structure` | Page PNG | Element/word-count structure JSON | other (test mining) |
| 39 | `olmocr/bench/miners/mine_multilingual_gpt.py:93` | bench-miner | `check_for_table` (language detect) | Page PNG | Language code JSON | other (corpus mining) |
| 40 | `olmocr/bench/miners/mine_headers_footers.py:166` | bench-miner | `detect_headers_footers` | Page PNG | Header/footer list JSON | other (test mining) |
| 41 | `olmocr/bench/miners/mine_long_tiny_text.py:129` | bench-miner | `detect_long_text` | Page PNG | Long-text/equation list JSON | other (test mining) |
| 42 | `olmocr/bench/miners/mine_multi_column.py:61` | bench-miner | `generate_html_from_image` | Page PNG | Layout analysis text | other (synth HTML mining) |
| 43 | `olmocr/bench/miners/mine_multi_column.py:87` | bench-miner | `generate_html_from_image` | Page PNG + analysis | HTML page | extraction (synth) |
| 44 | `olmocr/bench/miners/mine_old_scans_math.py:128` | bench-miner | `detect_equations` | Page PNG | Equation string list JSON | other (test mining) |
| 45 | `olmocr/bench/miners/mine_reading_order.py:198` | bench-miner | `analyze_document_layout` | Page PNG | Layout metadata JSON | other (test mining) |
| 46 | `olmocr/bench/miners/mine_reading_order.py:270` | bench-miner | `extract_document_content` | Page PNG | Full-page markdown | extraction (gold reference mining) |
| 47 | `olmocr/bench/miners/mine_tables_gemini.py:163` | bench-miner | `detect_tables` | Page PNG | Table detection / page markdown | extraction (test mining) |
| 48 | `olmocr/bench/miners/mine_tables_gemini.py:281` | bench-miner | `generate_table_tests` | Page PNG + table cell value + relationship prompt | Neighbor cell text for test JSON | other (creates table relationship tests from source) |
| 49 | `olmocr/bench/miners/mine_tables_gpt.py:131` | bench-miner | `detect_tables` | Page PNG | Page markdown with HTML tables | extraction (test mining) |
| 50 | `olmocr/bench/miners/mine_tables_gpt.py:267` | bench-miner | `generate_table_tests` | Page PNG + cell + relationship prompt | Neighbor cell text | other (creates table relationship tests) |
| 51 | `olmocr/bench/miners/mine_tables_gpt_simple.py:121` | bench-miner | `check_for_table` | Page PNG | Table presence/size JSON | other (test mining) |
| 52 | `scripts/hf_local_test.py:49` | script/dev | `main` | Page image + prompt | Generated OCR text | other (local HF smoke test) |
| 53 | `scripts/qianfan_bench_convert.py:152` | script/bench | `call_vllm` | Page PNG via HTTP POST | Markdown OCR | eval-harness |
| 54 | `scripts/pii/tagging_pipeline.py:121` | script/pii | `_process_single_page` | Page text only | PII/document-type JSON via local vLLM | other (PII tagging) |
| 55 | `scripts/pii/rich_tagging_pipeline.py:195` | script/pii | `_process_single_page` | Page text only | Rich PII JSON via local vLLM | other (PII tagging) |
| 56 | `scripts/pii/chatgpt_tag_dolmadocs_v1.py:370` | script/pii | `chatgpt_analyze_page` | Page PNG | PII annotation JSON | other (PII tagging) |
| 57 | `scripts/pii/chatgpt_tag_dolmadocs_v2.py:338` | script/pii | `chatgpt_analyze_page` | Page PNG | PII annotation JSON | other (PII tagging) |
| 58 | `scripts/pii/autoscan_dolmadocs.py:287` | script/pii | `chatgpt_analyze_page` | Page PNG | PII annotation JSON | other (PII tagging) |

**Bench scoring note:** `olmocr/bench/convert.py` and test execution use deterministic string matchers (`TextPresenceTest`, etc.); no LLM invocation in the scorer itself. GRPO reward functions in `olmocr/train/grpo_train.py` compare completions to mined test IDs deterministically, not via an LLM judge.

**Miner classification summary:** Bench miners predominantly **extract** ground-truth snippets or page-level markdown from source images to **create** olmOCR-bench tests. They do not judge an external pipeline's already-produced conversion output, except the dedicated `check_*` validators and `run_difference.py`.

## Verdict on the claim(s)

### C1 (negative existential: no repo judges already-produced conversion output against source per page/unit)

**REFUTED** for olmocr.

Production OCR path (`olmocr/pipeline.py:185`) is extraction-only: page image in, markdown out. No production path sends prior conversion output back to a model for fidelity judging.

However, multiple non-production sites **do** send already-produced text plus source to a model to judge fidelity or correctness per page:

| File:line | What is judged |
|-----------|----------------|
| `olmocr/bench/scripts/run_difference.py:47` | ChatGPT + Gemini OCR outputs vs page image; model picks differences and which is more accurate |
| `olmocr/bench/miners/check_headers_footers.py:56` | Miner-extracted header/footer strings vs page image |
| `olmocr/bench/miners/check_old_scans_math.py:59` | Miner-extracted LaTeX vs page image |

Related but **not** C1 (refinement, not verification): `olmocr/data/clean_olmocrmix.py:140` (existing OCR md + image → cleaned md), `olmocr/synth/mine_html_templates.py:563` (own HTML + rendered image → revised HTML).

### C2 (classify every invocation site)

**CONFIRMED.** All 58 sites above are classified in the Inventory table.

## Coverage gaps

None for Python source in this clone. Indirect invocations not enumerated as separate sites: (a) vLLM generation inside HuggingFace TRL during `trainer.train()` (`grpo_train.py:1571/1574`); (b) model inference inside external `dots.ocr` package called from `run_dotsocr.py:123`; (c) shell scripts that spawn `vllm serve` without Python completion calls.

## What could still hide a counterexample

- LLM calls added only in unpinned commits after the baseline SHA.
- Dynamic `eval`/`importlib` paths not matching search patterns.
- Jupyter notebooks or non-`.py` entry points not scanned (none found in repo layout).
- Additional C1-like paths in the external `dots.ocr` submodule checkout (not present in this workspace).
