# C04 Fail-Not-Partial

**Role**: Audit fault handling so that failures are loud and no partial result is mistakable for a complete one, on both the deterministic and advisory lanes.
**Audited state**: whisker 0.5.0, working tree, manifest b9ad8ab0a464aaaf030bfb9a9576bdeed986f6510b83dbd87945bdd7fe68f771 (HEAD 0d18a65 + 7205 uncommitted insertions).
**Gates**: G2 (Fidelity: fail not partial), D3 (Batch isolation).

## 1. Scope

Verify errors on the deterministic path produce a clean failure (never a false pass), that batch isolation prevents one paper's failure from aborting a fleet run, that the advisory lane's error tombstones and malformed-sidecar handling cannot be mistaken for a complete adjudication, and that this holds under live fault injection, not only synthetic exception tests.

## 2. Commands and Exits

| Evidence | Command / source | Exit |
|---|---|---|
| E1 | offline suite (context) | 1 (unrelated failures, see C02) |
| E8 | `whisker --all --json --no-write`, 381 papers | 5 |
| E11 | fault injection, 5 cases, deterministic path | 1 (x4), 5 (x1) |
| E12 | `--no-write` file-count check | 0 files added/changed |
| E13 | S6, nonexistent service slot | **1** (operational error, no verdict emitted) |

## 3. Current Evidence

### 3.1 Deterministic fleet run never silently drops a failing paper (live)

E8: `whisker --all --json --no-write` scored 381 papers with exit code 5 (fleet-worst verdict is `fail`, 20 papers, 5.2%). The run completed and reported all 381 results (188 pass, 173 review, 20 fail; §"Papers scored: 381" matches the corpus size), i.e. no paper silently vanished from the batch. `__main__.py:219-234` wraps each `score_paper` call in a per-paper `try/except`: `MissingPaperMdError`/`MissingSourceError` increments `skipped` and logs a warning (`__main__.py:224-226`); any other `Exception` increments `errored` and logs via `logger.exception` (`__main__.py:227-232`), inside a `finally` that always advances the progress bar (`__main__.py:233-234`). Only when `not results` (every paper failed) does the run return `EXIT_ERROR` (`__main__.py:237-239`); otherwise errored/skipped counts are logged and the run proceeds to report the successes.

### 3.2 No fault on the deterministic path produces a false exit 0 (live)

E11, five independent fault-injection cases:

| Case | Exit code | Note |
|---|---|---|
| unknown pid | 1 | error, not a pass |
| empty markdown (`score-file`) | **5** | scored as a fidelity fail, not skipped |
| binary bytes as markdown | 1 | error |
| corrupt PDF as `--source` | 1 | error |
| missing markdown file | 1 | error |

No case exits 0. The empty-markdown case is the load-bearing one for "fail not partial": an empty document is not silently treated as "nothing to score" (which would risk a vacuous pass); it is run through `score-file`'s own gate logic (`__main__.py:340,378-394`) and the `non_empty` gate (`gates.py:51-57`) fails it, producing a hard flag and exit `EXIT_FAIL` (5).

### 3.3 `--no-write` is inert; partial writes cannot occur when writes are disabled

E12: `--no-write` on a real paper added 0 files and changed 0 files in `<data>/whisker/det`. `__main__.py:244` gates the entire sidecar/report-write block behind `if not args.no_write`, so there is no code path where a partial write (e.g. sidecar written, report not written, or vice versa) could occur under this flag; the flag simply skips the write block in its entirety (`__main__.py:244-266`).

### 3.4 Advisory lane: per-paper firewall and error tombstones (code, not re-run live this pass)

`tapetum_llm/cli.py`'s `_adjudicate_one` wraps each paper in its own `try/except Exception`, logs, and calls `_write_error_tombstone` (per Auditv2 C04 §3.2-3.3, not independently re-read line-for-line in this pass; carried forward as unchanged since no code diff evidence contradicts it in this run's ledger). The tombstone payload is `{"pid", "status": "error", "error": type(exc).__name__}` with no `suggested_verdict`/`confidence` field, so `_validate_tapetum_sidecar` (`fusion.py:128-151`) rejects it structurally: an error tombstone has `sanitized.get("status") == "error"`, which `_validate_tapetum_sidecar` explicitly early-returns as valid-but-unusable (`fusion.py:142-143`), and `_tapetum_is_usable` (`fusion.py:154-164`) then returns `False` for any tapetum dict with `status == "error"` (`fusion.py:158-159`), forcing fusion to fall back to `whisker_only` (the deterministic verdict alone, §3.5 below).

### 3.5 Live confirmation: an operational error on the advisory lane emits no verdict, exit 1 (E13, S6)

E13 scenario S6 (nonexistent service slot) is the only one of ten live scenarios to exit non-zero: exit **1**, 2.9s, "operational error, no verdict emitted." This is the live analogue of §3.4's tombstone mechanism: when the advisory call cannot even complete, the CLI does not fabricate a `pass`/`review`/`fail` and does not exit 0. Compare S1-S5, S7-S10, which all exit 0 despite several of them carrying advisory `fail`/`review` verdicts (S5 both lanes fail; S9 `--fuse-only` runs no LLM call at all and still exits 0), confirming that 0 vs 1 for `whisker-tapetum-llm` tracks "did the call complete" (§ documented separate contract, Auditv2 C01 §6), never the CONTENT of the verdict.

### 3.6 Malformed-sidecar validation (fusion.py, re-read this run)

`_validate_whisker_sidecar` (`fusion.py:115-125`): rejects non-dict, missing/empty `pid`, or a `verdict` not in `{pass, review, fail, "?"}`. `_validate_tapetum_sidecar` (`fusion.py:128-151`): rejects non-dict or missing/empty `pid`; sanitizes a non-dict `fingerprint` field by dropping it (`fusion.py:136-140`); for non-error sidecars, rejects a `suggested_verdict` not in the recognized set or a non-finite `confidence` (`_finite_float`, `fusion.py:104-112`, rejects bool, non-numeric, `inf`/`nan`). `fuse_verdicts` (`fusion.py:354-358`) substitutes a neutral stub `{"pid": "", "verdict": "?"}` when whisker validation fails, and leaves `tapetum = None` when tapetum validation fails; `_tapetum_is_usable(None)` returns `False` (`fusion.py:156-157`), routing to `whisker_only`. A confidence-0, no-`axis_findings` stub is also treated as unusable (`fusion.py:162-164`), preventing a partially-completed LLM call (e.g. a truncated response that parsed to a technically-valid but empty structured output) from being read as a real advisory opinion.

## 4. Findings

| # | Finding | Severity | Confidence |
|---|---|---|---|
| F1 | Live fleet run (E8, 381 papers) completed with no silent paper loss; per-paper firewall confirmed by code (`__main__.py:219-234`) | Informational | HIGH |
| F2 | Live fault injection (E11, 5 cases) never produces exit 0; empty markdown correctly fails rather than vacuously passing | Informational | HIGH |
| F3 | `--no-write` (E12) is implemented as a single guard around the entire write block, structurally preventing a half-written sidecar/report pair | Informational | HIGH |
| F4 | Live advisory-lane operational failure (E13 S6) emits no verdict and exits 1, matching the tombstone-rejection code path traced in `fusion.py` | Informational | HIGH |
| F5 | Malformed/error tapetum sidecars are structurally rejected by `_validate_tapetum_sidecar`/`_tapetum_is_usable`, falling back to the deterministic verdict alone | Informational | HIGH |
| F6 | Advisory-lane debug-transcript-before-tombstone ordering (`finally` block flush) and partial-read demotion (`state.partial` forcing non-pass) were NOT independently re-verified with fresh code reads or live evidence this run; carried forward from Auditv2 unchanged | Medium | MEDIUM |

## 5. False-Pass Hypothesis

**Could a partial or errored result be mistaken for a complete one?**

Two vectors tested. (1) Deterministic lane: could a fault silently score as a clean pass? Refuted live across 5 fault classes (E11) and structurally for the fleet loop (§3.1): the `if not results` check only returns `EXIT_ERROR` when literally every paper failed, so a single paper's error never gets folded into a fabricated success, and it never produces a false 0. (2) Advisory lane: could an error tombstone carry a plausible-looking verdict field that fusion would treat as real? Refuted by code: the tombstone payload has exactly three keys (`pid`, `status`, `error`), no `suggested_verdict`/`confidence`, and `_validate_tapetum_sidecar` requires those fields to be present and well-typed for any non-error sidecar; an error-status sidecar is explicitly short-circuited to unusable before those checks even run (`fusion.py:142-143,158-159`). Live confirmation (E13 S6) shows the CLI itself refuses to exit 0 on an operational failure, so the tombstone path and the exit-code path are consistent with each other, not just individually plausible.

## 6. Gate/Dimension Mapping

**PROPOSED, not a settled verdict.** G2 (Fidelity: fail not partial): holds under live fault injection on the deterministic path (E11) and live operational-failure testing on the advisory path (E13 S6); both fail loudly (non-zero exit, or a hard-flagged fail verdict) rather than silently. D3 (Batch isolation): holds under live fleet evidence (E8, 381/381 papers accounted for, no silent drop) and code trace (`__main__.py:219-234`). PROPOSED status: **holds**, with one qualification the planner should weigh: the debug-transcript-preservation-before-tombstone claim (Auditv2 F3, `finally` block ordering) and the partial-read-demotion claim (Auditv2 F6, `state.partial` forcing non-pass) are carried forward from Auditv2 without fresh live or code confirmation in this run; see Limitations.

## 7. Limitations

- `tapetum_llm/cli.py`'s `_adjudicate_one`, `_write_error_tombstone`, and the `finally`-block debug-flush ordering were not re-read line-for-line in this pass; this file relies on Auditv2's citations (`cli.py:1246-1258,667-691,1127-1144`) for those specifics, cross-checked only indirectly via the live E13 S6 result and the `fusion.py` validation code re-read this run.
- The partial-read demotion (`adjudicate.py::_custom_decide`, `state.partial and suggested_verdict == VERDICT_PASS -> VERDICT_REVIEW`) was not independently re-verified this run; carried forward from Auditv2 F6 as an unconfirmed-this-pass claim.
- Malformed sidecar handling was tested this run only via code trace (`fusion.py`) and the E13 S6 live operational failure; no live test wrote a hand-corrupted on-disk JSON sidecar and re-ran fusion against it.

## 8. Conclusion

The fail-not-partial claim holds on the evidence gathered this run. Live fault injection on the deterministic path (E11) and a live fleet run (E8) confirm no fault produces a false exit 0 and no paper is silently dropped from a batch. Live advisory-lane operational failure (E13 S6) confirms the same discipline on the LLM side: an incomplete call emits no verdict and a non-zero exit, and the fusion validation code (`fusion.py`) structurally rejects malformed or error-status sidecars before they could be read as a real opinion. Two specific sub-claims (debug-transcript-before-tombstone ordering, partial-read demotion) are carried forward from Auditv2 without fresh verification this run and should be flagged to the planner as unconfirmed-this-pass rather than re-asserted as newly proven.

## 9. Delta vs Auditv2

Auditv2's C04 (`Auditv2/code-c04-fail-not-partial.md`) stated in its own §7 Limitations: "Runtime proof BLOCKED: cannot verify live error-tombstone writes or debug transcript preservation during actual LLM failures," and "Malformed sidecar handling tested only with synthetic dicts in `test_fusion.py`, not with corrupted on-disk JSON files." This run closes the first limitation partially: E13 S6 is a live operational failure on the advisory lane (nonexistent service slot), confirming the exit-code and no-verdict-emitted behavior live, though it does not specifically confirm debug-transcript-preservation ordering (that sub-claim remains carried forward, unconfirmed this pass, per §7 above). The second limitation (corrupted on-disk sidecar JSON) is still open; this run did not close it either, it only re-confirmed the validation code shape via a fresh `fusion.py` read. The deterministic-side evidence upgraded materially: Auditv2 had no live fault-injection matrix at all (blocked by credential denial); this run's E11 (5 live fault classes) and E8 (381-paper live fleet run) are new, live, first-time evidence for this gate that Auditv2 could not produce.
