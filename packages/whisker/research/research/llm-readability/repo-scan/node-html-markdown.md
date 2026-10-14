# Repo scan: node-html-markdown

**Does it verify LLM-readability?** **no** (README goal #2 is **human** readability of spacing, not LLM comprehension)

Scanned: local shallow clone at `packages/whisker/research/repos/node-html-markdown` (read-only, v2.0.0 layout).

## Findings

### QA model: Jest inline `expect().toBe()` exact strings

- **5** test modules, **115** `expect(` calls (`default-tags.test.ts` 21, `options.test.ts` 44, `special-cases.test.ts` 20, `table.test.ts` 18, `default-tags-codeblock.test.ts` 12).
- Primary gate: `expect(translate(html)).toBe(expected)` — slack **0** (e.g. `test/default-tags.test.ts:17-19`, `test/table.test.ts:18-20`).

### Construct-level decomposition

| File | Domain |
|------|--------|
| `test/table.test.ts` | pipe escape, padding, caption, nested-in-list |
| `test/default-tags-codeblock.test.ts` | fenced code inner whitespace |
| `test/default-tags.test.ts` | br, lists, links, headings |
| `test/options.test.ts` | 17+ option knobs with distinct expected outputs |
| `test/special-cases.test.ts` | entities, mixed-case tags, `\r\n`/`\t` |

### Hybrid anchor ladder (partial exactness)

When full `toBe` is brittle (table inside list), tests fall back to substring/regex anchors (`test/table.test.ts:141-150`):

- `expect(result).not.toContain('|\\')`
- `expect(result).toMatch(/^\* foo/)`
- `expect(result).toContain('| foo | bar |')`

This is **structural spot-check**, not olmOCR-style fact assertions or LLM read-back.

### Real-world HTML corpus: speed only, output discarded

- **87** hash-named production HTML files in `benchmark/files/` (count verified).
- `benchmark/index.js:13-24` loads files; `benchmark/index.js:48-65` times parse via callback **without inspecting markdown**.
- Wrapper explicitly drops output (`benchmark/wrapper/node-html-markdown.js:3-5`):

```3:5:packages/whisker/research/repos/node-html-markdown/benchmark/wrapper/node-html-markdown.js
module.exports = function (html, callback) {
  NodeHtmlMarkdown.translate(html);
	callback(null);
};
```

- `benchmark/execute.js:69-127`: turndown vs NHM **speed comparison only**; mean ± sd on **timing**, not quality.

### README goals vs LLM-readability

`README.md:12-23`: project goals are **(1) speed** and **(2) human readability** (clean spacing for human eyes). Published benchmarks (`README.md:31-59`) report throughput only. No LLM, RAG, or downstream QA claims.

### CI: build + Jest coverage, no quality floor on coverage

- `.github/workflows/build.yml:42-45`: `yarn run test:coverage` on Node 20/22/24.
- `jest.config.js:1-18`: `collectCoverageFrom: ["src/**/*.ts"]` — **no** `coverageThreshold`.
- Coveralls upload advisory (`build.yml:47-50`).

### Explicit absences (LLM-readability axes)

| Axis | node-html-markdown |
|------|-------------------|
| Comprehension / fact assertions | None |
| LLM-as-judge or blind read-back | None |
| Downstream field extraction (RealDocBench) | None |
| Output diff on 87-file benchmark corpus | None — timing only |
| Cross-parser output quality harness | None — speed vs turndown only |
| Threshold calibration | None — equality on inline fixtures |

Grep for `LLM`, `comprehension`, `fact assertion`, `olmocr` in `*.{ts,js,md}`: **no hits** (only README "Human Readability").

## Portable to whisker (ranked)

1. **Zero-slack exact gate on construct fixtures** — golden micro-corpus with `toBe`-grade equality for escape/table-pipe/list snippets (`test/default-tags.test.ts:17-19`, `test/table.test.ts:43`).
2. **Hybrid anchor facts** for embedded contexts — port NHM's `not.toContain` / `toMatch` / `toContain` ladder to whisker `present`/`absent`/`order` facts (`test/table.test.ts:141-150`); maps to olmOCR partial-anchor pattern without LLM judge.
3. **Construct-level test file split** — report guard failures by construct (table vs codeblock vs options), not one aggregate row per paper.
4. **Option-matrix exact baselines** — each NHM option permutation gets its own expected string (`test/options.test.ts:17-339`); whisker baseline should key by config hash when bench knobs exist.
5. **Issue-linked minimal repro metadata** on baseline rows (`test/special-cases.test.ts` issue comments; `test-fix.js` hand-run harness).
6. **Do not copy** speed-only benchmark as quality gate — keep whisker markitdown oracle; if scoring real HTML corpus, diff output/metrics, not wall-clock (`benchmark/wrapper/node-html-markdown.js:3-5`).

Not portable for Lane 3: NHM tests **synthetic HTML** with author-written expected markdown, not verified WG21 facts.

## Cross-check vs redteam report

Reference: `packages/whisker/research/redteam/node-html-markdown.md`.

| Redteam claim | Scan verdict |
|---------------|--------------|
| 5 Jest modules, inline `expect().toBe()`, zero golden snapshots | **Confirms** (5 `.ts` files; 115 `expect(` calls). |
| ~87 real HTML benchmark files | **Confirms** (87 files in `benchmark/files/`). |
| Benchmark discards output, measures speed only | **Confirms** (`benchmark/wrapper/node-html-markdown.js:3-5`, `benchmark/index.js:54-62`, `execute.js:82-87`). |
| Hybrid anchors in table-in-list | **Confirms** (`test/table.test.ts:141-150`). |
| Construct split (tables, codeblocks, lists, options, special-cases) | **Confirms** (5 test files). |
| Option permutation matrix in `options.test.ts` | **Confirms** (44 expects in options suite). |
| No `coverageThreshold` in jest config | **Confirms** (`jest.config.js:1-18`). |
| Coveralls advisory | **Confirms** (`build.yml:47-50`). |
| Cross-parser harness compares speed not output | **Confirms** (`execute.js:13-20`, `69-127`). |
| No committed snapshot refresh ritual (inline strings only) | **Confirms**. |
| Verifies LLM-readability | **Not claimed** — README "Human Readability" is spacing aesthetics; scan confirms **no** LLM comprehension layer. |

No material contradictions.
