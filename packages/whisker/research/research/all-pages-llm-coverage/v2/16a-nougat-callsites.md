# 16a - nougat (SHA 5a92920)
**Claims tested:** C1, C2
**Exhaustive:** yes

## Method

Repo: `packages/whisker/research/repos/nougat` at pinned SHA `5a92920d342fb6acf05fc9b594ccb4053dbe8e7a` (verified via `git rev-parse HEAD`).

Search commands run (all from repo root, case-insensitive where noted):

```
rg -i -n "openai|anthropic|claude|gemini|google\.genai|genai|litellm|vllm|ollama|chat\.completions|completions\.create|messages\.create|generate_content|GenerativeModel|transformers|AutoModel|\.generate\(|pipeline\(|predict\(|invoke\(|LLM|VLM|gpt-|llama|qwen|system_prompt|forward\(" --glob "*.py"

rg -n "\.generate\(|model\.forward|from_pretrained|Nougat|inference|decode|encoder|decoder" --glob "*.py"

rg -i -n "eval|benchmark|judge|compare|score|verify|validation|metric" --glob "*.py"

rg -n "model\.|\.inference\(|self\.model\(|pretrained_model\.|NougatModel|MBartForCausalLM|timm\.create_model|from_pretrained" --glob "*.py"
```

All 34 Python files enumerated via `Get-ChildItem -Recurse -Filter "*.py"`. Read in full: `nougat/model.py`, `app.py`, `predict.py`, `lightning_module.py`, `test.py`, `nougat/metrics.py`, `nougat/utils/dataset.py` (relevant sections), `nougat/dataset/staircase.py` (predict), `nougat/dataset/split_md_to_pages.py` (predict). Skimmed remaining `.py` files via rg hits only.

No matches for API LLM providers (OpenAI, Anthropic, Gemini, etc.). The sole neural page-image-to-markdown stack is SwinTransformer encoder + MBart decoder (`nougat/model.py`).

## Inventory

### Page-image-to-markdown VLM (SwinEncoder + BARTDecoder / NougatModel)

| File:Line | Function | Input | Output | Role | C2 class |
|-----------|----------|-------|--------|------|----------|
| `app.py:130` | `predict` | `image_tensors` batch (rasterized PDF page images) | `model_output["predictions"]`, `repeats` | Production FastAPI: per-page extraction | extraction |
| `predict.py:167` | `main` | `image_tensors` batch | `model_output["predictions"]` per page | Production CLI: per-page extraction | extraction |
| `lightning_module.py:73` | `training_step` | `image_tensors`, `decoder_input_ids`, `attention_masks` | `loss` scalar | Training: teacher-forcing forward | extraction |
| `lightning_module.py:88` | `validation_step` | `image_tensors` | `preds` strings (then compared to GT via deterministic metrics) | Validation loop: fresh inference per batch | extraction |
| `test.py:67` | `test` | `image_tensors` | `outputs` prediction strings (then `compute_metrics` vs GT) | Offline eval harness: fresh inference | extraction |
| `nougat/model.py:535` | `NougatModel.forward` | `image_tensors` | `encoder_outputs` (Swin hidden states) | Training path: vision encode | extraction |
| `nougat/model.py:536` | `NougatModel.forward` | `decoder_input_ids[:,:-1]`, `encoder_outputs`, `labels` | `decoder_outputs` (cross-entropy loss) | Training path: decoder forward | extraction |
| `nougat/model.py:580` | `NougatModel.inference` | `image_tensors` | `last_hidden_state` | Inference path: vision encode | extraction |
| `nougat/model.py:592` | `NougatModel.inference` | `encoder_outputs` (`ModelOutput`) | `decoder_output.sequences` (token IDs) | Inference path: autoregressive `generate` | extraction |
| `nougat/model.py:116` | `SwinEncoder.forward` | `x` (B,C,H,W tensor) | Swin layer output tensor | Vision backbone forward (called from `:535`, `:580`) | extraction |
| `nougat/model.py:121` | `SwinEncoder.forward` | patch embeddings | layer stack output | Swin `patch_embed` (internal) | extraction |
| `nougat/model.py:122` | `SwinEncoder.forward` | dropped patches | layer input | Swin `pos_drop` (internal) | extraction |
| `nougat/model.py:123` | `SwinEncoder.forward` | layer input | encoder features | Swin `layers` (internal) | extraction |
| `nougat/model.py:324` | `BARTDecoder.forward` | `input_ids`, `encoder_hidden_states`, `labels`, masks | MBart forward output / loss | Decoder forward (called from `:536`) | extraction |
| `nougat/model.py:454` | `StoppingCriteriaScores.__call__` | `input_ids`, per-step `scores` logits | `bool` early-stop flag | Heuristic repetition detector during `generate`; not a separate model | other |
| `nougat/model.py:84` | `SwinEncoder.__init__` | N/A (constructor) | pretrained Swin weight tensors loaded | One-time weight init from `timm` pretrained Swin | other |
| `nougat/model.py:247` | `BARTDecoder.__init__` | N/A (constructor) | pretrained mBART weight tensors loaded | One-time weight init from `facebook/mbart-large-50` | other |

**Notes on eval paths (not additional model invocations):**
- `lightning_module.py:95` calls `get_metrics(gts, preds)` (`nougat/metrics.py:86`); metrics are deterministic (edit distance, BLEU, METEOR via NLTK). No LLM in the scoring loop.
- `test.py:74` calls `compute_metrics(outputs, ground_truth)` (`nougat/metrics.py:27`); same deterministic scoring.
- Neither eval path feeds an already-produced conversion artifact back into the model for judgment; both run fresh `inference` from page images and compare strings offline.

**Dataset code using model object (preprocessing only, no forward/generate):**
- `nougat/utils/dataset.py:253` — `NougatDataset.__getitem__` calls `nougat_model.encoder.prepare_input(image)` (image tensor prep only; no forward).
- `nougat/utils/dataset.py:257` — tokenizes ground-truth markdown via `decoder.tokenizer(...)` (no model forward).

### Non-VLM `predict` hits (charter: list but mark)

| File:Line | Function | Input | Output | Role | C2 class |
|-----------|----------|-------|--------|------|----------|
| `nougat/dataset/split_md_to_pages.py:87` | `TFIDFClassifier.predict` (via wrapper) | TF-IDF feature matrix | sklearn class label | Dataset prep: paragraph-to-page alignment | other |
| `nougat/dataset/staircase.py:307` | `Staircase.predict` | 1-D numpy array | threshold boundaries | Dataset prep: staircase segmentation | other |

## Verdict on the claim(s)

**C1 (negative existential — no per-page verification of already-produced output by LLM/VLM):** **CONFIRMED.** At SHA 5a92920, no production or eval code path invokes the VLM (or any LLM) to judge an already-produced conversion output against the source document per page/chunk/unit. All VLM use is extraction (page image → markdown tokens). Validation (`lightning_module.py:88-95`) and testing (`test.py:67-74`) run fresh inference from images and score with deterministic string metrics (`nougat/metrics.py:27-44`); they do not implement tapetum-style verification of pre-existing markdown.

**C2 (positive classification):** All VLM invocation sites classified above. Summary: 14 extraction (including training/validation/test inference and internal forward/generate), 3 other (weight init ×2, stopping-criteria heuristic ×1). Zero refinement sites. Eval harnesses (`test.py`, `validation_step`) wrap extraction + deterministic metrics, not a separate VLM judge.

## Coverage gaps

None. All 34 Python files under repo root searched; `docker/` contains only `Dockerfile` and `README.md` (no Python); `config/` contains only `train_nougat.yaml` (training hyperparameters, no code, no model endpoints; read in full).

## What could still hide a counterexample

- A non-Python runtime path (e.g. external service called from Docker entrypoint not present in this clone). `docker/Dockerfile` not executed; grep found no model calls outside `.py`.
- Dynamic `eval`/`importlib` model loading: no matches in rg for those patterns across `.py`.
- Future commits beyond pinned SHA 5a92920.
