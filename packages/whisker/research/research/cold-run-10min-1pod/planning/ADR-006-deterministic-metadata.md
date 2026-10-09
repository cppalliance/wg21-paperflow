# ADR-006: Deterministic metadata / outline diff

## Title

Replace the metadata/outline LLM call with a deterministic `compare_metadata_outline()`, staged HTML-first behind A/B gates.

## Status

**Proposed** — A/B gated. Not shippable today (0/1 at HEAD; AGGRESSIVE tier). HTML-first staging allowed once HTML shadow gates pass; fleet-wide flip only after PDF parity.

## Context

Single `alliance-pod`, `S_eff = 16`. Dual-pod is out of scope.

Today each cold-fleet paper that reaches unit checks pays one `run_metadata_outline_check` LLM call (`MetadataOutlineCheck`: title/document/date booleans, `heading_drift[]`, `missing_sections[]`, `verdict`). That is **377** calls at ~20 s mean → **~471 s** wall at S=16 (`377 × 20 / 16`).

The call is structurally redundant with assets already in tree:

- HTML: `extract_heading_outline_normalized` / `route_html_units` already do occurrence-aware level+title diff (`html_outline.py`, `source_router.py`).
- Candidate side: `_candidate_structure_packet` already parses YAML + ATX headings.
- Front-matter keys: `gates.py` patterns extend cleanly for `document` / `date`.

What the LLM uniquely adds is **prompt-encoded lenience** (TOC chrome ignore, cosmetic formatting, fuzzy PDF page-1 mapping, date format softness), not detection power. On HTML heading-level defects (PR #282), the LLM has false-cleared while the deterministic router would catch. PDF remains noisier: font-size `heading_candidates` and page-1 prose can false-fire `missing_sections` if rules are too strict.

Fleet mix: **201 HTML / 180 PDF**. HTML-first deterministic metadata reclaims ~**251 s** (201 calls) as a first tranche; fleet-wide is ~**471 s**. Metadata-fail short-circuit (v11) is orthogonal and already landed; this lever removes the metadata LLM itself.

Package boundary: `packages/whisker/` only.

## Decision

1. Implement pure `compare_metadata_outline(pid, source_metadata, source_outline, candidate_md, *, source_kind, html_outline=None) -> MetadataOutlineCheck` with no `run_judge_task`.
2. **Verdict policy (conservative):**
   - Document PID mismatch → `fail`.
   - Title / date / heading drift / missing sections → `review` (date: exact ISO if both ISO; else mismatch → `review`; absent candidate date → `pass`).
   - PDF unmatched font lines / outline noise → cap at `review`, never `fail` unless PID wrong.
3. **Staging (HTML-first):**
   - Phase 0: shadow both paths (`TAPETUM_METADATA_SHADOW=1`); persist `metadata_outline_check_det`; no fleet behavior change.
   - Phase 1a: after HTML gates pass, default deterministic on **HTML** only; keep LLM on PDF.
   - Phase 1b: extend PDF branch; flip fleet-wide only after PDF holdout.
   - Phase 2: remove metadata LLM from hot path; bump `_LANE_VERSION`; drop `metadata` from prompt fingerprint class list; optional `--llm-metadata-audit` for inspect.
4. Rollback: `--llm-metadata` restores `run_metadata_outline_check`.
5. Wire-in behind `--deterministic-metadata` / env flags initially (`pdf_judge.py`, `adjudicate.py`).

## Consequences

**Positive**

- Eliminates ~377 LLM calls (~471 s @ S=16); HTML tranche ~251 s earlier.
- Improves HTML heading-level recall vs LLM false-clear (PR #282 / #295 with secno strip).
- Stacks with v11 short-circuit toward ~1191 s on a 3003 s baseline (still above 600 s; necessary, not sufficient).

**Negative / risks**

- PDF page-1 noise can increase advisory `review` vs LLM pass (fusion cap).
- HTML-only ship creates lane-asymmetric advisory posture until PDF flips.
- Wrong date-normalization policy could pass wrong revision year if too loose (mitigate: date mismatch always `review` unless byte-equal after ISO parse).
- False-fail if PID only appears past first N lines of page-1 text (mitigate: scan first N chars/lines before PID fail).

**Neutral**

- `MetadataOutlineCheck` schema and fusion fold semantics stay; only the producer changes.
- Table compare remains orthogonal (`table_compare.py`).

## Evidence

| Claim | Source |
|-------|--------|
| 377 metadata calls, ~20 s, S=16 → ~471 s | `13-deterministic-metadata.md`, `00-baseline.md` |
| Schema mechanically checkable | `models.py` MetadataOutlineCheck; `13` §What the LLM call does |
| HTML router already diffs levels | `source_router.py:286-312`; `13` §Deterministic assets |
| LLM false-cleared PR #282 level drift | `golden-qa-gap/00-baseline.md`; `131-surya-model-sizing.md` |
| HTML 201 / PDF 180; HTML-first ~251 s | `22-html-vs-pdf-mix.md` |
| Status AGGRESSIVE, not started | `10-impl-status-1pod.md` Tier 1 |
| Short-circuit orthogonal | `13` stacking note; v11 in `pdf_judge.py` / `adjudicate.py` |

## Quality gate

Ship blockers (all required):

1. **Shadow (381):** metadata verdict agreement ≥ **95%** det vs LLM; if **>5%** disagree **or any** fused `combined_verdict` change vs LLM → do not ship deterministic-only.
2. **Holdout:** 48-paper active holdout + 9 dev-replay golden PRs (#282–#286, #290, #293–#295).
3. **Zero** fused advisory verdict changes vs LLM control on holdout + replay.
4. Deterministic **≥ LLM** recall on HTML heading-level defects (PR #282 / #295).
5. PDF false-fail rate ≤ **2%** on clean papers (`fail` not; `review` demotion acceptable).

**HTML-first ship** may proceed if HTML shadow alone reaches ≥**98%** verdict agreement and **zero** holdout fused drift on HTML papers, without waiting on PDF parity — PDF stays on LLM until its gate passes.

**Mind-changers:** ≥98% agreement + PR #282 catch without new false-fails → upgrade to shippable; >5% drift or any holdout fused change → reject replacement (keep LLM or train small classifier on sidecar labels).
