# Repo scan: Dolphin (ByteDance)

**Does it verify LLM-readability?** **no**

Dolphin ships **inference demos only** (`demo_page.py`, `demo_element.py`, `demo_layout.py`) plus optional markdown post-processing. Published OmniDocBench scores (Text Edit, Formula CDM, Table TEDS/TEDS-S, Read Order Edit) appear in `README.md` but **no benchmark runner, scorer, or gold corpus** exists in-repo. There are no fact assertions, comprehension tests, LLM read-back, QA tracks, or LLM-as-judge eval paths.

---

## Findings

1. **[HIGH] No in-repo evaluation code — external structural benchmark only** — Performance table cites OmniDocBench v1.5 axes (Overall, Text Edit↓, Formula CDM↑, Table TEDS↑, TEDS-S↑, Read Order Edit↓) with point estimates for Dolphin variants. Evidence: `README.md:58-106`. No Python module imports TEDS, CDM, or edit-distance scorers; numbers are **published externally**, not reproducible from this clone.

2. **[HIGH] Demo scripts write outputs; never verify them** — `save_outputs` persists JSON + markdown per image (`utils/utils.py:234-247`); `demo_page.py` processes files in a loop with `--post_process` toggle (`demo_page.py:339,384`). No diff, no baseline JSON, no pass/fail gate. Impact: zero downstream consumability proof.

3. **[MED] Pre-score markdown normalization chain (metric-stability, not comprehension)** — when `post_process=True`, `MarkdownConverter.convert` applies `truncate_repeated_tail(threshold=20, keep=1)` on every text block (`markdown_utils.py:320-321,52-79`), LaTeX env canonicalization on formulas (`markdown_utils.py:291-296`), and table HTML attribute stripping (`markdown_utils.py:14-16,271-280`). Impact: portable **normalization-before-diff** for whisker bench; addresses VLM repetition tails crushing edit metrics.

4. **[MED] Modality-aware parsing pipeline (element-type routing)** — layout pass splits `tab`, `equ`, `code`, text elements with distinct handlers and batch prompts (`demo_page.py:211-257`, `markdown_utils.py:328-345`). Impact: architectural parallel to per-axis reporting; does not score elements after conversion.

5. **[MED] Document-class heuristic routing** — `check_bbox_overlap(..., iou_threshold=0.1, overlap_box_ratio=0.25)` detects photographed/distorted pages and falls back to `distorted_page` holistic parse (`demo_page.py:206-209`, `utils/utils.py:489-533`). Impact: portable **corpus stratification** field; not LLM-readability.

6. **[MED] Silent error continuation anti-pattern** — per-file exceptions logged and skipped (`demo_page.py:389-391`). Impact: regressions can vanish from a batch run without failing the job.

7. **[LOW] Deterministic decode defaults** — layout demo uses `do_sample=False`, `temperature=None` (`demo_layout.py:106-108` per redteam cite). Eval reproducibility given fixed weights; irrelevant to comprehension.

8. **[CONFIRMED ABSENT] Tests, CI, comprehension, fact assertions, LLM judge, QA benchmark** — no `tests/` directory, no `.github/workflows`, no `pytest`, no `facts`/`comprehension`/`QA` modules in tracked files (~32 files total). Fox-Page Benchmark announced as external download only (`README.md:50`).

---

## Findings vs Q3 baseline (downstream readability)

Per `research/llm-readability/05-web.md` Q3: benchmarks like ParseBench, RealDocBench, and olmOCR-bench measure **downstream consumability** via deterministic rules or fixed extraction LLM + field QA. Dolphin/OmniDocBench (as cited in README) remains **structural fidelity** (edit distance, TEDS, CDM): resemblance to gold layout, not "read → understood → correct." Dolphin adds no RealDocBench-style field QA and no olmOCR-style fact unit tests in this repo.

---

## Portable to whisker (ranked)

1. **`truncate_repeated_tail(s, threshold=20, keep=1)` before bench scoring** — deterministic tail-repetition collapse for VLM degeneracy; wire into `run_bench` normalization or pin as `normalizer_version`. Source: `utils/markdown_utils.py:52-79,320-321`. Highest ROI; directly reduces false NID regressions.

2. **LaTeX env canonicalization before formula/table compare** — `gathered_to_aligned`, `aligned_to_array`, `remove_numeric_quad_ending`, `replace_repeated_cdots`. Source: `utils/markdown_utils.py:23-49,291-296`. Partial overlap with whisker `pylatexenc` math surface; env transforms are additive.

3. **Table HTML attribute normalization** — strip `<table>` attrs to canonical `<table>` before TEDS HTML extraction. Source: `utils/markdown_utils.py:14-16`.

4. **Per-modality axis reporting with null eligibility** — gate Text / Formula / Table / Read-order independently; skip axis when GT lacks modality (Dolphin/OmniDocBench philosophy in `README.md:67-73`). whisker guard partially implements; missing formula CDM and TEDS-S axes.

5. **`document_class` + distorted-page routing metadata in baseline** — record IoU-routing outcome per paper for stratified regression. Source: `demo_page.py:206-209`, `utils/utils.py:489-533`.

6. **Pin `post_process` / normalizer version in baseline JSON** — Dolphin's eval quality depends on normalization chain being identical across runs (`demo_page.py:339`). whisker guard should record normalizer generation (redteam aligns).

7. **Low priority:** element-level regression (Dolphin parses per element; whisker guard is per-paper only).

**Not portable as LLM-readability proof:** Dolphin provides no comprehension corpus, no fact schema, no LLM read-back. OmniDocBench scoring must be run externally; whisker Lane 3 remains the only in-monorepo comprehension gate.

---

## Cross-check vs redteam report (`packages/whisker/research/redteam/Dolphin.md`)

| Redteam claim | Verdict | Evidence |
|---------------|---------|----------|
| No in-repo tests, CI, committed metric snapshots | **CONFIRMED** | no `tests/`, no `.github/`; only demo + utils |
| Pre-score normalization chain (`post_process`) | **CONFIRMED** | `markdown_utils.py:320-321,291-296,14-16`; CLI `--post_process` at `demo_page.py:339` |
| OmniDocBench six-axis published in README, not implemented in-repo | **CONFIRMED** | `README.md:60-106`; no scorer module |
| `truncate_repeated_tail(threshold=20, keep=1)` | **CONFIRMED** | `markdown_utils.py:52-79,320-321` |
| `check_bbox_overlap` distorted-page routing | **CONFIRMED** | `utils/utils.py:489-533`, `demo_page.py:206-209` |
| Demo swallows per-file errors | **CONFIRMED** | `demo_page.py:389-391` |
| Element-type parsing (tab/equ/code/text) | **CONFIRMED** | `demo_page.py:211-257`, `markdown_utils.py:328-345` |
| No threshold calibration in-repo | **CONFIRMED** | no calibrate module |
| Formula CDM / TEDS-S / read-order axes absent from whisker | **CONFIRMED (whisker gap, not Dolphin code)** | Dolphin README lists axes; no whisker implementation required in Dolphin repo |

**Scope correction vs redteam:** redteam compares Dolphin to whisker guard/calibrate. This scan adds: Dolphin verifies **nothing automatically** in-repo; README numbers are external OmniDocBench runs on **structural metrics**, not LLM-readability. Redteam's top portable pick (`truncate_repeated_tail`) confirmed as #1 here.

**No contradictions found** on cited file:line references.

---

*Sources: shallow clone at `packages/whisker/research/repos/Dolphin/` (ByteDance/Dolphin, read-only, ~32 tracked files, July 2026).*
