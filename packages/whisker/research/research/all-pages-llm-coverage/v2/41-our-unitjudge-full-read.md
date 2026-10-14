# 41 - unit_judge.py + source_router.py (C3b unit side)

**Claims tested:** C3 (subset C3b, unit-side only)

**Exhaustive:** yes (both scoped files read in full; caller/fusion consequence paths traced for empty-router and `run_unit_checks` return-`None` semantics only)

## Method

Files read in full (line counts verified):

- `packages/whisker/src/whisker/tapetum_llm/unit_judge.py` (698 lines on disk; charter cited 624, delta is post-51cb704 growth in same paths)
- `packages/whisker/src/whisker/tapetum_llm/source_router.py` (356 lines on disk; charter cited 312)

Supporting reads for C3b consequence chain (not full-file):

- `packages/whisker/src/whisker/tapetum_llm/pdf_judge.py:825-922`
- `packages/whisker/src/whisker/tapetum_llm/adjudicate.py:405-441,516-617`
- `packages/whisker/src/whisker/tapetum_llm/fusion.py:182-215`
- `packages/whisker/src/whisker/tapetum_llm/constants.py:177-227`
- `packages/whisker/tests/test_source_aware_integration.py:214-220`

Search commands:

```
rg run_unit_checks packages/whisker
rg coverage_complete packages/whisker
rg unit_selection packages/whisker
rg MAX_UNIT_CHECKS packages/whisker
```

## Inventory

### `run_unit_checks` call sites

| File:line | Role |
|---|---|
| `unit_judge.py:268` | Definition; returns `UnitJudgeResult \| None` |
| `pdf_judge.py:843` | PDF lane; called only inside `if risk_signals:` (`839`); no `exhaustive` kwarg |
| `adjudicate.py:523` | HTML lane; called only after `if not risk_signals: return` (`516-517`); passes `exhaustive=state.exhaustive` |
| `adjudicate.py:608` | PDF lane (adjudicate path); called only after `if not risk_signals: return` (`601-602`); passes `exhaustive=state.exhaustive` |
| `tests/test_source_aware_integration.py:215,227,241` | Contract tests |
| `tests/test_unit_judge.py:148,162,192,223,255,298,330,368,402,559,601,644,687,721` | Unit tests |

### (a) Empty `risk_signals` → `None` and consequences

| File:line | Finding |
|---|---|
| `unit_judge.py:287-288` | `if not risk_signals: return None` — exact guard; no `UnitJudgeResult` constructed |
| `unit_judge.py:280-281` | Docstring states monolith stands alone when no signals |
| `unit_judge.py:241` | `UnitJudgeResult.__init__` default `coverage_complete: bool = True` — never used on empty path because constructor not reached |
| `pdf_judge.py:831-836` | Before routing: `unit_coverage = {"coverage_complete": True, "checked_unit_ids": [], ...}` |
| `pdf_judge.py:837` | `risk_signals = route_pdf_units(...)` |
| `pdf_judge.py:839-850` | `if risk_signals:` — empty router skips `run_unit_checks`; defaults at `831-836` persist |
| `pdf_judge.py:851-860` | `if unit_result is not None:` — overwrites coverage only when unit judge ran |
| `adjudicate.py:516-517` | HTML: `if not risk_signals: return` — `state.unit_result` stays `None` |
| `adjudicate.py:601-602` | PDF: `if not risk_signals: return` — same |
| `adjudicate.py:434-440` | When `state.unit_result is None`: `unit_coverage = {"coverage_complete": True, "checked_unit_ids": [], "unchecked_unit_ids": [], "failed_unit_ids": []}` |
| `fusion.py:191-193` | `_source_aware_requires_review`: returns `True` (fail-closed) only if `coverage.get("coverage_complete") is not True`; default `True` passes gate |
| `fusion.py:194-195` | Also fail-closed on non-empty `unchecked_unit_ids` or `failed_unit_ids` — vacuously pass when both empty |
| `test_source_aware_integration.py:214-220` | `test_no_signals_returns_none` asserts `run_unit_checks(..., risk_signals=[])` → `None` |

**Consequence summary:** `run_unit_checks` never emits `coverage_complete=True` on empty input; it emits nothing. Production lanes never call it with empty signals (they short-circuit first). The C3b false-complete behavior is entirely from caller defaults (`pdf_judge.py:831-836`, `adjudicate.py:435-440`) that fusion treats as complete coverage (`fusion.py:192`).

### (b) Selection pipeline (exact semantics)

| File:line | Step |
|---|---|
| `unit_judge.py:290-299` | Sort all `risk_signals` by tuple: `(severity_rank[severity] default 3, _unit_id_sort_key(unit_id), signal_type, detail)`; ranks: critical=0, high=1, medium=2, low=3 |
| `unit_judge.py:122-133` | `_unit_id_sort_key`: `page:N` / `section:N` → `(N, unit_id)`; non-numeric suffix → `(999999, unit_id)` |
| `unit_judge.py:300-303` | Group into `signals_by_unit[unit_id]` preserving sorted order; `risky_unit_ids = list(signals_by_unit)` (insertion order = first appearance in sorted signal stream) |
| `unit_judge.py:304` | `max_checks = len(risky_unit_ids) if exhaustive else MAX_UNIT_CHECKS` |
| `constants.py:223` | `MAX_UNIT_CHECKS = 5` |
| `unit_judge.py:305-307` | `selected_unit_ids = _select_units_with_quotas(signals_by_unit, risky_unit_ids, max_checks)` |
| `unit_judge.py:147-174` | `_select_units_with_quotas`: Phase 1 — walk `risky_unit_ids` in order; select unit if it introduces ≥1 new `signal_type` not yet in `signal_types_covered`, until `len(selected) >= max_checks`. Phase 2 — walk `risky_unit_ids` again; append unselected units until cap. Return `selected` (length ≤ `max_checks`) |
| `unit_judge.py:308-311` | `quota_selected = set(selected_unit_ids)`; initial `unchecked_unit_ids` = risky units not in `quota_selected` |
| `unit_judge.py:276` | `exhaustive: bool = False` default; when `True`, `max_checks == len(risky_unit_ids)` so all risky units selected unless Phase 1+2 cap stops early (never early when `max_checks == len(risky_unit_ids)`) |
| `unit_judge.py:317-341` | Loop `for unit_id in selected_unit_ids`: missing `unit_text_map` entry → append to `unchecked_unit_ids`, skip LLM; success → `checked_unit_ids`; exception → `failed_unit_ids` (not checked, not unchecked initially) |

### (c) `coverage_complete` / checked / unchecked / failed (end of `run_unit_checks`)

| File:line | Computation |
|---|---|
| `unit_judge.py:312-313` | `failed_unit_ids`, `checked_unit_ids` start empty |
| `unit_judge.py:320-323` | Selected unit with empty/missing source text: `unchecked_unit_ids.append(unit_id)`; no LLM call |
| `unit_judge.py:336` | Successful LLM: `checked_unit_ids.append(unit_id)` |
| `unit_judge.py:337-341` | Exception: `failed_unit_ids.append(unit_id)` |
| `unit_judge.py:376-380` | `coverage_complete = (len(checked_unit_ids) == len(risky_unit_ids) and not unchecked_unit_ids and not failed_unit_ids)` — requires every risky unit checked, zero unchecked (quota-skipped OR missing source), zero failed |
| `unit_judge.py:390-394` | `verdict = "review"` if `defect_groups` OR `not coverage_complete` OR `evidence_uncertain`; else `"pass"` |
| `unit_judge.py:381-389` | `evidence_uncertain` if any `CANDIDATE_AMBIGUOUS` or `source_ungrounded` in summary, or any disposition `source_status` not in `(None, GROUND_EXACT)` |
| `unit_judge.py:423` | `unchecked_unit_ids=sorted(set(unchecked_unit_ids))` — dedupe quota-skipped + missing-source |
| `unit_judge.py:396-414` | `unit_selection`: per `uid` in `risky_unit_ids`, `status` = checked / failed / unchecked; `reason` = `"exhaustive"` if exhaustive else `"quota"` if uid ∈ `quota_selected` else `"priority"` |
| `unit_judge.py:421-424` | Passed through to `UnitJudgeResult` |

### (d) Prompt contract vs all-pages neutral audit

**`_UNIT_CONVERSION_CONTRACT` full text** (`unit_judge.py:67-76`):

```
The converter operates under a fixed contract. The following are CORRECT conversion behavior, never defects and never missing content:
- Title-block metadata is converted into YAML front matter.
- The table of contents is DELIBERATELY REMOVED; body headings replace it.
- Page numbers, running headers, and running footers are dropped.
- Text inside figures/images is legitimately imaged.
- Prose paragraphs are unwrapped; words are dehyphenated.
- Wording markup (<ins>/<del>, :::wording) is the deliverable.
```

**`UNIT_CHECK_SYSTEM_PROMPT` full text** (`unit_judge.py:93-120`, contract interpolated at `101`):

```
You are a conversion-fidelity unit checker. You receive:
1. SOURCE TEXT: one bounded region (a page or section) from the source document.
2. CANDIDATE MARKDOWN: the full converted document.
3. RISK SIGNAL: why this unit was flagged for checking.

Your task: determine whether the candidate faithfully preserves the source content for THIS UNIT ONLY. Report specific defects.

<file:67-76 contract block>

Defect types: qualifier_omission (missing keywords like constexpr), heading_drift (wrong heading level), content_omission (text/figures missing), table_corruption (table structure broken, cells shifted or content changed), cell_content_wrong (specific table cell has different text than source), label_not_stripped (structural label like section number retained in heading), punctuation_loss (periods/operators dropped), entity_artifact (HTML entities in output), toc_leak (TOC content in body), code_loss (code block missing/broken).

For each defect group, provide an `affected_count`: the total number of instances of that specific defect in the unit, not just the quoted example. This count must be verifiable against the source text.

Verdict:
- pass: unit content faithfully preserved.
- review: minor defects a human should check.
- fail: substantial content missing or corrupted in this unit.

### Output discipline (binding)
reasoning at most 40 words. source_quote must be verbatim from the SOURCE TEXT. affected_count must be exact.
```

**Gap vs all-pages neutral audit** (planned `--all-pages` / golden-review: compare every physical page, fail-closed on uncovered pages):

| Issue | Evidence |
|---|---|
| Prompt is tomd-contract-biased, not neutral | Contract pre-declares TOC removal, chrome drop, unwrapping, wording markup as non-defects (`unit_judge.py:67-76`) |
| Judge sees full candidate MD, not page-scoped candidate | User message sends entire `candidate_md` (`unit_judge.py:679-680`) — no mechanical isolation of candidate slice for page N |
| Closed defect-type vocabulary | Only listed types (`unit_judge.py:102-109`); types outside list rely on LLM schema (`UnitCheck` model — NOT VERIFIED in this read) |
| Risk signal conditions prompt focus | `signal_detail` joins router `detail` strings (`unit_judge.py:331`, `676`) — all-pages required units would need synthetic signal text |
| Post-LLM filtering drops most claimed defects | Only defects with `candidate_status == CANDIDATE_NOT_FOUND` and `source_status == GROUND_EXACT` enter `verified_defects` (`unit_judge.py:356-360`) |
| Count filter can zero groups | Groups with `count_status == "verified"` and `verified_delta == 0` removed (`unit_judge.py:368-375`) |
| `pass` verdict does not mean "all pages audited" | `pass` requires routed subset fully checked with no verified defects (`unit_judge.py:390-394`); unrouted pages never enter `risky_unit_ids` |

### (e) `route_pdf_units` — every `signal_type` and trigger

| signal_type | File:line | Trigger (all must hold where noted) |
|---|---|---|
| `token_delta` | `source_router.py:184-207` | For each token in `_CPP_KEYWORDS` (`45-48`): `deficit = source_document_words[token] - candidate_words[token]`; emit if `deficit >= TOKEN_DELTA_THRESHOLD` (`constants.py:219-221`, value 5). One signal per qualifying token. `unit_id = page:{representative.page}` where `representative` is first `page_units` entry whose page text contains that token as whole word (`188-197`). Severity `medium`. Document-wide counts, page-local unit_id. |
| `low_recall` | `source_router.py:211-222` | Per `unit` in `page_units`: if `unit.content_tokens >= PAGE_MIN_TOKENS` (`constants.py:183`, value 50) AND `content_recall(candidate_md, unit.text) < PAGE_RECALL_FLOOR` (`constants.py:177`, 0.90). Severity `high`. |
| `missing_captions` | `source_router.py:224-234` | Per unit: any `caption` in `unit.caption_lines` where `_text_key(caption) not in candidate_surface` (`candidate_surface = _text_key(candidate_md)`, `174-175`). Severity `medium`. |
| `heading_drift` | `source_router.py:236-255` | Per unit: any `(title, _font_size)` in `unit.heading_candidates` where normalized title key not in set of normalized candidate section title keys from `_parse_markdown_sections` (`175-178`, `239-244`). Severity `medium`. |
| `table_presence` | `source_router.py:257-263` | Per unit: if `unit.has_tables`. Severity `high`. No cell comparison here. |

**Closed-list blind-spot claim:** CONFIRMED for `route_pdf_units` — exactly five `signal_type` strings above; no other emitters in `source_router.py:167-265`. Pages matching none of these triggers produce zero signals and are never routed.

**Not in `route_pdf_units` but in PDF adjudicate path:** `table_corruption` appended in `adjudicate.py:580-597` from `compare_pdf_tables` cell diffs; severity `critical`. Not emitted by `route_pdf_units`.

### Other complications for required-units (all pages)

| File:line | Complication |
|---|---|
| `unit_judge.py:287-288` | Empty router → no unit lane; callers default complete (`see (a)`) |
| `unit_judge.py:304-311` | `MAX_UNIT_CHECKS=5` quota unless `exhaustive=True`; quota-skipped units → `coverage_complete=False` but only among *routed* units |
| `pdf_judge.py:843-850` | PDF `judge_pdf_extraction` never passes `exhaustive` (C3a adjacent) |
| `source_router.py:211-212` | `low_recall` skipped when `content_tokens < PAGE_MIN_TOKENS` — short pages invisible to router |
| `source_router.py:184-207` | `token_delta` attaches one representative page per keyword, not every page with deficit |
| `adjudicate.py:468` | `unit_selection` taken from `state.unit_selection` which is never assigned from `unit_result.unit_selection` (grep: no `state.unit_selection =` in repo) — selection audit lost on adjudicate path |
| `unit_judge.py:398-411` | `unit_selection.reason`: selected units labeled `"quota"`, unselected labeled `"priority"` — inverted naming vs intuition |
| `unit_judge.py:343-375` | Mechanical evidence pipeline can demote LLM findings before verdict |
| `unit_judge.py:679-680` | Full-document candidate in every unit call — cost/latency scale with doc size × page count for all-pages |
| `constants.py:223-227` | Comment states fleet default caps; exhaustive intended for golden-PR but PDF path unwired |

## Verdict on the claim(s)

**C3b (unit side): PARTIALLY CONFIRMED**

- **CONFIRMED:** Empty `route_pdf_units` → zero checked units → `coverage_complete=True` with empty ID lists → fusion `_source_aware_requires_review` does not fail-closed on coverage (`pdf_judge.py:831-836`, `adjudicate.py:435-440`, `fusion.py:192`).
- **REFUTED (narrow):** `run_unit_checks` does **not** return `coverage_complete=True` on empty `risk_signals`; it returns `None` at `unit_judge.py:287-288` without constructing `UnitJudgeResult`.
- **REFUTED (narrow):** Production code never invokes `run_unit_checks` with empty `risk_signals` (`pdf_judge.py:839`, `adjudicate.py:516-517`, `601-602`); the `None` return is API/test-only for direct callers.

Root defect for C3b is caller-side default-as-complete, not unit_judge's empty guard.

## Coverage gaps

None for scoped files (`unit_judge.py`, `source_router.py`). `UnitCheck` Pydantic schema (defect_type enum enforcement) not read — marked NOT VERIFIED where relevant above.

## What could still hide a counterexample

- A code path that constructs `UnitJudgeResult(coverage_complete=True)` with empty checks outside the traced defaults — not found in unit_judge empty path.
- HTML/PDF adjudicate divergence: table_corruption signals only on adjudicate PDF path (`adjudicate.py:580-597`), not in `pdf_judge.py::judge_pdf_extraction` router (`pdf_judge.py:837` only calls `route_pdf_units`).
- Fusion v5 sidecars without `unit_coverage` key bypass `_has_source_aware_data` gate — NOT VERIFIED in this read.

## Surprises (non-obvious)

1. `run_unit_checks` `None` return is unreachable from production callers (they guard before call).
2. `adjudicate` never copies `unit_result.unit_selection` into `state.unit_selection`.
3. `unit_selection.reason` labels selected units `"quota"` and capped-out units `"priority"`.
4. `token_delta` is document-scoped but emits a single page unit per keyword.
5. `table_corruption` signal exists only on adjudicate PDF path, not in `route_pdf_units` or `pdf_judge` routing.
