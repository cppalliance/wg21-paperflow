# P29 — unstructured / Nougat / Surya API & Serving Case Study

**Persona:** 29 (Cluster H — Repository case studies)  
**Date:** 2026-07-18  
**Scope:** External exemplar practices only. No whisker code inspection, no converter red-team, no code cloning.

---

## 1. Question restated

What transferable audit criteria can be extracted from **unstructured**, **Nougat**, and **Surya** regarding:

- **(a)** public API / library design and packaging,
- **(b)** license-model shifts and lessons for OSS extraction tools, and
- **(c)** eval transparency and reported metrics,

while keeping each repo's distinct lessons separate and tagging practices to audit dimensions?

---

## 2. Proposed audit criteria

Each criterion includes: how to measure, audit-method tag (§5 of `00-FRAME.md`), scoring-design hook (§6), gaming vector, anti-gaming guard, evidence grade, and Tier 1–2 sources.

### 2.1 Lesson bucket A — unstructured: API, packaging, OSS/commercial boundary

#### C-P29-A1 — Canonical element API with typed partition surface

**Criterion:** A document-extraction library exposes a stable, typed output contract (element types + metadata schema) and a single auto-routing entry point (`partition`) plus format-specific partition functions for non-default behavior.

**How to measure:** Check public API docs and package exports for: (1) enumerated element types, (2) metadata fields documented per element, (3) `partition` auto-route table by MIME/extension, (4) format-specific functions (`partition_pdf`, etc.) documented when kwargs differ from defaults.

**Audit method:** Conformance checklist (§5.1) + Comparative benchmarking against exemplars (§5.3).

**Scoring hook:** Feeds §6.1 dimension *release-readiness / public API contract*; supports §6.2 gate candidate "public output schema undocumented or unstable across minor releases."

**Gaming vector:** Re-exporting raw dict blobs without typed element classes while claiming "structured output."

**Anti-gaming guard:** Require published element-type enum, metadata field list, and at least one round-trip example (partition → JSON → documented schema) in official docs.

**Evidence grade:** B (converging Tier-2 official docs + pyproject metadata).

**Sources:** Unstructured partitioning docs (2026); Unstructured overview docs (2026); `pyproject.toml` in Unstructured-IO/unstructured (2026).

---

#### C-P29-A2 — Optional-dependencies matrix by format and deployment mode

**Criterion:** Heavy format-specific and inference dependencies are isolated in named `[project.optional-dependencies]` extras (per file type, per inference backend, per ingest connector bundle), with a documented install recipe per supported use case.

**How to measure:** Inspect `pyproject.toml` / packaging manifest for: extras keyed by format (`pdf`, `docx`, …), feature bundles (`local-inference`, `ingest`), and README install lines mapping use cases to `pip install pkg[extra,...]`.

**Audit method:** Conformance checklist (§5.1).

**Scoring hook:** §6.1 *release-readiness / dependency hygiene*; §6.4 anti-gaming (minimal core install must not silently omit required parsers).

**Gaming vector:** Declaring broad format support while default `pip install` omits parsers; users discover missing deps at runtime.

**Anti-gaming guard:** CI matrix installs each documented extra and runs at least one smoke partition per extra; README lists minimum extras per format.

**Evidence grade:** A (Tier-2 primary packaging manifest + official docs alignment).

**Sources:** Unstructured `pyproject.toml` (2026); PyPI `unstructured` metadata (v0.24.x, 2026).

**Whisker mismatch note:** Whisker is WG21 PDF/HTML focused; a 20+ format ingest matrix is out of scope. Transfer the *pattern* (extras for PDF vs HTML vs optional LLM lane), not the breadth.

---

#### C-P29-A3 — Explicit OSS-vs-production capability matrix (license posture without relicensing)

**Criterion:** When a project maintains Apache/MIT OSS code alongside a commercial platform, official docs publish a side-by-side capability table stating what the OSS library does **not** include (performance, models, compliance, ops), and which code paths invoke paid SaaS (e.g. `partition_via_api`).

**How to measure:** Locate official comparison table (OSS vs Platform/API); verify billing triggers for hybrid calls; confirm LICENSE file for core library unchanged (Apache-2.0) while commercial terms live in separate product docs.

**Audit method:** Documentation-completeness audit (§5.9) + Provenance / license conformance (§5.10).

**Scoring hook:** §6.2 hard-gate candidate: "license/provenance claim contradicts documented SaaS routing or undeclared commercial dependency for core workflows."

**Gaming vector:** Marketing "open source" while default quickstarts route to API keys and metered SaaS without prominent disclosure.

**Anti-gaming guard:** Require capability matrix in Tier-2 docs; audit sample quickstart for implicit SaaS calls; THIRD_PARTY / LICENSE unchanged for library artifact.

**Evidence grade:** B (Tier-2 official docs; no Tier-1 license change because core library remains Apache-2.0).

**Sources:** Unstructured overview docs — Limits & comparison table (2026); Unstructured pricing / SaaS routing docs (2026); Unstructured-IO/unstructured LICENSE.md (Apache-2.0, 2022–2026).

**Contradiction surfaced:** Roster search lead "unstructured license change" does **not** match current evidence: core `unstructured` and `unstructured-api` repos remain **Apache-2.0**. The shift is **product-tier** (OSS prototype vs Platform production), not a BSL/SSPL relicensing event. Audit criteria should target **boundary transparency**, not assume a license swap.

---

### 2.2 Lesson bucket B — Nougat: packaging, eval transparency, metric reporting

#### C-P29-B1 — Per-modality metric decomposition (never a single headline number)

**Criterion:** Extraction quality evaluation reports metrics **per modality** (e.g. plain text, math, tables, and an "All" aggregate) using multiple metric families (normalized edit distance/CER, BLEU, METEOR, precision/recall/F1), with methodology text explaining known blind spots.

**How to measure:** Review eval section of paper/README/benchmark docs for: modality rows in results tables, ≥2 metric families, prose on failure modes (e.g. math formatting ambiguity).

**Audit method:** Metric construct-validity audit (§5.4) + Benchmarking methodology (§5.3).

**Scoring hook:** §6.1 *extraction-quality/eval*; §6.4 anti-Goodhart — composite scores forbidden without per-axis disclosure (aligns with FRAME §6.1 "no single composite alone").

**Gaming vector:** Quoting only "All" F1 while math/table modalities collapse; using BLEU alone on markup with tokenization sensitivity.

**Anti-gaming guard:** Require published per-modality table; any public benchmark claim must cite modality + metric definition; holdout split described.

**Evidence grade:** A (Tier-1 peer-reviewed paper + reproducible metric definitions).

**Sources:** Blecher et al., *Nougat: Neural Optical Understanding for Academic Documents*, ICLR 2024 (arXiv:2308.13418); OpenReview entry (2024).

---

#### C-P29-B2 — Metric construct validity prose (limitations adjacent to numbers)

**Criterion:** Authors document **why** metrics disagree with human judgment for specific content types (inline math, table structure, PDF embedded text baselines) in the same section as numeric results.

**How to measure:** Eval section contains explicit limitation paragraphs tied to table rows (e.g. math edit distance remains high despite good plain text).

**Audit method:** Metric construct-validity audit (§5.4).

**Scoring hook:** §6.3 evidence grading — claims without limitation prose downgrade to grade C; §6.5 disagreement handling.

**Gaming vector:** Publishing SOTA tables without discussing baseline PDF text extraction unfair advantage or GROBID pipeline hacks.

**Anti-gaming guard:** Rubric requires "limitation sentence per modality with worst metric" in any eval artifact used for gates.

**Evidence grade:** A (Tier-1 ICLR paper §5 results + discussion).

**Sources:** ICLR 2024 Nougat paper (2024); arXiv:2308.13418 (v1, 2023-08).

---

#### C-P29-B3 — Console-script API with optional `[api]` / `[dataset]` extras

**Criterion:** ML extraction tools ship `console_scripts` for CLI inference plus optional extras that gate server (`fastapi`/`uvicorn`) and dataset tooling dependencies separately from core model code.

**How to measure:** Packaging manifest lists `entry_points.console_scripts`; extras_require/`[project.optional-dependencies]` for `api` and training/eval bundles; PyPI install strings documented.

**Audit method:** Conformance checklist (§5.1).

**Scoring hook:** §6.1 *release-readiness*; §6.2 gate: undeclared server deps for documented API path.

**Gaming vector:** Documenting API server in README but not packaging extras; unpinned torch/transformers breaking reproducibility.

**Anti-gaming guard:** `pip install pkg[api]` smoke test in CI; upper bounds on core ML deps declared.

**Evidence grade:** B (Tier-2 official repo packaging).

**Sources:** facebookresearch/nougat `setup.py` (2025); PyPI `nougat-ocr` v0.1.17 (2023-10).

**Whisker mismatch note:** Nougat uses legacy `setup.py` (not pyproject-first). Whisker should follow PyPA modern layout (per P01), but adopt the **extras split** pattern.

**Release cadence gap:** GitHub shows only **2** tagged releases vs **18+** PyPI versions — audit should penalize tag/release drift even when PyPI is active.

---

### 2.3 Lesson bucket C — Surya: serving architecture, dual license, benchmark transparency

#### C-P29-C1 — Shared inference manager across predictors (serving layer separation)

**Criterion:** Document OCR/layout/table predictors share a single inference manager that abstracts backend lifecycle (spawn vLLM / llama.cpp, attach to existing server, `--keep_server`), with env-var overrides documented in one settings module.

**How to measure:** API docs show one manager injected into multiple predictors; settings table lists env overrides; release notes document breaking migration from prior predictor class.

**Audit method:** Comparative benchmarking against exemplars (§5.3) + Observability / fault-injection (§5.11) for server lifecycle.

**Scoring hook:** §6.1 *architecture/hybrid* and *observability*; supports model-sovereignty self-host path.

**Gaming vector:** Hard-coded localhost assumptions; silent respawn per call hiding latency regressions.

**Anti-gaming guard:** Document `--keep_server` / `SURYA_INFERENCE_KEEP_ALIVE`; require benchmark throughput methodology to state server reuse.

**Evidence grade:** B (Tier-2 release notes + README).

**Sources:** datalab-to/surya README (2026-07); surya v0.20.0 release notes (2026-05-27).

**Whisker relevance:** Pattern for optional advisory LLM lane: one backend manager, serial default, env-tuned concurrency — without letting LLM path gate deterministic QA.

---

#### C-P29-C2 — Dual license: permissive **code** vs restricted **weights**

**Criterion:** When model weights carry use-based restrictions (OpenRAIL-M or similar) while code is Apache/MIT, both licenses are published in **primary** docs with revenue/funding thresholds and a commercial relicensing path; GitHub `License` badge alone is insufficient.

**How to measure:** README "Commercial usage" section; HuggingFace model card LICENSE; explicit statement that `pip install` code ≠ weight rights.

**Audit method:** Provenance / license conformance audit (§5.10).

**Scoring hook:** §6.2 **hard gate:** undeclared weight-license violation for redistribution/fine-tune; §6.3 propagate weakest evidence grade on licensing claims.

**Gaming vector:** "Apache-2.0" repo badge while weights forbid >$5M revenue use; downstream product assumes full OSS stack.

**Anti-gaming guard:** Require SPDX or plain-text weight license in repo + model hub; audit checklist separates `LICENSE` (code) from `MODEL_LICENSE`.

**Evidence grade:** A (Tier-2 primary weight license text + maintainer README).

**Sources:** datalab-to/surya README — Commercial usage (2026); HuggingFace `datalab-to/surya-ocr-2` LICENSE — modified OpenRAIL-M (2023 template, model card 2026); Datalab blog surya-2 announcement (2026-05).

---

#### C-P29-C3 — External benchmark with reproducibility path and comparability caveats

**Criterion:** Public benchmark claims cite an external harness (e.g. olmOCR-bench), include per-source/strata breakdown, document reproduction steps (model server + harness repo + format adjustments), and flag non-comparable entries.

**How to measure:** README benchmark section lists: dataset URL, aggregate score, sub-table by document source, "Reproducing" steps, footnotes where methodology differs (Surya explicitly marks LightOnOCR as not directly comparable).

**Audit method:** Benchmarking methodology (§5.3) + Reproducibility replay (§5.8).

**Scoring hook:** §6.1 *extraction-quality/eval*; §6.6 score uncertainty when internal benchmarks coexist with external ones.

**Gaming vector:** Quoting olmOCR-bench headline while tuning on same corpus; mixing internal 91-language pass rate with external bench without labeling provenance.

**Anti-gaming guard:** Require external harness name + commit/version; internal benchmarks labeled "internal" with test count; comparability footnotes mandatory.

**Evidence grade:** B (Tier-2 README + Tier-2 dataset card reference; olmOCR-bench dataset is Tier-1 benchmark artifact).

**Sources:** surya README Benchmarks / Reproducing (2026); allenai/olmOCR-bench dataset card (HuggingFace); surya v0.20.0 release (2026-05).

**Whisker mismatch note:** WG21 papers are English academic PDFs; Surya's multilingual internal bench is informative for method, not domain fit.

---

#### C-P29-C4 — Breaking-change migration guide in release artifacts

**Criterion:** Major API/schema changes ship with: warning in release title/body, before/after code snippet, enumerated output-schema diffs, and new runtime prerequisites.

**How to measure:** Latest major release note contains "Breaking changes", migration snippet, schema field rename list (e.g. `text_lines` → `blocks`).

**Audit method:** Documentation-completeness audit (§5.9).

**Scoring hook:** §6.1 *release-readiness / operator UX*; reduces §6.6 uncertainty on integrator breakage.

**Gaming vector:** Semver patch bump with breaking JSON output; undocumented schema drift breaking downstream gates.

**Anti-gaming guard:** Major releases require CHANGELOG section headers; JSON schema version field or documented output contract tests.

**Evidence grade:** B (Tier-2 GitHub release).

**Sources:** surya v0.20.0 release notes (2026-05-27).

---

## 3. External benchmark / exemplar bar

| Practice | unstructured bar | Nougat bar | Surya bar | Whisker-relevant bar |
|---|---|---|---|---|
| API surface | Typed `Element` list + `partition` router | CLI `nougat` + optional FastAPI extra | Shared `SuryaInferenceManager` + CLI commands | Small public surface; typed QA artifacts; optional tapetum extras |
| Packaging maturity | Modern `pyproject.toml`, hatchling, 234 GitHub releases | Legacy `setup.py`; PyPI≫GitHub release tags | `uv` dev workflow; 86 releases; semver breaking majors documented | pyproject-first + extras for HTML/PDF/LLM lane |
| License clarity | Apache-2.0 library; SaaS billing separate | MIT code + Meta release | Apache-2.0 code + OpenRAIL-M weights | BSL-1.0 code; no weight redistribution; document advisory lane non-gating |
| Eval transparency | Product matrix, not modality metrics | **Gold standard:** per-modality + multi-metric tables + limitation prose | External bench + strata; internal bench labeled | Per-axis whisker gates (stability/fidelity/comprehension); no composite-only reporting |
| Serving | OSS local only; Platform for prod scale | Single-model GPU inference | vLLM/llama.cpp backends; `--keep_server` | Self-hosted open-weight judges; serial LLM default |

**Strongest single exemplar by lesson type:**

- **API/packaging:** unstructured optional-deps + element schema.
- **License model:** Surya code/weight split (transparent dual license).
- **Eval transparency:** Nougat ICLR metric tables with modality split.

---

## 4. Recommended weight & hard-gate rationale

| Criterion | Weight suggestion | Hard gate? | Rationale |
|---|---|---|---|
| C-P29-A3 OSS/commercial matrix | Medium (release-readiness) | **Candidate gate** if product claims "fully OSS" but docs show SaaS-only features on critical path | Prevents license/provenance deception (§6.2) |
| C-P29-B1 Per-modality metrics | **High** (eval science) | **Candidate gate** if a single composite metric gates release without modality breakdown | Directly implements §6.1 anti-collapse rule |
| C-P29-B2 Metric limitation prose | Medium-high | No (scored) | Downgrades evidence grade when absent (§6.3) |
| C-P29-C2 Dual license disclosure | Medium (provenance) | **Yes** for weight-license violations in redistribution scenarios | Non-compensatory legal risk |
| C-P29-C3 Benchmark reproducibility | Medium-high (eval) | No | Required for defensible quality claims |
| C-P29-A1, A2, B3, C1, C4 | Low–medium | No | Maturity differentiators |

Weights deferred to Opus synthesis; above ranks by Tier-1 eval leverage for whisker's QA mission.

---

## 5. Sources (tiered)

### Tier 1 — Authoritative / primary

| ID | Source | URL | Date/version |
|---|---|---|---|
| S1 | Blecher et al., *Nougat: Neural Optical Understanding for Academic Documents* (ICLR 2024) | https://arxiv.org/abs/2308.13418 | 2023-08 preprint; ICLR 2024 |
| S2 | ICLR 2024 proceedings PDF (Nougat) | https://proceedings.iclr.cc/paper_files/paper/2024/file/a39a9aceda771cded859ae7560530e09-Paper-Conference.pdf | 2024 |
| S3 | Modified OpenRAIL-M license (Surya OCR 2 weights) | https://huggingface.co/datalab-to/surya-ocr-2/blob/main/LICENSE | Template 2023-03; model 2026 |

### Tier 2 — Strong secondary (official project / maintainer)

| ID | Source | URL | Date/version |
|---|---|---|---|
| S4 | Unstructured-IO/unstructured `pyproject.toml` | https://github.com/Unstructured-IO/unstructured/blob/main/pyproject.toml | 2026-07 |
| S5 | Unstructured open-source overview (limits & comparison table) | https://docs.unstructured.io/open-source/introduction/overview | 2026 |
| S6 | Unstructured partitioning docs | https://docs.unstructured.io/open-source/core-functionality/partitioning | 2026 |
| S7 | Unstructured library LICENSE (Apache-2.0) | https://github.com/Unstructured-IO/unstructured/blob/main/LICENSE.md | 2022–2026 |
| S8 | facebookresearch/nougat `setup.py` | https://github.com/facebookresearch/nougat/blob/main/setup.py | 2025-02 |
| S9 | PyPI `nougat-ocr` | https://pypi.org/project/nougat-ocr/ | v0.1.17, 2023-10 |
| S10 | datalab-to/surya README | https://github.com/datalab-to/surya | 2026-07-17 (v0.22.0) |
| S11 | surya v0.20.0 release (Surya OCR 2 breaking changes) | https://github.com/datalab-to/surya/releases/tag/v0.20.0 | 2026-05-27 |
| S12 | Datalab blog — Surya OCR 2 announcement | https://www.datalab.to/blog/surya-2 | 2026-05 |
| S13 | olmOCR-bench dataset card | https://huggingface.co/datasets/allenai/olmOCR-bench | 2025–2026 |
| S14 | PyPI `unstructured` | https://pypi.org/project/unstructured/ | v0.24.x, 2026-07 |

**Distinct Tier 1–2 primary sources used for load-bearing criteria:** **14** (minimum floor ≥3 satisfied).

**Tier 3 (context only, not load-bearing):** Unstructured pricing page; Datalab commercial blog CTAs.

---

## 6. Overlap statement

This persona researched **API design, packaging, license-boundary transparency, and eval reporting practices** from unstructured, Nougat, and Surya.

**Did not duplicate:**

- `packages/whisker/research/redteam/` — per-converter defect reports for these tools (converter red-team).
- Any whisker production-code audit or `file:line` scoring.
- `langextract/` adoption verdict, `buildvsbuy/` library picks, or `persona/` / `llm-stack/` code findings.
- Code cloning, forking, or copying from exemplar repositories.

**Distinct contribution:** Groups three ecosystems by **engineering and governance lessons** (element API + extras matrix, per-modality eval science, dual-license + serving manager patterns) to supply audit **criteria and external bars**, not converter quality scores.

---

## 7. Summary metrics (dispatch return)

| Metric | Value |
|---|---|
| **Tier 1–2 source count** | **14** distinct sources (3 Tier 1, 11 Tier 2) |
| **Strongest transferable practice** | **Nougat-style per-modality, multi-metric eval reporting with explicit construct-validity limitations adjacent to the numbers** — directly implements the FRAME rule against single-number collapse and gives whisker's stability/fidelity/comprehension axes a published precedent |
