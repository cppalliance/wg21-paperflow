# Repo scan: turndown (LLM-readability verification)

**Repo:** `packages/whisker/research/repos/turndown` (mixmark-io/turndown v7.2.4, shallow clone, read-only)  
**Scan date:** 2026-07-06  
**Question:** Does turndown verify that HTML→markdown output is LLM-readable?

## Does it verify LLM-readability?

**No.** Turndown gates **147 inline HTML fixture goldens** on strict `output === expected` (via `turndown-attendant`), plus separate API unit tests. There are **no** fact assertions, comprehension corpora, LLM judges, downstream extraction QA, or readability benchmarks. Exact string match catches formatting regressions humans notice (escaping, `<br>` trailing spaces) but does not test semantic recoverability.

---

## Findings

1. **[HIGH] Fixture-based golden harness — zero comprehension.** `test/turndown-test.js:1-10` loads `turndown-attendant` against `test/index.html`. Attendant selects every `.case`, reads `.input` / `<pre class="expected">`, and asserts `t.equal(output, expected)` twice per case — DOM node path and HTML-string path (`turndown-attendant/attendant.js:12-14`, `38-40`, `72-79`; source verified from package v0.0.3, matching `package.json:29`). **147** `<div class="case">` fixtures in `test/index.html` (not 100). Repo grep for `comprehension`, `LLM`, `fact`, `readability`, `benchmark` returned **no matches**.

2. **[HIGH] Dual entry point per fixture — structural parity, not LLM QA.** Each case runs `(DOM)` via `turndown(inputElement)` and `(string)` via `turndown(inputElement.innerHTML)` (`attendant.js:72-79`). Catches parser/DOM-boundary bugs; does not verify that an LLM can answer questions about the markdown.

3. **[MED] Config permutations inline (`data-options`).** **22** cases carry `data-options='{"headingStyle":"atx"}'` (and similar) so the same HTML is gated under alternate converter options (`test/index.html:101-104`, `:142-145`, `:153-156`; 22 `data-options` matches). Attendant parses JSON into `TurndownService` constructor args (`attendant.js:38-40`).

4. **[MED] Exact whitespace / escaping contracts encoded in goldens.** Examples: `<br>` → two trailing spaces + LF (`test/index.html:147-150`); heading escape when `===` would be setext (`:91-94`); img alt markdown escapes (`:174-177`). These are **byte-level** assertions — closer to Lane 1 golden stability than Lane 3 comprehension, but they gate edges NID/TEDS may miss (redteam §4, confirmed).

5. **[MED] Separate unit-test layers — no LLM lane.** `test/internals-test.js:5-34` unit-tests private `edgeWhitespace` with NBSP cases and a **32768-char perf bound** (`:27-30`). `test/turndown-test.js:19-179` covers API (`null`/`undefined` throws, `addRule`, `keep`, `remove`). `package.json:57` runs `standard`, then `internals-test.js`, then `turndown-test.js` — no comprehension step.

6. **[MED] No table fixtures.** Grep for `<table` in `test/index.html` returned **0 matches**. Turndown does not gate table markdown at all; whisker **leads** on table QA via TEDS and Lane 3 `table` facts (00-baseline).

7. **[LOW] No calibration / thresholds.** Operating point is implicit edit distance zero (`attendant.js:74`). No ROC, no labeled good/bad corpus — same lesson as pandoc/redteam §2.

---

## Portable to whisker (concrete, ranked)

1. **Dual-path golden harness: staged DOM/file + raw HTML string.** Adopt turndown-attendant's `(DOM)` + `(string)` pattern for whisker's HTML micro-corpus (`attendant.js:72-79`). Cheap; catches tomd/parser boundary bugs metric guard will not see. **Not** LLM-readability — structural parity only.

2. **Inline config matrix in fixtures (`data-options` → `(fixture_id, options_hash)`).** Same HTML, multiple converter configs, each with its own committed expected markdown (`test/index.html:101-104`). Map to baseline rows keyed by `(pid, config_id)` so option changes cannot pass on aggregate metrics alone.

3. **Exact-match micro-corpus beneath fuzzy bench guard.** Turndown's 147-case pattern is the hard backstop redteam §1.1 describes: zero slack on escaping, NBSP, `<br>` spaces, link styles. Complements whisker Lane 1/Lane 2; does **not** replace Lane 3 fact assertions.

4. **Internal helper tests + perf smoke bound.** `internals-test.js` style for whisker normalization helpers (e.g. table grid parser, `_math_surface`) with adversarial whitespace and a large-input timeout — meta-tests on scoring code, not document comprehension.

5. **Not portable as LLM-readability:** fact JSONL, blind read-back, tapetum LLM lane, downstream field QA — turndown has none. Lane 3 (`facts.py`) remains the only adopted comprehension pattern in our stack.

---

## Cross-check vs redteam report (`packages/whisker/research/redteam/turndown.md`)

| Redteam claim | Scan verdict | Evidence |
|---------------|--------------|----------|
| 100 inline HTML case-table goldens | **Contradicted (count)** | **147** `class="case"` divs in `test/index.html` at v7.2.4 |
| Byte-exact `output === expected`, zero slack | **Confirmed** | `attendant.js:74`; fixture structure `test/index.html:12-14` |
| Dual `(DOM)` + `(string)` tests per case | **Confirmed** | `attendant.js:72-79` (node_modules not installed in clone; verified via package dep + upstream v0.0.3 source) |
| 22 `data-options` permutations | **Confirmed** | 22 matches in `test/index.html` |
| No calibration / exact operating point | **Confirmed** | No threshold code; strict equality only |
| No tables in corpus | **Confirmed** | 0 `<table` in `test/index.html` |
| `.github/workflows/test.yml` CI never auto-updates goldens | **Unverified in clone** | `.github/` absent from shallow checkout; `package.json:57` confirms local test script only |
| Dual-path as top portable detail | **Confirmed** | Still #1 portable item for whisker HTML micro-corpus |
| Redteam scope is guard/calibrate, not LLM-readability | **Confirmed** | Redteam structural QA claims hold; this scan adds explicit **no LLM-readability** verdict |

**New vs redteam:** Fixture count corrected to 147; attendant.js verified from upstream when `node_modules/` missing; explicit statement that turndown's exact goldens test **formatting contracts**, not olmOCR-style fact recovery or Q3 downstream QA.
