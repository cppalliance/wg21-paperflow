# ADR-021: HTML-first deterministic metadata staging

## Status

Proposed

## Date

2026-07-24

## Context

ADR-006 decides to replace the metadata/outline LLM with `compare_metadata_outline()`. This card fixes **deployment order**: HTML before PDF.

Fleet mix is **201 HTML / 180 PDF** (`22`). HTML already has occurrence-aware level+title diff in `route_html_units` / `html_outline.py`; the metadata LLM re-asks that work (~198 HTML metadata calls). PDF page-1 font-size outline noise can false-fire `missing_sections` if rules are too strict (`13`).

HTML-first tranche: **~251 s** @ S=16 (201 calls). Fleet-wide: **~471 s** (377 calls). v11 metadata-fail short-circuit is orthogonal and already landed.

## Decision

1. **Stage HTML-first.** Ship deterministic metadata on HTML papers only after HTML shadow gates pass; keep the metadata LLM on PDF until PDF holdout passes.
2. **Shadow before flip.** Phase 0: both paths under `TAPETUM_METADATA_SHADOW=1`; persist `metadata_outline_check_det`; no fleet behavior change.
3. **HTML ship gate (ADR-006):** HTML shadow ≥**98%** metadata verdict agreement and **zero** holdout fused-verdict drift on HTML papers → enable det on HTML.
4. **PDF later.** Fleet-wide flip only after PDF holdout (≤2% false-fail on clean papers; `review` demotion acceptable). Do not block HTML ship on PDF parity.
5. Rollback: `--llm-metadata` restores `run_metadata_outline_check` for the flipped lane(s).

## Consequences

**Positive**

- Lands ~251 s earlier without waiting on PDF outline hardening.
- HTML heading-level recall can beat LLM false-clear (PR #282 / #295 class) while PDF stays on the lenient LLM.
- Matches Option A execution order in `PLANNING-HANDOFF.md` / `SYNTHESIS.md`.

**Negative / cost**

- Temporary lane-asymmetric advisory posture (HTML det vs PDF LLM) until PDF flips.
- Two quality gates instead of one fleet flip.

**Invariants**

- Does not change `MetadataOutlineCheck` schema or fusion fold semantics.
- Does not claim ≤600 s; stacks toward ~1191 s on a 3003 s baseline with short-circuit (`13`).

## Evidence

| Claim | Source |
|-------|--------|
| HTML 201 / PDF 180; HTML-first ~251 s; fleet ~471 s | `22-html-vs-pdf-mix.md` |
| Det-metadata A/B only; HTML router already diffs; PDF noisier | `13-deterministic-metadata.md` |
| Staging HTML-first → fleet in MoE package | `SYNTHESIS.md`, `PLANNING-HANDOFF.md` §6 |
| Full producer/policy design | ADR-006 |
| Status AGGRESSIVE / not started | `10-impl-status-1pod.md` |
