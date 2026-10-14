# 05 - Web finding cards (vlm-pdf-qa)

Collected 2026-07-07 by 5 Composer-2.5 web foragers. Cards grouped by originating question.
Personas and meta-reviewers may cite these as evidence (URL anchor).

## Q1 - Which self-hosted open-weight VLMs are viable for document QA in 2026?

- **Qwen3-VL Technical Report** | https://arxiv.org/pdf/2511.21631 | HIGH
  Qwen3-VL-235B-A22B is the strongest open-weight generalist for document work: DocVQA 96.5%, OCRBench 920 (Instruct), MMLongBench-Doc 57.0% (SOTA among tested). Evaluation groups OCR parsing (CC-OCR, OmniDocBench, OCRBench_v2) plus document VQA and long-document reasoning. Improves over Qwen2.5-VL on OCRBench and long-doc scores at comparable or smaller deploy sizes.

- **InternVL3 (arXiv 2504.10479)** | https://arxiv.org/html/2504.10479v3 | HIGH
  InternVL3-78B: DocVQA 95.4%, OCRBench 906, ChartQA 89.7%. Beats Qwen2.5-VL-72B on OCRBench, trails on DocVQA. InternVL3-8B competitive for edge deploy (DocVQA 92.7%, OCRBench 880). Less OCR-specialist tuning, lower end-to-end PDF-parsing on OmniDocBench than Qwen3-VL.

- **olmOCR (Allen AI) - olmOCR-Bench leaderboard** | https://github.com/allenai/olmocr | HIGH
  7B open-weight VLM (Qwen-VL finetune, ~250k GPT-4o-labeled pages) built for PDF->Markdown conversion, not open-ended QA. olmOCR-Bench 82.4% overall (v0.4.0); strengths: tables (84.9), headers/footers (96.1), old scans/math. GPU ~12GB+. Better matched to "did we convert this page correctly?" than general VLMs.

- **ibm-granite/granite-docling-258M** | https://huggingface.co/ibm-granite/granite-docling-258M | HIGH
  Apache-2.0, 258M-param end-to-end conversion VLM (DocTags). Table TEDS 0.97/0.96, equation F1 0.968, full-page OCR F1 0.84; but OCRBench only 500, MMStar 0.30. Unsuitable as primary QA/reasoning model; pair with larger VLM for QA checks.

- **OmniDocBench leaderboard** | https://github.com/opendatalab/OmniDocBench | HIGH
  Standard 2026 end-to-end PDF parsing benchmark. Qwen3-VL-235B Overall 89.15; InternVL3-78B 80.33; InternVL3.5-241B 82.67; olmOCR-7B 81.79. Top open parsers are sub-4B OCR-focused specialists (PaddleOCR-VL, MinerU2.5) in the low-90s, but parsing-only.

## Q2 - olmOCR weights availability, license, base model, infra

- **allenai/olmOCR-2-7B-1025-FP8 (HF)** | https://huggingface.co/allenai/olmOCR-2-7B-1025-FP8 | HIGH
  Public FP8 weights for production self-hosting. Finetuned from Qwen2.5-VL-7B-Instruct on olmOCR-mix-1025 + GRPO RL (math, tables, hard OCR). Apache 2.0. Official path: olmOCR toolkit with vLLM inference.

- **allenai/olmOCR-2-7B-1025 (HF)** | https://huggingface.co/allenai/olmOCR-2-7B-1025 | HIGH
  Full BF16 release, same lineage. FP8 recommended for inference, BF16 for further fine-tuning. Usable via transformers (Qwen2_5_VLForConditionalGeneration) or the olmOCR pipeline.

- **allenai/olmocr GitHub README** | https://github.com/allenai/olmocr | HIGH
  Pipeline uses vLLM since v0.1.75; spawns `vllm serve` locally or accepts external OpenAI-compatible servers (`--server`). GPU >=12 GB VRAM (tested RTX 4090, L40S, A100, H100), ~30 GB disk. Example: `vllm serve allenai/olmOCR-2-7B-1025-FP8 --max-model-len 16384`.

- **olmocr Issue #424 (OOM on 12GB)** | https://github.com/allenai/olmocr/issues/424 | MED
  12 GB minimum is tight: RTX 4070 Super 12GB OOMs at defaults; 16GB can OOM at default max-model-len (128k). Workarounds: lower `--max-model-len` (<=32000), `--max-num-seqs=1`, tune `--gpu-memory-utilization`.

- **allenai/olmOCR-7B-0225-preview (HF)** | https://huggingface.co/allenai/olmOCR-7B-0225-preview | MED
  v1 preview finetuned from Qwen2-VL-7B; later v1 releases moved to Qwen2.5-VL-7B before olmOCR-2 added GRPO. Full lineage openly released, Apache 2.0.

## Q3 - Qwen-VL serving under vLLM (OpenAI-compatible API)

- **vLLM Multimodal Inputs docs** | https://docs.vllm.ai/en/latest/features/multimodal_inputs/ | HIGH
  `/v1/chat/completions` accepts images as `image_url` content parts: HTTP URLs, `data:image/jpeg;base64,...` data URIs, or `file://` (with `--allowed-local-media-path`). Multi-image = multiple content parts; raise cap with `--limit-mm-per-prompt.image N`. Chat template inserts placeholders automatically.

- **vLLM recipe Qwen/Qwen2.5-VL-7B-Instruct** | https://recipes.vllm.ai/Qwen/Qwen2.5-VL-7B-Instruct | HIGH
  Launch with `--mm-processor-kwargs '{"max_pixels":1003520}'` to bound per-image encoder cost, `--limit-mm-per-prompt '{"image":10,"video":0}'`. BF16, lower `--max-model-len` below native 128K to save KV memory.

- **vLLM Conserving Memory docs** | https://docs.vllm.ai/en/latest/configuration/conserving_memory/ | HIGH
  Pixel limits via `--mm-processor-kwargs` (Qwen2-VL default `1280*28*28`). `--limit-mm-per-prompt` supports count and profiling dims. Larger images = more visual tokens = OOM risk even when text fits.

- **QwenLM/Qwen3-VL Issue #1434** | https://github.com/QwenLM/Qwen3-VL/issues/1434 | HIGH
  PITFALL: per-request `min_pixels`/`max_pixels` on `image_url` parts have NO effect under vLLM (same prompt_tokens either way). Resolution must be set at server startup (`--mm-processor-kwargs`), in `preprocessor_config.json`, or by pre-resizing images client-side before sending.

- **Qwen3-VL Pixel Control guide** | https://qwenlm-qwen3-vl.mintlify.app/inference/pixel-control | HIGH
  Token math: Qwen3-VL 32x32 patches (Qwen2.5-VL 28x28); `min_pixels = N_tokens*32*32`. Recommended ~256-1280 visual tokens per image. For vLLM serving, control via server kwargs or client-side pre-resize, not per-request fields.

## Q4 - Measured VLM hallucination/error rates on document QA + mitigations

- **HQH: Quality of Hallucination Benchmarks for LVLMs** | https://arxiv.org/html/2406.17115v1 | HIGH
  GPT-4o lowest overall hallucination at 13.6%, still >10% failures. OCR is the HARDEST category: average OCR hallucination rate ~60% across models. More than half of evaluated models exceed 40% overall.

- **MTabVQA (EMNLP 2025 Findings)** | https://aclanthology.org/2025.findings-emnlp.1083 | HIGH
  Multi-hop QA over rendered table images: GPT-4.1 only 37.0% EM / 61.7% F1 zero-shot; open-source 2.1-11.8% EM. Targeted 7B fine-tune reaches 43.4% EM, beating proprietary zero-shot. Table reading from images is unreliable without task-specific tuning.

- **DocVQA 2026 Competition** | https://github.com/VLR-CVC/DocVQA2026 | HIGH
  Hard document reasoning: frontier models 22.5-37.5% overall under strict checks (GPT-5.2 37.5%). Layout-heavy pages (maps, posters) fall to 0-20%.

- **DocVAL (arXiv 2511.22521)** | https://arxiv.org/html/2511.22521v2 | HIGH
  Post-hoc rule-based grounding validator (answer + OCR-region presence + bbox geometry) filters hallucinated traces: +12.4 mAP from validator filtering alone. Quantifies the value of grounding VLM judgments in verifiable regions.

- **M3DocDep (CVPR 2026)** | https://openaccess.thecvf.com/content/CVPR2026/papers/Shin_M3DocDep_Multi-modal_Multi-page_Multi-document_Dependency_Chunking_with_Large_Vision-Language_Models_CVPR_2026_paper.pdf | MED
  LVLM-guided dependency-aware page/block chunking improves QA ANLS +4.5 to +15.3 points vs naive chunking. Page-level structural chunking is a measurable error reducer.

## Q5 - Prior art: VLM verifying PDF->markdown conversion fidelity

- **DOCR-Inspector (arXiv 2512.10619)** | https://arxiv.org/abs/2512.10619 | HIGH
  VLM-as-a-Judge that takes page/element images PLUS parsed output and detects parsing errors WITHOUT ground truth. Chain-of-Checklist reasoning, 28-type error taxonomy, DOCR-Inspector-7B finetuned on DOCRcase-200K. Closest academic match to our exact task.

- **RaV-IDP (arXiv 2604.23644)** | https://arxiv.org/pdf/2604.23644 | HIGH
  Reconstruction-as-Validation: render extracted entities back to visual form, score against original document crop. Low fidelity scores trigger a vision fallback + re-validation loop anchored to the source image.

- **coarse - extraction_qa.py** | https://github.com/Davidvandijcke/coarse/blob/dev/src/coarse/extraction_qa.py | HIGH
  Open-source post-extraction QA: renders sampled PDF pages to images, sends them WITH corresponding markdown chunks to a vision LLM; returns quality rating (good/acceptable/poor) + find-replace corrections. Direct implementation of page-image-vs-markdown verification.

- **Parser_evals - parser_evaluator_vision.py** | https://github.com/AmazingK2k3/Parser_evals | MED
  Renders PDF pages to images, has Claude judge markdown fidelity against the visuals. Separates fast text-only judging from slower image-grounded verification mode.

- **OCR Progress by End of 2025 (survey)** | https://www.linkedin.com/pulse/ocr-progress-end-2025-new-horizons-battle-details-igor-galitskiy-mkppe | MED
  Practitioner synthesis: VLM-judge error analysis (image vs parsed output, no ground truth) is becoming standard practice.
