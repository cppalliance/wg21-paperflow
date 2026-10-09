# 14 - Maintainability-Complexity

**Verdict:** usable-with-conditions — the deterministic-gate / advisory-LLM split matches ecosystem practice (`05-web.md / Q4 / Deterministic Guardrails`), but the advisory lane carries ~22× the gate's LOC with duplicated rules, dormant subsystems, and doc/code drift that will mislead the next maintainer about what actually runs.
**Confidence:** high

## Findings

- [CRITICAL] Advisory surface dwarfs the gate core: `tapetum_llm/` is **4751** Python LOC vs `gates.py` **219** LOC (`00-baseline.md:60-61`; reproduced 2026-07-16). Impact: every prompt tweak, schema change, or fusion rule edit is a high-touch change across a 22-module package while the authoritative verdict stays in six gates (`gates.py:209-218`). Rot concentrates in the lane that never gates CI.

- [HIGH] The 2026-07-16 TOC rule is a coupling smell, not an accident: one semantic rule now lives in **five** places — deterministic gate `gates.py:143-218` (`no_toc_leak`), text-lane prompt `tapetum_llm.md:62`, PDF-lane prompt block `pdf_judge.py:137-144` (`_CONVERSION_CONTRACT`, also inherited by page escalations at `:218`), fusion rescue guard `fusion.py:105-116` (prefix match so TOC-leak details do not substring-match "heading"), and duplicate selector `adjudicate.py:140-151`. Impact: a future TOC signature (e.g. roman-numeral page suffix) must be updated in gate + two prompt authorities + two Python prefix guards; missing one site reopens the MC2 false-pass the baseline closed (`00-baseline.md:94-95`).

- [HIGH] Two-tier cascade is still effectively dead in production despite a July refactor to derived signals. Runtime: `escalated=true` in **0/198** sidecars; confidence never entered `[0.35, 0.65]` (`00-baseline.md:85`; `research/tapetum-golden-review-findings-2026-07-14.md:86-89`). Code keeps Step 2 hooks (`adjudicate.py:256-274`), ambiguous-band constants (`constants.py:27-28`), and same-service slots (`tapetum_llm.md:19-20`: fast and deep both `alliance-pod`). Impact: maintainers will tune tier-2 prompts/thresholds for a path that has not fired across two corpus runs; tests prove wiring (`test_tapetum_llm.py:1295+`) but not production calibration (`constants.py:23-26` documents the dead band explicitly).

- [HIGH] Dormant VLM sub-lane is ~637 LOC with zero CLI entry: `vlm_pipeline.py`, `vision_task.py`, `transcribe.py`, `vlm_diff.py`, `vision.py` are exercised only by `tests/test_vlm_lane.py`; `cli.py:747-832` routes PDF→`judge_pdf_extraction`, HTML→`adjudicate_paper`, never `vlm_adjudicate_paper`. Impact: a third parallel judge architecture (pixels→transcribe→diff) sits beside the live PDF-text and markdown cascades, increasing search cost and tempting mistaken "wire it back" work without deleting the superseding `pdf_judge.py` path (`pdf_judge.py:8-19` documents the deliberate replacement).

- [MED] Dual prompt authorities split the text and PDF lanes. Text lane loads one system prompt from `tapetum_llm.md` via `PipelinePrompt.load` (`adjudicate.py:482`, `cli.py:637`). PDF lane embeds a separate ~40-line `_CONVERSION_CONTRACT` plus monolith/page prompts in `pdf_judge.py:129-228`, fingerprinted independently (`cli.py:670-680`). Impact: model-churn edits (sanctioned markers, TOC rule, output discipline) must be mirrored manually; drift already visible — sanctioned-marker prose appears in both `tapetum_llm.md:91-98` and `pdf_judge.py:150-161` with different wording.

- [MED] `_is_heading_only_fail` is copy-pasted between fusion and candidate selection with identical TOC-leak commentary (`fusion.py:105-116`, `adjudicate.py:140-151`). Impact: a rescue-path bug fix must land twice; the prefix-match invariant exists because substring "heading" in `no_toc_leak` details would false-route (`test_fusion.py:131-140`, `adjudicate.py:143-145`).

- [MED] Authority doc drift on lane independence. `tapetum_llm.md:125-127` says Step 0 attaches whisker verdict/signals to state for triage; code loads `whisker_signals` (`adjudicate.py:197-203`) but injects **none** into triage prompts (`adjudicate.py:383-385`: "no deterministic-lane signals"), using the dict only for sidecar metadata (`adjudicate.py:336`). Impact: readers of `tapetum_llm.md` believe confirmation-bias defenses were removed when they were never wired; debugging "why didn't the LLM see lossy_table_count?" wastes time.

- [LOW] vs marker's LLM-processor layout, whisker's advisory stack is monolithic and harder to swap under model churn. Marker: optional block plugins under `processors/llm/__init__.py` with per-processor prompts and a **deterministic** CI gate (`00-baseline.md:26`: heuristic/TEDS floors; `05-web.md / Q5 / Marker CI gates heuristic only`). Whisker: one 825-LOC `cli.py` orchestrates fingerprinting, dual lanes, fusion, and inspect (`cli.py:322-351`, `747-832`); changing one axis rule touches gate + prompt(s) + fusion matrix (`fusion.py:124-252`, `00-baseline.md:70-72`). Impact: marker survives model churn by swapping a processor plugin; whisker survives by invalidating fingerprints and re-running the full advisory corpus — workable, but higher maintenance tax for the non-gating lane.

## False-pass hypothesis

A maintainer updates the TOC rule in `gates.py` and `tapetum_llm.md` but omits `pdf_judge.py:_CONVERSION_CONTRACT` (the dominant production path for PDF papers per `cli.py:747-790`). PDF-lane sidecars continue to false-clear leaked TOC at high confidence, exactly as `00-baseline.md:87` documents for p1122r3, while deterministic+text-lane catches look green — dual-authority drift manufactures a silent regression in the lane meant to localize defects.

## False-fail hypothesis

A maintainer, believing the two-tier cascade is load-bearing from `tapetum_llm.md:3-14`, spends a sprint splitting `fast`/`deep` onto distinct pods and tuning `CONFIDENCE_AMBIGUOUS_LO/HI` (`constants.py:27-28`) — but production escalation remains at 0/N because axis-conflict/ungrounded triggers also never fire at scale (`adjudicate.py:230-253`, baseline `0/198`). The effort adds operational complexity without changing advisory output, while the real false-fail rescue path remains the deterministic `heading_monotone` gate plus fusion rescue (`fusion.py:149-160`, `00-baseline.md:62-63`).

## What would change my mind

A measured refactor that (a) deletes or quarantines the dormant VLM lane, (b) collapses PDF+text prompts to a single loaded authority (or generates `pdf_judge` strings from `tapetum_llm.md`), and (c) extracts shared selectors (`_is_heading_only_fail`) to one module — bringing advisory LOC under ~3000 and rule touch-count to ≤2 files per defect class — would flip this to **usable** without questioning the architecture choice.
