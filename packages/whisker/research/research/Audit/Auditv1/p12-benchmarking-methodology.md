# P12 — Benchmarking & Leaderboard-Methodology Researcher

**Persona:** 12 of 30 (Cluster C: Extraction quality & eval science)  
**Date:** 2026-07-18  
**Scope:** External benchmarking method and standards only. No whisker production-code inspection.

---

## 1. Question restated

How should a **serious document-parsing benchmark** be built, run, and reported so that scores are **defensible, non-gameable, and comparable across tools**? This persona turns external precedent into audit criteria for: **per-axis (never single-number) scoring**, **separating content coverage from reading order**, **null-eligibility when a modality is absent**, **held-out vs development/replay splits**, **firewalls against tuning on the holdout**, and **honest cross-tool comparison**. Sources are OmniDocBench, DP-Bench, Docling-eval, and benchmark-integrity literature (contamination, leaderboard design).

---

## 2. Proposed audit criteria

Each criterion is scored on a **0–4 maturity ladder** unless marked as a **hard gate** (pass/fail). Evidence grades follow `00-FRAME.md` §6.3: **A** = multiple Tier-1 corroborating; **B** = single Tier-1 or converging Tier-2; **C** = Tier-3 only or contested; **D** = Tier-4/speculative.

### Criterion B1 — Per-axis modality decomposition (hard gate candidate)

| Field | Value |
|---|---|
| **Criterion** | Benchmark reports **separate scores per modality/axis** (minimum: text/content, tables, formulas if in scope, reading order, layout if applicable). A composite may exist but is **never the sole reported headline**. |
| **How to measure** | Inspect benchmark report/leaderboard: verify ≥4 distinct axis scores published alongside any aggregate. Composite formula must be documented (e.g. OmniDocBench: `Overall = ((1 − TextEdit) × 100 + TableTEDS + FormulaCDM) / 3`, explicitly excluding reading order from composite). Fail if README/leaderboard shows one rank column only. |
| **Audit method** | Comparative benchmarking (§5.3) + anti-gaming / Goodhart stress (§5.7) |
| **Scoring hook** | §6.1 (per-dimension scores always shown with composite); §6.2 gate if single-number-only reporting |
| **Gaming vector** | Strong text OCR masks broken tables/reading order behind one "Overall" figure; leaderboard cherry-picks favorable composite weighting. |
| **Anti-gaming guard** | Require published per-axis table in every public result; synthesis rule: composite cannot outweigh weakest axis in verdict narrative (weakest-axis visibility). |
| **Evidence grade** | **A** |
| **Sources** | OmniDocBench paper §4.3 (S1); OmniDocBench official repo leaderboard notes (S7); NeurIPS 2025 position paper multi-metric reporting desideratum (S4) |

### Criterion B2 — Content coverage vs reading order separation (strongest criterion)

| Field | Value |
|---|---|
| **Criterion** | **Content fidelity** (text extraction, table structure/content, formula recognition) and **reading order** are evaluated with **distinct metrics on distinct extracted signals**, never conflated into one edit-distance over full-page markdown. |
| **How to measure** | Verify eval harness exposes separate commands/config blocks for content vs order (e.g. DP-Bench: NID for layout/text serialization **excludes** tables/figures; separate reading-order modality in docling-eval; OmniDocBench: reading order uses text-component sequence only, excluding tables/images/ignored blocks). Cross-check that improving order without content change (or vice versa) moves only the corresponding axis. |
| **Audit method** | Metric construct-validity audit (§5.4) applied to **benchmark design** (not individual metric math; see P09 boundary) + comparative benchmarking (§5.3) |
| **Scoring hook** | §6.1 extraction-quality/eval dimension; §6.2 gate if order and content share one undifferentiated score used for gating |
| **Gaming vector** | Concatenating all text in arbitrary order yields high "content" edit distance while destroying semantics; or correct order with empty/wrong content passes a blended metric. |
| **Anti-gaming guard** | Mandatory paired reporting: both axes must appear; add canary cases where content is perfect but order permuted (order must fail) and order perfect but table cells swapped (table axis must fail). |
| **Evidence grade** | **A** |
| **Sources** | DP-Bench README metrics section (S2); OmniDocBench paper §4.3 Reading Order (S1); docling-eval DP-Bench reading_order vs markdown_text modalities (S8) |

**Why strongest:** Document parsing fails most often at **structure/order**, not character OCR. DP-Bench and OmniDocBench both treat this as a first-class design invariant; conflating axes is the dominant source of misleading leaderboard entries in the literature they cite (OmniDocBench Table 1 vs page-level edit distance benchmarks).

### Criterion B3 — Modality null-eligibility when absent

| Field | Value |
|---|---|
| **Criterion** | When a document/page **lacks a modality** (no table, no formula, no multi-column layout), that axis is **null-eligible**: excluded from aggregation for that sample, not scored as zero. Ignore flags for optional/inconsistent elements (headers, footers, captions) are documented. |
| **How to measure** | Inspect GT schema for `ignore` fields and evaluator logic (OmniDocBench JSON `"ignore": false` per element; ignore handling for headers/footers/captions documented in paper §4.2). Verify aggregate is computed over **eligible samples only** per axis. Run synthetic page with no tables: table axis should be N/A, not 0. |
| **Audit method** | Conformance checklist (§5.1) + metric construct-validity audit (§5.4) |
| **Scoring hook** | §6.1; §6.4 anti-gaming (prevents punishing tools that omit optional chrome) |
| **Gaming vector** | Scoring absent tables as 0 inflates averages for text-only pages; hiding failures by marking hard cases `ignore`. |
| **Anti-gaming guard** | Publish ignore-rule catalog; require per-axis **denominator counts** (n eligible) in results JSON; spot-audit ignored elements are semantically optional, not core content. |
| **Evidence grade** | **A** |
| **Sources** | OmniDocBench paper §4.2 Ignore Handling (S1); OmniDocBench GT schema docs (S7) |

### Criterion B4 — Stratified and attribute-sliced reporting

| Field | Value |
|---|---|
| **Criterion** | Beyond global axis means, benchmark reports **stratified slices**: document type, language, layout type (single/multi-column), table attributes, and other pre-registered cohorts. No "overall only" publication. |
| **How to measure** | Check for tables like OmniDocBench Table 2 (by doc type), Table 5 (reading order by column layout), Table 7 (table recognition by frame type). Require ≥3 independent stratification dimensions in public results. |
| **Audit method** | Comparative benchmarking (§5.3) + maturity model (§5.2) |
| **Scoring hook** | §6.1; §6.6 uncertainty (slices reveal where composite hides failure) |
| **Gaming vector** | Optimizing for average on easy academic-paper subset while failing newspapers/exams. |
| **Anti-gaming guard** | Pre-register stratification schema in benchmark spec; flag if reported slices omit worst-performing cohort present in corpus. |
| **Evidence grade** | **A** |
| **Sources** | OmniDocBench paper Tables 2, 5, 7 and §3 annotation diversity (S1) |

### Criterion B5 — Development vs held-out split discipline

| Field | Value |
|---|---|
| **Criterion** | Benchmark defines at least **development/replay** and **held-out** partitions (or equivalent: rolling fresh holdout with retired tests). Threshold tuning, matching-parameter search, and converter selection occur only on dev/replay; held-out is touched **once** per major release cycle with frozen config. |
| **How to measure** | Written split policy in benchmark README or eval harness; git-tagged eval configs; changelog showing holdout runs are versioned events. For static public sets (OmniDocBench, DP-Bench): require project-local **internal holdout** or **frozen golden replay set** distinct from sets used for iterative tuning. Absence of any split documentation = fail level 0. |
| **Audit method** | Reproducibility replay (§5.8) + anti-gaming / Goodhart stress (§5.7) |
| **Scoring hook** | §6.2 hard gate if thresholds tuned directly on public benchmark labels used for external claims |
| **Gaming vector** | Iterating on public OmniDocBench/DP-Bench until gates pass, then claiming generalization. |
| **Anti-gaming guard** | Maintain private or hashed holdout; document date of first holdout run; CapBencher-style accuracy ceiling optional for public sets (S6). |
| **Evidence grade** | **B** (static doc benchmarks rarely ship official dev/test splits; integrity literature supplies norm) |
| **Sources** | NeurIPS 2025 position paper secret/live test desiderata (S4); CapBencher arXiv (S6); EMNLP 2025 contamination survey §4 dynamic evaluation (S5) |

**Contradiction surfaced:** OmniDocBench and DP-Bench publish **full public test corpora** (necessary for reproducibility) while NeurIPS 2025 and CapBencher argue public static sets inevitably leak. **Resolution rule (§6.5):** prefer **higher-tier integrity guidance** for holdout discipline; treat public benchmarks as **replay/dev** unless project proves sealed holdout or contamination audit (B10). Do not discard public benchmarks; bifurcate their role.

### Criterion B6 — Holdout tuning firewall (hard gate candidate)

| Field | Value |
|---|---|
| **Criterion** | Documented firewall: no hyperparameter/threshold/matching-threshold changes after first holdout evaluation; no selective submission of best-of-N runs on holdout. Matching algorithms (e.g. Adjacency Search Match thresholds) frozen before holdout. |
| **How to measure** | Review eval config history: `match_method`, similarity thresholds, ignore rules must be committed before holdout tag. CI fails if holdout set paths appear in tuning scripts. For LLM judges: `do_sample=False` and token limits fixed pre-holdout (OmniDocBench appendix precedent). |
| **Audit method** | Anti-gaming / Goodhart stress (§5.7) + reproducibility replay (§5.8) |
| **Scoring hook** | §6.2 hard gate |
| **Gaming vector** | Running 20 configs on holdout, reporting best; adjusting ignore rules to erase failure modes. |
| **Anti-gaming guard** | Single pre-registered holdout run artifact; config hash in result JSON; optional CapBencher ceiling alarm (S6). |
| **Evidence grade** | **B** |
| **Sources** | CapBencher (S6); NeurIPS 2025 fair proctoring / unlimited submissions critique (S4); AAAI reproducibility checklist hyperparameter disclosure (S9) |

### Criterion B7 — Honest cross-tool comparison protocol

| Field | Value |
|---|---|
| **Criterion** | Cross-tool leaderboard entries use **identical**: benchmark version, eval harness commit/Docker image, input PDFs, output format contract (markdown/json), per-axis metrics, and hardware class for latency if reported. Vendor-specific post-processing disabled unless documented as part of that tool's default export. |
| **How to measure** | DP-Bench leaderboard columns require request date + frozen metric modes (`layout`, `table`, `all`, `speed`). OmniDocBench Docker eval image pins TeX/ImageMagick/Ghostscript versions. Compare two tools only via same `docling-eval evaluate --modality X` or OmniDocBench `pdf_validation.py` config YAML. |
| **Audit method** | Comparative benchmarking (§5.3) + conformance checklist (§5.1) |
| **Scoring hook** | §6.1; §6.5 (contested if harnesses differ) |
| **Gaming vector** | Evaluating competitor on older benchmark version; custom relaxed matching; cherry-picked page subset. |
| **Anti-gaming guard** | Pin benchmark version (OmniDocBench v1.6); publish eval Dockerfile digest; reject leaderboard rows missing harness version. |
| **Evidence grade** | **A** |
| **Sources** | DP-Bench leaderboard schema (S2); OmniDocBench Docker repro image (S7); docling-eval CLI modality contract (S8) |

### Criterion B8 — End-to-end vs component-level evaluation transparency

| Field | Value |
|---|---|
| **Criterion** | Benchmark distinguishes **end-to-end page parsing** from **component/module** evaluation (layout-only, table-only, OCR subset). Claims specify which mode produced each number. |
| **How to measure** | OmniDocBench: end2end markdown eval vs layout subset mAP vs table/formula subsets (Tables 6–9). DP-Bench: `--mode layout|table|all`. docling-eval: separate `create-eval` prediction providers (full Docling vs TableFormer-only). |
| **Audit method** | Comparative benchmarking (§5.3) |
| **Scoring hook** | §6.1; §6.4 (prevents pipeline component scores masquerading as e2e) |
| **Gaming vector** | Reporting TableFormer TEDS as "Docling score" without full pipeline. |
| **Anti-gaming guard** | Label every score with `eval_mode`; e2e claims require e2e config artifact. |
| **Evidence grade** | **A** |
| **Sources** | OmniDocBench paper §4, Tables 6–9 (S1); DP-Bench `--mode` (S2); docling-eval docs (S8) |

### Criterion B9 — Reproducibility artifacts and version pinning

| Field | Value |
|---|---|
| **Criterion** | Published results bundle: benchmark dataset version, eval code tag, config YAML, dependency lock/Docker digest, and per-sample score files (`.eval.json` per DP-Bench). NeurIPS-style statistical reporting where applicable (variance, cohort size). |
| **How to measure** | Re-run eval from published Docker + config reproduces axis means within documented tolerance. Check for per-image `.eval.json` (DP-Bench) and attribute-level dumps (OmniDocBench end2end). |
| **Audit method** | Reproducibility replay (§5.8) |
| **Scoring hook** | §6.3 evidence grade A only if replay succeeds |
| **Gaming vector** | "Contact us for eval script" or unpinned conda env. |
| **Anti-gaming guard** | Mandatory Docker or lockfile; CI job replays sample subset. |
| **Evidence grade** | **A** |
| **Sources** | OmniDocBench repro Docker + verify script (S7); DP-Bench per-image `.eval.json` (S2); NeurIPS paper checklist reproducibility items (S10) |

### Criterion B10 — Contamination and benchmark-integrity monitoring

| Field | Value |
|---|---|
| **Criterion** | For public benchmarks used in claims, project documents **contamination risk** and applies ≥1 integrity control: n-gram overlap audit, performance-based detection (ConStat-style), dynamic/fresh items, sealed holdout, or CapBencher ceiling. |
| **How to measure** | Written contamination assessment; if using static public set, record that external leaderboard scores are **replay/dev** not sealed generalization. Optional: run ConStat or document why inapplicable (small corpus). |
| **Audit method** | Anti-gaming / Goodhart stress (§5.7) + confidence / evidence grading (§5.12) |
| **Scoring hook** | §6.3 (lowers confidence on static-public-set claims); §6.6 flip condition if contamination plausible |
| **Gaming vector** | Training or prompt-tuning on benchmark PDFs/markdown; paraphrase leakage. |
| **Anti-gaming guard** | Treat public benchmark gains as necessary but not sufficient; require WG21-domain holdout separate from OmniDocBench/DP-Bench for production gate claims. |
| **Evidence grade** | **A** (detection methods); **B** (application to doc parsing specifically) |
| **Sources** | NeurIPS 2025 position paper (S4); ConStat NeurIPS 2024 (S3); EMNLP 2025 contamination survey (S5); CapBencher (S6) |

---

## 3. External benchmark / exemplar bar

### Tier-1/Tier-2 exemplar synthesis

| Practice | OmniDocBench | DP-Bench | Docling-eval | Benchmark-integrity literature |
|---|---|---|---|---|
| Per-axis metrics | Text, table, formula, reading order separate; composite excludes reading order | NID (text/layout), TEDS, TEDS-S separate modes | `layout`, `table_structure`, `reading_order`, `markdown_text` CLI modalities | Multi-metric reporting required for trustworthy leaderboards (S4) |
| Content vs order | Reading order = text components only; tables/images excluded | NID excludes tables/figures; order embedded in layout serialization | Separate `reading_order` vs `markdown_text` eval + ARD plots | Conflated metrics flagged as structural flaw (S1 limitation critique of prior work) |
| Null/ignore | Documented ignore for headers/footers/captions; GT `ignore` flags | Table mode only on pages with tables | Modality-specific eval skips inapplicable samples | Fair cross-tool comparison requires explicit eligibility rules |
| Stratification | 9 doc types, layout types, language, table attributes | Domain/subdomain counts in dataset card | Visualization per modality reports | Single-number hides cohort collapse (S1 Tables 2, 5) |
| Cross-tool fairness | Public Docker eval image; pinned toolchain | Leaderboard with request date; shared `evaluate.py` | IBM-maintained harness for DP-Bench + OmniDocBench | Identical harness/version or scores non-comparable (S7, S2) |
| Holdout integrity | Public full set (replay role) | Public full set (replay role) | Project-local GT creation path | Secret/live tests, CapBencher ceiling, ConStat (S3–S6) |

**Professional bar:** A defensible document-parsing QA benchmark program matches **OmniDocBench/DP-Bench axis separation** (B1, B2, B3) as floor, **docling-eval-style modality CLI + artifact pinning** (B7, B9) as operational target, and **integrity-literature holdout/contamination discipline** (B5, B6, B10) for any score used in release gates.

**Where exemplars diverge (do not cargo-cult):** OmniDocBench's published `Overall` formula omits reading order despite reporting it separately (acceptable only if order is always co-reported; gate decisions must not ignore order). DP-Bench leaderboard includes vendor cloud APIs (whisker targets self-hosted sovereignty; latency columns are informational, not quality). Docling-eval supports component providers (TableFormer-only) that must not stand in for full-pipeline QA without B8 labeling.

---

## 4. Recommended weight & gate recommendation

| Recommendation | Rationale |
|---|---|
| **Dimension weight: 10%** of composite (within extraction-quality/eval cluster shared with P09 metric validity, P10 LLM-judge, P11 corpus, P13 comprehension) | Benchmark **integrity** enables trust in all other metric claims; weight below P09 construct validity and P16 calibration because a perfect benchmark misapplied still fails if metrics/thresholds are wrong. |
| **Hard gates (conjunctive): B2, B6** | **B2:** If content and reading order are conflated in the primary gate metric, extraction-QA cannot detect the dominant failure class (order/table structure). **B6:** Tuning on holdout voids external benchmark claims (CapBencher/NeurIPS integrity tier). |
| **Soft gates (cap dimension at level 2): B1, B3, B7** if any fail | Single-number reporting, missing null-eligibility, or incomparable cross-tool runs undermine leaderboard defensibility but may not block internal dev replay. |
| **Strongest criterion for synthesis priority** | **B2 — Content coverage vs reading order separation** (Tier-1 corroboration across OmniDocBench, DP-Bench, docling-eval; directly addresses the mandate's core failure mode). |
| **Evidence propagation** | Dimension inherits weakest grade among B1–B4, B7, B9 load-bearing criteria (typically **A** when OmniDocBench/DP-Bench patterns followed). B5/B6/B10 often **B** until project documents holdout/contamination protocol. |
| **Contested criteria discount** | B5 public-vs-secret holdout: apply §6.5; mark **contested**, reduce B5 weight 30%, require explicit "replay set vs holdout set" labeling in all published scores. |

---

## 5. Sources

### Tier 1 — Authoritative / primary

| ID | Source | URL | Date/version |
|---|---|---|---|
| S1 | OmniDocBench: Benchmarking Diverse PDF Document Parsing with Comprehensive Annotations (CVPR 2025) | https://arxiv.org/html/2412.07626v2 | arXiv v2, Dec 2024; CVPR 2025 |
| S2 | DP-Bench: Document Parsing Benchmark (official dataset README) | https://huggingface.co/datasets/upstage/dp-bench/blob/main/README.md | Updated 2026-02 (leaderboard sync) |
| S3 | ConStat: Performance-Based Contamination Detection in LLMs (NeurIPS 2024) | https://proceedings.neurips.cc/paper_files/paper/2024/file/a7f89793b9e6f8c6568dbbb6ff727b9b-Paper-Conference.pdf | NeurIPS 2024 |
| S4 | Position: Benchmarking is Broken — Don't Let AI be its Own Judge (NeurIPS 2025 Position Paper) | https://proceedings.neurips.cc/paper_files/paper/2025/file/693e00827fd44bdfca210801fe1e6439-Paper-Position_Paper_Track.pdf | NeurIPS 2025 |
| S5 | Benchmarking LLMs Under Data Contamination: Survey from Static to Dynamic Evaluation (EMNLP 2025) | https://aclanthology.org/2025.emnlp-main.511.pdf | EMNLP 2025 |
| S6 | CapBencher: Publish LLM Benchmark Without Giving True Answers Away | https://arxiv.org/html/2505.18102v6 | arXiv v6, May 2025 |

### Tier 2 — Strong secondary

| ID | Source | URL | Date/version |
|---|---|---|---|
| S7 | OmniDocBench official evaluation repo | https://github.com/opendatalab/OmniDocBench | v1.6 eval + Docker repro, 2026 |
| S8 | Docling-eval (IBM) — DP-Bench & OmniDocBench harness docs | https://github.com/docling-project/docling-eval | README + `docs/DP-Bench_benchmarks.md`, 2026 |
| S9 | Docling technical report | https://arxiv.org/html/2408.09869v1 | Aug 2024 |
| S10 | NeurIPS Paper Checklist (reproducibility & statistical reporting) | https://neurips.cc/public/guides/PaperChecklist | 2024–2025 cycle |
| S11 | AAAI Reproducibility Checklist (via NeurIPS 2024 formatting guide) | https://arxiv.org/html/2404.10198v3 | 2024 |

### Tier 3 — Contextual (corroboration only)

| ID | Source | URL |
|---|---|---|
| S12 | CapBencher GitHub toolkit | https://github.com/ishida-lab/capbencher |

**Source count:** 6 Tier-1 + 5 Tier-2 = **11 distinct Tier 1–2 sources** (floor ≥3 satisfied).

**Contradictions surfaced (not hidden):**
- **Public reproducibility vs contamination resistance:** OmniDocBench/DP-Bench (S1, S2) publish full corpora; S4–S6 argue static public tests leak. Audit resolves by **role separation** (public = replay/dev; gates require private holdout or integrity controls).
- **Composite vs per-axis:** OmniDocBench publishes `Overall` (S1, S7) while frame §6.1 forbids single-number-only reporting. Audit resolves: composite allowed **only alongside** all axis scores; reading order must remain visible even when excluded from composite formula.

---

## 6. Overlap statement

This persona researched **external document-parsing benchmarking and leaderboard methodology only**. It did **not** open whisker production code, cite whisker `file:line`, score whisker, clone/fork/copy code, or duplicate:

- **`redteam/`** — per-converter defect reports (this is benchmark *method*, not converter red-team).
- **`persona/` / `llm-stack/`** — prior whisker code-level metric/gate audits.
- **`buildvsbuy/`** — library-choice decisions for metric implementations.
- **P09 (`p09-extraction-quality-metrics.md`)** — construct validity of individual metrics (TEDS, NID, CDM math); P12 covers **benchmark design, reporting, splits, and comparison integrity**, not metric formula correctness.
- **P16 (`p16-threshold-calibration.md`)** — ROC/operating-point calibration protocol; P12 references holdout firewalls but does not design threshold fitting.
- **P19 (`p19-anti-gaming-goodhart.md`)** — general Goodhart defenses; P12 applies anti-gaming specifically to benchmark/leaderboard structure.

Boundary held: **benchmarking-integrity criteria and external bar**, handed to synthesis as rubric inputs for the extraction-quality/eval-scoring dimension.
