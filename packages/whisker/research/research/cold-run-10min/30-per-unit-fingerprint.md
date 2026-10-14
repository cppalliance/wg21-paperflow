# 30 - Per-Unit Fingerprint Designer

**Verdict:** usable-with-conditions (+ per-unit incremental skip is the right warm/dev lever; it saves zero wall time on a true cold fleet and is out of scope for the 10 min target unless mislabeled as a rerun accelerator)
**Confidence:** high

**In cold-run critical path?** **no**

## Findings

- [CRITICAL] **Today's skip is whole-paper only; any single-key mismatch re-runs the full ~6-call serial cascade.** `_compute_fingerprint` hashes the entire candidate markdown (`md_sha256`), source file, one monolithic `prompt_sha256` (all four PDF-lane system prompts concatenated via `_pdf_prompt_contract()`, `cli.py:505-512`), one `schema_sha256`, `_LANE_VERSION`, model, ideal fields, and `coverage_mode` (`cli.py:595-648`). `_fingerprint_matches` requires every key equal (with coverage-mode superset rules only); one changed page updates `md_sha256` and forces monolith + metadata + all routed unit checks + any page escalations to re-LLM (`cli.py:679-702`, `pdf_judge.py:646-890`). Impact on **cold**: **0 s** — no prior sidecars, nothing to skip. Impact on **warm/dev**: a one-line tomd fix on one page still pays **~6 serial LLM calls (~120 s)** for that paper (`tapetum-llm-speedup/00-baseline.md:38-39`); a `UNIT_CHECK_SYSTEM_PROMPT` edit invalidates **all 381 papers (~3003 s)** because prompt hash is monolithic (`cli.py:599`, `19-incremental-granularity.md:8`).

- [CRITICAL] **Per-unit incremental design: sidecar `call_cache` + partial invalidation, not a faster cold path.** Proposed shape (persona 19): extend tapetum sidecar with per-call-class and per-unit entries, e.g. `call_cache: { "monolith": {prompt_hash, schema_hash, llm_output}, "metadata": {...}, "units": { "page:7": {source_sha256, risk_signal_sha256, prompt_hash, llm_output} }, "page_escalations": { "page:3": {...} } }`. Whole-paper gate becomes: skip only if source, coverage, ideal fields, **and** every required unit/page entry hits; otherwise run missing classes/units only, then deterministic merge (`pdf_judge.py:710-928`, `unit_judge.py:311-385`). Impact on **cold (381 papers, empty `whisker/llm/`)**: **0 s** — first run writes sidecars; incremental logic never fires. Impact on **warm/dev (surgical tomd re-convert, routed mode, median ~5 units)**: **6 → ~3 LLM calls** (monolith + metadata + ~1 changed unit; unchanged units re-ground only) ≈ **−50% wall per changed paper** (~60 s vs ~120 s) (`19-incremental-granularity.md:14-16`). Fleet unchanged papers still skip in **<1 s** via existing whole-paper fingerprint (`cold-run-10min/00-baseline.md:20`).

- [HIGH] **Per-unit LLM skip is unsound without mandatory re-grounding; monolith/metadata must re-LLM on any candidate change.** Unit and page prompts declare ANYWHERE presence: content counts as present if it appears anywhere in candidate markdown (`unit_judge.py:137-138`, `pdf_judge.py:225-226`). Post-processing already searches the full candidate via `classify_candidate_evidence(grounded, raw_tomd_md)` (`pdf_judge.py:697`, `783-786`). Sound skip conditions: (1) `source_page_sha256` unchanged for that `unit_id`; (2) unit-class prompt/schema/`lane_version` unchanged; (3) router `risk_signal` fingerprint unchanged; (4) on **any** `md_sha256` change, always re-run deterministic re-ground + verdict fold on cached LLM outputs; (5) **always** re-LLM monolith + metadata when candidate changes (`19-incremental-granularity.md:12-13`). Impact: design complexity is **warm-path correctness**, not cold throughput. Quality risk: **HIGH** without (4); **LOW–MEDIUM** with (4)+(5).

- [HIGH] **Call-class prompt splitting is a separate, fleet-scale warm/cold-rerun win — not the same as per-unit skip.** Splitting monolithic `prompt_sha256` into `monolith_prompt_sha256`, `metadata_*`, `unit_*`, etc. lets a unit-prompt-only deploy re-run **~1510 unit calls (~1888 s)** instead of **2284 (~3003 s)** (`19-incremental-granularity.md:10-11`). That helps **prompt-bump reruns** (still a rerun, not a greenfield cold), not the **first** 381-paper cold where every paper lacks a sidecar. Per-unit skip stacks on top for **markdown edits**; call-class split stacks for **prompt/schema edits**. Neither replaces levers ranked in `cold-run-10min/00-baseline.md:32-38` (metadata short-circuit, prefix cache, dual-pod, etc.).

- [MED] **Error tombstone fingerprints (synthesis lever #5) are warm-only and orthogonal.** Whole-paper error tombstones today carry no fingerprint, so warm runs re-pay full cascades for ~6 error papers (~55 s of 64.8 s warm) (`SYNTHESIS.md:35`, `150-verifier-warmrun-quality.md:8`). Storing fingerprint on tombstones fixes **steady-state warm**, not cold. Per-unit cache is a **deeper** incremental layer for **partial** invalidation; tombstone fingerprint is a **shallower** fix for **error** skip. Both are dev-iteration / rerun accelerators.

- [MED] **Typical tomd reconversion scope favors per-unit savings in dev, not in cold fleet.** Golden snapshot diffs cluster on **1 page or one code/table block** (e.g. p4012r0-page-10: 64% line churn on one page; p4012r0-codeblock: 14% on one construct) (`19-incremental-granularity.md:16`). Expect **1–2 invalidated source units** per surgical fix vs **≥30% of pages** on structural reflow. Impact: per-unit skip saves **~0.8–4 unit calls per changed paper** in routed mode (`MAX_UNIT_CHECKS=5`); during a **full cold convert+judge** of 381 papers, almost every paper is new or `--force` — per-unit granularity is irrelevant.

- [LOW] **Explicitly out of scope for the 10 min cold target.** Prior synthesis central estimate **~596 s (9–11 min)** from CONSERVATIVE+MODERATE levers that cut **in-flight LLM work** (metadata short-circuit ~1341 s, prefix/APC ~600–1100 s, dual-pod ~1.9×, verdict-first schema, client stalls) (`cold-run-10min/00-baseline.md:6-8`, `32-38`). Per-unit fingerprint removes **redundant calls only when a prior sidecar exists and only part of the input changed**. On greenfield cold: **2284 calls remain 2284 calls**. Even perfect per-unit skip on a hypothetical "all papers previously judged, one page edited fleet-wide" scenario is a **rerun** optimization, not the **first-run** path the 10 min goal names. Ship per-unit incremental **after** cold-path levers land, for golden-PR / tomd-fix iteration loops.

## Cold vs warm/dev impact summary

| Scenario | Whole-paper fingerprint (today) | Per-unit fingerprint (proposed) |
|----------|--------------------------------|----------------------------------|
| **Cold fleet (381 papers, no sidecars)** | 3003 s; every paper judged | **3003 s; no change** |
| **Cold fleet (`--force`)** | 3003 s | **3003 s; no change** |
| **Warm fleet (unchanged inputs)** | 64.8 s (375/381 skip) | **~same** (whole-paper gate still wins) |
| **Dev: one paper, one page tomd fix** | ~120 s (6 calls) | **~60 s (~3 calls + re-ground)** |
| **Dev: unit prompt edit, 381 papers** | ~3003 s (monolithic prompt hash) | **~1888 s** with call-class split; per-unit adds little |
| **Dev: re-run after transient error** | Full cascade per error tombstone | Tombstone fingerprint helps; per-unit optional |

## False-pass hypothesis

**P0533R9-class cross-page ANYWHERE refutation:** unit check cached `pass` on `page:12` while an older candidate had satisfying text on page 18; tomd re-convert removes page-18 matches but leaves page-12 source unchanged. Per-unit LLM skip **without** re-grounding preserves stale `pass`; mandatory `classify_candidate_evidence` against new full markdown would surface `candidate_not_found` (`19-incremental-granularity.md:24-25`). Mitigation: re-ground on any `md_sha256` change.

## False-fail hypothesis

**Front-matter-only markdown edit:** skipping monolith when only YAML front matter changed misses TOC-leak detection in monolith reasoning (`pdf_judge.py:180-202`). Mitigation: always re-LLM monolith + metadata on any candidate change (condition 5 in persona 19).

## What would change my mind

Sidecar replay on the 381-paper fleet showing **>5 papers** where a cached unit LLM `pass` flipped to **`fail` after re-ground-only** (no unit re-LLM) when another page's markdown changed would prove per-unit LLM skip is unsafe even with re-grounding and would reduce the lever to call-class versioning only (`19-incremental-granularity.md:30-32`). That would **not** move the cold-run verdict: it would only narrow warm-path design.

## Implementation note (if pursued post–10 min)

Anchors: `cli.py` fingerprint block (`595-702`), sidecar persist (`719-828`), merge path `pdf_judge.py:710-928`. Tests: `packages/whisker/tests/test_incremental.py`. Precedent comparisons: deepeval per-(test_case, metric) cache (`134-deepeval-batch-eval.md`), persona 19 full design. **Do not** conflate with error tombstone fingerprint (synthesis #5, warm-only, smaller diff).
