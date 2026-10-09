# 20b - firecrawl LLM extraction completeness/failure semantics
**Claims tested:** C4 (foreign completeness facts); supporting audit for C2 classification (extraction vs other)
**Exhaustive:** no (see Coverage gaps)

## Method

Repo: `packages/whisker/research/repos/firecrawl` at SHA `183d750` (per `00-baseline.md`).

```text
git -C .../firecrawl rev-parse HEAD
git -C .../firecrawl grep -n -E "generateObject|generateText|generateCompletions|generateBasicCompletion|extractData\(" -- apps/api/src | rg -v "__tests__|\.test\."
git -C .../firecrawl grep -n -i -E "openai|anthropic|claude|gemini|litellm|ollama|extract|schema|partial" -- apps/api/src
git -C .../firecrawl ls-tree -r HEAD --name-only -- apps/api/src | rg -i "extract|llm|deterministic"
```

Files read in full or in targeted sections: `apps/api/src/lib/generic-ai.ts`, `apps/api/src/scraper/scrapeURL/transformers/llmExtract.ts`, `apps/api/src/scraper/scrapeURL/lib/extractSmartScrape.ts`, `apps/api/src/lib/extract/extraction-service.ts`, `apps/api/src/lib/extract/fire-0/extraction-service-f0.ts`, `apps/api/src/lib/extract/fire-0/llmExtract-f0.ts`, `apps/api/src/lib/extract/completions/{batchExtract,singleAnswer,analyzeSchemaAndPrompt}.ts`, `apps/api/src/lib/extract/fire-0/completions/{batchExtract-f0,singleAnswer-f0,checkShouldExtract-f0,analyzeSchemaAndPrompt-f0}.ts`, `apps/api/src/lib/extract/{url-processor,reranker,document-scraper}.ts`, `apps/api/src/services/extract-worker.ts`, `apps/api/src/lib/deterministicJson/{extract,llm/client,pipeline/postprocess,pipeline/validate}.ts`, `apps/api/src/scraper/scrapeURL/transformers/{deterministicJson,diff,query}.ts`, `apps/api/src/lib/branding/llm.ts`, `apps/api/src/lib/generate-llmstxt/generate-llmstxt-service.ts`, `apps/api/src/lib/deep-research/research-manager.ts` (partial), `apps/api/src/lib/engpicker.ts` (partial), `apps/api/src/scraper/scrapeURL/engines/x-twitter/index.ts` (partial).

Production wiring note: `/v1/extract` and `extract-worker` call `performExtraction_F0` (`controllers/v1/extract.ts:60`, `services/extract-worker.ts:59`). `lib/extract/extraction-service.ts` (`performExtraction`, fire-1) is present but has **no production caller** at this SHA.

## Inventory

Each row is one decision point: silent content loss (S), surfaced failure (F), or both (B). Role column names the LLM step.

| # | Path | file:line | S/F | Role / finding |
|---|------|-----------|-----|----------------|
| 1 | Core object extraction (scrape json/extract, extract completions) | `apps/api/src/scraper/scrapeURL/transformers/llmExtract.ts:811` | F | `generateObject`; schema via `jsonSchema`/`zod`; throws on hard failure |
| 2 | Quota/rate-limit retry (object mode) | `llmExtract.ts:832-876` | F | Retries once with `retryModel`; rethrow if fallback fails |
| 3 | No-object text mode | `llmExtract.ts:351` | F | `generateText`; throws unless quota retry succeeds (`457-557`) |
| 4 | JSON repair (markdown fence strip) | `llmExtract.ts:603-624` | S | Strips ``` fences; if parse still fails, falls through to LLM repair |
| 5 | JSON repair (LLM) | `llmExtract.ts:627-709` | F | `experimental_repairText`; throws if repair LLM fails |
| 6 | NoObjectGeneratedError recovery | `llmExtract.ts:877-905` | B | Parses fenced JSON from error text; rethrows on parse fail |
| 7 | LLM refusal | `llmExtract.ts:943-944` | F | Throws `LLMRefusalError` |
| 8 | Terminal generateCompletions catch | `llmExtract.ts:941-951` | F | Logs and rethrows |
| 9 | Input trim (fire-0 only) | `apps/api/src/lib/extract/fire-0/llmExtract-f0.ts:221-228` | S | Trims markdown to ~80% max input tokens; sets `warning` |
| 10 | fire-0 generateObject (no quota retry) | `llmExtract-f0.ts:427` | F | Single attempt; throws (`455-459`) |
| 11 | fire-0 JSON repair | `llmExtract-f0.ts:322-377` | F | Same repair pattern as main; throws from outer catch |
| 12 | Scrape json/extract via SmartScrape wrapper | `apps/api/src/scraper/scrapeURL/lib/extractSmartScrape.ts:359` | B | First LLM call (schema + smart-scrape decision) |
| 13 | SmartScrape initial LLM failure swallowed | `extractSmartScrape.ts:373-382` | S | Catches error, logs; `extract` stays undefined → empty/partial downstream |
| 14 | SmartScrape page cap | `extractSmartScrape.ts:414-423` | S | Logs warn; only first 100 `smartScrapePages` processed |
| 15 | SmartScrape re-extract per page markdown | `extractSmartScrape.ts:473` | F | Second `generateCompletions`; uncaught → propagates to outer catch |
| 16 | SmartScrape cost limit | `extractSmartScrape.ts:485-491` | S | Sets `warning`; may return partial `extractedDataArray` |
| 17 | Auto schema from prompt (SmartScrape) | `extractSmartScrape.ts:265-279` | F | `generateSchemaFromPrompt`; throws after 3 temps (`llmExtract.ts:1515-1517`) |
| 18 | performLLMExtract entry | `llmExtract.ts:1010` | B | Scrape `json` format → `extractData` |
| 19 | Multi-page scrape json: last page only | `llmExtract.ts:1028-1030` | S | `extractedDataArray[extractedDataArray.length - 1]` only kept |
| 20 | Zero-data-retention skip json | `llmExtract.ts:973-977` | S | Skips LLM; sets `document.warning` |
| 21 | performCleanContent trim | `llmExtract.ts:1152-1159` | S | Trims to 120k tokens; may set warning |
| 22 | performCleanContent skip (output limit) | `llmExtract.ts:1162-1173` | S | Preserves original markdown; warning only |
| 23 | performCleanContent LLM | `llmExtract.ts:1258` | F | Throws on failure |
| 24 | performSummary skip empty | `llmExtract.ts:1307-1311` | S | Warning; no LLM call |
| 25 | performSummary LLM | `llmExtract.ts:1370` | F | Throws on failure |
| 26 | generateSchemaFromPrompt | `llmExtract.ts:1453-1517` | F | 3 temperature attempts then throw |
| 27 | generateCrawlerOptionsFromPrompt | `llmExtract.ts:1531-1583` | F | Same retry-then-throw pattern |
| 28 | Extract API fire-0 worker entry | `services/extract-worker.ts:59` | B | Calls `performExtraction_F0` |
| 29 | Extract sync entry | `controllers/v1/extract.ts:60` | B | Same fire-0 path |
| 30 | URL discovery LLM (fire-0) | `fire-0/url-processor-f0.ts:22` | F | `generateBasicCompletion_FO` via `generateText` |
| 31 | Schema analysis LLM (fire-0) | `fire-0/completions/analyzeSchemaAndPrompt-f0.ts:47` | B | `generateCompletions_F0` + zod parse |
| 32 | Schema analysis fallback (fire-0) | `analyzeSchemaAndPrompt-f0.ts:70-87` | S | On error → `isMultiEntity:false`; may mis-route pipeline silently |
| 33 | Should-extract gate (fire-0 multi-entity) | `fire-0/completions/checkShouldExtract-f0.ts:22` | S | LLM boolean; false → doc skipped (`extraction-service-f0.ts:429-434`) |
| 34 | Multi-entity batch extract (fire-0) | `fire-0/completions/batchExtract-f0.ts:39` | F | Direct `generateCompletions_F0`; throws to caller |
| 35 | Multi-entity per-doc timeout race | `extraction-service-f0.ts:414-481` | S | 45s timeout → `null` result, doc omitted from merge |
| 36 | Multi-entity per-doc catch | `extraction-service-f0.ts:528-534` | S | Logs error; returns `null`; job continues |
| 37 | Single-answer extract (fire-0) | `fire-0/completions/singleAnswer-f0.ts:30` | F | One LLM over concatenated docs; throws fail job |
| 38 | Extract success with partial data (fire-0) | `extraction-service-f0.ts:930-941` | S | `success:true`, `warning:undefined`, `data: finalResult ?? {}` even if URLs skipped |
| 39 | Extract scrape failure (fire-0) | `extraction-service-f0.ts:670-689` | F | `success:false`, error message |
| 40 | All URLs invalid (fire-0) | `extraction-service-f0.ts:692-713` | F | `success:false` |
| 41 | Transform merge failure (fire-0) | `extraction-service-f0.ts:578-597` | F | `success:false` |
| 42 | Worker surfaces extract failure | `extract-worker.ts:86-136` | F | Redis `failed`, webhook `EXTRACT_FAILED` |
| 43 | DLQ crash handler | `extract-worker.ts:148-165` | F | Marks extract failed with generic error |
| 44 | generateBasicCompletion (fire-1 url-processor) | `lib/extract/url-processor.ts:20` | B | Prompt rephrase / rerank prep |
| 45 | generateBasicCompletion failure → null | `url-processor.ts:67-125` | S | Returns `null`; caller keeps prior prompt (`184-194`, `313-333`) |
| 46 | Reranker LLM chunk | `lib/extract/reranker.ts:143` | B | Scores mapped URLs for extract relevance |
| 47 | Reranker chunk error → empty | `reranker.ts:182-218` | S | Failed chunk contributes `[]`; URLs dropped from extract set |
| 48 | Reranker score threshold filter | `reranker.ts:231-250` | S | URLs below 0.6 (single) / 0.45 (multi) omitted silently |
| 49 | processUrl map error → [] | `url-processor.ts:400-405` | S | Returns empty link list for that seed URL |
| 50 | Scrape document failure → null | `lib/extract/document-scraper.ts:124-131` | S | Failed scrape omitted from extract doc set (no job-level fail unless all null) |
| 51 | fire-1 batchExtract extractData catch | `completions/batchExtract.ts:126-131` | S | Logs; returns empty `extractedDataArray` |
| 52 | fire-1 multi-entity null on failure | `extraction-service.ts:545-556` | S | Same silent per-doc drop (unwired code) |
| 53 | fire-1 analyzeSchema fallback | `completions/analyzeSchemaAndPrompt.ts:100-117` | S | Same as fire-0 fallback |
| 54 | fire-1 success partial | `extraction-service.ts:1052-1063` | S | `success:true` with partial `data` (unwired) |
| 55 | Deterministic JSON LLM codegen | `lib/deterministicJson/llm/client.ts:59` | F | Throws `codegen API call failed` |
| 56 | Anchor snippet picker | `client.ts:78` | B | `pickSnippets`; parse fail → `[]` (`91-107`) |
| 57 | askLlm inner failure → null | `client.ts:142-144` | S | Any askLlm error becomes `null` in extractor sandbox |
| 58 | askLlm call budget | `client.ts:203-204` | F | Throws when `ASK_LLM_MAX_CALLS` exhausted |
| 59 | askLlm retries then throw | `client.ts:201-251` | F | 3 attempts; throw after exhaustion |
| 60 | Deterministic extract regenerate | `lib/deterministicJson/extract.ts:125-129` | F | One regeneration on sandbox failure; second failure propagates |
| 61 | Selector repair failure keeps first result | `extract.ts:105-112` | S | Logs; returns original extraction value |
| 62 | parseWithSchema coercion | `pipeline/postprocess.ts:9-14` | S | Drops unknown keys, fills required defaults, dedupes arrays (may mask missing data) |
| 63 | performDeterministicJson | `transformers/deterministicJson.ts:184` | B | Scrape `deterministicJson` format |
| 64 | Deterministic JSON failure warning | `deterministicJson.ts:193-196` | F | Sets `document.warning`; no throw; scrape still succeeds |
| 65 | Change-tracking schema extract (prev) | `transformers/diff.ts:19` | S | `extractDataWithSchema`; catch → `null` (`44-47`) |
| 66 | Change-tracking schema extract (curr) | `diff.ts:185-187` | S | Same; missing side → fallback LLM diff only |
| 67 | Change-tracking combined LLM diff | `diff.ts:195` | F | Warning on failure (`224-230`) |
| 68 | Query directQuote LLM | `transformers/query.ts:58` | B | Line-index selection |
| 69 | Query directQuote fail → null | `query.ts:95-104` | F | Warning if all models fail (`251-253`) |
| 70 | Query freeform model chain | `query.ts:150-197` | B | Up to 3 models |
| 71 | Highlights query | `query.ts:258-270` | F | Warning on failure |
| 72 | Branding LLM extract | `lib/branding/llm.ts:92` | B | `generateObject`; `strictJsonSchema:false` |
| 73 | Branding soft failure | `llm.ts:174-249` | S | Returns empty/low-confidence struct; scrape continues |
| 74 | llms.txt description LLM | `lib/generate-llmstxt/generate-llmstxt-service.ts:185` | B | Per-URL title/description |
| 75 | llms.txt URL failure skip | `generate-llmstxt-service.ts:214-223` | S | Failed URL omitted from output; job still completes |
| 76 | Deep research search-query LLM | `lib/deep-research/research-manager.ts:160` | B | Extraction-class (structured plan) |
| 77 | Deep research analysis LLM | `research-manager.ts:230` | B | NOT VERIFIED: full error path (file read partial) |
| 78 | Deep research synthesis LLM | `research-manager.ts:305` | B | NOT VERIFIED: full error path (file read partial) |
| 79 | Engpicker scrape-quality LLM | `lib/engpicker.ts:70` | B | Internal engine selection eval (not user extract API) |
| 80 | X/Twitter profile LLM | `engines/x-twitter/index.ts:514` | F | NOT VERIFIED: error surfacing to caller (read partial) |
| 81 | X/Twitter post LLM | `x-twitter/index.ts:550` | F | NOT VERIFIED: error surfacing (read partial) |
| 82 | Browser-agent LLM | `lib/scrape-interact/browser-agent.ts:343` | B | NOT VERIFIED: failure semantics (file unread) |
| 83 | Monitoring judgeChange LLM | `services/monitoring/judgeChange.ts:138` | B | Eval/monitoring, not user extraction output |

**Path count: 83**

## Completeness guarantees for callers

**None of the production paths guarantee that every page, URL, or chunk fed into the pipeline is LLM-extracted or LLM-validated.**

What callers actually get:

| Surface | Guarantee | Evidence |
|---------|-----------|----------|
| **Scrape `json` / `extract` format** | Best-effort structured object for **one scrape's markdown** (often one page). No per-field completeness proof. Input may be trimmed only in fire-0 extract path, not in scrape `performLLMExtract`. Multi-URL agent scrape keeps **last page only** (`llmExtract.ts:1028-1030`). Failures throw unless SmartScrape wrapper swallows first call (`extractSmartScrape.ts:373-382`). | `llmExtract.ts`, `extractSmartScrape.ts` |
| **`/v1/extract` (fire-0, production)** | **Partial success by design:** job returns `success:true` with merged JSON even when individual documents time out, fail scrape, fail `checkShouldExtract`, or throw during batch extract (`extraction-service-f0.ts:930-941`, `429-434`, `528-534`). URL set pre-filtered by reranker thresholds and chunk failures (`reranker.ts:231-250`, `182-218`). No post-hoc schema validation (commented-out block `803-841`). | `extraction-service-f0.ts`, `reranker.ts` |
| **`deterministicJson` format** | Cached codegen + sandbox run; LLM `askLlm` calls may return **`null` silently** (`client.ts:142-144`). Failure → `document.warning`, scrape HTTP success (`deterministicJson.ts:193-196`). `parseWithSchema` may inject defaults (`postprocess.ts:89-101`). | `deterministicJson/*` |
| **Query / summary / clean / changeTracking / branding / llms.txt** | Optional enrichments. Skip or warn on failure; **never fail-closed** on the parent scrape/job (warnings or soft defaults). | `query.ts`, `llmExtract.ts`, `diff.ts`, `branding/llm.ts`, `generate-llmstxt-service.ts` |

**Schema validation:** OpenAI `strictJsonSchema:true` on main `generateObject` (`llmExtract.ts:730-732`); AI SDK `experimental_repairText`; zod re-parse only in schema-analysis helpers. **No Ajv/JSON-Schema validation of final extract API output** (Ajv `compile` at `extraction-service-f0.ts:410` is compile-only). fire-0 uses stricter input trim; main scrape path does not trim inside `generateCompletions`.

**Retries:** Quota/rate-limit fallback model in main `generateCompletions` (`832-876`); `generateSchemaFromPrompt` / crawler-options 3-attempt loop; `askLlm` 3 attempts; reranker 2 retries per chunk; `generateBasicCompletion` rate-limit fallback. fire-0 `generateCompletions_F0` has **no** quota retry.

## Verdict on the claim(s)

**CONFIRMED (C4-style):** Firecrawl extract/scrape LLM paths allow **silent loss** of per-URL/per-chunk content while still returning success or partial JSON. Representative citations: `extractSmartScrape.ts:373-382`, `extraction-service-f0.ts:429-434`, `extraction-service-f0.ts:930-941`, `llmExtract.ts:1028-1030`, `reranker.ts:231-250`, `deterministicJson/llm/client.ts:142-144`.

**NOT VERIFIED:** Whether any path performs LLM verification of already-produced output against source (C1 negative existential); no such path found in files read.

## Coverage gaps

- `apps/api/src/lib/deep-research/deep-research-service.ts` (orchestration beyond `research-manager.ts` partial read)
- `apps/api/src/lib/scrape-interact/browser-agent.ts` (full failure paths)
- `apps/api/src/scraper/scrapeURL/engines/x-twitter/index.ts` (caller error handling above line 560)
- `apps/api/src/lib/extract/fire-0/{url-processor-f0,reranker-f0}.ts` (assumed symmetric to fire-1 reranker; not line-verified)
- `apps/api/src/lib/extract/fire-0/extraction-service-f0.ts` lines 1-399 (read partially)
- Non-`apps/api` packages (`apps/js-sdk`, `examples/`, etc.) — excluded as non-production server paths
- `lib/extract/extraction-service.ts` (fire-1): inventoried as unwired dead code; not runtime-tested

## What could still hide a counterexample

- Dynamic `require()` / transformer registration in `scraper/scrapeURL/transformers/index.ts` not fully traced
- LLM calls inside Rust (`@mendable/firecrawl-rs`) or worker subprocesses not grep'd here
- Feature flags / env-gated code paths (e.g. `MODEL_NAME`, `OLLAMA_BASE_URL`) altering provider behavior without changing line numbers
- v0 `extractorOptions` naming may map to v2 `json` format via `fromV0Combo` — mapping file not fully read
