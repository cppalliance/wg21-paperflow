# 15 - The Error-Handling / Robustness Reviewer

**Verdict:** usable-with-conditions — structural gates and guard/calibrate NaN hardening are sound, but `--all` treats scorer exceptions as out-of-band skips that do not fail CI, do not appear in JSON artifacts, and leave stale pass sidecars on disk.
**Confidence:** high

## Findings

- [HIGH] **`--all` errored papers never affect the exit code.** A paper that throws during `score_paper` is logged and skipped (`__main__.py:210-215`), but `_verdict_exit_code` only inspects scored verdicts (`__main__.py:267`, `114-120`). With the default `--gate review`, a batch where every *scored* paper passes can return **exit 0** even when N papers errored — the footer mentions errored count (`report.py:242-243`) but CI that checks exit code alone treats the run as green. Impact: a broken conversion hidden behind an upstream scorer crash looks like a successful QA batch.

- [HIGH] **Errored/skipped papers are absent from machine artifacts; stale sidecars can read PASS.** On write, only successfully scored pids get new sidecars and `build_report(results)` (`__main__.py:232-244`, `report.py:87-95`). A paper that previously passed and then errors on the next run keeps its old `<pid>.whisker.json` while `report.json` simply omits it. Impact: dashboards or humans reading sidecars per paper can see a **misleadingly green PASS** for a paper whisker no longer scored.

- [HIGH] **`--json` stdout carries scored results only — no errored/skipped field.** The JSON array is `[r.to_dict() for r in results]` (`__main__.py:251-253`); errored count exists only in the human footer via `render_summary` (`__main__.py:255-265`, `report.py:228-255`). Impact: automated consumers of `--json` cannot distinguish "all papers passed" from "some papers failed to score"; broken papers vanish from the payload.

- [MED] **Score-path `_decide` has no NaN/inf guard on coverage metrics (unlike guard/calibrate).** Red-team fix #2 added `STATUS_INVALID` in `guard.py:341-349` and `ValueError` in `calibrate.py:170-172`; verified in `test_guard.py:191-197` and `test_calibrate.py:101-102`. But `score.py:156-162` uses `unigram_coverage < edge` with no `math.isfinite` check — in Python, `NaN < 0.85` is **False**, so a corrupt NaN coverage would skip both hard and soft coverage flags and can **PASS** if gates are clean. Impact: guard lane is hardened; the default `whisker --all` score lane is not.

- [MED] **`MissingSourceError` / `MissingPaperMdError` are "skipped", not failed.** Expected for `--all` pre-filter (`__main__.py:184-187`, `207-209`), but explicit PID runs and guard corpus loading use the same warn-and-continue pattern (`__main__.py:281-283`, `571-573`). When a staged `.md` exists but source vanished, the paper is skipped without a fail verdict and without updating artifacts — same stale-sidecar blind spot as errored papers. Impact: partial store corruption does not surface as a whisker FAIL.

- [MED] **Guard corpus shrink is only fail-closed when the paper was in the baseline.** `_load_corpus_pairs` warns and continues on missing candidate md (`__main__.py:281-283`); `diff_rows` then marks baseline-only pids as `missing` hard fails (`guard.py:432-433`, `188-191`). Without a committed baseline, a shrunk corpus runs on a subset with **no signal** that papers were skipped. Impact: first-run / baseline-absent guard can green-light a partial corpus.

- [LOW] **`__main__.py` batch `except Exception` is commented and intentional** (`__main__.py:210-214`) — compliant with repo batch-worker allowance. **`metrics.py` has two uncommented broad catches** in LaTeX normalization (`metrics.py:295-296`, `331-332`); not batch workers, but any pylatexenc/textblock bug silently keeps raw LaTeX, biasing nid/ref_nid rather than failing the paper. Impact: normalization faults degrade metrics quietly; they do not currently crash the scorer.

- [LOW] **Structural gates cover empty/malformed markdown on the score path.** `gates.py:51-75` hard-fails empty body and missing/unterminated front matter; `gates.py:115-150` catches empty code fences and headless tables. `run_gates` runs before verdict fusion (`score.py:203`, `226-235`). Verified by `test_gates.py`. Impact: truncated or front-matter-broken `.md` files fail closed on structure even when content metrics might be ambiguous.

## False-pass hypothesis

Paper **P9999** previously scored PASS and wrote `whisker/p9999.whisker.json`. On the next `whisker --all`, markitdown/oracle conversion throws (or `check_paper_content` raises). The broad except skips the paper (`__main__.py:210-215`), exit code stays driven by other scored papers, **old sidecar still says pass**, and `--json` omits P9999 entirely. A CI job checking only exit 0 and sidecar pass counts would treat P9999 as shippable despite whisker failing to evaluate it this run.

## False-fail hypothesis

Not an error-handling false fail: **P3941R2/R3/R4** fail on `heading_monotone` with `uni=0.999` (`00-EVIDENCE-BASELINE.md` §3c, `gates.py:105-109`) — deterministic gate, not a skip/exception path. Scorer exceptions on these papers would instead produce a false **pass-by-omission** via skip, not a false fail.

## What would change my mind

A controlled run on the 382-paper corpus (`00` §3a) with `--all --no-write` where every injected scorer failure (mock exception in `score_paper`) produces: (1) **non-zero exit** under default `--gate review`, (2) an explicit `errored`/`skipped` pid list in `report.json` and `--json`, and (3) sidecar tombstone or FAIL stamp instead of retaining the previous PASS — demonstrating broken papers cannot disappear from CI-facing artifacts.
