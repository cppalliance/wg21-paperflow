# Repo scan: Firecrawl

**Does it verify LLM-readability?** **partial**

Scanned: local shallow clone at `packages/whisker/research/repos/firecrawl` (read-only).

Firecrawl markets "LLM-ready output" (`README.md:56`) but does **not** run olmOCR-style deterministic fact assertions, comprehension benchmarks, or snapshot gates on markdown. Quality control is **scrape fidelity** (substring anchors, metadata, structural PDF shadow metrics) plus **sparse downstream extract tests** where an LLM reads scraped content and returns schema-shaped JSON. That is a consumability *proxy*, not a dedicated markdown-readability proof.

## Findings

### Marketing vs measured claim

- README: "LLM-ready output: Clean markdown, structured JSON..." (`README.md:56`).
- Code search: zero uses of `comprehension`, `LLM-ready`, or `llm-ready` under `apps/api/src`; only incidental "readability" in branding/deep-research prose (`lib/branding/processor.ts:105`, `lib/deep-research/research-manager.ts:337`).

### Primary markdown QA: substring anchors (not comprehension)

- **124** test lines matching both `markdown` and `toContain` / `not.toContain` under `apps/api/src` (runtime count; top file `scrapeURL.test.ts`).
- Engine matrix replays the same scrape checks across four engines (`scrapeURL.test.ts:24-37`, `describe.each(testEngines)`).
- Representative anchors:
  - Must include: `expect(out.document.markdown).toContain("Firecrawl Test Site")` (`scrapeURL.test.ts:55`).
  - Must exclude after `excludeTags`: `not.toContain("Hartley Brody 2023")`, `not.toContain("[FAQ](/faq/)")` (`scrapeURL.test.ts:142-143`).
  - PDF title phrase: `toContain("Broad Line Radio Galaxy")` on arXiv PDF scrape (`scrapeURL.test.ts:366`).
  - Unicode CJK anchor in snips (`__tests__/snips/v1/scrape.test.ts:160-162`).
- Snips E2E also checks `response.markdown?.length > 0` and format wiring, not semantic recovery (`__tests__/snips/v2/scrape-formats.test.ts:36-38`, `217-218`).
- Go html-to-md service: substring containment on converted markdown (`apps/go-html-to-md-service/handler_test.go:157-162`).

These are **surface presence/absence** checks on curated test URLs. They do not test table neighbor semantics, reading order, math fidelity, or blind fact recovery (whisker Lane 3 / olmOCR-bench).

### Metadata, HTTP, and transform axes (separate from body comprehension)

- Title, og* fields, `statusCode`, `sourceURL` gated in scrapeURL tests (`scrapeURL.test.ts:56-71`, `162-257`).
- HTML transform include/exclude: `transformHtml` tests `toContain` / `not.toContain` on filtered HTML (`lib/__tests__/html-transformer.test.ts:322-323`, `352-357`).

### PDF shadow comparison: structural fidelity, logging-only in prod

- Joint tier rule: `lenRatio >= 0.8 && numberPreservationRatio >= 0.9` → `good`; wider band → `acceptable`; else `poor` (`shadowComparison.ts:54-61`).
- Helpers: `extractNumbers` via `\d+(?:\.\d+)?`, `countTables` via markdown separator rows (`shadowComparison.ts:16-24`).
- Unit tests cover tier boundaries (`__tests__/shadowComparison.test.ts:39-139`).
- **Production path logs only:** `comparePdfOutputs` runs async under `PDF_SHADOW_COMPARISON_ENABLE` and emits `shadowLogger.info`; it does **not** fail the scrape (`engines/pdf/index.ts:523-559`). Not a CI comprehension gate.

### AB cross-version compare: telemetry, not CI gate

- Post-`parseMarkdown` Jaccard word-set similarity; 5% variance threshold (`ab-test-comparison.ts:5-6`, `60-67`, `18-31`). Warn/info logs only; no test assertions in-repo.

### LLM extract + JSON schema: downstream consumability proxy (RealDocBench-adjacent)

**Runtime validation (shape, not semantic gold corpus):**

- Scrape/json format: `generateObject` with `jsonSchema(schema)`, `strictJsonSchema: true` (`llmExtract.ts:730-737`, `346-347` feeds `document.markdown` into prompt).
- Extract service imports `Ajv` (`extraction-service.ts:21-22`); `ajv.compile(multiEntitySchema)` before batch extract (`extraction-service.ts:467`).
- Deterministic-json path: sandbox extractor then `parseWithSchema(value, jsonSchema)` (`deterministicJson/extract.ts:89`; `pipeline/postprocess.ts:9-14` remaps keys/coerces nulls, no semantic fact checks).

**Tests (sparse, live-web, mostly API plumbing + weak semantics):**

- Snips extract: schema fields exist, types correct, `is_open_source === true` on test site (`__tests__/snips/v1/extract.test.ts:49-53`).
- Json/extract format backward compat: `userId === 1` from static `/example.json` URL (`json-extract-format.test.ts:51-54`); heading extract only `toBeDefined` (`json-extract-format.test.ts:84`).
- V2 json format with schema: `response.json` is object, no field gold (`scrape-formats.test.ts:217-218`).
- E2E extract (`e2e_extract/index.test.ts`): fuzzy roster checks (`gotItRight > 1` for authors, `founders`; `pciDssCompliance === true`; exact `Eric Ciarla` name `:281`; exact delayed content `:337-338`). One test commented-out / no asserts (`:174-176`). Requires running API + keys.
- **No** fixed-extractor corpus over Firecrawl's **own** markdown output scored per-field like RealDocBench (`05-web.md` Q3). Extract validates the **product feature**, not markdown QA at scale.

### Snapshot / eval harness

- **0** `toMatchSnapshot` / `matchSnapshot` under `apps/api/src` (runtime grep).
- CI default gate: `pnpm harness pnpm test:snips` on engine × proxy × search × ai × nuq matrix (`test-server.yml:15-30`, `264-265`; `package.json:22`).
- On-demand external eval: `#scrape-quality-eval` dispatches to `firecrawl/scrape-evals` repo (`scrape-evals.yml:9-69`); not in default PR path.
- Post-deploy prod benchmark: `eval_run.py` POST to external experiment API (`eval-prod.yml:34-36`; script has no local scoring logic).

### What Firecrawl does **not** do (vs whisker Lane 3 / olmOCR)

| Capability | Firecrawl | Whisker / olmOCR |
|------------|-----------|------------------|
| Deterministic fact assertions on markdown | No | `facts.py` + corpus |
| Table neighbor / order / math surface checks | No (PDF table *count* only in shadow) | olmOCR `TableTest`, whisker `table`/`order`/`math` |
| Human-verified fact provenance gate | No | `checked == verified` |
| LLM-as-judge in QA loop | Extract **is** LLM, but not used to grade markdown CI | tapetum_llm advisory only |
| Closed comprehension corpus | Test URLs in source code | 2 papers (+ expansion planned) |

## Portable to whisker (ranked)

1. **RealDocBench-style fixed extractor on tomd markdown** (highest comprehension signal): adopt Firecrawl's *pattern* (schema + LLM read of converted md + per-field gold), not their live-web snips. Fixed model, frozen prompts, typed `gold_dict` per corpus PID; schema validation = necessary but insufficient (mirror `json-extract-format.test.ts:51-54` + `e2e_extract/index.test.ts:337-338` strict cases). Keep out of whisker scoring loop or gate only on deterministic post-parse checks; aligns with `05-web.md` Q3 RealDocBench card.

2. **Substring must-include / must-not anchors** (124 markdown lines): maps directly to whisker `present` / `absent` facts (`scrapeURL.test.ts:55`, `142-143`). Redteam already flagged; highest-volume Firecrawl QA pattern.

3. **PDF shadow joint tier** (`lenRatio` + `numberPreservation` + table count): portable as auxiliary guard for PDF papers (`shadowComparison.ts:54-61`). Redteam ACTIONABLE-NOW; note prod is log-only, whisker would need explicit fail-on-`poor`.

4. **Multi-path matrix** (engine × source family): stratify guard baselines by `(pid, source_kind)` (`scrapeURL.test.ts:24-37`; `test-server.yml:15-30`).

5. **Metadata/front-matter contract checks**: title/status/front-matter fields as guard axes (`scrapeURL.test.ts:56-71`).

6. **External eval dispatch hook**: optional CI trigger to out-of-repo benchmark (`scrape-evals.yml`); low priority for whisker core.

7. **Not portable as comprehension proof:** AB Jaccard logging (`ab-test-comparison.ts`), extract snips with fuzzy `gotItRight` thresholds (`e2e_extract/index.test.ts:45`), json format tests that only assert `toBeDefined`.

## Cross-check vs redteam report

Reference: `packages/whisker/research/redteam/firecrawl.md`.

| Redteam claim | Scan verdict |
|---------------|--------------|
| 124× `markdown…toContain` / `not.toContain` in `apps/api/src` | **Confirms** (exact line count via repo scan). |
| Engine matrix in `scrapeURL.test.ts:24-37` | **Confirms**. |
| CI matrix engine × proxy × search × ai × nuq (`test-server.yml:15-30`, `264-265`) | **Confirms**. |
| PDF shadow joint tiers (`shadowComparison.ts:54-61`) | **Confirms**; scan adds: **prod shadow is log-only**, not fail gate (`engines/pdf/index.ts:523-559`). |
| Metadata / HTTP status axes | **Confirms** (`scrapeURL.test.ts:56-71`, `162-257`). |
| Go handler substring checks (`handler_test.go:157-162`) | **Confirms**. |
| AB 5% Jaccard (`ab-test-comparison.ts:5-6`, `67`) | **Confirms**; telemetry only. |
| `#scrape-quality-eval` → external repo (`scrape-evals.yml:9-69`) | **Confirms**; not default CI. |
| `eval-prod.yml` + `eval_run.py` | **Confirms**; external API, no in-repo scoring. |
| No metric baseline refresh ritual | **Confirms**; expectations live in test source. |
| Firecrawl does not ROC-calibrate | **Confirms**; fixed engineering constants. |
| Implied: substring QA = scrape regression, not LLM comprehension | **Confirms**; no olmOCR-class bench; extract tests are downstream product tests, not markdown comprehension corpus. |

**Nuances not in redteam:** (1) zero snapshot tests; (2) "LLM-ready" is README marketing only; (3) schema-validated extract reads markdown in-process (`llmExtract.ts:346-347`) but is **not** wired as markdown QA gate; (4) total `.toContain(` in `apps/api/src` is **506** (124 are markdown-specific lines).

No material contradictions with the redteam survey. Scan tightens verdict: Firecrawl **partially** addresses downstream consumability via extract+schema, but **does not** verify LLM-readability of markdown the way whisker Lane 3 or RealDocBench do.
