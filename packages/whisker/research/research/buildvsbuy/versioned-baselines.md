VERDICT: BUILD-IMPROVE - stdlib importlib.metadata; embed tool_versions; fail on mismatch

# BUILD-vs-BUY: Version-Keyed Guard Baselines + Refresh Ritual

Research for `whisker` guard baseline versioning. Question: when `tomd` or its deps bump, how do we prevent grading against a stale baseline, and do we need the `packaging` library to record/compare producing versions?

Constraints: deterministic, no LLM, minimalism ladder (stdlib first), permissive license only, Python >=3.12, lib funcs return data / CLI persists.

Prior art: `notes/redteam-synthesis.md` (Tier 3: version-keyed baselines), `notes/cross-repo-qa-research.md`, `research/redteam/PyMuPDF.md`, `pandoc.md`, `html-to-markdown-go.md`, `html-to-markdown-py.md`. Cloned repos under `research/repos/` currently hold `.git` metadata only (no working tree); per-repo evidence below is from redteam grep during the June 2026 clone pass, with file:line citations into upstream trees.

---

## 1. Current whisker baseline schema + refresh ritual

### 1.1 Baseline payload (`baseline_from_rows`)

| Field | Source | Role |
|-------|--------|------|
| `schema_version` | `C.WHISKER_SCHEMA_VERSION` (currently `1`) | Whisker **baseline JSON format** version; mismatch hard-fails in `_validate_baseline` |
| `kind` | `GUARD_BASELINE_KIND` (`"whisker-guard-baseline"`) | Distinguishes guard baselines from bench leaderboards |
| `axis_slack` | `C.GUARD_AXIS_SLACK` | Per-axis regression tolerance embedded in baseline |
| `floors` | `{nid, teds, mhs}` from `constants.py` | Absolute floors embedded in baseline |
| `rows` | `{pid: {axis: rounded float}}` | Per-paper metric snapshot (4dp) |

**No producer toolchain metadata.** A baseline committed after `tomd 0.4.0` can be diffed under `tomd 0.4.1` with no gate noticing the mismatch. Metric shifts from converter changes look like regressions or silent passes against the wrong contract.

Symbols:

- `baseline_from_rows` — builds committable payload (`guard.py:181-198`)
- `_validate_baseline` — rejects wrong `kind`, stale `schema_version`, bad slack/floors/rows (`guard.py:201-235`)
- `diff_rows` — validates baseline, resolves slack/floors from baseline, per-paper diff (`guard.py:321-365`)

### 1.2 Refresh ritual (CLI)

| Flag / path | Behavior |
|-------------|----------|
| `whisker guard --update` | Rewrites `--baseline` from current `run_bench` rows via `baseline_from_rows`; exit 0 (`__main__.py:331-334`, `371-381`) |
| default (no `--update`) | Load baseline, `diff_rows`, fail on regression / missing / optional `--fail-on-new` (`__main__.py:383-413`) |
| `--fail-on-new` | New corpus PIDs fail until explicit `--update` (`__main__.py:343-346`, `guard.py:337-338`) |

**Gap:** `--update` overwrites the single baseline file unconditionally. There is no version branch (PyMuPDF parallel goldens) and no recorded `tool_versions` at write time.

### 1.3 `schema_version` vs toolchain version

These must stay **separate**:

- `schema_version` — evolution of whisker's baseline **JSON shape** (add `tool_versions` ⇒ bump to `2`).
- `tool_versions` (proposed) — versions of packages that **produced the candidate markdown and scores** (`tomd`, optionally `pymupdf`, `whisker`, scorer deps).

A `schema_version` bump without a `tomd` bump means "re-read the file layout." A `tomd` bump without refresh means "scores may not be comparable to stored rows."

---

## 2. Per-repo evidence: version-keyed goldens + refresh flags

### 2.1 PyMuPDF — version-keyed parallel goldens (selector, not overwrite)

**Pattern:** Multiple committed expected artifacts; test code selects the golden matching **runtime** `mupdf_version_tuple`. Dependency bumps add parallel files; old goldens remain for other version bands.

| Evidence | Location (upstream) |
|----------|---------------------|
| Three text goldens selected by version tuple | `tests/test_font.py:69-77` (`test_2608_expected`, `_1.26`, `_1.28`) |
| PDF pixmap golden swap at `(1, 27)` | `tests/test_annots.py:241-244` |
| OCR text golden swap at `(1, 28)` | `tests/test_tesseract.py:82-85` |
| Inline version-specific markdown expectations | `tests/test_tables.py:308-326` |
| Version-band warning text | `tests/test_2548.py:29-36` |
| CI matrix across MuPDF branches | `test_quick.yml:26-46`, `test_multiple.yml:24-29` |

**Refresh ritual:** No single `--accept` CLI. Goldens are **hand-added/edited in PR** when output changes; e.g. add `test_2608_expected_1.28` rather than overwrite `_1.26` (`PyMuPDF.md` §1.9).

**Portable lesson for whisker:** Record which toolchain produced the baseline; on mismatch, **fail closed** and require `--update` (or maintain parallel baseline files keyed by `tomd` version). Do not silently diff against wrong-era metrics.

### 2.2 pandoc — `--accept` refresh, CI never auto-accepts

| Evidence | Location (upstream) |
|----------|---------------------|
| Local golden rewrite | `Makefile:50-55` — `make test TESTARGS='--accept'` |
| Human review before commit | `CONTRIBUTING.md:272-279` |
| CI runs tests **without** `--accept` | convention documented in redteam report |
| Fail-closed on new fixtures | `test/Tests/Command.hs:83-87`, `Old.hs:370-394` |

**Portable lesson:** Explicit refresh flag + CI dry-run only. whisker already has `--update`; missing piece is **toolchain metadata** and fail-on-stale-version (pandoc's analog is "any output change fails until accept").

### 2.3 html-to-markdown-go — `go test -update` (goldie)

| Evidence | Location (upstream) |
|----------|---------------------|
| Byte-exact goldie assert | `internal/tester/goldenfiles.go:63-78` |
| Refresh documented | `README.md:387-393` — `go test -update` rewrites `*.out.md` |
| CI without `-update` | `.github/workflows/go.yml:31` — `go test ./...` |
| Line-ending stability | `plugin/commonmark/testdata/.gitattributes:4` — `* -text` |

**Portable lesson:** CI never passes update flag; refresh is developer-local then committed. Same contract as `whisker guard --update`.

### 2.4 html-to-markdown-py — `htmbench oracle --bless` + audit metadata

| Evidence | Location (upstream) |
|----------|---------------------|
| Snapshot bless overwrite | `tools/benchmark-harness/.../main.rs:265-267` |
| Perf baseline records `schema`, git `sha`, `host`, `created_at` | `schema.rs:32-42`, `main.rs:164-170` |
| Human-blessed, not CI-written | `CHANGELOG.md:360` |
| CI oracle without bless | `benchmark.yml:20-23` |

**Portable lesson:** Baseline carries **audit metadata** beyond scores. whisker should embed at least `tool_versions` (deterministic, no host/sha required for reproducibility).

### 2.5 Cross-repo synthesis (`notes/cross-repo-qa-research.md`)

- Practice #2 lists pandoc `--accept`, go `-update`, py `--bless` as the refresh family.
- Practice #2 also calls out **PyMuPDF version-keyed goldens** so "a dependency bump can't silently pass against the wrong baseline."
- `redteam-synthesis.md` Tier 3 defers full version-keyed baselines but flags relevance when tomd pins shift.

---

## 3. Library check: `importlib.metadata` (stdlib) vs `packaging`

### 3.1 `importlib.metadata` (stdlib, Python 3.12+)

```python
from importlib.metadata import PackageNotFoundError, version
version("tomd")  # e.g. "0.4.1"
```

- **License:** stdlib (PSF).
- **Cost:** zero new dependency.
- **Determinism:** returns the installed distribution version string at call time; same env ⇒ same string.
- **Verified in workspace venv:** `tomd 0.4.1`, `whisker 0.4.1`, `pymupdf 1.27.2.3`, etc.

**Sufficient for whisker's need:** record exact version strings at baseline write; compare with **string equality** (after optional normalization of whitespace). No PEP 440 range logic required for v1.

### 3.2 `packaging` (PyPI)

- **License:** Apache-2.0 / BSD (permissive).
- **Already present transitively** in workspace (`packaging 25.0` importable; `uv.lock` lists it under scipy/pytest/markitdown-adjacent trees). **Not** declared in `packages/whisker/pyproject.toml`.
- **Provides:** `packaging.version.Version`, specifiers, compatibility parsing.

**When it would matter:** version **ranges** (`tomd >= 0.4,< 0.5`), canonical normalization of equivalent strings (`1.0.0` vs `1.0`), or selecting among parallel baselines by "nearest compatible" (PyMuPDF tuple branching is hand-coded, not `packaging`).

### 3.3 Decision table

| Need | stdlib | packaging |
|------|--------|-----------|
| Read installed package version | yes (`version()`) | yes (via importlib + parse) |
| Exact string match gate | yes | overkill |
| PEP 440 normalize/compare | manual / fragile | yes |
| Parallel baselines by version band | custom tuple logic (PyMuPDF style) | helper only |
| New whisker dependency | no | yes (avoid) |

---

## 4. VERDICT: BUILD-IMPROVE (stdlib), not BUY `packaging`

**BUILD-IMPROVE** with `importlib.metadata.version` for v1. Do **not** add `packaging` to `pyproject.toml` until a concrete need for specifiers or canonical normalization appears (e.g. multi-baseline files selected by compatible range).

### 4.1 Proposed baseline shape (schema_version → 2)

Add to `baseline_from_rows` output:

```json
{
  "schema_version": 2,
  "kind": "whisker-guard-baseline",
  "tool_versions": {
    "tomd": "0.4.1",
    "whisker": "0.4.1"
  },
  "axis_slack": 0.02,
  "floors": { "mhs": 0.5, "nid": 0.85, "teds": 0.7 },
  "rows": { "...": "..." }
}
```

**Collection helper (library, returns data):**

```python
_TOOL_VERSION_PACKAGES = ("tomd", "whisker")  # extend deliberately; sort keys in output

def collect_tool_versions() -> dict[str, str]:
    from importlib.metadata import PackageNotFoundError, version
    out: dict[str, str] = {}
    for name in sorted(_TOOL_VERSION_PACKAGES):
        try:
            out[name] = version(name)
        except PackageNotFoundError:
            out[name] = "unknown"
    return out
```

Optional v2.1: add `pymupdf` if guard corpus is PDF-heavy and tomd bumps often co-travel with pymupdf pin changes. Keep the list **small and named** (minimalism ladder); do not snapshot every transitive dep (numpy/scipy bumps rarely change markdown output).

### 4.2 Version-mismatch policy (mirror `schema_version`)

In `_validate_baseline` or a dedicated check before `diff_rows`:

| Condition | Policy | Rationale |
|-----------|--------|-----------|
| Baseline lacks `tool_versions` (schema 1) | **Warn once**, continue diff | Non-breaking migration |
| `tool_versions["tomd"]` != current `version("tomd")` | **Hard fail** (`ValueError`, CLI exit 1) | PyMuPDF wrong-golden prevention |
| `tool_versions["whisker"]` != current | **Hard fail** | Scorer/normalizer changes invalidate rows |
| Optional transitive (e.g. `pymupdf`) | **Warn** or hard fail if listed | Tune when evidence shows churn |

Message pattern (parallel existing schema error at `guard.py:217-220`):

```
baseline tool_versions.tomd '0.4.0' != current '0.4.1' (regenerate with --update)
```

**Do not WARN-only for `tomd`:** a warn-only mismatch recreates the silent stale-baseline bug. FAIL forces the same explicit acknowledgement as `--fail-on-new` and pandoc's "accept before green."

### 4.3 CLI surface

| Existing | Proposed |
|----------|----------|
| `whisker guard --update` | Also writes fresh `tool_versions` from current env |
| `whisker guard` (default) | Fail on `tool_versions` mismatch before per-paper diff |
| `--fail-on-new` | Orthogonal; keep both gates |

Optional escape hatch (local dev only, not CI):

- `--ignore-tool-version` — skip mismatch check (document as footgun; default off).

No new subcommand. Refresh stays `--update`.

### 4.4 Future: PyMuPDF-style parallel baselines (out of v1 scope)

If CI must keep **two tomd versions** green simultaneously:

- `guard-baseline-tomd-0.4.1.json` sibling files, or
- `rows_by_toolchain: {"tomd==0.4.1": {...}}` with selector on current version.

That is Tier 3 / separate pass. v1 embedding + fail-on-mismatch closes the critical hole with minimal diff.

---

## 5. Risks

### 5.1 Version noise causing churn

- **Patch bumps** that do not change conversion output still force `--update` and a baseline commit. Acceptable: the refresh ritual is the review moment; metric diffs may be empty if output unchanged.
- **Mitigation:** slack + floors still gate real regressions; version gate only blocks *unacknowledged* toolchain drift.

### 5.2 Monorepo editable installs

- `importlib.metadata.version("tomd")` returns **PEP 440 version from package metadata** (`0.4.1`), not git SHA. Two editable checkouts at the same declared version are indistinguishable.
- **Mitigation (optional later):** add `tool_versions_extra: {"tomd_git_sha": "..."}` from env var or `importlib.metadata.metadata("tomd").get("Source-Commit")` when present; do not require for v1.

### 5.3 Determinism

- Recording versions at `--update` time and comparing at diff time is deterministic given a fixed environment.
- **Non-determinism source:** different CI vs laptop dependency sets. Pin lockfile + record versions makes drift visible instead of silent.
- `schema_version` and `tool_versions` answer different questions; bump schema only when JSON shape changes.

### 5.4 False negatives on "improvement only" bumps

- tomd improves scores; version mismatch fails before diff shows all-green. Developer runs `--update` once; intended.

### 5.5 Over-snapshotting deps

- Snapshotting numpy/scipy/lxml/markitdown in v1 adds noise without proven conversion impact. Start with **`tomd` + `whisker`** only; expand with evidence.

---

## 6. Summary table

| Item | Current | Proposed v1 |
|------|---------|-------------|
| Toolchain in baseline | none | `tool_versions` dict |
| Version library | n/a | stdlib `importlib.metadata` |
| Mismatch policy | n/a | hard fail (like `schema_version`) |
| Refresh | `--update` | same; writes new `tool_versions` |
| Parallel baselines | n/a | deferred (PyMuPDF model) |
| `packaging` dep | transitive only | do not add |

---

## 7. Implementation checklist (future pass; no code in this research task)

1. Bump `WHISKER_SCHEMA_VERSION` to `2` when adding `tool_versions`.
2. `collect_tool_versions()` + embed in `baseline_from_rows`.
3. `_validate_baseline` / pre-diff check: compare `tomd`, `whisker`.
4. Tests: mismatch fails; `--update` round-trip; schema-1 baseline warns.
5. Document in guard module docstring + CLAUDE.md artifacts section.
6. CI: run guard without `--update`; fail on mismatch or metric regression.
