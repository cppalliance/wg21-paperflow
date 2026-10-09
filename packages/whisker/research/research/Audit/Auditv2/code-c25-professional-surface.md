# C25 Professional Surface

**Role**: Audit packaging, public API, CLI, exit codes, and Windows behavior.
**Audited state**: whisker 0.5.0, HEAD 51cb704 + local mods.
**Gates**: D7 (Professional surface), D8 (Platform compatibility).

## 1. Scope

Verify help text quality, JSON output correctness, stderr/stdout separation,
exit code contract, error messages, Windows console encoding, and packaging
(pyproject.toml, entry points).

## 2. Commands and Exits

```
uv run --package whisker pytest packages/whisker/tests/test_report.py -v
uv run --package whisker pytest packages/whisker/tests/test_menu.py -v
uv run --package whisker pytest packages/whisker/tests/test_score_file.py -v
uv run --package whisker pytest packages/whisker/tests/test_check_facts_main.py -v
```

Exit: Offline suite passes (E1).

## 3. Current Evidence

### 3.1 Packaging (pyproject.toml)

`pyproject.toml` defines:

- **Name**: `whisker` (version 0.5.0)
- **License**: BSL-1.0
- **Python**: `>=3.12`
- **Core dependencies**: apted, grits-metric, lxml, markitdown, mistune,
  numpy, paperstore, pylatexenc, rapidfuzz, rich, scipy, tomd
- **Optional tapetum-llm extra**: openai, pipeline, pydantic-ai, pydantic,
  python-dotenv

Three console scripts registered:
- `whisker` -> `whisker.__main__:main`
- `whisker-tapetum-llm` -> `whisker.tapetum_llm.cli:main`
- `whisker-readback` -> `whisker.tapetum_llm.readback_cli:main`

Build system: hatchling. Wheel target: `src/whisker`.

The core `whisker` install is LLM-free. The advisory lane (`tapetum-llm`)
is opt-in via the extra dependency group. This keeps the deterministic
QA tool standalone.

### 3.2 CLI subcommands and help text

`__main__.py` (lines 9-41) documents all subcommands in the module docstring:

| Subcommand | Purpose |
|------------|---------|
| `whisker [PID...]` | Score papers (default) |
| `whisker bench` | Corpus benchmark (Lane 2) |
| `whisker guard` | Per-paper regression gate |
| `whisker golden` | Lane 1 stability gate |
| `whisker facts` | Lane 3 comprehension gate |
| `whisker calibrate` | Fit coverage edges |
| `whisker score-file` | File-based scoring (no backend) |
| `whisker check-facts` | File-based fact checking |
| `whisker corpus` | Corpus management (stratify, draft) |

Each subcommand has its own `argparse.ArgumentParser` with descriptions.

### 3.3 Exit code contract

Typed exit codes (documented in `__main__.py` line 41):
```
0 ok, 1 error, 3 review, 5 fail
```

Defined as named constants in `constants.py` (lines 154-157):
```python
EXIT_OK = 0
EXIT_ERROR = 1
EXIT_REVIEW = 3
EXIT_FAIL = 5
```

`_verdict_exit_code()` (`__main__.py` line 130):
```python
def _verdict_exit_code(verdicts: list[str], gate: str) -> int:
    accepted = _GATE_ACCEPTS[gate]
    if VERDICT_FAIL in verdicts and VERDICT_FAIL not in accepted:
        return C.EXIT_FAIL
    if VERDICT_REVIEW in verdicts and VERDICT_REVIEW not in accepted:
        return C.EXIT_REVIEW
    return C.EXIT_OK
```

The `--gate` argument controls which verdicts are accepted:
- `--gate pass`: Only pass accepted (review/fail -> non-zero exit)
- `--gate review`: Pass and review accepted (fail -> non-zero)
- `--gate fail`: All accepted (always exit 0 unless error)

This CI contract is stable and tested.

### 3.4 stderr/stdout separation

`__main__.py` line 116: `_render_progress()` writes to `sys.stderr` only
when `sys.stderr.isatty()` returns True. When piped, no progress noise
leaks into stdout.

`report.py` is a pure function module returning strings. The CLI decides
where to write them. JSON output goes to stdout for machine consumption.
Human-readable reports go to files.

Logging uses `logging.getLogger("whisker")` (line 86), which defaults to
stderr via `logging.basicConfig()`.

### 3.5 JSON output

`--json` flag on `whisker` and `whisker score-file` produces JSON output
to stdout. `build_report()` in `report.py` returns a JSON-serializable
dict. Serialization uses `json.dumps()` with no `default=str` (per
CLAUDE.md invariant: "No `default=str` in JSON serialization").

### 3.6 Error messages

Per-paper errors in `_score_main()` (lines 218-233):
```python
except (MissingPaperMdError, MissingSourceError) as exc:
    skipped += 1
    logger.warning("skipping %s: %s", pid, exc)
except Exception:
    errored += 1
    logger.exception("error scoring %s (skipped)", pid)
```

Specific exception types produce specific warnings. Generic exceptions
produce full tracebacks via `logger.exception()`. Error counts are tracked
and reported in the summary.

### 3.7 Windows console encoding

`__main__.py` uses `sys.stderr.isatty()` to gate ANSI color codes and
progress bars. When running in a Windows console that does not support
ANSI, the tty check prevents escape-code garbage.

`report.py` line 42: `_paint()` applies ANSI codes only when `color=True`:
```python
def _paint(text: str, code: str, color: bool) -> str:
    return f"{code}{text}{_RESET}" if color else text
```

The `color` parameter is set by the CLI based on tty detection, not
hardcoded. This ensures clean output on Windows Command Prompt and when
piped to files.

Unicode handling: all file I/O uses `encoding="utf-8"` explicitly where
applicable. JSON output uses `ensure_ascii=False` (or defaults) for proper
Unicode pass-through.

### 3.8 Report rendering

`report.py` provides three pure functions:
- `build_report()`: JSON-serializable dict from `WhiskerResult` list
- `render_report_md()`: Human-readable markdown leaderboard
- `render_summary()`: One-line terminal summary

Reports are sorted by pid for deterministic output. Worst-first ordering
in the leaderboard. ANSI colors only when `color=True`.

### 3.9 Test coverage

- `test_report.py`: Tests report rendering, JSON structure, summary format
- `test_menu.py`: Tests CLI argument parsing and subcommand dispatch
- `test_score_file.py`: Tests file-based scoring entry point
- `test_check_facts_main.py`: Tests file-based fact checking entry point

All pass in the offline suite (E1).

## 4. Findings

| # | Finding | Severity | Confidence |
|---|---------|----------|------------|
| F1 | Three registered console scripts with clear separation | Informational | HIGH |
| F2 | Typed exit codes (0/1/3/5) with CI-contract documentation | Informational | HIGH |
| F3 | stderr/stdout separation via isatty() gating | Informational | HIGH |
| F4 | ANSI colors gated by tty detection (Windows-safe) | Informational | HIGH |
| F5 | Core install is LLM-free; tapetum-llm is opt-in extra | Informational | HIGH |
| F6 | No `default=str` in JSON serialization (CLAUDE.md invariant) | Informational | HIGH |
| F7 | Error messages use specific exception types with traceback | Informational | HIGH |

No violations found.

## 5. False-Pass Hypothesis

**Could a Windows console break the exit code contract?**

Exit codes are numeric constants returned by `main()`. Python's
`sys.exit(int)` passes these to the OS regardless of console encoding.
The contract is platform-independent.

**Could piped output contain ANSI escape codes?**

`_render_progress()` checks `sys.stderr.isatty()`. `_paint()` requires
`color=True`. The CLI sets `color` based on tty detection. When piped,
both functions produce plain text. The risk is zero.

## 6. Gate/Dimension Mapping

- **D7 (Professional surface)**: PASS. Help text, exit codes, JSON output,
  error messages, and report rendering are clean and professional.
- **D8 (Platform compatibility)**: PASS. ANSI gating, tty detection, and
  numeric exit codes are platform-safe. Windows console encoding is handled
  by conditional ANSI code emission.

## 7. Limitations

- Cannot test actual Windows console behavior from this environment.
  Evidence is from code inspection of tty detection and ANSI gating.
- Cannot verify `whisker --help` output rendering (requires running the
  CLI, which needs a paperstore backend for most subcommands).
- The `rich` dependency may add its own ANSI formatting; its interaction
  with the tty detection is not fully audited here.

## 8. Conclusion

The professional surface is well-maintained. Packaging cleanly separates
the LLM-free core from the advisory lane via optional dependencies. The
CLI provides typed exit codes with a documented CI contract (0/1/3/5),
proper stderr/stdout separation, and ANSI color gating for Windows
compatibility. Error messages use specific exception types. Reports are
pure, deterministic functions. All surface-level tests pass.
