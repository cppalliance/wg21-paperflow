# Opus Meta-Reviewer E - Steelman + Product Decision + API/Docs/Complexity (BALANCING)

**Role:** independent balancing assessment. The other four opus reviewers hunt
flaws; this report's job is to keep the final verdict *fair and decision-useful*,
not a pile-on. Every claim below was re-verified against `score.py`, `report.py`,
`gates.py`, `constants.py`, `__init__.py`, `__main__.py`, and `CLAUDE.md`, not
taken on the personas' word. Runtime numbers are from `00-EVIDENCE-BASELINE.md`.

The user's actual decision is one question: **"is this conversion safe to
ship?"** Everything here is judged against that, not against benchmark elegance.

---

## Strongest case FOR

whisker is a **genuinely conservative, deterministic, broken-artifact filter**,
and on that narrow claim it delivers. Grounded in code, not marketing:

- **The hard gate has exactly two failure paths, and both are defensible.**
  `_decide` hard-fails only on (a) a structural gate failure or (b)
  `unigram_coverage < UNIGRAM_COVERAGE_FAIL_EDGE` (0.85) (`score.py:152-160`).
  `ref_nid` is layered on as a *soft* flag and "never hard-fails" in actual code
  (`score.py:175-178`), exactly as CLAUDE.md promises. There is no path where a
  weak markitdown oracle can sink a paper. The design principle "review beats a
  false pass" is implemented, not just asserted.

- **The structural gates catch real breakage.** `run_gates` (`gates.py:153-162`)
  flags truncated/empty bodies, missing front-matter keys (`title`/`document`),
  empty fenced code blocks, and header-less table separators. These are
  unambiguous "the artifact is broken" signals. The `no_empty_table` gate even
  guards against false positives on `---` thematic breaks and setext underlines
  (`gates.py:138-148`) - that is careful, not naive, code.

- **The content gate is on the *right* axis.** It runs on order-invariant
  `unigram_coverage`, not the order-sensitive shingle `coverage`
  (`score.py:156-162`, `constants.py:20-38`). CLAUDE.md records that an earlier
  shingle-gated design false-failed 43 correctly-reflowed multi-column papers;
  the fix matches how every serious benchmark (Docling set-recall, Nougat set-F1,
  OmniDocBench) separates content from reading order. The 3/382 unigram-floor
  fails are the ones genuinely worth stopping the line for.

- **It is deterministic and reproducible.** No LLM, no network, no randomness;
  `to_dict()` sorts flags and rounds to 4dp (`score.py:84-115`); report rendering
  is a pure function of inputs (`report.py:87-115`). 353 tests pass in 1.62s.
  This is a prerequisite for trustworthy QA that a cloud-LLM judge cannot offer,
  and it is satisfied.

- **Architecture invariants hold in practice.** `__init__.py` is re-export-only
  (`__init__.py:10-106`); `score.py`/`report.py` perform no writes; persistence
  is confined to `__main__.py`. "Library returns data; CLI persists" is real.

- **Epistemic honesty is in the code, not buried.** `constants.py:11-15` states
  the edges are "PROVISIONAL ... not yet a value fitted on a labeled corpus";
  CLAUDE.md's Calibration section documents exactly what was never run. A tool
  that tells you its thresholds are borrowed is more trustworthy than one that
  presents them as measured.

**Net:** as "block obviously broken markdown, deterministically, with near-zero
false-fail risk on content," whisker is fit for purpose *today*.

---

## Decisive case AGAINST

The case against is not that the code is bad - it is that **the product's
verdict labels promise more than the operational path can deliver, and the one
number the user cares about (false-pass rate) is unmeasured.**

- **`pass` is a pre-filter, not a ship certificate, and nothing measures how
  often it lies.** Zero labeled corpus members (`00` §4), `calibrate` never run
  (`00` §5), edges provisional (`constants.py:11-15`). The known blind spot is
  concrete: a dropped non-repeated paragraph or a permuted table cell that keeps
  `unigram_coverage >= 0.85` passes every operational check (`_decide` has no
  table-content or fact gate, `score.py:152-184`). Lane 3 `facts` exists to catch
  exactly this and is **non-operational** (`00` §4). So "pass" means "structurally
  clean + high token recall," which is necessary but *not sufficient* for "safe
  to ship," and its precision is literally unknown.

- **The trichotomy does not survive contact with the CI contract.** Default
  `--gate review` accepts both pass and review (`_GATE_ACCEPTS`,
  `__main__.py:80-84`); `_verdict_exit_code` returns non-zero only for `fail`
  (`__main__.py:114-120`). So the shipped default is a **binary** (14 blocked,
  368 green), not three-way triage. The yellow "review" tier changes terminal
  color and sidecar fields but **not the release decision**.

- **The review tier is an unprioritized inbox dominated by a spec-declared-benign
  signal.** `REGION_SOFT_COUNT = 1` (`constants.py:43-47`) makes a *single*
  misaligned region a review flag (`score.py:164-166`); 186 of 205 review papers
  trip it (`00` §3a), and CLAUDE.md itself says misaligned regions are "expected
  on clean papers." Telling a human "205 papers need review" when ~91% are
  documented furniture-stripping is not a precision queue.

- **`fail` is heterogeneous, so "block" is not one decision.** 9/14 ref-free
  fails are `heading_monotone` H2->H4 jumps (`gates.py:96-112`); only 3/14 are
  genuine content-missing (`00` §3a-3c). `P3941R2/R3/R4` fail with `uni=0.999,
  drift=0.001` *solely* on a heading level jump. A release engineer cannot treat
  all 14 fails as "reconvert - content missing"; 64% are cosmetic policy.

- **Public docstrings actively misdirect integrators.** `score.py:74-76` says the
  `ref_*` fields "are the primary verdict signal"; `score.py:199-200` says the
  oracle agreement "drives the verdict." Both are **false** against `_decide`
  (oracle is soft-only, never hard). An engineer who reads the dataclass/docstring
  first - the normal entry point - will wire `ref_overall` into pass/fail logic
  the code explicitly forbids.

- **The headline oracle number is inflated.** `ref_overall = (ref_nid + ref_teds
  + ref_mhs) / 3.0` always (`score.py:213-215`), with no null-eligibility, while
  `table_score`/`mhs` return **1.0** when neither side has tables/headings. The
  `bench` path nulls these axes (`bench.py:223-228`) precisely to avoid this; the
  score path does not. So the `ovr=` line that leads terminal output
  (`report.py:72-77`) can show artificial cross-converter agreement on
  table-less/heading-less papers. The verdict tier stays correct, but the
  *reported* agreement is misleading.

**Net:** whisker answers "is this artifact broken?" but the user asked "is this
safe to ship?" - and the gap (table-cell/formula fidelity, pass precision) is
exactly the part that is unmeasured and undeployed.

---

## Is the verdict actionable?

**At 54% review and zero calibration: partially, and only if you ignore the
labels as designed and use the tool as a hard-fail linter.**

Breaking it down by what action each tier actually enables:

- **As a CI gate (default `--gate review`): YES, narrowly.** It is a clean binary
  - 14/382 blocked, deterministic, reproducible. That is a real, automatable
  decision. But the 14 need a *second* human triage because 9 are cosmetic
  heading jumps, not content loss. So the gate is actionable for "stop the merge"
  but not for "what do I fix."

- **As three-way triage (pass=ship / review=look / fail=fix): NO.**
  - `review` (54%) is mostly the benign `misaligned region(s)` signal; it is not
    a precision queue and does not beat eyeballing the corpus unless those
    region-only flags are demoted to informational. The 54 unigram-band + 88
    drift papers that signal *real* ambiguity are buried under 186 furniture
    flags.
  - `pass` (43%) has no measured precision, so "ship on pass" is unjustified.
    The honest action is "skip the full read, spot-sample ~5%," not "ship blind."
  - The trichotomy collapses to a binary at the default gate anyway, so the
    middle label carries no release consequence.

- **The output is a rollup, not a decision brief.** `_item_line`
  (`report.py:64-84`) emits `uni=/cov=/drift=/qa=` plus a sorted flag string. It
  never says *look at what* or *for how long*. The operator must translate every
  review line into an action with no guidance.

**Bottom line on actionability:** the **fail** verdict is actionable (after a
cosmetic-vs-broken split). The **pass** verdict is actionable as "deprioritize +
sample," not "trust." The **review** verdict, at this operating point, is the
least actionable tier - it is where good papers go to wait behind documented
false alarms. So the *trichotomy as labeled* is not decision-ready; the
*hard-fail filter underneath it* is.

---

## My recommended verdict (+confidence +flip conditions)

### Verdict band: **usable-with-conditions** &nbsp;|&nbsp; **Confidence: high**

This is the same band the four cluster personas reached, and after independent
code verification I concur - but I want it on record that this is a *floor-raise*
from the flaw-hunters, not a pile-on agreement. whisker is **not garbage**: the
hard gate is sound, conservative, deterministic, tested, and honest about its
limits. It is **not unconditionally usable**: its own labels oversell, and the
ship-safety number is unmeasured.

**Conditions under which it is usable as-is (operate it this way today):**

1. **Run `--no-reference` for any decision.** The oracle adds review noise (147
   advisory flags, mean `ref_nid=0.836` below its own 0.85 edge, `00` §3b),
   changes **zero** fail verdicts, and ships the misleading `ref_overall`. Use the
   trustworthy reference-free hard gate; treat the oracle as a manual curiosity.
2. **Treat only `fail` as merge-blocking, then sub-triage it.** Separate
   `heading_monotone` (cosmetic, 9/14) from `unigram coverage < floor` +
   `no_empty_table` (real, 5/14) before acting.
3. **Treat `pass` as "deprioritize + spot-sample ~5%," never "ship blind."**
   Until calibration exists, an unknown false-pass rate forbids unattended ship.
4. **Do not wire `ref_overall`/`ref_*` into any automated logic.** The code
   forbids it; only the (wrong) docstrings invite it.

**Flip to `usable` (unconditional) when ALL of:**
- A labeled holdout (30-50 papers, human ship/fix/reject) is run through
  `calibrate`, and **pass-tier precision >= 95%** with fail correlating to human
  "broken" on the unigram-floor + empty-table cases.
- `heading_monotone` is split out of the content `fail` tier (own exit lane or
  demoted to soft), so "block" means "content broken."
- The `score.py` docstrings are corrected and `ref_overall` adopts the bench
  null-eligibility rule (or is removed from the headline).

**Flip to `garbage` when:**
- That same calibration shows the hard gate's **false-pass rate > 10%** on
  conversions humans reject and fitted edges still cannot meet any reasonable FPR
  budget - i.e., the gate is decorative. (Current evidence does not point here;
  this is the disconfirming test, not a prediction.)

---

## Top-3 issues for the final report

1. **[CRITICAL] No calibration -> `pass` precision is unknown, and the only check
   that would catch sub-floor content loss (Lane 3 facts) is non-operational.**
   This is *the* issue against the user's real decision. `pass` = structurally
   clean + `unigram_coverage >= 0.95` + no furniture deltas, but with zero
   measured TPR/FPR (`constants.py:11-15`; `calibrate` never run, `00` §5) and an
   acknowledged blind spot for permuted table cells / dropped paragraphs above
   0.85 (`score.py:152-184`; Lane 3 dead, `00` §4). "Pass" is a defensible
   *pre-filter*, not a ship certificate. Fix: commit a 30-50 paper labeled
   holdout, run `calibrate`, publish pass-tier precision.

2. **[HIGH] The verdict labels don't map to actions.** Two halves of one problem:
   (a) `review` (54%) is an unprioritized inbox where 186/205 papers trip the
   spec-declared-benign `misaligned region(s)` flag (`REGION_SOFT_COUNT=1`,
   `constants.py:47`; CLAUDE.md soft signals), and the default `--gate review`
   collapses pass+review to exit 0 (`__main__.py:80-84,114-120`) so the middle
   tier carries no release consequence; (b) `fail` mixes 9 cosmetic
   `heading_monotone` jumps with 3 real content-missing fails (`00` §3a-3c),
   making "block" ambiguous. Fix: demote region-only flags to informational (or
   raise the count / furniture-filter), and split heading_monotone out of the
   content fail tier.

3. **[HIGH] Score-path contract lies: docstrings + inflated `ref_overall`.** The
   `WhiskerResult` field comment and `score_markdown` docstring call the oracle
   "the primary verdict signal" that "drives the verdict" (`score.py:74-76,
   199-200`), contradicting `_decide` (oracle soft-only, `score.py:175-178`) and
   CLAUDE.md. Meanwhile `ref_overall = (ref_nid+ref_teds+ref_mhs)/3.0` averages
   synthetic 1.0s on table-less/heading-less papers with no null-eligibility
   (`score.py:212-215` vs `bench.py:223-228`), inflating the `ovr=` headline
   (`report.py:72-77`). Together these push an integrator to wire a misleading,
   advisory number into ship logic the code forbids. Fix: correct the docstrings;
   make `ref_overall` null-eligible like bench, or drop it from the headline.

---

### Verification note

Independently confirmed against code (not personas): hard-fail set =
gates + unigram floor only (`score.py:152-160`); oracle never hard-fails
(`score.py:175-178`); docstring/contract contradiction (`score.py:74-76,
199-200`); `ref_overall` no null-eligibility (`score.py:213-215`); default gate
collapses to binary (`__main__.py:80-84,114-120`); `REGION_SOFT_COUNT=1`
(`constants.py:47`); calibration provisional (`constants.py:11-15`); all gates
hard incl. `heading_monotone` (`gates.py:96-112,153-162`); `__init__.py`
re-export-only (`__init__.py:10-106`). The personas' factual claims in this
cluster held up; their convergence on **usable-with-conditions** is correct.
