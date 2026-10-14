# P26 — LangExtract Engineering & Eval Case Study

**Persona:** 26 (Cluster H — Repository & framework case studies)  
**Date:** 2026-07-18  
**Exemplar:** Google [LangExtract](https://github.com/google/langextract) v1.6.0 (PyPI release 2026-07-02)  
**Method:** Comparative benchmarking against exemplars (§5.3); maturity-model cues (§5.2); provenance audit hooks (§5.10)

---

## 1. Question restated

What **engineering, evaluation, grounding-provenance, packaging, and release practices** does Google LangExtract demonstrate that a professional-grade extraction-QA audit rubric should treat as an external bar — and where would copying LangExtract's choices be **wrong** for a model-sovereign, fidelity-first, WG21-domain package like whisker?

This persona mines **practices and criteria only**. It does not re-decide algorithm or library adoption (that boundary belongs to the prior `langextract/` swarm).

---

## 2. Proposed audit criteria

Each criterion is transferable from LangExtract's public engineering surface. Audit dimensions tagged per `00-FRAME.md` clusters.

---

### Criterion 2.1 — Grounding provenance on every extraction span

| Field | Value |
|---|---|
| **Criterion** | Every LLM-derived claim returned to callers carries an explicit **grounding status**: either a source `char_interval` (start/end positions in the input document) or an explicit **ungrounded** sentinel (`char_interval = None`). |
| **How to measure** | Inspect API return types and docs: (a) is span provenance a first-class field on every extraction object? (b) is the ungrounded case documented with a filter/recipe? (c) do examples print `(pos: start-end)` for grounded spans? LangExtract documents: extractions that cannot be located in source text get `char_interval = None`; grounded-only filter: `[e for e in result.extractions if e.char_interval]`. Medication examples show `char_interval.start_pos` / `end_pos` on every grounded entity. |
| **Audit method** | Conformance checklist + metric construct-validity audit (§5.1, §5.4) |
| **Scoring hook** | Feeds §6.1 dimension **extraction-quality/eval** and §6.2 hard-gate candidate: "LLM output used as gate without span provenance." |
| **Gaming vector** | Declaring "grounded" because text *looks* similar without byte/char interval verification. |
| **Anti-gaming guard** | Require automated tests or golden fixtures where at least one extraction is known-ungroundable and must surface `None`/equivalent; audit fails if ungrounded items are silently dropped or coerced to approximate spans. |
| **Evidence grade** | **A** (multiple Tier-2 official docs converge) |
| **Audit dimension** | Extraction quality & eval science; provenance/licensing |
| **Wrong for whisker if copied blindly** | LangExtract keeps ungrounded extractions in the result bag and leaves filtering to the caller. Whisker fidelity doctrine prefers **fail-not-partial** on advisory outputs that would influence operator trust; an audit should require explicit ungrounded counts in trace, not silent omission. |

**Sources:** [README — Grounding note](https://github.com/google/langextract/blob/main/README.md) (2026, main); [medication_examples.md](https://github.com/google/langextract/blob/main/docs/examples/medication_examples.md) (2026, main); [v1.2.0 release — ungrounded clarification](https://github.com/google/langextract/releases/tag/v1.2.0) (2026-03-22).

---

### Criterion 2.2 — Prompt/example alignment validation before inference

| Field | Value |
|---|---|
| **Criterion** | Few-shot examples are **validated against their own source text** before they enter the prompt pipeline, with configurable severity (`OFF`, `WARNING` default, `ERROR`) and optional strict mode. |
| **How to measure** | Check for `prompt_validation_level` / `prompt_validation_strict` (or equivalent) in API docs and release notes; confirm default is not `OFF`. LangExtract v1.0.9 added prompt alignment validation with three modes. |
| **Audit method** | Conformance checklist (§5.1) |
| **Scoring hook** | Feeds §6.1 **documentation/operator-UX** and **adversarial-robustness** (prevents example-text leakage into live documents). |
| **Gaming vector** | Shipping examples that are paraphrased or out-of-order while claiming "few-shot guided" extraction. |
| **Anti-gaming guard** | CI or preflight step that runs example validation at `ERROR` on the shipped example corpus; release blocked on misaligned gold examples. |
| **Evidence grade** | **B** (single Tier-2 release note + README cross-reference) |
| **Audit dimension** | Extraction quality & eval; documentation & operator UX |
| **Wrong for whisker if copied blindly** | Validation warns by default; whisker's deterministic gate may need **ERROR** (or hard fail) for production calibration fixtures, not WARNING-only. |

**Sources:** [v1.0.9 release notes](https://github.com/google/langextract/releases/tag/v1.0.9) (2025-08-31); [README — Prompt alignment note](https://github.com/google/langextract/blob/main/README.md) (2026, main).

---

### Criterion 2.3 — Configurable alignment stage with explicit resolver parameters

| Field | Value |
|---|---|
| **Criterion** | Text-to-span alignment is a **separate, tunable stage** exposed via documented `resolver_params` / alignment kwargs (exact match, optional fuzzy LCS DP, coverage/density gates), not an undocumented post-processing hack. |
| **How to measure** | Verify public API exposes alignment configuration; release notes document algorithm changes (v1.3.0 replaced difflib fuzzy aligner with LCS DP; v1.1.0 added alignment parameter support via `resolver_params`). Confirm alignment settings are validated (unknown keys raise typed errors). |
| **Audit method** | Comparative benchmarking + reproducibility replay (§5.3, §5.8) |
| **Scoring hook** | Feeds §6.1 **scoring/calibration** and §6.4 anti-gaming (alignment thresholds must be named constants, not magic defaults). |
| **Gaming vector** | Inflating recall by accepting weak partial fuzzy matches without density/coverage gates. |
| **Anti-gaming guard** | Publish default alignment thresholds; regression tests on documents where fuzzy match must **reject** (alignment returns ungrounded). |
| **Evidence grade** | **A** (release notes + API surface in extraction entrypoint) |
| **Audit dimension** | Extraction quality & eval; determinism/reproducibility |
| **Wrong for whisker if copied blindly** | LangExtract optimizes alignment for **recall on literary/clinical NER**, including fuzzy acceptance. Whisker deterministic spans for WG21 papers may require **exact or stricter** alignment for gate metrics; fuzzy paths belong only in advisory lane with labeled operating points. |

**Sources:** [v1.3.0 release](https://github.com/google/langextract/releases/tag/v1.3.0) (2026-04-29); [v1.1.0 release](https://github.com/google/langextract/releases/tag/v1.1.0) (2025-11-14); [extraction.py alignment kwargs](https://github.com/google/langextract/blob/main/langextract/extraction.py) (2026, main).

---

### Criterion 2.4 — Portable eval artifacts (JSONL) + human review visualization

| Field | Value |
|---|---|
| **Criterion** | Extraction outputs serialize to a **line-oriented, replayable format** (JSONL) with a bundled **human review surface** (interactive HTML visualization) that rehydrates spans in original context. |
| **How to measure** | Confirm `save_annotated_documents` → JSONL → `visualize()` round-trip is documented with runnable examples; longer-text example reports entity counts and saves `romeo_juliet_extractions.jsonl` + HTML. |
| **Audit method** | Documentation-completeness audit + comparative benchmarking (§5.9, §5.3) |
| **Scoring hook** | Feeds §6.1 **observability/failure** and **documentation/operator-UX**; supports §6.6 score uncertainty (human adjudication sample). |
| **Gaming vector** | "Has visualization" that only renders aggregate counts, not span-linked highlights. |
| **Anti-gaming guard** | Spot-check: randomly sample N extractions in JSONL and verify HTML highlights match `char_interval` substrings in source. |
| **Evidence grade** | **A** |
| **Audit dimension** | Extraction quality & eval; observability; documentation & operator UX |
| **Wrong for whisker if copied blindly** | HTML viz is excellent for **exploratory** LLM extraction; whisker's CI contract may need **text diff / golden markdown** artifacts instead of animated HTML for deterministic gates. Port the *provenance-linked review* pattern, not the widget choice. |

**Sources:** [README — Visualize section](https://github.com/google/langextract/blob/main/README.md) (2026, main); [longer_text_example.md](https://github.com/google/langextract/blob/main/docs/examples/longer_text_example.md) (2026, main).

---

### Criterion 2.5 — Documented end-to-end eval narrative with quantitative sample output

| Field | Value |
|---|---|
| **Criterion** | Official examples include **full-corpus runs** with stated input size, extraction counts, and breakdown by entity type — not only toy one-liners. |
| **How to measure** | At least one maintained example doc reports: source character/word count, number of extractions, class histogram, and parameters used (`extraction_passes`, `max_workers`, `max_char_buffer`). LangExtract Romeo & Juliet example: 147,843 characters → 4,088 entities with class percentages. |
| **Audit method** | Benchmarking methodology + maturity model (§5.3, §5.2) |
| **Scoring hook** | Feeds §6.1 **benchmarking/scoring calibration**; informs §6.6 uncertainty bands (example run variance not hidden). |
| **Gaming vector** | Cherry-picked micro-examples without scale parameters or cost/rate-limit warnings. |
| **Anti-gaming guard** | Require examples to disclose model ID, pass count, concurrency, and known API cost/rate-limit caveats (LangExtract longer-text example includes Tier-2 quota and pricing warning). |
| **Evidence grade** | **B** |
| **Audit dimension** | Benchmarking & eval science; documentation & operator UX |
| **Wrong for whisker if copied blindly** | LangExtract optimizes for **recall** via `extraction_passes=3` and `max_workers=20` — inherently nondeterministic and cloud-cost sensitive. Whisker audit should treat multi-pass stochastic recall boosting as **advisory-lane only**, never deterministic gate path. |

**Sources:** [longer_text_example.md](https://github.com/google/langextract/blob/main/docs/examples/longer_text_example.md) (2026, main).

---

### Criterion 2.6 — PyPA-modern packaging with typed surface and optional extras

| Field | Value |
|---|---|
| **Criterion** | Package ships via **`pyproject.toml`** (PEP 621), declares `requires-python`, Apache-2.0 license, **`py.typed`**, optional dependency groups (`[dev]`, `[test]`, `[openai]`), and entry points for provider plugins. |
| **How to measure** | Inspect PyPI metadata and repo `pyproject.toml`: version alignment (1.6.0), extras install paths (`pip install -e ".[test]"`), `[project.entry-points."langextract.providers"]` registry, import-linter contracts forbidding core↔provider cycles. |
| **Audit method** | Conformance checklist against PyPA packaging bar (§5.1) |
| **Scoring hook** | Feeds §6.1 **release-readiness** and **modularity/boundaries** |
| **Gaming vector** | Declaring optional LLM backends as core deps, bloating deterministic installs. |
| **Anti-gaming guard** | Verify core wheel/install size and that cloud SDKs (e.g. `google-genai`) are justified; audit notes LangExtract **does** bundle Gemini client in core — a negative exemplar for model-sovereign minimal core. |
| **Evidence grade** | **A** |
| **Audit dimension** | Release-readiness; modularity & package boundaries; dependency & supply chain |
| **Wrong for whisker if copied blindly** | LangExtract core depends on `google-genai` and defaults docs to Gemini API keys. Whisker must keep cloud SDKs **optional** per model-sovereignty invariant; use LangExtract's *extras/entry-point pattern*, not its default dependency graph. |

**Sources:** [pyproject.toml](https://github.com/google/langextract/blob/main/pyproject.toml) (v1.6.0, 2026); [PyPI langextract 1.6.0](https://pypi.org/project/langextract/1.6.0/) (2026-07-02).

---

### Criterion 2.7 — Tiered CI matrix: unit, lint, live API, containerized local-model integration

| Field | Value |
|---|---|
| **Criterion** | CI runs **multi-Python matrix tests**, lint/format gates, **opt-in live API tests** (skipped gracefully without secrets), **change-scoped** Ollama Docker integration, and **provider plugin smoke** jobs. |
| **How to measure** | Map `.github/workflows/ci.yaml` jobs: `test` matrix 3.10–3.12 + tox; `live-api-tests` on push/internal PR; `ollama-integration-test` gated on Ollama-related diffs with Docker `ollama/ollama` + `gemma2:2b`; `plugin-integration-test` gated on provider changes; signed-release tags on GitHub releases. |
| **Audit method** | CI/CD maturity scoring (§5.1 maturity model) |
| **Scoring hook** | Feeds §6.1 **release-readiness** and §6.2 gate: "no CI" / "no integration path for self-hosted backend." |
| **Gaming vector** | Unit tests only; live-model paths never exercised in CI. |
| **Anti-gaming guard** | Require at least one job that runs real inference (LangExtract: Ollama container + optional live API) or documented skip with explicit notice — not silent absence. |
| **Evidence grade** | **A** |
| **Audit dimension** | Release-readiness; observability/failure handling |
| **Wrong for whisker if copied blindly** | LangExtract live tests depend on **maintainer secrets** for Gemini/OpenAI; fork PR testing uses `pull_request_target` + pinned SHA (high ceremony). Whisker should prefer **self-hosted vLLM fixtures** under operator control, not cloud API keys, for reproducible CI. |

**Sources:** [ci.yaml](https://github.com/google/langextract/blob/main/.github/workflows/ci.yaml) (2026, main); [CONTRIBUTING.md — Testing](https://github.com/google/langextract/blob/main/CONTRIBUTING.md) (2026, main).

---

### Criterion 2.8 — Provider plugin architecture for model backends (core vs community)

| Field | Value |
|---|---|
| **Criterion** | LLM backends are pluggable via **entry-point discovery**, router pattern, and documented third-party packages; core ships Gemini + Ollama, cloud/OpenAI as optional, vLLM/LiteLLM/llama.cpp as **community plugins** with registry table and safety disclaimer. |
| **How to measure** | Read `langextract/providers/README.md` and `COMMUNITY_PROVIDERS.md`: lazy plugin load, `LANGEXTRACT_DISABLE_PLUGINS`, import-linter forbids `core → providers` back-edges; community registry lists `langextract-vllm` with tracking issue. |
| **Audit method** | Modularity audit + provenance (§5.8 boundaries, §5.10) |
| **Scoring hook** | Feeds §6.1 **architecture/hybrid** and model-sovereignty sub-score |
| **Gaming vector** | Claiming "supports local models" while only documenting cloud quick-start. |
| **Anti-gaming guard** | Audit requires first-class doc path for at least one self-hosted backend (LangExtract: Ollama built-in + vLLM plugin registry); community plugins must link tracking issue + PyPI name. |
| **Evidence grade** | **A** |
| **Audit dimension** | Architecture & hybrid design; dependency/supply chain; release-readiness |
| **Wrong for whisker if copied blindly** | Community vLLM support is **external** and issue #414 reports low parse success on some self-hosted stacks — plugin registry ≠ production guarantee. Whisker audit should score **maintained first-party** self-hosted paths higher than community plugin listings. |

**Sources:** [providers/README.md](https://github.com/google/langextract/blob/main/langextract/providers/README.md) (2026, main); [COMMUNITY_PROVIDERS.md](https://github.com/google/langextract/blob/main/COMMUNITY_PROVIDERS.md) (2026, main); [Issue #236 vLLM plugin](https://github.com/google/langextract/issues/236) (2025-09-10, open tracking).

---

### Criterion 2.9 — Fail-soft chunk parsing vs fail-closed extraction products

| Field | Value |
|---|---|
| **Criterion** | Document and default behavior for **partial document success** when individual chunks fail to parse: LangExtract defaults `suppress_parse_errors=True` in `extract()` so one bad chunk does not abort the document (v1.2.0). |
| **How to measure** | Read release notes and API defaults; check whether callers must opt in to strict failure. |
| **Audit method** | Observability/fault-injection audit (§5.11) |
| **Scoring hook** | Feeds §6.2 **hard gate** design: partial LLM extraction acceptable or not. |
| **Gaming vector** | High headline success rate with silently skipped chunks. |
| **Anti-gaming guard** | Require trace/logging of suppressed parse errors with chunk index (LangExtract sanitizes logs to exclude raw chunk text — good for privacy, but audit must still count failures). |
| **Evidence grade** | **B** |
| **Audit dimension** | Observability/failure handling; hybrid architecture |
| **Wrong for whisker if copied blindly** | **Fail-soft is opposite of whisker fidelity.** LangExtract prioritizes throughput/recall for exploratory extraction; whisker must **fail the paper** when a critical advisory step returns partial schema. Treat this as a **negative exemplar** for gate behavior, positive only for non-gating telemetry. |

**Sources:** [v1.2.0 release](https://github.com/google/langextract/releases/tag/v1.2.0) (2026-03-22).

---

### Criterion 2.10 — Licensing, attribution, and citation hygiene

| Field | Value |
|---|---|
| **Criterion** | Apache-2.0 LICENSE in repo; PyPI declares `Apache-2.0`; README disclaimer ("not an officially supported Google product"); Zenodo DOI for academic citation; Google CLA for contributors; health-domain extra terms (HAI-DEF) called out when relevant. |
| **How to measure** | Verify LICENSE file, PyPI `license_expression`, README disclaimer block, DOI badge, CONTRIBUTING CLA requirement; medication docs cite ML4H paper for method provenance. |
| **Audit method** | Provenance/license conformance audit (§5.10) |
| **Scoring hook** | Feeds §6.2 hard gate on **licensing/attribution violation** |
| **Gaming vector** | Missing NOTICE for bundled models/data in examples. |
| **Anti-gaming guard** | SPDX/license field in package metadata + explicit "not production / not medical advice" domain disclaimers where examples touch regulated text. |
| **Evidence grade** | **A** (license + DOI + peer-reviewed citation chain) |
| **Audit dimension** | Provenance/licensing/fork hygiene; documentation |
| **Wrong for whisker if copied blindly** | HAI-DEF health terms do not apply to WG21 papers, but the **pattern** (domain-specific disclaimer + separate terms link) is transferable for standards-body corpus usage policies. |

**Sources:** [LICENSE](https://github.com/google/langextract/blob/main/LICENSE) (Apache-2.0); [PyPI 1.6.0 metadata](https://pypi.org/project/langextract/1.6.0/) (2026-07-02); [README disclaimer + DOI](https://github.com/google/langextract/blob/main/README.md) (2026, main); [medication_examples.md — ML4H citation](https://github.com/google/langextract/blob/main/docs/examples/medication_examples.md) (2026, main); Goel et al., ML4H 2023, [arXiv:2312.02296](https://arxiv.org/abs/2312.02296).

---

### Criterion 2.11 — Security defaults for untrusted input fetch

| Field | Value |
|---|---|
| **Criterion** | Untrusted URL auto-fetch in input text is **opt-in**, not default (v1.3.0 security fix). |
| **How to measure** | Confirm release note: URLs in input no longer auto-fetched unless explicit flag enabled. |
| **Audit method** | Adversarial/red-team methodology (§5.6) |
| **Scoring hook** | Feeds §6.2 security hard gate |
| **Gaming vector** | Convenience URL ingestion opening SSRF/data-exfil paths in batch workers. |
| **Anti-gaming guard** | Default-deny network fetch from document text; explicit operator flag + allowlist documented. |
| **Evidence grade** | **B** |
| **Audit dimension** | Security & prompt-injection defense |
| **Wrong for whisker if copied blindly** | Pattern aligns with whisker's untrusted-paper treatment; no conflict. |

**Sources:** [v1.3.0 release — Security](https://github.com/google/langextract/releases/tag/v1.3.0) (2026-04-29).

---

## 3. External benchmark / exemplar bar

LangExtract sets a **high bar** on five axes an extraction-QA audit should treat as best-in-class among LLM extraction libraries (2025–2026 vintage):

| Axis | LangExtract bar (observed) | Maturity level (0–4) |
|---|---|---|
| **Grounding provenance** | First-class `char_interval` + documented ungrounded sentinel + visualization | **4** — explicit, testable, operator-facing |
| **Eval transparency** | Full-corpus example with counts, JSONL replay, HTML review | **3** — strong narrative; not a formal benchmark suite |
| **Release engineering** | PyPI 16 releases in ~12 months to v1.6.0; signed tags; CI matrix + conditional integration | **4** |
| **Packaging/modularity** | pyproject extras, entry points, import-linter contracts | **3** — strong patterns; cloud SDK in core weakens sovereignty |
| **Self-hosted path** | Ollama first-class + community vLLM registry; cloud default in docs | **2** — documented but immature vs cloud happy path |

**Deliberate gaps (do not cargo-cult):**

- **Cloud-first defaults** (Gemini API key in quick-start, `google-genai` core dep).
- **Fail-soft** chunk parsing (`suppress_parse_errors=True`).
- **Stochastic recall** (`extraction_passes`, parallel `max_workers`) without determinism containment.
- **Advisory filtering** left to caller for ungrounded spans (no built-in `require_grounding` in stable API per maintainer response on #209).

---

## 4. Recommended weight & hard gates

| Recommendation | Rationale |
|---|---|
| **Weight: medium (composite ~8–12%)** for "grounding provenance + eval artifact replay" sub-criteria | LangExtract is the clearest open exemplar for span-linked LLM extraction review; high teaching value, but domain mismatch (general NER vs WG21 conversion-QA). |
| **Weight: low (~3–5%)** for "HTML visualization" specifically | Pattern valuable; implementation not required for whisker CI. |
| **Hard gate: NO** on "match LangExtract packaging deps" | Negative exemplar on core cloud deps; gate would misfire. |
| **Hard gate: YES (candidate)** — *Any LLM output presented to operators must carry grounding status or explicit `not_found`/equivalent* | LangExtract's `char_interval`/`None` split is the portable gate concept; whisker should meet or exceed it under fidelity rules. |
| **Hard gate: YES (candidate)** — *Default network fetch from document content must be deny* | v1.3.0 precedent directly supports whisker untrusted-input posture. |

Evidence for weights is **Tier A/B** across criteria 2.1, 2.4, 2.6, 2.7, 2.10; contested areas (self-hosted reliability) downgraded per §6.5 (community plugin + open issue, not maintainer SLA).

---

## 5. Sources

### Tier 1 — Authoritative / primary

| # | Source | URL | Date/version |
|---|---|---|---|
| T1-1 | Goel et al., "LLMs Accelerate Annotation for Medical Information Extraction," ML4H / PMLR (arXiv:2312.02296) | https://arxiv.org/abs/2312.02296 | 2023 |
| T1-2 | Apache License 2.0 (LangExtract LICENSE) | https://github.com/google/langextract/blob/main/LICENSE | 2004 spec; file 2025–2026 |

### Tier 2 — Strong secondary (official project)

| # | Source | URL | Date/version |
|---|---|---|---|
| T2-1 | LangExtract README (grounding, packaging, testing, disclaimer) | https://github.com/google/langextract/blob/main/README.md | main, accessed 2026-07-18 |
| T2-2 | `pyproject.toml` v1.6.0 | https://github.com/google/langextract/blob/main/pyproject.toml | 2026-07-02 |
| T2-3 | PyPI project metadata v1.6.0 | https://pypi.org/project/langextract/1.6.0/ | 2026-07-02 |
| T2-4 | GitHub Releases (v1.0.9, v1.2.0, v1.3.0, v1.6.0) | https://github.com/google/langextract/releases | 2025-08-31 – 2026-07-02 |
| T2-5 | CI workflow `ci.yaml` | https://github.com/google/langextract/blob/main/.github/workflows/ci.yaml | main, accessed 2026-07-18 |
| T2-6 | CONTRIBUTING.md | https://github.com/google/langextract/blob/main/CONTRIBUTING.md | main, accessed 2026-07-18 |
| T2-7 | Provider system README | https://github.com/google/langextract/blob/main/langextract/providers/README.md | main, accessed 2026-07-18 |
| T2-8 | COMMUNITY_PROVIDERS.md (vLLM, LiteLLM, etc.) | https://github.com/google/langextract/blob/main/COMMUNITY_PROVIDERS.md | main, accessed 2026-07-18 |
| T2-9 | Long-document eval example | https://github.com/google/langextract/blob/main/docs/examples/longer_text_example.md | main, accessed 2026-07-18 |
| T2-10 | Medication / grounding example | https://github.com/google/langextract/blob/main/docs/examples/medication_examples.md | main, accessed 2026-07-18 |
| T2-11 | Zenodo DOI 10.5281/zenodo.17015089 | https://doi.org/10.5281/zenodo.17015089 | per README badge |

### Tier 3 — Contextual (pointer only)

| # | Source | URL | Note |
|---|---|---|---|
| T3-1 | Issue #209 (example-text leakage / grounding filter) | https://github.com/google/langextract/issues/209 | Corroborates README; not sole basis for criteria |

**Distinct Tier 1–2 primary sources used:** **13** (T1-1, T1-2, T2-1 through T2-11).

---

## 6. Overlap statement

- **Did not inspect** whisker production code (`packages/whisker/src/**`) or cite whisker `file:line`.
- **Did not clone, fork, or copy** LangExtract source into this repo; all evidence from public docs, release notes, PyPI, and read-only GitHub URLs.
- **Did not re-litigate** the prior `langextract/` swarm adoption verdict (algorithm/library adopt-partially). This report operates one level up: **engineering, eval, grounding-provenance, packaging, and release maturity** as audit rubric inputs.
- **Did not duplicate** `redteam/` converter defect reports; LangExtract is treated as an **extraction-engineering exemplar**, not a PDF/HTML converter under red-team.
- **Boundary held:** practices and criteria only; no vendored code, no library re-adoption recommendation.

---

## Summary table — Transferable practices → audit dimensions

| Practice | Informs dimension | Whisker fit |
|---|---|---|
| `char_interval` / ungrounded sentinel | Extraction quality, provenance | **Adopt pattern** (stricter fail posture) |
| Prompt example alignment validation | Eval science, doc UX | **Adopt** (likely ERROR for goldens) |
| JSONL + provenance-linked review UI | Observability, eval | **Adapt** (golden diff > HTML for CI) |
| pyproject extras + entry-point providers | Release, modularity | **Adopt pattern** (no cloud in core) |
| CI: matrix + Ollama Docker + live API | Release, test maturity | **Adapt** (self-hosted vLLM, not Gemini secrets) |
| Fail-soft chunk parse default | Failure handling | **Reject for gates** (negative exemplar) |
| Multi-pass parallel extraction | Determinism | **Advisory lane only** |
| URL fetch opt-in default | Security | **Adopt** |

**Strongest transferable practice:** **Explicit grounding provenance on every extraction** — `char_interval` when aligned to source text, `None` when not, documented operator filter, alignment stage tunable via `resolver_params`, and eval artifacts (JSONL + visualization) that rehydrate spans for human verification. This is the single practice most directly portable to a professional extraction-QA audit rubric without importing LangExtract's cloud defaults or fail-soft semantics.
