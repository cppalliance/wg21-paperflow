# Repo scan: html-to-markdown-py

**Does it verify LLM-readability?** **no**

Scanned: local shallow clone at `packages/whisker/research/repos/html-to-markdown-py` (kreuzberg-dev/html-to-markdown / html-to-markdown-rs, read-only).

QA is **byte-exact output regression** (116 oracle snapshots × 4 option permutations), **tier byte-equality** property tests, **prescan structural** integration tests, **perf guardrails** per fixture group, and auto-generated **e2e substring** checks. Marketing copy mentions feeding plain text to LLMs (`readme_templates/partials/_plain_text_output.md:110`) but there is no LLM eval, fact corpus, or comprehension benchmark.

## Findings

### Oracle snapshot gate (primary quality contract)

- **116** committed `.snap` files, **29** HTML fixtures in `tools/benchmark-harness/fixtures/` (counts verified at scan time) → 29 × 4 `Permutation`s (`oracle.rs:37-42`).
- Strict string equality on converter output (`oracle.rs:160-168`: `actual != expected` → fail with line diff).
- Bless vs verify: `htmbench oracle --bless` writes snapshots (`oracle.rs:90-113`, `main.rs:265-267`, `main.rs:282-305`); compare path hard-fails on mismatch (`main.rs:291-302`, `main.rs:322`).
- Four profiles per fixture: Default, NoImages, NoMetadata, AtxClosed (`oracle.rs:24-71`).
- Known core panics on `kimbrain.html` / `rbloggers.html` caught and treated as skip, not fail (`oracle.rs:10-14`, `oracle.rs:103-111`, `oracle.rs:151-158`).

### Perf guardrails (throughput regression, not content QA)

- `guardrails.json:3-10`: per-group `max_regression_pct` (e.g. `clean_large` 5%, `adversarial` 30%).
- `main.rs:215-233`: relative ms regression vs committed `baselines/baseline.json`; missing baseline → warn and skip (`main.rs:210-212`).
- `schema.rs:35-40`: baseline records git `sha`, `host`, `created_at` — audit metadata whisker guard lacks.
- `output_bytes` recorded per run (`schema.rs:23-24`) but **not** compared in oracle/guardrail gates.

### Tier-1 correctness property tests (byte identity, not semantics)

- `tier1_byte_equality_test.rs:96-165`: Tier1 output must equal Tier2 byte-for-byte when Tier1 succeeds; `KNOWN_TIER2_QUIRK_FIXTURES` allowlist (`tier1_byte_equality_test.rs:107-122`).
- `tier1_property_test.rs:1-54`: invariant — Tier1 either bails or matches Tier2; **never** returns wrong `Ok` output on 50+ hand-curated snippets.
- 23 `tier1_*_test.rs` files under `crates/html-to-markdown/tests/` (router bail variants, tables, entities, etc.) — structural/regression coverage, not fact recovery.
- `prescan_test.rs:14-56`: prescan signal detection (head range, custom elements, etc.).

### Fixture corpus organization

- `fixtures/groups.toml:1-10`: group tags (`clean_small` … `adversarial`) drive perf thresholds.
- `fixture.rs:89-105`: `find_ungrouped()` detects HTML files absent from manifest.
- `survey.rs:16-67`: feature survey (CDATA, custom elements, bare `<`, table-no-tbody) — corpus coverage hygiene, not LLM QA.

### E2e substring anchors (weak proto-comprehension)

- Auto-generated Python e2e tests assert substrings in output, e.g. `assert "[AUDIO: podcast.mp3]" in result.content` and `assert "Listen to this:" in result.content` (`e2e/python/tests/test_visitor.py:38-40`).
- These are **must-contain** checks on toy HTML, not verified paper facts, table neighbors, or math surfaces.

### CommonMark spec vectors (dormant in this clone)

- `packages/python/tests/commonmark_spec.json` exists (~5200 lines of spec examples) but **no references** found anywhere else in the repo (search for `commonmark_spec`: zero hits). Orphan data in shallow clone — not an active gate.

### CI wiring (oracle/bench not in checked-in GitHub workflow)

- `ci-rust.yaml:109-113` runs `task rust:test:ci` only.
- `.task/languages/rust.yml:66-75`: `rust:test:ci` uses `cargo llvm-cov … --exclude html-to-markdown-bench` — **benchmark harness excluded**.
- `task bench:oracle` / `bench:compare` defined in `.task/workflows/benchmark.yml:15-23` but **not** invoked from any file under `.github/workflows/` in this clone.
- `CHANGELOG.md:380-384` claims PR CI runs `task bench:oracle && task bench:run && task bench:compare` — **contradicts** current checked-in workflow set (may reflect upstream/main drift or unreleased config).

### Explicit absences (LLM-readability axes from `00-baseline.md` / Q1–Q3)

| Axis | html-to-markdown-py |
|------|---------------------|
| Comprehension / fact assertions (olmOCR-style) | None |
| LLM-as-judge or blind read-back | None |
| Downstream field-QA on converted markdown (RealDocBench / ParseBench text rules) | None |
| Table neighbor / math layout semantic checks | None beyond byte snapshots |
| LLM eval of plain-text mode | Mentioned in README only (`_plain_text_output.md:110`), not tested |

## Portable to whisker (ranked)

1. **Per-group regression slack map** mirroring `guardrails.json` — stratify `axis_slack`/floors by corpus band (WG21 multi-column / adversarial vs clean). Evidence: `guardrails.json:3-10`, `main.rs:215-218`.
2. **Oracle bless ritual + committed snapshots** per `(pid, conversion_profile)`; CI compare never blesses. Evidence: `oracle.rs:90-113`, `.task/workflows/benchmark.yml:15-23`. Whisker follow-on: md5/sha256 per profile if full snapshots too heavy (redteam recommendation).
3. **Four-profile permutation matrix** (default + metadata/heading/code-block variants). Evidence: `oracle.rs:24-42`, `main.rs:281-305`.
4. **Known-failure / panic skip registry** in baseline (`expected_failure` entries). Evidence: `oracle.rs:10-14`, `oracle.rs:127-134`.
5. **Ungrouped fixture detection** beside GT corpus. Evidence: `fixture.rs:89-105`.
6. **Feature survey for corpus coverage gaps** (tables without tbody, CDATA, bare `<`). Evidence: `survey.rs:16-67` — maps to whisker corpus-coverage skeptic persona (#21).
7. **Tier bail-or-match property** — fast path must not emit wrong bytes; adopt as optional tomd fast-path gate. Evidence: `tier1_property_test.rs:43-53`.
8. **E2e must-contain anchors → whisker `present` facts** on high-risk micro-fixtures (proto-Lane-3, not a substitute). Evidence: `e2e/python/tests/test_visitor.py:38-40`.

Not portable for Lane 3 at scale: oracle snapshots encode **blessed converter output**, not human-verified WG21 paper facts (olmOCR / whisker `facts.py` in Q1).

## Cross-check vs redteam report

Reference: `packages/whisker/research/redteam/html-to-markdown-py.md`.

| Redteam claim | Scan verdict |
|---------------|--------------|
| 116 snapshots × 4 permutations, byte-exact oracle | **Confirms** (116 `.snap`, 29 fixtures; `oracle.rs:161-168`). |
| `guardrails.json` per-group `max_regression_pct` | **Confirms** (`guardrails.json:3-10`, `main.rs:215-218`). |
| Oracle panic skip for kimbrain/rbloggers | **Confirms** (`oracle.rs:10-14`, `oracle.rs:103-111`). |
| `KNOWN_TIER2_QUIRK_FIXTURES` allowlist | **Confirms** (`tier1_byte_equality_test.rs:107-122`). |
| Missing snapshot → hard fail; missing baseline → warn/skip | **Confirms** (`oracle.rs:136-141`, `main.rs:210-212`). |
| `find_ungrouped()` hygiene | **Confirms** (`fixture.rs:89-105`). |
| E2e substring / structural anchors | **Confirms** (`test_visitor.py:38-40`). |
| No ROC calibration (hand-set guardrails only) | **Confirms**. |
| Bench CI via `benchmark.yml` / CHANGELOG | **Partially contradicts** — tasks exist (`.task/workflows/benchmark.yml:15-23`) but checked-in `.github/workflows/ci-rust.yaml` excludes `benchmark-harness` (`rust.yml:72-74`); no `bench:oracle` step found in workflows. |
| `packages/python/tests/commonmark_spec.json` as active gate | **Contradicts** — file present, zero references in repo; no runner found in shallow clone. |
| Verifies LLM-readability | **Not claimed by redteam** — redteam compares guard/calibrate to htmbench; scan confirms **no** LLM-readability layer. |
