# 23 - Payload scope for dense S>16

**Verdict:** usable-with-conditions — a minimal **presence-index + H2 window** in `_check_one_unit` caps unit-check LLM input at **~10–12k tokens**, which is the stated prerequisite for **`h200-qwen3-32b` at S=32–48 with FP8 KV**; it does **not** by itself close the single-pod ≤600 s gap (MoE monolith queue stays limiting).
**Confidence:** high (KV math + file:line anchors); medium (page→section mapping edge cases without holdout A/B)

**Sources:** `research/cold-run-10min-1pod/12-dense-offload-architecture.md`, `research/tapetum-llm-speedup/{13-payload-scoper,105-vllm-dense-judge-throughput}.md`, `research/cold-run-10min/20-payload-scoping-auditor.md`, `packages/whisker/src/whisker/tapetum_llm/{unit_judge.py,chunking.py,source_router.py,grounding.py}`.

**Hard constraint:** MoE `alliance-pod` stays **S=16**. Dense slot lift applies only to offload endpoints.

---

## Executive answer

| Question | Answer |
|----------|--------|
| **Unblock dense S>16?** | **YES** — scoped unit payloads are the documented prerequisite; without them dense stays KV-saturated at **S≤16** and offload is negative EV (`105`, `12`). |
| **Minimal sufficient scope?** | **YES** — H2 window ±1 neighbor + compact presence index + unchanged post-hoc grounding on full `raw_tomd_md`. |
| **Closes ≤600 s alone?** | **NO** — even at S=48, fleet wall stays **MoE-bound ~511–710 s** (`12` scenarios A–B). |

---

## Blocker recap

Today `_check_one_unit` injects **full `candidate_md`** on every unit call (`unit_judge.py:791-798`). Measured candidate sizes (`13-payload-scoper.md`):

| Percentile | Chars | ~Tokens |
|------------|------:|--------:|
| P50 | 34,336 | ~8,584 |
| P90 | 139,148 | ~34,787 |
| P95 | 220,688 | ~50,000 |

Dense pod KV math (`105`):

- Qwen3-32B @ 131k on 1×H200, **~256 KiB/token** BF16 KV.
- **Full-md p95 (~50k tok/req):** ~12.8 GiB/seq → **S≤16**, preemption, **L≈20 s** (MoE-class).
- **Scoped ~12k tok/req + FP8 KV:** ~1.5 GiB/seq → **~44–48 concurrent seqs** → **S=32–48**, **L=8–12 s** (hypothesis).

**Without scoping:** `T_dense = 1510×20/16 ≈ 1888 s` — worse than keeping units on MoE (`105` false-pass).

---

## Minimal design (unit checks only)

Scope **only** the LLM prompt in `_check_one_unit`. Do **not** change monolith, page escalation, metadata, or post-hoc paths in v1.

### 1. H2 window (candidate slice)

Reuse existing fence-aware H2 splitting (`chunking.py:_split_sections`, same boundary rule as `chunk_markdown`).

**Constants (new in `constants.py`):**

| Constant | Value | Role |
|----------|------:|------|
| `UNIT_SCOPE_SOFT_CHARS` | 8,192 | Target window size |
| `UNIT_SCOPE_HARD_CHARS` | 12,288 | Hard cap; overflow → MoE fallback |
| `UNIT_SCOPE_NEIGHBOR_SECTIONS` | 1 | ±1 H2 section |

**Section selection:**

| `unit_id` | Anchor index | Window |
|-----------|--------------|--------|
| `section:N` (HTML) | `N` | sections `[max(0,N−1) .. min(last,N+1)]` |
| `page:N` (PDF) | Best-match H2 section | Match `unit.heading_candidates` titles (via `normalize_heading_text`) against section titles from `_parse_markdown_sections`; fallback: `floor(N / total_pages × num_h2_sections)` |

**Window body:**

```
[preamble: front matter + H1 title block, always included, ≤2k chars]
+ [concatenated H2 sections in anchor±1]
→ truncate at UNIT_SCOPE_HARD_CHARS with explicit `<!-- scope:truncated -->` marker
```

**MoE fallback (fail-closed):** if window still exceeds `UNIT_SCOPE_HARD_CHARS` after neighbor trim (single giant H2/table), or anchor unresolved on PDF with zero heading overlap, route this unit check to **`alliance-pod`** unchanged (full md). Expect **~8/381** papers (`23-small-judge-evaluator.md` oversize class).

**Table isolation:** never merge table HTML with unrelated prose in one window slice (unstructured `isolate_table` pattern, `123-unstructured-chunking-strategy.md`); if unit signal is `table_presence`, window = table section only + presence index (no ±1 prose neighbor).

### 2. Presence index (mechanical ANYWHERE oracle)

Built once per paper per run from **full** `candidate_md` (before `strip_binary_payloads` for grounding parity; strip for LLM if current path strips).

**Algorithm (pure, deterministic, no LLM):**

1. `norm = normalized_text(full_md)` (`whisker.metrics.normalized_text`, same surface as `grounding.py:283`).
2. Collect **index entries** (dedupe, sort):
   - Every ATX heading title (normalized, secno-stripped via `normalize_heading_text`).
   - Every word **5-gram** from `norm` where gram length ≥ 20 normalized chars (skips trivial tokens).
   - Every `_CPP_KEYWORDS` token present in `norm`.
   - Dehyphenation variants: for each `-` at line end in raw md, also index the joined form (`implementa` + `tion` → `implementation`) on the normalized surface.
3. Cap: **512 entries**, sorted lexicographically; drop longest grams first if over cap.
4. Serialize as compact lines under a fixed header (~**800–1200 chars**, ~**200–300 tok**):

```
PRESENCE INDEX (document-wide; normalized alnum matches count as present anywhere):
<entry_1>
<entry_2>
...
```

**Prompt clause (add to `UNIT_CHECK_SYSTEM_PROMPT`):**

> If a source phrase normalizes to an entry in PRESENCE INDEX, treat that content as present in the candidate document even when outside CANDIDATE WINDOW. CANDIDATE WINDOW is for local fidelity checks only; PRESENCE INDEX is authoritative for cross-page reflow and join tails (`tomd` cross-page join rule).

**Post-hoc unchanged:** `verify_unit_evidence(..., candidate_md=full raw)` (`unit_judge.py:742-744`), `classify_candidate_evidence` on full doc (`grounding.py:419`). Mechanical keyword counts stay on full md (`unit_judge.py:634`).

### 3. Prompt layout (dense + APC)

Replace full-md block in `_check_one_unit` user message:

```
CANDIDATE WINDOW:
{inject_untrusted(scoped_window, tag)}

PRESENCE INDEX:
{inject_untrusted(presence_index, tag)}

Paper: {pid}
Unit: {unit_id}
Risk signal: {signal_detail}

SOURCE TEXT ({unit_id}):
{inject_untrusted(source_text, tag)}
```

Keep paper-stable `guard_tag` and candidate-first ordering (`unit_judge.py:783-787`, `20-payload-scoping-auditor.md`).

**Estimated per-call tokens (scoped):**

| Component | Tokens |
|-----------|-------:|
| System + schema + guard | ~1,700 |
| CANDIDATE WINDOW (P50) | ~2,000 |
| PRESENCE INDEX | ~250 |
| SOURCE TEXT slice | ~625 |
| **Total user payload** | **~2,875** (P50); **~10–12k** at P90 long sections |

P50 drops from ~9,259 tok (`13`) to ~2,875 tok. P90 long papers stay under **12k** with hard cap + MoE fallback.

---

## KV / concurrency table (dense pod)

Assumptions: `h200-qwen3-32b`, `--max-model-len 131072`, `--kv-cache-dtype fp8`, output ~250 tok mean / 1536 cap.

| Scoped input | KV / seq (FP8) | Feasible S | L_unit (hyp.) | T_dense (1510 calls) |
|-------------:|---------------:|-----------:|--------------:|---------------------:|
| Full md P50 (~8.5k) | ~2.2 GiB | **16–22** | ~18–20 s | **1690–1888 s** |
| Full md P95 (~50k) | ~12.8 GiB | **≤16** | ~20 s | **1888 s** |
| **Scoped ~12k (this design)** | **~1.5 GiB** | **32–48** | **8–12 s** | **315–566 s** |
| Scoped ~8k + APC on shared prefix | ~1.0 GiB | **48–64** | **8–10 s** | **189–315 s** |

**S>16 unblocked when:** (1) scoped payload landed, (2) FP8 KV enabled on dense pod, (3) `UNIT_SCOPE_HARD_CHARS` enforced with MoE fallback for tail outliers.

---

## Quality gates (ship blockers)

| Risk | Mitigation |
|------|------------|
| Cross-page join false-fail | ±1 H2 neighbor + presence index + ANYWHERE clause |
| Cross-page join false-pass (scoped window hides defect) | Model must emit `source_quote` for defects; grounding on full doc; zero-defect pass does not prove absence |
| Index too strict (dehyphenation, wording markup) | Index uses `normalized_text` + dehyphen join variants; fuzzy still abstains in grounding |
| Truncated evidence false-clear | Hard cap → MoE fallback, not silent truncate on dense |
| Dense semantic drift | **381/381** fused verdict parity A/B (`12`, `25`) before `_LANE_VERSION` bump |

**Validation sequence:**

1. Unit-test `build_unit_scope()` + `build_presence_index()` on golden fixtures (join tails, table pages, P0533R8-scale keyword paper).
2. `vllm bench serve` on `h200-qwen3-32b` at **12k/256** and **8k/256**, concurrency sweep 16→64; confirm no preemption warnings at **S=48**.
3. Pilot A/B: 381 papers, dense units + MoE monolith, persona-47 equivalence worksheet.

---

## Implementation touchpoints (minimal diff)

| File | Change |
|------|--------|
| `packages/whisker/src/whisker/tapetum_llm/constants.py` | `UNIT_SCOPE_*` constants |
| `packages/whisker/src/whisker/tapetum_llm/payload_scope.py` (new) | `build_presence_index()`, `build_unit_window()` — pure functions, no I/O |
| `packages/whisker/src/whisker/tapetum_llm/unit_judge.py` | `_check_one_unit`: scoped window + index; prompt clause; MoE fallback hook |
| `packages/whisker/tests/test_payload_scope.py` (new) | Deterministic scope/index tests on fixture md |

**Out of scope v1:** page escalation scoping, monolith scoping, batching multiple units per prompt.

---

## Wall impact (1-pod + dense offload)

Scoping's primary win for dense offload is **KV headroom (S=48)**, not fleet wall:

| Effect | Wall delta |
|--------|----------:|
| Prefill savings alone @ S=16 MoE | ~198 s (~7% of 3003 s) (`13`) |
| Dense S=48 + L=10 s vs units on MoE @ S=16 | **~1536 s** on unit leg (`12` scenario A) |
| Fleet parallel `max(T_dense, T_moe)` | **~511 s** MoE-bound (scenario A) |

Single-pod ≤600 s still needs MODERATE call cuts (metadata short-circuit, router/quota) stacked on dense offload (`12`, `14`).

---

## False-pass hypothesis

Ship dense at **S=48** without payload scoping or FP8 KV: KV preemption keeps **L_unit ≥ 20 s**, dashboards show "48 slots" but wall unchanged — operators conclude dense offload failed when the blocker was unscopped full-md prefills (`105` false-pass).

---

## False-fail hypothesis

H2 window without presence index: cross-page join tail under prior heading → model reports `content_omission` → verified grounding refutes, but wasted decode and `review` caps from evidence uncertainty (`13` false-fail, `21-false-fail-review-mode.md`).

---

## What would change my mind

`vllm bench serve` on `h200-qwen3-32b` at **12k/256** showing preemption or **L>15 s** at **S=32** despite scoped payloads — would downgrade feasible S to **24–32** and require tighter **8k** hard cap or a second dense shard.

---

## Return line

**Unblock dense S>16? YES** — minimal presence-index + H2 window satisfies the scoped-payload prerequisite for **S=32–48** on `h200-qwen3-32b` with FP8 KV. **Implementation + A/B parity still required** before `_LANE_VERSION` bump; scoping alone does not hit ≤600 s on one MoE pod.
