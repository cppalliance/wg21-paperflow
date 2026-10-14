# 14 - Portability-Platform

**Verdict:** usable-with-conditions — path and config discovery are anchored to `Path.cwd()` and a repo-root `.env`, so the stack runs reliably from the author's Windows dev shell but fails or mis-configures when invoked from a Linux service/data-dir working directory without explicit env exports and a passed `SERVICES.toml` path.
**Confidence:** high

## Findings
- [CRITICAL] `SERVICES.toml` discovery walks upward from `Path.cwd()` only; there is no package-root or install-location anchor. `_find_services_toml` starts at `Path.cwd()` and checks `[here, *here.parents]` (`services.py:87-94`); `load_services()` calls it whenever `path` is omitted (`services.py:127-128`). Tapetum invokes `load_services()` with no path from `adjudicate_paper` (`adjudicate.py:379`). If the process cwd is `$WG21_DATA_DIR`, a systemd unit `WorkingDirectory`, or any directory outside the git checkout, discovery returns `None` and raises `FileNotFoundError` (`services.py:129-133`).
  Impact: a Linux cron job or CI step that `cd`s into the data dir before calling `whisker-tapetum-llm` cannot reach the LLM stack at all, while the same command from the repo root on the author's Windows machine succeeds.

- [HIGH] API-key hydration via `.env` is cwd-coupled and tapetum-only. `main()` calls `load_dotenv(find_dotenv(usecwd=True))` (`cli.py:346-348`), which searches upward from cwd for a file named `.env`, not from the installed package or repo root independently of cwd. The main `paperflow` CLI never loads dotenv (grep across `packages/cli/` is empty). `find_dotenv` returning `None` makes `load_dotenv(None)` a silent no-op; failure surfaces later as `ServiceConfigError` on missing `ALLIANCE_POD_KEY` (`services.py:504-515`).
  Impact: operators who keep secrets in a repo-root `.env` and run tapetum from a data-directory cwd (natural on Linux) get cryptic missing-key errors; Windows dev from repo root masks the defect.

- [HIGH] `WG21_DATA_DIR` resolution in tapetum skips the whitespace strip that paperstore enforces elsewhere. `_load_backend` reads `os.environ.get("WG21_DATA_DIR", "")` with no `.strip()` (`cli.py:158-162`); `default_workspace_dir()` strips before constructing `Path` (`factory.py:29-36`). Whisker core uses `SqliteBackend.from_env()` via `_open_backend` (`__main__.py:116-119`, `sqlite_backend.py:587-597`), which inherits the strip. Tapetum duplicates env resolution with a weaker contract.
  Impact: a trailing newline or space in `WG21_DATA_DIR` (common when set from a `.env` line or Windows setx) makes tapetum open a non-existent directory on any OS while `whisker`/`paperflow` on the same machine work.

- [MED] Error remediation text is Unix-shell-centric. Missing API-key errors instruct `export {env_var}=<your-key>` (`services.py:511-512`); unset workspace errors use the same pattern (`factory.py:31-35`). No PowerShell equivalent (`$env:VAR=...`) despite baseline dev on Windows PowerShell (`00-baseline.md` context, whisker CLAUDE.md quickstart).
  Impact: not a runtime break, but misleads Windows-first operators and copy-paste fixes fail silently until env is set correctly by other means.

- [MED] Batch progress uses `\r` in-place redraw guarded by `sys.stderr.isatty()` (`__main__.py:101-108`, `cli.py:89-90`), but batch mode replaces the entire root logging handler list with a single `_BarAwareHandler` (`cli.py:254-260`). On a real TTY (Windows Terminal, legacy conhost) interleaved log lines and bar redraw rely on carriage-return overwrite; on mis-detected TTY (some CI pseudo-TTY wrappers) `\r` noise can land in captured logs. Non-TTY paths correctly no-op the bar (`__main__.py:101-102`).
  Impact: CI log capture is mostly safe; interactive Windows consoles with heavy concurrent logging may show garbled progress lines, not silent wrong verdicts.

- [MED] `whisker_output_dir` derives output paths by assuming SqliteBackend layout `<root>/paperstore/<pid>.md` then `md_path.parent.parent / "whisker"` (`score.py:303-304`). Documented as a local-backend shortcut (`score.py:298-301`). All tapetum persistence routes through this helper (`cli.py:194-196`, `:223-225`).
  Impact: portable today on the sole production backend; any future non-local or reshaped paperstore layout breaks sidecar writes without code changes — a latent cross-platform backend portability gap.

- [LOW] Text artifact I/O in the tapetum CLI path consistently specifies `encoding="utf-8"` for sidecar reads/writes (`cli.py:183`, `:197-199`, `:209`, `:226`) and pipeline debug/trace writers do the same (`runner.py:320-321`, `:415`). `json.dumps(..., ensure_ascii=False)` preserves CJK in sidecars (`cli.py:198`). `SERVICES.toml` correctly opens as binary for `tomllib` (`services.py:135-136`). No locale-default `open()` on the hot path.
  Impact: encoding discipline is good where it matters; residual risk is only stderr console encoding on pre-UTF-8 Windows consoles when logs contain paper CJK, not persisted artifacts.

## False-pass hypothesis
An operator runs `whisker-tapetum-llm --review-all` from `$WG21_DATA_DIR` on Linux with `WG21_DATA_DIR` exported but no `SERVICES.toml` on the ancestor chain and no API keys in the process environment. The run fails at first LLM call with `FileNotFoundError` or missing-key errors, producing zero new sidecars; any pre-existing sidecars from an earlier repo-root Windows run remain on disk and look like fresh advisory output — stale pass preserved by invocation failure, not by a portability false pass of the model itself.

## False-fail hypothesis
None found for the portability failure class: when cwd and env are set coherently (repo root + `.env` + `WG21_DATA_DIR`), the stack runs on Linux CI the same as on Windows; failures from cwd coupling present as hard startup/config errors, not advisory false fails.

## What would change my mind
A documented invocation from a cwd outside the git tree (e.g. `WorkingDirectory=/var/wg21-data`) that succeeds without pre-exporting every secret — via explicit `--services-toml` / package-relative discovery and dotenv loaded from the installed package or repo root independent of cwd — would flip the CRITICAL/HIGH cwd-coupling findings to resolved.
