# 00 - Shared Evidence Baseline: google/langextract

**Target:** `packages/whisker/research/repos/langextract` (Google LangExtract)
**Pinned SHA:** `0dff5479aa51934c7d5833a7c38e2a5abba4e0c2` (last commit `2026-07-02`, cloned `2026-07-03`)
**Package version:** `1.6.0` (`pyproject.toml:22`)
**License:** Apache-2.0 (`pyproject.toml:26`)
**Clone caveat:** SHALLOW clone (`.git/shallow` present, 50 commits visible, 10 author lines in-window). Full maintenance-pulse / contributor history is a web question, not a git fact here.

Every claim below carries a `file:line` anchor into the target (paths relative to `packages/whisker/research/repos/langextract/`) or into our monorepo (paths relative to workspace root `c:\Users\sabo2\Desktop\cppalliance\`), or a reproduced number from a read-only command. No claim is unanchored.

---

## 1. What the target is

An LLM-based structured-information-extraction library. Given source text, an instruction prompt, and few-shot `ExampleData`, it (a) chunks the text on sentence/token boundaries, (b) prompts an LLM per chunk to emit YAML/JSON extractions, (c) parses the model output into `Extraction` objects, and (d) **grounds each extraction back to a character span in the source** via multi-tier token alignment (`char_interval`), tagging each with an `AlignmentStatus` (`MATCH_EXACT | MATCH_LESSER | MATCH_FUZZY | None`). Parallelism lives inside each provider's `infer()` (thread pool over the prompt batch), not in the orchestration layer.

Provider-pluggable via an entry-point registry (`pyproject.toml:94-97`): Gemini (default), OpenAI, Ollama, plus batch-API variants and third-party plugins.

Overlap with our stack: it is a direct analog of the **tapetum_llm advisory lane** (LLM adjudication over chunked documents with evidence grounding) sitting on a provider abstraction analogous to our **pipeline** framework (`ModelBackend`).

## 2. Size

- Library (`langextract/`, excl. tests): **~10,715 LOC** across 45 `.py` files.
- Largest modules: `resolver.py` **1213**, `providers/gemini_batch.py` **754**, `providers/ollama.py` **581**, `annotation.py` **538**, `visualization.py` **535**, `core/tokenizer.py` **514**, `providers/openai_batch.py` **482**, `providers/gemini.py` **450**, `chunking.py` **431**, `core/format_handler.py` **408**, `extraction.py` **392**, `providers/openai.py` **341**.
- Tests: **28 test files, 522 `def test_` functions** (reproduced via `Select-String '^\s*def test_'`). Alignment-specific: `resolver_test.py` 37, `fuzzy_alignment_cases_test.py` 16, `chunking_test.py` 16, `annotation_test.py` 17. Provider/schema: `inference_test.py` 40, `schema_test.py` 37, `provider_schema_test.py` 28, `gemini_retry_test.py` 27, `openai_batch_test.py` 23.
- Language: Python only (`requires-python >=3.10`, `pyproject.toml:25`).
- Runtime deps are cloud-SDK-heavy: `google-genai`, `google-cloud-storage`, `openai` (optional extra), plus `numpy`/`pandas`/`pydantic`/`PyYAML`/`more-itertools`/`tqdm` (`pyproject.toml:30-60`).

## 3. Runtime facts

- **Parallelism model:** per-provider thread pool. `GeminiLanguageModel.infer` opens `ThreadPoolExecutor(max_workers=min(self.max_workers, len(batch_prompts)))` (`providers/gemini.py:477-479`), submits one future per prompt keyed by index (`gemini.py:480-485`), collects via `as_completed` but writes into a pre-sized `results[index]` list (`gemini.py:487-497`), then **yields strictly in input order** (`gemini.py:499-504`). `max_workers` default **10** (`gemini.py:129`; identical in `openai.py:54`). OpenAI provider mirrors this exactly (`openai.py:355-389`).
- **Orchestration is serial:** `Annotator._annotate_documents_single_pass` iterates batches sequentially and calls `infer()` once per batch (`annotation.py:366-392`); ordering/attribution is maintained by an explicit `doc_order`/`next_emit_idx` emit cursor (`annotation.py:307-346`). Batches are formed by `more_itertools.batched` (`chunking.py:278`), default `batch_length=1` (`annotation.py:214`).
- **Determinism knobs:** provider temperature defaults to `0.0` for Gemini (`gemini.py:128`), `None` for OpenAI (`openai.py:53`). No global seed pin at the library level; nothing sorts extraction output beyond `extraction_index` (`resolver.py:534`). Thread-pool completion order does not affect output order (index-preserving), but concurrent in-flight requests exist by default.
- **Retry:** only for *transient HTTP* errors (503/429/timeout/network) with exponential backoff + jitter, per-prompt (`gemini.py:351-391`, `_RETRYABLE_API_CODES` `gemini.py:49`). **There is NO schema-noncompliance retry loop.** A parse/schema failure either raises `ResolverParsingError` or, with `suppress_parse_errors=True`, logs a warning and returns `[]` (`resolver.py:309-321`).
- **Structured output enforcement:** provider-native only. OpenAI: `response_format={"type":"json_schema", ..., "strict": True}` built from examples (`providers/schemas/openai.py:178-188`, applied `openai.py:209-211`), else `{"type":"json_object"}` JSON mode (`openai.py:224`). Gemini: `response_schema`/`response_mime_type` via `to_provider_config()` (`gemini.py:363-366`, keys `gemini.py:99-108`). Ollama: `FormatModeSchema` = format-only JSON mode, non-strict (`providers/ollama.py:172-178`, `core/schema.py:142-149`). **No vLLM/`guided_json`/`guided_decoding`/`extra_body` guided path exists anywhere** (grep over `langextract/`: 0 hits for `guided_json|guided_decoding|vllm|extra_body`).
- **Grounding:** three-tier, token-level. (1) Monotonic exact-occurrence DP (`_apply_monotonic_exact_matches` / `_select_monotonic_matches`, `resolver.py:948-959`, `1113-1243`), (2) `difflib.SequenceMatcher` exact/lesser (`resolver.py:962-1019`), (3) fuzzy fallback on unmatched only: LCS DP default (`_best_lcs_spans`, O(n·m²), `resolver.py:1287-1363`) or legacy sliding-window difflib ratio (`_fuzzy_align_extraction`, `resolver.py:591-715`). Thresholds: `_FUZZY_ALIGNMENT_MIN_THRESHOLD = 0.75`, `_FUZZY_ALIGNMENT_MIN_DENSITY = 1/3` (`resolver.py:57-58`). Light plural stemming with `lru_cache` (`_normalize_token`, `resolver.py:1275-1281`). `char_interval` derived from token char spans (`resolver.py:782-785`, `chunking.py:216-243`).
- **Prompt-injection posture:** none found. Source text is formatted into the prompt by `ContextAwarePromptBuilder`/`QAPromptGenerator` (`annotation.py:360-375`) with no delimiter-wrapping or injection-defense layer; untrusted paper text and instructions share the prompt namespace.

## 4. Comparison anchors (their `file:line` vs our `file:line`)

| Concern | langextract (target) | our monorepo |
| --- | --- | --- |
| Parallel batch of LLM calls | `providers/gemini.py:477-504` ThreadPoolExecutor, index-ordered yield, `max_workers=10` default (`gemini.py:129`) | serial by default: `pipeline/tasks.py:30,38` `_TASK_CONCURRENCY=1` / `Semaphore(1)`; `runner.py:147` bounded sem; tapetum forces `default_concurrency=1` (`whisker/tapetum_llm/adjudicate.py:409`) |
| Order-preserving concurrency pattern | `gemini.py:487-504` pre-sized `results[index]` | `pipeline/runner.py:133-162` `gather_concurrent` returns `(index,result)` sorted by index (same idea, but capped at Semaphore(1) for dissect/tapetum) |
| Structured output strategy | native `response_format`/`response_schema` strict, or json_object (`schemas/openai.py:178-188`, `openai.py:224`, `gemini.py:363-366`) | schema-in-prompt + raw-JSON extract + retry loop for self-hosted vLLM (`pipeline/model_backends.py:296-421`, `_extract_json` `234-247`... `115-133`); pydantic-ai `output_type` for cloud/native (`model_backends.py:466-490`) |
| Schema-failure recovery | none (raise or drop, `resolver.py:309-321`) | bounded raw-JSON retry with error feedback + length-aware `max_tokens` growth (`model_backends.py:311-421`, `_RAW_JSON_MAX_ATTEMPTS=3` `76-85`) |
| Evidence grounding | token-level 3-tier alignment, `char_interval`, `AlignmentStatus`, thresholds 0.75/0.333 (`resolver.py:57-58, 327-400, 789-1073`) | document-level substring OR rapidfuzz `partial_ratio` floor 0.90 (`whisker/tapetum_llm/grounding.py:49-52`, `EVIDENCE_FUZZY_FLOOR=0.90` `constants.py:50`); drop-if-ungrounded, no spans |
| Chunking | sentence/token `ChunkIterator`, `max_char_buffer` default 200 (`chunking.py:343-506`, `annotation.py:213`) | H2-heading, fence-aware, greedy-pack, hard-split fallback, `MAX_PAPER_MD_CHARS=500_000` (`whisker/tapetum_llm/chunking.py:57-148`, `constants.py:44`) |
| Multi-pass / merge | sequential passes, first-pass-wins overlap merge (`annotation.py:447-530`, `_merge_non_overlapping_extractions:46-84`) | two-tier fast→deep cascade, severity-aware worst-axis fold (`adjudicate.py:171-246`, `chunking.py:34-51`) |
| Determinism authority | none stated in-repo | root `CLAUDE.md` D1-D11 (serial default, temp/seed pins), `MODELS.md` workaround inventory |
| Model sovereignty | cloud-first (Gemini/OpenAI); self-hosted only via Ollama JSON mode (`providers/ollama.py`) | open-weight self-hosted mandate (`CLAUDE.md` "Model sovereignty"; `pipeline/model_backends.py` `VllmThinkingBackend`) |
| Prompt-injection defense | none found | `wrap_source`/`inject_untrusted` guard delimiters + framework floor (`pipeline` CLAUDE.md "Source delimiter contract"; tapetum uses `ctx.inject_untrusted`, `adjudicate.py:327,348`) |

## 5. Decision questions (with baseline evidence)

**DQ1 - How does langextract do PARALLEL batch LLM processing while keeping results deterministic/ordered?**
Parallelism is per-provider, not in the orchestrator. `GeminiLanguageModel.infer` (and identically `OpenAILanguageModel.infer`) spins a `ThreadPoolExecutor(max_workers=min(self.max_workers, len(batch_prompts)))` (`gemini.py:477-479`, `openai.py:356-358`), submits `{future: i}` (`gemini.py:480-485`), drains with `as_completed` but stores each into a pre-allocated `results[index]` slot and then yields in the original prompt order (`gemini.py:487-504`). So completion order is arbitrary but **output order is index-stable**. Default `max_workers=10` (`gemini.py:129`). The `Annotator` above it is serial over batches (`annotation.py:366-392`) with an explicit emit cursor for cross-batch document ordering (`annotation.py:307-346`, `504-528`). Determinism caveat: multiple in-flight requests exist by default (temperature-0 helps but is not a determinism guarantee on hosted endpoints), which directly conflicts with our D11 serial-default invariant.

**DQ2 - How does it enforce structured output? Does it use vLLM/OpenAI guided decoding (`response_format`, `guided_json`)?**
It uses **OpenAI-native `response_format`** (`{"type":"json_schema","json_schema":{...,"strict":True}}`, `schemas/openai.py:178-188`; JSON-mode fallback `{"type":"json_object"}`, `openai.py:224`) and **Gemini `response_schema`/`response_mime_type`** (`gemini.py:363-366`). It does **NOT** use vLLM `guided_json`/`guided_decoding` (grep: 0 hits). Self-hosted structured output is only Ollama's format-mode JSON (non-strict, no field constraints; `ollama.py:172-178`, `core/schema.py:146-149`). There is no in-prompt-schema + retry strategy and **no schema-failure retry** (parse errors raise or are dropped, `resolver.py:309-321`); retries cover transient HTTP only (`gemini.py:351-391`). This is the inverse of our self-hosted path, which needs schema-in-prompt + raw-JSON retry because vLLM tool/guided paths were unreliable (`model_backends.py:234-421`; `MODELS.md:121` names `guided_json` as the *retire-when* for the deepseek-v4-pro token-injection workaround, i.e. we want guided decoding but have not adopted it, and langextract does not provide it).

**DQ3 - What of langextract's grounding is stronger/weaker than our `grounding.py`?**
STRONGER (langextract): token-level spans with explicit `char_interval` and a graded `AlignmentStatus` (exact/lesser/fuzzy), a monotonic occurrence DP so repeated mentions map to successive positions (`resolver.py:1113-1243`), an LCS DP fuzzy matcher with a coverage gate (0.75) **and** a density gate (1/3) to reject scattered matches (`resolver.py:1377-1404`), and plural-stemming normalization (`resolver.py:1275-1281`). It returns *where* in the source each item is. WEAKER than ours in scope: it aligns extracted entity strings, not arbitrary evidence quotes, and correctness of the *value* is not verified (only its location). OUR `grounding.py` (`whisker/tapetum_llm/grounding.py:24-56`) is coarser: document-level normalized-substring test OR a single `rapidfuzz.partial_ratio >= 0.90` floor (`constants.py:50`), returns only kept/dropped counts (no spans, no status tiers, no token intervals). Ours is simpler and cheaper; theirs is more precise and locatable.

**DQ4 - What is adoptable for our tapetum batch lane under our determinism constraint (serial default; a NEW package MAY opt into concurrency via a per-package mechanism, never a global flip)?**
Adoptable: (a) the **index-keyed ordered-collection pattern** (`gemini.py:487-504`) is exactly our existing `gather_concurrent` shape (`runner.py:133-162`), so a *per-tapetum* bounded pool that writes `results[index]` and yields in order would preserve determinism-of-output while allowing parallel chunk triage, without touching the global `Semaphore(1)` (`tasks.py:38`) that dissect relies on. (b) The **graded `AlignmentStatus` + char-span return** is a clean upgrade to `ground_spans` (return spans+status instead of a boolean drop), giving trace/debug locatability. (c) The **first-pass-wins overlap merge** (`annotation.py:46-84`) is a determinism-friendly fold. NOT adoptable as-is: `max_workers=10` default and any cloud-provider dependence violate model-sovereignty and D11; langextract's lack of schema-retry and injection defense are regressions against our invariants. Any concurrency must be a per-tapetum opt-in (mirroring the existing `default_concurrency` param, `adjudicate.py:409`), never a change to the framework default.

## 6. Persona roster (22)

Core generic roster (01-17) + ad-hoc LLM-extraction specialists (18-22).

| NN | Name | Mandate | Failure class it hunts |
| --- | --- | --- | --- |
| 01 | Security-Reviewer | Audit untrusted-input handling, credential flow, deserialization | RCE / secret leak / unsafe parse |
| 02 | License-Compliance | Verify Apache-2.0 compatibility with our BSL-1.0 stack and dep licenses | license contamination / attribution gap |
| 03 | Determinism-Auditor | Check run-to-run stability vs our D1-D11 (serial default, seed/temp pins) | nondeterministic output / hidden concurrency |
| 04 | API-Contract-Design | Assess public surface stability, backward-compat shims, kwargs sprawl | brittle contract / silent breaking change |
| 05 | Maintainability-Complexity | Grade module cohesion, the 1213-LOC resolver, `_compat` debt | unmaintainable hotspot |
| 06 | Performance-Scalability | Evaluate LCS DP O(n·m²), thread-pool sizing, batch-API cost | pathological slowdown at scale |
| 07 | Test-Suite-Auditor | Judge the 522 tests: live-API mocking, alignment coverage, flakiness | false-green suite / untested path |
| 08 | Documentation-Claims | Cross-check README/docstring claims against code behavior | doc-vs-code drift |
| 09 | Error-Handling-Robustness | Trace failure modes: parse errors, empty outputs, partial batches | silent drop / swallowed failure |
| 10 | Adversary-Evasion | Model an attacker crafting text/extractions to evade or corrupt alignment | evasion / poisoning |
| 11 | False-Positive-Hunter | Find inputs the aligner wrongly grounds (spurious `MATCH_FUZZY`) | wrong-span acceptance |
| 12 | False-Negative-Hunter | Find valid extractions the aligner wrongly rejects (`char_interval=None`) | lost true positive |
| 13 | Dependency-Supply-Chain | Audit google-genai/openai/pandas footprint and pin hygiene | supply-chain / bloat risk |
| 14 | Portability-Platform | Windows/PowerShell, offline, no-GPU, non-Google-cloud viability | platform lock-in |
| 15 | Downstream-Consumer | Take the integrator's view: can our tapetum lane import/adapt cleanly | integration friction |
| 16 | Product-Decision-Skeptic | Ask whether adopting anything here beats our current design | net-negative adoption |
| 17 | Steelman | Argue the strongest case FOR trusting/adopting the target | over-dismissal bias |
| 18 | Parallel-Batching-Architect | Scrutinize the ThreadPoolExecutor/index-yield model vs our serial invariant | ordering bug / concurrency-determinism clash |
| 19 | Schema-Compliance-Auditor | Probe structured-output strategy, strict-mode gaps, missing guided decoding | schema-noncompliance / no self-hosted constraint |
| 20 | Grounding-Alignment-Specialist | Deep-audit the 3-tier aligner, thresholds, LCS density gate | mis-grounding / threshold miscalibration |
| 21 | Prompt-Injection-Auditor | Assess absence of source-wrapping vs our `wrap_source` contract | injection via paper/web text |
| 22 | Self-Hosting-Sovereignty-Auditor | Judge open-weight/self-hosted viability vs our model-sovereignty mandate | cloud lock-in / sovereignty breach |

## 7. Web questions (code cannot answer these)

```json
[
  {
    "question": "What is the maintenance pulse and release cadence of google/langextract around v1.6.0 (2026) — active, slowing, or archived?",
    "search_query": "google langextract 1.6.0 release changelog 2026 maintenance activity github"
  },
  {
    "question": "Are there open/closed issues about parallel inference ordering, ThreadPoolExecutor races, or Gemini/OpenAI batch-API scheduling bugs in langextract?",
    "search_query": "google langextract github issue parallel max_workers batch ordering ThreadPoolExecutor bug"
  },
  {
    "question": "Do langextract maintainers or issues discuss vLLM guided_json / guided decoding or self-hosted structured-output support beyond Ollama JSON mode?",
    "search_query": "langextract vLLM guided_json guided decoding self-hosted structured output ollama github discussion"
  },
  {
    "question": "How does langextract compare to alternatives for grounded LLM extraction (instructor, outlines, LangChain extraction, GLiNER) on evidence-span grounding?",
    "search_query": "langextract vs instructor outlines gliner grounded structured extraction char_interval comparison 2026"
  },
  {
    "question": "Are there reports of langextract fuzzy-alignment producing wrong char_interval spans or dropping valid extractions (calibration of the 0.75 threshold)?",
    "search_query": "langextract fuzzy alignment char_interval wrong span missing extraction threshold issue"
  }
]
```

## 8. Prior work

None. This is the first research run against this target.

---

## Persona report template

Each persona (01-22) appends one report using EXACTLY this template:

```
# NN - <Persona name>

**Verdict:** usable | usable-with-conditions | garbage   (+ 1 sentence why)
**Confidence:** high | medium | low

## Findings
- [CRITICAL|HIGH|MED|LOW] <claim>. Evidence: <file:line OR runtime number from 00>.
  Impact: <why it makes the target more/less trustworthy or adoptable>.
  (repeat; 3-8 findings, ranked)

## False-pass hypothesis
<one concrete case the target/our-equivalent would wrongly accept, or "none found">

## False-fail hypothesis
<one concrete case it would wrongly reject, or "none found">

## What would change my mind
<the single piece of evidence that would flip my verdict>
```
