# 14 - Portability-Platform

**Verdict:** usable-with-conditions — the hermetic Lane 3 CI gate is cross-platform today (whisker runs on ubuntu-latest and windows-latest per `00-baseline.md:58-59`, `.github/workflows/tests.yml:65-66`), but corpus I/O encoding is inconsistent across read paths, committed snapshots ship CRLF without `.gitattributes`, and the authoring playbook is PowerShell-only.
**Confidence:** high

## Findings

- [HIGH] **`expected.md` read encoding splits CI from the golden CLI.** Evidence: `tests/test_comprehension_corpus.py:62` reads snapshots with `encoding="utf-8"`; `__main__.py:584` reads the same files with `encoding="utf-8-sig"`. Impact: a Windows editor that saves UTF-8 with BOM (common for Notepad) strips cleanly on `whisker golden` but leaves U+FEFF inside the markdown passed to `check_facts` in CI, which can silently flip present/absent/table verdicts off the author's machine while local golden runs look fine.

- [MED] **Committed comprehension corpus is CRLF-heavy and the repo has no `.gitattributes`.** Evidence: runtime probe at this SHA — `P4182R0.expected.md` 411 `\r\n` sequences, `P4185R0.expected.md` 2180; repo-wide glob finds zero `.gitattributes`. Lane 1 collapses CRLF before `difflib` compare (`golden.py:88-90`, covered by `tests/test_golden.py:23-44`); Lane 3 table parsing uses `splitlines()` (`facts.py:268`) so tables survive, but `--update` rewrites snapshots as LF-only normalized text (`__main__.py:642-643`). Impact: bless/review diffs are platform-sensitive noise; a partial re-bless on one OS can churn thousands of line-ending bytes without changing comprehension semantics, eroding trust in golden stability claims (`00-baseline.md:29`).

- [MED] **JSONL/BOM tolerance is wired for facts but not mirrored on every committed text artifact.** Evidence: `parse_facts_jsonl` callers consistently use `utf-8-sig` (`__main__.py:506`, `__main__.py:714`, `tests/test_comprehension_corpus.py:63`); the POC one-liner documents the same split — `utf-8` for `expected.md`, `utf-8-sig` for `facts.jsonl` (`comprehension-poc-report.md:131`). Guard/bench reference markdown still uses plain `utf-8` only (`__main__.py:292`). Impact: hand-edited Windows baselines get asymmetric treatment (BOM-safe JSON, BOM-fragile markdown), matching the red-team warning that guard has no CRLF normalization beyond JSON BOM handling (`research/redteam/html-to-markdown-go.md:77`).

- [MED] **Corpus authoring workflow is PowerShell-only.** Evidence: `comprehension-poc-report.md:110-140` (`$env:WG21_DATA_DIR`, `Get-ChildItem`, backslash paths); `packages/whisker/src/whisker/CLAUDE.md` quickstart is likewise PowerShell-first. Impact: Ubuntu-only contributors can run CI (`uv run pytest packages/whisker/tests`, `00-baseline.md:58-59`) but cannot reproduce the bless/verify ritual without translating env syntax and paths; fact authorship stays tied to the author's Windows layout.

- [MED] **`--report-dir` sidecar filenames diverge from the default backend-derived path.** Evidence: default write uses `sidecar_path()` → `md_path.stem + ".whisker.json"` (`score.py:307-314`); `--report-dir` forces `f"{pid.lower()}.whisker.json"` (`__main__.py:241-244`). Impact: on case-sensitive filesystems (Linux CI agents, WSL bind mounts) tooling that assumes one naming convention misses sidecars written under the other flag; on Windows the collision is masked by case-insensitivity.

- [LOW] **`str.lower()` in `_norm_cell` / `_math_surface` is not locale-driven, but it is weaker than olmOCR's normalization story.** Evidence: `facts.py:181`, `facts.py:185`; verified under `tr_TR` locale — `'I'.lower()` remains `'i'`. olmOCR-bench applies NFC and hyphen/quote unification before deterministic scoring (`05-web.md` Q1, https://olmocr.allenai.org/papers/olmocr.pdf). Impact: Turkish-locale Windows is not a CPython `str.lower()` trap here; residual risk is Unicode edge cases (`ß` vs `ss` under `lower()` vs `casefold()`) and parity drift from the adopted olmOCR normalization contract, not OS locale itself.

- [LOW] **Hermetic CI deliberately decouples from `WG21_DATA_DIR`, but CLI lanes remain env-coupled.** Evidence: `tests/test_comprehension_corpus.py:10-14`, `00-baseline.md:58-59`; `whisker facts` / `whisker golden` require `_open_backend(args.workspace)` (`__main__.py:699-700`, `__main__.py:619-620`) backed by `sqlite_backend.py:1167-1169` lowercase stems under `paperstore/`. Impact: CI proves comprehension against committed snapshots; local guard/facts/golden verdicts on live candidates still need a correctly pointed data dir and staged lowercase `.md` files — failures off-machine are operational, not caught by the hermetic gate.

## False-pass hypothesis

A contributor blesses `P4182R0.expected.md` on Windows with a UTF-8 BOM while CI reads it via `utf-8` (`test_comprehension_corpus.py:62`): the hermetic comprehension suite fails, but they re-check with the POC incantation using `utf-8-sig` on facts only and `whisker golden` (which uses `utf-8-sig` on expected, `__main__.py:584`) — seeing golden stable while misreading the CI failure as "environment noise," they merge a snapshot that passes golden locally yet would fail the actual CI gate if BOM were present in expected (or conversely, strip BOM manually and pass CI while golden diff noise persists from CRLF/LF churn).

## False-fail hypothesis

A Linux contributor runs `whisker golden --update` (writes LF-normalized snapshots, `__main__.py:642-643`) and commits: comprehension facts still pass (table/`splitlines` path), but the PR shows a mass CRLF→LF diff on `*.expected.md` without `.gitattributes` enforcement; reviewers treat it as accidental corruption and reject a valid bless, blocking corpus updates off the original Windows author's line-ending convention.

## What would change my mind

One release cycle of clean `whisker` matrix runs on `windows-latest` **and** `ubuntu-latest` after adding repo-root `.gitattributes` (LF for `corpus/*.expected.md`, `corpus/*.facts.jsonl`), unifying all corpus read paths on `utf-8-sig`, and landing a bash-equivalent of `comprehension-poc-report.md:110-140` — with zero encoding or line-ending-related comprehension flakes and at least one non-Windows-authored corpus bless merged without manual path translation.
