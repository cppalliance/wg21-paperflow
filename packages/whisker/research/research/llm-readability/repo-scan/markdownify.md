# Repo scan: markdownify

**Does it verify LLM-readability?** **no**

Scanned: local shallow clone at `packages/whisker/research/repos/markdownify` (read-only, `develop` branch layout).

## Findings

### QA model: inline exact-string asserts, no external snapshot files

- **325** `assert` statements across **8** test modules (`test_conversions.py` 187, `test_escaping.py` 49, `test_tables.py` 30, `test_lists.py` 17, `test_args.py` 16, `test_advanced.py` 16, `test_custom_converter.py` 6, `test_basic.py` 4).
- Pattern: `assert md(html) == '<expected markdown>'` with **zero tolerance** (e.g. `tests/test_conversions.py:7`, `tests/test_tables.py:289`).
- Refresh = edit inline strings in the PR; no `--update` / snapshot directory.

### Test harness pins comparison defaults

```6:9:packages/whisker/research/repos/markdownify/tests/utils.py
def md(html, **options):
    options = {"strip_document": None, **options}
    return MarkdownConverter(**options).convert(html)
```

Production default differs from test harness (`tests/test_args.py:30-34`: bare `markdownify()` strips document; `md()` preserves `\n\n` boundaries).

### Modality-split + option-matrix coverage

| Module | Concern | Evidence |
|--------|---------|----------|
| `test_tables.py` | pipe tables, colspan, thead/tbody | `:288-321` |
| `test_escaping.py` | `*`, `_`, `#`, `\|`, list markers | `:6-77` |
| `test_lists.py` | nested OL/UL, start attrs | `:44-89` |
| `test_conversions.py` | links, headings, code, blockquote, br | `:7+` |
| `test_args.py` | strip/convert whitelists | `:9-34` |
| `test_advanced.py` | comments, custom tags | — |
| `test_custom_converter.py` | extensibility hooks | — |

Full table suite duplicated under `table_infer_header=True` and `False` (`tests/test_tables.py:288-321`).

**Multi-accept ambiguity** when whitespace is under-specified: `assert ... in ['foo  bar', 'foo bar']` (`tests/test_conversions.py:11`).

### CI: pytest + flake8 + mypy, no comprehension layer

- `tox.ini:11-14`: `pytest`, `flake8`, `restructuredtext-lint`.
- `.github/workflows/python-app.yml:27-29`: tox on push/PR; separate job runs `mypy` (`:50-51`).
- No LLM calls, no fact JSONL, no downstream extraction eval, no numeric metrics (TEDS/NID/etc.).

### Explicit absences (LLM-readability axes)

| Axis | markdownify |
|------|-------------|
| Comprehension / fact assertions | None |
| LLM-as-judge or blind read-back | None |
| Downstream consumability benchmark | None |
| Golden files on disk | None — all expectations inline |
| `xfail` / expectedFailure for known-bad | None in tests (grep) |
| Calibration / ROC | None — implicit FPR = 0 on fixtures |

Grep for `LLM`, `comprehension`, `readability`, `downstream`, `olmocr` in repo: **no hits**.

## Portable to whisker (ranked)

1. **Freeze `bench_config` in committed baseline** — mirror `utils.md()` forcing stable document boundaries before any diff; fail on config drift unless `--update` (`tests/utils.py:6-8`; redteam actionable item).
2. **Modality-stratified failure reporting** — table vs escaping vs list regressions localized by test module; map to whisker construct tags or facts sidecars.
3. **Option-matrix baselines** — duplicate critical rows under each bench knob (`table_infer_header` pattern at `tests/test_tables.py:306-321`) → baseline keyed by `(pid, config_hash)`.
4. **Exact golden micro-corpus tier** (slack 0) beneath metric guard — markdownify proves metric-only gates miss string-level regressions.
5. **Acceptable-output sets** for harness meta-tests (`tests/test_conversions.py:11`) where full equality is brittle.
6. **CI bundle**: flake8 + mypy on gate code (`.github/workflows/python-app.yml:50-51`) — low priority for whisker guard.

Not portable for Lane 3: inline asserts encode **developer-chosen** markdown, not verified paper facts or table neighbor relations.

## Cross-check vs redteam report

Reference: `packages/whisker/research/redteam/markdownify.md`.

| Redteam claim | Scan verdict |
|---------------|--------------|
| ~320 inline asserts, zero external snapshots | **Confirms** — **325** asserts counted across 8 modules (within rounding). |
| Exact expected Markdown, zero slack | **Confirms** (`tests/test_conversions.py:7`, `tests/test_tables.py:289`). |
| `utils.md()` forces `strip_document=None` | **Confirms** (`tests/utils.py:6-8`). |
| Production vs test default divergence documented | **Confirms** (`tests/test_args.py:30-34`). |
| Table suite under `table_infer_header` True/False | **Confirms** (`tests/test_tables.py:288-321`). |
| Multi-accept ambiguity (`in ['foo  bar', 'foo bar']`) | **Confirms** (`tests/test_conversions.py:11`). |
| Modality-split test modules | **Confirms** (8 files by concern). |
| No xfail / expectedFailure | **Confirms** (none found). |
| tox flake8 on CI | **Confirms** (`tox.ini:13`). |
| mypy in CI | **Confirms** (`.github/workflows/python-app.yml:50-51`). |
| No calibration | **Confirms**. |
| Verifies LLM-readability | **Not claimed** — scan confirms **no** comprehension/downstream layer. |

No material contradictions.
