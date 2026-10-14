# 12 - Longtail sweeper

**Verdict:** usable-with-conditions   (the sweep's main product is a strong negative result: 0 of 17 long-tail repos do LLM-based scoring, and only camelot ships an adoptable deterministic score-fusion pattern)
**Confidence:** high

## Findings

Sweep method: one keyword grep pass (`llm|gpt|openai|claude|judge|confidence|score|eval|benchmark`, case-insensitive) over every text file per repo, plus a look into each repo's eval/test/bench dirs. All paths relative to `packages/whisker/research/repos/`.

### Per-repo sweep table

| Repo | LLM scoring | Det. scoring | Most interesting mechanism (file:line) |
|---|---|---|---|
| camelot | no | **yes** | `Table.confidence` composite `(accuracy/100)*(1-whitespace/100)` at `camelot/camelot/core.py:682-705`; surfaced in `parsing_report` at `core.py:726-732`; dependency-free TEDS proxy `simple_teds` (difflib content ratio x shape penalty) at `camelot/bench/_metrics.py:24-33` |
| img2table | no | yes | structural row scoring for borderless table segmentation, `src/img2table/tables/borderless/sections/segmentation.py:75-93`; OCR `min_confidence` gate (`README.md:344`). LLMs mentioned only as an external alternative (`README.md:507`) |
| pdfplumber | no | no | nothing. Keyword hits are changelog/contributor noise (`pdfplumber/CHANGELOG.md:344`) |
| PyMuPDF | no | no | nothing. "LLM" appears only as marketing for pymupdf4llm (`PyMuPDF/README.md:38`) |
| pymupdf4llm | no | no | nothing. "llm" is in the package name only; CHANGES.md is bugfix log (`pymupdf4llm/CHANGES.md:18`) |
| tabula-java | no | no | nothing. Sole keyword hit is a test fixture string "evaluation" (`src/test/java/technology/tabula/TestBasicExtractor.java:25`) |
| html-to-markdown-go | no | no | speed-only Go microbenchmarks, e.g. `internal/textutils/consecutive_newlines_test.go:139` |
| html-to-markdown-py | no | **yes** | golden-oracle byte-equality snapshot harness: 4 deterministic permutations per fixture, `tools/benchmark-harness/src/oracle.rs:1-14,22-33`; 116 oracle snapshots + per-fixture byte-equality claimed at `CHANGELOG.md:349`; regression baseline `tools/benchmark-harness/baselines/baseline.json` + `guardrails.json` |
| html2text | no | no | nothing. Hits are CLI flag docs about underscores (`html2text/cli.py:147`) |
| markdownify | no | no | nothing. Hits are `UNDERSCORE` constants (`markdownify/__init__.py:59`) |
| node-html-markdown | no | no | speed-only benchmark suite (`benchmark/_run.js:1`, `package.json:12`) |
| turndown | no | no | nothing (`src/turndown.js:147` is escape logic) |
| pandoc | no | no | speed-only Haskell benchmark (`benchmark/benchmark-pandoc.hs`). "Claude" hits are AI-authorship credits in `changelog.md:491,613` — LLM as developer, not as judge |
| markitdown | no (generation only) | no | LLM used to GENERATE image captions, never to score: `packages/markitdown/src/markitdown/converters/_llm_caption.py:7`, wired via `llm_client` in `_markitdown.py:149,588-589`. No quality signal comes back |
| mdream | no | no | token-count comparison across converters (LLM-consumption cost, not quality), `bench/token-compare.ts:15-30` |
| pdf-to-markdown | no | no | nothing. Only `package-lock.json` hash noise |
| PDF-Extract-Kit | no | docs-only | README advertises "Comprehensive Evaluation Benchmarks" and an "Evaluation Metrics" section (`README.md:30,84`) but the in-repo eval material is documentation (`docs/en/evaluation/`), not runnable per-document scoring code |

### Ranked findings

- [HIGH] The negative result: 0 of 17 long-tail repos contain any LLM-based scoring, judging, or hybrid det+LLM fusion. The single repo that calls an LLM at all (markitdown) uses it for content generation (`converters/_llm_caption.py:7`), and discards any quality signal. Evidence: full sweep table above.
  Impact: per-document hybrid QA like whisker+tapetum is genuinely rare; goals 1-3 will not find prior art in this tier, so the merge design must come from the high-prior repos (olmocr, marker, opendataloader-pdf) or be designed in-house.
- [HIGH] camelot's `Table.confidence` is the one adoptable fusion pattern: two bounded deterministic signals multiplied into a single [0,1] composite with documented threshold semantics ("either signal going to its worst value pulls confidence to 0"). Evidence: `camelot/camelot/core.py:682-705`.
  Impact: a direct candidate for goal 3's merged score shape: multiplicative fusion punishes disagreement asymmetrically, and camelot persists both raw components next to the composite (`core.py:726-732`), exactly the "both lanes visible next to the merged value" requirement.
- [MED] camelot's `simple_teds` is a dependency-free TEDS proxy (difflib sequence ratio x shape penalty), explicitly documented as "not exact TEDS... monotonic and good enough for relative comparison". Evidence: `camelot/bench/_metrics.py:24-33`.
  Impact: whisker already computes `ref_teds`; this shows a cheap in-process proxy pattern if the merge lane ever needs a TEDS-like signal without the `apted` dependency.
- [MED] html-to-markdown-py's golden-oracle harness: deterministic snapshots over 4 option permutations, byte-equality verified, with a blessed baseline JSON and guardrails file. Evidence: `tools/benchmark-harness/src/oracle.rs:1-14`, `CHANGELOG.md:349`, `tools/benchmark-harness/baselines/baseline.json`.
  Impact: for goal 2 persistence, a pattern for regression-gating merged-score artifacts: blessed snapshots + explicit re-bless step keeps schema-versioned sidecars honest across runs (matches C3/C4 discipline).
- [LOW] img2table's structural section scoring folds several weak signals (adjacent whitespace matches, top-down and bottom-up passes) into an accept/reject decision for borderless tables. Evidence: `src/img2table/tables/borderless/sections/segmentation.py:75-93`.
  Impact: minor: another example of rules-fold-to-verdict (like whisker `_decide`), no numeric composite, nothing new for goals 1-3.

### Max 3 mechanisms worth a follow-up

1. camelot `Table.confidence` multiplicative composite + dual-reporting in `parsing_report` (`camelot/camelot/core.py:682-732`): candidate shape for the whisker merged score (report composite while both lanes stay visible; C1-safe because it is reporting, not gating).
2. camelot `simple_teds` proxy (`camelot/bench/_metrics.py:24-33`): cheap monotonic TEDS stand-in if the merge lane wants a structural-agreement axis without new dependencies.
3. html-to-markdown-py oracle/baseline harness (`tools/benchmark-harness/src/oracle.rs`, `baselines/baseline.json`): regression-gating pattern for schema-versioned merged-score sidecars in `data/whisker/`.

## False-pass hypothesis

Adopting camelot-style multiplicative fusion naively: if the tapetum lane is absent or errored (6 of 194 papers in the 2026-07-06 run left NO tapetum sidecar, per 00-baseline runtime facts) and the merge treats the missing LLM factor as neutral 1.0, a table-heavy paper with decent unigram coverage but garbled tables (exactly the class tapetum catches, e.g. p4003r0 whisker review -> tapetum fail) would merge to a passing composite on the deterministic factor alone.

## False-fail hypothesis

The same multiplicative fusion's "either signal going to its worst value pulls the composite to 0" property (camelot `core.py:701`): a paper both lanes individually rate as borderline-review (whisker coverage 0.86, in the 0.85-0.95 soft band; tapetum verdict pass but confidence 0.30) multiplies to a near-zero merged score and gets rejected, even though neither lane found a hard defect.

## What would change my mind

Finding runnable LLM-judge or hybrid-scoring code inside any of these 17 repos that the text grep missed (notebooks, binary assets, or a submodule not checked out), most plausibly a real evaluation package behind PDF-Extract-Kit's docs-only `docs/en/evaluation/` pages. That would break the "long tail has NOTHING" negative result.
