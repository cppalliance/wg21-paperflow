# 42 - our pdf_judge + textlayer (C3b PDF scope)
**Claims tested:** C3b (pdf side)
**Exhaustive:** yes (for `pdf_judge.py` 923 lines and `textlayer.py` 356 lines, read in full; partial cross-reads of `source_router.py`, `unit_judge.py`, `fusion.py`, `cli.py` for call-site and fusion-trust verification only)

## Method

Files read in full:
- `packages/whisker/src/whisker/tapetum_llm/pdf_judge.py` (923 lines)
- `packages/whisker/src/whisker/tapetum_llm/textlayer.py` (356 lines)

Partial reads (cross-reference only):
- `packages/whisker/src/whisker/tapetum_llm/source_router.py` (`route_pdf_units`, lines 167–265)
- `packages/whisker/src/whisker/tapetum_llm/unit_judge.py` (`run_unit_checks`, lines 268–427)
- `packages/whisker/src/whisker/tapetum_llm/fusion.py` (`_source_aware_requires_review`, lines 182–215)
- `packages/whisker/src/whisker/tapetum_llm/cli.py` (PDF vs text call sites, lines 1118–1191)

Search commands run:
```
rg "PAGE_MIN_TOKENS" packages/whisker
rg "route_pdf_units|run_unit_checks|unit_coverage|coverage_complete" packages/whisker
rg "judge_pdf_extraction|exhaustive|all_pages" packages/whisker
rg "checked.*page_count|page_count.*checked" packages/whisker
```

## Inventory

### (a) `judge_pdf_extraction` signature — no all_pages / exhaustive parameter

| Location | Role |
|---|---|
| `pdf_judge.py:567–573` | `async def judge_pdf_extraction(pid, backend, agent, *, debug_log=None) -> PdfJudgeResult` — only optional kwarg is `debug_log` |
| `pdf_judge.py:94–105` | `__all__` exports `judge_pdf_extraction`; no coverage-mode symbol |
| `cli.py:1121–1126` | PDF branch calls `judge_pdf_extraction(pid, backend, judge_agent, debug_log=judge_debug)` — no `exhaustive` |
| `cli.py:1186–1187` | Text branch passes `exhaustive=getattr(args, "exhaustive_units", False) or getattr(args, "inspect", False)` to `adjudicate_paper` only |
| `unit_judge.py:268–277` | `run_unit_checks(..., exhaustive: bool = False)` — parameter exists on callee, not wired from PDF lane |

### (b) Default `unit_coverage` dict and overwrite conditions

| Location | Role |
|---|---|
| `pdf_judge.py:831–836` | Default before routing: `{"coverage_complete": True, "checked_unit_ids": [], "unchecked_unit_ids": [], "failed_unit_ids": []}` — no `evidence_summary` key |
| `pdf_judge.py:837` | `risk_signals = route_pdf_units(page_units, raw_tomd_md)` |
| `pdf_judge.py:839–850` | `if risk_signals:` block calls `run_unit_checks(...)` |
| `pdf_judge.py:851–860` | Overwrite ONLY when `unit_result is not None`: adds `coverage_complete`, `checked_unit_ids`, `unchecked_unit_ids`, `failed_unit_ids`, `evidence_summary` from `UnitJudgeResult` |
| `unit_judge.py:287–288` | `run_unit_checks` returns `None` when `not risk_signals` — never entered when router is empty |
| `pdf_judge.py:921` | Final `PdfJudgeResult(..., unit_coverage=unit_coverage)` — default dict survives when `risk_signals` is falsy |
| `adjudicate.py:426–440` | Text lane mirrors same pattern: `coverage_complete=True` when `state.unit_result is None` |

**Overwrite truth table (PDF lane):**

| `risk_signals` | `run_unit_checks` called? | `unit_result` | `unit_coverage` source |
|---|---|---|---|
| `[]` | No | N/A | Default `pdf_judge.py:831–836` (`coverage_complete=True`, all lists empty) |
| non-empty | Yes | always non-None inside `if risk_signals` | `pdf_judge.py:854–860` from `UnitJudgeResult` |

When non-empty, `coverage_complete` is computed at `unit_judge.py:376–380`:
`len(checked_unit_ids) == len(risky_unit_ids) and not unchecked_unit_ids and not failed_unit_ids`.

### (c) How `page_units` are built; PAGE_MIN_TOKENS scope

| Location | Role |
|---|---|
| `textlayer.py:173–278` | `extract_page_units`: one `PageUnit` per physical page (`for page_index in range(doc.page_count)`); no page omitted |
| `textlayer.py:265–277` | Each unit: `page=index+1`, `text=cleaned_pages[index]`, metadata from blocks API |
| `textlayer.py:275` | `content_tokens=len(_WORD_RE.findall(cleaned_pages[index]))` — regex word count, not `whisker.metrics.content_tokens` |
| `pdf_judge.py:654–660` | `extract_page_units(source_path)`; raises if empty list |
| `pdf_judge.py:659–660` | Empty `page_units` → `PdfLaneError` (cannot happen while `doc.page_count > 0` unless extraction bug) |
| `textlayer.py:104–157` | `extract_textlayer`: separate open/pass; also one string per physical page |
| `source_router.py:209–222` | `PAGE_MIN_TOKENS` gates **only** the `low_recall` signal branch (`if unit.content_tokens >= constants.PAGE_MIN_TOKENS`) |
| `source_router.py:224–263` | Below-threshold pages still receive `missing_captions`, `heading_drift`, `table_presence` signals (no token floor) |
| `source_router.py:184–207` | Document-wide `token_delta` signals attach to first representative page (no PAGE_MIN_TOKENS gate) |
| `pdf_judge.py:311–336` | `screen_pages`: `PAGE_MIN_TOKENS` skips recall (`skipped=True`, `flagged=False`) but **still emits** a `PageScreenEntry` for every page |
| `pdf_judge.py:629` | `page_screen = screen_pages(cleaned_pages, tomd_md)` — runs on all cleaned pages from first extraction |

**Can a physical page be absent from `page_units`?** No, when extraction succeeds: `textlayer.py:193–277` iterates every page index. A page can be effectively empty (near-zero tokens) but still present as a `PageUnit`.

**PAGE_MIN_TOKENS applies to:** (1) recall screen skip in `screen_pages` (`pdf_judge.py:325–329`); (2) `low_recall` routing only in `route_pdf_units` (`source_router.py:211`). It does **not** suppress caption, heading, table, or token-delta routing.

### (d) `page_count` — source and semantics

| Location | Role |
|---|---|
| `pdf_judge.py:598` | `pages = extract_textlayer(source_path)` |
| `pdf_judge.py:909` | `page_count=len(pages)` on `PdfJudgeResult` |
| `textlayer.py:128–141` | `extract_textlayer`: `page_count = doc.page_count`; appends one string per index `0..page_count-1` |
| `pdf_judge.py:547` | Sidecar: `textlayer_diff.page_count` from `self.page_count` |
| `pdf_judge.py:654` | `page_units` from separate `extract_page_units` call — same `doc.page_count` loop (`textlayer.py:193`) |

**Counts:** physical PDF pages (PyMuPDF `doc.page_count`), not "routed units" or "checked units". No code compares `len(checked_unit_ids)` to `page_count` anywhere in the PDF lane (rg: no matches repo-wide for `checked.*page_count`).

### (e) Full sidecar assembly (`to_sidecar_dict`)

| Key | Source line | Value / notes |
|---|---|---|
| `pid` | `pdf_judge.py:514` | `self.pid` |
| `status` | `pdf_judge.py:515` | `"ok"` (literal) |
| `source_kind` | `pdf_judge.py:516` | `"pdf"` |
| `lane` | `pdf_judge.py:517` | `"pdf_textlayer_judge"` |
| `whisker_verdict` | `pdf_judge.py:518` | `""` (empty string) |
| `suggested_verdict` | `pdf_judge.py:519` | `self.verdict` |
| `confidence` | `pdf_judge.py:520` | `round(self.confidence, 4)` |
| `escalated` | `pdf_judge.py:521` | `False` |
| `escalation_signals` | `pdf_judge.py:522` | `[]` |
| `tier1_model` | `pdf_judge.py:523` | `self.judge_model` |
| `tier2_model` | `pdf_judge.py:524` | `None` |
| `axis_findings` | `pdf_judge.py:525`, `466–471` | One structure-axis finding |
| `grounded_evidence` | `pdf_judge.py:526–534` | Subset of dispositions with `candidate_not_found` |
| `evidence_dispositions` | `pdf_judge.py:535`, `486–493` | Sorted list |
| `evidence_summary` | `pdf_judge.py:536`, `498–512` | Counts: `present_in_candidate`, `candidate_not_found`, `ambiguous`, `source_ungrounded` |
| `ungrounded_dropped` | `pdf_judge.py:537` | `self.ungrounded_dropped` |
| `primary_concern` | `pdf_judge.py:538–541` | First missing quote truncated to 160 chars, or `""` |
| `reasoning` | `pdf_judge.py:542` | `self.reasoning` |
| `advisory` | `pdf_judge.py:543` | `True` |
| `textlayer_diff` | `pdf_judge.py:544–548` | `{text_nid, content_recall, page_count}` |
| `page_screen` | `pdf_judge.py:549` | `[entry.to_dict() for entry in self.page_screen]` |
| `page_escalations` | `pdf_judge.py:550` | `self.page_escalations` |
| `risk_signals` | `pdf_judge.py:551` | `self.risk_signals` (serialized in `judge_pdf_extraction` at `913–916`) |
| `defect_groups` | `pdf_judge.py:552` | `self.defect_groups` |
| `unit_checks` | `pdf_judge.py:553` | `self.unit_checks` |
| `metadata_outline_check` | `pdf_judge.py:554` | `self.metadata_outline_check` |
| `unit_coverage` | `pdf_judge.py:555` | `self.unit_coverage` |
| `schema_version` | `pdf_judge.py:556` | **`7`** (int literal) |
| `ideal_verification` | `pdf_judge.py:558–559` | Only if `self.ideal_verification is not None` |

### (f) `run_unit_checks` call site kwargs (PDF lane)

| Location | Value |
|---|---|
| `pdf_judge.py:843–849` | `run_unit_checks(pid, raw_tomd_md, agent, risk_signals=risk_signals, unit_text_map=unit_text_map, debug_log=debug_log)` |
| `pdf_judge.py:840–842` | `unit_text_map = {f"page:{unit.page}": unit.text for unit in page_units}` |
| Not passed | `exhaustive` (defaults `False` at `unit_judge.py:276`) |

### Additional complications for all-pages wiring

| # | Location | Complication |
|---|---|---|
| 1 | `pdf_judge.py:598–603`, `654` | Two separate PyMuPDF opens: `extract_textlayer` then `extract_page_units` |
| 2 | `pdf_judge.py:311–336` vs `textlayer.py:275` | Token counting mismatch: `screen_pages` uses `content_tokens()` from `whisker.metrics`; `PageUnit.content_tokens` uses `_WORD_RE.findall` — same threshold constant, different counters |
| 3 | `source_router.py:209–263` | Trivial pages (<50 tokens) skip `low_recall` but can still route via captions/headings/tables |
| 4 | `pdf_judge.py:639–651` | Whole-document monolith LLM call always runs before any unit routing |
| 5 | `pdf_judge.py:667–679` | Mandatory `run_metadata_outline_check` LLM call always runs |
| 6 | `pdf_judge.py:724–823` | Page escalation LLM calls only for `page_screen` flagged pages, capped at `MAX_PAGE_ESCALATIONS` — independent of unit checks |
| 7 | `unit_judge.py:304` | Non-exhaustive cap: `max_checks = MAX_UNIT_CHECKS` (5) unless `exhaustive=True` — PDF never passes `exhaustive` |
| 8 | `pdf_judge.py:831–836` vs `854–860` | Default `unit_coverage` lacks `evidence_summary`; post-check form includes it — schema shape differs by path |
| 9 | `fusion.py:191–195` | Fusion fail-closed on `coverage_complete is not True` or non-empty unchecked/failed lists; empty-router default passes all three checks |
| 10 | `cli.py:1121–1126` | No `trace` parameter on PDF path (text lane has `trace=args.trace` at `1185`) |
| 11 | N/A | No `all_pages_requested`, no `unit_selection`, no `checked == page_count` invariant anywhere in PDF lane today |

## Verdict on the claim(s)

**C3b (PDF side): CONFIRMED.**

When `route_pdf_units` returns an empty list (`pdf_judge.py:837`), the `if risk_signals:` block (`839`) is skipped, `run_unit_checks` is never called (`unit_judge.py:287–288` would return `None` anyway), and the default `unit_coverage` at `pdf_judge.py:831–836` persists with `coverage_complete=True`, `checked_unit_ids=[]`, `unchecked_unit_ids=[]`, `failed_unit_ids=[]`.

That sidecar is written at `pdf_judge.py:555` and fusion treats it as complete coverage: `fusion.py:191–195` requires `coverage.get("coverage_complete") is not True` or non-empty unchecked/failed lists to force review — all three pass on the empty-router default.

Related C3a (PDF branch never receives `exhaustive`): **CONFIRMED** via `cli.py:1121–1126` vs `1186–1187` and absent parameter on `judge_pdf_extraction` (`pdf_judge.py:567–573`). `run_unit_checks` supports `exhaustive` (`unit_judge.py:276`) but PDF call site omits it (`pdf_judge.py:843–849`).

## Coverage gaps

- `unit_judge.py`, `source_router.py`, `fusion.py`, `cli.py`: read only at cited line ranges, not in full.
- `_compute_fingerprint` (C3c): not in this agent's scope; not read.

## What could still hide a counterexample

- A second PDF entry path bypassing `judge_pdf_extraction` that sets `unit_coverage` differently (would require full `cli.py` / `adjudicate.py` inventory; out of scope here).
- Runtime mutation of sidecar after `to_sidecar_dict()` in persistence layer (not inspected).
- HTML lane empty-router behavior differs only in assembly site (`adjudicate.py:426–440`) but same semantic defect; not a PDF counterexample to C3b.
