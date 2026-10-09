# P28 — olmOCR / Marker / MinerU Comprehension-Eval Case Study

**Persona:** 28 of 30 (Cluster H — Repository case studies, grouped by lesson)  
**Date:** 2026-07-18  
**Scope:** External exemplar practices only. No whisker code inspection. No whisker verdict.

---

## 1. Question restated

What transferable audit criteria can be extracted from three document-conversion exemplars — **Allen AI olmOCR**, **Datalab Marker**, and **OpenDataLab MinerU** — when grouped by three *distinct* engineering lessons rather than per-repo converter red-team?

| Lesson track | Primary exemplar | What it teaches |
|---|---|---|
| **(a) Comprehension / QA-oriented evaluation** | olmOCR (+ MinerU benchmark posture) | How to evaluate extraction beyond surface similarity: fact-level unit tests and downstream task impact |
| **(b) Zero-authoring baseline sanity checks** | olmOCR | Deterministic, author-free gates for catastrophic OCR failure (empty output, repetition loops, charset drift) |
| **(c) Model-serving engineering maturity** | MinerU, Marker, olmOCR | Production deployment of self-hosted VLM inference: server separation, batch throughput, documented concurrency |

This persona hands the synthesis **audit criteria + an external bar**, not a whisker judgment.

---

## 2. Proposed audit criteria

Each criterion below maps to an audit method (§5 of `00-FRAME.md`), a scoring-design hook (§6), a gaming vector, an anti-gaming guard, and an evidence grade.

---

### Track A — Comprehension / QA-oriented evaluation (olmOCR-led; MinerU as contrast)

#### Criterion A1: Downstream task battery proves extraction quality, not just string match

| Field | Value |
|---|---|
| **Criterion** | A QA/extraction package that claims "comprehension matters" must report at least one **downstream task battery** (e.g., continued pretraining or QA benchmarks) where the *only* variable is extraction quality on a fixed document corpus — not a single fuzzy metric. |
| **How to measure** | Check for: fixed corpus, controlled linearization ablation, ≥3 downstream tasks reported individually (not one average only). olmOCR bar: 50B-token continued pretrain on identical peS2o PDFs, Grobid baseline vs olmOCR re-extraction, reporting MMLU, ARC-C, DROP, HellaSwag, NaturalQuestions, WinoGrande separately (+1.3 pp average, largest gains on DROP/NQ). |
| **Audit method** | Comparative benchmarking against exemplars (§5.3); metric construct-validity audit (§5.4) |
| **Scoring hook** | §6.1 extraction-quality/eval dimension; §6.5 disagreement handling when downstream and surface metrics diverge |
| **Gaming vector** | Pick downstream tasks that correlate with token count, not fidelity; report only aggregate average. |
| **Anti-gaming guard** | Require per-task breakdown; require corpus lock (same source PDFs, different extractors only); flag if downstream eval is absent while surface metrics are claimed as "comprehension." |
| **Evidence grade** | **A** — peer-reviewed paper with reproducible protocol (olmOCR §4.2, Table 5) |

**Exemplar bar:** olmOCR is the rare converter ecosystem that closes the loop from extraction → language-model utility. Most peers stop at edit distance or LLM-judge scores.

**Wrong for whisker if copied blindly:** olmOCR's downstream eval targets *training-data quality* for LMs, not WG21 gate calibration. Whisker should adapt the *method* (fixed-corpus ablation + downstream fact recovery) to its own labeled holdout, not run 50B-token pretraining.

---

#### Criterion A2: Deterministic binary unit tests supersede fuzzy gold-text matching for semantic errors

| Field | Value |
|---|---|
| **Criterion** | Extraction eval must include **machine-verifiable pass/fail tests** for properties where edit distance is construct-invalid: math subscript/superscript swaps, table cell neighbor relations, reading-order constraints, header/footer absence. |
| **How to measure** | Count of distinct test types; % pages covered; explicit rejection of LLM-as-judge as *primary* scorer. olmOCR-Bench: 7,010 tests across 1,402 PDFs, seven category axes (ArXiv math, old scans, tables, reading order, headers/footers, dense small print, historical scans). Test types: text presence/absence, natural reading order (relative span ordering), table cell adjacency, math formula layout via KaTeX headless render + bounding-box layout match. |
| **Audit method** | Metric construct-validity audit (§5.4); benchmarking methodology (§5.12 analog via P12) |
| **Scoring hook** | §6.1 per-axis mandatory reporting; §6.2 candidate hard gate if comprehension claims rest solely on edit distance |
| **Gaming vector** | Write trivial presence tests ("the" appears somewhere); optimize pass rate on easy categories while math/table columns fail. |
| **Anti-gaming guard** | Require category-stratified reporting with confidence intervals (olmOCR bootstraps 10k samples, reports ± CI per column); include adversarial categories (old scans, multi-column); minimum tests-per-page floor. |
| **Evidence grade** | **A** — benchmark-defining paper + open test suite (`allenai/olmOCR-bench`, GitHub `olmocr/bench/`) |

**Exemplar bar:** olmOCR-Bench explicitly rejects edit distance, ROUGE, and LLM-as-judge for primary scoring, citing self-preference bias (Panickssery et al., 2024) and construct invalidity for math (x^i vs x_i is one character in edit distance).

**Contrast — MinerU:** MinerU's primary public eval (OmniDocBench) remains **reference-matching**: normalized edit distance (text, reading order), TEDS (tables), CDM (formulas), with an Overall composite. MinerU2.5-Pro (Apr 2026) adds eval-*methodology* maturity (v1.6 protocol, Base/Hard/Full tiers, Multi-Granularity Adaptive Matching to fix v1.5 matching bias) but does not adopt olmOCR-style fact unit tests. **Lesson separation:** olmOCR owns comprehension-proxy via unit tests + downstream LM eval; MinerU owns per-axis benchmark hygiene and protocol versioning.

**Wrong for whisker:** Collapsing olmOCR-Bench categories into one number (olmOCR itself averages per-source percentages — the synthesis should still require axis visibility).

---

#### Criterion A3: Unit tests as training/eval unified verifiable rewards (olmOCR 2 extension)

| Field | Value |
|---|---|
| **Criterion** | Mature extraction projects should document whether eval tests are **stable enough to serve double duty** as RLVR/training rewards, with a synthetic-data pipeline to scale test generation beyond manual authoring. |
| **How to measure** | Presence of: synthetic document generator with known ground-truth HTML; programmatic test extraction from synthetic pages; reported benchmark lift from reward-aligned training. olmOCR 2: RLVR with binary unit-test rewards, +14.2 pp on olmOCR-Bench over six months; synthetic pipeline renders HTML from real PDF layouts then generates tests programmatically. |
| **Audit method** | Comparative benchmarking (§5.3); reproducibility replay (§5.8) for eval stability |
| **Scoring hook** | §6.1 eval-science maturity level descriptor |
| **Gaming vector** | Train on synthetic tests that don't transfer to real PDFs; overfit unit-test patterns. |
| **Anti-gaming guard** | Hold out manually verified real-PDF test set (olmOCR-Bench manual verification for math TeX/KaTeX compatibility); report real-vs-synthetic eval split. |
| **Evidence grade** | **A** — olmOCR 2 technical report (arXiv:2510.19817, Oct 2025) |

**Wrong for whisker:** RLVR training is out of scope; the transferable practice is **verifiable, binary checks** that can gate both eval and (optionally) advisory LLM self-correction — aligned with whisker's deterministic core, not its training pipeline.

---

### Track B — Zero-authoring baseline sanity checks (olmOCR-owned lesson)

#### Criterion B1: Every page gets an automatic baseline test without human authorship

| Field | Value |
|---|---|
| **Criterion** | A extraction QA system must run **zero-authoring baseline checks on 100% of pages**, even when no golden labels exist — catching catastrophic failures before any labeled eval. |
| **How to measure** | Confirm auto-generation of baseline tests for all pages lacking specific content tests. olmOCR: `BaselineTest` auto-created per page in benchmark orchestration; checks run before category-specific tests. |
| **Audit method** | Conformance checklist (§5.1) |
| **Scoring hook** | §6.2 candidate **hard gate**: empty/garbled output fails regardless of weighted score |
| **Gaming vector** | Skip baseline on "hard" pages; only baseline easy pages. |
| **Anti-gaming guard** | Code/doc proof that baseline is unconditional; report baseline pass rate separately from content-test pass rate. |
| **Evidence grade** | **B** — official paper §3 + open-source test framework (`olmocr/bench/tests.py`, `RepeatDetector`) |

---

#### Criterion B2: Baseline check catalog — non-empty, anti-repetition, charset sanity

| Field | Value |
|---|---|
| **Criterion** | Baseline checks must be **enumerated, deterministic, and documented** with explicit thresholds. Minimum catalog: (1) non-empty alphanumeric output, (2) no trailing repeated n-gram over threshold length, (3) charset sanity rules for known failure modes. |
| **How to measure** | olmOCR BaselineTest rules: output contains alphanumeric characters; no repeating n-gram string at end **longer than 30 characters**; output must not contain Chinese, Japanese, or Emoji Unicode (with manually flagged exemptions for legitimate pages). `RepeatDetector` analyzes abnormal frequency patterns. String normalization documented: NFC Unicode, whitespace collapse, Markdown bold/italics strip, quote/hyphen ASCII normalization. |
| **Audit method** | Conformance checklist (§5.1); anti-gaming / Goodhart stress (§5.7) |
| **Scoring hook** | §6.2 hard gate; §6.4 anti-gaming (cosmetic non-empty output) |
| **Gaming vector** | Emit one alphanumeric token; pass non-empty check while content is garbage. |
| **Anti-gaming guard** | Combine non-empty with repetition detection *and* minimum content-length or entropy floor; olmOCR pairs baseline with category tests on labeled pages. For whisker: align with existing anchor/guard design — baseline is necessary, not sufficient. |
| **Evidence grade** | **A** — primary paper baseline definition with footnote on exemption protocol |

**Serving-side coupling (olmOCR):** Dynamic temperature scaling (0.1 → 0.8 stepped) triggered on EOS/repetition-loop failure during inference — baseline checks inform *runtime* mitigation, not just post-hoc scoring (olmOCR 2 Table 3). This connects Track B to Track C.

**Marker / MinerU on this track:** Neither Marker nor MinerU documents an equivalent **zero-authoring universal baseline gate** in their public eval suites. Marker relies on heuristic + LLM-judge benchmark scoring; MinerU relies on OmniDocBench reference matching. **Track B is olmOCR-distinct.**

**Wrong for whisker:** Copying olmOCR's CJK/emoji exclusion literally — WG21 papers may legitimately contain Unicode math symbols; whisker needs domain-calibrated charset rules, not olmOCR's English-centric defaults.

---

### Track C — Model-serving engineering maturity (three distinct postures)

#### Criterion C1: Inference-server separation — load model once, many clients (MinerU exemplar; olmOCR aligned)

| Field | Value |
|---|---|
| **Criterion** | Self-hosted VLM extraction must document a **server/client split**: inference server (vLLM or equivalent) separate from stateless API/CLI workers, with explicit connection mode. |
| **How to measure** | MinerU: `mineru-openai-server --engine vllm` + client `-b vlm-http-client -u http://host:30000`; Docker compose profiles (`openai-server`, `api`, `router`). olmOCR: `--server http://remote:8000/v1` skips local vLLM spawn; local mode passes through `--gpu-memory-utilization`, `--tensor-parallel-size`, `--data-parallel-size`. Document whether multiple concurrent in-process clients are safe (MinerU: explicitly **not** — use HTTP client to shared server). |
| **Audit method** | Maturity-model scoring (§5.2); observability audit (§5.11) |
| **Scoring hook** | §6.1 release-readiness / model-sovereignty sub-dimension |
| **Gaming vector** | Claim "supports vLLM" but only document embedded single-process mode. |
| **Anti-gaming guard** | Require architecture diagram or compose file showing server/client; document max safe concurrency and known unsafe patterns. |
| **Evidence grade** | **B** — MinerU official Docker + advanced CLI docs; olmOCR README v0.1.75+ (June 2025) |

**MinerU-distinct:** `mineru-router` for multi-GPU worker orchestration; vLLM/lmdeploy parameter pass-through on all entrypoints; `MINERU_API_MAX_CONCURRENT_REQUESTS` API-layer throttle.

**olmOCR-distinct:** Switched default inference from SGLang to vLLM (June 2025); documents FP8 model variant (`olmOCR-2-7B-1025-FP8`); reports 12% retry rate and cost-per-million-pages table (L40S/H100).

---

#### Criterion C2: Throughput benchmarks with hardware context and serial vs batch modes (Marker exemplar)

| Field | Value |
|---|---|
| **Criterion** | Serving maturity requires **published throughput numbers** with: hardware spec, serial single-page latency, and batch/parallel mode throughput — not peak-only marketing. |
| **How to measure** | Marker README: serial H100 single-page benchmarks (heuristic ~95.7%, LLM judge ~4.24/5); projected **25 pages/sec** batch on H100 (single-PDF batch mode); **122 pages/sec** on long PDF (22 parallel processes, greenteapress ThinkPython). Documents VRAM: ~5 GB peak / 3.5 GB average per worker; `--workers` tuning. olmOCR cost table: tokens/sec and pages/USD on L40S vs H100 for olmOCR vs Marker vs MinerU. |
| **Audit method** | Comparative benchmarking (§5.3) |
| **Scoring hook** | §6.1; not a gate (throughput ≠ QA quality) |
| **Gaming vector** | Report batch peak without serial latency; omit VRAM requirements. |
| **Anti-gaming guard** | Require both serial and batch figures on named GPU; state worker count for batch. |
| **Evidence grade** | **B** — Marker official GitHub README benchmarks section; olmOCR paper Table 6 |

**Marker-distinct:** FastAPI server (`localhost:8001/docs`) for HTTP integration; Modal deployment example; optional `--use_llm` with pluggable backends (Gemini, Ollama, OpenAI-compatible, Azure, Claude, Vertex) — relevant to hybrid architecture but **wrong as whisker's default** (cloud-first, violates model-sovereignty).

**Wrong for whisker:** Marker's default LLM services are cloud APIs; whisker must document self-hosted slot mapping per `SERVICES.toml` doctrine.

---

#### Criterion C3: Benchmark/eval infrastructure versioned and maintained (MinerU + olmOCR contrast)

| Field | Value |
|---|---|
| **Criterion** | Extraction projects claiming benchmark leadership must **pin eval protocol version**, document known biases fixed across versions, and publish sub-metrics separately. |
| **How to measure** | MinerU2.5-Pro: OmniDocBench v1.6 with Base (standard) / Hard (296 complex) / Full (1,651 pages) tiers; fixes element-matching bias from v1.5 via Multi-Granularity Adaptive Matching; reports Text Edit↓, Formula CDM↑, Table TEDS↑, Table TEDS-S↑, Read Order Edit↓ separately. olmOCR: olmOCR-Bench developed *after* model training to prevent benchmark iteration leakage; category CI reported. Marker: HuggingFace `datalab-to/marker_benchmark` (~8K pages) + Datalab public benchmark pages combining OmniDocBench + olmOCR-bench + others; LLM-as-judge with **A/B order randomization** to reduce position bias. |
| **Audit method** | Benchmarking methodology (§5.12); calibration audit (§5.5) for protocol drift |
| **Scoring hook** | §6.5 disagreement handling; §6.3 evidence grade drops if eval protocol unversioned |
| **Gaming vector** | Tune on benchmark, report leaderboard score without protocol version; hide LLM-judge position bias. |
| **Anti-gaming guard** | Require eval config file or version tag in results; if LLM-judge used, require order randomization and per-axis breakdown (Marker does randomize; still not a substitute for deterministic tests). |
| **Evidence grade** | **A** — OmniDocBench CVPR 2025 paper; MinerU2.5-Pro arXiv:2604.04771; olmOCR paper §4.1 |

**Lesson separation:** MinerU leads on **reference-matching benchmark protocol maintenance**; olmOCR leads on **leakage-resistant benchmark design** (post-hoc bench); Marker leads on **cross-benchmark aggregation + public comparison UI** but couples heuristic with LLM-judge (weaker construct validity for gating).

---

## 3. External benchmark / exemplar bar (summary)

| Dimension | olmOCR bar | Marker bar | MinerU bar |
|---|---|---|---|
| Comprehension eval | olmOCR-Bench unit tests + downstream LM task battery | Heuristic + LLM-judge (1–5); no downstream tasks | OmniDocBench per-axis reference metrics; v1.6 tier protocol |
| Zero-authoring baseline | **Best-in-class:** auto BaselineTest every page, RepeatDetector, documented thresholds | Not documented | Not documented |
| Model serving | vLLM default, external server mode, Docker, cost/throughput table, retry rate | FastAPI, batch throughput docs, Modal example, VRAM/worker tuning | Docker compose (api/openai-server/router), vLLM pass-through, concurrency docs, router multi-GPU |
| Eval transparency | Open bench dataset + test code; post-hoc bench design | Open HF benchmark set; Datalab public comparison pages | OmniDocBench eval code; active leaderboard updates; protocol bias fixes published |
| Where wrong for whisker | English-centric charset baseline; LM pretraining eval ≠ WG21 gate | Cloud LLM defaults; GPL license; LLM-judge as primary metric | Overall composite score; pipeline tool ≠ QA gate framework |

**Cross-exemplar head-to-head (olmOCR-Bench Overall, from olmOCR paper Table 4):** olmOCR v0.1.75 anchored **75.5 ± 1.0** > Marker v1.7.5 **70.1 ± 1.1** > MinerU v1.3.10 **61.5 ± 1.1** — but category columns diverge sharply (e.g., MinerU leads headers/footers exclusion at 96.6 vs Marker's 84.9). **Per-axis reporting is mandatory**; Overall hides complementary strengths.

---

## 4. Recommended weight and gate rationale

| Criterion | Weight recommendation | Hard gate? | Rationale |
|---|---|---|---|
| A1 Downstream / comprehension proxy | **Medium** (8–12% of eval-science dimension) | No | Methodologically gold-standard but expensive; not every QA tool runs LM pretraining — require *either* downstream battery *or* fact-recovery unit tests, not neither. |
| A2 Binary unit tests | **High** (15–20% of eval-science dimension) | **Candidate gate:** if extraction QA gates on edit distance alone for math/tables/order | Strongest construct-validity evidence; directly mirrors whisker's multi-lane design. |
| A3 RLVR / synthetic test scaling | **Low** (3–5%) | No | Advanced maturity indicator; not required for professional-grade QA. |
| B1 Universal baseline coverage | **Medium** (10% of adversarial-robustness dimension) | **Yes — gate:** no baseline-on-all-pages = fail | Cheap, deterministic, catches catastrophic output; olmOCR proves industry feasibility. |
| B2 Baseline check catalog | **Medium** (paired with B1) | **Yes — gate:** silent empty/garbled pass | Anti-Goodhart floor; whisker already has guard/anchor philosophy — this externalizes the pattern. |
| C1 Server/client separation | **Medium** (10–12% of release-readiness / model-sovereignty) | No (unless package claims self-hosted production) | Model-sovereignty requires documented serving path; MinerU+olmOCR set the bar. |
| C2 Throughput benchmarks | **Low** (5%) | No | Informational for operators; not quality. |
| C3 Eval protocol versioning | **Medium** (10% of eval-science) | **Candidate gate:** undisclosed eval protocol version on published scores | MinerU v1.5→v1.6 bias fix proves protocols drift; unversioned scores are stale evidence. |

**Composite interaction:** Criteria A2 + B1 + B2 form a **conjunctive floor** for extraction eval credibility — aligned with §6.2 (high weighted score + failed gate = fail). Marker-style LLM-judge-only eval fails A2; missing baseline fails B1/B2.

---

## 5. Sources

### Tier 1 — Authoritative / primary

| ID | Source | URL | Date/version |
|---|---|---|---|
| S1 | Poznanski et al., *olmOCR: Unlocking Trillions of Tokens in PDFs with Vision Language Models* | https://arxiv.org/abs/2502.18443 | v3, Feb 2025 (paper); Jul 2025 arXiv revision |
| S2 | Poznanski et al., *olmOCR 2: Unit Test Rewards for Document OCR* | https://arxiv.org/html/2510.19817 | Oct 2025 |
| S3 | Ouyang et al., *OmniDocBench: Benchmarking Diverse PDF Document Parsing* (CVPR 2025) | https://arxiv.org/html/2412.07626v2 | Dec 2024 / CVPR 2025 |
| S4 | Wang et al., *MinerU2.5-Pro: Pushing the Limits of Data-Centric Document Parsing at Scale* | https://arxiv.org/html/2604.04771v2 | Apr 2026 |

### Tier 2 — Strong secondary (official project)

| ID | Source | URL | Date/version |
|---|---|---|---|
| S5 | Allen AI, `allenai/olmocr` README (vLLM pipeline, external server, Docker) | https://github.com/allenai/olmocr/blob/main/README.md | v0.1.75 Jun 2025; v0.2.0 Jul 2025 |
| S6 | Allen AI, `allenai/olmOCR-bench` dataset card (test types, category results) | https://huggingface.co/datasets/allenai/olmOCR-bench | Updated Dec 2025 |
| S7 | Datalab, `datalab-to/marker` README (benchmarks, FastAPI, throughput, LLM services) | https://github.com/datalab-to/marker | Accessed 2026-07-18 |
| S8 | OpenDataLab, MinerU Docker deployment docs | https://opendatalab.github.io/MinerU/quick_start/docker_deployment/ | vLLM base v0.21.0 |
| S9 | OpenDataLab, MinerU advanced CLI (vLLM pass-through, multi-GPU) | https://opendatalab.github.io/MinerU/usage/advanced_cli_parameters/ | Accessed 2026-07-18 |
| S10 | OpenDataLab, `opendatalab/OmniDocBench` README (metrics, Overall formula, eval config) | https://github.com/opendatalab/OmniDocBench | Leaderboard updates through Mar 2026 |

**Source count:** 10 distinct Tier 1–2 sources (4 Tier 1, 6 Tier 2). Tier 3 not load-bearing.

### Contradictions surfaced

| Topic | Position A | Position B | Resolution for rubric |
|---|---|---|---|
| Primary eval method | olmOCR: binary unit tests reject edit distance | MinerU/OmniDocBench: normalized edit distance + TEDS + CDM composite | **Both positions recorded.** Prefer higher-Tier construct-validity argument (olmOCR S1/S2) for *gating*; reference-matching (S3/S10) acceptable for *axis diagnostics* if sub-metrics reported separately. Mark contested if used as sole gate. |
| LLM-as-judge | Marker/Datalab: LLM judge with order randomization is standard | olmOCR: LLM judges self-prefer (Panickssery 2024), miss fine errors | LLM-judge = **advisory / tie-break only**, never hard gate — consistent with whisker doctrine. |
| Inference engine | olmOCR blog (Feb 2025): SGLang optimized | olmOCR README (Jun 2025): switched default to vLLM | vLLM is current exemplar bar (S5); SGLang mention is historical. |

---

## 6. Overlap statement

**Confirmed:** This persona did **not**:

- Open, inspect, or score whisker production code (no whisker `file:line` citations).
- Red-team olmOCR, Marker, or MinerU as converters (that is `packages/whisker/research/redteam/`, which holds per-repo defect reports for olmocr, marker, and MinerU among 28 others).
- Re-run or duplicate the `persona/` deterministic-core code audit, the `llm-stack/` tapetum advisory-lane audit, or the `buildvsbuy/` library-choice decisions.
- Clone, fork, or copy any exemplar code.

**Boundary held:** `redteam/` answered "where does this converter break?" This persona answers "what eval, baseline, and serving practices should the whisker *audit rubric* adopt?" — grouped by lesson (comprehension eval / baseline checks / serving), not by repo defect inventory.

**Prior folders explicitly avoided:** `redteam/`, `persona/`, `llm-stack/`, `buildvsbuy/`, `langextract/` (adoption verdict), `comprehension-poc-report.md` (internal POC results — external method only here).

---

## Strongest transferable practice (executive pull-quote)

**olmOCR's automatic BaselineTest on every page — non-empty alphanumeric output, trailing n-gram repetition detection (>30 chars), and documented charset sanity rules — combined with olmOCR-Bench's deterministic fact-level unit tests instead of edit distance or LLM-as-judge for primary scoring.**

This pair is the highest-leverage import for a WG21 extraction-QA audit rubric: a zero-cost catastrophic-failure gate (Track B) plus construct-valid comprehension-oriented eval (Track A). MinerU and Marker contribute serving topology (Track C) and benchmark protocol versioning, but neither matches olmOCR's baseline-plus-unit-test eval discipline.
