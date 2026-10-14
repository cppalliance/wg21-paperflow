# 27 - CLI contract auditor

**Verdict:** usable-with-conditions — the baseline `--all-pages` plan targets the right extension points (`judge_pdf_extraction`, `run_unit_checks`, fingerprint, sidecar audit), but today's CLI silently drops coverage intent on the default PDF lane and the help text over-promises `--inspect`; the planned flag only becomes trustworthy if implementation wires PDF lane end-to-end, rejects or redefines HTML/unknown sources, rescales timeout/fingerprint, and fails loudly when a coverage flag cannot apply.
**Confidence:** high

## Findings

- [CRITICAL] Baseline root cause 1 confirmed: `exhaustive` is passed only on the text/HTML lane. Evidence: `cli.py:1186-1187` sets `exhaustive=args.exhaustive_units or args.inspect` on `adjudicate_paper`; the PDF branch at `cli.py:1120-1127` calls `judge_pdf_extraction(pid, backend, judge_agent, debug_log=...)` with no coverage kwarg. Impact: `--exhaustive-units` and the coverage half of `--inspect` are dead on the default PDF lane (no warning, no error).

- [CRITICAL] PDF lane never forwards exhaustive even inside `pdf_judge`. Evidence: `judge_pdf_extraction` accepts only `debug_log` (`pdf_judge.py:567-573`); `run_unit_checks` is invoked without `exhaustive=` (`pdf_judge.py:843-850`), so `max_checks` stays at `MAX_UNIT_CHECKS=5` (`unit_judge.py:304`, `constants.py:223`). Impact: even a CLI fix that only touches `cli.py` is insufficient; `pdf_judge.py` must participate or `--all-pages` repeats the same wiring gap.

- [HIGH] `--inspect` help over-promises coverage. Evidence: help says exhaustive is "Implied by --inspect" (`cli.py:261`); on PDF lane `--inspect` only builds the side-by-side report (`cli.py:1174-1178`) and does not set any coverage mode on `judge_pdf_extraction`. Impact: golden-PR operators following documented CLI semantics believe they requested full routed-unit review while the tool runs capped fleet mode.

- [HIGH] Lane routing table for unit-check flags (current code):

  | Flag | PDF lane (`use_pdf_judge`, `cli.py:1041-1042`) | Text lane, PDF source (`--text-only` or judge disabled, `cli.py:944-964`, `adjudicate.py:369-370`) | Text lane, HTML source (`adjudicate.py:367-368`) |
  |---|---|---|---|
  | `--exhaustive-units` | **No effect** (not passed, `cli.py:1120-1127`) | **Partial**: all *routed* units, not all pages (`adjudicate.py:615`, `unit_judge.py:287-304`) | **Partial**: all *routed* `section:N` units (`adjudicate.py:530`, `source_router.py:268-312`) |
  | `--inspect` (coverage) | **No effect** on unit checks (report only, `cli.py:1174-1178`) | **Same as `--exhaustive-units`** via `or args.inspect` (`cli.py:1186-1187`) | **Same as `--exhaustive-units`** |
  | `--inspect` (report) | **Works** (`cli.py:1174-1178`, `1304-1306`) | **Works** (`cli.py:1250-1254`, `1304-1306`) | **Works** |
  | `--review-all` | **PID selection only** (`cli.py:895-898`); no change to unit checking | same | same |
  | `--trace` | **No effect** (only passed to text lane, `cli.py:1185`; PDF branch has no trace path) | **Works** via `adjudicate_paper(..., trace=...)` | **Works** |
  | `--debug` | **Works** (`cli.py:1119-1124`) | **Works** (`cli.py:1184`) | **Works** |

  Impact: three lanes with incompatible flag semantics; the default golden-PR path (PDF + judge service available) is the one where coverage flags lie.

- [HIGH] Planned `--all-pages` validation must reject HTML or define non-page semantics explicitly. Evidence: HTML unit IDs are `section:{index}` (`adjudicate.py:519-520`, `source_router.py:287`); PDF unit IDs are `page:{n}` (`pdf_judge.py:841`, `adjudicate.py:604-605`); `_source_kind` distinguishes `pdf` vs `html` (`cli.py:591-599`). Impact: a PDF-only `--all-pages` flag applied to an HTML paper in a mixed batch either silently no-ops (text lane, router-gated) or misleads operators expecting physical-page coverage; recommend hard error at `_run` startup when `--all-pages` is set and any selected PID is non-PDF, or a separate future `--all-sections` with documented `section:N` reconciliation.

- [MED] Flag precedence for the planned design should be explicit and `--inspect` decoupled from coverage. Evidence: today `--inspect` conflates report generation and exhaustive routing on the text lane only (`cli.py:1186-1187`, `1250-1254`); `--exhaustive-units` is a subset of planned all-pages (routed units vs every `page:1..page_count`, baseline `00-baseline.md:44`). Recommended contract: `--all-pages` implies exhaustive and supersedes `--exhaustive-units`; `--inspect` remains report-only; mutual exclusion or warning if `--exhaustive-units` is redundant under `--all-pages`.

- [MED] Batch mode with `--all-pages` needs per-PID timeout and fingerprint, not batch-global capped budget. Evidence: batch = `len(pids) > 1` (`cli.py:984`); workers are independent per PID (`cli.py:1034-1042`, `1274-1276`); PDF timeout is fixed from `MAX_UNIT_CHECKS=5` (`cli.py:146-151`, `constants.py:223`), not `page_count`. Impact: a 40-page paper in a multi-PID batch hits `asyncio.wait_for` (`cli.py:1121-1126`) before completing serial unit checks; incremental skip (`cli.py:1091-1105`, `_compute_fingerprint` at `cli.py:515-549`) must include a coverage-mode field or capped results mask as all-pages complete.

- [MED] CLI should fail loudly when a coverage flag cannot apply to the resolved lane, not silently ignore it. Evidence: no post-parse validation exists (`cli.py:1324-1325` goes straight to `_run`); concurrency mis-set warns (`cli.py:1017-1025`) but coverage flags do not; judge-service fallback silently moves PDFs to text lane (`cli.py:959-963`), which *would* honor exhaustive but changes semantics without announcing coverage recovery. Impact: operator trust; recommend `sys.exit(1)` (or per-PID error tombstone in batch) when `--all-pages`/`--exhaustive-units` is set, `use_pdf_judge` is True, and the flag is not wired through `judge_pdf_extraction`.

- [LOW] `--text-only` is an undocumented escape hatch that partially restores exhaustive for PDFs. Evidence: `--text-only` disables `judge_agent` (`cli.py:944`), forcing text lane where `exhaustive` is passed (`cli.py:1186-1187`) and `_run_pdf_unit_checks` runs (`adjudicate.py:369-370`, `615`). Impact: operators can accidentally get different coverage behavior without intending review-mode semantics; `--all-pages` should not rely on this side path.

## False-pass hypothesis

Operator runs `whisker-tapetum-llm P1068R11 --inspect` on a 15-page PDF with judge service enabled: monolith sees all pages once (`pdf_judge.py:633-649`), but only up to five router-flagged `page:N` units receive scoped LLM checks (`pdf_judge.py:837-850`, `unit_judge.py:304`); sidecar reports `coverage_complete=True` when `risk_signals` is empty (`pdf_judge.py:831-836`), so the run looks complete while ten pages never received an individual LLM unit judgment.

## False-fail hypothesis

Operator enables planned `--all-pages` on a 40-page PDF without timeout rescale: serial unit checks exceed the capped budget at `cli.py:146-151`, `asyncio.wait_for` raises at `cli.py:1121-1126`, and the CLI writes an error tombstone (`cli.py:1255-1264`) with no partial page-level audit listing which pages were checked before timeout.

## What would change my mind

An implemented `--all-pages` branch in `cli.py` and `pdf_judge.py` with a test on a 15-page fixture (zero router signals) asserting: CLI passes coverage mode into `judge_pdf_extraction`, all 15 `page:N` units are checked, timeout scales with `page_count`, fingerprint differs from capped mode, and startup validation errors when `--all-pages` is combined with a non-PDF PID in the batch.
