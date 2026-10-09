# 06 - Error-Handling-Robustness

**Verdict:** usable-with-conditions — the deterministic-gates-decide + advisory-LLM architecture matches how all 31 reference repos treat LLM signals (00-baseline.md §2, 05-web.md / Q1 / olmOCR-Bench), but our tapetum lane still has stale-sidecar and partial-disclosure gaps that let advisory failures masquerade as success.
**Confidence:** high

## Findings

- [CRITICAL] Rerun failure after a prior successful adjudication leaves a stale `*.tapetum.json` on disk. The batch worker catches all exceptions and skips persistence (`cli.py:865-873`); `_persist_result` / `_persist_lane_result` run only on the success path (`cli.py:812-814`, `850-852`). No tombstone, delete, or error sidecar is written on failure. A paper adjudicated `pass` yesterday that fails today with schema retry exhaustion (`model_backends.py:407-410`) still presents yesterday's pass sidecar as the current advisory result.
  Impact: hidden data loss in the advisory record; fusion and inspect tooling read sidecars as authoritative (`fusion.py:124-142`) and cannot detect a failed rerun — the exact failure class this persona hunts.

- [HIGH] Hard adjudication failures produce no structured sidecar, only footer/log noise. Exception path sets `verdict_str = None`, increments `counts["error"]` (`cli.py:891-892`), logs one ERROR line in batch mode (`cli.py:867-871`), and exits `_EXIT_OK` regardless (`cli.py:59`, `930`). First-run failures are indistinguishable from "never adjudicated" without log scraping; asymmetric with the stale-sidecar case above.
  Impact: failure state is not machine-readable; contradicts the readback lane's better pattern (transport `ERROR` excluded from pass/fail counts, `readback_cli.py:212-215`).

- [HIGH] Pod-down handling is split: pre-flight probe fails loud (`cli.py:545-584`, `sys.exit(1)`), but probe skip when no URL resolves (`cli.py:560-566`) and per-paper mid-batch failures only hit the silent error counter. Health gate mirrors olmocr/docling pre-flight intent (00-baseline.md §2) at batch start only; mid-run pod death leaves the stale-sidecar hole.
  Impact: batch start is honest; batch resume after infra blip is not — supports architecture (deterministic gate unaffected) but weakens advisory-lane trustworthiness.

- [HIGH] Partial-read disclosure demotes `pass` → `review` in decide (`adjudicate.py:314-318`) but never reaches the persisted sidecar. `TapetumResult.to_dict()` omits `partial`, `chunked`, and read-coverage metadata (`models.py:162-185`). Partial demotion is pass-only: `fail`/`review` from a hard-split oversized section stand unchanged (`adjudicate.py:317-318`, `chunking.py:148-150`).
  Impact: a partial adjudication can masquerade as a full-document advisory finding — violates the spirit of root Fidelity ("Never produce a partial result mistakable for a complete one", cited in 05-web.md / Q4 / Deterministic Guardrails) even though tapetum never gates CI.

- [MED] Schema retry exhaustion is honest at the exception layer but orphaned at persistence. `VllmThinkingBackend` raises `MalformedModelOutputError` after bounded retries (`model_backends.py:407-410`); `dispatch` preserves failures as `StepError` (pipeline `CLAUDE.md`: "Step failures fail the pipeline"). CLI firewall catches and swallows without sidecar (`cli.py:865-873`). Batch retry warnings are log-suppressed only (`cli.py:115-136`), not outcome-suppressed — acceptable UX, not a verdict bug.
  Impact: retry exhaustion is truthfully logged but not truthfully recorded; operators must correlate ERROR lines with missing sidecars.

- [MED] Sidecar write failure has no special handler: `_persist_result` / `_persist_lane_result` call `write_text` bare (`cli.py:415-418`, `440-443`). Failure propagates to the same exception path as LLM failure — no partial JSON, no corrupt sidecar. Honest at the file layer; still leaves stale prior sidecar if write fails after a successful in-memory result.
  Impact: write failures are fail-loud per paper but inherit the stale-artifact problem on rerun.

- [MED] Fusion correctly treats `status="error"` tapetum sidecars as unusable (`fusion.py:86-94`, `test_fusion.py:85-92`), falling back to whisker-only — defensible for advisory. The gap is upstream: exception paths never write that stub; only the `_result is None` library fallback sets `status="error"` (`adjudicate.py:532-545`), which the CLI would persist if dispatch completed without raising.
  Impact: fusion logic is sound; persistence idempotency is not.

- [MED] Reference: MinerU `llm_aided` title-leveling fails soft — after retries `_request_title_levels` returns `None`, `_apply_levels_to_blocks` no-ops (`llm_aided.py:221-223`, 00-baseline.md §1 row MinerU). Pipeline falls back to deterministic `doc_title→1`, `paragraph_title→2` with no error artifact (`research/hybrid-llm-scoring/04-mineru-llm.md:14-15`).
  Impact: **defensible for non-gating cosmetic post-processing** (heading levels are not accept/reject); **indicting if copied into a gating lane** — quality signal (LLM title structure) vanishes with no audit trail.

- [MED] Reference: langextract `suppress_parse_errors=True` by default drops failed chunks (`extraction.py:365`, `resolver.py:309-321`, 00-baseline.md §1 row langextract). Run completes with a complete-looking `AnnotatedDocument` and no `partial` flag.
  Impact: **never defensible for gating** — silent entity loss on parse/schema failure; 05-web.md / Q1 (deterministic unit tests over LLM judges) is the ecosystem's explicit rejection of this pattern for correctness-critical paths. Our grounding drop + demotion (`adjudicate.py:283-310`) is the inverse and closer to fail-safe.

- [MED] Reference: docling emits `ConversionStatus.PARTIAL_SUCCESS` and still exports assembled output on timeout, failed pages, or VLM `stop_reason` in `{LENGTH, CONTENT_FILTERED}` (`vlm_pipeline.py:245-274`, `base_models.py:85-91`, 00-baseline.md §1 row docling; `research/per-page-judging/13-docling-analyst.md:18`).
  Impact: **defensible for a conversion engine optimizing yield** (partial markdown beats nothing); **not defensible for a QA gate** — would false-pass localized page loss. Our `adjudicate.py:314-318` partial pass-demote is the docling analog inverted for advisory honesty, but incomplete without sidecar disclosure.

- [LOW] Reference: marker benchmark LLM scorer failures are skipped; CI gates only deterministic heuristic/TEDS (`benchmarks/overall/scorers/llm.py:94-134`, `overall.py:61-63`, 00-baseline.md §1; 05-web.md / Q5 / Marker CI gates heuristic only). olmOCR never hard-fails a page — temp escalation then pdftotext fallback (`pipeline.py:329-332`, 00-baseline.md §1).
  Impact: industry-standard **advisory/fallback** patterns; importing them into whisker `--gate` would corrupt deterministic verdicts — confirms our lane split is evidence-aligned.

## False-pass hypothesis

Paper P was adjudicated `pass` in an earlier tapetum run. A rerun hits JSON retry exhaustion (`model_backends.py:407-410`). The batch firewall logs one ERROR line and writes no sidecar (`cli.py:865-873`). The old `pass` sidecar remains. Fusion and inspect read only sidecars and report whisker-only or stale tapetum-pass — no signal that the latest run failed.

## False-fail hypothesis

An oversized H2 section is hard-split (`chunking.py:148-150`, `partial=True`). One chunk sees a table fragment without headers; triage returns `fail` on the `tables` axis. Partial demotion does not apply because verdict is not `pass` (`adjudicate.py:317-318`). Sidecar records `suggested_verdict=fail` with no `partial` field — a false fail driven by incomplete read, not full-document corruption.

## What would change my mind

A batch rerun test demonstrating that on adjudication failure the CLI either (a) deletes or tombstones any existing `{pid}.tapetum.json`, or (b) writes an explicit error sidecar with `status="error"` and the exception class — and that inspect/report tooling surfaces it — would flip the stale-sidecar and no-sidecar findings to resolved and move the architecture verdict toward plain **usable**.

## Fail-soft pattern ledger (advisory vs gating)

| Pattern | Repo anchor | Defensible advisory? | Defensible gating? |
|---|---|---|---|
| LLM post-step no-op on failure | MinerU `llm_aided.py:221-223` | Yes (cosmetic, det fallback) | No (signal loss) |
| Drop failed chunks, continue run | langextract `extraction.py:365`, `resolver.py:309-321` | Only with explicit `partial` + consumer filter | No |
| Export on `PARTIAL_SUCCESS` | docling `vlm_pipeline.py:245-274` | Yes (conversion yield) | No |
| Skip failed LLM benchmark scorer | marker `overall.py:61-63` | Yes (CI uses det axes) | N/A (already non-gating) |
| Page fallback lane | olmocr `pipeline.py:329-332` | Yes (conversion continuity) | No for QA accept |
| Ignore errored tapetum in fusion | whisker `fusion.py:86-94` | Yes | N/A (advisory by design) |
| Stale sidecar on rerun failure | whisker `cli.py:865-873` | No | No |
| Partial pass-demote without sidecar flag | whisker `adjudicate.py:314-318`, `models.py:162-185` | Partially (verdict demoted, not disclosed) | No |
