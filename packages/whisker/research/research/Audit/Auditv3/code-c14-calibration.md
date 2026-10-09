# C14 Calibration

**Role**: Audit whether verdict thresholds are calibrated against evidence or hand-tuned.
**Audited state**: whisker 0.5.0, working tree, manifest b9ad8ab0a464aaaf030bfb9a9576bdeed986f6510b83dbd87945bdd7fe68f771.
**Gates**: D4 (scoring accuracy, PROPOSED), D5 (corpus integrity / calibration data, PROPOSED).

## 1. Scope

Determine, per threshold constant in `constants.py` and `tapetum_llm/
constants.py`, whether it carries a recorded derivation (a measurement, a
cited external source, a documented calibration run) or is a bare numeric
literal with only a comment asserting intent. Verify the `calibrate.py`
ROC workflow still exists, is unexecuted against a committed labeled corpus,
and produces no promoted thresholds. Cross-check against the live evidence
in the ledger for any threshold whose provenance claim the runtime data now
contradicts or corroborates.

## 2. Commands and Exits

| Evidence | Command / source | Result |
|---|---|---|
| E1 | `uv run --package whisker pytest packages/whisker/tests -q --tb=line` | exit 1: 3 failed, 1784 passed, 8 skipped, 3 xfailed |
| E6 | `uv build --package whisker --wheel` | exit 0, no `thresholds.json` artifact in the wheel |
| E17 | `rt4_canaries.py` (metrology canaries) | live measurements against `UNIGRAM_COVERAGE_*`-class edges (indirect, see 3.4) |
| — | `packages/whisker/src/whisker/constants.py` read | every content/bench threshold, full file |
| — | `packages/whisker/src/whisker/tapetum_llm/constants.py` read | every tapetum-lane threshold, full file |
| — | `packages/whisker/src/whisker/calibrate.py` | not re-read this pass; Auditv2 §3.1 structural description carried forward, existence confirmed via `score.py` import graph (not imported by `score.py`; standalone CLI module per CLAUDE.md) |

## 3. Current Evidence

### 3.1 Provenance ledger, every threshold in `constants.py`

| Constant | Value | Comment-stated provenance | Class |
|---|---|---|---|
| `UNIGRAM_COVERAGE_FAIL_EDGE` | 0.85 | "clean-paper expectation... not yet a value fitted on a labeled corpus" | PROVISIONAL, hand-set |
| `UNIGRAM_COVERAGE_REVIEW_EDGE` | 0.95 | "DP-Bench/Docling clean-conversion recall" | PROVISIONAL, external-repo-analogy |
| `DRIFT_SOFT_EDGE` | 0.10 | none beyond "soft flag" | bare literal |
| `REGION_SOFT_COUNT` | 1 | none beyond "raises a soft flag" | bare literal |
| `REGION_BENIGN_UNIGRAM_FLOOR` | 0.95 | "tomd deliberately strips furniture... content is demonstrably complete" | reasoned, not measured |
| `QA_SCORE_SOFT_EDGE` | 70 | "Mirrors tomd's own `_NEEDS_REVIEW_THRESHOLD`" | inherited from another module, not independently derived |
| `TEDS_FLOOR` / `MHS_FLOOR` | 0.80 / 0.80 | none beyond section header "PROVISIONAL" | bare literal |
| `NID_FLOOR` | 0.90 | none beyond section header "PROVISIONAL" | bare literal |
| `CONTENT_RECALL_FLOOR` | 0.90 | "a clean conversion should preserve almost all reference word occurrences" | reasoned, not measured |
| `REF_NID_ADVISORY_EDGE` | 0.85 | "adopted from a literal repo constant: 0.85 = edgeparse's NID CI floor" | cited external source, named repo + field |
| `BENCH_REGRESSION_SLACK` | 0.03 | none | bare literal |
| `GUARD_AXIS_SLACK` | 0.02 | "matches OpenDataloader-pdf's per-axis check_regression tolerance" | cited external source |
| `BLOCK_LOCK_NED` / `BLOCK_ACCEPT_NED` / `BLOCK_FUZZY_RESCUE_NED` | 0.25 / 0.70 / 0.40 | "adopted VERBATIM from OmniDocBench" | cited external source, verbatim port |
| `BASELINE_MIN_ALNUM_CHARS` | 50 | "olmOCR's BaselineTest checks... we apply it per document" | cited external source, adapted |
| `BASELINE_MAX_REPEATED_NGRAM_RATIO` | 0.30 | none beyond "mojibake/extraction debris" | bare literal |

Of 16 distinct thresholds inspected, 5 cite a named external source or repo
constant (`REF_NID_ADVISORY_EDGE`, `GUARD_AXIS_SLACK`, the three
`BLOCK_*_NED` values, `BASELINE_MIN_ALNUM_CHARS`), 3 carry a stated
qualitative rationale without a number behind it (`REGION_BENIGN_UNIGRAM_
FLOOR`, `CONTENT_RECALL_FLOOR`, `QA_SCORE_SOFT_EDGE`), and the remainder
(`DRIFT_SOFT_EDGE`, `REGION_SOFT_COUNT`, `TEDS_FLOOR`, `MHS_FLOOR`,
`NID_FLOOR`, `BENCH_REGRESSION_SLACK`, `BASELINE_MAX_REPEATED_NGRAM_RATIO`)
are bare numbers accompanied only by a comment describing what they gate,
not why that number. None of the 16 carries a recorded TPR/FPR/precision
measurement from `calibrate.py`'s own output format. This matches Auditv2's
characterization ("PROVISIONAL... not yet a value fitted on a labeled
corpus") verbatim in the module header (`constants.py:8-16`); unchanged this
run.

### 3.2 Provenance ledger, `tapetum_llm/constants.py`

The advisory-lane thresholds show the same mixed pattern:
`CONFIDENCE_AMBIGUOUS_LO`/`HI` (0.35/0.65) are labeled "provisional and must
be refit on the labeled review set" and the module records the one
falsification available: "the band alone proved dead in production (0/198
escalations)" (`tapetum_llm/constants.py:16-26`), i.e. a measured outcome
against a threshold that is otherwise unfitted. `PAGE_RECALL_FLOOR` (0.90)
and `PAGE_MIN_TOKENS` (50) are the one pair in this file with an actual
calibration narrative: "Calibrated via an offline flip-check: p0957r8's
known defect (page 13, recall 0.8810) against a negative control of all 8
golden PDFs' non-trivial pages (107 pages, correct snapshots, worst healthy
page 0.9129). The gap between 0.8810 and 0.9129 is wide enough for a floor
at 0.90..." (`tapetum_llm/constants.py:172-188`). This is the one threshold
in either constants file that states a measured separation between a known
bad case and a full negative-control sweep, not just an external citation or
an unfitted placeholder. `SECTION_RECALL_FLOOR` (0.90) and
`TOKEN_DELTA_THRESHOLD` (5) carry no such narrative, only "the router is
lane-local" framing (`tapetum_llm/constants.py:211-226`); they are
structurally identical in form to `PAGE_RECALL_FLOOR` (both are recall
floors gating an LLM escalation decision) but only one of the two has a
recorded derivation.

### 3.3 `EVIDENCE_FUZZY_FLOOR` / `EVIDENCE_MIN_FUZZY_CHARS`, no calibration narrative

`EVIDENCE_FUZZY_FLOOR = 0.90` and `EVIDENCE_MIN_FUZZY_CHARS = 20`
(`tapetum_llm/constants.py:63-73`) gate whether an LLM-cited quote is
trusted as grounded evidence, load-bearing for every downstream demotion
rule in `fusion.py`. Their comments explain the failure mode they prevent
("a short generic phrase... clears 0.90 trivially... quotes below this
length must ground exactly") but cite no measurement of false-accept or
false-reject rates at these specific values. Same pattern for
`PAGE_QUOTE_MAX_DIFFS = 2` (cites the shape of the olmocr-bench formula, not
a fitted value) and `FUSION_REF_NID_FLOOR = 0.10` (no narrative beyond "a
near-empty or degenerate conversion").

### 3.4 The live canaries measure `unigram_coverage` behavior but do not calibrate its edge

Ledger E17's four canaries (C1-C4) all report `unigram_coverage` at either
0.9542 (C2, C3, C4, and the control) or 0.5021 (C1, the 46.7% deletion).
Both values sit far from either `UNIGRAM_COVERAGE_FAIL_EDGE` (0.85) or
`UNIGRAM_COVERAGE_REVIEW_EDGE` (0.95): C1's 0.5021 is well below the fail
edge (correctly triggers `fail`, per E17), and the others sit just under the
review edge, in the review band. This is consistent with the edges doing
their documented job on these four inputs, but four data points, one of
which is a 46.7% deletion far past any plausible boundary case, cannot
establish where the true operating point should sit; none of the canaries
probes the edge itself (e.g. a deletion sized to land at 0.86 or 0.94
unigram_coverage). The canaries are metrology probes for construct validity
(addressed in C15), not a calibration run, and the ledger does not claim
otherwise.

### 3.5 `calibrate.py` and its non-execution, unchanged

Not re-read line-by-line this pass; Auditv2 §3.1-3.5's structural
description (ROC sweep over `(value, is_bad)` samples, `OperatingPoint` /
`CalibrationResult` dataclasses, "returns data, CLI writes" discipline, no
auto-promotion) is carried forward as unchanged code shape based on the
absence of any diff-relevant finding in E6 (no `thresholds.json` in the
built wheel) or in `constants.py`'s header, which still reads "not yet a
value fitted on a labeled corpus" verbatim. E6 additionally confirms `uv
build --package whisker --wheel` exits 0 and ships no such artifact,
corroborating non-execution at the packaging level, not just the constants
level.

## 4. Findings

| # | Finding | Severity | Confidence |
|---|---|---|---|
| F1 | Of 16 `constants.py` thresholds inspected, 5 cite a named external source, 3 carry qualitative-only rationale, and 8 are bare numeric literals with a comment describing only what they gate, not why that value | MEDIUM | HIGH |
| F2 | `PAGE_RECALL_FLOOR` (`tapetum_llm/constants.py`) is the single threshold across both constants files with a recorded measured-separation calibration narrative (known-defect page vs. 107-page negative control); `SECTION_RECALL_FLOOR`, its structural sibling, has none | MEDIUM | HIGH |
| F3 | `EVIDENCE_FUZZY_FLOOR` and `EVIDENCE_MIN_FUZZY_CHARS`, which gate every downstream fusion demotion rule via evidence grounding, carry failure-mode reasoning but no measured false-accept/false-reject rate at their specific values | MEDIUM | HIGH |
| F4 | No `thresholds.json` or equivalent fitted-edge artifact exists in the repository or the built wheel (E6); `calibrate.py`'s ROC workflow remains, on this evidence, unexecuted against a committed labeled corpus | MEDIUM | HIGH |
| F5 | The live metrology canaries (E17) exercise `unigram_coverage` at two widely separated points (0.5021, 0.9542) and do not probe near either provisional edge, so they corroborate the edges' behavior on gross cases without calibrating the boundary itself | INFO | HIGH |
| F6 | `CONFIDENCE_AMBIGUOUS_LO`/`HI` carry one production falsification (0/198 escalations) that Auditv2 could not obtain live; this is evidence AGAINST the band's present usefulness, not evidence FOR its stated value | INFO | HIGH |

## 5. False-Pass Hypothesis

**Could a "PROVISIONAL" label make an actually-tuned threshold look
unaudited?** No evidence of this: every constant this report traced back to
its comment is consistent with either an external citation or an explicit
absence of a stated derivation. There is no case observed where a value
looks fitted (e.g. an oddly specific number like 0.847) but is labeled
provisional to evade scrutiny; the values present (0.85, 0.90, 0.95, 0.10,
0.02, 0.03, 5, 20, 50) are round numbers consistent with hand-selection.

**Could the calibration module's mere existence be mistaken for calibration
having occurred?** This is the live risk this report flags precisely: a
reader who sees "`calibrate.py` implements a complete ROC-based calibration
workflow" (Auditv2 F1, still true) could conflate infrastructure readiness
with an executed, evidence-backed operating point. E6's absence of a
`thresholds.json` artifact and the unchanged "not yet fitted" header text
are the falsifying checks that keep this distinction visible.

## 6. Gate/Dimension Mapping (PROPOSED)

| Gate | Dimension | Status (PROPOSED) |
|---|---|---|
| D4: Scoring accuracy | Threshold derivation completeness | PROPOSED MIXED: 5/16 constants.py thresholds externally cited, 8/16 bare (F1) |
| D4: Scoring accuracy | Evidence-grounding thresholds (`EVIDENCE_FUZZY_FLOOR` etc.) | PROPOSED UNCALIBRATED (F3) |
| D5: Corpus integrity | Calibration data / execution | PROPOSED NOT STARTED (F4), consistent with Auditv2 |

## 7. Limitations

- This report did not re-read `calibrate.py` in full this pass; its
  structural claims are inherited from Auditv2 and corroborated only
  indirectly (via E6's wheel contents and the unchanged `constants.py`
  header), not independently re-verified line-by-line.
- "Bare literal" classification is based on the comment text adjacent to
  each constant in the source read this run; it does not rule out
  derivation recorded elsewhere (a changelog entry, an external research
  note) that this report did not search for.
- The canary evidence in 3.4 is reused from the C15 metrology findings and
  is not a purpose-built calibration probe; no claim is made that four data
  points could calibrate an edge even if they had been designed to.
- Per 00-PRECONDITIONS.md §1, this is a working-tree audit, not reproducible
  from a clean clone without the pinned manifest.

## 8. Conclusion

The calibration infrastructure is unchanged from Auditv2: a complete,
unexecuted ROC workflow, provisional edges, and no promoted operating point
in the wheel or the repository. This pass adds a threshold-by-threshold
provenance ledger that Auditv2 did not produce at this granularity: most
`constants.py` values are bare numbers with intent comments rather than
either measurements or citations, a minority cite a named external source
verbatim, and exactly one threshold in the whole tapetum-lane constants file
(`PAGE_RECALL_FLOOR`) carries an actual measured-separation narrative. The
live canary evidence available this run corroborates the coarse behavior of
`unigram_coverage`'s edges without calibrating them. No verdict is rendered
on whether provisional-but-honestly-labeled thresholds are an acceptable
state for the current release; that judgment is deferred to synthesis.

## 9. Delta vs Auditv2

Auditv2's C14 (HEAD 51cb704) concluded "The C-CAL claim is accurate:
provisional edges, ready infrastructure, pending labeled data" (Auditv2 §8),
treating the provisional-status disclosure as sufficient and closing with a
PASS-flavored tone. This report does not dispute that the disclosure is
honest, but it decomposes "provisional" into three materially different
sub-classes (externally cited, qualitatively reasoned, bare literal) that
Auditv2's pass-level treatment did not separate, and it identifies one
threshold (`PAGE_RECALL_FLOOR`) that is qualitatively better-supported than
its own structural sibling (`SECTION_RECALL_FLOOR`), a comparison Auditv2's
code-only, LLM-lane-blocked audit could not make because it never observed
the tapetum-lane constants file's calibration narrative in the context of
live evidence. Auditv2 did not have access to the live canary runs (E17); this
report adds the observation (F5) that even the live evidence available this
run does not probe near the provisional edges, so the delta is additional
precision about what remains unverified, not a reversal of Auditv2's
top-line conclusion.
