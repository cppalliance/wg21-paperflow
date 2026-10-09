# Whisker Calibration Operating Protocol

**Status:** documentation only, no code changes. Defines the policy a future
`whisker calibrate` run must follow before any fitted edge is promoted into
`packages/whisker/src/whisker/constants.py`.

**Governing audit source:** `packages/whisker/research/research/Audit/Auditv1/p16-threshold-calibration.md`
("P16 — Threshold-Calibration & Operating-Point Researcher"). Every numbered
section below opens with the relevant P16 criterion quoted verbatim, then
restates it in whisker-specific terms.

## Scope: what this protocol governs

Whisker has exactly two threshold constants that gate a per-paper verdict via
a continuous, calibratable edge, both in `constants.py`:

```20:38:packages/whisker/src/whisker/constants.py
# -- Content coverage band edges (PROVISIONAL, pre-calibration) --------------
...
#   >= REVIEW_EDGE (0.95) : content OK (DP-Bench/Docling clean-conversion recall)
#   FAIL..REVIEW          : some words missing -> soft review
#   <  FAIL_EDGE  (0.85)  : content genuinely missing -> hard fail
UNIGRAM_COVERAGE_FAIL_EDGE = 0.85
UNIGRAM_COVERAGE_REVIEW_EDGE = 0.95
```

Everything else in `constants.py` that gates is either a boolean structural
gate (`gates.py`, no continuous threshold) or a bench/guard regression floor
(`BENCH_REGRESSION_SLACK`, `GUARD_AXIS_SLACK`, `TEDS_FLOOR`, `MHS_FLOOR`,
`NID_FLOOR`, `CONTENT_RECALL_FLOOR`, `STRUCTURAL_PARITY_MIN_REFERENCE_COUNT`
— these compare a run against a *committed baseline*, not against a
labeled-outcome ROC fit). Those two edges are the only ones `calibrate.py`
fits and the only ones this protocol covers.

`calibrate.py`'s module docstring states the fitting method:

```8:22:packages/whisker/src/whisker/calibrate.py
"""Fit whisker's content-coverage threshold edges from labeled data.
...
The gate is a "lower is worse" rule: a paper is FLAGGED when its
``unigram_coverage`` is BELOW the edge. Given samples labeled good/bad, this
module sweeps every reachable threshold, computes the full ROC confusion at
each, and selects the operating point that MAXIMIZES recall (true-positive rate,
bad papers caught) subject to a false-positive-rate ceiling, falling back to the
Youden-J maximizer when no threshold meets the ceiling. It reports the chosen
edge alongside its measured TPR/FPR/precision.
"""
```

The CLI (`packages/whisker/src/whisker/__main__.py`, `calibrate_main`) fits
the two edges from two different positive-class definitions in one pass:

```1181:1184:packages/whisker/src/whisker/__main__.py
    # FAIL edge: positive = genuinely bad (label fail). REVIEW edge: positive =
    # anything that needs human eyes (fail OR review). Both gate on coverage.
    fail_samples = [(cov, label == _LABEL_FAIL) for _, label, cov in samples]
    review_samples = [(cov, label in (_LABEL_FAIL, _LABEL_REVIEW)) for _, label, cov in samples]
```

Today both fits share one `--target-fpr` CLI flag and one constant,
`DEFAULT_TARGET_FPR = 0.05` (`calibrate.py:44`), passed identically to both
`calibrate_threshold` calls (`__main__.py:1188` and `:1191`). §1 below is the
Planner decision that ends that sharing.

---

## 1. Operating policy per P16 criterion 2.1

> **Criterion 2.1 — Documented operating policy before any numeric threshold**
>
> **Statement:** The project publishes, before calibration runs, which error
> type is intolerable (e.g., maximum FPR / minimum precision on bad
> conversions) and which metric is secondary (e.g., maximize TPR subject to
> FPR cap, or maximize recall subject to precision floor).
>
> **How to measure:** Written operating policy names: (a) primary constraint
> (FPR ceiling, precision floor, or explicit cost ratio C_FP:C_FN), (b)
> secondary objective when multiple thresholds satisfy the constraint, (c)
> fallback when the constraint is infeasible on the calibration set.
>
> — `packages/whisker/research/research/Audit/Auditv1/p16-threshold-calibration.md:21-25`

### The conflict this section resolves

Two existing whisker documents disagree on the FPR ceiling:

- `calibrate.py`'s `DEFAULT_TARGET_FPR = 0.05`, commented "at most 1 in 20
  good papers wrongly flagged" (`calibrate.py:41-44`).
- `packages/whisker/src/whisker/CLAUDE.md`'s stated aspiration, in its
  "Calibration status" section:

  > A `calibrate` step (label 30-50 papers, pick max recall at FPR <= 10%,
  > commit fitted edges with recorded TPR/FPR/precision) would replace these
  > with measured operating points; until then review beats a false pass.
  >
  > — `packages/whisker/src/whisker/CLAUDE.md:554-557`

`0.05` and `0.10` are not typos of each other. Both were written when whisker
had exactly **one** calibratable coverage-style edge in mind, before the
fail/review split existed as a modeled distinction in the calibration
tooling. Neither document was wrong; both were under-specified for a
two-edge world.

### Planner decision (this is a policy call, not an empirical result)

The fail-edge and review-edge carry **asymmetric costs**, so they get
**different** FPR ceilings:

| Edge | Primary constraint | Secondary objective | Fallback |
|---|---|---|---|
| **Fail edge** (`UNIGRAM_COVERAGE_FAIL_EDGE`) | FPR &le; **0.05** | maximize TPR (recall on bad papers) subject to that ceiling | Youden's J maximizer if the ceiling is infeasible on the calibration split |
| **Review edge** (`UNIGRAM_COVERAGE_REVIEW_EDGE`) | FPR &le; **0.10** | same: maximize TPR subject to the ceiling | same: Youden's J maximizer if infeasible |

Rationale for the split, not just a restatement of the numbers:

- A false positive on the **fail edge** hard-blocks a genuinely good paper.
  Hard-fail is the most severe, least recoverable error whisker can make
  against a good conversion (see `packages/whisker/src/whisker/CLAUDE.md`'s
  verdict model: "any structural gate failure ... or `unigram_coverage <
  UNIGRAM_COVERAGE_FAIL_EDGE`" are "the only ways to fail"). It gets the
  **stricter, lower** ceiling: `0.05`, i.e. `calibrate.py`'s existing
  `DEFAULT_TARGET_FPR` and its "1 in 20" framing.
- A false positive on the **review edge** only flags a good paper for human
  review, which is recoverable and cheap relative to a hard block. It can
  tolerate the **looser, higher** ceiling: `0.10`, the number CLAUDE.md
  already named.

This resolves the conflict as **"both documents were right about different
edges that used to share one constant,"** not as "one document was wrong."

**This decision is a Planner policy call, not an empirically derived
result.** It has not been validated against real labeled data because no
sufficient labeled corpus exists yet (see §6). It is reversible: once a real
labeled corpus reveals actual class-separation behavior (how cleanly
`unigram_coverage` separates good from bad papers in practice), these
ceilings should be revisited — a tighter or looser ceiling might turn out to
be the better trade against the labeled reality, and nothing here should be
read as claiming otherwise.

### Naming for the parallel code Executor

A parallel Executor is implementing this split in code by introducing two
distinct named constants in `calibrate.py`, replacing the single
`DEFAULT_TARGET_FPR`. The agreed names, so the code and this document stay
consistent regardless of which lands first:

```python
DEFAULT_TARGET_FPR_FAIL_EDGE = 0.05
DEFAULT_TARGET_FPR_REVIEW_EDGE = 0.10
```

This naming is a Planner decision already made. If this document is written
before the code change lands, the naming above is still correct and is not
the Executor's to change; if the code lands first, its constant names should
match this table.

---

## 2. Class definitions per whisker's use case

P16 criterion 2.1's operating-policy statement is generic across projects; it
does not name whisker's positive/negative class mapping. That mapping lives
in the CLI code, not in P16 itself, confirmed by reading `calibrate_main`
directly (`__main__.py:1181-1184`, quoted in "Scope" above):

| Edge | Positive class (the "bad" outcome to catch) | Negative class |
|---|---|---|
| Fail edge | human `label == "fail"` | `label` is `"pass"` or `"review"` |
| Review edge | human `label` in `{"fail", "review"}` | `label == "pass"` |

`_VALID_LABELS = {"pass", "review", "fail"}` (`__main__.py:1109`) is the
closed vocabulary the CLI's label loader accepts; no other string is a valid
calibration `label`.

The review edge's positive class is a strict superset of the fail edge's
positive class (`fail` papers count as positive for *both* fits), which is
why the two fits must run on the same underlying labeled pool with two
different boolean re-labelings, exactly as `calibrate_main` does — not on
two separately-sampled pools.

---

## 3. Labeling rubric

A labeler judges one question per paper: **is this whisker-converted
markdown a genuinely faithful, complete, non-corrupted representation of the
source paper?**

Use the same judgment vocabulary as the existing golden-PR ground truth at
`packages/whisker/corpus/dev-replay/labels.json`, whose schema (confirmed by
reading the file) is:

- `human_verdict`: values observed are `"merge"` and `"request_changes"`.
- `defect_groups[]`: a list of objects, each with `type`, `description`,
  `severity`, and `affected_count` fields (some entries additionally carry
  `source_evidence`, `ideal_evidence`, `page`/`pages`, or `token`, which are
  optional context, not part of the required field set).

A calibration label needs one more field this schema does not currently
carry: `label`, with value `pass` / `review` / `fail`. This is the exact
vocabulary `calibrate.py`'s CLI consumes, confirmed directly from
`_VALID_LABELS = {"pass", _LABEL_REVIEW, _LABEL_FAIL}` where `_LABEL_REVIEW =
"review"` and `_LABEL_FAIL = "fail"` (`__main__.py:1107-1109`).

**Critical: `label` must be the labeler's own independent severity judgment,
never copied from whisker's own output.** `dev-replay/labels.json` already
carries two fields that look tempting to reuse here but must **not** be used
as the calibration `label`: `expected_det_verdict` and `expected_llm_verdict`
(e.g. `p0957r8`: `"expected_det_verdict": "fail"`). Both of those are
predictions/records of what whisker's *own* deterministic gate or advisory
LLM lane produces or should produce. Using either as the calibration `label`
would fit the threshold to reproduce the very verdict it is supposed to
independently validate — the same circularity the blindness rule in §4
exists to prevent, just introduced through a data-reuse shortcut instead of
a worksheet-format shortcut. A new, independently-derived `label` field must
be added by a human who has not seen `expected_det_verdict` /
`expected_llm_verdict` while forming their judgment, if this pool is ever
reused for calibration.

---

## 4. Blindness rule (anti-circularity)

The labeler must **not** see any of the following while forming their
judgment:

- whisker's own computed verdict (`pass` / `review` / `fail`),
- the `unigram_coverage` value,
- any other deterministic gate output (hard flags, soft flags, sidecar
  fields).

If they did, the calibration would fit a threshold to reproduce the very
score it is supposed to independently validate — a circular, self-confirming
calibration that would "pass" no matter where the real separation line sits.

**This is a hard requirement for the worksheet format.** A parallel Executor
is building a sampler/worksheet tool for gathering calibration labels; that
tool must honor this rule by construction, not by labeler discipline alone.
Concretely: the worksheet must show only the paper's rendered candidate
markdown, and ideally a pointer to the source for the labeler to cross-check
against, and must never surface the score, the verdict, or any flag derived
from `score_paper` / `score_markdown`.

---

## 5. Frozen split assignment (P16 criterion 2.2)

> **Criterion 2.2 — Labeled calibration corpus independent of threshold
> tuning on the holdout**
>
> **Statement:** Thresholds are fit only on a **dedicated labeled calibration
> split** (or nested CV producing out-of-sample scores for calibration). The
> final reported operating point is evaluated once on a **held-out test
> split** that was not used to pick the threshold.
>
> **Anti-gaming guard:** Require frozen split IDs or hash of label file +
> explicit "τ selected on split A; metrics below on split B only."
>
> — `packages/whisker/research/research/Audit/Auditv1/p16-threshold-calibration.md:40-51`

Whisker-specific requirements:

- Every label entry must carry an explicit `"split": "calibration" |
  "holdout"` field.
- The split is assigned **once, at labeling time**, and is **never
  re-derived at calibration-run time**. This is P16 2.2's anti-gaming guard
  in whisker terms: the frozen `"split"` field IS the "frozen split ID"; the
  label file itself (or a hash of it) is the audit trail that the split
  assignment has not moved since labeling.
- Recommended split ratio: stratified, roughly **60-70% calibration / 30-40%
  holdout**, preserving class balance (the `pass`/`review`/`fail`
  distribution) in both halves as closely as the available N allows.
- **Hard requirement:** both splits must contain at least one example of
  each class relevant to the edge being fit, or the corresponding rate (TPR
  or FPR) is mathematically undefined on that split — `calibrate_threshold`
  itself enforces this for the fitting side (`calibrate.py:176-179` raises
  `ValueError` if either class is empty), and the same undefined-rate problem
  applies symmetrically to whichever split is used to report the final
  held-out metrics.

---

## 6. Target N and class balance (P16 criterion 2.3)

> **Criterion 2.3 — Minimum labeled N and class balance declared**
>
> **Statement:** Calibration documents labeled **N**, positive/negative
> counts, and acknowledges imprecision when N is small (especially for
> isotonic calibration or rare failure modes).
>
> — `packages/whisker/research/research/Audit/Auditv1/p16-threshold-calibration.md:59-63`

P16 does not mandate a single universal minimum N; it requires that N and
the class counts be *declared*, and that imprecision be flagged when N is
small. Whisker's own internal upgrade-path estimate, quoted verbatim, is the
working target:

> A `calibrate` step (**label 30-50 papers**, pick max recall at FPR <= 10%,
> commit fitted edges with recorded TPR/FPR/precision) would replace these
> with measured operating points; until then review beats a false pass.
>
> — `packages/whisker/src/whisker/CLAUDE.md:554-557`

### The real current numbers (re-verified directly against the source file)

`packages/whisker/corpus/dev-replay/labels.json` currently holds **9 total
labeled papers**. Its `human_verdict` field (not the `label`/`pass`-`review`-
`fail` field calibration needs — see §3) breaks down as:

- `"human_verdict": "merge"` — **1 paper** (`p2040r0`).
- `"human_verdict": "request_changes"` — **8 papers** (`p4020r0`, `p0957r8`,
  `p3556r0`, `p1068r11`, `p1122r3`, `p0533r9`, `p3411r5`, `p3953r0`).

For calibration purposes, "positive" means the *bad* outcome being flagged.
Re-reading the file directly (not assuming the direction): `request_changes`
is the bad outcome and `merge` is the good outcome, so on this framing **the
GOOD class (`merge`, n=1) is the scarce one, not the bad class**
(`request_changes`, n=8). This is the opposite of the usual "rare failure
mode" framing P16 2.3 warns about, and it does not change the conclusion:
either way, 9 total labels with a 1-vs-8 split is far below the 30-50 target
above, and it does not even reach a usable minimum for a *reliable* FPR
estimate on either edge in either direction (a fitted FPR from one single
negative example is a coin flip, not a rate).

**This protocol does not solve the labeling gap.** It only prepares the
pipeline (policy, class definitions, blindness, split, retrigger conditions)
so that once N is sufficient, running `whisker calibrate` is a labeling
task, not a coding task.

---

## 7. Recalibration triggers (P16 criterion 2.9)

> **Criterion 2.9 — Recalibration triggers and drift monitoring**
>
> **Statement:** Policy defines when τ must be recomputed: label schema
> change, metric definition change, score function change, material shift in
> document mix, or holdout FPR/TPR beyond tolerance vs committed record.
>
> — `packages/whisker/research/research/Audit/Auditv1/p16-threshold-calibration.md:179-183`

Adapted triggers for whisker, any one of which requires a recalibration run
before the committed edges can still be trusted:

1. A `WHISKER_SCHEMA_VERSION` bump in `constants.py` (currently `8`,
   `constants.py:306`) that touches any field the coverage computation or
   verdict model depends on.
2. Any change to how `unigram_coverage` itself is computed — this metric is
   computed upstream in `tomd`, not in whisker, so a `tomd` change to its
   content-check logic is a trigger even though it is outside whisker's own
   diff.
3. A material shift in the document mix being converted (e.g. a new WG21
   paper format, a new source type beyond PDF/HTML, or a shift in the
   proportion of table-heavy vs prose-heavy papers relative to what the
   calibration corpus represented).
4. A holdout replay showing FPR/TPR drift beyond a stated tolerance band
   versus the last committed calibration record (the tolerance band itself
   is set when the first real calibration record is committed; this
   protocol does not pre-set a number for a fit that does not exist yet).

---

## 8. C-LAB consequence

Once labels feed a gate threshold, the claims-registry classification of
ground-truth labels changes status. The registry row, quoted verbatim:

> | C-LAB | Golden-label role | `advisory` / `gate-bearing` | If gate-bearing:
> M2 IAA/adjudication required |
>
> — `packages/whisker/research/research/Audit/Auditv1/AUDIT-SCORECARD.md:41`

Today whisker's golden labels (`dev-replay/labels.json`, the holdout
anchors) are `advisory`: they validate the LLM lane and the deterministic
gate's behavior on known cases, but they do not themselves set a threshold.
The moment a labeled corpus's `label` field is used to fit
`UNIGRAM_COVERAGE_FAIL_EDGE` / `UNIGRAM_COVERAGE_REVIEW_EDGE` and that fit is
promoted into `constants.py`, C-LAB moves to `gate-bearing`.

That activates Extended Module M2, quoted verbatim from the audit synthesis:

> | M2 Ground-truth corpus rigor (IAA, adjudication) | p11 | labels are *gate-bearing* |
>
> — `packages/whisker/research/research/Audit/Auditv1/SYNTHESIS.md` §4.2, "Optional
> extended modules (run only on the matching claim)"

M2 requires ground-truth corpus rigor: inter-annotator agreement (multiple
labelers scoring the same papers and a measured agreement statistic) or a
documented single-adjudicator rationale (if only one person labels, a
written justification for why that is acceptable and what mitigates the
single-point-of-judgment risk).

**This is a KNOWN FUTURE CONSEQUENCE, to be actioned when labeling actually
begins, not something this document resolves now.** No labels have been
promoted to gate-bearing status yet (see §6: today's N is far too small to
promote anything), so M2 is not yet active. Whoever runs the first real
`whisker calibrate` fit and proposes promoting its output into `constants.py`
is the one who must satisfy M2 first.

---

## 9. Holdout separation from the existing holdout corpus

`packages/whisker/corpus/holdout/README.md` states its rule, quoted
verbatim:

> # Evidence Holdout Corpus
>
> Locked corpus for measuring LLM evidence precision and recall.
> **No threshold tuning permitted against this set.**
>
> — `packages/whisker/corpus/holdout/README.md:1-4`

**Explicit requirement: the calibration label pool must be a DIFFERENT
corpus, never drawn from `packages/whisker/corpus/holdout/`.** That corpus
exists specifically so at least one evidence set stays untouched by any
tuning process, ever; drawing calibration labels from it would destroy the
one thing that makes it useful as an independent check.

The calibration label pool may draw from `packages/whisker/corpus/dev-replay/`,
whose README states the opposite rule, quoted verbatim:

> **These are NOT holdout papers.** Thresholds and logic may be tuned
> against this set. The separate `../holdout/` set is locked.
>
> — `packages/whisker/corpus/dev-replay/README.md:6-7`

plus newly sampled papers gathered via the sampler/worksheet tool a parallel
Executor is building (see §4). But `dev-replay/` currently has only **9
entries** (§6), and none of them yet carry the independently-derived
`label` field this protocol requires (§3) — the field that exists today,
`expected_det_verdict`, is exactly the field that must **not** be reused as
that label (§3's circularity warning). That pool needs deliberate expansion
before it is a usable calibration source. **This document does not perform
that expansion**; it only states the requirement so the expansion work is
scoped correctly when it happens.

---

## 10. Mechanical promotion guard (C-CAL)

The canonical, committed location for a promoted calibration artifact is
`packages/whisker/corpus/calibration/thresholds.json`. It does not exist yet
(§6: no sufficient labeled corpus, no real calibration run).

`packages/whisker/tests/test_calibration_consistency.py` mechanically
enforces that a promotion is all-or-nothing and self-consistent: it fails CI
if the committed artifact and `constants.py`'s
`UNIGRAM_COVERAGE_FAIL_EDGE`/`UNIGRAM_COVERAGE_REVIEW_EDGE` ever disagree
(wrong number, wrong edge, stale artifact), if `edge_ordering_ok` is
`False`, if the artifact's `schema_version` does not match
`whisker.calibrate.CALIBRATION_ARTIFACT_SCHEMA_VERSION`, if a
max-tpr-at-fpr-method holdout breaches its target ceiling, or if
`constants.py`'s PROVISIONAL language is removed without a valid, consistent
artifact committed alongside it (and vice versa).

Read this section together with §1 (the two FPR ceilings the guard checks)
and §8 (promoting a fit activates C-LAB/M2 ground-truth-corpus rigor): a
promotion is not complete until all three are satisfied.

---

## 11. Golden-validation power report (G3): why this set cannot fit, only check

`packages/whisker/corpus/calibration/golden_validation_labels.json` is a
second, independent, LLM-free label source: each entry pairs a real
converter output (tomd or markitdown, run against the actual source) with a
deterministic content-loss label derived from `golden_labels.py` (local to this directory)
against the human-blessed golden ideal. It exists to VALIDATE a threshold
fitted elsewhere (§9's `dev-replay`/sampler pool, once populated), never to
fit one itself — this section shows the arithmetic reason why fitting on it
would be indefensible even if the intent were otherwise.

### Current counts (tomd + markitdown, 11 non-holdout golden papers, `p4182r0` excluded per its holdout role)

| `label` | count |
|---|---|
| `pass` | 18 |
| `review` | 3 |
| `fail` | 2 |

A third engine (marker, via `whisker survey`) was deliberately NOT added
here, after starting and then cancelling that run mid-flight. Reasoning,
stated plainly because it reverses an earlier step in this same effort: no
golden paper contains a genuine tomd content-loss failure (tomd's row is
`good`/`pass` on 10 of 11 golden papers, `review` on the 11th — see the tomd-
specificity note below), so NO non-tomd converter, however many are added,
can supply tomd-specific true-positive evidence for this gate. markitdown
already supplies the one thing a second converter usefully adds: proof that
`unigram_coverage` discriminates SOME severe content loss at all (its two
`bad`-labeled rows below). A third converter (marker) would only repeat that
same generic, non-tomd-specific claim at real cost: CPU-hours of OCR
inference, and repurposing `whisker/survey/` (a competitor-monitoring tool,
scoped to monthly benchmark runs) as a calibration-data generator, which is
not what that module exists for. Team tomd/whisker's calibration question is
"does whisker's gate correctly classify tomd's own output," not "how do
competitors compare" — that second question already has its own home
(`benchmark/`) and its own cadence, and blending it into calibration blurs
both.

### Applying `MIN_SAMPLES_PER_CLASS_PER_SPLIT` (`calibrate.py:89`, currently `5`)

**Fail edge** (positive class = `fail`): `n_pos=2`, `n_neg=20`. A frozen 60/40
calibration/holdout split needs at least 5 positive examples in EACH split,
i.e. at least 10 positive total before any split is drawn. This set has 2.
`calibrate_threshold_with_holdout` would raise
`InsufficientCalibrationDataError` on the calibration split alone, before
holdout is even considered.

**Review edge** (positive class = `fail` OR `review`): `n_pos=5`, `n_neg=17`.
Marginally better, but still short: 5 total positives cannot be divided into
two splits of at least 5 each. Every possible split leaves at least one side
with 0 positive examples (undefined TPR) or fewer than the minimum-per-class
floor.

### Conclusion

Even used in full, with no split held back for anything else, this golden
set cannot support a defensible fit for either edge. This is not an
execution defect; it is the exact shortfall the plan predicted before
building the set: real converters lose recall on golden papers rarely (the
`fail`/`review` classes are the scarce ones here, not `pass`), so a
human-blessed ideal set of this size is structurally suited to be a
**checker**, never a **fitter**. Adding a third non-tomd converter would not
change this arithmetic in any way that matters (see above): it cannot supply
what is actually missing, which is a genuine tomd failure. G4's separately-
sampled, larger, tomd-only labeled pool remains the fit source; this set
remains G5's independent check, split by construct into two distinct claims:

### Two distinct claims this set can support, and the one it cannot

1. **tomd specificity (production-relevant, this row set can prove it):**
   does a fitted edge avoid false-flagging tomd's own clean golden output?
   All 11 tomd rows: 10 `pass`, 1 `review` (`p0533r9-tomd`,
   `unigram_coverage=0.8864`), 0 `fail`. A useful, already-visible sanity
   check today, with zero fitting involved: under the CURRENT provisional
   edges (`UNIGRAM_COVERAGE_FAIL_EDGE=0.85`,
   `UNIGRAM_COVERAGE_REVIEW_EDGE=0.95`, `constants.py:37-38`),
   `0.8864` already lands in the review band, matching the independently-
   derived golden label exactly. One data point of convergence, not a
   calibration, but a real, tomd-specific, zero-cost consistency signal.
2. **Generic discriminative validity (markitdown supplies this, marker would
   only repeat it):** does `unigram_coverage` separate ANY severe content
   loss from ANY clean conversion, across converters in general? markitdown's
   two `bad` rows (`p1068r11`, `p2040r0`) answer this; a third converter adds
   no new claim, only a third data point for the same claim.
3. **tomd sensitivity/TPR on real failures (this set CANNOT support this,
   with any number of converters added):** no golden paper contains a real
   tomd failure, by definition of having been promoted to golden status. This
   is exclusively G4's job, on its own tomd-sourced, separately-labeled pool.

---

## 12. Pre-registered G5 convergence criteria (written BEFORE the G4 fit exists)

Written before any threshold has been fitted on the machine-labeled pool
(G4), so it cannot be tuned after the fact to whatever the fit happens to
produce — that would be exactly the "calibrate on hand-picked obvious
failures" gaming vector P16 2.3 names, just moved from sample selection to
tolerance selection.

**A. Zero-miss rule on known severe content loss (hard gate, n=2, no
statistics needed).** The two golden-derived `fail` rows
(`p1068r11-markitdown`, recall 0.2610; `p2040r0-markitdown`, recall 0.3904 —
see `golden_validation_labels.json`) must NOT be classified `pass` (i.e.
`unigram_coverage >= UNIGRAM_COVERAGE_REVIEW_EDGE`) by the frozen
fitted-tau. These two cases are unambiguous, human-blessed-ideal-derived
severe failures; no continuous tolerance is needed to state "a coverage gate
that cannot catch either of its two clearest known failures has failed,"
full stop.

**B. tomd-specific FPR ceiling on known-good rows (hard gate, n=10,
non-degenerate).** At most **1 of the 10** golden-derived `tomd` `pass` rows
may be flagged `review` or `fail` by the frozen tau — i.e. tomd-specific FPR
on the golden set &le; **10%**. This reuses
`DEFAULT_TARGET_FPR_REVIEW_EDGE = 0.10` (`calibrate.py:77`), an already-
committed project number, rather than inventing a new one for this check.
tomd rows are used here, not markitdown, because tomd is the production-
relevant converter (§11.1); a false positive on tomd's own clean golden
output is the error this whole calibration effort exists to avoid.

**C. Bootstrap-overlap corroboration (soft, reported not gating).** Where N
allows (the pooled `n_neg=20` good side of the golden set), compute a 95%
bootstrap band via the already-implemented `bootstrap_holdout_band` at the
frozen tau, and report whether G4's own holdout FPR point estimate falls
inside that band. This is disclosed per P16 2.3's requirement to state
imprecision "even wide," not used to force a promote/refuse decision on its
own — the golden set's `fail` side (`n_pos=2`) is too small for a band to
mean anything statistically, which is exactly why A exists as a deterministic
substitute for that side instead.

**Decision rule:** A and B BOTH pass → promotion eligible (subject to G6's
mechanical guard). Either A or B fails → refuse, document the exact numeric
failure, D4 stays capped. C is always reported alongside, regardless of the
A/B outcome, for transparency.

---

## 13. The FAIL edge cannot be empirically calibrated from this corpus (found during G4 sampling)

Re-drawing the calibration sample stratified by raw `unigram_coverage` value
(not whisker's compound verdict, which conflates structural gates with
content coverage — see the diagnosis that motivated this re-draw) surfaced a
population-level fact, not a sampling artifact: across the **entire**
376-paper non-golden corpus, only **4** papers have `unigram_coverage < 0.85`
(`UNIGRAM_COVERAGE_FAIL_EDGE`): `P3978R0` (0.7951), `P4012R0` (0.8389),
`P4167R0` (0.8393), `P4231R0` (0.8427). The mid band (`0.85 <= x < 0.95`) has
**49**; the high band (`>= 0.95`) has **323**.

This is a hard ceiling, not a labeling-effort problem: `MIN_SAMPLES_PER_CLASS_PER_SPLIT
= 5` needs at least 10 positive examples total before any calibration/holdout
split can be drawn for the FAIL edge (positive = independently-judged severe
content loss). Even a maximally generous independent re-judgment of the
"low"-band papers (all 4 count as positive) plus every "mid"-band paper an
independent judge ALSO calls severe (which would be a surprising, band-
crossing outcome, not the expected one) cannot manufacture the missing base
rate: there simply are not 10 real conversions in this corpus with severe
content loss. Lowering `MIN_SAMPLES_PER_CLASS_PER_SPLIT` to manufacture a fit
is explicitly the P16 2.3 gaming vector this protocol has refused twice
already (§3 for the golden set, here again for the full corpus) and is
refused a third time for the same reason.

**Consequence for scope, decided here rather than discovered by a failed
fit later:** the REVIEW edge (`UNIGRAM_COVERAGE_REVIEW_EDGE`) has a workable
population (49 mid-band papers, plenty for 5/5/5/5 splits) and remains a
realistic calibration target. The FAIL edge does not, on this corpus, with
this converter, today. Two honest paths forward, not mutually exclusive:

1. Calibrate the REVIEW edge only in this pass; leave
   `UNIGRAM_COVERAGE_FAIL_EDGE` explicitly `PROVISIONAL`, but replace the
   current justification ("hand-set from the clean-paper expectation") with
   this quantitative one: only ~1% of real conversions ever cross below it,
   so its practical hit rate is rare by construction, and a defensible
   population-based statement ("N=4/376 real papers ever trigger this edge;
   below the minimum N for an empirical fit; provisional pending corpus
   growth") is itself real audit evidence — an honest "cannot calibrate,
   here is the measured reason why" — not a gap.
2. If the FAIL edge specifically must be calibrated regardless, the only way
   is growing the underlying converted-paper corpus (more of WG21's ~381+
   papers converted and scored), which is a paperflow ingestion project, not
   a calibration-labeling task, and is explicitly out of scope here.

1. Two edges, two ceilings: fail edge FPR &le; 0.05, review edge FPR &le;
   0.10, both maximize-TPR-then-Youden-fallback (§1). This is a reversible
   Planner call, not an empirical result.
2. Positive/negative class mapping is fixed by the existing CLI code, not
   invented here (§2).
3. Labels need a `pass`/`review`/`fail` field, independently judged, never
   copied from whisker's own verdict fields (§3, §4).
4. Labeling must be blind to whisker's score/verdict (§4), split must be
   frozen at label time (§5), and the corpus is nowhere near the 30-50
   target — today it is 9 papers, 1 `merge` (good, scarce) vs 8
   `request_changes` (bad) (§6).
5. Recalibration triggers, the C-LAB/M2 consequence, and holdout separation
   are documented as future obligations, not resolved now (§7, §8, §9).
6. A second, independent, LLM-free label source now exists:
   `packages/whisker/corpus/calibration/golden_validation_labels.json`
   (`golden_labels.py` in this directory, recall-only construct-validity rule). It is
   arithmetically too small to fit either edge itself (§11) and must never
   be used to; its sole role is to check convergent validity of a threshold
   fitted from the §6 pool once that pool exists.

## 14. G4 panel design: 2 raters, deterministic tie-break (pre-registered before any real label)

The original plan named three open-weight annotator families
(`alliance-pod`, `b200x2-gemma4`, `b300-qwen36-27b`) plus a Claude
adjudicator. A real reachability check (`GET /v1/models` timing out on all
three, then a real `/v1/chat/completions` probe) found only `alliance-pod`
answering; the other two pods are not running and, per explicit user
instruction, will never be provisioned ("wir werden NIEMALS weitere Pods
haben"). The panel is corrected here, in writing, before a single real label
is produced — not discovered after the fact and back-fit to whatever came
out.

**Panel: 2 independent raters per candidate paper.**

- **Rater A** — `alliance-pod` (`deepseek-v4-pro`, self-hosted, model-sovereign).
  Called directly via `httpx` against `{base_url}/chat/completions`
  (`SERVICES.toml`'s `alliance-pod` entry, key from `.env`'s
  `ALLIANCE_POD_KEY`), mirroring the existing call shape in
  `whisker/llm/readback.py`'s `_ask_pod`. `temperature=0.0`. System
  prompt asks ONLY the content-fidelity question (§3's rubric); the worksheet
  passed in is the output of `build_blind_worksheet` in `calibration_sampler.py` (local to this directory), so Rater
  A never sees `unigram_coverage` or whisker's own verdict.
- **Rater B** — Claude (Sonnet, run as a Task subagent in this session, not
  via the missing `ANTHROPIC_API_KEY`/`anthropic-opus` service). Reads the
  SAME blind worksheet content, independently, before seeing Rater A's
  output. Allowed under project rules because this is calibration-labeling
  (a validation/QA activity), not a production analytical-pipeline call; the
  model-sovereignty rule (`CLAUDE.md`) explicitly permits Claude for
  "development, validation, and adjudication."

**Independence discipline:** both raters read the identical blind worksheet
text. Rater B's judgments are formed and recorded before either rater sees
the other's label or reasoning, so a disagreement reflects genuine
inter-rater variance, not anchoring.

**Deterministic tie-break rule (fixed in advance):**

| A vs B | Resolution |
|---|---|
| Same label | Use it. |
| Adjacent disagreement (`pass`/`review` or `review`/`fail`) | Use the MORE SEVERE (worse) of the two. Matches the project's already-stated bias ("review beats a false pass", `CLAUDE.md` / §1 above) — a conservative default under genuine rater uncertainty, not a novel policy invented for this check. |
| Maximal disagreement (`pass` vs `fail`) | NOT resolved mechanically. Logged as a named exception and given a written single-adjudicator rationale by the Planner, reading both raters' stated reasoning plus the source paper directly. This is the documented-single-adjudicator allowance §8/M2 already permits when only one person labels; expected to be rare (a `pass`/`fail` gap implies at least one rater badly misjudged content-fidelity), and every such case is named explicitly in the labels file's provenance, never silently folded in. |

**Consequence for M2 (C-LAB gate-bearing rigor, §8):** a documented
single-adjudicator rationale (this table plus any maximal-disagreement notes)
IS this pass's M2 answer — 2 raters instead of 3+1, honestly disclosed as a
narrower panel than originally scoped, with the exact reason (pod
availability, permanent per user instruction) recorded rather than hidden.

---

## 15. G4/G5/G6 executed: fit succeeded, external validation passed, internal generalization guard REFUSED promotion

Both raters labeled all 34 candidates. Two maximal-disagreement cases
(`P3982R2`, `P4167R0`) were resolved by a written single-adjudicator
rationale (§14's table), NOT by deferring to either rater: for each, the
disputed passage was grepped directly against the extracted worksheet/source
text rather than argued from the raters' prose.

- `P3982R2` (A: `fail`, B: `pass`) → **`pass`**. Rater A's `fail` rationale
  claimed the "Proposed polls" wording and two named references were
  missing. Both are verbatim present in the candidate ("Foward P3982R1 as
  resolution for PL007...", "Poland", "Tomasz Kaminski" in the References
  section). Rater A's claim was factually wrong.
- `P4167R0` (A: `pass`, B: `fail`) → **`fail`**. Rater B's `fail` rationale
  claimed a 3-translation-unit module/ADL worked example (`make()`,
  `apply()`, `test()`, `struct Z`) was missing. Confirmed: the source
  contains exactly that example (Example 2, TU #1/#2/#3); the candidate
  retains only TU #1 and jumps straight to an unrelated, smaller Example 3.
  TU #2/#3 are verifiably absent from the candidate.

**Final label distribution (34 candidates):** 24 `pass`, 6 `review`, 4
`fail`. Split frozen once (seed 42, stratified: positive pool
review+fail=10 split exactly 5/5 per `MIN_SAMPLES_PER_CLASS_PER_SPLIT=5`;
`pass`=24 split 15/9 by coverage band) — committed at
`corpus/calibration/labels.json`.

### G4g: `whisker calibrate` fit result

```
unigram_coverage_review_edge: threshold=0.9341
  calibration (n=20, 5 pos / 15 neg): tpr=0.800 fpr=0.0667 (ceiling 0.10, met)
  holdout    (n=14, 5 pos /  9 neg): tpr=0.800 fpr=0.2222 (ceiling 0.10, BREACHED)
unigram_coverage_fail_edge: NOT FIT
  calibration split has only 2 positive example(s); need >= 5 per class per
  split (as predicted in section 13)
```

Artifact: `corpus/calibration/thresholds_g4.json` (kept as the audit trail
of this fit attempt; NOT copied to the canonical `thresholds.json` path —
see G6 below for why).

### G5: convergent validation against golden-derived labels (pre-registered §12)

Checked at the fitted tau (0.9341) against `golden_validation_labels.json`
(`golden_labels.py` in this directory, recall-only, never used to fit anything):

- **A (zero-miss, hard gate): PASS.** Both known severe cases
  (`p1068r11-markitdown` cov=0.2624, `p2040r0-markitdown` cov=0.3917) sit far
  below tau; neither would slip through as `pass`.
- **B (tomd FPR ceiling, hard gate): PASS.** 0 of the 10 golden `tomd` `pass`
  rows are false-flagged (ceiling: <= 1/10). Closest margin: `p0957r8-tomd`
  cov=0.9628 vs tau=0.9341.
- **C (bootstrap overlap, soft): reported.** Pooled golden set (`n_pos=2`,
  `n_neg=20`) 95% bootstrap FPR band at tau: `[0.0000, 0.3333]` (wide, as
  predicted, because `n_pos=2`). G4's own holdout FPR point estimate
  (0.2222) falls inside this band — weak corroboration, not strong, exactly
  as the band's own width warns.

**A and B both PASS → G5 alone says promotion-eligible.**

### G6: the mechanical guard (`test_calibration_consistency.py`) REFUSED promotion

G5 checks whether tau separates KNOWN cases in an INDEPENDENT dataset. G6's
own guard checks something different and, for this specific fit, decisive:
whether the calibration-split operating point (which promised FPR <= 0.10
under `max_tpr_at_fpr`) actually holds on ITS OWN held-out data. Staging the
real artifact at the canonical path and running the project's own committed
consistency test (not just reading the code) produced:

```
artifact fitted.unigram_coverage_review_edge used method='max_tpr_at_fpr'
but its holdout fpr=0.2222 exceeds the target ceiling 0.1. The
max-tpr-at-fpr method is only trustworthy when the calibration-split
ceiling generalizes to holdout; a breach here means the fit does not hold
up and must not be promoted as-is.
```

This failure is **independent of what value is written into `constants.py`**
— it is purely an artifact-internal check. Re-splitting the labeled pool to
hunt for a holdout draw that clears the ceiling is explicitly the P16 2.3
gaming vector this protocol has refused three times already (§3, §13); doing
it a fourth time here, on the frozen split, would be the same move with
better cover. Forcing the Youden's J fallback when the FPR-ceiling method
already succeeded on the calibration split would be equally illegitimate
post-hoc method-shopping.

**Root cause (measured, not assumed):** holdout `n_neg=9`. A single
additional false positive moves FPR by 1/9 ≈ 11.1 points. The observed
holdout confusion is `tp=4, fp=2, tn=7, fn=1` — 2 false positives on 9
negatives is a real, not a freak, outcome at this N; it is a genuine
calibration/holdout instability at the current sample size, not a labeling
or code defect.

**Decision: REFUSE promotion.** `UNIGRAM_COVERAGE_REVIEW_EDGE` stays
`PROVISIONAL` at its current hand-set value (0.95), same as
`UNIGRAM_COVERAGE_FAIL_EDGE`, but the honest justification changes: this is
no longer "never attempted." A full labeling round, an external convergent
validation pass, and a real fit attempt exist, are committed, and this
specific attempt's own internal consistency guard is the reason it was not
promoted, not any absence of effort. `packages/whisker/corpus/calibration/
labels.json`, `thresholds_g4.json`, and `g5_convergence_result.json` are the
committed evidence trail.

**Two honest paths forward, not mutually exclusive (mirrors §13's framing
for the fail edge):**

1. Grow the holdout side specifically (more `pass`-band and `review`-band
   labels, not just more of the already-adequate calibration side) so a
   single false positive stops being an 11-point swing. This is a labeling
   task, reusing the same 2-rater pipeline (§14), not a code change.
2. Accept the current REVIEW edge as PROVISIONAL-with-evidence and revisit
   after the next corpus growth cycle, consistent with §13's fail-edge
   treatment: an honest "attempted, real fit, real refusal reason" is itself
   audit evidence, not a gap to be hidden.

This does **not** lift the D4 uncalibrated-threshold soft cap
(`AUDIT-SCORECARD.md` §0.2) package-wide: `TEDS_FLOOR`, `MHS_FLOOR`,
`NID_FLOOR`, `CONTENT_RECALL_FLOOR`, `REF_NID_ADVISORY_EDGE`, and
`READING_ORDER_SOFT_EDGE` remain untouched, unattempted, and still
`PROVISIONAL`, and even `UNIGRAM_COVERAGE_REVIEW_EDGE` itself did not clear
its own promotion bar this round. What changes for a future audit cycle is
narrower and factual: "zero calibration provenance exists anywhere in the
package" (Auditv5's D4 finding) is no longer literally true — a real fit,
a real external validation, and a real, evidenced refusal now exist for one
of the seven uncalibrated edges. Whether that narrow fact moves D4's grade
at all is an audit-synthesis judgment call for the next audit cycle, not
decided here.

---

This document does not change any code and does not promote any threshold.
Section 15 records that calibration WAS run (G4-G6) and its outcome was a
documented, evidence-based refusal, not an absence of attempt. It exists so
that the next attempt (corpus growth, then re-fit) follows an already-agreed
policy, not a re-litigation of one.
