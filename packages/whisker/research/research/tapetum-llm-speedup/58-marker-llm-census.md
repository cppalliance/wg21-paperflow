# 58 - marker-LLM-Services-Census

**Verdict:** usable-with-conditions — marker proves selective, block-gated LLM calls with scoped image+local-html payloads can cut call volume sharply, but it is a conversion corrector not a document-QA judge; porting requires our router to replace marker's layout block-type gates without dropping monolith/metadata coverage on ambiguous papers.
**Confidence:** high

## Findings

- [CRITICAL] `--use_llm` is a global off-by-default gate: `ConfigParser.get_llm_service()` returns `None` unless `use_llm=True` (`marker/config/parser.py:134-142`), and every LLM processor no-ops when `use_llm=False` or `llm_service is None` (`marker/processors/llm/__init__.py:64-65`, `138-139`, `llm_meta.py:29-30`). Impact: baseline marker run = **0 LLM calls**; our cold fleet always pays **6.0 calls/paper** (`00-baseline.md:22-23`). Quality risk: none at default; enabling LLM adds correction coverage marker's deterministic path lacks.

- [CRITICAL] Nine LLM processors register in the default PDF pipeline when `--use_llm` is on (`marker/converters/pdf.py:97-107`): `LLMTableProcessor`, `LLMTableMergeProcessor`, `LLMFormProcessor`, `LLMComplexRegionProcessor`, `LLMImageDescriptionProcessor`, `LLMEquationProcessor`, `LLMHandwritingProcessor`, `LLMMathBlockProcessor`, `LLMSectionHeaderProcessor`, `LLMPageCorrectionProcessor`. Simple block processors batch through `LLMSimpleBlockMetaProcessor` (`marker/converters/__init__.py:48-62`). Impact: call count scales with **detected block inventory**, not page count. Quality risk: skipping a block type skips that correction path entirely.

- [HIGH] Per-processor triggers (selective, not always-on):

  | Processor | Block types | Extra gate | Calls per hit |
  |---|---|---|---|
  | `LLMTableProcessor` | Table, TableOfContents | skip if `row_count > max_table_rows` (175) (`llm_table.py:132-133`) | `ceil(rows/60)` chunks × up to `max_table_iterations` (2) (`llm_table.py:23-38`, `143-178`, `256-263`) |
  | `LLMTableMergeProcessor` | adjacent table pairs | geometric heuristics + `no_merge_tables_across_pages` (`llm_table_merge.py:165-257`) | 1 per pair in a merge run, chain up to `len(run)-1` (`llm_table_merge.py:296-328`) |
  | `LLMFormProcessor` | Form | skip if no cells and no html (`llm_form.py:65-75`) | 1 |
  | `LLMComplexRegionProcessor` | ComplexRegion | none | 1 |
  | `LLMImageDescriptionProcessor` | Picture, Figure, Diagram | **disabled when `extract_images=True` (default)** — returns `[]` (`llm_image_description.py:17`, `43-47`; test `test_llm_processors.py:115-126`) | 1 per figure when `extract_images=False` |
  | `LLMEquationProcessor` | Equation | skip if block height `< min_equation_height` (0.06 × page) unless `redo_inline_math` (`llm_equation.py:12-15`, `80-88`) | 1 |
  | `LLMHandwritingProcessor` | Handwriting, Text | Text only if no lines and empty raw text (`llm_handwriting.py:36-48`) | 1 |
  | `LLMMathBlockProcessor` | TextInlineMath + math-detected blocks | **off unless `redo_inline_math=True`** (`llm_mathblock.py:17-23`, `79-81`) | 1 per inference block |
  | `LLMSectionHeaderProcessor` | all SectionHeaders in doc | skip if none (`llm_sectionheader.py:145-154`) | **1 per document** |
  | `LLMPageCorrectionProcessor` | per page | **off unless `block_correction_prompt` set** (`llm_page_correction.py:33-35`, `268-270`) | 1–2/page (`reorder_first` recurses, `llm_page_correction.py:169-175`) |

  Impact: typical digital WG21 paper likely pays **1 section-header call + 0–N table/equation calls**, not a fixed 6. Quality risk: papers whose defects live outside flagged block types (metadata drift, subtle wording on plain Text) would evade LLM entirely.

- [HIGH] Call count is **bounded by content structure and hard caps**, not a fixed per-doc budget:

  ```
  upper_bound =
    |eligible_simple_blocks|                          # 1 call each
  + Σ_tables  min(ceil(rows/60), rows≤175) × 2       # max_table_iterations
  + Σ_merge_runs (|run| - 1)                         # table merge pairs
  + 1_if_section_headers
  + pages × (1..2)_if_block_correction_prompt
  + |math_blocks|_if_redo_inline_math
  ```

  Hard skips: `max_table_rows=175` (`llm_table.py:27-30`), chunk size 60 (`llm_table.py:23-26`), retry iterations capped at 2 (`llm_table.py:35-38`). No document-wide call ceiling — a 10-table paper can exceed our 6-call cap. Impact: marker trades **predictable fixed cost** for **variable cost tied to hard regions**. Quality risk: tables >175 rows get no LLM correction (`llm_table.py:132-133`).

- [HIGH] Payload scope: each call sends **one block image (or two for merge) + local html/markdown**, never full document (`llm_table.py:237`, `llm_form.py:82-83`, `llm_equation.py:97-98`, `llm_table_merge.py:323-327`). Contrast: our unit checks send **full candidate markdown every call** (`00-baseline.md:43-47`). Impact: marker-style scoping could cut prefill tokens ~6× on multi-call papers even when call counts match. Quality risk: cross-page/cross-unit defects invisible to block-local prompts.

- [MED] In-document LLM concurrency defaults to **`max_concurrency=3`** thread pool per processor (`marker/processors/llm/__init__.py:42-45`, `163-172`, `llm_meta.py:44-49`). Services are synchronous; no cross-document LLM pool. Impact: at 16 vLLM slots, marker's per-doc cap of 3 concurrent calls under-utilizes fleet vs our 32-paper client concurrency (`00-baseline.md:34-35`) — but each marker call is smaller/faster. Quality risk: MoE batch-composition variance if we raised in-doc parallelism (same concern as `00-baseline.md:95-96`).

- [MED] Service layer defaults (all inherit `BaseService` unless overridden):

  | Setting | Default | Location | Per-service notes |
  |---|---|---|---|
  | `timeout` | 30 s | `marker/services/__init__.py:13` | Gemini/Vertex: `timeout * 1000` ms HTTP (`gemini.py:140`, `vertex.py:25`); OpenAI/Azure/OpenRouter: passed to `chat.completions.parse` (`openai.py:100`, `azure_openai.py:82`, `openrouter.py:112`); Claude: `messages.parse(timeout=...)` (`claude.py:82`); **Ollama: no timeout on `requests.post`** (`ollama.py:54-55`) |
  | `max_retries` | 2 (3 total tries) | `marker/services/__init__.py:14-16` | OpenAI/Azure/OpenRouter/Claude/Gemini: linear backoff `tries * retry_wait_time` (`openai.py:89-123`, `gemini.py:61-108`, `claude.py:72-111`); **Ollama: single attempt, no retry loop** (`ollama.py:54-71`) |
  | `retry_wait_time` | 3 s | `marker/services/__init__.py:17` | |
  | `max_output_tokens` | `None` (unlimited) | `marker/services/__init__.py:18-20` | Gemini honors if set (`gemini.py:69-70`); Claude uses separate `max_claude_tokens=8192` (`claude.py:22-24`) |

  Impact: marker tolerates shorter per-call timeouts (30 s vs our 120 s unit/page caps, `00-baseline.md:53-54`) because payloads are block-scoped. Quality risk: tight timeout on large table html could fail silently (`openai.py:128` returns `{}`).

- [HIGH] **Quantified comparison to our 2284-call / 381-paper fleet** (`00-baseline.md:17-23`):

  | Scenario | Est. calls | Calls/paper | vs 2284 baseline |
  |---|---:|---:|---|
  | Our measured cold fleet | 2284 | 6.0 | — |
  | Marker `--use_llm` off | 0 | 0 | −100% |
  | Skip our 70% zero-defect unit checks only (1057 calls, `00-baseline.md:29-30`) | 1227 | 3.2 | −46% wall if latency equal |
  | Marker-style on WG21 (1 section-header/doc + ~30% papers with tables ×1.5 + ~3 display equations/paper) | ~1350 | ~3.5 | −41% (~1230 s saved at 20 s/call/16 slots) |
  | Marker-style lower bound (section headers only, no tables/equations flagged) | ~381 | 1.0 | −83% |
  | Marker-style upper bound on table-heavy doc (10 tables × 100 rows: 10×2 chunks×2 iter + 1 header) | 41 | 41 | +583% vs our 6-call cap |

  Our router already gates unit checks (`00-baseline.md:90`), but marker gates **harder**: no always-on monolith/metadata, block-type detection first, optional processors default off, and "No corrections needed" short-circuit skips rewrite (`llm_table.py:246-247`, `llm_equation.py:124-125`). Quality risk: removing monolith+metadata without equivalent deterministic pre-gate would drop the 16/381 papers whose verdicts LLM findings changed (`00-baseline.md:29-30`).

## False-pass hypothesis

Adopting marker-style selectivity that skips monolith+metadata on "clean" router passes would false-pass papers where defects span multiple pages or live in plain Text blocks (marker never LLM-corrects undetected Text; `LLMHandwritingProcessor` skips Text with existing lines, `llm_handwriting.py:44-47`). A cross-page consistency error our monolith catches today would survive.

## False-fail hypothesis

Aggressive table chunking (`max_rows_per_batch=60`, `llm_table.py:143-178`) or skipping tables >175 rows (`llm_table.py:132-133`) could leave broken tables that our full-markdown unit judge flags; marker users see silent skip, we would see review/fail — opposite direction, but copying marker's hard caps into our judge without equivalence proof would false-fail table-heavy WG21 papers.

## What would change my mind

Measured call-count histogram from marker `--use_llm` on our 381-paper corpus (aggregate `llm_request_count` block metadata written at `openai.py:106-108` / `gemini.py:89-92`) showing median calls/paper and verdict-coverage overlap with our 16 changed-verdict papers.
