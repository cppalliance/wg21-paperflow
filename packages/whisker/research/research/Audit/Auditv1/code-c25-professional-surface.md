# C25 - Professional Surface Auditor

**Mandate:** Assess CLI help, README, CLAUDE.md commands, API exports, versions, packaging.
**Focus dimensions:** D7 (package boundary), D8 (packaging).

---

## 1. CLI Verbs (`__main__.py`)

### 1.1 Verb Routing

| Verb | Route Function | Documented in CLAUDE.md |
|------|---------------|------------------------|
| `(default)` / PIDs / `--all` | `_score_main` | Yes: `whisker [PID ...] [--all]` |
| `bench` | `_bench_main` | Yes: `whisker bench` |
| `guard` | `_guard_main` | Yes: `whisker guard` |
| `golden` | `_golden_main` | Yes: `whisker golden` |
| `facts` | `_facts_main` | Yes: `whisker facts` |
| `calibrate` | `_calibrate_main` | Yes: `whisker calibrate` |
| `score-file` | `_score_file_main` | Yes: `whisker score-file` |
| `check-facts` | `_check_facts_main` | Yes: `whisker check-facts` |
| `corpus` | `_corpus_main` | Yes: `whisker corpus` |
| (no args, tty) | `run_menu` | Not documented as a verb (implicit interactive mode) |

| Severity | **PASS** |
|----------|----------|
| Claim | All CLI verbs in `__main__.py` are documented in CLAUDE.md. |
| Evidence | `__main__.py:1241-1263` (verb routing) matches CLAUDE.md "Usage (quickstart)" section. The interactive menu (`run_menu`) is an undocumented fallback for no-args-on-tty, not a documented verb. |
| Affected gate | D7 |
| Confidence | 0.97 |
| False-pass hypothesis | The interactive menu is undocumented. Low risk: it only activates when no args are passed on a tty. |
| False-fail hypothesis | None. |

### 1.2 Flag Accuracy (Default Score Verb)

| Flag | Code Implementation | CLAUDE.md Documentation | Match |
|------|-------------------|------------------------|-------|
| `--all` | `store_true` (line 142) | Yes, two dashes noted | YES |
| `--json` | `store_true` (line 143) | Yes | YES |
| `-v/--verbose` | `store_true` (line 146) | Yes | YES |
| `-q/--quiet` | `store_true` (line 149) | Yes | YES |
| `--stats` | `store_true` (line 153) | Yes | YES |
| `--reference` | `choices=REFERENCE_ENGINES` (line 157) | Yes | YES |
| `--no-reference` | `store_true` (line 163) | Yes | YES |
| `--no-write` | `store_true` (line 166) | Yes | YES |
| `--report-dir` | `help=...` (line 170) | Yes | YES |
| `--gate` | `choices=("pass","review","fail")` (line 175) | Yes | YES |
| `--workspace` | `help=...` (line 180) | Yes (as `--workspace DIR`) | YES |

| Severity | **PASS** |
|----------|----------|
| Claim | All documented flags match their implementation. |
| Evidence | Cross-reference above. |
| Affected gate | D7 |
| Confidence | 0.99 |
| False-pass hypothesis | None. |
| False-fail hypothesis | None. |

---

## 2. `__init__.py` Exports

### 2.1 `__all__` Completeness

| Severity | **PASS** |
|----------|----------|
| Claim | `__init__.py` exports are clean and complete. All re-exported symbols are from whisker core modules (not tapetum_llm). |
| Evidence | `__init__.py:10-63`: imports from `anchors`, `bench`, `calibrate`, `facts`, `gates`, `golden`, `golden_ideals`, `guard`, `match`, `metrics`, `reference`, `report`, `score`. `__init__.py:64-118`: `__all__` lists 39 symbols. No imports from `tapetum_llm` (isolation invariant). |
| Affected gate | D7 |
| Confidence | 0.98 |
| False-pass hypothesis | A symbol imported at the top but missing from `__all__` would be accessible but not "officially" exported. Not found: every import is in `__all__`. |
| False-fail hypothesis | None. |

### 2.2 tapetum_llm `__init__.py`

| Severity | **PASS** |
|----------|----------|
| Claim | `tapetum_llm/__init__.py` re-exports only the model types from `tapetum_llm.models`. |
| Evidence | `tapetum_llm/__init__.py:30-46`: exports `Adjudication`, `AxisFinding`, `EvidenceSpan`, `FidelityAxis`, `TapetumResult`, `Verdict`. No VLM modules, no readback modules. |
| Affected gate | D7 |
| Confidence | 0.99 |
| False-pass hypothesis | None. |
| False-fail hypothesis | None. |

---

## 3. `pyproject.toml` Compliance

### 3.1 PEP 621 Compliance

| Severity | **PASS** |
|----------|----------|
| Claim | `pyproject.toml` follows PEP 621 metadata specification. |
| Evidence | `pyproject.toml:1-7`: `[project]` table with `name`, `version`, `description`, `requires-python`, `license`, `authors`. All required PEP 621 fields present. `requires-python = ">=3.12"` is a valid specifier. |
| Affected gate | D8 |
| Confidence | 0.99 |
| False-pass hypothesis | None. |
| False-fail hypothesis | None. |

### 3.2 Wheel Targets

| Severity | **PASS** |
|----------|----------|
| Claim | The wheel build target is correctly configured. |
| Evidence | `pyproject.toml:43-44`: `[tool.hatch.build.targets.wheel] packages = ["src/whisker"]`. This matches the source layout at `packages/whisker/src/whisker/`. |
| Affected gate | D8 |
| Confidence | 0.98 |
| False-pass hypothesis | None. |
| False-fail hypothesis | None. |

### 3.3 Extras Isolation

| Severity | **PASS** |
|----------|----------|
| Claim | The `tapetum-llm` extra is properly isolated from core dependencies. Pipeline and LLM packages are optional. |
| Evidence | `pyproject.toml:23-32`: `[project.optional-dependencies] tapetum-llm = ["openai", "pipeline", "pydantic-ai", "pydantic>=2.0", "python-dotenv>=1.0"]`. Core `dependencies` (lines 8-21) have no LLM packages: `apted`, `grits-metric`, `lxml`, `markitdown`, `mistune`, `numpy`, `paperstore`, `pylatexenc`, `rapidfuzz`, `rich`, `scipy`, `tomd`. |
| Affected gate | D8 |
| Confidence | 0.99 |
| False-pass hypothesis | `rich` is in core dependencies but is only used for the interactive menu. Acceptable: it is a lightweight dependency. |
| False-fail hypothesis | None. |

### 3.4 Console Scripts

| Severity | **PASS** |
|----------|----------|
| Claim | All three console scripts are correctly registered. |
| Evidence | `pyproject.toml:34-37`: `whisker = "whisker.__main__:main"`, `whisker-tapetum-llm = "whisker.tapetum_llm.cli:main"`, `whisker-readback = "whisker.tapetum_llm.readback_cli:main"`. |
| Affected gate | D8 |
| Confidence | 0.99 |
| False-pass hypothesis | None. |
| False-fail hypothesis | None. |

---

## 4. Version Consistency

| Severity | **PASS** |
|----------|----------|
| Claim | `pyproject.toml` version matches `__init__.py.__version__`. |
| Evidence | `pyproject.toml:3`: `version = "0.5.0"`. `__init__.py:120`: `__version__ = "0.5.0"`. Both are `"0.5.0"`. |
| Affected gate | D8 |
| Confidence | 1.00 |
| False-pass hypothesis | None: exact string match. |
| False-fail hypothesis | None. |

---

## 5. README

| Severity | **INFO** |
|----------|----------|
| Claim | No `README.md` exists for the whisker package. Documentation lives in `CLAUDE.md`. |
| Evidence | Glob search for `packages/whisker/README*` returned no results. `CLAUDE.md` at `packages/whisker/src/whisker/CLAUDE.md` serves as the primary documentation (architecture map, usage, invariants, known gaps). |
| Affected gate | D7 |
| Confidence | 0.99 |
| False-pass hypothesis | A user installing `whisker` from PyPI would see no README on the package page. Low risk: whisker is not published to PyPI (workspace-internal package). |
| False-fail hypothesis | None. |

---

## 6. Exit Code Documentation vs Implementation

| Severity | **PASS** |
|----------|----------|
| Claim | Exit codes (0 ok, 1 error, 3 review, 5 fail) match between CLAUDE.md and implementation. |
| Evidence | CLAUDE.md "Exit codes": `0` ok, `1` error, `3` review, `5` fail. `__main__.py:131-136`: `_verdict_exit_code` maps verdicts to `C.EXIT_FAIL` (5), `C.EXIT_REVIEW` (3), `C.EXIT_OK` (0). `constants.py` (whisker core): `EXIT_OK = 0`, `EXIT_ERROR = 1`, `EXIT_REVIEW = 3`, `EXIT_FAIL = 5` (verified via imports). |
| Affected gate | D7 |
| Confidence | 0.98 |
| False-pass hypothesis | None. |
| False-fail hypothesis | None. |

### 6.1 Exit Code Consistency Across Verbs

| Severity | **PASS** |
|----------|----------|
| Claim | All verbs use the same exit code constants. |
| Evidence | Every `_*_main` function returns `C.EXIT_*` constants. `_score_main` (line 283): `_verdict_exit_code`. `_bench_main` (line 498): `C.EXIT_FAIL` / `C.EXIT_OK`. `_guard_main` (line 617): `C.EXIT_FAIL` / `C.EXIT_OK`. `_golden_main` (line 832): `C.EXIT_FAIL` / `C.EXIT_OK`. `_facts_main` (line 916): `C.EXIT_FAIL` / `C.EXIT_OK`. `_calibrate_main` (line 1151): always `C.EXIT_OK`. `_score_file_main` (line 421): local `exit_code` mapped from flags. `_check_facts_main` (line 1016): `C.EXIT_FAIL` / `C.EXIT_OK`. |
| Affected gate | D7 |
| Confidence | 0.95 |
| False-pass hypothesis | `_score_file_main` computes its own exit code (line 392-393) rather than using `_verdict_exit_code`. The logic is equivalent but duplicated. Low risk. |
| False-fail hypothesis | None. |

---

## 7. stdout/stderr Discipline

| Severity | **PASS** |
|----------|----------|
| Claim | stdout carries results, stderr carries progress and log lines. |
| Evidence | `__main__.py:98-121`: `_render_progress` writes to `sys.stderr` (progress bar). `__main__.py:268-269`: JSON output via `print()` (stdout). `__main__.py:271-281`: human summary via `print()` (stdout). Logging goes to stderr via `logging.basicConfig` (line 1242). The progress bar is suppressed when `sys.stderr.isatty()` is False (line 109). |
| Affected gate | D7 |
| Confidence | 0.97 |
| False-pass hypothesis | None. |
| False-fail hypothesis | None. |

---

## 8. `--json` Flag Cleanliness

| Severity | **PASS** |
|----------|----------|
| Claim | `--json` produces clean JSON without human text leaking in. |
| Evidence | `__main__.py:267-269`: when `args.json` is True, only `json.dumps(...)` is printed. The `render_summary` call is in the `else` branch (line 270-281). The `_render_progress` function (line 109) checks `sys.stderr.isatty()` and writes to stderr only, so no progress bar contaminates stdout. |
| Affected gate | D7 |
| Confidence | 0.98 |
| False-pass hypothesis | A `logger.info` call between the `print(json.dumps(...))` and the end of the function could write to stderr (not stdout). No risk to JSON purity. |
| False-fail hypothesis | None. |

### 8.1 `--json` on Other Verbs

| Severity | **PASS** |
|----------|----------|
| Claim | `guard`, `golden`, and `facts` verbs with `--json` produce clean JSON. |
| Evidence | `_guard_main` (line 610-611): `if args.json: print(payload)` in an exclusive branch. `_golden_main` (line 822-823): same pattern. `_facts_main` (line 904-905): same pattern. All three gate the human summary in an `else` branch. |
| Affected gate | D7 |
| Confidence | 0.97 |
| False-pass hypothesis | None. |
| False-fail hypothesis | None. |

---

## 9. Windows-Specific Issues

| Severity | **PASS** |
|----------|----------|
| Claim | Windows-specific issues are documented and handled. |
| Evidence | (1) `readback_cli.py:132-133`: stdout UTF-8 reconfiguration with `errors="replace"` for Windows cp1252 consoles. Documented in CLAUDE.md "whisker-readback" section. (2) `__main__.py`: all file reads use `encoding="utf-8"` or `encoding="utf-8-sig"` (BOM tolerance for Windows-edited JSON). (3) No hardcoded Unix paths (`/` vs `\`): all paths use `pathlib.Path`. |
| Affected gate | D8 |
| Confidence | 0.95 |
| False-pass hypothesis | The main `whisker` CLI does not reconfigure stdout encoding (only `whisker-readback` does). If a whisker sidecar or report contains non-ASCII characters, writing to stdout on a cp1252 Windows console could fail. Low risk: sidecars are written to files (UTF-8), and the summary is typically ASCII. |
| False-fail hypothesis | None. |

### 9.1 Missing stdout Reconfiguration on Main CLI

| Severity | **LOW** |
|----------|---------|
| Claim | The main `whisker` CLI (`__main__.py`) does not reconfigure stdout to UTF-8. Only `readback_cli.py` does. |
| Evidence | `__main__.py`: no `sys.stdout.reconfigure` call. Papers with non-ASCII titles or content in flags could cause `UnicodeEncodeError` on Windows cp1252 consoles. |
| Affected gate | D8 |
| Confidence | 0.80 |
| False-pass hypothesis | WG21 papers occasionally have non-ASCII characters (e.g., author names, mathematical symbols). A flag like "misaligned region(s)" is ASCII, but a paper title in the summary could contain non-ASCII. |
| False-fail hypothesis | None. |

---

## 10. Build System

| Severity | **PASS** |
|----------|----------|
| Claim | The build system uses hatchling and is correctly configured. |
| Evidence | `pyproject.toml:39-41`: `[build-system] requires = ["hatchling"], build-backend = "hatchling.build"`. `pyproject.toml:43-44`: `[tool.hatch.build.targets.wheel] packages = ["src/whisker"]`. |
| Affected gate | D8 |
| Confidence | 0.99 |
| False-pass hypothesis | None. |
| False-fail hypothesis | None. |

---

## Summary

| # | Finding | Severity | Status |
|---|---------|----------|--------|
| 1 | All 9 CLI verbs documented in CLAUDE.md | HIGH | PASS |
| 2 | All flags match between implementation and docs | HIGH | PASS |
| 3 | `__all__` exports clean and complete (39 symbols) | HIGH | PASS |
| 4 | PEP 621 compliant pyproject.toml | HIGH | PASS |
| 5 | Extras isolation: tapetum-llm correctly optional | HIGH | PASS |
| 6 | Version consistency: pyproject.toml == `__init__.py` (0.5.0) | HIGH | PASS |
| 7 | No README.md (CLAUDE.md serves as docs) | INFO | NOTED |
| 8 | Exit codes match: 0/1/3/5 documented and implemented | HIGH | PASS |
| 9 | stdout for results, stderr for progress/logs | HIGH | PASS |
| 10 | `--json` clean JSON on all verbs | HIGH | PASS |
| 11 | Windows UTF-8 fix on readback CLI | MEDIUM | PASS |
| 12 | Main CLI missing stdout UTF-8 reconfiguration | LOW | NOTED |
| 13 | 3 console scripts correctly registered | HIGH | PASS |
| 14 | hatchling build system correctly configured | HIGH | PASS |

**Auditor verdict: The professional surface is clean and well-documented.** Version consistency, PEP 621 compliance, extras isolation, exit codes, and stdout/stderr discipline all pass. Two minor notes: no README.md (CLAUDE.md serves as docs, acceptable for a workspace-internal package), and the main CLI lacks the UTF-8 stdout reconfiguration that the readback CLI has.
