# Whisker Auditv3 — Block E (Doctrine Alignment) — Raw Quotes

Evidence only. No verdicts. No conclusions.

Query for item 2: `rg -ni "perfect|byte-exact|human-grade|pixel" packages/whisker packages/tomd --glob "*.md" --glob "*.py"`

Query for item 3: `rg -ni "llm.consum|llm.read|downstream|good.enough|comprehen|recover the paper|fact recovery" packages/whisker packages/tomd research --glob "*.md" --glob "*.py"`

Note: `packages/whisker/research/llm-readability/` does not exist. Matching material lives at repo root `research/llm-readability/`.

---

## 1. Stated purpose of measurement

### packages/whisker/src/whisker/CLAUDE.md

`packages/whisker/src/whisker/CLAUDE.md:7-9`
> 1. **This file, "What this is" + "Three lanes"**: the mental model. whisker is
>    deterministic QA for tomd conversions; three independent lanes (stability,
>    fidelity, comprehension) plus two opt-in LLM tools that never gate.

`packages/whisker/src/whisker/CLAUDE.md:38-49`
> whisker answers two questions:
>
> - **Per paper, without hand-labeled ground truth:** is this conversion safe to
>   ship, does it need a human, or is it broken? (`whisker [PID ...]`) The hard
>   gate is the reference-free path (structural gates + a content-coverage floor).
>   By default whisker ALSO generates an independent reference markdown from the
>   same source with a second converter (the *oracle*, markitdown) and scores
>   tomd's text against it as an ADVISORY signal: low cross-converter agreement
>   raises a review flag for a human to look, but never fails a paper on its own
>   (agreement != correctness). `--no-reference` skips the oracle entirely.
> - **Against labeled ground truth:** how good is the conversion on the structural
>   fidelity axes, and did it regress? (`whisker bench`)

`packages/whisker/src/whisker/CLAUDE.md:115-128`
> - **Lane 1 Stability** (`whisker golden`, `golden.py`): did the normalized
>   markdown change vs a committed `<pid>.expected.md` snapshot. Exact `difflib`
>   compare; catches silent regressions AND silent improvements. Bless a change by
>   reviewing the diff, then `--update`. A blessed snapshot is NOT a correctness
>   oracle: it freezes whatever a human approved, bugs included.
> - **Lane 2 Fidelity** (`whisker bench` / `whisker guard`): how CLOSE is the
>   output to a human-corrected `<pid>.gt.md` reference, on
>   `nid`/`teds`/`mhs`/`content_recall`. This is resemblance, not comprehension.
> - **Lane 3 Comprehension** (`whisker facts`, `facts.py`): can an LLM still
>   RECOVER the paper's facts from the markdown. Deterministic source-verified
>   assertions (`present`/`absent`/`order`/`table`/`math`), no LLM in the loop.

`packages/whisker/src/whisker/CLAUDE.md:130-137`
> **Fidelity is not comprehension.** A reflow can score high on every Lane 2 axis
> and still scramble a table cell or drop a formula's exponent so a downstream LLM
> reads "row 3, column 2" wrong, with every fidelity metric green. Only Lane 3
> catches that. Lane 3 also sidesteps the ground-truth-provenance problem: across
> the 28 surveyed converters, none has an automatic "this file is 100% correct"
> oracle, and only `olmocr` tests comprehension at all. A handful of source-verified
> facts per paper are cheap to author and independent of any single `tomd` output,
> so they are the honest WG21 ground truth without a perfect golden file.

`packages/whisker/src/whisker/CLAUDE.md:366-375`
> ## Verdict model
>
> Three outcomes: `pass`, `review`, `fail`. The hard gate is the same whether or
> not the oracle ran; the oracle only adds an advisory review overlay.
>
> **Hard fails (the only ways to fail):**
>
> - any structural gate failure (`gates.py`), or
> - `unigram_coverage < UNIGRAM_COVERAGE_FAIL_EDGE` (0.85): content genuinely
>   missing.

`packages/whisker/src/whisker/CLAUDE.md:527-535`
> The deterministic facts are a deterministic PROXY for what a downstream LLM must recover.
> That proxy is validated ONCE, empirically and out of band: hand a fresh LLM ONLY
> the converted markdown plus the fact questions, let it answer blind, compare to
> the verified facts. P4182R0 passed 3x 8/8 including the two table cells (recorded
> in `corpus/P4182R0.validation.md`). This read-back is NEVER in CI (determinism,
> cost, model-sovereignty); it is the one-time anchor that justifies trusting the
> LLM-free gate. A "regenerate similar text" round-trip is the WRONG test (LLMs
> paraphrase, so resemblance measures fidelity, not comprehension); the test is
> question answering ("row X, column Y reads what?").

### packages/whisker/src/whisker/tapetum_llm/tapetum_llm.md

`packages/whisker/src/whisker/tapetum_llm/tapetum_llm.md:3-4`
> Multi-axis conversion-fidelity adjudication for whisker candidates. A two-tier cascade: a cheap fast model adjudicates; any of three uncertainty signals (axis conflict, ungrounded evidence, ambiguous-band confidence) escalates to the deep model. Advisory only: never part of `whisker --gate`, never hard-fails, never overwrites the whisker verdict on record.

`packages/whisker/src/whisker/tapetum_llm/tapetum_llm.md:138`
> Advisory wording rule: a clean all-pages run means **no additional findings**, not proof of correctness. The inspect report line reads `all pages checked, no additional findings (advisory)` and must never say "verified correct". Deterministic whisker gates and the manual ideal-vs-source fidelity diff stay load-bearing; the LLM pass is triage only.

`packages/whisker/src/whisker/tapetum_llm/tapetum_llm.md:144-146`
> You are a conversion-fidelity adjudicator for WG21 documents converted from PDF or HTML to Markdown by the project's `tomd` converter. A deterministic gate (whisker) already scored this conversion; you give a second opinion on the CONVERSION, nothing else.
>
> Judge CONVERSION FIDELITY, not the paper's technical merit. The only question: does this Markdown faithfully and readably represent the source document a committee member would need to review? You are not grading the C++ proposal. A weak proposal converted perfectly is a `pass`; a strong proposal whose tables were scrambled is a `fail`.

### repo root CLAUDE.md

`CLAUDE.md:123-127`
> ## Fidelity
>
> The analytical pipelines (dissect, agora) cannot tolerate partial results. A wrong objection or missing evidence destroys credibility in a way that cannot be regained.
>
> If full fidelity cannot be achieved, stop. Fail the paper with a clear error message. Preserve the debug transcript. Never produce a partial result mistakable for a complete one.

(No passage in repo root `CLAUDE.md` defines whisker measurement doctrine or Lane 1/2/3.)

### packages/tomd/src/tomd/CLAUDE.md

`packages/tomd/src/tomd/CLAUDE.md:125-133`
> ## Honest Output
>
> The tool must never silently produce bad Markdown.
>
> - If a region is uncertain, emit the MuPDF version in the output marked with `<!-- tomd:uncertain:L{start}-L{end} -->`
> - The companion prompts file is a JSON array; each element is a self-contained prompt that includes BOTH extraction versions, surrounding context, and the framing instructions
> - LLM prompts must require verbatim data preservation - the LLM fixes structure, never content
> - If no prompts file is needed (zero uncertain regions), don't write one.
> - High-confidence output should look like a human wrote the Markdown - proper heading nesting, unwrapped paragraph lines, correct list formatting, blank lines between blocks

`packages/tomd/src/tomd/CLAUDE.md:135-148`
> ## Markdown Quality
>
> The output Markdown must be clean and readable:
> - Paragraphs are single unwrapped lines (no hard wraps from PDF line breaks)
> - One blank line between all block elements (paragraphs, headings, lists, code blocks)
> - Headings use ATX style (`##` not underlines)
> [...]
> - Collapse multiple spaces, replace non-breaking spaces, normalize whitespace

### packages/tomd/README.md

`packages/tomd/README.md:7-9`
> understands WG21 metadata fields (document number, date, reply-to, audience),
> detects structural elements (headings, lists, tables, code blocks, wording
> sections), and produces Markdown that looks like a human wrote it, suitable
> for version control, pull request diffs, and plain-text review workflows.

---

## 2. The word "perfect"

Search query: `rg -ni "perfect|byte-exact|human-grade|pixel" packages/whisker packages/tomd --glob "*.md" --glob "*.py"`

No hits for `human-grade` in packages/whisker or packages/tomd (*.md, *.py).

### Verdict / target usage (doctrine and code)

`packages/whisker/src/whisker/tapetum_llm/tapetum_llm.md:146`
> A weak proposal converted perfectly is a `pass`; a strong proposal whose tables were scrambled is a `fail`.

(Context: LLM advisory lane system prompt; `pass`/`fail` are advisory verdict states, not a "perfect conversion" metric.)

`packages/whisker/src/whisker/tapetum_llm/tapetum_llm.md:178`
> - A recoverable-but-imperfect defect is `review` with severity `minor`.

`packages/whisker/src/whisker/CLAUDE.md:137`
> so they are the honest WG21 ground truth without a perfect golden file.

`packages/whisker/src/whisker/golden.py:16-18`
> Provenance discipline (the June 2026 golden-provenance audit, 28 repos): no repo
> has an automatic "this file is 100% correct" oracle. The committed expected file
> is a self-blessed snapshot of tomd output, frozen by a HUMAN reviewing the diff,

`packages/whisker/src/whisker/golden.py:85`
> trailing-space noise (the brittle part of byte-exact goldens on Windows

`packages/whisker/src/whisker/golden_ideals.py:60-61`
> ineligible, not a synthetic perfect score (bench null-eligibility rule,
> schema v3 lesson). ``overall`` is the mean of the ELIGIBLE structural axes

`packages/whisker/src/whisker/bench.py:74`
> # synthetic perfect score. nid and content_recall always apply (text).

`packages/whisker/src/whisker/golden.py:31`
> `expected_failures` (in `golden.json`) flag known-imperfect snapshots that must

`packages/whisker/src/whisker/CLAUDE.md:944-945`
> raster extraction, pixel inspection, VLM coverage, and image fidelity are
> outside the audit scope and are not missing scoring requirements.

`packages/whisker/src/whisker/tapetum_llm/vision.py:40-43`
> TARGET_PIXELS = 2_073_600
> """Client-side pixel budget per page image (~1440x1440 or 1920x1080).
>
> The server's ``--mm-processor-kwargs max_pixels`` controls what the VLM

`packages/whisker/src/whisker/tapetum_llm/pdf_judge.py:15`
> Unlike the VLM lane (pixels only, deterministic diff afterwards), the

`packages/whisker/src/whisker/tapetum_llm/vlm_diff.py:10`
> After the VLM produces a pixel-only transcription of the PDF and tomd

### tomd — byte-exact / perfect (fixtures and QA)

`packages/tomd/tests/fixtures/golden/README.md:18-20`
> - **Snapshot** (`snapshots/<stem>.md`): a byte-exact lock on tomd's *current*
>   output. Guarded by `test_pdf_golden` / `test_html_golden`. Answers "did the
>   output change at all?" Any figure PNGs the markdown references live beside it.

`packages/tomd/tests/fixtures/golden/README.md:102`
> output and are guarded byte-exactly by `test_pdf_golden` / `test_html_golden`.

`packages/tomd/tests/test_pdf_golden.py:1`
> """Snapshot regression: full PDF papers vs committed byte-exact Markdown."""

`packages/tomd/tests/test_html_golden.py:1`
> """Snapshot regression: full HTML papers vs committed byte-exact Markdown."""

`packages/tomd/tests/test_golden_gate.py:6`
> below it. Byte-exact snapshot fidelity is covered separately by

`packages/tomd/src/tomd/lib/golden_qa.py:276-278`
> the comparator scores semantically, so even a structurally-perfect corrected
> correction step was skipped, so the ideal tests nothing the byte-exact

`packages/tomd/src/tomd/lib/check_content.py:883`
> "tokens in the produced markdown. Perfect coverage (1.00) is not\n"

`packages/tomd/tests/test_golden_qa.py:210-222`
> def test_generate_seeded_ideal_scores_perfect(tmp_path):
>     # byte-identical to tomd_markdown so the uncorrected seed scores a perfect

`packages/whisker/tests/test_golden_ideals.py:101`
> def test_identical_ideal_scores_perfect_panel():

(Test function names only; no verdict state named `perfect`.)

### Fixture paper content (not tool doctrine)

Hits in `packages/tomd/tests/fixtures/golden/snapshots/*.md` and similar contain the word "perfect" or "perfectly" inside converted WG21 paper prose (e.g. `p0533r9.md:132`, `p4016r0.golden.md:864`). These are source-paper words, not whisker/tomd measurement claims.

### Research / audit files under packages/whisker (selected)

`packages/whisker/research/Audit/Auditv1/p15-weighted-scoring-rubric.md:180`
> | **Compensability honesty** | UNDP HDI moved from linear to geometric (2010) to reduce **perfect substitution** across dimensions

`packages/whisker/research/Audit/Auditv1/p09-extraction-quality-metrics.md:21`
> (c) that absence is reported as `null`/`N/A`, not imputed as perfect or zero.

`packages/whisker/corpus/holdout/README.md:18-19`
> P3714R0 use tomd's byte-exact PDF snapshots. P4182R0 uses its human-blessed
> tomd ideal because no byte-exact tomd snapshot exists for that source.

`packages/whisker/corpus/P4182R0.validation.md:47`
> - Run 3: byte-exact, the subagent read the real committed `P4182R0.expected.md` directly (single file confirmed, 412 lines). Result: 8/8.

**No whisker verdict state, exit code, or fleet aggregate is named `perfect`. No `% perfect` string found in packages/whisker (*.md, *.py).**

---

## 3. LLM-consumption framing

Search query: `rg -ni "llm.consum|llm.read|downstream|good.enough|comprehen|recover the paper|fact recovery" packages/whisker packages/tomd research --glob "*.md" --glob "*.py"`

(Partial timeout on full `research/` tree; substantive hits below include required files and repo-root `research/llm-readability/`.)

### packages/whisker/research/comprehension-poc-report.md

`packages/whisker/research/comprehension-poc-report.md:1`
> # Comprehension POC report: proving converted markdown is LLM-readable

`packages/whisker/research/comprehension-poc-report.md:10-21`
> tomd converts WG21 PDF/HTML papers to markdown. The existing tests answer
> "does the output look faithful" (golden byte-diffs, fidelity metrics like
> nid/teds/mhs, content coverage). None of them answer the question that actually
> matters for the downstream analytical pipelines:
>
> > Can an LLM that consumes the converted markdown still READ it correctly:
> > recover the paper's facts, look up the right table cell, follow the section
> > order, not be fed page furniture?
>
> A faithful-looking reflow can still scramble a table so "row 3, column 2" reads
> wrong, and every fidelity metric stays green. We wanted a test that gates on
> read -> understood -> correct, not on resemblance to a golden file.

`packages/whisker/research/comprehension-poc-report.md:56-57`
> matches, the deterministic facts are proven to be a faithful proxy for what
> the LLM recovers.

### packages/whisker/research/Audit/Auditv1/p13-comprehension-vs-fidelity.md

`packages/whisker/research/Audit/Auditv1/p13-comprehension-vs-fidelity.md:11`
> How should a professional-grade document-extraction QA audit **separate fidelity** (resemblance to a reference artifact: string overlap, edit distance, tree similarity to gold markdown) from **comprehension** (whether a downstream reader can recover the document's facts from the converted text alone), and what external methods exist to **evaluate comprehension** via fact-recovery QA, blind read-back, and adversarial corrupt-and-recheck controls—while rejecting round-trip / regenerate-similar-text tests as comprehension proxies?

`packages/whisker/research/Audit/Auditv1/p13-comprehension-vs-fidelity.md:19`
> **Criterion:** The eval harness MUST report fidelity metrics and comprehension metrics on **separate axes**, with written definitions that forbid treating one as a proxy for the other. Fidelity answers "does output resemble the reference representation?"; comprehension answers "can verified facts be recovered from output alone?"

`packages/whisker/research/Audit/Auditv1/p13-comprehension-vs-fidelity.md:37-40`
> ### C2 — Closed-book fact-recovery QA battery (primary comprehension metric)
>
> **Criterion:** Comprehension MUST be measured by a **closed-book QA battery**: questions with verified gold answers, answered using **only** the extracted markdown (no PDF, no gold reference text, no source HTML). Score = fraction of questions where the recovered answer matches gold under a documented normalization policy.

### packages/whisker/research/persona/08-downstream-llm-consumer.md

`packages/whisker/research/persona/08-downstream-llm-consumer.md:3`
> **Verdict:** usable-with-conditions — whisker `pass` certifies structural well-formedness and high token-set recall against the source text layer, not that a dissect/agora LLM can recover facts, table geometry, math structure, or argument order; Lane 3 exists for that job but runs on **0/382** papers.

`packages/whisker/research/persona/08-downstream-llm-consumer.md:8`
> - [CRITICAL] **`pass` is not an LLM-comprehension certificate.** The spec states explicitly that fidelity axes "measure resemblance, not comprehension" and that only Lane 3 catches scrambled table cells or dropped exponents while fidelity stays green (`CLAUDE.md:30-40`). The default `whisker` verb calls `score_paper` only (`__main__.py:204`); it never invokes `check_facts`. Impact: **163/382 (42.7%)** ref-free passes (`00` §3a) and **368/382 (96.3%)** papers at default CI `--gate review` (`CLAUDE.md:302-303`) reach downstream pipelines with **zero** deterministic fact assertions enforced.

### packages/whisker/notes/QA-RELIABILITY-VERDICT.md

`packages/whisker/notes/QA-RELIABILITY-VERDICT.md:24-34`
> whisker is a **sound, deterministic, well-engineered instrument that measures exactly one
> thing well, is mislabeled by what `pass` implies, and is uncalibrated.** Used as a
> **coarse triage floor** ("block grossly broken artifacts, route the rest to a human") it
> is trustworthy today. Used as an **autonomous "this conversion is faithful" gate** (how
> `pass` will be read downstream) it is not, because reading-order, table-cell, and
> code-block semantics are categorically ungated and the layer designed to catch them
> (Lane 3) runs on zero papers.
>
> The instrument is honest about its own limits in `constants.py` and `CLAUDE.md`. The risk
> is not deception; it is the **gap between what `pass` certifies (word presence +
> well-formedness) and what a downstream consumer will assume `pass` means (fidelity).**

`packages/whisker/notes/QA-RELIABILITY-VERDICT.md:79`
> | 1 | **`pass` is a word-multiset-presence + well-formedness certificate, NOT a fidelity certificate.** Reading order, table row/cell assignment, and fenced-code identifiers are categorically ungated (`unigram_coverage` is order-invariant `check_content.py:621`; shingle `coverage` "never a verdict flag" `score.py:136-137`). | 01,03,08,18,19,20,21,23 (8) | **Opus B reproduced at scale: 96% (24/25) of passing table-papers survive an adversarial section-reverse + row-swap as `pass`.** `P1040R10` cov 0.991->0.976 stays pass. `P4178R0` already passes *uncrafted* at cov=0.837. **CRITICAL, confirmed.** |

`packages/whisker/notes/QA-RELIABILITY-VERDICT.md:127-128`
> 3. **Rename / re-document `pass`** as "content-present + well-formed", never "faithful",
> everywhere a downstream consumer (dissect/agora, CI) reads it.

### research/llm-readability/ (repo root; not under packages/whisker)

`research/llm-readability/00-baseline.md:15-17`
> - **#254** (OPEN): "verify converted output is actually LLM-readable (read ->
>   understood -> correct), not just golden-file faithful." This is the research
>   question of this run.

`research/llm-readability/00-baseline.md:32-34`
> - **Lane 3 Comprehension** (`facts.py`): deterministic, human-verified fact
>   assertions; the only lane that tests "can an LLM still recover the paper's
>   facts." No LLM in the scoring loop (olmOCR model, adopted deliberately).

`research/llm-readability/SYNTHESIS.md:5-7`
> **Run question:** "Are our markdowns provably fully LLM-readable, theoretically and practically confirmed?"
> **Honest one-line answer:** proven for the 2 corpus papers' authored facts; NOT YET PROVEN for the ~200-paper fleet; the stack is on the only externally validated path to making it provable.

`research/llm-readability/SYNTHESIS.md:28-30`
> - **The fleet gap is the single honest CRITICAL.** 198 of ~200 converted papers carry
>   zero verified facts; Lane 3 passes vacuously for them (facts.py:128-130). Their only
>   protection is the order-blind `unigram_coverage >= 0.85` multiset gate + structural

`research/llm-readability/15-downstream-consumer.md:3`
> **Verdict:** usable-with-conditions — Lane 3 certifies full-document fact recovery on two papers, but the live consumers (assay claim extraction + agora thread planning) read markdown through chunked, line-windowed, text-only views that the gate never exercises; a whisker-pass paper can still yield misread claims or hollow agora plans.

### packages/whisker/src/whisker (code)

`packages/whisker/src/whisker/facts.py:146-148`
>     def passed(self) -> bool:
>         # Only verified facts gate; a paper with no verified facts passes.
>         return all(c.passed for c in self._enforced())

`packages/whisker/src/whisker/__main__.py:28`
> nid/teds/mhs); ``facts`` is Lane 3 COMPREHENSION (can an LLM still read it, via

### packages/tomd (selected)

`packages/tomd/src/tomd/lib/golden_qa.py:552-555`
>     """Full score: structural axes, whisker metrics panel, comprehension panel.
>
>     Superset of :func:`score_report`. The whisker and comprehension panels are

`packages/tomd/src/tomd/CLAUDE.md:48`
> Never discard information from the PDF during extraction. Text is the primary output, but font size, font name, font flags, coordinates, and page boundaries are preserved as annotations. Downstream phases use this metadata for confidence scoring and LLM prompt context.

---

## 4. Verdict states in code

### Possible verdict values

`packages/whisker/src/whisker/score.py:53-55`
```python
VERDICT_PASS = "pass"
VERDICT_REVIEW = "review"
VERDICT_FAIL = "fail"
```

`packages/whisker/src/whisker/report.py:25-26`
```python
_VERDICTS = (VERDICT_PASS, VERDICT_REVIEW, VERDICT_FAIL)
_MARK = {VERDICT_PASS: "PASS", VERDICT_REVIEW: "REVIEW", VERDICT_FAIL: "FAIL"}
```

No other deterministic whisker verdict string exists in `score.py` / `constants.py`.

### `_decide()` logic (verbatim)

`packages/whisker/src/whisker/score.py:136-231`
```python
def _decide(
    unigram_coverage: float,
    unigram_drift: float,
    missing_count: int,
    extra_count: int,
    qa_score: int,
    uncertain_count: int,
    gates: list[GateResult],
    ref: tuple[float, float, float, float] | None = None,
    ideal: IdealPanel | None = None,
) -> tuple[str, list[str], list[str]]:
    """Return (verdict, hard_flags, soft_flags) from fused signals.

    The content hard-gate runs on ``unigram_coverage`` (order-invariant token-set
    recall), not on the order-sensitive shingle coverage. Structural gates and
    ``unigram_coverage < UNIGRAM_COVERAGE_FAIL_EDGE`` are the only HARD fails
    (broken artifact or genuinely missing words). A unigram coverage in the
    review band, ``unigram_drift`` (order-invariant precision complement),
    misaligned regions, qa and uncertain markers are soft (review). Both the
    shingle ``coverage`` and the order-sensitive shingle ``drift`` are
    reading-order proxies: reported elsewhere, never a verdict flag, because
    every benchmark repo keeps reading order off the content gate (see
    constants). The soft drift signal therefore tracks ``unigram_drift`` so a
    faithful reflow does not look like injected content.

    When ``ref`` (nid, teds, mhs, overall) is present, cross-converter TEXT
    agreement is layered on as an ADVISORY soft signal only: low ``ref_nid``
    adds a review flag but NEVER hard-fails (cross-converter agreement is a
    confidence signal, not ground truth: "agreement != correctness"). teds/mhs
    are reported per-axis but never flag, since against a weak oracle they carry
    no reliable signal.

    When ``ideal`` is present the paper has a human-blessed golden ideal, which
    IS ground truth, so every Lane-2 axis flags against its bench floor. The
    flags are still ADVISORY (review, never hard fail): the calibrated hard
    gate stays untouched until the ideal corpus is large enough to calibrate
    its own operating point (see constants).
    """
    hard: list[str] = []
    soft: list[str] = []

    for gate in gates:
        if not gate.passed:
            hard.append(f"gate:{gate.name}:{gate.detail or 'failed'}")

    if unigram_coverage < C.UNIGRAM_COVERAGE_FAIL_EDGE:
        hard.append(
            f"unigram coverage {unigram_coverage:.3f} < "
            f"{C.UNIGRAM_COVERAGE_FAIL_EDGE} (content missing)"
        )
    elif unigram_coverage < C.UNIGRAM_COVERAGE_REVIEW_EDGE:
        soft.append(f"unigram coverage {unigram_coverage:.3f} in review band")

    region_total = missing_count + extra_count
    if region_total >= C.REGION_SOFT_COUNT:
        soft.append(f"{region_total} misaligned region(s)")

    if unigram_drift > C.DRIFT_SOFT_EDGE:
        soft.append(f"unigram drift {unigram_drift:.3f} > {C.DRIFT_SOFT_EDGE}")
    if qa_score < C.QA_SCORE_SOFT_EDGE:
        soft.append(f"qa_score {qa_score} < {C.QA_SCORE_SOFT_EDGE}")
    if uncertain_count:
        soft.append(f"{uncertain_count} uncertain marker(s)")

    if ref is not None:
        ref_nid = ref[0]
        if ref_nid < C.REF_NID_ADVISORY_EDGE:
            soft.append(f"reference text agreement {ref_nid:.3f} low (advisory)")

    if ideal is not None:
        # teds/mhs are None when the ideal lacks the modality (null-eligibility):
        # an ineligible axis cannot flag.
        for value, floor, axis in (
            (ideal.nid, C.NID_FLOOR, "nid"),
            (ideal.teds, C.TEDS_FLOOR, "teds"),
            (ideal.mhs, C.MHS_FLOOR, "mhs"),
            (ideal.recall, C.CONTENT_RECALL_FLOOR, "recall"),
        ):
            if value is not None and value < floor:
                soft.append(f"ideal {axis} {value:.3f} < {floor} (advisory)")

    if hard:
        return VERDICT_FAIL, hard, soft

    # Benign-region fold: when the ONLY soft flags are misaligned region(s) and
    # unigram coverage confirms the content is complete (>= 0.95), the paper
    # passes. tomd deliberately strips page furniture, so region mismatches on
    # high-coverage papers are expected, not defects. The region flag stays
    # visible (annotated "(benign)") for auditability.
    if soft and _is_benign_region_only(soft, unigram_coverage):
        benign_soft = [f"{f} (benign)" for f in soft]
        return VERDICT_PASS, hard, benign_soft

    if soft:
        return VERDICT_REVIEW, hard, soft
    return VERDICT_PASS, hard, soft
```

### Condition summary

| Verdict | Conditions |
|---------|------------|
| `fail` | Any `hard` flag: structural gate failure OR `unigram_coverage < 0.85` |
| `review` | No hard flags AND at least one soft flag (and benign-region fold does not apply) |
| `pass` | No hard flags AND (no soft flags OR benign-region-only fold with `unigram_coverage >= 0.95`) |

**HARD fails:** gate failures; `unigram_coverage < UNIGRAM_COVERAGE_FAIL_EDGE` (0.85).

**SOFT (review) flags:** unigram in 0.85–0.95 band; `>= REGION_SOFT_COUNT` misaligned regions; `unigram_drift > DRIFT_SOFT_EDGE`; `qa_score < QA_SCORE_SOFT_EDGE`; any uncertain markers; `ref_nid < REF_NID_ADVISORY_EDGE`; ideal axis below floor (all advisory).

**No verdict state means "perfect".**

Threshold definitions: `packages/whisker/src/whisker/constants.py:37-38,41,47,54,58,63-65,74,94,101-105`

`packages/whisker/src/whisker/constants.py:96-105`
> # Unlike the markitdown oracle, a golden ideal (tomd golden-QA workflow,
> # packages/tomd/tests/fixtures/golden/ideals/) IS human-blessed ground truth,
> # so the ideal panel reuses the Lane-2 bench floors (NID_FLOOR, TEDS_FLOOR,
> # MHS_FLOOR, CONTENT_RECALL_FLOOR) as its advisory edges rather than the
> # weaker oracle edge. Still ADVISORY ONLY: a below-floor axis raises a review
> # flag, never a hard fail.

---

## 5. Cosmetics handling in the LLM lane

### System prompt (tapetum_llm.md)

`packages/whisker/src/whisker/tapetum_llm/tapetum_llm.md:171`
> 7. **structure** — section order and completeness. `fail` is reserved for sections reordered, dropped, or duplicated, or a body that ends mid-sentence. Permuted sections are the dominant defect the deterministic gate misses, so scrutinize order. A heading-level jump (e.g. an H2 followed by an H4, skipping H3) is cosmetic: severity `minor`, verdict `review` at most, never `fail`, since a reader loses nothing. Leaked TOC content in the body [...] is a structure defect: the converter's contract strips the TOC, so anything TOC-shaped that survives is a defect, severity at least `major`, verdict at least `review`.

`packages/whisker/src/whisker/tapetum_llm/tapetum_llm.md:177-181`
> - `fail` REQUIRES severity `major`: the axis content is unrecoverable by a human reader without the source.
> - A recoverable-but-imperfect defect is `review` with severity `minor`.
> - A clean axis is `pass` with severity `none`.
>
> Never emit `fail` with `minor` or `none` severity. Do not fail on cosmetics. The decide step enforces this: a `fail` below `major` is folded down to `review`, so a mislabeled cosmetic `fail` cannot escalate to an overall fail.

`packages/whisker/src/whisker/tapetum_llm/tapetum_llm.md:183-185`
> ### The RESCUE case (false-fail)
>
> Some papers reach you because whisker's ONLY hard flag was a heading-monotone jump. When the prose, tables, code, and section order are otherwise faithful, that is a false-fail: adjudicate `review` (likely shippable), not `fail`. The heading quirk alone is never `major`.

`packages/whisker/src/whisker/tapetum_llm/tapetum_llm.md:146`
> does this Markdown faithfully and readably represent the source document a committee member would need to review?

### Code enforcement

`packages/whisker/src/whisker/tapetum_llm/chunking.py:106-113`
> def worst_axis_verdict(findings: list[AxisFinding]) -> str:
>     """Severity-aware worst-axis fold.
>
>     The overall verdict tracks the worst axis, but a ``fail`` label only becomes
>     a hard overall fail when its severity is ``major`` (unrecoverable). A
>     non-major fail is the model's recoverable/cosmetic call (e.g. a heading-level
>     jump) and folds to ``review``. This is what rescues the false-fail RESCUE
>     population instead of escalating a cosmetic defect to ``fail``.

`packages/whisker/src/whisker/tapetum_llm/constants.py:47-51`
> # Severity at which an axis "fail" becomes a hard overall fail. A fail-labeled
> # axis below this severity (the model's recoverable/cosmetic call, e.g. a
> # heading-level jump) folds to "review", which is what lets the false-fail
> # RESCUE population (heading_monotone-only) actually be rescued. Mirrors the
> # AxisFinding.severity Literal in models.py.

`packages/whisker/src/whisker/tapetum_llm/adjudicate.py:327-329`
>     # Overall == severity-aware worst axis (see _worst_axis_verdict). This
>     # overrides the model's self-reported overall verdict so a fail/minor axis
>     # cannot become a hard overall fail.

`packages/whisker/src/whisker/tapetum_llm/pdf_judge.py:183-198`
> JUDGE_SYSTEM_PROMPT = (
>     "You are a conversion-fidelity judge. You receive two versions of the "
>     "same WG21 C++ committee paper:\n"
> [...]
>     "Verdict semantics:\n"
>     "- pass: the markdown faithfully represents the PDF text.\n"
>     "- review: minor omissions or structural drift a human should check.\n"
>     "- fail: substantial content missing, corrupted, or reordered.\n\n"

`packages/whisker/src/whisker/tapetum_llm/unit_judge.py:135`
> "drift. Cosmetic source formatting is not a defect. Ignore source "

`packages/whisker/src/whisker/tapetum_llm/fusion_report.py:143-161`
> def _classify_cosmetic(tap: dict) -> str:
>     """Return ``"cosmetic"`` when the LLM's only non-pass axis is structure/minor."""
> [...]
>         f.get("axis") == "structure" and f.get("severity") == "minor"
> [...]
>         return "cosmetic"

`packages/whisker/src/whisker/tapetum_llm/__init__.py:15`
> rescues the false-fail case: cosmetic ``heading_monotone``-only fails. It is

---

## 6. Fleet reporting

### build_report / render_report_md

`packages/whisker/src/whisker/report.py:37-38`
```python
def _counts(results: list[WhiskerResult]) -> dict[str, int]:
    return {v: sum(1 for r in results if r.verdict == v) for v in _VERDICTS}
```

`packages/whisker/src/whisker/report.py:90-98`
```python
def build_report(results: list[WhiskerResult]) -> dict:
    """Assemble the JSON report payload from a batch of results."""
    ordered = sorted(results, key=lambda r: r.pid)
    return {
        "schema_version": C.WHISKER_SCHEMA_VERSION,
        "count": len(ordered),
        "counts": _counts(ordered),
        "results": [r.to_dict() for r in ordered],
    }
```

`packages/whisker/src/whisker/report.py:108-109`
> (f"{len(ordered)} scored: {counts[VERDICT_PASS]} pass, "
>  f"{counts[VERDICT_REVIEW]} review, {counts[VERDICT_FAIL]} fail"),

### Footer / `--stats`

`packages/whisker/src/whisker/report.py:261-274`
```python
    parts = [
        f"{counts[VERDICT_FAIL]} failed",
        f"{counts[VERDICT_REVIEW]} review",
        f"{counts[VERDICT_PASS]} passed",
    ]
    [...]
    body = ", ".join(parts) + f" ({scope})"
```

`packages/whisker/src/whisker/report.py:236-248`
```python
def _flag_rollup(results: list[WhiskerResult]) -> list[str]:
    """ruff --statistics style: flag categories, by tier, counted, sorted."""
    [...]
        for flag, n in sorted(counter.items(), key=lambda kv: (-kv[1], kv[0])):
            lines.append(f"  {str(n).rjust(4)}  {tier}  {flag}")
```

`packages/whisker/src/whisker/report.py:321-322`
```python
    if stats:
        lines.extend(_flag_rollup(results))
```

`packages/whisker/src/whisker/CLAUDE.md:219-221`
> - **`--stats`:** append a ruff-style flag rollup, counts per hard/soft flag
>   category (values stripped so "coverage 0.53 < 0.85" and "0.78 < 0.85"
>   aggregate into one `coverage <` row).

**Aggregate outputs today:** integer counts of `pass` / `review` / `fail`; optional flag-category counts. Percentages are not computed in `report.py` (caller could derive pass rate manually). No string `% perfect`, `% perfectly converted`, or equivalent appears in whisker reporting code.

`packages/whisker/src/whisker/facts.py:160-161`
> ``{type: {passed, total, pass_rate}}``. A type with no verified facts is
> omitted so a reviewer sees only the types actually exercised.

(Lane 3 `pass_rate` is per fact-type within one paper's facts report, not fleet "% perfect conversion".)

---

## 7. Golden ideals doctrine

### packages/tomd/tests/fixtures/golden/README.md

`packages/tomd/tests/fixtures/golden/README.md:17-23`
> - **Source** (`sources/<stem>.{pdf,html}`): the paper, input to both nets.
> - **Snapshot** (`snapshots/<stem>.md`): a byte-exact lock on tomd's *current*
>   output. Guarded by `test_pdf_golden` / `test_html_golden`. Answers "did the
>   output change at all?" Any figure PNGs the markdown references live beside it.
> - **Ideal** (`ideals/<stem>.md`): the structural *gold standard* (only for
>   blessed papers). Guarded by `test_golden_gate`. Answers "did the output get
>   worse than the ideal?"

`packages/tomd/tests/fixtures/golden/README.md:97-108`
> The structural gate (`tests/test_golden_gate.py`) compares tomd's output
> against BLESSED IDEAL goldens, not snapshots of tomd's own output. A blessed
> ideal lives at `ideals/<stem>.md` and encodes the correct structure (verbatim
> content, ideal heading levels, list nesting, fences, tables, chrome stripped).
> It is distinct from the `snapshots/<stem>.md` snapshots, which are tomd's current
> output and are guarded byte-exactly by `test_pdf_golden` / `test_html_golden`.
>
> A freshly-blessed ideal encodes structure current tomd does not reach yet, so
> its score starts below 1.0. `baselines.json` records each blessed paper's
> per-axis score (front-matter, heading, list, code, table, text); the gate
> fails if any axis drops below its committed baseline. The gap to 1.0 is the
> visible bug backlog.

`packages/tomd/tests/fixtures/golden/README.md:130-135`
> 2. Correct its STRUCTURE against the source: headings at the right level, lists
>    nested correctly, code fenced and labeled, tables intact, front matter in
>    canonical order. tomd already gets the content right, so you rarely touch the
>    words; the structural corrections are what make the draft a gold standard. An
>    uncorrected seed is byte-identical to tomd's output and is rejected at bless
>    time (and by `test_golden_gate`), so the correction step cannot be skipped.

### packages/whisker/src/whisker/golden_ideals.py

`packages/whisker/src/whisker/golden_ideals.py:8-17`
> """Golden ideals as ground truth for the deterministic lane.
>
> The tomd golden-QA workflow (upstream PR #257) maintains hand-corrected
> "ideal" markdown files under ``packages/tomd/tests/fixtures/golden/ideals/``:
> one ``<pid>.md`` per blessed paper, human-verified against the source. Unlike
> the markitdown oracle (an independent but WEAK converter, advisory only) an
> ideal IS ground truth, so scoring tomd's live conversion against it gives the
> deterministic lane a Lane-2-quality fidelity signal per paper, with zero
> configuration: any new ideal that lands in the directory is picked up on the
> next run.

`packages/whisker/src/whisker/golden_ideals.py:24-27`
> Verdict policy: ideal agreement stays ADVISORY (a review flag at most, never a
> hard fail). The calibrated hard gate (structural gates + unigram coverage) is
> untouched; wiring ideals into the hard gate would change the verdict model and
> needs its own calibration and sign-off.

`packages/whisker/src/whisker/golden_ideals.py:56-63`
> class IdealPanel:
>     """Fidelity of a candidate markdown against a human-blessed ideal.
>
>     All axes are the existing Lane-2 metrics. ``teds``/``mhs`` are ``None``
>     when the ideal lacks that modality (no tables / no headings): the axis is
>     ineligible, not a synthetic perfect score (bench null-eligibility rule,
>     schema v3 lesson). ``overall`` is the mean of the ELIGIBLE structural axes
>     only. ``recall`` is reported separately (strata stay separate, never
>     folded into overall).

`packages/whisker/src/whisker/tapetum_llm/tapetum_llm.md:57-59`
> source remains the factual authority; an ideal is structural ground truth, not
> permission to contradict the source.
