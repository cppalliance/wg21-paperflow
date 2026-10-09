# 18 - Client-Stall-Auditor

**Verdict:** usable-with-conditions (+ P28/P43 event-loop blocking claims hold for all sync CPU between `await run_judge_task` calls; v11 landed `screen_pages` `to_thread`, monolith `wait_for`, and LJF, but candidate-token cache and four other sync bundles still stall the fleet asyncio thread; at c=32 expect **~22–42 s** remaining wall (~0.7–1.4% of 3003 s), not minutes)
**Confidence:** high

## Scope

Audit sync CPU on the tapetum_llm asyncio path at HEAD (lane v11). Confirm speedup personas **P26** (timeout / slot tail), **P28** (semaphore + event-loop topology), **P43** (grounding CPU profiler). Baseline wall **3003.4 s**, **381 papers**, client **c=32**, server **16 slots** (`research/cold-run-10min/00-baseline.md`).

**difflib:** not used anywhere under `packages/whisker/src/whisker/tapetum_llm/`. The analogous whole-document fuzzy cost is **rapidfuzz `partial_ratio`** in `grounding.py:327-329` (evidence grounding), not stdlib `difflib`. Lane 1 golden stability uses `difflib` in `whisker/golden.py`, which is outside the tapetum async fleet path.

---

## P26 / P28 / P43 claim confirmation

| Persona | Claim | HEAD status | Verdict |
|---------|-------|-------------|---------|
| **P26** | Zero timeout hits on cold run; monolith had no per-call cap; tightening saves **≈0 s** happy-path wall | `MONOLITH_TIMEOUT_SECONDS=240` now wraps PDF monolith (`pdf_judge.py:672-681`) and HTML tier calls (`adjudicate.py:257-309`). Cold fleet had **0** operational timeouts. | **Confirmed** for throughput; lever is **tail-risk**, not the 48→10 min gap. |
| **P28** | **Zero** `asyncio.to_thread` in tapetum_llm; sync CPU between awaits freezes all **32** paper workers; fix saves **~30–60 s** wall | **Partially superseded.** Exactly **one** `to_thread` call now: `screen_pages` (`pdf_judge.py:658`). **Five** other CPU bundles still run synchronously inside `async def` coroutines (see below). | **Core mechanism confirmed**; magnitude reduced by v11 partial fix. |
| **P43** | Fleet client CPU **≈98 s** (~3.3% wall); `screen_pages` **41.1 s** sum (52% PDF CPU); re-tokenizing full md per page; cache saves **38.1 s** CPU; full `to_thread` + cache saves **~30–40 s** wall | `screen_pages` still calls `content_recall(tomd_md, page)` per page with no candidate cache (`pdf_judge.py:317`, `metrics.py:388-392`). Benchmark numbers from `_scratch/research-tapetum-llm-speedup/bench_grounding_cpu.py` (2026-07-23) not re-run at HEAD; algorithm unchanged. | **Confirmed**; one implementation item (`to_thread` for `screen_pages`) already shipped. |

**Code-drift since P28/P43 (v11, `_LANE_VERSION = 11`, `cli.py:123`):**

- Landed: `screen_pages` → `asyncio.to_thread` (`pdf_judge.py:658`), monolith `wait_for` (`pdf_judge.py:672-681`), LJF fleet order (`cli.py:1030-1063`), metadata short-circuit (reduces how often post-LLM CPU runs, not CPU cost per call).
- Not landed: candidate `Counter(content_tokens(tomd_md))` cache inside `screen_pages`; `to_thread` on doc metrics, monolith/page grounding, `route_*_units`, or `verify_unit_evidence`.

---

## Sync CPU inventory (async path)

All sites below execute on the **single asyncio event-loop thread** unless noted. With **c=32**, one paper holding the loop blocks dispatch and completion handling for every in-flight paper (`judge_task.py:68`, `cli.py:1201`).

| Phase | Location | Mechanism | Fleet CPU sum (P43) | On loop? |
|-------|----------|-----------|---------------------|----------|
| Text-layer prep | `pdf_judge.py:618-635` | PyMuPDF extract, `clean_pages`, `normalize_textlayer`, `strip_binary_payloads` | not isolated in P43 bench | **yes** |
| Doc metrics | `pdf_judge.py:650-651` | `text_nid(normalized_text×2)` + `content_recall(tomd, pdf_text)` | **24.3 s** (PDF) | **yes** |
| Page screen | `pdf_judge.py:658` → `297-322` | per-page `content_recall` re-tokenizes full candidate md | **41.1 s** (PDF) | **no** (thread) |
| Monolith grounding | `pdf_judge.py:722-723` | `ground_spans` + `classify_candidate_evidence` on full texts | **2.3 + 3.8 s** | **yes** |
| Page escalation grounding | `pdf_judge.py:843-852` | per escalated page: `ground_page_spans` + `classify_candidate_evidence` | tail-only | **yes** |
| PDF routing | `pdf_judge.py:904` | `route_pdf_units`: doc-wide Counters + per-page `content_recall` | subset of routing CPU | **yes** |
| Unit verify | `unit_judge.py:439` → `695-753` | per-defect `ground_spans` + `classify_candidate_evidence(full md)` | **8.2 s** | **yes** |
| HTML decide | `adjudicate.py:280, 320` | `ground_spans` in `_escalation_signals` and `_custom_decide` | part of HTML **18.2 s** lane total | **yes** |
| HTML routing | `adjudicate.py:536, 579` | `route_html_units` / `route_pdf_units` | part of HTML lane | **yes** |

**Token-counting hot path:** `content_recall` always builds `hyp = Counter(content_tokens(candidate))` on every call (`metrics.py:388-392`). Called from `screen_pages` (N pages), `route_pdf_units` (N pages), doc metrics (once), and `source_router` HTML path (`source_router.py:212, 329`).

---

## Top 3 blocking sites (ranked by fleet impact)

### 1. `screen_pages` candidate re-tokenization (cache, not threading)

**Evidence:** `pdf_judge.py:307-317` loops pages; each iteration calls `content_recall(tomd_md, dehyphenated)` which re-tokenizes the **full** markdown (`metrics.py:391`). P43 measured **41.1 s** fleet sum, max **7.46 s** per paper (`P3596R1`, 100 pages).

**Already fixed:** event-loop offload at `pdf_judge.py:658`.

**Proposed fix (cache):**

```python
# pdf_judge.py:306 — inside screen_pages(), before the for loop
from collections import Counter
hyp = Counter(content_tokens(tomd_md))

# pdf_judge.py:317 — replace content_recall(tomd_md, dehyphenated) with
# a local helper that passes hyp= and only tokenizes reference (page) side
```

Alternative: add optional `candidate_tokens: Counter | None = None` to `content_recall` (`metrics.py:376`).

**Estimated fleet savings at c=32:** **~38 s CPU** (P43 micro-benchmark); **~2–5 s wall** incremental once threaded (thread pool overlap already absorbs most stall; cache reduces thread time and tail contention).

---

### 2. Pre-monolith doc metrics block

**Evidence:** `pdf_judge.py:650-651` runs synchronously **before** the first `await`:

```650:651:packages/whisker/src/whisker/tapetum_llm/pdf_judge.py
    nid = text_nid(normalized_text(pdf_text), normalized_text(tomd_md))
    recall = content_recall(tomd_md, pdf_text)
```

`text_nid` is whole-document normalized edit distance (rapidfuzz-backed in `metrics.py`); runs once per PDF paper. P43 fleet sum **24.3 s**, max **3.29 s**.

**Proposed fix (`to_thread`):**

```python
# pdf_judge.py:650 — replace sync block with:
nid, recall = await asyncio.to_thread(_doc_metrics, pdf_text, tomd_md)

# new helper near screen_pages:
def _doc_metrics(pdf_text: str, tomd_md: str) -> tuple[float, float]:
    return (
        text_nid(normalized_text(pdf_text), normalized_text(tomd_md)),
        content_recall(tomd_md, pdf_text),
    )
```

**Estimated fleet savings at c=32:** **~9–13 s wall** (~24.3/98 × P43's 30–40 s overlap band, plus tail papers up to 3 s blocking all workers).

---

### 3. Post-LLM grounding + unit evidence verification

**Evidence:**

- Monolith path: `pdf_judge.py:722-723` — sync between metadata `await` and page escalation loop.
- Unit path: `unit_judge.py:439` — `verify_unit_evidence(...)` after the unit LLM loop; each defect re-runs `classify_candidate_evidence` which calls `ground_spans` on **full** `candidate_md` (`grounding.py:434`).
- Page escalation: `pdf_judge.py:843-852` — same pattern per flagged page.

P43 sums: `ground_spans` **2.3 s**, `classify_candidate_evidence` **3.8 s**, `verify_unit_evidence` **8.2 s** → **~14.3 s** fleet CPU (plus page-loop tails).

**Proposed fixes:**

| Site | Action |
|------|--------|
| `pdf_judge.py:722-723` | `await asyncio.to_thread(_monolith_ground, spans, pdf_text, raw_tomd_md)` |
| `pdf_judge.py:843-852` | hoist per-page sync block into `to_thread` inside the escalation loop |
| `unit_judge.py:439` | `await asyncio.to_thread(verify_unit_evidence, unit_results, unit_text_map, candidate_md)` |
| `grounding.py:434` | per-call memo: `candidate_grounded_cache = {}` keyed by `(id(candidate_markdown), tuple(span quotes))` — saves **~2–4 s** CPU (P43 MED) |

**Estimated fleet savings at c=32:** **~8–12 s wall** from `to_thread`; **~2–4 s** additional from classify memo (CPU, small wall).

---

## Secondary sites (below top 3)

| Site | Lines | Note | Est. wall @ c=32 |
|------|-------|------|------------------|
| `route_pdf_units` | `pdf_judge.py:904`, `source_router.py:167-222` | Per-page `content_recall`; shares screen_pages token pattern | **~3–6 s** via `to_thread` |
| Text-layer extract | `pdf_judge.py:618-631` | PyMuPDF + normalize before any await | **~2–5 s** (not in P43 bench) |
| HTML `adjudicate` grounding | `adjudicate.py:280, 320` | 198 HTML papers, no `screen_pages` | **~4–8 s** bundled `to_thread` on `_custom_decide` CPU |
| `verify_defect_counts` | `unit_judge.py:462` | P43: **0.0 s** sum on cold fleet (dormant) | **~0 s** |

---

## Fleet savings arithmetic (c=32)

**Definitions:**

- **Fleet CPU sum** ≈ **98 s** = total sync Python time if one thread ran all papers sequentially (P43).
- **Wall stall** ≤ CPU sum when bursts align; with LLM-bound fleet and mixed paper sizes, P43/P28 model **~30–40 s** wall from **full** event-loop offload (not 98 s).

**Already recovered (v11):**

| Lever | Est. wall saved |
|-------|-----------------|
| `screen_pages` `to_thread` (`pdf_judge.py:658`) | **~12–18 s** (~40% of P43's 30–40 s band) |
| LJF (`cli.py:1030-1063`) | **~60–180 s** (scheduling, separate from stall class) |
| Monolith `wait_for` (P26 tail) | **≈0 s** happy path |

**Remaining client-stall package (cache + `to_thread` on sites 1–3 + routing):**

| Component | Wall @ c=32 |
|-----------|-------------|
| Candidate token cache in `screen_pages` | **~2–5 s** |
| Doc metrics `to_thread` | **~9–13 s** |
| Grounding + `verify_unit_evidence` `to_thread` + classify memo | **~10–16 s** |
| `route_pdf_units` / HTML decide offload | **~5–10 s** |
| **Total remaining stall class** | **~22–42 s** (~**0.7–1.4%** of 3003 s) |

**If v11 had not shipped `screen_pages` `to_thread`:** add **~12–18 s** → **~34–60 s** total stall class, consistent with P28/P43 **~30–40 s** central estimate.

**Interaction with c=32 paper semaphore:** the measured c=16→c=32 gain (**692.3 s vs 722.4 s**, **−4.2%**) is paper-count overfill, largely orthogonal. Event-loop stalls explain micro-bubbles **below** that ceiling (P28 CRITICAL finding).

---

## Concrete patch list (file:line)

| Priority | Change | Lines |
|----------|--------|-------|
| P0 cache | Precompute `hyp = Counter(content_tokens(tomd_md))` in `screen_pages` | `pdf_judge.py:306-317` |
| P0 thread | `await asyncio.to_thread(_doc_metrics, ...)` | `pdf_judge.py:650-651` |
| P1 thread | Wrap monolith grounding | `pdf_judge.py:722-723` |
| P1 thread | Wrap `verify_unit_evidence` call | `unit_judge.py:439` |
| P1 thread | Per-page escalation grounding | `pdf_judge.py:843-852` |
| P2 thread | Wrap `route_pdf_units` before unit checks | `pdf_judge.py:904` |
| P2 cache | Per-call candidate normalization memo in `classify_candidate_evidence` | `grounding.py:419-434` |
| P2 thread | HTML decide CPU in `_custom_decide` / `_escalation_signals` | `adjudicate.py:280, 320` |

Optional API extension: `content_recall(candidate, reference, *, candidate_tokens: Counter | None = None)` at `metrics.py:376` so `route_pdf_units` and `screen_pages` share one cache pattern.

---

## False-pass hypothesis

A **cross-paper** module-global cache of `content_tokens` keyed by string length (not object identity) could serve stale counters if markdown were mutated in place between calls. Mitigation: **per-call local** `hyp` inside `screen_pages` / `route_pdf_units` only (P43 false-pass note).

## False-fail hypothesis

`asyncio.to_thread` with unchanged thresholds cannot false-fail: multiset math is order-independent (`metrics.py:388-393`). A real false-fail requires lowering `PAGE_RECALL_FLOOR` or `EVIDENCE_FUZZY_FLOOR`, not CPU plumbing.

## What would change my mind

Pod-side metrics showing **>10% of wall** with `<16` active decodes **after** full offload **and** c=32, with timestamps aligned to HTML-lane `adjudicate.py:320` bursts — would upgrade the **~22–42 s** stall estimate to a schedulable multi-minute lever.

---

## Executive summary (return payload)

**Top 3 blocking sites:**

1. **`screen_pages` candidate re-tokenization** — `pdf_judge.py:317` / `metrics.py:391` — **41.1 s** fleet CPU; fix: cache at `pdf_judge.py:306`; **~2–5 s** wall left at c=32 (`to_thread` already at `:658`).
2. **Pre-monolith doc metrics** — `pdf_judge.py:650-651` — **24.3 s** fleet CPU; fix: `to_thread`; **~9–13 s** wall at c=32.
3. **Post-LLM grounding + unit verify** — `pdf_judge.py:722-723`, `unit_judge.py:439`, `grounding.py:434` — **~14 s** fleet CPU; fix: `to_thread` + classify memo; **~10–16 s** wall at c=32.

**Estimated fleet savings (remaining stall work, c=32):** **~22–42 s** on the 3003 s cold run (**~0.7–1.4%**). Not on the path to 10 min alone; pairs with metadata short-circuit (~1341 s), prefix cache, and dual-pod sharding per `00-baseline.md` lever ranking.

**P26/P28/P43:** timeout tail claims confirmed (≈0 s happy path); event-loop blocking mechanism confirmed with partial v11 remediation; P43 CPU sums and cache/`to_thread` wall band confirmed pending re-benchmark.
