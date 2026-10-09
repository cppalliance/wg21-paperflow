# ADR-004: Payload scoping for dense unit checks

**Status:** Proposed

**Date:** 2026-07-24

---

## Context

Unit checks today inject full `candidate_md` on every call (`unit_judge.py`). Measured candidate sizes reach P95 ~50k tokens. On `h200-qwen3-32b` (131k max, BF16 KV ~256 KiB/token), full-md p95 saturates KV at **S≤16** with preemption and **L≈20 s** — MoE-class latency.

Heterogeneous offload (ADR-003) needs dense at **S=32–48** and **L≈8–12 s** (2× decode hypothesis). That KV math only closes with scoped inputs (~12k tok/req) plus FP8 KV (~1.5 GiB/seq → ~44–48 concurrent).

Without scoping, offload is **negative EV**: `T_dense ≈ 1510×20/16 ≈ 1888 s` while adding router complexity. Scoping is the documented prerequisite for dense S>16; it does not by itself close the single-pod ≤600 s gap (MoE monolith remains limiting).

---

## Decision

Scope **only** the LLM prompt in `_check_one_unit` (v1). Leave monolith, page escalation, metadata, and post-hoc grounding on full document.

### Minimal scope design

1. **H2 window (±1 neighbor)**  
   Fence-aware split via existing `chunking.py:_split_sections`. Include preamble (front matter + H1, ≤2k chars) + anchor section ±1.  
   Constants: `UNIT_SCOPE_SOFT_CHARS=8192`, `UNIT_SCOPE_HARD_CHARS=12288`, `UNIT_SCOPE_NEIGHBOR_SECTIONS=1`.  
   HTML `section:N` anchors by index; PDF `page:N` by heading match then proportional fallback.  
   Table presence units: table section only (no ±1 prose).  
   Hard-cap overflow or unresolved anchor → **fail-closed MoE fallback** (full md on `alliance-pod`), not silent truncate on dense.

2. **Presence index (mechanical ANYWHERE oracle)**  
   Built once per paper from full `candidate_md`: normalized headings, 5-grams (≥20 norm chars), `_CPP_KEYWORDS`, dehyphenation join variants; cap 512 entries, sorted. Serialize ~200–300 tokens under a fixed header. Prompt clause: index is authoritative for cross-page reflow; window is for local fidelity only.

3. **Post-hoc unchanged**  
   `verify_unit_evidence` and `classify_candidate_evidence` stay on full `raw_tomd_md`. Mechanical keyword counts stay full-doc.

4. **Prompt layout**  
   `CANDIDATE WINDOW` + `PRESENCE INDEX` + source text; keep paper-stable `guard_tag` and candidate-first ordering.

### Implementation touchpoints

| File | Change |
|------|--------|
| `tapetum_llm/constants.py` | `UNIT_SCOPE_*` |
| `tapetum_llm/payload_scope.py` (new) | `build_presence_index()`, `build_unit_window()` — pure, no I/O |
| `tapetum_llm/unit_judge.py` | Wire scope + MoE fallback hook |
| `tests/test_payload_scope.py` (new) | Deterministic fixtures |

**Out of scope v1:** page-escalation scoping, monolith scoping, multi-unit batching.

**Landing order:** scoping **before** dense `_LANE_VERSION` bump; bench at 12k/256 (and 8k/256) after land.

---

## Consequences

**Positive**

- Unblocks dense S=32–48 + FP8 KV path assumed by ADR-003/005 wall math.
- P50 user payload drops ~9.3k → ~2.9k tokens; P90 stays under ~10–12k with hard cap.
- Prefill-only savings on MoE (~198 s / ~7%) are secondary; primary win is **KV headroom for concurrency**.

**Negative / constraints**

- Cross-page join risk if window lacks neighbor/index → false-fail; mitigated by ±1 + presence clause + full-doc grounding.
- Scoped window can hide remote defects → false-clear risk; require `source_quote` on defects and full-doc grounding; zero-defect pass does not prove absence.
- Does not move fleet wall below MoE monolith term (~511 s class after offload).
- Quality still gated by 381/381 A/B after dense routing lands.

---

## Evidence

| Claim | Source |
|-------|--------|
| Full md today; P50/P90/P95 sizes | `23-payload-scope-dense.md`; `13-payload-scoper.md` |
| Full-md dense → S≤16, L≈20 s; scoped+FP8 → S=32–48 | `23`; `105-vllm-dense-judge-throughput.md` |
| Without scope: negative EV / `NEGATIVE-EV-WITHOUT-SCOPE` | `12-dense-offload-architecture.md` Scenario D; `105` |
| Minimal design: H2±1 + presence index | `23-payload-scope-dense.md`; `20-payload-scoping-auditor.md` |
| Scoping primary win = KV headroom, not wall | `23` wall impact table; `12` |
| ~8/381 oversize / hard-cap → MoE fallback | `23-small-judge-evaluator.md` via `12`, `23` |

---

## Open blockers

1. **Implement and unit-test** `build_unit_scope` / `build_presence_index` on golden fixtures (join tails, tables, keyword-heavy papers).
2. **`vllm bench serve`** on live `h200-qwen3-32b` at 12k/256 and 8k/256, concurrency 16→64; confirm no preemption at S=48 (blocked on dense pod liveness — ADR-003 / `26`).
3. If bench shows L>15 s at S=32 despite scoping → tighten hard cap to ~8k or add a second dense shard.
4. Ship only with (or immediately before) dense A/B; do not bump `_LANE_VERSION` for dense without scoped production shapes.
