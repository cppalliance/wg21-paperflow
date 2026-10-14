# 23 - Benchmark and Holdout Designer

**Verdict:** usable-with-conditions — a 12-paper / 68-anchor WG21 holdout (anchors only, no `<pid>.gt.md`) is the minimum credible calibration set for bidirectional quote verification; olmOCR-bench supplies the fact schema and macro strata rollup, opendataloader-bench confirms document-level metrics are necessary but insufficient for evidence precision.
**Confidence:** high

## Findings

- [CRITICAL] **Minimum holdout size: 12 papers, 68 bidirectional evidence anchors (realistic, not olmOCR-scale).** Evidence: `00-baseline.md:14-24` labels 20 tapetum quotes across 4 PR-replay papers at 40% candidate-absence precision (8/20 genuinely absent); existing comprehension corpus is 5 papers / 37 facts (`whisker/CLAUDE.md` corpus section); olmOCR-bench runs 7,010 tests over 1,403 pages (`05-web.md:126-128`) — overkill for whisker calibration. Power sketch: to move a point estimate from 0.40 → ≥0.85 with ±0.10 margin at 95% confidence on absent-positive labels needs ~35–45 verified-absent anchors; adding ~25 present/ambiguous controls for FP and abstention rates yields **48 holdout anchors + 20 dev anchors = 68 total**. Authoring cost: ~4 anchors/paper × 12 papers ≈ 2–3 human days (olmOCR used GPT-4o draft + human review per `olmocr/bench/README.md:218`; whisker `corpus_tools.py` `draft_facts_scaffold` is the local equivalent). Impact: shippable calibration without building a second olmOCR corpus.

- [CRITICAL] **Label schema: `<pid>.evidence.jsonl` (anchor-only, no golden markdown).** Evidence: olmOCR `BasePDFTest` binds `(pdf, page, id, type, max_diffs)` (`olmocr/bench/tests.py:83-112`); whisker facts already gate on `checked: verified` (`facts.py:25-28`); opendataloader-bench requires hand-labeled `ground-truth/markdown/` per document (`opendataloader-bench-tmp/README.md:46`, `evaluator.py:30-31`) — correct for Lane 2, too heavy for quote-evidence. Proposed record (one JSON object per line):

  ```json
  {
    "id": "pr293-constexpr-1",
    "pid": "P293R0",
    "page": 3,
    "quote": "constexpr int example = 0;",
    "axis": "code",
    "source_label": "present",
    "candidate_label": "absent",
    "sanction": null,
    "surface": "raw",
    "max_diffs": 2,
    "stratum": "code-absent",
    "checked": "verified",
    "provenance": "source:pdf_textlayer:verbatim"
  }
  ```

  Required fields: `id`, `pid`, `page`, `quote` (5–25 words, verbatim in source for `source_label: present`), `source_label` (`present` | `absent`), `candidate_label` (`present` | `absent` | `ambiguous`), `stratum`, `checked` (`verified` only gates). Optional: `axis` (maps to `FidelityAxis` in `models.py:30-38`), `sanction` (`front_matter`, `toc_removed`, `dehyphenation`, `markup_equivalence`, `furniture`, `reordered`), `surface` (`raw` | `normalized`), `max_diffs`, `first_n`/`last_n` (olmOCR header/footer zones, `tests.py:160-165`). **No `<pid>.gt.md`**: each anchor is a self-contained quote + bilateral label; structural eligibility uses existing Lane 2 null-eligibility (skip `table` stratum when paper has no tables, mirroring `evaluator.py:107-113`).

- [HIGH] **Positive / negative / ambiguous examples (concrete WG21 instances).** Evidence: `00-baseline.md:16-19` PR replay outcomes; `02-candidate-absence.md:33-39` false-pass/fail classes.

  | Class | `candidate_label` | Example anchor | Source |
  | --- | --- | --- | --- |
  | **Positive (verified missing)** | `absent` | PR #293: five `constexpr` declarations in PDF text layer, not in markdown | `00-baseline.md:19` |
  | **Positive (verified missing)** | `absent` | PR #284: 3/5 quotes genuinely absent (prose blocks) | `00-baseline.md:16` |
  | **Negative (false missing)** | `present` | PR #285: quoted body prose already in markdown (0/5 absent) | `00-baseline.md:17` |
  | **Negative (false missing)** | `present` | PR #290: date lines already present, some duplicated in YAML + body | `00-baseline.md:18` |
  | **Negative (false missing)** | `present` | PR #284: 2/5 quotes already present | `00-baseline.md:16` |
  | **Ambiguous (abstain)** | `ambiguous` | Dehyphenated line break: PDF `"poly-\nmorphic"` vs MD `"polymorphic"` | `pdf_judge.py:96-108`, `02-candidate-absence.md:29` |
  | **Ambiguous (abstain)** | `ambiguous` | Front-matter key migrated to YAML (`Document Number` absent from body by contract) | `P4182R0.facts.jsonl` `docnumber-label-consumed` |
  | **Ambiguous (abstain)** | `ambiguous` | TOC line removed from body but structurally similar heading remains | `gates.py` `no_toc_leak`, `03-bidirectional-design.md:64-65` |
  | **Ambiguous (abstain)** | `ambiguous` | Reading-order reorder: both strings present, positions swapped | olmOCR `TextOrderTest` (`tests.py:186-226`) tolerates; evidence lane must abstain not fail |

  Target mix per 48 holdout anchors: **12 verified-absent**, **20 present (negative control)**, **16 ambiguous** — mirrors AttributionBench balanced FP/FN framing (`05-web.md:82-84`).

- [HIGH] **Hard negatives (must not false-clear to `verified_missing`).** Evidence: olmOCR `test_tests.py` `"max"` vs `"maximum"` substring trap (`10-olmocr-bench-analyst.md:26`); whisker table decoy exploit (`whisker/CLAUDE.md` Known gaps #1).

  1. **Boilerplate decoy**: repeated WG21 mailing footer phrase on wrong page/section — `fuzz.partial_ratio` matches decoy, true context absent (`tests.py:168-173`).
  2. **Substring-of-longer-present**: quote `"The committee"` embedded in a longer present sentence (`EVIDENCE_MIN_FUZZY_CHARS=20`, `constants.py:69-73`).
  3. **Duplicate date/front-matter**: PR #290 class — present twice (YAML + body); absence claim must refute.
  4. **Table cell collision**: same cell text in two tables; anchor needs `table_heading` disambiguator (`facts.py` / `EXAMPLE.facts.jsonl`).
  5. **Code-fence normalization**: `constexpr` spacing inside fence vs PDF whitespace (`03-bidirectional-design.md:72-74`).
  6. **Smart-quote / NFC fold**: PDF `"` vs MD `“` after `normalize_text` (`tests.py:74-78`).
  7. **Page-furniture absent label**: header page number should be `candidate_label: absent` with `sanction: furniture` — verifier must NOT promote to `verified_missing` evidence (sanctioned absence ≠ defect).

  Each hard-negative class needs ≥2 holdout anchors (14 of 48 slots reserved).

- [HIGH] **Metrics (evidence-only; separate from verdict agreement).** Evidence: `00-baseline.md:24` ("evidence precision, not verdict recall, is the target"); ALCE citation precision/recall split (`05-web.md:72-76`); olmOCR macro stratum rollup (`benchmark.py:44-45`, `380-388`).

  Per-quote (bidirectional verifier output vs `candidate_label`):

  | Metric | Definition | Baseline |
  | --- | --- | --- |
  | **Evidence precision** | TP(`verified_missing` ∧ label=`absent`) / all predicted `verified_missing` | 0.40 (`8/20` retained after source-only grounding overstates; true absent predictions unknown until candidate check) |
  | **Evidence recall** | TP / all label=`absent` | 1.0 on 8 genuine (if verifier keeps all 8) |
  | **False-missing rate** | predicted `verified_missing` ∧ label=`present` | 0.60 (12/20 replay) |
  | **Ambiguous abstention accuracy** | predicted `ambiguous` ∧ label=`ambiguous` / all label=`ambiguous` | n/a (unlabeled today) |
  | **Ambiguous leak rate** | predicted `verified_missing` ∧ label=`ambiguous` | must be 0 at ship |
  | **Source grounding recall** | source locate success / all anchors with `source_label: present` | 1.0 expected (current path) |

  Per-stratum macro-average (olmOCR pattern, not micro over all anchors): mean pass rate per `stratum` field, then mean of stratum means. Report bootstrap 95% CI per stratum (`olmocr/bench/utils.py:47-60`). **Do not** fold into opendataloader `overall_mean` (`evaluator.py:107-113`) — NID/TEDS/MHS are advisory eligibility screens only.

- [HIGH] **Splits (lock before tuning).** Evidence: `03-bidirectional-design.md:80-82` conditions flip on labeled replay; PR forced replay set `00-baseline.md:11-12`.

  | Split | Papers | Anchors | Use |
  | --- | --- | --- | --- |
  | **Dev / calibration** | 9 PR-replay PIDs (#282–#295) | 20 (replay quotes, relabeled with `candidate_label`) + 8 (new ambiguous/sanction anchors mined from same PDFs) = **28** | Threshold tuning (`CANDIDATE_AMBIGUOUS_BAND`, `max_diffs` scale) |
  | **Holdout** | 12 WG21 papers, zero overlap with dev PIDs, stratified 2/paper × 6 strata | **48** | Ship gate only; no parameter fitting |
  | **CI smoke** | 2 corpus members (e.g. P4182R0, P4185R0) | 8 | Regression guard in `test_evidence_holdout.py` (hermetic, anchor file only) |

  Strata (6, from whisker `corpus_tools.py` stratify + evidence-specific): `prose-absent`, `prose-present-fn`, `sanctioned-reformat`, `code-xref`, `table-cell`, `math-unicode`. Selection: `whisker corpus stratify` candidates with zero evidence coverage; prefer papers already in paperstore with PDF text layer. Lock holdout PIDs in `corpus/evidence-holdout.json` before first verifier commit.

- [HIGH] **Acceptance gates (verifier v1 ship).** Evidence: `02-candidate-absence.md:25` model boundary (≥90% precision, ≥87.5% recall on genuine absences); opendataloader regression tolerance 0.02 (`thresholds.json:7`).

  **Dev split (must pass before holdout evaluation):**
  - Evidence precision ≥ 0.90 on dev absent-labeled anchors (≥10/11 correct absent calls)
  - Recall on dev `candidate_label: absent` ≥ 0.875 (retain PR #293 5/5 + PR #284 3/3 minimum)
  - False-missing rate ≤ 0.10 on dev `present`-labeled (≤2/20 PR false-absent quotes promoted)

  **Holdout split (ship blocker):**
  - Evidence precision ≥ 0.85 (41/48 absent predictions if 12 absent labels; adjust for stratum prevalence)
  - False-missing rate ≤ 0.10 on `present`-labeled (≤2/20)
  - Ambiguous leak rate = 0 (no `verified_missing` when `candidate_label: ambiguous`)
  - Ambiguous abstention ≥ 0.90 on ambiguous-labeled (≥14/16)
  - Source grounding recall ≥ 0.95
  - Macro stratum mean ≥ 0.80 for each of 6 strata
  - Deterministic whisker `--gate pass` unchanged on holdout papers (evidence fix is advisory-only per `00-baseline.md:56-57`)

  Failure on holdout after dev pass → revise normalizer/sanction map, not holdout labels.

- [HIGH] **Replay protocol (deterministic, reproducible).** Evidence: tapetum fingerprint skip (`whisker/CLAUDE.md` tapetum section); olmOCR `process_test` page-scoped MD (`benchmark.py:93-116`); `27-determinism` lane serial constraint.

  1. **Pin environment**: record `SERVICES.toml` slot, model id, `_LANE_VERSION`, `schema_version` from sidecar (`pdf_judge.py:420`).
  2. **Stage inputs**: for each holdout PID, SHA-256 of `paper.md`, source PDF, and PDF text layer extract (`extract_textlayer`); store in `corpus/<pid>.evidence.manifest.json`.
  3. **Run tapetum**: `whisker-tapetum-llm <pid> --force` (or replay cached sidecar if fingerprints match).
  4. **Extract quotes**: collect `missing_content` + `grounded_evidence` from `whisker/llm/<pid>.whisker.tapetum.json`.
  5. **Score verifier** (library function, no LLM): for each quote, compute `source_status`, `candidate_status`, `entailment` per `03-bidirectional-design.md:28-35`; join to nearest holdout anchor by `(pid, normalized_quote)` with olmOCR length-relative threshold (`tests.py:167-168`).
  6. **Aggregate**: macro stratum means + bootstrap CI; write `research/llm-evidence-reliability/replay/<date>/metrics.json`.
  7. **Compare baseline**: rerun on archived pre-fix sidecars (nine-PR replay artifacts) to prove precision lift, not just holdout fit.
  8. **CI**: smoke split runs in hermetic test against committed anchors only (no pod, no `WG21_DATA_DIR`); full replay remains manual/out-of-band like `whisker-readback` (`whisker/CLAUDE.md`).

- [MED] **opendataloader-bench role: eligibility, not evidence labels.** Evidence: `opendataloader-bench-tmp/src/evaluator.py:25-27` (NID/TEDS/MHS only); `05-web.md:145-149` ("not sufficient for quote-level absence"). Use: a holdout paper with `teds: null` omits `table-cell` anchors; a paper with `nid < 0.85` on expected.md is ineligible for prose-absent strata (conversion too broken for quote-level signal). Thresholds from `thresholds.json` are advisory floors for corpus inclusion, not evidence gates.

- [MED] **Anchor authoring workflow (minimum process).** Evidence: olmOCR `checked: verified` stored but not enforced at runtime (`10-olmocr-bench-analyst.md:18`); whisker provenance discipline (`corpus/README.md:31-43`).

  1. Agent/human extracts quote from PDF text layer (PyMuPDF), not from tapetum output.
  2. Human confirms `candidate_label` against `paper.md` (and sanctioned behavior if applicable).
  3. `checked: draft` until step 2 complete; flip to `verified` only after source + candidate labels agree.
  4. Hard negatives explicitly tagged `"hard_negative": true` for metric slicing.
  5. Never derive `candidate_label` from tapetum quotes (circular).

- [LOW] **Do not import olmOCR math/table test classes into v1 holdout.** KaTeX render tests (`tests.py:561-608`) and `TableTest` neighbor graphs add Playwright/HTML-table dependencies beyond quote-evidence scope. v1 uses `facts.py`-compatible `table`/`math` anchor shapes only where already in whisker corpus style (`EXAMPLE.facts.jsonl`).

## False-pass hypothesis

Holdout includes only "easy" present-labeled prose negatives (PR #285 body text) and omits ambiguous/sanction classes. Verifier hits 0.90 precision on holdout by never seeing PR #290 duplicate-date or dehyphenation anchors; production still false-missing on sanctioned reformats. Mitigation: 16/48 ambiguous + 14/48 hard-negative slots are mandatory, not optional enrichment.

## False-fail hypothesis

Holdout over-weights PR #293-class code-absent anchors (12 slots) with `surface: raw` and `max_diffs: 0`. Verifier tuned on dev achieves recall but holdout rejects fuzzy-present code variants (spacing, fence wrapping), demoting real defects to `ambiguous` and missing recall gate. Mitigation: per-anchor `max_diffs` and `surface` in schema; code stratum uses `facts.py` `_present_within` tier (`02-candidate-absence.md:14`).

## What would change my mind

Measuring that 12 papers / 48 holdout anchors cannot stabilize bootstrap CI width below ±0.15 on evidence precision at the 0.85 operating point (i.e. fewer than ~30 effective absent-positive labels after stratification), forcing either a larger holdout or acceptance of wider ship gates — would revise the sample-size claim downward.
