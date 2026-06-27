VERDICT: BUILD (stdlib difflib) - CLI corpus lane; pytest plugins mis-fit scoring architecture

# Build vs Buy: Byte-/Near-Exact Golden Output Lane for whisker

Research date: June 2026. Scope: Tier-3 #1 from `notes/redteam-synthesis.md` (exact golden tier beneath fuzzy metrics). **No whisker source was modified.**

Evidence sources: `packages/whisker/src/whisker/{guard.py,__main__.py}`, `notes/{cross-repo-qa-research.md,redteam-synthesis.md}`, `research/redteam/*.md` (28-repo adversarial reads; line citations point at paths under `research/repos/<name>/` from pinned clones used during red-team, not present in this workspace snapshot).

---

## 1. Current state: no exact lane; closest pattern is `guard --update`

### Confirmed absence

| Artifact | Present? | Notes |
|----------|----------|-------|
| `<pid>.expected.md` (committed candidate snapshot) | **No** | `Glob **/*.expected.md` under `packages/whisker/` → 0 files |
| Byte/near-exact compare of tomd output | **No** | Scoring path compares candidate vs `<pid>.gt.md` reference inside `run_bench` / `metrics.py`; nothing snapshots the **candidate** for regression |
| Exact-lane CLI verb | **No** | Entry point documents four verbs only: default QA, `bench`, `guard`, `calibrate` (`__main__.py:10-17`) |
| pytest snapshot dependency | **No** | `pyproject.toml` lists apted, levenshtein, lxml, markitdown, numpy, scipy, pylatexenc, paperstore, tomd only |

Whisker today has **three regression layers**, none exact on output text:

1. **Fuzzy metrics** (`metrics.py`, `bench.py`): NID, TEDS, MHS, overall on `(candidate, reference)` pairs.
2. **Per-paper metric guard** (`guard.py`): committed JSON baseline of rounded axis scores; `--update` refresh (`__main__.py:331-334`, `371-381`).
3. **Corpus-mean bench baseline** (`bench --baseline`): aggregate `overall` only (`__main__.py:305-317`).

Corpus loading is shared and CLI-native: `_load_corpus_pairs` walks `*.gt.md`, pulls staged candidate via `backend.get_paper_md(pid)` (`__main__.py:247-262`). Ground truth is reference markdown; **expected candidate output is never committed or compared**.

### Closest existing pattern: `whisker guard --update`

`guard.py` already implements the **refresh ritual** and **lib-returns-data / CLI-persists** split the exact lane should mirror:

- Library: `baseline_from_rows`, `diff_rows` return `GuardReport` / dict payloads only (`guard.py:35`, `321-365`).
- CLI: `--update` writes baseline JSON and exits 0; diff mode reads baseline, emits report, sets exit code (`__main__.py:371-381`, `397+`).
- Contract in baseline: `kind`, `schema_version`, embedded slack/floors (`guard.py:54`, `189-197`).
- New/missing paper semantics: `STATUS_NEW`, `missing` list, optional `--fail-on-new` (`guard.py:288-292`, `357-358`, `__main__.py:343-345`).

Red-team synthesis explicitly deferred the exact tier as Tier-3 #1 (~17/28 repos): metrics catch semantic drift; exact lane catches **silent formatting regressions** metrics smooth over (`notes/redteam-synthesis.md:32-36`).

---

## 2. Candidate comparison

| Candidate | License (verified) | pytest coupling | Refresh mechanism | Determinism | Normalization support |
|-----------|-------------------|-----------------|-------------------|-------------|------------------------|
| **stdlib `difflib` + committed files** | PSF (stdlib) | **None** | Custom CLI flag (mirror `guard --update`) | Full control: explicit normalize-then-compare in one module | **Yes**: implement LF/CRLF, trailing WS, optional `rstrip()` policy in whisker code (matches html2text, pymupdf4llm) |
| **syrupy** | MIT (v5+); Apache-2.0 (≤4.x) | **Hard**: snapshots live under `__snapshots__/` beside **test modules**; requires `snapshot` fixture in `@pytest` tests | `pytest --snapshot-update` (never in CI) | Good inside pytest run; snapshot IDs tied to test node names | Extension hooks (Amber/SingleFile); no corpus-dir story; line-ending policy is yours but wired through pytest |
| **pytest-regressions** | MIT | **Hard**: `datadir` / `data_regression` fixtures; expected files colocated with tests | `pytest --force-regen` (one failure) or `--regen-all` | Deterministic for fixture tests | File compare helpers; normalization is ad hoc in test code |
| **pytest-golden** | MIT (PyPI 1.0.1; not Apache-2.0) | **Hard**: `@pytest.mark.golden_test("glob")`; YAML golden files next to test file | `pytest --update-goldens` | YAML round-trip via ruamel.yaml; good for structured blobs, awkward for multi-KiB markdown per WG21 paper | None built-in; equality is Python `==` on loaded YAML strings |

### Architectural misfit (all three pytest plugins)

Whisker's golden corpus is:

- A **directory of data files** (`<pid>.gt.md`), not parametrized test cases.
- Scored through **`whisker bench|guard --corpus DIR`**, often against **paperstore-staged** `<pid>.md`, not inline test fixtures.
- Intended for **CI invocation as a CLI gate** alongside (not inside) unit tests.

Pytest snapshot plugins assume: write a test → assert → snapshot file names derive from **test function + parametrization**. Adapting that to a CLI-driven corpus requires either (a) thin pytest wrappers that shell out to whisker and re-import snapshot machinery, or (b) duplicating corpus discovery in tests. Both violate the minimalism ladder and duplicate `guard`'s already-correct CLI pattern.

Converter repos in the red-team set **do not** use pytest snapshot plugins for their primary exact lane; they use **committed output files + explicit non-CI refresh flags** (see §3).

---

## 3. Per-repo evidence: exact lane + refresh ritual

Citations are from red-team deep-reads (`research/redteam/<repo>.md`) against pinned clones under `research/repos/`. Pattern: **committed expected output + normalize + exact compare + human refresh never in CI**.

| Repo | Exact compare | Normalization before diff | Refresh ritual (local only) | Primary citation |
|------|---------------|---------------------------|----------------------------|------------------|
| **pandoc** | Full stdout / AST golden; `expected == actual` after normalizers | Strip `\r` (Windows); format-specific XML/docx normalizers | `make test TESTARGS='--accept'`; CI never `--accept` | `Old.hs:380-408`, `402-403`; `Makefile:50-55`; `CONTRIBUTING.md:272-279` |
| **html2text** | `actual.rstrip() == expected.rstrip()` per `.html`/`.md` pair | `cleanup_eol()` CRLF→LF; `.gitattributes` LF | Hand-edit `.md` goldens in PR (no CLI bless) | `test_html2text.py:14-21`, `191`, `225-233` |
| **turndown** | `t.equal(output, expected)` zero slack | Normalization inside converter; harness compares raw `textContent` | Hand-edit `<pre class="expected">` in `test/index.html` | `attendant.js:66-74`, `39-40` |
| **markdownify** | ~320 inline `assert md(html) == '...'` | Test harness `strip_document=None` in `tests/utils.py:6-8` | Edit assert strings in PR | `test_conversions.py:7`; `utils.py:6-8` |
| **html-to-markdown-go** | `goldie.Assert(t, run, []byte(output))` byte-exact | Normalization in converter; `\r\n` collapse tests | `go test -update`; CI never `-update` | `internal/tester/goldenfiles.go:63-78`; `README.md:387-393` |
| **html-to-markdown-py** | Oracle `actual != expected` on `.snap` files | Raw output is contract (no pre-diff hook) | `htmbench oracle --bless` | `oracle.rs:161-168`; `main.rs:265-267` |
| **pymupdf4llm** | `assert md == expected` on `*.expected.md` | `expected.replace('\r', '')` before compare | Hand-add/update `*.expected.md`; failures print `difflib.unified_diff` | `test_sce-150.py:13,21,32`; `test_370.py:35-42,45` |
| **mdream** | `toBe` / Vitest snapshots / file snapshots | `trimEnd()` on stream vs string parity | `vitest -u` locally; not in CI workflow | `fixture-parity.test.ts:54-55`; `fetch.test.ts:27-33` |
| **unstructured** | `diff -ru` on committed metrics/output trees | JSON→clean-text; quote/whitespace prep | `OVERWRITE_FIXTURES=true` (workflow_dispatch only; not `ci.yml`) | `check-diff-evaluation-metrics.sh:46-73`; `check-diff-expected-output.sh:48-67` |
| **node-html-markdown** | Inline `toBe` expected strings in Jest | None separate (expected in test source) | Edit TypeScript expects | `test/default-tags.test.ts:17-19` (red-team) |

**Cross-cutting (~17/28):** Tier-3 synthesis lists pandoc `--accept`, html2text/turndown/markdownify/mdream/node-html-markdown/html-to-markdown-{go,py}, pymupdf4llm `.expected.md` CRLF-normalized (`notes/redteam-synthesis.md:32-34`). `notes/cross-repo-qa-research.md:48-60` maps this family to whisker Phase 4a (`--update`) + Phase 4c (committed golden markdown corpus).

**Whisker-relevant normalization precedents:**

- **CRLF**: pymupdf4llm `expected.replace('\r', '')` (`test_sce-150.py:13`); html2text `cleanup_eol()` (`test_html2text.py:14-21`); pandoc `\r` strip (`Old.hs:389-391`).
- **Trailing whitespace**: html2text `.rstrip()` both sides (`test_html2text.py:191`); mdream `trimEnd()` for stream path (`fixture-parity.test.ts:54-55`).
- **Failure UX**: pymupdf4llm prints `difflib.unified_diff` on mismatch (`test_370.py:35-42`).

---

## 4. Verdict: BUILD (stdlib difflib)

**Recommendation:** Implement the exact lane in whisker with **stdlib `difflib` + committed `<pid>.expected.md` files + a CLI `--update` refresh**, structurally parallel to `guard`, **not** a pytest snapshot plugin.

### Why BUILD fits whisker

1. **Same architecture as peer converters.** The red-team consensus lane is committed output files + explicit bless flag, not syrupy/regressions/golden. whisker already copied the refresh half via `guard --update`.
2. **CLI/corpus is the product surface.** Bench and guard score `--corpus DIR` with paperstore candidates; exact lane should attach to that path, not require new pytest parametrization over N papers.
3. **Minimalism ladder.** `difflib.unified_diff` + `Path.read_text`/`write_text` is a few lines; pytest plugins add deps (syrupy, pytest-datadir, ruamel.yaml, testfixtures) for orchestration whisker already has in `__main__.py`.
4. **Invariants.** Library returns diff report data; CLI owns writes and exit codes. Deterministic normalization lives in one named function, versioned in baseline metadata (same pattern as `GUARD_BASELINE_KIND` / `schema_version`).
5. **pytest stays for unit tests.** `tests/test_guard.py`-style tests can assert the normalize/compare helper without making the **corpus gate** pytest-native. Optional: unit-test the comparator; do not gate WG21 corpus through pytest snapshot IDs.

### Why not BUY

| Plugin | Blocker |
|--------|---------|
| syrupy | Snapshots keyed to test AST; poor fit for `<pid>.expected.md` beside corpus data; refresh is `pytest --snapshot-update`, not `whisker … --update` |
| pytest-regressions | Datadir convention tied to test module paths; same corpus/CLI mismatch |
| pytest-golden | YAML-centric; multi-page markdown in YAML is painful; still pytest-parametrized |

If BUY were forced: the least-bad hack is a **meta-test** that runs `whisker golden --corpus …` and compares hashes, which reimplements BUILD inside pytest without plugin value.

### Proposed BUILD sketch (spec only; not implemented)

**Verb:** `whisker golden` (or `whisker guard --exact-md`; separate verb keeps fuzzy guard unchanged).

**Corpus layout** (alongside existing guard corpus):

```
corpus/
  P1234R0.gt.md          # reference (existing)
  P1234R0.expected.md     # committed candidate snapshot (new)
```

**Flow:**

1. `_load_corpus_pairs` (or sibling) yields `(pid, candidate, ref)`.
2. **Normalize** both sides with a single function, e.g. `normalize_for_exact_lane(text) -> str`:
   - Unicode NFC (optional, document if enabled)
   - `\r\n` / `\r` → `\n`
   - Policy flag: `--strip-trailing-ws` (default on, html2text/pymupdf4llm precedent) vs strict bytes
   - Final newline: enforce single `\n` EOF or preserve (pick one; document in baseline `normalization_version`)
3. **Compare:** `normalize(candidate) == normalize(expected.read_text())` for each pid with an expected file.
4. **On fail:** return data structure with `difflib.unified_diff(..., lineterm="")` lines per pid; CLI logs and exit 5.
5. **Refresh:** `--update` writes `normalize(candidate)` to `<pid>.expected.md` for all scored pairs (or `--pid` subset); refuse when `CI=true` (docling/unstructured precedent).
6. **Membership:** mirror guard: fail if baseline lists pid missing from run; `--fail-on-new` if `*.gt.md` exists without `.expected.md`.
7. **Baseline sidecar (optional):** JSON manifest `golden-manifest.json` with `kind`, `schema_version`, `normalization_version`, `tomd_version`, per-pid sha256 of normalized text (PyMuPDF version-keyed lesson for toolchain bumps).

**Near-exact variant:** if strict bytes are too brittle for full WG21 papers, start with a **micro-corpus** (red-team recommendation across pandoc/html2text/go/py) where exact is strict; keep full corpus on fuzzy guard only. Near-exact = normalized equality, not Levenshtein (still deterministic, still no LLM).

**Integration with guard:** run order in CI: `golden` (exact) → `guard` (fuzzy axes). Independent failures; shared `--corpus` and `--update` ergonomics.

---

## 5. Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| **Brittleness on full WG21 corpus** | High | Phase 4c micro-corpus first; exact strict only where tomd output is stable; fuzzy guard remains primary on large labeled set |
| **Normalization drift** | High | Pin `normalization_version` in manifest; changing normalize function requires `--update` + PR review |
| **tomd / dependency bumps** | High | Record `tomd.__version__` in manifest; version-keyed expected files (PyMuPDF parallel-golden pattern) |
| **Windows CRLF in committed files** | Medium | `.gitattributes` `* text eol=lf` on `*.expected.md`; normalize `\r` before compare (pymupdf4llm/html2text) |
| **Improvement blocked until refresh** | Medium | By design (pandoc/html2text); intentional output changes need `--update` PR, same as guard |
| **Duplicate logic with guard** | Medium | Share corpus loader, `--fail-on-new`, CI guard; extract small `golden.py` module mirroring `guard.py` shape |
| **Candidate source ambiguity** | Medium | Document that expected snapshots stage **paperstore `<pid>.md`**, same as bench; re-run tomd before `--update` |
| **Large diff noise in PRs** | Medium | Cap micro-corpus size; unified_diff in report only, not auto-commit of huge files without review |
| **pytest plugin FOMO** | Low | Plugins add no capability whisker lacks if BUILD copies converter-repo pattern already validated by ~17/28 peers |

---

## References (in-repo)

- `packages/whisker/notes/redteam-synthesis.md` (Tier-3 #1)
- `packages/whisker/notes/cross-repo-qa-research.md` (§2 golden + refresh)
- `packages/whisker/research/redteam/{pandoc,html2text,turndown,markdownify,html-to-markdown-go,html-to-markdown-py,pymupdf4llm,mdream,unstructured,node-html-markdown}.md`
- `packages/whisker/src/whisker/guard.py`, `__main__.py`
