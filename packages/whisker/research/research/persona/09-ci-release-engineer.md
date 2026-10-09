# 09 - The CI / Release Engineer

**Verdict:** usable-with-conditions — the exit-code contract (0/1/3/5) and stdout/stderr split are wired correctly for automation, but the default `--gate review` only blocks hard fails (3.7% on the live corpus, not the 54% review tier), scoring exceptions never flip exit code, and lanes 1–3 cannot gate releases until a GT corpus exists.
**Confidence:** high

## Findings

- [HIGH] **Default `--gate review` does not block merges on the 54% review rate; only hard fails do.** Evidence: ref-free distribution **205 review (53.7%) / 14 fail (3.7%)** (`00` §3a); `_GATE_ACCEPTS["review"] = {pass, review}` (`__main__.py:80-84`, `161-162`); `_verdict_exit_code` returns `EXIT_FAIL` (5) only when a fail verdict is not accepted (`__main__.py:114-120`). Runtime: `whisker --all --no-write --no-reference --gate review` → **exit 5** (14 fails), while `P3100R6` (review-only) → **exit 0** at default gate and **exit 3** at `--gate pass`. Impact: CI with default settings is a **hard-fail gate (~4% block rate)**, not a human-triage gate; the 54% review tier is invisible to exit code unless operators tighten to `--gate pass`.

- [HIGH] **`--gate pass` is impractical as a merge gate on this corpus.** Evidence: **205/382** papers are review (`00` §3a); runtime `P3100R6 --gate pass` → **exit 3** (`EXIT_REVIEW`, `constants.py:138`). Full `--all --gate pass` → **exit 5** because fail verdicts are checked before review (`__main__.py:116-119`) and 14 papers hard-fail anyway. Impact: any workflow that treats exit 3 as merge-blocking would reject **most** conversions; operators must consciously choose `--gate review` (accept review) or `--gate fail` (accept everything including broken).

- [HIGH] **Per-paper scoring exceptions do not affect exit code.** Evidence: batch loop catches `Exception`, increments `errored`, logs, continues (`__main__.py:210-215`); exit is computed only from `[r.verdict for r in results]` (`__main__.py:267`), with at most a **warning** when `errored > 0` (`__main__.py:223-224`). Impact: a paper that throws during `score_paper` can leave CI **green** if the rest of the batch passes; unsafe as a sole release gate without an `errored == 0` check on stderr or a post-run JSON count.

- [HIGH] **Exit-code contract is implemented but untested through the CLI.** Evidence: `EXIT_OK/ERROR/REVIEW/FAIL = 0/1/3/5` (`constants.py:136-139`); `--gate {pass,review,fail}` default `review` (`__main__.py:158-162`); runtime verified on `P3941R2` (fail → 5 at default gate, 0 at `--gate fail`), `NONEXISTENT999` (no scored papers → 1). No test imports `whisker.__main__` or asserts subprocess exit codes (`16-test-suite-auditor.md` finding). Impact: regressions in gate wiring would not fail `uv run pytest packages/whisker`.

- [MED] **`--all` silently drops un-converted papers; exit code reflects only scored subset.** Evidence: `--all` filters to pids where `get_paper_md_path(pid).exists()` (`__main__.py:184-187`); missing single PID logs warning and returns `EXIT_ERROR` if nothing scored (`__main__.py:207-209`, `220-222`). Runtime: `382 scored` on populated data dir (`00` §3a). Impact: a CI job that runs `whisker --all` after partial convert can **pass while most of the store was never checked**; PR gates should score explicit changed PIDs, not assume `--all` equals full store coverage.

- [MED] **`--json` stdout is machine-pure but array order is not pid-stable for `--all`.** Evidence: `--json` prints only `json.dumps([r.to_dict() ...])` to stdout (`__main__.py:251-253`); human summary skipped; progress bar gated on `stderr.isatty()` (`__main__.py:90-96`). `build_report` sorts by pid (`report.py:89`) but `--json` path does not (`04-determinism-auditor.md`). `WhiskerResult.to_dict()` rounds to 4dp and sorts flags (`score.py:86-112`). Impact: piped `--all --json` is parseable and stderr-safe, but **byte-diffing two full JSON dumps may show reordering** without semantic change; consumers should key by `pid`, not array index.

- [MED] **Regression lanes (golden/guard/facts) cannot gate releases today.** Evidence: corpus has zero real `<pid>.gt.md` / facts members (`00` §4); only the reference-free score path runs on real data. Impact: CI can only enforce the structural + unigram hard gate; no committed baseline regression, exact snapshot, or comprehension facts in the pipeline until corpus work lands.

- [LOW] **Reproducibility across machines holds for scoring logic but requires pinned deps and `--no-reference` for CI speed/stability.** Evidence: determinism invariant (`CLAUDE.md:278-280`); per-paper `to_dict()` stable on re-run (`04-determinism-auditor.md`); ref-free full corpus **86.1s / 382 papers** (`00` §3a). Default oracle runs markitdown per paper (`CLAUDE.md:100-101`) and adds **147/382** advisory review flags (`00` §3b). Dependencies pinned in `pyproject.toml` (`markitdown[pdf]>=0.1.6`, `rapidfuzz>=3.14.5,<4`). Impact: CI should use `uv lock` + `whisker --no-reference --no-write`; cross-machine drift comes from dependency bumps or SQLite row order, not RNG.

## False-pass hypothesis

A conversion that **drops a repeated paragraph or scrambles one table cell** while keeping `unigram_coverage >= 0.85` and passing structural gates would **pass** at `--gate review` (exit 0). Evidence: only **3/382** ref-free fails on unigram floor (`00` §3a); hard gate stops at `UNIGRAM_COVERAGE_FAIL_EDGE` (`score.py:156-160`); Lane 3 facts and GT guard do not run (`00` §4).

## False-fail hypothesis

**P3941R2** (and R3/R4): `uni=0.999`, `drift=0.001`, hard-fail solely on `heading_monotone` — runtime **exit 5** at default gate, **exit 0** only with `--gate fail` (`00` §3c, `gates.py:105-109`). Separately, **P3100R6** is a clean **review** (misaligned region soft flag) that **exit 3** under `--gate pass` but **exit 0** under default `--gate review` (runtime this session).

## What would change my mind

A **checked-in CI recipe** (scoped PID list or convert-then-score, `--no-reference --no-write --json`, explicit `--gate fail` or `review`, fail on `errored > 0`) plus **subprocess integration tests** asserting exit 0/1/3/5 for pass/review/fail/missing-pid fixtures, and one labeled holdout showing the chosen gate's **fail rate matches operator intent** — would flip this to **usable** unconditionally.
