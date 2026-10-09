# CODE-ANCHORS — tapetum_llm change map

**Date:** 2026-07-24  
**Scope:** `packages/whisker/src/whisker/tapetum_llm/` only. Planning artifact; no production edits from this file.  
**Sources:** `10-impl-status-1pod.md`, `13-deterministic-metadata.md`, `15-verdict-first-design.md`, `12-dense-offload-architecture.md`, `23-payload-scope-dense.md`, plus HEAD grep.

Paths below are relative to `packages/whisker/src/whisker/tapetum_llm/` unless noted.

---

## Legend

| Column | Meaning |
|--------|---------|
| **Symbol / file:line** | Grep-verified at HEAD where possible; report ranges noted if they differ slightly |
| **Lever** | Which cold-run lever owns the change |
| **What to change** | Intended edit (not yet shipped unless Status = Done) |
| **Notes** | Status, gates, stacking |

---

## Anchors

| Symbol / file:line | Lever | What to change | Notes |
|--------------------|-------|----------------|-------|
| `_LANE_VERSION = 11` — `cli.py:123` (log comments `:110-122`) | Fingerprint / all Tier-1 ships | Bump on any lane-semantics change (short-circuit already at 11; bump again for dense routing, det-metadata default, verdict-first schema, payload scope) | Fingerprint field `lane_version` at `cli.py:630`. Bundle dense with short-circuit/HMAC only if quality protocol §4.1 allows; prefer isolated B. |
| Short-circuit PDF — `pdf_judge.py:742-759` (`metadata_short_circuited`) | Metadata-fail short-circuit (v11, **Done**) | Keep; exempt `--all-pages` / `--exhaustive-units` / `--inspect` | Largest landed N cut: −847 unit calls, **−1059 to −1341 s** @ S=16. Coverage mode `metadata_short_circuit` ~`pdf_judge.py:1057-1064`. |
| Short-circuit HTML — `adjudicate.py:521-531` | Metadata-fail short-circuit (v11, **Done**) | Keep mirror of PDF path | Same fold semantics as PDF. |
| `run_metadata_outline_check` — `unit_judge.py:231-273` | Deterministic metadata | Replace hot path with `compare_metadata_outline()`; keep LLM behind `--llm-metadata` / shadow | Today: one `run_judge_task` → `MetadataOutlineCheck`. Wire-in: `pdf_judge.py:702`, `adjudicate.py:512`. Est. **−~471 s** (377×20/16). A/B only until ≥95% verdict agreement + zero fused flips. |
| `_candidate_structure_packet` — `unit_judge.py:220-228` | Deterministic metadata | Reuse for candidate YAML + ATX list in det compare | No LLM. |
| `MetadataOutlineCheck` — `models.py:262-295` | Deterministic metadata; verdict-first (decode shrink) | Det path returns same model; optional shorten `reasoning` 40→15 words on LLM path | Fold: `pdf_judge.py:737-740`, `adjudicate.py:382-389`; fusion cap `fusion.py:187-189`. |
| HTML outline assets — `html_outline.py:128-147` (`extract_heading_outline*`), `:44-50` / `:119-125` (`normalize_heading_text`) | Deterministic metadata | Feed HTML branch of `compare_metadata_outline` | Secno strip fixes PR #295 class when both sides normalized. |
| Outline level diff — `source_router.py:286-312` (`route_html_units`); TOC filter `:163-164` | Deterministic metadata | Port occurrence-aware title+level compare into metadata verdict | HTML LLM largely re-asks this. PDF title-presence only `:236-255` (signal, not level). |
| Front-matter helpers — `gates.py:34-75` | Deterministic metadata | Extend for document/date regex vs candidate YAML | PID mismatch → **fail**; date/title ambiguity → **review**. |
| New `compare_metadata_outline()` — `unit_judge.py` after `:228` or new `metadata_compare.py` | Deterministic metadata | Pure function → `MetadataOutlineCheck`, no `run_judge_task` | Shadow: `TAPETUM_METADATA_SHADOW=1`; ship drops metadata from prompt fingerprint class (`cli.py` ~505-512 contract). |
| `UnitCheck` — `models.py:298-320` | Verdict-first | Keep as persistence shape; add `UnitCheckClear` + `UnitCheckDefects` | Reasoning-first CoT today; P50 pass JSON ~77 tok. Validator `verdict_matches_defects` `:316-320`. |
| `DefectFinding` — `models.py:231-259` | Verdict-first | Enum-harden `defect_type` to Literal of eight categories; slim served JSON schema | Tactic B from schema-slim research. |
| `_check_one_unit` — `unit_judge.py:770-809` | Verdict-first; payload scoping | (1) Two-stage Clear→Defects routing + `to_unit_check()`; (2) replace full `candidate_md` (`:791-798`) with CANDIDATE WINDOW + PRESENCE INDEX | Call site `UnitCheck` `:801-807`. Pass `max_tokens=128`, fail `768`. |
| `run_judge_task` — `judge_task.py:52+` | Verdict-first | Optional `max_tokens` forward | Caps useless without schema change. |
| Prompt reorder PDF unit/page — `unit_judge.py:791-798`, `pdf_judge.py:397-403` | Prefix / APC (v11 partial) | Already candidate-md-first on unit/page | Finish: monolith RAW-PDF-first `pdf_judge.py:662-665`; metadata source-first `unit_judge.py:252-261`; text triage `adjudicate.py`. |
| `_paper_guard_tag` — `cli.py:467-479`; PDF wire `:1331-1333` | Prefix / HMAC (v11 partial) | Thread `guard_tag` into `adjudicate_paper()` (`cli.py:1402-1412` today: **no** tag) | Est. **−100 to −200 s** unrealized on text lane. |
| `_sort_pids_ljf` — `cli.py:1030-1038`, applied `:1063` | LJF (v11, **Done**) | Keep | Tail **~−30 to −60 s**. |
| `asyncio.to_thread(screen_pages)` — `pdf_judge.py:658` | Client stall (v11, **Done**) | Keep | **~−30 s**. |
| `MONOLITH_TIMEOUT_SECONDS` — `constants.py:245` (=240); PDF `pdf_judge.py:672-681`; text `adjudicate.py:244-246` | Hung-slot guard (v11, **Done**) | Keep | Bounds worst case; not a mean-wall lever. |
| Empty-packet pre-filter — `unit_judge.py:370-381` | Quota hygiene (v10, **Done**) | Keep | Stops burning `MAX_UNIT_CHECKS` on unroutable IDs. |
| Error tombstones + `--retry-errors` — `cli.py:373-378`, `:810-828`, skip `:1269-1293` | Warm skip (v11, **Done**) | Keep | Cold wall unchanged; warm **65 s → ~10–15 s**. |
| Escalation loop — `pdf_judge.py:818-944` | Escalation dedupe (Tier 2) | Skip unit check when page escalation already covered same page | Est. **~−23 s**. |
| `_select_units_with_quotas` — `unit_judge.py:175+`; `MAX_UNIT_CHECKS = 5` — `constants.py:223` | Router combo_safe; dynamic quota | Tighten `combo_safe` emission / selection; optional cap-3 A/B | Post-short-circuit **~−80 to −130 s** (router); cap-3 larger but holdout-gated. |
| `_check_one_unit` full-md inject — `unit_judge.py:791-798` | Payload scoping | Scoped ~10–12k tok: H2 ±1 neighbor + presence index; grounding stays on full `raw_tomd_md` (`:742-744`) | **Prerequisite** for dense S=32–48. Without it dense offload is **negative EV** (S≤16, L≈20 s). |
| New `payload_scope.py` — `build_unit_window()`, `build_presence_index()` | Payload scoping | Pure functions; constants `UNIT_SCOPE_*` in `constants.py` | Soft 8192 / hard 12288 chars; neighbor=1; oversize → MoE fallback (~8/381). |
| `chunking.py` `_split_sections` / `chunk_markdown` | Payload scoping | Reuse fence-aware H2 splits for window | Table units: isolate table section, no ±1 prose. |
| Service router (new) — `cli.py` / `judge_task.py` (or small router module) | Dense offload | Map call class → `{alliance-pod, h200-qwen3-32b}`; per-pod semaphores; oversize token preflight → MoE | MoE keeps ~428 calls (monolith, HTML tier-1/2, page esc, 8 oversize units). Dense ~1879 (units+metadata) until det-metadata removes 377. Wall = `max(T_dense, T_moe)`. |
| Monolith path — `pdf_judge.py:668-681` (phase monolith) | Dense offload / keep-monolith | **Do not** offload monolith to dense | Needs 393k context; ~7.5% wall; sole document-wide reorder lens. |
| Page escalation — `pdf_judge.py` (scoped page + full md) | Dense offload | Stay on MoE | ~16 calls; 393k headroom. |
| Fingerprint builders — `cli.py:604-647` (`coverage_mode`, schemas) | Dense / verdict-first / det-metadata | Include service+model, schema variant (`unit_schema_variant`), drop metadata class when det ships | Incremental skip poison risk if bump skipped. |
| Sidecar write / fusion — `cli.py:725-765`; `fusion.py` | All semantic levers | Persist shadow fields (`metadata_outline_check_det`); equivalence vector for A/B | Fusion demotion-only; never gates CI. |
| Server ops (not client) — `alliance-pod` `--max-num-seqs 16` | Ops / S_eff | **Keep 16**; never 32 (+57% wall) | Docs: `tapetum_llm.md:29,301-303`; client `_DEFAULT_CONCURRENCY = 32` at `cli.py:133` overfills slots. Optional: DeepEP `deepep_low_latency`, MBT 16384, APC; MTP k=1 A/B only (do not bank). |

---

## Lever → primary files (quick index)

| Lever | Primary surfaces | Status @ HEAD |
|-------|------------------|---------------|
| Metadata short-circuit | `pdf_judge.py`, `adjudicate.py`, `_LANE_VERSION` | **Done** (v11) |
| HMAC + md-first | `cli.py`, `unit_judge.py`, `pdf_judge.py`, `adjudicate.py` | **Partial** |
| Deterministic metadata | `unit_judge.py`, `source_router.py`, `html_outline.py`, `gates.py`, `models.py` | **Not started** |
| Verdict-first | `models.py`, `unit_judge.py`, `judge_task.py` | **Not started** |
| Payload scoping | `unit_judge.py`, new `payload_scope.py`, `constants.py`, `chunking.py` | **Not started** |
| Dense offload | `cli.py`, `judge_task.py`, routing + SERVICES | **Not started** (infra: dense pods may be 404) |
| Router / MAX_UNIT_CHECKS | `source_router.py`, `unit_judge.py`, `constants.py` | **Not started** |
| Escalation dedupe | `pdf_judge.py` | **Not started** |

---

## Arithmetic reminder (do not mis-stack)

```
wall = (N_rem × L_eff) / S_eff + T + C − L_abs
```

- `S_eff = 16` on `alliance-pod` always for this program.
- Apply decode shrink (`L_abs` / verdict-first) on **survivors only** after short-circuit.
- Heterogeneous dense: `wall ≈ max(T_moe, T_dense) + T_client`, not sum of legs on one queue.
- Payload scoping enables dense S>16; it is not itself the ≤600 s closer.

---

## References

- Impl status: `../10-impl-status-1pod.md`
- Det metadata: `../13-deterministic-metadata.md`
- Verdict-first: `../15-verdict-first-design.md`
- Dense offload: `../12-dense-offload-architecture.md`
- Payload scope: `../23-payload-scope-dense.md`
- Packages: `../18-packages-1pod.md`
