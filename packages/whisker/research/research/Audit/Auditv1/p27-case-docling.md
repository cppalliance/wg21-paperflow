# P27 — Docling (IBM) Engineering & Governance Case Study

**Persona:** 27 — Docling (IBM) Engineering & Governance Case Study  
**Date:** 2026-07-18  
**Scope:** External exemplar research only. No whisker code inspection. No converter red-team.

---

## 1. Question restated

What engineering, governance, evaluation, and API-design practices does IBM **Docling** demonstrate at enterprise release maturity, and which of those practices should become **audit criteria** for a professional hybrid extraction-QA package (whisker), without cargo-culting Docling's role as a document *converter*?

Docling is studied here as an **exemplar of release engineering, typed document contracts, per-modality benchmarking transparency, table-structure verification discipline, and open-governance maturity** — not as a conversion-quality benchmark for WG21 papers.

---

## 2. Proposed audit criteria

Each criterion below is derived from Tier 1–2 Docling sources. Tags: **audit-method** (from `00-FRAME.md` §5), **scoring hook** (from §6), **evidence grade** (A/B/C/D).

---

### Criterion D27-01 — Unified typed document contract (Pydantic `DoclingDocument`)

**Criterion:** The package exposes a single, versioned, typed intermediate representation (IR) for all extraction/QA artifacts, defined with Pydantic (or equivalent schema-validated types), not ad-hoc dicts or free-text blobs.

**How to measure:** Inspect public API docs and core types module. Confirm: (a) IR is a named, importable type; (b) sub-item types (`TextItem`, `TableItem`, etc.) carry provenance, layout, and semantic role fields; (c) serialization round-trips through `model_validate_json` / `model_dump`; (d) export backends (Markdown, JSON) are projections of the IR, not alternate truth.

**Audit-method:** Conformance checklist + comparative benchmarking against exemplars (§5.1, §5.3).

**Scoring hook:** Feeds §6.1 dimension *release-readiness / API contract*; supports §6.2 gate "quality metric with disproven construct validity" when IR fields do not match what downstream gates claim to measure.

**Gaming vector:** Declaring a "schema" that is never validated at runtime, or exporting Markdown only with no typed IR behind it.

**Anti-gaming guard:** Require a live round-trip test: construct minimal valid IR → serialize → deserialize → assert field preservation on at least one table cell with span metadata and one text item with provenance.

**Evidence grade:** A (multiple Tier-1/2 converging: technical report §3.3, official concepts doc, public API reference).

**Sources:** Docling v2 concepts doc (`DoclingDocument` as Pydantic datatype with texts/tables/pictures, hierarchy, bboxes, provenance); API reference marks `DocumentConverter`, `FormatOption`, `InputFormat` as pydantic-model; technical report §3.3 describes assembly into `docling-core` typed document object.

**Whisker mismatch note:** Whisker QA gates operate on *markdown fidelity*, not a full page-layout IR. The transferable lesson is **separating typed internal truth from export projections**, not adopting Docling's layout ontology wholesale.

---

### Criterion D27-02 — Per-modality evaluation CLI with published benchmark recipes

**Criterion:** Evaluation is split by **modality** (layout, table_structure, reading_order, markdown_text, etc.), each with documented commands, metrics, and committed result artifacts — never a single opaque "quality score."

**How to measure:** Confirm a dedicated eval package or module exists with: (a) `create-gt`, `create-eval`, `evaluate`, `visualize` (or equivalent) subcommands; (b) per-benchmark markdown docs listing exact shell recipes; (c) checked-in JSON/txt/plot artifacts for at least one public benchmark (DP-Bench, OmniDocBench, or domain equivalent); (d) ability to evaluate sub-pipelines independently (e.g., table model only vs end-to-end).

**Audit-method:** Comparative benchmarking + metric construct-validity audit (§5.3, §5.4).

**Scoring hook:** Feeds §6.1 *extraction-quality/eval* and §6.4 anti-Goodhart rule "no single composite number alone."

**Gaming vector:** Reporting only end-to-end Markdown BLEU while table structure regressions hide in aggregate.

**Anti-gaming guard:** Require per-axis reports in CI or release notes; fail audit if only one modality is measured while others are claimed in marketing/docs.

**Evidence grade:** A (`docling-eval` README + DP-Bench/OmniDocBench benchmark docs with modality-specific `evaluate --modality` flags and linked evaluation JSON/plots).

**Sources:** `docling-eval` README (CLI commands, benchmark list); `docs/DP-Bench_benchmarks.md` (layout mAP, TableFormer TEDS struct-only/with-text, reading-order ARD, markdown BLEU/edit-distance/F1/precision/recall); parallel OmniDocBench doc with same modality split.

**Whisker mismatch note:** Whisker should evaluate **QA gate effectiveness** (guard/anchor/facts), not layout mAP. The transferable pattern is **modality-separated eval harness**, mapped to whisker axes (TEDS/NID/MHS/comprehension) per whisker's own docs.

---

### Criterion D27-03 — Span-aware table grid verification in regression tests

**Criterion:** Table QA/regression tests compare **full 2D grids** including row/column counts, cell text, and semantic cell roles (column_header, row_header, row_section), not just serialized Markdown string equality.

**How to measure:** Locate a `verify_table_*` (or equivalent) helper used by reference tests. Confirm it: (a) asserts `num_rows` / `num_cols`; (b) iterates `grid[i][j]`; (c) checks role flags per cell; (d) optionally supports fuzzy text mode with explicit threshold. Reference fixture updates require **double review** when golden data changes.

**Audit-method:** Conformance checklist + reproducibility replay (§5.1, §5.8).

**Scoring hook:** Feeds §6.1 *extraction-quality* and §6.2 candidate hard gate on table-structure claims.

**Gaming vector:** Markdown table snapshots that look correct while JSON/grid roles (header vs body) are wrong; cosmetic pipe-table compliance.

**Anti-gaming guard:** Require grid-level assertions for any criterion claiming table fidelity; pair Markdown export tests with structured grid tests.

**Evidence grade:** B (official project test utility `verify_table_v2` in public repo; CONTRIBUTING.md reference-test policy).

**Sources:** `tests/verify_utils.py` — `verify_table_v2` compares rows/cols, per-cell text via `verify_text`, and `column_header` / `row_header` / `row_section` flags; `CONTRIBUTING.md` — reference documents regenerated with `DOCLING_GEN_TEST_DATA=1`, **double review** on reference data PRs.

**Whisker mismatch note:** Docling verifies *conversion output* against frozen goldens. Whisker verifies *QA verdicts* against labeled corpora. The transferable practice is **structured, role-aware table diffing**, not copying Docling's OTSL/TableFormer pipeline.

---

### Criterion D27-04 — Reference-test golden discipline with explicit regeneration protocol

**Criterion:** Long-lived golden/reference fixtures exist for representative documents, with a documented regeneration command, review policy, and strict vs fuzzy comparison modes.

**How to measure:** Check for: (a) named env var or flag to regenerate goldens; (b) CONTRIBUTING/policy text requiring extra review when goldens change; (c) separate strict/fuzzy tolerances for OCR vs programmatic PDF paths; (d) multi-artifact verification (JSON IR, Markdown, optional secondary export like DocTags).

**Audit-method:** Maturity-model scoring (§5.2) + reproducibility replay (§5.8).

**Scoring hook:** Feeds §6.1 *CI/test maturity* and §6.4 ("has tests" → "tests exercise gate teeth").

**Gaming vector:** Shrinking golden corpus to pass CI; loosening tolerances without documented rationale.

**Anti-gaming guard:** Count of reference documents must not decrease without ADR; any tolerance change must cite modality (strict bbox vs fuzzy OCR) in named constants.

**Evidence grade:** B (CONTRIBUTING.md + `verify_conversion_result_v2` multi-export checks).

**Sources:** CONTRIBUTING.md reference-test section; `verify_utils.py` constants (`STRICT_BBOX_TOL_RATIO`, `FUZZY_BBOX_TOL_RATIO`, `verify_conversion_result_v2` checking pages meta, doc items, MD, DocTags).

---

### Criterion D27-05 — Typed public API surface with generated reference documentation

**Criterion:** Primary entry points (`DocumentConverter`-class) are documented in auto-generated API reference with type signatures, pydantic-model badges, and worked examples — not README-only.

**How to measure:** Official docs site has Reference section; entry class documents `allowed_formats`, `format_options`, return type `ConversionResult` wrapping typed document; examples show `convert` / batch paths.

**Audit-method:** Documentation-completeness audit (§5.9) + conformance checklist (§5.1).

**Scoring hook:** Feeds §6.1 *documentation/operator UX*.

**Gaming vector:** Undocumented kwargs; return type documented as `dict` or `Any`.

**Anti-gaming guard:** Spot-check that every public CLI flag maps to a typed config field in reference docs.

**Evidence grade:** A (official API reference + technical report §2 code example).

**Sources:** `docling-project.github.io/docling/reference/document_converter/` — `DocumentConverter`, `ConversionResult`, `FormatOption`, `InputFormat` with pydantic-model labels; technical report §2 `DocumentConverter` quick-start.

---

### Criterion D27-06 — Layered open governance (Contributor → Committer → Maintainer → TSC)

**Criterion:** Governance docs define role ladder, election/voting rules, release process, and per-repo `MAINTAINERS.md` with contact path — appropriate for a multi-repo foundation-hosted project.

**How to measure:** Check community repo for GOVERNANCE.md, CODE_OF_CONDUCT, CONTRIBUTING cross-links; each core repo lists named maintainers; release process stated; satellite-project criteria documented if ecosystem exists.

**Audit-method:** Maturity-model / capability-level scoring (§5.2) + provenance/license conformance (§5.10) for foundation donation path.

**Scoring hook:** Feeds §6.1 *release-readiness*; optional §6.2 gate for projects claiming "enterprise-grade" without maintainer accountability.

**Gaming vector:** Empty MAINTAINERS; governance doc without enforcement path; bus factor of one hidden behind org account.

**Anti-gaming guard:** Require named humans in MAINTAINERS, dated TSC list, and public release cadence evidence (≥4 releases in trailing 12 months for active projects).

**Evidence grade:** B (GOVERNANCE.md, MAINTAINERS.md, LF AI & Data project page).

**Sources:** `docling-project/community/GOVERNANCE.md` — Contributor/Committer/Maintainer/TSC roles, 2/3 vote rules, scheduled releases, satellite onboarding requires lint/CI/permissive licenses/**OpenSSF silver**; `docling/MAINTAINERS.md` — four named maintainers + contact email; LF AI & Data project page — IBM donation, incubation stage, community channels.

**Whisker mismatch note:** Whisker is a single-package C++ Alliance project, not LF-hosted. Criteria should scale down to **named maintainers + CONTRIBUTING + release notes**, not full TSC machinery.

---

### Criterion D27-07 — High-frequency semver releases with scoped changelogs

**Criterion:** Release cadence is frequent enough to ship fixes without batching unrelated changes; release notes group by type (feature/fix) with issue/PR links.

**How to measure:** Trailing 12 months: count semver tags; sample latest release for conventional sections; bot or human changelog discipline.

**Audit-method:** Comparative benchmarking (§5.3) — "is this normal for serious OSS?"

**Scoring hook:** Feeds §6.1 *release-readiness*.

**Gaming vector:** `v2.113.0` patch noise without semantic clarity; breaking changes in patch releases.

**Anti-gaming guard:** Require CHANGELOG or GitHub Release categories; flag if API-breaking change lacks major bump.

**Evidence grade:** B (GitHub releases metadata: ~195 releases since 2024-07; v2.113.0 2026-07-14 with Feature/Fix sections and linked PRs).

**Sources:** `github.com/docling-project/docling/releases/tag/v2.113.0`; repo metadata (195 releases, last push 2026-07-17).

**Whisker mismatch note:** Whisker pre-1.0 may intentionally release less often. Audit should compare **release hygiene**, not Docling's ~weekly velocity.

---

### Criterion D27-08 — Developer toolchain standardization (uv, ruff, ty, pre-commit hooks)

**Criterion:** CONTRIBUTING specifies one package manager, formatter/linter, type checker, and pre-commit runner so contributors reproduce CI locally.

**How to measure:** CONTRIBUTING names uv sync, ruff, ty, prek/pre-commit install; CI runs equivalent checks.

**Audit-method:** Conformance checklist (§5.1).

**Scoring hook:** Feeds §6.1 *release-readiness / CI*.

**Gaming vector:** "Works on my machine" without lockfile; type checking optional.

**Anti-gaming guard:** Require lockfile (`uv.lock`) and documented `prek run --all-files` equivalent in CI.

**Evidence grade:** B (CONTRIBUTING.md).

**Sources:** CONTRIBUTING.md — uv, ruff, ty, prek; reference-test and MkDocs doc build instructions.

---

### Criterion D27-09 — OpenSSF Best Practices silver badge as supply-chain maturity signal

**Criterion:** For projects claiming production/enterprise readiness, pursue OpenSSF Best Practices (silver minimum for foundation satellite onboarding; core Docling displays badge on repo).

**How to measure:** Badge visible on README; criteria page shows closed gaps (roadmap, coverage policy, trust boundaries documented, signed PyPI where applicable).

**Audit-method:** Conformance checklist against OpenSSF criteria (§5.1) + supply-chain dimension.

**Scoring hook:** Feeds §6.1 *security/supply-chain*; soft gate unless project claims enterprise bar.

**Gaming vector:** Badge on README linking to stale/incomplete criteria.

**Anti-gaming guard:** Spot-check bestpractices.dev project page for unresolved MUST items.

**Evidence grade:** B (GitHub issue #1374 closed 2025-04-15; badge on repo; GOVERNANCE satellite rule cites silver minimum).

**Sources:** docling README OpenSSF badge; issue #1374 checklist (roadmap, coverage, test policy, PyPI signing, trust boundaries); GOVERNANCE satellite requirements.

---

### Criterion D27-10 — Technical report with reproducible performance methodology

**Criterion:** A maintainer-authored technical report documents pipeline architecture, model boundaries, and **reproducible** perf benchmarks (hardware, thread budget, dataset size, metrics table) — not marketing claims.

**How to measure:** Report includes: test corpus description (page count), hardware specs, env vars (`OMP_NUM_THREADS`), per-backend comparison table, explicit quality/speed tradeoff warnings (e.g., fast backend degrades tables).

**Audit-method:** Metric construct-validity + documentation completeness (§5.4, §5.9).

**Scoring hook:** Feeds §6.1 *documentation* and §6.3 evidence grading (report = Tier 1 anchor).

**Gaming vector:** Cherry-picked PDFs; omitting failure modes.

**Anti-gaming guard:** Require dataset identifier or bundled test set name; disclose backend/mode tradeoffs.

**Evidence grade:** A (arXiv:2408.09869 v1.0, IBM Research affiliation, Table 1 reproducibility details).

**Sources:** Docling Technical Report — 225-page standard test set, M3 Max vs Xeon, 4 vs 16 threads, native vs pypdfium backend, TTS/pages/s/memory; §3.2 TableFormer span handling; Fig. 4 Markdown vs JSON span representation policy.

**Whisker mismatch note:** Whisker should document **deterministic gate latency and false-positive rates on WG21 corpus**, not PDF conversion throughput. The transferable practice is **published eval protocol with hardware/dataset pinned**.

---

### Criterion D27-11 — Foundation hosting with public roadmap and standards adjacency

**Criterion:** Mature exemplars align with a foundation or standards body when scale warrants it; public roadmap exists; adjacent spec work (e.g., DocLang) is separated from core code.

**How to measure:** LF AI & Data project page; roadmap in community repo; announcement of spec WG distinct from parser code.

**Audit-method:** Maturity-model (§5.2).

**Scoring hook:** Informational for whisker unless C++ Alliance pursues external standardization.

**Gaming vector:** "Joining foundation" press release without governance change.

**Anti-gaming guard:** Verify governance repo activity (meeting notes, roadmap commits) post-donation.

**Evidence grade:** B (LF AI & Data pages, GitHub discussion #1184, DocLang WG press 2026-06-09).

**Sources:** lfaidata.foundation/projects/docling; Linux Foundation DocLang WG press release 2026-06-09; discussion #1184 (joined LF AI & Data 2025-03-18).

---

### Criterion D27-12 — Explicit export policy for spanning cells (traceability vs compression)

**Criterion:** When IR supports merged cells, document export policy: whether Markdown **repeats** header text per column for traceability or preserves spans only in JSON — and test both.

**How to measure:** Technical report or docs state rule; tests cover multi-column header repetition in MD and span fields in JSON.

**Audit-method:** Metric construct-validity (§5.4) — ensures metric choice matches export path.

**Scoring hook:** Feeds §6.1 *extraction-quality*; prevents comparing whisker MD to Docling MD without knowing span policy.

**Gaming vector:** Pretty Markdown that duplicates headers inflating text-similarity scores.

**Anti-gaming guard:** Structure-first metrics (TEDS, grid diff) primary; text metrics secondary.

**Evidence grade:** A (technical report Fig. 4 explicit policy).

**Sources:** Technical report Fig. 4 — spanning cells repeated in Markdown for grid-coordinate traceability; span info in JSON cell fields.

---

## 3. External benchmark / exemplar bar

Docling sets the following **external bar** for a "professional, enterprise-adjacent" document AI Python project:

| Dimension | Docling bar (observed) | Whisker-relevant translation |
|---|---|---|
| **Typed IR** | Pydantic `DoclingDocument` in `docling-core`; all exports are projections | Typed gate results / verdict objects; markdown is export, not source of truth |
| **Eval transparency** | Separate `docling-eval` package; DP-Bench + OmniDocBench; per-modality metrics published | Per-axis whisker eval (TEDS, NID, MHS, comprehension) with public recipes; no single score |
| **Table verification** | `verify_table_v2` grid + role flags; double-review goldens | Grid/span-aware table diff in regression; golden WG21 papers with review policy |
| **Release** | ~195 semver releases in ~2 years; bot/human release notes | Less frequent OK; require categorized changelog and semver discipline |
| **Governance** | LF AI & Data, TSC, MAINTAINERS, OpenSSF silver | Named maintainers, CONTRIBUTING, proportionate governance for single package |
| **Docs** | MkDocs site: concepts + auto API reference + examples | Diataxis-style split: operator CLI, invariants, calibration status, agent guidance |
| **Security/supply-chain** | OpenSSF silver, trust-boundary doc, uv lock, signed PyPI (serve) | SPDX, lockfile, dependency audit; document LLM trust boundaries (whisker already emphasizes `wrap_source`) |

**Domain mismatches (do not cargo-cult):**

1. **Role:** Docling is a **converter**; whisker is a **QA gate** over converted markdown. Docling optimizes for RAG ingestion breadth; whisker optimizes for **fail-not-partial fidelity** on WG21 papers.
2. **Determinism:** Docling's AI pipeline (layout, TableFormer, optional VLM) is inherently nondeterministic across hardware/backends. Whisker requires a **strict deterministic core** with advisory-only LLM overlay (CLAUDE.md invariants D1–D11).
3. **Model sovereignty:** Docling defaults include remote/cloud inference paths in ecosystem packages (docling-graph LiteLLM remote, watsonx). Whisker production targets **self-hosted open-weight** models.
4. **Fail mode:** Docling generally **emits best-effort output** for downstream RAG. Whisker must **fail the paper** rather than emit partial QA verdicts.
5. **Comprehension eval:** Docling-eval emphasizes layout/TEDS/markdown similarity, not downstream fact-recovery QA (see P28/P13 for that bar).

**Contradiction surfaced:** Docling's CONTRIBUTING requires **lazy import fix** in recent releases (e.g., pypdfium2 lazy import in v2.113.0), while whisker repo invariants forbid lazy imports in production packages. Exemplar practice (lazy optional deps) is **wrong for whisker** unless explicitly scoped to optional extras with tests proving core import graph unchanged.

---

## 4. Recommended weight & hard-gate rationale

| Criterion | Suggested weight share (within case-study cluster) | Hard gate? | Rationale |
|---|---|---|---|
| D27-01 Typed IR | 12% | No | Foundational; whisker may use slimmer verdict types |
| D27-02 Per-modality eval | 18% | **Candidate yes** | Directly prevents Goodhart collapse; aligns with whisker multi-axis docs |
| D27-03 Table grid verification | 15% | **Candidate yes** | WG21 papers are table-heavy; grid tests are teeth, not cosmetics |
| D27-04 Golden discipline | 10% | No | Maturity signal |
| D27-05 API reference | 8% | No | Professional polish |
| D27-06 Governance | 8% | No (scaled) | Full TSC not required for whisker |
| D27-07 Release cadence | 7% | No | Hygiene, not frequency match |
| D27-08 Dev toolchain | 5% | No | Standard professional Python |
| D27-09 OpenSSF silver | 5% | No | Aspirational for small team |
| D27-10 Technical report | 7% | No | Whisker equivalent = calibration report + architecture docs |
| D27-11 Foundation | 3% | No | Not applicable at whisker scale |
| D27-12 Export/span policy | 2% | No | Methodological awareness |

**Hard-gate recommendation:** D27-02 and D27-03 are the strongest candidates for whisker audit gates because they mirror whisker's existing conjunctive multi-metric design and address the highest-risk gaming vectors (single-number optimization, Markdown-only table checks).

Weights are **cluster-local suggestions** for synthesis; final weights require cross-persona evidence (P09, P12, P15, P19).

---

## 5. Sources

| # | Tier | Source | URL | Version / date |
|---|---|---|---|---|
| 1 | **1** | Docling Technical Report (IBM Research) | https://arxiv.org/abs/2408.09869 | v1.0, arXiv:2408.09869, Aug 2024 (HTML v5 accessed 2026-07-18) |
| 2 | **1** | Docling official documentation (concepts + index) | https://docling-project.github.io/docling/ | Accessed 2026-07-18 |
| 3 | **1** | DoclingDocument concept documentation | https://docling-project.github.io/docling/concepts/docling_document/ | Docling v2, accessed 2026-07-18 |
| 4 | **2** | Docling API reference — `DocumentConverter` | https://docling-project.github.io/docling/reference/document_converter/ | Auto-generated, accessed 2026-07-18 |
| 5 | **2** | `docling-eval` README (evaluation CLI + benchmarks) | https://github.com/docling-project/docling-eval/blob/main/README.md | main, accessed 2026-07-18 |
| 6 | **2** | DP-Bench benchmark recipes | https://github.com/docling-project/docling-eval/blob/main/docs/DP-Bench_benchmarks.md | main, accessed 2026-07-18 |
| 7 | **2** | OmniDocBench benchmark recipes | https://github.com/docling-project/docling-eval/blob/main/docs/OmniDocBench_benchmarks.md | main, accessed 2026-07-18 |
| 8 | **2** | Docling GOVERNANCE.md | https://github.com/docling-project/community/blob/main/GOVERNANCE.md | main, accessed 2026-07-18 |
| 9 | **2** | Docling CONTRIBUTING.md | https://github.com/docling-project/docling/blob/main/CONTRIBUTING.md | main, accessed 2026-07-18 |
| 10 | **2** | Docling MAINTAINERS.md | https://github.com/docling-project/docling/blob/main/MAINTAINERS.md | main, accessed 2026-07-18 |
| 11 | **2** | Docling release v2.113.0 | https://github.com/docling-project/docling/releases/tag/v2.113.0 | 2026-07-14 |
| 12 | **2** | Table verification test utility (`verify_table_v2`) | https://github.com/docling-project/docling/blob/main/tests/verify_utils.py | main, accessed 2026-07-18 |
| 13 | **2** | LF AI & Data — Docling project page | https://lfaidata.foundation/projects/docling/ | Accessed 2026-07-18 |
| 14 | **3** | OpenSSF Best Practices silver badge issue #1374 | https://github.com/docling-project/docling/issues/1374 | Closed 2025-04-15 |

**Tier 1–2 distinct primary source count: 12** (floor ≥3 satisfied).

---

## 6. Overlap statement

This persona **did not**:

- Inspect whisker production code or cite whisker `file:line`
- Repeat converter red-team findings from `packages/whisker/research/redteam/docling.md` (conversion defects, attack probes on Docling-as-converter)
- Re-litigate build-vs-buy or LangExtract adoption (`langextract/` swarm)
- Clone, fork, or copy Docling source into the workspace

This persona **did** mine Docling's **engineering maturity, governance, typed API, per-modality eval transparency, and table grid verification practices** as external audit criteria for the whisker professional-grade audit frame (`00-FRAME.md` / `00-ROSTER.md` P27 mandate).

**Prior folder avoided:** `redteam/` (specifically `redteam/docling.md` converter red-team report).

---

## Summary metrics (dispatch return)

- **Tier 1–2 source count:** 12 distinct sources (4 Tier 1, 8 Tier 2)
- **Strongest transferable practice:** **Per-modality evaluation with a dedicated eval harness and published benchmark recipes** (`docling-eval`: separate `create-gt` / `create-eval` / `evaluate --modality` for layout, table_structure, reading_order, markdown_text on DP-Bench/OmniDocBench), paired with **`verify_table_v2` span-aware grid regression** — together they prevent single-score Goodhart gaming and Markdown-only table false confidence. For whisker, map this to **per-axis gate calibration (TEDS/NID/MHS/comprehension) with structured table grid diffs**, not Docling's conversion modalities.
