# 20a - firecrawl (SHA 183d750)
**Claims tested:** C1, C2
**Exhaustive:** yes

## Method
Repo: `packages/whisker/research/repos/firecrawl` at `183d75057529fca1632dc3b507260be1d4bc3de8`.

Search commands (PowerShell, repo root):
```
rg -i -l "openai|anthropic|claude|gemini|litellm|ollama|chat\.completions|generate_content|GenerativeModel|gpt-|llama|qwen|system_prompt" --glob "!**/node_modules/**" --glob "!**/.git/**" --glob "!**/dist/**"
rg -n "await (generateText|generateObject|streamText|streamObject|embed|embedMany)\(" apps/api/src --glob "!**/*.test.ts" --glob "!**/__tests__/**"
rg -n "await generateCompletions\(|await generateCompletions_F0\(" apps/api/src --glob "!**/*.test.ts" --glob "!**/__tests__/**"
rg -i -n "generateText|generateObject|getModel|openai|anthropic|gemini|embed\(" apps/api/src/scraper/scrapeURL/engines/pdf --glob "!**/__tests__/**" --glob "!**/*.test.ts"
```

Files read in full or in substantial part: `apps/api/src/lib/generic-ai.ts`, `apps/api/src/scraper/scrapeURL/transformers/llmExtract.ts`, `apps/api/src/lib/extract/fire-0/llmExtract-f0.ts`, `apps/api/src/scraper/scrapeURL/lib/extractSmartScrape.ts`, `apps/api/src/scraper/scrapeURL/lib/smartScrape.ts`, `apps/api/src/scraper/scrapeURL/transformers/query.ts`, `apps/api/src/scraper/scrapeURL/transformers/diff.ts`, `apps/api/src/scraper/scrapeURL/transformers/agent.ts`, `apps/api/src/services/monitoring/judgeChange.ts`, `apps/api/src/lib/engpicker.ts`, `apps/api/src/lib/deterministicJson/llm/client.ts`, `apps/api/src/lib/extract/url-processor.ts`, `apps/api/src/lib/extract/fire-0/url-processor-f0.ts`, `apps/api/src/lib/extract/reranker.ts`, `apps/api/src/lib/branding/llm.ts`, `apps/api/src/lib/scrape-interact/browser-agent.ts`, `apps/api/src/scraper/scrapeURL/engines/x-twitter/index.ts`, `apps/api/src/lib/ranker.ts`, `apps/api/src/lib/deep-research/research-manager.ts`, `apps/api/src/lib/generate-llmstxt/generate-llmstxt-service.ts`, PDF engine directory listing (`engines/pdf/*.ts`).

Scope: production `apps/api/src/**` excluding `*.test.ts` and `__tests__/**`. Examples, Python/Rust SDKs, docs, and lockfiles searched for hits but excluded from production inventory unless they contain executable LLM calls (none found outside `apps/api/src`).

## Inventory

### A. Direct LLM/VLM API invocation sites (23)

Each row is an `await generateText|generateObject|embed` in production code. Classification per C2.

| # | file:line | function | input | output | role | C2 class |
|---|-----------|----------|-------|--------|------|----------|
| 1 | `apps/api/src/scraper/scrapeURL/transformers/llmExtract.ts:351` | `generateCompletions` | markdown + schema/prompt/system (no-object mode) | free text | Structured/text extraction when schema mode is `no-object` | extraction |
| 2 | `apps/api/src/scraper/scrapeURL/transformers/llmExtract.ts:457` | `generateCompletions` | same as #1 on quota/rate-limit retry | free text | Fallback model retry for no-object extraction | extraction |
| 3 | `apps/api/src/scraper/scrapeURL/transformers/llmExtract.ts:627` | `generateCompletions` → `experimental_repairText` | malformed JSON text + parse error | fixed JSON string | JSON repair after failed `generateObject` | refinement |
| 4 | `apps/api/src/scraper/scrapeURL/transformers/llmExtract.ts:811` | `generateCompletions` | markdown + JSON schema + system/prompt | structured object | Primary scrape/extract JSON extraction (`generateObject`) | extraction |
| 5 | `apps/api/src/scraper/scrapeURL/transformers/llmExtract.ts:850` | `generateCompletions` | same as #4 on quota retry | structured object | Fallback model retry for `generateObject` | extraction |
| 6 | `apps/api/src/lib/extract/fire-0/llmExtract-f0.ts:237` | `generateCompletions_F0` | markdown + prompt/system (no-object) | free text | Legacy fire-0 no-object extraction path | extraction |
| 7 | `apps/api/src/lib/extract/fire-0/llmExtract-f0.ts:342` | `generateCompletions_F0` → repair callback | malformed JSON + error | fixed JSON string | Legacy fire-0 JSON repair | refinement |
| 8 | `apps/api/src/lib/extract/fire-0/llmExtract-f0.ts:427` | `generateCompletions_F0` | markdown + schema | structured object | Legacy fire-0 primary extraction | extraction |
| 9 | `apps/api/src/scraper/scrapeURL/transformers/query.ts:58` | `performDirectQuoteQuery` | numbered markdown lines + user query | JSON line indices → assembled answer string | Query/highlights: select verbatim lines from scraped markdown | extraction |
| 10 | `apps/api/src/scraper/scrapeURL/transformers/query.ts:153` | `performFreeformQuery` | full page markdown + query | answer text | Query format: freeform Q&A over scraped markdown | extraction |
| 11 | `apps/api/src/lib/extract/url-processor.ts:20` | `generateBasicCompletion` | user prompt (pre-rerank / rephrase) | text | Extract pipeline: rewrite/reframe search prompts | other |
| 12 | `apps/api/src/lib/extract/url-processor.ts:71` | `generateBasicCompletion` | same prompt on rate-limit fallback | text | Fallback for #11 | other |
| 13 | `apps/api/src/lib/extract/fire-0/url-processor-f0.ts:22` | `generateBasicCompletion_FO` | user prompt | text | Legacy fire-0 prompt completion | other |
| 14 | `apps/api/src/lib/deterministicJson/llm/client.ts:59` | `generateCode` | chat messages (codegen system) | Python extraction code string | Deterministic-json: synthesize extraction code | extraction |
| 15 | `apps/api/src/lib/deterministicJson/llm/client.ts:78` | `pickSnippets` | chat messages (anchor picker) | JSON snippet list | Deterministic-json: pick HTML anchor snippets | extraction |
| 16 | `apps/api/src/lib/deterministicJson/llm/client.ts:209` | `makeAskLlm` → `askOnce` | system + user prompt (+ optional schema) | parsed JSON or text | Deterministic-json: inner field-level extraction calls | extraction |
| 17 | `apps/api/src/lib/branding/llm.ts:92` | `enhanceBrandingWithLLM` | branding prompt (+ optional screenshot image) | branding schema object (colors, fonts, logo selection) | Branding endpoint: infer design tokens from page | extraction |
| 18 | `apps/api/src/lib/engpicker.ts:70` | `evaluateURL` | system rubric + first 4000 chars of scraped markdown | `{ is_successful: boolean }` | Engine-picker ops job: classify scrape as bot-block vs real content | other |
| 19 | `apps/api/src/services/monitoring/judgeChange.ts:138` | `callGemini` → `judgeChange` | monitor goal + unified markdown/json diffs | `{ meaningful, confidence, reason, meaningfulChanges[] }` | Monitoring: judge whether a page *diff* matters to user goal | other |
| 20 | `apps/api/src/lib/scrape-interact/browser-agent.ts:343` | browser interact agent | page snapshot + user task prompt + browser tool defs | tool-driven browser actions / final text | Scrape-interact: agentic browser automation | extraction |
| 21 | `apps/api/src/scraper/scrapeURL/engines/x-twitter/index.ts:514` | `fetchProfile` | xAI prompt for @handle profile + posts | structured X profile object | X/Twitter engine: fetch profile via xAI x_search tool | extraction |
| 22 | `apps/api/src/scraper/scrapeURL/engines/x-twitter/index.ts:550` | `fetchPost` | xAI prompt for post/thread/comments | structured X post object | X/Twitter engine: fetch post via xAI x_search tool | extraction |
| 23 | `apps/api/src/lib/ranker.ts:11` | `getEmbedding` | text string | embedding vector | Extract URL ranking: semantic similarity (embedding model, not generative judge) | other |

No `streamText`, `streamObject`, or `embedMany` awaits in production `apps/api/src`.

### B. Production orchestration entry points (call `generateCompletions` / `generateCompletions_F0`; LLM executes at sites in section A)

| file:line | function | triggers LLM via | role | C2 class |
|-----------|----------|------------------|------|----------|
| `llmExtract.ts:1258` | `performCleanContent` | #4/#3 | Remove nav/ads from scraped markdown | refinement |
| `llmExtract.ts:1370` | `performSummary` | #4/#3 | Summarize scraped markdown | extraction |
| `llmExtract.ts:1455` | `generateSchemaFromPrompt` | #4/#3 | Infer JSON schema from natural-language prompt | other |
| `llmExtract.ts:1533` | `generateCrawlerOptionsFromPrompt` | #4/#3 | Infer crawl options from NL prompt | other |
| `llmExtract.ts:1010` | `performLLMExtract` | `extractData` → #4/#3 (+ optional smartScrape) | Scrape JSON/extract format from markdown | extraction |
| `extractSmartScrape.ts:359` | `extractData` | #4/#3 | SmartScrape gate + initial structured extract | extraction |
| `extractSmartScrape.ts:473` | `extractData` | #4/#3 | Re-extract after smartScrape HTML fetch | extraction |
| `diff.ts:19` | `extractDataWithSchema` | #4/#3 | Change-tracking: extract schema fields from one markdown snapshot | extraction |
| `diff.ts:195` | `deriveDiff` | #4/#3 | Change-tracking: summarize prev vs current markdown | other |
| `reranker.ts:143` | `rerankLinksWithLLM` | #4/#3 (per chunk, up to 5000 links) | Score discovered URLs for extract relevance | other |
| `fire-0/reranker-f0.ts:87` | `rerankLinksWithLLM_F0` | #8/#7 | Legacy rerank | other |
| `analyzeSchemaAndPrompt.ts:66` | `analyzeSchemaAndPrompt` | #4/#3 | Classify multi-entity vs single-entity extract | other |
| `fire-0/analyzeSchemaAndPrompt-f0.ts:47` | `analyzeSchemaAndPrompt_F0` | #8/#7 | Legacy schema analysis | other |
| `fire-0/checkShouldExtract-f0.ts:22` | `checkShouldExtract_F0` | #8/#7 | Legacy boolean gate before extract | other |
| `fire-0/batchExtract-f0.ts:39` | `batchExtractPromise_F0` | #8/#7 | Legacy batch extract endpoint | extraction |
| `fire-0/singleAnswer-f0.ts:30` | `singleAnswerCompletion_F0` | #8/#7 | Legacy single-answer extract | extraction |
| `fire-0/llmExtract-f0.ts:519` | `generateSchemaFromPrompt_F0` | #8/#7 | Legacy schema generation | other |
| `batchExtract.ts:111` | `batchExtractPromise` | `extractData` → #4/#3 | v1/v2 extract batch | extraction |
| `singleAnswer.ts:78` | `singleAnswerCompletion` | `extractData` → #4/#3 | v1/v2 extract single-answer (no direct await; uses extractData) | extraction |
| `deep-research/research-manager.ts:160` | `generateSearchQueries` | #4/#3 | Deep research: plan SERP queries | other |
| `deep-research/research-manager.ts:230` | `analyzeAndPlan` | #4/#3 | Deep research: analyze findings | other |
| `deep-research/research-manager.ts:305` | `generateFinalReport` | #4/#3 | Deep research: final report synthesis | extraction |
| `generate-llmstxt/generate-llmstxt-service.ts:185` | per-URL handler | #4/#3 | llms.txt: title/description from page markdown | extraction |

### C. Delegated external LLM (production path, no in-repo `generateText`/`generateObject`)

| file:line | function | input | output | role | C2 class | note |
|-----------|----------|-------|--------|------|----------|------|
| `scrapeURL/lib/smartScrape.ts:82` | `smartScrape` | POST `{ url, prompt, models: gemini-2.5-pro + gemini-2.5-flash }` to `SMART_SCRAPE_API_URL/smart-scrape` | `{ scrapedPages[], tokenUsage }` HTML pages | Agentic re-scrape when static extract insufficient | extraction | LLM runs in external smart-scrape service; not enumerated at file:line inside this clone |
| `scrapeURL/transformers/agent.ts:35` | `performAgent` | calls `smartScrape` | HTML → markdown via `parseMarkdown` | v1 agent scrape format | extraction | Same external delegate |
| `extractSmartScrape.ts:402+` | `extractData` | calls `smartScrape` when `useAgent && shouldUseSmartscrape` | refreshed HTML → re-extract | Extract endpoint smart-scrape escalation | extraction | Same external delegate |

### D. PDF handling

Searched all production files under `apps/api/src/scraper/scrapeURL/engines/pdf/` (including `firePDF.ts`, `pdfParse.ts`, `runpodMU.ts`, `shadowComparison.ts`, `fire-pdf/*`). **Zero** matches for `generateText`, `generateObject`, `getModel`, `openai`, `anthropic`, `gemini`, or `embed`.

PDF conversion routes through non-LLM services in-repo (`FIRE_PDF_BASE_URL`, `PDF_MU_V2_BASE_URL`, local `pdfParse`, shadow comparison). No in-repo per-page LLM verification of PDF markdown against source.

## Verdict on the claim(s)

**C1 (negative existential): CONFIRMED for firecrawl at 183d750.**

No production path judges an already-produced conversion output against its source document per page/chunk/unit.

Closest non-matches (explicitly not C1):
- `judgeChange.ts:9-60,138` compares **temporal diffs** (previous scrape vs current scrape) against a **monitor goal**, not output-vs-source fidelity (`apps/api/src/services/monitoring/judgeChange.ts:172-180`).
- `engpicker.ts:69-101` judges whether markdown **looks like a bot-block/error page**, using markdown alone with no source document (`apps/api/src/services/monitoring/judgeChange.ts` N/A; cite `engpicker.ts:77-98`).
- `performCleanContent` (`llmExtract.ts:1193-1258`) **rewrites** markdown to drop chrome; input and output are both markdown with no parallel source payload.
- `deriveDiff` (`diff.ts:195-206`) compares **two markdown snapshots** from successive scrapes, not markdown vs original PDF/HTML source.

**C2:** All 23 direct invocation sites classified above (extraction 15, refinement 2, other 6). Orchestration and external-delegate rows classified separately.

## Coverage gaps

- **External smart-scrape service** (`SMART_SCRAPE_API_URL`): production Firecrawl code delegates agentic browsing here (`smartScrape.ts:82-111`); the service's internal LLM call sites are **not in this clone** and were not line-enumerated.
- **External PDF services** (`FIRE_PDF_BASE_URL`, `PDF_MU_V2_BASE_URL`): HTTP delegates; no LLM symbols in in-repo PDF engine code, but remote service internals were not inspected.
- **Examples/** (`examples/*`): many LLM demo scripts; excluded from production inventory per charter test/docs marking.
- **Python SDK** (`apps/python-sdk/**`): API client only; no LLM invocations.
- **Rust SDK / test-site / helm**: no production LLM call sites found.

## What could still hide a counterexample

- LLM logic inside the **external smart-scrape** or **fire-pdf** microservices not vendored in this repo.
- Dynamic `require()` / string-eval paths (none found in search floor; `langsmith.ts` re-exports AI SDK wrappers without additional calls).
- Runtime-only configuration enabling a code path not reachable from static review (no evidence found).
