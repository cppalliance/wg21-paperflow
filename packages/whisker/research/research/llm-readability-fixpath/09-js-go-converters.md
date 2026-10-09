# 09 - js-go-converters

**Verdict:** usable-with-conditions (+ 1 sentence: OUR Lane 3 comprehension stack — verified facts, blind readback, cell-neighbor geometry — is strictly ahead of all four converters, which gate conversion fidelity only; adoptable value is the html-to-markdown-go construct-isolated golden micro-corpus pattern plus mdream structural-invariant ideas, not their LLM-marketing claims as CI proof.)
**Confidence:** high

Evidence note: shallow clones at `packages/whisker/research/repos/{html-to-markdown-go,node-html-markdown,turndown,mdream}` read 2026-07-09. Prior scans extended, not re-filed: `research/llm-readability/repo-scan/{html-to-markdown-go,node-html-markdown,turndown,mdream}.md`. Fix-path anchors: `00-baseline.md`.

## Findings

- [CRITICAL] **Golden-file wave should copy html-to-markdown-go's construct-isolated paired corpus, not turndown/NHM inline suites or mdream's paper fixtures alone.** Go organizes goldens as flat `testdata/GoldenFiles/<name>.in.html` + `<name>.out.md` per plugin domain: `plugin/commonmark/testdata/GoldenFiles/{blockquote,bold,code,heading,image,link,list,metadata}.in.html` (8), `plugin/table/testdata/GoldenFiles/{basics,col_row_span,contents,email,parents}.in.html` (5), `plugin/strikethrough/testdata/GoldenFiles/strikethrough.in.html` (1) — 14 pairs total. Harness resolves `./testdata/<TestName>/` from the test name (`goldenfiles.go:45`), pairs only `.in.html`/`.out.md`, rejects subdirs and orphan files (`goldenfiles.go:27-34`), byte-exact via `goldie.Assert` (`goldenfiles.go:69-78`). Turndown packs **147** cases into one monolithic `test/index.html` with inline `<pre class="expected">` (`test/index.html:12-14`); NHM uses **115** inline `expect().toBe()` across 5 Jest files with no committed snapshots (`test/table.test.ts:18-20`). mdream uses a **fixed 3-fixture** integration list (`fixture-parity.test.ts:9-13`: wikipedia-small, github-markdown-complete, wikipedia-largest) for parity/size gates, not per-construct goldens. **Whisker should adopt:** `corpus/micro/<construct>/` paired snippets (html-to-markdown-go layout) **under** the existing pid-level triple (`corpus/README.md:6-13`: `<pid>.expected.md` + `<pid>.facts.jsonl` + optional `.gt.md`), with strata tags from `corpus_tools.classify_paper` (`corpus_tools.py:70-94`: table/html_table/display_math/code_heavy/footnotes/images). Impact: closes formatting regressions Lane 2 NID/TEDS miss without replacing Lane 3 facts.

- [HIGH] **mdream markets LLM readability; CI tests exact strings and structural ratios, not comprehension or token efficiency.** README claims "#1 Token Optimizer" and "Optimized for LLMs" (`README.md:7,26,35`). `withMinimalPreset()` strips nav/footer/forms/aside and enables frontmatter + isolateMain + tailwind + filter plugins (`packages/js/src/preset/minimal.ts:21-51`) — token reduction via content filtering, not tested against downstream Q&A. Token benchmarks (`bench/token-compare.ts:15-40` heuristic `countTokens`, `:69-79` compares mdream/turndown/NHM/go) and `bench/README.md:79` ("measures speed only, not output quality or token efficiency") are **developer tooling, not CI gates** (`test.yml` runs `pnpm test` only per prior scan). Structural CI checks: `minOutputKB * 1024` byte floor (`fixture-parity.test.ts:10-12,38-41`), string/stream parity after `trimEnd()` (`fixture-parity.test.ts:50-55`), heading count+level match (`fixture-parity.test.ts:89-98`), link count ±2% (`fixture-parity.test.ts:112-113`). **Whisker does not test:** token-count reduction vs HTML, nav/footer stripping, main-content isolation, streaming/batch parity, or heading/link-count structural floors on converted WG21 markdown. Impact: mdream's LLM pitch is orthogonal to our use case unless we add advisory token/structure metadata; Lane 3 facts remain the honest comprehension gate (`facts.py:8-32`, `00-baseline.md:29-39`).

- [HIGH] **llms.txt generation exists in mdream but is not relevant to WG21 paper conversion.** Engine-agnostic artifact builder `generateLlmsTxtArtifacts` in `packages/js/src/llms-txt.ts:34-118` assembles site-level `llms.txt` / `llms-full.txt` from crawled `ProcessedFile[]` (title, url, description links). Consumed by `@mdream/crawl` (`packages/crawl/src/crawl.ts:6`) and `@mdream/action` (`packages/action/src/index.ts:5,122`). **No WG21 paper analogue:** we ingest discrete committee papers, not multi-page sites; whisker corpus is pid-stratified (`corpus_tools.py:97-139`), not path-mirrored crawl output. Impact: skip porting llms.txt; if needed later, treat as a separate mailing-index artifact, not a conversion QA layer.

- [HIGH] **Go fuzzing covers one internal invariant; whisker should extend the pattern to table-grid properties, not copy go's scope.** Sole native fuzz target: `FuzzReplaceAnyWhitespaceWithSpace` asserts regex vs hand-rolled whitespace helper agree on arbitrary strings (`collapse/whitespace_test.go:156-168`). **No** converter-output fuzz, **no** markdown validity fuzz (confirmed: only one `Fuzz` in repo). Properties `facts.py`/`tables.py` should assert (currently untested at property level; partial coverage in `test_facts.py` canaries):
  1. **Idempotent whitespace collapse** — `_WS_RE.sub(" ", x)` twice equals once (mirrors go's regex≡function invariant).
  2. **`split_pipe_cells` round-trip** — joining split cells with `|` reproduces row modulo edge pipes (`tables.py:34-41`).
  3. **Fence isolation** — random/markdown with fenced ``` blocks never yields pipe tables from interior pipes (`tables.py:55-61`; canary at `test_facts.py:543`).
  4. **Grid neighbor consistency** — for every parsed cell, `_neighbor_value` inverse directions agree when in-bounds (`facts.py:348-356`).
  5. **HTML grid rectangularity** — each row in `parse_html_tables` has consistent column count after parse (`tables.py:80-135`; **colspan/rowspan not expanded**, unlike go).
  Impact: property tests catch parser drift; go only fuzzes a collapse helper, but the **pattern** (two implementations must agree) is the portable idea.

- [MED] **Table adversarial cases from converter tests map to new corpus strata and canary facts; several exceed our HTML parser.** html-to-markdown-go golden + unit coverage: invalid `colspan` attrs (`plugin/table/testdata/GoldenFiles/col_row_span.in.html:4-7`), colspan/rowspan mirror/empty behaviors (`table_test.go:54-203`), empty rows + skip-empty-rows (`table_test.go:230-354`), presentation tables (`table_test.go:545-621`), cell newlines (`table_test.go:623-690`). NHM: pipe escape (`test/table.test.ts:42-44`), empty cells (`test/table.test.ts:102-115`), nested tables flattened (`test/table.test.ts:61-64`), mismatched row widths (`test/table.test.ts:66-100`), table-in-list hybrid anchors (`test/table.test.ts:117-151`). Turndown: **zero** `<table` fixtures in `test/index.html` (prior scan confirmed). **Whisker already has:** decoy-table all-occurrence (`facts.py:376-404`, `test_facts.py:478-499`), HTML table cell checks (`test_facts.py:516-529`), pipe-in-code fence skip (`test_facts.py:543`). **Add as strata/canaries:**
  | Case | Source | Whisker gap |
  |------|--------|-------------|
  | Empty body cells | NHM `table.test.ts:102-115` | draft scaffold picks first data row (`corpus_tools.py:177-190`) — add explicit empty-cell neighbor fact |
  | colspan/rowspan grid | go `col_row_span.in.html`, `table_test.go:54-203` | `tables.py:80-135` ignores span attrs — cells collapse; need **HTML micro-fixtures + facts** documenting expected neighbor after tomd emit |
  | Nested table flatten | NHM `table.test.ts:61-64` | no canary — add `table` fact on outer cell after nested collapse |
  | Table-in-list context | NHM `table.test.ts:117-151` | hybrid `present`/`absent` anchors, not full grid |
  | Invalid colspan values | go `col_row_span.in.html:4-7` | parser robustness — property test + optional golden |
  Impact: table comprehension is whisker's lead axis (`00-baseline.md:25-28`); these cases harden the lead against WG21 SPEC_TABLE/NB_BALLOT HTML.

- [MED] **NHM hybrid anchor ladder is the portable pattern for embedded contexts where byte-exact goldens fail.** When table-in-list output is brittle, NHM falls back to `not.toContain('|\\')`, `toMatch(/^\* foo/)`, `toContain('| foo | bar |')` (`test/table.test.ts:141-150`) instead of full `toBe`. Maps directly to whisker `present`/`absent`/`order` facts on `surface: raw` (`facts.py:79-80,257-265`) for list-wrapped tables. Impact: complements strict table facts without abandoning zero-slack micro-goldens elsewhere.

- [LOW] **Turndown dual-path (DOM + string) and option-matrix fixtures are secondary adoptables.** Each of 147 cases runs `(DOM)` and `(string)` via turndown-attendant (`attendant.js:72-79` per prior scan); **22** carry `data-options` permutations (`test/index.html:101-104`). Useful for tomd HTML-path parity (staged file vs raw string), not LLM comprehension. Impact: cheap structural backstop beneath Lane 1 golden.

## False-pass hypothesis

**Theirs:** mdream passes `fixture-parity.test.ts:38-41` when output exceeds `minOutputKB` but a critical table row is permuted — byte floor does not inspect cell geometry. NHM nested-table test accepts flattened `| nested | abc |` (`test/table.test.ts:61-64`) with no assertion that inner grid structure survives. Go table gate with `SpanBehaviorEmpty` leaves colspan holes empty (`table_test.go:64-79`) — a "pass" on golden string while semantic cell count drops.

**Ours:** A `table` fact checking only `cell` + `right` passes when the cell and right neighbor are correct but a **down** neighbor was dropped (unless separately asserted). `parse_html_tables` treats `<td colspan="3">` as one cell (`tables.py:107-109`), so neighbor facts on spanned WG21 tables may pass on the wrong grid shape if the anchor cell text is unique. Mitigation: multi-direction neighbors per critical cell (N5040 pattern per `00-baseline.md:48-52`) + html_table stratum micro-fixtures for colspan-heavy papers (`corpus_tools.py:83-84`).

## False-fail hypothesis

**Theirs:** mdream cross-engine heading parity fails on benign entity-decoding differences despite comment at `fixture-parity.test.ts:93` ("content may differ"). Go `TestOptionFunc_ColRowSpan` byte-exact compare fails on padding whitespace drift (`table_test.go:220-225`).

**Ours:** `table_heading` filter skips the correct table when header text differs by whitespace/case (`facts.py:388-390`), false-failing on duplicate cell values. `math` facts may fail on display-vs-inline delimiters — mitigated by `_fold_display_math_delims` (`facts.py:213-234`, `00-baseline.md:29`). Fuzzy `max_diffs` on table neighbors can false-fail when padding changes cell tokenization but semantics hold (`facts.py:368-369`).

## Adoption candidate

**Corpus pattern: html-to-markdown-go `internal/tester/goldenfiles.go` (`getInputFiles` at `:19-42`, `GoldenFiles` at `:44-78`), MIT License (`LICENSE:1-21`).** Port as `packages/whisker/corpus/micro/<construct>/` with paired `.in.html` + `.expected.md`, construct-isolated suites mirroring `plugin/commonmark/testdata/GoldenFiles/` and `plugin/table/testdata/GoldenFiles/`, wired into Lane 1 `golden.py` or a new micro runner with the same orphan-file hygiene. **Not** turndown's monolithic `test/index.html` (147 cases, zero tables) or NHM's inline-only strings. Secondary function (if one code unit required): mdream `trimEnd()` normalization before parity compare (`fixture-parity.test.ts:54-55`, MIT) for whisker dual-path scoring — advisory only, not comprehension proof.

## What would change my mind

Finding committed CI gates in mdream or html-to-markdown-go that run blind LLM Q&A, per-cell fact assertions, or token-efficiency floors on converted markdown (not manual `bench/token-compare.ts`) — would elevate mdream from "marketing + structural CI" to a competing comprehension methodology and might flip the adoption candidate toward their preset/filter pipeline.

---

## Q1–Q5 direct answers (indexed to baseline)

### Q1. Which corpus ORGANIZATION pattern should our golden-file wave copy?

**Copy html-to-markdown-go's plugin/construct-isolated paired files** (`plugin/*/testdata/GoldenFiles/*.in.html` + `.out.md`, harness `goldenfiles.go:45,27-34,69-78`), **layered above** whisker's existing pid-centric corpus (`corpus/README.md:6-13`) with **strata tags** from `corpus_tools.classify_paper` (`corpus_tools.py:46-94`). Do **not** copy turndown's single `test/index.html` blob or NHM's inline-only Jest strings as the primary layout. Borrow mdream's **fixed named fixture list** (`fixture-parity.test.ts:9-13`) only for optional full-page integration tier, not as the micro-golden backbone.

### Q2. mdream LLM readability: what does it do that we don't test?

| mdream mechanism | Evidence | Whisker gap |
|------------------|----------|-------------|
| Token reduction preset | `minimal.ts:21-51`, `bench/token-compare.ts:15-40` | No token-count gate on converted papers |
| Content filtering (nav/footer/forms) | `minimal.ts:32-46` | No assert that WG21 boilerplate is absent/present |
| Main-content isolation | `minimal.ts:30` isolateMain plugin | No isolation QA |
| Structural invariants | `fixture-parity.test.ts:89-113` | No heading-count/link-count floors in guard |
| Streaming parity | `fixture-parity.test.ts:50-55` | N/A (batch conversion only) |
| llms.txt artifacts | `llms-txt.ts:34-118` | **Not relevant** to pid-level paper pipeline |

None of these are validated by LLM comprehension in mdream CI; whisker's blind readback (`readback.py`, `00-baseline.md:30-36`) remains the only empirical LLM probe — out of CI by design.

### Q3. Fuzz invariants to adopt for facts.py/tables.py

From go `FuzzReplaceAnyWhitespaceWithSpace` (`whitespace_test.go:156-168`): **two implementations must agree on all inputs.** Extend to whisker:
1. Whitespace normalization idempotence (`facts.py:268-269`, `tables.py:29`).
2. `split_pipe_cells` / pipe-row consistency (`tables.py:34-41`).
3. Fenced-code exclusion from pipe-table detection (`tables.py:55-61`).
4. `_neighbor_value` directional consistency (`facts.py:348-356`).
5. Parsed grid row-width consistency (`tables.py:80-135`); add colspan/rowspan cases once parser behavior is specified.

### Q4. Table adversarial cases to add

**Yes — as corpus strata (`html_table`, `table`) and canary facts.** Priority imports from go `col_row_span.in.html` + `table_test.go:54-203` (colspan/rowspan/empty), NHM `table.test.ts:102-115` (empty cells), `:61-64` (nested flatten), `:117-151` (table-in-list). Turndown contributes **nothing** (no table fixtures). Wire through `draft_facts_scaffold` table branch (`corpus_tools.py:176-206`) with explicit empty-cell and span-heavy templates.

### Q5. Single highest-leverage adoptable

**html-to-markdown-go construct-isolated golden corpus pattern** — `internal/tester/goldenfiles.go:19-78`, **MIT**. One module to study/port the hygiene contract; populate `corpus/micro/table/` from `plugin/table/testdata/GoldenFiles/` and `corpus/micro/commonmark/` from commonmark goldens as the first wave. Whisker Lane 3 facts stay authoritative for comprehension; micro-goldens catch formatting regressions the four repos actually gate well.
