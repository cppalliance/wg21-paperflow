# Repo scan: harlan-zw/mdream

**Does it verify LLM-readability?** **no** (partial: token-efficiency scripts + exact/snapshot structural CI; no comprehension, fact assertions, or LLM-as-judge eval)

Scanned: shallow clone at `packages/whisker/research/repos/mdream` (read-only, 2026-07-06).

---

## Findings

1. **[HIGH] README markets "LLM-optimized" output; CI never tests LLM comprehension.** Claims "#1 Token Optimizer" and "Optimized for LLMs" (`README.md:7`, `README.md:35`). Examples pipe md into Claude/GPT CLIs (`README.md:107-127`) as usage demos, not verified eval. CI runs `pnpm run test` only (`test.yml:211-212`); no read-back or fact-assertion suite.

2. **[HIGH] Primary CI QA is exact equality and Vitest snapshots, not downstream consumability.** Micro-cases use `expect(markdown).toBe('...')` (`headings.test.ts`, `spacing.test.ts`). Splitter and template tests use `toMatchSnapshot()` / `toMatchFileSnapshot()` (`splitter.test.ts`, `fetch.test.ts:27-33`). Any formatting change fails until local `vitest -u`; not in CI workflow.

3. **[HIGH] Dual-path parity gates (batch vs stream, JS vs Rust) are structural, not semantic.** String vs stream must match after `trimEnd()` (`fixture-parity.test.ts:50-56`). Cross-engine: output length ratio within 1% (`fixture-parity.test.ts:76-78`), heading count+level match (`fixture-parity.test.ts:89-98`), link count within 2% (`fixture-parity.test.ts:112-113`). Simple HTML requires byte-identical JS/Rust output (`fixture-parity.test.ts:132-134`).

4. **[MED] Per-fixture size floors catch near-empty output without prior baseline.** `minOutputKB * 1024` byte floor on both string and stream paths (`fixture-parity.test.ts:10-12`, `38-48`). Analogous to whisker needing per-paper `min_output_bytes`.

5. **[MED] Token benchmarks measure compression vs competitors, not LLM understanding.** `bench/token-compare.ts` counts approximate tokens (whitespace/punctuation heuristic, `token-compare.ts:15-40`) across turndown/node-html-markdown/html-to-markdown. Rust `token_cost.rs` bench compares default vs minimal+clean preset token counts (`token_cost.rs:1-60`). **Not in CI**; developer/marketing tooling only.

6. **[MED] Speed benchmark explicitly excludes output quality.** `bench/README.md:79`: "Output quality: This benchmark measures speed only, not output quality or token efficiency." `compare.bench.ts` measures ops/sec only. Token efficiency is a separate manual script, not a release gate.

7. **[MED] Reading-order checks are local `indexOf` ordering, not fact recovery.** Streaming test: `# Title` before `Paragraph` (`streaming.test.ts:31-33`). Same class as markitdown's `find()` chains; does not prove an LLM can answer questions about content.

8. **[LOW] No ROC, labeled corpus, or LLM-as-judge.** All thresholds hand-set (1% length, 2% links, exact micro-cases). Confirms redteam: whisker `calibrate.py` is ahead on formal threshold methodology; mdream offers no competing fitter.

---

## Portable to whisker (ranked)

1. **`trimEnd()` normalization before parity compare** — explicit comment that streaming flush may add trailing whitespace (`fixture-parity.test.ts:54-55`). Apply wherever whisker diffs two scoring paths (re-score vs cached sidecar, PDF vs HTML candidate).

2. **Structural invariant baselines** — cheap regex counts with tight slack: heading count+level (`fixture-parity.test.ts:89-98`), link count ±2% (`fixture-parity.test.ts:112-113`). Add optional baseline fields alongside NID/TEDS/MHS.

3. **Per-paper `min_output_bytes` floor** — catastrophic empty/near-empty backstop (`fixture-parity.test.ts:10-12`, `41`). Independent of metric floors.

4. **Dual-path parity sub-gate** — same pid scored twice must match on deterministic axes after normalization. Pattern from string/stream parity (`fixture-parity.test.ts:50-56`).

5. **Closed corpus discipline** — fixed fixture list; no silent pass for uncovered papers. Maps to whisker `--strict-corpus` / fail on `STATUS_NEW`.

6. **NOT portable as comprehension proof** — token-compare scripts (`bench/token-compare.ts`, `crates/core/benches/token_cost.rs`) measure character/token reduction vs HTML and competitors. Token efficiency ≠ LLM fact recovery (see Q2/Q5 web cards: pipe-table lookup ~52%, structural collapse common). Use at most as advisory metadata, never as Lane 3 substitute.

---

## Cross-check vs redteam report

| Redteam claim (`packages/whisker/research/redteam/mdream.md`) | Verdict | Evidence |
|---|---|---|
| Gates on committed exact markdown / snapshots, not scalar deltas | **Confirmed** | `fixture-parity.test.ts:50-56`, Vitest snapshots in `splitter.test.ts`, `fetch.test.ts:27-33` |
| Dual-path parity (string vs stream, JS vs Rust) | **Confirmed** | `fixture-parity.test.ts:50-56`, `62-134` |
| Per-fixture `minOutputKB` floors | **Confirmed** | `fixture-parity.test.ts:10-12`, `38-48` |
| Ordered-position reading checks (`indexOf`) | **Confirmed** | `streaming.test.ts:31-33` |
| No ROC fitting; hand-set thresholds | **Confirmed** | `fixture-parity.test.ts:76-78`, `112-113`; no calibrate module |
| Bench suite measures ops/sec only | **Confirmed** | `bench/README.md:79`, `compare.bench.ts:1-13` |
| Top portable: `trimEnd()` before equality | **Confirmed** | `fixture-parity.test.ts:54-55` |

**Contradictions:** none found. Redteam correctly classifies mdream as a golden/snapshot regression repo with token-efficiency marketing collateral, not an LLM-readability verification stack. mdream's token benchmarks are explicitly out of CI and out of the speed bench's quality scope.
