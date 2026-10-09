# 12a - langextract (SHA 0dff547)
**Claims tested:** C1, C2
**Exhaustive:** yes

## Method

Repo: `packages/whisker/research/repos/langextract` at detached HEAD `0dff547` (matches `00-baseline.md` pin).

Search commands (run from repo root; `--glob "!uv.lock" --glob "!.venv/**"` on all):

```
rg -i -n "openai|anthropic|claude|gemini|google\.genai|litellm|vllm|ollama|chat\.completions|completions\.create|messages\.create|generate_content|GenerativeModel|transformers|AutoModel|system_prompt|gpt-|llama|qwen"
rg -n "\bLLM\b|\bVLM\b"
rg -n "genai|vertex|bedrock|mistral|cohere|huggingface|hf_hub"
rg -n "\.infer\(|generate_content|chat\.completions\.create|_post_ollama_json\(|infer_batch\(|batches\.create\(" --glob "*.py"
rg -n "lx\.extract\(|langextract\.extract\(" --glob "*.py"
rg -n "def align|def resolve|class WordAligner" langextract/resolver.py
```

Files read in full or in focused sections: `langextract/annotation.py`, `langextract/extraction.py`, `langextract/prompting.py`, `langextract/prompt_validation.py`, `langextract/resolver.py` (lines 1–400, 539–950), `langextract/core/base_model.py`, `langextract/providers/gemini.py`, `langextract/providers/openai.py`, `langextract/providers/ollama.py`, `langextract/providers/gemini_batch.py`, `langextract/providers/openai_batch.py`, `benchmarks/benchmark.py`, `benchmarks/fuzzy_benchmark.py`, `langextract/inference.py`.

## Alignment / resolver: LLM or deterministic?

**No LLM.** The resolver parses model output and aligns extraction spans to source text with deterministic string/token matching.

After each `infer()` call, `annotation.py` passes raw model text through `resolver.resolve()` then `resolver.align()` — no second model call:

```404:428:packages/whisker/research/repos/langextract/langextract/annotation.py
          resolved_extractions = resolver.resolve(
              scored_outputs[0].output,
              ...
          )
          ...
          aligned_extractions = resolver.align(
              resolved_extractions,
              text_chunk.chunk_text,
              token_offset,
              char_offset,
              tokenizer_inst=tokenizer,
              **kwargs,
          )
```

- **`resolve()`** (`resolver.py:276–325`): parses JSON/YAML via `format_handler.parse_output()`; no model import or call.
- **`align()`** (`resolver.py:327–398`): instantiates `WordAligner` and calls `align_extractions()` on `source_text` and parsed extraction strings.
- **`WordAligner.align_extractions()`** (`resolver.py:789+`): tokenizes source and extraction text, runs exact DP matching (`_apply_monotonic_exact_matches`) and optional fuzzy LCS fallback (`difflib`/LCS thresholds at `resolver.py:57–72`); uses `_tokenize_with_lowercase`, `bisect`, `difflib` — no provider imports.

`prompt_validation.validate_prompt_alignment()` (`prompt_validation.py:130–168`) runs the same deterministic `WordAligner` against few-shot example text before extraction; no LLM.

`benchmarks/fuzzy_benchmark.py` benchmarks alignment latency only; no LLM.

## Verification loop: prior output back to model?

**No production or test path verified** that sends already-produced extraction/conversion output back to an LLM to judge it against the source document.

Checked paths:

| Path | Finding | Citation |
|---|---|---|
| `extraction_passes > 1` | Re-runs extraction on the same source chunks; merges non-overlapping results locally. Does not inject prior pass extractions into prompts. | `annotation.py:447–528` |
| `ContextAwarePromptBuilder` | Injects trailing **source** text from the previous chunk (`[Previous text]: ...`), not prior model extractions. | `prompting.py:179–276` |
| `additional_context` | User-supplied document context string; not model output. | `prompting.py:128–129`, `annotation.py:370–374` |
| `resolver` / `prompt_validation` | Post-processing only; no `infer()` call. | `resolver.py`, `prompt_validation.py` |
| `rg` for verify/judge/review/refine | No matches tying prior output to a second LLM call in production code. | NOT VERIFIED beyond targeted reads above |

## Inventory

Role key (C2): **extraction** = model produces structured extractions from source text; **eval-harness** = offline benchmark scoring extraction runs; **test** = unit/integration mock or live API; **example** = demo/sample script.

### A. Production pipeline (21 sites)

| # | file:line | function | input | output | role |
|---|---|---|---|---|---|
| 1 | `langextract/annotation.py:392` | `Annotator._annotate_documents_single_pass` | Prompts built from chunk source text + few-shot template + optional `additional_context` / prior-chunk **source** tail | `ScoredOutput` list (raw model text per chunk) | extraction |
| 2 | `langextract/core/base_model.py:201` | `BaseLanguageModel.infer_batch` | `prompts` sequence | Delegates to `infer()` | extraction |
| 3 | `langextract/providers/gemini.py:368` | `GeminiLanguageModel._process_single_prompt` | Single prompt string + gen config | `response.text` via `generate_content` | extraction |
| 4 | `langextract/providers/gemini.py:443` | `GeminiLanguageModel.infer` (batch branch) | `batch_prompts` | Batch API texts | extraction |
| 5 | `langextract/providers/gemini.py:481` | `GeminiLanguageModel.infer` (parallel branch) | Per-prompt via `ThreadPoolExecutor` → `_process_single_prompt` | Same as #3 | extraction |
| 6 | `langextract/providers/gemini.py:508` | `GeminiLanguageModel.infer` (sequential branch) | Per-prompt → `_process_single_prompt` | Same as #3 | extraction |
| 7 | `langextract/providers/gemini_batch.py:387` | `_submit_batch_job` | GCS prompt file | Vertex `client.batches.create` job | extraction |
| 8 | `langextract/providers/gemini_batch.py:707` | `infer_batch` | Prompt list + schema/gen config | List of output strings | extraction |
| 9 | `langextract/providers/openai.py:250` | `OpenAILanguageModel._process_single_prompt` | Chat messages built from prompt | `choices[0].message.content` | extraction |
| 10 | `langextract/providers/openai.py:280` | `OpenAILanguageModel.infer_batch` | `prompts` | Materialized `infer()` results | extraction |
| 11 | `langextract/providers/openai.py:325` | `OpenAILanguageModel.infer` (batch branch) | `batch_prompts` | Batch API texts | extraction |
| 12 | `langextract/providers/openai.py:360` | `OpenAILanguageModel.infer` (parallel branch) | Per-prompt → `_process_single_prompt` | Same as #9 | extraction |
| 13 | `langextract/providers/openai.py:388` | `OpenAILanguageModel.infer` (sequential branch) | Per-prompt → `_process_single_prompt` | Same as #9 | extraction |
| 14 | `langextract/providers/openai_batch.py:347` | `infer_batch` | Prompts + request builder | Output string list | extraction |
| 15 | `langextract/providers/openai_batch.py:442` | `infer_batch` (upload) | JSONL batch input | `client.files.create` | extraction |
| 16 | `langextract/providers/openai_batch.py:466` | `infer_batch` (submit) | Batch file id | `client.batches.create` | extraction |
| 17 | `langextract/providers/ollama.py:294` | `OllamaLanguageModel.infer` | Prompt (GPT-OSS chat path) | Chat response text | extraction |
| 18 | `langextract/providers/ollama.py:302` | `OllamaLanguageModel.infer` | Prompt (generate path) | Generate response text | extraction |
| 19 | `langextract/providers/ollama.py:447` | `OllamaLanguageModel._post_ollama_json` | HTTP payload | Ollama JSON | extraction |
| 20 | `langextract/providers/ollama.py:536` | `OllamaLanguageModel._ollama_gpt_oss_chat_query` | Prompt → `_post_ollama_json` at `/api/chat` | Chat JSON | extraction |
| 21 | `langextract/providers/ollama.py:653` | `OllamaLanguageModel._ollama_query` | Prompt → `_post_ollama_json` at `/api/generate` | Generate JSON | extraction |

### B. Examples and benchmarks (10 sites)

| # | file:line | function | input | output | role |
|---|---|---|---|---|---|
| 22 | `benchmarks/benchmark.py:199` | `BenchmarkSuite.test_single_extraction` | Source test text via `langextract.extract()` | AnnotatedDocument; benchmark counts grounded entities | eval-harness |
| 23 | `examples/ollama/demo_ollama.py:159` | module | Ollama demo text | extractions | example / extraction |
| 24 | `examples/ollama/demo_ollama.py:215` | module | Ollama demo text | extractions | example / extraction |
| 25 | `examples/ollama/demo_ollama.py:301` | module | Ollama demo text | extractions | example / extraction |
| 26 | `examples/ollama/demo_ollama.py:393` | module | Ollama demo text | extractions | example / extraction |
| 27 | `skills/langextract-usage/examples/basic_extraction.py:40` | module | sample text | extractions | example / extraction |
| 28 | `skills/langextract-usage/examples/multiple_documents.py:47` | module | document list | extractions | example / extraction |
| 29 | `skills/langextract-usage/examples/relationship_extraction.py:53` | module | sample text | extractions | example / extraction |
| 30 | `examples/custom_provider_plugin/test_example_provider.py:49` | module | test prompts | `model.infer` output | example / extraction |
| 31 | `examples/custom_provider_plugin/langextract_provider_example/provider.py:175` | `ExampleLanguageModel.infer` | prompt | `generate_content` text | example / extraction |

### C. Scripts (1 site)

| # | file:line | function | input | output | role |
|---|---|---|---|---|---|
| 32 | `scripts/create_provider_plugin.py:387` | plugin scaffold test | sample prompts | `provider.infer` | other (codegen smoke test) |

### D. Tests — `lx.extract()` entry points (73 sites, mocked except live/Ollama integration)

All funnel to production site #1 when not mocked. Role: **test** (mocked orchestration) unless noted.

`tests/extract_schema_integration_test.py`: 66, 99, 135, 169, 218, 263, 298, 340, 370, 388, 400, 412, 427, 457, 468, 480, 492, 502, 512, 526, 536

`tests/extract_precedence_test.py`: 58, 93, 130, 169, 198, 239, 265, 353, 384, 415, 445, 474, 504, 537, 571, 581

`tests/init_test.py`: 140, 187, 233, 295, 335, 374, 412, 446, 504, 571, 686, 736, 779, 930

`tests/provider_plugin_test.py`: 463

`tests/provider_schema_test.py`: 228, 283

`tests/test_live_api.py` (**live API, real LLM**): 393, 473, 545, 648, 744, 758, 819, 895, 930, 1016, 1116, 1175, 1234, 1249

`tests/test_ollama_integration.py` (**live Ollama, real LLM**): 77, 120, 158, 211, 259

### E. Tests — direct `.infer()` / provider API mocks (174 sites)

Complete `rg` enumeration (`\.infer\(|generate_content|chat\.completions\.create|_post_ollama_json\(|infer_batch\(|batches\.create\(`), excluding the 21 production rows in section A:

**`tests/annotation_test.py`**: 85, 202, 211, 321, 330, 465, 470, 556, 571, 590, 697, 711, 714, 745, 772, 775, 784, 809, 810, 813, 821, 865, 872, 922, 946, 952, 1128, 1129, 1132, 1153, 1156, 1212, 1213, 1216, 1227, 1260, 1276, 1299, 1320, 1339 — mock `GeminiLanguageModel.infer`; role **test**.

**`tests/factory_test.py`**: 43, 46–47, 61, 64–65, 205, 208–209, 226, 229–230, 272, 275–276, 294, 297–298, 319, 322–323, 370, 408 — fake provider `infer`/`infer_batch`; **test**.

**`tests/factory_schema_test.py`**: 151, 257 — fake `infer`; **test**.

**`tests/extract_schema_integration_test.py`**: 57, 90, 123, 157, 197, 209, 238, 289, 328, 339, 369, 399, 411, 426, 535 — patched `GeminiLanguageModel.infer` / `OllamaLanguageModel.infer`; **test**.

**`tests/gemini_retry_test.py`**: 199, 207, 213, 222, 229, 249, 269, 277, 286, 291, 295, 302, 320, 322, 331, 335, 348, 351 — mock `generate_content`; **test**.

**`tests/inference_test.py`**: 148, 189, 227, 247, 262, 289, 336, 365, 419, 454, 478, 508, 533, 580, 601, 627–630, 649, 658, 666, 785, 795, 798–799, 856, 865, 867, 882, 890–891, 905, 911, 913–914, 929, 933, 935–936, 951, 959, 961, 974, 981, 983, 997, 1004, 1006, 1023, 1030, 1032, 1044, 1051, 1053 — provider unit tests; **test**.

**`tests/openai_batch_test.py`**: 165, 205, 263, 276, 298, 310, 339, 352, 365, 399, 431, 461, 488, 519, 558, 597, 636, 668, 700, 726, 757, 769–770 — `openai_batch.infer_batch` / mock `batches.create`; **test**.

**`tests/provider_schema_test.py`**: 164, 189, 324, 527, 546, 569, 645, 652, 666, 670, 672 — mock `generate_content` / `chat.completions.create`; **test**.

**`tests/provider_plugin_test.py`**: 115, 615, 638 — plugin `infer`; **test**.

**`tests/registry_test.py`**: 41–42, 51–52 — fake `infer_batch`; **test**.

**`tests/test_gemini_batch_api.py`**: 99, 116, 124, 135, 144, 148–149, 160, 174, 178–179, 194, 222, 254, 270, 293, 309, 375, 392, 394, 413, 430, 454, 485, 495, 535, 546, 586, 596, 606, 637, 658, 761, 794 — Gemini batch / `infer` mocks; **test**.

**`tests/test_kwargs_passthrough.py`**: 37, 79, 103, 123, 138, 141, 159, 163, 180, 182, 197, 199, 214, 216, 237, 239, 259, 261, 277, 283, 310, 312, 344, 347, 409, 411, 438, 440, 511, 523, 525, 546, 570, 592, 638, 656, 738, 771 — OpenAI kwargs / `infer` mocks; **test**.

**`tests/test_live_api.py`**: 589, 590, 656–657, 865, 867, 905–906 — wraps live `infer_batch` for batch-mode tests; **test** (live API subclass).

## Verdict on the claim(s)

**C1: CONFIRMED.** At SHA `0dff547`, langextract has no production (or test) code path where an LLM judges an already-produced conversion/extraction output against the source document per page/chunk/unit. The sole production LLM dispatch is `annotation.py:392`, which sends **source chunk text** (plus few-shot examples and optional prior **source** context) to produce extractions. Post-processing (`resolver.resolve`, `resolver.align`) is deterministic string/token alignment (`resolver.py:276–398`, `789+`). `extraction_passes` re-invokes extraction for recall, not verification (`annotation.py:477–491`).

**C2:** All 279 enumerated sites classify as **extraction** (production, examples, live tests), **eval-harness** (`benchmarks/benchmark.py:199`), **test** (mocked unit/integration), or **other** (`scripts/create_provider_plugin.py:387`). Zero **refinement** (no LLM fixes prior pipeline output) and zero **verification** sites.

## Coverage gaps

None. All 6311 tracked files under repo root searched; `.venv/` and `uv.lock` excluded from search only.

## What could still hide a counterexample

- A dynamically loaded community provider plugin (documented in `COMMUNITY_PROVIDERS.md`, not vendored in this clone) could add a verification loop outside this SHA.
- Runtime monkey-patching of `BaseLanguageModel.infer` by downstream consumers (not in-repo).
