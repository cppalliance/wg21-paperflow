# Repo scan: html2text

**Does it verify LLM-readability?** **no**

Scanned: local shallow clone at `packages/whisker/research/repos/html2text` (read-only).

## Findings

### QA model: committed golden pairs, byte-exact after normalization

- **74** paired fixtures: `test/*.html` + sibling `test/*.md` (count verified at scan time).
- Auto-discovery via glob; missing `.md` fails at open time in `get_baseline()` (`test/test_html2text.py:26-27`, `225-233`).
- Compare ritual: `cleanup_eol()` then `.rstrip()` on both sides, strict equality (`test/test_html2text.py:14-21`, `187-191`, `213-214`, `221-222`).
- LF policy: `.gitattributes:1` (`* text eol=lf`).

### Three entry points over the same goldens

| Suite | Evidence |
|-------|----------|
| Library `HTML2Text.handle()` | `test_html2text.py:173-191` |
| CLI subprocess `python -m html2text` | `test_html2text.py:194-214` |
| Functional `html2text.html2text()` | `test_html2text.py:217-222` |

Filename prefixes drive **20+ option permutations** (unicode_snob, bypass_tables, pad_tables, google_doc, etc.) via `generate_testdata()` (`test_html2text.py:32-151`).

### Stateful re-entry and edge-case tests (not golden corpus)

- Memleak / state reset: `test/test_memleak.py:8-26` (issues #13).
- Determinism across repeated `handle()`: `test/test_newlines_on_multiple_calls.py:6-12` (issue #163).
- Callback API: `test_html2text.py:236-247`.

### CI: structural unit tests + coverage, no comprehension layer

- `tox.ini:10-12`: `pytest --cov=./ --cov-report=xml`.
- `.github/workflows/main.yml:45-95`: matrix py39–py313, Codecov upload with `fail_ci_if_error: true`.
- No LLM calls, no fact JSONL, no downstream extraction benchmark, no reading-order semantics beyond what goldens encode.

### Explicit absences (LLM-readability axes from `00-baseline.md` / Q1–Q3)

| Axis | html2text |
|------|-----------|
| Comprehension / fact assertions | None |
| LLM-as-judge or blind read-back | None |
| Downstream LLM consumability (ParseBench / RealDocBench style) | None |
| Table neighbor / math layout checks | Only if encoded in a golden string |
| Threshold calibration / ROC | None — implicit operating point is **100% exact match** |

README and code contain no references to LLM readability, RAG, or downstream QA (grep for `LLM`, `comprehension`, `readability` in source: no hits; only GPL "downstream recipients" in `COPYING`).

## Portable to whisker (ranked)

1. **Golden micro-corpus tier**: paired `<fixture>.html` → expected `.md`, `cleanup_eol` + `.rstrip()`, slack **0** — beneath whisker metric guard (closes formatting regressions metrics miss). Evidence: `test_html2text.py:14-21`, `191`.
2. **Fail-closed on corpus growth**: new input without committed golden hard-fails — adopt for whisker `STATUS_NEW` pids when baseline exists.
3. **EOL + whitespace normalization contract** at gate boundary: port `cleanup_eol` + `.gitattributes eol=lf` so golden diffs match CI on Windows.
4. **Multi-entry-point parity**: run guard/bench through CLI and library on a micro-corpus (`test_html2text.py:173-222`).
5. **Option-matrix goldens**: filename-prefix pattern maps to separate baselines per converter flag (`test_html2text.py:32-151`).
6. **Stateful re-entry tests**: repeated conversion must be bit-identical (`test_memleak.py`, `test_newlines_on_multiple_calls.py`) — relevant if tomd reuses converter instances.

Not portable for Lane 3: html2text goldens test **author-chosen expected strings**, not human-verified paper facts or table neighbor geometry (olmOCR pattern in Q1).

## Cross-check vs redteam report

Reference: `packages/whisker/research/redteam/html2text.md`.

| Redteam claim | Scan verdict |
|---------------|--------------|
| 74 `.html`/`.md` golden pairs, byte-exact after `cleanup_eol` + `.rstrip()` | **Confirms** (`test_html2text.py:14-21`, `191`; 74 HTML files counted). |
| Zero slack; exact match is the threshold | **Confirms** (`test_html2text.py:191`). |
| Fail-closed on new `.html` without paired `.md` | **Confirms** (`get_baseline()` opens `.md` at `225-233`). |
| Three entry points (library, CLI, function) | **Confirms** (`test_html2text.py:173-222`). |
| Filename-driven option permutations | **Confirms** (`test_html2text.py:32-151`). |
| No calibration / ROC | **Confirms** — no labeled thresholds anywhere. |
| No explicit missing-fixture fail (deleted `.html` shrinks coverage silently) | **Confirms** — glob-only discovery, no inventory check. |
| guard missing-pid hard-fail is stricter than html2text | **Confirms** — html2text has no baseline JSON missing-pid concept. |
| Codecov gate in CI | **Confirms** (`.github/workflows/main.yml:90-95`). |
| Stateful memleak / repeated-call tests | **Confirms** (`test_memleak.py`, `test_newlines_on_multiple_calls.py`). |
| Verifies LLM-readability | **Not claimed by redteam** — redteam compares regression gates to whisker guard; scan confirms **no** LLM-readability layer exists. |

No material contradictions.
