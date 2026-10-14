# Repo scan: marker (datalab PDF→markdown)

**Source:** `packages/whisker/research/repos/marker-v1.10.2/` (VikParuchuri/marker, shallow clone, read-only)  
**Question:** Does marker verify that its markdown output is LLM-readable (comprehension, fact recovery, downstream consumability)?

## Does it verify LLM-readability?

**partial**

Marker gates quality with **structural fidelity** (fuzzy GT-block alignment, Kendall-τ reading order, table TEDS) and optional **LLM-as-judge** scoring (Gemini compares page image to markdown). It does **not** run deterministic fact assertions, QA benchmarks, blind read-backs, or downstream-LLM consumability tests. CI enforces only the heuristic mean and table TEDS floors; the LLM judge and `--use_llm` conversion path are not comprehension-verified or span-grounded.

---

## Findings

1. **[HIGH] CI gates corpus-mean heuristic + table TEDS only; no comprehension lane.**  
   `benchmarks/verify_scores.py:9-13` averages per-sample `heuristic.score` and raises if mean `< 90`.  
   `benchmarks/verify_scores.py:20-22` averages table `marker_score` (TEDS) and raises if mean `< 0.7`.  
   `.github/workflows/benchmarks.yml:28-35` runs `overall.py --max_rows 5` then `verify_scores.py`; table job is separate.  
   Neither path checks fact recovery, QA, or LLM consumability.

2. **[HIGH] Primary scorer is GT fuzzy alignment + reading-order τ, not comprehension.**  
   `benchmarks/overall/scorers/heuristic.py:25-40` fuzzy-aligns each GT block into predicted markdown (`partial_ratio_alignment`, cutoff 70 at `:77-82`), length-weights scores (`:35-39`), blends **80% content + 20% Kendall-τ order** (`:39-40`).  
   `benchmarks/overall/scorers/clean.py:12-36` pandoc round-trip normalization before compare.  
   This measures **resemblance to hand-labeled GT blocks**, same class as whisker Lane 2 (NID/TEDS/MHS), not “can an LLM recover facts.”

3. **[MED] Optional LLM-as-judge scorer exists but is subjective, ungrounded, and not CI-gated.**  
   `benchmarks/overall/scorers/llm.py:15-51` prompts Gemini to rate markdown vs page image on 0–5 axes (overall, text, formatting, tables, equations, headers, lists, images).  
   `benchmarks/overall/scorers/llm.py:108-134` returns `response["overall"]` as score; no span grounding, no fact checklist, no abstention channel.  
   `benchmarks/overall/registry.py:11-14` registers `heuristic` and `llm`; default CLI score is `heuristic` (`overall.py:93`).  
   CI never passes `--scores llm` (`.github/workflows/benchmarks.yml:30`).  
   README documents LLM judge results (`README.md:470-495`) but treats them as **reporting**, not release gates.

4. **[MED] `--use_llm` conversion mode is benchmarked structurally only; LLM corrections are not separately grounded.**  
   `benchmarks/overall/methods/marker.py:16-23` passes `use_llm` into `PdfConverter` with Vertex Gemini service.  
   `benchmarks/overall/overall.py:96` exposes `--use_llm` flag; same scorers evaluate output.  
   Table bench reports higher TEDS with LLM (`README.md:511-515`, `benchmarks/table/table.py:34`) but scoring is still **HTML tree edit distance** (`benchmarks/table/scoring.py:92-108`), not fact QA on LLM-rewritten cells.  
   LLM processor unit tests mock the LLM (`tests/processors/test_llm_processors.py:46-57`, `:88-89`) and assert plumbing, not real output fidelity.

5. **[MED] Unit tests use substring presence anchors, not a fact-assertion corpus.**  
   `tests/converters/test_pdf_converter.py:14-28` asserts known phrases in converted markdown (title, cross-page joins, cross-column joins).  
   `tests/renderers/test_markdown_renderer.py:13-14` similar title check.  
   These are **smoke/regression anchors** on one fixture PDF; not typed present/absent/order/table/math facts, not in CI benchmark gate, not human-verified JSONL like olmOCR-bench or whisker Lane 3.

6. **[LOW] No olmOCR-bench / fact-assertion harness in repo.**  
   `benchmarks/overall/methods/olmocr.py` runs olmOCR as a **competitor method** scored by marker’s heuristic/LLM scorers (`overall.py:151-157`), not allenai’s 7,010 deterministic unit tests.  
   No imports of `olmocr/bench`, no `present`/`absent`/`order`/`table`/`math` assertion types anywhere in marker benchmarks.

7. **[LOW] No downstream consumability measurement.**  
   Unlike olmOCR’s continued-pretraining MMLU/DROP lift (see `05-web.md` Q3), marker has no eval that feeds converted markdown into a fixed downstream LLM task.  
   Throughput bench (`benchmarks/throughput/main.py`, `README.md:497-505`) is performance-only.

8. **[LOW] Failed benchmark samples dropped from averages ( hides collateral damage).**  
   `benchmarks/overall/overall.py:72-77` deletes failed indices from `markdown_by_method` and continues; `verify_scores.py` averages surviving scores only.  
   Whisker guard’s missing-pid hard fail is stricter (redteam already noted).

---

## Portable to whisker

Ranked by leverage for whisker Lane 2–3 and guard (not wholesale adoption of marker’s mean-only CI):

1. **Pandoc round-trip `normalize_markdown` before bench/guard diff** — reduces formatting-only false regressions.  
   Source: `benchmarks/overall/scorers/clean.py:38-76`.  
   Action: run equivalent normalization on candidate+reference before `run_bench`; symmetric rounding at guard diff.

2. **Length-weighted block fuzzy alignment + explicit order component (0.8/0.2)** — localizes regressions to GT blocks and treats reading order as scored, not advisory.  
   Source: `benchmarks/overall/scorers/heuristic.py:35-40`, `:49-71`.  
   Action: persist per-block weighted scores in guard baseline; optionally add order to `GUARD_REGRESSION_AXES` with slack.

3. **Stratified reporting by document type and block type** — prevents aggregate means hiding table/form collapse.  
   Source: `benchmarks/overall/overall.py:37-38`, `:67-71`; `benchmarks/overall/display/table.py:17-47`.  
   Action: extend whisker baseline rows with optional `classification` / block-type rollups; fail on stratum regression.

4. **Separate table TEDS CI job** — independent floor for tabular fidelity.  
   Source: `benchmarks/table/table.py`, `verify_scores.py:16-22`, `.github/workflows/benchmarks.yml:32-35`.  
   Action: optional split guard job when corpus is tables-heavy (whisker already has `teds` axis; mirror as explicit gate).

5. **Substring anchor tests as seeds for Lane 3 fact JSONL** — marker’s cross-page/column asserts (`test_pdf_converter.py:18-28`) are proto-`present` facts; promote to verified `facts.jsonl` entries instead of bare pytest strings.

6. **Do not adopt:** corpus-mean-only CI (`verify_scores.py:9-13`), silent sample drop (`overall.py:72-77`), ungrounded LLM judge as gate (`llm.py:15-134` without span grounding — aligns with #277 blocking conditions).

---

## Cross-check vs redteam report

**File:** `packages/whisker/research/redteam/marker.md`

| Redteam claim | Verdict | Evidence |
|---------------|---------|----------|
| CI gates corpus means only (heuristic ≥ 90, TEDS ≥ 0.7), no per-item baseline | **Confirm** | `verify_scores.py:9-13`, `:20-22`; `benchmarks.yml:28-35` |
| Heuristic blends 80% block fuzzy + 20% Kendall-τ order | **Confirm** | `heuristic.py:39-40`, `:49-71` |
| Pandoc normalization before scoring | **Confirm** | `clean.py:38-76` |
| Stratified doc-type and block-type aggregates | **Confirm** | `overall.py:67-71`; `display/table.py:17-47` |
| Substring anchor assertions in unit tests, none in guard | **Confirm** | `test_pdf_converter.py:14-28` |
| LLM sub-scores (tables, equations, headers, …) exist | **Confirm** | `llm.py:89-91`, `:38-44` |
| LLM scorer not applicable to whisker no-LLM gate | **Confirm** (for Lane 3); note LLM judge is **optional reporting**, not comprehension | `registry.py:11-14`; CI uses `heuristic` only |
| marker never calibrates thresholds | **Confirm** | `verify_scores.py:12-13`, `:21-22` hard-coded |
| Failed samples dropped from averages | **Confirm** | `overall.py:72-77` |
| `verify_table_scores` denominator uses `len(data)` not `len(data["marker"])` | **Confirm** | `verify_scores.py:20` |
| **Implicit redteam scope:** guard/calibrate comparison, not LLM-readability | **Extend** | This scan adds: **no fact assertions, no olmOCR-bench, no downstream QA** — marker is structural + optional ungrounded LLM judge; redteam’s “no anchor/fact layer beneath fuzzy metrics” (`marker.md` §4) **confirms** for comprehension specifically |

**Net:** Redteam findings on regression/calibration are **confirmed**. For LLM-readability specifically, marker is **partial at best** (LLM judge exists but does not test comprehension or gate `--use_llm` output with grounded facts).
