# Cross-Repo QA Research: How 28 Document-Conversion Projects Ensure Quality

Synthesis of a 28-repo deep-read swarm (June 2026) commissioned to harden
`whisker` into a regression gate for `tomd`. Each repo was cloned (pinned SHAs in
`whisker-research/MANIFEST.txt`) and read against a fixed rubric: test taxonomy,
fixtures/goldens, metrics, CI gating, calibration, and portability to whisker.
The raw per-repo reports live in `whisker-research/reports/<repo>.md`.

The driving question: **when tomd changes, how do we prove no conversion quality
was lost?**

## TL;DR (the field's verdict)

1. **Golden-file regression with an explicit refresh ritual is the universal
   backbone.** ~18 of 28 repos gate on committed expected outputs compared by
   exact (or near-exact) equality, refreshed by a deliberate, human-reviewed
   command (`--accept`, `--bless`, `-update`, `OVERWRITE_FIXTURES=true`,
   `DOCLING_GEN_TEST_DATA=1`). whisker has none of this. **This is gap #1.**
2. **Almost nobody calibrates thresholds.** Floors are hand-set engineering
   judgment (marker ≥90, opendataloader NID≥0.88, html2text exact). whisker's
   provisional 0.85/0.95 edges are in good company, but a real `calibrate`
   workflow would make whisker *better than the field*, not just even.
3. **Aggregate means hide per-item regressions.** The repos that take regression
   seriously (unstructured, opendataloader, tabula-java) diff **per-document /
   per-axis**, not a corpus mean. whisker's `bench --baseline` only checks mean
   `overall`: a single paper can crater while the mean holds. **This is gap #2,
   and it is exactly the "kein Kollateralschaden" failure mode.**
4. **Separate the axes; never average a regression away.** nougat (Text/Math/
   Tables), opendataloader (per-axis null eligibility), olmocr (8 assertion
   classes) all refuse to collapse a table collapse into a healthy overall.

## The 12 practices, ranked by impact on the "no collateral damage" goal

### 1. Per-item metrics-as-snapshots regression gate (HIGHEST)
Run the scorer over a fixed corpus, write **per-document** results to a committed
baseline, fail CI on **any** per-item regression, refresh via an explicit ritual.

- **unstructured**: writes per-doc metric TSV trees, `check-diff-evaluation-metrics.sh` fails on any diff; re-baseline via `OVERWRITE_FIXTURES=true`.
- **opendataloader-pdf**: `evaluator.py` + `thresholds.json` (NID≥0.88, TEDS≥0.47, MHS≥0.72) with `check_regression()` and a 0.02 tolerance, **per axis**.
- **tabula-java**: 67-doc ICDAR corpus with per-case `expectedFailure` baselines: known-bad cases stay in the gate, but a case getting *worse* fails; improving past the baseline forces an explicit baseline bump (monotonic guard).
- **marker**: `verify_scores.py` absolute floors (heuristic ≥90, TEDS ≥0.7) on a versioned micro-corpus as a backstop.
- **docling**: ~494 committed goldens, 2-reviewer Mergify governance on `tests/data/**`.

> Maps to whisker Phase 4a. whisker already writes `report.json` per run; the gate
> is "diff this run's per-paper verdict + per-axis metrics against a committed
> baseline, fail on regression beyond slack."

### 2. Golden corpus + explicit `--accept`/`--update` refresh ritual
The committed expected output is the contract; a deliberate command rewrites it,
and the diff is reviewed and committed alongside the code change.

- **pandoc**: ~1,760 command tests + 255 `.native` AST goldens; `make test TESTARGS='--accept'` splices expected output back into fixtures; CI never runs `--accept`.
- **html-to-markdown-go**: goldie `-update`; 14 byte-exact `.in.html`/`.out.md` pairs.
- **html-to-markdown-py**: 116 byte-exact `.snap` (29 fixtures x 4 option permutations), `htmbench oracle --bless`.
- **html2text**: 74 auto-discovered `.html`/`.md` pairs, exact compare, three entry points (lib/CLI/API) per fixture.
- **turndown**: 147 inline HTML case-table goldens, exact string match.
- **PyMuPDF**: version-keyed goldens (parallel expected outputs per MuPDF version) so a dependency bump can't silently pass against the wrong baseline.

> Maps to whisker Phase 4a (the guard's `--update` flag) and Phase 4c (a small
> committed golden markdown corpus).

### 3. Required/forbidden substring anchors (deterministic, format-robust)
Assert specific text MUST and MUST NOT appear, robust to formatting churn.

- **markitdown**: `must_include`/`must_not_include` per format vector; reading-order via **ordered `str.find()` chains** (section A must precede section B).
- **firecrawl**: ~124 `markdown.toContain(...)` anchors per conversion path.
- **olmocr**: JSONL `present`/`absent`/`order` fact assertions with explicit failure messages; explicitly rejects whole-page edit distance as the primary metric.
- **MinerU / marker**: substring hit-rate and rapidfuzz `partial_ratio` per GT block.

> Recommended next tier for whisker: a per-paper "facts" file (anchors + section
> order) as a hard, localized check beneath the fuzzy metrics.

### 4. Modality-stratified scoring (don't average a regression away)
- **nougat**: `metrics.py` splits Text / Math / Tables, reports char-NED + set-F1 **per stratum**.
- **opendataloader**: per-axis null eligibility (null when GT lacks that axis), excluded from means with published counts, so a table regression can't hide behind a strong reading-order score.

> Maps to whisker Phase 4a: diff nid/teds/mhs/unigram **separately**, never only `overall`.

### 5. Per-axis absolute floors on a versioned micro-corpus (CI backstop)
marker (`verify_scores.py`), opendataloader (`thresholds.json`), MinerU (coverage floor), surya (tiered CI). A floor catches catastrophic drops even when the baseline is stale or missing.

### 6. Intrinsic, reference-free confidence score
- **camelot**: `confidence = (accuracy/100) x (1 - whitespace/100)`, where accuracy comes from text-to-cell assignment geometry and whitespace is % empty cells. **No ground truth needed.**

> whisker's reference-free path is gates + unigram coverage; camelot shows an
> intrinsic *structural* confidence (e.g. table raggedness) whisker could add.

### 7. Property / round-trip / parity invariants
- **pandoc**: QuickCheck `read . write == id`.
- **html-to-markdown-go**: optional `HTML->MD->HTML->MD` idempotence.
- **mdream**: string-vs-stream parity (`stream == batch` after `trimEnd()`).
- **pdfplumber**: domain invariants (`colsum == total * 2` on a known report).

> Maps to whisker Phase 4c: metric invariants (identity=1.0, symmetry, bounds,
> monotonicity) are cheap and catch metric-code regressions directly.

### 8. Pre-score normalization layer
- **Dolphin**: LaTeX canonicalization, repeated-token truncation, table-HTML stripping *before* scoring, so formatting-only diffs don't fire as regressions.
- whisker already has `normalized_text` (OmniDocBench `clean_string` + LaTeX fold); confirmed sound, can be hardened.

### 9. Meta-tests on the gate logic itself
- **olmocr**: 148 of ~430 tests test the *assertion engine*, not documents.

> Maps to whisker Phase 4c: unit-test `_decide`, gates, and the new guard's
> regression logic on synthetic inputs (whisker already does some of this).

### 10. Per-stage intermediate goldens (localize the regression)
pdf-to-markdown (12-stage pipeline), img2table (contours->cells->tables staged goldens), MinerU (typed per-block asserts on `content_list.json`). Higher effort, tomd-side; pin a regression to a specific transformation.

### 11. Multi-tier field matching
- **grobid**: strict / soft / Levenshtein@0.8 / Ratcliff@0.95, field-level micro/macro P/R/F1, versioned baseline snapshots in `doc/benchmarks/`.

### 12. CI ops hygiene
surya (tiered fast-smoke vs heavy benchmark jobs), docling (split ML vs core tests; golden changes need 2 reviewers), PyMuPDF (version-keyed goldens).

## Where whisker already leads the field

- **Real metric math**: verbatim PubTabNet/OmniDocBench TEDS, Zhang-Shasha MHS, block-matched NID. Most repos (markitdown, MinerU, surya, Dolphin, PDF-Extract-Kit) have *no* in-repo metrics and cite external benchmarks only.
- **Order-invariant content gate**: whisker's unigram-coverage floor correctly separates content from reading order, exactly the separation nougat/docling/OmniDocBench document. Many repos conflate them.
- **Advisory cross-converter oracle**: whisker's markitdown agreement-as-confidence (never hard-fail) matches the literature ("agreement != correctness"); node-html-markdown shows the harness shape but doesn't even diff output.
- **CI exit-code contract** (0/1/3/5) and deterministic, no-LLM design: ahead of most.

The gap is **not** measurement sophistication. It is **regression plumbing**:
committed per-paper baselines, per-axis diffing, a refresh ritual, and calibration.

## What this means for the build (Phase 4)

- **4a (guard)** = practices #1 + #2 + #4 + #5 fused: a `whisker guard` that scores
  a fixed corpus, diffs per-paper verdict transitions and per-axis metric drops
  against a committed baseline JSON, fails on regression (CI exit codes), and
  refreshes via an explicit `--update` ritual.
- **4b (calibrate)** = the field's blind spot turned into whisker's advantage: fit
  the coverage/advisory edges on a labeled set, record TPR/FPR/precision.
- **4c (tests)** = practices #7 + #9: metric invariants (identity/symmetry/bounds/
  monotonicity), more gate fixtures, guard-logic meta-tests.
- **Recommended follow-on** (not in this pass): practice #3 per-paper anchor/
  section-order facts, and practice #6 intrinsic table-structure confidence.
