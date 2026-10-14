# 43 - C3 readers (fusion, models, inspect_report, adjudicate full read)
**Claims tested:** C3 (readers side: fusion consumption of `unit_coverage`; sidecar field inventory; inspect_report omissions; text-lane exhaustive reference vs PDF gap)
**Exhaustive:** no (Coverage gaps: `cli.py`, `fusion_report.py`, `pdf_judge.py`, `unit_judge.py` read only at grep targets and call-site excerpts; tests read only where they assert sidecar keys)

## Method
Files read in full (line counts per assignment):
- `packages/whisker/src/whisker/tapetum_llm/models.py` (412 lines)
- `packages/whisker/src/whisker/tapetum_llm/fusion.py` (538 lines)
- `packages/whisker/src/whisker/tapetum_llm/inspect_report.py` (376 lines)
- `packages/whisker/src/whisker/tapetum_llm/adjudicate.py` (816 lines)

Supplemental targeted search (not full-file reads):
- `rg 'unit_coverage|unit_selection|all_pages_requested|page_screen|page_count|page_escalations|exhaustive|fuse_verdicts|to_sidecar_dict|TapetumResult' packages/whisker/src/whisker/tapetum_llm/`
- `rg 'unit_selection|all_pages_requested' packages/whisker/tests/`
- Excerpt reads: `cli.py:515-655`, `cli.py:1118-1192`, `pdf_judge.py:421-560`, `pdf_judge.py:825-922`, `unit_judge.py:231-427`, `fusion_report.py:1-303`, `constants.py:158` (`FUSION_SCHEMA_VERSION`)

## Inventory

### A. `unit_coverage` producers (feeds readers)

| Location | Role |
|---|---|
| `adjudicate.py:426-441` | Builds `unit_coverage` from `state.unit_result` when set; else stub `{coverage_complete: True, checked/unchecked/failed: []}` |
| `adjudicate.py:516-517` | HTML: `if not risk_signals: return` before `run_unit_checks` → `unit_result` stays `None` → stub at 435-440 |
| `adjudicate.py:601-602` | PDF (text cascade): same early return when `not risk_signals` |
| `adjudicate.py:523-531` | HTML: `run_unit_checks(..., exhaustive=state.exhaustive)` |
| `adjudicate.py:608-616` | PDF (text cascade): `run_unit_checks(..., exhaustive=state.exhaustive)` |
| `unit_judge.py:376-380` | `coverage_complete = len(checked)==len(risky) and not unchecked and not failed` |
| `unit_judge.py:398-414` | Builds `unit_selection` with per-unit `status` and `reason` (`exhaustive`/`quota`/`priority`) |

(`pdf_judge.py` also produces `unit_coverage`; not in mandated full read; see Coverage gaps.)

### B. Fusion reads of `unit_coverage` (every call site in `fusion.py`)

| Line | Code path | Fields read |
|---|---|---|
| `fusion.py:177` | `_has_source_aware_data` | `"unit_coverage" in tapetum` (key presence only) |
| `fusion.py:191-195` | `_source_aware_requires_review` | `coverage.get("coverage_complete") is not True` → review cap; `coverage.get("unchecked_unit_ids")` truthy → review cap; `coverage.get("failed_unit_ids")` truthy → review cap |
| `fusion.py:398-400` | `fuse_verdicts` | Invokes `_source_aware_requires_review(tapetum)` on det pass/review |

Fields **not** read by fusion: `checked_unit_ids`, `evidence_summary` inside `unit_coverage`, `unit_selection`, `all_pages_requested` (does not exist in codebase).

**Ambiguity verdict (a):** Fusion **cannot** distinguish “complete because nothing was flagged/checked” from “complete because every routed unit was checked.” Both shapes pass when `coverage_complete is True` and `unchecked_unit_ids`/`failed_unit_ids` are empty (`fusion.py:192-195`). A zero-check stub from `adjudicate.py:435-440` (`coverage_complete: True`, all ID lists empty) is treated as fully complete. Fusion never inspects `len(checked_unit_ids)` or `risk_signals`. Inspect report shows `checked=N` (`inspect_report.py:192-195`) but the fusion gate does not.

### C. `TapetumResult` — every field and serialization

Dataclass fields (`models.py:334-361`):

| Field | Type / default | In `to_dict()` |
|---|---|---|
| `pid` | `str` | always (`models.py:366`) |
| `whisker_verdict` | `str` | always (`368`) |
| `suggested_verdict` | `str` | always (`369`) |
| `confidence` | `float` | always, rounded (`370`) |
| `escalated` | `bool` | always (`371`) |
| `tier1_model` | `str` | always (`373`) |
| `tier2_model` | `str \| None` | always (`374`) |
| `axis_findings` | `list[dict]` | always, sorted (`375-377`) |
| `grounded_evidence` | `list[dict]` | always, sorted (`378-381`) |
| `evidence_dispositions` | `list[dict]` | always, sorted (`382-389`) |
| `evidence_summary` | `dict` | always (`390`) |
| `ungrounded_dropped` | `int` | always (`391`) |
| `escalation_signals` | `list[str]` | always, sorted (`372`) |
| `primary_concern` | `str` | always (`392`) |
| `reasoning` | `str` | always (`393`) |
| `status` | `str`, default `"ok"` | always (`367`) |
| `risk_signals` | `list[dict]` | if non-empty (`399-400`) |
| `defect_groups` | `list[dict]` | if non-empty (`401-402`) |
| `unit_checks` | `list[dict]` | if non-empty (`403-404`) |
| `metadata_outline_check` | `dict` | always (`394`) |
| `unit_coverage` | `dict` | always (`395`) |
| `unit_selection` | `list[dict]` | if non-empty (`405-406`) |
| `table_compare` | `dict` | if non-empty (`407-408`) |
| `ideal_verification` | `IdealVerification \| None` | if not None (`409-410`) |
| — | — | `"advisory": True` (`396`), `"schema_version": 8` (`397`) |

`all_pages_requested`: **NOT VERIFIED** in any production file (grep over `packages/whisker/src`).

### D. `PdfJudgeResult` — every field and serialization

(`pdf_judge.py:422-455`, `457-560`; excerpt read, not in mandated four-file full read.)

| Field | In `to_sidecar_dict()` |
|---|---|
| `pid` | yes (`514`) |
| `verdict` → `suggested_verdict` | yes (`519`) |
| `confidence` | yes (`520`) |
| `reasoning` | yes (`542`) |
| `missing_content` | via `primary_concern`, `grounded_evidence`, dispositions (`538-541`, `472-485`) |
| `evidence_verification` | as `evidence_dispositions` (`535`) |
| `ungrounded_dropped` | yes (`537`) |
| `text_nid`, `content_recall`, `page_count` | nested under `textlayer_diff` (`544-548`) |
| `judge_model` | as `tier1_model` (`523`) |
| `page_screen` | yes (`549`) |
| `page_escalations` | yes (`550`) |
| `risk_signals` | yes (`551`) |
| `defect_groups` | yes (`552`) |
| `unit_checks` | yes (`553`) |
| `metadata_outline_check` | yes (`554`) |
| `unit_coverage` | yes (`555`) |
| `ideal_verification` | if not None (`558-559`) |
| — | `"schema_version": 7` (`556`); also `source_kind`, `lane`, `status`, `escalated`, `axis_findings`, `evidence_summary`, `advisory` |

No `unit_selection` or `all_pages_requested` on `PdfJudgeResult` or its sidecar.

### E. Schema version values (both layers)

| Artifact | Constant / value | Citation |
|---|---|---|
| Text-lane tapetum sidecar | `schema_version: 8` | `models.py:397` |
| PDF-judge sidecar | `schema_version: 7` | `pdf_judge.py:556` |
| Fusion block embedded in sidecar | `fusion_schema_version: FUSION_SCHEMA_VERSION` (= 4) | `fusion.py:78`, `93`; `constants.py:158` |
| Fusion source-aware gate | `tapetum.get("schema_version", 0) >= 6` **or** shape keys | `fusion.py:169-178` |

### F. Sidecar dict readers (every production consumer)

#### `fusion.py`
| Lines | Reads |
|---|---|
| `128-151` | `_validate_tapetum_sidecar`: `pid`, optional `fingerprint`, `status`, `suggested_verdict`, `confidence` |
| `154-164` | `_tapetum_is_usable`: `status`, `confidence`, `axis_findings`, `_has_source_aware_data` |
| `167-179` | `_has_source_aware_data`: `schema_version`, `metadata_outline_check`, `unit_coverage`, `defect_groups` |
| `182-215` | `_source_aware_requires_review`: metadata, unit_coverage, defect_groups, unit_checks, evidence_dispositions |
| `226-244` | `_accepted_unit_defects`, `_accepted_flat_dispositions` |
| `283-296` | `_has_major_axis_fail`, `_has_any_axis_fail`: `axis_findings` |
| `326-333` | `_ideal_summary`: `ideal_verification` |
| `336-537` | `fuse_verdicts`: whisker dict + all above |

#### `inspect_report.py`
| Lines | Reads |
|---|---|
| `85-96` | `pid`, `suggested_verdict`, `confidence`, `escalated`, `tier1_model`, `tier2_model` |
| `102-110` | whisker signal keys + flags |
| `114-144` | `ideal_verification` |
| `146-159` | `axis_findings` |
| `161-163` | `primary_concern` |
| `165-178` | `metadata_outline_check` |
| `180-209` | `unit_coverage` (complete flag + three ID lists + counts) |
| `211-222` | embedded `fusion` (`combined_rule`, `combined_verdict`) |
| `224-249` | `defect_groups` |
| `251-265` | `risk_signals` |
| `267-298` | `evidence_dispositions`, `evidence_summary` |
| `300-314` | `grounded_evidence`, `ungrounded_dropped` |
| `316-318` | `reasoning` |
| `323-375` | `format_report` header: `suggested_verdict`, `fusion` rollup |

**Absent from inspect_report (CONFIRMED):** `page_screen`, `page_count`, `page_escalations`, `textlayer_diff`, `unit_selection`, `all_pages_requested` — zero matches in file (grep).

#### `fusion_report.py` (excerpt read)
| Lines | Reads |
|---|---|
| `84-86` | `ideal_verification` |
| `87-96` | `confidence`, `suggested_verdict`, `fusion.combined_verdict`, `fusion.combined_rule` |
| `143-162` | `_classify_cosmetic`: `suggested_verdict`, `axis_findings` |

#### `cli.py` (excerpt read)
| Lines | Reads |
|---|---|
| `338-371` | whisker sidecars via `_validate_whisker_sidecar` |
| `571-588` | existing sidecar `fingerprint` |
| `619-647` | `to_sidecar_dict()` / `to_dict()` → `fuse_verdicts` → embed `fusion` |
| `669-671` | `_read_tapetum_sidecar` → `_validate_tapetum_sidecar` |
| `707-711` | `format_report` |
| `728-752` | `build_merged_json` over sidecar pairs |
| `776-786` | `--fuse-only` recomputes fusion |

### G. Readers vs new fields `all_pages_requested`, `unit_selection`

| Reader | Break if fields added? | Notes |
|---|---|---|
| `_validate_tapetum_sidecar` | **No** | Extra keys ignored (`fusion.py:128-151`) |
| `fuse_verdicts` / `_source_aware_requires_review` | **No** | Does not enumerate sidecar keys |
| `inspect_report.format_paper_section` | **No** | Would silently omit until code added |
| `fusion_report.build_merged_json` | **No** | Ignores unknown keys |
| `cli` persist / fuse-only | **No** | JSON round-trip preserves extra keys |
| `TapetumResult` dataclass | **Producer change** | New dataclass field needs constructor sites; not a reader break |
| `TapetumResult.to_dict` | **No reader break** | New always-on key changes bytes; optional keys match existing `unit_selection` pattern (`405-406`) |
| Tests (`test_pdf_judge.py:396-400`) | **No** | Asserts required fields present, not closed key set |

**Existing `unit_selection` gap:** `UnitJudgeResult` builds `unit_selection` (`unit_judge.py:398-414`), but `adjudicate.py:468` assigns `unit_selection=state.unit_selection` while `state.unit_selection` is never populated from `unit_result` (`adjudicate.py:198` default `[]` only). Sidecar `unit_selection` is therefore always omitted (empty → not serialized at `models.py:405-406`).

### H. Text-lane exhaustive flow (`state.exhaustive`) — reference for PDF gap

| Step | Lines | Behavior |
|---|---|---|
| CLI → text lane | `cli.py:1186-1187` | `exhaustive=getattr(args, "exhaustive_units", False) or getattr(args, "inspect", False)` passed to `adjudicate_paper` |
| CLI → PDF-judge lane | `cli.py:1121-1125` | `judge_pdf_extraction(...)` — **no `exhaustive` argument** |
| State init | `adjudicate.py:774` | `state.exhaustive = exhaustive` |
| HTML unit checks | `adjudicate.py:523-531` | `run_unit_checks(..., exhaustive=state.exhaustive)` |
| PDF unit checks (inside text cascade) | `adjudicate.py:608-616` | same |
| Unit cap | `unit_judge.py:304-307` | `max_checks = len(risky_unit_ids) if exhaustive else MAX_UNIT_CHECKS` |
| Selection audit | `unit_judge.py:398-414` | `reason: "exhaustive"` when flag set |

PDF-judge lane (`pdf_judge.py:843-850`, excerpt): `run_unit_checks` called **without** `exhaustive` → defaults `False` (`unit_judge.py:276`).

## Verdict on the claim(s)

**C3 readers side — PARTIALLY confirmed:**

1. **Fusion trusts empty-complete `unit_coverage`:** CONFIRMED. `_source_aware_requires_review` passes when `coverage_complete is True` and unchecked/failed lists are empty (`fusion.py:192-195`), with no check on `checked_unit_ids`. Stubs at `adjudicate.py:435-440` supply exactly that shape when `unit_result is None` (no risk signals / early return).

2. **Ambiguity not distinguishable at fusion:** CONFIRMED (same citations). Inspect report shows counts but fusion gate does not use them.

3. **`page_screen` / `page_count` / `page_escalations` absent from operator inspect report:** CONFIRMED. Fields exist on PDF sidecar (`pdf_judge.py:544-550`) but `inspect_report.py` has no references.

4. **Text exhaustive reference vs PDF:** CONFIRMED at CLI boundary (`cli.py:1186-1187` vs `1121-1125`). Text cascade’s internal PDF unit path would honor `state.exhaustive` (`adjudicate.py:615`) but PDF-judge lane bypasses it.

5. **New fields reader breakage:** REFUTED for “break” — all dict readers are tolerant. **Gap:** no reader surfaces `unit_selection` today; `all_pages_requested` does not exist.

## Coverage gaps
- `pdf_judge.py` (~923 lines): only `PdfJudgeResult`, `to_sidecar_dict`, and unit-check call site read via excerpt; not full file.
- `cli.py` (~1331 lines): fingerprint, persist, and `_adjudicate_one` read via excerpt; not full file.
- `fusion_report.py` (303 lines): read in full via single Read call.
- `unit_judge.py` (~699 lines): exhaustive/`coverage_complete` logic read via excerpt; not full file.
- Tests: not exhaustively enumerated; spot-checked `test_pdf_judge.py`, `test_tapetum_llm.py`.

## What could still hide a counterexample
- A reader outside `tapetum_llm/` (scripts, external tooling) parsing sidecars with closed key schemas — not searched.
- `vlm_diff.py` / `VlmDiffResult.to_sidecar_dict` (`schema_version: 2`) as a third sidecar shape; fusion reads same core fields but not verified line-by-line here.
- Incremental skip (`cli.py:515-565`) ignores exhaustive mode in fingerprint; stale sidecars could mask behavior changes (producer defect, affects what readers see).
- Menu or other entry points calling `adjudicate_paper` / `judge_pdf_extraction` without going through `cli.py:1186-1187` — not enumerated.

## Plan complications (beyond charter C3 bullets)
1. **`unit_selection` already modeled but never populated** on text lane (`adjudicate.py:468` vs `unit_judge.py:398-414`).
2. **Dual PDF paths:** text cascade PDF unit checks vs PDF-judge lane; exhaustive only wired on the former internally, never on the lane CLI selects for PDF papers.
3. **Schema split:** text sidecar v8 vs PDF sidecar v7; fusion treats both as source-aware when `schema_version >= 6` or shape keys present (`fusion.py:169-178`).
4. **Inspect report already shows `unit_coverage` but not PDF page recall artifacts** (`page_screen`, `page_escalations`, `textlayer_diff.page_count`) even though PDF sidecar carries them.
5. **`metadata_outline_check` always serialized** on text sidecar (`models.py:394`) even when `{}`; PDF-judge may omit when empty — asymmetric operator visibility.
6. **Embedded `fusion` block** written at persist time (`cli.py:621-622`, `646-647`); `inspect_report` reads it from tapetum dict (`inspect_report.py:211-222`) — report content depends on persist path, not live re-fusion.
7. **`all_pages_requested` is greenfield** — no field, no reader, no test references in repo (grep).
