# 33 - test-suite-auditor

**Verdict:** usable-with-conditions — the four mandated files already contain strong stub-agent and multi-page PDF fixtures, but none wire CLI flags through the PDF lane or assert `unit_coverage` on `PdfJudgeResult`, so the live unwired `--inspect`/`--exhaustive-units` defect would pass CI unchanged.
**Confidence:** high

## Findings

- [CRITICAL] No test in the mandated quartet would have caught the unwired exhaustive bug (`cli.py` passes `exhaustive` only to `adjudicate_paper` at `1186-1187`, never to `judge_pdf_extraction` at `1122-1125`). Evidence: `test_tapetum_llm.py:2164-2205` patches `judge_pdf_extraction` with a no-kwargs side effect; `test_incremental.py:662-664` mocks the same entry point for debug-only failure paths. Impact: the exact production defect (5/15 pages checked under `--inspect`) is invisible to CI.

- [CRITICAL] Zero tests anywhere under `packages/whisker/tests/` mention `exhaustive`, `all_pages`, or `--exhaustive-units` (repo-wide grep). Evidence: `unit_judge.py:276-304` implements `exhaustive: bool = False` and raises `max_checks` when True, but `pdf_judge.py:843-849` never passes it and no test calls `run_unit_checks(..., exhaustive=True)`. Impact: the cap-bypass logic is dead code from the test suite's perspective.

- [HIGH] PDF lane integration tests stop at `risk_signals` and `defect_groups`; they never assert `unit_coverage`, `coverage_complete`, or `unchecked_unit_ids` on `PdfJudgeResult`. Evidence: `test_source_aware_integration.py:373-421` (`test_risk_signals_populated_in_result`, `test_defect_groups_demote_pass`); `test_pdf_judge.py` has no `unit_coverage` grep hits. Impact: incomplete page coverage can ship while monolith/escalation tests stay green.

- [HIGH] Coverage sidecar fields are tested only at `run_unit_checks` unit scope (AsyncMock, no PDF orchestration) and on the HTML lane. Evidence: `test_source_aware_integration.py:222-249` (`coverage_complete is False`, `len(unchecked_unit_ids) == 5` on cap exceed); `test_source_aware_integration.py:323-324` (`coverage_complete is True` on HTML only). Impact: the assertions `--all-pages` must extend exist in isolation, not on the PDF path the operator uses.

- [MED] LLM faking is cheap and n-page ready: duck-typed `_StubAgent` / `_PagedStubAgent` return canned Pydantic outputs by `output_type` and optional `label`, with real pymupdf PDFs via `_make_pdf` / `_paged_setup`. Evidence: `test_pdf_judge.py:671-706`, `1226-1284`, `1274-1284`; `test_source_aware_integration.py:63-98`, `331-341`. Impact: an 8–15 page all-pages test needs no network; extend `_PagedStubAgent.run` to emit per-page `UnitCheck(unit_id=f"page:{n}")` and count calls.

- [MED] Existing call-count guards encode capped-mode assumptions, not all-pages. Evidence: `test_pdf_judge.py:1476-1478` expects `agent.call_count == 2 + MAX_PAGE_ESCALATIONS` with comment "five bounded unit checks"; `test_pdf_judge.py:1497` expects `call_count == 2` when no flagged pages (no unit checks). Impact: new all-pages tests must use separate fixtures; do not overload these assertions.

- [LOW] Fingerprint and timeout tests cover capped PDF budgets only. Evidence: `test_incremental.py:598-607` (`_pdf_judge_timeout_seconds` uses `MAX_UNIT_CHECKS`, not page count); `test_incremental.py:109-273` (`_compute_fingerprint` has no mode bit for all-pages). Impact: planned separate fingerprint for `--all-pages` has no test anchor yet.

## False-pass hypothesis

A 15-page golden PDF run with `--inspect`: monolith + metadata + 5 routed unit checks completes with `verdict=pass` and default `unit_coverage.coverage_complete=True` (because `pdf_judge.py:831-836` defaults complete when `risk_signals` is empty or checks finish under cap). Every test in the mandated quartet passes; the operator still never got per-page LLM verification on 10 pages.

## False-fail hypothesis

An all-pages test that naively asserts `len(checked_unit_ids) == page_count` without honoring `PAGE_MIN_TOKENS` skips (`constants.py:183`, exercised at `test_pdf_judge.py:1067-1074`) would false-fail on papers whose cover/blank pages are correctly skipped.

## What would change my mind

A mandated-file test invoking `cli._run` with `--inspect` or `--all-pages` on a `.pdf` source that asserts `judge_pdf_extraction` was called with `all_pages=True` or `exhaustive=True` (kwargs inspection, not a full mock replacement).

## Mandate answers (embedded)

### (a) Unwired exhaustive bug — any catching test?

**No.** Root cause is CLI→orchestrator wiring; mandated tests mock at or below `judge_pdf_extraction` and never assert flag pass-through. Miss reason: **no CLI-to-pdf_judge integration test** for PDF flags; mocking level is **too high** (patches discard kwargs) on the PDF path, while **too low** on unit tests (never reach CLI).

### (b) LLM fake pattern and n-page cheap test?

| Pattern | Location | Reuse for all-pages |
|---|---|---|
| `_StubAgent` / `_PagedStubAgent` — async `run()` returns canned `PdfJudgment`, `PageJudgment`, `UnitCheck`, `MetadataOutlineCheck` by `output_type` / `label` | `test_pdf_judge.py:671-706`, `1226-1271` | Yes: queue N `UnitCheck` responses, track `unit_id` |
| `_StubAgent(responses: list)` pop queue | `test_source_aware_integration.py:63-97` | Yes for integration |
| `AsyncMock()` agent | `test_source_aware_integration.py:216-231` | Cap tests only |
| `monkeypatch` on `extract_page_units`, `route_pdf_units` | `test_source_aware_integration.py:350-396` | Control which pages route without heavy PDFs |
| `_make_pdf` / `_paged_setup` real multi-page PDF | `test_pdf_judge.py:57-66`, `1274-1284` | Yes: deterministic n-page corpus |

Same pattern drives cheap n-page test: one `_PagedStubAgent`, one `_make_pdf` with n pages of `_words(...)`, assert N `UnitCheck` invocations and sidecar keys — no pod, no `run_agent`.

### (c) Tests asserting `unit_coverage` keys (in mandated files)

| Field | File:line | Scope |
|---|---|---|
| `coverage_complete is False` | `test_source_aware_integration.py:235`, `:249`, `:323` | `run_unit_checks` cap/missing (235, 249); HTML lane complete (323) |
| `unchecked_unit_ids` (length / content) | `test_source_aware_integration.py:236` | `run_unit_checks` cap exceed only |
| `checked_unit_ids` | `test_source_aware_integration.py:324` | HTML lane only |
| `unit_coverage` dict | — | **Not asserted in any mandated file on PDF path** |

`test_tapetum_llm.py:976-1012` touches inspect **report formatting**, not coverage sidecar semantics.

### (d) TDD test cases and placement

| # | Case | Assert | Belongs in |
|---|---|---|---|
| 1 | **CLI PDF `--inspect` / `--all-pages` wires flag** | `judge_pdf_extraction(..., all_pages=True)` or `exhaustive=True` when argv includes flag; PDF suffix routes to PDF branch | `test_tapetum_llm.py` new `TestCliPdfAllPages` (mirror `TestCliIdealVerification._run` at `2101-2215`) |
| 2 | **Happy path: all pages checked** | N-page PDF (e.g. N=8), all-pages mode, stub returns pass per page; `result.unit_coverage["coverage_complete"] is True`, `checked_unit_ids == [f"page:{i}" ...]`, `agent` unit-check call count == N | `test_pdf_judge.py` new `TestAllPagesCoverage` using `_PagedStubAgent` + `_make_pdf` |
| 3 | **N > MAX_UNIT_CHECKS still complete** | N = `MAX_UNIT_CHECKS + 3`, all-pages on; all N units checked, `coverage_complete is True`, `unchecked_unit_ids == []` (contrast `test_source_aware_integration.py:222-236` capped case) | `test_source_aware_integration.py::TestRunUnitChecksContract` + PDF integration variant in `TestPdfJudgeIntegration` |
| 4 | **Missing packet stays incomplete** | Required `page:7` absent from `unit_text_map`; `coverage_complete is False`, `page:7` in `unchecked_unit_ids`, aggregate `verdict == "review"` on PDF result | `test_source_aware_integration.py` (extend `test_missing_unit_text_forces_review` `:238-249` through `judge_pdf_extraction`) |
| 5 | **Failed unit call → review** | Stub raises on one page; `failed_unit_ids` populated, `coverage_complete is False`, `verdict == "review"` | `test_pdf_judge.py` (agent fail-page set, pattern from `_PagedStubAgent._fail_pages` at `1268-1269`) |
| 6 | **Fingerprint separation** | `_compute_fingerprint(...)` differs when all-pages enabled; `_pdf_judge_timeout_seconds()` scales with page count in all-pages mode | `test_incremental.py::TestComputeFingerprint` + `TestCliBudgetsAndDebug` (`588-607`) |
