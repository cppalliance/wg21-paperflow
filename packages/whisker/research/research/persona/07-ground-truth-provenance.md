# 07 - The Ground-Truth Provenance Skeptic

**Verdict:** usable-with-conditions — whisker honestly documents that it has no labeled ground truth, but the default production path still emits pass/review/fail as if those tiers were calibrated quality judgments; without labels, the tool validates internal consistency and borrowed priors, not conversion correctness.
**Confidence:** high

## Findings

- [CRITICAL] **No accuracy claim is defensible on this repo.** Lanes 1–3 (golden, bench/guard, facts) are built and tested but **cannot run**: `corpus/` holds only `README.md` + `EXAMPLE.facts.jsonl` (`00` §4: `whisker golden|facts|bench --corpus packages/whisker/corpus` all error with zero real members). Calibration was **never performed** (`00` §5: no `--labels` JSON; "No measured TPR / FPR / precision exists for any threshold"). Impact: the 163 pass / 205 review / 14 fail split on 382 papers (`00` §3a) is **unlabeled prevalence**, not precision, recall, or error rate; any statement like "42.7% of conversions are safe to ship" is epistemically invalid.

- [CRITICAL] **The only path that runs on real data is reference-free scoring plus an optional second converter** — not human ground truth. Evidence: `00` §4 ("only the reference-free / oracle SCORE path actually runs on real data"); `score.py:10-20` (hard gate = structural gates + tomd `check_content` + tomd `compute_metrics`; TEDS/MHS "require a labeled reference and live in whisker bench"). Impact: production QA is a **smoke test**, not a fidelity benchmark; the three-lane architecture described in `corpus/README.md:19-29` is aspirational until someone authors `<pid>.gt.md`, `.expected.md`, `.facts.jsonl`.

- [HIGH] **The reference-free hard gate is partially self-referential: it reuses tomd to judge tomd.** Evidence: `score.py:28-29,202-203` imports `check_paper_content` and `compute_metrics` from tomd; `constants.py:49-51` sets `QA_SCORE_SOFT_EDGE = 70` explicitly to "Mirrors tomd's own _NEEDS_REVIEW_THRESHOLD so the two tools agree on the review line"; `gates.py:10-14` ("need no ground truth … assert Markdown is structurally well-formed on its own terms"). Impact: structural gates catch broken artifacts (truncation, bad front matter) but **cannot detect semantic errors** tomd's own pipeline missed; folding tomd's QA score into whisker's review band aligns verdicts with the converter under test, not an external standard.

- [HIGH] **`unigram_coverage` is not independent ground truth — it treats the PDF/HTML text layer as oracle.** Evidence: `check_content.py:600-621` (PDF via `_extract_pdf_stream` / PyMuPDF `get_text()`, HTML via BeautifulSoup; recall = multiset of source tokens present in markdown); `score.py:156-160` (hard fail only below `UNIGRAM_COVERAGE_FAIL_EDGE = 0.85`, `constants.py:37`). Impact: shared blind spots (scanned pages, vector-only figures, text-layer emoji vs raster) yield **high unigram scores on wrong markdown**; only **3/382** ref-free fails hit the content floor (`00` §3a) while mean unigram coverage is **0.966** (`00` §3b), consistent with a loose, uncalibrated floor that rarely fires.

- [HIGH] **The markitdown "oracle" is a circular crutch if read as correctness — the code admits it, operators may not.** Evidence: `reference.py:10-14` ("Rather than hand-label gold Markdown, we run … converter … treat its Markdown as the reference"); `score.py:142-147,175-178` ("agreement != correctness"; `ref_nid` adds review only, never hard-fail); `CLAUDE.md:13-15,247-250` (same). With oracle on, mean `ref_nid` **0.836** and **147/382** below advisory edge 0.85 (`00` §3b) — yet neither side is labeled correct. Impact: low agreement means "two fallible converters disagree," not "tomd is wrong"; high agreement means "both made the same mistakes," not "tomd is right." Default-on oracle (`score_paper` default `reference_engine="markitdown"`, `score.py:268`) adds ~38% advisory review noise without provenance.

- [MED] **Provisional thresholds are borrowed literature priors, not fitted operating points.** Evidence: `constants.py:11-15` ("PROVISIONAL … not yet a value fitted on a labeled corpus"); `00` §5 (edges from DP-Bench/Docling/OmniDocBench norms; `calibrate` never run). Impact: `UNIGRAM_COVERAGE_FAIL_EDGE=0.85`, `REVIEW_EDGE=0.95`, `REF_NID_ADVISORY_EDGE=0.85` encode **someone else's corpus**, not WG21 paperflow; whisker cannot say what FPR those edges imply here.

- [MED] **Review-tier triage is dominated by signals explicitly declared benign, without label validation.** Evidence: ref-free soft rollup **186** "misaligned region(s)" vs 54 unigram review-band (`00` §3a); `constants.py:43-47` (`REGION_SOFT_COUNT = 1` — one region triggers review); `CLAUDE.md:233-236` ("expected on clean papers"). Impact: **53.7%** of papers land in review (`00` §3a) mostly on furniture-stripping artifacts; triage precision (does review correlate with human-needed fixes?) is **unmeasurable** without labels.

- [LOW] **Stale comment in `score.py` overstates oracle weight.** Evidence: `score.py:74-76` ("When present these are the primary verdict signal") vs `_decide` (`score.py:175-178`) where `ref_nid` is advisory soft only. Impact: misleads maintainers; does not change runtime behavior.

## False-pass hypothesis

A conversion that **permutes table cell text** or **drops a repeated boilerplate paragraph** while preserving multiset token recall above **0.85**, passing structural gates, and staying within tomd QA norms would **pass** the hard gate. Evidence: `facts.py` Lane 3 exists precisely because "A reflow can score high on every Lane 2 axis and still scramble a table cell" (`CLAUDE.md:37-40`); only **3/382** ref-free fails on unigram floor (`00` §3a); no `<pid>.facts.jsonl` in repo to catch it (`00` §4). Lane 3 is the designed antidote; it is not deployed.

## False-fail hypothesis

**P3941R2/R3/R4**: `uni=0.999`, `drift=0.001`, fail **solely** on `heading_monotone` H2→H4 (`00` §3c; `gates.py:105-109`). Nine of fourteen ref-free hard fails are heading pedantry, not content loss (`00` §3a). A human would likely ship these; whisker hard-fails without ground truth that the heading jump is wrong.

## What would change my mind

A **committed micro-corpus** (≥20 papers) with human-authored `<pid>.facts.jsonl` (`checked: verified` from source PDF/HTML, per `corpus/README.md:35-37`) plus a **held-out label file** for `whisker calibrate`, reporting measured TPR/FPR/precision on ref-free **fail** and **review** against human adjudication — demonstrating that pass tier correlates with "safe to ship" at a stated FPR, not merely that 353 unit tests pass (`00` §2: "353 passing tests is a quality signal for the CODE, not for the VERDICT's real-world accuracy").
