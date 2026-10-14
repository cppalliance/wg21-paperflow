# 05 - Web Finding Cards (Step 0.5)

Collected 2026-07-06 by 5 Composer-2.5 web foragers. Deduplicated by URL
(one duplicate: the improvingagents.com table-format study surfaced under both
Q2 and Q5; kept under both with a cross-reference). Personas and meta-reviewers
may cite these cards as evidence by URL.

## Q1: How does olmOCR's per-fact assertion benchmark work?

- **olmOCR-Bench README (GitHub)** | https://github.com/allenai/olmocr/tree/main/olmocr/bench | HIGH
  Pass/fail "fact" unit tests on OCR markdown output, not edit distance or LLM
  judging. 6 assertion classes: Text Presence, Text Absence, Natural Reading
  Order, Table Accuracy (cell exists + neighbor relations; HTML needed for
  rowspan/colspan), Math Formula Accuracy (KaTeX render -> relative symbol
  layout match), plus per-page Baseline checks (non-empty output, no repeating
  n-grams, no CJK/emoji). 1,403 single-page PDFs across 7 document-source
  categories. Tests are LLM-assisted then human-reviewed.
- **olmOCR technical report, section 3 / Table 3** | https://olmocr.allenai.org/papers/olmocr.pdf | HIGH
  7,010 unique test cases over 1,402-1,403 PDFs: 721 presence, 823 absence,
  1,061 reading order, 1,020 table, 3,385 math. Strictly deterministic pass/fail
  with string normalization (NFC, hyphen/quote unification, markdown stripping);
  math uses headless-browser KaTeX bounding boxes and relative orientations.
  Overall = macro-average of per-source pass rates. Explicitly avoids
  LLM-as-judge and fuzzy gold-reference metrics.
- **allenai/olmOCR-bench (HuggingFace dataset card)** | https://huggingface.co/datasets/allenai/olmOCR-bench | HIGH
  1,403 PDFs + 7,010 JSONL unit tests. Per-source breakdown: 522 arXiv-math
  PDFs -> 2,927 math tests; 188 table PDFs -> 1,020 table tests; 231
  multi-column -> 884 reading-order tests. Presence/absence support fuzzy
  matching and first/last-N-char constraints; tables verify cell existence and
  above/below/left/right relationships. Public leaderboard: top systems ~82-88%.
- **olmOCR 2: Unit test rewards for document OCR (Ai2 blog)** | https://allenai.org/blog/olmocr-2 | MED
  The same deterministic unit-test verifiers double as RLVR training rewards, no
  second model in the eval path. olmOCR 2 scores 82.4 overall on the unchanged
  bench scorer.
- **Test Framework and Test Types (DeepWiki on olmocr/bench code)** | https://deepwiki.com/allenai/olmocr/4.1-test-framework-and-test-types | MED
  All tests inherit `BasePDFTest`, run against JSONL fixtures with typed
  assertions; human QA encoded via optional `checked: VERIFIED | REJECTED`
  fields; fuzzy text uses configurable `max_diffs` (default 0). `BaselineTest`
  auto-generates for pages lacking explicit tests. Scorer is pure Python.

## Q2: LLM comprehension of markdown tables (formats, failure modes, size)

- **TabVerse: Benchmarking Cross-Format Table Understanding** | https://arxiv.org/html/2606.09578v1 | HIGH
  2026 controlled benchmark across HTML, LaTeX, Markdown, images. HTML often the
  most robust text format for structural tasks (Qwen3-30B structural score ~51%
  HTML vs ~40% Markdown); QA format gaps modest (1-3 pp). Cell-lookup-style
  structural accuracy COLLAPSES: mean cell lookup 9.9%, row retrieval 5.0%
  (GPT-5.2 only 2.7-5.1%), vs column counting 62.8%. Failure modes: row/column
  coordinate confusion, row-boundary errors, header/index convention
  sensitivity (explicit 0-indexed prompts shift scores up to +94.8 pp).
- **ViTaB-A: Visual Table Attribution** | https://arxiv.org/pdf/2602.15769 | HIGH
  HiTab, 200 tables, Markdown vs JSON vs images. QA moderate (~50-62%) across
  formats, but evidence-cell attribution diverges: images ~33-53%, Markdown
  ~13-42%, JSON near-random (~0.5-1.5%). Models cite correct rows 1.3-2x more
  often than correct columns (systematic column/schema-linking weakness).
- **Which Table Format Do LLMs Understand Best?** | https://www.improvingagents.com/blog/best-input-data-format-for-llms/ | MED
  1,000-record single table, 1,000 lookups, GPT-4.1-nano: Markdown-KV 60.7% >
  XML 56.0% > HTML 53.6% > JSON 52.3% > pipe Markdown 51.9% > CSV 44.3% >
  pipe-delimited 41.1%. Richer linearizations cost 2-3x tokens. (Also cited
  under Q5.)
- **Calibrated Confidence Estimation for Tabular QA** | https://arxiv.org/html/2604.12491v1 | MED
  Same tables serialized as Markdown/HTML/JSON/CSV: when all four formats agree,
  accuracy >85%; fewer than three agree -> <40%. log(rows) and log(cols) are the
  most informative correctness covariates: larger tables are systematically
  harder. No single serialization dominates.
- **Same Content, Different Representations (RePairTQA)** | https://arxiv.org/pdf/2509.22983 | MED
  Controlled 2025 study: no universal winner across representations; degradation
  intensifies with table size and query complexity, confirming size as an
  independent accuracy driver.

## Q3: Downstream readability / comprehension in document-parsing benchmarks

- **ParseBench: A Document Parsing Benchmark for AI Agents** | https://arxiv.org/abs/2604.08538 | HIGH
  LlamaIndex 2026. Targets LLM/agent consumability: ~2,078 enterprise pages,
  169K deterministic rules across 5 dimensions (tables via TableRecordMatch,
  charts, content faithfulness incl. omissions/hallucinations/reading-order
  (141K+ text rules), semantic formatting like strikethrough/superscripts,
  visual grounding). Explicitly rejects LLM-as-judge and TEDS/edit-distance
  gating.
- **RealDocBench: Field-Level QA on Regulated Documents** | https://arxiv.org/html/2606.07401 | HIGH
  2026. QA track: 1,356 field-level questions over 581 documents with typed
  gold_dicts (currency, dates, booleans). Each parser's markdown is read by a
  FIXED extraction LLM and scored per-field with type-tolerant matching,
  decoupling evaluation from formatting. Positioned explicitly against
  OmniDocBench's edit-distance/TEDS scoring.
- **olmOCR paper (downstream consumability gate)** | https://arxiv.org/abs/2502.18443 | HIGH
  Beyond the 7,010 unit tests: continued pretraining OLMo-2-7B on
  olmOCR-linearized PDFs yields +1.3pp average on MMLU/DROP/NaturalQuestions vs
  Grobid-extracted tokens: a direct downstream-LLM-consumability measurement.
- **OmniDocBench (GitHub / CVPR 2025)** | https://github.com/opendatalab/OmniDocBench | MED
  Still structural-fidelity: Overall = ((1 - text edit distance) x 100 + table
  TEDS + formula CDM) / 3. v1.6-1.7 (2025-2026) improve matching and add a Hard
  subset, no comprehension metrics. Marker and MinerU are scored on this.
- **opendataloader-bench** | https://github.com/opendataloader-project/opendataloader-bench | MED
  Active through June 2026: purely structural (NID reading order, TEDS/TEDS-S,
  Markdown Heading Similarity) over 200 PDFs, 12 engines. No QA or fact
  recovery: the counter-example showing structural gating has NOT universally
  moved to comprehension.

## Q4: LLM-as-judge pitfalls and mitigations

- **Beyond Document Grounding: Span-Level Hallucination Detection** | https://arxiv.org/html/2607.00895 | HIGH
  Zero-shot LLM judges localize unsupported text poorly (best 0.22 span-F1 on
  code-agent answers, over-flagging correct content). A fine-tuned 2B span
  detector with character-offset JSON spans reaches 0.602-0.689 span-F1:
  verbatim span grounding beats scalar judge faithfulness scores.
- **AbstentionBench** | https://arxiv.org/abs/2506.09038 | HIGH
  20 frontier models, 20 datasets: abstention unsolved, scale barely helps.
  Reasoning fine-tuning makes it WORSE (DeepSeek R1: average 24% abstention
  drop vs instruction-tuned baselines), models issue definitive answers even
  when chain-of-thought expresses uncertainty. Directly corroborates the #277
  abstention-failure finding.
- **Judging the Judges: Bias Mitigation in LLM-as-a-Judge** | https://arxiv.org/html/2604.23178 | HIGH
  Style bias dominates (0.10-0.76); verbosity bias +0.24 to +0.44; position
  bias now <=0.04 on current models. Position swap + tie-on-disagreement gives
  +4.7 pp agreement; best combined strategy 71.0% human agreement (kappa 0.549).
- **Overconfidence in LLM-as-a-Judge** | https://arxiv.org/html/2508.06225v3 | HIGH
  Judges systematically overstate correctness; TH-Score quantifies
  confidence-accuracy misalignment in high-confidence bins. Confidence-driven
  ensemble routing cuts ECE up to 53.7%. Supports confidence-floor demotion of
  uncertain verdicts to review.
- **GSAR: Typed Grounding for Hallucination Detection** | https://arxiv.org/html/2604.23366 | HIGH
  Scalar faithfulness scores collapse distinct failure modes; a typed claim
  partition (grounded/ungrounded/contradicted/complementary) with an abstain
  channel and a 3-tier proceed/regenerate/replan policy gives a measured
  demote-to-review pattern for ungrounded output.

## Q5: Markdown formatting choices and LLM reading accuracy

- **HiChunk (ACL 2026)** | https://aclanthology.org/2026.acl-long.1372/ | HIGH
  Heading-aware hierarchical chunking: cut-point F1 on Qasper 0.1007 (semantic
  chunker) -> 0.9441; evidence recall 74.06 (fixed 200-token chunks) -> 81.03
  with hierarchical chunking + Auto-Merge. Preserve heading hierarchy, chunk on
  section boundaries: validates our H2-boundary chunking choice.
- **MDKeyChunker** | https://arxiv.org/abs/2603.23533 | HIGH
  Treats headers, fenced code blocks, pipe tables, lists as ATOMIC units, never
  splitting mid-fence or mid-table. BM25 over structural chunks: Recall@5 1.000
  vs 0.867 for dense retrieval over fixed-size chunks; zero code-block or table
  splits.
- **Which Table Format Do LLMs Understand Best?** | https://www.improvingagents.com/blog/best-input-data-format-for-llms/ | HIGH
  (Card under Q2.) Pipe Markdown tables 51.9% vs Markdown-KV 60.7% on wide-table
  lookup: pipe tables are not the ceiling for LLM readability of tabular data.
- **Anthropic: Contextual Retrieval** | https://www.anthropic.com/engineering/contextual-retrieval | HIGH
  Prepending 50-100 tokens of situating context per chunk cuts top-20 retrieval
  failure 35-67%. Practitioners substitute deterministic heading breadcrumbs
  (title + H1/H2/H3 path) for LLM-generated prefixes.
- **Benchmarking Formula Extraction from PDFs** | https://arxiv.org/html/2512.09874v2 | HIGH
  2,000+ formulas, 20+ parsers: character-level CDM correlates poorly with human
  judgment (r=0.34) and penalizes Unicode math; LLM-judge semantic equivalence
  reaches r=0.78. Parsers substituting Unicode/ASCII for LaTeX symbols degrade
  downstream math QA. Directly relevant to our `_math_surface` pylatexenc
  folding, which normalizes LaTeX -> unicode for comparison.
